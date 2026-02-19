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

SPACE_HEATING_INTENSITY_VALUES = {
    "Final Energy Intensity of Oil Boilers for Space Heating": 86.45,
    "Final Energy Intensity of LPG Boilers for Space Heating": 86.45,
    "Final Energy Intensity of Natural Gas Boilers for Space Heating": 86.45,
    "Final Energy Intensity of Kerosene Boilers for Space Heating": 86.45,
    "Final Energy Intensity of Coal Boilers for Space Heating": 86.45,
    "Final Energy Intensity of Biogas Boilers for Space Heating": 86.45,
    "Final Energy Intensity of Traditional Biomass Boilers for Space Heating": 86.45,
    "Final Energy Intensity of Modern Biomass Boilers for Space Heating": 86.45,
    "Final Energy Intensity of Hydrogen Boilers for Space Heating": 86.45,
    "Final Energy Intensity of Solar Heating for Space Heating": 77.81,
    "Final Energy Intensity of District Heating for Space Heating": 77.81,
    "Final Energy Intensity of Electric Heaters for Space Heating": 77.81,
    "Final Energy Intensity of Heat Pumps for Space Heating": 77.81,
}

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

WATER_HEATING_INTENSITY_VALUES = {
    "Final Energy Intensity of Oil Boilers for Water Heating": 2215,
    "Final Energy Intensity of LPG Boilers for Water Heating": 2215,
    "Final Energy Intensity of Natural Gas Boilers for Water Heating": 2215,
    "Final Energy Intensity of Kerosene Boilers for Water Heating": 2215,
    "Final Energy Intensity of Coal Boilers for Water Heating": 2215,
    "Final Energy Intensity of Biogas Boilers for Water Heating": 2215,
    "Final Energy Intensity of Traditional Biomass Boilers for Water Heating": 2215,
    "Final Energy Intensity of Modern Biomass Boilers for Water Heating": 2215,
    "Final Energy Intensity of Hydrogen Boilers for Water Heating": 2215,
    "Final Energy Intensity of Solar Heating for Water Heating": 1993.5,
    "Final Energy Intensity of District Heating for Water Heating": 1993.5,
    "Final Energy Intensity of Electric Heaters for Water Heating": 1993.5,
    "Final Energy Intensity of Heat Pumps for Water Heating": 1993.5,
}

SPACE_COOLING_INTENSITY_METRICS = [
    "Final Energy Intensity of Heat Pumps for Space Cooling",
    "Final Energy Intensity of Air Conditioning for Space Cooling",
]

SPACE_COOLING_INTENSITY_VALUES = {
    "Final Energy Intensity of Heat Pumps for Space Cooling": 71.75,
    "Final Energy Intensity of Air Conditioning for Space Cooling": 71.75,
}

COOKING_INTENSITY_METRICS = [
    "Final Energy Intensity of Electric Stoves for Cooking",
    "Final Energy Intensity of Natural Gas Stoves for Cooking",
    "Final Energy Intensity of LPG Stoves for Cooking",
    "Final Energy Intensity of Kerosene Stoves for Cooking",
    "Final Energy Intensity of Traditional Biomass Stoves for Cooking",
]

COOKING_INTENSITY_VALUES = {
    "Final Energy Intensity of Electric Stoves for Cooking": 792,
    "Final Energy Intensity of Natural Gas Stoves for Cooking": 675,
    "Final Energy Intensity of LPG Stoves for Cooking": 385,
    "Final Energy Intensity of Kerosene Stoves for Cooking": 792,
    "Final Energy Intensity of Traditional Biomass Stoves for Cooking": 2000,
}

APPLIANCES_INTENSITY_METRICS = [
    "Final Energy Intensity of Electrical Appliances",
]


def insert_energy_intensities():
    intensity_sh = sum(SPACE_HEATING_INTENSITY_VALUES.values()) / len(SPACE_HEATING_INTENSITY_VALUES)
    intensity_sc = sum(SPACE_COOLING_INTENSITY_VALUES.values()) / len(SPACE_COOLING_INTENSITY_VALUES)
    intensity_wh = sum(WATER_HEATING_INTENSITY_VALUES.values()) / len(WATER_HEATING_INTENSITY_VALUES)
    intensity_cooking = sum(COOKING_INTENSITY_VALUES.values()) / len(COOKING_INTENSITY_VALUES)
    intensity_appliances = 994
    return intensity_sh, intensity_wh, intensity_sc, intensity_cooking, intensity_appliances


def get_cooking_intensity_map():
    return COOKING_INTENSITY_VALUES.copy()


def get_space_heating_intensity_map():
    return SPACE_HEATING_INTENSITY_VALUES.copy()


def get_space_cooling_intensity_map():
    return SPACE_COOLING_INTENSITY_VALUES.copy()


def get_water_heating_intensity_map():
    return WATER_HEATING_INTENSITY_VALUES.copy()

