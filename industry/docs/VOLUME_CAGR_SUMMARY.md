# Volume CAGR Summary - Activity & Production Growth Rates
**Generated: June 2026**  
**Model Version: 1.0**

This document summarizes the **activity and production growth rates** (volume CAGR) used across all industry sectors. These represent physical production growth independent of efficiency improvements.

---

## 📊 Overview

**Definition**: Volume CAGR represents the annual growth rate of physical production or economic activity.

- **Positive values** = Growth/expansion
- **Negative values** = Decline/contraction
- **Zero** = Stable production

**Formula**:
```
Production(year) = Base_Production(2020) × (1 + volume_CAGR)^(year - 2020)
```

---

## 🏭 DETAILED SECTORS (5 sectors)

These sectors have explicit production data, with growth rates derived from **SSP scenarios** and **national development plans**.

### Methodology for Detailed Sectors

1. **Base year production** (2020): Country-specific from statistical sources
2. **Target year production** (2030-2050): Projected from:
   - SSP (Shared Socioeconomic Pathways) scenarios
   - National infrastructure plans (cement)
   - Industry demand forecasts (chemicals)
   - GDP-elasticity models
3. **CAGR calculation**: Interpolated between base and target years

**Data storage**: `INDUSTRY_CONFIG.csv`, `metric_2='production'` or `metric_2='cagr'` with `metric_3` containing "production"

---

### 1. Steel (Iron and Steel)

**Production Metric**: Tonnes of crude steel per year

**Growth Drivers**:
- Infrastructure development (buildings, bridges, railways)
- Automotive industry expansion
- Manufacturing sector growth
- Urbanization trends

**Data Source**: 
- Historical: World Steel Association, national statistics
- Projections: SSP scenarios adjusted for regional development

**Typical Ranges** (varies by country development stage):
- **Developed countries**: -1% to +1% (mature markets, replacement demand)
- **Developing countries**: +2% to +5% (infrastructure buildout)
- **Rapid industrialization**: +5% to +8% (China historical rates)

**Country-Specific Values**: See `production_cagr.csv` for exact rates by scenario

**Data Location**: 
- `INDUSTRY_CONFIG.csv`, `metric_1='iron and steel'`, `metric_3='Steel production per year'`
- Extract: `docs/cagr_extracts/production_cagr.csv`

---

### 2. Ammonia (Chemical and Petrochemical)

**Production Metric**: Tonnes of ammonia per year

**Growth Drivers**:
- Fertilizer demand (agriculture expansion)
- Population growth
- Green hydrogen/ammonia for energy storage
- Industrial chemicals demand

**Data Source**:
- Historical: IFA (International Fertilizer Association), national chemical associations
- Projections: Food security projections, agricultural intensity scenarios

**Typical Ranges**:
- **BAU**: +1% to +2% (population growth, stable agricultural practices)
- **Progressive**: +2% to +3% (agricultural intensification, moderate green ammonia)
- **Optimistic**: +3% to +5% (green ammonia for energy, aggressive agricultural expansion)

**Country-Specific Values**: See `production_cagr.csv`

**Data Location**: 
- `INDUSTRY_CONFIG.csv`, `metric_1='ammonia'`, `metric_3='ammonia production'`

---

### 3. HVC - High Value Chemicals (Chemical and Petrochemical)

**Production Metric**: Tonnes of High Value Chemicals (ethylene, propylene, BTX) per year

**Growth Drivers**:
- Plastics demand (packaging, construction, consumer goods)
- GDP growth and consumption patterns
- Circular economy transitions (may reduce demand)

**Data Source**:
- Historical: IEA Petrochemicals report, ICIS Chemical Business
- Projections: GDP-elasticity models, material substitution scenarios

**Typical Ranges**:
- **BAU**: +2% to +3% (continued plastics growth)
- **Progressive**: +1.5% to +2.5% (moderate circular economy impact)
- **Optimistic**: +1% to +2% (aggressive recycling, material substitution)

