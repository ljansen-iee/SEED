import os
import pandas as pd
from pathlib import Path
import glob
import build_energy_intensities as build_en_int
from contextlib import contextmanager
from contextvars import ContextVar

DEFAULT_TARGET_YEARS = [2020, 2030, 2035, 2040, 2045, 2050]
_INPUT_DIR = ContextVar("residential_input_dir", default=None)


def load_shared_residential_shares(path, share_mode="base_period_2017_2023"):
    """Read the canonical households shared table without changing factors."""
    frame = pd.read_csv(path)
    fuels = ["oil", "gas", "electricity", "coal", "biomass", "ammonia"]
    missing = set(["country", "share_mode", *fuels]) - set(frame.columns)
    if missing:
        raise ValueError(f"{path} is missing columns: {sorted(missing)}")
    frame = frame[frame["share_mode"].astype(str).str.lower() == share_mode.lower()].copy()
    if frame.empty or frame["country"].isna().any() or frame.duplicated("country").any():
        raise ValueError(f"Expected populated, unique countries for {share_mode} in {path}")
    frame[fuels] = frame[fuels].apply(pd.to_numeric, errors="coerce")
    if frame[fuels].isna().any().any() or ((frame[fuels] < 0) | (frame[fuels] > 1)).any().any():
        raise ValueError(f"Invalid fuel shares in {path}")
    sums = frame[fuels].sum(axis=1)
    if ((sums > 0) & ((sums - 1).abs() > 1e-3)).any():
        raise ValueError(f"Fuel shares do not sum to one in {path}")
    frame = frame.rename(columns={"country": "Country", "oil": "residential oil_share",
        "gas": "residential gas_share", "biomass": "residential biomass_share",
        "electricity": "electricity residential_share"})
    result = frame.set_index("Country")[["residential oil_share", "residential gas_share",
        "residential biomass_share", "electricity residential_share"]].copy()
    for name in SH_METRICS:
        if name not in result:
            result[name] = 0.0
    return result


@contextmanager
def residential_source_paths(input_dir=None, shares_csv_path=None):
    """Scoped source-reader adapters for legacy siblings with no path arguments.

    Only readers are rebound, never factor/calculation functions. Restore them
    on success and failure; imports alone perform neither reads nor writes.
    """
    import build_CAGR as cagr
    import build_technology_shares as technology

    directory = Path(input_dir) if input_dir is not None else Path(__file__).resolve().parent / "input_data"
    token = _INPUT_DIR.set(directory)
    previous_regions = cagr.build_Africa_regions
    previous_shares = technology.load_centralized_residential_shares

    def read_regions():
        frame = pd.read_csv(directory / "global" / "UNSD — Methodology.csv")
        frame = frame[frame["Region Name"] == "Africa"]
        frame = frame[["Sub-region Name", "Intermediate Region Name", "Country or Area"]].copy()
        frame["Intermediate Region Name"] = frame["Intermediate Region Name"].fillna(frame["Sub-region Name"])
        frame = frame.drop(columns="Sub-region Name")
        frame.columns = ["subregion", "country"]
        frame = frame.set_index("country")
        return frame, frame["subregion"].unique()

    def read_shares(share_mode="base_period_2017_2023"):
        return load_shared_residential_shares(shares_csv_path, share_mode)

    try:
        cagr.build_Africa_regions = read_regions
        if shares_csv_path is not None:
            technology.load_centralized_residential_shares = read_shares
        yield
    finally:
        cagr.build_Africa_regions = previous_regions
        technology.load_centralized_residential_shares = previous_shares
        _INPUT_DIR.reset(token)


