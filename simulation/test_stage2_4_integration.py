"""
Stage 2.4 — Engine Code Integration & Test Verification Suite.

Comprehensive verification of:
1. Four Policy Modes: legacy_poc, statutory, override, counterfactual.
2. Mode resolution precedence, backward compatibility, and invalid combinations.
3. Itemized tuition and exam fee relief passthrough.
4. Stateless evaluation and dynamic re-evaluation across steps.
5. Nested Enum-safe JSON serialization.
6. API and Data Contract reconciliation.
7. Validation guards for non-finite rates, boundary conditions, and zero-division safety.
"""

import math
import json
import re
from contextlib import contextmanager
from typing import List

@contextmanager
def raises(expected_exception, match=None):
    try:
        yield
    except expected_exception as e:
        if match is not None and not re.search(match, str(e)):
            raise AssertionError(f"Expected regex {match!r} to match {str(e)!r}")
    else:
        raise AssertionError(f"Expected {expected_exception.__name__} was not raised")

from data.dhule_adapter import DhuleEducationDatasetAdapter
from simulation.persona_generator import SyntheticPersonaGenerator
from simulation.persona import (
    StudentPersona,
    InstitutionType,
    AdmissionMode,
    SimulationState,
    PersonalityTraits
)
from simulation.policy_rules import (
    RajarshiShahuPolicyEngine,
    DTEPolicyConfig,
    EpistemicStatus
)
from simulation.engine import (
    SimulationEngine,
    SimulationStepOutput,
    CohortSimulationResult,
    MultiStepSimulationResult,
    resolve_policy_parameters
)
from simulation.agent import StubLLMProvider
from backend.models import SimulationRequest, SimulationResponse
from backend.service import SimulationService


def _create_sample_eligible_persona(
    persona_id: str = "TEST-001",
    gender: str = "Female",
    tuition_fee: float = 60000.0,
    exam_fee: float = 4000.0,
    family_income: float = 400000.0,
    attendance: float = 85.0,
    admission_mode: AdmissionMode = AdmissionMode.CAP,
    institution_type: InstitutionType = InstitutionType.GOVERNMENT,
    is_orphan: bool = False
) -> StudentPersona:
    """Helper creating a fully deterministic, eligible test persona with explicit tuition and exam fees."""
    p = StudentPersona(
        persona_id=persona_id,
        name=f"Test Student {persona_id}",
        age=19,
        gender=gender,
        district="Dhule",
        is_maharashtra_domicile=True,
        family_income=family_income,
        caste_category="OPEN",
        first_generation_learner=False,
        is_orphan=is_orphan,
        course_name="B.E. Computer Engineering",
        is_professional_course=True,
        institution_type=institution_type,
        admission_mode=admission_mode,
        annual_tuition_fee=tuition_fee,
        annual_exam_fee=exam_fee,
        attendance_percentage=attendance,
        previous_year_passed=True,
        academic_gap_years=0,
        is_first_year=False,
        family_beneficiaries_count=0,
        has_other_scholarship=False,
        digital_literacy=0.70,
        initial_awareness=0.75,
        document_readiness=0.80,
        institutional_trust=0.70,
        personality=PersonalityTraits()
    )
    return p


# ==============================================================================
# SECTION 1: Policy Mode Contract & Backward Compatibility (T01 - T10)
# ==============================================================================

def test_t01_legacy_poc_cohort_default():
    """T01: Omitted mode in run_cohort defaults to legacy_poc with 50% tuition and strictly 0% exam fee."""
    p = _create_sample_eligible_persona("T01-01", gender="Female", tuition_fee=60000.0, exam_fee=4000.0)
    engine = SimulationEngine()
    result = engine.run_cohort([p], seed=42)

    assert result.policy_mode == "legacy_poc"
    assert result.is_counterfactual is False
    assert result.assumed_reimbursement_rate == 0.50
    assert result.eligible_count == 1
    assert result.total_tuition_fee_relief_inr == 30000.0
    assert result.total_exam_fee_relief_inr == 0.0  # Legacy PoC strictly gives 0 exam relief
    assert result.total_estimated_fee_relief_inr == 30000.0
    print("PASS: test_t01_legacy_poc_cohort_default")


