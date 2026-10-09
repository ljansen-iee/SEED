# Root PyPSA output contract

The [root exporter](../../build_pypsa_energy_demands.py) combines residential,
additional-sector and transport annual demand, and independently exports fresh
industrial demand. Importing it performs no reads, writes, printing, calculator
execution or import-path mutation. This is a country-level exchange boundary,
not a guarantee that every column produces a downstream network load.

## Names, index and compatibility decisions

Default output directory: the repository-root `pypsa_input/`. For each requested
scenario/year, write:

- `energy_totals_{Scenario}_{year}.csv`
- `industry_totals_{year}_{Scenario}.csv`
- An adjacent sidecar replacing `.csv` with `.units.json` for each CSV.

Scenarios remain **BAU, Progressive, Optimistic**, case-sensitive. Target years
remain **2030, 2035, 2040, 2045, 2050**. No lower-case slug or plus-delimited name
is used. The mapping from these model scenarios to example labels **EL/RF** (or
MAPaper **Exp/IR**) is **unapproved and intentionally absent**. A downstream
configuration must select the literal scenario name or supply an independently
reviewed mapping; renaming a file is not scientific scenario equivalence.

Both output families use sorted ISO3166-1 alpha-2 country identifiers and a
**named `country` CSV field**, matching the original examples. Energy tables
have one row per country, with exactly **59 measures plus `country`**. Industry
tables have unique **`country, carrier` rows and exactly 13 subsector columns**
(15 CSV fields total); they are not collapsed to country/carrier totals.
Read energy with `pd.read_csv(path, index_col='country')` and industry with
`pd.read_csv(path, index_col=['country', 'carrier'])`. Scenario/year are in the
filename and sidecar, not measure columns. Unknown countries raise, never `XX`.
Exact `pycountry` names/codes are accepted; explicit aliases are South Korea→KR,
Russia→RU, Vietnam→VN. No fuzzy matching is used.

### Compatibility with the original examples

The original, read-only EL/RF energy examples label the first column `country`.
That header and their **59 measure columns and order** are preserved exactly.

All six original industry examples (four EL/RF and two MAPaper) have the same
**country/carrier rows, 13 ordered subsectors and 11 quantity labels**, including
`biomass` (not `solid biomass`) and `low-temperature heat`. The exporter preserves
this exact shape and every subsector value, so the legacy custom-industry reader
can still use the subsectors for spatial allocation. Schema compatibility does
not establish scenario equivalence or certify downstream physical accounting.

The original examples remain outside this worktree; none are copied, included,
modified or committed. Several industry examples contain blank numeric cells:
2030 EL/RF each have 48 blanks, 2050 EL has four, and MAPaper Exp has one.
Production validation rejects these missing values, even for provisional review.
Read-only regression tests assert rejection without zero-filling, then use
wholly synthetic finite data with the same dimensions to check incomplete
examples' serialization shapes. Complete examples additionally undergo exact
numeric conservation checks. No missing reference value is assumed to be zero.

## Energy totals: sources, units and exact columns

All energy values are **TWh/a**; `district heat share` is a dimensionless fraction
in `[0, 1]`. The ordered columns are:

```text
agriculture biomass, agriculture coal, agriculture electricity, agriculture oil,
district heat share, electricity services space, electricity services water,
non energy biomass, non energy electricity, non energy gas, non energy heat,
non energy oil, services biomass, services electricity, services gas, services oil,
total services space, total services water, electricity residential space,
electricity residential water, electricity residential, residential hydrogen,
residential coal, residential biomass, residential gas, residential oil,
residential heat biomass, residential heat gas, residential heat oil,
residential heat biomass no cooking, residential heat gas no cooking,
residential heat oil no cooking, total residential space, total residential water,
electricity rail, total rail, road biomass, road electricity, road gas, road oil,
total road, total road ev, total road fcev, total road ice, total domestic aviation,
total domestic navigation, total navigation hydrogen, total navigation oil,
total international aviation, total international navigation, international aviation e-fuel,
other biomass, other electricity, other gas, other heat, other oil,
total navigation ammonia, total rail hydrogen, international navigation e-fuel
```

### Residential

Read the producer's residential all-scenarios/years/countries summary. It is TWh
by producer contract. Keys are `country, scenario, year`. Electricity and total
space/water fields map identically. For biomass/gas/oil:

