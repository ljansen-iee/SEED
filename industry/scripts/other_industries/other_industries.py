

import pandas as pd
import numpy as np
import glob
import os

# List of transactions to extract
transactions = [
    "Iron and steel",
    "Chemical and petrochemical",
    "Non-ferrous metals",
    "Non-metallic minerals",
    "Transport equipment",
    "Machinery",
    "Mining and quarrying",
    "Food and tobacco",
    "Paper  pulp and printing",
    "Wood and wood products",
    "Textile and leather",
    "Construction",
    "Industry n.e.s"
]

folder_path = r"C:\Users\eduque\Fraunhofer\DeV-KopSys-2 - Globale ESA\04_methods_and_models\Sectoral_End-Use_Energy_Scenario\subsector_workflows\industry\data_preparation\input_data\country_specific"
all_files = glob.glob(os.path.join(folder_path, "*.csv"))

dfs = []
for file in all_files:
    df = pd.read_csv(file, dtype=str)
    df = df.replace('---', np.nan)
    df = df.applymap(lambda x: x.lstrip('*') if isinstance(x, str) else x)
    # Extract only the rows for the specified transactions (case-insensitive, strip spaces)
    mask = df['Transactions(down)/Commodity(right)'].str.strip().str.lower().isin([t.lower() for t in transactions])
    df_transactions = df[mask].copy()
    # Convert all columns except the first two to numeric
    for col in df_transactions.columns[2:]:
        df_transactions[col] = pd.to_numeric(df_transactions[col], errors='coerce')
    # Add a column for country (from the first column, which is always the country name)
    df_transactions['Country(2019)'] = df_transactions[df_transactions.columns[0]]
    dfs.append(df_transactions)

# Concatenate all country DataFrames
df_all = pd.concat(dfs, ignore_index=True)

# Set Country(2019) as index
df_all.set_index('Country(2019)', inplace=True)


# Convert all columns except 'Transactions(down)/Commodity(right)' to numeric, then divide only numeric columns by 3.6
for col in df_all.columns:
    if col != 'Transactions(down)/Commodity(right)':
        df_all[col] = pd.to_numeric(df_all[col], errors='coerce')

numeric_cols = df_all.columns.difference(['Transactions(down)/Commodity(right)'])
df_all[numeric_cols] = df_all[numeric_cols] / 3.6

# Save or display the final DataFrame
print(df_all)
# df_all.to_csv("all_countries_industry_transactions_GWh.csv")
