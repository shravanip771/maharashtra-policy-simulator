"""
Multi-District Policy Simulation Test Suite.
Validates district expansion from Dhule-only to all 36 Maharashtra districts.
Tests registry completeness, API discovery, invalid district validation (HTTP 422),
and demographic differentiation across all six administrative divisions.
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models import SimulationRequest
from backend.service import SimulationService
from simulation.district_config import (
    list_supported_districts,
    get_district_profile,
    get_district_population_config,
    DISTRICT_REGISTRY
)

client = TestClient(app)

EXPECTED_DIVISIONS = {
    "Konkan": ["Mumbai City", "Mumbai Suburban", "Thane", "Palghar", "Raigad", "Ratnagiri", "Sindhudurg"],
    "Pune": ["Pune", "Kolhapur", "Sangli", "Satara", "Solapur"],
    "Nashik": ["Nashik", "Dhule", "Nandurbar", "Jalgaon", "Ahilyanagar"],
    "Chhatrapati Sambhajinagar": [
        "Chhatrapati Sambhajinagar", "Jalna", "Beed", "Parbhani",
        "Hingoli", "Nanded", "Latur", "Dharashiv"
    ],
    "Amravati": ["Amravati", "Akola", "Buldhana", "Washim", "Yavatmal"],
    "Nagpur": ["Nagpur", "Wardha", "Bhandara", "Gondia", "Chandrapur", "Gadchiroli"]
}


# ==============================================================================
# 1. District Registry & Configuration Integrity Tests
# ==============================================================================

def test_registry_contains_all_36_districts():
    """Verifies that list_supported_districts() returns exactly 36 distinct Maharashtra districts."""
    districts = list_supported_districts()
    assert len(districts) == 36
    assert len(set(districts)) == 36
    assert "Dhule" in districts
    assert "Mumbai City" in districts
    assert "Pune" in districts
    assert "Nagpur" in districts
    assert "Gadchiroli" in districts


def test_registry_covers_all_six_administrative_divisions():
    """Verifies that all 36 districts map to one of the 6 official administrative divisions."""
    found_divisions = set()
    total_counted = 0

    for div, expected_districts in EXPECTED_DIVISIONS.items():
        found_divisions.add(div)
        for dist_name in expected_districts:
            prof = get_district_profile(dist_name)
            assert prof is not None
            assert prof.district_name == dist_name
            assert prof.division == div
            assert len(prof.talukas) >= 1
            total_counted += 1

    assert found_divisions == set(EXPECTED_DIVISIONS.keys())
    assert total_counted == 36


def test_district_provenance_tiers():
    """Verifies empirical pilot labeling for Dhule/Mumbai City and provisional baseline for others."""
    dhule = get_district_profile("Dhule")
    mumbai = get_district_profile("Mumbai City")
    pune = get_district_profile("Pune")
    gadchiroli = get_district_profile("Gadchiroli")

    assert dhule.provenance_tier == "empirical_observed"
    assert mumbai.provenance_tier == "empirical_observed"
    assert pune.provenance_tier == "provisional_baseline"
    assert gadchiroli.provenance_tier == "provisional_baseline"


# ==============================================================================
# 2. REST API Discovery & Health Endpoint Tests
# ==============================================================================

def test_api_health_endpoint_reports_all_36_districts():
    """Verifies that GET /api/health exposes the 36-district list and count."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["active_district"] == "Dhule"
    assert data["total_supported_districts"] == 36
    assert len(data["supported_districts"]) == 36
    assert "Pune" in data["supported_districts"]
    assert "Gadchiroli" in data["supported_districts"]


def test_api_districts_endpoint_returns_36_districts_with_dhule_first():
    """Verifies that GET /api/districts returns all 36 districts with Dhule at index 0."""
    resp = client.get("/api/districts")
    assert resp.status_code == 200
    districts = resp.json()
    assert len(districts) == 36

    # Verify Dhule primary backward compatibility
    assert districts[0]["district_name"] == "Dhule"
    assert districts[0]["status"] == "Verified Empirical Baseline"
    assert "Shirpur" in districts[0]["talukas"]

    # Verify all 36 items have required metadata fields
    names = [d["district_name"] for d in districts]
    assert len(set(names)) == 36
    for d in districts:
        assert "district_name" in d
        assert "division" in d
        assert "region_type" in d
        assert "provenance_tier" in d
        assert "status" in d
        assert "talukas" in d
        assert len(d["talukas"]) >= 1


# ==============================================================================
# 3. District Validation & Error Handling (HTTP 422)
# ==============================================================================

def test_invalid_district_name_rejected_with_422():
    """Verifies that requesting an unsupported or misspelled district raises HTTP 422."""
    payload = {
        "district": "Atlantis",
        "cohort_size": 5,
        "simulation_steps": 1,
        "seed": 42
    }
    resp = client.post("/api/simulate", json=payload)
    assert resp.status_code == 422
    assert "District 'Atlantis' is not supported" in resp.text


