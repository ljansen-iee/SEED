"""Focused unittest suite; all writes use TemporaryDirectory, never sector outputs.

Optional read-only checks: PYPSA_REFERENCE_DIR, PYPSA_TRANSPORT_DIR,
PYPSA_RESIDENTIAL_DIR, PYPSA_ADDITIONAL_DIR and PYPSA_INDUSTRY_DIR.
The original local examples must never be copied into this worktree.
"""

import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

import build_pypsa_energy_demands as exporter


SCOPE = {"countries": ["Morocco"], "years": [2050], "scenarios": ["BAU"]}
# Independent example contract: do not derive the expected schema from exporter constants.
EXAMPLE_SECTORS = (
    "chemical and petrochemical", "construction", "food and tobacco", "iron and steel",
    "machinery", "mining and quarrying", "non-ferrous metals", "non-metallic minerals",
    "other", "paper pulp and print", "textile and leather", "transport equipment", "wood and wood products",
)
EXAMPLE_QUANTITIES = (
    "oil", "gas", "electricity", "coal", "biomass", "hydrogen", "ammonia", "steel", "methanol",
    "process emissions", "low-temperature heat",
)
EMITTING_SECTORS = ("iron and steel", "chemical and petrochemical", "non-metallic minerals",
                    "non-ferrous metals", "paper pulp and print")


def energy_fixture():
    res = pd.DataFrame([{"country": "Morocco", "scenario": "BAU", "year": 2050,
                         **{col: 1.0 for col in exporter.RESIDENTIAL_MAPPING},
                         "electricity residential": 3.0, "total residential space": 2.0,
                         "total residential water": 2.0,
                         "residential hydrogen": 1.0, "exog. renewable heat": 0.0}])
    additional = pd.DataFrame([{"country": "MA", "year": 2050, "unit": "TWh",
                               **{f"{prefix} {fuel}": 2.0 if fuel == "electricity" else 0.0
                                  for prefix in exporter.ADDITIONAL_FILES
                                  for fuel in ("oil", "gas", "electricity", "coal", "biomass", "ammonia")}}])
    transport = pd.DataFrame([{"country": "MA", "scenario": "BAU", "year": 2050,
                              **{col: 0.0 for col in exporter.TRANSPORT_REQUIRED}}])
    transport.loc[0, ["road electricity", "total road ev", "total road"]] = 1000.0
    transport.loc[0, ["electricity rail", "total rail"]] = 500.0
    transport.attrs["unit"] = "GWh"
    return res, additional, transport


def industry_fixture():
    rows = []
    for carrier in ("oil", "gas", "electricity", "coal", "biomass", "hydrogen", "ammonia", "steel", "methanol", "heat"):
        row = {"country": "Morocco", "scenario": "BAU", "year": 2050, "carrier": carrier,
               **{sector: 0.0 for sector in EXAMPLE_SECTORS}}
        row["iron and steel"] = 17.0 if carrier == "steel" else 2.0
        if carrier != "steel":
            row["construction"] = 3.0
        rows.append(row)
    industry = pd.DataFrame(rows)
    industry.attrs["units"] = {carrier: "tSteel/a" if carrier == "steel" else "MWh/a"
                               for carrier in industry["carrier"]}
    emissions = pd.DataFrame([{"country": "MA", "scenario": "BAU", "year": 2050,
                               "sector": sector, "emissions_MtCO2": 0.25}
                              for sector in EMITTING_SECTORS])
    return industry, emissions


