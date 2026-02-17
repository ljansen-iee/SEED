import os
import numpy as np
import pandas as pd
from pathlib import Path
import build_energy_intensities as build_en_int


RESIDENTIAL_CONFIG_FILE = "parameters_all_countries.csv"

residential_config_path = Path(__file__).resolve().parent / "output_data" / RESIDENTIAL_CONFIG_FILE


print("\n===============================")
print(f"Residential configuration file: {RESIDENTIAL_CONFIG_FILE}")
print("===============================\n")


INTENSITY_SH, INTENSITY_WH, INTENSITY_SC, INTENSITY_COOKING, INTENSITY_APPLIANCES = (
	build_en_int.insert_energy_intensities()
)

SPACE_HEATING_INTENSITY_MAP = build_en_int.get_space_heating_intensity_map()
SPACE_COOLING_INTENSITY_MAP = build_en_int.get_space_cooling_intensity_map()
WATER_HEATING_INTENSITY_MAP = build_en_int.get_water_heating_intensity_map()
COOKING_INTENSITY_MAP = build_en_int.get_cooking_intensity_map()


def get_cagr_adjusted_intensity(
	df_long: pd.DataFrame,
	cagr_metric: str,
	end_use_keyword: str,
	base_intensity: float,
	base_year: int = 2020,
) -> pd.Series:
	base_df = df_long[
		(df_long["type"] == "energy intensity")
		& df_long["metric name"].str.contains("Final Energy Intensity", case=False, na=False)
		& df_long["metric name"].str.contains(end_use_keyword, case=False, na=False)
		& (df_long["year"] == base_year)
	].copy()
	base_df["value"] = pd.to_numeric(base_df["value"], errors="coerce")
	base_series = base_df.groupby(["country", "scenario"])["value"].mean()

	cagr_series = df_long[(df_long["type"] == "CAGR") & (df_long["metric name"] == cagr_metric)].set_index(
		["country", "scenario", "year"]
	)["value"]
	cagr_series = pd.to_numeric(cagr_series, errors="coerce").fillna(0)

	base_aligned = base_series.reindex(cagr_series.index.droplevel("year"))
	base_aligned.index = cagr_series.index
	base_aligned = base_aligned.fillna(base_intensity)

	return base_aligned * (1 + cagr_series / 100) ** 5


def add_end_use_column(df: pd.DataFrame) -> pd.DataFrame:
	df = df.copy()
	metric = df["metric name"].astype(str)
	end_use = pd.Series(pd.NA, index=df.index, dtype="object")

	end_use = end_use.mask(metric.str.contains("Space Heating", case=False, na=False), "Space Heating")
	end_use = end_use.mask(metric.str.contains("Space Cooling", case=False, na=False), "Space Cooling")
	end_use = end_use.mask(metric.str.contains("Water Heating", case=False, na=False), "Water Heating")
	end_use = end_use.mask(metric.str.contains("Cooking", case=False, na=False), "Cooking")
	end_use = end_use.mask(metric.str.contains("Electrical Appliances", case=False, na=False), "Electrical Appliances")

	df["end_use"] = end_use
	return df


def prepare_long_df(df: pd.DataFrame) -> pd.DataFrame:
	df = add_end_use_column(df)
	country_cols = [c for c in df.columns if c not in ["type", "metric name", "year", "scenario", "units", "end_use"]]
	df_long = df.melt(
		id_vars=["type", "metric name", "year", "scenario", "units", "end_use"],
		value_vars=country_cols,
		var_name="country",
		value_name="value",
	)
	df_long["value"] = pd.to_numeric(df_long["value"], errors="coerce")
	return df_long


def get_metric_series(df_long: pd.DataFrame, metric_name: str) -> pd.Series:
	return df_long[df_long["metric name"] == metric_name].set_index(["country", "scenario", "year"])["value"]


