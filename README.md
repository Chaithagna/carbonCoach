# Carbon Coach: AI Sustainability Agent & Carbon Dashboard

Built with **Google ADK (Python) + Gemini** and a modern **React + FastAPI** interface. Carbon Coach transforms everyday human activities (transit, appliances, diet, waste) into verified $\text{kg CO}_2\text{e}$ emissions, maintains multi-session activity logs in SQLite, evaluates monthly and 6-month carbon limits, recommends realistic greener alternatives, and automatically calculates tree-planting offset plans when thresholds are exceeded.

> **Golden Rule:** The LLM never invents numbers. Every figure in a reply (emissions, totals, percentages, savings, budget metrics, and tree counts) originates strictly from deterministic Python calculation tools.

---

## 1. Project Architecture

```
carbon_coach/
├── __init__.py            # Exports agent and root_agent for ADK entry point
├── agent.py               # Google ADK agent (root_agent, tracker_agent, coach_agent)
├── tools.py               # Calculation & advisory Python tools (single source of truth for math)
├── factors.py             # Emission factors and baseline citations
├── storage.py             # SQLite persistence engine for multi-window history
└── tests/
    ├── test_tools.py      # Unit tests for all calculations, storage, & budgets
    └── test_workflow.py   # End-to-end integration & conversational workflow tests
eval/
└── golden.evalset.json    # ADK golden evaluation suite
dashboard/                 # Custom React frontend (Vite + Vanilla CSS glassmorphism)
server.py                  # FastAPI server exposing REST and conversational API
FACTORS_SOURCES.md         # Authoritative sources, methodology, and conversion formulas
requirements.txt           # google-adk, fastapi, uvicorn, pytest, python-dotenv
.env.example               # Environment variable configuration template
README.md                  # System documentation and demo script
```

---

## 2. Verified Emission Factors & Baseline Estimates

All factors are standardized against authoritative national and international benchmarks. Detailed formulas and citations are in [`FACTORS_SOURCES.md`](FACTORS_SOURCES.md).

> **Disclaimer:** All values are empirical estimates calibrated to Indian per-capita averages (~2 tonnes $\text{CO}_2\text{e}$/person/year). Actual local emissions depend on operational conditions and regional grid mix.

