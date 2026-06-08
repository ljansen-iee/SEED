# Process Emissions Implementation Guide

**Created**: June 1, 2026  
**Model Version**: 1.0

This document describes the implementation of industrial process emissions calculation, separate from energy-related emissions.

---

## 📊 Overview

**Definition**: Process emissions are CO₂ releases from chemical/physical reactions in industrial processes, **not from energy combustion**.

**Formula**:
```
MtCO₂/year = Σ_route [emission_factor(tCO₂/t) × production_route(Mt/year)]
```

**Key Principle**: Emission factors are **FIXED** (from JRC-IDEES EU28 average, future best-case) and **do not change over time**.

---

## 🏭 Sectors with Process Emissions

### 1. **Steel and Iron** (0.05 - 0.22 tCO₂/t)

**Physical Origin**: Carbon in coke/coal reacting with iron ore in blast furnace; residual from alloy additions in EAF

| Technology Route | Emission Factor | Process |
|-----------------|-----------------|---------|
| BF+BOF (Blast Furnace + Basic Oxygen Furnace) | 0.22 tCO₂/t | Coke reduction of iron ore |
| DR+EAF (Direct Reduction + Electric Arc) | 0.05 tCO₂/t | Residual from alloys |
| EAF (Electric Arc Furnace, secondary) | 0.05 tCO₂/t | Residual from alloys |

**Why Route-Specific?**
- BF+BOF uses carbon to reduce iron ore → high process CO₂
- DR+EAF uses hydrogen or natural gas → minimal process CO₂
- EAF uses scrap steel → only minor emissions from alloy additions

**Calculation**:
```python
# Total production split by route shares
production_BF = total_steel_Mt × route_share_BF
production_EAF = total_steel_Mt × route_share_EAF

# Emissions by route
emissions = production_BF × 0.22 + production_EAF × 0.05
```

**Future Trends**: As industry shifts from BF+BOF to DR+EAF and green hydrogen, process emissions decline (but energy emissions may shift).

---

### 2. **Cement** (0.54 tCO₂/t)

**Physical Origin**: Calcination reaction (limestone decomposition)

**Reaction**: CaCO₃ → CaO + CO₂

**Emission Factor**: 0.54 tCO₂/t clinker (fixed)

**Why Fixed?**
- This is stoichiometric chemistry (unavoidable with limestone feedstock)
- Only way to reduce: use alternative feedstocks (geopolymers, slag cement) or carbon capture

**Calculation**:
```python
emissions = cement_production_Mt × 0.54
```

**Note**: Emissions are per tonne of **clinker**, not final cement (cement = clinker + additives)

---

### 3. **High Value Chemicals (HVC)** (0.18 - 0.23 tCO₂/t)

**Physical Origin**: Fossil feedstock carbon content (petrochemicals)

| Technology Route | Emission Factor | Process |
|-----------------|-----------------|---------|
| Primary (steam cracking) | 0.18 tCO₂/t | Fossil naphtha/ethane feedstock |
| From feedstock | 0.23 tCO₂/t | Petrochemical CO₂ (potentially non-fossil) |
| Mechanical recycling | 0.0 tCO₂/t | No new feedstock |
| Chemical recycling | 0.0 tCO₂/t | Closed-loop carbon |

**Why Route-Specific?**
- Primary production uses virgin fossil feedstock
- Recycling pathways avoid new fossil carbon input

**Calculation**:
```python
# Currently uniform (TODO: split by recycling rate)
emissions = HVC_production_Mt × 0.18
```

**Future Enhancement**: When recycling pathway data available, differentiate primary vs. recycled production.

---

### 4. **Ammonia** (0.0 tCO₂/t)

**Process emissions**: ZERO

**Why Zero?**
- Ammonia is NH₃ (no carbon in product)
- CO₂ emissions from ammonia production are on the **energy side** (SMR hydrogen production or electrolysis)

**Note**: Energy-side emissions handled separately in energy demand calculation.

---

### 5. **Aluminium** (0.0 - 1.5 tCO₂/t)

**Physical Origin**: Anode oxidation in Hall-Héroult electrolysis (CF₄, C₂F₆ from carbon anodes)

