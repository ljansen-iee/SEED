import pandas as pd
from pathlib import Path

def load_transport_config(excel_path: Path, countries: list, scenarios: list):
    """
    Loads transport configuration from Excel using STRICT INDEX MAPPING.
    
    Excel Alias -> Python List Index
    sc_a        -> scenarios[0] (e.g. Baseline)
    sc_b        -> scenarios[1] (e.g. Reference/RF)
    sc_c        -> scenarios[2] (e.g. NetZero/EL)
    """
    
    df = pd.read_excel(excel_path)
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

    # STRICT INDEX MAP
    # This maps the Excel scenario code to the position in your 'scenarios' list.
    SCENARIO_INDEX_MAP = {
        "sc_a": 0,  # First item
        "sc_b": 1,  # Second item
        "sc_c": 2   # Third item
    }

    config = {c: {} for c in countries}

    for _, row in df.iterrows():
        metric = str(row["Metric Name"]).strip()

        try:
            year = int(row["Year"])
        except Exception:
            continue

        scenario_val = str(row["Scenario"]).strip()
        scenario_val_lower = scenario_val.lower()
        default_val = row["default"]

        for country in countries:
            # 1. GET VALUE (Country specific > Default > Skip)
            if country in df.columns and pd.notna(row[country]):
                val = float(row[country])
            elif pd.notna(default_val):
                val = float(default_val)
            else:
                continue

            # 2. RESOLVE SCENARIO BY INDEX
            target_scenarios = []

            # CASE A: "All" keyword (Applies to everything)
            if scenario_val_lower == "all":
                target_scenarios = scenarios

            # CASE B: Map sc_a/sc_b/sc_c to list indices 0/1/2
            elif scenario_val_lower in SCENARIO_INDEX_MAP:
                idx = SCENARIO_INDEX_MAP[scenario_val_lower]
                
                # Check if the list provided is long enough
                if idx < len(scenarios):
                    target_scenarios = [scenarios[idx]]
                else:
                    # Optional: Print warning if user provided a list that is too short 
                    # (e.g. provided 1 item but Excel asks for index 2)
                    pass 

            # CASE C: Fallback - Exact Name Match (if Excel contains "Baseline" directly)
            elif scenario_val in scenarios:
                target_scenarios = [scenario_val]

            # 3. APPLY VALUE
            for s in target_scenarios:
                entry = config[country].setdefault(
                    metric,
                    {
                        "assumption_type": str(row["Assumption Type"]).strip().upper(),
                        "values": {}
                    }
                )
                entry["values"].setdefault(year, {})[s] = val

    return config


def get_assumption(config, metric, expected_type):
    entry = config.get(metric)
    if entry is None:
        raise KeyError(f"Metric not found in config: {metric}")

    if entry["assumption_type"] != expected_type:
        raise ValueError(
            f"{metric}: expected {expected_type}, got {entry['assumption_type']}"
        )

    return entry["values"]