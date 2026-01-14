import pandas as pd
import pandas as pd
import numpy as np
import os

def load_industrial_database(csv_file_path):
    """
    Load the industrial database from a CSV file.
    """
    df = pd.read_csv(csv_file_path)
    df.drop(columns=['y', 'x', "ID"], inplace=True, errors='ignore')
    return df
# Filter for selected countries and group
def filter_and_group_by_country(df, countries):
    """
    Filter the DataFrame for specific countries and group by country, technology, and unit.
    """
    # Define the countries of interest
    df_filtered = df[df['country'].isin(countries)]
    df_filtered = df_filtered.groupby(['country', 'technology', 'unit']).sum(numeric_only=True).reset_index()
    return df_filtered


def convert_to_t_per_year_vectorized(df, efficiency=0.7):
    """
    Vectorized conversion of capacity to Mt/year and update unit column for successful conversions.
    """
    bpd_to_kt_per_year = {
        "Ethylene": 36.0,
        "Propylene": 37.2,
        "Benzene": 51.1,
        "Xylene": 51.1,
        "Diesel": 48.2,
        "Gasoline": 42.7,
        "HVC": 46.0,  # Assuming HVC refers to Methanol in this context
    }
    mt_year = np.full(len(df), np.nan)
    # Kt/yr and kt/yr
    mask_kt = df['unit'].isin(['Kt/yr', 'kt/yr'])
    mt_year[mask_kt] = df.loc[mask_kt, 'capacity'] / 1000
    # bpd
    mask_bpd = df['unit'] == 'bpd'
    factors = df.loc[mask_bpd, 'technology'].map(bpd_to_kt_per_year)
    mt_year[mask_bpd] = (df.loc[mask_bpd, 'capacity'] * factors) / 1000
    # 10kt/yr
    mask_10kt = df['unit'] == '10kt/yr'
    mt_year[mask_10kt] = df.loc[mask_10kt, 'capacity'] / 100
    # Apply efficiency and round
    df = df.copy()
    df['Mt/year'] = np.round(mt_year * efficiency, 3)
    # Only update unit where conversion was successful
    mask = ~df['Mt/year'].isna()
    df.loc[mask, 'unit'] = 'Mio. ton/yr'
    return df

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, "industrial_production_capacity.csv")
    csv_file_path = r"C:\Users\eduque\Fraunhofer\DeV-KopSys-2 - Globale ESA\04_methods_and_models\Sectoral_End-Use_Energy_Scenario\subsector_workflows\industry\data_preparation\input_data\industrial_database.csv"    
    countries = [
        "CL",
        "EG",
        "MA",
        "ZA",
    ]
    df = load_industrial_database(csv_file_path)
    df_filtered = filter_and_group_by_country(df, countries)
    df_filtered = convert_to_t_per_year_vectorized(df_filtered, efficiency=0.7)

    # Save the filtered DataFrame to a CSV file
    df_filtered.to_csv(output_path, index=True)

    
