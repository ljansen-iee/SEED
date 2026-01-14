import pandas as pd
import os

def build_scenarios():
    demand_options = [
        "Current Policies", 
        "Progessive Measuraments", 
        "Ambitious Net Zero"
    ]
    demand_years =[
        2030, 
        2050
    ]
    
    return demand_options,demand_years

def build_CAGR_default():
    demand_options, demand_years = build_scenarios()

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

    df_CAGR_default = pd.concat(
        [df_CAGR_2030,df_CAGR_2050], 
        axis=1
        )

    df_CAGR_default.columns = pd.MultiIndex.from_product(
        [demand_options, demand_years], 
        names=['Scenario', 'Year']
        )
    
    df_CAGR_default.index.name="energy_intensity"
    df_CAGR_default.insert(0,"subregion","Default")
    df_CAGR_default.reset_index(inplace=True)
    df_CAGR_default.set_index(["subregion","energy_intensity"], inplace=True)
    
    return df_CAGR_default

def build_Africa_regions():
    # path = os.path.join(os.path.dirname(os.getcwd()),"residential","input_data","global","UNSD — Methodology.csv")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(
        base_dir,
        "input_data",
        "global",
        "UNSD — Methodology.csv"
    )
    df = pd.read_csv(file_path, delimiter=";")
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
                energy_intensity_values = df_CAGR_default[scenario].droplevel(level= 0)
                adjusted_values = energy_intensity_values.values - ((1 - df_investment_shares.loc[subregion, "relative_shares"]) * energy_intensity_values.values)
                multi_index = pd.MultiIndex.from_product([
                        [subregion],
                        energy_intensity_values.index.tolist()],
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

    return df_CAGR_Africa

def build_CAGR_LATAM():
    demand_options, demand_years = build_scenarios()

    #NOTE: CAGR based on IEA scenarios,i.e. STEPS & APS, for the whole region. For the residential sector: https://iea.blob.core.windows.net/assets/1055131a-8dc4-488b-9e9e-7eb4f72bf7ad/LatinAmericaEnergyOutlook.pdf
    #TODO: Add a third scenario from IEE. For know we used the one from Morocco provided by hypat
    
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

    df_CAGR_LATAM = pd.concat(
        [df_CAGR_2030_LATAM,df_CAGR_2050_LATAM], 
        axis=1
        )

    # create the MultiIndex for the columns
    df_CAGR_LATAM.columns = pd.MultiIndex.from_product(
        [demand_options, demand_years], 
        names=['scenario', 'year']
        )
    
    df_CAGR_LATAM.index.name = ("energy_intensity")
    df_CAGR_LATAM.insert(0,"subregion","LATAM")
    df_CAGR_LATAM.reset_index(inplace=True)

    df_CAGR_LATAM.set_index(["subregion","energy_intensity"], inplace=True)

    return df_CAGR_LATAM

def build_CAGR():
    df_CAGR_LATAM = build_CAGR_LATAM()
    df_CAGR_Africa = build_CAGR_Africa()
    df_CAGR_default = build_CAGR_default()

    df_CAGR = pd.concat([df_CAGR_LATAM, df_CAGR_Africa, df_CAGR_default], axis = 0)
    return df_CAGR


# Only necessary for local testing
# if __name__=="__main__":
#     df_CAGR = build_CAGR()

#     file_path = r"C:\Users\eduque\Fraunhofer\DeV-KopSys-2 - Globale ESA\04_methods_and_models\Sectoral_demand\01_Buttom_up_workflow\residential\output_data\CAGR_output.xlsx"
#     df_CAGR.to_excel(file_path,"CAGR", index_label= True)


