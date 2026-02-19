import os
import pandas as pd
import numpy as np
import tabula
import pycountry
from pathlib import Path
import glob


# === Dynamic Paths for UNSD Aggregation ===
# This identifies the 'transport' folder where helpers.py resides
TRANSPORT_DIR = Path(__file__).resolve().parent

# Path to the folder containing individual country CSVs (Algeria-2021.csv, etc.)
UNSD_INPUT_FOLDER = TRANSPORT_DIR / "input_data" / "unsd_country_specific"

# Path to the global folder where the merged master file lives
UNSD_GLOBAL_DIR = TRANSPORT_DIR / "input_data" / "global"
UNSD_GLOBAL_OUTPUT = UNSD_GLOBAL_DIR / "aggregated_transport_data.xlsx"

# Ensure the global directory exists immediately upon import
os.makedirs(UNSD_GLOBAL_DIR, exist_ok=True)

def find_input_folder():
    start_dir = os.path.dirname(os.path.abspath(__file__))
    for _ in range(2):  # current dir and one level up
        input_folder = os.path.join(start_dir, "input_data")
        if os.path.isdir(input_folder):
            return input_folder
        start_dir = os.path.dirname(start_dir)
    raise FileNotFoundError("Could not find 'input_data' folder")

def read_excel_file(file_path, sheet_name):
    try:
        return pd.read_excel(file_path, sheet_name=sheet_name, engine="openpyxl")
    except Exception as e:
        print(f"Error reading Excel file {file_path}, sheet {sheet_name}: {e}")
        return None

def load_global_transport_data(output_folder="output_data"):
    input_path = find_input_folder()
    file_path = os.path.join(input_path, "global", "Supplementary_Material_Khalili2019_Data_final.xlsx")
    sheet_name = "Transportation Demand"
    os.makedirs(output_folder, exist_ok=True)
    df_raw = read_excel_file(file_path, sheet_name)
    if df_raw is None:
        print(f"Failed to load transportation demand data from {file_path}")
    return df_raw

def read_file(file_path):
    try:
        if file_path.endswith('.csv'):
            return pd.read_csv(file_path, encoding="utf8")
        elif file_path.endswith('.xlsx'):
            return pd.read_excel(file_path, engine='openpyxl')
        elif file_path.endswith('.pdf'):
            tables = tabula.read_pdf(file_path, pages="all", multiple_tables=True, encoding="latin1")
            if isinstance(tables, list) and len(tables) > 0:
                return tables[0]
            return None
        else:
            raise ValueError(f"Unsupported file extension: {file_path}")
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None

def load_country_specific_data(input_path):
    folder_path = os.path.join(input_path, "country_specific")
    dfs_country_spe = {}
    if os.path.exists(folder_path):
        for file_doc in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file_doc)
            df = read_file(file_path)
            if df is not None:
                dfs_country_spe[file_doc] = df
    return dfs_country_spe

def load_excel_files_from_folder(folder_path, sheet_name="Transportation Demand"):
    dfs = {}
    for file in os.listdir(folder_path):
        if file.endswith(".xlsx"):
            file_path = os.path.join(folder_path, file)
            try:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                dfs[os.path.splitext(file)[0]] = df
            except Exception as e:
                print(f"Error loading {file}: {e}")
    return dfs

def get_transport_constants(parameter, vehicle_type=None):
    constants = {
        "energy_intensity": {
            "Diesel ICE Passenger Train": 0.248 * 288,
            "Direct Electric Passenger Train": 0.088 * 288,
            "FCEV Passenger Train": 0.149 * 288,
            "Diesel ICE LDT": 0.82 * 2.2,
            "BEV LDT": 0.32 * 2.2,
            "FCEV LDT": 0.69 * 2.2,
            "Diesel ICE HDT": 0.82 * 9.4,
            "BEV HDT": 0.32 * 9.4,
            "FCEV HDT": 0.69 * 9.4,
            "Diesel ICE Freight Train": 0.114 * 564,
            "Direct Electric Freight Train": 0.041 * 564,
            "FCEV Freight Train": 0.068 * 564,
            "Diesel Freight Ship": 0.119 * 508.00,
            "FCEV Freight Ship": 0.071 * 508.00,
        },
        "load_factor_multiplier": {
            "Passenger Train": 160,
            "Freight Train": 60,
        },
    }
    return constants.get(parameter, {}).get(vehicle_type, np.nan)


