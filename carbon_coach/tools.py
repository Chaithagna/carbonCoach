"""Calculation and advisory tools for Carbon Coach.

Every tool returns a structured dictionary with 'status' and exact numerical outputs.
No tool relies on LLM approximations or assumptions.
"""

import math
from typing import Dict, Any, List, Optional
from datetime import datetime

from carbon_coach.factors import (
    GRID_KG_PER_KWH,
    GRID_SOURCE,
    TRAVEL_KG_PER_KM,
    TRAVEL_SOURCES,
    APPLIANCE_KW,
    APPLIANCE_DESCRIPTIONS,
    FOOD_KG_PER_MEAL,
    FOOD_SOURCES,
    WASTE_KG_PER_KG,
    WASTE_SOURCES,
    KG_CO2_PER_TREE_PER_YEAR,
    TREE_OFFSET_SOURCE,
    DEFAULT_MONTHLY_BUDGET_KG,
    DEFAULT_SIX_MONTH_BUDGET_KG,
)
from carbon_coach.storage import (
    save_activity as storage_save_activity,
    get_summary_data,
    set_user_budget as storage_set_budget,
    get_user_budget as storage_get_budget,
    get_budget_status as storage_get_budget_status,
    get_highest_emitting_category,
    get_leaderboard_data,
)


def calculate_travel_emissions(mode: str, km: float) -> Dict[str, Any]:
    """Calculates transport emissions based on passenger-kilometers and travel mode.

    Args:
        mode: Transport mode (walk, cycle, bus, metro, train, two_wheeler,
              auto_rickshaw, car_petrol, car_diesel, car_electric, flight_domestic).
        km: Distance travelled in kilometers (must be >= 0).

    Returns:
        Dict with status, kg_co2e, factor, unit, mode, km, and source citation.
    """
    mode_clean = str(mode).strip().lower().replace(" ", "_").replace("-", "_")
    if km is None:
        return {"status": "error", "message": "Distance in kilometers (km) is required."}

    try:
        km_val = float(km)
    except (ValueError, TypeError):
        return {"status": "error", "message": f"Invalid distance value: {km}"}

    if km_val < 0:
        return {"status": "error", "message": "Distance in kilometers cannot be negative."}

    if mode_clean not in TRAVEL_KG_PER_KM:
        valid_modes = ", ".join(sorted(TRAVEL_KG_PER_KM.keys()))
        return {
            "status": "error",
            "message": f"Unsupported travel mode '{mode}'. Supported modes: {valid_modes}",
        }

    factor = TRAVEL_KG_PER_KM[mode_clean]
    source = TRAVEL_SOURCES.get(mode_clean, "Standardized transit conversion factors")
    kg_co2e = round(km_val * factor, 4)

    return {
        "status": "success",
        "category": "travel",
        "mode": mode_clean,
        "km": km_val,
        "factor": factor,
        "unit": "kg CO2e/pkm",
        "kg_co2e": kg_co2e,
        "source": source,
    }


def calculate_electricity_emissions(kwh: float) -> Dict[str, Any]:
    """Calculates carbon emissions from electricity consumption using the grid factor.

    Args:
        kwh: Total electricity consumed in kilowatt-hours (kWh, must be >= 0).

    Returns:
        Dict with status, kg_co2e, factor, unit, kwh, and source citation.
    """
    if kwh is None:
        return {"status": "error", "message": "Electricity in kWh is required."}

    try:
        kwh_val = float(kwh)
    except (ValueError, TypeError):
        return {"status": "error", "message": f"Invalid kWh value: {kwh}"}

    if kwh_val < 0:
        return {"status": "error", "message": "Electricity consumption in kWh cannot be negative."}

    kg_co2e = round(kwh_val * GRID_KG_PER_KWH, 4)

    return {
        "status": "success",
        "category": "electricity",
        "kwh": kwh_val,
        "factor": GRID_KG_PER_KWH,
        "unit": "kg CO2e/kWh",
        "kg_co2e": kg_co2e,
        "source": GRID_SOURCE,
    }


