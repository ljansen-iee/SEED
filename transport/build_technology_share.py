# build_technology_share.py

import pandas as pd
import numpy as np
from helpers import clean_column_headers
from build_CAGR import expand_with_cagr, get_cagr
# =============================================================================
#  HELPER: Interpolate Overrides
# =============================================================================
def interpolate_overrides(metric, year, scenario, overrides):
    """
    Interpolates between 2030 and 2050 values for intermediate years.
    """
    y0, y1 = 2030, 2050
    key0, key1 = f"{y0}_{scenario}", f"{y1}_{scenario}"

    if key0 not in overrides or key1 not in overrides:
        return None 

    v0, v1 = overrides[key0], overrides[key1]

    # Safety: No extrapolation
    if year <= y0: return v0
    if year >= y1: return v1

    # Linear interpolation
    frac = (year - y0) / (y1 - y0)
    return v0 + (v1 - v0) * frac



def apply_technology_overrides(rows, target_years, scenarios, CAGR_VALUES, ASSUMPTION_TYPES):

    new_rows = []

    tech_metrics = {
        m for m, t in ASSUMPTION_TYPES.items() if t == "TECH_SHARE"
    }

    excel_overrides = {}

    for metric in tech_metrics:
        if metric not in CAGR_VALUES:
            continue

        values_dict = CAGR_VALUES.get(metric, {})

        if not isinstance(values_dict, dict):
            continue

        excel_overrides[metric] = {}

        for year, scen_dict in values_dict.items():
            if not isinstance(scen_dict, dict):
                continue

            for scen, val in scen_dict.items():
                key = f"{year}_{scen}"
                excel_overrides[metric][key] = float(val)

    for row in rows:
        metric = row["Metric"]
        base_value = row.get("2020", 0.0)

        overrides = excel_overrides.get(metric, {})

        for year in target_years:
            for scenario in scenarios:
                key = f"{year}_{scenario}"

                if key in overrides:
                    row[key] = overrides[key]
                else:
                    row[key] = base_value

        new_rows.append(row)

    return new_rows





# =============================================================================
#  BASE YEAR DEFINITIONS (2020)
# =============================================================================

def Share_of_Direct_Electric_Passenger_Train(df):
    clean_df = clean_column_headers(df)
    Share_of_Direct_Electric_Passenger_Train = clean_df.iloc[:, list(range(1)) + list(range(246, 257))]
    columns_to_multiply = ['2015.0','2020.0','2025.0','2030.0','2035.0','2040.0','2045.0','2050.0']
    Share_of_Direct_Electric_Passenger_Train.loc[:, columns_to_multiply] *= 100
    return Share_of_Direct_Electric_Passenger_Train

def share_technology():
    # Base values (2020) - Starting point
    
    # LDV
    technology_gasoline_ice_ldv = 0.167
    technology_diesel_ice_ldv = 0.833
    technology_lpg_ice_ldv = 0.0
    technology_bev_ldv = 0.0
    technology_fcev_ldv = 0.0
    technology_diesel_plugin_hybrid_ldv = 0.0
    technology_gasoline_plugin_hybrid_ldv = 0.0

    # Bus
    technology_diesel_ice_bus = 1.0
    technology_bev_bus = 0.0
    technology_fcev_bus = 0.0
    technology_diesel_plugin_hybrid_bus = 0.0

    # 2&3W
    technology_gasoline_ice_two_three_wheeler = 1.0
    technology_bev_two_three_wheeler = 0.0

    # Train
    technology_fcev_passenger_train = 0.0
    technology_fcev_freight_train = 0.0

    # Plane
    technology_kerosene_passenger_plane = 1.0
    technology_bev_passenger_plane = 0.0
    technology_fcev_passenger_plane = 0.0
    technology_kerosene_freight_plane = 1.0

    # Trucks
    technology_diesel_ice_ldt = 1.0
    technology_bev_ldt = 0.0
    technology_fcev_ldt = 0.0
    technology_diesel_plugin_hybrid_ldt = 0.0

    technology_diesel_ice_hdt = 1.0
    technology_diesel_plugin_hybrid_hdt = 0.0
    technology_bev_hdt = 0.0
    technology_fcev_hdt = 0.0

    # Ship
    technology_diesel_ice_freight_ship = 1.0
    technology_methanol_freight_ship = 0.0
    technology_ammonia_freight_ship = 0.0
    technology_bev_freight_ship = 0.0
    technology_fcev_freight_ship = 0.0
    technology_diesel_passenger_ship = 1.0

    # Biofuels
    bioethanol_in_road_gasoline = 0.0
    biodiesel_in_road_diesel = 0.0
    biodiesel_in_rail_diesel = 0.0
    biodiesel_in_internal_navigation_diesel = 0.0
    biokerosene_in_internal_aviation_fuel = 0.0
    ice_fuel_in_plugin_hybrid = 0.5

    return (
        technology_gasoline_ice_ldv, technology_diesel_ice_ldv, technology_lpg_ice_ldv,
        technology_bev_ldv, technology_fcev_ldv,
        technology_diesel_plugin_hybrid_ldv, technology_gasoline_plugin_hybrid_ldv,

        technology_diesel_ice_bus, technology_bev_bus, technology_fcev_bus, technology_diesel_plugin_hybrid_bus,

        technology_gasoline_ice_two_three_wheeler, technology_bev_two_three_wheeler,

        technology_fcev_passenger_train,

        technology_kerosene_passenger_plane, technology_bev_passenger_plane, technology_fcev_passenger_plane,

        technology_diesel_ice_ldt, technology_bev_ldt, technology_fcev_ldt, technology_diesel_plugin_hybrid_ldt,

        technology_diesel_ice_hdt, technology_bev_hdt, technology_fcev_hdt, technology_diesel_plugin_hybrid_hdt,

        technology_fcev_freight_train,

        technology_diesel_ice_freight_ship, technology_methanol_freight_ship, technology_ammonia_freight_ship,
        technology_bev_freight_ship, technology_fcev_freight_ship,

        technology_kerosene_freight_plane,
        technology_diesel_passenger_ship,

        bioethanol_in_road_gasoline, biodiesel_in_road_diesel, biodiesel_in_rail_diesel,
        biodiesel_in_internal_navigation_diesel, biokerosene_in_internal_aviation_fuel,
        ice_fuel_in_plugin_hybrid
    )