def test_t02_legacy_poc_multistep_default():
    """T02: Omitted mode in run_multistep_cohort defaults to legacy_poc with 50% tuition and 0% exam fee."""
    p = _create_sample_eligible_persona("T02-01", gender="Male", tuition_fee=80000.0, exam_fee=6000.0)
    engine = SimulationEngine()
    result = engine.run_multistep_cohort([p], total_steps=2, seed=42, enable_social_interaction=False)

    assert result.policy_mode == "legacy_poc"
    assert result.is_counterfactual is False
    step1 = result.step_cohort_results[0]
    assert step1.total_tuition_fee_relief_inr == 40000.0
    assert step1.total_exam_fee_relief_inr == 0.0
    assert step1.total_estimated_fee_relief_inr == 40000.0
    print("PASS: test_t02_legacy_poc_multistep_default")


def test_t03_run_step_statutory_default():
    """T03: Omitted mode and rate in run_step resolves to statutory (female 100%, male 50%)."""
    engine = SimulationEngine()
    female_p = _create_sample_eligible_persona("T03-F", gender="Female", tuition_fee=50000.0, exam_fee=2000.0)
    male_p = _create_sample_eligible_persona("T03-M", gender="Male", tuition_fee=50000.0, exam_fee=2000.0)

    out_f = engine.run_step(female_p, step_index=1)
    out_m = engine.run_step(male_p, step_index=1)

    assert out_f.policy_mode == "statutory"
    assert out_f.is_eligible is True
    assert out_f.tuition_fee_relief_inr == 50000.0  # 100% waiver
    assert out_f.exam_fee_relief_inr == 2000.0     # 100% waiver
    assert out_f.estimated_fee_relief_inr == 52000.0

    assert out_m.policy_mode == "statutory"
    assert out_m.is_eligible is True
    assert out_m.tuition_fee_relief_inr == 25000.0  # 50% waiver
    assert out_m.exam_fee_relief_inr == 1000.0     # 50% waiver (code baseline)
    assert out_m.estimated_fee_relief_inr == 26000.0
    print("PASS: test_t03_run_step_statutory_default")


def test_t04_explicit_0_50_override():
    """T04: Explicit override mode with rate 0.50 gives 50% tuition AND 50% exam fee relief."""
    p = _create_sample_eligible_persona("T04-01", gender="Female", tuition_fee=60000.0, exam_fee=4000.0)
    engine = SimulationEngine()
    result = engine.run_cohort([p], policy_mode="override", assumed_reimbursement_rate=0.50, seed=42)

    assert result.policy_mode == "override"
    assert result.is_counterfactual is False
    assert result.total_tuition_fee_relief_inr == 30000.0
    assert result.total_exam_fee_relief_inr == 2000.0  # Override applies 50% to exam fees too!
    assert result.total_estimated_fee_relief_inr == 32000.0
    print("PASS: test_t04_explicit_0_50_override")


def test_t05_statutory_female_100_percent_waiver():
    """T05: Statutory mode provides 100% tuition and 100% exam fee waiver for eligible females."""
    p = _create_sample_eligible_persona("T05-F", gender="Female", tuition_fee=100000.0, exam_fee=5000.0)
    engine = SimulationEngine()
    result = engine.run_cohort([p], policy_mode="statutory", seed=42)

    assert result.policy_mode == "statutory"
    assert result.total_tuition_fee_relief_inr == 100000.0
    assert result.total_exam_fee_relief_inr == 5000.0
    assert result.total_estimated_fee_relief_inr == 105000.0
    print("PASS: test_t05_statutory_female_100_percent_waiver")


