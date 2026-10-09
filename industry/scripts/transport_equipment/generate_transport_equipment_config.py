"""
Generate configuration rows for transport equipment sector.

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


def generate_transport_equipment_config_rows(
    countries: list[str],
    base_year: int,
    target_years: list[int],
    scenarios: list[str],
) -> "pd.DataFrame":
    """
    Generate config rows for transport equipment sector.
    
    Returns DataFrame with:
    1. historical_energy_demand rows
    2. cagr rows
    3. fuel_share rows
    """
    
    sector_name = "transport equipment"
    unsd_sector_name = "Transport equipment"
    
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
    
    test_countries = ['MA', 'EG', 'ZA', 'NA']
    test_base_year = 2020
    test_target_years = [2030, 2035, 2040, 2045, 2050]
    test_scenarios = ['BAU', 'Progressive', 'Optimistic']
    
    print("=" * 80)
    print("TRANSPORT EQUIPMENT SECTOR - Configuration Generator")
    print("=" * 80)
    
    df = generate_transport_equipment_config_rows(
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
    print("✓ Transport equipment config generation complete")
    print("=" * 80)
