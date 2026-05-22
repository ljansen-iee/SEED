"""
Generate INDUSTRY_CONFIG.csv with all country parameters in long format.

This is a THIN ORCHESTRATOR that coordinates sector-specific configuration builders.
Each sector has its own module in scripts/<sector>/ for maintainability.

Architecture:
    - This file: Orchestration, CSV writing, auto-generation of derivative files
    - scripts/iron_and_steel/build_config_rows_steel.py: All steel logic
    - scripts/chemical_and_petrochemical/ammonia/build_config_rows_ammonia.py: Ammonia logic
    - helpers.py: Generic row builders and utilities (see "CONFIGURATION BUILDERS" section)

Structure:
    - Columns: ['industry_sector', 'type', 'metric name', 'year', 'scenario', 'units'] + country_list
    - Years: 2020 (base), 2030, 2035, 2040, 2045, 2050
    - Scenarios: BAU, Progressive, Optimistic
    - Sectors: iron and steel, ammonia, cement, etc.
    - Metric types:
        - production: Physical production values (tons/year)
        - cagr: Compound annual growth rates (decimal)
        - technology_route: Technology route shares (fraction)
        - fuel_share: Fuel shares per route (fraction)
        - intensity_base: Base energy intensities (MWh/ton, 2020 only)

Separate Output Files (Auto-Generated):
    - steel_intensity_projections.csv: Projected steel intensities for all years
    - ammonia_intensity_projections.csv: Projected ammonia intensities for all years
    - steel_volumes.csv: Production volumes by technology pathway
    - ammonia_volumes.csv: Production volumes by pathway (conventional/green) with GALT/GAIR indicators
"""

from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime

# === Import sector-specific configuration builders ===
from scripts.iron_and_steel.build_config_rows_steel import generate_steel_config_rows
from scripts.chemical_and_petrochemical.ammonia.build_config_rows_ammonia import generate_ammonia_config_rows

# === Import helpers ===
from helpers import DEFAULT_TARGET_YEARS

# === Module-level constants ===
BASE_YEAR = 2020
TARGET_YEARS = DEFAULT_TARGET_YEARS
SCENARIOS = ["BAU", "Progressive", "Optimistic"]
INDUSTRY_CONFIG_FILE = "industry_config.csv"

BASE_DIR = Path(__file__).resolve().parent
INDUSTRY_CONFIG_PATH = BASE_DIR / INDUSTRY_CONFIG_FILE


# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================

