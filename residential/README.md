# The residential workflow provides options to customised parameters via csv files per demand-scenario, country and planning horizon.

# Rules for residential

It processes SSP,UNSD data and global sources to create demand projections. Results are saves as "xxxx". 

# PROS

# CONS

# configuration options



# quick methodology explained:

We categorized input_data into country-specific and global
	-country-specific:
		(i) ssp gdp and ssp population, source: https://www.climate-solutions-explorer.eu/dashboard

		(ii) UNSD Energy balance is use to create technology Distribution shares. default year is 2021. source: https://unstats.un.org/unsd/energystats/dataPortal/


	-global:


# Steps

1) Set config["custom_data"]["industry_demand"] = True

2) Create demand csv files for each "demand"-scenario and "planning_horizon" and save to "data/custom/industry_demand_{demand}_{planning_horizon}.csv". 


# Adding a new Country - 
		note: after download please complete the csv name with the category and name of country like this, e.g. "_gpd_country_name" or "_pop_country_name"
		note: after download please complete the csv name with the word "UNSD_" 
# Changing Scenario configurations


### OLD VERSION ###
Getting started
Usage
    How to add a country:
        1. Download the following
            country_specific: 
            - SSP pathways - Projections(pop & GDP): https://www.climate-solutions-explorer.eu/dashboard/ISL/overview
            - UNSD - Historical values (fuel shares): https://unstats.un.org/unsd/energystats/dataPortal/
            
            global:
            -
            -
            -


Calibration of projections:
    to validate: C:\Users\eduque\Fraunhofer\DeV-KopSys-2 - Globale ESA\04_methods_and_models\Sectoral_End-Use_Energy_Scenario\validation
        - EGYPT 