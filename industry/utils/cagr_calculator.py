"""
Centralized CAGR (Compound Annual Growth Rate) calculation utilities.

This module provides activity/volume growth rate calculations based on historical
UNSD (United Nations Statistics Division) energy consumption data.

IMPORTANT DISTINCTION - Activity vs Efficiency:
==============================================
UNSD CAGR = ACTIVITY/VOLUME GROWTH (net of historical efficiency improvements)

Historical energy trends reflect:
  Total Energy Growth = Activity Growth - Historical Efficiency Gains

For modeling purposes:
1. UNSD CAGR → used as ACTIVITY/VOLUME growth baseline
2. Efficiency improvements → applied SEPARATELY by scenario-based assumptions

Example:
  If UNSD shows 2.5%/year energy growth historically:
  - We interpret this as 2.5%/year ACTIVITY growth
  - Then apply additional scenario-based efficiency gains:
    * BAU: -1.0%/year
    * Progressive: -2.0%/year  
    * Optimistic: -3.0%/year

METHODOLOGY:
===========
Activity CAGR is calculated from historical energy consumption trends because:
1. Energy consumption closely tracks production/activity volumes
2. UNSD provides consistent, validated data across 200+ countries
3. Captures real market dynamics (policy, economic, technological changes)

Process:
1. Load UNSD historical energy consumption (2011-2023)
2. Calculate rolling 5-year CAGR windows
3. Apply IQR (Interquartile Range) outlier capping to remove anomalies
4. Take mean of capped values as final CAGR
5. Apply scenario-specific multipliers for future projections

IQR Outlier Capping:
- Removes statistical outliers (e.g., COVID shock, data errors)
- Bounds: Q1 - 1.5×IQR to Q3 + 1.5×IQR
- Hard limits: -30% to +30% CAGR (physically realistic bounds)

Fallback:
- If no UNSD data available: 1.5% default (IEA/World Bank industrial average)

Scenario Multipliers (Applied to Activity Growth):
- BAU (Baseline): 1.0× - historical trend continues unchanged
- Progressive: 1.2× - 20% acceleration from policy/efficiency gains
- Optimistic: 1.5× - 50% acceleration from aggressive decarbonization

Note: For DETAILED industries (steel, cement, ammonia), efficiency improvements
come from engineering-based intensity projections (IEA Technology Roadmaps).
For SIMPLE industries, efficiency improvements are applied via separate efficiency
rate parameters by scenario.
"""

from typing import Dict, List, Optional
from pathlib import Path
import numpy as np
import pandas as pd


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_rolling_cagr_with_iqr_capping(historical_data: Dict[int, float], window: int = 5) -> float:
    """
    Calculate mean CAGR from rolling windows with IQR-based outlier capping.
    
    This method provides robust growth estimates by:
    1. Computing rolling window CAGRs
    2. Removing statistical outliers using IQR (Interquartile Range)
    3. Applying hard bounds (±30%) for physical realism
    4. Taking mean of capped values
    
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
    
    # Calculate rolling CAGR for each window
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
            single_cagr = (last_val / first_val) ** (1 / years_diff) - 1
            # Apply hard bounds even for single value
            return np.clip(single_cagr, -0.30, 0.30)
        return 0.0
    
    # Apply IQR-based outlier capping if we have enough data points
    if len(cagr_list) >= 4:
        cagr_array = np.array(cagr_list)
        
        # Remove inf/-inf values
        cagr_array = cagr_array[~np.isinf(cagr_array)]
        
        if len(cagr_array) >= 4:
            q1 = np.percentile(cagr_array, 25)
            q3 = np.percentile(cagr_array, 75)
            iqr = q3 - q1
            
            # IQR bounds
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            
            # Cap values to IQR bounds
            cagr_capped = np.clip(cagr_array, lower_bound, upper_bound)
        else:
            cagr_capped = cagr_array
    else:
        cagr_capped = np.array(cagr_list)
    
    # Apply hard bounds for physical realism (±30% per year)
    cagr_capped = np.clip(cagr_capped, -0.30, 0.30)
    
    # Return mean of capped values
    return float(np.mean(cagr_capped))


def calculate_rolling_cagr(historical_data: Dict[int, float], window: int = 5) -> float:
    """
    Legacy function - calls new IQR-capped version.
    Kept for backward compatibility.
    """
    return calculate_rolling_cagr_with_iqr_capping(historical_data, window)


def get_final_energy_cagr_from_unsd(country: str, sector_keyword: str, floor_at_zero: bool = True) -> float:
    """
    Get historical data from UNSD files and calculate CAGR for a sector.
    
    Args:
        country: Country name (e.g., "Morocco")
        sector_keyword: Sector keyword to search in UNSD files (e.g., "Food and tobacco")
        floor_at_zero: If True, negative CAGRs are floored at 0% (prevents decline projections)
    
    Returns:
        CAGR as decimal (e.g., 0.02 for 2%)
    
    Notes:
        - Historical CAGR floored at 0% for "other" sectors to prevent unrealistic declines
        - Rationale: Historical declines often reflect data reclassification, sectoral shifts,
          or measurement issues rather than true long-term trends
        - Conservative approach assumes policy/investment will stabilize declining industries
    """
    from industry.utils.helpers import get_historical_sector_data
    
    # CENTRALIZED UNSD DATA: Use shared data folder across all sectors
    # Path: sectoral-energy-demands/data/country_specific/
    # Contains UNSD files named: {Country}-{Year}.csv (e.g., Morocco-2022.csv)
    industry_folder = Path(__file__).parent.parent
    folder_path = industry_folder.parent / "data" / "country_specific"
    
    # IMPORTANT: This calculates ACTIVITY/VOLUME CAGR from historical energy data.
    # The historical energy growth represents net activity growth (after historical efficiency).
    # For projections, we treat this as pure activity growth and apply additional
    # scenario-based efficiency improvements separately.
    
    historical_data = get_historical_sector_data(folder_path, country, sector_keyword)
    
    if historical_data is None or len(historical_data) < 2:
        return 0.0
    
    cagr = calculate_rolling_cagr(historical_data, window=5)
    
    # CONSERVATIVE FLOOR: Prevent unrealistic decline projections
    # Negative historical trends often reflect data issues, not sustainable long-term decline
    if floor_at_zero and cagr < 0:
        return 0.0
    
    return cagr


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
                print(f"    [WARNING] No UNSD data for {country}, using fallback default: {fallback_cagr:.1%}")
                historical_cagr = fallback_cagr
            else:
                print(f"    [OK] Historical CAGR: {historical_cagr:.4%}")
        
        except Exception as e:
            print(f"    [WARNING] Error loading UNSD data for {country}: {e}")
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