def test_t06_statutory_male_tiered():
    """T06: Statutory mode provides 50% tuition and 50% exam fee relief for eligible males."""
    p = _create_sample_eligible_persona("T06-M", gender="Male", tuition_fee=100000.0, exam_fee=5000.0)
    engine = SimulationEngine()
    result = engine.run_cohort([p], policy_mode="statutory", seed=42)

    assert result.policy_mode == "statutory"
    assert result.total_tuition_fee_relief_inr == 50000.0
    assert result.total_exam_fee_relief_inr == 2500.0
    assert result.total_estimated_fee_relief_inr == 52500.0
    print("PASS: test_t06_statutory_male_tiered")


def test_t07_custom_rate_override():
    """T07: Override mode with rate=0.75 scales both fee components to 75%."""
    p = _create_sample_eligible_persona("T07-01", gender="Female", tuition_fee=40000.0, exam_fee=4000.0)
    engine = SimulationEngine()
    result = engine.run_cohort([p], policy_mode="override", assumed_reimbursement_rate=0.75, seed=42)

    assert result.policy_mode == "override"
    assert result.total_tuition_fee_relief_inr == 30000.0
    assert result.total_exam_fee_relief_inr == 3000.0
    assert result.total_estimated_fee_relief_inr == 33000.0
    print("PASS: test_t07_custom_rate_override")


def test_t08_explicit_0_0_rate_override():
    """T08: Explicit 0.0 rate override marks applicant eligible but grants INR 0.00 relief."""
    p = _create_sample_eligible_persona("T08-01", gender="Female", tuition_fee=40000.0, exam_fee=4000.0)
    engine = SimulationEngine()
    result = engine.run_cohort([p], policy_mode="override", assumed_reimbursement_rate=0.0, seed=42)

    assert result.policy_mode == "override"
    assert result.eligible_count == 1
    assert result.total_tuition_fee_relief_inr == 0.0
    assert result.total_exam_fee_relief_inr == 0.0
    assert result.total_estimated_fee_relief_inr == 0.0
    print("PASS: test_t08_explicit_0_0_rate_override")


def test_t09_config_gate_propagation():
    """T09: Custom policy_config propagating relaxed income threshold in statutory mode."""
    # Student with 10L income is ineligible under statutory 8L cap
    p_high_income = _create_sample_eligible_persona("T09-01", family_income=1000000.0, tuition_fee=50000.0)
    engine = SimulationEngine()

    res_default = engine.run_cohort([p_high_income], policy_mode="statutory", seed=42)
    assert res_default.eligible_count == 0

    # Relax income ceiling to 12L via policy_config
    relaxed_cfg = DTEPolicyConfig(max_income_limit=1200000.0)
    res_relaxed = engine.run_cohort([p_high_income], policy_mode="statutory", policy_config=relaxed_cfg, seed=42)
    assert res_relaxed.eligible_count == 1
    assert res_relaxed.total_estimated_fee_relief_inr > 0.0
    print("PASS: test_t09_config_gate_propagation")


def test_t10_counterfactual_mode_benefit_rate():
    """T10: Counterfactual mode modifies benefit rates without raising conflict error."""
    p = _create_sample_eligible_persona("T10-M", gender="Male", tuition_fee=100000.0, exam_fee=4000.0)
    custom_cfg = DTEPolicyConfig(male_tier2_tuition_rate=0.75, male_exam_rate=0.75)
    engine = SimulationEngine()

    res = engine.run_cohort([p], policy_mode="counterfactual", policy_config=custom_cfg, seed=42)
    assert res.policy_mode == "counterfactual"
    assert res.is_counterfactual is True
    assert res.total_tuition_fee_relief_inr == 75000.0
    assert res.total_exam_fee_relief_inr == 3000.0
    assert res.total_estimated_fee_relief_inr == 78000.0
    print("PASS: test_t10_counterfactual_mode_benefit_rate")


# ==============================================================================
# SECTION 2: Stateless Evaluation & Itemized Passthrough (T11 - T16)
# ==============================================================================

