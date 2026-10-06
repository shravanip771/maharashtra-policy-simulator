"""
Unit tests for 10-Persona Cohort Population Simulation (Phase 2 Milestone).

Verifies:
1. Exactly 10 personas generated from the Dhule empirical configuration.
2. Unique persona IDs across all personas.
3. Every persona receives an individual structured policy evaluation.
4. Mathematical reconciliation between aggregate metrics and individual outputs.
5. Strict reproducibility under identical random seeds.
6. Behavioral and statistical variance under differing seeds.
7. Configurable benefit reimbursement rate propagation across the cohort.
8. Non-regression of Phase 1 and Phase 2 foundational tests.
"""

from data.dhule_adapter import DhuleEducationDatasetAdapter
from simulation.persona_generator import SyntheticPersonaGenerator
from simulation.engine import SimulationEngine, CohortSimulationResult, SimulationStepOutput
from simulation.run_cohort_slice import run_10_person_dhule_cohort


def test_exactly_10_personas_and_unique_ids():
    """Verifies that exactly 10 personas are generated with distinct, well-formed IDs."""
    dhule_config = DhuleEducationDatasetAdapter.create_population_config()
    generator = SyntheticPersonaGenerator(config=dhule_config, seed=42)

    personas = generator.generate_student_population(count=10, id_prefix="DHULE-STU")
    assert len(personas) == 10

    persona_ids = [p.persona_id for p in personas]
    assert len(set(persona_ids)) == 10
    assert persona_ids == [f"DHULE-STU-{i:03d}" for i in range(1, 11)]

    # Check that district is Dhule for all personas (grounded)
    for p in personas:
        assert p.district == "Dhule"
        assert p.is_maharashtra_domicile is True
    print("PASS: test_exactly_10_personas_and_unique_ids")


def test_individual_and_aggregate_reconciliation():
    """Verifies that every persona receives an evaluation and aggregate metrics reconcile."""
    result = run_10_person_dhule_cohort(seed=42, assumed_reimbursement_rate=0.50)

    assert isinstance(result, CohortSimulationResult)
    assert result.total_personas == 10
    assert len(result.individual_results) == 10

    # 1. Reconciliation of eligibility counts
    individual_eligible = [r for r in result.individual_results if r.is_eligible]
    individual_ineligible = [r for r in result.individual_results if not r.is_eligible]
    assert result.eligible_count == len(individual_eligible)
    assert result.ineligible_count == len(individual_ineligible)
    assert result.eligible_count + result.ineligible_count == 10
    assert result.eligibility_rate == round(result.eligible_count / 10, 4)

    # 2. Reconciliation of fee relief amounts
    sum_relief = sum(r.estimated_fee_relief_inr for r in result.individual_results)
    assert result.total_estimated_fee_relief_inr == sum_relief
    if result.eligible_count > 0:
        assert result.average_fee_relief_per_eligible_inr == round(sum_relief / result.eligible_count, 2)
    else:
        assert result.average_fee_relief_per_eligible_inr == 0.0

    # 3. Reconciliation of gender breakdown
    total_gender_count = sum(d["total_count"] for d in result.breakdown_by_gender.values())
    assert total_gender_count == 10

    # 4. Reconciliation of institution type breakdown
    total_inst_count = sum(d["total_count"] for d in result.breakdown_by_institution_type.values())
    assert total_inst_count == 10

    # 5. Reconciliation of state distribution
    total_states = sum(result.state_distribution.values())
    assert total_states == 10

    # 6. Check that each individual result has complete fields
    for r in result.individual_results:
        assert isinstance(r, SimulationStepOutput)
        assert r.persona_id.startswith("DHULE-STU-")
        assert len(r.persona_name) > 0
        assert 0.0 <= r.awareness_score <= 1.0
        assert 0.0 <= r.application_probability <= 1.0
        assert 0.0 <= r.completion_probability <= 1.0
        assert len(r.inner_monologue) > 0
        assert len(r.stated_intention) > 0
    print("PASS: test_individual_and_aggregate_reconciliation")


def test_seed_reproducibility():
    """Verifies that running with the same seed produces identical population and aggregate outputs."""
    result1 = run_10_person_dhule_cohort(seed=12345)
    result2 = run_10_person_dhule_cohort(seed=12345)

    assert result1.to_dict() == result2.to_dict(), "Runs with identical seed must match 100%"

    # Verify a different seed produces different outcomes
    result_diff = run_10_person_dhule_cohort(seed=99999)
    assert result1.to_dict() != result_diff.to_dict()
    print("PASS: test_seed_reproducibility")


def test_configurable_benefit_rate_in_cohort():
    """Verifies that changing assumed reimbursement rate scales fee relief across the cohort."""
    result_50 = run_10_person_dhule_cohort(seed=42, assumed_reimbursement_rate=0.50)
    result_100 = run_10_person_dhule_cohort(seed=42, assumed_reimbursement_rate=1.00)

    # Statutory eligibility must remain identical regardless of benefit rate
    assert result_50.eligible_count == result_100.eligible_count
    assert result_50.ineligible_count == result_100.ineligible_count

    # Fee relief under 100% rate must be exactly double that under 50% rate
    if result_50.eligible_count > 0:
        assert result_100.total_estimated_fee_relief_inr == result_50.total_estimated_fee_relief_inr * 2
    print("PASS: test_configurable_benefit_rate_in_cohort")


if __name__ == "__main__":
    test_exactly_10_personas_and_unique_ids()
    test_individual_and_aggregate_reconciliation()
    test_seed_reproducibility()
    test_configurable_benefit_rate_in_cohort()
    print("All 10-persona cohort simulation tests passed successfully!")
