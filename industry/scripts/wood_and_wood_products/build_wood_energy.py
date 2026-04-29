import pandas as pd
from pathlib import Path

def _clean_val(val):
    """Helper to convert strings with markers or nulls to 0.0"""
    try:
        s_val = str(val).strip()
        if pd.isna(val) or s_val == "---" or s_val == "":
            return 0.0
        
        # Remove * and any single hyphens that might be there
        clean_s = s_val.replace('*', '').replace('-', '')
        
        # If string is empty after cleaning, return 0
        if not clean_s:
            return 0.0
            
        return float(clean_s)
    except Exception:
        return 0.0

def get_wood_total_GWh(base_path: Path, country: str, year: int, sector_name: str = "Wood and wood products"):
    file_name = f"{country}-{year}.csv"
    file_path = base_path / file_name
    
    if not file_path.exists(): 
        print(f"Warning: {file_path} not found.")
        return 0.0
        
    df = pd.read_csv(file_path)
    sector_col = "Transactions(down)/Commodity(right)"
    
    # Matching lowercase to avoid case-sensitivity issues
    row = df[df[sector_col].str.strip().str.lower() == sector_name.lower()]
    
    if row.empty: 
        return 0.0
    
    # Extraction and conversion from TJ to MWh
    total_tj = _clean_val(row["Total Energy"].iloc[0])
    return round(total_tj * 0.277,2)