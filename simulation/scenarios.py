"""
Scenario Engine for Maharashtra Policy Simulator.

This module provides counterfactual policy scenario modeling and comparative evaluation
for higher education scholarship schemes (specifically Rajarshi Chhatrapati Shahu Maharaj Yojna).

Three Assigned Interventions:
1. Awareness Campaign: Modifies strictly initial_awareness.
2. Documentation Assistance: Modifies strictly document_readiness.
3. Institutional Support: Modifies strictly document_readiness and institutional_trust.

Core Architectural & Epistemic Tenets:
1. Strict Attribute Boundaries:
   Interventions modify ONLY their assigned capacity/support parameters.
   Attributes such as peer_network_support, digital_literacy, personality traits,
   demographics, caste category, and family income are strictly immutable.
2. Source Persona Immutability:
   The caller's original persona instances are never mutated; baseline and intervention
   populations are isolated via copy.deepcopy().
3. Statutory Eligibility Invariance:
   Interventions model administrative facilitation and behavioral outreach; they do NOT
   and CANNOT fabricate statutory eligibility. Baseline and intervention eligibility counts
   must match identically (delta_eligible == 0).
4. Deterministic Offline Safety:
   Default execution uses StubLLMProvider, ensuring zero network calls to Gemini or external APIs.
5. Integration Limitations & Epistemic Framing:
   - When assumed_reimbursement_rate is None, SimulationEngine.run_cohort() defaults to the
     PoC assumption of 50%. This is an assumed PoC rate, not a verified statutory DTE tiered outcome.
   - Institutional trust does not directly alter the existing deterministic application-probability
     formula in SimulationEngine; it provides qualitative/behavioral grounding while document_readiness
     drives the deterministic completion shift.
   - Counterfactual outputs represent exploratory simulation hypotheses, not empirical forecasts.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Any, Optional
import copy
import json
import math

from simulation.persona import StudentPersona
from simulation.engine import SimulationEngine, CohortSimulationResult
from simulation.agent import StubLLMProvider, BaseLLMProvider
from simulation.analytics import PolicySimulationAnalytics, AnalyticsReport


DEFAULT_EPISTEMIC_DISCLAIMER: str = (
    "Counterfactual scenario outputs represent synthetic behavioral simulations under explicitly defined "
    "intervention hypotheses. They are exploratory decision-support estimates based on modeled behavioral priors, "
    "NOT real-world empirical forecasts or guaranteed administrative outcomes."
)


class InterventionType(str, Enum):
    """Enumeration of the three approved counterfactual policy interventions."""
    AWARENESS_CAMPAIGN = "AWARENESS_CAMPAIGN"
    DOCUMENTATION_ASSISTANCE = "DOCUMENTATION_ASSISTANCE"
    INSTITUTIONAL_SUPPORT = "INSTITUTIONAL_SUPPORT"


def _validate_scenario_param(name: str, val: Any, is_floor: bool = False) -> None:
    """
    Validates that an intervention parameter is strictly a finite numeric int or float
    (excluding bool) bounded between 0.0 and 1.0 inclusive.
    """
    if val is None:
        return
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        raise ValueError(
            f"Invalid {name}: {val!r}. Parameter must be a strictly numeric int or float (excluding bool)."
        )
    f_val = float(val)
    if not math.isfinite(f_val):
        raise ValueError(
            f"Invalid {name}: {val!r}. Parameter must be a finite numeric value (not NaN or Infinity)."
        )
    if f_val < 0.0 or f_val > 1.0:
        raise ValueError(
            f"Invalid {name}: {val!r}. "
            f"{'Floor' if is_floor else 'Delta'} must be a non-negative value bounded between 0.0 and 1.0 inclusive."
        )


@dataclass
class ScenarioIntervention:
    """
    Specification for a counterfactual policy intervention with strict attribute boundaries.

    Permitted attribute boundaries:
    - AWARENESS_CAMPAIGN: modifies ONLY initial_awareness.
    - DOCUMENTATION_ASSISTANCE: modifies ONLY document_readiness.
    - INSTITUTIONAL_SUPPORT: modifies ONLY document_readiness and institutional_trust.
    """
    intervention_type: InterventionType
    name: str
    description: str

    # Awareness Campaign: modifies ONLY initial_awareness
    awareness_delta: float = 0.0
    awareness_floor: Optional[float] = None

    # Documentation Assistance: modifies ONLY document_readiness
    # Institutional Support: modifies document_readiness AND institutional_trust
    document_readiness_delta: float = 0.0
    document_readiness_floor: Optional[float] = None

    institutional_trust_delta: float = 0.0
    institutional_trust_floor: Optional[float] = None

    def __post_init__(self) -> None:
        """Validates numeric ranges, types, and attribute boundaries upon instantiation."""
        self.validate_boundaries()

    def validate_boundaries(self) -> None:
        """
        Enforces that only permitted attributes are configured for the specified intervention type,
        and validates that all parameters are strictly finite, non-negative, and bounded in [0.0, 1.0].
        Raises ValueError with an informative explanation if boundary rules are violated.
        """
        # 1. Type, finite, and range validation for all parameters
        _validate_scenario_param("awareness_delta", self.awareness_delta, is_floor=False)
        _validate_scenario_param("awareness_floor", self.awareness_floor, is_floor=True)
        _validate_scenario_param("document_readiness_delta", self.document_readiness_delta, is_floor=False)
        _validate_scenario_param("document_readiness_floor", self.document_readiness_floor, is_floor=True)
        _validate_scenario_param("institutional_trust_delta", self.institutional_trust_delta, is_floor=False)
        _validate_scenario_param("institutional_trust_floor", self.institutional_trust_floor, is_floor=True)

        # 2. Cross-intervention boundary enforcement
        if self.intervention_type == InterventionType.AWARENESS_CAMPAIGN:
            if self.document_readiness_delta != 0.0 or self.document_readiness_floor is not None:
                raise ValueError(
                    f"Boundary violation for {self.intervention_type.value}: "
                    "Awareness Campaign can modify ONLY initial_awareness; document_readiness cannot be altered."
                )
            if self.institutional_trust_delta != 0.0 or self.institutional_trust_floor is not None:
                raise ValueError(
                    f"Boundary violation for {self.intervention_type.value}: "
                    "Awareness Campaign can modify ONLY initial_awareness; institutional_trust cannot be altered."
                )

        elif self.intervention_type == InterventionType.DOCUMENTATION_ASSISTANCE:
            if self.awareness_delta != 0.0 or self.awareness_floor is not None:
                raise ValueError(
                    f"Boundary violation for {self.intervention_type.value}: "
                    "Documentation Assistance can modify ONLY document_readiness; initial_awareness cannot be altered."
                )
            if self.institutional_trust_delta != 0.0 or self.institutional_trust_floor is not None:
                raise ValueError(
                    f"Boundary violation for {self.intervention_type.value}: "
                    "Documentation Assistance can modify ONLY document_readiness; institutional_trust cannot be altered."
                )

        elif self.intervention_type == InterventionType.INSTITUTIONAL_SUPPORT:
            if self.awareness_delta != 0.0 or self.awareness_floor is not None:
                raise ValueError(
                    f"Boundary violation for {self.intervention_type.value}: "
                    "Institutional Support can modify ONLY document_readiness and institutional_trust; "
                    "initial_awareness cannot be altered."
                )


@dataclass
class ScenarioDeltaMetrics:
    """
    Mathematical differentials between intervention and baseline outcomes.
    All rates and sums declare explicit denominators.
    """
    # Statutory preservation verification (must be identically 0)
    eligible_count_delta: int
    ineligible_count_delta: int

    # Awareness funnel deltas
    aware_count_delta: int
    awareness_rate_delta: float

    # Application funnel deltas
    attempted_application_count_delta: int
    application_attempt_rate_delta: float
    eligible_attempted_count_delta: int
    eligible_application_attempt_rate_delta: float
    completed_application_count_delta: int
    application_completion_rate_delta: float

    # Realized benefits & relief deltas
    benefit_received_count_delta: int
    eligible_benefit_recipient_count_delta: int
    benefit_recipient_rate_delta: float
    eligible_benefit_recipient_rate_delta: float
    total_estimated_fee_relief_inr_delta: float
    average_estimated_fee_relief_per_recipient_persona_inr_delta: float

    # Percentage point shift in uptake (always defined, e.g. +5.0 pp)
    uptake_percentage_point_delta: float

    # Relative uptake growth percentage: ((interv - base) / base) * 100
    # Safely None (JSON null) when base == 0 to prevent NaN/Infinity serialization errors
    relative_uptake_growth_percentage: Optional[float]


@dataclass
class ScenarioComparisonReport:
    """
    Complete, structured, JSON-serializable scenario comparative report
    evaluating counterfactual intervention effects against baseline.
    """
    scenario_name: str
    intervention: ScenarioIntervention
    total_personas: int
    seed: Optional[int]
    assumed_reimbursement_rate: Optional[float]
    awareness_threshold: float
    baseline_analytics: AnalyticsReport
    intervention_analytics: AnalyticsReport
    deltas: ScenarioDeltaMetrics
    epistemic_disclaimer: str = DEFAULT_EPISTEMIC_DISCLAIMER
    methodological_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Converts the comparison report into a clean, nested dictionary."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Serializes the report to structured JSON, disallowing NaN/Infinity."""
        return json.dumps(self.to_dict(), indent=indent, default=str, allow_nan=False)


