# scripts/industry/steel/build_shares_steel.py

from typing import Dict, List, Optional
import os
import sys
from pathlib import Path

from industry.build_CAGR import interpolate_or_extrapolate
from industry.helpers import get_scenarios_from_build_config_industry

SCENARIOS = get_scenarios_from_build_config_industry()


# =====================================================================
# Helper Function
# =====================================================================
def _interpolate_shares(
    base_data: Dict[str, Dict[int, List[float]]],
    target_years: List[int],
    scenarios: List[str]
) -> Dict[str, Dict[int, Dict[str, float]]]:

    def _clamp01(x: float) -> float:
        return max(0.0, min(100.0, float(x)))

    result: Dict[str, Dict[int, Dict[str, float]]] = {}

    # 1) Interpolate and CLAMP
    for fuel, yearly in base_data.items():
        result[fuel] = {}
        for i, sc in enumerate(scenarios):
            # per-scenario series from anchors
            sc_dict = {int(y): (vals[i] if i < len(vals) else vals[-1])
                       for y, vals in yearly.items()}

            #  include both anchor years (e.g. 2020, 2030, 2050) and target_years
            years_all = sorted(set(list(sc_dict.keys()) + target_years))

            interpolated = interpolate_or_extrapolate(sc_dict, years_all)

            for year, val in interpolated.items():
                result[fuel].setdefault(year, {})[sc] = _clamp01(val)

    # 2) Renormalize so shares across fuels sum to 100 per (year, scenario)
    years_union = sorted({y for f in result for y in result[f].keys()})
    for y in years_union:
        for sc in scenarios:
            total = sum(result[f].get(y, {}).get(sc, 0.0) for f in result.keys())
            if total > 0:
                scale = 100.0 / total
                for f in result.keys():
                    if sc in result[f].get(y, {}):
                        result[f][y][sc] = result[f][y][sc] * scale

    return result


# =====================================================================
# === BLAST FURNACE + OPEN HEARTH FURNACE (BF + OHF)
# =====================================================================

def share_fuel_bf_ohf(target_years: List[int], scenarios: Optional[List[str]] = None):
    """Fuel shares (% of BF + OHF production)."""
    if scenarios is None:
        scenarios = SCENARIOS

    base_data = {
        "diesel":      {
            2020: [100, 100, 100], 
            2030: [100, 100, 100], 
            2050: [100, 100, 100]},
        "natural_gas": {
            2020: [0, 0, 0],        
            2030: [0, 0, 0],        
            2050: [0, 0, 0]},
        "electricity": {
            2020: [0, 0, 0],        
            2030: [0, 0, 0],        
            2050: [0, 0, 0]},
        "coal":        {
            2020: [0, 0, 0],        
            2030: [0, 0, 0],        
            2050: [0, 0, 0]},
        "heat":        {
            2020: [0, 0, 0],        
            2030: [0, 0, 0],        
            2050: [0, 0, 0]},
        "biomass":     {
            2020: [0, 0, 0],        
            2030: [0, 0, 0],        
            2050: [0, 0, 0]},
        "hydrogen":    {
            2020: [0, 0, 0],        
            2030: [0, 0, 0],        
            2050: [0, 0, 0]},
    }

    return _interpolate_shares(base_data, target_years, scenarios)


# =====================================================================
# === BLAST FURNACE + BASIC OXYGEN FURNACE (BF + BOF)
# =====================================================================

def share_fuel_bf_bof(target_years: List[int], scenarios: Optional[List[str]] = None):
    """Fuel shares (% of BF + BOF)."""
    if scenarios is None:
        scenarios = SCENARIOS

    base_data = {
        "diesel":      {
            2020: [1, 1, 1],
            2030: [1, 0, 0], 
            2050: [1, 0, 0]},
        "natural_gas": {
            2020: [3, 3, 3],
            2030: [3, 0, 0], 
            2050: [3, 0, 0]},
        "electricity": {
            2020: [7, 7, 7],
            2030: [7, 5, 5], 
            2050: [7, 5, 5]},
        "coal":        {
            2020: [89, 89, 89],
            2030: [89, 75, 70], 
            2050: [89, 70, 60]},
        "heat":        {
            2020: [0, 0, 0],
            2030: [0, 0, 0], 
            2050: [0, 0, 0]},
        "biomass":     {
            2020: [0, 0, 0],
            2030: [0, 15, 15], 
            2050: [0, 15, 15]},
        "hydrogen":    {
            2020: [0, 0, 0],
            2030: [0, 5, 10], 
            2050: [0, 10, 20]},
    }



    return _interpolate_shares(base_data, target_years, scenarios)


# =====================================================================
# === DIRECT REDUCTION + ELECTRIC ARC FURNACE (DR + EAF)
# =====================================================================

