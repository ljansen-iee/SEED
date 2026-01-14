# paper_and_pulp_production.py
import os  # Import the os module for file and directory operations
import pandas as pd  # Import pandas for data manipulation

def find_input_folder():
    # Get the absolute path of the directory where this script is located
    current_dir = os.path.abspath(os.path.dirname(__file__))  
    max_levels_up = 5  # Maximum number of parent directories to check

    # Loop to search for 'input_data/paper_and_pulp' folder up to max_levels_up directories above
    for _ in range(max_levels_up):
        candidate = os.path.join(current_dir, 'input_data', 'paper_and_pulp')  # Construct path to 'input_data/paper_and_pulp'
        if os.path.isdir(candidate):  # Check if the folder exists
            return candidate  # Return the path if found
        current_dir = os.path.dirname(current_dir)  # Move one directory up

    # Raise error if 'input_data/paper_and_pulp' folder is not found after checking all levels
    raise FileNotFoundError(f"'input_data/paper_and_pulp' folder not found after checking up to {max_levels_up} levels up")

def find_paper_pulp_files(input_folder):
    files = os.listdir(input_folder)  # List all files in the input folder
    # Filter files containing 'paper' or 'pulp' in their name and with valid extensions
    paper_pulp_files = [
        f for f in files 
        if ('paper' in f.lower() or 'pulp' in f.lower()) 
        and (f.endswith('.xls') or f.endswith('.xlsx') or f.endswith('.csv'))
    ]
    # Raise error if no matching files are found
    if not paper_pulp_files:
        raise FileNotFoundError("No paper and pulp related files found in input folder.")
    # Return full paths to the matching files
    return [os.path.join(input_folder, f) for f in paper_pulp_files]

def load_paper_pulp_data():
    input_folder = find_input_folder()  # Find the input folder path
    files = find_paper_pulp_files(input_folder)  # Get list of relevant files
    dfs = []  # List to store DataFrames
    for file in files:
        if file.endswith('.csv'):  # If file is CSV, use read_csv
            df = pd.read_csv(file)
        else:  # Otherwise, assume Excel format
            df = pd.read_excel(file)
        dfs.append(df)  # Add DataFrame to the list
    # Concatenate all DataFrames into one
    combined_df = pd.concat(dfs, ignore_index=True)
    return combined_df  # Return the combined DataFrame

def read_and_clean_data(df):
    # List of columns to drop if present
    columns_to_drop = [
        'Domain', 'Domain Code', 'Area Code (M49)', 'Element', 'Element Code',
        'Flag', 'Flag Description', 'Note', 'Year Code'
    ]
    # Drop unnecessary columns, ignore if not present
    df_clean = df.drop(columns=columns_to_drop, errors='ignore')
    # Rename 'Area' column to 'Country' for clarity
    df_clean = df_clean.rename(columns={"Area": "Country"})
    return df_clean  # Return the cleaned DataFrame

def convert_units_to_tons(df, density, pulpwood_items):
    # Helper function to convert values to tons based on item and unit
    def convert_to_tons(row):
        # If item is pulpwood and unit is m3, convert using density
        if row['Item'] in pulpwood_items and row['Unit'] == 'm3':
            return row['Value'] * density
        # If unit is already in tons, return as is
        elif row['Unit'] == 't':
            return row['Value']
        # Otherwise, return 0 (unknown or unsupported unit)
        else:
            return 0
    # Apply conversion to each row and create new column 'Value_tons'
    df['Value_tons'] = df.apply(convert_to_tons, axis=1)
    return df  # Return DataFrame with new column

def paper_pulp_production(df, pulpwood_items, pulp_items, paper_items):
    # Create mask for pulpwood and pulp items
    pulp_mask = df['Item'].isin(pulpwood_items + pulp_items)
    pulp_data = df[pulp_mask]  # Filter DataFrame for pulp data
    # Create mask for paper items
    paper_mask = df['Item'].isin(paper_items)
    paper_data = df[paper_mask]  # Filter DataFrame for paper data

    # Group pulp data by country and year, sum the tons
    pulp_summary = pulp_data.groupby(['Country', 'Year']).agg({'Value_tons': 'sum'}).reset_index()
    # Rename column for clarity
    pulp_summary = pulp_summary.rename(columns={'Value_tons': 'Pulp_Production_tons'})

    # Group paper data by country and year, sum the tons
    paper_summary = paper_data.groupby(['Country', 'Year']).agg({'Value_tons': 'sum'}).reset_index()
    # Rename column for clarity
    paper_summary = paper_summary.rename(columns={'Value_tons': 'Paper_Production_tons'})

    # Merge pulp and paper summaries on country and year, fill missing values with 0
    production_summary = pd.merge(pulp_summary, paper_summary, on=['Country', 'Year'], how='outer').fillna(0)
    return production_summary  # Return the merged summary

def process_paper_pulp_data():
    # Step 1: Load raw data from input folder automatically
    raw_df = load_paper_pulp_data()
    
    # Step 2: Clean the raw data
    clean_df = read_and_clean_data(raw_df)
    
    # Step 3: Define constants (density and item lists)
    density = 0.5  # Density for converting m3 to tons
    pulpwood_items = [
        "Pulpwood, round and split, coniferous (production)",
        "Pulpwood, round and split, non-coniferous (production)",
        "Other industrial roundwood, coniferous (production)",
        "Other industrial roundwood, non-coniferous (production)"
    ]
    pulp_items = [
        "Chemical wood pulp",
        "Chemical wood pulp, sulphate, bleached"
    ]
    paper_items = [
        "Recovered paper",
        "Newsprint",
        "Printing and writing papers",
        "Printing and writing papers, uncoated, mechanical",
        "Printing and writing papers, coated",
        "Other paper and paperboard",
        "Household and sanitary papers",
        "Wrapping papers"
    ]
    
    # Step 4: Convert units to tons
    df_with_tons = convert_units_to_tons(clean_df, density, pulpwood_items)
    
    # Step 5: Generate production summary
    production_summary = paper_pulp_production(df_with_tons, pulpwood_items, pulp_items, paper_items)
    
    return production_summary  # Return the final summary