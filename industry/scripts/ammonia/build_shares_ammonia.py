# scripts/chemicals/ammonia/build_shares_ammonia.py

from typing import Dict, List, Optional
import os
import sys

# Go up two levels (ammonia → chemicals → scripts)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from cagr_helper import interpolate_or_extrapolate


# ============================================================
# AMMONIA SHARES
# ============================================================

def share_fuel_ammonia_smr_hb(target_years: List[int], scenarios: Optional[List[str]] = None):
    if scenarios is None:
        scenarios = ["Baseline", "Ambitious Policies", "Net Zero"]

    base_data = {
        "diesel": {
            2020: [0, 0, 0], 
            2030: [0, 0, -40], 
            2050: [0, 0, 0]},
        "natural_gas": {
            2020: [97, 97, 97], 
            2030: [97, 96, 92], 
            2050: [97, 85, 60]},
        "electricity": {
            2020: [3, 3, 3], 
            2030: [3, 4, 8], 
            2050: [3, 15, 40]},
        "coal": {
            2020: [0, 0, 0], 
            2030: [0, 0, 0], 
            2050: [0, 0, 0]},
        "heat": {
            2020: [0, 0, 0], 
            2030: [0, 0, 0], 
            2050: [0, 0, 0]},
        "biomass": {
            2020: [0, 0, 0], 
            2030: [0, 0, 0], 
            2050: [0, 0, 0]},
        "hydrogen": {
            2020: [0, 0, 0], 
            2030: [0, 0, 40], 
            2050: [0, 0, 0]},
    }

    return _interpolate_shares(base_data, target_years, scenarios)



def share_fuel_ammonia_renewable(target_years: List[int], scenarios: Optional[List[str]] = None):
    if scenarios is None:
        scenarios = ["Baseline", "Ambitious Policies", "Net Zero"]

    base_data = {
        "diesel": {
            2020: [0, 0, 0], 
            2030: [0, 0, 0], 
            2050: [0, 0, 0]},
        "natural_gas": {
            2020: [0, 0, 0], 
            2030: [0, 0, 0], 
            2050: [0, 0, 0]},
        "electricity": {
            2020: [100, 100, 100], 
            2030: [100, 100, 100], 
            2050: [100, 100, 100]},
        "coal": {
            2020: [0, 0, 0], 
            2030: [0, 0, 0],
            2050: [0, 0, 0]},
        "heat": {
            2020: [0, 0, 0], 
            2030: [0, 0, 0], 
            2050: [0, 0, 0]},
        "biomass": {
            2020: [0, 0, 0], 
            2030: [0, 0, 0], 
            2050: [0, 0, 0]},
        "hydrogen": {
            2020: [0, 0, 0], 
            2030: [0, 0, 0], 
            2050: [0, 0, 0]},
    }

    return _interpolate_shares(base_data, target_years, scenarios)


# ============================================================
# HVC SHARES
# ============================================================

def share_fuel_hvc_naphtha_cracking(target_years: List[int], scenarios: Optional[List[str]] = None):
    if scenarios is None:
        scenarios = ["Baseline", "Ambitious Policies", "Net Zero"]

    base_data = {
        "diesel": {
            2020: [0, 0, 0], 
            2030: [0, 0, 0], 
            2050: [0, 0, 0]},
        "natural_gas": {
            2020: [98, 98, 98], 
            2030: [98, 96, 93], 
            2050: [98, 72, 30]},
        "electricity": {
            2020: [2, 2, 2], 
            2030: [2, 4, 6], 
            2050: [2, 25, 50]},
        "coal": {
            2020: [0, 0, 0], 
            2030: [0, 0, 0], 
            2050: [0, 0, 0]},
        "heat": {
            2020: [0, 0, 0], 
            2030: [0, 0, 0], 
            2050: [0, 0, 0]},
        "biomass": {
            2020: [0, 0, 0], 
            2030: [0, 0, 0], 
            2050: [0, 0, 0]},
        "hydrogen": {
            2020: [0, 0, 0], 
            2030: [0, 0, 1], 
            2050: [0, 3, 20]},
    }

    return _interpolate_shares(base_data, target_years, scenarios)


def share_fuel_hvc_lpg_cracking(target_years: List[int], scenarios: Optional[List[str]] = None):
    if scenarios is None:
        scenarios = ["Baseline", "Ambitious Policies", "Net Zero"]

    base_data = {
        "diesel": {
            2020: [0, 0, 0], 
            2030: [0, 0, 0], 
            2050: [0, 0, 0]},
        "natural_gas": {
            2020: [99, 99, 99], 
            2030: [99, 96, 93], 
            2050: [99, 72, 30]},
        "electricity": {
            2020: [1, 1, 1], 
            2030: [1, 4, 6], 
            2050: [1, 25, 50]},
        "coal": {
            2020: [0, 0, 0], 
            2030: [0, 0, 0], 
            2050: [0, 0, 0]},
        "heat": {
            2020: [0, 0, 0], 
            2030: [0, 0, 0], 
            2050: [0, 0, 0]},
        "biomass": {
            2020: [0, 0, 0], 
            2030: [0, 0, 0], 
            2050: [0, 0, 0]},
        "hydrogen": {
            2020: [0, 0, 0], 
            2030: [0, 0, 1], 
            2050: [0, 3, 20]},
    }

    return _interpolate_shares(base_data, target_years, scenarios)


