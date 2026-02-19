import re
from pathlib import Path
from typing import List, Optional
from functools import reduce
import pycountry
import pandas as pd

# -------------------------------------------------------------------
# CONFIG
# -------------------------------------------------------------------

# Set to None to auto-find the latest, or set to a specific name like "industry_config"
CHOOSE_FOLDER = "industry_config"

# Countries to run – you just edit this list
AVAILABLE_COUNTRIES = ["Chile", "Morocco", "Egypt","South Africa"]
                        #"Republic of the Congo", "Egypt", "Ethiopia", "Ghana","Kenya","Namibia","Niger",
                        # "Algeria","Argentina","Brazil","Chile","Colombia","Mexico","Peru","Venezuela",
                        #"Morocco","Tunisia","Tanzania", "South Africa","Libya",

                        #G20 countries
                        #"Argentina", "Australia", "Brazil", "Canada", "China", "France", "Germany",  
                        #"India", "Indonesia", "Italy", "Japan", "Mexico","Russia", "Saudi Arabia", 
                        #"South Africa", "South Korea", "United Kingdom", "United States"]

# todo select_output_data = [""]

# Order of carriers in the new "carrier" sheet
CARRIER_ORDER = [
    "oil",
    "gas",
    "electricity",
    "coal",
    "biomass",
    "hydrogen",
    "ammonia",
    "steel",
    "methanol",
    "process emissions",
    "low-temperature heat",
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
ROW_ORDER = ["Total", "Oil", "Gas", "Electricity", "Coal", "Heat", "Biomass", "Hydrogen", "Ammonia", "Methanol"]

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
    "Steel": "Steel", "steel": "Steel"
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
    "Industry Transport Equipment",
    "Industry Food and Tobacco",
    "Industry Mining and Quarrying",
    "Industry Textile and Leather",
    "Industry Wood and Wood Products",
]
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
            return result[0].alpha_2
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
    if CHOOSE_FOLDER:
        target = output_data / CHOOSE_FOLDER
        if target.exists() and target.is_dir():
            print(f"--- Using selected folder: {CHOOSE_FOLDER} ---")
            return target
        else:
            print(f"Warning: Selected folder '{CHOOSE_FOLDER}' not found. Searching for latest...")

    # 2. Fallback: Find the most recent folder
    subdirs = [p for p in output_data.iterdir() if p.is_dir()]
    if not subdirs:
        raise FileNotFoundError(f"No run folders found in: {output_data}")

    latest = max(subdirs, key=lambda p: p.stat().st_mtime)
    print(f"--- Using latest run folder: {latest.name} ---")
    return latest


def find_country_file(run_folder: Path, country: str) -> Path:
    """
    Search inside run_folder for an .xlsx whose name contains the country.
    Example: 'Morocco_Output.xlsx', 'Morocco_industry.xlsx', ...
    """
    country_lower = country.lower()
    candidates = [
        p for p in run_folder.glob("*.csv")
        if country_lower in p.stem.lower()
    ]

    if not candidates:
        raise FileNotFoundError(
            f"No Excel file found for country '{country}' in {run_folder}"
        )

    # If multiple, just take the first one (you can refine later)
    return candidates[0]


def get_results_folder(country: str) -> Path:
    """
    Create (if needed) .../industry/results/<Country> and return it.
    """
    root = get_industry_root()
    results_root = root / "results"
    results_root.mkdir(exist_ok=True)

    country_folder = results_root / country.replace(" ", "_")
    country_folder.mkdir(exist_ok=True)
    return country_folder


