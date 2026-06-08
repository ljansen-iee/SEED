"""
Cement sector configuration row builders.

This module contains all cement-specific logic for generating configuration rows
for INDUSTRY_CONFIG.csv. This includes:
- CAGR calculation from UNSD historical data
- Production projections (cement + clinker)
- Clinker ratio projections (blended cement adoption)
- Fuel shares (electrification + hydrogen transition)
- Energy intensities (efficiency improvements)
- Unspecified non-metallic minerals (proxy for glass, ceramics, etc.)

This modular structure allows easy maintenance and testing of cement logic
independently from other sectors (steel, ammonia, etc.).

CAGR METHODOLOGY:
=================

1. PRODUCTION CAGR:
   - Source: UNSD historical energy consumption data (2011-2023)
   - Calculation: Rolling 5-year mean CAGR from historical trends
   - Sector: "Non-metallic minerals" from UNSD energy database
   - Scenario adjustment: BAU (1.0×), Progressive (1.2×), Optimistic (1.5×)
   - Country-specific: Yes - each country has its own historical growth rate
   - Fallback: 1.5% if no UNSD data available
   - Fallback source: USGS historical cement production data (2011-2023) if UNSD unavailable

2. ENERGY INTENSITY CAGR:
   - Approach: Annual decline rate (negative CAGR)
   - Base intensity: 1.0972 MWh/t clinker (2020, all scenarios)
   - Decline rates (annual):
     * BAU: 0.0% (no efficiency gain, conservative baseline)
     * Progressive: -0.5%/year (~12% reduction by 2050)
     * Optimistic: -1.0%/year (~22% reduction by 2050)
   - Justification: IEA cement efficiency potential (15-25% by 2050)
   - Technologies: Waste heat recovery, improved kiln efficiency, alternative raw materials

3. CLINKER RATIO:
   - Definition: Clinker content as fraction of final cement (clinker/cement)
   - Source: Expert assumption (literature-based projections)
   - Decline represents blended cement adoption:
     * Fly ash substitution
     * Slag cement blending
     * Limestone calcined clay cement (LC3)
   - Values:
     * 2020: 0.71 (all scenarios, current practice)
     * 2030: BAU=0.71, Progressive=0.66, Optimistic=0.65
     * 2050: BAU=0.71, Progressive=0.64, Optimistic=0.61
   - Note: Lower clinker ratio = less CO2 emissions (clinker production is carbon-intensive)

4. FUEL SHARES:
   - Source: Expert assumptions (scenario-based transition pathways)
   - Key trends:
     * Diesel decline: 78% → 45% → 15% (BAU→Progressive→Optimistic by 2050)
     * Electrification: 12% → 35% → 50%
     * Hydrogen adoption: 0% → 15% → 30% (new fuel)
     * Coal phaseout: 2% → 0% (Progressive/Optimistic)
   - Interpolated linearly between anchor years (2020, 2030, 2050)

DATA SOURCES:
=============
- Production base values: USGS Mineral Yearbook (MyB) Excel files
- Production CAGR: UNSD historical energy consumption (sector: "Non-metallic minerals")
- Clinker ratios: Expert assumption (IEA/cement industry literature)
- Fuel shares: Expert assumption (decarbonization pathways)
- Energy intensity: Expert assumption (1.0972 MWh/t from cement industry standards)
- Intensity CAGR: Expert assumption (IEA efficiency potential)

CONFIGURATION STRUCTURE:
========================
metric_1: 'non-metallic minerals' (UNSD sector level - standardized)
metric_2: 'production', 'cagr', 'technology_route', 'fuel_share', 'intensity_base'
metric_3: Specific industry metric (e.g., 'Cement production per year', 'Clinker ratio', 'Unspecified NMM activity factor')
metric_4: Sub-metric (e.g., fuel type for fuel_share rows)
"""

from pathlib import Path
from typing import Dict, List
import pandas as pd
import numpy as np

# Import data loading functions
from industry.scripts.non_metallic_minerals.build_cement_production import (
    find_input_folder,
    find_cement_files,
    load_cement_value,
)
from industry.scripts.non_metallic_minerals.build_shares_cement import (
    share_fuel_cement_production,
    share_fuel_unspecified_nmm,
)
from industry.scripts.non_metallic_minerals.build_energy_intensities_cement import (
    intensity_cement_production,
)

