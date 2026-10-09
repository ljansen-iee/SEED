# Simple Sector Methodology

## Overview

"Simple sectors" are industries without detailed production modeling or technology route competition. They project energy demand based on:
1. **Historical energy consumption** (base year 2020)
2. **Activity growth** (CAGR from UNSD historical trends)
3. **Efficiency improvements** (scenario-dependent rates)
4. **Fuel switching** (fuel share transitions by scenario)

## Simple Sectors List

| Sector | UNSD Name | CONFIG metric_1 |
|--------|-----------|-----------------|
| Food and Tobacco | Food and tobacco | food and tobacco |
| Construction | Manufacturing  const. and mining | Manufacturing  const. and mining |
| Machinery | Machinery | machinery |
| Mining and Quarrying | Mining and quarrying | mining and quarrying |
| Textile and Leather | Textile and leather | textile and leather |
| Transport Equipment | Transport equipment | transport equipment |
| Wood and Wood Products | Wood and wood products | wood and wood products |
| Other Industries | Industry n.e.s | other |

**Note**: "Other" sector is mapped from "industry n.e.s" (industry not elsewhere specified) during CONFIG standardization.

## Methodology

### Formula

```
Energy(country, year, scenario, carrier) = 
    Historical_Energy(2020) 
    × (1 + activity_cagr)^(year - 2020)
    × (1 + efficiency_rate)^(year - 2020)
    × fuel_share(carrier, year, scenario)
```

Where:
- **Historical_Energy(2020)**: Base year total energy consumption from UNSD data (MWh)
- **activity_cagr**: Compound annual growth rate for activity/volume growth
- **efficiency_rate**: Annual efficiency improvement rate (negative value)
- **fuel_share**: Fraction of total energy for each carrier (sums to 1.0)

### Components

#### 1. Historical Energy Demand (Base Year)

**Source**: UN Statistics Division (UNSD) energy database
- **Files**: `data/country_specific/UNSD_{Country}-{Year}.csv`
- **Base year**: 2020
- **Units**: TJ (Terajoules) in raw files, converted to GWh then MWh
- **Sector mapping**: Uses UNSD sector names (see table above)

**Data Structure in UNSD Files**:
```csv
Country (2020),Transactions(down)/Commodity(right),...,Total Energy
Algeria,Food and tobacco,...,12345
Morocco,Food and tobacco,...,5678
...
```

**Note**: "Total Energy" column contains values in **TJ** (not GWh).

**Extraction and Conversion Logic**:
```python
# In industry/utils/helpers.py::get_historical_sector_data()
TJ_TO_GWH = 0.2777777778  # Conversion factor: 1 TJ = 277.778 MWh = 0.27778 GWh

# Read raw value from UNSD (TJ)
raw_value_tj = sector_row["Total Energy"].iloc[0]

# Convert TJ → GWh
history[year] = float(raw_value_tj) * TJ_TO_GWH  # Returns GWh

# In calculate_final_energy_demand.py
historical_data = get_historical_sector_data(unsd_path, country, sector_name)  # Returns dict {year: GWh}
base_energy_mwh = historical_data[2020] * 1000  # GWh → MWh
```

**Unit Conversion Chain**:
```
UNSD raw data (TJ) 
  → × 0.27778 → GWh (stored in historical_data dict)
  → × 1000 → MWh (used in calculations)
```

#### 2. Activity CAGR (Volume Growth)

**Source**: Calculated from UNSD historical energy trends (2011-2023)
- **Method**: `get_final_energy_cagr_from_unsd(country, sector)`
- **Calculation**: Rolling 5-year CAGR with IQR outlier capping
- **Country-specific**: Each country has own historical growth trajectory
- **Fallback**: If insufficient data, uses median of available countries

**Scenario Multipliers** (applied to historical CAGR):
- **BAU**: 1.0× - Historical trend continues
- **Progressive**: 1.2× - 20% faster activity growth
- **Optimistic**: 1.5× - 50% faster activity growth

