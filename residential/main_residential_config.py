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


# === SCENARIOS PARAMETRIZATION === 

# === basics ===
base_year = 2020  # select starting year between 2019 and 2023.
growth_pathway = ["SSP3", "SSP2", "SSP1"] # this is the order of growth path for the three scenarios
scenario_name = ["BAU", "Progressive", "Optimistic"] 

# TODO: What for??
# validate_scenarios_and_ssp(SCENARIO_NAME, GROWTH_PATHWAY)

target_years = [base_year, 2030, 2035, 2040, 2045, 2050] # select proyected years

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
    "Egypt",
    # "Libya",
    # "Mexico",
    "Namibia",
    # "Peru",
    # "Tunisia",
    # "Uruguay",
    "Morocco",
    "South Africa" 
]

# "Republic of the Congo", "Egypt", "Ethiopia", "Ghana","Kenya","Namibia","Niger",
# "Algeria","Argentina","Brazil","Chile","Colombia","Mexico","Peru","Venezuela",
# "Morocco","Tunisia","Tanzania","Libya",

countries_to_load = selected_countries + ["default"] 

# === create configuration parameters ===

def create_csv_all():
    # STEP 1 GENERATE MACRO INDICATORS
    macro_indicators = build_mac.create_macro_indicators_all()
    df_population, df_gdp_ssp, df_m2_p_all, df_person_dw, df_economics = macro_indicators

    # STEP 2 GENERATE TECHNOLOGY SHARES
    technology_shares = build_tec_share.create_technology_shares_all()
    df_sh_shares, df_cooking_shares_africa, df_cooking_shares_default = technology_shares

    # validate that distribution shares are not higher than 100%
    share_cols = [
        "residential oil_share",
        "residential gas_share",
        "residential biomass_share",
        "electricity residential_share",
    ]
    df_sh_shares = df_sh_shares.copy()
    df_sh_shares[share_cols] = df_sh_shares[share_cols].fillna(0)
    share_sum = df_sh_shares[share_cols].sum(axis=1)
    remainder = 1 - share_sum
    df_sh_shares.loc[remainder > 0, "residential oil_share"] += remainder[remainder > 0]
    if (share_sum > 1).any():
        print("WARNING: Some residential shares sum to more than 1. Check df_sh_shares input values.")

    sh_metrics = {
    "residential oil_share": "Share of Oil Boilers for Space Heating",
    "residential gas_share": "Share of Natural Gas Boilers for Space Heating",
    "residential biomass_share": "Share of Traditional Biomass Boilers for Space Heating",
    "electricity residential_share": "Share of Electric Heaters for Space Heating",
        }
    
    cooking_metrics = {
    "Share of Electric Stoves for Cooking": "electricity",
    "Share of Natural Gas Stoves for Cooking": "natural gas",
    "Share of LPG Stoves for Cooking": None,
    "Share of Kerosene Stoves for Cooking": "kerosene",
    "Share of Traditional Biomass Stoves for Cooking": "biomass",
        }
    units_dict = helpers.generate_units_dictionary()

    def build_metric_df(metric_name, unit_key, data_df):
        unit = units_dict.get(unit_key)
        macro_rows = []
        for year in target_years:
            for scenario, ssp in zip(scenario_name, growth_pathway):
                macro_rows.append(
                    {
                        "type": "macro_ind",
                        "metric name": metric_name,
                        "year": year,
                        "scenario": scenario,
                        "units": unit,
                    }
                )

        df_macro = pd.DataFrame(macro_rows)
        for country in selected_countries:
            values = []
            for year in target_years:
                for scenario, ssp in zip(scenario_name, growth_pathway):
                    values.append(data_df.loc[(country, ssp), year])
            df_macro[country] = values
        return df_macro

    def build_constant_metric_df(metric_name, unit_key, country_series, type_label="technology share"):
        unit = units_dict.get(unit_key)
        country_values = country_series.reindex(selected_countries)
        if country_values.isna().any():
            missing = country_values[country_values.isna()].index.tolist()
            print(f"WARNING: Missing values for {metric_name} in {missing}.")
        macro_rows = []
        for year in target_years:
            for scenario in scenario_name:
                macro_rows.append(
                    {
                        "type": type_label,
                        "metric name": metric_name,
                        "year": year,
                        "scenario": scenario,
                        "units": unit,
                    }
                )

        df_macro = pd.DataFrame(macro_rows)
        for country in selected_countries:
            value = country_values.loc[country]
            df_macro[country] = [value] * len(macro_rows)
        return df_macro

    def build_cooking_series(metric_col, default_value=0.0):
        values = {}
        for country in selected_countries:
            if country in df_cooking_shares_africa.index.get_level_values("country"):
                country_row = df_cooking_shares_africa.xs(country, level="country")
                value = float(country_row[metric_col].iloc[0])
            else:
                if metric_col in df_cooking_shares_default.columns:
                    value = float(df_cooking_shares_default[metric_col].iloc[0])
                else:
                    value = default_value
            values[country] = value
        return pd.Series(values)

    try:
        df_population_macro = build_metric_df("Population", "Population", df_population)
        df_area_macro = build_metric_df("Residential Area per Person", "Residential Area per Person", df_m2_p_all)


        share_macro_dfs = []
        for share_col, metric_name in sh_metrics.items():
            share_macro_dfs.append(
                build_constant_metric_df(metric_name, metric_name, df_sh_shares[share_col])
            )

        default_series = pd.Series({country: 0.0 for country in selected_countries})
        share_macro_dfs.append(
            build_constant_metric_df(
                "Share of Heat Pumps for Space Cooling",
                "Share of Heat Pumps for Space Cooling",
                default_series,
            )
        )
        share_macro_dfs.append(
            build_constant_metric_df(
                "Share of Air Conditioning for Space Cooling",
                "Share of Air Conditioning for Space Cooling",
                pd.Series({country: 1.0 for country in selected_countries}),
            )
        )

        cooking_series = {}
        for metric_name, col in cooking_metrics.items():
            if col is None:
                cooking_series[metric_name] = pd.Series({country: 0.0 for country in selected_countries})
            else:
                cooking_series[metric_name] = build_cooking_series(col, default_value=0.0)

        cooking_sum = sum(cooking_series.values())
        cooking_remainder = 1 - cooking_sum
        cooking_series["Share of Traditional Biomass Stoves for Cooking"] = (
            cooking_series["Share of Traditional Biomass Stoves for Cooking"]
            + cooking_remainder.where(cooking_remainder > 0, 0)
        )
        if (cooking_sum > 1).any():
            print("WARNING: Some cooking shares sum to more than 1. Check cooking share inputs.")

        for metric_name, series in cooking_series.items():
            share_macro_dfs.append(
                build_constant_metric_df(metric_name, metric_name, series)
            )

        water_heating_map = {
            "Share of Electric Stoves for Cooking": "Share of Electric Heaters for Water Heating",
            "Share of Natural Gas Stoves for Cooking": "Share of Natural Gas Boilers for Water Heating",
            "Share of LPG Stoves for Cooking": "Share of LPG Boilers for Water Heating",
            "Share of Kerosene Stoves for Cooking": "Share of Kerosene Boilers for Water Heating",
            "Share of Traditional Biomass Stoves for Cooking": "Share of Traditional Biomass Boilers for Water Heating",
        }

        for cooking_metric, wh_metric in water_heating_map.items():
            share_macro_dfs.append(
                build_constant_metric_df(wh_metric, wh_metric, cooking_series[cooking_metric])
            )

        intensity_sh, intensity_wh, intensity_sc, intensity_cooking, intensity_appliances = (
            build_en_int.insert_energy_intensities()
        )

        cagr_scenario_map = {
            "Current Policies": "BAU",
            "Progessive Measuraments": "Progressive",
            "Ambitious Net Zero": "Optimistic",
        }
        df_cagr_country_raw = build_cagr.build_country_cagr(
            selected_countries,
            target_years=target_years,
        )
        df_cagr_country = df_cagr_country_raw.copy()
        df_cagr_country.columns = pd.MultiIndex.from_tuples(
            [(cagr_scenario_map.get(scenario, scenario), year) for scenario, year in df_cagr_country.columns],
            names=df_cagr_country.columns.names,
        )

        base_intensity_map = {
            "Final Energy Intensity of Space Heating": intensity_sh,
            "Final Energy Intensity of Space Cooling": intensity_sc,
            "Final Energy Intensity of Water Heating": intensity_wh,
            "Final Energy Intensity of Cooking": intensity_cooking,
            "Final Energy Intensity of Electrical Appliances": intensity_appliances,
        }

        intensity_metrics_map = {
            "Final Energy Intensity of Space Heating": build_en_int.SPACE_HEATING_INTENSITY_METRICS,
            "Final Energy Intensity of Space Cooling": build_en_int.SPACE_COOLING_INTENSITY_METRICS,
            "Final Energy Intensity of Water Heating": build_en_int.WATER_HEATING_INTENSITY_METRICS,
            "Final Energy Intensity of Cooking": build_en_int.COOKING_INTENSITY_METRICS,
            "Final Energy Intensity of Electrical Appliances": build_en_int.APPLIANCES_INTENSITY_METRICS,
        }

        cagr_units_map = {
            "Final Energy Intensity of Space Heating": "kWh/m2",
            "Final Energy Intensity of Space Cooling": "kWh/m2",
            "Final Energy Intensity of Water Heating": "kWh/dw",
            "Final Energy Intensity of Cooking": "kWh/dw",
            "Final Energy Intensity of Electrical Appliances": "kWh/dw",
        }

        cagr_years = [base_year] + target_years
        cagr_rows = []
        row_keys = []
        energy_intensity_list = (
            df_cagr_country.index.get_level_values("energy_intensity").unique().tolist()
        )
        for energy_intensity in energy_intensity_list:
            for year in cagr_years:
                for scenario_dst in cagr_scenario_map.values():
                    cagr_rows.append(
                        {
                            "type": "CAGR",
                            "metric name": energy_intensity,
                            "year": year,
                            "scenario": scenario_dst,
                            "units": cagr_units_map.get(energy_intensity, units_dict.get(energy_intensity)),
                        }
                    )
                    row_keys.append((energy_intensity, year, scenario_dst))

        df_cagr_macro = pd.DataFrame(cagr_rows)
        for country in selected_countries:
            values = []
            for energy_intensity, year, scenario_dst in row_keys:
                try:
                    if year == base_year:
                        values.append(0)
                    else:
                        cagr_rate = df_cagr_country.loc[(country, energy_intensity), (scenario_dst, year)]
                        values.append(cagr_rate)
                except KeyError:
                    values.append(np.nan)
            df_cagr_macro[country] = values

        intensity_rows = []
        expanded_row_keys = []
        for energy_intensity, year, scenario_dst in row_keys:
            for metric_name in intensity_metrics_map.get(energy_intensity, []):
                intensity_rows.append(
                    {
                        "type": "energy intensity",
                        "metric name": metric_name,
                        "year": year,
                        "scenario": scenario_dst,
                        "units": units_dict.get(metric_name),
                    }
                )
                expanded_row_keys.append((energy_intensity, metric_name, year, scenario_dst))

        df_cagr_intensity_macro = pd.DataFrame(intensity_rows)
        for country in selected_countries:
            values = []
            for energy_intensity, metric_name, year, scenario_dst in expanded_row_keys:
                base_intensity = base_intensity_map.get(energy_intensity)
                if base_intensity is None:
                    values.append(np.nan)
                    continue
                try:
                    if year == base_year:
                        values.append(base_intensity)
                    else:
                        cagr_rate = df_cagr_country.loc[(country, energy_intensity), (scenario_dst, year)]
                        values.append(base_intensity * (1 + cagr_rate / 100) ** 5)
                except KeyError:
                    values.append(np.nan)
            df_cagr_intensity_macro[country] = values

        df_all = pd.concat(
            [df_population_macro, df_area_macro, *share_macro_dfs, df_cagr_macro, df_cagr_intensity_macro],
            ignore_index=True,
        )

        output_dir = Path(__file__).resolve().parent / "output_data"
        output_dir.mkdir(parents=True, exist_ok=True)
        df_all.to_csv(output_dir / "macro_indicators_all_countries.csv", index=False)

    except Exception as e:
        print(f"Error generating macro indicators CSV: {e}")


