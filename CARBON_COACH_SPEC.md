# Carbon Coach: Build Spec (for Antigravity)

Build an AI agent with **Google ADK (Python) + Gemini** that people talk to in plain language. It converts daily activities into kg CO2e using tools, remembers them, suggests greener and easier alternatives, and warns when the person crosses a carbon budget, with a tree-planting plan to repair the damage.

**Golden rule: the LLM never invents a number. Every figure in a reply must come from a tool result.**

---

## 1. Project structure

```
carbon_coach/
  __init__.py            # from . import agent
  agent.py               # root_agent (ADK entry point)
  tools.py               # all Python tools
  factors.py             # emission factors + sources (single source of truth)
  storage.py             # persistence (SQLite) so 6-month history survives restarts
  tests/test_tools.py    # pytest unit tests
  eval/golden.evalset.json  # ADK golden eval cases
requirements.txt         # google-adk
.env                     # GOOGLE_API_KEY=...  (never commit)
README.md
```

Run locally with `adk web` (dev UI) and `adk run carbon_coach`. Model: `gemini-2.5-flash` (or the latest Flash available).

---

## 2. Features

### 2.1 Conversational input
User says things like *"I travelled 12 km by bus today and used the AC for 4 hours."* The agent extracts the activities (category, mode, quantity) and calls the right tools. If a quantity is missing (e.g. no distance), ask one short question. Never assume numbers.

### 2.2 Tool-based calculation
All math happens in Python in `tools.py`, using factors from `factors.py`. Each tool returns a dict like `{"status": "success", "kg_co2e": 1.07, "factor": 0.089, "unit": "kg/km", "source": "..."}`.

### 2.3 Memory
- Every logged activity is saved with a timestamp, category, details and kg CO2e.
- Use ADK session state (`tool_context.state`, with the `user:` prefix for cross-session data) **and** persist to SQLite in `storage.py`, because the six-month budget needs history that outlives one session.
- Supports: "How did I do today / this week / this month / last 6 months?"

### 2.4 Greener, easier, compatible alternatives (NEW, key feature)
Whenever the user logs an activity, the agent also calls `suggest_alternative` and tells them what they could do **instead**, but only options that are realistic.

Compatibility rules (put in code, not in the prompt):
| Situation | Realistic alternatives |
|---|---|
| Distance <= 2 km by car/bike/auto | walk or cycle |
| 2 to 8 km by car/two-wheeler | bus, metro, carpool, e-scooter |
| 8 to 30 km by car | metro/train, bus, carpool (2+ people) |
| > 30 km | train or bus instead of car; avoid flight if train exists |
| AC use | set 24-26 C, use fan + AC, shorter hours, 5-star appliance |
| Non-veg meal | vegetarian or egg/chicken instead of mutton/beef |
| Waste | segregate, compost wet waste, reduce single-use plastic |

The response must show: current option kg, alternative kg, **saving in kg and %**, and a one-line "how easy it is" note (Easy / Medium / Needs planning). Rank by saving first, then by ease. Only suggest when the saving is positive; if the user already chose the lowest-carbon option, praise them.

### 2.5 Carbon budget alerts and tree-planting plan (NEW, key feature)
Budgets (configurable constants, defaults below; allow the user to change them via `set_carbon_budget`):
- **Monthly budget:** 150 kg CO2e
- **Six-month budget:** 900 kg CO2e

Defaults are roughly India's per-capita level (about 2 tCO2e per year) and are illustrative. Say so in the README.

After **every** `log_activity` call, run `check_carbon_budget` and act on the result:

| Usage vs budget | Status | What the agent says |
|---|---|---|
| < 80% | `ok` | Brief encouragement and remaining budget |
| 80% to 100% | `warning` | "You have used X% of your monthly budget. Y kg left." plus the top 2 easy alternatives |
| > 100% | `exceeded` | Clearly tell the user **"You have reached/crossed your monthly (or 6-month) carbon limit by X kg"** and give the tree plan below |

**Tree-planting plan** (`calculate_tree_offset(excess_kg)`):
- Assumption: one mature tree absorbs about **21 kg CO2 per year** (state this source in code; make it a constant `KG_CO2_PER_TREE_PER_YEAR`).
- `trees_needed = ceil(excess_kg / 21)` (this is the number of trees needed to absorb the excess **in one year**).
- Return trees for 1 year, and also a "plant now, offset over N years" option for small groups.
- The agent should be honest: trees take years to grow, and planting offsets but does not replace cutting emissions. Always pair the tree advice with 2 reduction actions.
- Suggest practical ways: campus plantation drive, local nursery, NGO or forest department programmes. Do not invent specific organisations or links.