**Country-Specific Values**: See `production_cagr.csv`

**Data Location**: 
- `INDUSTRY_CONFIG.csv`, `metric_1='chemical and petrochemical'`, `metric_3='HVC production per year'`

---

### 4. Cement (Non-Metallic Minerals)

**Production Metric**: Tonnes of clinker per year

**Growth Drivers**:
- Infrastructure investment (roads, dams, buildings)
- Urbanization rate
- Construction sector activity
- Government stimulus programs

**Data Source**:
- Historical: USGS Minerals Yearbook, national cement associations
- Projections: Infrastructure plans, urbanization forecasts, SSP scenarios

**Typical Ranges**:
- **Developed countries**: -2% to +1% (mature infrastructure, replacement only)
- **Developing countries**: +3% to +6% (rapid urbanization, infrastructure gap)
- **Middle-income countries**: +1% to +3% (moderate development)

**Note**: Cement is highly sensitive to government infrastructure spending cycles

**Country-Specific Values**: See `production_cagr.csv`

**Data Location**: 
- `INDUSTRY_CONFIG.csv`, `metric_1='non-metallic minerals'`, `metric_3='Cement production per year'`

---

### 5. Paper & Pulp (Paper, Pulp and Printing)

**Production Metric**: Tonnes of pulp and paper per year

**Growth Drivers**:
- Packaging demand (e-commerce growth)
- Printing paper demand (declining in digital age)
- Hygiene products (tissue, sanitary)
- Paperboard for construction

**Data Source**:
- Historical: FAO Forest Products Statistics, RISI
- Projections: Digitalization scenarios, packaging growth, hygiene trends

**Typical Ranges**:
- **Printing paper**: -3% to -1% (digital substitution)
- **Packaging paper**: +2% to +4% (e-commerce boom)
- **Overall**: -1% to +2% (mixed trends by product type)

**Country-Specific Values**: See `production_cagr.csv`

**Data Location**: 
- `INDUSTRY_CONFIG.csv`, `metric_1='paper, pulp and printing'`
- Separate rows for pulp and paper production

---

## 🔧 SIMPLE SECTORS (8 Sectors)

These sectors lack detailed production data. Activity growth is estimated from **historical energy consumption trends** with statistical robustness methods.

### Methodology for Simple Sectors

Since production data is unavailable, we use **total energy consumption** from UNSD (United Nations Statistics Division) as a proxy for activity levels.

**Key Assumption**: Historical energy trends reflect **net activity growth** after accounting for past efficiency improvements.

#### Step-by-Step Process

**1. Historical Data Extraction** (2011-2023)
- Source: UNSD Energy Statistics Database
- Metric: Total final energy consumption (TJ) by sector
- Coverage: 200+ countries

**2. Rolling CAGR Calculation**
- Window: 5-year rolling periods
- Example: CAGR(2016-2021), CAGR(2017-2022), etc.
- Result: 8-9 CAGR values per country-sector

**3. IQR Outlier Capping** ⭐ **Key Innovation**
- Purpose: Remove statistical outliers (COVID, data errors, policy shocks)
- Method: Interquartile Range (IQR) filtering
  ```
  Q1 = 25th percentile of CAGR values
  Q3 = 75th percentile of CAGR values
  IQR = Q3 - Q1
  
  Lower bound = Q1 - 1.5 × IQR
  Upper bound = Q3 + 1.5 × IQR
  
  Capped_CAGR = clip(CAGR, lower_bound, upper_bound)
  ```
- Requirement: Minimum 4 CAGR values for IQR calculation

**4. Hard Bounds Application**
- Physical realism constraints: -30% to +30% per year
- Prevents unrealistic growth/decline rates from data issues

**5. Final CAGR**
- Mean of capped values
- Represents **robust estimate** of historical activity trend

**6. Scenario Multipliers**

Once we have the historical activity CAGR, we apply scenario-based multipliers:

| Scenario | Multiplier | Interpretation |
|----------|-----------|----------------|
| **BAU** | 1.0× | Historical trend continues unchanged |
| **Progressive** | 1.2× | 20% faster activity growth (policy-driven development) |
| **Optimistic** | 1.5× | 50% faster activity growth (aggressive economic expansion) |

**Implementation**:
```python
activity_cagr = historical_CAGR_from_UNSD × scenario_multiplier

Activity(year) = Base_Activity(2020) × (1 + activity_cagr)^years
```

**Code Location**: 
- CAGR extraction: `industry/core/cagr_calculator.py::calculate_rolling_cagr_with_iqr_capping()`
- Application: `industry/calculate_final_energy_demand.py::calculate_simple_sector_energy()`

---

### Simple Sectors List

**9 sectors using this methodology**:

1. **Food and tobacco**
   - Drivers: Population, dietary shifts, food processing industrialization
   - Typical range: +1% to +3%

2. **Construction** (Manufacturing, construction and mining)
   - Drivers: Infrastructure, housing, commercial development
   - Typical range: +2% to +5%

3. **Machinery**
   - Drivers: Manufacturing expansion, industrial equipment demand
   - Typical range: +2% to +4%

4. **Mining and quarrying**
   - Drivers: Resource extraction, commodity prices, global demand
   - Typical range: +1% to +3%

5. **Non-ferrous metals** (aluminum, copper, etc.)
   - Drivers: Electrification, renewable energy infrastructure, electronics
   - Typical range: +2% to +4%

6. **Textile and leather**
   - Drivers: Population, consumption patterns, fast fashion vs. sustainability
   - Typical range: +1% to +3%

7. **Transport equipment** (vehicles, ships, aircraft manufacturing)
   - Drivers: Mobility demand, economic growth, electrification transition
   - Typical range: +1% to +3%

8. **Wood and wood products**
   - Drivers: Construction, furniture, packaging, sustainable material shifts
   - Typical range: +1% to +2%

9. **Other industries** (Industry n.e.s - not elsewhere specified)
   - UNSD catch-all category for unclassified industrial activities
   - Includes: Small-scale manufacturing, handicrafts, country-specific industries
   - Typical range: Highly variable (-2% to +3%, country-dependent)
   - **Note**: May show data discontinuities due to sector reclassifications

**Note**: Actual values are **country-specific** and calculated dynamically from UNSD data.

---

## 📊 Example: IQR Method in Action

### Morocco - Food and Tobacco Sector

**Raw CAGR values from rolling windows** (hypothetical example):
```
2011-2016: +2.1%
2012-2017: +2.5%
2013-2018: +2.3%
2014-2019: -8.2%  ← Outlier (COVID impact?)
2015-2020: +1.9%
2016-2021: +2.0%
2017-2022: +2.4%
2018-2023: +2.2%
```

**IQR Analysis**:
- Q1 (25th percentile): 2.0%
- Q3 (75th percentile): 2.4%
- IQR: 0.4%
- Lower bound: 2.0% - 1.5×0.4% = 1.4%
- Upper bound: 2.4% + 1.5×0.4% = 3.0%

**Capping**:
- -8.2% → 1.4% (capped to lower bound)

**Final CAGR**: Mean of capped values = 2.2%

**Scenario Application**:
- BAU: 2.2% × 1.0 = 2.2%/year
- Progressive: 2.2% × 1.2 = 2.64%/year
- Optimistic: 2.2% × 1.5 = 3.3%/year

---

## 🎯 Detailed vs. Simple: Comparison

| Aspect | Detailed Sectors | Simple Sectors |
|--------|------------------|----------------|
| **Data Source** | Production statistics, SSP scenarios | UNSD energy consumption |
| **Metric** | Physical production (tonnes) | Total energy (TJ) |
| **Granularity** | Country-specific targets | Country-specific historical trends |
| **Method** | Top-down projection from scenarios | Bottom-up from historical data |
| **Robustness** | Depends on scenario quality | Statistical (IQR capping) |
| **Flexibility** | Can model policy impacts explicitly | Limited to multiplier adjustments |
| **Data Availability** | Limited to major industries | Available for all UNSD sectors |