# Import centralized utilities
try:
    # When running from root
    from industry.utils.cagr_calculator import calculate_production_cagr_from_unsd
    from industry.utils.helpers import (
        extract_all_fuels,
        build_production_rows_with_cagr,
        build_cagr_rows,
        build_fuel_share_rows,
        build_intensity_base_rows,
        interpolate_or_extrapolate,
    )
except ImportError:
    # When running from industry folder directly
    from utils.cagr_calculator import calculate_production_cagr_from_unsd
    from utils.helpers import (
        extract_all_fuels,
        build_production_rows_with_cagr,
        build_cagr_rows,
        build_fuel_share_rows,
        build_intensity_base_rows,
        interpolate_or_extrapolate,
    )


# ============================================================================
# CAGR CALCULATION (Uses centralized core.cagr_calculator)
# ============================================================================

def calculate_cement_cagr_from_unsd(
    countries: List[str],
    scenarios: List[str],
    scenario_multipliers: Dict[str, float] = None,
    fallback_cagr: float = 0.015,
) -> Dict[str, Dict[str, float]]:
    """
    Calculate cement production CAGR from UNSD historical data.
    
    THIN WRAPPER around core.cagr_calculator.calculate_production_cagr_from_unsd.
    
    Args:
        countries: List of country names
        scenarios: List of scenario names (e.g., ["BAU", "Progressive", "Optimistic"])
        scenario_multipliers: Dict mapping scenario names to multipliers (default: BAU=1.0, Progressive=1.2, Optimistic=1.5)
        fallback_cagr: Default CAGR if no UNSD data (default: 1.5%)
    
    Returns:
        Dict[country, Dict[scenario, cagr_rate]] where cagr_rate is decimal (e.g., 0.015 for 1.5%)
    """
    if scenario_multipliers is None:
        scenario_multipliers = {
            "BAU": 1.0,
            "Progressive": 1.2,
            "Optimistic": 1.5,
        }
    
    # Use centralized CAGR calculator with UNSD sector "Non-metallic minerals"
    return calculate_production_cagr_from_unsd(
        countries=countries,
        unsd_sector_name="Non-metallic minerals",
        scenarios=scenarios,
        scenario_multipliers=scenario_multipliers,
        fallback_cagr=fallback_cagr,
    )


# ============================================================================
# PRODUCTION DATA LOADING
# ============================================================================

def load_cement_base_values(
    countries: List[str],
    base_year: int,
) -> Dict[str, float]:
    """
    Load cement production base year values from USGS MyB files.
    
    Args:
        countries: List of country names
        base_year: Base year (e.g., 2020)
    
    Returns:
        Dict[country, production_tonnes]
    """
    input_folder = find_input_folder()
    base_values = {}
    
    print(f"\nLoading cement production data for base year {base_year}...")
    for country in countries:
        try:
            cement_files = find_cement_files(input_folder, country)
            cement_file = cement_files[0]
            # load_cement_value returns thousand tonnes, convert to tonnes
            cement_value_kt = load_cement_value(cement_file, base_year)
            cement_value_t = cement_value_kt * 1e3
            base_values[country] = cement_value_t
            print(f"  {country}: {cement_value_t:,.0f} tonnes")
        except FileNotFoundError:
            print(f"  ⚠ No USGS data for {country}, assuming 0")
            base_values[country] = 0.0
    
    return base_values


# ============================================================================
# CLINKER RATIO CONFIGURATION
# ============================================================================

