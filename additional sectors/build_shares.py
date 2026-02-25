import re
from pathlib import Path

import pandas as pd


DEFAULT_SECTOR_LABELS = [
    "Agriculture  forestry and fishing",
    "Commerce and public services",
    "Non-energy use",
    "Other consumption n.e.s",
]

BASE_PERIODS = [
    (2011, 2016),
    (2017, 2023),
]


def _clean_val(val):
    if pd.isna(val):
        return 0.0
    s_val = str(val).strip()
    if s_val in ["---", "", "None", "-"]:
        return 0.0
    try:
        clean_s = s_val.replace("*", "").replace("-", "")
        return float(clean_s) if clean_s else 0.0
    except ValueError:
        return 0.0


def _default_share_dict():
    return {
        "oil": 0.0,
        "gas": 0.0,
        "electricity": 0.0,
        "coal": 0.0,
        "biomass": 0.0,
        "ammonia": 0.0,
    }


def _default_fuel_mapping():
    return {
        "oil": ["Primary Oil", "Oil Products"],
        "gas": ["Natural Gas"],
        "electricity": ["Nuclear", "Electricity"],
        "coal": ["Primary Coal and Peat", "Coal and Peat Products"],
        "biomass": ["Biofuels and Waste"],
        "ammonia": [],
    }


def _validate_share_sum(shares: dict, tolerance: float = 1e-3):
    share_sum = round(sum(shares.values()), 6)
    is_valid = share_sum > 0 and abs(share_sum - 1.0) <= tolerance
    return share_sum, is_valid


def _normalize_shares(shares: dict, decimals: int = 4):
    total = sum(shares.values())
    if total <= 0:
        return _default_share_dict()
    return {
        fuel: round(value / total, decimals)
        for fuel, value in shares.items()
    }


def _sector_slug(sector_label: str):
    slug = re.sub(r"[^a-z0-9]+", "_", sector_label.lower()).strip("_")
    return slug if slug else "sector"


def _sector_column_prefix(sector_label: str):
    normalized = " ".join(str(sector_label).lower().split())
    mapping = {
        "agriculture forestry and fishing": "agriculture",
        "commerce and public services": "services",
        "non-energy use": "non energy",
        "other consumption": "ohter",
    }
    return mapping.get(normalized, normalized)


def _sector_output_file_prefix(sector_label: str):
    return _sector_column_prefix(sector_label).replace(" ", "_")


def _get_candidate_dirs(base_path: Path):
    return [
        Path(base_path),
        Path(__file__).resolve().parents[1] / "data" / "country_specific",
    ]


def _discover_country_years(base_path: Path, country: str):
    years = set()
    prefix = f"UNSD_{country}-"
    suffix = ".csv"

    for directory in _get_candidate_dirs(base_path):
        if not directory.exists():
            continue
        for file_path in directory.glob(f"{prefix}*{suffix}"):
            name = file_path.name
            year_text = name[len(prefix) : -len(suffix)]
            if year_text.isdigit():
                years.add(int(year_text))

    return sorted(years)


def _discover_countries(base_path: Path):
    countries = set()
    prefix = "UNSD_"
    suffix = ".csv"

    for directory in _get_candidate_dirs(base_path):
        if not directory.exists():
            continue
        for file_path in directory.glob(f"{prefix}*{suffix}"):
            name = file_path.name
            if not name.startswith(prefix) or not name.endswith(suffix):
                continue
            country_and_year = name[len(prefix) : -len(suffix)]
            if "-" not in country_and_year:
                continue
            country, year_text = country_and_year.rsplit("-", 1)
            if country and year_text.isdigit():
                countries.add(country)

    return sorted(countries)


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
    row = df[df[sector_col].str.strip().str.lower() == sector_label.lower()]

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