---

## 📁 Quick Reference Files

### CSV Extracts

1. **[production_cagr.csv](cagr_extracts/production_cagr.csv)** (480 rows)
   - All production CAGR values for detailed sectors
   - By sector, country, period, scenario

### How to View Simple Sector Values

Simple sector activity CAGR values are **calculated dynamically** and not stored in config files.

To extract them, run the model with debug logging:

```python
# In calculate_final_energy_demand.py, add print statement:
print(f"  {country}: Activity CAGR = {historical_cagr:.3%}")
```

Or query UNSD data directly using the helper:
```python
from industry.core.cagr_calculator import get_final_energy_cagr_from_unsd

cagr = get_final_energy_cagr_from_unsd('Morocco', 'Food and tobacco')
print(f"Historical activity CAGR: {cagr:.2%}")
```

---

## 🔄 Fallback Behavior

When UNSD data is unavailable for a country-sector combination:

1. **Primary fallback**: Use 1.5% default (IEA/World Bank industrial growth average)
2. **Regional fallback** (future): Use regional average from similar countries
3. **Skip sector**: If no reasonable estimate available

**Current implementation**: Uses 1.5% default without warning

**Recommendation**: Add logging for fallback usage to track data gaps

---

## 📊 Summary: Volume Growth by Sector Type

### Detailed Sectors (Country-Specific)

| Sector | Low Growth | Medium Growth | High Growth |
|--------|-----------|---------------|-------------|
| Steel | -1% to +1% | +2% to +3% | +5% to +8% |
| Ammonia | +1% to +2% | +2% to +3% | +3% to +5% |
| HVC | +1% to +2% | +2% to +3% | +2% to +4% |
| Cement | -2% to +1% | +2% to +4% | +4% to +6% |
| Paper | -1% to +1% | +1% to +2% | +2% to +3% |

*Low = developed/mature, Medium = developing, High = rapid industrialization*

### Simple Sectors (UNSD-Based)

**Historical trends** (before scenario multipliers):
- Typical range: +1% to +3% per year
- Country-specific variation: High (depends on development stage)
- Data quality: Good (UNSD coverage)

**After scenario multipliers**:
- BAU: Historical trend (1.0×)
- Progressive: +20% faster (1.2×)
- Optimistic: +50% faster (1.5×)

---

## 🔄 Update History

| Date | Change | Author |
|------|--------|--------|
| June 2026 | Initial documentation with IQR-capped methodology | Model Team |
| TBD | Regional fallback implementation for UNSD gaps | Pending |
| TBD | Validation against SSP scenario narratives | Pending |

---

## ⚠️ Known Limitations & Future Work

### Current Limitations

1. **Simple sectors**: Single aggregate activity metric, cannot capture sub-sector differences
2. **Scenario multipliers**: Linear scaling may not reflect non-linear policy impacts
3. **Regional variation**: Limited country-specific calibration for simple sectors
4. **Data gaps**: Some countries missing from UNSD, uses blanket fallback

### Future Enhancements

1. **Sub-sector disaggregation**: Break simple sectors into technology-specific pathways
2. **Policy-responsive growth**: Incorporate carbon pricing, efficiency standards effects
3. **Regional calibration**: Develop country archetypes with differentiated growth potential
4. **Dynamic scenarios**: Link to macro-economic models (GDP, population, trade)
5. **Circular economy**: Model material recycling impacts on production demand

---

**Related Documentation**:
- [EFFICIENCY_CAGR_SUMMARY.md](EFFICIENCY_CAGR_SUMMARY.md) - Energy intensity improvements
- [CAGR_SUMMARY.md](CAGR_SUMMARY.md) - Combined overview
- [production_cagr.csv](cagr_extracts/production_cagr.csv) - Detailed sector values
- [IQR Methodology](../core/cagr_calculator.py) - Implementation details
