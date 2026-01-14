# build_share_subsectors.py
from helpers import clean_column_headers, clean_missing_countries
import pandas as pd
import build_macro_indicators as build_mac
import os

import warnings # Remove unnecessary warnings
warnings.filterwarnings("ignore")

def split_by_sector(df):
    """
    Splits the DataFrame into different sector-specific DataFrames.
    """
    sectors = {
        "road_freight": list(range(0, 15)),
        "road_passenger": list(range(4)) + list(range(15, 26)),
        "rail_freight": list(range(4)) + list(range(26, 37)),
        "rail_passenger": list(range(4)) + list(range(37, 48)),
        "aviation_freight": list(range(4)) + list(range(48, 59)),
        "aviation_passenger": list(range(4)) + list(range(59, 70)),
        "marine_freight": list(range(4)) + list(range(70, 81)),
        "marine_passenger": list(range(4)) + list(range(81, 92)),
    }
    split_dfs = {sector: df.iloc[:, cols] for sector, cols in sectors.items()}
    
    return split_dfs

def load_files_from_folder(folder_path):
    dfs = {}
    for file in os.listdir(folder_path):
        if file.endswith('.xlsx'):
            full_path = os.path.join(folder_path, file)
            try:
                df = pd.read_excel(full_path, sheet_name=None)  # read all sheets
                dfs[file] = df
            except Exception as e:
                print(f"Failed to load {file}: {e}")
    return dfs

def load_all_files(energy_sector):
    # === FIX: Use __file__ to get the exact location of this script ===
    # This ensures it works regardless of where you run the command from.
    # It finds the directory containing 'build_share_subsectors.py' (i.e., 'transport')
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Now look for 'input_data' inside that directory
    path = os.path.join(script_dir, "input_data")

    dfs_country_spe = {}
    dfs_global = {}

    if not os.path.exists(path):
        # Print the path it TRIED to look for, to help debugging
        raise FileNotFoundError(f"The path {path} does not exist. Please ensure 'input_data' is inside the 'transport' folder.")
    
    for folder_name in ['country_specific', 'global']:
        folder_path = os.path.join(path, folder_name)
        if os.path.exists(folder_path):
            if folder_name == "country_specific":
                dfs_country_spe = load_files_from_folder(folder_path)
            elif folder_name == 'global':
                dfs_global = load_files_from_folder(folder_path)
    
    return dfs_country_spe, dfs_global

# === Load both global and country-specific Excel files ===
dfs_country, dfs_global = load_all_files("transport")

# === Lo2ad specific sheet from specific global file ===
file_key = "Supplementary_Material_Khalili2019_Data_final.xlsx"
sheet_name = "Transportation Demand"

if file_key in dfs_global:
    if sheet_name in dfs_global[file_key]:
        df_raw = dfs_global[file_key][sheet_name]
    else:
        raise ValueError(f"Sheet '{sheet_name}' not found in file '{file_key}'")
else:
    raise FileNotFoundError(f"File '{file_key}' not found in global input data")

# === Process the data ===
clean_df = clean_missing_countries(df_raw)
clean_df = clean_column_headers(clean_df)
sector_dfs = split_by_sector(clean_df)
df_road_freight = sector_dfs['road_freight']
df_road_passenger = sector_dfs['road_passenger']
df_rail_passenger = sector_dfs['rail_passenger']
df_rail_freight = sector_dfs["rail_freight"]
df_aviation_freight = sector_dfs['aviation_freight']
df_aviation_passenger = sector_dfs['aviation_passenger']
df_marine_freight = sector_dfs['marine_freight']
df_marine_passenger = sector_dfs['marine_passenger']
df_marine_passenger = df_marine_passenger.rename(columns={'125.71919884252964_2015.0': '2015.0', '151.47765824442826_2020.0': '2020.0', '184.5888855780654_2025.0': '2025.0', '226.4661646642811_2030.0': '2030.0', '278.1129524393058_2035.0':'2035.0', '339.83324679411805_2040.0':'2040.0', '411.2003752630195_2045.0':'2045.0','491.2278256267032_2050.0':'2050.0'})
# === HDT/LDT shares: trucks slice has one metric (HDT share) with no 'Metric' column ===
# === HDT/LDT shares: trucks slice has one metric (HDT share) with no 'Metric' column ===
df_trucks = clean_df.iloc[:, list(range(4)) + list(range(103, 114))].copy()

