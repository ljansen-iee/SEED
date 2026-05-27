"""
industry.core - Centralized utilities for sectoral energy demand modeling.

This package contains shared functionality used across multiple industry sectors:
- CAGR calculation from UNSD historical data
- Generic configuration row builders
- Common data transformations

Centralizing these functions ensures:
- Single source of truth for methodology
- Consistent behavior across all sectors
- Easier testing and maintenance
- Bug fixes propagate to all sectors automatically
"""

from .cagr_calculator import calculate_production_cagr_from_unsd

__all__ = [
    "calculate_production_cagr_from_unsd",
]
