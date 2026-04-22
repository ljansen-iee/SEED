# Methodology Overview

## System boundary

The tool models **final energy demand** — energy consumed by end users after
conversion and distribution losses — for three main sectors:

| Sector | Modelling approach | Base year |
|--------|-------------------|-----------|
| **Transport** | Bottom-up: mode × vehicle × technology × fuel | 2020 |
| **Residential** | Bottom-up: end-use × technology × fuel | 2018 |
| **Additional sectors** | Top-down: UNSD totals × fuel shares × CAGR | 2011–2023 (avg.) |
| **Industry** | Bottom-up (energy-intensive sub-sectors) + top-down (UNSD CAGR) | 2020 |

## Core formula

Every sector resolves to a variant of:

\[
\text{FED} = \text{Activity Level}
             \times \text{Technology Share}
             \times \text{Fuel Share}
             \times \text{Energy Intensity}
\]

where each factor is projected independently from the base year to milestone
years (2030, 2035, 2040, 2045, 2050) using scenario-specific
[CAGRs](scenarios.md).

## Common pipeline

1. **Load** — country-specific CSVs (SSP, UNSD), global reference datasets,
   configuration files.
2. **Build base-year metrics** — one `build_*.py` script per factor
   (activity, technology shares, energy intensities, fuel shares).
3. **Project** — sector CAGR scripts chain growth rates and interpolate between
   milestone years for each scenario.
4. **Export** — the entry-point script (`build_transport_config.py`,
   `build_config_industry.py`, etc.) assembles all factors and writes
   per-country output files.

## Scenario framework

Three scenarios are defined per sector (names vary slightly):

| Generic name | Transport | Residential | Industry | Meaning |
|---|---|---|---|---|
| **Baseline** | BAU | Current Policies | BAU | No additional policy action beyond today |
| **Moderate** | Progressive | Progressive | Progressive | Moderate decarbonisation effort |
| **Ambitious** | Optimistic | Ambitious Net Zero | Optimistic | Full decarbonisation by 2050 |

See [Scenarios & CAGRs](scenarios.md) for the mathematical details.
