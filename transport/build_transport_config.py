
import os
import helpers
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
from build_technology_share import Share_of_Direct_Electric_Passenger_Train, share_technology, TECHNOLOGY_OVERRIDES, enforce_share_constraints, apply_technology_overrides, get_unsd_bunker_fuel_shares
from build_CAGR import poly_project, expand_with_cagr, expand_constant, as_fraction, get_cagr, apply_load_factor
from helpers import refresh_unsd_master_data, unsd_global_output, check_technology_groups, tech_groups, get_interpolated_value, unsd_input_folder, load_transport_config, extract_config_data

# === Constants ===
BASE_YEAR = 2020  
SSP_ORDER = ["SSP2", "SSP2", "SSP1"]

SCENARIOS = ["BAU", "Progressive", "Optimistic"]

validate_scenarios_and_ssp(SCENARIOS, SSP_ORDER)

TARGET_YEARS = helpers.DEFAULT_TARGET_YEARS

# === Transport assumptions file ===
transport_config_file = "trans_config.csv"
transport_config_path = Path(__file__).resolve().parent / transport_config_file

print("\n===============================")
print("Running transport sector pipeline")
print(f"Transport assumptions file: {transport_config_file}")
print("===============================\n")

countries_to_process = ["Morocco","Egypt","South Africa"]
                       #"Republic of the Congo", "Egypt", "Ethiopia", "Ghana","Kenya","Namibia","Nigeria"]
                       #"Algeria","Argentina","Brazil","Chile","Colombia","Mexico","Peru","Venezuela",
                       #"Morocco","Tunisia","Tanzania","Libya",
                       #"Australia", "Canada", "China", "France", "Germany",  
                       #"India", "Indonesia", "Italy", "Japan", "Mexico","Russia", "Saudi Arabia", 
                       #"South Africa", "South Korea", "United Kingdom", "United States of America"]

countries_to_load = countries_to_process + ["default"] 

transport_config = load_transport_config(
    excel_path=transport_config_path,
    countries=countries_to_load,
    scenarios=SCENARIOS
)

