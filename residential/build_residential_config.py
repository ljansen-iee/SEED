import os
import argparse
import numpy as np
import pandas as pd
from pathlib import Path

# === Imports from project libraries ===
import build_macro_indicators as build_mac
import build_saturation_rates as build_sat
import build_technology_shares as build_tec_share
import build_energy_intensities as build_en_int
import build_CAGR as build_cagr
import helpers
from helpers import load_residential_config


# === SCENARIOS PARAMETRIZATION === 

# === basics ===
base_year = 2020  # select starting year between 2019 and 2023.
growth_pathway = ["SSP3", "SSP2", "SSP1"] # this is the order of growth path for the three scenarios
scenario_name = ["BAU", "Progressive", "Optimistic"] 

target_years = helpers.DEFAULT_TARGET_YEARS  # select projected years


# Country options
selected_countries = [
    # "Algeria",
    # "Argentina",
    # "Brazil",
    # "Chile",
    # "Colombia",
    "Egypt",
    # "Libya",
    # "Mexico",
    "Namibia",
    # "Peru",
    # "Tunisia",
    # "Uruguay",
    "Morocco",
    "South Africa" 
]

# "Republic of the Congo", "Egypt", "Ethiopia", "Ghana","Kenya","Namibia","Niger",
# "Algeria","Argentina","Brazil","Chile","Colombia","Mexico","Peru","Venezuela",
# "Morocco","Tunisia","Tanzania","Libya",

countries_to_load = selected_countries + ["default"] 

SH_METRICS = helpers.SH_METRICS
COOKING_METRICS = helpers.COOKING_METRICS
CAGR_SCENARIO_MAP = helpers.CAGR_SCENARIO_MAP
CAGR_UNITS_MAP = helpers.CAGR_UNITS_MAP
INTENSITY_METRICS_MAP = helpers.INTENSITY_METRICS_MAP


def build_metric_df(metric_name, unit_key, data_df, target_years, scenario_name, growth_pathway, selected_countries, units_dict):
    """Build a long-format DataFrame for a single macro-indicator metric.

    Creates one row per (year, scenario) combination and one column per
    country, extracting values from *data_df* which is indexed by
    ``(country, SSP)``.

    Args:
        metric_name: Human-readable metric label.
        unit_key: Key into *units_dict* for the unit string.
        data_df: Source DataFrame indexed by ``(country, SSP)`` with
            year columns.
        target_years: List of projection years.
        scenario_name: Ordered list of scenario names.
        growth_pathway: Matching list of SSP identifiers.
        selected_countries: Countries to include.
        units_dict: Mapping of metric keys → unit strings.

    Returns:
        pd.DataFrame: Long-format parameter table.
    """
    unit = units_dict.get(unit_key)
    macro_rows = []
    for year in target_years:
        for scenario, ssp in zip(scenario_name, growth_pathway):
            macro_rows.append(
                {
                    "type": "macro_ind",
                    "metric name": metric_name,
                    "year": year,
                    "scenario": scenario,
                    "units": unit,
                }
            )

    df_macro = pd.DataFrame(macro_rows)
    for country in selected_countries:
        values = []
        for year in target_years:
            for scenario, ssp in zip(scenario_name, growth_pathway):
                values.append(data_df.loc[(country, ssp), year])
        df_macro[country] = values
    return df_macro


