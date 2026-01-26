# helpers.py

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
    Chained CAGR logic with interpolation between anchors.

    For each scenario:
      - We have anchor CAGRs, e.g. {2030: r_2030, 2050: r_2050}.
      - First compute values at all anchor years *sequentially*:
          v(2030) = base * (1 + r_2030)^(2030 - base_year)
          v(2050) = v(2030) * (1 + r_2050)^(2050 - 2030)
      - Then for any target year Y:
          * If Y == anchor year → use that anchor value.
          * If between two anchors → linearly interpolate between
            the two anchor VALUES (not the rates).
          * If before first anchor → use first anchor CAGR from base.
          * If after last anchor → extend last anchor CAGR beyond last anchor.
    """
    result: Dict[str, float] = {}

    if not target_years:
        return result

    target_years_sorted = sorted(set(int(y) for y in target_years))

    for sc in scenarios:
        anchors = sc_anchors.get(sc, {}) or {}
        # list of (year, rate) sorted by year
        anchor_items = sorted((int(y), float(r)) for y, r in anchors.items())

        # always store values at years here
        values: Dict[int, float] = {int(last_obs_year): float(last_obs_val)}

        # === 1. Compute values at anchor years sequentially (chained growth) ===
        if anchor_items:
            prev_year = int(last_obs_year)
            prev_val  = float(last_obs_val)

            for y_anchor, r_anchor in anchor_items:
                if y_anchor <= prev_year:
                    continue
                years_diff = y_anchor - prev_year
                v_anchor = prev_val * ((1.0 + r_anchor) ** years_diff)
                values[y_anchor] = v_anchor
                prev_year, prev_val = y_anchor, v_anchor

        # convenience variables
        anchor_years = sorted(y for y in values.keys() if y != last_obs_year)
        first_anchor_year = anchor_years[0] if anchor_years else None
        last_anchor_year  = anchor_years[-1] if anchor_years else None
        last_anchor_rate  = (
            anchor_items[-1][1] if anchor_items else 0.0
        )

        for Y in target_years_sorted:
            if Y <= last_obs_year:
                continue

            # exact anchor/base value
            if Y in values:
                val_Y = values[Y]

            else:
                # no anchors at all → no growth (flat)
                if not anchor_items:
                    val_Y = float(last_obs_val)

                # before first anchor → use first anchor CAGR from base
                elif first_anchor_year is not None and Y < first_anchor_year:
                    r_first = anchor_items[0][1]
                    years_diff = Y - last_obs_year
                    val_Y = float(last_obs_val) * ((1.0 + r_first) ** years_diff)

                # after last anchor → extend last anchor CAGR from last anchor value
                elif last_anchor_year is not None and Y > last_anchor_year:
                    v_last = values[last_anchor_year]
                    years_diff = Y - last_anchor_year
                    val_Y = v_last * ((1.0 + last_anchor_rate) ** years_diff)

                else:
                    # between two anchors → interpolate between anchor VALUES
                    # find previous and next anchor around Y
                    prev_y = None
                    next_y = None
                    for y in sorted(anchor_years):
                        if y <= Y:
                            prev_y = y
                        if y >= Y:
                            next_y = y
                            break

                    # safety fallback
                    if prev_y is None:
                        prev_y = first_anchor_year
                    if next_y is None:
                        next_y = last_anchor_year

                    v_prev = values[prev_y]
                    v_next = values[next_y]
                    if next_y == prev_y:
                        val_Y = v_prev
                    else:
                        frac = (Y - prev_y) / (next_y - prev_y)
                        val_Y = v_prev + (v_next - v_prev) * frac

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