**Rationale**: Historical CAGR reflects past demand drivers (population, GDP, industrialization). Scenario multipliers represent different socioeconomic pathways.

**Example**:
```python
# Historical CAGR for Morocco food sector: 2.3%/year
# Scenario-adjusted:
BAU:         2.3% × 1.0 = 2.3%/year
Progressive: 2.3% × 1.2 = 2.76%/year
Optimistic:  2.3% × 1.5 = 3.45%/year
```

#### 3. Efficiency Rate (Decarbonization)

**Source**: Scenario storyline assumptions (not data-driven)
- **BAU**: -1.0%/year - Modest efficiency gains from natural technology turnover
- **Progressive**: -2.0%/year - Active efficiency policies and technology deployment
- **Optimistic**: -3.0%/year - Aggressive efficiency mandates and breakthrough technologies

**Rationale**: Separates energy intensity improvements from activity growth. Negative values = efficiency improvement (less energy per unit output).

**Technologies Represented**:
- Process optimization (waste heat recovery, energy management systems)
- Equipment upgrades (high-efficiency motors, LED lighting, modern HVAC)
- Digitalization (IoT sensors, AI-driven optimization)
- Best practice adoption (ISO 50001 energy management)

**Validation Needed**: Current rates are engineering estimates. Should be validated against:
- IEA Energy Efficiency Indicators
- Industry-specific technology roadmaps
- Academic studies on sector efficiency potential

#### 4. Fuel Shares (Carrier Mix)

**Source**: Expert assumptions in sector-specific configuration generators
- **Configured in**: `industry/scripts/{sector}/build_shares_{sector}.py`
- **Storage**: INDUSTRY_CONFIG.csv (metric_2: "fuel_share")
- **Interpolation**: Linear between anchor years (2020, 2030, 2050)

**Typical Transition Patterns**:
```
2020 → 2030 → 2050 (BAU / Progressive / Optimistic)

Oil (diesel):     45% → 40%/35%/25% → 35%/25%/10%
Natural gas:      25% → 25%/25%/20% → 25%/20%/10%
Electricity:      20% → 25%/30%/40% → 30%/40%/60%
Coal:             10% → 10%/5%/0%   → 10%/0%/0%
Hydrogen:         0%  → 0%/5%/10%   → 0%/10%/15%
Biomass:          0%  → 0%/0%/5%    → 0%/5%/5%
```

**Fuel Mapping** (config name → output carrier):
```python
FUEL_MAPPING = {
    'diesel': 'oil',
    'oil': 'oil',
    'natural_gas': 'gas',
    'gas': 'gas',
    'electricity': 'electricity',
    'coal': 'coal',
    'heat': 'heat',
    'biomass': 'biomass',
    'hydrogen': 'hydrogen',
    'ammonia': 'ammonia',
    'methanol': 'methanol',
    'steel': 'steel',
}
```

## Data Flow

### Current Implementation

```
┌─────────────────────────────────────────────────────────────┐
│ 1. UNSD Historical Data (data/country_specific/)            │
│    - UNSD_{Country}-{Year}.csv (2011-2023)                  │
│    - Sector: "Food and tobacco", etc.                       │
│    - Energy: TJ total per sector per country per year       │
│    - Conversion: TJ × 0.27778 → GWh                         │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. CAGR Calculation (dynamic in calculate_final_energy_...py)│
│    - get_final_energy_cagr_from_unsd()                      │
│    - Rolling 5-year CAGR with IQR outlier capping          │
│    - Per country, per sector                                 │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. INDUSTRY_CONFIG.csv (only fuel_share)                    │
│    metric_1: "food and tobacco"                             │
│    metric_2: "fuel_share"                                   │
│    metric_3: "unspecified food and tobacco"                 │
│    metric_4: oil, gas, electricity, coal, etc.              │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. calculate_final_energy_demand.py                         │
│    - Read historical_data from UNSD (step 1)                │
│    - Calculate CAGR dynamically (step 2)                    │
│    - Read fuel_share from CONFIG (step 3)                   │
│    - Apply scenario multipliers (hardcoded)                 │
│    - Apply efficiency rates (hardcoded)                     │
│    - Project energy by carrier                              │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Output: final_energy_demand_detailed_sectors_wide.csv    │
│    Columns: country, scenario, year, sector, [carriers]     │
└─────────────────────────────────────────────────────────────┘
```