def test_t11_stateless_policy_evaluation_invariant():
    """T11: Policy evaluation is stateless and strictly idempotent across repeated evaluations."""
    p = _create_sample_eligible_persona("T11-01", gender="Female", tuition_fee=50000.0)
    engine = SimulationEngine()

    out1 = engine.run_step(p, step_index=1, policy_mode="statutory")
    out2 = engine.run_step(p, step_index=2, policy_mode="statutory")

    assert out1.is_eligible == out2.is_eligible
    assert out1.estimated_fee_relief_inr == out2.estimated_fee_relief_inr
    assert out1.statutory_failure_reasons == out2.statutory_failure_reasons
    print("PASS: test_t11_stateless_policy_evaluation_invariant")


def test_t12_dynamic_reevaluation_mid_run():
    """T12: When persona attributes drop mid-simulation, stateless evaluation immediately reflects it."""
    p = _create_sample_eligible_persona("T12-01", gender="Male", tuition_fee=50000.0, attendance=80.0)
    engine = SimulationEngine()

    out_pass = engine.run_step(p, step_index=1, policy_mode="statutory")
    assert out_pass.is_eligible is True

    # Attendance drops to 60%
    p.attendance_percentage = 60.0
    out_fail = engine.run_step(p, step_index=2, policy_mode="statutory")
    assert out_fail.is_eligible is False
    assert out_fail.estimated_fee_relief_inr == 0.0
    assert any("below statutory requirement" in r for r in out_fail.statutory_failure_reasons)
    print("PASS: test_t12_dynamic_reevaluation_mid_run")


def test_t13_gender_concession_parity():
    """T13: Verify female 100% vs male 50% concession under statutory baseline."""
    female_p = _create_sample_eligible_persona("T13-F", gender="Female", tuition_fee=60000.0, exam_fee=4000.0)
    male_p = _create_sample_eligible_persona("T13-M", gender="Male", tuition_fee=60000.0, exam_fee=4000.0)
    engine = SimulationEngine()

    out_f = engine.run_step(female_p, policy_mode="statutory")
    out_m = engine.run_step(male_p, policy_mode="statutory")

    assert out_f.tuition_fee_relief_inr == 60000.0
    assert out_m.tuition_fee_relief_inr == 30000.0
    print("PASS: test_t13_gender_concession_parity")


def test_t14_orphan_concession_parity():
    """T14: Verify orphan concession grants 100% waiver regardless of gender."""
    orphan_male = _create_sample_eligible_persona("T14-OM", gender="Male", tuition_fee=60000.0, exam_fee=4000.0, is_orphan=True)
    engine = SimulationEngine()

    out_om = engine.run_step(orphan_male, policy_mode="statutory")
    assert out_om.tuition_fee_relief_inr == 60000.0  # 100% waiver for orphan
    assert out_om.exam_fee_relief_inr == 4000.0
    print("PASS: test_t14_orphan_concession_parity")


def test_t15_itemized_relief_passthrough():
    """T15: SimulationStepOutput carries granular relief breakdown and policy evaluation details."""
    p = _create_sample_eligible_persona("T15-01", gender="Female", tuition_fee=70000.0, exam_fee=3000.0)
    engine = SimulationEngine()
    step_out = engine.run_step(p, policy_mode="statutory")

    assert hasattr(step_out, "tuition_fee_relief_inr")
    assert hasattr(step_out, "exam_fee_relief_inr")
    assert hasattr(step_out, "policy_mode")
    assert hasattr(step_out, "is_counterfactual")
    assert hasattr(step_out, "policy_result")
    assert step_out.tuition_fee_relief_inr == 70000.0
    assert step_out.exam_fee_relief_inr == 3000.0
    assert step_out.policy_mode == "statutory"
    assert step_out.policy_result is not None
    print("PASS: test_t15_itemized_relief_passthrough")