def calculate_appliance_emissions(appliance: str, hours: float) -> Dict[str, Any]:
    """Calculates emissions from running a household appliance for a duration.

    Args:
        appliance: Appliance type (ac, fan, light, refrigerator, laptop, geyser, washing_machine).
        hours: Usage duration in hours (must be >= 0).

    Returns:
        Dict with status, kg_co2e, power_kw, grid_factor, hours, and appliance details.
    """
    app_clean = str(appliance).strip().lower().replace(" ", "_").replace("-", "_")
    if hours is None:
        return {"status": "error", "message": "Usage duration in hours is required."}

    try:
        hours_val = float(hours)
    except (ValueError, TypeError):
        return {"status": "error", "message": f"Invalid hours value: {hours}"}

    if hours_val < 0:
        return {"status": "error", "message": "Appliance usage hours cannot be negative."}

    if app_clean not in APPLIANCE_KW:
        valid_apps = ", ".join(sorted(APPLIANCE_KW.keys()))
        return {
            "status": "error",
            "message": f"Unsupported appliance '{appliance}'. Supported appliances: {valid_apps}",
        }

    power_kw = APPLIANCE_KW[app_clean]
    desc = APPLIANCE_DESCRIPTIONS.get(app_clean, f"{app_clean} power draw")
    # Formula: hours * power_kw * GRID_KG_PER_KWH
    # Note: 4 * 1.5 * 0.71 = 4.26
    kg_co2e = round(hours_val * power_kw * GRID_KG_PER_KWH, 4)

    return {
        "status": "success",
        "category": "appliance",
        "appliance": app_clean,
        "hours": hours_val,
        "power_kw": power_kw,
        "grid_factor": GRID_KG_PER_KWH,
        "unit": "kg CO2e",
        "kg_co2e": kg_co2e,
        "description": desc,
        "source": f"{desc} with {GRID_SOURCE}",
    }


def calculate_food_emissions(meal_type: str, servings: int = 1) -> Dict[str, Any]:
    """Calculates dietary carbon footprint for a specified meal type and servings.

    Args:
        meal_type: Diet/meal type (vegan, veg, egg, fish, chicken, mutton, beef).
        servings: Number of meal servings (integer >= 1).

    Returns:
        Dict with status, kg_co2e, factor, servings, and source citation.
    """
    meal_clean = str(meal_type).strip().lower().replace(" ", "_").replace("-", "_")
    try:
        servings_val = int(servings)
    except (ValueError, TypeError):
        return {"status": "error", "message": f"Invalid servings value: {servings}"}

    if servings_val <= 0:
        return {"status": "error", "message": "Servings must be a positive integer >= 1."}

    if meal_clean not in FOOD_KG_PER_MEAL:
        valid_meals = ", ".join(sorted(FOOD_KG_PER_MEAL.keys()))
        return {
            "status": "error",
            "message": f"Unsupported meal type '{meal_type}'. Supported meal types: {valid_meals}",
        }

    factor = FOOD_KG_PER_MEAL[meal_clean]
    source = FOOD_SOURCES.get(meal_clean, "Poore & Nemecek 2018 food emissions database")
    kg_co2e = round(servings_val * factor, 4)

    return {
        "status": "success",
        "category": "food",
        "meal_type": meal_clean,
        "servings": servings_val,
        "factor": factor,
        "unit": "kg CO2e/meal",
        "kg_co2e": kg_co2e,
        "source": source,
    }


