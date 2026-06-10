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
    - Columns: ['metric_1', 'metric_2', 'metric_3', 'metric_4', 'year', 'scenario', 'units'] + country_list
      * metric_1: Industry sector (e.g., 'iron and steel', 'ammonia')
      * metric_2: Type (e.g., 'production', 'cagr', 'technology_route', 'fuel_share', 'intensity_base')
      * metric_3: Technology route or metric name (e.g., 'BF+BOF', 'SMR+HB', 'Steel production per year')
      * metric_4: Sub-metric (e.g., fuel type for fuel_share rows, empty for others)
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
    - ammonia_volumes.csv: Production volumes by pathway (conventional/green)

TODO - CLEANUP AFTER WORKFLOW COMPLETE:
    Once all sectors are integrated and final energy demand calculation is working,
    DELETE these deprecated scripts:
    1. industry/build_config_industry.py (OLD workflow - replaced by this file)
    2. industry/scripts/chemical_and_petrochemical/ammonia/build_ammonia.py (OLD - replaced by build_config_rows_ammonia.py)
    
    These files are no longer needed with the new consolidated workflow.
"""

from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime

# === Import sector-specific configuration builders ===
from industry.scripts.iron_and_steel.generate_steel_config import generate_steel_config_rows
from industry.scripts.chemical_and_petrochemical.ammonia.generate_ammonia_config import generate_ammonia_config_rows
from industry.scripts.chemical_and_petrochemical.HVC.generate_hvc_config import generate_hvc_config_rows
from industry.scripts.non_metallic_minerals.generate_cement_config import generate_cement_config_rows
from industry.scripts.paper_and_pulp.generate_paper_pulp_config import generate_paper_pulp_config_rows

# === Import simple sector configuration builders ===
from industry.scripts.food_and_tobacco.generate_food_tobacco_config import generate_food_tobacco_config_rows
from industry.scripts.construction.generate_construction_config import generate_construction_config_rows
from industry.scripts.machinery.generate_machinery_config import generate_machinery_config_rows
from industry.scripts.mining_and_quarrying.generate_mining_quarrying_config import generate_mining_quarrying_config_rows
from industry.scripts.non_ferrous_metals.generate_aluminium_config import generate_aluminium_config
from industry.scripts.textile_and_leather.generate_textile_leather_config import generate_textile_leather_config_rows
from industry.scripts.transport_equipment.generate_transport_equipment_config import generate_transport_equipment_config_rows
from industry.scripts.wood_and_wood_products.generate_wood_products_config import generate_wood_products_config_rows
from industry.scripts.other_industries.generate_other_industries_config import generate_other_industries_config_rows
from industry.scripts.calculate_process_emissions import generate_process_emissions_reports

# === Import helpers ===
from industry.utils.helpers import DEFAULT_TARGET_YEARS
from industry.utils.cagr_reporting import export_cagr_reports

# === Module-level constants ===
BASE_YEAR = 2020
TARGET_YEARS = DEFAULT_TARGET_YEARS
SCENARIOS = ["BAU", "Progressive", "Optimistic"]
INDUSTRY_CONFIG_FILE = "industry_config.csv"

BASE_DIR = Path(__file__).resolve().parents[1]  # Go up from scripts/ to industry/
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
    
    # HVC (Chemical and Petrochemical)
    df_hvc = generate_hvc_config_rows(
        countries, base_year, target_years, scenarios
    )
    print(f"✓ HVC configuration complete: {len(df_hvc)} rows")
    
    # Cement (Non-metallic Minerals)
    df_cement = generate_cement_config_rows(
        countries, base_year, target_years, scenarios
    )
    print(f"✓ Cement configuration complete: {len(df_cement)} rows")
    
    # Paper & Pulp
    df_paper_pulp = generate_paper_pulp_config_rows(
        countries, base_year, target_years, scenarios
    )
    print(f"✓ Paper & pulp configuration complete: {len(df_paper_pulp)} rows")
    
    # Aluminium (Non-ferrous Metals)
    df_aluminium = generate_aluminium_config(countries)
    print(f"✓ Aluminium configuration complete: {len(df_aluminium)} rows")
    
    # === Simple sectors (fuel shares only) ===
    print("\n" + "="*60)
    print("GENERATING SIMPLE SECTOR CONFIGURATIONS")
    print("="*60)
    
    df_food_tobacco = generate_food_tobacco_config_rows(
        countries, base_year, target_years, scenarios
    )
    print(f"✓ Food and tobacco: {len(df_food_tobacco)} rows")
    
    df_construction = generate_construction_config_rows(
        countries, base_year, target_years, scenarios
    )
    print(f"✓ Construction: {len(df_construction)} rows")
    
    df_machinery = generate_machinery_config_rows(
        countries, base_year, target_years, scenarios
    )
    print(f"✓ Machinery: {len(df_machinery)} rows")
    
    df_mining = generate_mining_quarrying_config_rows(
        countries, base_year, target_years, scenarios
    )
    print(f"✓ Mining and quarrying: {len(df_mining)} rows")
    
    df_textile = generate_textile_leather_config_rows(
        countries, base_year, target_years, scenarios
    )
    print(f"✓ Textile and leather: {len(df_textile)} rows")
    
    df_transport_eq = generate_transport_equipment_config_rows(
        countries, base_year, target_years, scenarios
    )
    print(f"✓ Transport equipment: {len(df_transport_eq)} rows")
    
    df_wood = generate_wood_products_config_rows(
        countries, base_year, target_years, scenarios
    )
    print(f"✓ Wood and wood products: {len(df_wood)} rows")
    
    df_other_industries = generate_other_industries_config_rows(
        countries, base_year, target_years, scenarios
    )
    print(f"✓ Other industries (Industry n.e.s): {len(df_other_industries)} rows")
    
    # === Concatenate all sectors ===
    df_all = pd.concat(
        [
            df_steel,
            df_ammonia,
            df_hvc,
            df_cement,
            df_paper_pulp,
            df_food_tobacco,
            df_construction,
            df_machinery,
            df_mining,
            df_aluminium,
            df_textile,
            df_transport_eq,
            df_wood,
            df_other_industries,
        ],
        ignore_index=True,
    )
    
    # === Apply standardization FIRST (before projection files) ===
    # 1. Make all metric_1 lowercase
    df_all['metric_1'] = df_all['metric_1'].str.lower()
    
    # 2. Rename 'industry n.e.s' to 'other'
    df_all['metric_1'] = df_all['metric_1'].replace('industry n.e.s', 'other')
    
    # 3. Make all metric_2 lowercase
    df_all['metric_2'] = df_all['metric_2'].str.lower()
    
    # 4. Make all metric_3 lowercase
    df_all['metric_3'] = df_all['metric_3'].str.lower()
    
    # 5. Rename 'energy_intensity' to 'intensity_base' in metric_2
    df_all['metric_2'] = df_all['metric_2'].replace('energy_intensity', 'intensity_base')
    
    # 6. Standardize units to t/a for production
    unit_mapping = {
        't/year': 't/a',
        'tonnes': 't/a',
        '100t/a': 't/a',  # Will need to multiply values by 100
    }
    
    # For 100t/a -> t/a conversion, multiply production values by 100
    mask_100t = df_all['units'] == '100t/a'
    if mask_100t.any():
        country_cols = [c for c in df_all.columns if c not in ['metric_1', 'metric_2', 'metric_3', 'metric_4', 'year', 'scenario', 'units']]
        df_all.loc[mask_100t, country_cols] = df_all.loc[mask_100t, country_cols] * 100
    
    df_all['units'] = df_all['units'].replace(unit_mapping)
    
    # === Auto-generate derivative files (AFTER standardization) ===
    # Create interim_data folder for auto-generated files
    interim_dir = BASE_DIR / "output_data" / "interim_data"
    interim_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*60}")
    print(f"AUTO-GENERATING STEEL INTENSITY PROJECTIONS")
    print(f"{'='*60}")
    steel_intensity_proj_path = interim_dir / "steel_intensity_projections.csv"
    build_steel_intensity_projections(
        df_all, countries, base_year, target_years, scenarios, steel_intensity_proj_path
    )
    
    print(f"\n{'='*60}")
    print(f"AUTO-GENERATING AMMONIA INTENSITY PROJECTIONS")
    print(f"{'='*60}")
    ammonia_intensity_proj_path = interim_dir / "ammonia_intensity_projections.csv"
    build_ammonia_intensity_projections(
        df_all, countries, base_year, target_years, scenarios, ammonia_intensity_proj_path
    )
    
    print(f"\n{'='*60}")
    print(f"AUTO-GENERATING STEEL VOLUMES")
    print(f"{'='*60}")
    volumes_path = interim_dir / "steel_volumes.csv"
    build_steel_volumes(
        df_all, countries, base_year, target_years, scenarios, volumes_path
    )
    
    export_cagr_reports(
        df_config=df_all,
        output_dir=interim_dir,
        countries=countries,
    )
    
    print(f"\n{'='*60}")
    print(f"AUTO-GENERATING PROCESS EMISSIONS")
    print(f"{'='*60}")
    generate_process_emissions_reports(
        df_config=df_all,
        output_dir=interim_dir,
        years=target_years,
        scenarios=scenarios,
    )
    
    # === Write to CSV ===
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"\nWriting to: {output_path}")
    df_all.to_csv(output_path, index=False)
    
    print(f"\n{'='*60}")
    print(f"INDUSTRY_CONFIG.csv GENERATION COMPLETE!")
    print(f"{'='*60}")
    print(f"  Total rows: {len(df_all)}")
    print(f"  Columns: {list(df_all.columns)}")
    print(f"  Countries: {countries}")
    
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
    
    # Get base intensities and CAGR from config (now lowercased)
    intensity_base = df_config[df_config['metric_2'] == 'intensity_base'].copy()
    intensity_cagr = df_config[df_config['metric_2'] == 'cagr'].copy()
    # Filter for intensity CAGR rows (not production CAGR)
    intensity_routes = [
        "energy intensity of bf+bof",
        "energy intensity of dr+eaf",
        "energy intensity of scrap eaf",
        "energy intensity of casting, rolling & finishing"
    ]
    intensity_cagr = intensity_cagr[intensity_cagr['metric_3'].isin(intensity_routes)]
    
    # Routes to process (lowercase after standardization)
    routes = [
        ("energy intensity of bf+bof", "bf+bof"),
        ("energy intensity of dr+eaf", "dr+eaf"),
        ("energy intensity of scrap eaf", "scrap eaf"),
        ("energy intensity of casting, rolling & finishing", "casting, rolling & finishing"),
    ]
    
    all_years = [base_year] + target_years
    rows = []
    
    for cagr_route_name, base_route_name in routes:
        # Get base intensity for this route (using base route name)
        base_rows = intensity_base[intensity_base['metric_3'] == base_route_name]
        if base_rows.empty:
            continue
        
        for scenario in scenarios:
            # Get base value (same for all scenarios at base year)
            base_row = base_rows[base_rows['year'] == base_year].iloc[0]
            
            # Get CAGR for this route and scenario (using CAGR route name)
            cagr_rows = intensity_cagr[
                (intensity_cagr['metric_3'] == cagr_route_name) &
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
                    'route': cagr_route_name,  # Use full CAGR route name (includes "Energy intensity of")
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
    Generate ammonia_intensity_projections.csv with year-by-year intensity projections.
    
    Unlike steel (base + CAGR), ammonia intensities are pre-calculated per year
    in the intensity functions. We generate projections directly from those functions
    since INDUSTRY_CONFIG.csv only stores the base year.
    
    NOTE: Intensities aggregate all fuel types. Future enhancement should add
    fuel-specific intensities for better modeling flexibility.
    
    Args:
        df_config: Generated config DataFrame (used to validate base year values)
        countries: List of country names
        base_year: Base year
        target_years: List of target years
        scenarios: List of scenarios
        output_path: Path to write projections CSV
    """
    print(f"\nGenerating ammonia intensity projections...")
    
    # Import intensity functions
    from industry.scripts.chemical_and_petrochemical.ammonia.build_intensities_ammonia import (
        intensity_ammonia_smr_hb,
        intensity_ammonia_renewable,
    )
    
    # Get intensity data directly from functions (all years)
    intensity_smr = intensity_ammonia_smr_hb(target_years=target_years, scenarios=scenarios)
    intensity_renewable = intensity_ammonia_renewable(target_years=target_years, scenarios=scenarios)
    
    # Route names (lowercase to match standardized config)
    pathways = [
        ("energy intensity of smr+hb", intensity_smr),
        ("energy intensity of renewable synthesis", intensity_renewable),
    ]
    
    all_years = [base_year] + target_years
    rows = []
    
    for route_name, intensity_data in pathways:
        for year in all_years:
            for scenario in scenarios:
                # Sum intensities across all fuels for this year/scenario
                total_intensity = 0.0
                for fuel, year_data in intensity_data.items():
                    if year in year_data and scenario in year_data[year]:
                        total_intensity += year_data[year][scenario]
                
                row = {
                    'route': route_name,
                    'scenario': scenario,
                    'year': year,
                    'units': 'MWh/t',
                }
                
                # Same intensity for all countries (not country-specific)
                for country in countries:
                    row[country] = round(total_intensity, 4)
                
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
    metric_4: str = '',
) -> pd.Series:
    """
    Extract a single metric row for specified countries.
    
    Returns a Series with country names as index and values.
    """
    mask = (
        (df["metric_1"] == industry_sector) &
        (df["metric_2"] == metric_type) &
        (df["metric_3"] == metric_name) &
        (df["metric_4"] == metric_4) &
        (df["scenario"] == scenario) &
        (df["year"] == year)
    )
    
    rows = df[mask]
    if len(rows) == 0:
        raise ValueError(
            f"No data found for: {industry_sector} / {metric_type} / {metric_name} / "
            f"{metric_4} / {scenario} / {year}"
        )
    if len(rows) > 1:
        raise ValueError(
            f"Multiple rows found for: {industry_sector} / {metric_type} / {metric_name} / "
            f"{metric_4} / {scenario} / {year}"
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
            # Extract metrics for this scenario/year (lowercase after standardization)
            total_prod = extract_metric(
                df_config, "iron and steel", "production", "steel production per year", 
                scenario, year, countries
            )
            
            primary_share = extract_metric(
                df_config, "iron and steel", "technology_route", "primary steel production", 
                scenario, year, countries
            )
            
            secondary_share = extract_metric(
                df_config, "iron and steel", "technology_route", "secondary steel production", 
                scenario, year, countries
            )
            
            bf_bof_share = extract_metric(
                df_config, "iron and steel", "technology_route",
                "bf+bof",
                scenario, year, countries
            )
            
            dr_eaf_share = extract_metric(
                df_config, "iron and steel", "technology_route",
                "dr+eaf",
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
