import re
from pathlib import Path
from typing import List, Optional
from functools import reduce
import pycountry
import pandas as pd
from industry.helpers import get_historical_sector_data
import numpy as _np
from industry.scripts.chemical_and_petrochemical.ammonia.build_ammonia import (
    AMMONIA_SCENARIO_XLSX,
    AMMONIA_SCENARIO_SHEET,
    AMMONIA_MWH_PER_TON,
    BASE_YEAR,
    unsd_path,
    AMMONIA_VOLUMES_CSV,
    _PIPELINE_TO_VOLUME_PATH,
)

# Single source of truth for scenario names
from industry.build_config_industry import SCENARIOS

# Path to industry config file for CAGR values
industry_config_path = Path(__file__).resolve().parent / "industry_config.csv"


# Set to None to auto-find the latest, or set to a specific folder name
choose_folder = "country_parameters"

# Countries to run – you just edit this list
available_countries = ["Morocco", "Egypt","South Africa","Namibia"]
                        #"Republic of the Congo", "Egypt", "Ethiopia", "Ghana","Kenya","Namibia","Niger",
                        # "Algeria","Argentina","Brazil","Chile","Colombia","Mexico","Peru","Venezuela",
                        #"Morocco","Tunisia","Tanzania", "South Africa","Libya",

                        #G20 countries
                        #"Argentina", "Australia", "Brazil", "Canada", "China", "France", "Germany",  
                        #"India", "Indonesia", "Italy", "Japan", "Mexico","Russia", "Saudi Arabia", 
                        #"South Africa", "South Korea", "United Kingdom", "United States"]


# Order of carriers in the new "carrier" sheet
CARRIER_ORDER = [
    "oil",
    "gas",
    "electricity",
    "coal",
    "heat",
    "biomass",
    "hydrogen",
    "ammonia",
    "methanol",
    "steel",
]

FUELS_ORDER = ["Diesel", "Natural Gas", "Electricity", "Coal", "Heat", "Biomass", "Hydrogen"]

# Internal detailed structure (for building from metrics workbook)
COL_ORDER = [
    "Year", "Sector", "Sub sector", "Product", "Process", "Technology",
    "Dropdown", "Fuel/Feedstock", "Level", "Description",
    "Total Production / Value Added", "Share per Process", "Production per Process",
    "Share per Technology", "Production per Process and Technology",
    "Share per Fuel", "Production per Process, Technology and Fuel",
    "Specific fuel intensity", "final energy demand", "Scenario_col"
]

# Row order for SEC sheet
ROW_ORDER = ["Total", "Oil", "Gas", "Electricity", "Coal", "Heat", "Biomass", "Hydrogen", "Ammonia", "Methanol", "Steel"]

FUEL_TO_SEC = {
    "Diesel": "Oil", "oil": "Oil",
    "Natural Gas": "Gas", "gas": "Gas",
    "Electricity": "Electricity", "electricity": "Electricity",
    "Coal": "Coal", "coal": "Coal",
    "Heat": "Heat",  "heat": "Heat",
    "Biomass": "Biomass", "biomass": "Biomass",
    "Hydrogen": "Hydrogen",  "hydrogen": "Hydrogen",
    "Ammonia": "Ammonia", "ammonia": "Ammonia",
    "Methanol": "Methanol", "methanol": "Methanol",
    "Steel": "Steel", "steel": "Steel",
}

# Sector-specific SEC columns
NMM_SEC_COLS = ["Industry NMM Cement", "Industry NMM Other"]
PP_SEC_COLS = [
    "Industry Paper and pulp Pulp Primary",
    "Industry Paper and pulp Pulp Secondary",
    "Industry Paper and pulp Paper",
]
STEEL_SEC_COLS = [
    "Industry Steel Primary Blast Furnace Open Hearth Furnace",
    "Industry Steel Primary Blast Furnace Basic Oxygen Furnace",
    "Industry Steel Primary DRI",
    "Industry Steel Secondary EAF",
    "Industry Steel Casting Rolling Finishing",
    "Industry Steel Other",
]
AMMONIA_SEC_COLS = [
    "Industry Chemical Ammonia SMR",
    "Industry Chemical Ammonia Other conventional",
    "Industry Chemical Ammonia Renewable",
    "Industry Chemical HVC Naphtha",
    "Industry Chemical HVC LPG",
    "Industry Chemical HVC Methanol",
]

OTHER_SEC_COLS = [
    "Industry Machinery",
    "Industry Construction",
    "Industry Non-ferrous Metals",
    "Industry Transport Equipment",
    "Industry Food and Tobacco",
    "Industry Mining and Quarrying",
    "Industry Textile and Leather",
    "Industry Wood and Wood Products",
]
# -------------------------------------------------------------------
# CAGR PROJECTION FUNCTIONS (aligned with transport)
# -------------------------------------------------------------------

def get_config_scenario_name(scenario_from_column: str) -> str:
    """
    Return the scenario name as-is for matching with industry_config.csv.
    industry_config.csv has scenario names like "BAU", "Progressive", "Optimistic".
    """
    return scenario_from_column


def get_aggregate_metric_name(metric: str) -> str:
    """
    Map fuel-specific metric names to their aggregate counterparts for CAGR lookup.
    
    Example:
    - "Energy intensity of diesel in blast furnaces + open hearth furnace" 
      -> "Energy intensity of blast furnaces + open hearth furnaces"
    """
    import re
    
    # Fuel types to strip from metric names
    fuels = ["diesel", "natural gas", "electricity", "coal", "heat", "biomass", "hydrogen"]
    
    # Patterns for fuel-specific energy intensity metrics
    # Pattern 1: "Energy intensity of {fuel} in {process}" -> "Energy intensity of {process}"
    # Pattern 2: "Energy intensity of {fuel} for {process}" -> "Energy intensity of {process}"
    
    for fuel in fuels:
        # Pattern: "Energy intensity of {fuel} in {process}"
        pattern_in = rf"Energy intensity of {fuel} in (.+)"
        match = re.match(pattern_in, metric, re.IGNORECASE)
        if match:
            process = match.group(1).strip()
            # Handle singular/plural variations
            if process.endswith("furnace"):
                process = process + "s"  # furnace -> furnaces
            return f"Energy intensity of {process}"
        
        # Pattern: "Energy intensity of {fuel} for {process}"
        pattern_for = rf"Energy intensity of {fuel} for (.+)"
        match = re.match(pattern_for, metric, re.IGNORECASE)
        if match:
            process = match.group(1).strip()
            return f"Energy intensity of {process}"
    
    # Return original if no fuel-specific pattern matched
    return metric


def apply_share_overrides(df: pd.DataFrame, config_path: Path, country: str) -> pd.DataFrame:
    """
    Apply SHARE value overrides from industry_config.csv.
    For metrics where user has provided country-specific share values,
    replace the 2020 UNSD defaults with the config values for each year/scenario.
    """
    try:
        config_df = pd.read_csv(config_path)
        share_config = config_df[config_df['Assumption Type'] == 'SHARE']
    except Exception as e:
        print(f"  Warning: Error loading SHARE config: {e}")
        return df

    if share_config.empty:
        return df

    # Build a lookup: metric_name -> {(year, scenario) -> value}
    share_lookup = {}
    for _, row in share_config.iterrows():
        metric_name = str(row['Metric Name']).strip()
        year = int(row['Year'])
        scenario = str(row['Scenario']).strip()
        
        # Get country value - check if it's set (including 0)
        val = row.get(country)
        country_has_value = not (pd.isna(val) or val == "")
        
        if not country_has_value:
            # Fall back to default
            val = row.get('default')
            default_has_value = not (pd.isna(val) or val == "")
            if not default_has_value:
                continue  # Skip only if BOTH country AND default are empty
            
        if metric_name not in share_lookup:
            share_lookup[metric_name] = {}
        share_lookup[metric_name][(year, scenario)] = float(val)

    # Identify columns to update
    all_cols = [c for c in df.columns if c not in ["Metric", "Units"]]

    def extract_year(column_name):
        digits = "".join(filter(str.isdigit, str(column_name)))
        return int(digits) if digits else None

    for index, row in df.iterrows():
        metric = str(row['Metric']).strip()
        
        if metric not in share_lookup:
            continue
        
        for col in all_cols:
            year = extract_year(col)
            if year is None or year == 2020:
                continue  # Don't override 2020 base values
            
            # Identify the scenario from column name (e.g., "2030_BAU" → "BAU")
            scenario_from_col = None
            for scn_name in SCENARIOS:
                if scn_name in str(col):
                    scenario_from_col = scn_name
                    break
            
            if scenario_from_col is None:
                continue
            
            # Map column scenario name to config scenario name
            scenario_for_lookup = get_config_scenario_name(scenario_from_col)
            
            # Look up the value
            key = (year, scenario_for_lookup)
            if key in share_lookup[metric]:
                new_val = share_lookup[metric][key]
                # Apply the share value directly
                df.at[index, col] = new_val

    return df


def apply_cagr_projections(df: pd.DataFrame, config_path: Path, country: str, base_year: str = "2020") -> pd.DataFrame:
    """
    Chain-linked CAGR calculation (aligned with transport):
    - 2030 is projected from 2020
    - 2035 is projected from 2030
    - 2040 is projected from 2035, and so on.
    
    Reads CAGR values from industry_config.csv and applies them to recalculate
    metric values based on updated 2020 base values.
    """
    try:
        config_df = pd.read_csv(config_path)
        # Filter for rows where Assumption Type is CAGR
        cagr_config = config_df[config_df['Assumption Type'] == 'CAGR']
    except Exception as e:
        print(f"  Warning: Error loading CAGR config: {e}")
        return df

    # Identify and sort milestone years present in the dataframe columns
    all_cols = [c for c in df.columns if c not in ["Metric", "Units"]]

    def extract_year(column_name):
        digits = "".join(filter(str.isdigit, str(column_name)))
        return int(digits) if digits else None

    # Get sorted list of unique numeric years: [2020, 2030, 2035, 2040, 2045, 2050]
    unique_years = sorted(list(set(extract_year(c) for c in all_cols if extract_year(c) is not None)))
    if len(unique_years) < 2:
        return df

    # Iterate through the intervals (e.g., 2020-2030, 2030-2035, 2035-2040)
    for i in range(1, len(unique_years)):
        prev_yr_num = unique_years[i - 1]
        curr_yr_num = unique_years[i]
        interval_length = curr_yr_num - prev_yr_num
        
        # Get all columns belonging to the current target year
        curr_year_cols = [c for c in all_cols if extract_year(c) == curr_yr_num]

        for index, row in df.iterrows():
            metric = str(row['Metric']).strip()
            
            for col in curr_year_cols:
                # Identify the scenario from column name (e.g., "2030_BAU" → "BAU")
                scenario_from_col = None
                for scn_name in SCENARIOS:
                    if scn_name in str(col):
                        scenario_from_col = scn_name
                        break
                
                if scenario_from_col is None:
                    scenario_for_lookup = "all"
                else:
                    scenario_for_lookup = get_config_scenario_name(scenario_from_col)

                # Find the specific CAGR for this Metric, Year, and Scenario
                match = cagr_config[
                    (cagr_config['Metric Name'] == metric) &
                    (cagr_config['Year'] == curr_yr_num) &
                    (cagr_config['Scenario'].str.lower() == scenario_for_lookup.lower())
                ]

                if match.empty:
                    # Fallback to any scenario for this metric/year
                    match = cagr_config[
                        (cagr_config['Metric Name'] == metric) &
                        (cagr_config['Year'] == curr_yr_num)
                    ]

                # If still no match, try the aggregate metric name (for fuel-specific metrics)
                if match.empty:
                    aggregate_metric = get_aggregate_metric_name(metric)
                    if aggregate_metric != metric:
                        match = cagr_config[
                            (cagr_config['Metric Name'] == aggregate_metric) &
                            (cagr_config['Year'] == curr_yr_num) &
                            (cagr_config['Scenario'].str.lower() == scenario_for_lookup.lower())
                        ]
                        if match.empty:
                            # Fallback to any scenario for aggregate metric/year
                            match = cagr_config[
                                (cagr_config['Metric Name'] == aggregate_metric) &
                                (cagr_config['Year'] == curr_yr_num)
                            ]

                if not match.empty:
                    # Get country value or default
                    cagr_val = match.iloc[0].get(country)
                    if pd.isna(cagr_val) or cagr_val == "":
                        cagr_val = match.iloc[0].get('default')

                    if not pd.isna(cagr_val) and cagr_val != "":
                        cagr = float(cagr_val)

                        # Find the corresponding base value from the PREVIOUS milestone
                        suffix = str(col).split("_", 1)[1] if "_" in str(col) else ""
                        prev_col_name = f"{prev_yr_num}_{suffix}" if suffix else str(prev_yr_num)

                        # Fallback if specific scenario didn't exist in prev year
                        if prev_col_name not in df.columns:
                            prev_col_name = str(prev_yr_num)

                        if prev_col_name in df.columns:
                            base_val = float(df.at[index, prev_col_name])
                            # CHAINED CALCULATION: New Value = Prev_Value * (1 + CAGR)^interval
                            new_val = base_val * ((1 + cagr) ** interval_length)
                            
                            # Safety cap for share metrics
                            if "Share" in metric:
                                new_val = min(100.0, max(0.0, new_val))

                            df.at[index, col] = new_val

    return df


# -------------------------------------------------------------------
# PATH HELPERS
# -------------------------------------------------------------------
def get_iso_code(country_name: str) -> str:
    """
    Dynamically finds the ISO 2-letter code for a given country name.
    Returns 'XX' if not found.
    """
    try:
        # search_fuzzy is robust; handles "South Korea", "Republic of the Congo", etc.
        result = pycountry.countries.search_fuzzy(country_name)
        if result:
            return getattr(result[0], "alpha_2", "XX")
    except (LookupError, AttributeError):
        pass
    
    print(f"Warning: Could not find ISO code for '{country_name}'. Defaulting to 'XX'.")
    return "XX"

def get_industry_root() -> Path:
    """
    Assumes this file is placed in:
    .../subsector_workflows/industry/
    Returns that 'industry' folder path.
    """
    return Path(__file__).resolve().parent


def get_output_data_folder() -> Path:
    """
    Returns: .../industry/output_data
    """
    root = get_industry_root()
    out_dir = root / "output_data"
    if not out_dir.exists():
        raise FileNotFoundError(f"output_data folder not found at: {out_dir}")
    return out_dir


def find_latest_run_folder() -> Path:
    """
    Inside output_data, find either the manually selected folder 
    or the most recent folder (by modified time).
    """
    output_data = get_output_data_folder()
    
    # 1. Check for manual selection first
    if choose_folder:
        target = output_data / choose_folder
        if target.exists() and target.is_dir():
            print(f"--- Using selected folder: {choose_folder} ---")
            return target
        else:
            print(f"Warning: Selected folder '{choose_folder}' not found. Searching for latest...")

    # 2. Fallback: Find the most recent folder
    subdirs = [p for p in output_data.iterdir() if p.is_dir()]
    if not subdirs:
        raise FileNotFoundError(f"No run folders found in: {output_data}")

    latest = max(subdirs, key=lambda p: p.stat().st_mtime)
    print(f"--- Using latest run folder: {latest.name} ---")
    return latest


def find_country_file(run_folder: Path, country: str) -> Path:
    """
    Search inside run_folder for a .csv whose name contains the country.
    Example: 'Morocco_Output.csv', 'Egypt_Output.csv', ...
    """
    country_lower = country.lower()
    candidates = [
        p for p in run_folder.glob("*.csv")
        if country_lower in p.stem.lower()
    ]

    if not candidates:
        raise FileNotFoundError(
            f"No CSV file found for country '{country}' in {run_folder}"
        )

    public_candidates = [
        p for p in candidates
        if p.stem.lower().endswith("_output")
    ]
    if public_candidates:
        return sorted(public_candidates)[0]

    # If multiple, just take the first one (you can refine later)
    return sorted(candidates)[0]


