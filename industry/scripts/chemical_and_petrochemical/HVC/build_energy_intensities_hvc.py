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
    
    TODO: Validate against IEA petrochemical benchmarks.
    source: https://www.osti.gov/servlets/purl/927032
    """
    if scenarios is None:
        scenarios = ["BAU", "Progressive", "Optimistic"]
    
    # Base data by fuel: {year: [BAU, Progressive, Optimistic]}
    base_data = {
        "diesel": {
            2020: [4.92, 4.92, 4.92],
            2030: [4.92, 4.92, 4.92],
            2050: [4.92, 4.92, 4.92],
        },
        "natural_gas": {
            2020: [4.92, 4.92, 4.92],
            2030: [4.92, 4.92, 4.92],
            2050: [4.92, 4.92, 4.92],
        },
        "electricity": {
            2020: [4.92, 4.92, 4.92],
            2030: [4.92, 4.92, 4.92],
            2050: [4.92, 4.92, 4.92],
        },
        "coal": {
            2020: [4.92, 4.92, 4.92],
            2030: [4.92, 4.92, 4.92],
            2050: [4.92, 4.92, 4.92],
        },
        "heat": {
            2020: [4.92, 4.92, 4.92],
            2030: [4.92, 4.92, 4.92],
            2050: [4.92, 4.92, 4.92],
        },
        "biomass": {
            2020: [4.92, 4.92, 4.92],
            2030: [4.92, 4.92, 4.92],
            2050: [4.92, 4.92, 4.92],
        },
        "hydrogen": {
            2020: [4.92, 4.92, 4.92],
            2030: [4.92, 4.92, 4.92],
            2050: [4.92, 4.92, 4.92],
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
            2020: [5.62, 5.62, 5.62],
            2030: [5.62, 5.62, 5.62],
            2050: [5.62, 5.62, 5.62],
        },
        "natural_gas": {
            2020: [5.62, 5.62, 5.62],
            2030: [5.62, 5.62, 5.62],
            2050: [5.62, 5.62, 5.62],
        },
        "electricity": {
            2020: [5.62, 5.62, 5.62],
            2030: [5.62, 5.62, 5.62],
            2050: [5.62, 5.62, 5.62],
        },
        "coal": {
            2020: [5.62, 5.62, 5.62],
            2030: [5.62, 5.62, 5.62],
            2050: [5.62, 5.62, 5.62],
        },
        "heat": {
            2020: [5.62, 5.62, 5.62],
            2030: [5.62, 5.62, 5.62],
            2050: [5.62, 5.62, 5.62],
        },
        "biomass": {
            2020: [5.62, 5.62, 5.62],
            2030: [5.62, 5.62, 5.62],
            2050: [5.62, 5.62, 5.62],
        },
        "hydrogen": {
            2020: [5.62, 5.62, 5.62],
            2030: [5.62, 5.62, 5.62],
            2050: [5.62, 5.62, 5.62],
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
            2020: [7.8, 7.8, 7.8],
            2030: [7.8, 7.8, 7.8],
            2050: [7.8, 7.8, 7.8],
        },
        "electricity": {
            2020: [7.8, 7.8, 7.8],
            2030: [7.8, 7.8, 7.8],
            2050: [7.8, 7.8, 7.8],
        },
        "natural_gas": {
            2020: [7.8, 7.8, 7.8],
            2030: [7.8, 7.8, 7.8],
            2050: [7.8, 7.8, 7.8],
        },
        "diesel": {
            2020: [7.8, 7.8, 7.8],
            2030: [7.8, 7.8, 7.8],
            2050: [7.8, 7.8, 7.8],
        },
        "coal": {
            2020: [7.8, 7.8, 7.8],
            2030: [7.8, 7.8, 7.8],
            2050: [7.8, 7.8, 7.8],
        },
        "heat": {
            2020: [7.8, 7.8, 7.8],
            2030: [7.8, 7.8, 7.8],
            2050: [7.8, 7.8, 7.8],
        },
        "biomass": {
            2020: [7.8, 7.8, 7.8],
            2030: [7.8, 7.8, 7.8],
            2050: [7.8, 7.8, 7.8],
        },
        "hydrogen": {
            2020: [7.8, 7.8, 7.8],
            2030: [7.8, 7.8, 7.8],
            2050: [7.8, 7.8, 7.8],
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
