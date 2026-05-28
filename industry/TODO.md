# Industry Module - Pending Tasks

## High Priority

### 🔴 Fuel Share Methodology Review
**Status:** Pending  
**Context:** Current fuel shares (2020 baseline and future projections) are hardcoded expert assumptions with no documented sources.

**Issue:** 
- UNSD data provides total energy demand per sector, not fuel share percentages
- Reverse engineering fuel shares from aggregate energy demand is problematic
- Need alternative approach for validating/deriving 2020 baseline fuel shares

**Affected Files:**
- `scripts/iron_and_steel/build_shares_steel.py`
- `scripts/chemical_and_petrochemical/ammonia/build_shares_ammonia.py`
- `scripts/non_metallic_minerals/build_shares_cement.py`

**Current Values (2020 baseline):**
- Steel BF+BOF: coal=89%, electricity=7%, gas=3%, diesel=1%
- Steel DR+EAF: electricity=50%, gas=38%, coal=11%, diesel=1%
- Steel Scrap EAF: electricity=100%
- Ammonia SMR+HB: gas=97%, electricity=3%
- Cement: diesel=78%, electricity=12%, biomass=4%, gas=4%, coal=2%

**Possible Solutions:**
1. Source from IEA Energy Technology Perspectives (sector-specific fuel mix tables)
2. Extract from IEA World Energy Balances (manufacturing subsector data)
3. Use industry association reports (WorldSteel, GCCA, IFA)
4. Validate aggregated fuel mix against UNSD totals as consistency check

**Action Items:**
- [ ] Review IEA ETP 2023 for sector-specific fuel shares
- [ ] Check IEA World Energy Balances for manufacturing subsector fuel data
- [ ] Document sources in function docstrings
- [ ] Add validation: aggregate fuel mix should match UNSD when weighted by route shares

---

## Medium Priority

### ✅ Steel Energy Intensity CAGR Validation - COMPLETED
**Status:** ✅ Complete
**Context:** Values updated based on IEA Technology Roadmap - Iron and Steel Sector

**Updated Values (line ~495 in generate_steel_config.py):**
```python
intensity_cagr_config = {
    "Energy intensity of BF+BOF": [0.0, -0.012, -0.022],
    "Energy intensity of DR+EAF": [0.0, -0.015, -0.025],
    "Energy intensity of Scrap EAF": [0.0, -0.015, -0.022],
    "Energy intensity of Casting, rolling & finishing": [0.0, -0.015, -0.022],
}
```

**Source:** IEA Technology Roadmap - Iron and Steel Sector
- Link: https://iea.blob.core.windows.net/assets/imports/events/64/IEARoadmapseries.pdf
- Current: ~20 GJ/t crude steel
- Target: ~10.4 GJ/t (50% reduction potential with energy efficiency slim process)
- Progressive: -1.2% to -1.5%/year → 30-35% reduction by 2050
- Optimistic: -2.2% to -2.5%/year → 48-53% reduction by 2050 (matches IEA target)

**File:** `scripts/iron_and_steel/generate_steel_config.py`

---

### 🟡 Cement Energy Intensity CAGR Validation
**Status:** ⚠️ Needs literature validation  
**Context:** Current values are engineering estimates, not from specific literature sources

**Current Values (line ~378 in generate_cement_config.py):**
```python
intensity_cagr_config = {
    "Energy intensity of Cement production": [0.0, -0.008, -0.015]
    # BAU: 0%, Progressive: -0.8%/year (20% by 2050), Optimistic: -1.5%/year (35% by 2050)
}
```

**Source Status:** Engineering estimates based on general industry knowledge
- Mechanisms identified: clinker substitution, waste heat recovery, alternative fuels
- But specific rates need validation

**Action Items:**
- [ ] Review IEA Technology Roadmap - Cement (2018 or latest edition)
  - Look for: thermal efficiency improvement rates, BAT vs. global average
- [ ] Check GCCA (Global Cement and Concrete Association) Climate Ambition reports
- [ ] Review academic studies on historical cement energy efficiency trends
- [ ] Update values and add specific page/table citations

