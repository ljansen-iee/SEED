"""Unit-aware process CO2 review reports, separate from energy carriers.

Retained factors are provisional, not validated JRC-IDEES values. Unknown data
raise; unresolved ammonia/aluminium factors produce missing CO2, never zero.
See ``require_accepted_process_emissions`` for the downstream acceptance gate.
"""

import argparse
import json
import math
from pathlib import Path
from typing import Optional

import pandas as pd

from industry.utils.process_emission_factors import (
    get_emission_factor_metadata,
    normalize_route_name,
    resolve_factor_key,
)


DEFAULT_YEARS = (2030, 2035, 2040, 2045, 2050)
DEFAULT_SCENARIOS = ('BAU', 'Progressive', 'Optimistic')
DIMENSIONS = ['country', 'scenario', 'year', 'sector']
CONFIG_COLUMNS = ['metric_1', 'metric_2', 'metric_3', 'metric_4',
                  'year', 'scenario', 'units']
DETAIL_COLUMNS = DIMENSIONS + [
    'product', 'route', 'factor_key', 'production_t', 'production_Mt',
    'production_basis', 'source_units', 'factor_tCO2_per_t',
    'emissions_tCO2', 'emissions_MtCO2', 'provisional_emissions_tCO2',
    'provisional_emissions_MtCO2', 'emissions_units', 'gas_basis',
    'factor_provenance', 'factor_version', 'factor_gas_basis',
    'factor_material_basis', 'factor_boundary', 'factor_status',
    'readiness', 'ready_for_export', 'blockers',
]
SUMMARY_COLUMNS = DIMENSIONS + [
    'emissions_tCO2', 'emissions_MtCO2', 'provisional_emissions_tCO2',
    'provisional_emissions_MtCO2', 'emissions_units', 'gas_basis',
    'readiness', 'ready_for_export', 'blockers',
]

# Explicit aliases only: no substring/default routing for an unknown technology.
HVC_FACTORS_BY_ROUTE = {
    'Naphtha cracking': 'HVC_primary', 'LPG cracking': 'HVC_primary',
    'MTO': 'HVC_feedstock', 'Methanol to olefins': 'HVC_feedstock',
    'HVC_primary': 'HVC_primary', 'HVC_feedstock': 'HVC_feedstock',
    'HVC_mechanical_recycling': 'HVC_mechanical_recycling',
    'HVC_chemical_recycling': 'HVC_chemical_recycling',
}
HVC_ROUTES = {normalize_route_name(name): key for name, key in HVC_FACTORS_BY_ROUTE.items()}
AMMONIA_ROUTES = {
    normalize_route_name(name): key for name, key in {
        'smr+hb': 'ammonia_SMR', 'ammonia_SMR': 'ammonia_SMR',
        'e+hb': 'ammonia_green', 'renewable synthesis': 'ammonia_green',
        'ammonia_green': 'ammonia_green',
    }.items()
}
STEEL_ROUTES = {
    normalize_route_name(name): key for name, key in {
        'primary steel production': 'primary', 'secondary steel production': 'secondary',
        'bf+bof': 'BF+BOF', 'dr+eaf': 'DR+EAF',
        'dr+eaf+h2': 'DR+EAF+H2', 'dr+eaf (h2)': 'DR+EAF+H2',
        'dr+eaf hydrogen': 'DR+EAF+H2',
        'dr+eaf+ng': 'DR+EAF+NG', 'dr+eaf (ng)': 'DR+EAF+NG',
        'dr+eaf natural gas': 'DR+EAF+NG',
    }.items()
}


def _number(value, label: str) -> float:
    value = pd.to_numeric(value, errors='coerce')
    if pd.isna(value) or not math.isfinite(float(value)) or float(value) < 0:
        raise ValueError(f"Missing, non-finite or negative {label}: {value!r}")
    return float(value)


