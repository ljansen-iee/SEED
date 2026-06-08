"""
Generate configuration rows for food and tobacco sector.

This is a "simple" sector with only fuel shares (no production/intensity detail).
Output format matches: "Share of [fuel] for unspecified food and tobacco"
"""

from industry.utils.helpers import build_simple_sector_fuel_share_rows
from industry.scripts.food_and_tobacco.build_shares_food_and_tobacco import get_unsd_fuel_shares


def generate_food_tobacco_config_rows(
    countries: list[str],
    base_year: int,
    target_years: list[int],
    scenarios: list[str],
) -> "pd.DataFrame":
    """
    Generate config rows for food and tobacco sector.
    
    Simple sector pattern:
    - metric_1: "Food and tobacco" (UNSD sector name)
    - metric_2: "fuel_share"
    - metric_3: "unspecified food and tobacco"
    - metric_4: fuel name (oil, gas, electricity, coal, biomass, hydrogen, ammonia, methanol)
    
    Args:
        countries: List of country codes (e.g., ['MA', 'EG', 'ZA', 'NA'])
        base_year: Base year for historical data (e.g., 2020)
        target_years: Future years to project (e.g., [2030, 2035, 2040, 2045, 2050])
        scenarios: List of scenario names (e.g., ['BAU', 'Progressive', 'Optimistic'])
    
    Returns:
        DataFrame with fuel share rows (8 fuels × 3 scenarios × 5 years × N countries)
    """
    
    return build_simple_sector_fuel_share_rows(
        sector_display_name="food and tobacco",
        unsd_sector_name="Food and tobacco",  # Must match UNSD exactly
        get_fuel_shares_func=get_unsd_fuel_shares,
        countries=countries,
        base_year=base_year,
        target_years=target_years,
        scenarios=scenarios,
    )


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
