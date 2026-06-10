"""
Generate configuration rows for food and tobacco sector.

SIMPLIFIED METHODOLOGY (Phase 1):
==================================
1. Historical Energy: Extract 2020 base year from UNSD (TJ → MWh)
2. CAGR: Calculate from UNSD historical trends with scenario multipliers
3. Fuel Shares: Extract 2020 UNSD shares, keep CONSTANT for all years

TODO - Phase 2 Enhancements:
- Add fuel share transformation logic (electrification, hydrogen adoption)
- Implement scenario-specific transitions (BAU vs Progressive vs Optimistic)
- Consider technology diffusion models (S-curves, Bass model)
- Align with IEA/IRENA decarbonization pathways

Current approach is conservative baseline - uses actual historical data
without assumptions about future transitions.
"""

from typing import List
import pandas as pd
from industry.utils.helpers import (
    build_historical_energy_rows,
    build_simple_sector_cagr_rows,
    build_simple_sector_fuel_share_rows_from_unsd,
)


def generate_food_tobacco_config_rows(
    countries: List[str],
    base_year: int,
    target_years: List[int],
    scenarios: List[str],
) -> pd.DataFrame:
    """
    Generate config rows for food and tobacco sector.
    
    This is a "simple" sector with basic projection methodology:
    - No production modeling (unlike steel, ammonia, HVC)
    - No technology routes (unlike aluminium, cement)
    - Energy projected from historical base + CAGR + fuel shares
    
    Args:
        countries: List of country codes (e.g., ['MA', 'EG', 'ZA', 'NA'])
        base_year: Base year for historical data (e.g., 2020)
        target_years: Future years to project (e.g., [2030, 2035, 2040, 2045, 2050])
        scenarios: List of scenario names (e.g., ['BAU', 'Progressive', 'Optimistic'])
    
    Returns:
        DataFrame with three types of rows:
        1. historical_energy_demand (1 row with all countries)
        2. cagr (3 rows, one per scenario)
        3. fuel_share (N fuels × 3 scenarios × 5 years × M countries)
    
    Example row counts (4 countries, 3 scenarios, 5 years):
        - Historical energy: 1 row
        - CAGR: 3 rows (one per scenario)
        - Fuel shares: ~5 fuels × 3 scenarios × 5 years = 75 rows
        - Total: ~79 rows
    """
    
    sector_name = "food and tobacco"
    unsd_sector_name = "Food and tobacco"  # Must match UNSD exactly
    
    all_dfs = []
    
    # 1. Historical energy demand (base year 2020)
    df_historical = build_historical_energy_rows(
        sector_name=sector_name,
        unsd_sector_name=unsd_sector_name,
        countries=countries,
        base_year=base_year,
    )
    all_dfs.append(df_historical)
    
    # 2. Activity CAGR (with scenario multipliers)
    df_cagr = build_simple_sector_cagr_rows(
        sector_name=sector_name,
        unsd_sector_name=unsd_sector_name,
        countries=countries,
        scenarios=scenarios,
    )
    all_dfs.append(df_cagr)
    
    # 3. Fuel shares (from UNSD 2020, constant for all years)
    df_fuel_shares = build_simple_sector_fuel_share_rows_from_unsd(
        sector_name=sector_name,
        unsd_sector_name=unsd_sector_name,
        countries=countries,
        base_year=base_year,
        target_years=target_years,
        scenarios=scenarios,
    )
    all_dfs.append(df_fuel_shares)
    
    # Concatenate all components
    return pd.concat(all_dfs, ignore_index=True)


if __name__ == "__main__":
    """Test standalone execution."""
    import pandas as pd
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    
    # Test parameters
    test_countries = ['MA', 'EG', 'ZA', 'NA']
    test_base_year = 2020
    test_target_years = [2030, 2035, 2040, 2045, 2050]
    test_scenarios = ['BAU', 'Progressive', 'Optimistic']
    
    print("=" * 80)
    print("FOOD AND TOBACCO SECTOR - Configuration Generator")
    print("=" * 80)
    
    df = generate_food_tobacco_config_rows(
        countries=test_countries,
        base_year=test_base_year,
        target_years=test_target_years,
        scenarios=test_scenarios,
    )
    
    print(f"\nTotal rows generated: {len(df)}")
    print(f"Expected: {8 * len(test_scenarios) * len(test_target_years) * len(test_countries)}")
    
    print("\n" + "-" * 80)
    print("Sample rows (first 10):")
    print("-" * 80)
    print(df.head(10).to_string(index=False))
    
    print("\n" + "-" * 80)
    print("Fuel distribution for Morocco 2030 Optimistic:")
    print("-" * 80)
    sample = df[(df['year'] == 2030) & (df['scenario'] == 'Optimistic')]
    if not sample.empty:
        print("\nFuel shares:")
        for _, row in sample.iterrows():
            fuel = row['metric_4']
            value = row['MA']
            if value > 0:
                print(f"  {fuel:12s}: {value*100:6.2f}%")
    
    print("\n" + "=" * 80)
    print("✓ Food and tobacco config generation complete")
    print("=" * 80)
