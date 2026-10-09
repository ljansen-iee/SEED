"""
generate_aluminium_config.py
-----------------------------
Generate configuration rows for aluminium subsector in INDUSTRY_CONFIG.csv.

This script integrates all aluminium-specific data:
1. Production volumes (from BGS historical data + CAGR projections)
2. Technology route shares (Primary vs Secondary)
3. Energy intensities (fuel-indexed base assumptions)
4. Fuel shares (from UNSD or defaults)
5. Process emissions factors (Primary: 1.5 tCO₂/t, Secondary: 0.0)

Configuration Structure
~~~~~~~~~~~~~~~~~~~~~~~
metric_1: 'non-ferrous metals' (sector level)
metric_2: 'production', 'technology_route', 'energy_intensity', 'fuel_share', 'unspecified'
metric_3: Specific metric (e.g., 'Aluminium production per year', 'Primary aluminium', etc.)
metric_4: Sub-metric (e.g., fuel type for fuel_share rows)

Output
~~~~~~
Rows added to INDUSTRY_CONFIG.csv for aluminium subsector:
- Production [100 tonnes/year]
- Technology routes [share 0-1]
- Energy intensities [MWh/t] (base rows)
- Fuel shares [share 0-1]
- Unspecified other non-ferrous [GWh] (residual from UNSD)

Author: Automated workflow
Date: June 2026
"""

from __future__ import annotations

from pathlib import Path
from typing import List
import pandas as pd

# Import aluminium-specific functions
from industry.scripts.non_ferrous_metals.build_aluminium_production import (
    load_aluminium_data,
    get_base_production,
    calculate_cagr_factor,
    CAGR_RATES,
    PROJECTION_YEARS,
    BASE_YEAR,
)
from industry.scripts.non_ferrous_metals.build_aluminium_shares import (
    get_aluminium_route_shares,
)
from industry.scripts.non_ferrous_metals.build_aluminium_intensities import (
    intensity_primary_aluminium,
    intensity_secondary_aluminium,
    get_aluminium_fuel_shares,
)

# Import shared utilities
from industry.utils.helpers import (
    get_scenarios,
    country_to_iso2,
    build_intensity_base_rows,
)

# Get scenarios from config
SCENARIOS = get_scenarios()

# Paths
_SCRIPT_DIR = Path(__file__).parent
_INDUSTRY_ROOT = _SCRIPT_DIR.parent.parent  # scripts/non_ferrous_metals/ -> scripts/ -> industry/
AL_PRODUCTION_CSV = (_INDUSTRY_ROOT / "input_data" / "non_ferrous_metals" / "AL_production.csv").resolve()

# ---------------------------------------------------------------------------
# Production Rows
# ---------------------------------------------------------------------------

def build_aluminium_production_rows(countries: List[str], target_years: List[int], scenarios=None, base_year=2020) -> pd.DataFrame:
    """
    Build production rows for aluminium.
    
    Returns DataFrame with columns:
    metric_1, metric_2, metric_3, metric_4, year, scenario, units, [country columns]
    """
    # Load historical data
    df_hist = load_aluminium_data(AL_PRODUCTION_CSV)
    
    rows = []
    
    scenarios = SCENARIOS if scenarios is None else scenarios
    all_years = [base_year] + target_years

    for scenario in scenarios:
        for year in all_years:
            row: dict[str, object] = {
                'metric_1': 'non-ferrous metals',
                'metric_2': 'production',
                'metric_3': 'Aluminium production per year',
                'metric_4': '',
                'year': str(year),
                'scenario': scenario,
                'units': '100t/a',
            }
            
            # Add country data
            for country in countries:
                # Convert country name to ISO code for data lookup
                # AL_production.csv uses ISO codes (e.g., 'EG', 'ZA')
                # but INDUSTRY_CONFIG uses full names (e.g., 'Egypt', 'South Africa')
                country_code = country_to_iso2(country)
                
                if not country_code:
                    # No ISO code mapping available
                    row[country] = 0.0
                    continue
                
                base_production, actual_base_year = get_base_production(df_hist, country_code, base_year)
                
                if base_production == 0:
                    row[country] = 0.0
                    continue
                
                # Keep the base year anchored to the historical observation.
                if year == base_year:
                    row[country] = round(base_production * 10, 2)
                    continue

                # Calculate CAGR factor
                cagr_factor, _ = calculate_cagr_factor(actual_base_year, year, scenario)
                
                # Project production (ktonnes)
                projected_ktonnes = base_production * cagr_factor
                
                # Convert to 100 tonnes (config unit)
                projected_100t = projected_ktonnes * 10  # 1 ktonne = 10 × 100 tonnes
                
                row[country] = round(projected_100t, 2)
            
            rows.append(row)
    
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Technology Route Share Rows
# ---------------------------------------------------------------------------

