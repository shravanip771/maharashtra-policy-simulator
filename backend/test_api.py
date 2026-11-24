"""
Offline API Test Suite for Maharashtra Policy Simulator Backend.
Verifies REST endpoints, schema serialization, deterministic authority, and secret protection.
"""

import json
import pytest
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
    assert data["metadata"]["cohort_size"] == 18
    assert data["metadata"]["simulation_steps"] == 2
    assert data["metadata"]["is_synthetic_poc"] is True

    # 2. Provenance verification
    prov = data["provenance_breakdown"]
    assert "district" in prov["grounded_reference_fields"]
    assert "initial_awareness" in prov["synthetic_behavioral_priors"]

    # 3. Aggregate metrics reconciliation (calculated over full 18-persona cohort)
    agg = data["aggregate_metrics"]
    assert agg["total_personas"] == 18
    assert agg["eligible_count"] + agg["ineligible_count"] == 18
    assert agg["eligible_count"] == 12
    assert agg["realized_uptake_count"] <= agg["eligible_count"]

    # 4. Step metrics
    steps = data["step_metrics"]
    assert len(steps) == 2
    assert steps[0]["step_number"] == 1
    assert steps[1]["step_number"] == 2
    assert steps[1]["mean_awareness"] >= steps[0]["mean_awareness"]

    # 5. Personas output (exactly 10 featured personas deterministically sampled)
    personas = data["personas"]
    assert len(personas) == 10
    assert len(data["featured_personas"]) == 10
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


