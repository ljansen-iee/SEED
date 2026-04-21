# scripts/industry/steel/build_energy_intensities_steel.py

from typing import Dict, List, Optional
import os
import sys
from pathlib import Path

from industry.build_CAGR import interpolate_or_extrapolate


def _interpolate_intensities(
    base_data: Dict[str, Dict[int, List[float]]],
    years: List[int],
    scenarios: List[str],
) -> Dict[str, Dict[int, Dict[str, float]]]:
    """
    Name-agnostic (index-based) interpolation.
    - We never look up by scenario name; we map by index 0..N-1.
    - We compute for the union of base_data knot years and requested 'years'
      so callers still see base-year values even if they didn't pass it in 'years'.
    base_data shape per fuel:
      {year -> vals} where vals can be:
        * list/tuple  (positional per scenario index)
        * dict        (we IGNORE KEYS and use insertion order positionally)
        * scalar      (broadcast to all scenarios)
    Returns: {fuel -> {year -> {scenario_name -> value}}}
    """
    def _val_at_index(vals, i: int) -> float:
        if vals is None:
            return None
        if isinstance(vals, (list, tuple)):
            return float(vals[i] if i < len(vals) else vals[-1])
        if isinstance(vals, dict):
            arr = list(vals.values())
            return float(arr[i] if i < len(arr) else arr[-1])
        return float(vals)  # scalar broadcast

    out: Dict[str, Dict[int, Dict[str, float]]] = {}

    for fuel, yearly in base_data.items():
        # union so we also emit knot years (e.g. 2020) even if caller only asked for [2030,2050]
        years_union = sorted(set(int(y) for y in yearly.keys()) | set(int(y) for y in years))
        out[fuel] = {}
        for i, sc in enumerate(scenarios):
            # build per-scenario series purely by index
            series = {int(y): _val_at_index(vals, i) for y, vals in yearly.items() if _val_at_index(vals, i) is not None}
            # interpolate/extrapolate over all desired years (incl. knots)
            filled = interpolate_or_extrapolate(series, years_union) if series else {y: None for y in years_union}
            for y in years_union:
                out[fuel].setdefault(int(y), {})[sc] = filled.get(int(y))
    return out


def _resolve_scenarios(
    scenarios: Optional[List[str]],
    base_data: Dict[str, Dict[int, List[float]]],
) -> List[str]:
    if scenarios:
        return scenarios

    max_len = 0
    for yearly in base_data.values():
        for vals in yearly.values():
            if vals is None:
                continue
            if isinstance(vals, (list, tuple)):
                max_len = max(max_len, len(vals))
            elif isinstance(vals, dict):
                max_len = max(max_len, len(vals))
            else:
                max_len = max(max_len, 1)

    n = max_len if max_len > 0 else 1
    return [f"Scenario_{i + 1}" for i in range(n)]


def intensity_bf_ohf(target_years: List[int], scenarios: Optional[List[str]] = None):
    # Identical for all scenarios but kept flexible
    base_data = {
        "diesel":      {
            2020: [5.20, 5.20, 5.20], 
            2030: [5.20, 5.20, 5.20], 
            2050: [5.20, 5.20, 5.20]},
        "natural_gas": {
            2020: [5.20, 5.20, 5.20], 
            2030: [5.20, 5.20, 5.20], 
            2050: [5.20, 5.20, 5.20]},
        "electricity": {
            2020: [5.20, 5.20, 5.20], 
            2030: [5.20, 5.20, 5.20], 
            2050: [5.20, 5.20, 5.20]},
        "coal":        {
            2020: [5.20, 5.20, 5.20], 
            2030: [5.20, 5.20, 5.20], 
            2050: [5.20, 5.20, 5.20]},
        "heat":        {
            2020: [5.20, 5.20, 5.20], 
            2030: [5.20, 5.20, 5.20], 
            2050: [5.20, 5.20, 5.20]},
        "biomass":     {
            2020: [5.20, 5.20, 5.20], 
            2030: [5.20, 5.20, 5.20], 
            2050: [5.20, 5.20, 5.20]},
        "hydrogen":    {
            2020: [5.20, 5.20, 5.20], 
            2030: [5.20, 5.20, 5.20], 
            2050: [5.20, 5.20, 5.20]},
    }

    scenarios = _resolve_scenarios(scenarios, base_data)

    return _interpolate_intensities(base_data, target_years, scenarios)


