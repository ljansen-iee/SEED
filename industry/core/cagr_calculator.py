"""
Centralized CAGR (Compound Annual Growth Rate) calculation utilities.

This module provides production growth rate calculations based on historical
UNSD (United Nations Statistics Division) energy consumption data.

METHODOLOGY:
===========
Production CAGR is calculated from historical energy consumption trends because:
1. Energy consumption closely tracks production volumes
2. UNSD provides consistent, validated data across 200+ countries
3. Captures real market dynamics (policy, economic, technological changes)

Process:
1. Load UNSD historical energy consumption (2011-2023)
2. Calculate rolling 5-year mean CAGR from trends
3. Apply scenario-specific multipliers for future projections

Fallback:
- If no UNSD data available: 1.5% default (IEA/World Bank industrial average)

Scenario Multipliers:
- BAU (Baseline): 1.0× - historical trend continues unchanged
- Progressive: 1.2× - 20% acceleration from policy/efficiency gains
- Optimistic: 1.5× - 50% acceleration from aggressive decarbonization

Note: This is for PRODUCTION growth only. Intensity improvements (efficiency gains)
are handled separately by sector-specific engineering models.
"""

from typing import Dict, List, Optional
from pathlib import Path


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_rolling_cagr(historical_data: Dict[int, float], window: int = 5) -> float:
    """
    Calculate mean CAGR from rolling 5-year windows.
    
    Args:
        historical_data: Dict of {year: value_in_GWh}
        window: Number of years for each CAGR calculation (default 5)
    
    Returns:
        Mean CAGR as a decimal (e.g., 0.02 for 2%)
    """
    if not historical_data or len(historical_data) < 2:
        return 0.0
    
    sorted_years = sorted(historical_data.keys())
    cagr_list = []
    
    # Calculate rolling CAGR for each 5-year window
    for i in range(len(sorted_years) - window):
        start_year = sorted_years[i]
        end_year = sorted_years[i + window]
        
        start_val = historical_data.get(start_year, 0)
        end_val = historical_data.get(end_year, 0)
        
        # Skip if either value is zero or negative
        if start_val > 0 and end_val > 0:
            cagr = (end_val / start_val) ** (1 / window) - 1
            cagr_list.append(cagr)
    
    if not cagr_list:
        # Fallback: calculate single CAGR from first to last available year
        first_year = sorted_years[0]
        last_year = sorted_years[-1]
        first_val = historical_data.get(first_year, 0)
        last_val = historical_data.get(last_year, 0)
        years_diff = last_year - first_year
        
        if first_val > 0 and last_val > 0 and years_diff > 0:
            return (last_val / first_val) ** (1 / years_diff) - 1
        return 0.0
    
    # Return mean of all rolling CAGRs
    return sum(cagr_list) / len(cagr_list)


def get_final_energy_cagr_from_unsd(country: str, sector_keyword: str) -> float:
    """
    Get historical data from UNSD files and calculate CAGR for a sector.
    
    Args:
        country: Country name (e.g., "Morocco")
        sector_keyword: Sector keyword to search in UNSD files (e.g., "Food and tobacco")
    
    Returns:
        CAGR as decimal (e.g., 0.02 for 2%)
    """
    from industry.core.helpers import get_historical_sector_data
    
    # Get the industry folder path (parent of core/)
    industry_folder = Path(__file__).parent.parent
    folder_path = industry_folder / "input_data" / "unsdata_historical"
    
    historical_data = get_historical_sector_data(folder_path, country, sector_keyword)
    
    if historical_data is None or len(historical_data) < 2:
        return 0.0
    
    return calculate_rolling_cagr(historical_data, window=5)


