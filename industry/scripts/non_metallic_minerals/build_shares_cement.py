# scripts/non_metallic_minerals/build_shares_cement.py

from typing import Dict, List, Optional
import os
import sys

# add parent path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from cagr_helper import interpolate_or_extrapolate


# ---------------------------------------------------------------------
# generic helper – SAME PATTERN AS STEEL
# ---------------------------------------------------------------------
def _interpolate_shares(
    base_data: Dict[str, Dict[int, List[float]]],
    target_years: List[int],
    scenarios: List[str],
) -> Dict[str, Dict[int, Dict[str, float]]]:
    result: Dict[str, Dict[int, Dict[str, float]]] = {}
    all_years = [2020] + target_years

    for fuel, yearly in base_data.items():
        result[fuel] = {}
        for i, sc in enumerate(scenarios):
            # make per-scenario series
            series = {
                year: vals[i] if i < len(vals) else vals[-1]
                for year, vals in yearly.items()
            }
            series_interp = interpolate_or_extrapolate(series, all_years)
            for y, v in series_interp.items():
                result[fuel].setdefault(y, {})[sc] = v

    TOL = 1.0  # percent tolerance
    for y in all_years:
        for sc in scenarios:
            total = sum(result[f][y][sc] for f in result)
            if total > 100.0 + TOL:
                print(f"Cement shares exceed 100%: {total:.2f}% in {y} ({sc})")


    return result


# ---------------------------------------------------------------------
# Cement fuel shares – NOW SAME STRUCTURE AS STEEL
# ---------------------------------------------------------------------
def share_fuel_cement_production(
    target_years: List[int],
    scenarios: Optional[List[str]] = None,
) -> Dict[str, Dict[int, Dict[str, float]]]:
    if scenarios is None:
        scenarios = ["Baseline", "Ambitious Policies", "Net Zero"]

    # exactly your Excel numbers
    base_data = {
        "diesel": {
            2020: [78, 78, 78],
            2030: [78, 73, 67],
            2050: [78, 45, 15],
        },
        "natural_gas": {
            2020: [4, 4, 4],
            2030: [4, 2, 1],
            2050: [4, 0, 0],
        },
        "electricity": {
            2020: [12, 12, 12],
            2030: [12, 20, 25],
            2050: [12, 35, 50],
        },
        "coal": {
            2020: [2, 2, 2],
            2030: [2, 0, 0],
            2050: [2, 0, 0],
        },
        "heat": {
            2020: [0, 0, 0],
            2030: [0, 0, 0],
            2050: [0, 0, 0],
        },
        "biomass": {
            2020: [4, 4, 4],
            2030: [4, 5, 5],
            2050: [4, 5, 5],
        },
        "hydrogen": {
            2020: [0, 0, 0],
            2030: [0, 0.1, 2],
            2050: [0, 15, 30],
        },
    }

    return _interpolate_shares(base_data, target_years, scenarios)


# ---------------------------------------------------------------------
# Unspecified NMM fuel shares – SAME PATTERN
# ---------------------------------------------------------------------
def share_fuel_unspecified_nmm(
    target_years: List[int],
    scenarios: Optional[List[str]] = None,
) -> Dict[str, Dict[int, Dict[str, float]]]:
    if scenarios is None:
        scenarios = ["Baseline", "Ambitious Policies", "Net Zero"]

    base_data = {
        "diesel": {
            2020: [78, 78, 78],
            2030: [78, 70, 59],
            2050: [78, 20, 10],
        },
        "natural_gas": {
            2020: [4, 4, 4],
            2030: [4, 5, 5],
            2050: [4, 10, 0],
        },
        "electricity": {
            2020: [12, 12, 12],
            2030: [12, 20, 30],
            2050: [12, 50, 60],
        },
        "coal": {
            2020: [2, 2, 2],
            2030: [2, 0, 0],
            2050: [2, 0, 0],
        },
        "heat": {
            2020: [0, 0, 0],
            2030: [0, 0, 0],
            2050: [0, 0, 0],
        },
        "biomass": {
            2020: [4, 4, 4],
            2030: [4, 5, 5],
            2050: [4, 5, 5],
        },
        "hydrogen": {
            2020: [0, 0, 0],
            2030: [0, 0.1, 1],
            2050: [0, 15, 25],
        },
    }

    return _interpolate_shares(base_data, target_years, scenarios)

