# Industry Module - Pending Tasks

## 📌 Recent Updates

### ✅ Data Centralization - COMPLETED (June 4, 2026)
**Status:** ✅ Industry sector complete | ⏳ Transport & Residential pending  

**What Changed:**
- UNSD historical data now accessed from centralized location
- **Old Path:** `industry/input_data/unsdata_historical/`
- **New Path:** `../data/country_specific/` (project root)

**Files Updated:**
- ✅ `industry/utils/cagr_calculator.py` - CAGR calculations
- ✅ `industry/scripts/calculate_final_energy_demand.py` - Simple sector projections

**Benefits:**
- Single source of truth for UNSD data across all sectors
- No duplicate 100+ MB CSV files
- Easier to update when new UNSD data releases

**Next Steps:**
- See [`../DATA_CENTRALIZATION_TODO.md`](../DATA_CENTRALIZATION_TODO.md) for transport/residential migration plan
- Test that CAGR calculations work with centralized path
- Consider removing `industry/input_data/unsdata_historical/` after validation

---

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

### ✅ Paper & Pulp Energy Intensity CAGR Validation - COMPLETED
**Status:** ✅ Complete
**Context:** Values updated based on China Energy Partnership Technical Guideline

**Updated Values (line ~278 in generate_paper_pulp_config.py):**
```python
intensity_cagr_config = {
    "Energy intensity of Primary pulp": [0.0, -0.006, -0.008],
    "Energy intensity of Secondary pulp": [0.0, -0.005, -0.007],
    "Energy intensity of Paper production": [0.0, -0.0055, -0.0075],
}
```

**Source:** China Energy Partnership (2021) - Technical Guideline Energy Efficiency
- Link: https://energypartnership.cn/fileadmin/china/media_elements/publications/2021/Technical_Guideline_Energy_Efficiency_Pulp_and_Paper_EN.pdf
- Target: 19-20% energy demand reduction by 2050
- Progressive: -0.5% to -0.6%/year → 14-17% reduction by 2050
- Optimistic: -0.7% to -0.8%/year → 19-21% reduction by 2050 (matches target)

**File:** `scripts/paper_and_pulp/generate_paper_pulp_config.py`

---

### ✅ CSV File Write Permission Issue - RESOLVED
**Status:** ✅ Complete  
**Resolution:** CSV file was closed, config regeneration successful (2,784 rows written)

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

### ✅ Paper & Pulp Sector Integration - COMPLETED
**Status:** ✅ Complete (2,784 total rows: Steel 840 + Ammonia 393 + HVC 519 + Cement 354 + Paper & Pulp 678)

**Files Created:**
- ✅ `scripts/paper_and_pulp/generate_paper_pulp_config.py` - Main orchestrator (~580 lines)
- ✅ Integration into `generate_industry_config.py` complete

**Existing Files Used:**
- `scripts/paper_and_pulp/build_paper_and_pulp_production.py` - FAO data loader
- `scripts/paper_and_pulp/build_share_primary_pulp.py` - Fuel shares & primary/secondary ratios
- `scripts/paper_and_pulp/build_energy_intensities_paper_pulp.py` - Intensity functions

**Intensity CAGR Source:**
- China Energy Partnership (2021) - Technical Guideline Energy Efficiency
- Link: https://energypartnership.cn/fileadmin/china/media_elements/publications/2021/Technical_Guideline_Energy_Efficiency_Pulp_and_Paper_EN.pdf
- Target: 19-20% reduction by 2050

---

### 🔵 Fuel-Specific Efficiency Curves  
**Status:** Future Enhancement  
**Context:** Current intensity CAGR applies uniformly across all fuel types, but improvement rates differ

**Issue:**
- Electrification improvements are faster than fossil fuel efficiency gains
- Current model: Single CAGR applies to all fuels equally
- Reality: Electricity efficiency and renewable power integration improve rapidly
- Fossil fuels: Limited efficiency gains (already near thermodynamic limits)

**Example Differentiation:**
- Electricity intensity CAGR: -1.5% to -2.5%/year (renewable integration, process electrification)
- Fossil fuel intensity CAGR: -0.3% to -0.8%/year (marginal efficiency, waste heat recovery)

**Affected Sectors:**
- Steel (electricity vs coal/gas in EAF vs BF)
- Paper & Pulp (electricity vs biomass/gas in pulping/drying)
- Cement (electricity vs coal/diesel in grinding vs kilns)
- All sectors where fuel mix transitions occur

**Implementation Approach:**
1. Modify intensity CAGR config structure to support per-fuel rates
2. Update `build_intensity_base_rows()` and `build_cagr_rows()` in `core/helpers.py`
3. Adjust intensity projection functions to handle fuel-specific curves
4. Document methodology change in sector docstrings

**Action Items:**
- [ ] Research IEA/literature for fuel-specific efficiency improvement rates
- [ ] Design data structure for per-fuel CAGR config
- [ ] Implement modified row builders
- [ ] Test with pilot sector (steel or paper & pulp)
- [ ] Roll out to remaining sectors

---

### 🟢 Additional Industry Sectors (Future)
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
