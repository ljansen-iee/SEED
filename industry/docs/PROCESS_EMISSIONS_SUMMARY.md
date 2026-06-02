# Process Emissions Summary (Quick Reference)

**Last Updated**: June 1, 2026  
**Status**: ✅ Steel, Cement, HVC implemented | ⚠️ Aluminium, Ceramics, Glass pending

---

## Emission Factors (Fixed, tCO₂/t material)

| Sector | Route/Technology | Factor | Physical Origin |
|--------|-----------------|--------|-----------------|
| **Steel** | BF+BOF (Blast Furnace) | 0.22 | Coke reduction of iron ore |
| | DR+EAF (Direct Reduction) | 0.05 | Residual from alloys |
| | EAF (Electric Arc) | 0.05 | Residual from alloys |
| **Cement** | All (clinker production) | 0.54 | Limestone calcination (CaCO₃→CaO+CO₂) |
| **HVC** | Primary (steam cracking) | 0.18 | Fossil feedstock carbon |
| | From feedstock | 0.23 | Petrochemical CO₂ |
| | Recycling | 0.00 | Closed-loop carbon |
| **Ammonia** | All | 0.00 | Emissions on energy side (H₂ production) |
| **Aluminium** ⚠️ | Primary (electrolysis) | 1.50 | Anode oxidation (CF₄, C₂F₆) |
| | Secondary (recycling) | 0.00 | No electrolysis |
| **Ceramics** ⚠️ | All | 0.03 | Minor decomposition |
| **Glass** ⚠️ | All | 0.02 | Minor carbonate decomposition |

⚠️ = Not yet implemented (waiting for production data)

---

## Key Assumptions

1. **Emission factors are FIXED** - do not change over time
   - Represent "future best-case" from JRC-IDEES EU28 average
   - Technology shifts (e.g., BF→EAF) reduce total emissions via route mix, not factors

2. **Process emissions ≠ Energy emissions**
   - Process: Chemical/physical reactions (unavoidable with current chemistry)
   - Energy: Combustion of fuels (can be decarbonized via fuel switching)

3. **Production-based calculation**
   ```
   MtCO₂/year = Production(Mt/year) × EmissionFactor(tCO₂/t)
   ```

---

## Example Calculations

### Egypt 2030 BAU

| Sector | Production | Factor | Process Emissions |
|--------|-----------|--------|-------------------|
| Steel (BF+BOF dominant) | ~4.1 Mt | 0.22 | ~900 MtCO₂ |
| Cement | ~6.6 Mt clinker | 0.54 | ~3,549 MtCO₂ |
| HVC | ~0.18 Mt | 0.18 | ~33 MtCO₂ |
| **Total** | | | **~4,482 MtCO₂** |

---

## Output Files

- **`process_emissions.csv`** - Detailed by route (264 records for 3 scenarios × 5 years × 4 countries)
- **`process_emissions_summary.csv`** - Aggregated by sector

**Generate**:
```bash
cd industry
python calculate_process_emissions.py
```

---

## Important Distinctions

### Why Steel Has Three Emission Factors?

Technology routes have different carbon requirements:
- **BF+BOF**: Uses coke to reduce iron ore → high CO₂ (chemistry requirement)
- **DR+EAF**: Uses hydrogen/nat gas to reduce ore → low CO₂
- **EAF**: Melts scrap steel → minimal CO₂ (only alloy additions)

### Why Ammonia Has Zero Process Emissions?

Ammonia is NH₃ (no carbon in product). CO₂ from ammonia production comes from:
- SMR pathway: Methane reforming for H₂ (energy-side emissions)
- Electrolysis pathway: Electricity for H₂ (energy-side emissions)

Process emissions are **only** CO₂ embedded in the product or reaction stoichiometry.

### Why Cement Emissions Are Fixed?

Calcination reaction is stoichiometric:
```
CaCO₃ (limestone) → CaO (lime) + CO₂
```

Only ways to reduce cement process emissions:
1. **Alternative feedstocks**: Use geopolymers, slag cement (less/no limestone)
2. **Carbon capture**: Capture CO₂ at kiln (adds to cost)
3. **Reduce clinker ratio**: More additives in final cement blend

Emission factor represents current "best available technology" (BAT).

---

## Future Enhancements

### Near-term
- ✅ Implement aluminium (when non-ferrous production data available)
- ✅ Disaggregate ceramics and glass (when NMM production split available)
- ✅ Add HVC recycling pathways (differentiate primary vs. recycled)

### Medium-term
- Carbon capture integration (reduce effective emission factors)
- Alternative feedstock scenarios (geopolymer cement, bio-HVC)
- Biogenic carbon accounting (separate fossil from biogenic CO₂)

### Long-term
- Dynamic emission factors (technology improvement over time)
- Regional calibration (country-specific vs. EU28 average)
- Uncertainty quantification (emission factor ranges)

---

## Quick Validation Checklist

When reviewing process emissions results:

1. **Steel**: Check route mix (BF+BOF should decline over time in progressive scenarios)
2. **Cement**: Total emissions ~0.5-0.6× production (clinker ratio effect)
3. **HVC**: Small contributor (~1-5% of steel emissions typically)
4. **Total magnitude**: Process emissions typically 20-40% of energy-side emissions for heavy industry

---

## References

- **Emission factors**: JRC-IDEES EU28 (https://data.jrc.ec.europa.eu/collection/id-00180)
- **Methodology**: IPCC 2006 Guidelines Volume 3 (Industrial Processes)
- **Steel roadmap**: IEA Iron and Steel Technology Roadmap
- **Cement roadmap**: IEA Cement Technology Roadmap

---

**Documentation**: See [PROCESS_EMISSIONS_GUIDE.md](PROCESS_EMISSIONS_GUIDE.md) for full details

**Code**: `industry/calculate_process_emissions.py` and `industry/core/process_emission_factors.py`
