# ===========================================================
# cagr_helper.py
# Utility functions for loading YAML configs and applying CAGR logic
# ===========================================================

import yaml
import os
import math
import numpy as np
from typing import Dict, List
import pandas as pd
from pathlib import Path
SCENARIO_ALIAS_MAP = {
    "sc_a": 0,
    "sc_b": 1,
    "sc_c": 2,
}


def load_yaml_config(file_path: str = "expert_assumptions.yaml") -> Dict:
    """
    Load the expert assumptions YAML configuration file.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


import math
import numpy as np
from typing import List, Dict

def expand_with_cagr_piecewise(
    base_value: float,
    base_year: int,
    target_years: List[int],
    cagr_segments: Dict[int, Dict[str, float]],
    scenario: str
) -> Dict[int, float]:
    """
    Interpolated CAGR version (continuous growth between milestones).

    Example:
        CAGR_2030 = 0.02 (2%)
        CAGR_2050 = 0.01 (1%)
      -> CAGR_2040 interpolates linearly ≈ 1.5%

    Formula:
        value(year) = base_value * (1 + interpolated_cagr)^(year - base_year)
    """

    # 1️ Validate inputs
    if base_value is None or (isinstance(base_value, float) and math.isnan(base_value)):
        return {y: None for y in target_years}

    if not isinstance(cagr_segments, dict) or len(cagr_segments.keys()) == 0:
        return {y: base_value for y in target_years}

    # 2️ Extract sorted milestone years and CAGRs for the scenario
    milestone_years = sorted(cagr_segments.keys())
    milestone_cagrs = [float(cagr_segments[y].get(scenario, 0.0)) for y in milestone_years]

    # 3 Compute interpolated CAGR for each target year
    result = {}
    for y in sorted(target_years):
        # Interpolate CAGR for this specific year
        if y <= milestone_years[0]:
            cagr = milestone_cagrs[0]
        elif y >= milestone_years[-1]:
            cagr = milestone_cagrs[-1]
        else:
            cagr = np.interp(y, milestone_years, milestone_cagrs)

        # Apply compounded growth from base_year
        result[y] = base_value * ((1 + cagr) ** (y - base_year))

    return result



from scipy.interpolate import interp1d
import numpy as np
from typing import Dict, List

from scipy.interpolate import interp1d
import numpy as np
from typing import Dict, List

def interpolate_or_extrapolate(values: Dict[int, float], target_years: List[int]) -> Dict[int, float]:
   
    known_years = sorted([y for y, v in values.items() if v is not None])
    known_vals = [values[y] for y in known_years]

    if len(known_years) < 2:
        return {year: known_vals[0] for year in target_years}

    f = interp1d(known_years, known_vals, fill_value="extrapolate")

    return {year: float(f(year)) for year in target_years}




def export_metric_template_to_yaml(metrics: dict, output_path: str, section_name: str = "industry"):
    """
    Creates or updates a YAML file with all metric names and placeholder CAGR values
    for each scenario and year.
    Existing values are preserved, new metrics are added automatically.
    """
    # Load existing file if present
    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    # Ensure section exists
    if section_name not in data:
        data[section_name] = {"cagr": {}}

    cagr_section = data[section_name]["cagr"]

    # Add missing metrics
    for metric_name in metrics.keys():
        if metric_name not in cagr_section:
            cagr_section[metric_name] = {
                "Baseline": {"2020-2030": 0.0, "2030-2050": 0.0},
                "Ambitious Policies": {"2020-2030": 0.0, "2030-2050": 0.0},
                "Net Zero": {"2020-2030": 0.0, "2030-2050": 0.0},
            }

    # Save back to file
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)

    print(f" YAML file updated/created: {output_path}")


def deep_merge_dicts(base: dict, override: dict) -> dict:
    """Recursively merge two dictionaries (override > base)."""
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge_dicts(result[k], v)
        else:
            result[k] = v
    return result


def load_and_merge_yaml(expert_path: str, manual_path: str = None) -> tuple:
    """
    Loads expert and manual YAMLs, merges them (manual overrides expert),
    and returns (merged_cfg, expert_cfg, manual_cfg).
    """
    # Load expert YAML
    if os.path.exists(expert_path):
        with open(expert_path, "r", encoding="utf-8") as f:
            expert_cfg = yaml.safe_load(f) or {}
    else:
        expert_cfg = {}

    # Load manual YAML
    if manual_path and os.path.exists(manual_path):
        with open(manual_path, "r", encoding="utf-8") as f:
            manual_cfg = yaml.safe_load(f) or {}
    else:
        manual_cfg = {}

    # Merge (manual overrides expert)
    merged_cfg = deep_merge_dicts(expert_cfg, manual_cfg)
    return merged_cfg, expert_cfg, manual_cfg


def save_merged_yaml(merged_cfg: dict, output_path: str):
    """Save the final merged YAML (for transparency)."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(merged_cfg, f, sort_keys=False, allow_unicode=True)
    print(f" Final merged YAML saved to: {output_path}")

