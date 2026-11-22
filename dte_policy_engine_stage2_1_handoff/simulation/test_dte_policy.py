"""
Comprehensive Unit Tests for Deterministic DTE Scholarship Policy Engine (Stage 2.2).

Verifies:
1. Income boundary conditions (8L ceiling, 2.5L tier, edge values, negative/None).
2. Eligibility & ineligibility scenarios.
3. CAP vs non-CAP (Management Quota, Institute Level).
4. Eligible vs excluded institutions (Government, Aided, Unaided vs Deemed/Private University).
5. Tuition fee and Examination fee separation without inventing missing fees.
6. Female student 100% fee waiver (Provisional GR 08.07.2024 reference).
7. Orphan 100% fee waiver (Provisional GR 08.07.2024 reference).
8. Missing fee handling and safety (clamped, bounded, non-negative).
9. Family beneficiary limit (maximum 2 beneficiaries).
10. Attendance threshold (50.0% statutory) and first-year fresh admission exemption.
11. Non-domicile applicant handling.
12. Concurrent scholarship restriction.
13. Academic gap exceeding allowed limit (e.g. 3 years).
14. Previous academic year examination failure.
15. Safe handling of missing/None numeric attributes without crashing.
16. Safe handling of missing/None enum/string attributes without crashing.
17. Invalid and negative fee inputs.
18. Configurable caste/category enforcement.
19. Ineligible student strictly receives INR 0.00 benefit.
20. Eligibility and benefit output consistency.
21. Epistemic provisional policy status and configuration versioning.
22. Deterministic repeated calculations.
23. Backward compatibility with existing callers.
24. [Stage 2.2] Strict rejection of boolean, non-numeric, and non-finite types in numeric fields.
25. [Stage 2.2] Reconciled first-year and continuing previous_year_passed validation.
26. [Stage 2.2] Strict validation and safe failure for explicit assumed_reimbursement_rate overrides.
"""

import math
from simulation.persona import StudentPersona, InstitutionType, AdmissionMode
from simulation.policy_rules import (
    RajarshiShahuPolicyEngine,
    DTEPolicyConfig,
    ScholarshipRoute,
    EpistemicStatus,
    FeeComponentBreakdown,
    PolicyEvaluationResult,
    _validate_numeric_scalar
)


def make_student(**kwargs) -> StudentPersona:
    """Helper to create a well-formed StudentPersona with sensible defaults."""
    params = {
        "persona_id": "TEST-DTE-001",
        "name": "Aniket Deshmukh",
        "age": 20,
        "gender": "Male",
        "district": "Pune",
        "is_maharashtra_domicile": True,
        "family_income": 200000.0,
        "caste_category": "General-EBC",
        "course_name": "B.Tech Computer Engineering",
        "course_level": "Undergraduate",
        "is_professional_course": True,
        "institution_type": InstitutionType.GOVERNMENT,
        "admission_mode": AdmissionMode.CAP,
        "annual_tuition_fee": 60000.0,
        "annual_exam_fee": 6000.0,
        "attendance_percentage": 85.0,
        "previous_year_passed": True,
        "previous_year_percentage": 75.0,
        "academic_gap_years": 0,
        "is_first_year": False,
        "is_orphan": False,
        "family_beneficiaries_count": 0,
        "has_other_scholarship": False,
    }
    params.update(kwargs)
    return StudentPersona(**params)


def test_female_student_100_percent_waiver_across_institutions():
    """Verifies that eligible female students receive 100% tuition + 100% exam fee waiver across all institution types."""
    institutions = [
        InstitutionType.GOVERNMENT,
        InstitutionType.GOVERNMENT_AIDED,
        InstitutionType.PRIVATE_UNAIDED
    ]
    for inst in institutions:
        female = make_student(
            persona_id=f"FEMALE-{inst.value}",
            name="Pooja Patil",
            gender="Female",
            institution_type=inst,
            family_income=450000.0,  # <= 8 Lakh
            annual_tuition_fee=80000.0,
            annual_exam_fee=6000.0
        )
        res = RajarshiShahuPolicyEngine.evaluate_eligibility(female)

        assert res.is_eligible is True
        assert res.tuition_reimbursement_percentage == 1.00
        assert res.exam_reimbursement_percentage == 1.00
        assert res.tuition_fee_relief_inr == 80000.0
        assert res.exam_fee_relief_inr == 6000.0
        assert res.estimated_fee_relief_inr == 86000.0
        assert res.reimbursement_percentage == 1.00
        assert res.scholarship_route == ScholarshipRoute.DTE_EBC.value
        assert any("08 July 2024" in note or "शिष्यवृ-२०२४" in note for note in res.statutory_notes)

    print("PASS: test_female_student_100_percent_waiver_across_institutions")


def test_male_student_income_under_2_5_lakh_govt_vs_private():
    """
    Verifies that male students with income <= 2.5L get:
    - 100% tuition fee + 50% exam fee in Govt/Aided
    - 50% tuition fee + 50% exam fee in Private Unaided
    """
    # 1. Government / Aided
    male_govt = make_student(
        gender="Male",
        family_income=220000.0,
        institution_type=InstitutionType.GOVERNMENT_AIDED,
        annual_tuition_fee=50000.0,
        annual_exam_fee=4000.0
    )
    res_govt = RajarshiShahuPolicyEngine.evaluate_eligibility(male_govt)
    assert res_govt.is_eligible is True
    assert res_govt.tuition_reimbursement_percentage == 1.00
    assert res_govt.exam_reimbursement_percentage == 0.50
    assert res_govt.tuition_fee_relief_inr == 50000.0
    assert res_govt.exam_fee_relief_inr == 2000.0
    assert res_govt.estimated_fee_relief_inr == 52000.0

    # 2. Private Unaided
    male_pvt = make_student(
        gender="Male",
        family_income=220000.0,
        institution_type=InstitutionType.PRIVATE_UNAIDED,
        annual_tuition_fee=100000.0,
        annual_exam_fee=6000.0
    )
    res_pvt = RajarshiShahuPolicyEngine.evaluate_eligibility(male_pvt)
    assert res_pvt.is_eligible is True
    assert res_pvt.tuition_reimbursement_percentage == 0.50
    assert res_pvt.exam_reimbursement_percentage == 0.50
    assert res_pvt.tuition_fee_relief_inr == 50000.0
    assert res_pvt.exam_fee_relief_inr == 3000.0
    assert res_pvt.estimated_fee_relief_inr == 53000.0

    print("PASS: test_male_student_income_under_2_5_lakh_govt_vs_private")


def test_male_student_income_2_5_to_8_lakh():
    """Verifies that male students with income between 2.5L and 8L receive 50% tuition + 50% exam fee."""
    male_mid = make_student(
        gender="Male",
        family_income=500000.0,
        institution_type=InstitutionType.GOVERNMENT,
        annual_tuition_fee=60000.0,
        annual_exam_fee=4000.0
    )
    res = RajarshiShahuPolicyEngine.evaluate_eligibility(male_mid)
    assert res.is_eligible is True
    assert res.tuition_reimbursement_percentage == 0.50
    assert res.exam_reimbursement_percentage == 0.50
    assert res.tuition_fee_relief_inr == 30000.0
    assert res.exam_fee_relief_inr == 2000.0
    assert res.estimated_fee_relief_inr == 32000.0
    assert res.reimbursement_percentage == 0.50
    print("PASS: test_male_student_income_2_5_to_8_lakh")


