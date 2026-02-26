#build_CAGR.py

import pandas as pd
import numpy as np
import os
import glob

# === Step 0: Helper to find Excel ===
def find_excel_file(base_dir=None, file_pattern="CAGR_compilation_*.xlsx"):
    if base_dir is None:
        base_dir = os.getcwd()
    search_pattern = os.path.join(base_dir, "**", file_pattern)
    matching_files = glob.glob(search_pattern, recursive=True)

    if not matching_files:
        raise FileNotFoundError(f"No file found matching {file_pattern} in {base_dir}")
    if len(matching_files) > 1:
        raise ValueError(f"Multiple files found: {matching_files}")

    return matching_files[0]


# === Step 1: Load Excel ===
try:
    file_path = find_excel_file(file_pattern="CAGR_compilation_*.xlsx")
    #print(f"Found Excel file: {file_path}")
    df = pd.read_excel(file_path, header=0)
except Exception as e:
    #print(f" Could not read Excel: {e}")
    df = pd.DataFrame()

# === Step 2: Clean columns ===
column_mapping = {
    'Source:': 'Subsector',
    'Unnamed: 1': 'Submode',
    'Unnamed: 2': 'Drive',
    'Unnamed: 3': 'Unit',
    'ISI': 'CAGR_2030_ISI',
    'Unnamed: 5': 'CAGR_2040_ISI',
    'Unnamed: 6': 'CAGR_2050_ISI',
    'Khalili': 'CAGR_2030_Khalili',
    'Unnamed: 8': 'CAGR_2040_Khalili',
    'Unnamed: 9': 'CAGR_2050_Khalili',
    'IEE': 'CAGR_2030_IEE',
    'Unnamed: 11': 'CAGR_2040_IEE',
    'Unnamed: 12': 'CAGR_2050_IEE',
}
df = df.rename(columns=column_mapping)

# Convert percentage strings → numeric
for col in df.columns:
    if col.startswith("CAGR_"):
        df[col] = df[col].apply(lambda x: float(x.strip('%'))/100 if isinstance(x, str) and '%' in x else x)
        df[col] = pd.to_numeric(df[col], errors="coerce")


# === Step 3: Compute min/avg/max CAGR ===
def compute_bandwidth_cagr(df, selected_sources):
    id_columns = ['Subsector', 'Submode', 'Drive', 'Unit']
    result = df[id_columns].copy()

    for year in ['2030', '2050']:
        cagr_cols = [f"CAGR_{year}_{src}" for src in selected_sources if f"CAGR_{year}_{src}" in df.columns]
        if cagr_cols:
            result[f"MIN_{year}"] = df[cagr_cols].min(axis=1)
            result[f"AVG_{year}"] = df[cagr_cols].mean(axis=1)
            result[f"MAX_{year}"] = df[cagr_cols].max(axis=1)
        else:
            result[f"MIN_{year}"] = np.nan
            result[f"AVG_{year}"] = np.nan
            result[f"MAX_{year}"] = np.nan

    return result


selected_sources = ["IEE", "ISI", "Khalili"]
try:
    result_df = compute_bandwidth_cagr(df, selected_sources)
except Exception as e:
    #print(f" Could not compute CAGR: {e}")
    result_df = pd.DataFrame()


