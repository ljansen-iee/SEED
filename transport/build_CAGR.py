#build_CAGR.py

import pandas as pd
import numpy as np
import os
import glob
import csv
from pathlib import Path

try:
    from transport.helpers import DEFAULT_TARGET_YEARS
except Exception:
    from helpers import DEFAULT_TARGET_YEARS


def _resolve_target_years(base_year=2020, target_years=None):
    years_source = DEFAULT_TARGET_YEARS if target_years is None else target_years
    years = []
    for year in years_source:
        try:
            year_int = int(year)
        except Exception:
            continue
        if year_int > int(base_year):
            years.append(year_int)

    years = sorted(set(years))
    return years if years else [2030, 2050]

# === Step 0: Helper to find source file (Excel or CSV) ===
def find_cagr_file(base_dir=None, file_patterns=("CAGR_current.csv", "CAGR_compilation_*.xlsx", "CAGR.csv")):
    """Locate the CAGR source file while ignoring backups/outside copies.

    Prefers a renamed "CAGR_current.csv" in the main transport input folder,
    then falls back to the original names. Restricts search to the transport
    package to avoid picking up backup/test duplicates.
    """

    transport_dir = Path(__file__).resolve().parent
    base_dir = Path(base_dir) if base_dir is not None else transport_dir

    # Search in the canonical input folder first, then the package root as fallback
    search_roots = [base_dir / "input_data" / "global", base_dir]

    matching_files = []
    for root in search_roots:
        if not root.is_dir():
            continue
        for file_pattern in file_patterns:
            search_pattern = str(root / "**" / file_pattern)
            matching_files.extend(glob.glob(search_pattern, recursive=True))

    matching_files = sorted(set(matching_files))

    if not matching_files:
        raise FileNotFoundError(
            f"No CAGR source file found in {base_dir}. Expected one of: {list(file_patterns)}"
        )
    if len(matching_files) > 1:
        raise ValueError(f"Multiple files found: {matching_files}")

    return matching_files[0]


# === Step 1: Load source file ===
try:
    file_path = find_cagr_file()
    if file_path.lower().endswith(".csv"):
        # CSV export has a meta header row above real column names
        df = pd.read_csv(file_path, header=1)
    else:
        df = pd.read_excel(file_path, header=0)
except Exception as e:
    print(f" Could not read CAGR source: {e}")
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

# CSV has duplicated columns (CAGR_2030, CAGR_2030.1, CAGR_2030.2)
# in ISI/Khalili/IEE order; normalize to the same names expected by the logic.
csv_cagr_mapping = {
    "CAGR_2030": "CAGR_2030_ISI",
    "CAGR_2040": "CAGR_2040_ISI",
    "CAGR_2050": "CAGR_2050_ISI",
    "CAGR_2030.1": "CAGR_2030_Khalili",
    "CAGR_2040.1": "CAGR_2040_Khalili",
    "CAGR_2050.1": "CAGR_2050_Khalili",
    "CAGR_2030.2": "CAGR_2030_IEE",
    "CAGR_2040.2": "CAGR_2040_IEE",
    "CAGR_2050.2": "CAGR_2050_IEE",
}
if any(col in df.columns for col in csv_cagr_mapping):
    df = df.rename(columns={k: v for k, v in csv_cagr_mapping.items() if k in df.columns})

# Convert percentage strings - numeric
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


# === Step 4: Mapping (Excel - metric names) ===
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
    # ( No "Gasoline Plugin Hybrid Bus" in your final list - excluded)

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

    # Source CSV uses "-" for aviation rows and explicit Passenger for inland shipping
    if "aviation" in subsector.lower():
        submode = "Passenger"
    if "shipping" in subsector.lower() or "ship" in subsector.lower():
        submode = "-"

    # --- Normalize drive types ---
    raw_d = d
    d = d.replace("(bev)", "bev").replace("(ice)", "ice")
    d = d.replace("phevbev", "efficiency phev bev")
    d = d.replace("phevice", "efficiency phev ice")

    if "efficiency ice" in raw_d:
        drive = "Diesel"
    elif "efficiency bev" in raw_d:
        drive = "BEV"
    elif "efficiency fcev" in raw_d:
        drive = "FCEV"
    elif "phev" in d and "bev" not in d and "ice" not in d:
        drive = "Efficiency PHEV (BEV)"
    elif "phev" in d and "ice" in d:
        drive = "Efficiency PHEV (ICE)"
    elif "phev" in d:
        drive = "Efficiency PHEV (BEV)"
    elif "electric" in d:
        drive = "Electric (incl. BEV)"
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
                val = float(str(x).replace("%", ""))
                if abs(val) > 1.0:
                    return val / 100.0
                return val
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


# try:
#     from helpers import load_expert_config
#     BASE_VALUES = load_expert_config()   # <-- NO ARGUMENTS NOW
# except Exception as e:
#     #print(f" Could not load base values from YAML: {e}")
#     BASE_VALUES = {}


# ==========================================================
# NEW: ROLLING CAGR CALCULATION WITH IQR-BASED OUTLIER CAPPING
# ==========================================================

def discover_years_from_unsd(unsd_folder, country):
    """Discover available years for a country from UNSD CSV files."""
    import glob
    from pathlib import Path
    
    try:
        unsd_path = Path(unsd_folder)
        country_files = sorted(glob.glob(str(unsd_path / f"{country}-*.csv")))
        years = []
        for file_path in country_files:
            try:
                year = int(file_path.split("-")[-1].replace(".csv", ""))
                years.append(year)
            except Exception:
                pass
        return sorted(set(years)) if years else []
    except Exception:
        return []


def _clean_val(val):
    """Convert messy numeric strings to float, handling UNSD special characters."""
    if pd.isna(val):
        return None
    s = str(val).strip()
    if s in ["---", "", "-", "None"]:
        return None
    try:
        # Remove * and other UNSD special characters, then convert
        cleaned = s.replace("*", "").replace(",", "")
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def get_sector_total_from_unsd(unsd_folder, country, year, sector):
    """
    Retrieve total energy (in TJ) for a country-sector-year from UNSD CSV.
    
    Sector names can be:
    - "International marine bunkers"
    - "International aviation bunkers"
    - "Road transport"
    - "Rail transport"
    - "Pipeline transport"
    - "Domestic aviation"
    - "Domestic navigation"
    """
    from pathlib import Path
    
    try:
        file_path = Path(unsd_folder) / f"{country}-{year}.csv"
        
        if not file_path.exists():
            return None
        
        # Read CSV with first row as header
        df = pd.read_csv(file_path)
        
        # Column 1 (0-indexed) contains sector/transaction names
        # It's named "Transactions(down)/Commodity(right)" in the header
        sector_col = df.iloc[:, 1]
        
        # Find the row matching the sector
        matching_rows = df[sector_col.str.contains(sector, case=False, na=False)]
        
        if matching_rows.empty:
            return None
        
        # Get the "Total Energy" column value
        if 'Total Energy' not in df.columns:
            return None
            
        value = matching_rows['Total Energy'].iloc[0]
        
        # Clean and convert the value
        cleaned_value = _clean_val(value)
        return cleaned_value
            
    except Exception as e:
        # Debug: uncomment to see errors
        # print(f"Error reading {country}-{year}: {e}")
        return None