def intensity_bf_bof(target_years: List[int], scenarios: Optional[List[str]] = None):
    """Energy intensities (MWh/t) for Blast Furnace + Basic Oxygen Furnace (BF + BOF)."""
    base_data = {
        "diesel":      {
            2020: [6.72, 6.72, 6.72], 
            2030: [6.72, 6.72, 6.72], 
            2050: [6.72, 6.72, 6.72]},
        "natural_gas": {
            2020: [6.72, 6.72, 6.72], 
            2030: [6.72, 6.72, 6.72], 
            2050: [6.72, 6.72, 6.72]},
        "electricity": {
            2020: [6.72, 6.72, 6.72], 
            2030: [6.72, 6.72, 6.72], 
            2050: [6.72, 6.72, 6.72]},
        "coal":        {
            2020: [6.72, 6.72, 6.72], 
            2030: [6.72, 6.72, 6.72], 
            2050: [6.72, 6.72, 6.72]},
        "heat":        {
            2020: [6.72, 6.72, 6.72], 
            2030: [6.72, 6.72, 6.72],
            2050: [6.72, 6.72, 6.72]},
        "biomass":     {
            2020: [6.72, 6.72, 6.72], 
            2030: [6.72, 6.72, 6.72], 
            2050: [6.72, 6.72, 6.72]},
        "hydrogen":    {
            2020: [6.72, 6.72, 6.72], 
            2030: [6.72, 6.72, 6.72], 
            2050: [6.72, 6.72, 6.72]},
    }

    scenarios = _resolve_scenarios(scenarios, base_data)

    return _interpolate_intensities(base_data, target_years, scenarios)

def intensity_dr_eaf(target_years: List[int], scenarios: Optional[List[str]] = None):
    """Energy intensities (MWh/t) for Direct Reduction + Electric Arc Furnace (DR + EAF)."""
    base_data = {
        "diesel":      {
            2020: [2.87, 2.87, 2.87],
            2030: [2.87, 2.87, 2.85],
            2050: [2.87, 2.87, 2.79]
            },
        "natural_gas": {
            2020: [2.87, 2.87, 2.87],
            2030: [2.87, 2.87, 2.85],
            2050: [2.87, 2.87, 2.79]
            },
        "electricity": {
            2020: [2.87, 2.87, 2.87],
            2030: [2.87, 2.87, 2.85],
            2050: [2.87, 2.87, 2.87]
            },
        "coal":        {
            2020: [2.87, 2.87, 2.87],
            2030: [2.87, 2.87, 2.85],
            2050: [2.87, 2.87, 2.79]
            },
        "heat":        {
            2020: [2.87, 2.87, 2.87],
            2030: [2.87, 2.87, 2.85],
            2050: [2.87, 2.87, 2.79]
            },
        "biomass":     {
            2020: [2.87, 2.87, 2.87],
            2030: [2.87, 2.87, 2.85],
            2050: [2.87, 2.87, 2.79]
            },
        "hydrogen":    {
            2020: [2.87, 2.87, 2.87],
            2030: [2.87, 2.85, 2.85],
            2050: [2.87, 2.87, 2.87]},
    }

    scenarios = _resolve_scenarios(scenarios, base_data)

    return _interpolate_intensities(base_data, target_years, scenarios)


def intensity_scrap_eaf(target_years: List[int], scenarios: Optional[List[str]] = None):
    """Energy intensities (MWh/t) for Scrap-based Electric Arc Furnaces (EAF)."""
    base_data = {
        "diesel":      {
            2020: [0.58, 0.58, 0.58], 
            2030: [0.58, 0.58, 0.57], 
            2050: [0.58, 0.58, 0.56]},
        "natural_gas": {
            2020: [0.58, 0.58, 0.58], 
            2030: [0.58, 0.58, 0.57], 
            2050: [0.58, 0.58, 0.56]},
        "electricity": {
            2020: [0.58, 0.58, 0.58], 
            2030: [0.58, 0.58, 0.57], 
            2050: [0.58, 0.58, 0.56]},
        "coal":        {
            2020: [0.58, 0.58, 0.58], 
            2030: [0.58, 0.58, 0.57], 
            2050: [0.58, 0.58, 0.56]},
        "heat":        {
            2020: [0.58, 0.58, 0.58], 
            2030: [0.58, 0.58, 0.57], 
            2050: [0.58, 0.58, 0.56]},
        "biomass":     {
            2020: [0.58, 0.58, 0.58], 
            2030: [0.58, 0.58, 0.57], 
            2050: [0.58, 0.58, 0.56]},
        "hydrogen":    {
            2020: [0.58, 0.58, 0.58], 
            2030: [0.58, 0.58, 0.57], 
            2050: [0.58, 0.58, 0.56]},
    }

    scenarios = _resolve_scenarios(scenarios, base_data)

    return _interpolate_intensities(base_data, target_years, scenarios)


def intensity_casting_rolling(target_years: List[int], scenarios: Optional[List[str]] = None):
    """Total energy intensity (MWh/t) for Casting, Rolling & Finishing (not fuel-specific)."""
    # Values differ slightly across scenarios
    base_data = {
        "total": {
            2020: [0.94, 0.94, 0.93],
            2030: [0.94, 0.94, 0.93],
            2050: [0.94, 0.94, 0.91],
        }
    }

    scenarios = _resolve_scenarios(scenarios, base_data)

    return _interpolate_intensities(base_data, target_years, scenarios)
