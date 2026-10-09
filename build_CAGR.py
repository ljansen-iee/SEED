"""Shared historical sector CAGR preprocessing, restored from main."""
import argparse
from pathlib import Path

import pandas as pd

from build_shares import (
    ROOT, _clean_val, _normalize_text, _read_unsd, _select_countries,
    _select_years, _sector_output_file_prefix,
)

TARGET_SECTORS = [
    "Agriculture forestry and fishing", "Chemical and petrochemical",
    "Commerce and public services", "Construction", "Food and tobacco",
    "International aviation bunkers", "International marine bunkers", "Iron and steel",
    "Machinery", "Mining and quarrying", "Non-ferrous metals", "Non-metallic minerals",
    "Paper pulp and printing", "Textile and leather", "Transport equipment",
    "Wood and wood products", "Non-energy use", "Other consumption n.e.s",
]


def _read_unsd_country_year_file(base_path, country, year):
    return _read_unsd(base_path, country, year)


def build_country_sector_year_aggregation(base_path, sectors=None, countries=None, years=None):
    if sectors is None:
        sectors = TARGET_SECTORS
    normalized_to_sector = {_normalize_text(sector): sector for sector in sectors}
    rows = []
    for country in _select_countries(base_path, countries):
        for year in _select_years(base_path, country, years):
            df = _read_unsd_country_year_file(base_path, country, year)
            working = df[["Transactions(down)/Commodity(right)", "Total Energy"]].copy()
            working["_sector_normalized"] = working.iloc[:, 0].map(_normalize_text)
            working["_total_tj"] = working["Total Energy"].map(_clean_val)
            totals = working[working["_sector_normalized"].isin(normalized_to_sector)].groupby(
                "_sector_normalized")["_total_tj"].sum().to_dict()
            for normalized, sector in normalized_to_sector.items():
                rows.append({"country": country, "sector": sector, "year": int(year),
                             "unit": "TWh", "total_energy_twh": round(float(totals.get(normalized, 0)) * 0.000277778, 6)})
    return pd.DataFrame(rows, columns=["country", "sector", "year", "unit", "total_energy_twh"]).sort_values(
        ["country", "sector", "year"]).reset_index(drop=True)


def add_rolling_cagr(aggregated_df):
    output_df = aggregated_df.copy()
    keys = ["country", "sector", "year"]
    if output_df[keys].isna().any().any() or output_df.duplicated(keys).any():
        raise ValueError("CAGR input must have populated, unique country/sector/year keys")
    if output_df.empty:
        output_df["CAGR"] = pd.NA
        output_df["suggested_cagr"] = pd.NA
        return output_df
    # Keep main's original convention: start at year-4, exponent 1/5.
    output_df["cagr_start_year"] = output_df["year"] - 4
    start_lookup = output_df[keys + ["total_energy_twh"]].rename(
        columns={"year": "cagr_start_year", "total_energy_twh": "start_total_twh"})
    output_df = output_df.merge(start_lookup, on=["country", "sector", "cagr_start_year"],
                                how="left", validate="many_to_one")
    valid = (output_df["start_total_twh"] > 0) & (output_df["total_energy_twh"] > 0)
    output_df["CAGR"] = float("nan")
    output_df.loc[valid, "CAGR"] = (
        (output_df.loc[valid, "total_energy_twh"] / output_df.loc[valid, "start_total_twh"]) ** (1 / 5) - 1)
    output_df["CAGR"] = pd.to_numeric(output_df["CAGR"], errors="coerce").round(6)
    output_df["suggested_cagr"] = output_df.groupby(["country", "sector"], dropna=False)["CAGR"].transform("mean").round(6)
    return output_df.drop(columns=["start_total_twh", "cagr_start_year"]).sort_values(keys).reset_index(drop=True)


def export_all_sectors_cagr_csv(base_path, output_dir, sectors=None, countries=None, years=None):
    cagr_df = add_rolling_cagr(build_country_sector_year_aggregation(base_path, sectors, countries, years))
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "all_sectors_country_year_cagr.csv"
    cagr_df.to_csv(output_path, index=False)
    for sector in TARGET_SECTORS if sectors is None else sectors:
        sector_slice = cagr_df[cagr_df["sector"].map(_normalize_text) == _normalize_text(sector)]
        sector_slice.to_csv(output_dir / f"{_sector_output_file_prefix(sector)}_cagr_all_countries.csv", index=False)
    return output_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=ROOT / "data/country_specific")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output_data/interim/cagr")
    parser.add_argument("--countries", nargs="+")
    parser.add_argument("--years", nargs="+", type=int, help="Historical UNSD source years; default: all available")
    args = parser.parse_args(argv)
    path = export_all_sectors_cagr_csv(args.input_dir, args.output_dir, countries=args.countries, years=args.years)
    print(f"Saved all-sectors CAGR CSV to: {path}")


if __name__ == "__main__":
    main()