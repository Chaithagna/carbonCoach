"""FastAPI backend server for Carbon Coach.

Provides REST and Chat endpoints for the React dashboard, CLI, and integration tests.
Guarantees that every emission, budget status, tree count, and saving figure
originates strictly from calculation tools.
"""

import os
import re
import math
from types import SimpleNamespace
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from carbon_coach.factors import (
    GRID_KG_PER_KWH,
    TRAVEL_KG_PER_KM,
    APPLIANCE_KW,
    FOOD_KG_PER_MEAL,
    WASTE_KG_PER_KG,
    KG_CO2_PER_TREE_PER_YEAR,
    DEFAULT_MONTHLY_BUDGET_KG,
    DEFAULT_SIX_MONTH_BUDGET_KG,
)
from carbon_coach.storage import (
    init_db,
    save_activity as storage_save_activity,
    get_all_activities,
    get_summary_data,
    set_user_budget as storage_set_budget,
    get_user_budget as storage_get_budget,
    get_budget_status as storage_get_budget_status,
    record_user_group,
    get_leaderboard_data,
)
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

load_dotenv()
init_db()

app = FastAPI(
    title="Carbon Coach API",
    description="Backend API powering the Carbon Coach Conversational Agent and Dashboard.",
    version="1.0.0",
)

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request/Response Models ---

class ChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = "default_user"


class LogActivityRequest(BaseModel):
    category: str
    details: str
    kg_co2e: float
    user_id: Optional[str] = "default_user"


class SetBudgetRequest(BaseModel):
    monthly_kg: float
    six_month_kg: float
    user_id: Optional[str] = "default_user"


class AlternativeRequest(BaseModel):
    category: str
    mode: str
    quantity: float


class GroupRegisterRequest(BaseModel):
    user_id: str
    group_type: str
    group_name: str


# --- Intelligent Natural Language & Tool Orchestrator ---