def generate_industry_config_csv(
    countries,
    base_year=2020,
    target_years=None,
    scenarios=None,
    output_path=None,
):
    """
    Generate the consolidated INDUSTRY_CONFIG.csv file.
    
    THIN ORCHESTRATOR: Calls sector-specific builders and concatenates results.
    
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
    
    # === Generate sector-specific configurations ===
    
    # Iron and Steel
    print("\n" + "="*60)
    print("GENERATING IRON AND STEEL CONFIGURATION")
    print("="*60)
    df_steel = generate_steel_config_rows(
        countries, base_year, target_years, scenarios
    )
    print(f"✓ Steel configuration complete: {len(df_steel)} rows")
    
    # Ammonia (Chemical and Petrochemical)
    print("\n" + "="*60)
    print("GENERATING AMMONIA CONFIGURATION")
    print("="*60)
    df_ammonia = generate_ammonia_config_rows(
        countries, base_year, target_years, scenarios
    )
    print(f"✓ Ammonia configuration complete: {len(df_ammonia)} rows")
    
    # TODO: Add other sectors
    # df_cement = generate_cement_config_rows(countries, base_year, target_years, scenarios)
    
    # === Concatenate all sectors ===
    print("\nConcatenating all sectors...")
    df_all = pd.concat(
        [
            df_steel,
            df_ammonia,
            # df_cement,   # TODO
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
    
    # === Auto-generate derivative files ===
    print(f"\n{'='*60}")
    print(f"AUTO-GENERATING STEEL INTENSITY PROJECTIONS")
    print(f"{'='*60}")
    steel_intensity_proj_path = BASE_DIR / "output_data" / "steel_intensity_projections.csv"
    build_steel_intensity_projections(
        df_all, countries, base_year, target_years, scenarios, steel_intensity_proj_path
    )
    
    print(f"\n{'='*60}")
    print(f"AUTO-GENERATING AMMONIA INTENSITY PROJECTIONS")
    print(f"{'='*60}")
    ammonia_intensity_proj_path = BASE_DIR / "output_data" / "ammonia_intensity_projections.csv"
    build_ammonia_intensity_projections(
        df_all, countries, base_year, target_years, scenarios, ammonia_intensity_proj_path
    )
    
    print(f"\n{'='*60}")
    print(f"AUTO-GENERATING STEEL VOLUMES")
    print(f"{'='*60}")
    volumes_path = BASE_DIR / "output_data" / "steel_volumes.csv"
    build_steel_volumes(
        df_all, countries, base_year, target_years, scenarios, volumes_path
    )
    
    print(f"\n{'='*60}")
    print(f"INDUSTRY_CONFIG.csv generation complete!")
    print(f"{'='*60}")
    
    return df_all


# ============================================================================
# HELPER FUNCTIONS (Generic Utilities)
# ============================================================================

def build_steel_intensity_projections(
    df_config,
    countries,
    base_year,
    target_years,
    scenarios,
    output_path,
):
    """
    Generate steel_intensity_projections.csv from INDUSTRY_CONFIG.csv.
    
    Reads base intensities and CAGR from config, calculates projected intensities
    for all years. This separates INPUT (config) from OUTPUT (projections).
    
    Formula: intensity[year] = base_intensity × (1 + CAGR)^(year - base_year)
    
    Args:
        df_config: Generated config DataFrame
        countries: List of country names
        base_year: Base year
        target_years: List of target years
        scenarios: List of scenarios
        output_path: Path to write projections CSV
    """
    print(f"\nGenerating steel intensity projections...")
    
    # Get base intensities and CAGR from config
    intensity_base = df_config[df_config['type'] == 'intensity_base'].copy()
    intensity_cagr = df_config[df_config['type'] == 'cagr'].copy()
    intensity_cagr = intensity_cagr[intensity_cagr['metric name'].str.contains('Energy intensity', na=False)]
    
    # Routes to process
    routes = [
        "Energy intensity of blast furnaces + basic oxygen furnaces",
        "Energy intensity of direct reduction + electric arc furnaces",
        "Energy intensity of scrap electric arc furnaces",
        "Energy intensity of casting, rolling & finishing",
    ]
    
    all_years = [base_year] + target_years
    rows = []
    
    for route in routes:
        # Get base intensity for this route
        base_rows = intensity_base[intensity_base['metric name'] == route]
        if base_rows.empty:
            continue
        
        for scenario in scenarios:
            # Get base value (same for all scenarios at base year)
            base_row = base_rows[base_rows['year'] == base_year].iloc[0]
            
            # Get CAGR for this route and scenario
            cagr_rows = intensity_cagr[
                (intensity_cagr['metric name'] == route) &
                (intensity_cagr['scenario'] == scenario)
            ]
            
            # Use first CAGR value (constant across periods)
            if not cagr_rows.empty:
                cagr_rate = cagr_rows.iloc[0][countries[0]]  # CAGR is same for all countries
            else:
                cagr_rate = 0.0
            
            # Generate projected values for all years
            for year in all_years:
                years_elapsed = year - base_year
                
                row = {
                    'route': route,
                    'scenario': scenario,
                    'year': year,
                    'units': 'MWh/t',
                }
                
                # Calculate projected intensity for each country
                for country in countries:
                    base_intensity = base_row[country]
                    if years_elapsed == 0:
                        projected_intensity = base_intensity
                    else:
                        projected_intensity = base_intensity * ((1 + cagr_rate) ** years_elapsed)
                    
                    row[country] = round(projected_intensity, 4)
                
                rows.append(row)
    
    df_projections = pd.DataFrame(rows)
    df_projections = df_projections.sort_values(['route', 'scenario', 'year']).reset_index(drop=True)
    
    # Write to CSV
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_projections.to_csv(output_path, index=False)
    
    print(f"✓ Written → {output_path}")
    print(f"  Total rows: {len(df_projections)}")
    print(f"  Structure: route | scenario | year | units | {' | '.join(countries)}")
    
    # Display preview
    print(f"\nSample (Morocco, BAU):")
    sample = df_projections[
        (df_projections['scenario'] == 'BAU') &
        (df_projections['year'].isin([2020, 2030, 2050]))
    ]
    for _, row in sample.iterrows():
        print(f"  {row['year']} | {row['route'][:30]:30s} | {row[countries[0]]:6.2f} MWh/t")


def build_ammonia_intensity_projections(
    df_config,
    countries,
    base_year,
    target_years,
    scenarios,
    output_path,
):
    """
    Generate ammonia_intensity_projections.csv from INDUSTRY_CONFIG.csv.
    
    Extracts intensity values for ammonia production routes across all years
    and scenarios. Unlike steel (which uses base + CAGR), ammonia intensities
    are pre-calculated per year in the intensity functions.
    
    Args:
        df_config: Generated config DataFrame
        countries: List of country names
        base_year: Base year
        target_years: List of target years
        scenarios: List of scenarios
        output_path: Path to write projections CSV
    """
    print(f"\nGenerating ammonia intensity projections...")
    
    # Get base intensities from config (these are per fuel, so we need to aggregate)
    intensity_base = df_config[
        (df_config['industry_sector'] == 'ammonia') & 
        (df_config['type'] == 'intensity_base')
    ].copy()
    
    # Routes to process (these are the metric labels from build_config_rows_ammonia.py)
    routes = {
        "intensity_ammonia_smr_hb": "Ammonia SMR + Haber-Bosch",
        "intensity_ammonia_renewable": "Ammonia renewable synthesis",
    }
    
    all_years = [base_year] + target_years
    rows = []
    
    for metric_label, route_name in routes.items():
        # Get all intensity rows for this route
        route_rows = intensity_base[intensity_base['metric name'] == metric_label]
        
        if route_rows.empty:
            continue
        
        # For each scenario and year combination
        for scenario in scenarios:
            for year in all_years:
                # Get the intensity value for this year and scenario
                year_rows = route_rows[
                    (route_rows['year'] == year) &
                    (route_rows['scenario'] == scenario)
                ]
                
                if year_rows.empty:
                    continue
                
                # Extract first row (should be unique per year/scenario)
                intensity_row = year_rows.iloc[0]
                
                row = {
                    'route': route_name,
                    'scenario': scenario,
                    'year': year,
                    'units': 'MWh/t',
                }
                
                # Extract intensity values for each country
                for country in countries:
                    if country in intensity_row:
                        row[country] = round(float(intensity_row[country]), 4)
                    else:
                        row[country] = 0.0
                
                rows.append(row)
    
    df_projections = pd.DataFrame(rows)
    df_projections = df_projections.sort_values(['route', 'scenario', 'year']).reset_index(drop=True)
    
    # Write to CSV
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_projections.to_csv(output_path, index=False)
    
    print(f"✓ Written → {output_path}")
    print(f"  Total rows: {len(df_projections)}")
    print(f"  Structure: route | scenario | year | units | {' | '.join(countries)}")
    
    # Display preview
    if len(df_projections) > 0:
        print(f"\nSample ({countries[0]}, BAU):")
        sample = df_projections[
            (df_projections['scenario'] == 'BAU') &
            (df_projections['year'].isin([2020, 2030, 2050]))
        ]
        for _, row in sample.iterrows():
            print(f"  {row['year']} | {row['route']:35s} | {row[countries[0]]:6.2f} MWh/t")


def extract_metric(
    df: pd.DataFrame,
    industry_sector: str,
    metric_type: str,
    metric_name: str,
    scenario: str,
    year: int,
    countries: list,
) -> pd.Series:
    """
    Extract a single metric row for specified countries.
    
    Returns a Series with country names as index and values.
    """
    mask = (
        (df["industry_sector"] == industry_sector) &
        (df["type"] == metric_type) &
        (df["metric name"] == metric_name) &
        (df["scenario"] == scenario) &
        (df["year"] == year)
    )
    
    rows = df[mask]
    if len(rows) == 0:
        raise ValueError(
            f"No data found for: {industry_sector} / {metric_type} / {metric_name} / "
            f"{scenario} / {year}"
        )
    if len(rows) > 1:
        raise ValueError(
            f"Multiple rows found for: {industry_sector} / {metric_type} / {metric_name} / "
            f"{scenario} / {year}"
        )
    
    # Get the row and extract country columns
    row = rows.iloc[0]
    return row[countries]


def build_steel_volumes(
    df_config,
    countries,
    base_year,
    target_years,
    scenarios,
    output_path,
):
    """
    Generate steel_volumes.csv from INDUSTRY_CONFIG.csv.
    
    Calculates steel production volumes split by technology pathway:
    - Exogenous conventional path (BF+BOF)
    - Endogenous green path (DR+EAF + secondary scrap)
    
    Args:
        df_config: Generated config DataFrame
        countries: List of country names
        base_year: Base year
        target_years: List of target years
        scenarios: List of scenarios
        output_path: Path to write volumes CSV
    """
    print(f"\nGenerating steel volumes...")
    
    all_years = [base_year] + target_years
    rows = []
    
    for scenario in scenarios:
        for year in all_years:
            # Extract metrics for this scenario/year
            total_prod = extract_metric(
                df_config, "iron and steel", "production", "Steel production per year", 
                scenario, year, countries
            )
            
            primary_share = extract_metric(
                df_config, "iron and steel", "technology_route", "Share of primary steel", 
                scenario, year, countries
            )
            
            secondary_share = extract_metric(
                df_config, "iron and steel", "technology_route", "Share of secondary steel", 
                scenario, year, countries
            )
            
            bf_bof_share = extract_metric(
                df_config, "iron and steel", "technology_route",
                "Share of blast furnace + basic oxygen furnace for steel making",
                scenario, year, countries
            )
            
            dr_eaf_share = extract_metric(
                df_config, "iron and steel", "technology_route",
                "Share of direct reduction + electric arc furnace for steel making",
                scenario, year, countries
            )
            
            # Calculate volumes for each country
            for country in countries:
                total = float(total_prod[country])
                p_share = float(primary_share[country])
                s_share = float(secondary_share[country])
                bf_share = float(bf_bof_share[country])
                dr_share = float(dr_eaf_share[country])
                
                # Calculate steel volumes by pathway
                primary_steel = total * p_share
                secondary_steel = total * s_share
                
                # Primary routes (shares sum to 1.0 within primary)
                bf_bof_primary = primary_steel * bf_share
                dr_eaf_primary = primary_steel * dr_share
                
                # Technology pathways
                # Conventional: BF+BOF only (fossil-fuel intensive)
                exog_conv = bf_bof_primary
                # Green: DR+EAF + Secondary scrap (electricity-based, renewable-ready)
                endog_green = dr_eaf_primary + secondary_steel
                
                rows.append({
                    "scenario": scenario,
                    "country": country,
                    "year": year,
                    "total_steel_production": round(total, 2),
                    "primary_steel": round(primary_steel, 2),
                    "secondary_steel": round(secondary_steel, 2),
                    "bf_bof_primary": round(bf_bof_primary, 2),
                    "dr_eaf_primary": round(dr_eaf_primary, 2),
                    "exog_steel_conv_path": round(exog_conv, 2),
                    "endog_green_steel_path": round(endog_green, 2),
                })
    
    df_volumes = pd.DataFrame(rows)
    df_volumes = df_volumes.sort_values(["scenario", "country", "year"]).reset_index(drop=True)
    
    # Write output
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_volumes.to_csv(output_path, index=False)
    
    print(f"✓ Written → {output_path}")
    print(f"  Total rows: {len(df_volumes)}")
    print(f"  Structure: scenario | country | year | total | primary | secondary | bf_bof | dr_eaf | exog | endog")
    
    # Display preview
    print(f"\nSample (Morocco, BAU, 2020 & 2050):")
    sample = df_volumes[
        (df_volumes['country'] == countries[0]) &
        (df_volumes['scenario'] == 'BAU') &
        (df_volumes['year'].isin([2020, 2050]))
    ]
    for _, row in sample.iterrows():
        print(f"  {row['year']} | Total: {row['total_steel_production']:,.0f} t | "
              f"Exog: {row['exog_steel_conv_path']:,.0f} t | "
              f"Endog: {row['endog_green_steel_path']:,.0f} t")


def main():
    """
    Main entry point for generating INDUSTRY_CONFIG.csv.
    
    Run this script directly to generate the configuration file:
        python generate_industry_config.py
    """
    # Define countries to process
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