def build_clinker_ratio_rows(
    countries: List[str],
    base_year: int,
    target_years: List[int],
    scenarios: List[str],
) -> pd.DataFrame:
    """
    Generate clinker ratio rows (clinker content as fraction of cement).
    
    Clinker ratio represents blended cement adoption:
    - 0.71 = traditional cement (71% clinker, 29% gypsum/additives)
    - 0.61 = blended cement (61% clinker, 39% fly ash/slag/LC3)
    
    Lower ratio = less CO2 emissions (clinker production is carbon-intensive).
    
    Args:
        countries: List of country names
        base_year: Base year (e.g., 2020)
        target_years: List of target years
        scenarios: List of scenario names
    
    Returns:
        pd.DataFrame: Clinker ratio rows in long format
    """
    # Expert assumptions (scenario-dependent adoption of blended cement)
    base_ratios = {
        2020: [0.71, 0.71, 0.71],  # BAU, Progressive, Optimistic
        2030: [0.71, 0.66, 0.65],
        2050: [0.71, 0.64, 0.61],
    }
    
    all_years = [base_year] + target_years
    rows = []
    
    # Interpolate ratios for intermediate years
    for scenario_idx, scenario in enumerate(scenarios):
        # Build per-scenario series
        series = {year: vals[scenario_idx] for year, vals in base_ratios.items()}
        series_interp = interpolate_or_extrapolate(series, all_years)
        
        for year, ratio_value in series_interp.items():
            row = {
                'metric_1': 'non-metallic minerals',
                'metric_2': 'technology_route',
                'metric_3': 'Clinker ratio',  # Clinker content as fraction of cement
                'metric_4': '',
                'year': year,
                'scenario': scenario,
                'units': 'share',
            }
            # Apply same ratio to all countries (technology-level assumption)
            for country in countries:
                row[country] = ratio_value
            rows.append(row)
    
    return pd.DataFrame(rows)


# ============================================================================
# MAIN CEMENT CONFIG GENERATOR
# ============================================================================

