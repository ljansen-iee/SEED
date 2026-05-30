# Phase 1 Validation Results: Final Energy Demand Calculation

## Executive Summary

✅ **Successfully created calculation engine** for final energy demand from INDUSTRY_CONFIG.csv  
⚠️ **MAJOR DISCREPANCIES FOUND** between old and new workflow outputs  
🔍 **ROOT CAUSES IDENTIFIED** - fixable issues in data structure and calculation logic  

---

## What We Built

### Files Created:

1. **`calculate_final_energy_demand.py`** (470 lines)
   - Core calculation engine reading INDUSTRY_CONFIG.csv
   - Loads intensity projections from interim_data/
   - Calculates energy per country/scenario/year/carrier/sector
   - Outputs both long and wide format CSV files

2. **`compare_workflows.py`** (90 lines)
   - Compares old vs new workflow outputs
   - Calculates differences, ratios, and percentage changes
   - Generates sector-by-sector comparison tables

3. **`debug_steel_calculation.py`** (130 lines)
   - Detailed trace through steel sector calculation
   - Shows production, routes, intensities, fuel shares step-by-step
   - Helped identify root cause of discrepancies

### Output Files Generated:

- `final_energy_demand_detailed_sectors_long.csv` (645 rows)
- `final_energy_demand_detailed_sectors_wide.csv` (60 rows)

---

## Comparison Results: Morocco Optimistic 2030

### Iron and Steel Sector

| Carrier | Old Workflow (MWh) | New Workflow (MWh) | Ratio | Status |
|---------|-------------------|-------------------|-------|---------|
| Oil | 241,967 | 0.26 | 0.000001× | ❌ BROKEN |
| Gas | 51,007 | 0.04 | 0.000001× | ❌ BROKEN |
| Electricity | 1,093,837 | 4,517,370 | **4.13×** | ❌ TOO HIGH |
| Coal | 309,956 | 0.05 | 0.000002× | ❌ BROKEN |
| Biomass | 67,933 | 0 | 0× | ❌ MISSING |
| Hydrogen | 1,771,131 | 20,579,130 | **11.62×** | ❌ TOO HIGH |
| Steel | 930,000 | 0 | 0× | ❌ MISSING |
| **TOTAL** | **4,465,831** | **25,096,498** | **5.62×** | ❌ BROKEN |

### Chemical and Petrochemical Sector

| Carrier | Old Workflow (MWh) | New Workflow (MWh) | Status |
|---------|-------------------|-------------------|---------|
| Oil | 0 | 0 | ✅ Match |
| Gas | 2,368,082 | 0 | ❌ MISSING |
| Electricity | 244,306 | 0 | ❌ MISSING |
| Hydrogen | 315,298 | 0 | ❌ MISSING |
| Ammonia | 3,032,777 | 0 | ❌ MISSING |
| **TOTAL** | **5,960,464** | **0** | ❌ **ZERO OUTPUT!** |

### Non-metallic Minerals (Cement)

| Carrier | Old Workflow (MWh) | New Workflow (MWh) | Status |
|---------|-------------------|-------------------|---------|
| Oil | 8,736,636 | 0.59 | ❌ BROKEN |
| Gas | 244,587 | 0.05 | ❌ BROKEN |
| Electricity | 3,481,284 | 0.30 | ❌ BROKEN |
| Biomass | 668,537 | 0.05 | ❌ BROKEN |
| Hydrogen | 239,695 | 0.01 | ❌ BROKEN |
| **TOTAL** | **13,370,739** | **1** | ❌ **~ZERO OUTPUT!** |

### Paper, Pulp and Printing

| Carrier | Old Workflow (MWh) | New Workflow (MWh) | Status |
|---------|-------------------|-------------------|---------|
| Oil | 131,584 | 0.17 | ❌ BROKEN |
| Gas | 35,471 | 0.42 | ❌ BROKEN |
| Electricity | 798,656 | 0.40 | ❌ BROKEN |
| Biomass | 986,917 | 0.00 | ❌ MISSING |
| Hydrogen | 19,223 | 0.01 | ❌ BROKEN |
| **TOTAL** | **1,971,850** | **1** | ❌ **~ZERO OUTPUT!** |

---

## Root Causes Identified

### Issue 1: Technology Route Structure Mismatch

**Problem:** Steel sector has hierarchical routes but calculation treats them as flat list

**INDUSTRY_CONFIG.csv structure:**
```
technology_route rows:
- BF+BOF: 0%
- DR+EAF: 100%
- Primary steel production: 80%
- Secondary steel production: 20%
```

**What this SHOULD mean:**
- 80% Primary production → split between BF+BOF (0%) and DR+EAF (100%)
- 20% Secondary production → all Scrap EAF

