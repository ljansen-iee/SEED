"""
HVC energy intensity functions.

Provides energy intensity data (MWh/tonne HVC) for each production route.
Energy intensity = total energy consumed per tonne of HVC produced.

Routes:
- Naphtha cracking: Steam cracking of naphtha feedstock
- LPG cracking: Liquefied petroleum gas cracking
- Methanol-to-Olefins (MTO): Methanol conversion to olefins

Energy intensities are based on engineering estimates from industry benchmarks.
Values represent TOTAL energy (thermal + electrical) per tonne of HVC output.

TODO: Validate against:
- IEA Energy Technology Perspectives (petrochemical sector tables)
- Industry benchmarks (ICIS, IHS Markit)
- Academic literature on petrochemical processes

NOTE: HVC = High-Value Chemicals (ethylene + propylene + butadiene + aromatics)
      Typical yield: ethylene ~55%, propylene ~30%, other ~15%
"""

from typing import Dict, List
import numpy as np


def interpolate_or_extrapolate(data: Dict[int, float], target_years: List[int]) -> Dict[int, float]:
    """
    Interpolate or extrapolate values for given target years.
    """
    years = sorted(data.keys())
    values = [data[y] for y in years]
    
    interpolated = {}
    for t in target_years:
        if t <= years[0]:
            interpolated[t] = values[0] + (values[1] - values[0]) / (years[1] - years[0]) * (t - years[0])
        elif t >= years[-1]:
            interpolated[t] = values[-2] + (values[-1] - values[-2]) / (years[-1] - years[-2]) * (t - years[-2])
        else:
            interpolated[t] = np.interp(t, years, values)
    
    # Include original data points
    for y, v in data.items():
        interpolated[y] = v
    
    return dict(sorted(interpolated.items()))


def intensity_hvc_naphtha(
    target_years: List[int],
    scenarios: List[str] = None
) -> Dict[str, Dict[int, Dict[str, float]]]:
    """
    Energy intensity for naphtha steam cracking (MWh/tonne HVC).
    
    2020 Baseline: 12-15 MWh/t HVC (industry typical)
    - Steam generation: ~40% of energy
    - Furnace cracking: ~35% of energy  
    - Compression/separation: ~25% of energy
    
    Source: Engineering estimate based on typical steam cracker energy balance
    - Modern crackers: 12-13 GJ/t ethylene ≈ 3.3-3.6 MWh/t ethylene
    - Scaled to HVC mix (ethylene 55%): 3.3/0.55 ≈ 6 MWh/t HVC for electricity
    - Total (thermal + electrical): ~14 MWh/t HVC
    
    Efficiency improvements (Optimistic scenario):
    - Heat recovery: -0.5 MWh/t
    - Process optimization: -0.5 MWh/t
    - By 2050: ~13 MWh/t HVC
    
    TODO: Validate against IEA petrochemical benchmarks
    """
    if scenarios is None:
        scenarios = ["BAU", "Progressive", "Optimistic"]
    
    # Base data by fuel: {year: [BAU, Progressive, Optimistic]}
    base_data = {
        "diesel": {
            2020: [0.42, 0.42, 0.42],
            2030: [0.42, 0.42, 0.41],
            2050: [0.42, 0.42, 0.39],
        },
        "natural_gas": {
            2020: [9.1, 9.1, 9.1],
            2030: [9.1, 9.1, 8.9],
            2050: [9.1, 9.1, 8.6],
        },
        "electricity": {
            2020: [4.2, 4.2, 4.2],
            2030: [4.2, 4.2, 4.1],
            2050: [4.2, 4.2, 4.0],
        },
        "coal": {
            2020: [0.28, 0.28, 0.28],
            2030: [0.28, 0.28, 0.27],
            2050: [0.28, 0.28, 0.26],
        },
        "heat": {
            2020: [0.0, 0.0, 0.0],
            2030: [0.0, 0.0, 0.0],
            2050: [0.0, 0.0, 0.0],
        },
        "biomass": {
            2020: [0.0, 0.0, 0.0],
            2030: [0.0, 0.0, 0.0],
            2050: [0.0, 0.0, 0.0],
        },
        "hydrogen": {
            2020: [0.0, 0.0, 0.0],
            2030: [0.0, 0.0, 0.0],
            2050: [0.0, 0.0, 0.0],
        },
    }
    
    # Interpolate and build result structure
    result = {}
    for fuel, yearly_data in base_data.items():
        result[fuel] = {}
        for scenario_idx, scenario in enumerate(scenarios):
            # Build series for this scenario
            series = {year: vals[scenario_idx] for year, vals in yearly_data.items()}
            interpolated = interpolate_or_extrapolate(series, target_years)
            
            # Store as {fuel: {year: {scenario: value}}}
            for year, value in interpolated.items():
                if year not in result[fuel]:
                    result[fuel][year] = {}
                result[fuel][year][scenario] = value
    
    return result


