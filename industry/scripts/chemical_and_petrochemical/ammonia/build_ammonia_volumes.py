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
    GALT | GAIR | CAGR_rate | CAGR_factor |
    exog_ammonia_conv_path | endog_ammonia_green_path

The ``path`` column contains the volume-scenario name (``mid_speed``,
``fast_track``, ``slow_mover``).  Use ``SCENARIO_MAPPING`` to translate the
pipeline scenario names (``BAU``, ``Progressive``, ``Optimistic``) to the
corresponding volume path before filtering.

Historical rows (up to last available year) contain actual measured values;
GALT/GAIR/CAGR for those rows are set to 0/0/0 (no transformation applied).
Projected rows cover 2025–2050 in 5-year steps, starting from the last
available base value of each country.

Transformation indicators (defaults, easily overridden per country/year)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
GALT – Green Ammonia Local Transformation  (share of local production going
       through a green synthesis route)
GAIR – Green Ammonia Import Reallocation   (share of imports sourced from
       green / renewable-ammonia supply chains)
CAGR_rate – compound annual growth rate applied to production/imports.
             Stored as a fraction (e.g. 0.07 = 7 %).
CAGR_factor – cumulative growth multiplier = (1 + CAGR_rate)^(year − base_year)

Projected demand formulas
~~~~~~~~~~~~~~~~~~~~~~~~~
    exog_ammonia_conv_path  = base_local  × CAGR_factor × (1 − GALT)
    endog_ammonia_green_path = base_import × CAGR_factor × GAIR
                              + base_local × CAGR_factor × GALT
where base_local / base_import are the values at the country's last available
historical year.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).resolve()
_INDUSTRY_ROOT = _SCRIPT_DIR.parents[3]

UNDATA_CSV = (
    _INDUSTRY_ROOT
    / "input_data"
    / "petrochemicals"
    / "UNdata_Export_20250709_101100979.csv"
)

OUTPUT_DIR = Path(__file__).resolve().parent

# Projected years (5-year steps)
PROJECTION_YEARS: List[int] = [2025, 2030, 2035, 2040, 2045, 2050]

# Default CAGR annual rate (fraction) – same for all scenarios
DEFAULT_CAGR_RATE: float = 0.07

# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------
# GALT and GAIR are defined in separate public dicts so users can tweak each
# indicator independently without touching the other.
#
# Each dict maps:  scenario_name  →  {anchor_year: value}
# Values for years between anchors are linearly interpolated.
# Values beyond the last anchor are held flat (np.interp behaviour).
#
# GALT – Green Ammonia Local Transformation
#         share of local production routed through a green synthesis path
# GAIR – Green Ammonia Import Reallocation
#         share of imports sourced from green / renewable-ammonia supply chains

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
    cagr_rate: float = DEFAULT_CAGR_RATE,
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
        GALT | GAIR | CAGR_rate | CAGR_factor |
        exog_ammonia_conv_path | endog_ammonia_green_path
    """
    if scenario_name not in _SCENARIOS:
        raise ValueError(
            f"Unknown scenario '{scenario_name}'. "
            f"Choose from: {_SCENARIOS}"
        )

    # --- Historical rows (no transformation) --------------------------------
    hist_out = hist.copy()
    hist_out["path"] = scenario_name
    hist_out["GALT"] = 0.0
    hist_out["GAIR"] = 0.0
    hist_out["CAGR_rate"] = 0.0
    hist_out["CAGR_factor"] = 1.0
    hist_out["exog_ammonia_conv_path"] = hist_out["local_production"]
    hist_out["endog_ammonia_green_path"] = 0.0

    # --- Projected rows  ---------------------------------------------------
    galt_values = _interpolate_indicator(GALT_ANCHORS[scenario_name], projection_years)
    gair_values = _interpolate_indicator(GAIR_ANCHORS[scenario_name], projection_years)

    base = _last_base(hist)  # index = country

    proj_rows = []
    for yr, galt, gair in zip(projection_years, galt_values, gair_values):
        yr = int(yr)
        galt = float(galt)
        gair = float(gair)

        for country, base_row in base.iterrows():
            base_year = int(base_row["year"])
            base_local = float(base_row["local_production"])
            base_import = float(base_row["import_volumes"])

            cagr_factor = (1.0 + cagr_rate) ** (yr - base_year)

            proj_local = base_local * cagr_factor
            proj_import = base_import * cagr_factor

            exog = proj_local * (1.0 - galt)
            endog = proj_import * gair + proj_local * galt

            proj_rows.append(
                {
                    "path": scenario_name,
                    "country": country,
                    "year": yr,
                    "local_production": round(proj_local, 4),
                    "import_volumes": round(proj_import, 4),
                    "total_demand": round(proj_local + proj_import, 4),
                    "GALT": round(galt, 4),
                    "GAIR": round(gair, 4),
                    "CAGR_rate": cagr_rate,
                    "CAGR_factor": round(cagr_factor, 6),
                    "exog_ammonia_conv_path": round(exog, 4),
                    "endog_ammonia_green_path": round(endog, 4),
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
        "GALT",
        "GAIR",
        "CAGR_rate",
        "CAGR_factor",
        "exog_ammonia_conv_path",
        "endog_ammonia_green_path",
    ]
    return combined[col_order]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def build_all_scenarios(
    undata_path: Path = UNDATA_CSV,
    output_dir: Path = OUTPUT_DIR,
    projection_years: List[int] = PROJECTION_YEARS,
    cagr_rate: float = DEFAULT_CAGR_RATE,
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
        df = build_scenario(hist, scenario, projection_years, cagr_rate)
        frames.append(df)
        print(f"  [{scenario}] built — {len(df):,} rows")

    combined = pd.concat(frames, ignore_index=True)
    out_path = output_dir / "ammonia_volumes.csv"
    combined.to_csv(out_path, index=False)
    print(f"\nWritten → {out_path}  ({len(combined):,} rows total)")
    return combined


if __name__ == "__main__":
    build_all_scenarios()
