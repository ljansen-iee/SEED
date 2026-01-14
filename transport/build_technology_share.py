import pandas as pd
import numpy as np
from helpers import clean_column_headers

def Share_of_Direct_Electric_Passenger_Train(df):
    clean_df = clean_column_headers(df)
    # Extract two-wheeler and three-wheeler occupancy data
    Share_of_Direct_Electric_Passenger_Train = clean_df.iloc[:, list(range(1)) + list(range(246, 257))]
    columns_to_multiply = ['2015.0','2020.0','2025.0','2030.0','2035.0','2040.0','2045.0','2050.0']

# Multiply only specified columns by 100 to get value in % 
    Share_of_Direct_Electric_Passenger_Train.loc[:, columns_to_multiply] *= 100

    return Share_of_Direct_Electric_Passenger_Train


   
def share_technology():
    # --- LDV ---
    technology_gasoline_ice_ldv = 16.7
    technology_diesel_ice_ldv = 83.3
    technology_lpg_ice_ldv = 0.0
    technology_bev_ldv = 0.0
    technology_fcev_ldv = 0.0
    technology_diesel_plugin_hybrid_ldv = 0.0
    technology_gasoline_plugin_hybrid_ldv = 0.0

    # --- Bus ---
    technology_diesel_ice_bus = 100.0
    technology_bev_bus = 0.0
    technology_fcev_bus = 0.0
    technology_diesel_plugin_hybrid_bus = 0.0

    # --- 2&3 Wheelers ---
    technology_gasoline_ice_two_three_wheeler = 100.0
    technology_bev_two_three_wheeler = 0.0

    # --- Passenger Train ---
    technology_fcev_passenger_train = 0.0

    # --- Passenger Plane ---
    technology_kerosene_passenger_plane = 100.0
    technology_bev_passenger_plane = 0.0
    technology_fcev_passenger_plane = 0.0

    # --- Light Duty Trucks (LDT) ---
    technology_diesel_ice_ldt = 100.0
    technology_bev_ldt = 0.0
    technology_fcev_ldt = 0.0
    technology_diesel_plugin_hybrid_ldt = 0.0

    # --- Heavy Duty Trucks (HDT) ---
    technology_diesel_ice_hdt = 100.0
    technology_diesel_plugin_hybrid_hdt = 0.0
    technology_bev_hdt = 0.0
    technology_fcev_hdt = 0.0

    # --- Freight Train ---
    technology_fcev_freight_train = 0.0

    # --- Freight Ship ---
    technology_diesel_ice_freight_ship = 100.0
    technology_methanol_freight_ship = 0.0
    technology_ammonia_freight_ship = 0.0
    technology_bev_freight_ship = 0.0
    technology_fcev_freight_ship = 0.0

    # --- Freight Plane ---
    technology_kerosene_freight_plane = 100.0

    # --- Passenger Ship ---
    technology_diesel_passenger_ship = 100.0

    # --- Biofuels in Road & Aviation ---
    bioethanol_in_road_gasoline = 0.0
    biodiesel_in_road_diesel = 0.0
    biodiesel_in_rail_diesel = 0.0
    biodiesel_in_internal_navigation_diesel = 0.0
    biokerosene_in_internal_aviation_fuel = 0.0  # ✅ fixed
    ice_fuel_in_plugin_hybrid = 0.5

    return (
        # LDV
        technology_gasoline_ice_ldv, technology_diesel_ice_ldv, technology_lpg_ice_ldv,
        technology_bev_ldv, technology_fcev_ldv,
        technology_diesel_plugin_hybrid_ldv, technology_gasoline_plugin_hybrid_ldv,

        # Bus
        technology_diesel_ice_bus, technology_bev_bus, technology_fcev_bus, technology_diesel_plugin_hybrid_bus,

        # 2&3W
        technology_gasoline_ice_two_three_wheeler, technology_bev_two_three_wheeler,

        # Passenger Train
        technology_fcev_passenger_train,

        # Passenger Plane
        technology_kerosene_passenger_plane, technology_bev_passenger_plane, technology_fcev_passenger_plane,

        # LDT
        technology_diesel_ice_ldt, technology_bev_ldt, technology_fcev_ldt, technology_diesel_plugin_hybrid_ldt,

        # HDT
        technology_diesel_ice_hdt, technology_bev_hdt, technology_fcev_hdt, technology_diesel_plugin_hybrid_hdt,

        # Freight Train
        technology_fcev_freight_train,

        # Freight Ship
        technology_diesel_ice_freight_ship, technology_methanol_freight_ship, technology_ammonia_freight_ship,
        technology_bev_freight_ship, technology_fcev_freight_ship,

        # Freight Plane
        technology_kerosene_freight_plane,

        # Passenger Ship
        technology_diesel_passenger_ship,

        # Biofuels
        bioethanol_in_road_gasoline, biodiesel_in_road_diesel, biodiesel_in_rail_diesel,
        biodiesel_in_internal_navigation_diesel, biokerosene_in_internal_aviation_fuel,
        ice_fuel_in_plugin_hybrid
    )


