# build_hvc_production.py
import pandas as pd
from pathlib import Path

# ==============================
# CONFIG
# ==============================
UTILIZATION_FACTOR = 0.9

feedstock_shares = {
    "naphtha": 0.60,
    "LPG": 0.25,
    "methanol": 0.15
}

conversion_factors_kt_per_kbd = {
    "naphtha": 41.6,
    "LPG": 33.2,
    "methanol": 46.0
}

# Weighted conversion factor (kt/year per 1000 bpd)
weighted_kt_per_kbd = sum(
    feedstock_shares[fuel] * conversion_factors_kt_per_kbd[fuel]
    for fuel in feedstock_shares
)


# ==============================
# FILE DISCOVERY
# ==============================
def find_industrial_database():
    """
    Locate industrial_database.csv inside:
    industry/input_data/petrochemicals/
    """

    # Go up to the industry/ root folder
    base_path = Path(__file__).resolve().parents[3]

    search_path = base_path / "input_data" / "petrochemicals"

    file_path = search_path / "industrial_database.csv"

    if file_path.exists():
        return file_path

    raise FileNotFoundError(
        f"industrial_database.csv not found in:\n{search_path}"
    )


# ==============================
# CONVERSION LOGIC
# ==============================
def convert_to_t_per_year(row):
    unit = str(row["unit"]).lower()
    capacity = row["capacity"]

    if unit == "bpd":
        return capacity * weighted_kt_per_kbd * UTILIZATION_FACTOR

    elif unit in ["kt/yr", "kt/year"]:
        return capacity * 1000 * UTILIZATION_FACTOR

    elif unit == "10kt/yr":
        return capacity * 10000 * UTILIZATION_FACTOR

    else:
        return None


# ==============================
# MAIN FUNCTION
# ==============================
def get_hvc_production(add_country_names=True):
    """
    Returns HVC production by country as a DataFrame.
    """

    csv_path = find_industrial_database()
    df = pd.read_csv(csv_path)

    df.drop(columns=['y', 'x', 'ID'], inplace=True, errors='ignore')

    # Filter HVC
    hvc_df = df[df["technology"] == "HVC"].copy()
    if hvc_df.empty:
        raise ValueError("No HVC technology found")

    # Convert units
    hvc_df["HVC_production_t_per_year"] = hvc_df.apply(convert_to_t_per_year, axis=1)
    hvc_df = hvc_df.dropna(subset=["HVC_production_t_per_year"])

    # Aggregate
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
                except:
                    return None

            result["country_name"] = result["country"].apply(iso_to_name)
        except ImportError:
            pass

    return result
