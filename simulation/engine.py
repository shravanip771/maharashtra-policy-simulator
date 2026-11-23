from dataclasses import dataclass, asdict, field, is_dataclass
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
import json
import math

from simulation.persona import StudentPersona, SimulationState
from simulation.policy_rules import RajarshiShahuPolicyEngine, PolicyEvaluationResult, DTEPolicyConfig
from simulation.agent import PersonaAgent, PersonaCalculatedMetrics, PersonaReasoningOutput, BaseLLMProvider


def _safe_serialize(val: Any) -> Any:
    """Recursively serializes enums to string values and dataclasses to dicts for clean JSON."""
    if isinstance(val, Enum):
        return val.value
    if is_dataclass(val) and not isinstance(val, type):
        return {k: _safe_serialize(v) for k, v in asdict(val).items()}
    if isinstance(val, (list, tuple)):
        return [_safe_serialize(x) for x in val]
    if isinstance(val, dict):
        return {k: _safe_serialize(v) for k, v in val.items()}
    return val


def _has_modified_benefit_rates(config: DTEPolicyConfig) -> bool:
    """Checks whether any benefit rate schedule in DTEPolicyConfig deviates from statutory baseline."""
    default_cfg = RajarshiShahuPolicyEngine.DEFAULT_CONFIG
    return (
        config.female_tuition_rate != default_cfg.female_tuition_rate
        or config.female_exam_rate != default_cfg.female_exam_rate
        or config.orphan_tuition_rate != default_cfg.orphan_tuition_rate
        or config.orphan_exam_rate != default_cfg.orphan_exam_rate
        or config.male_tier1_govt_tuition_rate != default_cfg.male_tier1_govt_tuition_rate
        or config.male_tier1_pvt_tuition_rate != default_cfg.male_tier1_pvt_tuition_rate
        or config.male_tier2_tuition_rate != default_cfg.male_tier2_tuition_rate
        or config.male_exam_rate != default_cfg.male_exam_rate
        or config.enable_female_100_percent_rule != default_cfg.enable_female_100_percent_rule
        or config.enable_orphan_100_percent_rule != default_cfg.enable_orphan_100_percent_rule
    )


def resolve_policy_parameters(
    interface_name: str,
    policy_mode: Optional[str] = None,
    assumed_reimbursement_rate: Optional[Any] = None,
    policy_config: Optional[Any] = None
) -> Tuple[str, Optional[float], DTEPolicyConfig, bool]:
    """
    Deterministically resolves and validates policy mode, rate, and configuration parameters.
    Guarantees backward compatibility for existing callers while preventing invalid combinations.
    """
    # 1. Type validation for policy_config
    if policy_config is not None and not isinstance(policy_config, DTEPolicyConfig):
        raise TypeError(f"policy_config must be an instance of DTEPolicyConfig, got {type(policy_config).__name__}.")

    active_config = policy_config or RajarshiShahuPolicyEngine.DEFAULT_CONFIG

    # 2. Type validation for policy_mode
    if policy_mode is not None:
        if not isinstance(policy_mode, str):
            raise TypeError(f"policy_mode must be a string, got {type(policy_mode).__name__}.")
        if policy_mode not in {"legacy_poc", "statutory", "override", "counterfactual"}:
            raise ValueError(f"Invalid policy_mode '{policy_mode}'. Supported modes: 'legacy_poc', 'statutory', 'override', 'counterfactual'.")

    # 3. Mode Resolution
    if policy_mode is not None:
        resolved_mode = policy_mode
    elif assumed_reimbursement_rate is not None:
        if interface_name in {"run_cohort", "run_multistep_cohort"} and not isinstance(assumed_reimbursement_rate, bool) and isinstance(assumed_reimbursement_rate, (int, float)) and float(assumed_reimbursement_rate) == 0.50:
            # Existing cohort callers passing assumed_reimbursement_rate=0.50 retain historical legacy_poc behavior
            resolved_mode = "legacy_poc"
        else:
            resolved_mode = "override"
    else:
        # Both policy_mode and assumed_reimbursement_rate omitted:
        if interface_name == "run_step":
            # Historical run_step evaluated statutory rules when rate was None
            if _has_modified_benefit_rates(active_config):
                resolved_mode = "counterfactual"
            else:
                resolved_mode = "statutory"
        else:
            # Historical run_cohort / run_multistep_cohort evaluated 50% legacy PoC
            resolved_mode = "legacy_poc"

    # 4. Mode-specific constraints and rate validation
    is_counterfactual = False

    if resolved_mode == "statutory":
        if assumed_reimbursement_rate is not None:
            raise ValueError("Explicit assumed_reimbursement_rate cannot be provided when policy_mode='statutory'.")
        if _has_modified_benefit_rates(active_config):
            raise ValueError("Cannot modify statutory benefit rates in policy_mode='statutory'. Use policy_mode='counterfactual'.")
        resolved_rate = None

    elif resolved_mode == "counterfactual":
        if assumed_reimbursement_rate is not None:
            raise ValueError("assumed_reimbursement_rate cannot be specified when policy_mode='counterfactual'. Use policy_mode='override'.")
        resolved_rate = None
        is_counterfactual = True

    elif resolved_mode == "override":
        if assumed_reimbursement_rate is None:
            raise ValueError("policy_mode='override' requires an explicit assumed_reimbursement_rate in [0.0, 1.0].")
        if isinstance(assumed_reimbursement_rate, bool):
            raise ValueError("assumed_reimbursement_rate cannot be a boolean.")
        if not isinstance(assumed_reimbursement_rate, (int, float)):
            raise ValueError(f"assumed_reimbursement_rate must be numeric, got {type(assumed_reimbursement_rate).__name__}.")
        if math.isnan(assumed_reimbursement_rate) or math.isinf(assumed_reimbursement_rate):
            raise ValueError(f"assumed_reimbursement_rate is non-finite ({assumed_reimbursement_rate}).")
        if assumed_reimbursement_rate < 0.0 or assumed_reimbursement_rate > 1.0:
            raise ValueError(f"assumed_reimbursement_rate ({assumed_reimbursement_rate}) is outside the valid range [0.0, 1.0].")
        resolved_rate = float(assumed_reimbursement_rate)
        is_counterfactual = False

    elif resolved_mode == "legacy_poc":
        if assumed_reimbursement_rate is not None:
            if isinstance(assumed_reimbursement_rate, bool):
                raise ValueError("assumed_reimbursement_rate cannot be a boolean.")
            if not isinstance(assumed_reimbursement_rate, (int, float)):
                raise ValueError(f"assumed_reimbursement_rate must be numeric, got {type(assumed_reimbursement_rate).__name__}.")
            if float(assumed_reimbursement_rate) != 0.50:
                raise ValueError(f"policy_mode='legacy_poc' requires assumed_reimbursement_rate=0.50 or None, got {assumed_reimbursement_rate}.")
        resolved_rate = 0.50
        is_counterfactual = False

    return resolved_mode, resolved_rate, active_config, is_counterfactual