def test_t16_nested_enum_safe_json_serialization():
    """T16: Nested Enum fields in personas and policy results serialize safely without TypeError."""
    p = _create_sample_eligible_persona("T16-01", institution_type=InstitutionType.PRIVATE_UNAIDED, admission_mode=AdmissionMode.CAP)
    engine = SimulationEngine()

    step_out = engine.run_step(p, policy_mode="statutory")
    step_dict = step_out.to_dict()
    # Must serialize via json.dumps without error
    step_json = json.dumps(step_dict)
    assert "Private-Unaided" in step_json or "CAP" in step_json

    # Multi-step result serialization
    multi_res = engine.run_multistep_cohort([p], total_steps=1, policy_mode="statutory", enable_social_interaction=False)
    multi_json = multi_res.to_json()
    assert len(multi_json) > 0
    parsed = json.loads(multi_json)
    assert parsed["policy_mode"] == "statutory"
    print("PASS: test_t16_nested_enum_safe_json_serialization")


# ==============================================================================
# SECTION 3: API Contract & Reconciliation (T17 - T22)
# ==============================================================================

def test_t17_api_contract_and_metadata():
    """T17: Backend API service maps simulation results to extended DTO contract cleanly."""
    req = SimulationRequest(
        district="Dhule",
        cohort_size=5,
        simulation_steps=1,
        seed=42,
        use_gemini=False,
        policy_mode="legacy_poc"
    )
    resp: SimulationResponse = SimulationService.execute_simulation(req)

    assert resp.metadata.district == "Dhule"
    assert resp.metadata.resolved_policy_mode == "legacy_poc"
    assert resp.metadata.is_counterfactual is False
    assert resp.metadata.policy_version == "2024.1-provisional"
    assert resp.aggregate_metrics.total_personas == 5
    assert hasattr(resp.aggregate_metrics, "total_tuition_fee_relief_inr")
    assert hasattr(resp.aggregate_metrics, "total_exam_fee_relief_inr")
    assert hasattr(resp.aggregate_metrics, "cohort_effective_relief_rate")

    for p_out in resp.personas:
        assert hasattr(p_out, "reimbursement_rate")
        assert hasattr(p_out, "tuition_fee_relief_inr")
        assert hasattr(p_out, "exam_fee_relief_inr")
        assert hasattr(p_out, "policy_details")
    print("PASS: test_t17_api_contract_and_metadata")


def test_t18_aggregate_reconciliation():
    """T18: Total estimated relief matches sum of tuition relief and exam relief."""
    p1 = _create_sample_eligible_persona("T18-01", gender="Female", tuition_fee=40000.0, exam_fee=2000.0)
    p2 = _create_sample_eligible_persona("T18-02", gender="Male", tuition_fee=60000.0, exam_fee=3000.0)
    engine = SimulationEngine()
    result = engine.run_cohort([p1, p2], policy_mode="statutory", seed=42)

    expected_tuition = 40000.0 + 30000.0
    expected_exam = 2000.0 + 1500.0
    expected_total = expected_tuition + expected_exam

    assert result.total_tuition_fee_relief_inr == expected_tuition
    assert result.total_exam_fee_relief_inr == expected_exam
    assert result.total_estimated_fee_relief_inr == expected_total
    print("PASS: test_t18_aggregate_reconciliation")


def test_t19_ineligible_adoption_guard():
    """T19: Ineligible persona strictly receives INR 0 relief and transitions to REJECTED."""
    p_ineligible = _create_sample_eligible_persona("T19-01", family_income=900000.0)  # > 8L
    engine = SimulationEngine()
    step_out = engine.run_step(p_ineligible, policy_mode="statutory")

    assert step_out.is_eligible is False
    assert step_out.estimated_fee_relief_inr == 0.0
    assert step_out.tuition_fee_relief_inr == 0.0
    assert step_out.exam_fee_relief_inr == 0.0
    assert step_out.final_simulation_state == "REJECTED"
    print("PASS: test_t19_ineligible_adoption_guard")


def test_t20_large_fee_safety():
    """T20: Large tuition and exam fees calculate accurately without overflow or precision loss."""
    p_large = _create_sample_eligible_persona("T20-01", gender="Female", tuition_fee=500000.0, exam_fee=25000.0)
    engine = SimulationEngine()
    step_out = engine.run_step(p_large, policy_mode="statutory")

    assert step_out.tuition_fee_relief_inr == 500000.0
    assert step_out.exam_fee_relief_inr == 25000.0
    assert step_out.estimated_fee_relief_inr == 525000.0
    print("PASS: test_t20_large_fee_safety")