# Identify id vs year columns
id_cols = [c for c in ["Countries List", "Countries", "Continent", "Superregion", "Units"] if c in df_trucks.columns]
year_cols = [c for c in df_trucks.columns if c not in id_cols]

# Fix odd 2000 column name if present (we don't use it downstream anyway)
if "[%]_2000" in df_trucks.columns:
    df_trucks.rename(columns={"[%]_2000": "2000.0"}, inplace=True)

# Keep only the years we actually use
years_keep = ['2005.0','2010.0','2015.0','2020.0','2025.0','2030.0','2035.0','2040.0','2045.0','2050.0']
year_cols = [c for c in year_cols if c in years_keep]

# Ensure numeric; if values look like 53 (percent), normalize to fraction (0.53)
df_trucks[year_cols] = df_trucks[year_cols].apply(pd.to_numeric, errors="coerce")
if df_trucks[year_cols].max(numeric_only=True).max() > 1:
    df_trucks[year_cols] = df_trucks[year_cols] / 100.0

# Build per-country HDT/LDT shares
df_hdt_shares = df_trucks[["Countries List"] + year_cols].copy()
df_ldt_shares = df_hdt_shares.copy()
for c in year_cols:
    df_ldt_shares[c] = 1.0 - df_hdt_shares[c]   # Excel logic = 1 - SUM(F69)

# Expose as module-level lookups for use in calculate_subsectors()
HDT_SHARE_BY_COUNTRY = df_hdt_shares.set_index("Countries List")
LDT_SHARE_BY_COUNTRY = df_ldt_shares.set_index("Countries List")



# Add "Mode" column to each DataFrame
df_road_passenger['Mode'] = 'Road Passenger'
df_rail_passenger['Mode'] = 'Rail Passenger'
df_aviation_passenger['Mode'] = 'Aviation Passenger '
df_marine_passenger['Mode'] = 'Marine Passenger '

df_road_freight['Mode'] = 'Road Freight'
df_rail_freight['Mode'] = 'Rail Freight'
df_aviation_freight['Mode'] = 'Aviation Freight'
df_marine_freight['Mode'] = 'Marine Freight '

# Combine all dataframes into a dictionary 
dataframes = {
    'Road Passenger': df_road_passenger,
    'Rail Passenger': df_rail_passenger,
    'Marine Passenger':df_marine_passenger, 
    'Aviation Passenger': df_aviation_passenger,
    
    'Road Freight': df_road_freight,
    'Rail Freight': df_rail_freight,
    'Marine Freight': df_marine_freight,
    'Aviation Freight': df_aviation_freight,

}

# Get the list of unique countries from one DataFrame 
countries = df_road_passenger['Countries List'].unique()


passenger_freight_data = pd.DataFrame()

 
years = [2005.0, 2010.0, 2015.0, 2020.0, 2025.0, 2030.0, 2035.0, 2040.0, 2045.0, 2050.0]


for country in countries:
    
    rows = []
    for mode, df in dataframes.items():
        # Select only the rows for the current country and the desired years
        df.columns = df.columns.astype(str)  
        filtered_row = df[df['Countries List'] == country][['Countries List'] + [str(year) for year in years if str(year) in df.columns]].copy()

        filtered_row['Mode'] = mode
        rows.append(filtered_row)
    
    # Concatenate the rows for the current country
    country_data = pd.concat(rows, ignore_index=True)
    
    # Append to the final DataFrame
    passenger_freight_data = pd.concat([passenger_freight_data, country_data], ignore_index=True)

# Rename columns for better readability 
passenger_freight_data.columns = ['Country'] + [str(year) for year in years] + ['subsector_transport']
passenger_freight_data.index = passenger_freight_data.index + 1

column_name = 'subsector_transport'

columns = passenger_freight_data.columns.tolist()
columns.remove(column_name)
columns.insert(1, column_name)
passenger_freight_data = passenger_freight_data[columns]

