
import os
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path

# === Imports from project libraries ===
from helpers import find_input_folder, load_country_specific_data, load_global_transport_data, get_transport_constants, interpolate_or_extrapolate, clean_column_headers, clean_missing_countries, generate_units_dictionary, reorder_and_filter_columns 
from build_macro_indicators import process_population_data, get_ssp_for_scenario, validate_scenarios_and_ssp
from build_share_subsectors import extract_country_transport_data, create_country_dfs, final_df as TRANSPORT_SUBSECTOR_FINAL
from build_share_mode import process_bus_share_data, share_of_two_Three
from build_load_factors import get_Load_factor_Car, Load_factor_Bus, Load_factor_two_three_occupancy, heavy_load_factor, medium_load_factor, load_factor
from build_energy_intensities import generate_energy_intensities, expand_intensity
from build_technology_share import Share_of_Direct_Electric_Passenger_Train, share_technology, TECHNOLOGY_OVERRIDES, enforce_share_constraints, apply_technology_overrides
from config_loader import load_transport_config
<<<<<<< HEAD
from build_macro_indicators import validate_scenarios_and_ssp
# === Constants DEFAULT VALUES ===
# TODO: @rakesh, can the user change this too?

# TODO. MAKE THIS A DICTIONARY
SSP_ORDER = [
    "SSP2", 
    "SSP2", 
    "SSP1"
    ]

#TODO: @Rakesh, check the scenarios logic
SCENARIOS = [
    "Baseline",
    "BAU", 
    "AT"] # a max of three scenarios are possible.

# map the scenario names with the corresponding SSP
validate_scenarios_and_ssp(SCENARIOS, SSP_ORDER)

TARGET_YEARS = [2035,2045,20250,2055]  # from 2030 up to 2055 in steps of 5 years possible. 


# todo: let us use csv. 

# === Transport assumptions file (user can change this) ===

BASE_YEAR = 2025  # Define the start year for the projections. 2020 by default. Years between 2020 and 2025 are available (via interpolation),

=======
from CAGR import poly_project, expand_with_cagr, expand_constant, as_fraction, get_cagr

# === Constants ===
BASE_YEAR = 2020  
SSP_ORDER = ["SSP2", "SSP2", "SSP1"]
SCENARIOS = ["Baseline", "Er", "RL"] 

validate_scenarios_and_ssp(SCENARIOS, SSP_ORDER)

TARGET_YEARS = [2030, 2035, 2040, 2045, 2050] 

# === Transport assumptions file ===
>>>>>>> main
TRANSPORT_CONFIG_FILE = "trans_config.xlsx"
TRANSPORT_CONFIG_PATH = Path(__file__).resolve().parent / TRANSPORT_CONFIG_FILE

print("\n===============================")
print("Running transport sector pipeline")
print(f"Transport assumptions file: {TRANSPORT_CONFIG_FILE}")
print("===============================\n")

devkopsys_countries = ["Republic of the Congo", "Egypt", "Ethiopia", "Ghana","Kenya","Namibia","Niger",
                       "Algeria","Argentina","Brazil","Chile","Colombia","Mexico","Peru","Venezuela",
                       "Morocco","Tunisia","Tanzania","Libya",
                       "Australia", "Canada", "China", "France", "Germany",  
                       "India", "Indonesia", "Italy", "Japan", "Mexico","Russia", "Saudi Arabia", 
                       "South Africa", "South Korea", "United Kingdom", "United States"]

<<<<<<< HEAD
selected_countries = ["Congo",
                       "Egypt",
                       "Ethiopia",
                       "Ghana",
                       "Kenya",
                       "Namibia",
                       "Niger",
                       #"Algeria",
                       "Morocco",
                       "Tunisia",
                       "Tanzania",
                       "South Africa",
                       # "Libya"
                       # "Argentina","Brazil","Chile","Colombia",,"Mexico",
                        ]
                            # "Namibia","Peru","Tunisia","Uruguay","Morocco","South Africa",
                            # "Angola","Benin","Botswana","Burkina Faso","Burundi","Cameroon",
                            # "Central African Republic","Chad","Comoros","Djibouti","Equatorial Guinea","Eritrea",
                            # "Ethiopia","Gabon","Gambia","Ghana","Guinea","Guinea Bissau","Kenya","Lesotho",
                            # "Liberia","Madagascar","Malawi","Mali","Mauritania","Mozambique","Namibia","Niger",
                            # "Rwanda","Senegal","Sierra Leone","Somalia","Sudan","Tanzania","Togo","Uganda",
                            # "Zambia","Zimbabwe","Seychelles","Cote D'Ivoire","Sao Tome and Principe",
                            # "South Sudan","Cabo Verde", "Congo", "Eswatini" ]
