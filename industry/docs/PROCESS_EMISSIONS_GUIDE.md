# Process emissions: methodology and acceptance contract

**Updated: 2026-10-09. Status: provisional arithmetic, NOT validated final CO₂ inputs.**

The calculator is [industry/scripts/calculate_process_emissions.py](../scripts/calculate_process_emissions.py).
The retained factors and machine-readable metadata are in
[industry/utils/process_emission_factors.py](../utils/process_emission_factors.py).
All existing numeric factors are retained. No replacement ammonia or aluminium
factor has been invented. Legacy claims that every factor is a JRC-IDEES EU28
"future best-case" value are **unverified**, not accepted attribution.

## Boundaries and unresolved decisions

Process emissions are a separate **CO₂ mass flow**, never an energy carrier.
Do not add these records to fuel-demand rows or sum them with MWh/TWh.
The intended boundary excludes fuel-combustion emissions, but each retained
factor's actual boundary still requires source review to prevent double counting.

All factors currently carry these acceptance blockers:

- `factor_provenance_missing`: no verified dataset/table/cell or source citation;
- `factor_version_missing`: no verified source release/reference year;
- `factor_gas_basis_unverified`: intended CO₂ does not prove a CO₂-only source;
- `factor_boundary_unverified`: process-versus-combustion boundary is not established.

Additional blockers:

- HVC: `hvc_route_mapping_unverified` covers the provisional cracking/MTO mapping.
- Ammonia: `ammonia_source_missing`; SMR also has
   `ammonia_smr_factor_is_unverified_zero_placeholder`.
- Primary aluminium:
   `aluminium_co2_only_factor_unverified_legacy_pfc_annotation`.

`ammonia_SMR=0` is **not evidence of zero emissions** or evidence that another
module already counts them. The user boundary puts ammonia process emissions
here, but a verified SMR+HB process factor/source is still missing. Local and
reallocated production is calculated here; SMR physical CO₂ remains missing.
E+HB uses the retained zero provisionally and remains unaccepted.

The primary-aluminium factor `1.5` previously mentioned CF₄/C₂F₆. These gases
are not CO₂. There is no verified gas split or CO₂-only attribution in the
repository. Retain `1.5` for hand checks; do not infer a replacement, a GWP, or
convert PFCs/CO₂e into CO₂. Primary-aluminium physical CO₂ remains missing.
`gas_basis=CO2` specifies the **requested output**, while
`factor_gas_basis=unverified` records the unresolved input basis.

## Configuration contract and units

The standardized wide config requires `metric_1`, `metric_2`, `metric_3`,
`metric_4`, `year`, `scenario`, `units`, followed by named country columns.
Country identifiers are retained exactly as config column labels (usually full
country names); they are not automatically converted to ISO codes.
Metrics and known routes are case/whitespace normalized, with explicit aliases.
Missing identifiers, missing/non-finite/negative values, duplicate activity or
route rows, unsupported units and unknown routes/factors raise `ValueError`.
An unknown factor never falls back to `Unspecified` or zero. `Unspecified` is
available only when explicitly requested; an omitted route is allowed only for
an explicit sector `default`.

The real orchestrator lowercases metrics and converts `t/year`, `tonnes`, and
`100t/a` to `t/a`, multiplying **only** the last unit's values by 100 upstream.
The emissions calculator respects the actual `units` field:

| Declared units | Multiply value by to obtain t/a |
|---|---:|
| `t/a`, `t/year`, `tonnes`, `tonnes/year` | 1 |
| `100t/a`, `100t/year` | 100 |
| `Mt/a`, `Mt/year` | 1,000,000 |

Thus 1,000,000 t/a = 10,000 × 100t/a = 1 Mt/a. There is **no additional 100×**
conversion for standardized tonnes. Shares are fractions for `share`/`fraction`;
only explicit `%`/`percent`/`percentage` units are divided by 100. Groups must sum
to 1 within absolute tolerance `1e-6`; invalid shares are never renormalized.

Production and technology-route years must be integers. CAGR period rows remain
untouched. For each configured production metric, every requested year/scenario
must be present; absence of an entire unconfigured product is outside report
scope, not an invented zero-emissions sector. The readiness JSON states scope and
configured products; this is **not** an all-industry emissions inventory.

## Route accounting

### Steel

The actual production metric is `steel production per year`.
`primary steel production` and `secondary steel production` are top-level shares;
`BF+BOF` and `DR+EAF` are shares **within primary steel**, not extra total routes.
For total activity $P$, primary share $p$ and within-primary BF share $b$:

$$P_{BF}=Ppb,\qquad P_{DR}=Pp(1-b),\qquad P_{scrap}=P(1-p).$$

Apply retained factors BF+BOF `0.22`, DR+EAF `0.05`, scrap EAF `0.05` only to
these leaves. Never emit the primary/secondary parent rows as additional activity.
Optional `DR+EAF+H2` and `DR+EAF+NG` shares are conditional **within DR+EAF**;
both are required when present and must sum to 1. Explicit equivalent spellings
and `metric_3=DR+EAF`, `metric_4=hydrogen/natural gas` are supported. They replace
the aggregate DR leaf, not add to it. Both retain the DR factor `0.05`, pending
the same boundary/provenance review; no route-specific new numbers are inferred.

### Cement/clinker

The generated metric `cement production per year` is final cement.
Use its country/year/scenario `clinker ratio` (`technology_route`, fraction) to
derive clinker tonnes, then multiply **clinker only** by retained `Cement=0.54`.
An explicit `clinker production per year` can be used directly. If both cement
plus ratio and direct clinker exist, they must agree within tolerance and are
counted once. Missing ratios are not replaced by 1 or an assumed typical value.
The generic calculation API rejects the cement factor on a cement activity metric.

### HVC

Use `hvc production per year` and its technology shares, separately from ammonia
shares in the same `chemical and petrochemical` sector. Retain distinct HVC routes:

| Config route | Factor key | Retained factor |
|---|---|---:|
| Naphtha cracking | `HVC_primary` | 0.18 |
| LPG cracking | `HVC_primary` | 0.18 |
| MTO / Methanol to olefins | `HVC_feedstock` | 0.23 |
| Explicit `HVC_primary` / `HVC_feedstock` | corresponding key | 0.18 / 0.23 |
| Explicit mechanical / chemical recycling factor route | corresponding key | 0 / 0 |

This mapping is a **provisional model mapping**, not a verified MTO factor source
or proof of fossil/biogenic carbon accounting. All active shares must sum to 1.
Unknown chemical routes raise rather than silently disappear. Ammonia and import
reallocation rows are recognized as another family, not included in HVC totals.

### Ammonia

Use `ammonia production per year`, SMR+HB and E+HB (alias `renewable synthesis`)
shares. Conventional production is local tonnes × SMR share; green production is
local tonnes × E+HB share **plus imports reallocated to local green production**.
Ordinary imports are not domestic process activity. If imports are present, an
explicit `import reallocation` share is required. An optional
`ammonia import reallocated volume per year` must agree with imports × share.
Do not count that derivative row again as total production. Missing verified
SMR factors yield missing physical emissions and blocked acceptance, not a zero.

### Aluminium and paper

Split `aluminium production per year` by `primary aluminium` and
`secondary aluminium` shares, summing to 1. Retain `Aluminium_primary=1.5` and
`Aluminium_secondary=0`; primary CO₂ is blocked by the unresolved gas basis.
Pulp and paper use their own production tonnes and retained factors `0.02` and
`0.01`, respectively. They are provisional too. Additional factor entries remain
available via strict lookup; unconfigured sectors are not fabricated by this stage.

## Public API and downstream gate

Imports use `industry.scripts.calculate_process_emissions` and
`industry.utils.process_emission_factors` from the repository root.

- `ProcessEmissionCalculator(config_path=None, config_df=None)` retains the existing
   constructor and sector methods. `calculate_all_emissions(years, scenarios)`
   returns detailed rows without writing anything.
- `production_to_tonnes(value, units)` is the explicit unit-conversion helper.
- `get_emission_factor(sector, route=None)` returns a retained hand-check number.
   It **does not** certify acceptance. `get_emission_factor_metadata(...)` returns
   independent machine-readable provenance/basis/blocker data.
- `summarize_process_emissions(detailed)` groups by country/scenario/year/sector.
   Any missing leaf makes the entire sector's physical CO₂ total missing (no
   pandas skip-NA partial totals).
- `generate_process_emissions_reports(df_config, output_dir, years, scenarios,
   *, require_accepted=False, allow_provisional=False)` preserves `detailed` and
   `summary` path keys and adds `readiness`. Defaults write review reports even
   when acceptance is blocked. `require_accepted=True` gates **before** writing.