#passenger_freight_data.set_index(['Country', 'Share per Sector'], inplace=True)
passenger_freight_data
# Load the data
all_countries_df = passenger_freight_data.copy()
all_countries_df =  all_countries_df 

# Define the year columns
year_columns = ['2005.0', '2010.0', '2015.0', '2020.0', '2025.0', 
                '2030.0', '2035.0', '2040.0', '2045.0', '2050.0']

# Convert year columns to float to ensure summation works correctly
all_countries_df[year_columns] = all_countries_df[year_columns].apply(pd.to_numeric, errors='coerce')

updated_rows = []

# Initialize a list to store updated rows (including total)
updated_rows = []

# Iterate through each country
for country in all_countries_df['Country'].unique():
    country_data = all_countries_df[all_countries_df['Country'] == country]
    
    # Comment out the line that appends a blank row to separate countries visually
    # updated_rows.append({'Country': country, 'subsector_transport': None, **{year: None for year in year_columns}})

    # Initialize total sums for passenger and freight
    total_passenger_km = {year: 0 for year in year_columns}
    total_freight_km = {year: 0 for year in year_columns}
    
    # Flag to set the country name in the first sector row
    first_sector = True
    
    # Iterate through each sector (passenger or freight) for the current country
    for sector in country_data['subsector_transport'].unique():
        sector_data = country_data[country_data['subsector_transport'] == sector]
        
        # Calculate the sum of the year columns for the current sector
        total_per_sector = sector_data[year_columns].sum(axis=0)
        
        # Create a row for the current country and sector
        # Set the country name only for the first sector row
        if first_sector:
            row = {'Country': country, 'subsector_transport': sector}
            first_sector = False
        else:
            row = {'Country': " ", 'subsector_transport': sector}
        
        for year in year_columns:
            row[year] = total_per_sector[year]
        
        # Add the sector row to the updated rows list
        updated_rows.append(row)
        
        # Sum up total passenger and freight data separately
        if "Passenger" in sector:  # Assuming "Passenger" is part of the sector name
            total_passenger_km = {year: total_passenger_km[year] + total_per_sector[year] for year in year_columns}
        elif "Freight" in sector:  # Assuming "Freight" is part of the sector name
            total_freight_km = {year: total_freight_km[year] + total_per_sector[year] for year in year_columns}
    
    # Add a row for total passenger data
    total_passenger_row = {'Country': " ", 'subsector_transport': 'Total Passenger '}
    for year in year_columns:
        total_passenger_row[year] = total_passenger_km[year]
    
    updated_rows.append(total_passenger_row)
    
    # Add a row for total freight data
    total_freight_row = {'Country': " ", 'subsector_transport': 'Total Freight'}
    for year in year_columns:
        total_freight_row[year] = total_freight_km[year]
    
    updated_rows.append(total_freight_row)
    
    # Add a row for total (combined passenger and freight) for this country
    total_combined_km = {year: total_passenger_km[year] + total_freight_km[year] for year in year_columns}
    total_combined_row = {'Country': " ", 'subsector_transport': 'Total Combined'}
    for year in year_columns:
        total_combined_row[year] = total_combined_km[year]
    
    updated_rows.append(total_combined_row)

# Create a DataFrame from the updated rows
updated_df = pd.DataFrame(updated_rows)

# Fill the country column only at the beginning of each country group
updated_df['Country'] = updated_df['Country'].fillna(method='ffill')
updated_df.index = updated_df.index + 1

out_df = updated_df.copy()

# Add a "Units" column to out_df based on subsector_transport
def add_units_to_subsector(subsector):
    if not subsector:  # For the combined total row where subsector_transport is empty
        return subsector
    elif subsector in ["Total Passenger ", "Total Freight"]:
        return subsector  
    elif "Passenger" in subsector:
        return f"{subsector} [million p-km]"
    elif "Freight" in subsector:
        return f"{subsector} [million ton-km]"
    else:
        return subsector 

out_df['subsector_transport'] = out_df['subsector_transport'].apply(add_units_to_subsector)


