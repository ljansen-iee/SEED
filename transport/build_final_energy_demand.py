import os
import glob
import copy
import pandas as pd
import numpy as np
import pycountry
from pathlib import Path

# Import transport-specific functions
from transport.build_CAGR import expand_with_cagr, get_cagr
from transport.build_technology_share import get_unsd_bunker_fuel_shares
from transport.helpers import unsd_global_output, unsd_input_folder, load_transport_config, extract_config_data
from transport.build_transport_config import SCENARIOS

# =============================================================================
# 1. SETUP & CONFIGURATION
# =============================================================================

# Get the absolute path of this script and project root

script_dir = os.path.dirname(os.path.abspath(__file__))

# All transport outputs stay within transport/output_data
results_dir = os.path.join(script_dir, "output_data")
os.makedirs(results_dir, exist_ok=True)

choose_folder = "interim_parametrisation"

# Placeholder - will be loaded after countries is defined
transport_config_file = "trans_config.csv"
transport_config_path = Path(__file__).resolve().parent / transport_config_file
transport_config = {}


# List of countries to process

countries = ["Morocco","South Africa","Egypt","Namibia"]
    #"Republic of the Congo", "Egypt", "Ethiopia", "Ghana","Kenya","Namibia","Niger",
    #"Algeria","Argentina","Brazil","Chile","Colombia","Mexico","Peru","Venezuela",
    #"Morocco","Tunisia","Tanzania", "South Africa","Libya",
    #"Australia", "Canada", "China", "France", "Germany",  
    #"India", "Indonesia", "Italy", "Japan", "Russia", "Saudi Arabia",
   # "South Korea", "United Kingdom", "United States of America"]

# NOW load transport config after countries is defined
try:
    countries_to_load = countries + ["default"]
    transport_config = load_transport_config(
        excel_path=transport_config_path,
        countries=countries_to_load,
        scenarios=list(SCENARIOS)
    )
except Exception as e:
    print(f" Warning: Could not load transport config: {e}")
    import traceback
    traceback.print_exc()
    transport_config = {}


def get_iso2_country_code(c):
    try:
        match = pycountry.countries.search_fuzzy(c)[0]
        return match.alpha_2  
    except (LookupError, AttributeError):
        # Fallback for very specific naming mismatches if pycountry fails
        print(f"Warning: Could not find ISO code for '{c}'. Using fallback.")
        return c[:2].upper()

# =============================================================================
# 2. INDICATOR GENERATION FUNCTION (ALL TWh)
# =============================================================================

def generate_transport_indicators(final_df: pd.DataFrame, country: str, metrics_raw: dict = None) -> pd.DataFrame:
    df = final_df.copy()
    metrics_raw = metrics_raw or {}
    df["Scenario"] = df["Scenario"].astype(str).str.strip()

    normalized_metrics_raw = {}
    for metric_name, metric_values in metrics_raw.items():
        normalized_name = str(metric_name).strip()
        if isinstance(metric_values, dict):
            normalized_metrics_raw[normalized_name] = {
                str(key).strip(): value for key, value in metric_values.items()
            }
        else:
            normalized_metrics_raw[normalized_name] = metric_values
    metrics_raw = normalized_metrics_raw
    unit_col = "Final Energy Demand (GWh)"
    df[unit_col] = pd.to_numeric(df[unit_col], errors="coerce").fillna(0)
    scenario_index = pd.Index(df["Scenario"].unique(), name="scenario")
    gwh_to_twh = 1.0 / 1000.0

    def sum_filter(subsector=None, mode=None, enduse=None, fuels=None):
        d = df
        if subsector:
            d = d[d["Subsector"].isin(subsector if isinstance(subsector, list) else [subsector])]
        if mode:
            d = d[d["Mode"].isin(mode if isinstance(mode, list) else [mode])]
        if enduse:
            d = d[d["End-Use"].isin(enduse if isinstance(enduse, list) else [enduse])]
        if fuels:
            d = d[d["Fuel"].isin(fuels if isinstance(fuels, list) else [fuels])]
        return d.groupby("Scenario")[unit_col].sum().reindex(scenario_index, fill_value=0.0) * gwh_to_twh

    def get_share_series(metric_name):
        metric_values = metrics_raw.get(metric_name, {})
        values = []
        for scenario in scenario_index:
            scenario_key = str(scenario).strip()
            raw_val = metric_values.get(scenario_key, 0.0)
            try:
                share = float(raw_val)
            except Exception:
                share = 0.0
            if share > 1:
                share = share / 100.0
            values.append(min(1.0, max(0.0, share)))
        return pd.Series(values, index=scenario_index, dtype=float)

    road_enduses = ["LDV", "Bus", "2&3 Wheelers", "Light-Duty Trucks", "Heavy-Duty Trucks"]
    rail_enduses = ["Passenger Train", "Freight Train"]
    aviation_passenger_enduses = ["Passenger Planes"]
    navigation_freight_enduses = ["Freight Ships"]

    road_oil_fuels = ["Gasoline", "Synthetic Gasoline", "Diesel", "Synthetic Diesel", "LPG", "E-Diesel"]
    rail_oil_fuels = ["Diesel", "Synthetic Diesel", "E-Diesel", "Fuel Oil", "LPG"]
    aviation_oil_fuels = ["Kerosene", "Synthetic Kerosene", "E-Kerosene", "Fuel Oil"]
    navigation_oil_fuels = ["Diesel", "Methanol"]
    share_bioethanol_road = get_share_series("Share of Bioethanol in Road Gasoline")
    share_biodiesel_road = get_share_series("Share of Biodiesel in Road Diesel")
    share_biokerosene_aviation = get_share_series("Share of Biokerosene in Internal Aviation Fuel")
    share_biodiesel_navigation = get_share_series("Share of Biodiesel in Internal Navigation Diesel")

    result = pd.DataFrame(index=scenario_index)
    result["country"] = country

    rail_electricity = sum_filter(enduse=rail_enduses, fuels=["Electricity"])
    rail_hydrogen = sum_filter(enduse=rail_enduses, fuels=["Hydrogen"])
    rail_oil = sum_filter(enduse=rail_enduses, fuels=rail_oil_fuels)
    result["electricity rail"] = rail_electricity
    result["total rail"] = rail_oil + rail_electricity + rail_hydrogen
    result["total rail hydrogen"] = rail_hydrogen

    road_total = sum_filter(enduse=road_enduses)
    road_electricity = sum_filter(enduse=road_enduses, fuels=["Electricity"])
    road_hydrogen = sum_filter(enduse=road_enduses, fuels=["Hydrogen"])
    road_gas = sum_filter(enduse=road_enduses, fuels=["LPG"])
    road_oil = sum_filter(enduse=road_enduses, fuels=road_oil_fuels)
    road_biomass = sum_filter(enduse=road_enduses, fuels=["Bio Diesel", "Bio Ethanol"])

    result["road biomass"] = road_biomass
    result["road electricity"] = road_electricity
    result["road gas"] = road_gas
    result["road oil"] = road_oil
    result["total road"] = road_oil + road_biomass + road_electricity + road_hydrogen + road_gas
    result["total road ev"] = road_electricity
    result["total road fcev"] = road_hydrogen
    result["total road ice"] = road_oil + road_biomass

    aviation_oil_gross = sum_filter(enduse=aviation_passenger_enduses, fuels=aviation_oil_fuels)
    aviation_electricity = sum_filter(enduse=aviation_passenger_enduses, fuels=["Electricity"])
    aviation_hydrogen = sum_filter(enduse=aviation_passenger_enduses, fuels=["Hydrogen"])
    aviation_kerosene = sum_filter(enduse=aviation_passenger_enduses, fuels=["Kerosene"])
    aviation_bio_kerosene = aviation_kerosene * share_biokerosene_aviation
    aviation_biomass_explicit = sum_filter(enduse=aviation_passenger_enduses, fuels=["Bio Kerosene"])
    aviation_biomass = aviation_biomass_explicit + aviation_bio_kerosene
    aviation_oil = (aviation_oil_gross - aviation_bio_kerosene).clip(lower=0.0)
    result["total domestic aviation"] = aviation_oil + aviation_electricity + aviation_hydrogen + aviation_biomass
    result["total aviation biomass"] = aviation_biomass

    navigation_oil_gross = sum_filter(enduse=navigation_freight_enduses, fuels=navigation_oil_fuels)
    navigation_electricity = sum_filter(enduse=navigation_freight_enduses, fuels=["Electricity"])
    navigation_hydrogen = sum_filter(enduse=navigation_freight_enduses, fuels=["Hydrogen"])
    navigation_ammonia = sum_filter(enduse=navigation_freight_enduses, fuels=["Ammonia"])
    navigation_diesel = sum_filter(enduse=navigation_freight_enduses, fuels=["Diesel"])
    navigation_bio_diesel = navigation_diesel * share_biodiesel_navigation
    navigation_biomass_explicit = sum_filter(enduse=navigation_freight_enduses, fuels=["Bio Diesel"])
    navigation_biomass = navigation_biomass_explicit + navigation_bio_diesel
    navigation_oil = (navigation_oil_gross - navigation_bio_diesel).clip(lower=0.0)

    result["total domestic navigation"] = navigation_oil + navigation_electricity + navigation_hydrogen + navigation_ammonia + navigation_biomass
    result["total navigation hydrogen"] = navigation_hydrogen
    result["total navigation oil"] = navigation_oil
    result["total navigation ammonia"] = navigation_ammonia
    result["total navigation biomass"] = navigation_biomass

    result["total international aviation"] = np.nan
    result["total international navigation"] = np.nan

    ordered_columns = [
        "country",
        "electricity rail",
        "total rail",
        "total rail hydrogen",
        "road biomass",
        "road electricity",
        "road gas",
        "road oil",
        "total road",
        "total road ev",
        "total road fcev",
        "total road ice",
        "total domestic aviation",
        "total domestic navigation",
        "total navigation hydrogen",
        "total navigation oil",
        "total navigation ammonia",
        "total navigation biomass",
        "total aviation biomass",
        "total international aviation",
        "total international navigation",
    ]

    return result[ordered_columns].reset_index()