def build_aluminium_route_rows(countries: List[str], target_years: List[int], scenarios=None, base_year=2020) -> pd.DataFrame:
    """Build technology route share rows (Primary vs Secondary)."""
    scenarios = SCENARIOS if scenarios is None else scenarios
    all_years = [base_year] + target_years
    route_shares = get_aluminium_route_shares(all_years, scenarios)
    
    rows = []
    
    for route_name, year_scenario_shares in route_shares.items():
        for year in all_years:
            for scenario in scenarios:
                share = year_scenario_shares[year][scenario]
                
                row: dict[str, object] = {
                    'metric_1': 'non-ferrous metals',
                    'metric_2': 'technology_route',
                    'metric_3': route_name,
                    'metric_4': '',
                    'year': str(year),
                    'scenario': scenario,
                    'units': 'share',
                }
                
                # Same share for all countries (global average)
                for country in countries:
                    row[country] = round(share, 4)
                
                rows.append(row)
    
    return pd.DataFrame(rows)


def build_aluminium_cagr_rows(
    countries: List[str],
    base_year: int,
    target_years: List[int],
    scenarios: List[str],
) -> pd.DataFrame:
    """Build CAGR rows for aluminium production using exogenous interval rates."""
    rows = []
    all_years = [base_year] + target_years

    for i in range(len(all_years) - 1):
        start_year = all_years[i]
        end_year = all_years[i + 1]
        period = f"{start_year}-{end_year}"

        for scenario in scenarios:
            cagr_value = float(CAGR_RATES.get(scenario, {}).get(end_year, 0.0))
            row: dict[str, object] = {
                'metric_1': 'non-ferrous metals',
                'metric_2': 'cagr',
                'metric_3': 'Aluminium production per year',
                'metric_4': '',
                'year': period,
                'scenario': scenario,
                'units': 'share',
            }

            for country in countries:
                row[country] = cagr_value

            rows.append(row)

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Energy Intensity Rows
# ---------------------------------------------------------------------------

def build_aluminium_intensity_rows(
    countries: List[str],
    target_years: List[int],
    intensity_selection: str = 'average',
    scenarios=None,
    base_year=2020,
) -> pd.DataFrame:
    """
    Build energy intensity rows for each route.

    Aluminium intensities are generated via the shared fuel-indexed detailed
    sector pattern and collapsed to route-level base rows using
    build_intensity_base_rows.
    """
    if intensity_selection not in {'average', 'first_fuel'}:
        raise ValueError(
            f"Unsupported intensity_selection='{intensity_selection}'. "
            "Use 'average' or 'first_fuel'."
        )

    scenarios = SCENARIOS if scenarios is None else scenarios

    df_primary = build_intensity_base_rows(
        industry_sector='non-ferrous metals',
        intensity_function=intensity_primary_aluminium,
        metric_label='Primary aluminium',
        countries=countries,
        base_year=base_year,
        scenarios=scenarios,
        intensity_selection=intensity_selection,
    )

    df_secondary = build_intensity_base_rows(
        industry_sector='non-ferrous metals',
        intensity_function=intensity_secondary_aluminium,
        metric_label='Secondary aluminium',
        countries=countries,
        base_year=base_year,
        scenarios=scenarios,
        intensity_selection=intensity_selection,
    )

    return pd.concat([df_primary, df_secondary], ignore_index=True)


