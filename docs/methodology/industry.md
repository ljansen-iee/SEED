# Industry Methodology

## Scope

The industry module covers final energy demand for the industrial sector across
three countries (Morocco, Egypt, South Africa) from a base year of **2020** to
milestone years **2030, 2035, 2040, 2045, 2050** under three scenarios: BAU,
Progressive, and Optimistic.

## Core formula

\[
\text{FED}_{\text{sub-sector}} =
  \text{Production} \times \text{Technology share} \times \text{Energy intensity}
  \times \text{Fuel share}
\]

Each factor is projected from the base year using scenario-specific CAGRs and
share overrides defined in `industry/industry_config.csv`.

## Sub-sectors

The module distinguishes between energy-intensive sub-sectors modelled
bottom-up and remaining industries modelled top-down via UNSD data and
sector-level CAGRs.

### Energy-intensive (bottom-up)

| Sub-sector | Processes modelled |
|------------|-------------------|
| **Iron & Steel** | BF+OHF, BF+BOF (primary); DR+EAF; Scrap EAF (secondary); Casting/Rolling/Finishing |
| **Non-Metallic Minerals** | Cement (dry/wet kiln), Clinker, Unspecified NMM |
| **Paper, Pulp & Printing** | Primary pulp (kraft/sulfite), Secondary pulp, Paper |
| **Chemical & Petrochemical** | Ammonia (SMR+Haber-Bosch, Renewable); HVC (naphtha, LPG, methanol cracking) |

For each process the model tracks production volume (t/y), technology/process
share, energy intensity (MWh/t), and fuel share.

### Other industries (top-down)

The following sub-sectors are projected using historical UNSD energy data and
sector-level CAGRs: Food & Tobacco, Non-ferrous Metals, Mining & Quarrying,
Machinery, Transport Equipment, Textile & Leather, Wood & Wood Products,
Construction.

## Workflow

The module runs in two sequential steps.

**Step 1 — Build parameters** (`build_config_industry.py`)

Loads production databases (WorldSteel, FAO FAOSTAT, IFA, UNSD) and computes
base-year fuel shares and energy intensities for each sub-sector. CAGR
assumptions are read from `industry/industry_config.csv`. Results are written
to `industry/country_parameters/{Country}_Output_.csv`.

**Step 2 — Calculate final energy demand** (`build_final_energy_demand.py`)

Reads the country parameter files, applies `SHARE` overrides and chain-linked
`CAGR` projections from `industry_config.csv`, and writes final energy demand
outputs to `industry/output_data/`.

## CAGR Calculation Methodology

The module uses a **data-driven approach** to calculate Compound Annual Growth Rates (CAGR) for production projections. Instead of hardcoded values, CAGRs are derived from historical UNSD energy consumption data (2011-2023) with scenario-specific multipliers:

- **BAU**: Historical CAGR × 1.0 (continuation of current trends)
- **Progressive**: Historical CAGR × 1.2 (20% growth acceleration)
- **Optimistic**: Historical CAGR × 1.5 (50% growth acceleration)

This methodology ensures transparency, reproducibility, and country-specific projections based on actual historical patterns.

> **📖 For detailed methodology**: See [CAGR Methodology](cagr_methodology.md)

## Scenarios

| Scenario | Description |
|----------|-------------|
| **BAU** | Business As Usual — continuation of current production trends, no additional policy action |
| **Progressive** | Moderate decarbonisation — gradual technology shifts and efficiency improvements |
| **Optimistic** | Aggressive decarbonisation — rapid electrification, hydrogen adoption, and fuel switching |

## Data sources

| Dataset | Sub-sector | Variable |
|---------|-----------|---------|
| WorldSteel Annual Statistics | Iron & Steel | Production volumes, capacity shares |
| FAO FAOSTAT | Paper & Pulp | Production volumes |
| IFA / UN Comtrade | Chemical & Petrochemical | Ammonia production |
| USGS Mineral Yearbook | Non-Metallic Minerals | Cement/clinker production |
| UNSD Energy Statistics | All | Base-year fuel demand and calibration |

## Limitations

- Country coverage is currently limited to Morocco, Egypt, and South Africa.
- Aluminium (primary/secondary) is listed as a planned sub-sector but is not yet modelled.
- International industrial bunker fuels are not included.