def calculate_production_cagr_from_unsd(
    countries: List[str],
    unsd_sector_name: str,
    scenarios: List[str],
    scenario_multipliers: Optional[Dict[str, float]] = None,
    fallback_cagr: float = 0.015,
) -> Dict[str, Dict[str, float]]:
    """
    Calculate data-driven CAGR for production from historical UNSD data.
    
    This generic function replaces sector-specific CAGR calculators with a unified
    approach. Originally duplicated in:
    - steel: calculate_steel_cagr_from_unsd()
    - ammonia: calculate_ammonia_cagr_from_unsd()
    
    Now centralized to ensure consistent methodology across all sectors.
    
    Args:
        countries: List of country names (e.g., ["Morocco", "Egypt"])
        unsd_sector_name: UNSD sector identifier for energy data lookup
                         Examples: "Iron and steel", "Chemical and petrochemical",
                                  "Non-metallic minerals"
        scenarios: List of scenario names (e.g., ["BAU", "Progressive", "Optimistic"])
        scenario_multipliers: Optional dict of {scenario: multiplier}
                            Default: {"BAU": 1.0, "Progressive": 1.2, "Optimistic": 1.5}
        fallback_cagr: Default CAGR if no UNSD data available (default: 0.015 = 1.5%)
    
    Returns:
        Dict of {country: {scenario: cagr_value}}
        
        Example output:
        {
            'Morocco': {'BAU': 0.032685, 'Progressive': 0.039222, 'Optimistic': 0.049028},
            'Egypt': {'BAU': 0.015, 'Progressive': 0.018, 'Optimistic': 0.0225}
        }
    
    Example Usage:
        >>> # Steel sector
        >>> steel_cagr = calculate_production_cagr_from_unsd(
        ...     countries=["Morocco", "Egypt"],
        ...     unsd_sector_name="Iron and steel",
        ...     scenarios=["BAU", "Progressive", "Optimistic"]
        ... )
        
        >>> # Ammonia sector
        >>> ammonia_cagr = calculate_production_cagr_from_unsd(
        ...     countries=["Morocco", "Egypt"],
        ...     unsd_sector_name="Chemical and petrochemical",
        ...     scenarios=["BAU", "Progressive", "Optimistic"]
        ... )
        
        >>> # Cement sector
        >>> cement_cagr = calculate_production_cagr_from_unsd(
        ...     countries=["Morocco", "Egypt"],
        ...     unsd_sector_name="Non-metallic minerals",
        ...     scenarios=["BAU", "Progressive", "Optimistic"]
        ... )
    
    Raises:
        None - Always returns valid output. Uses fallback_cagr if data unavailable.
    """
    if scenario_multipliers is None:
        scenario_multipliers = {
            "BAU": 1.0,          # Business as usual: historical trend continues
            "Progressive": 1.2,  # 20% growth acceleration
            "Optimistic": 1.5,   # 50% growth acceleration
        }
    
    production_cagr = {}
    
    for country in countries:
        print(f"  Calculating CAGR for {country} from UNSD historical data...")
        
        # Get historical CAGR from UNSD data for this sector
        try:
            historical_cagr = get_final_energy_cagr_from_unsd(country, unsd_sector_name)
            
            if historical_cagr is None or historical_cagr == 0.0:
                print(f"    ⚠ No UNSD data for {country}, using fallback default: {fallback_cagr:.1%}")
                historical_cagr = fallback_cagr
            else:
                print(f"    ✓ Historical CAGR: {historical_cagr:.4%}")
        
        except Exception as e:
            print(f"    ⚠ Error loading UNSD data for {country}: {e}")
            print(f"    Using fallback default: {fallback_cagr:.1%}")
            historical_cagr = fallback_cagr
        
        # Apply scenario multipliers
        production_cagr[country] = {}
        for scenario in scenarios:
            multiplier = scenario_multipliers.get(scenario, 1.0)
            cagr_value = historical_cagr * multiplier
            production_cagr[country][scenario] = round(cagr_value, 6)
            print(f"    {scenario}: {cagr_value:.4%} (historical: {historical_cagr:.4%} × {multiplier})")
    
    return production_cagr