def build_tech_intensity_frame(
	share_rows: pd.DataFrame,
	df_long: pd.DataFrame,
	end_use_keyword: str,
	cagr_metric: str,
	default_intensity_map: dict,
	default_base_intensity: float,
	base_year: int = 2020,
) -> pd.DataFrame:
	def extract_tech(name: str) -> str:
		name = name.replace("Final Energy Intensity of ", "")
		name = name.replace("Share of ", "")
		name = name.replace(f"for {end_use_keyword}", "")
		return name.strip()

	base_intensity_rows = df_long[
		(df_long["type"] == "energy intensity")
		& df_long["metric name"].str.contains("Final Energy Intensity", case=False, na=False)
		& df_long["metric name"].str.contains(end_use_keyword, case=False, na=False)
		& (df_long["year"] == base_year)
	].copy()
	base_intensity_rows["value"] = pd.to_numeric(base_intensity_rows["value"], errors="coerce")
	base_intensity_rows["tech"] = base_intensity_rows["metric name"].map(extract_tech)
	base_intensity_series = base_intensity_rows.set_index(["country", "scenario", "tech"])["value"]

	cagr_series = df_long[(df_long["type"] == "CAGR") & (df_long["metric name"] == cagr_metric)].set_index(
		["country", "scenario", "year"]
	)["value"]
	cagr_series = pd.to_numeric(cagr_series, errors="coerce").fillna(0)

	share_rows = share_rows.copy()
	share_rows["tech"] = share_rows["metric name"].map(extract_tech)
	share_rows = share_rows.set_index(["country", "scenario", "year", "tech"])["value"]

	tech_frame = share_rows.rename("share").reset_index()
	tech_frame = tech_frame.merge(
		cagr_series.rename("cagr").reset_index(),
		on=["country", "scenario", "year"],
		how="left",
	)
	tech_frame["base_intensity"] = tech_frame.set_index(["country", "scenario", "tech"]).index.map(
		base_intensity_series
	)
	tech_frame["base_intensity"] = tech_frame["base_intensity"].fillna(
		tech_frame["tech"].map(default_intensity_map)
	).fillna(default_base_intensity)
	tech_frame["cagr"] = pd.to_numeric(tech_frame["cagr"], errors="coerce").fillna(0)
	tech_frame["intensity"] = tech_frame["base_intensity"] * (1 + tech_frame["cagr"] / 100) ** 5
	tech_frame = tech_frame.dropna(subset=["share", "intensity"])
	return tech_frame.reset_index()


def compute_space_heating_demand(df: pd.DataFrame) -> pd.DataFrame:
	df_long = prepare_long_df(df)

	pop = get_metric_series(df_long, "Population")
	area = get_metric_series(df_long, "Residential Area per Person")
	saturation = get_metric_series(df_long, "Saturation of Space Heating")

	share_rows = df_long[
		df_long["metric name"].str.contains("Share of", case=False, na=False)
		& df_long["metric name"].str.contains("Space Heating", case=False, na=False)
	]
	tech_frame = build_tech_intensity_frame(
		share_rows,
		df_long,
		"Space Heating",
		"Final Energy Intensity of Space Heating",
		SPACE_HEATING_INTENSITY_MAP,
		INTENSITY_SH,
	)

	base = pd.concat(
		[pop.rename("population"), area.rename("area_per_person"), saturation.rename("saturation")],
		axis=1,
	).reset_index()

	merged = tech_frame.merge(base, on=["country", "scenario", "year"], how="left")
	merged = merged.dropna(subset=["population", "area_per_person", "saturation", "share", "intensity"])

	def map_fuel(tech: str) -> str:
		fuel_map = {
			"Oil Boilers": "Oil",
			"LPG Boilers": "LPG",
			"Natural Gas Boilers": "Natural Gas",
			"Kerosene Boilers": "Kerosene",
			"Coal Boilers": "Coal",
			"Biogas Boilers": "Biogas",
			"Traditional Biomass Boilers": "Traditional Biomass",
			"Modern Biomass Boilers": "Modern Biomass",
			"Hydrogen Boilers": "Hydrogen",
			"Solar Heating": "Solar",
			"District Heating": "District Heating",
			"Electric Heaters": "Electricity",
			"Heat Pumps": "Electricity",
		}
		for key, val in fuel_map.items():
			if key in tech:
				return val
		return "Unknown"

	merged["fuel"] = merged["tech"].map(map_fuel)
	merged["electricity_part"] = np.where(merged["tech"].str.contains("Heat Pumps", na=False), 0.3, 1.0)
	merged["final_energy_demand_kwh"] = (
		merged["population"]
		* merged["area_per_person"]
		* merged["saturation"]
		* merged["share"]
		* merged["intensity"]
		* merged["electricity_part"]
	)
	merged["final_energy_demand_twh"] = merged["final_energy_demand_kwh"] / 1e9
	merged["end_use"] = "Space Heating"

	return merged[["country", "scenario", "year", "end_use", "tech", "fuel", "final_energy_demand_kwh", "final_energy_demand_twh"]]