# === Step 4: Mapping (Excel → metric names) ===
METRIC_NAME_MAP = {
    ("Cars", "Passenger", "Gasoline"): "Final Energy Intensity - Gasoline ICE LDV",
    ("Cars", "Passenger", "Diesel"): "Final Energy Intensity - Diesel ICE LDV",
    ("Cars", "Passenger", "LPG"): "Final Energy Intensity - LPG ICE LDV",
    ("Cars", "Passenger", "BEV"): "Final Energy Intensity - BEV LDV",
    ("Cars", "Passenger", "FCEV"): "Final Energy Intensity - FCEV LDV",
    ("Cars", "Passenger", "Efficiency PHEV (ICE)"): "Final Energy Intensity - Diesel Plugin Hybrid LDV",
    ("Cars", "Passenger", "Efficiency PHEV (BEV)"): "Final Energy Intensity - Gasoline Plugin Hybrid LDV",

    # === Passenger Bus ===
    ("BUS", "Passenger", "Diesel"): "Final Energy Intensity - Diesel ICE Bus",
    ("BUS", "Passenger", "BEV"): "Final Energy Intensity - BEV Bus",
    ("BUS", "Passenger", "FCEV"): "Final Energy Intensity - FCEV Bus",
    ("BUS", "Passenger", "Efficiency PHEV (ICE)"): "Final Energy Intensity - Diesel Plugin Hybrid Bus",
    # ( No "Gasoline Plugin Hybrid Bus" in your final list → excluded)

    # === Passenger 2&3 Wheelers ===
    ("Cars", "Passenger", "2&3W Gasoline"): "Final Energy Intensity - Gasoline ICE 2&3W",
    ("Cars", "Passenger", "2&3W BEV"): "Final Energy Intensity - BEV 2&3W",

    # === Aviation (Passenger only) ===
    ("Aviation national (short flights)", "Passenger", "Kerosine"): "Final Energy Intensity - Kerosene Passenger Plane",
    ("Aviation national (short flights)", "Passenger", "BEV"): "Final Energy Intensity - BEV Passenger Plane",
    ("Aviation national (short flights)", "Passenger", "FCEV"): "Final Energy Intensity - FCEV Passenger Plane",
    ("Aviation international (long flights)", "Passenger", "Kerosine"): "Final Energy Intensity - Kerosene Passenger Plane",
    ("Aviation international (long flights)", "Passenger", "BEV"): "Final Energy Intensity - BEV Passenger Plane",
    ("Aviation international (long flights)", "Passenger", "FCEV"): "Final Energy Intensity - FCEV Passenger Plane",
    # ( Freight planes excluded — not in your final list)

    # === Passenger Rail ===
    ("Rail", "Passenger", "Diesel"): "Final Energy Intensity - Diesel ICE Passenger Train",
    ("Rail", "Passenger", "Electric (incl. BEV)"): "Final Energy Intensity - Direct Electric Passenger Train",
    ("Rail", "Passenger", "FCEV"): "Final Energy Intensity - FCEV Passenger Train",

    # === Freight Rail ===
    ("Rail", "Freight", "Diesel"): "Final Energy Intensity - Diesel ICE Freight Train",
    ("Rail", "Freight", "Electric (incl. BEV)"): "Final Energy Intensity - Direct Electric Freight Train",
    ("Rail", "Freight", "FCEV"): "Final Energy Intensity - FCEV Freight Train",

    # === Freight LDT (<3.5t) ===
    ("Heavy duty vehicles <3.5t", "Freight", "Diesel"): "Final Energy Intensity - Diesel ICE LDT",
    ("Heavy duty vehicles <3.5t", "Freight", "BEV"): "Final Energy Intensity - BEV LDT",
    ("Heavy duty vehicles <3.5t", "Freight", "FCEV"): "Final Energy Intensity - FCEV LDT",
    ("Heavy duty vehicles <3.5t", "Freight", "Efficiency PHEV (ICE)"): "Final Energy Intensity - Diesel Plugin Hybrid LDT",
    # ( No Gasoline Plugin Hybrid LDT in your final list)

    # === Freight HDT (3.5t+) ===
    ("Heavy duty vehicles 3.5-7.5t", "Freight", "Diesel"): "Final Energy Intensity - Diesel ICE HDT",
    ("Heavy duty vehicles 3.5-7.5t", "Freight", "BEV"): "Final Energy Intensity - BEV HDT",
    ("Heavy duty vehicles 3.5-7.5t", "Freight", "FCEV"): "Final Energy Intensity - FCEV HDT",

    ("Heavy duty vehicles 7.5-12t", "Freight", "Diesel"): "Final Energy Intensity - Diesel ICE HDT",
    ("Heavy duty vehicles 7.5-12t", "Freight", "BEV"): "Final Energy Intensity - BEV HDT",
    ("Heavy duty vehicles 7.5-12t", "Freight", "FCEV"): "Final Energy Intensity - FCEV HDT",

    ("Heavy duty vehicles >12t", "Freight", "Diesel"): "Final Energy Intensity - Diesel ICE HDT",
    ("Heavy duty vehicles >12t", "Freight", "BEV"): "Final Energy Intensity - BEV HDT",
    ("Heavy duty vehicles >12t", "Freight", "FCEV"): "Final Energy Intensity - FCEV HDT",
    ("Heavy duty vehicles >12t", "Freight", "Efficiency PHEV (ICE)"): "Final Energy Intensity - Diesel Plugin Hybrid HDT",
    # ( No Gasoline Plugin Hybrid HDT in your final list)

    ("Heavy duty vehicles SZM", "Freight", "Diesel"): "Final Energy Intensity - Diesel ICE HDT",
    ("Heavy duty vehicles SZM", "Freight", "BEV"): "Final Energy Intensity - BEV HDT",
    ("Heavy duty vehicles SZM", "Freight", "FCEV"): "Final Energy Intensity - FCEV HDT",

    # === Freight Shipping ===
    ("Inland shipping", "-", "Combustion"): "Final Energy Intensity - Diesel Freight Ship",
    ("Inland shipping", "-", "FCEV"): "Final Energy Intensity - FCEV Freight Ship",
    ("International shipping", "-", "Combustion (incl. novel fuels)"): "Final Energy Intensity - Diesel Freight Ship",
    ("International shipping", "-", "FCEV"): "Final Energy Intensity - FCEV Freight Ship",

    # Extra alternative fuels for ships
    ("International shipping", "-", "Methanol"): "Final Energy Intensity - Methanol Freight Ship",
    ("International shipping", "-", "Ammonia"): "Final Energy Intensity - Ammonia Freight Ship",
    ("International shipping", "-", "BEV"): "Final Energy Intensity - BEV Freight Ship",
}


