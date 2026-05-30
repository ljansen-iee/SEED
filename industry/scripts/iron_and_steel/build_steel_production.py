# scripts/iron_and_steel/steelproduction.py

import os  # Import OS module for file and directory operations
import sys
import pandas as pd  # Import pandas for data manipulation
from pathlib import Path
from typing import List, Optional

from industry.core.helpers import get_scenarios_from_build_config_industry, interpolate_or_extrapolate

SCENARIOS = get_scenarios_from_build_config_industry()

BASE_DIR = Path(__file__).parents[2]   # → industry/
INPUT_DIR = BASE_DIR / "input_data"
sector = "iron_and_steel"

def find_input_folder_recursive(base_folder, target_subfolder="iron_and_steel", max_depth=3):
    base_folder = str(base_folder)

    for root, dirs, files in os.walk(base_folder):
        rel_path = os.path.relpath(root, base_folder)
        depth = len(rel_path.split(os.sep))
        if depth > max_depth:
            dirs[:] = []
            continue

        candidate = os.path.join(root, target_subfolder)
        if os.path.isdir(candidate):
            return candidate

    raise FileNotFoundError(
        f"'{target_subfolder}' folder not found inside '{base_folder}' within depth {max_depth}"
    )

def load_specific_csv(input_folder, sector=None, keyword=None):
    csv_files = [f for f in os.listdir(input_folder) if f.lower().endswith('.csv')]
    for f in csv_files:
        return pd.read_csv(os.path.join(input_folder, f))
    raise FileNotFoundError(f"No CSV file found in '{input_folder}'.")

def load_specific_excel(input_folder, keyword='worldsteel'):
    excel_files = [f for f in os.listdir(input_folder) if f.lower().endswith(('.xls', '.xlsx'))]  # List all Excel files
    for f in excel_files:  # Loop through each Excel file
        if keyword in f.lower():  # If filename contains the keyword
            #print(f"Loading Excel file: {f}")
            return pd.read_excel(os.path.join(input_folder, f))  # Load and return the Excel as DataFrame
    raise FileNotFoundError(f"No Excel file found containing '{keyword}' in its name.")  # Raise error if not found

def clean_worldsteel_excel(df):
    df_clean = df.dropna().copy()  # Drop rows with any NaN values and copy DataFrame
    df_clean.columns = ["Country", "2020", "2021", "2022", "2023", "2024"]  # Rename columns to standard names
    df_clean = df_clean[df_clean['Country'] != 'Country'].reset_index(drop=True)  # Remove header rows and reset index
    df_clean.index += 1  # Start index from 1 instead of 0
    # ---- Convert from thousand tons to tons ----
    year_cols = ["2020", "2021", "2022", "2023", "2024"]
    # make sure they are numeric
    df_clean[year_cols] = df_clean[year_cols].apply(pd.to_numeric, errors="coerce")
    # multiply by 1000 to get tons
    df_clean[year_cols] = df_clean[year_cols] * 1000
    return df_clean  # Return cleaned DataFrame

def clean_globalenergymonitor_csv(df):
    df = df.copy()  # Make a copy of the DataFrame
    if 'Country (Steel)' in df.columns:  # If 'Country (Steel)' column exists
        df.rename(columns={'Country (Steel)': 'Country'}, inplace=True)  # Rename to 'Country'

    df['Total_Capacity'] = df.groupby('Country')['Capacity'].transform('sum')  # Calculate total capacity per country

    df['Percentage'] = (df['Capacity'] / df['Total_Capacity']) * 100  # Calculate percentage share for each row

    df['Percentage'] = df['Percentage'].round(2)  # Round percentage to 2 decimal places

    return df  # Return cleaned DataFrame

def load_and_process_both():
    csv_input_folder = find_input_folder_recursive(
        base_folder=INPUT_DIR,
        target_subfolder=sector,
        max_depth=5
    )
    csv_df = load_specific_csv(csv_input_folder)

    excel_input_folder = find_input_folder_recursive(
        base_folder=INPUT_DIR,
        target_subfolder=sector,
        max_depth=5
    )
    excel_df = load_specific_excel(excel_input_folder, keyword='worldsteel')

    clean_csv = clean_globalenergymonitor_csv(csv_df)
    clean_excel = clean_worldsteel_excel(excel_df)

    return clean_csv, clean_excel



def share_steel(target_years: List[int], scenarios: Optional[List[str]] = None):
    """
    Returns interpolated/extrapolated shares for primary and secondary steel.
    Works for any base year (e.g., 2019, 2023, 2025) using known data points
    (2020, 2030, 2050) and extrapolates beyond if needed.
    """

    if scenarios is None:
        scenarios = SCENARIOS

    # --- Base shares for Primary Steel ---
    base_primary = {
        2020: [80.0, 80.0, 80.0],
        2030: [80.0, 80.0, 80.0],
        2050: [80.0, 70.0, 70.0],
    }

    # --- Base shares for Secondary Steel ---
    base_secondary = {
        2020: [20.0, 20.0, 20.0],
        2030: [20.0, 20.0, 20.0],
        2050: [20.0, 30.0, 30.0],
    }

    # --- Helper function for interpolation/extrapolation ---
    def interpolate_shares(base_data, target_years, scenarios):
        per_scenario = {}

        for i, sc in enumerate(scenarios):
            # Build a dict of {year: value} for each scenario
            sc_dict = {
                y: vals[i] if i < len(vals) else vals[-1]
                for y, vals in base_data.items()
            }

            # 🔹 Removed [2020] hardcoding — now flexible for any base year
            per_scenario[sc] = interpolate_or_extrapolate(sc_dict, target_years)

        # 🔹 Build output dictionary for all target years
        return {
            y: {sc: per_scenario[sc][y] for sc in scenarios}
            for y in target_years
        }

    # --- Compute both ---
    share_primary_steel = interpolate_shares(base_primary, target_years, scenarios)
    share_secondary_steel = interpolate_shares(base_secondary, target_years, scenarios)

    return share_primary_steel, share_secondary_steel
