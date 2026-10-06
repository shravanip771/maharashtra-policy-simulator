from dataclasses import dataclass, asdict, field
from typing import Dict, List, Any, Optional
import json

from simulation.persona import StudentPersona, SimulationState
from simulation.policy_rules import RajarshiShahuPolicyEngine, PolicyEvaluationResult
from simulation.agent import PersonaAgent, PersonaCalculatedMetrics, PersonaReasoningOutput, BaseLLMProvider

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

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

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

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

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
        assumed_reimbursement_rate: Optional[float] = None
    ) -> SimulationStepOutput:
        """
        Executes a complete single-persona simulation cycle for the Rajarshi Shahu scheme.
        """
        agent = PersonaAgent(persona=persona, llm_provider=self.llm_provider)

        # 1. OBSERVE: Deterministic Policy Evaluation & Environment Perception
        policy_eval: PolicyEvaluationResult = RajarshiShahuPolicyEngine.evaluate_eligibility(
            persona, assumed_reimbursement_rate=assumed_reimbursement_rate
        )
        metrics: PersonaCalculatedMetrics = agent.compute_baseline_metrics(policy_eval)

        persona.record_memory(
            step=step_index,
            event_type="OBSERVE_POLICY",
            details={
                "is_eligible": policy_eval.is_eligible,
                "fee_relief": policy_eval.estimated_fee_relief_inr,
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
            reimbursement_percentage=policy_eval.reimbursement_percentage,
            estimated_fee_relief_inr=policy_eval.estimated_fee_relief_inr,
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
            confidence_level=reasoning.confidence_level
        )

    def run_cohort(
        self,
        personas: List[StudentPersona],
        cohort_name: str = "Dhule-10-Persona-Cohort",
        seed: Optional[int] = None,
        assumed_reimbursement_rate: Optional[float] = None
    ) -> CohortSimulationResult:
        """
        Executes individual simulations for each persona in a cohort and calculates
        comprehensive aggregate statistics, breakdowns, and barrier distributions.
        """
        individual_results: List[SimulationStepOutput] = []
        effective_rate = (
            assumed_reimbursement_rate
            if assumed_reimbursement_rate is not None
            else RajarshiShahuPolicyEngine.DEFAULT_POC_ASSUMED_REIMBURSEMENT_RATE
        )

        for p in personas:
            step_out = self.run_step(
                persona=p,
                step_index=1,
                assumed_reimbursement_rate=effective_rate
            )
            individual_results.append(step_out)

        total = len(individual_results)
        eligible_count = sum(1 for r in individual_results if r.is_eligible)
        ineligible_count = total - eligible_count
        eligibility_rate = round(eligible_count / total, 4) if total > 0 else 0.0

        total_relief = sum(r.estimated_fee_relief_inr for r in individual_results)
        avg_relief_eligible = round(total_relief / eligible_count, 2) if eligible_count > 0 else 0.0

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

        assumptions = [
            f"Statutory rules based on official Rajarshi Shahu EBC criteria (Income <= 8L, CAP admission, attendance >= 75%).",
            f"Assumed fee reimbursement rate: {effective_rate * 100:.0f}%. Note: actual departmental rules vary.",
            f"Demographic fields grounded in Dhule 2010-11 education data; income/caste/behavioral parameters use baseline priors."
        ]

        return CohortSimulationResult(
            cohort_name=cohort_name,
            total_personas=total,
            seed=seed,
            assumed_reimbursement_rate=effective_rate,
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
            assumptions_and_limitations=assumptions
        )

    def run_multistep_cohort(
        self,
        personas: List[StudentPersona],
        total_steps: int = 2,
        cohort_name: str = "Dhule-10-Persona-Cohort",
        seed: Optional[int] = 42,
        assumed_reimbursement_rate: Optional[float] = None,
        enable_social_interaction: bool = True,
        max_connections_per_persona: int = 2
    ) -> "MultiStepSimulationResult":
        """
        Executes a multi-step simulation cycle over a persona cohort:
        For each step: Observe -> Reason -> Interact -> Act -> Update State.
        """
        from simulation.social_network import SyntheticSocialNetwork
        from simulation.interaction import InteractionRecord, InteractionTopic

        effective_rate = (
            assumed_reimbursement_rate
            if assumed_reimbursement_rate is not None
            else RajarshiShahuPolicyEngine.DEFAULT_POC_ASSUMED_REIMBURSEMENT_RATE
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
                p.persona_id: RajarshiShahuPolicyEngine.evaluate_eligibility(p, assumed_reimbursement_rate=effective_rate)
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
                        reimbursement_percentage=policy_eval.reimbursement_percentage,
                        estimated_fee_relief_inr=policy_eval.estimated_fee_relief_inr,
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
                        confidence_level=reasoning.confidence_level
                    )
                )

            # Compute step cohort aggregates
            step_cohort = self._aggregate_step_cohort(
                step_individual_outputs,
                cohort_name=f"{cohort_name}-Step{step_idx}",
                seed=seed,
                assumed_reimbursement_rate=effective_rate
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

        assumptions = [
            f"Multi-step simulation executed across {total_steps} sequential cycle rounds.",
            f"Social interactions modeled over synthetic degree-bounded peer graph (seed={seed}).",
            f"Deterministic statutory policy evaluation remains authoritative at every step."
        ]

        return MultiStepSimulationResult(
            cohort_name=cohort_name,
            total_personas=len(personas),
            total_steps=total_steps,
            seed=seed,
            assumed_reimbursement_rate=effective_rate,
            network_summary=network.to_dict(),
            interactions_by_step=interactions_by_step,
            step_cohort_results=step_cohort_results,
            final_cohort_result=step_cohort_results[-1],
            state_evolution_summary=final_states,
            assumptions_and_limitations=assumptions
        )

    def _aggregate_step_cohort(
        self,
        individual_results: List[SimulationStepOutput],
        cohort_name: str,
        seed: Optional[int],
        assumed_reimbursement_rate: float
    ) -> CohortSimulationResult:
        """Helper to compute standard CohortSimulationResult from a list of SimulationStepOutputs."""
        total = len(individual_results)
        eligible_count = sum(1 for r in individual_results if r.is_eligible)
        ineligible_count = total - eligible_count
        eligibility_rate = round(eligible_count / total, 4) if total > 0 else 0.0

        total_relief = sum(r.estimated_fee_relief_inr for r in individual_results)
        avg_relief_eligible = round(total_relief / eligible_count, 2) if eligible_count > 0 else 0.0

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

        assumptions = [
            f"Statutory rules based on official Rajarshi Shahu EBC criteria (Income <= 8L, CAP admission, attendance >= 75%).",
            f"Assumed fee reimbursement rate: {assumed_reimbursement_rate * 100:.0f}%.",
            f"Demographic fields grounded in Dhule 2010-11 education data; behavioral traits dynamically updated via peer diffusion."
        ]

        return CohortSimulationResult(
            cohort_name=cohort_name,
            total_personas=total,
            seed=seed,
            assumed_reimbursement_rate=assumed_reimbursement_rate,
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
            assumptions_and_limitations=assumptions
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

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)