# === Step 5: Build CAGR_VALUES ===
def normalize_tuple(subsector, submode, drive):
    """
    Normalize (subsector, submode, drive) to match METRIC_NAME_MAP keys.
    Makes matching robust against variations like capitalization, spacing,
    and prefixes like 'Efficiency', 'Passenger', 'Freight', etc.
    """
    s = subsector.strip().lower()
    m = submode.strip().lower()
    d = drive.strip().lower()

    # --- Normalize subsector names ---
    if "car" in s or "ldv" in s:
        subsector = "Cars"
    elif "bus" in s:
        subsector = "BUS"
    elif "2" in s and "3" in s:
        subsector = "Cars"
        d = "2&3W " + d
    elif "rail" in s or "train" in s:
        subsector = "Rail"
    elif "aviation" in s or "plane" in s or "flight" in s:
        if "international" in s or "long" in s:
            subsector = "Aviation international (long flights)"
        else:
            subsector = "Aviation national (short flights)"
    elif "shipping" in s or "ship" in s:
        if "international" in s:
            subsector = "International shipping"
        else:
            subsector = "Inland shipping"
    elif "heavy" in s and "<" in s:
        subsector = "Heavy duty vehicles <3.5t"
    elif "heavy" in s and ">" in s:
        subsector = "Heavy duty vehicles >12t"
    elif "heavy" in s and "3.5" in s:
        subsector = "Heavy duty vehicles 3.5-7.5t"
    elif "hdt" in s or "truck" in s:
        subsector = "Heavy duty vehicles >12t"

    # --- Normalize submode (Passenger / Freight) ---
    if "passenger" in m:
        submode = "Passenger"
    elif "freight" in m or "goods" in m:
        submode = "Freight"
    else:
        submode = "-"

    # --- Normalize drive types ---
    d = d.replace("efficiency", "").strip()
    d = d.replace("(bev)", "bev").replace("(ice)", "ice")
    d = d.replace("phevbev", "Efficiency PHEV (BEV)")
    d = d.replace("phevice", "Efficiency PHEV (ICE)")

    if "phev" in d and "bev" not in d and "ice" not in d:
        drive = "Efficiency PHEV (BEV)"
    elif "phev" in d and "ice" in d:
        drive = "Efficiency PHEV (ICE)"
    elif "phev" in d:
        drive = "Efficiency PHEV (BEV)"
    elif "bev" in d:
        drive = "BEV"
    elif "fcev" in d or "h2" in d or "fuel" in d:
        drive = "FCEV"
    elif "diesel" in d:
        drive = "Diesel"
    elif "gasoline" in d or "petrol" in d:
        drive = "Gasoline"
    elif "keros" in d:
        drive = "Kerosine"
    elif "lpg" in d:
        drive = "LPG"
    elif "combustion" in d:
        drive = "Combustion"
    elif "electric" in d:
        drive = "Electric (incl. BEV)"
    elif "methanol" in d:
        drive = "Methanol"
    elif "ammonia" in d:
        drive = "Ammonia"
    else:
        drive = drive.strip().capitalize()

    return subsector, submode, drive