def test_api_statutory_mode():
    """
    Verifies that POST /api/simulate with policy_mode='statutory' (and alias 'statutory_dte')
    evaluates statutory DTE rules, itemizes tuition vs exam fee relief,
    attaches provisional notes, and sets policy_version='2024.1-provisional'.
    """
    payload = {
        "district": "Dhule",
        "cohort_size": 10,
        "simulation_steps": 1,
        "seed": 42,
        "policy_mode": "statutory",
        "use_gemini": False
    }

    response = client.post("/api/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()

    meta = data["metadata"]
    assert meta["policy_mode"] == "statutory"
    assert meta["policy_version"] == "2024.1-provisional"
    assert meta["assumed_reimbursement_rate"] is None
    assert meta["is_provisional"] is True
    assert len(meta["provisional_notes"]) >= 3
    assert any("male candidates is provisional" in note.lower() for note in meta["provisional_notes"])

    agg = data["aggregate_metrics"]
    assert agg["policy_mode"] == "statutory"
    assert agg["policy_version"] == "2024.1-provisional"
    assert agg["is_provisional"] is True
    assert agg["total_estimated_fee_relief_inr"] >= 0.0

    personas = data["personas"]
    for p in personas:
        assert p["policy_version"] == "2024.1-provisional"
        assert p["is_provisional"] is True
        if p["is_statutorily_eligible"]:
            assert p["estimated_fee_relief_inr"] == round(p["tuition_fee_relief_inr"] + p["exam_fee_relief_inr"], 2)
        else:
            assert p["estimated_fee_relief_inr"] == 0.0
            assert p["tuition_fee_relief_inr"] == 0.0
            assert p["exam_fee_relief_inr"] == 0.0
            assert len(p["statutory_failure_reasons"]) > 0

    print("PASS: test_api_statutory_mode")


def test_api_override_mode_and_validation():
    """
    Verifies that POST /api/simulate with policy_mode='override'
    applies the explicit uniform override rate, and validates missing/invalid rates.
    """
    # 1. Valid override rate
    payload_valid = {
        "district": "Dhule",
        "cohort_size": 5,
        "simulation_steps": 1,
        "seed": 42,
        "policy_mode": "override",
        "override_reimbursement_rate": 0.75,
        "use_gemini": False
    }

    response = client.post("/api/simulate", json=payload_valid)
    assert response.status_code == 200
    data = response.json()
    assert data["metadata"]["policy_mode"] == "override"

    for p in data["personas"]:
        if p["is_statutorily_eligible"]:
            expected_relief = round(p["annual_tuition_fee"] * 0.75, 2)
            assert p["tuition_fee_relief_inr"] == expected_relief

    # 2. Invalid override: policy_mode='override' without override_reimbursement_rate -> 422
    payload_missing_rate = {
        "district": "Dhule",
        "cohort_size": 5,
        "simulation_steps": 1,
        "seed": 42,
        "policy_mode": "override",
        "use_gemini": False
    }
    res_err = client.post("/api/simulate", json=payload_missing_rate)
    assert res_err.status_code == 422
    assert "override_reimbursement_rate must be provided" in res_err.json()["detail"]

    # 3. Invalid override: policy_mode='statutory' with override_reimbursement_rate -> 422
    payload_conflict = {
        "district": "Dhule",
        "cohort_size": 5,
        "simulation_steps": 1,
        "seed": 42,
        "policy_mode": "statutory",
        "override_reimbursement_rate": 0.75,
        "use_gemini": False
    }
    res_conflict = client.post("/api/simulate", json=payload_conflict)
    assert res_conflict.status_code == 422
    assert "cannot be specified in 'statutory' mode" in res_conflict.json()["detail"]

    print("PASS: test_api_override_mode_and_validation")


def test_api_counterfactual_mode():
    """
    Verifies that POST /api/simulate with policy_mode='counterfactual'
    applies custom what-if reform parameters (e.g. 10 Lakh income cap).
    """
    payload = {
        "district": "Dhule",
        "cohort_size": 10,
        "simulation_steps": 1,
        "seed": 42,
        "policy_mode": "counterfactual",
        "counterfactual_params": {
            "max_income_limit": 1000000.0,
            "female_tuition_rate": 1.00,
            "male_tier2_tuition_rate": 0.75,
            "policy_label": "Income-10L-Reform"
        },
        "use_gemini": False
    }

    response = client.post("/api/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["metadata"]["policy_mode"] == "counterfactual"
    assert "counterfactual" in data["metadata"]["policy_version"]
    assert data["aggregate_metrics"]["policy_mode"] == "counterfactual"
    print("PASS: test_api_counterfactual_mode")


def test_api_legacy_poc_backward_compatibility():
    """
    Verifies backward compatibility: requests omitting policy_mode default
    to legacy_poc (50% flat rate) and retain historical behavior.
    """
    payload_omitted = {
        "district": "Dhule",
        "cohort_size": 5,
        "simulation_steps": 1,
        "seed": 42,
        "use_gemini": False
    }

    response = client.post("/api/simulate", json=payload_omitted)
    assert response.status_code == 200
    data = response.json()

    assert data["metadata"]["policy_mode"] == "legacy_poc"
    assert data["aggregate_metrics"]["policy_mode"] == "legacy_poc"

    for p in data["personas"]:
        if p["is_statutorily_eligible"]:
            expected_50 = round(p["annual_tuition_fee"] * 0.50, 2)
            assert p["tuition_fee_relief_inr"] == expected_50

    print("PASS: test_api_legacy_poc_backward_compatibility")


def test_api_override_mode_rejects_boolean_rate():
    """Verifies that POST /api/simulate rejects boolean override_reimbursement_rate with 422."""
    payload = {
        "district": "Dhule",
        "cohort_size": 5,
        "simulation_steps": 1,
        "seed": 42,
        "policy_mode": "override",
        "override_reimbursement_rate": True,
        "use_gemini": False
    }
    response = client.post("/api/simulate", json=payload)
    assert response.status_code == 422
    assert "boolean" in response.text.lower()
    print("PASS: test_api_override_mode_rejects_boolean_rate")


def test_api_counterfactual_conflicting_inputs_rejected():
    """Verifies that providing both counterfactual_params and counterfactual_config returns 422."""
    payload = {
        "district": "Dhule",
        "cohort_size": 5,
        "simulation_steps": 1,
        "seed": 42,
        "policy_mode": "counterfactual",
        "counterfactual_params": {
            "max_income_limit": 1000000.0
        },
        "counterfactual_config": {
            "max_income_limit": 1000000.0
        },
        "use_gemini": False
    }
    response = client.post("/api/simulate", json=payload)
    assert response.status_code == 422
    assert "Cannot supply both" in response.text
    print("PASS: test_api_counterfactual_conflicting_inputs_rejected")


def test_api_counterfactual_dict_config_and_validation():
    """Verifies that raw dict counterfactual_config works and validates inputs with 422 on bad data."""
    # 1. Valid raw dict counterfactual_config
    payload_valid = {
        "district": "Dhule",
        "cohort_size": 5,
        "simulation_steps": 1,
        "seed": 42,
        "policy_mode": "counterfactual",
        "counterfactual_config": {
            "max_income_limit": 1200000.0,
            "male_exam_rate": 0.60
        },
        "use_gemini": False
    }
    res_ok = client.post("/api/simulate", json=payload_valid)
    assert res_ok.status_code == 200
    data = res_ok.json()
    assert data["metadata"]["policy_mode"] == "counterfactual"
    assert data["metadata"]["assumed_reimbursement_rate"] is None
    assert data["metadata"]["is_provisional"] is True

    # 2. Invalid dict counterfactual_config (out-of-range rate)
    payload_invalid = {
        "district": "Dhule",
        "cohort_size": 5,
        "simulation_steps": 1,
        "seed": 42,
        "policy_mode": "counterfactual",
        "counterfactual_config": {
            "min_attendance_percent": 150.0
        },
        "use_gemini": False
    }
    res_err = client.post("/api/simulate", json=payload_invalid)
    assert res_err.status_code == 422
    assert "min_attendance_percent must be between 0.0 and 100.0" in res_err.json()["detail"]

    # 3. Boolean in dict counterfactual_config
    payload_bool = {
        "district": "Dhule",
        "cohort_size": 5,
        "simulation_steps": 1,
        "seed": 42,
        "policy_mode": "counterfactual",
        "counterfactual_config": {
            "female_tuition_rate": True
        },
        "use_gemini": False
    }
    res_bool = client.post("/api/simulate", json=payload_bool)
    assert res_bool.status_code == 422
    assert "boolean" in res_bool.text.lower()
    print("PASS: test_api_counterfactual_dict_config_and_validation")


def test_api_policy_modes_metadata_and_assumed_rate_behavior():
    """Verifies metadata, nullable assumed rate, and provisional scoping across all 4 modes."""
    # Statutory
    res_stat = client.post("/api/simulate", json={
        "district": "Dhule", "cohort_size": 3, "simulation_steps": 1,
        "policy_mode": "statutory", "use_gemini": False
    })
    assert res_stat.status_code == 200
    data_stat = res_stat.json()
    assert data_stat["metadata"]["assumed_reimbursement_rate"] is None
    assert data_stat["metadata"]["is_provisional"] is True
    assert len(data_stat["metadata"]["provisional_notes"]) >= 3
    assert data_stat["aggregate_metrics"]["is_provisional"] is True

    # Counterfactual
    res_cf = client.post("/api/simulate", json={
        "district": "Dhule", "cohort_size": 3, "simulation_steps": 1,
        "policy_mode": "counterfactual",
        "counterfactual_config": {"max_income_limit": 900000.0},
        "use_gemini": False
    })
    assert res_cf.status_code == 200
    data_cf = res_cf.json()
    assert data_cf["metadata"]["assumed_reimbursement_rate"] is None
    assert data_cf["metadata"]["is_provisional"] is True
    assert len(data_cf["metadata"]["provisional_notes"]) >= 3

    # Legacy PoC
    res_poc = client.post("/api/simulate", json={
        "district": "Dhule", "cohort_size": 3, "simulation_steps": 1,
        "policy_mode": "legacy_poc", "use_gemini": False
    })
    assert res_poc.status_code == 200
    data_poc = res_poc.json()
    assert data_poc["metadata"]["assumed_reimbursement_rate"] == 0.50
    assert data_poc["metadata"]["is_provisional"] is False
    assert len(data_poc["metadata"]["provisional_notes"]) == 0
    assert data_poc["aggregate_metrics"]["is_provisional"] is False

    # Override
    res_ov = client.post("/api/simulate", json={
        "district": "Dhule", "cohort_size": 3, "simulation_steps": 1,
        "policy_mode": "override", "override_reimbursement_rate": 0.65,
        "use_gemini": False
    })
    assert res_ov.status_code == 200
    data_ov = res_ov.json()
    assert data_ov["metadata"]["assumed_reimbursement_rate"] == 0.65
    assert data_ov["metadata"]["is_provisional"] is False
    assert len(data_ov["metadata"]["provisional_notes"]) == 0
    assert data_ov["aggregate_metrics"]["is_provisional"] is False
    print("PASS: test_api_policy_modes_metadata_and_assumed_rate_behavior")


def test_api_override_mode_zero_rate_preserves_zero_in_metadata():
    """F-01: Verifies that POST /api/simulate with policy_mode='override' and assumed_reimbursement_rate=0.0 returns exactly 0.0."""
    payload = {
        "district": "Dhule",
        "cohort_size": 3,
        "simulation_steps": 1,
        "seed": 42,
        "policy_mode": "override",
        "assumed_reimbursement_rate": 0.0,
        "use_gemini": False
    }
    response = client.post("/api/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["metadata"]["policy_mode"] == "override"
    assert data["metadata"]["assumed_reimbursement_rate"] == 0.0
    assert data["metadata"]["assumed_reimbursement_rate"] is not None
    assert data["metadata"]["assumed_reimbursement_rate"] != 0.50
    for p in data["personas"]:
        assert p["tuition_fee_relief_inr"] == 0.0
        assert p["estimated_fee_relief_inr"] == 0.0
    print("PASS: test_api_override_mode_zero_rate_preserves_zero_in_metadata")


def test_api_reimbursement_rate_conflict_and_exact_equality_validation():
    """
    Verifies that SimulationRequest rejects conflicting values when both
    override_reimbursement_rate and assumed_reimbursement_rate are supplied,
    while permitting identical values, 0.0, and single fields.
    """
    # 1. Conflicting positive rates -> Model raises ValueError, API returns 422
    with pytest.raises(ValueError, match="cannot differ"):
        SimulationRequest(
            district="Dhule",
            cohort_size=2,
            simulation_steps=1,
            policy_mode="override",
            override_reimbursement_rate=0.80,
            assumed_reimbursement_rate=0.60
        )
    res_conflict = client.post("/api/simulate", json={
        "district": "Dhule", "cohort_size": 2, "simulation_steps": 1,
        "policy_mode": "override",
        "override_reimbursement_rate": 0.80,
        "assumed_reimbursement_rate": 0.60,
        "use_gemini": False
    })
    assert res_conflict.status_code == 422
    assert "cannot differ" in res_conflict.text

    # 2. 0.0 versus a positive rate -> Model raises ValueError, API returns 422
    with pytest.raises(ValueError, match="cannot differ"):
        SimulationRequest(
            district="Dhule",
            cohort_size=2,
            simulation_steps=1,
            policy_mode="override",
            override_reimbursement_rate=0.0,
            assumed_reimbursement_rate=0.75
        )
    res_zero_pos = client.post("/api/simulate", json={
        "district": "Dhule", "cohort_size": 2, "simulation_steps": 1,
        "policy_mode": "override",
        "override_reimbursement_rate": 0.0,
        "assumed_reimbursement_rate": 0.75,
        "use_gemini": False
    })
    assert res_zero_pos.status_code == 422
    assert "cannot differ" in res_zero_pos.text

    # 3. Identical positive rates -> Valid, API returns 200 with matching rate
    req_ident = SimulationRequest(
        district="Dhule",
        cohort_size=2,
        simulation_steps=1,
        policy_mode="override",
        override_reimbursement_rate=0.75,
        assumed_reimbursement_rate=0.75
    )
    assert req_ident.override_reimbursement_rate == 0.75
    assert req_ident.assumed_reimbursement_rate == 0.75
    res_ident = client.post("/api/simulate", json={
        "district": "Dhule", "cohort_size": 2, "simulation_steps": 1,
        "policy_mode": "override",
        "override_reimbursement_rate": 0.75,
        "assumed_reimbursement_rate": 0.75,
        "use_gemini": False
    })
    assert res_ident.status_code == 200
    assert res_ident.json()["metadata"]["assumed_reimbursement_rate"] == 0.75

    # 4. Both rates set to 0.0 -> Valid, API returns 200 with 0.0 preserved
    req_zero_both = SimulationRequest(
        district="Dhule",
        cohort_size=2,
        simulation_steps=1,
        policy_mode="override",
        override_reimbursement_rate=0.0,
        assumed_reimbursement_rate=0.0
    )
    assert req_zero_both.override_reimbursement_rate == 0.0
    assert req_zero_both.assumed_reimbursement_rate == 0.0
    res_zero_both = client.post("/api/simulate", json={
        "district": "Dhule", "cohort_size": 2, "simulation_steps": 1,
        "policy_mode": "override",
        "override_reimbursement_rate": 0.0,
        "assumed_reimbursement_rate": 0.0,
        "use_gemini": False
    })
    assert res_zero_both.status_code == 200
    assert res_zero_both.json()["metadata"]["assumed_reimbursement_rate"] == 0.0

    # 5. Only override_reimbursement_rate -> Valid, API returns 200
    req_only_ov = SimulationRequest(
        district="Dhule",
        cohort_size=2,
        simulation_steps=1,
        policy_mode="override",
        override_reimbursement_rate=0.65
    )
    assert req_only_ov.override_reimbursement_rate == 0.65
    assert req_only_ov.assumed_reimbursement_rate is None
    res_only_ov = client.post("/api/simulate", json={
        "district": "Dhule", "cohort_size": 2, "simulation_steps": 1,
        "policy_mode": "override",
        "override_reimbursement_rate": 0.65,
        "use_gemini": False
    })
    assert res_only_ov.status_code == 200
    assert res_only_ov.json()["metadata"]["assumed_reimbursement_rate"] == 0.65

    # 6. Only assumed_reimbursement_rate -> Valid, API returns 200
    req_only_ar = SimulationRequest(
        district="Dhule",
        cohort_size=2,
        simulation_steps=1,
        policy_mode="override",
        assumed_reimbursement_rate=0.65
    )
    assert req_only_ar.override_reimbursement_rate is None
    assert req_only_ar.assumed_reimbursement_rate == 0.65
    res_only_ar = client.post("/api/simulate", json={
        "district": "Dhule", "cohort_size": 2, "simulation_steps": 1,
        "policy_mode": "override",
        "assumed_reimbursement_rate": 0.65,
        "use_gemini": False
    })
    assert res_only_ar.status_code == 200
    assert res_only_ar.json()["metadata"]["assumed_reimbursement_rate"] == 0.65
    print("PASS: test_api_reimbursement_rate_conflict_and_exact_equality_validation")


if __name__ == "__main__":
    test_api_health_endpoint()
    test_api_schemes_and_districts_endpoints()
    test_api_simulate_contract_and_reconciliation()
    test_api_no_secrets_exposed()
    test_api_statutory_mode()
    test_api_override_mode_and_validation()
    test_api_counterfactual_mode()
    test_api_legacy_poc_backward_compatibility()
    test_api_override_mode_rejects_boolean_rate()
    test_api_counterfactual_conflicting_inputs_rejected()
    test_api_counterfactual_dict_config_and_validation()
    test_api_policy_modes_metadata_and_assumed_rate_behavior()
    test_api_override_mode_zero_rate_preserves_zero_in_metadata()
    test_api_reimbursement_rate_conflict_and_exact_equality_validation()
    print("All backend API tests passed successfully!")