def production_to_tonnes(value, units: str) -> float:
    """Convert declared production units; standardized t/a is NOT 100t/a."""
    scale = {'t/a': 1, 't/year': 1, 'tonnes': 1, 'tonnes/year': 1,
             '100t/a': 100, '100t/year': 100, 'mt/a': 1e6, 'mt/year': 1e6}
    unit = str(units).strip().casefold()
    if unit not in scale:
        raise ValueError(f"Unsupported production unit: {units!r}")
    tonnes = _number(value, 'production') * scale[unit]
    if not math.isfinite(tonnes):
        raise ValueError('Production conversion overflow')
    return tonnes


def _share(row: pd.Series, country: str) -> float:
    unit = str(row['units']).strip().casefold()
    value = _number(row[country], f"share {row['metric_3']}/{country}")
    if unit in {'%', 'percent', 'percentage'}:
        value /= 100
    elif unit not in {'share', 'fraction'}:
        raise ValueError(f"Unsupported share unit: {unit!r}")
    if value > 1:
        raise ValueError(f"Share outside [0, 1]: {row['metric_3']}/{country}={value}")
    return value


def _conserve(shares: dict, expected: set, label: str) -> None:
    if set(shares) != expected:
        raise ValueError(f"Missing/extra {label} routes: expected {sorted(expected)}, got {sorted(shares)}")
    if not math.isclose(sum(shares.values()), 1, rel_tol=0, abs_tol=1e-6):
        raise ValueError(f"{label} shares must sum to 1, got {sum(shares.values())}")


