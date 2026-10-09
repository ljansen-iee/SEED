"""Shared UNSD fuel-share preprocessing, restored from main.

``--years`` restricts source years (not projection years). Explicit input
directories never fall back to another worktree's data.
"""
import argparse
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
DEFAULT_SECTOR_LABELS = [
    "Agriculture  forestry and fishing", "Commerce and public services",
    "Non-energy use", "Other consumption n.e.s", "Households",
]
BASE_PERIODS = [(2011, 2016), (2017, 2023)]


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
    return dict.fromkeys(["oil", "gas", "electricity", "coal", "biomass", "ammonia"], 0.0)


def _default_fuel_mapping():
    return {
        "oil": ["Primary Oil", "Oil Products"], "gas": ["Natural Gas"],
        "electricity": ["Nuclear", "Electricity"],
        "coal": ["Primary Coal and Peat", "Coal and Peat Products"],
        "biomass": ["Biofuels and Waste"], "ammonia": [],
    }


def _validate_share_sum(shares, tolerance=1e-3):
    share_sum = round(sum(shares.values()), 6)
    return share_sum, share_sum > 0 and abs(share_sum - 1.0) <= tolerance


def _normalize_shares(shares, decimals=4):
    total = sum(shares.values())
    if total <= 0:
        return _default_share_dict()
    return {fuel: round(value / total, decimals) for fuel, value in shares.items()}


def _normalize_text(value):
    return " ".join(str(value).strip().lower().split())


def _sector_slug(sector_label):
    return re.sub(r"[^a-z0-9]+", "_", sector_label.lower()).strip("_") or "sector"


def _sector_column_prefix(sector_label):
    normalized = _normalize_text(sector_label)
    return {
        "agriculture forestry and fishing": "agriculture",
        "commerce and public services": "services", "non-energy use": "non energy",
        "other consumption n.e.s": "other",
    }.get(normalized, normalized)


def _sector_output_file_prefix(sector_label):
    return _sector_column_prefix(sector_label).replace(" ", "_")


def _get_candidate_dirs(base_path):
    return [Path(base_path)]


def _discover_country_years(base_path, country):
    prefix = f"UNSD_{country}-"
    years = set()
    for directory in _get_candidate_dirs(base_path):
        for file_path in directory.glob(f"{prefix}*.csv"):
            year = file_path.name[len(prefix):-4]
            if year.isdigit():
                years.add(int(year))
    return sorted(years)


def _discover_countries(base_path):
    countries = set()
    for directory in _get_candidate_dirs(base_path):
        for file_path in directory.glob("UNSD_*.csv"):
            country, separator, year = file_path.stem[5:].rpartition("-")
            if country and separator and year.isdigit():
                countries.add(country)
    return sorted(countries)


def _select_countries(base_path, countries=None):
    available = _discover_countries(base_path)
    selected = available if countries is None else sorted(set(countries))
    missing = sorted(set(selected) - set(available))
    if missing or not selected:
        raise FileNotFoundError(f"No UNSD source files in {base_path} for: {missing or selected}")
    return selected


def _select_years(base_path, country, years=None):
    available = _discover_country_years(base_path, country)
    selected = available if years is None else sorted(set(map(int, years)))
    missing = sorted(set(selected) - set(available))
    if missing:
        raise FileNotFoundError(f"Missing UNSD source years for {country} in {base_path}: {missing}")
    return selected


def _read_unsd(base_path, country, year):
    path = Path(base_path) / f"UNSD_{country}-{year}.csv"
    df = pd.read_csv(path)
    required = {"Transactions(down)/Commodity(right)", "Total Energy"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"{path} is missing columns: {sorted(missing)}")
    return df


def _get_sector_totals_by_fuel(base_path, country, year, sector_label, fuel_mapping=None):
    df = _read_unsd(base_path, country, year)
    sector_col = "Transactions(down)/Commodity(right)"
    row = df[df[sector_col].map(_normalize_text) == _normalize_text(sector_label)]
    if row.empty:
        return 0.0, _default_share_dict()
    total_tj = _clean_val(row["Total Energy"].iloc[0])
    if total_tj <= 0:
        return 0.0, _default_share_dict()
    mapping = _default_fuel_mapping() if fuel_mapping is None else fuel_mapping
    fuel_totals = {
        category: sum(_clean_val(row[h].iloc[0]) for h in headers if h in df.columns)
        for category, headers in mapping.items()
    }
    return total_tj, fuel_totals


def get_sector_shares(base_path, country, year, sector_label, fuel_mapping=None):
    total_tj, fuels = _get_sector_totals_by_fuel(base_path, country, year, sector_label, fuel_mapping)
    if total_tj <= 0:
        return _default_share_dict()
    return {fuel: round(value / total_tj, 6) for fuel, value in fuels.items()}


def get_sector_shares_historical_average(base_path, country, sector_label, years=None, fuel_mapping=None):
    if years is None:
        years = _discover_country_years(base_path, country)
    aggregate_total_tj = 0.0
    aggregate_fuel_totals = _default_share_dict()
    for year in years:
        total, fuels = _get_sector_totals_by_fuel(base_path, country, year, sector_label, fuel_mapping)
        if total <= 0:
            continue
        aggregate_total_tj += total
        for fuel in aggregate_fuel_totals:
            aggregate_fuel_totals[fuel] += fuels.get(fuel, 0.0)
    if aggregate_total_tj <= 0:
        return _default_share_dict()
    return _normalize_shares(aggregate_fuel_totals, decimals=4)


def export_sector_shares_all_countries(base_path, output_dir, sector_label, year=None,
                                      fuel_mapping=None, countries=None, years=None):
    rows = []
    for country in _select_countries(base_path, countries):
        source_years = _select_years(base_path, country, [year] if year is not None else years)
        if year is not None:
            modes = [("single_year", source_years)]
        else:
            modes = [("historical_average", source_years)]
            for start, end in BASE_PERIODS:
                period = [y for y in source_years if start <= y <= end]
                if period:
                    modes.append((f"base_period_{start}_{end}", period))
        for mode, period in modes:
            if year is not None:
                shares = get_sector_shares(base_path, country, year, sector_label, fuel_mapping)
            else:
                shares = get_sector_shares_historical_average(base_path, country, sector_label, period, fuel_mapping)
            share_sum, valid = _validate_share_sum(shares)
            rows.append({"sector": sector_label, "country": country, "share_mode": mode,
                         "share_sum": share_sum, "share_sum_is_valid": valid, **shares})
    path = Path(output_dir) / f"{_sector_output_file_prefix(sector_label)}_shares_all_countries.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def export_shares_for_multiple_sectors(base_path, output_dir, sector_labels,
                                      year=None, fuel_mapping=None, countries=None, years=None):
    return [export_sector_shares_all_countries(base_path, output_dir, sector, year,
            fuel_mapping, countries, years) for sector in sector_labels]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=ROOT / "data/country_specific")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output_data/interim/shares")
    parser.add_argument("--countries", nargs="+")
    parser.add_argument("--years", nargs="+", type=int, help="Historical UNSD source years; default: all available")
    args = parser.parse_args(argv)
    for path in export_shares_for_multiple_sectors(args.input_dir, args.output_dir,
            DEFAULT_SECTOR_LABELS, countries=args.countries, years=args.years):
        print(f"Saved shares CSV to: {path}")


if __name__ == "__main__":
    main()