TECHNOLOGY_OVERRIDES = {
    "Share of Technology - Gasoline ICE LDV": {
        "2030_Baseline": 0.1670,
        "2030_RF": 0.6800,
        "2030_EL": 0.6800,
        "2050_Baseline": 0.1670,
        "2050_RF": 0.0800,
        "2050_EL": 0.0300,
    },
    "Share of Technology - Diesel ICE LDV": {
        "2030_Baseline": 0.8330,
        "2030_RF": 0.2500,
        "2030_EL": 0.2000,
        "2050_Baseline": 0.8330,
        "2050_RF": 0.1000,
        "2050_EL": 0.0100,
    },
    "Share of Technology - BEV LDV": {
        "2030_Baseline": 0.0000,
        "2030_RF": 0.0600,
        "2030_EL": 0.1200,
        "2050_Baseline": 0.0000,
        "2050_RF": 0.7500,
        "2050_EL": 0.9600,
    },
    "Share of Technology - FCEV LDV": {
        "2030_Baseline": 0.0000,
        "2030_RF": 0.0100,
        "2030_EL": 0.0000,
        "2050_Baseline": 0.0000,
        "2050_RF": 0.0700,
        "2050_EL": 0.0000,
    },
    "Share of Technology - Diesel ICE Bus": {
        "2030_Baseline": 1.0000,
        "2030_RF": 0.9300,
        "2030_EL": 0.8800,
        "2050_Baseline": 1.0000,
        "2050_RF": 0.1800,
        "2050_EL": 0.0400,
    },
    "Share of Technology - BEV Bus": {
        "2030_Baseline": 0.0000,
        "2030_RF": 0.0600,
        "2030_EL": 0.1200,
        "2050_Baseline": 0.0000,
        "2050_RF": 0.7500,
        "2050_EL": 0.9600,
    },
    "Share of Technology - FCEV Bus": {
        "2030_Baseline": 0.0000,
        "2030_RF": 0.0100,
        "2030_EL": 0.0000,
        "2050_Baseline": 0.0000,
        "2050_RF": 0.0700,
        "2050_EL": 0.0000,
    },
    "Share of Technology - Gasoline ICE 2&3W": {
        "2030_Baseline": 1.0000,
        "2030_RF": 0.9400,
        "2030_EL": 0.8800,
        "2050_Baseline": 1.0000,
        "2050_RF": 0.2000,
        "2050_EL": 0.1000,
    },
    "Share of Technology - BEV 2&3W": {
        "2030_Baseline": 0.0000,
        "2030_RF": 0.0600,
        "2030_EL": 0.1200,
        "2050_Baseline": 0.0000,
        "2050_RF": 0.8000,
        "2050_EL": 0.9000,
    },
    "Share of Technology - Diesel ICE Passenger Train": {
        "2030_Baseline": 0.0000,
        "2030_RF": 0.0000,
        "2030_EL": 0.0000,
        "2050_Baseline": 0.0000,
        "2050_RF": 0.0000,
        "2050_EL": 0.0000,
    },
    "Share of Technology - Direct Electric Passenger Train": {
        "2030_Baseline": 1.0000,
        "2030_RF": 1.0000,
        "2030_EL": 1.0000,
        "2050_Baseline": 1.0000,
        "2050_RF": 0.9800,
        "2050_EL": 0.9800,
    },
    "Share of Technology - FCEV Passenger Train": {
        "2030_Baseline": 0.0000,
        "2030_RF": 0.0000,
        "2030_EL": 0.0000,
        "2050_Baseline": 0.0000,
        "2050_RF": 0.0200,
        "2050_EL": 0.0200,
    },
    "Share of Technology - Kerosene Passenger Plane": {
        "2030_Baseline": 1.0000,
        "2030_RF": 1.0000,
        "2030_EL": 1.0000,
        "2050_Baseline": 1.0000,
        "2050_RF": 1.0000,
        "2050_EL": 1.0000,
    },
        # Light Duty Trucks (LDT)
    "Share of Technology - Diesel ICE LDT": {
        "2030_Baseline": 1.0000,
        "2030_RF": 0.9300,
        "2030_EL": 0.8800,
        "2050_Baseline": 0.9500,
        "2050_RF": 0.1600,
        "2050_EL": 0.0700,
    },
    "Share of Technology - BEV LDT": {
        "2030_Baseline": 0.0000,
        "2030_RF": 0.0600,
        "2030_EL": 0.1200,
        "2050_Baseline": 0.0500,
        "2050_RF": 0.7500,
        "2050_EL": 0.9200,
    },
    "Share of Technology - FCEV LDT": {
        "2030_Baseline": 0.0000,
        "2030_RF": 0.0100,
        "2030_EL": 0.0000,
        "2050_Baseline": 0.0000,
        "2050_RF": 0.0900,
        "2050_EL": 0.0100,
    },
    "Share of Technology - Diesel Plugin Hybrid LDT": {
        "2030_Baseline": 0.0000,
        "2030_RF": 0.0000,
        "2030_EL": 0.0000,
        "2050_Baseline": 0.0000,
        "2050_RF": 0.0000,
        "2050_EL": 0.0000,
    },

    # Heavy Duty Trucks (HDT)
    "Share of Technology - Diesel ICE HDT": {
        "2030_Baseline": 1.0000,
        "2030_RF": 0.9300,
        "2030_EL": 0.8800,
        "2050_Baseline": 0.9500,
        "2050_RF": 0.1600,
        "2050_EL": 0.0700,
    },
    "Share of Technology - BEV HDT": {
        "2030_Baseline": 0.0000,
        "2030_RF": 0.0600,
        "2030_EL": 0.1200,
        "2050_Baseline": 0.0500,
        "2050_RF": 0.7500,
        "2050_EL": 0.9200,
    },
    "Share of Technology - FCEV HDT": {
        "2030_Baseline": 0.0000,
        "2030_RF": 0.0100,
        "2030_EL": 0.0000,
        "2050_Baseline": 0.0000,
        "2050_RF": 0.0900,
        "2050_EL": 0.0100,
    },
    "Share of Technology - Diesel Plugin Hybrid HDT": {
        "2030_Baseline": 0.0000,
        "2030_RF": 0.0000,
        "2030_EL": 0.0000,
        "2050_Baseline": 0.0000,
        "2050_RF": 0.0000,
        "2050_EL": 0.0000,
    },

    # Freight Train
    "Share of Technology - Diesel ICE Freight Train": {
        "2030_Baseline": 0.4220,
        "2030_RF": 0.3500,
        "2030_EL": 0.3000,
        "2050_Baseline": 0.4220,
        "2050_RF": 0.3000,
        "2050_EL": 0.2500,
    },
    "Share of Technology - Direct Electric Freight Train": {
        "2030_Baseline": 0.5780,
        "2030_RF": 0.6500,
        "2030_EL": 0.7000,
        "2050_Baseline": 0.5780,
        "2050_RF": 0.6500,
        "2050_EL": 0.7000,
    },
    "Share of Technology - FCEV Freight Train": {
        "2030_Baseline": 0.0000,
        "2030_RF": 0.0000,
        "2030_EL": 0.0000,
        "2050_Baseline": 0.0000,
        "2050_RF": 0.0500,
        "2050_EL": 0.0500,
    },

    # Freight Ship
    "Share of Technology - Diesel ICE Freight Ship": {
        "2030_Baseline": 1.0000,
        "2030_RF": 0.6500,
        "2030_EL": 0.4000,
        "2050_Baseline": 1.0000,
        "2050_RF": 0.0000,
        "2050_EL": 0.5000,
    },
    "Share of Technology - Methanol Freight Ship": {
        "2030_Baseline": 0.0000,
        "2030_RF": 0.2500,
        "2030_EL": 0.3000,
        "2050_Baseline": 0.0000,
        "2050_RF": 0.5000,
        "2050_EL": 0.1000,
    },
    "Share of Technology - Ammonia Freight Ship": {
        "2030_Baseline": 0.0000,
        "2030_RF": 0.1000,
        "2030_EL": 0.2000,
        "2050_Baseline": 0.0000,
        "2050_RF": 0.3500,
        "2050_EL": 0.3800,
    },
    "Share of Technology - BEV Freight Ship": {
        "2030_Baseline": 0.0000,
        "2030_RF": 0.0000,
        "2030_EL": 0.0000,
        "2050_Baseline": 0.0000,
        "2050_RF": 0.0000,
        "2050_EL": 0.0000,
    },
    "Share of Technology - FCEV Freight Ship": {
        "2030_Baseline": 0.0000,
        "2030_RF": 0.0000,
        "2030_EL": 0.1000,
        "2050_Baseline": 0.0000,
        "2050_RF": 0.1500,
        "2050_EL": 0.0200,
    },
    "Share of Technology - Kerosene Freight Plane": {
        "2030_Baseline": 1.0000,
        "2030_RF": 1.0000,
        "2030_EL": 1.0000,
        "2050_Baseline": 1.0000,
        "2050_RF": 1.0000,
        "2050_EL": 1.0000,
    },
    "Share of Technology - Diesel Passenger Ship": {
        "2030_Baseline": 1.0000,
        "2030_RF": 1.0000,
        "2030_EL": 1.0000,
        "2050_Baseline": 1.0000,
        "2050_RF": 1.0000,
        "2050_EL": 1.0000,
    },
    "Share of Bioethanol in Road Gasoline": {
        "Units": "%",
        "2020": 0.00,
        "2030_Baseline": 0.00,
        "2030_RF": 0.00,
        "2030_EL": 0.00,
        "2050_Baseline": 0.00,
        "2050_RF": 0.00,
        "2050_EL": 0.00,
    },
    "Share of Biodiesel in Road Diesel": {
        "Units": "%",
        "2020": 0.00,
        "2030_Baseline": 0.00,
        "2030_RF": 0.00,
        "2030_EL": 0.00,
        "2050_Baseline": 0.00,
        "2050_RF": 0.00,
        "2050_EL": 0.00,
    },
    "Share of Biodiesel in Rail Diesel": {
        "Units": "%",
        "2020": 0.00,
        "2030_Baseline": 0.00,
        "2030_RF": 0.00,
        "2030_EL": 0.00,
        "2050_Baseline": 0.00,
        "2050_RF": 0.00,
        "2050_EL": 0.00,
    },
    "Share of Biodiesel in Internal Navigation Diesel": {
        "Units": "%",
        "2020": 0.00,
        "2030_Baseline": 0.00,
        "2030_RF": 0.02,
        "2030_EL": 0.04,
        "2050_Baseline": 0.00,
        "2050_RF": 0.20,
        "2050_EL": 0.45,
    },
    "Share of Biokerosene in Internal Aviation Fuel": {
        "Units": "%",
        "2020": 0.00,
        "2030_Baseline": 0.00,
        "2030_RF": 0.02,
        "2030_EL": 0.04,
        "2050_Baseline": 0.00,
        "2050_RF": 0.20,
        "2050_EL": 0.25,
    },
    "Share of ICE Fuel in Plugin Hybrid": {
        "Units": "%",
        "2020": 0.5,
        "2030_Baseline": 0.5,
        "2030_RF": 0.5,
        "2030_EL": 0.5,
        "2050_Baseline": 0.5,
        "2050_RF": 0.5,
        "2050_EL": 0.5,
    },
}