def share_fuel_dr_eaf(target_years: List[int], scenarios: Optional[List[str]] = None):
    """Fuel shares (% of DR + EAF)."""
    if scenarios is None:
        scenarios = SCENARIOS

    base_data = {
        "diesel":      {
            2020: [1, 1, 1],
            2030: [1, 0, 0], 
            2050: [1, 0, 0]},
        "natural_gas": {
            2020: [38, 38, 38], 
            2030: [38, 0, 0], 
            2050: [38, 0, 0]},
        "electricity": {
            2020: [50, 50, 50], 
            2030: [50, 18, 18], 
            2050: [50, 18, 18]},
        "coal":        {
            2020: [11, 11, 11],
            2030: [11, 0, 0], 
            2050: [11, 0, 0]},
        "heat":        {
            2020: [0, 0, 0],
            2030: [0, 0, 0], 
            2050: [0, 0, 0]},
        "biomass":     {
            2020: [0, 0, 0],
            2030: [0, 0, 0], 
            2050: [0, 0, 0]},
        "hydrogen":    {
            2020: [0, 0, 0],
            2030: [0, 82, 82], 
            2050: [0, 82, 82]},
    }


    return _interpolate_shares(base_data, target_years, scenarios)


# =====================================================================
# === SCRAP ELECTRIC ARC FURNACE (EAF)
# =====================================================================

def share_fuel_scrap_eaf(target_years: List[int], scenarios: Optional[List[str]] = None):
    """Fuel shares (% of Scrap EAF)."""
    if scenarios is None:
        scenarios = SCENARIOS

    base_data = {
        "diesel":      {
            2020: [0, 0, 0],
            2030: [0, 0, 0], 
            2050: [0, 0, 0]},
        "natural_gas": {
            2020: [0, 0, 0],
            2030: [0, 17, 12], 
            2050: [0, 0, 0]},
        "electricity": {
            2020: [100, 100, 100],
            2030: [100, 73, 78], 
            2050: [100, 90, 90]},
        "coal":        {
            2020: [0, 0, 0],
            2030: [0, 0, 0], 
            2050: [0, 0, 0]},
        "heat":        {
            2020: [0, 0, 0],
            2030: [0, 0, 0], 
            2050: [0, 0, 0]},
        "biomass":     {
            2020: [0, 0, 0],
            2030: [0, 10, 10], 
            2050: [0, 10, 10]},
        "hydrogen":    {
            2020: [0, 0, 0],
            2030: [0, 0, 0], 
            2050: [0, 0, 0]},
    }

    return _interpolate_shares(base_data, target_years, scenarios)


# =====================================================================
# === CASTING, ROLLING & FINISHING
# =====================================================================

def share_fuel_casting_rolling(target_years: List[int], scenarios: Optional[List[str]] = None):
    """Fuel shares (% of casting, rolling, and finishing)."""
    if scenarios is None:
        scenarios = SCENARIOS

    base_data = {
        "diesel":      {
            2020: [50, 50, 50],
            2030: [50, 38, 26], 
            2050: [50, 14, 10]},
        "natural_gas": {
            2020: [0, 0, 0],
            2030: [0, 4, 4], 
            2050: [0, 4, 0]},
        "electricity": {
            2020: [50, 50, 50], 
            2030: [50, 50, 65],
            2050: [50, 80, 85]},
        "coal":        {
            2020: [0, 0, 0],
            2030: [0, 8, 5], 
            2050: [0, 0, 0]},
        "heat":  {
            2020: [0, 0, 0],      
            2030: [0, 0, 0], 
            2050: [0, 0, 0]},
        "biomass":     {
            2020: [0, 0, 0],
            2030: [0, 0, 0], 
            2050: [0, 0, 0]},
        "hydrogen":    {
            2020: [0, 0, 0],
            2030: [0, 0, 0], 
            2050: [0, 2, 5]},
    }

    return _interpolate_shares(base_data, target_years, scenarios)


# =====================================================================
# === UNSPECIFIED STEEL
# =====================================================================

def share_fuel_unspecified_steel(target_years: List[int], scenarios: Optional[List[str]] = None):
    """Fuel shares (% of unspecified steel category)."""
    if scenarios is None:
        scenarios = SCENARIOS

    base_data = {
        "diesel": {
            2020: [4, 4, 4],
            2030: [4, 38, 26],
            2050: [4, 14, 10],
        },
        "natural_gas": {
            2020: [7, 7, 7],
            2030: [7, 4, 4],
            2050: [7, 4, 0],
        },
        "electricity": {
            2020: [89, 89, 89],
            2030: [89, 50, 65],
            2050: [89, 80, 85],
        },
        "coal": {
            2020: [0, 0, 0],
            2030: [0, 8, 5],
            2050: [0, 0, 0],
        },
        "heat": {
            2020: [0, 0, 0],
            2030: [0, 0, 0],
            2050: [0, 0, 0],
        },
        "biomass": {
            2020: [0, 0, 0],
            2030: [0, 0, 0],
            2050: [0, 0, 0],
        },
        "hydrogen": {
            2020: [0, 0, 0],
            2030: [0, 0, 0],
            2050: [0, 2, 5],
        },
    }
    return _interpolate_shares(base_data, target_years, scenarios)