def calculate_waste_emissions(waste_type: str, kg: float) -> Dict[str, Any]:
    """Calculates lifecycle emissions from discarded waste materials.

    Args:
        waste_type: Material category (mixed_landfill, plastic, food_waste, paper, recycled).
        kg: Waste quantity in kilograms (must be >= 0).

    Returns:
        Dict with status, kg_co2e, factor, unit, kg, and source citation.
    """
    waste_clean = str(waste_type).strip().lower().replace(" ", "_").replace("-", "_")
    if kg is None:
        return {"status": "error", "message": "Waste weight in kg is required."}

    try:
        kg_val = float(kg)
    except (ValueError, TypeError):
        return {"status": "error", "message": f"Invalid waste weight value: {kg}"}

    if kg_val < 0:
        return {"status": "error", "message": "Waste weight in kg cannot be negative."}

    if waste_clean not in WASTE_KG_PER_KG:
        valid_waste = ", ".join(sorted(WASTE_KG_PER_KG.keys()))
        return {
            "status": "error",
            "message": f"Unsupported waste type '{waste_type}'. Supported types: {valid_waste}",
        }

    factor = WASTE_KG_PER_KG[waste_clean]
    source = WASTE_SOURCES.get(waste_clean, "US EPA WARM waste factors")
    kg_co2e = round(kg_val * factor, 4)

    return {
        "status": "success",
        "category": "waste",
        "waste_type": waste_clean,
        "kg": kg_val,
        "factor": factor,
        "unit": "kg CO2e/kg",
        "kg_co2e": kg_co2e,
        "source": source,
    }


def _extract_user_id(tool_context: Optional[Any]) -> str:
    """Helper to extract user_id from tool_context or default to 'default_user'."""
    if tool_context is not None:
        if hasattr(tool_context, "user_id") and tool_context.user_id:
            return str(tool_context.user_id)
        if hasattr(tool_context, "session") and hasattr(tool_context.session, "user_id") and tool_context.session.user_id:
            return str(tool_context.session.user_id)
    return "default_user"


def log_activity(
    category: str,
    details: str,
    kg_co2e: float,
    tool_context: Optional[Any] = None,
) -> Dict[str, Any]:
    """Persists a verified carbon activity into SQLite and ADK session state.

    The kg_co2e figure MUST be provided directly from a calculate_* tool result.

    Args:
        category: Activity category (travel, electricity, appliance, food, waste).
        details: Human-readable activity description (e.g., 'car_petrol 12 km', 'ac 4 hours').
        kg_co2e: Calculated emission in kg CO2e from a previous tool calculation.
        tool_context: ADK context injected by the agent runtime.

    Returns:
        Dict with status, activity_id, details, kg_co2e, timestamp, and updated session count.
    """
    if kg_co2e is None:
        return {"status": "error", "message": "kg_co2e must be provided from a calculation tool."}

    try:
        kg_val = float(kg_co2e)
    except (ValueError, TypeError):
        return {"status": "error", "message": f"Invalid kg_co2e value: {kg_co2e}"}

    if kg_val < 0:
        return {"status": "error", "message": "kg_co2e cannot be negative."}

    user_id = _extract_user_id(tool_context)
    cat_clean = str(category).strip().lower()
    det_clean = str(details).strip()

    record = storage_save_activity(
        category=cat_clean,
        details=det_clean,
        kg_co2e=kg_val,
        user_id=user_id,
        timestamp=datetime.now(),
    )

    # If ADK tool_context is present, update session state with user: prefix
    if tool_context is not None and hasattr(tool_context, "state") and tool_context.state is not None:
        state_key = "user:logged_activities_count"
        current_count = tool_context.state.get(state_key, 0)
        tool_context.state[state_key] = current_count + 1
        tool_context.state["user:last_logged_activity"] = {
            "id": record["id"],
            "category": cat_clean,
            "details": det_clean,
            "kg_co2e": kg_val,
            "timestamp": record["timestamp"],
        }

    return {
        "status": "success",
        "message": f"Logged {det_clean} ({kg_val} kg CO2e)",
        "activity_id": record["id"],
        "category": cat_clean,
        "details": det_clean,
        "kg_co2e": kg_val,
        "timestamp": record["timestamp"],
        "user_id": user_id,
    }


def get_summary(
    period: str = "today",
    tool_context: Optional[Any] = None,
) -> Dict[str, Any]:
    """Retrieves carbon emissions totals, category breakdown, and trend for a period.

    Args:
        period: Time window ('today', 'week', 'month', 'six_months', 'all').
        tool_context: ADK context injected by the agent runtime.

    Returns:
        Dict with total_kg_co2e, activity_count, category_breakdown, and trend vs previous period.
    """
    user_id = _extract_user_id(tool_context)
    summary = get_summary_data(period=period, user_id=user_id)
    summary["status"] = "success"
    return summary


