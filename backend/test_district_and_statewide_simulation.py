"""
Unit & Integration Tests for Statewide & Single-District Simulations.

Verifies:
1. Statewide 1,000-persona processing across all 36 Maharashtra districts.
2. Single-district runs with automatic allocation for Pune (83), Thane (98), Kolhapur (34), Dhule (18).
3. Exactly 10 deterministically selected featured personas returned in both modes.
4. Aggregates calculated over full cohorts (not just the 10 featured personas).
5. Peer interaction histories associated with featured personas and deduplicated interactions list.
6. Deterministic reproducibility across identical seeds and divergence across different seeds.
7. Proper rejection of unsupported districts with HTTP 400 Bad Request.
8. Epistemic disclaimer identifying allocations as provisional synthetic quotas.
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from simulation.district_config import STATEWIDE_POPULATION_ALLOCATION_36

client = TestClient(app)


class TestStatewideSimulationBackend:
    """Tests for POST /api/simulate/statewide endpoint and execution."""

    def test_statewide_simulation_1000_personas_and_36_districts(self):
        """Verifies processing of exactly 1,000 personas across all 36 districts."""
        payload = {"simulation_steps": 2, "seed": 42, "use_gemini": False}
        resp = client.post("/api/simulate/statewide", json=payload)
        assert resp.status_code == 200

        data = resp.json()
        summary = data["simulation_summary"]
        metadata = data["simulation_metadata"]
        district_results = data["district_results"]
        featured = data["featured_personas"]
        interactions = data["interactions"]

        # 1,000 total personas processed
        assert summary["total_personas"] == 1000
        assert metadata["total_personas_processed"] == 1000
        assert metadata["total_districts_configured"] == 36
        assert len(district_results) == 36

        # Quotas sum to 1,000 and match STATEWIDE_POPULATION_ALLOCATION_36
        total_allocated = sum(d["allocated_personas"] for d in district_results)
        assert total_allocated == 1000
        for d in district_results:
            d_name = d["district_name"]
            assert d["allocated_personas"] == STATEWIDE_POPULATION_ALLOCATION_36[d_name]

        # Exactly 10 featured personas returned
        assert len(featured) == 10

        # Aggregates calculated over full cohort (sum of eligible + ineligible = 1,000)
        assert summary["eligible_count"] + summary["ineligible_count"] == 1000
        assert summary["eligible_count"] > 0
        assert summary["ineligible_count"] > 0

        # Featured personas have interaction histories
        featured_ids = {p["persona_id"] for p in featured}
        for fp in featured:
            assert isinstance(fp["interaction_history"], list)
            for inter in fp["interaction_history"]:
                assert inter["sender_id"] == fp["persona_id"] or inter["receiver_id"] == fp["persona_id"]

        # Interactions list provided and contains peer records involving featured personas
        assert len(interactions) > 0
        for inter in interactions:
            assert inter["sender_id"] in featured_ids or inter["receiver_id"] in featured_ids

        # Data disclaimer contains provisional synthetic quota notice
        assert "provisional synthetic quota" in metadata["data_disclaimer"]

    def test_statewide_deterministic_seed_sampling(self):
        """Verifies deterministic selection of 10 featured personas for the same seed."""
        payload = {"simulation_steps": 1, "seed": 42, "use_gemini": False}
        resp1 = client.post("/api/simulate/statewide", json=payload)
        resp2 = client.post("/api/simulate/statewide", json=payload)

        assert resp1.status_code == 200
        assert resp2.status_code == 200

        data1 = resp1.json()
        data2 = resp2.json()

        featured_ids1 = [p["persona_id"] for p in data1["featured_personas"]]
        featured_ids2 = [p["persona_id"] for p in data2["featured_personas"]]
        assert featured_ids1 == featured_ids2
        assert len(featured_ids1) == 10

    def test_statewide_different_seeds_produce_different_featured_samples(self):
        """Verifies different seeds sample different featured personas."""
        resp1 = client.post("/api/simulate/statewide", json={"simulation_steps": 1, "seed": 42})
        resp2 = client.post("/api/simulate/statewide", json={"simulation_steps": 1, "seed": 9999})

        assert resp1.status_code == 200
        assert resp2.status_code == 200

        ids1 = {p["persona_id"] for p in resp1.json()["featured_personas"]}
        ids2 = {p["persona_id"] for p in resp2.json()["featured_personas"]}
        assert len(ids1) == 10
        assert len(ids2) == 10
        assert ids1 != ids2


class TestSingleDistrictSimulationBackend:
    """Tests for POST /api/simulate endpoint with automatic allocation."""

    @pytest.mark.parametrize("district,expected_cohort_size", [
        ("Pune", 83),
        ("Thane", 98),
        ("Kolhapur", 34),
        ("Dhule", 18),
    ])
    def test_single_district_configured_allocations(self, district: str, expected_cohort_size: int):
        """
        Verifies Pune=83, Thane=98, Kolhapur=34, Dhule=18 cohorts:
        - Cohort size matches STATEWIDE_POPULATION_ALLOCATION_36.
        - Aggregates are computed over the full cohort.
        - Exactly 10 featured personas are returned.
        - Interaction histories are attached to featured personas.
        - Epistemic disclaimer highlights provisional synthetic quotas.
        """
        req_payload = {
            "district": district,
            "simulation_steps": 2,
            "seed": 42,
            "use_gemini": False
        }
        resp = client.post("/api/simulate", json=req_payload)
        assert resp.status_code == 200

        data = resp.json()
        metadata = data["metadata"]
        agg = data["aggregate_metrics"]
        personas = data["personas"]
        interactions = data["interactions"]

        # Metadata cohort_size
        assert metadata["cohort_size"] == expected_cohort_size
        assert metadata["district"] == district

        # Aggregates computed over the entire cohort, not just 10 personas
        assert agg["total_personas"] == expected_cohort_size
        assert agg["eligible_count"] + agg["ineligible_count"] == expected_cohort_size
        assert agg["realized_uptake_count"] <= agg["eligible_count"]

        # Exactly 10 featured personas returned for UI presentation
        assert len(personas) == 10
        assert len(data["featured_personas"]) == 10

        # Personas have appropriate district prefix and interaction histories
        featured_ids = {p["persona_id"] for p in personas}
        for p in personas:
            assert p["district"] == district
            assert isinstance(p["interaction_history"], list)
            for inter in p["interaction_history"]:
                assert inter["sender_id"] == p["persona_id"] or inter["receiver_id"] == p["persona_id"]

        # Flat interactions list contains relevant records involving featured personas
        for inter in interactions:
            assert inter["sender_id"] in featured_ids or inter["receiver_id"] in featured_ids

        # Data disclaimer contains provisional synthetic quota statement
        assert "provisional synthetic quota" in metadata["data_disclaimer"]

    def test_single_district_deterministic_seed_sampling(self):
        """Verifies that seed deterministically controls both persona generation and featured sampling."""
        payload = {"district": "Pune", "simulation_steps": 1, "seed": 42}
        resp1 = client.post("/api/simulate", json=payload)
        resp2 = client.post("/api/simulate", json=payload)

        assert resp1.status_code == 200
        assert resp2.status_code == 200

        data1 = resp1.json()
        data2 = resp2.json()

        # Both runs produce identical aggregate metrics
        assert data1["aggregate_metrics"]["total_personas"] == 83
        assert data1["aggregate_metrics"]["eligible_count"] == data2["aggregate_metrics"]["eligible_count"]

        # Both runs sample identical 10 featured personas
        ids1 = [p["persona_id"] for p in data1["personas"]]
        ids2 = [p["persona_id"] for p in data2["personas"]]
        assert ids1 == ids2
        assert len(ids1) == 10

    def test_single_district_different_seeds_produce_different_featured_samples(self):
        """Verifies different seeds select different featured personas from Pune's 83-person cohort."""
        resp1 = client.post("/api/simulate", json={"district": "Pune", "simulation_steps": 1, "seed": 42})
        resp2 = client.post("/api/simulate", json={"district": "Pune", "simulation_steps": 1, "seed": 9999})

        assert resp1.status_code == 200
        assert resp2.status_code == 200

        ids1 = {p["persona_id"] for p in resp1.json()["personas"]}
        ids2 = {p["persona_id"] for p in resp2.json()["personas"]}
        assert len(ids1) == 10
        assert len(ids2) == 10
        assert ids1 != ids2

    def test_unsupported_district_rejected_with_400(self):
        """Verifies invalid or unconfigured district requests fail explicitly with 400 Bad Request."""
        resp = client.post("/api/simulate", json={"district": "MarsDistrict", "seed": 42})
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert "Invalid district 'MarsDistrict'" in detail
        assert "Supported districts:" in detail
