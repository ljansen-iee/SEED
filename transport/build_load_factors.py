# build_load_factors.py
import pandas as pd
import numpy as np
from helpers import clean_column_headers

def get_Load_factor_Car(df):
    "Extracts the load factor data for cars from the given DataFrame."
    clean_df = clean_column_headers(df)
    # Ensure a clean copy of the sliced DataFrame
    Load_factor_Car = clean_df.iloc[:, list(range(1)) + list(range(125, 136))].copy()

    return Load_factor_Car

def Load_factor_Bus(df):
    clean_df = clean_column_headers(df)
    # Ensure a clean copy of the sliced DataFrame
    Load_factor_Bus = clean_df.iloc[:, list(range(1)) + list(range(158, 169))].copy()

    return Load_factor_Bus

def Load_factor_two_three_occupancy(df):
    clean_df = clean_column_headers(df)
    # Extract two-wheeler and three-wheeler occupancy data
    three_wheeler_occupancy = clean_df.iloc[:, list(range(1)) + list(range(290, 301))]
    two_wheeler_occupancy = clean_df.iloc[:, list(range(1)) + list(range(268, 279))]

    # Select numeric columns from two-wheeler occupancy
    numeric_cols = two_wheeler_occupancy.select_dtypes(include=['number']).columns

    # Create a copy of two-wheeler occupancy and calculate the load factor
    Load_factor_two_three_occupancy = two_wheeler_occupancy.copy()
    Load_factor_two_three_occupancy[numeric_cols] = (two_wheeler_occupancy[numeric_cols] + three_wheeler_occupancy[numeric_cols]) / 2

    return Load_factor_two_three_occupancy

def medium_load_factor(df):
    clean_df = clean_column_headers(df)
    # Ensure a clean copy of the sliced DataFrame
    medium_load_factor = clean_df.iloc[:, list(range(1)) + list(range(191, 202))].copy()
    medium_load_factor = medium_load_factor.rename(columns={"For country level the ton/truck is only for medium_2020"  : '2020.0' })
    return medium_load_factor

def heavy_load_factor(df):
    clean_df = clean_column_headers(df)
    # Ensure a clean copy of the sliced DataFrame
    heavy_load_factor = clean_df.iloc[:, list(range(1)) + list(range(224, 235))].copy()
    return heavy_load_factor

def Load_factor_Bus_scaled(df):
    load_factor = Load_factor_Bus(df)
    
    # Identify numeric columns only
    numeric_cols = load_factor.select_dtypes(include='number').columns
    
    # Scale only numeric columns by 160
    load_factor_scaled = load_factor.copy()
    load_factor_scaled[numeric_cols] = load_factor_scaled[numeric_cols] * 160
    
    return load_factor_scaled

def load_factor_passenger_train(df_load_factor_car, selected_countries, years):
    # Create a list to store the results
    result = []

    for selected_country in selected_countries:
        # Extract values for each country and year (assuming 'Countries List' is the index)
        country_data = df_load_factor_car.loc[df_load_factor_car.index == selected_country, years]
        
        if not country_data.empty:
            # Multiply the result by 160 and append to the list
            result.append(country_data.values[0] * 160)
        else:
            result.append(np.nan)

    # Convert the result to a pandas DataFrame
    df_result = pd.DataFrame(result, index=selected_countries, columns=[years])
    
    return df_result

    
def load_factor():
    passenger_plane = 100
    freight_ship = 508.00
    passenger_ship = 0
    return passenger_plane, freight_ship, passenger_ship