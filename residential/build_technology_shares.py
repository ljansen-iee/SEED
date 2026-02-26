import os
import numpy as np
import pandas as pd
import tabula
from pathlib import Path

from helpers import open_pdf
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


def load_centralized_residential_shares(share_mode: str = "base_period_2017_2023"):
    root_dir = Path(__file__).resolve().parents[1]
    shares_path = root_dir / "output_data" / "interim" / "shares" / "households_shares_all_countries.csv"
    if not shares_path.exists():
        raise FileNotFoundError(
            f"Centralized residential shares not found: {shares_path}. Run top-level build_shares.py first."
        )

    shares_df = pd.read_csv(shares_path)
    mode_mask = shares_df["share_mode"].astype(str).str.lower() == str(share_mode).strip().lower()
    shares_df = shares_df[mode_mask].copy()
    if shares_df.empty:
        raise ValueError(f"No rows found for share_mode '{share_mode}' in {shares_path}.")

    shares_df = shares_df.rename(
        columns={
            "country": "Country",
            "oil": "residential oil_share",
            "gas": "residential gas_share",
            "biomass": "residential biomass_share",
            "electricity": "electricity residential_share",
        }
    )

    required_share_cols = [
        "residential oil_share",
        "residential gas_share",
        "residential biomass_share",
        "electricity residential_share",
    ]
    for column in required_share_cols:
        shares_df[column] = pd.to_numeric(shares_df[column], errors="coerce").fillna(0.0)

    df_sh_shares = shares_df[["Country", *required_share_cols]].copy()
    df_sh_shares.set_index("Country", drop=True, inplace=True)

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

    return df_sh_shares
    
def create_technology_shares_all():
    df_sh_shares = load_centralized_residential_shares(share_mode="base_period_2017_2023")

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
    





   
