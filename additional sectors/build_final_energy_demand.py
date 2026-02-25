from pathlib import Path

import pandas as pd


DEFAULT_SECTOR_LABELS = [
    "Agriculture  forestry and fishing",
    "Commerce and public services",
    "Non-energy use",
    "Other Consumption",
]

from build_shares import (
    _clean_val,
    _default_share_dict,
    _discover_countries,
    _discover_country_years,
    _get_candidate_dirs,
    _sector_slug,
    get_sector_shares,
)


def _load_average_shares_from_csv(shares_csv_path: Path):
    if not shares_csv_path.exists():
        raise FileNotFoundError(
            f"Shares CSV not found: {shares_csv_path}. Run build_shares.py first."
        )

    shares_df = pd.read_csv(shares_csv_path)
    required_columns = ["country", "share_mode", *_default_share_dict().keys()]
    missing_columns = [column for column in required_columns if column not in shares_df.columns]
    if missing_columns:
        raise ValueError(f"Shares CSV is missing required columns: {missing_columns}")

    average_rows = shares_df[shares_df["share_mode"].astype(str).str.lower() == "historical_average"]
    if average_rows.empty:
        raise ValueError("No 'historical_average' rows found in shares CSV.")

    fuels = list(_default_share_dict().keys())
    country_to_shares = {}
    for _, row in average_rows.iterrows():
        country_to_shares[row["country"]] = {
            fuel: float(row[fuel]) if pd.notna(row[fuel]) else 0.0
            for fuel in fuels
        }

    return country_to_shares


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
    row = df[df[sector_col].str.strip().str.lower() == sector_label.lower()]

    if row.empty:
        return 0.0

    total_tj = _clean_val(row["Total Energy"].iloc[0])
    return round(total_tj * 0.000277778, 6)


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
        "other consumption": "ohter",
    }
    return mapping.get(normalized, normalized)


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
    cagr: float = 0.03,
    future_years: list = None,
    shares_csv_path: Path = None,
):
    if future_years is None:
        future_years = [2030, 2035, 2040, 2045, 2050]

    sector_slug = _sector_slug(sector_label)
    if shares_csv_path is None:
        shares_csv_path = Path(output_dir) / f"{sector_slug}_shares_all_countries.csv"

    output_csv_path = Path(output_dir) / f"{sector_slug}_fuel_demand_history_future.csv"

    countries = _discover_countries(base_path=base_path)
    fuels = list(_default_share_dict().keys())
    average_shares_by_country = _load_average_shares_from_csv(shares_csv_path=shares_csv_path)

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

        for future_year in future_years:
            if future_year <= base_year_for_projection:
                continue

            year_delta = future_year - base_year_for_projection
            projected_total_twh = round(
                base_year_total_twh * ((1 + cagr) ** year_delta),
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
    sector_labels: list,
    base_year_for_projection: int,
    cagr: float = 0.03,
    future_years: list = None,
):
    output_files = []
    for sector_label in sector_labels:
        output_files.append(
            build_sector_fuel_demand_history_and_future(
                base_path=base_path,
                output_dir=output_dir,
                sector_label=sector_label,
                base_year_for_projection=base_year_for_projection,
                cagr=cagr,
                future_years=future_years,
            )
        )
    return output_files


if __name__ == "__main__":
    base_path = Path(__file__).resolve().parents[1] / "data" / "country_specific"
    output_dir = Path(__file__).resolve().parent / "output_data"

    demand_files = build_fuel_demand_for_multiple_sectors(
        base_path=base_path,
        output_dir=output_dir,
        sector_labels=DEFAULT_SECTOR_LABELS,
        base_year_for_projection=2023,
        cagr=0.03,
    )
    for demand_file in demand_files:
        print(f"Saved final demand CSV to: {demand_file}")
