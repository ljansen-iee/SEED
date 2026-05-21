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
    from industry.build_CAGR import get_final_energy_cagr_from_unsd
    from industry.helpers import extract_all_fuels, extract_capacity_shares
except ImportError:
    # When running from industry folder directly
    from build_CAGR import get_final_energy_cagr_from_unsd
    from helpers import extract_all_fuels, extract_capacity_shares


# ============================================================================
# CAGR CALCULATION
# ============================================================================

def calculate_steel_cagr_from_unsd(
    countries: List[str],
    scenarios: List[str],
    scenario_multipliers: Optional[Dict[str, float]] = None,
) -> Dict[str, Dict[str, float]]:
    """
    Calculate data-driven CAGR for steel production from historical UNSD data.
    
    This replaces hardcoded CAGR values with methodology-based calculations:
    1. Loads historical energy consumption from UNSD (2011-2023)
    2. Calculates rolling 5-year mean CAGR
    3. Applies scenario-specific multipliers
    
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
    if scenario_multipliers is None:
        scenario_multipliers = {
            "BAU": 1.0,          # Business as usual: use historical trend
            "Progressive": 1.2,  # 20% growth acceleration
            "Optimistic": 1.5,   # 50% growth acceleration
        }
    
    steel_cagr = {}
    
    for country in countries:
        print(f"  Calculating CAGR for {country} from UNSD historical data...")
        
        # Get historical CAGR from UNSD data (iron and steel sector)
        try:
            historical_cagr = get_final_energy_cagr_from_unsd(country, "Iron and steel")
            
            if historical_cagr is None or historical_cagr == 0.0:
                print(f"    ⚠️  No historical data for {country}, using default 1.5% CAGR")
                historical_cagr = 0.015  # Default 1.5% if no data
            else:
                print(f"    ✓ Historical CAGR: {historical_cagr:.3%}")
        
        except Exception as e:
            print(f"    ⚠️  Error calculating CAGR for {country}: {e}")
            historical_cagr = 0.015  # Default 1.5%
        
        # Apply scenario multipliers
        steel_cagr[country] = {}
        for scenario in scenarios:
            multiplier = scenario_multipliers.get(scenario, 1.0)
            steel_cagr[country][scenario] = historical_cagr * multiplier
            print(f"    {scenario}: {steel_cagr[country][scenario]:.3%} (×{multiplier})")
    
    return steel_cagr


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
                        'industry_sector': 'iron and steel',
                        'type': 'production',
                        'metric name': 'Steel production per year',
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
                'industry_sector': 'iron and steel',
                'type': 'cagr',
                'metric name': 'Steel production per year',
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
        {'name': 'Share of blast furnace + basic oxygen furnace for steel making', 'route_type': 'bf_bof'},
        {'name': 'Share of direct reduction + electric arc furnace for steel making', 'route_type': 'dr_eaf'},
    ]
    
    for route_cfg in route_configs:
        for year in all_years:
            for scenario in scenarios:
                row = {
                    'industry_sector': 'iron and steel',
                    'type': 'technology_route',
                    'metric name': route_cfg['name'],
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
        metric_name = f"Share of {share_type} steel"
        
        for year in all_years:
            for scenario in scenarios:
                value = shares_dict[share_type][year][scenario]
                
                row = {
                    'industry_sector': 'iron and steel',
                    'type': 'technology_route',
                    'metric name': metric_name,
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
        from industry.helpers import build_fuel_share_rows, build_intensity_base_rows
    except ImportError:
        from ...helpers import build_fuel_share_rows, build_intensity_base_rows
    
    # Fuel shares
    print("Loading fuel shares...")
    fuel_shares_bf_bof = extract_all_fuels(share_fuel_bf_bof, target_years, scenarios)
    fuel_shares_dr_eaf = extract_all_fuels(share_fuel_dr_eaf, target_years, scenarios)
    fuel_shares_scrap_eaf = extract_all_fuels(share_fuel_scrap_eaf, target_years, scenarios)
    fuel_shares_casting_rolling = extract_all_fuels(share_fuel_casting_rolling, target_years, scenarios)
    fuel_shares_unspecified = extract_all_fuels(share_fuel_unspecified_steel, target_years, scenarios)
    
    print("Building fuel share rows...")
    df_fuel_bf_bof = build_fuel_share_rows(
        'iron and steel', fuel_shares_bf_bof, "BF+BOF fuel share",
        countries, base_year, target_years, scenarios
    )
    df_fuel_dr_eaf = build_fuel_share_rows(
        'iron and steel', fuel_shares_dr_eaf, "DR+EAF fuel share",
        countries, base_year, target_years, scenarios
    )
    df_fuel_scrap_eaf = build_fuel_share_rows(
        'iron and steel', fuel_shares_scrap_eaf, "Scrap EAF fuel share",
        countries, base_year, target_years, scenarios
    )
    df_fuel_casting_rolling = build_fuel_share_rows(
        'iron and steel', fuel_shares_casting_rolling, "Casting, rolling & finishing fuel share",
        countries, base_year, target_years, scenarios
    )
    df_fuel_unspecified = build_fuel_share_rows(
        'iron and steel', fuel_shares_unspecified, "Unspecified iron and steel fuel share",
        countries, base_year, target_years, scenarios
    )
    
    # Intensities
    print("Building base year intensity rows...")
    df_intensity_bf_bof = build_intensity_base_rows(
        'iron and steel', intensity_bf_bof,
        "Energy intensity of blast furnaces + basic oxygen furnaces",
        countries, base_year, scenarios
    )
    df_intensity_dr_eaf = build_intensity_base_rows(
        'iron and steel', intensity_dr_eaf,
        "Energy intensity of direct reduction + electric arc furnaces",
        countries, base_year, scenarios
    )
    df_intensity_scrap_eaf = build_intensity_base_rows(
        'iron and steel', intensity_scrap_eaf,
        "Energy intensity of scrap electric arc furnaces",
        countries, base_year, scenarios
    )
    df_intensity_casting_rolling = build_intensity_base_rows(
        'iron and steel', intensity_casting_rolling,
        "Energy intensity of casting, rolling & finishing",
        countries, base_year, scenarios
    )
    
    # Intensity CAGR
    print("Building energy intensity CAGR rows...")
    intensity_cagr_config = {
        "Energy intensity of blast furnaces + basic oxygen furnaces": [0.0, 0.0, 0.0],
        "Energy intensity of direct reduction + electric arc furnaces": [0.0, 0.0, -0.001],
        "Energy intensity of scrap electric arc furnaces": [0.0, 0.0, -0.001],
        "Energy intensity of casting, rolling & finishing": [0.0, 0.0, -0.00107],
    }
    
    df_intensity_cagr_rows = []
    all_years = [base_year] + target_years
    periods = [f"{all_years[i]}-{all_years[i+1]}" for i in range(len(all_years) - 1)]
    
    for metric_name, scenario_values in intensity_cagr_config.items():
        for period in periods:
            for scenario_idx, scenario in enumerate(scenarios):
                row = {
                    'industry_sector': 'iron and steel',
                    'type': 'cagr',
                    'metric name': metric_name,
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
    print("Building unspecified iron and steel rows...")
    df_unspecified_prod = build_steel_production_rows(
        df_steel_production, steel_cagr_dict, countries, base_year, target_years, scenarios
    )
    df_unspecified_prod['metric name'] = 'Activity factor of unspecified iron and steel'
    
    df_unspecified_cagr = build_steel_cagr_rows(
        steel_cagr_dict, countries, base_year, target_years, scenarios
    )
    df_unspecified_cagr['metric name'] = 'Activity factor of unspecified iron and steel'
    
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
    
    print(f"✓ Steel configuration complete: {len(df_steel_all)} rows")
    
    return df_steel_all