import numpy as np

def interpolate_or_extrapolate(expanded_dict, target_years, scenarios):
    """
    If some years (like 2035, 2045, 2055) are missing, interpolate between
    known points or extrapolate from the nearest available ones.
    """
    # Extract numeric year and scenario values
    values = {}
    for key, val in expanded_dict.items():
        if key.isdigit():  # base year (2020)
            year, scenario = int(key), "Base"
        elif "_" in key:
            parts = key.split("_")
            year, scenario = int(parts[0]), parts[1]
        else:
            continue
        values.setdefault(scenario, {})[year] = val

    # Interpolate per scenario
    for scen in scenarios:
        if scen not in values:
            continue

        years = sorted(values[scen].keys())
        vals = [values[scen][y] for y in years]

        for y in target_years:
            if y in years:
                continue  # already present
            if y < min(years):
                # extrapolate backward
                slope = (vals[1] - vals[0]) / (years[1] - years[0])
                values[scen][y] = vals[0] + slope * (y - years[0])
            elif y > max(years):
                # extrapolate forward
                slope = (vals[-1] - vals[-2]) / (years[-1] - years[-2])
                values[scen][y] = vals[-1] + slope * (y - years[-1])
            else:
                # interpolate between known years
                y0 = max([yr for yr in years if yr < y])
                y1 = min([yr for yr in years if yr > y])
                v0, v1 = values[scen][y0], values[scen][y1]
                values[scen][y] = v0 + (v1 - v0) * ((y - y0) / (y1 - y0))

    # Rebuild flattened dict
    new_dict = {}
    for scen, yvals in values.items():
        for y, val in sorted(yvals.items()):
            if scen == "Base":
                new_dict[str(y)] = val
            else:
                new_dict[f"{y}_{scen}"] = val

    return new_dict

import pandas as pd

def read_excel_file(file_path, sheet_name):
    """
    Reads an Excel file and returns a DataFrame.
    """
    pd.set_option('display.float_format', '{:.6f}'.format)
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        #print("Excel file read successfully!")
        return df
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        return None

def clean_column_headers(df):
    """
    Cleans column headers by merging the first two rows as column names.
    """
    try:
        if len(df) < 2:
            raise ValueError("DataFrame does not have enough rows to clean column headers.")

        col_names = df.iloc[0].fillna('').astype(str) + "_" + df.iloc[1].fillna('').astype(str)
        df.columns = col_names.str.replace(r'^nan_', '', regex=True).str.strip('_')
        df = df.drop([0, 1]).reset_index(drop=True)
        df.index = range(1, len(df) + 1)

        return df
    except Exception as e:
        print(f"Error cleaning column headers: {e}")
        return df

def clean_missing_countries(df):
    """
    Removes rows with missing country names.
    """
    required_columns = ["Countries", "Countries List"]
    missing_cols = [col for col in required_columns if col not in df.columns]
    
    if missing_cols:
        #print(f"Warning: Missing columns in DataFrame: {missing_cols}")
        return df  

    df.dropna(subset=required_columns, inplace=True)
    df.reset_index(drop=True, inplace=True)
    df.index = df.index + 1

    return df


def split_data_by_columns(df):
    """
    Splits data into separate DataFrames based on transport modes and renames specific columns in Marine_passenger.
    """
    subsets = {
        'Road_freight': df.iloc[:, 0:15],
        'Road_passenger': df.iloc[:, list(range(4)) + list(range(15, 26))],
        'Rail_freight': df.iloc[:, list(range(4)) + list(range(26, 37))],
        'Rail_passenger': df.iloc[:, list(range(4)) + list(range(37, 48))],
        'Aviation_freight': df.iloc[:, list(range(4)) + list(range(48, 59))],
        'Aviation_passenger': df.iloc[:, list(range(4)) + list(range(59, 70))],
        'Marine_freight': df.iloc[:, list(range(4)) + list(range(70, 81))],
        'Marine_passenger': df.iloc[:, list(range(4)) + list(range(81, 92))]
    }

    # Rename specific columns in Marine_passenger
    if 'Marine_passenger' in subsets:
        subsets['Marine_passenger'] = subsets['Marine_passenger'].rename(columns={
            '125.71919884252964_2015.0': '2015.0',
            '151.47765824442826_2020.0': '2020.0',
            '184.5888855780654_2025.0': '2025.0',
            '226.4661646642811_2030.0': '2030.0',
            '278.1129524393058_2035.0': '2035.0',
            '339.83324679411805_2040.0': '2040.0',
            '411.2003752630195_2045.0': '2045.0',
            '491.2278256267032_2050.0': '2050.0'
        })

    return subsets

