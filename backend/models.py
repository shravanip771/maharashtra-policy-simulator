"""
Backend API Models: Pydantic schemas for the Maharashtra Policy Simulator.
Enforces the explicit Phase A data contract between Python simulation and React frontend.
"""

from typing import Dict, List, Any, Optional, Union
from pydantic import BaseModel, Field


class SimulationRequest(BaseModel):
    """Configuration payload to trigger a multi-step cohort simulation."""
    district: str = Field(default="Dhule", description="Target district for demographic baseline, or 'STATEWIDE' for all 36 districts")
    cohort_size: Optional[int] = Field(
        default=None,
        description="Optional cohort size; automatically determined from configured district allocation if omitted"
    )
    cohort_size_per_district: Optional[int] = Field(
        default=None,
        description="Optional personas per district (legacy field)"
    )
    simulation_steps: int = Field(default=2, ge=1, le=5, description="Number of sequential simulation rounds")
    seed: int = Field(default=42, description="Random seed for deterministic reproducibility")
    use_gemini: bool = Field(default=False, description="Whether to invoke live Gemini API (defaults to offline stub)")
    gemini_model: str = Field(default="gemini-3.1-flash-lite", description="Gemini model identifier when use_gemini is True")
    policy_mode: Optional[str] = Field(default=None, description="Optional policy mode: legacy_poc, statutory, override, counterfactual")
    assumed_reimbursement_rate: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Optional override reimbursement rate [0.0, 1.0]")


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
    assumed_reimbursement_rate: float
    data_disclaimer: str
    requested_policy_mode: Optional[str] = None
    resolved_policy_mode: str = "legacy_poc"
    is_counterfactual: bool = False
    policy_version: str = "2024.1-provisional"
    epistemic_status: str = "provisional"


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
    total_tuition_fee_relief_inr: Optional[float] = None
    total_exam_fee_relief_inr: Optional[float] = None
    cohort_effective_relief_rate: Optional[float] = None


class DistrictSummaryDTO(BaseModel):
    """Aggregated metrics and demographic summary for one district sliced from a statewide simulation run."""
    district_name: str
    district_code: Optional[str] = None
    division: Optional[str] = None
    provenance_tier: Optional[str] = None
    total_personas: int
    eligible_count: int
    ineligible_count: int
    eligibility_rate: float
    mean_awareness: float
    mean_perceived_benefit: Optional[float] = None
    mean_application_probability: float
    expected_uptake_probability: Optional[float] = None
    realized_uptake_count: int
    realized_uptake_rate: float
    total_estimated_fee_relief_inr: float
    average_fee_relief_per_eligible_inr: float
    talukas_represented: Optional[List[str]] = None


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

    # Interaction History
    interaction_history: List[InteractionRecordDTO] = Field(
        default_factory=list,
        description="Chronological peer interaction records involving this persona"
    )

    # Optional Fee & Policy Fields
    reimbursement_rate: float = 0.0
    tuition_fee_relief_inr: Optional[float] = None
    exam_fee_relief_inr: Optional[float] = None
    policy_details: Optional[Dict[str, Any]] = None


class FeaturedPersonaDTO(PersonaOutput):
    """Profile, decision trace, and peer conversation history for a featured persona."""
    pass


class SimulationResponse(BaseModel):
    """Complete response payload delivered to the frontend dashboard."""
    metadata: SimulationMetadata
    provenance_breakdown: ProvenanceBreakdown
    aggregate_metrics: AggregateMetrics
    step_metrics: List[StepMetric]
    network_topology: NetworkTopology
    personas: List[FeaturedPersonaDTO] = Field(
        ...,
        description="Featured personas sampled deterministically for UI display"
    )
    interactions: List[InteractionRecordDTO] = Field(
        default_factory=list,
        description="Interaction records involving the featured personas"
    )
    featured_personas: Optional[List[FeaturedPersonaDTO]] = Field(
        default=None,
        description="Featured personas with interaction histories (alias for personas)"
    )
    is_statewide: bool = False
    district_summaries: Optional[Dict[str, Any]] = None


class StatewideCohortResponse(BaseModel):
    """Payload for the statewide 1,000-student cohort across Maharashtra districts."""
    total_count: int = Field(..., description="Total number of personas generated across the state")
    district_allocations: Dict[str, int] = Field(..., description="Configured quota allocation per district")
    missing_district: Optional[str] = Field(default=None, description="Any omitted district if applicable")
    seed: int = Field(default=42, description="Random seed used for deterministic generation")
    personas: List[PersonaOutput] = Field(..., description="List of generated personas with baseline policy evaluation")


class StatewideSimulationRequest(BaseModel):
    """Configuration payload to trigger a statewide 1,000-persona multi-step simulation."""
    simulation_steps: int = Field(default=2, ge=1, le=5, description="Number of sequential simulation rounds")
    seed: int = Field(default=42, description="Random seed for deterministic statewide generation and sampling")
    use_gemini: bool = Field(default=False, description="Whether to invoke live Gemini API (defaults to offline stub)")
    gemini_model: str = Field(default="gemini-3.1-flash-lite", description="Gemini model identifier when use_gemini is True")


class DistrictSimulationResultDTO(BaseModel):
    """Aggregated policy metrics for an individual district within the statewide cohort."""
    district_name: str
    allocated_personas: int
    eligible_count: int
    ineligible_count: int
    eligibility_rate: float
    attempted_applications: int
    completed_applications: int
    realized_beneficiaries: int
    uptake_rate: float
    total_estimated_fee_relief_inr: float
    average_relief_per_eligible_inr: float
    mean_awareness: float
    mean_application_probability: float


class StatewideSimulationSummaryDTO(BaseModel):
    """Statewide macro KPIs aggregated across all 1,000 simulated student personas."""
    total_personas: int
    eligible_count: int
    ineligible_count: int
    eligibility_rate: float
    mean_initial_awareness: float
    mean_final_awareness: float
    mean_awareness_gain: float
    mean_perceived_benefit: float
    mean_application_probability: float
    expected_uptake_probability: float
    attempted_applications_count: int
    completed_applications_count: int
    realized_beneficiaries_count: int
    realized_uptake_rate: float
    total_estimated_fee_relief_inr: float
    average_fee_relief_per_eligible_inr: float
    ineligibility_reasons_summary: Dict[str, int]
    simulation_state_distribution: Dict[str, int]
    top_application_barriers: Dict[str, int]
    step_metrics: List[StepMetric]


class StatewideSimulationMetadataDTO(BaseModel):
    """System provenance and operational metadata for the statewide run."""
    run_id: str
    seed: int
    simulation_steps: int
    scheme_name: str
    scheme_code: str
    total_districts_configured: int
    total_personas_processed: int
    llm_provider: str
    completion_status: str
    assumed_reimbursement_rate: float
    data_disclaimer: str


class StatewideSimulationResponse(BaseModel):
    """Complete response payload for the statewide 1,000-persona simulation."""
    simulation_summary: StatewideSimulationSummaryDTO
    district_results: List[DistrictSimulationResultDTO]
    featured_personas: List[FeaturedPersonaDTO]
    simulation_metadata: StatewideSimulationMetadataDTO
    interactions: List[InteractionRecordDTO] = Field(
        default_factory=list,
        description="Interaction records involving the featured personas"
    )
    # Compatibility fields for frontend contract
    is_statewide: bool = True
    aggregate_metrics: Optional[Dict[str, Any]] = None
    personas: Optional[List[FeaturedPersonaDTO]] = None
    district_summaries: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
