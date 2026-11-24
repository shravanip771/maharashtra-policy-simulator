"""
Stage 2.4 DTE Policy Integration Test Suite.
Validates the four canonical policy modes, precedence rules, counterfactual configurations,
provisional male 50% examination fee relief, net payable fee serialization,
multi-step cohort execution, and backward compatibility.
Total: Exactly 42 Tests (32 Core Integration Tests + 10 Review Findings & Regression Tests).
"""

import json
import pytest
from typing import Dict, Any

from simulation.persona import StudentPersona, InstitutionType, AdmissionMode
from simulation.policy_rules import RajarshiShahuPolicyEngine, DTEPolicyConfig
from simulation.engine import (
    SimulationEngine,
    SimulationStepOutput,
    CohortSimulationResult,
    resolve_policy_parameters,
    resolve_policy_mode_and_rate,
)
from backend.models import SimulationRequest, PersonaOutput
from backend.service import SimulationService


def make_persona(
    persona_id: str = "TEST-STU-01",
    name: str = "Test Student",
    age: int = 20,
    gender: str = "Female",
    district: str = "Dhule",
    is_maharashtra_domicile: bool = True,
    family_income: float = 300000.0,
    caste_category: str = "General-EBC",
    institution_type: InstitutionType = InstitutionType.PRIVATE_UNAIDED,
    admission_mode: AdmissionMode = AdmissionMode.CAP,
    annual_tuition_fee: float = 80000.0,
    annual_exam_fee: float = 4000.0,
    attendance_percentage: float = 80.0,
    previous_year_passed: bool = True,
    academic_gap_years: int = 0,
    family_beneficiaries_count: int = 0,
    has_other_scholarship: bool = False,
    is_orphan: bool = False,
    **kwargs: Any,
) -> StudentPersona:
    """Helper to instantiate a fully valid student persona."""
    return StudentPersona(
        persona_id=persona_id,
        name=name,
        age=age,
        gender=gender,
        district=district,
        is_maharashtra_domicile=is_maharashtra_domicile,
        family_income=family_income,
        caste_category=caste_category,
        institution_type=institution_type,
        admission_mode=admission_mode,
        annual_tuition_fee=annual_tuition_fee,
        annual_exam_fee=annual_exam_fee,
        attendance_percentage=attendance_percentage,
        previous_year_passed=previous_year_passed,
        academic_gap_years=academic_gap_years,
        family_beneficiaries_count=family_beneficiaries_count,
        has_other_scholarship=has_other_scholarship,
        is_orphan=is_orphan,
        **kwargs,
    )


# ==============================================================================
# CLASS 1: Policy Mode Resolution and Precedence Rules (9 Tests)
# ==============================================================================

