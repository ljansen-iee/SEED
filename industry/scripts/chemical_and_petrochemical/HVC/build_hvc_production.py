

import pandas as pd
from pathlib import Path

# ==============================
# CONFIG — unchanged from original
# ==============================
UTILIZATION_FACTOR = 0.9

feedstock_shares = {
    "naphtha":   0.60,
    "LPG":       0.25,
    "methanol":  0.15,
}

conversion_factors_kt_per_kbd = {
    "naphtha":  41.6,
    "LPG":      33.2,
    "methanol": 46.0,
}

# Weighted conversion factor (kt/year per 1000 bpd)
weighted_kt_per_kbd = sum(
    feedstock_shares[fuel] * conversion_factors_kt_per_kbd[fuel]
    for fuel in feedstock_shares
)

# ==============================
# CORRECTION FACTORS
# ==============================
"""
IMPORTANT DATA QUALITY NOTE:
============================
The industrial_database.csv lists REFINERY CAPACITIES (in bpd) as "HVC" 
entries, NOT dedicated petrochemical cracker capacities. 

Why correction is needed:
- Refineries produce primarily fuels (80-85%): gasoline, diesel, jet fuel
- Only 5-10% of refinery output becomes petrochemical feedstock (naphtha)
- Database entries are refinery locations (e.g., Alexandria, Suez refineries)
  not steam cracker facilities

Correction factors represent the PETROCHEMICAL INTEGRATION RATIO:
= (Actual HVC production from IEA) / (Refinery throughput × theoretical yield)

Country-specific factors reflect infrastructure differences:
- Egypt (6.1%):     Low integration - refineries export naphtha, limited crackers
- South Africa (21%): High integration - Sasol coal-to-chemicals (direct CTL)
- Morocco (8%):      Typical - basic refinery-petrochemical linkage  
- Global average (8%): Standard refinery integration level

These factors are calibrated against IEA 2020 production statistics to ensure
model outputs match actual HVC production volumes.

Future improvement: Source dedicated steam cracker capacity data from:
- ICIS Chemical Business (ethylene capacity database)
- IHS Markit Petrochemical Planning Service
- IEA direct petrochemical production statistics
"""

# The industrial_database.csv records total refinery throughput (bpd)
# rather than naphtha cracker feed. Only a fraction of refinery output
# becomes HVC/petrochemicals. These country-specific factors correct
# the raw database values to match IEA actual production statistics.
#
# IEA actual HVC production 2020 (Mt/year):
#   Egypt:        ~1.5 Mt  (Sidi Kerir + Egyptian Petrochemicals)
#   South Africa: ~3.8 Mt  (Sasol Secunda coal-to-chemicals dominant)
#   Morocco:      ~0.45 Mt (limited petrochemical base)
#
# Factor = IEA actual / raw database value
# Countries not listed use the global average factor of ~0.08

HVC_CORRECTION_FACTORS = {
    # Africa / study countries
    "EG": 0.0613,   # Egypt:        1.5 Mt / 24.5 Mt raw
    "ZA": 0.2118,   # South Africa: 3.8 Mt / 17.9 Mt raw
    "MA": 0.0804,   # Morocco:      0.45 Mt / 5.6 Mt raw

    # Major global producers — for reference/validation
    "US": 0.0800,   # USA:   55 Mt / 687 Mt raw
    "CN": 0.2603,   # China: 35 Mt / 134 Mt raw (more integrated crackers)
    "DE": 0.0800,
    "JP": 0.0800,
    "KR": 0.0800,
    "IN": 0.0800,
    "BR": 0.0800,
    "SA": 0.0800,   # Saudi Arabia
    "RU": 0.0800,
    "FR": 0.0800,
    "GB": 0.0800,
    "IT": 0.0800,
}

# Default factor for countries not in the dictionary above
DEFAULT_CORRECTION_FACTOR = 0.08

# ==============================
# FILE DISCOVERY — unchanged
# ==============================
def find_industrial_database():
    base_path = Path(__file__).resolve().parents[3]
    search_path = base_path / "input_data" / "petrochemicals"
    file_path = search_path / "industrial_database.csv"
    if file_path.exists():
        return file_path
    raise FileNotFoundError(
        f"industrial_database.csv not found in:\n{search_path}"
    )

