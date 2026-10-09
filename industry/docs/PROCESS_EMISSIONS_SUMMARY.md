# Process emissions: quick reference

**Updated: 2026-10-09. All retained factors are provisional. Final acceptance is blocked.**

## Retained numbers, not verified sources

| Activity/route | Retained factor | Treatment |
|---|---:|---|
| Steel BF+BOF | 0.22 | Apply to BF leaf within primary steel |
| Steel DR+EAF / scrap EAF | 0.05 / 0.05 | Conditional DR subroutes replace DR parent |
| Clinker | 0.54 | Never apply directly to final cement |
| HVC naphtha/LPG cracking | 0.18 | Provisional `HVC_primary` route mapping |
| HVC MTO | 0.23 | Provisional `HVC_feedstock` route mapping |
| HVC mechanical/chemical recycling | 0 / 0 | Explicit recycling routes only |
| Ammonia SMR+HB | 0 retained placeholder | Physical CO₂ **missing**, not zero |
| Ammonia E+HB / renewable synthesis | 0 | Provisional; source/boundary review required |
| Primary aluminium | 1.5 | Physical CO₂ **missing**; CO₂-only gas basis unresolved |
| Secondary aluminium | 0 | Provisional CO₂-only review value |
| Pulp / paper | 0.02 / 0.01 | Their own production tonnes |

All existing numbers, including unused sector factors, are unchanged. Their
intended units are tCO₂/t material, but missing provenance/version/gas/boundary
verification means the table is **not validated emissions data**. The previous
JRC-IDEES/EU28/"best-case" attribution is not substantiated by a traceable source.

## Units and conservation

- Standardized config is normally **t/a**. Read declared units, never assume
   100t/a. Supported multipliers to tonnes: t/a = 1, 100t/a = 100, Mt/a = 1,000,000.
- 1,000,000 t/a = 10,000 × 100t/a = 1 Mt/a.
- `emissions_tCO2 = production_t × factor`; `emissions_MtCO2 = emissions_tCO2 / 1e6`.
- Shares must be finite, nonnegative fractions summing to 1. Only explicitly
   declared percentage units are divided by 100. No implicit renormalization.
- Steel parents: primary + secondary = 1. Within primary: BF+BOF + DR+EAF = 1.
   Optional hydrogen/natural-gas DR shares sum to 1 **within DR**, not all steel.
- Cement × explicit clinker ratio gives clinker. Direct clinker is counted once
   and cross-checked if cement plus ratio are also present.
- HVC and ammonia share the chemical sector but have separate route families.
- Ammonia: local SMR/E+HB split plus imports reallocated to local E+HB; ordinary
   imports are not domestic process activity.
- Aluminium primary + secondary = 1. CO₂e/PFC emissions are not exported as CO₂.
- Unknown factors/routes, duplicate rows, missing numeric data and invalid shares
   raise; missing factor provenance is reported as a blocker, never assumed away.

## Exporter coordination: exact API

From `industry.scripts.calculate_process_emissions`:

- `ProcessEmissionCalculator(config_path=None, config_df=None)`;
- `calculate_all_emissions(years, scenarios)` returns detailed review rows;
- `summarize_process_emissions(detailed)` returns a sector summary;
- `generate_process_emissions_reports(df_config, output_dir, years, scenarios,
   *, require_accepted=False, allow_provisional=False)` returns paths under keys
   **`detailed`, `summary`, `readiness`**;
- **`require_accepted_process_emissions(summary, *, allow_provisional=False)`**
   must be called by the final exporter on its scenario/year subset.

The default gate rejects current provisional factors. `allow_provisional=True`
is a clearly explicit **review-only** opt-in for finite provisional CO₂; it
cannot bypass missing SMR or primary-aluminium CO₂, fill NaNs, change readiness,
or convert PFCs/CO₂e. `require_accepted=True` gates report writing before creating
outputs. The emissions change provides the gate, not edits to other agents'
exporter code. No process record is an energy carrier.

From `industry.utils.process_emission_factors`, `get_emission_factor(...)`
provides strict normalized lookup; `get_emission_factor_metadata(...)` supplies
retained value, canonical factor key and machine-readable provenance/basis.

## Summary columns (exact order)

`country`, `scenario`, `year`, `sector`, `emissions_tCO2`, `emissions_MtCO2`,
`provisional_emissions_tCO2`, `provisional_emissions_MtCO2`, `emissions_units`,
`gas_basis`, `readiness`, `ready_for_export`, `blockers`.

Country labels are preserved from config. Units are annual `tCO2/a`, requested
gas basis `CO2`. Readiness is `provisional` or `blocked`; `ready_for_export=false`.
`blockers` is a JSON array. **Any missing leaf makes its whole sector's physical
emissions missing**, including HVC + ammonia grouped in the chemical sector.
Never replace this with a skip-NA sum or export the diagnostic provisional total.

Detailed reports additionally carry product/route, production mass and basis,
source units, factor key/value, provenance/version/gas/material/boundary metadata.
The readiness JSON records scope, dimensions, rows, configured products and used
factors (`schema_version=process-co2-review-v1`). Diagnostic
`provisional_emissions_*` remain available for arithmetic checks, not validated
CO₂ substitution for blocked factors. Missing physical CO₂ is a CSV blank.

## Blockers requiring review

1. **All factors:** `factor_provenance_missing`, `factor_version_missing`,
    `factor_gas_basis_unverified`, `factor_boundary_unverified`.
2. **HVC:** `hvc_route_mapping_unverified` (especially MTO/feedstock carbon).
3. **Ammonia:** `ammonia_source_missing`;
    `ammonia_smr_factor_is_unverified_zero_placeholder`. A verified SMR+HB process
    factor is required here; no replacement is invented or delegated to energy.
4. **Primary aluminium:**
    `aluminium_co2_only_factor_unverified_legacy_pfc_annotation`. The legacy
    CF₄/C₂F₆ comment cannot establish that 1.5 is CO₂-only; no gas split is assumed.

## Synthetic hand checks, not country forecasts

| Case | Arithmetic |
|---|---|
| 1 Mt steel; primary 0.8; BF within primary 0.75 | **0.152 MtCO₂ = 152,000 tCO₂** |
| 2 Mt cement; clinker ratio 0.7 | **0.756 MtCO₂ = 756,000 tCO₂** |
| 1 Mt HVC; naphtha/LPG/MTO 0.6/0.25/0.15 | **0.1875 MtCO₂ = 187,500 tCO₂** |
| 1 Mt aluminium; primary 0.6 | retained arithmetic 0.9 Mt; **CO₂ missing** |
| 1 Mt local ammonia; SMR 0.6 | 0.6 Mt SMR activity; **CO₂ missing** |

See [PROCESS_EMISSIONS_GUIDE.md](PROCESS_EMISSIONS_GUIDE.md) for boundaries,
units, route aliases, report schemas and review requirements. The focused
[tests/test_process_emissions.py](../../tests/test_process_emissions.py) uses
`unittest`, real producer row builders and temporary report directories. It does
not certify factor provenance or regenerate unrelated sectors.
