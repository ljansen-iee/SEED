# Quick Start

Get from a clean environment to your first set of outputs in six steps.

## Step 1 — Build cross-sector shares and CAGRs

These pre-computed intermediates are consumed by all sector modules.

```bash
python build_shares.py     # → output_data/interim/shares/
python build_CAGR.py       # → output_data/interim/cagr/
```

## Step 2 — Run the Transport module

```bash
# Build per-country parameter CSVs and trans_config.csv
python -m transport.build_transport_config
# → transport/trans_config.csv
# → transport/country_parameters/output_{Country}.csv

# Compute final energy demand
python -m transport.build_final_energy_demand
# → transport/output_data/  (per-country + aggregated CSVs)
```

## Step 3 — Run the Industry module

```bash
# Build per-country parameter CSVs and industry_config.csv
python -m industry.build_config_industry
# → industry/industry_config.csv
# → industry/country_parameters/{Country}_Output_.csv

# Compute final energy demand
python -m industry.build_final_energy_demand
# → industry/output_data/  (per-country Excel + aggregated CSVs)
```

## Step 5 — Run the Residential module

```bash
python residential/build_residential_config.py
# → residential/output_data/parameters_all_countries.csv

python residential/build_final_energy_demand.py
# → residential/output_data/  (per-scenario/year CSVs)
```

## Step 5 — Run the Additional Sectors module

```bash
python "additional sectors/build_add_sectors_demand.py"
# → additional sectors/output_data/  ({sector}_fuel_demand_history_future.csv)
```

## Step 6 — Merge into PyPSA energy totals

```bash
python build_pypsa_energy_totals.py
# → output_data/energy_totals/energy_total+{scenario}+{year}.csv
```

## Next steps

- Explore the outputs with the [Tutorials](../tutorials/transport_tutorial.ipynb).
- Adjust scenario assumptions via the [Configuration](../configuration.md) files.
- Add a new country by following the [Contributing](../contributing.md) guide.
