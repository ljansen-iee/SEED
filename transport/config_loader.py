# transport/config_loader.py
import pandas as pd
from pathlib import Path

import pandas as pd
import numpy as np
from pathlib import Path

def load_transport_config(excel_path: Path, countries: list, scenarios: list):
    """
    Loads the transport configuration Excel and merges country-specific 
    values with defaults, handling empty strings and spaces robustly.
    """
    # Load Excel
    df = pd.read_excel(excel_path)
    # Strip any spaces from column headers (e.g. "Morocco " -> "Morocco")
    df.columns = df.columns.str.strip()

    required_cols = {
        "Assumption Type",
        "Metric Name",
        "Year",
        "Scenario",
        "default"
    }
    
    if not required_cols.issubset(df.columns):
        raise ValueError(f"Excel must contain columns: {required_cols}")

    SCENARIO_ALIAS_MAP = {"sc_a": 0, "sc_b": 1, "sc_c": 2}
    config = {c: {} for c in countries}

    # Helper function to clean text and convert to float safely
    def safe_float(val):
        if pd.isna(val):
            return None
        # Remove spaces
        s_val = str(val).strip()
        # If it's just a space or empty string, treat as None
        if s_val == "" or s_val.lower() == "nan":
            return None
        try:
            return float(s_val)
        except ValueError:
            return None

    for _, row in df.iterrows():
        metric = str(row["Metric Name"]).strip()
        
        try:
            year = int(row["Year"])
        except (ValueError, TypeError):
            continue

        scenario_val_raw = str(row["Scenario"]).strip()
        scenario_val_lower = scenario_val_raw.lower()
        
        # Pre-clean the default value for this row
        default_num = safe_float(row["default"])

        for country in countries:
            # 1. Get and clean the country-specific value
            country_raw = row[country] if country in df.columns else np.nan
            val = safe_float(country_raw)

            # 2. FALLBACK: If country value is empty, use the default value
            if val is None:
                val = default_num

            # 3. If BOTH are empty, skip this entry
            if val is None:
                continue

            # 4. Resolve which scenarios this applies to
            if scenario_val_raw in scenarios:
                target_scenarios = [scenario_val_raw]
            elif scenario_val_lower == "all":
                target_scenarios = scenarios
            elif scenario_val_lower in SCENARIO_ALIAS_MAP:
                idx = SCENARIO_ALIAS_MAP[scenario_val_lower]
                if idx < len(scenarios):
                    target_scenarios = [scenarios[idx]]
                else:
                    continue
            else:
                continue

            # 5. Store in the config dictionary
            for s in target_scenarios:
                if metric not in config[country]:
                    config[country][metric] = {
                        "assumption_type": str(row["Assumption Type"]).strip().upper(),
                        "values": {}
                    }
                
                if year not in config[country][metric]["values"]:
                    config[country][metric]["values"][year] = {}
                
                config[country][metric]["values"][year][s] = val

    return config

def extract_config_data(config, country):

    values = {}
    assumption_types = {}

    for metric, data in config.get(country, {}).items():
        values[metric] = data.get("values", {})
        assumption_types[metric] = data.get("assumption_type", "")

    return values, assumption_types

def get_assumption(config, metric, expected_type):
    entry = config.get(metric)
    if entry is None:
        raise KeyError(f"Metric not found in config: {metric}")

    if entry["assumption_type"] != expected_type:
        raise ValueError(
            f"{metric}: expected {expected_type}, got {entry['assumption_type']}"
        )

    return entry["values"]
