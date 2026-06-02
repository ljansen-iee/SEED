# CAGR Values Summary - Industry Sector Model
**Generated: June 2026**  
**Model Version: 1.0 (First Iteration)**

This document summarizes the Compound Annual Growth Rates (CAGR) used for both **activity/volume growth** and **efficiency improvements** across all industry sectors.

---

## 📊 Overview: Two Types of CAGR

### 1. **Activity/Volume CAGR** (Production Growth)
- **Purpose**: Models growth in physical production (tonnes steel, tonnes cement, etc.)
- **Source**: Historical trends, scenario assumptions
- **Direction**: Typically positive (growth)

### 2. **Efficiency/Intensity CAGR** (Energy Efficiency)
- **Purpose**: Models improvements in energy per unit of production (MWh/tonne)
- **Source**: Engineering studies, IEA Technology Roadmaps
- **Direction**: Typically negative (improvement = less energy per unit)

---

## 🏭 DETAILED SECTORS (5 sectors)

These sectors have explicit production data and technology-specific intensities.

### Steel (iron and steel)

**Location**: `INDUSTRY_CONFIG.csv`, rows with `metric_2='cagr'`

| Metric Type | Technology Route | BAU | Progressive | Optimistic | Source |
|------------|-----------------|-----|-------------|-----------|--------|
| **Production CAGR** | Steel production per year | See CONFIG | See CONFIG | See CONFIG | Country-specific from SSP scenarios |
| **Intensity CAGR** | Energy intensity of BF+BOF | 0.0% | -1.2% | -2.2% | IEA Technology Roadmap |
| **Intensity CAGR** | Energy intensity of DR+EAF | 0.0% | -1.5% | -2.5% | IEA Technology Roadmap |
| **Intensity CAGR** | Energy intensity of Scrap EAF | 0.0% | -1.5% | -2.2% | IEA Technology Roadmap |
| **Intensity CAGR** | Energy intensity of Casting, rolling & finishing | 0.0% | -1.5% | -2.2% | IEA Technology Roadmap |

**Target**: Optimistic scenario achieves ~48-53% energy intensity reduction by 2050 (matching IEA "energy efficiency slim process" target)

---

### Ammonia (chemical and petrochemical - ammonia subsector)

**Location**: `INDUSTRY_CONFIG.csv`, rows with `metric_1='ammonia'`

| Metric Type | Technology Route | BAU | Progressive | Optimistic | Source |
|------------|-----------------|-----|-------------|-----------|--------|
| **Production CAGR** | ammonia production | See CONFIG | See CONFIG | See CONFIG | Country-specific from demand projections |
| **Intensity CAGR** | Energy intensity of SMR+HB | 0.0% | -0.5% | -1.0% | Engineering assumptions |
| **Intensity CAGR** | Energy intensity of Renewable synthesis | 0.0% | -0.5% | -1.0% | Engineering assumptions |

---

### HVC - High Value Chemicals (chemical and petrochemical - HVC subsector)

**Location**: `INDUSTRY_CONFIG.csv`, rows with `metric_1='chemical and petrochemical'`

| Metric Type | Technology Route | BAU | Progressive | Optimistic | Source |
|------------|-----------------|-----|-------------|-----------|--------|
| **Production CAGR** | HVC production per year | See CONFIG | See CONFIG | See CONFIG | Country-specific from demand projections |
| **Intensity CAGR** | Energy intensity of Naphtha cracking | 0.0% | -0.5% | -1.0% | Engineering assumptions |
| **Intensity CAGR** | Energy intensity of LPG cracking | 0.0% | -0.5% | -1.0% | Engineering assumptions |
| **Intensity CAGR** | Energy intensity of MTO | 0.0% | -0.5% | -1.0% | Engineering assumptions |

---

### Cement (non-metallic minerals)

**Location**: `INDUSTRY_CONFIG.csv`, rows with `metric_1='non-metallic minerals'`

| Metric Type | Technology Route | BAU | Progressive | Optimistic | Source |
|------------|-----------------|-----|-------------|-----------|--------|
| **Production CAGR** | Cement production per year | See CONFIG | See CONFIG | See CONFIG | Country-specific from infrastructure projections |
| **Intensity CAGR** | Energy intensity of Cement production | 0.0% | -0.8% | -1.5% | Engineering assumptions |
| **Intensity CAGR** | Unspecified NMM activity factor | 0.0% | 0.0% | 0.0% | Other minerals (limestone, gypsum, etc.) |

---

### Paper & Pulp (paper, pulp and printing)

**Location**: `INDUSTRY_CONFIG.csv`, rows with `metric_1='paper, pulp and printing'`

| Metric Type | Technology Route | BAU | Progressive | Optimistic | Source |
|------------|-----------------|-----|-------------|-----------|--------|
| **Production CAGR** | Pulp production per year | See CONFIG | See CONFIG | See CONFIG | Country-specific from demand projections |
| **Production CAGR** | Paper production per year | See CONFIG | See CONFIG | See CONFIG | Country-specific from demand projections |
| **Intensity CAGR** | Energy intensity of Primary pulp | 0.0% | -0.5% | -1.0% | Engineering assumptions |
| **Intensity CAGR** | Energy intensity of Secondary pulp | 0.0% | -0.5% | -1.0% | Engineering assumptions |
| **Intensity CAGR** | Energy intensity of Paper production | 0.0% | -0.5% | -1.0% | Engineering assumptions |