- **Exporter coordination:** call `require_accepted_process_emissions(summary,
   *, allow_provisional=False)` on the exact scenario/year subset before final
   export. Default raises on provisional/unaccepted/missing CO₂. The explicit
   opt-in is **review-only** and permits finite provisional CO₂ with metadata;
   it never fills missing CO₂, promotes readiness, or exports PFCs/CO₂e as CO₂.

The gate is provided here; exporters must actually call it. No energy-carrier
exporter is modified by this emissions-only change. Verification/review of
source metadata and factors is still required before any acceptance flags may
be promoted; the bundled factor set cannot produce accepted output today.

CLI module execution requires an explicit `--output-dir` and supports `--config`,
`--require-accepted`, and `--allow-provisional`. Use temporary review directories
for validation, not source/generated production directories.

## Reports and exact schemas

Report basenames are `process_emissions.csv`, `process_emissions_summary.csv`,
and `process_emissions_readiness.json` in the caller's explicit output directory.

**Summary columns**, in order:

`country`, `scenario`, `year`, `sector`, `emissions_tCO2`, `emissions_MtCO2`,
`provisional_emissions_tCO2`, `provisional_emissions_MtCO2`, `emissions_units`,
`gas_basis`, `readiness`, `ready_for_export`, `blockers`.

- `emissions_tCO2`: annual CO₂ tonnes (may be missing); not MWh, not Mt.
- `emissions_MtCO2`: same annual quantity / 1,000,000; retained internal unit.
- `provisional_emissions_*`: retained-factor arithmetic for **hand checks only**.
   For blocked SMR/aluminium these are placeholders/unresolved-gas calculations,
   **not substitute physical emissions or validated CO₂ values**.
- `emissions_units=tCO2/a`; `gas_basis=CO2` is the requested output boundary.
- `readiness`: `provisional` for finite retained arithmetic or `blocked` for
   missing CO₂. `accepted` is recognized by the gate but never emitted currently.
- `ready_for_export`: boolean, always false with the current unreviewed factors.
- `blockers`: JSON array of stable identifiers, unioned across a sector's routes.

**Detailed rows** contain the summary dimensions plus `product`, `route`,
`factor_key`, `production_t`, `production_Mt`, `production_basis`, `source_units`,
`factor_tCO2_per_t`, both physical and provisional emissions-unit pairs,
`emissions_units`, `gas_basis`, `factor_provenance`, `factor_version`,
`factor_gas_basis`, `factor_material_basis`, `factor_boundary`, `factor_status`,
`readiness`, `ready_for_export`, `blockers`. They contain no `carrier` column.

The readiness JSON (`schema_version=process-co2-review-v1`) contains global
readiness/blockers, requested dimensions, configured products, scope, row counts,
and each used factor's retained value, provenance, version, gas/material basis,
intended boundary, provisional status and blockers. Missing provenance/version
are JSON null, not invented citations. Missing physical emissions are CSV blanks.

## Reproducible arithmetic checks (not country forecasts)

| Fixture | Hand calculation | Expected annual mass |
|---|---|---:|
| 1 Mt steel; primary 0.8, BF within primary 0.75 | 0.6×0.22 + 0.2×0.05 + 0.2×0.05 | 0.152 MtCO₂ = 152,000 tCO₂ |
| 2 Mt cement; clinker ratio 0.7 | 2×0.7×0.54 | 0.756 MtCO₂ = 756,000 tCO₂ |
| 1 Mt HVC; cracking 0.6/0.25, MTO 0.15 | (0.6+0.25)×0.18 + 0.15×0.23 | 0.1875 MtCO₂ = 187,500 tCO₂ |
| 1 Mt aluminium; primary 0.6 | 0.6×1.5 | retained arithmetic 0.9 Mt; **physical CO₂ missing** |
| 1 Mt local ammonia; SMR 0.6; imports 0.5 Mt, reallocation 0.2 | SMR 0.6 Mt; green 0.4+0.1 Mt | **SMR physical CO₂ missing** |

The prior illustrative examples mislabeled thousands of kilotonnes as Mt and
claimed reasonableness without support. They are replaced by dimensionally exact
synthetic hand checks. No country forecast or factor provenance is validated by
these arithmetic examples.

Focused standard-library tests are in [tests/test_process_emissions.py](../../tests/test_process_emissions.py).
They cover unit conversions, casing/aliases, strict missing/bad factors, share
bounds/conservation/duplicates, hierarchical DR leaves, clinker basis, HVC and
ammonia family separation, reallocation, CO₂-only aluminium, all standard
horizons/scenarios, real producer row builders, CSV/JSON readback and refusal
before final writing. All test report outputs use temporary directories.
