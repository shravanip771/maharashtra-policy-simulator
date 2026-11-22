"""
Analytics Module for Maharashtra Policy Simulator.

This module provides reusable, statistically transparent analytics for policy simulations.
Consumes structured simulation outputs (CohortSimulationResult, MultiStepSimulationResult,
or SimulationStepOutput collections) and produces comprehensive metrics, rates with
explicitly defined denominators, demographic breakdowns, and administrative caveats.

Core Epistemic & Methodological Principles:
1. Strict Separation of Simulation Flags vs. Administrative Statuses:
   - Behavioral flags (attempted_application, completed_application) represent simulated
     agent decisions, not verified government portal logs.
   - Administrative lifecycle statuses (e.g., SUBMITTED, UNDER_VERIFICATION, APPROVED,
     REJECTED, SENT_BACK) are explicitly cataloged as UNAVAILABLE because they are not
     exposed by the SimulationStepOutput schema. They must NEVER be inferred from
     final_simulation_state.
2. Explicit Denominators:
   - Every rate and percentage declares its exact mathematical denominator to prevent
     ambiguity between total population, eligible population, and applicant cohorts.
3. Multi-Step Deduplication:
   - When evaluating multi-step simulation outputs, only the final realized outcome of
     each individual persona (from final_cohort_result) is counted to avoid multi-counting.
4. Configurable Awareness Threshold:
   - Baseline awareness scores are continuous floats (0.0 to 1.0). The classification of
     a persona as "aware" requires exceeding a documented, configurable threshold
     (default: 0.5), rather than treating any non-zero score as aware.
5. Zero-Division Safety:
   - Gracefully handles empty populations, zero denominators, missing demographic dictionaries,
     and unmapped categorical values.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Union
import json
import math

from simulation.engine import CohortSimulationResult, MultiStepSimulationResult, SimulationStepOutput


# Standard default threshold for continuous awareness scores (0.0 to 1.0)
DEFAULT_AWARENESS_THRESHOLD: float = 0.5


def validate_awareness_threshold(threshold: Any) -> float:
    """
    Validates that awareness_threshold is strictly a finite numeric value (int or float, excluding bool)
    between 0.0 and 1.0 inclusive.
    Raises ValueError with an informative message if validation fails.
    """
    if threshold is None or isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
        raise ValueError(
            f"Invalid awareness_threshold: {threshold!r}. "
            "Threshold must be a strictly numeric int or float (excluding bool) between 0.0 and 1.0 inclusive."
        )

    val = float(threshold)
    if not math.isfinite(val) or val < 0.0 or val > 1.0:
        raise ValueError(
            f"Invalid awareness_threshold: {threshold!r}. "
            "Threshold must be a finite numeric value between 0.0 and 1.0 inclusive."
        )
    return val


@dataclass
class PopulationEligibilityMetrics:
    """Core population volume and statutory eligibility metrics."""
    total_personas: int
    eligible_count: int
    ineligible_count: int
    eligibility_rate: float            # eligible_count / total_personas
    eligibility_percentage: float      # eligibility_rate * 100
    denominators: Dict[str, str] = field(default_factory=lambda: {
        "eligibility_rate": "total_personas",
        "eligibility_percentage": "total_personas"
    })


@dataclass
class AwarenessApplicationMetrics:
    """Awareness levels and simulated application funnel progression."""
    awareness_threshold: float
    aware_count: int
    unaware_count: int
    awareness_rate: float                     # aware_count / total_personas
    awareness_percentage: float
    attempted_application_count: int
    eligible_attempted_count: int             # Count of personas where is_eligible AND attempted_application
    application_attempt_rate: float           # attempted_application_count / total_personas
    eligible_application_attempt_rate: float  # eligible_attempted_count / eligible_count (if eligible > 0)
    completed_application_count: int
    application_completion_rate: float        # completed_application_count / attempted_application_count (funnel completion)
    population_completion_rate: float         # completed_application_count / total_personas
    disclaimer: str = (
        "attempted_application and completed_application are simulated behavioral actions "
        "derived from persona decision rules, not independently verified administrative portal logs."
    )
    denominators: Dict[str, str] = field(default_factory=lambda: {
        "awareness_rate": "total_personas",
        "application_attempt_rate": "total_personas",
        "eligible_application_attempt_rate": "eligible_count",
        "application_completion_rate": "attempted_application_count (funnel completion)",
        "population_completion_rate": "total_personas"
    })


@dataclass
class BenefitMetrics:
    """Realized benefit recipients and estimated financial fee relief."""
    benefit_received_count: int                  # Total count of personas with benefit_received=True
    eligible_benefit_recipient_count: int         # Count of personas where is_eligible AND benefit_received
    benefit_recipient_rate: float                # benefit_received_count / total_personas
    eligible_benefit_recipient_rate: float       # eligible_benefit_recipient_count / eligible_count
    total_estimated_fee_relief_inr: float        # Whole-cohort total estimated fee relief
    average_fee_relief_per_eligible_inr: float   # total_relief / eligible_count
    average_estimated_fee_relief_per_recipient_persona_inr: float  # recipient_estimated_relief / benefit_received_count
    disclaimer: str = (
        "benefit_received represents simulated realization of scheme benefits. "
        "Estimated fee relief reflects potential statutory entitlement and is counted separately from "
        "actual administrative disbursement. average_estimated_fee_relief_per_recipient_persona_inr is an "
        "estimated entitlement metric calculated strictly across realized recipient personas (using recipient-only "
        "estimated relief), not an independently verified actual treasury disbursement order."
    )
    denominators: Dict[str, str] = field(default_factory=lambda: {
        "benefit_recipient_rate": "total_personas",
        "eligible_benefit_recipient_rate": "eligible_count",
        "average_fee_relief_per_eligible_inr": "eligible_count",
        "average_estimated_fee_relief_per_recipient_persona_inr": "benefit_received_count"
    })


@dataclass
class AdministrativeLifecycleStatus:
    """Explicit disclosure that administrative application statuses are unavailable."""
    status: str = "UNAVAILABLE"
    is_available: bool = False
    message: str = (
        "Administrative lifecycle statuses (such as SUBMITTED, UNDER_VERIFICATION, "
        "APPROVED, REJECTED, SENT_BACK) are not exposed by the SimulationStepOutput schema. "
        "These statuses represent administrative records in the application lifecycle service "
        "and must not be inferred from behavioral simulation states (final_simulation_state)."
    )
    unavailable_metrics: List[str] = field(default_factory=lambda: [
        "submitted_count",
        "under_verification_count",
        "approved_count",
        "administratively_rejected_count",
        "sent_back_count"
    ])


@dataclass
class GroupBreakdownSummary:
    """Aggregated metrics for a demographic or categorical subset."""
    total_count: int
    eligible_count: int
    ineligible_count: int
    eligibility_rate: float
    aware_count: int
    awareness_rate: float
    attempted_application_count: int
    eligible_attempted_count: int
    application_attempt_rate: float
    eligible_application_attempt_rate: float
    completed_application_count: int
    application_completion_rate: float
    benefit_received_count: int
    eligible_benefit_recipient_count: int
    benefit_recipient_rate: float
    eligible_benefit_recipient_rate: float
    total_estimated_fee_relief_inr: float
    average_fee_relief_per_eligible_inr: float
    average_estimated_fee_relief_per_recipient_persona_inr: float


@dataclass
class AnalyticsReport:
    """Complete, structured, JSON-serializable policy simulation analytics report."""
    cohort_name: str
    total_personas: int
    awareness_threshold: float
    population_and_eligibility: PopulationEligibilityMetrics
    awareness_and_application: AwarenessApplicationMetrics
    benefits: BenefitMetrics
    administrative_lifecycle: AdministrativeLifecycleStatus
    breakdowns: Dict[str, Dict[str, Dict[str, Any]]]
    ineligibility_reasons: Dict[str, int]
    methodological_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Converts the analytics report into a clean, nested dictionary."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Serializes the analytics report to a structured JSON string, disallowing NaN/Infinity."""
        return json.dumps(self.to_dict(), indent=indent, default=str, allow_nan=False)