def add_mode_column(subsets):
    """
    Adds a 'Mode' column to each subset DataFrame.
    """
    updated_dfs = {}
    for mode, df in subsets.items():
        if isinstance(df, pd.DataFrame):
            df = df.copy()
            df['Mode'] = mode
            updated_dfs[mode] = df
    return updated_dfs

def process_transport_data(dataframes, years):
    """
    Processes transport data by filtering for specific years and appending all modes into a single DataFrame.
    """
    countries = dataframes['Road_passenger']['Countries List'].unique()
    passenger_freight_data = pd.DataFrame()
    
    for country in countries:
        rows = []
        
        for mode, df in dataframes.items():
            df.columns = df.columns.astype(str)  
            filtered_row = df[df['Countries List'] == country][['Countries List'] + [str(year) for year in years if str(year) in df.columns]].copy()
            filtered_row['Mode'] = mode
            rows.append(filtered_row)
        
        country_data = pd.concat(rows, ignore_index=True)
        passenger_freight_data = pd.concat([passenger_freight_data, country_data], ignore_index=True)
    
    # Rename columns for better readability
    passenger_freight_data.columns = ['Country'] + [str(year) for year in years] + ['Subsector_transport']
    passenger_freight_data.index = passenger_freight_data.index + 1

    # Reorder columns
    column_name = 'Subsector_transport'
    columns = passenger_freight_data.columns.tolist()
    columns.remove(column_name)
    columns.insert(1, column_name)
    passenger_freight_data = passenger_freight_data[columns]

    # Set MultiIndex
    passenger_freight_data.set_index(['Country', 'Subsector_transport'], inplace=True)

    return passenger_freight_data

def calculate_sector_totals(all_countries_df, year_columns):
    updated_rows = []  # List to store new rows

    for country in all_countries_df.index.get_level_values('Country').unique():
        country_data = all_countries_df[all_countries_df.index.get_level_values('Country') == country]

        # Initialize total dictionaries
        total_passenger_km = {year: 0 for year in year_columns}
        total_freight_km = {year: 0 for year in year_columns}

        for sector in country_data.index.get_level_values('Subsector_transport').unique():
            sector_data = country_data[country_data.index.get_level_values('Subsector_transport') == sector]

            # Ensure total_per_sector is always a Pandas Series
            total_per_sector = sector_data[year_columns].sum(axis=0)
            total_per_sector = pd.Series(total_per_sector, index=year_columns)

            # Store the row
            row = {'Country': country, 'Subsector_transport': sector, **total_per_sector.to_dict()}
            updated_rows.append(row)

            # Check sector type (ignoring case differences)
            sector_lower = sector.lower()
            if "passenger" in sector_lower:
                for year in year_columns:
                    total_passenger_km[year] += total_per_sector[year]
            elif "freight" in sector_lower:
                for year in year_columns:
                    total_freight_km[year] += total_per_sector[year]

        # Append total passenger, freight, and combined transport
        total_combined_km = {year: total_passenger_km[year] + total_freight_km[year] for year in year_columns}

        updated_rows.append({'Country': country, 'Subsector_transport': "Total Passenger", **total_passenger_km})
        updated_rows.append({'Country': country, 'Subsector_transport': "Total Freight", **total_freight_km})
        updated_rows.append({'Country': country, 'Subsector_transport': "Total Combined", **total_combined_km})

    # Convert to DataFrame
    updated_df = pd.DataFrame(updated_rows)
    updated_df['Country'] = updated_df['Country'].ffill()  # Fill missing country names
    updated_df.set_index(['Country', 'Subsector_transport'], inplace=True)

    return updated_df

def save_to_excel(df, filename):
    """
    Saves a DataFrame to an Excel file.
    """
    df.to_excel(filename, index=True, float_format='%.2f')