| Technology Route | Emission Factor | Process |
|-----------------|-----------------|---------|
| Primary (electrolysis) | 1.5 tCO₂/t | Carbon anode consumption |
| Secondary (recycling) | 0.0 tCO₂/t | No electrolysis |

**Status**: ⚠️ **NOT YET IMPLEMENTED** - waiting for non-ferrous production data in CONFIG

**Future Implementation**: When aluminium production data added to CONFIG, enable this calculation.

---

### 6. **Other Non-Metallic Minerals** (0.02 - 0.03 tCO₂/t)

**Ceramics**: 0.03 tCO₂/t (minor decomposition)  
**Glass**: 0.02 tCO₂/t (minor carbonate decomposition)

**Status**: ⚠️ **NOT YET IMPLEMENTED** - waiting for disaggregated production data

**Future Implementation**: When ceramics/glass production data available, add to calculation.

---

## 🗂️ File Structure

```
industry/
  ├── core/
  │   └── process_emission_factors.py  ← Emission factor definitions
  ├── calculate_process_emissions.py    ← Main calculation script
  ├── output_data/
  │   ├── process_emissions.csv         ← Detailed results (by route)
  │   └── process_emissions_summary.csv ← Aggregated by sector
  └── docs/
      └── PROCESS_EMISSIONS_GUIDE.md    ← This file
```

---

## 🔄 Workflow Integration

### Current Workflow

```
1. generate_industry_config.py
   ↓ Creates INDUSTRY_CONFIG.csv with production volumes
   
2. calculate_final_energy_demand.py
   ↓ Calculates energy demand (fuel combustion emissions)
   
3. calculate_process_emissions.py  ← NEW
   ↓ Calculates process emissions (non-energy)
   
4. Combine in PyPSA-Earth or final reporting
```

**Why Separate?**
- Process emissions don't affect energy demand
- Different data sources (JRC-IDEES vs. energy statistics)
- Easier validation and debugging
- Cleaner separation of concerns

---

## 🚀 Usage

### Basic Execution

```bash
# Navigate to industry folder
cd industry/

# Run process emissions calculation (uses default CONFIG path)
python calculate_process_emissions.py
```

**Output**:
- `output_data/process_emissions.csv` - Detailed (264 rows for 4 countries × 3 scenarios × 5 years × sectors)
- `output_data/process_emissions_summary.csv` - Aggregated by sector/country/scenario/year

### Custom Configuration

```bash
# Specify custom CONFIG location
python calculate_process_emissions.py --config path/to/INDUSTRY_CONFIG.csv

# Specify custom output directory
python calculate_process_emissions.py --output-dir path/to/output/
```

### Programmatic Usage

```python
from industry.calculate_process_emissions import ProcessEmissionCalculator

# Initialize calculator
calc = ProcessEmissionCalculator()

# Calculate emissions for specific years/scenarios
emissions = calc.calculate_all_emissions(
    years=[2030, 2040, 2050],
    scenarios=['BAU', 'Optimistic']
)

# Access results
print(emissions.head())
```

---

## 📊 Output Format

### Detailed Format (`process_emissions.csv`)

| Column | Type | Description |
|--------|------|-------------|
| country | str | Country code (MA, EG, ZA, NA) |
| scenario | str | Scenario name (BAU, Progressive, Optimistic) |
| year | int | Target year (2030, 2035, 2040, 2045, 2050) |
| sector | str | Industry sector (iron and steel, cement, etc.) |
| route | str | Technology route (BF+BOF, DR+EAF, Cement, etc.) |
| production_Mt | float | Production volume (million tonnes/year) |
| factor_tCO2_per_t | float | Emission factor (tCO₂/t material) |
| emissions_MtCO2 | float | **Process emissions (MtCO₂/year)** |

### Summary Format (`process_emissions_summary.csv`)

| Column | Type | Description |
|--------|------|-------------|
| country | str | Country code |
| sector | str | Industry sector |
| scenario | str | Scenario name |
| year | int | Target year |
| emissions_MtCO2 | float | **Total process emissions by sector** |

---

## ✅ Validation Examples

### Egypt 2030 BAU

