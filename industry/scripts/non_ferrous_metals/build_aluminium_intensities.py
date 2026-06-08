"""
build_aluminium_intensities.py
-------------------------------
Generate energy intensity values for aluminium production routes.

Energy Intensities (MWh/tonne aluminium)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Primary Aluminium (Hall-Héroult electrolysis):**
- Baseline (2020): 15.0 MWh/t
  * Electrolysis: ~13.5 MWh/t (electricity)
  * Anode production: ~1.0 MWh/t (fossil fuels)
  * Alumina refining: ~0.5 MWh/t (heat)

- Efficiency improvements:
  * BAU: -0.5%/year → 13.5 MWh/t by 2050
  * Progressive: -1.0%/year → 11.9 MWh/t by 2050
  * Optimistic: -1.5%/year → 10.6 MWh/t by 2050 (inert anodes, renewable heat)

**Secondary Aluminium (Scrap recycling):**
- Baseline (2020): 0.75 MWh/t
  * Only 5% of primary energy (no electrolysis needed!)
  * Melting furnaces: ~0.6 MWh/t
  * Refining & casting: ~0.15 MWh/t

- Efficiency improvements:
  * BAU: -0.3%/year → 0.68 MWh/t by 2050
  * Progressive: -0.5%/year → 0.64 MWh/t by 2050
  * Optimistic: -0.8%/year → 0.59 MWh/t by 2050

Technology Drivers
~~~~~~~~~~~~~~~~~~
- **Inert anodes**: Replace carbon anodes → eliminate process CO₂ + reduce electricity
- **Renewable heat**: Replace fossil fuels in anode/alumina production
- **Process optimization**: Advanced control systems, waste heat recovery
- **Efficient furnaces**: Secondary smelting efficiency gains

Fuel Share Breakdown
~~~~~~~~~~~~~~~~~~~~
Fuel shares are extracted from UNSD historical data per country.
Default global averages (if UNSD missing):

**Primary Aluminium:**
- Electricity: 85% (electrolysis dominates)
- Natural gas: 10% (anode production, alumina refining heat)
- Oil products: 5% (transportation, backup fuel)

**Secondary Aluminium:**
- Electricity: 70% (melting furnaces)
- Natural gas: 25% (remelting, holding furnaces)
- Oil products: 5% (process heat, materials handling)

TODO: Validate intensity values against:
- IEA "Energy Technology Perspectives 2023" - Aluminium sector
- IAI "Global Aluminium Cycle 2022" - Energy benchmarks
- JRC-IDEES database - EU industrial energy intensities
- Energetics Inc. "Energy and Environmental Profile of the U.S. Aluminum Industry"

Placeholder Warning
~~~~~~~~~~~~~~~~~~~
⚠️  Current values are ESTIMATES based on typical industry ranges.
    MUST be validated with authoritative sources before production use!

Author: Automated workflow
Date: June 2026
"""

from __future__ import annotations

from typing import Dict, List, Optional
from industry.utils.helpers import interpolate_or_extrapolate
from industry.utils.helpers import get_scenarios_from_build_config_industry

SCENARIOS = get_scenarios_from_build_config_industry()

# ---------------------------------------------------------------------------
# Energy Intensity Functions
# ---------------------------------------------------------------------------

def calculate_intensity_from_cagr(
    base_intensity: float,
    base_year: int,
    target_year: int,
    efficiency_cagr: float
) -> float:
    """
    Calculate future intensity using efficiency CAGR.
    
    Efficiency CAGR is NEGATIVE (improvement reduces intensity).
    
    Args:
        base_intensity: Starting intensity (MWh/t)
        base_year: Base year
        target_year: Target year
        efficiency_cagr: Annual efficiency improvement rate (e.g., -0.01 = -1%/year)
    
    Returns:
        Future intensity (MWh/t)
    """
    years_elapsed = target_year - base_year
    future_intensity = base_intensity * ((1 + efficiency_cagr) ** years_elapsed)
    return future_intensity


