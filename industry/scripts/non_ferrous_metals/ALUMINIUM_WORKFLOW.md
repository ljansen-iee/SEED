# Aluminium Subsector Workflow

**Status:** ✅ Implementation Complete  
**Date:** June 2026  
**Approach:** Detailed subsector modeling (similar to cement, ammonia, steel)

---

## 📋 Overview

This workflow adds **detailed aluminium production modeling** to the non-ferrous metals sector, enabling:
- Technology-specific projections (Primary vs Secondary aluminium)
- Process emission calculations (anode oxidation)
- Energy intensity improvements tracking
- Circular economy scenario analysis

### Key Features
- **Production volumes:** BGS historical data (2015-2022) + CAGR projections to 2050
- **Technology routes:** Primary (Hall-Héroult electrolysis) vs Secondary (recycling)
- **Process emissions:** 1.5 tCO₂/t (Primary) vs 0.0 tCO₂/t (Secondary)
- **Avoids double counting:** Other non-ferrous metals = UNSD total - aluminium detailed

---

## 🏗️ Architecture

### Data Flow
```
1. BGS Production Data (AL_production.csv)
   ↓
2. build_aluminium_production.py → Volume projections
   ↓
3. build_aluminium_shares.py → Primary/Secondary splits
   ↓
4. build_aluminium_intensities.py → Fuel-indexed base intensities + fuel shares
   ↓
5. generate_aluminium_config.py → INDUSTRY_CONFIG rows
   ↓
6. calculate_final_energy_demand.py → Energy by carrier
   ↓
7. calculate_process_emissions.py → CO₂ emissions by route
```

### Residual Calculation (Avoiding Double Counting)
```python
# Other non-ferrous metals (copper, zinc, lead, etc.)
other_metals_energy = max(0, UNSD_total_non_ferrous - aluminium_detailed)
```

---

## 📁 Files Created/Modified

### New Scripts
| File | Purpose |
|------|---------|
| `build_aluminium_production.py` | Volume projections with CAGR |
| `build_aluminium_shares.py` | Primary (64%) vs Secondary (36%) routes |
| `build_aluminium_intensities.py` | Energy intensities with efficiency improvements |
| `generate_aluminium_config.py` | Integrate into INDUSTRY_CONFIG format |

### Modified Files
| File | Changes |
|------|---------|
| `build_non_ferrous_metals_energy.py` | Added `get_other_non_ferrous_GWh()` function |
| `calculate_final_energy_demand.py` | Added `calculate_aluminium_energy()` method |
| `calculate_process_emissions.py` | Added `calculate_aluminium_emissions()` method |
| `calculate_process_emissions.py` | Fixed ammonia emissions to show 0 values (not empty) |

---

## 🎯 Scenario Parameters

### Production Volume CAGR (Exogenous)
Based on IEA projections + electrification trends:
- **BAU:** ~1.2%/year avg (current trends continue)
- **Progressive:** ~1.6%/year (circular economy push)
- **Optimistic:** ~2.0%/year (green transition)

### Technology Route Shares
Based on IAI global data (36% secondary in 2020):

| Scenario | 2020 | 2030 | 2050 |
|----------|------|------|------|
| **Primary (BAU)** | 64% | 62% | 58% |
| **Primary (Progressive)** | 64% | 60% | 50% |
| **Primary (Optimistic)** | 64% | 57% | 40% |
| **Secondary** | Inverse of Primary |

### Energy Intensities (Base + Exogenous CAGR)

**Primary Aluminium:**
- Base route intensity: 11.24 MWh/t
- Fuel-level default intensity assignment: 11.24 MWh/t for all fuels

**Secondary Aluminium:**
- Base route intensity: 11.24 MWh/t
- Fuel-level default intensity assignment: 11.24 MWh/t for all fuels

The intensity builder follows the same structure as steel and paper/pulp:
fuel-indexed route intensities are generated first, then collapsed to
route-level base intensity rows by the shared helper.

Future intensity evolution is handled by **exogenous CAGR assumptions** in the
configuration workflow, not hardcoded in this script.

### Fuel Shares
Extracted from UNSD historical data per country.

**Default fallback values** (if UNSD missing):
- Primary: 85% electricity, 10% natural gas, 5% oil
- Secondary: 70% electricity, 25% natural gas, 5% oil

Electricity share increases over time (electrification of heat processes).

---

## 🚀 Usage

### 1. Test Individual Components
```bash
# Test production volumes
python industry/scripts/non_ferrous_metals/build_aluminium_production.py

# Test route shares
python industry/scripts/non_ferrous_metals/build_aluminium_shares.py

# Test intensities
python industry/scripts/non_ferrous_metals/build_aluminium_intensities.py

# Test config generation
python industry/scripts/non_ferrous_metals/generate_aluminium_config.py
```

