# Industry package initialization
from pathlib import Path

# Core imports
from industry.utils.helpers import (
    _resolve_industry_dir,
    INDUSTRY_DIR,
    get_scenarios_from_build_config_industry,
    get_scenarios_from_main_industry,
    DEFAULT_TARGET_YEARS,
    extract_capacity_shares,
    extract_all_fuels,
    _build_rate_anchors_indexed,
    _forecast_from_history_and_sparse_cagr,
    _get_value_by_index,
    _interp_at,
    get_mapped_config_name,
    poly_project,
    get_historical_sector_data,
    validate_fuel_shares,
    country_to_iso2,
    get_fuel_shares_from_unsd,
    interpolate_or_extrapolate,
    METRIC_ORDER
)

# Constants (previously from build_config_industry.py)
SCENARIOS = ["BAU", "Progressive", "Optimistic"]
BASE_YEAR = 2020
TARGET_YEARS = DEFAULT_TARGET_YEARS
INDUSTRY_CONFIG_FILE = "INDUSTRY_CONFIG.csv"
BASE_DIR = INDUSTRY_DIR
INDUSTRY_CONFIG_PATH = BASE_DIR / "output_data" / "CONFIG" / INDUSTRY_CONFIG_FILE

# Legacy imports - only used by old workflow files (build_CAGR.py, build_config_industry.py, build_final_energy_demand.py)
# These are kept for backward compatibility but should NOT be used in new code
# Legacy imports removed - old workflow files (build_CAGR.py, build_config_industry.py) have been deleted
# New workflow uses scripts/generate_industry_config.py instead