def test_income_boundary_conditions():
    """Verifies boundary thresholds: 800,000 vs 800,001; 250,000 vs 250,001; None/negative."""
    # Exactly 8,00,000.0 -> Eligible
    s_800k = make_student(family_income=800000.0)
    assert RajarshiShahuPolicyEngine.check_statutory_eligibility(s_800k)[0] is True

    # 8,00,001.0 -> Ineligible
    s_800k_1 = make_student(family_income=800001.0)
    assert RajarshiShahuPolicyEngine.check_statutory_eligibility(s_800k_1)[0] is False

    # Negative / None -> Ineligible
    s_neg = make_student(family_income=-500.0)
    assert RajarshiShahuPolicyEngine.check_statutory_eligibility(s_neg)[0] is False

    # Exactly 2,50,000.0 -> Tier 1 (100% in Govt)
    s_250k = make_student(gender="Male", family_income=250000.0, institution_type=InstitutionType.GOVERNMENT)
    res_250k = RajarshiShahuPolicyEngine.evaluate_eligibility(s_250k)
    assert res_250k.tuition_reimbursement_percentage == 1.00

    # 2,50,001.0 -> Tier 2 (50% in Govt)
    s_250k_1 = make_student(gender="Male", family_income=250001.0, institution_type=InstitutionType.GOVERNMENT)
    res_250k_1 = RajarshiShahuPolicyEngine.evaluate_eligibility(s_250k_1)
    assert res_250k_1.tuition_reimbursement_percentage == 0.50

    print("PASS: test_income_boundary_conditions")


def test_tuition_and_exam_fee_separation():
    """Verifies independent calculation of tuition and exam fee components."""
    student = make_student(
        gender="Male",
        family_income=400000.0,
        annual_tuition_fee=90000.0,
        annual_exam_fee=8000.0
    )
    res = RajarshiShahuPolicyEngine.evaluate_eligibility(student)
    assert res.tuition_fee_relief_inr == 45000.0  # 50%
    assert res.exam_fee_relief_inr == 4000.0      # 50%
    assert res.estimated_fee_relief_inr == 49000.0
    assert res.fee_breakdown is not None
    assert res.fee_breakdown.annual_tuition_fee == 90000.0
    assert res.fee_breakdown.annual_exam_fee == 8000.0
    print("PASS: test_tuition_and_exam_fee_separation")


def test_missing_and_zero_fee_handling():
    """Verifies that missing fees are not invented and are handled with explicit notes."""
    # Zero exam fee (male income > 2.5L -> 50% tuition)
    s_no_exam = make_student(family_income=400000.0, annual_tuition_fee=70000.0, annual_exam_fee=0.0)
    res_no_exam = RajarshiShahuPolicyEngine.evaluate_eligibility(s_no_exam)
    assert res_no_exam.tuition_fee_relief_inr == 35000.0
    assert res_no_exam.exam_fee_relief_inr == 0.0
    assert res_no_exam.estimated_fee_relief_inr == 35000.0
    assert any("annual_exam_fee is INR 0.00" in n for n in res_no_exam.fee_breakdown.missing_fee_notes)

    # Zero tuition fee (male income > 2.5L -> 50% exam)
    s_zero_tuition = make_student(family_income=400000.0, annual_tuition_fee=0.0, annual_exam_fee=5000.0)
    res_zero = RajarshiShahuPolicyEngine.evaluate_eligibility(s_zero_tuition)
    assert res_zero.tuition_fee_relief_inr == 0.0
    assert res_zero.exam_fee_relief_inr == 2500.0
    assert res_zero.estimated_fee_relief_inr == 2500.0
    assert any("annual_tuition_fee is INR 0.00" in n for n in res_zero.fee_breakdown.missing_fee_notes)

    print("PASS: test_missing_and_zero_fee_handling")


def test_cap_vs_non_cap_admission():
    """Verifies that CAP admission is required for professional courses."""
    s_cap = make_student(admission_mode=AdmissionMode.CAP)
    assert RajarshiShahuPolicyEngine.check_statutory_eligibility(s_cap)[0] is True

    s_mgmt = make_student(admission_mode=AdmissionMode.MANAGEMENT_QUOTA)
    is_ok, _, fails = RajarshiShahuPolicyEngine.check_statutory_eligibility(s_mgmt)
    assert is_ok is False
    assert any("CAP admission" in f for f in fails)

    s_inst = make_student(admission_mode=AdmissionMode.INSTITUTE_LEVEL)
    is_ok_inst, _, fails_inst = RajarshiShahuPolicyEngine.check_statutory_eligibility(s_inst)
    assert is_ok_inst is False
    assert any("CAP admission" in f for f in fails_inst)

    print("PASS: test_cap_vs_non_cap_admission")


def test_eligible_vs_excluded_institutions():
    """Verifies that Deemed/Private Universities are excluded, while Govt/Aided/Unaided pass."""
    for inst in [InstitutionType.GOVERNMENT, InstitutionType.GOVERNMENT_AIDED, InstitutionType.PRIVATE_UNAIDED]:
        s = make_student(institution_type=inst)
        assert RajarshiShahuPolicyEngine.check_statutory_eligibility(s)[0] is True

    s_deemed = make_student(institution_type=InstitutionType.DEEMED_OR_PRIVATE_UNIVERSITY)
    is_ok, _, fails = RajarshiShahuPolicyEngine.check_statutory_eligibility(s_deemed)
    assert is_ok is False
    assert any("Deemed/Private-University" in f for f in fails)
    print("PASS: test_eligible_vs_excluded_institutions")


def test_attendance_and_first_year_exemption():
    """Verifies statutory 50% attendance threshold and 1st-year fresh admission exemption."""
    cfg_statutory = DTEPolicyConfig(use_strict_institutional_attendance=False, min_attendance_percent=50.0)

    # 1. 2nd year student with 52% attendance -> Passes statutory 50% check
    s_52 = make_student(attendance_percentage=52.0, is_first_year=False)
    assert RajarshiShahuPolicyEngine.check_statutory_eligibility(s_52, config=cfg_statutory)[0] is True

    # 2. 2nd year student with 45% attendance -> Fails statutory check
    s_45 = make_student(attendance_percentage=45.0, is_first_year=False)
    is_ok_45, _, fails_45 = RajarshiShahuPolicyEngine.check_statutory_eligibility(s_45, config=cfg_statutory)
    assert is_ok_45 is False
    assert any("Attendance (45.0%) is below statutory requirement" in f for f in fails_45)

    # 3. 1st year student with 45% attendance -> Passes due to statutory exemption
    s_1st_yr = make_student(attendance_percentage=45.0, is_first_year=True)
    is_ok_1st, checks_1st, fails_1st = RajarshiShahuPolicyEngine.check_statutory_eligibility(s_1st_yr, config=cfg_statutory)
    assert is_ok_1st is True
    assert len(fails_1st) == 0
    att_check = [c for c in checks_1st if c.rule_name == "Minimum Attendance Requirement"][0]
    assert att_check.is_satisfied is True
    assert "First-year fresh entrant is statutorily exempt" in att_check.message

    print("PASS: test_attendance_and_first_year_exemption")


