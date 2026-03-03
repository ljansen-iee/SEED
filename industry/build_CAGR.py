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


def _normalize_metric_name(metric_name: str) -> str:
    name = str(metric_name).strip().lower()
    return (
        name
        .replace("furncace", "furnace")
        .replace("furnaces + basic oxygen furnace", "furnace + basic oxygen furnace")
    )


def _parse_numeric_cell(value):
    if pd.isna(value):
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def load_industry_config(excel_path: Path, countries: list, scenarios: list):
    if not excel_path.exists():
        raise FileNotFoundError(f"Could not find config at {excel_path}")
    
    # Use read_csv if it's a .csv, otherwise read_excel
    if excel_path.suffix.lower() == '.csv':
        df = pd.read_csv(excel_path)
    else:
        df = pd.read_excel(excel_path)
        
    df.columns = df.columns.str.strip()
    config = {c: {} for c in countries}

    # === DUAL FORMAT HANDLING ===
    # If "Year" is a column, it's the NEW "Long" format.
    # If "Year" is NOT a column, we assume the old "Wide" format where headers were years.
    if "Year" not in df.columns:
        # PIVOT: Convert Wide (Year headers) to Long (Year column)
        # This makes the rest of the loop work for both versions
        non_year_cols = [c for c in df.columns if not str(c).isdigit()]
        year_cols = [c for c in df.columns if str(c).isdigit()]
        df = df.melt(id_vars=non_year_cols, value_vars=year_cols, 
                    var_name="Year", value_name="value")
        # In this old format, 'value' contains the data, so we map it to 'default'
        # so the country-check logic below still works.
        df["default"] = df["value"]

    # === PROCESSING LOOP ===
    for _, row in df.iterrows():
        metric = _normalize_metric_name(row["Metric Name"])
        a_type = str(row["Assumption Type"]).strip().upper()
        
        try:
            year = int(row["Year"])
        except:
            continue
            
        for country in countries:
            country_val = _parse_numeric_cell(row[country]) if country in df.columns else None
            default_val = _parse_numeric_cell(row.get("default", None))

            if country_val is not None:
                val = country_val
            elif default_val is not None:
                val = default_val
            else:
                continue

            scenario_key = str(row["Scenario"]).strip().lower()
            target_indices = []
            
            # Map "all" to every scenario, or specific ones via SCENARIO_INDEX_MAP
            if scenario_key == "all":
                target_indices = range(len(scenarios))
            elif scenario_key in SCENARIO_INDEX_MAP:
                idx = SCENARIO_INDEX_MAP[scenario_key]
                if idx < len(scenarios): 
                    target_indices = [idx]
            
            # Populate the nested dictionary
            metric_entry = config[country].setdefault(metric, {"assumption_type": a_type, "values": {}})
            for idx in target_indices:
                scenario_name = scenarios[idx]
                metric_entry["values"].setdefault(year, {})[scenario_name] = val
                
    return config

def get_metric_cagr_cfg_from_excel(industry_config, country, metric_name):
    """Bridge for main_industry.py loop"""
    metric_name = _normalize_metric_name(metric_name)
    return industry_config.get(country, {}).get(metric_name, {}).get("values", {})


def get_metric_config_entry_from_excel(industry_config, country, metric_name):
    """Return full metric config entry (assumption_type + values)."""
    metric_name = _normalize_metric_name(metric_name)
    return industry_config.get(country, {}).get(metric_name, {})

def expand_with_cagr_smooth(base_value, cagr_table, base_year, target_years, scenarios):
    result = {}
    max_target = max(target_years)
    
    # Identify milestone years from the dict keys
    config_milestones = sorted([int(k) for k in cagr_table.keys() if str(k).isdigit()])
    
    # --- SAFETY CHECK ---
    # If no CAGR milestones found for this country/metric, keep the value flat
    if not config_milestones:
        for scenario in scenarios:
            for y in target_years:
                result[f"{y}_{scenario}"] = float(base_value)
        return result

    for scenario in scenarios:
        current_val = float(base_value)
        
        for y in range(base_year + 1, max_target + 1):
            active_rate = 0.0
            
            # Find the rate for the current year period
            for m_year in config_milestones:
                if y <= m_year:
                    val = cagr_table.get(m_year, {}).get(scenario)
                    # Check if value exists and is not NaN
                    if val is not None and not pd.isna(val):
                        active_rate = float(val)
                        break
            else:
                # If we are past the last milestone year, use the last available rate
                last_year = config_milestones[-1]
                active_rate = float(cagr_table.get(last_year, {}).get(scenario, 0.0))

            # Apply Compounding: New Value = Old Value * (1 + rate)
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