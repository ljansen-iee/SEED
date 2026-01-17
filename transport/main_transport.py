import os
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
# === Imports from project libraries ===
from helpers import find_input_folder, load_country_specific_data, load_global_transport_data, get_transport_constants, interpolate_or_extrapolate, clean_column_headers, clean_missing_countries, generate_units_dictionary, reorder_and_filter_columns 
from build_macro_indicators import process_population_data, get_ssp_for_scenario
from build_share_subsectors import extract_country_transport_data, create_country_dfs, final_df as TRANSPORT_SUBSECTOR_FINAL
from build_share_mode import process_bus_share_data, share_of_two_Three
from build_load_factors import get_Load_factor_Car, Load_factor_Bus, Load_factor_two_three_occupancy, heavy_load_factor, medium_load_factor, load_factor
from build_energy_intensities import generate_energy_intensities, expand_intensity
from build_technology_share import Share_of_Direct_Electric_Passenger_Train, share_technology, TECHNOLOGY_OVERRIDES, enforce_share_constraints, apply_technology_overrides
from build_CAGR import poly_project, expand_with_cagr, expand_constant, as_fraction, get_cagr
from config_loader import load_transport_config


# === Constants ===
BASE_YEAR = 2020  # Define the start year for the projections. 2020 by default. Years between 2020 and 2025 are available (via interpolation),

SSP_ORDER = ["SSP2", "SSP2", "SSP1"]

SCENARIOS = [
    "Baseline",
    "Er", 
    "RL"] # a max of three scenarios are possible.

from build_macro_indicators import validate_scenarios_and_ssp
validate_scenarios_and_ssp(SCENARIOS, SSP_ORDER)

TARGET_YEARS = [2030,2040,2050]  # multiple year are possible. 

# === Transport assumptions file (user can change this) ===
TRANSPORT_CONFIG_FILE = "trans_config.xlsx"


TRANSPORT_CONFIG_PATH = Path(__file__).resolve().parent / TRANSPORT_CONFIG_FILE
print("\n===============================")
print("Running transport sector pipeline")
print(f"Transport assumptions file: {TRANSPORT_CONFIG_FILE}")
print("===============================\n")


devkopsys_countries =  ["Republic of the Congo", "Egypt", "Ethiopia", "Ghana","Kenya","Namibia","Niger",
                         "Algeria","Argentina","Brazil","Chile","Colombia","Mexico","Peru","Venezuela",
                          "Morocco","Tunisia","Tanzania", "South Africa","Libya",

                          #G20 countries
                          "Argentina", "Australia", "Brazil", "Canada", "China", "France", "Germany",  
                          "India", "Indonesia", "Italy", "Japan", "Mexico","Russia", "Saudi Arabia", 
                          "South Africa", "South Korea", "United Kingdom", "United States"]

#Turkey population data is missing in the population dataset, so excluding Turkey temporarily.
# === Loop through countries ===

countries_to_load = devkopsys_countries + ["default"] 

TRANSPORT_CONFIG = load_transport_config(
    excel_path=Path(__file__).resolve().parent / TRANSPORT_CONFIG_FILE,
    countries=countries_to_load,
    scenarios=SCENARIOS
)

# Extract the Default values once, to use them later
DEFAULT_VALUES = TRANSPORT_CONFIG.get("default", {})
if not DEFAULT_VALUES:
    print(" WARNING: No 'default' data found in trans_config.xlsx. Fallback logic might fail.")

