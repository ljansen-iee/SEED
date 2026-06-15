# scripts/pulp_paper/build_energy_intensities_pulp.py

import os
import sys
from typing import Dict, List, Optional
from pathlib import Path

from industry.utils.helpers import interpolate_or_extrapolate
from industry.utils.helpers import get_scenarios_from_build_config_industry

SCENARIOS = get_scenarios_from_build_config_industry()


# =====================================================================
# === PRIMARY PULP ENERGY INTENSITIES ===
# =====================================================================

def intensity_primary_pulp(
    target_years: List[int],
    scenarios: Optional[List[str]] = None
) -> Dict[str, Dict[int, Dict[str, float]]]:

    if scenarios is None:
        scenarios = SCENARIOS

    # --- Base anchor data for each fuel (2020, 2030, 2050)
    base_data = {
        "diesel":      {
            2020: [4.08, 4.08, 4.08], 
            2030: [4.08, 4.08, 4.08], 
            2050: [4.08, 4.08, 4.08]},
        "natural_gas": {
            2020: [4.08, 4.08, 4.08], 
            2030: [4.08, 4.08, 4.08], 
            2050: [4.08, 4.08, 4.08]},
        "electricity": {
            2020: [4.08, 4.08, 4.08], 
            2030: [4.08, 4.08, 4.08], 
            2050: [4.08, 4.08, 4.08]},
        "coal":        {
            2020: [4.08, 4.08, 4.08], 
            2030: [4.08, 4.08, 4.08], 
            2050: [4.08, 4.08, 4.08]},
        "heat":        {
            2020: [4.08, 4.08, 4.08], 
            2030: [4.08, 4.08, 4.08], 
            2050: [4.08, 4.08, 4.08]},
        "biomass":     {
            2020: [4.08, 4.08, 4.08], 
            2030: [4.08, 4.08, 4.08], 
            2050: [4.08, 4.08, 4.08]},
        "hydrogen":    {
            2020: [4.08, 4.08, 4.08], 
            2030: [4.08, 4.08, 4.08], 
            2050: [4.08, 4.08, 4.08]},
    }

    result: Dict[str, Dict[int, Dict[str, float]]] = {}

    for fuel, yearly_values in base_data.items():
        per_scenario = {}
        for i, sc in enumerate(scenarios):
            # Build dict per scenario using list index mapping
            sc_dict = {y: vals[i] if i < len(vals) else vals[-1] for y, vals in yearly_values.items()}
            per_scenario[sc] = interpolate_or_extrapolate(sc_dict, [2020] + target_years)

        result[fuel] = {
            y: {sc: per_scenario[sc][y] for sc in scenarios}
            for y in [2020] + target_years
        }

    return result



def intensity_secondary_pulp(
    target_years: List[int],
    scenarios: Optional[List[str]] = None
) -> Dict[str, Dict[int, Dict[str, float]]]:
    
    if scenarios is None:
        scenarios = SCENARIOS

    # --- Base anchor data (2020, 2030, 2050)
    base_data = {
        "diesel":      {
            2020: [4.08, 4.08, 4.08], 
            2030: [4.08, 4.08, 4.08], 
            2050: [4.08, 4.08, 4.08]},
        "natural_gas": {
            2020: [4.08, 4.08, 4.08], 
            2030: [4.08, 4.08, 4.08], 
            2050: [4.08, 4.08, 4.08]},
        "electricity": {
            2020: [4.08, 4.08, 4.08], 
            2030: [4.08, 4.08, 4.08], 
            2050: [4.08, 4.08, 4.08]},
        "coal":        {
            2020: [4.08, 4.08, 4.08], 
            2030: [4.08, 4.08, 4.08], 
            2050: [4.08, 4.08, 4.08]},
        "heat":        {
            2020: [4.08, 4.08, 4.08], 
            2030: [4.08, 4.08, 4.08], 
            2050: [4.08, 4.08, 4.08]},
        "biomass":     {
            2020: [4.08, 4.08, 4.08], 
            2030: [4.08, 4.08, 4.08], 
            2050: [4.08, 4.08, 4.08]},
        "hydrogen":    {
            2020: [4.08, 4.08, 4.08], 
            2030: [4.08, 4.08, 4.08], 
            2050: [4.08, 4.08, 4.08]},
    }

    result: Dict[str, Dict[int, Dict[str, float]]] = {}

    for fuel, yearly_values in base_data.items():
        per_scenario = {}
        for i, sc in enumerate(scenarios):
            sc_dict = {y: vals[i] if i < len(vals) else vals[-1] for y, vals in yearly_values.items()}
            per_scenario[sc] = interpolate_or_extrapolate(sc_dict, [2020] + target_years)

        result[fuel] = {
            y: {sc: per_scenario[sc][y] for sc in scenarios}
            for y in [2020] + target_years
        }

    return result


def intensity_paper_production(
    target_years: List[int],
    scenarios: Optional[List[str]] = None,
) -> Dict[str, Dict[int, Dict[str, float]]]:
    
    if scenarios is None:
        scenarios = SCENARIOS

    base_data = {
        "diesel": {
            2020: [2.60, 2.60, 2.60],
            2030: [2.60, 2.60, 2.60],
            2050: [2.60, 2.60, 2.60],
        },
        "natural_gas": {
            2020: [2.60, 2.60, 2.60],
            2030: [2.60, 2.60, 2.60],
            2050: [2.60, 2.60, 2.60],
        },
        "electricity": {
            2020: [2.60, 2.60, 2.60],
            2030: [2.60, 2.60, 2.60],
            2050: [2.60, 2.60, 2.60],
        },
        "coal": {
            2020: [2.60, 2.60, 2.60],
            2030: [2.55, 2.55, 2.55],
            2050: [2.45, 2.45, 2.45],
        },
        "heat": {
            2020: [2.60, 2.60, 2.60],
            2030: [2.60, 2.60, 2.60],
            2050: [2.60, 2.60, 2.60],
        },
        "biomass": {
            2020: [2.60, 2.60, 2.60],
            2030: [2.60, 2.60, 2.60],
            2050: [2.60, 2.60, 2.60],
        },
        "hydrogen": {
            2020: [2.60, 2.60, 2.60],
            2030: [2.60, 2.60, 2.60],
            2050: [2.60, 2.60, 2.60],
        },
    }

    result: Dict[str, Dict[int, Dict[str, float]]] = {}

    for fuel, yearly_values in base_data.items():
        per_scenario: Dict[str, Dict[int, float]] = {}

        for i, sc in enumerate(scenarios):
            sc_dict = {year: vals[i] for year, vals in yearly_values.items()}
            per_scenario[sc] = interpolate_or_extrapolate(sc_dict, [2020] + target_years)

        # fuel → year → scenario
        result[fuel] = {
            year: {sc: per_scenario[sc][year] for sc in scenarios}
            for year in [2020] + target_years
        }

    return result