class EnergyExportTests(unittest.TestCase):
    def test_csv_reader_preserves_namibia_and_missing_measures(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "countries.csv"
            path.write_text("country,value\nNA,1\nMA,\n,2\n", encoding="utf-8")
            frame = exporter._read_csv(path)
            self.assertEqual(frame.loc[0, "country"], "NA")
            self.assertEqual(exporter.get_iso_code(frame.loc[0, "country"]), "NA")
            self.assertTrue(pd.isna(frame.loc[1, "value"]))
            self.assertTrue(pd.isna(frame.loc[2, "country"]))

    def test_three_sectors_gwh_conversion_and_sidecar(self):
        res, add, transport = energy_fixture()
        tables = exporter.build_energy_totals(res, add, transport, **SCOPE)
        table = tables[("BAU", 2050)]
        self.assertEqual(list(table.columns), list(exporter.ENERGY_COLUMNS))
        self.assertEqual(list(table.index), ["MA"])
        self.assertEqual(table.index.name, "country")
        self.assertEqual(len(table.columns), 59)
        self.assertEqual(table.loc["MA", "total road"], 1.0)
        self.assertEqual(table.loc["MA", "electricity rail"], 0.5)
        self.assertEqual(table.loc["MA", "electricity residential"], 3.0)
        self.assertEqual(table.loc["MA", "services electricity"], 2.0)
        self.assertEqual(table.loc["MA", "residential heat gas"], 1.0)
        self.assertEqual(table.loc["MA", "residential heat gas no cooking"], 1.0)
        with tempfile.TemporaryDirectory() as temporary:
            paths = exporter.write_export_tables(tables, Path(temporary), "energy")
            self.assertEqual(paths[0].name, "energy_totals_BAU_2050.csv")
            self.assertTrue(paths[0].read_text().startswith("country,agriculture biomass,"))
            saved = pd.read_csv(paths[0], index_col=0)
            pd.testing.assert_frame_equal(saved, table, check_dtype=False)
            metadata = json.loads(paths[0].with_suffix(".units.json").read_text())
            self.assertEqual(metadata["scenario"], "BAU")
            self.assertEqual(metadata["country_index"]["name"], "country")
            self.assertEqual(metadata["columns"]["total road"]["unit"], "TWh/a")
            self.assertEqual(metadata["columns"]["district heat share"]["unit"], "fraction")
            self.assertEqual(metadata["lineage"]["total road"]["scale"], 0.001)

    def test_all_scenarios_years_replicate_additional_once(self):
        res, add, transport = energy_fixture()
        res = pd.concat([res.assign(scenario=s, year=y) for s in exporter.SCENARIOS
                         for y in exporter.TARGET_YEARS], ignore_index=True)
        add = pd.concat([add.assign(year=y) for y in exporter.TARGET_YEARS], ignore_index=True)
        transport = pd.concat([transport.assign(scenario=s, year=y) for s in exporter.SCENARIOS
                               for y in exporter.TARGET_YEARS], ignore_index=True)
        tables = exporter.build_energy_totals(res, add, transport, countries=["MA"], transport_unit="GWh")
        self.assertEqual(len(tables), 15)
        self.assertEqual(sum(t.loc["MA", "services electricity"] for t in tables.values()), 30.0)

    def test_coverage_is_not_inferred_from_available_rows(self):
        frames = energy_fixture()
        with self.assertRaisesRegex(ValueError, "coverage"):
            exporter.build_energy_totals(*frames, countries=["MA", "CL"], years=[2050], scenarios=["BAU"])
        with self.assertRaisesRegex(ValueError, "coverage"):
            exporter.build_energy_totals(*frames, countries=["MA"], years=[2050], scenarios=["BAU", "Optimistic"])
        with self.assertRaisesRegex(ValueError, "coverage"):
            exporter.build_energy_totals(*frames, countries=["MA"], years=[2045, 2050], scenarios=["BAU"])

    def test_duplicate_normalised_country_keys_rejected(self):
        res, add, transport = energy_fixture()
        duplicate = pd.concat([res, res.assign(country="MA")], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "duplicate keys"):
            exporter.build_energy_totals(duplicate, add, transport, **SCOPE)
        with self.assertRaisesRegex(ValueError, "duplicate keys"):
            exporter.build_energy_totals(res, pd.concat([add, add]), transport, **SCOPE)

    def test_invalid_identifiers_units_and_values(self):
        for value in (None, "Atlantis", "XX", ""):
            with self.subTest(country=value), self.assertRaises(ValueError):
                exporter.get_iso_code(value)
        for value in (2050.5, np.inf, np.nan):
            res, add, transport = energy_fixture()
            res["year"] = value
            with self.subTest(year=value), self.assertRaises(ValueError):
                exporter.build_energy_totals(res, add, transport, **SCOPE)
        for value in (-1, np.inf, np.nan):
            res, add, transport = energy_fixture()
            res["electricity residential"] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "finite and nonnegative"):
                exporter.build_energy_totals(res, add, transport, **SCOPE)
        res, add, transport = energy_fixture()
        transport.attrs.clear()
        with self.assertRaisesRegex(ValueError, "declare GWh or TWh"):
            exporter.build_energy_totals(res, add, transport, **SCOPE)
        add["unit"] = "GWh"
        with self.assertRaisesRegex(ValueError, "unit must be TWh"):
            exporter.build_energy_totals(res, add, transport, transport_unit="GWh", **SCOPE)

    def test_unsupported_nonzero_data_and_share_consistency(self):
        for source, column in ((0, "exog. renewable heat"), (1, "agriculture gas"),
                               (1, "services coal"), (1, "services ammonia"), (2, "total navigation electricity")):
            frames = list(energy_fixture())
            frames[source][column] = 1.0
            with self.subTest(column=column), self.assertRaisesRegex(ValueError, "nonzero unmapped"):
                exporter.build_energy_totals(*frames, **SCOPE)
        res, add, transport = energy_fixture()
        transport["total road fcev"] = 1.0
        with self.assertRaisesRegex(ValueError, "EV.*FCEV"):
            exporter.build_energy_totals(res, add, transport, **SCOPE)
        res["district heat share"] = 1.1
        with self.assertRaisesRegex(ValueError, "fraction"):
            exporter.build_energy_totals(res, add, transport, **SCOPE)

    def test_real_transport_method_biomass_is_subsumed_not_added_or_oil(self):
        from transport.build_final_energy_demand import generate_transport_indicators

        # Hand-computable raw vehicle rows, explicitly synthetic, using the real
        # indicator method. Diesel/kerosene blends shift fuel, not total energy.
        raw = pd.DataFrame([
            {"Scenario": "2050_BAU", "Subsector": "Freight", "Mode": "Marine", "End-Use": "Freight Ships",
             "Fuel": fuel, "Final Energy Demand (GWh)": amount}
            for fuel, amount in (("Diesel", 1000.0), ("Hydrogen", 200.0), ("Ammonia", 300.0))
        ] + [
            {"Scenario": "2050_BAU", "Subsector": "Passenger", "Mode": "Aviation", "End-Use": "Passenger Planes",
             "Fuel": fuel, "Final Energy Demand (GWh)": amount}
            for fuel, amount in (("Kerosene", 2000.0), ("Bio Kerosene", 100.0))
        ])
        indicators = generate_transport_indicators(raw, "Morocco", {
            "Share of Biodiesel in Internal Navigation Diesel": {"2050_BAU": .2},
            "Share of Biokerosene in Internal Aviation Fuel": {"2050_BAU": .25},
        })
        indicators["scenario"], indicators["year"] = "BAU", 2050
        indicators[["total international aviation", "total international navigation"]] = 0.0
        res, add, _ = energy_fixture()
        for unit, factor in (("TWh", 1.0), ("GWh", 1000.0)):
            transport = indicators.copy()
            for col in transport.columns.difference(exporter.KEYS):
                transport[col] *= factor
            table = exporter.build_energy_totals(res, add, transport, transport_unit=unit, **SCOPE)[("BAU", 2050)]
            self.assertEqual(list(table.columns), list(exporter.ENERGY_COLUMNS))
            self.assertAlmostEqual(table.loc["MA", "total domestic navigation"], 1.5)
            self.assertAlmostEqual(table.loc["MA", "total navigation oil"], .8)
            self.assertAlmostEqual(table.loc["MA", "total domestic aviation"], 2.1)
            metadata = table.attrs["metadata"]
            diagnostics = metadata["diagnostic_submeasures"]["transport"]
            self.assertAlmostEqual(diagnostics["total navigation biomass"]["values"][0]["value"], .2)
            self.assertAlmostEqual(diagnostics["total aviation biomass"]["values"][0]["value"], .6)
            self.assertEqual(diagnostics["total navigation biomass"]["included_in"], "total domestic navigation")
            self.assertNotIn("total navigation biomass", metadata["omitted_zero_columns"]["transport"])
            with tempfile.TemporaryDirectory() as temporary:
                path = exporter.write_export_tables({("BAU", 2050): table}, Path(temporary), "energy")[0]
                saved = json.loads(path.with_suffix(".units.json").read_text())
                self.assertEqual(saved["diagnostic_submeasures"], metadata["diagnostic_submeasures"])

    def test_navigation_identity_blocks_unrepresented_electricity_or_unknown_energy(self):
        for residual in (1.0, -1.0):
            res, add, transport = energy_fixture()
            transport["total navigation oil"] = 1000.0
            transport["total domestic navigation"] = 1000.0 + residual
            with self.subTest(residual=residual), self.assertRaisesRegex(ValueError, "BLOCKER.*navigation.*electricity/unknown"):
                exporter.build_energy_totals(res, add, transport, **SCOPE)
        for diagnostic, total in exporter.TRANSPORT_DIAGNOSTICS.items():
            res, add, transport = energy_fixture()
            transport[diagnostic] = 1.0
            with self.subTest(diagnostic=diagnostic), self.assertRaisesRegex(ValueError, "exceeds"):
                exporter.build_energy_totals(res, add, transport, **SCOPE)
            transport[diagnostic] = -1.0
            with self.assertRaisesRegex(ValueError, "finite and nonnegative"):
                exporter.build_energy_totals(res, add, transport, **SCOPE)

    def test_explicit_coal_and_hydrogen_preserved_with_subset_guards(self):
        res, add, transport = energy_fixture()
        res["residential coal with cooking"] = 4.0
        res["residential coal"] = 4.0  # equal diagnostic, not another energy quantity
        add["agriculture coal"] = 5.0
        table = exporter.build_energy_totals(res, add, transport, **SCOPE)[("BAU", 2050)]
        self.assertEqual(table.loc["MA", "residential coal"], 4.0)
        self.assertEqual(table.loc["MA", "residential hydrogen"], 1.0)
        self.assertEqual(table.loc["MA", "residential biomass"], 1.0)
        self.assertEqual(table.loc["MA", "agriculture coal"], 5.0)
        self.assertEqual(table.loc["MA", "agriculture oil"], 0.0)
        self.assertNotIn("residential coal", table.attrs["metadata"]["structural_zero_columns"])
        self.assertEqual(table.attrs["metadata"]["lineage"]["residential coal"]["column"], "residential coal with cooking")
        for fuel in ("coal", "hydrogen"):
            bad = res.copy()
            bad[f"residential {fuel}"] += 1.0
            with self.subTest(fuel=fuel), self.assertRaisesRegex(ValueError, "summaries disagree"):
                exporter.build_energy_totals(bad, add, transport, **SCOPE)
        for column, value, error in (("residential heat gas", 2.0, "exceeds full carrier"),
                                     ("electricity residential", 1.0, "exceeds total electricity"),
                                     ("total residential water", .5, "electricity exceeds"),
                                     ("total residential space", 100.0, "non-cooking carrier bound")):
            bad = res.copy()
            bad[column] = value
            with self.subTest(column=column), self.assertRaisesRegex(ValueError, error):
                exporter.build_energy_totals(bad, add, transport, **SCOPE)

    def test_missing_files_and_duplicate_csv_header(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(FileNotFoundError):
                exporter.load_transport_data(root, years=[2050], scenarios=["BAU"])
            (root / "residential_all_scenarios_years_countries.csv").write_text("country,country\nMA,MA\n")
            with self.assertRaisesRegex(ValueError, "duplicate CSV header"):
                exporter.load_residential_data(root)
            self.assertFalse((root / "pypsa_input").exists())


class IndustryExportTests(unittest.TestCase):
    def build(self, industry=None, emissions=None, **kwargs):
        original_industry, original_emissions = industry_fixture()
        return exporter.build_industry_totals(
            original_industry if industry is None else industry,
            original_emissions if emissions is None else emissions, **SCOPE, **kwargs)

    def test_example_layout_heat_native_steel_and_provisional_sidecar(self):
        tables = self.build(allow_provisional=True)
        table = tables[("BAU", 2050)]
        self.assertEqual(list(table.columns), list(EXAMPLE_SECTORS))
        self.assertEqual(table.index.names, ["country", "carrier"])
        self.assertEqual(list(table.index.get_level_values("carrier")), list(EXAMPLE_QUANTITIES))
        self.assertEqual(table.shape, (11, 13))
        self.assertTrue(table.index.is_unique)
        for quantity in ("electricity", "low-temperature heat", "biomass"):
            self.assertEqual(table.loc[("MA", quantity), "iron and steel"], 2.0)
            self.assertEqual(table.loc[("MA", quantity), "construction"], 3.0)
        self.assertEqual(table.loc[("MA", "steel"), "iron and steel"], 17.0)
        emissions_row = table.loc[("MA", "process emissions")]
        self.assertEqual(emissions_row.sum(), 1_250_000.0)
        for sector in EMITTING_SECTORS:
            self.assertEqual(emissions_row[sector], 250_000.0)
        self.assertEqual(emissions_row["construction"], 0.0)
        with tempfile.TemporaryDirectory() as temporary:
            path = exporter.write_export_tables(tables, Path(temporary), "industry")[0]
            self.assertEqual(path.name, "industry_totals_2050_BAU.csv")
            saved = pd.read_csv(path)
            self.assertEqual(list(saved.columns), ["country", "carrier"] + list(EXAMPLE_SECTORS))
            self.assertFalse(saved.duplicated(["country", "carrier"]).any())
            pd.testing.assert_frame_equal(saved.set_index(["country", "carrier"]), table, check_dtype=False)
            metadata = json.loads(path.with_suffix(".units.json").read_text())
            self.assertTrue(metadata["provisional"])
            self.assertIn("missing emissions factor_provenance", metadata["blockers"])
            self.assertEqual(metadata["index_fields"], ["country", "carrier"])
            quantities = metadata["quantity_index"]
            self.assertEqual(quantities["field"], "carrier")
            self.assertTrue(quantities["legacy_field"])
            self.assertEqual(quantities["values"]["steel"], {"unit": "tSteel/a", "quantity_class": "product_activity"})
            self.assertEqual(quantities["values"]["process emissions"],
                             {"unit": "tCO2/a", "quantity_class": "process_emissions"})
            self.assertEqual(quantities["values"]["low-temperature heat"]["unit"], "MWh/a")
            self.assertNotIn("steel", metadata["quantity_classes"]["energy"]["index_values"])
            self.assertNotIn("process emissions", metadata["quantity_classes"]["energy"]["index_values"])
            self.assertEqual(set(metadata["columns"]), set(EXAMPLE_SECTORS))
            self.assertTrue(all(value == {"unit_by_index_field": "carrier"}
                                for value in metadata["columns"].values()))

    def test_tco2_does_not_convert_twice(self):
        industry, emissions = industry_fixture()
        emissions = emissions.rename(columns={"emissions_MtCO2": "emissions_tCO2"})
        emissions["unit"] = "tCO2/a"
        table = self.build(industry, emissions, allow_provisional=True)[("BAU", 2050)]
        self.assertEqual(table.loc[("MA", "process emissions")].sum(), 1.25)
        emissions["unit"] = "MtCO2/a"
        with self.assertRaisesRegex(ValueError, "contradicts unit"):
            self.build(industry, emissions, allow_provisional=True)

    def test_real_calculator_native_energy_steel_and_ammonia_units(self):
        from industry.scripts.calculate_final_energy_demand import FinalEnergyCalculator

        # Exercise the real calculation and wide-pivot methods, with in-memory
        # config only. Skip the constructor's unrelated projection/report writes.
        rows = []

        def add(sector, kind, metric, value, unit="share", fuel="", year="2050"):
            rows.append(dict(metric_1=sector, metric_2=kind, metric_3=metric, metric_4=fuel,
                             year=year, scenario="BAU", units=unit, Morocco=value))

        steel = "iron and steel"
        add(steel, "production", "steel production per year", 100, "t/a")
        for route, value in (("primary steel production", .8), ("secondary steel production", .2),
                             ("bf+bof", .75), ("dr+eaf", .25)):
            add(steel, "technology_route", route, value)
        for route, intensity in (("bf+bof", 2), ("dr+eaf", 3), ("scrap eaf", 4),
                                 ("casting, rolling & finishing", .5)):
            add(steel, "intensity_base", route, intensity * 100, "MWh/100t", year="2020")
            add(steel, "fuel_share", route, 1, fuel="electricity")
        chemical = "chemical and petrochemical"
        add(chemical, "production", "ammonia production per year", 100, "t/a")
        add(chemical, "production", "ammonia import volumes per year", 50, "t/a")
        for route, share, intensity, fuel in (("smr+hb", .6, 2, "gas"),
                                              ("renewable synthesis", .4, 3, "electricity")):
            add(chemical, "technology_route", route, share)
            add(chemical, "intensity_base", route, intensity, "MWh/t", year="2020")
            add(chemical, "fuel_share", route, 1, fuel=fuel)
        add(chemical, "technology_route", "import reallocation", .2)
        calculator = FinalEnergyCalculator.__new__(FinalEnergyCalculator)
        calculator.config, calculator.countries = pd.DataFrame(rows), ["Morocco"]
        calculator.steel_intensities = calculator.ammonia_intensities = None
        with contextlib.redirect_stdout(io.StringIO()):
            steel_result = calculator.calculate_steel_energy([2050], ["BAU"]).assign(sector=steel)
            ammonia_result = calculator.calculate_ammonia_energy([2050], ["BAU"]).assign(sector=chemical)
            wide = calculator.pivot_to_wide_format(pd.concat([steel_result, ammonia_result], ignore_index=True))
        table = self.build(wide, industry_units=exporter.CALCULATOR_UNITS, allow_provisional=True)[("BAU", 2050)]
        # Steel: 100*.8*.25 + 100*.2 = 40 tonnes, NOT MWh.
        self.assertAlmostEqual(table.loc[("MA", "steel"), steel], 40.0)
        # Fuel energy: 60*2 + 20*3 + 20*4 + 100*.5 = 310 MWh.
        self.assertAlmostEqual(table.loc[("MA", "electricity"), steel], 310.0)
        # Ammonia product-bus energy: (100*.4 + 50*.2)*5.17 = 258.5 MWh.
        self.assertAlmostEqual(table.loc[("MA", "ammonia"), chemical], 258.5)
        self.assertAlmostEqual(table.loc[("MA", "gas"), chemical], 120.0)
        self.assertAlmostEqual(table.loc[("MA", "electricity"), chemical], 120.0)

    def test_new_producer_dual_units_and_readiness_cannot_be_overridden(self):
        industry, emissions = industry_fixture()
        emissions["emissions_tCO2"] = emissions["emissions_MtCO2"] * 1e6
        emissions["provisional_emissions_tCO2"] = emissions["emissions_tCO2"]
        emissions["provisional_emissions_MtCO2"] = emissions["emissions_MtCO2"]
        emissions["emissions_units"] = "tCO2/a"
        emissions["gas_basis"] = "CO2"
        emissions["readiness"] = "provisional"
        emissions["ready_for_export"] = "False"
        emissions["blockers"] = '["source_unverified"]'
        claimed_ready = {"status": "ready", "factor_provenance": "synthetic evidence",
                         "ammonia_basis": "test boundary", "aluminium_basis": "test CO2"}
        with self.assertRaisesRegex(ValueError, "provisional/blocked"):
            self.build(industry, emissions, emissions_readiness=claimed_ready)
        table = self.build(industry, emissions, emissions_readiness=claimed_ready,
                           allow_provisional=True)[("BAU", 2050)]
        self.assertTrue(table.attrs["metadata"]["provisional"])
        self.assertIn("source_unverified", table.attrs["metadata"]["blockers"])
        self.assertEqual(table.loc[("MA", "process emissions")].sum(), 1_250_000)
        emissions["gas_basis"] = "CO2e"
        with self.assertRaisesRegex(ValueError, "physical CO2"):
            self.build(industry, emissions, allow_provisional=True)
        emissions["gas_basis"] = "CO2"
        emissions.loc[0, "emissions_MtCO2"] = 99
        with self.assertRaisesRegex(ValueError, "inconsistent"):
            self.build(industry, emissions, allow_provisional=True)

    def test_ready_requires_provenance_and_both_accounting_bases(self):
        with self.assertRaisesRegex(ValueError, "BLOCKER"):
            self.build()
        for field in ("factor_provenance", "ammonia_basis", "aluminium_basis"):
            metadata = {"status": "ready", "factor_provenance": "synthetic test evidence",
                        "ammonia_basis": "test-only energy-side accounting",
                        "aluminium_basis": "test-only CO2, not CO2e"}
            metadata.pop(field)
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "BLOCKER"):
                self.build(emissions_readiness=metadata)
        metadata = {"status": "ready", "factor_provenance": "synthetic test evidence",
                    "ammonia_basis": "test-only energy-side accounting", "aluminium_basis": "test-only CO2"}
        table = self.build(emissions_readiness=metadata)[("BAU", 2050)]
        self.assertFalse(table.attrs["metadata"]["provisional"])

    def test_missing_or_incorrect_industry_units_block_even_provisional(self):
        industry, emissions = industry_fixture()
        industry.attrs.clear()
        with self.assertRaisesRegex(ValueError, "must declare"):
            self.build(industry, emissions, allow_provisional=True)
        industry.attrs["units"] = {carrier: "MWh/a" for carrier in industry["carrier"]}
        with self.assertRaisesRegex(ValueError, "steel must declare tSteel/a"):
            self.build(industry, emissions, allow_provisional=True)

    def test_duplicate_unknown_missing_and_negative_inputs(self):
        industry, emissions = industry_fixture()
        with self.assertRaisesRegex(ValueError, "duplicate keys"):
            self.build(pd.concat([industry, industry]), emissions, allow_provisional=True)
        with self.assertRaisesRegex(ValueError, "duplicate keys"):
            self.build(industry, pd.concat([emissions, emissions]), allow_provisional=True)
        unknown = industry.copy()
        unknown.loc[0, "carrier"] = "unobtainium"
        with self.assertRaisesRegex(ValueError, "unknown"):
            self.build(unknown, emissions, allow_provisional=True)
        with self.assertRaisesRegex(ValueError, "missing columns"):
            self.build(industry.drop(columns="construction"), emissions, allow_provisional=True)
        with self.assertRaisesRegex(ValueError, "sector coverage"):
            self.build(industry, emissions.iloc[:-1], allow_provisional=True)
        bad = emissions.copy()
        bad.loc[0, "emissions_MtCO2"] = -1
        with self.assertRaisesRegex(ValueError, "nonnegative"):
            self.build(industry, bad, allow_provisional=True)
        bad = industry.copy()
        bad.loc[bad["carrier"] == "steel", "construction"] = 1
        with self.assertRaisesRegex(ValueError, "steel activity"):
            self.build(bad, emissions, allow_provisional=True)

    def test_missing_values_never_become_structural_zeros(self):
        for value in (np.nan, np.inf, -1.0):
            industry, emissions = industry_fixture()
            industry.loc[0, "construction"] = value
            with self.subTest(source="industry", value=value), self.assertRaisesRegex(ValueError, "finite and nonnegative"):
                self.build(industry, emissions, allow_provisional=True)
            industry, emissions = industry_fixture()
            emissions.loc[0, "emissions_MtCO2"] = value
            with self.subTest(source="emissions", value=value), self.assertRaisesRegex(ValueError, "finite and nonnegative"):
                self.build(industry, emissions, allow_provisional=True)

    def test_real_emissions_summary_gate_never_uses_provisional_placeholder(self):
        from industry.scripts.calculate_process_emissions import summarize_process_emissions

        _, legacy = industry_fixture()
        detailed = legacy.assign(emissions_tCO2=0.25, provisional_emissions_tCO2=999.0,
                                 ready_for_export=False, blockers='["unverified_factor"]')
        summary = summarize_process_emissions(detailed)
        table = self.build(emissions=summary, allow_provisional=True)[("BAU", 2050)]
        self.assertEqual(table.loc[("MA", "process emissions"), "iron and steel"], 0.25)
        detailed.loc[0, "emissions_tCO2"] = np.nan
        blocked = summarize_process_emissions(detailed)
        self.assertTrue(blocked["emissions_tCO2"].isna().any())
        with self.assertRaisesRegex(ValueError, "finite and nonnegative"):
            self.build(emissions=blocked, allow_provisional=True)

    def test_all_subsectors_and_quantity_classes_conserve_each_scope(self):
        industry, emissions = industry_fixture()
        frames, summaries = [], []
        for n, (country, scenario, year) in enumerate(
                (c, s, y) for c in ("MA", "CL") for s in exporter.SCENARIOS for y in exporter.TARGET_YEARS):
            wide = industry.assign(country=country, scenario=scenario, year=year).copy()
            for i, sector in enumerate(EXAMPLE_SECTORS):
                wide.loc[wide["carrier"] != "steel", sector] = (n + 1) * (i + 1)
            frames.append(wide)
            summaries.append(emissions.assign(country=country, scenario=scenario, year=year,
                                               emissions_MtCO2=(n + 1) / 1e6))
        wide, summary = pd.concat(frames, ignore_index=True), pd.concat(summaries, ignore_index=True)
        # Remove one entire sparse carrier row; only that missing row is zero.
        sparse = (wide.country == "CL") & (wide.scenario == "BAU") & (wide.year == 2030) & (wide.carrier == "gas")
        wide = wide.loc[~sparse].copy()
        tables = exporter.build_industry_totals(wide, summary, countries=["MA", "CL"], allow_provisional=True)
        self.assertEqual(len(tables), 15)
        self.assertTrue(tables[("BAU", 2030)].loc[("CL", "gas")].eq(0).all())
        self.assertEqual(len(tables[("BAU", 2030)].attrs["metadata"]["structural_zero_rows"]), 1)
        for (scenario, year), table in tables.items():
            self.assertEqual(table.shape, (22, 13))
            self.assertTrue(table.index.is_unique)
            for country in ("MA", "CL"):
                original = wide.loc[(wide.country == country) & (wide.scenario == scenario) & (wide.year == year)].copy()
                original["carrier"] = original["carrier"].replace({"heat": "low-temperature heat"})
                expected = original.set_index("carrier")[list(EXAMPLE_SECTORS)].reindex(
                    [label for label in EXAMPLE_QUANTITIES if label != "process emissions"], fill_value=0.0)
                actual = table.xs(country).drop(index="process emissions")
                pd.testing.assert_frame_equal(actual, expected, check_dtype=False)
                energy_labels = [label for label in EXAMPLE_QUANTITIES if label not in ("steel", "process emissions")]
                np.testing.assert_allclose(actual.loc[energy_labels].sum(), expected.loc[energy_labels].sum())
                self.assertEqual(actual.loc["steel"].sum(), 17.0)
                pe = summary.loc[(summary.country == country) & (summary.scenario == scenario) & (summary.year == year)]
                for sector in EMITTING_SECTORS:
                    self.assertAlmostEqual(table.loc[(country, "process emissions"), sector],
                                           pe.loc[pe.sector == sector, "emissions_MtCO2"].iloc[0] * 1e6)