class ProcessEmissionCalculator:
    """Calculate route arithmetic with explicit provenance/acceptance blockers."""

    def __init__(self, config_path: Optional[Path] = None,
                 config_df: Optional[pd.DataFrame] = None):
        if config_df is None:
            config_path = (Path(config_path) if config_path is not None else
                           Path(__file__).resolve().parents[1] / 'output_data' /
                           'CONFIG' / 'INDUSTRY_CONFIG.csv')
            config_df = pd.read_csv(config_path)
        missing = set(CONFIG_COLUMNS).difference(config_df.columns)
        if missing:
            raise ValueError(f"Missing config columns: {sorted(missing)}")
        if config_df.columns.duplicated().any():
            raise ValueError('Duplicate config columns')
        self.config = config_df.copy()
        self.countries = [c for c in self.config.columns if c not in CONFIG_COLUMNS]
        if not self.countries or any(not str(c).strip() for c in self.countries):
            raise ValueError('Config must contain named country columns')
        for column in ['metric_1', 'metric_2', 'metric_3', 'year', 'scenario', 'units']:
            if self.config[column].isna().any() or self.config[column].astype(str).str.strip().eq('').any():
                raise ValueError(f"Missing config identifier: {column}")
        for column in ['metric_1', 'metric_2', 'metric_3']:
            self.config[column] = self.config[column].astype(str).str.strip().str.casefold()
        self.config['metric_4'] = self.config['metric_4'].fillna('').astype(str).str.strip().str.casefold()
        self.config['year'] = self.config['year'].astype(str).str.strip()
        # CAGR rows contain period identifiers; only activity/route years must be integers.
        annual = self.config['metric_2'].isin(['production', 'technology_route'])
        years = pd.to_numeric(self.config.loc[annual, 'year'], errors='coerce')
        if years.isna().any() or (~years.map(math.isfinite)).any() or (years % 1 != 0).any():
            raise ValueError('Production and route years must be integer years')
        self.config.loc[annual, 'year'] = years.astype(int).astype(str)

    def _rows(self, sector, kind, metric=None, year=None, scenario=None):
        mask = ((self.config['metric_1'] == str(sector).strip().casefold()) &
                (self.config['metric_2'] == kind))
        if metric is not None:
            mask &= self.config['metric_3'] == str(metric).strip().casefold()
        if year is not None:
            mask &= self.config['year'] == str(year)
        if scenario is not None:
            mask &= self.config['scenario'] == scenario
        return self.config.loc[mask]

    def _production_rows(self, sector, metric, years, scenarios):
        rows = self._rows(sector, 'production', metric)
        if rows.empty:
            return rows
        selected = rows[rows['year'].isin([str(y) for y in years]) &
                        rows['scenario'].isin(scenarios)]
        if selected.duplicated(['year', 'scenario']).any():
            raise ValueError(f"Duplicate production rows for {sector}/{metric}")
        expected = {(str(y), s) for y in years for s in scenarios}
        actual = set(zip(selected['year'], selected['scenario']))
        if expected != actual:
            raise ValueError(f"Missing production dimensions for {metric}: {sorted(expected - actual)}")
        return selected

    def _one(self, sector, kind, metric, year, scenario, required=True):
        rows = self._rows(sector, kind, metric, year, scenario)
        if len(rows) > 1:
            raise ValueError(f"Duplicate {metric} for {scenario}/{year}")
        if rows.empty:
            if required:
                raise ValueError(f"Missing {metric} for {scenario}/{year}")
            return None
        return rows.iloc[0]

    def _route_shares(self, sector, year, scenario, country, mapping, excluded=None):
        shares = {}
        for _, row in self._rows(sector, 'technology_route', year=year, scenario=scenario).iterrows():
            name = normalize_route_name(row['metric_3'])
            if excluded and name in excluded:
                continue
            # Optional DR subroute dimension is within DR+EAF, not total steel.
            if sector == 'iron and steel' and name == normalize_route_name('dr+eaf') and row['metric_4']:
                fuels = {'h2': 'DR+EAF+H2', 'hydrogen': 'DR+EAF+H2',
                         'ng': 'DR+EAF+NG', 'natural gas': 'DR+EAF+NG'}
                route = fuels.get(row['metric_4'])
            else:
                if row['metric_4']:
                    raise ValueError(f"Unexpected route sub-dimension: {row['metric_3']}/{row['metric_4']}")
                route = mapping.get(name)
            if route is None:
                raise ValueError(f"Unknown {sector} route: {row['metric_3']!r}/{row['metric_4']!r}")
            if route in shares:
                raise ValueError(f"Duplicate route {route} for {country}/{scenario}/{year}")
            shares[route] = _share(row, country)
        return shares

    @staticmethod
    def _record(prod, country, product, route, factor_key, tonnes, basis, extra_blockers=()):
        sector = prod['metric_1']
        metadata = get_emission_factor_metadata(sector, factor_key)
        arithmetic = tonnes * metadata['retained_factor']
        if not math.isfinite(arithmetic):
            raise ValueError(f"Emissions multiplication overflow for {sector}/{route}")
        blockers = sorted(set(metadata['factor_blockers']).union(extra_blockers))
        emissions = arithmetic if metadata['usable_for_provisional_co2'] else float('nan')
        return {
            'country': country, 'scenario': prod['scenario'], 'year': int(prod['year']),
            'sector': sector, 'product': product, 'route': route, 'factor_key': metadata['factor_key'],
            'production_t': tonnes, 'production_Mt': tonnes / 1e6,
            'production_basis': basis, 'source_units': prod['units'],
            'factor_tCO2_per_t': metadata['retained_factor'],
            'emissions_tCO2': emissions, 'emissions_MtCO2': emissions / 1e6,
            'provisional_emissions_tCO2': arithmetic,
            'provisional_emissions_MtCO2': arithmetic / 1e6,
            'emissions_units': 'tCO2/a', 'gas_basis': 'CO2',
            **{key: metadata[key] for key in ['factor_provenance', 'factor_version',
               'factor_gas_basis', 'factor_material_basis', 'factor_boundary', 'factor_status']},
            'readiness': 'blocked' if pd.isna(emissions) else 'provisional',
            'ready_for_export': False, 'blockers': json.dumps(blockers),
        }

    def calculate_steel_emissions(self, years, scenarios):
        records = []
        sector = 'iron and steel'
        for _, prod in self._production_rows(sector, 'steel production per year', years, scenarios).iterrows():
            for country in self.countries:
                total = production_to_tonnes(prod[country], prod['units'])
                shares = self._route_shares(sector, prod['year'], prod['scenario'], country, STEEL_ROUTES)
                _conserve({k: v for k, v in shares.items() if k in {'primary', 'secondary'}},
                          {'primary', 'secondary'}, 'primary/secondary steel')
                _conserve({k: v for k, v in shares.items() if k in {'BF+BOF', 'DR+EAF'}},
                          {'BF+BOF', 'DR+EAF'}, 'within-primary steel')
                leaves = {'BF+BOF': shares['primary'] * shares['BF+BOF'],
                          'EAF': shares['secondary']}
                children = {k: v for k, v in shares.items() if k.startswith('DR+EAF+')}
                if children:
                    _conserve(children, {'DR+EAF+H2', 'DR+EAF+NG'}, 'within-DR+EAF steel')
                    leaves.update({k: shares['primary'] * shares['DR+EAF'] * v
                                   for k, v in children.items()})
                else:
                    leaves['DR+EAF'] = shares['primary'] * shares['DR+EAF']
                _conserve(leaves, set(leaves), 'leaf steel')
                for route, share in leaves.items():
                    factor = 'DR+EAF' if route.startswith('DR+EAF') else route
                    records.append(self._record(prod, country, 'steel', route, factor,
                                                total * share, 'steel'))
        return pd.DataFrame(records, columns=DETAIL_COLUMNS)

    def calculate_cement_emissions(self, years, scenarios):
        records = []
        sector = 'non-metallic minerals'
        cement = self._production_rows(sector, 'cement production per year', years, scenarios)
        clinker = self._production_rows(sector, 'clinker production per year', years, scenarios)
        # Direct clinker and derived clinker must agree; emit only once.
        source = clinker if not clinker.empty else cement
        for _, prod in source.iterrows():
            year, scenario = prod['year'], prod['scenario']
            cement_row = self._one(sector, 'production', 'cement production per year', year, scenario, False)
            ratio = self._one(sector, 'technology_route', 'clinker ratio', year, scenario,
                              required=clinker.empty)
            for country in self.countries:
                tonnes = production_to_tonnes(prod[country], prod['units'])
                ratio_value = _share(ratio, country) if ratio is not None else None
                if clinker.empty:
                    tonnes *= ratio_value
                elif cement_row is not None and ratio_value is not None:
                    derived = production_to_tonnes(cement_row[country], cement_row['units']) * ratio_value
                    if not math.isclose(tonnes, derived, rel_tol=1e-6, abs_tol=1e-6):
                        raise ValueError(f"Clinker production disagrees with cement × ratio for {country}/{scenario}/{year}")
                records.append(self._record(prod, country, 'clinker', 'Cement', 'Cement', tonnes, 'clinker'))
        return pd.DataFrame(records, columns=DETAIL_COLUMNS)

    def _calculate_split_product(self, product, sector, mapping, expected, years, scenarios, excluded=None):
        records = []
        for _, prod in self._production_rows(sector, f'{product} production per year', years, scenarios).iterrows():
            for country in self.countries:
                total = production_to_tonnes(prod[country], prod['units'])
                shares = self._route_shares(sector, prod['year'], prod['scenario'], country, mapping, excluded)
                _conserve(shares, expected, product)
                if not shares:
                    raise ValueError(f"Missing {product} route shares")
                for route, share in shares.items():
                    records.append(self._record(prod, country, product, route, route, total * share, product))
        return pd.DataFrame(records, columns=DETAIL_COLUMNS)

    def calculate_hvc_emissions(self, years, scenarios):
        # Keep producer route labels separate even when factors are shared.
        mapping = {normalize_route_name(name): name for name in HVC_FACTORS_BY_ROUTE}
        excluded = set(AMMONIA_ROUTES) | {normalize_route_name('import reallocation')}
        records = []
        sector = 'chemical and petrochemical'
        for _, prod in self._production_rows(sector, 'hvc production per year', years, scenarios).iterrows():
            for country in self.countries:
                total = production_to_tonnes(prod[country], prod['units'])
                shares = self._route_shares(sector, prod['year'], prod['scenario'], country, mapping, excluded)
                _conserve(shares, set(shares), 'HVC')
                if not shares:
                    raise ValueError('Missing HVC route shares')
                for route, share in shares.items():
                    records.append(self._record(prod, country, 'HVC', route,
                                                HVC_FACTORS_BY_ROUTE[route], total * share, 'HVC'))
        return pd.DataFrame(records, columns=DETAIL_COLUMNS)

    def calculate_ammonia_emissions(self, years, scenarios):
        records = []
        sector = 'chemical and petrochemical'
        excluded = set(HVC_ROUTES) | {normalize_route_name('import reallocation')}
        for _, prod in self._production_rows(sector, 'ammonia production per year', years, scenarios).iterrows():
            year, scenario = prod['year'], prod['scenario']
            reallocated = self._one(sector, 'production', 'ammonia import reallocated volume per year', year, scenario, False)
            imports = self._one(sector, 'production', 'ammonia import volumes per year', year, scenario, False)
            realloc_share = self._one(sector, 'technology_route', 'import reallocation', year, scenario, False)
            for country in self.countries:
                local = production_to_tonnes(prod[country], prod['units'])
                shares = self._route_shares(sector, year, scenario, country, AMMONIA_ROUTES, excluded)
                _conserve(shares, {'ammonia_SMR', 'ammonia_green'}, 'ammonia local')
                extra = production_to_tonnes(reallocated[country], reallocated['units']) if reallocated is not None else 0
                if imports is not None:
                    imported = production_to_tonnes(imports[country], imports['units'])
                    if realloc_share is None:
                        raise ValueError('Ammonia imports require an explicit import reallocation share')
                    derived = imported * _share(realloc_share, country)
                    if reallocated is not None and not math.isclose(extra, derived, rel_tol=1e-6, abs_tol=1e-6):
                        raise ValueError('Ammonia reallocated volume disagrees with imports × share')
                    extra = derived
                elif realloc_share is not None and reallocated is None:
                    raise ValueError('Ammonia import reallocation requires import production data')
                for route, share in shares.items():
                    tonnes = local * share + (extra if route == 'ammonia_green' else 0)
                    records.append(self._record(prod, country, 'ammonia',
                                                'SMR+HB' if route == 'ammonia_SMR' else 'E+HB',
                                                route, tonnes, 'ammonia'))
        return pd.DataFrame(records, columns=DETAIL_COLUMNS)

    def calculate_aluminium_emissions(self, years, scenarios):
        mapping = {normalize_route_name(name): key for name, key in {
            'primary aluminium': 'Aluminium_primary', 'Aluminium_primary': 'Aluminium_primary',
            'secondary aluminium': 'Aluminium_secondary', 'Aluminium_secondary': 'Aluminium_secondary',
        }.items()}
        return self._calculate_split_product('aluminium', 'non-ferrous metals', mapping,
                                            {'Aluminium_primary', 'Aluminium_secondary'}, years, scenarios)

    def calculate_generic_sector_emissions(self, sector_name, production_metric, route_name, years, scenarios):
        sector, route = resolve_factor_key(sector_name, route_name)
        # Do not allow a generic call to bypass the clinker/route accounting boundary.
        basis = get_emission_factor_metadata(sector, route)['factor_material_basis']
        if basis == 'clinker' and str(production_metric).strip().casefold() != 'clinker production per year':
            raise ValueError('Cement factor requires clinker production; use calculate_cement_emissions')
        records = []
        for _, prod in self._production_rows(sector, production_metric, years, scenarios).iterrows():
            for country in self.countries:
                tonnes = production_to_tonnes(prod[country], prod['units'])
                records.append(self._record(prod, country, basis, route, route, tonnes, basis))
        return pd.DataFrame(records, columns=DETAIL_COLUMNS)

    def calculate_paper_emissions(self, years, scenarios):
        return pd.concat([self.calculate_generic_sector_emissions(
            'paper, pulp and printing', f'{product} production per year', product,
            years, scenarios) for product in ['Pulp', 'Paper']], ignore_index=True)

    def calculate_all_emissions(self, years=DEFAULT_YEARS, scenarios=DEFAULT_SCENARIOS):
        frames = [calculate(years, scenarios) for calculate in [
            self.calculate_steel_emissions, self.calculate_cement_emissions,
            self.calculate_hvc_emissions, self.calculate_ammonia_emissions,
            self.calculate_paper_emissions, self.calculate_aluminium_emissions,
        ]]
        frames = [frame for frame in frames if not frame.empty]
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=DETAIL_COLUMNS)