TECHNOLOGY_GROUPS = {
    "LDV": [
        "Share of Technology - Gasoline ICE LDV",
        "Share of Technology - Diesel ICE LDV",
        "Share of Technology - LPG ICE LDV",
        "Share of Technology - BEV LDV",
        "Share of Technology - FCEV LDV",
        "Share of Technology - Diesel Plugin Hybrid LDV",
        "Share of Technology - Gasoline Plugin Hybrid LDV",
    ],
    "Bus": [
        "Share of Technology - Diesel ICE Bus",
        "Share of Technology - BEV Bus",
        "Share of Technology - FCEV Bus",
        "Share of Technology - Diesel Plugin Hybrid Bus",
    ],
    "2&3W": [
        "Share of Technology - Gasoline ICE 2&3W",
        "Share of Technology - BEV 2&3W",
    ],
    "Passenger Train": [
        "Share of Technology - Diesel ICE Passenger Train",
        "Share of Technology - Direct Electric Passenger Train",
        "Share of Technology - FCEV Passenger Train",
    ],
    "Passenger Plane": [
        "Share of Technology - Kerosene Passenger Plane",
        "Share of Technology - BEV Passenger Plane",
        "Share of Technology - FCEV Passenger Plane",
    ],
    "Light Duty Truck": [
    "Share of Technology - Diesel ICE LDT",
    "Share of Technology - BEV LDT",
    "Share of Technology - FCEV LDT",
    "Share of Technology - Diesel Plugin Hybrid LDT",
    ],
    "Heavy Duty Truck": [
        "Share of Technology - Diesel ICE HDT",
        "Share of Technology - BEV HDT",
        "Share of Technology - FCEV HDT",
        "Share of Technology - Diesel Plugin Hybrid HDT",
    ],
    "Freight Train": [
        "Share of Technology - Diesel ICE Freight Train",
        "Share of Technology - Direct Electric Freight Train",
        "Share of Technology - FCEV Freight Train",
    ],
    "Freight Ship": [
        "Share of Technology - Diesel ICE Freight Ship",
        "Share of Technology - Methanol Freight Ship",
        "Share of Technology - Ammonia Freight Ship",
        "Share of Technology - BEV Freight Ship",
        "Share of Technology - FCEV Freight Ship",
    ],

    "Passenger Ship": [
    "Share of Technology - Diesel Passenger Ship",
    ],
    "Freight Plane": [
        "Share of Technology - Kerosene Freight Plane",
    ]
}

