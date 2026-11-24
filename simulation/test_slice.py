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
from simulation.policy_rules import RajarshiShahuPolicyEngine, DTEPolicyConfig
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

    # 2b. Configurable legacy PoC benefit evaluation (50% uniform concession)
    eval_50 = RajarshiShahuPolicyEngine.evaluate_eligibility(student, assumed_reimbursement_rate=0.50)
    assert eval_50.is_eligible is True
    assert eval_50.reimbursement_percentage == 0.50
    assert eval_50.estimated_fee_relief_inr == 30000.0

    # 3. Default statutory evaluation (GR 08.07.2024: 100% waiver for female candidate in Govt college)
    # Student inputs: Female, Income 1.8L <= 8L, Govt college, CAP -> 100% of 60,000 = 60,000 INR
    eval_default = RajarshiShahuPolicyEngine.evaluate_eligibility(student)
    assert eval_default.reimbursement_percentage == 1.00
    assert eval_default.estimated_fee_relief_inr == 60000.0
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

def test_male_examination_fee_relief_and_net_payable():
    """
    Task 1 Regression Test:
    Evaluates a valid male student persona with non-zero annual examination fee under 'statutory' mode.
    Verifies:
      - 50% examination-fee relief according to implemented provisional rules (GR 31.03.2018 reference).
      - Net payable examination fee = annual_exam_fee - exam_fee_relief_inr.
      - Net payable tuition fee and total net payable fee.
      - Explicit provisional markings (not claiming to be officially verified).
    """
    male_student = StudentPersona(
        persona_id="TEST-MALE-EXAM-RELIEF-01",
        name="Sachin Deshmukh",
        age=20,
        gender="Male",
        district="Dhule",
        is_maharashtra_domicile=True,
        family_income=350000.0,  # Tier 2: between 2.5L and 8.0L
        caste_category="General-EBC",
        course_name="B.Tech Mechanical",
        is_professional_course=True,
        institution_type=InstitutionType.GOVERNMENT_AIDED,
        admission_mode=AdmissionMode.CAP,
        annual_tuition_fee=70000.0,
        annual_exam_fee=8000.0,
        attendance_percentage=82.0,
        previous_year_passed=True,
        digital_literacy=0.75,
        initial_awareness=0.7,
        document_readiness=0.8,
        financial_urgency=0.6,
        peer_network_support=0.7
    )

    engine = SimulationEngine()
    result = engine.run_step(male_student, policy_mode="statutory")

    # 1. Statutory eligibility verification
    assert result.is_eligible is True
    assert len(result.statutory_failure_reasons) == 0
    assert result.policy_mode == "statutory"
    assert result.policy_version == "2024.1-provisional"

    # 2. Fee relief verification (Provisional rules: Male Tier 2 Govt/Aided -> 50% tuition, 50% exam)
    # Annual tuition fee: 70,000 INR -> 50% = 35,000 INR
    # Annual exam fee: 8,000 INR -> 50% = 4,000 INR
    assert result.tuition_fee_relief_inr == 35000.0
    assert result.exam_fee_relief_inr == 4000.0
    assert result.estimated_fee_relief_inr == 39000.0
    assert result.reimbursement_percentage == 0.50

    # 3. Net payable fee verification
    assert result.net_payable_tuition_fee == 35000.0
    assert result.net_payable_exam_fee == 4000.0
    assert result.total_net_payable_fee == 39000.0
    assert result.net_payable_exam_fee == result.annual_exam_fee - result.exam_fee_relief_inr
    assert result.total_net_payable_fee == (result.annual_tuition_fee + result.annual_exam_fee) - result.estimated_fee_relief_inr

    # 4. Explicit Epistemic Status (Provisional / Unverified - must NOT claim official verification)
    assert result.is_provisional is True
    notes_combined = " ".join(result.statutory_notes + result.benefit_assumptions).lower()
    assert "provisional" in notes_combined
    assert "exam" in notes_combined
    assert any("provisional assumption" in note.lower() and "exam" in note.lower() for note in result.statutory_notes)
    assert "officially verified" not in notes_combined
    print("PASS: test_male_examination_fee_relief_and_net_payable")

