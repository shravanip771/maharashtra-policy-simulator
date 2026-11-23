"""
Backend API Models: Pydantic schemas for the Maharashtra Policy Simulator.
Enforces the explicit Phase A data contract between Python simulation and React frontend.
"""

import math
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class CounterfactualPolicyParams(BaseModel):
    """Configurable parameters for counterfactual 'what-if' policy scenarios."""
    max_income_limit: Optional[float] = Field(default=800000.0, ge=0.0, description="Annual family income ceiling in INR")
    income_slab_lower: Optional[float] = Field(default=250000.0, ge=0.0, description="Lower income slab for 100% male govt/aided concession")
    min_attendance_percent: Optional[float] = Field(default=50.0, ge=0.0, le=100.0, description="Statutory minimum attendance percentage")
    institutional_attendance_threshold: Optional[float] = Field(default=75.0, ge=0.0, le=100.0, description="Institutional term-end attendance threshold")
    enable_female_100_percent_rule: Optional[bool] = Field(default=True, description="Enable 100% waiver for female students")
    female_tuition_rate: Optional[float] = Field(default=1.00, ge=0.0, le=1.0, description="Female tuition reimbursement rate")
    female_exam_rate: Optional[float] = Field(default=1.00, ge=0.0, le=1.0, description="Female exam reimbursement rate")
    male_tier1_govt_tuition_rate: Optional[float] = Field(default=1.00, ge=0.0, le=1.0, description="Male tier-1 govt tuition rate")
    male_tier1_pvt_tuition_rate: Optional[float] = Field(default=0.50, ge=0.0, le=1.0, description="Male tier-1 private unaided tuition rate")
    male_tier2_tuition_rate: Optional[float] = Field(default=0.50, ge=0.0, le=1.0, description="Male tier-2 tuition rate")
    male_exam_rate: Optional[float] = Field(default=0.50, ge=0.0, le=1.0, description="Male exam reimbursement rate")
    policy_label: Optional[str] = Field(default="Counterfactual Scenario", description="Scenario descriptive label")

    @field_validator(
        "max_income_limit", "income_slab_lower", "min_attendance_percent",
        "institutional_attendance_threshold", "female_tuition_rate",
        "female_exam_rate", "male_tier1_govt_tuition_rate",
        "male_tier1_pvt_tuition_rate", "male_tier2_tuition_rate",
        "male_exam_rate",
        mode="before"
    )
    @classmethod
    def reject_bool_and_non_finite_params(cls, v: Any, info) -> Any:
        if v is None:
            return v
        if isinstance(v, bool):
            raise ValueError(f"{info.field_name} cannot be a boolean value.")
        if isinstance(v, (int, float)):
            if math.isnan(v) or math.isinf(v):
                raise ValueError(f"{info.field_name} must be a finite number.")
        return v


class SimulationRequest(BaseModel):
    """Configuration payload to trigger a multi-step cohort simulation."""
    district: str = Field(default="Dhule", description="Target district for demographic baseline")
    cohort_size: int = Field(default=10, ge=1, le=50, description="Number of synthetic personas to simulate")
    simulation_steps: int = Field(default=2, ge=1, le=5, description="Number of sequential simulation rounds")
    seed: int = Field(default=42, description="Random seed for deterministic reproducibility")
    use_gemini: bool = Field(default=False, description="Whether to invoke live Gemini API (defaults to offline stub)")
    gemini_model: str = Field(default="gemini-3.1-flash-lite", description="Gemini model identifier when use_gemini is True")
    policy_mode: Optional[str] = Field(default="legacy_poc", description="Policy evaluation mode: 'legacy_poc', 'statutory', 'override', or 'counterfactual'")
    override_reimbursement_rate: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Uniform override reimbursement rate (required when policy_mode='override')")
    assumed_reimbursement_rate: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Alternative/legacy parameter for override_reimbursement_rate")
    counterfactual_params: Optional[CounterfactualPolicyParams] = Field(default=None, description="Configurable policy parameters for 'counterfactual' mode")
    counterfactual_config: Optional[Dict[str, Any]] = Field(default=None, description="Alternative dictionary payload for counterfactual policy parameters")

    @field_validator("district")
    @classmethod
    def validate_supported_district(cls, v: Any) -> str:
        if v is None:
            return "Dhule"
        if not isinstance(v, str) or not v.strip():
            raise ValueError("District name must be a non-empty string.")
        from simulation.district_config import list_supported_districts
        supported = list_supported_districts()
        matched = next((d for d in supported if d.lower() == v.strip().lower()), None)
        if not matched:
            raise ValueError(
                f"District '{v}' is not supported. Supported districts: {', '.join(supported)}"
            )
        return matched

    @field_validator("override_reimbursement_rate", "assumed_reimbursement_rate", mode="before")
    @classmethod
    def reject_bool_override_rate(cls, v: Any, info) -> Any:
        if v is None:
            return v
        if isinstance(v, bool):
            raise ValueError(f"{info.field_name} cannot be a boolean value.")
        if isinstance(v, (int, float)):
            if math.isnan(v) or math.isinf(v):
                raise ValueError(f"{info.field_name} must be a finite number.")
        return v

    @model_validator(mode="after")
    def validate_counterfactual_inputs(self) -> "SimulationRequest":
        if self.counterfactual_params is not None and self.counterfactual_config is not None:
            raise ValueError(
                "Cannot supply both 'counterfactual_params' and 'counterfactual_config'. Please provide only one."
            )
        return self

    @model_validator(mode="after")
    def validate_reimbursement_rate_inputs(self) -> "SimulationRequest":
        if self.override_reimbursement_rate is not None and self.assumed_reimbursement_rate is not None:
            if self.override_reimbursement_rate != self.assumed_reimbursement_rate:
                raise ValueError(
                    f"Conflicting reimbursement rates supplied: 'override_reimbursement_rate' ({self.override_reimbursement_rate}) "
                    f"and 'assumed_reimbursement_rate' ({self.assumed_reimbursement_rate}) cannot differ. "
                    f"Please provide matching values or specify only one."
                )
        return self