class PolicySimulationAnalytics:
    """
    Reusable analytics engine for the Maharashtra Policy Simulator.
    Processes SimulationStepOutput collections, CohortSimulationResult,
    and MultiStepSimulationResult objects to generate comprehensive,
    statistically transparent metrics and breakdowns.
    """

    DEFAULT_AWARENESS_THRESHOLD: float = DEFAULT_AWARENESS_THRESHOLD

    @classmethod
    def analyze_cohort(
        cls,
        cohort: CohortSimulationResult,
        awareness_threshold: float = DEFAULT_AWARENESS_THRESHOLD
    ) -> AnalyticsReport:
        """
        Analyzes a single CohortSimulationResult.
        """
        return cls.analyze_step_outputs(
            outputs=cohort.individual_results,
            cohort_name=cohort.cohort_name,
            awareness_threshold=awareness_threshold,
            additional_notes=cohort.assumptions_and_limitations
        )

    @classmethod
    def analyze_multi_step(
        cls,
        multi_step_result: MultiStepSimulationResult,
        awareness_threshold: float = DEFAULT_AWARENESS_THRESHOLD
    ) -> AnalyticsReport:
        """
        Analyzes the final realized state of a MultiStepSimulationResult.
        Guarantees that each persona is counted exactly once by consuming
        multi_step_result.final_cohort_result.
        """
        final_cohort = multi_step_result.final_cohort_result
        notes = list(multi_step_result.assumptions_and_limitations or [])
        notes.append(
            f"Multi-step simulation analytics consumed final cohort outputs across {multi_step_result.total_steps} "
            f"simulation cycles. Exactly {len(final_cohort.individual_results)} unique personas analyzed without multi-counting."
        )

        return cls.analyze_step_outputs(
            outputs=final_cohort.individual_results,
            cohort_name=f"{multi_step_result.cohort_name}-FinalState",
            awareness_threshold=awareness_threshold,
            additional_notes=notes
        )

    @classmethod
    def analyze_step_outputs(
        cls,
        outputs: List[SimulationStepOutput],
        cohort_name: str = "Policy-Simulation-Cohort",
        awareness_threshold: float = DEFAULT_AWARENESS_THRESHOLD,
        additional_notes: Optional[List[str]] = None
    ) -> AnalyticsReport:
        """
        Core computation engine generating AnalyticsReport from a list of SimulationStepOutputs.
        """
        # Validate awareness threshold input (must be finite float between 0.0 and 1.0)
        awareness_threshold = validate_awareness_threshold(awareness_threshold)

        total = len(outputs)
        notes = list(additional_notes or [])

        # ----------------------------------------------------------------------
        # 1. Population & Statutory Eligibility
        # ----------------------------------------------------------------------
        eligible_count = sum(1 for r in outputs if r.is_eligible)
        ineligible_count = total - eligible_count
        eligibility_rate = round(eligible_count / total, 4) if total > 0 else 0.0
        eligibility_pct = round(eligibility_rate * 100.0, 2)

        pop_elig_metrics = PopulationEligibilityMetrics(
            total_personas=total,
            eligible_count=eligible_count,
            ineligible_count=ineligible_count,
            eligibility_rate=eligibility_rate,
            eligibility_percentage=eligibility_pct
        )

        # ----------------------------------------------------------------------
        # 2. Awareness & Application Funnel (Numeric Validation & Sanitization)
        # ----------------------------------------------------------------------
        invalid_awareness_count = 0
        aware_count = 0
        eligible_attempted_count = 0

        for r in outputs:
            # Validate awareness score
            raw_awareness = getattr(r, "awareness_score", None)
            if raw_awareness is not None and not isinstance(raw_awareness, bool):
                try:
                    f_awareness = float(raw_awareness)
                    if math.isfinite(f_awareness):
                        if f_awareness >= awareness_threshold:
                            aware_count += 1
                    else:
                        invalid_awareness_count += 1
                except (ValueError, TypeError):
                    invalid_awareness_count += 1
            else:
                invalid_awareness_count += 1

            # Track eligible application attempts separately
            if r.is_eligible and getattr(r, "attempted_application", False):
                eligible_attempted_count += 1

        unaware_count = total - aware_count
        awareness_rate = round(aware_count / total, 4) if total > 0 else 0.0
        awareness_pct = round(awareness_rate * 100.0, 2)

        attempted_count = sum(1 for r in outputs if getattr(r, "attempted_application", False))
        attempt_rate = round(attempted_count / total, 4) if total > 0 else 0.0
        eligible_attempt_rate = round(eligible_attempted_count / eligible_count, 4) if eligible_count > 0 else 0.0

        completed_count = sum(1 for r in outputs if getattr(r, "completed_application", False))
        completion_rate = round(completed_count / attempted_count, 4) if attempted_count > 0 else 0.0
        pop_completion_rate = round(completed_count / total, 4) if total > 0 else 0.0

        awareness_app_metrics = AwarenessApplicationMetrics(
            awareness_threshold=awareness_threshold,
            aware_count=aware_count,
            unaware_count=unaware_count,
            awareness_rate=awareness_rate,
            awareness_percentage=awareness_pct,
            attempted_application_count=attempted_count,
            eligible_attempted_count=eligible_attempted_count,
            application_attempt_rate=attempt_rate,
            eligible_application_attempt_rate=eligible_attempt_rate,
            completed_application_count=completed_count,
            application_completion_rate=completion_rate,
            population_completion_rate=pop_completion_rate
        )

        # ----------------------------------------------------------------------
        # 3. Benefits & Fee Relief (Numeric Validation & Sanitization)
        # ----------------------------------------------------------------------
        invalid_fee_count = 0
        valid_total_relief = 0.0
        recipient_estimated_relief = 0.0
        eligible_benefit_recipient_count = 0

        for r in outputs:
            is_recipient = bool(getattr(r, "benefit_received", False))
            if r.is_eligible and is_recipient:
                eligible_benefit_recipient_count += 1

            raw_fee = getattr(r, "estimated_fee_relief_inr", None)
            if raw_fee is not None and not isinstance(raw_fee, bool):
                try:
                    f_fee = float(raw_fee)
                    if math.isfinite(f_fee) and f_fee >= 0.0:
                        valid_total_relief += f_fee
                        if is_recipient:
                            recipient_estimated_relief += f_fee
                    else:
                        invalid_fee_count += 1
                except (ValueError, TypeError):
                    invalid_fee_count += 1
            else:
                invalid_fee_count += 1

        benefit_count = sum(1 for r in outputs if getattr(r, "benefit_received", False))
        recipient_rate = round(benefit_count / total, 4) if total > 0 else 0.0
        eligible_recipient_rate = round(eligible_benefit_recipient_count / eligible_count, 4) if eligible_count > 0 else 0.0

        total_relief = round(valid_total_relief, 2)
        recip_relief = round(recipient_estimated_relief, 2)
        avg_relief_eligible = round(total_relief / eligible_count, 2) if eligible_count > 0 else 0.0
        avg_relief_recipient = round(recip_relief / benefit_count, 2) if benefit_count > 0 else 0.0

        benefit_metrics = BenefitMetrics(
            benefit_received_count=benefit_count,
            eligible_benefit_recipient_count=eligible_benefit_recipient_count,
            benefit_recipient_rate=recipient_rate,
            eligible_benefit_recipient_rate=eligible_recipient_rate,
            total_estimated_fee_relief_inr=total_relief,
            average_fee_relief_per_eligible_inr=avg_relief_eligible,
            average_estimated_fee_relief_per_recipient_persona_inr=avg_relief_recipient
        )

        # ----------------------------------------------------------------------
        # 4. Administrative Lifecycle Caveat
        # ----------------------------------------------------------------------
        lifecycle_status = AdministrativeLifecycleStatus()

        # ----------------------------------------------------------------------
        # 5. Categorical & Demographic Breakdowns
        # ----------------------------------------------------------------------
        breakdown_keys = [
            "district",
            "gender",
            "course",
            "caste_category",
            "institution_type"
        ]

        breakdowns: Dict[str, Dict[str, Dict[str, Any]]] = {}

        # Compute demographic breakdowns from demographics_summary
        for key in breakdown_keys:
            breakdowns[key] = cls._compute_demographic_breakdown(
                outputs=outputs,
                field_key=key,
                awareness_threshold=awareness_threshold
            )

        # Compute breakdown by final simulation state (SimulationState enum value)
        breakdowns["final_simulation_state"] = cls._compute_state_breakdown(
            outputs=outputs,
            awareness_threshold=awareness_threshold
        )

        # ----------------------------------------------------------------------
        # 6. Ineligibility Reasons Distribution
        # ----------------------------------------------------------------------
        ineligibility_reasons: Dict[str, int] = {}
        for r in outputs:
            if not r.is_eligible and hasattr(r, "statutory_failure_reasons") and r.statutory_failure_reasons:
                for reason in r.statutory_failure_reasons:
                    ineligibility_reasons[reason] = ineligibility_reasons.get(reason, 0) + 1

        # Methodological disclosures
        notes.append(
            f"Awareness classification applied threshold >= {awareness_threshold:.2f} on continuous awareness score."
        )
        if invalid_awareness_count > 0:
            notes.append(
                f"Encountered {invalid_awareness_count} personas with missing or non-finite awareness_score (non-numeric or non-finite); "
                "classified as unaware without corrupting calculations."
            )
        if invalid_fee_count > 0:
            notes.append(
                f"Encountered {invalid_fee_count} personas with missing, negative, or non-finite estimated_fee_relief_inr (non-numeric or non-finite); "
                "excluded from aggregate fee relief sums without fabricating financial values."
            )
        notes.append(
            "Administrative application workflow metrics are reported as UNAVAILABLE; simulation outcomes represent "
            "agent behavioral states rather than verified portal audit trails."
        )

        return AnalyticsReport(
            cohort_name=cohort_name,
            total_personas=total,
            awareness_threshold=awareness_threshold,
            population_and_eligibility=pop_elig_metrics,
            awareness_and_application=awareness_app_metrics,
            benefits=benefit_metrics,
            administrative_lifecycle=lifecycle_status,
            breakdowns=breakdowns,
            ineligibility_reasons=ineligibility_reasons,
            methodological_notes=notes
        )

    @classmethod
    def _compute_demographic_breakdown(
        cls,
        outputs: List[SimulationStepOutput],
        field_key: str,
        awareness_threshold: float
    ) -> Dict[str, Dict[str, Any]]:
        """
        Groups outputs by a specific key in demographics_summary and computes sub-metrics.
        Safely defaults missing or non-dict demographics to 'Unknown'.
        """
        groups: Dict[str, List[SimulationStepOutput]] = {}
        for r in outputs:
            summary = r.demographics_summary if isinstance(r.demographics_summary, dict) else {}
            raw_val = summary.get(field_key)
            if raw_val is None or str(raw_val).strip() == "":
                group_name = "Unknown"
            else:
                group_name = str(raw_val).strip()

            if group_name not in groups:
                groups[group_name] = []
            groups[group_name].append(r)

        return cls._aggregate_group_metrics(groups, awareness_threshold)

    @classmethod
    def _compute_state_breakdown(
        cls,
        outputs: List[SimulationStepOutput],
        awareness_threshold: float
    ) -> Dict[str, Dict[str, Any]]:
        """
        Groups outputs by final_simulation_state and computes sub-metrics.
        """
        groups: Dict[str, List[SimulationStepOutput]] = {}
        for r in outputs:
            raw_val = getattr(r, "final_simulation_state", None)
            if raw_val is None or str(raw_val).strip() == "":
                group_name = "Unknown"
            else:
                group_name = str(raw_val).strip()

            if group_name not in groups:
                groups[group_name] = []
            groups[group_name].append(r)

        return cls._aggregate_group_metrics(groups, awareness_threshold)

    @staticmethod
    def _aggregate_group_metrics(
        groups: Dict[str, List[SimulationStepOutput]],
        awareness_threshold: float
    ) -> Dict[str, Dict[str, Any]]:
        """
        Calculates rates and counts for each group in a grouped dictionary.
        """
        result: Dict[str, Dict[str, Any]] = {}
        for group_name, members in groups.items():
            tot = len(members)
            elig = sum(1 for m in members if m.is_eligible)
            inelig = tot - elig
            elig_rate = round(elig / tot, 4) if tot > 0 else 0.0

            aware = 0
            for m in members:
                raw_score = getattr(m, "awareness_score", None)
                if raw_score is not None and not isinstance(raw_score, bool):
                    try:
                        f_score = float(raw_score)
                        if math.isfinite(f_score) and f_score >= awareness_threshold:
                            aware += 1
                    except (ValueError, TypeError):
                        pass
            aware_rate = round(aware / tot, 4) if tot > 0 else 0.0

            attempted = sum(1 for m in members if getattr(m, "attempted_application", False))
            eligible_attempted = sum(
                1 for m in members if m.is_eligible and getattr(m, "attempted_application", False)
            )
            attempt_rate = round(attempted / tot, 4) if tot > 0 else 0.0
            eligible_attempt_rate = round(eligible_attempted / elig, 4) if elig > 0 else 0.0

            completed = sum(1 for m in members if getattr(m, "completed_application", False))
            completion_rate = round(completed / attempted, 4) if attempted > 0 else 0.0

            benefit = sum(1 for m in members if getattr(m, "benefit_received", False))
            eligible_benefit = sum(
                1 for m in members if m.is_eligible and getattr(m, "benefit_received", False)
            )
            benefit_rate = round(benefit / tot, 4) if tot > 0 else 0.0
            eligible_benefit_rate = round(eligible_benefit / elig, 4) if elig > 0 else 0.0

            valid_relief = 0.0
            recipient_estimated_relief = 0.0
            for m in members:
                is_m_recipient = bool(getattr(m, "benefit_received", False))
                raw_fee = getattr(m, "estimated_fee_relief_inr", None)
                if raw_fee is not None and not isinstance(raw_fee, bool):
                    try:
                        f_fee = float(raw_fee)
                        if math.isfinite(f_fee) and f_fee >= 0.0:
                            valid_relief += f_fee
                            if is_m_recipient:
                                recipient_estimated_relief += f_fee
                    except (ValueError, TypeError):
                        pass

            total_relief = round(valid_relief, 2)
            recip_relief = round(recipient_estimated_relief, 2)
            avg_relief_elig = round(total_relief / elig, 2) if elig > 0 else 0.0
            avg_relief_recipient = round(recip_relief / benefit, 2) if benefit > 0 else 0.0

            summary = GroupBreakdownSummary(
                total_count=tot,
                eligible_count=elig,
                ineligible_count=inelig,
                eligibility_rate=elig_rate,
                aware_count=aware,
                awareness_rate=aware_rate,
                attempted_application_count=attempted,
                eligible_attempted_count=eligible_attempted,
                application_attempt_rate=attempt_rate,
                eligible_application_attempt_rate=eligible_attempt_rate,
                completed_application_count=completed,
                application_completion_rate=completion_rate,
                benefit_received_count=benefit,
                eligible_benefit_recipient_count=eligible_benefit,
                benefit_recipient_rate=benefit_rate,
                eligible_benefit_recipient_rate=eligible_benefit_rate,
                total_estimated_fee_relief_inr=total_relief,
                average_fee_relief_per_eligible_inr=avg_relief_elig,
                average_estimated_fee_relief_per_recipient_persona_inr=avg_relief_recipient
            )
            result[group_name] = asdict(summary)

        return result


