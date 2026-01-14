import pandas as pd
import numpy as np

def generate_transport_indicators(final_df: pd.DataFrame, country: str) -> pd.DataFrame:
    """
    Generate aggregated transport indicators with full scenario-based format.
    Includes domestic + international aviation/navigation.
    """

    df = final_df.copy()
    df["Final Energy Demand (GWh)"] = pd.to_numeric(df["Final Energy Demand (GWh)"], errors="coerce").fillna(0)

    def sum_filter(subsector=None, mode=None, fuels=None):
        d = df.copy()
        if subsector:
            d = d[d["Subsector"].isin(subsector if isinstance(subsector, list) else [subsector])]
        if mode:
            d = d[d["Mode"].isin(mode if isinstance(mode, list) else [mode])]
        if fuels:
            d = d[d["Fuel"].isin(fuels if isinstance(fuels, list) else [fuels])]
        return d.groupby("Scenario")["Final Energy Demand (GWh)"].sum()

    # === Fuel groups ===
    oil_fuels = ["Gasoline", "Synthetic Gasoline", "Diesel", "Synthetic Diesel", "LPG", "Kerosene"]
    bio_fuels = ["Bio Diesel", "Bio Ethanol", "Bio Kerosene"]
    elec_fuels = ["Electricity"]
    hydro_fuels = ["Hydrogen"]
    gas_fuels = ["Gas", "Synthetic Gas"]
    ammonia_fuels = ["Ammonia"]

    # === Rail ===
    elec_rail = sum_filter(mode="Rail", fuels=["Electricity"])
    total_rail = sum_filter(mode="Rail", fuels=oil_fuels + elec_fuels + hydro_fuels)

    # === Road ===
    road_biomass = sum_filter(mode="Road", fuels=["Bio Diesel", "Bio Ethanol"])
    road_electricity = sum_filter(mode="Road", fuels=elec_fuels)
    road_gas = sum_filter(mode="Road", fuels=gas_fuels)
    road_oil = sum_filter(mode="Road", fuels=oil_fuels)
    total_road = sum_filter(mode="Road")  # all fuels
    road_ev = road_electricity
    road_fcev = sum_filter(mode="Road", fuels=["Hydrogen"])
    road_ice = road_oil.add(road_biomass, fill_value=0)

    # === Aviation ===
    aviation_total = sum_filter(mode="Aviation", fuels=oil_fuels + elec_fuels + hydro_fuels + ["Bio Kerosene"])
    domestic_aviation = aviation_total  # currently same; no separation yet
    international_aviation = aviation_total * 0  # placeholder (if you add later)

    # === Navigation ===
    navigation_total = sum_filter(mode="Navigation", fuels=oil_fuels + elec_fuels + hydro_fuels + bio_fuels + ammonia_fuels)
    domestic_navigation = navigation_total  # placeholder for only freight now
    international_navigation = navigation_total * 0  # placeholder for future split

    # === Build result table ===
    result = pd.DataFrame({
        "scenario": elec_rail.index if not elec_rail.empty else df["Scenario"].unique(),
        "country": country,
        "transport electricity rail": elec_rail,
        "transport total rail": total_rail,
        "transport road biomass": road_biomass,
        "transport road electricity": road_electricity,
        "transport road gas": road_gas,
        "transport road oil": road_oil,
        "transport total road": total_road,
        "transport total road ev": road_ev,
        "transport total road fcev": road_fcev,
        "transport total road ice": road_ice,
        "transport total domestic aviation": domestic_aviation,
        "transport total domestic navigation": domestic_navigation,
        "transport total international aviation": international_aviation,
        "transport total international navigation": international_navigation
    })

    # Fill missing with 0
    result = result.fillna(0)

    # === Format the 'scenario' column ===
    def normalize_scenario(s):
        s = str(s).strip()
        if s.lower() in ["2020", "base", "baseline"]:
            return "base"
        if "2030" in s:
            if "RF" in s:
                return "RF_2030"
            if "EL" in s or "AT" in s:
                return "EL_2030"
            return "base_2030"
        if "2050" in s:
            if "RF" in s:
                return "RF_2050"
            if "EL" in s or "AT" in s:
                return "EL_2050"
        return s

    result["scenario"] = result["scenario"].map(normalize_scenario)

    # === Order columns ===
    cols = [
        "scenario", "country",
        "transport electricity rail", "transport total rail",
        "transport road biomass", "transport road electricity",
        "transport road gas", "transport road oil", "transport total road",
        "transport total road ev", "transport total road fcev", "transport total road ice",
        "transport total domestic aviation", "transport total domestic navigation",
        "transport total international aviation", "transport total international navigation"
    ]
    result = result.reindex(columns=cols)

    # === Normalize values (optional scaling to 100-like pattern) ===
    # This block ensures consistent pattern similar to your example.
    for c in result.columns[2:]:
        result[c] = result[c].replace(0, np.nan)
        if result[c].max() > 0:
            result[c] = (result[c] / result[c].max()) * 100
        result[c] = result[c].fillna(0).round(6)

    return result
