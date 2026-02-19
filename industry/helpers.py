# helpers.py
import numpy as np
import pandas as pd
def convert_wide_to_long(df_wide, country):
    """
    Convert wide format dataframe to long format for a given country.
    Assumes year columns are all except 'Country'.
    """
    df_country = df_wide[df_wide["Country"] == country]
    year_cols = [col for col in df_wide.columns if col != "Country"]
    df_long = df_country.melt(id_vars=["Country"], value_vars=year_cols,
                              var_name="Year", value_name="Production")
    df_long["Year"] = df_long["Year"].astype(int)
    return df_long

from industry.build_CAGR import interpolate_or_extrapolate

def extract_capacity_shares(df, country, steel_types, base_year=2020, target_years=None, all_types=None):
    """
    Extracts capacity share (% of total) for selected steel_types in a given country.
    - If types are missing → returns 0.
    - Automatically normalizes total shares across all steel pathways to 100%.
    - Interpolates/extrapolates for flexible target years.
    """

    df_country = df[df["Country"] == country]
    if df_country.empty:
        return {base_year: 0.0}

    # --- Sum share for this specific technology group ---
    share_value = df_country[df_country["Steel type"].isin(steel_types)]["Percentage"].sum()

    # --- Handle missing data ---
    if pd.isna(share_value) or share_value == 0:
        share_value = 0.0

    # --- Optional normalization across all steel types ---
    if all_types:
        total_sum = df_country[df_country["Steel type"].isin(all_types)]["Percentage"].sum()
        if total_sum > 0:
            share_value = round((share_value / total_sum) * 100.0, 2)

    # --- Ensure within bounds ---
    share_value = min(max(share_value, 0.0), 100.0)

    # --- Interpolate/extrapolate if needed ---
    result = {base_year: share_value}
    if target_years:
        interpolated = interpolate_or_extrapolate(result, [base_year] + target_years)
        return interpolated
    return result


def extract_all_fuels(func, target_years, scenarios=None):
    """
    Generic wrapper to extract interpolated results for all standard fuels
    from a given function like share_fuel_bf_bof or intensity_bf_bof.
    """
    fuels = ["diesel", "natural_gas", "electricity", "coal", "heat", "biomass", "hydrogen"]
    data = func(target_years, scenarios) if scenarios else func(target_years)
    
    extracted = {}
    for fuel in fuels:
        if fuel in data:
            extracted[fuel] = data[fuel]
        else:
            print(f" Warning: Fuel '{fuel}' missing in {func.__name__}")
            extracted[fuel] = {}
    return extracted


import re

def get_metric_cagr_cfg(cfg, country: str, metric_name: str):
    """
    Return the CAGR config for (country, metric), falling back to global if missing.
    Keys are matched case-insensitively. Values may be scalars, lists (index-mapped to scenarios),
    or dicts (legacy per-scenario names).
    """
    name_key = metric_name.strip().lower()

    # normalize keys once so casing/spacing in YAML won't matter
    def _norm_keys(d):
        return {str(k).strip().lower(): v for k, v in d.items()} if isinstance(d, dict) else {}

    ind = _norm_keys(cfg.get("industry", {}))
    cagr_global = _norm_keys(_norm_keys(cfg.get("industry", {})).get("cagr", {}))
    cagr_by_ctry_root = _norm_keys(_norm_keys(cfg.get("industry", {})).get("cagr_by_country", {}))

    # country block (case-insensitive country name)
    ctry_block = None
    for k, v in cagr_by_ctry_root.items():
        if str(k).strip().lower() == country.strip().lower():
            ctry_block = _norm_keys(v)
            break

    # pick country override if present, else global
    if ctry_block and name_key in ctry_block:
        return ctry_block[name_key]
    return cagr_global.get(name_key, {})



def _parse_rate(x):
    """Accept 0.02, '2%', '0.02', 2 → return decimal (e.g., 0.02)."""
    if x is None:
        return 0.0
    s = str(x).strip().replace("%", "")
    try:
        val = float(s)
    except Exception:
        return 0.0
    return val / 100.0 if val > 1 else val

