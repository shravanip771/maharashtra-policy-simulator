from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from simulation.persona import StudentPersona, InstitutionType, AdmissionMode

@dataclass
class RuleCheckResult:
    rule_name: str
    is_satisfied: bool
    observed_value: Any
    threshold_or_condition: str
    message: str

@dataclass
class PolicyEvaluationResult:
    scheme_name: str
    is_eligible: bool
    reimbursement_percentage: float   # Configured / estimated benefit percentage
    estimated_fee_relief_inr: float   # Estimated annual fee relief amount
    rule_checks: List[RuleCheckResult] = field(default_factory=list)
    failure_reasons: List[str] = field(default_factory=list)
    statutory_notes: List[str] = field(default_factory=list)
    benefit_assumptions: List[str] = field(default_factory=list)

class RajarshiShahuPolicyEngine:
    """
    Deterministic rule engine for Rajarshi Chhatrapati Shahu Maharaj
    Shikshan Shulk Shishyavrutti Yojna (EBC Scholarship Scheme - Maharashtra).

    Separates statutory eligibility criteria from configurable PoC benefit estimates.
    """
    SCHEME_NAME: str = "Rajarshi Chhatrapati Shahu Maharaj Shikshan Shulk Shishyavrutti Yojna"
    MAX_INCOME_LIMIT: float = 800000.0  # INR 8,00,000 per annum
    MAX_FAMILY_BENEFICIARIES: int = 2   # Maximum 2 children per family
    MIN_ATTENDANCE_PERCENT: float = 75.0 # Standard statutory minimum attendance
    MAX_PERMISSIBLE_GAP_YEARS: int = 2   # Permissible education gap years

    # Baseline PoC assumption for standard demonstration
    # Note: Real-world government rules vary by department, course, institution, income, and gender.
    DEFAULT_POC_ASSUMED_REIMBURSEMENT_RATE: float = 0.50

    @classmethod
    def check_statutory_eligibility(cls, persona: StudentPersona) -> Tuple[bool, List[RuleCheckResult], List[str]]:
        """
        Evaluates purely statutory eligibility criteria from official scheme rules.
        Does not perform variable fee or subsidy calculations.
        """
        rule_checks: List[RuleCheckResult] = []
        failure_reasons: List[str] = []

        # 1. Domicile Check
        is_domicile = persona.is_maharashtra_domicile
        rule_checks.append(RuleCheckResult(
            rule_name="Maharashtra Domicile",
            is_satisfied=is_domicile,
            observed_value=persona.is_maharashtra_domicile,
            threshold_or_condition="Must be true",
            message="Applicant must possess valid Maharashtra domicile."
        ))
        if not is_domicile:
            failure_reasons.append("Applicant is not a domicile of Maharashtra.")

        # 2. Annual Family Income Cap
        is_income_eligible = persona.family_income <= cls.MAX_INCOME_LIMIT
        rule_checks.append(RuleCheckResult(
            rule_name="Family Income Cap",
            is_satisfied=is_income_eligible,
            observed_value=f"INR {persona.family_income:,.2f}",
            threshold_or_condition=f"<= INR {cls.MAX_INCOME_LIMIT:,.2f}",
            message=f"Annual family income must not exceed INR {cls.MAX_INCOME_LIMIT:,.2f}."
        ))
        if not is_income_eligible:
            failure_reasons.append(
                f"Annual family income (INR {persona.family_income:,.2f}) exceeds the statutory limit of INR {cls.MAX_INCOME_LIMIT:,.2f}."
            )

        # 3. Admission Mode (CAP for professional courses)
        if persona.is_professional_course:
            is_cap_admitted = (persona.admission_mode == AdmissionMode.CAP)
            rule_checks.append(RuleCheckResult(
                rule_name="CAP Admission Compliance",
                is_satisfied=is_cap_admitted,
                observed_value=persona.admission_mode.value,
                threshold_or_condition="CAP (Centralized Admission Process)",
                message="For professional/technical courses, admission must be through CAP merit rounds."
            ))
            if not is_cap_admitted:
                failure_reasons.append(
                    f"Admission mode is '{persona.admission_mode.value}'; scheme requires CAP admission for professional courses."
                )
        else:
            rule_checks.append(RuleCheckResult(
                rule_name="CAP Admission Compliance",
                is_satisfied=True,
                observed_value=persona.admission_mode.value,
                threshold_or_condition="N/A (Non-professional course)",
                message="Non-professional general merit admission is acceptable."
            ))

        # 4. Institution Eligibility
        is_institution_eligible = persona.institution_type in [
            InstitutionType.GOVERNMENT,
            InstitutionType.GOVERNMENT_AIDED,
            InstitutionType.PRIVATE_UNAIDED
        ]
        rule_checks.append(RuleCheckResult(
            rule_name="Institution Eligibility",
            is_satisfied=is_institution_eligible,
            observed_value=persona.institution_type.value,
            threshold_or_condition="Government, Govt-Aided, or Recognized Private-Unaided",
            message="Institution must be state-approved and participating in MahaDBT."
        ))
        if not is_institution_eligible:
            failure_reasons.append(
                f"Institution type '{persona.institution_type.value}' is ineligible for state EBC fee reimbursement."
            )

        # 5. Family Beneficiaries Cap
        is_beneficiary_cap_satisfied = persona.family_beneficiaries_count < cls.MAX_FAMILY_BENEFICIARIES
        rule_checks.append(RuleCheckResult(
            rule_name="Family Beneficiary Cap",
            is_satisfied=is_beneficiary_cap_satisfied,
            observed_value=persona.family_beneficiaries_count,
            threshold_or_condition=f"< {cls.MAX_FAMILY_BENEFICIARIES} existing beneficiaries",
            message=f"Only maximum {cls.MAX_FAMILY_BENEFICIARIES} children from the same family can claim the benefit."
        ))
        if not is_beneficiary_cap_satisfied:
            failure_reasons.append(
                f"Family already has {persona.family_beneficiaries_count} beneficiaries (maximum limit is {cls.MAX_FAMILY_BENEFICIARIES})."
            )

        # 6. Concurrent Scholarship Prohibition
        no_other_scholarship = not persona.has_other_scholarship
        rule_checks.append(RuleCheckResult(
            rule_name="No Concurrent Scholarship",
            is_satisfied=no_other_scholarship,
            observed_value=f"Has other: {persona.has_other_scholarship}",
            threshold_or_condition="Must not hold concurrent government scholarship",
            message="Students cannot claim dual state/central scholarships for the same course."
        ))
        if not no_other_scholarship:
            failure_reasons.append("Applicant is already receiving another government scholarship.")

        # 7. Academic Progress and Gap Years
        is_academic_progress_ok = persona.previous_year_passed and (persona.academic_gap_years <= cls.MAX_PERMISSIBLE_GAP_YEARS)
        rule_checks.append(RuleCheckResult(
            rule_name="Academic Progress & Gap",
            is_satisfied=is_academic_progress_ok,
            observed_value=f"Passed: {persona.previous_year_passed}, Gap: {persona.academic_gap_years} yrs",
            threshold_or_condition=f"Passed previous exam and Gap <= {cls.MAX_PERMISSIBLE_GAP_YEARS} yrs",
            message="Applicant must have passed the previous year with permissible gap."
        ))
        if not is_academic_progress_ok:
            if not persona.previous_year_passed:
                failure_reasons.append("Applicant did not pass the previous academic year/qualifying examination.")
            if persona.academic_gap_years > cls.MAX_PERMISSIBLE_GAP_YEARS:
                failure_reasons.append(f"Academic gap ({persona.academic_gap_years} years) exceeds maximum allowed ({cls.MAX_PERMISSIBLE_GAP_YEARS} years).")

        # 8. Minimum Attendance Check
        is_attendance_ok = persona.attendance_percentage >= cls.MIN_ATTENDANCE_PERCENT
        rule_checks.append(RuleCheckResult(
            rule_name="Minimum Attendance Requirement",
            is_satisfied=is_attendance_ok,
            observed_value=f"{persona.attendance_percentage:.1f}%",
            threshold_or_condition=f">= {cls.MIN_ATTENDANCE_PERCENT:.1f}%",
            message=f"Mandatory minimum attendance is {cls.MIN_ATTENDANCE_PERCENT:.1f}%."
        ))
        if not is_attendance_ok:
            failure_reasons.append(f"Attendance ({persona.attendance_percentage:.1f}%) is below statutory requirement ({cls.MIN_ATTENDANCE_PERCENT:.1f}%).")

        is_eligible = (len(failure_reasons) == 0)
        return is_eligible, rule_checks, failure_reasons

    @classmethod
    def calculate_poc_benefit_estimate(
        cls,
        persona: StudentPersona,
        is_eligible: bool,
        assumed_reimbursement_rate: Optional[float] = None
    ) -> Tuple[float, float, List[str], List[str]]:
        """
        Calculates estimated fee relief based on explicit, configurable PoC assumptions.
        Clearly labels that actual government benefits vary by department, course,
        institution type, income slab, and gender (with applicable female benefits potentially reaching 100%).
        """
        statutory_notes: List[str] = []
        benefit_assumptions: List[str] = []

        if not is_eligible:
            statutory_notes.append("Ineligible for fee reimbursement based on statutory criteria.")
            return 0.0, 0.0, statutory_notes, benefit_assumptions

        rate = assumed_reimbursement_rate if assumed_reimbursement_rate is not None else cls.DEFAULT_POC_ASSUMED_REIMBURSEMENT_RATE
        fee_relief_inr = persona.annual_tuition_fee * rate

        statutory_notes.append(
            f"Statutorily eligible for fee concession under EBC scheme. Estimated relief: INR {fee_relief_inr:,.2f} of INR {persona.annual_tuition_fee:,.2f}."
        )

        benefit_assumptions.append(
            f"PoC Assumption: Applied baseline reimbursement rate of {rate * 100:.0f}%. "
            f"Note: Official Maharashtra government rules vary by department (DTE/DHE/DMER), course tier, "
            f"institution type, income bracket, and gender (with applicable female benefits potentially reaching 100%)."
        )

        return rate, fee_relief_inr, statutory_notes, benefit_assumptions

    @classmethod
    def evaluate_eligibility(
        cls,
        persona: StudentPersona,
        assumed_reimbursement_rate: Optional[float] = None
    ) -> PolicyEvaluationResult:
        """
        Runs statutory evaluation and attaches configurable PoC fee relief estimates.
        """
        is_eligible, rule_checks, failure_reasons = cls.check_statutory_eligibility(persona)

        rate, fee_relief, statutory_notes, benefit_assumptions = cls.calculate_poc_benefit_estimate(
            persona=persona,
            is_eligible=is_eligible,
            assumed_reimbursement_rate=assumed_reimbursement_rate
        )

        return PolicyEvaluationResult(
            scheme_name=cls.SCHEME_NAME,
            is_eligible=is_eligible,
            reimbursement_percentage=rate,
            estimated_fee_relief_inr=fee_relief,
            rule_checks=rule_checks,
            failure_reasons=failure_reasons,
            statutory_notes=statutory_notes,
            benefit_assumptions=benefit_assumptions
        )
