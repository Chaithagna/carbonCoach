"""Comprehensive unit tests for Carbon Coach calculation tools, storage, and budgets.
"""

import pytest
import os
import tempfile
import math

from carbon_coach.tools import (
    calculate_travel_emissions,
    calculate_electricity_emissions,
    calculate_appliance_emissions,
    calculate_food_emissions,
    calculate_waste_emissions,
    calculate_tree_offset,
    suggest_alternative,
    log_activity,
    get_summary,
    check_carbon_budget,
    set_carbon_budget,
    suggest_reductions,
    get_leaderboard,
)
from carbon_coach.storage import (
    init_db,
    save_activity,
    get_summary_data,
    set_user_budget,
    get_user_budget,
    get_budget_status,
    record_user_group,
    get_leaderboard_data,
)


# --- 1. Travel Emissions Tests ---

def test_calculate_travel_bus():
    """Verify 12 km by bus = 12 * 0.089 = 1.068 kg CO2e."""
    res = calculate_travel_emissions("bus", 12)
    assert res["status"] == "success"
    assert math.isclose(res["kg_co2e"], 1.068, rel_tol=1e-3)
    assert res["unit"] == "kg CO2e/pkm"
    assert res["factor"] == 0.089


def test_calculate_travel_walk():
    """Verify walking has 0 emissions."""
    res = calculate_travel_emissions("walk", 5)
    assert res["status"] == "success"
    assert res["kg_co2e"] == 0.0


def test_calculate_travel_cycle():
    """Verify cycling has 0 emissions."""
    res = calculate_travel_emissions("cycle", 10)
    assert res["status"] == "success"
    assert res["kg_co2e"] == 0.0


def test_calculate_travel_car_petrol():
    """Verify 10 km petrol car = 10 * 0.17 = 1.7 kg CO2e."""
    res = calculate_travel_emissions("car_petrol", 10)
    assert res["status"] == "success"
    assert math.isclose(res["kg_co2e"], 1.70, rel_tol=1e-3)


def test_calculate_travel_invalid_mode():
    """Verify unsupported travel mode returns error status."""
    res = calculate_travel_emissions("rocket", 100)
    assert res["status"] == "error"
    assert "Unsupported travel mode" in res["message"]


def test_calculate_travel_negative_distance():
    """Verify negative distance returns error status."""
    res = calculate_travel_emissions("bus", -5)
    assert res["status"] == "error"
    assert "cannot be negative" in res["message"]


# --- 2. Electricity & Appliance Tests ---

def test_calculate_electricity():
    """Verify electricity calculation with 0.71 grid factor."""
    res = calculate_electricity_emissions(10)
    assert res["status"] == "success"
    assert math.isclose(res["kg_co2e"], 7.10, rel_tol=1e-3)
    assert res["factor"] == 0.71


def test_calculate_electricity_negative():
    """Verify negative electricity consumption returns error."""
    res = calculate_electricity_emissions(-10)
    assert res["status"] == "error"


def test_calculate_appliance_ac():
    """Verify 4 hours AC = 4 * 1.5 * 0.71 = 4.26 kg CO2e."""
    res = calculate_appliance_emissions("ac", 4)
    assert res["status"] == "success"
    assert math.isclose(res["kg_co2e"], 4.26, rel_tol=1e-3)
    assert res["power_kw"] == 1.5
    assert res["grid_factor"] == 0.71


def test_calculate_appliance_fan():
    """Verify 10 hours fan = 10 * 0.07 * 0.71 = 0.497 kg CO2e."""
    res = calculate_appliance_emissions("fan", 10)
    assert res["status"] == "success"
    assert math.isclose(res["kg_co2e"], 0.497, rel_tol=1e-3)


def test_calculate_appliance_invalid():
    """Verify unsupported appliance returns error."""
    res = calculate_appliance_emissions("supercomputer", 5)
    assert res["status"] == "error"


def test_calculate_appliance_negative_hours():
    """Verify negative usage duration returns error."""
    res = calculate_appliance_emissions("ac", -2)
    assert res["status"] == "error"


# --- 3. Food & Waste Tests ---

