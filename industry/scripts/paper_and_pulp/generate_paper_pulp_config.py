"""
Paper & Pulp sector configuration row builders.

This module contains all paper & pulp-specific logic for generating configuration rows
for INDUSTRY_CONFIG.csv. This includes:
- CAGR calculation from UNSD historical data
- Production projections from FAO data
- Primary/secondary pulp ratio
- Fuel shares per process (primary pulp, secondary pulp, paper production)
- Energy intensities per process
- Unspecified paper & pulp activities (placeholder)
  DEFAULT: Zero activity (user can populate if needed)

This modular structure follows the steel/ammonia/cement/HVC pattern, allowing easy
maintenance and testing of paper & pulp logic independently from other sectors.

STANDALONE USAGE:
=================
To run this script independently and see intensity trajectories:
    
    # From industry folder (recommended):
    cd industry/
    $env:PYTHONPATH="$(pwd)"; python scripts/paper_and_pulp/generate_paper_pulp_config.py
    
    # Or on Linux/Mac:
    cd industry/
    PYTHONPATH=$(pwd) python scripts/paper_and_pulp/generate_paper_pulp_config.py

This will:
- Generate configuration rows for 4 test countries
- Show CAGR values and 2050 reduction targets
- Display 5-year intensity trajectories
- Verify alignment with China Energy Partnership (2021) targets

CAGR METHODOLOGY:
=================

1. PRODUCTION CAGR:
   - Source: UNSD historical energy consumption data (2011-2023)
   - Sector: "Paper  pulp and printing" from UNSD energy database (note: double space)
   - Calculation: Rolling 5-year mean CAGR from historical trends
   - Scenario adjustment: BAU (1.0×), Progressive (1.2×), Optimistic (1.5×)
   - Country-specific: Yes - each country has its own historical growth rate
   - Fallback: 1.5% if no UNSD data available

2. INTENSITY CAGR:
   - Source: China Energy Partnership (2021) - Technical Guideline Energy Efficiency
   - Reference: https://energypartnership.cn/fileadmin/china/media_elements/publications/2021/Technical_Guideline_Energy_Efficiency_Pulp_and_Paper_EN.pdf
   - Target: 19-20% energy demand reduction by 2050 (from 2020 baseline)
   - Method: Constant CAGR per process and scenario to reach reduction targets
   - BAU: 0% (no improvement - business as usual)
   - Progressive: -0.5% to -0.6%/year (~14-17% reduction by 2050)
     * Process optimization, waste heat recovery
     * Increased biomass residue use (black liquor, wood waste)
   - Optimistic: -0.7% to -0.8%/year (~19-21% reduction by 2050)
     * Advanced electrification with renewable power
     * Hydrogen for high-temperature processes
     * Comprehensive heat integration and cogeneration
   - Country-specific: No - technology improvements are global
   - Processes:
     * Primary pulp: Chemical pulping (kraft, sulfite) - most improvement potential
     * Secondary pulp: Recycled paper processing - already more efficient
     * Paper production: Sheet forming, drying, finishing - moderate potential
   - Future improvement: Separate efficiency curves for electricity vs. fossil fuels
     (electrification has steeper improvement curve than fossil efficiency gains)

3. ACTIVITY FACTOR CAGR (Unspecified Paper & Pulp):
   - Source: Uses the same CAGR as paper/pulp production (UNSD-based)
   - NOTE: Only applies if user manually adds activity values to Unspecified
   - DEFAULT: Unspecified activity is ZERO (to avoid double-counting with detailed pulp/paper)
   - Rationale: If user adds unspecified processes, they should scale with production
   - Same as production CAGR values (see #1 above)

CONFIGURATION STRUCTURE:
========================
metric_1: 'paper, pulp and printing' (UNSD sector level)
metric_2: 'production', 'cagr', 'technology_route', 'fuel_share', 'intensity_base'
metric_3: Specific process (e.g., 'Primary pulp production', 'Paper production')
metric_4: Sub-metric (e.g., fuel type for fuel_share rows)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional

# Import paper & pulp-specific data libraries
from industry.scripts.paper_and_pulp.build_paper_and_pulp_production import (
    process_paper_pulp_data,
)
from industry.scripts.paper_and_pulp.build_share_primary_pulp import (
    share_fuel_primary_pulp,
    share_fuel_secondary_pulp,
    share_fuel_paper,
    share_primary_secondary_pulp,
)
from industry.scripts.paper_and_pulp.build_energy_intensities_paper_pulp import (
    intensity_primary_pulp,
    intensity_secondary_pulp,
    intensity_paper_production,
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
    )


# ============================================================================
# CAGR CALCULATION (Uses centralized core.cagr_calculator)
# ============================================================================

def calculate_paper_pulp_cagr_from_unsd(
    countries: List[str],
    scenarios: List[str],
    scenario_multipliers: Optional[Dict[str, float]] = None,
) -> Dict[str, Dict[str, float]]:
    """
    Calculate data-driven CAGR for paper & pulp production from historical UNSD data.
    
    Uses UNSD "Paper  pulp and printing" sector (note: double space in actual data).
    
    Args:
        countries: List of country names
        scenarios: List of scenario names
        scenario_multipliers: Optional dict of {scenario: multiplier}
    
    Returns:
        Dict of {country: {scenario: cagr_value}}
    """
    return calculate_production_cagr_from_unsd(
        countries=countries,
        unsd_sector_name="Paper  pulp and printing",  # Note: double space
        scenarios=scenarios,
        scenario_multipliers=scenario_multipliers,
        fallback_cagr=0.015,  # 1.5% default for paper & pulp
    )


# ============================================================================
# PRODUCTION ROW BUILDERS
# ============================================================================

def load_paper_pulp_base_values(countries: List[str], base_year: int) -> Dict[str, Dict[str, float]]:
    """
    Load paper & pulp production base year values from FAO data.
    
    Args:
        countries: List of country names (full names: "Morocco", "Egypt", etc.)
        base_year: Base year (e.g., 2020)
    
    Returns:
        Dict of {country: {'pulp': tonnes, 'paper': tonnes}}
    """
    # Load and process FAO data
    df_production = process_paper_pulp_data()
    
    base_values = {}
    for country in countries:
        # Filter for country and base year
        country_data = df_production[
            (df_production['Country'] == country) & 
            (df_production['Year'] == base_year)
        ]
        
        if not country_data.empty:
            pulp_tonnes = country_data['Pulp_Production_tons'].values[0]
            paper_tonnes = country_data['Paper_Production_tons'].values[0]
            base_values[country] = {
                'pulp': float(pulp_tonnes),
                'paper': float(paper_tonnes),
            }
            print(f"  {country}: {pulp_tonnes:,.0f} t pulp, {paper_tonnes:,.0f} t paper")
        else:
            print(f"  ⚠ No data for {country} in {base_year}, using 0")
            base_values[country] = {'pulp': 0.0, 'paper': 0.0}
    
    return base_values


def build_paper_pulp_production_rows(
    countries: List[str],
    base_year: int,
    target_years: List[int],
    scenarios: List[str],
    cagr_dict: Dict[str, Dict[str, float]],
) -> pd.DataFrame:
    """
    Build paper & pulp production rows using FAO data and UNSD CAGR.
    
    Creates separate production rows for pulp and paper.
    """
    print("  Loading base year paper & pulp production from FAO data...")
    base_values_dict = load_paper_pulp_base_values(countries, base_year)
    
    all_dfs = []
    
    # 1. Pulp production rows
    pulp_base = {c: vals['pulp'] for c, vals in base_values_dict.items()}
    df_pulp = build_production_rows_with_cagr(
        industry_sector="paper, pulp and printing",
        metric_name="Pulp production per year",
        base_values=pulp_base,
        cagr_dict=cagr_dict,
        countries=countries,
        base_year=base_year,
        target_years=target_years,
        scenarios=scenarios,
        units="tonnes",
    )
    all_dfs.append(df_pulp)
    
    # 2. Paper production rows
    paper_base = {c: vals['paper'] for c, vals in base_values_dict.items()}
    df_paper = build_production_rows_with_cagr(
        industry_sector="paper, pulp and printing",
        metric_name="Paper production per year",
        base_values=paper_base,
        cagr_dict=cagr_dict,
        countries=countries,
        base_year=base_year,
        target_years=target_years,
        scenarios=scenarios,
        units="tonnes",
    )
    all_dfs.append(df_paper)
    
    return pd.concat(all_dfs, ignore_index=True)


# ============================================================================
# PRIMARY/SECONDARY PULP SHARE BUILDERS
# ============================================================================

def build_primary_secondary_pulp_shares(
    countries: List[str],
    base_year: int,
    target_years: List[int],
    scenarios: List[str],
) -> pd.DataFrame:
    """
    Generate primary vs. secondary pulp share rows.
    
    Primary: Virgin fiber (wood pulp)
    Secondary: Recycled fiber (waste paper)
    """
    rows = []
    all_years = [base_year] + target_years
    
    # Get shares from function
    shares = share_primary_secondary_pulp(target_years, scenarios)
    
    for category, year_data in shares.items():
        for year in all_years:
            if year not in year_data:
                continue
            for scenario in scenarios:
                share_pct = year_data[year][scenario]
                row = {
                    'metric_1': 'paper, pulp and printing',
                    'metric_2': 'technology_route',
                    'metric_3': f'{category.capitalize()} pulp',
                    'metric_4': '',
                    'year': year,
                    'scenario': scenario,
                    'units': 'share',
                }
                # Same shares for all countries (technology-level assumption)
                for country in countries:
                    row[country] = share_pct / 100.0  # Convert to fraction
                rows.append(row)
    
    return pd.DataFrame(rows)


# ============================================================================
# INTENSITY CAGR BUILDER
# ============================================================================

def build_paper_pulp_intensity_cagr_rows(
    countries: List[str],
    base_year: int,
    target_years: List[int],
    scenarios: List[str],
) -> pd.DataFrame:
    """
    Generate energy intensity CAGR rows for paper & pulp processes.
    
    Source: China Energy Partnership (2021) - Technical Guideline Energy Efficiency
    Reference: https://energypartnership.cn/fileadmin/china/media_elements/publications/2021/Technical_Guideline_Energy_Efficiency_Pulp_and_Paper_EN.pdf
    Target: 19-20% energy demand reduction by 2050
    """
    intensity_cagr_config = {
        # [BAU, Progressive, Optimistic] - annual CAGR rates
        # Primary pulp (highest energy use, most improvement potential):
        "Energy intensity of Primary pulp": [0.0, -0.006, -0.008],
        # → BAU: 0%, Progressive: 16.5% reduction, Optimistic: 21.4% reduction by 2050
        
        # Secondary pulp (recycled fiber, already more efficient):
        "Energy intensity of Secondary pulp": [0.0, -0.005, -0.007],
        # → BAU: 0%, Progressive: 13.9% reduction, Optimistic: 19.5% reduction by 2050
        
        # Paper production (sheet forming, drying, finishing):
        "Energy intensity of Paper production": [0.0, -0.0055, -0.0075],
        # → BAU: 0%, Progressive: 15.2% reduction, Optimistic: 20.4% reduction by 2050
    }
    # Rationale:
    # BAU: 0% (no improvement - business as usual)
    # Progressive: -0.5% to -0.6%/year
    #   - Waste heat recovery, process optimization
    #   - Increased biomass residues (black liquor, wood waste)
    # Optimistic: -0.7% to -0.8%/year (matches 19-20% target)
    #   - Advanced electrification with renewable power
    #   - Hydrogen for high-temperature processes
    #   - Comprehensive heat integration and cogeneration
    #
    # NOTE: Future enhancement - separate curves for electricity vs fossil fuels
    #       (electrification improvement rate differs from fossil efficiency gains)
    
    rows = []
    all_years = [base_year] + target_years
    periods = [f"{all_years[i]}-{all_years[i+1]}" for i in range(len(all_years) - 1)]
    
    for metric_name, scenario_values in intensity_cagr_config.items():
        for period in periods:
            for scenario_idx, scenario in enumerate(scenarios):
                row = {
                    'metric_1': 'paper, pulp and printing',
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
# MAIN PAPER & PULP CONFIG GENERATOR
# ============================================================================

def generate_paper_pulp_config_rows(
    countries: List[str],
    base_year: int,
    target_years: List[int],
    scenarios: List[str],
) -> pd.DataFrame:
    """
    Generate all paper & pulp-related configuration rows.
    
    This is the main entry point for paper & pulp sector configuration generation.
    Returns a complete DataFrame with all metrics that can be concatenated
    with other sectors.
    
    Args:
        countries: List of country names
        base_year: Base year (e.g., 2020)
        target_years: List of target years [2030, 2035, 2040, 2045, 2050]
        scenarios: List of scenario names
    
    Returns:
        pd.DataFrame: Complete paper & pulp configuration rows
    """
    print(f"\n{'='*60}")
    print("GENERATING PAPER & PULP CONFIGURATION")
    print(f"{'='*60}")
    
    all_dfs = []
    
    # 1. Calculate CAGR
    print("\n1. Calculating CAGR from UNSD historical data...")
    paper_pulp_cagr_dict = calculate_paper_pulp_cagr_from_unsd(countries, scenarios)
    
    # 2. Build production rows (pulp + paper)
    print("\n2. Building paper & pulp production rows...")
    df_production = build_paper_pulp_production_rows(
        countries, base_year, target_years, scenarios, paper_pulp_cagr_dict
    )
    all_dfs.append(df_production)
    print(f"  ✓ Generated {len(df_production)} production rows")
    
    # 3. Build CAGR rows (pulp + paper)
    print("\n3. Building CAGR rows...")
    df_cagr_pulp = build_cagr_rows(
        industry_sector="paper, pulp and printing",
        metric_name="Pulp production per year",
        cagr_dict=paper_pulp_cagr_dict,
        countries=countries,
        base_year=base_year,
        target_years=target_years,
        scenarios=scenarios,
    )
    df_cagr_paper = build_cagr_rows(
        industry_sector="paper, pulp and printing",
        metric_name="Paper production per year",
        cagr_dict=paper_pulp_cagr_dict,
        countries=countries,
        base_year=base_year,
        target_years=target_years,
        scenarios=scenarios,
    )
    all_dfs.extend([df_cagr_pulp, df_cagr_paper])
    print(f"  ✓ Generated {len(df_cagr_pulp) + len(df_cagr_paper)} CAGR rows")
    
    # 4. Build primary/secondary pulp share rows
    print("\n4. Building primary/secondary pulp share rows...")
    df_pulp_shares = build_primary_secondary_pulp_shares(
        countries, base_year, target_years, scenarios
    )
    all_dfs.append(df_pulp_shares)
    print(f"  ✓ Generated {len(df_pulp_shares)} pulp share rows")
    
    # 5. Build fuel share rows (3 processes)
    print("\n5. Building fuel share rows...")
    fuel_shares_primary = extract_all_fuels(share_fuel_primary_pulp, target_years, scenarios)
    fuel_shares_secondary = extract_all_fuels(share_fuel_secondary_pulp, target_years, scenarios)
    fuel_shares_paper = extract_all_fuels(share_fuel_paper, target_years, scenarios)
    
    df_fuel_primary = build_fuel_share_rows(
        industry_sector="paper, pulp and printing",
        fuel_shares_dict=fuel_shares_primary,
        metric_label="Primary pulp",
        countries=countries,
        base_year=base_year,
        target_years=target_years,
        scenarios=scenarios,
    )
    
    df_fuel_secondary = build_fuel_share_rows(
        industry_sector="paper, pulp and printing",
        fuel_shares_dict=fuel_shares_secondary,
        metric_label="Secondary pulp",
        countries=countries,
        base_year=base_year,
        target_years=target_years,
        scenarios=scenarios,
    )
    
    df_fuel_paper = build_fuel_share_rows(
        industry_sector="paper, pulp and printing",
        fuel_shares_dict=fuel_shares_paper,
        metric_label="Paper production",
        countries=countries,
        base_year=base_year,
        target_years=target_years,
        scenarios=scenarios,
    )
    
    all_dfs.extend([df_fuel_primary, df_fuel_secondary, df_fuel_paper])
    print(f"  ✓ Generated {len(df_fuel_primary) + len(df_fuel_secondary) + len(df_fuel_paper)} fuel share rows")
    
    # 6. Build base year intensity rows (3 processes)
    print("\n6. Building base year intensity rows...")
    df_intensity_primary = build_intensity_base_rows(
        industry_sector="paper, pulp and printing",
        intensity_function=intensity_primary_pulp,
        metric_label="Energy intensity of Primary pulp",
        countries=countries,
        base_year=base_year,
        scenarios=scenarios,
        intensity_selection='average',
    )
    
    df_intensity_secondary = build_intensity_base_rows(
        industry_sector="paper, pulp and printing",
        intensity_function=intensity_secondary_pulp,
        metric_label="Energy intensity of Secondary pulp",
        countries=countries,
        base_year=base_year,
        scenarios=scenarios,
        intensity_selection='average',
    )
    
    df_intensity_paper = build_intensity_base_rows(
        industry_sector="paper, pulp and printing",
        intensity_function=intensity_paper_production,
        metric_label="Energy intensity of Paper production",
        countries=countries,
        base_year=base_year,
        scenarios=scenarios,
        intensity_selection='average',
    )
    
    all_dfs.extend([df_intensity_primary, df_intensity_secondary, df_intensity_paper])
    print(f"  ✓ Generated {len(df_intensity_primary) + len(df_intensity_secondary) + len(df_intensity_paper)} intensity base rows")
    
    # 7. Build intensity CAGR rows
    print("\n7. Building energy intensity CAGR rows...")
    df_intensity_cagr = build_paper_pulp_intensity_cagr_rows(
        countries, base_year, target_years, scenarios
    )
    all_dfs.append(df_intensity_cagr)
    print(f"  ✓ Generated {len(df_intensity_cagr)} intensity CAGR rows")
    
    # 8. Concatenate all paper & pulp rows
    print("\n8. Concatenating all paper & pulp metrics...")
    df_paper_pulp_all = pd.concat(all_dfs, ignore_index=True)
    
    # Fill NaN values with 0
    df_paper_pulp_all = df_paper_pulp_all.fillna(0)
    
    print(f"\n{'='*60}")
    print(f"✓ Paper & Pulp configuration complete: {len(df_paper_pulp_all)} rows")
    print(f"{'='*60}")
    
    return df_paper_pulp_all


# ============================================================================
# STANDALONE TESTING AND VERIFICATION
# ============================================================================

if __name__ == "__main__":
    """
    Test script independently with sample countries and show intensity trajectories.
    Requires PYTHONPATH to be set to industry folder (see module docstring).
    """
    print("\n" + "="*100)
    print("TESTING PAPER & PULP CONFIG GENERATOR")
    print("="*100)
    
    # Test parameters
    test_countries = ['Morocco', 'Egypt', 'South Africa', 'Namibia']
    test_scenarios = ['BAU', 'Progressive', 'Optimistic']
    test_base_year = 2020
    test_target_years = [2030, 2035, 2040, 2045, 2050]
    
    # Generate config
    df_result = generate_paper_pulp_config_rows(
        countries=test_countries,
        base_year=test_base_year,
        target_years=test_target_years,
        scenarios=test_scenarios
    )
    
    print(f"\n{'='*100}")
    print("INTENSITY CAGR VERIFICATION")
    print(f"{'='*100}")
    
    # Extract and show CAGR values with reduction calculations
    pp_cagr = df_result[
        (df_result['metric_2'] == 'cagr') & 
        (df_result['metric_3'].str.contains('Energy intensity'))
    ]
    
    print("\nIntensity CAGR Values and 2050 Reductions:")
    for metric in pp_cagr['metric_3'].unique():
        scenarios_df = pp_cagr[pp_cagr['metric_3']==metric][['scenario','Morocco']].drop_duplicates()
        print(f"\n{metric}:")
        for _, row in scenarios_df.iterrows():
            cagr_pct = row['Morocco'] * 100
            reduction_2050 = (1 - (1 + row['Morocco'])**30) * 100
            print(f"  {row['scenario']:12s}: {cagr_pct:+6.2f}%/year → {reduction_2050:5.1f}% reduction by 2050")
    
    print(f"\n{'='*100}")
    print("5-YEAR INTENSITY TRAJECTORY (Morocco)")
    print(f"{'='*100}")
    
    # Base intensities from config
    pp_int = df_result[
        (df_result['metric_2'] == 'intensity_base') &
        (df_result['year'] == test_base_year)
    ]
    
    # CAGR config
    intensity_cagr_config = {
        'Energy intensity of Primary pulp': [0.0, -0.006, -0.008],
        'Energy intensity of Secondary pulp': [0.0, -0.005, -0.007],
        'Energy intensity of Paper production': [0.0, -0.0055, -0.0075],
    }
    
    all_years = [test_base_year] + test_target_years
    
    for metric_name in intensity_cagr_config.keys():
        # Get base value
        base_row = pp_int[pp_int['metric_3'] == metric_name]
        if base_row.empty:
            continue
        base_value = base_row['Morocco'].values[0]
        
        print(f"\n{metric_name.upper().replace('ENERGY INTENSITY OF ', '')}:")
        print(f"Base intensity ({test_base_year}): {base_value:.2f} MWh/t")
        print("-" * 100)
        
        for i, scenario in enumerate(test_scenarios):
            cagr = intensity_cagr_config[metric_name][i]
            print(f"\n{scenario:12s} (CAGR: {cagr*100:+.2f}%/year):")
            print(f"{'Year':<10} {'Intensity':<20} {'Reduction'}")
            
            for year in all_years:
                years_elapsed = year - test_base_year
                intensity = base_value * (1 + cagr) ** years_elapsed
                reduction_pct = (1 - intensity / base_value) * 100
                print(f"{year:<10} {intensity:>6.2f} MWh/t          {reduction_pct:>5.1f}%")
    
    print("\n" + "="*100)
    print("\nSOURCE:")
    print("China Energy Partnership (2021) - Technical Guideline Energy Efficiency")
    print("https://energypartnership.cn/fileadmin/china/media_elements/publications/2021/")
    print("Technical_Guideline_Energy_Efficiency_Pulp_and_Paper_EN.pdf")
    print("\nTARGET: 19-20% energy demand reduction by 2050 (Optimistic scenario)")
    print("="*100)
