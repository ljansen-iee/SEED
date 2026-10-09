"""Focused emissions hand checks; unittest only, all reports in temp directories."""

import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from industry.scripts.calculate_process_emissions import (
    ProcessEmissionCalculator, generate_process_emissions_reports,
    production_to_tonnes, require_accepted_process_emissions,
    summarize_process_emissions,
)
from industry.utils.process_emission_factors import (
    PROCESS_EMISSION_FACTORS, get_emission_factor, get_emission_factor_metadata,
)


YEARS = [2030]
SCENARIOS = ['BAU']


def row(sector, kind, metric, value, units='share', **kwargs):
    return dict(metric_1=sector, metric_2=kind, metric_3=metric, metric_4='',
                year=2030, scenario='BAU', units=units, Egypt=value, **kwargs)


def steel_rows(value=1e6, units='t/a'):
    sector = 'iron and steel'
    return [row(sector, 'production', 'steel production per year', value, units),
            row(sector, 'technology_route', 'primary steel production', .8),
            row(sector, 'technology_route', 'secondary steel production', .2),
            row(sector, 'technology_route', 'bf+bof', .75),
            row(sector, 'technology_route', 'dr+eaf', .25)]


def chemical_rows():
    sector = 'chemical and petrochemical'
    return [row(sector, 'production', 'HVC production per year', 1e6, 't/a'),
            row(sector, 'technology_route', 'Naphtha cracking', .6),
            row(sector, 'technology_route', 'LPG cracking', .25),
            row(sector, 'technology_route', 'MTO', .15),
            row(sector, 'production', 'ammonia production per year', 1e6, 't/a'),
            row(sector, 'technology_route', 'SMR+HB', .6),
            row(sector, 'technology_route', 'Renewable synthesis', .4),
            row(sector, 'production', 'ammonia import volumes per year', 5e5, 't/a'),
            row(sector, 'production', 'ammonia import reallocated volume per year', 1e5, 't/a'),
            row(sector, 'technology_route', 'import reallocation', .2)]


def cement_rows():
    sector = 'non-metallic minerals'
    return [row(sector, 'production', 'Cement production per year', 2e6, 't/a'),
            row(sector, 'technology_route', 'Clinker ratio', .7)]


def aluminium_rows():
    sector = 'non-ferrous metals'
    return [row(sector, 'production', 'Aluminium production per year', 1e6, 't/a'),
            row(sector, 'technology_route', 'Primary aluminium', .6),
            row(sector, 'technology_route', 'Secondary aluminium', .4)]


def calc(rows):
    return ProcessEmissionCalculator(config_df=pd.DataFrame(rows))


