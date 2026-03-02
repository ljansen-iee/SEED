# share_primary_pulp.py
import os  # Import OS module for file and directory operations
import pandas as pd  # Import pandas for data manipulation

def find_input_folder():
    current_dir = os.path.abspath(os.path.dirname(__file__))
    max_levels_up = 5
    for _ in range(max_levels_up):
        candidate = os.path.join(current_dir, 'input_data', 'paper_and_pulp')
        if os.path.isdir(candidate):
            return candidate
        current_dir = os.path.dirname(current_dir)
    raise FileNotFoundError(f"'input_data/paper_and_pulp' folder not found after checking up to {max_levels_up} levels up")

def find_oecd_file():
    input_folder = find_input_folder()
    file_name = "OECD-Stat-EEI_INDUSTRY_13062022164438544 (version 1).csv"
    file_path = os.path.join(input_folder, file_name)
    if os.path.isfile(file_path):
        return file_path
    else:
        raise FileNotFoundError(f"File '{file_name}' not found in '{input_folder}'")

def load_data(file_path: str) -> pd.DataFrame:
    return pd.read_csv(file_path)  # Load the CSV file into a DataFrame

def get_oecd_df (year: int, use_filter: str, countries: list) -> pd.DataFrame:
    file_path = find_oecd_file()  # Find the OECD file path
    df = load_data(file_path)  # Load the data into a DataFrame

    # Strip whitespace from columns
    df.columns = df.columns.str.strip()  # Remove leading/trailing spaces from column names

    # Drop columns safely if present
    columns_to_drop = ['Flag Codes', 'Flags', 'Unnamed: 11']  # Columns to drop if they exist
    df = df.drop(columns=[col for col in columns_to_drop if col in df.columns])  # Drop columns if present

    # Use the existing 'Country' and 'Time' columns directly, stripping spaces in values
    df['Country'] = df['Country'].astype(str).str.strip()  # Strip spaces from country names
    df['Time'] = pd.to_numeric(df['Time'], errors='coerce')  # Convert 'Time' column to numeric for filtering

    # Clean input country list as well
    countries_clean = [c.strip() for c in countries]  # Remove spaces from input country names

    # Filter by year and ENDUSE (case-sensitive)
    df_filtered = df[(df['Time'] == year) & (df['ENDUSE'] == use_filter)]  # Filter by year and ENDUSE

    # Filter by countries
    df_filtered = df_filtered[df_filtered['Country'].isin(countries_clean)].reset_index(drop=True)  # Filter by country

    if df_filtered.empty:  # If no data after filtering
        #print(f"unique years in data: {df['Time'].unique()}")
        #print(f" unique ENDUSE values: {df['ENDUSE'].unique()}")
        #print(f"unique countries in data: {df['Country'].unique()}")
        print(f"Given filters => year: {year}, use_filter: '{use_filter}', countries: {countries_clean}")

    # Add share per country if data present
    if not df_filtered.empty:
        # Calculate share as percentage of each country's value over the sum for that country
        df_filtered['share'] = df_filtered.groupby('Country')['Value'].transform(lambda x: x / x.sum() * 100)
    else:
        df_filtered['share'] = []  # If empty, set share as empty list

    return df_filtered  # Return the filtered DataFrame

from typing import Dict, List, Optional
import sys
# Allow importing helper functions from parent directories
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from build_CAGR import interpolate_or_extrapolate

def share_fuel_primary_pulp(
    target_years: List[int],
    scenarios: Optional[List[str]] = None,
) -> Dict[str, Dict[int, Dict[str, float]]]:
    
    if scenarios is None:
        scenarios = SCENARIOS

    base_data = {
        "diesel": {
            2020: [55, 55, 55],
            2030: [55, 5, 5],
            2050: [55, 0, 0],
        },
        "natural_gas": {
            2020: [45, 45, 45],
            2030: [45, 5, 0],  
            2050: [45, 0, 0],
        },
        "electricity": {
            2020: [0, 0, 0],
            2030: [0, 25, 35],   
            2050: [0, 65, 75],
        },
        "coal": {
            2020: [0, 0, 0],
            2030: [0, 0, 0],
            2050: [0, 0, 0],
        },
        "heat": {
            2020: [0, 0, 0],
            2030: [0, 0, 0],
            2050: [0, 0, 0],
        },
        "biomass": {
            2020: [0, 0, 0],
            2030: [0, 65, 59],
            2050: [0, 30, 10],
        },
        "hydrogen": {
            2020: [0, 0, 0],
            2030: [0, 0.1, 1],
            2050: [0, 5, 15],
        },
    }

    result: Dict[str, Dict[int, Dict[str, float]]] = {}

    for fuel, yearly_values in base_data.items():
        per_scenario: Dict[str, Dict[int, float]] = {}
        for i, sc in enumerate(scenarios):
            # pick the i-th value from the list for each year
            sc_dict = {year: vals[i] if i < len(vals) else vals[-1] for year, vals in yearly_values.items()}
            per_scenario[sc] = interpolate_or_extrapolate(sc_dict, [2020] + target_years)

        # reassemble into fuel -> year -> scenario
        result[fuel] = {
            year: {sc: per_scenario[sc][year] for sc in scenarios}
            for year in [2020] + target_years
        }

    # sanity check per year / scenario
    for y in [2020] + target_years:
        for sc in scenarios:
            total = sum(result[f][y][sc] for f in result)
            if abs(total - 100) > 1:
                print(f" Warning: PRIMARY pulp fuel shares total = {total:.2f}% in {y} ({sc})")

    return result