if __name__=="__main__":
    create_csv_all()










#             scenario = "baseline"
#             year = 2018 # NOTE: default for now

#             # STEP 1 GENERATE MACRO INDICATORS
#             macro_indicators = build_mac.create_macro_indicators_all()
#             df_population, df_gdp_ssp, df_m2_p_all, df_person_dw, df_economics = macro_indicators
        
#             # STEP 2 GENERATE SATURATION RATES
#             saturation_rates = build_sat.create_saturation_rates_all()
#             df_sh_saturation, df_sc_saturation, df_appliances_saturation, df_cooking_saturation = saturation_rates

#             # STEP 3 GENERATE ENERGY INTENSITIES
#             intensity_sh, intensity_wh, intensity_sc, intensity_cooking, intensity_appliances = build_en_int.insert_energy_intensities()

#             # STEP 4 GENERATE TECHNOLOGY SHARES
#             technology_shares =  build_tec_share.create_technology_shares_all()
#             df_sh_shares, df_cooking_shares_africa, df_cooking_shares_default = technology_shares

#             # For cooking and dhw there are two options, for african countries or a default. Preliminary for LATAM
#             if selected_country not in df_cooking_shares_africa.index:
#                 df_cooking_shares = df_cooking_shares_default
#             else: 
#                 df_cooking_shares = df_cooking_shares_africa.loc[selected_country]
            
