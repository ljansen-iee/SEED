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

# Configuration options
    ## basics:
        BASE_YEAR: refers to the starting point for building the demands. Possible years from 2019 until 2023 
        GROWTH_PATHWAY: The Shared Socioeconomic Pathways (SSPs) are used as reference trajectories of development FOR GDP and Population. 
            Options are SSP1, SSP2, SSP3, SSP4, SSP5
  
            # mitigation challenges vs adaption challenges
            # SSP1 : Sustainability ("Taking the Green Road") - low challenges in both mitigation and adaptation
            # SSP2 : "Middle of the Road" - intermediate challenges in both mitigation and adaptation
            # SSP3 : Regional Rivalry ("A Rocky Road") - high challenges in both mitigation and adaptation
            # SSP4 : Inequality ("A Road Divided") - adaptation challenges dominate
            # SSP5 : Fossil-fueled Development ("Taking the Highway") - mitigation challenges dominate
            more information-->  https://en.wikipedia.org/wiki/Shared_Socioeconomic_Pathways

        SCENARIO_NAME: max. three scenarios


    
    ## configuration parameters
        TRANSPORT_CONFIG_FILE - a preliminary selection for a configuration is provided based on a mix of methodologies to build parameters. 
    
        Parameters are possible to configurate:
        
        - macro indicators:
        - technology shares: 
           - the shares for cooking technologies are the reference value for shares for water heating, unless noted different.
           - air conditioning is by defaul 100% electric.
        -


        Data is available for the following countries: 
            [ "Republic of the Congo", "Egypt", "Ethiopia", "Ghana","Kenya","Namibia","Niger",
                "Algeria","Argentina","Brazil","Chile","Colombia","Mexico","Peru","Venezuela",
                "Morocco","Tunisia","Tanzania","Libya",
                "Australia", "Canada", "China", "France", "Germany",  
                "India", "Indonesia", "Italy", "Japan", "Mexico","Russia", "Saudi Arabia", 
                "South Africa", "South Korea", "United Kingdom", "United States of America"
            ]

* IMPORTANT NOTE: in the parameters.csv it is possible to change only the CAGR for the final energy intensity. If final energy intensity absolute values are change in this conf file, it wont be possible to overwrite the values.

# Steps in PyPSA

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