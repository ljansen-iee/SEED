from pathlib import Path
from importlib import util

import pandas as pd

SECTORS_TO_BUILD = [
    "Agriculture  forestry and fishing",
    "Commerce and public services",
    "Non-energy use",
    "Other consumption n.e.s",
]

_CORE_SHARES_PATH = Path(__file__).resolve().parents[1] / "build_shares.py"
_CORE_SHARES_SPEC = util.spec_from_file_location("_core_build_shares", _CORE_SHARES_PATH)
_CORE_SHARES = util.module_from_spec(_CORE_SHARES_SPEC)
_CORE_SHARES_SPEC.loader.exec_module(_CORE_SHARES)

_clean_val = _CORE_SHARES._clean_val
_default_fuel_mapping = _CORE_SHARES._default_fuel_mapping
_default_share_dict = _CORE_SHARES._default_share_dict
_discover_countries = _CORE_SHARES._discover_countries
_discover_country_years = _CORE_SHARES._discover_country_years
_get_candidate_dirs = _CORE_SHARES._get_candidate_dirs


def _load_average_shares_from_csv(shares_csv_path: Path, share_mode: str):
    if not shares_csv_path.exists():
        raise FileNotFoundError(
            f"Shares CSV not found: {shares_csv_path}. Run build_shares.py first."
        )

    shares_df = pd.read_csv(shares_csv_path)
    required_columns = ["country", "share_mode", *_default_share_dict().keys()]
    missing_columns = [column for column in required_columns if column not in shares_df.columns]
    if missing_columns:
        raise ValueError(f"Shares CSV is missing required columns: {missing_columns}")

    average_rows = shares_df[
        shares_df["share_mode"].astype(str).str.lower() == str(share_mode).strip().lower()
    ]
    if average_rows.empty:
        raise ValueError(f"No '{share_mode}' rows found in shares CSV.")

    fuels = list(_default_share_dict().keys())
    country_to_shares = {}
    for _, row in average_rows.iterrows():
        country_to_shares[row["country"]] = {
            fuel: float(row[fuel]) if pd.notna(row[fuel]) else 0.0
            for fuel in fuels
        }

    return country_to_shares


def _normalize_sector_label(sector_label: str):
    return " ".join(str(sector_label).strip().lower().split())


def _find_sector_row(df: pd.DataFrame, sector_col: str, sector_label: str):
    normalized_sector = _normalize_sector_label(sector_label)
    return df[df[sector_col].astype(str).apply(_normalize_sector_label) == normalized_sector]


def _load_suggested_cagr_from_csv(cagr_csv_path: Path, sector_label: str):
    if not cagr_csv_path.exists():
        raise FileNotFoundError(
            f"CAGR CSV not found: {cagr_csv_path}. Run build_CAGR.py first."
        )

    cagr_df = pd.read_csv(cagr_csv_path)
    required_columns = ["country", "sector", "suggested_cagr"]
    missing_columns = [column for column in required_columns if column not in cagr_df.columns]
    if missing_columns:
        raise ValueError(f"CAGR CSV is missing required columns: {missing_columns}")

    normalized_sector = _normalize_sector_label(sector_label)
    sector_rows = cagr_df[
        cagr_df["sector"].astype(str).apply(_normalize_sector_label) == normalized_sector
    ].copy()

    if sector_rows.empty:
        raise ValueError(f"No rows found in CAGR CSV for sector: {sector_label}")

    sector_rows["suggested_cagr"] = pd.to_numeric(sector_rows["suggested_cagr"], errors="coerce")
    sector_rows = sector_rows.dropna(subset=["suggested_cagr"])
    if sector_rows.empty:
        raise ValueError(f"No valid suggested_cagr values found for sector: {sector_label}")

    return sector_rows.groupby("country", as_index=True)["suggested_cagr"].mean().to_dict()


