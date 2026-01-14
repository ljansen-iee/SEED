import os
import numpy as np
import pandas as pd

from scipy.interpolate import interp1d
from sklearn.linear_model import LinearRegression

from helpers import load_all_files
from build_macro_indicators import*

def build_saturation_sh():
    df_saturation_dict = {
        "baseline": [
            {"2021": 0.08}], # this an assumpation derivated from "what if analysis tool from excel"
        "Current Policies": [
            {"2030": 0.50,
            "2050": 0.60}],
        "Progessive Measuraments": [
            {"2030": 0.50,
            "2050": 0.65}],
        "Ambitious Net Zero":[
            {"2030": 0.60,
            "2050": 0.65}]}
    
    df_sh_saturation ={}

    for scenario, data in df_saturation_dict.items():
        flattened_data = {year: value for d in data for year, value in d.items()}
        df = pd.DataFrame(list(flattened_data.items()), columns=['Year', 'Value in %'])
        df_sh_saturation[scenario] = df
        # TODO: saturation of space heaating is hard to now and to project as well. Baseline is default value choosen for Morocco....THINK ABOUT A METHODOLOGY
    return df_sh_saturation

def clean_build_saturation_sh(df):
    df = pd.concat(df,axis= 0)
    df.index.names = ['Scenario', 'Index']
    df.reset_index(level='Index', drop=True, inplace=True)
    df.set_index('Year', append=True, inplace=True)
    df = df.reorder_levels(['Scenario', 'Year'])
    return df


def interpolation(years, values, new_years):
    linear_interp = interp1d(years, values, kind='linear', fill_value="extrapolate")
    return linear_interp(new_years)

def build_saturation_sc():
    graphic_data = {
        "Tunisia": [40.3, 78, 88, 91.5], 
        "Algeria": [37.2, 70, 81, 84.5 ],
        "Morocco": [9.3, 22, 35, 49]
    } # this was read manually from paper

    mena_sc_saturation = pd.DataFrame(graphic_data)
    mena_sc_saturation = mena_sc_saturation.transpose()

    iee_assumption_2050 = pd.DataFrame({
        "Tunisia": [100], 
        "Algeria": [95],
        "Morocco": [70]
    }) # TODO: Define if this is realistic.... ask jochen?

    iee_assumption = iee_assumption_2050.transpose()
    mena_sc_saturation = pd.concat([mena_sc_saturation,iee_assumption], axis= 1)
    mena_sc_saturation.columns = [2015,2025,2030,2035,2050]
    mena_sc_saturation.columns.name = "year"

    #interpolate
    df =  mena_sc_saturation.transpose().reset_index()
    new_years = np.arange(2015,2051,1)
    df = {country: interpolation(pd.to_numeric(df['year']), df[country], new_years) for country in df.columns[1:]}
    df = round(pd.DataFrame(df, index=new_years),2)
    df = df.transpose()
    df.index.name = "country"
    mena_sc_saturation = df.copy()

    macro_indicators = create_macro_indicators_all()
    df_population, df_gdp_ssp, df_m2_p_all, df_person_dw, df_economics  = macro_indicators

    df = df_gdp_ssp[df_gdp_ssp["SSP"] == "SSP2"] # ssp2 is the "Middle of the road" pathway, hence use for this step....
    # clean data
    df = df.drop(["SSP", "Unit", "Region"],axis= 1).set_index("country",drop=True)
    df.columns.name = "year"
    df.index.name = ""
    df = df.T.reset_index()

    new_years = np.arange(2015,2051,1)

    df = {country: interpolation(pd.to_numeric(df['year']), df[country], new_years) for country in df.columns[1:]}
    df = pd.DataFrame(df, index=new_years).T
    df = round(df,2)
    df.index.name = "country"

    df_gdp_ssp2 = df.copy()
   
    # separate the data into training and the others
    reference_countries = ["Algeria", "Tunisia","Morocco"]
    #step 1
    reference_gdp_ssp = df_gdp_ssp2.loc[reference_countries]
    reference_gdp_ssp
    #step2
    df_gdp_ssp2 = df_gdp_ssp2.drop(reference_countries)
    df_gdp_ssp2

    
    models = {}

    # Train a model for each country
    for country in mena_sc_saturation.index:
        # Filter the data for the current country
        X_gdp = np.array(reference_gdp_ssp.loc[country].reset_index(drop=True)).reshape(-1, 1)
        y_ac = np.array(mena_sc_saturation.loc[country])
        
        # Create and train the model
        model = LinearRegression()
        model.fit(X_gdp, y_ac)
        # Store the model
        models[country] = model

    # Test with all coeficcients
    # Define a function to use the combined coefficients for prediction
    def predict_weighted(models,df_gdp_ssp2):

        def predict_with_combined_model(X, intercept, coefficients):
            return np.dot(X, coefficients) + intercept

        # Extract coefficients
        coefficients1 = models["Algeria"].coef_
        coefficients2 = models["Tunisia"].coef_
        coefficients3 = models["Morocco"].coef_

        # Define weights # TODO: TB Discuss
        weight1 = 0.25
        weight2 = 0.25
        weight3 = 0.5

        # Combine coefficients
        combined_coefficients = (weight1 * coefficients1 +
                                weight2 * coefficients2 +
                                weight3 * coefficients3)

        intercept = models["Morocco"].intercept_ # this is beta0

        predictions = {}
        for country in df_gdp_ssp2.index:
                gdp_values = np.array(df_gdp_ssp2.loc[country]).reshape(-1,1)
                # Make predictions
                predictions[country] = predict_with_combined_model(gdp_values, intercept, combined_coefficients)      

        predictions = pd.DataFrame(predictions,  index=df_gdp_ssp2.columns).clip(upper=100)

        return predictions

    df_sc_saturation_prediction = predict_weighted(models,df_gdp_ssp2)

    df_sc_saturation_prediction = round(df_sc_saturation_prediction/100,2)
    
    mena_sc_saturation = mena_sc_saturation.transpose()

    df_sc_saturation = pd.merge(
            mena_sc_saturation,
            df_sc_saturation_prediction,
            how = "inner",
            left_index=True, 
            right_index=True, 
        )

    return df_sc_saturation