class TestPolicyModeResolutionAndPrecedence:
    def test_default_mode_when_omitted_is_legacy_poc(self):
        """1. resolve_policy_parameters() defaults to legacy_poc with 0.50 rate when omitted."""
        mode, rate, cfg = resolve_policy_parameters()
        assert mode == "legacy_poc"
        assert rate == 0.50
        assert cfg is None

    def test_none_policy_mode_resolves_to_legacy_poc(self):
        """2. Passing policy_mode=None safely resolves to legacy_poc."""
        mode, rate, cfg = resolve_policy_parameters(policy_mode=None)
        assert mode == "legacy_poc"
        assert rate == 0.50
        assert cfg is None

    def test_mode_aliases_resolve_correctly(self):
        """3. Canonical aliases 'poc_legacy' and 'statutory_dte' resolve correctly."""
        mode_poc, rate_poc, _ = resolve_policy_parameters(policy_mode="poc_legacy")
        assert mode_poc == "legacy_poc"
        assert rate_poc == 0.50

        mode_stat, rate_stat, cfg_stat = resolve_policy_parameters(policy_mode="statutory_dte")
        assert mode_stat == "statutory"
        assert rate_stat is None
        assert isinstance(cfg_stat, DTEPolicyConfig)

    def test_statutory_mode_resolution(self):
        """4. 'statutory' mode returns None rate and default DTEPolicyConfig."""
        mode, rate, cfg = resolve_policy_parameters(policy_mode="statutory")
        assert mode == "statutory"
        assert rate is None
        assert isinstance(cfg, DTEPolicyConfig)
        assert cfg.max_income_limit == 800000.0

    def test_statutory_mode_rejects_override_rate(self):
        """5. Passing override rate in statutory mode raises ValueError."""
        with pytest.raises(ValueError, match="override_reimbursement_rate cannot be specified in 'statutory' mode"):
            resolve_policy_parameters(policy_mode="statutory", override_reimbursement_rate=0.75)
        with pytest.raises(ValueError, match="assumed_reimbursement_rate cannot be specified in 'statutory' mode"):
            resolve_policy_parameters(policy_mode="statutory", assumed_reimbursement_rate=0.75)

    def test_override_mode_requires_valid_rate(self):
        """6. 'override' mode requires explicit rate in [0.0, 1.0]."""
        with pytest.raises(ValueError, match="override_reimbursement_rate must be provided"):
            resolve_policy_parameters(policy_mode="override")
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            resolve_policy_parameters(policy_mode="override", override_reimbursement_rate=1.5)
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            resolve_policy_parameters(policy_mode="override", override_reimbursement_rate=-0.2)

    def test_override_mode_valid_rate_succeeds(self):
        """7. 'override' mode with valid rate succeeds and returns float rate."""
        mode, rate, cfg = resolve_policy_parameters(policy_mode="override", override_reimbursement_rate=0.65)
        assert mode == "override"
        assert rate == 0.65
        assert cfg is None

    def test_counterfactual_mode_rejects_override_rate(self):
        """8. Combining 'counterfactual' mode with override rate raises ValueError."""
        with pytest.raises(ValueError, match="override_reimbursement_rate cannot be specified in 'counterfactual' mode"):
            resolve_policy_parameters(policy_mode="counterfactual", override_reimbursement_rate=0.70)
        with pytest.raises(ValueError, match="assumed_reimbursement_rate cannot be specified in 'counterfactual' mode"):
            resolve_policy_parameters(policy_mode="counterfactual", assumed_reimbursement_rate=0.70)

    def test_unknown_policy_mode_raises_value_error(self):
        """9. Unrecognized policy mode raises descriptive ValueError."""
        with pytest.raises(ValueError, match="Unknown policy_mode 'hypothetical_mode'"):
            resolve_policy_parameters(policy_mode="hypothetical_mode")


# ==============================================================================
# CLASS 2: Backward Compatibility Alias and Existing Interface (3 Tests)
# ==============================================================================

class TestBackwardCompatibilityAlias:
    def test_resolve_policy_mode_and_rate_alias_identical_to_resolve_policy_parameters(self):
        """10. resolve_policy_mode_and_rate is identical alias to resolve_policy_parameters."""
        assert resolve_policy_mode_and_rate is resolve_policy_parameters
        r1 = resolve_policy_parameters(policy_mode="statutory")
        r2 = resolve_policy_mode_and_rate(policy_mode="statutory")
        assert r1 == r2

    def test_run_step_legacy_poc_backward_compatibility(self):
        """11. Calling run_step without policy_mode retains flat 50% legacy PoC calculation."""
        persona = make_persona("P-LEG-1", annual_tuition_fee=80000.0, annual_exam_fee=4000.0)
        engine = SimulationEngine()
        step_out = engine.run_step(persona)
        assert step_out.policy_mode == "legacy_poc"
        assert step_out.reimbursement_percentage == 0.50
        assert step_out.estimated_fee_relief_inr == 42000.0  # 50% of (80000 + 4000)

    def test_run_cohort_legacy_poc_backward_compatibility(self):
        """12. Calling run_cohort without policy_mode retains legacy PoC aggregate results."""
        personas = [make_persona(f"P-LEG-C{i}") for i in range(3)]
        engine = SimulationEngine()
        cohort_res = engine.run_cohort(personas)
        assert cohort_res.policy_mode == "legacy_poc"
        assert cohort_res.assumed_reimbursement_rate == 0.50