def validate_residential_sources(input_dir, countries):
    """Fail explicitly for absent raw inputs rather than fabricating parameters."""
    directory = Path(input_dir)
    historical = directory / "unsdata_historical"
    if not historical.is_dir():
        historical = directory / "country_specific"
    paths = [historical / f"chart-data_{kind}_{country}.csv"
             for country in countries for kind in ("pop", "gdp")]
    paths += [directory / "global" / name for name in (
        "residential_floor_area_arab_regions.csv", "CLASS_worldbank.xlsx",
        "gdp-per-capita-worldbank.csv", "undesa_pd_2022_hh-size-composition_ALL_COUNTRIES_raw.xlsx",
        "wb_acces_ele_2024_all.csv", "wb_acces_cooking_2024_all.csv",
        "UNSD — Methodology.csv", "98667-WP-P146621-PUBLIC-Box393179B.pdf")]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing residential raw inputs:\n" + "\n".join(missing))


def open_pdf(file_path, pages="1", multiple_tables=False, encoding="latin1", **kwargs):
    """
    Reads tables from a PDF file using tabula-py.
    """
    if _INPUT_DIR.get() is not None:
        file_path = _INPUT_DIR.get() / "global" / Path(file_path).name
    try:
        # Preferred import style for tabula-py
        from tabula.io import read_pdf  # tabula-py
    except Exception as e:
        raise ImportError(
            "tabula-py is required to read PDFs, but it could not be imported.\n"
            "Fix: `pip install -U tabula-py` (and ensure Java is installed),\n"
            "and make sure you don't have a different 'tabula' package shadowing it."
        ) from e

    return read_pdf(
        file_path,
        pages=pages,
        multiple_tables=multiple_tables,
        encoding=encoding,
        **kwargs,
    )
def read_file(file_path,pdf_options=None):
    """Read a CSV, Excel, or PDF file into a DataFrame.

    Args:
        file_path: Path to the file (must end in ``.csv``, ``.xlsx``,
            or ``.pdf``).
        pdf_options: Reserved for future PDF handling.

    Returns:
        pd.DataFrame | None: Parsed data, or ``None`` for PDFs and on
        errors.
    """
    try:
        if file_path.endswith('.csv'):
            return pd.read_csv(file_path, encoding="utf8")
        elif file_path.endswith('.xlsx'):
            return pd.read_excel(file_path, engine='openpyxl')
        elif file_path.endswith('.pdf'):
            # PDFs are not loaded here; handle them manually with open_pdf()
            return None
        else:
            raise ValueError(f"Unsupported file extension: {file_path}")
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None
        
def load_files_from_folder(folder_path):
    """Load every file in *folder_path* into a dict of DataFrames.

    Args:
        folder_path: Directory to scan.

    Returns:
        dict[str, pd.DataFrame]: Mapping of filename → DataFrame.
    """
    return {file_doc: read_file(os.path.join(folder_path, file_doc)) 
            for file_doc in os.listdir(folder_path)}       

    
def load_all_files(energy_sector="residential", base_dir=None):
    """Load country-specific and global input data for a sector.

    Scans ``{base_dir}/{energy_sector}/input_data/`` for the
    ``unsdata_historical`` and ``global`` sub-folders and reads every
    file therein.

    Args:
        energy_sector: Sector name (used as directory name).
        base_dir: Repository root; auto-detected if ``None``.

    Returns:
        tuple[dict, dict]: ``(unsdata_historical_dfs, global_dfs)``.

    Raises:
        FileNotFoundError: If the resolved path does not exist.
    """
    if base_dir is None:
        if '__file__' in globals():
            base_dir = os.path.dirname(os.path.abspath(__file__))
        else:
            base_dir = os.getcwd()
    # Prevent double folder names if energy_sector is empty or already in base_dir
    if energy_sector and os.path.basename(os.path.normpath(base_dir)).lower() != energy_sector.lower():
        path = os.path.join(base_dir, energy_sector, "input_data")
    else:
        path = os.path.join(base_dir, "input_data")

    if _INPUT_DIR.get() is not None:
        path = str(_INPUT_DIR.get())
    dfs_country_spe = {}  # Dict to hold df
    dfs_global = {}  # Dict to hold df

    if not os.path.exists(path):
        raise FileNotFoundError(f"The path {path} does not exist.")
    
    historical_folder = "unsdata_historical" if (Path(path) / "unsdata_historical").is_dir() else "country_specific"
    for folder_name in [historical_folder, 'global']:
        folder_path = os.path.join(path, folder_name)
        if os.path.exists(folder_path):
            if folder_name == historical_folder:
                dfs_country_spe = load_files_from_folder(folder_path)
            elif folder_name == 'global':
                dfs_global = load_files_from_folder(folder_path)
    return dfs_country_spe, dfs_global