# =============================================================================
# 3. HELPER FUNCTIONS
# =============================================================================

# === Dynamic Scenario Mapping Function ===
def get_config_scenario_name(scenario_from_column):
    
    try:
        idx = SCENARIOS.index(scenario_from_column)
        # Map index to sc_a, sc_b, sc_c, sc_d, ... (assuming alphabetic pattern)
        config_scenario = f"sc_{chr(ord('a') + idx)}"
        return config_scenario
    except (ValueError, IndexError):
        # Fallback if scenario not found in SCENARIOS list
        return "all"


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
    if d in (None, 0):
        return n  
    return n / d




def add_row(rows, sector, subsector, mode, enduse, tech, fuel, scn, vkm, tech_share, inten, fuel_split=1.0):
    """
    Calculates Energy Demand and appends to rows.
    Current conversion: kWh -> GWh (1e6)
    To change to TWh later, simply change 1e6 to 1e9.
    """
    # Formula: Distance * % Tech * Energy Intensity * % Fuel split
    fed_kwh = vkm * tech_share * inten * fuel_split
    #  UNIT CONVERSION: kWh to GWh
    fed_unit = fed_kwh / 1e6
    rows.append([sector, subsector, mode, enduse, tech, fuel, scn, fed_unit])



def apply_cagr_projections(df, config_path, country, base_year="2020"):
    """
    Chain-linked CAGR calculation:
    - 2030 is projected from 2020
    - 2035 is projected from 2030
    - 2040 is projected from 2035, and so on.
    """
    try:
        config_df = pd.read_csv(config_path)
        config_df['Scenario'] = config_df['Scenario'].astype(str)

        # Separate CAGR and Value rows
        cagr_config = config_df[config_df['Assumption Type'].str.upper() == 'CAGR']
        value_config = config_df[config_df['Assumption Type'].str.upper() == 'VALUE']
    except Exception as e:
        print(f"  Warning: Error loading CAGR config: {e}")
        return df



    # 1. Identify and sort milestone years present in the dataeline', etc.
    all_cols = [c for c in df.columns if c not in ["Metric", "Units"]]

    def extract_year(column_name):
        digits = "".join(filter(str.isdigit, column_name))
        return int(digits) if digits else None

    # Get a sorted listframe columns
    # We extract digits to identify years like '2020', '2030_Bas of unique numeric years: [2020, 2030, 2035, 2040, 2045, 2050]
    unique_years = sorted(list(set(extract_year(c) for c in all_cols if extract_year(c) is not None)))
    if len(unique_years) < 2:
        return df
    # --- Apply VALUE overrides before chaining CAGRs ---
    def resolve_target_scenarios(scen_value):
        scen_lower = str(scen_value).lower()
        if scen_value in SCENARIOS:
            return [scen_value]
        if scen_lower == 'all':
            return list(SCENARIOS)
        # handle aliases sc_a/sc_b/sc_c
        if scen_lower.startswith('sc_') and len(scen_lower) == 4:
            idx = ord(scen_lower[-1]) - ord('a')
            if 0 <= idx < len(SCENARIOS):
                return [SCENARIOS[idx]]
        return []

    override_cells = set()
    for _, row in value_config.iterrows():
        metric = str(row.get('Metric Name', '')).strip()
        try:
            year_val = int(row.get('Year'))
        except Exception:
            continue
        target_scenarios = resolve_target_scenarios(row.get('Scenario', ''))
        if not target_scenarios:
            continue

        # pick country value, else default
        country_val = row.get(country, np.nan)
        val = country_val if pd.notna(country_val) and str(country_val) != '' else row.get('default', np.nan)
        if pd.isna(val) or str(val) == '':
            continue
        try:
            val = float(val)
        except Exception:
            continue

        for scen in target_scenarios:
            # Base year columns in the source file are stored without scenario suffix
            if year_val == int(base_year):
                col_name = str(year_val)
            else:
                col_name = f"{year_val}_{scen}"

            if col_name not in df.columns:
                df[col_name] = np.nan
            df.loc[df['Metric'] == metric, col_name] = val
            override_cells.add((metric, col_name))

    # 2. Iterate through the intervals (e.g., 2020-2030, 2030-2035, 2035-2040)
    for i in range(1, len(unique_years)):
        prev_yr_num = unique_years[i-1]
        curr_yr_num = unique_years[i]
        interval_length = curr_yr_num - prev_yr_num
        # Get all columns belonging to the current target year (e.g., all 2035 scenarios)
        curr_year_cols = [c for c in all_cols if extract_year(c) == curr_yr_num]

        for index, row in df.iterrows():
            metric = str(row['Metric']).strip()
            for col in curr_year_cols:
                # Identify the scenario from column name (e.g., "2030_BAU" → "BAU")
                scenario_from_col = None
                for scn_name in SCENARIOS:
                    if scn_name in col:
                        scenario_from_col = scn_name
                        break

                # Build a set of possible labels to match against the config (handles BAU/Progressive/Optimistic or sc_a/sc_b/sc_c/all)
                scenario_candidates = []
                if scenario_from_col:
                    scenario_candidates.append(scenario_from_col)
                    scenario_candidates.append(scenario_from_col.lower())
                    scenario_alias = get_config_scenario_name(scenario_from_col)
                    if scenario_alias:
                        scenario_candidates.append(scenario_alias)
                scenario_candidates.append("all")
                scenario_candidates_lower = {str(s).lower() for s in scenario_candidates if s}

                # Find the specific CAGR for this Metric, Year, and Scenario
                match = cagr_config[
                    (cagr_config['Metric Name'] == metric) &
                    (cagr_config['Year'] == curr_yr_num) &
                    (cagr_config['Scenario'].str.lower().isin(scenario_candidates_lower))
                ]

                if match.empty:
                    # Fallback to any scenario for that metric/year
                    match = cagr_config[
                        (cagr_config['Metric Name'] == metric) &
                        (cagr_config['Year'] == curr_yr_num)
                    ]
                if not match.empty:
                    # Get country value or default
                    cagr_val = match.iloc[0].get(country)
                    if pd.isna(cagr_val) or cagr_val == "":
                        cagr_val = match.iloc[0].get('default')

                    if not pd.isna(cagr_val):
                        cagr = float(cagr_val)

                        # Skip if this cell was explicitly overridden by a Value row
                        if (metric, col) in override_cells:
                            continue

                        # Find the corresponding base value from the PREVIOUS milestone
                        # We look for a column with the same scenario suffix in the previous year
                        # e.g., if col is '2035_EL', we look for '2030_EL' or '2020'
                        suffix = col.split("_", 1)[1] if "_" in col else ""
                        prev_col_name = f"{prev_yr_num}_{suffix}" if suffix else str(prev_yr_num)

                        # Fallback if specific scenario didn't exist in prev year (use raw year)
                        if prev_col_name not in df.columns:
                            prev_col_name = str(prev_yr_num)

                        if prev_col_name in df.columns:
                            base_val = float(df.at[index, prev_col_name])
                            # CHAINED CALCULATION: New Value = Prev_Value * (1 + CAGR)^interval
                            new_val = base_val * ((1 + cagr) ** interval_length)
                            # ADD THIS SAFETY CAP:
                            if "Share" in metric:
                                # Stop it from exceeding 100 or dropping below 0
                                new_val = min(100.0, max(0.0, new_val))

                            df.at[index, col] = new_val
        
    return df

