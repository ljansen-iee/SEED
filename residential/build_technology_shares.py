import os
import numpy as np
import pandas as pd
import tabula

# from helpers import load_all_files
from helpers import load_all_files, open_pdf
from build_macro_indicators import*

# from helpers import load_all_files # Only if I want to run the code directly, otherwise relative path
# NOTE: For technology shares, UNSD data is use for space cooling has only be downloaded for the devkopsys countries

def remove_asterisk(value):
    if isinstance(value, str):
        return value.replace('*', '')
    return value   

# desaggregated df into energy sectors based on UNSD
# NOTE: Left out--> "other consumptions" and "non-energy use". 
def clean_unsd(df):
    df.rename({"Transactions(down)/Commodity(right)": "Commodity"},axis = 1,inplace = True)
    df.replace("---", np.nan, inplace=True)
    df = df.applymap(remove_asterisk)
    df_num = df.iloc[:,2:].apply(pd.to_numeric, errors= "coerce")
    df.iloc[:,2:] = df_num
    return df

def extract_unsd_residential(df):
    residential_sectors = ['Households']
    df = df.query("Commodity in @residential_sectors")
    return df

def clean_unsd_residential(df):
    df.rename({
    'Country (2021)':'Country' ,
    'Oil Products': "residential oil", 
    'Natural Gas':"residential gas",
    'Biofuels and Waste': "residential biomass", 
    'Electricity': "electricity residential",
    "Heat": "heat"
    }, 
    axis = 1, 
    inplace = True)

    df = df[["Country", 
             "residential oil", 
             "residential gas",
             "residential biomass", 
            "electricity residential", 
            'heat']]
    df.set_index(["Country"],drop = True, inplace = True)
    df = df.fillna(0)
    df = round(df * 0.277,2) # from TJ to GWh
    df["total GWh"] = df.sum(axis= 1)
    return df

def aggregate_biomass(df):
    if df.columns[0] == "fuel type":
        df = df.T
        df.columns =df.iloc[0]
        df.columns.name = ""
        df.index.name = "country"
        df.drop(df.index[0],inplace=True)

    biomass_to_sum = ["coal", "charcoal", "wood", "ag. waste/straw", "dung", "other"] # simplifying the energy sources
    existing_columns = [col for col in biomass_to_sum if col in df.columns]

    if existing_columns:
        df["biomass"] = df[existing_columns].sum(axis=1)

    else:
        df["biomass"] = 0

    df.rename({
        "LPG/LNG/biogas" : "natural gas",
    }, axis= 1, inplace= True)

    if 'lpg' in df.columns:
        df["natural gas"] += df["lpg"]
        df.drop(columns ="lpg", inplace= True)

    df = df[["electricity","natural gas","kerosene","biomass"]]
    return df

def clean_cooking_shares(df):
    df_cooking_columns= [
        "country",
        "year",
        "LPG/LNG/biogas",
        "electricity",
        "kerosene",
        "coal",
        "charcoal",
        "wood",
        "ag. waste/straw",
        "dung",
        "other",
        "solid-fuel share"
        ]

    df.columns = df_cooking_columns

    df.replace({
        "Côte d’Ivoire": "Cote d'Ivoire",
        "Congo (Brazzaville)": "Congo"
        },inplace= True)
    
    df.set_index("country", inplace= True, drop=True)

    df.drop("year", inplace= True, axis= 1)

    df = df.applymap(lambda x: float(x[:-1]))

    df = aggregate_biomass(df)

    return df

