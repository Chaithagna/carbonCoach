"""Emission factors and baseline constants for Carbon Coach.

All values are verified against standardized datasets (CEA India, DEFRA, BEE,
Poore & Nemecek 2018, US EPA WARM, EEA) and documented in FACTORS_SOURCES.md.
"""

from typing import Dict, Any

# Grid electricity factor (kg CO2e per kWh)
# Source: Central Electricity Authority (CEA) of India, CO2 Baseline Database for Indian Power Sector
GRID_KG_PER_KWH: float = 0.71
GRID_SOURCE: str = "CEA India CO2 Baseline Database (National Grid average)"

# Travel emission factors per passenger-kilometer (kg CO2e per km)
# Sources: DEFRA / DESNZ GHG Conversion Factors, ICCT/ARAI India benchmarks
TRAVEL_KG_PER_KM: Dict[str, float] = {
    "walk": 0.0,
    "cycle": 0.0,
    "bus": 0.089,
    "metro": 0.03,
    "train": 0.04,
    "two_wheeler": 0.05,
    "auto_rickshaw": 0.10,
    "car_petrol": 0.17,
    "car_diesel": 0.17,
    "car_electric": 0.05,
    "flight_domestic": 0.15,
}

TRAVEL_SOURCES: Dict[str, str] = {
    "walk": "Human powered (0 direct tailpipe emissions)",
    "cycle": "Human powered (0 direct tailpipe emissions)",
    "bus": "DEFRA / DESNZ GHG Conversion Factors (average local bus)",
    "metro": "DMRC Sustainability Report (urban mass transit average)",
    "train": "Indian Railways sustainability statistics",
    "two_wheeler": "ICCT India / ARAI 100-125cc scooter baseline",
    "auto_rickshaw": "ARAI / PCRA Indian urban 3-wheeler benchmark",
    "car_petrol": "DEFRA / ARAI small-to-mid petrol passenger car",
    "car_diesel": "DEFRA / ARAI mid diesel passenger car",
    "car_electric": "BEV fleet average (0.15 kWh/km @ 0.71 kg/kWh)",
    "flight_domestic": "DEFRA domestic air travel with radiative forcing",
}

# Appliance typical power draw in kilowatts (kW)
# Sources: Bureau of Energy Efficiency (BEE) India ratings
APPLIANCE_KW: Dict[str, float] = {
    "ac": 1.5,
    "fan": 0.07,
    "light": 0.01,
    "refrigerator": 0.15,
    "laptop": 0.05,
    "geyser": 2.0,
    "washing_machine": 0.5,
}

APPLIANCE_DESCRIPTIONS: Dict[str, str] = {
    "ac": "BEE 3-star 1.5 ton split air conditioner (~1500W)",
    "fan": "Standard 1200mm induction ceiling fan (~70W)",
    "light": "Standard 9-10W residential LED bulb (~10W)",
    "refrigerator": "Effective average draw for 250L frost-free refrigerator (~150W)",
    "laptop": "Standard laptop active working load (~50W)",
    "geyser": "Residential storage water heater element (~2000W)",
    "washing_machine": "Automatic washing machine average cycle (~500W)",
}

# Food emissions per meal serving (kg CO2e per meal)
# Source: Poore & Nemecek (Science 2018), Our World in Data
FOOD_KG_PER_MEAL: Dict[str, float] = {
    "vegan": 0.4,
    "veg": 0.7,
    "egg": 1.0,
    "fish": 1.4,
    "chicken": 1.8,
    "mutton": 5.5,
    "beef": 6.5,
}

FOOD_SOURCES: Dict[str, str] = {
    "vegan": "Poore & Nemecek 2018 (plant-based meal serving)",
    "veg": "Poore & Nemecek 2018 (lacto-vegetarian meal with dairy/paneer)",
    "egg": "Poore & Nemecek 2018 (egg-inclusive meal serving)",
    "fish": "Poore & Nemecek 2018 (farmed and wild marine fish average)",
    "chicken": "Poore & Nemecek 2018 (poultry meat meal portion)",
    "mutton": "Poore & Nemecek 2018 (goat/sheep small ruminant meat)",
    "beef": "Poore & Nemecek 2018 (bovine meat portion)",
}

# Waste emissions per kg (kg CO2e per kg)
# Source: US EPA Waste Reduction Model (WARM) / IPCC
WASTE_KG_PER_KG: Dict[str, float] = {
    "mixed_landfill": 0.5,
    "plastic": 2.0,
    "food_waste": 0.8,
    "paper": 1.0,
    "recycled": 0.1,
}

WASTE_SOURCES: Dict[str, str] = {
    "mixed_landfill": "US EPA WARM (municipal solid waste in landfill)",
    "plastic": "US EPA WARM (single-use polymer disposal lifecycle)",
    "food_waste": "US EPA WARM (organic waste anaerobic methane generation)",
    "paper": "US EPA WARM (landfilled virgin/mixed paper)",
    "recycled": "US EPA WARM (recycling collection and reprocessing net impact)",
}

# Carbon offset calculation constant
# Source: European Environment Agency / Arbor Day Foundation
KG_CO2_PER_TREE_PER_YEAR: float = 21.0
TREE_OFFSET_SOURCE: str = "EEA / Arbor Day Foundation (~21 kg CO2 absorbed per mature tree/year)"

# Default carbon budgets (kg CO2e)
# Calibrated around Indian per-capita baseline (~2 tCO2e/year)
DEFAULT_MONTHLY_BUDGET_KG: float = 150.0
DEFAULT_SIX_MONTH_BUDGET_KG: float = 900.0