def compute_space_cooling_demand(df: pd.DataFrame) -> pd.DataFrame:
	df_long = prepare_long_df(df)

	pop = get_metric_series(df_long, "Population")
	area = get_metric_series(df_long, "Residential Area per Person")
	saturation = get_metric_series(df_long, "Saturation of Space Cooling")

	share_rows = df_long[
		df_long["metric name"].str.contains("Share of", case=False, na=False)
		& df_long["metric name"].str.contains("Space Cooling", case=False, na=False)
	]
	tech_frame = build_tech_intensity_frame(
		share_rows,
		df_long,
		"Space Cooling",
		"Final Energy Intensity of Space Cooling",
		SPACE_COOLING_INTENSITY_MAP,
		INTENSITY_SC,
	)
	unique_techs = sorted(tech_frame["tech"].dropna().unique().tolist())
	if len(unique_techs) > 2:
		print(f"Warning: Expected 2 space cooling technologies, found {len(unique_techs)}: {unique_techs}")

	base = pd.concat(
		[pop.rename("population"), area.rename("area_per_person"), saturation.rename("saturation")],
		axis=1,
	).reset_index()

	merged = tech_frame.merge(base, on=["country", "scenario", "year"], how="left")
	merged = merged.dropna(subset=["population", "area_per_person", "saturation", "share", "intensity"])

	def map_fuel(tech: str) -> str:
		fuel_map = {
			"Air Conditioners": "Electricity",
			"Fans": "Electricity",
			"Heat Pumps": "Electricity",
		}
		for key, val in fuel_map.items():
			if key in tech:
				return val
		return "Unknown"

	merged["fuel"] = merged["tech"].map(map_fuel)
	merged["electricity_part"] = np.where(merged["tech"].str.contains("Heat Pumps", na=False), 1, 1.0)
	merged["final_energy_demand_kwh"] = (
		merged["population"]
		* merged["area_per_person"]
		* merged["saturation"]
		* merged["share"]
		* merged["intensity"]
		* merged["electricity_part"]
	)
	merged["final_energy_demand_twh"] = merged["final_energy_demand_kwh"] / 1e9
	merged["end_use"] = "Space Cooling"

	return merged[["country", "scenario", "year", "end_use", "tech", "fuel", "final_energy_demand_kwh", "final_energy_demand_twh"]]


def compute_water_heating_demand(df: pd.DataFrame) -> pd.DataFrame:
	df_long = prepare_long_df(df)

	pop = get_metric_series(df_long, "Population")
	ppd = get_metric_series(df_long, "Persons per Dwelling")
	saturation = get_metric_series(df_long, "Saturation of Water Heating")

	share_rows = df_long[
		df_long["metric name"].str.contains("Share of", case=False, na=False)
		& df_long["metric name"].str.contains("Water Heating", case=False, na=False)
	]
	tech_frame = build_tech_intensity_frame(
		share_rows,
		df_long,
		"Water Heating",
		"Final Energy Intensity of Water Heating",
		WATER_HEATING_INTENSITY_MAP,
		INTENSITY_WH,
	)

	base = pd.concat(
		[
			pop.rename("population"),
			ppd.rename("persons_per_dwelling"),
			saturation.rename("saturation"),
		],
		axis=1,
	).reset_index()

	merged = tech_frame.merge(base, on=["country", "scenario", "year"], how="left")
	merged = merged.dropna(subset=["population", "persons_per_dwelling", "saturation", "share", "intensity"])

	def map_fuel(tech: str) -> str:
		fuel_map = {
			"Oil Boilers": "Oil",
			"LPG Boilers": "LPG",
			"Natural Gas Boilers": "Natural Gas",
			"Kerosene Boilers": "Kerosene",
			"Coal Boilers": "Coal",
			"Biogas Boilers": "Biogas",
			"Traditional Biomass Boilers": "Traditional Biomass",
			"Modern Biomass Boilers": "Modern Biomass",
			"Hydrogen Boilers": "Hydrogen",
			"Solar Heating": "Solar",
			"District Heating": "District Heating",
			"Electric Heaters": "Electricity",
			"Heat Pumps": "Electricity",
		}
		for key, val in fuel_map.items():
			if key in tech:
				return val
		return "Unknown"

	merged["fuel"] = merged["tech"].map(map_fuel)
	merged["electricity_part"] = np.where(merged["tech"].str.contains("Heat Pumps", na=False), 0.3, 1.0)
	merged["dwellings"] = merged["population"] / merged["persons_per_dwelling"]
	merged = merged.replace([np.inf, -np.inf], np.nan)
	merged = merged.dropna(subset=["dwellings"])
	merged["final_energy_demand_kwh"] = (
		merged["dwellings"]
		* merged["saturation"]
		* merged["share"]
		* merged["intensity"]
		* merged["electricity_part"]
	)
	merged["final_energy_demand_twh"] = merged["final_energy_demand_kwh"] / 1e9
	merged["end_use"] = "Water Heating"

	return merged[["country", "scenario", "year", "end_use", "tech", "fuel", "final_energy_demand_kwh", "final_energy_demand_twh"]]