def build_cagr_values(result_df, base_values, base_year=2020):
    values = {}
    matched = 0
    unmatched = 0

    for _, row in result_df.iterrows():
        subsector, submode, drive = normalize_tuple(
            str(row["Subsector"]), str(row["Submode"]), str(row["Drive"])
        )
        key = METRIC_NAME_MAP.get((subsector, submode, drive))
        if key is None:
            unmatched += 1
            continue

        # Skip rows with no valid CAGR data
        if all(pd.isna(row.get(c)) for c in ["AVG_2030", "AVG_2050"]):
            continue

        matched += 1
        base = None
        if key in base_values and isinstance(base_values[key], dict):
            base = base_values[key].get(str(base_year))

        def safe_float(x):
            try:
                return float(str(x).replace("%", "")) / 100.0
            except Exception:
                return 0.0

        # Build final structure cleanly
        values[key] = {
            str(base_year): base,
            2030: {
                "Baseline": safe_float(row.get("AVG_2030")),
                "RF": safe_float(row.get("MIN_2030")),
                "EL": safe_float(row.get("MAX_2030")),
            },
            2050: {
                "Baseline": safe_float(row.get("AVG_2050")),
                "RF": safe_float(row.get("MIN_2050")),
                "EL": safe_float(row.get("MAX_2050")),
            },
        }

    #print(f" build_cagr_values matched {matched} metrics, skipped {unmatched}.")
    return values


try:
    from helpers import load_expert_config
    BASE_VALUES = load_expert_config()   # <-- NO ARGUMENTS NOW
except Exception as e:
    #print(f" Could not load base values from YAML: {e}")
    BASE_VALUES = {}


try:
    CAGR_VALUES = build_cagr_values(result_df, BASE_VALUES, base_year=2020)
except Exception:
    CAGR_VALUES = {}


#print(f" build_cagr_values produced {len(CAGR_VALUES)} entries")
#if not CAGR_VALUES:
    #print(" No metrics were matched. Check METRIC_NAME_MAP or BASE_VALUES[2020].")



# === Step 7: Export functions for loader ===
def expand_with_cagr_from_base(base_value, cagr_dict):
    out = {"2020": base_value}
    out["2030_Baseline"] = base_value * (1 + cagr_dict["2030_Baseline"]) ** 10
    out["2030_RF"]       = base_value * (1 + cagr_dict["2030_RF"]) ** 10
    out["2030_EL"]       = base_value * (1 + cagr_dict["2030_EL"]) ** 10
    out["2050_Baseline"] = out["2030_Baseline"] * (1 + cagr_dict["2050_Baseline"]) ** 20
    out["2050_RF"]       = out["2030_RF"]       * (1 + cagr_dict["2050_RF"]) ** 20
    out["2050_EL"]       = out["2030_EL"]       * (1 + cagr_dict["2050_EL"]) ** 20
    return out


def expand_intensity_with_cagr(base_value, cagr_dict):
    return expand_with_cagr_from_base(base_value, cagr_dict)


def expand_constant(value):
    return {
        "2020": value,
        "2030_Baseline": value,
        "2030_RF": value,
        "2030_EL": value,
        "2050_Baseline": value,
        "2050_RF": value,
        "2050_EL": value,
    }


