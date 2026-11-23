from dataclasses import dataclass, asdict, field, fields
from typing import Dict, List, Any, Optional, Tuple, Union
import json
import math

from simulation.persona import StudentPersona, SimulationState
from simulation.policy_rules import RajarshiShahuPolicyEngine, PolicyEvaluationResult, DTEPolicyConfig
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

    # Granular DTE Policy Fee Relief & Metadata
    tuition_fee_relief_inr: float = 0.0
    exam_fee_relief_inr: float = 0.0
    annual_tuition_fee: float = 0.0
    annual_exam_fee: float = 0.0
    net_payable_tuition_fee: float = 0.0
    net_payable_exam_fee: float = 0.0
    total_net_payable_fee: float = 0.0
    policy_mode: str = "legacy_poc"
    policy_version: str = "2024.1-provisional"
    is_provisional: bool = True

    def __post_init__(self):
        if self.net_payable_tuition_fee == 0.0 and self.annual_tuition_fee > self.tuition_fee_relief_inr:
            self.net_payable_tuition_fee = round(max(0.0, self.annual_tuition_fee - self.tuition_fee_relief_inr), 2)
        if self.net_payable_exam_fee == 0.0 and self.annual_exam_fee > self.exam_fee_relief_inr:
            self.net_payable_exam_fee = round(max(0.0, self.annual_exam_fee - self.exam_fee_relief_inr), 2)
        if self.total_net_payable_fee == 0.0 and (self.annual_tuition_fee + self.annual_exam_fee) > self.estimated_fee_relief_inr:
            self.total_net_payable_fee = round(max(0.0, (self.annual_tuition_fee + self.annual_exam_fee) - self.estimated_fee_relief_inr), 2)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["net_payable_tuition_fee"] = self.net_payable_tuition_fee
        d["net_payable_exam_fee"] = self.net_payable_exam_fee
        d["total_net_payable_fee"] = self.total_net_payable_fee
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

@dataclass
class CohortSimulationResult:
    """Structured aggregate result of a multi-persona population simulation."""
    cohort_name: str
    total_personas: int
    seed: Optional[int]
    assumed_reimbursement_rate: Optional[float]

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

    # Granular DTE Fee Relief & Policy Metadata
    total_tuition_fee_relief_inr: float = 0.0
    total_exam_fee_relief_inr: float = 0.0
    total_net_payable_tuition_fee_inr: float = 0.0
    total_net_payable_exam_fee_inr: float = 0.0
    total_net_payable_fee_inr: float = 0.0
    policy_mode: str = "legacy_poc"
    policy_version: str = "2024.1-provisional"
    is_provisional: bool = True

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["total_net_payable_tuition_fee_inr"] = self.total_net_payable_tuition_fee_inr
        d["total_net_payable_exam_fee_inr"] = self.total_net_payable_exam_fee_inr
        d["total_net_payable_fee_inr"] = self.total_net_payable_fee_inr
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)


