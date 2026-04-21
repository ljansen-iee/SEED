#build_CAGR.py

import pandas as pd
from pathlib import Path
import numpy as np
import os
from typing import Dict, List
from scipy.interpolate import interp1d

# --- STRICT SCENARIO MAPPING ---
SCENARIO_INDEX_MAP = {
    "sc_a": 0, 
    "sc_b": 1,  
    "sc_c": 2,
    "bau": 0,
    "progressive": 1,
    "optimistic": 2,
    "baseline": 0,
}


def _normalize_metric_name(metric_name: str) -> str:
    name = str(metric_name).strip().lower()
    return (
        name
        .replace("furncace", "furnace")
        .replace("furnaces + basic oxygen furnace", "furnace + basic oxygen furnace")
    )


def _parse_numeric_cell(value):
    if pd.isna(value):
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def load_industry_config(excel_path: Path, countries: list, scenarios: list):
    if not excel_path.exists():
        raise FileNotFoundError(f"Could not find config at {excel_path}")
    
    # Use read_csv if it's a .csv, otherwise read_excel
    if excel_path.suffix.lower() == '.csv':
        df = pd.read_csv(excel_path)
    else:
        df = pd.read_excel(excel_path)
        
    df.columns = df.columns.str.strip()
    config = {c: {} for c in countries}

    # === DUAL FORMAT HANDLING ===
    # If "Year" is a column, it's the NEW "Long" format.
    # If "Year" is NOT a column, we assume the old "Wide" format where headers were years.
    if "Year" not in df.columns:
        # PIVOT: Convert Wide (Year headers) to Long (Year column)
        # This makes the rest of the loop work for both versions
        non_year_cols = [c for c in df.columns if not str(c).isdigit()]
        year_cols = [c for c in df.columns if str(c).isdigit()]
        df = df.melt(id_vars=non_year_cols, value_vars=year_cols, 
                    var_name="Year", value_name="value")
        # In this old format, 'value' contains the data, so we map it to 'default'
        # so the country-check logic below still works.
        df["default"] = df["value"]

    # === PROCESSING LOOP ===
    for _, row in df.iterrows():
        metric = _normalize_metric_name(row["Metric Name"])
        a_type = str(row["Assumption Type"]).strip().upper()
        
        try:
            year = int(row["Year"])
        except:
            continue
            
        for country in countries:
            country_val = _parse_numeric_cell(row[country]) if country in df.columns else None
            default_val = _parse_numeric_cell(row.get("default", None))

            if country_val is not None:
                val = country_val
            elif default_val is not None:
                val = default_val
            else:
                continue

            scenario_key = str(row["Scenario"]).strip().lower()
            target_indices = []
            
            # Map "all" to every scenario, or specific ones via SCENARIO_INDEX_MAP
            if scenario_key == "all":
                target_indices = range(len(scenarios))
            elif scenario_key in SCENARIO_INDEX_MAP:
                idx = SCENARIO_INDEX_MAP[scenario_key]
                if idx < len(scenarios): 
                    target_indices = [idx]
            
            # Populate the nested dictionary
            metric_entry = config[country].setdefault(metric, {"assumption_type": a_type, "values": {}})
            for idx in target_indices:
                scenario_name = scenarios[idx]
                metric_entry["values"].setdefault(year, {})[scenario_name] = val
                
    return config

def get_metric_cagr_cfg_from_excel(industry_config, country, metric_name):
    """Bridge for build_industry_config.py loop"""
    metric_name = _normalize_metric_name(metric_name)
    return industry_config.get(country, {}).get(metric_name, {}).get("values", {})


def get_metric_config_entry_from_excel(industry_config, country, metric_name):
    """Return full metric config entry (assumption_type + values)."""
    metric_name = _normalize_metric_name(metric_name)
    return industry_config.get(country, {}).get(metric_name, {})

def expand_with_cagr_smooth(base_value, cagr_table, base_year, target_years, scenarios):
    result = {}
    max_target = max(target_years)
    
    # Identify milestone years from the dict keys
    config_milestones = sorted([int(k) for k in cagr_table.keys() if str(k).isdigit()])
    
    # --- SAFETY CHECK ---
    # If no CAGR milestones found for this country/metric, keep the value flat
    if not config_milestones:
        for scenario in scenarios:
            for y in target_years:
                result[f"{y}_{scenario}"] = float(base_value)
        return result

    for scenario in scenarios:
        current_val = float(base_value)
        
        for y in range(base_year + 1, max_target + 1):
            active_rate = 0.0
            
            # Find the rate for the current year period
            for m_year in config_milestones:
                if y <= m_year:
                    val = cagr_table.get(m_year, {}).get(scenario)
                    # Check if value exists and is not NaN
                    if val is not None and not pd.isna(val):
                        active_rate = float(val)
                        break
            else:
                # If we are past the last milestone year, use the last available rate
                last_year = config_milestones[-1]
                active_rate = float(cagr_table.get(last_year, {}).get(scenario, 0.0))

            # Apply Compounding: New Value = Old Value * (1 + rate)
            current_val = current_val * (1 + active_rate)
            
            if y in target_years:
                result[f"{y}_{scenario}"] = current_val
                
    return result

def interpolate_or_extrapolate(values, target_years):
    known_years = sorted([y for y, v in values.items() if v is not None])
    if not known_years: return {y: 0.0 for y in target_years}
    known_vals = [values[y] for y in known_years]
    if len(known_years) < 2: return {y: known_vals[0] for y in target_years}
    f = interp1d(known_years, known_vals, fill_value="extrapolate")
    return {y: float(f(y)) for y in target_years}

def load_yaml_config(path): return {}
def export_metric_template_to_yaml(*args, **kwargs): pass
def load_and_merge_yaml(*args, **kwargs): return {}, {}, {}

# ============================================================================
# CAGR CALCULATION FROM HISTORICAL UNSD DATA
# ============================================================================

# Mapping from metric names to UNSD sector keywords
FINAL_ENERGY_SECTOR_MAP = {
    "Final energy of transport equipment": "Transport equipment",
    "Final energy of textile and leather": "Textile and leather",
    "Final energy of non-ferrous metals": "Non-ferrous metals",
    "Final energy of mining and quarrying": "Mining and quarrying",
    "Final energy of machinery": "Machinery",
    "Final energy of construction": "Construction",
    "Final energy of food and tobacco": "Food and tobacco",
    "Final energy of wood and wood products": "Wood and wood products",
}

