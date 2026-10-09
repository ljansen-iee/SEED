"""Generate aluminium route intensities and fuel shares.

This module follows the same pattern used by other detailed sectors:
route-specific intensity functions return fuel-indexed values
(fuel -> year -> scenario -> MWh/t).

Current modelling assumption agreed for this workflow:
- Primary aluminium: 11.24 MWh/t for all fuels, years, scenarios
- Secondary aluminium: 11.24 MWh/t for all fuels, years, scenarios

Future intensity evolution is handled through exogenous CAGR assumptions in
the industry configuration, not in this module.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from industry.utils.helpers import interpolate_or_extrapolate
from industry.utils.helpers import get_scenarios

SCENARIOS = get_scenarios()

STANDARD_FUELS = [
    'diesel',
    'natural_gas',
    'electricity',
    'coal',
    'heat',
    'biomass',
    'hydrogen',
]

ALUMINIUM_INTENSITY_MWH_PER_T = 11.24


def _build_constant_intensity(
    target_years: List[int],
    scenarios: List[str],
    value: float,
) -> Dict[str, Dict[int, Dict[str, float]]]:
    """Build fuel-indexed constant intensity data for all fuels/scenarios/years."""
    years_with_base = sorted(set([2020] + target_years))
    return {
        fuel: {
            year: {scenario: value for scenario in scenarios}
            for year in years_with_base
        }
        for fuel in STANDARD_FUELS
    }


def intensity_primary_aluminium(
    target_years: List[int],
    scenarios: Optional[List[str]] = None,
) -> Dict[str, Dict[int, Dict[str, float]]]:
    """Fuel-indexed intensities for primary aluminium (MWh/t)."""
    if scenarios is None:
        scenarios = SCENARIOS
    return _build_constant_intensity(target_years, scenarios, ALUMINIUM_INTENSITY_MWH_PER_T)


def intensity_secondary_aluminium(
    target_years: List[int],
    scenarios: Optional[List[str]] = None,
) -> Dict[str, Dict[int, Dict[str, float]]]:
    """Fuel-indexed intensities for secondary aluminium (MWh/t)."""
    if scenarios is None:
        scenarios = SCENARIOS
    return _build_constant_intensity(target_years, scenarios, ALUMINIUM_INTENSITY_MWH_PER_T)


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

    primary_fuel_data = intensity_primary_aluminium(target_years, scenarios)
    secondary_fuel_data = intensity_secondary_aluminium(target_years, scenarios)

    years_with_base = sorted(set([2020] + target_years))

    primary_intensities = {
        year: {
            scenario: list(primary_fuel_data.values())[0][year][scenario]
            for scenario in scenarios
        }
        for year in years_with_base
    }
    secondary_intensities = {
        year: {
            scenario: list(secondary_fuel_data.values())[0][year][scenario]
            for scenario in scenarios
        }
        for year in years_with_base
    }

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
        'diesel': {
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
        'diesel': {
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
    for fuel in ['electricity', 'natural_gas', 'diesel']:
        share_2020 = fuel_shares['Primary aluminium'][fuel][2020]['Optimistic']
        share_2050 = fuel_shares['Primary aluminium'][fuel][2050]['Optimistic']
        print(f"  {fuel:15s}: 2020 = {share_2020:5.1%}  →  2050 = {share_2050:5.1%}")
    
    print("\n✓ Intensity assumption applied: 11.24 MWh/t for all routes/fuels.")
    print("   Future changes are controlled by exogenous intensity CAGR assumptions in config.\n")