### Proposed Enhanced Implementation

**Centralize all parameters in INDUSTRY_CONFIG.csv for transparency:**

```
┌─────────────────────────────────────────────────────────────┐
│ 1. generate_industry_config.py (enhanced)                   │
│    For each simple sector:                                   │
│    a) Calculate CAGR from UNSD →(TJ→MWh) → store in CONFIG  │
│    b) Extract historical energy → store in CONFIG           │
│    c) Generate fuel shares → store in CONFIG                │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. INDUSTRY_CONFIG.csv (comprehensive)                      │
│                                                              │
│    metric_2: "historical_energy_demand"                     │
│    - Base year 2020 total energy (MWh)                      │
│    - Per country, one row per sector                        │
│                                                              │
│    metric_2: "cagr"                                         │
│    - Activity growth rate (decimal, e.g., 0.023 = 2.3%)    │
│    - Per country, per scenario                              │
│    - Includes scenario multipliers already applied          │
│                                                              │
│    metric_2: "fuel_share"                                   │
│    - Fraction per carrier (unchanged from current)          │
│    - Per country, per scenario, per year, per fuel          │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. calculate_final_energy_demand.py (simplified)            │
│    - Read historical_energy_demand from CONFIG              │
│    - Read cagr from CONFIG                                  │
│    - Read fuel_share from CONFIG                            │
│    - Apply efficiency rates (still hardcoded in script)     │
│    - Project energy by carrier                              │
│                                                              │
│    Benefits:                                                 │
│    - No dynamic CAGR calculation                            │
│    - No UNSD file reading in calculation step               │
│    - Users can adjust CAGR values directly in CONFIG        │
│    - Full transparency of all parameters                     │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Output: final_energy_demand_detailed_sectors_wide.csv    │
│    (unchanged)                                               │
└─────────────────────────────────────────────────────────────┘
```

## CONFIG Structure Example (Proposed)

### metric_2: "historical_energy_demand"
```csv
metric_1,metric_2,metric_3,metric_4,year,scenario,units,MA,EG,ZA,NA
food and tobacco,historical_energy_demand,Base year energy consumption,,2020,all,MWh,1234567,5678901,2345678,890123
```

**Notes**:
- Single row per sector (scenario="all" since historical data is same for all)
- Units: MWh (converted from UNSD TJ data: TJ × 0.27778 × 1000)
- Values from UNSD 2020 data converted to MWh

### metric_2: "cagr"
```csv
metric_1,metric_2,metric_3,metric_4,year,scenario,units,MA,EG,ZA,NA
food and tobacco,cagr,Activity growth rate,,2020-2050,BAU,share,0.023,0.031,0.018,0.025
food and tobacco,cagr,Activity growth rate,,2020-2050,Progressive,share,0.028,0.037,0.022,0.030
food and tobacco,cagr,Activity growth rate,,2020-2050,Optimistic,share,0.035,0.047,0.027,0.038
```

**Notes**:
- Three rows per sector (one per scenario)
- Values already include scenario multipliers (1.0×, 1.2×, 1.5×)
- Units: share (decimal rate)
- Calculated from: historical_CAGR_from_UNSD × scenario_multiplier

### metric_2: "fuel_share" (unchanged)
```csv
metric_1,metric_2,metric_3,metric_4,year,scenario,units,MA,EG,ZA,NA
food and tobacco,fuel_share,unspecified food and tobacco,oil,2030,BAU,share,0.35,0.40,0.38,0.42
food and tobacco,fuel_share,unspecified food and tobacco,gas,2030,BAU,share,0.25,0.22,0.28,0.20
...
```

## Implementation Changes Required

