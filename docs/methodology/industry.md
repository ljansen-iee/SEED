# Industry Methodology

## Scope

The industry module projects industrial demand from base year **2020** to
**2030, 2035, 2040, 2045, 2050** under **BAU, Progressive, Optimistic**.
The current generator defaults select Morocco, Egypt, South Africa and Namibia;
country subsets require the corresponding raw inputs and complete config
dimensions. This is a staged integration for review, **not approval to merge**.

## Core formula

\[
\text{FED}_{\text{sub-sector}} =
  \text{Production} \times \text{Technology share} \times \text{Energy intensity}
  \times \text{Fuel share}
\]

Production, route/fuel shares and intensities are taken from the central
long-metric configuration `industry/output_data/CONFIG/INDUSTRY_CONFIG.csv`.
CAGR keys use periods such as `2020-2030`; route/fuel shares use fractions,
not percentages. See [Configuration](../configuration.md) for the schema and
unit contract. The former wide industry configuration is not supported.

Steel is hierarchical: total production splits into primary and secondary;
primary production splits into BF+BOF and DR+EAF, while secondary uses scrap EAF.
Do not add hierarchical shares as if they were a flat technology partition.
Ammonia and HVC use separate route sets inside their shared chemical sector.

## Sub-sectors

The module distinguishes between energy-intensive sub-sectors modelled
bottom-up and remaining industries modelled top-down via UNSD data and
sector-level CAGRs.

### Energy-intensive (bottom-up)

| Sub-sector | Processes modelled |
| --- | --- |
| **Iron & Steel** | BF+BOF and DR+EAF (primary); Scrap EAF (secondary); Casting/Rolling/Finishing |
| **Non-Metallic Minerals** | Cement (dry/wet kiln), Clinker, Unspecified NMM |
| **Paper, Pulp & Printing** | Primary pulp (kraft/sulfite), Secondary pulp, Paper |
| **Chemical & Petrochemical** | Ammonia (SMR+Haber-Bosch, Renewable); HVC (naphtha cracking, LPG cracking, methanol-to-olefins) |
| **Non-Ferrous Metals (Aluminium)** | Primary aluminium (Hall-Heroult), Secondary aluminium (recycling) |

For each process the model tracks production volume (t/y), technology/process
share, energy intensity (MWh/t), and fuel share.

### Other industries (top-down)

The following sub-sectors are projected using historical UNSD energy data and
sector-level CAGRs: Food & Tobacco, Mining & Quarrying,
Machinery, Transport Equipment, Textile & Leather, Wood & Wood Products,
Construction, and Other Industries (`other`). Construction's UNSD/config key
`manufacturing  const. and mining` maps to the output `construction`; UNSD
Industry n.e.s maps to config/output `other`.

The simple-sector calculation uses base-year historical MWh embedded in the
selected config, projected activity, a separate efficiency assumption and fuel
shares. It does not silently reread a different UNSD tree. An explicit
`--unsd-dir` replaces base energy only, not the configured fuel mix or CAGR.

## Workflow

The central industry workflow has two steps, run from the repository root:

```bash
python -m industry.scripts.generate_industry_config
python -m industry.scripts.calculate_final_energy_demand
```

1. **Generate configuration.** `generate_industry_config_csv` calls sector row
  builders, standardizes and validates the seven leading columns
  `metric_1, metric_2, metric_3, metric_4, year, scenario, units` plus countries,
  and writes `industry/output_data/CONFIG/INDUSTRY_CONFIG.csv`.
  The central orchestrator owns derivatives under
  `industry/output_data/interim_data/`: steel/ammonia intensity projections
  and volumes, CAGR reports, and process-emission review reports.
2. **Calculate demand.** `FinalEnergyCalculator` loads the selected config and
  refreshes projections from that config, not cached derivative files.
  `calculate_all_detailed_sectors` covers detailed and simple sectors;
  `pivot_to_wide_format` retains 13 output subsector columns. Default outputs
  are `final_energy_demand_detailed_sectors_long.csv` and
  `final_energy_demand_detailed_sectors_wide.csv` under `industry/output_data/`.