def _ensure_len(vals, n):
    """Pad a list/tuple by repeating the last value until length n."""
    out = list(vals)
    while len(out) < n:
        out.append(out[-1])
    return out[:n]

def _build_rate_anchors_indexed(cagr_cfg, scenarios):
    """
    Accepts YAML in 3 shapes per year key:
      - scalar: 0.01 → same for all scenarios
      - list/tuple: [0.0, 0.01, 0.02] → map by position to scenarios
      - dict: {'Baseline':0.0,'Ambitious Policies':0.01,...} → fallback to old mode (tries exact/fuzzy)
    Returns: {scenario -> {year:int -> rate:float}}
    """
    anchors = {sc: {} for sc in scenarios}
    if not isinstance(cagr_cfg, dict):
        return anchors

    # helper: fuzzy pick from dict if given (for backward compatibility)
    def _pick_from_dict(per_sc: dict, sc_name: str):
        if sc_name in per_sc:
            return _parse_rate(per_sc[sc_name])
        # fuzzy tokens
        toks = set(re.findall(r"[a-z0-9]+", sc_name.lower()))
        best_key, best_score = None, -1
        for k in per_sc.keys():
            score = len(toks & set(re.findall(r"[a-z0-9]+", str(k).lower())))
            if score > best_score:
                best_key, best_score = k, score
        if best_key is not None and best_score > 0:
            return _parse_rate(per_sc[best_key])
        # fallback baseline or 0
        if "Baseline" in per_sc:
            return _parse_rate(per_sc["Baseline"])
        return 0.0

    for y_str, val in cagr_cfg.items():
        try:
            y = int(y_str)
        except Exception:
            continue

        if isinstance(val, dict):
            # old style: pick per scenario name (exact/fuzzy)
            for i, sc in enumerate(scenarios):
                anchors[sc][y] = _pick_from_dict(val, sc)

        elif isinstance(val, (list, tuple)):
            # index-based mapping
            arr = _ensure_len([_parse_rate(v) for v in val], len(scenarios))
            for i, sc in enumerate(scenarios):
                anchors[sc][y] = arr[i]

        else:
            # scalar → same for all scenarios
            r = _parse_rate(val)
            for sc in scenarios:
                anchors[sc][y] = r

    return anchors

def _rate_for_year_linear(sc_anchors: dict, year: int) -> float:
    """Piecewise-linear interpolation of annual rate between anchor years."""
    if not sc_anchors:
        return 0.0
    years = sorted(sc_anchors.keys())
    if year <= years[0]:
        return sc_anchors[years[0]]
    if year >= years[-1]:
        return sc_anchors[years[-1]]
    for i in range(1, len(years)):
        y1, y2 = years[i-1], years[i]
        if y1 < year <= y2:
            r1, r2 = sc_anchors[y1], sc_anchors[y2]
            t = (year - y1) / (y2 - y1)
            return r1 + t * (r2 - r1)
    return sc_anchors[years[-1]]

from typing import Dict, List


from typing import Dict, List

def _interpolated_cagr_for_year(
    cagr_cfg: Dict[int, float],
    year: int,
) -> float:
    """
    Given anchor CAGRs like {2030: -0.019, 2050: -0.01},
    return a CAGR for `year` by:
      - using exact value if year is present
      - linearly interpolating between the two surrounding anchors
      - linearly extrapolating outside the range
    """
    if not cagr_cfg:
        return 0.0

    # Ensure integer keys
    years = sorted(int(y) for y in cagr_cfg.keys())

    # Exact anchor
    if year in cagr_cfg:
        return float(cagr_cfg[year])

    # Before first anchor -> extrapolate using first two
    if year < years[0]:
        if len(years) == 1:
            return float(cagr_cfg[years[0]])
        y0, y1 = years[0], years[1]
    # After last anchor -> extrapolate using last two
    elif year > years[-1]:
        if len(years) == 1:
            return float(cagr_cfg[years[0]])
        y0, y1 = years[-2], years[-1]
    else:
        # Between anchors: find [y0, y1] such that y0 <= year <= y1
        y0, y1 = years[0], years[-1]
        for a, b in zip(years[:-1], years[1:]):
            if a <= year <= b:
                y0, y1 = a, b
                break

    r0 = float(cagr_cfg[y0])
    r1 = float(cagr_cfg[y1])

    if y1 == y0:
        return r0

    # Linear interpolation in time
    return r0 + (r1 - r0) * (year - y0) / (y1 - y0)


