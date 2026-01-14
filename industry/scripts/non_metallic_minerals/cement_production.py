# scripts/non_metallic_minerals/cement_production.py

import os
import sys
import pandas as pd
from typing import List, Dict, Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from cagr_helper import interpolate_or_extrapolate


def find_input_folder():
    current_dir = os.path.abspath(os.path.dirname(__file__))
    for _ in range(5):
        candidate = os.path.join(current_dir, "input_data")
        if os.path.isdir(candidate):
            return candidate
        current_dir = os.path.dirname(current_dir)
    raise FileNotFoundError("'input_data' folder not found after checking 5 levels.")


def find_cement_files(input_folder, country_name=None):
    cement_folder = os.path.join(input_folder, "cement")
    if not os.path.isdir(cement_folder):
        raise FileNotFoundError("Cement data subfolder not found.")

    def norm(x): return x.lower().replace(" ", "").replace("-", "")

    files = [
        f for f in os.listdir(cement_folder)
        if "myb3" in f.lower() and f.endswith((".xls", ".xlsx"))
    ]
    if country_name:
        cname = norm(country_name)
        files = [f for f in files if cname in norm(f)]

    if not files:
        raise FileNotFoundError(f"No cement files found for {country_name}")

    return [os.path.join(cement_folder, f) for f in files]


def load_cement_value(file_path, year="2020") -> float:
    df = pd.read_excel(file_path, sheet_name="Table 1", header=5)
    df.columns = df.columns.astype(str).str.strip()
    df["Commodity"] = df.iloc[:, 0].astype(str).str.strip()
    mask = df["Commodity"] == "Cement, hydraulic"
    if not mask.any():
        raise ValueError(f"'Cement, hydraulic' not found in {file_path}")

    year_str = str(year)
    if year_str not in df.columns:
        raise KeyError(f"Year column {year} not found in {file_path}")

    value = df.loc[mask, year_str].values[0]
    return float(value)  # thousand metric tons


# cement_production.py (or wherever your original lived)
from typing import Dict, List, Optional
from cagr_helper import interpolate_or_extrapolate, load_yaml_config

def get_cement_and_clinker(
    country_name: str,
    base_year: int,
    target_years: Optional[List[int]] = None,
    scenarios: Optional[List[str]] = None,
):
    
    if target_years is None:
        target_years = [2030, 2050]
    if scenarios is None:
        scenarios = ["Baseline", "Ambitious Policies", "Net Zero"]

    # --- Locate & load the country file the same way you already do ---
    input_folder = find_input_folder()
    cement_file = find_cement_files(input_folder, country_name)[0]

    # thousand t -> t
    cement_value_tpy = load_cement_value(cement_file, base_year) * 1e3

    # --- Clinker ratios (per scenario column order) ---
    base_factors = {
        2020: [0.71, 0.71, 0.71],
        2030: [0.71, 0.66, 0.65],
        2050: [0.71, 0.64, 0.61],
    }

    all_years = sorted(set([base_year] + target_years))
    clinker_factors: Dict[int, Dict[str, float]] = {}

    for i, sc in enumerate(scenarios):
        # make a per-scenario sparse series then interpolate to all_years
        series = {y: (vals[i] if i < len(vals) else vals[-1]) for y, vals in base_factors.items()}
        interp = interpolate_or_extrapolate(series, all_years)
        for y, v in interp.items():
            clinker_factors.setdefault(y, {})[sc] = float(v)

    # --- Build a cement production path (best-effort) ---
    # Try to read CAGR config so clinker production matches the table's logic.
    cement_path: Dict[int, Dict[str, float]] = {}
    try:
        # Optional imports kept inside the try so this function remains drop-in.
        from helpers import (
            _build_rate_anchors_indexed,
            _forecast_from_history_and_sparse_cagr,
            get_metric_cagr_cfg_layered,
        )

        cfg_expert = load_yaml_config("expert_assumptions.yaml")
        try:
            cfg_manual = load_yaml_config("manual_assumptions.yaml")
        except Exception:
            cfg_manual = {}

        metric_name = "Cement production per year"
        metric_cfg = get_metric_cagr_cfg_layered(cfg_expert, cfg_manual, country_name, metric_name)
        anchors = _build_rate_anchors_indexed(metric_cfg, scenarios)

        # Forecast from the base to the requested target years
        grown = _forecast_from_history_and_sparse_cagr(
            cement_value_tpy, base_year, target_years, anchors, scenarios
        )
        # grown is expected to be like {"2030_Baseline": val, "2030_Ambitious Policies": val, ...}
        # Build a {year: {sc: val}} dict; include base year
        cement_path[base_year] = {sc: cement_value_tpy for sc in scenarios}
        for y in target_years:
            for sc in scenarios:
                key = f"{y}_{sc}"
                v = grown.get(key, None)
                if v is None:
                    # fallback: if something off in format, keep base value
                    v = cement_value_tpy
                cement_path.setdefault(y, {})[sc] = float(v)

    except Exception:
        # No config / helpers / anything failed -> flat path
        cement_path = {y: {sc: cement_value_tpy for sc in scenarios} for y in all_years}

    # --- Finally compute clinker production from cement_path × clinker_factors ---
    clinker_production = {
        y: {sc: float(cement_path[y][sc]) * float(clinker_factors[y][sc]) for sc in scenarios}
        for y in all_years
    }

    return cement_value_tpy, clinker_factors, clinker_production