Missing required sources, dimensions, intensities and share rows fail explicitly;
derivative exceptions propagate. Config-only generation is an explicit option,
not silent recovery. `--no-refresh-interim` rebuilds temporary derivatives
without persistence. For external validation, select generator `--output-path`
and `--interim-dir`, then calculator `--config-file`, `--interim-dir` and
`--output-dir` in the same external tree. Match requested countries/years/scenarios.

The restored root shared producers `build_shares.py`, `build_CAGR.py` and the
quoted additional-sector script support the separate cross-sector workflow.
The replacement root `build_pypsa_energy_demands.py` driver merges residential,
additional sectors **and transport**, and calculates industry fresh. It does not
read a cached industry-wide demand CSV. See [Quick Start](../getting-started/quickstart.md).

## CAGR Calculation Methodology

The module uses a **data-driven approach** to calculate Compound Annual Growth Rates (CAGR) for production projections. Instead of hardcoded values, CAGRs are derived from historical UNSD energy consumption data (2011-2023) with scenario-specific multipliers:

- **BAU**: Historical CAGR × 1.0 (continuation of current trends)
- **Progressive**: Historical CAGR × 1.2 (20% growth acceleration)
- **Optimistic**: Historical CAGR × 1.5 (50% growth acceleration)

The central industry CAGR utility caps rolling-window rates using IQR bounds
and hard limits of ±30%, then averages them. Historical energy growth is used
as an **activity proxy**, not a separately measured production growth rate;
this modelling assumption requires review. Callers may floor negative trends
and apply documented fallbacks. Simple industries apply additional annual
efficiency assumptions separately: **-1%, -2%, -3%**, respectively. Do not
equate industry's central utility with the restored root shared CAGR table.

For further assumptions and limitations, see [CAGR Methodology](cagr_methodology.md).

## Scenarios

| Scenario | Description |
| --- | --- |
| **BAU** | Business As Usual — continuation of current production trends, no additional policy action |
| **Progressive** | Moderate decarbonisation — gradual technology shifts and efficiency improvements |
| **Optimistic** | Aggressive decarbonisation — rapid electrification, hydrogen adoption, and fuel switching |

## Aluminium Assumptions

- Base route intensity for both Primary and Secondary aluminium is fixed at
  **11.24 MWh/t** in the base-year intensity rows.
- The aluminium intensity builder follows the same fuel-indexed structure used
  in other detailed sectors (fuel-level values collapsed to route-level base
  intensity via the shared helper).
- Any future intensity evolution is controlled through **exogenous CAGR
  assumptions** in configuration, not inferred endogenously from historical
  aluminium intensity time series.

## Outputs and mixed quantities

The calculator's long table has
`country, scenario, year, carrier, energy_MWh, sector`. Its legacy
`energy_MWh` field contains **MWh for energy carriers**, but **tonnes for
endogenous steel**. Endogenous ammonia has already been converted using
**5.17 MWh/t**. Do not sum steel with energy or convert ammonia a second time.

Root exports preserve the user's example layout: ISO2 `country, carrier` rows
and **13 subsector columns**, not collapsed country/carrier sums. Default root
directory is `pypsa_input/`; names are
`industry_totals_{year}_{Scenario}.csv` and
`energy_totals_{Scenario}_{year}.csv`, with adjacent `.units.json` sidecars.
The legacy industry `carrier` dimension mixes:

| Quantity class | Unit |
| --- | --- |
| Energy (including ammonia, methanol, low-temperature heat) | MWh/a |
| Steel product activity | tSteel/a |
| Physical process CO2 | tCO2/a |

Supplied purchased industrial heat is assigned to `low-temperature heat` as an
explicit modelling assumption, not a claim about all process-heat temperatures.
Energy totals use TWh/a plus a dimensionless district heat share and include
transport. EL/RF example scenario mapping is **unapproved**. The
[PyPSA output contract](../data/pypsa-output-contract.md) is authoritative for
the schema, units, sidecars, conservation and downstream acceptance.

## Process-emissions readiness

