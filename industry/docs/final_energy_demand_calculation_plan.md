# Final Energy Demand Calculation from INDUSTRY_CONFIG.csv

## Overview

This document outlines the detailed approach for calculating final energy demand from the new modular INDUSTRY_CONFIG.csv structure and comparing it with the old workflow output.

## Data Structure Analysis

### INDUSTRY_CONFIG.csv (NEW - Long Format)
**Total rows: 6,624** (all countries combined)

**Structure:**
```
Columns: metric_1, metric_2, metric_3, metric_4, year, scenario, units, [Morocco, Egypt, South Africa, Namibia]
```

**Metric Types by Sector:**

**Detailed Sectors:**
- **Iron and Steel**: production (36), cagr (90), technology_route (72), fuel_share (630), intensity_base (12)
- **Chemical & Petrochemical** (Ammonia + HVC): production (54), cagr (90), technology_route (54), fuel_share (630), intensity_base (9)  
- **Non-metallic Minerals** (Cement): production (36), cagr (45), technology_route (18), fuel_share (252), intensity_base (3)
- **Paper, Pulp and Printing**: production (36), cagr (75), technology_route (36), fuel_share (504), activity_factor (18), intensity_base (9)

**Simple Sectors** (8 sectors × 480 rows = 3,840 rows):
- Food and tobacco, Machinery, Construction, Mining & quarrying, Non-ferrous metals, Textile & leather, Transport equipment, Wood & wood products  
- **Only fuel_share rows** (no production/intensity detail)

### Old Output Format (WIDE Format) target_output.csv
**Structure:**
```
Columns: country, scenario, year, carrier, [12 sector columns]
```

**Sectors as columns:**
1. chemical and petrochemical
2. iron and steel  
3. non-metallic minerals
4. paper pulp and print
5. machinery
6. construction
7. non-ferrous metals
8. transport equipment
9. food and tobacco
10. mining and quarrying
11. textile and leather  
12. wood and wood products

**Values:** Energy demand in MWh (or kWh) per carrier per sector

## Calculation Methodology

### For DETAILED Sectors (Steel, Ammonia, HVC, Cement, Paper & Pulp):

**Formula:**
```python
Energy_Demand(country, scenario, year, fuel, sector) = 
    Σ over all routes [
        Production(country, scenario, year) ×
        Route_Share(country, scenario, year, route) ×  
        Intensity(country, route, year_base) ×  # From intensity_base + projections
        Fuel_Share(country, scenario, year, route, fuel)
    ] + Unspecified_Energy(country, scenario, year, fuel, sector)
```

**Data Sources from INDUSTRY_CONFIG.csv:**
1. **Production**: `metric_2='production'`, `metric_3='[Sector] production per year'`
2. **Route Shares**: `metric_2='technology_route'`, `metric_3=[route name]`
3. **Base Intensity**: `metric_2='intensity_base'`, `metric_3=[route name]`, `year=2020`
4. **Intensity Projections**: Load from auto-generated files:
   - `steel_intensity_projections.csv` (72 rows)
   - `ammonia_intensity_projections.csv` (36 rows)
5. **Fuel Shares**: `metric_2='fuel_share'`, `metric_3=[route name]`, `metric_4=[fuel]`
6. **Unspecified**: `metric_2='fuel_share'`, `metric_3='Unspecified [sector]'`, `metric_4=[fuel]`
   - Scaled by activity_factor if present

**Example Calculation (Steel, Morocco, 2030, Optimistic):**

```
Production = 1,249,203 tonnes

Routes:
- BF+BOF: 0% 
- DR+EAF: 100%
- Primary: 80%
- Secondary: 20%

DR+EAF Fuel Shares (for Optimistic 2030):
- natural_gas: 0%
- electricity: 52%
- coal: 0%
- hydrogen: 48%

Base Intensity (DR+EAF, 2020): 20.09 MWh/t  
Intensity Projection (DR+EAF, 2030, Optimistic): ~19.56 MWh/t (after -2.5%/year CAGR)

Energy Demand (electricity) = 1,249,203 t × 0.8 (primary) × 1.0 (DR+EAF) × 19.56 MWh/t × 0.52 (elec share)
                            = ~10,131,000 MWh
```

