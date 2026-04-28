import pandas as pd
import os
from pathlib import Path

def build_scenarios():
    reference_pathway_options = [
        "Current Policies",
        "Progessive Measuraments",
        "Ambitious Net Zero",
    ]  # keep names as-is to avoid breaking downstream mapping

    target_years = [2030, 2035, 2040, 2045, 2050]
    return reference_pathway_options, target_years


def _interp_tables(df_start: pd.DataFrame, start_year: int, df_end: pd.DataFrame, end_year: int, year: int) -> pd.DataFrame:
    """
    Linear interpolation of CAGR *rates* between two anchor-year tables.
    All tables are expected to be in PERCENT units (e.g. -2.0 for -2%).
    """
    if year <= start_year:
        return df_start
    if year >= end_year:
        return df_end
    w = (year - start_year) / float(end_year - start_year)
    return df_start * (1.0 - w) + df_end * w


def build_CAGR_default(interpolate_years: bool = True):
    reference_pathway_options, target_years = build_scenarios()

    # NOTE: values below are in PERCENT per year
    df_2030 = pd.DataFrame(
        {
            "Final Energy Intensity of Space Heating": [-1, -1, -1],
            "Final Energy Intensity of Space Cooling": [-2, -2, -2],
            "Final Energy Intensity of Water Heating": [-2, -2, -2],
            "Final Energy Intensity of Cooking": [-0.25, -0.25, -0.25],
            "Final Energy Intensity of Electrical Appliances": [-0.25, -0.25, -0.25],
        }
    ).transpose()

    # If you want a different regime post-2030, set different values here.
    df_2050 = pd.DataFrame(
        {
            "Final Energy Intensity of Space Heating": [-1, -1, -1],
            "Final Energy Intensity of Space Cooling": [-2, -2, -2],
            "Final Energy Intensity of Water Heating": [-1, -1, -1],
            "Final Energy Intensity of Cooking": [-0.5,-0.5,-0.5],
            "Final Energy Intensity of Electrical Appliances": [-0.5,-0.5,-0.5],
        }
    ).transpose()

    df_2030.columns = reference_pathway_options
    df_2050.columns = reference_pathway_options

    columns = []
    data = []
    for scenario in reference_pathway_options:
        for year in target_years:
            if interpolate_years:
                base_df = _interp_tables(df_2030[[scenario]], 2030, df_2050[[scenario]], 2050, year)
                series = base_df[scenario]
            else:
                # legacy behavior: 2030/2035 use 2030 table; 2040+ use 2050 table
                base_df = df_2030 if year in (2030, 2035) else df_2050
                series = base_df[scenario]
            data.append(series)
            columns.append((scenario, year))

    df = pd.concat(data, axis=1)
    df.columns = pd.MultiIndex.from_tuples(columns, names=["Scenario", "Year"])

    df.index.name = "energy_intensity"
    df.insert(0, "subregion", "Default")
    df.reset_index(inplace=True)
    df.set_index(["subregion", "energy_intensity"], inplace=True)

    return df.round(4)  # PERCENT


def build_Africa_regions():
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        base_dir = os.getcwd()

    file_path = os.path.join(base_dir, "input_data", "global", "UNSD — Methodology.csv")
    df = pd.read_csv(file_path, delimiter=",")

    df = df[df["Region Name"] == "Africa"]
    df = df[["Sub-region Name", "Intermediate Region Name", "Country or Area"]]

    df["Intermediate Region Name"] = df["Intermediate Region Name"].fillna(df["Sub-region Name"])
    df.drop("Sub-region Name", axis=1, inplace=True)
    df.columns = ["subregion", "country"]

    df_africa_regions = pd.DataFrame(df).set_index("country")
    df_africa_subregions = df_africa_regions["subregion"].unique()
    return df_africa_regions, df_africa_subregions


def build_private_investment_shares_per_region():
    df_africa_regions, df_africa_subregions = build_Africa_regions()

    data = {
        "subregion": df_africa_subregions,
        "private investment [$ Billions by 2030]": [27.2, 59.7, 13.6, 84.4, 28.5],
    } # source: Mobilizing private sector financing for climate and green growth in Africa 2023. ISBN.9780976565567
    df = pd.DataFrame(data).set_index("subregion")

    df["shares"] = df["private investment [$ Billions by 2030]"] / df["private investment [$ Billions by 2030]"].sum() * 100

    # Higher finance gap => harder transition => multiplier < 1 => slower CAGR magnitude.
    # Using inverse ratio: baseline (Northern Africa) / region gap.
    # Clipped to [0.5, 2.0] to avoid extreme scaling.
    if "Northern Africa" not in df.index:
        raise KeyError("Expected 'Northern Africa' in investment shares table index.")
    na_share = df.loc["Northern Africa", "shares"]
    df["relative_shares"] = (na_share / df["shares"]).clip(lower=0.0, upper=3.0)

    return df


def build_CAGR_Africa(interpolate_years: bool = True):
    # default values in PERCENT
    df_CAGR_default = build_CAGR_default(interpolate_years=interpolate_years)
    df_investment_shares = build_private_investment_shares_per_region()

    df_all = []
    for scenario in df_CAGR_default.columns:
        df_region = []
        for subregion in df_investment_shares.index:
            # drop the "Default" subregion level so index is energy_intensity only
            base_rates = df_CAGR_default[scenario].droplevel(level=0)  # PERCENT
            mult = float(df_investment_shares.loc[subregion, "relative_shares"])
            adjusted = base_rates.values * mult

            multi_index = pd.MultiIndex.from_product(
                [[subregion], base_rates.index.tolist()],
                names=["subregion", "energy_intensity"],
            )
            df_region.append(pd.DataFrame(adjusted, index=multi_index, columns=[scenario]))

        df_all.append(pd.concat(df_region, axis=0))

    df_CAGR_Africa = pd.concat(df_all, axis=1)
    df_CAGR_Africa.columns = pd.MultiIndex.from_tuples(df_CAGR_Africa.columns, names=["scenario", "year"])
    return df_CAGR_Africa.round(4)  # PERCENT