def apply_cagr_growth(base_value, base_year, target_years, cagr_segments, scenario="Baseline"):
    """
    Wrapper for expand_with_cagr_piecewise to maintain compatibility
    with all sector scripts (steel, ammonia, pulp, cement, etc.).
    """
    return expand_with_cagr_piecewise(base_value, base_year, target_years, cagr_segments, scenario)


import os, copy, yaml

# ---------- basic loaders ----------
def load_yaml_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def save_merged_yaml(cfg: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)

# ---------- merge (manual overrides expert) ----------
def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base (override wins)."""
    if not isinstance(base, dict) or not isinstance(override, dict):
        return copy.deepcopy(override)
    out = copy.deepcopy(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out

def make_effective_cfg(run_mode: str,
                       expert_path="expert_assumptions.yaml",
                       manual_path="manual_assumptions.yaml",
                       final_out="final_assumptions.yaml"):
    """
    Returns the config actually used, plus a source label.
    - 'expert' -> expert only
    - 'manual' -> manual over expert (NOT saved)
    - 'final'  -> manual over expert (SAVED to final_assumptions.yaml)
    """
    expert = load_yaml_config(expert_path)
    if run_mode == "expert":
        return expert, "expert_assumptions.yaml"

    manual = load_yaml_config(manual_path)
    effective = _deep_merge(expert, manual)

    if run_mode == "final":
        save_merged_yaml(effective, final_out)
        src = "expert + manual (merged -> final_assumptions.yaml)"
    else:  # run_mode == "manual"
        src = "manual overrides applied over expert (not saved)"
    return effective, src

# ---------- resolving per-metric CAGR with country fallback ----------
def get_metric_cagr_cfg_from_excel(
    cagr_cfg_excel: dict,
    country: str,
    metric_name: str,
) -> dict:
    """
    Returns:
      {year: [v0, v1, v2]}
    """
    country_cfg = cagr_cfg_excel.get(country, {})

    # exact match
    if metric_name in country_cfg:
        return country_cfg[metric_name]

    # case-insensitive fallback
    for k, v in country_cfg.items():
        if k.strip().lower() == metric_name.strip().lower():
            return v

    return {}


def load_industry_cagr_from_excel(
    excel_path: Path,
    countries: list,
    scenarios: list,
):
    """
    Loads CAGR assumptions from industry_config.xlsx
    Returns:
      cfg[country][metric][year] = [val_s0, val_s1, val_s2]
    """

    df = pd.read_excel(excel_path)
    df.columns = df.columns.str.strip()

    required = {"Assumption Type", "Metric Name", "Year", "Scenario", "default"}
    if not required.issubset(df.columns):
        raise ValueError(f"Missing required columns: {required}")

    cfg = {c: {} for c in countries}

    for _, row in df.iterrows():
        if str(row["Assumption Type"]).strip().upper() != "CAGR":
            continue

        metric = str(row["Metric Name"]).strip()

        try:
            year = int(row["Year"])
        except Exception:
            continue

        scen_key = str(row["Scenario"]).strip().lower()
        if scen_key not in SCENARIO_ALIAS_MAP:
            continue

        s_idx = SCENARIO_ALIAS_MAP[scen_key]
        if s_idx >= len(scenarios):
            continue

        for country in countries:

            # ---------- THIS IS THE FALLBACK RULE ----------
            if country in df.columns and pd.notna(row[country]):
                val = float(row[country])
            elif pd.notna(row["default"]):
                val = float(row["default"])
            else:
                continue
            # ---------------------------------------------

            metric_cfg = cfg[country].setdefault(metric, {})
            year_cfg = metric_cfg.setdefault(year, [None] * len(scenarios))
            year_cfg[s_idx] = val

    return cfg
