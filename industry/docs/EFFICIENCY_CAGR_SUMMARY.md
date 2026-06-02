# Efficiency CAGR Summary - Energy Intensity Improvements
**Generated: June 2026**  
**Model Version: 1.0**

This document summarizes the **energy efficiency improvement rates** (intensity CAGR) used across all industry sectors. These represent technological improvements that reduce energy consumption per unit of production.

---

## 📊 Overview

**Definition**: Efficiency CAGR represents the annual rate of improvement in energy intensity (MWh per tonne of production).

- **Negative values** = Improvement (less energy needed per unit)
- **Zero** = No improvement (business-as-usual inertia)
- **Applied to**: Energy intensities for specific technology routes

**Formula**:
```
Intensity(year) = Base_Intensity(2020) × (1 + efficiency_CAGR)^(year - 2020)
```

---

## 🏭 DETAILED SECTORS

### 1. Steel (Iron and Steel)

**Source**: IEA Technology Roadmap - Iron and Steel Sector  
**Target**: 50% energy intensity reduction by 2050 (20 GJ/t → 10.4 GJ/t)

| Technology Route | BAU | Progressive | Optimistic |
|-----------------|-----|-------------|------------|
| BF+BOF (Blast Furnace + Basic Oxygen Furnace) | 0.0% | -1.2%/year | -2.2%/year |
| DR+EAF (Direct Reduction + Electric Arc Furnace) | 0.0% | -1.5%/year | -2.5%/year |
| Scrap+EAF (Scrap-based Electric Arc Furnace) | 0.0% | -1.5%/year | -2.2%/year |
| Casting, rolling & finishing | 0.0% | -1.5%/year | -2.2%/year |

**Scenario Interpretation**:
- **BAU**: No improvement - inertia in developing countries, limited investment
- **Progressive**: ~30-35% reduction by 2050 - waste heat recovery, process optimization, partial fuel switching
- **Optimistic**: ~48-53% reduction by 2050 - hydrogen-based DRI, advanced EAF, comprehensive heat recovery (matches IEA "energy efficiency slim process" target)

**Data Location**: 
- Config: `INDUSTRY_CONFIG.csv`, `metric_2='cagr'`, `metric_3` contains "Energy intensity"
- Projections: `industry/output_data/interim_data/steel_intensity_projections.csv`

---

### 2. Ammonia (Chemical and Petrochemical)

**Source**: Engineering assumptions  
**Note**: Conservative rates reflect mature technology with limited efficiency potential

| Technology Route | BAU | Progressive | Optimistic |
|-----------------|-----|-------------|------------|
| SMR+HB (Steam Methane Reforming + Haber-Bosch) | 0.0% | 0.0% | -0.09%/year |
| Renewable synthesis (Electrolysis) | 0.0% | 0.0% | -0.09%/year |

**Scenario Interpretation**:
- **BAU & Progressive**: No efficiency improvement (mature technology, already optimized)
- **Optimistic**: Modest improvements from advanced catalyst systems and process integration

**Data Location**: 
- Config: `INDUSTRY_CONFIG.csv`, `metric_1='ammonia'`
- Projections: `industry/output_data/interim_data/ammonia_intensity_projections.csv`

---

### 3. HVC - High Value Chemicals (Chemical and Petrochemical)

**Source**: Engineering assumptions  
**Target**: Incremental improvements in cracking efficiency

| Technology Route | BAU | Progressive | Optimistic |
|-----------------|-----|-------------|------------|
| Naphtha cracking | 0.0% | -0.17%/year | -0.33%/year |
| LPG cracking | 0.0% | -0.17%/year | -0.33%/year |
| MTO (Methanol-to-Olefins) | 0.0% | -0.20%/year | -0.40%/year |

**Scenario Interpretation**:
- **BAU**: No improvement
- **Progressive**: ~5% reduction by 2050 - process heat integration
- **Optimistic**: ~10% reduction by 2050 - advanced catalysts, electrification of heat

**Data Location**: `INDUSTRY_CONFIG.csv`, `metric_1='chemical and petrochemical'`

---

### 4. Cement (Non-Metallic Minerals)

**Source**: Engineering assumptions  
**Target**: Clinker substitution, energy recovery, alternative fuels

| Technology Route | BAU | Progressive | Optimistic |
|-----------------|-----|-------------|------------|
| Cement production | 0.0% | -0.8%/year | -1.5%/year |

**Scenario Interpretation**:
- **BAU**: No improvement
- **Progressive**: ~21% reduction by 2050 - increased clinker substitution (fly ash, slag), waste heat recovery
- **Optimistic**: ~37% reduction by 2050 - advanced kiln technology, electrification, carbon capture energy integration

**Data Location**: `INDUSTRY_CONFIG.csv`, `metric_1='non-metallic minerals'`

---

### 5. Paper & Pulp (Paper, Pulp and Printing)

**Source**: Engineering assumptions  
**Target**: Mechanical improvements, heat recovery, efficient drying

| Technology Route | BAU | Progressive | Optimistic |
|-----------------|-----|-------------|------------|
| Primary pulp | 0.0% | -0.6%/year | -0.8%/year |
| Secondary pulp (recycled) | 0.0% | -0.5%/year | -0.7%/year |
| Paper production | 0.0% | -0.55%/year | -0.75%/year |

**Scenario Interpretation**:
- **BAU**: No improvement
- **Progressive**: ~16-18% reduction by 2050 - improved mechanical pulping, waste heat recovery
- **Optimistic**: ~21-23% reduction by 2050 - advanced drying technologies, process integration

**Data Location**: `INDUSTRY_CONFIG.csv`, `metric_1='paper, pulp and printing'`