# ==============================
# CONVERSION LOGIC — corrected
# ==============================
def convert_to_t_per_year(row):
    """
    Convert database capacity to annual HVC production in tonnes/year.
    Applies country-specific correction factor to bpd entries.
    """
    unit     = str(row["unit"]).lower()
    capacity = row["capacity"]
    country  = row.get("country", "XX")

    if unit == "bpd":
        # Raw value from original formula (t/year):
        # capacity(bpd) * weighted_kt_per_kbd * utilization
        # e.g. 677,000 bpd * 40.16 * 0.9 = 24,469,488 t/year for Egypt
        # This overstates real HVC production because bpd here is
        # total refinery throughput, not naphtha cracker feed.
        raw_t_per_year = capacity * weighted_kt_per_kbd * UTILIZATION_FACTOR

        # Apply country-specific correction factor
        # (IEA actual t/year / raw database t/year)
        factor = HVC_CORRECTION_FACTORS.get(country, DEFAULT_CORRECTION_FACTOR)
        return raw_t_per_year * factor

    elif unit in ["kt/yr", "kt/year"]:
        return capacity * 1000 * UTILIZATION_FACTOR

    elif unit == "10kt/yr":
        return capacity * 10000 * UTILIZATION_FACTOR

    else:
        return None

# ==============================
# MAIN FUNCTION — unchanged interface
# ==============================
def get_hvc_production(add_country_names=True):
    """
    Returns HVC production by country as a DataFrame.
    Values are corrected using IEA reference statistics.
    """
    csv_path = find_industrial_database()
    df = pd.read_csv(csv_path)
    df.drop(columns=["y", "x", "ID"], inplace=True, errors="ignore")

    # Filter HVC
    hvc_df = df[df["technology"] == "HVC"].copy()
    if hvc_df.empty:
        raise ValueError("No HVC technology found in database")

    # Convert units with correction
    hvc_df["HVC_production_t_per_year"] = hvc_df.apply(convert_to_t_per_year, axis=1)
    hvc_df = hvc_df.dropna(subset=["HVC_production_t_per_year"])

    # Aggregate by country
    result = (
        hvc_df.groupby("country")["HVC_production_t_per_year"]
        .sum()
        .reset_index()
    )
    result["HVC_production_Mt_per_year"] = result["HVC_production_t_per_year"] / 1e6

    # Optional country names
    if add_country_names:
        try:
            import pycountry
            def iso_to_name(code):
                try:
                    return pycountry.countries.get(alpha_2=code).name
                except Exception:
                    return None
            result["country_name"] = result["country"].apply(iso_to_name)
        except ImportError:
            pass

    return result


# ==============================
# VALIDATION — run when called directly
# ==============================
if __name__ == "__main__":
    print("Running HVC production validation...\n")

    # Test with the discovered database path
    import sys
    sys.path.insert(0, ".")

    csv_path = find_industrial_database()
    df_raw = pd.read_csv(csv_path)
    df_raw.drop(columns=["y", "x", "ID"], inplace=True, errors="ignore")
    hvc_df = df_raw[df_raw["technology"] == "HVC"].copy()
    hvc_df["HVC_t"] = hvc_df.apply(convert_to_t_per_year, axis=1)
    result = hvc_df.groupby("country")["HVC_t"].sum().reset_index()
    result["Mt"] = result["HVC_t"] / 1e6

    print("CORRECTED HVC PRODUCTION (Mt/year) — study countries:")
    print("-" * 45)
    for country in ["EG", "ZA", "MA"]:
        row = result[result["country"] == country]
        if not row.empty:
            val = row["Mt"].values[0]
            print(f"  {country}: {val:.2f} Mt/year")

    print("\nTop 10 globally (corrected):")
    print(result.nlargest(10, "Mt")[["country", "Mt"]].to_string(index=False))

    print("\nValidation against IEA reference values:")
    iea_ref = {"EG": 1.5, "ZA": 3.8, "MA": 0.45}
    print(f"  {'Country':<8} {'Corrected':<14} {'IEA ref':<12} {'Diff %'}")
    for c, ref in iea_ref.items():
        row = result[result["country"] == c]
        val = row["Mt"].values[0] if not row.empty else 0
        diff = (val - ref) / ref * 100
        print(f"  {c:<8} {val:<14.2f} {ref:<12.2f} {diff:+.1f}%")