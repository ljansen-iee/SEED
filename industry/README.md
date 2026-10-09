# Industry energy-demand model

Run the industry package from the repository root in the `sectoral-energy`
environment defined by [environment.yaml](../environment.yaml). The model uses
2020 as its base year and preserves the BAU, Progressive, and Optimistic
storylines and the default target years 2030, 2035, 2040, 2045, and 2050.

## Canonical workflow

1. `python -m industry.scripts.generate_industry_config`
2. `python -m industry.scripts.calculate_final_energy_demand`

The sole generated configuration is
[output_data/CONFIG/INDUSTRY_CONFIG.csv](output_data/CONFIG/INDUSTRY_CONFIG.csv).
The public generator is `generate_industry_config_csv`; the calculator is
`FinalEnergyCalculator`. There is no old wide-configuration compatibility API.
Package and script defaults resolve to the same canonical config, with no
version suffix. Paths derive from the installed script location, not a personal
filesystem path or an assumed current directory.

## Isolated validation

Choose an **external temporary directory** for smoke checks. Do not regenerate
tracked sector outputs just to test a change. For example, with `$temp` pointing
to that directory, pass these arguments to the package modules:

- Generator: `--countries Morocco Egypt "South Africa" Namibia --years 2030 2035 2040 2045 2050 --scenarios BAU Progressive Optimistic --output-path "$temp/CONFIG/INDUSTRY_CONFIG.csv" --interim-dir "$temp/interim_data"`.
- Calculator: `--config-file "$temp/CONFIG/INDUSTRY_CONFIG.csv" --interim-dir "$temp/interim_data" --output-dir "$temp/demand" --countries Morocco Egypt "South Africa" Namibia --years 2030 2035 2040 2045 2050 --scenarios BAU Progressive Optimistic`.

Quote multiword country names. Both modules expose `--help`. The generator also
accepts `--config-output` as a spelling of `--output-path`. When omitted,
`interim_dir` follows the selected config tree: beside the CONFIG directory, or
beside a custom config file outside CONFIG. The calculator's output directory
likewise follows the config tree unless explicitly supplied; an explicit output
directory supplies its default interim directory.

### Python API

`generate_industry_config_csv(countries, base_year=2020, target_years=None,
scenarios=None, output_path=None, interim_dir=None, generate_derivatives=True)`
returns the validated config DataFrame. Sector row builders do not write
derivatives; the central generator owns all derivative paths, including ammonia
volumes. Derivative exceptions propagate. `--config-only` (or
`generate_derivatives=False`) explicitly omits every derivative; it is not a
silent fallback after errors.

`FinalEnergyCalculator(config_path=INDUSTRY_CONFIG_PATH, interim_dir=None,
output_suffix='', refresh_interim=True, refresh_years=None,
refresh_scenarios=None, countries=None, unsd_dir=None)` loads the selected config.
The Python API infers projection dimensions from that config unless supplied.
CLI dimensions retain the full standard defaults, so pass `--years` and
`--scenarios` when calculating a subset config.

`calculate_all_detailed_sectors(years=None, scenarios=None)` calculates **all**
detailed and simple sectors, despite its historical method name. It returns
long-form demand; `pivot_to_wide_format` produces the sector-column table.
Country selection restricts config columns. Missing requested country columns,
required sector rows, intensities, or fuel-share dimensions fail explicitly.

The calculator always regenerates projections from the selected configuration,
never reads stale cached derivative files. `--no-refresh-interim` (or
`refresh_interim=False`) means **do not persist derivatives**: temporary files
are generated in OS temporary storage and removed. It does not create the
requested interim directory. `--output-suffix` applies only to calculator
outputs/reports and is normalized to an underscore-prefixed filename suffix.

## Configuration contract and source data

Leading columns are `metric_1`, `metric_2`, `metric_3`, `metric_4`, `year`,
`scenario`, `units`, followed by full country names. Keys comprise all six
dimensions excluding units. Duplicate keys, blank required identifiers/units,
missing country values, invalid scenarios, non-finite values, and inconsistent
units fail validation. A blank `metric_4` is allowed outside fuel-share rows.
There is no implicit `default` country column.

