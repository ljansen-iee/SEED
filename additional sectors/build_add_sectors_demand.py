"""UNSD additional-sector demand producer, restored from main (TJ to TWh)."""
import argparse
from importlib import util
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
_CORE_SHARES_SPEC = util.spec_from_file_location("_core_build_shares", ROOT / "build_shares.py")
_CORE_SHARES = util.module_from_spec(_CORE_SHARES_SPEC)
_CORE_SHARES_SPEC.loader.exec_module(_CORE_SHARES)
_clean_val = _CORE_SHARES._clean_val
_default_fuel_mapping = _CORE_SHARES._default_fuel_mapping
_default_share_dict = _CORE_SHARES._default_share_dict
_discover_countries = _CORE_SHARES._discover_countries
_discover_country_years = _CORE_SHARES._discover_country_years
_get_candidate_dirs = _CORE_SHARES._get_candidate_dirs
_normalize_sector_label = _CORE_SHARES._normalize_text
_read_unsd = _CORE_SHARES._read_unsd

SECTORS_TO_BUILD = ["Agriculture  forestry and fishing", "Commerce and public services",
                    "Non-energy use", "Other consumption n.e.s"]
TARGET_YEARS = [2030, 2035, 2040, 2045, 2050]


def _load_average_shares_from_csv(shares_csv_path, share_mode):
    shares_df = pd.read_csv(shares_csv_path)
    fuels = list(_default_share_dict())
    missing = set(["country", "share_mode", *fuels]) - set(shares_df.columns)
    if missing:
        raise ValueError(f"Shares CSV is missing required columns: {sorted(missing)}")
    rows = shares_df[shares_df["share_mode"].map(_normalize_sector_label) == _normalize_sector_label(share_mode)].copy()
    if rows.empty:
        raise ValueError(f"No '{share_mode}' rows found in {shares_csv_path}")
    if rows["country"].isna().any() or rows.duplicated("country").any():
        raise ValueError("Shares must have unique, populated country/share_mode keys")
    rows[fuels] = rows[fuels].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(rows[fuels].to_numpy()).all() or ((rows[fuels] < 0) | (rows[fuels] > 1)).any().any():
        raise ValueError("Shares must be finite fractions between zero and one")
    sums = rows[fuels].sum(axis=1)
    if ((sums > 0) & ((sums - 1).abs() > 1e-3)).any():
        raise ValueError("Positive shares must sum to one within 1e-3")
    return rows.set_index("country")[fuels].to_dict(orient="index")


def _find_sector_row(df, sector_col, sector_label):
    return df[df[sector_col].map(_normalize_sector_label) == _normalize_sector_label(sector_label)]


def _load_suggested_cagr_from_csv(cagr_csv_path, sector_label):
    df = pd.read_csv(cagr_csv_path)
    missing = {"country", "sector", "suggested_cagr"} - set(df.columns)
    if missing:
        raise ValueError(f"CAGR CSV is missing required columns: {sorted(missing)}")
    rows = _find_sector_row(df, "sector", sector_label).copy()
    if rows.empty:
        raise ValueError(f"No rows found in CAGR CSV for sector: {sector_label}")
    if rows["country"].isna().any():
        raise ValueError("CAGR countries must be populated")
    if "year" in rows and rows.duplicated(["country", "sector", "year"]).any():
        raise ValueError("CAGR country/sector/year keys must be unique")
    rows["suggested_cagr"] = pd.to_numeric(rows["suggested_cagr"], errors="coerce")
    valid = rows["suggested_cagr"].dropna()
    if not np.isfinite(valid).all() or (valid < -1).any():
        raise ValueError("suggested_cagr must be finite and at least -1")
    # Main averaged repeated suggested values across source years; retain it.
    return rows.dropna(subset=["suggested_cagr"]).groupby("country")["suggested_cagr"].mean().to_dict()


def get_sector_total_TWh(base_path, country, year, sector_label):
    df = _read_unsd(base_path, country, year)
    row = _find_sector_row(df, "Transactions(down)/Commodity(right)", sector_label)
    if row.empty:
        return 0.0
    return round(_clean_val(row["Total Energy"].iloc[0]) * 0.000277778, 6)


def get_sector_shares(base_path, country, year, sector_label, fuel_mapping=None):
    return _CORE_SHARES.get_sector_shares(base_path, country, year, sector_label, fuel_mapping)


def _fuel_demand_from_total(total_energy_twh, shares):
    return {fuel: round(total_energy_twh * share, 6) for fuel, share in shares.items()}


def _sector_column_prefix(sector_label):
    if _normalize_sector_label(sector_label) == "households":
        return "residential"
    return _CORE_SHARES._sector_column_prefix(sector_label)


def _sector_output_file_prefix(sector_label):
    return _sector_column_prefix(sector_label).replace(" ", "_")


def _rename_fuel_columns(fuel_demand, sector_label):
    return {f"{_sector_column_prefix(sector_label)} {fuel}": value for fuel, value in fuel_demand.items()}


