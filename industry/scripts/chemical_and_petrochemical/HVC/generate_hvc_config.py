"""
HVC (High-Value Chemicals) sector configuration row builders.

This module contains all HVC-specific logic for generating configuration rows
for INDUSTRY_CONFIG.csv. This includes:
- CAGR calculation from UNSD historical data
- Production projections from industrial database
- Technology route shares (Naphtha cracking / LPG cracking / MTO)
- Fuel shares per route
- Energy intensities per route

This modular structure follows the steel/ammonia/cement pattern, allowing easy
maintenance and testing of HVC logic independently from other sectors.

HVC = High-Value Chemicals:
- Ethylene (~55% of HVC output)
- Propylene (~30% of HVC output)  
- Butadiene (~10% of HVC output)
- Aromatics (~5% of HVC output)

CAGR METHODOLOGY:
=================

1. PRODUCTION CAGR:
   - Source: UNSD historical energy consumption data (2011-2023)
   - Sector: "Chemical and petrochemical" from UNSD energy database
   - Calculation: Rolling 5-year mean CAGR from historical trends
   - Scenario adjustment: BAU (1.0×), Progressive (1.2×), Optimistic (1.5×)
   - Country-specific: Yes - each country has its own historical growth rate
   - Fallback: 2.0% if no UNSD data available (higher than ammonia due to plastics demand)

2. INTENSITY CAGR:
   - Source: Engineering efficiency improvements (see build_energy_intensities_hvc.py)
   - BAU: 0% (no improvement assumed)
   - Progressive: -0.17% to -0.20%/year (heat recovery, process optimization)
   - Optimistic: -0.33% to -0.40%/year (advanced catalysts, electrification)
   - Country-specific: No - technology improvements are global

3. ROUTE SHARE EVOLUTION:
   - 2020 baseline: Naphtha 60%, LPG 25%, MTO 15%
   - Trend: MTO growing (can use green methanol), naphtha declining
   - Scenarios: Different decarbonization speeds

DATA QUALITY NOTE:
==================
Production data from industrial_database.csv uses correction factors because
database lists REFINERY CAPACITIES, not dedicated cracker capacities.
See build_hvc_production.py docstring for detailed explanation.

CONFIGURATION STRUCTURE:
========================
metric_1: 'chemical and petrochemical' (UNSD sector level - shared with ammonia)
metric_2: 'production', 'cagr', 'technology_route', 'fuel_share', 'intensity_base'
metric_3: Specific industry metric (e.g., 'HVC production per year', 'Naphtha cracking')
metric_4: Sub-metric (e.g., fuel type for fuel_share rows)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional

# Import HVC-specific data libraries
from industry.scripts.chemical_and_petrochemical.HVC.build_hvc_production import (
    get_hvc_production,
)
from industry.scripts.chemical_and_petrochemical.HVC.build_shares_hvc import (
    share_fuel_hvc_naphtha,
    share_fuel_hvc_lpg,
    share_fuel_hvc_mto,
)
from industry.scripts.chemical_and_petrochemical.HVC.build_energy_intensities_hvc import (
    intensity_hvc_naphtha,
    intensity_hvc_lpg,
    intensity_hvc_mto,
)

# Import helpers
try:
    # When running from root
    from industry.utils.cagr_calculator import calculate_production_cagr_from_unsd
    from industry.utils.helpers import (
        extract_all_fuels,
        build_fuel_share_rows,
        build_intensity_base_rows,
        build_production_rows_with_cagr,
        build_cagr_rows,
        interpolate_or_extrapolate,
    )
except ImportError:
    # When running from industry folder directly
    from utils.cagr_calculator import calculate_production_cagr_from_unsd
    from utils.helpers import (
        extract_all_fuels,
        build_fuel_share_rows,
        build_intensity_base_rows,
        build_production_rows_with_cagr,
        build_cagr_rows,
        interpolate_or_extrapolate,
    )


# ============================================================================
# CAGR CALCULATION (Uses centralized core.cagr_calculator)
# ============================================================================

def calculate_hvc_cagr_from_unsd(
    countries: List[str],
    scenarios: List[str],
    scenario_multipliers: Optional[Dict[str, float]] = None,
) -> Dict[str, Dict[str, float]]:
    """
    Calculate data-driven CAGR for HVC production from historical UNSD data.
    
    Uses the same UNSD sector as ammonia ("Chemical and petrochemical") since
    both are petrochemical products tracked together in energy statistics.
    
    Args:
        countries: List of country names
        scenarios: List of scenario names
        scenario_multipliers: Optional dict of {scenario: multiplier}
    
    Returns:
        Dict of {country: {scenario: cagr_value}}
    """
    return calculate_production_cagr_from_unsd(
        countries=countries,
        unsd_sector_name="Chemical and petrochemical",
        scenarios=scenarios,
        scenario_multipliers=scenario_multipliers,
        fallback_cagr=0.02,  # 2% default for HVC (plastics demand growth)
    )


# ============================================================================
# PRODUCTION ROW BUILDERS
# ============================================================================

def load_hvc_base_values(countries: List[str], base_year: int) -> Dict[str, float]:
    """
    Load HVC production base year values from industrial database.
    
    Args:
        countries: List of country names (full names: "Morocco", "Egypt", etc.)
        base_year: Base year (e.g., 2020)
    
    Returns:
        Dict of {country: production_tonnes}
    """
    # Country name to ISO code mapping
    country_to_iso = {
        "Morocco": "MA",
        "Egypt": "EG",
        "South Africa": "ZA",
        "Namibia": "NA",
    }
    
    # Load HVC production from industrial database
    df_hvc = get_hvc_production(add_country_names=True)
    
    base_values = {}
    for country in countries:
        iso_code = country_to_iso.get(country)
        if iso_code is None:
            print(f"  ⚠ No ISO code mapping for {country}, using 0")
            base_values[country] = 0.0
            continue
        
        # Find country in HVC data
        country_data = df_hvc[df_hvc["country"] == iso_code]
        
        if not country_data.empty:
            # Get production in tonnes (from Mt)
            prod_mt = country_data["HVC_production_Mt_per_year"].values[0]
            prod_tonnes = prod_mt * 1e6
            base_values[country] = prod_tonnes
            print(f"  {country}: {prod_tonnes:,.0f} tonnes ({prod_mt:.2f} Mt)")
        else:
            print(f"  ⚠ No HVC data for {country} ({iso_code}), using 0")
            base_values[country] = 0.0
    
    return base_values


def build_hvc_production_rows(
    countries: List[str],
    base_year: int,
    target_years: List[int],
    scenarios: List[str],
    cagr_dict: Dict[str, Dict[str, float]],
) -> pd.DataFrame:
    """
    Build HVC production rows using industrial database and UNSD CAGR.
    
    Base year values from industrial database (with correction factors).
    Future projections using UNSD historical CAGR.
    """
    print("  Loading base year HVC production from industrial database...")
    base_values = load_hvc_base_values(countries, base_year)
    
    return build_production_rows_with_cagr(
        industry_sector="chemical and petrochemical",
        metric_name="HVC production per year",
        base_values=base_values,
        cagr_dict=cagr_dict,
        countries=countries,
        base_year=base_year,
        target_years=target_years,
        scenarios=scenarios,
        units="tonnes",
    )


# ============================================================================
# TECHNOLOGY ROUTE SHARE BUILDERS
# ============================================================================

def build_hvc_route_share_rows(
    countries: List[str],
    base_year: int,
    target_years: List[int],
    scenarios: List[str],
) -> pd.DataFrame:
    """
    Generate technology route share rows for HVC production.
    
    Routes:
    - Naphtha cracking: 60% (2020) → declining to 45% (2050 Optimistic)
    - LPG cracking: 25% (2020) → stable at 25% (all scenarios)
    - MTO: 15% (2020) → growing to 30% (2050 Optimistic, green methanol potential)
    
    Rationale:
    - Naphtha: Traditional route, declining due to higher emissions
    - LPG: Stable, efficient for smaller olefins
    - MTO: Growing, can use green methanol (H2 + CO2)
    """
    rows = []
    all_years = [base_year] + target_years
    
    # Route share evolution by scenario
    # Format: {year: [BAU, Progressive, Optimistic]}
    route_shares = {
        "Naphtha cracking": {
            2020: [60, 60, 60],
            2030: [60, 58, 55],
            2050: [60, 52, 45],
        },
        "LPG cracking": {
            2020: [25, 25, 25],
            2030: [25, 25, 25],
            2050: [25, 25, 25],
        },
        "MTO": {
            2020: [15, 15, 15],
            2030: [15, 17, 20],
            2050: [15, 23, 30],
        },
    }
    
    for route_name, yearly_shares in route_shares.items():
        for scenario_idx, scenario in enumerate(scenarios):
            # Build per-scenario series
            series = {year: vals[scenario_idx] for year, vals in yearly_shares.items()}
            series_interp = interpolate_or_extrapolate(series, all_years)
            
            for year, share_pct in series_interp.items():
                row = {
                    'metric_1': 'chemical and petrochemical',
                    'metric_2': 'technology_route',
                    'metric_3': route_name,
                    'metric_4': '',
                    'year': year,
                    'scenario': scenario,
                    'units': 'share',
                }
                
                # Same route shares for all countries (technology-level assumption)
                for country in countries:
                    row[country] = share_pct / 100.0  # Convert to fraction
                
                rows.append(row)
    
    return pd.DataFrame(rows)


# ============================================================================
# INTENSITY CAGR BUILDER
# ============================================================================

def build_hvc_intensity_cagr_rows(
    countries: List[str],
    base_year: int,
    target_years: List[int],
    scenarios: List[str],
) -> pd.DataFrame:
    """
    Generate energy intensity CAGR rows for HVC routes.
    
    CAGR values based on engineering efficiency improvements:
    - BAU: 0% (no improvement)
    - Progressive: -0.17% to -0.20%/year (5-6% total by 2050)
    - Optimistic: -0.33% to -0.40%/year (10-12% total by 2050)
    
    Source: Engineering estimates from build_energy_intensities_hvc.py
    """
    intensity_cagr_config = {
        "Energy intensity of Naphtha cracking": [0.0, -0.0017, -0.0033],
        "Energy intensity of LPG cracking": [0.0, -0.0017, -0.0033],
        "Energy intensity of MTO": [0.0, -0.0020, -0.0040],
    }
    
    rows = []
    all_years = [base_year] + target_years
    periods = [f"{all_years[i]}-{all_years[i+1]}" for i in range(len(all_years) - 1)]
    
    for metric_name, scenario_values in intensity_cagr_config.items():
        for period in periods:
            for scenario_idx, scenario in enumerate(scenarios):
                row = {
                    'metric_1': 'chemical and petrochemical',
                    'metric_2': 'cagr',
                    'metric_3': metric_name,
                    'metric_4': '',
                    'year': period,
                    'scenario': scenario,
                    'units': 'share',
                }
                cagr_value = scenario_values[scenario_idx]
                for country in countries:
                    row[country] = cagr_value
                rows.append(row)
    
    return pd.DataFrame(rows)


# ============================================================================
# MAIN HVC CONFIG GENERATOR
# ============================================================================

def generate_hvc_config_rows(
    countries: List[str],
    base_year: int,
    target_years: List[int],
    scenarios: List[str],
) -> pd.DataFrame:
    """
    Generate all HVC-related configuration rows.
    
    This is the main entry point for HVC sector configuration generation.
    Returns a complete DataFrame with all HVC metrics that can be concatenated
    with other sectors.
    
    Args:
        countries: List of country names
        base_year: Base year (e.g., 2020)
        target_years: List of target years [2030, 2035, 2040, 2045, 2050]
        scenarios: List of scenario names
    
    Returns:
        pd.DataFrame: Complete HVC configuration rows
    """
    print(f"\n{'='*60}")
    print("GENERATING HVC (HIGH-VALUE CHEMICALS) CONFIGURATION")
    print(f"{'='*60}")
    
    all_dfs = []
    
    # 1. Calculate CAGR
    print("\n1. Calculating CAGR from UNSD historical data...")
    hvc_cagr_dict = calculate_hvc_cagr_from_unsd(countries, scenarios)
    
    # 2. Build production rows
    print("\n2. Building HVC production rows...")
    df_production = build_hvc_production_rows(
        countries, base_year, target_years, scenarios, hvc_cagr_dict
    )
    all_dfs.append(df_production)
    print(f"  ✓ Generated {len(df_production)} production rows")
    
    # 3. Build CAGR rows
    print("\n3. Building CAGR rows...")
    df_cagr = build_cagr_rows(
        industry_sector="chemical and petrochemical",
        metric_name="HVC production per year",
        cagr_dict=hvc_cagr_dict,
        countries=countries,
        base_year=base_year,
        target_years=target_years,
        scenarios=scenarios,
    )
    all_dfs.append(df_cagr)
    print(f"  ✓ Generated {len(df_cagr)} CAGR rows")
    
    # 4. Build technology route share rows
    print("\n4. Building technology route share rows...")
    df_route_shares = build_hvc_route_share_rows(
        countries, base_year, target_years, scenarios
    )
    all_dfs.append(df_route_shares)
    print(f"  ✓ Generated {len(df_route_shares)} route share rows")
    
    # 5. Build fuel share rows (per route)
    print("\n5. Building fuel share rows...")
    fuel_shares_naphtha = extract_all_fuels(share_fuel_hvc_naphtha, target_years, scenarios)
    fuel_shares_lpg = extract_all_fuels(share_fuel_hvc_lpg, target_years, scenarios)
    fuel_shares_mto = extract_all_fuels(share_fuel_hvc_mto, target_years, scenarios)
    
    df_fuel_naphtha = build_fuel_share_rows(
        industry_sector="chemical and petrochemical",
        fuel_shares_dict=fuel_shares_naphtha,
        metric_label="Naphtha cracking",
        countries=countries,
        base_year=base_year,
        target_years=target_years,
        scenarios=scenarios,
    )
    
    df_fuel_lpg = build_fuel_share_rows(
        industry_sector="chemical and petrochemical",
        fuel_shares_dict=fuel_shares_lpg,
        metric_label="LPG cracking",
        countries=countries,
        base_year=base_year,
        target_years=target_years,
        scenarios=scenarios,
    )
    
    df_fuel_mto = build_fuel_share_rows(
        industry_sector="chemical and petrochemical",
        fuel_shares_dict=fuel_shares_mto,
        metric_label="MTO",
        countries=countries,
        base_year=base_year,
        target_years=target_years,
        scenarios=scenarios,
    )
    
    all_dfs.extend([df_fuel_naphtha, df_fuel_lpg, df_fuel_mto])
    print(f"  ✓ Generated {len(df_fuel_naphtha) + len(df_fuel_lpg) + len(df_fuel_mto)} fuel share rows")
    
    # 6. Build base year intensity rows (per route)
    print("\n6. Building base year intensity rows...")
    df_intensity_naphtha = build_intensity_base_rows(
        industry_sector="chemical and petrochemical",
        intensity_function=intensity_hvc_naphtha,
        metric_label="Energy intensity of Naphtha cracking",
        countries=countries,
        base_year=base_year,
        scenarios=scenarios,
    )
    
    df_intensity_lpg = build_intensity_base_rows(
        industry_sector="chemical and petrochemical",
        intensity_function=intensity_hvc_lpg,
        metric_label="Energy intensity of LPG cracking",
        countries=countries,
        base_year=base_year,
        scenarios=scenarios,
    )
    
    df_intensity_mto = build_intensity_base_rows(
        industry_sector="chemical and petrochemical",
        intensity_function=intensity_hvc_mto,
        metric_label="Energy intensity of MTO",
        countries=countries,
        base_year=base_year,
        scenarios=scenarios,
    )
    
    all_dfs.extend([df_intensity_naphtha, df_intensity_lpg, df_intensity_mto])
    print(f"  ✓ Generated {len(df_intensity_naphtha) + len(df_intensity_lpg) + len(df_intensity_mto)} intensity base rows")
    
    # 7. Build intensity CAGR rows
    print("\n7. Building energy intensity CAGR rows...")
    df_intensity_cagr = build_hvc_intensity_cagr_rows(
        countries, base_year, target_years, scenarios
    )
    all_dfs.append(df_intensity_cagr)
    print(f"  ✓ Generated {len(df_intensity_cagr)} intensity CAGR rows")
    
    # 8. Concatenate all HVC rows
    print("\n8. Concatenating all HVC metrics...")
    df_hvc_all = pd.concat(all_dfs, ignore_index=True)
    
    # Fill NaN values with 0
    df_hvc_all = df_hvc_all.fillna(0)
    
    print(f"✓ HVC configuration complete: {len(df_hvc_all)} rows")
    
    return df_hvc_all


# ============================================================================
# STANDALONE TESTING AND VERIFICATION
# ============================================================================

if __name__ == "__main__":
    """
    Test script independently with sample countries and show key metrics.
    Requires PYTHONPATH to be set to industry folder.
    
    Usage:
        cd industry/
        $env:PYTHONPATH="$(pwd)"; python scripts/chemical_and_petrochemical/HVC/generate_hvc_config.py
    """
    print("\n" + "="*100)
    print("TESTING HVC CONFIG GENERATOR")
    print("="*100)
    
    # Test parameters
    test_countries = ['Morocco', 'Egypt', 'South Africa', 'Namibia']
    test_scenarios = ['BAU', 'Progressive', 'Optimistic']
    test_base_year = 2020
    test_target_years = [2030, 2035, 2040, 2045, 2050]
    
    # Generate config
    df_result = generate_hvc_config_rows(
        countries=test_countries,
        base_year=test_base_year,
        target_years=test_target_years,
        scenarios=test_scenarios
    )
    
    print(f"\n{'='*100}")
    print("INTENSITY CAGR VERIFICATION")
    print(f"{'='*100}")
    
    # Extract and show CAGR values with reduction calculations
    hvc_cagr = df_result[
        (df_result['metric_2'] == 'cagr') & 
        (df_result['metric_3'].str.contains('Energy intensity'))
    ]
    
    print("\nIntensity CAGR Values and 2050 Reductions:")
    for metric in hvc_cagr['metric_3'].unique():
        scenarios_df = hvc_cagr[hvc_cagr['metric_3']==metric][['scenario','Morocco']].drop_duplicates()
        print(f"\n{metric}:")
        for _, row in scenarios_df.iterrows():
            cagr_pct = row['Morocco'] * 100
            reduction_2050 = (1 - (1 + row['Morocco'])**30) * 100
            print(f"  {row['scenario']:12s}: {cagr_pct:+6.2f}%/year → {reduction_2050:5.1f}% reduction by 2050")
    
    # Show technology route transitions
    print(f"\n{'='*100}")
    print("TECHNOLOGY ROUTE TRANSITIONS (Morocco, Optimistic)")
    print(f"{'='*100}")
    
    route_shares = df_result[
        (df_result['metric_2'] == 'technology_route') &
        (df_result['metric_3'].isin(['Naphtha cracking', 'LPG cracking', 'MTO'])) &
        (df_result['scenario'] == 'Optimistic') &
        (df_result['year'].isin([2020, 2030, 2050]))
    ][['metric_3', 'year', 'Morocco']].pivot(index='metric_3', columns='year', values='Morocco')
    
    if not route_shares.empty:
        print("\n" + route_shares.to_string())
        print("\nTransition: Naphtha dominance → Increased MTO (methanol-to-olefins)")
    
    print(f"\n{'='*100}")
    print("DATA QUALITY NOTE")
    print(f"{'='*100}")
    print("\n⚠ Production data uses refinery capacities with correction factors.")
    print("   See build_hvc_production.py for detailed explanation.")
    print("\nCorrection factors (petrochemical integration ratios):")
    print("  - Egypt: 6.13%")
    print("  - South Africa: 21.18%")
    print("  - Morocco: 8.04%")
    print("  - Global default: 8.00%")
    print("\nFallback CAGR: 2.0% (used when no UNSD data available)")
    print("="*100)