# ==============================================================================
# CLASS 3: Validated Counterfactual Dictionary Conversion (5 Tests)
# ==============================================================================

class TestCounterfactualConfigurationConversion:
    def test_counterfactual_with_dte_policy_config_instance(self):
        """13. Passing DTEPolicyConfig instance directly is supported in counterfactual mode."""
        cfg = DTEPolicyConfig(max_income_limit=1200000.0, policy_version="custom-12L")
        mode, rate, resolved_cfg = resolve_policy_parameters(
            policy_mode="counterfactual", counterfactual_config=cfg
        )
        assert mode == "counterfactual"
        assert rate is None
        assert resolved_cfg.max_income_limit == 1200000.0
        assert resolved_cfg.policy_version == "custom-12L"

    def test_counterfactual_with_valid_dict_conversion(self):
        """14. Valid dictionary converts into DTEPolicyConfig with overridden parameters."""
        dict_cfg = {"max_income_limit": 1000000.0, "male_exam_rate": 0.60}
        mode, rate, resolved_cfg = resolve_policy_parameters(
            policy_mode="counterfactual", counterfactual_config=dict_cfg
        )
        assert mode == "counterfactual"
        assert isinstance(resolved_cfg, DTEPolicyConfig)
        assert resolved_cfg.max_income_limit == 1000000.0
        assert resolved_cfg.male_exam_rate == 0.60
        assert resolved_cfg.income_slab_lower == 250000.0  # preserved baseline default

    def test_counterfactual_with_unknown_dict_keys_raises_value_error(self):
        """15. Unknown dictionary keys in counterfactual_config are strictly rejected."""
        with pytest.raises(ValueError, match="Invalid counterfactual parameter"):
            resolve_policy_parameters(
                policy_mode="counterfactual",
                counterfactual_config={"unsupported_custom_rule": True},
            )

    def test_counterfactual_with_negative_income_raises_value_error(self):
        """16. Negative max_income_limit in counterfactual_config raises ValueError."""
        with pytest.raises(ValueError, match="max_income_limit cannot be negative"):
            resolve_policy_parameters(
                policy_mode="counterfactual",
                counterfactual_config={"max_income_limit": -50000.0},
            )

    def test_counterfactual_with_invalid_rate_raises_value_error(self):
        """17. Out-of-bounds rate in counterfactual_config raises ValueError."""
        with pytest.raises(ValueError, match="female_tuition_rate must be between 0.0 and 1.0"):
            resolve_policy_parameters(
                policy_mode="counterfactual",
                counterfactual_config={"female_tuition_rate": 1.40},
            )


# ==============================================================================
# CLASS 4: Statutory Fee Calculations & Itemization (5 Tests)
# ==============================================================================