def _build_counterfactual_config(cfg_input: Any) -> DTEPolicyConfig:
    """Validates and converts a dictionary or DTEPolicyConfig into a verified DTEPolicyConfig instance."""
    if cfg_input is None:
        return RajarshiShahuPolicyEngine.DEFAULT_CONFIG
    if isinstance(cfg_input, DTEPolicyConfig):
        cfg = cfg_input
    elif isinstance(cfg_input, dict):
        valid_fields = {f.name for f in fields(DTEPolicyConfig)}
        unknown = set(cfg_input.keys()) - valid_fields
        if unknown:
            raise ValueError(f"Invalid counterfactual parameter(s): {sorted(unknown)}")
        base = asdict(RajarshiShahuPolicyEngine.DEFAULT_CONFIG)
        base.update(cfg_input)
        cfg = DTEPolicyConfig(**base)
    else:
        raise TypeError(f"counterfactual_config must be a dict or DTEPolicyConfig instance, got {type(cfg_input).__name__}")

    # Validate numeric fields on cfg (applies identically to dict conversion and DTEPolicyConfig instances)
    if isinstance(cfg.max_income_limit, bool):
        raise ValueError("max_income_limit cannot be a boolean value.")
    if not isinstance(cfg.max_income_limit, (int, float)):
        raise ValueError("max_income_limit must be a numeric value.")
    if math.isnan(cfg.max_income_limit) or math.isinf(cfg.max_income_limit):
        raise ValueError(f"max_income_limit must be a finite number, got {cfg.max_income_limit}.")
    if cfg.max_income_limit < 0:
        raise ValueError(f"max_income_limit cannot be negative ({cfg.max_income_limit}).")

    if isinstance(cfg.income_slab_lower, bool):
        raise ValueError("income_slab_lower cannot be a boolean value.")
    if not isinstance(cfg.income_slab_lower, (int, float)):
        raise ValueError("income_slab_lower must be a numeric value.")
    if math.isnan(cfg.income_slab_lower) or math.isinf(cfg.income_slab_lower):
        raise ValueError(f"income_slab_lower must be a finite number, got {cfg.income_slab_lower}.")
    if cfg.income_slab_lower < 0:
        raise ValueError(f"income_slab_lower cannot be negative ({cfg.income_slab_lower}).")

    if isinstance(cfg.min_attendance_percent, bool):
        raise ValueError("min_attendance_percent cannot be a boolean value.")
    if not isinstance(cfg.min_attendance_percent, (int, float)):
        raise ValueError("min_attendance_percent must be a numeric value.")
    if math.isnan(cfg.min_attendance_percent) or math.isinf(cfg.min_attendance_percent):
        raise ValueError(f"min_attendance_percent must be a finite number, got {cfg.min_attendance_percent}.")
    if not (0.0 <= cfg.min_attendance_percent <= 100.0):
        raise ValueError(f"min_attendance_percent must be between 0.0 and 100.0, got {cfg.min_attendance_percent}.")

    if isinstance(cfg.institutional_attendance_threshold, bool):
        raise ValueError("institutional_attendance_threshold cannot be a boolean value.")
    if not isinstance(cfg.institutional_attendance_threshold, (int, float)):
        raise ValueError("institutional_attendance_threshold must be a numeric value.")
    if math.isnan(cfg.institutional_attendance_threshold) or math.isinf(cfg.institutional_attendance_threshold):
        raise ValueError(f"institutional_attendance_threshold must be a finite number, got {cfg.institutional_attendance_threshold}.")
    if not (0.0 <= cfg.institutional_attendance_threshold <= 100.0):
        raise ValueError(f"institutional_attendance_threshold must be between 0.0 and 100.0, got {cfg.institutional_attendance_threshold}.")

    if isinstance(cfg.max_family_beneficiaries, bool):
        raise ValueError("max_family_beneficiaries cannot be a boolean value.")
    if not isinstance(cfg.max_family_beneficiaries, (int, float)):
        raise ValueError("max_family_beneficiaries must be a numeric value.")
    if math.isnan(cfg.max_family_beneficiaries) or math.isinf(cfg.max_family_beneficiaries):
        raise ValueError(f"max_family_beneficiaries must be a finite number, got {cfg.max_family_beneficiaries}.")
    if cfg.max_family_beneficiaries < 0:
        raise ValueError(f"max_family_beneficiaries cannot be negative ({cfg.max_family_beneficiaries}).")

    if isinstance(cfg.max_permissible_gap_years, bool):
        raise ValueError("max_permissible_gap_years cannot be a boolean value.")
    if not isinstance(cfg.max_permissible_gap_years, (int, float)):
        raise ValueError("max_permissible_gap_years must be a numeric value.")
    if math.isnan(cfg.max_permissible_gap_years) or math.isinf(cfg.max_permissible_gap_years):
        raise ValueError(f"max_permissible_gap_years must be a finite number, got {cfg.max_permissible_gap_years}.")
    if cfg.max_permissible_gap_years < 0:
        raise ValueError(f"max_permissible_gap_years cannot be negative ({cfg.max_permissible_gap_years}).")

    rate_fields = [
        "female_tuition_rate", "female_exam_rate", "orphan_tuition_rate", "orphan_exam_rate",
        "male_tier1_govt_tuition_rate", "male_tier1_pvt_tuition_rate", "male_tier2_tuition_rate", "male_exam_rate",
        "default_poc_rate"
    ]
    for rate_field in rate_fields:
        r = getattr(cfg, rate_field, None)
        if r is not None:
            if isinstance(r, bool):
                raise ValueError(f"{rate_field} cannot be a boolean value.")
            if not isinstance(r, (int, float)):
                raise ValueError(f"{rate_field} must be a numeric value.")
            if math.isnan(r) or math.isinf(r):
                raise ValueError(f"{rate_field} must be a finite number, got {r}.")
            if not (0.0 <= r <= 1.0):
                raise ValueError(f"{rate_field} must be between 0.0 and 1.0, got {r}.")

    bool_fields = ["use_strict_institutional_attendance", "enable_female_100_percent_rule", "enable_orphan_100_percent_rule"]
    for b_field in bool_fields:
        b_val = getattr(cfg, b_field, None)
        if b_val is not None and not isinstance(b_val, bool):
            raise ValueError(f"{b_field} must be a boolean, got {type(b_val).__name__}.")

    return cfg