### For SIMPLE Sectors (8 sectors):

**Formula:**
```python
Energy_Demand(country, scenario, year, fuel, sector) = 
    Historical_Total_Energy(country, 2020) ×  # From UNSD
    (1 + CAGR)^(year - 2020) ×  # Growth projection  
    Fuel_Share(country, fuel, 2020)  # Base year share (no decarbonization path defined yet)
```

**Data Sources:**
1. **Fuel Shares**: `metric_2='fuel_share'`, `metric_3='unspecified [sector]'`, `metric_4=[fuel]`
   - NOTE: Currently replicates base year shares across all years/scenarios
2. **Historical Energy**: Need to read from UNSD data files (not in INDUSTRY_CONFIG.csv)
3. **CAGR**: Use UNSD historical trends (like detailed sectors)

**Limitation:**  
Simple sectors currently DON'T have:
- Production volumes in config
- Total energy baseline in config  
- CAGR projection logic integrated

This means we need to:
- **Option A**: Add production/total_energy rows to simple sector configs
- **Option B**: Read UNSD data separately during final energy calculation
- **Option C**: Accept that simple sectors use base year values (no growth)

## Implementation Plan

### Phase 1: Create Calculation Engine (NEW FILE)

**Create:** `industry/calculate_final_energy_demand.py`

**Functions:**
```python
def calculate_detailed_sector_energy(
    config_df: pd.DataFrame,
    intensity_projections: dict,
    sector: str,
    countries: list,
    years: list,
    scenarios: list
) -> pd.DataFrame:
    """Calculate energy demand for detailed sectors (steel, ammonia, etc.)"""
    # 1. Extract production, routes, intensities, fuel shares
    # 2. Apply formula per route
    # 3. Sum across routes
    # 4. Add unspecified energy
    # 5. Return DataFrame with columns: country, scenario, year, carrier, [sector]
    
def calculate_simple_sector_energy(
    config_df: pd.DataFrame,
    unsd_data_path: Path,
    sector: str,
    unsd_sector_name: str,
    countries: list,
    years: list,
    scenarios: list
) -> pd.DataFrame:
    """Calculate energy demand for simple sectors (food & tobacco, etc.)"""
    # 1. Read UNSD historical total energy
    # 2. Calculate CAGR from historical data
    # 3. Project total energy with CAGR
    # 4. Apply fuel shares from config
    # 5. Return DataFrame

def generate_final_energy_demand_output(
    config_path: Path,
    output_path: Path,
    countries: list = ['Morocco', 'Egypt', 'South Africa', 'Namibia'],
    years: list = [2030, 2035, 2040, 2045, 2050],
    scenarios: list = ['BAU', 'Progressive', 'Optimistic']
) -> pd.DataFrame:
    """Main orchestrator - generates output in old format for comparison"""
    # 1. Load INDUSTRY_CONFIG.csv
    # 2. Load intensity projections
    # 3. Calculate each detailed sector
    # 4. Calculate each simple sector  
    # 5. Concatenate all sectors  
    # 6. Pivot to wide format (sectors as columns)
    # 7. Save CSV in target format
    # 8. Return DataFrame
```

### Phase 2: Comparison & Validation

**Create:** `industry/compare_workflows.py`

