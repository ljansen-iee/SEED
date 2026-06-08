"""
Generate configuration rows for 'other industries' sector.

This is a "simple" sector with only fuel shares (no production/intensity detail).
Maps to UNSD sector "Industry n.e.s" (not elsewhere specified) - a catch-all
category for industrial activities not classified in specific sectors.

Output format matches: "Share of [fuel] for other industries"
"""

from industry.utils.helpers import build_simple_sector_fuel_share_rows
from industry.scripts.other_industries.build_shares_other_industries import get_unsd_fuel_shares


def generate_other_industries_config_rows(
    countries: list[str],
    base_year: int,
    target_years: list[int],
    scenarios: list[str],
) -> "pd.DataFrame":
    """
    Generate config rows for 'other industries' sector (UNSD: Industry n.e.s).
    
    Simple sector pattern:
    - metric_1: "Industry n.e.s" (UNSD sector name - must match exactly)
    - metric_2: "fuel_share"
    - metric_3: "other industries" (display name)
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
        sector_display_name="other industries",  # User-friendly name for output
        unsd_sector_name="Industry n.e.s",      # UNSD sector name (must match CSV exactly)
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
    print("OTHER INDUSTRIES SECTOR - Configuration Generator")
    print("=" * 80)
    print("\nMapping: UNSD 'Industry n.e.s' → Model 'other industries'")
    print("Description: Catch-all for industries not classified elsewhere")
    
    df = generate_other_industries_config_rows(
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
    
    # Check data magnitude by country
    print("\n" + "-" * 80)
    print("Data Magnitude Check (2030 BAU scenario):")
    print("-" * 80)
    sample = df[(df['year'] == 2030) & (df['scenario'] == 'BAU')]
    
    if not sample.empty:
        print("\nCountries with data:")
        for country in test_countries:
            country_data = sample[country].sum()
            if country_data > 0:
                print(f"  {country}: {country_data:.4f} (sum of fuel shares)")
    
    print("\n" + "-" * 80)
    print("Fuel distribution for Egypt 2030 Optimistic:")
    print("-" * 80)
    sample_eg = df[(df['year'] == 2030) & (df['scenario'] == 'Optimistic')]
    if not sample_eg.empty and 'EG' in sample_eg.columns:
        print("\nFuel shares:")
        for _, row in sample_eg.iterrows():
            fuel = row['metric_4']
            value = row.get('EG', 0)
            if value > 0:
                print(f"  {fuel:12s}: {value*100:6.2f}%")
    
    print("\n" + "=" * 80)
    print("✓ Other industries config generation complete")
    print("=" * 80)