| Producer field | Output field(s) | Decision |
| --- | --- | --- |
| `residential heat {fuel} with cooking` | `residential {fuel}`, `residential heat {fuel}` | Preserve complete carrier demand; the second field is reporting/heat accounting, not additional energy |
| `residential heat {fuel}` | `residential heat {fuel} no cooking` | Preserve producer's non-cooking subset |
| `residential hydrogen with cooking` | `residential hydrogen` | Complete hydrogen demand; if the duplicate producer hydrogen field is supplied, require equality |
| `residential coal with cooking` (when explicitly separated) | `residential coal` | Identity mapping, not biomass or oil; a supplied duplicate `residential coal` must agree |
| `residential coal` alone (when explicitly separated) | `residential coal` | Identity mapping; never zero-fill a supplied coal value |

The legacy upstream summary groups coal into biomass. Without an explicit coal
field, the exporter cannot separate that aggregate: the coal output is a listed
structural zero and `residential_coal_basis` warns that biomass may include coal.
This is **not** proof of zero raw coal and must not certify separate coal demand
for a study with positive legacy coal. The real-artifact QA independently checks
the detailed producer rows; in the fresh Morocco run all requested raw coal
values are genuinely zero. The exporter supports the corrected, separately
reported coal contract without changing the example schema. It never subtracts
an inferred coal amount from biomass.

Non-cooking biomass/gas/oil may not exceed their full carrier summaries.
Space + water electricity may not exceed total electricity; neither electric
end-use may exceed its total. Space + water non-electric demand must fit within
non-cooking biomass/gas/oil plus full hydrogen/coal as an **upper bound** only:
no hydrogen/coal end-use split is invented. Equal hydrogen/coal duplicates are
recorded in `diagnostic_submeasures`, not classified as omitted zero columns.
The producer's total-space and electricity-space fields include space cooling;
the exporter preserves that energy, not a newly inferred heat-only allocation.
Nonzero `exog. renewable heat` fails: the fixed example schema has no unambiguous
column for it, so it must not be silently dropped or assigned to a fuel.

An optional explicit residential `district heat share` is preserved and bounded.
Otherwise it is zero (no specified district allocation). Structural zero columns
are enumerated in the sidecar. Do not sum the full output row: heat subsets and
transport technology totals overlap with carrier totals.

### Additional sectors

Require agriculture, services, non-energy-use and other annual fuel-demand files.
Each declares `unit=TWh`; DataFrame callers may instead use `attrs['unit']='TWh'`.
Files join one-to-one on country/year; all four must have identical key sets.
The resulting country/year values are broadcast once to each requested scenario
using a validated many-to-one join, with no implicit growth or scenario adjustment.

Represented sector-prefixed columns map identically. Non-energy/other heat is
preserved if present, otherwise explicitly zero. Services space/water heating
and electric space/water fields are zero because no end-use split is available.
Any nonzero unrepresented column (e.g. agriculture gas, services coal, ammonia)
raises. Zero unrepresented columns are recorded in `omitted_zero_columns`.
Agriculture coal is **represented** and maps identically, including positive
values. The producer obtains gas from UNSD `Natural Gas`, coal from `Primary Coal
and Peat` + `Coal and Peat Products`, using the shared fuel-share preprocessing.
It projects the base-year total with CAGR and historical-average shares, then
rounds each TWh fuel measure to six decimals. Do not invent an agriculture-gas
allocation to oil, biomass or coal if that unsupported source becomes nonzero.

### Transport: avoid double conversion

The detailed transport producer writes **GWh**. However the current
`generate_transport_indicators` explicitly multiplies by `1/1000` and the
aggregate writer preserves **TWh**, including international bunker values.
Consequently the aggregate-file loader/CLI defaults to **TWh**. It validates
each filename and the producer's `scenario={year}_{Scenario}` row label, then
normalizes separate scenario/year keys.

For genuinely GWh aggregate DataFrames/files, declare `transport_unit='GWh'`
or `--transport-unit GWh`: all represented transport fields are divided by 1000
**exactly once**. DataFrame callers must supply a unit argument or `attrs['unit']`;
contradictory unit declarations fail. Never infer units from numerical magnitude.
Raw detailed vehicle-level rows need a separately reviewed aggregation before
calling this country-indicator API. No mixed domestic-GWh/bunker-TWh input is valid.

