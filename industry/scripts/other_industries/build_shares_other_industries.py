"""
Extract fuel shares for 'Industry n.e.s' sector from UNSD historical data.

Industry n.e.s (not elsewhere specified) is a catch-all UNSD sector for
industrial activities not classified under specific sectors like steel,
cement, chemicals, etc.

Examples include:
- Small-scale manufacturing
- Handicrafts and artisanal production
- Miscellaneous industrial services
- Country-specific industries
"""

from pathlib import Path
import pandas as pd
from industry.utils.helpers import get_fuel_shares_from_unsd


# UNSD sector name (must match UNSD CSV exactly)
UNSD_SECTOR_NAME = "Industry n.e.s"

# Clean value helper (copied from food_and_tobacco for consistency)
def _clean_val(val):
    """Convert messy numeric strings to float."""
    if pd.isna(val):
        return 0.0
    s = str(val).strip()
    if s in ["---", "", "-", "None", "nan", "NaN"]:
        return 0.0
    try:
        return float(s.replace("*", "").replace(",", ""))
    except:
        return 0.0


def get_unsd_fuel_shares(base_path: Path, country: str, year: int, sector_name: str = "Industry n.e.s") -> dict:
    """
    Get fuel shares for 'Industry n.e.s' sector from UNSD data.
    
    Args:
        base_path: Path to UNSD data folder
        country: Country name (e.g., 'Morocco', 'Egypt')
        year: Year for historical data (e.g., 2020)
        sector_name: UNSD sector name (default: "Industry n.e.s")
    
    Returns:
        Dictionary with fuel shares as percentages: {'oil': 30.0, 'gas': 25.0, ...}
    """
    target_categories = ['oil', 'gas', 'electricity', 'coal', 'biomass', 'hydrogen', 'ammonia', 'steel', 'methanol']

    # Find files for this country
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
        'hydrogen': [], 
        'ammonia': [], 
        'methanol': []
    }

    shares = {}
    for cat, headers in fuel_mapping.items():
        cat_sum = sum([_clean_val(row[h].iloc[0]) for h in headers if h in row.columns])
        shares[cat] = round((cat_sum / total_tj) * 100, 4)
        
    return shares


if __name__ == "__main__":
    """Test fuel share extraction for Industry n.e.s."""
    import sys
    
    test_countries = ['Morocco', 'Egypt', 'South Africa', 'Namibia']
    test_year = 2020
    
    print("=" * 80)
    print(f"FUEL SHARES EXTRACTION - {UNSD_SECTOR_NAME}")
    print("=" * 80)
    
    for country in test_countries:
        print(f"\n{country} ({test_year}):")
        print("-" * 40)
        
        shares = get_unsd_fuel_shares(country, test_year)
        
        if shares is None:
            print("  ⚠ No data available")
        else:
            total = sum(shares.values())
            print(f"  Total share: {total:.4f} (should be ~1.0)")
            print("\n  Fuel breakdown:")
            for fuel, share in sorted(shares.items(), key=lambda x: -x[1]):
                if share > 0:
                    print(f"    {fuel:12s}: {share*100:6.2f}%")
    
    print("\n" + "=" * 80)
    print("✓ Fuel shares extraction test complete")
    print("=" * 80)
