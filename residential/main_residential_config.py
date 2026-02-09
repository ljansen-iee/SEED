import os
import numpy as np
import pandas as pd
from pathlib import Path
import tabula

# === Imports from project libraries ===
import build_macro_indicators as build_mac
import build_saturation_rates as build_sat
import build_technology_shares as build_tec_share
import build_energy_intensities as build_en_int
import build_CAGR as build_cagr
import helpers
from helpers import load_residential_config




if __name__=="__main__":

# === SCENARIOS PARAMETRIZATION === 

    # === basics ===
    base_year = 2020  # select starting year between 2019 and 2023.
    growth_pathway = ["SSP2", "SSP2", "SSP1"] # this is the order of growth path for the three scenarios
    scenario_name = ["BAU", "Progressive", "Optimistic"] 

    # TODO: What for??
    # validate_scenarios_and_ssp(SCENARIO_NAME, GROWTH_PATHWAY)

    target_Years = [2030, 2035, 2040, 2045, 2050] # select proyected years
    
    RESIDENTIAL_CONFIG_FILE = "residential_config.xlsx"

    residential_config_path = Path(__file__).resolve().parent / RESIDENTIAL_CONFIG_FILE

    # todo: tdb run_name
    # run_name = "DKS_202507"

    print("\n===============================")
    print(f"Residential configuration file: {RESIDENTIAL_CONFIG_FILE}")
    print("===============================\n")

    # Country options
    selected_countries = [
        # "Algeria",
        # "Argentina",
        # "Brazil",
        # "Chile",
        # "Colombia",
        # "Egypt",
        # "Libya",
        # "Mexico",
        # "Namibia",
        # "Peru",
        # "Tunisia",
        # "Uruguay",
        # "Morocco",
        "South Africa" 
    ]

    # "Republic of the Congo", "Egypt", "Ethiopia", "Ghana","Kenya","Namibia","Niger",
    # "Algeria","Argentina","Brazil","Chile","Colombia","Mexico","Peru","Venezuela",
    # "Morocco","Tunisia","Tanzania","Libya",

countries_to_load = selected_countries + ["default"] 

# === create configuration parameters ===