def share_fuel_hvc_methanol_route(target_years: List[int], scenarios: Optional[List[str]] = None):
    if scenarios is None:
        scenarios = ["Baseline", "Ambitious Policies", "Net Zero"]

    base_data = {
        "diesel": {
            2020: [0, 0, 0], 
            2030: [0, 26, 0], 
            2050: [0, 0, 0]},
        "natural_gas": {
            2020: [76, 76, 76], 
            2030: [76, 0, 0], 
            2050: [76, 0, 0]},
        "electricity": {
            2020: [24, 24, 24], 
            2030: [24, 24, 24], 
            2050: [24, 24, 24]},
        "coal": {
            2020: [0, 0, 0], 
            2030: [0, 0, 0], 
            2050: [0, 0, 0]},
        "heat": {
            2020: [0, 0, 0], 
            2030: [0, 0, 0], 
            2050: [0, 0, 0]},
        "biomass": {
            2020: [0, 0, 0], 
            2030: [0, 0, 0], 
            2050: [0, 0, 0]},
        "hydrogen": {
            2020: [0, 0, 0], 
            2030: [0, 50, 76], 
            2050: [0, 76, 76]},
    }

    return _interpolate_shares(base_data, target_years, scenarios)


def share_fuel_unspecified_chemicals(target_years: List[int], scenarios: Optional[List[str]] = None):
    if scenarios is None:
        scenarios = ["Baseline", "Ambitious Policies", "Net Zero"]

    base_data = {
        "diesel": {
            2020: [100, 100, 100],
            2030: [100, 0, 0], 
            2050: [100, 0, 0]},
        "natural_gas": {
            2020: [0, 0, 0], 
            2030: [0, 84, 73], 
            2050: [0, 25, 0]},
        "electricity": {
            2020: [0, 0, 0], 
            2030: [0, 15, 25], 
            2050: [0, 70, 90]},
        "coal": {
            2020: [0, 0, 0], 
            2030: [0, 0, 0], 
            2050: [0, 0, 0]},
        "heat": {
            2020: [0, 0, 0], 
            2030: [0, 0, 0], 
            2050: [0, 0, 0]},
        "biomass": {
            2020: [0, 0, 0], 
            2030: [0, 0, 0], 
            2050: [0, 0, 0]},
        "hydrogen": {
            2020: [0, 0, 0], 
            2030: [0, 1, 2], 
            2050: [0, 5, 10]},
    }

    return _interpolate_shares(base_data, target_years, scenarios)


from typing import List, Dict, Optional

def share_HVC_production(
    target_years: List[int],
    scenarios: Optional[List[str]] = None
) -> Dict[str, Dict[int, Dict[str, float]]]:
    if scenarios is None:
        scenarios = ["Baseline", "Ambitious Policies", "Net Zero"]

    base_data = {
        "Naphtha": {
            2020: [70, 70, 70],
            2030: [70, 69, 61],
            2050: [70, 51, 100],
        },
        "LPG": {
            2020: [20, 20, 20],
            2030: [20, 25, 30],
            2050: [20, 45, 0],
        },
        "Methanol": {
            2020: [10, 10, 10],
            2030: [10, 6, 9],
            2050: [10, 4, 0],
        },
    }

    # Reuse your existing helper
    shares = _interpolate_shares(base_data, target_years, scenarios)

    for y in [2020] + target_years:
        for i, sc in enumerate(scenarios):
            total = sum(shares[r][y][sc] for r in shares)
            if total and abs(total - 100.0) > 0.1:
                for r in shares:
                    shares[r][y][sc] = shares[r][y][sc] * 100.0 / total

    return shares

# ============================================================
# HELPER FUNCTION
# ============================================================

def _interpolate_shares(base_data: Dict[str, Dict[int, List[float]]],
                        target_years: List[int],
                        scenarios: List[str]) -> Dict[str, Dict[int, Dict[str, float]]]:
    """Reusable helper to interpolate/extrapolate fuel share data across scenarios."""
    result = {}
    for fuel, yearly in base_data.items():
        result[fuel] = {}
        for i, sc in enumerate(scenarios):
            year_values = {year: vals[i] if i < len(vals) else vals[-1] for year, vals in yearly.items()}
            interpolated = interpolate_or_extrapolate(year_values, [2020] + target_years)
            for year, val in interpolated.items():
                result[fuel].setdefault(year, {})[sc] = val
    return result
