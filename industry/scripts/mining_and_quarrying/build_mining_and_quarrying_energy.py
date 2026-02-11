import pandas as pd
from pathlib import Path

def _clean_val(val):
    """
    Removes markers like '*' and '-' to return absolute positive numbers.
    Handles NaN, empty strings, and placeholders safely.
    """
    if pd.isna(val):
        return 0.0
    s_val = str(val).strip()
    if s_val in ["---", "", "None", "-"]:
        return 0.0
    try:
        # Remove * (confidential) and - (formatting) then convert to float
        clean_s = s_val.replace('*', '').replace('-', '')
        return float(clean_s) if clean_s else 0.0
    except ValueError:
        return 0.0

def get_mining_total_GWh(base_path: Path, country: str, year: int, sector_name: str = "Mining and quarrying"):
    """
    Extracts total energy from the raw country CSV and converts it to GWh.
    Conversion: 1 TJ = 0.277778 GWh.
    """
    file_path = base_path / f"{country}-{year}.csv"
    if not file_path.exists(): 
        return 0.0
        
    df = pd.read_csv(file_path)
    sector_col = "Transactions(down)/Commodity(right)"
    
    # Locate the specific sector row (case-insensitive)
    row = df[df[sector_col].str.strip().str.lower() == sector_name.lower()]
    
    if row.empty: 
        return 0.0
        
    total_tj = _clean_val(row["Total Energy"].iloc[0])
    # Returns GWh rounded to 2 decimal places
    return round(total_tj * 0.277778, 2)