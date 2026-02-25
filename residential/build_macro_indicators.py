import numpy as np
import pandas as pd
import os
from pathlib import Path
from sklearn.metrics import r2_score, mean_squared_error
from helpers import load_all_files
# from .helpers import load_all_files
   
def clean_df_ssp(df):
    df = df[df.iloc[:,0].str.startswith("SSP")]
    df = df.set_index(' ',drop=True)
    return df

def country_name (key): # TODO: Make this function better
    # saving the names of the countries
    if 'chart-data_pop_'in key:
        name = key.split('chart-data_pop_')[1].split('.csv')[0]
    elif 'chart-data_gdp_'in key:
        name = key.split('chart-data_gdp_')[1].split('.csv')[0]
    return name

def add_countries (dfs,countries):
    for df, country in zip(dfs, countries):
        df.insert(0,"Country", country)
    return dfs

def prepare_ssp_df (df):
    df = pd.concat(df,axis=0, ignore_index= False)
    df.reset_index(inplace=True)
    df.columns = ["SSP"] + list(df.columns[1:])
    df.set_index(["Country","SSP"],drop=True,inplace=True)
    df = df * 1000000 # units is person
    return df

def interpolate (df):
    if "Unit" in df.columns:
        df.drop("Unit", axis=1, inplace=True)
    df.columns = df.columns.astype(int)
    df = (
        df
        .reindex(columns=range(df.columns.min(), df.columns.max() + 1))
        .interpolate(axis=1, method="linear")
    )
    return df

def process_ssp_pop(dfs_country_spe): 
    # create df_population until 2070 for all DevKopSys countries in all SSP scenarios # TODO: Download all countries!!!
    df_ssp = [clean_df_ssp(df) for key, df in dfs_country_spe.items() if key.startswith('chart-data_pop')]
    country_names = [country_name(key) for key, df in dfs_country_spe.items() if key.startswith('chart-data_pop')]
    df_ssp = add_countries(df_ssp,country_names)
    df_ssp = prepare_ssp_df (df_ssp) 
    #interpolate all values
    df_ssp.drop("Unit", axis=1, inplace=True)
    df_ssp = interpolate(df_ssp)
    return df_ssp

def process_ssp_gdp(dfs_country_spe):
    # create df_gdp in 2015 € until 2070 for all DevKopSys countries in all SSP scenarios
    df_ssp = [clean_df_ssp(df) for key, df in dfs_country_spe.items() if key.startswith('chart-data_gdp')]
    country_names = [country_name(key) for key, df in dfs_country_spe.items() if key.startswith('chart-data_gdp')]

    df_ssp = add_countries(df_ssp,country_names)

    df_ssp = prepare_ssp_df (df_ssp)
    # present value in 2015
    column_position = df_ssp.columns.get_loc('Unit') 
    df_gdp_euro = df_ssp.iloc[:,column_position+1:].apply(
        convert_to_euro,
        args=(2005, 2015, 0.803), 
        axis=1
        )
    df_gdp_euro = interpolate(df_gdp_euro)
    df_gdp_euro.insert(
        0,
        "Unit",
        "billion €2015/yr")
    return df_gdp_euro

def process_ssp_gdp_percapita(df_gdp_euro,df_population):
    # Generate gdp per capita
    # unit = df_gdp_euro["Unit"]
    gdp_values = df_gdp_euro.drop(columns=["Unit"], errors="ignore")
    pop_values = df_population.drop(columns=["Unit"], errors="ignore")
    df_gdp_ssp = gdp_values / (pop_values / 1000)  # billion is assumed 10e9
    df_gdp_ssp.insert(0, "Unit", "GDP/per capita [€2015]")
    df_gdp_ssp = df_gdp_ssp.rename_axis(index = {"Country" : "country"})
    # df_gdp_ssp.insert(0, "Unit", unit)
    return df_gdp_ssp

# to make all values comparable convert everything to euros (default €2015)
def convert_to_euro(currency_val, year_currency, to_year, ex_rate): 
    val_euros = currency_val * ex_rate  
    avg_inflation_rate = 0.01792 # yearly default rate from: https://www.officialdata.org/2005-euro-in-2015 #TODO: This can be change or adapted
    current_euro = val_euros * ((1 + avg_inflation_rate) ** abs((to_year-year_currency)))
    return current_euro