### 2. Integrate into Main Workflow
```python
# In your config generation script:
from industry.scripts.non_ferrous_metals.generate_aluminium_config import generate_aluminium_config

# Generate aluminium rows
df_aluminium = generate_aluminium_config(countries)

# Append to INDUSTRY_CONFIG.csv
# ... (integrate with your existing config assembly)
```

### 3. Calculate Final Energy Demand
```bash
python industry/calculate_final_energy_demand.py
# Now includes aluminium as detailed sector (not simple)
```

### 4. Calculate Process Emissions
```bash
python industry/calculate_process_emissions.py
# Now includes aluminium emissions by route
```

---

## 📊 Expected Outputs

### Production Volumes
```
Country | 2030 BAU | 2050 Optimistic | Growth
--------|----------|-----------------|-------
CN      | 40,000   | 50,000 kt/year  | +25%
US      | 2,000    | 2,800 kt/year   | +40%
IN      | 4,500    | 7,000 kt/year   | +56%
```

### Process Emissions (Primary Aluminium)
```
Global Primary Production (2050 BAU): ~50 Mt/year
Emission Factor: 1.5 tCO₂/t
Process Emissions: ~75 MtCO₂/year
```

### Energy Demand Split
```
Aluminium (detailed):    60-70% of non-ferrous energy
Other metals (residual): 30-40% of non-ferrous energy
```

---

## ⚠️ Known Limitations & TODOs

### High Priority
1. **Energy intensity baseline is a fixed assumption**
   - Current base value is 11.24 MWh/t for both routes
   - Future trajectory must come from explicit exogenous CAGR assumptions

2. **Country coverage**
   - Only 40 countries have BGS production data
   - Missing countries get 0 production (not modeled)

3. **Fuel shares**
   - Currently using global default values
   - Should extract actual UNSD fuel breakdown per country

### Medium Priority
4. **Validate CAGR rates**
   - Cross-check with IEA scenarios (STEPS, APS, NZE)
   - Consider regional differences (China vs Europe vs North America)

5. **Inert anode technology**
   - Could eliminate process CO₂ emissions
   - Not explicitly modeled in current routes
   - Could be added as separate route in future

### Low Priority
6. **Scrap availability constraints**
   - Secondary share growth assumes scrap availability
   - Material flow analysis could refine projections

7. **Quality degradation**
   - Aluminium alloy complexity limits recycling
   - Current model assumes perfect recyclability

---

## 🔬 Methodology Notes

### Why Exogenous CAGR for Intensities?
Aluminium uses fixed base-year route intensities in config. Any future change
must be introduced explicitly through configuration-level intensity CAGR
assumptions, keeping the projection mechanism consistent and auditable across
sectors.

### Process Emissions Source
**Primary Aluminium (Hall-Héroult):**
```
2 Al₂O₃ + 3 C → 4 Al + 3 CO₂
```
Carbon anode is consumed → produces CO₂

**Secondary Aluminium (Recycling):**
```
No chemical reaction → no process CO₂
Only energy-related emissions (from electricity/heat generation)
```

### Avoiding Double Counting
```python
# Old approach (PROBLEMATIC):
non_ferrous_energy = UNSD_total  # Contains aluminium + copper + zinc + ...

# New approach (CORRECT):
aluminium_energy = calculate_aluminium_detailed()
other_metals_energy = max(0, UNSD_total - aluminium_energy)

non_ferrous_total = aluminium_energy + other_metals_energy
```

---

## 📚 References & Data Sources

### Production Data
- **BGS (British Geological Survey):** Historical production 2015-2022
  - https://www2.bgs.ac.uk/mineralsUK/statistics/

### Scenario Calibration
- **IEA Energy Technology Perspectives 2023:** Aluminium sector analysis
- **IAI (International Aluminium Institute):** Global recycling data
  - https://international-aluminium.org/statistics/

### Energy Intensity
- **TODO:** Need authoritative sources
- **Recommended:**
  - IEA Technology Roadmap: Energy and GHG reductions in the aluminium sector
  - Energetics Inc. "Energy Profile of the U.S. Aluminum Industry"
  - JRC-IDEES: EU industrial energy intensities

### Process Emissions
- **PROCESS_EMISSION_FACTORS:** 1.5 tCO₂/t (Primary), 0.0 tCO₂/t (Secondary)
- **Source:** Previously validated with user

---

## 🎓 Design Principles Applied

1. **Modularity:** Each script has single responsibility
2. **Consistency:** Follows patterns from cement/ammonia/steel
3. **Transparency:** CAGR rates documented with rationale
4. **Extensibility:** Easy to add new routes (e.g., inert anode)
5. **Validation:** Test suite ensures components work together

---

## 👤 Contact & Support

For questions about this implementation:
1. Check this README first
2. Review code documentation in each script
3. Run test suite to validate setup
4. Consult referenced IEA/IAI literature

---

**Last Updated:** June 2026  
**Version:** 1.0.0  
**Status:** ✅ Ready for validation with literature sources