def suggest_alternative(
    category: str,
    mode: str,
    quantity: float,
) -> Dict[str, Any]:
    """Generates realistic, greener alternative options with exact savings and ease ratings.

    Evaluates compatibility rules deterministically (no hallucinations).
    Returns alternatives sorted by emission savings (highest first), then by ease level.

    Args:
        category: Activity category ('travel', 'appliance', 'food', 'waste').
        mode: The current chosen option (e.g. 'car_petrol', 'ac', 'mutton', 'mixed_landfill').
        quantity: Distance in km, hours of use, or servings/kg.

    Returns:
        Dict with current_kg, alternatives list (each with saving_kg, saving_percent, ease),
        or praise if already optimal.
    """
    cat_clean = str(category).strip().lower()
    mode_clean = str(mode).strip().lower().replace(" ", "_").replace("-", "_")

    try:
        qty_val = float(quantity)
    except (ValueError, TypeError):
        return {"status": "error", "message": f"Invalid quantity: {quantity}"}

    if qty_val < 0:
        return {"status": "error", "message": "Quantity cannot be negative."}

    alternatives: List[Dict[str, Any]] = []
    current_kg = 0.0

    # Ease ranking: Easy (1) -> Medium (2) -> Needs planning (3)
    ease_weights = {"Easy": 1, "Medium": 2, "Needs planning": 3}

    # 1. Travel category
    if cat_clean in ("travel", "transport"):
        if mode_clean not in TRAVEL_KG_PER_KM:
            return {"status": "error", "message": f"Unsupported travel mode: {mode}"}

        current_factor = TRAVEL_KG_PER_KM[mode_clean]
        current_kg = round(qty_val * current_factor, 4)

        candidate_modes: List[Tuple[str, str, str]] = []
        # Compatibility rules from Spec Section 2.4:
        # Distance <= 2 km by car/bike/auto: walk or cycle
        if qty_val <= 2.0:
            if mode_clean in ("car_petrol", "car_diesel", "car_electric", "two_wheeler", "auto_rickshaw"):
                candidate_modes.append(("walk", "Walk instead", "Easy"))
                candidate_modes.append(("cycle", "Bicycle instead", "Easy"))
        # 2 to 8 km by car/two-wheeler: bus, metro, carpool, e-scooter
        elif 2.0 < qty_val <= 8.0:
            if mode_clean in ("car_petrol", "car_diesel", "two_wheeler", "auto_rickshaw"):
                candidate_modes.append(("metro", "Take the Metro", "Easy"))
                candidate_modes.append(("bus", "Take a Public Bus", "Easy"))
                candidate_modes.append(("car_electric", "Switch to an Electric Two-Wheeler / EV", "Medium"))
        # 8 to 30 km by car: metro/train, bus, carpool (2+ people)
        elif 8.0 < qty_val <= 30.0:
            if mode_clean in ("car_petrol", "car_diesel", "auto_rickshaw"):
                candidate_modes.append(("metro", "Take the Metro", "Easy"))
                candidate_modes.append(("train", "Take Local Train / Suburban Rail", "Medium"))
                candidate_modes.append(("bus", "Take Express Bus", "Easy"))
                # Carpool (splits car emissions by half)
                carpool_kg = round(current_kg / 2.0, 4)
                carpool_saving = round(current_kg - carpool_kg, 4)
                carpool_pct = round((carpool_saving / current_kg) * 100, 1) if current_kg > 0 else 0.0
                alternatives.append({
                    "name": "Carpool (2+ people)",
                    "mode": "carpool",
                    "alternative_kg": carpool_kg,
                    "saving_kg": carpool_saving,
                    "saving_percent": carpool_pct,
                    "ease": "Medium",
                    "note": "Share the ride with a colleague or friend to cut emissions by 50%.",
                })
        # > 30 km: train or bus instead of car; avoid flight if train exists
        else:
            if mode_clean in ("car_petrol", "car_diesel"):
                candidate_modes.append(("train", "Take an Intercity Train", "Medium"))
                candidate_modes.append(("bus", "Take an Intercity Electric/CNG Bus", "Medium"))
            elif mode_clean == "flight_domestic":
                candidate_modes.append(("train", "Take High-Speed / Overnight Train instead of Flight", "Needs planning"))

        for alt_mode, alt_name, alt_ease in candidate_modes:
            alt_factor = TRAVEL_KG_PER_KM.get(alt_mode, 0.0)
            alt_kg = round(qty_val * alt_factor, 4)
            saving_kg = round(current_kg - alt_kg, 4)
            if saving_kg > 0.001:
                saving_pct = round((saving_kg / current_kg) * 100, 1) if current_kg > 0 else 0.0
                alternatives.append({
                    "name": alt_name,
                    "mode": alt_mode,
                    "alternative_kg": alt_kg,
                    "saving_kg": saving_kg,
                    "saving_percent": saving_pct,
                    "ease": alt_ease,
                    "note": f"Switching to {alt_mode} cuts your travel carbon by {saving_pct}%.",
                })

    # 2. Appliance category (e.g. AC)
    elif cat_clean in ("appliance", "electricity"):
        if mode_clean == "ac":
            power_kw = APPLIANCE_KW["ac"]
            current_kg = round(qty_val * power_kw * GRID_KG_PER_KWH, 4)

            # Rule: set 24-26 C (saves ~18% compressor energy)
            saving_24c = round(current_kg * 0.18, 4)
            alt_24c = round(current_kg - saving_24c, 4)
            alternatives.append({
                "name": "Set AC thermostat to 24-26°C",
                "mode": "ac_thermostat_24c",
                "alternative_kg": alt_24c,
                "saving_kg": saving_24c,
                "saving_percent": 18.0,
                "ease": "Easy",
                "note": "Every 1°C higher thermostat setting reduces compressor load by ~6%.",
            })

            # Rule: use fan + AC (cut AC hours in half, add fan)
            fan_kw = APPLIANCE_KW["fan"]
            half_ac_kg = (qty_val * 0.5) * power_kw * GRID_KG_PER_KWH
            fan_kg = qty_val * fan_kw * GRID_KG_PER_KWH
            alt_fan_ac = round(half_ac_kg + fan_kg, 4)
            saving_fan = round(current_kg - alt_fan_ac, 4)
            if saving_fan > 0:
                saving_pct = round((saving_fan / current_kg) * 100, 1)
                alternatives.append({
                    "name": "Use Ceiling Fan + AC (Shorter compressor duty)",
                    "mode": "fan_plus_ac",
                    "alternative_kg": alt_fan_ac,
                    "saving_kg": saving_fan,
                    "saving_percent": saving_pct,
                    "ease": "Easy",
                    "note": "Air circulation from a fan allows running AC for fewer hours while keeping cool.",
                })

            # Rule: Shorter hours (reduce by 1 hour)
            if qty_val > 1.0:
                saving_1h = round(1.0 * power_kw * GRID_KG_PER_KWH, 4)
                alt_1h = round(current_kg - saving_1h, 4)
                saving_pct = round((saving_1h / current_kg) * 100, 1)
                alternatives.append({
                    "name": f"Reduce AC usage to {qty_val - 1:.1f} hours",
                    "mode": "ac_shorter_hours",
                    "alternative_kg": alt_1h,
                    "saving_kg": saving_1h,
                    "saving_percent": saving_pct,
                    "ease": "Easy",
                    "note": "Using sleep timer to turn off AC 1 hour earlier saves significant energy.",
                })

            # Rule: 5-star inverter appliance upgrade
            saving_5star = round(current_kg * 0.30, 4)
            alt_5star = round(current_kg - saving_5star, 4)
            alternatives.append({
                "name": "Upgrade to BEE 5-Star Inverter AC",
                "mode": "ac_5star_inverter",
                "alternative_kg": alt_5star,
                "saving_kg": saving_5star,
                "saving_percent": 30.0,
                "ease": "Needs planning",
                "note": "Modern inverter ACs consume up to 30% less power than standard units.",
            })

    # 3. Food category
    elif cat_clean in ("food", "diet"):
        if mode_clean in FOOD_KG_PER_MEAL:
            current_factor = FOOD_KG_PER_MEAL[mode_clean]
            current_kg = round(qty_val * current_factor, 4)

            # Non-veg meal: vegetarian or egg/chicken instead of mutton/beef
            candidates: List[Tuple[str, str, str]] = []
            if mode_clean in ("beef", "mutton"):
                candidates.append(("veg", "Lacto-Vegetarian Meal (e.g. Dal, Paneer, Sabzi)", "Easy"))
                candidates.append(("egg", "Egg-based Meal", "Easy"))
                candidates.append(("chicken", "Poultry / Chicken Meal", "Easy"))
                candidates.append(("vegan", "Plant-based Vegan Meal (Legumes, Lentils)", "Medium"))
            elif mode_clean in ("chicken", "fish", "egg"):
                candidates.append(("veg", "Lacto-Vegetarian Meal", "Easy"))
                candidates.append(("vegan", "Plant-based Vegan Meal", "Medium"))

            for alt_type, alt_name, alt_ease in candidates:
                alt_factor = FOOD_KG_PER_MEAL[alt_type]
                alt_kg = round(qty_val * alt_factor, 4)
                saving_kg = round(current_kg - alt_kg, 4)
                if saving_kg > 0:
                    saving_pct = round((saving_kg / current_kg) * 100, 1)
                    alternatives.append({
                        "name": alt_name,
                        "mode": alt_type,
                        "alternative_kg": alt_kg,
                        "saving_kg": saving_kg,
                        "saving_percent": saving_pct,
                        "ease": alt_ease,
                        "note": f"Replacing {mode_clean} with {alt_type} cuts meal carbon by {saving_pct}%.",
                    })

    # 4. Waste category
    elif cat_clean == "waste":
        if mode_clean in WASTE_KG_PER_KG:
            current_factor = WASTE_KG_PER_KG[mode_clean]
            current_kg = round(qty_val * current_factor, 4)

            if mode_clean in ("mixed_landfill", "plastic"):
                alt_kg = round(qty_val * WASTE_KG_PER_KG["recycled"], 4)
                saving_kg = round(current_kg - alt_kg, 4)
                if saving_kg > 0:
                    saving_pct = round((saving_kg / current_kg) * 100, 1)
                    alternatives.append({
                        "name": "Segregate and send for recycling",
                        "mode": "recycled",
                        "alternative_kg": alt_kg,
                        "saving_kg": saving_kg,
                        "saving_percent": saving_pct,
                        "ease": "Easy",
                        "note": "Recycling diverts solid waste from open dumps and captures reusable materials.",
                    })
            if mode_clean == "food_waste":
                # Composting wet waste produces negligible landfill methane
                alt_kg = 0.0
                saving_kg = current_kg
                alternatives.append({
                    "name": "Home / Community Composting for Wet Waste",
                    "mode": "compost",
                    "alternative_kg": 0.0,
                    "saving_kg": saving_kg,
                    "saving_percent": 100.0,
                    "ease": "Medium",
                    "note": "Composting aerates organic matter, eliminating anaerobic methane generation.",
                })

    # Filter for strictly positive savings
    valid_alts = [a for a in alternatives if a["saving_kg"] > 0]

    # Rank by saving (DESC), then ease level (Easy < Medium < Needs planning)
    valid_alts.sort(key=lambda x: (-x["saving_kg"], ease_weights.get(x["ease"], 99)))

    if not valid_alts:
        return {
            "status": "success",
            "category": cat_clean,
            "mode": mode_clean,
            "quantity": qty_val,
            "current_kg": current_kg,
            "already_optimal": True,
            "message": f"Great job! Your choice ({mode_clean}) is already among the lowest carbon options.",
            "alternatives": [],
        }

    return {
        "status": "success",
        "category": cat_clean,
        "mode": mode_clean,
        "quantity": qty_val,
        "current_kg": current_kg,
        "already_optimal": False,
        "top_recommendation": valid_alts[0],
        "alternatives": valid_alts,
    }