def create_config_file_all():

    for country in selected_countries:
        print(f"\n🔹 Processing: {country}")

    # STEP 1 GENERATE MACRO INDICATORS
        # ------- Population -------
        try:
            macro_indicators = build_mac.create_macro_indicators_all()
            df_population, df_gdp_ssp, df_m2_p_all, df_person_dw, df_economics = macro_indicators
















            scenario = "baseline"
            year = 2018 # NOTE: default for now

            # STEP 1 GENERATE MACRO INDICATORS
            macro_indicators = build_mac.create_macro_indicators_all()
            df_population, df_gdp_ssp, df_m2_p_all, df_person_dw, df_economics = macro_indicators
        
            # STEP 2 GENERATE SATURATION RATES
            saturation_rates = build_sat.create_saturation_rates_all()
            df_sh_saturation, df_sc_saturation, df_appliances_saturation, df_cooking_saturation = saturation_rates

            # STEP 3 GENERATE ENERGY INTENSITIES
            intensity_sh, intensity_wh, intensity_sc, intensity_cooking, intensity_appliances = build_en_int.insert_energy_intensities()

            # STEP 4 GENERATE TECHNOLOGY SHARES
            technology_shares =  build_tec_share.create_technology_shares_all()
            df_sh_shares, df_cooking_shares_africa, df_cooking_shares_default = technology_shares

            # For cooking and dhw there are two options, for african countries or a default. Preliminary for LATAM
            if selected_country not in df_cooking_shares_africa.index:
                df_cooking_shares = df_cooking_shares_default
            else: 
                df_cooking_shares = df_cooking_shares_africa.loc[selected_country]
            
            df_wh_shares = df_cooking_shares #NOTE: Default assumption

            # STEP 5 GENERATE CAGR 
            df_CAGR = build_cagr.build_CAGR()

            # For CARG there are three options, for african countries and DEVKOPSYS or a default (base on Morocco HYPAT information).
            df_africa_regions, df_africa_subregions = build_cagr.build_Africa_regions()
            
            if selected_country not in selected_countries and selected_country not in df_africa_regions.index:
                CAGR_region = "Default"
            elif selected_country in df_africa_regions.index:
                CAGR_region = df_africa_regions.loc[selected_country].values[0]
            else:
                CAGR_region = "LATAM"
            
            df_CAGR = df_CAGR.loc[CAGR_region,:]

            # Generate data for baseline energy balance
            scenario_baseline = {
            "Population": df_population.loc[selected_country,GROWTH_PATHWAY][str(year)],
            "Residential Area per Person": df_m2_p_all.loc[selected_country,GROWTH_PATHWAY][str(year)],
            "Persons per Dwelling": df_person_dw.loc[(selected_country,GROWTH_PATHWAY,slice(None))][str(year)].iloc[0], # for other years call either 2030,2040,2050

            "Saturation of Space Heating": df_sh_saturation.loc[(scenario, "2021"), "Value in %"], # Only for Morocco!!!! Assumption, same for all other countries???
            "Saturation of Space Cooling": df_sc_saturation.loc[year,selected_country], # Available for DevKopSys countries
            "Saturation of Water Heating": df_cooking_saturation.loc[selected_country,"2021"], # Assumption according to Africas context --> SAME AS COOKING
            "Saturation of Cooking": df_cooking_saturation.loc[selected_country,"2021"], # TODO: Define projections...
            "Saturation of Appliances": df_appliances_saturation.loc[selected_country,"2021"], # TODO: Projections are all set to 100 by 2050 with linear interpolation

            # NOTE: Big assumption for Africa since 80% of total population use firewood for cooking, it is ok to assume that Cooking and water heating have the energy carriers distribution. 
            # Per default heating system will use the UNSD energy balance distribution

            # TODO: Download all this data for all African countries....For now its only for DevKopSys Focus
            "Share of Oil Boilers for Space Heating": df_sh_shares["residential oil_share"].loc[selected_country],
            "Share of LPG Boilers for Space Heating": np.nan, #TODO: all LPG demands are under natural gas 
            "Share of Natural Gas Boilers for Space Heating": df_sh_shares["residential gas_share"].loc[selected_country],
            "Share of Kerosene Boilers for Space Heating": np.nan, #TODO: all Kerosene demands are under Oil ,
            "Share of Coal Boilers for Space Heating": np.nan,
            "Share of Biogas Boilers for Space Heating": np.nan,
            "Share of Traditional Biomass Boilers for Space Heating": df_sh_shares["residential biomass_share"].loc[selected_country],
            "Share of Modern Biomass Boilers for Space Heating": np.nan, # TODO: This should be calcualted accroding to the urbanisation level
            "Share of Hydrogen Boilers for Space Heating": np.nan,
            "Share of Solar Heating for Space Heating": np.nan,
            "Share of District Heating for Space Heating": np.nan,
            "Share of Electric Heaters for Space Heating": df_sh_shares["electricity residential_share"].loc[selected_country],
            "Share of Heat Pumps for Space Heating": np.nan,
            #TODO: HEAT SHARE WHERE TO?

            # TODO: How to solve that selected country is needed to select the df
            "Share of Heat Pumps for Space Cooling": np.nan,
            "Share of Air Conditioning for Space Cooling": 1, # Literature says mainly AC system are being install and will be install

            "Share of Oil Boilers for Water Heating": np.nan,
            "Share of LPG Boilers for Water Heating": np.nan, #TODO: all LPG demands are under natural gas 
            "Share of Natural Gas Boilers for Water Heating": df_wh_shares["natural gas"].iloc[0],
            "Share of Kerosene Boilers for Water Heating": df_wh_shares["kerosene"].iloc[0],
            "Share of Coal Boilers for Water Heating": np.nan,
            "Share of Biogas Boilers for Water Heating": np.nan,
            "Share of Traditional Biomass Boilers for Water Heating": df_wh_shares["biomass"].iloc[0],
            "Share of Modern Biomass Boilers for Water Heating": np.nan, # TODO: This should be calcualted accroding to the urbanisation level
            "Share of Hydrogen Boilers for Water Heating": np.nan,
            "Share of Solar Heating for Water Heating": np.nan,
            "Share of District Heating for Water Heating": np.nan,
            "Share of Electric Heaters for Water Heating": df_wh_shares["electricity"].iloc[0],
            "Share of Heat Pumps for Water Heating": np.nan,
            #TODO: HEAT SHARE WHERE TO?

            "Share of Electric Stoves for Cooking": df_cooking_shares["electricity"].iloc[0],
            "Share of Natural Gas Stoves for Cooking": df_cooking_shares["natural gas"].iloc[0],
            "Share of LPG Stoves for Cooking": np.nan,
            "Share of Kerosene Stoves for Cooking": df_cooking_shares["kerosene"].iloc[0],
            "Share of Traditional Biomass Stoves for Cooking": df_cooking_shares["biomass"].iloc[0], # Traditional Biomass contains also Coal, Charcoal, wood, ag.waste/straw dung and others...# TODO: Optional is to differiante between rural and urban areas!
            
            "Final Energy Intensity of Oil Boilers for Space Heating": intensity_sh,

            "Final Energy Intensity of Heat Pumps for Space Cooling":intensity_sc,
            "Final Energy Intensity of LPG Boilers for Water Heating" : intensity_wh,
            "Final Energy Intensity of Electric Stoves for Cooking" : intensity_cooking,
            "Final Energy Intensity of Electrical Appliances" : intensity_appliances
            }

            main_config = pd.DataFrame(list(scenario_baseline.items()),columns=["metric","value"])
            main_config["value"] = main_config["value"].fillna(0)
            df_units = helpers.generate_units_dictionary()
            df_units = pd.DataFrame(list(df_units.items()),columns=["metric","units"])
            
            main_config = pd.merge(
                left=main_config,
                right=df_units, 
                how="left", 
                on="metric"
                )

    # export residential main configuration
            # Ensure the output directory exists
            energy_sector = "residential"
            file_name = f'output_{run_name}_{selected_country}.xlsx'
            output_path = Path.cwd().parent / energy_sector / "output_data" / file_name
            output_path.parent.mkdir(parents=True, exist_ok=True)  # Ensure target directory exists

            dataframes = {
                'Main_Residential': main_config,
                'CAGR': df_CAGR,
                # Add additional sheets/dataframes as needed
            }

            with pd.ExcelWriter(output_path) as writer:
                for sheet, df in dataframes.items():
                    df.to_excel(writer, sheet_name=sheet, index=True)

            # Save to Excel
            energy_sector ="residential"
            file_name = f'output_{selected_country}.xlsx'
            path = os.path.join(
                os.path.dirname(os.getcwd()),
                energy_sector,
                "output_data")
            output_path = os.path.join(path, file_name)
            main_config.to_excel(output_path, index=False)

            with pd.ExcelWriter(output_path) as writer:
                main_config.to_excel(writer, sheet_name='Main_Residential', index=False)  # Write df1 to Sheet1
                df_CAGR.to_excel(writer, sheet_name='CAGR')
        except Exception as e:
            print(f"Error for country {selected_country}: {e}")


# load default or modified configuration
RESIDENTIAL_CONFIG = helpers.load_residential_config(
    path=residential_config_path,
    countries=countries_to_load,
    scenarios=scenario_name
)

# Extract the default values once
DEFAULT_VALUES = RESIDENTIAL_CONFIG.get("default", {})
if not DEFAULT_VALUES:
    print(" WARNING: No 'default' data found in trans_config.xlsx. Fallback logic might fail.")
