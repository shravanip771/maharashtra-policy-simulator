"""
Backend API Models: Pydantic schemas for the Maharashtra Policy Simulator.
Enforces the explicit Phase A data contract between Python simulation and React frontend.
"""

from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field


class SimulationRequest(BaseModel):
    """Configuration payload to trigger a multi-step cohort simulation."""
    district: str = Field(default="Dhule", description="Target district for demographic baseline")
    cohort_size: int = Field(default=10, ge=1, le=50, description="Number of synthetic personas to simulate")
    simulation_steps: int = Field(default=2, ge=1, le=5, description="Number of sequential simulation rounds")
    seed: int = Field(default=42, description="Random seed for deterministic reproducibility")
    use_gemini: bool = Field(default=False, description="Whether to invoke live Gemini API (defaults to offline stub)")
    gemini_model: str = Field(default="gemini-3.1-flash-lite", description="Gemini model identifier when use_gemini is True")


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
