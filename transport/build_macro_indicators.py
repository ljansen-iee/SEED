#build_macro_indicators.py

import os
import pandas as pd
import numpy as np

def find_input_folder():
    start_dir = os.path.dirname(os.path.abspath(__file__))
    input_folder = os.path.join(start_dir, 'input_data')
    if os.path.exists(input_folder) and os.path.isdir(input_folder):
        return input_folder
    parent_dir = os.path.dirname(start_dir)
    input_folder = os.path.join(parent_dir, 'input_data')
    if os.path.exists(input_folder) and os.path.isdir(input_folder):
        return input_folder
    raise FileNotFoundError("Could not find 'input_data' folder")

def read_file(file_path):
    try:
        if file_path.endswith(".csv"):
            return pd.read_csv(file_path)
        elif file_path.endswith((".xls", ".xlsx")):
            return pd.read_excel(file_path, engine="openpyxl")
        else:
            print(f"Skipping unsupported file format: {file_path}")
            return None
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None

def clean_df_ssp(df):
    if df.empty or df.iloc[:, 0].isna().all():
        return df
    df = df[df.iloc[:, 0].str.startswith("SSP", na=False)]
    df = df.set_index(df.columns[0], drop=True)
    return df

def country_name(key):
    for prefix in ['chart-data_pop_', 'chart-data_gdp_']:
        if prefix in key:
            return key.split(prefix)[1].split('.csv')[0]
    return "Unknown"

def add_countries(dfs, countries):
    for df, country in zip(dfs, countries):
        df.insert(0, "Country", country)
    return dfs

def prepare_df(df_list):
    df = pd.concat(df_list, axis=0, ignore_index=False)
    df.reset_index(inplace=True)
    df.columns = ["SSP"] + list(df.columns[1:])
    df.set_index(["Country", "SSP"], drop=True, inplace=True)
    return df

def process_population_data(dfs_country_spe):
    df_population = [clean_df_ssp(df) for key, df in dfs_country_spe.items() 
                     if key.startswith('chart-data_pop')]
    pop_country_names = [country_name(key) for key, df in dfs_country_spe.items() 
                         if key.startswith('chart-data_pop')]
    df_population = add_countries(df_population, pop_country_names)
    df_population = prepare_df(df_population)
    return df_population

def get_country_population_value(df_population, country, year="2018", scenario="SSP1"):
    try:
        value = df_population.loc[(country, scenario), str(year)]
        return value
    except KeyError:
        return f"Data not available for {country}, {scenario} in {year}"
    except Exception as e:
        return f"Error: {str(e)}"

def extract_population_values(df_population, country, years=[2030, 2050], scenarios=["Baseline", "RF", "EL"], ssp_scenarios=None):
    if ssp_scenarios is None:
        ssp_scenarios = {
            2030: {"Baseline": "SSP2", "RF": "SSP2", "EL": "SSP1"},
            2050: {"Baseline": "SSP2", "RF": "SSP2", "EL": "SSP1"}
        }
    
    result = {}
    base_year = '2018'
    try:
        result['2018'] = df_population.loc[(country, 'SSP1'), base_year]
    except (KeyError, IndexError):
        print(f"Warning: Missing {base_year} SSP2 population for {country}")
        result['2018'] = np.nan
    
    for year in years:
        for scenario in scenarios:
            ssp = ssp_scenarios[year][scenario]
            col_name = f"{year}_{scenario}"
            try:
                result[col_name] = df_population.loc[(country, ssp), str(year)]
            except (KeyError, IndexError):
                print(f"Warning: Missing {ssp} {year} population for {country}")
                result[col_name] = np.nan
    
    return result

def load_data(input_path=None):
    if input_path is None:
        input_path = find_input_folder()
    
    dfs_country_spe = {}
    if not os.path.exists(input_path):
        print(f"Directory does not exist: {input_path}")
        return None
    
    for folder_name in os.listdir(input_path):
        folder_path = os.path.join(input_path, folder_name)
        if folder_name == "country_specific":
            for file_doc in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file_doc)
                df = read_file(file_path)
                if df is not None:
                    dfs_country_spe[file_doc] = df
    return dfs_country_spe

def validate_scenarios_and_ssp(scenarios, ssp_order):
    if not scenarios:
        raise ValueError("SCENARIOS cannot be empty.")

    if scenarios[0] != "Baseline":
        raise ValueError("Baseline must be the first scenario in SCENARIOS.")

    if len(scenarios) != len(ssp_order):
        raise ValueError(
            "SCENARIOS and SSP_ORDER must have the same length.\n"
            f"SCENARIOS={scenarios}\nSSP_ORDER={ssp_order}"
        )
def get_ssp_for_scenario(scenario, scenarios, ssp_order):
    idx = scenarios.index(scenario)
    return ssp_order[idx]


