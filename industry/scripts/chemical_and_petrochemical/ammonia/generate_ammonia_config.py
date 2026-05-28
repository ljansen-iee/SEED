"""
Ammonia sector configuration row builders.

This module contains all ammonia-specific logic for generating configuration rows
for INDUSTRY_CONFIG.csv. This includes:
- CAGR calculation from UNSD historical data
- Local production projections
- Import volume tracking
- Technology pathway shares (SMR+Haber-Bosch vs renewable synthesis)
- Import reallocation shares
- Fuel shares per pathway
- Energy intensities per pathway
- Ammonia volumes (pathway splits with renewable/SMR+HB)

This modular structure follows the steel sector pattern, allowing easy maintenance
and testing of ammonia logic independently from other sectors.

Key indicators:
- GALT (Green Ammonia Local Transformation): share of local production using green synthesis
- GAIR (Green Ammonia Import Reallocation): share of imports reallocated to local green production

CAGR METHODOLOGY:
=================

1. PRODUCTION CAGR (same as steel):
   - Source: UNSD historical energy consumption data (2011-2023)
   - Calculation: Rolling 5-year mean CAGR from historical trends
   - Scenario adjustment: BAU (1.0×), Progressive (1.2×), Optimistic (1.5×)
   - Country-specific: Yes - each country has its own historical growth rate
   - Fallback: 1.5% if no UNSD data available

2. INTENSITY CAGR (different from steel):
   - Source: Year-specific values from intensity functions (build_intensities_ammonia.py)
   - Calculation: (end_intensity / start_intensity)^(1/years) - 1
   - Steel comparison: Steel uses fixed CAGR values; ammonia calculates from functions
   - Scenario variation: BAU/Progressive (~0%), Optimistic (~-0.1% annual)
   - Country-specific: No - technology improvements are global
   - Efficiency gains:
     * SMR pathway: Process optimization, heat recovery
     * Renewable pathway: Electrolyzer efficiency improvements

CONFIGURATION STRUCTURE:
========================
metric_1: 'chemical and petrochemical' (UNSD sector level - standardized)
metric_2: 'production', 'cagr', 'technology_route', 'fuel_share', 'intensity_base'
metric_3: Specific industry metric (e.g., 'ammonia production per year', 'SMR+HB', 'Renewable synthesis')
metric_4: Sub-metric (e.g., fuel type for fuel_share rows)

WHY DIFFERENT APPROACHES?
- Production: Historical data reflects policy, economic, market trends → use UNSD
- Intensity: Technology efficiency gains are predictable → use engineering projections
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
    from industry.core.cagr_calculator import calculate_production_cagr_from_unsd
    from industry.core.helpers import (
        extract_all_fuels,
        build_fuel_share_rows,
        build_intensity_base_rows,
        build_production_rows_with_cagr,
        build_cagr_rows,
    )
except ImportError:
    # When running from industry folder directly
    from core.cagr_calculator import calculate_production_cagr_from_unsd
    from core.helpers import (
        extract_all_fuels,
        build_fuel_share_rows,
        build_intensity_base_rows,
        build_production_rows_with_cagr,
        build_cagr_rows,
    )


# ============================================================================
# CAGR CALCULATION (Now uses centralized core.cagr_calculator)
# ============================================================================

def calculate_ammonia_cagr_from_unsd(
    countries: List[str],
    scenarios: List[str],
    scenario_multipliers: Optional[Dict[str, float]] = None,
) -> Dict[str, Dict[str, float]]:
    """
    Calculate data-driven CAGR for ammonia production from historical UNSD data.
    
    This is now a thin wrapper around the centralized calculate_production_cagr_from_unsd()
    function in industry.core.cagr_calculator. The centralized version ensures consistent
    methodology across all sectors (steel, ammonia, cement, etc.).
    
    METHODOLOGY (SAME AS STEEL):
    Both steel and ammonia use UNSD historical energy consumption data to calculate
    realistic growth rates. This ensures projections are grounded in actual trends.
    
    Process:
    1. Load historical energy consumption from UNSD database (2011-2023)
    2. Calculate rolling 5-year mean CAGR from historical data
    3. Apply scenario-specific multipliers to adjust for future expectations
    
    Scenario multipliers:
    - BAU (1.0): Business as usual - historical trend continues unchanged
    - Progressive (1.2): 20% growth acceleration - moderate policy push
    - Optimistic (1.5): 50% growth acceleration - strong decarbonization push
    
    Fallback: If no UNSD data available for a country, uses 1.5% default
    (average industrial growth rate from IEA/World Bank estimates)
    
    Args:
        countries: List of country names
        scenarios: List of scenario names (e.g., ["BAU", "Progressive", "Optimistic"])
        scenario_multipliers: Optional dict of {scenario: multiplier}
                            Default: {"BAU": 1.0, "Progressive": 1.2, "Optimistic": 1.5}
    
    Returns:
        Dict of {country: {scenario: cagr_value}}
    
    Example:
        >>> calculate_ammonia_cagr_from_unsd(["Morocco"], ["BAU", "Progressive", "Optimistic"])
        {'Morocco': {'BAU': 0.032685, 'Progressive': 0.039222, 'Optimistic': 0.049028}}
    """
    return calculate_production_cagr_from_unsd(
        countries=countries,
        unsd_sector_name="Chemical and petrochemical",
        scenarios=scenarios,
        scenario_multipliers=scenario_multipliers,
        fallback_cagr=0.015,  # 1.5% default for ammonia
    )


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
        industry_sector="chemical and petrochemical",
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
        industry_sector="chemical and petrochemical",
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
    """
    Build CAGR metric rows for ammonia production.
    
    Note: Metric name is just 'ammonia production' since the 'type' column
    already indicates this is a CAGR value.
    """
    return build_cagr_rows(
        industry_sector="ammonia",
        metric_name="ammonia production",
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
            
            # Create ONE row for SMR+HB with all countries
            row_smr = {
                "metric_1": "ammonia",  # Industry sector
                "metric_2": "technology_route",  # Type
                "metric_3": "SMR+HB",  # Technology route
                "metric_4": "",  # Not applicable
                "year": year,
                "scenario": scenario,
                "units": "share",
            }
            for country in countries:
                row_smr[country] = smr_share
            all_rows.append(row_smr)
            
            # Create ONE row for Renewable synthesis with all countries
            row_renewable = {
                "metric_1": "ammonia",  # Industry sector
                "metric_2": "technology_route",  # Type
                "metric_3": "Renewable synthesis",  # Technology route
                "metric_4": "",  # Not applicable
                "year": year,
                "scenario": scenario,
                "units": "share",
            }
            for country in countries:
                row_renewable[country] = galt
            all_rows.append(row_renewable)
    
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
            
            # Create ONE row for import reallocation with all countries
            row = {
                "metric_1": "ammonia",  # Industry sector
                "metric_2": "technology_route",  # Type
                "metric_3": "Import reallocation",  # Metric
                "metric_4": "",  # Not applicable
                "year": year,
                "scenario": scenario,
                "units": "share",
            }
            for country in countries:
                row[country] = gair
            all_rows.append(row)
    
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
        industry_sector="chemical and petrochemical",
        fuel_shares_dict=smr_shares,
        metric_label="SMR+HB",
        countries=countries,
        base_year=base_year,
        target_years=target_years,
        scenarios=scenarios,
    )
    
    df_renewable = build_fuel_share_rows(
        industry_sector="chemical and petrochemical",
        fuel_shares_dict=renewable_shares,
        metric_label="Renewable synthesis",
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
    Build energy intensity rows for ammonia pathways (BASE YEAR ONLY).
    
    Similar to steel, we only store base year intensities in INDUSTRY_CONFIG.csv.
    Full year-by-year projections are auto-generated in ammonia_intensity_projections.csv.
    
    Two pathways:
    1. SMR + Haber-Bosch: Conventional ammonia production using steam methane reforming
    2. Renewable synthesis: Green ammonia using renewable electricity + electrolysis
    
    ASSUMPTION: We aggregate all fuel intensities into a single total intensity value.
    This assumes the same energy intensity applies regardless of fuel type used.
    
    TODO (Future Enhancement): Add fuel-specific intensities to differentiate between:
    - Natural gas vs coal vs biomass for SMR pathway
    - Different electricity sources for renewable pathway
    - Allow model to optimize fuel mix based on cost and availability
    """
    rows = []
    
    # Get intensity data for both pathways
    intensity_smr = intensity_ammonia_smr_hb(target_years=target_years, scenarios=scenarios)
    intensity_renewable = intensity_ammonia_renewable(target_years=target_years, scenarios=scenarios)
    
    # Map to human-readable metric names (matches steel pattern)
    pathways = [
        ("SMR+HB", intensity_smr),
        ("Renewable synthesis", intensity_renewable),
    ]
    
    for metric_name, intensity_data in pathways:
        # Only store BASE YEAR in config (projections go to separate CSV)
        for scenario in scenarios:
            # Sum intensities across all fuels for base year
            total_intensity = 0.0
            for fuel, year_data in intensity_data.items():
                if base_year in year_data and scenario in year_data[base_year]:
                    total_intensity += year_data[base_year][scenario]
            
            # Create row for base year only
            row = {
                "metric_1": "ammonia",  # Industry sector
                "metric_2": "intensity_base",  # Type
                "metric_3": metric_name,  # Technology route
                "metric_4": "",  # Not applicable
                "year": base_year,
                "scenario": scenario,
                "units": "MWh/t",
            }
            
            # Same intensity for all countries (not country-specific)
            for country in countries:
                row[country] = round(total_intensity, 2)
            
            rows.append(row)
    
    return pd.DataFrame(rows)


