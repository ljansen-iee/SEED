"""Focused industry migration regressions; all generated files use external temp.

Fixtures below are deliberately small, synthetic unit-test inputs, not substitutes
for the separate raw-source-backed Morocco verification.
Run from the repository root with python -B -m unittest discover -s tests
-p test_industry_migration.py -v.
"""

import contextlib
import importlib
import inspect
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

import industry
from industry.scripts import calculate_final_energy_demand as demand
from industry.scripts import generate_industry_config as generator
from industry.utils import helpers


def make_config():
    """Hand-computable complete contract for all thirteen output sectors."""
    rows = []

    def add(sector, kind, metric, year, scenario, value, units, fuel=""):
        rows.append(dict(zip(helpers.CONFIG_COLUMNS + ["Morocco"],
                             [sector, kind, metric, fuel, year, scenario, units, value])))

    detailed = {
        "iron and steel": {
            "production": ["steel production per year"],
            "routes": {"primary steel production": .6, "secondary steel production": .4,
                       "bf+bof": .25, "dr+eaf": .75},
            "intensities": {"bf+bof": 2., "dr+eaf": 3., "scrap eaf": 1.,
                            "casting, rolling & finishing": .5},
        },
        "chemical and petrochemical": {
            "production": ["ammonia production per year", "ammonia import volumes per year",
                           "hvc production per year"],
            "routes": {"smr+hb": .5, "renewable synthesis": .5, "import reallocation": .2,
                       "naphtha cracking": .5, "lpg cracking": .3, "mto": .2},
            "intensities": {"smr+hb": 2., "renewable synthesis": 3.,
                            "naphtha cracking": 2., "lpg cracking": 2., "mto": 2.},
        },
        "non-metallic minerals": {
            "production": ["cement production per year"],
            "routes": {"clinker ratio": .7},
            "intensities": {"cement production": 2.},
        },
        "paper, pulp and printing": {
            "production": ["paper production per year", "pulp production per year"],
            "routes": {"primary pulp": .4, "secondary pulp": .6},
            "intensities": {"primary pulp": 2., "secondary pulp": 1., "paper production": 2.},
        },
        "non-ferrous metals": {
            "production": ["aluminium production per year"],
            "routes": {"primary aluminium": .4, "secondary aluminium": .6},
            "intensities": {"primary aluminium": 2., "secondary aluminium": 1.},
        },
    }
    for scenario in helpers.SCENARIOS:
        for sector, spec in detailed.items():
            for year in [2020] + helpers.DEFAULT_TARGET_YEARS:
                for name in spec["production"]:
                    add(sector, "production", name, year, scenario, 100., "t/a")
                for route, value in spec["routes"].items():
                    add(sector, "technology_route", route, year, scenario, value, "share")
                for route in spec["intensities"]:
                    add(sector, "fuel_share", route, year, scenario, 1., "share", "electricity")
            for route, value in spec["intensities"].items():
                add(sector, "intensity_base", route, 2020, scenario, value, "MWh/t")
                add(sector, "cagr", "energy intensity of " + route, "2020-2050",
                    scenario, 0., "share")
        for sector in helpers.SIMPLE_SECTORS:
            add(sector, "cagr", "activity growth rate", "2020-2050", scenario, .01, "share")
            for year in [2020] + helpers.DEFAULT_TARGET_YEARS:
                add(sector, "fuel_share", "unspecified " + sector, year, scenario,
                    1., "share", "electricity")
    for sector in helpers.SIMPLE_SECTORS:
        add(sector, "historical_energy_demand", "base year energy consumption",
            2020, "all", 100., "MWh")
    return pd.DataFrame(rows)