#             df_wh_shares = df_cooking_shares #NOTE: Default assumption

#             # STEP 5 GENERATE CAGR 
#             df_CAGR = build_cagr.build_CAGR()

#             # For CARG there are three options, for african countries and DEVKOPSYS or a default (base on Morocco HYPAT information).
#             df_africa_regions, df_africa_subregions = build_cagr.build_Africa_regions()
            
#             if selected_country not in selected_countries and selected_country not in df_africa_regions.index:
#                 CAGR_region = "Default"
#             elif selected_country in df_africa_regions.index:
#                 CAGR_region = df_africa_regions.loc[selected_country].values[0]
#             else:
#                 CAGR_region = "LATAM"
            
#             df_CAGR = df_CAGR.loc[CAGR_region,:]

#             # Generate data for baseline energy balance
#             scenario_baseline = {
#             "Population": df_population.loc[selected_country,GROWTH_PATHWAY][str(year)],
#             "Residential Area per Person": df_m2_p_all.loc[selected_country,GROWTH_PATHWAY][str(year)],
#             "Persons per Dwelling": df_person_dw.loc[(selected_country,GROWTH_PATHWAY,slice(None))][str(year)].iloc[0], # for other years call either 2030,2040,2050

#             "Saturation of Space Heating": df_sh_saturation.loc[(scenario, "2021"), "Value in %"], # Only for Morocco!!!! Assumption, same for all other countries???
#             "Saturation of Space Cooling": df_sc_saturation.loc[year,selected_country], # Available for DevKopSys countries
#             "Saturation of Water Heating": df_cooking_saturation.loc[selected_country,"2021"], # Assumption according to Africas context --> SAME AS COOKING
#             "Saturation of Cooking": df_cooking_saturation.loc[selected_country,"2021"], # TODO: Define projections...
#             "Saturation of Appliances": df_appliances_saturation.loc[selected_country,"2021"], # TODO: Projections are all set to 100 by 2050 with linear interpolation

