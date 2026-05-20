"""
Generate INDUSTRY_CONFIG.csv with all country parameters in long format.

This module creates a single consolidated configuration file matching the
residential workflow pattern, replacing the per-country Output.csv files.

Structure:
    - Columns: ['type', 'metric name', 'year', 'scenario', 'units'] + country_list
    - Years: 2020 (base), 2030, 2035, 2040, 2045, 2050
    - Scenarios: BAU, Progressive, Optimistic
    - Metric types:
        - production: Physical production values (tons/year)
        - cagr: Compound annual growth rates (decimal)
        - route_share: Technology route shares (fraction)
        - fuel_share: Fuel shares per route (fraction)
        - intensity_base: Base energy intensities (GJ/ton)
        - intensity_improvement: Efficiency improvements (fraction)
"""

from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime

# === Import existing industry modules ===
from scripts.iron_and_steel.build_steel_production import (
    load_and_process_both,
    clean_worldsteel_excel,
)
from scripts.iron_and_steel.build_shares_steel import (
    share_fuel_bf_ohf,
    share_fuel_bf_bof,
    share_fuel_dr_eaf,
    share_fuel_scrap_eaf,
)
from scripts.iron_and_steel.build_energy_intensities_steel import (
    intensity_bf_ohf,
    intensity_bf_bof,
    intensity_dr_eaf,
    intensity_scrap_eaf,
)
# from scripts.iron_and_steel.build_cement_production import get_cement_and_clinker  # TODO: Add when implementing cement
from build_CAGR import (
    expand_with_cagr_smooth,
    get_metric_cagr_cfg_from_excel,
    load_industry_config,
)
import helpers
from helpers import (
    DEFAULT_TARGET_YEARS,
    extract_all_fuels,
    extract_capacity_shares,
)

# === Module-level constants (matching build_config_industry.py) ===
BASE_YEAR = 2020
TARGET_YEARS = DEFAULT_TARGET_YEARS
SCENARIOS = ["BAU", "Progressive", "Optimistic"]
INDUSTRY_CONFIG_FILE = "industry_config.csv"

BASE_DIR = Path(__file__).resolve().parent
INDUSTRY_CONFIG_PATH = BASE_DIR / INDUSTRY_CONFIG_FILE


def build_steel_production_rows(
    df_steel_production,
    industry_cagr_excel,
    countries,
    base_year,
    target_years,
    scenarios,
):
    """
    Extract steel production data for each country and create production rows.
    
    Fills base year (2020) from historical WorldSteel data, then projects future
    years (2030-2050) using CAGR values from industry config.
    
    Args:
        df_steel_production: DataFrame from load_and_process_both()
        industry_cagr_excel: Loaded industry config Excel data (for CAGR projections)
        countries: List of country names
        base_year: Base year (e.g., 2020)
        target_years: List of target years [2030, 2035, 2040, 2045, 2050]
        scenarios: List of scenario names
    
    Returns:
        pd.DataFrame: Production rows in long format
    """
    rows = []
    
    # Process each country separately to project using CAGR
    for country in countries:
        # Get base year production from WorldSteel historical data
        country_data = df_steel_production[
            df_steel_production['Country'] == country
        ]
        
        if not country_data.empty and str(base_year) in country_data.columns:
            base_value = country_data[str(base_year)].values[0]
            base_value = float(base_value) if pd.notna(base_value) else 0.0
        else:
            base_value = 0.0
        
        # Get CAGR config for this country
        cagr_cfg = get_metric_cagr_cfg_from_excel(
            industry_cagr_excel,
            country,
            "Steel production per year"
        )
        
        # Build production values for all years and scenarios
        production_dict = {}  # {(year, scenario): value}
        
        # Base year: same value for all scenarios
        for scenario in scenarios:
            production_dict[(base_year, scenario)] = base_value
        
        # Future years: project using CAGR
        if base_value > 0 and cagr_cfg:
            projected = expand_with_cagr_smooth(
                base_value=base_value,
                cagr_table=cagr_cfg,
                base_year=base_year,
                target_years=target_years,
                scenarios=scenarios,
            )
            
            # projected format: {'2030_BAU': value, '2030_Progressive': value, ...}
            for key, value in projected.items():
                year_str, scenario = key.split('_', 1)
                year = int(year_str)
                production_dict[(year, scenario)] = value
        else:
            # No data or CAGR, use zeros for future years
            for year in target_years:
                for scenario in scenarios:
                    production_dict[(year, scenario)] = 0.0
        
        # Create rows for this country
        all_years = [base_year] + target_years
        for year in all_years:
            for scenario in scenarios:
                # Find or create row for this (year, scenario)
                row_key = (year, scenario)
                
                # Check if row already exists in our list
                existing_row = None
                for r in rows:
                    if r['year'] == year and r['scenario'] == scenario:
                        existing_row = r
                        break
                
                if existing_row is None:
                    # Create new row
                    existing_row = {
                        'type': 'production',
                        'metric name': 'Steel production per year',
                        'year': year,
                        'scenario': scenario,
                        'units': 't/year',
                    }
                    rows.append(existing_row)
                
                # Add this country's value
                existing_row[country] = production_dict.get((year, scenario), 0.0)
    
    return pd.DataFrame(rows)