def calculate_remainders(df):
    """
    Ensures that transport shares always sum to 100% by calculating 
    the remainder for 'Road' and 'LDV' metrics.
    """
    # Identify the year/scenario columns
    all_cols = [c for c in df.columns if c not in ["Metric", "Units"]]
    
    # Define which metrics are 'drivers' and which one is the 'remainder'
    remainder_logic = {
        "Share per Subsector - Road Passenger": [
            "Share per Subsector - Rail Passenger = Train", 
            "Share per Subsector - Aviation Passenger = Plane"
        ],
        "Share per Subsector - Road Freight": [
            "Share per Subsector - Rail Freight = Train", 
            "Share per Subsector - Navigation Freight = Ship", 
            "Share per Subsector - Aviation Freight = Plane"
        ],
        "Share per Mode - LDV": [
            "Share per Mode - Bus", 
            "Share per Mode - 2&3W"
        ],
        "Share per Mode - LDT": [
            "Share per Mode - HDT"
        ]
    }

    for col in all_cols:
        for remainder_metric, drivers in remainder_logic.items():
            # Sum up the drivers for the current column
            driver_sum = df[df["Metric"].isin(drivers)][col].sum()
            
            # Calculate the remainder (100 - drivers)
            # Use max(0, ...) to prevent negative shares if drivers > 100
            remainder_val = max(0, 100.0 - driver_sum)
            
            # Update the remainder row in the dataframe
            df.loc[df["Metric"] == remainder_metric, col] = remainder_val
            
    return df

# =============================================================================
# 4. MAIN CALCULATION LOGIC (TWh)
# =============================================================================


