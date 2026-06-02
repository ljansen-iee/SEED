"""
Process emission factors from JRC-IDEES EU28 average (future best-case).

These factors are FIXED and do NOT change over time. They represent the physical/chemical
CO₂ emissions from industrial processes, separate from energy-related emissions.

Physical origins:
- Steel: Carbon reacting with iron ore in blast furnace, residual from alloys
- Cement: Calcination (CaCO₃ → CaO + CO₂)  
- HVC (High Value Chemicals): Fossil feedstock carbon
- Aluminium: Anode oxidation in Hall-Héroult electrolysis
"""

# Process emission factors (tCO₂ per tonne of material produced)
PROCESS_EMISSION_FACTORS = {
    # ============================================================================
    # STEEL AND IRON (tCO₂/t steel)
    # ============================================================================
    'iron and steel': {
        'BF+BOF': 0.22,           # Integrated steelworks (blast furnace + basic oxygen furnace)
        'DR+EAF': 0.05,           # Direct reduced iron + electric arc furnace
        'EAF': 0.05,              # Electric arc furnace (secondary steel from scrap)
        'Unspecified': 0.15,      # Weighted average for unknown route
    },
    
    # ============================================================================
    # NON-METALLIC MINERALS (tCO₂/t product)
    # ============================================================================
    'non-metallic minerals': {
        'Cement': 0.54,           # Calcination: CaCO₃ → CaO + CO₂
        'Ceramics': 0.03,         # Minor decomposition reactions
        'Glass': 0.02,            # Minor carbonate decomposition
        'Unspecified': 0.40,      # Conservative average (cement-dominant)
    },
    
    # ============================================================================
    # CHEMICAL AND PETROCHEMICAL (tCO₂/t product)
    # ============================================================================
    'chemical and petrochemical': {
        # HVC (High Value Chemicals: ethylene, propylene, BTX)
        'HVC_primary': 0.18,              # Fossil feedstock (steam cracking)
        'HVC_feedstock': 0.23,            # Petrochemical CO₂ (potentially non-fossil)
        'HVC_mechanical_recycling': 0.0,  # No process emissions
        'HVC_chemical_recycling': 0.0,    # No process emissions
        
        # Ammonia
        'ammonia_SMR': 0.0,               # Emissions on energy side (SMR hydrogen)
        'ammonia_green': 0.0,             # No process emissions (electrolysis hydrogen)
        
        'Unspecified': 0.12,              # Weighted average
    },
    
    # ============================================================================
    # NON-FERROUS METALS (tCO₂/t metal)
    # ============================================================================
    'non-ferrous metals': {
        'Aluminium_primary': 1.5,    # Hall-Héroult anode oxidation (CF₄, C₂F₆)
        'Aluminium_secondary': 0.0,  # Recycling - no process emissions
        'Copper': 0.03,              # Minor from sulfide roasting
        'Zinc': 0.03,                # Minor from oxide reduction
        'Other': 0.03,               # Minor (lead, nickel, etc.)
        'Unspecified': 0.50,         # Weighted by typical aluminium share (~30%)
    },
    
    # ============================================================================
    # PAPER AND PULP (tCO₂/t product)
    # ============================================================================
    'paper, pulp and printing': {
        'Pulp': 0.02,   # Minor emissions from pulping chemicals (Kraft process)
        'Paper': 0.01,  # Very minor (mostly energy-side from drying)
    },
    
    # ============================================================================
    # SIMPLE SECTORS - NO PROCESS EMISSIONS (TODO: Add if production data available)
    # ============================================================================
    'food and tobacco': {
        'default': 0.0,  # TODO: Add fermentation (meat, dairy) if production data available
    },
    'construction': {
        'default': 0.0,  # TODO: Minor emissions from lime/gypsum if disaggregated data available
    },
    'machinery': {'default': 0.0},
    'mining and quarrying': {
        'default': 0.0,  # TODO: Add methane from coal mining if production data available
    },
    'textile and leather': {'default': 0.0},
    'transport equipment': {'default': 0.0},
    'wood and wood products': {
        'default': 0.0,  # Biogenic carbon (neutral in most accounting frameworks)
    },
    'other industries': {
        'default': 0.0,  # Catch-all sector, emissions unknown without disaggregation
    },
}


def get_emission_factor(sector: str, route: str = None) -> float:
    """
    Get process emission factor for a sector and technology route.
    
    Args:
        sector: Industry sector name (e.g., 'iron and steel')
        route: Technology route (e.g., 'BF+BOF', 'DR+EAF'). If None, returns 'Unspecified' or 'default'
    
    Returns:
        Emission factor in tCO₂/t material
    
    Examples:
        >>> get_emission_factor('iron and steel', 'BF+BOF')
        0.22
        >>> get_emission_factor('non-metallic minerals', 'Cement')
        0.54
        >>> get_emission_factor('food and tobacco')
        0.0
    """
    if sector not in PROCESS_EMISSION_FACTORS:
        return 0.0
    
    sector_factors = PROCESS_EMISSION_FACTORS[sector]
    
    # If no route specified, try 'Unspecified' then 'default'
    if route is None:
        return sector_factors.get('Unspecified', sector_factors.get('default', 0.0))
    
    # Return specific route factor, fallback to Unspecified/default
    return sector_factors.get(route, 
                             sector_factors.get('Unspecified', 
                                              sector_factors.get('default', 0.0)))


def list_sectors_with_emissions() -> list:
    """Return list of sectors that have non-zero process emissions."""
    sectors = []
    for sector, routes in PROCESS_EMISSION_FACTORS.items():
        # Check if any route has non-zero emissions
        if any(factor > 0 for factor in routes.values()):
            sectors.append(sector)
    return sectors


if __name__ == "__main__":
    """Test emission factor retrieval."""
    print("=" * 80)
    print("PROCESS EMISSION FACTORS")
    print("=" * 80)
    
    # Test detailed sectors
    test_cases = [
        ('iron and steel', 'BF+BOF'),
        ('iron and steel', 'DR+EAF'),
        ('iron and steel', 'EAF'),
        ('non-metallic minerals', 'Cement'),
        ('non-metallic minerals', 'Glass'),
        ('chemical and petrochemical', 'HVC_primary'),
        ('chemical and petrochemical', 'ammonia_SMR'),
        ('non-ferrous metals', 'Aluminium_primary'),
        ('non-ferrous metals', 'Aluminium_secondary'),
        ('food and tobacco', None),
    ]
    
    print("\nDetailed sectors:")
    print("-" * 80)
    for sector, route in test_cases:
        factor = get_emission_factor(sector, route)
        route_str = route if route else 'default'
        print(f"{sector:30s} | {route_str:25s} | {factor:.2f} tCO₂/t")
    
    print("\n" + "=" * 80)
    print("Sectors with non-zero emissions:")
    print("=" * 80)
    for sector in list_sectors_with_emissions():
        print(f"  - {sector}")
    
    print("\n" + "=" * 80)
    print("✓ Process emission factors loaded")
    print("=" * 80)