@dataclass
class SimulationStepOutput:
    """Structured output representing the complete outcome of one persona simulation."""
    # Identification
    persona_id: str
    persona_name: str
    demographics_summary: Dict[str, Any]

    # Policy & Statutory Result
    scheme_name: str
    is_eligible: bool
    reimbursement_percentage: float
    estimated_fee_relief_inr: float
    statutory_failure_reasons: list
    statutory_notes: list
    benefit_assumptions: list

    # Behavioral & Probabilistic Metrics
    awareness_score: float
    perceived_benefit_score: float
    application_probability: float
    completion_probability: float
    expected_uptake_probability: float

    # Realized Simulation Actions
    attempted_application: bool
    completed_application: bool
    benefit_received: bool
    final_simulation_state: str

    # AI Persona Reasoning & Narrative
    inner_monologue: str
    stated_intention: str
    perceived_barriers: list
    chosen_action: str
    confidence_level: str

    # Stage 2.4 Granular Fee Breakdown & Policy Traceability
    tuition_fee_relief_inr: float = 0.0
    exam_fee_relief_inr: float = 0.0
    policy_mode: str = "statutory"
    is_counterfactual: bool = False
    policy_result: Optional[PolicyEvaluationResult] = None

    def to_dict(self) -> Dict[str, Any]:
        return _safe_serialize(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)


@dataclass
class CohortSimulationResult:
    """Structured aggregate result of a multi-persona population simulation."""
    cohort_name: str
    total_personas: int
    seed: Optional[int]
    assumed_reimbursement_rate: float

    # Statutory & Policy Totals
    eligible_count: int
    ineligible_count: int
    eligibility_rate: float
    total_estimated_fee_relief_inr: float
    average_fee_relief_per_eligible_inr: float

    # Behavioral & Probabilistic Metrics
    average_awareness_score: float
    average_perceived_benefit_score: float
    average_application_probability: float
    average_completion_probability: float
    average_expected_uptake_probability: float

    # Realized Simulation Actions
    attempted_application_count: int
    completed_application_count: int
    benefit_received_count: int
    uptake_rate: float

    # Detailed Categorical Breakdowns
    breakdown_by_gender: Dict[str, Dict[str, Any]]
    breakdown_by_institution_type: Dict[str, Dict[str, Any]]
    breakdown_by_caste_category: Dict[str, Dict[str, Any]]
    ineligibility_reasons_summary: Dict[str, int]
    state_distribution: Dict[str, int]

    # Individual Results
    individual_results: List[SimulationStepOutput]
    assumptions_and_limitations: List[str] = field(default_factory=list)

    # Stage 2.4 Aggregate Extensions
    policy_mode: str = "legacy_poc"
    total_tuition_fee_relief_inr: float = 0.0
    total_exam_fee_relief_inr: float = 0.0
    is_counterfactual: bool = False
    cohort_effective_relief_rate: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return _safe_serialize(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)


