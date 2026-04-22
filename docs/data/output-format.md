# Output Format

All outputs are written to `output_data/` directories (git-ignored).

## Transport

| File | Rows | Columns | Content |
|------|------|---------|---------|
| `country_parameters/{Country}_transport_params.csv` | ~80 metrics | years | Population, shares, load factors, intensities, technology splits |
| `{Country}_final_energy_demand.csv` | mode × technology × fuel | scenario × year | GWh final energy demand |
| `pypsa_indicators_{Country}.csv` | PyPSA categories | scenario × year | Aggregated by road/rail/aviation/navigation × fuel |

## Residential

| File | Content |
|------|---------|
| `parameters_all_countries.csv` | Combined parameter table (all countries × scenarios × years) |
| `residential_all_scenarios_years_countries.csv` | Final demand by fuel for each country/scenario/year |
| Per-scenario/year CSVs | Fuel-level demand slices |

## Additional Sectors

| File | Content |
|------|---------|
| `{sector}_fuel_demand_history_future.csv` | Historical + projected TWh by fuel per country and year |

## PyPSA Energy Totals

| File | Content |
|------|---------|
| `energy_total+{scenario}+{year}.csv` | Merged residential + additional-sector demand per country |

## Industry

All files are written to `industry/output_data/` (git-ignored).

| File | Content |
|------|---------|
| `country_parameters/{Country}_Output_.csv` | Intermediate parameter table: production, shares, intensities, fuel splits for all sub-sectors × milestone years × scenarios |
| `{ISO}_final_energy_demand.xlsx` | Final energy demand by fuel and sub-sector per scenario and milestone year |
| `{ISO}_energy_demand_summary.xlsx` | Aggregated final energy demand by energy carrier per scenario and milestone year |
| `industry_{scenario}_{year}.csv` | Flat aggregated outputs used for cross-sector merging |

## Units

| Quantity | Unit |
|----------|------|
| Final energy demand (transport) | GWh / year |
| Final energy demand (residential, additional) | TWh / year |
| Energy intensity | kWh/vkm (transport), kWh/m² or kWh/dwelling (residential) |
| Production | tonnes / year (industry) |
| Population | thousands |
| GDP | USD (PPP, constant 2010) |