=======
countries_to_load = devkopsys_countries + ["default"] 
>>>>>>> main

TRANSPORT_CONFIG = load_transport_config(
<<<<<<< HEAD
    excel_path=Path(__file__).resolve().parent / TRANSPORT_CONFIG_FILE,
    countries=selected_countries,
=======
    excel_path=TRANSPORT_CONFIG_PATH,
    countries=countries_to_load,
>>>>>>> main
    scenarios=SCENARIOS
)

# Extract the Default values once
DEFAULT_VALUES = TRANSPORT_CONFIG.get("default", {})
if not DEFAULT_VALUES:
    print(" WARNING: No 'default' data found in trans_config.xlsx. Fallback logic might fail.")

def main(base_year=None, target_years=None, scenarios=None):
    # Use arguments if provided, else defaults
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
    TRANSPORT_DIR = Path(__file__).resolve().parent
    base_output_dir = TRANSPORT_DIR / "output_data" / f"DKS_{today_str}"
    base_output_dir.mkdir(parents=True, exist_ok=True)

    units_dict = generate_units_dictionary()

    # === Loop through countries ===
    for selected_country in selected_countries:
        print(f"\n🔹 Processing: {selected_country}")
        
        # === Load Data & Merge with Defaults ===
        try:
            country_values = TRANSPORT_CONFIG.get(selected_country, {})
            
            # Start with Defaults
            CAGR_VALUES = DEFAULT_VALUES.copy() 
            
            # Update with Country Specifics
            if country_values:
                CAGR_VALUES.update(country_values)
            
            if not CAGR_VALUES:
                raise ValueError(f"No data found for: {selected_country}")

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

            known_years = [2020, 2030, 2040, 2050] 
            all_years = [base_year] + target_years

            pop_values = {}
            for year in all_years:
                for scenario in scenarios:
                    ssp = get_ssp_for_scenario(
                        scenario=scenario,
                        scenarios=scenarios,
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

            # Add plain base year
            base_ssp = SSP_ORDER[0] 
            if str(base_year) in pop_df.columns:
                pop_values[str(base_year)] = float(pop_df.loc[base_ssp, str(base_year)])
            else:
                pop_values[str(base_year)] = pop_values[f"{base_year}_{scenarios[0]}"]

            population_row = {"Metric": "Population", **pop_values, "Units": "million"}
            all_rows = [population_row]

        except Exception as e:
            print(f" Skipping {selected_country}: Population error ({e})")
            continue

        # ------- Transport indicators -------
        try:
            subsector_df = TRANSPORT_SUBSECTOR_FINAL 
            country_dfs = create_country_dfs(subsector_df, [selected_country])
            country_key = f"df_{selected_country.replace(' ', '_')}"
            country_df = country_dfs.get(country_key)
            if country_df is None:
                raise Exception(f"Subsector data for {selected_country} not found")

            country_df = country_df.reset_index() 
            country_data, _ = extract_country_transport_data(selected_country, "SSP1", df_population, country_df)

            def val(name, year):
                y = str(year)
                candidates = [y] if '.' in y else [y, f"{y}.0"] 
                for col in candidates:
                    if name in country_data.index and col in country_data.columns:
                        try: return float(country_data.loc[name, col])
                        except Exception: pass
                return np.nan

            share_years = [
                c for c in country_data.columns
                if str(c).replace('.', '').isdigit()
                and not any(x in str(c) for x in ["Baseline", "RF", "EL"])
            ]
            
            # Use base_year variable instead of constant
            scenario_baseline = {
                "Mobility per capita - Passenger": poly_project(
                    share_years, [val('Mobility per capita - Passenger', y) for y in share_years], [base_year]
                )[base_year],

                "Load Factor - LDV": poly_project(
                    share_years,
                    [df_load_factor_car.loc[df_load_factor_car["Countries List"] == selected_country, str(y)].values[0] if str(y) in df_load_factor_car.columns else np.nan for y in share_years],
                    [base_year]
                )[base_year],

                "Load Factor - Bus": poly_project(
                    share_years,
                    [df_load_factor_bus.loc[df_load_factor_bus["Countries List"] == selected_country, str(y)].values[0] if str(y) in df_load_factor_bus.columns else np.nan for y in share_years],
                    [base_year]
                )[base_year],

                "Load Factor - 2&3W": poly_project(
                    share_years,
                    [df_load_factor_two_three_occupancy.loc[df_load_factor_two_three_occupancy["Countries List"] == selected_country, str(y)].values[0] if str(y) in df_load_factor_two_three_occupancy.columns else np.nan for y in share_years],
                    [base_year]
                )[base_year],

                "Load Factor - Passenger Train": (
                    poly_project(
                        share_years,
                        [df_load_factor_car.loc[df_load_factor_car["Countries List"] == selected_country, str(y)].values[0] if str(y) in df_load_factor_car.columns else np.nan for y in share_years],
                        [base_year]
                    )[base_year] * get_transport_constants('load_factor_multiplier', 'Passenger Train')
                ),
                "Load Factor - Passenger Plane": load_passenger_plane,
                "Load Factor - Freight Ship": load_freight_ship,
                "Load Factor - Passenger Ship": load_passenger_ship,
            }

            # --- Freight Load Factors ---
            ldt_base = poly_project(
                share_years,
                [df_medium_load_factor.loc[df_medium_load_factor["Countries List"] == selected_country, str(y)].values[0]
                if str(y) in df_medium_load_factor.columns else np.nan for y in share_years],
                [base_year]
            )[base_year]
            ldt_expanded = expand_constant(ldt_base, base_year, target_years, scenarios)

            hdt_base = poly_project(
                share_years,
                [df_heavy_load_factor.loc[df_heavy_load_factor["Countries List"] == selected_country, str(y)].values[0]
                if str(y) in df_heavy_load_factor.columns else np.nan for y in share_years],
                [base_year]
            )[base_year]
            hdt_expanded = expand_constant(hdt_base, base_year, target_years, scenarios)

            train_freight_base = hdt_base * get_transport_constants('load_factor_multiplier', 'Freight Train')
            train_freight_expanded = expand_constant(train_freight_base, base_year, target_years, scenarios)

            ship_freight_base = 508.0
            ship_freight_expanded = expand_constant(ship_freight_base, base_year, target_years, scenarios)

            all_rows.append({"Metric": "Load Factor - LDT", **ldt_expanded, "Units": "t/vehicle"})
            all_rows.append({"Metric": "Load Factor - HDT", **hdt_expanded, "Units": "t/vehicle"})
            all_rows.append({"Metric": "Load Factor - Freight Train", **train_freight_expanded, "Units": "t/vehicle"})
            all_rows.append({"Metric": "Load Factor - Freight Ship", **ship_freight_expanded, "Units": "t/vehicle"})

            # --- Subsector Shares ---
            try:
                rail_base = poly_project(share_years, [val("Rail Passenger %", y) for y in share_years], [base_year])[base_year]
                aviation_base = poly_project(share_years, [val("Aviation Passenger %", y) for y in share_years], [base_year])[base_year]
                if aviation_base is None or np.isnan(aviation_base): aviation_base = 1.12

                rail_expanded = expand_with_cagr(
                    rail_base,
                    get_cagr(CAGR_VALUES, "Share per Subsector - Rail Passenger = Train"),
                    base_year, target_years, scenarios
                )

                aviation_expanded = expand_with_cagr(
                    aviation_base,
                    get_cagr(CAGR_VALUES, "Share per Subsector - Aviation Passenger = Plane"),
                    base_year, target_years, scenarios
                )

                road_expanded = {}
                road_expanded[str(base_year)] = 100.0 - (rail_expanded[str(base_year)] + aviation_expanded[str(base_year)])
                for year in target_years:
                    for scenario in scenarios:
                        key = f"{year}_{scenario}"
                        road_expanded[key] = 100.0 - (rail_expanded[key] + aviation_expanded[key])

                # Normalize
                for year in [str(base_year)] + [f"{y}_{s}" for y in target_years for s in scenarios]:
                    total = rail_expanded.get(year, 0) + aviation_expanded.get(year, 0) + road_expanded.get(year, 0)
                    if abs(total - 100.0) > 1e-6 and total > 0:
                        scale = 100.0 / total
                        if year in rail_expanded: rail_expanded[year] *= scale
                        if year in aviation_expanded: aviation_expanded[year] *= scale
                        if year in road_expanded: road_expanded[year] *= scale

                all_rows.append({"Metric": "Share per Subsector - Rail Passenger = Train", **rail_expanded, "Units": "% of pkm"})
                all_rows.append({"Metric": "Share per Subsector - Aviation Passenger = Plane", **aviation_expanded, "Units": "% of pkm"})
                all_rows.append({"Metric": "Share per Subsector - Road Passenger", **road_expanded, "Units": "% of pkm"})

                mcp_expanded = expand_with_cagr(
                    scenario_baseline["Mobility per capita - Passenger"],
                    get_cagr(CAGR_VALUES, "Mobility per capita - Passenger"),
                    base_year, target_years, scenarios
                )
                all_rows.append({"Metric": "Mobility per capita - Passenger", **mcp_expanded, "Units": units_dict.get("Mobility per capita - Passenger", "pkm/p")})

            except Exception as e:
                print(f" Skipping {selected_country}: Subsector shares error ({e})")

            # --- Mode Shares ---
            try:
                bus_base = poly_project(share_years, [df_process_bus_share_data.loc[df_process_bus_share_data["Countries List"] == selected_country, str(y)].values[0] if str(y) in df_process_bus_share_data.columns else np.nan for y in share_years], [base_year])[base_year]
                two3w_base = poly_project(share_years, [df_share_two_three.loc[df_share_two_three["Countries List"] == selected_country, str(y)].values[0] if str(y) in df_share_two_three.columns else np.nan for y in share_years], [base_year])[base_year]
                ldv_base = 100.0 - (bus_base + two3w_base)

                bus_expanded = expand_with_cagr(bus_base, get_cagr(CAGR_VALUES, "Share per Mode - Bus"), base_year, target_years, scenarios)
                two3w_expanded = expand_with_cagr(two3w_base, get_cagr(CAGR_VALUES, "Share per Mode - 2&3W"), base_year, target_years, scenarios)

                ldv_expanded = {}
                ldv_expanded[str(base_year)] = ldv_base
                for year in target_years:
                    for scenario in scenarios:
                        key = f"{year}_{scenario}"
                        ldv_expanded[key] = 100.0 - (bus_expanded[key] + two3w_expanded[key])

                # Normalize
                for year in [str(base_year)] + [f"{y}_{s}" for y in target_years for s in scenarios]:
                    total = (bus_expanded.get(year, 0) + two3w_expanded.get(year, 0) + ldv_expanded.get(year, 0))
                    if abs(total - 100.0) > 1e-6 and total > 0:
                        scale = 100.0 / total
                        if year in bus_expanded: bus_expanded[year] *= scale
                        if year in two3w_expanded: two3w_expanded[year] *= scale
                        if year in ldv_expanded: ldv_expanded[year] *= scale

                all_rows.append({"Metric": "Share per Mode - Bus", **bus_expanded, "Units": "% of Road pkm"})
                all_rows.append({"Metric": "Share per Mode - 2&3W", **two3w_expanded, "Units": "% of Road pkm"})
                all_rows.append({"Metric": "Share per Mode - LDV", **ldv_expanded, "Units": "% of Road pkm"})

            except Exception as e:
                print(f" Skipping {selected_country}: Mode shares error ({e})")

            # --- Load Factors ---
            try:
                ldv_base = poly_project(share_years, [df_load_factor_car.loc[df_load_factor_car["Countries List"] == selected_country, str(y)].values[0] if str(y) in df_load_factor_car.columns else np.nan for y in share_years], [base_year])[base_year]
                ldv_expanded = expand_constant(ldv_base, base_year, target_years, scenarios)

                bus_base = poly_project(share_years, [df_load_factor_bus.loc[df_load_factor_bus["Countries List"] == selected_country, str(y)].values[0] if str(y) in df_load_factor_bus.columns else np.nan for y in share_years], [base_year])[base_year]
                bus_expanded = expand_constant(bus_base, base_year, target_years, scenarios)

                two3w_base = poly_project(share_years, [df_load_factor_two_three_occupancy.loc[df_load_factor_two_three_occupancy["Countries List"] == selected_country, str(y)].values[0] if str(y) in df_load_factor_two_three_occupancy.columns else np.nan for y in share_years], [base_year])[base_year]
                two3w_expanded = expand_constant(two3w_base, base_year, target_years, scenarios)

                train_base = ldv_base * get_transport_constants('load_factor_multiplier', 'Passenger Train')
                train_expanded = expand_constant(train_base, base_year, target_years, scenarios)

                plane_base = 101.0
                plane_expanded = expand_constant(plane_base, base_year, target_years, scenarios)

                all_rows.append({"Metric": "Load Factor - LDV", **ldv_expanded, "Units": "p/vehicle"})
                all_rows.append({"Metric": "Load Factor - Bus", **bus_expanded, "Units": "p/vehicle"})
                all_rows.append({"Metric": "Load Factor - 2&3W", **two3w_expanded, "Units": "p/vehicle"})
                all_rows.append({"Metric": "Load Factor - Passenger Train", **train_expanded, "Units": "p/vehicle"})
                all_rows.append({"Metric": "Load Factor - Passenger Plane", **plane_expanded, "Units": "p/vehicle"})
                
                ship_base = load_passenger_ship
                ship_expanded = expand_constant(ship_base, base_year, target_years, scenarios)
                all_rows.append({"Metric": "Load Factor - Passenger Ship", **ship_expanded, "Units": "p/vehicle"})

            except Exception as e:
                print(f" Skipping {selected_country}: Load factors error ({e})")

            # --- Freight ---
            try:
                freight_base = poly_project(share_years, [val("Mobility per capita - Freight", y) for y in share_years], [base_year])[base_year]
                freight_expanded = expand_with_cagr(freight_base, get_cagr(CAGR_VALUES, "Mobility per capita - Freight"), base_year, target_years, scenarios)
                all_rows.append({"Metric": "Mobility per capita - Freight", **freight_expanded, "Units": "tkm/p"})

                road_freight_base = 75.0
                ship_freight_base = 3.70
                rail_freight_base = 100.0 - (road_freight_base + ship_freight_base)

                rail_freight_expanded = expand_with_cagr(rail_freight_base, get_cagr(CAGR_VALUES, "Share per Subsector - Rail Freight = Train"), base_year, target_years, scenarios)
                ship_freight_expanded = expand_with_cagr(ship_freight_base, get_cagr(CAGR_VALUES, "Share per Subsector - Navigation Freight = Ship"), base_year, target_years, scenarios)

                road_freight_expanded = {}
                road_freight_expanded[str(base_year)] = road_freight_base
                for year in target_years:
                    for scenario in scenarios:
                        key = f"{year}_{scenario}"
                        road_freight_expanded[key] = 100.0 - (rail_freight_expanded[key] + ship_freight_expanded[key])

                # Normalize
                for year in [str(base_year)] + [f"{y}_{s}" for y in target_years for s in scenarios]:
                    total = (rail_freight_expanded.get(year, 0) + ship_freight_expanded.get(year, 0) + road_freight_expanded.get(year, 0))
                    if abs(total - 100.0) > 1e-6 and total > 0:
                        scale = 100.0 / total
                        if year in rail_freight_expanded: rail_freight_expanded[year] *= scale
                        if year in ship_freight_expanded: ship_freight_expanded[year] *= scale
                        if year in road_freight_expanded: road_freight_expanded[year] *= scale

                all_rows.append({"Metric": "Share per Subsector - Road Freight", **road_freight_expanded, "Units": "% of tkm"})
                all_rows.append({"Metric": "Share per Subsector - Rail Freight = Train", **rail_freight_expanded, "Units": "% of tkm"})
                all_rows.append({"Metric": "Share per Subsector - Navigation Freight = Ship", **ship_freight_expanded, "Units": "% of tkm"})

                # --- Freight Trucks (HDT vs LDT) ---
                try:
                    numeric_years = sorted({int(float(c)) for c in country_data.columns if str(c).replace('.', '').isdigit() and not any(x in str(c) for x in ["Baseline", "RF", "EL"])})
                    hdt_series = [val("Road Freight - Heavy-Duty Trucks", y) for y in numeric_years]
                    total_series = [val("Road Freight", y) for y in numeric_years]

                    hdt_base_tkm = poly_project(numeric_years, hdt_series, [base_year])[base_year]
                    total_base_tkm = poly_project(numeric_years, total_series, [base_year])[base_year]

                    if total_base_tkm and total_base_tkm > 0:
                        hdt_base = 100.0 * (hdt_base_tkm / total_base_tkm)
                    else:
                        raise ValueError("Total road freight tkm at base year is zero or NaN")

                    hdt_expanded = expand_with_cagr(hdt_base, get_cagr(CAGR_VALUES, "Share per Mode - Heavy-Duty Trucks"), base_year, target_years, scenarios)
                    
                    if 'interpolate_or_extrapolate' in globals():
                        hdt_expanded = interpolate_or_extrapolate(hdt_expanded, target_years, scenarios)

                    ldt_expanded = {str(base_year): 100.0 - hdt_expanded[str(base_year)]}
                    for year in target_years:
                        for scenario in scenarios:
                            key = f"{year}_{scenario}"
                            ldt_expanded[key] = 100.0 - hdt_expanded[key]

                    all_rows.append({"Metric": "Share per Mode - Heavy-Duty Trucks", **hdt_expanded, "Units": "% of Road Freight tkm"})
                    all_rows.append({"Metric": "Share per Mode - Light-Duty Trucks", **ldt_expanded, "Units": "% of Road Freight tkm"})

                except Exception as e:
                    print(f" Skipping {selected_country}: HDT/LDT shares error ({e})")

            except Exception as e:
                print(f" Skipping {selected_country}: Freight subsector shares error ({e})")

        except Exception as e:
            print(f" Skipping {selected_country}: Transport error ({e})")
            continue
        
        # ==============================================================================
        # <--- INSERT THE NEW CODE BLOCK HERE (International Aviation & Maritime) --->
        # ==============================================================================
        try:
            # 1. Maritime: Load Total Energy directly (converted from Mtoe to TWh in Excel)
            maritime_energy_base = CAGR_VALUES.get("Total Energy - Int. Maritime", {}).get(base_year, 2477.0)
            maritime_energy_expanded = expand_with_cagr(
                maritime_energy_base,
                get_cagr(CAGR_VALUES, "Total Energy - Int. Maritime"),
                base_year, target_years, scenarios
            )
            all_rows.append({"Metric": "Total Energy - Int. Maritime", **maritime_energy_expanded, "Units": "TWh"})

            # 2. Aviation: Load Activity Index and Efficiency Index
            av_act_base = CAGR_VALUES.get("Activity Index - Int. Aviation", {}).get(base_year, 1.0)
            av_act_expanded = expand_with_cagr(
                av_act_base,
                get_cagr(CAGR_VALUES, "Activity Index - Int. Aviation"),
                base_year, target_years, scenarios
            )
            all_rows.append({"Metric": "Activity Index - Int. Aviation", **av_act_expanded, "Units": "Index (2020=1.0)"})

            av_eff_base = CAGR_VALUES.get("Efficiency Index - Int. Aviation", {}).get(base_year, 1.0)
            av_eff_expanded = expand_with_cagr(
                av_eff_base,
                get_cagr(CAGR_VALUES, "Efficiency Index - Int. Aviation"),
                base_year, target_years, scenarios
            )
            all_rows.append({"Metric": "Efficiency Index - Int. Aviation", **av_eff_expanded, "Units": "Index (2020=1.0)"})

            # 3. Technology Shares
            intl_tech_vars = [
                "Share - Int. Aviation E-fuel",
                "Share - Int. Maritime Ammonia",
                "Share - Int. Maritime E-fuel"
            ]

            for tech in intl_tech_vars:
                t_base = CAGR_VALUES.get(tech, {}).get(base_year, 0.0)
                t_expanded = expand_with_cagr(
                    t_base,
                    get_cagr(CAGR_VALUES, tech),
                    base_year, target_years, scenarios
                )
                all_rows.append({"Metric": tech, **t_expanded, "Units": "Fraction"})

        except Exception as e:
            print(f" Skipping International Bunkers for {selected_country}: {e}")
        # ==============================================================================
        # <--- END OF INSERTION --->
        # ==============================================================================

        # ------- Final Energy Intensities -------
        try:
            # === FIX 2: Pass 'target_years' (the argument) instead of global 'TARGET_YEARS' ===
            intensities_dict = generate_energy_intensities(
                selected_country=selected_country,
                BASE_YEAR=base_year,
                TARGET_YEARS=target_years,
                SCENARIOS=scenarios,
                CAGR_VALUES=CAGR_VALUES
            )

            if not isinstance(intensities_dict, dict) or not intensities_dict:
                raise ValueError("generate_energy_intensities returned empty or invalid dictionary")

            for metric, expanded in intensities_dict.items():
                unit = units_dict.get(metric, "kWh/vkm")
                if not isinstance(expanded, dict) or not expanded:
                    continue
                all_rows.append({"Metric": metric, **expanded, "Units": unit})

        except Exception as e:
            print(f" Skipping {selected_country}: Intensities generation error ({e})")
            continue

        # ------- Technology shares -------
        try:
            (technology_gasoline_ice_ldv, technology_diesel_ice_ldv, technology_lpg_ice_ldv,
             technology_bev_ldv, technology_fcev_ldv, technology_diesel_plugin_hybrid_ldv, technology_gasoline_plugin_hybrid_ldv,
             technology_diesel_ice_bus, technology_bev_bus, technology_fcev_bus, technology_diesel_plugin_hybrid_bus,
             technology_gasoline_ice_2_and_3w, technology_bev_two_three_wheeler,
             technology_fcev_passenger_train,
             technology_kerosene_passenger_plane, technology_bev_passenger_plane, technology_fcev_passenger_plane,
             technology_diesel_ice_ldt, technology_bev_ldt, technology_fcev_ldt, technology_diesel_plugin_hybrid_ldt,
             technology_diesel_ice_hdt, technology_bev_hdt, technology_fcev_hdt, technology_diesel_plugin_hybrid_hdt,
             technology_fcev_freight_train,
             technology_diesel_ice_freight_ship, technology_methanol_freight_ship, technology_ammonia_freight_ship, technology_bev_freight_ship, technology_fcev_freight_ship,
             technology_kerosene_freight_plane,
             technology_diesel_passenger_ship,
             bioethanol_in_road_gasoline, biodiesel_in_road_diesel, biodiesel_in_rail_diesel, biodiesel_in_internal_navigation_diesel, biokerosene_in_internal_aviation_fuel, ice_fuel_in_plugin_hybrid
             ) = share_technology()
        except Exception as e:
            print(f" Skipping {selected_country}: Technology shares error ({e})")
            continue

        try:
            share_direct_elec_train = poly_project(
                share_years,
                [df_Share_of_Direct_Electric_Passenger_Train.loc[df_Share_of_Direct_Electric_Passenger_Train["Countries List"] == selected_country, str(y)].values[0] if str(y) in df_Share_of_Direct_Electric_Passenger_Train.columns else np.nan for y in share_years],
                [base_year] + target_years
            )
            share_direct_elec_train = {k: as_fraction(v) for k, v in share_direct_elec_train.items()}
            share_diesel_ice_train = {k: 1 - v for k, v in share_direct_elec_train.items()}
        except Exception as e:
            print(f" Skipping {selected_country}: Train share error ({e})")
            continue

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
            "Share of Technology - Diesel ICE Passenger Train": share_diesel_ice_train[base_year],
            "Share of Technology - Direct Electric Passenger Train": share_direct_elec_train[base_year],
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
            "Share of Technology - Diesel ICE Freight Train": share_diesel_ice_train[base_year],
            "Share of Technology - Direct Electric Freight Train": share_direct_elec_train[base_year],
            "Share of Technology - FCEV Freight Train": technology_fcev_freight_train,
            "Share of Technology - Diesel ICE Freight Ship": technology_diesel_ice_freight_ship,
            "Share of Technology - Methanol Freight Ship": technology_methanol_freight_ship,
            "Share of Technology - Ammonia Freight Ship": technology_ammonia_freight_ship,
            "Share of Technology - BEV Freight Ship": technology_bev_freight_ship,
            "Share of Technology - FCEV Freight Ship": technology_fcev_freight_ship,
            "Share of Technology - Kerosene Freight Plane": technology_kerosene_freight_plane,
            "Share of Technology - Diesel Passenger Ship": technology_diesel_passenger_ship,
            "Share of Bioethanol in Road Gasoline": bioethanol_in_road_gasoline,
            "Share of Biodiesel in Road Diesel": biodiesel_in_road_diesel,
            "Share of Biodiesel in Rail Diesel": biodiesel_in_rail_diesel,
            "Share of Biodiesel in Internal Navigation Diesel": biodiesel_in_internal_navigation_diesel,
            "Share of Biokerosene in Internal Aviation Diesel": biokerosene_in_internal_aviation_fuel,
            "Share of ICE Fuel in Plugin Hybrid": ice_fuel_in_plugin_hybrid,
        }

        tech_rows = []
        for metric in TECHNOLOGY_OVERRIDES.keys():
            row = {"Metric": metric, str(base_year): tech_base.get(metric, np.nan), "Units": "% of km"}
            tech_rows.append(row)

        tech_rows = apply_technology_overrides(tech_rows, target_years, scenarios, CAGR_VALUES)
        tech_rows = enforce_share_constraints(tech_rows)

        df_tech = pd.DataFrame(tech_rows)
        for col in df_tech.columns:
            if col not in ["Metric", "Units"]:
                df_tech[col] = df_tech[col].apply(lambda x: round(x * 100, 2) if pd.notnull(x) and isinstance(x, (int, float)) and x <= 1 else x)
        tech_rows = df_tech.to_dict("records")
        all_rows.extend(tech_rows)

        other_metrics = {}
        if other_metrics:
            for metric, metric_value in other_metrics.items():
                unit = units_dict.get(metric, "kWh/vkm" if "Load Factor" not in metric else "t/vehicle")
                expanded = expand_intensity(metric, metric_value, selected_country)
                all_rows.append({"Metric": metric, **expanded, "Units": unit})

        try:
            main_config = pd.DataFrame(all_rows)
            main_config = main_config.drop_duplicates(subset=["Metric"], keep="first")
            tech_mask = main_config["Metric"].str.startswith("Share of Technology - ", na=False)
            main_config.loc[tech_mask, "Units"] = "% of km"
            
            # === FIX 3: Pass arguments to reorder function too ===
            main_config = reorder_and_filter_columns(main_config, base_year, target_years, scenarios)

            output_file_path = os.path.join(base_output_dir, f'output_{selected_country}.xlsx')
            with pd.ExcelWriter(output_file_path, engine="openpyxl") as writer:
                main_config.to_excel(writer, index=False, sheet_name="Main_Transport")
            print(f"  Saved: {output_file_path}")
        except Exception as e:
            print(f" Skipping {selected_country}: Error saving Excel file ({e})")
            continue

if __name__ == "__main__":
    main()