# Display the DataFrame or save it as needed
output_folder = "output_data"
path = os.path.join(os.getcwd(), output_folder)
os.makedirs(path, exist_ok=True)

# Save the file inside the output folder with the index
out_df.set_index(['Country', 'subsector_transport'], inplace=True)
output_file = os.path.join(path, 'updated_all_countries.xlsx')
out_df.to_excel(output_file, index=True, float_format='%.2f')  # index=True includes the multi-index


df_aviation_freight_share = clean_df.iloc[:, list(range(4)) + list(range(48, 59))]
df_aviation_passenger_share  = clean_df.iloc[:, list(range(4)) + list(range(59, 70))]
df_marine_freight_share  = clean_df.iloc[:, list(range(4)) + list(range(70, 81))]
df_marine_passenger_share  = clean_df.iloc[:, list(range(4)) + list(range(81, 92))]

# List of countries to process (add the specific countries here)
countries_to_process =  [ 
        "Algeria","Argentina", "Brazil","Chile","Colombia",
        "Egypt", "Libya","Mexico","Namibia","Peru","Tunisia","Uruguay",'Morocco',"South Africa","Angola",
        "Benin","Botswana","Burkina Faso","Burundi","Cameroon""Central African Republic","Chad","Comoros", 
        "Congo","Djibouti","Equatorial Guinea","Eritrea", "Eswatini","Ethiopia","Gabon","Gambia","Ghana",
        "Guinea","Guinea Bissau","Kenya","Lesotho","Liberia","Madagascar","Malawi","Mali","Mauritania",
        "Mozambique","Namibia","Niger","Rwanda","Senegal","Sierra Leone","Somalia","Sudan","Tanzania",
        "Togo","Uganda","Zambia","Zimbabwe"]

# Initialize a list to store updated rows (including total)
updated_rows = []

# Iterate through each country (only those in the countries_to_process list)
for country in all_countries_df['Country'].unique():
    if country not in countries_to_process:
        continue  # Skip countries not in the list
    
    country_data = all_countries_df[all_countries_df['Country'] == country]

    # Initialize total sums for passenger and freight
    total_passenger_km = {year: 0 for year in year_columns}
    total_freight_km = {year: 0 for year in year_columns}
    
    # Iterate through each sector (passenger or freight) for the current country
    for sector in country_data['subsector_transport'].unique():
        sector_data = country_data[country_data['subsector_transport'] == sector]
        
        # Calculate the sum of the year columns for the current sector
        total_per_sector = sector_data[year_columns].sum(axis=0)
        
        # Create a row for the current country and sector
        row = {'Country': country, 'subsector_transport': sector}
        for year in year_columns:
            row[year] = total_per_sector[year]
        
        # Add the sector row to the updated rows list
        updated_rows.append(row)

# Create a DataFrame from the updated rows
new_updated_df = pd.DataFrame(updated_rows)

# Fill the country column only at the beginning of each country group
new_updated_df.index = new_updated_df.index + 1


# List of sectors requiring extra rows
sectors_to_add = ['Marine Freight', 'Marine Passenger', 'Aviation Freight', 'Aviation Passenger']

# Sector share values
sector_share_values = {
    'Marine Freight': 0.05,  
    'Marine Passenger': 1.00,  
    'Aviation Freight': 0.04,  
    'Aviation Passenger': 0.07  
}

# Define year columns
year_columns = ['2005.0', '2010.0', '2015.0', '2020.0', '2025.0', 
                '2030.0', '2035.0', '2040.0', '2045.0', '2050.0']

# Final list to store processed data for all countries
final_rows = []