Transport columns map identically. EV+FCEV must not exceed road total; electric
rail+hydrogen rail must not exceed rail total. Missing required transport columns
fail. Optional e-fuel columns default to documented structural zeros.

The actual producer's **`total navigation biomass`** and **`total aviation biomass`**
are already included in **`total domestic navigation`** and **`total domestic
aviation`**, respectively. They are validated diagnostic submeasures, not missing
physical energy, additional oil, international e-fuel or new schema columns.
Both must be finite/nonnegative and no larger than their domestic total. Sidecars
retain their country/scenario/year values, included-in field, conversion scale,
validation description and `TWh/a` unit under `diagnostic_submeasures.transport`.
They are not recorded as `omitted_zero_columns`, even when their values are zero.

For every selected row, require the navigation identity (within tolerance):

$$
E_{\mathrm{domestic\ navigation}} = E_{\mathrm{oil}} + E_{\mathrm{hydrogen}}
  + E_{\mathrm{ammonia}} + E_{\mathrm{biomass}}.
$$

The current producer includes navigation electricity in the domestic total but
does not publish a separate electricity indicator. A residual therefore **blocks**
with exact country/scenario/year and TWh residual evidence; it must not be guessed
as oil or biomass. Positive explicit unsupported electricity/unknown columns also
block. No unreviewed electricity allocation or alternative MAPaper schema is
introduced. Aviation only publishes its aggregate and biomass diagnostic, so its
fuel-specific identity cannot be independently reconstructed from the summary;
the exporter preserves the full domestic total and bounds the biomass subset.

## Industry: energy, products, heat and physical CO2

The ordered **subsector columns** (following `country, carrier`) are:

```text
chemical and petrochemical, construction, food and tobacco, iron and steel,
machinery, mining and quarrying, non-ferrous metals, non-metallic minerals,
other, paper pulp and print, textile and leather, transport equipment,
wood and wood products
```

The ordered **legacy `carrier` index values**, repeated for each country, are:

```text
oil, gas, electricity, coal, biomass, hydrogen, ammonia,
steel, methanol, process emissions, low-temperature heat
```

The CSV field name **`carrier` is legacy vocabulary for a mixed quantity
dimension, not a claim that all its values are energy carriers**. The sidecar
explicitly assigns each index value to a physical quantity class and unit:

| Quantity class | Legacy index values | Unit |
| --- | --- | --- |
| `energy` | oil, gas, electricity, coal, biomass, hydrogen, ammonia, methanol, low-temperature heat | **MWh/a** |
| `product_activity` | steel | **tSteel/a** |
| `process_emissions` | process emissions | **tCO2/a** |

- Steel and process emissions are **not energy**. Never multiply them by an
  energy factor or include them in an energy sum. No mixed-unit grand total is valid.
- Ammonia/methanol are downstream product-bus **energy quantities**, not tonnes.
- `biomass` stays `biomass`; an explicit input alias `solid biomass` maps to it.
- **All supplied industrial `heat` is explicitly assigned to `low-temperature
  heat`**, in MWh/a. This is a modelling assumption about supplied purchased heat,
  not evidence that all industrial process heat is low-temperature. High-temperature
  energy already represented by fuel carriers is not reassigned. Review this
  assumption before downstream heat-network interpretation.

Require all 13 sector columns from the industry calculator's wide output and
preserve them directly for each `(country, scenario, year, carrier)` row. Do not
sum subsectors or pivot quantity labels to columns. Steel activity may occur only
in the iron-and-steel sector. Export exactly 11 quantity rows per country,
including heat. Only entirely absent sparse quantity rows represent structural
zero demand; these exact keys are listed in `structural_zero_rows`. Existing
missing numeric cells, countries/scenarios/years and sector columns are not zeros.

DataFrame callers declare units by a row `unit` column, a per-quantity `industry_units`
mapping, or `industry_wide_df.attrs['units']`. Alias keys are accepted. Require
`MWh/a` for energy rows and `tSteel/a` for steel. A blanket `energy_MWh` label
is insufficient for mixed physical quantities. For fresh results from the real
`FinalEnergyCalculator`, the CLI explicitly supplies its verified native-unit
contract when attrs are absent: energy is already MWh, and the calculator's
legacy `energy_MWh` field for steel actually contains **tonnes**. The calculator
already converts ammonia tonnes to MWh using its LHV; the exporter must not
convert that again. Native MWh and steel tonnes pass through with scale **1**.
`--industry-units` supplies an independently reviewed per-quantity JSON override;
wrong units still fail rather than triggering a guessed conversion.

