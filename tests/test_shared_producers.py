"""Focused unittest checks; all generated fixtures/outputs live outside the repo.

Run from the isolated root: python -B -m unittest discover -s tests
-p test_shared_producers.py -v. Synthetic unit fixtures are not model inputs.
"""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build_shares as shares
import build_CAGR as cagr

spec = importlib.util.spec_from_file_location("additional_producer", ROOT / "additional sectors/build_add_sectors_demand.py")
additional = importlib.util.module_from_spec(spec)
spec.loader.exec_module(additional)


class SharedProducerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.source = self.base / "source"
        self.source.mkdir()

    def write_source(self, year, total, oil, electricity):
        rows = [{"Transactions(down)/Commodity(right)": sector, "Total Energy": total,
                 "Oil Products": oil, "Electricity": electricity}
                for sector in shares.DEFAULT_SECTOR_LABELS]
        pd.DataFrame(rows).to_csv(self.source / f"UNSD_Test Country-{year}.csv", index=False)

    def test_main_cleaning_and_share_formulas(self):
        for value in [None, "---", "", "None", "-"]:
            self.assertEqual(shares._clean_val(value), 0)
        self.assertEqual(shares._clean_val("12*"), 12)
        self.assertEqual(shares._clean_val("-12"), 12)  # main convention
        self.assertEqual(shares._normalize_shares({"oil": 0, "gas": 0}), shares._default_share_dict())
        self.write_source(2011, 100, 20, 80)
        self.write_source(2015, 300, 180, 120)
        result = shares.get_sector_shares_historical_average(self.source, "Test Country", "Households")
        self.assertEqual(result["oil"], 0.5)  # weighted totals, NOT mean of year shares
        self.assertEqual(result["electricity"], 0.5)
        self.assertTrue(shares._validate_share_sum(result)[1])
        path = shares.export_sector_shares_all_countries(self.source, self.base / "shares",
            "Households", countries=["Test Country"], years=[2011])
        frame = pd.read_csv(path)
        self.assertEqual(set(frame.share_mode), {"historical_average", "base_period_2011_2016"})
        self.assertTrue((frame.oil == 0.2).all())
        self.assertEqual(path.name, "households_shares_all_countries.csv")

    def test_main_cagr_exponent_zero_and_duplicate_keys(self):
        frame = pd.DataFrame({"country": ["A"] * 3, "sector": ["S"] * 3,
            "year": [2011, 2015, 2019], "unit": ["TWh"] * 3,
            "total_energy_twh": [10, 10 * 1.1 ** 5, 0]})
        result = cagr.add_rolling_cagr(frame)
        self.assertAlmostEqual(result.loc[1, "CAGR"], 0.1)
        self.assertTrue(pd.isna(result.loc[0, "CAGR"]))
        self.assertTrue(pd.isna(result.loc[2, "CAGR"]))
        self.assertTrue((result.suggested_cagr == 0.1).all())
        with self.assertRaisesRegex(ValueError, "unique"):
            cagr.add_rolling_cagr(pd.concat([frame, frame.iloc[:1]]))
        one = cagr.add_rolling_cagr(frame.iloc[:1])
        self.assertTrue(one.suggested_cagr.isna().all())

    def test_missing_country_or_year_never_falls_back(self):
        for producer in (
            lambda: shares.export_shares_for_multiple_sectors(self.source, self.base / "out", shares.DEFAULT_SECTOR_LABELS, countries=["Morocco"]),
            lambda: cagr.export_all_sectors_cagr_csv(self.source, self.base / "out", countries=["Morocco"]),
            lambda: additional.build_fuel_demand_for_multiple_sectors(self.source, self.base / "out", 2023, countries=["Morocco"]),
        ):
            with self.assertRaisesRegex(FileNotFoundError, "Morocco"):
                producer()
            self.assertFalse((self.base / "out").exists())
        self.write_source(2023, 100, 50, 50)
        with self.assertRaisesRegex(FileNotFoundError, "2020"):
            shares.export_sector_shares_all_countries(self.source, self.base / "out", "Households", years=[2020])

    def test_schema_validation_before_calculation(self):
        pd.DataFrame({"wrong": [1]}).to_csv(self.source / "UNSD_A-2020.csv", index=False)
        with self.assertRaisesRegex(ValueError, "Total Energy"):
            cagr.build_country_sector_year_aggregation(self.source)
        bad_shares = pd.DataFrame([{"country": "A", "share_mode": "historical_average",
                                   **shares._default_share_dict()}])
        bad_shares.loc[0, "oil"] = -0.2
        path = self.base / "bad.csv"
        bad_shares.to_csv(path, index=False)
        with self.assertRaisesRegex(ValueError, "fractions"):
            additional._load_average_shares_from_csv(path, "historical_average")
        pd.concat([bad_shares, bad_shares]).to_csv(path, index=False)
        with self.assertRaisesRegex(ValueError, "unique"):
            additional._load_average_shares_from_csv(path, "historical_average")

    def test_additional_projection_all_standard_years(self):
        for year in range(2011, 2024):
            self.write_source(year, 3600 * 1.02 ** (year - 2011), 1800 * 1.02 ** (year - 2011), 1800 * 1.02 ** (year - 2011))
        share_dir, cagr_dir, out = self.base / "data/shares", self.base / "data/cagr", self.base / "additional"
        shares.export_shares_for_multiple_sectors(self.source, share_dir, shares.DEFAULT_SECTOR_LABELS)
        cagr.export_all_sectors_cagr_csv(self.source, cagr_dir)
        years = [2023, *additional.TARGET_YEARS]
        paths = additional.build_fuel_demand_for_multiple_sectors(self.source, out, 2023,
            future_years=[*additional.TARGET_YEARS, 2050], countries=["Test Country"],
            years=years, shares_dir=share_dir, cagr_dir=cagr_dir)
        self.assertEqual(len(paths), 4)
        for path, sector in zip(paths, additional.SECTORS_TO_BUILD):
            frame = pd.read_csv(path)
            self.assertEqual(frame.year.tolist(), years)
            self.assertFalse(frame.duplicated(["country", "year"]).any())
            self.assertEqual(set(frame.unit), {"TWh"})
            self.assertTrue(np.isfinite(frame.iloc[:, 3:]).all().all())
            self.assertTrue((frame.iloc[:, 3:] >= 0).all().all())
            base = additional.get_sector_total_TWh(self.source, "Test Country", 2023, sector)
            prefix = additional._sector_output_file_prefix(sector)
            rate = pd.read_csv(cagr_dir / f"{prefix}_cagr_all_countries.csv").suggested_cagr.iloc[0]
            expected = round(base * (1 + rate) ** 7, 6)
            self.assertAlmostEqual(frame.loc[frame.year == 2030].iloc[:, 3:].sum(axis=1).iloc[0], expected, places=5)

    def test_cli_morocco_source_backed_and_all_outputs_external(self):
        source = ROOT / "data/country_specific"
        if not (source / "UNSD_Morocco-2023.csv").is_file():
            self.skipTest("Morocco UNSD raw source unavailable")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        share_dir, cagr_dir, out = self.base / "data/shares", self.base / "data/cagr", self.base / "additional"
        commands = [
            ["build_shares.py", "--output-dir", str(share_dir)],
            ["build_CAGR.py", "--output-dir", str(cagr_dir)],
            ["additional sectors/build_add_sectors_demand.py", "--shares-dir", str(share_dir),
             "--cagr-dir", str(cagr_dir), "--output-dir", str(out), "--years", "2020", "2030", "2035", "2040", "2045", "2050"],
        ]
        for command in commands:
            result = subprocess.run([sys.executable, "-B", *command, "--input-dir", str(source), "--countries", "Morocco"],
                                    cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(list(share_dir.glob("*.csv"))), 5)
        self.assertEqual(len(list(cagr_dir.glob("*.csv"))), len(cagr.TARGET_SECTORS) + 1)
        for path in out.glob("*.csv"):
            frame = pd.read_csv(path)
            self.assertEqual(set(frame.country), {"Morocco"})
            self.assertEqual(frame.year.tolist(), [2020, *additional.TARGET_YEARS])
            self.assertEqual(set(frame.unit), {"TWh"})
            self.assertFalse(frame.duplicated(["country", "year"]).any())
            self.assertTrue((frame.iloc[:, 3:] >= 0).all().all())

    def test_imports_perform_no_reads_writes_or_prints(self):
        code = f"""
import sys, importlib.util, pathlib, os, builtins
import pandas as pd
sys.dont_write_bytecode = True
sys.path.insert(0, {str(ROOT / 'residential')!r})
# Load heavy dependencies before trapping model I/O.
import sklearn.metrics
def forbidden(*args, **kwargs):
    raise AssertionError('Import performed model I/O')
pd.read_csv = pd.read_excel = pd.DataFrame.to_csv = forbidden
pathlib.Path.mkdir = os.mkdir = forbidden
old_open = builtins.open
def guarded_open(path, mode='r', *args, **kwargs):
    if any(flag in mode for flag in 'wax+'):
        forbidden()
    return old_open(path, mode, *args, **kwargs)
builtins.open = guarded_open
for number, relative in enumerate({['build_shares.py', 'build_CAGR.py', 'additional sectors/build_add_sectors_demand.py', 'residential/helpers.py', 'residential/build_residential_config.py', 'residential/build_final_energy_demand.py']!r}):
    spec = importlib.util.spec_from_file_location('import_check_' + str(number), pathlib.Path({str(ROOT)!r}) / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
"""
        result = subprocess.run([sys.executable, "-B", "-c", code], cwd=self.base,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(ROOT)),
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_residential_paths_missing_inputs_and_demand_output(self):
        # Use a separate process to retain intentional sibling imports and avoid
        # collisions between root and residential build_CAGR modules.
        code = f"""
import sys, pathlib, pandas as pd
sys.path.insert(0, {str(ROOT / 'residential')!r})
import helpers, build_CAGR, build_technology_shares
import build_final_energy_demand as demand
base = pathlib.Path({str(self.base)!r})
try:
    helpers.validate_residential_sources(base / 'missing', ['Morocco'])
except FileNotFoundError as exc:
    assert 'chart-data_pop_Morocco.csv' in str(exc)
    assert '98667-WP-P146621-PUBLIC-Box393179B.pdf' in str(exc)
else:
    raise AssertionError('Absent raw source was accepted')
old = build_CAGR.build_Africa_regions
with helpers.residential_source_paths(base / 'missing'):
    try:
        build_CAGR.build_Africa_regions()
    except FileNotFoundError:
        pass
assert build_CAGR.build_Africa_regions is old
years = helpers.DEFAULT_TARGET_YEARS
values = {{'Population':1000, 'Residential Area per Person':10, 'Persons per Dwelling':2,
    'Saturation of Space Heating':1, 'Saturation of Space Cooling':1,
    'Saturation of Water Heating':1, 'Saturation of Cooking':1, 'Saturation of Appliances':1}}
rows = []
for scenario in ['BAU', 'Progressive', 'Optimistic']:
    for year in years:
        for metric, value in values.items():
            rows.append({{'type':'macro_ind', 'metric name':metric, 'year':year, 'scenario':scenario, 'units':'fixture', 'Morocco':value}})
        for end, tech, intensity in [('Space Heating','Electric Heaters',10), ('Space Cooling','Air Conditioning',20), ('Water Heating','Electric Heaters',30), ('Cooking','Electric Stoves',40), ('Electrical Appliances',None,50)]:
            if tech:
                rows.append({{'type':'technology share', 'metric name':f'Share of {{tech}} for {{end}}', 'year':year, 'scenario':scenario, 'units':'fraction', 'Morocco':1}})
            name = f'Final Energy Intensity of {{tech}} for {{end}}' if tech else f'Final Energy Intensity of {{end}}'
            rows.append({{'type':'energy intensity', 'metric name':name, 'year':year, 'scenario':scenario, 'units':'fixture', 'Morocco':intensity}})
            rows.append({{'type':'CAGR', 'metric name':f'Final Energy Intensity of {{end}}', 'year':year, 'scenario':scenario, 'units':'%', 'Morocco':0}})
config = base / 'config'
config.mkdir()
pd.DataFrame(rows).to_csv(config / demand.RESIDENTIAL_CONFIG_FILE, index=False)
result = demand.main(['--input-dir',str(config),'--output-dir',str(base/'demand'),'--countries','Morocco','--years',*map(str, years)])
assert sorted(result.year.unique()) == years
assert set(result.scenario) == {{'BAU','Progressive','Optimistic'}}
assert (result.final_energy_demand_twh >= 0).all()
app = result[result.end_use == 'Electrical Appliances']
assert (abs(app.final_energy_demand_twh - 0.000025) < 1e-12).all()
assert len(list((base/'demand').glob('*.csv'))) == 20
summary = pd.read_csv(base/'demand/residential_all_scenarios_years_countries.csv')
assert len(summary) == 18 and not summary.duplicated(['country','scenario','year']).any()
assert set(summary.country) == {{'MA'}}
"""
        result = subprocess.run([sys.executable, "-B", "-c", code], cwd=self.base,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()