def main(base_year=None, target_years=None, scenarios=None):
    base_year = int(base_year) if base_year is not None else BASE_YEAR
    target_years = list(map(int, target_years)) if target_years is not None else list(TARGET_YEARS)
    scenarios = list(scenarios) if scenarios is not None else list(SCENARIOS)

    # Load global transport data
    try:
        df_raw = load_global_transport_data()
        if df_raw is None:
            print("Global transport data missing. Exiting.")
            return
    except Exception as e:
        print(f"Error loading global transport data: {e}")
        return

    # Preprocess
    try:
        df_cleaned = clean_missing_countries(df_raw)
        df_cleaned = clean_column_headers(df_cleaned)
        df_process_bus_share_data = process_bus_share_data(df_raw)
        df_share_two_three = share_of_two_Three(df_raw)
        df_load_factor_car = get_Load_factor_Car(df_raw)
        df_load_factor_bus = Load_factor_Bus(df_raw)
        df_load_factor_two_three_occupancy = Load_factor_two_three_occupancy(df_raw)
        df_Share_of_Direct_Electric_Passenger_Train = Share_of_Direct_Electric_Passenger_Train(df_raw)
        df_medium_load_factor = medium_load_factor(df_raw)
        df_heavy_load_factor = heavy_load_factor(df_raw)
        load_passenger_plane, load_freight_ship, load_passenger_ship = load_factor()
    except Exception as e:
        print(f"Error in preprocessing: {e}")
        return

    # Output folder
    today_str = datetime.today().strftime("%Y%m%d")

    # transport/ folder (where this file lives)
    TRANSPORT_DIR = Path(__file__).resolve().parent

    # transport/output_data/DKS_YYYYMMDD
    base_output_dir = TRANSPORT_DIR / "output_data" / f"DKS_{today_str}"

    base_output_dir.mkdir(parents=True, exist_ok=True)


    units_dict = generate_units_dictionary()

    # === Loop through countries ===
    for selected_country in devkopsys_countries:
        print(f"\n🔹 Processing: {selected_country}")
        years = str(BASE_YEAR)

        # === Load Data & Merge with Defaults ===
        try:
            # 1. Get Country Specific Data
            country_values = TRANSPORT_CONFIG.get(selected_country, {})
            
            # 2. Start with Defaults
            # We use .copy() so we don't accidentally change the defaults for the next country
            CAGR_VALUES = DEFAULT_VALUES.copy() 
            
            # 3. Update with Country Specifics (Overwrites defaults if data exists)
            if country_values:
                CAGR_VALUES.update(country_values)
            
            # 4. Final Safety Check
            if not CAGR_VALUES:
                raise ValueError(
                    f"No data found (neither Default nor Country-specific) for: {selected_country}"
                )

        except Exception as e:
            print(f" Error preparing configuration for {selected_country}: {e}")
            continue

       # ------- Population -------
        try:
            dfs_country_spe = load_country_specific_data(find_input_folder())
            df_population = process_population_data(dfs_country_spe)
            pop_df = df_population.loc[selected_country]
            if "Unit" in pop_df.columns:
                pop_df = pop_df.drop(columns=["Unit"])

            known_years = [2020, 2030, 2040, 2050]   # years we trust
            all_years = [BASE_YEAR] + TARGET_YEARS

            pop_values = {}
            for year in all_years:
                for scenario in SCENARIOS:
                    ssp = get_ssp_for_scenario(
                        scenario=scenario,
                        scenarios=SCENARIOS,
                        ssp_order=SSP_ORDER
                    )
                    if str(year) in pop_df.columns:
                        value = float(pop_df.loc[ssp, str(year)])
                    else:
                        known_vals = [float(pop_df.loc[ssp, str(y)]) for y in known_years if str(y) in pop_df.columns]
                        known_yrs  = [y for y in known_years if str(y) in pop_df.columns]
                        projections = poly_project(known_yrs, known_vals, [year])
                        value = projections[year]
                    pop_values[f"{year}_{scenario}"] = value



            # add plain base year (default to Baseline’s SSP)
            base_ssp = SSP_ORDER[0]  # SSP for first scenario (Baseline by position)

            if str(BASE_YEAR) in pop_df.columns:
                pop_values[str(BASE_YEAR)] = float(
                    pop_df.loc[base_ssp, str(BASE_YEAR)]
                )
            else:
                pop_values[str(BASE_YEAR)] = pop_values[f"{BASE_YEAR}_{SCENARIOS[0]}"]


            population_row = {"Metric": "Population", **pop_values, "Units": "million"}
            all_rows = [population_row]

        except Exception as e:
            print(f" Skipping {selected_country}: Population error ({e})")
            continue
        # ------- Transport indicators (use processed subsector DF) -------
        try:
            # Use the fully processed MultiIndex DF from build_share_subsectors.py
            subsector_df = TRANSPORT_SUBSECTOR_FINAL  # index levels: ["Country", "subsector_transport"]

            # Build a per-country dataframe
            country_dfs = create_country_dfs(subsector_df, [selected_country])
            country_key = f"df_{selected_country.replace(' ', '_')}"
            country_df = country_dfs.get(country_key)
            if country_df is None:
                raise Exception(f"Subsector data for {selected_country} not found")

            # Flatten MultiIndex to columns so extract_country_transport_data can work
            country_df = country_df.reset_index()  # columns: Country, subsector_transport, 2005.0, 2010.0, ...

            # This computes shares & mobility and returns a table indexed by subsector names
            country_data, _ = extract_country_transport_data(selected_country, "SSP1", df_population, country_df)

            # helper to fetch a value from the country_data (row by name, column by year)
            def val(name, year):
                """
                Fetch a value from country_data (row by name, column by year).
                Accepts 2020 or 2020.0 style columns.
                """
                y = str(year)
                candidates = [y] if '.' in y else [y, f"{y}.0"]  # try '2020' then '2020.0'
                for col in candidates:
                    if name in country_data.index and col in country_data.columns:
                        try:
                            return float(country_data.loc[name, col])
                        except Exception:
                            pass
                return np.nan

            # --- filter numeric year columns only ---
            share_years = [
                c for c in country_data.columns
                if str(c).replace('.', '').isdigit()  # must be all digits
                and not any(x in str(c) for x in ["Baseline", "RF", "EL"])  # drop scenario cols
            ]
            # Build the scenario baseline using the computed subsector rows
            scenario_baseline = {
                "Mobility per capita - Passenger": poly_project(
                    share_years, [val('Mobility per capita - Passenger', y) for y in share_years], [BASE_YEAR]
                )[BASE_YEAR],

                "Load Factor - LDV": poly_project(
                    share_years,
                    [df_load_factor_car.loc[df_load_factor_car["Countries List"] == selected_country, str(y)].values[0] if str(y) in df_load_factor_car.columns else np.nan for y in share_years],
                    [BASE_YEAR]
                )[BASE_YEAR],

                "Load Factor - Bus": poly_project(
                    share_years,
                    [df_load_factor_bus.loc[df_load_factor_bus["Countries List"] == selected_country, str(y)].values[0] if str(y) in df_load_factor_bus.columns else np.nan for y in share_years],
                    [BASE_YEAR]
                )[BASE_YEAR],

                "Load Factor - 2&3W": poly_project(
                    share_years,
                    [df_load_factor_two_three_occupancy.loc[df_load_factor_two_three_occupancy["Countries List"] == selected_country, str(y)].values[0] if str(y) in df_load_factor_two_three_occupancy.columns else np.nan for y in share_years],
                    [BASE_YEAR]
                )[BASE_YEAR],

                "Load Factor - Passenger Train": (
                    poly_project(
                        share_years,
                        [df_load_factor_car.loc[df_load_factor_car["Countries List"] == selected_country, str(y)].values[0] if str(y) in df_load_factor_car.columns else np.nan for y in share_years],
                        [BASE_YEAR]
                    )[BASE_YEAR] * get_transport_constants('load_factor_multiplier', 'Passenger Train')
                ),
                "Load Factor - Passenger Plane": load_passenger_plane,
                "Load Factor - Freight Ship": load_freight_ship,
                "Load Factor - Passenger Ship": load_passenger_ship,
            }

            # --- Freight Load Factors ---

            # LDT
            ldt_base = poly_project(
                share_years,
                [df_medium_load_factor.loc[df_medium_load_factor["Countries List"] == selected_country, str(y)].values[0]
                if str(y) in df_medium_load_factor.columns else np.nan for y in share_years],
                [BASE_YEAR]
            )[BASE_YEAR]
            ldt_expanded = expand_constant(ldt_base, BASE_YEAR, TARGET_YEARS, SCENARIOS)

            # HDT
            hdt_base = poly_project(
                share_years,
                [df_heavy_load_factor.loc[df_heavy_load_factor["Countries List"] == selected_country, str(y)].values[0]
                if str(y) in df_heavy_load_factor.columns else np.nan for y in share_years],
                [BASE_YEAR]
            )[BASE_YEAR]
            hdt_expanded = expand_constant(hdt_base, BASE_YEAR, TARGET_YEARS, SCENARIOS)

            # Freight Train
            train_freight_base = hdt_base * get_transport_constants('load_factor_multiplier', 'Freight Train')
            train_freight_expanded = expand_constant(train_freight_base, BASE_YEAR, TARGET_YEARS, SCENARIOS)

            # Freight Ship (default = 508)
            ship_freight_base = 508.0
            ship_freight_expanded = expand_constant(ship_freight_base, BASE_YEAR, TARGET_YEARS, SCENARIOS)

            # Append rows
            all_rows.append({"Metric": "Load Factor - LDT", **ldt_expanded, "Units": "t/vehicle"})
            all_rows.append({"Metric": "Load Factor - HDT", **hdt_expanded, "Units": "t/vehicle"})
            all_rows.append({"Metric": "Load Factor - Freight Train", **train_freight_expanded, "Units": "t/vehicle"})
            all_rows.append({"Metric": "Load Factor - Freight Ship", **ship_freight_expanded, "Units": "t/vehicle"})


            # --- Subsector Shares: Road, Rail, Aviation ---
            try:
                # Get base-year Rail value (interpolate if needed)
                rail_base = poly_project(
                    share_years, [val("Rail Passenger %", y) for y in share_years], [BASE_YEAR]
                )[BASE_YEAR]

                # Get base-year Aviation value (default 1.12 if missing)
                aviation_base = poly_project(
                    share_years, [val("Aviation Passenger %", y) for y in share_years], [BASE_YEAR]
                )[BASE_YEAR]
                if aviation_base is None or np.isnan(aviation_base):
                    aviation_base = 1.12

                # Expand with manual CAGRs
                rail_expanded = expand_with_cagr(
                    rail_base,
                    get_cagr(CAGR_VALUES, "Share per Subsector - Rail Passenger = Train"),
                    BASE_YEAR,
                    TARGET_YEARS,
                    SCENARIOS
                )

                aviation_expanded = expand_with_cagr(
                    aviation_base,
                    get_cagr(CAGR_VALUES, "Share per Subsector - Aviation Passenger = Plane"),
                    BASE_YEAR,
                    TARGET_YEARS,
                    SCENARIOS
                )


                # Road share = 100 - (Rail + Aviation)
                road_expanded = {}
                road_expanded[str(BASE_YEAR)] = 100.0 - (rail_expanded[str(BASE_YEAR)] + aviation_expanded[str(BASE_YEAR)])
                for year in TARGET_YEARS:
                    for scenario in SCENARIOS:
                        key = f"{year}_{scenario}"
                        road_expanded[key] = 100.0 - (rail_expanded[key] + aviation_expanded[key])

                # --- Safety check: normalize so Road + Rail + Aviation = 100 each year ---
                for year in [str(BASE_YEAR)] + [f"{y}_{s}" for y in TARGET_YEARS for s in SCENARIOS]:
                    total = rail_expanded.get(year, 0) + aviation_expanded.get(year, 0) + road_expanded.get(year, 0)
                    if abs(total - 100.0) > 1e-6 and total > 0:
                        scale = 100.0 / total
                        if year in rail_expanded:
                            rail_expanded[year] *= scale
                        if year in aviation_expanded:
                            aviation_expanded[year] *= scale
                        if year in road_expanded:
                            road_expanded[year] *= scale

                # Append rows AFTER normalization
                all_rows.append({
                    "Metric": "Share per Subsector - Rail Passenger = Train",
                    **rail_expanded, "Units": "% of pkm"
                })
                all_rows.append({
                    "Metric": "Share per Subsector - Aviation Passenger = Plane",
                    **aviation_expanded, "Units": "% of pkm"
                })
                all_rows.append({
                    "Metric": "Share per Subsector - Road Passenger",
                    **road_expanded, "Units": "% of pkm"
                })
                mcp_expanded = expand_with_cagr(
                    scenario_baseline["Mobility per capita - Passenger"],
                    get_cagr(CAGR_VALUES, "Mobility per capita - Passenger"),
                    BASE_YEAR,
                    TARGET_YEARS,
                    SCENARIOS
                )


                all_rows.append({
                    "Metric": "Mobility per capita - Passenger",
                    **mcp_expanded,
                    "Units": units_dict.get("Mobility per capita - Passenger", "pkm/p")
                })
            except Exception as e:
                print(f" Skipping {selected_country}: Subsector shares error ({e})")

            # --- Subsector Shares: Freight (Road, Rail, Ship) ---

            # --- Mode Shares: LDV, Bus, 2&3W ---
            try:
                # --- Base year Bus ---
                bus_base = poly_project(
                    share_years,
                    [df_process_bus_share_data.loc[df_process_bus_share_data["Countries List"] == selected_country, str(y)].values[0]
                     if str(y) in df_process_bus_share_data.columns else np.nan for y in share_years],
                    [BASE_YEAR]
                )[BASE_YEAR]

                # --- Base year 2&3W ---
                two3w_base = poly_project(
                    share_years,
                    [df_share_two_three.loc[df_share_two_three["Countries List"] == selected_country, str(y)].values[0]
                     if str(y) in df_share_two_three.columns else np.nan for y in share_years],
                    [BASE_YEAR]
                )[BASE_YEAR]

                # --- LDV = remainder ---
                ldv_base = 100.0 - (bus_base + two3w_base)

                # --- Expand with CAGR ---
                bus_expanded = expand_with_cagr(
                    bus_base,
                    get_cagr(CAGR_VALUES, "Share per Mode - Bus"),
                    BASE_YEAR,
                    TARGET_YEARS,
                    SCENARIOS
                )


                two3w_expanded = expand_with_cagr(
                    two3w_base,
                    get_cagr(CAGR_VALUES, "Share per Mode - 2&3W"),
                    BASE_YEAR,
                    TARGET_YEARS,
                    SCENARIOS
                )

                # LDV = remainder each year
                ldv_expanded = {}
                ldv_expanded[str(BASE_YEAR)] = ldv_base
                for year in TARGET_YEARS:
                    for scenario in SCENARIOS:
                        key = f"{year}_{scenario}"
                        ldv_expanded[key] = 100.0 - (bus_expanded[key] + two3w_expanded[key])

                # --- Safety check: sum to 100 ---
                for year in [str(BASE_YEAR)] + [f"{y}_{s}" for y in TARGET_YEARS for s in SCENARIOS]:
                    total = (bus_expanded.get(year, 0) +
                             two3w_expanded.get(year, 0) +
                             ldv_expanded.get(year, 0))
                    if abs(total - 100.0) > 1e-6 and total > 0:
                        scale = 100.0 / total
                        if year in bus_expanded:
                            bus_expanded[year] *= scale
                        if year in two3w_expanded:
                            two3w_expanded[year] *= scale
                        if year in ldv_expanded:
                            ldv_expanded[year] *= scale

                # --- Append rows ---
                all_rows.append({
                    "Metric": "Share per Mode - Bus",
                    **bus_expanded, "Units": "% of Road pkm"
                })
                all_rows.append({
                    "Metric": "Share per Mode - 2&3W",
                    **two3w_expanded, "Units": "% of Road pkm"
                })
                all_rows.append({
                    "Metric": "Share per Mode - LDV",
                    **ldv_expanded, "Units": "% of Road pkm"
                })

            except Exception as e:
                print(f" Skipping {selected_country}: Mode shares error ({e})")

                        # --- Load Factors ---
            try:
                # LDV
                ldv_base = poly_project(
                    share_years,
                    [df_load_factor_car.loc[df_load_factor_car["Countries List"] == selected_country, str(y)].values[0]
                    if str(y) in df_load_factor_car.columns else np.nan for y in share_years],
                    [BASE_YEAR]
                )[BASE_YEAR]
                ldv_expanded = expand_constant(ldv_base, BASE_YEAR, TARGET_YEARS, SCENARIOS)

                # Bus
                bus_base = poly_project(
                    share_years,
                    [df_load_factor_bus.loc[df_load_factor_bus["Countries List"] == selected_country, str(y)].values[0]
                    if str(y) in df_load_factor_bus.columns else np.nan for y in share_years],
                    [BASE_YEAR]
                )[BASE_YEAR]
                bus_expanded = expand_constant(bus_base, BASE_YEAR, TARGET_YEARS, SCENARIOS)

                # 2&3W
                two3w_base = poly_project(
                    share_years,
                    [df_load_factor_two_three_occupancy.loc[df_load_factor_two_three_occupancy["Countries List"] == selected_country, str(y)].values[0]
                    if str(y) in df_load_factor_two_three_occupancy.columns else np.nan for y in share_years],
                    [BASE_YEAR]
                )[BASE_YEAR]
                two3w_expanded = expand_constant(two3w_base, BASE_YEAR, TARGET_YEARS, SCENARIOS)

                # Passenger Train
                train_base = ldv_base * get_transport_constants('load_factor_multiplier', 'Passenger Train')
                train_expanded = expand_constant(train_base, BASE_YEAR, TARGET_YEARS, SCENARIOS)

                # Passenger Plane (default = 101)
                plane_base = 101.0
                plane_expanded = expand_constant(plane_base, BASE_YEAR, TARGET_YEARS, SCENARIOS)

                # Append rows
                all_rows.append({"Metric": "Load Factor - LDV", **ldv_expanded, "Units": "p/vehicle"})
                all_rows.append({"Metric": "Load Factor - Bus", **bus_expanded, "Units": "p/vehicle"})
                all_rows.append({"Metric": "Load Factor - 2&3W", **two3w_expanded, "Units": "p/vehicle"})
                all_rows.append({"Metric": "Load Factor - Passenger Train", **train_expanded, "Units": "p/vehicle"})
                all_rows.append({"Metric": "Load Factor - Passenger Plane", **plane_expanded, "Units": "p/vehicle"})
                
                ship_base = load_passenger_ship
                ship_expanded = expand_constant(ship_base, BASE_YEAR, TARGET_YEARS, SCENARIOS)
                all_rows.append({
                    "Metric": "Load Factor - Passenger Ship",
                    **ship_expanded,
                    "Units": "p/vehicle"
                })

            except Exception as e:
                print(f" Skipping {selected_country}: Load factors error ({e})")

            try:
                # --- Mobility per capita - Freight (MCF) ---
                freight_base = poly_project(
                    share_years, [val("Mobility per capita - Freight", y) for y in share_years], [BASE_YEAR]
                )[BASE_YEAR]

                freight_expanded = expand_with_cagr(
                    freight_base,
                    get_cagr(CAGR_VALUES, "Mobility per capita - Freight"),
                    BASE_YEAR,
                    TARGET_YEARS,
                    SCENARIOS
                )

                all_rows.append({
                    "Metric": "Mobility per capita - Freight",
                    **freight_expanded,
                    "Units": "tkm/p"
                })

                # --- Default base-year values ---
                road_freight_base = 75.0
                ship_freight_base = 3.70
                rail_freight_base = 100.0 - (road_freight_base + ship_freight_base)

                # --- Expand Rail and Ship with CAGRs ---
                rail_freight_expanded = expand_with_cagr(
                    rail_freight_base,
                    get_cagr(CAGR_VALUES, "Share per Subsector - Rail Freight = Train"),
                    BASE_YEAR,
                    TARGET_YEARS,
                    SCENARIOS
                )


                ship_freight_expanded = expand_with_cagr(
                    ship_freight_base,
                    get_cagr(CAGR_VALUES, "Share per Subsector - Navigation Freight = Ship"),
                    BASE_YEAR,
                    TARGET_YEARS,
                    SCENARIOS
                )


                # Road Freight = remainder each year
                road_freight_expanded = {}
                road_freight_expanded[str(BASE_YEAR)] = road_freight_base
                for year in TARGET_YEARS:
                    for scenario in SCENARIOS:
                        key = f"{year}_{scenario}"
                        road_freight_expanded[key] = 100.0 - (
                            rail_freight_expanded[key] + ship_freight_expanded[key]
                        )

                # --- Safety check: sum to 100 ---
                for year in [str(BASE_YEAR)] + [f"{y}_{s}" for y in TARGET_YEARS for s in SCENARIOS]:
                    total = (rail_freight_expanded.get(year, 0) +
                             ship_freight_expanded.get(year, 0) +
                             road_freight_expanded.get(year, 0))
                    if abs(total - 100.0) > 1e-6 and total > 0:
                        scale = 100.0 / total
                        if year in rail_freight_expanded:
                            rail_freight_expanded[year] *= scale
                        if year in ship_freight_expanded:
                            ship_freight_expanded[year] *= scale
                        if year in road_freight_expanded:
                            road_freight_expanded[year] *= scale

                # --- Append rows ---
                all_rows.append({
                    "Metric": "Share per Subsector - Road Freight",
                    **road_freight_expanded, "Units": "% of tkm"
                })
                all_rows.append({
                    "Metric": "Share per Subsector - Rail Freight = Train",
                    **rail_freight_expanded, "Units": "% of tkm"
                })
                all_rows.append({
                    "Metric": "Share per Subsector - Navigation Freight = Ship",
                    **ship_freight_expanded, "Units": "% of tkm"
                })

                # --- Mode Shares: Freight Trucks (HDT vs LDT) ---
                # --- Mode Shares: Freight Trucks (HDT vs LDT) ---
                try:
                    # numeric year columns available in country_data (e.g., 2005.0..2050.0)
                    numeric_years = sorted(
                        {int(float(c)) for c in country_data.columns
                        if str(c).replace('.', '').isdigit()
                        and not any(x in str(c) for x in ["Baseline", "RF", "EL"])}
                    )

                    # build series for HDT/LDT/Total Road Freight (tkm)
                    hdt_series = [val("Road Freight - Heavy-Duty Trucks", y) for y in numeric_years]
                    ldt_series = [val("Road Freight - Light-Duty Trucks", y) for y in numeric_years]
                    total_series = [val("Road Freight", y) for y in numeric_years]

                    # interpolate/extrapolate each series to BASE_YEAR
                    hdt_base_tkm = poly_project(numeric_years, hdt_series, [BASE_YEAR])[BASE_YEAR]
                    ldt_base_tkm = poly_project(numeric_years, ldt_series, [BASE_YEAR])[BASE_YEAR]
                    total_base_tkm = poly_project(numeric_years, total_series, [BASE_YEAR])[BASE_YEAR]

                    if total_base_tkm and total_base_tkm > 0:
                        hdt_base = 100.0 * (hdt_base_tkm / total_base_tkm)
                        # ldt_base is complement, but we’ll compute it after expansion
                    else:
                        raise ValueError("Total road freight tkm at base year is zero or NaN")

                    # Expand HDT share with CAGR (small CAGR → small movement; change YAML if you want bigger change)
                    hdt_expanded = expand_with_cagr(
                        hdt_base,
                        get_cagr(CAGR_VALUES, "Share per Mode - Heavy-Duty Trucks"),
                        BASE_YEAR, TARGET_YEARS, SCENARIOS
                    )

                    # Optional: fill any missing keys produced by the backend
                    if 'interpolate_or_extrapolate' in globals():
                        hdt_expanded = interpolate_or_extrapolate(hdt_expanded, TARGET_YEARS, SCENARIOS)

                    # LDT is complement each year
                    ldt_expanded = {str(BASE_YEAR): 100.0 - hdt_expanded[str(BASE_YEAR)]}
                    for year in TARGET_YEARS:
                        for scenario in SCENARIOS:
                            key = f"{year}_{scenario}"
                            ldt_expanded[key] = 100.0 - hdt_expanded[key]

                    #  Append with the CORRECT mapping (no swap!)
                    all_rows.append({
                        "Metric": "Share per Mode - Heavy-Duty Trucks",
                        **ldt_expanded, "Units": "% of Road Freight tkm"
                    })
                    all_rows.append({
                        "Metric": "Share per Mode - Light-Duty Trucks",
                        **hdt_expanded, "Units": "% of Road Freight tkm"
                    })

                except Exception as e:
                    print(f" Skipping {selected_country}: HDT/LDT shares error ({e})")


            except Exception as e:
                print(f" Skipping {selected_country}: Freight subsector shares error ({e})")


        except Exception as e:
            print(f" Skipping {selected_country}: Transport error ({e})")
            continue

        # ------- Final Energy Intensities -------
        # =====================================================

        try:
            # Generate dynamically expanded intensities (CAGR or constant)
            intensities_dict = generate_energy_intensities(
            selected_country=selected_country,
            BASE_YEAR=BASE_YEAR,
            TARGET_YEARS=TARGET_YEARS,
            SCENARIOS=SCENARIOS,
            CAGR_VALUES=CAGR_VALUES
        )

            if not isinstance(intensities_dict, dict) or not intensities_dict:
                raise ValueError("generate_energy_intensities returned empty or invalid dictionary")

            #print(f" Expanded {len(intensities_dict)} energy intensity metrics for {selected_country}")

        except Exception as e:
            print(f" Skipping {selected_country}: Intensities generation error ({e})")
            continue


        try:
            # Each key in intensities_dict already has full expansion (2020, 2030_B, 2050_EL...)
            for metric, expanded in intensities_dict.items():
                unit = units_dict.get(metric, "kWh/vkm")

                # Skip invalid or empty metrics
                if not isinstance(expanded, dict) or not expanded:
                    print(f" Skipping {metric}: Invalid or empty expansion")
                    continue

                # Debug info for transparency
                if any(abs(expanded.get("2030_Baseline", 0) - expanded.get("2020", 0)) > 1e-6 for _ in [0]):
                    source = "CAGR"
                else:
                    source = "constant"
                #print(f"   • {metric} → ({source})")

                # Append to results
                all_rows.append({
                    "Metric": metric,
                    **expanded,
                    "Units": unit
                })

        except Exception as e:
            print(f" Skipping {selected_country}: Error inserting intensities ({e})")
            continue


        # ------- Technology shares (base) -------
        try:
            (
                # LDV (7)
                technology_gasoline_ice_ldv, technology_diesel_ice_ldv, technology_lpg_ice_ldv,
                technology_bev_ldv, technology_fcev_ldv,
                technology_diesel_plugin_hybrid_ldv, technology_gasoline_plugin_hybrid_ldv,

                # Bus (4)
                technology_diesel_ice_bus, technology_bev_bus, technology_fcev_bus, technology_diesel_plugin_hybrid_bus,

                # 2&3W (2)
                technology_gasoline_ice_2_and_3w, technology_bev_two_three_wheeler,

                # Passenger Train (1)
                technology_fcev_passenger_train,

                # Passenger Plane (3)
                technology_kerosene_passenger_plane, technology_bev_passenger_plane, technology_fcev_passenger_plane,

                # LDT (4)
                technology_diesel_ice_ldt, technology_bev_ldt, technology_fcev_ldt, technology_diesel_plugin_hybrid_ldt,

                # HDT (4)
                technology_diesel_ice_hdt, technology_bev_hdt, technology_fcev_hdt, technology_diesel_plugin_hybrid_hdt,

                # Freight Train (1)
                technology_fcev_freight_train,

                # Freight Ship (5)
                technology_diesel_ice_freight_ship, technology_methanol_freight_ship, technology_ammonia_freight_ship,
                technology_bev_freight_ship, technology_fcev_freight_ship,

                # Freight Plane (1)
                technology_kerosene_freight_plane,

                # Passenger Ship (1)
                technology_diesel_passenger_ship,

                #biodiesel(6)
                bioethanol_in_road_gasoline,
                biodiesel_in_road_diesel,
                biodiesel_in_rail_diesel,
                biodiesel_in_internal_navigation_diesel,
                biokerosene_in_internal_aviation_fuel,
                ice_fuel_in_plugin_hybrid,
                 ) = share_technology()

        except Exception as e:
            print(f" Skipping {selected_country}: Technology shares error ({e})")
            continue

        # Direct electric passenger train share
        try:
            share_direct_elec_train = poly_project(
                share_years,
                [df_Share_of_Direct_Electric_Passenger_Train.loc[
                    df_Share_of_Direct_Electric_Passenger_Train["Countries List"] == selected_country,
                    str(y)
                ].values[0] if str(y) in df_Share_of_Direct_Electric_Passenger_Train.columns else np.nan for y in share_years],
                [BASE_YEAR] + TARGET_YEARS
            )
            share_direct_elec_train = {k: as_fraction(v) for k, v in share_direct_elec_train.items()}
            share_diesel_ice_train = {k: 1 - v for k, v in share_direct_elec_train.items()}
        except Exception as e:
            print(f" Skipping {selected_country}: Train share error ({e})")
            continue

        tech_base = {
            # LDV
            "Share of Technology - Gasoline ICE LDV": technology_gasoline_ice_ldv,
            "Share of Technology - Diesel ICE LDV": technology_diesel_ice_ldv,
            "Share of Technology - LPG ICE LDV": technology_lpg_ice_ldv,
            "Share of Technology - BEV LDV": technology_bev_ldv,
            "Share of Technology - FCEV LDV": technology_fcev_ldv,
            "Share of Technology - Diesel Plugin Hybrid LDV": technology_diesel_plugin_hybrid_ldv,
            "Share of Technology - Gasoline Plugin Hybrid LDV": technology_gasoline_plugin_hybrid_ldv,

            # Bus
            "Share of Technology - Diesel ICE Bus": technology_diesel_ice_bus,
            "Share of Technology - BEV Bus": technology_bev_bus,
            "Share of Technology - FCEV Bus": technology_fcev_bus,
            "Share of Technology - Diesel Plugin Hybrid Bus": technology_diesel_plugin_hybrid_bus,

            # 2&3W
            "Share of Technology - Gasoline ICE 2&3W": technology_gasoline_ice_2_and_3w,
            "Share of Technology - BEV 2&3W": technology_bev_two_three_wheeler,

            # Passenger Train
            "Share of Technology - Diesel ICE Passenger Train": share_diesel_ice_train[BASE_YEAR],
            "Share of Technology - Direct Electric Passenger Train": share_direct_elec_train[BASE_YEAR],
            "Share of Technology - FCEV Passenger Train": technology_fcev_passenger_train,

            # Passenger Plane
            "Share of Technology - Kerosene Passenger Plane": technology_kerosene_passenger_plane,
            "Share of Technology - BEV Passenger Plane": technology_bev_passenger_plane,
            "Share of Technology - FCEV Passenger Plane": technology_fcev_passenger_plane,

            # LDT
            "Share of Technology - Diesel ICE LDT": technology_diesel_ice_ldt,
            "Share of Technology - BEV LDT": technology_bev_ldt,
            "Share of Technology - FCEV LDT": technology_fcev_ldt,
            "Share of Technology - Diesel Plugin Hybrid LDT": technology_diesel_plugin_hybrid_ldt,

            # HDT
            "Share of Technology - Diesel ICE HDT": technology_diesel_ice_hdt,
            "Share of Technology - BEV HDT": technology_bev_hdt,
            "Share of Technology - FCEV HDT": technology_fcev_hdt,
            "Share of Technology - Diesel Plugin Hybrid HDT": technology_diesel_plugin_hybrid_hdt,

            # Freight Train
            "Share of Technology - Diesel ICE Freight Train": share_diesel_ice_train[BASE_YEAR],
            "Share of Technology - Direct Electric Freight Train": share_direct_elec_train[BASE_YEAR],
            "Share of Technology - FCEV Freight Train": technology_fcev_freight_train,

            # Freight Ship
            "Share of Technology - Diesel ICE Freight Ship": technology_diesel_ice_freight_ship,
            "Share of Technology - Methanol Freight Ship": technology_methanol_freight_ship,
            "Share of Technology - Ammonia Freight Ship": technology_ammonia_freight_ship,
            "Share of Technology - BEV Freight Ship": technology_bev_freight_ship,
            "Share of Technology - FCEV Freight Ship": technology_fcev_freight_ship,

            # Freight Plane
            "Share of Technology - Kerosene Freight Plane": technology_kerosene_freight_plane,

            # Passenger Ship
            "Share of Technology - Diesel Passenger Ship": technology_diesel_passenger_ship,
            "Share of Bioethanol in Road Gasoline": bioethanol_in_road_gasoline,
            "Share of Biodiesel in Road Diesel": biodiesel_in_road_diesel,
            "Share of Biodiesel in Rail Diesel": biodiesel_in_rail_diesel,
            "Share of Biodiesel in Internal Navigation Diesel": biodiesel_in_internal_navigation_diesel,
            "Share of Biokerosene in Internal Aviation Diesel": biokerosene_in_internal_aviation_fuel,
            "Share of ICE Fuel in Plugin Hybrid": ice_fuel_in_plugin_hybrid,
        }

        # ------- Technology overrides + interpolation -------
        tech_rows = []
        for metric in TECHNOLOGY_OVERRIDES.keys():
            row = {
                "Metric": metric,
                str(BASE_YEAR): tech_base.get(metric, np.nan),
                "Units": "% of km",
            }
            tech_rows.append(row)

        # Apply overrides and interpolate (2030/2050 direct, 2035–2045 interpolated)
        tech_rows = apply_technology_overrides(tech_rows, TARGET_YEARS, SCENARIOS, CAGR_VALUES)

        # Enforce constraints (warn if >100%)
        tech_rows = enforce_share_constraints(tech_rows)

        # Convert fractions (0.167 → 16.7%)
        df_tech = pd.DataFrame(tech_rows)
        for col in df_tech.columns:
            if col not in ["Metric", "Units"]:
                df_tech[col] = df_tech[col].apply(
                    lambda x: round(x * 100, 2) if pd.notnull(x) and isinstance(x, (int, float)) and x <= 1 else x
                )
        tech_rows = df_tech.to_dict("records")

        # Add to master list
        all_rows.extend(tech_rows)

        # ------- Other metrics -------
        other_metrics = {}

        # Expand and append non-duplicate metrics
        if other_metrics:
            for metric, metric_value in other_metrics.items():
                if "Load Factor" in metric:
                    unit = units_dict.get(metric, "t/vehicle")
                else:
                    unit = units_dict.get(metric, "kWh/vkm")
                expanded = expand_intensity(metric, metric_value, selected_country)

                all_rows.append({"Metric": metric, **expanded, "Units": unit})

        # ------- Save per country -------
        try:
            main_config = pd.DataFrame(all_rows)
            main_config = main_config.drop_duplicates(subset=["Metric"], keep="first")
            tech_mask = main_config["Metric"].str.startswith("Share of Technology - ", na=False)
            main_config.loc[tech_mask, "Units"] = "% of km"
            main_config = reorder_and_filter_columns(main_config, BASE_YEAR, TARGET_YEARS, SCENARIOS)

            output_file_path = os.path.join(base_output_dir, f'output_{selected_country}.xlsx')
            with pd.ExcelWriter(output_file_path, engine="openpyxl") as writer:
                main_config.to_excel(writer, index=False, sheet_name="Main_Transport")
            print(f"  Saved: {output_file_path}")
        except Exception as e:
            print(f" Skipping {selected_country}: Error saving Excel file ({e})")
            continue

if __name__ == "__main__":
    main()