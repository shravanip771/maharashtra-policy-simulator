"""
Unit tests for Simulation Analytics Module (simulation/analytics.py).

Tests:
1. Correct population and eligibility counts
2. Awareness threshold behaviour (default vs custom, continuous scoring)
3. Application attempt and completion counts (funnel progression and denominators)
4. Benefit recipient counts and estimated relief calculations
5. District and demographic breakdowns
6. Final-state breakdown
7. Missing demographic fields handling (defaulting to Unknown)
8. Empty population and zero denominators safety
9. Multi-step final-result handling without duplicate counting
10. Unavailable administrative lifecycle statuses are not fabricated
11. JSON serialization integrity
"""

import pytest
import json
from typing import List, Dict, Any

from simulation.engine import (
    SimulationEngine,
    SimulationStepOutput,
    CohortSimulationResult,
    MultiStepSimulationResult
)
from simulation.agent import StubLLMProvider
from simulation.persona_generator import SyntheticPersonaGenerator
from simulation.analytics import (
    PolicySimulationAnalytics,
    AnalyticsReport,
    compute_cohort_analytics,
    compute_multi_step_analytics,
    compute_step_outputs_analytics,
    DEFAULT_AWARENESS_THRESHOLD
)


def _create_mock_output(
    persona_id: str,
    persona_name: str,
    district: str = "Dhule",
    gender: str = "Female",
    course: str = "B.Tech Computer Engineering",
    caste_category: str = "OBC",
    institution_type: str = "Government-Aided",
    is_eligible: bool = True,
    fee_relief_inr: float = 45000.0,
    awareness_score: float = 0.65,
    attempted_application: bool = True,
    completed_application: bool = True,
    benefit_received: bool = True,
    final_simulation_state: str = "BENEFIT_RECEIVED",
    failure_reasons: List[str] = None,
    demographics_override: Dict[str, Any] = None
) -> SimulationStepOutput:
    """Helper fixture to create deterministic mock SimulationStepOutput instances."""
    if demographics_override is not None:
        demographics = demographics_override
    else:
        demographics = {
            "age": 20,
            "gender": gender,
            "district": district,
            "family_income": 250000.0,
            "caste_category": caste_category,
            "course": course,
            "institution_type": institution_type,
            "admission_mode": "CAP",
            "annual_tuition_fee": 90000.0,
            "first_generation_learner": True
        }

    return SimulationStepOutput(
        persona_id=persona_id,
        persona_name=persona_name,
        demographics_summary=demographics,
        scheme_name="Rajarshi Chhatrapati Shahu Maharaj Yojna",
        is_eligible=is_eligible,
        reimbursement_percentage=0.50 if is_eligible else 0.0,
        estimated_fee_relief_inr=fee_relief_inr if is_eligible else 0.0,
        statutory_failure_reasons=failure_reasons or ([] if is_eligible else ["Income exceeds 8L limit"]),
        statutory_notes=["Statutory check complete."],
        benefit_assumptions=["50% PoC reimbursement rate."],
        awareness_score=awareness_score,
        perceived_benefit_score=0.70,
        application_probability=0.80,
        completion_probability=0.75,
        expected_uptake_probability=0.60,
        attempted_application=attempted_application,
        completed_application=completed_application,
        benefit_received=benefit_received,
        final_simulation_state=final_simulation_state,
        inner_monologue="Simulated monologue.",
        stated_intention="I will apply.",
        perceived_barriers=["Document collection"],
        chosen_action="SUBMIT_APPLICATION",
        confidence_level="High"
    )


def _build_test_cohort(outputs: List[SimulationStepOutput], name: str = "Test-Cohort") -> CohortSimulationResult:
    """Wraps outputs into a minimal CohortSimulationResult."""
    total = len(outputs)
    eligible = sum(1 for o in outputs if o.is_eligible)
    return CohortSimulationResult(
        cohort_name=name,
        total_personas=total,
        seed=42,
        assumed_reimbursement_rate=0.50,
        eligible_count=eligible,
        ineligible_count=total - eligible,
        eligibility_rate=round(eligible / total, 4) if total > 0 else 0.0,
        total_estimated_fee_relief_inr=sum(o.estimated_fee_relief_inr for o in outputs),
        average_fee_relief_per_eligible_inr=0.0,
        average_awareness_score=0.5,
        average_perceived_benefit_score=0.5,
        average_application_probability=0.5,
        average_completion_probability=0.5,
        average_expected_uptake_probability=0.5,
        attempted_application_count=sum(1 for o in outputs if o.attempted_application),
        completed_application_count=sum(1 for o in outputs if o.completed_application),
        benefit_received_count=sum(1 for o in outputs if o.benefit_received),
        uptake_rate=0.0,
        breakdown_by_gender={},
        breakdown_by_institution_type={},
        breakdown_by_caste_category={},
        ineligibility_reasons_summary={},
        state_distribution={},
        individual_results=outputs,
        assumptions_and_limitations=["Test assumptions."]
    )