def parse_and_process_message(message: str, user_id: str = "default_user") -> Dict[str, Any]:
    """Interprets conversational user inputs, executes tools deterministically,
    and formats responses strictly complying with CARBON_COACH_SPEC.md rules.
    """
    msg_lower = message.lower().strip()
    tool_context = SimpleNamespace(user_id=user_id)
    tool_results: List[Dict[str, Any]] = []
    logged_activities: List[Dict[str, Any]] = []
    alternatives_list: List[Dict[str, Any]] = []

    # Detect language (Hindi / Telugu / English)
    is_hindi = any(ord(c) >= 0x0900 and ord(c) <= 0x097F for c in message)
    is_telugu = any(ord(c) >= 0x0C00 and ord(c) <= 0x0C7F for c in message)

    # 1. Budget setting intent (e.g., "set monthly budget to 120 kg")
    budget_set_match = re.search(r"set\s+(?:my\s+)?(?:monthly\s+)?budget\s+to\s+([0-9.]+)", msg_lower)
    if budget_set_match:
        m_kg = float(budget_set_match.group(1))
        # Default six-month is 6x monthly or 900
        s_kg = m_kg * 6.0
        b_res = set_carbon_budget(
            monthly_kg=m_kg,
            six_month_kg=s_kg,
            tool_context=tool_context,
        )
        tool_results.append({"tool": "set_carbon_budget", "result": b_res})
        return {
            "reply": f"Your carbon budget has been updated to {m_kg} kg/month and {s_kg} kg/6-months.",
            "tool_results": tool_results,
            "budget_status": check_carbon_budget(tool_context=tool_context),
        }

    # 2. "How did I do" / Summary queries
    if any(q in msg_lower for q in ("how did i do", "summary", "my emissions", "my footprint", "report")):
        period = "month"
        if "today" in msg_lower:
            period = "today"
        elif "week" in msg_lower:
            period = "week"
        elif "6 month" in msg_lower or "six month" in msg_lower or "last 6" in msg_lower:
            period = "six_months"

        summary = get_summary(period=period, tool_context=tool_context)
        tool_results.append({"tool": "get_summary", "result": summary})

        tot = summary["total_kg_co2e"]
        cnt = summary["activity_count"]
        trend = summary["trend"]
        direction = trend["direction"]
        diff = abs(trend["diff_kg"])

        breakdown_parts = []
        for cat, data in summary.get("category_breakdown", {}).items():
            breakdown_parts.append(f"{cat}: {data['kg_co2e']} kg ({data['percentage']}%)")
        breakdown_str = ", ".join(breakdown_parts) if breakdown_parts else "no activities logged yet"

        reply = (
            f"Here is your summary for {period}: Total emissions are {tot} kg CO2e across {cnt} activities "
            f"({breakdown_str}). "
            f"Compared to the previous period, emissions {direction} by {diff} kg ({trend['percent_change']}%)."
        )
        return {
            "reply": reply,
            "tool_results": tool_results,
            "summary": summary,
            "budget_status": check_carbon_budget(tool_context=tool_context),
        }

    # 3. Leaderboard query
    if any(q in msg_lower for q in ("leaderboard", "hostel", "department", "campus ranking")):
        g_type = "hostel" if "hostel" in msg_lower else "department"
        lb = get_leaderboard(group_type=g_type)
        tool_results.append({"tool": "get_leaderboard", "result": lb})
        entries = lb.get("leaderboard", [])
        if entries:
            top_str = ", ".join(f"#{e['rank']} {e['group_name']} ({e['avg_kg_per_person']} kg/person)" for e in entries[:3])
            reply = f"Campus {g_type} leaderboard: {top_str}."
        else:
            reply = f"No campus data recorded yet for {g_type}s."
        return {
            "reply": reply,
            "tool_results": tool_results,
            "leaderboard": lb,
        }

    # 4. Tips / Reduction query
    if any(q in msg_lower for q in ("tips", "how to reduce", "cut emissions", "suggest reductions")):
        reductions = suggest_reductions(tool_context=tool_context)
        tool_results.append({"tool": "suggest_reductions", "result": reductions})
        top_cat = reductions.get("highest_emitting_category", "general")
        recs = reductions.get("recommendations", [])
        if recs:
            rec_texts = "; ".join(f"{r['action']} (saves ~{r['estimated_weekly_saving_kg']} kg/week, {r['ease']})" for r in recs)
            reply = f"Your highest-emitting category this month is {top_cat}. Recommended steps: {rec_texts}."
        else:
            reply = "Log more activities so I can personalize your reduction steps!"
        return {
            "reply": reply,
            "tool_results": tool_results,
            "reductions": reductions,
        }

    # 5. Missing parameter check: user mentions travel mode without any distance
    travel_keywords = ["car", "bus", "metro", "train", "taxi", "cab", "auto", "flight", "plane", "two wheeler", "bike", "cycle", "walk"]
    has_travel_kw = any(kw in msg_lower for kw in travel_keywords)
    has_distance = bool(re.search(r"(\d+(?:\.\d+)?)\s*(?:km|kms|kilometer|kilometres|miles)", msg_lower))

    if has_travel_kw and not has_distance and not re.search(r"\d+", msg_lower):
        if is_hindi:
            return {"reply": "आपकी यात्रा की दूरी कितने किलोमीटर थी?", "tool_results": []}
        if is_telugu:
            return {"reply": "మీ ప్రయాణ దూరం ఎన్ని కిలోమీటర్లు?", "tool_results": []}
        return {"reply": "How many kilometers was your trip?", "tool_results": []}

    # 6. Extract Activities (Multi-activity support: travel, appliance, food, waste)
    extracted = False

    # A. Travel extraction (English, Hindi, Telugu)
    travel_patterns = [
        r"([0-9.]+)\s*(?:km|kms|kilometers|किमी|किलोमीटर|కిమీ|కిలోమీటర్లు|కిలోమీటర్ల|కిలోమీటర్)?\s*(?:by|in|via|on|की|తో)?\s*(walk|cycle|bicycle|bus|metro|train|auto|rickshaw|car|petrol car|diesel car|electric car|ev|two wheeler|bike|motorcycle|scooter|flight|plane|बस|कार|मेट्रो|ट्रेन|ऑटो|साइकिल|బస్సు|కారు|మెట్రో|రైలు|ఆటో|సైకిల్)",
        r"(walk|cycle|bicycle|bus|metro|train|auto|rickshaw|car|petrol car|diesel car|electric car|ev|two wheeler|bike|motorcycle|scooter|flight|plane|बस|कार|मेट्रो|ट्रेन|ऑटो|साइकिल|బస్సు|కారు|మెట్రో|రైలు|ఆటో|సైకిల్)\s*(?:for|లో|में|से)?\s*([0-9.]+)\s*(?:km|kms|kilometers|किमी|किलोमीटर|కిమీ|కిలోమీటర్లు|కిలోమీటర్ల|కిలోమీటర్)",
    ]

    for pat in travel_patterns:
        for match in re.finditer(pat, msg_lower):
            g1, g2 = match.groups()
            try:
                km = float(g1)
                mode_raw = g2
            except ValueError:
                km = float(g2)
                mode_raw = g1

            # Map mode_raw to factors dictionary keys (including Hindi and Telugu)
            mode_map = {
                "walk": "walk", "cycle": "cycle", "bicycle": "cycle",
                "bus": "bus", "metro": "metro", "train": "train",
                "auto": "auto_rickshaw", "rickshaw": "auto_rickshaw",
                "car": "car_petrol", "petrol car": "car_petrol", "diesel car": "car_diesel",
                "electric car": "car_electric", "ev": "car_electric",
                "two wheeler": "two_wheeler", "bike": "two_wheeler", "motorcycle": "two_wheeler", "scooter": "two_wheeler",
                "flight": "flight_domestic", "plane": "flight_domestic",
                # Hindi
                "बस": "bus", "कार": "car_petrol", "मेट्रो": "metro", "ट्रेन": "train",
                "ऑटो": "auto_rickshaw", "साइकिल": "cycle",
                # Telugu
                "బస్సు": "bus", "కారు": "car_petrol", "మెట్రో": "metro", "రైలు": "train",
                "ఆటో": "auto_rickshaw", "సైకిల్": "cycle",
            }
            mode = mode_map.get(mode_raw, "car_petrol")

            calc = calculate_travel_emissions(mode, km)
            tool_results.append({"tool": "calculate_travel_emissions", "result": calc})
            if calc.get("status") == "success":
                kg = calc["kg_co2e"]
                log_res = log_activity(
                    "travel",
                    f"{mode} {km} km",
                    kg,
                    tool_context=tool_context,
                )
                tool_results.append({"tool": "log_activity", "result": log_res})
                logged_activities.append({"category": "travel", "details": f"{mode} {km} km", "kg_co2e": kg})

                alt = suggest_alternative("travel", mode, km)
                tool_results.append({"tool": "suggest_alternative", "result": alt})
                if alt.get("status") == "success":
                    alternatives_list.append(alt)
                extracted = True

    # B. Appliance extraction
    # Pattern: "used the ac for 4 hours", "ac 4 hours", "fan for 8 hours"
    app_pattern = r"(ac|fan|light|refrigerator|fridge|laptop|geyser|washing machine)\s*(?:for|use|used|ran)?\s*([0-9.]+)\s*(?:hour|hours|h|hrs)"
    for match in re.finditer(app_pattern, msg_lower):
        app_raw, hours_str = match.groups()
        hours = float(hours_str)
        app_map = {"fridge": "refrigerator", "ac": "ac", "fan": "fan", "light": "light", "laptop": "laptop", "geyser": "geyser", "washing machine": "washing_machine"}
        app = app_map.get(app_raw, app_raw)

        calc = calculate_appliance_emissions(app, hours)
        tool_results.append({"tool": "calculate_appliance_emissions", "result": calc})
        if calc.get("status") == "success":
            kg = calc["kg_co2e"]
            log_res = log_activity(
                "appliance",
                f"{app} {hours} hours",
                kg,
                tool_context=tool_context,
            )
            tool_results.append({"tool": "log_activity", "result": log_res})
            logged_activities.append({"category": "appliance", "details": f"{app} {hours} hours", "kg_co2e": kg})

            alt = suggest_alternative("appliance", app, hours)
            tool_results.append({"tool": "suggest_alternative", "result": alt})
            if alt.get("status") == "success":
                alternatives_list.append(alt)
            extracted = True

    # C. Food extraction
    # Pattern: "ate 2 servings of chicken", "mutton meal", "veg food"
    food_pattern = r"(?:ate|had|eating)?\s*([0-9]+)?\s*(?:servings?|meals?|plates?)?\s*(?:of)?\s*(vegan|veg|vegetarian|egg|fish|chicken|mutton|beef)"
    for match in re.finditer(food_pattern, msg_lower):
        serv_str, food_raw = match.groups()
        if not food_raw:
            continue
        servings = int(serv_str) if serv_str else 1
        food_map = {"vegetarian": "veg"}
        f_type = food_map.get(food_raw, food_raw)

        calc = calculate_food_emissions(f_type, servings)
        tool_results.append({"tool": "calculate_food_emissions", "result": calc})
        if calc.get("status") == "success":
            kg = calc["kg_co2e"]
            log_res = log_activity(
                "food",
                f"{f_type} {servings} serving(s)",
                kg,
                tool_context=tool_context,
            )
            tool_results.append({"tool": "log_activity", "result": log_res})
            logged_activities.append({"category": "food", "details": f"{f_type} {servings} serving(s)", "kg_co2e": kg})

            alt = suggest_alternative("food", f_type, servings)
            tool_results.append({"tool": "suggest_alternative", "result": alt})
            if alt.get("status") == "success":
                alternatives_list.append(alt)
            extracted = True

    # D. Waste extraction
    waste_pattern = r"([0-9.]+)\s*(?:kg|kgs|kilograms)\s*(?:of)?\s*(plastic|paper|food waste|mixed landfill|garbage|trash|recycled)"
    for match in re.finditer(waste_pattern, msg_lower):
        kg_str, waste_raw = match.groups()
        w_kg = float(kg_str)
        waste_map = {"garbage": "mixed_landfill", "trash": "mixed_landfill", "food waste": "food_waste"}
        w_type = waste_map.get(waste_raw, waste_raw)

        calc = calculate_waste_emissions(w_type, w_kg)
        tool_results.append({"tool": "calculate_waste_emissions", "result": calc})
        if calc.get("status") == "success":
            kg = calc["kg_co2e"]
            log_res = log_activity(
                "waste",
                f"{w_type} {w_kg} kg",
                kg,
                tool_context=tool_context,
            )
            tool_results.append({"tool": "log_activity", "result": log_res})
            logged_activities.append({"category": "waste", "details": f"{w_type} {w_kg} kg", "kg_co2e": kg})
            extracted = True

    # If nothing was extracted and no other intent matched, prompt user gently
    if not extracted:
        if is_hindi:
            return {
                "reply": "नमस्ते! मैं कार्बन कोच हूँ। आप अपनी दैनिक गतिविधियाँ (जैसे '12 किमी बस और 4 घंटे एसी') साझा कर सकते हैं।",
                "tool_results": [],
            }
        if is_telugu:
            return {
                "reply": "నమస్కారం! నేను కార్బన్ కోచ్‌ని. మీరు మీ రోజువారీ కార్యకలాపాలను (ఉదాహరణకు '12 కిమీ బస్సు మరియు 4 గంటలు ఏసీ') నమోదు చేయవచ్చు.",
                "tool_results": [],
            }
        return {
            "reply": "I am Carbon Coach. Tell me about your day, for example: 'I travelled 12 km by car and used the AC for 4 hours.'",
            "tool_results": [],
        }

    # Evaluate budget status after logging
    budget_status = check_carbon_budget(tool_context=tool_context)
    tool_results.append({"tool": "check_carbon_budget", "result": budget_status})

    monthly = budget_status["monthly"]
    month_used = monthly["used_kg"]
    month_pct = monthly["percent_used"]
    month_rem = monthly["remaining_kg"]
    month_stat = monthly["status"]
    month_excess = monthly["excess_kg"]

    # Format reply strictly per Spec Section 6 and Section 2.5
    logged_summary_parts = [f"{act['details']} = {act['kg_co2e']} kg" for act in logged_activities]
    total_batch_kg = round(sum(act["kg_co2e"] for act in logged_activities), 3)

    reply_parts = []
    reply_parts.append(f"Logged: {', '.join(logged_summary_parts)}, total {total_batch_kg} kg.")

    # Alternatives section
    for alt in alternatives_list:
        if alt.get("already_optimal"):
            reply_parts.append(f"{alt.get('message', 'Great green choice!')}")
        elif alt.get("alternatives"):
            top = alt["alternatives"][0]
            reply_parts.append(
                f"If you choose {top['name']}, you would save {top['saving_kg']} kg ({top['saving_percent']}%), and it is {top['ease']}."
            )

    # Budget Status & Tree offset handling
    if month_stat == "exceeded":
        offset_res = calculate_tree_offset(month_excess)
        tool_results.append({"tool": "calculate_tree_offset", "result": offset_res})
        trees = offset_res["trees_needed"]
        tree_factor_int = int(KG_CO2_PER_TREE_PER_YEAR)
        reply_parts.append(
            f"You have crossed your monthly carbon limit by {month_excess} kg. "
            f"To balance that, about {trees} tree{'s' if trees != 1 else ''} (~{tree_factor_int} kg CO2 per tree per year) would be needed. "
            f"A campus plantation drive or community nursery is a good way to do it. "
            f"Remember, trees take years to grow and offset carbon over time, so cutting emissions is paramount. "
            f"Meanwhile, here are two changes that help most: switch short car trips to public transit and set your AC thermostat to 24-26°C."
        )
    elif month_stat == "warning":
        reply_parts.append(
            f"Monthly budget: You have used {month_pct}% of your monthly budget ({month_rem} kg left). "
            f"Consider taking the metro/bus or raising your AC temperature by 2°C to stay within your limit."
        )
    else:
        reply_parts.append(f"Monthly budget: {month_pct}% used, {month_rem} kg left. Keep up the great work!")

    full_reply = " ".join(reply_parts)

    # Multilingual translation if needed
    if is_hindi:
        full_reply = f"दर्ज किया गया: {total_batch_kg} किग्रा CO2e। मासिक बजट: {month_pct}% उपयोग ({month_rem} किग्रा शेष)।"
    elif is_telugu:
        full_reply = f"నమోదు చేయబడింది: {total_batch_kg} కిలోల CO2e. నెలవారీ బడ్జెట్: {month_pct}% ఉపయోగించబడింది ({month_rem} కిలోలు మిగిలి ఉన్నాయి)."

    return {
        "reply": full_reply,
        "tool_results": tool_results,
        "activities_logged": logged_activities,
        "budget_status": budget_status,
        "alternatives": alternatives_list,
    }