- Physical production: `t/a`; aluminium source `100t/a` is explicitly converted.
- Base route intensity: `MWh/t` (supported `MWh/100t` is explicitly converted).
- Technology and fuel shares: fractions in `[0, 1]`, not percentages. Nonzero
  fuel groups and hierarchical route groups must sum to one within rounding
  tolerance. Genuine zero-consumption fuel groups remain zero.
- CAGR: decimal annual rates in units `share`, with interval keys such as
  `2020-2030`; non-CAGR rows use individual four-digit years.
- Simple-sector historical energy: `MWh`, year 2020, scenario `all`.
- Unspecified NMM activity placeholders retain production units
  `activity_factor`; zero placeholders do not become phantom energy demand.

Required production datasets reside under industry input_data: Worldsteel and
GEM steel, UNdata ammonia, the petrochemical industrial database, FAOSTAT paper
and pulp, BGS aluminium, and country USGS cement workbooks. Their absence is
reported before generation writes anything. Simple-sector inputs require the
exact base-year sector row in root UNSD data named
`UNSD_{Country}-2020.csv`, including the transaction and Total Energy columns.
Source placeholders retain the established cleaning convention; missing files
or missing sector identifiers are not treated as zero consumption. Existing
documented production/CAGR assumptions and country-data fallbacks in detailed
sector builders are otherwise unchanged. Generation does not read cached
industry outputs, alter hosted data sources, or weaken SSL verification.

Simple-sector calculations normally use the historical-energy rows embedded in
the selected config, so they do not silently re-read another input tree. An
explicit `--unsd-dir`/`unsd_dir` replaces only their base-energy input with exact
UNSD base-year rows; it does not regenerate the configured fuel mix or CAGR.

## Covered sectors

Detailed sectors are iron and steel, chemical and petrochemical (ammonia and
HVC), non-metallic minerals (cement/clinker), paper/pulp/printing, and non-ferrous
metals (aluminium). Ammonia and HVC use separate route sets within their shared
sector and aggregate once.

Simple sectors are food and tobacco, construction, machinery, mining and
quarrying, textile and leather, transport equipment, wood and wood products,
and other industries. The UNSD/config construction key
`manufacturing  const. and mining` maps to output `construction`; UNSD Industry
n.e.s maps to config/output `other`. Simple-sector energy uses base MWh,
configured activity CAGR, the existing scenario efficiency assumptions
(-1%, -2%, -3% annually), and configured fuel shares.

## Outputs and units

Generator derivatives include steel/ammonia intensity projections,
steel/ammonia pathway volumes, CAGR reports, and process-emission review
reports. All follow `interim_dir`. Process-emission readiness/provenance is
owned by the process-emissions module; successful demand generation does **not**
mean those provisional factors are accepted for final export.

Calculator outputs are the detailed-sector long and wide demand CSVs under the
selected output directory. The long table contains `country`, `scenario`,
`year`, `carrier`, `energy_MWh`, and `sector`; the wide table uses sector columns.
Zero-production sectors may have no long records but still appear in wide
output as zero columns.

**Unit exception:** ordinary carriers and endogenous ammonia are in MWh;
the endogenous `steel` carrier stores **tonnes**, despite the shared legacy
`energy_MWh` field name. Never sum this carrier with energy carriers. Steel
volume derivatives use tonnes; endogenous ammonia uses 5.17 MWh per tonne.
Root export/aggregation is a separate stage and must enforce its own conversion
and process-emission acceptance contracts.

## Focused checks

Compile changed Python modules with bytecode redirected outside the repository,
run both module help commands, then generate one country into an external tree
and calculate from that exact config. Check dimension uniqueness, all requested
years/scenarios, finite nonnegative demand, construction/other coverage,
zero-sector columns, and explicit errors for missing input rows. Broaden to
the default four countries only after that focused check passes.# Industry Sector Energy Demand Model

This module calculates final energy demand projections for the industrial sector across multiple countries and scenarios (BAU, Progressive, Optimistic) from a base year (2020) to target years (2030-2050).