def build_energy_table_with_rolling_cagr(
    unsd_folder=None,
    countries=None, 
    sectors=None, 
    window=5,  # 5-year rolling window
    base_year=2020
):
    """
    Build energy table for specified countries & sectors from UNSD data.
    Compute rolling CAGR over specified window.
    Apply IQR-based outlier capping and calculate suggested CAGR.
    
    Parameters:
    - unsd_folder: Path to UNSD CSV files (default: auto-detect)
    - countries: List of country names (REQUIRED - only these countries will be processed)
    - sectors: List of sectors to extract (default: only bunker sectors)
    - window: Rolling window in years
    - base_year: Reference year
    
    Returns: DataFrame with columns [country, sector, year, total_tj, total_twh, CAGR, CAGR_capped, suggested_cagr]
    """
    from pathlib import Path
    import glob
    
    # Auto-detect UNSD folder
    if unsd_folder is None:
        possible_paths = [
            Path("input_data/unsd_unsdata_historical"),
            Path("transport/input_data/unsd_unsdata_historical"),
            Path(__file__).resolve().parent / "input_data/unsd_unsdata_historical",
        ]
        for path in possible_paths:
            if path.exists():
                unsd_folder = path
                break
        
        if unsd_folder is None:
            print("[!] UNSD folder not found. Checked:")
            for p in possible_paths:
                print(f"  - {p}")
            return pd.DataFrame()
    
    unsd_path = Path(unsd_folder)
    
    if not unsd_path.exists():
        print(f"[!] UNSD folder not found: {unsd_folder}")
        return pd.DataFrame()
    
    print(f"[OK] Using UNSD folder: {unsd_path.resolve()}")
    
    # Countries MUST be provided - do not auto-discover
    if countries is None or len(countries) == 0:
        print("[!] Error: countries list must be provided (cannot auto-discover)")
        return pd.DataFrame()
    
    # Only bunker sectors by default (not all transport sectors)
    if sectors is None:
        sectors = [
            "International marine bunkers",
            "International aviation bunkers",
        ]
    
    # 5.1 BUILD ENERGY TABLE
    rows = []
    processed_countries = []
    for country in countries:
        years = discover_years_from_unsd(unsd_folder, country)
        if not years:
            continue
            
        processed_countries.append(country)
        print(f"  {country}: {len(years)} years ({min(years)}-{max(years)})", end="")
        country_records = 0
        
        for sector in sectors:
            for year in years:
                total_tj = get_sector_total_from_unsd(unsd_folder, country, year, sector)
                
                if total_tj is None:
                    continue
                
                # Take absolute value (bunker fuels are negative in UNSD)
                total_tj = abs(total_tj)
                
                if total_tj == 0:
                    continue
                    
                total_twh = total_tj * 0.000277778  # TJ - TWh
                
                rows.append({
                    "country": country,
                    "sector": sector,
                    "year": year,
                    "total_tj": total_tj,
                    "total_twh": total_twh,
                })
                country_records += 1
        
        print(f" - {country_records} records")
    
    if not rows:
        print(f"\n[!] No energy data extracted! Processed {len(processed_countries)} countries but no sectors found.")
        print(f"  Countries processed: {', '.join(processed_countries[:5])}...")
        print(f"  Sectors searched: {sectors[:3]}...")
        return pd.DataFrame()
    
    df = pd.DataFrame(rows).sort_values(["country", "sector", "year"])
    print(f"\n[OK] Energy table built: {len(df)} records from {len(df['country'].unique())} countries")
    
    if df.empty:
        print("[!] Warning: Energy table is empty!")
        return df
    
    # 5.2 COMPUTE ROLLING CAGR
    df["start_year"] = df["year"] - window
    
    # Build lookup for start values
    start_lookup = df[["country", "sector", "year", "total_twh"]].copy()
    start_lookup = start_lookup.rename(columns={
        "year": "start_year",
        "total_twh": "start_twh"
    })
    
    # Merge to get start values
    df = df.merge(start_lookup, on=["country", "sector", "start_year"], how="left")
    
    # Compute CAGR
    valid = (df["start_twh"] > 0) & (df["total_twh"] > 0)
    df["CAGR"] = pd.NA
    df.loc[valid, "CAGR"] = (
        (df.loc[valid, "total_twh"] / df.loc[valid, "start_twh"]) ** (1 / window) - 1
    )
    df["CAGR"] = pd.to_numeric(df["CAGR"], errors="coerce")
    
    print(f"[OK] CAGR computed for {valid.sum()} records")
    
    # 6.1 APPLY IQR-BASED OUTLIER CAPPING
    def apply_iqr_capping(group):
        """Apply IQR-based outlier detection and capping per group."""
        group = group.copy()
        
        growth = pd.to_numeric(group["CAGR"], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        
        group["CAGR_capped"] = group["CAGR"]
        group["IQR_lower"] = np.nan
        group["IQR_upper"] = np.nan
        
        if len(growth) >= 4:
            q1 = growth.quantile(0.25)
            q3 = growth.quantile(0.75)
            iqr = q3 - q1
            
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            
            group["IQR_lower"] = lower
            group["IQR_upper"] = upper
            
            group["CAGR_capped"] = group["CAGR"].clip(lower=lower, upper=upper)
        
        return group
    
    # Apply per country & sector
    df = df.groupby(["country", "sector"], group_keys=False).apply(apply_iqr_capping)
    df["CAGR_capped"] = pd.to_numeric(df["CAGR_capped"], errors="coerce").round(6)
    
    # Hard bounds (±30%)
    df["CAGR_capped"] = df["CAGR_capped"].clip(-0.30, 0.30)
    
    print(f"[OK] IQR capping applied")
    
    # 7. CALCULATE SUGGESTED CAGR FROM CAPPED VALUES
    df["suggested_cagr"] = (
        df.groupby(["country", "sector"])["CAGR_capped"]
        .transform("mean")
        .round(6)
    )
    
    print(f"[OK] Suggested CAGR calculated")
    
    return df


def get_bunker_cagr_for_countries(countries, unsd_folder=None, bunker_type="marine"):
    """
    Extract suggested CAGR values for international bunkers for SPECIFIC countries only.
    
    Args:
        countries: list of country names (REQUIRED)
        unsd_folder: path to UNSD folder (auto-detected if None)
        bunker_type: "marine" or "aviation"
    
    Returns:
        dict: {country: suggested_cagr_value}
    
    Example:
        marine_cagr = get_bunker_cagr_for_countries(["Morocco", "Algeria"], bunker_type="marine")
        aviation_cagr = get_bunker_cagr_for_countries(["Morocco", "Algeria"], bunker_type="aviation")
    """
    if not countries or len(countries) == 0:
        print(f"[WARN] No countries provided, returning empty dict")
        return {}
    
    try:
        # Build rolling CAGR table ONLY for the specified countries (lazy initialization)
        sectors = [
            "International marine bunkers" if bunker_type.lower() == "marine" else "International aviation bunkers"
        ]
        
        rolling_df = build_energy_table_with_rolling_cagr(
            unsd_folder=unsd_folder, 
            countries=countries,  # ONLY these countries
            sectors=sectors,      # ONLY this bunker sector
            window=5
        )
        
        if rolling_df.empty:
            print(f"[WARN] Rolling CAGR table is empty, returning zeros")
            return {country: 0.0 for country in countries}
        
        # Map bunker_type to sector name in the UNSD data
        if bunker_type.lower() == "marine":
            sector_filter = "International marine bunkers"
        elif bunker_type.lower() == "aviation":
            sector_filter = "International aviation bunkers"
        else:
            raise ValueError(f"Unknown bunker_type: {bunker_type}")
        
        # Extract CAGR values for requested countries
        result = {}
        for country in countries:
            country_bunker = rolling_df[
                (rolling_df["country"] == country) & 
                (rolling_df["sector"] == sector_filter)
            ]
            
            if country_bunker.empty:
                result[country] = 0.0  # Default to 0% if not found
                print(f"  [WARN] {country} {bunker_type} bunkers: not found (using 0%)")
            else:
                # Get the unique suggested_cagr value (should be same for all years)
                cagr_value = country_bunker["suggested_cagr"].iloc[0]
                # Handle NaN values (convert to 0.0)
                if pd.isna(cagr_value):
                    cagr_value = 0.0
                    print(f"  [WARN] {country} {bunker_type} bunkers: insufficient data (using 0%)")
                else:
                    cagr_value = float(cagr_value)
                    print(f"  [OK] {country} {bunker_type} bunkers: {cagr_value:.6f} ({cagr_value*100:.4f}%)")
                result[country] = cagr_value
        
        return result
        
    except Exception as e:
        print(f"[!] Error extracting bunker CAGR: {e}")
        return {country: 0.0 for country in countries}


# Build the rolling CAGR table from UNSD data - ONLY when needed (lazy initialization)
# Do NOT auto-compute at module load time - wait for countries list from build_config_transport.py
ROLLING_CAGR_DF = pd.DataFrame()


try:
    CAGR_VALUES = build_cagr_values(result_df, BASE_VALUES, base_year=2020)
except Exception:
    CAGR_VALUES = {}


#print(f" build_cagr_values produced {len(CAGR_VALUES)} entries")
#if not CAGR_VALUES:
    #print(" No metrics were matched. Check METRIC_NAME_MAP or BASE_VALUES[2020].")



def expand_with_piecewise_cagr(base_value, cagr_dict, base_year=2020, target_years=None):
    
    import pandas as pd

    target_years = _resolve_target_years(base_year=base_year, target_years=target_years)

    if base_value in [None] or pd.isna(base_value):
        base_value = 1.0

    out = {str(base_year): round(float(base_value), 6)}

    available_years = sorted(int(y) for y in cagr_dict.keys() if str(y).isdigit())

    for y in target_years:
        year = int(y)
        # find the bounding years
        prev_years = [yr for yr in available_years if yr <= year]
        next_years = [yr for yr in available_years if yr >= year]

        # if below first known year - use first CAGR
        if not prev_years:
            y1 = available_years[0]
            year_data = cagr_dict.get(y1, {})
        # if beyond last known year - use last CAGR (extrapolate)
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


MA_METRIC_MAP = {
    "Final Energy Intensity -  ICE LDV": "Final Energy Intensity - Diesel ICE LDV",
    "Final Energy Intensity - Gasoline ICE LDV": "Final Energy Intensity - Gasoline ICE LDV",
    "Final Energy Intensity -  ICE Bus": "Final Energy Intensity - Diesel ICE Bus",
    "Final Energy Intensity - ICE 2&3W": "Final Energy Intensity - Gasoline ICE 2&3W",
    "Final Energy Intensity - ICE LDT": "Final Energy Intensity - Diesel ICE LDT",
    "Final Energy Intensity - ICE HDT": "Final Energy Intensity - Diesel ICE HDT",
    "Final Energy Intensity - Plugin Hybrid LDV": "Final Energy Intensity - Diesel Plugin Hybrid LDV",
    "Final Energy Intensity - Plugin Hybrid Bus": "Final Energy Intensity - Diesel Plugin Hybrid Bus",
    "Final Energy Intensity - Plugin Hybrid LDT": "Final Energy Intensity - Diesel Plugin Hybrid LDT",
    "Final Energy Intensity - Plugin Hybrid HDT": "Final Energy Intensity - Diesel Plugin Hybrid HDT",
    "Final Energy Intensity - BEV LDV": "Final Energy Intensity - BEV LDV",
    "Final Energy Intensity - BEV Bus": "Final Energy Intensity - BEV Bus",
    "Final Energy Intensity - BEV 2&3W": "Final Energy Intensity - BEV 2&3W",
    "Final Energy Intensity - BEV LDT": "Final Energy Intensity - BEV LDT",
    "Final Energy Intensity - BEV HDT": "Final Energy Intensity - BEV HDT",
    "Final Energy Intensity - FCEV LDV": "Final Energy Intensity - FCEV LDV",
    "Final Energy Intensity - FCEV Bus": "Final Energy Intensity - FCEV Bus",
    "Final Energy Intensity - FCEV LDT": "Final Energy Intensity - FCEV LDT",
    "Final Energy Intensity - FCEV HDT": "Final Energy Intensity - FCEV HDT",
    "Final Energy Intensity - ICE Train": "Final Energy Intensity - Diesel ICE Passenger Train",
    "Final Energy Intensity - Direct Electric Train": "Final Energy Intensity - Direct Electric Passenger Train",
    "Final Energy Intensity - FCEV Train": "Final Energy Intensity - FCEV Passenger Train",
    "Final Energy Intensity - ICE Freight Train": "Final Energy Intensity - Diesel ICE Freight Train",
    "Final Energy Intensity - Direct Electric Freight Train": "Final Energy Intensity - Direct Electric Freight Train",
    "Final Energy Intensity - FCEV Freight Train": "Final Energy Intensity - FCEV Freight Train",
    "Final Energy Intensity - ICE Ship": "Final Energy Intensity - Diesel Freight Ship",
    "Final Energy Intensity - BEV Ship": "Final Energy Intensity - BEV Freight Ship",
    "Final Energy Intensity - FCEV Ship": "Final Energy Intensity - FCEV Freight Ship",
    "Final Energy Intensity - Methanol Ship": "Final Energy Intensity - Methanol Freight Ship",
    "Final Energy Intensity - Ammonia Ship": "Final Energy Intensity - Ammonia Freight Ship",
    "Final Energy Intensity - ICE Plane": "Final Energy Intensity - Kerosene Passenger Plane",
    "Final Energy Intensity - BEV Plane": "Final Energy Intensity - BEV Passenger Plane",
    "Final Energy Intensity - FCEV Plane": "Final Energy Intensity - FCEV Passenger Plane",
    "Final Energy Intensity - LPG ICE LDV": "Final Energy Intensity - LPG ICE LDV",
    "Final Energy Intensity - Gasoline Plugin Hybrid LDV": "Final Energy Intensity - Gasoline Plugin Hybrid LDV",
}

# Map metrics to their CAGR source when they don't have their own CAGR data
# Key = metric that needs CAGR, Value = metric to copy CAGR from
CAGR_SOURCE_MAP = {
    "Final Energy Intensity - Gasoline ICE LDV": "Final Energy Intensity - Diesel ICE LDV",
    "Final Energy Intensity - LPG ICE LDV": "Final Energy Intensity - Diesel ICE LDV",
    "Final Energy Intensity - Methanol Freight Ship": "Final Energy Intensity - Diesel Freight Ship",
    "Final Energy Intensity - Ammonia Freight Ship": "Final Energy Intensity - Diesel Freight Ship",
}


# Manual percentage CAGRs for selected metrics (values as fractions, e.g. -0.0075 = -0.75%)
MANUAL_FINAL_ENERGY_CAGR = {
    "Final Energy Intensity - ICE 2&3W": (
        -0.0075, -0.0150, -0.0200,  # 2030: EL, Baseline, RF
        -0.0025, -0.0050, -0.0100,  # 2050: EL, Baseline, RF
    ),
    "Final Energy Intensity - BEV 2&3W": (
        -0.0025, -0.0050, -0.0100,
        -0.0025, -0.0050, -0.0100,
    ),
    "Final Energy Intensity - BEV Ship": (
        -0.0040, -0.0080, -0.0100,
        -0.0040, -0.0080, -0.0100,
    ),
    "Final Energy Intensity - FCEV Ship": (
        -0.0105, -0.0105, -0.0105,
        -0.0102, -0.0113, -0.0125,
    ),
}


def export_rolling_cagr_analysis(
    rolling_cagr_df=None,
    output_csv_path="transport/output_data/country_parameters/rolling_cagr_analysis.csv",
):
    """
    Export the rolling CAGR analysis to CSV for inspection and validation.
    Includes: original CAGR, outlier bounds (IQR), capped CAGR, and suggested CAGR.
    """
    if rolling_cagr_df is None or rolling_cagr_df.empty:
        print("Warning: No rolling CAGR data to export")
        return None
    
    # Select relevant columns for export
    export_cols = [
        "country", "sector", "year", "start_year",
        "total_tj", "total_twh", "start_twh",
        "CAGR", "IQR_lower", "IQR_upper", "CAGR_capped", "suggested_cagr"
    ]
    
    available_cols = [c for c in export_cols if c in rolling_cagr_df.columns]
    df_export = rolling_cagr_df[available_cols].copy()
    
    # Round numeric columns for readability
    for col in ["total_tj", "total_twh", "start_twh", "CAGR", "IQR_lower", "IQR_upper", "CAGR_capped", "suggested_cagr"]:
        if col in df_export.columns:
            df_export[col] = df_export[col].round(6)
    
    os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)
    df_export.to_csv(output_csv_path, index=False)
    print(f"Rolling CAGR analysis exported to: {output_csv_path}")
    
    return output_csv_path