def _get_sector_totals_by_fuel(
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
        return 0.0, _default_share_dict()

    df = pd.read_csv(file_path)
    sector_col = "Transactions(down)/Commodity(right)"
    row = df[df[sector_col].str.strip().str.lower() == sector_label.lower()]

    if row.empty:
        return 0.0, _default_share_dict()

    total_tj = _clean_val(row["Total Energy"].iloc[0])
    if total_tj <= 0:
        return 0.0, _default_share_dict()

    fuel_totals = {}
    for category, headers in fuel_mapping.items():
        fuel_totals[category] = sum([_clean_val(row[h].iloc[0]) for h in headers if h in df.columns])

    return total_tj, fuel_totals


def get_sector_shares_historical_average(
    base_path: Path,
    country: str,
    sector_label: str,
    years: list = None,
    fuel_mapping: dict = None,
):
    if years is None:
        years = _discover_country_years(base_path=base_path, country=country)

    if not years:
        return _default_share_dict()

    aggregate_total_tj = 0.0
    aggregate_fuel_totals = _default_share_dict()

    for historical_year in years:
        year_total_tj, year_fuel_totals = _get_sector_totals_by_fuel(
            base_path=base_path,
            country=country,
            year=historical_year,
            sector_label=sector_label,
            fuel_mapping=fuel_mapping,
        )
        if year_total_tj <= 0:
            continue

        aggregate_total_tj += year_total_tj
        for fuel in aggregate_fuel_totals.keys():
            aggregate_fuel_totals[fuel] += year_fuel_totals.get(fuel, 0.0)

    if aggregate_total_tj <= 0:
        return _default_share_dict()

    return _normalize_shares(aggregate_fuel_totals, decimals=4)


def export_sector_shares_all_countries(
    base_path: Path,
    output_dir: Path,
    sector_label: str,
    year: int = None,
    fuel_mapping: dict = None,
):
    countries = _discover_countries(base_path=base_path)
    output_prefix = _sector_output_file_prefix(sector_label)
    output_csv_path = Path(output_dir) / f"{output_prefix}_shares_all_countries.csv"

    if not countries:
        output_csv_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=["sector", "country", "share_mode", "share_sum", "share_sum_is_valid", *_default_share_dict().keys()]).to_csv(
            output_csv_path, index=False
        )
        return output_csv_path

    rows = []
    for country in countries:
        if year is None:
            all_years = _discover_country_years(base_path=base_path, country=country)
            shares = get_sector_shares_historical_average(
                base_path=base_path,
                country=country,
                sector_label=sector_label,
                years=all_years,
                fuel_mapping=fuel_mapping,
            )
            share_sum, share_sum_is_valid = _validate_share_sum(shares)
            row = {
                "sector": sector_label,
                "country": country,
                "share_mode": "historical_average",
                "share_sum": share_sum,
                "share_sum_is_valid": share_sum_is_valid,
                **shares,
            }
            rows.append(row)

            for start_year, end_year in BASE_PERIODS:
                period_years = [historical_year for historical_year in all_years if start_year <= historical_year <= end_year]
                if not period_years:
                    continue

                period_shares = get_sector_shares_historical_average(
                    base_path=base_path,
                    country=country,
                    sector_label=sector_label,
                    years=period_years,
                    fuel_mapping=fuel_mapping,
                )
                period_share_sum, period_share_sum_is_valid = _validate_share_sum(period_shares)
                period_row = {
                    "sector": sector_label,
                    "country": country,
                    "share_mode": f"base_period_{start_year}_{end_year}",
                    "share_sum": period_share_sum,
                    "share_sum_is_valid": period_share_sum_is_valid,
                    **period_shares,
                }
                rows.append(period_row)
        else:
            shares = get_sector_shares(
                base_path=base_path,
                country=country,
                year=year,
                sector_label=sector_label,
                fuel_mapping=fuel_mapping,
            )
            share_sum, share_sum_is_valid = _validate_share_sum(shares)
            row = {
                "sector": sector_label,
                "country": country,
                "share_mode": "single_year",
                "share_sum": share_sum,
                "share_sum_is_valid": share_sum_is_valid,
                **shares,
            }
            rows.append(row)

    output_df = pd.DataFrame(rows)
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    output_df.to_csv(output_csv_path, index=False)
    return output_csv_path


def export_shares_for_multiple_sectors(
    base_path: Path,
    output_dir: Path,
    sector_labels: list,
    year: int = None,
    fuel_mapping: dict = None,
):
    output_files = []
    for sector_label in sector_labels:
        output_files.append(
            export_sector_shares_all_countries(
                base_path=base_path,
                output_dir=output_dir,
                sector_label=sector_label,
                year=year,
                fuel_mapping=fuel_mapping,
            )
        )
    return output_files


if __name__ == "__main__":
    base_path = Path(__file__).resolve().parents[1] / "data" / "country_specific"
    output_dir = Path(__file__).resolve().parent / "output_data"

    shares_files = export_shares_for_multiple_sectors(
        base_path=base_path,
        output_dir=output_dir,
        sector_labels=DEFAULT_SECTOR_LABELS,
        year=None,
    )
    for shares_file in shares_files:
        print(f"Saved shares CSV to: {shares_file}")