def summarize_process_emissions(emissions_df: pd.DataFrame) -> pd.DataFrame:
    """Sector summary; any missing leaf makes the entire sector CO2 total missing."""
    records = []
    for keys, group in emissions_df.groupby(DIMENSIONS, sort=True, dropna=False):
        blockers = sorted({b for value in group['blockers'] for b in json.loads(value)})
        emissions = group['emissions_tCO2'].sum(min_count=len(group))
        provisional = group['provisional_emissions_tCO2'].sum(min_count=len(group))
        ready = bool(group['ready_for_export'].map(
            lambda value: str(value).strip().casefold() == 'true').all()) and not blockers and pd.notna(emissions)
        records.append({
            **dict(zip(DIMENSIONS, keys)), 'emissions_tCO2': emissions,
            'emissions_MtCO2': emissions / 1e6,
            'provisional_emissions_tCO2': provisional,
            'provisional_emissions_MtCO2': provisional / 1e6,
            'emissions_units': 'tCO2/a', 'gas_basis': 'CO2',
            'readiness': 'accepted' if ready else ('blocked' if pd.isna(emissions) else 'provisional'),
            'ready_for_export': ready, 'blockers': json.dumps(blockers),
        })
    return pd.DataFrame(records, columns=SUMMARY_COLUMNS)