def test_orphan_100_percent_waiver():
    """Verifies that orphan students receive 100% tuition and exam fee waiver under July 2024 GR."""
    orphan_male = make_student(
        gender="Male",
        is_orphan=True,
        family_income=150000.0,
        annual_tuition_fee=75000.0,
        annual_exam_fee=5000.0,
        institution_type=InstitutionType.PRIVATE_UNAIDED
    )
    res = RajarshiShahuPolicyEngine.evaluate_eligibility(orphan_male)
    assert res.is_eligible is True
    assert res.tuition_reimbursement_percentage == 1.00
    assert res.exam_reimbursement_percentage == 1.00
    assert res.tuition_fee_relief_inr == 75000.0
    assert res.exam_fee_relief_inr == 5000.0
    assert res.estimated_fee_relief_inr == 80000.0
    assert res.scholarship_route == ScholarshipRoute.DTE_EBC.value
    print("PASS: test_orphan_100_percent_waiver")


def test_family_beneficiary_limit():
    """Verifies that maximum 2 beneficiaries are allowed per family."""
    for count in [0, 1]:
        s = make_student(family_beneficiaries_count=count)
        assert RajarshiShahuPolicyEngine.check_statutory_eligibility(s)[0] is True

    for count in [2, 3]:
        s_exceed = make_student(family_beneficiaries_count=count)
        is_ok, _, fails = RajarshiShahuPolicyEngine.check_statutory_eligibility(s_exceed)
        assert is_ok is False
        assert any("maximum limit is 2 children" in f for f in fails)

    print("PASS: test_family_beneficiary_limit")


def test_non_domicile_applicant():
    """Verifies that non-domicile applicants fail statutory eligibility and receive zero benefit."""
    s_non_dom = make_student(is_maharashtra_domicile=False)
    is_ok, _, fails = RajarshiShahuPolicyEngine.check_statutory_eligibility(s_non_dom)
    assert is_ok is False
    assert any("not a domicile of Maharashtra" in f for f in fails)

    res = RajarshiShahuPolicyEngine.evaluate_eligibility(s_non_dom)
    assert res.is_eligible is False
    assert res.estimated_fee_relief_inr == 0.0
    assert res.scholarship_route == ScholarshipRoute.INELIGIBLE.value
    print("PASS: test_non_domicile_applicant")


def test_concurrent_scholarship_restriction():
    """Verifies that holding another government scholarship disqualifies applicant from fee relief."""
    s_dual = make_student(has_other_scholarship=True)
    is_ok, _, fails = RajarshiShahuPolicyEngine.check_statutory_eligibility(s_dual)
    assert is_ok is False
    assert any("already receiving another government scholarship" in f for f in fails)

    res = RajarshiShahuPolicyEngine.evaluate_eligibility(s_dual)
    assert res.is_eligible is False
    assert res.estimated_fee_relief_inr == 0.0
    assert res.scholarship_route == ScholarshipRoute.INELIGIBLE.value
    print("PASS: test_concurrent_scholarship_restriction")


def test_academic_gap_exceeding_limit():
    """Verifies that academic educational gap > 2 years is disqualified."""
    s_gap3 = make_student(academic_gap_years=3)
    is_ok, _, fails = RajarshiShahuPolicyEngine.check_statutory_eligibility(s_gap3)
    assert is_ok is False
    assert any("Academic gap (3 years) exceeds maximum allowed" in f for f in fails)

    res = RajarshiShahuPolicyEngine.evaluate_eligibility(s_gap3)
    assert res.is_eligible is False
    assert res.estimated_fee_relief_inr == 0.0
    print("PASS: test_academic_gap_exceeding_limit")


def test_previous_examination_failure():
    """Verifies that failing the previous academic examination disqualifies continuing students."""
    s_failed = make_student(previous_year_passed=False, is_first_year=False)
    is_ok, _, fails = RajarshiShahuPolicyEngine.check_statutory_eligibility(s_failed)
    assert is_ok is False
    assert any("did not pass the previous academic year" in f for f in fails)

    res = RajarshiShahuPolicyEngine.evaluate_eligibility(s_failed)
    assert res.is_eligible is False
    assert res.estimated_fee_relief_inr == 0.0
    print("PASS: test_previous_examination_failure")


def test_missing_none_numeric_attributes():
    """Verifies safe handling and explicit failure for None in numeric attributes without crashing."""
    # 1. Missing attendance percentage
    s_none_att = make_student(attendance_percentage=None, is_first_year=False)
    is_ok_att, _, fails_att = RajarshiShahuPolicyEngine.check_statutory_eligibility(s_none_att)
    assert is_ok_att is False
    assert any("Attendance percentage is invalid or missing" in f for f in fails_att)

    # 2. Missing academic gap years
    s_none_gap = make_student(academic_gap_years=None)
    is_ok_gap, _, fails_gap = RajarshiShahuPolicyEngine.check_statutory_eligibility(s_none_gap)
    assert is_ok_gap is False
    assert any("Academic gap years information is invalid or missing" in f for f in fails_gap)

    # 3. Missing family beneficiaries count
    s_none_ben = make_student(family_beneficiaries_count=None)
    is_ok_ben, _, fails_ben = RajarshiShahuPolicyEngine.check_statutory_eligibility(s_none_ben)
    assert is_ok_ben is False
    assert any("Family beneficiaries count is invalid or missing" in f for f in fails_ben)

    # 4. Missing family income
    s_none_inc = make_student(family_income=None)
    is_ok_inc, _, fails_inc = RajarshiShahuPolicyEngine.check_statutory_eligibility(s_none_inc)
    assert is_ok_inc is False
    assert any("Annual family income is invalid or missing" in f for f in fails_inc)

    print("PASS: test_missing_none_numeric_attributes")