def share_fuel_secondary_pulp(
    target_years: List[int],
    scenarios: Optional[List[str]] = None,
) -> Dict[str, Dict[int, Dict[str, float]]]:
    
    if scenarios is None:
        scenarios = SCENARIOS

    base_data = {
        "diesel": {
            2020: [55, 55, 55],
            2030: [55, 1, 0],
            2050: [55, 0, 0],
        },
        "natural_gas": {
            2020: [45, 45, 45],
            2030: [45, 1, 0],
            2050: [45, 0, 0],
        },
        "electricity": {
            2020: [0, 0, 0],
            2030: [0, 70, 75],
            2050: [0, 80, 90],
        },
        "coal": {
            2020: [0, 0, 0],
            2030: [0, 0, 0],
            2050: [0, 0, 0],
        },
        "heat": {
            2020: [0, 0, 0],
            2030: [0, 0, 0],
            2050: [0, 0, 0],
        },
        "biomass": {
            2020: [0, 0, 0],
            2030: [0, 29, 25],
            2050: [0, 20, 10],
        },
        "hydrogen": {
            2020: [0, 0, 0],
            2030: [0, 0, 0],
            2050: [0, 0, 0],
        },
    }

    result: Dict[str, Dict[int, Dict[str, float]]] = {}

    for fuel, yearly_values in base_data.items():
        per_scenario: Dict[str, Dict[int, float]] = {}
        for i, sc in enumerate(scenarios):
            sc_dict = {year: vals[i] if i < len(vals) else vals[-1] for year, vals in yearly_values.items()}
            per_scenario[sc] = interpolate_or_extrapolate(sc_dict, [2020] + target_years)

        result[fuel] = {
            year: {sc: per_scenario[sc][year] for sc in scenarios}
            for year in [2020] + target_years
        }

    # sanity check
    for y in [2020] + target_years:
        for sc in scenarios:
            total = sum(result[f][y][sc] for f in result)
            if abs(total - 100) > 1:
                print(f" Warning: SECONDARY pulp fuel shares total = {total:.2f}% in {y} ({sc})")

    return result


def share_primary_secondary_pulp(
    target_years: List[int],
    scenarios: Optional[List[str]] = None,
) -> Dict[str, Dict[int, Dict[str, float]]]:
    if scenarios is None:
        scenarios = SCENARIOS

    base_data = {
        "primary": {
            2020: [95, 95, 95],
            2030: [95, 85, 75],  
            2050: [95, 65, 40],  
        },
        "secondary": {
            2020: [5, 5, 5],
            2030: [5, 15, 25],
            2050: [5, 35, 60],  
        },
    }

    result: Dict[str, Dict[int, Dict[str, float]]] = {}

    for category, yearly_values in base_data.items():
        per_scenario: Dict[str, Dict[int, float]] = {}
        for i, sc in enumerate(scenarios):
            sc_dict = {year: vals[i] if i < len(vals) else vals[-1] for year, vals in yearly_values.items()}
            per_scenario[sc] = interpolate_or_extrapolate(sc_dict, [2020] + target_years)

        result[category] = {
            year: {sc: per_scenario[sc][year] for sc in scenarios}
            for year in [2020] + target_years
        }

    return result


