# Transport Methodology

## Scope

The transport module covers Morocco, Egypt, South Africa, and Namibia from a
base year of **2020** to milestone years **2030, 2035, 2040, 2045, 2050**
under three scenarios: BAU, Progressive, and Optimistic.

## Workflow

The module runs in two sequential steps.

**Step 1 — Build parameters** (`build_transport_config.py`)

Loads UNSD base-year data, SSP projections, Khalili reference data, and
OECD technology shares. Computes base-year values for all model dimensions
and writes CAGR assumptions to `transport/trans_config.csv` (auto-generated
on first run; hand-editable afterwards). Per-country parameter files are
written to `transport/country_parameters/output_{Country}.csv`.

**Step 2 — Calculate final energy demand** (`build_final_energy_demand.py`)

Reads the country parameter files, applies chain-linked CAGR projections
from `trans_config.csv`, and writes final energy demand outputs to
`transport/output_data/`.

## System decomposition

Transport final energy demand is decomposed hierarchically:

\[
\text{FED} = \frac{
  \text{Population} \times \text{Mobility/capita}
  \times \text{Subsector share} \times \text{Mode share}
}{\text{Load factor}}
\times \text{Technology share} \times \text{Energy intensity}
\]

| Dimension | Categories |
|-----------|-----------|
| **Mode** | Road, Rail, Aviation, Marine (domestic + international) |
| **Vehicle type** | LDV, Bus, 2-&-3-Wheeler, HDT, LDT, Passenger/Freight Train, Ship, Plane |
| **Technology** | ICE, BEV, FCEV, PHEV, Biofuel blends |
| **Fuel** | Gasoline, Diesel, Electricity, Hydrogen, Biofuels, LNG, Kerosene |

## Activity drivers

- **Population** — SSP1–SSP5 projections from the
  [Climate Solutions Explorer](https://climate-solutions-explorer.pik-potsdam.de/).
- **Mobility per capita** — Passenger-km/year and tonne-km/year from
  Khalili et al. (2019), scaled by GDP per capita growth.

## Technology share projections

Base-year ICE/BEV/FCEV splits are sourced from `OECD.Stat-EEI_TRANSPORT.csv`.
Future shares evolve per scenario, constrained to sum to 100%. Country-level
overrides are applied from `trans_config.csv`.

## Energy intensities

Base-year kWh/vkm values for ~35 vehicle-fuel combinations are defined in
`build_energy_intensities.py`. They improve (decline) over time via CAGR.

## Data sources

| Dataset | Used for | Reference |
|---------|----------|-----------|
| Khalili et al. 2019 | Subsector shares, load factors, mode splits | Supplementary data, Excel |
| OECD.Stat-EEI | Technology shares | `OECD.Stat-EEI_TRANSPORT.csv` |
| Climate Solutions Explorer | SSP population & GDP | PIK Potsdam |
| UNSD Energy Statistics | Base-year fuel demand, international bunkers | unstats.un.org |

## Limitations

- International bunker fuels (marine, aviation) are added on top using UNSD
  data and are not decomposed by technology.
- Rail electrification share is currently fixed; no endogenous electrification
  model is applied.
- Setting `INCLUDE_BUNKER_TOTALS_IN_OUTPUT = False` (default) excludes
  international bunker totals from the country parameter CSV while still
  allowing CAGR overrides in `trans_config.csv`.
