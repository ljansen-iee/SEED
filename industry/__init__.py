# Industry package initialization
from pathlib import Path

# Core imports
from industry.helpers import (
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
    METRIC_ORDER
)

from industry.build_CAGR import (
    load_industry_config,
    interpolate_or_extrapolate,
    get_metric_cagr_cfg_from_excel,
    get_metric_config_entry_from_excel,
    expand_with_cagr_smooth,
    generate_industry_config_csv
)

from industry.build_config_industry import (
    SCENARIOS,
    BASE_YEAR,
    TARGET_YEARS,
    INDUSTRY_CONFIG_FILE,
    BASE_DIR,
    INDUSTRY_CONFIG_PATH
)