**Functions:**
```python
def load_old_output(path: Path) -> pd.DataFrame:
    """Load old workflow output (attached CSV format)"""

def load_new_output(path: Path) -> pd.DataFrame:
    """Load new workflow output"""

def compare_workflows(
    old_df: pd.DataFrame,
    new_df: pd.DataFrame,
    threshold_pct: float = 10.0
) -> dict:
    """
    Compare old vs new workflow results.
    
    Returns:
        dict with keys:
            - 'total_energy_by_sector': DataFrame
            - 'differences': DataFrame  
            - 'relative_error_pct': DataFrame
            - 'large_discrepancies': List of (sector, country, year, scenario, diff_pct)
            - 'summary': Dict with overall stats
    """
    
def visualize_comparison(comparison_results: dict, output_dir: Path):
    """Generate plots comparing old vs new"""
    # 1. Total energy by sector (bar chart)
    # 2. Fuel distribution (stacked bar)
    # 3. Difference heatmap
    # 4. Scatter plot (old vs new)
```

### Phase 3: Diagnose Discrepancies

**Expected Differences:**

1. **Intensity CAGR Changes** (Steel):
   - Old: May have used different intensity reduction rates  
   - New: IEA-validated rates (-2.2% to -2.5%/year Optimistic)
   - Impact: Steel energy demand should be LOWER in new workflow (Optimistic scenario)

2. **HVC Data Quality** (Chemical & Petrochemical):
   - Old: Unknown data source
   - New: Uses refinery capacity with correction factors (Egypt 6%, SA 21%, Morocco 8%)
   - Impact: Production volumes may differ

3. **Paper & Pulp CAGR**:
   - Old: Unknown methodology
   - New: User-researched 19-20% reduction target validated
   - Impact: Should be slightly different

4. **Simple Sectors**:
   - Old: May have had growth projections
   - New: Currently uses base year shares (NO GROWTH unless we add it)
   - Impact: Simple sectors will be CONSTANT across years if not fixed

5. **Fuel Share Sources**:
   - Old: Unknown sources (HIGH PRIORITY in TODO.md)
   - New: Same unknown sources (inherited from old files)
   - Impact: Should be identical if code is correct

## Critical Questions to Answer

### Question 1: Do we need to fix simple sectors before comparing?

**Option A:** Add production/CAGR logic to simple sectors now
- Pros: Complete comparison
- Cons: Delays validation by 1-2 hours

**Option B:** Run comparison with simple sectors at base year values
- Pros: Quick validation of detailed sectors
- Cons: Won't match old output for simple sectors

**Recommendation:** **Option B** - validate detailed sectors first, then fix simple sectors

### Question 2: How to handle intensity projections?

Steel and ammonia have separate intensity projection files. Other sectors apply CAGR in place.

**Approach:**
- Load `steel_intensity_projections.csv` and `ammonia_intensity_projections.csv`
- For other sectors, calculate: `Intensity(year) = Intensity(2020) × (1 + intensity_cagr)^(year - 2020)`

### Question 3: What's an acceptable difference threshold?

**Proposed thresholds:**
- ✅ **< 5%**: Excellent (rounding/methodology tweaks)
- ⚠️ **5-15%**: Acceptable (different data sources/CAGR)
- ❌ **> 15%**: Investigate (likely calculation error)

## Next Steps

1. **Review this analysis** - Confirm approach makes sense
2. **Decide on simple sectors** - Fix now or validate detailed sectors first?
3. **Implement Phase 1** - Create calculation engine  
4. **Run Phase 2** - Compare outputs
5. **Phase 3** - Diagnose and document differences
6. **Iterate** - Fix issues and re-compare

## Files to Create

1. `industry/calculate_final_energy_demand.py` (~400 lines)
2. `industry/compare_workflows.py` (~200 lines)
3. `industry/docs/workflow_comparison_report.md` (auto-generated)

## Estimated Time

- Phase 1: 2-3 hours (implementation + testing)
- Phase 2: 30 minutes (comparison runs)
- Phase 3: 1-2 hours (diagnosis + fixes)
- **Total: 4-6 hours**

---

**DECISION NEEDED:** Should we proceed with implementing this approach?
