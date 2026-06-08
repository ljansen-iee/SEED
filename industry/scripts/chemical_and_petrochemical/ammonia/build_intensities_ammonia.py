# scripts/ammonia/build_intensities_ammonia.py

import os
import sys
import numpy as np  
from typing import Dict, List, Optional
from pathlib import Path

from industry.utils.helpers import get_scenarios_from_build_config_industry

SCENARIOS = get_scenarios_from_build_config_industry()

def interpolate_or_extrapolate(data: Dict[int, float], target_years: List[int]) -> Dict[int, float]:
    """
    Interpolates or extrapolates values for given target years.
    Example: {2020: 10, 2030: 12, 2050: 16} → fills 2040 automatically.
    """
    years = sorted(data.keys())
    values = [data[y] for y in years]

    interpolated = {}
    for t in target_years:
        # numpy interpolation handles in-between; extrapolate if outside
        if t <= years[0]:
            interpolated[t] = values[0] + (values[1] - values[0]) / (years[1] - years[0]) * (t - years[0])
        elif t >= years[-1]:
            interpolated[t] = values[-2] + (values[-1] - values[-2]) / (years[-1] - years[-2]) * (t - years[-2])
        else:
            interpolated[t] = np.interp(t, years, values)

    # also include original data points
    for y, v in data.items():
        interpolated[y] = v

    return dict(sorted(interpolated.items()))


def intensity_ammonia_smr_hb(
    target_years: List[int],
    scenarios: Optional[List[str]] = None
) -> Dict[str, Dict[int, Dict[str, float]]]:
    
    if scenarios is None:
        scenarios = SCENARIOS

    base_data = {
        "diesel": {
            2020: [7.80, 7.80, 7.80],
            2030: [7.80, 7.80, 7.73],
            2050: [7.80, 7.80, 7.58],
        },
        "natural_gas": {
            2020: [7.80, 7.80, 7.80],
            2030: [7.80, 7.80, 7.73],
            2050: [7.80, 7.80, 7.58],
        },
        "electricity": {
            2020: [7.80, 7.80, 7.80],
            2030: [7.80, 7.80, 7.73],
            2050: [7.80, 7.80, 7.58],
        },
        "coal": {
            2020: [7.80, 7.80, 7.80],
            2030: [7.80, 7.80, 7.73],
            2050: [7.80, 7.80, 7.58],
        },
        "heat": {
            2020: [7.80, 7.80, 7.80],
            2030: [7.80, 7.80, 7.73],
            2050: [7.80, 7.80, 7.58],
        },
        "biomass": {
            2020: [7.80, 7.80, 7.80],
            2030: [7.80, 7.80, 7.73],
            2050: [7.80, 7.80, 7.58],
        },
        "hydrogen": {
            2020: [7.80, 7.80, 7.80],
            2030: [7.80, 7.80, 7.73],
            2050: [7.80, 7.80, 7.58],
        },
    }

    result = {}

    for fuel, yearly in base_data.items():
        result[fuel] = {}

        # Iterate through scenarios dynamically
        for i, sc in enumerate(scenarios):
            # Build dict {year: value} for each scenario
            year_values = {
                year: vals[i] if i < len(vals) else vals[-1]
                for year, vals in yearly.items()
            }

            # Interpolate or extrapolate to include all target years
            interpolated = interpolate_or_extrapolate(year_values, [2020] + target_years)

            # Merge into final structure
            for year, val in interpolated.items():
                result[fuel].setdefault(year, {})[sc] = val

    return result


def intensity_ammonia_otherconv_hb(
    target_years: List[int],
    scenarios: Optional[List[str]] = None
) -> Dict[str, Dict[int, Dict[str, float]]]:

    if scenarios is None:
        scenarios = SCENARIOS

    base_data = {
        "diesel": {
            2020: [8.97, 8.97, 8.97],
            2030: [8.97, 8.97, 8.89],
            2050: [8.97, 8.97, 8.71],
        },
        "natural_gas": {
            2020: [8.97, 8.97, 8.97],
            2030: [8.97, 8.97, 8.89],
            2050: [8.97, 8.97, 8.71],
        },
        "electricity": {
            2020: [8.97, 8.97, 8.97],
            2030: [8.97, 8.97, 8.89],
            2050: [8.97, 8.97, 8.71],
        },
        "coal": {
            2020: [8.97, 8.97, 8.97],
            2030: [8.97, 8.97, 8.89],
            2050: [8.97, 8.97, 8.71],
        },
        "heat": {
            2020: [8.97, 8.97, 8.97],
            2030: [8.97, 8.97, 8.89],
            2050: [8.97, 8.97, 8.71],
        },
        "biomass": {
            2020: [8.97, 8.97, 8.97],
            2030: [8.97, 8.97, 8.89],
            2050: [8.97, 8.97, 8.71],
        },
        "hydrogen": {
            2020: [8.97, 8.97, 8.97],
            2030: [8.97, 8.97, 8.89],
            2050: [8.97, 8.97, 8.71],
        },
    }

    result = {}

    for fuel, yearly in base_data.items():
        result[fuel] = {}

        for i, sc in enumerate(scenarios):
            # Build per-scenario {year: value}
            year_values = {
                year: vals[i] if i < len(vals) else vals[-1]
                for year, vals in yearly.items()
            }

            # Interpolate or extrapolate to all target years
            interpolated = interpolate_or_extrapolate(year_values, [2020] + target_years)

            # Merge results
            for year, val in interpolated.items():
                result[fuel].setdefault(year, {})[sc] = val

    return result