### 1. generate_industry_config.py
- Add CAGR calculation for simple sectors
- Add historical energy extraction for simple sectors
- Store both in INDUSTRY_CONFIG.csv

### 2. calculate_final_energy_demand.py
- Remove dynamic CAGR calculation
- Remove UNSD historical data reading
- Read CAGR and historical_energy_demand from CONFIG
- Keep efficiency rate logic (hardcoded in scenario_params)

### 3. Simple sector generators (e.g., generate_food_tobacco_config.py)
- Extend to return 3 types of rows:
  - historical_energy_demand rows
  - cagr rows
  - fuel_share rows (existing)

## Advantages of Centralized Approach

1. **Transparency**: All parameters visible in one file
2. **User Control**: Easy to modify CAGR or base year energy without code changes
3. **Reproducibility**: CONFIG file fully defines model inputs
4. **Sensitivity Analysis**: Easy to test different CAGR scenarios
5. **Auditing**: Clear documentation of data sources and assumptions
6. **Flexibility**: Can override UNSD-derived CAGR with alternative data sources

## Validation and Quality Control

### CAGR Validation
- Check for outliers (>10%/year growth or <-5%/year decline)
- Compare against GDP growth rates (energy CAGR should correlate with economic activity)
- Validate against IEA/IRENA sector-specific projections

### Historical Energy Validation
- Cross-check UNSD totals against IEA energy balances
- Verify sector definitions match between UNSD and IEA
- Check for data quality issues (missing years, anomalies)

### Fuel Share Validation
- Ensure shares sum to 1.0 for each (country, year, scenario)
- Verify transition pathways are physically feasible
- Compare against technology adoption roadmaps

## Scenario Storylines

### BAU (Business As Usually)
- **Activity**: Historical trends continue (1.0× multiplier)
- **Efficiency**: Modest improvements (-1.0%/year)
- **Fuel Mix**: Limited electrification, continued fossil dependence
- **Rationale**: Inertia in policy and technology adoption

### Progressive
- **Activity**: Moderate acceleration (1.2× multiplier)
- **Efficiency**: Active policies drive improvements (-2.0%/year)
- **Fuel Mix**: Significant electrification and renewable hydrogen adoption
- **Rationale**: Climate policies aligned with 2°C pathway

### Optimistic
- **Activity**: Strong growth in developing regions (1.5× multiplier)
- **Efficiency**: Aggressive efficiency mandates (-3.0%/year)
- **Fuel Mix**: Rapid electrification, high renewable penetration
- **Rationale**: Ambitious climate action aligned with 1.5°C pathway

## Future Improvements

### Priority 1: Fuel Share Transformation Logic (TODO)

**Current Status**: Fuel shares are CONSTANT - 2020 UNSD values used for all years and scenarios.

**Problem**: This conservative baseline doesn't model:
- Electrification trends
- Hydrogen adoption
- Coal phase-out
- Renewable energy integration
- Scenario differentiation (BAU vs Progressive vs Optimistic)

**Proposed Approaches** (ranked by complexity):

#### Option A: Simple Linear Interpolation (Low Complexity)
Define target shares for anchor years (2020, 2030, 2050) and interpolate:
```python
# Example for Progressive scenario
FUEL_SHARE_TARGETS = {
    "oil": {2020: 0.40, 2030: 0.30, 2050: 0.15},
    "electricity": {2020: 0.20, 2030: 0.35, 2050: 0.50},
    "hydrogen": {2020: 0.00, 2030: 0.05, 2050: 0.15},
    # ... interpolate between anchor years
}
```
- ✅ Simple to implement and understand
- ✅ User can easily modify target shares
- ❌ Linear transitions may be unrealistic
- ❌ Doesn't capture technology adoption dynamics

#### Option B: Exponential Decay/Growth (Medium Complexity)
Model fossil fuel decline and renewable growth with different rates:
```python
# Fossil fuels: Exponential decay
oil_share(t) = oil_2020 * exp(-decay_rate * (t - 2020))

# New carriers: Logistic growth (S-curve)
hydrogen_share(t) = max_share / (1 + exp(-growth_rate * (t - inflection_year)))
```
- ✅ More realistic transition dynamics
- ✅ Captures slow start, rapid adoption, saturation phases
- ❌ Requires calibration of decay/growth rates
- ❌ More parameters to document and validate

