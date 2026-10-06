"""
Offline API Test Suite for Maharashtra Policy Simulator Backend.
Verifies REST endpoints, schema serialization, deterministic authority, and secret protection.
"""

import json
from fastapi.testclient import TestClient

from backend.main import app
from backend.models import SimulationRequest, SimulationResponse

client = TestClient(app)


def test_api_health_endpoint():
    """Verifies that GET /api/health returns 200 OK and valid metadata."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "Rajarshi Chhatrapati Shahu Maharaj" in data["active_policy"]
    assert data["active_district"] == "Dhule"
    print("PASS: test_api_health_endpoint")


def test_api_schemes_and_districts_endpoints():
    """Verifies that GET /api/schemes and GET /api/districts return grounded metadata."""
    res_schemes = client.get("/api/schemes")
    assert res_schemes.status_code == 200
    schemes = res_schemes.json()
    assert len(schemes) >= 1
    assert schemes[0]["scheme_code"] == "RCSMS-EBC"
    assert schemes[0]["income_ceiling_inr"] == 800000.0

    res_districts = client.get("/api/districts")
    assert res_districts.status_code == 200
    districts = res_districts.json()
    assert len(districts) >= 1
    assert districts[0]["district_name"] == "Dhule"
    assert "Shirpur" in districts[0]["talukas"]
    print("PASS: test_api_schemes_and_districts_endpoints")


def test_api_simulate_contract_and_reconciliation():
    """
    Verifies that POST /api/simulate executes an offline multi-step run and returns
    a fully populated response adhering strictly to the Phase A Data Contract.
    """
    payload = {
        "district": "Dhule",
        "cohort_size": 10,
        "simulation_steps": 2,
        "seed": 42,
        "use_gemini": False
    }

    response = client.post("/api/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()

    # 1. Metadata verification
    assert data["metadata"]["district"] == "Dhule"
    assert data["metadata"]["cohort_size"] == 10
    assert data["metadata"]["simulation_steps"] == 2
    assert data["metadata"]["is_synthetic_poc"] is True

    # 2. Provenance verification
    prov = data["provenance_breakdown"]
    assert "district" in prov["grounded_reference_fields"]
    assert "initial_awareness" in prov["synthetic_behavioral_priors"]

    # 3. Aggregate metrics reconciliation
    agg = data["aggregate_metrics"]
    assert agg["total_personas"] == 10
    assert agg["eligible_count"] + agg["ineligible_count"] == 10
    assert agg["eligible_count"] == 7
    assert agg["realized_uptake_count"] <= agg["eligible_count"]

    # 4. Step metrics
    steps = data["step_metrics"]
    assert len(steps) == 2
    assert steps[0]["step_number"] == 1
    assert steps[1]["step_number"] == 2
    assert steps[1]["mean_awareness"] >= steps[0]["mean_awareness"]

    # 5. Personas output
    personas = data["personas"]
    assert len(personas) == 10
    for p in personas:
        assert p["persona_id"].startswith("DHULE-STU-")
        assert 0.0 <= p["initial_awareness"] <= 1.0
        assert 0.0 <= p["final_awareness"] <= 1.0
        assert 0.0 <= p["initial_trust"] <= 1.0
        assert 0.0 <= p["final_trust"] <= 1.0
        assert p["final_state"] in ["BENEFIT_RECEIVED", "EVALUATING", "REJECTED", "DROPPED_OUT", "APPLICATION_SUBMITTED"]

        # Deterministic statutory authority
        if not p["is_statutorily_eligible"]:
            assert p["estimated_fee_relief_inr"] == 0.0
            assert p["final_state"] == "REJECTED"

    # 6. Interaction records
    interactions = data["interactions"]
    assert len(interactions) >= 1
    for inter in interactions:
        assert inter["simulation_step"] in [1, 2]
        assert inter["sender_id"].startswith("DHULE-STU-")
        assert inter["receiver_id"].startswith("DHULE-STU-")
        assert len(inter["sender_message"]) > 0
        assert len(inter["receiver_response"]) > 0

    print("PASS: test_api_simulate_contract_and_reconciliation")


def test_api_no_secrets_exposed():
    """Verifies that no API keys or environment secrets are exposed in API payloads."""
    payload = {
        "district": "Dhule",
        "cohort_size": 3,
        "simulation_steps": 1,
        "seed": 42,
        "use_gemini": False
    }

    response = client.post("/api/simulate", json=payload)
    assert response.status_code == 200
    raw_text = response.text

    assert "GEMINI_API_KEY" not in raw_text
    assert "AIzaSy" not in raw_text  # Common prefix pattern for Google API keys
    assert "api_key" not in raw_text.lower()
    print("PASS: test_api_no_secrets_exposed")


if __name__ == "__main__":
    test_api_health_endpoint()
    test_api_schemes_and_districts_endpoints()
    test_api_simulate_contract_and_reconciliation()
    test_api_no_secrets_exposed()
    print("All backend API tests passed successfully!")
