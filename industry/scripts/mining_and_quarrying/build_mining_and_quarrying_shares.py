import pandas as pd 
from pathlib import Path 
from scripts.mining_and_quarrying.build_mining_and_quarrying_energy import _clean_val

def get_mining_fuel_shares(base_path: Path, country: str, year: int, sector_name: str = "Mining and quarrying"):
    """
    Calculates the percentage shares of each fuel for the Mining sector.
    """
    file_path = base_path / f"{country}-{year}.csv"
    
    # Define all required categories for your metrics dictionary
    fuel_mapping = {
        'oil': ['Primary Oil', 'Oil Products'], 
        'gas': ['Natural Gas'], 
        'electricity': ['Nuclear', 'Electricity'], 
        'coal': ['Primary Coal and Peat', 'Coal and Peat Products'], 
        'biomass': ['Biofuels and Waste'], 
        'hydrogen': [], 
        'ammonia': [], 
        'steel': [], 
        'methanol': []
    }
    
    if not file_path.exists(): 
        return {f: 0.0 for f in fuel_mapping.keys()}
        
    df = pd.read_csv(file_path)
    sector_col = "Transactions(down)/Commodity(right)"
    row = df[df[sector_col].str.strip().str.lower() == sector_name.lower()]
    
    if row.empty: 
        return {f: 0.0 for f in fuel_mapping.keys()}
        
    total_tj = _clean_val(row["Total Energy"].iloc[0])
    
    # Prevent division by zero if sector energy is 0
    if total_tj == 0: 
        return {f: 0.0 for f in fuel_mapping.keys()}

    shares = {}
    for cat, headers in fuel_mapping.items():
        # Sum only headers that actually exist in the CSV columns
        cat_sum = sum([_clean_val(row[h].iloc[0]) for h in headers if h in df.columns])
        # Calculate percentage share
        shares[cat] = round((cat_sum / total_tj) * 100, 4)
        
    return shares