def build_aluminium_intensity_cagr_rows(
    countries: List[str],
    base_year: int,
    target_years: List[int],
    scenarios: List[str],
) -> pd.DataFrame:
    """Build CAGR rows for aluminium route intensities.

    Intensities are currently fixed at base value (11.24 MWh/t), so CAGR is 0.0.
    """
    rows = []
    all_years = [base_year] + target_years
    intensity_metrics = [
        'Energy intensity of Primary aluminium',
        'Energy intensity of Secondary aluminium',
    ]

    for i in range(len(all_years) - 1):
        period = f"{all_years[i]}-{all_years[i + 1]}"
        for metric_name in intensity_metrics:
            for scenario in scenarios:
                row: dict[str, object] = {
                    'metric_1': 'non-ferrous metals',
                    'metric_2': 'cagr',
                    'metric_3': metric_name,
                    'metric_4': '',
                    'year': period,
                    'scenario': scenario,
                    'units': 'share',
                }
                for country in countries:
                    row[country] = 0.0
                rows.append(row)

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Fuel Share Rows
# ---------------------------------------------------------------------------

def build_aluminium_fuel_share_rows(countries: List[str], target_years: List[int], scenarios=None, base_year=2020) -> pd.DataFrame:
    """Build fuel share rows for each route."""
    scenarios = SCENARIOS if scenarios is None else scenarios
    all_years = [base_year] + target_years
    fuel_shares = get_aluminium_fuel_shares(all_years, scenarios)
    fuel_universe = [
        'diesel',
        'natural_gas',
        'electricity',
        'coal',
        'heat',
        'biomass',
        'hydrogen',
        'ammonia',
        'methanol',
        'steel',
    ]
    
    rows = []
    
    # Iterate through routes
    for route_name, fuels_dict in fuel_shares.items():
        # Iterate through a fixed fuel universe so zero-share fuels are still exported.
        for fuel_name in fuel_universe:
            year_scenario_shares = fuels_dict.get(fuel_name, {})
            for year in all_years:
                for scenario in scenarios:
                    share = year_scenario_shares.get(year, {}).get(scenario, 0.0)
                    
                    row: dict[str, object] = {
                        'metric_1': 'non-ferrous metals',
                        'metric_2': 'fuel_share',
                        'metric_3': route_name,
                        'metric_4': fuel_name,
                        'year': str(year),
                        'scenario': scenario,
                        'units': 'share',
                    }
                    
                    # Same fuel share for all countries (can be customized per country later)
                    # TODO: Extract actual fuel shares from UNSD per country
                    for country in countries:
                        row[country] = round(share, 4)
                    
                    rows.append(row)
    
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Main Generation Function
# ---------------------------------------------------------------------------

def generate_aluminium_config(countries: List[str], base_year=2020, target_years=None, scenarios=None) -> pd.DataFrame:
    """
    Generate all aluminium configuration rows.
    
    Args:
        countries: List of country codes (e.g., ['CN', 'US', 'IN', ...])
    
    Returns:
        DataFrame with all aluminium config rows
    """
    target_years = PROJECTION_YEARS if target_years is None else target_years
    scenarios = SCENARIOS if scenarios is None else scenarios
    
    # Build all components
    df_production = build_aluminium_production_rows(countries, target_years, scenarios, base_year)
    df_cagr = build_aluminium_cagr_rows(countries, base_year, target_years, scenarios)
    df_routes = build_aluminium_route_rows(countries, target_years, scenarios, base_year)
    df_intensities = build_aluminium_intensity_rows(
        countries,
        target_years,
        intensity_selection='average',
        scenarios=scenarios,
        base_year=base_year,
    )
    df_intensity_cagr = build_aluminium_intensity_cagr_rows(
        countries,
        base_year,
        target_years,
        scenarios,
    )
    df_fuel_shares = build_aluminium_fuel_share_rows(countries, target_years, scenarios, base_year)
    
    # Combine all rows
    df_all = pd.concat([
        df_production,
        df_cagr,
        df_routes,
        df_intensities,
        df_intensity_cagr,
        df_fuel_shares,
    ], ignore_index=True)
    
    return df_all


# ---------------------------------------------------------------------------
# Main Execution (for testing)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Test with a small set of countries
    test_countries = ['CN', 'US', 'IN', 'RU', 'CA', 'AE', 'AU', 'NO', 'BH', 'IS']
    
    df_config = generate_aluminium_config(test_countries)
    
    # Display summary
    print("\nSample rows:")
    print(df_config.head(20))
    
    print("\nRow count by metric_2:")
    print(df_config.groupby('metric_2').size())
    
    # Save test output
    output_path = _INDUSTRY_ROOT / "output_data" / "CONFIG" / "test_aluminium_config.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_config.to_csv(output_path, index=False)
    
    print(f"\n✓ Test config saved to: {output_path}\n")
