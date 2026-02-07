import os
import glob
import pandas as pd
import numpy as np

import pycountry

# =============================================================================
# 1. SETUP & CONFIGURATION
# =============================================================================

# Get the absolute path of this script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TRANSPORT_OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output_data")
RESULTS_DIR = os.path.join(SCRIPT_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

# List of countries to process
COUNTRY = [ 
    "Republic of the Congo", "Egypt", "Ethiopia", "Ghana","Kenya","Namibia","Niger",
    "Algeria","Argentina","Brazil","Chile","Colombia","Mexico","Peru","Venezuela",
    "Morocco","Tunisia","Tanzania", "South Africa","Libya",
    "Australia", "Canada", "China", "France", "Germany",  
    "India", "Indonesia", "Italy", "Japan", "Russia", "Saudi Arabia", 
    "South Korea", "United Kingdom", "United States of America"
]


def get_iso2_country_code(c):
    try:
        # search_fuzzy handles common names like "South Korea", "Russia", "USA"
        match = pycountry.countries.search_fuzzy(c)[0]
        return match.alpha_2
    except (LookupError, AttributeError):
        # Fallback for very specific naming mismatches if pycountry fails
        print(f"Warning: Could not find ISO code for '{c}'. Using fallback.")
        return c[:2].upper()

# =============================================================================
# 2. INDICATOR GENERATION FUNCTION (ALL TWh)
# =============================================================================

def generate_transport_indicators(final_df: pd.DataFrame, country: str) -> pd.DataFrame:
    """
    Generates aggregated transport indicators.
    1. Removes 'transport' and '(TWh)' from column names.
    2. Includes 'road hydrogen' column.
    """
    df = final_df.copy()
    # Ensure numeric
    df["Final Energy Demand (TWh)"] = pd.to_numeric(df["Final Energy Demand (TWh)"], errors="coerce").fillna(0)

    # Helper: Filter and sum energy
    def sum_filter(subsector=None, mode=None, fuels=None):
        d = df.copy()
        if subsector:
            d = d[d["Subsector"].isin(subsector if isinstance(subsector, list) else [subsector])]
        if mode:
            d = d[d["Mode"].isin(mode if isinstance(mode, list) else [mode])]
        if fuels:
            d = d[d["Fuel"].isin(fuels if isinstance(fuels, list) else [fuels])]
        return d.groupby("Scenario")["Final Energy Demand (TWh)"].sum()

    # Fuel groups
    elec_fuels = ["Electricity"]
    road_modes = ["Road", "LDV", "Bus", "2&3 Wheelers", "Light-Duty Trucks", "Heavy-Duty Trucks"]

    # --- Calculations ---
    all_scenarios = df["Scenario"].unique()
    result = pd.DataFrame({"scenario": all_scenarios, "country": country}).set_index("scenario")

    # Rail
    result["electricity rail"] = sum_filter(mode=["Rail", "Passenger Train", "Freight Train"], fuels=elec_fuels)
    result["total rail"] = sum_filter(mode=["Rail", "Passenger Train", "Freight Train"])

    # Road
    result["road biomass"] = sum_filter(mode=road_modes, fuels=["Bio Diesel", "Bio Ethanol"])
    result["road electricity"] = sum_filter(mode=road_modes, fuels=elec_fuels)
    result["road hydrogen"] = sum_filter(mode=road_modes, fuels=["Hydrogen"]) # Added this
    result["road gas"] = sum_filter(mode=road_modes, fuels=["LPG", "Gas"])
    result["road oil"] = sum_filter(mode=road_modes, fuels=["Gasoline", "Diesel", "Kerosene", "Fuel Oil"])
    
    total_road = sum_filter(mode=road_modes)
    result["total road"] = total_road
    result["total road ev"] = result["road electricity"]
    result["total road fcev"] = result["road hydrogen"]
    result["total road ice"] = total_road - result["road electricity"] - result["road hydrogen"]

    # Aviation & Navigation
    result["total domestic aviation"] = sum_filter(mode=["Aviation", "Passenger Planes", "Freight Planes"])
    result["total domestic navigation"] = sum_filter(mode=["Navigation", "Passenger Ships", "Freight Ships"])
    result["total international aviation"] = sum_filter(mode="International Aviation")
    result["total international navigation"] = sum_filter(mode="International Navigation")

    result = result.fillna(0).reset_index()

    # Normalize scenario names
    def normalize_scenario(s):
        s = str(s).strip()
        if s.lower() in ["2020", "base", "baseline"]: return "base"
        return s
    result["scenario"] = result["scenario"].map(normalize_scenario)

    # --- Define final column order (Clean Names) ---
    cols = [
        "scenario", "country",
        "electricity rail", "total rail",
        "road biomass", "road electricity", "road hydrogen", "road gas", "road oil", 
        "total road", "total road ev", "total road fcev", "total road ice",
        "total domestic aviation", "total domestic navigation",
        "total international aviation", "total international navigation"
    ]
    
    result = result.reindex(columns=cols, fill_value=0)
    return result

# =============================================================================
# 3. HELPER FUNCTIONS
# =============================================================================

def get_metric(metrics_raw, key: str, scenario: str, default=0.0) -> float:
    if key not in metrics_raw:
        return float(default)
    val = metrics_raw[key].get(scenario, default)
    try:
        return float(val)
    except Exception:
        return float(default)

def pct(metrics_raw, key: str, scenario: str, default=0.0) -> float:
    return get_metric(metrics_raw, key, scenario, default) / 100.0

def safe_div(n, d):
    if d in (None, 0): return 0.0
    if d == 99999999: return 0.0
    return n / d

def add_row(rows, sector, subsector, mode, enduse, tech, fuel, scn, vkm, share, inten):
    fed_kwh = vkm * share * inten
    # CHANGE: Divide by 1e9 for TWh (instead of 1e6 for GWh)
    fed_twh = fed_kwh / 1e9  
    rows.append([sector, subsector, mode, enduse, tech, fuel, scn, fed_twh])

# =============================================================================
# 4. MAIN CALCULATION LOGIC (TWh)
# =============================================================================

def calc_for_scenario(metrics_raw: dict, scenario: str) -> pd.DataFrame:
    rows = []

    # === Population and totals ===
    pop = get_metric(metrics_raw, "Population", scenario, 0.0) * 1e6
    pkm_pc = get_metric(metrics_raw, "Mobility per capita - Passenger", scenario, 0.0)
    tkm_pc = get_metric(metrics_raw, "Mobility per capita - Freight", scenario, 0.0)
    total_pkm = pop * pkm_pc
    total_tkm = pop * tkm_pc

    # === Passenger subsector split ===
    road_pass = total_pkm * pct(metrics_raw, "Share per Subsector - Road Passenger", scenario)
    rail_pass = total_pkm * pct(metrics_raw, "Share per Subsector - Rail Passenger = Train", scenario)
    air_pass  = total_pkm * pct(metrics_raw, "Share per Subsector - Aviation Passenger = Plane", scenario)
    ship_pass = total_pkm * pct(metrics_raw, "Share per Subsector - Navigation Passenger = Ship", scenario)

    # === Passenger road mode split ===
    sh_ldv = pct(metrics_raw, "Share per Mode - LDV", scenario)
    sh_bus = pct(metrics_raw, "Share per Mode - Bus", scenario)
    sh_23w = pct(metrics_raw, "Share per Mode - 2&3W", scenario)

    ldv_pkm = road_pass * sh_ldv
    bus_pkm = road_pass * sh_bus
    w23_pkm = road_pass * sh_23w

    # === Passenger vkm conversion ===
    vkm_ldv = safe_div(ldv_pkm, get_metric(metrics_raw, "Load Factor - LDV", scenario, 1.0))
    vkm_bus = safe_div(bus_pkm, get_metric(metrics_raw, "Load Factor - Bus", scenario, 1.0))
    vkm_23w = safe_div(w23_pkm, get_metric(metrics_raw, "Load Factor - 2&3W", scenario, 1.0))
    vkm_ptr = safe_div(rail_pass, get_metric(metrics_raw, "Load Factor - Passenger Train", scenario, 1.0))
    vkm_ppl = safe_div(air_pass,  get_metric(metrics_raw, "Load Factor - Passenger Plane", scenario, 1.0))
    vkm_psh = safe_div(ship_pass, get_metric(metrics_raw, "Load Factor - Passenger Ship", scenario, 99999999))

    # === PASSENGER: LDV ===
    for tech, fuel in [
        ("Gasoline ICE", "Gasoline"), ("Diesel ICE", "Diesel"),
        ("BEV", "Electricity"), ("FCEV", "Hydrogen"),
    ]:
        add_row(rows, "Transport","Passenger","Road","LDV", tech, fuel, scenario,
                vkm_ldv,
                pct(metrics_raw, f"Share of Technology - {tech} LDV", scenario),
                get_metric(metrics_raw, f"Final Energy Intensity - {tech} LDV", scenario))

    # === PASSENGER: Bus ===
    for tech, fuel in [
        ("Diesel ICE", "Diesel"), ("BEV", "Electricity"), ("FCEV", "Hydrogen"),
    ]:
        add_row(rows, "Transport","Passenger","Road","Bus", tech, fuel, scenario,
                vkm_bus,
                pct(metrics_raw, f"Share of Technology - {tech} Bus", scenario),
                get_metric(metrics_raw, f"Final Energy Intensity - {tech} Bus", scenario))

    # === PASSENGER: 2&3 Wheelers ===
    for tech, fuel in [
        ("Gasoline ICE", "Gasoline"), ("BEV", "Electricity"),
    ]:
        add_row(rows, "Transport","Passenger","Road","2&3 Wheelers", tech, fuel, scenario,
                vkm_23w,
                pct(metrics_raw, f"Share of Technology - {tech} 2&3W", scenario),
                get_metric(metrics_raw, f"Final Energy Intensity - {tech} 2&3W", scenario))

    # === PASSENGER: Rail ===
    for tech, fuel in [
        ("Diesel ICE", "Diesel"), ("Direct Electric", "Electricity"), ("FCEV", "Hydrogen"),
    ]:
        add_row(rows, "Transport","Passenger","Rail","Passenger Train", tech, fuel, scenario,
                vkm_ptr,
                pct(metrics_raw, f"Share of Technology - {tech} Passenger Train", scenario),
                get_metric(metrics_raw, f"Final Energy Intensity - {tech} Passenger Train", scenario))

    # === PASSENGER: Aviation ===
    for tech, fuel in [
        ("Kerosene", "Kerosene"), ("BEV", "Electricity"), ("FCEV", "Hydrogen"),
    ]:
        add_row(rows, "Transport","Passenger","Aviation","Passenger Planes", tech, fuel, scenario,
                vkm_ppl,
                pct(metrics_raw, f"Share of Technology - {tech} Passenger Plane", scenario),
                get_metric(metrics_raw, f"Final Energy Intensity - {tech} Passenger Plane", scenario))

    # === PASSENGER: Ships ===
    add_row(rows, "Transport","Passenger","Navigation","Passenger Ships", "Diesel", "Diesel", scenario,
            vkm_psh,
            pct(metrics_raw, "Share of Technology - Diesel Passenger Ship", scenario),
            get_metric(metrics_raw, "Final Energy Intensity - Diesel Passenger Ship", scenario))

    # === FREIGHT subsectors ===
    road_frt = total_tkm * pct(metrics_raw, "Share per Subsector - Road Freight", scenario)
    rail_frt = total_tkm * pct(metrics_raw, "Share per Subsector - Rail Freight = Train", scenario)
    ship_frt = total_tkm * pct(metrics_raw, "Share per Subsector - Navigation Freight = Ship", scenario)

    sh_ldt = pct(metrics_raw, "Share per Mode - Light-Duty Trucks", scenario)
    sh_hdt = pct(metrics_raw, "Share per Mode - Heavy-Duty Trucks", scenario)

    ldt_tkm = road_frt * sh_ldt
    hdt_tkm = road_frt * sh_hdt

    vkm_ldt = safe_div(ldt_tkm, get_metric(metrics_raw, "Load Factor - LDT", scenario, 1.0))
    vkm_hdt = safe_div(hdt_tkm, get_metric(metrics_raw, "Load Factor - HDT", scenario, 1.0))
    vkm_ftr = safe_div(rail_frt, get_metric(metrics_raw, "Load Factor - Freight Train", scenario, 1.0))
    vkm_fsh = safe_div(ship_frt, get_metric(metrics_raw, "Load Factor - Freight Ship", scenario, 1.0))

    # === FREIGHT: Light-Duty Trucks ===
    for tech, fuel in [
        ("Diesel ICE", "Diesel"), ("BEV", "Electricity"), ("FCEV", "Hydrogen"),
    ]:
        add_row(rows, "Transport","Freight","Road","Light-Duty Trucks", tech, fuel, scenario,
                vkm_ldt,
                pct(metrics_raw, f"Share of Technology - {tech} LDT", scenario),
                get_metric(metrics_raw, f"Final Energy Intensity - {tech} LDT", scenario))

    # === FREIGHT: Heavy-Duty Trucks ===
    for tech, fuel in [
        ("Diesel ICE", "Diesel"), ("BEV", "Electricity"), ("FCEV", "Hydrogen"),
    ]:
        add_row(rows, "Transport","Freight","Road","Heavy-Duty Trucks", tech, fuel, scenario,
                vkm_hdt,
                pct(metrics_raw, f"Share of Technology - {tech} HDT", scenario),
                get_metric(metrics_raw, f"Final Energy Intensity - {tech} HDT", scenario))

    # === FREIGHT: Rail ===
    for tech, fuel in [
        ("Diesel ICE", "Diesel"), ("Direct Electric", "Electricity"), ("FCEV", "Hydrogen"),
    ]:
        add_row(rows, "Transport","Freight","Rail","Freight Train", tech, fuel, scenario,
                vkm_ftr,
                pct(metrics_raw, f"Share of Technology - {tech} Freight Train", scenario),
                get_metric(metrics_raw, f"Final Energy Intensity - {tech} Freight Train", scenario))

    # === FREIGHT: Navigation Ships ===
    for tech, fuel in [
        ("Diesel ICE", "Diesel"), ("Methanol", "Methanol"), ("Ammonia", "Ammonia"),
        ("BEV", "Electricity"), ("FCEV", "Hydrogen"),
    ]:
        add_row(rows, "Transport","Freight","Navigation","Freight Ships", tech, fuel, scenario,
                vkm_fsh,
                pct(metrics_raw, f"Share of Technology - {tech} Freight Ship", scenario),
                get_metric(metrics_raw, f"Final Energy Intensity - {tech} Freight Ship", scenario))

    # === FREIGHT: Aviation ===
    add_row(rows, "Transport","Freight","Aviation","Freight Planes","Kerosene","Kerosene", scenario,
            safe_div(total_tkm * pct(metrics_raw, "Share per Subsector - Aviation Freight = Plane", scenario),
                     get_metric(metrics_raw, "Load Factor - Freight Plane", scenario, 99999999)),
            pct(metrics_raw, "Share of Technology - Kerosene Freight Plane", scenario),
            get_metric(metrics_raw, "Final Energy Intensity - Kerosene Freight Plane", scenario))

    # === INTERNATIONAL BUNKERS (SIMPLIFIED) ===
    # 1. MARITIME
    if "Total Energy - Int. Maritime" in metrics_raw:
        val_twh = get_metric(metrics_raw, "Total Energy - Int. Maritime", scenario, 0.0)
        # CHANGE: Already in TWh, use directly
        if val_twh > 0:
            rows.append(["Transport", "International Transport", "International Navigation", "Bunkers", "Conventional", "Fuel Oil", scenario, val_twh])

    # 2. AVIATION
    if "Total Energy - Int. Aviation" in metrics_raw:
        val_twh = get_metric(metrics_raw, "Total Energy - Int. Aviation", scenario, 0.0)
        # CHANGE: Already in TWh, use directly
        if val_twh > 0:
            rows.append(["Transport", "International Transport", "International Aviation", "Bunkers", "Conventional", "Kerosene", scenario, val_twh])

    # === TOTAL ===
    total_twh = sum(r[-1] for r in rows)
    rows.append(["Transport", "TOTAL", "", "", "", "TOTAL", scenario, total_twh])

    # CHANGE: Renamed column to (TWh)
    return pd.DataFrame(rows, columns=[
        "Sector","Subsector","Mode","End-Use","Technology","Fuel","Scenario","Final Energy Demand (TWh)"])

# =============================================================================
# 5. ORCHESTRATION & SUMMARY
# =============================================================================

def find_latest_dir(base_dir="output_data") -> str:
    dirs = [
        d for d in glob.glob(os.path.join(base_dir, "DKS_*"))
        if os.path.isdir(d)
    ]
    if not dirs:
        raise FileNotFoundError(f"No DKS_* folders found in {base_dir}")
    return max(dirs, key=os.path.getmtime)

def list_countries(latest_dir: str):
    files = glob.glob(os.path.join(latest_dir, "output_*.xlsx"))
    return sorted([os.path.splitext(os.path.basename(f))[0].replace("output_", "") for f in files])

def find_country_file(country: str, latest_dir: str) -> str:
    path = os.path.join(latest_dir, f"output_{country}.xlsx")
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    return path

def load_country_dataframe(path: str) -> pd.DataFrame:
    df = pd.read_excel(path)
    df["Metric"] = df["Metric"].astype(str).str.replace("\xa0", " ").str.strip()
    numeric_cols = [c for c in df.columns if c not in ["Metric", "Units"]]
    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.drop_duplicates(subset=["Metric"], keep="first")

def dataframe_to_metrics_raw(df: pd.DataFrame) -> dict:
    return df.set_index("Metric").to_dict(orient="index")

def build_summary(df, metrics_raw):
    df = df[df["Fuel"].astype(str).str.strip() != ""]

    # 1. Group by Scenario names EXACTLY as they appear in the data
    fuel_summary = df.groupby(["Fuel", "Scenario"])["Final Energy Demand (TWh)"].sum().unstack(fill_value=0)
    mode_summary = df.groupby(["Mode", "Scenario"])["Final Energy Demand (TWh)"].sum().unstack(fill_value=0)
    subsector_summary = df.groupby(["Subsector", "Scenario"])["Final Energy Demand (TWh)"].sum().unstack(fill_value=0)
    enduse_summary = df.groupby(["End-Use", "Scenario"])["Final Energy Demand (TWh)"].sum().unstack(fill_value=0)

    # 2. Biofuel blending logic
    def share(metric_name, scn):
        d = metrics_raw.get(metric_name, {})
        val = float(d.get(scn, 0.0) or 0.0)
        return val / 100.0 if val > 1 else val

    for idx in ["Bio Ethanol", "Bio Diesel", "Bio Kerosene", "LPG"]:
        if idx not in fuel_summary.index: fuel_summary.loc[idx] = 0.0

    for scn in list(fuel_summary.columns):
        be = share("Share of Bioethanol in Road Gasoline", scn)
        bd = share("Share of Biodiesel in Road Diesel", scn)
        bk = share("Share of Biokerosene in Internal Aviation Fuel", scn)

        gas = fuel_summary.at["Gasoline", scn] if "Gasoline" in fuel_summary.index else 0.0
        die = fuel_summary.at["Diesel", scn]    if "Diesel" in fuel_summary.index    else 0.0
        ker = fuel_summary.at["Kerosene", scn] if "Kerosene" in fuel_summary.index else 0.0

        gas_bio = gas * be
        die_bio = die * bd
        ker_bio = ker * bk

        fuel_summary.at["Bio Ethanol", scn]  = gas_bio
        fuel_summary.at["Bio Diesel", scn]   = die_bio
        fuel_summary.at["Bio Kerosene", scn] = ker_bio

        if "Gasoline" in fuel_summary.index: fuel_summary.at["Gasoline", scn] = max(0.0, gas - gas_bio)
        if "Diesel" in fuel_summary.index:   fuel_summary.at["Diesel", scn]   = max(0.0, die - die_bio)
        if "Kerosene" in fuel_summary.index: fuel_summary.at["Kerosene", scn] = max(0.0, ker - ker_bio)

    # 3. Sorting (Dynamic)
    def scenario_sort_key(s):
        # Extracts year to sort chronologically, keeps suffix order flexible
        digits = "".join(filter(str.isdigit, str(s)))
        return int(digits) if digits else 9999

    fuel_summary = fuel_summary[sorted(fuel_summary.columns, key=scenario_sort_key)]

    fuels_order = ["Ammonia", "Bio Diesel", "Bio Ethanol", "Bio Kerosene", "Diesel", "E-Diesel", "E-Kerosene", 
                   "Electricity", "Fuel Oil", "Gasoline", "Hydrogen", "Kerosene", "LPG", "Methanol"]
    existing_fuels = [f for f in fuels_order if f in fuel_summary.index]
    fuel_summary = fuel_summary.reindex(existing_fuels)
    fuel_summary.loc["Sum"] = fuel_summary.sum(numeric_only=True, axis=0)

    return fuel_summary.round(4), mode_summary, subsector_summary, enduse_summary

def run(country: str, base_dir: str = "output_data") -> None:
    country_code = get_iso2_country_code(country)
    latest_dir = find_latest_dir(base_dir)
    print(f" Latest folder: {latest_dir}")

    available = list_countries(latest_dir)
    if country not in available:
        raise ValueError(f"{country} not found. Available: {', '.join(available)}")

    file_path = find_country_file(country, latest_dir)
    df = load_country_dataframe(file_path)

    metrics_raw = dataframe_to_metrics_raw(df)
    scenarios = [c for c in df.columns if c not in ["Metric", "Units"]]

    all_results = []
    for scn in scenarios:
        df_scn = calc_for_scenario(metrics_raw, scn)
        if df_scn is not None and not df_scn.empty:
            all_results.append(df_scn)

    if not all_results:
        raise ValueError(f"No valid scenarios produced for {country}")

    final_df = pd.concat(all_results, ignore_index=True)

    fuel_summary, mode_summary, subsector_summary, enduse_summary = build_summary(final_df, metrics_raw)

    country_results_dir = os.path.join(RESULTS_DIR, country)
    os.makedirs(country_results_dir, exist_ok=True)

    # 1. Save detailed Energy Demand (TWh)
    final_df.to_csv(
        os.path.join(country_results_dir, f"{country_code}_energy_demand.csv"),
        index=False)

    # 2. Generate Indicators (TWh)
    try:
        indicators_df = generate_transport_indicators(final_df, country)
        indicators_df.to_csv(
            os.path.join(country_results_dir, f"{country_code}_final_energy_demand.csv"),
            index=False
        )
    except Exception as e:
        print(f"  Warning: Could not generate indicators: {e}")

    # 3. Save Summaries (TWh)
    with pd.ExcelWriter(os.path.join(country_results_dir, f"{country_code}_summary.xlsx")) as writer:
        fuel_summary.to_excel(writer, sheet_name="Fuel")
        mode_summary.to_excel(writer, sheet_name="Mode")
        subsector_summary.to_excel(writer, sheet_name="Subsector")
        enduse_summary.to_excel(writer, sheet_name="EndUse")

    print(f" Saved results for {country} ({country_code})")


if __name__ == "__main__":
    for country in COUNTRY:
        try:
            print(f"\n{'='*50}\n Processing country: {country}\n{'='*50}")
            run(country=country, base_dir=TRANSPORT_OUTPUT_DIR)
        except Exception as e:
            print(f" Error processing {country}: {e}")