def weighted_m2_pcapita (df):
    df.drop("GDP per Capita (2012 PPP USD/person) / [m2/p]", axis=1, inplace=True)
        # This are IEE assumptions
    weighted_data={
        "Average" : 0.15,
        "Minimum" : 0.8,
        "Maximum" : 0.05,
        } # TODO: validate if the weighting makes sense....or use only average (Lukas recommendation)

    # engineered feature call m2_weighted, that basically simplifies the spectrum of the three features
    df_interm = pd.DataFrame()
    for column, weight in weighted_data.items():
        df_interm[column] = df[column] * weight 

    df["m2_weighted"] = df_interm["Average"] +  df_interm["Minimum"] +  df_interm["Maximum"]
    return df

# define the regression formulas
def linear_reg(df,deg):
    X = df.iloc[:,0] # X: training (historical data)
    y = df.iloc[:,1] # y: training (historical data)
    # generate coefficients with predifine polynom degree
    coef = np.polyfit(X,y,deg=deg)
    return coef

def regression_m2_p(df, df_prediction):
    # select features for regression
    df = df[["GDP_per_capita [€2015]","m2_weighted"]]
    polynom_deg = 1 # polynom degree 2 seems from the graphic to be the best fit...
    # TODO: this method could be improved
    coef = linear_reg(df,polynom_deg)   # find coefficients
    # use df_prediction (in our case the gdp per capita)
    column_position = df_prediction.columns.get_loc('Unit')
    df_m2_p_all = df_prediction.iloc[:,column_position+1:].apply(lambda x: prediction(coef,x),axis =0)
    return df_m2_p_all

def prediction(coef,x):
    # Predict y value for a single x
    y_single_pred = np.polyval(coef, x)
    return y_single_pred

def best_fit(coef,x_test,y_test):
    y_pred = np.polyval(coef, x_test)
    # Calculate R-squared
    r_squared = r2_score(y_test, y_pred)
    # Calculate RMSE (root mean squared error)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    return r_squared, rmse

def remove_asterisk(value):
    if isinstance(value, str):
        return value.replace('*', '')
    return value

#Uploading macroeconomic indicators
def upload_required_globals(df1, df2, df3):
    country_mapping = {
    "Bahamas, The":"Bahamas",
    "Brunei Darussalam": "Brunei",
    "Cabo Verde": "Cape Verde",
    "Congo, Rep.":"Congo",
    "Curaçao": "Curacao",
    "Côte d’Ivoire": "Cote d'Ivoire",	
    "Czech Republic":"Czechia",
    "Korea, Dem. People's Rep.":"Democratic People's Republic of Korea",
    "Congo, Dem. Rep.":"Democratic Republic of the Congo",
    "Democratic Republic of Congo": "Democratic Republic of the Congo",	
    "Egypt, Arab Rep.":"Egypt",
    "Gambia, The":"Gambia",
    "Iran, Islamic Rep.":"Iran",
    "Kyrgyz Republic":"Kyrgyzstan",
    "Lao PDR":"Lao People's Democratic Republic",
    "Micronesia, Fed. Sts.":"Micronesia (Federated States of)",
    "Korea, Rep.":"Republic of Korea",
    "Moldova":"Republic of Moldova",
    "North Macedonia":"Republic of North Macedonia",
    "São Tomé and Príncipe": "Sao Tome and Principe",
    "St. Kitts and Nevis":"Saint Kitts and Nevis",
    "St. Lucia":"Saint Lucia",
    "St. Martin (French part)":"Saint Martin (French Part)",
    "St. Vincent and the Grenadines":"Saint Vincent and the Grenadines",
    "Slovak Republic":"Slovakia",
    #"South Korea" : ""
    "Türkiye":"Turkey",
    "United Kingdom":"United Kingdom of Great Britain and Northern Ireland",
    "Virgin Islands (U.S.)":"United States Virgin Islands",
    "United States":"United States of America",
    "Venezuela, RB":"Venezuela (Bolivarian Republic of)",
    "Vietnam":"Viet Nam",
    "Yemen, Rep.":"Yemen"
    }
    
    df_income_class = clean_worldbank(df1)
    df_income_class.rename(index=country_mapping,inplace=True)

    df_hst_gdp = historical_gdp(df2) # hisorical gdp is necessary to classify 
    df_hst_gdp.rename(index=country_mapping,inplace=True)
    
    # extract input data - people per dwelling (ppd) from undesa
    df_ppd = clear_unsd_ppd(df3)

    return df_income_class, df_hst_gdp, df_ppd