def enforce_share_constraints(rows):
    """
    Check if technology shares exceed 100% for 2030/2050.
    - Leave 2020 values untouched.
    - Only print a warning if >100% in 2030/2050.
    - Do NOT normalize automatically.
    """
    df = pd.DataFrame(rows)

    #  Only check future years, never 2020
    year_cols = ["2030_Baseline", "2030_RF", "2030_EL",
                 "2050_Baseline", "2050_RF", "2050_EL"]

    for subsector, metrics in TECHNOLOGY_GROUPS.items():
        subset = df[df["Metric"].isin(metrics)]

        if subset.empty:
            continue  # no data for this subsector, skip

        for year in year_cols:
            if year not in df.columns:
                continue

            total = subset[year].sum()

            # Only warn if it crosses 100%
            if total > 100.0 + 1e-6:  # small tolerance
                print(f" {subsector} shares in {year} = {total:.2f}, exceeds 100%")

    #  Return untouched values (2020 remains same as extracted)
    return df.to_dict("records")


TECH_SHARE_METRICS = [
    "Share of Technology - Gasoline ICE LDV",
    "Share of Technology - Diesel ICE LDV",
    "Share of Technology - BEV LDV",
    "Share of Technology - FCEV LDV",
    "Share of Technology - Diesel ICE Bus",
    "Share of Technology - BEV Bus",
    "Share of Technology - FCEV Bus",
    "Share of Technology - Gasoline ICE 2&3W",
    "Share of Technology - BEV 2&3W",
    "Share of Technology - Diesel ICE Passenger Train",
    "Share of Technology - Direct Electric Passenger Train",
    "Share of Technology - FCEV Passenger Train",
    "Share of Technology - Kerosene Passenger Plane",
    "Share of Technology - Kerosene Freight Plane",
    "Share of Technology - Diesel Passenger Ship",

]

