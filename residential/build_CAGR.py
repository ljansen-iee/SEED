import pandas as pd
import os
from pathlib import Path

def build_scenarios():
    reference_pathway_options = [
        "Current Policies", 
        "Progessive Measuraments", 
        "Ambitious Net Zero"
    ] # based on available IEA scenario names

    target_years =[
        2030,
        2035,
        2040,
        2045,
        2050
    ]
    
    return reference_pathway_options,target_years

def build_CAGR_default():
    reference_pathway_options, target_years = build_scenarios()

    #NOTE: This are default values taken from the HYPAT base assumptions

    df_CAGR_2030 = pd.DataFrame({
        "Final Energy Intensity of Space Heating" : [-1, -2, -3],
        "Final Energy Intensity of Space Cooling" : [-0.13, -0.25, -0.5],
        "Final Energy Intensity of Water Heating" : [-0.25, -0.5, -1],
        "Final Energy Intensity of Cooking" : [-0.63, -1.25, -1.75],
        "Final Energy Intensity of Electrical Appliances": [3, 2, 1.5],
        }
        ).transpose()

    df_CAGR_2050 = pd.DataFrame({
        "Final Energy Intensity of Space Heating" : [-1, -2, -3],
        "Final Energy Intensity of Space Cooling" : [-0.13, -0.25, -0.5],
        "Final Energy Intensity of Water Heating" : [-0.25, -0.5, -1],
        "Final Energy Intensity of Cooking" : [-0.63, -1.25, -1.75],
        "Final Energy Intensity of Electrical Appliances": [3, 2, 1.5],
        }
        ).transpose()

    df_CAGR_2030.columns = reference_pathway_options
    df_CAGR_2050.columns = reference_pathway_options

    columns = []
    data = []
    for scenario in reference_pathway_options:
        for year in target_years:
            base_df = df_CAGR_2030 if year in (2030, 2035) else df_CAGR_2050
            data.append(base_df[scenario])
            columns.append((scenario, year))

    df_CAGR_default = pd.concat(data, axis=1)
    df_CAGR_default.columns = pd.MultiIndex.from_tuples(
        columns, names=['Scenario', 'Year']
    )
    
    df_CAGR_default.index.name="energy_intensity"
    df_CAGR_default.insert(0,"subregion","Default")
    df_CAGR_default.reset_index(inplace=True)
    df_CAGR_default.set_index(["subregion","energy_intensity"], inplace=True)
    
    return (df_CAGR_default / 100).round(4)

def build_Africa_regions():
    # path = os.path.join(os.path.dirname(os.getcwd()),"residential","input_data","global","UNSD — Methodology.csv")
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        base_dir = os.getcwd()
    file_path = os.path.join(
        base_dir,
        "input_data",
        "global",
        "UNSD — Methodology.csv"
    )
    df = pd.read_csv(file_path, delimiter=",")
    df = df[df["Region Name"] == "Africa"]
    df = df[['Sub-region Name','Intermediate Region Name', 'Country or Area']]

    df["Intermediate Region Name"] = df["Intermediate Region Name"].fillna(df["Sub-region Name"])
    df.drop("Sub-region Name",axis=1,inplace =True)
    df.columns = ["subregion","country"]
    df_africa_regions = pd.DataFrame(df)
    df_africa_regions.set_index("country",inplace=True)

    df_africa_subregions = df_africa_regions["subregion"].unique()

    return df_africa_regions, df_africa_subregions

def build_private_investment_shares_per_region():
    df_africa_regions, df_africa_subregions = build_Africa_regions ()

    data = {
            "subregion" : df_africa_subregions,
            "private investment [$ Billions by 2030]" : [
                    27.2, 59.7, 13.6, 84.4, 28.5
            ] # from the african economic outlook 2023: 
        }
    df = pd.DataFrame(data)

    df["shares"] = df["private investment [$ Billions by 2030]"].div(df["private investment [$ Billions by 2030]"].sum())*100
    df.set_index("subregion", inplace=True)
    df["relative_shares"] = [df.loc["Northern Africa","shares"]/df.loc[subregion,"shares"] for subregion in df.index]

    return df


def build_CAGR_Africa():
    df_CAGR_default = build_CAGR_default()
    df_investment_shares = build_private_investment_shares_per_region()

    df_all = []
    for scenario in df_CAGR_default.columns:
        df_region =[]
        for subregion in df_investment_shares.index:
                energy_intensity_shares = df_CAGR_default[scenario].droplevel(level= 0)
                adjusted_values = energy_intensity_shares.values - ((1 - df_investment_shares.loc[subregion, "relative_shares"]) * energy_intensity_shares.values)
                multi_index = pd.MultiIndex.from_product([
                        [subregion],
                        energy_intensity_shares.index.tolist()],
                        names=['subregion', 'energy_intensity']
                        )
                df = pd.DataFrame(adjusted_values,
                                index = multi_index,
                                columns=[scenario]
                                )
                df_region.append(df)
               
        df_region_combined  = pd.concat(df_region,ignore_index= False,axis=0)
        df_all.append(df_region_combined)

    # Concatenate all DataFrames into one
    df_CAGR_Africa = pd.concat(df_all, ignore_index=False,axis =1)
    df_CAGR_Africa.columns = pd.MultiIndex.from_tuples(df_CAGR_Africa.columns, names=['scenario', 'year'])

    return (df_CAGR_Africa / 100).round(4)

