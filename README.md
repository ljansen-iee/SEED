# Sectoral Energy Demands

> Bottom-up final energy demand forecasting tool for 30+ countries, developed at
> [Fraunhofer IEE](https://www.iee.fraunhofer.de/) as part of the projects
>  [DeV-KopSys-2](https://www.iee.fraunhofer.de/de/projekte/suche/2021/dev-kopsys-2.html) and [H2Global meets Africa](https://www.iee.fraunhofer.de/en/research_projects/search/2024/h2global-africa.html).

The tool projects sectoral final energy consumption from a base year (~2018–2023)
to 2030–2050 under multiple policy scenarios.  Outputs are structured for direct
ingestion by energy system models such as
[PyPSA-Earth](https://github.com/pypsa-meets-earth/pypsa-earth).

This documentation was created with the help of AI and is in development.

---

## Table of Contents

1. [Project Purpose & Context](#project-purpose--context)
2. [Architecture Overview](#architecture-overview)
3. [Common Pipeline Pattern](#common-pipeline-pattern)
4. [Sector Modules](#sector-modules)
   - [Transport](#transport)
   - [Residential](#residential)
   - [Additional Sectors](#additional-sectors)
   - [Industry (planned)](#industry-planned)
5. [Environment Setup](#environment-setup)
6. [Running the Tool](#running-the-tool)
7. [Input Data & Configuration](#input-data--configuration)
8. [Output Format](#output-format)
9. [Visualisation Notebooks (plots/)](#visualisation-notebooks-plots)
10. [Root-Level Scripts](#root-level-scripts)
11. [Known Limitations & Work in Progress](#known-limitations--work-in-progress)
12. [License](#license)

---

## Project Purpose & Context

Many integrated energy system models (e.g. PyPSA-Earth) require exogenous
projections of final energy demand broken down by sector, fuel, and technology.
Existing global datasets are often too aggregated or rely on proprietary
assumptions.

**Sectoral Energy Demands** fills this gap by:

- Computing base-year energy balances from **UN Statistics Division (UNSD)**
  energy-balance CSVs (2011–2023, ~34 countries).
- Applying country- and scenario-specific **Compound Annual Growth Rates
  (CAGRs)** at milestone years (2030, 2040, 2050) with linear interpolation
  in between.
- Decomposing demand through a hierarchy of **activity levels, technology
  shares, fuel shares, and energy intensities** — the core formula being:

$$
\text{FED} = \text{Activity Level} \times \text{Technology Share} \times \text{Fuel Share} \times \text{Energy Intensity}
$$

The result is a set of per-country, per-scenario CSV/Excel files that can be
fed directly into PyPSA or analysed with the included Jupyter notebooks.

---

## Architecture Overview

```
sectoral-energy-demands/
│
├── transport/                  # Transport mode & technology energy demand
├── residential/                # Residential end-use energy demand
├── additional sectors/         # Agriculture, Services, Non-energy, Other
├── data/country_specific/      # UNSD energy-balance CSVs (34 countries × 13 years)
├── plots/                      # Post-processing Jupyter notebooks
│
├── build_CAGR.py               # Cross-sector CAGR computation from UNSD data
├── build_shares.py             # Cross-sector fuel-share computation from UNSD data
├── build_pypsa_energy_totals.py# Merges residential + additional sectors → PyPSA energy_totals
├── build_pypsa_industry.py     # (placeholder) Industry → PyPSA integration
│
└── environment.yaml            # Conda environment specification
```

Each **sector module** is self-contained with its own `input_data/`, build
scripts, helpers, and an entry-point script.  Shared UNSD parsing logic lives
in the root `build_shares.py` and is reused by `build_CAGR.py` and the
additional-sectors module.

---

## Common Pipeline Pattern

Every sector follows the same four-stage pipeline:

```
┌─────────────┐    ┌──────────────────┐    ┌───────────────────┐    ┌──────────────┐
│ 1. Load      │───▶│ 2. Build base-   │───▶│ 3. Apply CAGR &   │───▶│ 4. Assemble  │
│    input data│    │    year metrics   │    │    scenario proj.  │    │    & export   │
└─────────────┘    └──────────────────┘    └───────────────────┘    └──────────────┘
```

| Stage | What happens | Key scripts |
|-------|-------------|-------------|
| **1 — Load** | Read country-specific CSVs (SSP projections, UNSD balances), global reference datasets (Khalili 2019, OECD, World Bank, UNDESA), and configuration files. | `helpers.py` in each module |
| **2 — Build** | One `build_*.py` script per dimension: activity/production, technology shares, energy intensities, fuel shares, saturation rates, load factors. | `build_macro_indicators.py`, `build_technology_share*.py`, `build_energy_intensities.py`, etc. |
| **3 — Project** | `build_CAGR.py` defines CAGRs at anchor years; growth is chained and linearly interpolated between milestones. Multiple scenarios (e.g. *Baseline*, *Moderate*, *Advanced*) produce diverging trajectories. | `build_CAGR.py` in each module |
| **4 — Export** | The entry-point script loops over all countries, combines metrics, and writes output CSVs or Excel workbooks. A separate `build_final_energy_demand.py` then decomposes outputs into a full Sub-sector → Mode → Technology → Fuel hierarchy. | `main_transport.py`, `build_residential_config.py`, `build_final_energy_demand.py` |

---

## Sector Modules

### Transport

**Entry point:** `transport/main_transport.py`

Decomposes transport demand by **mode × vehicle type × technology × fuel**:

| Dimension | Categories |
|-----------|-----------|
| Mode | Road, Rail, Aviation, Marine (domestic + international) |
| Vehicle type | LDV, Bus, 2-&-3-Wheeler, HDT, LDT, Passenger/Freight Train, Ship, Plane |
| Technology | ICE, BEV, FCEV, PHEV (plug-in hybrid), Biofuel blends |
| Fuel | Gasoline, Diesel, Electricity, Hydrogen, Biofuels, LNG, Kerosene |

**Build scripts:**

| Script | Purpose |
|--------|---------|
| `build_macro_indicators.py` | Population & GDP from SSP projections |
| `build_share_subsectors.py` | Passenger/freight splits from Khalili 2019 data |
| `build_share_mode.py` | Bus / 2-&-3-Wheeler / LDV road-mode shares |
| `build_load_factors.py` | Passengers-per-vehicle / tonnes-per-vehicle (Khalili 2019) |
| `build_technology_share.py` | ICE/BEV/FCEV shares from OECD data + config overrides |
| `build_energy_intensities.py` | Base-year kWh/vkm by vehicle-technology pair |
| `build_CAGR.py` | CAGR loading from Excel compilation, polynomial regression, piecewise expansion |
| `build_final_energy_demand.py` | Converts parameter CSVs → GWh final demand by fuel/mode/technology |
| `helpers.py` | I/O, constants, metric ordering, validation, config loading |

**Configuration:** `trans_config.csv` — per-country overrides for base year,
growth pathway, CAGR sources, technology-share targets, and scenario names.

**Data dependencies:**
- `input_data/global/` — `CAGR.csv`, `international_marine_and_aviation_data.xlsx`,
  Khalili 2019 supplementary data, `OECD.Stat-EEI_TRANSPORT.csv`
- `input_data/country_specific/` — SSP population/GDP CSVs, UNSD energy-balance CSVs
- `data/country_specific/` (root) — additional UNSD balance files

---

### Residential

**Entry point:** `residential/build_residential_config.py`

Models five residential end-uses, each driven by:

$$
\text{FED}_{\text{end-use}} = \text{Population} \times \frac{\text{Floor area}}{\text{Person}} \times \text{Saturation rate} \times \text{Technology share} \times \text{Energy intensity}
$$

(Water heating, cooking, and appliances use *dwellings* instead of floor area.)

| End-Use | Saturation Driver | Intensity Unit |
|---------|-------------------|---------------|
| Space Heating | Fixed scenario assumptions | kWh / m² |
| Space Cooling | GDP-based regression | kWh / m² |
| Water Heating | Fixed scenario assumptions | kWh / dwelling |
| Cooking | World Bank clean-cooking access | kWh / dwelling |
| Electrical Appliances | World Bank electricity access | kWh / dwelling |

**Build scripts:**

| Script | Purpose |
|--------|---------|
| `build_macro_indicators.py` | Population, GDP/capita, floor area/person, persons/dwelling (SSP + World Bank + UNDESA) |
| `build_saturation_rates.py` | End-use saturation projections (regression, scenario assumptions, access data) |
| `build_technology_shares.py` | Heating/cooking fuel mix from UNSD shares + World Bank survey data |
| `build_energy_intensities.py` | Technology-level intensity constants (13 heating technologies, 5 cooking, 2 cooling, 1 appliance) |
| `build_CAGR.py` | Sub-regional CAGR weighting (Africa by investment share, LATAM by IEA scenarios) |
| `build_final_energy_demand.py` | Aggregates per-end-use demand → fuel-level totals, exports per-scenario/year CSVs |
| `helpers.py` | I/O, constants, metric-to-unit mapping, config loading |

**Data dependencies:**
- `input_data/country_specific/` — SSP population/GDP CSVs, UNSD energy-balance CSVs (base year only)
- `input_data/global/` — World Bank income classification, GDP per capita, floor-area regressions,
  UNDESA household-size data, World Bank electricity/cooking access, residential cooking-fuel PDF

**Configuration:** Scenarios are defined in code inside `build_residential_config.py`
(variables `SCENARIOS`, `SSP_ORDER`, `BASE_YEAR`, `GROWTH_PATHWAY`). Only CAGR
values for final energy intensity can currently be overridden via the output CSV;
absolute intensity values are hard-coded.

> **Note:** The residential module is the least mature and is under active
> development. See [Known Limitations](#known-limitations--work-in-progress).

---

### Additional Sectors

**Entry point:** `additional sectors/build_add_sectors_demand.py`

Covers four non-core sectors that are not modelled with a full bottom-up
decomposition but are projected from historical UNSD totals:

| Sector | UNSD Label |
|--------|-----------|
| Agriculture | Agriculture forestry and fishing |
| Services | Commerce and public services |
| Non-energy use | Non-energy use |
| Other | Other consumption n.e.s |

The pipeline:
1. Reads pre-computed **fuel shares** (from root `build_shares.py`) and **CAGRs**
   (from root `build_CAGR.py`).
2. Extracts base-year total energy per sector from UNSD data.
3. Multiplies totals by fuel shares and grows them using CAGR.
4. Exports one CSV per sector: `{sector}_fuel_demand_history_future.csv`.

---

### Industry (planned)

An `industry/` module is referenced in the `.gitignore` and in the
visualisation notebooks but **is not yet present** in this branch. The root
file `build_pypsa_industry.py` exists as an empty placeholder.

Industry sub-sectors envisioned (visible in `build_CAGR.py`):

- Iron and steel
- Chemical and petrochemical
- Non-metallic minerals (Cement)
- Paper, pulp and printing
- Food and tobacco
- Non-ferrous metals
- Machinery
- Mining and quarrying
- Construction
- Textile and leather
- Transport equipment
- Wood and wood products

---

## Environment Setup

The project uses a **Conda** environment defined in `environment.yaml`.

```bash
# 1. Clone the repository
git clone <repo-url> sectoral-energy-demands
cd sectoral-energy-demands

# 2. Create and activate the Conda environment
conda env create -f environment.yaml
conda activate sectoral-energy

# 3. Verify
python --version   # Should print Python 3.10.x
```

<details>
<summary>Key dependencies</summary>

| Package | Version | Purpose |
|---------|---------|---------|
| python | 3.10.19 | Runtime |
| pandas | 2.3.3 | Data manipulation |
| numpy | 2.2.5 | Numerics |
| scipy | 1.15.3 | Regression / interpolation |
| matplotlib | 3.10.7 | Plotting |
| openpyxl | 3.1.5 | Excel reading |
| xlsxwriter | 3.2.9 | Excel writing |
| geopandas | latest | Geospatial operations |
| pycountry | 24.6.1 | ISO country-code lookups |
| tabula | 1.0.5 | PDF table extraction (residential cooking data) |
| jupyterlab | 4.5.2 | Notebook interface |

</details>

---

## Running the Tool

### Prerequisite: Build Cross-Sector Shares & CAGRs

Several modules depend on pre-computed fuel shares and CAGR CSVs produced by
the root-level scripts.  Run these **first**:

```bash
# From the repository root
python build_shares.py      # → output_data/interim/shares/
python build_CAGR.py        # → output_data/interim/cagr/
```

### Transport

```bash
# Step 1 — Build per-country parameter CSVs
python transport/main_transport.py
# → transport/output_data/country_parameters/{Country}_transport_params.csv

# Step 2 — Compute final energy demand (GWh) and PyPSA indicators
python transport/build_final_energy_demand.py
# → transport/output_data/  (per-country + aggregated CSVs)
```

### Residential

```bash
# Step 1 — Build combined parameter CSV
python residential/build_residential_config.py
# → residential/output_data/parameters_all_countries.csv

# Step 2 — Compute final energy demand and export per-scenario/year files
python residential/build_final_energy_demand.py
# → residential/output_data/  (per-scenario/year CSVs)
```

### Additional Sectors

```bash
# Requires build_shares.py and build_CAGR.py outputs to exist
python "additional sectors/build_add_sectors_demand.py"
# → additional sectors/output_data/  ({sector}_fuel_demand_history_future.csv)
```

### PyPSA Energy Totals (all sectors combined)

```bash
# Merges residential + additional sectors into scenario × year CSVs
python build_pypsa_energy_totals.py
# → output_data/energy_totals/energy_total+{scenario}+{year}.csv
```

---

## Input Data & Configuration

### UNSD Energy-Balance CSVs

Located in `data/country_specific/` (root) and sector-specific
`input_data/country_specific/` directories.

- **Filename pattern:** `UNSD_{Country}-{Year}.csv`
- **Coverage:** ~34 countries, 2011–2023
- **Structure:** Rows = sectors/transactions, Columns = commodity groups
  (`Total Energy`, `Primary Oil`, `Natural Gas`, `Electricity`, etc.)
- **Source:** [UN Statistics Division Energy Balances](https://unstats.un.org/unsd/energystats/)

### Global Reference Datasets

| File | Used by | Content |
|------|---------|---------|
| Khalili 2019 Supplementary Data | Transport | Subsector shares, load factors, mode splits |
| `OECD.Stat-EEI_TRANSPORT.csv` | Transport | Technology shares (ICE/BEV/FCEV) per country |
| `CAGR.csv` / `CAGR_compilation_*.xlsx` | Transport | Compiled CAGR from IEE, ISI, Khalili sources |
| `international_marine_and_aviation_data.xlsx` | Transport | International bunker fuel data |
| `CLASS_worldbank.xlsx` | Residential | Country income classification |
| `gdp-per-capita-worldbank.csv` | Residential | Historical GDP/capita |
| UNDESA household-size Excel | Residential | Persons per dwelling |
| World Bank access CSVs | Residential | Electricity & clean-cooking access rates |
| World Bank cooking-fuel PDF | Residential | Cooking technology mix (parsed via tabula) |

### Country-Specific SSP Projections

Located in each sector's `input_data/country_specific/`:

- **Population:** `chart-data_pop_{Country}.csv`
- **GDP:** `chart-data_gdp_{Country}.csv`
- **Source:** [Climate Solutions Explorer](https://climate-solutions-explorer.pik-potsdam.de/) (SSP1–SSP5)

### Configuration Files

| File | Sector | Format | Purpose |
|------|--------|--------|---------|
| `transport/trans_config.csv` | Transport | CSV | Per-country overrides: base year, SSP pathway, CAGR source, technology targets, scenario names |
| In-code constants | Residential | Python | `SCENARIOS`, `SSP_ORDER`, `BASE_YEAR`, `GROWTH_PATHWAY` in `build_residential_config.py` |
| `build_shares.py` constants | Additional | Python | `DEFAULT_SECTOR_LABELS`, `BASE_PERIODS`, fuel-to-commodity mapping |

---

## Output Format

All sector outputs are written to `output_data/` directories (git-ignored).

### Transport

| File | Content |
|------|---------|
| `country_parameters/{Country}_transport_params.csv` | ~80 metrics × years (population, shares, load factors, intensities, technology splits) |
| `{Country}_final_energy_demand.csv` | GWh by mode/technology/fuel for each scenario and year |
| `pypsa_indicators_{Country}.csv` | Aggregated PyPSA-compatible indicators (road EV, road FCEV, rail, aviation, navigation by fuel) |

### Residential

| File | Content |
|------|---------|
| `parameters_all_countries.csv` | Combined parameter table (all countries × scenarios × years) |
| `residential_all_scenarios_years_countries.csv` | Final demand by fuel for each country/scenario/year |
| Per-scenario/year CSVs | Fuel-level demand slices |

### Additional Sectors

| File | Content |
|------|---------|
| `{sector}_fuel_demand_history_future.csv` | Historical + projected TWh by fuel (oil, gas, electricity, coal, biomass) per country and year |

### PyPSA Energy Totals

| File | Content |
|------|---------|
| `energy_total+{scenario}+{year}.csv` | Merged residential + additional-sector demand per country |

---

## Visualisation Notebooks (`plots/`)

The `plots/` directory contains Jupyter notebooks for post-processing
exploration and figure generation:

| Notebook | Purpose |
|----------|---------|
| `plots.ipynb` | Cross-sector comparison plots and scenario-specific CSV exports |
| `industry_graphs.ipynb` | Industry sub-sector demand bar charts by carrier and scenario |
| `transport_graphs.ipynb` | Transport demand breakdown (road EV, FCEV, rail, aviation, navigation) |
| `residential_graphs.ipynb` | Residential demand by fuel (electricity, biomass, gas, oil, etc.) |
| `statistics.ipynb` | Quick statistical overview — loads all three sector Excel files |
| `Industry_type_analysis_table.xlsx` | Supporting data for industry notebook |

> **Note:** Several notebooks contain **hardcoded Windows paths** (e.g.
> `C:\Users\eduque\...`).  You will need to update these paths to point to
> your local `output_data/` directories before running them.

Launch the notebook interface with:

```bash
conda activate sectoral-energy
jupyter lab
```

---

## Root-Level Scripts

| Script | Purpose |
|--------|---------|
| `build_shares.py` | Computes historical fuel shares for all UNSD sectors across all countries. Exports per-sector CSVs to `output_data/interim/shares/`. Used by additional-sectors and residential modules. |
| `build_CAGR.py` | Computes 5-year rolling CAGRs from UNSD total-energy data. Exports per-sector CSVs to `output_data/interim/cagr/`. Used by additional-sectors module. |
| `build_pypsa_energy_totals.py` | Merges residential and additional-sector outputs into scenario × year CSVs for PyPSA integration. |
| `build_pypsa_industry.py` | Placeholder for future industry → PyPSA integration (currently empty). |

---

## Known Limitations & Work in Progress

| Area | Status | Details |
|------|--------|---------|
| **Industry module** | 🔴 Not present | An `industry/` module is planned (sub-sectors are defined in `build_CAGR.py`) but is not yet in this branch. `build_pypsa_industry.py` is an empty placeholder. |
| **Residential maturity** | 🟡 Active development | The residential module works end-to-end but has several TODOs: district heating is disabled, absolute energy intensities cannot be overridden via config, and the `__init__.py` exports are fully commented out. |
| **Hardcoded notebook paths** | 🟡 Needs cleanup | Visualisation notebooks reference absolute Windows paths (`C:\Users\eduque\...`) that must be updated per user. |
| **Country coverage** | 🟡 Partial | UNSD data covers ~34 countries; the transport module currently lists only a subset (e.g. Morocco, Egypt, South Africa) in its default run. Coverage depends on available SSP and UNSD files. |
| **Configuration consistency** | 🟡 Mixed | Transport uses a CSV config file; residential uses in-code constants; additional sectors inherit from root scripts. A unified configuration layer is not yet implemented. |
| **Heat pump modelling** | 🟡 Simplified | Residential space-heating splits heat-pump demand as a fixed 30% electricity / 70% geothermal ratio rather than using COP-based calculations. |
| **Testing** | 🔴 Minimal | Test files exist in `.gitignore` but are excluded from the repository. No test suite is included. |
| **PyPSA integration** | 🟡 Partial | `build_pypsa_energy_totals.py` covers residential + additional sectors only; transport and industry PyPSA exports are not yet unified into this script. |

---

## Contributors

<!-- To refresh this list run: git shortlog -sne HEAD -->

- Estefanía Duque Pérez, Fraunhofer IEE
- Rakesh Etikala Narendar, Fraunhofer IEE

---

## License

*To be specified.* <!-- Add your license here -->