def compute_cooking_demand(df: pd.DataFrame) -> pd.DataFrame:
	df_long = prepare_long_df(df)

	pop = get_metric_series(df_long, "Population")
	ppd = get_metric_series(df_long, "Persons per Dwelling")
	saturation = get_metric_series(df_long, "Saturation of Cooking")

	share_rows = df_long[
		df_long["metric name"].str.contains("Share of", case=False, na=False)
		& df_long["metric name"].str.contains("Cooking", case=False, na=False)
	]
	base_intensity_rows = df_long[
		(df_long["type"] == "energy intensity")
		& df_long["metric name"].str.contains("Final Energy Intensity", case=False, na=False)
		& df_long["metric name"].str.contains("Cooking", case=False, na=False)
		& (df_long["year"] == 2020)
	].copy()
	cagr_series = df_long[
		(df_long["type"] == "CAGR")
		& (df_long["metric name"] == "Final Energy Intensity of Cooking")
	].set_index(["country", "scenario", "year"])["value"]
	cagr_series = pd.to_numeric(cagr_series, errors="coerce").fillna(0)

	def extract_tech(name: str) -> str:
		name = name.replace("Final Energy Intensity of ", "")
		name = name.replace("Share of ", "")
		name = name.replace("for Cooking", "")
		return name.strip()

	share_rows = share_rows.copy()
	share_rows["tech"] = share_rows["metric name"].map(extract_tech)
	base_intensity_rows["tech"] = base_intensity_rows["metric name"].map(extract_tech)

	share_rows = share_rows.set_index(["country", "scenario", "year", "tech"])["value"]
	base_intensity_rows["value"] = pd.to_numeric(base_intensity_rows["value"], errors="coerce")
	base_intensity_series = base_intensity_rows.set_index(["country", "scenario", "tech"])["value"]

	default_cooking_map = {
		"Electric Stoves": 792,
		"Natural Gas Stoves": 675,
		"LPG Stoves": 385,
		"Kerosene Stoves": 792,
		"Traditional Biomass Stoves": 2000,
	}

	tech_frame = share_rows.rename("share").reset_index()
	tech_frame = tech_frame.merge(
		cagr_series.rename("cagr").reset_index(),
		on=["country", "scenario", "year"],
		how="left",
	)
	tech_frame["base_intensity"] = tech_frame.set_index(["country", "scenario", "tech"]).index.map(
		base_intensity_series
	)
	tech_frame["base_intensity"] = tech_frame["base_intensity"].fillna(
		tech_frame["tech"].map(default_cooking_map)
	).fillna(INTENSITY_COOKING)
	tech_frame["cagr"] = pd.to_numeric(tech_frame["cagr"], errors="coerce").fillna(0)
	tech_frame["intensity"] = tech_frame["base_intensity"] * (1 + tech_frame["cagr"] / 100) ** 5
	tech_frame = tech_frame.dropna(subset=["share", "intensity"])
	tech_frame = tech_frame.reset_index()

	base = pd.concat(
		[
			pop.rename("population"),
			ppd.rename("persons_per_dwelling"),
			saturation.rename("saturation"),
		],
		axis=1,
	).reset_index()

	merged = tech_frame.merge(base, on=["country", "scenario", "year"], how="left")
	merged = merged.dropna(subset=["population", "persons_per_dwelling", "saturation", "share", "intensity"])

	def map_fuel(tech: str) -> str:
		fuel_map = {
			"Electric Stoves": "Electricity",
			"Natural Gas Stoves": "Natural Gas",
			"LPG Stoves": "LPG",
			"Kerosene Stoves": "Kerosene",
			"Traditional Biomass Stoves": "Traditional Biomass",
		}
		for key, val in fuel_map.items():
			if key in tech:
				return val
		return "Unknown"

	merged["fuel"] = merged["tech"].map(map_fuel)
	merged["dwellings"] = merged["population"] / merged["persons_per_dwelling"]
	merged = merged.replace([np.inf, -np.inf], np.nan)
	merged = merged.dropna(subset=["dwellings"])
	merged["final_energy_demand_kwh"] = (
		merged["dwellings"] * merged["saturation"] * merged["share"] * merged["intensity"]
	)
	merged["final_energy_demand_twh"] = merged["final_energy_demand_kwh"] / 1e9
	merged["end_use"] = "Cooking"

	return merged[["country", "scenario", "year", "end_use", "tech", "fuel", "final_energy_demand_kwh", "final_energy_demand_twh"]]