**What the code DOES:**
- Treats all 4 as independent routes
- Tries to find intensity for "Primary steel production" (doesn't exist!)
- Fails to match routes with intensity projection file

**Solution needed:** Understand the intended route hierarchy and implement proper nesting logic

---

### Issue 2: Missing Intensity Matches

**Problem:** Intensity projection file uses route names like:
```
"Energy intensity of BF+BOF"
"Energy intensity of DR+EAF"
"Energy intensity of Scrap EAF"
"Energy intensity of Casting, rolling & finishing"
```

But technology routes in INDUSTRY_CONFIG.csv don't include "Casting, rolling & finishing" or "Scrap EAF" as separate routes.

**Result:** Intensities not found → energy calculation returns 0

---

### Issue 3: Chemical Sector Has Zero Production

**Morocco production values (2030 Optimistic):**
- Ammonia production: **0.0 tonnes** (Morocco imports ammonia, doesn't produce it)
- HVC production: **726,465 tonnes** (Morocco DOES produce HVC)

**Problem:** Code searches for generic "chemical and petrochemical" production, but config separates:
- `metric_1='ammonia'` with `metric_3='ammonia production per year'`
- `metric_1='chemical and petrochemical'` with `metric_3='HVC production per year'`

**Solution needed:** 
1. Check if "ammonia" and "chemical and petrochemical" should be separate sectors
2. OR combine them intelligently in calculation
3. Handle countries with no production but imports (Morocco ammonia case)

---

### Issue 4: Tiny Values from Unspecified Energy

**Cement and Paper sectors return values like 0.05, 0.59, 0.40 MWh**

**Trace shows:** These are raw fuel share fractions (not multiplied by production × intensity)

**Problem:** Sectors without proper intensity data are falling back to unspecified energy calculation, which is outputting fractions instead of MWh values

---

### Issue 5: Missing "Steel" Carrier Output

**Old workflow generates:** "steel" carrier with 930,000 MWh for Morocco 2030
**New workflow generates:** 0 MWh

**Likely cause:** This might be "steel as a commodity input" to other industries (e.g., machinery sector uses steel). Need to check if this is part of "Unspecified" calculations or a separate metric.

---

## Questions Requiring Your Input

### Q1: Steel Sector Route Structure

How should the route hierarchy work?

**Option A - Hierarchical (most likely):**
```
Total Production = 1,249,203 tonnes
├─ Primary (80%) = 999,362 tonnes
│  ├─ BF+BOF (0% of primary) = 0 tonnes
│  └─ DR+EAF (100% of primary) = 999,362 tonnes
└─ Secondary (20%) = 249,841 tonnes
   └─ Scrap EAF (100% of secondary) = 249,841 tonnes
```

**Option B - Flat (unlikely):**
```
Total Production split 4 ways:
- BF+BOF: 0%
- DR+EAF: 100%
- Primary: 80% (separate process?)
- Secondary: 20% (separate process?)
```

### Q2: Chemical Sector Structure

Should ammonia and HVC be:
- **Option A:** Combined into single "chemical and petrochemical" sector output
- **Option B:** Separate sectors in final output (add "ammonia" and "HVC" columns)
- **Option C:** Handled specially (some countries produce, some import)

### Q3: Missing Routes in Config

Steel intensity file has these routes:
- BF+BOF
- DR+EAF
- Scrap EAF
- Casting, rolling & finishing

But INDUSTRY_CONFIG.csv only shows:
- BF+BOF
- DR+EAF
- (no Scrap EAF?)
- Casting, rolling & finishing (as separate metric_3 in fuel_share)

**Question:** Where is "Scrap EAF" route defined? Should it be added to technology_route rows?

### Q4: Unspecified Energy Calculation

**Current behavior:** "Unspecified" fuel shares (e.g., 0.65 for electricity) are stored as fractions

**Question:** How should these be scaled to MWh?
- **Option A:** Multiply by production × some base intensity
- **Option B:** They're already in MWh (but data shows fractions?)
- **Option C:** Use activity_factor to scale them

---

## Recommended Next Steps

### Immediate (1-2 hours):

1. **Clarify route structure** with you (Q1-Q4 above)
2. **Fix steel calculation logic** to handle hierarchical routes correctly
3. **Fix chemical sector** to find HVC production data
4. **Add "Scrap EAF"** route if missing from config

### Short-term (2-3 hours):

5. **Debug cement/paper sectors** to fix tiny value outputs
6. **Implement "steel" carrier** output (if it's a real commodity flow)
7. **Re-run comparison** with fixes applied
8. **Validate against Egypt data** (has ammonia production, so chemical sector should work)

### Validation (1 hour):

9. **Compare all 4 countries** across all scenarios
10. **Generate difference report** with acceptable thresholds
11. **Document known differences** (updated CAGR, etc.)

---

## Files for Your Review

### Key outputs to examine:

1. **`compare_workflows.py` output** (shown above) - comparison tables
2. **`debug_steel_calculation.py` output** - detailed trace showing missing intensities
3. **`final_energy_demand_detailed_sectors_wide.csv`** - our generated output

### To reproduce the comparison:

```bash
cd industry
python calculate_final_energy_demand.py  # Generates new output
python compare_workflows.py              # Shows comparison
python debug_steel_calculation.py        # Shows detailed trace
```

---

## Conclusion

**Good News:**
✅ Calculation framework is working and extensible  
✅ Root causes identified (not fundamental design flaws)  
✅ Fixable with 3-5 hours of targeted debugging  

**Action Needed:**
❗ Answer Q1-Q4 about data structure intentions  
❗ Decide if we should fix now or document differences  
❗ Validate if old workflow output is actually correct (it might have bugs too!)  

**This is indeed "a very important step"** - we're discovering that the INDUSTRY_CONFIG.csv structure may not perfectly capture the calculation logic from the old workflow. We need to either:
1. Fix the config structure to match the calculation needs
2. Fix the calculation to interpret the config correctly
3. Document that this is an intentional simplification

**What would you like to focus on first?**
