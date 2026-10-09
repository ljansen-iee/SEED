# Sectoral Energy Demands

> Bottom-up final energy demand forecasting tool for 30+ countries, developed at
> [Fraunhofer IEE](https://www.iee.fraunhofer.de/) as part of the projects
> [DeV-KopSys-2](https://www.iee.fraunhofer.de/de/projekte/suche/2021/dev-kopsys-2.html)
> and [H2Global meets Africa](https://www.iee.fraunhofer.de/en/research_projects/search/2024/h2global-africa.html).

The tool projects sectoral final energy consumption from a base year (~2018–2023)
to 2030–2050 under multiple policy scenarios. Outputs are structured for direct
ingestion by energy system models such as
[PyPSA-Earth](https://github.com/pypsa-meets-earth/pypsa-earth).

!!! warning "Staged integration — not approved to merge"
  The central industry workflow and root exporter are integrated for review,
  not certified for final studies. Current process-emission reports are
  **BLOCKED** by provenance/version, ammonia SMR and aluminium gas/boundary
  evidence. Missing inputs/readiness must fail. Validate exports externally
  with the [PyPSA output contract](data/pypsa-output-contract.md).

---

## What it does

Many integrated energy-system models require exogenous projections of final energy
demand broken down by sector, fuel, and technology. Existing global datasets are
often too aggregated or rely on proprietary assumptions.

**Sectoral Energy Demands** fills this gap by:

- Computing base-year energy balances from **UN Statistics Division (UNSD)**
  energy-balance data (2011–2023, ~34 countries).
- Applying country- and scenario-specific **Compound Annual Growth Rates (CAGRs)**
  at milestone years (2030, 2035, 2040, 2045, 2050) with linear interpolation in between.
- Decomposing demand through a hierarchy of activity levels, technology shares,
  fuel shares, and energy intensities via the core formula:

\[
\text{FED} = \text{Activity Level} \times \text{Technology Share}
             \times \text{Fuel Share} \times \text{Energy Intensity}
\]

- Exporting readiness-gated country/scenario/year exchange tables for
  [PyPSA-Earth](https://github.com/pypsa-meets-earth/pypsa-earth), with explicit
  units sidecars. Schema compatibility does not establish scientific acceptance
  or guarantee that every column becomes a downstream load.

---

## Quick navigation

<div class="grid cards" markdown>

- :material-rocket-launch: **[Quick Start](getting-started/quickstart.md)**
  — Follow the six-stage workflow and its readiness gates.

- :material-cog: **[Installation](getting-started/installation.md)**
  — Set up the Conda environment.

- :material-math-integral: **[Methodology](methodology/overview.md)**
  — Equations, assumptions and data sources.

- :material-database: **[Input Data](data/input-data.md)**
  — What data is needed and where to get it.

- :material-file-chart: **[Output Format](data/output-format.md)**
  — Schema of the generated CSV/Excel files.

- :material-check-decagram: **[PyPSA Output Contract](data/pypsa-output-contract.md)**
  — Exact root export layout, mixed quantities, sidecars and acceptance blockers.

- :material-notebook: **[Tutorials](tutorials/transport_tutorial.ipynb)**
  — Step-by-step Jupyter notebooks.

</div>

---

## Repository structure

```text
sectoral-energy-demands/
│
├── transport/                   # Transport mode & technology energy demand
├── industry/                    # Central config generator + demand calculator
├── residential/                 # Residential end-use energy demand
├── additional sectors/          # Agriculture, Services, Non-energy, Other
├── data/country_specific/        # Root UNSD_{Country}-{Year}.csv inputs
├── plots/                       # Post-processing Jupyter notebooks
│
├── build_CAGR.py                # Cross-sector CAGR computation from UNSD data
├── build_shares.py              # Cross-sector fuel-share computation from UNSD data
├── build_pypsa_energy_demands.py # Energy (including transport) + fresh industry export
├── pypsa_input/                  # Generated root CSVs + .units.json sidecars (ignored)
│
├── docs/                        # This documentation (MkDocs)
├── mkdocs.yml                   # Documentation configuration
└── environment.yaml             # Conda environment specification
```

Industry runs through `python -m industry.scripts.generate_industry_config`
and `python -m industry.scripts.calculate_final_energy_demand`, using
`industry/output_data/CONFIG/INDUSTRY_CONFIG.csv` in long-metric format.
The root driver combines **residential + additional sectors + transport** and
calculates industry fresh. Standard scenarios are **BAU, Progressive, Optimistic**;
root filenames are `energy_totals_{Scenario}_{year}.csv` and
`industry_totals_{year}_{Scenario}.csv`.

Energy totals use TWh/a (apart from district heat share). Industry preserves the
example-compatible `country, carrier` rows and 13 subsectors. The legacy
`carrier` field mixes energy **MWh/a**, steel **tSteel/a** and physical process
CO2 **tCO2/a**; read its sidecar and never sum mixed quantities. Scenario mapping
to example EL/RF labels remains unapproved.

---

## Developers and Collaborators

- Estefanía Duque Pérez, Fraunhofer IEE
- Rakesh Etikala Narendar, Fraunhofer IEE
- Lukas Jansen, Fraunhofer IEE

---

## Acknowledgements

This work was carried out within the projects **DeV-KopSys-2** and
**H2Global meets Africa**, funded by the German Federal Ministry for Economic
Affairs and Climate Action (BMWK).