def test_missing_none_enum_string_attributes():
    """Verifies safe handling and explicit failure for None in enum/string attributes without crashing."""
    # 1. Missing admission mode for professional course
    s_none_adm = make_student(admission_mode=None, is_professional_course=True)
    is_ok_adm, _, fails_adm = RajarshiShahuPolicyEngine.check_statutory_eligibility(s_none_adm)
    assert is_ok_adm is False
    assert any("Admission mode is missing" in f for f in fails_adm)

    # 2. Missing admission mode for non-professional course (should pass)
    s_non_prof = make_student(admission_mode=None, is_professional_course=False)
    is_ok_np, _, _ = RajarshiShahuPolicyEngine.check_statutory_eligibility(s_non_prof)
    assert is_ok_np is True

    # 3. Missing institution type
    s_none_inst = make_student(institution_type=None)
    is_ok_inst, _, fails_inst = RajarshiShahuPolicyEngine.check_statutory_eligibility(s_none_inst)
    assert is_ok_inst is False
    assert any("Institution type is missing" in f for f in fails_inst)

    # 4. Missing domicile
    s_none_dom = make_student(is_maharashtra_domicile=None)
    is_ok_dom, _, fails_dom = RajarshiShahuPolicyEngine.check_statutory_eligibility(s_none_dom)
    assert is_ok_dom is False
    assert any("Maharashtra domicile status is missing" in f for f in fails_dom)

    # 5. Missing concurrent scholarship flag
    s_none_schol = make_student(has_other_scholarship=None)
    is_ok_schol, _, fails_schol = RajarshiShahuPolicyEngine.check_statutory_eligibility(s_none_schol)
    assert is_ok_schol is False
    assert any("Concurrent scholarship status is missing" in f for f in fails_schol)

    print("PASS: test_missing_none_enum_string_attributes")


def test_invalid_and_negative_fee_inputs():
    """Verifies clamping and safe handling of negative/invalid fee amounts."""
    s_neg_fee = make_student(annual_tuition_fee=-50000.0, annual_exam_fee=-4000.0)
    res = RajarshiShahuPolicyEngine.evaluate_eligibility(s_neg_fee)
    assert res.tuition_fee_relief_inr == 0.0
    assert res.exam_fee_relief_inr == 0.0
    assert res.estimated_fee_relief_inr == 0.0
    assert res.fee_breakdown.annual_tuition_fee == 0.0
    assert res.fee_breakdown.annual_exam_fee == 0.0
    assert any("annual_tuition_fee is" in n for n in res.fee_breakdown.missing_fee_notes)
    print("PASS: test_invalid_and_negative_fee_inputs")


def test_configurable_caste_enforcement():
    """Verifies that configurable caste categories are respected when configured, and open by default."""
    # Open / unconstrained by default
    s_sc = make_student(caste_category="SC")
    assert RajarshiShahuPolicyEngine.check_statutory_eligibility(s_sc)[0] is True

    # Restrictive configuration
    cfg_ebc_only = DTEPolicyConfig(allowed_caste_categories=["General-EBC", "Open", "SEBC"])
    is_ok_ebc, _, fails_ebc = RajarshiShahuPolicyEngine.check_statutory_eligibility(s_sc, config=cfg_ebc_only)
    assert is_ok_ebc is False
    assert any("Caste category 'SC' is not eligible" in f for f in fails_ebc)

    # Candidate with allowed caste passes
    s_ebc = make_student(caste_category="General-EBC")
    assert RajarshiShahuPolicyEngine.check_statutory_eligibility(s_ebc, config=cfg_ebc_only)[0] is True
    print("PASS: test_configurable_caste_enforcement")


def test_ineligible_student_cannot_receive_benefit():
    """STRICT GUARANTEE: An ineligible student must strictly receive INR 0.00 relief."""
    ineligible_scenarios = [
        make_student(family_income=900000.0),                               # Income > 8L
        make_student(admission_mode=AdmissionMode.MANAGEMENT_QUOTA),        # Management Quota
        make_student(institution_type=InstitutionType.DEEMED_OR_PRIVATE_UNIVERSITY), # Deemed Univ
        make_student(is_maharashtra_domicile=False),                        # Non-domicile
        make_student(family_beneficiaries_count=2),                         # Sibling cap reached
        make_student(has_other_scholarship=True),                           # Dual scholarship
        make_student(academic_gap_years=3),                                 # Gap > 2 yrs
        make_student(attendance_percentage=40.0, is_first_year=False),     # Low attendance
    ]
    for s in ineligible_scenarios:
        res = RajarshiShahuPolicyEngine.evaluate_eligibility(s)
        assert res.is_eligible is False
        assert res.estimated_fee_relief_inr == 0.0
        assert res.tuition_fee_relief_inr == 0.0
        assert res.exam_fee_relief_inr == 0.0
        assert res.reimbursement_percentage == 0.0
        assert res.scholarship_route == ScholarshipRoute.INELIGIBLE.value
        assert len(res.failure_reasons) > 0

    print("PASS: test_ineligible_student_cannot_receive_benefit")


def test_eligibility_and_benefit_consistency():
    """Verifies that benefits are bounded by actual assessed fees and deterministic across calls."""
    student = make_student(
        gender="Male",
        family_income=300000.0,
        annual_tuition_fee=80000.0,
        annual_exam_fee=6000.0
    )
    res = RajarshiShahuPolicyEngine.evaluate_eligibility(student)
    assert res.is_eligible is True
    # Bounded by actual fees
    assert res.tuition_fee_relief_inr <= student.annual_tuition_fee
    assert res.exam_fee_relief_inr <= student.annual_exam_fee
    assert res.estimated_fee_relief_inr == res.tuition_fee_relief_inr + res.exam_fee_relief_inr
    print("PASS: test_eligibility_and_benefit_consistency")


def test_provisional_policy_status_and_version():
    """Verifies that unverified policy rules carry PROVISIONAL status and explicit versioning."""
    student = make_student()
    res = RajarshiShahuPolicyEngine.evaluate_eligibility(student)
    assert res.policy_version == "2024.1-provisional"
    assert res.verification_status == "PROVISIONAL"
    for rc in res.rule_checks:
        assert rc.epistemic_status == "PROVISIONAL"
    print("PASS: test_provisional_policy_status_and_version")


def test_deterministic_repeated_calculations():
    """Verifies that repeated evaluations of the same persona return 100% identical results."""
    student = make_student(gender="Female", annual_tuition_fee=95000.0, annual_exam_fee=7500.0)
    res1 = RajarshiShahuPolicyEngine.evaluate_eligibility(student)
    for _ in range(50):
        res_i = RajarshiShahuPolicyEngine.evaluate_eligibility(student)
        assert res_i.estimated_fee_relief_inr == res1.estimated_fee_relief_inr
        assert res_i.reimbursement_percentage == res1.reimbursement_percentage
        assert res_i.tuition_fee_relief_inr == res1.tuition_fee_relief_inr
        assert res_i.exam_fee_relief_inr == res1.exam_fee_relief_inr
        assert res_i.is_eligible == res1.is_eligible
    print("PASS: test_deterministic_repeated_calculations")


def test_backward_compatibility_contract():
    """Verifies that all Phase 1/Phase 2 contract fields are populated and valid."""
    student = make_student()
    is_ok, checks, fails = RajarshiShahuPolicyEngine.check_statutory_eligibility(student)
    assert isinstance(is_ok, bool)
    assert len(checks) == 8  # Exact 8-check contract preserved
    for c in checks:
        assert hasattr(c, "epistemic_status")
        assert c.epistemic_status in ["VERIFIED", "PROVISIONAL", "UNVERIFIED"]

    eval_res = RajarshiShahuPolicyEngine.evaluate_eligibility(student, assumed_reimbursement_rate=0.50)
    assert isinstance(eval_res, PolicyEvaluationResult)
    assert eval_res.reimbursement_percentage == 0.50
    assert eval_res.estimated_fee_relief_inr > 0.0
    assert len(eval_res.benefit_assumptions) > 0
    assert len(eval_res.statutory_notes) > 0
    print("PASS: test_backward_compatibility_contract")