**File:** `scripts/non_metallic_minerals/generate_cement_config.py`

---

### ✅ CSV File Write Permission Issue - RESOLVED
**Status:** ✅ Complete  
**Resolution:** CSV file was closed, config regeneration successful (2,106 rows written)

**File:** `generate_industry_config.py`

---

## Low Priority / Future Work

### ✅ HVC Sector Integration - COMPLETED
**Status:** ✅ Complete (2,106 total rows: Steel 840 + Ammonia 393 + HVC 519 + Cement 354)

**Files Created:**
- ✅ `scripts/chemical_and_petrochemical/HVC/build_shares_hvc.py` - 3 routes implemented
- ✅ `scripts/chemical_and_petrochemical/HVC/build_energy_intensities_hvc.py` - Intensities: 14/11/16 MWh/t
- ✅ `scripts/chemical_and_petrochemical/HVC/generate_hvc_config.py` - Main orchestrator
- ✅ `generate_industry_config.py` - HVC integrated

**Data Quality Note:**
- industrial_database.csv uses refinery capacities with correction factors
- Egypt 6.1%, South Africa 21%, Morocco 8%, Global 8%
- Represents petrochemical integration ratio (documented in build_hvc_production.py)

---

### 🟢 Paper & Pulp Sector - NEXT UP
**Status:** Not started  
**Priority:** Next industry sector after HVC

**Action Items:**
- [ ] Create production data loader
- [ ] Define technology routes (kraft/sulfite/mechanical pulping)
- [ ] Create fuel share functions
- [ ] Create energy intensity functions
- [ ] Create generate_paper_pulp_config.py
- [ ] Integrate into generate_industry_config.py

### 🟢 Paper & Pulp Sector Integration
**Status:** Planning (after HVC)

**Pattern to Follow:**
1. Create `generate_*_config.py` in appropriate subfolder
2. Use `industry.core.cagr_calculator` for production CAGR
3. Use `industry.core.helpers` for generic row builders
4. Add extensive docstrings documenting methodology
5. Update `generate_industry_config.py` to import and call new generator
6. Test with 4 countries: Morocco, Egypt, South Africa, Namibia

**Action Items:**
- [ ] Decide which sector to integrate next (user preference)
- [ ] Follow cement integration pattern
- [ ] Document all assumptions and data sources clearly

---

### 🟢 Energy Intensity Sources Documentation
**Status:** Needs Review  
**Context:** Energy intensities for each route need source documentation

**Files to Review:**
- `scripts/iron_and_steel/build_energy_intensities_steel.py`
- `scripts/chemical_and_petrochemical/ammonia/build_energy_intensities_ammonia.py`
- `scripts/non_metallic_minerals/build_energy_intensities_cement.py`

**Action Items:**
- [ ] Add source citations for baseline energy intensity values (MWh/t)
- [ ] Document engineering assumptions
- [ ] Cross-reference with IEA sector reports

---

## Completed ✅

- ✅ Created `industry/core/` folder structure
- ✅ Centralized CAGR calculator (`core/cagr_calculator.py`)
- ✅ Moved helpers to `core/helpers.py`
- ✅ Renamed config builders: `generate_steel_config.py`, `generate_ammonia_config.py`
- ✅ Updated 18 imports across codebase
- ✅ Integrated cement sector (354 rows generated successfully)
- ✅ UNSD CAGR working for all test countries
- ✅ Total system test: 1,587 rows (steel + ammonia + cement)

---

## Notes

**Data-Driven vs Expert Assumptions:**
- ✅ Production CAGR: Data-driven from UNSD (2011-2023 historical analysis)
- ❓ Fuel shares: Hardcoded expert assumptions (needs review)
- ❓ Energy intensities: Hardcoded values (needs source documentation)
- ❓ Intensity CAGR: Fixed engineering assumptions (needs literature validation)

**Key Principle:** Maximize data-driven approaches where possible, document all expert assumptions with literature sources.
