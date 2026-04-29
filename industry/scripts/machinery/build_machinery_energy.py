import pandas as pd
from pathlib import Path

def _clean_val(val):
    """Cleans markers like * and - from the data"""
    try:
        s_val = str(val).strip()
        if pd.isna(val) or s_val == "---" or s_val == "":
            return 0.0
        # This removes the - and * characters as you requested
        clean_s = s_val.replace('*', '').replace('-', '')
        return float(clean_s) if clean_s else 0.0
    except:
        return 0.0

# Add the 4th argument 'sector_name' with a default value
def get_machinery_total_GWh(base_path: Path, country: str, year: int, sector_name: str = "Machinery"):
    file_path = base_path / f"{country}-{year}.csv"
    if not file_path.exists(): 
        return 0.0
        
    df = pd.read_csv(file_path)
    sector_col = "Transactions(down)/Commodity(right)"
    
    # Use lowercase comparison for robustness
    row = df[df[sector_col].str.strip().str.lower() == sector_name.lower()]
    
    if row.empty: 
        return 0.0
        
    total_tj = _clean_val(row["Total Energy"].iloc[0])
    return round(total_tj * 0.277,2)