Check both windows independently: the current calendar month and the rolling last 6 months. If both are exceeded, report both.

### 2.6 Actionable tips
`suggest_reductions()` looks at the user's logged history, finds the highest-emitting category, and returns personalised suggestions with estimated savings computed by tools.

---

## 3. Tools to implement (`tools.py`)

All are plain Python functions with type hints and **clear docstrings** (ADK uses them as tool descriptions). Return a dict with `status`.

| Tool | Purpose |
|---|---|
| `calculate_travel_emissions(mode: str, km: float)` | km x factor. Modes: walk, cycle, bus, metro, train, two_wheeler, auto_rickshaw, car_petrol, car_diesel, car_electric, flight_domestic |
| `calculate_electricity_emissions(kwh: float)` | kWh x grid factor |
| `calculate_appliance_emissions(appliance: str, hours: float)` | hours x typical kW x grid factor. Appliances: ac, fan, light, refrigerator, laptop, geyser, washing_machine |
| `calculate_food_emissions(meal_type: str, servings: int = 1)` | veg, egg, chicken, fish, mutton, beef, vegan |
| `calculate_waste_emissions(waste_type: str, kg: float)` | mixed_landfill, plastic, food_waste, paper, recycled |
| `log_activity(category: str, details: str, kg_co2e: float, tool_context)` | Save to state + SQLite. It must take kg_co2e from a calculator's output, never from the user |
| `get_summary(period: str, tool_context)` | period: today, week, month, six_months. Totals, per-category breakdown, trend vs previous period |
| `suggest_alternative(category: str, mode: str, quantity: float)` | Section 2.4 |
| `suggest_reductions(tool_context)` | Section 2.6 |
| `set_carbon_budget(monthly_kg: float, six_month_kg: float, tool_context)` | Update thresholds |
| `check_carbon_budget(tool_context)` | Section 2.5: returns usage, percent, status for both windows |
| `calculate_tree_offset(excess_kg: float)` | Section 2.5 |

---

## 4. Emission factors (`factors.py`)

Put all values in one dict with a `source` string next to each. These are **approximate starting values**; before the demo, verify them against the cited sources and update. Label them as estimates in the README.

```python
GRID_KG_PER_KWH = 0.71        # India grid average, CEA CO2 baseline database (approx; verify latest)

TRAVEL_KG_PER_KM = {          # per passenger-km; sources: DEFRA/UK GHG conversion factors, ICCT/IEA India figures (approx)
    "walk": 0.0, "cycle": 0.0,
    "bus": 0.089, "metro": 0.03, "train": 0.04,
    "two_wheeler": 0.05, "auto_rickshaw": 0.10,
    "car_petrol": 0.17, "car_diesel": 0.17, "car_electric": 0.05,
    "flight_domestic": 0.15,
}

APPLIANCE_KW = {              # typical power draw
    "ac": 1.5, "fan": 0.07, "light": 0.01, "refrigerator": 0.15,
    "laptop": 0.05, "geyser": 2.0, "washing_machine": 0.5,
}

FOOD_KG_PER_MEAL = {          # approx, from Poore & Nemecek 2018 / Our World in Data scaled to a meal
    "vegan": 0.4, "veg": 0.7, "egg": 1.0, "fish": 1.4,
    "chicken": 1.8, "mutton": 5.5, "beef": 6.5,
}

WASTE_KG_PER_KG = {           # approx, EPA WARM-style factors
    "mixed_landfill": 0.5, "plastic": 2.0, "food_waste": 0.8,
    "paper": 1.0, "recycled": 0.1,
}

KG_CO2_PER_TREE_PER_YEAR = 21  # commonly cited figure for a mature tree (e.g. EEA/Arbor Day estimates)

DEFAULT_MONTHLY_BUDGET_KG = 150
DEFAULT_SIX_MONTH_BUDGET_KG = 900
```

Add a `FACTORS_SOURCES.md` or README table listing where each number came from.

---

## 5. Agent instruction (put in `agent.py`)