def get_suggested_cagr_by_country_sector(rolling_cagr_df=None, country=None, sector=None):
    """
    Query suggested CAGR from rolling CAGR analysis by country and sector.
    Returns: Single suggested CAGR value or None if not found.
    """
    if rolling_cagr_df is None or rolling_cagr_df.empty:
        return None
    
    if country is None or sector is None:
        return None
    
    subset = rolling_cagr_df[
        (rolling_cagr_df["country"] == country) &
        (rolling_cagr_df["sector"] == sector)
    ]
    
    if subset.empty:
        return None
    
    # Return the first (consistent) suggested_cagr value for this country-sector pair
    suggested = subset["suggested_cagr"].iloc[0]
    return suggested if pd.notna(suggested) else None


def build_cagr_matrix_from_rolling(rolling_cagr_df, base_year=2020, target_years=None):
    """
    Convert rolling CAGR suggestions into the standard CAGR_VALUES dictionary structure.
    This allows seamless integration with the existing export_final_energy_intensity_cagr_with_intermediate() function.
    
    Returns: Dictionary structured like CAGR_VALUES for use in config export.
    """
    if rolling_cagr_df is None or rolling_cagr_df.empty:
        return {}
    
    if target_years is None:
        target_years = _resolve_target_years(base_year=base_year)
    
    cagr_matrix = {}
    
    # Group by country and sector to extract unique suggested CAGR values
    for (country, sector), group in rolling_cagr_df.groupby(["country", "sector"]):
        suggested_cagr = group["suggested_cagr"].iloc[0]
        
        if pd.isna(suggested_cagr):
            continue
        
        # Create a metric key (e.g., "Road - Passenger LDV - Suggested")
        metric_key = f"{sector} ({country}) - Suggested CAGR"
        
        # Structure with 2030 and 2050 scenarios (replicating across Baseline/RF/EL)
        cagr_matrix[metric_key] = {
            str(base_year): None,  # No base value needed
            2030: {
                "Baseline": suggested_cagr,
                "RF": suggested_cagr,
                "EL": suggested_cagr,
            },
            2050: {
                "Baseline": suggested_cagr,
                "RF": suggested_cagr,
                "EL": suggested_cagr,
            },
        }
    
    print(f"Built CAGR matrix from {len(cagr_matrix)} country-sector combinations")
    return cagr_matrix


