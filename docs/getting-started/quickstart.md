# Quick Start

Get from a clean environment to your first set of outputs in five steps.

## Step 1 — Build cross-sector shares and CAGRs

These pre-computed intermediates are consumed by all sector modules.

```bash
python build_shares.py     # → output_data/interim/shares/
python build_CAGR.py       # → output_data/interim/cagr/
```

## Step 2 — Run the Transport module

```bash
# Build per-country parameter CSVs
python transport/main_transport.py
# → transport/output_data/country_parameters/{Country}_transport_params.csv

# Compute final energy demand
python transport/build_final_energy_demand.py
# → transport/output_data/  (per-country + aggregated CSVs)
```

## Step 3 — Run the Residential module

```bash
python residential/build_residential_config.py
# → residential/output_data/parameters_all_countries.csv

python residential/build_final_energy_demand.py
# → residential/output_data/  (per-scenario/year CSVs)
```

## Step 4 — Run the Additional Sectors module

```bash
python "additional sectors/build_add_sectors_demand.py"
# → additional sectors/output_data/  ({sector}_fuel_demand_history_future.csv)
```

## Step 5 — Merge into PyPSA energy totals

```bash
python build_pypsa_energy_totals.py
# → output_data/energy_totals/energy_total+{scenario}+{year}.csv
```

## Next steps

- Explore the outputs with the [Tutorials](../tutorials/transport_tutorial.ipynb).
- Adjust scenario assumptions via the [Configuration](../configuration.md) files.
- Add a new country by following the [Contributing](../contributing.md) guide.
