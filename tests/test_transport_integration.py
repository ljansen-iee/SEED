"""Focused standard-library transport checks; all generated data stays in TEMP.

Optional TRANSPORT_TEST_SOURCE_ROOT selects a read-only source repository.
Optional TRANSPORT_TEST_OUTPUT_DIR retains logs/artifacts below an external directory.
Run with python -B -m unittest discover -s tests -p test_transport_integration.py.
"""

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

from transport.build_final_energy_demand import generate_transport_indicators, calc_for_scenario
from transport.helpers import load_transport_config, refresh_unsd_master_data


ROOT = Path(__file__).resolve().parents[1]
YEARS = [2030, 2035, 2040, 2045, 2050]
SCENARIOS = ["BAU", "Progressive", "Optimistic"]
KEYS = {"2020"} | {f"{year}_{scenario}" for year in YEARS for scenario in SCENARIOS}


def fingerprint(folder):
    return {
        str(path.relative_to(folder)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in folder.rglob("*") if path.is_file()
    }


def detail_frame(fuels, enduse="LDV", mode="Road"):
    return pd.DataFrame([
        {"Sector": "Transport", "Subsector": "Passenger", "Mode": mode,
         "End-Use": enduse, "Technology": "test", "Fuel": fuel,
         "Scenario": "2030_BAU", "Final Energy Demand (GWh)": value}
        for fuel, value in fuels.items()
    ])


class TransportIsolationTests(unittest.TestCase):
    def test_lpg_is_gas_not_oil_and_road_conserves_detailed_energy(self):
        detailed = detail_frame({"Gasoline": 1000, "Diesel": 500, "LPG": 200,
                                 "Electricity": 300, "Hydrogen": 10, "Bio Diesel": 50})
        row = generate_transport_indicators(detailed, "Morocco").iloc[0]
        self.assertAlmostEqual(row["road oil"], 1.5)
        self.assertAlmostEqual(row["road gas"], 0.2)
        self.assertAlmostEqual(row["total road"], 2.06)
        self.assertAlmostEqual(row["total road"], sum(row[col] for col in
                               ["road oil", "road gas", "road electricity", "road biomass", "total road fcev"]))
        zero = generate_transport_indicators(detail_frame({"LPG": 0}), "Morocco").iloc[0]
        self.assertEqual(zero["road oil"], 0)
        self.assertEqual(zero["total road"], 0)

    def test_activity_kwh_to_gwh_to_twh_hand_check(self):
        metrics = {name: {"2030_BAU": value} for name, value in {
            "Population": 1, "Mobility per capita - Passenger": 1000,
            "Share per Subsector - Road Passenger": 100, "Share per Mode - LDV": 100,
            "Load Factor - LDV": 2, "Share of Technology - LPG ICE LDV": 100,
            "Final Energy Intensity - LPG ICE LDV": 0.6,
        }.items()}
        detailed = calc_for_scenario(metrics, "2030_BAU")
        self.assertAlmostEqual(detailed.loc[detailed.Fuel == "LPG", "Final Energy Demand (GWh)"].sum(), 300)
        row = generate_transport_indicators(detailed, "Morocco").iloc[0]
        self.assertAlmostEqual(row["total road"], 0.3)
        self.assertEqual(row["road oil"], 0)

    def test_navigation_methanol_retains_legacy_oil_category(self):
        row = generate_transport_indicators(
            detail_frame({"Methanol": 1000}, "Freight Ships", "Navigation"), "Morocco"
        ).iloc[0]
        self.assertAlmostEqual(row["total navigation oil"], 1)
        self.assertAlmostEqual(row["total domestic navigation"], 1)

    def test_unsd_aggregate_is_fresh_read_only_and_twh(self):
        with tempfile.TemporaryDirectory() as temp:
            raw = Path(temp) / "raw"
            raw.mkdir()
            pd.DataFrame({
                "Transactions(down)/Commodity(right)": ["International marine bunkers", "International aviation bunkers"],
                "Total Energy": ["-3600*", "-7200"],
            }).to_csv(raw / "Morocco-2020.csv", index=False)
            before = fingerprint(raw)
            result = refresh_unsd_master_data(raw, countries=["Morocco"])
            self.assertEqual(result.iloc[0]["Marine_Bunkers_TWh"], 1)
            self.assertEqual(result.iloc[0]["Aviation_Bunkers_TWh"], 2)
            self.assertEqual(before, fingerprint(raw))
            external = Path(temp) / "aggregate" / "bunkers.xlsx"
            refresh_unsd_master_data(raw, output_path=external, countries=["Morocco"])
            self.assertTrue(external.exists())
            with self.assertRaises(FileNotFoundError):
                refresh_unsd_master_data(raw, countries=["Missing country"])

    def test_missing_config_is_not_created(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "not-created" / "config.csv"
            with self.assertRaises(FileNotFoundError):
                load_transport_config(path, ["default"], SCENARIOS)
            self.assertFalse(path.parent.exists())

    def test_scenario_alias_keeps_canonical_identity_for_subset(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "config.csv"
            pd.DataFrame({"Assumption Type": ["CAGR"] * 3, "Metric Name": ["Population"] * 3,
                          "Year": [2035] * 3, "Scenario": ["sc_a", "sc_b", "sc_c"],
                          "default": [0.01, 0.02, 0.03]}).to_csv(path, index=False)
            cfg = load_transport_config(path, ["default"], ["Optimistic"])
            self.assertEqual(cfg["default"]["Population"]["values"][2035], {"Optimistic": 0.03})

    def test_all_transport_imports_have_no_filesystem_writes(self):
        # Audit the OS operations too: snapshot-only checks would miss attempts
        # to create an already-existing directory or to rewrite identical bytes.
        code = """
import importlib, os, sys
import pandas, numpy, pycountry, openpyxl, tabula
from pathlib import Path
def no_writes(event, args):
    if event == 'open':
        mode, flags = args[1], args[2]
        if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
        ):
            raise AssertionError('Import attempted file write: ' + str(args[0]))
    if event in {'os.mkdir', 'os.remove', 'os.rename', 'os.rmdir'}:
        raise AssertionError('Import attempted filesystem mutation: ' + str(args))
sys.addaudithook(no_writes)
for path in sorted(Path('transport').glob('*.py')):
    importlib.import_module('transport.' + path.stem)
print('All transport imports are write-free')
"""
        result = subprocess.run([sys.executable, "-B", "-c", code], cwd=ROOT,
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class SourceBackedTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(os.environ.get("TRANSPORT_TEST_SOURCE_ROOT", ROOT)).resolve()
        cls.raw = cls.source / "transport" / "input_data"
        required = [cls.raw / "global" / "Supplementary_Material_Khalili2019_Data_final.xlsx",
                    cls.raw / "global" / "OECD.Stat-EEI_TRANSPORT.csv",
                    cls.raw / "country_specific" / "chart-data_pop_Morocco.csv",
                    cls.raw / "unsd_country_specific" / "Morocco-2020.csv",
                    cls.source / "transport" / "trans_config.csv"]
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise unittest.SkipTest("Source-backed runtime blocked; missing raw inputs: " + "; ".join(missing))
        parent = os.environ.get("TRANSPORT_TEST_OUTPUT_DIR")
        if parent:
            Path(parent).mkdir(parents=True, exist_ok=True)
        cls.audit = Path(tempfile.mkdtemp(prefix="transport-tests-", dir=parent))
        if cls.audit.is_relative_to(ROOT) or cls.audit.is_relative_to(cls.source):
            raise ValueError("Transport test outputs must be outside both repositories")
        cls.before = fingerprint(cls.raw)
        cls.source_config_before = (cls.source / "transport" / "trans_config.csv").read_bytes()
        cls.config = cls.audit / "trans_config.csv"
        shutil.copyfile(cls.source / "transport" / "trans_config.csv", cls.config)
        cls.parameters = cls.audit / "parameters"
        cls.output = cls.audit / "transport"
        cls.cli("transport.build_transport_config", "config.log")
        cls.parameter_before = fingerprint(cls.parameters)
        cls.cli("transport.build_final_energy_demand", "demand.log")
        print(f"\nSource-backed transport artifacts: {cls.audit}")

    @classmethod
    def cli(cls, module, log, extra=()):
        command = [sys.executable, "-B", "-m", module,
                   "--config-path", str(cls.config), "--output-dir", str(cls.output),
                   "--parameter-dir", str(cls.parameters), "--input-dir", str(cls.raw),
                   "--countries", "Morocco", "--years", *map(str, YEARS),
                   "--scenarios", *SCENARIOS, *extra]
        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        (cls.audit / log).write_text(result.stdout + result.stderr, encoding="utf-8")
        if result.returncode:
            raise AssertionError(f"Source-backed transport command failed ({result.returncode}): "
                                 f"{result.stdout}\n{result.stderr}")

    def test_config_has_all_keys_and_positive_activity_from_fresh_raw(self):
        files = list(self.parameters.glob("output_*.csv"))
        self.assertEqual([path.name for path in files], ["output_Morocco.csv"])
        frame = pd.read_csv(files[0])
        self.assertFalse(frame.Metric.duplicated().any())
        self.assertTrue(KEYS.issubset(frame.columns))
        values = frame.set_index("Metric").loc[
            ["Population", "Mobility per capita - Passenger", "Mobility per capita - Freight"], sorted(KEYS)]
        self.assertTrue(np.isfinite(values.to_numpy()).all())
        self.assertTrue((values > 0).all().all())
        self.assertEqual(self.before, fingerprint(self.raw))
        self.assertEqual(self.source_config_before, (self.source / "transport" / "trans_config.csv").read_bytes())

    def test_aggregates_all_dimensions_conservation_and_twh(self):
        files = list(self.output.glob("transport_*.csv"))
        self.assertEqual(len(files), 16)
        combined = pd.concat([pd.read_csv(path, dtype={"scenario": str}) for path in files], ignore_index=True)
        self.assertEqual(set(combined.scenario), KEYS)
        self.assertEqual(set(combined.country), {"Morocco"})
        self.assertFalse(combined.duplicated(["country", "scenario"]).any())
        measures = combined.drop(columns=["country", "scenario"])
        self.assertTrue(np.isfinite(measures.to_numpy()).all())
        self.assertTrue((measures >= 0).all().all())
        self.assertTrue((combined["total road"] > 0).all())
        detailed = pd.read_csv(self.output / "unsdata_historical" / "Morocco" / "parameters_Morocco.csv")
        road = detailed.loc[detailed.Mode == "Road"].groupby("Scenario")["Final Energy Demand (GWh)"].sum() / 1000
        indicators = combined.set_index("scenario")
        np.testing.assert_allclose(indicators.loc[road.index, "total road"], road)
        partition = indicators[["road oil", "road gas", "road electricity", "road biomass", "total road fcev"]].sum(axis=1)
        np.testing.assert_allclose(indicators["total road"], partition)
        source_bunkers = refresh_unsd_master_data(self.raw / "unsd_country_specific", countries=["Morocco"])
        base = source_bunkers.loc[source_bunkers.Year == "2020"].iloc[0]
        self.assertAlmostEqual(indicators.at["2020", "total international aviation"], base.Aviation_Bunkers_TWh)
        self.assertAlmostEqual(indicators.at["2020", "total international navigation"], base.Marine_Bunkers_TWh)
        biomass = combined[["country", "scenario", "total navigation biomass", "total aviation biomass"]].sort_values("scenario")
        (self.audit / "schema-review-biomass-twh.json").write_text(
            biomass.to_json(orient="records", indent=2), encoding="utf-8")

    def test_demand_never_mutates_input_parameters(self):
        self.assertEqual(self.parameter_before, fingerprint(self.parameters))
        self.assertTrue((self.output / "unsdata_historical" / "Morocco" / "output_Morocco_updated.csv").exists())
        self.assertFalse(any(self.audit.rglob("__pycache__")))

    def test_subset_cli_honors_year_scenario_and_external_paths(self):
        subset = self.audit / "subset"
        self.cli("transport.build_transport_config", "subset-config.log",
                 ["--output-dir", str(subset), "--parameter-dir", str(subset / "parameters"),
                  "--years", "2035", "--scenarios", "Optimistic"])
        params = pd.read_csv(subset / "parameters" / "output_Morocco.csv")
        self.assertEqual(set(params.columns), {"Metric", "Units", "2020", "2035_Optimistic"})
        self.cli("transport.build_final_energy_demand", "subset-demand.log",
                 ["--output-dir", str(subset), "--parameter-dir", str(subset / "parameters"),
                  "--years", "2035", "--scenarios", "Optimistic"])
        self.assertEqual({path.name for path in subset.glob("transport_*.csv")},
                         {"transport_all_2020.csv", "transport_Optimistic_2035.csv"})


if __name__ == "__main__":
    unittest.main()