def export_final_energy_intensity_ma_format(
    cagr_values=None,
    output_csv_path="transport/output_data/country_parameters/final_energy_intensity_MA_format.csv",
    output_xlsx_path="transport/output_data/country_parameters/final_energy_intensity_MA_format.xlsx",
):
    """
    Export MA-format final energy intensity table from CAGR_VALUES (data-driven, no hardcoded percentages).
    """
    if cagr_values is None:
        cagr_values = CAGR_VALUES

    def pct(val):
        if val is None or pd.isna(val):
            return ""
        return f"{float(val) * 100:.2f}%"

    rows = [
        ["Input Data", "2030", "2030", "2030", "2050", "2050", "2050"],
        ["MA", "Baseline", "RF", "EL", "Baseline", "RF", "EL"],
        ["", "SSP2", "SSP2", "SSP1", "SSP2", "SSP2", "SSP1"],
        ["", "", "", "", "", "", ""],
        ["CAGR", "", "", "", "", "", ""],
        ["", "", "", "", "", "", ""],
    ]

    for display_metric, source_metric in MA_METRIC_MAP.items():
        values = cagr_values.get(source_metric, {})
        y2030 = values.get(2030, {}) if isinstance(values, dict) else {}
        y2050 = values.get(2050, {}) if isinstance(values, dict) else {}

        rows.append([
            display_metric,
            pct(y2030.get("EL")),
            pct(y2030.get("Baseline")),
            pct(y2030.get("RF")),
            pct(y2050.get("EL")),
            pct(y2050.get("Baseline")),
            pct(y2050.get("RF")),
        ])

    os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)
    with open(output_csv_path, "w", newline="", encoding="utf-8") as file_handle:
        writer = csv.writer(file_handle)
        writer.writerows(rows)

    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font

        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "CAGR"

        for row_idx, row in enumerate(rows, start=1):
            for col_idx, value in enumerate(row, start=1):
                worksheet.cell(row=row_idx, column=col_idx, value=value)

        worksheet.merge_cells("B1:D1")
        worksheet.merge_cells("E1:G1")

        for cell in worksheet[1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center")
        for cell in worksheet[2]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center")
        for cell in worksheet[3]:
            cell.alignment = Alignment(horizontal="center")

        worksheet["A5"].font = Font(bold=True)
        worksheet.column_dimensions["A"].width = 52
        for column_letter in ["B", "C", "D", "E", "F", "G"]:
            worksheet.column_dimensions[column_letter].width = 14

        worksheet.freeze_panes = "A7"
        os.makedirs(os.path.dirname(output_xlsx_path), exist_ok=True)
        workbook.save(output_xlsx_path)
    except Exception:
        pass

    return output_csv_path, output_xlsx_path


def export_final_energy_intensity_cagr_with_intermediate(
    cagr_values=None,
    output_csv_path=str(Path(__file__).resolve().parent / "trans_config.csv"),
):

    if cagr_values is None:
        cagr_values = CAGR_VALUES

    def format_fraction(val):
        if val is None or pd.isna(val):
            return ""
        try:
            return f"{float(val):.4f}"
        except Exception:
            return ""

    # Scenario labels and country list come from transport config (no hardcoded defaults).
    # Ensure the transport folder is on sys.path so build_transport_config
    # can import its local helpers module correctly.
    import sys
    transport_dir = os.path.dirname(__file__)
    if transport_dir not in sys.path:
        sys.path.append(transport_dir)

    # Use the actual config module name in this repository
    from transport.build_transport_config import SCENARIOS as TRANSPORT_SCENARIOS, countries_to_process
    from transport.build_share_subsectors import get_final_df_with_mobility
    scenario_names = list(TRANSPORT_SCENARIOS)
    country_names = list(countries_to_process)

    if len(scenario_names) != 3:
        raise ValueError("export_final_energy_intensity_cagr_with_intermediate expects exactly 3 scenarios in build_transport_config.SCENARIOS")
    if not country_names:
        raise ValueError("No countries found in build_transport_config.countries_to_process")

    base_year = 2020
    target_years = _resolve_target_years(base_year=base_year)

    header = ["Assumption Type", "Metric Name", "Year", "Scenario", *country_names]
    rows = [header]

    # === Population rows (2020 base + blank CAGR placeholders) ===
    try:
        from helpers import load_unsdata_historical_data, find_input_folder, get_interpolated_value
        from build_macro_indicators import process_population_data

        dfs_country = load_unsdata_historical_data(find_input_folder())
        df_population = process_population_data(dfs_country)

        population_base_values = []
        for country in country_names:
            try:
                pop_df = df_population.loc[country]
                if "Unit" in pop_df.columns:
                    pop_df = pop_df.drop(columns=["Unit"])
                # Keep one base line (single scenario) using SSP2 at base year
                pop_val = get_interpolated_value(pop_df, "SSP2", base_year)
                population_base_values.append(pop_val)
            except Exception:
                population_base_values.append(None)

        rows.append([
            "Base",
            "Population",
            base_year,
            "Base",
            *[f"{float(v):.4f}" if v is not None and not pd.isna(v) else "" for v in population_base_values],
        ])

        # Keep population CAGR slots blank for all configured target years
        for year in target_years:
            for scenario in scenario_names:
                rows.append([
                    "CAGR",
                    "Population",
                    year,
                    scenario,
                    *["" for _ in country_names],
                ])
    except Exception as exc:
        print(f"Warning: could not add Population rows ({exc})")

    # === Base year (2020) levels for final energy intensities ===
    from build_energy_intensities import get_base_intensity_values

    base_intensity_map = get_base_intensity_values()

    def format_value(val):
        if val is None or pd.isna(val):
            return ""
        try:
            return f"{float(val):.4f}"
        except Exception:
            return ""

    metric_list = list(dict.fromkeys(MA_METRIC_MAP.values()))
    manual_by_source = {}
    for disp, src in MA_METRIC_MAP.items():
        if disp in MANUAL_FINAL_ENERGY_CAGR:
            manual_by_source[src] = MANUAL_FINAL_ENERGY_CAGR[disp]

    for source_metric in metric_list:
        base_val = base_intensity_map.get(source_metric)
        row = [
            "Base",
            source_metric,
            base_year,
            "Base",
            *[format_value(base_val) for _ in country_names],
        ]
        rows.append(row)

    for source_metric in metric_list:
        manual = manual_by_source.get(source_metric)

        for year in target_years:
            for scen_idx, scenario in enumerate(scenario_names):
                if manual is not None:
                    el_2030, base_2030, rf_2030, el_2050, base_2050, rf_2050 = manual
                    values_2030 = (el_2030, base_2030, rf_2030)
                    values_2050 = (el_2050, base_2050, rf_2050)
                    values_for_year = values_2030 if year in (2030, 2035) else values_2050
                    val = values_for_year[scen_idx] if scen_idx < len(values_for_year) else None
                else:
                    # Check if this metric should use another metric's CAGR
                    cagr_lookup_metric = CAGR_SOURCE_MAP.get(source_metric, source_metric)
                    entry = cagr_values.get(cagr_lookup_metric, {})
                    y2030 = entry.get(2030, {}) if isinstance(entry, dict) else {}
                    y2050 = entry.get(2050, {}) if isinstance(entry, dict) else {}

                    src = y2030 if year in (2030, 2035) else y2050
                    src_values = list(src.values()) if isinstance(src, dict) else []

                    if len(src_values) == 3:
                        index_order = [2, 0, 1]  # preserve previous EL/Baseline/RF ordering by position
                    else:
                        index_order = list(range(len(src_values)))

                    if scen_idx < len(index_order) and index_order[scen_idx] < len(src_values):
                        val = src_values[index_order[scen_idx]]
                    else:
                        val = None

                row = [
                    "CAGR",
                    source_metric,
                    year,
                    scenario,
                    *[format_fraction(val) for _ in country_names],
                ]
                rows.append(row)

    # === Mobility per capita (Freight/Passenger) CAGRs per country ===
    try:
        mobility_df = get_final_df_with_mobility()
    except Exception as exc:
        print(f"Warning: could not build mobility dataframe ({exc})")
        mobility_df = None

    if mobility_df is not None:
        timeline_years = [base_year] + target_years
        year_pairs = {
            timeline_years[i]: (timeline_years[i - 1], timeline_years[i])
            for i in range(1, len(timeline_years))
        }

        def get_val(series, year):
            for key in (f"{float(year)}", f"{year}", float(year), year):
                if key in series.index:
                    try:
                        return float(series[key])
                    except Exception:
                        pass
            return None

        def calc_cagr(a, b, years):
            try:
                if a is None or b is None or a == 0:
                    return None
                return (b / a) ** (1 / years) - 1
            except Exception:
                return None

        for mobility_metric in ["Mobility per capita - Freight", "Mobility per capita - Passenger"]:
            # Base year (2020) level rows
            base_values = []
            for country in country_names:
                try:
                    series = mobility_df.loc[(country, mobility_metric)]
                except KeyError:
                    base_values.append(None)
                    continue
                base_values.append(get_val(series, base_year))

            row = [
                "Base",
                mobility_metric,
                base_year,
                "Base",
                *[format_value(v) for v in base_values],
            ]
            rows.append(row)

            # CAGR rows for mobility metrics
            for target_year, (start_year, end_year) in year_pairs.items():
                values = []
                for country in country_names:
                    try:
                        series = mobility_df.loc[(country, mobility_metric)]
                    except KeyError:
                        values.append(None)
                        continue

                    start_val = get_val(series, start_year)
                    end_val = get_val(series, end_year)
                    cagr_val = calc_cagr(start_val, end_val, end_year - start_year)
                    values.append(cagr_val)

                for scenario in scenario_names:
                    row = [
                        "CAGR",
                        mobility_metric,
                        target_year,
                        scenario,
                        *[format_fraction(v) for v in values],
                    ]
                    rows.append(row)

        # === Load Factor levels (sourced directly from load_factor inputs) ===
        try:
            from build_load_factors import (
                get_Load_factor_Car,
                Load_factor_Bus,
                Load_factor_two_three_occupancy,
                medium_load_factor,
                heavy_load_factor,
                load_factor,
            )
            from helpers import load_global_transport_data, get_transport_constants

            raw_df = load_global_transport_data()
            if raw_df is None or raw_df.empty:
                raise ValueError("transport input data is empty")

            df_car = get_Load_factor_Car(raw_df)
            df_bus = Load_factor_Bus(raw_df)
            df_two_three = Load_factor_two_three_occupancy(raw_df)
            df_medium = medium_load_factor(raw_df)
            df_heavy = heavy_load_factor(raw_df)
            load_passenger_plane, load_freight_ship, _ = load_factor()

            load_factor_metrics = [
                "Load Factor - LDV",
                "Load Factor - Bus",
                "Load Factor - 2&3W",
                "Load Factor - Passenger Train",
                "Load Factor - Passenger Plane",
                "Load Factor - LDT",
                "Load Factor - HDT",
                "Load Factor - Freight Train",
                "Load Factor - Freight Ship",
            ]

            def lf_value(metric, country, year):
                def grab(df_obj):
                    try:
                        if "Countries List" in df_obj.columns:
                            matches = df_obj.loc[df_obj["Countries List"] == country]
                            if matches.empty:
                                return None
                            series = matches.iloc[0]
                        else:
                            series = df_obj.loc[country]

                        candidates = [str(year)] if "." in str(year) else [str(year), f"{year}.0"]
                        for col in candidates:
                            if col in series.index:
                                val = series.get(col)
                                if not pd.isna(val):
                                    return val
                        return None
                    except Exception:
                        return None

                if metric == "Load Factor - LDV":
                    return grab(df_car)
                if metric == "Load Factor - Bus":
                    return grab(df_bus)
                if metric == "Load Factor - 2&3W":
                    return grab(df_two_three)
                if metric == "Load Factor - Passenger Train":
                    base_val = grab(df_car)
                    if base_val is None:
                        return None
                    return base_val * get_transport_constants("load_factor_multiplier", "Passenger Train")
                if metric == "Load Factor - Passenger Plane":
                    return load_passenger_plane
                if metric == "Load Factor - LDT":
                    return grab(df_medium)
                if metric == "Load Factor - HDT":
                    return grab(df_heavy)
                if metric == "Load Factor - Freight Train":
                    hdt_val = grab(df_heavy)
                    if hdt_val is None:
                        return None
                    return hdt_val * get_transport_constants("load_factor_multiplier", "Freight Train")
                if metric == "Load Factor - Freight Ship":
                    return load_freight_ship
                return None

            for metric in load_factor_metrics:
                base_values = [lf_value(metric, country, base_year) for country in country_names]

                rows.append([
                    "Base",
                    metric,
                    base_year,
                    "Base",
                    *[format_value(v) for v in base_values],
                ])

                for year in target_years:
                    for scenario in scenario_names:
                        values = []
                        for country in country_names:
                            val = lf_value(metric, country, year)
                            if val is None:
                                val = lf_value(metric, country, base_year)
                            values.append(val)

                        rows.append([
                            "Value",
                            metric,
                            year,
                            scenario,
                            *[format_value(v) for v in values],
                        ])

        except Exception as exc:
            print(f"Warning: could not append load factor rows ({exc})")

        # === Technology share levels (2020 base, flat for future years) ===
        try:
            from build_technology_share import (
                share_technology,
                Share_of_Direct_Electric_Passenger_Train,
                TECHNOLOGY_OVERRIDES,
                get_unsd_bunker_fuel_shares,
            )
            from helpers import load_global_transport_data, clean_column_headers, unsd_input_folder

            df_raw_source = load_global_transport_data()
            df_direct_elec = Share_of_Direct_Electric_Passenger_Train(df_raw_source)
            if "Countries List" not in df_direct_elec.columns:
                df_direct_elec = clean_column_headers(df_direct_elec)
            df_direct_elec = df_direct_elec.set_index("Countries List")

            tech_metric_order = list(TECHNOLOGY_OVERRIDES.keys())

            # Default reference country for technology shares when OECD data is missing
            DEFAULT_TECH_COUNTRY = "Morocco"

            def tech_base_for_country(country):
                (
                    technology_gasoline_ice_ldv, technology_diesel_ice_ldv, technology_lpg_ice_ldv,
                    technology_bev_ldv, technology_fcev_ldv,
                    technology_diesel_plugin_hybrid_ldv, technology_gasoline_plugin_hybrid_ldv,
                    technology_diesel_ice_bus, technology_bev_bus, technology_fcev_bus, technology_diesel_plugin_hybrid_bus,
                    technology_gasoline_ice_2_and_3w, technology_bev_two_three_wheeler,
                    technology_fcev_passenger_train,
                    technology_kerosene_passenger_plane, technology_bev_passenger_plane, technology_fcev_passenger_plane,
                    technology_diesel_ice_ldt, technology_bev_ldt, technology_fcev_ldt, technology_diesel_plugin_hybrid_ldt,
                    technology_diesel_ice_hdt, technology_bev_hdt, technology_fcev_hdt, technology_diesel_plugin_hybrid_hdt,
                    technology_fcev_freight_train,
                    technology_diesel_ice_freight_ship, technology_methanol_freight_ship, technology_ammonia_freight_ship,
                    technology_bev_freight_ship, technology_fcev_freight_ship,
                    bioethanol_in_road_gasoline, biodiesel_in_road_diesel, biodiesel_in_rail_diesel,
                    biodiesel_in_internal_navigation_diesel, biokerosene_in_internal_aviation_fuel,
                    ice_fuel_in_plugin_hybrid
                ) = share_technology(country, year=2019)

                # Check if OECD data is missing (LDV shares are all zero) - fall back to default country
                ldv_total = technology_gasoline_ice_ldv + technology_diesel_ice_ldv + technology_lpg_ice_ldv
                if ldv_total == 0 and country != DEFAULT_TECH_COUNTRY:
                    print(f"   -> INFO: {country} has no OECD technology data, using default column values from trans_config")
                    (
                        technology_gasoline_ice_ldv, technology_diesel_ice_ldv, technology_lpg_ice_ldv,
                        technology_bev_ldv, technology_fcev_ldv,
                        technology_diesel_plugin_hybrid_ldv, technology_gasoline_plugin_hybrid_ldv,
                        technology_diesel_ice_bus, technology_bev_bus, technology_fcev_bus, technology_diesel_plugin_hybrid_bus,
                        technology_gasoline_ice_2_and_3w, technology_bev_two_three_wheeler,
                        technology_fcev_passenger_train,
                        technology_kerosene_passenger_plane, technology_bev_passenger_plane, technology_fcev_passenger_plane,
                        technology_diesel_ice_ldt, technology_bev_ldt, technology_fcev_ldt, technology_diesel_plugin_hybrid_ldt,
                        technology_diesel_ice_hdt, technology_bev_hdt, technology_fcev_hdt, technology_diesel_plugin_hybrid_hdt,
                        technology_fcev_freight_train,
                        technology_diesel_ice_freight_ship, technology_methanol_freight_ship, technology_ammonia_freight_ship,
                        technology_bev_freight_ship, technology_fcev_freight_ship,
                        bioethanol_in_road_gasoline, biodiesel_in_road_diesel, biodiesel_in_rail_diesel,
                        biodiesel_in_internal_navigation_diesel, biokerosene_in_internal_aviation_fuel,
                        ice_fuel_in_plugin_hybrid
                    ) = share_technology(DEFAULT_TECH_COUNTRY, year=2019)

                # Direct electric train share (percent); diesel is complement
                try:
                    direct_train_pct = float(df_direct_elec.loc[country, "2020.0"])
                except Exception:
                    direct_train_pct = 0.0
                diesel_train_pct = 100.0 - direct_train_pct

                tech_base = {
                    "Share of Technology - Gasoline ICE LDV": technology_gasoline_ice_ldv,
                    "Share of Technology - Diesel ICE LDV": technology_diesel_ice_ldv,
                    "Share of Technology - LPG ICE LDV": technology_lpg_ice_ldv,
                    "Share of Technology - BEV LDV": technology_bev_ldv,
                    "Share of Technology - FCEV LDV": technology_fcev_ldv,
                    "Share of Technology - Diesel Plugin Hybrid LDV": technology_diesel_plugin_hybrid_ldv,
                    "Share of Technology - Gasoline Plugin Hybrid LDV": technology_gasoline_plugin_hybrid_ldv,
                    "Share of Technology - Diesel ICE Bus": technology_diesel_ice_bus,
                    "Share of Technology - BEV Bus": technology_bev_bus,
                    "Share of Technology - FCEV Bus": technology_fcev_bus,
                    "Share of Technology - Diesel Plugin Hybrid Bus": technology_diesel_plugin_hybrid_bus,
                    "Share of Technology - Gasoline ICE 2&3W": technology_gasoline_ice_2_and_3w,
                    "Share of Technology - BEV 2&3W": technology_bev_two_three_wheeler,
                    "Share of Technology - Diesel ICE Passenger Train": diesel_train_pct,
                    "Share of Technology - Direct Electric Passenger Train": direct_train_pct,
                    "Share of Technology - FCEV Passenger Train": technology_fcev_passenger_train,
                    "Share of Technology - Kerosene Passenger Plane": technology_kerosene_passenger_plane,
                    "Share of Technology - BEV Passenger Plane": technology_bev_passenger_plane,
                    "Share of Technology - FCEV Passenger Plane": technology_fcev_passenger_plane,
                    "Share of Technology - Diesel ICE LDT": technology_diesel_ice_ldt,
                    "Share of Technology - BEV LDT": technology_bev_ldt,
                    "Share of Technology - FCEV LDT": technology_fcev_ldt,
                    "Share of Technology - Diesel Plugin Hybrid LDT": technology_diesel_plugin_hybrid_ldt,
                    "Share of Technology - Diesel ICE HDT": technology_diesel_ice_hdt,
                    "Share of Technology - BEV HDT": technology_bev_hdt,
                    "Share of Technology - FCEV HDT": technology_fcev_hdt,
                    "Share of Technology - Diesel Plugin Hybrid HDT": technology_diesel_plugin_hybrid_hdt,
                    "Share of Technology - Diesel ICE Freight Train": diesel_train_pct,
                    "Share of Technology - Direct Electric Freight Train": direct_train_pct,
                    "Share of Technology - FCEV Freight Train": technology_fcev_freight_train,
                    "Share of Technology - Diesel ICE Freight Ship": technology_diesel_ice_freight_ship,
                    "Share of Technology - Methanol Freight Ship": technology_methanol_freight_ship,
                    "Share of Technology - Ammonia Freight Ship": technology_ammonia_freight_ship,
                    "Share of Technology - BEV Freight Ship": technology_bev_freight_ship,
                    "Share of Technology - FCEV Freight Ship": technology_fcev_freight_ship,
                    "Share of Bioethanol in Road Gasoline": bioethanol_in_road_gasoline,
                    "Share of Biodiesel in Road Diesel": biodiesel_in_road_diesel,
                    "Share of Biodiesel in Rail Diesel": biodiesel_in_rail_diesel,
                    "Share of Biodiesel in Internal Navigation Diesel": biodiesel_in_internal_navigation_diesel,
                    "Share of Biokerosene in Internal Aviation Fuel": biokerosene_in_internal_aviation_fuel,
                    "Share of ICE Fuel in Plugin Hybrid": ice_fuel_in_plugin_hybrid,
                }

                bunker_fuel_display = {
                    "oil": "Oil",
                    "gas": "Gas",
                    "electricity": "Electricity",
                    "coal": "Coal",
                    "biomass": "Biomass",
                    "heat": "Heat",
                    "hydrogen": "Hydrogen",
                }

                try:
                    aviation_shares = get_unsd_bunker_fuel_shares(
                        base_path=unsd_input_folder,
                        country=country,
                        year=base_year,
                        bunker_type="aviation",
                    )
                    maritime_shares = get_unsd_bunker_fuel_shares(
                        base_path=unsd_input_folder,
                        country=country,
                        year=base_year,
                        bunker_type="marine",
                    )
                except Exception:
                    aviation_shares, maritime_shares = {}, {}

                for fuel_key, display in bunker_fuel_display.items():
                    metric_name_av = f"Share of Technology - {display} Int Aviation"
                    metric_name_ma = f"Share of Technology - {display} Int Maritime"
                    if fuel_key in aviation_shares:
                        tech_base[metric_name_av] = aviation_shares[fuel_key]
                    if fuel_key in maritime_shares:
                        tech_base[metric_name_ma] = maritime_shares[fuel_key]

                def pct(val):
                    if val is None or pd.isna(val):
                        return None
                    try:
                        f = float(val)
                        return f * 100.0 if abs(f) <= 1 else f
                    except Exception:
                        return None

                return {k: pct(tech_base.get(k)) for k in tech_metric_order}

            tech_base_by_country = {c: tech_base_for_country(c) for c in country_names}

            # Base rows (2020) with scenario "Base"
            for metric in tech_metric_order:
                values = [tech_base_by_country.get(c, {}).get(metric) for c in country_names]
                row = ["Base", metric, base_year, "Base", *[format_value(v) for v in values]]
                rows.append(row)

            # Flat projections: copy 2020 value to all target years/scenarios
            for metric in tech_metric_order:
                values = [tech_base_by_country.get(c, {}).get(metric) for c in country_names]
                for year in target_years:
                    for scenario in scenario_names:
                        row = ["Value", metric, year, scenario, *[format_value(v) for v in values]]
                        rows.append(row)

        except Exception as exc:
            print(f"Warning: could not compute technology share rows ({exc})")

        # === Share/Mode/Subsector CAGRs (from config) replicated across countries ===
        # === Share/Mode/Subsector CAGRs computed directly from Khalili source per country ===
        try:
            import pandas as _pd
            from helpers import load_global_transport_data, clean_column_headers, clean_missing_countries
            from build_share_subsectors import split_by_sector, HDT_SHARE_BY_COUNTRY
            from build_share_mode import process_bus_share_data, share_of_two_Three

            df_raw_source = load_global_transport_data()
            df_clean_source = clean_column_headers(clean_missing_countries(df_raw_source))

            # Helper to keep only year columns and set country as index
            def _years_only(df_in):
                df = df_in.copy()
                if "Countries List" in df.columns:
                    df = df.set_index("Countries List")
                year_cols_local = [c for c in df.columns if str(c).replace(".", "", 1).isdigit()]
                return df[year_cols_local].apply(_pd.to_numeric, errors="coerce")

            sector_dfs = split_by_sector(df_clean_source)

            # Mode shares from Khalili (already in %)
            bus_share_df = _years_only(process_bus_share_data(df_raw_source))
            two_three_share_df = _years_only(share_of_two_Three(df_raw_source))

            # HDT share of trucks (stored as fraction); keep as-is for CAGR
            hdt_share_df = HDT_SHARE_BY_COUNTRY.copy()

            # Subsector shares computed from Khalili volumes
            rp = _years_only(sector_dfs.get("road_passenger", _pd.DataFrame()))
            rail_p = _years_only(sector_dfs.get("rail_passenger", _pd.DataFrame()))
            av_p = _years_only(sector_dfs.get("aviation_passenger", _pd.DataFrame()))
            marine_p = _years_only(sector_dfs.get("marine_passenger", _pd.DataFrame()))

            road_f = _years_only(sector_dfs.get("road_freight", _pd.DataFrame()))
            rail_f = _years_only(sector_dfs.get("rail_freight", _pd.DataFrame()))
            av_f = _years_only(sector_dfs.get("aviation_freight", _pd.DataFrame()))
            marine_f = _years_only(sector_dfs.get("marine_freight", _pd.DataFrame()))

            total_passenger = rp.add(rail_p, fill_value=0).add(av_p, fill_value=0).add(marine_p, fill_value=0)
            total_freight = road_f.add(rail_f, fill_value=0).add(av_f, fill_value=0).add(marine_f, fill_value=0)

            def _safe_share(numer, denom):
                share = numer.copy()
                share.loc[:, :] = _pd.NA
                mask = denom > 0
                share[mask] = (numer[mask] / denom[mask]) * 100
                return share

            share_rail_passenger_df = _safe_share(rail_p, total_passenger)
            share_av_passenger_df = _safe_share(av_p, total_passenger)
            share_rail_freight_df = _safe_share(rail_f, total_freight)
            share_nav_freight_df = _safe_share(marine_f, total_freight)

            share_tables = {
                "Share per Mode - Bus": bus_share_df,
                "Share per Mode - 2&3W": two_three_share_df,
                "Share per Mode - HDT": hdt_share_df,
                "Share per Subsector - Rail Passenger = Train": share_rail_passenger_df,
                "Share per Subsector - Aviation Passenger = Plane": share_av_passenger_df,
                "Share per Subsector - Rail Freight = Train": share_rail_freight_df,
                "Share per Subsector - Navigation Freight = Ship": share_nav_freight_df,
            }

            # Base year (2020) levels for share/mode/subsector metrics
            for metric, table in share_tables.items():
                base_values = []
                for country in country_names:
                    if table is None or table.empty or country not in table.index:
                        base_values.append(None)
                        continue

                    def _extract(df, yr):
                        for key in (f"{float(yr)}", f"{yr}", float(yr), yr):
                            if key in df.columns:
                                try:
                                    return float(df.loc[country, key])
                                except Exception:
                                    pass
                        return None

                    val = _extract(table, base_year)
                    if metric == "Share per Mode - HDT" and val is not None and abs(val) <= 1:
                        val = val * 100.0  # express HDT share as percent for output
                    base_values.append(val)

                row = [
                    "Base",
                    metric,
                    base_year,
                    "Base",
                    *[format_value(v) for v in base_values],
                ]
                rows.append(row)

            # CAGR rows for share/mode/subsector metrics
            for metric, table in share_tables.items():
                for target_year, (start_year, end_year) in year_pairs.items():
                    values = []
                    for country in country_names:
                        if table is None or table.empty or country not in table.index:
                            values.append(None)
                            continue

                        def _extract(df, yr):
                            for key in (f"{float(yr)}", f"{yr}", float(yr), yr):
                                if key in df.columns:
                                    try:
                                        return float(df.loc[country, key])
                                    except Exception:
                                        pass
                            return None

                        start_val = _extract(table, start_year)
                        end_val = _extract(table, end_year)
                        values.append(calc_cagr(start_val, end_val, end_year - start_year))

                    for scenario in scenario_names:
                        row = [
                            "CAGR",
                            metric,
                            target_year,
                            scenario,
                            *[format_fraction(v) for v in values],
                        ]
                        rows.append(row)

        except Exception as exc:
            print(f"Warning: could not compute share/mode/subsector CAGRs from Khalili ({exc})")

    # === International bunker totals (Final Energy) with default 0% CAGR ===
    bunker_total_metrics = [
        "Final Energy - Int. Maritime",
        "Final Energy - Int. Aviation",
    ]

    for metric in bunker_total_metrics:
        for target_year in target_years:
            for scenario in scenario_names:
                row = [
                    "CAGR",
                    metric,
                    target_year,
                    scenario,
                    *[format_fraction(0.0) for _ in country_names],
                ]
                rows.append(row)

    # === Order rows: 2020 first, then 2030-2050; metrics in requested order ===
    desired_metric_order = [
        "Population",
        "Mobility per capita - Passenger",
        "Share per Subsector - Road Passenger",
        "Share per Subsector - Rail Passenger = Train",
        "Share per Subsector - Aviation Passenger = Plane",
        "Share per Mode - LDV",
        "Share per Mode - Bus",
        "Share per Mode - 2&3W",
        "Load Factor - LDV",
        "Load Factor - Bus",
        "Load Factor - 2&3W",
        "Load Factor - Passenger Train",
        "Load Factor - Passenger Plane",
        "Share of Technology - Gasoline ICE LDV",
        "Share of Technology - Diesel ICE LDV",
        "Share of Technology - LPG ICE LDV",
        "Share of Technology - BEV LDV",
        "Share of Technology - FCEV LDV",
        "Share of Technology - Diesel Plugin Hybrid LDV",
        "Share of Technology - Gasoline Plugin Hybrid LDV",
        "Share of Technology - Diesel ICE Bus",
        "Share of Technology - BEV Bus",
        "Share of Technology - FCEV Bus",
        "Share of Technology - Diesel Plugin Hybrid Bus",
        "Share of Technology - Gasoline ICE 2&3W",
        "Share of Technology - BEV 2&3W",
        "Share of Technology - Diesel ICE Passenger Train",
        "Share of Technology - Direct Electric Passenger Train",
        "Share of Technology - FCEV Passenger Train",
        "Share of Technology - Kerosene Passenger Plane",
        "Share of Technology - BEV Passenger Plane",
        "Share of Technology - FCEV Passenger Plane",
        "Final Energy Intensity - Gasoline ICE LDV",
        "Final Energy Intensity - Diesel ICE LDV",
        "Final Energy Intensity - LPG ICE LDV",
        "Final Energy Intensity - BEV LDV",
        "Final Energy Intensity - FCEV LDV",
        "Final Energy Intensity - Diesel Plugin Hybrid LDV",
        "Final Energy Intensity - Gasoline Plugin Hybrid LDV",
        "Final Energy Intensity - Diesel ICE Bus",
        "Final Energy Intensity - BEV Bus",
        "Final Energy Intensity - FCEV Bus",
        "Final Energy Intensity - Diesel Plugin Hybrid Bus",
        "Final Energy Intensity - Gasoline ICE 2&3W",
        "Final Energy Intensity - BEV 2&3W",
        "Final Energy Intensity - Diesel ICE Passenger Train",
        "Final Energy Intensity - Direct Electric Passenger Train",
        "Final Energy Intensity - FCEV Passenger Train",
        "Final Energy Intensity - Kerosene Passenger Plane",
        "Final Energy Intensity - BEV Passenger Plane",
        "Final Energy Intensity - FCEV Passenger Plane",
        "Mobility per capita - Freight",
        "Share per Subsector - Road Freight",
        "Share per Subsector - Rail Freight = Train",
        "Share per Subsector - Navigation Freight = Ship",
        "Share per Mode - LDT",
        "Share per Mode - HDT",
        "Load Factor - LDT",
        "Load Factor - HDT",
        "Load Factor - Freight Train",
        "Load Factor - Freight Ship",
        "Share of Technology - Diesel ICE LDT",
        "Share of Technology - BEV LDT",
        "Share of Technology - FCEV LDT",
        "Share of Technology - Diesel Plugin Hybrid LDT",
        "Share of Technology - Diesel ICE HDT",
        "Share of Technology - BEV HDT",
        "Share of Technology - FCEV HDT",
        "Share of Technology - Diesel Plugin Hybrid HDT",
        "Share of Technology - Diesel ICE Freight Train",
        "Share of Technology - Direct Electric Freight Train",
        "Share of Technology - FCEV Freight Train",
        "Share of Technology - Diesel ICE Freight Ship",
        "Share of Technology - Methanol Freight Ship",
        "Share of Technology - Ammonia Freight Ship",
        "Share of Technology - BEV Freight Ship",
        "Share of Technology - FCEV Freight Ship",
        "Final Energy Intensity - Diesel ICE LDT",
        "Final Energy Intensity - BEV LDT",
        "Final Energy Intensity - FCEV LDT",
        "Final Energy Intensity - Diesel Plugin Hybrid LDT",
        "Final Energy Intensity - Diesel ICE HDT",
        "Final Energy Intensity - BEV HDT",
        "Final Energy Intensity - FCEV HDT",
        "Final Energy Intensity - Diesel Plugin Hybrid HDT",
        "Final Energy Intensity - Diesel ICE Freight Train",
        "Final Energy Intensity - Direct Electric Freight Train",
        "Final Energy Intensity - FCEV Freight Train",
        "Final Energy Intensity - Diesel Freight Ship",
        "Final Energy Intensity - Methanol Freight Ship",
        "Final Energy Intensity - Ammonia Freight Ship",
        "Final Energy Intensity - BEV Freight Ship",
        "Final Energy Intensity - FCEV Freight Ship",
        "Share of Bioethanol in Road Gasoline",
        "Share of Biodiesel in Road Diesel",
        "Share of Biodiesel in Rail Diesel",
        "Share of Biodiesel in Internal Navigation Diesel",
        "Share of Biokerosene in Internal Aviation Fuel",
        "Share of ICE Fuel in Plugin Hybrid",
        "Final Energy - Int. Maritime",
        "Final Energy - Int. Aviation",
        "Share of Technology - Electricity International Aviation",
        "Share of Technology - Hydrogen International Maritime",
        "Share of Technology - Gas International Maritime",
        "Share of Technology - Electricity International Maritime",
        "Share of Technology - Oil International Aviation",
        "Share of Technology - Gas International Aviation",
        "Share of Technology - Biomass International Maritime",
        "Share of Technology - Biomass International Aviation",
        "Share of Technology - Hydrogen International Aviation",
        "Share of Technology - Oil International Maritime",
    ]

    metric_rank = {m: i for i, m in enumerate(desired_metric_order)}
    year_rank = {base_year: 0, **{year: idx + 1 for idx, year in enumerate(target_years)}}
    scenario_rank = {"Base": 0, "BAU": 1, "Progressive": 2, "Optimistic": 3}

    df = pd.DataFrame(rows[1:], columns=header)
    # Drop base-year rows entirely; downstream pipeline will source 2020 bases from raw inputs
    df = df[~((df["Year"] == base_year) & (df["Scenario"] == "Base"))]

    # Insert a default column (after Scenario) using Morocco's values as the default
    country_cols = [c for c in df.columns if c not in ["Assumption Type", "Metric Name", "Year", "Scenario"]]

    def pick_default(row):
        # Use Morocco as the default reference country
        if "Morocco" in row.index:
            val = row["Morocco"]
            if pd.notna(val) and str(val) != "":
                return val
        # Fallback: use first non-empty country value if Morocco is unavailable
        for col in country_cols:
            val = row[col]
            if pd.notna(val) and str(val) != "":
                return val
        return ""

    df.insert(4, "default", df.apply(pick_default, axis=1))

    # Reorder columns to keep default beside Scenario
    ordered_cols = ["Assumption Type", "Metric Name", "Year", "Scenario", "default", *country_cols]
    df = df[ordered_cols]

    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")

    df["__year_rank"] = df["Year"].apply(lambda y: year_rank.get(int(y), len(year_rank)))
    df["__metric_rank"] = df["Metric Name"].apply(lambda m: metric_rank.get(m, len(metric_rank)))
    df["__scenario_rank"] = df["Scenario"].apply(lambda s: scenario_rank.get(s, len(scenario_rank)))

    # Group by metric first (all scenarios/years together), then by year, then scenario
    df.sort_values(by=["__metric_rank", "__year_rank", "__scenario_rank"], inplace=True)
    df.drop(columns=["__year_rank", "__metric_rank", "__scenario_rank"], inplace=True)

    os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)
    df.to_csv(output_csv_path, index=False)

    return output_csv_path