# --- Polynomial regression for projections ---
def poly_project(years, values, target_years, degree=2):
    """
    years: list of years (should be numeric like 2005, 2010...)
    values: list of values
    target_years: list of years we want to predict
    """
    try:
        # Filter out non-numeric year labels
        clean = [(float(y), v) for y, v in zip(years, values)
                 if str(y).replace(".", "").isdigit() and pd.notna(v)]
        if not clean:
            return {int(t): np.nan for t in target_years}

        years, values = zip(*clean)
        years = np.array(years, dtype=float)
        values = np.array(values, dtype=float)

        # Fit polynomial
        deg = min(int(degree), max(0, len(years) - 1))
        if deg == 0:
            const = float(np.nanmedian(values))
            return {int(t): const for t in target_years}

        coeffs = np.polyfit(years, values, deg)
        poly = np.poly1d(coeffs)

        return {int(t): max(0.0, float(poly(t))) for t in target_years}

    except Exception as e:
        print(f"Polynomial projection error: {e}")
        return {t: np.nan for t in target_years}
# --- Expansion functions ---
def expand_with_cagr(base_value, cagr_table, base_year, target_years, scenarios):
    """
    Expand base_value across target_years using piecewise CAGRs.
    Scenario names come directly from SCENARIOS.
    """
    out = {str(base_year): base_value}
    milestones = sorted(int(k) for k in cagr_table.keys())

    def rate_for(scenario, milestone):
        # try exact scenario name first
        if scenario in cagr_table[milestone]:
            return cagr_table[milestone][scenario]
        # else fall back to Baseline/default
        return (
            cagr_table[milestone].get("Baseline")
            or cagr_table[milestone].get("default", 0.0)
        )

    def value_at(year, scenario):
        v = base_value
        last = base_year
        for m in milestones:
            r = float(rate_for(scenario, m))
            if year <= m:
                return v * (1 + r) ** (year - last)
            v = v * (1 + r) ** (m - last)
            last = m
        # beyond last milestone → continue with last rate
        r_last = float(rate_for(scenario, milestones[-1]))
        return v * (1 + r_last) ** (year - last)

    for y in target_years:
        for s in scenarios:
            out[f"{y}_{s}"] = value_at(int(y), s)

    return out


def expand_constant(value, base_year=2020, target_years=(2030,2050), scenarios=("Baseline","RF","EL")):
    return {
        str(base_year): value,
        **{f"{year}_{scenario}": value for year in target_years for scenario in scenarios}
    }

def expand_intensity_with_cagr_excel(base_value, cagr_dict, base_year, target_years, scenarios):
    """Excel-style CAGR expansion"""
    results = {str(base_year): base_value}
    prev_year = base_year
    prev_values = {s: base_value for s in scenarios}

    for year in sorted(target_years):
        for scenario in scenarios:
            cagr = cagr_dict.get(f"{year}_{scenario}", cagr_dict.get(scenario, 0.0))
            if cagr is None:
                cagr = 0.0
            fv = prev_values[scenario] * (1 + cagr) ** (year - prev_year)
            results[f"{year}_{scenario}"] = fv
        prev_year = year
        prev_values = {s: results[f"{year}_{s}"] for s in scenarios}
    return results


def tuple_to_cagr_dict(tup):
    return {
        2030: {"Baseline": tup[0], "RF": tup[1], "EL": tup[2]},
        2050: {"Baseline": tup[3], "RF": tup[4], "EL": tup[5]},
    }

import pandas as pd