# =====================================================================
# === PRODUCTION ROUTE SHARES
# =====================================================================

def share_route_steel(target_years: List[int], scenarios: Optional[List[str]] = None):
    """Production route shares (% of total steel production)."""
    if scenarios is None:
        scenarios = SCENARIOS

    base_data = {
        "bf_ohf": {
            2020: [0, 0, 0],
            2030: [0, 0, 0],
            2050: [0, 0, 0]},
        "bf_bof": {
            2020: [100, 100, 100],
            2030: [14, 7, 7],
            2050: [0, 0, 0]},
        "dr_eaf": {
            2020: [0, 0, 0],
            2030: [86, 93, 93],
            2050: [100, 100, 100]},
    }

    return _interpolate_shares(base_data, target_years, scenarios)


# =====================================================================
# Helper for route normalization
# =====================================================================
def _normalize(a: Optional[float], b: Optional[float], c: Optional[float]):
    a = 0.0 if a is None else float(a)
    b = 0.0 if b is None else float(b)
    c = 0.0 if c is None else float(c)
    s = a + b + c
    if s == 0:
        return 0.0, 0.0, 0.0
    return a * 100.0 / s, b * 100.0 / s, c * 100.0 / s


# =====================================================================
# === OVERRIDE FUNCTION FOR STEEL ROUTES
# =====================================================================
def override_steel_routes_positional(
    target_years: List[int],
    scenarios: List[str],
    share_bf_ohf: Dict[int, Dict[str, float]],
    share_bf_bof: Dict[int, Dict[str, float]],
    share_dr_eaf: Dict[int, Dict[str, float]],
    base_year: int,
):
    """
    Apply share_route_steel values to override capacity-derived shares.
    Keeps base_year from capacity; uses share_route_steel for target years.
    """
    # Get route shares from share_route_steel function
    route_shares = share_route_steel(target_years, scenarios)
    
    # Ensure top-level containers are dicts-of-dicts
    def _ensure_year_dict(d: Dict[int, Dict[str, float]], y: int):
        if y not in d or not isinstance(d.get(y), dict):
            d[y] = {}

    for y in target_years:
        if y == base_year:
            # leave capacity-derived base year intact
            continue

        for sc in scenarios:
            a = route_shares.get("bf_ohf", {}).get(y, {}).get(sc, 0.0)
            b = route_shares.get("bf_bof", {}).get(y, {}).get(sc, 0.0)
            c = route_shares.get("dr_eaf", {}).get(y, {}).get(sc, 0.0)

            A, B, C = _normalize(a, b, c)

            _ensure_year_dict(share_bf_ohf, y)
            _ensure_year_dict(share_bf_bof, y)
            _ensure_year_dict(share_dr_eaf, y)
            share_bf_ohf[y][sc] = A
            share_bf_bof[y][sc] = B
            share_dr_eaf[y][sc] = C

    return share_bf_ohf, share_bf_bof, share_dr_eaf, True


# =====================================================================
# === PRIMARY AND SECONDARY STEEL SHARES
# =====================================================================
def share_steel_primary_secondary(target_years: List[int], scenarios: Optional[List[str]] = None):
    """
    Returns shares for primary and secondary steel production.
    
    Primary steel: NEW steel production from iron ore (using BF+BOF or DR+EAF routes)
    Secondary steel: RECYCLED steel production from scrap (using Scrap EAF)
    
    These shares always sum to 100% of total steel production.
    
    Returns:
        Dict with structure: {
            'primary': {year: {scenario: value}},
            'secondary': {year: {scenario: value}}
        }
    """
    if scenarios is None:
        scenarios = SCENARIOS
    
    base_data = {
        "primary": {
            2020: [80.0, 80.0, 80.0],    # [BAU, Progressive, Optimistic]
            2030: [80.0, 80.0, 80.0],
            2050: [80.0, 70.0, 70.0],    # Progressive/Optimistic decline
        },
        "secondary": {
            2020: [20.0, 20.0, 20.0],
            2030: [20.0, 20.0, 20.0],
            2050: [20.0, 30.0, 30.0],    # Progressive/Optimistic increase
        },
    }
    
    return _interpolate_shares(base_data, target_years, scenarios)