def build_CAGR_LATAM():
    reference_pathway_options, target_years = build_scenarios()

    #NOTE: CAGR based on IEA scenarios,i.e. STEPS & APS, for the whole region. For the residential sector: https://iea.blob.core.windows.net/assets/1055131a-8dc4-488b-9e9e-7eb4f72bf7ad/LatinAmericaEnergyOutlook.pdf
    
    df_CAGR_2030_LATAM = pd.DataFrame({
    "Final Energy Intensity of Space Heating" : [0.3, -1.2, -3],
    "Final Energy Intensity of Space Cooling" : [0.3, -1.2, -0.5],
    "Final Energy Intensity of Water Heating" : [0.3, -1.2, -1],
    "Final Energy Intensity of Cooking" : [0.3, -1.2, -1.75],
    "Final Energy Intensity of Electrical Appliances": [0.3, -1.2, 1.5],
    }).transpose()

    df_CAGR_2050_LATAM = pd.DataFrame({
    "Final Energy Intensity of Space Heating" : [0.7, 0.0, -3],
    "Final Energy Intensity of Space Cooling" : [0.7, 0.0, -0.5],
    "Final Energy Intensity of Water Heating" : [0.7, 0.0, -1],
    "Final Energy Intensity of Cooking" : [0.7, 0.0, -1.75],
    "Final Energy Intensity of Electrical Appliances": [0.7, 0.0, 1.5],
    }).transpose()

    df_CAGR_2030_LATAM.columns = reference_pathway_options
    df_CAGR_2050_LATAM.columns = reference_pathway_options

    columns = []
    data = []
    for scenario in reference_pathway_options:
        for year in target_years:
            base_df = df_CAGR_2030_LATAM if year in (2030, 2035) else df_CAGR_2050_LATAM
            data.append(base_df[scenario])
            columns.append((scenario, year))

    df_CAGR_LATAM = pd.concat(data, axis=1)

    # create the MultiIndex for the columns
    df_CAGR_LATAM.columns = pd.MultiIndex.from_tuples(
        columns, names=['scenario', 'year']
    )
    
    df_CAGR_LATAM.index.name = ("energy_intensity")
    df_CAGR_LATAM.insert(0,"subregion","LATAM")
    df_CAGR_LATAM.reset_index(inplace=True)

    df_CAGR_LATAM.set_index(["subregion","energy_intensity"], inplace=True)

    return (df_CAGR_LATAM / 100).round(4)

def build_CAGR():
    df_CAGR_LATAM = build_CAGR_LATAM()
    df_CAGR_Africa = build_CAGR_Africa()
    df_CAGR_default = build_CAGR_default()

    df_CAGR = pd.concat([df_CAGR_LATAM, df_CAGR_Africa, df_CAGR_default], axis = 0)
    return df_CAGR


def build_country_cagr(selected_countries, target_years=None):
    df_cagr = build_CAGR()
    df_africa_regions, _ = build_Africa_regions()

    if target_years is None:
        _, target_years = build_scenarios()

    subregion_list = df_cagr.index.get_level_values("subregion").unique().tolist()

    def resolve_subregion(country):
        if country in ("LATAM", "Default"):
            return country
        if country in df_africa_regions.index:
            return df_africa_regions.loc[country, "subregion"]
        if "LATAM" in subregion_list:
            return "LATAM"
        if "Default" in subregion_list:
            return "Default"
        return subregion_list[0] if subregion_list else None

    energy_intensity_list = (
        df_cagr.index.get_level_values("energy_intensity").unique().tolist()
    )

    reference_pathway_options, _ = build_scenarios()
    columns = []
    row_keys = []
    for scenario in reference_pathway_options:
        for year in target_years:
            columns.append((scenario, year))
            row_keys.append((scenario, year))

    data = {}
    for country in selected_countries:
        subregion = resolve_subregion(country)
        rows = []
        for energy_intensity in energy_intensity_list:
            values = []
            for scenario_src, year in row_keys:
                try:
                    values.append(
                        df_cagr.loc[(subregion, energy_intensity), (scenario_src, year)]
                    )
                except KeyError:
                    values.append(float("nan"))
            rows.append(values)

        idx = pd.MultiIndex.from_product(
            [[country], energy_intensity_list],
            names=["country", "energy_intensity"],
        )
        data[country] = pd.DataFrame(rows, index=idx, columns=pd.MultiIndex.from_tuples(columns))

    return pd.concat(data.values(), axis=0)


def build_all_countries_cagr(target_years=None):
    df_africa_regions, _ = build_Africa_regions()
    selected_countries = df_africa_regions.index.tolist() + ["LATAM", "Default"]
    return build_country_cagr(selected_countries, target_years=target_years)


def export_all_countries_cagr_csv(output_path=None):
    df_cagr = build_all_countries_cagr()
    df_cagr = df_cagr.reset_index()
    if isinstance(df_cagr.columns, pd.MultiIndex):
        df_cagr.columns = [
            "_".join([str(part) for part in col if part != ""]).strip("_")
            for col in df_cagr.columns
        ]
    if output_path is None:
        output_dir = Path(__file__).resolve().parent / "output_data/interim_indicators/macro_indicators"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "CAGR_residential.csv"
    df_cagr.to_csv(output_path, index=False)
    return output_path


# Only necessary for local testing
# if __name__=="__main__":
#     export_all_countries_cagr_csv()