def get_results_folder(country: str) -> Path:
    """
    Create (if needed) .../industry/output_data/country_specific/<Country> and return it.
    Aligned with transport folder structure.
    """
    root = get_industry_root()
    results_root = root / "output_data" / "country_specific"
    results_root.mkdir(parents=True, exist_ok=True)

    country_folder = results_root / country.replace(" ", "_")
    country_folder.mkdir(exist_ok=True)
    return country_folder


def build_sec_other_from_output(df_output: pd.DataFrame, country_name: str) -> pd.DataFrame:
    frames = []
    # Ensure these match the EXACT string in your "Metric" column in Morocco_Output
    sector_map = {
        "machinery": "Industry Machinery",
        "construction": "Industry Construction",
        "non-ferrous metals": "Industry Non-ferrous Metals",
        "transport equipment": "Industry Transport Equipment",
        "food and tobacco": "Industry Food and Tobacco",
        "mining and quarrying": "Industry Mining and Quarrying",
        "textile and leather": "Industry Textile and Leather",
        "wood and wood products": "Industry Wood and Wood Products"
    }

    TARGET_FUELS = ["Diesel", "Natural Gas", "Electricity", "Coal", "Heat", "Biomass", "Hydrogen", "Ammonia", "Methanol", "Steel"]
    scenario_cols = [c for c in df_output.columns if c not in ["Metric", "Units"]]

    sector_meta = {
        "machinery": {"csv_name": "Machinery", "metric_name": "final energy of machinery"},
        "construction": {"csv_name": "Construction", "metric_name": "final energy of construction"},
        "non-ferrous metals": {"csv_name": "Non-ferrous metals", "metric_name": "final energy of non-ferrous metals"},
        "transport equipment": {"csv_name": "Transport equipment", "metric_name": "final energy of transport equipment"},
        "food and tobacco": {"csv_name": "Food and tobacco", "metric_name": "final energy of food and tobacco"},
        "mining and quarrying": {"csv_name": "Mining and quarrying", "metric_name": "final energy of mining and quarrying"},
        "textile and leather": {"csv_name": "Textile and leather", "metric_name": "final energy of textile and leather"},
        "wood and wood products": {"csv_name": "Wood and wood products", "metric_name": "final energy of wood and wood products"},
    }

    def _metric_exists(metric_name: str) -> bool:
        return (df_output["Metric"].astype(str).str.strip() == metric_name).any()

    def _interp_history_at(history: dict, year: int) -> float:
        if not history:
            return 0.0
        pts = []
        for y, v in history.items():
            try:
                pts.append((int(y), float(v)))
            except Exception:
                continue
        if not pts:
            return 0.0
        pts = sorted(pts, key=lambda x: x[0])
        years = [p[0] for p in pts]
        vals = [p[1] for p in pts]
        if year <= years[0]:
            return float(vals[0])
        if year >= years[-1]:
            return float(vals[-1])
        for i in range(1, len(years)):
            if years[i - 1] <= year <= years[i]:
                y0, y1 = years[i - 1], years[i]
                v0, v1 = vals[i - 1], vals[i]
                if y1 == y0:
                    return float(v0)
                return float(v0 + (year - y0) * (v1 - v0) / (y1 - y0))
        return float(vals[-1])

    cagr_config = pd.read_csv(industry_config_path) if industry_config_path.exists() else pd.DataFrame()
    if not cagr_config.empty and "Assumption Type" in cagr_config.columns:
        cagr_config = cagr_config[cagr_config["Assumption Type"].astype(str).str.upper() == "CAGR"]
    else:
        cagr_config = pd.DataFrame()

    def _project_other_total_gwh(metric_name: str, base_gwh: float, target_year: int, scenario_name: str, country_name: str) -> float:
        if target_year <= BASE_YEAR:
            return float(base_gwh)
        if cagr_config.empty:
            return float(base_gwh)

        scenario_key = get_config_scenario_name(scenario_name)
        metric_rows = cagr_config[cagr_config["Metric Name"].astype(str).str.strip().str.lower() == str(metric_name).strip().lower()]
        if metric_rows.empty:
            return float(base_gwh)

        milestones = sorted({int(y) for y in metric_rows["Year"].dropna().tolist() if int(y) > BASE_YEAR and int(y) <= target_year})
        if not milestones:
            return float(base_gwh)

        value = float(base_gwh)
        prev = BASE_YEAR

        for milestone in milestones:
            match = metric_rows[
                (metric_rows["Year"] == milestone) &
                (metric_rows["Scenario"].astype(str).str.lower() == scenario_key.lower())
            ]
            if match.empty:
                match = metric_rows[metric_rows["Year"] == milestone]
            if match.empty:
                continue

            row = match.iloc[0]
            cagr_val = row.get(country_name)
            if pd.isna(cagr_val) or str(cagr_val).strip() == "":
                cagr_val = row.get("default")
            if pd.isna(cagr_val) or str(cagr_val).strip() == "":
                cagr = 0.0
            else:
                cagr = float(cagr_val)

            interval = int(milestone) - int(prev)
            if interval > 0:
                value = value * ((1 + cagr) ** interval)
            prev = milestone

        return float(value)

    def _normalize_share(raw_val: float) -> float:
        """
        Normalize shares provided as either fractions (0-1) or percent points (0-100)
        into fractions (0-1).
        """
        try:
            v = float(raw_val)
        except Exception:
            return 0.0
        if pd.isna(v):
            return 0.0
        if v < 0:
            return 0.0
        if v > 1:
            return v / 100.0
        return v

    for col in scenario_cols:
        year = _first_year_in_string(col)
        # Fix: Ensure scenario name is cleaned (e.g., '2030_AP' -> 'AP')
        scenario = col.split("_", 1)[1] if "_" in str(col) else "Historic"
        rows = []

        for metric_key, sec_label in sector_map.items():
            # IMPORTANT: Check if metric name is 'Final energy of food and tobacco' 
            # or 'Final energy demand of food and tobacco'
            metric_with_of = f"Final energy of {metric_key}"
            metric_without_of = f"Final energy {metric_key}"

            has_total_metric = _metric_exists(metric_with_of) or _metric_exists(metric_without_of)
            total_demand = _get_val(df_output, metric_with_of, col, 0.0)
            if total_demand == 0:
                total_demand = _get_val(df_output, metric_without_of, col, 0.0)

            # Transport-style behavior: if totals are not present in the output file,
            # derive them here directly from UNSD history + CAGR assumptions.
            if not has_total_metric:
                meta = sector_meta.get(metric_key, {})
                csv_name = meta.get("csv_name")
                cagr_metric_name = meta.get("metric_name")
                if csv_name and cagr_metric_name and year is not None:
                    history = get_historical_sector_data(unsd_path, country_name, csv_name)
                    base_gwh = _interp_history_at(history, BASE_YEAR)
                    if "_" in str(col):
                        total_demand = _project_other_total_gwh(cagr_metric_name, base_gwh, int(year), scenario, country_name)
                    else:
                        total_demand = base_gwh

            shares = {
                "Diesel": _normalize_share(_get_val(df_output, f"Share of oil for unspecified {metric_key}", col, 0.0)),
                "Natural Gas": _normalize_share(_get_val(df_output, f"Share of gas for unspecified {metric_key}", col, 0.0)),
                "Electricity": _normalize_share(_get_val(df_output, f"Share of electricity for unspecified {metric_key}", col, 0.0)),
                "Coal": _normalize_share(_get_val(df_output, f"Share of coal for unspecified {metric_key}", col, 0.0)),
                "Heat": _normalize_share(_get_val(df_output, f"Share of heat for unspecified {metric_key}", col, 0.0)),
                "Biomass": _normalize_share(_get_val(df_output, f"Share of biomass for unspecified {metric_key}", col, 0.0)),
                "Hydrogen": _normalize_share(_get_val(df_output, f"Share of hydrogen for unspecified {metric_key}", col, 0.0)),
                "Ammonia": _normalize_share(_get_val(df_output, f"Share of ammonia for unspecified {metric_key}", col, 0.0)),
                "Methanol": _normalize_share(_get_val(df_output, f"Share of methanol for unspecified {metric_key}", col, 0.0)),
                "Steel": _normalize_share(_get_val(df_output, f"Share of steel for unspecified {metric_key}", col, 0.0)),
            }

            allocated_total = 0.0
            for fuel_key in TARGET_FUELS:
                share_val = shares.get(fuel_key, 0.0)
                fuel_demand = (total_demand * 1000) * share_val
                allocated_total += fuel_demand
                
                rows.append({
                    "Year": year,
                    "Scenario": scenario,
                    "SEC_Fuel": FUEL_TO_SEC.get(fuel_key, fuel_key),
                    sec_label: fuel_demand
                })

            # Explicit total row: force consistency with carrier rows
            rows.append({
                "Year": year,
                "Scenario": scenario,
                "SEC_Fuel": "Total",
                sec_label: allocated_total,
            })

        if rows:
            df_tmp = pd.DataFrame(rows)
            frames.append(df_tmp)

    if not frames:
        return pd.DataFrame(columns=["Year", "Scenario", "SEC_Fuel"])
        
    df = pd.concat(frames, ignore_index=True)
    piv = df.pivot_table(index=["Year", "Scenario", "SEC_Fuel"], aggfunc="sum", fill_value=0).reset_index()
    return piv


# -------------------------------------------------------------------
# GENERIC SMALL UTILS
# -------------------------------------------------------------------

def _first_year_in_string(txt: str) -> Optional[int]:
    m = re.search(r"(\d{4})", str(txt))
    return int(m.group(1)) if m else None


def _get_val(df: pd.DataFrame, metric: str, col: str, default: float = 0.0) -> float:
    """
    Safely get a single float value from 'df' where Metric == metric, column == col.
    """
    s = df.loc[df["Metric"] == metric, col]
    if s.empty:
        return default
    v = s.iloc[0]
    if pd.isna(v):
        return default
    try:
        return float(v)
    except Exception:
        return default


def _add(
    rows: List[dict],
    year,
    sector,
    subsector,
    product,
    process,
    tech,
    dropdown,
    fuel,
    level,
    desc,
    total_prod,
    share_proc,
    prod_proc,
    share_tech,
    prod_tech,
    share_fuel,
    prod_fuel,
    spec_intensity,
    fuel_demand,
    scenario_col,
):
    """
    Append a row to the internal detailed list with all columns.
    """
    rows.append({
        "Year": year,
        "Sector": sector,
        "Sub sector": subsector,
        "Product": product,
        "Process": process,
        "Technology": tech,
        "Dropdown": dropdown,
        "Fuel/Feedstock": fuel,
        "Level": level,
        "Description": desc,
        "Total Production / Value Added": total_prod if total_prod is not None else "",
        "Share per Process": share_proc if share_proc is not None else "",
        "Production per Process": prod_proc if prod_proc is not None else "",
        "Share per Technology": share_tech if share_tech is not None else "",
        "Production per Process and Technology": prod_tech if prod_tech is not None else "",
        "Share per Fuel": share_fuel if share_fuel is not None else "",
        "Production per Process, Technology and Fuel": prod_fuel if prod_fuel is not None else "",
        "Specific fuel intensity": spec_intensity if spec_intensity is not None else "",
        "final energy demand": fuel_demand if fuel_demand is not None else "",
        "Scenario_col": scenario_col,
    })


def first_year(text: str) -> Optional[int]:
    m = re.search(r"(\d{4})", str(text))
    return int(m.group(1)) if m else None


def parse_year_and_scenario(scol: str):
    """
    Parse 'Scenario_col' like '2020', '2030_Baseline', '2050_Net Zero' into:
      (Year: int, Scenario_label: str)
    """
    y = first_year(scol)
    if "_" in str(scol):
        scen = str(scol).split("_", 1)[1]
    else:
        scen = "Historic"
    return y, scen


def _scenario_to_ammonia_column(scenario_label: str) -> Optional[str]:
    mapping = {
        "Historic": "Baseline - total_production_t",
        "BAU": "Baseline - total_production_t",
        "Progressive": "Ambitious Policies - total_production_t",
        "Optimistic": "Net Zero - total_production_t",
        "Baseline": "Baseline - total_production_t",
        "Ambitious Policies": "Ambitious Policies - total_production_t",
        "Net Zero": "Net Zero - total_production_t",
    }
    return mapping.get(str(scenario_label).strip())


def _load_external_ammonia_mwh(country_name: str, year: int, scenario_label: str) -> float:
    """Return green-path ammonia energy [MWh] from endog_ammonia_green_path in ammonia_volumes.csv.

    Reads endog_ammonia_green_path [kt] for the given country/year/scenario and
    converts to MWh via AMMONIA_MWH_PER_TON.  Falls back to 0.0 if the CSV is
    missing or the country is not found.
    """
    if not AMMONIA_VOLUMES_CSV.exists():
        return 0.0

    vol_path = _PIPELINE_TO_VOLUME_PATH.get(scenario_label)
    if vol_path is None:
        return 0.0

    try:
        df = pd.read_csv(AMMONIA_VOLUMES_CSV)
    except Exception:
        return 0.0

    sub = df[
        (df["path"] == vol_path) &
        (df["country"].astype(str).str.strip().str.lower() == str(country_name).strip().lower())
    ].copy()
    if sub.empty:
        return 0.0

    sub["year"] = pd.to_numeric(sub["year"], errors="coerce")
    sub["endog_ammonia_green_path"] = pd.to_numeric(sub["endog_ammonia_green_path"], errors="coerce")
    sub = sub.dropna(subset=["year", "endog_ammonia_green_path"]).sort_values("year")
    if sub.empty:
        return 0.0

    tons_val = float(_np.interp(int(year), sub["year"].astype(int).to_numpy(),
                                sub["endog_ammonia_green_path"].astype(float).to_numpy()))
    return tons_val * AMMONIA_MWH_PER_TON


# -------------------------------------------------------------------
# STEEL (IRON & STEEL)
# -------------------------------------------------------------------

def _steel_header_subsector(rows, year, scenario_col, sector="Industry", subsector="Iron and Steel"):
    _add(
        rows, year, sector, subsector,
        product="", process="", tech="",
        dropdown="Sub sector", fuel="", level="Sub sector", desc=subsector,
        total_prod="", share_proc="", prod_proc="",
        share_tech="", prod_tech="",
        share_fuel="", prod_fuel="",
        spec_intensity="", fuel_demand="", scenario_col=scenario_col,
    )


def _steel_header_product(rows, year, scenario_col, product, total_prod=None,
                          sector="Industry", subsector="Iron and Steel"):
    _add(
        rows, year, sector, subsector,
        product=product, process="", tech="",
        dropdown="Product", fuel="", level="Product", desc=product,
        total_prod=total_prod, share_proc="", prod_proc="",
        share_tech="", prod_tech="",
        share_fuel="", prod_fuel="",
        spec_intensity="", fuel_demand="", scenario_col=scenario_col,
    )


def _steel_header_process(rows, year, scenario_col, product, process,
                          share_process=None, prod_process=None,
                          sector="Industry", subsector="Iron and Steel"):
    _add(
        rows, year, sector, subsector,
        product=product, process=process, tech="",
        dropdown="Process", fuel="", level="Process", desc=process,
        total_prod="", share_proc=share_process, prod_proc=prod_process,
        share_tech="", prod_tech="",
        share_fuel="", prod_fuel="",
        spec_intensity="", fuel_demand="", scenario_col=scenario_col,
    )