def require_accepted_process_emissions(summary: pd.DataFrame, *, allow_provisional: bool = False) -> None:
    """Downstream export gate. Provisional opt-in is REVIEW ONLY, not acceptance.

    Opt-in never fills missing CO2 with retained placeholders or reinterprets
    aluminium CO2e/PFCs as CO2. Call on the exact scenario/year being exported.
    """
    missing = set(SUMMARY_COLUMNS).difference(summary.columns)
    if missing or summary.empty:
        raise ValueError(f"Missing emissions/readiness contract: {sorted(missing)}; rows={len(summary)}")
    if summary[DIMENSIONS].isna().any().any() or summary.duplicated(DIMENSIONS).any():
        raise ValueError('Missing or duplicate process-emission dimensions')
    if not summary['emissions_units'].eq('tCO2/a').all() or not summary['gas_basis'].eq('CO2').all():
        raise ValueError('Process emissions must be CO2 only in tCO2/a')
    numeric = pd.to_numeric(summary['emissions_tCO2'], errors='coerce')
    if numeric.isna().any() or (~numeric.map(math.isfinite)).any() or (numeric < 0).any():
        raise ValueError('Missing/invalid CO2: resolve ammonia/aluminium/data blockers before export')
    megatonnes = pd.to_numeric(summary['emissions_MtCO2'], errors='coerce')
    if any(not math.isclose(t / 1e6, mt, rel_tol=1e-9, abs_tol=1e-12)
           for t, mt in zip(numeric, megatonnes)):
        raise ValueError('Inconsistent emissions_tCO2 and emissions_MtCO2 units')
    # CSV read-back can return strings; never bool("False").
    if not summary['ready_for_export'].map(lambda v: str(v).strip().casefold() in {'true', 'false'}).all():
        raise ValueError('Invalid ready_for_export flags')
    if not summary['readiness'].isin(['accepted', 'provisional', 'blocked']).all():
        raise ValueError('Unknown emissions readiness status')
    ready = summary['ready_for_export'].map(lambda v: str(v).strip().casefold() == 'true')
    blockers = summary['blockers'].map(json.loads)
    if not blockers.map(lambda values: isinstance(values, list) and
                        all(isinstance(value, str) and value for value in values)).all():
        raise ValueError('Blockers must be JSON arrays of nonempty blocker identifiers')
    if not allow_provisional and (not ready.all() or not summary['readiness'].eq('accepted').all() or blockers.map(bool).any()):
        raise ValueError('Process emissions are provisional/blocked; review factor provenance, version, gas basis and boundary')