def intensity_ammonia_renewable(
    target_years: List[int],
    scenarios: Optional[List[str]] = None
) -> Dict[str, Dict[int, Dict[str, float]]]:

    if scenarios is None:
        scenarios = SCENARIOS

    base_data = {
        "diesel": {
            2020: [10.60, 10.60, 10.60],
            2030: [10.60, 10.60, 10.50],
            2050: [10.60, 10.60, 10.30],
        },
        "natural_gas": {
            2020: [10.60, 10.60, 10.60],
            2030: [10.60, 10.60, 10.50],
            2050: [10.60, 10.60, 10.30],
        },
        "electricity": {
            2020: [10.60, 10.60, 10.60],
            2030: [10.60, 10.60, 10.50],
            2050: [10.60, 10.60, 10.30],
        },
        "coal": {
            2020: [10.60, 10.60, 10.60],
            2030: [10.60, 10.60, 10.50],
            2050: [10.60, 10.60, 10.30],
        },
        "heat": {
            2020: [10.60, 10.60, 10.60],
            2030: [10.60, 10.60, 10.50],
            2050: [10.60, 10.60, 10.30],
        },
        "biomass": {
            2020: [10.60, 10.60, 10.60],
            2030: [10.60, 10.60, 10.50],
            2050: [10.60, 10.60, 10.30],
        },
        "hydrogen": {
            2020: [10.60, 10.60, 10.60],
            2030: [10.60, 10.60, 10.50],
            2050: [10.60, 10.60, 10.30],
        },
    }

    result = {}

    for fuel, yearly in base_data.items():
        result[fuel] = {}

        for i, sc in enumerate(scenarios):
            # Build per-scenario dictionary {year: value}
            year_values = {
                year: vals[i] if i < len(vals) else vals[-1]
                for year, vals in yearly.items()
            }

            # Interpolate or extrapolate to include all target years
            interpolated = interpolate_or_extrapolate(year_values, [2020] + target_years)

            # Merge back into final structure
            for year, val in interpolated.items():
                result[fuel].setdefault(year, {})[sc] = val

    return result



def intensity_hvc_naphtha_cracking(
    target_years: List[int],
    scenarios: Optional[List[str]] = None
) -> Dict[str, Dict[int, Dict[str, float]]]:
    """Energy intensities (MWh/t) for Naphtha Cracking.
    Adapts dynamically to scenario names and interpolates/extrapolates for target years.
    """

    if scenarios is None:
        scenarios = SCENARIOS

    base_data = {
        "diesel": {
            2020: [4.92, 4.92, 4.92],
            2030: [4.92, 4.92, 4.92],
            2050: [4.92, 4.92, 4.60],
        },
        "natural_gas": {
            2020: [4.92, 4.92, 4.92],
            2030: [4.92, 4.92, 4.88],
            2050: [4.92, 4.92, 4.78],
        },
        "electricity": {
            2020: [4.92, 4.92, 4.92],
            2030: [4.92, 4.92, 4.92],
            2050: [4.92, 4.92, 4.78],
        },
        "coal": {
            2020: [4.92, 4.92, 4.92],
            2030: [4.92, 4.92, 4.88],
            2050: [4.92, 4.92, 4.78],
        },
        "heat": {
            2020: [4.92, 4.92, 4.92],
            2030: [4.92, 4.92, 4.88],
            2050: [4.92, 4.92, 4.78],
        },
        "biomass": {
            2020: [4.92, 4.92, 4.92],
            2030: [4.92, 4.92, 4.88],
            2050: [4.92, 4.92, 4.78],
        },
        "hydrogen": {
            2020: [4.92, 4.92, 4.92],
            2030: [4.92, 4.92, 4.88],
            2050: [4.92, 4.92, 4.78],
        },
    }

    result = {}

    for fuel, yearly in base_data.items():
        result[fuel] = {}

        for i, sc in enumerate(scenarios):
            # Build per-scenario dictionary {year: value}
            year_values = {
                year: vals[i] if i < len(vals) else vals[-1]
                for year, vals in yearly.items()
            }

            # Interpolate or extrapolate for all target years
            interpolated = interpolate_or_extrapolate(year_values, [2020] + target_years)

            # Merge results into the final structure
            for year, val in interpolated.items():
                result[fuel].setdefault(year, {})[sc] = val

    return result