def suggest_reductions(tool_context: Optional[Any] = None) -> Dict[str, Any]:
    """Analyzes logged history to find the highest-emitting category and returns actionable tips.

    Args:
        tool_context: ADK context injected by the agent runtime.

    Returns:
        Dict with top_category, total_kg, percentage, and concrete reduction options.
    """
    user_id = _extract_user_id(tool_context)
    top_cat_data = get_highest_emitting_category(user_id=user_id, period="month")

    if not top_cat_data:
        return {
            "status": "success",
            "message": "Not enough logged activities yet to identify your highest emitting category. Keep logging!",
            "recommendations": [],
        }

    top_cat = top_cat_data["category"]
    top_kg = top_cat_data["kg_co2e"]
    top_pct = top_cat_data["percentage"]

    # Provide category specific suggestions with computed potential savings
    recommendations = []
    if top_cat == "travel":
        recommendations.append({
            "action": "Switch 10 km of weekly car travel to Metro or Bus",
            "estimated_weekly_saving_kg": round(10 * (0.17 - 0.03), 2),
            "ease": "Easy",
            "impact": "High",
        })
        recommendations.append({
            "action": "Walk or cycle for trips under 2 km",
            "estimated_weekly_saving_kg": round(5 * 0.05, 2),
            "ease": "Easy",
            "impact": "Medium",
        })
    elif top_cat in ("appliance", "electricity"):
        recommendations.append({
            "action": "Set AC temperature to 25°C instead of 20°C (18% cooling reduction)",
            "estimated_weekly_saving_kg": round(7 * (4 * 1.5 * 0.71 * 0.18), 2),
            "ease": "Easy",
            "impact": "High",
        })
        recommendations.append({
            "action": "Turn off water geyser immediately after heating (save 0.5h/day)",
            "estimated_weekly_saving_kg": round(7 * (0.5 * 2.0 * 0.71), 2),
            "ease": "Easy",
            "impact": "Medium",
        })
    elif top_cat == "food":
        recommendations.append({
            "action": "Replace one mutton/beef meal per week with a vegetarian meal",
            "estimated_weekly_saving_kg": round(5.5 - 0.7, 2),
            "ease": "Easy",
            "impact": "High",
        })
        recommendations.append({
            "action": "Designate one day a week as Green/Vegan day",
            "estimated_weekly_saving_kg": round(3 * (1.8 - 0.4), 2),
            "ease": "Medium",
            "impact": "Medium",
        })
    else:
        recommendations.append({
            "action": "Compost kitchen wet waste to prevent anaerobic methane in landfills",
            "estimated_weekly_saving_kg": round(3.0 * 0.8, 2),
            "ease": "Medium",
            "impact": "Medium",
        })

    return {
        "status": "success",
        "highest_emitting_category": top_cat,
        "category_kg_co2e": top_kg,
        "category_percentage": top_pct,
        "recommendations": recommendations,
    }