---

## 🔧 SIMPLE SECTORS (8 sectors)

These sectors lack detailed production data. Growth is modeled using total energy projections with separated activity and efficiency components.

**Location**: Computed dynamically in `calculate_final_energy_demand.py` (lines 637-760)

### Methodology

```
Energy(year) = BaseEnergy(2020) × ActivityGrowth × EfficiencyGrowth × FuelShares

Where:
- ActivityGrowth = (1 + UNSD_CAGR × activity_multiplier)^years
- EfficiencyGrowth = (1 + efficiency_rate)^years
```

### Activity CAGR (Volume Growth)

**Source**: UNSD historical energy data (2011-2023) with IQR outlier capping

| Scenario | Activity Multiplier | Interpretation |
|----------|---------------------|----------------|
| **BAU** | 1.0× | Historical trend continues |
| **Progressive** | 1.2× | 20% faster activity growth from policy/development |
| **Optimistic** | 1.5× | 50% faster activity growth from aggressive development |

**Country-specific CAGR values**: Calculated dynamically from `industry/input_data/unsdata_historical/` files using IQR-capped rolling 5-year windows.

### Efficiency Rates (Energy Intensity Improvement)

⚠️ **TODO**: These values are **placeholder assumptions** requiring validation against IEA/IRENA sector-specific technology roadmaps.

| Scenario | Efficiency Rate | Target by 2050 | Rationale |
|----------|----------------|----------------|-----------|
| **BAU** | -1.0% per year | ~26% reduction | Business-as-usual efficiency gains |
| **Progressive** | -2.0% per year | ~45% reduction | Moderate technology adoption |
| **Optimistic** | -3.0% per year | ~60% reduction | Aggressive efficiency improvements |

**Applied to all 8 simple sectors**:
1. Food and tobacco
2. Construction (Manufacturing, construction and mining)
3. Machinery
4. Mining and quarrying
5. Non-ferrous metals
6. Textile and leather
7. Transport equipment
8. Wood and wood products

---

## 📁 Data Locations

### Where to Find CAGR Values:

1. **Detailed Sectors - Production & Intensity CAGR**:
   - File: `industry/output_data/CONFIG/INDUSTRY_CONFIG.csv`
   - Filter: `metric_2 == 'cagr'`
   - Contains 315 rows with country-specific values

2. **Detailed Sectors - Intensity Projections** (computed from CAGR):
   - File: `industry/output_data/interim_data/steel_intensity_projections.csv` (72 rows)
   - File: `industry/output_data/interim_data/ammonia_intensity_projections.csv` (36 rows)
   - Shows projected intensities for all years (2020-2050)

3. **Simple Sectors - Activity CAGR**:
   - Computed dynamically from UNSD data
   - Function: `industry/core/cagr_calculator.py::get_final_energy_cagr_from_unsd()`
   - Not stored in config (calculated per country/sector on demand)

4. **Simple Sectors - Efficiency Rates**:
   - Hardcoded: `industry/calculate_final_energy_demand.py`, lines 685-697
   - Scenario parameters dictionary

### IQR Outlier Capping Method

For simple sectors, activity CAGR is calculated with statistical robustness:

1. **Rolling windows**: 5-year CAGR windows from historical data (2011-2023)
2. **IQR capping**: Remove outliers using Q1-1.5×IQR to Q3+1.5×IQR bounds
3. **Hard limits**: ±30% per year (physically realistic bounds)
4. **Mean**: Average of capped values

This method filters out anomalies like:
- COVID-19 pandemic effects (2020-2021)
- Data transcription errors
- Exceptional policy-driven changes

---

## 🎯 Model Philosophy

### Detailed Sectors
**Energy = Production × Technology_Routes × Intensities × Fuel_Shares**
- Production and Intensity growth are **explicitly separated**
- Technology shifts (BF+BOF → DRI+EAF) are **modeled explicitly**
- Efficiency improvements come from **engineering-based intensity projections**

### Simple Sectors
**Energy = BaseEnergy × Activity_Growth × Efficiency_Improvement × Fuel_Shares**
- Production data unavailable, so use **total energy approach**
- Activity and Efficiency are **mathematically separated** but both derived from aggregate trends
- Efficiency improvements come from **scenario storytelling assumptions**

---

## 📝 Next Steps for Model Refinement

1. **Validate simple sector efficiency rates** against:
   - IEA Energy Efficiency indicators by sector
   - IRENA technology roadmaps
   - World Bank sectoral studies

2. **Add country-specific efficiency variations**:
   - Developing countries may have different efficiency potentials
   - Consider technological capacity and policy environment

3. **Review production CAGR** for detailed sectors:
   - Compare with SSP scenarios
   - Validate against national development plans

4. **Document data sources** for all parameters:
   - Track provenance of each CAGR value
   - Version control for input data

---

**Last Updated**: June 1, 2026  
**Contact**: Model development team  
**Related Files**: `METHODOLOGY.md`, `DATA_SOURCES.md`