def build_sector_fuel_demand_history_and_future(
        base_path, output_dir, sector_label, base_year_for_projection, future_years=None,
        shares_csv_path=None, cagr_csv_path=None, projection_share_mode="base_period_2017_2023",
        countries=None, years=None):
    future_years = TARGET_YEARS if future_years is None else sorted(set(future_years))
    output_prefix = _sector_output_file_prefix(sector_label)
    shares_csv_path = Path(shares_csv_path) if shares_csv_path is not None else ROOT / "output_data/interim/shares" / f"{output_prefix}_shares_all_countries.csv"
    cagr_csv_path = Path(cagr_csv_path) if cagr_csv_path is not None else ROOT / "output_data/interim/cagr" / f"{output_prefix}_cagr_all_countries.csv"
    selected = _CORE_SHARES._select_countries(base_path, countries)
    # Validate source selection before creating any output.
    for country in selected:
        _CORE_SHARES._select_years(base_path, country, [base_year_for_projection])
        if years is not None:
            _CORE_SHARES._select_years(base_path, country, [y for y in years if y <= base_year_for_projection])
    average_shares = _load_average_shares_from_csv(shares_csv_path, projection_share_mode)
    suggested_cagr = _load_suggested_cagr_from_csv(cagr_csv_path, sector_label)
    rows = []
    for country in selected:
        history = _discover_country_years(base_path, country)
        for historical_year in history:
            if years is not None and historical_year not in years:
                continue
            total = get_sector_total_TWh(base_path, country, historical_year, sector_label)
            if total <= 0:
                continue
            shares = get_sector_shares(base_path, country, historical_year, sector_label)
            rows.append({"country": country, "year": historical_year, "unit": "TWh",
                         **_rename_fuel_columns(_fuel_demand_from_total(total, shares), sector_label)})
        total = get_sector_total_TWh(base_path, country, base_year_for_projection, sector_label)
        if total <= 0:
            continue
        if country not in average_shares or country not in suggested_cagr:
            raise ValueError(f"Missing projection shares or valid suggested_cagr for {country}, {sector_label}")
        for future_year in future_years:
            if future_year <= base_year_for_projection or future_year in history:
                continue
            if years is not None and future_year not in years:
                continue
            projected = round(total * (1 + suggested_cagr[country]) ** (future_year - base_year_for_projection), 6)
            rows.append({"country": country, "year": future_year, "unit": "TWh",
                         **_rename_fuel_columns(_fuel_demand_from_total(projected, average_shares[country]), sector_label)})
    columns = ["country", "year", "unit", *[f"{_sector_column_prefix(sector_label)} {fuel}" for fuel in _default_share_dict()]]
    df = pd.DataFrame(rows, columns=columns).sort_values(["country", "year"]).reset_index(drop=True)
    if df.duplicated(["country", "year"]).any():
        raise ValueError("Additional demand country/year keys must be unique")
    if not np.isfinite(df[columns[3:]].to_numpy(dtype=float)).all() or (df[columns[3:]] < 0).any().any():
        raise ValueError("Additional demand must be finite, nonnegative TWh")
    path = Path(output_dir) / f"{output_prefix}_fuel_demand_history_future.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path


def build_fuel_demand_for_multiple_sectors(
        base_path, output_dir, base_year_for_projection, future_years=None, cagr_csv_path=None,
        projection_share_mode="base_period_2017_2023", countries=None, years=None,
        shares_dir=None, cagr_dir=None):
    outputs = []
    for sector in SECTORS_TO_BUILD:
        prefix = _sector_output_file_prefix(sector)
        outputs.append(build_sector_fuel_demand_history_and_future(
            base_path, output_dir, sector, base_year_for_projection, future_years,
            shares_csv_path=Path(shares_dir) / f"{prefix}_shares_all_countries.csv" if shares_dir is not None else None,
            cagr_csv_path=Path(cagr_dir) / f"{prefix}_cagr_all_countries.csv" if cagr_dir is not None else cagr_csv_path,
            projection_share_mode=projection_share_mode, countries=countries, years=years))
    return outputs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=ROOT / "data/country_specific")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent / "output_data")
    parser.add_argument("--countries", nargs="+")
    parser.add_argument("--years", nargs="+", type=int, help="Exact output years; default: history and standard projections")
    parser.add_argument("--base-year", type=int, default=2023)
    parser.add_argument("--shares-dir", type=Path, default=ROOT / "output_data/interim/shares")
    parser.add_argument("--cagr-dir", type=Path, default=ROOT / "output_data/interim/cagr")
    parser.add_argument("--cagr-csv-path", type=Path, help="Use one all-sector CAGR table instead of --cagr-dir")
    parser.add_argument("--projection-share-mode", default="base_period_2017_2023")
    args = parser.parse_args(argv)
    for path in build_fuel_demand_for_multiple_sectors(args.input_dir, args.output_dir, args.base_year,
            future_years=[y for y in args.years if y > args.base_year] if args.years is not None else None,
            cagr_csv_path=args.cagr_csv_path, projection_share_mode=args.projection_share_mode,
            countries=args.countries, years=args.years, shares_dir=args.shares_dir,
            cagr_dir=None if args.cagr_csv_path is not None else args.cagr_dir):
        print(f"Saved final demand CSV to: {path}")


if __name__ == "__main__":
    main()