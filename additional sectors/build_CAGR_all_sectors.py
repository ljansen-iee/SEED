from pathlib import Path

import pandas as pd

from build_shares import _clean_val, _discover_countries, _discover_country_years, _get_candidate_dirs


TARGET_SECTORS = [
	"Agriculture forestry and fishing",
	"Chemical and petrochemical",
	"Commerce and public services",
	"Construction",
	"Food and tobacco",
	"International aviation bunkers",
	"International marine bunkers",
	"Iron and steel",
	"Machinery",
	"Mining and quarrying",
	"Non-ferrous metals",
	"Non-metallic minerals",
	"Paper pulp and printing",
	"Textile and leather",
	"Transport equipment",
	"Wood and wood products",
	"Non-energy use",
	"Other consumption n.e.s",
]


def _normalize_text(value: str):
	return " ".join(str(value).strip().lower().split())


def _read_unsd_country_year_file(base_path: Path, country: str, year: int):
	filename = f"UNSD_{country}-{year}.csv"
	candidates = [directory / filename for directory in _get_candidate_dirs(base_path)]
	file_path = next((candidate for candidate in candidates if candidate.exists()), candidates[0])

	if not file_path.exists():
		return None

	return pd.read_csv(file_path)


def build_country_sector_year_aggregation(base_path: Path, sectors: list = None):
	if sectors is None:
		sectors = TARGET_SECTORS

	normalized_to_sector = {_normalize_text(sector): sector for sector in sectors}
	countries = _discover_countries(base_path=base_path)
	rows = []

	for country in countries:
		years = _discover_country_years(base_path=base_path, country=country)
		for year in years:
			unsd_df = _read_unsd_country_year_file(base_path=base_path, country=country, year=year)
			if unsd_df is None or unsd_df.empty:
				continue

			sector_col = "Transactions(down)/Commodity(right)"
			if sector_col not in unsd_df.columns or "Total Energy" not in unsd_df.columns:
				continue

			working_df = unsd_df[[sector_col, "Total Energy"]].copy()
			working_df["_sector_normalized"] = working_df[sector_col].apply(_normalize_text)
			working_df["_total_tj"] = working_df["Total Energy"].apply(_clean_val)

			totals_by_sector = (
				working_df[working_df["_sector_normalized"].isin(normalized_to_sector.keys())]
				.groupby("_sector_normalized", as_index=True)["_total_tj"]
				.sum()
				.to_dict()
			)

			for normalized_sector, sector_name in normalized_to_sector.items():
				total_tj = float(totals_by_sector.get(normalized_sector, 0.0))
				total_twh = round(total_tj * 0.000277778, 6)
				rows.append(
					{
						"country": country,
						"sector": sector_name,
						"year": int(year),
						"unit": "TWh",
						"total_energy_twh": total_twh,
					}
				)

	output_df = pd.DataFrame(rows)
	if output_df.empty:
		return pd.DataFrame(columns=["country", "sector", "year", "unit", "total_energy_twh"])

	return output_df.sort_values(by=["country", "sector", "year"]).reset_index(drop=True)


def add_rolling_cagr(aggregated_df: pd.DataFrame):
	output_df = aggregated_df.copy()
	if output_df.empty:
		output_df["CAGR"] = pd.NA
		output_df["suggested_cagr"] = pd.NA
		return output_df

	output_df["cagr_end_year"] = output_df["year"]
	output_df["cagr_start_year"] = output_df["year"] - 4
	output_df["cagr_periods"] = 5

	start_lookup = output_df[["country", "sector", "year", "total_energy_twh"]].rename(
		columns={
			"year": "cagr_start_year",
			"total_energy_twh": "start_total_twh",
		}
	)

	output_df = output_df.merge(start_lookup, on=["country", "sector", "cagr_start_year"], how="left")

	valid_mask = (output_df["start_total_twh"] > 0) & (output_df["total_energy_twh"] > 0)
	output_df["CAGR"] = pd.NA
	output_df.loc[valid_mask, "CAGR"] = (
		(output_df.loc[valid_mask, "total_energy_twh"] / output_df.loc[valid_mask, "start_total_twh"])
		** (1 / output_df.loc[valid_mask, "cagr_periods"])
		- 1
	)
	output_df["CAGR"] = pd.to_numeric(output_df["CAGR"], errors="coerce").round(6)
	output_df["suggested_cagr"] = (
		output_df.groupby(["country", "sector"], dropna=False)["CAGR"]
		.transform("mean")
		.round(6)
	)

	output_df = output_df.drop(columns=["start_total_twh", "cagr_start_year", "cagr_end_year", "cagr_periods"])
	return output_df.sort_values(by=["country", "sector", "year"]).reset_index(drop=True)


def export_all_sectors_cagr_csv(base_path: Path, output_dir: Path, sectors: list = None):
	aggregated_df = build_country_sector_year_aggregation(base_path=base_path, sectors=sectors)
	cagr_df = add_rolling_cagr(aggregated_df=aggregated_df)

	output_dir = Path(output_dir)
	output_dir.mkdir(parents=True, exist_ok=True)
	output_path = output_dir / "all_sectors_country_year_cagr.csv"
	cagr_df.to_csv(output_path, index=False)
	return output_path


if __name__ == "__main__":
	base_path = Path(__file__).resolve().parents[1] / "data" / "country_specific"
	output_dir = Path(__file__).resolve().parent / "output_data"

	output_file = export_all_sectors_cagr_csv(
		base_path=base_path,
		output_dir=output_dir,
		sectors=TARGET_SECTORS,
	)
	print(f"Saved all-sectors CAGR CSV to: {output_file}")