def generate_units_dictionary():
    """Return the canonical mapping of residential metrics to their units.

    The dictionary covers macro indicators, saturation rates, technology
    shares, and energy intensities for all five residential end-uses
    (space heating/cooling, water heating, cooking, appliances).

    Returns:
        dict[str, str]: Metric name → unit string.
    """
    data_units_dict = {
    "Population": "persons",
    "Residential Area per Person": "m2/p",
    "Persons per Dwelling": "p/dw",

    "Saturation of Space Heating": "% of m2",
    "Saturation of Space Cooling": "% of m2",
    "Saturation of Water Heating": "% of dw",
    "Saturation of Cooking": "% of dw",
    "Saturation of Appliances": "% of dw",
    
    "Share of Oil Boilers for Space Heating" : "% of Space Heating",
    "Share of LPG Boilers for Space Heating": "% of Space Heating",
    "Share of Natural Gas Boilers for Space Heating": "% of Space Heating",
    "Share of Kerosene Boilers for Space Heating": "% of Space Heating",
    "Share of Coal Boilers for Space Heating": "% of Space Heating",
    "Share of Biogas Boilers for Space Heating": "% of Space Heating",
    "Share of Traditional Biomass Boilers for Space Heating": "% of Space Heating",
    "Share of Modern Biomass Boilers for Space Heating": "% of Space Heating",
    "Share of Hydrogen Boilers for Space Heating": "% of Space Heating",
    "Share of Solar Heating for Space Heating": "% of Space Heating",
    "Share of District Heating for Space Heating": "% of Space Heating",
    "Share of Electric Heaters for Space Heating": "% of Space Heating",
    "Share of Heat Pumps for Space Heating": "% of Space Heating",

    "Share of Heat Pumps for Space Cooling": "% of Space Cooling",
    "Share of Air Conditioning for Space Cooling": "% of Space Cooling",

    "Share of Oil Boilers for Water Heating": "% of Water Heating",
    "Share of LPG Boilers for Water Heating": "% of Water Heating",
    "Share of Natural Gas Boilers for Water Heating": "% of Water Heating",
    "Share of Kerosene Boilers for Water Heating": "% of Water Heating",
    "Share of Coal Boilers for Water Heating": "% of Water Heating",
    "Share of Biogas Boilers for Water Heating": "% of Water Heating",
    "Share of Traditional Biomass Boilers for Water Heating": "% of Water Heating",
    "Share of Modern Biomass Boilers for Water Heating": "% of Water Heating",
    "Share of Hydrogen Boilers for Water Heating": "% of Water Heating",
    "Share of Solar Heating for Water Heating": "% of Water Heating",
    "Share of District Heating for Water Heating": "% of Water Heating",
    "Share of Electric Heaters for Water Heating": "% of Water Heating",
    "Share of Heat Pumps for Water Heating": "% of Water Heating",

    "Share of Electric Stoves for Cooking": "% of Cooking",
    "Share of Natural Gas Stoves for Cooking": "% of Cooking",
    "Share of LPG Stoves for Cooking": "% of Cooking",
    "Share of Kerosene Stoves for Cooking": "% of Cooking",
    "Share of Traditional Biomass Stoves for Cooking": "% of Cooking",

    "Final Energy Intensity of Oil Boilers for Space Heating": "kWh/m2",
    "Final Energy Intensity of LPG Boilers for Space Heating": "kWh/m2",
    "Final Energy Intensity of Natural Gas Boilers for Space Heating": "kWh/m2",
    "Final Energy Intensity of Kerosene Boilers for Space Heating": "kWh/m2",
    "Final Energy Intensity of Coal Boilers for Space Heating": "kWh/m2",
    "Final Energy Intensity of Biogas Boilers for Space Heating": "kWh/m2",
    "Final Energy Intensity of Traditional Biomass Boilers for Space Heating": "kWh/m2",
    "Final Energy Intensity of Modern Biomass Boilers for Space Heating": "kWh/m2",
    "Final Energy Intensity of Hydrogen Boilers for Space Heating": "kWh/m2",
    "Final Energy Intensity of Solar Heating for Space Heating": "kWh/m2",
    "Final Energy Intensity of District Heating for Space Heating": "kWh/m2",
    "Final Energy Intensity of Electric Heaters for Space Heating": "kWh/m2",
    "Final Energy Intensity of Heat Pumps for Space Heating": "kWh/m2",
    "Final Energy Intensity of Heat Pumps for Space Cooling": "kWh/m2",
    "Final Energy Intensity of Air Conditioning for Space Cooling": "kWh/m2",
    "Final Energy Intensity of Oil Boilers for Water Heating": "kWh/dw",
    "Final Energy Intensity of LPG Boilers for Water Heating": "kWh/dw",
    "Final Energy Intensity of Natural Gas Boilers for Water Heating": "kWh/dw",
    "Final Energy Intensity of Kerosene Boilers for Water Heating": "kWh/dw",
    "Final Energy Intensity of Coal Boilers for Water Heating": "kWh/dw",
    "Final Energy Intensity of Biogas Boilers for Water Heating": "kWh/dw",
    "Final Energy Intensity of Traditional Biomass Boilers for Water Heating": "kWh/dw",
    "Final Energy Intensity of Modern Biomass Boilers for Water Heating": "kWh/dw",
    "Final Energy Intensity of Hydrogen Boilers for Water Heating": "kWh/dw",
    "Final Energy Intensity of Solar Heating for Water Heating": "kWh/dw",
    "Final Energy Intensity of District Heating for Water Heating": "kWh/dw",
    "Final Energy Intensity of Electric Heaters for Water Heating": "kWh/dw",
    "Final Energy Intensity of Heat Pumps for Water Heating": "kWh/dw",
    "Final Energy Intensity of Electric Stoves for Cooking": "kWh/dw",
    "Final Energy Intensity of Natural Gas Stoves for Cooking": "kWh/dw",
    "Final Energy Intensity of LPG Stoves for Cooking": "kWh/dw",
    "Final Energy Intensity of Kerosene Stoves for Cooking": "kWh/dw",
    "Final Energy Intensity of Traditional Biomass Stoves for Cooking": "kWh/dw",
    "Final Energy Intensity of Electrical Appliances": "kWh/dw",

    }
    return data_units_dict


