#build_CAGR.py

import pandas as pd
from pathlib import Path
import numpy as np
import os
from typing import Dict, List
from scipy.interpolate import interp1d

# --- STRICT SCENARIO MAPPING ---
SCENARIO_INDEX_MAP = {
    "sc_a": 0,  # Baseline
    "sc_b": 1,  # Ambitious Policies
    "sc_c": 2   # Net Zero
}

def load_industry_config(excel_path: Path, countries: list, scenarios: list):
    if not excel_path.exists():
        raise FileNotFoundError(f"Could not find config at {excel_path}")
    df = pd.read_excel(excel_path)
    df.columns = df.columns.str.strip()
    config = {c: {} for c in countries}
    for _, row in df.iterrows():
        metric = str(row["Metric Name"]).strip()
        a_type = str(row["Assumption Type"]).strip().upper()
        try:
            year = int(row["Year"])
        except:
            continue
        for country in countries:
            val = row[country] if (country in df.columns and pd.notna(row[country])) else row["default"]
            if pd.isna(val): continue
            scenario_key = str(row["Scenario"]).strip().lower()
            target_indices = []
            if scenario_key == "all":
                target_indices = range(len(scenarios))
            elif scenario_key in SCENARIO_INDEX_MAP:
                idx = SCENARIO_INDEX_MAP[scenario_key]
                if idx < len(scenarios): target_indices = [idx]
            metric_entry = config[country].setdefault(metric, {"assumption_type": a_type, "values": {}})
            for idx in target_indices:
                scenario_name = scenarios[idx]
                metric_entry["values"].setdefault(year, {})[scenario_name] = float(val)
    return config

def get_metric_cagr_cfg_from_excel(industry_config, country, metric_name):
    """Bridge for main_industry.py loop"""
    return industry_config.get(country, {}).get(metric_name, {}).get("values", {})

def expand_with_cagr_smooth(base_value, cagr_table, base_year, target_years, scenarios):
    """
    Calculates future values for ALL scenarios using smooth sliding growth rates.
    This replaces the piecewise function to ensure the 'Very Smooth' transition.
    """
    if isinstance(base_value, (list, tuple, dict)):
        # Extract the first available number
        if isinstance(base_value, dict):
            base_value = list(base_value.values())[0]
        else:
            base_value = base_value[0]

    if base_value is None or (isinstance(base_value, float) and np.isnan(base_value)):
        return {f"{y}_{sc}": 0.0 for y in target_years for sc in scenarios}
    
    # Identify the milestones (2030, 2050)
    config_milestones = sorted([int(k) for k in cagr_table.keys() if str(k).isdigit()])
    
    # If no CAGR data in Excel, keep base value constant
    if not config_milestones:
        return {f"{y}_{sc}": float(base_value) for y in target_years for sc in scenarios}

    result = {}
    mile_years = [base_year] + config_milestones
    max_target = max(target_years)

    for scenario in scenarios:
        # Get rates for this scenario at each milestone
        # Use the first available milestone rate as the 'starting rate' at base_year
        first_rate = cagr_table.get(config_milestones[0], {}).get(scenario, 0.0)
        mile_rates = [first_rate] + [cagr_table.get(m, {}).get(scenario, 0.0) for m in config_milestones]
        
        current_val = float(base_value)
        
        # Calculate every single year to allow the rate to 'slide' (Interpolate)
        for y in range(base_year + 1, max_target + 1):
            # Interpolate the growth rate for this specific year
            annual_rate = np.interp(y, mile_years, mile_rates)
            
            # Compound the value
            current_val = current_val * (1 + annual_rate)
            
            # If this is a report year, save it
            if y in target_years:
                result[f"{y}_{scenario}"] = current_val
                
    return result

def interpolate_or_extrapolate(values, target_years):
    known_years = sorted([y for y, v in values.items() if v is not None])
    if not known_years: return {y: 0.0 for y in target_years}
    known_vals = [values[y] for y in known_years]
    if len(known_years) < 2: return {y: known_vals[0] for y in target_years}
    f = interp1d(known_years, known_vals, fill_value="extrapolate")
    return {y: float(f(y)) for y in target_years}

def load_yaml_config(path): return {}
def export_metric_template_to_yaml(*args, **kwargs): pass
def load_and_merge_yaml(*args, **kwargs): return {}, {}, {}