# =============================================================================
#  TECHNOLOGY DEFINITIONS
#  (Used to populate the base dictionary keys in main_transport.py)
# =============================================================================
TECHNOLOGY_OVERRIDES = {
    # Keys only - Values are NOT used here.
    "Share of Technology - Gasoline ICE LDV": {},
    "Share of Technology - Diesel ICE LDV": {},
    "Share of Technology - LPG ICE LDV": {},
    "Share of Technology - BEV LDV": {},
    "Share of Technology - FCEV LDV": {},
    "Share of Technology - Diesel Plugin Hybrid LDV": {},
    "Share of Technology - Gasoline Plugin Hybrid LDV": {},
    
    "Share of Technology - Diesel ICE Bus": {},
    "Share of Technology - BEV Bus": {},
    "Share of Technology - FCEV Bus": {},
    "Share of Technology - Diesel Plugin Hybrid Bus": {},
    
    "Share of Technology - Gasoline ICE 2&3W": {},
    "Share of Technology - BEV 2&3W": {},
    
    "Share of Technology - Diesel ICE Passenger Train": {},
    "Share of Technology - Direct Electric Passenger Train": {},
    "Share of Technology - FCEV Passenger Train": {},
    
    "Share of Technology - Kerosene Passenger Plane": {},
    "Share of Technology - BEV Passenger Plane": {},
    "Share of Technology - FCEV Passenger Plane": {},
    
    "Share of Technology - Diesel ICE LDT": {},
    "Share of Technology - BEV LDT": {},
    "Share of Technology - FCEV LDT": {},
    "Share of Technology - Diesel Plugin Hybrid LDT": {},
    
    "Share of Technology - Diesel ICE HDT": {},
    "Share of Technology - BEV HDT": {},
    "Share of Technology - FCEV HDT": {},
    "Share of Technology - Diesel Plugin Hybrid HDT": {},
    
    "Share of Technology - Diesel ICE Freight Train": {},
    "Share of Technology - Direct Electric Freight Train": {},
    "Share of Technology - FCEV Freight Train": {},
    
    "Share of Technology - Diesel ICE Freight Ship": {},
    "Share of Technology - Methanol Freight Ship": {},
    "Share of Technology - Ammonia Freight Ship": {},
    "Share of Technology - BEV Freight Ship": {},
    "Share of Technology - FCEV Freight Ship": {},
    
    "Share of Technology - Kerosene Freight Plane": {},
    "Share of Technology - Diesel Passenger Ship": {},
    
    "Share of Bioethanol in Road Gasoline": {},
    "Share of Biodiesel in Road Diesel": {},
    "Share of Biodiesel in Rail Diesel": {},
    "Share of Biodiesel in Internal Navigation Diesel": {},
    "Share of Biokerosene in Internal Aviation Fuel": {},
    "Share of ICE Fuel in Plugin Hybrid": {},
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

def enforce_share_constraints(rows):
    """
    Check if technology shares exceed 100% for 2030/2050.
    """
    df = pd.DataFrame(rows)
    year_cols = [c for c in df.columns if c not in ["Metric", "Units"]]

    for subsector, metrics in TECHNOLOGY_GROUPS.items():
        subset = df[df["Metric"].isin(metrics)]
        if subset.empty: continue

        for year in year_cols:
            if year in df.columns:
                total = subset[year].sum()
                if total > 1.0 + 1e-6 and total <= 100: # Fraction check
                     pass 
                elif total > 100.0 + 1e-6: 
                    print(f" [WARN] {subsector} shares in {year} = {total:.2f}, exceeds 100%")

    return df.to_dict("records")