def generate_process_emissions_reports(df_config: pd.DataFrame, output_dir: Path,
                                      years=DEFAULT_YEARS, scenarios=DEFAULT_SCENARIOS,
                                      *, require_accepted: bool = False,
                                      allow_provisional: bool = False) -> dict:
    """Write review CSVs plus JSON readiness; existing detailed/summary keys retained.

    ``require_accepted=True`` gates final use BEFORE writing. Default reports are
    explicitly provisional and remain useful when physical CO2 is blocked.
    """
    calc = ProcessEmissionCalculator(config_df=df_config)
    detailed = calc.calculate_all_emissions(years, scenarios)
    summary = summarize_process_emissions(detailed)
    if require_accepted:
        require_accepted_process_emissions(summary, allow_provisional=allow_provisional)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {'detailed': output_dir / 'process_emissions.csv',
             'summary': output_dir / 'process_emissions_summary.csv',
             'readiness': output_dir / 'process_emissions_readiness.json'}
    detailed.to_csv(paths['detailed'], index=False)
    summary.to_csv(paths['summary'], index=False)
    used_factors = detailed[['sector', 'factor_key']].drop_duplicates()
    blockers = sorted({b for value in summary['blockers'] for b in json.loads(value)})
    if summary.empty:
        blockers.append('no_supported_production_data')
    report = {
        'schema_version': 'process-co2-review-v1', 'gas_basis': 'CO2',
        'emissions_units': 'tCO2/a', 'ready_for_export': False,
        'readiness': 'blocked' if summary.empty or summary['emissions_tCO2'].isna().any() else 'provisional',
        'blockers': blockers, 'summary_rows': len(summary), 'detailed_rows': len(detailed),
        'scope': 'configured steel, clinker, HVC, ammonia, pulp, paper, aluminium; not an all-industry inventory',
        'requested_years': list(years), 'requested_scenarios': list(scenarios),
        'configured_products': sorted(detailed['product'].unique().tolist()),
        'factors': [get_emission_factor_metadata(row['sector'], row['factor_key'])
                    for _, row in used_factors.iterrows()],
    }
    paths['readiness'].write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True,
                        help='Explicit review output directory (no implicit source outputs)')
    parser.add_argument('--require-accepted', action='store_true')
    parser.add_argument('--allow-provisional', action='store_true', help='Review only; never fills missing CO2')
    args = parser.parse_args()
    calc = ProcessEmissionCalculator(config_path=args.config)
    paths = generate_process_emissions_reports(calc.config, args.output_dir,
                                              require_accepted=args.require_accepted,
                                              allow_provisional=args.allow_provisional)
    print(f"Provisional process-emission reports: {paths}; consult readiness JSON before export.")


if __name__ == '__main__':
    main()
