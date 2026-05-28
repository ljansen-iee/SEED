"""
HVC fuel share functions.

Provides fuel share data for High-Value Chemicals (HVC) production routes:
- Naphtha cracking (steam cracking of naphtha → ethylene, propylene, butadiene)
- LPG cracking (liquefied petroleum gas cracking)
- Methanol-to-Olefins (MTO - can use green methanol in future)

Fuel shares represent the percentage of total energy consumed by each fuel type
for a given production route. All values are expert assumptions based on typical
industry process configurations.

TODO: Validate baseline (2020) values against:
- IEA Energy Technology Perspectives (petrochemical sector)
- Industry benchmarks from petrochemical associations
- Process engineering handbooks

Interpolation: Linear between anchor years (2020, 2030, 2050)
Normalization: Renormalized to sum to 100% per (year, scenario)
"""

from typing import List, Dict, Optional
from industry.build_CAGR import interpolate_or_extrapolate

SCENARIOS = ["BAU", "Progressive", "Optimistic"]


def _interpolate_shares(
    base_data: Dict,
    target_years: List[int],
    scenarios: List[str]
) -> Dict[str, Dict[int, Dict[str, float]]]:
    """
    Interpolate and normalize fuel shares across scenarios and years.
    
    Args:
        base_data: Dict of {fuel: {year: [BAU, Progressive, Optimistic]}}
        target_years: Years to interpolate to
        scenarios: Scenario names
    
    Returns:
        Dict of {fuel: {year: {scenario: share%}}}
    """
    def _clamp01(x: float) -> float:
        return max(0.0, min(100.0, float(x)))
    
    result: Dict[str, Dict[int, Dict[str, float]]] = {}
    
    # 1) Interpolate and clamp
    for fuel, yearly in base_data.items():
        result[fuel] = {}
        for i, sc in enumerate(scenarios):
            # Per-scenario series from anchors
            sc_dict = {int(y): (vals[i] if i < len(vals) else vals[-1])
                       for y, vals in yearly.items()}
            
            # Include both anchor years and target_years
            years_all = sorted(set(list(sc_dict.keys()) + target_years))
            
            interpolated = interpolate_or_extrapolate(sc_dict, years_all)
            
            for year, val in interpolated.items():
                result[fuel].setdefault(year, {})[sc] = _clamp01(val)
    
    # 2) Renormalize so shares sum to 100 per (year, scenario)
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
# === NAPHTHA CRACKING (Steam Cracking)
# =====================================================================

def share_fuel_hvc_naphtha(target_years: List[int], scenarios: Optional[List[str]] = None):
    """
    Fuel shares for naphtha steam cracking (% of naphtha cracking energy).
    
    2020 Baseline Source: Expert assumption based on typical steam cracker configuration
    - Natural gas: 65% (steam generation, furnace heating)
    - Electricity: 30% (compressors, refrigeration, separation)
    - Diesel: 3% (backup/startup)
    - Biomass/Hydrogen: 0% initially, introduced in decarbonization scenarios
    
    Decarbonization pathway:
    - Progressive: Some electrification + heat recovery
    - Optimistic: Major electrification + green hydrogen for high-temp heat
    
    TODO: Validate against IEA petrochemical benchmarks
    """
    if scenarios is None:
        scenarios = SCENARIOS
    
    base_data = {
        "diesel": {
            2020: [3, 3, 3],
            2030: [3, 2, 0],
            2050: [3, 0, 0]
        },
        "natural_gas": {
            2020: [65, 65, 65],
            2030: [65, 55, 45],
            2050: [65, 40, 20]
        },
        "electricity": {
            2020: [30, 30, 30],
            2030: [30, 38, 45],
            2050: [30, 45, 55]
        },
        "coal": {
            2020: [2, 2, 2],
            2030: [2, 0, 0],
            2050: [0, 0, 0]
        },
        "heat": {
            2020: [0, 0, 0],
            2030: [0, 0, 0],
            2050: [0, 0, 0]
        },
        "biomass": {
            2020: [0, 0, 0],
            2030: [0, 5, 5],
            2050: [0, 10, 10]
        },
        "hydrogen": {
            2020: [0, 0, 0],
            2030: [0, 0, 5],
            2050: [0, 5, 15]
        },
    }
    
    return _interpolate_shares(base_data, target_years, scenarios)