def remove_missing_countries(df, columns=["Countries", "Countries List"]):
    """
    Removes rows with missing values in the specified columns and resets the index.
    """
    # Identify rows with NaN values in the specified columns
    nan_rows = df[df[columns].isna().any(axis=1)]

    # Drop NaN rows from the DataFrame
    df_cleaned = df.dropna(subset=columns).reset_index(drop=True)

    # Reset index to start from 1
    df_cleaned.index = df_cleaned.index + 1

    return df_cleaned, nan_rows


def extract_country_data(df, countries):
    country_data_dict = {}

    for country in countries:
        try:
            # If the dataframe has a MultiIndex, use xs()
            if isinstance(df.index, pd.MultiIndex):
                country_df = df.xs(country, level=0).reset_index()
            else:
                country_df = df.loc[country].reset_index()
            
            country_df.index = country_df.index + 1  # Adjust index
            country_data_dict[country] = country_df
        except KeyError:
            print(f"Warning: {country} not found in the dataset.")

    return country_data_dict


def get_iso2_country_code(country_name: str) -> str:
    """
    Returns ISO-2 country code (e.g. Algeria -> DZ).
    Falls back to a safe filename if not found.
    """
    try:
        country = pycountry.countries.search_fuzzy(country_name)[0]
        return country.alpha_2
    except LookupError:
        # fallback: safe filename
        return country_name.replace(" ", "_")


def reorder_and_filter_columns(df, base_year, target_years, scenarios):
    keep = (["Metric", str(base_year)] +
            [f"{y}_{s}" for y in target_years for s in scenarios] +
            ["Units"])
    # keep only those, in that order, if they exist
    cols = [c for c in keep if c in df.columns]
    missing = [c for c in keep if c not in df.columns]
    if missing:
        print("Warning: missing expected columns:", missing)
    # return only these columns; extra columns are dropped
    return df[cols]