# Extract the Default values once
DEFAULT_VALUES, DEFAULT_ASSUMPTION_TYPES = extract_config_data(transport_config, "default")
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
    TRANSPORT_DIR = Path(__file__).resolve().parent
    # Use the configuration file name as the folder name
    base_output_dir = TRANSPORT_DIR / "output_data" / "country_parameters"
    
    base_output_dir.mkdir(parents=True, exist_ok=True)

    units_dict = generate_units_dictionary()

    # === Loop through countries ===
    for selected_country in countries_to_process:
        print(f"\n>> Processing: {selected_country}")
        all_rows = []
        # === Load Data & Merge with Defaults ===
        # === Load Data & Merge with Defaults ===
        try:
            country_values, country_types = extract_config_data(transport_config, selected_country)

            # --- FIX: Clean NaN values so they don't overwrite defaults ---
            country_values = {k: ({sk: sv for sk, sv in v.items() if pd.notna(sv)} if isinstance(v, dict) else v) 
                              for k, v in country_values.items() if pd.notna(v)}
            # Also clean the types
            country_types = {k: v for k, v in country_types.items() if pd.notna(v)}

            cagr_values = DEFAULT_VALUES.copy()
            assumption_types = DEFAULT_ASSUMPTION_TYPES.copy()
            
            # Deep update to merge year-by-year 
            for k, v in country_values.items():
                if k in cagr_values and isinstance(cagr_values[k], dict) and isinstance(v, dict):
                    cagr_values[k].update(v)
                else:
                    cagr_values[k] = v
            
            # Update types (Target vs CAGR)
            assumption_types.update(country_types)

        except Exception as e:
            print(f" Error preparing configuration for {selected_country}: {e}")
            continue

        # ------- Population using CAGR from config -------

        try:
            # Get base year population from dataset (still needed)
            dfs_country_spe = load_country_specific_data(find_input_folder())
            df_population = process_population_data(dfs_country_spe)

            pop_df = df_population.loc[selected_country]

            if "Unit" in pop_df.columns:
                pop_df = pop_df.drop(columns=["Unit"])

            # Get base year value
            base_ssp = SSP_ORDER[0]
            pop_base = get_interpolated_value(pop_df, base_ssp, base_year)
            # Check if Population CAGR exists in config
            if "Population" in cagr_values:

                pop_expanded = expand_with_cagr(
                    pop_base,
                    get_cagr(cagr_values, "Population"),
                    base_year,
                    target_years,
                    scenarios
                )

                all_rows.append({
                    "Metric": "Population",
                    **pop_expanded,
                    "Units": "million"
                })

            else:
                # Fallback to old SSP logic if CAGR not provided
                print("Population Growth rate not found in config using SSP data as fallback")

                pop_values = {}

                for year in [base_year] + target_years:
                    for scenario in scenarios:
                        ssp = get_ssp_for_scenario(scenario, scenarios, SSP_ORDER)
                        value = get_interpolated_value(pop_df, ssp, year)
                        pop_values[f"{year}_{scenario}"] = value

                pop_values[str(base_year)] = pop_base

                all_rows.append({
                    "Metric": "Population",
                    **pop_values,
                    "Units": "million"
                })

        except Exception as e:
            print(f"Skipping {selected_country}: Population error ({e})")
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
                and not any(x in str(c) for x in scenarios)
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
            }

            # --- Freight Load Factors ---
            ldt_base = poly_project(
                share_years,
                [df_medium_load_factor.loc[df_medium_load_factor["Countries List"] == selected_country, str(y)].values[0]
                if str(y) in df_medium_load_factor.columns else np.nan for y in share_years],
                [base_year]
            )[base_year]
            ldt_expanded = apply_load_factor(
                "Load Factor - LDT",
                ldt_base,
                cagr_values,
                assumption_types,
                base_year,
                target_years,
                scenarios
            )

            hdt_base = poly_project(
                share_years,
                [df_heavy_load_factor.loc[df_heavy_load_factor["Countries List"] == selected_country, str(y)].values[0]
                if str(y) in df_heavy_load_factor.columns else np.nan for y in share_years],
                [base_year]
            )[base_year]
            hdt_expanded = apply_load_factor(
                "Load Factor - HDT",
                hdt_base,
                cagr_values,
                assumption_types,
                base_year,
                target_years,
                scenarios
            )
            train_freight_base = hdt_base * get_transport_constants('load_factor_multiplier', 'Freight Train')
            train_freight_expanded = expand_constant(train_freight_base, base_year, target_years, scenarios)

            ship_freight_base = 508.0
            ship_freight_expanded = apply_load_factor(
                "Load Factor - Freight Ship",
                ship_freight_base,
                cagr_values,
                assumption_types,
                base_year,
                target_years,
                scenarios
            )

            all_rows.append({"Metric": "Load Factor - LDT", **ldt_expanded, "Units": "t/vehicle"})
            all_rows.append({"Metric": "Load Factor - HDT", **hdt_expanded, "Units": "t/vehicle"})
            all_rows.append({"Metric": "Load Factor - Freight Train", **train_freight_expanded, "Units": "t/vehicle"})
            all_rows.append({"Metric": "Load Factor - Freight Ship", **ship_freight_expanded, "Units": "t/vehicle"})

            # --- Subsector Shares ---
            try:
                # 1. Calculate Base Year Values
                rail_base = poly_project(share_years, [val("Rail Passenger %", y) for y in share_years], [base_year])[base_year]
                
                aviation_base = poly_project(share_years, [val("Aviation Passenger %", y) for y in share_years], [base_year])[base_year]
                if aviation_base is None or np.isnan(aviation_base): aviation_base = 1.12 # Default fallback

                # 2. Expand Futures with CAGR
                rail_expanded = expand_with_cagr(
                    rail_base,
                    get_cagr(cagr_values, "Share per Subsector - Rail Passenger = Train"),
                    base_year, target_years, scenarios
                )

                aviation_expanded = expand_with_cagr(
                    aviation_base,
                    get_cagr(cagr_values, "Share per Subsector - Aviation Passenger = Plane"),
                    base_year, target_years, scenarios
                )

                # 3. Calculate Road (Residual: 100 - others)
                road_expanded = {}
                # Base year residual
                road_expanded[str(base_year)] = 100.0 - (
                    rail_expanded[str(base_year)] + 
                    aviation_expanded[str(base_year)]
                )

                # Future years residual
                for year in target_years:
                    for scenario in scenarios:
                        key = f"{year}_{scenario}"
                        road_expanded[key] = 100.0 - (
                            rail_expanded.get(key, 0) + 
                            aviation_expanded.get(key, 0)
                        )

                # 4. Normalize (Ensure sum = 100%)
                for year in [str(base_year)] + [f"{y}_{s}" for y in target_years for s in scenarios]:
                    total = (rail_expanded.get(year, 0) + 
                             aviation_expanded.get(year, 0) + 
                             road_expanded.get(year, 0))
                    
                    if abs(total - 100.0) > 1e-6 and total > 0:
                        scale = 100.0 / total
                        if year in rail_expanded: rail_expanded[year] *= scale
                        if year in aviation_expanded: aviation_expanded[year] *= scale
                        if year in road_expanded: road_expanded[year] *= scale

                # 5. Append Rows
                all_rows.append({"Metric": "Share per Subsector - Rail Passenger = Train", **rail_expanded, "Units": "% of pkm"})
                all_rows.append({"Metric": "Share per Subsector - Aviation Passenger = Plane", **aviation_expanded, "Units": "% of pkm"})
                all_rows.append({"Metric": "Share per Subsector - Road Passenger", **road_expanded, "Units": "% of pkm"})

                mcp_expanded = expand_with_cagr(
                    scenario_baseline["Mobility per capita - Passenger"],
                    get_cagr(cagr_values, "Mobility per capita - Passenger"),
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

                bus_expanded = expand_with_cagr(bus_base, get_cagr(cagr_values, "Share per Mode - Bus"), base_year, target_years, scenarios)
                two3w_expanded = expand_with_cagr(two3w_base, get_cagr(cagr_values, "Share per Mode - 2&3W"), base_year, target_years, scenarios)

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
                ldv_expanded = apply_load_factor(
                        "Load Factor - LDV",
                        ldv_base,
                        cagr_values,
                        assumption_types,
                        base_year,
                        target_years,
                        scenarios
                    )
                
                bus_base = poly_project(share_years, [df_load_factor_bus.loc[df_load_factor_bus["Countries List"] == selected_country, str(y)].values[0] if str(y) in df_load_factor_bus.columns else np.nan for y in share_years], [base_year])[base_year]
                bus_expanded = apply_load_factor(
                        "Load Factor - Bus",
                        bus_base,
                        cagr_values,
                        assumption_types,
                        base_year,
                        target_years,
                        scenarios
                    )

                two3w_base = poly_project(share_years, [df_load_factor_two_three_occupancy.loc[df_load_factor_two_three_occupancy["Countries List"] == selected_country, str(y)].values[0] if str(y) in df_load_factor_two_three_occupancy.columns else np.nan for y in share_years], [base_year])[base_year]
                two3w_expanded = apply_load_factor(
                        "Load Factor - 2&3W",
                        two3w_base,
                        cagr_values,
                        assumption_types,
                        base_year,
                        target_years,
                        scenarios
                    )

                train_base = ldv_base * get_transport_constants('load_factor_multiplier', 'Passenger Train')
                train_expanded = apply_load_factor(
                    "Load Factor - Passenger Train",
                    train_base,
                    cagr_values,
                    assumption_types,
                    base_year,
                    target_years,
                    scenarios
                )

                plane_base = 101.0
                plane_expanded = apply_load_factor(
                    "Load Factor - Passenger Plane",
                    plane_base,
                    cagr_values,
                    assumption_types,
                    base_year,
                    target_years,
                    scenarios
                )

                all_rows.append({"Metric": "Load Factor - LDV", **ldv_expanded, "Units": "p/vehicle"})
                all_rows.append({"Metric": "Load Factor - Bus", **bus_expanded, "Units": "p/vehicle"})
                all_rows.append({"Metric": "Load Factor - 2&3W", **two3w_expanded, "Units": "p/vehicle"})
                all_rows.append({"Metric": "Load Factor - Passenger Train", **train_expanded, "Units": "p/vehicle"})
                all_rows.append({"Metric": "Load Factor - Passenger Plane", **plane_expanded, "Units": "p/vehicle"})

            except Exception as e:
                print(f" Skipping {selected_country}: Load factors error ({e})")

            # --- Freight ---
            try:
                freight_base = poly_project(share_years, [val("Mobility per capita - Freight", y) for y in share_years], [base_year])[base_year]
                freight_expanded = expand_with_cagr(freight_base, get_cagr(cagr_values, "Mobility per capita - Freight"), base_year, target_years, scenarios)
                all_rows.append({"Metric": "Mobility per capita - Freight", **freight_expanded, "Units": "tkm/p"})

                road_freight_base = 75.0
                ship_freight_base = 3.70
                rail_freight_base = 100.0 - (road_freight_base + ship_freight_base)

                rail_freight_expanded = expand_with_cagr(rail_freight_base, get_cagr(cagr_values, "Share per Subsector - Rail Freight = Train"), base_year, target_years, scenarios)
                ship_freight_expanded = expand_with_cagr(ship_freight_base, get_cagr(cagr_values, "Share per Subsector - Navigation Freight = Ship"), base_year, target_years, scenarios)


                road_freight_expanded = {}
                road_freight_expanded[str(base_year)] = road_freight_base
                for year in target_years:
                    for scenario in scenarios:
                        key = f"{year}_{scenario}"
                        road_freight_expanded[key] = 100.0 - rail_freight_expanded[key] - ship_freight_expanded[key]

                # Normalize
                for year in [str(base_year)] + [f"{y}_{s}" for y in target_years for s in scenarios]:
                    total = (
                        rail_freight_expanded.get(year, 0)
                        + road_freight_expanded.get(year, 0)
                        + ship_freight_expanded.get(year, 0)
                    )
                    if abs(total - 100.0) > 1e-6 and total > 0:
                        scale = 100.0 / total
                        if year in rail_freight_expanded: rail_freight_expanded[year] *= scale
                        if year in road_freight_expanded: road_freight_expanded[year] *= scale
                        if year in ship_freight_expanded: ship_freight_expanded[year] *= scale

                all_rows.append({"Metric": "Share per Subsector - Road Freight", **road_freight_expanded, "Units": "% of tkm"})
                all_rows.append({"Metric": "Share per Subsector - Rail Freight = Train", **rail_freight_expanded, "Units": "% of tkm"})
                all_rows.append({"Metric": "Share per Subsector - Navigation Freight = Ship", **ship_freight_expanded, "Units": "% of tkm"})
                # --- Freight Trucks (HDT vs LDT) ---
                try:
                    numeric_years = sorted({int(float(c)) for c in country_data.columns if str(c).replace('.', '').isdigit() and not any(x in str(c) for x in scenarios)})
                    hdt_series = [val("Road Freight - Heavy-Duty Trucks", y) for y in numeric_years]
                    total_series = [val("Road Freight", y) for y in numeric_years]

                    hdt_base_tkm = poly_project(numeric_years, hdt_series, [base_year])[base_year]
                    total_base_tkm = poly_project(numeric_years, total_series, [base_year])[base_year]

                    if total_base_tkm and total_base_tkm > 0:
                        hdt_base = 100.0 * (hdt_base_tkm / total_base_tkm)
                    else:
                        raise ValueError("Total road freight tkm at base year is zero or NaN")

                    hdt_expanded = expand_with_cagr(hdt_base, get_cagr(cagr_values, "Share per Mode - HDT"), base_year, target_years, scenarios)
                    
                    if 'interpolate_or_extrapolate' in globals():
                        hdt_expanded = interpolate_or_extrapolate(hdt_expanded, target_years, scenarios)

                    ldt_expanded = {str(base_year): 100.0 - hdt_expanded[str(base_year)]}
                    for year in target_years:
                        for scenario in scenarios:
                            key = f"{year}_{scenario}"
                            ldt_expanded[key] = 100.0 - hdt_expanded[key]

                    all_rows.append({"Metric": "Share per Mode - HDT", **ldt_expanded, "Units": "% of Road Freight tkm"})
                    all_rows.append({"Metric": "Share per Mode - LDT", **hdt_expanded, "Units": "% of Road Freight tkm"})

                except Exception as e:
                    print(f" Skipping {selected_country}: HDT/LDT shares error ({e})")

            except Exception as e:
                print(f" Skipping {selected_country}: Freight subsector shares error ({e})")

        except Exception as e:
            print(f" Skipping {selected_country}: Transport error ({e})")
            continue
        
        try:
            # --- 1. Load Total Energy (TWh) from Master Excel ---
            if unsd_global_output.exists():
                unsd_df = pd.read_excel(unsd_global_output)
                
                # Standardize columns for matching
                unsd_df['Country_Clean'] = unsd_df['Country'].astype(str).str.strip().str.lower()
                target_country_clean = selected_country.strip().lower()
                
                # Filter using cleaned names
                match = unsd_df[
                    (unsd_df['Country_Clean'] == target_country_clean) & 
                    (unsd_df['Year'].astype(str) == str(base_year))
                ]
                
                if not match.empty:
                    marine_base = float(match['Marine_Bunkers_TWh'].values[0])
                    aviation_base = float(match['Aviation_Bunkers_TWh'].values[0])
                else:
                    print(f"   -> WARNING: {selected_country} not found in UNSD Master data. Defaulting Bunkers to 0.")
                    marine_base, aviation_base = 0.0, 0.0
            else:
                print("   -> WARNING: UNSD Master file not found. Defaulting Bunkers to 0.")
                marine_base, aviation_base = 0.0, 0.0

            # --- 2. Calculate Fuel Shares (Percentages) ---
            # because we might have the CSVs even if the aggregated Excel is missing.
            
            aviation_fuel_shares = get_unsd_bunker_fuel_shares(
                base_path=unsd_input_folder,
                country=selected_country,
                year=base_year,
                bunker_type="aviation"
            )

            maritime_fuel_shares = get_unsd_bunker_fuel_shares(
                base_path=unsd_input_folder,
                country=selected_country,
                year=base_year,
                bunker_type="marine"
            )

            # --- 3. Add Fuel Share Rows to Output ---
            
            # Add Aviation fuel share rows
            BUNKER_FUELS = {"oil", "gas", "electricity", "biomass", "hydrogen"}
            for fuel, value in aviation_fuel_shares.items():
                fuel_lower = fuel.lower()
                if fuel_lower not in BUNKER_FUELS:
                    continue
                metric_name = f"Share of Technology - {fuel.capitalize()} International Aviation"

                expanded = {}
                # Base year
                expanded[str(base_year)] = value

                # Future years
                for year in target_years:
                    for scenario in scenarios:
                        key = f"{year}_{scenario}"

                        # Check config
                        if metric_name in cagr_values and year in cagr_values[metric_name]:
                            year_dict = cagr_values[metric_name][year]
                            if scenario in year_dict:
                                expanded[key] = year_dict[scenario] * 100   
                            else:
                                expanded[key] = value
                        else:
                            expanded[key] = value

                all_rows.append({
                    "Metric": metric_name,
                    **expanded,
                    "Units": "%"
                })


            for fuel, value in maritime_fuel_shares.items():
                fuel_lower = fuel.lower()
                if fuel_lower not in BUNKER_FUELS:
                    continue
                metric_name = f"Share of Technology - {fuel.capitalize()} International Maritime"
                expanded = {}

                expanded[str(base_year)] = value

                for year in target_years:
                    for scenario in scenarios:
                        key = f"{year}_{scenario}"

                        if metric_name in cagr_values and year in cagr_values[metric_name]:
                            year_dict = cagr_values[metric_name][year]

                            if scenario in year_dict:
                                expanded[key] = year_dict[scenario] * 100
                            else:
                                expanded[key] = value
                        else:
                            expanded[key] = value

                all_rows.append({
                    "Metric": metric_name,
                    **expanded,
                    "Units": "%"
                })

            # --- 4. Expand Total Energy with CAGR ---
            # Expand Marine TWh
            marine_expanded = expand_with_cagr(
                marine_base,
                get_cagr(cagr_values, "Total Energy - Int. Maritime"),
                base_year, target_years, scenarios
            )

            # Expand Aviation TWh
            aviation_expanded = expand_with_cagr(
                aviation_base,
                get_cagr(cagr_values, "Total Energy - Int. Aviation"),
                base_year, target_years, scenarios
            )

        except Exception as e:
            print(f" Error processing International Bunkers for {selected_country}: {e}")
        # --- 5. Validate Fuel Share Sum (Base Year Only) ---

        aviation_total = sum(aviation_fuel_shares.values())
        if abs(aviation_total - 100) > 0.01:
            print(f" WARNING: {selected_country} Int Aviation fuel shares in {base_year} = {aviation_total:.2f}% (should be 100%)")

        maritime_total = sum(maritime_fuel_shares.values())
        if abs(maritime_total - 100) > 0.01:
            print(f" WARNING: {selected_country} Int Maritime fuel shares in {base_year} = {maritime_total:.2f}% (should be 100%)")

        # ==============================================================================

        # ------- Final Energy Intensities -------
        try:
            # === FIX 2: Pass 'target_years' (the argument) instead of global 'TARGET_YEARS' ===
            intensities_dict = generate_energy_intensities(
                selected_country=selected_country,
                BASE_YEAR=base_year,
                TARGET_YEARS=target_years,
                SCENARIOS=scenarios,
                cagr_values=cagr_values
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
             bioethanol_in_road_gasoline, biodiesel_in_road_diesel, biodiesel_in_rail_diesel, biodiesel_in_internal_navigation_diesel, biokerosene_in_internal_aviation_fuel, ice_fuel_in_plugin_hybrid
             ) = share_technology(selected_country, year=2019)
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

            "Share of Bioethanol in Road Gasoline": bioethanol_in_road_gasoline,
            "Share of Biodiesel in Road Diesel": biodiesel_in_road_diesel,
            "Share of Biodiesel in Rail Diesel": biodiesel_in_rail_diesel,
            "Share of Biodiesel in Internal Navigation Diesel": biodiesel_in_internal_navigation_diesel,
            "Share of Biokerosene in Internal Aviation Fuel": biokerosene_in_internal_aviation_fuel,
            "Share of ICE Fuel in Plugin Hybrid": ice_fuel_in_plugin_hybrid,
        }

        tech_rows = []
        for metric in TECHNOLOGY_OVERRIDES.keys():
            row = {"Metric": metric, str(base_year): tech_base.get(metric, np.nan), "Units": "% of km"}
            tech_rows.append(row)

        tech_rows = apply_technology_overrides(
                tech_rows,
                target_years,
                scenarios,
                cagr_values,
                assumption_types
            )
        tech_rows = enforce_share_constraints(tech_rows)

        df_tech = pd.DataFrame(tech_rows)
        for col in df_tech.columns:
            if col not in ["Metric", "Units"]:
                df_tech[col] = df_tech[col].apply(lambda x: round(x * 100, 2) if pd.notnull(x) and isinstance(x, (int, float)) and x <= 1 else x)
        
        check_technology_groups(
            df_tech,
            tech_groups,
            base_year,
            target_years,
            scenarios
        )
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
            
            # === REORDER ROWS USING METRIC ORDER FROM UNITS DICTIONARY ===
            # Use the keys from generate_units_dictionary() to define the metric order
            metric_order = list(units_dict.keys())
            
            # Create ordered dataframe
            main_config["_sort_order"] = main_config["Metric"].apply(
                lambda x: metric_order.index(x) if x in metric_order else 999
            )
            main_config = main_config.sort_values("_sort_order").drop(columns=["_sort_order"])
            main_config = main_config.reset_index(drop=True)
            
            main_config = reorder_and_filter_columns(main_config, base_year, target_years, scenarios)

            output_file_path = os.path.join(base_output_dir, f'output_{selected_country}.csv')
            
            # Use to_csv instead of ExcelWriter
            main_config.to_csv(output_file_path, index=False, encoding='utf-8')
            
            print(f"  Saved: {output_file_path}")
        except Exception as e:
            # Updated error message to reflect CSV context
            print(f" Skipping {selected_country}: Error saving CSV file ({e})")
            continue

if __name__ == "__main__":
    refresh_unsd_master_data()
    main()