# ==============================================================================
# CONVENIENCE MODULE FUNCTIONS
# ==============================================================================

def compute_cohort_analytics(
    cohort: CohortSimulationResult,
    awareness_threshold: float = DEFAULT_AWARENESS_THRESHOLD
) -> AnalyticsReport:
    """Convenience function to compute analytics on a CohortSimulationResult."""
    return PolicySimulationAnalytics.analyze_cohort(cohort, awareness_threshold=awareness_threshold)


def compute_multi_step_analytics(
    multi_step_result: MultiStepSimulationResult,
    awareness_threshold: float = DEFAULT_AWARENESS_THRESHOLD
) -> AnalyticsReport:
    """Convenience function to compute analytics on a MultiStepSimulationResult."""
    return PolicySimulationAnalytics.analyze_multi_step(multi_step_result, awareness_threshold=awareness_threshold)


def compute_step_outputs_analytics(
    outputs: List[SimulationStepOutput],
    cohort_name: str = "Custom-Outputs",
    awareness_threshold: float = DEFAULT_AWARENESS_THRESHOLD
) -> AnalyticsReport:
    """Convenience function to compute analytics directly from a list of SimulationStepOutputs."""
    return PolicySimulationAnalytics.analyze_step_outputs(
        outputs=outputs,
        cohort_name=cohort_name,
        awareness_threshold=awareness_threshold
    )