def convert_shares_to_percent_numbers(df):
    """
    Convert selected technology shares from fractions (0.167) to numbers (16.70).
    """
    year_cols = ["2020", "2030_Baseline", "2030_RF", "2030_EL",
                 "2050_Baseline", "2050_RF", "2050_EL"]

    mask = df["Metric"].isin(TECH_SHARE_METRICS)
    for col in year_cols:
        if col in df.columns:
            df.loc[mask, col] = df.loc[mask, col].apply(
                lambda x: round(x * 100, 2) if pd.notnull(x) and not isinstance(x, str) else x
            )
    return df

def interpolate_overrides(metric, year, scenario):
    """
    Interpolates between 2030 and 2050 TECHNOLOGY_OVERRIDES values
    for intermediate years (e.g. 2035, 2040, 2045).
    Returns None if no override exists for the metric.
    """
    if metric not in TECHNOLOGY_OVERRIDES:
        return None

    overrides = TECHNOLOGY_OVERRIDES[metric]
    y0, y1 = 2030, 2050
    key0, key1 = f"{y0}_{scenario}", f"{y1}_{scenario}"

    if key0 not in overrides or key1 not in overrides:
        return None  # not enough data to interpolate

    v0, v1 = overrides[key0], overrides[key1]

    if year <= y0:
        return v0
    if year >= y1:
        return v1

    # linear interpolation
    frac = (year - y0) / (y1 - y0)
    return v0 + (v1 - v0) * frac


