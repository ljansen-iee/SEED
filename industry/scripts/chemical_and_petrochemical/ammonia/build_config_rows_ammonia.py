"""
Ammonia sector configuration row builders.

This module contains all ammonia-specific logic for generating configuration rows
for INDUSTRY_CONFIG.csv. This includes:
- CAGR calculation from UNSD historical data
- Local production projections
- Import volume tracking
- Technology pathway shares (SMR+Haber-Bosch vs renewable synthesis)
- Import reallocation shares (GAIR indicator)
- Fuel shares per pathway
- Energy intensities per pathway
- Ammonia volumes (pathway splits with GALT/GAIR indicators)

This modular structure follows the steel sector pattern, allowing easy maintenance
and testing of ammonia logic independently from other sectors.

Key indicators:
- GALT (Green Ammonia Local Transformation): share of local production using green synthesis
- GAIR (Green Ammonia Import Reallocation): share of imports reallocated to local green production
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional

# Import ammonia-specific data libraries
from industry.scripts.chemical_and_petrochemical.ammonia.build_ammonia_volumes import (
    load_undata,
    build_all_scenarios,
    GALT_ANCHORS,
    GAIR_ANCHORS,
    SCENARIO_MAPPING,
    PROJECTION_YEARS,
    AMMONIA_MWH_PER_TON,
    BASE_YEAR as AMMONIA_BASE_YEAR,
)
from industry.scripts.chemical_and_petrochemical.ammonia.build_shares_ammonia import (
    share_fuel_ammonia_smr_hb,
    share_fuel_ammonia_renewable,
)
from industry.scripts.chemical_and_petrochemical.ammonia.build_intensities_ammonia import (
    intensity_ammonia_smr_hb,
    intensity_ammonia_renewable,
)

# Import helpers
try:
    # When running from root
    from industry.build_CAGR import get_final_energy_cagr_from_unsd
    from industry.helpers import (
        extract_all_fuels,
        build_fuel_share_rows,
        build_intensity_base_rows,
        build_production_rows_with_cagr,
        build_cagr_rows,
    )
except ImportError:
    # When running from industry folder directly
    from build_CAGR import get_final_energy_cagr_from_unsd
    from helpers import (
        extract_all_fuels,
        build_fuel_share_rows,
        build_intensity_base_rows,
        build_production_rows_with_cagr,
        build_cagr_rows,
    )


# ============================================================================
# CAGR CALCULATION
# ============================================================================

def calculate_ammonia_cagr_from_unsd(
    countries: List[str],
    scenarios: List[str],
    scenario_multipliers: Optional[Dict[str, float]] = None,
) -> Dict[str, Dict[str, float]]:
    """
    Calculate data-driven CAGR for ammonia production from historical UNSD data.
    
    This follows the same methodology as steel:
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
        >>> calculate_ammonia_cagr_from_unsd(["Morocco"], ["BAU", "Progressive", "Optimistic"])
        {'Morocco': {'BAU': 0.015, 'Progressive': 0.018, 'Optimistic': 0.0225}}
    """
    if scenario_multipliers is None:
        scenario_multipliers = {
            "BAU": 1.0,          # Business as usual: use historical trend
            "Progressive": 1.2,  # 20% growth acceleration
            "Optimistic": 1.5,   # 50% growth acceleration
        }
    
    ammonia_cagr = {}
    
    for country in countries:
        print(f"  Calculating CAGR for {country} from UNSD historical data...")
        
        # Get historical CAGR from UNSD data (chemical and petrochemical sector)
        try:
            historical_cagr = get_final_energy_cagr_from_unsd(country, "Chemical and petrochemical")
            
            if historical_cagr is None or historical_cagr == 0.0:
                print(f"    ⚠ No UNSD data for {country}, using fallback default: 1.5%")
                historical_cagr = 0.015  # Fallback to industry average
        except Exception as e:
            print(f"    ⚠ Error loading UNSD data for {country}: {e}")
            print(f"    Using fallback default: 1.5%")
            historical_cagr = 0.015
        
        # Apply scenario multipliers
        ammonia_cagr[country] = {}
        for scenario in scenarios:
            multiplier = scenario_multipliers.get(scenario, 1.0)
            cagr_value = historical_cagr * multiplier
            ammonia_cagr[country][scenario] = round(cagr_value, 6)
            print(f"    {scenario}: {cagr_value:.4%} (historical: {historical_cagr:.4%} × {multiplier})")
    
    return ammonia_cagr


# ============================================================================
# PRODUCTION ROWS
# ============================================================================

def build_ammonia_production_rows(
    countries: List[str],
    base_year: int,
    target_years: List[int],
    scenarios: List[str],
    cagr_dict: Dict[str, Dict[str, float]],
) -> pd.DataFrame:
    """
    Build ammonia local production rows from UNSD historical data with CAGR projections.
    
    Args:
        countries: List of country names
        base_year: Base year for projections (e.g., 2020)
        target_years: Future years to project (e.g., [2030, 2035, 2040, 2045, 2050])
        scenarios: List of scenario names
        cagr_dict: Dict of {country: {scenario: cagr_value}}
    
    Returns:
        DataFrame with production rows for all countries, years, and scenarios
    """
    # Load UNSD historical data
    hist_data = load_undata()
    
    # Get base year production values per country
    base_values = {}
    for country in countries:
        country_data = hist_data[hist_data["country"] == country]
        if len(country_data) == 0:
            print(f"  ⚠ No UNSD production data for {country}, using 0")
            base_values[country] = 0.0
            continue
        
        base_row = country_data[country_data["year"] == base_year]
        if len(base_row) == 0:
            # Use last available year before base_year
            available_years = country_data[country_data["year"] <= base_year]["year"]
            if len(available_years) == 0:
                print(f"  ⚠ No data before {base_year} for {country}, using 0")
                base_values[country] = 0.0
                continue
            last_year = available_years.max()
            base_row = country_data[country_data["year"] == last_year]
            print(f"  ⚠ Using {last_year} data for {country} (base_year {base_year} not available)")
        
        base_values[country] = float(base_row["local_production"].iloc[0])
        print(f"  {country}: {base_values[country]:,.0f} tonnes in {base_year}")
    
    # Use generic helper to build production rows with CAGR
    return build_production_rows_with_cagr(
        industry_sector="ammonia",
        metric_name="ammonia production per year",
        base_values=base_values,
        cagr_dict=cagr_dict,
        countries=countries,
        base_year=base_year,
        target_years=target_years,
        scenarios=scenarios,
        units="tonnes",
    )


def build_ammonia_import_rows(
    countries: List[str],
    base_year: int,
    target_years: List[int],
    scenarios: List[str],
    cagr_dict: Dict[str, Dict[str, float]],
) -> pd.DataFrame:
    """
    Build ammonia import volume rows (for transparency in tracking total demand).
    
    Imports grow at same CAGR as local production.
    """
    # Load UNSD historical data
    hist_data = load_undata()
    
    # Get base year import values per country
    base_values = {}
    for country in countries:
        country_data = hist_data[hist_data["country"] == country]
        if len(country_data) == 0:
            base_values[country] = 0.0
            continue
        
        base_row = country_data[country_data["year"] == base_year]
        if len(base_row) == 0:
            available_years = country_data[country_data["year"] <= base_year]["year"]
            if len(available_years) == 0:
                base_values[country] = 0.0
                continue
            last_year = available_years.max()
            base_row = country_data[country_data["year"] == last_year]
        
        base_values[country] = float(base_row["import_volumes"].iloc[0])
    
    return build_production_rows_with_cagr(
        industry_sector="ammonia",
        metric_name="ammonia import volumes per year",
        base_values=base_values,
        cagr_dict=cagr_dict,
        countries=countries,
        base_year=base_year,
        target_years=target_years,
        scenarios=scenarios,
        units="tonnes",
    )


# ============================================================================
# CAGR ROWS
# ============================================================================

def build_ammonia_cagr_rows(
    countries: List[str],
    base_year: int,
    target_years: List[int],
    scenarios: List[str],
    cagr_dict: Dict[str, Dict[str, float]],
) -> pd.DataFrame:
    """Build CAGR metric rows for ammonia production."""
    return build_cagr_rows(
        industry_sector="ammonia",
        metric_name="CAGR ammonia production",
        cagr_dict=cagr_dict,
        countries=countries,
        base_year=base_year,
        target_years=target_years,
        scenarios=scenarios,
    )


# ============================================================================
# PATHWAY SHARE ROWS (GALT-based)
# ============================================================================

def build_ammonia_pathway_share_rows(
    countries: List[str],
    base_year: int,
    target_years: List[int],
    scenarios: List[str],
) -> pd.DataFrame:
    """
    Build technology pathway share rows for ammonia production.
    
    Two pathways:
    1. SMR + Haber-Bosch (conventional): 1 - GALT
    2. Renewable ammonia synthesis: GALT
    
    GALT values are read from build_ammonia_volumes.py anchor points.
    """
    all_rows = []
    
    # Convert pipeline scenarios to volume scenarios
    volume_scenarios = {sc: SCENARIO_MAPPING.get(sc, "mid_speed") for sc in scenarios}
    
    # For each target year, get GALT values from anchors
    for year in [base_year] + target_years:
        for scenario in scenarios:
            volume_scenario = volume_scenarios[scenario]
            
            # Interpolate GALT from anchors
            anchors = GALT_ANCHORS[volume_scenario]
            anchor_years = sorted(anchors.keys())
            anchor_vals = [anchors[y] for y in anchor_years]
            galt = float(np.interp(year, anchor_years, anchor_vals))
            
            # SMR + Haber-Bosch share = 1 - GALT
            smr_share = 1.0 - galt
            
            for country in countries:
                # SMR + Haber-Bosch pathway
                all_rows.append({
                    "industry_sector": "ammonia",
                    "type": "share",
                    "metric name": "Share of SMR + Haber-Bosch",
                    "year": year,
                    "scenario": scenario,
                    country: smr_share,
                    "units": "fraction",
                })
                
                # Renewable synthesis pathway
                all_rows.append({
                    "industry_sector": "ammonia",
                    "type": "share",
                    "metric name": "Share of renewable ammonia synthesis",
                    "year": year,
                    "scenario": scenario,
                    country: galt,
                    "units": "fraction",
                })
    
    return pd.DataFrame(all_rows)


# ============================================================================
# IMPORT REALLOCATION SHARE ROWS (GAIR-based)
# ============================================================================

def build_ammonia_reallocation_share_rows(
    countries: List[str],
    base_year: int,
    target_years: List[int],
    scenarios: List[str],
) -> pd.DataFrame:
    """
    Build import reallocation share rows (GAIR indicator).
    
    GAIR = share of imports reallocated to local green production.
    Values are read from build_ammonia_volumes.py anchor points.
    """
    all_rows = []
    
    # Convert pipeline scenarios to volume scenarios
    volume_scenarios = {sc: SCENARIO_MAPPING.get(sc, "mid_speed") for sc in scenarios}
    
    # For each target year, get GAIR values from anchors
    for year in [base_year] + target_years:
        for scenario in scenarios:
            volume_scenario = volume_scenarios[scenario]
            
            # Interpolate GAIR from anchors
            anchors = GAIR_ANCHORS[volume_scenario]
            anchor_years = sorted(anchors.keys())
            anchor_vals = [anchors[y] for y in anchor_years]
            gair = float(np.interp(year, anchor_years, anchor_vals))
            
            for country in countries:
                all_rows.append({
                    "industry_sector": "ammonia",
                    "type": "share",
                    "metric name": "Share of imports reallocation",
                    "year": year,
                    "scenario": scenario,
                    country: gair,
                    "units": "fraction",
                })
    
    return pd.DataFrame(all_rows)


# ============================================================================
# FUEL SHARE ROWS
# ============================================================================

def build_ammonia_fuel_share_rows(
    countries: List[str],
    base_year: int,
    target_years: List[int],
    scenarios: List[str],
) -> pd.DataFrame:
    """
    Build fuel share rows for ammonia pathways.
    
    Two pathways:
    1. SMR + Haber-Bosch: uses share_fuel_ammonia_smr_hb()
    2. Renewable synthesis: uses share_fuel_ammonia_renewable()
    """
    # Get fuel shares from existing functions
    smr_shares = share_fuel_ammonia_smr_hb(target_years, scenarios)
    renewable_shares = share_fuel_ammonia_renewable(target_years, scenarios)
    
    # Build rows using generic helper
    df_smr = build_fuel_share_rows(
        industry_sector="ammonia",
        fuel_shares_dict=smr_shares,
        metric_label="fuel_ammonia_smr_hb",
        countries=countries,
        base_year=base_year,
        target_years=target_years,
        scenarios=scenarios,
    )
    
    df_renewable = build_fuel_share_rows(
        industry_sector="ammonia",
        fuel_shares_dict=renewable_shares,
        metric_label="fuel_ammonia_renewable",
        countries=countries,
        base_year=base_year,
        target_years=target_years,
        scenarios=scenarios,
    )
    
    return pd.concat([df_smr, df_renewable], ignore_index=True)


# ============================================================================
# INTENSITY ROWS
# ============================================================================

def build_ammonia_intensity_rows(
    countries: List[str],
    base_year: int,
    target_years: List[int],
    scenarios: List[str],
) -> pd.DataFrame:
    """
    Build energy intensity rows for ammonia pathways.
    
    Unlike steel (which uses base + CAGR), ammonia intensities are pre-calculated
    for each year in the intensity functions. We store values for ALL years.
    
    Two pathways:
    1. SMR + Haber-Bosch: uses intensity_ammonia_smr_hb()
    2. Renewable synthesis: uses intensity_ammonia_renewable()
    """
    all_years = [base_year] + target_years
    rows = []
    
    # Get intensity data for both pathways
    intensity_smr = intensity_ammonia_smr_hb(target_years=target_years, scenarios=scenarios)
    intensity_renewable = intensity_ammonia_renewable(target_years=target_years, scenarios=scenarios)
    
    pathways = [
        ("intensity_ammonia_smr_hb", intensity_smr),
        ("intensity_ammonia_renewable", intensity_renewable),
    ]
    
    for metric_label, intensity_data in pathways:
        # Sum all fuels to get total intensity per year/scenario
        for year in all_years:
            for scenario in scenarios:
                # Sum intensities across all fuels for this year/scenario
                total_intensity = 0.0
                for fuel, year_data in intensity_data.items():
                    if year in year_data and scenario in year_data[year]:
                        total_intensity += year_data[year][scenario]
                
                # Create row for this year/scenario
                row = {
                    "industry_sector": "ammonia",
                    "type": "intensity_base",  # Keep this name for compatibility
                    "metric name": metric_label,
                    "year": year,
                    "scenario": scenario,
                    "units": "MWh/t",
                }
                
                # Same intensity for all countries (not country-specific)
                for country in countries:
                    row[country] = round(total_intensity, 2)
                
                rows.append(row)
    
    return pd.DataFrame(rows)


# ============================================================================
# AMMONIA VOLUMES (PATHWAY SPLITS)
# ============================================================================

def build_ammonia_volumes_csv(output_dir: Optional[Path] = None) -> pd.DataFrame:
    """
    Generate ammonia_volumes.csv with pathway splits (exog/endog) and GALT/GAIR indicators.
    
    This is equivalent to steel_volumes.csv for steel sector.
    Output includes:
    - path (scenario)
    - country
    - year
    - local_production
    - import_volumes
    - total_demand
    - GALT (Green Ammonia Local Transformation)
    - GAIR (Green Ammonia Import Reallocation)
    - CAGR_rate
    - CAGR_factor
    - exog_ammonia_conv_path (conventional/fossil pathway)
    - endog_ammonia_green_path (renewable/green pathway)
    
    Returns:
        DataFrame written to ammonia_volumes.csv
    """
    print("\n" + "="*70)
    print("Generating ammonia_volumes.csv (pathway splits with GALT/GAIR)")
    print("="*70)
    
    if output_dir is None:
        # Write to industry/output_data/ like steel_volumes.csv
        output_dir = Path(__file__).resolve().parents[3] / "output_data"
    
    # Use existing build_all_scenarios function
    df = build_all_scenarios(output_dir=output_dir)
    
    print(f"✓ Generated {len(df):,} rows")
    print(f"✓ Scenarios: {df['path'].unique().tolist()}")
    print(f"✓ Countries: {df['country'].nunique()}")
    print(f"✓ Year range: {df['year'].min()} - {df['year'].max()}")
    
    return df


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def generate_ammonia_config_rows(
    countries: List[str],
    base_year: int,
    target_years: List[int],
    scenarios: List[str],
) -> pd.DataFrame:
    """
    Generate all configuration rows for ammonia sector.
    
    This is the main entry point called by generate_industry_config.py.
    Follows the same pattern as generate_steel_config_rows().
    
    Args:
        countries: List of country names
        base_year: Base year for projections (e.g., 2020)
        target_years: Future years to project (e.g., [2030, 2035, 2040, 2045, 2050])
        scenarios: List of scenario names (e.g., ["BAU", "Progressive", "Optimistic"])
    
    Returns:
        Complete DataFrame with all ammonia configuration rows
    """
    print("\n" + "="*70)
    print("GENERATING AMMONIA CONFIGURATION ROWS")
    print("="*70)
    
    # Step 1: Calculate CAGR from UNSD data
    print("\n1. Calculating CAGR from UNSD historical data...")
    cagr_dict = calculate_ammonia_cagr_from_unsd(countries, scenarios)
    
    # Step 2: Build production rows
    print("\n2. Building production rows...")
    df_production = build_ammonia_production_rows(
        countries, base_year, target_years, scenarios, cagr_dict
    )
    print(f"  ✓ Generated {len(df_production)} production rows")
    
    # Step 3: Build import rows
    print("\n3. Building import volume rows...")
    df_imports = build_ammonia_import_rows(
        countries, base_year, target_years, scenarios, cagr_dict
    )
    print(f"  ✓ Generated {len(df_imports)} import rows")
    
    # Step 4: Build CAGR rows
    print("\n4. Building CAGR rows...")
    df_cagr = build_ammonia_cagr_rows(
        countries, base_year, target_years, scenarios, cagr_dict
    )
    print(f"  ✓ Generated {len(df_cagr)} CAGR rows")
    
    # Step 5: Build pathway share rows (GALT-based)
    print("\n5. Building pathway share rows (GALT)...")
    df_pathway_shares = build_ammonia_pathway_share_rows(
        countries, base_year, target_years, scenarios
    )
    print(f"  ✓ Generated {len(df_pathway_shares)} pathway share rows")
    
    # Step 6: Build import reallocation share rows (GAIR-based)
    print("\n6. Building import reallocation share rows (GAIR)...")
    df_reallocation_shares = build_ammonia_reallocation_share_rows(
        countries, base_year, target_years, scenarios
    )
    print(f"  ✓ Generated {len(df_reallocation_shares)} reallocation share rows")
    
    # Step 7: Build fuel share rows
    print("\n7. Building fuel share rows...")
    df_fuel_shares = build_ammonia_fuel_share_rows(
        countries, base_year, target_years, scenarios
    )
    print(f"  ✓ Generated {len(df_fuel_shares)} fuel share rows")
    
    # Step 8: Build intensity rows
    print("\n8. Building intensity rows...")
    df_intensities = build_ammonia_intensity_rows(
        countries, base_year, target_years, scenarios
    )
    print(f"  ✓ Generated {len(df_intensities)} intensity rows")
    
    # Step 9: Generate ammonia_volumes.csv
    print("\n9. Generating ammonia_volumes.csv...")
    build_ammonia_volumes_csv()
    
    # Concatenate all rows
    df_all = pd.concat(
        [
            df_production,
            df_imports,
            df_cagr,
            df_pathway_shares,
            df_reallocation_shares,
            df_fuel_shares,
            df_intensities,
        ],
        ignore_index=True,
    )
    
    print("\n" + "="*70)
    print(f"✓ AMMONIA CONFIG COMPLETE: {len(df_all)} total rows")
    print("="*70)
    
    return df_all


# ============================================================================
# CLI ENTRY POINT (for testing)
# ============================================================================

if __name__ == "__main__":
    # Test with a small set of countries
    test_countries = ["Morocco", "Egypt", "South Africa"]
    test_scenarios = ["BAU", "Progressive", "Optimistic"]
    test_base_year = 2020
    test_target_years = [2030, 2035, 2040, 2045, 2050]
    
    df = generate_ammonia_config_rows(
        countries=test_countries,
        base_year=test_base_year,
        target_years=test_target_years,
        scenarios=test_scenarios,
    )
    
    print("\nSample rows:")
    print(df.head(20))
    print("\nRow counts by type:")
    print(df.groupby("type")["metric name"].value_counts())
