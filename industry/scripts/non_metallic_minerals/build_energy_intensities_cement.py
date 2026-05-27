# scripts/non_metallic_minerals/build_energy_intensities_cement.py

from typing import Dict, List, Optional
import os
import sys
from pathlib import Path

from industry.build_CAGR import interpolate_or_extrapolate
from industry.core.helpers import _build_rate_anchors_indexed, _get_value_by_index, get_scenarios_from_build_config_industry

SCENARIOS = get_scenarios_from_build_config_industry()

def _interpolate_intensities(
    base_data: Dict[str, Dict[int, List[float]]],
    target_years: List[int],
    scenarios: List[str],
) -> Dict[str, Dict[int, Dict[str, float]]]:
    result: Dict[str, Dict[int, Dict[str, float]]] = {}
    all_years = [2020] + target_years

    for fuel, yearly in base_data.items():
        result[fuel] = {}
        for i, sc in enumerate(scenarios):
            series = {
                year: vals[i] if i < len(vals) else vals[-1]
                for year, vals in yearly.items()
            }
            series_interp = interpolate_or_extrapolate(series, all_years)
            for y, v in series_interp.items():
                result[fuel].setdefault(y, {})[sc] = v
    return result


def intensity_cement_production(
    target_years: List[int],
    scenarios: Optional[List[str]] = None,
) -> Dict[str, Dict[int, Dict[str, float]]]:
    if scenarios is None:
        scenarios = SCENARIOS

    base_data = {
        # exactly your sheet
        "diesel": {
            2020: [1.0972, 1.0972, 1.0972],
            2030: [1.0972, 1.0972, 1.0972],
            2050: [1.0972, 1.0972, 1.0972],
        },
        "natural_gas": {
            2020: [1.0972, 1.0972, 1.0972],
            2030: [1.0972, 1.0972, 1.0972],
            2050: [1.0972, 1.0972, 1.0972],
        },
        "electricity": {
            2020: [1.0972, 1.0972, 1.0972],
            2030: [1.0972, 1.0972, 1.0972],
            2050: [1.0972, 1.0972, 1.0972],
        },
        "coal": {
            2020: [1.0972, 1.0972, 1.0972],
            2030: [1.0972, 1.0972, 1.0972],
            2050: [1.0972, 1.0972, 1.0972],
        },
        "heat": {
            2020: [1.0972, 1.0972, 1.0972],
            2030: [1.0972, 1.0972, 1.0972],
            2050: [1.0972, 1.0972, 1.0972],
        },
        "biomass": {
            2020: [1.0972, 1.0972, 1.0972],
            2030: [1.0972, 1.0972, 1.0972],
            2050: [1.0972, 1.0972, 1.0972],
        },
        "hydrogen": {
            2020: [1.0972, 1.0972, 1.0972],
            2030: [1.0972, 1.0972, 1.0972],
            2050: [1.0972, 1.0972, 1.0972],
        },
    }

    return _interpolate_intensities(base_data, target_years, scenarios)




# add parent path

from industry.core.helpers import _build_rate_anchors_indexed, _forecast_from_history_and_sparse_cagr


def activity_factor_unspecified_nmm(
    base_value: float,
    base_year: int,
    target_years: List[int],
    cagr_cfg: Dict,
    scenarios: Optional[List[str]] = None,
    use_profile: bool = False,
) -> Dict[int, Dict[str, float]]:
    if scenarios is None:
        scenarios = SCENARIOS

    if use_profile:
        anchors = {
            2020: [1.00, 1.00, 1.00],
            2030: [1.20, 1.20, 1.20],
            2050: [1.78, 1.78, 1.78],
        }
        result: Dict[int, Dict[str, float]] = {}
        all_years = [base_year] + target_years
        for i, sc in enumerate(scenarios):
            series = {y: vals[i] for y, vals in anchors.items()}
            series_interp = interpolate_or_extrapolate(series, all_years)
            for y, v in series_interp.items():
                result.setdefault(y, {})[sc] = v
        return result

    # CAGR mode
    result: Dict[int, Dict[str, float]] = {}

    anchors = _build_rate_anchors_indexed(cagr_cfg, scenarios)

    grown = _forecast_from_history_and_sparse_cagr(
        last_obs_val=base_value,
        last_obs_year=base_year,
        target_years=target_years,
        sc_anchors=anchors,
        scenarios=scenarios,
    )

    for y in target_years:
        result[y] = {}
        for sc in scenarios:
            result[y][sc] = grown.get(f"{y}_{sc}")

    result[base_year] = {sc: float(base_value) for sc in scenarios}
    return result


