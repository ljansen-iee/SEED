import pandas as pd
from pathlib import Path

# --- Configuration ---
FILE_NAME = "transport/Morocco-2020.csv" # Ensure this matches your file exactly
COUNTRY = "Morocco"
YEAR = 2020
# ---------------------

def _clean_val(val):
    """Debug version of cleaner that prints weird values."""
    try:
        s_val = str(val).strip()
        if pd.isna(val) or s_val in ["---", "", "nan", "...", "-"]:
            return 0.0
        
        # Remove * , and - (negative sign)
        clean_s = s_val.replace('*', '').replace(',', '').replace('-', '')
        return float(clean_s)
    except Exception as e:
        print(f"    [!] Error cleaning value '{val}': {e}")
        return 0.0

def test_bunker_logic():
    print(f"--- Debugging UNSD Bunker Logic for {FILE_NAME} ---")
    
    file_path = Path(FILE_NAME)
    if not file_path.exists():
        print(f"ERROR: File not found at {file_path.absolute()}")
        return

    # 1. Load Data
    try:
        df = pd.read_csv(file_path)
        print(f"File loaded successfully. Columns found:")
        print(df.columns.tolist())
    except Exception as e:
        print(f"ERROR reading CSV: {e}")
        return

    # 2. Find the correct sector column (fuzzy match)
    sector_col = None
    for col in df.columns:
        if "Transactions" in col and "Commodity" in col:
            sector_col = col
            print(f"\nFOUND Sector Column: '{sector_col}'")
            break
    
    if not sector_col:
        print("\nERROR: Could not find 'Transactions(down)/Commodity(right)' column.")
        return

    # 3. Test Aviation Bunker Row
    target_bunker = "International aviation bunkers"
    print(f"\nSearching for row: '{target_bunker}'...")
    
    # Strip and lower the column for matching
    row = df[df[sector_col].astype(str).str.strip().str.lower() == target_bunker.lower()]
    
    if row.empty:
        print(f"ERROR: Row not found! Here are the available row names:")
        print(df[sector_col].head(10).tolist())
        return
    else:
        print("Row found!")

    # 4. Check Total Energy
    total_raw = row["Total Energy"].iloc[0]
    total_clean = _clean_val(total_raw)
    print(f"Total Energy Raw: '{total_raw}' -> Cleaned: {total_clean}")

    if total_clean == 0:
        print("WARNING: Total Energy is 0. Shares cannot be calculated.")
        return

    # 5. Check Oil Products (The expected fuel)
    print("\nChecking Fuel Columns:")
    fuel_mapping = {
        'oil': ['Primary Oil', 'Oil Products'], 
        'gas': ['Natural Gas'], 
        'electricity': ['Electricity'], 
        'heat': ['Heat']
    }
    
    for fuel, cols in fuel_mapping.items():
        fuel_sum = 0.0
        print(f"  > Checking category '{fuel}'")
        for c in cols:
            if c in df.columns:
                raw_val = row[c].iloc[0]
                val = _clean_val(raw_val)
                fuel_sum += val
                print(f"    - Column '{c}': Raw='{raw_val}' -> Val={val}")
            else:
                print(f"    - Column '{c}': NOT FOUND in CSV")
        
        share = (fuel_sum / total_clean) * 100
        print(f"  = Total {fuel}: {fuel_sum} ({share:.2f}%)")

if __name__ == "__main__":
    test_bunker_logic()