def build_constant_metric_df(metric_name, unit_key, country_series, target_years, scenario_name, selected_countries, units_dict, type_label="technology share"):
    """Build a parameter DataFrame for a metric that is constant over time.

    The same base-year value is repeated across all years and scenarios.

    Args:
        metric_name: Human-readable metric label.
        unit_key: Key into *units_dict*.
        country_series: ``pd.Series`` indexed by country.
        target_years: Projection years.
        scenario_name: Scenario names.
        selected_countries: Countries to include.
        units_dict: Metric → unit mapping.
        type_label: Row type label (default ``"technology share"``).

    Returns:
        pd.DataFrame: Long-format parameter table.
    """
    unit = units_dict.get(unit_key)
    country_values = country_series.reindex(selected_countries)
    if country_values.isna().any():
        missing = country_values[country_values.isna()].index.tolist()
        print(f"WARNING: Missing values for {metric_name} in {missing}.")
    macro_rows = []
    for year in target_years:
        for scenario in scenario_name:
            macro_rows.append(
                {
                    "type": type_label,
                    "metric name": metric_name,
                    "year": year,
                    "scenario": scenario,
                    "units": unit,
                }
            )

    df_macro = pd.DataFrame(macro_rows)
    for country in selected_countries:
        value = country_values.loc[country]
        df_macro[country] = [value] * len(macro_rows)
    return df_macro


def build_cooking_shares(metric_col, selected_countries, df_cooking_shares_africa, df_cooking_shares_default, default_value=0.0):
    values = {}
    for country in selected_countries:
        if country in df_cooking_shares_africa.index.get_level_values("country"):
            country_row = df_cooking_shares_africa.xs(country, level="country")
            value = float(country_row[metric_col].iloc[0])
        else:
            if metric_col in df_cooking_shares_default.columns:
                value = float(df_cooking_shares_default[metric_col].iloc[0])
            else:
                value = default_value
        values[country] = value
    return pd.Series(values)


def build_sh_saturation(df_sh_saturation, target_years, scenario_name, selected_countries, units_dict):
    df = df_sh_saturation.reset_index().copy()
    df["Year"] = df["Year"].astype(int)

    saturation_rows = []
    for scenario in scenario_name:
        series = df[df["Scenario"] == scenario].set_index("Year")["Value in %"]
        series = series.reindex(target_years).astype(float)
        for year in target_years:
            saturation_rows.append(
                {
                    "type": "saturation rate",
                    "metric name": "Saturation of Space Heating",
                    "year": year,
                    "scenario": scenario,
                    "units": units_dict.get("Saturation of Space Heating"),
                }
            )

    df_macro = pd.DataFrame(saturation_rows)
    for country in selected_countries:
        values = []
        for scenario in scenario_name:
            series = df[df["Scenario"] == scenario].set_index("Year")["Value in %"]
            series = series.reindex(target_years).astype(float).interpolate().ffill().bfill()
            for year in target_years:
                values.append(series.loc[year])
        df_macro[country] = values
    return df_macro


def build_sc_saturation(df_sc_saturation, target_years, scenario_name, selected_countries, units_dict):
    saturation_rows = []
    for scenario in scenario_name:
        for year in target_years:
            saturation_rows.append(
                {
                    "type": "saturation rate",
                    "metric name": "Saturation of Space Cooling",
                    "year": year,
                    "scenario": scenario,
                    "units": units_dict.get("Saturation of Space Cooling"),
                }
            )

    df_macro = pd.DataFrame(saturation_rows)
    if isinstance(df_sc_saturation.columns, pd.MultiIndex):
        df_sc = df_sc_saturation
    else:
        df_sc = df_sc_saturation.reindex(columns=target_years)

    for country in selected_countries:
        values = []
        for scenario in scenario_name:
            if isinstance(df_sc.columns, pd.MultiIndex):
                if country in df_sc.index and scenario in df_sc.columns.get_level_values(0):
                    country_series = df_sc.loc[country].xs(scenario, level=0)
                else:
                    country_series = pd.Series({year: np.nan for year in target_years})
            else:
                if country in df_sc.index:
                    country_series = df_sc.loc[country]
                else:
                    country_series = pd.Series({year: np.nan for year in target_years})
            for year in target_years:
                values.append(country_series.get(year))
        df_macro[country] = values
    return df_macro