**Current new reports are BLOCKED, not approved physical-CO2 inventories.**
Retain the defined factors for reproducible review; the integration does not
replace them or certify their legacy JRC-IDEES/EU28/best-case attribution.
Factor source/version/table/cell, material basis, gas basis and process-versus-
combustion boundary must be established before acceptance. HVC route mappings
also lack source verification; retained zero defaults do not demonstrate an
inventory is complete.

Selected retained arithmetic values (not accepted factors) are:

| Factor key | Retained value | Review issue |
| --- | --- | --- |
| Steel BF+BOF / DR+EAF / EAF | 0.22 / 0.05 / 0.05 | Provenance/version/gas/boundary unverified |
| Cement (used on clinker activity) | 0.54 | Verify factor per tonne clinker, not finished cement |
| HVC primary / feedstock | 0.18 / 0.23 | Route mapping and source unverified |
| Ammonia SMR / green | 0.0 / 0.0 | SMR zero is an unverified placeholder, not accepted zero CO2 |
| Aluminium primary / secondary | 1.5 / 0.0 | Primary physical CO2-only factor is not verified |

The intended factor unit is **tCO2 per tonne of material**, but that intended
label is not evidence of verified gas basis or accounting boundary.

### Ammonia: calculate-here boundary remains unresolved

The report explicitly includes configured local SMR+HB and E+HB production
(including configured import-reallocation accounting). The retained **SMR zero
placeholder conflicts with that calculate-here boundary**: it cannot establish
that SMR process CO2 was calculated here or accounted for elsewhere. Both
conventional and green sources and boundaries need verification, including
separation from energy-side combustion to avoid omission or double counting.
Where active SMR activity requires the unresolved factor, physical CO2 is
missing/blocked, not a legitimate zero-emission result.

### Aluminium: physical CO2 is not PFC/CO2e

The retained primary factor **1.5** has an unresolved legacy CF4/C2F6 annotation.
It cannot be asserted to be a verified physical **CO2-only** factor, and PFC
or CO2-equivalent quantities cannot substitute for tonnes of CO2. Active
primary aluminium therefore blocks a complete physical-CO2 report until the
gas basis, factor source and boundary are resolved.

### Reports and hard acceptance gate

The generator/calculator writes `process_emissions.csv`,
`process_emissions_summary.csv` and `process_emissions_readiness.json` below
the chosen interim directory. Reports expose retained arithmetic separately
from physical `emissions_tCO2`, readiness and blockers. Both
`emissions_tCO2` and `emissions_MtCO2` are declared; the root exporter prefers
tonnes and checks consistency, multiplying only a legacy Mt-only summary by
**1e6**. Never reuse `provisional_emissions_tCO2` as missing physical CO2.

`require_accepted_process_emissions` and the root exporter reject incomplete
physical CO2 and unresolved readiness. External readiness metadata cannot
override blockers embedded in new producer reports. `--allow-provisional`
permits only explicitly authorized finite physical-CO2 review fixtures; missing
CO2, unknown routes and PFC/CO2e placeholders still fail. Root CSV/sidecar pairs
must be validated externally before any downstream use. Successful demand or
report generation is **not** process-factor acceptance or merge approval.

## Data sources

| Dataset | Sub-sector | Variable |
| --- | --- | --- |
| WorldSteel Annual Statistics | Iron & Steel | Production volumes, capacity shares |
| FAO FAOSTAT | Paper & Pulp | Production volumes |
| UNdata production tables / petrochemical industrial database | Chemical & Petrochemical | Ammonia / HVC production |
| USGS Mineral Yearbook | Non-Metallic Minerals | Cement/clinker production |
| BGS aluminium production workbook | Non-Ferrous Metals | Aluminium production |
| UNSD Energy Statistics | All | Base-year fuel demand and calibration |

## Limitations

- Default country coverage is four countries; additional coverage requires
  source readiness and explicit validation, not a blanket claim of completeness.
- Aluminium route intensities currently use a fixed baseline assumption
  (11.24 MWh/t) pending further literature calibration.
- Process-emission factors and ammonia/aluminium accounting are blocked as
  above; review reports are not an all-industry inventory.
- International industrial bunker fuels are not included.
