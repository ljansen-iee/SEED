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

def extract_population_values(df_population, country, base_year=2020, years=None, scenarios=None, ssp_order=None):
    """
    Extracts population values by matching the SCENARIOS list to the SSP_ORDER list
    based on their position (index).
    """
    # Ensure we have lists to work with
    if years is None: years = [2030, 2050]
    if scenarios is None: scenarios = []
    if ssp_order is None: ssp_order = []

    result = {}
    
    # 1. Get Base Year Value (using the first SSP in your order as the reference)
    try:
        base_ssp = ssp_order[0] if ssp_order else "SSP2"
        result[str(base_year)] = df_population.loc[(country, base_ssp), str(base_year)]
    except (KeyError, IndexError):
        result[str(base_year)] = np.nan
    
    # 2. MATCHING LOGIC:
    # This matches scenarios[0] with ssp_order[0], scenarios[1] with ssp_order[1], etc.
    for year in years:
        for idx, scenario in enumerate(scenarios):
            # Get the SSP that matches this scenario's position
            ssp = ssp_order[idx] 
            
            col_name = f"{year}_{scenario}"
            try:
                result[col_name] = df_population.loc[(country, ssp), str(year)]
            except (KeyError, IndexError):
                print(f"Warning: Missing data for {country} | {ssp} | {year}")
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
    """
    Validates that the lists match in length. 
    REMOVED: The requirement for the first scenario to be named 'Baseline'.
    """
    if not scenarios:
        raise ValueError("SCENARIOS cannot be empty.")

    # FIX: We no longer check if scenarios[0] == "Baseline". 
    # This allows you to name your scenarios whatever you want.

    if len(scenarios) != len(ssp_order):
        raise ValueError(
            "SCENARIOS and SSP_ORDER must have the same length.\n"
            f"SCENARIOS={scenarios}\nSSP_ORDER={ssp_order}"
        )
    
def get_ssp_for_scenario(scenario, scenarios, ssp_order):
    """
    Finds the SSP associated with a scenario by its position in the list.
    """
    try:
        idx = scenarios.index(scenario)
        return ssp_order[idx]
    except ValueError:
        # If the scenario name isn't found, fallback to the first SSP
        return ssp_order[0]