def build_steel_cagr_rows(
    industry_cagr_excel,
    countries,
    base_year,
    target_years,
    scenarios,
):
    """
    Generate CAGR rows for steel production.
    
    CAGR periods: 2020-2030, 2030-2035, 2035-2040, 2040-2045, 2045-2050
    
    Args:
        industry_cagr_excel: Loaded industry config Excel data
        countries: List of country names
        base_year: Base year (e.g., 2020)
        target_years: List of target years
        scenarios: List of scenario names
    
    Returns:
        pd.DataFrame: CAGR rows in long format
    """
    rows = []
    
    # Define CAGR periods (5-year intervals)
    periods = []
    all_years = [base_year] + target_years
    for i in range(len(all_years) - 1):
        periods.append(f"{all_years[i]}-{all_years[i+1]}")
    
    # Create one row per (period, scenario)
    for period in periods:
        for scenario in scenarios:
            row = {
                'type': 'cagr',
                'metric name': 'Steel production per year',
                'year': period,  # Period string like "2020-2030"
                'scenario': scenario,
                'units': 'share',
            }
            
            # Get CAGR values from industry config for each country
            for country in countries:
                cagr_cfg = get_metric_cagr_cfg_from_excel(
                    industry_cagr_excel,
                    country,
                    "Steel production per year"
                )
                
                # Extract CAGR value for this period and scenario
                if cagr_cfg and scenario in cagr_cfg:
                    scenario_data = cagr_cfg[scenario]
                    # Match period to CAGR config structure
                    if period in scenario_data:
                        row[country] = scenario_data[period]
                    else:
                        row[country] = 0.01  # Default 1% growth
                else:
                    row[country] = 0.01  # Default 1% growth
            
            rows.append(row)
    
    return pd.DataFrame(rows)


