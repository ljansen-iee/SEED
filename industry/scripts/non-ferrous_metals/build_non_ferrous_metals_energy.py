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

def get_non_ferrous_total_GWh(base_path: Path, country: str, year: int, sector_name: str = "Non-ferrous metals"):
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


def get_other_non_ferrous_GWh(
    base_path: Path, 
    country: str, 
    year: int, 
    aluminium_gwh: float,
    sector_name: str = "Non-ferrous metals"
) -> float:
    """
    Calculate residual energy for "other non-ferrous metals" (copper, zinc, lead, etc.).
    
    Methodology:
        other_non_ferrous = total_UNSD - aluminium_detailed
    
    This ensures NO DOUBLE COUNTING:
    - Aluminium gets detailed treatment (production volumes, technology routes, emissions)
    - Other metals get residual UNSD energy (simple projection via CAGR)
    
    Typical breakdown:
        - Aluminium: ~60-70% of non-ferrous energy
        - Copper: ~15-20%
        - Zinc: ~5-10%
        - Others (lead, nickel, etc.): ~5-15%
    
    Args:
        base_path: Path to UNSD historical data folder
        country: Country code (e.g., 'CN', 'US', 'IN')
        year: Historical year
        aluminium_gwh: Aluminium energy from detailed model (GWh)
        sector_name: Sector name in UNSD (default: "Non-ferrous metals")
    
    Returns:
        Energy for other non-ferrous metals (GWh)
        Returns 0.0 if:
            - UNSD data missing
            - Total UNSD < aluminium energy (possible if UNSD incomplete)
    """
    # Get total UNSD energy for non-ferrous sector
    total_unsd_gwh = get_non_ferrous_total_GWh(base_path, country, year, sector_name)
    
    # Calculate residual
    other_gwh = total_unsd_gwh - aluminium_gwh
    
    # Safety: return 0 if residual is negative (means UNSD data incomplete or aluminium model overestimates)
    return max(0.0, round(other_gwh, 2))