from typing import Dict, List

def _forecast_from_history_and_sparse_cagr(
    last_obs_val: float,
    last_obs_year: int,
    target_years: List[int],
    sc_anchors: Dict[str, Dict[int, float]],
    scenarios: List[str],
) -> Dict[str, float]:
    """
    Step-CAGR logic to match Excel milestones exactly.
    Applies the CAGR rate exponentially for the entire period.
    """
    result: Dict[str, float] = {}

    if not target_years:
        return result

    for sc in scenarios:
        anchors = sc_anchors.get(sc, {}) or {}
        # Get (year, rate) sorted by year
        anchor_items = sorted((int(y), float(r)) for y, r in anchors.items())

        for Y in sorted(target_years):
            if Y <= last_obs_year:
                result[f"{Y}_{sc}"] = float(last_obs_val)
                continue

            # STEP LOGIC: Find the rate that applies to the current target year
            active_rate = 0.0
            if anchor_items:
                for y_anchor, r_anchor in anchor_items:
                    if Y <= y_anchor:
                        active_rate = r_anchor
                        break
                else:
                    # If target year is past the last anchor, use the last known rate
                    active_rate = anchor_items[-1][1]

            # COMPOUND GROWTH: Base * (1 + r)^n
            # This is exactly how Excel calculates the 544,967 value.
            years_diff = Y - last_obs_year
            val_Y = float(last_obs_val) * ((1.0 + active_rate) ** years_diff)
            
            result[f"{Y}_{sc}"] = float(val_Y)

    return result


def _get_value_by_index(v, i: int):
    if v is None:
        return None

    # Handle Lists and Tuples
    if isinstance(v, (list, tuple)):
        # 1. Get the raw item first
        item = v[i] if i < len(v) else v[-1]
        
        # 2. Check if it is None BEFORE converting
        if item is None:
            return None
            
        return float(item)

    # Handle Dictionaries
    if isinstance(v, dict):
        arr = list(v.values())
        item = arr[i] if i < len(arr) else arr[-1]
        
        if item is None:
            return None
            
        return float(item)

    # Handle single values
    return float(v)

def _interp_at(series: dict, y: int):
    """series: {year:int -> float} → interpolate/extrapolate to year y"""
    if not series:
        return None
    try:
        out = interpolate_or_extrapolate(series, [int(y)])
        return out.get(int(y))
    except Exception:
        return None
    

def get_metric_cagr_cfg_layered(cfg_expert, cfg_manual, country, metric):

    def _get(dct, *keys):
        cur = dct
        for k in keys:
            if cur is None or not isinstance(cur, dict):
                return None
            cur = cur.get(k)
        return cur if isinstance(cur, dict) else None

    # manual > expert, country > global
    cand = (
        _get(cfg_manual.get("industry", {}), "cagr_by_country", country, metric)
        or _get(cfg_manual.get("industry", {}), "cagr", metric)
        or _get(cfg_expert.get("industry", {}), "cagr_by_country", country, metric)
        or _get(cfg_expert.get("industry", {}), "cagr", metric)
    )
    return cand or {}


from typing import Dict, Optional

