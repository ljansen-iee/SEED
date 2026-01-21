# transport/config_loader.py
import pandas as pd
from pathlib import Path

def load_transport_config(excel_path: Path, countries: list, scenarios: list):

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

    SCENARIO_ALIAS_MAP = {"sc_a": 0, "sc_b": 1, "sc_c": 2}

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
            if country in df.columns and pd.notna(row[country]):
                val = float(row[country])
            elif pd.notna(default_val):
                val = float(default_val)
            else:
                continue

            # Resolve scenario
            if scenario_val in scenarios:
                target_scenarios = [scenario_val]
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