def clean_worldbank(df):
    # discard all countries/regions without classification
    df = df[~df.iloc[:,3].isna()]
    df.set_index("Economy", drop= True,inplace=True)
    df.rename_axis("country",inplace=True)
    df.drop(["Lending category","Code"], axis=1,inplace=True)
    return df

def historical_gdp(df):
    # use the latest values - most upt to date
    updated_info = df.groupby("Entity")["Year"].idxmax()
    df = df.iloc[updated_info]
    df["GDP per capita(€2015)"] = df["GDP per capita, PPP (constant 2017 international $)"].apply(convert_to_euro,args=(2017,2015,0.92))
    df.drop("GDP per capita, PPP (constant 2017 international $)",inplace=True,axis=1)

    # cleand df
    df.set_index("Entity", drop= True,inplace=True)
    df.rename_axis("country",inplace=True)
    df["GDP per capita(€2015)"] = pd.to_numeric(round(df["GDP per capita(€2015)"],2))
    df.rename(columns={'Year':"GDP_year"},inplace=True)
    df = df[["Code","GDP per capita(€2015)", "GDP_year"]]
    return df

def clear_unsd_ppd(df):
    col_names = df.iloc[0]
    df.drop(index=3,axis=0,inplace=True)
    df.columns = col_names
    df.columns.name=None

    # selecting useful columns 
    df = df.iloc[:,:9]

    # read datetime correctly # TODO: add this as a function
    df["Reference date (dd/mm/yyyy)"] = pd.to_datetime(df.loc[:,"Reference date (dd/mm/yyyy)"])
    df.reset_index(inplace=True) # reset index necessary to successfully groupby

    # use the latest values # TODO: add this as a function
    updated_info = df.groupby("Country or area")["Reference date (dd/mm/yyyy)"].idxmax()
    df = df.iloc[updated_info]

    # set country as index
    df = df.set_index("Country or area",drop= True).rename_axis("country")

    # select only relevant data - Average household size (number of members)
    df = pd.DataFrame(df.iloc[:,4])
    df["Average household size (number of members)"] = pd.to_numeric(df["Average household size (number of members)"],errors='coerce')
    return df

def create_categories(df_economics_std, df_all):
    # generate the default bins and labels for all regions
    # NOTE: This is only possible for DevKopSys countries
    # TODO: Download all this for all countries in the world

    bins_dict = {}
    labels_dict = {}
    years_ssp_gdp =[2018, 2030, 2040, 2050, 2060,2070]
    years_ssp_gdp = [2018] + list(range(2030, 2071))

    for region in df_economics_std.index.get_level_values(0).unique():
        bins = df_economics_std.loc[(region),"mean"].values
        labels = df_economics_std.loc[(region),"mean"].index
        
        # Pair bins with labels and sort them
        sorted_pairs = sorted(zip(bins, labels))
        sorted_bins, sorted_labels = zip(*sorted_pairs)

        # Convert back to list
        sorted_bins = list(sorted_bins)
        sorted_bins= np.insert(sorted_bins,0,0)
        sorted_labels = list(sorted_labels)

        bins_dict[region] = sorted_bins
        labels_dict[region] = sorted_labels

        # now we create the classes as the default values for the projections.
        df_class = df_all.groupby(["Region","Income group"])["Average household size (number of members)"].mean() #agg({"mean","std","count"})
        df_mean_classification = pd.DataFrame(df_class)

    return df_mean_classification, bins_dict, labels_dict, years_ssp_gdp

# This function make use of other df generated along the way, how to deal with it to add all functions at the beginning?
def categorize_persons_per_dwelling(row, df_mean_classification, bins_dict, labels_dict, years_ssp_gdp):
    region = row['Region']
    if region not in bins_dict:
        print(f"Region {region} not found in bins_dict")
        return row
    
    bins = bins_dict[region]
    labels = labels_dict[region]

    for col in years_ssp_gdp:
        value = row.loc[col]
        # in case the projections of the country fall out of boundries
        if value > bins[-1]: 
            bins = bins_dict['Europe & Central Asia']
            labels = labels_dict['Europe & Central Asia']
        income_group = pd.cut([value], bins=bins, labels=labels, include_lowest=True)[0]

        if pd.isna(income_group):
            row[col] = df_mean_classification.loc[('Europe & Central Asia','High income')].values[0]
        else: 
            try:
                row[col] = df_mean_classification.loc[(region,income_group)].values[0]
            except KeyError:
                print(f"KeyError accessing df_mean_classification with region {region} and income_group {income_group}")
                row[col] = np.nan
    return row