def set_carbon_budget(
    monthly_kg: float,
    six_month_kg: float,
    tool_context: Optional[Any] = None,
) -> Dict[str, Any]:
    """Updates the user's monthly and six-month carbon budget thresholds.

    Args:
        monthly_kg: Target monthly limit in kg CO2e (must be > 0).
        six_month_kg: Target six-month limit in kg CO2e (must be > 0).
        tool_context: ADK context injected by the agent runtime.

    Returns:
        Dict with status, updated budget figures, and user_id.
    """
    if monthly_kg is None or six_month_kg is None:
        return {"status": "error", "message": "Both monthly_kg and six_month_kg are required."}

    try:
        m_val = float(monthly_kg)
        s_val = float(six_month_kg)
    except (ValueError, TypeError):
        return {"status": "error", "message": "Budget values must be numeric."}

    if m_val <= 0 or s_val <= 0:
        return {"status": "error", "message": "Budget values must be greater than zero."}

    user_id = _extract_user_id(tool_context)
    res = storage_set_budget(monthly_kg=m_val, six_month_kg=s_val, user_id=user_id)

    if tool_context is not None and hasattr(tool_context, "state") and tool_context.state is not None:
        tool_context.state["user:monthly_budget_kg"] = m_val
        tool_context.state["user:six_month_budget_kg"] = s_val

    return {
        "status": "success",
        "message": f"Updated budget thresholds to {m_val} kg/month and {s_val} kg/6-months.",
        "monthly_kg": m_val,
        "six_month_kg": s_val,
        "user_id": user_id,
    }


