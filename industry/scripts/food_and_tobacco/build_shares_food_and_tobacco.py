# scripts/industry/scripts/food_and_tobacco/build_food_and_tobacco_energy.py
import pandas as pd
from pathlib import Path
from industry.scripts.food_and_tobacco.build_food_and_tobacco_energy import _clean_val


def get_unsd_fuel_shares(base_path: Path, country: str, year: int, sector_name: str = "Food and tobacco"):
    target_categories = ['oil', 'gas', 'electricity', 'coal', 'biomass', 'hydrogen', 'ammonia', 'steel', 'methanol']

    file_candidates = []
    for fp in base_path.glob(f"{country}-*.csv"):
        try:
            y = int(fp.stem.split("-")[-1])
            file_candidates.append((y, fp))
        except Exception:
            continue

    if not file_candidates:
        return {f: 0.0 for f in target_categories}

    # Prefer closest year to requested one; if tie, prefer earlier year
    file_candidates.sort(key=lambda t: (abs(t[0] - int(year)), 0 if t[0] <= int(year) else 1, t[0]))

    row = None
    total_tj = 0.0
    for _, file_path in file_candidates:
        try:
            df = pd.read_csv(file_path)
            sector_col = "Transactions(down)/Commodity(right)"
            if sector_col not in df.columns or "Total Energy" not in df.columns:
                continue

            row_try = df[df[sector_col].astype(str).str.strip().str.lower() == sector_name.lower()]
            if row_try.empty:
                continue

            total_try = _clean_val(row_try["Total Energy"].iloc[0])
            if total_try == 0:
                continue

            row = row_try
            total_tj = total_try
            break
        except Exception:
            continue

    if row is None or total_tj == 0:
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