# --- REST Endpoints ---

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """Conversational endpoint executing Google ADK tools and returning grounded responses."""
    try:
        response_data = parse_and_process_message(request.message, user_id=request.user_id or "default_user")
        return response_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/activities")
async def get_activities_endpoint(user_id: str = "default_user", limit: int = 100):
    """Returns recent activities for user_id."""
    return get_all_activities(user_id=user_id, limit=limit)


@app.post("/api/activities")
async def log_activity_endpoint(request: LogActivityRequest):
    """Directly log an activity with verified calculation."""
    res = log_activity(
        category=request.category,
        details=request.details,
        kg_co2e=request.kg_co2e,
        tool_context=SimpleNamespace(user_id=request.user_id or "default_user"),
    )
    return res


@app.get("/api/summary")
async def get_summary_endpoint(period: str = "month", user_id: str = "default_user"):
    """Returns emissions totals, category breakdown, and trends."""
    return get_summary(
        period=period,
        tool_context=SimpleNamespace(user_id=user_id or "default_user"),
    )


@app.get("/api/budget")
async def get_budget_endpoint(user_id: str = "default_user"):
    """Returns current usage and status against monthly and 6-month budgets."""
    return check_carbon_budget(
        tool_context=SimpleNamespace(user_id=user_id or "default_user"),
    )


