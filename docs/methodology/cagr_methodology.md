# Data-Driven CAGR Methodology

## Overview

**NEW WORKFLOW** replaces hardcoded CAGR values with data-driven calculations from historical UNSD energy consumption data.

> **Note**: This methodology is currently implemented for the **iron and steel** sector as a pilot. The approach will be **generalized and applied to all industrial sectors** (ammonia, cement, chemicals, paper/pulp, etc.) to ensure consistent, data-driven projections across the entire industry module.

## Comparison: Old vs New

| Aspect | OLD (Hardcoded) | NEW (Data-Driven) |
|--------|----------------|-------------------|
| **Source** | Arbitrary values in `industry/build_CAGR.py` | Historical UNSD energy data (2011-2023) |
| **Methodology** | None - manually set | Rolling 5-year CAGR calculation |
| **Example** | `{"2030": [0.0, 0.0, 0.0], "2050": [0.0, 0.01, 0.01]}` | Morocco: 2.5% (calculated from historical trend) |
| **Transparency** | ❌ No justification | ✅ Based on actual data |
| **Reproducibility** | ❌ Can't verify | ✅ Fully reproducible |

## New Calculation Process

### 1. Calculate Historical CAGR
```python
def calculate_steel_cagr_from_unsd(countries, scenarios):
    # For each country:
    historical_cagr = get_final_energy_cagr_from_unsd(country, "Iron and steel")
    # Returns: mean CAGR from rolling 5-year windows (2011-2023)
```

**Example Output:**
- Morocco: 2.5% annual growth (based on 2011-2023 energy consumption)
- Egypt: 3.2% annual growth
- South Africa: 1.8% annual growth
- Namibia: 4.1% annual growth

### 2. Apply Scenario Multipliers

Different future pathways modify the historical baseline:

```python
scenario_multipliers = {
    "BAU": 1.0,          # Business as usual: historical trend continues
    "Progressive": 1.2,  # 20% acceleration (green growth policies)
    "Optimistic": 1.5,   # 50% acceleration (aggressive industrialization)
}
```

**Example (Morocco with 2.5% historical CAGR):**
- BAU: 2.5% × 1.0 = **2.5% growth**
- Progressive: 2.5% × 1.2 = **3.0% growth**
- Optimistic: 2.5% × 1.5 = **3.75% growth**

### 3. Project Production

Uses compound growth formula:
```
Production[year] = Production[2020] × (1 + CAGR)^(year - 2020)
```

**Example (Morocco with 1000 tons in 2020, 2.5% CAGR):**
- 2030: 1000 × (1.025)^10 = **1280 tons**
- 2040: 1000 × (1.025)^20 = **1639 tons**
- 2050: 1000 × (1.025)^30 = **2098 tons**

## Benefits of New Approach

1. **Methodological Rigor**: Based on actual historical trends, not guesses
2. **Transparency**: Clear calculation steps anyone can verify
3. **Flexibility**: Easy to adjust scenario multipliers based on policy assumptions
4. **Country-Specific**: Each country uses its own historical trend
5. **Reproducibility**: Same inputs always produce same outputs

## Future Enhancements

### Option 1: Period-Differentiated CAGR
CAGR could vary over time:
```python
# Example: Growth slows as economy matures
2020-2030: historical_cagr × 1.0
2030-2040: historical_cagr × 0.8
2040-2050: historical_cagr × 0.6
```

### Option 2: Policy-Adjusted Scenarios
Incorporate specific policy targets:
```python
# Example: Morocco's 2030 steel production target = 5000 tons
# Back-calculate required CAGR to meet target
```

### Option 3: Sector Convergence
Countries converge toward regional average:
```python
# Example: By 2050, all African countries converge to mean CAGR
```

## Technical Notes

- **Data Source**: UNSD country-specific CSV files in `data/country_specific/`
- **Calculation Function**: `get_final_energy_cagr_from_unsd()` in `industry/build_CAGR.py`
- **Window Size**: 5-year rolling windows
- **Fallback**: If no historical data, defaults to 1.5% CAGR
- **Application**: Same CAGR used for ALL periods (can be enhanced for period variation)

## Files Modified

- `industry/generate_industry_config.py`: New workflow implementation
- `industry/build_CAGR.py`: Data-driven calculation functions (already existed)

## Files Deprecated

- Hardcoded `CAGR` dictionary in `industry/build_CAGR.py` (lines 377-408) - NO LONGER USED
