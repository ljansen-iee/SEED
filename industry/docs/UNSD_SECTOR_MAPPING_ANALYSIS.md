# UNSD Sector Mapping Analysis

## Sectors Currently Mapped

### Industry Module (13 sectors)
| UNSD Sector | Model Sector | Status |
|-------------|--------------|--------|
| Iron and steel | Steel | ✓ Detailed |
| Chemical and petrochemical | Ammonia + HVC | ✓ Detailed |
| Non-metallic minerals | Cement | ✓ Detailed |
| Paper pulp and printing | Paper & Pulp | ✓ Detailed |
| Food and tobacco | Food | ✓ Simple |
| Manufacturing const. and mining | Construction | ✓ Simple |
| Machinery | Machinery | ✓ Simple |
| Mining and quarrying | Mining | ✓ Simple |
| Non-ferrous metals | Non-ferrous | ✓ Simple |
| Textile and leather | Textile | ✓ Simple |
| Transport equipment | Transport equip | ✓ Simple |
| Wood and wood products | Wood | ✓ Simple |

### Additional Sectors Module (4 sectors)
| UNSD Sector | Model Sector | Status |
|-------------|--------------|--------|
| Agriculture forestry and fishing | Agriculture | ✓ Handled |
| Commerce and public services | Services | ✓ Handled |
| Non-energy use | Non-energy | ✓ Handled |
| Other consumption n.e.s | Other | ✓ Handled |

### Transport Module
| UNSD Sector | Model Sector | Status |
|-------------|--------------|--------|
| Road | Road transport | ✓ Handled |
| Rail | Rail transport | ✓ Handled |
| Domestic aviation | Aviation | ✓ Handled |
| Domestic navigation | Navigation | ✓ Handled |
| Pipeline transport | Pipeline | ✓ Handled |

---

## ❌ MISSING SECTOR - Currently Dropped

### **Industry n.e.s** (Industry not elsewhere specified)

**Data Example** (Algeria 2023):
- Total Energy: 42,125 TJ (11.7 TWh)
- Represents ~11% of total manufacturing energy!

**Definition**: Catch-all category for industrial activities not classified in specific sectors above. Examples:
- Small-scale manufacturing
- Handicrafts and artisanal production
- Miscellaneous industrial services
- Industries unique to specific countries
- Data reporting residuals

**Why It Matters**:
- Significant energy consumption (10-20% of industrial total in many countries)
- Currently creates energy balance discrepancy
- Should be captured for completeness

---

## 🚢 Sectors Handled Elsewhere (Not Industry)

### International Bunkers
These are **international transport fuels** (NOT domestic industrial energy):

1. **International aviation bunkers**
   - Jet fuel for international flights
   - Excluded from national energy accounting (UNFCCC rules)
   - Should be in transport module if modeling global emissions

2. **International marine bunkers**  
   - Marine fuel for international shipping
   - Excluded from national energy accounting (UNFCCC rules)
   - Should be in transport module if modeling global emissions

**Note**: Bunkers are excluded from national inventories by convention (fuel purchased in country A but consumed in international waters). Not an industry sector issue.

---

## Recommended Solution

### Add "Other Industries" Sector

**Approach**: Treat as a simple sector using UNSD-based methodology

**Implementation**:
```python
# In calculate_final_energy_demand.py, add to simple_sectors list:
simple_sectors = [
    # ... existing sectors ...
    ('Industry n.e.s', 'other industries'),  # NEW
]
```

**Parameters**:
- **Activity CAGR**: From UNSD historical data with IQR capping (same as other simple sectors)
- **Efficiency rates** (by scenario):
  - BAU: -1.0%/year
  - Progressive: -2.0%/year  
  - Optimistic: -3.0%/year
- **Fuel shares**: From UNSD latest year data

**Justification**:
1. ✅ **Comprehensive**: Captures all industrial energy, no residuals
2. ✅ **Consistent**: Uses same methodology as other simple sectors
3. ✅ **Low effort**: Requires ~5 lines of code change
4. ✅ **Data available**: UNSD provides full historical data for this sector
5. ✅ **Realistic**: Default efficiency rates appropriate for mixed small industries

---

## Data Magnitude Check

Sample data from 4 countries (2023):

| Country | Industry n.e.s (TWh) | % of Total Industry |
|---------|---------------------|---------------------|
| Algeria | 11.7 | ~11% |
| Argentina | TBD | TBD |
| Morocco | TBD | TBD |
| Egypt | TBD | TBD |

**Conclusion**: Non-trivial energy consumption that should be captured.

---

## Alternative Approaches (NOT Recommended)

### ❌ Option 1: Distribute to existing sectors
- Problem: Arbitrary allocation, no physical basis
- Problem: Distorts sector-specific trends

### ❌ Option 2: Ignore as residual
- Problem: Creates energy balance error
- Problem: Larger in developing countries (informal sector)

### ❌ Option 3: Add to "Construction" or other catch-all
- Problem: Muddles sector definitions
- Problem: Makes comparison with IEA/other studies difficult

---

## Implementation Checklist

- [ ] Add "Industry n.e.s" to CONFIG generation (fuel shares)
- [ ] Add to simple_sectors list in calculate_final_energy_demand.py
- [ ] Update wide format pivot to include "other industries" column
- [ ] Test with sample countries
- [ ] Update documentation (efficiency/volume CAGR summaries)
- [ ] Verify energy totals match UNSD base year

---

**Created**: June 1, 2026  
**Author**: Model Development Team