---

## Table of Contents

1. [Overview](#overview)
2. [Industrial Subsectors](#industrial-subsectors)
3. [Model Workflow](#model-workflow)
4. [Quick Start](#quick-start)
5. [Configuration Files](#configuration-files)
6. [Adding a New Country](#adding-a-new-country)
7. [Customizing Parameters](#customizing-parameters)
8. [Output Files](#output-files)
9. [File Structure](#file-structure)
10. [Troubleshooting](#troubleshooting)

---

## Overview

The industry model uses a bottom-up approach combining physical production data with energy intensities and fuel shares to calculate energy demand. The model covers:

- **Production volumes** (tons/year for steel, cement, paper, chemicals)
- **Process/technology shares** (e.g., BF-BOF vs DR-EAF for steel)
- **Fuel shares** (electricity, gas, coal, oil, hydrogen, biomass, etc.)
- **Energy intensities** (MWh per ton of product)
- **Activity factors** for unspecified subsectors

The model supports three scenarios:
| Scenario | Description |
|----------|-------------|
| **BAU** | Business As Usual - continuation of current trends |
| **Progressive** | Moderate decarbonization with gradual technology shifts |
| **Optimistic** | Aggressive decarbonization with rapid electrification and hydrogen adoption |

---

## Industrial Subsectors

The model covers the following industrial subsectors:

### Energy-Intensive Industries (Bottom-Up Modeling)

| Subsector | Processes/Products Modeled |
|-----------|---------------------------|
| **Iron & Steel** | BF+OHF, BF+BOF, DR+EAF, Scrap EAF, Casting/Rolling/Finishing |
| **Non-Metallic Minerals** | Cement production, Clinker, Unspecified NMM |
| **Paper & Pulp** | Primary pulp, Secondary pulp, Paper production |
| **Chemicals & Petrochemicals** | Ammonia (SMR-HB, Renewable), HVC (Naphtha, LPG, Methanol cracking) |

### Other Industries (Top-Down UNSD Data)

| Subsector | Data Source |
|-----------|-------------|
| Food & Tobacco | UNSD historical data + CAGR projections |
| Non-Ferrous Metals | UNSD historical data + CAGR projections |
| Mining & Quarrying | UNSD historical data + CAGR projections |
| Machinery | UNSD historical data + CAGR projections |
| Transport Equipment | UNSD historical data + CAGR projections |
| Textile & Leather | UNSD historical data + CAGR projections |
| Wood & Wood Products | UNSD historical data + CAGR projections |
| Construction | UNSD historical data + CAGR projections |

---

## Model Workflow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              MODEL WORKFLOW                                  │
└─────────────────────────────────────────────────────────────────────────────┘

  STEP 1: Generate Configuration
  ══════════════════════════════
  Run: python -m industry.build_config_industry
  
       ┌──────────────────────────┐         ┌─────────────────────────────┐
       │   Input Data             │         │   industry_config.csv       │
       │   - Steel capacity       │         │   (CAGR values for 2030-50) │
       │   - UNSD energy data     │ ──────► │                             │
       │   - Production databases │         └─────────────────────────────┘
       │   - IEA/SSP scenarios    │                      │
       └──────────────────────────┘                      ▼
                                        ┌─────────────────────────────┐
                                        │   country_parameters/       │
                                        │   {Country}_Output_.csv     │
                                        │   (Base year 2020 values +  │
                                        │    projected values for all │
                                        │    metrics by scenario)     │
                                        └─────────────────────────────┘

  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
  
  OPTIONAL: User Modifications
  ════════════════════════════
  - Edit industry_config.csv to change CAGR values for future projections
  - Edit {Country}_Output_.csv in country_parameters/ to change 2020 base 
    values or any projected values

  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─

  STEP 2: Calculate Final Energy Demand
  ═════════════════════════════════════
  Run: python -m industry.build_final_energy_demand
  
       ┌─────────────────────────────┐
       │   country_parameters/       │
       │   {Country}_Output_.csv     │
       └─────────────────────────────┘
                    │
                    ▼
       ┌─────────────────────────────────────────────────────────────────┐
       │                    OUTPUTS GENERATED                             │
       ├─────────────────────────────────────────────────────────────────┤
       │  unsdata_historical/{Country}/                                     │
       │    ├── {ISO}_final_energy_demand.xlsx  (detailed demand)        │
       │    ├── {ISO}_energy_demand_summary.xlsx (summary by carrier)    │
       │    └── output_{Country}_updated.csv    (updated parameters)     │
       ├─────────────────────────────────────────────────────────────────┤
       │  output_data/                                                    │
       │    ├── industry_all_2020.csv           (all countries base yr)  │
       │    ├── industry_BAU_{year}.csv         (BAU scenario by year)   │
       │    ├── industry_Progressive_{year}.csv                          │
       │    └── industry_Optimistic_{year}.csv                           │
       └─────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Prerequisites

- Python 3.8+
- Required packages: `pandas`, `numpy`, `pycountry`, `openpyxl`
- Install dependencies: `pip install -r requirements.txt` (or use `environment.yaml`)

### Running the Model

**Always run from the repository root directory** (the folder containing `transport/`, `industry/`, `residential/`, etc.)

```bash
# Step 1: Generate configuration and country parameters
python -m industry.build_config_industry

# Step 2: Calculate final energy demand
python -m industry.build_final_energy_demand
```

---

## Configuration Files

### 1. `industry_config.csv` - Future Projections (CAGR Values)

This file controls how parameters change from the base year to future years. It is **auto-generated** on the first run but can be manually edited.

**Structure:**
```
Metric Name                              | Year | Scenario    | default | Morocco | Egypt | ...
Steel production per year               | 2030 | BAU         | 0.01    | 0.02    | 0.015 | ...
Steel production per year               | 2030 | Progressive | 0.01    | 0.02    | 0.015 | ...
Share of hydrogen for DR+EAF            | 2050 | Optimistic  |         | 82.0    |       | ...
```

**Key Columns:**
- **Metric Name**: The parameter being projected
- **Year**: Target year (2030, 2035, 2040, 2045, 2050)
- **Scenario**: BAU, Progressive, or Optimistic
- **Country columns**: CAGR or target values specific to each country

### 2. `country_parameters/{Country}_Output_.csv` - Complete Parameter Set

These files contain the **complete parameter set** for each country, including:
- Base year (2020) values
- Projected values for all scenarios and target years

**Structure:**
```
Metric                                                    | 2020      | 2030_BAU | 2030_Progressive | ... | Units
Steel production per year                                | 1000000.0 | 1100000  | 1050000          | ... | tons/y
Share of primary steel                                   | 80.0      | 80.0     | 77.5             | ... | % of steel production
Share of blast furnace + basic oxygen furnace            | 0.0       | 14.0     | 7.0              | ... | % of primary steel
Share of hydrogen for direct reduction + electric arc    | 0.0       | 0.0      | 82.0             | ... | % of DR + EAF
Energy intensity of electricity in DR+EAF                | 2.87      | 2.87     | 2.84             | ... | MWh/t
```

**Categories of Metrics:**

| Category | Examples | Units |
|----------|----------|-------|
| **Production** | Steel/Cement/Paper/Ammonia/HVC production per year | tons/y |
| **Process Shares** | Share of BF+BOF, DR+EAF, primary pulp | % of production |
| **Fuel Shares** | Share of electricity/gas/coal/hydrogen for process | % of process |
| **Energy Intensities** | Energy intensity of fuel in process | MWh/t |
| **Activity Factors** | Activity factor for unspecified sectors | dimensionless |

---

## Adding a New Country

### Step 1: Add Country to the Countries List

Edit `build_config_industry.py` and add the new country to `countries_to_process`:

```python
countries_to_process = [
    "Morocco", 
    "Egypt", 
    "South Africa",
    "NewCountry"  # ← Add your new country here
]
```

Also update the list in `build_final_energy_demand.py`:

```python
available_countries = [
    "Morocco", 
    "Egypt", 
    "South Africa",
    "NewCountry"  # ← Add here too
]
```

### Step 2: Ensure Input Data Exists

The model requires input data for each country:

1. **UNSD Energy Data** (`input_data/unsdata_historical/{Country}/`)
   - Historical energy consumption by subsector
   - Fuel shares for each sector

2. **Steel Capacity Data** (in `input_data/steel/`)
   - Furnace capacities by type (BOF, EAF, OHF)

3. **Production Data**
   - Cement production (in `input_data/cement/`)
   - Paper & pulp production (in `input_data/paper_and_pulp/`)
   - Chemical production (in `input_data/petrochemicals/`)

### Step 3: Add Country Column to `industry_config.csv` (Optional)

If you want country-specific CAGR values different from defaults:

```csv
Metric Name,Year,Scenario,default,Morocco,Egypt,NewCountry
Steel production per year,2030,BAU,0.01,0.02,0.015,0.025
```

### Step 4: Run the Model

```bash
# Generate configuration for all countries including the new one
python -m industry.build_config_industry

# Calculate energy demand
python -m industry.build_final_energy_demand
```

---

## Customizing Parameters

### Modifying Future Projections (2030-2050)

**Edit `industry_config.csv`:**

1. Open the file in Excel or a text editor
2. Find the metric you want to change
3. Modify the CAGR or target value for the appropriate Year/Scenario/Country
4. Save the file
5. Run `python -m industry.build_config_industry` to regenerate country parameters
6. Run `python -m industry.build_final_energy_demand` to recalculate

**Example: Increase hydrogen share for DR+EAF in Morocco by 2050**
```csv
Share of hydrogen for direct reduction + electric arc furnace,2050,Optimistic,82.0,90.0,,
```

### Modifying Base Year Values (2020)

**Edit `output_data/country_parameters/{Country}_Output_.csv`:**

1. Open the file for your target country
2. Find the metric in the `Metric` column
3. Edit the value in the `2020` column
4. Save the file
5. Run `python -m industry.build_final_energy_demand` to recalculate

**Example: Change Morocco's 2020 steel production**
```csv
Metric,2020,...
Steel production per year,1200000.0,...   # Changed from 1000000
```

### Modifying Technology/Process Shares

Process and fuel shares must sum to 100% within each group:

**Steel Production Routes (must sum to 100% of primary steel):**
- Share of BF + OHF
- Share of BF + BOF  
- Share of DR + EAF

**Fuel Shares for Each Process (must sum to 100%):**
- Diesel + Natural Gas + Electricity + Coal + Heat + Biomass + Hydrogen = 100%

The model will use your specified values directly without normalization, so ensure they sum correctly.

---

## Output Files

### Per-Country Outputs (`output_data/unsdata_historical/{Country}/`)

| File | Description |
|------|-------------|
| `{ISO}_final_energy_demand.xlsx` | Detailed energy demand by sector, process, technology, and fuel |
| `{ISO}_energy_demand_summary.xlsx` | Summary tables by energy carrier (oil, gas, electricity, etc.) |
| `output_{Country}_updated.csv` | Updated parameter file with any modifications |

### Aggregated Outputs (`output_data/`)

| File | Description |
|------|-------------|
| `industry_all_2020.csv` | Base year energy demand for all countries |
| `industry_{Scenario}_{Year}.csv` | Energy demand by scenario and year for all countries |

**Scenarios:** BAU, Progressive, Optimistic  
**Years:** 2030, 2035, 2040, 2045, 2050

---

## File Structure

```
industry/
├── README.md                      # This file
│
├── build_config_industry.py       # MAIN SCRIPT 1: Generate configuration
├── build_final_energy_demand.py   # MAIN SCRIPT 2: Calculate energy demand
│
├── industry_config.csv            # Configuration file (auto-generated)
│
├── helpers.py                     # Utility functions
├── build_CAGR.py                  # CAGR calculation and config loading
│
├── scripts/                       # Subsector-specific calculations
│   ├── iron_and_steel/
│   │   ├── build_steel_production.py
│   │   ├── build_shares_steel.py
│   │   └── build_energy_intensities_steel.py
│   │
│   ├── non_metallic_minerals/
│   │   ├── build_cement_production.py
│   │   ├── build_shares_cement.py
│   │   └── build_energy_intensities_cement.py
│   │
│   ├── paper_and_pulp/
│   │   ├── build_paper_and_pulp_production.py
│   │   ├── build_share_primary_pulp.py
│   │   └── build_energy_intensities_paper_pulp.py
│   │
│   ├── chemical_and_petrochemical/
│   │   ├── ammonia/
│   │   │   ├── build_ammonia.py
│   │   │   ├── build_shares_ammonia.py
│   │   │   └── build_intensities_ammonia.py
│   │   └── HVC/
│   │       └── build_hvc_production.py
│   │
│   ├── food_and_tobacco/
│   ├── non_ferrous_metals/
│   ├── mining_and_quarrying/
│   ├── machinery/
│   ├── transport_equipment/
│   ├── textile_and_leather/
│   ├── wood_and_wood_products/
│   ├── construction/
│   └── other_industries/
│
├── input_data/                    # Input data files
│   ├── unsdata_historical/          # UNSD data per country
│   │   ├── Morocco/
│   │   ├── Egypt/
│   │   └── ...
│   ├── steel/                     # Steel capacity databases
│   ├── cement/                    # Cement production data
│   ├── paper_and_pulp/            # Paper & pulp data
│   └── petrochemicals/            # Chemical production data
│
└── output_data/                   # Output files
    ├── country_parameters/        # Per-country parameter files
    │   ├── Morocco_Output_.csv
    │   ├── Egypt_Output_.csv
    │   └── South Africa_Output_.csv
    │
    ├── unsdata_historical/          # Per-country detailed outputs
    │   ├── Morocco/
    │   │   ├── MA_final_energy_demand.xlsx
    │   │   └── MA_energy_demand_summary.xlsx
    │   ├── Egypt/
    │   └── South_Africa/
    │
    ├── industry_all_2020.csv      # Aggregated base year
    ├── industry_BAU_2030.csv      # Aggregated by scenario/year
    ├── industry_Progressive_2030.csv
    └── industry_Optimistic_2030.csv
```

---

## Troubleshooting

### Common Issues

**1. ModuleNotFoundError: No module named 'industry'**
- **Solution:** Run from the repository root, not from inside the `industry/` folder
```bash
cd path/to/sectoral-energy-demands
python -m industry.build_config_industry
```

**2. Missing UNSD data for country**
- **Cause:** The country doesn't have historical energy data in `input_data/unsdata_historical/`
- **Solution:** Add UNSD energy balance data for the country, or the model will use defaults/zeros

**3. Steel capacity data not found**
- **Cause:** Country not in the steel capacity database
- **Solution:** The model will use production ratios from similar countries or default assumptions

**4. Fuel shares don't sum to 100%**
- **Cause:** Manual edits introduced inconsistencies
- **Solution:** Ensure all fuel shares for each process sum to 100%

**5. industry_config.csv is missing**
- **Solution:** Run `python -m industry.build_config_industry` to generate it

### Key Data Sources

The model relies on several data sources:
- **UNSD Energy Statistics** - Historical energy consumption by sector
- **World Steel Association** - Steel production and capacity data
- **USGS / Global Cement Report** - Cement production data
- **IEA / FAO** - Paper & pulp production
- **IFA / Ammonia Industry** - Ammonia production capacity
- **SSP Database** - Scenario growth trajectories

---

## Energy Carriers Tracked

The model tracks the following energy carriers:

| Carrier | Description |
|---------|-------------|
| Oil/Diesel | Petroleum products |
| Natural Gas | Pipeline and LNG |
| Electricity | Grid electricity |
| Coal | All coal types |
| Heat | District/process heat |
| Biomass | Solid biomass, biogas |
| Hydrogen | Green/blue hydrogen |
| Ammonia | As energy carrier |
| Methanol | As energy carrier |
| Steel | Scrap/feedstock energy content |

---

## Contact

For questions or issues, please open an issue in the repository or contact the development team.

---

*Last updated: March 2026*
