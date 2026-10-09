"""Retained, PROVISIONAL process factors; attribution is not verified.

Numeric values are preserved for reproducible hand checks, not validated export.
The legacy JRC-IDEES/EU28/best-case attribution has no traceable dataset version
or table/cell reference here. See PROCESS_EMISSION_METADATA for acceptance blockers.
"""

import math
import re
from copy import deepcopy

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
        'ammonia_SMR': 0.0,               # Retained placeholder, NOT a verified SMR+HB factor
        'ammonia_green': 0.0,             # Provisional E+HB value; source/boundary unverified
        
        'Unspecified': 0.12,              # Weighted average
    },
    
    # ============================================================================
    # NON-FERROUS METALS (tCO₂/t metal)
    # ============================================================================
    'non-ferrous metals': {
        'Aluminium_primary': 1.5,    # Retained; legacy CF4/C2F6 comment leaves gas basis unresolved
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
    # SIMPLE SECTORS - RETAINED ZERO DEFAULTS, NOT VERIFIED INVENTORY COMPLETENESS
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


def normalize_route_name(route: str) -> str:
    """Case/whitespace/punctuation normalization, never a fuzzy factor fallback."""
    return re.sub(r"[\s_\-]+", "", str(route).strip().casefold())


ROUTE_ALIASES = {
    'iron and steel': {
        'scrap eaf': 'EAF', 'secondary steel': 'EAF',
        'dr+eaf+h2': 'DR+EAF', 'dr+eaf+ng': 'DR+EAF',
        'dr+eaf (h2)': 'DR+EAF', 'dr+eaf (ng)': 'DR+EAF',
        'dr+eaf hydrogen': 'DR+EAF', 'dr+eaf natural gas': 'DR+EAF',
    },
    'non-metallic minerals': {'clinker': 'Cement'},
    'chemical and petrochemical': {
        'naphtha cracking': 'HVC_primary', 'lpg cracking': 'HVC_primary',
        'mto': 'HVC_feedstock', 'methanol to olefins': 'HVC_feedstock',
        'smr+hb': 'ammonia_SMR', 'e+hb': 'ammonia_green',
        'renewable synthesis': 'ammonia_green',
    },
    'non-ferrous metals': {
        'primary aluminium': 'Aluminium_primary',
        'secondary aluminium': 'Aluminium_secondary',
    },
}


def resolve_factor_key(sector: str, route: str = None) -> tuple:
    """Return canonical (sector, route); unknown inputs raise, even for zero shares.

    ``None`` is allowed only for sectors with an explicit ``default`` factor.
    ``Unspecified`` must be requested explicitly, not substituted for a typo.
    HVC production-route aliases are provisional mappings, not source verification.
    """
    sector = str(sector).strip().casefold()
    if sector not in PROCESS_EMISSION_FACTORS:
        raise ValueError(f"Unknown process-emission sector: {sector!r}")
    factors = PROCESS_EMISSION_FACTORS[sector]
    if route is None:
        if 'default' not in factors:
            raise ValueError(f"An explicit factor route is required for {sector!r}")
        return sector, 'default'
    keys = {normalize_route_name(key): key for key in factors}
    keys.update({normalize_route_name(alias): key
                 for alias, key in ROUTE_ALIASES.get(sector, {}).items()})
    canonical = keys.get(normalize_route_name(route))
    if canonical is None:
        raise ValueError(f"Unknown process-emission route {route!r} in {sector!r}")
    return sector, canonical


def get_emission_factor(sector: str, route: str = None) -> float:
    """Return the retained provisional value; reject missing/bad/unknown factors."""
    sector, route = resolve_factor_key(sector, route)
    try:
        value = float(PROCESS_EMISSION_FACTORS[sector][route])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid process factor for {sector}/{route}") from exc
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"Invalid process factor for {sector}/{route}: {value!r}")
    return value


def _material_basis(sector: str, route: str) -> str:
    if sector == 'iron and steel':
        return 'steel'
    if sector == 'non-metallic minerals' and route == 'Cement':
        return 'clinker'
    if route.startswith('HVC_'):
        return 'HVC'
    if route.startswith('ammonia_'):
        return 'ammonia'
    if route.startswith('Aluminium_'):
        return 'aluminium'
    return route.casefold() if route not in {'default', 'Unspecified'} else 'unspecified product'


PROCESS_EMISSION_METADATA = {}
for _sector, _routes in PROCESS_EMISSION_FACTORS.items():
    PROCESS_EMISSION_METADATA[_sector] = {}
    for _route in _routes:
        _blockers = ['factor_provenance_missing', 'factor_version_missing',
                     'factor_gas_basis_unverified', 'factor_boundary_unverified']
        _usable = True
        if _route.startswith('HVC_'):
            _blockers.append('hvc_route_mapping_unverified')
        if _route.startswith('ammonia_'):
            _blockers.append('ammonia_source_missing')
        if _route == 'ammonia_SMR':
            _blockers.append('ammonia_smr_factor_is_unverified_zero_placeholder')
            _usable = False
        if _route == 'Aluminium_primary':
            _blockers.append('aluminium_co2_only_factor_unverified_legacy_pfc_annotation')
            _usable = False
        PROCESS_EMISSION_METADATA[_sector][_route] = {
            'factor_provenance': None,
            'factor_version': None,
            'factor_gas_basis': 'unverified',
            'requested_gas_basis': 'CO2',
            'factor_units': 'tCO2/t material (intended, unverified)',
            'factor_material_basis': _material_basis(_sector, _route),
            'factor_boundary': 'process only; excludes combustion (intended, unverified)',
            'factor_status': 'provisional',
            'factor_blockers': _blockers,
            'usable_for_provisional_co2': _usable,
        }


def get_emission_factor_metadata(sector: str, route: str = None) -> dict:
    """Return independent machine-readable metadata for the canonical factor."""
    sector, route = resolve_factor_key(sector, route)
    metadata = deepcopy(PROCESS_EMISSION_METADATA[sector][route])
    metadata.update(sector=sector, factor_key=route,
                    retained_factor=get_emission_factor(sector, route))
    return metadata


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
    print("PROVISIONAL PROCESS EMISSION FACTORS - NOT ACCEPTED FOR FINAL EXPORT")
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
    print("Retained factors loaded; provenance/version/gas/boundary review is blocked")
    print("=" * 80)