def expand_with_piecewise_cagr(base_value, cagr_dict, base_year=2020, target_years=[2030, 2050, 2055]):
    """
    Expands base_value using CAGR rates from a YAML dictionary.
    - Interpolates between known years (e.g., 2030–2050 → 2035, 2045)
    - Extrapolates beyond last known year (e.g., 2055 uses 2050 CAGR)
    """
    import pandas as pd

    if base_value in [None] or pd.isna(base_value):
        base_value = 1.0

    out = {str(base_year): round(float(base_value), 6)}

    available_years = sorted(int(y) for y in cagr_dict.keys() if str(y).isdigit())

    for y in target_years:
        year = int(y)
        # find the bounding years
        prev_years = [yr for yr in available_years if yr <= year]
        next_years = [yr for yr in available_years if yr >= year]

        # if below first known year → use first CAGR
        if not prev_years:
            y1 = available_years[0]
            year_data = cagr_dict.get(y1, {})
        # if beyond last known year → use last CAGR (extrapolate)
        elif not next_years:
            y1 = available_years[-1]
            year_data = cagr_dict.get(y1, {})
        # normal interpolation
        else:
            y1 = max(prev_years)
            y2 = min(next_years)
            factor = 0 if y1 == y2 else (year - y1) / (y2 - y1)
            year_data1 = cagr_dict.get(y1, {})
            year_data2 = cagr_dict.get(y2, {})

            year_data = {}
            for scenario in set(year_data1.keys()) | set(year_data2.keys()):
                c1 = year_data1.get(scenario, 0)
                c2 = year_data2.get(scenario, c1)
                if abs(c1) > 0.5: c1 /= 100
                if abs(c2) > 0.5: c2 /= 100
                year_data[scenario] = c1 + (c2 - c1) * factor

        # apply CAGR for each scenario
        for scenario, cagr in year_data.items():
            try:
                if abs(cagr) > 0.5:  # handle percentages
                    cagr /= 100.0
                years_diff = year - base_year
                value = float(base_value) * ((1 + float(cagr)) ** years_diff)
                out[f"{year}_{scenario}"] = round(value, 6)
            except Exception:
                out[f"{year}_{scenario}"] = round(float(base_value), 6)

    return out


def as_fraction(val):
    """
    Converts percentage to fraction safely.
    Example: 2.5 -> 0.025, 0.05 -> 0.05
    Returns 0.0 if empty (safest for CAGR math).
    """
    if pd.isnull(val):
        return 0.0
    try:
        val = float(val)
        # If value is > 1.0 (e.g. 1.5 or 50), assume it's a percentage (1.5% or 50%)
        # and divide by 100.
        if abs(val) > 1.0:  
            return val / 100.0
        return val
    except Exception:
        return 0.0

def get_cagr(cagr_values, metric):
    entry = cagr_values.get(metric)
    if entry is None:
        raise KeyError(f"CAGR not found for metric: {metric}")
    if entry.get("assumption_type") != "CAGR":
        raise ValueError(f"{metric} is not CAGR-based")
    return entry["values"]



def get_cagr(cagr_values, metric):
    """
    Retrieves the CAGR value dictionary for a specific metric.
    Expects cagr_values to be a dictionary where keys are metric names.
    """
    if not isinstance(cagr_values, dict):
        raise ValueError("cagr_values must be a dictionary.")
        
    entry = cagr_values.get(metric)
    
    if entry is None:
        # It's better to return an empty dict than crash, 
        # allowing the calling function to handle the default fallback.
        return {}
    
    # Handle structure: {'assumption_type': 'CAGR', 'values': {2030: ...}}
    if isinstance(entry, dict) and "values" in entry:
        return entry["values"]
    
    # Handle flat structure: {2030: ...}
    return entry