def calculate_rolling_cagr(historical_data: Dict[int, float], window: int = 5) -> float:
    """
    Calculate mean CAGR from rolling 5-year windows.
    
    Args:
        historical_data: Dict of {year: value_in_GWh}
        window: Number of years for each CAGR calculation (default 5)
    
    Returns:
        Mean CAGR as a decimal (e.g., 0.02 for 2%)
    """
    if not historical_data or len(historical_data) < 2:
        return 0.0
    
    sorted_years = sorted(historical_data.keys())
    cagr_list = []
    
    # Calculate rolling CAGR for each 5-year window
    for i in range(len(sorted_years) - window):
        start_year = sorted_years[i]
        end_year = sorted_years[i + window]
        
        start_val = historical_data.get(start_year, 0)
        end_val = historical_data.get(end_year, 0)
        
        # Skip if either value is zero or negative
        if start_val > 0 and end_val > 0:
            cagr = (end_val / start_val) ** (1 / window) - 1
            cagr_list.append(cagr)
    
    if not cagr_list:
        # Fallback: calculate single CAGR from first to last available year
        first_year = sorted_years[0]
        last_year = sorted_years[-1]
        first_val = historical_data.get(first_year, 0)
        last_val = historical_data.get(last_year, 0)
        years_diff = last_year - first_year
        
        if first_val > 0 and last_val > 0 and years_diff > 0:
            return (last_val / first_val) ** (1 / years_diff) - 1
        return 0.0
    
    # Return mean of all rolling CAGRs
    return sum(cagr_list) / len(cagr_list)


def get_final_energy_cagr_from_unsd(country: str, sector_keyword: str) -> float:
    """
    Get historical data from UNSD files and calculate CAGR for a sector.
    
    Args:
        country: Country name (e.g., "Morocco")
        sector_keyword: Sector keyword to search in UNSD files (e.g., "Food and tobacco")
    
    Returns:
        CAGR as decimal (e.g., 0.02 for 2%)
    """
    from industry.helpers import get_historical_sector_data
    
    folder_path = Path(__file__).parent / "input_data" / "country_specific"
    
    historical_data = get_historical_sector_data(folder_path, country, sector_keyword)
    
    if historical_data is None or len(historical_data) < 2:
        return 0.0
    
    return calculate_rolling_cagr(historical_data, window=5)


# ============================================================================
# CAGR CALCULATION FROM HISTORICAL FAO PAPER/PULP DATA
# ============================================================================

# Mapping from metric names to FAO item categories
PAPER_PULP_PRODUCTION_MAP = {
    "Pulp production per year": "pulp",
    "Paper production per year": "paper",
}

def get_paper_pulp_historical_data(country: str, product_type: str) -> Dict[int, float]:
    """
    Get historical paper/pulp production data from FAO files.
    
    Args:
        country: Country name (e.g., "Morocco")
        product_type: "pulp" or "paper"
    
    Returns:
        Dict of {year: production_in_tons}
    """
    import pandas as pd
    
    fao_path = Path(__file__).parent / "input_data" / "paper_and_pulp" / "Paper_Pulp_FAOSTAT_data_en_11-26-2025.xls"
    
    if not fao_path.exists():
        return {}
    
    try:
        df = pd.read_excel(fao_path)
        
        # Filter for country
        df_country = df[df['Area'] == country].copy()
        
        if df_country.empty:
            return {}
        
        # Define item lists (same as build_paper_and_pulp_production.py)
        density = 0.5  # Density for converting m3 to tons
        
        pulpwood_items = [
            "Pulpwood, round and split, coniferous (production)",
            "Pulpwood, round and split, non-coniferous (production)",
            "Other industrial roundwood, coniferous (production)",
            "Other industrial roundwood, non-coniferous (production)"
        ]
        pulp_items = [
            "Chemical wood pulp",
            "Chemical wood pulp, sulphate, bleached"
        ]
        paper_items = [
            "Recovered paper",
            "Newsprint",
            "Printing and writing papers",
            "Printing and writing papers, uncoated, mechanical",
            "Printing and writing papers, coated",
            "Other paper and paperboard",
            "Household and sanitary papers",
            "Wrapping papers"
        ]
        
        # Filter by product type
        if product_type == "pulp":
            target_items = pulpwood_items + pulp_items
        else:  # paper
            target_items = paper_items
        
        df_filtered = df_country[df_country['Item'].isin(target_items)].copy()
        
        if df_filtered.empty:
            return {}
        
        # Convert units to tons (pulpwood is in m3, needs density conversion)
        def convert_to_tons(row):
            if row['Item'] in pulpwood_items and row['Unit'] == 'm3':
                return row['Value'] * density
            elif row['Unit'] in ['t', 'tonnes']:
                return row['Value']
            else:
                return row['Value']  # Assume already in tons
        
        df_filtered['Value_tons'] = df_filtered.apply(convert_to_tons, axis=1)
        
        # Group by year and sum
        yearly_data = df_filtered.groupby('Year')['Value_tons'].sum()
        
        return {int(year): float(val) for year, val in yearly_data.items() if pd.notna(val) and val > 0}
        
    except Exception as e:
        print(f"Error reading FAO paper/pulp data for {country}: {e}")
        return {}


def get_paper_pulp_cagr_from_fao(country: str, product_type: str) -> float:
    """
    Get historical paper/pulp data from FAO files and calculate CAGR.
    
    Args:
        country: Country name (e.g., "Morocco")
        product_type: "pulp" or "paper"
    
    Returns:
        CAGR as decimal (e.g., 0.02 for 2%)
    """
    historical_data = get_paper_pulp_historical_data(country, product_type)
    
    if not historical_data or len(historical_data) < 2:
        return 0.0
    
    return calculate_rolling_cagr(historical_data, window=5)


# ============================================================================
# HARDCODED CAGR RATES
# Structure: metric_name -> { "2030": [sc_0, sc_1, sc_2], "2050": [sc_0, sc_1, sc_2] }
# "2050" applies to years 2035, 2040, 2045, 2050
# ============================================================================

