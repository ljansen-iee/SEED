"""
build_aluminium_shares.py
--------------------------
Generate technology route shares for aluminium production.

Technology Routes
~~~~~~~~~~~~~~~~~
1. **Primary Aluminium** (Hall-Héroult electrolysis)
   - Electrolysis of alumina (Al₂O₃) in molten cryolite
   - Energy-intensive: ~15 MWh/t (mostly electricity)
   - Process emissions: 1.5 tCO₂/t (anode oxidation)
   - Current global share: ~64% (IAI 2020)

2. **Secondary Aluminium** (Scrap recycling)
   - Melting and refining of aluminium scrap
   - Low energy: ~0.75 MWh/t (only 5% of primary)
   - Process emissions: 0.0 tCO₂/t (no chemical reaction)
   - Current global share: ~36% (IAI 2020)

Scenario Trajectories
~~~~~~~~~~~~~~~~~~~~~
Recycling share growth driven by:
- Circular economy policies (EU, China)
- Growing scrap availability (building stock, vehicles)
- Economic incentives (energy cost savings)
- Quality improvements (alloy separation tech)

Conservative constraints:
- Scrap availability lag (aluminium lifecycle: 10-30 years)
- Quality requirements (primary needed for aerospace, automotive)
- Infrastructure investment timeline

Scenarios:
- BAU: Slow growth (36% → 42% by 2050)
  * Business-as-usual recycling trends
  * Limited policy intervention
  
- Progressive: Moderate growth (36% → 50% by 2050)
  * Circular economy action plans
  * Extended producer responsibility
  
- Optimistic: Strong growth (36% → 60% by 2050)
  * Maximum recycling push
  * Advanced sorting & processing tech
  * Carbon pricing drives primary costs up

Data Source: IAI (International Aluminium Institute)
https://international-aluminium.org/statistics/primary-production/
https://international-aluminium.org/statistics/recycling/

TODO: Validate scenarios against:
- IEA "Energy Technology Perspectives 2023"
- EU Circular Economy Action Plan targets
- Material Economics "Industrial Transformation 2050"

Author: Automated workflow
Date: June 2026
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
from industry.build_CAGR import interpolate_or_extrapolate
from industry.core.helpers import get_scenarios_from_build_config_industry

SCENARIOS = get_scenarios_from_build_config_industry()

# ---------------------------------------------------------------------------
# Technology Route Shares
# ---------------------------------------------------------------------------

def get_aluminium_route_shares(
    target_years: List[int],
    scenarios: Optional[List[str]] = None,
) -> Dict[str, Dict[int, Dict[str, float]]]:
    """
    Calculate Primary and Secondary aluminium route shares.
    
    Returns nested dictionary:
    {
        'Primary': {year: {scenario: share}},
        'Secondary': {year: {scenario: share}}
    }
    
    Args:
        target_years: Projection years (e.g., [2025, 2030, 2035, 2040, 2045, 2050])
        scenarios: Scenario names (default: from build_config_industry)
    
    Returns:
        Nested dict with route shares by year and scenario
    """
    if scenarios is None:
        scenarios = SCENARIOS
    
    # --- Primary Aluminium Share (Hall-Héroult) ---
    # Decreases over time as recycling grows
    base_primary = {
        2020: [0.64, 0.64, 0.64],  # IAI global data (64% primary in 2020)
        2030: [0.62, 0.60, 0.57],  # Slow/moderate/fast recycling growth
        2040: [0.56, 0.52, 0.48],  # Continued divergence
        2050: [0.58, 0.50, 0.40],  # BAU rebounds slightly (scrap constraints)
    }
    
    # --- Secondary Aluminium Share (Recycling) ---
    # Inverse of primary (must sum to 1.0)
    base_secondary = {
        2020: [0.36, 0.36, 0.36],  # IAI global data (36% secondary in 2020)
        2030: [0.38, 0.40, 0.43],  # Complementary to primary
        2040: [0.44, 0.48, 0.52],  # Growing scrap availability
        2050: [0.42, 0.50, 0.60],  # BAU: scrap shortage; Optimistic: max recycling
    }
    
    # --- Interpolation helper ---
    def interpolate_shares(base_data, target_years, scenarios):
        per_scenario = {}
        
        for i, sc in enumerate(scenarios):
            # Build {year: value} dict for this scenario
            sc_dict = {
                y: vals[i] if i < len(vals) else vals[-1]
                for y, vals in base_data.items()
            }
            
            # Interpolate/extrapolate to target years
            per_scenario[sc] = interpolate_or_extrapolate(sc_dict, target_years)
        
        # Restructure: {year: {scenario: value}}
        return {
            y: {sc: per_scenario[sc][y] for sc in scenarios}
            for y in target_years
        }
    
    # --- Compute both routes ---
    share_primary = interpolate_shares(base_primary, target_years, scenarios)
    share_secondary = interpolate_shares(base_secondary, target_years, scenarios)
    
    # --- Validate: ensure they sum to 1.0 ---
    for year in target_years:
        for scenario in scenarios:
            total = share_primary[year][scenario] + share_secondary[year][scenario]
            if abs(total - 1.0) > 0.01:  # Allow 1% tolerance
                # Normalize to ensure sum = 1.0
                share_primary[year][scenario] /= total
                share_secondary[year][scenario] /= total
    
    return {
        'Primary aluminium': share_primary,
        'Secondary aluminium': share_secondary,
    }


# ---------------------------------------------------------------------------
# Main Execution (for testing)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("="*80)
    print("ALUMINIUM TECHNOLOGY ROUTE SHARES")
    print("="*80)
    
    target_years = [2025, 2030, 2035, 2040, 2045, 2050]
    shares = get_aluminium_route_shares(target_years)
    
    print("\nPRIMARY ALUMINIUM (Hall-Héroult electrolysis)")
    print("-" * 80)
    print(f"{'Year':<6} {'BAU':>10} {'Progressive':>12} {'Optimistic':>12}")
    print("-" * 80)
    
    for year in target_years:
        values = shares['Primary aluminium'][year]
        print(f"{year:<6} {values['BAU']:>10.1%} {values['Progressive']:>12.1%} {values['Optimistic']:>12.1%}")
    
    print("\n\nSECONDARY ALUMINIUM (Recycling)")
    print("-" * 80)
    print(f"{'Year':<6} {'BAU':>10} {'Progressive':>12} {'Optimistic':>12}")
    print("-" * 80)
    
    for year in target_years:
        values = shares['Secondary aluminium'][year]
        print(f"{year:<6} {values['BAU']:>10.1%} {values['Progressive']:>12.1%} {values['Optimistic']:>12.1%}")
    
    print("\n✓ Aluminium route shares calculated successfully!\n")