class ScenarioEngine:
    """
    Scenario Engine orchestrating paired baseline and counterfactual intervention
    simulations for policy evaluation.
    """

    def __init__(self, simulation_engine: Optional[SimulationEngine] = None):
        """
        Initializes ScenarioEngine.
        Defaults to an offline SimulationEngine using StubLLMProvider.
        """
        self.simulation_engine = simulation_engine or SimulationEngine(llm_provider=StubLLMProvider())

    def apply_intervention(
        self,
        personas: List[StudentPersona],
        intervention: ScenarioIntervention
    ) -> List[StudentPersona]:
        """
        Deep-copies the persona population and applies bounded attribute changes ([0.0, 1.0]).
        Guarantees that caller's original persona instances are never mutated.
        """
        intervention.validate_boundaries()
        cloned_personas = copy.deepcopy(personas)

        for p in cloned_personas:
            if intervention.intervention_type == InterventionType.AWARENESS_CAMPAIGN:
                val = p.initial_awareness + intervention.awareness_delta
                if intervention.awareness_floor is not None:
                    val = max(val, intervention.awareness_floor)
                p.initial_awareness = round(min(1.0, max(0.0, val)), 4)

            elif intervention.intervention_type == InterventionType.DOCUMENTATION_ASSISTANCE:
                val = p.document_readiness + intervention.document_readiness_delta
                if intervention.document_readiness_floor is not None:
                    val = max(val, intervention.document_readiness_floor)
                p.document_readiness = round(min(1.0, max(0.0, val)), 4)

            elif intervention.intervention_type == InterventionType.INSTITUTIONAL_SUPPORT:
                # Modifies document_readiness AND institutional_trust
                val_doc = p.document_readiness + intervention.document_readiness_delta
                if intervention.document_readiness_floor is not None:
                    val_doc = max(val_doc, intervention.document_readiness_floor)
                p.document_readiness = round(min(1.0, max(0.0, val_doc)), 4)

                val_trust = p.institutional_trust + intervention.institutional_trust_delta
                if intervention.institutional_trust_floor is not None:
                    val_trust = max(val_trust, intervention.institutional_trust_floor)
                p.institutional_trust = round(min(1.0, max(0.0, val_trust)), 4)

        return cloned_personas

    def run_comparison(
        self,
        personas: List[StudentPersona],
        intervention: ScenarioIntervention,
        cohort_name: str = "Scenario-Cohort",
        seed: Optional[int] = 42,
        awareness_threshold: float = PolicySimulationAnalytics.DEFAULT_AWARENESS_THRESHOLD,
        assumed_reimbursement_rate: Optional[float] = None
    ) -> ScenarioComparisonReport:
        """
        Executes a paired baseline and intervention simulation run using identical
        initial populations, deep-copy isolation, compatible random seeds, and
        the reusable PolicySimulationAnalytics engine.
        """
        intervention.validate_boundaries()

        # Isolate baseline and intervention cohorts via copy.deepcopy
        baseline_personas = copy.deepcopy(personas)
        intervention_personas = self.apply_intervention(personas, intervention)

        # 1. Run Baseline Simulation
        baseline_result: CohortSimulationResult = self.simulation_engine.run_cohort(
            personas=baseline_personas,
            cohort_name=f"{cohort_name}-Baseline",
            seed=seed,
            assumed_reimbursement_rate=assumed_reimbursement_rate
        )

        # 2. Run Intervention Simulation (with identical seed and parameters)
        intervention_result: CohortSimulationResult = self.simulation_engine.run_cohort(
            personas=intervention_personas,
            cohort_name=f"{cohort_name}-{intervention.intervention_type.value}",
            seed=seed,
            assumed_reimbursement_rate=assumed_reimbursement_rate
        )

        # 3. Analyze both runs using PolicySimulationAnalytics
        baseline_analytics: AnalyticsReport = PolicySimulationAnalytics.analyze_cohort(
            cohort=baseline_result,
            awareness_threshold=awareness_threshold
        )
        intervention_analytics: AnalyticsReport = PolicySimulationAnalytics.analyze_cohort(
            cohort=intervention_result,
            awareness_threshold=awareness_threshold
        )

        # 4. Compute Differentials
        deltas = self._calculate_deltas(baseline_analytics, intervention_analytics)

        # 5. Methodological Documentation
        notes: List[str] = [
            f"Paired counterfactual evaluation executed for intervention: '{intervention.name}' ({intervention.intervention_type.value}).",
            f"Deep-copy isolation applied to {len(personas)} input personas; source personas remained completely unmutated.",
            f"Random seed={seed} applied symmetrically to both baseline and intervention runs."
        ]

        if assumed_reimbursement_rate is None:
            notes.append(
                "Integration Limitation: SimulationEngine was executed without an explicit assumed_reimbursement_rate, "
                "falling back to the PoC default baseline of 50%. Estimated fee relief reflects this assumed 50% PoC "
                "parameter rather than verified statutory DTE tiered rules. Full statutory fee relief calculations "
                "require integration with Shravani's DTE Policy Engine."
            )
        else:
            notes.append(
                f"Reimbursement Rate: Simulation executed with explicit assumed_reimbursement_rate={assumed_reimbursement_rate:.2f}."
            )

        if intervention.intervention_type == InterventionType.INSTITUTIONAL_SUPPORT:
            notes.append(
                "Behavioral Note: The deterministic application-probability formula in the simulation engine does not "
                "directly evaluate institutional_trust; increasing institutional_trust serves as a behavioral/qualitative "
                "attribute for persona reasoning, while document_readiness is the attribute driving the deterministic "
                "completion and uptake shifts. No numerical uptake effect is claimed from institutional_trust alone."
            )

        return ScenarioComparisonReport(
            scenario_name=cohort_name,
            intervention=intervention,
            total_personas=len(personas),
            seed=seed,
            assumed_reimbursement_rate=assumed_reimbursement_rate,
            awareness_threshold=awareness_threshold,
            baseline_analytics=baseline_analytics,
            intervention_analytics=intervention_analytics,
            deltas=deltas,
            epistemic_disclaimer=DEFAULT_EPISTEMIC_DISCLAIMER,
            methodological_notes=notes
        )

    @staticmethod
    def _calculate_deltas(
        baseline: AnalyticsReport,
        intervention: AnalyticsReport
    ) -> ScenarioDeltaMetrics:
        """
        Calculates exact mathematical differentials between intervention and baseline analytics.
        Handles zero denominators safely.
        """
        b_pop = baseline.population_and_eligibility
        i_pop = intervention.population_and_eligibility

        b_app = baseline.awareness_and_application
        i_app = intervention.awareness_and_application

        b_ben = baseline.benefits
        i_ben = intervention.benefits

        # Relative uptake growth calculation with zero-denominator safety
        base_recipients = b_ben.benefit_received_count
        interv_recipients = i_ben.benefit_received_count

        if base_recipients > 0:
            relative_growth: Optional[float] = round(
                ((interv_recipients - base_recipients) / base_recipients) * 100.0,
                2
            )
        else:
            # Whenever baseline uptake is zero, relative growth is mathematically undefined
            # and strictly represented as None (regardless of whether intervention uptake is zero or positive)
            relative_growth = None

        return ScenarioDeltaMetrics(
            eligible_count_delta=i_pop.eligible_count - b_pop.eligible_count,
            ineligible_count_delta=i_pop.ineligible_count - b_pop.ineligible_count,
            aware_count_delta=i_app.aware_count - b_app.aware_count,
            awareness_rate_delta=round(i_app.awareness_rate - b_app.awareness_rate, 4),
            attempted_application_count_delta=i_app.attempted_application_count - b_app.attempted_application_count,
            application_attempt_rate_delta=round(i_app.application_attempt_rate - b_app.application_attempt_rate, 4),
            eligible_attempted_count_delta=i_app.eligible_attempted_count - b_app.eligible_attempted_count,
            eligible_application_attempt_rate_delta=round(
                i_app.eligible_application_attempt_rate - b_app.eligible_application_attempt_rate,
                4
            ),
            completed_application_count_delta=i_app.completed_application_count - b_app.completed_application_count,
            application_completion_rate_delta=round(
                i_app.application_completion_rate - b_app.application_completion_rate,
                4
            ),
            benefit_received_count_delta=interv_recipients - base_recipients,
            eligible_benefit_recipient_count_delta=(
                i_ben.eligible_benefit_recipient_count - b_ben.eligible_benefit_recipient_count
            ),
            benefit_recipient_rate_delta=round(i_ben.benefit_recipient_rate - b_ben.benefit_recipient_rate, 4),
            eligible_benefit_recipient_rate_delta=round(
                i_ben.eligible_benefit_recipient_rate - b_ben.eligible_benefit_recipient_rate,
                4
            ),
            total_estimated_fee_relief_inr_delta=round(
                i_ben.total_estimated_fee_relief_inr - b_ben.total_estimated_fee_relief_inr,
                2
            ),
            average_estimated_fee_relief_per_recipient_persona_inr_delta=round(
                i_ben.average_estimated_fee_relief_per_recipient_persona_inr -
                b_ben.average_estimated_fee_relief_per_recipient_persona_inr,
                2
            ),
            uptake_percentage_point_delta=round(
                (i_ben.benefit_recipient_rate - b_ben.benefit_recipient_rate) * 100.0,
                2
            ),
            relative_uptake_growth_percentage=relative_growth
        )

    # --------------------------------------------------------------------------
    # Standard Factory Presets
    # --------------------------------------------------------------------------

    @staticmethod
    def create_awareness_campaign(
        name: str = "Awareness Campaign",
        delta: float = 0.25,
        floor: Optional[float] = None
    ) -> ScenarioIntervention:
        """
        Factory creating an Awareness Campaign intervention.
        Modifies strictly initial_awareness.
        """
        intervention = ScenarioIntervention(
            intervention_type=InterventionType.AWARENESS_CAMPAIGN,
            name=name,
            description="Campaign intervention increasing initial_awareness of the scheme among personas.",
            awareness_delta=delta,
            awareness_floor=floor
        )
        intervention.validate_boundaries()
        return intervention

    @staticmethod
    def create_documentation_assistance(
        name: str = "Documentation Assistance",
        delta: float = 0.25,
        floor: Optional[float] = None
    ) -> ScenarioIntervention:
        """
        Factory creating a Documentation Assistance intervention.
        Modifies strictly document_readiness.
        """
        intervention = ScenarioIntervention(
            intervention_type=InterventionType.DOCUMENTATION_ASSISTANCE,
            name=name,
            description="Assistance intervention improving document_readiness through document scrutiny camps.",
            document_readiness_delta=delta,
            document_readiness_floor=floor
        )
        intervention.validate_boundaries()
        return intervention

    @staticmethod
    def create_institutional_support(
        name: str = "Institutional Support",
        doc_delta: float = 0.15,
        trust_delta: float = 0.25,
        doc_floor: Optional[float] = None,
        trust_floor: Optional[float] = None
    ) -> ScenarioIntervention:
        """
        Factory creating an Institutional Support intervention.
        Modifies strictly document_readiness and institutional_trust.
        """
        intervention = ScenarioIntervention(
            intervention_type=InterventionType.INSTITUTIONAL_SUPPORT,
            name=name,
            description="College scholarship cell intervention improving document_readiness and institutional_trust.",
            document_readiness_delta=doc_delta,
            document_readiness_floor=doc_floor,
            institutional_trust_delta=trust_delta,
            institutional_trust_floor=trust_floor
        )
        intervention.validate_boundaries()
        return intervention


# ==============================================================================
# CONVENIENCE MODULE FUNCTIONS
# ==============================================================================

def run_scenario_comparison(
    personas: List[StudentPersona],
    intervention: ScenarioIntervention,
    cohort_name: str = "Scenario-Cohort",
    seed: Optional[int] = 42,
    awareness_threshold: float = PolicySimulationAnalytics.DEFAULT_AWARENESS_THRESHOLD,
    assumed_reimbursement_rate: Optional[float] = None,
    simulation_engine: Optional[SimulationEngine] = None
) -> ScenarioComparisonReport:
    """Convenience function to run a paired scenario comparison."""
    engine = ScenarioEngine(simulation_engine=simulation_engine)
    return engine.run_comparison(
        personas=personas,
        intervention=intervention,
        cohort_name=cohort_name,
        seed=seed,
        awareness_threshold=awareness_threshold,
        assumed_reimbursement_rate=assumed_reimbursement_rate
    )
