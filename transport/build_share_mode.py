import pandas as pd
import numpy as np
from helpers import clean_column_headers  # Import the function from khalili.py

def process_bus_share_data(df):
    # Clean column headers using the function from khalili.py
    clean_df = clean_column_headers(df)
    
    # Select columns
    bus_share_road_passenger = clean_df.iloc[:, list(range(1)) + list(range(92, 103))].copy()
    bus_share_road_passenger = bus_share_road_passenger.rename(columns={'40.0_2015.0': '2015.0', '40.0_2020.0': '2020.0', '39.0_2025.0': '2025.0', '38.0_2030.0': '2030.0', '38.0_2035.0':'2035.0', '37.0_2040.0':'2040.0', '37.0_2045.0':'2045.0','35.0_2050.0':'2050.0'})
    columns_to_multiply = ['[%]_2000','2005.0','2010.0','2015.0','2020.0','2025.0','2030.0','2035.0','2040.0','2045.0','2050.0']

# Multiply only specified columns by 100 to get value in % 
    bus_share_road_passenger[columns_to_multiply] = bus_share_road_passenger[columns_to_multiply] * 100
    return bus_share_road_passenger

def share_of_two_Three(df):
    clean_df = clean_column_headers(df)
    # Ensure a clean copy of the sliced DataFrame
    share_of_two_Three = clean_df.iloc[:, list(range(1)) + list(range(631, 642))].copy()

    columns_to_multiply = [
        '[%]_2000', '2005.0', '2010.0', '2015.0', '2020.0',
        '2025.0', '2030.0', '2035.0', '2040.0', '2045.0', '2050.0'
    ]

    # Ensure modification is direct and avoids SettingWithCopyWarning
    share_of_two_Three.loc[:, columns_to_multiply] *= 100

    return share_of_two_Three

#def share_per_mode_ldv(df_cleaned, df_share_two_three, selected_countries, years):
      #result = []
      #for selected_country in selected_countries:
         #row = []  # To store data for each country across multiple years
        
         #for year in years:
             # Get the value from df_cleaned for the selected country and year
            # cleaned_value = df_cleaned.loc[df_cleaned["Countries List"] == selected_country, year].values[0]
            
             # Get the value from df_share_two_three for the selected country and year
             #share_value = df_share_two_three.loc[df_share_two_three["Countries List"] == selected_country, year].values[0]
            
             # Calculate the "Share per Mode - LDV"
             #share_per_mode_ldv = 100 - (cleaned_value + share_value)
            
             # Append the result to the row for the selected country
             #row.append(share_per_mode_ldv)

         # Append the row to the result list (one row for each country)
         #result.append(row)

     # Convert the result to a pandas DataFrame, with the selected countries as index and years as columns
      #df_result = pd.DataFrame(result, index=selected_countries, columns=years)

      #return df_result

def share_per_mode_ldv(df_process_bus_share_data, df_share_two_three, countries, year):
    """
    Calculate the share of LDV (Light Duty Vehicles) for each country.
    
    Parameters:
    - df_process_bus_share_data: DataFrame with bus share data
    - df_share_two_three: DataFrame with 2&3 wheeler share data
    - countries: List of countries to process
    - year: Column name for the year (e.g., '2020.0')
    
    Returns:
    - DataFrame with LDV shares for each country
    """
    df_cleaned = pd.DataFrame({"Countries List": countries})
    df_cleaned[year] = np.nan

    for selected_country in countries:
        try:
            # Get bus share
            bus_share = df_process_bus_share_data.loc[
                df_process_bus_share_data["Countries List"] == selected_country, year
            ].values
            bus_share = bus_share[0] if len(bus_share) > 0 else 0

            # Get 2&3W share
            two_three_share = df_share_two_three.loc[
                df_share_two_three["Countries List"] == selected_country, year
            ].values
            two_three_share = two_three_share[0] if len(two_three_share) > 0 else 0

            # Calculate LDV share (100 - bus - 2&3W)
            ldv_share = 100 - bus_share - two_three_share
            df_cleaned.loc[df_cleaned["Countries List"] == selected_country, year] = max(0, ldv_share)
        except Exception as e:
            print(f"Error processing {selected_country}: {e}")
            df_cleaned.loc[df_cleaned["Countries List"] == selected_country, year] = np.nan

    return df_cleaned


