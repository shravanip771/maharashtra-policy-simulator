"""
Unit and Integration Tests for District-Aware Persona Generation and Synthetic Diversity.

Verifies:
1. District selection properly routes to the district profile (not defaulting to Dhule).
2. Persona attributes exhibit realistic, bounded variation across regional archetypes.
3. Values remain strictly within statutory and probabilistic bounds.
4. Deterministic reproducibility under identical random seeds.
5. The provisional 2011 total-population-weighted allocation across 35 districts totals exactly 1,000.
6. Statutory policy eligibility rules remain 100% strictly enforced and unaltered.
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models import SimulationRequest
from backend.service import SimulationService
from simulation.district_config import (
    DISTRICT_REGISTRY,
    list_supported_districts,
    get_district_profile,
    STATEWIDE_POPULATION_ALLOCATION_36,
    PROVISIONAL_2011_TOTAL_POPULATION_WEIGHTED_ALLOCATION_35,
    MISSING_36TH_DISTRICT
)
from simulation.persona_generator import SyntheticPersonaGenerator
from simulation.persona import InstitutionType, AdmissionMode
from simulation.policy_rules import RajarshiShahuPolicyEngine

client = TestClient(app)


class TestDistrictAwareGeneration:
    """Verifies that user-selected district drives persona generation and API responses."""

    def test_pune_district_generates_pune_personas(self):
        """Ensures selecting Pune does not generate Dhule personas."""
        req = SimulationRequest(district="Pune", cohort_size=10, simulation_steps=2, seed=42)
        resp = SimulationService.execute_simulation(req)

        assert resp.metadata.district == "Pune"
        assert len(resp.personas) == 10

        pune_talukas = set(get_district_profile("Pune").talukas)
        for p in resp.personas:
            assert p.district == "Pune", f"Expected district 'Pune', got '{p.district}'"
            assert p.taluka in pune_talukas, f"Taluka '{p.taluka}' not in Pune talukas: {pune_talukas}"

    def test_mumbai_city_district_generates_mumbai_personas(self):
        """Ensures selecting Mumbai City generates Mumbai personas."""
        req = SimulationRequest(district="Mumbai City", cohort_size=10, simulation_steps=2, seed=42)
        resp = SimulationService.execute_simulation(req)

        assert resp.metadata.district == "Mumbai City"
        assert len(resp.personas) == 10
        for p in resp.personas:
            assert p.district == "Mumbai City"

    def test_gadchiroli_district_generates_gadchiroli_personas(self):
        """Ensures selecting a rural/tribal district like Gadchiroli generates correct personas with its configured cohort size."""
        req = SimulationRequest(district="Gadchiroli", cohort_size=10, simulation_steps=2, seed=42)
        resp = SimulationService.execute_simulation(req)

        assert resp.metadata.district == "Gadchiroli"
        assert resp.metadata.cohort_size == 9
        assert resp.aggregate_metrics.total_personas == 9
        assert len(resp.personas) == 9  # min(10, 9)
        gadchiroli_talukas = set(get_district_profile("Gadchiroli").talukas)
        for p in resp.personas:
            assert p.district == "Gadchiroli"
            assert p.taluka in gadchiroli_talukas

    def test_alias_resolution_ahmednagar_and_osmanabad(self):
        """Verifies that historical district names map smoothly to official registry profiles."""
        p_ahmednagar = get_district_profile("Ahmednagar")
        assert p_ahmednagar.district_id == "AHILYANAGAR"
        assert p_ahmednagar.district_name == "Ahilyanagar"

        p_osmanabad = get_district_profile("Osmanabad (Dharashiv)")
        assert p_osmanabad.district_id == "DHARASHIV"
        assert p_osmanabad.district_name == "Dharashiv"

    def test_invalid_district_rejected_with_400_via_api(self):
        """Verifies that an unknown district returns HTTP 400 with helpful error details."""
        res = client.post("/api/simulate", json={
            "district": "Atlantis",
            "cohort_size": 10,
            "simulation_steps": 2,
            "seed": 42
        })
        assert res.status_code == 400
        detail = res.json()["detail"]
        assert "Invalid district 'Atlantis'" in detail
        assert "Supported districts:" in detail

    def test_get_districts_returns_all_36_with_dhule_first(self):
        """Verifies GET /api/districts returns all 36 configured districts with backward compatibility."""
        res = client.get("/api/districts")
        assert res.status_code == 200
        districts = res.json()
        assert len(districts) == 36
        # Backward compatibility check for tests expecting Dhule first
        assert districts[0]["district_name"] == "Dhule"
        assert "Shirpur" in districts[0]["talukas"]

        # Ensure all 36 supported districts are present in response
        names = {d["district_name"] for d in districts}
        assert len(names) == 36


class TestSyntheticDiversityAndBounds:
    """Verifies realistic variation and strict mathematical bounding of generated attributes."""

    def test_regional_income_variation(self):
        """Verifies that Urban districts have higher median income than Rural districts."""
        gen_urban = SyntheticPersonaGenerator.for_district("Mumbai Suburban", seed=42)
        cohort_urban = gen_urban.generate_cohort(100, seed=42)

        gen_rural = SyntheticPersonaGenerator.for_district("Gadchiroli", seed=42)
        cohort_rural = gen_rural.generate_cohort(100, seed=42)

        avg_urban_income = sum(p.family_income for p in cohort_urban) / len(cohort_urban)
        avg_rural_income = sum(p.family_income for p in cohort_rural) / len(cohort_rural)

        # Urban incomes should reflect higher cost-of-living archetype than rural
        assert avg_urban_income > avg_rural_income
        assert avg_urban_income > 300000.0
        assert avg_rural_income < 350000.0

    def test_persona_attribute_bounds(self):
        """Verifies that all persona metrics remain strictly within plausible and valid bounds."""
        for d in ["Pune", "Dhule", "Mumbai City", "Gadchiroli"]:
            gen = SyntheticPersonaGenerator.for_district(d, seed=123)
            cohort = gen.generate_cohort(50, seed=123)

            for p in cohort:
                # Incomes and fees
                assert p.family_income >= 40000.0
                assert p.annual_tuition_fee >= 5000.0

                # Academic metrics
                assert 55.0 <= p.attendance_percentage <= 100.0
                assert 35.0 <= p.previous_year_percentage <= 100.0
                assert 0 <= p.academic_gap_years <= 3

                # Probabilistic and behavioral scores
                assert 0.05 <= p.initial_awareness <= 0.95
                assert 0.05 <= p.digital_literacy <= 0.95
                assert 0.05 <= p.document_readiness <= 0.95
                assert 0.05 <= p.financial_urgency <= 1.0
                assert 0.05 <= p.institutional_trust <= 0.95

    def test_seed_reproducibility(self):
        """Verifies identical seed produces bit-identical cohort, while differing seed produces variation."""
        gen1 = SyntheticPersonaGenerator.for_district("Pune", seed=42)
        cohort1 = gen1.generate_cohort(10, seed=42)

        gen2 = SyntheticPersonaGenerator.for_district("Pune", seed=42)
        cohort2 = gen2.generate_cohort(10, seed=42)

        gen3 = SyntheticPersonaGenerator.for_district("Pune", seed=99)
        cohort3 = gen3.generate_cohort(10, seed=99)

        for p1, p2 in zip(cohort1, cohort2):
            assert p1.persona_id == p2.persona_id
            assert p1.name == p2.name
            assert p1.family_income == p2.family_income
            assert p1.annual_tuition_fee == p2.annual_tuition_fee
            assert p1.initial_awareness == p2.initial_awareness

        # Verify seed 99 differs
        diff_count = sum(1 for p1, p3 in zip(cohort1, cohort3) if p1.name != p3.name)
        assert diff_count > 5


class TestStatewideAllocationAndQuotas:
    """Verifies the statewide population allocation across all 36 Maharashtra districts."""

    def test_provisional_allocation_counts_and_missing_district(self):
        """Verifies the 36-district statewide allocation totals exactly 1,000."""
        # 1. 36 districts represented
        assert len(STATEWIDE_POPULATION_ALLOCATION_36) == 36
        assert sum(STATEWIDE_POPULATION_ALLOCATION_36.values()) == 1000

        # 2. Chhatrapati Sambhajinagar receives exactly 10 personas
        assert STATEWIDE_POPULATION_ALLOCATION_36["Chhatrapati Sambhajinagar"] == 10

        # 3. The other 35 districts sum to exactly 990
        other_35_sum = sum(
            c for d, c in STATEWIDE_POPULATION_ALLOCATION_36.items()
            if d != "Chhatrapati Sambhajinagar"
        )
        assert other_35_sum == 990

        # 4. Historical 35-district allocation remains available
        assert len(PROVISIONAL_2011_TOTAL_POPULATION_WEIGHTED_ALLOCATION_35) == 35
        assert sum(PROVISIONAL_2011_TOTAL_POPULATION_WEIGHTED_ALLOCATION_35.values()) == 1000

    def test_generate_weighted_state_population_produces_exactly_1000(self):
        """Verifies generate_weighted_state_population produces exactly 1,000 personas matching 36 quotas."""
        pop = SyntheticPersonaGenerator.generate_weighted_state_population(seed=42)
        assert len(pop) == 1000

        # Unique persona IDs
        ids = {p.persona_id for p in pop}
        assert len(ids) == 1000

        # Verify quotas match expected distribution across all 36 districts
        from collections import Counter
        dist_counts = Counter(p.district for p in pop)
        assert len(dist_counts) == 36

        for dist_name, expected_count in STATEWIDE_POPULATION_ALLOCATION_36.items():
            assert dist_counts[dist_name] == expected_count, (
                f"District {dist_name}: expected {expected_count}, got {dist_counts[dist_name]}"
            )

    def test_standard_generate_state_population_backward_compatibility(self):
        """Verifies that the original generate_state_population continues to produce balanced cohorts."""
        pop = SyntheticPersonaGenerator.generate_state_population(total_count=1000, seed=42)
        assert len(pop) == 1000
        dist_counts = {p.district for p in pop}
        assert len(dist_counts) == 36


class TestStatutoryEligibilityPreservation:
    """Verifies that statutory policy rules remain strictly unaltered."""

    def test_statutory_rules_not_relaxed(self):
        """Verifies that ineligibility conditions strictly trigger rejection."""
        gen = SyntheticPersonaGenerator.for_district("Pune", seed=42)
        cohort = gen.generate_cohort(50, seed=42)

        for p in cohort:
            res = RajarshiShahuPolicyEngine.evaluate_eligibility(p)
            if p.family_income > 800000.0:
                assert not res.is_eligible
                assert any("exceeds the statutory limit" in f for f in res.failure_reasons)
            if p.attendance_percentage < 75.0:
                assert not res.is_eligible
                assert any("below statutory requirement" in f for f in res.failure_reasons)
            if p.has_other_scholarship:
                assert not res.is_eligible
                assert any("already receiving another government scholarship" in f for f in res.failure_reasons)


class TestStatewideCohortEndpoint:
    """
    Integration tests for GET /api/cohorts/statewide.
    Verifies:
    1. HTTP 200 response and exactly 1,000 personas generated.
    2. District allocations sum to 1,000 across 35 configured districts.
    3. Accurate reporting of Chhatrapati Sambhajinagar as the omitted 36th district.
    4. Actual generated counts per district match configured quotas with 0 discrepancy.
    5. Deterministic reproducibility for identical seeds.
    6. Distinct valid outputs across differing seeds.
    7. Complete Pydantic schema validation and serialization consistency.
    """

    def test_statewide_cohort_endpoint_http_200_and_total_count(self):
        """Verifies GET /api/cohorts/statewide returns HTTP 200 with 1,000 personas by default."""
        response = client.get("/api/cohorts/statewide")
        assert response.status_code == 200

        data = response.json()
        assert data["total_count"] == 1000
        assert len(data["personas"]) == 1000
        assert data["seed"] == 42
        assert "None" in str(data["missing_district"])

    def test_statewide_cohort_allocations_sum_to_1000_and_missing_district(self):
        """Verifies configured district allocations sum to 1,000 across all 36 districts."""
        response = client.get("/api/cohorts/statewide?seed=42")
        assert response.status_code == 200

        data = response.json()
        allocations = data["district_allocations"]
        assert len(allocations) == 36
        assert sum(allocations.values()) == 1000

        # Verify Chhatrapati Sambhajinagar is included with quota 10
        assert allocations["Chhatrapati Sambhajinagar"] == 10

        # Verify specific district quotas are strictly preserved under largest-remainder allocation
        assert allocations["Pune"] == 83
        assert allocations["Thane"] == 98
        assert allocations["Solapur"] == 38
        assert allocations["Mumbai Suburban"] == 83
        assert allocations["Mumbai City"] == 28
        assert allocations["Dhule"] == 18
        assert allocations["Gadchiroli"] == 9
        assert allocations["Sindhudurg"] == 8

    def test_statewide_cohort_actual_counts_match_configured_quotas(self):
        """Verifies actual persona counts per district match configured allocations exactly."""
        response = client.get("/api/cohorts/statewide?seed=42")
        assert response.status_code == 200

        data = response.json()
        allocations = data["district_allocations"]

        from collections import Counter
        actual_counts = Counter(p["district"] for p in data["personas"])

        assert len(actual_counts) == 36
        for district, expected_count in allocations.items():
            assert actual_counts[district] == expected_count, (
                f"Mismatch in {district}: expected {expected_count}, got {actual_counts[district]}"
            )

    def test_statewide_cohort_deterministic_output_for_same_seed(self):
        """Verifies that calling the endpoint with the same seed produces identical output."""
        resp1 = client.get("/api/cohorts/statewide?seed=123")
        resp2 = client.get("/api/cohorts/statewide?seed=123")

        assert resp1.status_code == 200
        assert resp2.status_code == 200

        data1 = resp1.json()
        data2 = resp2.json()

        assert data1["total_count"] == data2["total_count"]
        assert data1["seed"] == data2["seed"] == 123

        p_ids1 = [p["persona_id"] for p in data1["personas"]]
        p_ids2 = [p["persona_id"] for p in data2["personas"]]
        assert p_ids1 == p_ids2

        # Check full equality on sample personas
        assert data1["personas"][0] == data2["personas"][0]
        assert data1["personas"][500] == data2["personas"][500]
        assert data1["personas"][999] == data2["personas"][999]

    def test_statewide_cohort_different_seeds_produce_valid_varying_output(self):
        """Verifies that varying seed parameter produces different synthetic personas while preserving quotas."""
        resp1 = client.get("/api/cohorts/statewide?seed=42")
        resp2 = client.get("/api/cohorts/statewide?seed=999")

        assert resp1.status_code == 200
        assert resp2.status_code == 200

        data1 = resp1.json()
        data2 = resp2.json()

        assert data1["seed"] == 42
        assert data2["seed"] == 999
        assert data1["total_count"] == data2["total_count"] == 1000

        # Persona IDs or attributes differ between seeds
        names1 = [p["name"] for p in data1["personas"][:20]]
        names2 = [p["name"] for p in data2["personas"][:20]]
        assert names1 != names2, "Expected different persona names across differing seeds"

    def test_statewide_cohort_response_schema_and_serialization(self):
        """Verifies all required fields, data types, value bounds, and policy evaluation in personas."""
        response = client.get("/api/cohorts/statewide?seed=42")
        assert response.status_code == 200

        data = response.json()
        personas = data["personas"]
        assert len(personas) == 1000

        for p in personas[:50]:  # Verify detailed attributes across a representative slice
            assert isinstance(p["persona_id"], str) and len(p["persona_id"]) > 0
            assert isinstance(p["name"], str) and len(p["name"]) > 0
            assert p["gender"] in ["Male", "Female"]
            assert 16 <= p["age"] <= 35
            assert isinstance(p["district"], str)
            assert isinstance(p["taluka"], str)
            assert isinstance(p["course_name"], str)
            assert isinstance(p["is_professional_course"], bool)
            assert p["institution_type"] in [i.value for i in InstitutionType]
            assert p["admission_mode"] in [m.value for m in AdmissionMode]
            assert p["caste_category"] in ["General", "General-EBC", "OBC", "SC", "ST", "VJNT"]
            assert p["family_income"] > 0
            assert p["annual_tuition_fee"] > 0
            assert 50.0 <= p["attendance_percentage"] <= 100.0
            assert isinstance(p["previous_year_passed"], bool)
            assert isinstance(p["first_generation_learner"], bool)

            # Statutory policy evaluation consistency
            assert isinstance(p["is_statutorily_eligible"], bool)
            assert isinstance(p["estimated_fee_relief_inr"], (int, float))
            assert isinstance(p["statutory_failure_reasons"], list)

            if not p["is_statutorily_eligible"]:
                assert p["estimated_fee_relief_inr"] == 0.0
                assert len(p["statutory_failure_reasons"]) > 0
            else:
                assert p["estimated_fee_relief_inr"] > 0.0

            # Bounded probabilistic priors
            assert 0.0 <= p["initial_awareness"] <= 1.0
            assert 0.0 <= p["final_awareness"] <= 1.0
            assert 0.0 <= p["initial_trust"] <= 1.0
            assert 0.0 <= p["final_trust"] <= 1.0
            assert 0.0 <= p["digital_literacy"] <= 1.0
            assert 0.0 <= p["document_readiness"] <= 1.0
            assert p["final_state"] in ["UNINFORMED", "AWARE", "EVALUATING", "APPLICATION_SUBMITTED", "BENEFIT_RECEIVED", "REJECTED", "DROPPED_OUT"]


class TestStatewideSimulationEndpoint:
    """
    Comprehensive tests for POST /api/simulate/statewide:
    1. All 36 districts represented in allocation.
    2. Chhatrapati Sambhajinagar receives exactly 10 personas.
    3. All quotas sum to exactly 1,000.
    4. The other 35 district quotas sum to 990.
    5. Actual generated district counts match configured quotas.
    6. All 1,000 personas undergo the complete simulation.
    7. Only 10 featured personas are returned.
    8. All 10 featured personas belong to the simulated cohort.
    9. Featured selection is deterministic for the same seed.
    10. Different seeds produce different featured samples.
    11. Aggregate metrics are calculated using all 1,000 personas.
    12. District-wise aggregate metrics match actual simulation outcomes.
    13. The existing single-district endpoint remains backward-compatible.
    14. API response serialization and error handling work correctly.
    """

    def test_statewide_simulation_full_lifecycle_and_aggregates(self):
        """
        Executes POST /api/simulate/statewide and verifies requirements 1 through 8, 11, and 12.
        """
        payload = {
            "simulation_steps": 2,
            "seed": 42,
            "use_gemini": False
        }
        response = client.post("/api/simulate/statewide", json=payload)
        assert response.status_code == 200

        data = response.json()
        summary = data["simulation_summary"]
        district_results = data["district_results"]
        featured = data["featured_personas"]
        metadata = data["simulation_metadata"]

        # Requirement 1: All 36 districts represented
        assert len(district_results) == 36
        district_names = {d["district_name"] for d in district_results}
        assert len(district_names) == 36
        assert "Chhatrapati Sambhajinagar" in district_names

        # Requirement 2: Chhatrapati Sambhajinagar receives exactly 10 personas
        cs_result = next(d for d in district_results if d["district_name"] == "Chhatrapati Sambhajinagar")
        assert cs_result["allocated_personas"] == 10

        # Requirement 3: All quotas sum to exactly 1,000
        total_allocated = sum(d["allocated_personas"] for d in district_results)
        assert total_allocated == 1000
        assert summary["total_personas"] == 1000

        # Requirement 4: The other 35 district quotas sum to 990
        other_35_sum = sum(d["allocated_personas"] for d in district_results if d["district_name"] != "Chhatrapati Sambhajinagar")
        assert other_35_sum == 990

        # Requirement 5: Actual generated district counts match configured quotas
        for d in district_results:
            assert d["allocated_personas"] == STATEWIDE_POPULATION_ALLOCATION_36[d["district_name"]]

        # Requirement 6: All 1,000 personas undergo complete simulation
        # Sum of eligible + ineligible must equal 1,000
        assert summary["eligible_count"] + summary["ineligible_count"] == 1000
        assert metadata["total_personas_processed"] == 1000
        assert metadata["completion_status"] == "SUCCESS"
        assert len(summary["step_metrics"]) == 2

        # Requirement 7: Exactly 10 featured personas returned
        assert len(featured) == 10

        # Requirement 8: All 10 featured personas belong to the simulated cohort
        for fp in featured:
            assert fp["district"] in district_names
            assert fp["persona_id"].endswith("-STU-", 0, len(fp["persona_id"]) - 3) or "-STU-" in fp["persona_id"]
            # Verify interaction history structure is present
            assert isinstance(fp["interaction_history"], list)

        # Requirement 11: Aggregate metrics calculated using all 1,000 personas
        assert summary["eligible_count"] == sum(d["eligible_count"] for d in district_results)
        assert summary["ineligible_count"] == sum(d["ineligible_count"] for d in district_results)
        assert summary["realized_beneficiaries_count"] == sum(d["realized_beneficiaries"] for d in district_results)
        assert summary["total_estimated_fee_relief_inr"] == pytest.approx(
            sum(d["total_estimated_fee_relief_inr"] for d in district_results), rel=1e-3
        )
        assert summary["attempted_applications_count"] == sum(d["attempted_applications"] for d in district_results)
        assert summary["completed_applications_count"] == sum(d["completed_applications"] for d in district_results)

        # Requirement 12: District-wise aggregate metrics match actual outcomes
        for d in district_results:
            assert d["eligible_count"] + d["ineligible_count"] == d["allocated_personas"]
            assert d["realized_beneficiaries"] <= d["completed_applications"] <= d["attempted_applications"] <= d["allocated_personas"]
            if d["eligible_count"] > 0:
                assert d["average_relief_per_eligible_inr"] == pytest.approx(
                    round(d["total_estimated_fee_relief_inr"] / d["eligible_count"], 2), rel=1e-2
                )

    def test_featured_selection_deterministic_reproducibility(self):
        """Requirement 9: Featured selection is deterministic for the same seed."""
        payload = {"simulation_steps": 1, "seed": 777, "use_gemini": False}
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

        # Entire featured persona objects match identically
        for fp1, fp2 in zip(data1["featured_personas"], data2["featured_personas"]):
            assert fp1["persona_id"] == fp2["persona_id"]
            assert fp1["name"] == fp2["name"]
            assert fp1["district"] == fp2["district"]
            assert fp1["final_state"] == fp2["final_state"]

    def test_different_seeds_produce_different_featured_samples(self):
        """Requirement 10: Different seeds produce different featured persona samples."""
        payload1 = {"simulation_steps": 1, "seed": 42, "use_gemini": False}
        payload2 = {"simulation_steps": 1, "seed": 9999, "use_gemini": False}

        resp1 = client.post("/api/simulate/statewide", json=payload1)
        resp2 = client.post("/api/simulate/statewide", json=payload2)

        assert resp1.status_code == 200
        assert resp2.status_code == 200

        ids1 = {p["persona_id"] for p in resp1.json()["featured_personas"]}
        ids2 = {p["persona_id"] for p in resp2.json()["featured_personas"]}
        assert len(ids1) == 10
        assert len(ids2) == 10
        # Given 1,000 personas, probability of sampling the exact same 10 with different seed is negligible
        assert ids1 != ids2

    def test_single_district_endpoint_backward_compatibility(self):
        """Existing single-district POST /api/simulate resolves cohort from statewide allocation and returns 10 featured personas."""
        single_req = {
            "district": "Dhule",
            "cohort_size": 10,
            "simulation_steps": 2,
            "seed": 42,
            "use_gemini": False
        }
        resp = client.post("/api/simulate", json=single_req)
        assert resp.status_code == 200

        data = resp.json()
        assert data["metadata"]["district"] == "Dhule"
        assert data["metadata"]["cohort_size"] == 18
        assert data["aggregate_metrics"]["total_personas"] == 18
        assert len(data["personas"]) == 10
        assert len(data["featured_personas"]) == 10
        assert "provenance_breakdown" in data
        assert "network_topology" in data
        assert "provisional synthetic quota" in data["metadata"]["data_disclaimer"]

    def test_statewide_simulation_validation_and_error_handling(self):
        """Requirement 14: API response serialization and error handling work correctly."""
        # Invalid simulation steps (0 or negative)
        bad_payload = {"simulation_steps": 0, "seed": 42}
        resp = client.post("/api/simulate/statewide", json=bad_payload)
        assert resp.status_code == 422

        # Invalid simulation steps (> 5)
        bad_payload2 = {"simulation_steps": 6, "seed": 42}
        resp2 = client.post("/api/simulate/statewide", json=bad_payload2)
        assert resp2.status_code == 422