# ==============================================================================
# STAGE 2.2 NEW VALIDATION & INTEGRATION TESTS
# ==============================================================================

def test_stage2_2_invalid_numeric_data_types():
    """
    Verifies that boolean, string, non-finite (NaN/Inf) types in numeric fields
    fail safely and deterministically without throwing exceptions.
    """
    # 1. Family Income type rejection
    for invalid_val in [True, False, "invalid", "500000", float("nan"), float("inf"), -100.0]:
        s = make_student(family_income=invalid_val)
        is_ok, checks, fails = RajarshiShahuPolicyEngine.check_statutory_eligibility(s)
        assert is_ok is False, f"Expected family_income={invalid_val!r} to fail eligibility"
        inc_check = [c for c in checks if c.rule_name == "Family Income Cap"][0]
        assert inc_check.is_satisfied is False
        assert any("Annual family income is invalid" in f or "exceeds" in f for f in fails)

    # 2. Attendance percentage type rejection
    for invalid_att in [True, False, "85%", "invalid", float("nan"), float("inf"), -1.0, 105.0]:
        s = make_student(attendance_percentage=invalid_att, is_first_year=False)
        is_ok, checks, fails = RajarshiShahuPolicyEngine.check_statutory_eligibility(s)
        assert is_ok is False, f"Expected attendance_percentage={invalid_att!r} to fail eligibility"
        att_check = [c for c in checks if c.rule_name == "Minimum Attendance Requirement"][0]
        assert att_check.is_satisfied is False

    # 3. Academic Gap Years type rejection
    for invalid_gap in [True, False, "one", 1.5, float("nan"), float("inf"), -1]:
        s = make_student(academic_gap_years=invalid_gap)
        is_ok, checks, fails = RajarshiShahuPolicyEngine.check_statutory_eligibility(s)
        assert is_ok is False, f"Expected academic_gap_years={invalid_gap!r} to fail eligibility"
        gap_check = [c for c in checks if c.rule_name == "Academic Progress & Gap"][0]
        assert gap_check.is_satisfied is False

    # 4. Family Beneficiaries Count type rejection
    for invalid_ben in [True, False, "zero", 1.5, float("nan"), float("inf"), -1]:
        s = make_student(family_beneficiaries_count=invalid_ben)
        is_ok, checks, fails = RajarshiShahuPolicyEngine.check_statutory_eligibility(s)
        assert is_ok is False, f"Expected family_beneficiaries_count={invalid_ben!r} to fail eligibility"
        ben_check = [c for c in checks if c.rule_name == "Family Beneficiary Cap"][0]
        assert ben_check.is_satisfied is False

    print("PASS: test_stage2_2_invalid_numeric_data_types")


def test_stage2_2_first_year_and_continuing_reconciliation():
    """
    Verifies reconciled previous_year_passed behavior for both fresh 1st-year
    and continuing students across True, False, None, and invalid types.
    """
    # Case A: First-Year Entrant
    # A1. previous_year_passed=True -> Eligible (attendance exempt)
    s_1st_pass = make_student(is_first_year=True, previous_year_passed=True, attendance_percentage=30.0)
    is_ok, _, fails = RajarshiShahuPolicyEngine.check_statutory_eligibility(s_1st_pass)
    assert is_ok is True
    assert len(fails) == 0

    # A2. previous_year_passed=False -> Ineligible (failed qualifying exam)
    s_1st_fail = make_student(is_first_year=True, previous_year_passed=False)
    is_ok, _, fails = RajarshiShahuPolicyEngine.check_statutory_eligibility(s_1st_fail)
    assert is_ok is False
    assert any("qualifying examination" in f.lower() for f in fails)

    # A3. previous_year_passed=None -> Ineligible (qualifying exam status missing)
    s_1st_none = make_student(is_first_year=True, previous_year_passed=None)
    is_ok, _, fails = RajarshiShahuPolicyEngine.check_statutory_eligibility(s_1st_none)
    assert is_ok is False
    assert any("qualifying examination" in f.lower() for f in fails)

    # A4. previous_year_passed="passed" (non-bool string) -> Ineligible (invalid type)
    s_1st_str = make_student(is_first_year=True, previous_year_passed="passed")
    is_ok, _, fails = RajarshiShahuPolicyEngine.check_statutory_eligibility(s_1st_str)
    assert is_ok is False
    assert any("must be a boolean" in f.lower() for f in fails)

    # Case B: Continuing Student (2nd/3rd/4th Year)
    # B1. previous_year_passed=True with good attendance -> Eligible
    s_cont_pass = make_student(is_first_year=False, previous_year_passed=True, attendance_percentage=80.0)
    is_ok, _, _ = RajarshiShahuPolicyEngine.check_statutory_eligibility(s_cont_pass)
    assert is_ok is True

    # B2. previous_year_passed=False -> Ineligible (failed previous college exam)
    s_cont_fail = make_student(is_first_year=False, previous_year_passed=False)
    is_ok, _, fails = RajarshiShahuPolicyEngine.check_statutory_eligibility(s_cont_fail)
    assert is_ok is False
    assert any("previous academic year" in f.lower() for f in fails)

    # B3. previous_year_passed=None -> Ineligible (missing exam status)
    s_cont_none = make_student(is_first_year=False, previous_year_passed=None)
    is_ok, _, fails = RajarshiShahuPolicyEngine.check_statutory_eligibility(s_cont_none)
    assert is_ok is False
    assert any("previous academic year" in f.lower() for f in fails)

    # B4. previous_year_passed=1 (integer instead of bool) -> Ineligible
    s_cont_int = make_student(is_first_year=False, previous_year_passed=1)
    is_ok, _, fails = RajarshiShahuPolicyEngine.check_statutory_eligibility(s_cont_int)
    assert is_ok is False
    assert any("must be a boolean" in f.lower() for f in fails)

    print("PASS: test_stage2_2_first_year_and_continuing_reconciliation")