class SimulationEngine:
    """
    Simulation Engine orchestrating the virtual step cycle:
    Observe -> Reason -> Act -> Update State for individual personas and populations.
    """
    def __init__(self, llm_provider: Optional[BaseLLMProvider] = None):
        self.llm_provider = llm_provider

    def run_step(
        self,
        persona: StudentPersona,
        step_index: int = 1,
        assumed_reimbursement_rate: Optional[float] = None,
        policy_mode: Optional[str] = None,
        policy_config: Optional[DTEPolicyConfig] = None
    ) -> SimulationStepOutput:
        """
        Executes a complete single-persona simulation cycle for the Rajarshi Shahu scheme.
        """
        resolved_mode, resolved_rate, active_config, is_counterfactual = resolve_policy_parameters(
            interface_name="run_step",
            policy_mode=policy_mode,
            assumed_reimbursement_rate=assumed_reimbursement_rate,
            policy_config=policy_config
        )

        agent = PersonaAgent(persona=persona, llm_provider=self.llm_provider)

        # 1. OBSERVE: Deterministic Policy Evaluation & Environment Perception
        policy_eval: PolicyEvaluationResult = RajarshiShahuPolicyEngine.evaluate_eligibility(
            persona, assumed_reimbursement_rate=resolved_rate, config=active_config
        )

        # Handle legacy_poc mode special clamping (strictly tuition-only 50% relief, 0% exam fee relief)
        if resolved_mode == "legacy_poc":
            if policy_eval.is_eligible:
                tuition_val = float(getattr(persona, "annual_tuition_fee", 0.0) or 0.0)
                tuition_relief = round(min(tuition_val, max(0.0, tuition_val * 0.50)), 2)
                exam_relief = 0.0
                total_relief = tuition_relief
                eff_rate = 0.50
            else:
                tuition_relief = 0.0
                exam_relief = 0.0
                total_relief = 0.0
                eff_rate = 0.0
        else:
            tuition_relief = policy_eval.tuition_fee_relief_inr
            exam_relief = policy_eval.exam_fee_relief_inr
            total_relief = policy_eval.estimated_fee_relief_inr
            eff_rate = policy_eval.reimbursement_percentage

        metrics: PersonaCalculatedMetrics = agent.compute_baseline_metrics(policy_eval)

        persona.record_memory(
            step=step_index,
            event_type="OBSERVE_POLICY",
            details={
                "is_eligible": policy_eval.is_eligible,
                "fee_relief": total_relief,
                "failures": policy_eval.failure_reasons
            }
        )

        # 2. REASON: Cognitive processing & qualitative deliberation via PersonaAgent
        reasoning: PersonaReasoningOutput = agent.reason(policy_eval, metrics)

        persona.record_memory(
            step=step_index,
            event_type="REASON_OUTCOME",
            details={
                "chosen_action": reasoning.chosen_action,
                "barriers": reasoning.perceived_barriers,
                "monologue": reasoning.inner_monologue
            }
        )

        # 3. ACT: Determine the simulated operational behavior
        if not policy_eval.is_eligible:
            new_state = SimulationState.REJECTED
        elif metrics.final_benefit_received:
            new_state = SimulationState.BENEFIT_RECEIVED
        elif metrics.will_attempt_application:
            new_state = SimulationState.APPLIED if metrics.will_complete_application else SimulationState.COLLECTING_DOCUMENTS
        elif metrics.awareness_score > 0.4:
            new_state = SimulationState.EVALUATING
        else:
            new_state = SimulationState.DROPPED_OUT

        # 4. UPDATE STATE
        persona.current_state = new_state
        persona.record_memory(
            step=step_index,
            event_type="STATE_TRANSITION",
            details={"new_state": new_state.value}
        )

        # Package comprehensive structured output
        return SimulationStepOutput(
            persona_id=persona.persona_id,
            persona_name=persona.name,
            demographics_summary={
                "age": persona.age,
                "gender": persona.gender,
                "district": persona.district,
                "family_income": persona.family_income,
                "caste_category": persona.caste_category,
                "course": persona.course_name,
                "institution_type": persona.institution_type.value,
                "admission_mode": persona.admission_mode.value,
                "annual_tuition_fee": persona.annual_tuition_fee,
                "first_generation_learner": persona.first_generation_learner
            },
            scheme_name=policy_eval.scheme_name,
            is_eligible=policy_eval.is_eligible,
            reimbursement_percentage=eff_rate,
            estimated_fee_relief_inr=total_relief,
            statutory_failure_reasons=policy_eval.failure_reasons,
            statutory_notes=policy_eval.statutory_notes,
            benefit_assumptions=policy_eval.benefit_assumptions,
            awareness_score=metrics.awareness_score,
            perceived_benefit_score=metrics.perceived_benefit_score,
            application_probability=metrics.application_probability,
            completion_probability=metrics.completion_probability,
            expected_uptake_probability=metrics.expected_uptake_probability,
            attempted_application=metrics.will_attempt_application,
            completed_application=metrics.will_complete_application,
            benefit_received=metrics.final_benefit_received,
            final_simulation_state=new_state.value,
            inner_monologue=reasoning.inner_monologue,
            stated_intention=reasoning.stated_intention,
            perceived_barriers=reasoning.perceived_barriers,
            chosen_action=reasoning.chosen_action,
            confidence_level=reasoning.confidence_level,
            tuition_fee_relief_inr=tuition_relief,
            exam_fee_relief_inr=exam_relief,
            policy_mode=resolved_mode,
            is_counterfactual=is_counterfactual,
            policy_result=policy_eval
        )

    def run_cohort(
        self,
        personas: List[StudentPersona],
        cohort_name: str = "Dhule-10-Persona-Cohort",
        seed: Optional[int] = None,
        assumed_reimbursement_rate: Optional[float] = None,
        policy_mode: Optional[str] = None,
        policy_config: Optional[DTEPolicyConfig] = None
    ) -> CohortSimulationResult:
        """
        Executes individual simulations for each persona in a cohort and calculates
        comprehensive aggregate statistics, breakdowns, and barrier distributions.
        Supports policy_mode: 'legacy_poc', 'statutory', 'override', and 'counterfactual'.
        """
        resolved_mode, resolved_rate, active_config, is_counterfactual = resolve_policy_parameters(
            "run_cohort",
            policy_mode=policy_mode,
            assumed_reimbursement_rate=assumed_reimbursement_rate,
            policy_config=policy_config
        )

        individual_results: List[SimulationStepOutput] = []

        for p in personas:
            step_out = self.run_step(
                persona=p,
                step_index=1,
                assumed_reimbursement_rate=resolved_rate,
                policy_mode=resolved_mode,
                policy_config=active_config
            )
            individual_results.append(step_out)

        total = len(individual_results)
        eligible_count = sum(1 for r in individual_results if r.is_eligible)
        ineligible_count = total - eligible_count
        eligibility_rate = round(eligible_count / total, 4) if total > 0 else 0.0

        total_relief = sum(r.estimated_fee_relief_inr for r in individual_results)
        total_tuition = sum(r.tuition_fee_relief_inr for r in individual_results)
        total_exam = sum(r.exam_fee_relief_inr for r in individual_results)
        avg_relief_eligible = round(total_relief / eligible_count, 2) if eligible_count > 0 else 0.0

        total_eligible_fees = sum(
            (r.demographics_summary.get("annual_tuition_fee", 0.0) + (r.policy_result.fee_breakdown.annual_exam_fee if r.policy_result and r.policy_result.fee_breakdown else 0.0))
            for r in individual_results if r.is_eligible
        )
        cohort_effective_relief_rate = round(total_relief / total_eligible_fees, 4) if total_eligible_fees > 0 else (
            round(sum(r.reimbursement_percentage for r in individual_results if r.is_eligible) / eligible_count, 4) if eligible_count > 0 else 0.0
        )

        # Behavioral & Probabilistic Averages
        avg_awareness = round(sum(r.awareness_score for r in individual_results) / total, 4) if total > 0 else 0.0
        avg_benefit = round(sum(r.perceived_benefit_score for r in individual_results) / total, 4) if total > 0 else 0.0
        avg_app_prob = round(sum(r.application_probability for r in individual_results) / total, 4) if total > 0 else 0.0
        avg_comp_prob = round(sum(r.completion_probability for r in individual_results) / total, 4) if total > 0 else 0.0
        avg_uptake_prob = round(sum(r.expected_uptake_probability for r in individual_results) / total, 4) if total > 0 else 0.0

        # Realized actions
        attempted_count = sum(1 for r in individual_results if r.attempted_application)
        completed_count = sum(1 for r in individual_results if r.completed_application)
        benefit_count = sum(1 for r in individual_results if r.benefit_received)
        uptake_rate = round(benefit_count / total, 4) if total > 0 else 0.0

        # Breakdowns helper
        def compute_breakdown(key: str) -> Dict[str, Dict[str, Any]]:
            breakdown: Dict[str, Dict[str, Any]] = {}
            for r in individual_results:
                group_val = r.demographics_summary.get(key, "Unknown")
                if group_val not in breakdown:
                    breakdown[group_val] = {
                        "total_count": 0,
                        "eligible_count": 0,
                        "ineligible_count": 0,
                        "benefit_received_count": 0,
                        "total_relief_inr": 0.0
                    }
                breakdown[group_val]["total_count"] += 1
                if r.is_eligible:
                    breakdown[group_val]["eligible_count"] += 1
                else:
                    breakdown[group_val]["ineligible_count"] += 1
                if r.benefit_received:
                    breakdown[group_val]["benefit_received_count"] += 1
                breakdown[group_val]["total_relief_inr"] += r.estimated_fee_relief_inr

            # Calculate rates
            for g, data in breakdown.items():
                tot_g = data["total_count"]
                data["eligibility_rate"] = round(data["eligible_count"] / tot_g, 4) if tot_g > 0 else 0.0
                data["uptake_rate"] = round(data["benefit_received_count"] / tot_g, 4) if tot_g > 0 else 0.0

            return breakdown

        gender_breakdown = compute_breakdown("gender")
        inst_breakdown = compute_breakdown("institution_type")
        caste_breakdown = compute_breakdown("caste_category")

        # Statutory ineligibility failure reasons summary
        ineligibility_reasons: Dict[str, int] = {}
        for r in individual_results:
            for reason in r.statutory_failure_reasons:
                ineligibility_reasons[reason] = ineligibility_reasons.get(reason, 0) + 1

        # Simulation state distribution
        state_distribution: Dict[str, int] = {}
        for r in individual_results:
            state_distribution[r.final_simulation_state] = state_distribution.get(r.final_simulation_state, 0) + 1

        eff_assumed_rate = resolved_rate if resolved_rate is not None else cohort_effective_relief_rate

        assumptions = [
            f"Policy mode evaluated: {resolved_mode} (is_counterfactual={is_counterfactual}).",
            f"Statutory rules based on official Rajarshi Shahu EBC criteria (Income <= 8L, CAP admission, attendance >= 75%).",
            f"Assumed fee reimbursement rate: {eff_assumed_rate * 100:.0f}%. Note: actual departmental rules vary.",
            f"Demographic fields grounded in Dhule 2010-11 education data; income/caste/behavioral parameters use baseline priors."
        ]

        return CohortSimulationResult(
            cohort_name=cohort_name,
            total_personas=total,
            seed=seed,
            assumed_reimbursement_rate=eff_assumed_rate,
            eligible_count=eligible_count,
            ineligible_count=ineligible_count,
            eligibility_rate=eligibility_rate,
            total_estimated_fee_relief_inr=total_relief,
            average_fee_relief_per_eligible_inr=avg_relief_eligible,
            average_awareness_score=avg_awareness,
            average_perceived_benefit_score=avg_benefit,
            average_application_probability=avg_app_prob,
            average_completion_probability=avg_comp_prob,
            average_expected_uptake_probability=avg_uptake_prob,
            attempted_application_count=attempted_count,
            completed_application_count=completed_count,
            benefit_received_count=benefit_count,
            uptake_rate=uptake_rate,
            breakdown_by_gender=gender_breakdown,
            breakdown_by_institution_type=inst_breakdown,
            breakdown_by_caste_category=caste_breakdown,
            ineligibility_reasons_summary=ineligibility_reasons,
            state_distribution=state_distribution,
            individual_results=individual_results,
            assumptions_and_limitations=assumptions,
            policy_mode=resolved_mode,
            total_tuition_fee_relief_inr=total_tuition,
            total_exam_fee_relief_inr=total_exam,
            is_counterfactual=is_counterfactual,
            cohort_effective_relief_rate=cohort_effective_relief_rate
        )

    def run_multistep_cohort(
        self,
        personas: List[StudentPersona],
        total_steps: int = 2,
        cohort_name: str = "Dhule-10-Persona-Cohort",
        seed: Optional[int] = 42,
        assumed_reimbursement_rate: Optional[float] = None,
        enable_social_interaction: bool = True,
        max_connections_per_persona: int = 2,
        policy_mode: Optional[str] = None,
        policy_config: Optional[DTEPolicyConfig] = None
    ) -> "MultiStepSimulationResult":
        """
        Executes a multi-step simulation cycle over a persona cohort:
        For each step: Observe -> Reason -> Interact -> Act -> Update State.
        Supports policy_mode: 'legacy_poc', 'statutory', 'override', and 'counterfactual'.
        """
        from simulation.social_network import SyntheticSocialNetwork
        from simulation.interaction import InteractionRecord, InteractionTopic

        resolved_mode, resolved_rate, active_config, is_counterfactual = resolve_policy_parameters(
            "run_multistep_cohort",
            policy_mode=policy_mode,
            assumed_reimbursement_rate=assumed_reimbursement_rate,
            policy_config=policy_config
        )

        # 1. Initialize Synthetic Social Network
        network = SyntheticSocialNetwork(
            personas=personas,
            seed=seed,
            max_degree=max_connections_per_persona
        )

        persona_map: Dict[str, StudentPersona] = {p.persona_id: p for p in personas}
        interactions_by_step: Dict[int, List[Dict[str, Any]]] = {}
        step_cohort_results: List[CohortSimulationResult] = []

        # Record initial baseline state
        initial_states: Dict[str, Dict[str, Any]] = {
            p.persona_id: {
                "awareness": p.initial_awareness,
                "trust": p.institutional_trust,
                "document_readiness": p.document_readiness,
                "state": p.current_state.value
            }
            for p in personas
        }

        for step_idx in range(1, total_steps + 1):
            step_interactions: List[InteractionRecord] = []

            # A. OBSERVE: Evaluate deterministic statutory policy outcome
            policy_evals: Dict[str, PolicyEvaluationResult] = {
                p.persona_id: RajarshiShahuPolicyEngine.evaluate_eligibility(
                    persona=p,
                    config=active_config,
                    assumed_reimbursement_rate=resolved_rate
                )
                for p in personas
            }

            # B. REASON (Individual initial deliberation)
            agents: Dict[str, PersonaAgent] = {
                p.persona_id: PersonaAgent(persona=p, llm_provider=self.llm_provider)
                for p in personas
            }
            metrics_map: Dict[str, PersonaCalculatedMetrics] = {
                p.persona_id: agents[p.persona_id].compute_baseline_metrics(policy_evals[p.persona_id])
                for p in personas
            }

            # C. INTERACT (Peer-to-peer social communication & state diffusion)
            if enable_social_interaction:
                active_pairs = network.select_interactions_for_step(step_index=step_idx, seed=seed)
                for sender_id, receiver_id in active_pairs:
                    sender = persona_map[sender_id]
                    receiver = persona_map[receiver_id]

                    # Select plausible topic based on receiver state
                    if receiver.initial_awareness < 0.40:
                        topic = InteractionTopic.SCHEME_AWARENESS.value
                    elif receiver.document_readiness < 0.55:
                        topic = InteractionTopic.DOCUMENTATION_HURDLE.value
                    elif receiver.institutional_trust < 0.45:
                        topic = InteractionTopic.TRUST_AND_DISCOURAGEMENT.value
                    else:
                        topic = InteractionTopic.APPLICATION_GUIDANCE.value

                    sender_agent = agents[sender_id]
                    record = sender_agent.interact_with(
                        receiver=receiver,
                        sender_eval=policy_evals[sender_id],
                        receiver_eval=policy_evals[receiver_id],
                        topic=topic,
                        step_index=step_idx
                    )
                    step_interactions.append(record)

            interactions_by_step[step_idx] = [r.to_dict() for r in step_interactions]

            # D. ACT & E. UPDATE STATE (Recompute metrics after interactions)
            step_individual_outputs: List[SimulationStepOutput] = []
            for p in personas:
                agent = agents[p.persona_id]
                policy_eval = policy_evals[p.persona_id]

                if resolved_mode == "legacy_poc":
                    tuition_relief = policy_eval.tuition_fee_relief_inr
                    exam_relief = 0.0
                    total_relief = tuition_relief
                    eff_rate = 0.50 if policy_eval.is_eligible else 0.0
                else:
                    tuition_relief = policy_eval.tuition_fee_relief_inr
                    exam_relief = policy_eval.exam_fee_relief_inr
                    total_relief = policy_eval.estimated_fee_relief_inr
                    eff_rate = policy_eval.reimbursement_percentage

                updated_metrics = agent.compute_baseline_metrics(policy_eval)
                reasoning = agent.reason(policy_eval, updated_metrics)

                if not policy_eval.is_eligible:
                    new_state = SimulationState.REJECTED
                elif updated_metrics.final_benefit_received:
                    new_state = SimulationState.BENEFIT_RECEIVED
                elif updated_metrics.will_attempt_application:
                    new_state = SimulationState.APPLIED if updated_metrics.will_complete_application else SimulationState.COLLECTING_DOCUMENTS
                elif updated_metrics.awareness_score > 0.4:
                    new_state = SimulationState.EVALUATING
                else:
                    new_state = SimulationState.DROPPED_OUT

                p.current_state = new_state
                p.record_memory(
                    step=step_idx,
                    event_type="STEP_CYCLE_COMPLETED",
                    details={"state": new_state.value, "uptake": updated_metrics.expected_uptake_probability}
                )

                step_individual_outputs.append(
                    SimulationStepOutput(
                        persona_id=p.persona_id,
                        persona_name=p.name,
                        demographics_summary={
                            "age": p.age,
                            "gender": p.gender,
                            "district": p.district,
                            "family_income": p.family_income,
                            "caste_category": p.caste_category,
                            "course": p.course_name,
                            "institution_type": p.institution_type.value,
                            "admission_mode": p.admission_mode.value,
                            "annual_tuition_fee": p.annual_tuition_fee,
                            "first_generation_learner": p.first_generation_learner
                        },
                        scheme_name=policy_eval.scheme_name,
                        is_eligible=policy_eval.is_eligible,
                        reimbursement_percentage=eff_rate,
                        estimated_fee_relief_inr=total_relief,
                        statutory_failure_reasons=policy_eval.failure_reasons,
                        statutory_notes=policy_eval.statutory_notes,
                        benefit_assumptions=policy_eval.benefit_assumptions,
                        awareness_score=updated_metrics.awareness_score,
                        perceived_benefit_score=updated_metrics.perceived_benefit_score,
                        application_probability=updated_metrics.application_probability,
                        completion_probability=updated_metrics.completion_probability,
                        expected_uptake_probability=updated_metrics.expected_uptake_probability,
                        attempted_application=updated_metrics.will_attempt_application,
                        completed_application=updated_metrics.will_complete_application,
                        benefit_received=updated_metrics.final_benefit_received,
                        final_simulation_state=new_state.value,
                        inner_monologue=reasoning.inner_monologue,
                        stated_intention=reasoning.stated_intention,
                        perceived_barriers=reasoning.perceived_barriers,
                        chosen_action=reasoning.chosen_action,
                        confidence_level=reasoning.confidence_level,
                        tuition_fee_relief_inr=tuition_relief,
                        exam_fee_relief_inr=exam_relief,
                        policy_mode=resolved_mode,
                        is_counterfactual=is_counterfactual,
                        policy_result=policy_eval
                    )
                )

            # Compute step cohort aggregates
            step_cohort = self._aggregate_step_cohort(
                step_individual_outputs,
                cohort_name=f"{cohort_name}-Step{step_idx}",
                seed=seed,
                assumed_reimbursement_rate=resolved_rate,
                policy_mode=resolved_mode,
                is_counterfactual=is_counterfactual
            )
            step_cohort_results.append(step_cohort)

        # State evolution summary
        final_states: Dict[str, Dict[str, Any]] = {
            p.persona_id: {
                "initial_awareness": initial_states[p.persona_id]["awareness"],
                "final_awareness": p.initial_awareness,
                "awareness_gain": round(p.initial_awareness - initial_states[p.persona_id]["awareness"], 4),
                "initial_trust": initial_states[p.persona_id]["trust"],
                "final_trust": p.institutional_trust,
                "trust_delta": round(p.institutional_trust - initial_states[p.persona_id]["trust"], 4),
                "initial_state": initial_states[p.persona_id]["state"],
                "final_state": p.current_state.value
            }
            for p in personas
        }

        eff_assumed_rate = resolved_rate if resolved_rate is not None else step_cohort_results[-1].cohort_effective_relief_rate

        assumptions = [
            f"Policy mode evaluated: {resolved_mode} (is_counterfactual={is_counterfactual}).",
            f"Multi-step simulation executed across {total_steps} sequential cycle rounds.",
            f"Social interactions modeled over synthetic degree-bounded peer graph (seed={seed}).",
            f"Deterministic statutory policy evaluation remains authoritative at every step."
        ]

        return MultiStepSimulationResult(
            cohort_name=cohort_name,
            total_personas=len(personas),
            total_steps=total_steps,
            seed=seed,
            assumed_reimbursement_rate=eff_assumed_rate,
            network_summary=network.to_dict(),
            interactions_by_step=interactions_by_step,
            step_cohort_results=step_cohort_results,
            final_cohort_result=step_cohort_results[-1],
            state_evolution_summary=final_states,
            assumptions_and_limitations=assumptions,
            policy_mode=resolved_mode,
            is_counterfactual=is_counterfactual
        )

    def _aggregate_step_cohort(
        self,
        individual_results: List[SimulationStepOutput],
        cohort_name: str,
        seed: Optional[int],
        assumed_reimbursement_rate: Optional[float],
        policy_mode: str = "legacy_poc",
        is_counterfactual: bool = False
    ) -> CohortSimulationResult:
        """Helper to compute standard CohortSimulationResult from a list of SimulationStepOutputs."""
        total = len(individual_results)
        eligible_count = sum(1 for r in individual_results if r.is_eligible)
        ineligible_count = total - eligible_count
        eligibility_rate = round(eligible_count / total, 4) if total > 0 else 0.0

        total_relief = sum(r.estimated_fee_relief_inr for r in individual_results)
        total_tuition = sum(r.tuition_fee_relief_inr for r in individual_results)
        total_exam = sum(r.exam_fee_relief_inr for r in individual_results)
        avg_relief_eligible = round(total_relief / eligible_count, 2) if eligible_count > 0 else 0.0

        total_eligible_fees = sum(
            (r.demographics_summary.get("annual_tuition_fee", 0.0) + (r.policy_result.fee_breakdown.annual_exam_fee if r.policy_result and r.policy_result.fee_breakdown else 0.0))
            for r in individual_results if r.is_eligible
        )
        cohort_effective_relief_rate = round(total_relief / total_eligible_fees, 4) if total_eligible_fees > 0 else (
            round(sum(r.reimbursement_percentage for r in individual_results if r.is_eligible) / eligible_count, 4) if eligible_count > 0 else 0.0
        )

        avg_awareness = round(sum(r.awareness_score for r in individual_results) / total, 4) if total > 0 else 0.0
        avg_benefit = round(sum(r.perceived_benefit_score for r in individual_results) / total, 4) if total > 0 else 0.0
        avg_app_prob = round(sum(r.application_probability for r in individual_results) / total, 4) if total > 0 else 0.0
        avg_comp_prob = round(sum(r.completion_probability for r in individual_results) / total, 4) if total > 0 else 0.0
        avg_uptake_prob = round(sum(r.expected_uptake_probability for r in individual_results) / total, 4) if total > 0 else 0.0

        attempted_count = sum(1 for r in individual_results if r.attempted_application)
        completed_count = sum(1 for r in individual_results if r.completed_application)
        benefit_count = sum(1 for r in individual_results if r.benefit_received)
        uptake_rate = round(benefit_count / total, 4) if total > 0 else 0.0

        def compute_breakdown(key: str) -> Dict[str, Dict[str, Any]]:
            breakdown: Dict[str, Dict[str, Any]] = {}
            for r in individual_results:
                group_val = r.demographics_summary.get(key, "Unknown")
                if group_val not in breakdown:
                    breakdown[group_val] = {
                        "total_count": 0,
                        "eligible_count": 0,
                        "ineligible_count": 0,
                        "benefit_received_count": 0,
                        "total_relief_inr": 0.0
                    }
                breakdown[group_val]["total_count"] += 1
                if r.is_eligible:
                    breakdown[group_val]["eligible_count"] += 1
                else:
                    breakdown[group_val]["ineligible_count"] += 1
                if r.benefit_received:
                    breakdown[group_val]["benefit_received_count"] += 1
                breakdown[group_val]["total_relief_inr"] += r.estimated_fee_relief_inr

            for g, data in breakdown.items():
                tot_g = data["total_count"]
                data["eligibility_rate"] = round(data["eligible_count"] / tot_g, 4) if tot_g > 0 else 0.0
                data["uptake_rate"] = round(data["benefit_received_count"] / tot_g, 4) if tot_g > 0 else 0.0

            return breakdown

        ineligibility_reasons: Dict[str, int] = {}
        for r in individual_results:
            for reason in r.statutory_failure_reasons:
                ineligibility_reasons[reason] = ineligibility_reasons.get(reason, 0) + 1

        state_distribution: Dict[str, int] = {}
        for r in individual_results:
            state_distribution[r.final_simulation_state] = state_distribution.get(r.final_simulation_state, 0) + 1

        eff_assumed_rate = assumed_reimbursement_rate if assumed_reimbursement_rate is not None else cohort_effective_relief_rate

        assumptions = [
            f"Policy mode evaluated: {policy_mode} (is_counterfactual={is_counterfactual}).",
            f"Statutory rules based on official Rajarshi Shahu EBC criteria (Income <= 8L, CAP admission, attendance >= 75%).",
            f"Assumed fee reimbursement rate: {eff_assumed_rate * 100:.0f}%.",
            f"Demographic fields grounded in Dhule 2010-11 education data; behavioral traits dynamically updated via peer diffusion."
        ]

        return CohortSimulationResult(
            cohort_name=cohort_name,
            total_personas=total,
            seed=seed,
            assumed_reimbursement_rate=eff_assumed_rate,
            eligible_count=eligible_count,
            ineligible_count=ineligible_count,
            eligibility_rate=eligibility_rate,
            total_estimated_fee_relief_inr=total_relief,
            average_fee_relief_per_eligible_inr=avg_relief_eligible,
            average_awareness_score=avg_awareness,
            average_perceived_benefit_score=avg_benefit,
            average_application_probability=avg_app_prob,
            average_completion_probability=avg_comp_prob,
            average_expected_uptake_probability=avg_uptake_prob,
            attempted_application_count=attempted_count,
            completed_application_count=completed_count,
            benefit_received_count=benefit_count,
            uptake_rate=uptake_rate,
            breakdown_by_gender=compute_breakdown("gender"),
            breakdown_by_institution_type=compute_breakdown("institution_type"),
            breakdown_by_caste_category=compute_breakdown("caste_category"),
            ineligibility_reasons_summary=ineligibility_reasons,
            state_distribution=state_distribution,
            individual_results=individual_results,
            assumptions_and_limitations=assumptions,
            policy_mode=policy_mode,
            total_tuition_fee_relief_inr=total_tuition,
            total_exam_fee_relief_inr=total_exam,
            is_counterfactual=is_counterfactual,
            cohort_effective_relief_rate=cohort_effective_relief_rate
        )


@dataclass
class MultiStepSimulationResult:
    """Structured result of a multi-step simulation run including network dynamics and interaction history."""
    cohort_name: str
    total_personas: int
    total_steps: int
    seed: Optional[int]
    assumed_reimbursement_rate: float
    network_summary: Dict[str, Any]
    interactions_by_step: Dict[int, List[Dict[str, Any]]]
    step_cohort_results: List[CohortSimulationResult]
    final_cohort_result: CohortSimulationResult
    state_evolution_summary: Dict[str, Dict[str, Any]]
    assumptions_and_limitations: List[str] = field(default_factory=list)
    policy_mode: str = "legacy_poc"
    is_counterfactual: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return _safe_serialize(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)



