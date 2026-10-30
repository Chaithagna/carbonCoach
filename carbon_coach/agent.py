"""Google ADK Agent entry point for Carbon Coach.

Configures root_agent with Gemini 2.5 Flash, registers all calculation,
logging, advisory, budget, and offset tools, and enforces strict reliance
on tool calculation outputs.
"""

import os
from dotenv import load_dotenv
from google.adk import Agent

from carbon_coach.tools import (
    calculate_travel_emissions,
    calculate_electricity_emissions,
    calculate_appliance_emissions,
    calculate_food_emissions,
    calculate_waste_emissions,
    log_activity,
    get_summary,
    suggest_alternative,
    suggest_reductions,
    set_carbon_budget,
    check_carbon_budget,
    calculate_tree_offset,
    get_leaderboard,
)

# Load environment variables from .env
load_dotenv()

# System prompt adhering to Section 5 of CARBON_COACH_SPEC.md
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

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

# Specialized Tracker sub-agent (calculate and log)
tracker_agent = Agent(
    name="carbon_tracker",
    model=MODEL_NAME,
    description="Calculates emissions from daily human activities and logs them into persistent memory.",
    instruction="""
    You are the Carbon Tracker sub-agent.
    Your responsibility is to extract activities and invoke the precise calculation tools:
    - calculate_travel_emissions for transit (walk, cycle, bus, metro, train, car, flight, etc.)
    - calculate_electricity_emissions for kWh consumption
    - calculate_appliance_emissions for appliances (ac, fan, light, geyser, refrigerator, laptop, washing_machine)
    - calculate_food_emissions for dietary meals
    - calculate_waste_emissions for waste disposal
    Once calculated, immediately call log_activity with the exact kg_co2e result.
    Never invent numbers.
    """,
    tools=[
        calculate_travel_emissions,
        calculate_electricity_emissions,
        calculate_appliance_emissions,
        calculate_food_emissions,
        calculate_waste_emissions,
        log_activity,
    ],
)

# Specialized Coach sub-agent (alternatives, budgets, offsets)
coach_agent = Agent(
    name="carbon_advisor",
    model=MODEL_NAME,
    description="Provides greener alternatives, monitors carbon budgets, and computes tree planting offsets.",
    instruction="""
    You are the Carbon Advisor sub-agent.
    Your responsibility is to:
    1. Call suggest_alternative for activities and present realistic, easier alternatives with exact savings and ease.
    2. Check the user's budget status with check_carbon_budget.
    3. If budget status is 'exceeded', call calculate_tree_offset and provide the tree planting plan along with 2 concrete reduction actions.
    4. Call suggest_reductions when the user asks for tips to cut their footprint.
    5. Call get_leaderboard when the user asks for campus or hostel comparisons.
    Never invent numbers. Every figure must originate from a tool output.
    """,
    tools=[
        suggest_alternative,
        suggest_reductions,
        check_carbon_budget,
        calculate_tree_offset,
        set_carbon_budget,
        get_leaderboard,
    ],
)

# Root Agent entry point for Google ADK (adk run carbon_coach / adk web)
root_agent = Agent(
    name="carbon_coach",
    model=MODEL_NAME,
    description="Carbon Coach: AI Agent converting daily activities into kg CO2e, tracking budgets, and coaching sustainability.",
    instruction=INSTRUCTION,
    tools=[
        calculate_travel_emissions,
        calculate_electricity_emissions,
        calculate_appliance_emissions,
        calculate_food_emissions,
        calculate_waste_emissions,
        log_activity,
        get_summary,
        suggest_alternative,
        suggest_reductions,
        set_carbon_budget,
        check_carbon_budget,
        calculate_tree_offset,
        get_leaderboard,
    ],
    sub_agents=[tracker_agent, coach_agent],
)