def test_stage2_2_assumed_reimbursement_rate_validation():
    """
    Verifies that explicit assumed_reimbursement_rate overrides are strictly validated:
    - Finite float [0.0, 1.0] succeeds as override.
    - None executes normal DTE deterministic policy calculation.
    - Boolean, string, NaN, Inf, < 0.0, > 1.0 fail safely, produce INR 0.00 relief, and record diagnostics.
    """
    student = make_student(
        gender="Female",
        annual_tuition_fee=80000.0,
        annual_exam_fee=6000.0,
        family_income=300000.0
    )

    # 1. Normal execution when override is None (Female gets 100% Tuition + 100% Exam under GR 08.07.2024)
    res_normal = RajarshiShahuPolicyEngine.evaluate_eligibility(student, assumed_reimbursement_rate=None)
    assert res_normal.is_eligible is True
    assert res_normal.reimbursement_percentage == 1.00
    assert res_normal.estimated_fee_relief_inr == 86000.0

    # 2. Valid explicit overrides
    res_half = RajarshiShahuPolicyEngine.evaluate_eligibility(student, assumed_reimbursement_rate=0.50)
    assert res_half.is_eligible is True
    assert res_half.reimbursement_percentage == 0.50
    assert res_half.estimated_fee_relief_inr == 43000.0

    res_zero = RajarshiShahuPolicyEngine.evaluate_eligibility(student, assumed_reimbursement_rate=0.0)
    assert res_zero.is_eligible is True
    assert res_zero.reimbursement_percentage == 0.0
    assert res_zero.estimated_fee_relief_inr == 0.0

    res_full = RajarshiShahuPolicyEngine.evaluate_eligibility(student, assumed_reimbursement_rate=1.0)
    assert res_full.is_eligible is True
    assert res_full.reimbursement_percentage == 1.00
    assert res_full.estimated_fee_relief_inr == 86000.0

    # 3. Invalid explicit overrides -> must fail safely and result in INR 0.00 relief with diagnostics
    invalid_overrides = [
        True,
        False,
        "0.50",
        float("nan"),
        float("inf"),
        -0.1,
        1.1,
        [0.5],
    ]
    for bad_rate in invalid_overrides:
        res_bad = RajarshiShahuPolicyEngine.evaluate_eligibility(student, assumed_reimbursement_rate=bad_rate)
        assert res_bad.is_eligible is True  # statutory eligibility itself passed
        assert res_bad.estimated_fee_relief_inr == 0.0, f"Expected 0.0 relief for bad override {bad_rate!r}"
        assert res_bad.reimbursement_percentage == 0.0
        assert res_bad.tuition_fee_relief_inr == 0.0
        assert res_bad.exam_fee_relief_inr == 0.0
        assert any("Invalid explicit override" in note for note in res_bad.statutory_notes)
        assert any("Override Rate: Invalid explicit value" in r for r in res_bad.indeterminate_reasons)

    print("PASS: test_stage2_2_assumed_reimbursement_rate_validation")


def test_stage2_2_invalid_fee_inputs_clamping():
    """
    Verifies that tuition and exam fees with boolean, non-numeric, NaN, Infinity,
    or negative values clamp safely to INR 0.00 and do not cause arithmetic crashes.
    """
    for bad_tuition in [True, False, "free", float("nan"), float("inf"), -50000.0]:
        s = make_student(annual_tuition_fee=bad_tuition, annual_exam_fee=6000.0)
        res = RajarshiShahuPolicyEngine.evaluate_eligibility(s)
        assert res.fee_breakdown.annual_tuition_fee == 0.0
        assert res.tuition_fee_relief_inr == 0.0
        assert any("annual_tuition_fee is" in n for n in res.fee_breakdown.missing_fee_notes)

    for bad_exam in [True, False, "zero", float("nan"), float("inf"), -4000.0]:
        s = make_student(annual_tuition_fee=60000.0, annual_exam_fee=bad_exam)
        res = RajarshiShahuPolicyEngine.evaluate_eligibility(s)
        assert res.fee_breakdown.annual_exam_fee == 0.0
        assert res.exam_fee_relief_inr == 0.0
        assert any("annual_exam_fee is" in n for n in res.fee_breakdown.missing_fee_notes)

    print("PASS: test_stage2_2_invalid_fee_inputs_clamping")


# ==============================================================================
# STAGE 2.2.1 HOTFIX REGRESSION TESTS: INELIGIBLE FEE SANITIZATION
# ==============================================================================

def test_stage2_2_1_ineligible_applicant_invalid_fees():
    """
    Stage 2.2.1 Hotfix Regression Test:
    Verifies that for ineligible applicants, fee breakdown values remain strictly
    valid (numeric, finite, non-negative, and not boolean) under all invalid inputs:
    - Numeric strings
    - Arbitrary strings
    - Boolean True / False
    - NaN
    - Positive Infinity
    - Negative Infinity
    - Negative numeric values
    - None
    Verifies across individual fee fields, fee combinations, and various ineligibility triggers.
    Ensures applicants remain ineligible and receive strictly INR 0.00 relief.
    """
    invalid_fee_values = [
        "100000",        # Numeric string
        "arbitrary_fee", # Non-numeric string
        "",              # Empty string
        True,            # Boolean True
        False,           # Boolean False
        float("nan"),    # NaN
        float("inf"),    # Positive Infinity
        float("-inf"),   # Negative Infinity
        -50000.0,        # Negative float
        -1,              # Negative integer
        None,            # None
    ]

    breakdown_monetary_attrs = [
        "annual_tuition_fee",
        "annual_exam_fee",
        "tuition_reimbursement_rate",
        "exam_reimbursement_rate",
        "tuition_fee_relief_inr",
        "exam_fee_relief_inr",
        "total_fee_relief_inr",
        "effective_relief_rate",
    ]

    # Matrix of distinct ineligible applicant profiles
    ineligible_bases = [
        {"family_income": 950000.0},                               # Income > 8L
        {"admission_mode": AdmissionMode.MANAGEMENT_QUOTA},        # Non-CAP
        {"is_maharashtra_domicile": False},                        # Non-domicile
        {"family_beneficiaries_count": 2},                         # Family sibling cap
        {"attendance_percentage": 35.0, "is_first_year": False},   # Sub-threshold attendance
        {"academic_gap_years": 3},                                 # Excessive gap
        {"has_other_scholarship": True},                           # Dual scholarship
        {"previous_year_passed": False},                           # Failed previous exam
    ]

    for base_kwargs in ineligible_bases:
        # 1. Invalid tuition fee individually (with valid exam fee)
        for bad_val in invalid_fee_values:
            s = make_student(annual_tuition_fee=bad_val, annual_exam_fee=6000.0, **base_kwargs)
            res = RajarshiShahuPolicyEngine.evaluate_eligibility(s)

            assert res.is_eligible is False, f"Applicant with {base_kwargs} must remain ineligible"
            assert res.reimbursement_percentage == 0.0
            assert res.estimated_fee_relief_inr == 0.0
            assert res.tuition_fee_relief_inr == 0.0
            assert res.exam_fee_relief_inr == 0.0
            assert res.scholarship_route == ScholarshipRoute.INELIGIBLE.value
            assert res.fee_breakdown is not None

            # Verify every monetary field in breakdown is strictly numeric, finite, non-negative, and not bool
            for attr in breakdown_monetary_attrs:
                val = getattr(res.fee_breakdown, attr)
                assert isinstance(val, (int, float)), f"{attr} must be numeric, got {type(val).__name__} ({val!r})"
                assert not isinstance(val, bool), f"{attr} must not be a boolean, got {val!r}"
                assert not math.isnan(val), f"{attr} must not be NaN"
                assert not math.isinf(val), f"{attr} must not be Infinity"
                assert val >= 0.0, f"{attr} must be non-negative, got {val}"

            # Invalid tuition clamped to 0.0
            assert res.fee_breakdown.annual_tuition_fee == 0.0
            assert res.fee_breakdown.annual_exam_fee == 6000.0

        # 2. Invalid exam fee individually (with valid tuition fee)
        for bad_val in invalid_fee_values:
            s = make_student(annual_tuition_fee=60000.0, annual_exam_fee=bad_val, **base_kwargs)
            res = RajarshiShahuPolicyEngine.evaluate_eligibility(s)

            assert res.is_eligible is False
            assert res.estimated_fee_relief_inr == 0.0
            assert res.tuition_fee_relief_inr == 0.0
            assert res.exam_fee_relief_inr == 0.0
            assert res.fee_breakdown is not None

            for attr in breakdown_monetary_attrs:
                val = getattr(res.fee_breakdown, attr)
                assert isinstance(val, (int, float)) and not isinstance(val, bool)
                assert not math.isnan(val) and not math.isinf(val)
                assert val >= 0.0

            assert res.fee_breakdown.annual_tuition_fee == 60000.0
            assert res.fee_breakdown.annual_exam_fee == 0.0

        # 3. Both fees invalid in combinations
        paired_bad_values = [
            (True, False),
            ("100000", -500.0),
            (float("nan"), float("inf")),
            (float("-inf"), "arbitrary"),
            (None, None),
            (-75000.0, True),
        ]
        for bad_t, bad_e in paired_bad_values:
            s = make_student(annual_tuition_fee=bad_t, annual_exam_fee=bad_e, **base_kwargs)
            res = RajarshiShahuPolicyEngine.evaluate_eligibility(s)

            assert res.is_eligible is False
            assert res.estimated_fee_relief_inr == 0.0
            assert res.fee_breakdown.annual_tuition_fee == 0.0
            assert res.fee_breakdown.annual_exam_fee == 0.0

            for attr in breakdown_monetary_attrs:
                val = getattr(res.fee_breakdown, attr)
                assert isinstance(val, (int, float)) and not isinstance(val, bool)
                assert not math.isnan(val) and not math.isinf(val)
                assert val == 0.0

        # 4. Direct calculate_dte_benefit() call with is_eligible=False
        for bad_val in invalid_fee_values:
            s = make_student(annual_tuition_fee=bad_val, annual_exam_fee=bad_val, **base_kwargs)
            rate, relief, bd, notes, assumptions = RajarshiShahuPolicyEngine.calculate_dte_benefit(
                persona=s, is_eligible=False
            )
            assert rate == 0.0
            assert relief == 0.0
            assert bd.annual_tuition_fee == 0.0
            assert bd.annual_exam_fee == 0.0
            assert bd.total_fee_relief_inr == 0.0

    print("PASS: test_stage2_2_1_ineligible_applicant_invalid_fees")