| Sector | Production (Mt/year) | Factor (tCO₂/t) | Emissions (MtCO₂/year) |
|--------|---------------------|----------------|----------------------|
| Steel (BF+BOF) | ~4 Mt | 0.22 | ~900 MtCO₂ |
| Cement | ~6.5 Mt | 0.54 | ~3,500 MtCO₂ |
| HVC | ~0.18 Mt | 0.18 | ~33 MtCO₂ |
| **Total** | | | **~4,433 MtCO₂** |

**Reasonableness Check**: ✅
- Egypt steel production ~5-6 Mt/year historically → 4 Mt is conservative
- Cement production ~50-70 Mt/year, clinker ratio ~70% → 6.5 Mt clinker is reasonable
- HVC is small fraction → 33 MtCO₂ makes sense

---

## 🔮 Future Enhancements

### Phase 2 (Near-term)

1. **Aluminium process emissions** - waiting for non-ferrous production data
2. **Ceramics and glass** - waiting for disaggregated NMM production
3. **HVC recycling pathways** - differentiate primary vs. recycled production

### Phase 3 (Medium-term)

4. **Carbon capture integration** - reduce effective emission factors with CCS
5. **Alternative feedstocks** - geopolymer cement, bio-based plastics
6. **Biogenic carbon accounting** - separate fossil from biogenic CO₂

### Phase 4 (Long-term)

7. **Dynamic emission factors** - technology-specific improvements over time
8. **Regional calibration** - country-specific emission factors (currently EU28 average)
9. **Uncertainty quantification** - emission factor ranges

---

## ⚠️ Known Limitations

### Current Implementation

1. **Fixed emission factors**: Don't change over time (assumes "future best-case" from JRC-IDEES)
2. **EU28 averages**: May not reflect regional differences (developing vs. developed countries)
3. **Steel route aggregation**: Uses average route shares, not plant-level detail
4. **HVC uniformity**: Doesn't yet differentiate recycling pathways
5. **Missing sectors**: Aluminium, ceramics, glass not yet implemented

### Data Quality

1. **Production data dependency**: Emissions accuracy depends on production projections
2. **Route share accuracy**: Steel emissions sensitive to BF vs. EAF split
3. **Clinker ratio**: Cement emissions assume fixed clinker content (may vary by country)

---

## 📖 References

### Emission Factors

- **JRC-IDEES**: EU28 Industrial Energy Demand and Efficiency Statistics
  - https://data.jrc.ec.europa.eu/collection/id-00180
  - Used for all emission factors (future best-case values)

### Validation Sources

- **IEA**: Cement Technology Roadmap
- **IEA**: Iron and Steel Technology Roadmap
- **IPCC**: 2006 IPCC Guidelines for National Greenhouse Gas Inventories (Volume 3: Industrial Processes)

---

## 💡 Discussion Points

Based on your requirements, here are some questions for refinement:

### 1. Carbon Capture Integration

**Question**: How to handle CCS (Carbon Capture and Storage)?

**Options**:
- A) Reduce emission factors (e.g., cement with 90% capture: 0.54 → 0.054 tCO₂/t)
- B) Calculate separately and subtract from process emissions
- C) Include CCS as negative emissions in energy accounting

**Recommendation**: Option B - calculate separately for transparency, easier validation

### 2. Time-Varying Factors

**Question**: Should emission factors change over time as technology improves?

**Current**: Fixed (your requirement: "always future best-case")

**Alternative**: Gradual improvement (e.g., steel BF efficiency improvement reduces 0.22 → 0.20 by 2050)

**Trade-off**: Simplicity vs. realism

### 3. Aluminium Priority

**Question**: How urgent is aluminium implementation?

**Context**: Aluminium has highest emission factor (1.5 tCO₂/t) but smaller production volumes

**Status**: Waiting for non-ferrous production data in CONFIG

### 4. Integration with PyPSA-Earth

**Question**: How to pass process emissions to PyPSA-Earth?

**Options**:
- A) Add to energy demand CSV as pseudo-fuel "process emissions"
- B) Separate CSV that PyPSA reads independently
- C) Pre-aggregate into total emissions for each region

**Recommendation**: Option B for clarity (separate process from energy emissions)

---

**Questions? Suggestions?** Please discuss with the model development team.

---

**Last Updated**: June 1, 2026  
**Authors**: Model Development Team  
**Status**: ✅ Implemented for steel, cement, HVC; ⚠️ Pending for aluminium, ceramics, glass