def build_CAGR_LATAM(interpolate_years: bool = True):
    reference_pathway_options, target_years = build_scenarios()

    # NOTE: values below are in PERCENT per year
    df_2030 = pd.DataFrame(
        {
            "Final Energy Intensity of Space Heating": [0.3, -1.2, -3],
            "Final Energy Intensity of Space Cooling": [0.3, -1.2, -0.5],
            "Final Energy Intensity of Water Heating": [0.3, -1.2, -1],
            "Final Energy Intensity of Cooking": [0.3, -1.2, -1.75],
            "Final Energy Intensity of Electrical Appliances": [0.3, -1.2, -1.5],
        }
    ).transpose()

    df_2050 = pd.DataFrame(
        {
            "Final Energy Intensity of Space Heating": [0.7, 0.0, -3],
            "Final Energy Intensity of Space Cooling": [0.7, 0.0, -0.5],
            "Final Energy Intensity of Water Heating": [0.7, 0.0, -1],
            "Final Energy Intensity of Cooking": [0.7, 0.0, -1.75],
            "Final Energy Intensity of Electrical Appliances": [0.7, 0.0, -1.5],
        }
    ).transpose()

    df_2030.columns = reference_pathway_options
    df_2050.columns = reference_pathway_options

    columns = []
    data = []
    for scenario in reference_pathway_options:
        for year in target_years:
            if interpolate_years:
                base_df = _interp_tables(df_2030[[scenario]], 2030, df_2050[[scenario]], 2050, year)
                series = base_df[scenario]
            else:
                base_df = df_2030 if year in (2030, 2035) else df_2050
                series = base_df[scenario]
            data.append(series)
            columns.append((scenario, year))

    df = pd.concat(data, axis=1)
    df.columns = pd.MultiIndex.from_tuples(columns, names=["scenario", "year"])

    df.index.name = "energy_intensity"
    df.insert(0, "subregion", "LATAM")
    df.reset_index(inplace=True)
    df.set_index(["subregion", "energy_intensity"], inplace=True)

    return df.round(4)  # PERCENT


def build_CAGR(interpolate_years: bool = True):
    df_CAGR_LATAM = build_CAGR_LATAM(interpolate_years=interpolate_years)
    df_CAGR_Africa = build_CAGR_Africa(interpolate_years=interpolate_years)
    df_CAGR_default = build_CAGR_default(interpolate_years=interpolate_years)
    return pd.concat([df_CAGR_LATAM, df_CAGR_Africa, df_CAGR_default], axis=0)


# Countries belonging to the LATAM subregion.
_LATAM_COUNTRIES = {
    "Argentina", "Bolivia", "Brazil", "Chile", "Colombia", "Costa Rica",
    "Cuba", "Dominican Republic", "Ecuador", "El Salvador", "Guatemala",
    "Haiti", "Honduras", "Jamaica", "Mexico", "Nicaragua", "Panama",
    "Paraguay", "Peru", "Trinidad and Tobago", "Uruguay", "Venezuela",
}


def build_country_cagr(selected_countries: list, target_years: list = None, interpolate_years: bool = True) -> pd.DataFrame:
    """Map each country to its regional CAGR table and return a combined DataFrame.

    Countries are assigned to subregions as follows:
    - African countries: matched via UNSD Methodology file to the correct
      African subregion (Northern Africa, Eastern Africa, etc.).
    - LATAM countries: assigned to the 'LATAM' subregion.
    - All other countries: assigned to 'Default'.

    Returns:
        pd.DataFrame indexed by (country, energy_intensity) with
        MultiIndex columns (scenario, year). CAGR values in PERCENT per year.
    """
    if target_years is None:
        _, target_years = build_scenarios()

    df_cagr_all = build_CAGR(interpolate_years=interpolate_years)

    # Build country → subregion mapping
    df_africa_regions, _ = build_Africa_regions()
    africa_country_to_subregion = df_africa_regions["subregion"].to_dict()

    def get_subregion(country: str) -> str:
        if country in africa_country_to_subregion:
            return africa_country_to_subregion[country]
        if country in _LATAM_COUNTRIES:
            return "LATAM"
        return "Default"

    frames = []
    for country in selected_countries:
        subregion = get_subregion(country)

        if subregion not in df_cagr_all.index.get_level_values("subregion"):
            print(f"WARNING: subregion '{subregion}' for country '{country}' not found in CAGR table. Falling back to Default.")
            subregion = "Default"

        country_rates = df_cagr_all.loc[subregion].copy()
        # Filter to requested target years only
        year_mask = [col for col in country_rates.columns if col[1] in target_years]
        country_rates = country_rates[year_mask]
        country_rates.index = pd.MultiIndex.from_product(
            [[country], country_rates.index.tolist()],
            names=["country", "energy_intensity"],
        )
        frames.append(country_rates)

    if not frames:
        raise ValueError("No CAGR data could be assembled for the selected countries.")

    return pd.concat(frames, axis=0)