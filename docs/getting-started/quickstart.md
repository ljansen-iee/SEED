# Quick Start

Run from the repository root in the `sectoral-energy` environment after
[installation](installation.md). The integration is staged for review, **not
approved to merge or use for final studies**. Check raw inputs and requested
country/year/scenario coverage before running a stage; missing inputs and
readiness errors are failures, not permission to fabricate zeros.

These six steps describe the normal output locations. For validation, redirect
generated outputs to **external temporary directories**, not tracked sector
outputs or `public/`. Run only affected stages when upstream results are current.

## Step 1 — Build cross-sector shares and CAGRs

The restored shared producers feed residential/additional-sector workflows.
They read root `data/country_specific/UNSD_{Country}-{Year}.csv`.

```bash
python build_shares.py
python build_CAGR.py
```

Outputs go to root `output_data/interim/shares/` and
`output_data/interim/cagr/`. Both commands support `--input-dir`, `--output-dir`,
`--countries` and historical `--years`.

## Step 2 — Run transport

```bash
python -m transport.build_transport_config
python -m transport.build_final_energy_demand
```

Configuration is `transport/trans_config.csv`; country parameters and demand
are below `transport/output_data/`. Detailed vehicle demand is GWh, but current
country aggregates `transport_{Scenario}_{year}.csv` are already **TWh**.
Do not divide those aggregates by 1000 again at the root export boundary.

## Step 3 — Run the central industry workflow

```bash
python -m industry.scripts.generate_industry_config
python -m industry.scripts.calculate_final_energy_demand
```

The only default industry config is
`industry/output_data/CONFIG/INDUSTRY_CONFIG.csv`, in the
[long-metric schema](../configuration.md#industry-central-long-metric-configuration).
Derivatives and process-emission review reports go to
`industry/output_data/interim_data/`; the calculator writes detailed long/wide
demand CSVs below `industry/output_data/`.

For an isolated check, use generator `--output-path` and `--interim-dir`, then
calculator `--config-file`, `--interim-dir` and `--output-dir` pointing to the
same external tree. Both commands support `--countries`, `--years` and
`--scenarios`; quote `"South Africa"`. See the [industry API](../api/industry.md).

!!! warning "Process-emission reports are currently BLOCKED"
    Report generation is not factor acceptance. Provenance/version and
    ammonia/aluminium accounting remain unresolved. The ammonia SMR zero
    placeholder and unverified aluminium CO2-only factor leave physical CO2
    missing where those routes are active. Inspect the readiness JSON; the root
    exporter must reject these reports, even with provisional opt-in when CO2
    is missing. See [readiness](../methodology/industry.md#process-emissions-readiness).

## Step 4 — Run residential

```bash
python residential/build_residential_config.py
python residential/build_final_energy_demand.py
```

Configuration is `residential/output_data/CONFIG/DEFAULT_RESIDENTIAL_CONFIG.csv`;
the annual summary is
`residential/output_data/residential_all_scenarios_years_countries.csv`.
Use file-path entry points, not package-module execution.

## Step 5 — Run additional sectors

```bash
python "additional sectors/build_add_sectors_demand.py"
```

The restored producer writes agriculture, services, non-energy-use and other
fuel demand under `additional sectors/output_data/`, with explicit `unit=TWh`.

## Step 6 — Export the PyPSA exchange tables (readiness-gated)

```bash
python build_pypsa_energy_demands.py
```

The root driver combines **residential + additional sectors + transport** and
calculates industry fresh from the central config (it does not load a cached
wide demand file). Both output families validate before any root export is
written. Default root directory is `pypsa_input/`, with standard scenario names:

- `energy_totals_BAU_2030.csv`, one row per ISO2 `country`.
- `industry_totals_2030_BAU.csv`, `country, carrier` rows with 13 subsectors.
- Adjacent `.units.json` sidecars for both files.

The same naming applies to **BAU, Progressive, Optimistic** and all five target
years. Energy measures are TWh/a (except the district heat fraction). Industry
quantity rows mix **MWh/a**, **tSteel/a** and **tCO2/a**; never sum them together.
The legacy industry `carrier` field and subsector layout match the user's
examples, but **EL/RF scenario equivalence is unapproved**.

For external validation, pass `--config-path`, `--interim-dir`,
`--residential-output-dir`, `--additional-output-dir`, `--transport-output-dir`
and `--output-dir` explicitly, selecting the same countries/scenarios/years.
Current emissions block final export. `--allow-provisional` is only for
authorized finite physical-CO2 review fixtures; it does not fill missing CO2,
resolve blockers or approve production use. Always validate each CSV **and**
sidecar using the [PyPSA output contract](../data/pypsa-output-contract.md).

## Next steps

- Review [Configuration](../configuration.md) and [Contributing](../contributing.md).
- Use the [transport tutorial](../tutorials/transport_tutorial.ipynb) for analysis,
  but treat older notebook commands as examples rather than migration authority.
