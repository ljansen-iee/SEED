# helpers.py
import ast
from pathlib import Path
from typing import Callable, Dict, List
import numpy as np
import pandas as pd
from scipy.interpolate import interp1d

DEFAULT_TARGET_YEARS = [2030, 2035, 2040, 2045, 2050]


# ============================================================================
# INTERPOLATION / EXTRAPOLATION UTILITIES
# ============================================================================

def interpolate_or_extrapolate(values: Dict[int, float], target_years: List[int]) -> Dict[int, float]:
    """
    Interpolate or extrapolate values for target years based on known values.
    
    Args:
        values: Dict of {year: value}, some values may be None
        target_years: List of years to generate values for
    
    Returns:
        Dict of {year: interpolated_value} for all target years
    """
    known_years = sorted([y for y, v in values.items() if v is not None])
    if not known_years:
        return {y: 0.0 for y in target_years}
    
    known_vals = [values[y] for y in known_years]
    if len(known_years) < 2:
        return {y: known_vals[0] for y in target_years}
    
    f = interp1d(known_years, known_vals, fill_value="extrapolate")
    return {y: float(f(y)) for y in target_years}


def _resolve_industry_dir():
    """Resolve the industry directory path for both script and interactive use."""
    try:
        # Since this file is now in core/, go up one level to get industry/
        return Path(__file__).resolve().parent.parent
    except NameError:
        cwd = Path.cwd().resolve()
        if (cwd / "industry").exists():
            return cwd / "industry"
        return cwd


INDUSTRY_DIR = _resolve_industry_dir()


