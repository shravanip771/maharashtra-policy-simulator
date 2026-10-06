"""
Automated unit tests for Phase 1 simulation vertical slice.
"""

from simulation.persona import (
    StudentPersona,
    InstitutionType,
    AdmissionMode,
    SimulationState,
    PersonalityTraits
)
from simulation.policy_rules import RajarshiShahuPolicyEngine
from simulation.agent import PersonaAgent, StubLLMProvider
from simulation.engine import SimulationEngine

def test_eligible_student_simulation():
    student = StudentPersona(
        persona_id="TEST-ELIGIBLE-01",
        name="Pooja Patil",
        age=20,
        gender="Female",
        district="Kolhapur",
        is_maharashtra_domicile=True,
        family_income=320000.0,
        caste_category="General-EBC",
        course_name="B.Pharm",
        institution_type=InstitutionType.PRIVATE_UNAIDED,
        admission_mode=AdmissionMode.CAP,
        annual_tuition_fee=80000.0,
        attendance_percentage=85.0,
        previous_year_passed=True,
        digital_literacy=0.8,
        initial_awareness=0.7,
        document_readiness=0.8,
        financial_urgency=0.7,
        peer_network_support=0.7
    )

    engine = SimulationEngine()
    result = engine.run_step(student)

    assert result.is_eligible is True
    assert result.estimated_fee_relief_inr == 40000.0
    assert result.reimbursement_percentage == 0.50
    assert len(result.statutory_failure_reasons) == 0
    assert len(result.benefit_assumptions) > 0
    assert "PoC Assumption" in result.benefit_assumptions[0]
    assert result.application_probability > 0.5
    assert result.final_simulation_state == SimulationState.BENEFIT_RECEIVED.value
    print("PASS: test_eligible_student_simulation")

def test_statutory_check_separation_and_configurable_benefit():
    # Verify statutory check works independently of benefit assumption
    student = StudentPersona(
        persona_id="TEST-ELIGIBLE-FEMALE-02",
        name="Sneha Jadhav",
        age=19,
        gender="Female",
        district="Satara",
        is_maharashtra_domicile=True,
        family_income=180000.0,
        caste_category="General-EBC",
        course_name="B.Tech IT",
        institution_type=InstitutionType.GOVERNMENT,
        admission_mode=AdmissionMode.CAP,
        annual_tuition_fee=60000.0,
        attendance_percentage=90.0,
        previous_year_passed=True
    )

    # 1. Pure statutory eligibility evaluation
    is_eligible, rule_checks, failure_reasons = RajarshiShahuPolicyEngine.check_statutory_eligibility(student)
    assert is_eligible is True
    assert len(failure_reasons) == 0
    assert len(rule_checks) == 8

    # 2. Configurable benefit evaluation (e.g. testing 100% concession assumption)
    eval_100 = RajarshiShahuPolicyEngine.evaluate_eligibility(student, assumed_reimbursement_rate=1.00)
    assert eval_100.is_eligible is True
    assert eval_100.reimbursement_percentage == 1.00
    assert eval_100.estimated_fee_relief_inr == 60000.0
    assert any("100%" in note for note in eval_100.benefit_assumptions)

    # 3. Default PoC baseline assumption (50%)
    eval_default = RajarshiShahuPolicyEngine.evaluate_eligibility(student)
    assert eval_default.reimbursement_percentage == 0.50
    assert eval_default.estimated_fee_relief_inr == 30000.0
    print("PASS: test_statutory_check_separation_and_configurable_benefit")

def test_ineligible_income_and_management_quota():
    student = StudentPersona(
        persona_id="TEST-INELIGIBLE-01",
        name="Rohan Sharma",
        age=21,
        gender="Male",
        district="Pune",
        is_maharashtra_domicile=True,
        family_income=950000.0,  # Exceeds 8L
        caste_category="General",
        course_name="B.Tech Computer Science",
        is_professional_course=True,
        institution_type=InstitutionType.PRIVATE_UNAIDED,
        admission_mode=AdmissionMode.MANAGEMENT_QUOTA,  # Ineligible for professional
        annual_tuition_fee=180000.0,
        attendance_percentage=78.0,
        previous_year_passed=True
    )

    engine = SimulationEngine()
    result = engine.run_step(student)

    assert result.is_eligible is False
    assert result.estimated_fee_relief_inr == 0.0
    assert len(result.statutory_failure_reasons) >= 2
    assert result.application_probability == 0.0
    assert result.benefit_received is False
    assert result.final_simulation_state == SimulationState.REJECTED.value
    print("PASS: test_ineligible_income_and_management_quota")

if __name__ == "__main__":
    test_eligible_student_simulation()
    test_statutory_check_separation_and_configurable_benefit()
    test_ineligible_income_and_management_quota()
    print("All Phase 1 tests passed successfully!")