CAGR = {
    # Activity / Production metrics
    "Steel production per year": {"2030": [0.0, 0.0, 0.0], "2050": [0.0, 0.01, 0.01]},
    "Activity factor of unspecified iron and steel": {"2030": [0.0, 0.01, 0.01], "2050": [0.0, 0.01, 0.01]},
    "Ammonia production per year": {"2030": [0.02, 0.02, 0.02], "2050": [0.02, 0.02, 0.02]},
    "High value chemical production per year": {"2030": [0.02, 0.02, 0.02], "2050": [0.02, 0.02, 0.02]},
    "Activity factor of unspecified chemicals": {"2030": [0.02, 0.02, 0.02], "2050": [0.02, 0.02, 0.02]},
    "Cement production per year": {"2030": [0.02, 0.02, 0.02], "2050": [0.02, 0.02, 0.02]},
    "Activity factor of unspecified non metallic minerals": {"2030": [0.02, 0.02, 0.02], "2050": [0.02, 0.02, 0.02]},
    # "Pulp production per year" and "Paper production per year" are now calculated from historical FAO data
    "Activity factor of unspecified paper and pulp": {"2030": [0.001, 0.001, 0.001], "2050": [0.0, 0.0, 0.0]},
    # Activity factors for Other Industries removed - using Final energy CAGR directly
    
    # Energy intensity metrics
    "Energy intensity of blast furnaces + open hearth furnaces": {"2030": [0.0, 0.0, 0.0], "2050": [0.0, 0.0, 0.0]},
    "Energy intensity of blast furnaces + basic oxygen furnaces": {"2030": [0.0, 0.0, 0.0], "2050": [0.0, 0.0, 0.0]},
    "Energy intensity of direct reduction + electric arc furnaces": {"2030": [0.0, 0.0, -0.001], "2050": [0.0, 0.0, -0.001]},
    "Energy intensity of scrap electric arc furnaces": {"2030": [0.0, 0.0, -0.001], "2050": [0.0, 0.0, -0.001]},
    "Energy intensity of casting, rolling & finishing": {"2030": [0.0, 0.0, -0.001], "2050": [0.0, 0.0, -0.001]},
    "Energy intensity of unspecified iron and steel": {"2030": [0.0, 0.0, -0.001], "2050": [0.0, 0.0, -0.001]},
    "Energy intensity of SMR + Haber-Bosch": {"2030": [0.0, 0.0, -0.001], "2050": [0.0, 0.0, -0.001]},
    "Energy intensity of Other Conventional + Haber-Bosch": {"2030": [0.0, 0.0, -0.001], "2050": [0.0, 0.0, -0.001]},
    "Energy intensity of renewable ammonia synthesis": {"2030": [0.0, 0.0, -0.001], "2050": [0.0, 0.0, -0.001]},
    "Energy intensity of Naphtha cracking": {"2030": [0.0, 0.0, -0.001], "2050": [0.0, 0.0, -0.001]},
    "Energy intensity of LPG cracking": {"2030": [0.0, 0.0, -0.001], "2050": [0.0, 0.0, -0.001]},
    "Energy intensity of Methanol route": {"2030": [0.0, 0.0, -0.001], "2050": [0.0, 0.0, -0.001]},
    "Energy intensity of unspecified chemicals": {"2030": [0.0, 0.0, -0.001], "2050": [0.0, 0.0, -0.001]},
    "Energy intensity of cement production": {"2030": [0.0, 0.0, -0.001], "2050": [0.0, 0.0, -0.001]},
    "Energy intensity of unspecified non metallic minerals": {"2030": [0.0, 0.0, -0.001], "2050": [0.0, 0.0, -0.001]},
    "Energy intensity of primary pulp production": {"2030": [-0.002, -0.002, -0.002], "2050": [-0.002, -0.002, -0.002]},
    "Energy intensity of secondary pulp production": {"2030": [-0.002, -0.002, -0.002], "2050": [-0.002, -0.002, -0.002]},
    "Energy intensity of paper production": {"2030": [-0.002, -0.002, -0.002], "2050": [-0.002, -0.002, -0.002]},
    "Energy intensity of unspecified paper and pulp": {"2030": [-0.002, -0.002, -0.002], "2050": [-0.002, -0.002, -0.002]},
    # Energy intensities for Other Industries removed - using Final energy CAGR directly
    
    # Non-energy use metrics
    "Energy Demand factor of Bitumen for unspecified non energy use": {"2030": [0.0, 0.0, 0.0], "2050": [0.0, 0.0, 0.0]},
    "Energy Demand factor of Lubricants for unspecified non energy use": {"2030": [0.0, 0.0, 0.0], "2050": [0.0, 0.0, 0.0]},
    "Energy Demand factor of Other Oil Products for unspecified non energy use": {"2030": [0.0, 0.0, 0.0], "2050": [0.0, 0.0, 0.0]},
    "Energy Demand factor of Natural Gas for unspecified non energy use": {"2030": [0.0, 0.0, 0.0], "2050": [0.0, 0.0, 0.0]},
    "Energy Demand factor of Coal for unspecified non energy use": {"2030": [0.0, 0.0, 0.0], "2050": [0.0, 0.0, 0.0]},
}