class SimulationMetadata(BaseModel):
    """Metadata describing the active scheme, scope, model, and epistemic boundaries."""
    scheme_name: str
    scheme_code: str
    district: str
    cohort_size: int
    simulation_steps: int
    seed: int
    llm_provider: str
    is_synthetic_poc: bool
    assumed_reimbursement_rate: Optional[float] = None
    data_disclaimer: str
    policy_mode: str = "legacy_poc"
    policy_version: str = "2024.1-provisional"
    is_provisional: bool = True
    provisional_notes: List[str] = Field(default_factory=list)


class ProvenanceBreakdown(BaseModel):
    """Epistemic transparency classification for all simulated attributes."""
    grounded_reference_fields: List[str]
    derived_fields: List[str]
    synthetic_behavioral_priors: List[str]
    poc_assumptions: List[str]


class AggregateMetrics(BaseModel):
    """High-level cohort policy outcomes and financial metrics."""
    total_personas: int
    eligible_count: int
    ineligible_count: int
    eligibility_rate: float
    mean_awareness: float
    mean_perceived_benefit: float
    mean_application_probability: float
    expected_uptake_probability: float
    realized_uptake_count: int
    realized_uptake_rate: float
    total_estimated_fee_relief_inr: float
    average_fee_relief_per_eligible_inr: float
    total_tuition_fee_relief_inr: float = 0.0
    total_exam_fee_relief_inr: float = 0.0
    total_net_payable_tuition_fee_inr: float = 0.0
    total_net_payable_exam_fee_inr: float = 0.0
    total_net_payable_fee_inr: float = 0.0
    policy_mode: str = "legacy_poc"
    policy_version: str = "2024.1-provisional"
    is_provisional: bool = True
    provisional_notes: List[str] = Field(default_factory=list)


class StepMetric(BaseModel):
    """Metrics snapshot at a single simulation round."""
    step_number: int
    eligible_count: int
    mean_awareness: float
    mean_perceived_benefit: float
    mean_application_probability: float
    expected_uptake_probability: float
    realized_uptake_count: int
    interaction_count: int


class NetworkTopology(BaseModel):
    """Summary of the synthetic degree-bounded social graph."""
    total_nodes: int
    total_edges: int
    max_degree_limit: int
    adjacency_list: Dict[str, List[str]]


class PersonaOutput(BaseModel):
    """Complete profile, decision trace, and state for one simulated citizen."""
    persona_id: str
    name: str
    gender: str
    age: int
    district: str
    taluka: str
    course_name: str
    is_professional_course: bool
    institution_type: str
    admission_mode: str
    caste_category: str
    family_income: float
    annual_tuition_fee: float
    attendance_percentage: float
    previous_year_passed: bool
    first_generation_learner: bool

    # Statutory Policy Result
    is_statutorily_eligible: bool
    estimated_fee_relief_inr: float
    statutory_failure_reasons: List[str]
    annual_exam_fee: float = 0.0
    tuition_fee_relief_inr: float = 0.0
    exam_fee_relief_inr: float = 0.0
    net_payable_tuition_fee: float = 0.0
    net_payable_exam_fee: float = 0.0
    total_net_payable_fee: float = 0.0
    policy_version: str = "2024.1-provisional"
    is_provisional: bool = True
    provisional_notes: List[str] = Field(default_factory=list)

    # Behavioral & Probabilistic Metrics
    initial_awareness: float
    final_awareness: float
    awareness_gain: float
    initial_trust: float
    final_trust: float
    digital_literacy: float
    document_readiness: float
    application_probability: float
    completion_probability: float
    final_state: str

    # AI Reasoning & Explanations
    stated_intention: str
    major_barriers: List[str]
    inner_monologue: str


class InteractionRecordDTO(BaseModel):
    """Structured dialogue and state transition record for peer interactions."""
    simulation_step: int
    sender_id: str
    sender_name: str
    receiver_id: str
    receiver_name: str
    interaction_topic: str
    sender_message: str
    receiver_response: str
    state_changed: bool
    state_changes: Dict[str, Any]


class SimulationResponse(BaseModel):
    """Complete response payload delivered to the frontend dashboard."""
    metadata: SimulationMetadata
    provenance_breakdown: ProvenanceBreakdown
    aggregate_metrics: AggregateMetrics
    step_metrics: List[StepMetric]
    network_topology: NetworkTopology
    personas: List[PersonaOutput]
    interactions: List[InteractionRecordDTO]