def calc_for_scenario(metrics_raw: dict, scenario: str) -> pd.DataFrame:

    rows = []
    # ── 1. Get core activity levels ─────────────────────────────────────────
    pop_million = get_metric(metrics_raw, "Population", scenario, 0.0)
    population = pop_million * 1_000_000
    pkm_per_capita = get_metric(metrics_raw, "Mobility per capita - Passenger", scenario, 0.0)
    tkm_per_capita = get_metric(metrics_raw, "Mobility per capita - Freight", scenario, 0.0)

    total_pkm = population * pkm_per_capita
    total_tkm = population * tkm_per_capita



    # ── 2. Passenger subsector split (in pkm) ────────────────────────────────
    road_pass_pkm   = total_pkm * pct(metrics_raw, "Share per Subsector - Road Passenger", scenario)
    rail_pass_pkm   = total_pkm * pct(metrics_raw, "Share per Subsector - Rail Passenger = Train", scenario)
    aviation_pass_pkm = total_pkm * pct(metrics_raw, "Share per Subsector - Aviation Passenger = Plane", scenario)



    # ── 3. Passenger road mode split (pkm → vkm) ─────────────────────────────
    share_ldv   = pct(metrics_raw, "Share per Mode - LDV", scenario)
    share_bus   = pct(metrics_raw, "Share per Mode - Bus", scenario)
    share_23w   = pct(metrics_raw, "Share per Mode - 2&3W", scenario)

    pkm_ldv   = road_pass_pkm * share_ldv
    pkm_bus   = road_pass_pkm * share_bus
    pkm_23w   = road_pass_pkm * share_23w

    vkm_ldv   = safe_div(pkm_ldv,   get_metric(metrics_raw, "Load Factor - LDV", scenario, 1.0))
    vkm_bus   = safe_div(pkm_bus,   get_metric(metrics_raw, "Load Factor - Bus", scenario, 1.0))
    vkm_23w   = safe_div(pkm_23w,   get_metric(metrics_raw, "Load Factor - 2&3W", scenario, 1.0))


    # Rail passenger – special handling if load factor = 0
    lf_pass_train = get_metric(metrics_raw, "Load Factor - Passenger Train", scenario, 0)
    if lf_pass_train <= 0:
        vkm_pass_train = 0   # no activity
    else:

        vkm_pass_train = rail_pass_pkm / lf_pass_train



    vkm_pass_plane = safe_div(
    aviation_pass_pkm,
    get_metric(metrics_raw, "Load Factor - Passenger Plane", scenario, 1.0)
    )



    # ── 4. Freight subsector split (tkm → vkm) ───────────────────────────────
    road_frt_tkm   = total_tkm * pct(metrics_raw, "Share per Subsector - Road Freight", scenario)
    rail_frt_tkm   = total_tkm * pct(metrics_raw, "Share per Subsector - Rail Freight = Train", scenario)
    nav_frt_tkm    = total_tkm * pct(metrics_raw, "Share per Subsector - Navigation Freight = Ship", scenario)
    aviation_frt_tkm = total_tkm * pct(metrics_raw, "Share per Subsector - Aviation Freight = Plane", scenario)

    share_ldt = pct(metrics_raw, "Share per Mode - LDT", scenario)
    share_hdt = pct(metrics_raw, "Share per Mode - HDT", scenario)

    tkm_ldt = road_frt_tkm * share_ldt
    tkm_hdt = road_frt_tkm * share_hdt

    vkm_ldt = safe_div(tkm_ldt, get_metric(metrics_raw, "Load Factor - LDT", scenario, 1.0))
    vkm_hdt = safe_div(tkm_hdt, get_metric(metrics_raw, "Load Factor - HDT", scenario, 1.0))
    vkm_fr_train = safe_div(rail_frt_tkm, get_metric(metrics_raw, "Load Factor - Freight Train", scenario, 1.0))
    vkm_fr_ship  = safe_div(nav_frt_tkm,  get_metric(metrics_raw, "Load Factor - Freight Ship", scenario, 1.0))
    vkm_fr_plane = safe_div(aviation_frt_tkm, get_metric(metrics_raw, "Load Factor - Freight Plane", scenario, 1.0))



    # ── Helper to add energy demand row (all in GWh) ─────────────────────────
    def add_energy_row(sector, subsector, mode, enduse, tech, fuel, vkm, tech_share_pct, intensity_kwh_per_vkm):
        if vkm <= 0 or tech_share_pct <= 0 or intensity_kwh_per_vkm <= 0:
            return

        energy_kwh = vkm * (tech_share_pct / 100.0) * intensity_kwh_per_vkm
        energy_gwh = energy_kwh / 1_000_000
        rows.append([sector, subsector, mode, enduse, tech, fuel, scenario, energy_gwh])



    # ── 5. Passenger – Road LDV ──────────────────────────────────────────────
    ldv_techs = [
        ("Gasoline ICE", "Gasoline"),
        ("Diesel ICE", "Diesel"),
        ("LPG ICE", "LPG"),
        ("BEV", "Electricity"),
        ("FCEV", "Hydrogen"),
        ("Gasoline Plugin Hybrid", "Gasoline"),
        ("Diesel Plugin Hybrid", "Diesel"),
    ]



    ice_share_in_phev = pct(metrics_raw, "Share of ICE Fuel in Plugin Hybrid", scenario)
    for tech, fuel in ldv_techs:
        tech_share = pct(metrics_raw, f"Share of Technology - {tech} LDV", scenario)
        intensity = get_metric(metrics_raw, f"Final Energy Intensity - {tech} LDV", scenario, 0.0)

        # NEW LOGIC: Check if it's a Hybrid to split the fuel
        if "Plugin Hybrid" in tech:
            # 1. Fuel part (Gasoline/Diesel)
            add_energy_row(
                "Transport", "Passenger", "Road", "LDV", tech, fuel,
                vkm_ldv, tech_share * 100, intensity * ice_share_in_phev
            )
            # 2. Electricity part
            add_energy_row(
                "Transport", "Passenger", "Road", "LDV", tech, "Electricity",
                vkm_ldv, tech_share * 100, intensity * (1 - ice_share_in_phev)
            )

        else:
            # Regular cars (ICE or 100% Electric) use the old logic
            add_energy_row(
                "Transport", "Passenger", "Road", "LDV", tech, fuel,
                vkm_ldv, tech_share * 100, intensity
            )



    # ── Passenger – Bus, 2&3W, Rail, Aviation, Navigation ────────────────────

    # Bus
    for tech, fuel in [("Diesel ICE", "Diesel"), ("BEV", "Electricity"), ("FCEV", "Hydrogen")]:
        add_energy_row("Transport", "Passenger", "Road", "Bus", tech, fuel, vkm_bus,
                       pct(metrics_raw, f"Share of Technology - {tech} Bus", scenario) * 100,
                       get_metric(metrics_raw, f"Final Energy Intensity - {tech} Bus", scenario, 0))



    # 2&3 Wheelers
    for tech, fuel in [("Gasoline ICE", "Gasoline"), ("BEV", "Electricity")]:
        add_energy_row("Transport", "Passenger", "Road", "2&3 Wheelers", tech, fuel, vkm_23w,
                       pct(metrics_raw, f"Share of Technology - {tech} 2&3W", scenario) * 100,
                       get_metric(metrics_raw, f"Final Energy Intensity - {tech} 2&3W", scenario, 0))



    # Rail passenger
    for tech, fuel in [("Diesel ICE", "Diesel"), ("Direct Electric", "Electricity"), ("FCEV", "Hydrogen")]:
        add_energy_row("Transport", "Passenger", "Rail", "Passenger Train", tech, fuel, vkm_pass_train,
                       pct(metrics_raw, f"Share of Technology - {tech} Passenger Train", scenario) * 100,
                       get_metric(metrics_raw, f"Final Energy Intensity - {tech} Passenger Train", scenario, 0))



    # Aviation passenger
    for tech, fuel in [("Kerosene", "Kerosene"), ("BEV", "Electricity"), ("FCEV", "Hydrogen")]:
        add_energy_row("Transport", "Passenger", "Aviation", "Passenger Planes", tech, fuel, vkm_pass_plane,
                       pct(metrics_raw, f"Share of Technology - {tech} Passenger Plane", scenario) * 100,
                       get_metric(metrics_raw, f"Final Energy Intensity - {tech} Passenger Plane", scenario, 0))



    # ── 6. Freight ───────────────────────────────────────────────────────────
    # Light-Duty Trucks
    for tech, fuel in [("Diesel ICE", "Diesel"), ("BEV", "Electricity"), ("FCEV", "Hydrogen")]:
        add_energy_row("Transport", "Freight", "Road", "Light-Duty Trucks", tech, fuel, vkm_ldt,
                       pct(metrics_raw, f"Share of Technology - {tech} LDT", scenario) * 100,
                       get_metric(metrics_raw, f"Final Energy Intensity - {tech} LDT", scenario, 0))



    # Heavy-Duty Trucks
    for tech, fuel in [("Diesel ICE", "Diesel"), ("BEV", "Electricity"), ("FCEV", "Hydrogen")]:
        add_energy_row("Transport", "Freight", "Road", "Heavy-Duty Trucks", tech, fuel, vkm_hdt,
                       pct(metrics_raw, f"Share of Technology - {tech} HDT", scenario) * 100,
                       get_metric(metrics_raw, f"Final Energy Intensity - {tech} HDT", scenario, 0))



    # Freight Rail
    for tech, fuel in [("Diesel ICE", "Diesel"), ("Direct Electric", "Electricity"), ("FCEV", "Hydrogen")]:
        tech_share_key = f"Share of Technology - {tech} Freight Train"
        # Ensure this pulls the exact 42.23 or 57.77 from your dict
        share = pct(metrics_raw, tech_share_key, scenario)
        add_energy_row("Transport", "Freight", "Rail", "Freight Train", tech, fuel, vkm_fr_train,
                    share * 100,
                    get_metric(metrics_raw, f"Final Energy Intensity - {tech} Freight Train", scenario, 0))



    # Freight Navigation
    for tech, fuel in [("Diesel ICE", "Diesel"), ("Methanol", "Methanol"), ("Ammonia", "Ammonia"),
                       ("BEV", "Electricity"), ("FCEV", "Hydrogen")]:

       

        # FIX: The Excel metric name for ships is "Diesel", not "Diesel ICE"
        intensity_tech = tech.replace(" ICE", "") if tech == "Diesel ICE" else tech

        add_energy_row(
            "Transport", "Freight", "Navigation", "Freight Ships", tech, fuel, vkm_fr_ship,
            pct(metrics_raw, f"Share of Technology - {tech} Freight Ship", scenario) * 100,
            get_metric(metrics_raw, f"Final Energy Intensity - {intensity_tech} Freight Ship", scenario, 0)
        )



    # Freight Aviation (kerosene only for now)
    add_energy_row("Transport", "Freight", "Aviation", "Freight Planes", "Kerosene", "Kerosene", vkm_fr_plane,
                   pct(metrics_raw, "Share of Technology - Kerosene Freight Plane", scenario) * 100,
                   get_metric(metrics_raw, "Final Energy Intensity - Kerosene Freight Plane", scenario, 0))



    # ── 7. International bunkers (REMOVED to match Excel Summary) ──────────
    # Note: Excel excludes these from the main transport fuel summary table.
    # If you need them later for a separate report, keep the variables but don't append to 'rows'.
    # int_maritime_twh = get_metric(metrics_raw, "Final Energy - Int. Maritime", scenario, 0.0)
    # int_aviation_twh = get_metric(metrics_raw, "Final Energy - Int. Aviation", scenario, 0.0)

    # ── 8. Add total row ─────────────────────────────────────────────────────
    # This sum now only includes the domestic transport rows calculated in steps 1-6
    total_gwh = sum(row[-1] for row in rows)
    rows.append(["Transport", "TOTAL", "", "", "", "TOTAL", scenario, total_gwh])

    # ── Return DataFrame ─────────────────────────────────────────────────────
    columns = ["Sector", "Subsector", "Mode", "End-Use", "Technology", "Fuel", "Scenario", "Final Energy Demand (GWh)"]
    df = pd.DataFrame(rows, columns=columns)

    return df

