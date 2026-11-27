import math
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple, Union

from simulation.persona import StudentPersona, InstitutionType, AdmissionMode


class EpistemicStatus(str, Enum):
    """Epistemic classification of rules and assumptions."""
    VERIFIED = "VERIFIED"         # Directly verified against primary GR or official gazette available locally
    PROVISIONAL = "PROVISIONAL"   # Supported by departmental circulars or university directives, awaiting primary GR PDF
    UNVERIFIED = "UNVERIFIED"     # Simulation prior or modeled hypothesis without official citation


class ScholarshipRoute(str, Enum):
    """Scholarship status classification for the DTE EBC scheme."""
    DTE_EBC = "DTE_EBC"           # Rajarshi Chhatrapati Shahu Maharaj EBC Scheme
    INELIGIBLE = "INELIGIBLE"     # Disqualified under statutory criteria


def _validate_numeric_scalar(
    val: Any,
    field_name: str,
    allow_negative: bool = False,
    integer_only: bool = False,
    max_value: Optional[float] = None
) -> Tuple[bool, Optional[Union[int, float]], Optional[str]]:
    """
    Validates that a field is a valid finite numeric value.
    Strictly rejects boolean values, non-numeric types, strings, NaN, Infinity,
    and negative values (unless allow_negative is True).
    Preserves native Python integers exactly without float precision loss.
    """
    if val is None:
        return False, None, f"{field_name} is missing (None)."
    if isinstance(val, bool):
        return False, None, f"{field_name} cannot be a boolean value ({val})."
    if not isinstance(val, (int, float)):
        return False, None, f"{field_name} must be numeric, got {type(val).__name__} ({val!r})."

    if integer_only:
        if isinstance(val, int):
            if not allow_negative and val < 0:
                return False, None, f"{field_name} cannot be negative ({val})."
            if max_value is not None and val > max_value:
                return False, None, f"{field_name} ({val}) exceeds maximum allowed threshold ({max_value})."
            return True, val, None

        # val is float
        try:
            if math.isnan(val) or math.isinf(val):
                return False, None, f"{field_name} is non-finite ({val})."
        except (OverflowError, ValueError):
            return False, None, f"{field_name} exceeds representable numeric limits (overflow)."

        if not val.is_integer():
            return False, None, f"{field_name} must be a whole integer, got {val}."

        try:
            int_val = int(val)
        except (OverflowError, ValueError):
            return False, None, f"{field_name} exceeds representable numeric limits (overflow)."

        if not allow_negative and int_val < 0:
            return False, None, f"{field_name} cannot be negative ({val})."
        if max_value is not None and int_val > max_value:
            return False, None, f"{field_name} ({int_val}) exceeds maximum allowed threshold ({max_value})."
        return True, int_val, None

    # Float-valued validation (integer_only=False)
    if isinstance(val, float):
        try:
            if math.isnan(val) or math.isinf(val):
                return False, None, f"{field_name} is non-finite ({val})."
            num = val
        except (OverflowError, ValueError):
            return False, None, f"{field_name} exceeds representable numeric limits (overflow)."
    else:  # val is int
        try:
            num = float(val)
        except (OverflowError, ValueError):
            return False, None, f"{field_name} exceeds representable numeric limits (overflow)."

    if not allow_negative and num < 0.0:
        return False, None, f"{field_name} cannot be negative ({val})."
    if max_value is not None and num > max_value:
        return False, None, f"{field_name} ({num}) exceeds maximum allowed threshold ({max_value})."
    return True, num, None


@dataclass
class FeeComponentBreakdown:
    """Itemized breakdown of instructional tuition fees and university examination fees."""
    annual_tuition_fee: float
    annual_exam_fee: float
    tuition_reimbursement_rate: float
    exam_reimbursement_rate: float
    tuition_fee_relief_inr: float
    exam_fee_relief_inr: float
    total_fee_relief_inr: float
    effective_relief_rate: float
    missing_fee_notes: List[str] = field(default_factory=list)

    def __post_init__(self):
        """
        Defensively guarantees that every monetary and rate field is numeric, finite,
        non-negative, and not a boolean. Any invalid value safely defaults to 0.0.
        """
        numeric_fields = (
            "annual_tuition_fee",
            "annual_exam_fee",
            "tuition_reimbursement_rate",
            "exam_reimbursement_rate",
            "tuition_fee_relief_inr",
            "exam_fee_relief_inr",
            "total_fee_relief_inr",
            "effective_relief_rate",
        )
        for field_name in numeric_fields:
            val = getattr(self, field_name, 0.0)
            is_valid, valid_val, _ = _validate_numeric_scalar(val, field_name, allow_negative=False)
            if not is_valid:
                setattr(self, field_name, 0.0)
            else:
                setattr(self, field_name, float(valid_val))