---

## 🔧 SIMPLE SECTORS (9 Sectors)

These sectors lack detailed production and technology data. Efficiency improvements are applied uniformly across all fuels/technologies.

### Methodology

Since we cannot model specific technologies, we apply **aggregate efficiency rates** based on scenario narratives:

```
Energy(year) = BaseEnergy(2020) × Activity_Growth × (1 + efficiency_rate)^years × FuelShares
```

### Efficiency Rates

⚠️ **IMPORTANT**: These are **placeholder values requiring validation** against sector-specific studies (IEA Energy Efficiency Indicators, IRENA reports, etc.)

| Scenario | Efficiency Rate | Target by 2050 | Rationale |
|----------|----------------|----------------|-----------|
| **BAU** | -1.0% per year | ~26% reduction | Natural technology turnover, existing regulations |
| **Progressive** | -2.0% per year | ~45% reduction | Active efficiency policies, best-available technology adoption |
| **Optimistic** | -3.0% per year | ~60% reduction | Aggressive efficiency standards, breakthrough technologies |

**Applied uniformly to**:
1. Food and tobacco
2. Construction (Manufacturing, construction and mining)
3. Machinery
4. Mining and quarrying
5. Non-ferrous metals
6. Textile and leather
7. Transport equipment
8. Wood and wood products
9. **Other industries** (Industry n.e.s) - catch-all for unclassified industries

**Note on "Other industries"**: This UNSD catch-all category may show data discontinuities due to sector reclassifications. Some countries (e.g., Egypt) show large year-over-year variations that likely reflect reporting changes rather than real energy trends.

### Validation Needed

Each sector should have specific efficiency potential based on:
- **Current best-available technology** vs. average practice
- **Technology readiness levels** for emerging solutions
- **Sector-specific barriers**: capital costs, process constraints, heat requirements
- **Regional differences**: developing vs. developed country potential

**Suggested sources for validation**:
- IEA Energy Efficiency Indicators (by sector and country)
- UNIDO Industrial Energy Efficiency reports
- Sector-specific technology roadmaps (e.g., CEMBUREAU for cement)
- Academic literature on industrial energy efficiency potential

**Data Location**: Hardcoded in `industry/calculate_final_energy_demand.py`, lines 685-697

---

## 📁 Quick Reference Files

### CSV Extracts

1. **[intensity_cagr.csv](cagr_extracts/intensity_cagr.csv)** (780 rows)
   - All efficiency CAGR values by sector, technology, scenario, country
   - Long format for analysis

2. **[intensity_cagr_summary.csv](cagr_extracts/intensity_cagr_summary.csv)** (13 rows)
   - Summary table: one row per technology route
   - Columns: sector, technology, BAU, Progressive, Optimistic

### How to Generate

Run extraction script:
```bash
cd industry
python extract_cagr_values.py
```

---

## 🎯 Model Implementation

### Detailed Sectors

**Step 1**: Base intensities stored in `INDUSTRY_CONFIG.csv` (`metric_2='intensity_base'`)

**Step 2**: Efficiency CAGR applied to project future intensities:
```python
intensity[year] = base_intensity × (1 + cagr)^(year - 2020)
```

**Step 3**: Projected intensities saved to interim files:
- `steel_intensity_projections.csv`
- `ammonia_intensity_projections.csv`

**Step 4**: Final energy calculation:
```python
Energy = Production × Route_Share × Intensity(year) × Fuel_Share
```

### Simple Sectors

**Implementation**: Directly applied in `calculate_final_energy_demand.py`

```python
scenario_params = {
    'BAU': {'efficiency_rate': -0.010},
    'Progressive': {'efficiency_rate': -0.020},
    'Optimistic': {'efficiency_rate': -0.030}
}

efficiency_factor = (1 + efficiency_rate) ** years_elapsed
projected_energy = base_energy × activity_factor × efficiency_factor
```

---

## 📊 Summary Table: Efficiency Targets by 2050

| Sector | Technology | BAU | Progressive | Optimistic |
|--------|-----------|-----|-------------|------------|
| **Steel** | BF+BOF | 0% | -31% | -50% |
| **Steel** | DR+EAF | 0% | -37% | -56% |
| **Ammonia** | SMR+HB | 0% | 0% | -3% |
| **HVC** | Naphtha | 0% | -5% | -10% |
| **Cement** | Clinker | 0% | -21% | -37% |
| **Paper** | Primary pulp | 0% | -17% | -22% |
| **Simple Sectors** | All | -26% | -45% | -60% |

*Reductions calculated as: (1 + CAGR)^30 - 1*

---

## 🔄 Update History

| Date | Change | Author |
|------|--------|--------|
| June 2026 | Initial documentation with IQR-capped CAGR methodology | Model Team |
| TBD | Validation of simple sector rates against IEA/IRENA data | Pending |
| TBD | Country-specific efficiency potentials | Pending |

---

**Next Steps**:
1. ✅ Document volume CAGR methodology (see VOLUME_CAGR_SUMMARY.md)
2. ⚠️ Validate simple sector efficiency rates
3. 🔄 Review detailed sector rates against latest IEA/IRENA publications
4. 🔄 Consider country-specific efficiency baselines and potentials

---

**Related Documentation**:
- [VOLUME_CAGR_SUMMARY.md](VOLUME_CAGR_SUMMARY.md) - Activity/production growth rates
- [CAGR_SUMMARY.md](CAGR_SUMMARY.md) - Combined overview
- [intensity_cagr_summary.csv](cagr_extracts/intensity_cagr_summary.csv) - Quick reference table