class IndustryMigrationTests(unittest.TestCase):
    def setUp(self):
        parent = os.environ.get("INDUSTRY_MIGRATION_TMP_PARENT")
        self.temp = tempfile.TemporaryDirectory(prefix="industry-test-", dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config_path = self.root / "CONFIG" / helpers.INDUSTRY_CONFIG_FILE
        self.config_path.parent.mkdir()
        self.frame = make_config()
        self.frame.to_csv(self.config_path, index=False)
        self.captured = io.StringIO()
        self.redirect = contextlib.redirect_stdout(self.captured)
        self.redirect.__enter__()
        self.addCleanup(self.redirect.__exit__, None, None, None)

    def calculator(self, **kwargs):
        return demand.FinalEnergyCalculator(self.config_path, **kwargs)

    def drop_key(self, sector, kind, metric, year, scenario):
        selected = (self.frame.metric_1.eq(sector) & self.frame.metric_2.eq(kind)
                    & self.frame.metric_3.eq(metric) & self.frame.year.astype(str).eq(str(year))
                    & self.frame.scenario.eq(scenario))
        self.assertEqual(int(selected.sum()), 1)
        self.frame.loc[~selected].to_csv(self.config_path, index=False)

    def patch_sector_builders(self):
        # Only unit-test orchestration is mocked; derivatives remain real.
        builders = {
            "generate_steel_config_rows": "iron and steel",
            "generate_ammonia_config_rows": "chemical and petrochemical",
            "generate_hvc_config_rows": None,
            "generate_cement_config_rows": "non-metallic minerals",
            "generate_paper_pulp_config_rows": "paper, pulp and printing",
            "generate_aluminium_config": "non-ferrous metals",
            "generate_food_tobacco_config_rows": "food and tobacco",
            "generate_construction_config_rows": "manufacturing  const. and mining",
            "generate_machinery_config_rows": "machinery",
            "generate_mining_quarrying_config_rows": "mining and quarrying",
            "generate_textile_leather_config_rows": "textile and leather",
            "generate_transport_equipment_config_rows": "transport equipment",
            "generate_wood_products_config_rows": "wood and wood products",
            "generate_other_industries_config_rows": "other",
        }
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(generator, "validate_sector_source_files"))
        for name, sector in builders.items():
            stack.enter_context(patch.object(generator, name,
                                             return_value=self.frame[self.frame.metric_1.eq(sector)].copy()))

    def test_defaults_use_canonical_config_and_standard_dimensions(self):
        expected = helpers.INDUSTRY_DIR / "output_data" / "CONFIG" / "INDUSTRY_CONFIG.csv"
        self.assertEqual(helpers.INDUSTRY_CONFIG_PATH, expected)
        self.assertEqual(inspect.signature(demand.FinalEnergyCalculator).parameters["config_path"].default,
                         expected)
        with patch.object(generator, "generate_industry_config_csv") as generate:
            with patch("sys.argv", ["generate_industry_config"]):
                generator.main()
            self.assertEqual(generate.call_args.kwargs["output_path"], expected)
            self.assertEqual(generate.call_args.kwargs["target_years"], helpers.DEFAULT_TARGET_YEARS)
            self.assertEqual(generate.call_args.kwargs["scenarios"], helpers.SCENARIOS)
        with patch.object(demand, "FinalEnergyCalculator") as factory:
            factory.return_value.calculate_all_detailed_sectors.return_value = pd.DataFrame()
            with patch.object(Path, "exists", return_value=True), patch("sys.argv", ["calculate_final_energy_demand"]):
                with self.assertRaisesRegex(ValueError, "No industry demand"):
                    demand.main()
            self.assertEqual(factory.call_args.args[0], expected)

    def test_get_scenarios_is_exported_and_has_no_legacy_alias(self):
        self.assertIs(industry.get_scenarios, helpers.get_scenarios)
        copy = industry.get_scenarios()
        copy.clear()
        self.assertEqual(industry.get_scenarios(), helpers.SCENARIOS)
        for module in [industry, helpers]:
            self.assertFalse(hasattr(module, "get_scenarios_from_build_config_industry"))
            self.assertFalse(hasattr(module, "get_scenarios_from_main_industry"))
        for path in helpers.INDUSTRY_DIR.rglob("*.py"):
            self.assertNotIn("get_scenarios_from_build_config_industry", path.read_text(encoding="utf-8"), str(path))
        # Import every industry source module, including callers not imported by the orchestrator.
        for path in helpers.INDUSTRY_DIR.rglob("*.py"):
            parts = path.relative_to(helpers.INDUSTRY_DIR.parent).with_suffix("").parts
            name = ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
            importlib.import_module(name)

    def test_all_thirteen_sectors_all_years_and_scenarios(self):
        calc = self.calculator(refresh_interim=False)
        result = calc.calculate_all_detailed_sectors()
        self.assertEqual(set(result.sector), set(demand.SECTOR_NAME_MAPPING.values()))
        self.assertEqual(set(result.year), set(helpers.DEFAULT_TARGET_YEARS))
        self.assertEqual(set(result.scenario), set(helpers.SCENARIOS))
        self.assertFalse(result.duplicated(["country", "scenario", "year", "carrier", "sector"]).any())
        self.assertTrue(np.isfinite(result.energy_MWh).all())
        self.assertTrue(result.energy_MWh.ge(0).all())
        for sector, subset in result.groupby("sector"):
            self.assertEqual(len(subset.groupby(["year", "scenario"])), 15, sector)
        wide = calc.pivot_to_wide_format(result)
        self.assertEqual(len(wide.columns), 4 + 13)

    def test_no_refresh_never_reads_or_rewrites_stale_cache(self):
        interim = self.root / "interim_data"
        interim.mkdir()
        for stem in ["steel_intensity_projections", "ammonia_intensity_projections", "steel_volumes", "ammonia_volumes"]:
            (interim / (stem + ".csv")).write_text("NOT A VALID CACHE", encoding="utf-8")
        calc = self.calculator(refresh_interim=False)
        self.assertEqual(calc.get_intensity("iron and steel", "dr+eaf", "Morocco", "BAU", 2050), 3.)
        selected = self.frame.metric_1.eq("iron and steel") & self.frame.metric_2.eq("intensity_base") & self.frame.metric_3.eq("dr+eaf")
        self.frame.loc[selected, "Morocco"] = 9.
        self.frame.to_csv(self.config_path, index=False)
        changed = self.calculator(refresh_interim=False)
        self.assertEqual(changed.get_intensity("iron and steel", "dr+eaf", "Morocco", "BAU", 2050), 9.)
        for path in interim.iterdir():
            self.assertEqual(path.read_text(encoding="utf-8"), "NOT A VALID CACHE")
        self.assertEqual(len(list(interim.iterdir())), 4)

    def test_refresh_derivatives_follow_external_config_tree(self):
        calc = self.calculator()
        self.assertEqual(calc.interim_dir, self.root / "interim_data")
        required = {"steel_intensity_projections.csv", "ammonia_intensity_projections.csv",
                    "steel_volumes.csv", "ammonia_volumes.csv", "production_cagr.csv",
                    "intensity_cagr.csv", "intensity_cagr_summary.csv", "process_emissions.csv",
                    "process_emissions_summary.csv"}
        self.assertTrue(required.issubset({p.name for p in calc.interim_dir.iterdir()}))
        self.assertTrue(all(p.resolve().is_relative_to(self.root) for p in calc.interim_dir.iterdir()))

    def test_generator_derivatives_follow_external_config_tree(self):
        self.patch_sector_builders()
        generator.generate_industry_config_csv(["Morocco"], output_path=self.config_path)
        files = {p.name for p in (self.root / "interim_data").iterdir()}
        self.assertTrue({"steel_volumes.csv", "ammonia_volumes.csv", "process_emissions.csv"}.issubset(files))
        self.assertEqual(helpers.industry_output_root(self.root / "custom.csv"), self.root)

    def test_generator_does_not_swallow_derivative_failures(self):
        self.patch_sector_builders()
        with patch.object(generator, "build_steel_intensity_projections", side_effect=ValueError("derivative failure")):
            with self.assertRaisesRegex(ValueError, "derivative failure"):
                generator.generate_industry_config_csv(["Morocco"], output_path=self.config_path)

    def test_config_only_omits_derivatives_explicitly(self):
        self.patch_sector_builders()
        generator.generate_industry_config_csv(["Morocco"], output_path=self.config_path,
                                               generate_derivatives=False)
        self.assertFalse((self.root / "interim_data").exists())

    def test_validation_rejects_missing_columns_duplicate_keys_and_percent_shares(self):
        with self.assertRaisesRegex(ValueError, "missing required columns"):
            helpers.validate_industry_config(self.frame.drop(columns="scenario"))
        with self.assertRaisesRegex(ValueError, "Duplicate industry dimension keys"):
            helpers.validate_industry_config(pd.concat([self.frame, self.frame.iloc[:1]]))
        frame = self.frame.copy()
        frame.loc[frame.metric_2.eq("fuel_share"), "Morocco"] = 100.
        with self.assertRaisesRegex(ValueError, "fractions"):
            helpers.validate_industry_config(frame)

    def test_validation_rejects_missing_required_production_key(self):
        self.drop_key("iron and steel", "production", "steel production per year", 2040, "Optimistic")
        with self.assertRaisesRegex(ValueError, "steel production per year / 2040 / Optimistic"):
            self.calculator(refresh_interim=False)

    def test_validation_rejects_missing_required_fuel_key(self):
        self.drop_key("non-ferrous metals", "fuel_share", "primary aluminium", 2035, "Progressive")
        with self.assertRaisesRegex(ValueError, "primary aluminium / 2035 / Progressive"):
            self.calculator(refresh_interim=False)

    def test_validation_rejects_missing_scenario_base_intensity(self):
        self.drop_key("paper, pulp and printing", "intensity_base", "paper production", 2020, "Optimistic")
        with self.assertRaisesRegex(ValueError, "paper production / 2020 / Optimistic"):
            self.calculator(refresh_interim=False)

    def test_mwh_energy_and_tonnes_steel_are_not_interchangeable(self):
        calc = self.calculator(refresh_interim=False)
        result = calc.calculate_steel_energy([2030], ["BAU"]).set_index("carrier").energy_MWh
        # 100 t: 15 BF, 45 DR, 40 scrap; casting applies to all 100 t.
        self.assertAlmostEqual(result["electricity"], 15 * 2 + 45 * 3 + 40 * 1 + 100 * .5)
        self.assertAlmostEqual(result["steel"], 45 + 40)  # tonnes, despite legacy measure name
        self.assertNotAlmostEqual(result["steel"], result["electricity"])

    def test_mwh_per_100t_intensity_is_converted_before_energy(self):
        selected = self.frame.metric_1.eq("non-ferrous metals") & self.frame.metric_2.eq("intensity_base") & self.frame.metric_3.eq("primary aluminium")
        self.frame.loc[selected, "Morocco"] = 200.
        self.frame.loc[selected, "units"] = "MWh/100t"
        self.frame.to_csv(self.config_path, index=False)
        calc = self.calculator(refresh_interim=False)
        self.assertEqual(calc.get_intensity("non-ferrous metals", "primary aluminium", "Morocco", "BAU", 2030), 2.)

    def test_zero_unspecified_activity_does_not_add_one_mwh(self):
        calc = self.calculator(refresh_interim=False)
        frame = pd.DataFrame([{"metric_2": "fuel_share", "metric_3": "unspecified iron and steel",
                               "metric_4": "electricity", "scenario": "BAU", "year": "2030",
                               "units": "share", "Morocco": 1.}])
        carriers = dict.fromkeys(demand.CARRIER_ORDER, 0.)
        self.assertEqual(calc._add_unspecified_energy(frame, "iron and steel", "Morocco", "BAU", "2030", carriers), carriers)
        self.assertEqual(sum(carriers.values()), 0.)


if __name__ == "__main__":
    unittest.main()