```python
INSTRUCTION = """
You are Carbon Coach, a friendly, practical assistant that helps students,
families and campuses measure and reduce their carbon footprint.

RULES
1. NEVER state or estimate an emission number yourself. Every kg CO2e, saving,
   percentage, total, tree count and budget figure MUST come from a tool result.
2. For each activity the user mentions: call the matching calculate_* tool,
   then log_activity with that tool's kg_co2e, then suggest_alternative,
   then check_carbon_budget.
3. If a quantity is missing (distance, hours, servings), ask ONE short
   question. Do not guess.
4. Alternatives must be realistic (distance, effort, cost). Say how easy they
   are. If the user's choice is already the greenest, praise them.
5. If check_carbon_budget returns 'exceeded' for the month or six months, say
   clearly that they have crossed their limit and by how much, call
   calculate_tree_offset, and give the tree-planting plan PLUS two concrete
   ways to reduce emissions. Be honest that trees take years to absorb carbon
   and do not replace cutting emissions. Never shame the user.
6. If status is 'warning' (80%+), give a gentle heads-up and the top two easy
   changes.
7. For 'how did I do' questions, call get_summary.
8. Reply in the user's language (English, Telugu or Hindi). Keep replies short,
   warm and encouraging. Use simple language.
"""
```

---

## 6. Example conversation (expected behaviour)

**User:** I travelled 12 km by car and used the AC for 4 hours.
**Agent (after tools):** Logged: car 12 km = X kg, AC 4 h = Y kg, total Z kg. If you take the metro for that trip you would save A kg (B%), and it is Easy. Setting the AC to 24-26 C saves about C kg. Monthly budget: D% used, E kg left.

**Later, when the month total passes 150 kg:** "You have crossed your monthly carbon limit by F kg. To balance that, about N trees (about 21 kg CO2 per tree per year) would be needed. A campus plantation drive is a good way to do it. Meanwhile, here are two changes that help most: ..."

(X, Y, Z... always come from tools.)

---

## 7. Tests and golden evals

**Unit tests** (`tests/test_tools.py`), e.g.:
- `calculate_travel_emissions("bus", 12)` equals 12 x 0.089 = 1.068
- `calculate_travel_emissions("walk", 5)` equals 0
- `calculate_appliance_emissions("ac", 4)` equals 4 x 1.5 x 0.71 = 4.26
- `calculate_tree_offset(42)["trees_needed"]` equals 2
- `check_carbon_budget` returns `warning` at 85% and `exceeded` at 101%
- Invalid mode or negative km returns `{"status": "error", ...}`

**Golden eval cases** (`eval/golden.evalset.json`, ADK eval format) for: bus + AC input, missing distance (agent asks), budget exceeded (tree plan appears), Hindi/Telugu input, "how did I do this week". Check expected tool calls and that numbers match tool output. Run with `adk eval`.

---

## 8. Bonus (build after the core works)
1. **Multi-agent:** Tracker agent (calculate and log) + Coach agent (alternatives, budgets, trees), coordinated by a root agent using `sub_agents`.
2. **Campus mode:** `get_leaderboard(group_type)` comparing hostels or departments by average kg CO2e per person.
3. **Telugu / Hindi:** instruction already requires replying in the user's language; add golden cases.
4. **Deploy to Cloud Run** with `adk deploy cloud_run` and share the live URL.

---

## 9. Definition of done
- [ ] `adk web` runs; typing the example sentence returns correct tool-based numbers
- [ ] No number in any reply that is not in a tool output
- [ ] Alternatives shown with saving in kg and %, and ease level
- [ ] Budget `warning` and `exceeded` flows work for month and six months, with tree plan
- [ ] History persists across restarts (SQLite)
- [ ] Unit tests pass; golden evals pass
- [ ] README lists factor sources and states they are estimates
- [ ] 3-minute demo script ready (log activity, show alternative, trigger budget alert, show tree plan)

---

## 10. How Antigravity should work
1. Read this whole file first. Produce a short plan and file list, then build.
2. Build `factors.py`, `tools.py` and `storage.py` first, and write tests before wiring the agent.
3. Then write `agent.py` and verify in `adk web` with the example conversation.
4. Do not hardcode any API key. Load from `.env`.
5. If any ADK API differs from what is written here, follow the current official ADK docs and keep the behaviour described above.
