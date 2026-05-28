"""
Fuel shares for non-ferrous metals sector.

Uses generic UNSD fuel share loader since non-ferrous metals
doesn't have sector-specific calculation logic.
"""

from industry.scripts.food_and_tobacco.build_shares_food_and_tobacco import get_unsd_fuel_shares

# Re-export generic function for non-ferrous metals
get_non_ferrous_fuel_shares = get_unsd_fuel_shares
