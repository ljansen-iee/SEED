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
    
    IMPORTANT: Methanol is treated as an ENDOGENOUS CARRIER.
    Intensity here reflects methanol feedstock + process energy only.
    Methanol production energy is handled separately in the energy system.
    
    2020 Baseline: ~16 MWh/t HVC total
    - Methanol feedstock: ~11 MWh/t (2.5-3.0 tonnes methanol per tonne olefins)
    - Process electricity: ~4 MWh/t (reaction, separation, compression)
    - Process heat: ~1 MWh/t (natural gas for heat integration)
    
    Source: Engineering estimate based on MTO plant designs
    - Chinese MTO plants: 2.5-3.0 t methanol/t olefins
    - Methanol LHV: ~5.5 MWh/t → 11-16.5 MWh/t feedstock energy
    
    Future: Process efficiency improvements, but methanol requirement stable
    
    TODO: Validate against MTO operator data (Dalian, Jiangsu plants)
    """
    if scenarios is None:
        scenarios = ["BAU", "Progressive", "Optimistic"]
    
    base_data = {
        "methanol": {
            2020: [11.0, 11.0, 11.0],
            2030: [11.0, 11.0, 11.0],
            2050: [11.0, 11.0, 11.0],
        },
        "electricity": {
            2020: [4.0, 4.0, 4.0],
            2030: [4.0, 3.9, 3.8],
            2050: [4.0, 3.8, 3.7],
        },
        "natural_gas": {
            2020: [1.0, 1.0, 1.0],
            2030: [1.0, 0.9, 0.8],
            2050: [1.0, 0.8, 0.7],
        },
        "diesel": {
            2020: [0.0, 0.0, 0.0],
            2030: [0.0, 0.0, 0.0],
            2050: [0.0, 0.0, 0.0],
        },
        "coal": {
            2020: [0.0, 0.0, 0.0],
            2030: [0.0, 0.0, 0.0],
            2050: [0.0, 0.0, 0.0],
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