def build_steel_route_share_rows(
    df_steel_capacity,
    countries,
    base_year,
    target_years,
    scenarios,
):
    """
    Generate route share rows for steel production technologies with transformation applied.
    
    This function combines baseline capacity data with transformation factors to calculate
    final route shares for each year/scenario combination.
    
    Transformation logic:
        - BF+BOF: baseline_capacity[2020] × transformation_factor[year, scenario]
        - DR+EAF: 1.0 - BF+BOF (complement, assuming only 2 active technologies)
        - BF+OHF: 0.0 (obsolete technology, kept for downstream compatibility)
    
    Routes:
        - BF + OHF: Blast Furnace + Open Hearth Furnace (obsolete)
        - BF + BOF: Blast Furnace + Basic Oxygen Furnace (declining)
        - DR + EAF: Direct Reduction + Electric Arc Furnace (growing)
    
    Args:
        df_steel_capacity: Steel capacity DataFrame
        countries: List of country names
        base_year: Base year
        target_years: List of target years
        scenarios: List of scenario names
    
    Returns:
        pd.DataFrame: Route share rows in long format with transformed values
    """
    from build_CAGR import interpolate_or_extrapolate
    
    rows = []
    
    all_years = [base_year] + target_years
    all_steel_types = ["Blast oxygen furnace", "Open hearth furnace", "Electric arc furnace"]
    
    # Define transformation factors (same as route_transformation)
    transformation_anchors = {
        2040: [1.0, 0.5, 0.25],   # [BAU, Progressive, Optimistic]
        2050: [1.0, 0.25, 0.0],
    }
    
    # Interpolate transformation factors for each scenario
    transformation_by_scenario = {}
    for scenario_idx, scenario in enumerate(scenarios):
        scenario_anchors = {
            base_year: 1.0,  # Always start at 100% of baseline capacity
        }
        for year, values in transformation_anchors.items():
            scenario_anchors[year] = values[scenario_idx]
        
        transformation_by_scenario[scenario] = interpolate_or_extrapolate(
            scenario_anchors, 
            all_years
        )
    
    # Extract baseline capacity shares for each country (2020 only)
    # Renormalize to exclude BF+OHF (obsolete) so BF+BOF + DR+EAF = 1.0
    baseline_bf_bof = {}
    
    for country in countries:
        # BF+BOF baseline (raw from capacity data)
        bf_bof_shares = extract_capacity_shares(
            df=df_steel_capacity,
            country=country,
            steel_types=["Blast oxygen furnace"],
            base_year=base_year,
            target_years=None,  # Only get base year
            all_types=all_steel_types
        )
        bf_bof_raw = bf_bof_shares.get(base_year, 0.0) / 100.0  # fraction
        
        # DR+EAF baseline (raw from capacity data)
        dr_eaf_shares = extract_capacity_shares(
            df=df_steel_capacity,
            country=country,
            steel_types=["Electric arc furnace"],
            base_year=base_year,
            target_years=None,
            all_types=all_steel_types
        )
        dr_eaf_raw = dr_eaf_shares.get(base_year, 0.0) / 100.0  # fraction
        
        # Renormalize BF+BOF and DR+EAF to sum to 1.0 (ignoring BF+OHF)
        total_active = bf_bof_raw + dr_eaf_raw
        if total_active > 0:
            baseline_bf_bof[country] = bf_bof_raw / total_active
        else:
            # Fallback if no capacity data: assume 50/50 split
            baseline_bf_bof[country] = 0.5
    
    # Generate rows with transformation applied
    route_configs = [
        {
            'name': 'Share of blast furnace + open hearth furnace for steel making',
            'route_type': 'bf_ohf',
        },
        {
            'name': 'Share of blast furnace + basic oxygen furnace for steel making',
            'route_type': 'bf_bof',
        },
        {
            'name': 'Share of direct reduction + electric arc furnace for steel making',
            'route_type': 'dr_eaf',
        },
    ]
    
    for route_cfg in route_configs:
        for year in all_years:
            for scenario in scenarios:
                row = {
                    'type': 'route_share',
                    'metric name': route_cfg['name'],
                    'year': year,
                    'scenario': scenario,
                    'units': 'share',
                }
                
                # Calculate transformed shares for each country
                transformation = transformation_by_scenario[scenario].get(year, 1.0)
                
                for country in countries:
                    if route_cfg['route_type'] == 'bf_ohf':
                        # BF+OHF is obsolete (0% for all years/scenarios)
                        # Keep metric for downstream compatibility but set to 0
                        row[country] = 0.0
                    
                    elif route_cfg['route_type'] == 'bf_bof':
                        # BF+BOF: baseline × transformation factor
                        row[country] = baseline_bf_bof[country] * transformation
                    
                    elif route_cfg['route_type'] == 'dr_eaf':
                        # DR+EAF: complement of BF+BOF (1.0 - bf_bof_share)
                        bf_bof_share = baseline_bf_bof[country] * transformation
                        row[country] = 1.0 - bf_bof_share
                
                rows.append(row)
    
    return pd.DataFrame(rows)