def create_macro_indicators_all():

    dfs_country_spe, dfs_global = load_all_files("residential") # specify the sector to load the data. It is also possible to configurate it with "industry"
    
    df_population = process_ssp_pop(dfs_country_spe)
    df_gdp = process_ssp_gdp(dfs_country_spe)
    df_gdp_ssp = process_ssp_gdp_percapita(df_gdp,df_population)

    # opening global info for residencial floor area--> Using this as based
    df_m2_p = dfs_global["residential_floor_area_arab_regions.csv"].copy()
    df_m2_p["GDP_per_capita [€2015]"] = df_m2_p[
        "GDP per Capita (2012 PPP USD/person) / [m2/p]"
        ].apply(convert_to_euro,args=(2012,2015,0.92)) # convert currency to 2015 and clean df
    
    df_m2_p = weighted_m2_pcapita(df_m2_p)
    df_m2_p_all = regression_m2_p(df_m2_p, df_gdp_ssp ) # the regassion uses the GDP per capita and the weighted data
    df_m2_p_all = round(df_m2_p_all,2)

    # upload all raw interim data
    df1 = dfs_global['CLASS_worldbank.xlsx'].copy()
    df2 = dfs_global['gdp-per-capita-worldbank.csv'].copy()
    df3 = dfs_global['undesa_pd_2022_hh-size-composition_ALL_COUNTRIES_raw.xlsx'].iloc[3:,:].copy()
    globals = upload_required_globals(df1,df2, df3)

    df_income_class, df_hst_gdp, df_ppd = globals
    
    df_economics= pd.merge(
        df_hst_gdp,
        df_income_class, 
        right_index= True, 
        left_index=True
    )
    df_economics_std = df_economics.groupby(["Region","Income group"])["GDP per capita(€2015)"].agg({"mean","count","std"})
    
    df_all =pd.merge(
        df_economics,
        df_ppd, 
        left_index= True, 
        right_index=True)

    df_gdp_ssp = pd.merge(
        df_gdp_ssp.reset_index(),
        df_economics["Region"],
        on="country",
        how="left",
    )

    
    categories = create_categories(df_economics_std, df_all)
    df_mean_classification, bins_dict, labels_dict, years_ssp_gdp = categories

    # generate person/dwelling for all interested countries
    df_ppd_source = df_gdp_ssp.drop(columns=["Unit"], errors="ignore")
    df_person_dw = df_ppd_source.apply(
        categorize_persons_per_dwelling,
        axis=1,
        args=(df_mean_classification, bins_dict, labels_dict, years_ssp_gdp),
    )
    df_person_dw.set_index(["country", "SSP", "Region"], drop=True, inplace=True)

    year_cols = pd.to_numeric(df_person_dw.columns, errors="coerce")
    df_person_dw.columns = year_cols
    df_person_dw = df_person_dw.loc[:, year_cols.notna()]
    df_person_dw.columns = df_person_dw.columns.astype(int)

    for year in df_person_dw.columns:
        if year not in years_ssp_gdp:
            df_person_dw[year] = np.nan
    df_person_dw = df_person_dw.reindex(
        columns=range(df_person_dw.columns.min(), df_person_dw.columns.max() + 1)
    ).interpolate(axis=1).ffill(axis=1).bfill(axis=1)
    df_person_dw = round(df_person_dw, 2)

    return df_population, df_gdp_ssp, df_m2_p_all, df_person_dw, df_economics


def export_macro_indicators_csv(output_dir=None):
    df_population, df_gdp_ssp, df_m2_p_all, df_person_dw, df_economics = create_macro_indicators_all()

    if output_dir is None:
        output_dir = Path(__file__).resolve().parent / "output_data/interim_indicators/macro_indicators"
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    output_files = {
        "population": output_dir / "population.csv",
        "gdp_ssp": output_dir / "gdp_ssp.csv",
        "m2_pp": output_dir / "m2_pp.csv",
        "person_dw": output_dir / "person_dw.csv",
        "economic_ind": output_dir / "economic_ind.csv",
    }

    df_population.to_csv(output_files["population"], index=True)
    df_gdp_ssp.to_csv(output_files["gdp_ssp"], index=True)
    df_m2_p_all.to_csv(output_files["m2_pp"], index=True)
    df_person_dw.to_csv(output_files["person_dw"], index=True)
    df_economics.to_csv(output_files["economic_ind"], index=True)

    return output_files

## Only necessary for local testing
# if __name__=="__main__":
#     export_macro_indicators_csv()