# ==============================================================================
# SECTION 4: Input Validation & Boundary Guards (V01 - V12)
# ==============================================================================

def test_v01_inf_rate_rejected():
    """V01: Positive infinity rate raises ValueError."""
    with raises(ValueError, match="non-finite"):
        resolve_policy_parameters("run_cohort", policy_mode="override", assumed_reimbursement_rate=float("inf"), policy_config=None)
    print("PASS: test_v01_inf_rate_rejected")


def test_v02_neg_inf_rate_rejected():
    """V02: Negative infinity rate raises ValueError."""
    with raises(ValueError, match="non-finite"):
        resolve_policy_parameters("run_cohort", policy_mode="override", assumed_reimbursement_rate=float("-inf"), policy_config=None)
    print("PASS: test_v02_neg_inf_rate_rejected")


def test_v03_non_numeric_rate_rejected():
    """V03: Non-numeric reimbursement rate types raise ValueError."""
    with raises(ValueError, match="must be numeric"):
        resolve_policy_parameters("run_cohort", policy_mode="override", assumed_reimbursement_rate="0.50", policy_config=None)

    with raises(ValueError, match="cannot be a boolean"):
        resolve_policy_parameters("run_cohort", policy_mode="override", assumed_reimbursement_rate=True, policy_config=None)
    print("PASS: test_v03_non_numeric_rate_rejected")


def test_v04_invalid_mode_rejected():
    """V04: Unknown or malformed policy_mode raises ValueError."""
    with raises(ValueError, match="Invalid policy_mode"):
        resolve_policy_parameters("run_cohort", policy_mode="unsupported_mode", assumed_reimbursement_rate=None, policy_config=None)
    print("PASS: test_v04_invalid_mode_rejected")


def test_v05_empty_cohort_safety():
    """V05: Empty cohort input is handled cleanly without ZeroDivisionError."""
    engine = SimulationEngine()
    result = engine.run_cohort([], policy_mode="statutory", seed=42)

    assert result.total_personas == 0
    assert result.eligible_count == 0
    assert result.eligibility_rate == 0.0
    assert result.total_estimated_fee_relief_inr == 0.0
    assert result.cohort_effective_relief_rate == 0.0
    print("PASS: test_v05_empty_cohort_safety")


def test_v06_zero_eligible_safety():
    """V06: Cohort with zero eligible personas calculates averages safely without ZeroDivisionError."""
    p_inelig1 = _create_sample_eligible_persona("V06-01", family_income=900000.0)
    p_inelig2 = _create_sample_eligible_persona("V06-02", family_income=1200000.0)
    engine = SimulationEngine()
    result = engine.run_cohort([p_inelig1, p_inelig2], policy_mode="statutory", seed=42)

    assert result.total_personas == 2
    assert result.eligible_count == 0
    assert result.eligibility_rate == 0.0
    assert result.average_fee_relief_per_eligible_inr == 0.0
    assert result.cohort_effective_relief_rate == 0.0
    print("PASS: test_v06_zero_eligible_safety")


def test_v07_seed_reproducibility():
    """V07: Deterministic reproducibility across repeated multi-step runs."""
    p1 = _create_sample_eligible_persona("V07-01")
    p2 = _create_sample_eligible_persona("V07-01")
    engine = SimulationEngine()

    run1 = engine.run_multistep_cohort([p1], total_steps=2, seed=123, policy_mode="statutory", enable_social_interaction=False)
    run2 = engine.run_multistep_cohort([p2], total_steps=2, seed=123, policy_mode="statutory", enable_social_interaction=False)

    assert run1.to_dict() == run2.to_dict()
    print("PASS: test_v07_seed_reproducibility")