def build_ammonia_intensity_cagr_rows(
    countries: List[str],
    base_year: int,
    target_years: List[int],
    scenarios: List[str],
) -> pd.DataFrame:
    """
    Build CAGR rows for ammonia energy intensities.
    
    METHODOLOGY (DIFFERENT FROM STEEL):
    Steel uses fixed CAGR values defined in the config builder (e.g., 0.0, -0.001).
    Ammonia calculates CAGR from the intensity functions which contain year-specific
    technology assumptions. This allows for more granular intensity projections.
    
    Process:
    1. Get intensity values from intensity functions for start/end year
    2. Calculate CAGR: (end_intensity / start_intensity)^(1/years) - 1
    3. Generate CAGR rows for each period (2020-2030, 2030-2035, etc.)
    
    Intensity improvements by scenario:
    - BAU: No improvement (0% CAGR) - assumes current technology persists
    - Progressive: No improvement (0% CAGR) - technology adoption, not efficiency
    - Optimistic: ~-0.1% annual - efficiency gains from:
      * SMR pathway: Process optimization, heat recovery improvements
      * Renewable pathway: Electrolyzer efficiency gains, better integration
    
    NOTE: These CAGRs are technology-driven (same for all countries).
    Country-specific variations would require different technology adoption rates.
    
    Returns:
        DataFrame with CAGR values for each period, pathway, and scenario
    """
    # Get intensity data
    intensity_smr = intensity_ammonia_smr_hb(target_years=target_years, scenarios=scenarios)
    intensity_renewable = intensity_ammonia_renewable(target_years=target_years, scenarios=scenarios)
    
    pathways = [
        ("Energy intensity of SMR+HB", intensity_smr),
        ("Energy intensity of Renewable synthesis", intensity_renewable),
    ]
    
    all_years = [base_year] + target_years
    periods = [f"{all_years[i]}-{all_years[i+1]}" for i in range(len(all_years) - 1)]
    
    rows = []
    
    for metric_name, intensity_data in pathways:
        for period in periods:
            # Parse period years
            start_year, end_year = map(int, period.split('-'))
            years_elapsed = end_year - start_year
            
            for scenario in scenarios:
                # Calculate total intensity for start and end years
                start_intensity = sum(
                    intensity_data[fuel][start_year][scenario]
                    for fuel in intensity_data
                    if start_year in intensity_data[fuel] and scenario in intensity_data[fuel][start_year]
                )
                
                end_intensity = sum(
                    intensity_data[fuel][end_year][scenario]
                    for fuel in intensity_data
                    if end_year in intensity_data[fuel] and scenario in intensity_data[fuel][end_year]
                )
                
                # Calculate CAGR: (end/start)^(1/years) - 1
                if start_intensity > 0:
                    cagr_value = (end_intensity / start_intensity) ** (1 / years_elapsed) - 1
                else:
                    cagr_value = 0.0
                
                row = {
                    'metric_1': 'chemical and petrochemical',  # Industry sector
                    'metric_2': 'cagr',  # Type
                    'metric_3': metric_name,  # Technology route
                    'metric_4': '',  # Not applicable
                    'year': period,
                    'scenario': scenario,
                    'units': 'share',
                }
                
                # Same CAGR for all countries (intensity improvements are technology-driven)
                for country in countries:
                    row[country] = round(cagr_value, 6)
                
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
        # Write to industry/output_data/interim_data/ to match steel_volumes.csv location
        output_dir = Path(__file__).resolve().parents[3] / "output_data" / "interim_data"
    
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
    
    # Step 9: Build intensity CAGR rows
    print("\n9. Building intensity CAGR rows...")
    df_intensity_cagr = build_ammonia_intensity_cagr_rows(
        countries, base_year, target_years, scenarios
    )
    print(f"  ✓ Generated {len(df_intensity_cagr)} intensity CAGR rows")
    
    # Step 10: Generate ammonia_volumes.csv
    print("\n10. Generating ammonia_volumes.csv...")
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
            df_intensity_cagr,
        ],
        ignore_index=True,
    )
    
    # Fill NaN values with 0 (matching iron and steel nomenclature)
    df_all = df_all.fillna(0)
    
    print("\n" + "="*70)
    print(f"✓ AMMONIA CONFIG COMPLETE: {len(df_all)} total rows")
    print("="*70)
    
    return df_all


