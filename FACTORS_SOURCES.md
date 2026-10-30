# Carbon Coach: Emission Factors & Data Sources

This document details all emission factors, unit conversions, and authoritative sources used across the **Carbon Coach** system.

> **Important Note:** All emission factors in this database are empirical estimates based on standardized national and international baselines. Actual emissions can vary based on local grid mix, vehicle loading, driving conditions, and manufacturing lifecycle boundaries.

---

## 1. Electricity Grid Baseline

| Parameter | Value | Unit | Source & Verification Notes |
|---|---|---|---|
| `GRID_KG_PER_KWH` | **0.71** | $\text{kg CO}_2\text{e}/\text{kWh}$ | **Central Electricity Authority (CEA)**, Ministry of Power, Government of India: *CO2 Baseline Database for the Indian Power Sector* (weighted average grid emission factor for the National Grid, standardized baseline ~0.71 kg/kWh). |

---

## 2. Transport & Travel Factors

Calculated on a **per passenger-kilometer (pkm)** basis.

| Mode | Factor ($\text{kg CO}_2\text{e}/\text{pkm}$) | Primary Source & Verification Basis |
|---|---|---|
| `walk` | **0.000** | Human powered; 0 direct tailpipe emissions. |
| `cycle` | **0.000** | Human powered; 0 direct tailpipe emissions. |
| `bus` | **0.089** | UK Department for Environment, Food & Rural Affairs (**DEFRA**) / DESNZ Greenhouse Gas Conversion Factors for Local Public Bus (~0.08–0.10 kg/pkm). Corroborated with Indian urban transit lifecycle studies. |
| `metro` | **0.030** | Delhi Metro Rail Corporation (**DMRC**) Sustainability Reports & urban mass rapid transit lifecycle figures (~0.025–0.035 kg/pkm). |
| `train` | **0.040** | **Indian Railways** sustainability statistics / National rail passenger averages (~0.035–0.045 kg/pkm). |
| `two_wheeler` | **0.050** | International Council on Clean Transportation (**ICCT**) India & ARAI baseline for typical 100–125cc petrol two-wheelers with single occupant (~0.045–0.055 kg/km). |
| `auto_rickshaw` | **0.100** | ARAI / Petroleum Conservation Research Association (**PCRA**) Indian urban 3-wheeler average (CNG/petrol mixed fleet, ~0.09–0.11 kg/pkm). |
| `car_petrol` | **0.170** | **DEFRA** / ARAI passenger car benchmarks for small/mid petrol car (~160–180 g CO2/km per passenger). |
| `car_diesel` | **0.170** | **DEFRA** / ARAI passenger car benchmarks for mid diesel car (~165–175 g CO2/km per passenger). |
| `car_electric` | **0.050** | Battery Electric Vehicle (BEV) operational emission: Average efficiency of ~0.15 kWh/km $\times$ 0.71 kg CO2e/kWh $\approx$ 0.053 kg/km (occupancy 1). |
| `flight_domestic` | **0.150** | **DEFRA** domestic short-haul flights including indirect effects and radiative forcing multiplier (~0.15–0.24 kg/pkm). |

---

## 3. Household Appliances (Typical Power Draw)

Emissions are computed as:  
$$\text{Emissions (kg CO}_2\text{e)} = \text{hours} \times \text{Power (kW)} \times \text{GRID\_KG\_PER\_KWH (0.71)}$$

| Appliance | Power (`APPLIANCE_KW`) | Description / Source Baseline |
|---|---|---|
| `ac` | **1.50 kW** | Bureau of Energy Efficiency (**BEE**) standard 1.5-ton 3-star split air conditioner (~1450–1600 W compressor load). |
| `fan` | **0.07 kW** | BEE baseline 1200mm induction ceiling fan (~65–75 W). |
| `light` | **0.01 kW** | Standard residential 9–10 W LED bulb. |
| `refrigerator` | **0.15 kW** | Effective continuous duty cycle power draw for a standard 250-liter frost-free refrigerator (~120–180 W). |
| `laptop` | **0.05 kW** | Active office/productivity load on a modern laptop power adapter (~45–65 W). |
| `geyser` | **2.00 kW** | Standard 15–25 liter storage electric water heater (2000 W heating element). |
| `washing_machine` | **0.50 kW** | Average cycle power draw for residential automatic front/top-load washer (~400–600 W). |

---

## 4. Food & Diet Emissions

Calculated on a **per meal serving** basis (~300–400g portion).

| Meal Type | Factor ($\text{kg CO}_2\text{e}/\text{meal}$) | Primary Source & Methodology |
|---|---|---|
| `vegan` | **0.40** | **Poore & Nemecek (2018)**, *Science*, and Our World in Data. Strict plant-based legumes, grains, vegetables, nuts. |
| `veg` | **0.70** | Lacto-vegetarian Indian diet, including dairy proteins (paneer, curd, milk, ghee). |
| `egg` | **1.00** | Egg-inclusive meal (poultry feed and egg production lifecycle). |
| `fish` | **1.40** | Average farmed aquaculture and marine wild capture fish portion. |
| `chicken` | **1.80** | Poultry broiler meat portion (feed conversion ratio and processing). |
| `mutton` | **5.50** | Sheep and goat meat. High enteric fermentation and feed impact typical of small ruminants. |
| `beef` | **6.50** | Bovine meat. Significant enteric methane generation and extensive pasture footprint. |

---

## 5. Waste Disposal

Calculated **per kg of waste generated**.

| Waste Type | Factor ($\text{kg CO}_2\text{e}/\text{kg}$) | Primary Source & Methodology |
|---|---|---|
| `mixed_landfill` | **0.50** | US EPA Waste Reduction Model (**WARM**) / IPCC guidelines for mixed municipal solid waste disposal in unsanitary/mixed landfills. |
| `plastic` | **2.00** | US EPA WARM and Ellen MacArthur Foundation lifecycle data for fossil-based single-use plastics (incineration and open burning burden). |
| `food_waste` | **0.80** | Anaerobic decomposition of organic waste in municipal landfills generating methane ($CH_4$). |
| `paper` | **1.00** | Landfilled virgin paper decomposition and lifecycle footprint. |
| `recycled` | **0.10** | Net carbon footprint of collection, sorting, and reprocessing recyclable materials. |

---

## 6. Carbon Offsets (Tree Planting)

| Metric | Value | Reference & Biological Baseline |
|---|---|---|
| `KG_CO2_PER_TREE_PER_YEAR` | **21 kg CO2 / year** | **European Environment Agency (EEA)** and **Arbor Day Foundation** estimates (~21.77 kg or 48 lbs $\text{CO}_2$ absorbed per mature deciduous tree annually). |

> **Ethical Note:** Trees require 10–20 years of growth to achieve full sequestration capacity, and sapling survival rates vary. Planting trees offsets carbon over a long multi-year horizon, but cannot replace immediate emission reductions at the source.