def intensity_hvc_lpg(
    target_years: List[int],
    scenarios: List[str] = None
) -> Dict[str, Dict[int, Dict[str, float]]]:
    """
    Energy intensity for LPG cracking (MWh/tonne HVC).
    
    2020 Baseline: 10-12 MWh/t HVC (lighter feedstock = lower energy)
    - LPG requires less cracking severity than naphtha
    - Lower furnace temperature needed
    - Higher yield per unit feedstock
    
    Source: Engineering estimate
    - Typical: 10-11 GJ/t ethylene ≈ 2.8-3.0 MWh/t ethylene
    - Scaled to HVC mix: ~11 MWh/t HVC total
    
    TODO: Validate against process engineering literature
    """
    if scenarios is None:
        scenarios = ["BAU", "Progressive", "Optimistic"]
    
    base_data = {
        "diesel": {
            2020: [0.33, 0.33, 0.33],
            2030: [0.33, 0.33, 0.32],
            2050: [0.33, 0.33, 0.31],
        },
        "natural_gas": {
            2020: [6.05, 6.05, 6.05],
            2030: [6.05, 6.05, 5.95],
            2050: [6.05, 6.05, 5.75],
        },
        "electricity": {
            2020: [4.4, 4.4, 4.4],
            2030: [4.4, 4.4, 4.3],
            2050: [4.4, 4.4, 4.2],
        },
        "coal": {
            2020: [0.22, 0.22, 0.22],
            2030: [0.22, 0.22, 0.21],
            2050: [0.22, 0.22, 0.20],
        },
        "heat": {
            2020: [0.0, 0.0, 0.0],
            2030: [0.0, 0.0, 0.0],
            2050: [0.0, 0.0, 0.0],
        },
        "biomass": {
            2020: [0.0, 0.0, 0.0],
            2030: [0.0, 0.0, 0.0],
            2050: [0.0, 0.0, 0.0],
        },
        "hydrogen": {
            2020: [0.0, 0.0, 0.0],
            2030: [0.0, 0.0, 0.0],
            2050: [0.0, 0.0, 0.0],
        },
    }
    
    result = {}
    for fuel, yearly_data in base_data.items():
        result[fuel] = {}
        for scenario_idx, scenario in enumerate(scenarios):
            series = {year: vals[scenario_idx] for year, vals in yearly_data.items()}
            interpolated = interpolate_or_extrapolate(series, target_years)
            
            for year, value in interpolated.items():
                if year not in result[fuel]:
                    result[fuel][year] = {}
                result[fuel][year][scenario] = value
    
    return result


def intensity_hvc_mto(
    target_years: List[int],
    scenarios: List[str] = None
) -> Dict[str, Dict[int, Dict[str, float]]]:
    """
    Energy intensity for Methanol-to-Olefins (MTO) route (MWh/tonne HVC).
    
    2020 Baseline: 15-18 MWh/t HVC (most energy-intensive route)
    - MTO reactor: Higher energy requirement than cracking
    - Methanol synthesis energy embedded (if not green methanol)
    - More complex separation process
    
    Source: Engineering estimate based on MTO plant designs
    - Chinese MTO plants: ~16-18 MWh/t olefins
    
    Future: Green methanol could reduce carbon intensity but not necessarily
            energy intensity (electrolysis + synthesis energy)
    
    TODO: Validate against MTO operator data (Dalian, Jiangsu plants)
    """
    if scenarios is None:
        scenarios = ["BAU", "Progressive", "Optimistic"]
    
    base_data = {
        "diesel": {
            2020: [0.32, 0.32, 0.32],
            2030: [0.32, 0.32, 0.31],
            2050: [0.32, 0.32, 0.29],
        },
        "natural_gas": {
            2020: [5.6, 5.6, 5.6],
            2030: [5.6, 5.6, 5.45],
            2050: [5.6, 5.6, 5.15],
        },
        "electricity": {
            2020: [9.6, 9.6, 9.6],
            2030: [9.6, 9.6, 9.35],
            2050: [9.6, 9.6, 8.85],
        },
        "coal": {
            2020: [0.48, 0.48, 0.48],
            2030: [0.48, 0.48, 0.47],
            2050: [0.48, 0.48, 0.44],
        },
        "heat": {
            2020: [0.0, 0.0, 0.0],
            2030: [0.0, 0.0, 0.0],
            2050: [0.0, 0.0, 0.0],
        },
        "biomass": {
            2020: [0.0, 0.0, 0.0],
            2030: [0.0, 0.0, 0.0],
            2050: [0.0, 0.0, 0.0],
        },
        "hydrogen": {
            2020: [0.0, 0.0, 0.0],
            2030: [0.0, 0.0, 0.0],
            2050: [0.0, 0.0, 0.0],
        },
    }
    
    result = {}
    for fuel, yearly_data in base_data.items():
        result[fuel] = {}
        for scenario_idx, scenario in enumerate(scenarios):
            series = {year: vals[scenario_idx] for year, vals in yearly_data.items()}
            interpolated = interpolate_or_extrapolate(series, target_years)
            
            for year, value in interpolated.items():
                if year not in result[fuel]:
                    result[fuel][year] = {}
                result[fuel][year][scenario] = value
    
    return result
