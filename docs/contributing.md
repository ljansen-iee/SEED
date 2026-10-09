# Contributing

Thank you for contributing to Sectoral Energy Demands!

## How to add a new country

Adding a country requires providing data for each sector you want to model.

### 1 — Download UNSD energy-balance data

1. Go to <https://unstats.un.org/unsd/energystats/dataPortal/>
2. Select your country and download the energy balance CSV for all available years.
3. Place it in root `data/country_specific/` with the filename
   `UNSD_{Country}-{Year}.csv`. Do not confuse this with sector-specific
   UNSD input directories or naming conventions.

### 2 — Download SSP population & GDP projections

1. Go to <https://climate-solutions-explorer.pik-potsdam.de/>
2. Select your country, navigate to the Population and GDP charts.
3. Download the chart CSV for SSP1–SSP5.
4. Place the files in each sector's configured country-input directory
   (transport `input_data/unsdata_historical/`; residential
   `input_data/unsdata_historical/` with its existing `country_specific/` fallback)
   with the names:
   - `chart-data_pop_{Country}.csv`
   - `chart-data_gdp_{Country}.csv`

### 3 — Add the country to `trans_config.csv`

Transport uses country **columns**, not one country row. Add a country column
for overrides and include the country in the producer's selected scope.
Confirm the base year and SSP pathway. Residential has a separate end-use
configuration; do not reuse transport's schema.

For industry, supply the raw production sources under `industry/input_data/`
and pass the full country name to the central generator's `--countries` option.
Its sole default config is `industry/output_data/CONFIG/INDUSTRY_CONFIG.csv`,
with `metric_1, metric_2, metric_3, metric_4, year, scenario, units` followed by
country columns. There is no implicit default-country fallback. See
[Configuration](configuration.md) and the [industry API](api/industry.md).

### 4 — Run and validate

Follow the [Quick Start](getting-started/quickstart.md): restored shared shares
and CAGR producers, transport, central industry generator/calculator,
residential file-path scripts, quoted additional-sector script, then the root
`build_pypsa_energy_demands.py` exporter. Run only affected stages.

For checks, redirect generated configs, derivatives, demand and root exports to
an **external temporary tree**. Industry exposes generator `--output-path` and
`--interim-dir`, and calculator `--config-file`, `--interim-dir`, `--output-dir`.
Pass the same selected countries, years and scenarios to both. Root export
path/scope flags are listed in the
[PyPSA output contract](data/pypsa-output-contract.md).

Validate required columns/units, unique dimension keys, complete requested
coverage, finite nonnegative values, share conservation and per-subsector
quantity conservation. Missing files/identifiers/measures and invalid readiness
are failures, not missing-as-zero fallbacks. Do not repair generated outputs
by hand, rerun unrelated sectors or overwrite `public/` during a focused check.

!!! warning "Staged integration is not approval to merge"
   Current process-emission reports are **BLOCKED**: factor provenance/version,
   gas basis and boundaries are unverified; ammonia SMR retains a zero
   placeholder conflicting with the calculate-here boundary; aluminium's
   physical CO2-only factor is not verified. Preserve retained values for
   review, never claim they are validated JRC factors. Do not fill missing
   physical CO2 or bypass the root acceptance gate. Provisional fixtures are
   review-only and require explicit authorization. See
   [readiness](methodology/industry.md#process-emissions-readiness).

---

## How to add a new sector or sub-sector

1. Keep complex sector logic in small Python modules. For industry, add a
   sector-specific row builder under `industry/scripts/` and register it with
   `industry.scripts.generate_industry_config`; keep derivative ownership in
   that central orchestrator. Extend `FinalEnergyCalculator` deliberately rather
   than adding an independent legacy industry workflow.
2. Follow the pipeline and unit contracts described in
   [Methodology Overview](methodology/overview.md).
3. Review the producing schema, units and physical accounting before wiring it
   into `build_pypsa_energy_demands.py`. The root energy tables include
   transport; industry preserves 13 subsectors and a mixed `carrier` dimension.
   Every change requires CSV **and** `.units.json` validation. Do not collapse
   subsectors, add energy/products/emissions together, or invent EL/RF scenario
   equivalence to match a filename.

---

## Code style

- Python 3.10, PEP 8.
- Use **Google-style docstrings** for all public functions so that
  `mkdocstrings` can auto-generate API documentation.
- Keep one `build_*.py` script per concern (no monolithic files).
- Use absolute package imports and repository/script-relative paths, not
   personal filesystem paths. Keep executable work behind a main guard.
- Preserve the standard `BAU`, `Progressive`, `Optimistic` scenario spelling.
- Use focused syntax/import/data checks; there is no repository-wide mandatory
   pytest/linter suite. Report skipped checks, missing inputs and stale outputs.

## Documentation checks

Use the pinned documentation dependencies from `.github/workflows/docs.yml`
and an external site directory. See [Installation](getting-started/installation.md)
for the current missing SSL-hook build blocker. Preserve the configured local
GitHub URLs and hosting/SSL behavior; do not introduce TLS bypasses to make a
review build pass.

## Reporting issues

Open an issue on the
[GitHub project page](https://github.com/ljansen-iee/SEED/issues).