def _interpolated_cagr_for_year(
    cagr_cfg: Dict[int, float],
    year: int,
) -> float:
    """
    Given anchor CAGRs like {2030: -0.019, 2050: -0.01},
    return a CAGR for `year` by:
      - using exact value if year is present
      - linearly interpolating between the two surrounding anchors
      - linearly extrapolating outside the range
    """
    if not cagr_cfg:
        return 0.0

    years = sorted(int(y) for y in cagr_cfg.keys())

    # Exact anchor
    if year in cagr_cfg:
        return float(cagr_cfg[year])

    # Before first anchor -> extrapolate using first two
    if year < years[0]:
        if len(years) == 1:
            return float(cagr_cfg[years[0]])
        y0, y1 = years[0], years[1]
    # After last anchor -> extrapolate using last two
    elif year > years[-1]:
        if len(years) == 1:
            return float(cagr_cfg[years[0]])
        y0, y1 = years[-2], years[-1]
    else:
        # Between anchors: find the segment [y0, y1] that contains `year`
        y0, y1 = years[0], years[-1]
        for a, b in zip(years[:-1], years[1:]):
            if a <= year <= b:
                y0, y1 = a, b
                break

    r0 = float(cagr_cfg[y0])
    r1 = float(cagr_cfg[y1])

    if y1 == y0:
        return r0

    # Linear interpolation in time
    return r0 + (r1 - r0) * (year - y0) / (y1 - y0)


def get_mapped_config_name(metric_name: str) -> str:
    """
    Maps specific fuel-based metric names to general process categories 
    defined in the industry_config Excel file.
    """
    # 1. First, check if this is an Intensity metric. 
    # If it is NOT an intensity metric, return the name as is (to pick up Production rates)
    if "intensity" not in metric_name.lower():
        return metric_name

    # 2. If it IS an intensity metric, map the fuel-specific name to the general category
    mapping_keywords = {
        "blast furnaces + open hearth furnace": "Energy intensity of blast furnaces + open hearth furnaces",
        "blast furnaces + basic oxygen furnace": "Energy intensity of blast furnaces + basic oxygen furnaces",
        "direct reduction + electric arc furnace": "Energy intensity of direct reduction + electric arc furnaces",
        "scrap electric arc furnaces": "Energy intensity of scrap electric arc furnaces",
        "casting, rolling & finishing": "Energy intensity of casting, rolling & finishing",
        "SMR + Haber-Bosch": "Energy intensity of SMR + Haber-Bosch",
        "renewable ammonia synthesis": "Energy intensity of renewable ammonia synthesis",
        "cement production": "Energy intensity of cement production",
        "paper production": "Energy intensity of paper production",
        "primary pulp": "Energy intensity of primary pulp production",
        "secondary pulp": "Energy intensity of secondary pulp production"
    }

    for keyword, config_name in mapping_keywords.items():
        if keyword.lower() in metric_name.lower():
            return config_name
            
    return metric_name

import pandas as pd
from pathlib import Path

def get_historical_sector_data(folder_path: Path, country: str, sector_keyword: str):
    """
    Scans folder for 'Country-Year.csv', finds sector in the 2nd column, 
    and cleans strings like '---' or '*123' into numbers.
    """
    history = {}
    
    # 1. Glob all files for this country (e.g., Morocco-2016.csv, Morocco-2017.csv)
    files = list(folder_path.glob(f"{country}-*.csv"))
    
    if not files:
        print(f" No files found for {country} in {folder_path}")
        return None

    for file_path in files:
        try:
            # 2. Extract year from filename
            year_str = file_path.stem.split("-")[-1]
            year = int(year_str)

            df = pd.read_csv(file_path)
            
            # 3. Clean column headers and find the 'Total Energy' column
            df.columns = df.columns.str.strip()
            val_col = [c for c in df.columns if "Total Energy" in c][0]
            
            # 4. Search in the SECOND column (index 1) for the sector name
            # Your CSV format has 'Transactions' in the second column.
            mask = df.iloc[:, 1].astype(str).str.contains(sector_keyword, case=False, na=False)
            sector_row = df[mask]
            
            if not sector_row.empty:
                raw_val = str(sector_row[val_col].iloc[0])
                
                # 5. Data Cleaning: remove '---', '*', and spaces
                clean_val = raw_val.replace("---", "0").replace("*", "").strip()
                history[year] = float(clean_val)
                
        except Exception as e:
            print(f" Error processing {file_path.name} for {sector_keyword}: {e}")

    if not history:
        print(f" No data found for sector '{sector_keyword}' in {country}")
        return None

    #print(f" Loaded {len(history)} years for {sector_keyword}")
    return history
    
