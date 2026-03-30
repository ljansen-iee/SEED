# Residential Methodology

## System decomposition

Residential final energy demand is modelled for five end-uses:

\[
\text{FED}_{\text{end-use}} = \text{Population}
  \times \frac{\text{Floor area}}{\text{Person}}
  \times \text{Saturation rate}
  \times \text{Technology share}
  \times \text{Energy intensity}
\]

!!! note
    Water heating, cooking, and appliances use *dwellings* (persons / dwelling)
    rather than floor area as the activity driver.

## End-use summary

| End-Use | Activity driver | Saturation driver | Intensity unit |
|---------|-----------------|------------------|---------------|
| Space Heating | Floor area (m²) | Fixed scenario assumptions | kWh / m² |
| Space Cooling | Floor area (m²) | GDP-based regression | kWh / m² |
| Water Heating | Dwellings | Fixed scenario assumptions | kWh / dwelling |
| Cooking | Dwellings | World Bank clean-cooking access | kWh / dwelling |
| Electrical Appliances | Dwellings | World Bank electricity access | kWh / dwelling |

## Macro indicators

Population and GDP/capita come from SSP projections (SSP2 by default).
Floor area per person is estimated from a GDP/capita regression fitted to
MENA country data. Persons per dwelling is taken from UNDESA household-size data.

## Technology shares

- **Space heating**: Fuel mix from UNSD residential energy balances.
- **Cooking**: Country-level shares extracted from a World Bank PDF report
  using `tabula-py`.
- **Space cooling**: Electricity only (COP assumed = 3).

## Saturation rates

- **Space heating**: Fixed by scenario and income group.
- **Space cooling**: Logistic regression on GDP/capita calibrated to MENA data.
- **Appliances/cooking**: Linear interpolation from World Bank access rates
  to 100% saturation by 2050.

## Data sources

| Dataset | Used for |
|---------|----------|
| Climate Solutions Explorer (PIK) | SSP population & GDP |
| UNDESA household-size data | Persons per dwelling |
| World Bank GDP per capita | Floor area regression |
| World Bank electricity/cooking access | Saturation rates |
| UNSD Energy Statistics | Base-year fuel shares |

## Known limitations

!!! warning "Work in progress"
    - District heating is disabled (commented out in `build_technology_shares.py`).
    - Absolute energy intensities are hard-coded and cannot be overridden via config.
    - Heat-pump demand is split as a fixed 30 % electricity / 70 % geothermal
      ratio rather than a COP-based calculation.
    - `__init__.py` exports are fully commented out.
