from pathlib import Path
import pandas as pd
import re


# Countries we want to keep in merged outputs
ALLOWED_COUNTRIES = [
	"Algeria",
	"Egypt",
	"Ethiopia",
	"Ghana",
	"Kenya",
	"Namibia",
	"Nigeria",
	"Mauritania",
	"Morocco",
	"Tunisia",
	"Tanzania",
	"Libya",
	"Republic of Congo",
	"South Africa",
]


def _scenario_slug(value: str):
	return "_".join(str(value).strip().lower().split())


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

	merged_df = None
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

		if merged_df is None:
			merged_df = sector_df
		else:
			merged_df = merged_df.merge(sector_df, on=["country", "year"], how="outer")

	return merged_df


def load_transport_data(transport_output_dir: Path):
	pattern = re.compile(r"transport_(?P<scenario>.+?)_(?P<year>\d{4})\.csv", re.IGNORECASE)
	files = list(Path(transport_output_dir).glob("transport_*.csv"))
	if not files:
		raise FileNotFoundError(f"No transport files found in {transport_output_dir}")

	frames = []
	for file_path in files:
		match = pattern.match(file_path.name)
		scenario_from_name = match.group("scenario") if match else None
		year_from_name = int(match.group("year")) if match else None

		df = pd.read_csv(file_path)

		# prefer explicit columns if present
		year_col = None
		scenario_col = None
		if "year" in df.columns:
			year_col = pd.to_numeric(df["year"], errors="coerce")
		if "scenario_name" in df.columns:
			scenario_col = df["scenario_name"].astype(str)
		elif "scenario" in df.columns:
			scenario_col = df["scenario"].astype(str)

		if year_col is not None:
			df["year"] = year_col
		elif year_from_name is not None:
			df["year"] = year_from_name

		if scenario_col is not None:
			df["scenario"] = scenario_col
		elif scenario_from_name is not None:
			df["scenario"] = scenario_from_name

		df["year"] = pd.to_numeric(df["year"], errors="coerce")
		df = df.dropna(subset=["year"])
		df["year"] = df["year"].astype(int)

		frames.append(df)

	transport_df = pd.concat(frames, ignore_index=True)
	if "country" not in transport_df.columns:
		raise ValueError("Transport data missing required column 'country'")

	transport_df["country"] = transport_df["country"].astype(str).str.strip()
	transport_df["scenario"] = transport_df["scenario"].astype(str).str.strip()
	return transport_df


def _filter_allowed_countries(df: pd.DataFrame, allowed_countries):
	if allowed_countries is None or df is None:
		return df
	return df[df["country"].isin(allowed_countries)]


def export_energy_totals_by_scenario_year(
	residential_output_dir: Path,
	additional_output_dir: Path,
	transport_output_dir: Path,
	output_dir: Path,
	allowed_countries=None,
):
	residential_df = load_residential_data(residential_output_dir=residential_output_dir)
	additional_df = load_additional_sectors_data(additional_output_dir=additional_output_dir)
	transport_df = load_transport_data(transport_output_dir=transport_output_dir)

	residential_df = _filter_allowed_countries(residential_df, allowed_countries)
	additional_df = _filter_allowed_countries(additional_df, allowed_countries)
	transport_df = _filter_allowed_countries(transport_df, allowed_countries)

	output_dir = Path(output_dir)
	output_dir.mkdir(parents=True, exist_ok=True)

	output_files = []

	# Collect all scenario/year combos from residential and transport
	scenario_years_df = pd.concat(
		[
			residential_df[["scenario", "year"]],
			transport_df[["scenario", "year"]],
		],
		ignore_index=True,
	).drop_duplicates().sort_values(by=["scenario", "year"])

	scenario_years = scenario_years_df.itertuples(index=False)

	for scenario_value, year_value in scenario_years:
		residential_slice = residential_df[
			(residential_df["scenario"] == scenario_value) & (residential_df["year"] == int(year_value))
		]

		additional_slice = additional_df[additional_df["year"] == int(year_value)]


		transport_slice = transport_df[
			(transport_df["scenario"] == scenario_value) & (transport_df["year"] == int(year_value))
		]

		# Track country coverage per sector
		countries_res = set(residential_slice["country"]) if not residential_slice.empty else set()
		countries_add = set(additional_slice["country"]) if not additional_slice.empty else set()
		countries_trn = set(transport_slice["country"]) if not transport_slice.empty else set()
		all_countries = countries_res | countries_add | countries_trn

		missing_msgs = []
		if countries_res != all_countries:
			missing = sorted(all_countries - countries_res)
			if missing:
				missing_msgs.append(f"Residential missing: {missing}")
		if countries_add != all_countries:
			missing = sorted(all_countries - countries_add)
			if missing:
				missing_msgs.append(f"Additional missing: {missing}")
		if countries_trn != all_countries:
			missing = sorted(all_countries - countries_trn)
			if missing:
				missing_msgs.append(f"Transport missing: {missing}")
		if missing_msgs:
			print(f"WARNING [{scenario_value} {year_value}]: " + "; ".join(missing_msgs))

		# Drop scenario column to avoid duplicates, we'll reattach later
		residential_slice = residential_slice.drop(columns=["scenario"], errors="ignore")
		transport_slice = transport_slice.drop(columns=["scenario", "scenario_name"], errors="ignore")

		merged = residential_slice.merge(
			additional_slice,
			on=["country", "year"],
			how="outer",
		)
		merged = merged.merge(
			transport_slice,
			on=["country", "year"],
			how="outer",
		)

		merged["scenario"] = scenario_value
		merged["year"] = int(year_value)

		scenario_slug = _scenario_slug(scenario_value)
		output_path = output_dir / f"energy_total+{scenario_slug}+{int(year_value)}.csv"
		merged.to_csv(output_path, index=False)
		output_files.append(output_path)

	return output_files


if __name__ == "__main__":
	root = Path(__file__).resolve().parent
	residential_output_dir = root / "residential" / "output_data"
	additional_output_dir = root / "additional sectors" / "output_data"
	transport_output_dir = root / "transport" / "output_data"
	output_dir = root / "output_data" / "energy_totals"

	files = export_energy_totals_by_scenario_year(
		residential_output_dir=residential_output_dir,
		additional_output_dir=additional_output_dir,
		transport_output_dir=transport_output_dir,
		output_dir=output_dir,
		allowed_countries=ALLOWED_COUNTRIES,
	)

	for file_path in files:
		print(f"Saved: {file_path}")