#             # NOTE: Big assumption for Africa since 80% of total population use firewood for cooking, it is ok to assume that Cooking and water heating have the energy carriers distribution. 
#             # Per default heating system will use the UNSD energy balance distribution

#             # TODO: Download all this data for all African countries....For now its only for DevKopSys Focus
#             "Share of Oil Boilers for Space Heating": df_sh_shares["residential oil_share"].loc[selected_country],
#             "Share of LPG Boilers for Space Heating": np.nan, #TODO: all LPG demands are under natural gas 
#             "Share of Natural Gas Boilers for Space Heating": df_sh_shares["residential gas_share"].loc[selected_country],
#             "Share of Kerosene Boilers for Space Heating": np.nan, #TODO: all Kerosene demands are under Oil ,
#             "Share of Coal Boilers for Space Heating": np.nan,
#             "Share of Biogas Boilers for Space Heating": np.nan,
#             "Share of Traditional Biomass Boilers for Space Heating": df_sh_shares["residential biomass_share"].loc[selected_country],
#             "Share of Modern Biomass Boilers for Space Heating": np.nan, # TODO: This should be calcualted accroding to the urbanisation level
#             "Share of Hydrogen Boilers for Space Heating": np.nan,
#             "Share of Solar Heating for Space Heating": np.nan,
#             "Share of District Heating for Space Heating": np.nan,
#             "Share of Electric Heaters for Space Heating": df_sh_shares["electricity residential_share"].loc[selected_country],
#             "Share of Heat Pumps for Space Heating": np.nan,
#             #TODO: HEAT SHARE WHERE TO?

#             # TODO: How to solve that selected country is needed to select the df
#             "Share of Heat Pumps for Space Cooling": np.nan,
#             "Share of Air Conditioning for Space Cooling": 1, # Literature says mainly AC system are being install and will be install