def get_aluminium_energy_intensities(
    target_years: List[int],
    scenarios: Optional[List[str]] = None,
) -> Dict[str, Dict[int, Dict[str, float]]]:
    """
    Calculate energy intensities for aluminium production routes.
    
    Returns nested dictionary:
    {
        'Primary aluminium': {year: {scenario: intensity_MWh_per_t}},
        'Secondary aluminium': {year: {scenario: intensity_MWh_per_t}}
    }
    
    Args:
        target_years: Projection years
        scenarios: Scenario names
    
    Returns:
        Nested dict with intensities by route, year, and scenario
    """
    if scenarios is None:
        scenarios = SCENARIOS
    
    base_year = 2020
    
    # --- Primary Aluminium Intensity ---
    # TODO: Validate these values with IEA/IAI/JRC-IDEES sources
    PRIMARY_BASE = 15.0  # MWh/t (placeholder)
    PRIMARY_EFFICIENCY_CAGR = {
        'BAU': -0.005,        # -0.5%/year → 13.5 MWh/t by 2050
        'Progressive': -0.010,  # -1.0%/year → 11.9 MWh/t by 2050
        'Optimistic': -0.015,   # -1.5%/year → 10.6 MWh/t by 2050
    }
    
    # --- Secondary Aluminium Intensity ---
    # TODO: Validate these values with literature
    SECONDARY_BASE = 0.75  # MWh/t (placeholder)
    SECONDARY_EFFICIENCY_CAGR = {
        'BAU': -0.003,        # -0.3%/year → 0.68 MWh/t by 2050
        'Progressive': -0.005,  # -0.5%/year → 0.64 MWh/t by 2050
        'Optimistic': -0.008,   # -0.8%/year → 0.59 MWh/t by 2050
    }
    
    # --- Calculate intensities for all years/scenarios ---
    primary_intensities = {}
    secondary_intensities = {}
    
    for year in target_years:
        primary_intensities[year] = {}
        secondary_intensities[year] = {}
        
        for scenario in scenarios:
            # Primary intensity
            primary_intensities[year][scenario] = calculate_intensity_from_cagr(
                PRIMARY_BASE, base_year, year, 
                PRIMARY_EFFICIENCY_CAGR.get(scenario, PRIMARY_EFFICIENCY_CAGR['BAU'])
            )
            
            # Secondary intensity
            secondary_intensities[year][scenario] = calculate_intensity_from_cagr(
                SECONDARY_BASE, base_year, year,
                SECONDARY_EFFICIENCY_CAGR.get(scenario, SECONDARY_EFFICIENCY_CAGR['BAU'])
            )
    
    return {
        'Primary aluminium': primary_intensities,
        'Secondary aluminium': secondary_intensities,
    }


