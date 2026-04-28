import pandas as pd
import numpy as np
from transport.build_CAGR import expand_with_piecewise_cagr, expand_constant, expand_with_cagr

def read_excel_file(file_path, sheet_name):
    pd.set_option('display.float_format', '{:.6f}'.format)
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        print("Excel file read successfully!")
        return df
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        return None

def get_base_intensity_values():
    """
    Returns a dictionary of baseline (2020) final energy intensities
    """
    base_intensity = {
        # ---------- LDV ----------
        "Final Energy Intensity - Gasoline ICE LDV": 0.57,
        "Final Energy Intensity - Diesel ICE LDV": 0.48,
        "Final Energy Intensity - LPG ICE LDV": 0.6,
        "Final Energy Intensity - BEV LDV": 0.2,
        "Final Energy Intensity - FCEV LDV": 0.36,
        "Final Energy Intensity - Diesel Plugin Hybrid LDV": 0.40,
        "Final Energy Intensity - Gasoline Plugin Hybrid LDV": 0.48,

        # ---------- Bus ----------
        "Final Energy Intensity - Diesel ICE Bus": 4.02,
        "Final Energy Intensity - BEV Bus": 1.81,
        "Final Energy Intensity - FCEV Bus": 2.99,
        "Final Energy Intensity - Diesel Plugin Hybrid Bus": 2.50,

        # ---------- 2&3 Wheelers ----------
        "Final Energy Intensity - Gasoline ICE 2&3W": 0.25,
        "Final Energy Intensity - BEV 2&3W": 0.06,

        # ---------- Passenger Trains ----------
        "Final Energy Intensity - Diesel ICE Passenger Train": 0.248 * 288,
        "Final Energy Intensity - Direct Electric Passenger Train": 0.082 * 288,
        "Final Energy Intensity - FCEV Passenger Train": 0.149 * 288,

        # ---------- Aviation ----------
        "Final Energy Intensity - Kerosene Passenger Plane": 0.696 * 100,
        "Final Energy Intensity - BEV Passenger Plane": 45.00,
        "Final Energy Intensity - FCEV Passenger Plane": 55.00,

        # ---------- Freight (Road) ----------
        "Final Energy Intensity - Diesel ICE LDT": 0.82 * 2.2,
        "Final Energy Intensity - BEV LDT": 0.32 * 2.2,
        "Final Energy Intensity - FCEV LDT": 0.69 * 2.2,
        "Final Energy Intensity - Diesel Plugin Hybrid LDT": 1.20,

        "Final Energy Intensity - Diesel ICE HDT": 0.82 * 9.4,
        "Final Energy Intensity - BEV HDT": 0.32 * 9.4,
        "Final Energy Intensity - FCEV HDT": 0.69 * 9.4,
        "Final Energy Intensity - Diesel Plugin Hybrid HDT": 2.30,

        # ---------- Freight Trains ----------
        "Final Energy Intensity - Diesel ICE Freight Train": 0.114 * 564,
        "Final Energy Intensity - Direct Electric Freight Train": 0.041 * 564,
        "Final Energy Intensity - FCEV Freight Train": 0.068 * 564,

        # ---------- Freight Ships ----------
        "Final Energy Intensity - Diesel Freight Ship": 0.119 * 508.00,
        "Final Energy Intensity - Methanol Freight Ship": 145.80,
        "Final Energy Intensity - Ammonia Freight Ship": 145.80,
        "Final Energy Intensity - BEV Freight Ship": 145.80,
        "Final Energy Intensity - FCEV Freight Ship": 0.071 * 508.00,


    }
    return base_intensity

def expand_intensity(metric_name, base_value, BASE_YEAR, TARGET_YEARS, SCENARIOS, cagr_values):
    try:
        # 1. Get the raw entry from the config
        entry = cagr_values.get(metric_name)

        # --- SAFETY GUARD 1: Check Base Value ---
        if (
            base_value is None
            or isinstance(base_value, (list, tuple))
            or not isinstance(base_value, (int, float))
        ):
            return expand_constant(1.0, BASE_YEAR, TARGET_YEARS, SCENARIOS)

        # --- SAFETY GUARD 2: Check if entry exists ---
        if not isinstance(entry, dict):
            return expand_constant(base_value, BASE_YEAR, TARGET_YEARS, SCENARIOS)

        # --- CRITICAL FIX START: Extract 'values' sub-dictionary ---
        # The loader returns: {'assumption_type': 'CAGR', 'values': {2030: ...}}
        # We need to grab specifically the 'values' part.
        cagr_data = entry.get("values", {})
        
        if not cagr_data:
            # Fallback: maybe the dictionary IS the values (legacy structure check)
            # If keys look like integers, assume it is the values dict
            if any(isinstance(k, int) or str(k).isdigit() for k in entry.keys()):
                cagr_data = entry
            else:
                # No valid data found -> return constant
                return expand_constant(base_value, BASE_YEAR, TARGET_YEARS, SCENARIOS)
        # --- CRITICAL FIX END ---

        parsed_cagr = {}
        for year, scen_dict in cagr_data.items():
            try:
                year_int = int(str(year).strip("'"))
            except ValueError:
                continue

            parsed_cagr[year_int] = {}
            if not isinstance(scen_dict, dict):
                continue

            for scen, val in scen_dict.items():
                try:
                    parsed_cagr[year_int][scen] = float(val)
                except Exception:
                    parsed_cagr[year_int][scen] = 0.0

        # --- Check if we successfully parsed any years ---
        if not parsed_cagr:
            return expand_constant(base_value, BASE_YEAR, TARGET_YEARS, SCENARIOS)
        
        # Proceed to calculation with actual data
        return expand_with_cagr(
            base_value,
            parsed_cagr,
            BASE_YEAR,
            TARGET_YEARS,
            SCENARIOS
        )

    except Exception as e:
        print(f" expand_intensity error for {metric_name}: {e}")
        return expand_constant(1.0, BASE_YEAR, TARGET_YEARS, SCENARIOS)


def generate_energy_intensities(
    selected_country,
    BASE_YEAR,
    TARGET_YEARS,
    SCENARIOS,
    cagr_values,
    BACKEND=None
):
    intensity_base = get_base_intensity_values()
    result = {}

    for metric, base_value in intensity_base.items():
        try:
            expanded = expand_intensity(
                metric_name=metric,
                base_value=base_value,
                BASE_YEAR=BASE_YEAR,
                TARGET_YEARS=TARGET_YEARS,
                SCENARIOS=SCENARIOS,
                cagr_values=cagr_values
            )
            result[metric] = expanded
        except Exception as e:
            print(f"[WARN] {metric}: Error during expansion ({e})")
            result[metric] = expand_constant(base_value, BASE_YEAR, TARGET_YEARS, SCENARIOS)

    return result