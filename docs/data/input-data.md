# Input Data

## UNSD Energy-Balance CSVs

The primary base-year data source is the
[UN Statistics Division Energy Statistics Data Portal](https://unstats.un.org/unsd/energystats/dataPortal/).

- **Location in repo:** `data/country_specific/` (root) and
  `transport/input_data/country_specific/`, `residential/input_data/country_specific/`
- **File pattern:** `UNSD_{Country}-{Year}.csv` (e.g. `UNSD_Morocco-2020.csv`)
- **Coverage:** ~34 countries, years 2011–2023
- **Structure:** Rows = sector/transaction labels; columns = commodity groups
  (`Total Energy Supply`, `Primary Oil`, `Natural Gas`, `Electricity`, etc.)
- **Download:** Log in → Data Portal → Energy Balances → select country & year range → export CSV

## SSP Projections (Population & GDP)

Used by both Transport and Residential modules.

- **Location:** `{sector}/input_data/country_specific/`
- **Files:** `chart-data_pop_{Country}.csv`, `chart-data_gdp_{Country}.csv`
- **Source:** [Climate Solutions Explorer](https://climate-solutions-explorer.pik-potsdam.de/)
  — PIK Potsdam, SSP1–SSP5
- **Download:** Select country → Download chart data

## Global Reference Datasets

| File | Sector | Content | Source |
|------|--------|---------|--------|
| Khalili 2019 supplementary data | Transport | Subsector shares, load factors, mode splits | Khalili et al. (2019) |
| `OECD.Stat-EEI_TRANSPORT.csv` | Transport | Technology shares by country | OECD.Stat |
| `CAGR_compilation_*.xlsx` | Transport | CAGR values from ISI/IEA/Khalili | Internal compilation |
| `international_marine_and_aviation_data.xlsx` | Transport | International bunker fuels | UNSD |
| `CLASS_worldbank.xlsx` | Residential | Country income classification | World Bank |
| `gdp-per-capita-worldbank.csv` | Residential | Historical GDP/capita | World Bank |
| UNDESA household-size Excel | Residential | Persons per dwelling | UN DESA |
| World Bank access CSVs | Residential | Electricity & cooking access rates | World Bank |
| World Bank cooking-fuel PDF | Residential | Cooking technology mix | World Bank |
| WorldSteel Annual Statistics | Industry | Iron & Steel production volumes, capacity shares | worldsteel.org |
| FAO FAOSTAT | Industry | Paper & Pulp production volumes | fao.org/faostat |
| IFA / UN Comtrade | Industry | Ammonia production volumes | fertilizer.org / comtrade.un.org |
| USGS Mineral Yearbook | Industry | Cement and clinker production | usgs.gov |