| Category | Item | Factor / Value | Unit | Primary Source & Verification Basis |
|---|---|---|---|---|
| **Electricity** | Indian National Grid | **0.71** | $\text{kg CO}_2\text{e}/\text{kWh}$ | Central Electricity Authority (CEA) India, CO2 Baseline Database for Indian Power Sector. |
| **Transport** | Walk / Cycle | **0.00** | $\text{kg CO}_2\text{e}/\text{pkm}$ | Zero direct tailpipe emissions. |
| | Bus | **0.089** | $\text{kg CO}_2\text{e}/\text{pkm}$ | DEFRA / DESNZ average public bus benchmark & Indian urban transit studies. |
| | Metro | **0.030** | $\text{kg CO}_2\text{e}/\text{pkm}$ | Delhi Metro Rail Corporation (DMRC) / urban mass transit sustainability reports. |
| | Train | **0.040** | $\text{kg CO}_2\text{e}/\text{pkm}$ | Indian Railways national passenger average. |
| | Two-Wheeler | **0.050** | $\text{kg CO}_2\text{e}/\text{pkm}$ | ICCT India / ARAI 100–125cc petrol scooter baseline. |
| | Auto Rickshaw | **0.100** | $\text{kg CO}_2\text{e}/\text{pkm}$ | ARAI / PCRA urban 3-wheeler operational factor. |
| | Car (Petrol) | **0.170** | $\text{kg CO}_2\text{e}/\text{pkm}$ | DEFRA / ARAI small-to-mid petrol passenger car. |
| | Car (Diesel) | **0.170** | $\text{kg CO}_2\text{e}/\text{pkm}$ | DEFRA / ARAI mid-size diesel passenger car. |
| | Car (Electric) | **0.050** | $\text{kg CO}_2\text{e}/\text{pkm}$ | BEV lifecycle average ($0.15\text{ kWh/km} \times 0.71\text{ kg/kWh}$). |
| | Flight (Domestic) | **0.150** | $\text{kg CO}_2\text{e}/\text{pkm}$ | DEFRA domestic short-haul air travel with radiative forcing. |
| **Appliances** | AC | **1.50 kW** | $\text{kW}$ | BEE 3-star 1.5-ton split air conditioner (~1500 W). |
| | Ceiling Fan | **0.07 kW** | $\text{kW}$ | Standard 1200mm induction ceiling fan (~70 W). |
| | LED Light | **0.01 kW** | $\text{kW}$ | Residential 9–10 W LED bulb. |
| | Refrigerator | **0.15 kW** | $\text{kW}$ | Effective duty-cycle average for 250L frost-free refrigerator. |
| | Laptop | **0.05 kW** | $\text{kW}$ | Working office load on modern laptop adapter (~50 W). |
| | Geyser | **2.00 kW** | $\text{kW}$ | Standard residential 15–25L storage water heater. |
| | Washing Machine | **0.50 kW** | $\text{kW}$ | Average cycle power draw (~500 W). |
| **Diet** | Vegan | **0.40** | $\text{kg CO}_2\text{e}/\text{meal}$ | Poore & Nemecek (Science 2018), plant-based meal. |
| | Vegetarian | **0.70** | $\text{kg CO}_2\text{e}/\text{meal}$ | Lacto-vegetarian diet with dairy/paneer. |
| | Egg | **1.00** | $\text{kg CO}_2\text{e}/\text{meal}$ | Egg-inclusive meal. |
| | Fish | **1.40** | $\text{kg CO}_2\text{e}/\text{meal}$ | Marine and farmed fish average. |
| | Chicken | **1.80** | $\text{kg CO}_2\text{e}/\text{meal}$ | Poultry broiler meat portion. |
| | Mutton | **5.50** | $\text{kg CO}_2\text{e}/\text{meal}$ | Goat/sheep small ruminant meat (high enteric methane). |
| | Beef | **6.50** | $\text{kg CO}_2\text{e}/\text{meal}$ | Bovine meat footprint. |
| **Waste** | Mixed Landfill | **0.50** | $\text{kg CO}_2\text{e}/\text{kg}$ | US EPA WARM municipal solid waste to landfill. |
| | Plastic | **2.00** | $\text{kg CO}_2\text{e}/\text{kg}$ | Fossil-fuel polymer lifecycle disposal impact. |
| | Food Waste | **0.80** | $\text{kg CO}_2\text{e}/\text{kg}$ | Organic waste anaerobic decomposition in landfills. |
| | Paper | **1.00** | $\text{kg CO}_2\text{e}/\text{kg}$ | Landfilled paper decomposition factor. |
| | Recycled | **0.10** | $\text{kg CO}_2\text{e}/\text{kg}$ | Net processing & collection footprint. |
| **Offsets** | Mature Tree | **21.0** | $\text{kg CO}_2/\text{tree/yr}$ | European Environment Agency (EEA) / Arbor Day Foundation benchmark (~21.77 kg/year). |

---

## 3. Setup & Installation

### Prerequisites
- **Python 3.10+** (Tested on Python 3.12.10)
- **Node.js 18+** & npm (Tested on Node v24.16.0, npm 11.13.0)

### Step 1: Install Python Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Edit `.env` to configure your API keys (optional for local deterministic rules, required for full Gemini LLM execution):
```env
GOOGLE_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
PORT=8000
HOST=0.0.0.0
```

### Step 3: Install Dashboard Dependencies
```bash
cd dashboard
npm install
npm run build
cd ..
```

---

## 4. Running Carbon Coach

### Option A: Complete Web Application (FastAPI + React Dashboard)
Start the unified server on port 8000 (serves both API and prebuilt React UI):
```bash
python server.py
```
Open your browser at: **`http://localhost:8000`**

