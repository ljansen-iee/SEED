# Sectoral Energy Demands

> Bottom-up final energy demand forecasting tool for 30+ countries, developed at
> [Fraunhofer IEE](https://www.iee.fraunhofer.de/) as part of the projects
> [DeV-KopSys-2](https://www.iee.fraunhofer.de/de/projekte/suche/2021/dev-kopsys-2.html)
> and [H2Global meets Africa](https://www.iee.fraunhofer.de/en/research_projects/search/2024/h2global-africa.html).

The tool projects sectoral final energy consumption from a base year (~2018–2023)
to 2030–2050 under multiple policy scenarios. Outputs are structured for direct
ingestion by energy system models such as
[PyPSA-Earth](https://github.com/pypsa-meets-earth/pypsa-earth).

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

- Exporting per-country, per-scenario CSV/Excel files ready for
  [PyPSA-Earth](https://github.com/pypsa-meets-earth/pypsa-earth).

---

## Quick navigation

<div class="grid cards" markdown>

- :material-rocket-launch: **[Quick Start](getting-started/quickstart.md)**
  — Run your first country in five steps.

- :material-cog: **[Installation](getting-started/installation.md)**
  — Set up the Conda environment.

- :material-math-integral: **[Methodology](methodology/overview.md)**
  — Equations, assumptions and data sources.

- :material-database: **[Input Data](data/input-data.md)**
  — What data is needed and where to get it.

- :material-file-chart: **[Output Format](data/output-format.md)**
  — Schema of the generated CSV/Excel files.

- :material-notebook: **[Tutorials](tutorials/transport_tutorial.ipynb)**
  — Step-by-step Jupyter notebooks.

</div>

---

## Repository structure

```
sectoral-energy-demands/
│
├── transport/                   # Transport mode & technology energy demand
├── residential/                 # Residential end-use energy demand
├── additional sectors/          # Agriculture, Services, Non-energy, Other
├── data/country_specific/       # UNSD energy-balance CSVs (34 countries × 13 years)
├── plots/                       # Post-processing Jupyter notebooks
│
├── build_CAGR.py                # Cross-sector CAGR computation from UNSD data
├── build_shares.py              # Cross-sector fuel-share computation from UNSD data
├── build_pypsa_energy_totals.py # Merges residential + additional sectors → PyPSA
├── build_pypsa_industry.py      # (placeholder) Industry → PyPSA integration
│
├── docs/                        # This documentation (MkDocs)
├── mkdocs.yml                   # Documentation configuration
└── environment.yaml             # Conda environment specification
```

---

## Developers and Collaborators

- Estefanía Duque Pérez, Fraunhofer IEE
- Rakesh Etikala Narendar, Fraunhofer IEE

---

## Acknowledgements

This work was carried out within the projects **DeV-KopSys-2** and
**H2Global meets Africa**, funded by the German Federal Ministry for Economic
Affairs and Climate Action (BMWK).