class ImportAndMainTests(unittest.TestCase):
    def test_import_has_no_prints_io_or_calculator_import(self):
        code = ("import pathlib; from unittest.mock import patch; "
                "import pandas, numpy, pycountry; "
                "guard=patch.object(pathlib.Path, 'mkdir', side_effect=AssertionError('mkdir at import')); "
                "guard.start(); import build_pypsa_energy_demands; import sys; "
                "assert 'industry.scripts.calculate_final_energy_demand' not in sys.modules")
        with tempfile.TemporaryDirectory() as temporary:
            environment = dict(os.environ, PYTHONPATH=str(Path(exporter.__file__).parent),
                               PYTHONDONTWRITEBYTECODE="1")
            result = subprocess.run([sys.executable, "-c", code], cwd=temporary, env=environment,
                                    capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
            self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_main_uses_fresh_calculator_and_only_supplied_directories(self):
        res, add, transport = energy_fixture()
        industry, emissions = industry_fixture()
        calls = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ("residential", "additional", "transport", "interim"):
                (root / name).mkdir()
            res.to_csv(root / "residential/residential_all_scenarios_years_countries.csv", index=False)
            for prefix, filename in exporter.ADDITIONAL_FILES.items():
                columns = ["country", "year", "unit"] + [col for col in add if col.startswith(prefix + " ")]
                add[columns].to_csv(root / "additional" / filename, index=False)
            transport["scenario"] = "2050_BAU"
            transport.drop(columns="year").to_csv(root / "transport/transport_BAU_2050.csv", index=False)
            pd.DataFrame([{"metric_1": "test", "MA": 0}]).to_csv(root / "config.csv", index=False)

            class FakeCalculator:
                def __init__(self, config_path, interim_dir, **kwargs):
                    calls.append((config_path, interim_dir, kwargs))
                    emissions.to_csv(interim_dir / "process_emissions_summary.csv", index=False)

                def calculate_all_detailed_sectors(self, **kwargs):
                    calls.append(kwargs)
                    return industry

                def pivot_to_wide_format(self, results):
                    # The real calculator currently has no unit attrs: main must
                    # explicitly apply its verified MWh/tonnes producer contract.
                    results.attrs.clear()
                    return results

            module = types.ModuleType("industry.scripts.calculate_final_energy_demand")
            module.FinalEnergyCalculator = FakeCalculator
            argv = ["--years", "2050", "--scenarios", "BAU", "--transport-unit", "GWh", "--allow-provisional"]
            for option, name in (("residential-output-dir", "residential"), ("additional-output-dir", "additional"),
                                 ("transport-output-dir", "transport"), ("interim-dir", "interim"),
                                 ("config-path", "config.csv"), ("output-dir", "exports")):
                argv.extend(["--" + option, str(root / name)])
            with patch.dict(sys.modules, {module.__name__: module}), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(exporter.main(argv), 0)
            self.assertEqual(calls[0][1], root / "interim")
            self.assertEqual(calls[1], {"years": [2050], "scenarios": ["BAU"]})
            self.assertEqual(len(list((root / "exports").glob("*.csv"))), 2)
            self.assertEqual(len(list((root / "exports").glob("*.units.json"))), 2)
            for sidecar in (root / "exports").glob("*.units.json"):
                self.assertTrue(json.loads(sidecar.read_text())["provisional"])
            self.assertFalse((root / "final_energy_demand_detailed_sectors_wide.csv").exists())
            industry_csv = pd.read_csv(root / "exports/industry_totals_2050_BAU.csv")
            self.assertEqual(list(industry_csv.columns), ["country", "carrier"] + list(EXAMPLE_SECTORS))
            self.assertEqual(industry_csv.loc[industry_csv.carrier == "steel", "iron and steel"].iloc[0], 17.0)
            # No export-directory creation if fresh physical CO2 is missing,
            # even with --allow-provisional and finite review placeholders.
            emissions.loc[0, "emissions_MtCO2"] = np.nan
            argv[argv.index(str(root / "exports"))] = str(root / "blocked_exports")
            with patch.dict(sys.modules, {module.__name__: module}), self.assertRaisesRegex(ValueError, "finite and nonnegative"):
                exporter.main(argv)
            self.assertFalse((root / "blocked_exports").exists())


class RealProducerArtifactTests(unittest.TestCase):
    """Opt-in, read-only checks of fresh producer files, never patched acceptance."""

    def directory(self, variable):
        value = os.environ.get(variable)
        if not value:
            self.skipTest(f"Set {variable} for fresh producer QA")
        return Path(value)

    def test_all15_real_energy_lineage_units_and_diagnostics(self):
        residential_dir = self.directory("PYPSA_RESIDENTIAL_DIR")
        residential = exporter.load_residential_data(residential_dir)
        additional = exporter.load_additional_sectors_data(self.directory("PYPSA_ADDITIONAL_DIR"))
        transport = exporter.load_transport_data(self.directory("PYPSA_TRANSPORT_DIR"))
        countries = list(transport.country.unique())
        tables = exporter.build_energy_totals(residential, additional, transport, countries=countries)
        self.assertEqual(len(tables), 15)
        detailed = pd.read_csv(residential_dir / "final_energy_demand_all_end_uses.csv")
        detailed["country"] = detailed.country.map(exporter.get_iso_code)
        residential = exporter._dimensions(residential, "real residential").set_index(exporter.KEYS)
        transport = exporter._dimensions(transport, "real transport").set_index(exporter.KEYS)
        additional = additional.set_index(["country", "year"])
        fuel_groups = {"biomass": {"traditional biomass", "modern biomass", "wood"},
                       "coal": {"coal"}, "hydrogen": {"hydrogen"},
                       "gas": {"natural gas", "gas", "biogas"}, "oil": {"kerosene", "oil", "diesel", "lpg"},
                       "electricity": {"electricity"}}
        with tempfile.TemporaryDirectory() as temporary:
            paths = exporter.write_export_tables(tables, Path(temporary), "energy")
            self.assertEqual(len(paths), 15)
            for (scenario, year), table in tables.items():
                self.assertEqual(list(table.columns), list(exporter.ENERGY_COLUMNS))
                for country in table.index:
                    key = (country, scenario, year)
                    raw = detailed.loc[(detailed.country == country) & (detailed.scenario == scenario) & (detailed.year == year)]
                    self.assertFalse(raw.empty)
                    fuel = raw.fuel.str.strip().str.lower()
                    # A legacy coal-in-biomass summary can only certify the exact
                    # fuel split here if raw coal is genuinely zero, not inferred.
                    if "residential coal with cooking" not in residential.columns and "residential coal" not in residential.columns:
                        self.assertEqual(raw.loc[fuel.eq("coal"), "final_energy_demand_twh"].sum(), 0.0,
                                         "Legacy coal-in-biomass summary cannot certify positive separate coal")
                    for name, aliases in fuel_groups.items():
                        target = "electricity residential" if name == "electricity" else f"residential {name}"
                        self.assertAlmostEqual(table.loc[country, target],
                            raw.loc[fuel.isin(aliases), "final_energy_demand_twh"].sum(), places=8)
                    for col in exporter.TRANSPORT_REQUIRED:
                        self.assertAlmostEqual(table.loc[country, col], transport.loc[key, col], places=10)
                    for col in additional.columns.intersection(table.columns):
                        self.assertAlmostEqual(table.loc[country, col], additional.loc[(country, year), col], places=10)
                    nav = sum(table.loc[country, f"total navigation {fuel}"] for fuel in ("oil", "hydrogen", "ammonia"))
                    self.assertAlmostEqual(table.loc[country, "total domestic navigation"],
                                           nav + transport.loc[key, "total navigation biomass"], places=10)
                saved = pd.read_csv(Path(temporary) / f"energy_totals_{scenario}_{year}.csv", index_col="country")
                pd.testing.assert_frame_equal(saved, table, check_dtype=False)
                sidecar = json.loads((Path(temporary) / f"energy_totals_{scenario}_{year}.units.json").read_text())
                self.assertEqual(sidecar["input_units"], {"residential": "TWh", "additional": "TWh", "transport": "TWh"})
                self.assertTrue(all(value["unit"] == ("fraction" if col == "district heat share" else "TWh/a")
                                    for col, value in sidecar["columns"].items()))
                for col in exporter.TRANSPORT_DIAGNOSTICS:
                    diagnostics = sidecar["diagnostic_submeasures"]["transport"][col]
                    self.assertEqual(diagnostics["unit"], "TWh/a")
                    for record in diagnostics["values"]:
                        key = tuple(record[k] for k in exporter.KEYS)
                        self.assertAlmostEqual(record["value"], transport.loc[key, col], places=10)

    def test_all15_real_industry_blocked_before_writes(self):
        root = self.directory("PYPSA_INDUSTRY_DIR")
        wide = pd.read_csv(root / "output_data/final_energy_demand_detailed_sectors_wide.csv")
        emissions = pd.read_csv(root / "interim_data/process_emissions_summary.csv")
        readiness = json.loads((root / "interim_data/process_emissions_readiness.json").read_text())
        self.assertEqual(len(wide[exporter.KEYS].drop_duplicates()), 15)
        self.assertEqual(len(emissions[exporter.KEYS].drop_duplicates()), 15)
        self.assertTrue(emissions.emissions_tCO2.isna().any())
        self.assertTrue(emissions.provisional_emissions_tCO2.notna().all())
        countries = list(wide.country.unique())
        with tempfile.TemporaryDirectory() as temporary, patch.object(exporter, "write_export_tables") as writer:
            output = Path(temporary) / "blocked"
            with self.assertRaisesRegex(ValueError, "emissions_tCO2.*finite and nonnegative"):
                exporter.export_industry_totals_by_scenario_year(wide, emissions, output,
                    countries=countries, industry_units=exporter.CALCULATOR_UNITS, emissions_readiness=readiness)
            writer.assert_not_called()
            self.assertFalse(output.exists())
        self.assertEqual(exporter.INDUSTRY_UNITS["steel"], "tSteel/a")
        self.assertEqual(exporter.INDUSTRY_UNITS["process emissions"], "tCO2/a")
        self.assertTrue(all(unit == "MWh/a" for label, unit in exporter.CALCULATOR_UNITS.items() if label != "steel"))


class ReadOnlyReferenceTests(unittest.TestCase):
    def references(self):
        directory = os.environ.get("PYPSA_REFERENCE_DIR")
        if not directory:
            self.skipTest("Set PYPSA_REFERENCE_DIR to read local examples without copying them")
        return Path(directory)

    def test_actual_el_rf_energy_headers(self):
        directory = self.references()
        for scenario in ("EL", "RF"):
            for year in (2030, 2050):
                energy = pd.read_csv(directory / f"energy_totals_{scenario}_{year}.csv")
                self.assertEqual(list(energy.columns), ["country"] + list(exporter.ENERGY_COLUMNS))
                self.assertEqual(energy.shape[1], 60)
                res, add, transport = energy_fixture()
                countries = list(energy.country)
                res = pd.concat([res.assign(country=c) for c in countries], ignore_index=True)
                add = pd.concat([add.assign(country=c) for c in countries], ignore_index=True)
                transport = pd.concat([transport.assign(country=c) for c in countries], ignore_index=True)
                output = exporter.build_energy_totals(res, add, transport, countries=countries,
                    years=[2050], scenarios=["BAU"], transport_unit="GWh")
                with tempfile.TemporaryDirectory() as temporary:
                    saved = pd.read_csv(exporter.write_export_tables(output, Path(temporary), "energy")[0])
                    self.assertEqual(saved.shape, energy.shape)
                    self.assertEqual(list(saved.columns), list(energy.columns))
                    self.assertFalse(saved.country.duplicated().any())

    def test_all_original_industry_shapes_and_per_sector_quantity_conservation(self):
        directory = self.references()
        paths = sorted(directory.rglob("industry_totals_*.csv"))
        self.assertEqual(len(paths), 6)  # EL/RF plus both MAPaper examples
        for path in paths:
            with self.subTest(example=path.relative_to(directory)):
                reference = pd.read_csv(path)
                self.assertEqual(list(reference.columns), ["country", "carrier"] + list(EXAMPLE_SECTORS))
                self.assertFalse(reference.duplicated(["country", "carrier"]).any())
                for _, rows in reference.groupby("country", sort=False):
                    self.assertEqual(list(rows.carrier), list(EXAMPLE_QUANTITIES))
                countries = list(reference.country.unique())

                def build(frame):
                    wide = frame[frame.carrier != "process emissions"].assign(year=2050, scenario="BAU")
                    wide.attrs["units"] = {label: "tSteel/a" if label == "steel" else "MWh/a"
                                           for label in wide.carrier}
                    summary = frame[frame.carrier == "process emissions"].melt(
                        id_vars=["country"], value_vars=list(EXAMPLE_SECTORS),
                        var_name="sector", value_name="emissions_tCO2").assign(year=2050, scenario="BAU")
                    return exporter.build_industry_totals(wide, summary, countries=countries,
                        years=[2050], scenarios=["BAU"], allow_provisional=True)

                if reference[list(EXAMPLE_SECTORS)].isna().any().any():
                    # Reject original missing values; never zero-assume them.
                    with self.assertRaisesRegex(ValueError, "finite and nonnegative"):
                        build(reference)
                    # A wholly synthetic finite fixture tests this file's shape;
                    # it makes no claim about the missing example's numeric totals.
                    fixture = reference[["country", "carrier"]].copy()
                    for n, sector in enumerate(EXAMPLE_SECTORS):
                        fixture[sector] = np.arange(1, len(fixture) + 1, dtype=float) * (n + 1)
                    fixture.loc[fixture.carrier == "steel", [s for s in EXAMPLE_SECTORS if s != "iron and steel"]] = 0.0
                else:
                    fixture = reference.copy()  # exact numeric conservation on complete examples
                output = build(fixture)[("BAU", 2050)]
                expected = fixture.set_index(["country", "carrier"]).reindex(output.index)
                pd.testing.assert_frame_equal(output, expected, check_dtype=False)
                for label in EXAMPLE_QUANTITIES:
                    np.testing.assert_allclose(output.xs(label, level="carrier").sum(),
                                               expected.xs(label, level="carrier").sum(), rtol=1e-12, atol=1e-8)
                for labels in ([q for q in EXAMPLE_QUANTITIES if q not in ("steel", "process emissions")],
                               ["steel"], ["process emissions"]):
                    mask = output.index.get_level_values("carrier").isin(labels)
                    np.testing.assert_allclose(output.loc[mask].sum(), expected.loc[mask].sum(), rtol=1e-12, atol=1e-8)
                with tempfile.TemporaryDirectory() as temporary:
                    saved = pd.read_csv(exporter.write_export_tables({("BAU", 2050): output}, Path(temporary), "industry")[0])
                    self.assertEqual(saved.shape, reference.shape)
                    self.assertEqual(list(saved.columns), list(reference.columns))
                    self.assertFalse(saved.duplicated(["country", "carrier"]).any())

    def test_actual_transport_indicators_do_not_convert_twh_twice(self):
        directory = os.environ.get("PYPSA_TRANSPORT_DIR")
        if not directory:
            self.skipTest("Set PYPSA_TRANSPORT_DIR for read-only producer output validation")
        transport = exporter.load_transport_data(Path(directory), years=[2050], scenarios=["BAU"])
        countries = list(transport["country"])
        res, add, _ = energy_fixture()
        res = pd.concat([res.assign(country=country) for country in countries], ignore_index=True)
        add = pd.concat([add.assign(country=country) for country in countries], ignore_index=True)
        table = exporter.build_energy_totals(res, add, transport, countries=countries,
                                             years=[2050], scenarios=["BAU"])[("BAU", 2050)]
        expected = transport.set_index(transport["country"].map(exporter.get_iso_code))["total road"].sort_index()
        np.testing.assert_allclose(table["total road"], expected, rtol=1e-12)


if __name__ == "__main__":
    unittest.main()