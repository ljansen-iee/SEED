"""
build_ammonia_from_undata.py
----------------------------
Processes the UNdata ammonia CSV export (FAO FAOSTAT / UN Comtrade format)
into scenario CSV files that can supplement or replace
``ammonia_all_countries_scenarios.xlsx``.

Input
~~~~~
``industry/input_data/petrochemicals/UNdata_Export_20250709_101100979.csv``

    Columns: Country or Area | Element | Year | Unit | Value | Value Footnotes
    Relevant elements:
        * ``Production``       → local_production  [tonnes]
        * ``Import Quantity``  → import_volumes     [tonnes]

Output
~~~~~~
A single CSV written to the same folder as this script:

    ``ammonia_volumes.csv``

Columns:
    path | country | year | local_production | import_volumes | total_demand |
    local_green_transformation_share | import_green_reallocation_share | CAGR_rate | CAGR_factor |
    exog_ammonia_conv_path | exog_ammonia_conv_path_MWh_nh3 |
    endog_ammonia_green_path | endog_ammonia_green_path_MWh_nh3

Note: Energy columns (*_MWh_nh3) are calculated using conversion factor:
    AMMONIA_MWH_PER_TON = 5.166 MWh/tonne

The ``path`` column contains the volume-scenario name (``mid_speed``,
``fast_track``, ``slow_mover``).  Use ``SCENARIO_MAPPING`` to translate the
pipeline scenario names (``BAU``, ``Progressive``, ``Optimistic``) to the
corresponding volume path before filtering.

Historical rows (up to last available year) contain actual measured values;
transformation shares and CAGR for those rows are set to 0/0/0 (no transformation applied).
Projected rows cover 2025–2050 in 5-year steps, starting from the last
available base value of each country.

Transformation indicators (defaults, easily overridden per country/year)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
local_green_transformation_share – Share of local production transitioning
                                   to green synthesis route (renewable pathway)
import_green_reallocation_share – Share of imports sourced from green/renewable
                                  ammonia supply chains
CAGR_rate – compound annual growth rate applied to production/imports.
             Stored as a fraction (e.g. 0.07 = 7 %).
CAGR_factor – cumulative growth multiplier = (1 + CAGR_rate)^(year − base_year)

Projected demand formulas
~~~~~~~~~~~~~~~~~~~~~~~~~
    exog_ammonia_conv_path  = base_local  × CAGR_factor × (1 − local_green_transformation_share)
    endog_ammonia_green_path = base_import × CAGR_factor × import_green_reallocation_share
                              + base_local × CAGR_factor × local_green_transformation_share
where base_local / base_import are the values at the country's last available
historical year.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Energy conversion factor (MWh per tonne of ammonia)
AMMONIA_MWH_PER_TON = 5.166

# Base year for projections
BASE_YEAR = 2020

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).resolve()
_INDUSTRY_ROOT = _SCRIPT_DIR.parents[3]

# Path to UNSD ammonia data
UNDATA_CSV = (
    _INDUSTRY_ROOT
    / "input_data"
    / "petrochemicals"
    / "UNdata_Export_20250709_101100979.csv"
)

# Path to country-specific UNSD data
unsd_path = _INDUSTRY_ROOT / "input_data" / "country_specific"

# Legacy Excel file path (for backwards compatibility)
AMMONIA_SCENARIO_XLSX = _INDUSTRY_ROOT / "input_data" / "petrochemicals" / "ammonia_all_countries_scenarios.xlsx"
AMMONIA_SCENARIO_SHEET = "combined_wide"

# Path to generated volumes CSV (output)
AMMONIA_VOLUMES_CSV = _INDUSTRY_ROOT / "output_data" / "interim_data" / "ammonia_volumes.csv"

# Default output directory (can be overridden)
OUTPUT_DIR = _INDUSTRY_ROOT / "output_data" / "interim_data"

# Projected years (5-year steps)
PROJECTION_YEARS: List[int] = [2025, 2030, 2035, 2040, 2045, 2050]

# Per-scenario, per-interval CAGR rates (annual fraction).
# Each inner dict maps a projection year to the rate applied FROM the previous
# projection year (or the country's last historical year) UP TO that year.
#
# Calibration reference: 40% total growth by 2050 from a ~2022 base ≈ 1.22%/yr flat.
# mid_speed  chained → ~1.16^28 ≈ +38%  (≈ 40% target) base on : https://es.weforum.org/publications/the-net-zero-industry-tracker/in-full/ammonia-industry/
# fast_track chained → ~1.18^28 ≈ +67%  (higher-demand optimistic path)
# slow_mover chained → ~1.07^28 ≈ +21%  (conservative)
CAGR_RATES: Dict[str, Dict[int, float]] = {
    #              year: annual rate for the interval ending at that year
    "mid_speed":  {2025: 0.015, 2030: 0.013, 2035: 0.012, 2040: 0.011, 2045: 0.010, 2050: 0.010},
    "fast_track": {2025: 0.020, 2030: 0.018, 2035: 0.016, 2040: 0.014, 2045: 0.012, 2050: 0.012},
    "slow_mover": {2025: 0.008, 2030: 0.008, 2035: 0.007, 2040: 0.007, 2045: 0.006, 2050: 0.005},
}

# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------
# Green transformation shares are defined in separate public dicts so users
# can tweak each indicator independently without touching the other.
#
# Each dict maps:  scenario_name  →  {anchor_year: value}
# Values for years between anchors are linearly interpolated.
# Values beyond the last anchor are held flat (np.interp behaviour).
#
# local_green_transformation_share (GALT_ANCHORS for backwards compatibility)
#   - Share of local production transitioning to green synthesis pathway
# import_green_reallocation_share (GAIR_ANCHORS for backwards compatibility)
#   - Share of imports sourced from green/renewable ammonia supply chains

GALT_ANCHORS: Dict[str, Dict[int, float]] = {
    "mid_speed":  {2020: 0.00, 2030: 0.20, 2050: 1.00},
    "fast_track": {2020: 0.00, 2030: 0.30, 2045: 1.00, 2050: 1.00},
    "slow_mover": {2020: 0.00, 2030: 0.10, 2050: 0.80},
}

GAIR_ANCHORS: Dict[str, Dict[int, float]] = {
    "mid_speed":  {2020: 0.00, 2030: 0.20, 2050: 1.00},
    "fast_track": {2020: 0.00, 2030: 0.30, 2045: 1.00, 2050: 1.00},
    "slow_mover": {2020: 0.00, 2030: 0.10, 2050: 0.80},
}

# Derived: all scenario names are the union of both dicts' keys
_SCENARIOS = sorted(set(GALT_ANCHORS) | set(GAIR_ANCHORS))

# ---------------------------------------------------------------------------
# Pipeline scenario → volume scenario mapping
# ---------------------------------------------------------------------------
# Maps the scenario labels used in build_config_industry.py / build_final_energy_demand.py
# to the volume scenarios defined above.  Edit this dict to reassign scenarios.

SCENARIO_MAPPING: Dict[str, str] = {
    "BAU":         "slow_mover",
    "Progressive": "mid_speed",
    "Optimistic":  "fast_track",
}

# Also export as _PIPELINE_TO_VOLUME_PATH for backwards compatibility
_PIPELINE_TO_VOLUME_PATH = SCENARIO_MAPPING


def _compute_cagr_factor(
    rates_by_year: Dict[int, float],
    base_year: int,
    target_year: int,
    projection_years: List[int],
) -> float:
    """
    Compute a cumulative growth factor by chaining per-interval CAGR rates.

    Each interval runs from the previous projection year (or *base_year* for
    the first interval) up to the current projection year, using the rate
    stored for that year in *rates_by_year*.

    Example for base_year=2022, target_year=2035, rates {2025:0.015, 2030:0.013, 2035:0.012}::

        factor = 1.015**3  ×  1.013**5  ×  1.012**5
    """
    factor = 1.0
    prev = base_year
    for yr in sorted(projection_years):
        if yr > target_year:
            break
        rate = rates_by_year[yr]
        factor *= (1.0 + rate) ** (yr - prev)
        prev = yr
    return factor


def _interpolate_indicator(
    anchors: Dict[int, float], years: List[int]
) -> np.ndarray:
    """
    Linearly interpolate a single indicator from anchor points to *years*.
    Extrapolates flat beyond the last anchor (np.interp default).

    Parameters
    ----------
    anchors:
        ``{anchor_year: value}`` mapping (e.g. from GALT_ANCHORS or GAIR_ANCHORS).
    years:
        List of target years.

    Returns
    -------
    numpy array of interpolated values, one per entry in *years*.
    """
    anchor_years = sorted(anchors.keys())
    anchor_vals = [anchors[y] for y in anchor_years]
    return np.interp(years, anchor_years, anchor_vals)


# ---------------------------------------------------------------------------
# Loading & cleaning
# ---------------------------------------------------------------------------


def load_undata(path: Path = UNDATA_CSV) -> pd.DataFrame:
    """
    Load the UNdata CSV and return a clean wide-format DataFrame:

        country | year | local_production | import_volumes

    Only ``Production`` and ``Import Quantity`` elements are retained.
    Rows with NaN values are filled with 0.
    """
    raw = pd.read_csv(path, low_memory=False)

    # Normalise column names
    raw.columns = raw.columns.str.strip()
    raw = raw.rename(columns={"Country or Area": "country"})

    # Keep only relevant elements
    keep_elements = {"Production": "local_production", "Import Quantity": "import_volumes"}
    raw = raw[raw["Element"].isin(keep_elements)]
    raw = raw.copy()
    raw["element_clean"] = raw["Element"].map(keep_elements)

    # Convert value to numeric (some cells may be blank / special chars)
    raw["Value"] = pd.to_numeric(raw["Value"], errors="coerce").fillna(0.0)

    # Pivot to wide format
    wide = raw.pivot_table(
        index=["country", "Year"],
        columns="element_clean",
        values="Value",
        aggfunc="sum",
    ).reset_index()
    wide.columns.name = None
    wide = wide.rename(columns={"Year": "year"})

    # Ensure both columns exist even if absent in pivot
    for col in ("local_production", "import_volumes"):
        if col not in wide.columns:
            wide[col] = 0.0

    wide[["local_production", "import_volumes"]] = wide[
        ["local_production", "import_volumes"]
    ].fillna(0.0)

    wide["total_demand"] = wide["local_production"] + wide["import_volumes"]

    return wide.sort_values(["country", "year"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------


def _last_base(hist: pd.DataFrame) -> pd.DataFrame:
    """Return the last historical row per country (base for projections)."""
    return hist.loc[hist.groupby("country")["year"].idxmax()].set_index("country")


def build_scenario(
    hist: pd.DataFrame,
    scenario_name: str,
    projection_years: List[int] = PROJECTION_YEARS,
) -> pd.DataFrame:
    """
    Build a combined historical + projected DataFrame for one scenario.

    Parameters
    ----------
    hist:
        Wide-format historical DataFrame from :func:`load_undata`.
    scenario_name:
        One of ``"mid_speed"``, ``"fast_track"``, ``"slow_mover"``.
    projection_years:
        Future years to project (5-year steps by default).
    cagr_rate:
        Annual compound growth rate (fraction).

    Returns
    -------
    DataFrame with columns:
        path | country | year | local_production | import_volumes | total_demand |
        local_green_transformation_share | import_green_reallocation_share | CAGR_rate | CAGR_factor |
        exog_ammonia_conv_path | endog_ammonia_green_path
    """
    if scenario_name not in _SCENARIOS:
        raise ValueError(
            f"Unknown scenario '{scenario_name}'. "
            f"Choose from: {_SCENARIOS}"
        )

    rates = CAGR_RATES[scenario_name]  # Dict[int, float] — one rate per projection year

    # --- Historical rows (no transformation) --------------------------------
    hist_out = hist.copy()
    hist_out["path"] = scenario_name
    hist_out["local_green_transformation_share"] = 0.0  # Renamed from GALT
    hist_out["import_green_reallocation_share"] = 0.0   # Renamed from GAIR
    hist_out["CAGR_rate"] = 0.0
    hist_out["CAGR_factor"] = 1.0
    hist_out["exog_ammonia_conv_path"] = hist_out["local_production"]
    hist_out["exog_ammonia_conv_path_MWh_nh3"] = hist_out["local_production"] * AMMONIA_MWH_PER_TON
    hist_out["endog_ammonia_green_path"] = 0.0
    hist_out["endog_ammonia_green_path_MWh_nh3"] = 0.0

    # --- Projected rows  ---------------------------------------------------
    local_green_shares = _interpolate_indicator(GALT_ANCHORS[scenario_name], projection_years)
    import_green_shares = _interpolate_indicator(GAIR_ANCHORS[scenario_name], projection_years)

    base = _last_base(hist)  # index = country

    proj_rows = []
    for yr, local_green_share, import_green_share in zip(projection_years, local_green_shares, import_green_shares):
        yr = int(yr)
        local_green_share = float(local_green_share)
        import_green_share = float(import_green_share)

        for country, base_row in base.iterrows():
            base_year = int(base_row["year"])
            base_local = float(base_row["local_production"])
            base_import = float(base_row["import_volumes"])

            cagr_factor = _compute_cagr_factor(rates, base_year, yr, projection_years)
            interval_rate = rates[yr]  # rate applied in the interval ending at yr

            proj_local = base_local * cagr_factor
            proj_import = base_import * cagr_factor

            exog = proj_local * (1.0 - local_green_share)
            endog = proj_import * import_green_share + proj_local * local_green_share

            proj_rows.append(
                {
                    "path": scenario_name,
                    "country": country,
                    "year": yr,
                    "local_production": round(proj_local, 4),
                    "import_volumes": round(proj_import, 4),
                    "total_demand": round(proj_local + proj_import, 4),
                    "local_green_transformation_share": round(local_green_share, 4),      # Renamed from GALT
                    "import_green_reallocation_share": round(import_green_share, 4),       # Renamed from GAIR
                    "CAGR_rate": interval_rate,
                    "CAGR_factor": round(cagr_factor, 6),
                    "exog_ammonia_conv_path": round(exog, 4),
                    "exog_ammonia_conv_path_MWh_nh3": round(exog * AMMONIA_MWH_PER_TON, 4),
                    "endog_ammonia_green_path": round(endog, 4),
                    "endog_ammonia_green_path_MWh_nh3": round(endog * AMMONIA_MWH_PER_TON, 4),
                }
            )

    proj_df = pd.DataFrame(proj_rows)

    # Tag historical rows with the same extra columns for consistency
    hist_out["CAGR_rate"] = 0.0
    # Already set above, add missing cols at correct dtype
    hist_out["CAGR_factor"] = 1.0

    combined = (
        pd.concat([hist_out, proj_df], ignore_index=True)
        .sort_values(["country", "year"])
        .reset_index(drop=True)
    )

    # Enforce column order
    col_order = [
        "path",
        "country",
        "year",
        "local_production",
        "import_volumes",
        "total_demand",
        "local_green_transformation_share",  # Renamed from GALT
        "import_green_reallocation_share",   # Renamed from GAIR
        "CAGR_rate",
        "CAGR_factor",
        "exog_ammonia_conv_path",
        "exog_ammonia_conv_path_MWh_nh3",
        "endog_ammonia_green_path",
        "endog_ammonia_green_path_MWh_nh3",
    ]
    return combined[col_order]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def build_all_scenarios(
    undata_path: Path = UNDATA_CSV,
    output_dir: Path = OUTPUT_DIR,
    projection_years: List[int] = PROJECTION_YEARS,
) -> pd.DataFrame:
    """
    Load historical data, build all scenarios, and write a single combined CSV.

    The CSV contains a ``path`` column so callers can filter by volume
    scenario name directly, or use ``SCENARIO_MAPPING`` to translate pipeline
    scenario labels (BAU / Progressive / Optimistic) first.

    Returns the combined DataFrame.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    hist = load_undata(undata_path)
    print(f"Loaded {len(hist):,} historical rows for {hist['country'].nunique()} countries.")
    print(f"Year range: {hist['year'].min()} – {hist['year'].max()}")

    frames = []
    for scenario in _SCENARIOS:
        df = build_scenario(hist, scenario, projection_years)
        frames.append(df)
        print(f"  [{scenario}] built — {len(df):,} rows")

    combined = pd.concat(frames, ignore_index=True)
    
    out_path = output_dir / "ammonia_volumes.csv"
    combined.to_csv(out_path, index=False)
    print(f"\nWritten → {out_path}  ({len(combined):,} rows total)")
    return combined


if __name__ == "__main__":
    build_all_scenarios()