class TestStatutoryFeeCalculationsAndItemization:
    def test_female_student_100_percent_tuition_and_exam_relief(self):
        """18. Eligible female candidate receives 100% tuition and 100% exam fee relief."""
        persona = make_persona(
            "FEMALE-01",
            gender="Female",
            annual_tuition_fee=85000.0,
            annual_exam_fee=5000.0,
        )
        engine = SimulationEngine()
        step_out = engine.run_step(persona, policy_mode="statutory")
        assert step_out.is_eligible is True
        assert step_out.tuition_fee_relief_inr == 85000.0
        assert step_out.exam_fee_relief_inr == 5000.0
        assert step_out.estimated_fee_relief_inr == 90000.0
        assert step_out.net_payable_tuition_fee == 0.0
        assert step_out.net_payable_exam_fee == 0.0
        assert step_out.total_net_payable_fee == 0.0

    def test_male_student_provisional_50_percent_exam_relief(self):
        """19. Male candidate receives 50% examination fee relief with verified net payable."""
        persona = make_persona(
            "MALE-EXAM-01",
            gender="Male",
            family_income=500000.0,
            annual_tuition_fee=60000.0,
            annual_exam_fee=6000.0,
        )
        engine = SimulationEngine()
        step_out = engine.run_step(persona, policy_mode="statutory")
        assert step_out.is_eligible is True
        assert step_out.exam_fee_relief_inr == 3000.0  # 50% of 6000
        assert step_out.net_payable_exam_fee == 3000.0

    def test_male_student_tier1_govt_tuition_relief(self):
        """20. Male candidate with income <= 2.5L in Govt college gets 100% tuition and 50% exam relief."""
        persona = make_persona(
            "MALE-GOVT-T1",
            gender="Male",
            family_income=200000.0,
            institution_type=InstitutionType.GOVERNMENT,
            annual_tuition_fee=50000.0,
            annual_exam_fee=4000.0,
        )
        engine = SimulationEngine()
        step_out = engine.run_step(persona, policy_mode="statutory")
        assert step_out.is_eligible is True
        assert step_out.tuition_fee_relief_inr == 50000.0
        assert step_out.net_payable_tuition_fee == 0.0
        assert step_out.exam_fee_relief_inr == 2000.0
        assert step_out.net_payable_exam_fee == 2000.0
        assert step_out.total_net_payable_fee == 2000.0

    def test_male_student_tier1_pvt_tuition_relief(self):
        """21. Male candidate with income <= 2.5L in Private college gets 50% tuition and 50% exam relief."""
        persona = make_persona(
            "MALE-PVT-T1",
            gender="Male",
            family_income=220000.0,
            institution_type=InstitutionType.PRIVATE_UNAIDED,
            annual_tuition_fee=100000.0,
            annual_exam_fee=6000.0,
        )
        engine = SimulationEngine()
        step_out = engine.run_step(persona, policy_mode="statutory")
        assert step_out.is_eligible is True
        assert step_out.tuition_fee_relief_inr == 50000.0
        assert step_out.net_payable_tuition_fee == 50000.0
        assert step_out.exam_fee_relief_inr == 3000.0
        assert step_out.net_payable_exam_fee == 3000.0
        assert step_out.total_net_payable_fee == 53000.0

    def test_male_student_tier2_tuition_relief(self):
        """22. Male candidate with income between 2.5L and 8L receives 50% tuition across institution types."""
        persona = make_persona(
            "MALE-T2-01",
            gender="Male",
            family_income=650000.0,
            institution_type=InstitutionType.GOVERNMENT_AIDED,
            annual_tuition_fee=70000.0,
            annual_exam_fee=4000.0,
        )
        engine = SimulationEngine()
        step_out = engine.run_step(persona, policy_mode="statutory")
        assert step_out.is_eligible is True
        assert step_out.tuition_fee_relief_inr == 35000.0
        assert step_out.net_payable_tuition_fee == 35000.0
        assert step_out.exam_fee_relief_inr == 2000.0
        assert step_out.net_payable_exam_fee == 2000.0
        assert step_out.total_net_payable_fee == 37000.0


# ==============================================================================
# CLASS 5: Net Payable Fee Serialization (4 Tests)
# ==============================================================================