def test_empty_district_name_rejected_with_422():
    """Verifies that an empty district string is rejected with HTTP 422."""
    payload = {
        "district": "",
        "cohort_size": 5,
        "simulation_steps": 1,
        "seed": 42
    }
    resp = client.post("/api/simulate", json=payload)
    assert resp.status_code == 422


def test_case_insensitive_district_name_normalization():
    """Verifies that district names are matched case-insensitively and normalized."""
    req = SimulationRequest(
        district="pune",
        cohort_size=3,
        simulation_steps=1,
        seed=42
    )
    assert req.district == "Pune"

    resp = SimulationService.execute_simulation(req, persist=False)
    assert resp.metadata.district == "Pune"
    for p in resp.personas:
        assert p.district == "Pune"


# ==============================================================================
# 4. Multi-District Simulation Across All Six Administrative Divisions
# ==============================================================================

@pytest.mark.parametrize("district_name,expected_division,expected_region", [
    ("Mumbai City", "Konkan", "Urban"),
    ("Pune", "Pune", "Urban"),
    ("Dhule", "Nashik", "Semi-Urban"),
    ("Chhatrapati Sambhajinagar", "Chhatrapati Sambhajinagar", "Urban"),
    ("Amravati", "Amravati", "Semi-Urban"),
    ("Gadchiroli", "Nagpur", "Rural"),
])
def test_simulation_executes_across_all_divisions(district_name, expected_division, expected_region):
    """
    Executes a multi-step simulation for representative districts across all 6 administrative divisions.
    Verifies district metadata, taluka sampling, and response structure.
    """
    req = SimulationRequest(
        district=district_name,
        cohort_size=5,
        simulation_steps=2,
        seed=42,
        policy_mode="statutory"
    )
    resp = SimulationService.execute_simulation(req, persist=False)
    assert resp.metadata.district == district_name
    assert resp.aggregate_metrics.total_personas == 5
    assert len(resp.personas) == 5

    prof = get_district_profile(district_name)
    assert prof.division == expected_division

    # Verify that generated personas belong to the requested district and its constituent talukas
    for p in resp.personas:
        assert p.district == district_name
        assert p.taluka in prof.talukas
        assert p.persona_id.startswith(prof.district_id[:4]) or p.persona_id.startswith("MUMB") or p.persona_id.startswith("CHHA") or p.persona_id.startswith("DHUL") or p.persona_id.startswith("PUNE") or p.persona_id.startswith("AMRA") or p.persona_id.startswith("GADC")


# ==============================================================================
# 5. Demographic Influence & Differentiation Verification
# ==============================================================================

def test_demographic_differentiation_between_mumbai_and_gadchiroli():
    """
    Verifies that district configurations actually influence generated student profiles.
    Compares metropolitan Mumbai City (urban, higher income) against rural Gadchiroli (tribal, lower income).
    """
    req_mumbai = SimulationRequest(district="Mumbai City", cohort_size=25, seed=100)
    req_gad = SimulationRequest(district="Gadchiroli", cohort_size=25, seed=100)

    resp_mumbai = SimulationService.execute_simulation(req_mumbai, persist=False)
    resp_gad = SimulationService.execute_simulation(req_gad, persist=False)

    mumbai_incomes = [p.family_income for p in resp_mumbai.personas]
    gad_incomes = [p.family_income for p in resp_gad.personas]

    avg_mumbai_income = sum(mumbai_incomes) / len(mumbai_incomes)
    avg_gad_income = sum(gad_incomes) / len(gad_incomes)

    # Metropolitan Mumbai has higher income bracket weights than tribal Gadchiroli
    assert avg_mumbai_income > avg_gad_income, (
        f"Expected Mumbai mean income ({avg_mumbai_income}) > Gadchiroli mean income ({avg_gad_income})"
    )

    # Taluka separation
    mumbai_talukas = {p.taluka for p in resp_mumbai.personas}
    gad_talukas = {p.taluka for p in resp_gad.personas}
    assert mumbai_talukas == {"Mumbai City"}
    assert "Mumbai City" not in gad_talukas
    assert any(t in get_district_profile("Gadchiroli").talukas for t in gad_talukas)


def test_dhule_backward_compatibility_preserved():
    """Verifies that Dhule cohort generation retains identical empirical properties."""
    req = SimulationRequest(district="Dhule", cohort_size=10, seed=42)
    resp = SimulationService.execute_simulation(req, persist=False)

    assert resp.metadata.district == "Dhule"
    assert "Dhule Educational Census table" in resp.metadata.data_disclaimer
    dhule_talukas = {"Dhule", "Shirpur", "Sindkhede", "Sakri"}
    for p in resp.personas:
        assert p.district == "Dhule"
        assert p.taluka in dhule_talukas
        assert p.persona_id.startswith("DHULE-STU")
