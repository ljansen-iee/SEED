# scripts/non_metallic_minerals/cement_production.py

import os
import sys
import pandas as pd
from typing import List, Dict, Optional
import numpy as np
import re
from pathlib import Path

from industry.utils.helpers import interpolate_or_extrapolate


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
    if f.lower().startswith("myb") and f.endswith((".xls", ".xlsx"))
   ]
    if country_name:
        cname = norm(country_name)
        files = [f for f in files if cname in norm(f)]

    if not files:
        raise FileNotFoundError(f"No cement files found for {country_name}")

    return [os.path.join(cement_folder, f) for f in files]

def load_cement_value(file_path, year: int) -> float:
    """
    Load cement production (FINAL cement).
    Includes dynamic header detection to handle USGS formatting variations
    where headers appear on row 4, 5, or 6 instead of row 0.
    """
    # --------------------------------------------------
    # 1. Read file (ROBUST HEADER DETECTION)
    # --------------------------------------------------
    try:
        # Read raw data without assuming a header row
        df_raw = pd.read_excel(file_path, sheet_name="Table 1", header=None)
    except Exception:
        # Fallback: try reading the first sheet if "Table 1" doesn't exist
        try:
            df_raw = pd.read_excel(file_path, sheet_name=0, header=None)
        except Exception as e:
            print(f" Warning: Failed to read {file_path}. Assuming cement = 0. ({e})")
            return 0.0

    # Search first 20 rows for a row that looks like a header (contains years)
    header_idx = 0
    found_header = False
    
    for i, row in df_raw.head(20).iterrows():
        # Count how many cells look like years (2019, 2020, etc.)
        year_matches = sum(
            1 for x in row.astype(str) 
            if re.fullmatch(r"(19|20)\d{2}(\.0)?", x.strip())
        )
        # If we find at least 2 columns with years, this is our header
        if year_matches >= 2: 
            header_idx = i
            found_header = True
            break
    
    # If no header found, default to 0 (legacy behavior)
    if not found_header:
        header_idx = 0

    # Reload/slice dataframe using the identified header row
    df = df_raw.iloc[header_idx + 1:].copy()
    
    # Clean up column names: convert 2020.0 -> 2020 and strip whitespace
    df.columns = (
        df_raw.iloc[header_idx]
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
    )
    
    # Ensure the first column is named "Commodity" for consistency
    df.rename(columns={df.columns[0]: "Commodity"}, inplace=True)
    
    # Clean the Commodity column (remove nan/whitespace)
    df["Commodity"] = df["Commodity"].astype(str).str.strip()

    # --------------------------------------------------
    # 2. Find hydraulic cement row
    # --------------------------------------------------
    mask_hydraulic = df["Commodity"].str.contains(
        r"\bhydraulic\b", case=False, na=False
    )

    if not mask_hydraulic.any():
        print(f" Warning: No hydraulic cement found in {file_path}. Assuming 0.")
        return 0.0

    # Get the row where "hydraulic" was found
    row = df.loc[mask_hydraulic].iloc[0]

    # --------------------------------------------------
    # 3. Check if row has numeric year data
    # --------------------------------------------------
    # Regex checks for columns "19XX" or "20XX"
    year_cols = [c for c in df.columns if re.fullmatch(r"(19|20)\d{2}", str(c))]

    has_numbers = any(pd.notna(row[c]) for c in year_cols)

    if not has_numbers:
        # If the "Hydraulic" row is just a category header (common in US files),
        # check the next 8 rows for "Total" or the first row with numbers.
        idx = df.loc[mask_hydraulic].index[0]
        
        # Determine integer location to slice safely
        current_iloc = df.index.get_loc(idx)
        sub = df.iloc[current_iloc + 1 : current_iloc + 9]

        # Case A: Tunisia-style "Total"
        mask_total = sub["Commodity"].str.fullmatch(r"total", case=False, na=False)

        if mask_total.any():
            row = sub.loc[mask_total].iloc[0]
        else:
            # Case B: US-style -> Take the first row that has numbers in year columns
            found = False
            for _, r in sub.iterrows():
                if any(pd.notna(r[c]) for c in year_cols):
                    row = r
                    found = True
                    break

            if not found:
                print(
                    f" Warning: Hydraulic cement found but no usable numeric row in {file_path}. "
                    "Assuming 0."
                )
                return 0.0

    # --------------------------------------------------
    # 4. Extract yearly values
    # --------------------------------------------------
    year_value_map = {}

    for col in year_cols:
        cell = row[col]

        if pd.isna(cell):
            continue

        # Clean string values (e.g. "95,000 (e)" -> "95000")
        if isinstance(cell, str):
            cell_clean = re.sub(r"[^\d.]", "", cell)
        else:
            cell_clean = str(cell)

        if cell_clean != "":
            try:
                year_value_map[int(col)] = float(cell_clean)
            except ValueError:
                pass

    if not year_value_map:
        print(f" Warning: No usable cement values in {file_path}. Assuming 0.")
        return 0.0

    # --------------------------------------------------
    # 5. Exact year
    # --------------------------------------------------
    if year in year_value_map:
        return year_value_map[year]

    # --------------------------------------------------
    # 6. Interpolation / extrapolation
    # --------------------------------------------------
    years = np.array(sorted(year_value_map.keys()))
    values = np.array([year_value_map[y] for y in years])

    interpolated = float(np.interp(year, years, values))

    print(
        f" Info: Cement value for year {year} in {file_path} "
        f"derived by interpolation/extrapolation."
    )

    return interpolated


# cement_production.py (or wherever your original lived)
from typing import Dict, List, Optional
from industry.utils.helpers import interpolate_or_extrapolate, get_scenarios
import yaml

def load_yaml_config(filename: str):
    """Load YAML config file (helper for legacy code)."""
    config_path = Path(__file__).parent.parent.parent / "input_data" / filename
    if config_path.exists():
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    return {}

SCENARIOS = get_scenarios()

def get_cement_and_clinker(
    country_name: str,
    base_year: int,
    target_years: Optional[List[int]] = None,
    scenarios: Optional[List[str]] = None,
):
    
    if target_years is None:
        target_years = [2030, 2050]
    if scenarios is None:
        scenarios = SCENARIOS

    # --- Locate & load the country file the same way you already do ---
    input_folder = find_input_folder()
    try:
        cement_files = find_cement_files(input_folder, country_name)
        cement_file = cement_files[0]
    except FileNotFoundError:
        print(
            f" Info: No cement data file found for {country_name}. "
            f"Assuming cement production = 0."
        )
        # Return zeros and continue with other countries
        all_years = [base_year] + (target_years or [])
        zero_path = {y: {sc: 0.0 for sc in scenarios} for y in all_years}

        return (
            0.0,        # cement_value_tpy
            zero_path,  # clinker_factors
            zero_path,  # clinker_production
        )
    #print("DEBUG cement file:", cement_file)
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
        from industry.utils.helpers import (
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