def build_appliances_saturation(df_appliances_saturation, target_years, scenario_name, selected_countries, units_dict):
    saturation_rows = []
    for scenario in scenario_name:
        for year in target_years:
            saturation_rows.append(
                {
                    "type": "saturation rate",
                    "metric name": "Saturation of Appliances",
                    "year": year,
                    "scenario": scenario,
                    "units": units_dict.get("Saturation of Appliances"),
                }
            )

    df_macro = pd.DataFrame(saturation_rows)
    df_app = df_appliances_saturation.reindex(columns=target_years)

    for country in selected_countries:
        if country in df_app.index:
            country_series = df_app.loc[country]
        else:
            country_series = pd.Series({year: np.nan for year in target_years})
        values = []
        for scenario in scenario_name:
            for year in target_years:
                values.append(country_series.get(year))
        df_macro[country] = values
    return df_macro


def build_cooking_saturation(df_cooking_saturation, target_years, scenario_name, selected_countries, units_dict):
    saturation_rows = []
    for scenario in scenario_name:
        for year in target_years:
            saturation_rows.append(
                {
                    "type": "saturation rate",
                    "metric name": "Saturation of Cooking",
                    "year": year,
                    "scenario": scenario,
                    "units": units_dict.get("Saturation of Cooking"),
                }
            )

    df_macro = pd.DataFrame(saturation_rows)
    df_cook = df_cooking_saturation.reindex(columns=target_years)

    for country in selected_countries:
        if country in df_cook.index:
            country_series = df_cook.loc[country]
        else:
            country_series = pd.Series({year: np.nan for year in target_years})
        values = []
        for scenario in scenario_name:
            for year in target_years:
                values.append(country_series.get(year))
        df_macro[country] = values
    return df_macro


def build_saturation_water_heating_macro(df_cooking_saturation, target_years, scenario_name, selected_countries, units_dict):
    saturation_rows = []
    for scenario in scenario_name:
        for year in target_years:
            saturation_rows.append(
                {
                    "type": "saturation rate",
                    "metric name": "Saturation of Water Heating",
                    "year": year,
                    "scenario": scenario,
                    "units": units_dict.get("Saturation of Water Heating"),
                }
            )

    df_macro = pd.DataFrame(saturation_rows)
    df_cook = df_cooking_saturation.reindex(columns=target_years)

    for country in selected_countries:
        if country in df_cook.index:
            country_series = df_cook.loc[country]
        else:
            country_series = pd.Series({year: np.nan for year in target_years})
        values = []
        for scenario in scenario_name:
            for year in target_years:
                values.append(country_series.get(year))
        df_macro[country] = values
    return df_macro