def apply_technology_overrides(rows, target_years, scenarios):
    """
    Apply manual overrides (TECHNOLOGY_OVERRIDES) for 2030/2050
    and interpolate values for intermediate years.
    """
    new_rows = []
    for row in rows:
        metric = row["Metric"]
        if metric not in TECHNOLOGY_OVERRIDES:
            new_rows.append(row)
            continue

        overrides = TECHNOLOGY_OVERRIDES[metric]

        for year in target_years:
            for scenario in scenarios:
                key = f"{year}_{scenario}"
                if key in overrides:
                    row[key] = overrides[key] # stored as fraction → convert %
                else:
                    # interpolate between 2030 and 2050
                    interpolated = interpolate_overrides(metric, year, scenario)
                    if interpolated is not None:
                        row[key] = interpolated * 100.0

        new_rows.append(row)

    return new_rows

def normalize_shares(rows, groups):
    """
    Ensure that technology shares within each group sum to 100% for all years.
    Example: LDV (Gasoline + Diesel + BEV + FCEV + Hybrids = 100).
    """
    df = pd.DataFrame(rows)

    year_cols = [c for c in df.columns if c not in ["Metric", "Units"]]

    for group, metrics in groups.items():
        subset = df[df["Metric"].isin(metrics)]
        if subset.empty:
            continue

        for col in year_cols:
            if col not in df.columns:
                continue
            total = subset[col].sum()
            if total > 0:
                scale = 100.0 / total
                df.loc[df["Metric"].isin(metrics), col] *= scale

    return df.to_dict("records")