def test_counterfactual_income_ceiling_scenario():
    """
    Task 2 Regression Test:
    Evaluates a student whose family income falls between statutory ceiling (8 Lakh)
    and a configurable counterfactual ceiling (10 Lakh).
    Demonstrates that counterfactual mode flips eligibility from False to True
    and calculates fee relief accordingly.
    """
    cf_student = StudentPersona(
        persona_id="TEST-CF-INCOME-CEILING-01",
        name="Priyanka Deshpande",
        age=20,
        gender="Female",
        district="Pune",
        is_maharashtra_domicile=True,
        family_income=920000.0,  # 9.2 Lakhs: strictly > 8.0L and <= 10.0L
        caste_category="General-EBC",
        course_name="B.Tech Computer Science",
        is_professional_course=True,
        institution_type=InstitutionType.GOVERNMENT,
        admission_mode=AdmissionMode.CAP,
        annual_tuition_fee=80000.0,
        annual_exam_fee=6000.0,
        attendance_percentage=85.0,
        previous_year_passed=True,
        digital_literacy=0.8,
        initial_awareness=0.8,
        document_readiness=0.8,
        financial_urgency=0.5,
        peer_network_support=0.7
    )

    engine = SimulationEngine()

    # Evaluation 1: Statutory mode (statutory ceiling 8 Lakhs)
    statutory_result = engine.run_step(cf_student, policy_mode="statutory")

    assert statutory_result.is_eligible is False
    assert statutory_result.estimated_fee_relief_inr == 0.0
    assert statutory_result.tuition_fee_relief_inr == 0.0
    assert statutory_result.exam_fee_relief_inr == 0.0
    assert statutory_result.net_payable_tuition_fee == 80000.0
    assert statutory_result.net_payable_exam_fee == 6000.0
    assert statutory_result.total_net_payable_fee == 86000.0
    assert statutory_result.final_simulation_state == SimulationState.REJECTED.value
    assert any("800,000" in reason or "income" in reason.lower() for reason in statutory_result.statutory_failure_reasons)

    # Evaluation 2: Counterfactual mode with 10 Lakh income ceiling
    counterfactual_config = DTEPolicyConfig(
        max_income_limit=1000000.0,
        policy_version="counterfactual-10L-cap"
    )
    cf_result = engine.run_step(
        cf_student,
        policy_mode="counterfactual",
        counterfactual_config=counterfactual_config
    )

    assert cf_result.is_eligible is True
    assert len(cf_result.statutory_failure_reasons) == 0
    assert cf_result.policy_mode == "counterfactual"
    assert cf_result.policy_version == "counterfactual-10L-cap"

    # Female candidate in Govt college under provisional GR 08.07.2024: 100% tuition and 100% exam fee waiver
    assert cf_result.tuition_fee_relief_inr == 80000.0
    assert cf_result.exam_fee_relief_inr == 6000.0
    assert cf_result.estimated_fee_relief_inr == 86000.0
    assert cf_result.net_payable_tuition_fee == 0.0
    assert cf_result.net_payable_exam_fee == 0.0
    assert cf_result.total_net_payable_fee == 0.0
    assert cf_result.final_simulation_state != SimulationState.REJECTED.value

    # Contrast deltas directly
    assert statutory_result.is_eligible is False and cf_result.is_eligible is True
    assert cf_result.estimated_fee_relief_inr - statutory_result.estimated_fee_relief_inr == 86000.0
    assert statutory_result.total_net_payable_fee - cf_result.total_net_payable_fee == 86000.0
    print("PASS: test_counterfactual_income_ceiling_scenario")

if __name__ == "__main__":
    test_eligible_student_simulation()
    test_statutory_check_separation_and_configurable_benefit()
    test_ineligible_income_and_management_quota()
    test_male_examination_fee_relief_and_net_payable()
    test_counterfactual_income_ceiling_scenario()
    print("All Phase 1 tests passed successfully!")