def build_steel_fuel_share_rows(
    fuel_shares_dict,
    route_name,
    metric_label,
    countries,
    base_year,
    target_years,
    scenarios,
):
    """
    Generate fuel share rows for a specific steel production route.
    
    Args:
        fuel_shares_dict: Dictionary with fuel shares {fuel: {year: {scenario: value}}}
        route_name: Route identifier (e.g., "bf_bof")
        metric_label: Human-readable metric name (e.g., "BF+BOF fuel share")
        countries: List of country names
        base_year: Base year
        target_years: List of target years
        scenarios: List of scenario names
    
    Returns:
        pd.DataFrame: Fuel share rows in long format
    """
    rows = []
    
    # Fuel shares are typically uniform across countries (technology-level data)
    # but structure supports country-specific values if needed
    
    all_years = [base_year] + target_years
    
    for year in all_years:
        for scenario in scenarios:
            # Create one row per fuel type
            for fuel, year_data in fuel_shares_dict.items():
                if year not in year_data:
                    continue
                
                # year_data[year] is {scenario_name: value}
                scenario_values = year_data[year]
                
                if scenario not in scenario_values:
                    continue
                
                value = scenario_values[scenario]
                
                row = {
                    'type': 'fuel_share',
                    'metric name': f'{metric_label} - {fuel}',
                    'year': year,
                    'scenario': scenario,
                    'units': 'share',
                }
                
                # Apply same share to all countries (can be customized later)
                for country in countries:
                    row[country] = value / 100.0  # Convert from percentage to fraction
                
                rows.append(row)
    
    return pd.DataFrame(rows)


def build_steel_intensity_base_rows(
    intensity_function,
    route_name,
    metric_label,
    countries,
    base_year,
    scenarios,
):
    """
    Generate base year (2020) energy intensity rows for a steel production route.
    
    Creates single aggregated intensity value per route (not per-fuel breakdown).
    This base intensity will be modified by CAGR in downstream calculations.
    
    Args:
        intensity_function: Function that returns intensities (e.g., intensity_bf_bof)
        route_name: Route identifier (e.g., "bf_bof")
        metric_label: Human-readable metric name (e.g., "Energy intensity of blast furnaces + basic oxygen furnaces")
        countries: List of country names
        base_year: Base year (e.g., 2020)
        scenarios: List of scenario names (all get same base year value)
    
    Returns:
        pd.DataFrame: Base intensity rows in long format
    """
    rows = []
    
    # Get base year intensities from function
    intensities = intensity_function([base_year], scenarios)
    
    # Calculate total aggregated intensity across all fuels
    # Sum up all fuel intensities for base year
    total_intensity = 0.0
    for fuel, year_data in intensities.items():
        if base_year in year_data:
            # Use first scenario value (base year same across scenarios)
            scenario_values = year_data[base_year]
            if scenario_values:
                first_scenario = list(scenario_values.values())[0]
                total_intensity += first_scenario
    
    # Create one row for base year (same value for all scenarios)
    for scenario in scenarios:
        row = {
            'type': 'intensity_base',
            'metric name': metric_label,
            'year': base_year,
            'scenario': scenario,
            'units': 'MWh/t',
        }
        
        # Apply same base intensity to all countries (technology-level constant)
        for country in countries:
            row[country] = total_intensity
        
        rows.append(row)
    
    return pd.DataFrame(rows)


