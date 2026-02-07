import pandas as pd
from pathlib import Path
from scripts.construction.build_construction_energy import _clean_val


def get_construction_fuel_shares(base_path: Path, country: str, year: int, sector_name: str = "Manufacturing  const. and mining"):
    file_path = base_path / f"{country}-{year}.csv"
    target_categories = ['oil', 'gas', 'electricity', 'coal', 'biomass', 'hydrogen', 'ammonia', 'steel', 'methanol']
    
    if not file_path.exists(): 
        return {f: 0.0 for f in target_categories}
        
    df = pd.read_csv(file_path)
    sector_col = "Transactions(down)/Commodity(right)"
    row = df[df[sector_col].str.strip().str.lower() == sector_name.lower()]
    
    if row.empty: 
        return {f: 0.0 for f in target_categories}
        
    total_tj = _clean_val(row["Total Energy"].iloc[0])
    if total_tj == 0: 
        return {f: 0.0 for f in target_categories}

    fuel_mapping = {
        'oil': ['Primary Oil', 'Oil Products'], 
        'gas': ['Natural Gas'], 
        'electricity': ['Nuclear', 'Electricity'], 
        'coal': ['Primary Coal and Peat', 'Coal and Peat Products'], 
        'biomass': ['Biofuels and Waste'], 
        'hydrogen': [], 'ammonia': [], 'steel': [], 'methanol': []
    }

    shares = {}
    for cat, headers in fuel_mapping.items():
        cat_sum = sum([_clean_val(row[h].iloc[0]) for h in headers if h in row.columns])
        shares[cat] = round((cat_sum / total_tj) * 100, 4)
        
    return shares