# =============================================================================
# 5. SUMMARY
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
    files = glob.glob(os.path.join(latest_dir, "output_*.csv"))
    return sorted([os.path.splitext(os.path.basename(f))[0].replace("output_", "") for f in files])

def find_country_file(country: str, latest_dir: str) -> str:
    path = os.path.join(latest_dir, f"output_{country}.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    return path

def load_country_dataframe(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["Metric"] = df["Metric"].astype(str).str.replace("\xa0", " ").str.strip()
    numeric_cols = [c for c in df.columns if c not in ["Metric", "Units"]]
    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.drop_duplicates(subset=["Metric"], keep="first")

def dataframe_to_metrics_raw(df: pd.DataFrame) -> dict:
    return df.set_index("Metric").to_dict(orient="index")

def build_summary(df, metrics_raw):
    # Filter out rows with empty values for each grouping column
    df_fuel = df[df["Fuel"].astype(str).str.strip() != ""]
    df_mode = df[df["Mode"].astype(str).str.strip() != ""]
    df_subsector = df[df["Subsector"].astype(str).str.strip() != ""]
    df_enduse = df[df["End-Use"].astype(str).str.strip() != ""]

    # 1. Group by Scenario names EXACTLY as they appear in the data
    fuel_summary = df_fuel.groupby(["Fuel", "Scenario"])["Final Energy Demand (GWh)"].sum().unstack(fill_value=0)
    mode_summary = df_mode.groupby(["Mode", "Scenario"])["Final Energy Demand (GWh)"].sum().unstack(fill_value=0)
    subsector_summary = df_subsector.groupby(["Subsector", "Scenario"])["Final Energy Demand (GWh)"].sum().unstack(fill_value=0)
    enduse_summary = df_enduse.groupby(["End-Use", "Scenario"])["Final Energy Demand (GWh)"].sum().unstack(fill_value=0)

    # 2. Biofuel blending logic
    def share(metric_name, scn):
        d = metrics_raw.get(metric_name, {})
        val = float(d.get(scn, 0.0) or 0.0)
        return val / 100.0 if val > 1 else val

    for idx in ["Bio Ethanol", "Bio Diesel", "Bio Kerosene", "LPG"]:
        if idx not in fuel_summary.index: fuel_summary.loc[idx] = 0.0

    for scn in list(fuel_summary.columns):
        be = share("Share of Bioethanol in Road Gasoline", scn)
        bd_road = share("Share of Biodiesel in Road Diesel", scn)
        bd_rail = share("Share of Biodiesel in Rail Diesel", scn)
        bd_nav = share("Share of Biodiesel in Internal Navigation Diesel", scn)
        bk = share("Share of Biokerosene in Internal Aviation Fuel", scn)

        gas = fuel_summary.at["Gasoline", scn] if "Gasoline" in fuel_summary.index else 0.0
        die = fuel_summary.at["Diesel", scn]    if "Diesel" in fuel_summary.index    else 0.0
        ker = fuel_summary.at["Kerosene", scn] if "Kerosene" in fuel_summary.index else 0.0

        scn_df = df[df["Scenario"] == scn]

        road_gas = scn_df[
            (scn_df["Mode"] == "Road") & (scn_df["Fuel"] == "Gasoline")
        ]["Final Energy Demand (GWh)"].sum()

        road_die = scn_df[
            (scn_df["Mode"] == "Road") & (scn_df["Fuel"] == "Diesel")
        ]["Final Energy Demand (GWh)"].sum()
        rail_die = scn_df[
            (scn_df["Mode"] == "Rail") & (scn_df["Fuel"] == "Diesel")
        ]["Final Energy Demand (GWh)"].sum()
        nav_die = scn_df[
            (scn_df["Mode"] == "Navigation") & (scn_df["Fuel"] == "Diesel")
        ]["Final Energy Demand (GWh)"].sum()

        aviation_ker = scn_df[
            (scn_df["Mode"] == "Aviation") & (scn_df["Fuel"] == "Kerosene")
        ]["Final Energy Demand (GWh)"].sum()

        gas_bio = road_gas * be
        die_bio = (road_die * bd_road) + (rail_die * bd_rail) + (nav_die * bd_nav)
        ker_bio = aviation_ker * bk

        gas_bio = min(gas, gas_bio)
        die_bio = min(die, die_bio)
        ker_bio = min(ker, ker_bio)

        fuel_summary.at["Bio Ethanol", scn]  = gas_bio
        fuel_summary.at["Bio Diesel", scn]   = die_bio
        fuel_summary.at["Bio Kerosene", scn] = ker_bio

        if "Gasoline" in fuel_summary.index: fuel_summary.at["Gasoline", scn] = max(0.0, gas - gas_bio)
        if "Diesel" in fuel_summary.index:   fuel_summary.at["Diesel", scn]   = max(0.0, die - die_bio)
        if "Kerosene" in fuel_summary.index: fuel_summary.at["Kerosene", scn] = max(0.0, ker - ker_bio)

    # 3. Sorting (Dynamic)
    def scenario_sort_key(s):
        # Extract year and scenario name to sort chronologically with consistent scenario order
        digits = "".join(filter(str.isdigit, str(s)))
        year = int(digits) if digits else 9999
        
        # Determine scenario order (BAU=0, Progressive=1, Optimistic=2)
        scenario_order = 999
        for scenario_name in SCENARIOS:
            if scenario_name in str(s):
                scenario_order = SCENARIOS.index(scenario_name)
                break
        
        return (year, scenario_order)

    # Sort columns by year for all summaries
    fuel_summary = fuel_summary[sorted(fuel_summary.columns, key=scenario_sort_key)]
    mode_summary = mode_summary[sorted(mode_summary.columns, key=scenario_sort_key)]
    subsector_summary = subsector_summary[sorted(subsector_summary.columns, key=scenario_sort_key)]
    enduse_summary = enduse_summary[sorted(enduse_summary.columns, key=scenario_sort_key)]
    
    # Remove any existing TOTAL/Sum/Total rows before processing
    total_labels = ["TOTAL", "Total", "Sum", "sum", "total"]
    fuel_summary = fuel_summary[~fuel_summary.index.isin(total_labels)]
    mode_summary = mode_summary[~mode_summary.index.isin(total_labels)]
    subsector_summary = subsector_summary[~subsector_summary.index.isin(total_labels)]
    enduse_summary = enduse_summary[~enduse_summary.index.isin(total_labels)]
    
    # Define row order for fuel summary
    fuels_order = ["Ammonia", "Bio Diesel", "Bio Ethanol", "Bio Kerosene", "Diesel", "E-Diesel", "E-Kerosene",
                   "Electricity", "Fuel Oil", "Gasoline", "Hydrogen", "Kerosene", "LPG", "Methanol"]
    existing_fuels = [f for f in fuels_order if f in fuel_summary.index]
    fuel_summary = fuel_summary.reindex(existing_fuels)
    
    # Sort rows alphabetically for other summaries
    mode_summary = mode_summary.sort_index()
    subsector_summary = subsector_summary.sort_index()
    enduse_summary = enduse_summary.sort_index()
    
    # Add "TOTAL" row at the BOTTOM of each summary (consistent naming)
    fuel_summary.loc["TOTAL"] = fuel_summary.sum(numeric_only=True, axis=0)
    mode_summary.loc["TOTAL"] = mode_summary.sum(numeric_only=True, axis=0)
    subsector_summary.loc["TOTAL"] = subsector_summary.sum(numeric_only=True, axis=0)
    enduse_summary.loc["TOTAL"] = enduse_summary.sum(numeric_only=True, axis=0)
    
    return fuel_summary.round(4), mode_summary.round(4), subsector_summary.round(4), enduse_summary.round(4)


def parse_scenario_name(scenario_str):
    parts = str(scenario_str).split('_')
    year = int(parts[0]) if parts and parts[0].isdigit() else None
    scenario = '_'.join(parts[1:]) if len(parts) > 1 else None
    return year, scenario


def get_country_bunker_series(country: str, scenario_labels, transport_cfg: dict):
    empty = {'maritime': {}, 'aviation': {}}
    if not transport_cfg:
        return empty

    parsed = [parse_scenario_name(s) for s in scenario_labels]
    years_present = sorted(set(year for year, _ in parsed if year is not None))
    if not years_present:
        return empty

    base_year = years_present[0]
    target_years = years_present
    scenario_types = sorted(set(scenario for _, scenario in parsed if scenario is not None))

    try:
        default_values, _ = extract_config_data(transport_cfg, "default")
        country_values, _ = extract_config_data(transport_cfg, country)

        cagr_values = copy.deepcopy(default_values)
        for key, value in country_values.items():
            if key in cagr_values and isinstance(cagr_values[key], dict) and isinstance(value, dict):
                cagr_values[key].update(value)
            else:
                cagr_values[key] = value

        marine_base, aviation_base = 0.0, 0.0
        if unsd_global_output.exists():
            unsd_df = pd.read_excel(unsd_global_output)
            unsd_df['Country_Clean'] = unsd_df['Country'].astype(str).str.strip().str.lower()
            target_country_clean = country.strip().lower()

            match = unsd_df[
                (unsd_df['Country_Clean'] == target_country_clean) &
                (unsd_df['Year'].astype(str) == str(base_year))
            ]
            if not match.empty:
                marine_base = float(match['Marine_Bunkers_TWh'].values[0])
                aviation_base = float(match['Aviation_Bunkers_TWh'].values[0])

        marine_cagr = get_cagr(cagr_values, "Final Energy - Int. Maritime")
        aviation_cagr = get_cagr(cagr_values, "Final Energy - Int. Aviation")

        marine_expanded = expand_with_cagr(
            marine_base,
            marine_cagr,
            base_year,
            target_years,
            scenario_types
        )
        aviation_expanded = expand_with_cagr(
            aviation_base,
            aviation_cagr,
            base_year,
            target_years,
            scenario_types
        )

        return {
            'maritime': marine_expanded,
            'aviation': aviation_expanded,
        }
    except Exception as e:
        print(f"  [WARNING] Could not compute bunker series for {country}: {e}")
        return empty

def run(country: str, base_dir: str = "output_data") -> None:
    country_code = get_iso2_country_code(country)

    # === FOLDER SELECTION LOGIC ===

    if choose_folder:
        latest_dir = os.path.join(base_dir, choose_folder)
        if not os.path.exists(latest_dir):
            raise FileNotFoundError(f"The chosen folder does not exist: {latest_dir}")
        print(f" Using folder: {choose_folder}")

    else:
        latest_dir = find_latest_dir(base_dir)
        print(f" Latest folder found: {latest_dir}")

    available = list_countries(latest_dir)
    if country not in available:
        raise ValueError(f"{country} not found. Available: {', '.join(available)}")

    # 1. LOAD THE DATA (User-edited 2020 values are loaded here)
    file_path = find_country_file(country, latest_dir)
    df = load_country_dataframe(file_path)
    # 2. UPDATED PATH: Look for config in the main script folder

    # -----------------------------------------------------------------
    # Use the top-level transport_config_path (set at the top of this file)

    if transport_config_path.exists():
        print(f"  >>> Found config! Refreshing projections for {country}...")
        # 1. First, apply the growth rates from your config (use the single top-level path)
        df = apply_cagr_projections(df, transport_config_path, country, base_year="2020")
        # 2. Balance the 100% shares
        df = calculate_remainders(df)

        # Persist the refreshed assumptions back to the source CSV so the user can see the applied values
        df.to_csv(file_path, index=False)

        # SAVE THE REFRESHED DATA FOR VERIFICATION
        debug_dir = os.path.join(results_dir, "country_specific", country)
        os.makedirs(debug_dir, exist_ok=True)
        debug_path = os.path.join(debug_dir, f"output_{country}_updated.csv")
        df.to_csv(debug_path, index=False)

    else:
        print(f"  Warning: trans_config.csv NOT found at {transport_config_path}")

    # 3. PROCEED WITH CALCULATIONS (Updated: only one metrics_raw creation)
    metrics_raw = dataframe_to_metrics_raw(df)
    scenarios = [c for c in df.columns if c not in ["Metric", "Units"]]
    all_results = []
    for scn in scenarios:
        df_scn = calc_for_scenario(metrics_raw, scn)
        if df_scn is not None and not df_scn.empty:
            all_results.append(df_scn)

    if not all_results:
        raise ValueError(f"No valid scenarios produced for {country}")

    # ... (Rest of your original code for saving results remains the same) ...
    final_df = pd.concat(all_results, ignore_index=True)
    fuel_summary, mode_summary, subsector_summary, enduse_summary = build_summary(final_df, metrics_raw)

    # Save results in output_data/country_specific
    country_results_dir = os.path.join(results_dir, "country_specific", country)
    os.makedirs(country_results_dir, exist_ok=True)

    # Save detailed Energy Demand (GWh) as parameters_{country}.csv
    final_df.to_csv(os.path.join(country_results_dir, f"parameters_{country}.csv"), index=False)

    # ...existing code...

    # Generate Indicators and save
    indicators_df = pd.DataFrame()
    try:
        indicators_df = generate_transport_indicators(final_df, country, metrics_raw)

        bunker_series = get_country_bunker_series(country, indicators_df["scenario"].tolist(), transport_config)
        indicators_df["total international aviation"] = indicators_df["scenario"].map(
            lambda s: float(bunker_series["aviation"].get(str(s), 0.0))
        )
        indicators_df["total international navigation"] = indicators_df["scenario"].map(
            lambda s: float(bunker_series["maritime"].get(str(s), 0.0))
        )

        indicators_df.to_csv(os.path.join(country_results_dir, f"{country_code}_final_energy_demand.csv"), index=False)
    except Exception as e:
        print(f"  Warning: Could not generate indicators: {e}")

    # Save Summaries (Excel)
    with pd.ExcelWriter(os.path.join(country_results_dir, f"{country_code}_summary.xlsx")) as writer:
        fuel_summary.to_excel(writer, sheet_name="Fuel")
        mode_summary.to_excel(writer, sheet_name="Mode")
        subsector_summary.to_excel(writer, sheet_name="Subsector")
        enduse_summary.to_excel(writer, sheet_name="EndUse")

    print(f" Saved results for {country} ({country_code}) in {country_results_dir}")
    return indicators_df

def export_global_energy_totals(all_country_indicators: list, bunker_data_by_country: dict = None):
    """
    Combines indicators from all countries and saves separate CSVs 
    for each scenario/year combination in results/ folder.
    
    Each file contains all countries with their individual values plus 
    international bunker data, NOT aggregated totals.
    """
    if not all_country_indicators:
        return
    
    if bunker_data_by_country is None:
        bunker_data_by_country = {}

    # Combine all collected DataFrames (keeps all country rows)
    master_df = pd.concat(all_country_indicators, ignore_index=True)
    
    # Save directly to results folder (no subfolder)
    total_dir = results_dir

    # Group by scenario (e.g., 2030_Baseline, 2030_EL, 2030_RF)
    groups = master_df.groupby("scenario")

    for scenario_name, group_df in groups:
        # Build filename as transport_{scenario}_{year}.csv
        scenario_str = str(scenario_name).replace(" ", "_")
        parts = scenario_str.split("_", 1)
        year_part = parts[0] if parts and parts[0].isdigit() else "unknown"
        scenario_part = parts[1] if len(parts) > 1 and parts[1] else "all"
        file_path = os.path.join(total_dir, f"transport_{scenario_part}_{year_part}.csv")
        
        # Add international bunker values to each country row
        group_df_copy = group_df.copy()
        
        scenario_key = str(scenario_name)
        
        # Add bunker columns for each country
        for idx, row in group_df_copy.iterrows():
            country = row.get("country", "Unknown")
            
            # Keep already-computed indicator values unless a bunker lookup overrides them
            try:
                aviation_bunker = float(row.get("total international aviation", 0.0))
            except (TypeError, ValueError):
                aviation_bunker = 0.0

            try:
                maritime_bunker = float(row.get("total international navigation", 0.0))
            except (TypeError, ValueError):
                maritime_bunker = 0.0
            
            if country in bunker_data_by_country:
                bunker_dicts = bunker_data_by_country[country]
                
                # DEBUG: First time for this country, print available keys
                #if idx == group_df_copy.index[0]:
                    #print(f"  [Debug] {country} aviation bunker keys: {list(bunker_dicts['aviation'].keys())[:10]}")
                
                # Bunker values are kept in TWh for indicator outputs
                if bunker_dicts['aviation'] and scenario_key in bunker_dicts['aviation']:
                    aviation_bunker = float(bunker_dicts['aviation'][scenario_key])
                    #print(f"  [Debug] Found aviation bunker for {country}/{scenario_key}: {aviation_bunker:.2f} GWh")
                #elif bunker_dicts['aviation']:
                    #print(f"  [Debug] ERROR: scenario_key '{scenario_key}' NOT in aviation bunker dict for {country}")
                
                if bunker_dicts['maritime'] and scenario_key in bunker_dicts['maritime']:
                    maritime_bunker = float(bunker_dicts['maritime'][scenario_key])
                    #print(f"  [Debug] Found maritime bunker for {country}/{scenario_key}: {maritime_bunker:.2f} GWh")
                #elif bunker_dicts['maritime']:
                    #print(f"  [Debug] ERROR: scenario_key '{scenario_key}' NOT in maritime bunker dict for {country}")
            #else:
                #print(f"  [Debug] WARNING: {country} not in bunker_data_by_country")
            
            # Set the bunker values in the dataframe
            group_df_copy.at[idx, "total international aviation"] = aviation_bunker
            group_df_copy.at[idx, "total international navigation"] = maritime_bunker
        
        # Save the full dataframe with all countries and bunker data
        group_df_copy.to_csv(file_path, index=False, encoding='utf-8')



if __name__ == "__main__":
    # List to collect indicator dataframes from all countries
    all_indicators_list = []
    for country in countries:
        try:
            print(f"\n{'='*50}\n Processing country: {country}\n{'='*50}")
            # Capture the returned dataframe
            country_indicators = run(country=country, base_dir=results_dir)
            if not country_indicators.empty:
                all_indicators_list.append(country_indicators)
        except Exception as e:
            print(f" Error processing {country}: {e}")

    # Final step: Calculate bunker data and export global totals
    print(f"\n{'='*50}\n Generating Global Energy Totals\n{'='*50}")
    
    # Extract base_year, target_years, and scenarios from scenario names in the data

    if all_indicators_list and transport_config:
        master_df = pd.concat(all_indicators_list, ignore_index=True)
        scenarios_present = master_df["scenario"].unique()
        years_present = sorted(set(year for year, _ in [parse_scenario_name(s) for s in scenarios_present] if year is not None))
        base_year = years_present[0] if years_present else 2020
        target_years = years_present if years_present else [2030, 2035, 2040, 2045, 2050]
        # Extract scenario types, excluding None (which represents base year without specific scenario)
        scenario_types = sorted(set(scenario for _, scenario in [parse_scenario_name(s) for s in scenarios_present] if scenario is not None))
        
        bunker_data_by_country = {}
        
        try:
            # Extract default CAGR values
            DEFAULT_VALUES, _ = extract_config_data(transport_config, "default")
            
            # Calculate international bunker values for each country
            for country in countries:
                try:
                    # Load country-specific CAGR overrides
                    country_values, _ = extract_config_data(transport_config, country)
                    cagr_values = DEFAULT_VALUES.copy()
                    
                    # Merge country overrides
                    for k, v in country_values.items():
                        if k in cagr_values and isinstance(cagr_values[k], dict) and isinstance(v, dict):
                            cagr_values[k].update(v)
                        else:
                            cagr_values[k] = v
                    
                    # Load base year bunker values from UNSD Excel
                    if unsd_global_output.exists():
                        unsd_df = pd.read_excel(unsd_global_output)
                        unsd_df['Country_Clean'] = unsd_df['Country'].astype(str).str.strip().str.lower()
                        target_country_clean = country.strip().lower()
                        
                        match = unsd_df[
                            (unsd_df['Country_Clean'] == target_country_clean) & 
                            (unsd_df['Year'].astype(str) == str(base_year))
                        ]
                        
                        if not match.empty:
                            marine_base = float(match['Marine_Bunkers_TWh'].values[0])
                            aviation_base = float(match['Aviation_Bunkers_TWh'].values[0])
                        else:
                            marine_base, aviation_base = 0.0, 0.0
                            print(f"    [WARNING] {country} not found in UNSD {unsd_global_output}")
                    else:
                        marine_base, aviation_base = 0.0, 0.0
                        print(f"    [WARNING] UNSD file not found at {unsd_global_output}")
                    
                    # Expand bunker values using CAGR for all target years and scenarios
                    marine_cagr = get_cagr(cagr_values, "Final Energy - Int. Maritime")
                    aviation_cagr = get_cagr(cagr_values, "Final Energy - Int. Aviation")
                    
                    marine_expanded = expand_with_cagr(
                        marine_base,
                        marine_cagr,
                        base_year, target_years, scenario_types
                    )
                    
                    aviation_expanded = expand_with_cagr(
                        aviation_base,
                        aviation_cagr,
                        base_year, target_years, scenario_types
                    )
                    
                    bunker_data_by_country[country] = {
                        'maritime': marine_expanded,
                        'aviation': aviation_expanded
                    }
                    
                except Exception as e:
                    bunker_data_by_country[country] = {'maritime': {}, 'aviation': {}}
        
        except Exception as e:
            bunker_data_by_country = {c: {'maritime': {}, 'aviation': {}} for c in countries}
        
        # Export global energy totals with bunker data
        export_global_energy_totals(all_indicators_list, bunker_data_by_country)
        
    elif all_indicators_list:
        # If config not loaded, still export without bunker data
        print("  [WARNING] Config not loaded. Exporting without international bunker data.")
        export_global_energy_totals(all_indicators_list)
    
    print("All tasks complete.")