def generate_units_dictionary():
    return {
        "Population": "p",
        "Mobility per capita - Passenger": "pkm/p",
        "Share per Subsector - Road Passenger": "% of pkm",
        "Share per Subsector - Rail Passenger = Train": "% of pkm",
        "Share per Subsector - Aviation Passenger = Plane": "% of pkm",
        "Share per Mode - LDV": "% of Road pkm",
        "Share per Mode - Bus": "% of Road pkm",
        "Share per Mode - 2&3W": "% of Road pkm",
        "Load Factor - LDV": "p/vehicle",
        "Load Factor - Bus": "p/vehicle",
        "Load Factor - 2&3W": "p/vehicle",
        "Load Factor - Passenger Train": "p/vehicle",
        "Load Factor - Passenger Plane": "p/vehicle",
        "Load Factor - Freight Ship": "t/vehicle",
        "Share of Technology - Gasoline ICE LDV": "% of LDV km",
        "Share of Technology - Diesel ICE LDV": "% of LDV km",
        "Share of Technology - BEV LDV": "% of LDV km",
        "Share of Technology - LPG ICE LDV": "% of LDV km",
        "Share of Technology - Gasoline Plugin Hybrid LDV": "% of LDV km",
        "Share of Technology - Diesel Plugin Hybrid LDV": "% of LDV km",
        "Share of Technology - FCEV LDV": "% of LDV km",
        "Share of Technology - Diesel ICE Bus": "% of Bus km",
        "Share of Technology - BEV Bus": "% of Bus km",
        "Share of Technology - FCEV Bus": "% of Bus km",
        "Share of Technology - Diesel Plugin Hybrid Bus": "% of Bus km",
        "Share of Technology - Gasoline ICE 2&3W": "% of 2&3W km",
        "Share of Technology - BEV 2&3W": "% of 2&3W km",
        "Share of Technology - Diesel ICE Passenger Train": "% of Passenger Train km",
        "Share of Technology - Direct Electric Passenger Train": "% of Passenger Train km",
        "Share of Technology - FCEV Passenger Train": "% of Passenger Train km",
        "Share of Technology - Kerosene Passenger Plane": "% of Passenger Plane km",
        "Share of Technology - Diesel ICE LDT": "% of LDT km",
        "Share of Technology - BEV LDT": "% of LDT km",
        "Share of Technology - FCEV LDT": "% of LDT km",
        "Share of Technology - Diesel Plugin Hybrid LDT": "% of LDT km",
        "Share of Technology - Diesel ICE HDT": "% of HDT km",
        "Share of Technology - BEV HDT": "% of HDT km",
        "Share of Technology - FCEV HDT": "% of HDT km",
        "Share of Technology - Diesel Plugin Hybrid HDT": "% of HDT km",
        "Share of Technology - Diesel ICE Freight Train": "% of Freight Train km",
        "Share of Technology - Direct Electric Freight Train": "% of Freight Train km",
        "Share of Technology - FCEV Freight Train": "% of Freight Train km",
        "Share of Technology - Diesel ICE Freight Ship": "% of Freight Ship km",
        "Share of Technology - Methanol Freight Ship": "% of Freight Ship km",
        "Share of Technology - Ammonia Freight Ship": "% of Freight Ship km",
        "Share of Technology - BEV Freight Ship": "% of Freight Ship km",
        "Share of Technology - FCEV Freight Ship": "% of Freight Ship km",
        "Share of Technology - Kerosene Freight Plane": "% of Freight Plane km",
        "Share of Technology - Diesel Passenger Ship": "% of Passenger Ship km",
        "Mobility per capita - Freight": "tkm/p",
        "Share per Subsector - Road Freight": "% of tkm",
        "Share per Subsector - Rail Freight = Train": "% of tkm",
        "Final Energy Intensity - Diesel ICE Bus": "kWh/vkm",
        "Final Energy Intensity - Gasoline ICE LDV": "kWh/vkm",
        "Final Energy Intensity - Diesel ICE LDV": "kWh/vkm",
        "Final Energy Intensity - LPG ICE LDV": "kWh/vkm",
        "Final Energy Intensity - BEV LDV": "kWh/vkm",
        "Final Energy Intensity - FCEV LDV": "kWh/vkm",
        "Final Energy Intensity - Gasoline Plugin Hybrid LDV": "kWh/vkm",
        "Final Energy Intensity - Diesel Plugin Hybrid LDV": "kWh/vkm",
        "Final Energy Intensity - BEV Bus": "kWh/vkm",
        "Final Energy Intensity - FCEV Bus": "kWh/vkm",
        "Final Energy Intensity - Diesel Plugin Hybrid Bus": "kWh/vkm",
        "Final Energy Intensity - Gasoline ICE 2&3W": "kWh/vkm",
        "Final Energy Intensity - BEV 2&3W": "kWh/vkm",
        "Final Energy Intensity - Diesel ICE Passenger Train": "kWh/vkm",
        "Final Energy Intensity - Direct Electric Passenger Train": "kWh/vkm",
        "Final Energy Intensity - FCEV Passenger Train": "kWh/vkm",
        "Final Energy Intensity - BEV Passenger Plane": "kWh/vkm",
        "Final Energy Intensity - FCEV Passenger Plane": "kWh/vkm",
        "Final Energy Intensity - Kerosene Passenger Plane": "kWh/vkm",
        "Load Factor - LDT": "t/vehicle",
        "Load Factor - HDT": "t/vehicle",
        "Load Factor - Passenger Ship": "p/vehicle",
        "Load Factor - Freight Train": "t/vehicle",
        "Final Energy Intensity - Diesel ICE LDT": "kWh/vkm",
        "Final Energy Intensity - BEV LDT": "kWh/vkm",
        "Final Energy Intensity - FCEV LDT": "kWh/vkm",
        "Final Energy Intensity - Diesel Plugin Hybrid LDT": "kWh/vkm",
        "Final Energy Intensity - Diesel ICE HDT": "kWh/vkm",
        "Final Energy Intensity - BEV HDT": "kWh/vkm",
        "Final Energy Intensity - FCEV HDT": "kWh/vkm",
        "Final Energy Intensity - Diesel Plugin Hybrid HDT": "kWh/vkm",
        "Final Energy Intensity - Diesel ICE Freight Train": "kWh/vkm",
        "Final Energy Intensity - Direct Electric Freight Train": "kWh/vkm",
        "Final Energy Intensity - FCEV Freight Train": "kWh/vkm",
        "Final Energy Intensity - Diesel Freight Ship": "kWh/vkm",
        "Final Energy Intensity - Methanol Freight Ship": "kWh/vkm",
        "Final Energy Intensity - Ammonia Freight Ship": "kWh/vkm",
        "Final Energy Intensity - BEV Freight Ship": "kWh/vkm",
        "Final Energy Intensity - FCEV Freight Ship": "kWh/vkm",
        "Final Energy Intensity - Kerosene Freight Plane": "kWh/vkm",
        "Final Energy Intensity - Diesel Passenger Ship": "kWh/vkm",
    }