def test_calculate_food_emissions():
    """Verify food calculations for veg and mutton."""
    veg_res = calculate_food_emissions("veg", 2)
    assert veg_res["status"] == "success"
    assert math.isclose(veg_res["kg_co2e"], 1.40, rel_tol=1e-3)

    mutton_res = calculate_food_emissions("mutton", 1)
    assert mutton_res["status"] == "success"
    assert math.isclose(mutton_res["kg_co2e"], 5.50, rel_tol=1e-3)


def test_calculate_food_invalid():
    """Verify invalid food type returns error."""
    res = calculate_food_emissions("alien_meat", 1)
    assert res["status"] == "error"


def test_calculate_food_invalid_servings():
    """Verify non-positive servings returns error."""
    res = calculate_food_emissions("veg", 0)
    assert res["status"] == "error"


def test_calculate_waste_emissions():
    """Verify waste calculations."""
    res = calculate_waste_emissions("plastic", 3)
    assert res["status"] == "success"
    assert math.isclose(res["kg_co2e"], 6.0, rel_tol=1e-3)

    rec = calculate_waste_emissions("recycled", 5)
    assert rec["status"] == "success"
    assert math.isclose(rec["kg_co2e"], 0.5, rel_tol=1e-3)


def test_calculate_waste_invalid():
    """Verify invalid waste type returns error."""
    res = calculate_waste_emissions("nuclear", 1)
    assert res["status"] == "error"


# --- 4. Tree Offset Calculation Tests ---

def test_calculate_tree_offset_42kg():
    """Verify 42 kg excess requires ceil(42 / 21) = 2 trees."""
    res = calculate_tree_offset(42)
    assert res["status"] == "success"
    assert res["trees_needed"] == 2
    assert res["kg_per_tree_per_year"] == 21.0
    assert len(res["timeline_options"]) == 3


def test_calculate_tree_offset_21kg():
    """Verify 21 kg excess requires ceil(21 / 21) = 1 tree."""
    res = calculate_tree_offset(21)
    assert res["status"] == "success"
    assert res["trees_needed"] == 1


def test_calculate_tree_offset_zero():
    """Verify 0 excess requires 0 trees."""
    res = calculate_tree_offset(0)
    assert res["status"] == "success"
    assert res["trees_needed"] == 0


def test_calculate_tree_offset_negative():
    """Verify negative excess returns error."""
    res = calculate_tree_offset(-10)
    assert res["status"] == "error"


# --- 5. Alternatives Recommendation Tests ---

def test_suggest_alternative_car_12km():
    """Verify 12 km car returns metro/bus/carpool with positive savings and sorted."""
    res = suggest_alternative("travel", "car_petrol", 12)
    assert res["status"] == "success"
    assert not res["already_optimal"]
    alts = res["alternatives"]
    assert len(alts) > 0
    # Check that savings are positive and in descending order
    for a in alts:
        assert a["saving_kg"] > 0
        assert a["saving_percent"] > 0
        assert a["ease"] in ("Easy", "Medium", "Needs planning")
    for i in range(len(alts) - 1):
        assert alts[i]["saving_kg"] >= alts[i + 1]["saving_kg"]


def test_suggest_alternative_walk_optimal():
    """Verify walking returns already optimal praise."""
    res = suggest_alternative("travel", "walk", 1.5)
    assert res["status"] == "success"
    assert res["already_optimal"] is True
    assert "lowest carbon" in res["message"]


def test_suggest_alternative_ac():
    """Verify AC alternatives include thermostat, fan+ac, and 5-star upgrade."""
    res = suggest_alternative("appliance", "ac", 4)
    assert res["status"] == "success"
    alts = res["alternatives"]
    names = [a["name"] for a in alts]
    assert any("24-26°C" in n for n in names)
    assert any("Fan" in n for n in names)


def test_suggest_alternative_mutton():
    """Verify mutton alternatives include veg, egg, chicken."""
    res = suggest_alternative("food", "mutton", 1)
    assert res["status"] == "success"
    modes = [a["mode"] for a in res["alternatives"]]
    assert "veg" in modes
    assert "chicken" in modes


# --- 6. Persistence & Budget Calculation Tests ---