def test_stage2_2_1_fee_component_breakdown_monetary_sanitization():
    """
    Stage 2.2.1 Hotfix Unit Test:
    Verifies that FeeComponentBreakdown.__post_init__ defensively sanitizes
    all monetary and rate fields, converting any invalid value (string, boolean,
    NaN, Infinity, negative, None) safely to 0.0 without unhandled exceptions.
    """
    invalid_inputs = [
        "not_a_number",
        "50000",
        True,
        False,
        float("nan"),
        float("inf"),
        float("-inf"),
        -100.0,
        None,
    ]

    for bad in invalid_inputs:
        bd = FeeComponentBreakdown(
            annual_tuition_fee=bad,
            annual_exam_fee=bad,
            tuition_reimbursement_rate=bad,
            exam_reimbursement_rate=bad,
            tuition_fee_relief_inr=bad,
            exam_fee_relief_inr=bad,
            total_fee_relief_inr=bad,
            effective_relief_rate=bad,
        )
        assert bd.annual_tuition_fee == 0.0
        assert bd.annual_exam_fee == 0.0
        assert bd.tuition_reimbursement_rate == 0.0
        assert bd.exam_reimbursement_rate == 0.0
        assert bd.tuition_fee_relief_inr == 0.0
        assert bd.exam_fee_relief_inr == 0.0
        assert bd.total_fee_relief_inr == 0.0
        assert bd.effective_relief_rate == 0.0
        assert not isinstance(bd.annual_tuition_fee, bool)

    # Valid values are preserved
    bd_valid = FeeComponentBreakdown(
        annual_tuition_fee=85000.0,
        annual_exam_fee=7500.0,
        tuition_reimbursement_rate=1.0,
        exam_reimbursement_rate=1.0,
        tuition_fee_relief_inr=85000.0,
        exam_fee_relief_inr=7500.0,
        total_fee_relief_inr=92500.0,
        effective_relief_rate=1.0,
    )
    assert bd_valid.annual_tuition_fee == 85000.0
    assert bd_valid.annual_exam_fee == 7500.0
    assert bd_valid.total_fee_relief_inr == 92500.0

    print("PASS: test_stage2_2_1_fee_component_breakdown_monetary_sanitization")