# =====================================================================
# === LPG CRACKING
# =====================================================================

def share_fuel_hvc_lpg(target_years: List[int], scenarios: Optional[List[str]] = None):
    """
    Fuel shares for LPG cracking (% of LPG cracking energy).
    
    2020 Baseline Source: Expert assumption
    - LPG cracking requires less energy than naphtha (lighter feedstock)
    - Higher electricity share for separation/refrigeration
    - Natural gas: 55% (lower furnace demand)
    - Electricity: 40% (higher refrigeration/compression)
    
    TODO: Validate against process engineering data
    """
    if scenarios is None:
        scenarios = SCENARIOS
    
    base_data = {
        "diesel": {
            2020: [3, 3, 3],
            2030: [3, 2, 0],
            2050: [3, 0, 0]
        },
        "natural_gas": {
            2020: [55, 55, 55],
            2030: [55, 45, 35],
            2050: [55, 30, 15]
        },
        "electricity": {
            2020: [40, 40, 40],
            2030: [40, 48, 55],
            2050: [40, 55, 65]
        },
        "coal": {
            2020: [2, 2, 2],
            2030: [2, 0, 0],
            2050: [0, 0, 0]
        },
        "heat": {
            2020: [0, 0, 0],
            2030: [0, 0, 0],
            2050: [0, 0, 0]
        },
        "biomass": {
            2020: [0, 0, 0],
            2030: [0, 5, 5],
            2050: [0, 10, 10]
        },
        "hydrogen": {
            2020: [0, 0, 0],
            2030: [0, 0, 5],
            2050: [0, 5, 10]
        },
    }
    
    return _interpolate_shares(base_data, target_years, scenarios)


# =====================================================================
# === METHANOL-TO-OLEFINS (MTO)
# =====================================================================

def share_fuel_hvc_mto(target_years: List[int], scenarios: Optional[List[str]] = None):
    """
    Fuel shares for Methanol-to-Olefins (MTO) route (% of MTO energy).
    
    2020 Baseline Source: Expert assumption
    - MTO is more electricity-intensive than cracking
    - Electricity: 60% (reaction, separation)
    - Natural gas: 35% (heat integration)
    
    Future potential: Green methanol from H2 + CO2 capture
    - Optimistic scenario: High electrification + green methanol feedstock
    
    TODO: Validate against MTO plant operation data
    """
    if scenarios is None:
        scenarios = SCENARIOS
    
    base_data = {
        "diesel": {
            2020: [2, 2, 2],
            2030: [2, 1, 0],
            2050: [2, 0, 0]
        },
        "natural_gas": {
            2020: [35, 35, 35],
            2030: [35, 30, 20],
            2050: [35, 20, 10]
        },
        "electricity": {
            2020: [60, 60, 60],
            2030: [60, 64, 70],
            2050: [60, 70, 80]
        },
        "coal": {
            2020: [3, 3, 3],
            2030: [3, 0, 0],
            2050: [0, 0, 0]
        },
        "heat": {
            2020: [0, 0, 0],
            2030: [0, 0, 0],
            2050: [0, 0, 0]
        },
        "biomass": {
            2020: [0, 0, 0],
            2030: [0, 5, 5],
            2050: [0, 5, 5]
        },
        "hydrogen": {
            2020: [0, 0, 0],
            2030: [0, 0, 5],
            2050: [0, 5, 5]
        },
    }
    
    return _interpolate_shares(base_data, target_years, scenarios)
