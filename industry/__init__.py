# Industry package initialization
# Core imports
from industry.utils.helpers import (
    _resolve_industry_dir,
    INDUSTRY_DIR,
    get_scenarios,
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
from industry.utils.helpers import (
    SCENARIOS, DEFAULT_COUNTRIES, INDUSTRY_CONFIG_FILE, INDUSTRY_CONFIG_PATH,
    validate_industry_config,
)

# Constants (previously from build_config_industry.py)
BASE_YEAR = 2020
TARGET_YEARS = DEFAULT_TARGET_YEARS
BASE_DIR = INDUSTRY_DIR