def poly_project(years, values, target_years, degree=1):
    import numpy as np
    try:
        # 1. Filter out zeros and NaNs to find the real historical trend
        clean_points = [(float(y), float(v)) for y, v in zip(years, values) if v > 0]
        
        if len(clean_points) < 2:
            # Not enough data to find a trend; return the last known value flat
            val = clean_points[-1][1] if clean_points else 0.0
            return {int(t): val for t in target_years}

        x_train, y_train = zip(*clean_points)
        
        # 2. Linear fit (Degree 1)
        coeffs = np.polyfit(x_train, y_train, degree)
        model = np.poly1d(coeffs)
        
        # 3. Predict future years (keeping values positive)
        return {int(t): max(0.0, float(model(t))) for t in target_years}
    except Exception as e:
        print(f"Error in poly_project: {e}")
        return {int(t): 0.0 for t in target_years}
    
def validate_fuel_shares(rows, base_year, target_years, scenarios):
    """
    Checks if FUEL shares sum to 100%. 
    Filters out production route shares to avoid incorrect warnings.
    """
    # Only sum metrics that contain these specific fuel words
    valid_fuels = [
        "diesel", "natural gas", "gas", "electricity", "coal", 
        "heat", "biomass", "hydrogen", "ammonia", "methanol", "oil", "steel"
    ]

    sector_keywords = {
        "Primary Pulp": "primary pulp production",
        "Secondary Pulp": "secondary pulp production",
        "Paper": "paper production",
        "Cement": "cement production",
        "Steel (BF+OHF)": "blast furnaces + open hearth furnace",
        "Steel (BF+BOF)": "blast furnaces + basic oxygen furnace",
        "Steel (DR+EAF)": "direct reduction + electric arc furnace",
        "Steel (Scrap EAF)": "scrap electric arc furnaces",
        "Steel (Unspecified)": "unspecified iron and steel",
        "Chemicals (Unspecified)": "unspecified chemicals",
        "Construction": "unspecified construction",
        "Machinery": "unspecified machinery",
        "Mining": "unspecified mining and quarrying",
        "Textile": "unspecified textile and leather",
        "Transport": "unspecified transport equipment",
        "Wood": "unspecified wood and wood products",
        "Food & Tobacco": "unspecified food and tobacco"
    }

    check_cols = [str(base_year)] + [f"{y}_{sc}" for y in target_years for sc in scenarios]
    
    for label, keyword in sector_keywords.items():
        # FILTER LOGIC: Must contain "share of" AND the sector keyword AND a valid fuel name
        sector_rows = [
            r for r in rows if keyword in r['Metric'].lower() 
            and "share of" in r['Metric'].lower()
            and any(fuel in r['Metric'].lower() for fuel in valid_fuels)
        ]
        
        if not sector_rows:
            continue

        for col in check_cols:
            total = sum(float(r.get(col, 0) or 0) for r in sector_rows)
            
            # Warn if not 100%
            if abs(total - 100) > 0.1 and total > 0:
                print(f" FUEL SHARE WARNING: {label} totals {total:.2f}% in {col}")


# ==============================
# COUNTRY NAME → ISO2 CONVERSION
# ==============================

def country_to_iso2(country_name: str) -> str:
    """
    Convert full country name to ISO2 code.
    Example: 'Morocco' -> 'MA'
    """

    if not country_name:
        return None

    name = country_name.strip()

    # --- Try pycountry first (most reliable) ---
    try:
        import pycountry
        country = pycountry.countries.lookup(name)
        return country.alpha_2
    except Exception:
        pass

    # --- Fallback manual mapping (common mismatches) ---
    fallback = {
        "South Africa": "ZA",
        "Egypt": "EG",
        "Morocco": "MA",
        "Chile": "CL",
        "Republic of the Congo": "CG",
        "Congo": "CG",
        "Democratic Republic of the Congo": "CD",
        "Tanzania": "TZ",
        "United States": "US",
        "United States of America": "US",
        "Russia": "RU",
        "South Korea": "KR",
        "North Korea": "KP",
        "Vietnam": "VN",
        "Iran": "IR",
        "Syria": "SY",
        "Bolivia": "BO",
        "Venezuela": "VE",
        "Libya": "LY",
    }

    return fallback.get(name)