def refresh_unsd_master_data():
    """Aggregates all country CSVs into one master Excel in the global folder."""
    # Ensure the global directory exists before trying to save
    UNSD_GLOBAL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    
    all_data = []
    # Using the path defined in this same file
    csv_files = glob.glob(os.path.join(UNSD_INPUT_FOLDER, "*.csv"))
    
    if not csv_files:
        print(f" No UNSD CSV files found in {UNSD_INPUT_FOLDER}")
        return

    for file_path in csv_files:
        try:
            filename = os.path.basename(file_path)
            name_part = os.path.splitext(filename)[0]
            # Split "Algeria-2021" -> "Algeria", "2021"
            country_name, year = name_part.rsplit('-', 1) if '-' in name_part else (name_part, "2020")
            
            df = pd.read_csv(file_path)
            # Process Marine and Aviation
            for trans in ['International marine bunkers', 'International aviation bunkers']:
                row = df[df['Transactions(down)/Commodity(right)'] == trans]
                
                if not row.empty:
                    # Clean the data (TJ to TWh)
                    raw_val = str(row['Total Energy'].values[0]).replace('*', '').replace('---', '0').strip()
                    val_twh = abs(float(raw_val)) / 3600.0
                else:
                    val_twh = 0.0
                
                all_data.append({
                    'Country': country_name, 
                    'Year': str(year),
                    'Type': 'Marine' if 'marine' in trans else 'Aviation',
                    'Value_TWh': val_twh
                })
        except Exception as e:
            print(f"Error processing {filename}: {e}")

    # Create pivot table: Rows = Country/Year, Columns = Aviation/Marine
    master_df = pd.DataFrame(all_data).pivot_table(
        index=['Country', 'Year'], 
        columns='Type', 
        values='Value_TWh'
    ).reset_index()
    
    # Finalize columns and save
    master_df.columns = ['Country', 'Year', 'Aviation_Bunkers_TWh', 'Marine_Bunkers_TWh']
    master_df.to_excel(UNSD_GLOBAL_OUTPUT, index=False)
    #print(f" UNSD Master Data Refreshed: {UNSD_GLOBAL_OUTPUT}")

<<<<<<< HEAD
def check_technology_groups(df, tech_groups, base_year, target_years, scenarios, tolerance=0.01):

    years = [str(base_year)] + [f"{y}_{s}" for y in target_years for s in scenarios]

    for group_name, metrics in tech_groups.items():

        for year in years:

            total = df.loc[df["Metric"].isin(metrics), year].sum()

            if pd.isna(total):
                continue

            if abs(total - 100.0) > tolerance:
                print(
                    f" WARNING: {group_name} technology shares in {year} = "
                    f"{total:.2f}% (should be 100%)"
                )