class TestPolicySimulationAnalytics:
    """Test suite verifying analytics calculations, edge cases, and integrity."""

    def test_correct_population_and_eligibility_counts(self):
        """Verifies total personas, eligible count, ineligible count, and rates."""
        outputs = [
            _create_mock_output("STU-1", "Aarav", is_eligible=True),
            _create_mock_output("STU-2", "Pooja", is_eligible=True),
            _create_mock_output("STU-3", "Rohan", is_eligible=False),
            _create_mock_output("STU-4", "Sneha", is_eligible=True),
        ]
        report = compute_step_outputs_analytics(outputs, cohort_name="Eligibility-Test")

        pop = report.population_and_eligibility
        assert pop.total_personas == 4
        assert pop.eligible_count == 3
        assert pop.ineligible_count == 1
        assert pop.eligibility_rate == 0.75
        assert pop.eligibility_percentage == 75.0
        assert pop.denominators["eligibility_rate"] == "total_personas"

    def test_awareness_threshold_behaviour(self):
        """
        Verifies that awareness classification strictly uses the threshold
        and does NOT classify every non-zero score as aware.
        """
        outputs = [
            _create_mock_output("STU-1", "Student A", awareness_score=0.10),  # Non-zero, but low
            _create_mock_output("STU-2", "Student B", awareness_score=0.49),  # Just below default
            _create_mock_output("STU-3", "Student C", awareness_score=0.50),  # Exactly at default
            _create_mock_output("STU-4", "Student D", awareness_score=0.75),  # Well above default
        ]

        # 1. Default threshold (0.50)
        report_default = compute_step_outputs_analytics(outputs, awareness_threshold=DEFAULT_AWARENESS_THRESHOLD)
        aware_def = report_default.awareness_and_application
        assert aware_def.awareness_threshold == 0.50
        assert aware_def.aware_count == 2      # STU-3 and STU-4
        assert aware_def.unaware_count == 2    # STU-1 and STU-2
        assert aware_def.awareness_rate == 0.50

        # 2. Strict custom threshold (0.70)
        report_strict = compute_step_outputs_analytics(outputs, awareness_threshold=0.70)
        aware_strict = report_strict.awareness_and_application
        assert aware_strict.awareness_threshold == 0.70
        assert aware_strict.aware_count == 1    # Only STU-4
        assert aware_strict.unaware_count == 3
        assert aware_strict.awareness_rate == 0.25

        # 3. Lenient custom threshold (0.05)
        report_lenient = compute_step_outputs_analytics(outputs, awareness_threshold=0.05)
        assert report_lenient.awareness_and_application.aware_count == 4

    def test_application_attempt_and_completion_counts(self):
        """Verifies application attempt and completion counts and distinct denominators."""
        outputs = [
            # 1: Attempted and completed
            _create_mock_output("STU-1", "A", attempted_application=True, completed_application=True, is_eligible=True),
            # 2: Attempted but dropped out (did not complete)
            _create_mock_output("STU-2", "B", attempted_application=True, completed_application=False, is_eligible=True),
            # 3: Did not attempt
            _create_mock_output("STU-3", "C", attempted_application=False, completed_application=False, is_eligible=True),
            # 4: Ineligible, did not attempt
            _create_mock_output("STU-4", "D", attempted_application=False, completed_application=False, is_eligible=False),
        ]
        report = compute_step_outputs_analytics(outputs)
        app = report.awareness_and_application

        assert app.attempted_application_count == 2
        assert app.completed_application_count == 1

        # Denominator checks
        assert app.application_attempt_rate == 0.50       # 2 attempted / 4 total
        assert app.eligible_application_attempt_rate == round(2 / 3, 4)  # 2 attempted / 3 eligible
        assert app.application_completion_rate == 0.50    # 1 completed / 2 attempted (funnel completion)
        assert app.population_completion_rate == 0.25     # 1 completed / 4 total

        # Disclaimer presence check
        assert "simulated behavioral actions" in app.disclaimer
        assert "not independently verified administrative portal logs" in app.disclaimer

    def test_benefit_recipient_and_fee_relief_calculations(self):
        """Verifies benefit recipients and estimated fee relief are counted distinctly."""
        outputs = [
            # Eligible and received benefit
            _create_mock_output("STU-1", "A", is_eligible=True, fee_relief_inr=50000.0, benefit_received=True),
            # Eligible but did NOT receive benefit (e.g. dropped out during document collection)
            _create_mock_output("STU-2", "B", is_eligible=True, fee_relief_inr=30000.0, benefit_received=False),
            # Ineligible, 0 relief, no benefit
            _create_mock_output("STU-3", "C", is_eligible=False, fee_relief_inr=0.0, benefit_received=False),
        ]
        report = compute_step_outputs_analytics(outputs)
        b = report.benefits

        assert b.benefit_received_count == 1
        assert b.eligible_benefit_recipient_count == 1
        assert b.benefit_recipient_rate == round(1 / 3, 4)
        assert b.eligible_benefit_recipient_rate == 0.50  # 1 recipient / 2 eligible

        # Total fee relief sum (whole-cohort total: 50000 + 30000)
        assert b.total_estimated_fee_relief_inr == 80000.0
        # Average per eligible (80000 / 2 = 40000)
        assert b.average_fee_relief_per_eligible_inr == 40000.0
        # Average per realized recipient persona (recipient-only relief: 50000 / 1 = 50000)
        # STU-2 is an eligible non-recipient whose 30,000 INR estimated relief is excluded from recipient average!
        assert b.average_estimated_fee_relief_per_recipient_persona_inr == 50000.0
        assert "counted separately" in b.disclaimer
        assert "average_estimated_fee_relief_per_recipient_persona_inr" in b.denominators

    def test_eligible_and_ineligible_application_attempts_separated(self):
        """
        Verifies that eligible_application_attempt_rate uses only eligible applicants in numerator.
        Ineligible application attempts must NOT inflate the eligible attempt rate.
        """
        outputs = [
            # P1: Eligible, attempted
            _create_mock_output("STU-1", "A", is_eligible=True, attempted_application=True),
            # P2: Ineligible, attempted
            _create_mock_output("STU-2", "B", is_eligible=False, attempted_application=True),
            # P3: Eligible, did NOT attempt
            _create_mock_output("STU-3", "C", is_eligible=True, attempted_application=False),
            # P4: Ineligible, did NOT attempt
            _create_mock_output("STU-4", "D", is_eligible=False, attempted_application=False),
        ]
        report = compute_step_outputs_analytics(outputs)
        app = report.awareness_and_application

        assert report.population_and_eligibility.total_personas == 4
        assert report.population_and_eligibility.eligible_count == 2
        assert app.attempted_application_count == 2          # P1 + P2
        assert app.eligible_attempted_count == 1              # Only P1
        assert app.application_attempt_rate == 0.50           # 2 attempted / 4 total
        # Correctly 1 / 2 = 0.50, NOT 2 / 2 = 1.00!
        assert app.eligible_application_attempt_rate == 0.50

    def test_eligible_and_ineligible_benefit_recipients_separated(self):
        """
        Verifies that eligible_benefit_recipient_rate uses only eligible recipients in numerator.
        Any simulated ineligible recipients must not inflate the eligible recipient rate.
        """
        outputs = [
            # P1: Eligible, benefit received
            _create_mock_output("STU-1", "A", is_eligible=True, benefit_received=True),
            # P2: Ineligible, benefit received (simulated anomaly/test case)
            _create_mock_output("STU-2", "B", is_eligible=False, benefit_received=True),
            # P3: Eligible, NO benefit
            _create_mock_output("STU-3", "C", is_eligible=True, benefit_received=False),
            # P4: Ineligible, NO benefit
            _create_mock_output("STU-4", "D", is_eligible=False, benefit_received=False),
        ]
        report = compute_step_outputs_analytics(outputs)
        b = report.benefits

        assert report.population_and_eligibility.total_personas == 4
        assert report.population_and_eligibility.eligible_count == 2
        assert b.benefit_received_count == 2                  # Total recipients (P1 + P2)
        assert b.eligible_benefit_recipient_count == 1         # Only P1
        assert b.benefit_recipient_rate == 0.50               # 2 / 4
        # Correctly 1 / 2 = 0.50, NOT 2 / 2 = 1.00!
        assert b.eligible_benefit_recipient_rate == 0.50

    def test_awareness_threshold_validation_raises_value_error(self):
        """Verifies that invalid awareness thresholds strictly raise ValueError."""
        outputs = [_create_mock_output("STU-1", "A")]

        # Reject numeric strings (strictly numeric int or float required)
        with pytest.raises(ValueError, match="between 0.0 and 1.0 inclusive"):
            compute_step_outputs_analytics(outputs, awareness_threshold="0.5")

        with pytest.raises(ValueError, match="between 0.0 and 1.0 inclusive"):
            compute_step_outputs_analytics(outputs, awareness_threshold="0")

        with pytest.raises(ValueError, match="between 0.0 and 1.0 inclusive"):
            compute_step_outputs_analytics(outputs, awareness_threshold="1.0")

        with pytest.raises(ValueError, match="between 0.0 and 1.0 inclusive"):
            compute_step_outputs_analytics(outputs, awareness_threshold="not_a_number")

        # Reject boolean values (True and False)
        with pytest.raises(ValueError, match="between 0.0 and 1.0 inclusive"):
            compute_step_outputs_analytics(outputs, awareness_threshold=True)

        with pytest.raises(ValueError, match="between 0.0 and 1.0 inclusive"):
            compute_step_outputs_analytics(outputs, awareness_threshold=False)

        # Reject None and complex/collection types
        with pytest.raises(ValueError, match="between 0.0 and 1.0 inclusive"):
            compute_step_outputs_analytics(outputs, awareness_threshold=None)

        with pytest.raises(ValueError, match="between 0.0 and 1.0 inclusive"):
            compute_step_outputs_analytics(outputs, awareness_threshold=[0.5])

        # Negative thresholds
        with pytest.raises(ValueError, match="between 0.0 and 1.0 inclusive"):
            compute_step_outputs_analytics(outputs, awareness_threshold=-0.01)

        with pytest.raises(ValueError, match="between 0.0 and 1.0 inclusive"):
            compute_step_outputs_analytics(outputs, awareness_threshold=-1.0)

        # Thresholds exceeding 1.0
        with pytest.raises(ValueError, match="between 0.0 and 1.0 inclusive"):
            compute_step_outputs_analytics(outputs, awareness_threshold=1.01)

        with pytest.raises(ValueError, match="between 0.0 and 1.0 inclusive"):
            compute_step_outputs_analytics(outputs, awareness_threshold=2.5)

        # Non-finite values: NaN and Infinity
        with pytest.raises(ValueError, match="between 0.0 and 1.0 inclusive"):
            compute_step_outputs_analytics(outputs, awareness_threshold=float("nan"))

        with pytest.raises(ValueError, match="between 0.0 and 1.0 inclusive"):
            compute_step_outputs_analytics(outputs, awareness_threshold=float("inf"))

        with pytest.raises(ValueError, match="between 0.0 and 1.0 inclusive"):
            compute_step_outputs_analytics(outputs, awareness_threshold=float("-inf"))

        # Valid integer thresholds (0 and 1) must be accepted and cast to float
        rep_int_0 = compute_step_outputs_analytics(outputs, awareness_threshold=0)
        assert rep_int_0.awareness_and_application.awareness_threshold == 0.0

        rep_int_1 = compute_step_outputs_analytics(outputs, awareness_threshold=1)
        assert rep_int_1.awareness_and_application.awareness_threshold == 1.0

        # Valid float thresholds (0.0, 0.5, 1.0) must be accepted
        rep_0 = compute_step_outputs_analytics(outputs, awareness_threshold=0.0)
        assert rep_0.awareness_and_application.awareness_threshold == 0.0

        rep_half = compute_step_outputs_analytics(outputs, awareness_threshold=0.5)
        assert rep_half.awareness_and_application.awareness_threshold == 0.5

        rep_1 = compute_step_outputs_analytics(outputs, awareness_threshold=1.0)
        assert rep_1.awareness_and_application.awareness_threshold == 1.0

    def test_recipient_only_estimated_relief_average_and_breakdowns(self):
        """
        Verifies that:
        1. Recipient-only estimated relief is used in average_estimated_fee_relief_per_recipient_persona_inr.
        2. Non-recipients' estimated relief is excluded from that average.
        3. Whole-cohort estimated relief remains unchanged (includes non-recipients).
        4. Demographic breakdowns use the exact same recipient-only formula.
        5. Zero recipients case safely yields 0.0 without division by zero.
        """
        outputs = [
            # Dhule cohort
            # P1: Eligible, recipient, 60,000 relief
            _create_mock_output("STU-1", "Aarav", district="Dhule", is_eligible=True, fee_relief_inr=60000.0, benefit_received=True),
            # P2: Eligible, recipient, 40,000 relief
            _create_mock_output("STU-2", "Pooja", district="Dhule", is_eligible=True, fee_relief_inr=40000.0, benefit_received=True),
            # P3: Eligible, NON-recipient, 50,000 relief (dropped out)
            _create_mock_output("STU-3", "Rohan", district="Dhule", is_eligible=True, fee_relief_inr=50000.0, benefit_received=False),
            # P4: Ineligible, NON-recipient, 0 relief
            _create_mock_output("STU-4", "Sneha", district="Dhule", is_eligible=False, fee_relief_inr=0.0, benefit_received=False),

            # Nashik cohort
            # P5: Eligible, recipient, 75,000 relief
            _create_mock_output("STU-5", "Kiran", district="Nashik", is_eligible=True, fee_relief_inr=75000.0, benefit_received=True),
            # P6: Eligible, NON-recipient, 25,000 relief
            _create_mock_output("STU-6", "Meera", district="Nashik", is_eligible=True, fee_relief_inr=25000.0, benefit_received=False),
        ]

        report = compute_step_outputs_analytics(outputs)
        b = report.benefits

        # Whole-cohort total relief includes ALL valid estimated relief:
        # 60k + 40k + 50k + 0 + 75k + 25k = 250,000.0
        assert b.total_estimated_fee_relief_inr == 250000.0

        # Eligible count = 5 (P1, P2, P3, P5, P6)
        # Average per eligible = 250,000 / 5 = 50,000.0
        assert b.average_fee_relief_per_eligible_inr == 50000.0

        # Recipients = 3 (P1, P2, P5)
        assert b.benefit_received_count == 3
        # Recipient-only estimated relief = 60k + 40k + 75k = 175,000.0
        # Non-recipients P3 (50k) and P6 (25k) are strictly excluded from the recipient average!
        # Average per recipient persona = 175,000 / 3 = 58,333.33 (NOT 250,000 / 3 = 83,333.33!)
        assert b.average_estimated_fee_relief_per_recipient_persona_inr == 58333.33

        # Breakdown by District: Dhule
        dhule = report.breakdowns["district"]["Dhule"]
        assert dhule["total_count"] == 4
        assert dhule["eligible_count"] == 3
        assert dhule["benefit_received_count"] == 2  # P1, P2
        # Dhule whole-group total relief includes P3: 60k + 40k + 50k = 150,000.0
        assert dhule["total_estimated_fee_relief_inr"] == 150000.0
        assert dhule["average_fee_relief_per_eligible_inr"] == 50000.0  # 150k / 3
        # Dhule recipient-only average: (60k + 40k) / 2 = 50,000.0 (NOT 150k / 2 = 75,000.0!)
        assert dhule["average_estimated_fee_relief_per_recipient_persona_inr"] == 50000.0

        # Breakdown by District: Nashik
        nashik = report.breakdowns["district"]["Nashik"]
        assert nashik["total_count"] == 2
        assert nashik["eligible_count"] == 2
        assert nashik["benefit_received_count"] == 1  # P5
        # Nashik whole-group total relief includes P6: 75k + 25k = 100,000.0
        assert nashik["total_estimated_fee_relief_inr"] == 100000.0
        assert nashik["average_fee_relief_per_eligible_inr"] == 50000.0  # 100k / 2
        # Nashik recipient-only average: 75k / 1 = 75,000.0 (NOT 100k / 1 = 100,000.0!)
        assert nashik["average_estimated_fee_relief_per_recipient_persona_inr"] == 75000.0

        # Zero recipient test: when no one receives benefits
        zero_recipients_outputs = [
            _create_mock_output("STU-10", "X", is_eligible=True, fee_relief_inr=50000.0, benefit_received=False),
        ]
        zero_rep = compute_step_outputs_analytics(zero_recipients_outputs)
        assert zero_rep.benefits.benefit_received_count == 0
        assert zero_rep.benefits.total_estimated_fee_relief_inr == 50000.0
        assert zero_rep.benefits.average_estimated_fee_relief_per_recipient_persona_inr == 0.0

    def test_numeric_input_nan_and_infinity_handling(self):
        """
        Verifies that NaN and Infinity in awareness scores and fee relief values
        are safely handled and do NOT corrupt aggregate sums or calculations.
        """
        outputs = [
            # P1: NaN awareness, NaN fee relief
            _create_mock_output("STU-1", "A", is_eligible=True, awareness_score=float("nan"), fee_relief_inr=float("nan")),
            # P2: Inf awareness, Inf fee relief
            _create_mock_output("STU-2", "B", is_eligible=True, awareness_score=float("inf"), fee_relief_inr=float("inf")),
            # P3: Valid awareness, valid fee relief
            _create_mock_output("STU-3", "C", is_eligible=True, awareness_score=0.75, fee_relief_inr=50000.0),
            # P4: Negative fee relief (corrupt input)
            _create_mock_output("STU-4", "D", is_eligible=False, awareness_score=0.60, fee_relief_inr=-9999.0),
        ]

        # Must execute cleanly without exception
        report = compute_step_outputs_analytics(outputs, awareness_threshold=0.50)

        # Only P3 and P4 have finite scores >= 0.50; P1 and P2 (NaN/Inf) are safely treated as unaware
        assert report.awareness_and_application.aware_count == 2
        assert report.awareness_and_application.unaware_count == 2

        # Fee relief must only sum the valid finite positive amount (50,000.0); NaN, Inf, and negative excluded
        assert report.benefits.total_estimated_fee_relief_inr == 50000.0

        # Methodological notes explicitly document the handling
        assert any("non-finite awareness_score" in n for n in report.methodological_notes)
        assert any("non-finite estimated_fee_relief_inr" in n for n in report.methodological_notes)

    def test_json_serialization_disallows_nan_and_infinity(self):
        """
        Verifies that report.to_json() strictly produces valid JSON without NaN or Infinity,
        even when inputs contained non-finite values.
        """
        outputs = [
            _create_mock_output("STU-1", "A", awareness_score=float("nan"), fee_relief_inr=float("nan")),
            _create_mock_output("STU-2", "B", awareness_score=0.8, fee_relief_inr=40000.0),
        ]
        report = compute_step_outputs_analytics(outputs)

        # Serializing to JSON must not raise and must enforce allow_nan=False
        json_str = report.to_json(indent=2)
        assert "NaN" not in json_str
        assert "Infinity" not in json_str
        assert "-Infinity" not in json_str

        # Must parse back cleanly
        parsed = json.loads(json_str)
        assert parsed["benefits"]["total_estimated_fee_relief_inr"] == 40000.0

    def test_district_and_demographic_breakdowns(self):
        """Verifies breakdowns by district, gender, course, caste, and institution type."""
        outputs = [
            _create_mock_output("STU-1", "A", district="Dhule", gender="Female", course="B.Tech", caste_category="OBC", institution_type="Government-Aided", is_eligible=True, fee_relief_inr=40000.0),
            _create_mock_output("STU-2", "B", district="Dhule", gender="Male", course="B.Tech", caste_category="General-EBC", institution_type="Private-Unaided", is_eligible=True, fee_relief_inr=60000.0),
            _create_mock_output("STU-3", "C", district="Mumbai City", gender="Female", course="B.Pharm", caste_category="SC", institution_type="Government", is_eligible=False, fee_relief_inr=0.0),
        ]
        report = compute_step_outputs_analytics(outputs)
        b_dist = report.breakdowns["district"]
        b_gender = report.breakdowns["gender"]
        b_course = report.breakdowns["course"]
        b_caste = report.breakdowns["caste_category"]
        b_inst = report.breakdowns["institution_type"]

        # District check
        assert set(b_dist.keys()) == {"Dhule", "Mumbai City"}
        assert b_dist["Dhule"]["total_count"] == 2
        assert b_dist["Dhule"]["eligible_count"] == 2
        assert b_dist["Dhule"]["total_estimated_fee_relief_inr"] == 100000.0
        assert b_dist["Mumbai City"]["total_count"] == 1
        assert b_dist["Mumbai City"]["eligible_count"] == 0

        # Gender check
        assert b_gender["Female"]["total_count"] == 2
        assert b_gender["Male"]["total_count"] == 1

        # Course check
        assert b_course["B.Tech"]["total_count"] == 2
        assert b_course["B.Pharm"]["total_count"] == 1

        # Caste check
        assert b_caste["OBC"]["total_count"] == 1
        assert b_caste["General-EBC"]["total_count"] == 1
        assert b_caste["SC"]["total_count"] == 1

        # Institution type check
        assert b_inst["Government-Aided"]["total_count"] == 1
        assert b_inst["Private-Unaided"]["total_count"] == 1
        assert b_inst["Government"]["total_count"] == 1

        # Check total across any breakdown sums to total cohort
        assert sum(v["total_count"] for v in b_dist.values()) == 3
        assert sum(v["total_count"] for v in b_gender.values()) == 3

    def test_final_simulation_state_breakdown(self):
        """Verifies breakdown by final_simulation_state."""
        outputs = [
            _create_mock_output("STU-1", "A", final_simulation_state="BENEFIT_RECEIVED"),
            _create_mock_output("STU-2", "B", final_simulation_state="APPLIED"),
            _create_mock_output("STU-3", "C", final_simulation_state="REJECTED"),
            _create_mock_output("STU-4", "D", final_simulation_state="BENEFIT_RECEIVED"),
        ]
        report = compute_step_outputs_analytics(outputs)
        b_state = report.breakdowns["final_simulation_state"]

        assert set(b_state.keys()) == {"BENEFIT_RECEIVED", "APPLIED", "REJECTED"}
        assert b_state["BENEFIT_RECEIVED"]["total_count"] == 2
        assert b_state["APPLIED"]["total_count"] == 1
        assert b_state["REJECTED"]["total_count"] == 1

    def test_missing_demographic_fields_handling(self):
        """Verifies robust handling when demographics_summary is empty or missing fields."""
        outputs = [
            _create_mock_output("STU-1", "A", demographics_override={}),
            _create_mock_output("STU-2", "B", demographics_override={"district": "Kolhapur", "gender": None}),
        ]
        report = compute_step_outputs_analytics(outputs)
        b_dist = report.breakdowns["district"]
        b_gender = report.breakdowns["gender"]

        # Missing district defaults to Unknown
        assert "Unknown" in b_dist
        assert b_dist["Unknown"]["total_count"] == 1
        assert b_dist["Kolhapur"]["total_count"] == 1

        # Missing or None gender defaults to Unknown
        assert "Unknown" in b_gender
        assert b_gender["Unknown"]["total_count"] == 2

    def test_empty_population_and_zero_denominators(self):
        """Verifies zero division safety when population is empty."""
        report = compute_step_outputs_analytics([], cohort_name="Empty-Cohort")

        assert report.total_personas == 0
        assert report.population_and_eligibility.eligible_count == 0
        assert report.population_and_eligibility.eligibility_rate == 0.0
        assert report.population_and_eligibility.eligibility_percentage == 0.0

        assert report.awareness_and_application.aware_count == 0
        assert report.awareness_and_application.awareness_rate == 0.0
        assert report.awareness_and_application.application_attempt_rate == 0.0
        assert report.awareness_and_application.application_completion_rate == 0.0

        assert report.benefits.benefit_received_count == 0
        assert report.benefits.benefit_recipient_rate == 0.0
        assert report.benefits.total_estimated_fee_relief_inr == 0.0
        assert report.benefits.average_fee_relief_per_eligible_inr == 0.0
        assert report.benefits.average_estimated_fee_relief_per_recipient_persona_inr == 0.0

        for key, bd in report.breakdowns.items():
            assert bd == {}

    def test_multi_step_final_result_handling_without_duplicate_counting(self):
        """
        Verifies that analyzing a multi-step simulation uses final_cohort_result
        and counts each persona exactly once, avoiding multi-counting across steps.
        """
        # 3 personas simulated over 2 steps = 6 step outputs total
        step1_outputs = [
            _create_mock_output("STU-1", "Aarav", awareness_score=0.3, attempted_application=False, benefit_received=False),
            _create_mock_output("STU-2", "Pooja", awareness_score=0.4, attempted_application=False, benefit_received=False),
            _create_mock_output("STU-3", "Rohan", awareness_score=0.2, attempted_application=False, benefit_received=False),
        ]
        step2_outputs = [
            _create_mock_output("STU-1", "Aarav", awareness_score=0.7, attempted_application=True, completed_application=True, benefit_received=True),
            _create_mock_output("STU-2", "Pooja", awareness_score=0.6, attempted_application=True, completed_application=False, benefit_received=False),
            _create_mock_output("STU-3", "Rohan", awareness_score=0.3, attempted_application=False, completed_application=False, benefit_received=False),
        ]

        cohort1 = _build_test_cohort(step1_outputs, name="MultiStep-Step1")
        cohort2 = _build_test_cohort(step2_outputs, name="MultiStep-Step2")

        multi_step = MultiStepSimulationResult(
            cohort_name="MultiStep-Simulation",
            total_personas=3,
            total_steps=2,
            seed=42,
            assumed_reimbursement_rate=0.50,
            network_summary={},
            interactions_by_step={},
            step_cohort_results=[cohort1, cohort2],
            final_cohort_result=cohort2,
            state_evolution_summary={},
            assumptions_and_limitations=["Multi-step test."]
        )

        report = compute_multi_step_analytics(multi_step)

        # Must report exactly 3 personas, NOT 6!
        assert report.total_personas == 3
        # In step 2 (final), STU-1 and STU-2 are aware (0.7, 0.6 >= 0.5)
        assert report.awareness_and_application.aware_count == 2
        # STU-1 received benefit
        assert report.benefits.benefit_received_count == 1
        # Notes confirm multi-step deduplication
        assert any("Exactly 3 unique personas analyzed without multi-counting" in n for n in report.methodological_notes)

    def test_unavailable_administrative_lifecycle_statuses_not_fabricated(self):
        """
        Verifies that administrative lifecycle statuses are explicitly reported
        as UNAVAILABLE rather than fabricated or inferred from final_simulation_state.
        """
        outputs = [
            _create_mock_output("STU-1", "A", final_simulation_state="APPLIED"),
            _create_mock_output("STU-2", "B", final_simulation_state="REJECTED"),
        ]
        report = compute_step_outputs_analytics(outputs)
        admin = report.administrative_lifecycle

        assert admin.status == "UNAVAILABLE"
        assert admin.is_available is False
        assert "must not be inferred from behavioral simulation states" in admin.message
        assert "submitted_count" in admin.unavailable_metrics
        assert "under_verification_count" in admin.unavailable_metrics
        assert "approved_count" in admin.unavailable_metrics
        assert "administratively_rejected_count" in admin.unavailable_metrics

    def test_cohort_simulation_result_convenience_function(self):
        """Verifies compute_cohort_analytics wraps CohortSimulationResult smoothly."""
        outputs = [
            _create_mock_output("STU-1", "A"),
            _create_mock_output("STU-2", "B"),
        ]
        cohort = _build_test_cohort(outputs, name="Dhule-10-Persona")
        report = compute_cohort_analytics(cohort)

        assert isinstance(report, AnalyticsReport)
        assert report.cohort_name == "Dhule-10-Persona"
        assert report.total_personas == 2

    def test_json_serialization_integrity(self):
        """Verifies that the report serializes to valid, well-formed JSON."""
        outputs = [
            _create_mock_output("STU-1", "A", district="Dhule", is_eligible=True, fee_relief_inr=50000.0),
            _create_mock_output("STU-2", "B", district="Dhule", is_eligible=False, fee_relief_inr=0.0),
        ]
        report = compute_step_outputs_analytics(outputs, cohort_name="JSON-Serialization-Cohort")

        # Dictionary conversion
        d = report.to_dict()
        assert isinstance(d, dict)
        assert d["cohort_name"] == "JSON-Serialization-Cohort"
        assert d["total_personas"] == 2
        assert "population_and_eligibility" in d
        assert "breakdowns" in d

        # JSON string serialization & deserialization
        raw_json = report.to_json(indent=2)
        assert isinstance(raw_json, str)
        parsed = json.loads(raw_json)
        assert parsed["total_personas"] == 2
        assert parsed["administrative_lifecycle"]["status"] == "UNAVAILABLE"
        assert parsed["breakdowns"]["district"]["Dhule"]["total_count"] == 2

    def test_live_simulation_to_analytics_integration(self):
        """
        Integration test verifying end-to-end integration between SimulationEngine.run_cohort()
        and PolicySimulationAnalytics.analyze_cohort() using a real generated student cohort.

        Verifies:
        1. CohortSimulationResult from live SimulationEngine reconciles cleanly with AnalyticsReport.
        2. Eligibility, attempted application, completed application, and benefit received counts match exactly.
        3. Total estimated fee relief matches and is properly rounded.
        4. Runs in deterministic, offline mode with StubLLMProvider (zero network calls).
        """
        seed = 101
        gen = SyntheticPersonaGenerator.for_district("Dhule", seed=seed)
        cohort = gen.generate_cohort(count=10, id_prefix="DHULE-TEST", seed=seed)
        assert len(cohort) == 10

        sim_engine = SimulationEngine(llm_provider=StubLLMProvider())
        sim_result = sim_engine.run_cohort(
            personas=cohort,
            cohort_name="Live-Sim-Reconciliation",
            seed=seed
        )
        assert isinstance(sim_result, CohortSimulationResult)
        assert sim_result.total_personas == 10

        # Pass live simulation result into analytics engine
        report = PolicySimulationAnalytics.analyze_cohort(sim_result)
        assert isinstance(report, AnalyticsReport)

        # 1. Reconcile population totals
        assert report.total_personas == sim_result.total_personas == 10
        assert report.population_and_eligibility.eligible_count == sim_result.eligible_count
        assert report.population_and_eligibility.ineligible_count == sim_result.ineligible_count
        assert report.population_and_eligibility.eligibility_rate == sim_result.eligibility_rate

        # 2. Reconcile funnel progression counts
        assert report.awareness_and_application.attempted_application_count == sim_result.attempted_application_count
        assert report.awareness_and_application.completed_application_count == sim_result.completed_application_count

        # 3. Reconcile benefit counts and estimated relief
        assert report.benefits.benefit_received_count == sim_result.benefit_received_count
        assert report.benefits.total_estimated_fee_relief_inr == round(sim_result.total_estimated_fee_relief_inr, 2)
        assert report.benefits.average_fee_relief_per_eligible_inr == round(sim_result.average_fee_relief_per_eligible_inr, 2)

        # 4. Reconcile demographic breakdowns
        assert "Dhule" in report.breakdowns["district"]
        assert report.breakdowns["district"]["Dhule"]["total_count"] == 10
        assert report.breakdowns["district"]["Dhule"]["eligible_count"] == sim_result.eligible_count

        # 5. Administrative lifecycle is explicitly unavailable
        assert report.administrative_lifecycle.status == "UNAVAILABLE"
        assert report.administrative_lifecycle.is_available is False