def share_fuel_paper(
    target_years: List[int],
    scenarios: Optional[List[str]] = None,
) -> Dict[str, Dict[int, Dict[str, float]]]:
    
    if scenarios is None:
        scenarios = SCENARIOS

    base_data = {
        "diesel": {
            2020: [55, 55, 55],
            2030: [55, 8, 7],    
            2050: [55, 0, 0],
        },
        "natural_gas": {
            2020: [45, 45, 45],
            2030: [45, 2, 2],
            2050: [45, 0, 0],
        },
        "electricity": {
            2020: [0, 0, 0],
            2030: [0, 35, 40],
            2050: [0, 75, 85],
        },
        "coal": {
            2020: [0, 0, 0],
            2030: [0, 0, 0],
            2050: [0, 0, 0],
        },
        "heat": {
            2020: [0, 0, 0],
            2030: [0, 0, 0],
            2050: [0, 0, 0],
        },
        "biomass": {
            2020: [0, 0, 0],
            2030: [0, 55, 50],
            2050: [0, 24, 13],
        },
        "hydrogen": {
            2020: [0, 0, 0],
            2030: [0, 0.1, 1],
            2050: [0, 1, 2],
        },
    }

    result: Dict[str, Dict[int, Dict[str, float]]] = {}

    for fuel, yearly_values in base_data.items():
        per_scenario: Dict[str, Dict[int, float]] = {}
        for i, sc in enumerate(scenarios):
            sc_dict = {year: vals[i] if i < len(vals) else vals[-1] for year, vals in yearly_values.items()}
            per_scenario[sc] = interpolate_or_extrapolate(sc_dict, [2020] + target_years)

        result[fuel] = {
            year: {sc: per_scenario[sc][year] for sc in scenarios}
            for year in [2020] + target_years
        }

    # sanity check
    for y in [2020] + target_years:
        for sc in scenarios:
            total = sum(result[f][y][sc] for f in result)
            if abs(total - 100) > 1:
                print(f" Warning: PAPER fuel shares total = {total:.2f}% in {y} ({sc})")

    return result

def activity_unspecified_paper_pulp(
    target_years: List[int],
    scenarios: Optional[List[str]] = None,
) -> Dict[int, Dict[str, float]]:
    if scenarios is None:
        scenarios = SCENARIOS

    base_dict = {
        2020: [1.0, 1.0, 1.0],
        2030: [1.01, 1.01, 1.01],
        2050: [1.01, 1.01, 1.01],
    }

    result: Dict[int, Dict[str, float]] = {}

    for i, sc in enumerate(scenarios):
        sc_dict = {year: vals[i] for year, vals in base_dict.items()}
        interp = interpolate_or_extrapolate(sc_dict, [2020] + target_years)
        for year, val in interp.items():
            result.setdefault(year, {})[sc] = val

    return result


def share_fuel_unspecified_paper_pulp(
    target_years: List[int],
    scenarios: Optional[List[str]] = None,
) -> Dict[str, Dict[int, Dict[str, float]]]:
   
    if scenarios is None:
        scenarios = SCENARIOS

    base_data = {
        "diesel": {
            2020: [100, 100, 100],
            2030: [100, 20, 17],
            2050: [100, 12, 5],
        },
        "natural_gas": {
            2020: [0, 0, 0],
            2030: [0, 45, 42],
            2050: [0, 10, 0],
        },
        "electricity": {
            2020: [0, 0, 0],
            2030: [0, 35, 40],
            2050: [0, 75, 85],
        },
        "coal": {
            2020: [0, 0, 0],
            2030: [0, 0, 0],
            2050: [0, 0, 0],
        },
        "heat": {
            2020: [0, 0, 0],
            2030: [0, 0, 0],
            2050: [0, 0, 0],
        },
        "biomass": {
            2020: [0, 0, 0],
            2030: [0, 0, 0],
            2050: [0, 0, 0],
        },
        "hydrogen": {
            2020: [0, 0, 0],
            2030: [0, 0.1, 1],
            2050: [0, 3, 10],
        },
    }

    result: Dict[str, Dict[int, Dict[str, float]]] = {}

    for fuel, yearly_values in base_data.items():
        per_scenario: Dict[str, Dict[int, float]] = {}
        for i, sc in enumerate(scenarios):
            sc_dict = {year: vals[i] if i < len(vals) else vals[-1] for year, vals in yearly_values.items()}
            per_scenario[sc] = interpolate_or_extrapolate(sc_dict, [2020] + target_years)

        result[fuel] = {
            year: {sc: per_scenario[sc][year] for sc in scenarios}
            for year in [2020] + target_years
        }

    for y in [2020] + target_years:
        for sc in scenarios:
            total = sum(result[f][y][sc] for f in result)
            if abs(total - 100) > 1:
                print(f" Warning: UNSPECIFIED paper/pulp fuel shares total = {total:.2f}% in {y} ({sc})")

    return result

# --- Paper & Pulp: activity factor for "unspecified" (CAGR-based) ---
from typing import Dict, List, Optional
from scripts.non_metallic_minerals.build_energy_intensities_cement import activity_factor_unspecified_nmm

def activity_factor_unspecified_paper_pulp(
    base_year: int,
    target_years: List[int],
    scenarios: List[str],
    cagr_cfg: Dict,              
    base_value: float = 1.0,
    use_profile: bool = False,   
) -> Dict[int, Dict[str, float]]:
   
    return activity_factor_unspecified_nmm(
        base_value=base_value,
        base_year=base_year,
        target_years=target_years,
        cagr_cfg=cagr_cfg,
        scenarios=scenarios,
        use_profile=use_profile,
    )