def expand_with_cagr(base_value, cagr_table, base_year, target_years, scenarios):
    """
    Expands a base value into future years using piecewise CAGRs.
    
    CRITICAL LOGIC:
    1. If the config has a rate for Year X, that rate applies to the period 
       ending at Year X (from the previous milestone).
    2. If a target year (e.g. 2035) exists in the config, we use that specific rate.
    3. If a target year is MISSING from config, we find the NEXT available milestone 
       and use its rate (effectively interpolating the growth trend).
    """
    if base_value is None:
        base_value = 0.0
        
    out = {str(base_year): float(base_value)}
    
    # 1. Gather all milestones defined in the Excel config (e.g. 2030, 2035, 2040, 2050)
    config_milestones = sorted([int(k) for k in cagr_table.keys() if str(k).isdigit()])
    
    if not config_milestones:
        # No CAGR data? Return constant base value for all years
        for y in target_years:
            for s in scenarios:
                out[f"{y}_{s}"] = float(base_value)
        return out

    def get_rate(year, scenario):
        """Helper to get rate for a specific milestone year and scenario."""
        if year not in cagr_table:
            return 0.0
        yr_data = cagr_table[year]
        
        # Priority: Specific Scenario -> Default/Baseline -> First Available
        if scenario in yr_data: return as_fraction(yr_data[scenario])
        if "default" in yr_data: return as_fraction(yr_data["default"])
        if "Baseline" in yr_data: return as_fraction(yr_data["Baseline"])
        if len(yr_data) > 0: return as_fraction(list(yr_data.values())[0])
        return 0.0

    # Calculate for each scenario independently
    for scenario in scenarios:
        current_value = float(base_value)
        current_year = int(base_year)
        
        # 2. Build the full timeline of years we need to hit
        # We merge the config milestones with the requested target years
        # Example: Config has [2030, 2050]. Target is [2030, 2035, 2040, 2050].
        # Timeline becomes: 2020 -> 2030 -> 2035 -> 2040 -> 2050
        timeline = sorted(list(set(target_years) | set(config_milestones)))
        
        # Filter out years before base year
        timeline = [t for t in timeline if t > current_year]

        # Iterate through time
        for t_year in timeline:
            # 3. Determine which rate applies to this segment (current_year -> t_year)
            
            # CASE A: If t_year is explicitly in the config, use its rate.
            # (e.g. If calculating 2035 and 2035 is in config, use 2035 rate)
            if t_year in config_milestones:
                applicable_milestone = t_year
            
            # CASE B: If t_year is NOT in config (e.g. 2035 is missing, next is 2050),
            # use the rate of the NEXT milestone.
            else:
                applicable_milestone = next((m for m in config_milestones if m >= t_year), None)
                
                # If beyond the last config milestone (e.g. 2060), extrapolate with the last known rate
                if applicable_milestone is None:
                    applicable_milestone = config_milestones[-1]
            
            rate = get_rate(applicable_milestone, scenario)
            
            # Apply CAGR formula
            years_diff = t_year - current_year
            next_value = current_value * ((1 + rate) ** years_diff)
            
            # Store if this is a requested target year
            if t_year in target_years:
                out[f"{t_year}_{scenario}"] = next_value
            
            # Update state for next segment
            current_value = next_value
            current_year = t_year

    return out

def expand_constant(value, base_year, target_years, scenarios):
    """Expands a single value constant across all years/scenarios."""
    if value is None: value = 0.0
    res = {str(base_year): value}
    for y in target_years:
        for s in scenarios:
            res[f"{y}_{s}"] = value
    return res

def poly_project(years, values, target_years, degree=2):
    """
    Project/Interpolate missing values using a polynomial fit (numpy).
    Useful for filling gaps in historical data (e.g. population).
    """
    try:
        # Filter clean data
        clean_points = [(float(y), float(v)) for y, v in zip(years, values) 
                        if str(y).replace('.','').isdigit() and pd.notnull(v)]
        
        if not clean_points:
            return {int(t): np.nan for t in target_years}
            
        x_train, y_train = zip(*clean_points)
        
        # Determine degree (cannot be > number of points - 1)
        deg = min(int(degree), len(x_train) - 1)
        
        if deg < 1:
            # Constant projection if only 1 point
            mean_val = np.mean(y_train)
            return {int(t): mean_val for t in target_years}
            
        # Fit polynomial
        coeffs = np.polyfit(x_train, y_train, deg)
        model = np.poly1d(coeffs)
        
        results = {}
        for t in target_years:
            val = model(t)
            # Prevent negative values for physical quantities
            results[int(t)] = max(0.0, float(val))
            
        # If the input BASE_YEAR was in target_years, ensure it matches input exactly if possible
        # (This block is optional but good for consistency)
        for y, v in clean_points:
            if int(y) in results:
                results[int(y)] = v

        return results
        
    except Exception as e:
        print(f"poly_project error: {e}")
        return {int(t): np.nan for t in target_years}
    
def apply_load_factor(metric, base_value, cagr_values, assumption_types, base_year, target_years, scenarios):

    if assumption_types.get(metric) == "LOAD_FACTOR":

        expanded = {}

        for year in [base_year] + target_years:
            for scenario in scenarios:

                key = f"{year}_{scenario}"

                val = cagr_values.get(metric, {}).get(year, {}).get(scenario)

                if val is not None:
                    expanded[key] = val
                else:
                    expanded[key] = base_value

        expanded[str(base_year)] = base_value
        return expanded

    else:
        return expand_constant(base_value, base_year, target_years, scenarios)