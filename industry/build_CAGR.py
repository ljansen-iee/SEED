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
        # CHANGE: Convert metric name to lowercase right here
        metric = str(row["Metric Name"]).strip().lower() 
        a_type = str(row["Assumption Type"]).strip().upper()
        
        try:
            year = int(row["Year"])
        except:
            continue
            
        for country in countries:
            # CHANGE: Use .get() and .columns to avoid KeyErrors
            if country in df.columns and pd.notna(row[country]):
                val = row[country]
            else:
                val = row.get("default", 0.0) # Safer fallback
                
            if pd.isna(val):
                continue

            scenario_key = str(row["Scenario"]).strip().lower()
            target_indices = []
            
            if scenario_key == "all":
                target_indices = range(len(scenarios))
            elif scenario_key in SCENARIO_INDEX_MAP:
                idx = SCENARIO_INDEX_MAP[scenario_key]
                if idx < len(scenarios): 
                    target_indices = [idx]
            
            # Store in config
            metric_entry = config[country].setdefault(metric, {"assumption_type": a_type, "values": {}})
            for idx in target_indices:
                scenario_name = scenarios[idx]
                metric_entry["values"].setdefault(year, {})[scenario_name] = float(val)
                
    return config

def get_metric_cagr_cfg_from_excel(industry_config, country, metric_name):
    """Bridge for main_industry.py loop"""
    metric_name = str(metric_name).strip().lower()
    return industry_config.get(country, {}).get(metric_name, {}).get("values", {})

def expand_with_cagr_smooth(base_value, cagr_table, base_year, target_years, scenarios):
    # [Keep your base_value extraction code at the top]
    
    result = {}
    max_target = max(target_years)
    config_milestones = sorted([int(k) for k in cagr_table.keys() if str(k).isdigit()])

    for scenario in scenarios:
        current_val = float(base_value)
        
        for y in range(base_year + 1, max_target + 1):
            # STEP LOGIC: Find the rate for the CURRENT period
            # We look for the milestone that governs the current year 'y'
            active_rate = 0.0
            
            # Find the milestone that is greater than or equal to the current year
            # If we are in 2025, we look at the 2030 milestone rate.
            # If we are in 2035, we look at the 2050 milestone rate.
            for m_year in config_milestones:
                if y <= m_year:
                    val = cagr_table.get(m_year, {}).get(scenario)
                    # If the milestone exists but is empty (NaN), use the previous milestone's rate
                    if val is not None and not np.isnan(val):
                        active_rate = val
                        break
            else:
                # Fallback to the very last rate if we are past 2050
                active_rate = cagr_table.get(config_milestones[-1], {}).get(scenario, 0.0)

            # Compound
            current_val = current_val * (1 + active_rate)
            
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