@dataclass
class DTEPolicyConfig:
    """
    Configurable options and parameters for the DTE Scholarship Policy Engine.
    All parameters are documented with their epistemic confidence tier.
    """
    policy_version: str = "2024.1-provisional"
    default_verification_status: str = EpistemicStatus.PROVISIONAL.value

    # Statutory eligibility parameters (PROVISIONAL: GR 31.03.2018 research reference)
    max_income_limit: float = 800000.0             # PROVISIONAL: INR 8 Lakh annual household ceiling
    income_slab_lower: float = 250000.0            # PROVISIONAL: INR 2.5 Lakh lower threshold for male govt/aided 100%
    max_family_beneficiaries: int = 2              # PROVISIONAL: Max 2 beneficiaries per family in current academic year
    min_attendance_percent: float = 50.0           # PROVISIONAL: MahaDBT statutory minimum threshold (50.0%)
    institutional_attendance_threshold: float = 75.0 # PROVISIONAL: Standard college term-end exam target (75.0%)
    use_strict_institutional_attendance: bool = True # Preserves 75% for default cohort baseline compatibility
    max_permissible_gap_years: int = 2             # PROVISIONAL: Maximum permissible educational gap across course

    # Gender and orphan concession parameters (PROVISIONAL: GR 08.07.2024 research reference)
    enable_female_100_percent_rule: bool = True    # PROVISIONAL: 100% Tuition & Exam waiver for female students
    female_tuition_rate: float = 1.00              # Configurable female tuition reimbursement rate
    female_exam_rate: float = 1.00                 # Configurable female exam reimbursement rate

    enable_orphan_100_percent_rule: bool = True    # PROVISIONAL: 100% Tuition & Exam waiver for orphans
    orphan_tuition_rate: float = 1.00              # Configurable orphan tuition reimbursement rate
    orphan_exam_rate: float = 1.00                 # Configurable orphan exam reimbursement rate

    # Male tiered concession rates (PROVISIONAL: GR 31.03.2018 research reference)
    male_tier1_govt_tuition_rate: float = 1.00     # Income <= 2.5L in Govt / Aided colleges
    male_tier1_pvt_tuition_rate: float = 0.50      # Income <= 2.5L in Private Unaided colleges
    male_tier2_tuition_rate: float = 0.50          # Income between 2.5L and 8.0L across all eligible institutions
    male_exam_rate: float = 0.50                   # Standard 50% exam reimbursement for male students

    # Configurable caste filter (Optional, default None = open evaluation under DTE EBC)
    allowed_caste_categories: Optional[List[str]] = None

    # Fallback / baseline settings
    default_poc_rate: float = 0.50                 # Baseline fallback rate when explicit override is provided


@dataclass
class RuleCheckResult:
    """Individual rule evaluation output with epistemic traceability."""
    rule_name: str
    is_satisfied: bool
    observed_value: Any
    threshold_or_condition: str
    message: str
    epistemic_status: str = EpistemicStatus.PROVISIONAL.value


@dataclass
class PolicyEvaluationResult:
    """
    Structured outcome of the DTE policy evaluation.
    Preserves 100% backward compatibility for existing callers while exposing granular fee breakdowns.
    """
    scheme_name: str
    is_eligible: bool
    reimbursement_percentage: float   # Configured / effective overall benefit percentage (0.0 to 1.0)
    estimated_fee_relief_inr: float   # Total estimated annual fee relief amount (Tuition + Exam)
    rule_checks: List[RuleCheckResult] = field(default_factory=list)
    failure_reasons: List[str] = field(default_factory=list)
    statutory_notes: List[str] = field(default_factory=list)
    benefit_assumptions: List[str] = field(default_factory=list)

    # Detailed fee component breakdown
    tuition_fee_relief_inr: float = 0.0
    exam_fee_relief_inr: float = 0.0
    tuition_reimbursement_percentage: float = 0.0
    exam_reimbursement_percentage: float = 0.0

    # Policy governance, versioning and diagnostics
    policy_version: str = "2024.1-provisional"
    verification_status: str = EpistemicStatus.PROVISIONAL.value
    indeterminate_reasons: List[str] = field(default_factory=list)
    fee_breakdown: Optional[FeeComponentBreakdown] = None

    # Backward compatibility fields (DTE scheme only)
    scholarship_route: str = ScholarshipRoute.DTE_EBC.value
    alternate_scheme_name: Optional[str] = None
    routing_reason: Optional[str] = None


