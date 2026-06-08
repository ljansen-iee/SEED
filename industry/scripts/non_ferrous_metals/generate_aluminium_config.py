"""
generate_aluminium_config.py
-----------------------------
Generate configuration rows for aluminium subsector in INDUSTRY_CONFIG.csv.

This script integrates all aluminium-specific data:
1. Production volumes (from BGS historical data + CAGR projections)
2. Technology route shares (Primary vs Secondary)
3. Energy intensities (with efficiency improvements)
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
- Energy intensities [MWh/100t]
- Fuel shares [share 0-1]
- Unspecified other non-ferrous [GWh] (residual from UNSD)

Author: Automated workflow
Date: June 2026
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List
import pandas as pd
import numpy as np

# Import aluminium-specific functions
from industry.scripts.non_ferrous_metals.build_aluminium_production import (
    load_aluminium_data,
    get_base_production,
    calculate_cagr_factor,
    PROJECTION_YEARS,
    BASE_YEAR,
)
from industry.scripts.non_ferrous_metals.build_aluminium_shares import (
    get_aluminium_route_shares,
)
from industry.scripts.non_ferrous_metals.build_aluminium_intensities import (
    get_aluminium_energy_intensities,
    get_aluminium_fuel_shares,
)

# Import shared utilities
from industry.utils.helpers import get_scenarios_from_build_config_industry, country_to_iso2

# Get scenarios from config
SCENARIOS = get_scenarios_from_build_config_industry()

# Paths
_SCRIPT_DIR = Path(__file__).parent
_INDUSTRY_ROOT = _SCRIPT_DIR.parent.parent  # scripts/non_ferrous_metals/ -> scripts/ -> industry/
AL_PRODUCTION_CSV = (_INDUSTRY_ROOT / "input_data" / "non_ferrous_metals" / "AL_production.csv").resolve()

# ---------------------------------------------------------------------------
# Production Rows
# ---------------------------------------------------------------------------

def build_aluminium_production_rows(countries: List[str], target_years: List[int]) -> pd.DataFrame:
    """
    Build production rows for aluminium.
    
    Returns DataFrame with columns:
    metric_1, metric_2, metric_3, metric_4, year, scenario, units, [country columns]
    """
    # Load historical data
    df_hist = load_aluminium_data(AL_PRODUCTION_CSV)
    
    rows = []
    
    for scenario in SCENARIOS:
        for year in target_years:
            row = {
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
                
                base_production, actual_base_year = get_base_production(df_hist, country_code, BASE_YEAR)
                
                if base_production == 0:
                    row[country] = 0.0
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

def build_aluminium_route_rows(countries: List[str], target_years: List[int]) -> pd.DataFrame:
    """Build technology route share rows (Primary vs Secondary)."""
    route_shares = get_aluminium_route_shares(target_years, SCENARIOS)
    
    rows = []
    
    for route_name, year_scenario_shares in route_shares.items():
        for year in target_years:
            for scenario in SCENARIOS:
                share = year_scenario_shares[year][scenario]
                
                row = {
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


# ---------------------------------------------------------------------------
# Energy Intensity Rows
# ---------------------------------------------------------------------------

def build_aluminium_intensity_rows(countries: List[str], target_years: List[int]) -> pd.DataFrame:
    """Build energy intensity rows for each route."""
    intensities = get_aluminium_energy_intensities(target_years, SCENARIOS)
    
    rows = []
    
    for route_name, year_scenario_intensities in intensities.items():
        for year in target_years:
            for scenario in SCENARIOS:
                intensity_mwh_per_t = year_scenario_intensities[year][scenario]
                
                # Convert MWh/t → MWh/100t (config uses 100 tonnes as unit)
                intensity_mwh_per_100t = intensity_mwh_per_t * 100
                
                row = {
                    'metric_1': 'non-ferrous metals',
                    'metric_2': 'energy_intensity',
                    'metric_3': route_name,
                    'metric_4': '',
                    'year': str(year),
                    'scenario': scenario,
                    'units': 'MWh/100t',
                }
                
                # Same intensity for all countries (global average)
                # TODO: Consider country-specific intensities if data available
                for country in countries:
                    row[country] = round(intensity_mwh_per_100t, 2)
                
                rows.append(row)
    
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Fuel Share Rows
# ---------------------------------------------------------------------------

def build_aluminium_fuel_share_rows(countries: List[str], target_years: List[int]) -> pd.DataFrame:
    """Build fuel share rows for each route."""
    fuel_shares = get_aluminium_fuel_shares(target_years, SCENARIOS)
    
    rows = []
    
    # Iterate through routes
    for route_name, fuels_dict in fuel_shares.items():
        # Iterate through fuels
        for fuel_name, year_scenario_shares in fuels_dict.items():
            for year in target_years:
                for scenario in SCENARIOS:
                    share = year_scenario_shares[year][scenario]
                    
                    row = {
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
# Unspecified "Other Non-Ferrous" Rows
# ---------------------------------------------------------------------------

def build_other_non_ferrous_rows(countries: List[str], target_years: List[str]) -> pd.DataFrame:
    """
    Build activity_factor rows for other non-ferrous metals (copper, zinc, lead, etc.).
    
    This is a PLACEHOLDER - actual implementation should calculate residual:
        other_non_ferrous = UNSD_total - aluminium_detailed
    
    For now, we create empty rows that will be populated by calculate_final_energy_demand.py
    Changed from 'unspecified' to 'activity_factor' for consistency with simple sectors.
    """
    rows = []
    
    # Placeholder: will be calculated in calculate_final_energy_demand.py
    # using get_other_non_ferrous_GWh() function
    
    for scenario in SCENARIOS:
        for year in target_years:
            row = {
                'metric_1': 'non-ferrous metals',
                'metric_2': 'activity_factor',
                'metric_3': 'other_non_ferrous',
                'metric_4': '',
                'year': str(year),
                'scenario': scenario,
                'units': 'dimensionless',
            }
            
            # Placeholder zeros - will be calculated dynamically
            for country in countries:
                row[country] = 0.0
            
            rows.append(row)
    
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Main Generation Function
# ---------------------------------------------------------------------------

def generate_aluminium_config(countries: List[str]) -> pd.DataFrame:
    """
    Generate all aluminium configuration rows.
    
    Args:
        countries: List of country codes (e.g., ['CN', 'US', 'IN', ...])
    
    Returns:
        DataFrame with all aluminium config rows
    """
    print("="*80)
    print("GENERATING ALUMINIUM CONFIGURATION")
    print("="*80)
    
    target_years = PROJECTION_YEARS
    
    # 1. Production volumes
    print("\n1. Building aluminium production rows...")
    df_production = build_aluminium_production_rows(countries, target_years)
    print(f"   ✓ Generated {len(df_production)} production rows")
    
    # 2. Technology route shares
    print("\n2. Building technology route share rows...")
    df_routes = build_aluminium_route_rows(countries, target_years)
    print(f"   ✓ Generated {len(df_routes)} route share rows")
    
    # 3. Energy intensities
    print("\n3. Building energy intensity rows...")
    df_intensities = build_aluminium_intensity_rows(countries, target_years)
    print(f"   ✓ Generated {len(df_intensities)} intensity rows")
    
    # 4. Fuel shares
    print("\n4. Building fuel share rows...")
    df_fuel_shares = build_aluminium_fuel_share_rows(countries, target_years)
    print(f"   ✓ Generated {len(df_fuel_shares)} fuel share rows")
    
    # 5. Other non-ferrous (placeholder)
    print("\n5. Building other non-ferrous placeholder rows...")
    df_other = build_other_non_ferrous_rows(countries, target_years)
    print(f"   ✓ Generated {len(df_other)} other non-ferrous rows")
    
    # Combine all rows
    df_all = pd.concat([
        df_production,
        df_routes,
        df_intensities,
        df_fuel_shares,
        df_other,
    ], ignore_index=True)
    
    print(f"\n✓ Total aluminium config rows: {len(df_all)}")
    print("="*80 + "\n")
    
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