def generate_industry_config_csv(scenarios: List[str], countries: List[str] = None, output_path: Path = None) -> pd.DataFrame:
    """
    Generate industry_config_file.csv from hardcoded CAGR rates.
    
    Args:
        scenarios: List of scenario names (e.g., ["BAU", "Progressive", "Optimistic"])
        countries: List of country names to create columns for. Each country gets the same hardcoded values.
        output_path: Path to save the CSV file. If None, uses default location.
    
    Returns:
        DataFrame with the generated config
    """
    if output_path is None:
        output_path = Path(__file__).parent / "industry_config_file.csv"
    
    if countries is None:
        countries = []
    
    years = [2030, 2035, 2040, 2045, 2050]  # from helpers.DEFAULT_TARGET_YEARS
    rows = []
    
    # === Process CAGR rates ===
    for metric_name, rates in CAGR.items():
        rate_2030 = rates["2030"]
        rate_long_term = rates["2050"]
        
        for year in years:
            for sc_idx, scenario in enumerate(scenarios):
                # Use 2030 rates for 2030, long_term rates for 2035-2050
                if year == 2030:
                    rate = rate_2030[sc_idx] if sc_idx < len(rate_2030) else rate_2030[-1]
                else:
                    rate = rate_long_term[sc_idx] if sc_idx < len(rate_long_term) else rate_long_term[-1]
                
                row = {
                    "Assumption Type": "CAGR",
                    "Metric Name": metric_name,
                    "Year": year,
                    "Scenario": scenario,
                    "default": rate
                }
                
                # Add country-specific columns with the same value
                for country in countries:
                    row[country] = rate
                
                rows.append(row)
    
    # === Process Final Energy CAGR from historical UNSD data ===
    for metric_name, sector_keyword in FINAL_ENERGY_SECTOR_MAP.items():
        # Calculate country-specific CAGR from historical data
        country_cagr = {}
        for country in countries:
            cagr = get_final_energy_cagr_from_unsd(country, sector_keyword)
            country_cagr[country] = round(cagr, 4)  # Round to 4 decimal places
        
        # Calculate default CAGR (mean of all countries, or 0.0 if no countries)
        if country_cagr:
            default_cagr = sum(country_cagr.values()) / len(country_cagr)
        else:
            default_cagr = 0.0
        
        for year in years:
            for sc_idx, scenario in enumerate(scenarios):
                row = {
                    "Assumption Type": "CAGR",
                    "Metric Name": metric_name,
                    "Year": year,
                    "Scenario": scenario,
                    "default": round(default_cagr, 4)
                }
                
                # Add country-specific CAGR values
                for country in countries:
                    row[country] = country_cagr.get(country, default_cagr)
                
                rows.append(row)
    
    # === Process Paper/Pulp Production CAGR from historical FAO data ===
    for metric_name, product_type in PAPER_PULP_PRODUCTION_MAP.items():
        # Calculate country-specific CAGR from historical FAO data
        country_cagr = {}
        for country in countries:
            cagr = get_paper_pulp_cagr_from_fao(country, product_type)
            country_cagr[country] = round(cagr, 4)  # Round to 4 decimal places
        
        # Calculate default CAGR (mean of all countries, or 0.0 if no countries)
        if country_cagr:
            default_cagr = sum(country_cagr.values()) / len(country_cagr)
        else:
            default_cagr = 0.0
        
        for year in years:
            for sc_idx, scenario in enumerate(scenarios):
                row = {
                    "Assumption Type": "CAGR",
                    "Metric Name": metric_name,
                    "Year": year,
                    "Scenario": scenario,
                    "default": round(default_cagr, 4)
                }
                
                # Add country-specific CAGR values
                for country in countries:
                    row[country] = country_cagr.get(country, default_cagr)
                
                rows.append(row)
    
    # === Process SHARE values from build_steel_production.py ===
    from industry.scripts.iron_and_steel.build_steel_production import share_steel
    _, share_secondary_steel = share_steel(years, scenarios)
    
    for year in years:
        if year not in share_secondary_steel:
            continue
        year_data = share_secondary_steel[year]
        
        for sc_idx, scenario in enumerate(scenarios):
            share_val = year_data.get(scenario, 20.0)
            
            row = {
                "Assumption Type": "SHARE",
                "Metric Name": "Share of secondary steel = scrap electric arc furnaces",
                "Year": year,
                "Scenario": scenario,
                "default": share_val
            }
            
            # Add country-specific columns with the same value
            for country in countries:
                row[country] = share_val
            
            rows.append(row)
    
    # === Process steel route shares (BF+BOF, DR+EAF, BF+OHF) ===
    # Import route share function from build_shares_steel.py
    from industry.scripts.iron_and_steel.build_shares_steel import share_route_steel
    
    route_shares = share_route_steel(years, scenarios)
    
    route_metrics = [
        ("Share of blast furnace + basic oxygen furnace for steel making", "bf_bof"),
        ("Share of direct reduction + electric arc furnace for steel making", "dr_eaf"),
        ("Share of blast furnace + open hearth furnace for steel making", "bf_ohf"),
    ]
    
    for metric_name, route_key in route_metrics:
        for year in years:
            for scenario in scenarios:
                row = {
                    "Assumption Type": "SHARE",
                    "Metric Name": metric_name,
                    "Year": year,
                    "Scenario": scenario,
                    "default": 0.0  # No default - must be country-specific
                }
                
                # Get value from share_route_steel (same for all countries)
                share_val = route_shares.get(route_key, {}).get(year, {}).get(scenario, 0.0)
                for country in countries:
                    row[country] = share_val
                
                rows.append(row)
    # === Process fuel shares for BF+OHF from build_shares_steel.py ===
    from industry.scripts.iron_and_steel.build_shares_steel import share_fuel_bf_ohf, share_fuel_bf_bof
    
    bf_ohf_fuel_data = share_fuel_bf_ohf(years, scenarios)
    
    fuel_metric_map = {
        "diesel": "Share of diesel for blast furnaces",
        "natural_gas": "Share of natural gas for blast furnaces",
        "electricity": "Share of electricity for blast furnaces + open hearth furnace",
        "coal": "Share of coal for blast furnaces + open hearth furnace",
        "heat": "Share of heat for blast furnaces + open hearth furnace",
        "biomass": "Share of biomass for blast furnaces + open hearth furnace",
        "hydrogen": "Share of hydrogen for blast furnaces + open hearth furnace",
    }
    
    for fuel_key, metric_name in fuel_metric_map.items():
        fuel_year_data = bf_ohf_fuel_data.get(fuel_key, {})
        
        for year in years:
            if year not in fuel_year_data:
                continue
            year_data = fuel_year_data[year]
            
            for sc_idx, scenario in enumerate(scenarios):
                share_val = year_data.get(scenario, 0.0)
                
                row = {
                    "Assumption Type": "SHARE",
                    "Metric Name": metric_name,
                    "Year": year,
                    "Scenario": scenario,
                    "default": share_val
                }
                
                # Same value for all countries (global fuel mix)
                for country in countries:
                    row[country] = share_val
                
                rows.append(row)
    
    # === Process fuel shares for BF+BOF from build_shares_steel.py ===
    bf_bof_fuel_data = share_fuel_bf_bof(years, scenarios)
    
    bf_bof_fuel_metric_map = {
        "diesel": "Share of diesel for blast furnaces + basic oxygen furnace",
        "natural_gas": "Share of natural gas for blast furnaces + basic oxygen furnace",
        "electricity": "Share of electricity for blast furnaces + basic oxygen furnace",
        "coal": "Share of coal for blast furnaces + basic oxygen furnace",
        "heat": "Share of heat for blast furnaces + basic oxygen furnace",
        "biomass": "Share of biomass for blast furnaces + basic oxygen furnace",
        "hydrogen": "Share of hydrogen for blast furnaces + basic oxygen furnace",
    }
    
    for fuel_key, metric_name in bf_bof_fuel_metric_map.items():
        fuel_year_data = bf_bof_fuel_data.get(fuel_key, {})
        
        for year in years:
            if year not in fuel_year_data:
                continue
            year_data = fuel_year_data[year]
            
            for sc_idx, scenario in enumerate(scenarios):
                share_val = year_data.get(scenario, 0.0)
                
                row = {
                    "Assumption Type": "SHARE",
                    "Metric Name": metric_name,
                    "Year": year,
                    "Scenario": scenario,
                    "default": share_val
                }
                
                # Same value for all countries (global fuel mix)
                for country in countries:
                    row[country] = share_val
                
                rows.append(row)
    
    # === Process fuel shares for DR+EAF from build_shares_steel.py ===
    from industry.scripts.iron_and_steel.build_shares_steel import share_fuel_dr_eaf
    dr_eaf_fuel_data = share_fuel_dr_eaf(years, scenarios)
    
    dr_eaf_fuel_metric_map = {
        "diesel": "Share of diesel for direct reduction + electric arc furnace",
        "natural_gas": "Share of natural gas for direct reduction + electric arc furnace",
        "electricity": "Share of electricity for direct reduction + electric arc furnace",
        "coal": "Share of coal for direct reduction + electric arc furnace",
        "heat": "Share of heat for direct reduction + electric arc furnace",
        "biomass": "Share of biomass for direct reduction + electric arc furnace",
        "hydrogen": "Share of hydrogen for direct reduction + electric arc furnace",
    }
    
    for fuel_key, metric_name in dr_eaf_fuel_metric_map.items():
        fuel_year_data = dr_eaf_fuel_data.get(fuel_key, {})
        
        for year in years:
            if year not in fuel_year_data:
                continue
            year_data = fuel_year_data[year]
            
            for sc_idx, scenario in enumerate(scenarios):
                share_val = year_data.get(scenario, 0.0)
                
                row = {
                    "Assumption Type": "SHARE",
                    "Metric Name": metric_name,
                    "Year": year,
                    "Scenario": scenario,
                    "default": share_val
                }
                
                for country in countries:
                    row[country] = share_val
                
                rows.append(row)
    
    # === Process fuel shares for Scrap EAF from build_shares_steel.py ===
    from industry.scripts.iron_and_steel.build_shares_steel import share_fuel_scrap_eaf
    scrap_eaf_fuel_data = share_fuel_scrap_eaf(years, scenarios)
    
    scrap_eaf_fuel_metric_map = {
        "diesel": "Share of diesel for scrap electric arc furnaces",
        "natural_gas": "Share of natural gas for scrap electric arc furnaces",
        "electricity": "Share of electricity for scrap electric arc furnaces",
        "coal": "Share of coal for scrap electric arc furnaces",
        "heat": "Share of heat for scrap electric arc furnaces",
        "biomass": "Share of biomass for scrap electric arc furnaces",
        "hydrogen": "Share of hydrogen for scrap electric arc furnaces",
    }
    
    for fuel_key, metric_name in scrap_eaf_fuel_metric_map.items():
        fuel_year_data = scrap_eaf_fuel_data.get(fuel_key, {})
        
        for year in years:
            if year not in fuel_year_data:
                continue
            year_data = fuel_year_data[year]
            
            for sc_idx, scenario in enumerate(scenarios):
                share_val = year_data.get(scenario, 0.0)
                
                row = {
                    "Assumption Type": "SHARE",
                    "Metric Name": metric_name,
                    "Year": year,
                    "Scenario": scenario,
                    "default": share_val
                }
                
                for country in countries:
                    row[country] = share_val
                
                rows.append(row)
    
    # === Process fuel shares for Casting, Rolling & Finishing from build_shares_steel.py ===
    from industry.scripts.iron_and_steel.build_shares_steel import share_fuel_casting_rolling
    casting_rolling_fuel_data = share_fuel_casting_rolling(years, scenarios)
    
    casting_rolling_fuel_metric_map = {
        "diesel": "Share of diesel for casting, rolling & finishing",
        "natural_gas": "Share of natural gas for casting, rolling & finishing",
        "electricity": "Share of electricity for casting, rolling & finishing",
        "coal": "Share of coal for casting, rolling & finishing",
        "heat": "Share of heat for casting, rolling & finishing",
        "biomass": "Share of biomass for casting, rolling & finishing",
        "hydrogen": "Share of hydrogen for casting, rolling & finishing",
    }
    
    for fuel_key, metric_name in casting_rolling_fuel_metric_map.items():
        fuel_year_data = casting_rolling_fuel_data.get(fuel_key, {})
        
        for year in years:
            if year not in fuel_year_data:
                continue
            year_data = fuel_year_data[year]
            
            for sc_idx, scenario in enumerate(scenarios):
                share_val = year_data.get(scenario, 0.0)
                
                row = {
                    "Assumption Type": "SHARE",
                    "Metric Name": metric_name,
                    "Year": year,
                    "Scenario": scenario,
                    "default": share_val
                }
                
                for country in countries:
                    row[country] = share_val
                
                rows.append(row)
    
    # === Process fuel shares for Unspecified Iron and Steel from build_shares_steel.py ===
    from industry.scripts.iron_and_steel.build_shares_steel import share_fuel_unspecified_steel
    unspecified_steel_fuel_data = share_fuel_unspecified_steel(years, scenarios)
    
    unspecified_steel_fuel_metric_map = {
        "diesel": "Share of diesel for unspecified iron and steel",
        "natural_gas": "Share of natural gas for unspecified iron and steel",
        "electricity": "Share of electricity for unspecified iron and steel",
        "coal": "Share of coal for unspecified iron and steel",
        "heat": "Share of heat for unspecified iron and steel",
        "biomass": "Share of biomass for unspecified iron and steel",
        "hydrogen": "Share of hydrogen for unspecified iron and steel",
    }
    
    for fuel_key, metric_name in unspecified_steel_fuel_metric_map.items():
        fuel_year_data = unspecified_steel_fuel_data.get(fuel_key, {})
        
        for year in years:
            if year not in fuel_year_data:
                continue
            year_data = fuel_year_data[year]
            
            for sc_idx, scenario in enumerate(scenarios):
                share_val = year_data.get(scenario, 0.0)
                
                row = {
                    "Assumption Type": "SHARE",
                    "Metric Name": metric_name,
                    "Year": year,
                    "Scenario": scenario,
                    "default": share_val
                }
                
                for country in countries:
                    row[country] = share_val
                
                rows.append(row)
    
    # =====================================================================
    # === AMMONIA SHARES
    # =====================================================================
    
    # === Process fuel shares for SMR + Haber-Bosch ===
    from industry.scripts.chemical_and_petrochemical.ammonia.build_shares_ammonia import (
        share_fuel_ammonia_smr_hb, 
        share_fuel_ammonia_renewable, 
        share_fuel_hvc_naphtha_cracking, 
        share_fuel_hvc_lpg_cracking, 
        share_fuel_hvc_methanol_route, 
        share_fuel_unspecified_chemicals,
        share_HVC_production
    )
    
    smr_hb_fuel_data = share_fuel_ammonia_smr_hb(years, scenarios)
    
    smr_hb_fuel_metric_map = {
        "diesel": "Share of diesel for SMR + Haber-Bosch",
        "natural_gas": "Share of natural gas for SMR + Haber-Bosch",
        "electricity": "Share of electricity for SMR + Haber-Bosch",
        "coal": "Share of coal for SMR + Haber-Bosch",
        "heat": "Share of heat for SMR + Haber-Bosch",
        "biomass": "Share of biomass for SMR + Haber-Bosch",
        "hydrogen": "Share of hydrogen for SMR + Haber-Bosch",
    }
    
    for fuel_key, metric_name in smr_hb_fuel_metric_map.items():
        fuel_year_data = smr_hb_fuel_data.get(fuel_key, {})
        
        for year in years:
            if year not in fuel_year_data:
                continue
            year_data = fuel_year_data[year]
            
            for sc_idx, scenario in enumerate(scenarios):
                share_val = year_data.get(scenario, 0.0)
                
                row = {
                    "Assumption Type": "SHARE",
                    "Metric Name": metric_name,
                    "Year": year,
                    "Scenario": scenario,
                    "default": share_val
                }
                
                for country in countries:
                    row[country] = share_val
                
                rows.append(row)
    
    # === Process fuel shares for renewable ammonia synthesis ===
    renewable_ammonia_fuel_data = share_fuel_ammonia_renewable(years, scenarios)
    
    renewable_ammonia_fuel_metric_map = {
        "diesel": "Share of diesel for renewable ammonia synthesis",
        "natural_gas": "Share of natural gas for renewable ammonia synthesis",
        "electricity": "Share of electricity for renewable ammonia synthesis",
        "coal": "Share of coal for renewable ammonia synthesis",
        "heat": "Share of heat for renewable ammonia synthesis",
        "biomass": "Share of biomass for renewable ammonia synthesis",
        "hydrogen": "Share of hydrogen for renewable ammonia synthesis",
    }
    
    for fuel_key, metric_name in renewable_ammonia_fuel_metric_map.items():
        fuel_year_data = renewable_ammonia_fuel_data.get(fuel_key, {})
        
        for year in years:
            if year not in fuel_year_data:
                continue
            year_data = fuel_year_data[year]
            
            for sc_idx, scenario in enumerate(scenarios):
                share_val = year_data.get(scenario, 0.0)
                
                row = {
                    "Assumption Type": "SHARE",
                    "Metric Name": metric_name,
                    "Year": year,
                    "Scenario": scenario,
                    "default": share_val
                }
                
                for country in countries:
                    row[country] = share_val
                
                rows.append(row)
    
    # =====================================================================
    # === HVC (HIGH VALUE CHEMICALS) SHARES
    # =====================================================================
    
    # === HVC route shares (Naphtha, LPG, Methanol) ===
    hvc_route_data = share_HVC_production(years, scenarios)
    
    hvc_route_metric_map = {
        "Naphtha": "Share of Naphtha cracking for HVC production",
        "LPG": "Share of LPG cracking for HVC production",
        "Methanol": "Share of Methanol route for HVC production",
    }
    
    for route_key, metric_name in hvc_route_metric_map.items():
        route_year_data = hvc_route_data.get(route_key, {})
        
        for year in years:
            if year not in route_year_data:
                continue
            year_data = route_year_data[year]
            
            for sc_idx, scenario in enumerate(scenarios):
                share_val = year_data.get(scenario, 0.0)
                
                row = {
                    "Assumption Type": "SHARE",
                    "Metric Name": metric_name,
                    "Year": year,
                    "Scenario": scenario,
                    "default": share_val
                }
                
                for country in countries:
                    row[country] = share_val
                
                rows.append(row)
    
    # === Process fuel shares for Naphtha cracking ===
    naphtha_fuel_data = share_fuel_hvc_naphtha_cracking(years, scenarios)
    
    naphtha_fuel_metric_map = {
        "diesel": "Share of diesel for Naphtha cracking",
        "natural_gas": "Share of natural gas for Naphtha cracking",
        "electricity": "Share of electricity for Naphtha cracking",
        "coal": "Share of coal for Naphtha cracking",
        "heat": "Share of heat for Naphtha cracking",
        "biomass": "Share of biomass for Naphtha cracking",
        "hydrogen": "Share of hydrogen for Naphtha cracking",
    }
    
    for fuel_key, metric_name in naphtha_fuel_metric_map.items():
        fuel_year_data = naphtha_fuel_data.get(fuel_key, {})
        
        for year in years:
            if year not in fuel_year_data:
                continue
            year_data = fuel_year_data[year]
            
            for sc_idx, scenario in enumerate(scenarios):
                share_val = year_data.get(scenario, 0.0)
                
                row = {
                    "Assumption Type": "SHARE",
                    "Metric Name": metric_name,
                    "Year": year,
                    "Scenario": scenario,
                    "default": share_val
                }
                
                for country in countries:
                    row[country] = share_val
                
                rows.append(row)
    
    # === Process fuel shares for LPG cracking ===
    lpg_fuel_data = share_fuel_hvc_lpg_cracking(years, scenarios)
    
    lpg_fuel_metric_map = {
        "diesel": "Share of diesel for LPG cracking",
        "natural_gas": "Share of natural gas for LPG cracking",
        "electricity": "Share of electricity for LPG cracking",
        "coal": "Share of coal for LPG cracking",
        "heat": "Share of heat for LPG cracking",
        "biomass": "Share of biomass for LPG cracking",
        "hydrogen": "Share of hydrogen for LPG cracking",
    }
    
    for fuel_key, metric_name in lpg_fuel_metric_map.items():
        fuel_year_data = lpg_fuel_data.get(fuel_key, {})
        
        for year in years:
            if year not in fuel_year_data:
                continue
            year_data = fuel_year_data[year]
            
            for sc_idx, scenario in enumerate(scenarios):
                share_val = year_data.get(scenario, 0.0)
                
                row = {
                    "Assumption Type": "SHARE",
                    "Metric Name": metric_name,
                    "Year": year,
                    "Scenario": scenario,
                    "default": share_val
                }
                
                for country in countries:
                    row[country] = share_val
                
                rows.append(row)
    
    # === Process fuel shares for Methanol route ===
    methanol_fuel_data = share_fuel_hvc_methanol_route(years, scenarios)
    
    methanol_fuel_metric_map = {
        "diesel": "Share of diesel for Methanol route",
        "natural_gas": "Share of natural gas for Methanol route",
        "electricity": "Share of electricity for Methanol route",
        "coal": "Share of coal for Methanol route",
        "heat": "Share of heat for Methanol route",
        "biomass": "Share of biomass for Methanol route",
        "hydrogen": "Share of hydrogen for Methanol route",
    }
    
    for fuel_key, metric_name in methanol_fuel_metric_map.items():
        fuel_year_data = methanol_fuel_data.get(fuel_key, {})
        
        for year in years:
            if year not in fuel_year_data:
                continue
            year_data = fuel_year_data[year]
            
            for sc_idx, scenario in enumerate(scenarios):
                share_val = year_data.get(scenario, 0.0)
                
                row = {
                    "Assumption Type": "SHARE",
                    "Metric Name": metric_name,
                    "Year": year,
                    "Scenario": scenario,
                    "default": share_val
                }
                
                for country in countries:
                    row[country] = share_val
                
                rows.append(row)
    
    # === Process fuel shares for unspecified chemicals ===
    unspecified_chem_fuel_data = share_fuel_unspecified_chemicals(years, scenarios)
    
    unspecified_chem_fuel_metric_map = {
        "diesel": "Share of diesel for unspecified chemicals",
        "natural_gas": "Share of natural gas for unspecified chemicals",
        "electricity": "Share of electricity for unspecified chemicals",
        "coal": "Share of coal for unspecified chemicals",
        "heat": "Share of heat for unspecified chemicals",
        "biomass": "Share of biomass for unspecified chemicals",
        "hydrogen": "Share of hydrogen for unspecified chemicals",
    }
    
    for fuel_key, metric_name in unspecified_chem_fuel_metric_map.items():
        fuel_year_data = unspecified_chem_fuel_data.get(fuel_key, {})
        
        for year in years:
            if year not in fuel_year_data:
                continue
            year_data = fuel_year_data[year]
            
            for sc_idx, scenario in enumerate(scenarios):
                share_val = year_data.get(scenario, 0.0)
                
                row = {
                    "Assumption Type": "SHARE",
                    "Metric Name": metric_name,
                    "Year": year,
                    "Scenario": scenario,
                    "default": share_val
                }
                
                for country in countries:
                    row[country] = share_val
                
                rows.append(row)
    
    # =====================================================================
    # === CEMENT AND NON-METALLIC MINERALS SHARES
    # =====================================================================
    
    from industry.scripts.non_metallic_minerals.build_shares_cement import (
        share_fuel_cement_production, 
        share_fuel_unspecified_nmm
    )
    
    # === Process fuel shares for Cement production ===
    cement_fuel_data = share_fuel_cement_production(years, scenarios)
    
    cement_fuel_metric_map = {
        "diesel": "Share of diesel for Cement production",
        "natural_gas": "Share of natural gas for Cement production",
        "electricity": "Share of electricity for Cement production",
        "coal": "Share of coal for Cement production",
        "heat": "Share of heat for Cement production",
        "biomass": "Share of biomass for Cement production",
        "hydrogen": "Share of hydrogen for Cement production",
    }
    
    for fuel_key, metric_name in cement_fuel_metric_map.items():
        fuel_year_data = cement_fuel_data.get(fuel_key, {})
        
        for year in years:
            if year not in fuel_year_data:
                continue
            year_data = fuel_year_data[year]
            
            for sc_idx, scenario in enumerate(scenarios):
                share_val = year_data.get(scenario, 0.0)
                
                row = {
                    "Assumption Type": "SHARE",
                    "Metric Name": metric_name,
                    "Year": year,
                    "Scenario": scenario,
                    "default": share_val
                }
                
                for country in countries:
                    row[country] = share_val
                
                rows.append(row)
    
    # === Process fuel shares for unspecified non metallic minerals ===
    nmm_fuel_data = share_fuel_unspecified_nmm(years, scenarios)
    
    nmm_fuel_metric_map = {
        "diesel": "Share of diesel for unspecified non metallic minerals",
        "natural_gas": "Share of natural gas for unspecified non metallic minerals",
        "electricity": "Share of electricity for unspecified non metallic minerals",
        "coal": "Share of coal for unspecified non metallic minerals",
        "heat": "Share of heat for unspecified non metallic minerals",
        "biomass": "Share of biomass for unspecified non metallic minerals",
        "hydrogen": "Share of hydrogen for unspecified non metallic minerals",
    }
    
    for fuel_key, metric_name in nmm_fuel_metric_map.items():
        fuel_year_data = nmm_fuel_data.get(fuel_key, {})
        
        for year in years:
            if year not in fuel_year_data:
                continue
            year_data = fuel_year_data[year]
            
            for sc_idx, scenario in enumerate(scenarios):
                share_val = year_data.get(scenario, 0.0)
                
                row = {
                    "Assumption Type": "SHARE",
                    "Metric Name": metric_name,
                    "Year": year,
                    "Scenario": scenario,
                    "default": share_val
                }
                
                for country in countries:
                    row[country] = share_val
                
                rows.append(row)
    
    # =====================================================================
    # === PAPER AND PULP SHARES
    # =====================================================================
    
    from industry.scripts.paper_and_pulp.build_share_primary_pulp import (
        share_fuel_primary_pulp, 
        share_fuel_secondary_pulp, 
        share_fuel_paper, 
        share_primary_secondary_pulp,
        share_fuel_unspecified_paper_pulp
    )
    
    # === Process primary/secondary pulp shares ===
    pulp_type_data = share_primary_secondary_pulp(years, scenarios)
    
    pulp_type_metric_map = {
        "primary": "Share of primary pulp",
        "secondary": "Share of secondary pulp",
    }
    
    for pulp_type, metric_name in pulp_type_metric_map.items():
        type_year_data = pulp_type_data.get(pulp_type, {})
        
        for year in years:
            if year not in type_year_data:
                continue
            year_data = type_year_data[year]
            
            for sc_idx, scenario in enumerate(scenarios):
                share_val = year_data.get(scenario, 0.0)
                
                row = {
                    "Assumption Type": "SHARE",
                    "Metric Name": metric_name,
                    "Year": year,
                    "Scenario": scenario,
                    "default": share_val
                }
                
                for country in countries:
                    row[country] = share_val
                
                rows.append(row)
    
    # === Process fuel shares for primary pulp production ===
    primary_pulp_fuel_data = share_fuel_primary_pulp(years, scenarios)
    
    primary_pulp_fuel_metric_map = {
        "diesel": "Share of diesel for primary pulp production",
        "natural_gas": "Share of natural gas for primary pulp production",
        "electricity": "Share of electricity for primary pulp production",
        "coal": "Share of coal for primary pulp production",
        "heat": "Share of heat for primary pulp production",
        "biomass": "Share of biomass for primary pulp production",
        "hydrogen": "Share of hydrogen for primary pulp production",
    }
    
    for fuel_key, metric_name in primary_pulp_fuel_metric_map.items():
        fuel_year_data = primary_pulp_fuel_data.get(fuel_key, {})
        
        for year in years:
            if year not in fuel_year_data:
                continue
            year_data = fuel_year_data[year]
            
            for sc_idx, scenario in enumerate(scenarios):
                share_val = year_data.get(scenario, 0.0)
                
                row = {
                    "Assumption Type": "SHARE",
                    "Metric Name": metric_name,
                    "Year": year,
                    "Scenario": scenario,
                    "default": share_val
                }
                
                for country in countries:
                    row[country] = share_val
                
                rows.append(row)
    
    # === Process fuel shares for secondary pulp production ===
    secondary_pulp_fuel_data = share_fuel_secondary_pulp(years, scenarios)
    
    secondary_pulp_fuel_metric_map = {
        "diesel": "Share of diesel for secondary pulp production",
        "natural_gas": "Share of natural gas for secondary pulp production",
        "electricity": "Share of electricity for secondary pulp production",
        "coal": "Share of coal for secondary pulp production",
        "heat": "Share of heat for secondary pulp production",
        "biomass": "Share of biomass for secondary pulp production",
        "hydrogen": "Share of hydrogen for secondary pulp production",
    }
    
    for fuel_key, metric_name in secondary_pulp_fuel_metric_map.items():
        fuel_year_data = secondary_pulp_fuel_data.get(fuel_key, {})
        
        for year in years:
            if year not in fuel_year_data:
                continue
            year_data = fuel_year_data[year]
            
            for sc_idx, scenario in enumerate(scenarios):
                share_val = year_data.get(scenario, 0.0)
                
                row = {
                    "Assumption Type": "SHARE",
                    "Metric Name": metric_name,
                    "Year": year,
                    "Scenario": scenario,
                    "default": share_val
                }
                
                for country in countries:
                    row[country] = share_val
                
                rows.append(row)
    
    # === Process fuel shares for paper production ===
    paper_fuel_data = share_fuel_paper(years, scenarios)
    
    paper_fuel_metric_map = {
        "diesel": "Share of diesel for paper production",
        "natural_gas": "Share of natural gas for paper production",
        "electricity": "Share of electricity for paper production",
        "coal": "Share of coal for paper production",
        "heat": "Share of heat for paper production",
        "biomass": "Share of biomass for paper production",
        "hydrogen": "Share of hydrogen for paper production",
    }
    
    for fuel_key, metric_name in paper_fuel_metric_map.items():
        fuel_year_data = paper_fuel_data.get(fuel_key, {})
        
        for year in years:
            if year not in fuel_year_data:
                continue
            year_data = fuel_year_data[year]
            
            for sc_idx, scenario in enumerate(scenarios):
                share_val = year_data.get(scenario, 0.0)
                
                row = {
                    "Assumption Type": "SHARE",
                    "Metric Name": metric_name,
                    "Year": year,
                    "Scenario": scenario,
                    "default": share_val
                }
                
                for country in countries:
                    row[country] = share_val
                
                rows.append(row)
    
    # === Process fuel shares for unspecified paper and pulp ===
    unspec_pp_fuel_data = share_fuel_unspecified_paper_pulp(years, scenarios)
    
    unspec_pp_fuel_metric_map = {
        "diesel": "Share of diesel for unspecified paper and pulp",
        "natural_gas": "Share of natural gas for unspecified paper and pulp",
        "electricity": "Share of electricity for unspecified paper and pulp",
        "coal": "Share of coal for unspecified paper and pulp",
        "heat": "Share of heat for unspecified paper and pulp",
        "biomass": "Share of biomass for unspecified paper and pulp",
        "hydrogen": "Share of hydrogen for unspecified paper and pulp",
    }
    
    for fuel_key, metric_name in unspec_pp_fuel_metric_map.items():
        fuel_year_data = unspec_pp_fuel_data.get(fuel_key, {})
        
        for year in years:
            if year not in fuel_year_data:
                continue
            year_data = fuel_year_data[year]
            
            for sc_idx, scenario in enumerate(scenarios):
                share_val = year_data.get(scenario, 0.0)
                
                row = {
                    "Assumption Type": "SHARE",
                    "Metric Name": metric_name,
                    "Year": year,
                    "Scenario": scenario,
                    "default": share_val
                }
                
                for country in countries:
                    row[country] = share_val
                
                rows.append(row)
    
    # =====================================================================
    # === OTHER INDUSTRIES SHARES (food & tobacco, construction, machinery, etc.)
    # =====================================================================
    # These fuel shares are generated with default=0 so users can specify
    # country-specific values. If left as 0/blank, build_config_industry.py 
    # will use 2020 historical UNSD fuel shares.
    # =====================================================================
    
    other_industries = [
        "food and tobacco",
        "construction",
        "machinery",
        "mining and quarrying",
        "non-ferrous metals",
        "textile and leather",
        "transport equipment",
        "wood and wood products",
    ]
    
    other_industry_fuels = ["diesel", "natural gas", "electricity", "coal", "heat", "biomass", "hydrogen"]
    
    for industry in other_industries:
        for fuel in other_industry_fuels:
            metric_name = f"Share of {fuel} for unspecified {industry}"
            
            for year in years:
                for scenario in scenarios:
                    row = {
                        "Assumption Type": "SHARE",
                        "Metric Name": metric_name,
                        "Year": year,
                        "Scenario": scenario,
                        "default": 0.0
                    }
                    
                    for country in countries:
                        row[country] = 0.0
                    
                    rows.append(row)

    df = pd.DataFrame(rows)
    
    # Reorder columns: put countries after 'default'
    base_cols = ["Assumption Type", "Metric Name", "Year", "Scenario", "default"]
    country_cols = [c for c in countries if c in df.columns]
    df = df[base_cols + country_cols]
    
    df.to_csv(output_path, index=False)
    return df

