# "OTHER" SECTOR FIX - UNSD Sector Name Mapping

## Issue
"Other" sector (Industry n.e.s.) was generating **0 records** despite having fuel share configuration and UNSD historical data available.

## Root Cause: Ambiguous UNSD Sector Name Lookup

### The Problem
1. **Config standardization**: generate_industry_config.py renamed 'industry n.e.s' → 'other'
2. **UNSD lookup**: calculate_simple_sector_energy() called `get_historical_sector_data(country, 'other')`
3. **Substring matching**: helpers.py uses `str.contains()` for sector name matching
4. **Wrong match**: Searching for 'other' matched **"Other Consumption"** (negative values: -160 GWh) instead of **"Industry n.e.s"** (correct values: 471 GWh for Morocco 2020)

### Why This Failed
UNSD files contain multiple sectors with "other" in the name:
- ❌ "Other Consumption" (first match - wrong sector!)
- ❌ "Other transformation"
- ❌ "Other consumption n.e.s"  
- ✅ "Industry n.e.s" (correct sector - not matched!)

The substring match returned the FIRST match ("Other Consumption"), which had:
- Negative energy values (energy subtracted from total)
- Wrong sector classification (residential/commercial, not industrial)

## The Fix

**Added CONFIG_TO_UNSD_SECTOR mapping** in calculate_final_energy_demand.py:

```python
# Map INDUSTRY_CONFIG metric_1 names to UNSD sector names for data lookup
# CRITICAL: UNSD uses different names than our standardized config
CONFIG_TO_UNSD_SECTOR = {
    'other': 'Industry n.e.s',  # FIX: 'other' renamed from 'industry n.e.s' during standardization
    # Other sectors use same names in both config and UNSD, no mapping needed
}
```

**Updated calculate_simple_sector_energy()** to use mapping:

```python
# Before calling UNSD lookup:
unsd_sector_name = CONFIG_TO_UNSD_SECTOR.get(sector_config_name, sector_config_name)

# Use mapped name for all UNSD data access:
historical_data = get_historical_sector_data(unsd_path, country, unsd_sector_name)
historical_cagr = get_final_energy_cagr_from_unsd(country, unsd_sector_name)
```

## Results

### Before Fix:
- **Records:** 0 (no data generated)
- **Error:** Wrong UNSD sector matched, negative/invalid energy values
- **Total:** 2,104 records (12 of 13 sectors)

### After Fix:
- **Records:** 195 new records ✅
- **Total:** 2,299 records (+9.2%, **all 13 sectors working**)
- **Data quality:** Positive, realistic energy values

### Energy Output:
**Morocco (example: 2030 BAU):** 229 GWh  
**Total (all countries/years/scenarios):** 1,306 TWh

**Carrier breakdown (total):**
- Electricity: 425 TWh (42.5%)
- Oil: 350 TWh (35.0%)
- Gas: 318 TWh (31.8%)
- Coal: 118 TWh (11.8%)
- Biomass: 96 TWh (9.6%)

## Industries in "Other" Sector

According to UNSD classification, **"Industry n.e.s" (not elsewhere specified)** is a catch-all category for miscellaneous industrial manufacturing activities not classified in specific sectors:

1. **Furniture manufacturing**
2. **Plastics and rubber products** (non-HVC petrochemicals)
3. **Printing and publishing** (separate from pulp/paper production)
4. **Metal fabrication and assembly** (not primary metal production)
5. **Electronics and appliances**
6. **Other manufacturing n.e.s.**

This is typically a small residual sector representing diverse light manufacturing activities.

## Technical Details

**Files Modified:**
- industry/scripts/calculate_final_energy_demand.py
  - Lines 17-24: Added CONFIG_TO_UNSD_SECTOR mapping
  - Line 840: Map config name before get_historical_sector_data()
  - Line 857: Map config name before get_final_energy_cagr_from_unsd()

**Dependencies:**
- industry/utils/helpers.py (get_historical_sector_data - uses str.contains())
- industry/utils/cagr_calculator.py (get_final_energy_cagr_from_unsd)
- data/country_specific/UNSD_{Country}-{Year}.csv (UNSD sector names)

## Lessons Learned

1. **Explicit is better than implicit:** When standardizing names, maintain bidirectional mappings for data lookups
2. **Substring matching is fragile:** Consider exact matching or ranking by relevance
3. **Test edge cases:** "Other" is inherently ambiguous - validate data lookup results
4. **Document name changes:** Track original vs. standardized names throughout pipeline

## Impact

**Status:** ✅ **ALL 13 INDUSTRIAL SECTORS NOW WORKING**

This fix completes the 13-sector industrial energy demand model, making it production-ready for PyPSA network modeling and scenario analysis.

**Date Fixed:** June 8, 2026  
**Total Development Time:** ~30 minutes (diagnosis + fix + validation)
