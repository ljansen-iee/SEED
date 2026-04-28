# Transport Sector Energy Demand Model

This module calculates final energy demand projections for the transport sector across multiple countries and scenarios (BAU, Progressive, Optimistic) from a base year (2020) to target years (2030-2050).

---

## Table of Contents

1. [Overview](#overview)
2. [Model Workflow](#model-workflow)
3. [Quick Start](#quick-start)
4. [Configuration Files](#configuration-files)
5. [Adding a New Country](#adding-a-new-country)
6. [Customizing Parameters](#customizing-parameters)
7. [Output Files](#output-files)
8. [File Structure](#file-structure)
9. [Troubleshooting](#troubleshooting)

---

## Overview

The transport model uses a bottom-up approach to calculate energy demand based on:

- **Population projections**
- **Mobility per capita** (passenger-km and tonne-km per person)
- **Subsector shares** (Road, Rail, Aviation for passengers; Road, Rail, Navigation for freight)
- **Mode shares** (LDV, Bus, 2&3W for road passenger; HDT, LDT for road freight)
- **Technology shares** (ICE, BEV, FCEV, Plugin Hybrid, etc.)
- **Load factors** (passengers or tonnes per vehicle)
- **Energy intensities** (kWh per vehicle-km)

The model supports three scenarios:
| Scenario | Description |
|----------|-------------|
| **BAU** | Business As Usual - continuation of current trends |
| **Progressive** | Moderate decarbonization pathway |
| **Optimistic** | Aggressive decarbonization with rapid electrification |

---

## Model Workflow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              MODEL WORKFLOW                                  │
└─────────────────────────────────────────────────────────────────────────────┘

  STEP 1: Generate Configuration
  ══════════════════════════════
  Run: python -m transport.build_config_transport
  
       ┌──────────────────────┐         ┌─────────────────────────────┐
       │   Input Data         │         │   trans_config.csv          │
       │   (UNSD, SSP, etc.)  │ ──────► │   (CAGR values for 2030-50) │
       └──────────────────────┘         └─────────────────────────────┘
                                                     │
                                                     ▼
                                        ┌─────────────────────────────┐
                                        │   country_parameters/       │
                                        │   output_{Country}.csv      │
                                        │   (Base year 2020 values +  │
                                        │    projected values)        │
                                        └─────────────────────────────┘

  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
  
  OPTIONAL: User Modifications
  ════════════════════════════
  - Edit trans_config.csv to change CAGR values for future projections
  - Edit output_{Country}.csv in country_parameters/ to change 2020 base values

  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─

  STEP 2: Calculate Final Energy Demand
  ═════════════════════════════════════
  Run: python -m transport.build_final_energy_demand
  
       ┌─────────────────────────────┐
       │   country_parameters/       │
       │   output_{Country}.csv      │
       └─────────────────────────────┘
                    │
                    ▼
       ┌─────────────────────────────────────────────────────────────────┐
       │                    OUTPUTS GENERATED                             │
       ├─────────────────────────────────────────────────────────────────┤
       │  country_specific/{Country}/                                     │
       │    ├── {ISO}_final_energy_demand.csv  (detailed demand by fuel) │
       │    ├── {ISO}_summary.xlsx             (summary tables)          │
       │    ├── output_{Country}_updated.csv   (updated parameters)      │
       │    └── parameters_{Country}.csv       (final parameters used)   │
       ├─────────────────────────────────────────────────────────────────┤
       │  output_data/                                                    │
       │    ├── transport_all_2020.csv         (all countries base year) │
       │    ├── transport_BAU_{year}.csv       (BAU scenario by year)    │
       │    ├── transport_Progressive_{year}.csv                         │
       │    └── transport_Optimistic_{year}.csv                          │
       └─────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Prerequisites

- Python 3.8+
- Required packages: `pandas`, `numpy`, `pycountry`, `openpyxl`
- Install dependencies: `pip install -r requirements.txt` (or use `environment.yaml`)

### Running the Model

**Always run from the repository root directory** (the folder containing `transport/`, `residential/`, etc.)

```bash
# Step 1: Generate configuration and country parameters
python -m transport.build_config_transport

# Step 2: Calculate final energy demand
python -m transport.build_final_energy_demand
```

---

## Configuration Files

### 1. `trans_config.csv` - Future Projections (CAGR & Target Values)

This file controls how parameters change from the base year to future years. It is **auto-generated** on the first run but can be manually edited.

**Structure:**
```
Assumption Type | Metric Name                        | Year | Scenario    | default | Algeria | Argentina | ...
CAGR           | Mobility per capita - Passenger    | 2030 | BAU         | 0.0096  | 0.0088  | 0.0248    | ...
CAGR           | Mobility per capita - Passenger    | 2030 | Progressive | 0.0096  | 0.0088  | 0.0248    | ...
Target         | Share of Technology - BEV LDV      | 2050 | Optimistic  |         |         | 96.0      | ...
```

**Key Columns:**
- **Assumption Type**: `CAGR` (compound annual growth rate) or `Target` (absolute value)
- **Metric Name**: The parameter being projected
- **Year**: Target year (2030, 2035, 2040, 2045, 2050)
- **Scenario**: BAU, Progressive, or Optimistic
- **Country columns**: Values specific to each country (blank = use `default`)

**Example CAGR Calculation:**
- If 2020 value = 100 and CAGR = 0.02 (2%), then 2030 value = 100 × (1.02)^10 = 121.9

### 2. `country_parameters/output_{Country}.csv` - Base Year + Projected Values

These files contain the **complete parameter set** for each country, including base year (2020) values and all projected values.

**Structure:**
```
Metric                                      | 2020 | 2030_BAU | 2030_Progressive | ... | Units
Population                                  | 36.6 | 39.7     | 39.7             | ... | million
Mobility per capita - Passenger             | 2596 | 3543     | 3342             | ... | pkm/p
Share of Technology - BEV LDV              | 0.0  | 0.0      | 6.0              | ... | % of km
Final Energy Intensity - Gasoline ICE LDV  | 0.57 | 0.51     | 0.49             | ... | kWh/vkm
```

**Categories of Metrics:**
| Category | Examples | Units |
|----------|----------|-------|
| Population | Population | million |
| Mobility | Mobility per capita - Passenger/Freight | pkm/p, tkm/p |
| Subsector Shares | Share per Subsector - Road/Rail/Aviation | % of pkm/tkm |
| Mode Shares | Share per Mode - LDV/Bus/2&3W/HDT/LDT | % of Road pkm/tkm |
| Load Factors | Load Factor - LDV/Bus/Train/Plane/etc. | p/vehicle, t/vehicle |
| Technology Shares | Share of Technology - BEV/ICE/FCEV/etc. | % of km |
| Energy Intensities | Final Energy Intensity - [Tech] [Mode] | kWh/vkm |
| Biofuel Shares | Share of Bioethanol/Biodiesel in fuel | % |

---

## Adding a New Country

### Step 1: Add Country to the Countries List

Edit `build_config_transport.py` and add the new country to `countries_to_process`:

```python
countries_to_process = [
    "Algeria",
    "Argentina",
    # ... existing countries ...
    "South Africa",
    "NewCountry"  # ← Add your new country here
]
```

### Step 2: Add Country Column to `trans_config.csv`

Open `trans_config.csv` and add a new column for your country. You can:
- Copy values from a similar country
- Leave blank to use `default` values
- Enter country-specific CAGR or Target values

```csv
Assumption Type,Metric Name,Year,Scenario,default,Algeria,...,NewCountry
CAGR,Mobility per capita - Passenger,2030,BAU,0.0096,0.0088,...,0.015
```

### Step 3: Ensure Input Data Exists

The model requires input data for each country from:
- **UNSD Energy Statistics** (for bunker fuels)
- **Global Transport Data** (for subsector shares, mode shares)
- **SSP Population Data** (for population projections)
- **OECD Data** (for technology shares - uses Morocco as default if missing)

If data is missing, the model will use default values or Morocco as a reference.

### Step 4: Run the Model

```bash
# Generate configuration for all countries including the new one
python -m transport.build_config_transport

# Calculate energy demand
python -m transport.build_final_energy_demand
```

---

## Customizing Parameters

### Modifying Future Projections (2030-2050)

**Edit `trans_config.csv`:**

1. Open the file in Excel or a text editor
2. Find the metric you want to change
3. Modify the value in the appropriate Year/Scenario/Country cell
4. Save the file
5. Run `python -m transport.build_final_energy_demand` to recalculate

**Example: Increase BEV adoption in Brazil for 2050 Optimistic scenario**
```csv
Target,Share of Technology - BEV LDV,2050,Optimistic,,,,,90.0   # Change to 90%
```

### Modifying Base Year Values (2020)

**Edit `output_data/country_parameters/output_{Country}.csv`:**

1. Open the file for your target country
2. Find the metric in the `Metric` column
3. Edit the value in the `2020` column
4. Save the file
5. Run `python -m transport.build_final_energy_demand` to recalculate

**Example: Change Morocco's 2020 LDV load factor**
```csv
Metric,2020,...
Load Factor - LDV,2.1,...   # Changed from 1.8 to 2.1
```

### Modifying Technology Shares by Scenario

Technology shares must sum to 100% within each technology group:
- **LDV:** Gasoline ICE + Diesel ICE + LPG ICE + BEV + FCEV + Plugin Hybrids = 100%
- **Bus:** Diesel ICE + BEV + FCEV + Plugin Hybrid = 100%
- **Trucks (LDT/HDT):** Diesel ICE + BEV + FCEV + Plugin Hybrid = 100%
- **Train:** Diesel ICE + Direct Electric + FCEV = 100%

The model will warn you if shares don't sum to 100%.

---

## Output Files

### Per-Country Outputs (`output_data/country_specific/{Country}/`)

| File | Description |
|------|-------------|
| `{ISO}_final_energy_demand.csv` | Detailed energy demand by subsector, mode, technology, and fuel type (GWh) |
| `{ISO}_summary.xlsx` | Summary tables with key indicators and totals |
| `output_{Country}_updated.csv` | Updated parameter file with any modifications |
| `parameters_{Country}.csv` | Final parameters used in the calculation |

### Aggregated Outputs (`output_data/`)

| File | Description |
|------|-------------|
| `transport_all_2020.csv` | Base year energy demand for all countries |
| `transport_{Scenario}_{Year}.csv` | Energy demand by scenario and year for all countries |

**Scenarios:** BAU, Progressive, Optimistic  
**Years:** 2030, 2035, 2040, 2045, 2050

---

## File Structure

```
transport/
├── README.md                      # This file
├── RUNNING.md                     # Instructions for running scripts
│
├── build_config_transport.py      # MAIN SCRIPT 1: Generate configuration
├── build_final_energy_demand.py   # MAIN SCRIPT 2: Calculate energy demand
│
├── trans_config.csv               # Configuration file (CAGR & Target values)
│
├── helpers.py                     # Utility functions
├── build_CAGR.py                  # CAGR calculation functions
├── build_energy_intensities.py    # Energy intensity calculations
├── build_load_factors.py          # Load factor calculations
├── build_macro_indicators.py      # Population and macro indicators
├── build_share_mode.py            # Mode share calculations
├── build_share_subsectors.py      # Subsector share calculations
├── build_technology_share.py      # Technology share calculations
│
├── input_data/                    # Input data files
│   ├── UNSD/                      # UN Statistics Division energy data
│   ├── global/                    # Global transport statistics
│   └── ...
│
└── output_data/                   # Output files
    ├── country_parameters/        # Per-country parameter files
    │   ├── output_Algeria.csv
    │   ├── output_Argentina.csv
    │   └── ...
    │
    ├── country_specific/          # Per-country detailed outputs
    │   ├── Algeria/
    │   │   ├── DZ_final_energy_demand.csv
    │   │   └── DZ_summary.xlsx
    │   └── ...
    │
    ├── transport_all_2020.csv     # Aggregated base year
    ├── transport_BAU_2030.csv     # Aggregated by scenario/year
    └── ...
```

---

## Troubleshooting

### Common Issues

**1. ModuleNotFoundError: No module named 'transport'**
- **Solution:** Run from the repository root, not from inside the `transport/` folder
```bash
cd path/to/sectoral-energy-demands
python -m transport.build_config_transport
```

**2. WARNING: Technology shares = 0% (should be 100%)**
- **Cause:** Missing technology share data for that country/mode
- **Solution:** Add values to `trans_config.csv` or the model will use Morocco as default

**3. Country not found in input data**
- **Cause:** The country name doesn't match the input data
- **Solution:** Check spelling and use the exact country name from the input data

**4. trans_config.csv is empty or missing**
- **Solution:** Delete the file and run `build_config_transport.py` to regenerate it

### Validation Warnings

The model validates that:
- Technology shares sum to 100% for each mode
- Subsector shares sum to 100%
- Mode shares sum to 100%

If validation fails, you'll see warnings like:
```
WARNING: LDV technology shares in 2030_BAU = 95.00% (should be 100%)
```

Fix these by editing `trans_config.csv` or the country parameter files.

---


*Last updated: March 2026*
