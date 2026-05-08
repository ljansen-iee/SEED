from pathlib import Path

import pandas as pd
import pycountry


def _scenario_slug(value: str):
	return "_".join(str(value).strip().lower().split())


def get_iso_code(country_name: str) -> str:
	"""Return the ISO 3166-1 alpha-2 code for a country name. Falls back to 'XX' if not found."""
	try:
		result = pycountry.countries.search_fuzzy(country_name)
		if result:
			return getattr(result[0], "alpha_2", "XX")
	except (LookupError, AttributeError):
		pass
	print(f"Warning: Could not find ISO code for '{country_name}'. Defaulting to 'XX'.")
	return "XX"


def load_residential_data(residential_output_dir: Path):
	residential_file = Path(residential_output_dir) / "residential_all_scenarios_years_countries.csv"
	if not residential_file.exists():
		raise FileNotFoundError(f"Residential file not found: {residential_file}")

	residential_df = pd.read_csv(residential_file)
	required = ["country", "scenario", "year"]
	missing = [column for column in required if column not in residential_df.columns]
	if missing:
		raise ValueError(f"Residential file is missing required columns: {missing}")

	residential_df["year"] = pd.to_numeric(residential_df["year"], errors="coerce")
	residential_df = residential_df.dropna(subset=["year"])
	residential_df["year"] = residential_df["year"].astype(int)
	return residential_df


def load_additional_sectors_data(additional_output_dir: Path):
	sector_files = [
		"agriculture_fuel_demand_history_future.csv",
		"services_fuel_demand_history_future.csv",
		"non_energy_fuel_demand_history_future.csv",
		"other_fuel_demand_history_future.csv",
	]

	merged_df: pd.DataFrame = pd.DataFrame()
	for file_name in sector_files:
		file_path = Path(additional_output_dir) / file_name
		if not file_path.exists():
			raise FileNotFoundError(f"Additional sectors file not found: {file_path}")

		sector_df = pd.read_csv(file_path)
		sector_df["year"] = pd.to_numeric(sector_df["year"], errors="coerce")
		sector_df = sector_df.dropna(subset=["year"])
		sector_df["year"] = sector_df["year"].astype(int)

		if "unit" in sector_df.columns:
			sector_df = sector_df.drop(columns=["unit"])

		if merged_df.empty:
			merged_df = sector_df
		else:
			merged_df = merged_df.merge(sector_df, on=["country", "year"], how="outer")

	return merged_df


def export_energy_totals_by_scenario_year(
	residential_output_dir: Path,
	additional_output_dir: Path,
	output_dir: Path,
):
	residential_df = load_residential_data(residential_output_dir=residential_output_dir)
	additional_df = load_additional_sectors_data(additional_output_dir=additional_output_dir)

	output_dir = Path(output_dir)
	output_dir.mkdir(parents=True, exist_ok=True)

	output_files = []
	scenario_years = (
		residential_df[["scenario", "year"]]
		.drop_duplicates()
		.sort_values(by=["scenario", "year"])
		.itertuples(index=False)
	)

	for scenario_value, year_value in scenario_years:
		residential_slice = residential_df[
			(residential_df["scenario"] == scenario_value) & (residential_df["year"] == int(year_value))
		]

		additional_slice = additional_df[additional_df["year"] == int(year_value)]

		merged = residential_slice.merge(
			additional_slice,
			on=["country", "year"],
			how="left",
		)

		merged["country"] = merged["country"].map(get_iso_code)

		scenario_slug = _scenario_slug(scenario_value)
		output_path = output_dir / f"energy_total+{scenario_slug}+{int(year_value)}.csv"
		merged.to_csv(output_path, index=False)
		output_files.append(output_path)

	return output_files


if __name__ == "__main__":
	root = Path(__file__).resolve().parent
	residential_output_dir = root / "residential" / "output_data"
	additional_output_dir = root / "additional sectors" / "output_data"
	output_dir = root / "output_data" / "energy_totals"

	files = export_energy_totals_by_scenario_year(
		residential_output_dir=residential_output_dir,
		additional_output_dir=additional_output_dir,
		output_dir=output_dir,
	)

	for file_path in files:
		print(f"Saved: {file_path}")