def build_steel_intensity_cagr_rows(
    countries,
    base_year,
    target_years,
    scenarios,
):
    """
    Generate CAGR rows for steel energy intensity improvement rates.
    
    These CAGR values modify the base intensities over time:
        final_intensity[year] = base_intensity × (1 + CAGR)^(year - base_year)
    
    Hardcoded values from build_CAGR.py:
        - BF+OHF: 0.0% (no improvement - obsolete technology)
        - BF+BOF: 0.0% (no improvement - mature technology)  
        - DR+EAF: -0.1% in Optimistic (slight efficiency gain)
        - Scrap EAF: -0.1% in Optimistic
    
    Args:
        countries: List of country names
        base_year: Base year
        target_years: List of target years
        scenarios: List of scenario names
    
    Returns:
        pd.DataFrame: Intensity CAGR rows in long format
    """
    rows = []
    
    # Hardcoded CAGR values from build_CAGR.py
    intensity_cagr_config = {
        "Energy intensity of blast furnaces + open hearth furnaces": [0.0, 0.0, 0.0],
        "Energy intensity of blast furnaces + basic oxygen furnaces": [0.0, 0.0, 0.0],
        "Energy intensity of direct reduction + electric arc furnaces": [0.0, 0.0, -0.001],
        "Energy intensity of scrap electric arc furnaces": [0.0, 0.0, -0.001],
    }
    
    # Define CAGR periods (5-year intervals)
    periods = []
    all_years = [base_year] + target_years
    for i in range(len(all_years) - 1):
        periods.append(f"{all_years[i]}-{all_years[i+1]}")
    
    # Create one row per (metric, period, scenario)
    for metric_name, scenario_values in intensity_cagr_config.items():
        for period in periods:
            for scenario_idx, scenario in enumerate(scenarios):
                row = {
                    'type': 'cagr',
                    'metric name': metric_name,
                    'year': period,
                    'scenario': scenario,
                    'units': 'share',
                }
                
                # Apply same CAGR to all countries
                cagr_value = scenario_values[scenario_idx]
                for country in countries:
                    row[country] = cagr_value
                
                rows.append(row)
    
    return pd.DataFrame(rows)