def generate_cement_config_rows(
    countries: List[str],
    base_year: int,
    target_years: List[int],
    scenarios: List[str],
) -> pd.DataFrame:
    """
    Generate all cement configuration rows.
    
    This is the main entry point called by generate_industry_config.py.
    Generates ~600-800 rows covering:
    - Cement production (tonnes/year)
    - Clinker ratios (blended cement adoption)
    - CAGR (production growth rates)
    - Fuel shares (7 fuels × routes × years × scenarios)
    - Energy intensities (base + CAGR)
    - Unspecified non-metallic minerals
    
    Args:
        countries: List of country names
        base_year: Base year (e.g., 2020)
        target_years: List of target years (e.g., [2030, 2035, 2040, 2045, 2050])
        scenarios: List of scenario names (e.g., ["BAU", "Progressive", "Optimistic"])
    
    Returns:
        pd.DataFrame: All cement configuration rows in long format
    """
    print("\n" + "="*70)
    print("GENERATING CEMENT CONFIGURATION")
    print("="*70)
    
    all_dfs = []
    
    # 1. Calculate CAGR from UNSD
    print("\n1. Calculating CAGR from UNSD historical data...")
    cement_cagr_dict = calculate_cement_cagr_from_unsd(
        countries=countries,
        scenarios=scenarios,
    )
    
    # 2. Load base year production values
    print("\n2. Loading base year cement production...")
    base_values = load_cement_base_values(countries, base_year)
    
    # 3. Build cement production rows
    print("\n3. Building cement production rows...")
    df_production = build_production_rows_with_cagr(
        industry_sector="non-metallic minerals",
        metric_name="Cement production per year",
        base_values=base_values,
        cagr_dict=cement_cagr_dict,
        countries=countries,
        base_year=base_year,
        target_years=target_years,
        scenarios=scenarios,
        units="tonnes",
    )
    all_dfs.append(df_production)
    print(f"  ✓ Generated {len(df_production)} production rows")
    
    # 4. Build CAGR rows
    print("\n4. Building CAGR rows...")
    df_cagr = build_cagr_rows(
        industry_sector="non-metallic minerals",
        metric_name="Cement production per year",
        cagr_dict=cement_cagr_dict,
        countries=countries,
        base_year=base_year,
        target_years=target_years,
        scenarios=scenarios,
    )
    all_dfs.append(df_cagr)
    print(f"  ✓ Generated {len(df_cagr)} CAGR rows")
    
    # 5. Build clinker ratio rows
    print("\n5. Building clinker ratio rows...")
    df_clinker_ratio = build_clinker_ratio_rows(
        countries, base_year, target_years, scenarios
    )
    all_dfs.append(df_clinker_ratio)
    print(f"  ✓ Generated {len(df_clinker_ratio)} clinker ratio rows")
    
    # 6. Build fuel share rows
    print("\n6. Building fuel share rows...")
    fuel_shares_dict = extract_all_fuels(share_fuel_cement_production, target_years, scenarios)
    df_fuel_shares = build_fuel_share_rows(
        industry_sector="non-metallic minerals",
        fuel_shares_dict=fuel_shares_dict,
        metric_label="Cement production",
        countries=countries,
        base_year=base_year,
        target_years=target_years,
        scenarios=scenarios,
    )
    all_dfs.append(df_fuel_shares)
    print(f"  ✓ Generated {len(df_fuel_shares)} fuel share rows")
    
    # 7. Build base year intensity rows
    print("\n7. Building base year intensity rows...")
    df_intensity_base = build_intensity_base_rows(
        industry_sector="non-metallic minerals",
        intensity_function=intensity_cement_production,
        metric_label="Energy intensity of Cement production",
        countries=countries,
        base_year=base_year,
        scenarios=scenarios,
    )
    all_dfs.append(df_intensity_base)
    print(f"  ✓ Generated {len(df_intensity_base)} intensity base rows")
    
    # 8. Build intensity CAGR rows
    print("\n8. Building energy intensity CAGR rows...")
    intensity_cagr_config = {
        "Energy intensity of Cement production": [0.0, -0.008, -0.015],
        # BAU: 0% (no efficiency gain - inertia in developing countries)
        # Progressive: -0.8%/year (~20% reduction by 2050)
        #   - Clinker substitution (fly ash, slag)
        #   - Waste heat recovery systems
        #   - Alternative fuels (biomass, waste)
        # Optimistic: -1.5%/year (~35% reduction by 2050)
        #   - Advanced clinker substitution (>50% replacement)
        #   - High-efficiency grinding & kiln systems
        #   - Partial electrification with renewable power
        #
        # TODO: Validate with specific literature sources:
        #   - IEA Technology Roadmap - Cement (2018 or latest edition)
        #   - GCCA Climate Ambition reports
        #   - Academic studies on cement energy efficiency trends
        # Current values are engineering estimates and should be verified.
    }
    
    df_intensity_cagr_rows = []
    all_years = [base_year] + target_years
    periods = [f"{all_years[i]}-{all_years[i+1]}" for i in range(len(all_years) - 1)]
    
    for metric_name, scenario_values in intensity_cagr_config.items():
        for period in periods:
            for scenario_idx, scenario in enumerate(scenarios):
                row = {
                    'metric_1': 'non-metallic minerals',
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
                df_intensity_cagr_rows.append(row)
    
    df_intensity_cagr = pd.DataFrame(df_intensity_cagr_rows)
    all_dfs.append(df_intensity_cagr)
    print(f"  ✓ Generated {len(df_intensity_cagr)} intensity CAGR rows")
    
    # 9. Build unspecified non-metallic minerals rows
    # NOTE: "Unspecified NMM" captures other non-metallic mineral processes not explicitly modeled
    # (e.g., glass production, ceramics, lime, gypsum)
    # Uses cement as a proxy with separate fuel shares and CAGR
    print("\n9. Building unspecified non-metallic minerals rows...")
    
    # Use cement production as base, scaled by a factor (proxy for other NMM)
    unspecified_base_values = {country: value * 0.3 for country, value in base_values.items()}
    
    df_unspecified_prod = build_production_rows_with_cagr(
        industry_sector="non-metallic minerals",
        metric_name="Unspecified NMM activity factor",
        base_values=unspecified_base_values,
        cagr_dict=cement_cagr_dict,  # Same CAGR as cement
        countries=countries,
        base_year=base_year,
        target_years=target_years,
        scenarios=scenarios,
        units="activity_factor",
    )
    all_dfs.append(df_unspecified_prod)
    
    df_unspecified_cagr = build_cagr_rows(
        industry_sector="non-metallic minerals",
        metric_name="Unspecified NMM activity factor",
        cagr_dict=cement_cagr_dict,
        countries=countries,
        base_year=base_year,
        target_years=target_years,
        scenarios=scenarios,
    )
    all_dfs.append(df_unspecified_cagr)
    
    # Unspecified NMM fuel shares (different from cement)
    fuel_shares_unspecified = extract_all_fuels(share_fuel_unspecified_nmm, target_years, scenarios)
    df_fuel_shares_unspecified = build_fuel_share_rows(
        industry_sector="non-metallic minerals",
        fuel_shares_dict=fuel_shares_unspecified,
        metric_label="Unspecified NMM",
        countries=countries,
        base_year=base_year,
        target_years=target_years,
        scenarios=scenarios,
    )
    all_dfs.append(df_fuel_shares_unspecified)
    
    print(f"  ✓ Generated {len(df_unspecified_prod) + len(df_unspecified_cagr) + len(df_fuel_shares_unspecified)} unspecified NMM rows")
    
    # 10. Concatenate all rows
    print("\n10. Concatenating all cement metrics...")
    df_all = pd.concat(all_dfs, ignore_index=True)
    
    print(f"\n{'='*70}")
    print(f"✓ Cement configuration complete: {len(df_all)} rows")
    print(f"{'='*70}")
    
    return df_all


# ============================================================================
# STANDALONE TESTING AND VERIFICATION
# ============================================================================

if __name__ == "__main__":
    """
    Test script independently with sample countries and show intensity trajectories.
    Requires PYTHONPATH to be set to industry folder.
    
    Usage:
        cd industry/
        $env:PYTHONPATH="$(pwd)"; python scripts/non_metallic_minerals/generate_cement_config.py
    """
    print("\n" + "="*100)
    print("TESTING CEMENT CONFIG GENERATOR")
    print("="*100)
    
    # Test parameters
    test_countries = ['Morocco', 'Egypt', 'South Africa', 'Namibia']
    test_scenarios = ['BAU', 'Progressive', 'Optimistic']
    test_base_year = 2020
    test_target_years = [2030, 2035, 2040, 2045, 2050]
    
    # Generate config
    df_result = generate_cement_config_rows(
        countries=test_countries,
        base_year=test_base_year,
        target_years=test_target_years,
        scenarios=test_scenarios
    )
    
    print(f"\n{'='*100}")
    print("INTENSITY CAGR VERIFICATION")
    print(f"{'='*100}")
    
    # Extract and show CAGR values with reduction calculations
    cement_cagr = df_result[
        (df_result['metric_2'] == 'cagr') & 
        (df_result['metric_3'].str.contains('Energy intensity'))
    ]
    
    print("\nIntensity CAGR Values and 2050 Reductions:")
    for metric in cement_cagr['metric_3'].unique():
        scenarios_df = cement_cagr[cement_cagr['metric_3']==metric][['scenario','Morocco']].drop_duplicates()
        print(f"\n{metric}:")
        for _, row in scenarios_df.iterrows():
            cagr_pct = row['Morocco'] * 100
            reduction_2050 = (1 - (1 + row['Morocco'])**30) * 100
            print(f"  {row['scenario']:12s}: {cagr_pct:+6.2f}%/year → {reduction_2050:5.1f}% reduction by 2050")
    
    print(f"\n{'='*100}")
    print("STATUS: Engineering Estimates - Needs Validation")
    print(f"{'='*100}")
    print("\n⚠ WARNING: Current values are engineering estimates, not from specific literature.")
    print("\nREQUIRED VALIDATION SOURCES:")
    print("  - IEA Technology Roadmap - Cement (2018 or latest)")
    print("  - GCCA (Global Cement and Concrete Association) Climate Ambition reports")
    print("  - Academic studies on cement energy efficiency trends")
    print("\nPLACEHOLDER ASSUMPTIONS:")
    print("  - BAU: 0% (no improvement)")
    print("  - Progressive: -0.8%/year → 21.4% reduction (clinker substitution, waste heat recovery)")
    print("  - Optimistic: -1.5%/year → 36.5% reduction (alternative fuels, advanced kilns)")
    print("\nTODO: Replace with validated IEA/GCCA values.")
    print("="*100)