#             "Share of Oil Boilers for Water Heating": np.nan,
#             "Share of LPG Boilers for Water Heating": np.nan, #TODO: all LPG demands are under natural gas 
#             "Share of Natural Gas Boilers for Water Heating": df_wh_shares["natural gas"].iloc[0],
#             "Share of Kerosene Boilers for Water Heating": df_wh_shares["kerosene"].iloc[0],
#             "Share of Coal Boilers for Water Heating": np.nan,
#             "Share of Biogas Boilers for Water Heating": np.nan,
#             "Share of Traditional Biomass Boilers for Water Heating": df_wh_shares["biomass"].iloc[0],
#             "Share of Modern Biomass Boilers for Water Heating": np.nan, # TODO: This should be calcualted accroding to the urbanisation level
#             "Share of Hydrogen Boilers for Water Heating": np.nan,
#             "Share of Solar Heating for Water Heating": np.nan,
#             "Share of District Heating for Water Heating": np.nan,
#             "Share of Electric Heaters for Water Heating": df_wh_shares["electricity"].iloc[0],
#             "Share of Heat Pumps for Water Heating": np.nan,
#             #TODO: HEAT SHARE WHERE TO?

#             "Share of Electric Stoves for Cooking": df_cooking_shares["electricity"].iloc[0],
#             "Share of Natural Gas Stoves for Cooking": df_cooking_shares["natural gas"].iloc[0],
#             "Share of LPG Stoves for Cooking": np.nan,
#             "Share of Kerosene Stoves for Cooking": df_cooking_shares["kerosene"].iloc[0],
#             "Share of Traditional Biomass Stoves for Cooking": df_cooking_shares["biomass"].iloc[0], # Traditional Biomass contains also Coal, Charcoal, wood, ag.waste/straw dung and others...# TODO: Optional is to differiante between rural and urban areas!
            
#             "Final Energy Intensity of Oil Boilers for Space Heating": intensity_sh,

#             "Final Energy Intensity of Heat Pumps for Space Cooling":intensity_sc,
#             "Final Energy Intensity of LPG Boilers for Water Heating" : intensity_wh,
#             "Final Energy Intensity of Electric Stoves for Cooking" : intensity_cooking,
#             "Final Energy Intensity of Electrical Appliances" : intensity_appliances
#             }

#             main_config = pd.DataFrame(list(scenario_baseline.items()),columns=["metric","value"])
#             main_config["value"] = main_config["value"].fillna(0)
#             df_units = helpers.generate_units_dictionary()
#             df_units = pd.DataFrame(list(df_units.items()),columns=["metric","units"])
            
#             main_config = pd.merge(
#                 left=main_config,
#                 right=df_units, 
#                 how="left", 
#                 on="metric"
#                 )

#     # export residential main configuration
#             # Ensure the output directory exists
#             energy_sector = "residential"
#             file_name = f'output_{run_name}_{selected_country}.xlsx'
#             output_path = Path.cwd().parent / energy_sector / "output_data" / file_name
#             output_path.parent.mkdir(parents=True, exist_ok=True)  # Ensure target directory exists

#             dataframes = {
#                 'Main_Residential': main_config,
#                 'CAGR': df_CAGR,
#                 # Add additional sheets/dataframes as needed
#             }

#             with pd.ExcelWriter(output_path) as writer:
#                 for sheet, df in dataframes.items():
#                     df.to_excel(writer, sheet_name=sheet, index=True)

#             # Save to Excel
#             energy_sector ="residential"
#             file_name = f'output_{selected_country}.xlsx'
#             path = os.path.join(
#                 os.path.dirname(os.getcwd()),
#                 energy_sector,
#                 "output_data")
#             output_path = os.path.join(path, file_name)
#             main_config.to_excel(output_path, index=False)

#             with pd.ExcelWriter(output_path) as writer:
#                 main_config.to_excel(writer, sheet_name='Main_Residential', index=False)  # Write df1 to Sheet1
#                 df_CAGR.to_excel(writer, sheet_name='CAGR')
#         except Exception as e:
#             print(f"Error for country {selected_country}: {e}")


# # load default or modified configuration
# RESIDENTIAL_CONFIG = helpers.load_residential_config(
#     path=residential_config_path,
#     countries=countries_to_load,
#     scenarios=scenario_name
# )

# # Extract the default values once
# DEFAULT_VALUES = RESIDENTIAL_CONFIG.get("default", {})
# if not DEFAULT_VALUES:
#     print(" WARNING: No 'default' data found in trans_config.xlsx. Fallback logic might fail.")