### Process summary and hard readiness gate

Supply a DataFrame with unique `country, scenario, year, sector` keys. Map each
sector's CO2 value into that subsector of the `process emissions` row; never
collapse those values into a single country total. Normalize
`paper, pulp and printing` to `paper pulp and print`. Require explicit coverage
for steel, chemicals, non-metallic minerals, non-ferrous metals and paper/pulp,
including zero rows; missing emitting-sector coverage is not inferred as zero.
The eight other subsectors are explicit structural zeros only when absent from
the summary; their keys are listed in `structural_zero_emissions_sectors`.
Supplied values for any of the 13 recognized sectors are retained and validated.

Prefer **`emissions_tCO2`**, passed through unchanged. Only a legacy
**`emissions_MtCO2`**-only summary is multiplied by **1e6**. When the updated
producer includes both, use tonnes and verify consistency against megatonnes.
The field names themselves declare units for legacy data; any `unit`/attrs
declaration must agree. Updated producer review fields (`emissions_units`,
`gas_basis`, `readiness`, `ready_for_export`, JSON-array `blockers`) are validated
and their blockers cannot be overridden by an external readiness file. For
updated summaries, the exporter additionally calls the producer's
`require_accepted_process_emissions` gate on the selected scope, including its
dual-unit and readiness contract. Missing physical CO2 fails before reshaping,
even if a finite `provisional_emissions_tCO2` placeholder exists.

**Missing factor provenance or unresolved ammonia/aluminium accounting is a
BLOCKER.** Accepted external readiness metadata requires `status='ready'` and
nonempty `factor_provenance`, `ammonia_basis`, `aluminium_basis`, without blockers.
Provenance should identify source/version/table/cell and boundary; ammonia must
specify process versus energy-side SMR+HB/green accounting; aluminium must resolve
physical CO2 versus PFC/CO2e. These are evidence declarations, not evidence
automatically verified against a publication by this exporter.

Without that readiness, default export fails. `allow_provisional=True` /
`--allow-provisional` permits **review-only finite physical-CO2 fixtures** and
sets `status='provisional'`, `provisional=true`, and all blockers in the sidecar.
Missing/NaN CO2, unknown routes from upstream, or CO2e/PFC-only placeholders
**still fail even with opt-in**. Never substitute `provisional_emissions_tCO2`
for missing physical `emissions_tCO2`. The main pipeline marks paired energy
outputs provisional too if industry is provisional.

## Public APIs and executable pipeline

Pure builders return a dictionary keyed by `(Scenario, year)` whose values are
DataFrames with `attrs['metadata']`: energy uses a named `country` index and
industry a named `(country, carrier)` MultiIndex with the 13 subsector columns:

- `build_energy_totals(residential_df, additional_df, transport_df, *, countries,
  years=TARGET_YEARS, scenarios=SCENARIOS, transport_unit=None)`
- `build_industry_totals(industry_wide_df, process_emissions_df, *, countries,
  years=TARGET_YEARS, scenarios=SCENARIOS, industry_units=None,
  emissions_readiness=None, allow_provisional=False)`

Writers return a list of generated CSV `Path` objects:

- `write_export_tables(tables, output_dir, kind)` (`kind='energy'` or `'industry'`)
- `export_energy_totals_by_scenario_year(residential_output_dir,
  additional_output_dir, transport_output_dir, output_dir, *, countries,
  years=TARGET_YEARS, scenarios=SCENARIOS, transport_unit='TWh')`
- `export_industry_totals_by_scenario_year(industry_wide_df,
  process_emissions_df, output_dir, **builder_options)`

`main(argv=None)` parses arguments and produces industry results **fresh** via
`FinalEnergyCalculator(config_path, interim_dir, refresh_years=years,
refresh_scenarios=scenarios, countries=selected_config_country_names)`,
`calculate_all_detailed_sectors`, and
`pivot_to_wide_format`. It never reads/writes the cached industry-wide CSV.
Both families are validated before any root exports are written. Calculator
interim files go to the supplied interim directory.