def check_carbon_budget(tool_context: Optional[Any] = None) -> Dict[str, Any]:
    """Evaluates carbon usage against monthly and 6-month budgets.

    Status thresholds:
    - < 80%: ok
    - 80% to 100%: warning
    - > 100%: exceeded

    Args:
        tool_context: ADK context injected by the agent runtime.

    Returns:
        Dict with status (ok, warning, exceeded), monthly data, and six_months data.
    """
    user_id = _extract_user_id(tool_context)
    status_data = storage_get_budget_status(user_id=user_id)
    status_data["status_code"] = "success"
    return status_data


def calculate_tree_offset(excess_kg: float) -> Dict[str, Any]:
    """Calculates tree-planting requirements to absorb excess CO2e emissions.

    Uses a benchmark of 21 kg CO2 absorbed per mature tree per year.

    Args:
        excess_kg: Emissions in kg CO2e exceeding the budget (must be >= 0).

    Returns:
        Dict with trees_needed (1-year offset), multi-year options, and practical planting advice.
    """
    if excess_kg is None:
        return {"status": "error", "message": "excess_kg must be provided."}

    try:
        excess_val = float(excess_kg)
    except (ValueError, TypeError):
        return {"status": "error", "message": f"Invalid excess_kg value: {excess_kg}"}

    if excess_val < 0:
        return {"status": "error", "message": "excess_kg cannot be negative."}

    if excess_val == 0:
        return {
            "status": "success",
            "excess_kg": 0.0,
            "trees_needed": 0,
            "message": "Emissions are within budget. No offset required!",
        }

    # ceil(excess / 21) as specified in Spec Section 2.5
    trees_1_year = math.ceil(excess_val / KG_CO2_PER_TREE_PER_YEAR)
    trees_3_year = math.ceil(excess_val / (KG_CO2_PER_TREE_PER_YEAR * 3))
    trees_5_year = math.ceil(excess_val / (KG_CO2_PER_TREE_PER_YEAR * 5))

    return {
        "status": "success",
        "excess_kg": round(excess_val, 2),
        "kg_per_tree_per_year": KG_CO2_PER_TREE_PER_YEAR,
        "source": TREE_OFFSET_SOURCE,
        "trees_needed": trees_1_year,
        "timeline_options": [
            {
                "years_to_offset": 1,
                "trees_needed": trees_1_year,
                "note": f"{trees_1_year} trees absorbing ~{KG_CO2_PER_TREE_PER_YEAR} kg CO2/year will offset {excess_val:.1f} kg in 1 year.",
            },
            {
                "years_to_offset": 3,
                "trees_needed": trees_3_year,
                "note": f"{trees_3_year} trees will offset the excess over a 3-year growth period.",
            },
            {
                "years_to_offset": 5,
                "trees_needed": trees_5_year,
                "note": f"{trees_5_year} trees will offset the excess over a 5-year growth period.",
            },
        ],
        "important_disclosure": (
            "Trees take years to grow into maturity and offset carbon over time. "
            "Planting trees complements but never replaces cutting emissions at the source."
        ),
        "practical_channels": [
            "Campus plantation drives or student environmental club activities",
            "State Forest Department seedling distribution programmes",
            "Local community nurseries and urban greening initiatives",
        ],
    }


def get_leaderboard(group_type: str = "hostel") -> Dict[str, Any]:
    """Retrieves campus emissions leaderboard comparing hostels or departments.

    Args:
        group_type: Grouping category ('hostel', 'department', 'floor').

    Returns:
        Dict with status, group_type, and ranked list of groups by avg kg per person.
    """
    clean_gt = str(group_type).strip().lower()
    data = get_leaderboard_data(group_type=clean_gt)
    return {
        "status": "success",
        "group_type": clean_gt,
        "leaderboard": data,
    }
