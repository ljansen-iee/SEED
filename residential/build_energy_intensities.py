SPACE_HEATING_INTENSITY_METRICS = [
    "Final Energy Intensity of Oil Boilers for Space Heating",
    "Final Energy Intensity of LPG Boilers for Space Heating",
    "Final Energy Intensity of Natural Gas Boilers for Space Heating",
    "Final Energy Intensity of Kerosene Boilers for Space Heating",
    "Final Energy Intensity of Coal Boilers for Space Heating",
    "Final Energy Intensity of Biogas Boilers for Space Heating",
    "Final Energy Intensity of Traditional Biomass Boilers for Space Heating",
    "Final Energy Intensity of Modern Biomass Boilers for Space Heating",
    "Final Energy Intensity of Hydrogen Boilers for Space Heating",
    "Final Energy Intensity of Solar Heating for Space Heating",
    "Final Energy Intensity of District Heating for Space Heating",
    "Final Energy Intensity of Electric Heaters for Space Heating",
    "Final Energy Intensity of Heat Pumps for Space Heating",
]

WATER_HEATING_INTENSITY_METRICS = [
    "Final Energy Intensity of Oil Boilers for Water Heating",
    "Final Energy Intensity of LPG Boilers for Water Heating",
    "Final Energy Intensity of Natural Gas Boilers for Water Heating",
    "Final Energy Intensity of Kerosene Boilers for Water Heating",
    "Final Energy Intensity of Coal Boilers for Water Heating",
    "Final Energy Intensity of Biogas Boilers for Water Heating",
    "Final Energy Intensity of Traditional Biomass Boilers for Water Heating",
    "Final Energy Intensity of Modern Biomass Boilers for Water Heating",
    "Final Energy Intensity of Hydrogen Boilers for Water Heating",
    "Final Energy Intensity of Solar Heating for Water Heating",
    "Final Energy Intensity of District Heating for Water Heating",
    "Final Energy Intensity of Electric Heaters for Water Heating",
    "Final Energy Intensity of Heat Pumps for Water Heating",
]

SPACE_COOLING_INTENSITY_METRICS = [
    "Final Energy Intensity of Heat Pumps for Space Cooling",
    "Final Energy Intensity of Air Conditioning for Space Cooling",
]

COOKING_INTENSITY_METRICS = [
    "Final Energy Intensity of Electric Stoves for Cooking",
    "Final Energy Intensity of Natural Gas Stoves for Cooking",
    "Final Energy Intensity of LPG Stoves for Cooking",
    "Final Energy Intensity of Kerosene Stoves for Cooking",
    "Final Energy Intensity of Traditional Biomass Stoves for Cooking",
]

APPLIANCES_INTENSITY_METRICS = [
    "Final Energy Intensity of Electrical Appliances",
]


def insert_energy_intensities():
    intensity_sh = 86.45
    intensity_sc = 71.15
    intensity_wh = 2215
    intensity_cooking = 2604
    intensity_appliances = 994
    return intensity_sh, intensity_wh, intensity_sc, intensity_cooking, intensity_appliances