def intensity_hvc_lpg_cracking(
    target_years: List[int],
    scenarios: Optional[List[str]] = None
) -> Dict[str, Dict[int, Dict[str, float]]]:
    """Energy intensities (MWh/t) for LPG Cracking.
    Adapts dynamically to scenario names and interpolates/extrapolates for target years.
    """

    if scenarios is None:
        scenarios = SCENARIOS

    base_data = {
        "diesel": {
            2020: [5.62, 5.62, 5.62],
            2030: [5.62, 5.62, 5.57],
            2050: [5.62, 5.62, 5.40],
        },
        "natural_gas": {
            2020: [5.62, 5.62, 5.62],
            2030: [5.62, 5.62, 5.57],
            2050: [5.62, 5.57, 5.46],
        },
        "electricity": {
            2020: [5.62, 5.62, 5.62],
            2030: [5.62, 5.62, 5.57],
            2050: [5.62, 5.57, 5.46],
        },
        "coal": {
            2020: [5.62, 5.62, 5.62],
            2030: [5.62, 5.62, 5.57],
            2050: [5.62, 5.57, 5.46],
        },
        "heat": {
            2020: [5.62, 5.62, 5.62],
            2030: [5.62, 5.62, 5.57],
            2050: [5.62, 5.62, 5.46],
        },
        "biomass": {
            2020: [5.62, 5.62, 5.62],
            2030: [5.62, 5.62, 5.57],
            2050: [5.62, 5.62, 5.46],
        },
        "hydrogen": {
            2020: [5.62, 5.62, 5.62],
            2030: [5.62, 5.62, 5.57],
            2050: [5.62, 5.62, 5.46],
        },
    }

    result = {}

    for fuel, yearly in base_data.items():
        result[fuel] = {}

        for i, sc in enumerate(scenarios):
            # Map years to values per scenario
            year_values = {
                year: vals[i] if i < len(vals) else vals[-1]
                for year, vals in yearly.items()
            }

            # Interpolate or extrapolate for all target years
            interpolated = interpolate_or_extrapolate(year_values, [2020] + target_years)

            # Merge into final result
            for year, val in interpolated.items():
                result[fuel].setdefault(year, {})[sc] = val

    return result



def intensity_hvc_methanol_route(
    target_years: List[int],
    scenarios: Optional[List[str]] = None
) -> Dict[str, Dict[int, Dict[str, float]]]:
    """Energy intensities (MWh/t) for Methanol Route.
    Adapts dynamically to scenario names and interpolates/extrapolates for target years.
    """

    if scenarios is None:
        scenarios = SCENARIOS

    base_data = {
        "diesel": {
            2020: [7.80, 7.80, 7.80],
            2030: [7.80, 7.80, 7.73],
            2050: [7.70, 7.80, 7.58],
        },
        "natural_gas": {
            2020: [7.80, 7.80, 7.80],
            2030: [7.80, 7.80, 7.73],
            2050: [7.70, 7.80, 7.58],
        },
        "electricity": {
            2020: [7.80, 7.80, 7.80],
            2030: [7.80, 7.80, 7.73],
            2050: [7.70, 7.80, 7.58],
        },
        "coal": {
            2020: [7.80, 7.80, 7.80],
            2030: [7.80, 7.80, 7.73],
            2050: [7.70, 7.80, 7.58],
        },
        "heat": {
            2020: [7.80, 7.80, 7.80],
            2030: [7.80, 7.80, 7.73],
            2050: [7.70, 7.80, 7.58],
        },
        "biomass": {
            2020: [7.80, 7.80, 7.80],
            2030: [7.80, 7.80, 7.73],
            2050: [7.70, 7.80, 7.58],
        },
        "hydrogen": {
            2020: [7.80, 7.80, 7.80],
            2030: [7.80, 7.80, 7.73],
            2050: [7.70, 7.80, 7.58],
        },
    }

    result = {}

    for fuel, yearly in base_data.items():
        result[fuel] = {}

        for i, sc in enumerate(scenarios):
            # Build per-scenario dictionary {year: value}
            year_values = {
                year: vals[i] if i < len(vals) else vals[-1]
                for year, vals in yearly.items()
            }

            # Interpolate or extrapolate to include all target years
            interpolated = interpolate_or_extrapolate(year_values, [2020] + target_years)

            # Merge into final structure
            for year, val in interpolated.items():
                result[fuel].setdefault(year, {})[sc] = val

    return result


# --- Unspecified Chemicals activity factor (CAGR-based) ---
from industry.scripts.non_metallic_minerals.build_energy_intensities_cement import activity_factor_unspecified_nmm

def activity_factor_unspecified_chemicals(
    base_year: int,
    target_years: List[int],
    scenarios: List[str],
    cagr_cfg: Dict,            # cfg["industry"]["cagr"]["Activity factor of unspecified chemicals"]
    base_value: float = 1.0,
) -> Dict[int, Dict[str, float]]:
    """
    Returns {year:{scenario:value}} with base=1.0 and growth by scenario CAGRs.
    Reuses the proven NMM activity-factor builder for interpolation/extrapolation.
    """
    return activity_factor_unspecified_nmm(
        base_value=base_value,
        base_year=base_year,
        target_years=target_years,
        cagr_cfg=cagr_cfg,
        scenarios=scenarios,
        use_profile=False,
    )