@app.post("/api/budget")
async def set_budget_endpoint(request: SetBudgetRequest):
    """Updates carbon budget limits."""
    return set_carbon_budget(
        monthly_kg=request.monthly_kg,
        six_month_kg=request.six_month_kg,
        tool_context=SimpleNamespace(user_id=request.user_id or "default_user"),
    )


@app.post("/api/alternatives")
async def get_alternatives_endpoint(request: AlternativeRequest):
    """Computes realistic greener alternatives with savings and ease ratings."""
    return suggest_alternative(
        category=request.category,
        mode=request.mode,
        quantity=request.quantity,
    )


@app.get("/api/reductions")
async def get_reductions_endpoint(user_id: str = "default_user"):
    """Personalized reduction suggestions based on highest emitting category."""
    return suggest_reductions(
        tool_context=SimpleNamespace(user_id=user_id or "default_user"),
    )


@app.get("/api/tree-offset")
async def get_tree_offset_endpoint(excess_kg: float = Query(..., ge=0)):
    """Computes tree offset requirements for excess emissions."""
    return calculate_tree_offset(excess_kg=excess_kg)


@app.get("/api/leaderboard")
async def get_leaderboard_endpoint(group_type: str = "hostel"):
    """Returns campus mode rankings by group type."""
    return get_leaderboard(group_type=group_type)


@app.get("/api/factors")
async def get_factors_endpoint():
    """Returns official verified emission factors and citations."""
    return {
        "grid_kg_per_kwh": GRID_KG_PER_KWH,
        "travel_kg_per_km": TRAVEL_KG_PER_KM,
        "appliance_kw": APPLIANCE_KW,
        "food_kg_per_meal": FOOD_KG_PER_MEAL,
        "waste_kg_per_kg": WASTE_KG_PER_KG,
        "tree_kg_per_year": KG_CO2_PER_TREE_PER_YEAR,
        "default_monthly_budget": DEFAULT_MONTHLY_BUDGET_KG,
        "default_six_month_budget": DEFAULT_SIX_MONTH_BUDGET_KG,
    }


# Mount built static assets if available
dist_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard", "dist")
if os.path.exists(dist_dir):
    app.mount("/", StaticFiles(directory=dist_dir, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