def _steel_header_tech(rows, year, scenario_col, product, process, tech,
                       share_tech=None, prod_tech=None,
                       sector="Industry", subsector="Iron and Steel"):
    _add(
        rows, year, sector, subsector,
        product=product, process=process, tech=tech,
        dropdown="Technology", fuel="", level="Technology", desc=tech,
        total_prod="", share_proc="", prod_proc="",
        share_tech=share_tech, prod_tech=prod_tech,
        share_fuel="", prod_fuel="",
        spec_intensity="", fuel_demand="", scenario_col=scenario_col,
    )


def _steel_fuel_row(rows, year, scenario_col, product, process, tech, fuel,
                    share_fuel=None, prod_fuel=None, spec_intensity=None, fuel_demand=None,
                    sector="Industry", subsector="Iron and Steel"):
    _add(
        rows, year, sector, subsector,
        product=product, process=process, tech=tech,
        dropdown="Fuel", fuel=fuel, level="Fuel", desc=fuel,
        total_prod="", share_proc="", prod_proc="",
        share_tech="", prod_tech="",
        share_fuel=share_fuel, prod_fuel=prod_fuel,
        spec_intensity=spec_intensity, fuel_demand=fuel_demand,
        scenario_col=scenario_col,
    )


def build_iron_steel(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """
    Builds the hierarchical Iron & Steel table for a single scenario column.
    Assumptions:
      - 'Steel production per year' in input is in 100 t/year → we multiply by 100 → t/year.
      - All 'Energy intensity ...' metrics are in MWh/t.
      - Resulting 'final energy demand' is in MWh/year.
    """
    year = _first_year_in_string(col)
    scenario_col = col
    sector = "Industry"
    subsector = "Iron and Steel"

    rows: List[dict] = []

    # Header: Sub sector
    _steel_header_subsector(rows, year, scenario_col, sector=sector, subsector=subsector)

    # Product: Steel (show total production/value here only)
    steel_raw = _get_val(df, "Steel production per year", col, 0.0)
    steel_total = steel_raw   
    _steel_header_product(rows, year, scenario_col, product="Steel", total_prod=steel_total,
                          sector=sector, subsector=subsector)

    # Top-level shares / productions
    share_primary = _get_val(df, "Share of primary steel", col, 0.0) / 100.0
    share_secondary = _get_val(df, "Share of secondary steel = scrap electric arc furnaces", col, 0.0) / 100.0

    prod_primary = steel_total * share_primary     # t/a
    prod_secondary = steel_total * share_secondary # t/a
    prod_casting  = steel_total                    # t/a (casting applies to all steel)

    # ---------------- Primary steel making ----------------
    _steel_header_process(
        rows, year, scenario_col,
        product="Steel", process="Primary steel making",
        share_process=share_primary * 100,      # %
        prod_process=prod_primary,              # t/a
        sector=sector, subsector=subsector
    )

    # Technology shares within Primary
    share_bf_ohf = _get_val(df, "Share of blast furnace + open hearth furnace for steel making", col, 0.0) / 100.0
    share_bf_bof = _get_val(df, "Share of blast furnace + basic oxygen furnace for steel making", col, 0.0) / 100.0
    share_dr_eaf = _get_val(df, "Share of direct reduction + electric arc furnace for steel making", col, 0.0) / 100.0

    # ---- BF+OHF ----
    prod_bf_ohf = prod_primary * share_bf_ohf
    _steel_header_tech(
        rows, year, scenario_col,
        product="Steel", process="Primary steel making",
        tech="Blast Furnace + Open Hearth Furnace",
        share_tech=share_bf_ohf * 100,         # %
        prod_tech=prod_bf_ohf,                 # t/a
        sector=sector, subsector=subsector
    )
    bf_ohf_int = {
        "Diesel":      _get_val(df, "Energy intensity of diesel in blast furnaces + open hearth furnace", col, 0.0),
        "Natural Gas": _get_val(df, "Energy intensity of natural gas in blast furnaces + open hearth furnace", col, 0.0),
        "Electricity": _get_val(df, "Energy intensity of electricity in blast furnaces + open hearth furnace", col, 0.0),
        "Coal":        _get_val(df, "Energy intensity of coal in blast furnaces + open hearth furnace", col, 0.0),
        "Heat":        _get_val(df, "Energy intensity of heat in blast furnaces + open hearth furnace", col, 0.0),
        "Biomass":     _get_val(df, "Energy intensity of biomass in blast furnaces + open hearth furnace", col, 0.0),
        "Hydrogen":    _get_val(df, "Energy intensity of hydrogen in blast furnaces + open hearth furnace", col, 0.0),
    }
    bf_ohf_share = {
        "Diesel":      _get_val(df, "Share of diesel for blast furnaces", col, 0.0) / 100.0,
        "Natural Gas": _get_val(df, "Share of natural gas for blast furnaces", col, 0.0) / 100.0,
        "Electricity": _get_val(df, "Share of electricity for blast furnaces + open hearth furnace", col, 0.0) / 100.0,
        "Coal":        _get_val(df, "Share of coal for blast furnaces + open hearth furnace", col, 0.0) / 100.0,
        "Heat":        _get_val(df, "Share of heat for blast furnaces + open hearth furnace", col, 0.0) / 100.0,
        "Biomass":     _get_val(df, "Share of biomass for blast furnaces + open hearth furnace", col, 0.0) / 100.0,
        "Hydrogen":    _get_val(df, "Share of hydrogen for blast furnaces + open hearth furnace", col, 0.0) / 100.0,
    }
    for f in FUELS_ORDER:
        prod_fuel = prod_bf_ohf * bf_ohf_share[f]                 # t/a
        demand = prod_fuel * bf_ohf_int[f]                        # MWh
        _steel_fuel_row(
            rows, year, scenario_col, "Steel", "Primary steel making",
            "Blast Furnace + Open Hearth Furnace", f,
            share_fuel=bf_ohf_share[f] * 100,               # %
            prod_fuel=prod_fuel,                            # t/a
            spec_intensity=bf_ohf_int[f],                   # MWh/t
            fuel_demand=demand,                             # MWh
            sector=sector, subsector=subsector
        )

    # ---- BF+BOF ----
    prod_bf_bof = prod_primary * share_bf_bof
    _steel_header_tech(
        rows, year, scenario_col,
        product="Steel", process="Primary steel making",
        tech="Blast Furnace + Basic Oxygen Furnace",
        share_tech=share_bf_bof * 100, prod_tech=prod_bf_bof,
        sector=sector, subsector=subsector
    )
    bf_bof_int = {
        "Diesel":      _get_val(df, "Energy intensity of diesel in blast furnaces + basic oxygen furnace", col, 0.0),
        "Natural Gas": _get_val(df, "Energy intensity of natural gas in blast furnaces + basic oxygen furnace", col, 0.0),
        "Electricity": _get_val(df, "Energy intensity of electricity in blast furnaces + basic oxygen furnace", col, 0.0),
        "Coal":        _get_val(df, "Energy intensity of coal in blast furnaces + basic oxygen furnace", col, 0.0),
        "Heat":        _get_val(df, "Energy intensity of heat in blast furnaces + basic oxygen furnace", col, 0.0),
        "Biomass":     _get_val(df, "Energy intensity of biomass in blast furnaces + basic oxygen furnace", col, 0.0),
        "Hydrogen":    _get_val(df, "Energy intensity of hydrogen in blast furnaces + basic oxygen furnace", col, 0.0),
    }
    bf_bof_share = {
        "Diesel":      _get_val(df, "Share of diesel for blast furnaces + basic oxygen furnace", col, 0.0) / 100.0,
        "Natural Gas": _get_val(df, "Share of natural gas for blast furnaces + basic oxygen furnace", col, 0.0) / 100.0,
        "Electricity": _get_val(df, "Share of electricity for blast furnaces + basic oxygen furnace", col, 0.0) / 100.0,
        "Coal":        _get_val(df, "Share of coal for blast furnaces + basic oxygen furnace", col, 0.0) / 100.0,
        "Heat":        _get_val(df, "Share of heat for blast furnaces + basic oxygen furnace", col, 0.0) / 100.0,
        "Biomass":     _get_val(df, "Share of biomass for blast furnaces + basic oxygen furnace", col, 0.0) / 100.0,
        "Hydrogen":    _get_val(df, "Share of hydrogen for blast furnaces + basic oxygen furnace", col, 0.0) / 100.0,
    }
    for f in FUELS_ORDER:
        prod_fuel = prod_bf_bof * bf_bof_share[f]
        demand = prod_fuel * bf_bof_int[f]
        _steel_fuel_row(
            rows, year, scenario_col, "Steel", "Primary steel making",
            "Blast Furnace + Basic Oxygen Furnace", f,
            share_fuel=bf_bof_share[f] * 100, prod_fuel=prod_fuel,
            spec_intensity=bf_bof_int[f], fuel_demand=demand,
            sector=sector, subsector=subsector
        )

    # ---- DR + EAF ----
    prod_dr_eaf = prod_primary * share_dr_eaf
    _steel_header_tech(
        rows, year, scenario_col,
        product="Steel", process="Primary steel making",
        tech="Direct Reduction + Electric Arc Furnace",
        share_tech=share_dr_eaf * 100, prod_tech=prod_dr_eaf,
        sector=sector, subsector=subsector
    )
    dr_eaf_int = {
        "Diesel":      _get_val(df, "Energy intensity of diesel in direct reduction + electric arc furnace", col, 0.0),
        "Natural Gas": _get_val(df, "Energy intensity of natural gas in direct reduction + electric arc furnace", col, 0.0),
        "Electricity": _get_val(df, "Energy intensity of electricity in direct reduction + electric arc furnace", col, 0.0),
        "Coal":        _get_val(df, "Energy intensity of coal in direct reduction + electric arc furnace", col, 0.0),
        "Heat":        _get_val(df, "Energy intensity of heat in direct reduction + electric arc furnace", col, 0.0),
        "Biomass":     _get_val(df, "Energy intensity of biomass in direct reduction + electric arc furnace", col, 0.0),
        "Hydrogen":    _get_val(df, "Energy intensity of hydrogen in direct reduction + electric arc furnace", col, 0.0),
    }
    dr_eaf_share = {
        "Diesel":      _get_val(df, "Share of diesel for direct reduction + electric arc furnace", col, 0.0) / 100.0,
        "Natural Gas": _get_val(df, "Share of natural gas for direct reduction + electric arc furnace", col, 0.0) / 100.0,
        "Electricity": _get_val(df, "Share of electricity for direct reduction + electric arc furnace", col, 0.0) / 100.0,
        "Coal":        _get_val(df, "Share of coal for direct reduction + electric arc furnace", col, 0.0) / 100.0,
        "Heat":        _get_val(df, "Share of heat for direct reduction + electric arc furnace", col, 0.0) / 100.0,
        "Biomass":     _get_val(df, "Share of biomass for direct reduction + electric arc furnace", col, 0.0) / 100.0,
        "Hydrogen":    _get_val(df, "Share of hydrogen for direct reduction + electric arc furnace", col, 0.0) / 100.0,
    }
    for f in FUELS_ORDER:
        prod_fuel = prod_dr_eaf * dr_eaf_share[f]
        demand = prod_fuel * dr_eaf_int[f]
        _steel_fuel_row(
            rows, year, scenario_col, "Steel", "Primary steel making",
            "Direct Reduction + Electric Arc Furnace", f,
            share_fuel=dr_eaf_share[f] * 100, prod_fuel=prod_fuel,
            spec_intensity=dr_eaf_int[f], fuel_demand=demand,
            sector=sector, subsector=subsector
        )

    # ---------------- Secondary steel making ----------------
    _steel_header_process(
        rows, year, scenario_col,
        product="Steel", process="Secondary steel making",
        share_process=share_secondary * 100,     # %
        prod_process=prod_secondary,             # t/a
        sector=sector, subsector=subsector
    )
    _steel_header_tech(
        rows, year, scenario_col,
        product="Steel", process="Secondary steel making",
        tech="Scrap Electric Arc Furnace",
        share_tech=100.0, prod_tech=prod_secondary,
        sector=sector, subsector=subsector
    )
    scrap_int = {
        "Diesel":      _get_val(df, "Energy intensity of diesel in scrap electric arc furnaces", col, 0.0),
        "Natural Gas": _get_val(df, "Energy intensity of natural gas in scrap electric arc furnaces", col, 0.0),
        "Electricity": _get_val(df, "Energy intensity of electricity in scrap electric arc furnaces", col, 0.0),
        "Coal":        _get_val(df, "Energy intensity of coal in scrap electric arc furnaces", col, 0.0),
        "Heat":        _get_val(df, "Energy intensity of heat in scrap electric arc furnaces", col, 0.0),
        "Biomass":     _get_val(df, "Energy intensity of biomass in scrap electric arc furnaces", col, 0.0),
        "Hydrogen":    _get_val(df, "Energy intensity of hydrogen in scrap electric arc furnaces", col, 0.0),
    }
    scrap_share = {
        "Diesel":      _get_val(df, "Share of diesel for scrap electric arc furnaces", col, 0.0) / 100.0,
        "Natural Gas": _get_val(df, "Share of natural gas for scrap electric arc furnaces", col, 0.0) / 100.0,
        "Electricity": _get_val(df, "Share of electricity for scrap electric arc furnaces", col, 0.0) / 100.0,
        "Coal":        _get_val(df, "Share of coal for scrap electric arc furnaces", col, 0.0) / 100.0,
        "Heat":        _get_val(df, "Share of heat for scrap electric arc furnaces", col, 0.0) / 100.0,
        "Biomass":     _get_val(df, "Share of biomass for scrap electric arc furnaces", col, 0.0) / 100.0,
        "Hydrogen":    _get_val(df, "Share of hydrogen for scrap electric arc furnaces", col, 0.0) / 100.0,
    }
    for f in FUELS_ORDER:
        prod_fuel = prod_secondary * scrap_share[f]
        demand = prod_fuel * scrap_int[f]
        _steel_fuel_row(
            rows, year, scenario_col, "Steel", "Secondary steel making",
            "Scrap Electric Arc Furnace", f,
            share_fuel=scrap_share[f] * 100, prod_fuel=prod_fuel,
            spec_intensity=scrap_int[f], fuel_demand=demand,
            sector=sector, subsector=subsector
        )

    # ---------------- Casting, Rolling & Finishing ----------------
    _steel_header_process(
        rows, year, scenario_col,
        product="Steel", process="Casting, Rolling and Finishing",
        share_process=100.0, prod_process=prod_casting,
        sector=sector, subsector=subsector
    )
    _steel_header_tech(
        rows, year, scenario_col,
        product="Steel", process="Casting, Rolling and Finishing",
        tech="Casting, Rolling and Finishing",
        share_tech=100.0, prod_tech=prod_casting,
        sector=sector, subsector=subsector
    )
    casting_intensity = _get_val(df, "Energy intensity of casting, rolling & finishing", col, 0.0)
    cast_shares = {
        "Diesel":      _get_val(df, "Share of diesel for casting, rolling & finishing", col, 0.0) / 100.0,
        "Natural Gas": _get_val(df, "Share of natural gas for casting, rolling & finishing", col, 0.0) / 100.0,
        "Electricity": _get_val(df, "Share of electricity for casting, rolling & finishing", col, 0.0) / 100.0,
        "Coal":        _get_val(df, "Share of coal for casting, rolling & finishing", col, 0.0) / 100.0,
        "Heat":        _get_val(df, "Share of heat for casting, rolling & finishing", col, 0.0) / 100.0,
        "Biomass":     _get_val(df, "Share of biomass for casting, rolling & finishing", col, 0.0) / 100.0,
        "Hydrogen":    _get_val(df, "Share of hydrogen for casting, rolling & finishing", col, 0.0) / 100.0,
    }
    for f in FUELS_ORDER:
        prod_fuel = prod_casting * cast_shares[f]       # t/a
        demand = prod_fuel * casting_intensity          # MWh
        _steel_fuel_row(
            rows, year, scenario_col, "Steel", "Casting, Rolling and Finishing",
            "Casting, Rolling and Finishing", f,
            share_fuel=cast_shares[f] * 100,       # %
            prod_fuel=prod_fuel,                   # t/a
            spec_intensity=casting_intensity,      # MWh/t
            fuel_demand=demand,                    # MWh
            sector=sector, subsector=subsector
        )

    # ---------------- Unspecified Iron & Steel ----------------
    unspecified_activity = _get_val(df, "Activity factor of unspecified iron and steel", col, 0.0)
    _steel_header_product(
        rows, year, scenario_col,
        product="Unspecified Iron and Steel",
        total_prod=unspecified_activity, sector=sector, subsector=subsector
    )
    _steel_header_process(
        rows, year, scenario_col, product="Unspecified Iron and Steel",
        process="Unspecified Iron and Steel",
        share_process=100.0, prod_process=unspecified_activity,
        sector=sector, subsector=subsector
    )
    _steel_header_tech(
        rows, year, scenario_col, "Unspecified Iron and Steel",
        "Unspecified Iron and Steel", "Unspecified Iron and Steel",
        share_tech=100.0, prod_tech=unspecified_activity,
        sector=sector, subsector=subsector
    )

    unsp_shares = {
        "Diesel":      _get_val(df, "Share of diesel for unspecified iron and steel", col, 0.0) / 100.0,
        "Natural Gas": _get_val(df, "Share of natural gas for unspecified iron and steel", col, 0.0) / 100.0,
        "Electricity": _get_val(df, "Share of electricity for unspecified iron and steel", col, 0.0) / 100.0,
        "Coal":        _get_val(df, "Share of coal for unspecified iron and steel", col, 0.0) / 100.0,
        "Heat":        _get_val(df, "Share of heat for unspecified iron and steel", col, 0.0) / 100.0,
        "Biomass":     _get_val(df, "Share of biomass for unspecified iron and steel", col, 0.0) / 100.0,
        "Hydrogen":    _get_val(df, "Share of hydrogen for unspecified iron and steel", col, 0.0) / 100.0,
    }
    # intensity = 0 → demand = 0 for unspecified
    for f in FUELS_ORDER:
        prod_fuel = unspecified_activity * unsp_shares[f]
        inten = 0.0
        demand = prod_fuel * inten
        _steel_fuel_row(
            rows, year, scenario_col, "Unspecified Iron and Steel",
            "Unspecified Iron and Steel", "Unspecified Iron and Steel", f,
            share_fuel=unsp_shares[f] * 100, prod_fuel=prod_fuel,
            spec_intensity=inten, fuel_demand=demand,
            sector=sector, subsector=subsector
        )

    out = pd.DataFrame(rows)
    return out[COL_ORDER]


def build_steel_full_table_from_metrics(df_metrics: pd.DataFrame) -> pd.DataFrame:
    """
    Take the metrics workbook for one country and build the full detailed Iron & Steel table
    for all scenario columns.
    """
    if "Metric" not in df_metrics.columns:
        raise ValueError("Input must contain a 'Metric' column.")

    scenario_cols = [c for c in df_metrics.columns if c not in ("Metric", "Units")]
    frames = [build_iron_steel(df_metrics, col) for col in scenario_cols]
    all_scenarios = pd.concat(frames, ignore_index=True)

    if "Year" in all_scenarios.columns:
        all_scenarios = all_scenarios.sort_values(["Year", "Scenario_col"], kind="stable")

    return all_scenarios[COL_ORDER]


def build_steel_tidy_feedstock(full_df: pd.DataFrame) -> pd.DataFrame:
    """
    From the detailed Steel table, create a clean/tidy feedstock table.
    """
    tidy = full_df[full_df["Dropdown"] == "Fuel"].copy()

    tidy = tidy[
        [
            "Year",
            "Scenario_col",
            "Sector",
            "Sub sector",
            "Product",
            "Process",
            "Technology",
            "Fuel/Feedstock",
            "final energy demand",
        ]
    ]

    tidy["Units"] = "MWh"

    tidy = tidy.sort_values(
        ["Year", "Scenario_col", "Sector", "Sub sector", "Product", "Process", "Technology", "Fuel/Feedstock"]
    )

    return tidy


def steel_bucket(product: str, process: str, tech: str) -> Optional[str]:
    p = str(product).strip()
    pr = str(process).strip()
    t = str(tech).strip()

    if p == "Steel" and pr == "Primary steel making" and t == "Blast Furnace + Open Hearth Furnace":
        return "Industry Steel Primary Blast Furnace Open Hearth Furnace"
    if p == "Steel" and pr == "Primary steel making" and t == "Blast Furnace + Basic Oxygen Furnace":
        return "Industry Steel Primary Blast Furnace Basic Oxygen Furnace"
    if p == "Steel" and pr == "Primary steel making" and t == "Direct Reduction + Electric Arc Furnace":
        return "Industry Steel Primary DRI"
    if p == "Steel" and pr == "Secondary steel making" and t == "Scrap Electric Arc Furnace":
        return "Industry Steel Secondary EAF"
    if p == "Steel" and pr == "Casting, Rolling and Finishing" and t == "Casting, Rolling and Finishing":
        return "Industry Steel Casting Rolling Finishing"
    if p == "Unspecified Iron and Steel":
        return "Industry Steel Other"
    return None


def build_sec_steel_from_tidy(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build Steel SEC table from tidy steel feedstock.
    Returns columns: Year, Scenario, SEC_Fuel, <STEEL_SEC_COLS>
    """
    df = df.copy()

    df["Bucket"] = df.apply(
        lambda r: steel_bucket(r.get("Product", ""), r.get("Process", ""), r.get("Technology", "")),
        axis=1
    )
    df = df[df["Bucket"].notna()].copy()

    ys = df["Scenario_col"].apply(parse_year_and_scenario)
    df["Year_extracted"] = ys.apply(lambda t: t[0])
    df["Scenario_label"] = ys.apply(lambda t: t[1])

    df["SEC_Fuel"] = df["Fuel/Feedstock"].map(FUEL_TO_SEC)
    df = df[df["SEC_Fuel"].notna()].copy()

    df["final energy demand"] = pd.to_numeric(df["final energy demand"], errors="coerce").fillna(0.0)

    grp = (
        df.groupby(["Year_extracted", "Scenario_label", "SEC_Fuel", "Bucket"], dropna=False)["final energy demand"]
        .sum()
        .reset_index()
    )

    total = (
        df.groupby(["Year_extracted", "Scenario_label", "Bucket"], dropna=False)["final energy demand"]
        .sum()
        .reset_index()
    )
    total["SEC_Fuel"] = "Total"

    comb = pd.concat([grp, total], ignore_index=True)

    piv = (
        comb.pivot_table(
            index=["Year_extracted", "Scenario_label", "SEC_Fuel"],
            columns="Bucket",
            values="final energy demand",
            aggfunc="sum",
            fill_value=0,
        )
        .reset_index()
    )

    for c in STEEL_SEC_COLS:
        if c not in piv.columns:
            piv[c] = 0.0

    piv["__order__"] = piv["SEC_Fuel"].map({name: i for i, name in enumerate(ROW_ORDER)})
    piv = piv.sort_values(["Year_extracted", "Scenario_label", "__order__"]).drop(columns="__order__")

    piv = piv.rename(columns={
        "Year_extracted": "Year",
        "Scenario_label": "Scenario",
    })

    return piv[["Year", "Scenario", "SEC_Fuel"] + STEEL_SEC_COLS]


# -------------------------------------------------------------------
# NON METALLIC MINERALS (NMM)
# -------------------------------------------------------------------

def build_nmm_for_col(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """
    Build the detailed Non metallic minerals (cement + unspecified)
    table for one scenario column in the metrics workbook.
    """
    year = _first_year_in_string(col)
    scenario_col = col

    sector = "Industry"
    subsector = "Non metallic minerals"
    rows: List[dict] = []

    # ---- Cement: clinker production (t/a) ----
    clinker_total = _get_val(df, "Clinker production per year", col, 0.0)

    cement_fuel_shares_pct = {
        "Diesel":      _get_val(df, "Share of diesel for cement production", col, 0.0),
        "Natural Gas": _get_val(df, "Share of natural gas for cement production", col, 0.0),
        "Electricity": _get_val(df, "Share of electricity for cement production", col, 0.0),
        "Coal":        _get_val(df, "Share of coal for cement production", col, 0.0),
        "Heat":        _get_val(df, "Share of heat for cement production", col, 0.0),
        "Biomass":     _get_val(df, "Share of biomass for cement production", col, 0.0),
        "Hydrogen":    _get_val(df, "Share of hydrogen for cement production", col, 0.0),
    }
    cement_fuel_shares = {k: v / 100.0 for k, v in cement_fuel_shares_pct.items()}

    cement_intensity = {
        "Diesel":      _get_val(df, "Energy intensity of diesel in cement production", col, 0.0),
        "Natural Gas": _get_val(df, "Energy intensity of natural gas in cement production", col, 0.0),
        "Electricity": _get_val(df, "Energy intensity of electricity in cement production", col, 0.0),
        "Coal":        _get_val(df, "Energy intensity of coal in cement production", col, 0.0),
        "Heat":        _get_val(df, "Energy intensity of heat in cement production", col, 0.0),
        "Biomass":     _get_val(df, "Energy intensity of biomass in cement production", col, 0.0),
        "Hydrogen":    _get_val(df, "Energy intensity of hydrogen in cement production", col, 0.0),
    }

    # ---- Sub sector header ----
    _add(
        rows, year, sector, subsector, "", "", "",
        "Sub sector", "", "Sub sector", subsector,
        total_prod="", share_proc="", prod_proc="",
        share_tech="", prod_tech="",
        share_fuel="", prod_fuel="",
        spec_intensity="", fuel_demand="", scenario_col=scenario_col,
    )

    # ---- Product header (Cement) ----
    _add(
        rows, year, sector, subsector, "Cement", "", "",
        "Product", "", "Product", "Cement",
        total_prod=clinker_total, share_proc="", prod_proc="",
        share_tech="", prod_tech="",
        share_fuel="", prod_fuel="",
        spec_intensity="", fuel_demand="", scenario_col=scenario_col,
    )

    # ---- Process header (Cement, 100%) ----
    process = "Cement Production (Kiln & Mills)"
    _add(
        rows, year, sector, subsector, "Cement", process, "",
        "Process", "", "Process", process,
        total_prod="", share_proc=100.0, prod_proc=clinker_total,
        share_tech="", prod_tech="",
        share_fuel="", prod_fuel="",
        spec_intensity="", fuel_demand="", scenario_col=scenario_col,
    )

    # ---- Technology header (Cement, 100%) ----
    technology = "Cement Production (Kiln & Mills)"
    _add(
        rows, year, sector, subsector, "Cement", process, technology,
        "Technology", "", "Technology", technology,
        total_prod="", share_proc="", prod_proc="",
        share_tech=100.0, prod_tech=clinker_total,
        share_fuel="", prod_fuel="",
        spec_intensity="", fuel_demand="", scenario_col=scenario_col,
    )

    # ---- Fuel rows (Cement) ----
    for fuel in FUELS_ORDER:
        prod_fuel = clinker_total * cement_fuel_shares[fuel]      # t/a
        demand = prod_fuel * cement_intensity[fuel]               # MWh
        _add(
            rows, year, sector, subsector, "Cement", process, technology,
            "Fuel", fuel, "Fuel", fuel,
            total_prod="", share_proc="", prod_proc="",
            share_tech="", prod_tech="",
            share_fuel=cement_fuel_shares_pct[fuel],             # %
            prod_fuel=prod_fuel,                                 # t/a
            spec_intensity=cement_intensity[fuel],               # MWh/t
            fuel_demand=demand,                                  # MWh
            scenario_col=scenario_col,
        )

    # ---- Unspecified non metallic minerals ----
    u_prod = "Unspecified non metallic minerals"
    u_proc = "Unspecified non metallic minerals"
    u_tech = "Unspecified non metallic minerals"

    u_activity = _get_val(
        df, "Activity factor of unspecified non metallic minerals", col, 0.0
    )
    u_intensity = _get_val(
        df, "Energy intensity of unspecified non metallic minerals", col, 0.0
    )

    u_shares_pct = {
        "Diesel":      _get_val(df, "Share of diesel for unspecified non metallic minerals", col, 0.0),
        "Natural Gas": _get_val(df, "Share of natural gas for unspecified non metallic minerals", col, 0.0),
        "Electricity": _get_val(df, "Share of electricity for unspecified non metallic minerals", col, 0.0),
        "Coal":        _get_val(df, "Share of coal for unspecified non metallic minerals", col, 0.0),
        "Heat":        _get_val(df, "Share of heat for unspecified non metallic minerals", col, 0.0),
        "Biomass":     _get_val(df, "Share of biomass for unspecified non metallic minerals", col, 0.0),
        "Hydrogen":    _get_val(df, "Share of hydrogen for unspecified non metallic minerals", col, 0.0),
    }
    u_shares = {k: v / 100.0 for k, v in u_shares_pct.items()}

    # Product header
    _add(
        rows, year, sector, subsector, u_prod, "", "",
        "Product", "", "Product", u_prod,
        total_prod=u_activity, share_proc="", prod_proc="",
        share_tech="", prod_tech="",
        share_fuel="", prod_fuel="",
        spec_intensity="", fuel_demand="", scenario_col=scenario_col,
    )

    # Process header
    _add(
        rows, year, sector, subsector, u_prod, u_proc, "",
        "Process", "", "Process", u_proc,
        total_prod="", share_proc=100.0, prod_proc=u_activity,
        share_tech="", prod_tech="",
        share_fuel="", prod_fuel="",
        spec_intensity="", fuel_demand="", scenario_col=scenario_col,
    )

    # Technology header
    _add(
        rows, year, sector, subsector, u_prod, u_proc, u_tech,
        "Technology", "", "Technology", u_tech,
        total_prod="", share_proc="", prod_proc="",
        share_tech=100.0, prod_tech=u_activity,
        share_fuel="", prod_fuel="",
        spec_intensity="", fuel_demand="", scenario_col=scenario_col,
    )

    # Fuel rows
    for fuel in FUELS_ORDER:
        u_prod_fuel = u_activity * u_shares[fuel]
        u_demand = u_prod_fuel * u_intensity
        _add(
            rows, year, sector, subsector, u_prod, u_proc, u_tech,
            "Fuel", fuel, "Fuel", fuel,
            total_prod="", share_proc="", prod_proc="",
            share_tech="", prod_tech="",
            share_fuel=u_shares_pct[fuel],
            prod_fuel=u_prod_fuel,
            spec_intensity=u_intensity,
            fuel_demand=u_demand,
            scenario_col=scenario_col,
        )

    out = pd.DataFrame(rows)
    return out[COL_ORDER]


def build_nmm_full_table_from_metrics(df_metrics: pd.DataFrame) -> pd.DataFrame:
    """
    Take the metrics workbook for one country and build the full detailed
    Non metallic minerals table for all scenario columns.
    """
    if "Metric" not in df_metrics.columns:
        raise ValueError("Input must contain 'Metric' column.")

    scenario_cols = [c for c in df_metrics.columns if c not in ("Metric", "Units")]
    parts: List[pd.DataFrame] = [build_nmm_for_col(df_metrics, c) for c in scenario_cols]
    return pd.concat(parts, ignore_index=True)


def build_nmm_tidy_feedstock(full_df: pd.DataFrame) -> pd.DataFrame:
    """
    From the detailed NMM table, create a clean/tidy feedstock table.
    """
    tidy = full_df[full_df["Dropdown"] == "Fuel"].copy()

    tidy = tidy[
        [
            "Year",
            "Scenario_col",
            "Sector",
            "Sub sector",
            "Product",
            "Process",
            "Technology",
            "Fuel/Feedstock",
            "final energy demand",
        ]
    ]

    tidy["Units"] = "MWh"

    tidy = tidy.sort_values(
        ["Year", "Scenario_col", "Sector", "Sub sector", "Product", "Process", "Technology", "Fuel/Feedstock"]
    )

    return tidy


def build_sec_nmm_from_tidy(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build NMM SEC table (only NMM columns) from tidy NMM feedstock.
    Returns columns: Year, Scenario, SEC_Fuel, Industry NMM Cement, Industry NMM Other
    """
    def bucket_col(prod: str) -> Optional[str]:
        prod_str = str(prod).strip()
        if prod_str == "Cement":
            return "Industry NMM Cement"
        elif prod_str == "Unspecified non metallic minerals":
            return "Industry NMM Other"
        else:
            return None

    df = df.copy()
    df["Bucket"] = df["Product"].map(bucket_col)
    df = df[df["Bucket"].notna()].copy()

    ys = df["Scenario_col"].apply(parse_year_and_scenario)
    df["Year_extracted"] = ys.apply(lambda t: t[0])
    df["Scenario_label"] = ys.apply(lambda t: t[1])

    df["SEC_Fuel"] = df["Fuel/Feedstock"].map(FUEL_TO_SEC)
    df = df[df["SEC_Fuel"].notna()].copy()

    df["final energy demand"] = pd.to_numeric(df["final energy demand"], errors="coerce").fillna(0.0)

    grp = (
        df.groupby(["Year_extracted", "Scenario_label", "SEC_Fuel", "Bucket"], dropna=False)["final energy demand"]
        .sum()
        .reset_index()
    )

    total = (
        df.groupby(["Year_extracted", "Scenario_label", "Bucket"], dropna=False)["final energy demand"]
        .sum()
        .reset_index()
    )
    total["SEC_Fuel"] = "Total"

    comb = pd.concat([grp, total], ignore_index=True)

    piv = (
        comb.pivot_table(
            index=["Year_extracted", "Scenario_label", "SEC_Fuel"],
            columns="Bucket",
            values="final energy demand",
            aggfunc="sum",
            fill_value=0,
        )
        .reset_index()
    )

    for c in NMM_SEC_COLS:
        if c not in piv.columns:
            piv[c] = 0.0

    piv["__order__"] = piv["SEC_Fuel"].map({name: i for i, name in enumerate(ROW_ORDER)})
    piv = piv.sort_values(["Year_extracted", "Scenario_label", "__order__"]).drop(columns="__order__")

    piv = piv.rename(columns={
        "Year_extracted": "Year",
        "Scenario_label": "Scenario",
    })

    return piv[["Year", "Scenario", "SEC_Fuel"] + NMM_SEC_COLS]


# -------------------------------------------------------------------
# PAPER AND PULP
# -------------------------------------------------------------------

def _pp_header_subsector(rows, year, scenario_col, sector="Industry", subsector="Paper and pulp"):
    _add(
        rows, year, sector, subsector,
        product="", process="", tech="",
        dropdown="Sub sector", fuel="", level="Sub sector", desc=subsector,
        total_prod="", share_proc="", prod_proc="",
        share_tech="", prod_tech="",
        share_fuel="", prod_fuel="",
        spec_intensity="", fuel_demand="", scenario_col=scenario_col,
    )


def _pp_header_product(rows, year, scenario_col, product, total_prod=None,
                       sector="Industry", subsector="Paper and pulp"):
    _add(
        rows, year, sector, subsector,
        product=product, process="", tech="",
        dropdown="Product", fuel="", level="Product", desc=product,
        total_prod=total_prod, share_proc="", prod_proc="",
        share_tech="", prod_tech="",
        share_fuel="", prod_fuel="",
        spec_intensity="", fuel_demand="", scenario_col=scenario_col,
    )


def _pp_header_process(rows, year, scenario_col, product, process,
                       share_process=None, prod_process=None,
                       sector="Industry", subsector="Paper and pulp"):
    _add(
        rows, year, sector, subsector,
        product=product, process=process, tech="",
        dropdown="Process", fuel="", level="Process", desc=process,
        total_prod="", share_proc=share_process, prod_proc=prod_process,
        share_tech="", prod_tech="",
        share_fuel="", prod_fuel="",
        spec_intensity="", fuel_demand="", scenario_col=scenario_col,
    )


def _pp_header_tech(rows, year, scenario_col, product, process, tech,
                    share_tech=None, prod_tech=None,
                    sector="Industry", subsector="Paper and pulp"):
    _add(
        rows, year, sector, subsector,
        product=product, process=process, tech=tech,
        dropdown="Technology", fuel="", level="Technology", desc=tech,
        total_prod="", share_proc="", prod_proc="",
        share_tech=share_tech, prod_tech=prod_tech,
        share_fuel="", prod_fuel="",
        spec_intensity="", fuel_demand="", scenario_col=scenario_col,
    )


def _pp_fuel_row(rows, year, scenario_col, product, process, tech, fuel,
                 share_fuel=None, prod_fuel=None, spec_intensity=None, fuel_demand=None,
                 sector="Industry", subsector="Paper and pulp"):
    _add(
        rows, year, sector, subsector,
        product=product, process=process, tech=tech,
        dropdown="Fuel", fuel=fuel, level="Fuel", desc=fuel,
        total_prod="", share_proc="", prod_proc="",
        share_tech="", prod_tech="",
        share_fuel=share_fuel, prod_fuel=prod_fuel,
        spec_intensity=spec_intensity, fuel_demand=fuel_demand,
        scenario_col=scenario_col,
    )


def build_paper_pulp_for_col(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """
    Builds the hierarchical Paper & Pulp table for one scenario column.
    Uses metric labels exactly as provided.
    """
    year = _first_year_in_string(col)
    scenario_col = col
    sector = "Industry"
    subsector = "Paper and pulp"

    rows: List[dict] = []

    # ===== Sub sector header
    _pp_header_subsector(rows, year, scenario_col, sector=sector, subsector=subsector)

    # ===== PRODUCT: Pulp
    pulp_total = _get_val(df, "Pulp production per year", col, 0.0)  # tons/y
    _pp_header_product(rows, year, scenario_col, product="Pulp",
                       total_prod=pulp_total, sector=sector, subsector=subsector)

    share_primary_pulp = _get_val(df, "Share of primary pulp", col, 0.0) / 100.0
    share_secondary_pulp = _get_val(df, "Share of secondary pulp", col, 0.0) / 100.0
    prod_primary_pulp = pulp_total * share_primary_pulp
    prod_secondary_pulp = pulp_total * share_secondary_pulp

    # ---- PROCESS: Primary pulp production
    _pp_header_process(
        rows, year, scenario_col, product="Pulp",
        process="Primary pulp production",
        share_process=share_primary_pulp * 100,
        prod_process=prod_primary_pulp,
        sector=sector, subsector=subsector,
    )
    _pp_header_tech(
        rows, year, scenario_col, "Pulp", "Primary pulp production",
        "Primary pulp production",
        share_tech=100.0, prod_tech=prod_primary_pulp,
        sector=sector, subsector=subsector,
    )

    prim_int = {
        "Diesel":      _get_val(df, "Energy intensity of diesel in primary pulp production", col, 0.0),
        "Natural Gas": _get_val(df, "Energy intensity of natural gas in primary pulp production", col, 0.0),
        "Electricity": _get_val(df, "Energy intensity of electricity in primary pulp production", col, 0.0),
        "Coal":        _get_val(df, "Energy intensity of coal in primary pulp production", col, 0.0),
        "Heat":        _get_val(df, "Energy intensity of heat in primary pulp production", col, 0.0),
        "Biomass":     _get_val(df, "Energy intensity of biomass in primary pulp production", col, 0.0),
        "Hydrogen":    _get_val(df, "Energy intensity of hydrogen in primary pulp production", col, 0.0),
    }
    prim_share = {
        "Diesel":      _get_val(df, "Share of diesel for primary pulp production", col, 0.0) / 100.0,
        "Natural Gas": _get_val(df, "Share of natural gas for primary pulp production", col, 0.0) / 100.0,
        "Electricity": _get_val(df, "Share of electricity for primary pulp production", col, 0.0) / 100.0,
        "Coal":        _get_val(df, "Share of coal for primary pulp production", col, 0.0) / 100.0,
        "Heat":        _get_val(df, "Share of heat for primary pulp production", col, 0.0) / 100.0,
        "Biomass":     _get_val(df, "Share of biomass for primary pulp production", col, 0.0) / 100.0,
        "Hydrogen":    _get_val(df, "Share of hydrogen for primary pulp production", col, 0.0) / 100.0,
    }
    for f in FUELS_ORDER:
        prod_fuel = prod_primary_pulp * prim_share[f]
        demand = prod_fuel * prim_int[f]
        _pp_fuel_row(
            rows, year, scenario_col, "Pulp", "Primary pulp production", "Primary pulp production", f,
            share_fuel=prim_share[f] * 100, prod_fuel=prod_fuel,
            spec_intensity=prim_int[f], fuel_demand=demand,
            sector=sector, subsector=subsector,
        )

    # ---- PROCESS: Secondary pulp production
    _pp_header_process(
        rows, year, scenario_col, product="Pulp",
        process="Secondary pulp production",
        share_process=share_secondary_pulp * 100,
        prod_process=prod_secondary_pulp,
        sector=sector, subsector=subsector,
    )
    _pp_header_tech(
        rows, year, scenario_col, "Pulp", "Secondary pulp production",
        "Secondary pulp production",
        share_tech=100.0, prod_tech=prod_secondary_pulp,
        sector=sector, subsector=subsector,
    )

    sec_int = {
        "Diesel":      _get_val(df, "Energy intensity of diesel in secondary pulp production", col, 0.0),
        "Natural Gas": _get_val(df, "Energy intensity of natural gas in secondary pulp production", col, 0.0),
        "Electricity": _get_val(df, "Energy intensity of electricity in secondary pulp production", col, 0.0),
        "Coal":        _get_val(df, "Energy intensity of coal in secondary pulp production", col, 0.0),
        "Heat":        _get_val(df, "Energy intensity of heat in secondary pulp production", col, 0.0),
        "Biomass":     _get_val(df, "Energy intensity of biomass in secondary pulp production", col, 0.0),
        "Hydrogen":    _get_val(df, "Energy intensity of hydrogen in secondary pulp production", col, 0.0),
    }
    sec_share = {
        "Diesel":      _get_val(df, "Share of diesel for secondary pulp production", col, 0.0) / 100.0,
        "Natural Gas": _get_val(df, "Share of natural gas for secondary pulp production", col, 0.0) / 100.0,
        "Electricity": _get_val(df, "Share of electricity for secondary pulp production", col, 0.0) / 100.0,
        "Coal":        _get_val(df, "Share of coal for secondary pulp production", col, 0.0) / 100.0,
        "Heat":        _get_val(df, "Share of heat for secondary pulp production", col, 0.0) / 100.0,
        "Biomass":     _get_val(df, "Share of biomass for secondary pulp production", col, 0.0) / 100.0,
        "Hydrogen":    _get_val(df, "Share of hydrogen for secondary pulp production", col, 0.0) / 100.0,
    }
    for f in FUELS_ORDER:
        prod_fuel = prod_secondary_pulp * sec_share[f]
        demand = prod_fuel * sec_int[f]
        _pp_fuel_row(
            rows, year, scenario_col, "Pulp", "Secondary pulp production", "Secondary pulp production", f,
            share_fuel=sec_share[f] * 100, prod_fuel=prod_fuel,
            spec_intensity=sec_int[f], fuel_demand=demand,
            sector=sector, subsector=subsector,
        )

    # ===== PRODUCT: Paper
    paper_total = _get_val(df, "Paper production per year", col, 0.0)
    _pp_header_product(rows, year, scenario_col, product="Paper",
                       total_prod=paper_total, sector=sector, subsector=subsector)

    _pp_header_process(
        rows, year, scenario_col, product="Paper",
        process="Paper production",
        share_process=100.0, prod_process=paper_total,
        sector=sector, subsector=subsector,
    )
    _pp_header_tech(
        rows, year, scenario_col, "Paper", "Paper production",
        "Paper production",
        share_tech=100.0, prod_tech=paper_total,
        sector=sector, subsector=subsector,
    )

    paper_int = {
        "Diesel":      _get_val(df, "Energy intensity of diesel in paper production", col, 0.0),
        "Natural Gas": _get_val(df, "Energy intensity of natural gas in paper production", col, 0.0),
        "Electricity": _get_val(df, "Energy intensity of electricity in paper production", col, 0.0),
        "Coal":        _get_val(df, "Energy intensity of coal in paper production", col, 0.0),
        "Heat":        _get_val(df, "Energy intensity of heat in paper production", col, 0.0),
        "Biomass":     _get_val(df, "Energy intensity of biomass in paper production", col, 0.0),
        "Hydrogen":    _get_val(df, "Energy intensity of hydrogen in paper production", col, 0.0),
    }
    paper_share = {
        "Diesel":      _get_val(df, "Share of diesel for paper production", col, 0.0) / 100.0,
        "Natural Gas": _get_val(df, "Share of natural gas for paper production", col, 0.0) / 100.0,
        "Electricity": _get_val(df, "Share of electricity for paper production", col, 0.0) / 100.0,
        "Coal":        _get_val(df, "Share of coal for paper production", col, 0.0) / 100.0,
        "Heat":        _get_val(df, "Share of heat for paper production", col, 0.0) / 100.0,
        "Biomass":     _get_val(df, "Share of biomass for paper production", col, 0.0) / 100.0,
        "Hydrogen":    _get_val(df, "Share of hydrogen for paper production", col, 0.0) / 100.0,
    }
    for f in FUELS_ORDER:
        prod_fuel = paper_total * paper_share[f]
        demand = prod_fuel * paper_int[f]
        _pp_fuel_row(
            rows, year, scenario_col, "Paper", "Paper production", "Paper production", f,
            share_fuel=paper_share[f] * 100, prod_fuel=prod_fuel,
            spec_intensity=paper_int[f], fuel_demand=demand,
            sector=sector, subsector=subsector,
        )

    # ===== PRODUCT: Unspecified paper and pulp
    unspecified_activity = _get_val(df, "Activity factor of unspecified paper and pulp", col, 0.0)
    unspecified_base_energy = _get_val(df, "Energy of unspecified paper and pulp", col, 0.0)
    _pp_header_product(
        rows, year, scenario_col, product="Unspecified paper and pulp",
        total_prod=unspecified_activity, sector=sector, subsector=subsector,
    )
    _pp_header_process(
        rows, year, scenario_col, product="Unspecified paper and pulp",
        process="Unspecified paper and pulp",
        share_process=100.0, prod_process=unspecified_activity,
        sector=sector, subsector=subsector,
    )
    _pp_header_tech(
        rows, year, scenario_col, "Unspecified paper and pulp",
        "Unspecified paper and pulp", "Unspecified paper and pulp",
        share_tech=100.0, prod_tech=unspecified_activity,
        sector=sector, subsector=subsector,
    )

    unsp_share = {
        "Diesel":      _get_val(df, "Share of diesel for unspecified paper and pulp", col, 0.0) / 100.0,
        "Natural Gas": _get_val(df, "Share of natural gas for unspecified paper and pulp", col, 0.0) / 100.0,
        "Electricity": _get_val(df, "Share of electricity for unspecified paper and pulp", col, 0.0) / 100.0,
        "Coal":        _get_val(df, "Share of coal for unspecified paper and pulp", col, 0.0) / 100.0,
        "Heat":        _get_val(df, "Share of heat for unspecified paper and pulp", col, 0.0) / 100.0,
        "Biomass":     _get_val(df, "Share of biomass for unspecified paper and pulp", col, 0.0) / 100.0,
        "Hydrogen":    _get_val(df, "Share of hydrogen for unspecified paper and pulp", col, 0.0) / 100.0,
    }
    for f in FUELS_ORDER:
        # Unspecified energy = base_energy × activity_factor × fuel_share
        demand = unspecified_base_energy * unspecified_activity * unsp_share[f]
        prod_fuel = demand  # For display purposes
        inten = 1.0 if unsp_share[f] > 0 else 0.0  # Effective intensity
        _pp_fuel_row(
            rows, year, scenario_col, "Unspecified paper and pulp",
            "Unspecified paper and pulp", "Unspecified paper and pulp", f,
            share_fuel=unsp_share[f] * 100, prod_fuel=prod_fuel,
            spec_intensity=inten, fuel_demand=demand,
            sector=sector, subsector=subsector,
        )

    out = pd.DataFrame(rows)
    return out[COL_ORDER]


def build_paper_pulp_full_table_from_metrics(df_metrics: pd.DataFrame) -> pd.DataFrame:
    """
    Build full detailed Paper & Pulp table for all scenario columns.
    """
    if "Metric" not in df_metrics.columns:
        raise ValueError("Input must contain a 'Metric' column.")
    scenario_cols = [c for c in df_metrics.columns if c not in ("Metric", "Units")]
    parts: List[pd.DataFrame] = [build_paper_pulp_for_col(df_metrics, c) for c in scenario_cols]
    return pd.concat(parts, ignore_index=True)


def build_paper_pulp_tidy_feedstock(full_df: pd.DataFrame) -> pd.DataFrame:
    """
    From detailed Paper & Pulp table, create tidy feedstock table.
    """
    tidy = full_df[full_df["Dropdown"] == "Fuel"].copy()
    tidy = tidy[
        [
            "Year",
            "Scenario_col",
            "Sector",
            "Sub sector",
            "Product",
            "Process",
            "Technology",
            "Fuel/Feedstock",
            "final energy demand",
        ]
    ]
    tidy["Units"] = "MWh"
    tidy = tidy.sort_values(
        ["Year", "Scenario_col", "Sector", "Sub sector", "Product", "Process", "Technology", "Fuel/Feedstock"]
    )
    return tidy


def build_sec_paper_pulp_from_tidy(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build Paper & Pulp SEC table from tidy feedstock.
    Returns columns: Year, Scenario, SEC_Fuel, <PP_SEC_COLS>
    """
    df = df.copy()

    def bucket_col(product: str, process: str) -> Optional[str]:
        p = str(product).strip()
        pr = str(process).strip()
        if p == "Pulp" and pr == "Primary pulp production":
            return "Industry Paper and pulp Pulp Primary"
        if p == "Pulp" and pr == "Secondary pulp production":
            return "Industry Paper and pulp Pulp Secondary"
        if p == "Paper" and pr == "Paper production":
            return "Industry Paper and pulp Paper"
        return None

    df["Bucket"] = df.apply(lambda r: bucket_col(r["Product"], r["Process"]), axis=1)
    df = df[df["Bucket"].notna()].copy()

    ys = df["Scenario_col"].apply(parse_year_and_scenario)
    df["Year_extracted"] = ys.apply(lambda t: t[0])
    df["Scenario_label"] = ys.apply(lambda t: t[1])

    df["SEC_Fuel"] = df["Fuel/Feedstock"].map(FUEL_TO_SEC)
    df = df[df["SEC_Fuel"].notna()].copy()

    df["final energy demand"] = pd.to_numeric(df["final energy demand"], errors="coerce").fillna(0.0)

    grp = (
        df.groupby(["Year_extracted", "Scenario_label", "SEC_Fuel", "Bucket"], dropna=False)["final energy demand"]
        .sum()
        .reset_index()
    )

    total = (
        df.groupby(["Year_extracted", "Scenario_label", "Bucket"], dropna=False)["final energy demand"]
        .sum()
        .reset_index()
    )
    total["SEC_Fuel"] = "Total"

    comb = pd.concat([grp, total], ignore_index=True)

    piv = (
        comb.pivot_table(
            index=["Year_extracted", "Scenario_label", "SEC_Fuel"],
            columns="Bucket",
            values="final energy demand",
            aggfunc="sum",
            fill_value=0,
        )
        .reset_index()
    )

    for c in PP_SEC_COLS:
        if c not in piv.columns:
            piv[c] = 0.0

    piv["__order__"] = piv["SEC_Fuel"].map({name: i for i, name in enumerate(ROW_ORDER)})
    piv = piv.sort_values(["Year_extracted", "Scenario_label", "__order__"]).drop(columns="__order__")

    piv = piv.rename(columns={
        "Year_extracted": "Year",
        "Scenario_label": "Scenario",
    })

    return piv[["Year", "Scenario", "SEC_Fuel"] + PP_SEC_COLS]


# -------------------------------------------------------------------
# CHEMICALS (AMMONIA + HVC + UNSPECIFIED)
# -------------------------------------------------------------------

def build_chemicals_for_col(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """
    Build detailed Chemical table (Ammonia + High Value Chemicals + Unspecified)
    for a single scenario column `col` from the metrics DataFrame.
    """
    year = _first_year_in_string(col)
    scenario_col = col
    sector = "Industry"
    subsector = "Chemical"  # singular, used only as a label in the table

    rows: List[dict] = []

    # ===========================================================
    # SUBSECTOR HEADER
    # ===========================================================
    _add(
        rows, year, sector, subsector,
        product="", process="", tech="",
        dropdown="Sub sector", fuel="", level="Sub sector", desc=subsector,
        total_prod="", share_proc="", prod_proc="",
        share_tech="", prod_tech="",
        share_fuel="", prod_fuel="",
        spec_intensity="", fuel_demand="", scenario_col=scenario_col,
    )

    # ===========================================================
    # 1. AMMONIA
    # ===========================================================
    ammo_total = _get_val(df, "Ammonia production per year", col, 0.0)

    # Product header
    _add(
        rows, year, sector, subsector,
        product="Ammonia", process="", tech="",
        dropdown="Product", fuel="", level="Product", desc="Ammonia",
        total_prod=ammo_total, share_proc="", prod_proc="",
        share_tech="", prod_tech="",
        share_fuel="", prod_fuel="",
        spec_intensity="", fuel_demand="", scenario_col=scenario_col,
    )

    # Process: Ammonia synthesis (100% of ammonia)
    process_ammo = "Ammonia synthesis"
    _add(
        rows, year, sector, subsector,
        product="Ammonia", process=process_ammo, tech="",
        dropdown="Process", fuel="", level="Process", desc=process_ammo,
        total_prod="", share_proc=100.0, prod_proc=ammo_total,
        share_tech="", prod_tech="",
        share_fuel="", prod_fuel="",
        spec_intensity="", fuel_demand="", scenario_col=scenario_col,
    )

    # ----- Technology 1: SMR + Haber-Bosch
    share_smr_pct = _get_val(df, "Share of SMR + Haber-Bosch", col, 0.0)
    share_smr = share_smr_pct / 100.0
    prod_smr = ammo_total * share_smr

    tech_smr = "SMR + Haber-Bosch"
    _add(
        rows, year, sector, subsector,
        product="Ammonia", process=process_ammo, tech=tech_smr,
        dropdown="Technology", fuel="", level="Technology", desc=tech_smr,
        total_prod="", share_proc="", prod_proc="",
        share_tech=share_smr_pct, prod_tech=prod_smr,
        share_fuel="", prod_fuel="",
        spec_intensity="", fuel_demand="", scenario_col=scenario_col,
    )

    smr_shares_pct = {
        "Diesel":      _get_val(df, "Share of diesel for SMR + Haber-Bosch", col, 0.0),
        "Natural Gas": _get_val(df, "Share of natural gas for SMR + Haber-Bosch", col, 0.0),
        "Electricity": _get_val(df, "Share of electricity for SMR + Haber-Bosch", col, 0.0),
        "Coal":        _get_val(df, "Share of coal for SMR + Haber-Bosch", col, 0.0),
        "Heat":        _get_val(df, "Share of heat for SMR + Haber-Bosch", col, 0.0),
        "Biomass":     _get_val(df, "Share of biomass for SMR + Haber-Bosch", col, 0.0),
        "Hydrogen":    _get_val(df, "Share of hydrogen for SMR + Haber-Bosch", col, 0.0),
    }
    smr_shares = {k: v / 100.0 for k, v in smr_shares_pct.items()}

    smr_intensity = {
        "Diesel":      _get_val(df, "Energy intensity of diesel in SMR + Haber-Bosch", col, 0.0),
        "Natural Gas": _get_val(df, "Energy intensity of natural gas in SMR + Haber-Bosch", col, 0.0),
        "Electricity": _get_val(df, "Energy intensity of electricity in SMR + Haber-Bosch", col, 0.0),
        "Coal":        _get_val(df, "Energy intensity of coal in SMR + Haber-Bosch", col, 0.0),
        "Heat":        _get_val(df, "Energy intensity of heat in SMR + Haber-Bosch", col, 0.0),
        "Biomass":     _get_val(df, "Energy intensity of biomass in SMR + Haber-Bosch", col, 0.0),
        "Hydrogen":    _get_val(df, "Energy intensity of hydrogen in SMR + Haber-Bosch", col, 0.0),
    }

    for fuel in FUELS_ORDER:
        prod_fuel = prod_smr * smr_shares[fuel]
        demand = prod_fuel * smr_intensity[fuel]
        _add(
            rows, year, sector, subsector,
            product="Ammonia", process=process_ammo, tech=tech_smr,
            dropdown="Fuel", fuel=fuel, level="Fuel", desc=fuel,
            total_prod="", share_proc="", prod_proc="",
            share_tech="", prod_tech="",
            share_fuel=smr_shares_pct[fuel],
            prod_fuel=prod_fuel,
            spec_intensity=smr_intensity[fuel],
            fuel_demand=demand,
            scenario_col=scenario_col,
        )

    # ----- Technology 2: Renewable Ammonia Synthesis
    share_ren_pct = _get_val(df, "Share of renewable ammonia synthesis", col, 0.0)
    share_ren = share_ren_pct / 100.0
    prod_ren = ammo_total * share_ren

    tech_ren = "Renewable Ammonia Synthesis"
    _add(
        rows, year, sector, subsector,
        product="Ammonia", process=process_ammo, tech=tech_ren,
        dropdown="Technology", fuel="", level="Technology", desc=tech_ren,
        total_prod="", share_proc="", prod_proc="",
        share_tech=share_ren_pct, prod_tech=prod_ren,
        share_fuel="", prod_fuel="",
        spec_intensity="", fuel_demand="", scenario_col=scenario_col,
    )

    ren_shares_pct = {
        "Diesel":      _get_val(df, "Share of diesel for renewable ammonia synthesis", col, 0.0),
        "Natural Gas": _get_val(df, "Share of natural gas for renewable ammonia synthesis", col, 0.0),
        "Electricity": _get_val(df, "Share of electricity for renewable ammonia synthesis", col, 0.0),
        "Coal":        _get_val(df, "Share of coal for renewable ammonia synthesis", col, 0.0),
        "Heat":        _get_val(df, "Share of heat for renewable ammonia synthesis", col, 0.0),
        "Biomass":     _get_val(df, "Share of biomass for renewable ammonia synthesis", col, 0.0),
        "Hydrogen":    _get_val(df, "Share of hydrogen for renewable ammonia synthesis", col, 0.0),
    }
    ren_shares = {k: v / 100.0 for k, v in ren_shares_pct.items()}

    ren_intensity = {
        "Diesel":      _get_val(df, "Energy intensity of diesel in renewable ammonia synthesis", col, 0.0),
        "Natural Gas": _get_val(df, "Energy intensity of natural gas in renewable ammonia synthesis", col, 0.0),
        "Electricity": _get_val(df, "Energy intensity of electricity in renewable ammonia synthesis", col, 0.0),
        "Coal":        _get_val(df, "Energy intensity of coal in renewable ammonia synthesis", col, 0.0),
        "Heat":        _get_val(df, "Energy intensity of heat in renewable ammonia synthesis", col, 0.0),
        "Biomass":     _get_val(df, "Energy intensity of biomass in renewable ammonia synthesis", col, 0.0),
        "Hydrogen":    _get_val(df, "Energy intensity of hydrogen in renewable ammonia synthesis", col, 0.0),
    }

    for fuel in FUELS_ORDER:
        prod_fuel = prod_ren * ren_shares[fuel]
        demand = prod_fuel * ren_intensity[fuel]
        _add(
            rows, year, sector, subsector,
            product="Ammonia", process=process_ammo, tech=tech_ren,
            dropdown="Fuel", fuel=fuel, level="Fuel", desc=fuel,
            total_prod="", share_proc="", prod_proc="",
            share_tech="", prod_tech="",
            share_fuel=ren_shares_pct[fuel],
            prod_fuel=prod_fuel,
            spec_intensity=ren_intensity[fuel],
            fuel_demand=demand,
            scenario_col=scenario_col,
        )

    # ===========================================================
    # 2. HIGH VALUE CHEMICALS (HVC)
    # ===========================================================
    hvc_total = _get_val(df, "High value chemical production per year", col, 0.0)

    if hvc_total > 0:
        # Product header
        _add(
            rows, year, sector, subsector,
            product="High Value Chemicals", process="", tech="",
            dropdown="Product", fuel="", level="Product", desc="High Value Chemicals",
            total_prod=hvc_total, share_proc="", prod_proc="",
            share_tech="", prod_tech="",
            share_fuel="", prod_fuel="",
            spec_intensity="", fuel_demand="", scenario_col=scenario_col,
        )

        process_hvc = "HVC production"
        _add(
            rows, year, sector, subsector,
            product="High Value Chemicals", process=process_hvc, tech="",
            dropdown="Process", fuel="", level="Process", desc=process_hvc,
            total_prod="", share_proc=100.0, prod_proc=hvc_total,
            share_tech="", prod_tech="",
            share_fuel="", prod_fuel="",
            spec_intensity="", fuel_demand="", scenario_col=scenario_col,
        )

        # ----- Route 1: Naphtha cracking
        share_nap_pct = _get_val(df, "Share of Naphtha cracking for HVC production", col, 0.0)
        share_nap = share_nap_pct / 100.0
        prod_nap = hvc_total * share_nap

        tech_nap = "Naphtha cracking"
        _add(
            rows, year, sector, subsector,
            product="High Value Chemicals", process=process_hvc, tech=tech_nap,
            dropdown="Technology", fuel="", level="Technology", desc=tech_nap,
            total_prod="", share_proc="", prod_proc="",
            share_tech=share_nap_pct, prod_tech=prod_nap,
            share_fuel="", prod_fuel="",
            spec_intensity="", fuel_demand="", scenario_col=scenario_col,
        )

        nap_shares_pct = {
            "Diesel":      _get_val(df, "Share of diesel for Naphtha cracking", col, 0.0),
            "Natural Gas": _get_val(df, "Share of natural gas for Naphtha cracking", col, 0.0),
            "Electricity": _get_val(df, "Share of electricity for Naphtha cracking", col, 0.0),
            "Coal":        _get_val(df, "Share of coal for Naphtha cracking", col, 0.0),
            "Heat":        _get_val(df, "Share of heat for Naphtha cracking", col, 0.0),
            "Biomass":     _get_val(df, "Share of biomass for Naphtha cracking", col, 0.0),
            "Hydrogen":    _get_val(df, "Share of hydrogen for Naphtha cracking", col, 0.0),
        }
        nap_shares = {k: v / 100.0 for k, v in nap_shares_pct.items()}

        nap_intensity = {
            "Diesel":      _get_val(df, "Energy intensity of diesel in Naphtha cracking", col, 0.0),
            "Natural Gas": _get_val(df, "Energy intensity of natural gas in Naphtha cracking", col, 0.0),
            "Electricity": _get_val(df, "Energy intensity of electricity in Naphtha cracking", col, 0.0),
            "Coal":        _get_val(df, "Energy intensity of coal in Naphtha cracking", col, 0.0),
            "Heat":        _get_val(df, "Energy intensity of heat in Naphtha cracking", col, 0.0),
            "Biomass":     _get_val(df, "Energy intensity of biomass in Naphtha cracking", col, 0.0),
            "Hydrogen":    _get_val(df, "Energy intensity of hydrogen in Naphtha cracking", col, 0.0),
        }

        for fuel in FUELS_ORDER:
            prod_fuel = prod_nap * nap_shares[fuel]
            demand = prod_fuel * nap_intensity[fuel]
            _add(
                rows, year, sector, subsector,
                product="High Value Chemicals", process=process_hvc, tech=tech_nap,
                dropdown="Fuel", fuel=fuel, level="Fuel", desc=fuel,
                total_prod="", share_proc="", prod_proc="",
                share_tech="", prod_tech="",
                share_fuel=nap_shares_pct[fuel],
                prod_fuel=prod_fuel,
                spec_intensity=nap_intensity[fuel],
                fuel_demand=demand,
                scenario_col=scenario_col,
            )

        # ----- Route 2: LPG cracking
        share_lpg_pct = _get_val(df, "Share of LPG cracking for HVC production", col, 0.0)
        share_lpg = share_lpg_pct / 100.0
        prod_lpg = hvc_total * share_lpg

        tech_lpg = "LPG cracking"
        _add(
            rows, year, sector, subsector,
            product="High Value Chemicals", process=process_hvc, tech=tech_lpg,
            dropdown="Technology", fuel="", level="Technology", desc=tech_lpg,
            total_prod="", share_proc="", prod_proc="",
            share_tech=share_lpg_pct, prod_tech=prod_lpg,
            share_fuel="", prod_fuel="",
            spec_intensity="", fuel_demand="", scenario_col=scenario_col,
        )

        lpg_shares_pct = {
            "Diesel":      _get_val(df, "Share of diesel for LPG cracking", col, 0.0),
            "Natural Gas": _get_val(df, "Share of natural gas for LPG cracking", col, 0.0),
            "Electricity": _get_val(df, "Share of electricity for LPG cracking", col, 0.0),
            "Coal":        _get_val(df, "Share of coal for LPG cracking", col, 0.0),
            "Heat":        _get_val(df, "Share of heat for LPG cracking", col, 0.0),
            "Biomass":     _get_val(df, "Share of biomass for LPG cracking", col, 0.0),
            "Hydrogen":    _get_val(df, "Share of hydrogen for LPG cracking", col, 0.0),
        }
        lpg_shares = {k: v / 100.0 for k, v in lpg_shares_pct.items()}

        lpg_intensity = {
            "Diesel":      _get_val(df, "Energy intensity of diesel in LPG cracking", col, 0.0),
            "Natural Gas": _get_val(df, "Energy intensity of natural gas in LPG cracking", col, 0.0),
            "Electricity": _get_val(df, "Energy intensity of electricity in LPG cracking", col, 0.0),
            "Coal":        _get_val(df, "Energy intensity of coal in LPG cracking", col, 0.0),
            "Heat":        _get_val(df, "Energy intensity of heat in LPG cracking", col, 0.0),
            "Biomass":     _get_val(df, "Energy intensity of biomass in LPG cracking", col, 0.0),
            "Hydrogen":    _get_val(df, "Energy intensity of hydrogen in LPG cracking", col, 0.0),
        }

        for fuel in FUELS_ORDER:
            prod_fuel = prod_lpg * lpg_shares[fuel]
            demand = prod_fuel * lpg_intensity[fuel]
            _add(
                rows, year, sector, subsector,
                product="High Value Chemicals", process=process_hvc, tech=tech_lpg,
                dropdown="Fuel", fuel=fuel, level="Fuel", desc=fuel,
                total_prod="", share_proc="", prod_proc="",
                share_tech="", prod_tech="",
                share_fuel=lpg_shares_pct[fuel],
                prod_fuel=prod_fuel,
                spec_intensity=lpg_intensity[fuel],
                fuel_demand=demand,
                scenario_col=scenario_col,
            )

        # ----- Route 3: Methanol route
        share_meoh_pct = _get_val(df, "Share of Methanol route for HVC production", col, 0.0)
        share_meoh = share_meoh_pct / 100.0
        prod_meoh = hvc_total * share_meoh

        tech_meoh = "Methanol route"
        _add(
            rows, year, sector, subsector,
            product="High Value Chemicals", process=process_hvc, tech=tech_meoh,
            dropdown="Technology", fuel="", level="Technology", desc=tech_meoh,
            total_prod="", share_proc="", prod_proc="",
            share_tech=share_meoh_pct, prod_tech=prod_meoh,
            share_fuel="", prod_fuel="",
            spec_intensity="", fuel_demand="", scenario_col=scenario_col,
        )

        meoh_shares_pct = {
            "Diesel":      _get_val(df, "Share of diesel for Methanol route", col, 0.0),
            "Natural Gas": _get_val(df, "Share of natural gas for Methanol route", col, 0.0),
            "Electricity": _get_val(df, "Share of electricity for Methanol route", col, 0.0),
            "Coal":        _get_val(df, "Share of coal for Methanol route", col, 0.0),
            "Heat":        _get_val(df, "Share of heat for Methanol route", col, 0.0),
            "Biomass":     _get_val(df, "Share of biomass for Methanol route", col, 0.0),
            "Hydrogen":    _get_val(df, "Share of hydrogen for Methanol route", col, 0.0),
        }
        meoh_shares = {k: v / 100.0 for k, v in meoh_shares_pct.items()}

        meoh_intensity = {
            "Diesel":      _get_val(df, "Energy intensity of diesel in Methanol route", col, 0.0),
            "Natural Gas": _get_val(df, "Energy intensity of natural gas in Methanol route", col, 0.0),
            "Electricity": _get_val(df, "Energy intensity of electricity in Methanol route", col, 0.0),
            "Coal":        _get_val(df, "Energy intensity of coal in Methanol route", col, 0.0),
            "Heat":        _get_val(df, "Energy intensity of heat in Methanol route", col, 0.0),
            "Biomass":     _get_val(df, "Energy intensity of biomass in Methanol route", col, 0.0),
            "Hydrogen":    _get_val(df, "Energy intensity of hydrogen in Methanol route", col, 0.0),
        }

        for fuel in FUELS_ORDER:
            prod_fuel = prod_meoh * meoh_shares[fuel]
            demand = prod_fuel * meoh_intensity[fuel]
            _add(
                rows, year, sector, subsector,
                product="High Value Chemicals", process=process_hvc, tech=tech_meoh,
                dropdown="Fuel", fuel=fuel, level="Fuel", desc=fuel,
                total_prod="", share_proc="", prod_proc="",
                share_tech="", prod_tech="",
                share_fuel=meoh_shares_pct[fuel],
                prod_fuel=prod_fuel,
                spec_intensity=meoh_intensity[fuel],
                fuel_demand=demand,
                scenario_col=scenario_col,
            )

    # ===========================================================
    # 3. UNSPECIFIED CHEMICALS
    # ===========================================================
    u_total = _get_val(df, "Activity factor of unspecified chemicals", col, 0.0)

    # Product header
    _add(
        rows, year, sector, subsector,
        product="Unspecified Chemical", process="", tech="",
        dropdown="Product", fuel="", level="Product", desc="Unspecified Chemical",
        total_prod=u_total, share_proc="", prod_proc="",
        share_tech="", prod_tech="",
        share_fuel="", prod_fuel="",
        spec_intensity="", fuel_demand="", scenario_col=scenario_col,
    )

    u_proc = "Unspecified Chemical"
    _add(
        rows, year, sector, subsector,
        product="Unspecified Chemical", process=u_proc, tech="",
        dropdown="Process", fuel="", level="Process", desc=u_proc,
        total_prod="", share_proc=100.0, prod_proc=u_total,
        share_tech="", prod_tech="",
        share_fuel="", prod_fuel="",
        spec_intensity="", fuel_demand="", scenario_col=scenario_col,
    )

    u_tech = "Unspecified Chemical"
    _add(
        rows, year, sector, subsector,
        product="Unspecified Chemical", process=u_proc, tech=u_tech,
        dropdown="Technology", fuel="", level="Technology", desc=u_tech,
        total_prod="", share_proc="", prod_proc="",
        share_tech=100.0, prod_tech=u_total,
        share_fuel="", prod_fuel="",
        spec_intensity="", fuel_demand="", scenario_col=scenario_col,
    )

    u_shares_pct = {
        "Diesel":      _get_val(df, "Share of diesel for unspecified chemicals", col, 0.0),
        "Natural Gas": _get_val(df, "Share of natural gas for unspecified chemicals", col, 0.0),
        "Electricity": _get_val(df, "Share of electricity for unspecified chemicals", col, 0.0),
        "Coal":        _get_val(df, "Share of coal for unspecified chemicals", col, 0.0),
        "Heat":        _get_val(df, "Share of heat for unspecified chemicals", col, 0.0),
        "Biomass":     _get_val(df, "Share of biomass for unspecified chemicals", col, 0.0),
        "Hydrogen":    _get_val(df, "Share of hydrogen for unspecified chemicals", col, 0.0),
    }
    u_shares = {k: v / 100.0 for k, v in u_shares_pct.items()}

    # No intensity given → set to 0 so fuel demand is 0 (like your example)
    for fuel in FUELS_ORDER:
        prod_fuel = u_total * u_shares[fuel]
        inten = 0.0
        demand = prod_fuel * inten
        _add(
            rows, year, sector, subsector,
            product="Unspecified Chemical", process=u_proc, tech=u_tech,
            dropdown="Fuel", fuel=fuel, level="Fuel", desc=fuel,
            total_prod="", share_proc="", prod_proc="",
            share_tech="", prod_tech="",
            share_fuel=u_shares_pct[fuel],
            prod_fuel=prod_fuel,
            spec_intensity=inten,
            fuel_demand=demand,
            scenario_col=scenario_col,
        )

    out = pd.DataFrame(rows)
    return out[COL_ORDER]


def build_ammonia_full_table_from_metrics(df_metrics: pd.DataFrame) -> pd.DataFrame:
    """
    (Name kept for compatibility)
    Take the metrics workbook for one country and build the full detailed
    Chemical table (Ammonia + HVC + Unspecified) for all scenario columns.
    """
    if "Metric" not in df_metrics.columns:
        raise ValueError("Input must contain a 'Metric' column.")

    scenario_cols = [c for c in df_metrics.columns if c not in ("Metric", "Units")]
    frames = [build_chemicals_for_col(df_metrics, col) for col in scenario_cols]
    all_scenarios = pd.concat(frames, ignore_index=True)

    if "Year" in all_scenarios.columns:
        all_scenarios = all_scenarios.sort_values(["Year", "Scenario_col"], kind="stable")

    return all_scenarios[COL_ORDER]


def build_ammonia_tidy_feedstock(full_df: pd.DataFrame) -> pd.DataFrame:
    """
    From detailed Chemical table, create tidy feedstock table.
    (Again name kept for compatibility with the rest of the pipeline.)
    """
    tidy = full_df[full_df["Dropdown"] == "Fuel"].copy()

    tidy = tidy[
        [
            "Year",
            "Scenario_col",
            "Sector",
            "Sub sector",
            "Product",
            "Process",
            "Technology",
            "Fuel/Feedstock",
            "final energy demand",
        ]
    ]

    tidy["Units"] = "MWh"

    tidy = tidy.sort_values(
        ["Year", "Scenario_col", "Sector", "Sub sector", "Product", "Process", "Technology", "Fuel/Feedstock"]
    )

    return tidy


def _chemicals_bucket(product: str, process: str, tech: str) -> Optional[str]:
    """
    Map (Product, Process, Technology) → SEC bucket for Chemicals.
    """
    p = str(product).strip()
    pr = str(process).strip()
    t = str(tech).strip()

    # Ammonia
    if p == "Ammonia" and pr == "Ammonia synthesis":
        if t == "SMR + Haber-Bosch":
            return "Industry Chemical Ammonia SMR"
        if t == "Renewable Ammonia Synthesis":
            return "Industry Chemical Ammonia Renewable"
        # Any other Ammonia tech → Other conventional
        return "Industry Chemical Ammonia Other conventional"

    # High Value Chemicals
    if p == "High Value Chemicals" and pr == "HVC production":
        if t == "Naphtha cracking":
            return "Industry Chemical HVC Naphtha"
        if t == "LPG cracking":
            return "Industry Chemical HVC LPG"
        if t == "Methanol route":
            return "Industry Chemical HVC Methanol"

    # Unspecified chemical → no SEC bucket (None → dropped)
    return None


def build_sec_ammonia_from_tidy(df: pd.DataFrame, country_name: Optional[str] = None) -> pd.DataFrame:
    """
    Build Chemicals SEC table from tidy feedstock (ammonia + HVC).
    Returns columns: Year, Scenario, SEC_Fuel, <AMMONIA_SEC_COLS>
    """
    df = df.copy()

    # Assign buckets
    df["Bucket"] = df.apply(
        lambda r: _chemicals_bucket(r.get("Product", ""), r.get("Process", ""), r.get("Technology", "")),
        axis=1
    )
    df = df[df["Bucket"].notna()].copy()

    # Parse Year / Scenario
    ys = df["Scenario_col"].apply(parse_year_and_scenario)
    df["Year_extracted"] = ys.apply(lambda t: t[0])
    df["Scenario_label"] = ys.apply(lambda t: t[1])

    # Map fuels → SEC fuel types
    df["SEC_Fuel"] = df["Fuel/Feedstock"].map(FUEL_TO_SEC)
    df = df[df["SEC_Fuel"].notna()].copy()

    df["final energy demand"] = pd.to_numeric(df["final energy demand"], errors="coerce").fillna(0.0)

    # Sum by bucket and fuel
    grp = (
        df.groupby(["Year_extracted", "Scenario_label", "SEC_Fuel", "Bucket"], dropna=False)["final energy demand"]
        .sum()
        .reset_index()
    )

    # Total row per bucket (all fuels)
    total = (
        df.groupby(["Year_extracted", "Scenario_label", "Bucket"], dropna=False)["final energy demand"]
        .sum()
        .reset_index()
    )
    total["SEC_Fuel"] = "Total"

    comb = pd.concat([grp, total], ignore_index=True)

    piv = (
        comb.pivot_table(
            index=["Year_extracted", "Scenario_label", "SEC_Fuel"],
            columns="Bucket",
            values="final energy demand",
            aggfunc="sum",
            fill_value=0,
        )
        .reset_index()
    )

    # Ensure all desired columns exist
    for c in AMMONIA_SEC_COLS:
        if c not in piv.columns:
            piv[c] = 0.0

    # Order SEC_Fuel rows
    piv["__order__"] = piv["SEC_Fuel"].map({name: i for i, name in enumerate(ROW_ORDER)})
    piv = piv.sort_values(["Year_extracted", "Scenario_label", "__order__"]).drop(columns="__order__")

    piv = piv.rename(columns={
        "Year_extracted": "Year",
        "Scenario_label": "Scenario",
    })

    out = piv[["Year", "Scenario", "SEC_Fuel"] + AMMONIA_SEC_COLS].copy()

    if country_name:
        ammonia_target_col = "Industry Chemical Ammonia Renewable"
        methanol_target_col = "Industry Chemical HVC Methanol"
        combos = out[["Year", "Scenario"]].drop_duplicates()

        def _add_fuel_to_bucket(y, sc, sec_fuel: str, bucket_col: str, value_mwh: float):
            if value_mwh == 0.0:
                return
            mask_fuel = (
                (out["Year"] == y) &
                (out["Scenario"] == sc) &
                (out["SEC_Fuel"] == sec_fuel)
            )
            if mask_fuel.any():
                out.loc[mask_fuel, bucket_col] = out.loc[mask_fuel, bucket_col] + value_mwh
            else:
                new_row = {"Year": y, "Scenario": sc, "SEC_Fuel": sec_fuel}
                for c in AMMONIA_SEC_COLS:
                    new_row[c] = 0.0
                new_row[bucket_col] = value_mwh
                out.loc[len(out)] = new_row

            mask_total = (
                (out["Year"] == y) &
                (out["Scenario"] == sc) &
                (out["SEC_Fuel"] == "Total")
            )
            if mask_total.any():
                out.loc[mask_total, bucket_col] = out.loc[mask_total, bucket_col] + value_mwh

        for _, row in combos.iterrows():
            y = int(row["Year"])
            sc = row["Scenario"]
            _add_fuel_to_bucket(y, sc, "Ammonia", ammonia_target_col, _load_external_ammonia_mwh(country_name, y, sc))

    out["__order__"] = out["SEC_Fuel"].map({name: i for i, name in enumerate(ROW_ORDER)})
    out = out[out["__order__"].notna()].sort_values(["Year", "Scenario", "__order__"]).drop(columns="__order__")
    return out


def build_carrier_table_from_sec(sec_all: pd.DataFrame, country_name: str, df_metrics: pd.DataFrame = None) -> pd.DataFrame:
    """
    Build a 'carrier-level' table including ALL aggregated sectors and individual 'Other' sectors.
    For 'steel' carrier, adds green path steel in tonnes (Steel Production × DRI+EAF Share).
    """
    iso = get_iso_code(country_name)

    # Subsector groups for the 4 main aggregated columns
    steel_cols = [c for c in sec_all.columns if "Steel" in c and "Other" not in c]
    nmm_cols = [c for c in sec_all.columns if "NMM" in c]
    pp_cols = [c for c in sec_all.columns if "Paper and pulp" in c]
    chem_cols = [c for c in sec_all.columns if "Chemical" in c]
    
    # Map for the 7 other individual sectors
    other_mapping = {
        "Industry Machinery": "machinery",
        "Industry Construction": "construction",
        "Industry Non-ferrous Metals": "non-ferrous metals",
        "Industry Transport Equipment": "transport equipment",
        "Industry Food and Tobacco": "food and tobacco",
        "Industry Mining and Quarrying": "mining and quarrying",
        "Industry Textile and Leather": "textile and leather",
        "Industry Wood and Wood Products": "wood and wood products"
    }

    rows = []
    # Loop through all Year/Scenario combos present in the data
    combos = sec_all[["Year", "Scenario"]].drop_duplicates().sort_values(["Year", "Scenario"]).itertuples(index=False)

    for year, scenario in combos:
        # Loop through ALL carriers (skip "Total" - it's a summary, not a carrier)
        for fuel_row in ROW_ORDER:
            if fuel_row == "Total":
                continue
            sub = sec_all[
                (sec_all["Year"] == year) & 
                (sec_all["Scenario"] == scenario) & 
                (sec_all["SEC_Fuel"] == fuel_row)
            ]

            row_dict = {
                "country": iso,
                "scenario": scenario,
                "year": int(year),
                "carrier": fuel_row.lower()
            }

            if not sub.empty:
                data = sub.iloc[0]
                # Sum the 4 main big categories
                row_dict["iron and steel"] = data[steel_cols].sum()
                row_dict["non-metallic minerals"] = data[nmm_cols].sum()
                row_dict["paper pulp and print"] = data[pp_cols].sum()
                row_dict["chemical and petrochemical"] = data[chem_cols].sum()

                # Map the 7 other individual industry sectors
                for sec_col, short_name in other_mapping.items():
                    row_dict[short_name] = data.get(sec_col, 0.0)
                
                # For 'steel' carrier, add green path steel (tonnes)
                if fuel_row.lower() == "steel" and df_metrics is not None:
                    # Get steel production for this year/scenario
                    # Handle base year (2020) which has no scenario suffix in df_metrics
                    if int(year) == 2020 or scenario == "Historic":
                        col_name = "2020"
                    else:
                        col_name = f"{year}_{scenario}"
                    steel_prod = _get_val(df_metrics, "Steel production per year", col_name, 0.0)
                    # Get DRI+EAF share (green path) directly from df_metrics
                    green_share_pct = _get_val(df_metrics, "Share of direct reduction + electric arc furnace for steel making", col_name, 0.0)
                    # Green path steel in tonnes (share is in %, so divide by 100)
                    green_path_steel = steel_prod * (green_share_pct / 100.0)
                    row_dict["iron and steel"] = green_path_steel
                
                rows.append(row_dict)
            else:
                # Optional: Handle missing carrier rows by setting them to 0
                row_dict.update({
                    "iron and steel": 0.0, "non-metallic minerals": 0.0, 
                    "paper pulp and print": 0.0, "chemical and petrochemical": 0.0
                })
                row_dict.update({v: 0.0 for v in other_mapping.values()})
                rows.append(row_dict)

    df_car = pd.DataFrame(rows)
    df_car["carrier"] = pd.Categorical(df_car["carrier"], categories=CARRIER_ORDER, ordered=True)
    # Remove rows where carrier became NaN (not in CARRIER_ORDER)
    df_car = df_car[df_car["carrier"].notna()].copy()
    
    # Order columns as requested
    final_cols = [
        "country", "scenario", "year", "carrier",
        "chemical and petrochemical", "iron and steel",
        "non-metallic minerals", "paper pulp and print"
    ] + list(other_mapping.values())
    
    return df_car.sort_values(["country", "scenario", "year", "carrier"])[final_cols]

# -------------------------------------------------------------------
# FEEDSTOCK & SEC PIPELINE
# -------------------------------------------------------------------

def build_all_feedstock_from_metrics(input_path: Path, output_path: Path, df_override: pd.DataFrame = None):
    """
    Read metrics workbook and build feedstock tables for:
      - Steel
      - Non metallic minerals
      - Paper and pulp
      - Ammonia
    Writes them to 'output_path' with sheets:
      - "Steel"
      - "Non metallic minerals"
      - "Paper and pulp"
      - "Ammonia"
      
    If df_override is provided, use it instead of reading from input_path.
    This allows using CAGR-updated metrics.
    """
    if df_override is not None:
        df_metrics = df_override
    else:
        df_metrics = pd.read_csv(input_path)

    steel_full = build_steel_full_table_from_metrics(df_metrics)
    steel_tidy = build_steel_tidy_feedstock(steel_full)

    nmm_full = build_nmm_full_table_from_metrics(df_metrics)
    nmm_tidy = build_nmm_tidy_feedstock(nmm_full)

    pp_full = build_paper_pulp_full_table_from_metrics(df_metrics)
    pp_tidy = build_paper_pulp_tidy_feedstock(pp_full)

    ammo_full = build_ammonia_full_table_from_metrics(df_metrics)
    ammo_tidy = build_ammonia_tidy_feedstock(ammo_full)

    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        steel_tidy.to_excel(writer, sheet_name="Steel", index=False)
        nmm_tidy.to_excel(writer, sheet_name="Non metallic minerals", index=False)
        pp_tidy.to_excel(writer, sheet_name="Paper and pulp", index=False)
        ammo_tidy.to_excel(writer, sheet_name="Ammonia", index=False)

    print(f" Saved final energy demand → {output_path}")


def build_sec_table_from_feedstock(
    input_xlsx: Path,
    output_xlsx: Path,
    country_name: str,
    df_metrics: pd.DataFrame,
    sheet_name: str = "SEC",
    
):
    """
    Read energy_demand_summary.xlsx and build:
      - SEC sheet (Steel + NMM + Paper & Pulp + Ammonia)
      - Carrier sheet with aggregated sectors per carrier
    """
    steel_df = pd.read_excel(input_xlsx, sheet_name="Steel")
    nmm_df = pd.read_excel(input_xlsx, sheet_name="Non metallic minerals")
    pp_df = pd.read_excel(input_xlsx, sheet_name="Paper and pulp")
    ammo_df = pd.read_excel(input_xlsx, sheet_name="Ammonia")

    sec_steel = build_sec_steel_from_tidy(steel_df)
    sec_nmm = build_sec_nmm_from_tidy(nmm_df)
    sec_pp = build_sec_paper_pulp_from_tidy(pp_df)
    sec_ammo = build_sec_ammonia_from_tidy(ammo_df, country_name=country_name)
    
    sec_other = build_sec_other_from_output(df_metrics, country_name)

    sec_all = reduce(
        lambda left, right: pd.merge(left, right, on=["Year", "Scenario", "SEC_Fuel"], how="outer"),
        [sec_steel, sec_nmm, sec_pp, sec_ammo, sec_other],
    )

    # Fill NaNs in numeric columns
    num_cols = [c for c in sec_all.columns if c not in ["Year", "Scenario", "SEC_Fuel"]]
    sec_all[num_cols] = sec_all[num_cols].fillna(0.0)

    sec_all["SEC_Fuel"] = pd.Categorical(sec_all["SEC_Fuel"], categories=ROW_ORDER, ordered=True)
    # Remove rows where SEC_Fuel became NaN (not in ROW_ORDER)
    sec_all = sec_all[sec_all["SEC_Fuel"].notna()].copy()
    sec_all = sec_all.sort_values(["Year", "Scenario", "SEC_Fuel"]).reset_index(drop=True)

    desired_cols = ["Year", "Scenario", "SEC_Fuel"] + STEEL_SEC_COLS + NMM_SEC_COLS + PP_SEC_COLS + AMMONIA_SEC_COLS  + OTHER_SEC_COLS
    for c in desired_cols:
        if c not in sec_all.columns:
            sec_all[c] = 0.0
    sec_all = sec_all[desired_cols]

    # === NEW: build the carrier sheet ===
    carriers_df = build_carrier_table_from_sec(sec_all, country_name, df_metrics)

    with pd.ExcelWriter(output_xlsx, engine="xlsxwriter") as writer:
        # SEC sheet
        sec_all.to_excel(writer, sheet_name=sheet_name, index=False)

        wb = writer.book
        ws = writer.sheets[sheet_name]
        num_fmt = wb.add_format({"num_format": "#,##0.00"})
        ws.set_column(0, 0, 8)   # Year
        ws.set_column(1, 1, 18)  # Scenario
        ws.set_column(2, 2, 12)  # SEC_Fuel
        ws.set_column(3, 3 + len(STEEL_SEC_COLS) + len(NMM_SEC_COLS) + len(PP_SEC_COLS) + len(AMMONIA_SEC_COLS) - 1, 20, num_fmt)

        # Carrier sheet (second sheet in the same file)
        carriers_df.to_excel(writer, sheet_name="carrier_energy", index=False)

    print(f"Saved combined SEC table → {output_xlsx}")
    print(f"Saved carrier-level table → {output_xlsx}")
    return carriers_df

def build_presentation_summary(sec_all: pd.DataFrame, country_name: str) -> pd.DataFrame:
    """
    Generates a high-level summary table (Presentation style).
    Aggregates ALL industry sectors dynamically.
    """
    iso = get_iso_code(country_name)
    metadata_cols = ["Year", "Scenario", "SEC_Fuel"]
    
    # Automatically identify ALL individual sector columns present in the SEC sheet
    sector_cols = [c for c in sec_all.columns if c not in metadata_cols]
    
    summary = sec_all[metadata_cols].copy()
    summary.insert(0, "Country", iso) # Add Country at the start
    
    # Calculate Total Industry Demand
    summary["Total Industry Energy (MWh)"] = sec_all[sector_cols].sum(axis=1)
    
    # Add individual columns for every sector found (cleaned names)
    for col in sector_cols:
        clean_name = col.replace("Industry ", "")
        summary[clean_name] = sec_all[col]

    return summary

def export_energy_totals(all_countries_carrier_dfs: List[pd.DataFrame]):
    """
    Groups all collected data by Scenario and Year, then saves 
    each group as a separate CSV directly in output_data/ folder.
    Aligned with transport folder structure.
    """
    if not all_countries_carrier_dfs:
        return

    master_df = pd.concat(all_countries_carrier_dfs, ignore_index=True)
    
    root = get_industry_root()
    total_dir = root / "output_data"
    total_dir.mkdir(parents=True, exist_ok=True)

    groups = master_df.groupby(['scenario', 'year'])

    for (scen, year), group_df in groups:
        clean_scen = str(scen).replace(" ", "_")
        # Match transport naming: industry_all_2020.csv for historic, industry_BAU_2030.csv for scenarios
        if clean_scen == "Historic":
            file_name = f"industry_all_{year}.csv"
        else:
            file_name = f"industry_{clean_scen}_{year}.csv"
        file_path = total_dir / file_name
        
        group_df.to_csv(file_path, index=False, encoding='utf-8')
        print(f"  [Global Export] Saved: {file_path.name}")

def run_industry_pipeline_for_country(country: str):
    """
    1. Find latest run folder in output_data
    2. Find that country's metrics .xlsx file
    3. Get ISO2 code dynamically
    4. Create output_data/country_specific/<Country> folder
    5. Run pipeline with ISO2 code in filenames
    """
    latest_folder = find_latest_run_folder()
    country_file = find_country_file(latest_folder, country)
    
    # --- USE THE HELPER FUNCTION HERE ---
    iso_code = get_iso_code(country)
    # ------------------------------------

    print(f"Using latest folder: {latest_folder.name}")
    print(f"Using country file: {country_file.name}")
    #print(f"Detected ISO code: {iso_code}") # Helpful for debugging

    results_dir = get_results_folder(country)

    # Filenames using the dynamic ISO code
    feedstock_filename = f"{iso_code}_energy_demand_summary.xlsx"
    sec_filename = f"{iso_code}_final_energy_demand.xlsx"

    feedstock_out = results_dir / feedstock_filename
    sec_out = results_dir / sec_filename

    df_metrics = pd.read_csv(country_file)

    # === APPLY CAGR PROJECTIONS (aligned with transport workflow) ===
    if industry_config_path.exists():
        print(f"  >>> Found config! Refreshing projections for {country}...")
        df_metrics = apply_cagr_projections(df_metrics, industry_config_path, country, base_year="2020")
        
        # === APPLY SHARE OVERRIDES (for other industries fuel shares) ===
        df_metrics = apply_share_overrides(df_metrics, industry_config_path, country)
        
        # Save the refreshed data for verification (aligned with transport naming)
        updated_path = results_dir / f"output_{country}_updated.csv"
        df_metrics.to_csv(updated_path, index=False)
        print(f"  Saved updated metrics → {updated_path}")
    else:
        print(f"  Warning: industry_config.csv NOT found at {industry_config_path}")

    build_all_feedstock_from_metrics(country_file, feedstock_out, df_override=df_metrics)

    carriers_df = build_sec_table_from_feedstock(
        feedstock_out,
        sec_out,
        country_name=country,
        df_metrics=df_metrics,      
        sheet_name="SEC"
    )
    return carriers_df


# -------------------------------------------------------------------
# CLI / manual run
# -------------------------------------------------------------------
if __name__ == "__main__":
    # List to store dataframes from all countries
    all_carrier_data = []

    for country in available_countries:
        print(f"  - Processing: {country}")
        try:
            # Run the pipeline and capture the carrier dataframe
            country_carrier_df = run_industry_pipeline_for_country(country)
            if country_carrier_df is not None:
                all_carrier_data.append(country_carrier_df)
        except Exception as e:
            print(f"Error processing {country}: {e}")

    # After all countries are processed, generate the individual CSVs
    print("\nGenerating scenario-specific CSV totals...")
    export_energy_totals(all_carrier_data)
    print("Done.")