def build_cagr_blocks(
    selected_countries,
    target_years,
    base_year,
    units_dict,
    intensity_sh,
    intensity_wh,
    intensity_sc,
    intensity_cooking,
    intensity_appliances,
    space_heating_intensity_map,
    space_cooling_intensity_map,
    cooking_intensity_map,
    water_heating_intensity_map,
):
    """Build CAGR and projected energy-intensity DataFrames.

    Retrieves region-specific CAGR values via
    :func:`build_CAGR.build_country_cagr`, then applies compound growth
    to base-year intensities for every end-use and technology.

    Args:
        selected_countries: Country names to process.
        target_years: Projection years.
        base_year: Reference year.
        units_dict: Metric → unit mapping.
        intensity_sh: Base space-heating intensity (kWh/m²).
        intensity_wh: Base water-heating intensity (kWh/dw).
        intensity_sc: Base space-cooling intensity (kWh/m²).
        intensity_cooking: Base cooking intensity (kWh/dw).
        intensity_appliances: Base appliances intensity (kWh/dw).
        space_heating_intensity_map: Technology → intensity overrides.
        space_cooling_intensity_map: Technology → intensity overrides.
        cooking_intensity_map: Technology → intensity overrides.
        water_heating_intensity_map: Technology → intensity overrides.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]: ``(df_cagr_macro,
        df_cagr_intensity_macro)`` — the raw CAGR rates and the
        resulting projected intensity values.
    """
    df_cagr_country_raw = build_cagr.build_country_cagr(
        selected_countries,
        target_years=target_years,
    )
    df_cagr_country = df_cagr_country_raw.copy()
    df_cagr_country.columns = pd.MultiIndex.from_tuples(
        [(CAGR_SCENARIO_MAP.get(scenario, scenario), year) for scenario, year in df_cagr_country.columns],
        names=df_cagr_country.columns.names,
    )

    base_intensity_map = {
        "Final Energy Intensity of Space Heating": intensity_sh,
        "Final Energy Intensity of Space Cooling": intensity_sc,
        "Final Energy Intensity of Water Heating": intensity_wh,
        "Final Energy Intensity of Cooking": intensity_cooking,
        "Final Energy Intensity of Electrical Appliances": intensity_appliances,
    }

    cagr_years = list(dict.fromkeys([base_year] + target_years))
    cagr_rows = []
    row_keys = []
    energy_intensity_list = (
        df_cagr_country.index.get_level_values("energy_intensity").unique().tolist()
    )
    for energy_intensity in energy_intensity_list:
        for year in cagr_years:
            for scenario_dst in CAGR_SCENARIO_MAP.values():
                cagr_rows.append(
                    {
                        "type": "CAGR",
                        "metric name": energy_intensity,
                        "year": year,
                        "scenario": scenario_dst,
                        "units": CAGR_UNITS_MAP.get(energy_intensity, units_dict.get(energy_intensity)),
                    }
                )
                row_keys.append((energy_intensity, year, scenario_dst))

    df_cagr_macro = pd.DataFrame(cagr_rows)
    for country in selected_countries:
        values = []
        for energy_intensity, year, scenario_dst in row_keys:
            try:
                if year == base_year:
                    values.append(0)
                else:
                    cagr_rate = df_cagr_country.loc[(country, energy_intensity), (scenario_dst, year)]
                    values.append(cagr_rate)
            except KeyError:
                values.append(np.nan)
        df_cagr_macro[country] = values

    intensity_rows = []
    expanded_row_keys = []
    for energy_intensity, year, scenario_dst in row_keys:
        for metric_name in INTENSITY_METRICS_MAP.get(energy_intensity, []):
            intensity_rows.append(
                {
                    "type": "energy intensity",
                    "metric name": metric_name,
                    "year": year,
                    "scenario": scenario_dst,
                    "units": units_dict.get(metric_name),
                }
            )
            expanded_row_keys.append((energy_intensity, metric_name, year, scenario_dst))

    df_cagr_intensity_macro = pd.DataFrame(intensity_rows)
    for country in selected_countries:
        values = []
        for energy_intensity, metric_name, year, scenario_dst in expanded_row_keys:
            if energy_intensity == "Final Energy Intensity of Space Heating":
                base_intensity = space_heating_intensity_map.get(metric_name, intensity_sh)
            elif energy_intensity == "Final Energy Intensity of Space Cooling":
                base_intensity = space_cooling_intensity_map.get(metric_name, intensity_sc)
            elif energy_intensity == "Final Energy Intensity of Cooking":
                base_intensity = cooking_intensity_map.get(metric_name, intensity_cooking)
            elif energy_intensity == "Final Energy Intensity of Water Heating":
                base_intensity = water_heating_intensity_map.get(metric_name, intensity_wh)
            else:
                base_intensity = base_intensity_map.get(energy_intensity)
            if base_intensity is None:
                values.append(np.nan)
                continue
            try:
                if year == base_year:
                    values.append(base_intensity)
                else:
                    cagr_rate = df_cagr_country.loc[(country, energy_intensity), (scenario_dst, year)]
                    values.append(base_intensity * (1 + cagr_rate / 100) ** 5)
            except KeyError:
                values.append(np.nan)
        df_cagr_intensity_macro[country] = values

    return df_cagr_macro, df_cagr_intensity_macro