def get_sector_total_TWh(
    base_path: Path,
    country: str,
    year: int,
    sector_label: str,
):
    filename = f"UNSD_{country}-{year}.csv"
    candidates = [directory / filename for directory in _get_candidate_dirs(base_path)]
    file_path = next((candidate for candidate in candidates if candidate.exists()), candidates[0])

    if not file_path.exists():
        return 0.0

    df = pd.read_csv(file_path)
    sector_col = "Transactions(down)/Commodity(right)"
    row = _find_sector_row(df=df, sector_col=sector_col, sector_label=sector_label)

    if row.empty:
        return 0.0

    total_tj = _clean_val(row["Total Energy"].iloc[0])
    return round(total_tj * 0.000277778, 6)


def get_sector_shares(
    base_path: Path,
    country: str,
    year: int,
    sector_label: str,
    fuel_mapping: dict = None,
):
    filename = f"UNSD_{country}-{year}.csv"
    candidates = [directory / filename for directory in _get_candidate_dirs(base_path)]
    file_path = next((candidate for candidate in candidates if candidate.exists()), candidates[0])

    if fuel_mapping is None:
        fuel_mapping = _default_fuel_mapping()

    if not file_path.exists():
        return _default_share_dict()

    df = pd.read_csv(file_path)
    sector_col = "Transactions(down)/Commodity(right)"
    row = _find_sector_row(df=df, sector_col=sector_col, sector_label=sector_label)

    if row.empty:
        return _default_share_dict()

    total_tj = _clean_val(row["Total Energy"].iloc[0])
    if total_tj == 0:
        return _default_share_dict()

    shares = {}
    for category, headers in fuel_mapping.items():
        category_sum = sum([_clean_val(row[h].iloc[0]) for h in headers if h in df.columns])
        shares[category] = round(category_sum / total_tj, 6)

    return shares


def _fuel_demand_from_total(total_energy_twh: float, shares: dict):
    return {
        fuel: round(total_energy_twh * share, 6)
        for fuel, share in shares.items()
    }


def _sector_column_prefix(sector_label: str):
    normalized = " ".join(str(sector_label).lower().split())
    mapping = {
        "agriculture forestry and fishing": "agriculture",
        "commerce and public services": "services",
        "non-energy use": "non energy",
        "other consumption n.e.s": "other",
        "households":"residential",

    }
    return mapping.get(normalized, normalized)


def _sector_output_file_prefix(sector_label: str):
    return _sector_column_prefix(sector_label).replace(" ", "_")


def _rename_fuel_columns(fuel_demand: dict, sector_label: str):
    prefix = _sector_column_prefix(sector_label)
    return {
        f"{prefix} {fuel}": value
        for fuel, value in fuel_demand.items()
    }