def get_scenarios_from_build_config_industry() -> list[str]:
    """
    Return the standard scenarios list.
    
    Note: This used to read from build_config_industry.py, but now returns
    the standard scenarios directly to avoid circular imports with legacy files.
    """
    return ["BAU", "Progressive", "Optimistic"]

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
    
    Includes endogenous carriers (ammonia, methanol, steel) which are demanded
    as intermediate products rather than being disaggregated into their production fuels.
    """
    fuels = ["diesel", "natural_gas", "electricity", "coal", "heat", "biomass", "hydrogen", 
             "ammonia", "methanol", "steel"]
    data = func(target_years, scenarios) if scenarios else func(target_years)
    
    extracted = {}
    for fuel in fuels:
        if fuel in data:
            extracted[fuel] = data[fuel]
        else:
            # Don't warn - many routes legitimately don't use all fuels
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
        "unspecified iron and steel": "Energy intensity of unspecified iron and steel",
        "SMR + Haber-Bosch": "Energy intensity of SMR + Haber-Bosch",
        "Other Conventional + Haber-Bosch": "Energy intensity of Other Conventional + Haber-Bosch",
        "renewable ammonia synthesis": "Energy intensity of renewable ammonia synthesis",
        "Naphtha cracking": "Energy intensity of Naphtha cracking",
        "LPG cracking": "Energy intensity of LPG cracking",
        "Methanol route": "Energy intensity of Methanol route",
        "unspecified chemicals": "Energy intensity of unspecified chemicals",
        "cement production": "Energy intensity of cement production",
        "unspecified non metallic minerals": "Energy intensity of unspecified non metallic minerals",
        "paper production": "Energy intensity of paper production",
        "primary pulp production": "Energy intensity of primary pulp production",
        "secondary pulp production": "Energy intensity of secondary pulp production",
        "unspecified paper and pulp": "Energy intensity of unspecified paper and pulp"
    }

    for keyword, config_name in mapping_keywords.items():
        if keyword.lower() in metric_name.lower():
            return config_name
            
    return metric_name

import pandas as pd
from pathlib import Path

TJ_TO_GWH = 0.2777777778

def get_historical_sector_data(folder_path: Path, country: str, sector_keyword: str):
    """
    Scans folder for 'Country-Year.csv', finds sector in the 2nd column, 
    and cleans strings like '---' or '*123' into numbers.
    """
    history = {}
    
    # 1. Glob all files for this country (e.g., UNSD_Morocco-2016.csv, UNSD_Morocco-2017.csv)
    files = list(folder_path.glob(f"UNSD_{country}-*.csv"))
    
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

                clean_val = raw_val.replace("*", "").replace(",", "").strip()
                if clean_val in {"---", "", "nan", "NaN"}:
                    continue

                history[year] = float(clean_val) * TJ_TO_GWH
                
        except Exception as e:
            pass  # Silently skip files with processing errors

    if not history:
        return None

    #print(f" Loaded {len(history)} years for {sector_keyword}")
    return history


def get_fuel_shares_from_unsd(folder_path: Path, country: str, sector_keyword: str) -> dict | None:
    """
    Extract fuel share percentages from the latest UNSD country-year CSV for a sector.
    
    Args:
        folder_path: Path to folder containing Country-Year.csv files
        country: Country name (e.g., "Morocco")
        sector_keyword: Sector to search for (e.g., "Food and tobacco")
    
    Returns:
        Dict with fuel shares as percentages: {"oil": 30.0, "gas": 25.0, ...}
        Returns all zeros if sector exists but has zero energy consumption.
        Returns None only if data file is missing or sector not found (caller should handle averaging).
    """
    # Zero shares - returned when sector has zero energy consumption
    zero_shares = {
        "oil": 0.0,
        "gas": 0.0,
        "electricity": 0.0,
        "coal": 0.0,
        "biomass": 0.0,
        "hydrogen": 0.0,
    }
    
    # Find all files for this country (with UNSD_ prefix)
    files = list(folder_path.glob(f"UNSD_{country}-*.csv"))
    if not files:
        print(f" No UNSD files found for {country} in {folder_path}")
        return None  # Missing data - caller should use average
    
    # Get the latest year file
    year_files = []
    for f in files:
        try:
            year_str = f.stem.split("-")[-1]
            year = int(year_str)
            year_files.append((year, f))
        except ValueError:
            continue
    
    if not year_files:
        return None  # Missing data - caller should use average
    
    year_files.sort(reverse=True)
    latest_year, latest_file = year_files[0]
    
    try:
        df = pd.read_csv(latest_file)
        df.columns = df.columns.str.strip()
        
        # Find the sector row (search in second column)
        mask = df.iloc[:, 1].astype(str).str.contains(sector_keyword, case=False, na=False)
        sector_row = df[mask]
        
        if sector_row.empty:
            print(f" Sector '{sector_keyword}' not found in {latest_file.name}")
            return None  # Sector not in file - caller should use average
        
        row = sector_row.iloc[0]
        
        # Helper to clean and parse cell values
        def parse_val(col_pattern):
            for col in df.columns:
                if col_pattern.lower() in col.lower():
                    raw = str(row[col])
                    clean = raw.replace("*", "").replace(",", "").strip()
                    if clean in {"---", "", "nan", "NaN"}:
                        return 0.0
                    try:
                        return float(clean)
                    except ValueError:
                        return 0.0
            return 0.0
        
        # Extract fuel values (TJ)
        coal = parse_val("Primary Coal") + parse_val("Coal and Peat Products")
        oil = parse_val("Oil Products")  # Primary Oil is typically 0 at industry level
        gas = parse_val("Natural Gas")
        electricity = parse_val("Electricity")
        biomass = parse_val("Biofuels")  # "Biofuels and Waste"
        heat = parse_val("Heat")
        
        # Total (electricity + heat + fuels)
        total = coal + oil + gas + electricity + biomass + heat
        
        if total <= 0:
            # Sector exists but uses zero energy - return all zeros (NOT None)
            return zero_shares
        
        # Calculate percentages
        shares = {
            "oil": round(100 * oil / total, 2),
            "gas": round(100 * gas / total, 2),
            "electricity": round(100 * (electricity + heat) / total, 2),  # Include heat with electricity
            "coal": round(100 * coal / total, 2),
            "biomass": round(100 * biomass / total, 2),
            "hydrogen": 0.0,  # No historical hydrogen data
        }
        
        return shares
        
    except Exception as e:
        print(f" Error extracting fuel shares from {latest_file.name}: {e}")
        return None  # Error reading file - caller should use average

    
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
    # NOTE: Removed "steel" to avoid matching "steel making" in route share names
    valid_fuels = [
        "diesel", "natural gas", "gas", "electricity", "coal", 
        "heat", "biomass", "hydrogen", "ammonia", "methanol", "oil"
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
            
            # Warn if not 100% (allow 0.2% tolerance for rounding)
            if abs(total - 100) > 0.2 and total > 0:
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


# === Metric ordering for output CSV ===
METRIC_ORDER = [
    # --- STEEL ---
    "Steel production per year",
    "Share of primary steel",
    "Share of secondary steel = scrap electric arc furnaces",
    "Share of blast furnace + open hearth furnace for steel making",
    "Share of blast furnace + basic oxygen furnace for steel making",
    "Share of direct reduction + electric arc furnace for steel making",
    # BF+OHF shares
    "Share of diesel for blast furnaces + open hearth furnace",
    "Share of natural gas for blast furnaces + open hearth furnace",
    "Share of electricity for blast furnaces + open hearth furnace",
    "Share of coal for blast furnaces + open hearth furnace",
    "Share of heat for blast furnaces + open hearth furnace",
    "Share of biomass for blast furnaces + open hearth furnace",
    "Share of hydrogen for blast furnaces + open hearth furnace",
    # BF+OHF intensities
    "Energy intensity of diesel in blast furnaces + open hearth furnace",
    "Energy intensity of natural gas in blast furnaces + open hearth furnace",
    "Energy intensity of electricity in blast furnaces + open hearth furnace",
    "Energy intensity of coal in blast furnaces + open hearth furnace",
    "Energy intensity of heat in blast furnaces + open hearth furnace",
    "Energy intensity of biomass in blast furnaces + open hearth furnace",
    "Energy intensity of hydrogen in blast furnaces + open hearth furnace",
    # BF+BOF shares
    "Share of diesel for blast furnaces + basic oxygen furnace",
    "Share of natural gas for blast furnaces + basic oxygen furnace",
    "Share of electricity for blast furnaces + basic oxygen furnace",
    "Share of coal for blast furnaces + basic oxygen furnace",
    "Share of heat for blast furnaces + basic oxygen furnace",
    "Share of biomass for blast furnaces + basic oxygen furnace",
    "Share of hydrogen for blast furnaces + basic oxygen furnace",
    # BF+BOF intensities
    "Energy intensity of diesel in blast furnaces + basic oxygen furnace",
    "Energy intensity of natural gas in blast furnaces + basic oxygen furnace",
    "Energy intensity of electricity in blast furnaces + basic oxygen furnace",
    "Energy intensity of coal in blast furnaces + basic oxygen furnace",
    "Energy intensity of heat in blast furnaces + basic oxygen furnace",
    "Energy intensity of biomass in blast furnaces + basic oxygen furnace",
    "Energy intensity of hydrogen in blast furnaces + basic oxygen furnace",
    # DR+EAF shares
    "Share of diesel for direct reduction + electric arc furnace",
    "Share of natural gas for direct reduction + electric arc furnace",
    "Share of electricity for direct reduction + electric arc furnace",
    "Share of coal for direct reduction + electric arc furnace",
    "Share of heat for direct reduction + electric arc furnace",
    "Share of biomass for direct reduction + electric arc furnace",
    "Share of hydrogen for direct reduction + electric arc furnace",
    # DR+EAF intensities
    "Energy intensity of diesel in direct reduction + electric arc furnace",
    "Energy intensity of natural gas in direct reduction + electric arc furnace",
    "Energy intensity of electricity in direct reduction + electric arc furnace",
    "Energy intensity of coal in direct reduction + electric arc furnace",
    "Energy intensity of heat in direct reduction + electric arc furnace",
    "Energy intensity of biomass in direct reduction + electric arc furnace",
    "Energy intensity of hydrogen in direct reduction + electric arc furnace",
    # Scrap EAF shares
    "Share of diesel for scrap electric arc furnaces",
    "Share of natural gas for scrap electric arc furnaces",
    "Share of electricity for scrap electric arc furnaces",
    "Share of coal for scrap electric arc furnaces",
    "Share of heat for scrap electric arc furnaces",
    "Share of biomass for scrap electric arc furnaces",
    "Share of hydrogen for scrap electric arc furnaces",
    # Scrap EAF intensities
    "Energy intensity of diesel in scrap electric arc furnaces",
    "Energy intensity of natural gas in scrap electric arc furnaces",
    "Energy intensity of electricity in scrap electric arc furnaces",
    "Energy intensity of coal in scrap electric arc furnaces",
    "Energy intensity of heat in scrap electric arc furnaces",
    "Energy intensity of biomass in scrap electric arc furnaces",
    "Energy intensity of hydrogen in scrap electric arc furnaces",
    # Casting/Rolling shares
    "Share of diesel for casting, rolling & finishing",
    "Share of natural gas for casting, rolling & finishing",
    "Share of electricity for casting, rolling & finishing",
    "Share of coal for casting, rolling & finishing",
    "Share of heat for casting, rolling & finishing",
    "Share of biomass for casting, rolling & finishing",
    "Share of hydrogen for casting, rolling & finishing",
    # Casting/Rolling intensity
    "Energy intensity of casting, rolling & finishing",
    # Unspecified iron and steel
    "Activity factor of unspecified iron and steel",
    "Share of diesel for unspecified iron and steel",
    "Share of natural gas for unspecified iron and steel",
    "Share of electricity for unspecified iron and steel",
    "Share of coal for unspecified iron and steel",
    "Share of heat for unspecified iron and steel",
    "Share of biomass for unspecified iron and steel",
    "Share of hydrogen for unspecified iron and steel",
    "Energy intensity of unspecified iron and steel",
    
    # --- CHEMICAL ---
    "Ammonia production per year",
    "Share of SMR + Haber-Bosch",
    "Share of Other Conventional + Haber-Bosch",
    "Share of renewable ammonia synthesis",
    # SMR+HB shares
    "Share of diesel for SMR + Haber-Bosch",
    "Share of natural gas for SMR + Haber-Bosch",
    "Share of electricity for SMR + Haber-Bosch",
    "Share of coal for SMR + Haber-Bosch",
    "Share of heat for SMR + Haber-Bosch",
    "Share of biomass for SMR + Haber-Bosch",
    "Share of hydrogen for SMR + Haber-Bosch",
    # SMR+HB intensities
    "Energy intensity of diesel in SMR + Haber-Bosch",
    "Energy intensity of natural gas in SMR + Haber-Bosch",
    "Energy intensity of electricity in SMR + Haber-Bosch",
    "Energy intensity of coal in SMR + Haber-Bosch",
    "Energy intensity of heat in SMR + Haber-Bosch",
    "Energy intensity of biomass in SMR + Haber-Bosch",
    "Energy intensity of hydrogen in SMR + Haber-Bosch",
    # Other Conventional shares
    "Share of diesel for Other Conventional + Haber-Bosch",
    "Share of natural gas for Other Conventional + Haber-Bosch",
    "Share of electricity for Other Conventional + Haber-Bosch",
    "Share of coal for Other Conventional + Haber-Bosch",
    "Share of heat for Other Conventional + Haber-Bosch",
    "Share of biomass for Other Conventional + Haber-Bosch",
    "Share of hydrogen for Other Conventional + Haber-Bosch",
    # Other Conventional intensities
    "Energy intensity of diesel in Other Conventional + Haber-Bosch",
    "Energy intensity of natural gas in Other Conventional + Haber-Bosch",
    "Energy intensity of electricity in Other Conventional + Haber-Bosch",
    "Energy intensity of coal in Other Conventional + Haber-Bosch",
    "Energy intensity of heat in Other Conventional + Haber-Bosch",
    "Energy intensity of biomass in Other Conventional + Haber-Bosch",
    "Energy intensity of hydrogen in Other Conventional + Haber-Bosch",
    # Renewable ammonia shares
    "Share of diesel for renewable ammonia synthesis",
    "Share of natural gas for renewable ammonia synthesis",
    "Share of electricity for renewable ammonia synthesis",
    "Share of coal for renewable ammonia synthesis",
    "Share of heat for renewable ammonia synthesis",
    "Share of biomass for renewable ammonia synthesis",
    "Share of hydrogen for renewable ammonia synthesis",
    # Renewable ammonia intensities
    "Energy intensity of diesel in renewable ammonia synthesis",
    "Energy intensity of natural gas in renewable ammonia synthesis",
    "Energy intensity of electricity in renewable ammonia synthesis",
    "Energy intensity of coal in renewable ammonia synthesis",
    "Energy intensity of heat in renewable ammonia synthesis",
    "Energy intensity of biomass in renewable ammonia synthesis",
    "Energy intensity of hydrogen in renewable ammonia synthesis",
    # HVC
    "High value chemical production per year",
    "Share of Naphtha cracking for HVC production",
    "Share of LPG cracking for HVC production",
    "Share of Methanol route for HVC production",
    # Naphtha cracking shares
    "Share of diesel for Naphtha cracking",
    "Share of natural gas for Naphtha cracking",
    "Share of electricity for Naphtha cracking",
    "Share of coal for Naphtha cracking",
    "Share of heat for Naphtha cracking",
    "Share of biomass for Naphtha cracking",
    "Share of hydrogen for Naphtha cracking",
    # Naphtha cracking intensities
    "Energy intensity of diesel in Naphtha cracking",
    "Energy intensity of natural gas in Naphtha cracking",
    "Energy intensity of electricity in Naphtha cracking",
    "Energy intensity of coal in Naphtha cracking",
    "Energy intensity of heat in Naphtha cracking",
    "Energy intensity of biomass in Naphtha cracking",
    "Energy intensity of hydrogen in Naphtha cracking",
    # LPG cracking shares
    "Share of diesel for LPG cracking",
    "Share of natural gas for LPG cracking",
    "Share of electricity for LPG cracking",
    "Share of coal for LPG cracking",
    "Share of heat for LPG cracking",
    "Share of biomass for LPG cracking",
    "Share of hydrogen for LPG cracking",
    # LPG cracking intensities
    "Energy intensity of diesel in LPG cracking",
    "Energy intensity of natural gas in LPG cracking",
    "Energy intensity of electricity in LPG cracking",
    "Energy intensity of coal in LPG cracking",
    "Energy intensity of heat in LPG cracking",
    "Energy intensity of biomass in LPG cracking",
    "Energy intensity of hydrogen in LPG cracking",
    # Methanol route shares
    "Share of diesel for Methanol route",
    "Share of natural gas for Methanol route",
    "Share of electricity for Methanol route",
    "Share of coal for Methanol route",
    "Share of heat for Methanol route",
    "Share of biomass for Methanol route",
    "Share of hydrogen for Methanol route",
    # Methanol route intensities
    "Energy intensity of diesel in Methanol route",
    "Energy intensity of natural gas in Methanol route",
    "Energy intensity of electricity in Methanol route",
    "Energy intensity of coal in Methanol route",
    "Energy intensity of heat in Methanol route",
    "Energy intensity of biomass in Methanol route",
    "Energy intensity of hydrogen in Methanol route",
    # Unspecified chemicals
    "Activity factor of unspecified chemicals",
    "Share of diesel for unspecified chemicals",
    "Share of natural gas for unspecified chemicals",
    "Share of electricity for unspecified chemicals",
    "Share of coal for unspecified chemicals",
    "Share of heat for unspecified chemicals",
    "Share of biomass for unspecified chemicals",
    "Share of hydrogen for unspecified chemicals",
    "Energy intensity of unspecified chemicals",
    
    # --- NON METALLIC MINERALS ---
    "Cement production per year",
    "Average Clinker Factor",
    "Clinker production per year",
    # Cement shares
    "Share of diesel for Cement production",
    "Share of natural gas for Cement production",
    "Share of electricity for Cement production",
    "Share of coal for Cement production",
    "Share of heat for Cement production",
    "Share of biomass for Cement production",
    "Share of hydrogen for Cement production",
    # Cement intensities
    "Energy intensity of diesel in Cement production",
    "Energy intensity of natural gas in Cement production",
    "Energy intensity of electricity in Cement production",
    "Energy intensity of coal in Cement production",
    "Energy intensity of heat in Cement production",
    "Energy intensity of biomass in Cement production",
    "Energy intensity of hydrogen in Cement production",
    # Unspecified NMM
    "Activity factor of unspecified non metallic minerals",
    "Share of diesel for unspecified non metallic minerals",
    "Share of natural gas for unspecified non metallic minerals",
    "Share of electricity for unspecified non metallic minerals",
    "Share of coal for unspecified non metallic minerals",
    "Share of heat for unspecified non metallic minerals",
    "Share of biomass for unspecified non metallic minerals",
    "Share of hydrogen for unspecified non metallic minerals",
    "Energy intensity of unspecified non metallic minerals",
    
    # --- FOOD AND TOBACCO ---
    "Activity factor of unspecified food and tobacco",
    "Share of diesel for unspecified food and tobacco",
    "Share of natural gas for unspecified food and tobacco",
    "Share of electricity for unspecified food and tobacco",
    "Share of coal for unspecified food and tobacco",
    "Share of heat for unspecified food and tobacco",
    "Share of biomass for unspecified food and tobacco",
    "Share of hydrogen for unspecified food and tobacco",
    "Energy intensity of unspecified food and tobacco",
    
    # --- CONSTRUCTION ---
    "Activity factor of unspecified construction",
    "Share of diesel for unspecified construction",
    "Share of natural gas for unspecified construction",
    "Share of electricity for unspecified construction",
    "Share of coal for unspecified construction",
    "Share of heat for unspecified construction",
    "Share of biomass for unspecified construction",
    "Share of hydrogen for unspecified construction",
    "Energy intensity of unspecified construction",
    
    # --- MINING ---
    "Activity factor of unspecified mining",
    "Share of diesel for unspecified mining",
    "Share of natural gas for unspecified mining",
    "Share of electricity for unspecified mining",
    "Share of coal for unspecified mining",
    "Share of heat for unspecified mining",
    "Share of biomass for unspecified mining",
    "Share of hydrogen for unspecified mining",
    "Energy intensity of unspecified mining",
    
    # --- MACHINERY ---
    "Activity factor of unspecified machinery",
    "Share of diesel for unspecified machinery",
    "Share of natural gas for unspecified machinery",
    "Share of electricity for unspecified machinery",
    "Share of coal for unspecified machinery",
    "Share of heat for unspecified machinery",
    "Share of biomass for unspecified machinery",
    "Share of hydrogen for unspecified machinery",
    "Energy intensity of unspecified machinery",
    
    # --- NON FERROUS METALS ---
    "Aluminium production per year",
    "Share of primary aluminium",
    "Share of secondary aluminium",
    # Primary aluminium shares
    "Share of diesel for primary aluminium production",
    "Share of natural gas for primary aluminium production",
    "Share of electricity for primary aluminium production",
    "Share of coal for primary aluminium production",
    "Share of heat for primary aluminium production",
    "Share of biomass for primary aluminium production",
    "Share of hydrogen for primary aluminium production",
    # Primary aluminium intensities
    "Energy intensity of diesel in primary aluminium production",
    "Energy intensity of natural gas in primary aluminium production",
    "Energy intensity of electricity in primary aluminium production",
    "Energy intensity of coal in primary aluminium production",
    "Energy intensity of heat in primary aluminium production",
    "Energy intensity of biomass in primary aluminium production",
    "Energy intensity of hydrogen in primary aluminium production",
    # Secondary aluminium shares
    "Share of diesel for secondary aluminium production",
    "Share of natural gas for secondary aluminium production",
    "Share of electricity for secondary aluminium production",
    "Share of coal for secondary aluminium production",
    "Share of heat for secondary aluminium production",
    "Share of biomass for secondary aluminium production",
    "Share of hydrogen for secondary aluminium production",
    # Secondary aluminium intensities
    "Energy intensity of diesel in secondary aluminium production",
    "Energy intensity of natural gas in secondary aluminium production",
    "Energy intensity of electricity in secondary aluminium production",
    "Energy intensity of coal in secondary aluminium production",
    "Energy intensity of heat in secondary aluminium production",
    "Energy intensity of biomass in secondary aluminium production",
    "Energy intensity of hydrogen in secondary aluminium production",
    # Unspecified non ferrous metals
    "Activity factor of unspecified non ferrous metals",
    "Share of diesel for unspecified non ferrous metals",
    "Share of natural gas for unspecified non ferrous metals",
    "Share of electricity for unspecified non ferrous metals",
    "Share of coal for unspecified non ferrous metals",
    "Share of heat for unspecified non ferrous metals",
    "Share of biomass for unspecified non ferrous metals",
    "Share of hydrogen for unspecified non ferrous metals",
    "Energy intensity of unspecified non ferrous metals",
    
    # --- PAPER AND PULP ---
    "Pulp production per year",
    "Share of primary pulp",
    "Share of secondary pulp",
    # Primary pulp shares
    "Share of diesel for primary pulp production",
    "Share of natural gas for primary pulp production",
    "Share of electricity for primary pulp production",
    "Share of coal for primary pulp production",
    "Share of heat for primary pulp production",
    "Share of biomass for primary pulp production",
    "Share of hydrogen for primary pulp production",
    # Primary pulp intensities
    "Energy intensity of diesel in primary pulp production",
    "Energy intensity of natural gas in primary pulp production",
    "Energy intensity of electricity in primary pulp production",
    "Energy intensity of coal in primary pulp production",
    "Energy intensity of heat in primary pulp production",
    "Energy intensity of biomass in primary pulp production",
    "Energy intensity of hydrogen in primary pulp production",
    # Secondary pulp shares
    "Share of diesel for secondary pulp production",
    "Share of natural gas for secondary pulp production",
    "Share of electricity for secondary pulp production",
    "Share of coal for secondary pulp production",
    "Share of heat for secondary pulp production",
    "Share of biomass for secondary pulp production",
    "Share of hydrogen for secondary pulp production",
    # Secondary pulp intensities
    "Energy intensity of diesel in secondary pulp production",
    "Energy intensity of natural gas in secondary pulp production",
    "Energy intensity of electricity in secondary pulp production",
    "Energy intensity of coal in secondary pulp production",
    "Energy intensity of heat in secondary pulp production",
    "Energy intensity of biomass in secondary pulp production",
    "Energy intensity of hydrogen in secondary pulp production",
    # Paper
    "Paper production per year",
    "Share of diesel for paper production",
    "Share of natural gas for paper production",
    "Share of electricity for paper production",
    "Share of coal for paper production",
    "Share of heat for paper production",
    "Share of biomass for paper production",
    "Share of hydrogen for paper production",
    # Paper intensities
    "Energy intensity of diesel in paper production",
    "Energy intensity of natural gas in paper production",
    "Energy intensity of electricity in paper production",
    "Energy intensity of coal in paper production",
    "Energy intensity of heat in paper production",
    "Energy intensity of biomass in paper production",
    "Energy intensity of hydrogen in paper production",
    # Unspecified paper and pulp
    "Activity factor of unspecified paper and pulp",
    "Share of diesel for unspecified paper and pulp",
    "Share of natural gas for unspecified paper and pulp",
    "Share of electricity for unspecified paper and pulp",
    "Share of coal for unspecified paper and pulp",
    "Share of heat for unspecified paper and pulp",
    "Share of biomass for unspecified paper and pulp",
    "Share of hydrogen for unspecified paper and pulp",
    
    # --- TRANSPORT EQUIPMENT ---
    "Share of diesel for unspecified transport equipment",
    "Share of natural gas for unspecified transport equipment",
    "Share of electricity for unspecified transport equipment",
    "Share of coal for unspecified transport equipment",
    "Share of heat for unspecified transport equipment",
    "Share of biomass for unspecified transport equipment",
    "Share of hydrogen for unspecified transport equipment",
    
    # --- TEXTILES AND LEATHER ---
    "Share of diesel for unspecified textiles and leather",
    "Share of natural gas for unspecified textiles and leather",
    "Share of electricity for unspecified textiles and leather",
    "Share of coal for unspecified textiles and leather",
    "Share of heat for unspecified textiles and leather",
    "Share of biomass for unspecified textiles and leather",
    "Share of hydrogen for unspecified textiles and leather",
    
    # --- WOOD ---
    "Share of diesel for unspecified wood",
    "Share of natural gas for unspecified wood",
    "Share of electricity for unspecified wood",
    "Share of coal for unspecified wood",
    "Share of heat for unspecified wood",
    "Share of biomass for unspecified wood",
    "Share of hydrogen for unspecified wood",
        # --- MISSING METRICS FROM build_config_industry.py ---
        "Final energy of food and tobacco",
        "Share of oil for unspecified food and tobacco",
        "Share of gas for unspecified food and tobacco",
        "Share of ammonia for unspecified food and tobacco",
        "Share of methanol for unspecified food and tobacco",
        "Share of steel for unspecified food and tobacco",
        "Final energy of construction",
        "Share of oil for unspecified construction",
        "Share of gas for unspecified construction",
        "Share of ammonia for unspecified construction",
        "Share of methanol for unspecified construction",
        "Share of steel for unspecified construction",
        "Final energy of machinery",
        "Share of oil for unspecified machinery",
        "Share of gas for unspecified machinery",
        "Share of ammonia for unspecified machinery",
        "Share of methanol for unspecified machinery",
        "Share of steel for unspecified machinery",
        "Final energy of mining and quarrying",
        "Share of oil for unspecified mining and quarrying",
        "Share of gas for unspecified mining and quarrying",
        "Share of ammonia for unspecified mining and quarrying",
        "Share of methanol for unspecified mining and quarrying",
        "Share of steel for unspecified mining and quarrying",
        "Final energy of non-ferrous metals",
        "Share of oil for unspecified non-ferrous metals",
        "Share of gas for unspecified non-ferrous metals",
        "Share of ammonia for unspecified non-ferrous metals",
        "Share of methanol for unspecified non-ferrous metals",
        "Share of steel for unspecified non-ferrous metals",
        "Final energy of textile and leather",
        "Share of oil for unspecified textile and leather",
        "Share of gas for unspecified textile and leather",
        "Share of ammonia for unspecified textile and leather",
        "Share of methanol for unspecified textile and leather",
        "Share of steel for unspecified textile and leather",
        "Final energy of transport equipment",
        "Share of oil for unspecified transport equipment",
        "Share of gas for unspecified transport equipment",
        "Share of ammonia for unspecified transport equipment",
        "Share of methanol for unspecified transport equipment",
        "Share of steel for unspecified transport equipment",
        "Final energy of wood and wood products",
        "Share of oil for unspecified wood and wood products",
        "Share of gas for unspecified wood and wood products",
        "Share of ammonia for unspecified wood and wood products",
        "Share of methanol for unspecified wood and wood products",
        "Share of steel for unspecified wood and wood products",
        # --- NAME VARIANTS USED IN build_config_industry.py ---
        "Share of diesel for blast furnaces",
        "Share of natural gas for blast furnaces",
        "Clinker-to-cement ratio",
        "Share of diesel for cement production",
        "Share of natural gas for cement production",
        "Share of electricity for cement production",
        "Share of coal for cement production",
        "Share of heat for cement production",
        "Share of biomass for cement production",
        "Share of hydrogen for cement production",
        "Energy intensity of diesel in cement production",
        "Energy intensity of natural gas in cement production",
        "Energy intensity of electricity in cement production",
        "Energy intensity of coal in cement production",
        "Energy intensity of heat in cement production",
        "Energy intensity of biomass in cement production",
        "Energy intensity of hydrogen in cement production",
        "Share of electricity for unspecified mining and quarrying",
        "Share of coal for unspecified mining and quarrying",
        "Share of biomass for unspecified mining and quarrying",
        "Share of hydrogen for unspecified mining and quarrying",
        "Share of electricity for unspecified non-ferrous metals",
        "Share of coal for unspecified non-ferrous metals",
        "Share of biomass for unspecified non-ferrous metals",
        "Share of hydrogen for unspecified non-ferrous metals",
        "Share of electricity for unspecified textile and leather",
        "Share of coal for unspecified textile and leather",
        "Share of biomass for unspecified textile and leather",
        "Share of hydrogen for unspecified textile and leather",
        "Share of electricity for unspecified wood and wood products",
        "Share of coal for unspecified wood and wood products",
        "Share of biomass for unspecified wood and wood products",
        "Share of hydrogen for unspecified wood and wood products",
    ]


def _load_metric_order_from_main_industry(default_order):
    import ast
    from pathlib import Path

    try:
        # Since this file is now in core/, go up one level to find build_config_industry.py
        main_path = Path(__file__).resolve().parent.parent / "build_config_industry.py"
        source = main_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        metric_names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name) and node.target.id == "metrics" and isinstance(node.value, ast.Dict):
                    for key in node.value.keys:
                        if isinstance(key, ast.Constant) and isinstance(key.value, str):
                            metric_names.append(key.value)
            elif isinstance(node, ast.Assign):
                targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
                if "metrics" in targets and isinstance(node.value, ast.Dict):
                    for key in node.value.keys:
                        if isinstance(key, ast.Constant) and isinstance(key.value, str):
                            metric_names.append(key.value)

        if metric_names:
            unique_order = []
            seen = set()
            for name in metric_names:
                if name not in seen:
                    seen.add(name)
                    unique_order.append(name)
            return unique_order
    except Exception:
        pass

    return default_order


def get_scenarios_from_main_industry() -> list[str]:
    return get_scenarios_from_build_config_industry()


METRIC_ORDER = _load_metric_order_from_main_industry(METRIC_ORDER)


# ============================================================================
# CONFIGURATION BUILDERS
# ============================================================================
# Functions below generate standardized configuration DataFrames for
# INDUSTRY_CONFIG.csv. These are high-level builders that take sector-specific
# data and convert it into the long-format configuration structure.
#
# Use these when building config rows for any sector (steel, ammonia, cement, etc.).
# ============================================================================


def build_fuel_share_rows(
    industry_sector: str,
    fuel_shares_dict: Dict,
    metric_label: str,
    countries: List[str],
    base_year: int,
    target_years: List[int],
    scenarios: List[str],
) -> pd.DataFrame:
    """
    Generate fuel share rows for any sector/process.
    
    Generic pattern that works for steel, ammonia, cement, etc.
    
    Args:
        industry_sector: Sector name (e.g., "iron and steel", "ammonia")
        fuel_shares_dict: Dictionary with fuel shares {fuel: {year: {scenario: value}}}
        metric_label: Technology route name (e.g., "BF+BOF", "Ammonia SMR+HB")
        countries: List of country names
        base_year: Base year
        target_years: List of target years
        scenarios: List of scenario names
    
    Returns:
        pd.DataFrame: Fuel share rows in long format with hierarchical structure
    """
    rows = []
    all_years = [base_year] + target_years
    
    for year in all_years:
        for scenario in scenarios:
            # Create one row per fuel type
            for fuel, year_data in fuel_shares_dict.items():
                if year not in year_data:
                    continue
                
                scenario_values = year_data[year]
                
                if scenario not in scenario_values:
                    continue
                
                value = scenario_values[scenario]
                
                row = {
                    'metric_1': industry_sector,  # Industry sector
                    'metric_2': 'fuel_share',  # Type
                    'metric_3': metric_label,  # Technology route
                    'metric_4': fuel,  # Fuel type
                    'year': year,
                    'scenario': scenario,
                    'units': 'share',
                }
                
                # Apply same share to all countries (technology-level data)
                for country in countries:
                    row[country] = value / 100.0  # Convert from percentage to fraction
                
                rows.append(row)
    
    return pd.DataFrame(rows)


def build_intensity_base_rows(
    industry_sector: str,
    intensity_function: Callable,
    metric_label: str,
    countries: List[str],
    base_year: int,
    scenarios: List[str],
) -> pd.DataFrame:
    """
    Generate BASE YEAR energy intensity rows for any sector/process.
    
    Generic pattern that works for steel, ammonia, cement, etc.
    Creates aggregated intensity values per route for base year only.
    Future projections are calculated separately using CAGR values from config.
    
    Args:
        industry_sector: Sector name (e.g., "iron and steel", "ammonia")
        intensity_function: Function that returns intensities (e.g., intensity_bf_bof)
        metric_label: Human-readable metric name
        countries: List of country names
        base_year: Base year (e.g., 2020)
        scenarios: List of scenario names
    
    Returns:
        pd.DataFrame: Base intensity rows (2020 only) in long format
    """
    rows = []
    
    # Get base year intensities from function
    intensities = intensity_function([base_year], scenarios)
    
    # Calculate base intensity
    # NOTE: For simplified config, all fuels have the same intensity value.
    # We take the first fuel's value instead of summing (which would be 7× too high).
    base_intensity = 0.0
    fuel_count = 0
    for fuel, year_data in intensities.items():
        if base_year in year_data:
            # Use first scenario value (base year same across scenarios)
            scenario_values = year_data[base_year]
            if scenario_values:
                first_scenario = list(scenario_values.values())[0]
                base_intensity += first_scenario
                fuel_count += 1
    
    # Average across fuels (or just take first if all same)
    if fuel_count > 0:
        base_intensity = base_intensity / fuel_count
    
    # Generate row for BASE YEAR only (same for all scenarios)
    for scenario in scenarios:
        row = {
            'metric_1': industry_sector,  # Industry sector
            'metric_2': 'intensity_base',  # Type
            'metric_3': metric_label,  # Technology route
            'metric_4': '',  # Not applicable for intensity rows
            'year': base_year,
            'scenario': scenario,
            'units': 'MWh/t',
        }
        
        # Apply same base intensity to all countries (technology-level constant)
        for country in countries:
            row[country] = base_intensity
        
        rows.append(row)
    
    return pd.DataFrame(rows)


def build_production_rows_with_cagr(
    industry_sector: str,
    metric_name: str,
    base_values: Dict[str, float],
    cagr_dict: Dict[str, Dict[str, float]],
    countries: List[str],
    base_year: int,
    target_years: List[int],
    scenarios: List[str],
    units: str = 't/year',
) -> pd.DataFrame:
    """
    Generate production rows using CAGR projection (generic pattern).
    
    Can be used for steel, ammonia, cement, etc.
    
    Args:
        industry_sector: Sector name
        metric_name: Metric name (e.g., "Steel production per year")
        base_values: Dict of {country: base_year_value}
        cagr_dict: Dict of {country: {scenario: cagr_rate}}
        countries: List of country names
        base_year: Base year
        target_years: List of target years
        scenarios: List of scenarios
        units: Units (default: 't/year')
    
    Returns:
        pd.DataFrame: Production rows
    """
    rows = []
    
    for country in countries:
        base_value = base_values.get(country, 0.0)
        country_cagr = cagr_dict.get(country, {})
        
        # Build production values
        production_dict = {}
        
        # Base year: same for all scenarios
        for scenario in scenarios:
            production_dict[(base_year, scenario)] = base_value
        
        # Future years: project using CAGR
        if base_value > 0 and country_cagr:
            for scenario in scenarios:
                cagr_rate = country_cagr.get(scenario, 0.0)
                for year in target_years:
                    years_elapsed = year - base_year
                    projected_value = base_value * ((1 + cagr_rate) ** years_elapsed)
                    production_dict[(year, scenario)] = projected_value
        else:
            for year in target_years:
                for scenario in scenarios:
                    production_dict[(year, scenario)] = 0.0
        
        # Create rows
        all_years = [base_year] + target_years
        for year in all_years:
            for scenario in scenarios:
                existing_row = None
                for r in rows:
                    if r['year'] == year and r['scenario'] == scenario:
                        existing_row = r
                        break
                
                if existing_row is None:
                    existing_row = {
                        'metric_1': industry_sector,  # Industry sector
                        'metric_2': 'production',  # Type
                        'metric_3': metric_name,  # Metric name
                        'metric_4': '',  # Not applicable for production rows
                        'year': year,
                        'scenario': scenario,
                        'units': units,
                    }
                    rows.append(existing_row)
                
                existing_row[country] = production_dict.get((year, scenario), 0.0)
    
    return pd.DataFrame(rows)


def build_cagr_rows(
    industry_sector: str,
    metric_name: str,
    cagr_dict: Dict[str, Dict[str, float]],
    countries: List[str],
    base_year: int,
    target_years: List[int],
    scenarios: List[str],
) -> pd.DataFrame:
    """
    Generate CAGR rows (generic pattern for any sector).
    
    Args:
        industry_sector: Sector name
        metric_name: Metric name
        cagr_dict: Dict of {country: {scenario: cagr_rate}}
        countries: List of country names
        base_year: Base year
        target_years: List of target years
        scenarios: List of scenarios
    
    Returns:
        pd.DataFrame: CAGR rows
    """
    rows = []
    
    # Define CAGR periods
    periods = []
    all_years = [base_year] + target_years
    for i in range(len(all_years) - 1):
        periods.append(f"{all_years[i]}-{all_years[i+1]}")
    
    for period in periods:
        for scenario in scenarios:
            row = {
                'metric_1': industry_sector,  # Industry sector
                'metric_2': 'cagr',  # Type
                'metric_3': metric_name,  # Metric name
                'metric_4': '',  # Not applicable for CAGR rows
                'year': period,
                'scenario': scenario,
                'units': 'share',
            }
            
            for country in countries:
                country_cagr = cagr_dict.get(country, {})
                row[country] = country_cagr.get(scenario, 0.0)
            
            rows.append(row)
    
    return pd.DataFrame(rows)


def build_simple_sector_fuel_share_rows(
    sector_display_name: str,
    unsd_sector_name: str,
    get_fuel_shares_func: Callable,
    countries: list[str],
    base_year: int,
    target_years: list[int],
    scenarios: list[str],
) -> pd.DataFrame:
    """
    Build fuel share rows for "simple" sectors (no production/intensity detail).
    
    Args:
        sector_display_name: Display name for metric_3 (e.g., "food and tobacco")
        unsd_sector_name: Exact UNSD sector name for data lookup (e.g., "Food and tobacco")
        get_fuel_shares_func: Function(base_path, country, year, sector_name) -> dict[fuel: share]
        countries: List of country codes
        base_year: Base year for historical data (e.g., 2020)
        target_years: Future years to project
        scenarios: List of scenario names
    
    Returns:
        DataFrame with fuel share rows in standardized format
    """
    # UNSD data is in industry/input_data/unsdata_historical/
    unsd_data_dir = INDUSTRY_DIR / "input_data" / "unsdata_historical"
    
    # Define fuel types for simple sectors (matching final energy demand output)
    fuels = ['oil', 'gas', 'electricity', 'coal', 'biomass', 'hydrogen', 'ammonia', 'methanol']
    
    # Map country codes to full names (matching file naming convention)
    country_map = {
        'MA': 'Morocco',
        'EG': 'Egypt',
        'ZA': 'South Africa',
        'NA': 'Namibia',
    }
    
    rows = []
    
    for country_code in countries:
        country_name = country_map.get(country_code, country_code)
        
        # Get base year fuel shares from UNSD
        base_shares = get_fuel_shares_func(unsd_data_dir, country_name, base_year, unsd_sector_name)
        
        # If no data found, use zeros
        if not base_shares:
            base_shares = {fuel: 0.0 for fuel in fuels}
        
        # For simple sectors, replicate base year shares across all scenarios and years
        # (no complex decarbonization pathways defined yet)
        for fuel in fuels:
            share_value = base_shares.get(fuel, 0.0) / 100.0  # Convert from percentage to fraction
            
            for year in target_years:
                for scenario in scenarios:
                    row = {
                        'metric_1': unsd_sector_name,  # UNSD sector name
                        'metric_2': 'fuel_share',  # Type
                        'metric_3': f'unspecified {sector_display_name}',  # Specific metric
                        'metric_4': fuel,  # Fuel type
                        'year': year,
                        'scenario': scenario,
                        'units': 'share',
                    }
                    
                    # Set value for this country
                    for c in countries:
                        row[c] = share_value if c == country_code else 0.0
                    
                    rows.append(row)
    
    return pd.DataFrame(rows)


# ==============================================================================
# SIMPLE SECTOR CONFIG BUILDERS (centralized for food, construction, etc.)
# ==============================================================================

def build_historical_energy_rows(
    sector_name: str,
    unsd_sector_name: str,
    countries: List[str],
    base_year: int = 2020
) -> pd.DataFrame:
    """
    Extract historical energy from UNSD and return CONFIG rows.
    
    This function provides base year energy consumption for simple sectors.
    Values are extracted from UNSD "Total Energy" column and converted:
    TJ (raw) → GWh (intermediate) → MWh (stored in CONFIG)
    
    Args:
        sector_name: Standardized sector name for CONFIG (e.g., 'food and tobacco')
        unsd_sector_name: UNSD sector name for data lookup (e.g., 'Food and tobacco')
        countries: List of country codes (e.g., ['MA', 'EG', 'ZA'])
        base_year: Base year for historical data (default: 2020)
    
    Returns:
        DataFrame with historical_energy_demand rows (one row with all countries)
    
    Example output:
        metric_1: 'food and tobacco'
        metric_2: 'historical_energy_demand'
        metric_3: 'Base year energy consumption'
        metric_4: ''
        year: 2020
        scenario: 'all'
        units: 'MWh'
        MA: 1234567
        EG: 5678901
        ...
    """
    from pathlib import Path
    
    # Get UNSD data path (centralized location)
    industry_folder = Path(__file__).parent.parent
    unsd_path = industry_folder.parent / "data" / "country_specific"
    
    # Build single row with all countries
    row = {
        'metric_1': sector_name,
        'metric_2': 'historical_energy_demand',
        'metric_3': 'Base year energy consumption',
        'metric_4': '',
        'year': base_year,
        'scenario': 'all',
        'units': 'MWh',
    }
    
    for country in countries:
        historical_data = get_historical_sector_data(unsd_path, country, unsd_sector_name)
        
        if historical_data and base_year in historical_data:
            energy_gwh = historical_data[base_year]
            energy_mwh = energy_gwh * 1000
        else:
            energy_mwh = 0.0
            print(f"  Warning: No UNSD data for {country} {unsd_sector_name} in {base_year}")
        
        row[country] = energy_mwh
    
    return pd.DataFrame([row])


def build_simple_sector_cagr_rows(
    sector_name: str,
    unsd_sector_name: str,
    countries: List[str],
    scenarios: List[str],
    scenario_multipliers: Dict[str, float] = None
) -> pd.DataFrame:
    """
    Calculate CAGR from UNSD historical trends and return CONFIG rows.
    
    Uses centralized CAGR calculator with IQR outlier capping and applies
    scenario-specific multipliers for activity growth projections.
    
    Args:
        sector_name: Standardized sector name for CONFIG
        unsd_sector_name: UNSD sector name for data lookup
        countries: List of country codes
        scenarios: List of scenario names (e.g., ['BAU', 'Progressive', 'Optimistic'])
        scenario_multipliers: Optional dict of {scenario: multiplier}
    
    Returns:
        DataFrame with cagr rows (3 rows × N countries for 3 scenarios)
    
    Scenario Multipliers (default):
        BAU: 1.0× - Historical trend continues
        Progressive: 1.2× - 20% activity acceleration
        Optimistic: 1.5× - 50% activity acceleration
    
    Example output:
        metric_1: 'food and tobacco'
        metric_2: 'cagr'
        metric_3: 'Activity growth rate'
        metric_4: ''
        year: '2020-2050'
        scenario: 'BAU' / 'Progressive' / 'Optimistic'
        units: 'share'
        MA: 0.023
        EG: 0.031
        ...
    """
    from industry.utils.cagr_calculator import get_final_energy_cagr_from_unsd
    
    if scenario_multipliers is None:
        scenario_multipliers = {
            'BAU': 1.0,
            'Progressive': 1.2,
            'Optimistic': 1.5,
        }
    
    rows = []
    
    for scenario in scenarios:
        multiplier = scenario_multipliers.get(scenario, 1.0)
        
        row = {
            'metric_1': sector_name,
            'metric_2': 'cagr',
            'metric_3': 'Activity growth rate',
            'metric_4': '',
            'year': '2020-2050',
            'scenario': scenario,
            'units': 'share',
        }
        
        for country in countries:
            base_cagr = get_final_energy_cagr_from_unsd(country, unsd_sector_name)
            adjusted_cagr = base_cagr * multiplier
            row[country] = adjusted_cagr
        
        rows.append(row)
    
    return pd.DataFrame(rows)


def build_simple_sector_fuel_share_rows_from_unsd(
    sector_name: str,
    unsd_sector_name: str,
    countries: List[str],
    base_year: int,
    target_years: List[int],
    scenarios: List[str],
) -> pd.DataFrame:
    """
    Build fuel share rows for simple sectors using UNSD base year data.
    
    METHODOLOGY:
    - Extracts fuel mix from UNSD 2020 data (actual historical shares)
    - Applies shares CONSTANT across all future years (no transformation)
    - All scenarios use same fuel shares (conservative baseline)
    
    TODO: Enhance with transformation logic
    - Add scenario-specific fuel transitions (electrification, hydrogen adoption)
    - Implement interpolation between anchor years (2020 → 2030 → 2050)
    - Consider technology diffusion models (S-curves for new carriers)
    - Align with IEA/IRENA decarbonization pathways
    
    Potential transformation approaches:
    1. Linear interpolation with expert target shares (2030, 2050)
    2. Exponential decay for fossil fuels, logistic growth for renewables
    3. Technology diffusion models (Bass model, Fisher-Pry substitution)
    4. Pathway alignment (match IEA NZE or IRENA 1.5°C scenarios)
    
    Args:
        sector_name: Standardized sector name for CONFIG
        unsd_sector_name: UNSD sector name for data lookup
        countries: List of country codes
        base_year: Base year for fuel share extraction (default: 2020)
        target_years: Future years to project (e.g., [2030, 2035, 2040, 2045, 2050])
        scenarios: List of scenario names
    
    Returns:
        DataFrame with fuel_share rows (N fuels × M scenarios × P years × Q countries)
    
    Note: Currently shares are CONSTANT (2020 values used for all years).
          This is a conservative baseline pending transformation methodology.
    """
    import pandas as pd
    from pathlib import Path
    
    # Import _clean_val for UNSD data cleaning
    try:
        from industry.scripts.food_and_tobacco.build_food_and_tobacco_energy import _clean_val
    except:
        # Fallback if import fails
        def _clean_val(val):
            try:
                s_val = str(val).strip()
                if pd.isna(val) or s_val == "---" or s_val == "":
                    return 0.0
                clean_s = s_val.replace('*', '').replace('-', '')
                return float(clean_s) if clean_s else 0.0
            except:
                return 0.0
    
    # Get UNSD data path
    industry_folder = Path(__file__).parent.parent
    unsd_path = industry_folder.parent / "data" / "country_specific"
    
    # Fuel mapping from UNSD columns to carrier names
    fuel_mapping = {
        'oil': ['Primary Oil', 'Oil Products'],
        'gas': ['Natural Gas'],
        'electricity': ['Nuclear', 'Electricity'],
        'coal': ['Primary Coal and Peat', 'Coal and Peat Products'],
        'biomass': ['Biofuels and Waste'],
        'hydrogen': [],  # Future carrier, not in UNSD
        'ammonia': [],   # Future carrier, not in UNSD
        'methanol': [],  # Future carrier, not in UNSD
        'steel': [],     # Endogenous carrier, not in UNSD
    }
    
    rows = []
    
    for country in countries:
        # Extract base year fuel shares from UNSD
        base_shares = {}
        
        # Try to find UNSD file for base year
        file_path = unsd_path / f"UNSD_{country}-{base_year}.csv"
        
        if file_path.exists():
            try:
                df = pd.read_csv(file_path)
                sector_col = "Transactions(down)/Commodity(right)"
                
                # Find sector row
                if sector_col in df.columns and "Total Energy" in df.columns:
                    row_data = df[df[sector_col].astype(str).str.strip().str.lower() == unsd_sector_name.lower()]
                    
                    if not row_data.empty:
                        total_tj = _clean_val(row_data["Total Energy"].iloc[0])
                        
                        if total_tj > 0:
                            # Extract fuel values and calculate shares
                            for fuel, columns in fuel_mapping.items():
                                fuel_sum = sum([_clean_val(row_data[col].iloc[0]) 
                                              for col in columns if col in df.columns])
                                share = fuel_sum / total_tj if total_tj > 0 else 0.0
                                base_shares[fuel] = share
                        else:
                            # No energy data - use default shares
                            base_shares = _get_default_fuel_shares()
                    else:
                        # Sector not found - use default shares
                        base_shares = _get_default_fuel_shares()
                else:
                    # Malformed file - use defaults
                    base_shares = _get_default_fuel_shares()
                    
            except Exception as e:
                print(f"  Warning: Error reading UNSD for {country}: {e}")
                base_shares = _get_default_fuel_shares()
        else:
            print(f"  Warning: No UNSD file for {country} {base_year}")
            base_shares = _get_default_fuel_shares()
        
        # Normalize shares to sum to 1.0
        total_share = sum(base_shares.values())
        if total_share > 0:
            base_shares = {f: v / total_share for f, v in base_shares.items()}
        else:
            base_shares = _get_default_fuel_shares()
        
        # Apply shares to all years and scenarios (CONSTANT - no transformation)
        for scenario in scenarios:
            for year in target_years:
                for fuel, share_value in base_shares.items():
                    if share_value > 0:  # Only add non-zero shares
                        rows.append({
                            'metric_1': sector_name,
                            'metric_2': 'fuel_share',
                            'metric_3': f'unspecified {sector_name}',
                            'metric_4': fuel,
                            'year': year,
                            'scenario': scenario,
                            'units': 'share',
                            country: share_value
                        })
    
    return pd.DataFrame(rows)


def _get_default_fuel_shares() -> Dict[str, float]:
    """Return default fuel shares for simple sectors when UNSD data unavailable."""
    return {
        'oil': 0.4,
        'gas': 0.25,
        'electricity': 0.2,
        'coal': 0.15,
        'biomass': 0.0,
        'hydrogen': 0.0,
        'ammonia': 0.0,
        'methanol': 0.0,
        'steel': 0.0,
    }