SH_METRICS = {
    "residential oil_share": "Share of Oil Boilers for Space Heating",
    "lpg_share": "Share of LPG Boilers for Space Heating",
    "residential gas_share": "Share of Natural Gas Boilers for Space Heating",
    "kerosene_share": "Share of Kerosene Boilers for Space Heating",
    "coal_share": "Share of Coal Boilers for Space Heating",
    "biogas_share": "Share of Biogas Boilers for Space Heating",
    "residential biomass_share": "Share of Traditional Biomass Boilers for Space Heating",
    "modern_biomass_share": "Share of Modern Biomass Boilers for Space Heating",
    "hydrogen_share": "Share of Hydrogen Boilers for Space Heating",
    "solar_share": "Share of Solar Heating for Space Heating",
    "district_heating_share": "Share of District Heating for Space Heating",
    "electricity residential_share": "Share of Electric Heaters for Space Heating",
    "heat_pumps_share": "Share of Heat Pumps for Space Heating",
}

COOKING_METRICS = {
    "Share of Electric Stoves for Cooking": "electricity",
    "Share of Natural Gas Stoves for Cooking": "natural gas",
    "Share of LPG Stoves for Cooking": None,
    "Share of Kerosene Stoves for Cooking": "kerosene",
    "Share of Traditional Biomass Stoves for Cooking": "biomass",
}