To run the React dashboard in live Vite hot-reload mode:
```bash
# Terminal 1: Backend
python server.py

# Terminal 2: Vite Dev Frontend
cd dashboard
npm run dev
```
Open your browser at **`http://localhost:5173`**

### Option B: Google ADK CLI & Developer Web UI
Carbon Coach integrates directly with Google ADK:
```bash
# Interactive terminal session
adk run carbon_coach

# ADK Developer Web Interface
adk web .
```

---

## 5. Verification & Test Suite

The test suite thoroughly validates every calculation formula, SQLite persistence, budget alert thresholds, tree offset math, and multilingual interactions.

Run all 35 tests with pytest:
```bash
python -m pytest -v
```

### Test Results Summary:
```
carbon_coach/tests/test_tools.py ............................ [ 80%] (28 passed)
carbon_coach/tests/test_workflow.py .......                  [100%] (7 passed)
======================== 35 passed in 1.37s ========================
```

Key verified test assertions:
- `calculate_travel_emissions("bus", 12)` = **1.068 kg CO2e**
- `calculate_travel_emissions("walk", 5)` = **0.0 kg CO2e**
- `calculate_appliance_emissions("ac", 4)` = $4 \times 1.5 \times 0.71$ = **4.26 kg CO2e**
- `calculate_tree_offset(42)` = **2 trees** ($\lceil 42 / 21 \rceil$)
- `check_carbon_budget`: Verified status transitions at `< 80%` (`ok`), `80%–100%` (`warning`), and `> 100%` (`exceeded`)
- Multilingual responses in Hindi and Telugu accurately preserve tool calculations

---

## 6. Three-Minute Live Demo Script

Use this script during live demonstrations:

| Step | Action / User Message | What to Observe |
|---|---|---|
| **1. Log Multi-Activity Trip** | Enter: *"I travelled 12 km by car and used the AC for 4 hours."* | Agent logs: car (2.04 kg) + AC (4.26 kg) = **6.3 kg**. Recommends Metro (saves 1.68 kg, 82.4%, Easy) and AC 24-26°C. Progress gauges update smoothly. |
| **2. Missing Parameter Handling** | Enter: *"I took a taxi to the campus today."* | Agent asks: *"How many kilometers was your trip?"* without guessing or inventing figures. |
| **3. Trigger Budget Exceeded & Tree Offset** | Enter: *"I drove 1000 km by petrol car this month."* (or use Quick Log) | Monthly budget crosses 150 kg limit. Red alert banner activates showing **170 kg logged** (crossed by 20+ kg), calculating **1 mature tree** required ($\lceil \text{excess}/21 \rceil$), giving 1/3/5-year timeline, and providing 2 concrete reduction actions. |
| **4. Multilingual Hindi / Telugu** | Enter: *"आज मैंने 10 किमी बस की यात्रा की।"* or *"నేను ఈరోజు 15 కిలోమీటర్లు మెట్రోలో ప్రయాణించాను."* | Agent understands native terms and replies in the user's language with exact figures (0.89 kg and 0.45 kg). |
| **5. Campus Mode Leaderboard** | Click *"Campus Mode"* button | View hostel and department rankings by lowest average kg CO2e per student. |

---

## 7. Known Considerations & Limitations

1. **Tree Offset Biological Horizon:** Tree planting offsets emissions across a 10–20 year biological growth timeline. The system explicitly discloses that offsets complement but never replace cutting emissions at the source.
2. **Standardized Factors:** Regional electricity mixes vary across Indian states (e.g., higher hydro in the north, coal in the east). The system uses the official national grid weighted average of $0.71\text{ kg CO}_2\text{e/kWh}$.
3. **API Keys:** Running with Google ADK against Gemini requires a valid `GOOGLE_API_KEY` in `.env`. When running offline or in unit tests, the internal deterministic parser and calculation tools execute autonomously without external API dependencies.