def generate_industry_config_csv(
    countries,
    base_year=2020,
    target_years=None,
    scenarios=None,
    output_path=None,
):
    """
    Generate the consolidated INDUSTRY_CONFIG.csv file.
    
    This function replaces the per-country Output.csv workflow with a single
    centralized configuration file matching the residential pattern.
    
    Args:
        countries: List of country names to process
        base_year: Base year for projections
        target_years: List of target years (defaults to [2030, 2035, 2040, 2045, 2050])
        scenarios: List of scenario names (defaults to ["BAU", "Progressive", "Optimistic"])
        output_path: Path to write CSV (defaults to industry/output_data/CONFIG/INDUSTRY_CONFIG.csv)
    
    Returns:
        pd.DataFrame: The generated configuration DataFrame
    """
    print(f"\n{'='*60}")
    print(f"Generating INDUSTRY_CONFIG.csv")
    print(f"Countries: {countries}")
    print(f"Base year: {base_year}")
    print(f"Target years: {target_years}")
    print(f"Scenarios: {scenarios}")
    print(f"{'='*60}\n")
    
    # Set defaults
    if target_years is None:
        target_years = TARGET_YEARS
    if scenarios is None:
        scenarios = SCENARIOS
    if output_path is None:
        output_path = BASE_DIR / "output_data" / "CONFIG" / "INDUSTRY_CONFIG.csv"
    
    # === Load industry config Excel (for CAGR values) ===
    industry_cagr_excel = load_industry_config(
        excel_path=INDUSTRY_CONFIG_PATH,
        countries=countries,
        scenarios=scenarios,
    )
    
    # === Load data sources ===
    print("Loading steel data...")
    df_steel_capacity, df_steel_production = load_and_process_both()
    
    # === Build metric DataFrames ===
    print("Building steel production rows...")
    df_steel_prod = build_steel_production_rows(
        df_steel_production,
        industry_cagr_excel,  # Added for CAGR projections
        countries,
        base_year,
        target_years,
        scenarios,
    )
    
    print("Building steel CAGR rows...")
    df_steel_cagr = build_steel_cagr_rows(
        industry_cagr_excel,
        countries,
        base_year,
        target_years,
        scenarios,
    )
    
    print("Building steel route share rows...")
    df_steel_routes = build_steel_route_share_rows(
        df_steel_capacity,
        countries,
        base_year,
        target_years,
        scenarios,
    )
    
    # === Load fuel shares (keep these - needed for fuel mix calculations) ===
    print("Loading fuel shares...")
    
    # BF + OHF
    fuel_shares_bf_ohf = extract_all_fuels(share_fuel_bf_ohf, target_years, scenarios)
    
    # BF + BOF
    fuel_shares_bf_bof = extract_all_fuels(share_fuel_bf_bof, target_years, scenarios)
    
    # DR + EAF
    fuel_shares_dr_eaf = extract_all_fuels(share_fuel_dr_eaf, target_years, scenarios)
    
    # Scrap EAF
    fuel_shares_scrap_eaf = extract_all_fuels(share_fuel_scrap_eaf, target_years, scenarios)
    
    # === Build fuel share DataFrames ===
    print("Building fuel share rows...")
    df_fuel_bf_ohf = build_steel_fuel_share_rows(
        fuel_shares_bf_ohf, "bf_ohf", "BF+OHF fuel share",
        countries, base_year, target_years, scenarios
    )
    df_fuel_bf_bof = build_steel_fuel_share_rows(
        fuel_shares_bf_bof, "bf_bof", "BF+BOF fuel share",
        countries, base_year, target_years, scenarios
    )
    df_fuel_dr_eaf = build_steel_fuel_share_rows(
        fuel_shares_dr_eaf, "dr_eaf", "DR+EAF fuel share",
        countries, base_year, target_years, scenarios
    )
    df_fuel_scrap_eaf = build_steel_fuel_share_rows(
        fuel_shares_scrap_eaf, "scrap_eaf", "Scrap EAF fuel share",
        countries, base_year, target_years, scenarios
    )
    
    # === Build base intensity DataFrames (2020 only, aggregated per route) ===
    print("Building base year intensity rows...")
    df_intensity_bf_ohf = build_steel_intensity_base_rows(
        intensity_bf_ohf, "bf_ohf", 
        "Energy intensity of blast furnaces + open hearth furnaces",
        countries, base_year, scenarios
    )
    df_intensity_bf_bof = build_steel_intensity_base_rows(
        intensity_bf_bof, "bf_bof",
        "Energy intensity of blast furnaces + basic oxygen furnaces",
        countries, base_year, scenarios
    )
    df_intensity_dr_eaf = build_steel_intensity_base_rows(
        intensity_dr_eaf, "dr_eaf",
        "Energy intensity of direct reduction + electric arc furnaces",
        countries, base_year, scenarios
    )
    df_intensity_scrap_eaf = build_steel_intensity_base_rows(
        intensity_scrap_eaf, "scrap_eaf",
        "Energy intensity of scrap electric arc furnaces",
        countries, base_year, scenarios
    )
    
    # === Build intensity CAGR rows ===
    print("Building energy intensity CAGR rows...")
    df_intensity_cagr = build_steel_intensity_cagr_rows(
        countries, base_year, target_years, scenarios
    )
    
    # === Concatenate all metrics ===
    print("Concatenating all metrics...")
    df_all = pd.concat(
        [
            df_steel_prod,
            df_steel_cagr,
            df_intensity_cagr,
            df_steel_routes,
            df_fuel_bf_ohf,
            df_fuel_bf_bof,
            df_fuel_dr_eaf,
            df_fuel_scrap_eaf,
            df_intensity_bf_ohf,
            df_intensity_bf_bof,
            df_intensity_dr_eaf,
            df_intensity_scrap_eaf,
            # TODO: Add other sectors (cement, chemicals, etc.)
        ],
        ignore_index=True,
    )
    
    # === Write to CSV ===
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"\nWriting to: {output_path}")
    df_all.to_csv(output_path, index=False)
    
    print(f"✓ Successfully generated INDUSTRY_CONFIG.csv")
    print(f"  Total rows: {len(df_all)}")
    print(f"  Columns: {list(df_all.columns)}")
    print(f"  Countries: {countries}")
    
    # === Display intensity preview ===
    print_intensity_preview(df_all, countries[0], base_year, target_years, scenarios)
    
    print(f"\n{'='*60}")
    print(f"INDUSTRY_CONFIG.csv generation complete!")
    print(f"{'='*60}")
    
    return df_all