def build_sec_other_from_output(df_output: pd.DataFrame) -> pd.DataFrame:
    frames = []
    # Ensure these match the EXACT string in your "Metric" column in Morocco_Output
    sector_map = {
        "machinery": "Industry Machinery",
        "construction": "Industry Construction",
        "transport equipment": "Industry Transport Equipment",
        "food and tobacco": "Industry Food and Tobacco",
        "mining and quarrying": "Industry Mining and Quarrying",
        "textile and leather": "Industry Textile and Leather",
        "wood and wood products": "Industry Wood and Wood Products"
    }

    TARGET_FUELS = ["Diesel", "Natural Gas", "Electricity", "Coal", "Heat", "Biomass", "Hydrogen", "Ammonia", "Methanol", "Steel"]
    scenario_cols = [c for c in df_output.columns if c not in ["Metric", "Units"]]

    for col in scenario_cols:
        year = _first_year_in_string(col)
        # Fix: Ensure scenario name is cleaned (e.g., '2030_AP' -> 'AP')
        scenario = col.split("_", 1)[1] if "_" in str(col) else "Historic"
        rows = []

        for metric_key, sec_label in sector_map.items():
            # IMPORTANT: Check if metric name is 'Final energy of food and tobacco' 
            # or 'Final energy demand of food and tobacco'
            total_demand = _get_val(df_output, f"Final energy of {metric_key}", col, 0.0)
            
            # If total_demand is 0, try searching for the metric without "of"
            if total_demand == 0:
                total_demand = _get_val(df_output, f"Final energy {metric_key}", col, 0.0)

            shares = {
                "Diesel": _get_val(df_output, f"Share of oil for unspecified {metric_key}", col, 0.0) / 100,
                "Natural Gas": _get_val(df_output, f"Share of gas for unspecified {metric_key}", col, 0.0) / 100,
                "Electricity": _get_val(df_output, f"Share of electricity for unspecified {metric_key}", col, 0.0) / 100,
                "Coal": _get_val(df_output, f"Share of coal for unspecified {metric_key}", col, 0.0) / 100,
                "Heat": _get_val(df_output, f"Share of heat for unspecified {metric_key}", col, 0.0) / 100,
                "Biomass": _get_val(df_output, f"Share of biomass for unspecified {metric_key}", col, 0.0) / 100,
                "Hydrogen": _get_val(df_output, f"Share of hydrogen for unspecified {metric_key}", col, 0.0) / 100,
            }

            for fuel_key in TARGET_FUELS:
                share_val = shares.get(fuel_key, 0.0)
                # If your numbers are too big, divide by a factor (e.g., 1e6) here if the source is in Joules
                fuel_demand = (total_demand * 1000) * share_val
                
                rows.append({
                    "Year": year,
                    "Scenario": scenario,
                    "SEC_Fuel": FUEL_TO_SEC.get(fuel_key, fuel_key),
                    sec_label: fuel_demand
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
        prod_fuel = unspecified_activity * unsp_share[f]
        inten = 0.0
        demand = prod_fuel * inten
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


def build_sec_ammonia_from_tidy(df: pd.DataFrame) -> pd.DataFrame:
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

    return piv[["Year", "Scenario", "SEC_Fuel"] + AMMONIA_SEC_COLS]


def build_carrier_table_from_sec(sec_all: pd.DataFrame, country_name: str) -> pd.DataFrame:
    """
    Build a 'carrier-level' table including ALL aggregated sectors and individual 'Other' sectors.
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
        # Loop through ALL carriers (including Ammonia, Methanol, and Heat)
        for fuel_row in ROW_ORDER: 
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

def build_all_feedstock_from_metrics(input_path: Path, output_path: Path):
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
    """
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
    sec_ammo = build_sec_ammonia_from_tidy(ammo_df)
    
    sec_other = build_sec_other_from_output(df_metrics)

    sec_all = reduce(
        lambda left, right: pd.merge(left, right, on=["Year", "Scenario", "SEC_Fuel"], how="outer"),
        [sec_steel, sec_nmm, sec_pp, sec_ammo, sec_other],
    )

    # Fill NaNs in numeric columns
    num_cols = [c for c in sec_all.columns if c not in ["Year", "Scenario", "SEC_Fuel"]]
    sec_all[num_cols] = sec_all[num_cols].fillna(0.0)

    sec_all["SEC_Fuel"] = pd.Categorical(sec_all["SEC_Fuel"], categories=ROW_ORDER, ordered=True)
    sec_all = sec_all.sort_values(["Year", "Scenario", "SEC_Fuel"]).reset_index(drop=True)

    desired_cols = ["Year", "Scenario", "SEC_Fuel"] + STEEL_SEC_COLS + NMM_SEC_COLS + PP_SEC_COLS + AMMONIA_SEC_COLS  + OTHER_SEC_COLS
    for c in desired_cols:
        if c not in sec_all.columns:
            sec_all[c] = 0.0
    sec_all = sec_all[desired_cols]

    # === NEW: build the carrier sheet ===
    carriers_df = build_carrier_table_from_sec(sec_all, country_name)

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
    each group as a separate CSV in results/energy_totals.
    """
    if not all_countries_carrier_dfs:
        return

    master_df = pd.concat(all_countries_carrier_dfs, ignore_index=True)
    
    root = get_industry_root()
    total_dir = root / "results" / "energy_totals"
    total_dir.mkdir(parents=True, exist_ok=True)

    groups = master_df.groupby(['scenario', 'year'])

    for (scen, year), group_df in groups:
        clean_scen = str(scen).replace(" ", "_")
        file_name = f"{clean_scen}_{year}.csv"
        file_path = total_dir / file_name
        
        group_df.to_csv(file_path, index=False, encoding='utf-8')
        print(f"  [Global Export] Saved: {file_path}")

def run_industry_pipeline_for_country(country: str):
    """
    1. Find latest run folder in output_data
    2. Find that country's metrics .xlsx file
    3. Get ISO2 code dynamically
    4. Create results/<Country> folder
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

    build_all_feedstock_from_metrics(country_file, feedstock_out)

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

    for country in AVAILABLE_COUNTRIES:
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