# Process each country's data separately
for country, country_df in new_updated_df.groupby('Country'):
    updated_rows = []
    
    # Iterate through each row for the current country
    for index, row in country_df.iterrows():
        row_dict = row.to_dict()
        row_dict["Country"] = country  # Ensure country name stays
        row_dict["subsector_transport"] = f"{country} {row['subsector_transport']}"  # Prefix country name to the sector
        updated_rows.append(row_dict)

        # If the sector is in the list, create extra rows
        if row['subsector_transport'].replace(f"{country} ", "") in sectors_to_add:
            sector_name = row['subsector_transport'].replace(f"{country} ", "")
            sector_share = sector_share_values[sector_name]
            
            # Create Share row
            share_row = row.copy()
            share_row['Country'] = country
            share_row['subsector_transport'] = f"{country} {sector_name} Domestic %"
            for year in year_columns:
                share_row[year] = sector_share
            updated_rows.append(share_row.to_dict())

            # Create Domestic row
            dom_row = row.copy()
            dom_row['Country'] = country
            dom_row['subsector_transport'] =  f"{country} {sector_name} Domestic"
            for year in year_columns:
                dom_row[year] = row[year] * sector_share
            updated_rows.append(dom_row.to_dict())

            # Create International row
            inter_row = row.copy()
            inter_row['Country'] = country
            inter_row['subsector_transport'] = f"{country} {sector_name} International"
            for year in year_columns:
                inter_row[year] = row[year] * (1 - sector_share)
            updated_rows.append(inter_row.to_dict())

    # Convert updated rows for the country into a DataFrame
    country_df_updated = pd.DataFrame(updated_rows)

    # Define specific freight and passenger sectors dynamically for the current country
    freight_sectors = [
        f"{country} Road Freight", f"{country} Rail Freight", 
        f"{country} Marine Freight Domestic", f"{country} Aviation Freight Domestic"
    ]
    
    passenger_sectors = [
        f"{country} Road Passenger", f"{country} Rail Passenger", 
        f"{country} Marine Passenger Domestic", f"{country} Aviation Passenger Domestic"
    ]
    
    # Calculate total freight for the current country
    total_freight = country_df_updated[country_df_updated['subsector_transport'].isin(freight_sectors)].iloc[:, 2:].sum(axis=0)
    
    # Calculate total passenger for the current country
    total_passenger = country_df_updated[country_df_updated['subsector_transport'].isin(passenger_sectors)].iloc[:, 2:].sum(axis=0)
    
    # Calculate the total combined freight + passenger
    total_combined = total_freight + total_passenger

    # Create total rows for the current country
    total_freight_row = pd.DataFrame({
        'Country': country,
        'subsector_transport': f"Total Freight {country}",
        **{str(year): [total_freight[year]] for year in total_freight.index}
    })

    total_passenger_row = pd.DataFrame({
        'Country': country,
        'subsector_transport': f"Total Passenger {country}",
        **{str(year): [total_passenger[year]] for year in total_passenger.index}
    })

    total_combined_row = pd.DataFrame({
        'Country': country,
        'subsector_transport': f"Total Combined {country}",
        **{str(year): [total_combined[year]] for year in total_combined.index}
    })

    # Append these total rows to the current country's DataFrame
    country_df_updated = pd.concat([country_df_updated, total_freight_row, total_passenger_row, total_combined_row], ignore_index=True)

    # Append the updated country DataFrame to the final list
    final_rows.append(country_df_updated)

# Combine all processed country DataFrames into one
final_df = pd.concat(final_rows, ignore_index=True)

# Replace NaN with 0
final_df = final_df.fillna(0)

# Reset index
final_df.reset_index(drop=True, inplace=True)
final_df.set_index(['Country', 'subsector_transport'], inplace=True)

def create_country_dfs(df, country_list):
    """
    Creates separate DataFrames for each country in the provided list.
    """
    df_by_country = {}

    # Check the country list
    #print(f"Country list: {country_list}")
    available_countries = df.index.get_level_values('Country').unique()
    #print(f"Available countries in the DataFrame: {available_countries}")

    for country in country_list:
        if country in available_countries:
            var_name = f"df_{country.replace(' ', '_')}"
            df_by_country[var_name] = df.loc[df.index.get_level_values('Country') == country]
            #print(f"Created DataFrame: {var_name}")
        else:
            print(f"Warning: {country} not found in the DataFrame")

    return df_by_country

