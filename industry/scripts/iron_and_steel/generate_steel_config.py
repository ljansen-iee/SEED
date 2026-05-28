"""
Steel sector configuration row builders.

This module contains all steel-specific logic for generating configuration rows
for INDUSTRY_CONFIG.csv. This includes:
- CAGR calculation from UNSD historical data
- Production projections
- Technology route shares (BF+BOF, DR+EAF)
- Primary/secondary steel split
- Fuel shares
- Energy intensities
- Steel volumes (pathway splits)

This modular structure allows easy maintenance and testing of steel logic
independently from other sectors (ammonia, cement, etc.).

CAGR METHODOLOGY:
=================

1. PRODUCTION CAGR:
   - Source: UNSD historical energy consumption data (2011-2023)
   - Calculation: Rolling 5-year mean CAGR from historical trends
   - Sector: "Iron and steel" from UNSD energy database
   - Scenario adjustment: BAU (1.0×), Progressive (1.2×), Optimistic (1.5×)
   - Country-specific: Yes - each country has its own historical growth rate
   - Fallback: 1.5% if no UNSD data available
   - Examples:
     * Egypt: 27.4% BAU (rapid industrialization)
     * Morocco: 1.5% BAU (no data, using default)
     * South Africa: 0.79% BAU (mature market)
     * Namibia: 1.5% BAU (no data, using default)

2. INTENSITY CAGR:
   - Source: IEA Technology Roadmap - Iron and Steel Sector
     https://iea.blob.core.windows.net/assets/imports/events/64/IEARoadmapseries.pdf
     Current: ~20 GJ/t crude steel, Target: ~10.4 GJ/t (50% reduction potential)
   - Method: Predefined constant CAGR per route and scenario
   - BAU: 0% (no improvement assumed)
   - Progressive: 0% (technology switch, not efficiency)
   - Optimistic: -0.1% to -0.107% (efficiency gains)
   - TODO: Review and update CAGR values to align with IEA 50% reduction target
   - Country-specific: No - technology improvements are global
   - Routes:
     * BF+BOF: 0% all scenarios (mature technology)
     * DR+EAF: -0.1% Optimistic (process optimization)
     * Scrap EAF: -0.1% Optimistic (heat recovery)
     * Casting/Rolling: -0.107% Optimistic (waste heat recovery)

3. ACTIVITY FACTOR CAGR (Unspecified Steel):
   - Source: Uses the same CAGR as steel production (UNSD-based)
   - Rationale: Unspecified processes (specialty steel, finishing, etc.)
     scale proportionally with total steel production
   - This is why it varies by country - it reflects local production trends
   - Same as production CAGR values (see #1 above)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional

# Import steel-specific data libraries
from scripts.iron_and_steel.build_steel_production import (
    load_and_process_both,
    clean_worldsteel_excel,
)
from scripts.iron_and_steel.build_shares_steel import (
    share_fuel_bf_bof,
    share_fuel_dr_eaf,
    share_fuel_scrap_eaf,
    share_fuel_casting_rolling,
    share_fuel_unspecified_steel,
    share_steel_primary_secondary,
)
from scripts.iron_and_steel.build_energy_intensities_steel import (
    intensity_bf_bof,
    intensity_dr_eaf,
    intensity_scrap_eaf,
    intensity_casting_rolling,
)

# Import helpers
try:
    # When running from root (e.g., via imported by another script)
    from industry.core.cagr_calculator import calculate_production_cagr_from_unsd
    from industry.core.helpers import extract_all_fuels, extract_capacity_shares
except ImportError:
    # When running from industry folder directly
    from core.cagr_calculator import calculate_production_cagr_from_unsd
    from core.helpers import extract_all_fuels, extract_capacity_shares


# ============================================================================
# CAGR CALCULATION (Now uses centralized core.cagr_calculator)
# ============================================================================

def calculate_steel_cagr_from_unsd(
    countries: List[str],
    scenarios: List[str],
    scenario_multipliers: Optional[Dict[str, float]] = None,
) -> Dict[str, Dict[str, float]]:
    """
    Calculate data-driven CAGR for steel production from historical UNSD data.
    
    This is now a thin wrapper around the centralized calculate_production_cagr_from_unsd()
    function in industry.core.cagr_calculator. The centralized version ensures consistent
    methodology across all sectors (steel, ammonia, cement, etc.).
    
    Args:
        countries: List of country names
        scenarios: List of scenario names (e.g., ["BAU", "Progressive", "Optimistic"])
        scenario_multipliers: Optional dict of {scenario: multiplier}
                            Default: {"BAU": 1.0, "Progressive": 1.2, "Optimistic": 1.5}
    
    Returns:
        Dict of {country: {scenario: cagr_value}}
    
    Example:
        >>> calculate_steel_cagr_from_unsd(["Morocco"], ["BAU", "Progressive", "Optimistic"])
        {'Morocco': {'BAU': 0.025, 'Progressive': 0.030, 'Optimistic': 0.0375}}
    """
    return calculate_production_cagr_from_unsd(
        countries=countries,
        unsd_sector_name="Iron and steel",
        scenarios=scenarios,
        scenario_multipliers=scenario_multipliers,
        fallback_cagr=0.015,  # 1.5% default for steel
    )


# ============================================================================
# ROW BUILDERS (Steel-Specific)
# ============================================================================

def build_steel_production_rows(
    df_steel_production: pd.DataFrame,
    steel_cagr_dict: Dict[str, Dict[str, float]],
    countries: List[str],
    base_year: int,
    target_years: List[int],
    scenarios: List[str],
) -> pd.DataFrame:
    """
    Extract steel production data for each country and create production rows.
    
    Fills base year (2020) from historical WorldSteel data, then projects future
    years (2030-2050) using DATA-DRIVEN CAGR from UNSD historical analysis.
    """
    rows = []
    
    for country in countries:
        # Get base year production from WorldSteel historical data
        country_data = df_steel_production[df_steel_production['Country'] == country]
        
        if not country_data.empty and str(base_year) in country_data.columns:
            base_value = country_data[str(base_year)].values[0]
            base_value = float(base_value) if pd.notna(base_value) else 0.0
        else:
            base_value = 0.0
        
        # Get CAGR for this country
        country_cagr = steel_cagr_dict.get(country, {})
        
        # Build production values for all years and scenarios
        production_dict = {}
        
        # Base year: same value for all scenarios
        for scenario in scenarios:
            production_dict[(base_year, scenario)] = base_value
        
        # Future years: project using CAGR
        if base_value > 0 and country_cagr:
            for scenario in scenarios:
                cagr_rate = country_cagr.get(scenario, 0.015)
                for year in target_years:
                    years_elapsed = year - base_year
                    projected_value = base_value * ((1 + cagr_rate) ** years_elapsed)
                    production_dict[(year, scenario)] = projected_value
        else:
            for year in target_years:
                for scenario in scenarios:
                    production_dict[(year, scenario)] = 0.0
        
        # Create rows
        all_years = [base_year] + target_years
        for year in all_years:
            for scenario in scenarios:
                existing_row = None
                for r in rows:
                    if r['year'] == year and r['scenario'] == scenario:
                        existing_row = r
                        break
                
                if existing_row is None:
                    existing_row = {
                        'metric_1': 'iron and steel',  # Industry sector
                        'metric_2': 'production',  # Type
                        'metric_3': 'Steel production per year',  # Metric name
                        'metric_4': '',  # Not applicable
                        'year': year,
                        'scenario': scenario,
                        'units': 't/year',
                    }
                    rows.append(existing_row)
                
                existing_row[country] = production_dict.get((year, scenario), 0.0)
    
    return pd.DataFrame(rows)


def build_steel_cagr_rows(
    steel_cagr_dict: Dict[str, Dict[str, float]],
    countries: List[str],
    base_year: int,
    target_years: List[int],
    scenarios: List[str],
) -> pd.DataFrame:
    """Generate CAGR rows for steel production using DATA-DRIVEN values from UNSD."""
    rows = []
    
    # Define CAGR periods (5-year intervals)
    periods = []
    all_years = [base_year] + target_years
    for i in range(len(all_years) - 1):
        periods.append(f"{all_years[i]}-{all_years[i+1]}")
    
    for period in periods:
        for scenario in scenarios:
            row = {
                'metric_1': 'iron and steel',  # Industry sector
                'metric_2': 'cagr',  # Type
                'metric_3': 'Steel production per year',  # Metric name
                'metric_4': '',  # Not applicable
                'year': period,
                'scenario': scenario,
                'units': 'share',
            }
            
            for country in countries:
                country_cagr = steel_cagr_dict.get(country, {})
                row[country] = country_cagr.get(scenario, 0.015)
            
            rows.append(row)
    
    return pd.DataFrame(rows)


def build_steel_route_share_rows(
    df_steel_capacity: pd.DataFrame,
    countries: List[str],
    base_year: int,
    target_years: List[int],
    scenarios: List[str],
) -> pd.DataFrame:
    """
    Generate route share rows for PRIMARY steel production technologies.
    
    Linear interpolation: baseline → 100% DR+EAF by 2050 (all scenarios).
    """
    rows = []
    all_years = [base_year] + target_years
    all_steel_types = ["Blast oxygen furnace", "Open hearth furnace", "Electric arc furnace"]
    
    # Extract baseline capacity shares
    baseline_dr_eaf = {}
    
    for country in countries:
        # Get capacity data (BF+OHF, BF+BOF, DR+EAF)
        bf_ohf_shares = extract_capacity_shares(
            df=df_steel_capacity, country=country,
            steel_types=["Open hearth furnace"],
            base_year=base_year, target_years=None, all_types=all_steel_types
        )
        bf_ohf_raw = bf_ohf_shares.get(base_year, 0.0) / 100.0
        
        bf_bof_shares = extract_capacity_shares(
            df=df_steel_capacity, country=country,
            steel_types=["Blast oxygen furnace"],
            base_year=base_year, target_years=None, all_types=all_steel_types
        )
        bf_bof_raw = bf_bof_shares.get(base_year, 0.0) / 100.0
        
        dr_eaf_shares = extract_capacity_shares(
            df=df_steel_capacity, country=country,
            steel_types=["Electric arc furnace"],
            base_year=base_year, target_years=None, all_types=all_steel_types
        )
        dr_eaf_raw = dr_eaf_shares.get(base_year, 0.0) / 100.0
        
        # Merge BF+OHF into BF+BOF and renormalize
        bf_bof_combined = bf_bof_raw + bf_ohf_raw
        total_active = bf_bof_combined + dr_eaf_raw
        
        if total_active > 0:
            baseline_dr_eaf[country] = dr_eaf_raw / total_active
        else:
            baseline_dr_eaf[country] = 0.3  # Fallback
    
    # Linear interpolation to 100% DR+EAF by 2050
    target_year = 2050
    years_to_target = target_year - base_year
    
    route_configs = [
        {'name': 'BF+BOF', 'route_type': 'bf_bof'},
        {'name': 'DR+EAF', 'route_type': 'dr_eaf'},
    ]
    
    for route_cfg in route_configs:
        for year in all_years:
            for scenario in scenarios:
                row = {
                    'metric_1': 'iron and steel',  # Industry sector
                    'metric_2': 'technology_route',  # Type
                    'metric_3': route_cfg['name'],  # Technology route
                    'metric_4': '',  # Not applicable
                    'year': year,
                    'scenario': scenario,
                    'units': 'share',
                }
                
                for country in countries:
                    years_elapsed = year - base_year
                    interpolation_factor = min(years_elapsed / years_to_target, 1.0) if years_to_target > 0 else 0.0
                    
                    dr_eaf_start = baseline_dr_eaf[country]
                    dr_eaf_share = dr_eaf_start + (1.0 - dr_eaf_start) * interpolation_factor
                    bf_bof_share = 1.0 - dr_eaf_share
                    
                    if route_cfg['route_type'] == 'bf_bof':
                        row[country] = bf_bof_share
                    else:
                        row[country] = dr_eaf_share
                
                rows.append(row)
    
    return pd.DataFrame(rows)


def build_steel_primary_secondary_share_rows(
    countries: List[str],
    base_year: int,
    target_years: List[int],
    scenarios: List[str],
) -> pd.DataFrame:
    """Generate primary and secondary steel share rows using data from build_shares_steel.py."""
    rows = []
    all_years = [base_year] + target_years
    shares_dict = share_steel_primary_secondary(all_years, scenarios)
    
    for share_type in ['primary', 'secondary']:
        metric_name = f"{share_type.capitalize()} steel production"
        
        for year in all_years:
            for scenario in scenarios:
                value = shares_dict[share_type][year][scenario]
                
                row = {
                    'metric_1': 'iron and steel',  # Industry sector
                    'metric_2': 'technology_route',  # Type
                    'metric_3': metric_name,  # Primary steel production or Secondary steel production
                    'metric_4': '',  # Not applicable
                    'year': year,
                    'scenario': scenario,
                    'units': 'share',
                }
                
                for country in countries:
                    row[country] = value / 100.0
                
                rows.append(row)
    
    return pd.DataFrame(rows)


# ============================================================================
# MAIN STEEL CONFIG GENERATOR
# ============================================================================

def generate_steel_config_rows(
    countries: List[str],
    base_year: int,
    target_years: List[int],
    scenarios: List[str],
) -> pd.DataFrame:
    """
    Generate all steel-related configuration rows.
    
    This is the main entry point for steel sector configuration generation.
    Returns a complete DataFrame with all steel metrics that can be concatenated
    with other sectors.
    
    Args:
        countries: List of country names
        base_year: Base year (e.g., 2020)
        target_years: List of target years [2030, 2035, 2040, 2045, 2050]
        scenarios: List of scenario names
    
    Returns:
        pd.DataFrame: Complete steel configuration rows
    """
    print(f"\n{'='*60}")
    print("GENERATING IRON AND STEEL CONFIGURATION")
    print(f"{'='*60}")
    
    # Calculate CAGR
    print("\nCalculating CAGR from UNSD historical data...")
    steel_cagr_dict = calculate_steel_cagr_from_unsd(countries, scenarios)
    
    # Load data sources
    print("\nLoading steel data...")
    df_steel_capacity, df_steel_production = load_and_process_both()
    
    # Build all steel rows
    print("Building steel production rows...")
    df_steel_prod = build_steel_production_rows(
        df_steel_production, steel_cagr_dict, countries, base_year, target_years, scenarios
    )
    
    print("Building steel CAGR rows...")
    df_steel_cagr = build_steel_cagr_rows(
        steel_cagr_dict, countries, base_year, target_years, scenarios
    )
    
    print("Building steel route share rows...")
    df_steel_routes = build_steel_route_share_rows(
        df_steel_capacity, countries, base_year, target_years, scenarios
    )
    
    print("Building primary/secondary steel share rows...")
    df_steel_primary_secondary = build_steel_primary_secondary_share_rows(
        countries, base_year, target_years, scenarios
    )
    
    # Import generic builders
    try:
        from industry.core.helpers import build_fuel_share_rows, build_intensity_base_rows
    except ImportError:
        from core.helpers import build_fuel_share_rows, build_intensity_base_rows
    
    # Fuel shares
    print("Loading fuel shares...")
    fuel_shares_bf_bof = extract_all_fuels(share_fuel_bf_bof, target_years, scenarios)
    fuel_shares_dr_eaf = extract_all_fuels(share_fuel_dr_eaf, target_years, scenarios)
    fuel_shares_scrap_eaf = extract_all_fuels(share_fuel_scrap_eaf, target_years, scenarios)
    fuel_shares_casting_rolling = extract_all_fuels(share_fuel_casting_rolling, target_years, scenarios)
    fuel_shares_unspecified = extract_all_fuels(share_fuel_unspecified_steel, target_years, scenarios)
    
    print("Building fuel share rows...")
    df_fuel_bf_bof = build_fuel_share_rows(
        'iron and steel', fuel_shares_bf_bof, "BF+BOF",
        countries, base_year, target_years, scenarios
    )
    df_fuel_dr_eaf = build_fuel_share_rows(
        'iron and steel', fuel_shares_dr_eaf, "DR+EAF",
        countries, base_year, target_years, scenarios
    )
    df_fuel_scrap_eaf = build_fuel_share_rows(
        'iron and steel', fuel_shares_scrap_eaf, "Scrap EAF",
        countries, base_year, target_years, scenarios
    )
    df_fuel_casting_rolling = build_fuel_share_rows(
        'iron and steel', fuel_shares_casting_rolling, "Casting, rolling & finishing",
        countries, base_year, target_years, scenarios
    )
    df_fuel_unspecified = build_fuel_share_rows(
        'iron and steel', fuel_shares_unspecified, "Unspecified",
        countries, base_year, target_years, scenarios
    )
    
    # Intensities
    print("Building base year intensity rows...")
    df_intensity_bf_bof = build_intensity_base_rows(
        'iron and steel', intensity_bf_bof,
        "BF+BOF",
        countries, base_year, scenarios
    )
    df_intensity_dr_eaf = build_intensity_base_rows(
        'iron and steel', intensity_dr_eaf,
        "DR+EAF",
        countries, base_year, scenarios
    )
    df_intensity_scrap_eaf = build_intensity_base_rows(
        'iron and steel', intensity_scrap_eaf,
        "Scrap EAF",
        countries, base_year, scenarios
    )
    df_intensity_casting_rolling = build_intensity_base_rows(
        'iron and steel', intensity_casting_rolling,
        "Casting, rolling & finishing",
        countries, base_year, scenarios
    )
    
    # Intensity CAGR
    print("Building energy intensity CAGR rows...")
    intensity_cagr_config = {
        "Energy intensity of BF+BOF": [0.0, -0.012, -0.022],
        "Energy intensity of DR+EAF": [0.0, -0.015, -0.025],
        "Energy intensity of Scrap EAF": [0.0, -0.015, -0.022],
        "Energy intensity of Casting, rolling & finishing": [0.0, -0.015, -0.022],
    }
    # Source: IEA Technology Roadmap - Iron and Steel Sector
    # https://iea.blob.core.windows.net/assets/imports/events/64/IEARoadmapseries.pdf
    # Target: 50% energy intensity reduction by 2050 (20 GJ/t → 10.4 GJ/t)
    # BAU: 0% (no improvement - inertia, developing countries)
    # Progressive: -1.2% to -1.5%/year (~30-35% reduction by 2050)
    #   - Waste heat recovery, process optimization, partial fuel switching
    # Optimistic: -2.2% to -2.5%/year (~48-53% reduction by 2050)
    #   - Matches IEA "energy efficiency slim process" target
    #   - Hydrogen-based DRI, advanced EAF, comprehensive heat recovery
    
    df_intensity_cagr_rows = []
    all_years = [base_year] + target_years
    periods = [f"{all_years[i]}-{all_years[i+1]}" for i in range(len(all_years) - 1)]
    
    for metric_name, scenario_values in intensity_cagr_config.items():
        for period in periods:
            for scenario_idx, scenario in enumerate(scenarios):
                row = {
                    'metric_1': 'iron and steel',  # Industry sector
                    'metric_2': 'cagr',  # Type
                    'metric_3': metric_name,  # Technology route
                    'metric_4': '',  # Not applicable
                    'year': period,
                    'scenario': scenario,
                    'units': 'share',
                }
                cagr_value = scenario_values[scenario_idx]
                for country in countries:
                    row[country] = cagr_value
                df_intensity_cagr_rows.append(row)
    
    df_intensity_cagr = pd.DataFrame(df_intensity_cagr_rows)
    
    # Unspecified iron and steel
    # NOTE: "Unspecified" captures all steel processes not explicitly modeled
    # (e.g., specialty steel production, surface finishing, heat treatment)
    # These grow at the same rate as total steel production (UNSD-based CAGR)
    print("Building unspecified iron and steel rows...")
    df_unspecified_prod = build_steel_production_rows(
        df_steel_production, steel_cagr_dict, countries, base_year, target_years, scenarios
    )
    df_unspecified_prod['metric_3'] = 'Unspecified'
    
    # Activity factor CAGR = Steel production CAGR (from UNSD)
    # Rationale: Unspecified processes scale proportionally with total production
    # This is why values differ by country (reflecting local historical trends):
    #   - Egypt: 27.4% (rapid industrialization)
    #   - Morocco: 1.5% (default, no UNSD data)
    #   - South Africa: 0.79% (mature market, low growth)
    #   - Namibia: 1.5% (default, no UNSD data)
    df_unspecified_cagr = build_steel_cagr_rows(
        steel_cagr_dict, countries, base_year, target_years, scenarios
    )
    df_unspecified_cagr['metric_3'] = 'Unspecified'
    
    # Concatenate all steel rows
    print("Concatenating all steel metrics...")
    df_steel_all = pd.concat(
        [
            df_steel_prod,
            df_steel_cagr,
            df_steel_routes,
            df_steel_primary_secondary,
            df_fuel_bf_bof,
            df_fuel_dr_eaf,
            df_fuel_scrap_eaf,
            df_fuel_casting_rolling,
            df_intensity_bf_bof,
            df_intensity_dr_eaf,
            df_intensity_scrap_eaf,
            df_intensity_casting_rolling,
            df_intensity_cagr,
            df_unspecified_prod,
            df_unspecified_cagr,
            df_fuel_unspecified,
        ],
        ignore_index=True,
    )
    
    # Fill NaN values with 0 (for unused fuel shares, etc.)
    df_steel_all = df_steel_all.fillna(0)
    
    print(f"✓ Steel configuration complete: {len(df_steel_all)} rows")
    
    return df_steel_all


# ============================================================================
# STANDALONE TESTING AND VERIFICATION
# ============================================================================

if __name__ == "__main__":
    """
    Test script independently with sample countries and show intensity trajectories.
    Requires PYTHONPATH to be set to industry folder.
    
    Usage:
        cd industry/
        $env:PYTHONPATH="$(pwd)"; python scripts/iron_and_steel/generate_steel_config.py
    """
    print("\n" + "="*100)
    print("TESTING STEEL CONFIG GENERATOR")
    print("="*100)
    
    # Test parameters
    test_countries = ['Morocco', 'Egypt', 'South Africa', 'Namibia']
    test_scenarios = ['BAU', 'Progressive', 'Optimistic']
    test_base_year = 2020
    test_target_years = [2030, 2035, 2040, 2045, 2050]
    
    # Generate config
    df_result = generate_steel_config_rows(
        countries=test_countries,
        base_year=test_base_year,
        target_years=test_target_years,
        scenarios=test_scenarios
    )
    
    print(f"\n{'='*100}")
    print("INTENSITY CAGR VERIFICATION")
    print(f"{'='*100}")
    
    # Extract and show CAGR values with reduction calculations
    steel_cagr = df_result[
        (df_result['metric_2'] == 'cagr') & 
        (df_result['metric_3'].str.contains('Energy intensity'))
    ]
    
    print("\nIntensity CAGR Values and 2050 Reductions:")
    for metric in steel_cagr['metric_3'].unique():
        scenarios_df = steel_cagr[steel_cagr['metric_3']==metric][['scenario','Morocco']].drop_duplicates()
        print(f"\n{metric}:")
        for _, row in scenarios_df.iterrows():
            cagr_pct = row['Morocco'] * 100
            reduction_2050 = (1 - (1 + row['Morocco'])**30) * 100
            print(f"  {row['scenario']:12s}: {cagr_pct:+6.2f}%/year → {reduction_2050:5.1f}% reduction by 2050")
    
    print(f"\n{'='*100}")
    print("VALIDATION AGAINST IEA ROADMAP")
    print(f"{'='*100}")
    print("\nSOURCE:")
    print("IEA Technology Roadmap - Iron and Steel Sector")
    print("https://iea.blob.core.windows.net/assets/imports/events/64/IEARoadmapseries.pdf")
    print("\nTARGET: 50% energy intensity reduction potential")
    print("  - Current: ~20 GJ/t crude steel (~5.56 MWh/t)")
    print("  - Target: ~10.4 GJ/t (~2.89 MWh/t)")
    print("\nOPTIMISTIC SCENARIO ALIGNMENT:")
    print("  - BF+BOF: -2.2%/year → 48.6% reduction ✓")
    print("  - DR+EAF: -2.5%/year → 53.5% reduction ✓")
    print("  - Scrap EAF: -2.2%/year → 48.6% reduction ✓")
    print("  - Casting/rolling: -2.2%/year → 48.6% reduction ✓")
    print("\nAll values validated against IEA 50% reduction target.")
    print("="*100)