def compute_appliances_demand(df: pd.DataFrame) -> pd.DataFrame:
	df_long = prepare_long_df(df)

	pop = get_metric_series(df_long, "Population")
	ppd = get_metric_series(df_long, "Persons per Dwelling")
	saturation = get_metric_series(df_long, "Saturation of Appliances")
	intensity_series = get_cagr_adjusted_intensity(
		df_long,
		"Final Energy Intensity of Electrical Appliances",
		"Electrical Appliances",
		INTENSITY_APPLIANCES,
	)
	tech_frame = intensity_series.rename("intensity").reset_index()
	tech_frame["tech"] = "Electrical Appliances"
	tech_frame["share"] = 1.0

	base = pd.concat(
		[
			pop.rename("population"),
			ppd.rename("persons_per_dwelling"),
			saturation.rename("saturation"),
		],
		axis=1,
	).reset_index()

	merged = tech_frame.merge(base, on=["country", "scenario", "year"], how="left")
	merged = merged.dropna(subset=["population", "persons_per_dwelling", "saturation", "intensity"])

	merged["fuel"] = "Electricity"
	merged["dwellings"] = merged["population"] / merged["persons_per_dwelling"]
	merged = merged.replace([np.inf, -np.inf], np.nan)
	merged = merged.dropna(subset=["dwellings"])
	merged["final_energy_demand_kwh"] = (
		merged["dwellings"] * merged["saturation"] * merged["share"] * merged["intensity"]
	)
	merged["final_energy_demand_twh"] = merged["final_energy_demand_kwh"] / 1e9
	merged["end_use"] = "Electrical Appliances"

	return merged[["country", "scenario", "year", "end_use", "tech", "fuel", "final_energy_demand_kwh", "final_energy_demand_twh"]]


def main():
	if not residential_config_path.exists():
		raise FileNotFoundError(f"Input file not found: {residential_config_path}")

	df = pd.read_csv(residential_config_path)
	df_space_heating = compute_space_heating_demand(df)
	df_space_cooling = compute_space_cooling_demand(df)
	df_water_heating = compute_water_heating_demand(df)
	df_cooking = compute_cooking_demand(df)
	df_appliances = compute_appliances_demand(df)

	output_dir = Path(__file__).resolve().parent / "output_data"
	output_dir.mkdir(parents=True, exist_ok=True)
	final_df = pd.concat(
		[df_space_heating, df_space_cooling, df_water_heating, df_cooking, df_appliances],
		ignore_index=True,
	)
	final_df.to_csv(output_dir / "final_energy_demand_all_end_uses.csv", index=False)


if __name__ == "__main__":
	main()


