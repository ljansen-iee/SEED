# Scenarios & CAGRs

## Scenario framework

Three scenarios capture different levels of policy ambition:

| Scenario | Description | SSP |
|----------|-------------|-----|
| **Baseline** (Current Policies) | No additional policy action. Energy demand grows with population and GDP. | SSP2 |
| **Moderate** (Progressive / Er) | Moderate efficiency improvements and partial fuel switching. | SSP2 |
| **Ambitious** (Net Zero / RL) | Full decarbonisation trajectory consistent with 1.5 °C. | SSP1 |

## CAGR mechanics

Growth between the base year and each milestone year (2030, 2035, 2040, 2045, 2050) is
expressed as a **Compound Annual Growth Rate**:

\[
V_{t+1} = V_t \times (1 + r)
\]

where \( r \) is the CAGR for the current period.

Between milestone years the CAGR is held constant. Between the milestone
*values* that result, linear interpolation is applied to smooth the trajectory:

```
Base  ──CAGR₁──▶  2030  ──interpolate──▶  2040  ──CAGR₂──▶  2050
```

## Country-level overrides

Default CAGRs come from compiled literature sources
(ISI/IEA, Khalili 2019, HYPAT). Country-specific overrides are applied from:

- `transport/trans_config.csv` — per-country, per-metric, per-year, per-scenario
- In-code constants in `residential/build_residential_config.py`

See [Configuration](../configuration.md) for the full schema.