#### Option C: Technology Diffusion Models (High Complexity)
Use established models from innovation economics:
- **Bass Diffusion Model**: Models technology adoption with innovation and imitation coefficients
- **Fisher-Pry Substitution**: Models competitive replacement of old technology by new
```python
# Bass Model
f(t) = (p + q*F(t)) * (1 - F(t))
# where p = innovation coefficient, q = imitation coefficient
```
- ✅ Theoretically grounded in empirical adoption patterns
- ✅ Can calibrate from historical electrification data
- ❌ Complex to implement and explain
- ❌ Requires extensive parameter calibration

#### Option D: Pathway Alignment (Medium-High Complexity)
Match IEA or IRENA published decarbonization scenarios:
- IEA Net Zero by 2050 (NZE)
- IEA Announced Pledges Scenario (APS)
- IRENA 1.5°C Scenario
```python
# Extract sector-specific fuel shares from published pathways
# Interpolate to match our years and scenarios
```
- ✅ Aligned with authoritative sources
- ✅ Defensible in academic/policy contexts
- ❌ Requires data extraction from IEA/IRENA reports
- ❌ May not match specific country contexts

**Recommendation**: Start with **Option A (Linear Interpolation)** for Phase 2:
1. Define expert target shares for 2030 and 2050 per scenario
2. Implement in `build_simple_sector_fuel_share_rows_with_transformation()`
3. Validate total shares sum to 1.0
4. Document assumptions in sector-specific files

**Implementation Tasks**:
- [ ] Define transformation assumptions per scenario (BAU vs Progressive vs Optimistic)
- [ ] Create helper function for linear interpolation between anchor years
- [ ] Update fuel share builder to accept transformation mode (constant vs interpolated)
- [ ] Validate physically feasible transitions (e.g., no sudden jumps)
- [ ] Document fuel share assumptions for each simple sector
- [ ] Consider regional variations (developed vs developing countries)

### Priority 2: Sector-Specific Efficiency Rates

**Current Status**: Uniform rates across all simple sectors:
- BAU: -1.0%/year
- Progressive: -2.0%/year
- Optimistic: -3.0%/year

**Enhancement**: Replace with sector-specific rates based on literature:
```python
EFFICIENCY_RATES = {
    "food and tobacco": {
        "BAU": -0.8,      # Conservative - mature industry
        "Progressive": -1.5,
        "Optimistic": -2.5,
    },
    "construction": {
        "BAU": -1.2,      # More potential - building efficiency
        "Progressive": -2.5,
        "Optimistic": -4.0,
    },
    # ... per sector
}
```

**Validation Sources**:
- IEA Energy Efficiency Indicators
- IPCC AR6 WG3 Ch. 11 (Industry)
- Sector-specific technology roadmaps

### Priority 3: Regional Efficiency Differentiation

## References

### Data Sources
- **UNSD Energy Statistics**: https://unstats.un.org/unsd/energy/
- **IEA World Energy Balances**: https://www.iea.org/data-and-statistics
- **IRENA Renewable Energy Statistics**: https://www.irena.org/Statistics

### Methodology References
- IEA (2022). Energy Efficiency Indicators Database
- IPCC AR6 WG3 (2022). Chapter 11: Industry
- Material Economics (2019). Industrial Transformation 2050
- IEA (2020). Energy Technology Perspectives - Industry Sector

### Validation Studies
- [ ] Compare CAGR with IEA WEO projections by sector
- [ ] Validate efficiency rates against IPCC AR6 scenarios
- [ ] Cross-check fuel shares with technology roadmaps

---

**Document Status**: Draft - requires review and validation of assumptions  
**Last Updated**: 2026-06-08  
**Author**: Sectoral Energy Demands Workflow Team