def resolve_policy_parameters(
    policy_mode: Optional[str] = "legacy_poc",
    override_reimbursement_rate: Optional[float] = None,
    assumed_reimbursement_rate: Optional[float] = None,
    counterfactual_config: Optional[Any] = None,
) -> Tuple[str, Optional[float], Optional[Any]]:
    """
    Resolves policy evaluation mode, effective reimbursement rate, and policy configuration.

    Modes:
      - 'legacy_poc': Applies legacy flat 50% reimbursement rate (default when omitted).
      - 'statutory': Applies statutory DTE rules with deterministic criteria and fee itemization.
      - 'override': Applies explicit uniform override rate (requires override_reimbursement_rate in [0.0, 1.0]).
      - 'counterfactual': Applies counterfactual/what-if configuration parameters.

    Aliases:
      - 'poc_legacy' -> 'legacy_poc'
      - 'statutory_dte' -> 'statutory'
    """
    if override_reimbursement_rate is not None:
        if isinstance(override_reimbursement_rate, bool):
            raise ValueError("override_reimbursement_rate cannot be a boolean value.")
        if not isinstance(override_reimbursement_rate, (int, float)):
            raise ValueError("override_reimbursement_rate must be a numeric value.")
        if math.isnan(override_reimbursement_rate) or math.isinf(override_reimbursement_rate):
            raise ValueError("override_reimbursement_rate must be a finite number.")

    if assumed_reimbursement_rate is not None:
        if isinstance(assumed_reimbursement_rate, bool):
            raise ValueError("assumed_reimbursement_rate cannot be a boolean value.")
        if not isinstance(assumed_reimbursement_rate, (int, float)):
            raise ValueError("assumed_reimbursement_rate must be a numeric value.")
        if math.isnan(assumed_reimbursement_rate) or math.isinf(assumed_reimbursement_rate):
            raise ValueError("assumed_reimbursement_rate must be a finite number.")

    raw_mode = (policy_mode or "").strip().lower() if policy_mode is not None else ""

    # Alias resolution & normalization
    if raw_mode in ("", "legacy_poc", "poc_legacy"):
        mode = "legacy_poc"
    elif raw_mode in ("statutory", "statutory_dte"):
        mode = "statutory"
    elif raw_mode == "override":
        mode = "override"
    elif raw_mode == "counterfactual":
        mode = "counterfactual"
    else:
        raise ValueError(
            f"Unknown policy_mode '{policy_mode}'. Supported modes: 'legacy_poc', 'statutory', 'override', 'counterfactual'."
        )

    # 1. Counterfactual mode validation
    if mode == "counterfactual":
        if override_reimbursement_rate is not None:
            raise ValueError(
                "override_reimbursement_rate cannot be specified in 'counterfactual' mode. "
                "Counterfactual evaluations configure policy parameters, not uniform override rates."
            )
        if assumed_reimbursement_rate is not None:
            raise ValueError(
                "assumed_reimbursement_rate cannot be specified in 'counterfactual' mode. "
                "Counterfactual evaluations configure policy parameters, not uniform override rates."
            )
        cfg = _build_counterfactual_config(counterfactual_config)
        return "counterfactual", None, cfg

    # 2. Statutory mode validation
    if mode == "statutory":
        if override_reimbursement_rate is not None:
            raise ValueError("override_reimbursement_rate cannot be specified in 'statutory' mode. Use policy_mode='override'.")
        if assumed_reimbursement_rate is not None:
            raise ValueError("assumed_reimbursement_rate cannot be specified in 'statutory' mode. Use policy_mode='override'.")
        return "statutory", None, RajarshiShahuPolicyEngine.DEFAULT_CONFIG

    # 3. Explicit override mode
    if mode == "override":
        rate = override_reimbursement_rate if override_reimbursement_rate is not None else assumed_reimbursement_rate
        if rate is None:
            raise ValueError("override_reimbursement_rate must be provided when policy_mode is 'override'.")
        if not (0.0 <= rate <= 1.0):
            raise ValueError(f"override_reimbursement_rate must be between 0.0 and 1.0, got {rate}.")
        return mode, float(rate), None

    # 4. Legacy PoC mode (mode == "legacy_poc")
    if override_reimbursement_rate is not None:
        if not (0.0 <= override_reimbursement_rate <= 1.0):
            raise ValueError(f"override_reimbursement_rate must be between 0.0 and 1.0, got {override_reimbursement_rate}.")
        return "override", float(override_reimbursement_rate), None

    if assumed_reimbursement_rate is not None:
        if not (0.0 <= assumed_reimbursement_rate <= 1.0):
            raise ValueError(f"assumed_reimbursement_rate must be between 0.0 and 1.0, got {assumed_reimbursement_rate}.")
        return "override", float(assumed_reimbursement_rate), None

    return "legacy_poc", RajarshiShahuPolicyEngine.DEFAULT_POC_ASSUMED_REIMBURSEMENT_RATE, None