class TestNetPayableFeeSerialization:
    def test_simulation_step_output_net_payable_properties_and_fields(self):
        """23. SimulationStepOutput exposes net payable tuition, exam, and total fee attributes."""
        persona = make_persona("P-NET-01", annual_tuition_fee=80000.0, annual_exam_fee=5000.0)
        engine = SimulationEngine()
        step_out = engine.run_step(persona, policy_mode="override", override_reimbursement_rate=0.40)
        assert hasattr(step_out, "net_payable_tuition_fee")
        assert hasattr(step_out, "net_payable_exam_fee")
        assert hasattr(step_out, "total_net_payable_fee")
        assert step_out.net_payable_tuition_fee == round(80000.0 - step_out.tuition_fee_relief_inr, 2)
        assert step_out.net_payable_exam_fee == round(5000.0 - step_out.exam_fee_relief_inr, 2)
        assert step_out.total_net_payable_fee == round(85000.0 - step_out.estimated_fee_relief_inr, 2)

    def test_simulation_step_output_to_dict_includes_net_payable_fees(self):
        """24. SimulationStepOutput.to_dict() serializes net payable tuition, exam, and total fees."""
        persona = make_persona("P-DICT-01", annual_tuition_fee=90000.0, annual_exam_fee=6000.0)
        engine = SimulationEngine()
        step_out = engine.run_step(persona, policy_mode="statutory")
        d = step_out.to_dict()
        assert "net_payable_tuition_fee" in d
        assert "net_payable_exam_fee" in d
        assert "total_net_payable_fee" in d
        assert d["net_payable_tuition_fee"] == step_out.net_payable_tuition_fee
        assert d["net_payable_exam_fee"] == step_out.net_payable_exam_fee
        assert d["total_net_payable_fee"] == step_out.total_net_payable_fee

    def test_simulation_step_output_to_json_serialization(self):
        """25. SimulationStepOutput.to_json() produces valid JSON containing all net payable keys."""
        persona = make_persona("P-JSON-01", annual_tuition_fee=100000.0, annual_exam_fee=5000.0)
        engine = SimulationEngine()
        step_out = engine.run_step(persona, policy_mode="statutory")
        parsed = json.loads(step_out.to_json())
        assert "net_payable_tuition_fee" in parsed
        assert "net_payable_exam_fee" in parsed
        assert "total_net_payable_fee" in parsed

    def test_cohort_result_net_payable_totals_serialization(self):
        """26. CohortSimulationResult.to_dict() includes total net payable tuition, exam, and total fees."""
        personas = [make_persona(f"P-COHORT-{i}", annual_tuition_fee=60000.0, annual_exam_fee=4000.0) for i in range(2)]
        engine = SimulationEngine()
        cohort_res = engine.run_cohort(personas, policy_mode="statutory")
        d = cohort_res.to_dict()
        assert "total_net_payable_tuition_fee_inr" in d
        assert "total_net_payable_exam_fee_inr" in d
        assert "total_net_payable_fee_inr" in d
        expected_total = sum(r.total_net_payable_fee for r in cohort_res.individual_results)
        assert d["total_net_payable_fee_inr"] == round(expected_total, 2)


# ==============================================================================
# CLASS 6: Provisional Epistemic Traceability (2 Tests)
# ==============================================================================

class TestProvisionalMetadataTraceability:
    def test_male_exam_relief_marked_provisional_in_notes_and_assumptions(self):
        """27. 50% male exam relief is explicitly flagged as PROVISIONAL in notes and assumptions."""
        persona = make_persona("P-PROV-MALE", gender="Male", annual_exam_fee=5000.0)
        engine = SimulationEngine()
        step_out = engine.run_step(persona, policy_mode="statutory")
        notes = " ".join(step_out.statutory_notes)
        assumptions = " ".join(step_out.benefit_assumptions)
        assert "PROVISIONAL ASSUMPTION" in notes or "PROVISIONAL" in notes
        assert "50% Exam Fee" in notes or "50% examination fee" in assumptions

    def test_step_output_is_provisional_flag(self):
        """28. is_provisional flag is True on step output and policy_version is 2024.1-provisional."""
        persona = make_persona("P-PROV-FLAG")
        engine = SimulationEngine()
        step_out = engine.run_step(persona, policy_mode="statutory")
        assert step_out.is_provisional is True
        assert "provisional" in step_out.policy_version.lower()


# ==============================================================================
# CLASS 7: Cohort Reconciliation, Multi-Step & API Integration (4 Tests)
# ==============================================================================