def build_sector_fuel_demand_history_and_future(
    base_path: Path,
    output_dir: Path,
    sector_label: str,
    base_year_for_projection: int,
    future_years: list = None,
    shares_csv_path: Path = None,
    cagr_csv_path: Path = None,
    projection_share_mode: str = "base_period_2017_2023",
):
    if future_years is None:
        future_years = [2030, 2035, 2040, 2045, 2050]

    output_prefix = _sector_output_file_prefix(sector_label)
    if shares_csv_path is None:
        shares_csv_path = Path(__file__).resolve().parents[1] / "output_data" / "interim" / "shares" / f"{output_prefix}_shares_all_countries.csv"
    if cagr_csv_path is None:
        cagr_csv_path = Path(__file__).resolve().parents[1] / "output_data" / "interim" / "cagr" / f"{output_prefix}_cagr_all_countries.csv"

    output_csv_path = Path(output_dir) / f"{output_prefix}_fuel_demand_history_future.csv"

    countries = _discover_countries(base_path=base_path)
    fuels = list(_default_share_dict().keys())
    average_shares_by_country = _load_average_shares_from_csv(
        shares_csv_path=shares_csv_path,
        share_mode=projection_share_mode,
    )
    suggested_cagr_by_country = _load_suggested_cagr_from_csv(
        cagr_csv_path=cagr_csv_path,
        sector_label=sector_label,
    )

    rows = []
    for country in countries:
        historical_years = _discover_country_years(base_path=base_path, country=country)

        for historical_year in historical_years:
            total_twh = get_sector_total_TWh(
                base_path=base_path,
                country=country,
                year=historical_year,
                sector_label=sector_label,
            )
            if total_twh <= 0:
                continue

            historical_shares = get_sector_shares(
                base_path=base_path,
                country=country,
                year=historical_year,
                sector_label=sector_label,
            )
            historical_fuel_demand = _fuel_demand_from_total(
                total_energy_twh=total_twh,
                shares=historical_shares,
            )
            historical_fuel_demand = _rename_fuel_columns(
                fuel_demand=historical_fuel_demand,
                sector_label=sector_label,
            )

            rows.append(
                {
                    "country": country,
                    "year": historical_year,
                    "unit": "TWh",
                    **historical_fuel_demand,
                }
            )

        base_year_total_twh = get_sector_total_TWh(
            base_path=base_path,
            country=country,
            year=base_year_for_projection,
            sector_label=sector_label,
        )
        if base_year_total_twh <= 0:
            continue

        average_shares = average_shares_by_country.get(country)
        if average_shares is None:
            continue

        country_cagr = suggested_cagr_by_country.get(country)
        if pd.isna(country_cagr):
            continue

        for future_year in future_years:
            if future_year <= base_year_for_projection:
                continue

            year_delta = future_year - base_year_for_projection
            projected_total_twh = round(
                base_year_total_twh * ((1 + country_cagr) ** year_delta),
                6,
            )
            projected_fuel_demand = _fuel_demand_from_total(
                total_energy_twh=projected_total_twh,
                shares=average_shares,
            )
            projected_fuel_demand = _rename_fuel_columns(
                fuel_demand=projected_fuel_demand,
                sector_label=sector_label,
            )

            rows.append(
                {
                    "country": country,
                    "year": future_year,
                    "unit": "TWh",
                    **projected_fuel_demand,
                }
            )

    output_csv_path.parent.mkdir(parents=True, exist_ok=True)

    column_prefix = _sector_column_prefix(sector_label)
    output_columns = ["country", "year", "unit", *[f"{column_prefix} {fuel}" for fuel in fuels]]
    output_df = pd.DataFrame(rows)
    if output_df.empty:
        output_df = pd.DataFrame(columns=output_columns)
    else:
        output_df = output_df[output_columns].sort_values(by=["country", "year"]).reset_index(drop=True)

    output_df.to_csv(output_csv_path, index=False)
    return output_csv_path


def build_fuel_demand_for_multiple_sectors(
    base_path: Path,
    output_dir: Path,
    base_year_for_projection: int,
    future_years: list = None,
    cagr_csv_path: Path = None,
    projection_share_mode: str = "base_period_2017_2023",
):
    output_files = []
    for sector_label in SECTORS_TO_BUILD:
        output_files.append(
            build_sector_fuel_demand_history_and_future(
                base_path=base_path,
                output_dir=output_dir,
                sector_label=sector_label,
                base_year_for_projection=base_year_for_projection,
                future_years=future_years,
                cagr_csv_path=cagr_csv_path,
                projection_share_mode=projection_share_mode,
            )
        )
    return output_files


if __name__ == "__main__":
    base_path = Path(__file__).resolve().parents[1] / "data" / "unsdata_historical"
    output_dir = Path(__file__).resolve().parent / "output_data"

    demand_files = build_fuel_demand_for_multiple_sectors(
        base_path=base_path,
        output_dir=output_dir,
        base_year_for_projection=2023,
        projection_share_mode="base_period_2017_2023",
        # historical_average
        # base_period_2011_2016
        # base_period_2017_2023
    )
    for demand_file in demand_files:
        print(f"Saved final demand CSV to: {demand_file}")