if __name__ == "__main__":
    # =========================================================================
    # OPTION 1: Use the existing CAGR calculation (current workflow)
    # =========================================================================
    print("\n" + "="*60)
    print("OPTION 1: Original CAGR Workflow")
    print("="*60)
    export_final_energy_intensity_cagr_with_intermediate()
    print("[OK] Generated: trans_config.csv with existing CAGR values")
    
    # =========================================================================
    # OPTION 2: Use the new rolling CAGR calculation
    # =========================================================================
    print("\n" + "="*60)
    print("OPTION 2: New Rolling CAGR Workflow")
    print("="*60)
    
    if not ROLLING_CAGR_DF.empty:
        # Export rolling CAGR analysis for inspection
        rolling_cagr_path = export_rolling_cagr_analysis(ROLLING_CAGR_DF)
        
        # View sample of suggested CAGRs
        print("\nSample of suggested CAGRs (by country-sector):")
        sample_df = ROLLING_CAGR_DF[["country", "sector", "CAGR", "CAGR_capped", "suggested_cagr"]].drop_duplicates(["country", "sector"]).head(10)
        print(sample_df.to_string(index=False))
        
        # Convert rolling CAGR suggestions to CAGR matrix format
        rolling_cagr_matrix = build_cagr_matrix_from_rolling(ROLLING_CAGR_DF)
        print(f"\n[OK] Generated CAGR matrix from rolling calculations: {len(rolling_cagr_matrix)} metrics")
    else:
        print("[!] Rolling CAGR DataFrame is empty - skipping export")
    
    # =========================================================================
    # USAGE TIPS
    # =========================================================================
    print("\n" + "="*60)
    print("USAGE TIPS")
    print("="*60)
    print("""
To use rolling CAGR values in the config export:

1. **View rolling CAGR analysis:** 
   rolling_cagr_analysis.csv contains:
   - Original CAGR (per year-pair)
   - IQR outlier bounds
   - Capped CAGR (outliers removed)
   - Suggested CAGR (average of capped values)

2. **Query suggested CAGR:**
   >>> cagr = get_suggested_cagr_by_country_sector(
   ...     ROLLING_CAGR_DF, 
   ...     country="Brazil", 
   ...     sector="Road - Passenger LDV"
   ... )
   >>> print(f"Suggested CAGR: {cagr*100:.2f}%")

3. **Use rolling CAGR matrix:**
   >>> cagr_matrix = build_cagr_matrix_from_rolling(ROLLING_CAGR_DF)
   >>> # Modify export function to use this matrix instead of CAGR_VALUES
   >>> export_final_energy_intensity_cagr_with_intermediate(
   ...     cagr_values=rolling_cagr_matrix,
   ...     output_csv_path="transport/output_data/trans_config_rolling_cagr.csv"
   ... )

4. **Compare both approaches:**
   - Check rolling_cagr_analysis.csv for data-driven CAGR values
   - Check trans_config.csv for literature-based CAGR values
   - Use rolling CAGR if your data is reliable; use literature CAGR for expert inputs
    """)