def test_storage_and_budget_thresholds():
    """Verify SQLite persistence and budget warning (80%+) and exceeded (>100%) status."""
    tf = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    test_db = tf.name
    tf.close()

    try:
        init_db(test_db)
        user = "test_user_budget"

        # Set budget: monthly 100 kg, six-month 600 kg
        set_user_budget(100.0, 600.0, user_id=user, db_path=test_db)
        b = get_user_budget(user_id=user, db_path=test_db)
        assert b["monthly_kg"] == 100.0
        assert b["six_month_kg"] == 600.0

        # State 1: < 80% (usage = 50 kg -> ok)
        save_activity("travel", "car 200 km", 50.0, user_id=user, db_path=test_db)
        status_ok = get_budget_status(user_id=user, db_path=test_db)
        assert status_ok["status"] == "ok"
        assert status_ok["monthly"]["status"] == "ok"
        assert status_ok["monthly"]["percent_used"] == 50.0

        # State 2: 80% to 100% (add 35 kg -> total 85 kg -> 85% warning)
        save_activity("travel", "flight 200 km", 35.0, user_id=user, db_path=test_db)
        status_warn = get_budget_status(user_id=user, db_path=test_db)
        assert status_warn["status"] == "warning"
        assert status_warn["monthly"]["status"] == "warning"
        assert status_warn["monthly"]["percent_used"] == 85.0
        assert status_warn["monthly"]["remaining_kg"] == 15.0

        # State 3: > 100% (add 16 kg -> total 101 kg -> 101% exceeded)
        save_activity("appliance", "ac running 15 hours", 16.0, user_id=user, db_path=test_db)
        status_exc = get_budget_status(user_id=user, db_path=test_db)
        assert status_exc["status"] == "exceeded"
        assert status_exc["monthly"]["status"] == "exceeded"
        assert status_exc["monthly"]["percent_used"] == 101.0
        assert status_exc["monthly"]["excess_kg"] == 1.0

        # Check summary calculation
        summary = get_summary_data("month", user_id=user, db_path=test_db)
        assert summary["total_kg_co2e"] == 101.0
        assert summary["activity_count"] == 3
        assert "travel" in summary["category_breakdown"]
        assert "appliance" in summary["category_breakdown"]

    finally:
        if os.path.exists(test_db):
            os.remove(test_db)


def test_campus_leaderboard():
    """Verify campus leaderboard ranks groups by average kg CO2e."""
    tf = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    test_db = tf.name
    tf.close()

    try:
        init_db(test_db)
        # 2 members in Hostel A
        record_user_group("user_a1", "hostel", "Hostel A", db_path=test_db)
        record_user_group("user_a2", "hostel", "Hostel A", db_path=test_db)
        save_activity("travel", "bus", 10.0, user_id="user_a1", db_path=test_db)
        save_activity("travel", "metro", 10.0, user_id="user_a2", db_path=test_db)
        # Total Hostel A = 20 kg for 2 users -> avg 10.0 kg

        # 1 member in Hostel B
        record_user_group("user_b1", "hostel", "Hostel B", db_path=test_db)
        save_activity("travel", "car", 30.0, user_id="user_b1", db_path=test_db)
        # Total Hostel B = 30 kg for 1 user -> avg 30.0 kg

        lb = get_leaderboard_data("hostel", db_path=test_db)
        assert len(lb) == 2
        assert lb[0]["group_name"] == "Hostel A"
        assert lb[0]["avg_kg_per_person"] == 10.0
        assert lb[1]["group_name"] == "Hostel B"
        assert lb[1]["avg_kg_per_person"] == 30.0
    finally:
        if os.path.exists(test_db):
            os.remove(test_db)


# --- 7. Tool Context Integration Tests ---

class MockToolContext:
    def __init__(self, user_id="test_ctx_user"):
        self.user_id = user_id
        self.state = {}


def test_log_activity_with_context():
    """Verify log_activity properly integrates with tool_context."""
    ctx = MockToolContext("ctx_user_42")
    res = log_activity("travel", "metro 15 km", 0.45, tool_context=ctx)
    assert res["status"] == "success"
    assert res["user_id"] == "ctx_user_42"
    assert ctx.state.get("user:logged_activities_count") == 1
    assert ctx.state.get("user:last_logged_activity")["details"] == "metro 15 km"