# === Technology validation groups ===
TECH_GROUPS = {

    "LDV": [
        "Share of Technology - Gasoline ICE LDV",
        "Share of Technology - Diesel ICE LDV",
        "Share of Technology - LPG ICE LDV",
        "Share of Technology - BEV LDV",
        "Share of Technology - FCEV LDV",
        "Share of Technology - Diesel Plugin Hybrid LDV",
        "Share of Technology - Gasoline Plugin Hybrid LDV"
    ],

    "Bus": [
        "Share of Technology - Diesel ICE Bus",
        "Share of Technology - BEV Bus",
        "Share of Technology - FCEV Bus",
        "Share of Technology - Diesel Plugin Hybrid Bus"
    ],

    "2&3W": [
        "Share of Technology - Gasoline ICE 2&3W",
        "Share of Technology - BEV 2&3W"
    ],

    "Passenger Train": [
        "Share of Technology - Diesel ICE Passenger Train",
        "Share of Technology - Direct Electric Passenger Train",
        "Share of Technology - FCEV Passenger Train"
    ],

    "Passenger Plane": [
        "Share of Technology - Kerosene Passenger Plane",
        "Share of Technology - BEV Passenger Plane",
        "Share of Technology - FCEV Passenger Plane"
    ],

    "LDT": [
        "Share of Technology - Diesel ICE LDT",
        "Share of Technology - BEV LDT",
        "Share of Technology - FCEV LDT",
        "Share of Technology - Diesel Plugin Hybrid LDT"
    ],

    "HDT": [
        "Share of Technology - Diesel ICE HDT",
        "Share of Technology - BEV HDT",
        "Share of Technology - FCEV HDT",
        "Share of Technology - Diesel Plugin Hybrid HDT"
    ],

    "Freight Train": [
        "Share of Technology - Diesel ICE Freight Train",
        "Share of Technology - Direct Electric Freight Train",
        "Share of Technology - FCEV Freight Train"
    ],

    "Freight Ship": [
        "Share of Technology - Diesel ICE Freight Ship",
        "Share of Technology - Methanol Freight Ship",
        "Share of Technology - Ammonia Freight Ship",
        "Share of Technology - BEV Freight Ship",
        "Share of Technology - FCEV Freight Ship"
    ],
    "Int Aviation": [
        "Share of Technology - Oil Int Aviation", "Share of Technology - Gas Int Aviation",
        "Share of Technology - Electricity Int Aviation", "Share of Technology - Coal Int Aviation",
        "Share of Technology - Biomass Int Aviation", "Share of Technology - Heat Int Aviation",
        "Share of Technology - Hydrogen Int Aviation"
    ],
    "Int Maritime": [
        "Share of Technology - Oil Int Maritime", "Share of Technology - Gas Int Maritime",
        "Share of Technology - Electricity Int Maritime", "Share of Technology - Coal Int Maritime",
        "Share of Technology - Biomass Int Maritime", "Share of Technology - Heat Int Maritime",
        "Share of Technology - Hydrogen Int Maritime"
    ]
}



def get_interpolated_value(df, ssp, year):
    available_years = [int(y) for y in df.columns if y.isdigit()]
    available_years.sort()

    if year in available_years:
        return float(df.loc[ssp, str(year)])

    # find surrounding years
    lower = max([y for y in available_years if y < year], default=None)
    upper = min([y for y in available_years if y > year], default=None)

    if lower is None or upper is None:
        raise ValueError(f"Cannot interpolate year {year}")

    lower_val = float(df.loc[ssp, str(lower)])
    upper_val = float(df.loc[ssp, str(upper)])

    # linear interpolation
    ratio = (year - lower) / (upper - lower)

    return lower_val + ratio * (upper_val - lower_val)



=======

def load_transport_config(excel_path: Path, countries: list, scenarios: list):

    df = pd.read_excel(excel_path)
    df.columns = df.columns.str.strip()

    required_cols = {
        "Assumption Type",
        "Metric Name",
        "Year",
        "Scenario",
        "default"
    }
    if not required_cols.issubset(df.columns):
        raise ValueError(f"Excel must contain columns: {required_cols}")

    SCENARIO_ALIAS_MAP = {"sc_a": 0, "sc_b": 1, "sc_c": 2}

    config = {c: {} for c in countries}

    for _, row in df.iterrows():
        metric = str(row["Metric Name"]).strip()

        try:
            year = int(row["Year"])
        except Exception:
            continue

        scenario_val = str(row["Scenario"]).strip()
        scenario_val_lower = scenario_val.lower()
        default_val = row["default"]

        for country in countries:
            if country in df.columns and pd.notna(row[country]):
                val = float(row[country])
            elif pd.notna(default_val):
                val = float(default_val)
            else:
                continue

            # Resolve scenario
            if scenario_val in scenarios:
                target_scenarios = [scenario_val]
            elif scenario_val_lower == "all":
                target_scenarios = scenarios
            elif scenario_val_lower in SCENARIO_ALIAS_MAP:
                idx = SCENARIO_ALIAS_MAP[scenario_val_lower]
                if idx < len(scenarios):
                    target_scenarios = [scenarios[idx]]
                else:
                    continue
            else:
                continue

            for s in target_scenarios:
                entry = config[country].setdefault(
                    metric,
                    {
                        "assumption_type": str(row["Assumption Type"]).strip().upper(),
                        "values": {}
                    }
                )
                entry["values"].setdefault(year, {})[s] = val

    return config


# def get_assumption(config, metric, expected_type):
#     entry = config.get(metric)
#     if entry is None:
#         raise KeyError(f"Metric not found in config: {metric}")

#     if entry["assumption_type"] != expected_type:
#         raise ValueError(
#             f"{metric}: expected {expected_type}, got {entry['assumption_type']}"
#         )

#     return entry["values"]
>>>>>>> main
