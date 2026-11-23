"""
Offline API Test Suite for Maharashtra Policy Simulator Backend.
Verifies REST endpoints, schema serialization, deterministic authority, and secret protection.
"""

import json
import os
import sys

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

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
    assert agg["eligible_count"] == 4
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


def test_api_simulate_invalid_district():
    """Verifies that POST /api/simulate with an invalid district returns HTTP 400 with helpful detail."""
    payload = {
        "district": "NonExistentDistrict999",
        "cohort_size": 3,
        "simulation_steps": 1,
        "seed": 42,
        "use_gemini": False
    }

    response = client.post("/api/simulate", json=payload)
    assert response.status_code == 400, f"Expected HTTP 400, got {response.status_code}: {response.text}"
    data = response.json()
    detail = data.get("detail", "")
    assert "NonExistentDistrict999" in detail, f"Expected invalid district in detail: {detail}"
    assert "Supported districts" in detail, f"Expected supported districts in detail: {detail}"
    print("PASS: test_api_simulate_invalid_district")


def test_api_simulate_statewide():
    """
    Verifies that POST /api/simulate with district='STATEWIDE' executes a composite
    multi-step simulation across all 36 districts, returning 180 personas, statewide
    aggregates, and reconciled district summaries.
    """
    payload = {
        "district": "STATEWIDE",
        "cohort_size_per_district": 5,
        "simulation_steps": 2,
        "seed": 42,
        "use_gemini": False
    }

    response = client.post("/api/simulate", json=payload)
    assert response.status_code == 200, f"Expected HTTP 200, got {response.status_code}: {response.text}"
    data = response.json()

    # 1. Statewide metadata verification
    assert data["is_statewide"] is True
    assert data["metadata"]["district"] == "Maharashtra (Statewide)"
    assert data["metadata"]["cohort_size"] == 180
    assert data["metadata"]["epistemic_status"] == "statewide_composite"
    assert "36 Maharashtra districts" in data["metadata"]["data_disclaimer"]

    # 2. Personas verification across all 36 districts
    personas = data["personas"]
    assert len(personas) == 180
    districts_present = {p["district"] for p in personas}
    assert len(districts_present) == 36, f"Expected 36 districts in personas, got {len(districts_present)}"
    for p in personas:
        assert p["taluka"] is not None and len(p["taluka"]) > 0

    # 3. District summaries verification
    summaries = data["district_summaries"]
    assert summaries is not None
    assert len(summaries) == 36, f"Expected 36 district summaries, got {len(summaries)}"

    # 4. Strict reconciliation between district slices and statewide totals
    agg = data["aggregate_metrics"]
    sum_total_personas = sum(d["total_personas"] for d in summaries.values())
    sum_eligible = sum(d["eligible_count"] for d in summaries.values())
    sum_ineligible = sum(d["ineligible_count"] for d in summaries.values())
    sum_uptake = sum(d["realized_uptake_count"] for d in summaries.values())
    sum_relief = round(sum(d["total_estimated_fee_relief_inr"] for d in summaries.values()), 2)

    assert sum_total_personas == 180
    assert sum_total_personas == agg["total_personas"]
    assert sum_eligible == agg["eligible_count"]
    assert sum_ineligible == agg["ineligible_count"]
    assert sum_uptake == agg["realized_uptake_count"]
    assert abs(sum_relief - agg["total_estimated_fee_relief_inr"]) < 0.05, (
        f"Relief discrepancy: sum={sum_relief} vs agg={agg['total_estimated_fee_relief_inr']}"
    )

    # Specific district check (e.g., Pune, Dhule)
    assert "Pune" in summaries
    assert summaries["Pune"]["total_personas"] == 5
    assert len(summaries["Pune"]["talukas_represented"]) >= 1

    assert "Dhule" in summaries
    assert summaries["Dhule"]["total_personas"] == 5
    assert summaries["Dhule"]["provenance_tier"] == "empirical_observed"
    print("PASS: test_api_simulate_statewide")


def test_api_simulate_statewide_rejects_gemini():
    """
    Verifies that requests combining statewide mode with use_gemini=True are explicitly
    rejected with a clear validation error, without silently falling back to offline mode.
    Also verifies single-district Gemini mode is not rejected by this guard.
    """
    from backend.service import SimulationService

    # 1. Direct service layer rejection
    for alias in ["STATEWIDE", "ALL", "MAHARASHTRA"]:
        req = SimulationRequest(district=alias, use_gemini=True)
        try:
            SimulationService.execute_simulation(req)
            assert False, f"Expected ValueError for statewide Gemini request with district='{alias}'"
        except ValueError as exc:
            err_msg = str(exc)
            assert "restricted to single-district" in err_msg, f"Unexpected error message: {err_msg}"
            assert "offline mode" in err_msg, f"Unexpected error message: {err_msg}"

    # 2. HTTP API endpoint rejection
    payload = {
        "district": "STATEWIDE",
        "cohort_size_per_district": 5,
        "simulation_steps": 1,
        "seed": 42,
        "use_gemini": True
    }
    response = client.post("/api/simulate", json=payload)
    assert response.status_code != 200, f"Expected error response, got {response.status_code}"
    data = response.json()
    detail = data.get("detail", "")
    assert "restricted to single-district" in detail, f"Expected rejection detail, got: {detail}"

    # 3. Verify single-district requests with use_gemini=True are NOT rejected by this guard
    req_single = SimulationRequest(district="Dhule", cohort_size=3, simulation_steps=1, seed=42, use_gemini=True)
    resp_single = SimulationService.execute_simulation(req_single)
    assert resp_single.metadata.district == "Dhule"
    assert resp_single.is_statewide is False

    print("PASS: test_api_simulate_statewide_rejects_gemini")


if __name__ == "__main__":
    test_api_health_endpoint()
    test_api_schemes_and_districts_endpoints()
    test_api_simulate_contract_and_reconciliation()
    test_api_no_secrets_exposed()
    test_api_simulate_invalid_district()
    test_api_simulate_statewide()
    test_api_simulate_statewide_rejects_gemini()
    print("All backend API tests passed successfully!")