# === create configuration parameters ===

def create_csv_all(input_dir=None, output_dir=None, countries=None, years=None, shares_csv_path=None):
    """Generate configuration with explicit source and output isolation."""
    countries = selected_countries if countries is None else list(dict.fromkeys(countries))
    years = target_years if years is None else sorted(set(years))
    if not countries or not years or set(years) - set(helpers.DEFAULT_TARGET_YEARS):
        raise ValueError("Select countries and standard residential years (2020, 2030, 2035, 2040, 2045, 2050)")
    input_dir = Path(input_dir) if input_dir is not None else Path(__file__).resolve().parent / "input_data"
    helpers.validate_residential_sources(input_dir, countries)
    with helpers.residential_source_paths(input_dir, shares_csv_path):
        return _create_csv_all(countries, years, output_dir)


def _create_csv_all(selected_countries, target_years, output_dir):
    """Run the full residential parameter pipeline and export results.

    Orchestrates all build steps:

    1. Macro indicators (population, floor area, persons/dwelling).
    2. Technology shares (space heating, cooking, water heating).
    3. Saturation rates (heating, cooling, appliances, cooking).
    4. CAGR-based energy-intensity projections.

    Concatenates all parameter DataFrames and writes
    ``output_data/parameters_all_countries.csv``.
    """
    # STEP 1 GENERATE MACRO INDICATORS
    macro_indicators = build_mac.create_macro_indicators_all()
    df_population, df_gdp_ssp, df_m2_p_all, df_person_dw, df_economics = macro_indicators

    if isinstance(df_person_dw.index, pd.MultiIndex) and "Region" in df_person_dw.index.names:
        df_person_dw = df_person_dw.reset_index(level="Region", drop=True)

    # STEP 2 GENERATE TECHNOLOGY SHARES
    technology_shares = build_tec_share.create_technology_shares_all()
    df_sh_shares, df_cooking_shares_africa, df_cooking_shares_default = technology_shares
    missing_countries = set(selected_countries) - set(df_sh_shares.index)
    if missing_countries:
        raise ValueError(f"Countries missing from shared households shares: {sorted(missing_countries)}")

    # STEP 3 GENERATE SATURATION RATES
    df_sh_saturation, df_sc_saturation, df_appliances_saturation, df_cooking_saturation = (
        build_sat.create_saturation_rates_all_prepared(
            target_years,
            helpers.SATURATION_SCENARIO_MAP,
            scenario_name,
        )
    )

    # validate that distribution shares are not higher than 100%
    share_cols = [
        "residential oil_share",
        "residential gas_share",
        "residential biomass_share",
        "electricity residential_share",
    ]
    df_sh_shares = df_sh_shares.copy()
    df_sh_shares[share_cols] = df_sh_shares[share_cols].fillna(0)
    share_sum = df_sh_shares[share_cols].sum(axis=1)
    remainder = 1 - share_sum
    df_sh_shares.loc[remainder > 0, "residential oil_share"] += remainder[remainder > 0]
    if (share_sum > 1).any():
        print("WARNING: Some residential shares sum to more than 1. Check df_sh_shares input values.")

    units_dict = helpers.generate_units_dictionary()

    try:
        df_population_macro = build_metric_df(
            "Population",
            "Population",
            df_population,
            target_years,
            scenario_name,
            growth_pathway,
            selected_countries,
            units_dict,
        )
        df_area_macro = build_metric_df(
            "Residential Area per Person",
            "Residential Area per Person",
            df_m2_p_all,
            target_years,
            scenario_name,
            growth_pathway,
            selected_countries,
            units_dict,
        )
        df_person_dw_macro = build_metric_df(
            "Persons per Dwelling",
            "Persons per Dwelling",
            df_person_dw,
            target_years,
            scenario_name,
            growth_pathway,
            selected_countries,
            units_dict,
        )


        share_macro_dfs = []
        for share_col, metric_name in SH_METRICS.items():
            share_macro_dfs.append(
                build_constant_metric_df(
                    metric_name,
                    metric_name,
                    df_sh_shares[share_col],
                    target_years,
                    scenario_name,
                    selected_countries,
                    units_dict,
                )
            )

        default_series = pd.Series({country: 0.0 for country in selected_countries})
        share_macro_dfs.append(
            build_constant_metric_df(
                "Share of Heat Pumps for Space Cooling",
                "Share of Heat Pumps for Space Cooling",
                default_series,
                target_years,
                scenario_name,
                selected_countries,
                units_dict,
            )
        )
        share_macro_dfs.append(
            build_constant_metric_df(
                "Share of Air Conditioning for Space Cooling",
                "Share of Air Conditioning for Space Cooling",
                pd.Series({country: 1.0 for country in selected_countries}),
                target_years,
                scenario_name,
                selected_countries,
                units_dict,
            )
        )

        cooking_series = {}
        for metric_name, col in COOKING_METRICS.items():
            if col is None:
                cooking_series[metric_name] = pd.Series({country: 0.0 for country in selected_countries})
            else:
                cooking_series[metric_name] = build_cooking_shares(
                    col,
                    selected_countries,
                    df_cooking_shares_africa,
                    df_cooking_shares_default,
                    default_value=0.0,
                )

        cooking_sum = sum(cooking_series.values())
        cooking_remainder = 1 - cooking_sum
        cooking_series["Share of Traditional Biomass Stoves for Cooking"] = (
            cooking_series["Share of Traditional Biomass Stoves for Cooking"]
            + cooking_remainder.where(cooking_remainder > 0, 0)
        )
        if (cooking_sum > 1).any():
            print("WARNING: Some cooking shares sum to more than 1. Check cooking share inputs.")

        for metric_name, series in cooking_series.items():
            share_macro_dfs.append(
                build_constant_metric_df(
                    metric_name,
                    metric_name,
                    series,
                    target_years,
                    scenario_name,
                    selected_countries,
                    units_dict,
                )
            )

        water_heating_map = {
            "Share of Electric Stoves for Cooking": "Share of Electric Heaters for Water Heating",
            "Share of Natural Gas Stoves for Cooking": "Share of Natural Gas Boilers for Water Heating",
            "Share of LPG Stoves for Cooking": "Share of LPG Boilers for Water Heating",
            "Share of Kerosene Stoves for Cooking": "Share of Kerosene Boilers for Water Heating",
            "Share of Traditional Biomass Stoves for Cooking": "Share of Traditional Biomass Boilers for Water Heating",
        }

        water_heating_series = {
            wh_metric: cooking_series[cooking_metric]
            for cooking_metric, wh_metric in water_heating_map.items()
        }
        water_heating_metrics_ordered = [
            "Share of Oil Boilers for Water Heating",
            "Share of LPG Boilers for Water Heating",
            "Share of Natural Gas Boilers for Water Heating",
            "Share of Kerosene Boilers for Water Heating",
            "Share of Coal Boilers for Water Heating",
            "Share of Biogas Boilers for Water Heating",
            "Share of Traditional Biomass Boilers for Water Heating",
            "Share of Modern Biomass Boilers for Water Heating",
            "Share of Hydrogen Boilers for Water Heating",
            "Share of Solar Heating for Water Heating",
            "Share of District Heating for Water Heating",
            "Share of Electric Heaters for Water Heating",
            "Share of Heat Pumps for Water Heating",
        ]
        for metric_name in water_heating_metrics_ordered:
            series = water_heating_series.get(
                metric_name,
                pd.Series({country: 0.0 for country in selected_countries}),
            )
            share_macro_dfs.append(
                build_constant_metric_df(
                    metric_name,
                    metric_name,
                    series,
                    target_years,
                    scenario_name,
                    selected_countries,
                    units_dict,
                )
            )

        intensity_sh, intensity_wh, intensity_sc, intensity_cooking, intensity_appliances = (
            build_en_int.insert_energy_intensities()
        )
        space_heating_intensity_map = build_en_int.get_space_heating_intensity_map()
        space_cooling_intensity_map = build_en_int.get_space_cooling_intensity_map()
        cooking_intensity_map = build_en_int.get_cooking_intensity_map()
        water_heating_intensity_map = build_en_int.get_water_heating_intensity_map()
        df_cagr_macro, df_cagr_intensity_macro = build_cagr_blocks(
            selected_countries,
            target_years,
            base_year,
            units_dict,
            intensity_sh,
            intensity_wh,
            intensity_sc,
            intensity_cooking,
            intensity_appliances,
            space_heating_intensity_map,
            space_cooling_intensity_map,
            cooking_intensity_map,
            water_heating_intensity_map,
        )

        df_sh_saturation_macro = build_sh_saturation(
            df_sh_saturation,
            target_years,
            scenario_name,
            selected_countries,
            units_dict,
        )
        df_sc_saturation_macro = build_sc_saturation(
            df_sc_saturation,
            target_years,
            scenario_name,
            selected_countries,
            units_dict,
        )
        df_appliances_saturation_macro = build_appliances_saturation(
            df_appliances_saturation,
            target_years,
            scenario_name,
            selected_countries,
            units_dict,
        )
        df_cooking_saturation_macro = build_cooking_saturation(
            df_cooking_saturation,
            target_years,
            scenario_name,
            selected_countries,
            units_dict,
        )
        df_water_heating_saturation_macro = build_saturation_water_heating_macro(
            df_cooking_saturation,
            target_years,
            scenario_name,
            selected_countries,
            units_dict,
        )

        df_all = pd.concat(
            [
                df_population_macro,
                df_area_macro,
                df_person_dw_macro,
                df_sh_saturation_macro,
                df_sc_saturation_macro,
                df_appliances_saturation_macro,
                df_cooking_saturation_macro,
                df_water_heating_saturation_macro,
                *share_macro_dfs,
                df_cagr_macro,
                df_cagr_intensity_macro,
            ],
            ignore_index=True,
        )

        dimensions = ["type", "metric name", "year", "scenario", "units"]
        if df_all[dimensions].isna().any().any() or df_all.duplicated(dimensions[:-1]).any():
            raise ValueError("Residential configuration dimensions must be populated and unique")
        values = df_all[selected_countries].apply(pd.to_numeric, errors="coerce")
        if not np.isfinite(values.to_numpy()).all():
            raise ValueError("Residential source data produced missing or nonfinite parameter values")
        if (values.loc[df_all["type"] != "CAGR"] < 0).any().any():
            raise ValueError("Residential non-CAGR parameters must be nonnegative")
        output_dir = Path(output_dir) if output_dir is not None else Path(__file__).resolve().parent / "output_data/CONFIG"
        output_dir.mkdir(parents=True, exist_ok=True)
        df_all.to_csv(output_dir / "DEFAULT_RESIDENTIAL_CONFIG.csv", index=False)
        return df_all

    except Exception as e:
        raise RuntimeError(f"Error generating residential configuration: {e}") from e


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build source-backed residential configuration")
    parser.add_argument("--input-dir", type=Path, help="Residential raw input directory (country_specific/ and global/)")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--countries", nargs="+")
    parser.add_argument("--years", nargs="+", type=int)
    parser.add_argument("--shares-csv-path", type=Path, help="External households_shares_all_countries.csv")
    args = parser.parse_args(argv)
    create_csv_all(args.input_dir, args.output_dir, args.countries, args.years, args.shares_csv_path)


if __name__ == "__main__":
    main()
