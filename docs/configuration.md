# Configuration

## Transport — `trans_config.csv`

Located at `transport/trans_config.csv`. Each row overrides a default value for a
specific country, metric, milestone year, and scenario.

| Column | Type | Description |
|--------|------|-------------|
| `country` | string | ISO country name as used in SSP filenames |
| `metric` | string | Metric key (matches keys in `helpers.py` unit map) |
| `year` | int | Milestone year: 2030, 2040, or 2050 |
| `scenario` | string | `sc_a` (Baseline), `sc_b` (Moderate), `sc_c` (Ambitious) |
| `value` | float | Override value |
| `source` | string | Reference or rationale (optional) |

**Example** — override BEV share for Morocco in the Ambitious scenario by 2030:

```csv
country,metric,year,scenario,value,source
Morocco,bev_share_ldv,2030,sc_c,0.25,IRENA Morocco 2023
```

## Residential — in-code constants

Residential configuration is currently defined as Python variables inside
`residential/build_residential_config.py`:

```python
BASE_YEAR      = 2018
SCENARIOS      = ["Current Policies", "Progressive", "Ambitious Net Zero"]
SSP_ORDER      = ["SSP2", "SSP2", "SSP1"]
GROWTH_PATHWAY = "moderate"   # "low" | "moderate" | "high"
```

!!! warning "Work in progress"
    A dedicated config file (CSV or YAML) for the residential module is planned
    but not yet implemented.

## Root-level CAGRs — `build_CAGR.py`

The root `build_CAGR.py` computes rolling 5-year CAGRs from UNSD historical
totals. These are consumed by the additional-sectors module. The sector labels
and base period are defined as constants inside the script:

```python
BASE_PERIODS = [2011, 2015, 2019]
DEFAULT_SECTOR_LABELS = { ... }   # UNSD → internal sector name mapping
```