class TestCohortReconciliationAndMultiStepExecution:
    def test_cohort_aggregate_relief_reconciliation(self):
        """29. Total cohort fee relief exactly reconciles with sum of individual persona reliefs."""
        personas = [
            make_persona("P-REC-1", gender="Female", annual_tuition_fee=60000.0, annual_exam_fee=3000.0),
            make_persona("P-REC-2", gender="Male", family_income=300000.0, annual_tuition_fee=80000.0, annual_exam_fee=4000.0),
        ]
        engine = SimulationEngine()
        cohort_res = engine.run_cohort(personas, policy_mode="statutory")
        ind_relief_sum = sum(r.estimated_fee_relief_inr for r in cohort_res.individual_results)
        ind_tuition_sum = sum(r.tuition_fee_relief_inr for r in cohort_res.individual_results)
        ind_exam_sum = sum(r.exam_fee_relief_inr for r in cohort_res.individual_results)

        assert cohort_res.total_estimated_fee_relief_inr == round(ind_relief_sum, 2)
        assert cohort_res.total_tuition_fee_relief_inr == round(ind_tuition_sum, 2)
        assert cohort_res.total_exam_fee_relief_inr == round(ind_exam_sum, 2)
        assert round(cohort_res.total_tuition_fee_relief_inr + cohort_res.total_exam_fee_relief_inr, 2) == cohort_res.total_estimated_fee_relief_inr

    def test_counterfactual_income_expansion_increases_eligibility(self):
        """30. Persona with 9L income is ineligible under statutory (8L limit), but eligible under 10L counterfactual."""
        persona = make_persona("P-CF-INC", family_income=900000.0, annual_tuition_fee=90000.0)
        engine = SimulationEngine()
        step_stat = engine.run_step(persona, policy_mode="statutory")
        assert step_stat.is_eligible is False
        assert step_stat.estimated_fee_relief_inr == 0.0

        step_cf = engine.run_step(
            persona,
            policy_mode="counterfactual",
            counterfactual_config={"max_income_limit": 1000000.0},
        )
        assert step_cf.is_eligible is True
        assert step_cf.estimated_fee_relief_inr > 0.0

    def test_multistep_cohort_execution_with_statutory_mode(self):
        """31. run_multistep_cohort executes across steps with statutory mode preserved."""
        personas = [make_persona(f"P-MS-{i}", annual_tuition_fee=50000.0, annual_exam_fee=2000.0) for i in range(3)]
        engine = SimulationEngine()
        multi_res = engine.run_multistep_cohort(personas, total_steps=2, policy_mode="statutory")
        assert len(multi_res.step_cohort_results) == 2
        assert multi_res.final_cohort_result.policy_mode == "statutory"
        for r in multi_res.final_cohort_result.individual_results:
            assert r.policy_mode == "statutory"
            assert r.net_payable_tuition_fee >= 0.0
            assert r.net_payable_exam_fee >= 0.0

    def test_backend_persona_output_serializes_net_payable_fees(self):
        """32. Backend SimulationService maps and serializes net payable fee fields in API responses."""
        req = SimulationRequest(
            district="Dhule",
            cohort_size=2,
            simulation_steps=1,
            policy_mode="statutory",
        )
        resp = SimulationService.execute_simulation(req, persist=False)
        assert len(resp.personas) == 2
        for p in resp.personas:
            p_dict = p.model_dump()
            assert "net_payable_tuition_fee" in p_dict
            assert "net_payable_exam_fee" in p_dict
            assert "total_net_payable_fee" in p_dict
            assert p_dict["net_payable_tuition_fee"] >= 0.0

        agg_dict = resp.aggregate_metrics.model_dump()
        assert "total_net_payable_tuition_fee_inr" in agg_dict
        assert "total_net_payable_exam_fee_inr" in agg_dict
        assert "total_net_payable_fee_inr" in agg_dict


# ==============================================================================
# CLASS 8: Review Findings Controlled Corrections & Regression Tests (10 Methods)
# ==============================================================================

