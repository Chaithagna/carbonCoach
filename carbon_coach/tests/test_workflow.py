"""End-to-end integration and user workflow tests for Carbon Coach.

Validates that all conversational flows, tool executions, budget alerts,
tree offset calculations, and multilingual inputs adhere strictly to
CARBON_COACH_SPEC.md requirements.
"""

import pytest
from fastapi.testclient import TestClient
from server import app
from carbon_coach.storage import init_db

client = TestClient(app)


def setup_module(module):
    """Ensure database is initialized before workflow tests."""
    init_db()


def test_api_factors_verification():
    """Verify official emission factors are served with proper units and values."""
    response = client.get("/api/factors")
    assert response.status_code == 200
    data = response.json()
    assert data["grid_kg_per_kwh"] == 0.71
    assert data["travel_kg_per_km"]["bus"] == 0.089
    assert data["travel_kg_per_km"]["metro"] == 0.030
    assert data["appliance_kw"]["ac"] == 1.5
    assert data["food_kg_per_meal"]["mutton"] == 5.5
    assert data["waste_kg_per_kg"]["plastic"] == 2.0
    assert data["tree_kg_per_year"] == 21.0


def test_workflow_example_conversation_car_and_ac():
    """Verify Section 6 example conversation:
    User: 'I travelled 12 km by car and used the AC for 4 hours.'
    """
    response = client.post("/api/chat", json={
        "message": "I travelled 12 km by car and used the AC for 4 hours."
    })
    assert response.status_code == 200
    data = response.json()

    # Verify tool results exist
    tools_called = [t["tool"] for t in data["tool_results"]]
    assert "calculate_travel_emissions" in tools_called
    assert "calculate_appliance_emissions" in tools_called
    assert "log_activity" in tools_called
    assert "suggest_alternative" in tools_called
    assert "check_carbon_budget" in tools_called

    # Check exact figures in reply
    # car 12 km = 12 * 0.17 = 2.04 kg
    # AC 4 hours = 4 * 1.5 * 0.71 = 4.26 kg
    # Total = 6.3 kg
    reply = data["reply"]
    assert "2.04 kg" in reply
    assert "4.26 kg" in reply
    assert "6.3 kg" in reply

    # Alternatives must be realistic and have savings + ease
    assert len(data["alternatives"]) > 0
    alt_text = reply.lower()
    assert "save" in alt_text
    assert ("easy" in alt_text or "medium" in alt_text)


def test_workflow_missing_distance_question():
    """Verify agent asks ONE short question when distance is missing without guessing."""
    response = client.post("/api/chat", json={
        "message": "I took a taxi to the campus today."
    })
    assert response.status_code == 200
    data = response.json()
    reply = data["reply"].lower()
    # Must ask for kilometers
    assert "kilometer" in reply or "km" in reply or "?" in reply
    # Must NOT call calculate tools with invented numbers
    tools_called = [t["tool"] for t in data["tool_results"]]
    assert "calculate_travel_emissions" not in tools_called


def test_workflow_budget_exceeded_and_tree_offset():
    """Verify budget exceeded flow triggers tree offset plan and 2 reduction actions."""
    # First, configure a low monthly budget to test exceeded threshold
    client.post("/api/budget", json={
        "monthly_kg": 20.0,
        "six_month_kg": 120.0
    })

    # Log an activity that exceeds 20 kg (e.g. 200 km by petrol car = 34 kg)
    response = client.post("/api/chat", json={
        "message": "I travelled 200 km by petrol car today."
    })
    assert response.status_code == 200
    data = response.json()

    # Must contain calculate_tree_offset
    tools_called = [t["tool"] for t in data["tool_results"]]
    assert "calculate_tree_offset" in tools_called

    reply = data["reply"]
    # Must clearly say limit crossed
    assert "crossed your monthly carbon limit" in reply or "exceeded" in reply.lower()
    # Must contain tree calculation (e.g. 21 kg CO2 per tree per year)
    assert "21 kg co2 per tree per year" in reply.lower()
    assert "tree" in reply.lower()
    # Must give concrete reduction actions
    assert "transit" in reply.lower() or "ac" in reply.lower() or "metro" in reply.lower()


def test_workflow_summary_query():
    """Verify 'how did I do' query calls get_summary."""
    response = client.post("/api/chat", json={
        "message": "How did I do this month?"
    })
    assert response.status_code == 200
    data = response.json()
    tools_called = [t["tool"] for t in data["tool_results"]]
    assert "get_summary" in tools_called
    assert "total emissions are" in data["reply"].lower()


def test_workflow_multilingual_hindi():
    """Verify Hindi input returns response in Hindi with verified tool numbers."""
    response = client.post("/api/chat", json={
        "message": "आज मैंने 10 किमी बस की यात्रा की।"
    })
    assert response.status_code == 200
    data = response.json()
    # 10 km bus = 0.89 kg
    tools_called = [t["tool"] for t in data["tool_results"]]
    assert "calculate_travel_emissions" in tools_called
    # Hindi response check
    assert "दर्ज किया गया" in data["reply"] or "किग्रा" in data["reply"]
    assert "0.89" in data["reply"]


def test_workflow_multilingual_telugu():
    """Verify Telugu input returns response in Telugu with verified tool numbers."""
    response = client.post("/api/chat", json={
        "message": "నేను ఈరోజు 15 కిలోమీటర్లు మెట్రోలో ప్రయాణించాను."
    })
    assert response.status_code == 200
    data = response.json()
    # 15 km metro = 0.45 kg
    tools_called = [t["tool"] for t in data["tool_results"]]
    assert "calculate_travel_emissions" in tools_called
    assert "నమోదు చేయబడింది" in data["reply"] or "కిలోల" in data["reply"]
    assert "0.45" in data["reply"]
