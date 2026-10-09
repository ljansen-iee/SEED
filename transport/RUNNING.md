# Running transport

Run package modules from the repository root using the `sectoral-energy`
environment declared in `environment.yaml`. No requirements.txt is required.

## Legacy defaults

```bash
python -B -m transport.build_transport_config
python -B -m transport.build_final_energy_demand
```

Default countries remain Morocco, South Africa, Egypt and Namibia; base year
2020, target years 2030/2035/2040/2045/2050, scenarios BAU/Progressive/Optimistic.
Config generation updates the default assumptions file when invoked without
path options; demand reads parameters from transport/output_data/interim_parametrisation.
Imports never create directories or configuration files or refresh aggregates.
Demand no longer overwrites its input country parameter CSVs; refreshed values
are saved only in the chosen output directory.

## Isolated source-backed run (PowerShell)

Create a fresh external destination, copy **assumptions only**, then regenerate
country parameters and demand from raw inputs. Do not copy existing outputs.

```powershell
$raw = Join-Path $sourceRoot 'transport/input_data'
$run = Join-Path $env:TEMP ('transport-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $run | Out-Null
Copy-Item (Join-Path $sourceRoot 'transport/trans_config.csv') (Join-Path $run 'trans_config.csv')
$paths = @('--config-path', (Join-Path $run 'trans_config.csv'),
                          '--input-dir', $raw, '--output-dir', (Join-Path $run 'transport'),
                          '--parameter-dir', (Join-Path $run 'parameters'),
                          '--countries', 'Morocco', '--years', '2030', '2035', '2040', '2045', '2050',
                          '--scenarios', 'BAU', 'Progressive', 'Optimistic')
python -B -m transport.build_transport_config @paths
if ($LASTEXITCODE -ne 0) { throw 'Transport parameter generation failed' }
python -B -m transport.build_final_energy_demand @paths
if ($LASTEXITCODE -ne 0) { throw 'Transport demand generation failed' }
```

Set `$sourceRoot` to the read-only source repository. Execute these commands in
the repository containing the updated transport code, not the source repository.

Both CLIs expose `--config-path`, `--output-dir`, `--parameter-dir`, `--input-dir`,
`--countries`, `--years`, `--scenarios`. Lists are space-separated; quote country
names containing spaces. `--parameter-dir` is the direct country parameter folder
(config writes there; demand only reads it). `--output-dir` is the demand-output
root, not its interim subfolder. If omitted, config places parameters under
`--output-dir/interim_parametrisation`; supplying an output/parameter directory
without a config path makes config generation copy default assumptions into
that external output root. Pass that generated config path to demand explicitly.
With only `--parameter-dir`, demand uses its parent as the output root.
For isolation always use external paths for **both** output directories and
the writable config; an explicitly supplied config is intentionally updated
with source-backed bunker CAGRs by the configuration stage.

Required raw inputs:

- global/Supplementary_Material_Khalili2019_Data_final.xlsx, sheet Transportation Demand;
- global/OECD.Stat-EEI_TRANSPORT.csv;
- country_specific/chart-data_pop_{Country}.csv (SSP population);
- unsd_country_specific/{Country}-{Year}.csv (base year and available history).

The obsolete global/international_marine_and_aviation_data.xlsx is **not** read
or refreshed. Bunker totals are rebuilt from raw CSVs in memory, TJ / 3600 = TWh;
an optional explicit external aggregate can be written with
`refresh_unsd_master_data(input_folder, output_path=...)`.
Missing raw files, required base-year bunker records, configuration, or parameter
keys cause failure; no fabricated replacement rows are produced. Existing model
technology fallbacks and projection formulas remain, including warnings for
zero baseline technology groups. VALUE rows can supply future technology values
when demand refreshes the generated parameters.

## Outputs and units

- Direct parameter folder: output_{Country}.csv (Metric, base year, all selected
     year_scenario columns, Units).
- output-dir/unsdata_historical/{Country}/parameters_{Country}.csv:
     technology/fuel details, **GWh**, including a TOTAL row per scenario.
- output-dir/unsdata_historical/{Country}/{ISO}_summary.xlsx: **GWh** summaries.
- output-dir/unsdata_historical/{Country}/{ISO}_final_energy_demand.csv:
     indicators, **TWh**, including international bunkers.
- output-dir/transport_all_2020.csv and transport_{Scenario}_{Year}.csv:
     indicators, **TWh**, with country and scenario keys. A full Morocco run has
     16 files (base year plus 5 years × 3 scenarios).

Detailed GWh / 1000 = indicator TWh. The original generic schema instruction's
GWh description must not be applied to these aggregate/indicator files.
Road LPG is counted only in road gas, not also in road oil; total road equals
the detailed road sum. Methanol remains classified as navigation oil under the
legacy model convention; no unsupported carrier/schema remapping is implied.
Nonzero total navigation biomass and total aviation biomass require separate
reviewed mappings if a downstream exporter rejects unknown fields. Do not drop
these fields or zero their values to satisfy an exporter.

## Focused validation

```powershell
$env:TRANSPORT_TEST_SOURCE_ROOT = $sourceRoot
$env:TRANSPORT_TEST_OUTPUT_DIR = $run
python -B -m unittest discover -s tests -p test_transport_integration.py -v
```

The standard-library tests include LPG/unit hand checks, import write guards,
fresh UNSD totals, unchanged source/parameter checks, all year/scenario keys,
road conservation, and subset CLIs. Outputs and logs are retained in a new
external temporary subdirectory; schema-review-biomass-twh.json records actual
biomass quantities for exporter review. Source-backed tests explicitly report
missing raw inputs as skipped rather than claiming successful data validation.

For interactive use, keep the repository root on the import path and call
`transport.build_transport_config.main(...)` or
`transport.build_final_energy_demand.main(...)` with the same explicit paths.
