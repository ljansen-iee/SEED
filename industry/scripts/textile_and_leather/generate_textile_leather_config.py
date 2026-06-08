"""
Generate configuration rows for textile and leather sector.

This is a "simple" sector with only fuel shares (no production/intensity detail).
Output format matches: "Share of [fuel] for unspecified textile and leather"
"""

from industry.utils.helpers import build_simple_sector_fuel_share_rows
from industry.scripts.textile_and_leather.build_textile_and_leather_shares import get_textiles_fuel_shares


def generate_textile_leather_config_rows(
    countries: list[str],
    base_year: int,
    target_years: list[int],
    scenarios: list[str],
) -> "pd.DataFrame":
    """
    Generate config rows for textile and leather sector.
    
    Simple sector pattern:
    - metric_1: "Textile and leather" (UNSD sector name)
    - metric_2: "fuel_share"
    - metric_3: "unspecified textile and leather"
    - metric_4: fuel name
    """
    
    return build_simple_sector_fuel_share_rows(
        sector_display_name="textile and leather",
        unsd_sector_name="Textile and leather",
        get_fuel_shares_func=get_textiles_fuel_shares,
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
    print("TEXTILE AND LEATHER SECTOR - Configuration Generator")
    print("=" * 80)
    
    df = generate_textile_leather_config_rows(
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
    print("✓ Textile and leather config generation complete")
    print("=" * 80)
