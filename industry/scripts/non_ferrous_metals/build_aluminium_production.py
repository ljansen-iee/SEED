"""
build_aluminium_production.py
------------------------------
Processes BGS aluminium production data into scenario-based volume projections.

Input
~~~~~
``industry/input_data/non-ferrous_metals/AL_production.csv``
    Columns: country | production[ktons/a] | Year | source
    Historical data from British Geological Survey (2015-2022)

Output
~~~~~~
``industry/output_data/interim_data/aluminium_production.csv``

Columns:
    country | year | scenario | production_ktonnes | 
    CAGR_rate | CAGR_factor | base_year | base_production

Methodology
~~~~~~~~~~~
Volume projections use exogenous CAGR rates calibrated to IEA/IAI scenarios:
- BAU: ~1.2%/year average (current trends continue)
- Progressive: ~1.6%/year (electrification push, circular economy)
- Optimistic: ~2.0%/year (green economy transition, renewable infrastructure)

Formula:
    Production(year) = Base_Production × (1 + CAGR_rate)^(year - base_year)

Historical Context (Global Aluminium):
- 2020: ~65 Mt/year
- 2050 BAU: ~85 Mt/year (+31%)
- 2050 Progressive: ~100 Mt/year (+54%)
- 2050 Optimistic: ~115 Mt/year (+77%)

Key Drivers:
- Electric vehicles (3x more aluminium than ICE)
- Renewable energy infrastructure (solar, wind)
- Lightweight packaging substitution
- Construction (green building materials)

TODO: Validate CAGR rates against:
- IEA "Energy Technology Perspectives 2023" - Aluminium chapter
- IAI (International Aluminium Institute) - Global aluminium outlook
- World Aluminium - Sustainability scenarios

Author: Automated workflow
Date: June 2026
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Base year for projections
BASE_YEAR = 2020

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).resolve().parent
_INDUSTRY_ROOT = _SCRIPT_DIR.parents[2]

# Path to BGS aluminium data
AL_PRODUCTION_CSV = (
    _INDUSTRY_ROOT / "input_data" / "non-ferrous_metals" / "AL_production.csv"
)

# Output directory
OUTPUT_DIR = _INDUSTRY_ROOT / "output_data" / "interim_data"

# Projected years (5-year steps)
PROJECTION_YEARS: List[int] = [2025, 2030, 2035, 2040, 2045, 2050]

# Per-scenario, per-interval CAGR rates (annual fraction).
# Each inner dict maps a projection year to the rate applied FROM the previous
# projection year (or base year) UP TO that year.
#
# Calibration reference: 
# - BAU: ~1.2%/year → ~40% growth by 2050 (IEA STEPS)
# - Progressive: ~1.6%/year → ~55% growth by 2050 (IEA APS)
# - Optimistic: ~2.0%/year → ~80% growth by 2050 (IEA NZE)
CAGR_RATES: Dict[str, Dict[int, float]] = {
    #              year: annual rate for the interval ending at that year
    "BAU":        {2025: 0.015, 2030: 0.013, 2035: 0.012, 2040: 0.011, 2045: 0.010, 2050: 0.010},
    "Progressive": {2025: 0.020, 2030: 0.018, 2035: 0.016, 2040: 0.014, 2045: 0.012, 2050: 0.012},
    "Optimistic":  {2025: 0.025, 2030: 0.023, 2035: 0.020, 2040: 0.018, 2045: 0.015, 2050: 0.015},
}

# Scenario names
SCENARIOS = ["BAU", "Progressive", "Optimistic"]

# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def load_aluminium_data(csv_path: Path) -> pd.DataFrame:
    """
    Load BGS aluminium production data.
    
    Args:
        csv_path: Path to AL_production.csv
    
    Returns:
        DataFrame with columns: country, Year, production_ktonnes
    """
    df = pd.read_csv(csv_path)
    
    # Rename for clarity
    df = df.rename(columns={'production[ktons/a]': 'production_ktonnes'})
    
    # Ensure Year is integer
    df['Year'] = df['Year'].astype(int)
    
    # Ensure production is numeric
    df['production_ktonnes'] = pd.to_numeric(df['production_ktonnes'], errors='coerce')
    
    return df[['country', 'Year', 'production_ktonnes']].copy()


def get_base_production(df: pd.DataFrame, country: str, base_year: int) -> tuple[float, int]:
    """
    Get base year production for a country.
    
    If base_year not available, use closest available year.
    
    Args:
        df: Full production DataFrame
        country: Country code (e.g., 'CN', 'US', 'IN')
        base_year: Target base year (typically 2020)
    
    Returns:
        Tuple of (production_ktonnes, actual_year_used)
    """
    country_data = df[df['country'] == country].copy()
    
    if country_data.empty:
        return 0.0, base_year
    
    # Check if base year exists
    base_row = country_data[country_data['Year'] == base_year]
    
    if not base_row.empty:
        production = base_row['production_ktonnes'].iloc[0]
        return production if pd.notna(production) else 0.0, base_year
    
    # Find closest available year
    country_data['year_diff'] = abs(country_data['Year'] - base_year)
    closest = country_data.nsmallest(1, 'year_diff')
    
    if not closest.empty:
        production = closest['production_ktonnes'].iloc[0]
        actual_year = int(closest['Year'].iloc[0])
        return production if pd.notna(production) else 0.0, actual_year
    
    return 0.0, base_year


def calculate_cagr_factor(base_year: int, target_year: int, scenario: str) -> tuple[float, float]:
    """
    Calculate cumulative CAGR factor for a target year.
    
    CAGR is applied in intervals (not constant rate).
    Example: 2020 → 2025 → 2030 → ... → 2050
    
    Args:
        base_year: Starting year
        target_year: Target projection year
        scenario: Scenario name (BAU, Progressive, Optimistic)
    
    Returns:
        Tuple of (cumulative_factor, effective_annual_rate)
    """
    if target_year <= base_year:
        return 1.0, 0.0
    
    rates = CAGR_RATES[scenario]
    
    # Sort projection milestones
    milestones = sorted([y for y in rates.keys() if base_year < y <= target_year])
    
    if not milestones:
        # No milestones → use rate for first future year
        first_future = min([y for y in rates.keys() if y > base_year], default=target_year)
        rate = rates.get(first_future, 0.0)
        years_elapsed = target_year - base_year
        return (1 + rate) ** years_elapsed, rate
    
    # Compound growth through intervals
    cumulative_factor = 1.0
    prev_year = base_year
    
    for milestone in milestones:
        rate = rates[milestone]
        years_in_interval = milestone - prev_year
        cumulative_factor *= (1 + rate) ** years_in_interval
        prev_year = milestone
    
    # If target_year is beyond last milestone, extend with last rate
    if target_year > milestones[-1]:
        rate = rates[milestones[-1]]
        years_beyond = target_year - milestones[-1]
        cumulative_factor *= (1 + rate) ** years_beyond
    
    # Calculate effective annual rate (geometric mean)
    years_total = target_year - base_year
    effective_rate = cumulative_factor ** (1 / years_total) - 1
    
    return cumulative_factor, effective_rate


def generate_aluminium_projections() -> pd.DataFrame:
    """
    Generate aluminium production projections for all countries and scenarios.
    
    Returns:
        DataFrame with projected volumes
    """
    # Load historical data
    print(f"Loading aluminium production data from: {AL_PRODUCTION_CSV}")
    df = load_aluminium_data(AL_PRODUCTION_CSV)
    
    # Get unique countries
    countries = sorted(df['country'].unique())
    print(f"Found {len(countries)} countries with aluminium production data")
    
    results = []
    
    for country in countries:
        # Get base year production
        base_production, actual_base_year = get_base_production(df, country, BASE_YEAR)
        
        if base_production == 0:
            print(f"  {country}: No production data, skipping")
            continue
        
        print(f"  {country}: Base production = {base_production:.1f} kt/year ({actual_base_year})")
        
        # Generate projections for each scenario
        for scenario in SCENARIOS:
            for year in PROJECTION_YEARS:
                # Calculate CAGR factor
                cagr_factor, effective_rate = calculate_cagr_factor(actual_base_year, year, scenario)
                
                # Project production
                projected_production = base_production * cagr_factor
                
                results.append({
                    'country': country,
                    'year': year,
                    'scenario': scenario,
                    'production_ktonnes': projected_production,
                    'CAGR_rate': effective_rate,
                    'CAGR_factor': cagr_factor,
                    'base_year': actual_base_year,
                    'base_production': base_production,
                })
    
    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# Main Execution
# ---------------------------------------------------------------------------

def main():
    """Generate aluminium production projections."""
    print("="*80)
    print("ALUMINIUM PRODUCTION VOLUME PROJECTIONS")
    print("="*80)
    
    # Generate projections
    df_projections = generate_aluminium_projections()
    
    # Save to CSV
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "aluminium_production.csv"
    
    df_projections.to_csv(output_path, index=False, float_format='%.3f')
    
    print(f"\n✓ Saved projections to: {output_path}")
    print(f"  Total rows: {len(df_projections)}")
    print(f"  Countries: {df_projections['country'].nunique()}")
    print(f"  Years: {sorted(df_projections['year'].unique())}")
    print(f"  Scenarios: {sorted(df_projections['scenario'].unique())}")
    
    # Summary statistics
    print("\n" + "="*80)
    print("SUMMARY BY SCENARIO (2050)")
    print("="*80)
    
    df_2050 = df_projections[df_projections['year'] == 2050]
    for scenario in SCENARIOS:
        scenario_data = df_2050[df_2050['scenario'] == scenario]
        total = scenario_data['production_ktonnes'].sum()
        print(f"  {scenario:12s}: {total:10,.0f} kt/year")
    
    print("\n✓ Aluminium production projections complete!\n")


if __name__ == "__main__":
    main()