def build_saturation_appliances(df):
    # clean data
    columns = df.iloc[3]
    df = df.iloc[4:]
    df.columns = columns
    df = df[['Country Name', df.columns[-3]]] # Drop code
    df.columns = ['country',"2021"] # TODO: select year automatically (2021 was the last updated year)
    df.set_index("country",drop=True, inplace=True)
    df.rename({'Egypt, Arab Rep.' : "Egypt"},axis=0, inplace= True)
    return df
    
def project_saturation_appliances(df):
    # TODO: For DKS countries this is enough. For African countries, it might be necessary to have another method like, liner regression or bins and labels
    df[[2030,2040]] = np.nan
    df[2050] = 100 # Assumption
    df = df.interpolate(method='linear', axis=1) # per default with linear interpolation
    df = round(df/100,2)
    return df

def build_saturation_cooking(df):
    columns = df.iloc[3]
    df = df.iloc[4:]
    df.columns = columns
    df = df[["Country Name",df.columns[-3]]] # 2021 was the last updated year
    df.columns = ["country","2021"]
    df.set_index("country",drop=True, inplace=True)
    df.rename({'Egypt, Arab Rep.' : "Egypt"},axis=0, inplace= True)
    return df

def project_saturation_cooking(df):
    # TODO: Do the same with the bins a the labels to define the projections according to the GDP per capita
    df[[2030,2040]] = np.nan
    df[2050] = 100 # IEE Assumption
    df = df.interpolate(method='linear', axis=1)
    df = round(df/100,2)
    # TODO: For DKS countries this is enough. For African countries, it might be necessary to have another method like, liner regression or bins and labels
    return df
    
def create_saturation_rates_all():
    # load all raw data    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dfs_country_spe, dfs_global = load_all_files("",base_dir=base_dir)
    
    # build saturation for Space Heating
    df = build_saturation_sh() # This step is all assumption from IEE
    df_sh_saturation = clean_build_saturation_sh(df)
    
    # build saturation for Space Cooking
    df_sc_saturation = build_saturation_sc()

    # build saturation for Appliances
    df = dfs_global["wb_acces_ele_2024_all.csv"].copy()
    df = build_saturation_appliances(df)
    df_appliances_saturation = project_saturation_appliances(df)

    # build saturation for Cooking
    df = dfs_global["wb_acces_cooking_2024_all.csv"]
    df = build_saturation_cooking(df)
    df_cooking_saturation = project_saturation_cooking(df)

    return df_sh_saturation, df_sc_saturation, df_appliances_saturation, df_cooking_saturation

# Only necessary for local testing
if __name__=="__main__":
    df_sh_saturation, df_sc_saturation, df_appliances_saturation, df_cooking_saturation = create_saturation_rates_all()

    print(df_sh_saturation)

    
   