def _parse_rate(x):
    # accepts 0.02, "2%", "0.02", 2 -> returns 0.02
    s = str(x).strip().replace("%", "")
    try:
        v = float(s)
    except Exception:
        return 0.0
    return v/100.0 if v > 1 else v

def _normalize_cagr_cfg_indexed(cagr_cfg: dict, scenarios: list) -> dict:
    
    if not isinstance(cagr_cfg, dict):
        return {}

    out = {}
    for y_str, val in cagr_cfg.items():
        try:
            y = int(y_str)
        except Exception:
            continue

        if isinstance(val, dict):
            out[y] = {sc: _parse_rate(val.get(sc, val.get("Baseline", 0.0))) for sc in scenarios}

        elif isinstance(val, (list, tuple)):
            arr = [_parse_rate(v) for v in val]
            # pad by repeating last value
            while len(arr) < len(scenarios):
                arr.append(arr[-1] if arr else 0.0)
            out[y] = {sc: arr[i] for i, sc in enumerate(scenarios)}

        else:
            r = _parse_rate(val)
            out[y] = {sc: r for sc in scenarios}

    return out


from typing import Dict, List

def build_unspecified_nmm_intensity(
    cement_base_tpy: float,
    cement_diesel_intensity: Dict[int, Dict[str, float]],
    base_year: int,
    target_years: List[int],
    scenarios: List[str],
    cagr_cfg: Dict[int, List[float]],
) -> Dict[int, Dict[str, float]]:
    """
    Build energy use of unspecified non-metallic minerals as:
        base_value = cement_base_tpy * diesel_intensity(base_year, scenario)
        value(year, scenario) = base_value * (1 + rate_year,scenario)^(year - base_year)

    - If a given year is NOT present in cagr_cfg, the rate is linearly
      interpolated/extrapolated from the available anchor years for that metric.
    - If cagr_cfg is empty, rate defaults to 0.0.
    """

    out: Dict[int, Dict[str, float]] = {}

    # ---- 1. Base-year diesel intensity per scenario ----
    base_int_map = cement_diesel_intensity.get(base_year, {})  # {scenario_name: intensity}
    out[base_year] = {
        sc: float(cement_base_tpy) * float(base_int_map.get(sc, 0.0))
        for sc in scenarios
    }

    # ---- 2. Preprocess CAGR config per scenario index ----
    # cagr_cfg: {year: [r_base, r_ambitious, r_netzero], ...}
    # Build series_by_sc[i] = {year: rate_for_that_scenario}
    series_by_sc: Dict[int, Dict[int, float]] = {i: {} for i in range(len(scenarios))}

    for y_key, vals in cagr_cfg.items():
        try:
            y = int(y_key)
        except Exception:
            continue
        for i in range(len(scenarios)):
            # use your helper; if you changed _get_value_by_index to be safe, this is robust
            r = _get_value_by_index(vals, i)
            if r is None:
                continue
            series_by_sc[i][y] = float(r)

    def _interp_rate(series: Dict[int, float], year: int) -> float:
        """
        Linear interpolation/extrapolation of CAGR over time for a single scenario.
        series: {anchor_year: rate}
        """
        if not series:
            # no info at all -> assume 0 growth
            return 0.0

        years = sorted(series.keys())

        # Exact anchor year
        if year in series:
            return series[year]

        # Below smallest anchor -> extrapolate using first segment
        if year < years[0]:
            if len(years) == 1:
                return series[years[0]]
            y0, y1 = years[0], years[1]
        # Above largest anchor -> extrapolate using last segment
        elif year > years[-1]:
            if len(years) == 1:
                return series[years[0]]
            y0, y1 = years[-2], years[-1]
        else:
            # Between anchors -> interpolate
            y0, y1 = years[0], years[-1]
            for a, b in zip(years[:-1], years[1:]):
                if a <= year <= b:
                    y0, y1 = a, b
                    break

        r0, r1 = series[y0], series[y1]
        if y1 == y0:
            return r0

        # simple linear interpolation in time
        return r0 + (r1 - r0) * (year - y0) / (y1 - y0)

    # ---- 3. Grow from base_year to each target_year per scenario ----
    for i, sc in enumerate(scenarios):
        base_val_sc = out[base_year][sc]
        sc_series = series_by_sc.get(i, {})

        for y in target_years:
            years = max(0, int(y) - int(base_year))
            rate = _interp_rate(sc_series, int(y))  # interpolated/extrapolated CAGR
            out.setdefault(y, {})
            out[y][sc] = base_val_sc * ((1.0 + float(rate)) ** years)

    return out