def test_stage2_2_1_numeric_scalar_precision_and_validation():
    """
    Stage 2.2.1 Hotfix Regression Test:
    Verifies that _validate_numeric_scalar() accurately preserves native Python
    integers of arbitrary precision (including > 2**53 and 9007199254740993) without
    float precision loss, strictly handles whole-number vs fractional floats in
    integer-only mode, rejects booleans, None, strings, and non-finite values,
    safely checks max_value without unnecessary float conversion, and defends against
    OverflowError during float-valued validation.
    """
    # 1. Exact required regression assertion for 9007199254740993 (2**53 + 1)
    value = 9007199254740993
    is_valid, result, error = _validate_numeric_scalar(
        value,
        "test_integer",
        integer_only=True
    )
    assert is_valid is True
    assert result == value
    assert type(result) is int
    assert error is None

    # 2. Integers larger than 2**53 (arbitrary precision preservation)
    large_ints = [
        2**53 + 1,          # 9007199254740993
        2**53 + 3,          # 9007199254740995
        2**64 - 1,          # 18446744073709551615
        2**128 + 7,
        10**30,
        10**100,
    ]
    for li in large_ints:
        is_val, res, err = _validate_numeric_scalar(li, "test_large_int", integer_only=True)
        assert is_val is True
        assert res == li
        assert type(res) is int
        assert err is None

    # 3. None rejection
    is_val, res, err = _validate_numeric_scalar(None, "test_none")
    assert is_val is False
    assert res is None
    assert "missing" in err

    # 4. True and False boolean rejection (bool is subclass of int)
    for b in (True, False):
        for int_mode in (True, False):
            is_val, res, err = _validate_numeric_scalar(b, "test_bool", integer_only=int_mode)
            assert is_val is False
            assert res is None
            assert "cannot be a boolean" in err

    # 5. Numeric strings and non-numeric types rejection
    unsupported_inputs = ["100", "0", "-5.5", "nan", "inf", [1, 2], {"val": 10}]
    for bad in unsupported_inputs:
        for int_mode in (True, False):
            is_val, res, err = _validate_numeric_scalar(bad, "test_unsupported", integer_only=int_mode)
            assert is_val is False
            assert res is None
            assert "must be numeric" in err

    # 6. NaN rejection (finite number validation)
    for int_mode in (True, False):
        is_val, res, err = _validate_numeric_scalar(float("nan"), "test_nan", integer_only=int_mode)
        assert is_val is False
        assert res is None
        assert "non-finite" in err

    # 7. Positive and negative infinity rejection
    for inf_val in (float("inf"), float("-inf")):
        for int_mode in (True, False):
            is_val, res, err = _validate_numeric_scalar(inf_val, "test_inf", integer_only=int_mode)
            assert is_val is False
            assert res is None
            assert "non-finite" in err

    # 8. Negative values when negatives are disallowed (allow_negative=False)
    # Native int negative
    is_val, res, err = _validate_numeric_scalar(-15, "test_neg", allow_negative=False, integer_only=True)
    assert is_val is False
    assert res is None
    assert "cannot be negative" in err

    # Float negative in int mode
    is_val, res, err = _validate_numeric_scalar(-15.0, "test_neg", allow_negative=False, integer_only=True)
    assert is_val is False
    assert res is None
    assert "cannot be negative" in err

    # Float negative in float mode
    is_val, res, err = _validate_numeric_scalar(-15.75, "test_neg", allow_negative=False, integer_only=False)
    assert is_val is False
    assert res is None
    assert "cannot be negative" in err

    # 9. Negative values when allow_negative=True
    is_val, res, err = _validate_numeric_scalar(-15, "test_neg_ok", allow_negative=True, integer_only=True)
    assert is_val is True
    assert res == -15
    assert type(res) is int
    assert err is None

    is_val, res, err = _validate_numeric_scalar(-15.0, "test_neg_ok", allow_negative=True, integer_only=True)
    assert is_val is True
    assert res == -15
    assert type(res) is int
    assert err is None

    is_val, res, err = _validate_numeric_scalar(-15.75, "test_neg_ok", allow_negative=True, integer_only=False)
    assert is_val is True
    assert res == -15.75
    assert type(res) is float
    assert err is None

    # 10. Fractional floats with integer_only=True (must be rejected)
    fractional_floats = [0.1, 0.999, 1.0001, 5.5, -2.7, 12345.5, -98765.25]
    for frac in fractional_floats:
        is_val, res, err = _validate_numeric_scalar(frac, "test_frac", integer_only=True, allow_negative=True)
        assert is_val is False
        assert res is None
        assert "must be a whole integer" in err

    # 11. Whole-number floats in integer-only mode (must be accepted and converted to int)
    whole_floats = [(0.0, 0), (1.0, 1), (5.0, 5), (100.0, 100)]
    for wf, expected_int in whole_floats:
        is_val, res, err = _validate_numeric_scalar(wf, "test_whole_float", integer_only=True)
        assert is_val is True
        assert res == expected_int
        assert type(res) is int
        assert err is None

    # Negative whole-number float with allow_negative=True
    is_val, res, err = _validate_numeric_scalar(-4.0, "test_whole_float_neg", allow_negative=True, integer_only=True)
    assert is_val is True
    assert res == -4
    assert type(res) is int
    assert err is None

    # 12. Ordinary native integers
    for ival in (0, 1, 2, 42, 100000, 800000):
        is_val, res, err = _validate_numeric_scalar(ival, "test_ord_int", integer_only=True)
        assert is_val is True
        assert res == ival
        assert type(res) is int
        assert err is None

    # 13. Values exceeding max_value (checked without unnecessary float conversions)
    # Native int exceeding max_value in integer-only mode
    is_val, res, err = _validate_numeric_scalar(150, "test_max", max_value=100, integer_only=True)
    assert is_val is False
    assert res is None
    assert "exceeds maximum allowed threshold" in err

    # Large integer exceeding max_value in integer-only mode (without float conversion)
    is_val, res, err = _validate_numeric_scalar(10**1000, "test_max_large", max_value=100.0, integer_only=True)
    assert is_val is False
    assert res is None
    assert "exceeds maximum allowed threshold" in err

    # Float exceeding max_value
    is_val, res, err = _validate_numeric_scalar(105.5, "test_max_float", max_value=100.0, integer_only=False)
    assert is_val is False
    assert res is None
    assert "exceeds maximum allowed threshold" in err

    # Value exactly at max_value is accepted
    is_val, res, err = _validate_numeric_scalar(100.0, "test_max_exact", max_value=100.0, integer_only=False)
    assert is_val is True
    assert res == 100.0
    assert err is None

    # 14. Extremely large integers triggering float conversion overflow in float-valued validation
    extreme_pos = 10**1000
    is_val, res, err = _validate_numeric_scalar(extreme_pos, "test_extreme_pos", integer_only=False)
    assert is_val is False
    assert res is None
    assert "overflow" in err

    extreme_neg = -10**1000
    is_val, res, err = _validate_numeric_scalar(extreme_neg, "test_extreme_neg", allow_negative=True, integer_only=False)
    assert is_val is False
    assert res is None
    assert "overflow" in err

    print("PASS: test_stage2_2_1_numeric_scalar_precision_and_validation")


if __name__ == "__main__":
    test_female_student_100_percent_waiver_across_institutions()
    test_male_student_income_under_2_5_lakh_govt_vs_private()
    test_male_student_income_2_5_to_8_lakh()
    test_income_boundary_conditions()
    test_tuition_and_exam_fee_separation()
    test_missing_and_zero_fee_handling()
    test_cap_vs_non_cap_admission()
    test_eligible_vs_excluded_institutions()
    test_attendance_and_first_year_exemption()
    test_orphan_100_percent_waiver()
    test_family_beneficiary_limit()
    test_non_domicile_applicant()
    test_concurrent_scholarship_restriction()
    test_academic_gap_exceeding_limit()
    test_previous_examination_failure()
    test_missing_none_numeric_attributes()
    test_missing_none_enum_string_attributes()
    test_invalid_and_negative_fee_inputs()
    test_configurable_caste_enforcement()
    test_ineligible_student_cannot_receive_benefit()
    test_eligibility_and_benefit_consistency()
    test_provisional_policy_status_and_version()
    test_deterministic_repeated_calculations()
    test_backward_compatibility_contract()
    # Stage 2.2 additions:
    test_stage2_2_invalid_numeric_data_types()
    test_stage2_2_first_year_and_continuing_reconciliation()
    test_stage2_2_assumed_reimbursement_rate_validation()
    test_stage2_2_invalid_fee_inputs_clamping()
    # Stage 2.2.1 additions:
    test_stage2_2_1_ineligible_applicant_invalid_fees()
    test_stage2_2_1_fee_component_breakdown_monetary_sanitization()
    test_stage2_2_1_numeric_scalar_precision_and_validation()
    print("All Stage 2.2.1 DTE Policy Engine tests (31 suites) passed successfully!")