def add_north_africa_data(df_cooking_shares_ssa):

    macro_indicators = create_macro_indicators_all()
    df_population, df_gdp_ssp, df_m2_p_all, df_person_dw, df_economics  = macro_indicators

    df_cooking_shares_ssa_all = pd.merge(
        df_cooking_shares_ssa,
        df_economics[["Region","Income group"]], 
        on ="country",
        how = "left"  
        )       
    # NOTE: we generate the default values based on the income group
    distribution_per_income_group= round(df_cooking_shares_ssa_all.groupby(
        ["Region","Income group"]).mean(),
        2)
    
    distribution_per_income_group = distribution_per_income_group.loc[
        ("Sub-Saharan Africa"), slice(None)].reset_index() 
    
    north_africa = {
        'country': [
            'Algeria', 
            'Egypt', 
            'Libya', 
            'Morocco', 
            "Lebanon", 
            'Tunisia'
            ]
        } # NOTE: I left Malta out, because it is a high income country (?) and therefore no available profile   
    north_africa =pd.DataFrame(north_africa)
                               
    north_africa_indicators = pd.merge(
        north_africa,
        df_economics[["Region", "Income group"]],
        on ="country",
        how="left"
        )

    distribution_north_africa = pd.merge(
        north_africa_indicators,
        distribution_per_income_group,
        on= "Income group",
        how = "left"
        )
    
    df = pd.concat([df_cooking_shares_ssa_all.reset_index(),distribution_north_africa],ignore_index= True)
    df.set_index(["country","Region","Income group"], drop= True,inplace=True)
    df = df/100
    return df

def clean_cooking_shares_default(df):
    df = df[df["Share of SSA"].notna() & df["Fuel type"].notna()]
    df.columns = ["fuel type", "default country"]
    df["fuel type"] = df["fuel type"].str.lower()
    df["default country"] = df["default country"].str[:-1].astype(float)
    df = aggregate_biomass(df)
    df = df/100
    return df
    
def create_technology_shares_all():

    # Set base_dir to the parent directory of this script (i.e., the 'residential' folder)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # If this script is already in 'residential', use its parent
    if os.path.basename(base_dir).lower() != 'residential':
        base_dir = os.path.join(base_dir, 'residential')
    dfs_country_spe, dfs_global = load_all_files("", base_dir=base_dir)  # robust to script location

    # NOTE: For Space Heating we use the UNSD data shares of the residential sector
    df = pd.concat([df for key, df in dfs_country_spe.items() if key.startswith('UNSD')], ignore_index=True)
    df_unsd = clean_unsd(df)
    df_sh_shares = extract_unsd_residential(df_unsd)
    df_sh_shares = clean_unsd_residential (df_sh_shares)    

    # calculate energy shares
    columns_to_calculate = [
        'residential oil', 
        'residential gas', 
        'residential biomass',
        'electricity residential', 
        'heat'
    ]

    df_sh_shares[[f'{col}_share' for col in columns_to_calculate]] = df_sh_shares[columns_to_calculate].apply(lambda x: round(x / df_sh_shares["total GWh"],2), axis= 0)

    zero_share_columns = [
        "lpg_share",
        "kerosene_share",
        "coal_share",
        "biogas_share",
        "modern_biomass_share",
        "hydrogen_share",
        "solar_share",
        "district_heating_share",
        "heat_pumps_share",
    ]
    for col in zero_share_columns:
        if col not in df_sh_shares.columns:
            df_sh_shares[col] = 0.0

    # Load tables for cooking
    # cwd =os.getcwd()
    # file_path= os.path.join(
    #     cwd,
    #     "residential",
    #     "input_data",
    #     "global",
    #     "98667-WP-P146621-PUBLIC-Box393179B.pdf",
    #     )
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, "input_data", "global", "98667-WP-P146621-PUBLIC-Box393179B.pdf")

    df = open_pdf(file_path, "140")
    df = pd.DataFrame(df[0])
    df_cooking_shares_ssa = clean_cooking_shares(df)
    df_cooking_shares_ssa = df_cooking_shares_ssa

    df_cooking_shares_africa = add_north_africa_data(df_cooking_shares_ssa)
    
    # TODO: Using the SSA interpolate for all other countries in the world?
    df = open_pdf(file_path, "145")
    df = pd.DataFrame(df[0].iloc[:,:2])
    df_cooking_shares_default = clean_cooking_shares_default(df)
    
    return df_sh_shares, df_cooking_shares_africa, df_cooking_shares_default


    # TODO: create a method for LATAM

if __name__=="__main__":
    df_sh_shares, df_cooking_shares_africa, df_cooking_shares_default = create_technology_shares_all()

    print(df_sh_shares)
    # print(df_cooking_shares_africa)
    # print(df_cooking_shares_default)
    





   
