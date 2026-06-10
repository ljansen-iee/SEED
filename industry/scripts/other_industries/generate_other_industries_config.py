"""
Generate configuration rows for 'other industries' sector.

Maps to UNSD sector "Industry n.e.s" (not elsewhere specified) - catch-all
for industrial activities not classified in specific sectors.

SIMPLIFIED METHODOLOGY (Phase 1):
1. Historical Energy: Extract 2020 base year from UNSD
2. CAGR: Calculate from UNSD trends with scenario multipliers
3. Fuel Shares: Extract 2020 UNSD shares, keep CONSTANT

TODO: Add fuel share transformation logic for Phase 2
"""

from typing import List
import pandas as pd
from industry.utils.helpers import (
    build_historical_energy_rows,
    build_simple_sector_cagr_rows,
    build_simple_sector_fuel_share_rows_from_unsd,
)


def generate_other_industries_config_rows(
    countries: list[str],
    base_year: int,
    target_years: list[int],
    scenarios: list[str],
) -> "pd.DataFrame":
    """
    Generate config rows for 'other industries' (UNSD: Industry n.e.s).
    
    Returns DataFrame with:
    1. historical_energy_demand rows
    2. cagr rows
    3. fuel_share rows
    """
    
    sector_name = "other"
    unsd_sector_name = "Industry n.e.s"
    
    all_dfs = []
    
    all_dfs.append(build_historical_energy_rows(
        sector_name, unsd_sector_name, countries, base_year
    ))
    
    all_dfs.append(build_simple_sector_cagr_rows(
        sector_name, unsd_sector_name, countries, scenarios
    ))
    
    all_dfs.append(build_simple_sector_fuel_share_rows_from_unsd(
        sector_name, unsd_sector_name, countries, base_year, target_years, scenarios
    ))
    
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