class RajarshiShahuPolicyEngine:
    """
    Deterministic rule engine for Rajarshi Chhatrapati Shahu Maharaj
    Shikshan Shulk Shishyavrutti Yojna (EBC Scholarship Scheme - Maharashtra).

    Separates statutory eligibility criteria from configurable PoC benefit estimates.
    """
    SCHEME_NAME: str = "Rajarshi Chhatrapati Shahu Maharaj Shikshan Shulk Shishyavrutti Yojna"
    MAX_INCOME_LIMIT: float = 800000.0            # INR 8,00,000 per annum (PROVISIONAL: GR 31.03.2018)
    LOWER_INCOME_SLAB: float = 250000.0           # INR 2,50,000 per annum (PROVISIONAL: GR 31.03.2018)
    MAX_FAMILY_BENEFICIARIES: int = 2             # Maximum 2 children per family (PROVISIONAL: MahaDBT undertaking)
    MIN_ATTENDANCE_PERCENT: float = 75.0          # Institutional standard; statutory is 50.0%
    STATUTORY_MIN_ATTENDANCE_PERCENT: float = 50.0 # Provisional MahaDBT statutory threshold
    MAX_PERMISSIBLE_GAP_YEARS: int = 2             # Permissible education gap years (PROVISIONAL)
    DEFAULT_POC_ASSUMED_REIMBURSEMENT_RATE: float = 0.50

    DEFAULT_CONFIG = DTEPolicyConfig()

    @classmethod
    def check_statutory_eligibility(
        cls,
        persona: StudentPersona,
        config: Optional[DTEPolicyConfig] = None
    ) -> Tuple[bool, List[RuleCheckResult], List[str]]:
        """
        Evaluates the 8 core statutory eligibility criteria from DTE scheme rules.
        Preserves exact 8-check contract expected by existing callers and tests.
        Safely validates input types, strictly rejecting booleans, strings, non-finite
        numbers, and malformed inputs without unhandled exceptions.
        """
        cfg = config or cls.DEFAULT_CONFIG
        rule_checks: List[RuleCheckResult] = []
        failure_reasons: List[str] = []

        # 1. Maharashtra Domicile Check (PROVISIONAL)
        dom_val = getattr(persona, "is_maharashtra_domicile", None)
        if dom_val is None:
            is_domicile = False
            observed_domicile = "Missing / Not Provided"
            failure_reasons.append("Maharashtra domicile status is missing or not provided.")
        elif not isinstance(dom_val, bool):
            is_domicile = False
            observed_domicile = f"Invalid ({type(dom_val).__name__}: {dom_val!r})"
            failure_reasons.append(f"Maharashtra domicile must be a boolean, got {type(dom_val).__name__}.")
        elif not dom_val:
            is_domicile = False
            observed_domicile = False
            failure_reasons.append("Applicant is not a domicile of Maharashtra.")
        else:
            is_domicile = True
            observed_domicile = True

        rule_checks.append(RuleCheckResult(
            rule_name="Maharashtra Domicile",
            is_satisfied=is_domicile,
            observed_value=observed_domicile,
            threshold_or_condition="Must be true",
            message="Applicant must possess valid Maharashtra domicile (or recognized border village certificate).",
            epistemic_status=EpistemicStatus.PROVISIONAL.value
        ))

        # 2. Annual Family Income Cap (PROVISIONAL: GR 31.03.2018)
        inc_val = getattr(persona, "family_income", None)
        is_inc_valid, valid_income, inc_err = _validate_numeric_scalar(
            inc_val, "Annual family income", allow_negative=False
        )
        if not is_inc_valid:
            is_income_eligible = False
            income_str = f"Invalid/Missing ({inc_err})"
            failure_reasons.append(f"Annual family income is invalid or missing: {inc_err}")
        else:
            is_income_eligible = valid_income <= cfg.max_income_limit
            income_str = f"INR {valid_income:,.2f}"
            if not is_income_eligible:
                failure_reasons.append(
                    f"Annual family income ({income_str}) exceeds the statutory limit of INR {cfg.max_income_limit:,.2f}."
                )

        rule_checks.append(RuleCheckResult(
            rule_name="Family Income Cap",
            is_satisfied=is_income_eligible,
            observed_value=income_str,
            threshold_or_condition=f"<= INR {cfg.max_income_limit:,.2f}",
            message=f"Annual family income must not exceed INR {cfg.max_income_limit:,.2f}.",
            epistemic_status=EpistemicStatus.PROVISIONAL.value
        ))

        # 3. Admission Mode (CAP for professional courses) (PROVISIONAL)
        adm_mode = getattr(persona, "admission_mode", None)
        adm_mode_str = (
            adm_mode.value
            if hasattr(adm_mode, "value")
            else str(adm_mode)
            if adm_mode is not None
            else None
        )

        is_prof_course = getattr(persona, "is_professional_course", True)
        if not isinstance(is_prof_course, bool):
            is_prof_course = True

        if is_prof_course:
            if adm_mode is None:
                is_cap_admitted = False
                observed_adm = "Missing / Not Provided"
                failure_reasons.append("Admission mode is missing; CAP admission verification is required for professional courses.")
            else:
                is_cap_admitted = (
                    adm_mode == AdmissionMode.CAP
                    or adm_mode_str == AdmissionMode.CAP.value
                )
                observed_adm = adm_mode_str
                if not is_cap_admitted:
                    failure_reasons.append(
                        f"Admission mode is '{adm_mode_str}'; scheme requires CAP admission for professional courses."
                    )

            rule_checks.append(RuleCheckResult(
                rule_name="CAP Admission Compliance",
                is_satisfied=is_cap_admitted,
                observed_value=observed_adm,
                threshold_or_condition="CAP (Centralized Admission Process)",
                message="For professional/technical courses, admission must be through CAP merit rounds.",
                epistemic_status=EpistemicStatus.PROVISIONAL.value
            ))
        else:
            observed_adm = adm_mode_str if adm_mode_str is not None else "N/A (Non-professional course)"
            rule_checks.append(RuleCheckResult(
                rule_name="CAP Admission Compliance",
                is_satisfied=True,
                observed_value=observed_adm,
                threshold_or_condition="N/A (Non-professional course)",
                message="Non-professional general merit admission is acceptable.",
                epistemic_status=EpistemicStatus.PROVISIONAL.value
            ))

        # 4. Institution Eligibility & Exclusions (PROVISIONAL)
        inst_type = getattr(persona, "institution_type", None)
        if inst_type is None:
            is_institution_eligible = False
            observed_inst = "Missing / Not Provided"
            failure_reasons.append("Institution type is missing; cannot verify institution eligibility.")
        else:
            inst_str = (
                inst_type.value
                if hasattr(inst_type, "value")
                else str(inst_type)
            )
            observed_inst = inst_str
            is_deemed = (
                inst_type == InstitutionType.DEEMED_OR_PRIVATE_UNIVERSITY
                or inst_str == InstitutionType.DEEMED_OR_PRIVATE_UNIVERSITY.value
            )
            is_institution_eligible = (not is_deemed) and (
                inst_type in [
                    InstitutionType.GOVERNMENT,
                    InstitutionType.GOVERNMENT_AIDED,
                    InstitutionType.PRIVATE_UNAIDED
                ]
                or inst_str in [
                    InstitutionType.GOVERNMENT.value,
                    InstitutionType.GOVERNMENT_AIDED.value,
                    InstitutionType.PRIVATE_UNAIDED.value
                ]
            )
            if is_deemed:
                failure_reasons.append(
                    "Institution type 'Deemed/Private-University' is statutorily excluded under MahaDBT DTE rules."
                )
            elif not is_institution_eligible:
                failure_reasons.append(
                    f"Institution type '{inst_str}' is ineligible for state EBC fee reimbursement."
                )

        rule_checks.append(RuleCheckResult(
            rule_name="Institution Eligibility",
            is_satisfied=is_institution_eligible,
            observed_value=observed_inst,
            threshold_or_condition="Government, Govt-Aided, or Recognized Private-Unaided",
            message="Institution must be state-approved and participating in MahaDBT (Deemed/Private Universities excluded).",
            epistemic_status=EpistemicStatus.PROVISIONAL.value
        ))

        # 5. Family Beneficiaries Cap (PROVISIONAL: MahaDBT Mandatory Undertaking)
        ben_raw = getattr(persona, "family_beneficiaries_count", None)
        is_ben_valid, valid_ben, ben_err = _validate_numeric_scalar(
            ben_raw, "Family beneficiaries count", allow_negative=False, integer_only=True
        )
        if not is_ben_valid:
            is_beneficiary_cap_satisfied = False
            observed_ben = f"Invalid/Missing ({ben_err})"
            failure_reasons.append(f"Family beneficiaries count is invalid or missing: {ben_err}")
        else:
            is_beneficiary_cap_satisfied = valid_ben < cfg.max_family_beneficiaries
            observed_ben = valid_ben
            if not is_beneficiary_cap_satisfied:
                failure_reasons.append(
                    f"Family already has {valid_ben} beneficiaries (maximum limit is {cfg.max_family_beneficiaries} children in current year)."
                )

        rule_checks.append(RuleCheckResult(
            rule_name="Family Beneficiary Cap",
            is_satisfied=is_beneficiary_cap_satisfied,
            observed_value=observed_ben,
            threshold_or_condition=f"< {cfg.max_family_beneficiaries} existing beneficiaries",
            message=f"Only maximum {cfg.max_family_beneficiaries} children from the same family can claim the benefit in an academic year.",
            epistemic_status=EpistemicStatus.PROVISIONAL.value
        ))

        # 6. Concurrent Scholarship Prohibition (PROVISIONAL)
        schol_val = getattr(persona, "has_other_scholarship", None)
        if schol_val is None:
            no_other_scholarship = False
            observed_schol = "Missing / Not Provided"
            failure_reasons.append("Concurrent scholarship status is missing; cannot verify dual-scholarship prohibition.")
        elif not isinstance(schol_val, bool):
            no_other_scholarship = False
            observed_schol = f"Invalid ({type(schol_val).__name__}: {schol_val!r})"
            failure_reasons.append(f"Concurrent scholarship flag must be a boolean, got {type(schol_val).__name__}.")
        else:
            no_other_scholarship = not schol_val
            observed_schol = f"Has other: {schol_val}"
            if not no_other_scholarship:
                failure_reasons.append("Applicant is already receiving another government scholarship.")

        rule_checks.append(RuleCheckResult(
            rule_name="No Concurrent Scholarship",
            is_satisfied=no_other_scholarship,
            observed_value=observed_schol,
            threshold_or_condition="Must not hold concurrent government scholarship",
            message="Students cannot claim dual state/central scholarships for the same course.",
            epistemic_status=EpistemicStatus.PROVISIONAL.value
        ))

        # 7. Academic Progress and Gap Years (PROVISIONAL)
        # Reconciled behavior:
        # Both first-year and continuing students require previous_year_passed to be verified as True.
        # - For continuing students: confirms passing previous college year.
        # - For first-year entrants: confirms passing qualifying entrance examination (e.g. 12th/Diploma).
        # - Missing (None) or non-boolean previous_year_passed fails safely with an explicit message.
        is_first_yr_val = getattr(persona, "is_first_year", False)
        is_first_yr = bool(is_first_yr_val) if isinstance(is_first_yr_val, bool) else False

        gap_raw = getattr(persona, "academic_gap_years", None)
        is_gap_valid, valid_gap, gap_err = _validate_numeric_scalar(
            gap_raw, "Academic gap years", allow_negative=False, integer_only=True
        )
        gap_ok = is_gap_valid and (valid_gap <= cfg.max_permissible_gap_years)

        prev_passed = getattr(persona, "previous_year_passed", None)
        is_prev_passed_valid = isinstance(prev_passed, bool)

        if is_first_yr:
            if prev_passed is None:
                is_academic_progress_ok = False
                observed_prog = f"First-Year Entrant, Qualifying Exam: Missing, Gap: {valid_gap if is_gap_valid else 'Invalid'}"
                failure_reasons.append("Qualifying examination passing status is missing or not provided for first-year entrant.")
            elif not is_prev_passed_valid:
                is_academic_progress_ok = False
                observed_prog = f"First-Year Entrant, Qualifying Exam: Invalid ({type(prev_passed).__name__}), Gap: {valid_gap if is_gap_valid else 'Invalid'}"
                failure_reasons.append(f"Qualifying examination passing status must be a boolean, got {type(prev_passed).__name__}.")
            elif not prev_passed:
                is_academic_progress_ok = False
                observed_prog = f"First-Year Entrant, Failed Qualifying Exam, Gap: {valid_gap if is_gap_valid else 'Invalid'}"
                failure_reasons.append("Applicant did not pass the qualifying examination for admission.")
            elif not is_gap_valid:
                is_academic_progress_ok = False
                observed_prog = f"First-Year Entrant, Qualifying Exam: Passed, Gap: Invalid ({gap_err})"
                failure_reasons.append(f"Academic gap years information is invalid or missing: {gap_err}")
            elif not gap_ok:
                is_academic_progress_ok = False
                observed_prog = f"First-Year Entrant, Qualifying Exam: Passed, Gap: {valid_gap} yrs"
                failure_reasons.append(
                    f"Academic gap ({valid_gap} years) exceeds maximum allowed ({cfg.max_permissible_gap_years} years)."
                )
            else:
                is_academic_progress_ok = True
                observed_prog = f"First-Year Entrant, Passed Qualifying Exam, Gap: {valid_gap} yrs"
        else:
            if prev_passed is None:
                is_academic_progress_ok = False
                observed_prog = f"Passed: Missing, Gap: {valid_gap if is_gap_valid else 'Invalid'}"
                failure_reasons.append("Previous academic year passing status is missing or not provided.")
            elif not is_prev_passed_valid:
                is_academic_progress_ok = False
                observed_prog = f"Passed: Invalid ({type(prev_passed).__name__}), Gap: {valid_gap if is_gap_valid else 'Invalid'}"
                failure_reasons.append(f"Previous academic year passing status must be a boolean, got {type(prev_passed).__name__}.")
            elif not prev_passed:
                is_academic_progress_ok = False
                observed_prog = f"Passed: False, Gap: {valid_gap if is_gap_valid else 'Invalid'}"
                failure_reasons.append("Applicant did not pass the previous academic year/qualifying examination.")
            elif not is_gap_valid:
                is_academic_progress_ok = False
                observed_prog = f"Passed: True, Gap: Invalid ({gap_err})"
                failure_reasons.append(f"Academic gap years information is invalid or missing: {gap_err}")
            elif not gap_ok:
                is_academic_progress_ok = False
                observed_prog = f"Passed: True, Gap: {valid_gap} yrs"
                failure_reasons.append(
                    f"Academic gap ({valid_gap} years) exceeds maximum allowed ({cfg.max_permissible_gap_years} years)."
                )
            else:
                is_academic_progress_ok = True
                observed_prog = f"Passed: True, Gap: {valid_gap} yrs"

        rule_checks.append(RuleCheckResult(
            rule_name="Academic Progress & Gap",
            is_satisfied=is_academic_progress_ok,
            observed_value=observed_prog,
            threshold_or_condition=f"Passed qualifying/previous exam and Gap <= {cfg.max_permissible_gap_years} yrs",
            message="Applicant must have passed the previous qualifying examination with permissible educational gap.",
            epistemic_status=EpistemicStatus.PROVISIONAL.value
        ))

        # 8. Minimum Attendance Requirement with First-Year Exemption (PROVISIONAL: MahaDBT Rules)
        if is_first_yr:
            is_attendance_ok = True
            observed_att = "First-Year Exempt"
            att_message = "First-year fresh entrant is statutorily exempt from previous semester attendance proof."
            att_threshold_str = "Exempt (First-Year)"
        else:
            eff_att_threshold = (
                cfg.institutional_attendance_threshold
                if cfg.use_strict_institutional_attendance
                else cfg.min_attendance_percent
            )
            att_raw = getattr(persona, "attendance_percentage", None)
            is_att_valid, valid_att, att_err = _validate_numeric_scalar(
                att_raw, "Attendance percentage", allow_negative=False, max_value=100.0
            )
            if not is_att_valid:
                is_attendance_ok = False
                observed_att = f"Invalid/Missing ({att_err})"
                att_threshold_str = f">= {eff_att_threshold:.1f}%"
                att_message = f"Attendance percentage is invalid or missing: {att_err}"
                failure_reasons.append(
                    f"Attendance percentage is invalid or missing: {att_err}"
                )
            else:
                is_attendance_ok = valid_att >= eff_att_threshold
                observed_att = f"{valid_att:.1f}%"
                att_threshold_str = f">= {eff_att_threshold:.1f}%"
                att_message = f"Mandatory minimum attendance threshold is {eff_att_threshold:.1f}%."
                if not is_attendance_ok:
                    failure_reasons.append(
                        f"Attendance ({valid_att:.1f}%) is below statutory requirement ({eff_att_threshold:.1f}%)."
                    )

        rule_checks.append(RuleCheckResult(
            rule_name="Minimum Attendance Requirement",
            is_satisfied=is_attendance_ok,
            observed_value=observed_att,
            threshold_or_condition=att_threshold_str,
            message=att_message,
            epistemic_status=EpistemicStatus.PROVISIONAL.value
        ))

        # Optional configurable caste/category filter (default None = open evaluation under DTE EBC)
        if cfg.allowed_caste_categories is not None:
            caste_raw = (getattr(persona, "caste_category", "") or "").strip().upper()
            allowed_normalized = [c.strip().upper() for c in cfg.allowed_caste_categories]
            if caste_raw not in allowed_normalized:
                failure_reasons.append(
                    f"Caste category '{getattr(persona, 'caste_category', None)}' is not eligible under the configured DTE scheme scope."
                )

        is_eligible = (len(failure_reasons) == 0)
        return is_eligible, rule_checks, failure_reasons

    @classmethod
    def calculate_dte_benefit(
        cls,
        persona: StudentPersona,
        is_eligible: bool,
        config: Optional[DTEPolicyConfig] = None,
        assumed_reimbursement_rate: Optional[float] = None
    ) -> Tuple[float, float, FeeComponentBreakdown, List[str], List[str]]:
        """
        Calculates itemized Tuition Fee and Examination Fee relief deterministically.
        Ineligible applicants strictly receive INR 0.00 relief and 0.0 reimbursement rate.
        Calculated relief amounts are clamped and strictly bounded by assessed fee components.
        Invalid, boolean, non-finite, or malformed inputs are safely handled and clamped to INR 0.00.
        """
        cfg = config or cls.DEFAULT_CONFIG
        statutory_notes: List[str] = []
        benefit_assumptions: List[str] = []
        missing_fee_notes: List[str] = []

        # Validate, sanitize, and clamp tuition fee input for ALL applicants (eligible & ineligible)
        raw_tuition = (
            getattr(persona, "annual_tuition_fee", None)
            if not isinstance(persona, dict)
            else persona.get("annual_tuition_fee", None)
        )
        is_t_valid, valid_tuition, t_err = _validate_numeric_scalar(
            raw_tuition, "annual_tuition_fee", allow_negative=False
        )
        if not is_t_valid or valid_tuition == 0.0:
            tuition_fee = 0.0
            diag_t = t_err if not is_t_valid else "INR 0.00"
            missing_fee_notes.append(
                f"Notice: annual_tuition_fee is {diag_t}. Tuition fee relief calculated as INR 0.00."
            )
        else:
            tuition_fee = float(valid_tuition)

        # Validate, sanitize, and clamp examination fee input for ALL applicants (eligible & ineligible)
        raw_exam = (
            getattr(persona, "annual_exam_fee", 0.0)
            if not isinstance(persona, dict)
            else persona.get("annual_exam_fee", 0.0)
        )
        is_e_valid, valid_exam, e_err = _validate_numeric_scalar(
            raw_exam, "annual_exam_fee", allow_negative=False
        )
        if not is_e_valid or valid_exam == 0.0:
            exam_fee = 0.0
            diag_e = e_err if not is_e_valid else "INR 0.00"
            missing_fee_notes.append(
                f"Notice: annual_exam_fee is {diag_e}. No separate examination fee reimbursement calculated."
            )
        else:
            exam_fee = float(valid_exam)

        # STRICT GUARANTEE: Ineligible applicants receive zero benefit under all circumstances.
        # Early return uses pre-sanitized numeric fee values; invalid inputs are clamped to 0.0.
        if not is_eligible:
            breakdown = FeeComponentBreakdown(
                annual_tuition_fee=tuition_fee,
                annual_exam_fee=exam_fee,
                tuition_reimbursement_rate=0.0,
                exam_reimbursement_rate=0.0,
                tuition_fee_relief_inr=0.0,
                exam_fee_relief_inr=0.0,
                total_fee_relief_inr=0.0,
                effective_relief_rate=0.0,
                missing_fee_notes=["Ineligible for statutory fee concession."] + missing_fee_notes
            )
            statutory_notes.append("Ineligible for fee reimbursement based on statutory criteria.")
            return 0.0, 0.0, breakdown, statutory_notes, benefit_assumptions

        # 1. Caller Override Mode Validation & Execution
        # If assumed_reimbursement_rate is explicitly provided:
        # Must be a finite numeric value from 0.0 through 1.0 inclusive (strictly rejecting booleans).
        # Invalid explicit overrides fail safely with diagnostics and produce INR 0.00 relief.
        if assumed_reimbursement_rate is not None:
            is_override_valid = True
            override_err: Optional[str] = None

            if isinstance(assumed_reimbursement_rate, bool):
                is_override_valid = False
                override_err = f"assumed_reimbursement_rate cannot be a boolean ({assumed_reimbursement_rate})."
            elif not isinstance(assumed_reimbursement_rate, (int, float)):
                is_override_valid = False
                override_err = f"assumed_reimbursement_rate must be numeric, got {type(assumed_reimbursement_rate).__name__} ({assumed_reimbursement_rate!r})."
            elif math.isnan(assumed_reimbursement_rate) or math.isinf(assumed_reimbursement_rate):
                is_override_valid = False
                override_err = f"assumed_reimbursement_rate is non-finite ({assumed_reimbursement_rate})."
            elif assumed_reimbursement_rate < 0.0 or assumed_reimbursement_rate > 1.0:
                is_override_valid = False
                override_err = f"assumed_reimbursement_rate ({assumed_reimbursement_rate}) is outside the valid range [0.0, 1.0]."

            if not is_override_valid:
                diag_msg = f"Invalid explicit override rate rejected: {override_err} Concession calculated as INR 0.00."
                statutory_notes.append(diag_msg)
                benefit_assumptions.append(diag_msg)
                missing_fee_notes.append(diag_msg)

                breakdown = FeeComponentBreakdown(
                    annual_tuition_fee=tuition_fee,
                    annual_exam_fee=exam_fee,
                    tuition_reimbursement_rate=0.0,
                    exam_reimbursement_rate=0.0,
                    tuition_fee_relief_inr=0.0,
                    exam_fee_relief_inr=0.0,
                    total_fee_relief_inr=0.0,
                    effective_relief_rate=0.0,
                    missing_fee_notes=missing_fee_notes
                )
                return 0.0, 0.0, breakdown, statutory_notes, benefit_assumptions

            # Valid explicit override rate execution
            override_val = float(assumed_reimbursement_rate)
            tuition_rate = override_val
            exam_rate = override_val if exam_fee > 0 else 0.0
            tuition_relief = round(min(tuition_fee, max(0.0, tuition_fee * tuition_rate)), 2)
            exam_relief = round(min(exam_fee, max(0.0, exam_fee * exam_rate)), 2)
            total_relief = round(tuition_relief + exam_relief, 2)
            denom = max(1.0, tuition_fee + exam_fee)
            eff_rate = round(total_relief / denom, 4)

            statutory_notes.append(
                f"Statutorily eligible under EBC scheme. Applied override rate of {tuition_rate * 100:.0f}%. "
                f"Estimated relief: INR {total_relief:,.2f} (Tuition: INR {tuition_relief:,.2f}, Exam: INR {exam_relief:,.2f})."
            )
            benefit_assumptions.append(
                f"PoC Assumption: Applied explicit reimbursement rate of {tuition_rate * 100:.0f}%."
            )

            breakdown = FeeComponentBreakdown(
                annual_tuition_fee=tuition_fee,
                annual_exam_fee=exam_fee,
                tuition_reimbursement_rate=tuition_rate,
                exam_reimbursement_rate=exam_rate,
                tuition_fee_relief_inr=tuition_relief,
                exam_fee_relief_inr=exam_relief,
                total_fee_relief_inr=total_relief,
                effective_relief_rate=eff_rate,
                missing_fee_notes=missing_fee_notes
            )
            return eff_rate, total_relief, breakdown, statutory_notes, benefit_assumptions

        # 2. Deterministic DTE Benefit Calculation (Provisional Policy Baseline)
        gender = (getattr(persona, "gender", "") or "").strip().lower()
        is_orphan_val = getattr(persona, "is_orphan", False)
        is_orphan = bool(is_orphan_val) if isinstance(is_orphan_val, bool) else False

        # Case A: Female Students & Orphans -> Configurable Rates (Default 100% under Provisional GR 08.07.2024 Reference)
        if (gender == "female" and cfg.enable_female_100_percent_rule) or (is_orphan and cfg.enable_orphan_100_percent_rule):
            target_label = "Orphan" if is_orphan else "Female"
            tuition_rate = cfg.orphan_tuition_rate if is_orphan else cfg.female_tuition_rate
            exam_rate = cfg.orphan_exam_rate if is_orphan else cfg.female_exam_rate
            statutory_notes.append(
                f"PROVISIONAL: Applied {tuition_rate*100:.0f}% Tuition Fee & {exam_rate*100:.0f}% Exam Fee waiver for {target_label} candidate under "
                f"research reference GR No. शिष्यवृ-२०२४/प्र.क्र.१०५/तांशि-४ (Dated 08 July 2024; unverified raw GR)."
            )
            benefit_assumptions.append(
                f"Provisional Policy Configuration (Version {cfg.policy_version}): {tuition_rate*100:.0f}% Tuition & {exam_rate*100:.0f}% Exam fee waiver for {target_label} student with family income <= INR {cfg.max_income_limit:,.0f}."
            )

        # Case B: Male Students -> Tiered by Income and Institution Type (Provisional GR 31.03.2018 Reference)
        else:
            exam_rate = cfg.male_exam_rate
            fam_inc = getattr(persona, "family_income", 0.0) or 0.0

            # Tier 1: Income <= INR 2.50 Lakh
            if fam_inc <= cfg.income_slab_lower:
                inst_type = getattr(persona, "institution_type", None)
                inst_str = (
                    inst_type.value
                    if hasattr(inst_type, "value")
                    else str(inst_type)
                )
                if inst_type in [InstitutionType.GOVERNMENT, InstitutionType.GOVERNMENT_AIDED] or inst_str in [InstitutionType.GOVERNMENT.value, InstitutionType.GOVERNMENT_AIDED.value]:
                    tuition_rate = cfg.male_tier1_govt_tuition_rate
                    statutory_notes.append(
                        f"PROVISIONAL: Male candidate with income <= INR {cfg.income_slab_lower:,.0f} in Government/Aided college receives "
                        f"{tuition_rate*100:.0f}% Tuition Fee and {exam_rate*100:.0f}% Exam Fee reimbursement (research reference GR TEM-2018/C.R.35/TE-4)."
                    )
                else:
                    tuition_rate = cfg.male_tier1_pvt_tuition_rate
                    statutory_notes.append(
                        f"PROVISIONAL: Male candidate with income <= INR {cfg.income_slab_lower:,.0f} in Private Unaided college receives "
                        f"{tuition_rate*100:.0f}% Tuition Fee and {exam_rate*100:.0f}% Exam Fee reimbursement (research reference GR TEM-2018/C.R.35/TE-4)."
                    )
                benefit_assumptions.append(
                    f"Provisional Policy Configuration (Version {cfg.policy_version}): Male income <= INR {cfg.income_slab_lower:,.0f} tier applied."
                )

            # Tier 2: Income between INR 2.50 Lakh and INR 8.00 Lakh
            else:
                tuition_rate = cfg.male_tier2_tuition_rate
                statutory_notes.append(
                    f"PROVISIONAL: Male candidate with income between INR {cfg.income_slab_lower:,.0f} and INR {cfg.max_income_limit:,.0f} receives "
                    f"{tuition_rate*100:.0f}% Tuition Fee and {exam_rate*100:.0f}% Exam Fee reimbursement across all eligible institution types (research reference GR TEM-2018/C.R.35/TE-4)."
                )
                benefit_assumptions.append(
                    f"Provisional Policy Configuration (Version {cfg.policy_version}): Standard male concession for income <= INR {cfg.max_income_limit:,.0f}."
                )

        # Calculate exact monetary fee reliefs, strictly bounded by assessed fee components
        tuition_relief = round(min(tuition_fee, max(0.0, tuition_fee * tuition_rate)), 2)
        exam_relief = round(min(exam_fee, max(0.0, exam_fee * exam_rate)), 2)
        total_relief = round(tuition_relief + exam_relief, 2)
        total_fee = tuition_fee + exam_fee
        eff_rate = round(total_relief / max(1.0, total_fee), 4)

        statutory_notes.append(
            f"Estimated total relief: INR {total_relief:,.2f} of total assessed fee INR {total_fee:,.2f} "
            f"(Tuition Relief: INR {tuition_relief:,.2f} @ {tuition_rate*100:.0f}%, "
            f"Exam Relief: INR {exam_relief:,.2f} @ {exam_rate*100:.0f}%)."
        )

        breakdown = FeeComponentBreakdown(
            annual_tuition_fee=tuition_fee,
            annual_exam_fee=exam_fee,
            tuition_reimbursement_rate=tuition_rate,
            exam_reimbursement_rate=exam_rate,
            tuition_fee_relief_inr=tuition_relief,
            exam_fee_relief_inr=exam_relief,
            total_fee_relief_inr=total_relief,
            effective_relief_rate=eff_rate,
            missing_fee_notes=missing_fee_notes
        )
        return eff_rate, total_relief, breakdown, statutory_notes, benefit_assumptions

    @classmethod
    def calculate_poc_benefit_estimate(
        cls,
        persona: StudentPersona,
        is_eligible: bool,
        assumed_reimbursement_rate: Optional[float] = None
    ) -> Tuple[float, float, List[str], List[str]]:
        """
        Legacy adapter maintaining exact signature for Phase 1 code.
        Internally delegates to calculate_dte_benefit.
        """
        rate, relief, _, notes, assumptions = cls.calculate_dte_benefit(
            persona=persona,
            is_eligible=is_eligible,
            assumed_reimbursement_rate=assumed_reimbursement_rate
        )
        return rate, relief, notes, assumptions

    @classmethod
    def evaluate_eligibility(
        cls,
        persona: StudentPersona,
        assumed_reimbursement_rate: Optional[float] = None,
        config: Optional[DTEPolicyConfig] = None
    ) -> PolicyEvaluationResult:
        """
        Runs comprehensive statutory evaluation and attaches deterministic fee relief calculations.
        Evaluates ONLY the DTE Rajarshi Chhatrapati Shahu Maharaj Scheme.
        Preserves all scalar getters while attaching granular DTE fee breakdowns.
        """
        cfg = config or cls.DEFAULT_CONFIG
        is_eligible, rule_checks, failure_reasons = cls.check_statutory_eligibility(persona, config=cfg)

        # Collect indeterminate data explanations from rule check diagnostics
        indeterminate_reasons: List[str] = []
        for rc in rule_checks:
            if not rc.is_satisfied and (
                "missing" in rc.message.lower()
                or "missing" in str(rc.observed_value).lower()
                or "invalid" in rc.message.lower()
                or "invalid" in str(rc.observed_value).lower()
                or "non-finite" in rc.message.lower()
                or "boolean" in rc.message.lower()
            ):
                indeterminate_reasons.append(f"{rc.rule_name}: {rc.observed_value}")

        rate, fee_relief, breakdown, statutory_notes, benefit_assumptions = cls.calculate_dte_benefit(
            persona=persona,
            is_eligible=is_eligible,
            config=cfg,
            assumed_reimbursement_rate=assumed_reimbursement_rate
        )

        # If explicit override was invalid, register indeterminate note
        if assumed_reimbursement_rate is not None and any("Invalid explicit override" in n for n in statutory_notes):
            indeterminate_reasons.append(f"Override Rate: Invalid explicit value ({assumed_reimbursement_rate!r})")

        route_val = ScholarshipRoute.DTE_EBC.value if is_eligible else ScholarshipRoute.INELIGIBLE.value

        return PolicyEvaluationResult(
            scheme_name=cls.SCHEME_NAME,
            is_eligible=is_eligible,
            reimbursement_percentage=rate,
            estimated_fee_relief_inr=fee_relief,
            rule_checks=rule_checks,
            failure_reasons=failure_reasons,
            statutory_notes=statutory_notes,
            benefit_assumptions=benefit_assumptions,
            tuition_fee_relief_inr=breakdown.tuition_fee_relief_inr,
            exam_fee_relief_inr=breakdown.exam_fee_relief_inr,
            tuition_reimbursement_percentage=breakdown.tuition_reimbursement_rate,
            exam_reimbursement_percentage=breakdown.exam_reimbursement_rate,
            policy_version=cfg.policy_version,
            verification_status=cfg.default_verification_status,
            indeterminate_reasons=indeterminate_reasons,
            fee_breakdown=breakdown,
            scholarship_route=route_val,
            alternate_scheme_name=None,
            routing_reason=None
        )