CLI path flags (hyphenated and underscore aliases) are
`--residential-output-dir`, `--additional-output-dir`, `--transport-output-dir`,
`--config-path`, `--interim-dir`, `--output-dir`. Optional scope flags are
`--countries`, `--years`, `--scenarios`; countries default to config country
columns. Explicit country subsets are supported; historical/unrequested rows
are excluded after dimension/duplicate validation. Required coverage is the
full requested country × scenario × year product, not whatever happens to exist.

Optional `--process-emissions-path` overrides the freshly produced interim
summary; the caller owns its freshness. `--emissions-readiness` requires an
existing JSON file. Otherwise look for the summary-adjacent `.readiness.json`,
then the producer's interim `process_emissions_readiness.json`.

## Machine-readable sidecar

Each sidecar contains `schema_version`, `file`, `scenario`, `year`,
`country_index` (name `country`, ISO2 encoding and unique country list),
`index_fields`, `orientation`, `time_resolution`, identity-only `scenario_mapping`,
and `columns`. Schema version **2** distinguishes the corrected named-country
energy contract and uncollapsed industry contract from the former layout.
Energy columns declare a fixed unit; industry subsector columns declare
`unit_by_index_field='carrier'`. Industry `quantity_index` states
`field='carrier'`, `legacy_field=true`, and explains that this legacy field
includes non-energy products/emissions. Its `values` mapping assigns each index
label a `quantity_class` and `unit`; `quantity_classes` separately enumerates
energy (MWh/a), steel activity (tSteel/a), and process emissions (tCO2/a).
It also contains `status`/`provisional`,
readiness evidence/blockers where applicable, input units, transformations,
structural/omitted zeros and conservation description. JSON forbids NaN/Infinity.
CSV and sidecar are a pair: downstream validation must read both and reject
provisional status outside a separately authorized review.

Energy sidecars contain per-column `lineage` with source/column/scale. Conserved
column joins use `one_to_one` or `many_to_one` validation. Industry conservation
is checked for every country/scenario/year/subsector, independently by quantity
label and physical quantity class in native units; there is no mixed-unit
"grand total". All measures are finite/nonnegative and all keys are unique.
Energy sidecars additionally distinguish validated overlapping
`diagnostic_submeasures` from unsupported omitted-zero fields. Diagnostic values
are not another energy demand and must not be added to an already-inclusive total.

## Focused validation and main-agent follow-up

Run from the worktree root using the `sectoral-energy` interpreter. Set
`PYTHONPYCACHEPREFIX` outside both repositories, and use external temporary paths
for every generated output. The focused suite is:

```powershell
python -m py_compile build_pypsa_energy_demands.py tests/test_pypsa_exports.py
python -m unittest discover -s tests -p test_pypsa_exports.py -v
```

Optional `PYPSA_REFERENCE_DIR` and `PYPSA_TRANSPORT_DIR` point to original local
examples and transport outputs for **read-only** data-backed checks. Supplying
`PYPSA_RESIDENTIAL_DIR`, `PYPSA_ADDITIONAL_DIR`, `PYPSA_TRANSPORT_DIR` and
`PYPSA_INDUSTRY_DIR` (the external root with `output_data/` and `interim_data/`)
also enables real-artifact tests over **all 15 year/scenario combinations**.
These independently compare detailed residential fuels, each mapped transport
and additional-sector column, navigation's biomass-inclusive identity, serialized
diagnostics, and TWh units. The real industry test requires the blocked physical
CO2 artifacts to fail before the writer is called; it never patches readiness or
uses provisional placeholders. Tests write only external temporary outputs and
never regenerate upstream sectors. The synthetic CLI regression uses a fake
fresh calculator; a separate logged real CLI run is needed to certify integration.
A separate in-memory test exercises the real steel/ammonia calculation and wide
pivot methods: 100 tonnes of steel activity gives 40 tonnes of endogenous steel
and 310 MWh of fuel electricity; 100 tonnes of ammonia production plus 50 tonnes
of imports at the test route shares gives 258.5 MWh of product-bus ammonia.
These hand checks verify native-unit pass-through without constructor I/O.
Another hand-computable test calls the **real transport indicator method**:
1,000 GWh diesel with a 20% biodiesel blend, 200 GWh hydrogen and 300 GWh ammonia
produce 1.5 TWh domestic navigation, including 0.2 TWh biomass and 0.8 TWh oil.
2,000 GWh kerosene at a 25% blend plus 100 GWh explicit biokerosene produce
2.1 TWh domestic aviation including 0.6 TWh biomass. Both aggregate-unit paths
(TWh and GWh) preserve these quantities exactly once.