def get_aluminium_fuel_shares(
    target_years: List[int],
    scenarios: Optional[List[str]] = None,
) -> Dict[str, Dict[str, Dict[int, Dict[str, float]]]]:
    """
    Get fuel share breakdown for aluminium routes.
    
    Fuel shares are extracted from UNSD historical data per country.
    These are DEFAULT/FALLBACK values if UNSD data is missing.
    
    Returns nested dictionary:
    {
        'Primary aluminium': {
            'electricity': {year: {scenario: share}},
            'natural_gas': {year: {scenario: share}},
            ...
        },
        'Secondary aluminium': {...}
    }
    
    Args:
        target_years: Projection years
        scenarios: Scenario names
    
    Returns:
        Nested dict with fuel shares
    """
    if scenarios is None:
        scenarios = SCENARIOS
    
    # --- PRIMARY ALUMINIUM FUEL SHARES (electrolysis-heavy) ---
    # Electricity share increases over time (electrification of heat processes)
    primary_fuel_data = {
        'electricity': {
            2020: [0.85, 0.85, 0.85],
            2030: [0.87, 0.88, 0.90],
            2050: [0.88, 0.90, 0.92],
        },
        'natural_gas': {
            2020: [0.10, 0.10, 0.10],
            2030: [0.09, 0.08, 0.06],
            2050: [0.08, 0.06, 0.04],
        },
        'oil': {
            2020: [0.05, 0.05, 0.05],
            2030: [0.04, 0.04, 0.04],
            2050: [0.04, 0.04, 0.04],
        },
    }
    
    # --- SECONDARY ALUMINIUM FUEL SHARES (more thermal) ---
    secondary_fuel_data = {
        'electricity': {
            2020: [0.70, 0.70, 0.70],
            2030: [0.72, 0.75, 0.78],
            2050: [0.74, 0.78, 0.82],
        },
        'natural_gas': {
            2020: [0.25, 0.25, 0.25],
            2030: [0.23, 0.20, 0.17],
            2050: [0.21, 0.17, 0.13],
        },
        'oil': {
            2020: [0.05, 0.05, 0.05],
            2030: [0.05, 0.05, 0.05],
            2050: [0.05, 0.05, 0.05],
        },
    }
    
    # --- Interpolation helper ---
    def interpolate_fuel_shares(base_data, target_years, scenarios):
        result = {}
        
        for fuel, yearly in base_data.items():
            result[fuel] = {}
            
            for i, sc in enumerate(scenarios):
                # Build {year: value} for this scenario
                series = {
                    year: vals[i] if i < len(vals) else vals[-1]
                    for year, vals in yearly.items()
                }
                
                # Interpolate
                series_interp = interpolate_or_extrapolate(series, target_years)
                
                # Store as {year: {scenario: value}}
                for y, v in series_interp.items():
                    result[fuel].setdefault(y, {})[sc] = v
        
        return result
    
    # --- Compute fuel shares for both routes ---
    primary_shares = interpolate_fuel_shares(primary_fuel_data, target_years, scenarios)
    secondary_shares = interpolate_fuel_shares(secondary_fuel_data, target_years, scenarios)
    
    return {
        'Primary aluminium': primary_shares,
        'Secondary aluminium': secondary_shares,
    }


# ---------------------------------------------------------------------------
# Main Execution (for testing)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("="*80)
    print("ALUMINIUM ENERGY INTENSITIES")
    print("="*80)
    
    target_years = [2025, 2030, 2035, 2040, 2045, 2050]
    intensities = get_aluminium_energy_intensities(target_years)
    
    print("\nPRIMARY ALUMINIUM (Hall-Héroult)")
    print("-" * 80)
    print(f"{'Year':<6} {'BAU':>10} {'Progressive':>12} {'Optimistic':>12}")
    print("-" * 80)
    
    for year in target_years:
        values = intensities['Primary aluminium'][year]
        print(f"{year:<6} {values['BAU']:>10.2f} {values['Progressive']:>12.2f} {values['Optimistic']:>12.2f} MWh/t")
    
    print("\n\nSECONDARY ALUMINIUM (Recycling)")
    print("-" * 80)
    print(f"{'Year':<6} {'BAU':>10} {'Progressive':>12} {'Optimistic':>12}")
    print("-" * 80)
    
    for year in target_years:
        values = intensities['Secondary aluminium'][year]
        print(f"{year:<6} {values['BAU']:>10.2f} {values['Progressive']:>12.2f} {values['Optimistic']:>12.2f} MWh/t")
    
    # Show fuel shares
    print("\n\n" + "="*80)
    print("FUEL SHARES (2020 vs 2050)")
    print("="*80)
    
    fuel_shares = get_aluminium_fuel_shares(target_years)
    
    print("\nPrimary Aluminium - Optimistic Scenario:")
    print("-" * 80)
    for fuel in ['electricity', 'natural_gas', 'oil']:
        share_2020 = fuel_shares['Primary aluminium'][fuel][2020]['Optimistic']
        share_2050 = fuel_shares['Primary aluminium'][fuel][2050]['Optimistic']
        print(f"  {fuel:15s}: 2020 = {share_2020:5.1%}  →  2050 = {share_2050:5.1%}")
    
    print("\n⚠️  WARNING: Intensity values are PLACEHOLDERS!")
    print("   TODO: Validate with IEA/IAI/JRC-IDEES sources\n")