# ============================================================================
# STANDALONE TESTING AND VERIFICATION
# ============================================================================

if __name__ == "__main__":
    """
    Test script independently with sample countries and show key metrics.
    Requires PYTHONPATH to be set to industry folder.
    
    Usage:
        cd industry/
        $env:PYTHONPATH="$(pwd)"; python scripts/chemical_and_petrochemical/ammonia/generate_ammonia_config.py
    """
    print("\n" + "="*100)
    print("TESTING AMMONIA CONFIG GENERATOR")
    print("="*100)
    
    # Test parameters
    test_countries = ["Morocco", "Egypt", "South Africa", "Namibia"]
    test_scenarios = ["BAU", "Progressive", "Optimistic"]
    test_base_year = 2020
    test_target_years = [2030, 2035, 2040, 2045, 2050]
    
    # Generate config
    df = generate_ammonia_config_rows(
        countries=test_countries,
        base_year=test_base_year,
        target_years=test_target_years,
        scenarios=test_scenarios,
    )
    
    print(f"\n{'='*100}")
    print("CONFIGURATION SUMMARY")
    print(f"{'='*100}")
    print(f"\nTotal rows generated: {len(df)}")
    print(f"\nRow distribution by metric type:")
    metric_counts = df.groupby('metric_2')['metric_3'].value_counts()
    for (metric_2, metric_3), count in metric_counts.items():
        print(f"  {metric_2:20s} | {metric_3:40s} | {count:3d} rows")
    
    # Show CAGR values
    print(f"\n{'='*100}")
    print("INTENSITY CAGR VALUES")
    print(f"{'='*100}")
    
    ammonia_cagr = df[
        (df['metric_2'] == 'cagr') & 
        (df['metric_3'].str.contains('Energy intensity'))
    ]
    
    if not ammonia_cagr.empty:
        print("\nIntensity CAGR Values and 2050 Reductions:")
        for metric in ammonia_cagr['metric_3'].unique():
            scenarios_df = ammonia_cagr[ammonia_cagr['metric_3']==metric][['scenario','Morocco']].drop_duplicates()
            print(f"\n{metric}:")
            for _, row in scenarios_df.iterrows():
                cagr_pct = row['Morocco'] * 100
                reduction_2050 = (1 - (1 + row['Morocco'])**30) * 100
                print(f"  {row['scenario']:12s}: {cagr_pct:+6.2f}%/year → {reduction_2050:5.1f}% reduction by 2050")
    
    # Show technology route transitions
    print(f"\n{'='*100}")
    print("TECHNOLOGY ROUTE TRANSITIONS (Morocco, Optimistic)")
    print(f"{'='*100}")
    
    route_shares = df[
        (df['metric_2'] == 'technology_route') &
        (df['metric_3'].isin(['SMR+HB', 'Renewable synthesis', 'Import reallocation'])) &
        (df['scenario'] == 'Optimistic') &
        (df['year'].isin([2020, 2030, 2050]))
    ][['metric_3', 'year', 'Morocco']].pivot(index='metric_3', columns='year', values='Morocco')
    
    if not route_shares.empty:
        print("\n" + route_shares.to_string())
        print("\nTransition: Fossil SMR → Renewable synthesis + strategic imports")
    
    print("\n" + "="*100)
    print("\nAMMONIA CONFIG TEST COMPLETE")
    print("="*100)