CAGR_SCENARIO_MAP = {
    "Current Policies": "BAU",
    "Progessive Measuraments": "Progressive",
    "Ambitious Net Zero": "Optimistic",
}

CAGR_UNITS_MAP = {
    "Final Energy Intensity of Space Heating": "kWh/m2",
    "Final Energy Intensity of Space Cooling": "kWh/m2",
    "Final Energy Intensity of Water Heating": "kWh/dw",
    "Final Energy Intensity of Cooking": "kWh/dw",
    "Final Energy Intensity of Electrical Appliances": "kWh/dw",
}

SATURATION_SCENARIO_MAP = {
    "baseline": "BAU",
    "Current Policies": "BAU",
    "Progessive Measuraments": "Progressive",
    "Ambitious Net Zero": "Optimistic",
}

INTENSITY_METRICS_MAP = {
    "Final Energy Intensity of Space Heating": build_en_int.SPACE_HEATING_INTENSITY_METRICS,
    "Final Energy Intensity of Space Cooling": build_en_int.SPACE_COOLING_INTENSITY_METRICS,
    "Final Energy Intensity of Water Heating": build_en_int.WATER_HEATING_INTENSITY_METRICS,
    "Final Energy Intensity of Cooking": build_en_int.COOKING_INTENSITY_METRICS,
    "Final Energy Intensity of Electrical Appliances": build_en_int.APPLIANCES_INTENSITY_METRICS,
}


def load_residential_config(path: Path, countries: list, scenarios: list):
    """Load the residential configuration CSV and build a nested dict.

    Reads a CSV with columns ``Assumption Type``, ``Metric Name``,
    ``Year``, ``Scenario``, ``default``, and optional country columns.
    Country-specific values override the default.

    Args:
        path: Path to the CSV config file.
        countries: Country names to extract (must match column headers).
        scenarios: Ordered list of scenario names.

    Returns:
        dict: Nested ``{country: {metric: {assumption_type, values}}}``
        structure.

    Raises:
        ValueError: If required columns are missing.
    """
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()

    required_cols = {
        "Assumption Type",
        "Metric Name",
        "Year",
        "Scenario",
        "default"
    }
    if not required_cols.issubset(df.columns):
        raise ValueError(f"Excel must contain columns: {required_cols}")

    SCENARIO_ALIAS_MAP = {"sc_a": 0, "sc_b": 1, "sc_c": 2}

    config = {c: {} for c in countries}

    for _, row in df.iterrows():
        metric = str(row["Metric Name"]).strip()

        try:
            year = int(row["Year"])
        except Exception:
            continue

        scenario_val = str(row["Scenario"]).strip()
        scenario_val_lower = scenario_val.lower()
        default_val = row["default"]

        for country in countries:
            if country in df.columns and pd.notna(row[country]):
                val = float(row[country])
            elif pd.notna(default_val):
                val = float(default_val)
            else:
                continue

            # Resolve scenario
            if scenario_val in scenarios:
                target_scenarios = [scenario_val]
            elif scenario_val_lower == "all":
                target_scenarios = scenarios
            elif scenario_val_lower in SCENARIO_ALIAS_MAP:
                idx = SCENARIO_ALIAS_MAP[scenario_val_lower]
                if idx < len(scenarios):
                    target_scenarios = [scenarios[idx]]
                else:
                    continue
            else:
                continue

            for s in target_scenarios:
                entry = config[country].setdefault(
                    metric,
                    {
                        "assumption_type": str(row["Assumption Type"]).strip().upper(),
                        "values": {}
                    }
                )
                entry["values"].setdefault(year, {})[s] = val

    return config