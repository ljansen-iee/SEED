from pathlib import Path
from typing import List

import pandas as pd
import pycountry
import sys

print("="*80)
print("STARTING PYPSA ENERGY DEMANDS GENERATION")
print("="*80)

# Add industry module to path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from industry.scripts.calculate_final_energy_demand import FinalEnergyCalculator


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


def export_industry_totals_by_scenario_year(
	industry_wide_df: pd.DataFrame,
	process_emissions_path: Path,
	output_dir: Path,
) -> List[Path]:
	"""
	Export industry totals in PyPSA format.
	
	- One CSV per scenario-year combination (e.g., industry_totals+bau+2030.csv)
	- Drop 'scenario' and 'year' columns
	- Add process emissions as a carrier row (same level as oil, gas, etc.)
	
	Args:
		industry_wide_df: Wide format energy demand DataFrame from industry
		process_emissions_path: Path to process_emissions_summary.csv
		output_dir: Output directory for PyPSA CSVs (root pypsa_input/)
	
	Returns:
		List of generated file paths
	"""
	print("\n" + "="*80)
	print("EXPORTING INDUSTRY_TOTAL FILES (scenario-year CSVs + process emissions)")
	print("="*80)
	
	output_dir = Path(output_dir)
	output_dir.mkdir(parents=True, exist_ok=True)
	
	# Load process emissions if available
	process_emissions_df = None
	if process_emissions_path and process_emissions_path.exists():
		process_emissions_df = pd.read_csv(process_emissions_path)
		print(f"\nLoaded process emissions: {len(process_emissions_df)} rows")
	else:
		print(f"\nWarning: Process emissions not found at {process_emissions_path}")
		print("  Generating CSVs without process emissions")
	
	generated_files = []
	
	# Get unique scenario-year combinations
	scenario_years = industry_wide_df[['scenario', 'year']].drop_duplicates().sort_values(['scenario', 'year'])
	
	for _, row in scenario_years.iterrows():
		scenario = row['scenario']
		year = int(row['year'])
		
		print(f"\nProcessing {scenario} {year}...")
		
		# Filter energy data for this scenario-year
		energy_data = industry_wide_df[
			(industry_wide_df['scenario'] == scenario) &
			(industry_wide_df['year'] == year)
		].copy()
		
		# Drop scenario and year columns
		energy_data = energy_data.drop(columns=['scenario', 'year'])
		
		# Add process emissions as a carrier row if available
		if process_emissions_df is not None:
			# Filter process emissions for this scenario-year
			pe_data = process_emissions_df[
				(process_emissions_df['scenario'] == scenario) &
				(process_emissions_df['year'] == year)
			].copy()
			
			if not pe_data.empty:
				# Pivot process emissions: sector columns with emissions values
				pe_pivot = pe_data.pivot_table(
					index='country',
					columns='sector',
					values='emissions_MtCO2',
					aggfunc='sum',
					fill_value=0
				).reset_index()

				# Normalize sector names between process emissions and industry-wide demand output.
				pe_sector_aliases = {
					'paper, pulp and printing': 'paper pulp and print',
				}
				pe_pivot = pe_pivot.rename(columns=pe_sector_aliases)
				
				# Add carrier column
				pe_pivot['carrier'] = 'process emissions'
				
				# Align columns with energy_data
				# Get all sector columns from energy_data
				sector_cols = [col for col in energy_data.columns if col not in ['country', 'carrier']]
				
				# Ensure process emissions has all sector columns
				for col in sector_cols:
					if col not in pe_pivot.columns:
						pe_pivot[col] = 0
				
				# Reorder columns to match energy_data
				pe_pivot = pe_pivot[['country', 'carrier'] + sector_cols]
				
				# Append process emissions row(s) to energy data
				energy_data = pd.concat([energy_data, pe_pivot], ignore_index=True)
				print(f"  Added process emissions: {len(pe_pivot)} rows")
	
		# Define custom carrier order for PyPSA compatibility
		carrier_order = ['oil', 'biomass', 'coal', 'electricity', 'gas', 'hydrogen', 
		                 'ammonia', 'steel', 'methanol', 'process emissions']
		
		# Convert carrier to categorical with custom order
		energy_data['carrier'] = pd.Categorical(
			energy_data['carrier'], 
			categories=carrier_order, 
			ordered=True
		)
		
		# Sort by country and carrier (using custom order)
		energy_data = energy_data.sort_values(['country', 'carrier'])
		
		# Generate filename: industry_total+{scenario}+{year}.csv
		scenario_slug = _scenario_slug(scenario)
		filename = f"industry_total+{scenario_slug}+{year}.csv"
		output_path = output_dir / filename
		
		# Save (skip if file is locked)
		try:
			energy_data.to_csv(output_path, index=False)
			generated_files.append(output_path)
			print(f"  Saved: {filename} ({len(energy_data)} rows)")
		except PermissionError:
			print(f"  ⚠️ SKIPPED: {filename} (file is open in another program)")
	for f in generated_files:
		print(f"  - {f.name}")

	return generated_files


# ============================================================================
# MAIN EXECUTION
# ============================================================================

# Define paths
project_root = Path(__file__).resolve().parent
residential_output_dir = project_root / 'residential' / 'output_data'
additional_output_dir = project_root / 'additional sectors' / 'output_data'
industry_root = project_root / 'industry'
output_dir = project_root / 'pypsa_input'

# ========== 1. ENERGY TOTALS (residential + transport + agriculture + services) ==========
print("\n1. Generating energy_total files...")
files = export_energy_totals_by_scenario_year(
	residential_output_dir=residential_output_dir,
	additional_output_dir=additional_output_dir,
	output_dir=output_dir,
)

for file_path in files:
	print(f"  Saved: {file_path.name}")

# ========== 2. INDUSTRY TOTALS ==========
print("\n2. Generating industry_total files...")

# Load industry data
config_path = industry_root / 'output_data' / 'CONFIG' / 'INDUSTRY_CONFIG.csv'
interim_dir = industry_root / 'output_data' / 'interim_data'
wide_format_path = industry_root / 'output_data' / 'final_energy_demand_detailed_sectors_wide.csv'
process_emissions_path = interim_dir / 'process_emissions_summary.csv'

print("  Recomputing industry data from config to avoid stale cached wide output...")

# Initialize calculator
calculator = FinalEnergyCalculator(config_path, interim_dir)

# Calculate
results_long = calculator.calculate_all_detailed_sectors(
	years=[2030, 2035, 2040, 2045, 2050],
	scenarios=['BAU', 'Progressive', 'Optimistic']
)

if results_long.empty:
	print("  Error: No industry results generated!")
	sys.exit(1)

# Convert to wide format
industry_wide_df = calculator.pivot_to_wide_format(results_long)

# Save for future use
industry_wide_df.to_csv(wide_format_path, index=False)
print(f"  Saved industry wide format: {wide_format_path.name}")

# Export industry totals
industry_files = export_industry_totals_by_scenario_year(
	industry_wide_df=industry_wide_df,
	process_emissions_path=process_emissions_path,
	output_dir=output_dir,
)

print("\n" + "="*80)
print("PYPSA INPUT GENERATION COMPLETE")
print("="*80)
print(f"\nGenerated {len(files)} energy_total files")
print(f"Generated {len(industry_files)} industry_total files")
print(f"\nAll outputs in: {output_dir}")
