# scripts/industry/steel/build_shares_steel.py

from typing import Dict, List, Optional
import os
import sys

# Add parent directories to Python path to import cagr_helper
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from build_CAGR import interpolate_or_extrapolate
from helpers import get_scenarios_from_main_industry

SCENARIOS = get_scenarios_from_main_industry()


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
            2020: [1, 0, 0],
            2030: [1, 0, 0], 
            2050: [1, 0, 0]},
        "natural_gas": {
            2020: [3, 0, 0],
            2030: [3, 0, 0], 
            2050: [3, 0, 0]},
        "electricity": {
            2020: [7, 5, 5],
            2030: [7, 5, 5], 
            2050: [7, 5, 5]},
        "coal":        {
            2020: [89, 75, 70],
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
            2020: [1, 0, 0],
            2030: [1, 0, 0], 
            2050: [1, 0, 0]},
        "natural_gas": {
            2020: [38, 0, 0], 
            2030: [38, 0, 0], 
            2050: [38, 0, 0]},
        "electricity": {
            2020: [50, 0, 0], 
            2030: [50, 18, 18], 
            2050: [50, 18, 18]},
        "coal":        {
            2020: [11, 0, 0],
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
            2020: [3, 3, 3],
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


# helpers_routes_overrides.py
COUNTRY_ROUTE_OVERRIDES_POS: Dict[str, Dict[int, Dict[str, List[float]]]] = {
    "Morocco": {
        2030: {
            "bf_ohf": [0, 0, 0],
            "bf_bof": [0, 90, 75],
            "dr_eaf": [100, 10, 25],
        },
        2050: {
            "bf_ohf": [0, 0, 0],
            "bf_bof": [0, 50, 0],
            "dr_eaf": [100, 50, 100],
        },
    },
    "Egypt": {
        2030: {
            "bf_ohf": [43, 43, 46],
            "bf_bof": [43, 43, 46],
            "dr_eaf": [14, 14, 8],
        },
        2050: {
            "bf_ohf": [0, 0, 0],
            "bf_bof": [0, 0, 0],
            "dr_eaf": [100, 100, 100],
        },
    },
    "Chile": {
        2030: {
            "bf_ohf": [35, 35, 25],
            "bf_bof": [35, 35, 25],
            "dr_eaf": [30, 30, 50],
        },
        2050: {
            "bf_ohf": [0, 20, 0],
            "bf_bof": [0, 20, 0],
            "dr_eaf": [100, 60, 100],
        },
    },
}

# --- tiny helpers (if you don't already have them) ---
from typing import Dict, List, Optional
import numpy as np

def _get_pos(arr: List[float], i: int) -> Optional[float]:
    return float(arr[i]) if (arr and 0 <= i < len(arr)) else None

def _interp_series(points: Dict[int, float], years: List[int]) -> Dict[int, float]:
    # linear interpolate/extrapolate on integers
    if not points:
        return {}
    xs = sorted(points.keys())
    ys = [float(points[x]) for x in xs]
    out: Dict[int, float] = {}
    for y in years:
        # exact
        if y in points:
            out[y] = float(points[y])
            continue
        # left/right extrapolate
        if y < xs[0]:
            if len(xs) == 1:
                out[y] = ys[0]
            else:
                x0, x1 = xs[0], xs[1]
                y0, y1 = points[x0], points[x1]
                out[y] = y0 + (y - x0) * (y1 - y0) / (x1 - x0)
            continue
        if y > xs[-1]:
            if len(xs) == 1:
                out[y] = ys[0]
            else:
                x0, x1 = xs[-2], xs[-1]
                y0, y1 = points[x0], points[x1]
                out[y] = y0 + (y - x0) * (y1 - y0) / (x1 - x0)
            continue
        # interpolate between neighbors
        for k in range(1, len(xs)):
            if xs[k-1] < y < xs[k]:
                x0, x1 = xs[k-1], xs[k]
                y0, y1 = points[x0], points[x1]
                out[y] = y0 + (y - x0) * (y1 - y0) / (x1 - x0)
                break
    return out

def _normalize(a: Optional[float], b: Optional[float], c: Optional[float]):
    a = 0.0 if a is None else float(a)
    b = 0.0 if b is None else float(b)
    c = 0.0 if c is None else float(c)
    s = a + b + c
    if s == 0:
        return 0.0, 0.0, 0.0
    return a * 100.0 / s, b * 100.0 / s, c * 100.0 / s

# --- robust override function ---
def override_steel_routes_positional(
    country: str,
    target_years: List[int],
    scenarios: List[str],
    share_bf_ohf: Dict[int, Dict[str, float]],
    share_bf_bof: Dict[int, Dict[str, float]],
    share_dr_eaf: Dict[int, Dict[str, float]],
    base_year: int,
):
    """
    Apply COUNTRY_ROUTE_OVERRIDES_POS by *scenario position* (index in `scenarios`).
    Keeps base_year from capacity; interpolates missing years; renormalizes to 100.
    Never assumes a year entry is a dict (fixes 'numpy.float64 does not support item assignment').
    """
    if country not in COUNTRY_ROUTE_OVERRIDES_POS:
        return share_bf_ohf, share_bf_bof, share_dr_eaf, False

    manual = COUNTRY_ROUTE_OVERRIDES_POS[country]     # {year: {"bf_ohf":[...], "bf_bof":[...], "dr_eaf":[...]}}
    years = sorted(set([base_year, *target_years]))
    routes = ("bf_ohf", "bf_bof", "dr_eaf")

    # Ensure top-level containers are dicts-of-dicts
    def _ensure_year_dict(d: Dict[int, Dict[str, float]], y: int):
        if y not in d or not isinstance(d.get(y), dict):
            d[y] = {}

    for i, sc in enumerate(scenarios):
        # collect sparse points per route for this scenario position
        pts = {r: {} for r in routes}
        for y, rmap in manual.items():
            for r in routes:
                v = _get_pos(rmap.get(r, []), i)
                if v is not None:
                    pts[r][y] = v

        # interpolate across requested years
        series = {r: _interp_series(pts[r], years) for r in routes}

        for y in years:
            if y == base_year:
                # leave capacity-derived base year intact
                continue

            a = series["bf_ohf"].get(y)
            b = series["bf_bof"].get(y)
            c = series["dr_eaf"].get(y)

            # fallback to existing values if any is missing
            if a is None:
                a = (share_bf_ohf.get(y, {}).get(sc)
                     if isinstance(share_bf_ohf.get(y), dict) else share_bf_ohf.get(y))
            if b is None:
                b = (share_bf_bof.get(y, {}).get(sc)
                     if isinstance(share_bf_bof.get(y), dict) else share_bf_bof.get(y))
            if c is None:
                c = (share_dr_eaf.get(y, {}).get(sc)
                     if isinstance(share_dr_eaf.get(y), dict) else share_dr_eaf.get(y))

            # still missing? skip this (y, sc)
            if a is None or b is None or c is None:
                continue

            A, B, C = _normalize(a, b, c)

            # now it's safe to assign
            _ensure_year_dict(share_bf_ohf, y)
            _ensure_year_dict(share_bf_bof, y)
            _ensure_year_dict(share_dr_eaf, y)
            share_bf_ohf[y][sc] = A
            share_bf_bof[y][sc] = B
            share_dr_eaf[y][sc] = C

    return share_bf_ohf, share_bf_bof, share_dr_eaf, True