def calculate_subsectors(country, df_population, country_data):
    """
    Performs transport analysis for the given country's data.
    Returns:
    - DataFrame: The modified country_data with calculated values.
    """
    
    # Extract total population for the country under SSP1 scenario
    total_population = df_population.loc[(country, "SSP1"), "2018"]
    
    # Set index for country_data
    country_data = country_data.set_index('subsector_transport')

    # Clean the index to remove leading/trailing spaces
    country_data.index = country_data.index.str.strip()

    # Extract transport data and convert them to numeric
    road_passenger = pd.to_numeric(country_data.loc[f"{country} Road Passenger"], errors='coerce')
    rail_passenger = pd.to_numeric(country_data.loc[f"{country} Rail Passenger"], errors='coerce')
    aviation_passenger = pd.to_numeric(country_data.loc[f"{country} Aviation Passenger Domestic"], errors='coerce')
    total_passenger = pd.to_numeric(country_data.loc[f"Total Passenger {country}"], errors='coerce')

    road_freight = pd.to_numeric(country_data.loc[f"{country} Road Freight"], errors='coerce')
    rail_freight = pd.to_numeric(country_data.loc[f"{country} Rail Freight"], errors='coerce')
    total_freight = pd.to_numeric(country_data.loc[f"Total Freight {country}"], errors='coerce')

        # === Split Road Freight into HDT and LDT using the lookups built above ===
       # === Split Road Freight into HDT and LDT using the lookups built above ===
    try:
        # Make sure indices (year labels) match like '2005.0', '2010.0', ...
        road_freight.index = road_freight.index.astype(str)

        share_hdt = HDT_SHARE_BY_COUNTRY.loc[country]
        share_hdt.index = share_hdt.index.astype(str)
        share_hdt = share_hdt.reindex(road_freight.index)

        share_ldt = LDT_SHARE_BY_COUNTRY.loc[country]
        share_ldt.index = share_ldt.index.astype(str)
        share_ldt = share_ldt.reindex(road_freight.index)

        # tkm splits
        road_freight_hdt = road_freight * share_hdt
        road_freight_ldt = road_freight * share_ldt

        # Store rows (with country prefix; stripped later)
        country_data.loc[f"{country} Road Freight - Heavy-Duty Trucks"] = road_freight_hdt
        country_data.loc[f"{country} Road Freight - Light-Duty Trucks"] = road_freight_ldt

    except KeyError:
        print(f"⚠️ HDT/LDT shares not found for {country}")


    # Compute Passenger Shares
    country_data.loc[f"Road Passenger %"] = (road_passenger / total_passenger) * 100
    country_data.loc[f"Rail Passenger %"] = (rail_passenger / total_passenger) * 100
    country_data.loc[f"Aviation Passenger %"] = (aviation_passenger / total_passenger) * 100

    # Compute Freight Shares
    country_data.loc[f"Road Freight %"] = (road_freight / total_freight) * 100
    country_data.loc[f"Rail Freight %"] = (rail_freight / total_freight) * 100

    # Compute Mobility per Capita
    mobility_per_capita_freight = (total_freight / total_population) 
    mobility_per_capita_passenger = (total_passenger / total_population) 

    # Assign mobility per capita values
    country_data.loc[f"Mobility per capita - Freight"] = mobility_per_capita_freight
    country_data.loc[f"Mobility per capita - Passenger"] = mobility_per_capita_passenger

    # Clean up index
    country_data.index.name = "Subsector_Transport"
    country_data.index = country_data.index.astype(str)
    country_data.index = country_data.index.str.replace(f"{country} ", "", regex=False)

    return country_data

def extract_country_transport_data(country_name, scenario, df_population, country_df):
    # Extract total population for the chosen country under the given scenario
    total_population = df_population.loc[(country_name, scenario), "2018"]
    
    # Run the analysis (assuming analyze_transport_data is defined)
    country_results = calculate_subsectors(country_name, df_population, country_df)
    
    # Drop the country column for a cleaner output
    country_data = country_results.drop(columns="Country")
    
    return country_data, total_population

   
def share_subsector():
    subsector_aviation_passenger_plane = 1.21
    subsector_road_freight = 75.0
    return subsector_aviation_passenger_plane, subsector_road_freight

def save_subsector_shares(out_df, output_file):
    out_df.to_excel(output_file, index=True, float_format='%.2f')