"""
Generate configuration rows for mining and quarrying sector.

This is a "simple" sector with only fuel shares (no production/intensity detail).
Output format matches: "Share of [fuel] for unspecified mining and quarrying"
"""

from industry.core.helpers import build_simple_sector_fuel_share_rows
from industry.scripts.mining_and_quarrying.build_mining_and_quarrying_shares import get_mining_fuel_shares


def generate_mining_quarrying_config_rows(
    countries: list[str],
    base_year: int,
    target_years: list[int],
    scenarios: list[str],
) -> "pd.DataFrame":
    """
    Generate config rows for mining and quarrying sector.
    
    Simple sector pattern:
    - metric_1: "Mining and quarrying" (UNSD sector name)
    - metric_2: "fuel_share"
    - metric_3: "unspecified mining and quarrying"
    - metric_4: fuel name
    """
    
    return build_simple_sector_fuel_share_rows(
        sector_display_name="mining and quarrying",
        unsd_sector_name="Mining and quarrying",
        get_fuel_shares_func=get_mining_fuel_shares,
        countries=countries,
        base_year=base_year,
        target_years=target_years,
        scenarios=scenarios,
    )


if __name__ == "__main__":
    """Test standalone execution."""
    import pandas as pd
    pd.set_option('display.max_columns', None)
    
    test_countries = ['MA', 'EG', 'ZA', 'NA']
    test_base_year = 2020
    test_target_years = [2030, 2035, 2040, 2045, 2050]
    test_scenarios = ['BAU', 'Progressive', 'Optimistic']
    
    print("=" * 80)
    print("MINING AND QUARRYING SECTOR - Configuration Generator")
    print("=" * 80)
    
    df = generate_mining_quarrying_config_rows(
        countries=test_countries,
        base_year=test_base_year,
        target_years=test_target_years,
        scenarios=test_scenarios,
    )
    
    print(f"\nTotal rows: {len(df)}")
    print(f"\nSample (Morocco 2030 Optimistic fuel shares):")
    sample = df[(df['year'] == 2030) & (df['scenario'] == 'Optimistic')]
    for _, row in sample.iterrows():
        fuel = row['metric_4']
        value = row['MA']
        if value > 0:
            print(f"  {fuel:12s}: {value*100:6.2f}%")
    
    print("\n" + "=" * 80)
    print("✓ Mining and quarrying config generation complete")
    print("=" * 80)