class ProcessEmissionsTests(unittest.TestCase):
    def test_units_equivalent_and_no_100x_error(self):
        for value, units in [(1e6, 't/a'), (1e4, '100t/a'), (1, 'Mt/a'),
                             (1e6, 't/year'), (1e6, 'tonnes')]:
            with self.subTest(units=units):
                self.assertEqual(production_to_tonnes(value, units), 1e6)
                emissions = calc(steel_rows(value, units)).calculate_steel_emissions(YEARS, SCENARIOS)
                self.assertAlmostEqual(emissions.emissions_tCO2.sum(), 152000)
                self.assertAlmostEqual(emissions.emissions_MtCO2.sum(), .152)

    def test_units_and_production_are_strict(self):
        for value, unit in [(1, 'GWh'), (1, ''), (None, 't/a'),
                            (-1, 't/a'), ('bad', 't/a'), (math.inf, 't/a')]:
            with self.subTest(value=value, unit=unit), self.assertRaises(ValueError):
                production_to_tonnes(value, unit)

    def test_factor_normalization_and_numeric_set(self):
        self.assertEqual(get_emission_factor(' Iron and Steel ', ' bf + bof '), .22)
        self.assertEqual(get_emission_factor('iron and steel', 'scrap eaf'), .05)
        self.assertEqual(get_emission_factor('non-ferrous metals', 'PRIMARY ALUMINIUM'), 1.5)
        self.assertEqual(get_emission_factor('chemical and petrochemical', 'SMR+HB'), 0)
        self.assertEqual(get_emission_factor('chemical and petrochemical', 'E+HB'), 0)
        self.assertEqual(get_emission_factor('food and tobacco'), 0)
        self.assertEqual(get_emission_factor('iron and steel', 'Unspecified'), .15)
        self.assertEqual([list(values.values()) for values in PROCESS_EMISSION_FACTORS.values()],
                         [[.22, .05, .05, .15], [.54, .03, .02, .4],
                          [.18, .23, 0, 0, 0, 0, .12], [1.5, 0, .03, .03, .03, .5],
                          [.02, .01]] + [[0]] * 8)

    def test_unknown_missing_and_bad_factors_never_fallback(self):
        for sector, route in [('unknown', None), ('iron and steel', None),
                              ('iron and steel', 'bf+boff')]:
            with self.subTest(sector=sector, route=route), self.assertRaises(ValueError):
                get_emission_factor(sector, route)
        factors = PROCESS_EMISSION_FACTORS['iron and steel']
        for value in [None, -1, 'bad', math.inf, math.nan]:
            with patch.dict(factors, {'BF+BOF': value}), self.assertRaises(ValueError):
                calc(steel_rows()).calculate_steel_emissions(YEARS, SCENARIOS)
        with patch.dict(factors, {}, clear=True), self.assertRaises(ValueError):
            get_emission_factor('iron and steel', 'BF+BOF')

    def test_factor_metadata_is_explicit_and_independent(self):
        data = get_emission_factor_metadata('iron and steel', 'bf+bof')
        self.assertIsNone(data['factor_provenance'])
        self.assertIsNone(data['factor_version'])
        self.assertEqual(data['factor_gas_basis'], 'unverified')
        self.assertEqual(data['factor_status'], 'provisional')
        data['factor_blockers'].clear()
        self.assertTrue(get_emission_factor_metadata('iron and steel', 'bf+bof')['factor_blockers'])
        self.assertIn('ammonia_source_missing', get_emission_factor_metadata(
            'chemical and petrochemical', 'SMR+HB')['factor_blockers'])

    def test_steel_hierarchy_conserves_and_never_counts_parent_rows(self):
        result = calc(steel_rows()).calculate_steel_emissions(YEARS, SCENARIOS).set_index('route')
        self.assertEqual(set(result.index), {'BF+BOF', 'DR+EAF', 'EAF'})
        self.assertAlmostEqual(result.loc['BF+BOF', 'production_t'], 600000)
        self.assertAlmostEqual(result.loc['DR+EAF', 'production_t'], 200000)
        self.assertAlmostEqual(result.loc['EAF', 'production_t'], 200000)
        self.assertAlmostEqual(result.production_t.sum(), 1e6)

    def test_dr_subroutes_are_conditional_and_replace_parent(self):
        rows = steel_rows() + [row('iron and steel', 'technology_route', 'DR+EAF+H2', .25),
                               row('iron and steel', 'technology_route', 'DR+EAF+NG', .75)]
        result = calc(rows).calculate_steel_emissions(YEARS, SCENARIOS).set_index('route')
        self.assertNotIn('DR+EAF', result.index)
        self.assertAlmostEqual(result.loc['DR+EAF+H2', 'production_t'], 50000)
        self.assertAlmostEqual(result.loc['DR+EAF+NG', 'production_t'], 150000)
        self.assertAlmostEqual(result.production_t.sum(), 1e6)
        self.assertAlmostEqual(result.emissions_tCO2.sum(), 152000)

    def test_dr_subroutes_in_metric_four(self):
        rows = steel_rows()
        for fuel, value in [('hydrogen', .25), ('natural gas', .75)]:
            child = row('iron and steel', 'technology_route', 'dr+eaf', value)
            child['metric_4'] = fuel
            rows.append(child)
        self.assertAlmostEqual(calc(rows).calculate_steel_emissions(YEARS, SCENARIOS).production_t.sum(), 1e6)

    def test_share_failures_missing_bounds_sums_duplicates_unknown(self):
        changes = [lambda rows: rows.pop(),
                   lambda rows: rows[1].update(Egypt=None),
                   lambda rows: rows[1].update(Egypt=-.1),
                   lambda rows: rows[1].update(Egypt=80),
                   lambda rows: rows[1].update(Egypt=.7),
                   lambda rows: rows.append(rows[3].copy()),
                   lambda rows: rows.append(row('iron and steel', 'technology_route', 'typo', 0)),
                   lambda rows: rows.append(row('iron and steel', 'technology_route', 'DR+EAF+H2', 1))]
        for change in changes:
            rows = steel_rows()
            change(rows)
            with self.subTest(change=change), self.assertRaises(ValueError):
                calc(rows).calculate_steel_emissions(YEARS, SCENARIOS)

    def test_explicit_percent_units_not_implicit_renormalization(self):
        rows = steel_rows()
        for item in rows[1:]:
            item['Egypt'] *= 100
            item['units'] = '%'
        self.assertAlmostEqual(calc(rows).calculate_steel_emissions(YEARS, SCENARIOS).emissions_tCO2.sum(), 152000)

    def test_zero_activity_keeps_trace_and_blockers(self):
        result = calc(steel_rows(0)).calculate_steel_emissions(YEARS, SCENARIOS)
        self.assertEqual(len(result), 3)
        self.assertEqual(result.emissions_tCO2.sum(), 0)
        self.assertFalse(result.ready_for_export.any())

    def test_clinker_basis_and_hand_check(self):
        result = calc(cement_rows()).calculate_cement_emissions(YEARS, SCENARIOS)
        self.assertEqual(result.iloc[0].production_t, 1.4e6)
        self.assertAlmostEqual(result.iloc[0].emissions_tCO2, 756000)
        self.assertEqual(result.iloc[0].production_basis, 'clinker')
        with self.assertRaises(ValueError):
            calc(cement_rows()[:1]).calculate_cement_emissions(YEARS, SCENARIOS)
        with self.assertRaises(ValueError):
            calc(cement_rows()).calculate_generic_sector_emissions(
                'non-metallic minerals', 'cement production per year', 'Cement', YEARS, SCENARIOS)

    def test_direct_clinker_not_double_counted_and_must_agree(self):
        rows = cement_rows() + [row('non-metallic minerals', 'production', 'clinker production per year', 1.4, 'Mt/a')]
        result = calc(rows).calculate_cement_emissions(YEARS, SCENARIOS)
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result.emissions_tCO2.sum(), 756000)
        rows[-1]['Egypt'] = 2
        with self.assertRaises(ValueError):
            calc(rows).calculate_cement_emissions(YEARS, SCENARIOS)
        direct = calc([rows[-1]]).calculate_cement_emissions(YEARS, SCENARIOS)
        self.assertAlmostEqual(direct.emissions_tCO2.sum(), 1080000)

    def test_hvc_route_factors_and_chemical_family_separation(self):
        result = calc(chemical_rows()).calculate_hvc_emissions(YEARS, SCENARIOS)
        self.assertEqual(len(result), 3)
        self.assertEqual(set(result.route), {'Naphtha cracking', 'LPG cracking', 'MTO'})
        self.assertEqual(result.production_t.sum(), 1e6)
        self.assertAlmostEqual(result.emissions_tCO2.sum(), 187500)
        self.assertEqual(sorted(result.factor_tCO2_per_t), [.18, .18, .23])

    def test_hvc_recycling_factors_and_missing_routes(self):
        sector = 'chemical and petrochemical'
        rows = [row(sector, 'production', 'HVC production per year', 1, 'Mt/a'),
                row(sector, 'technology_route', 'HVC_primary', .5),
                row(sector, 'technology_route', 'HVC_mechanical_recycling', .3),
                row(sector, 'technology_route', 'HVC_chemical_recycling', .2)]
        self.assertEqual(calc(rows).calculate_hvc_emissions(YEARS, SCENARIOS).emissions_tCO2.sum(), 90000)
        with self.assertRaises(ValueError):
            calc(rows[:1]).calculate_hvc_emissions(YEARS, SCENARIOS)

    def test_ammonia_here_local_plus_reallocated_green_not_import_total(self):
        result = calc(chemical_rows()).calculate_ammonia_emissions(YEARS, SCENARIOS).set_index('route')
        self.assertEqual(result.loc['SMR+HB', 'production_t'], 600000)
        self.assertEqual(result.loc['E+HB', 'production_t'], 500000)
        self.assertTrue(pd.isna(result.loc['SMR+HB', 'emissions_tCO2']))
        self.assertEqual(result.loc['SMR+HB', 'provisional_emissions_tCO2'], 0)
        self.assertIn('ammonia_source_missing', json.loads(result.loc['SMR+HB', 'blockers']))
        self.assertFalse(result.ready_for_export.any())

    def test_ammonia_reallocation_mismatch_and_e_hb_alias(self):
        rows = chemical_rows()
        rows[6]['metric_3'] = 'E+HB'
        self.assertEqual(len(calc(rows).calculate_ammonia_emissions(YEARS, SCENARIOS)), 2)
        rows[8]['Egypt'] = 200000
        with self.assertRaises(ValueError):
            calc(rows).calculate_ammonia_emissions(YEARS, SCENARIOS)

    def test_aluminium_co2_only_no_pfc_guess_or_zero_mask(self):
        result = calc(aluminium_rows()).calculate_aluminium_emissions(YEARS, SCENARIOS).set_index('route')
        primary = result.loc['Aluminium_primary']
        self.assertEqual(primary.factor_tCO2_per_t, 1.5)
        self.assertEqual(primary.provisional_emissions_tCO2, 900000)
        self.assertTrue(pd.isna(primary.emissions_tCO2))
        self.assertEqual(primary.gas_basis, 'CO2')
        self.assertEqual(primary.factor_gas_basis, 'unverified')
        self.assertEqual(result.loc['Aluminium_secondary', 'emissions_tCO2'], 0)

    def test_paper_correct_units_and_factors(self):
        rows = [row('paper, pulp and printing', 'production', 'pulp production per year', 100000, 't/a'),
                row('paper, pulp and printing', 'production', 'paper production per year', 200000, 't/a')]
        self.assertEqual(calc(rows).calculate_paper_emissions(YEARS, SCENARIOS).emissions_tCO2.sum(), 4000)

    def test_schema_identifiers_duplicate_production_and_missing_year(self):
        frame = pd.DataFrame(steel_rows())
        with self.assertRaises(ValueError):
            ProcessEmissionCalculator(config_df=frame.drop(columns='units'))
        for field in ['metric_1', 'metric_2', 'metric_3', 'year', 'scenario', 'units', 'Egypt']:
            bad = frame.copy()
            bad.loc[0, field] = None
            with self.subTest(field=field), self.assertRaises(ValueError):
                ProcessEmissionCalculator(config_df=bad).calculate_steel_emissions(YEARS, SCENARIOS)
        with self.assertRaises(ValueError):
            calc(steel_rows() + [steel_rows()[0]]).calculate_steel_emissions(YEARS, SCENARIOS)
        with self.assertRaises(ValueError):
            calc(steel_rows()).calculate_steel_emissions([2030, 2035], SCENARIOS)

    def test_summary_missing_leaf_never_skipna_to_false_total(self):
        detailed = calc(chemical_rows() + aluminium_rows()).calculate_all_emissions(YEARS, SCENARIOS)
        summary = summarize_process_emissions(detailed)
        self.assertTrue(summary.emissions_tCO2.isna().all())
        self.assertEqual(set(summary.readiness), {'blocked'})
        with self.assertRaises(ValueError):
            require_accepted_process_emissions(summary, allow_provisional=True)

    def test_gate_provisional_optin_finite_only_and_readback_false(self):
        summary = summarize_process_emissions(calc(steel_rows()).calculate_all_emissions(YEARS, SCENARIOS))
        summary['ready_for_export'] = 'False'
        with self.assertRaises(ValueError):
            require_accepted_process_emissions(summary)
        require_accepted_process_emissions(summary, allow_provisional=True)
        summary['readiness'] = 'accepted'
        summary['ready_for_export'] = True
        summary['blockers'] = '[]'
        require_accepted_process_emissions(summary)
        summary['gas_basis'] = 'CO2e'
        with self.assertRaises(ValueError):
            require_accepted_process_emissions(summary, allow_provisional=True)

    def test_reports_temp_readback_and_json_provenance(self):
        rows = steel_rows() + cement_rows() + chemical_rows() + aluminium_rows()
        with tempfile.TemporaryDirectory() as temp:
            paths = generate_process_emissions_reports(pd.DataFrame(rows), Path(temp), YEARS, SCENARIOS)
            self.assertEqual(set(paths), {'detailed', 'summary', 'readiness'})
            summary = pd.read_csv(paths['summary'])
            detailed = pd.read_csv(paths['detailed'])
            self.assertEqual(len(summary), 4)
            self.assertFalse(summary.ready_for_export.any())
            self.assertNotIn('carrier', detailed.columns)
            self.assertTrue({'country', 'scenario', 'year', 'sector', 'emissions_tCO2',
                             'emissions_MtCO2', 'readiness', 'ready_for_export', 'blockers'}.issubset(summary.columns))
            report = json.loads(paths['readiness'].read_text(encoding='utf-8'))
            self.assertFalse(report['ready_for_export'])
            self.assertIn('factor_provenance_missing', report['blockers'])
            self.assertIn('ammonia_source_missing', report['blockers'])
            self.assertTrue(all(factor['factor_provenance'] is None for factor in report['factors']))
            with self.assertRaises(ValueError):
                require_accepted_process_emissions(summary)

    def test_final_gate_before_writing_and_empty_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'must-not-exist'
            with self.assertRaises(ValueError):
                generate_process_emissions_reports(pd.DataFrame(steel_rows()), output,
                                                   YEARS, SCENARIOS, require_accepted=True)
            self.assertFalse(output.exists())
        with self.assertRaises(ValueError):
            require_accepted_process_emissions(pd.DataFrame())

    def test_cli_temp_review_and_final_refusal(self):
        with tempfile.TemporaryDirectory() as temp:
            config_path = Path(temp) / 'config.csv'
            # CLI default horizons use the fixture repeated over the real dimensions.
            rows = []
            for year in [2030, 2035, 2040, 2045, 2050]:
                for scenario in ['BAU', 'Progressive', 'Optimistic']:
                    for item in steel_rows():
                        item.update(year=year, scenario=scenario)
                        rows.append(item)
            pd.DataFrame(rows).to_csv(config_path, index=False)
            command = [sys.executable, '-B', '-m', 'industry.scripts.calculate_process_emissions',
                       '--config', str(config_path), '--output-dir', str(Path(temp) / 'review')]
            result = subprocess.run(command, cwd=Path(__file__).resolve().parents[1],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((Path(temp) / 'review' / 'process_emissions_readiness.json').exists())
            command[-1] = str(Path(temp) / 'final')
            result = subprocess.run(command + ['--require-accepted'],
                                    cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((Path(temp) / 'final').exists())

    def test_gate_rejects_inconsistent_units_and_malformed_metadata(self):
        original = summarize_process_emissions(calc(steel_rows()).calculate_all_emissions(YEARS, SCENARIOS))
        for field, value in [('emissions_MtCO2', 152000), ('readiness', 'unknown'),
                             ('ready_for_export', 'unknown'), ('blockers', '{}')]:
            summary = original.copy()
            summary[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                require_accepted_process_emissions(summary, allow_provisional=True)

    def test_missing_route_dimension_not_silently_ignored(self):
        rows = steel_rows()
        rows[3]['metric_4'] = 'unknown'
        with self.assertRaises(ValueError):
            calc(rows).calculate_steel_emissions(YEARS, SCENARIOS)

    def test_all_configured_horizons_scenarios_and_countries(self):
        rows = []
        years = [2020, 2030, 2035, 2040, 2045, 2050]
        scenarios = ['BAU', 'Progressive', 'Optimistic']
        for year in years:
            for scenario in scenarios:
                for item in steel_rows():
                    item.update(year=year, scenario=scenario, Morocco=item['Egypt'])
                    rows.append(item)
        result = calc(rows).calculate_all_emissions(years, scenarios)
        summary = summarize_process_emissions(result)
        self.assertEqual(len(result), 2 * 6 * 3 * 3)
        self.assertEqual(len(summary), 2 * 6 * 3)
        self.assertEqual(set(summary.country), {'Egypt', 'Morocco'})
        self.assertTrue(all(math.isclose(value, 152000) for value in summary.emissions_tCO2))

    def test_real_producer_schema_builders_no_outputs(self):
        from industry.scripts.iron_and_steel.generate_steel_config import build_steel_production_rows
        from industry.scripts.chemical_and_petrochemical.HVC.generate_hvc_config import build_hvc_route_share_rows
        from industry.scripts.non_metallic_minerals.generate_cement_config import build_clinker_ratio_rows
        production = build_steel_production_rows(
            pd.DataFrame({'Country': ['Egypt'], '2020': [1e6]}),
            {'Egypt': {'BAU': 0}}, ['Egypt'], 2020, YEARS, SCENARIOS)
        self.assertEqual(set(production.units), {'t/year'})
        production['units'] = 't/a'  # Same values, real orchestrator normalization.
        production = production[production.year == 2030]
        self.assertAlmostEqual(ProcessEmissionCalculator(config_df=pd.concat(
            [production, pd.DataFrame(steel_rows()[1:])], ignore_index=True)
        ).calculate_steel_emissions(YEARS, SCENARIOS).emissions_tCO2.sum(), 152000)
        hvc_routes = build_hvc_route_share_rows(['Egypt'], 2020, YEARS, SCENARIOS)
        hvc = pd.concat([pd.DataFrame(chemical_rows()[:1]), hvc_routes], ignore_index=True)
        self.assertAlmostEqual(ProcessEmissionCalculator(config_df=hvc).calculate_hvc_emissions(
            YEARS, SCENARIOS).emissions_tCO2.sum(), 187500)
        ratios = build_clinker_ratio_rows(['Egypt'], 2020, YEARS, SCENARIOS)
        cement = pd.concat([pd.DataFrame(cement_rows()[:1]), ratios], ignore_index=True)
        self.assertAlmostEqual(ProcessEmissionCalculator(config_df=cement).calculate_cement_emissions(
            YEARS, SCENARIOS).emissions_tCO2.sum(), 2e6 * .71 * .54)


if __name__ == '__main__':
    unittest.main()