class TestControlledCorrectionsF01ThroughF06:
    def test_f01_counterfactual_validation_rejects_nan_inf_and_invalid_ranges(self):
        """F-01: Rejection of NaN, Inf, and invalid ranges on dict and DTEPolicyConfig instances."""
        # Test NaN on dict
        with pytest.raises(ValueError, match="finite number"):
            resolve_policy_parameters(
                policy_mode="counterfactual",
                counterfactual_config={"max_income_limit": float("nan")}
            )
        # Test Inf on dict
        with pytest.raises(ValueError, match="finite number"):
            resolve_policy_parameters(
                policy_mode="counterfactual",
                counterfactual_config={"female_tuition_rate": float("inf")}
            )
        # Test out-of-range attendance threshold
        with pytest.raises(ValueError, match="min_attendance_percent must be between 0.0 and 100.0"):
            resolve_policy_parameters(
                policy_mode="counterfactual",
                counterfactual_config={"min_attendance_percent": 120.0}
            )
        # Test negative max_family_beneficiaries
        with pytest.raises(ValueError, match="max_family_beneficiaries cannot be negative"):
            resolve_policy_parameters(
                policy_mode="counterfactual",
                counterfactual_config={"max_family_beneficiaries": -1}
            )
        # Test DTEPolicyConfig instance with NaN
        bad_cfg = DTEPolicyConfig(male_exam_rate=float("nan"))
        with pytest.raises(ValueError, match="finite number"):
            resolve_policy_parameters(
                policy_mode="counterfactual",
                counterfactual_config=bad_cfg
            )

    def test_f02_reimbursement_rates_reject_booleans(self):
        """F-02: Booleans are explicitly rejected as reimbursement rates."""
        with pytest.raises(ValueError, match="cannot be a boolean value"):
            resolve_policy_parameters(policy_mode="override", override_reimbursement_rate=True)
        with pytest.raises(ValueError, match="cannot be a boolean value"):
            resolve_policy_parameters(policy_mode="legacy_poc", override_reimbursement_rate=False)
        with pytest.raises(ValueError, match="cannot be a boolean value"):
            resolve_policy_parameters(
                policy_mode="counterfactual",
                counterfactual_config={"female_tuition_rate": True}
            )
        with pytest.raises(ValueError, match="cannot be a boolean value"):
            resolve_policy_parameters(
                policy_mode="counterfactual",
                counterfactual_config={"max_income_limit": False}
            )

    def test_f03_assumed_reimbursement_rate_is_nullable_in_statutory_and_counterfactual(self):
        """F-03: assumed_reimbursement_rate is None in statutory/counterfactual modes, not 1.0."""
        personas = [make_persona("P-F03-1"), make_persona("P-F03-2")]
        engine = SimulationEngine()

        stat_res = engine.run_cohort(personas, policy_mode="statutory")
        assert stat_res.assumed_reimbursement_rate is None

        cf_res = engine.run_cohort(personas, policy_mode="counterfactual")
        assert cf_res.assumed_reimbursement_rate is None

        poc_res = engine.run_cohort(personas, policy_mode="legacy_poc")
        assert poc_res.assumed_reimbursement_rate == 0.50

        ov_res = engine.run_cohort(personas, policy_mode="override", override_reimbursement_rate=0.75)
        assert ov_res.assumed_reimbursement_rate == 0.75

    def test_f04_simultaneous_counterfactual_params_and_config_rejected(self):
        """F-04: Reject simultaneous counterfactual_params and counterfactual_config in service."""
        from backend.models import CounterfactualPolicyParams
        with pytest.raises(ValueError, match="Cannot supply both 'counterfactual_params' and 'counterfactual_config'"):
            SimulationRequest(
                district="Dhule",
                cohort_size=2,
                simulation_steps=1,
                policy_mode="counterfactual",
                counterfactual_params=CounterfactualPolicyParams(max_income_limit=900000.0),
                counterfactual_config={"max_income_limit": 900000.0}
            )

    def test_f05_provisional_metadata_scoped_to_statutory_and_counterfactual_modes(self):
        """F-05: Provisional metadata and notes are restricted to statutory and counterfactual modes."""
        req_stat = SimulationRequest(district="Dhule", cohort_size=2, simulation_steps=1, policy_mode="statutory")
        resp_stat = SimulationService.execute_simulation(req_stat, persist=False)
        assert resp_stat.metadata.is_provisional is True
        assert resp_stat.aggregate_metrics.is_provisional is True
        assert len(resp_stat.metadata.provisional_notes) >= 3

        req_poc = SimulationRequest(district="Dhule", cohort_size=2, simulation_steps=1, policy_mode="legacy_poc")
        resp_poc = SimulationService.execute_simulation(req_poc, persist=False)
        assert resp_poc.metadata.is_provisional is False
        assert resp_poc.aggregate_metrics.is_provisional is False
        assert len(resp_poc.metadata.provisional_notes) == 0

        req_ov = SimulationRequest(
            district="Dhule", cohort_size=2, simulation_steps=1,
            policy_mode="override", override_reimbursement_rate=0.60
        )
        resp_ov = SimulationService.execute_simulation(req_ov, persist=False)
        assert resp_ov.metadata.is_provisional is False
        assert resp_ov.aggregate_metrics.is_provisional is False
        assert len(resp_ov.metadata.provisional_notes) == 0

    def test_f06_counterfactual_dict_end_to_end_execution(self):
        """F-06: Raw dictionary counterfactual_config executes end-to-end via service."""
        req = SimulationRequest(
            district="Dhule",
            cohort_size=2,
            simulation_steps=1,
            policy_mode="counterfactual",
            counterfactual_config={"max_income_limit": 1200000.0, "male_exam_rate": 0.75}
        )
        resp = SimulationService.execute_simulation(req, persist=False)
        assert resp.metadata.policy_mode == "counterfactual"
        assert resp.metadata.assumed_reimbursement_rate is None
        assert resp.metadata.is_provisional is True

    def test_t21_api_zero_rate_override_metadata(self):
        """T21: API/service-level zero-rate override metadata preserves exactly 0.0."""
        req = SimulationRequest(
            district="Dhule",
            cohort_size=2,
            simulation_steps=1,
            policy_mode="override",
            assumed_reimbursement_rate=0.0
        )
        resp = SimulationService.execute_simulation(req, persist=False)
        assert resp.metadata.policy_mode == "override"
        assert resp.metadata.assumed_reimbursement_rate == 0.0
        assert resp.metadata.assumed_reimbursement_rate is not None
        assert resp.metadata.assumed_reimbursement_rate != 0.50
        for p in resp.personas:
            assert p.tuition_fee_relief_inr == 0.0

    def test_t22_api_statutory_mode_resolution(self):
        """T22: API/service-level statutory mode resolution returns None rate and 2024.1-provisional."""
        req = SimulationRequest(
            district="Dhule",
            cohort_size=3,
            simulation_steps=1,
            policy_mode="statutory"
        )
        resp = SimulationService.execute_simulation(req, persist=False)
        assert resp.metadata.policy_mode == "statutory"
        assert resp.metadata.policy_version == "2024.1-provisional"
        assert resp.metadata.assumed_reimbursement_rate is None
        assert resp.metadata.is_provisional is True
        assert resp.aggregate_metrics.policy_mode == "statutory"
        assert resp.aggregate_metrics.is_provisional is True
        assert len(resp.metadata.provisional_notes) >= 3

    def test_implicit_mode_precedence_rate_over_config_when_mode_omitted(self):
        """Locks down existing precedence: when policy_mode is omitted, rate override takes precedence over config."""
        mode, rate, cfg = resolve_policy_parameters(
            policy_mode=None,
            assumed_reimbursement_rate=0.70,
            counterfactual_config={"max_income_limit": 1000000.0}
        )
        assert mode == "override"
        assert rate == 0.70
        assert cfg is None

    def test_attendance_metadata_description_in_assumptions(self):
        """Verifies statutory assumptions description states 50% attendance for continuing and first-year exemption."""
        personas = [make_persona("P-ATT-1"), make_persona("P-ATT-2")]
        engine = SimulationEngine()
        cohort_res = engine.run_cohort(personas, policy_mode="statutory")
        assumptions_str = " ".join(cohort_res.assumptions_and_limitations)
        assert "50%" in assumptions_str
        assert "first-year exempt" in assumptions_str.lower()