# Backward compatibility alias
resolve_policy_mode_and_rate = resolve_policy_parameters


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
        policy_mode: Optional[str] = "legacy_poc",
        override_reimbursement_rate: Optional[float] = None,
        counterfactual_config: Optional[Any] = None,
    ) -> SimulationStepOutput:
        """
        Executes a complete single-persona simulation cycle for the Rajarshi Shahu scheme.
        Supports explicit policy_mode ('legacy_poc', 'statutory', 'override', 'counterfactual').
        """
        agent = PersonaAgent(persona=persona, llm_provider=self.llm_provider)

        resolved_mode, effective_rate, eval_config = resolve_policy_parameters(
            policy_mode=policy_mode,
            override_reimbursement_rate=override_reimbursement_rate,
            assumed_reimbursement_rate=assumed_reimbursement_rate,
            counterfactual_config=counterfactual_config,
        )

        # 1. OBSERVE: Deterministic Policy Evaluation & Environment Perception
        policy_eval: PolicyEvaluationResult = RajarshiShahuPolicyEngine.evaluate_eligibility(
            persona, assumed_reimbursement_rate=effective_rate, config=eval_config
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
                "annual_exam_fee": getattr(persona, "annual_exam_fee", 0.0),
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
            confidence_level=reasoning.confidence_level,
            tuition_fee_relief_inr=policy_eval.tuition_fee_relief_inr,
            exam_fee_relief_inr=policy_eval.exam_fee_relief_inr,
            annual_tuition_fee=getattr(persona, "annual_tuition_fee", 0.0),
            annual_exam_fee=getattr(persona, "annual_exam_fee", 0.0),
            net_payable_tuition_fee=round(max(0.0, getattr(persona, "annual_tuition_fee", 0.0) - policy_eval.tuition_fee_relief_inr), 2),
            net_payable_exam_fee=round(max(0.0, getattr(persona, "annual_exam_fee", 0.0) - policy_eval.exam_fee_relief_inr), 2),
            total_net_payable_fee=round(max(0.0, (getattr(persona, "annual_tuition_fee", 0.0) + getattr(persona, "annual_exam_fee", 0.0)) - policy_eval.estimated_fee_relief_inr), 2),
            policy_mode=resolved_mode,
            policy_version=policy_eval.policy_version,
            is_provisional=(resolved_mode in ("statutory", "counterfactual") and policy_eval.verification_status == "PROVISIONAL")
        )

    def run_cohort(
        self,
        personas: List[StudentPersona],
        cohort_name: str = "Dhule-10-Persona-Cohort",
        seed: Optional[int] = None,
        assumed_reimbursement_rate: Optional[float] = None,
        policy_mode: Optional[str] = "legacy_poc",
        override_reimbursement_rate: Optional[float] = None,
        counterfactual_config: Optional[Any] = None,
    ) -> CohortSimulationResult:
        """
        Executes individual simulations for each persona in a cohort and calculates
        comprehensive aggregate statistics, breakdowns, and barrier distributions.
        Supports explicit policy_mode ('legacy_poc', 'statutory', 'override', 'counterfactual').
        """
        resolved_mode, effective_rate, eval_config = resolve_policy_parameters(
            policy_mode=policy_mode,
            override_reimbursement_rate=override_reimbursement_rate,
            assumed_reimbursement_rate=assumed_reimbursement_rate,
            counterfactual_config=counterfactual_config,
        )

        individual_results: List[SimulationStepOutput] = []
        for p in personas:
            step_out = self.run_step(
                persona=p,
                step_index=1,
                assumed_reimbursement_rate=effective_rate,
                policy_mode=resolved_mode,
                override_reimbursement_rate=override_reimbursement_rate,
                counterfactual_config=eval_config,
            )
            individual_results.append(step_out)

        total = len(individual_results)
        eligible_count = sum(1 for r in individual_results if r.is_eligible)
        ineligible_count = total - eligible_count
        eligibility_rate = round(eligible_count / total, 4) if total > 0 else 0.0

        total_relief = sum(r.estimated_fee_relief_inr for r in individual_results)
        total_tuition_relief = sum(r.tuition_fee_relief_inr for r in individual_results)
        total_exam_relief = sum(r.exam_fee_relief_inr for r in individual_results)
        total_net_tuition = sum(r.net_payable_tuition_fee for r in individual_results)
        total_net_exam = sum(r.net_payable_exam_fee for r in individual_results)
        total_net_fee = sum(r.total_net_payable_fee for r in individual_results)
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

        if resolved_mode == "statutory":
            rate_desc = "Statutory DTE Rules (2024.1-provisional; female/orphan 100% waiver, tiered male rates)"
        elif resolved_mode == "counterfactual":
            cfg_ver = eval_config.policy_version if eval_config else "custom"
            rate_desc = f"Counterfactual Policy Scenario ({cfg_ver})"
        elif effective_rate is not None:
            rate_desc = f"Assumed fee reimbursement rate: {effective_rate * 100:.0f}%. Note: actual departmental rules vary."
        else:
            rate_desc = "Statutory DTE Rules"

        assumptions = [
            f"Statutory rules based on official Rajarshi Shahu EBC criteria (Income <= 8L, CAP admission, attendance >= 50% for continuing students, first-year exempt).",
            rate_desc,
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
            assumptions_and_limitations=assumptions,
            total_tuition_fee_relief_inr=round(total_tuition_relief, 2),
            total_exam_fee_relief_inr=round(total_exam_relief, 2),
            total_net_payable_tuition_fee_inr=round(total_net_tuition, 2),
            total_net_payable_exam_fee_inr=round(total_net_exam, 2),
            total_net_payable_fee_inr=round(total_net_fee, 2),
            policy_mode=resolved_mode,
            policy_version=eval_config.policy_version if eval_config else ("2024.1-provisional" if resolved_mode == "statutory" else ("legacy-poc" if resolved_mode == "legacy_poc" else "override")),
            is_provisional=(resolved_mode in ("statutory", "counterfactual"))
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
        session: Optional[Any] = None,
        run_id: Optional[str] = None,
        policy_id: Optional[int] = None,
        policy_config_id: Optional[int] = None,
        policy_mode: Optional[str] = "legacy_poc",
        override_reimbursement_rate: Optional[float] = None,
        counterfactual_config: Optional[Any] = None,
    ) -> "MultiStepSimulationResult":
        """
        Executes a multi-step simulation cycle over a persona cohort:
        For each step: Observe -> Reason -> Interact -> Act -> Administrative Lifecycle -> Update State.
        Supports optional relational database and lifecycle service persistence when session is provided.
        Supports explicit policy_mode ('legacy_poc', 'statutory', 'override', 'counterfactual').
        """
        from simulation.social_network import SyntheticSocialNetwork
        from simulation.interaction import InteractionRecord, InteractionTopic

        resolved_mode, effective_rate, eval_config = resolve_policy_parameters(
            policy_mode=policy_mode,
            override_reimbursement_rate=override_reimbursement_rate,
            assumed_reimbursement_rate=assumed_reimbursement_rate,
            counterfactual_config=counterfactual_config,
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
        lifecycle_apps: Dict[str, Any] = {}
        lifecycle_step_advancement: Dict[str, int] = {}

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
                    p, assumed_reimbursement_rate=effective_rate, config=eval_config
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
                updated_metrics = agent.compute_baseline_metrics(policy_eval)
                reasoning = agent.reason(policy_eval, updated_metrics)

                # Connect administrative application lifecycle if database session and policy context exist
                if session is not None and policy_id is not None and policy_config_id is not None:
                    from backend.lifecycle_service import (
                        create_application,
                        submit_application,
                        start_desk_scrutiny,
                        record_eligibility_evaluation,
                        approve_application,
                        disburse_benefit,
                        reject_application,
                        ApplicationEvaluationStage,
                        EvaluationActor,
                    )

                    app_rec = lifecycle_apps.get(p.persona_id)

                    # 1. Citizen initiates application upon sufficient awareness / document collection
                    if app_rec is None:
                        if (
                            updated_metrics.will_attempt_application
                            or p.current_state in (
                                SimulationState.COLLECTING_DOCUMENTS,
                                SimulationState.APPLIED,
                                SimulationState.BENEFIT_RECEIVED,
                            )
                            or (updated_metrics.awareness_score >= 0.45 and p.document_readiness >= 0.50)
                        ):
                            app_rec = create_application(
                                session=session,
                                persona_id=p.persona_id,
                                policy_id=policy_id,
                                evaluation_policy_config_id=policy_config_id,
                                claimed_fee_relief_inr=policy_eval.estimated_fee_relief_inr,
                                is_eligible=policy_eval.is_eligible,
                                ineligibility_reasons=policy_eval.failure_reasons,
                                run_id=run_id,
                                evaluation_notes=f"Application initiated at simulation step {step_idx}",
                            )
                            lifecycle_apps[p.persona_id] = app_rec
                            lifecycle_step_advancement[p.persona_id] = step_idx
                            # A newly created application MUST remain DRAFT for this step.
                    else:
                        # Application was created in a previous step; advance only in subsequent steps
                        last_advanced_step = lifecycle_step_advancement.get(p.persona_id, 0)
                        if step_idx > last_advanced_step:
                            current_status = app_rec.current_status

                            # DRAFT -> SUBMITTED (Citizen files completed application in subsequent step)
                            if current_status == "DRAFT":
                                if updated_metrics.will_complete_application or not policy_eval.is_eligible:
                                    app_rec = submit_application(
                                        session=session,
                                        application_id=app_rec.id,
                                        remarks=f"Application submitted via MahaDBT portal at step {step_idx}",
                                    )
                                    lifecycle_apps[p.persona_id] = app_rec
                                    lifecycle_step_advancement[p.persona_id] = step_idx

                            # SUBMITTED -> UNDER_VERIFICATION (Desk scrutiny commenced in subsequent step)
                            elif current_status == "SUBMITTED":
                                app_rec = start_desk_scrutiny(
                                    session=session,
                                    application_id=app_rec.id,
                                    remarks=f"Desk scrutiny commenced by verification officer at step {step_idx}",
                                )
                                lifecycle_apps[p.persona_id] = app_rec
                                lifecycle_step_advancement[p.persona_id] = step_idx

                            # UNDER_VERIFICATION -> APPROVED / REJECTED (Statutory evaluation in subsequent step)
                            elif current_status == "UNDER_VERIFICATION":
                                if policy_eval.is_eligible:
                                    record_eligibility_evaluation(
                                        session=session,
                                        application_id=app_rec.id,
                                        evaluation_stage=ApplicationEvaluationStage.DESK_SCRUTINY,
                                        is_eligible=True,
                                        policy_config_id=policy_config_id,
                                        evaluated_by=EvaluationActor.SCRUTINY_OFFICER,
                                        evaluation_notes=f"Step {step_idx} statutory eligibility compliance verified",
                                    )
                                    app_rec = approve_application(
                                        session=session,
                                        application_id=app_rec.id,
                                        remarks=f"Approved under statutory eligibility criteria at step {step_idx}",
                                        approved_amount=policy_eval.estimated_fee_relief_inr,
                                    )
                                else:
                                    record_eligibility_evaluation(
                                        session=session,
                                        application_id=app_rec.id,
                                        evaluation_stage=ApplicationEvaluationStage.DESK_SCRUTINY,
                                        is_eligible=False,
                                        policy_config_id=policy_config_id,
                                        evaluated_by=EvaluationActor.SCRUTINY_OFFICER,
                                        failure_reasons=policy_eval.failure_reasons,
                                        evaluation_notes=f"Step {step_idx} statutory requirements not satisfied",
                                    )
                                    app_rec = reject_application(
                                        session=session,
                                        application_id=app_rec.id,
                                        reason=f"Ineligible at step {step_idx}: {', '.join(policy_eval.failure_reasons)}",
                                    )
                                lifecycle_apps[p.persona_id] = app_rec
                                lifecycle_step_advancement[p.persona_id] = step_idx

                            # APPROVED -> BENEFIT_DISBURSED (Financial DBT execution in subsequent step)
                            elif current_status == "APPROVED":
                                if updated_metrics.final_benefit_received and policy_eval.is_eligible:
                                    payment_ref = f"DBT-MH-{p.persona_id[-6:]}-S{step_idx}"
                                    app_rec = disburse_benefit(
                                        session=session,
                                        application_id=app_rec.id,
                                        disbursed_amount=policy_eval.estimated_fee_relief_inr,
                                        payment_reference=payment_ref,
                                    )
                                    lifecycle_apps[p.persona_id] = app_rec
                                    lifecycle_step_advancement[p.persona_id] = step_idx

                    # Derive realized behavioral state strictly confirmed by administrative lifecycle
                    if app_rec is not None:
                        if app_rec.current_status == "BENEFIT_DISBURSED":
                            new_state = SimulationState.BENEFIT_RECEIVED
                            act_attempted = True
                            act_completed = True
                            act_benefit = True
                        elif app_rec.current_status == "REJECTED":
                            new_state = SimulationState.REJECTED
                            act_attempted = True
                            act_completed = True
                            act_benefit = False
                        elif app_rec.current_status in ("APPROVED", "UNDER_VERIFICATION", "RESUBMITTED", "SUBMITTED"):
                            new_state = SimulationState.APPLIED
                            act_attempted = True
                            act_completed = True
                            act_benefit = False
                        elif app_rec.current_status == "DRAFT":
                            new_state = SimulationState.COLLECTING_DOCUMENTS
                            act_attempted = True
                            act_completed = False
                            act_benefit = False
                        else:
                            new_state = SimulationState.DROPPED_OUT
                            act_attempted = False
                            act_completed = False
                            act_benefit = False
                    else:
                        if not policy_eval.is_eligible:
                            new_state = SimulationState.REJECTED
                            act_attempted = False
                            act_completed = False
                            act_benefit = False
                        elif updated_metrics.awareness_score > 0.4:
                            new_state = SimulationState.EVALUATING
                            act_attempted = False
                            act_completed = False
                            act_benefit = False
                        else:
                            new_state = SimulationState.DROPPED_OUT
                            act_attempted = False
                            act_completed = False
                            act_benefit = False
                else:
                    # In-memory heuristic simulation without persistence
                    if not policy_eval.is_eligible:
                        new_state = SimulationState.REJECTED
                        act_attempted = False
                        act_completed = False
                        act_benefit = False
                    elif updated_metrics.final_benefit_received:
                        new_state = SimulationState.BENEFIT_RECEIVED
                        act_attempted = True
                        act_completed = True
                        act_benefit = True
                    elif updated_metrics.will_attempt_application:
                        new_state = SimulationState.APPLIED if updated_metrics.will_complete_application else SimulationState.COLLECTING_DOCUMENTS
                        act_attempted = True
                        act_completed = updated_metrics.will_complete_application
                        act_benefit = False
                    elif updated_metrics.awareness_score > 0.4:
                        new_state = SimulationState.EVALUATING
                        act_attempted = False
                        act_completed = False
                        act_benefit = False
                    else:
                        new_state = SimulationState.DROPPED_OUT
                        act_attempted = False
                        act_completed = False
                        act_benefit = False

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
                            "annual_exam_fee": getattr(p, "annual_exam_fee", 0.0),
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
                        attempted_application=act_attempted,
                        completed_application=act_completed,
                        benefit_received=act_benefit,
                        final_simulation_state=new_state.value,
                        inner_monologue=reasoning.inner_monologue,
                        stated_intention=reasoning.stated_intention,
                        perceived_barriers=reasoning.perceived_barriers,
                        chosen_action=reasoning.chosen_action,
                        confidence_level=reasoning.confidence_level,
                        tuition_fee_relief_inr=policy_eval.tuition_fee_relief_inr,
                        exam_fee_relief_inr=policy_eval.exam_fee_relief_inr,
                        annual_tuition_fee=getattr(p, "annual_tuition_fee", 0.0),
                        annual_exam_fee=getattr(p, "annual_exam_fee", 0.0),
                        net_payable_tuition_fee=round(max(0.0, getattr(p, "annual_tuition_fee", 0.0) - policy_eval.tuition_fee_relief_inr), 2),
                        net_payable_exam_fee=round(max(0.0, getattr(p, "annual_exam_fee", 0.0) - policy_eval.exam_fee_relief_inr), 2),
                        total_net_payable_fee=round(max(0.0, (getattr(p, "annual_tuition_fee", 0.0) + getattr(p, "annual_exam_fee", 0.0)) - policy_eval.estimated_fee_relief_inr), 2),
                        policy_mode=resolved_mode,
                        policy_version=policy_eval.policy_version,
                        is_provisional=(resolved_mode in ("statutory", "counterfactual") and policy_eval.verification_status == "PROVISIONAL")
                    )
                )

            # Compute step cohort aggregates
            step_cohort = self._aggregate_step_cohort(
                step_individual_outputs,
                cohort_name=f"{cohort_name}-Step{step_idx}",
                seed=seed,
                assumed_reimbursement_rate=effective_rate,
                policy_mode=resolved_mode,
                policy_version=eval_config.policy_version if eval_config else ("2024.1-provisional" if resolved_mode == "statutory" else ("legacy-poc" if resolved_mode == "legacy_poc" else "override"))
            )
            step_cohort_results.append(step_cohort)

            # Record step temporal state in database if session is provided
            if session is not None and run_id is not None:
                from backend.simulation_persistence import SimulationPersistenceAdapter
                SimulationPersistenceAdapter.record_step_snapshot(
                    session=session,
                    run_id=run_id,
                    step_number=step_idx,
                    personas=personas,
                    step_outputs=step_individual_outputs,
                    interactions=interactions_by_step[step_idx],
                    step_cohort=step_cohort
                )

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

        # Record final individual outcomes in database if session is provided
        if session is not None and run_id is not None:
            from backend.simulation_persistence import SimulationPersistenceAdapter
            SimulationPersistenceAdapter.record_final_outcomes(
                session=session,
                run_id=run_id,
                individual_results=step_cohort_results[-1].individual_results
            )

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
        assumed_reimbursement_rate: Optional[float] = None,
        policy_mode: str = "legacy_poc",
        policy_version: str = "2024.1-provisional"
    ) -> CohortSimulationResult:
        """Helper to compute standard CohortSimulationResult from a list of SimulationStepOutputs."""
        total = len(individual_results)
        eligible_count = sum(1 for r in individual_results if r.is_eligible)
        ineligible_count = total - eligible_count
        eligibility_rate = round(eligible_count / total, 4) if total > 0 else 0.0

        total_relief = sum(r.estimated_fee_relief_inr for r in individual_results)
        total_tuition_relief = sum(r.tuition_fee_relief_inr for r in individual_results)
        total_exam_relief = sum(r.exam_fee_relief_inr for r in individual_results)
        total_net_tuition = sum(r.net_payable_tuition_fee for r in individual_results)
        total_net_exam = sum(r.net_payable_exam_fee for r in individual_results)
        total_net_fee = sum(r.total_net_payable_fee for r in individual_results)
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

        if policy_mode == "statutory":
            rate_desc = "Statutory DTE Rules (2024.1-provisional; female/orphan 100% waiver, tiered male rates)"
        elif policy_mode == "counterfactual":
            rate_desc = f"Counterfactual Policy Scenario ({policy_version})"
        elif policy_mode == "override":
            rate_desc = f"Explicit override reimbursement rate: {assumed_reimbursement_rate * 100:.0f}%."
        else:
            rate_desc = f"Legacy PoC Baseline (assumed uniform rate: {assumed_reimbursement_rate * 100:.0f}%)."

        assumptions = [
            f"Statutory rules based on official Rajarshi Shahu EBC criteria (Income <= 8L, CAP admission, attendance >= 50% for continuing students, first-year exempt).",
            rate_desc,
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
            assumptions_and_limitations=assumptions,
            total_tuition_fee_relief_inr=round(total_tuition_relief, 2),
            total_exam_fee_relief_inr=round(total_exam_relief, 2),
            total_net_payable_tuition_fee_inr=round(total_net_tuition, 2),
            total_net_payable_exam_fee_inr=round(total_net_exam, 2),
            total_net_payable_fee_inr=round(total_net_fee, 2),
            policy_mode=policy_mode,
            policy_version=policy_version,
            is_provisional=(policy_mode in ("statutory", "counterfactual"))
        )


@dataclass
class MultiStepSimulationResult:
    """Structured result of a multi-step simulation run including network dynamics and interaction history."""
    cohort_name: str
    total_personas: int
    total_steps: int
    seed: Optional[int]
    assumed_reimbursement_rate: Optional[float]
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