def print_intensity_preview(df_config, sample_country, base_year, target_years, scenarios):
    """
    Calculate and display final intensity values for preview.
    
    Shows how base intensities are modified by CAGR over time.
    These values are NOT stored in the config - they're calculated for transparency.
    
    Args:
        df_config: Generated config DataFrame
        sample_country: Country to use for preview
        base_year: Base year
        target_years: List of target years
        scenarios: List of scenarios
    """
    print(f"\n{'='*60}")
    print(f"INTENSITY PREVIEW (Calculated, Not Stored)")
    print(f"Sample Country: {sample_country}")
    print(f"Formula: final_intensity = base_intensity × (1 + CAGR)^(years)")
    print(f"{'='*60}\n")
    
    # Get base intensities
    intensity_base = df_config[df_config['type'] == 'intensity_base'].copy()
    
    # Get intensity CAGR
    intensity_cagr = df_config[df_config['type'] == 'cagr'].copy()
    intensity_cagr = intensity_cagr[intensity_cagr['metric name'].str.contains('Energy intensity', na=False)]
    
    # Routes to preview
    routes = [
        "Energy intensity of blast furnaces + basic oxygen furnaces",
        "Energy intensity of direct reduction + electric arc furnaces",
        "Energy intensity of scrap electric arc furnaces",
    ]
    
    all_years = [base_year] + target_years
    
    for route in routes:
        print(f"\n{route}:")
        print(f"{'Year':<8} {'Scenario':<15} {'Base (MWh/t)':<15} {'CAGR':<10} {'Final (MWh/t)':<15}")
        print("-" * 70)
        
        # Get base intensity for this route
        base_rows = intensity_base[intensity_base['metric name'] == route]
        if base_rows.empty:
            continue
            
        base_value = base_rows[base_rows['year'] == base_year].iloc[0][sample_country]
        
        for year in all_years:
            for scenario in scenarios:
                # Calculate cumulative CAGR
                years_elapsed = year - base_year
                
                if years_elapsed == 0:
                    # Base year - no CAGR applied
                    final_value = base_value
                    cagr_display = "N/A"
                else:
                    # Get average CAGR for this period
                    cagr_rows = intensity_cagr[
                        (intensity_cagr['metric name'] == route) &
                        (intensity_cagr['scenario'] == scenario)
                    ]
                    
                    if not cagr_rows.empty:
                        # Use first CAGR value (they're all the same per scenario)
                        avg_cagr = cagr_rows.iloc[0][sample_country]
                        final_value = base_value * ((1 + avg_cagr) ** years_elapsed)
                        cagr_display = f"{avg_cagr:+.3f}"
                    else:
                        final_value = base_value
                        cagr_display = "0.000"
                
                print(f"{year:<8} {scenario:<15} {base_value:<15.2f} {cagr_display:<10} {final_value:<15.2f}")
    
    print(f"\n{'='*60}")
    print("Note: Only base intensities and CAGR are stored in config.")
    print("Final intensities are calculated during demand generation.")
    print(f"{'='*60}\n")


def main():
    """
    Main entry point for generating INDUSTRY_CONFIG.csv.
    
    Run this script directly to generate the configuration file:
        python generate_industry_config.py
    """
    # Define countries to process (matching build_config_industry.py)
    countries_to_process = ["Morocco", "Egypt", "South Africa", "Namibia"]
    
    # Generate the configuration
    df_config = generate_industry_config_csv(
        countries=countries_to_process,
        base_year=BASE_YEAR,
        target_years=TARGET_YEARS,
        scenarios=SCENARIOS,
    )


if __name__ == "__main__":
    main()