After the industry/emissions agents finish, the main agent should run:

```powershell
python build_pypsa_energy_demands.py --help
python build_pypsa_energy_demands.py --residential-output-dir "$validation/residential" --additional-output-dir "$validation/additional" --transport-output-dir "$validation/transport" --config-path "$validation/CONFIG/INDUSTRY_CONFIG.csv" --interim-dir "$validation/interim" --output-dir "$validation/pypsa_input" --years 2050 --scenarios BAU --transport-unit TWh
```

Here `$validation` is an external temporary validation tree containing fresh
upstream inputs, not a tracked sector output location. Supply reviewed unit and
readiness JSONs when necessary. Do not add `--allow-provisional` to evade missing
physical CO2 or declare production readiness. For documentation validation use
the CI-pinned documentation dependencies and `mkdocs build --site-dir` targeting
an external temporary directory, never the tracked public output.

### Real producer → export QA, 2026-10-09

The fresh external Morocco residential, additional-sector, transport and industry
artifacts were tested for all five target years and all three scenarios. This
run uses **actual producer outputs**, not the unit-test fixtures or cached tracked
sector outputs. Standalone energy export succeeds with 15 CSV/sidecar pairs,
the exact 59-measure example schema, TWh units and conserved source mappings.
Across the 15 distinct scopes, navigation biomass is **0.1951578621024081 TWh**
and aviation biomass **0.6500185757054149 TWh**. These sums are already contained
in domestic navigation **8.43663215498576 TWh** and aviation
**13.76508944611145 TWh**; summing diagnostic and parent would double-count.
These cross-scenario audit sums are checksums, **not** one physical year.

Fresh agriculture future values are gas **0 TWh**, coal **0 TWh**, oil
**13.214325–20.431529 TWh** and electricity **4.532553–7.008075 TWh**. The base
Morocco UNSD agriculture row has `---` for Natural Gas and both coal headers,
which the source cleaner treats as zero. Zero gas is validated, not allocated
to another fuel; positive coal remains supported by identity mapping.
Detailed residential coal and hydrogen are zero in this artifact set. Full
biomass/gas/oil and their non-cooking subsets are conserved; producer electric
space cooling remains included. Nonzero explicit-coal and hydrogen mapping is
covered by independent hand-computable tests, not claimed as a real observation.

**Industry and the combined production export remain BLOCKED.** The actual
external `interim_data/process_emissions_summary.csv` contains 75 rows; **30**
rows (chemicals and non-ferrous metals in every requested scope) have missing
`emissions_tCO2` and `emissions_MtCO2`. Finite
`provisional_emissions_tCO2`/`provisional_emissions_MtCO2` are not substitutes.
The companion `interim_data/process_emissions_readiness.json` reports:

- `aluminium_co2_only_factor_unverified_legacy_pfc_annotation`
- `ammonia_smr_factor_is_unverified_zero_placeholder`
- `ammonia_source_missing` (factor provenance, not the available raw UNdata file)
- `factor_boundary_unverified`, `factor_gas_basis_unverified`
- `factor_provenance_missing`, `factor_version_missing`
- `hvc_route_mapping_unverified`

The actual industry builder and combined CLI must fail before creating final
exports; successful **standalone** energy QA is not approval of a combined pair.
The combined CLI calculates fresh industry intermediates in an external folder,
preflights both families and writes neither final family when emissions block.
No readiness override, synthetic acceptance or `--allow-provisional` is used in
the real run. Preserve external `report.json`, source-to-export conservation CSV,
blocked-physical-CO2 row CSV, input hashes/timestamps and logs alongside the
standalone energy outputs as evidence; the evidence directory is supplied by
the audit invocation, not hard-coded into production or tests.

Remaining integration gaps: ammonia/aluminium physical-CO2 basis and factor
attribution; positive legacy coal without a separate summary measure; nonzero
renewable heat, agriculture gas or unsupported navigation electricity. No
industry-orientation adapter is needed for the original reader.
Country-to-node/profile/network conservation, heat branches, shipping config
shares, the current downstream coal-load gap and hardcoded 8760 assumptions remain
consumer-side checks, not guarantees made by this root exporter.
