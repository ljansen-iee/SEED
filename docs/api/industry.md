# API Reference — Industry

## Supported entry points

Run from the repository root:

```bash
python -m industry.scripts.generate_industry_config
python -m industry.scripts.calculate_final_energy_demand
```

Both use `industry/output_data/CONFIG/INDUSTRY_CONFIG.csv`, with leading columns
`metric_1, metric_2, metric_3, metric_4, year, scenario, units` followed by
country columns. There is no old wide-config compatibility API. See
[Configuration](../configuration.md) for units, interval CAGR keys and required
dimensions.

`generate_industry_config_csv(countries, base_year=2020, target_years=None,
scenarios=None, output_path=None, interim_dir=None, generate_derivatives=True)`
returns the validated config DataFrame. It centrally owns CSV writing,
projection/volume derivatives, CAGR reports and process-emission review reports.
Missing sources and derivative errors propagate. `--config-only` explicitly
omits derivatives; it is not a fallback after failure.

`FinalEnergyCalculator(config_path=INDUSTRY_CONFIG_PATH, interim_dir=None,
output_suffix='', refresh_interim=True, refresh_years=None,
refresh_scenarios=None, countries=None, unsd_dir=None)` validates the selected
config and regenerates derivatives from it. `refresh_interim=False` (CLI
`--no-refresh-interim`) uses temporary derivatives without persistence, never
stale cached data. Python dimensions can be inferred from the config; CLI
dimensions use standard defaults, so specify subset years/scenarios explicitly.

`calculate_all_detailed_sectors(years=None, scenarios=None)` includes both
detailed **and simple** sectors. It returns long rows with
`country, scenario, year, carrier, energy_MWh, sector`.
`pivot_to_wide_format(long_df)` returns the country/scenario/year/carrier table
with 13 subsector columns. Despite `energy_MWh`, **steel stores tonnes**;
other carriers, including endogenous ammonia, store MWh. Ammonia is already
converted with 5.17 MWh/t; do not convert it again in the exporter.

Use generator `--output-path`/`--interim-dir` and calculator
`--config-file`/`--interim-dir`/`--output-dir` for external validation. Both
accept `--countries`, `--years`, `--scenarios` and `--help`.

## Process emissions and acceptance

`ProcessEmissionCalculator` and `generate_process_emissions_reports` produce
route-level and sector-summary physical-CO2 review data separately from energy
demand. `require_accepted_process_emissions` gates downstream use. Retained
factors do **not** establish verified provenance or a complete inventory.
Current reports are **BLOCKED** by factor provenance/version/gas/boundary,
ammonia SMR's zero placeholder and unverified aluminium CO2-only accounting.
Missing physical CO2 fails even with provisional opt-in. See
[process-emissions readiness](../methodology/industry.md#process-emissions-readiness).

The root `build_pypsa_energy_demands.py` driver exports fresh industry results
and energy totals including transport to root `pypsa_input/`. The
[PyPSA output contract](../data/pypsa-output-contract.md) specifies filenames,
the mixed-quantity `carrier` dimension, 13 preserved subsectors, units sidecars,
readiness metadata and external checks. Staged integration is **not merge approval**.

## Generated API documentation

The following sections are generated from docstrings via
[mkdocstrings](https://mkdocstrings.github.io/).

### Config orchestrator

::: industry.scripts.generate_industry_config

### Final energy calculator

::: industry.scripts.calculate_final_energy_demand

### Process-emission reports and gate

::: industry.scripts.calculate_process_emissions

### Configuration and data helpers

::: industry.utils.helpers