def test_v08_statutory_config_benefit_rate_guard():
    """V08: Attempting to modify statutory benefit rates under policy_mode='statutory' raises ValueError."""
    custom_cfg = DTEPolicyConfig(male_tier2_tuition_rate=0.70)
    with raises(ValueError, match="Cannot modify statutory benefit rates in policy_mode='statutory'"):
        resolve_policy_parameters("run_cohort", policy_mode="statutory", assumed_reimbursement_rate=None, policy_config=custom_cfg)
    print("PASS: test_v08_statutory_config_benefit_rate_guard")


def test_v09_counterfactual_default_config():
    """V09: policy_mode='counterfactual' with default policy_config is permitted and sets is_counterfactual=True."""
    mode, rate, cfg, is_cf = resolve_policy_parameters("run_cohort", policy_mode="counterfactual", assumed_reimbursement_rate=None, policy_config=None)
    assert mode == "counterfactual"
    assert is_cf is True
    print("PASS: test_v09_counterfactual_default_config")


def test_v10_override_mode_missing_rate():
    """V10: policy_mode='override' without a rate raises ValueError."""
    with raises(ValueError, match="policy_mode='override' requires an explicit assumed_reimbursement_rate"):
        resolve_policy_parameters("run_cohort", policy_mode="override", assumed_reimbursement_rate=None, policy_config=None)
    print("PASS: test_v10_override_mode_missing_rate")


def test_v11_statutory_mode_with_rate_rejected():
    """V11: Passing explicit assumed_reimbursement_rate under policy_mode='statutory' raises ValueError."""
    with raises(ValueError, match="Explicit assumed_reimbursement_rate cannot be provided when policy_mode='statutory'"):
        resolve_policy_parameters("run_cohort", policy_mode="statutory", assumed_reimbursement_rate=0.50, policy_config=None)
    print("PASS: test_v11_statutory_mode_with_rate_rejected")


def test_v12_rate_out_of_bounds_rejected():
    """V12: Reimbursement rate < 0.0 or > 1.0 raises ValueError."""
    with raises(ValueError, match="outside the valid range"):
        resolve_policy_parameters("run_cohort", policy_mode="override", assumed_reimbursement_rate=1.5, policy_config=None)

    with raises(ValueError, match="outside the valid range"):
        resolve_policy_parameters("run_cohort", policy_mode="override", assumed_reimbursement_rate=-0.1, policy_config=None)
    print("PASS: test_v12_rate_out_of_bounds_rejected")


if __name__ == "__main__":
    test_t01_legacy_poc_cohort_default()
    test_t02_legacy_poc_multistep_default()
    test_t03_run_step_statutory_default()
    test_t04_explicit_0_50_override()
    test_t05_statutory_female_100_percent_waiver()
    test_t06_statutory_male_tiered()
    test_t07_custom_rate_override()
    test_t08_explicit_0_0_rate_override()
    test_t09_config_gate_propagation()
    test_t10_counterfactual_mode_benefit_rate()
    test_t11_stateless_policy_evaluation_invariant()
    test_t12_dynamic_reevaluation_mid_run()
    test_t13_gender_concession_parity()
    test_t14_orphan_concession_parity()
    test_t15_itemized_relief_passthrough()
    test_t16_nested_enum_safe_json_serialization()
    test_t17_api_contract_and_metadata()
    test_t18_aggregate_reconciliation()
    test_t19_ineligible_adoption_guard()
    test_t20_large_fee_safety()
    test_v01_inf_rate_rejected()
    test_v02_neg_inf_rate_rejected()
    test_v03_non_numeric_rate_rejected()
    test_v04_invalid_mode_rejected()
    test_v05_empty_cohort_safety()
    test_v06_zero_eligible_safety()
    test_v07_seed_reproducibility()
    test_v08_statutory_config_benefit_rate_guard()
    test_v09_counterfactual_default_config()
    test_v10_override_mode_missing_rate()
    test_v11_statutory_mode_with_rate_rejected()
    test_v12_rate_out_of_bounds_rejected()
    print("\nALL 32 STAGE 2.4 INTEGRATION & VALIDATION TESTS PASSED SUCCESSFULLY!")
