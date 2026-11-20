"""
SQLAlchemy ORM Models for Maharashtra Policy Simulator.
Faithfully implements the approved database schema specification in docs/database_schema.md.
Follows modern SQLAlchemy 2.0 Mapped typing patterns, declarative constraints, and explicit deletion guards.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


# -----------------------------------------------------------------------------
# 1. Custom TypeDecorators: UTCDateTime
# -----------------------------------------------------------------------------
class UTCDateTime(TypeDecorator):
    """
    Ensures datetimes are stored in UTC in SQLite and always retrieved
    as timezone-aware UTC datetime objects.
    """
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: Optional[datetime], dialect: Any) -> Optional[datetime]:
        if value is not None:
            if not isinstance(value, datetime):
                raise TypeError(f"Expected datetime object, got {type(value)}")
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            else:
                value = value.astimezone(timezone.utc)
            return value.replace(tzinfo=None)
        return None

    def process_result_value(self, value: Optional[datetime], dialect: Any) -> Optional[datetime]:
        if value is not None:
            return value.replace(tzinfo=timezone.utc)
        return None


# -----------------------------------------------------------------------------
# 2. Status & Enumeration Types (Inherit from (str, Enum))
# -----------------------------------------------------------------------------
class ApplicationLifecycleStatus(str, Enum):
    """Administrative status of a formal student scholarship application."""
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_VERIFICATION = "UNDER_VERIFICATION"
    SENT_BACK_FOR_CORRECTION = "SENT_BACK_FOR_CORRECTION"
    RESUBMITTED = "RESUBMITTED"
    APPROVED = "APPROVED"
    BENEFIT_DISBURSED = "BENEFIT_DISBURSED"
    REJECTED = "REJECTED"
    REVOKED = "REVOKED"
    ABANDONED = "ABANDONED"


class SimulationRunStatus(str, Enum):
    """Execution status of a simulation batch run."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class SimulationState(str, Enum):
    """Cognitive behavioral state of a synthetic citizen persona."""
    UNINFORMED = "UNINFORMED"
    AWARE = "AWARE"
    EVALUATING = "EVALUATING"
    COLLECTING_DOCUMENTS = "COLLECTING_DOCUMENTS"
    APPLIED = "APPLIED"
    BENEFIT_RECEIVED = "BENEFIT_RECEIVED"
    REJECTED = "REJECTED"
    DROPPED_OUT = "DROPPED_OUT"


class ApplicationEvaluationStage(str, Enum):
    """Formal administrative stage at which an eligibility evaluation occurs."""
    INITIAL_ASSESSMENT = "INITIAL_ASSESSMENT"
    DESK_SCRUTINY = "DESK_SCRUTINY"
    RESUBMISSION_RE_EVALUATION = "RESUBMISSION_RE_EVALUATION"
    POST_SANCTION_AUDIT = "POST_SANCTION_AUDIT"


class EvaluationActor(str, Enum):
    """Actor performing an eligibility evaluation."""
    SYSTEM_ENGINE = "SYSTEM_ENGINE"
    SCRUTINY_OFFICER = "SCRUTINY_OFFICER"
    AUDIT_OFFICER = "AUDIT_OFFICER"


class AuditActor(str, Enum):
    """Actor performing an administrative lifecycle state transition."""
    STUDENT = "STUDENT"
    SCRUTINY_OFFICER = "SCRUTINY_OFFICER"
    DISBURSEMENT_OFFICER = "DISBURSEMENT_OFFICER"
    SYSTEM_ENGINE = "SYSTEM_ENGINE"


class ConfidenceLevel(str, Enum):
    """Qualitative confidence level reported by AI persona reasoning."""
    HIGH = "High"
    MODERATE = "Moderate"
    LOW = "Low"


# -----------------------------------------------------------------------------
# 3. ORM Models (10 Core Entities + 2 Supporting Tables)
# -----------------------------------------------------------------------------

class PolicyDB(Base):
    """Entity 1: Policies / Schemes catalog."""
    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scheme_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    scheme_name: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[str] = mapped_column(String(255), nullable=False)
    target_beneficiary: Mapped[str] = mapped_column(String(255), nullable=False)
    official_portal_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    configurations: Mapped[List[PolicyConfigurationDB]] = relationship(
        "PolicyConfigurationDB",
        back_populates="policy",
        cascade="save-update, merge",
        passive_deletes=True
    )
    applications: Mapped[List[ApplicationRecordDB]] = relationship(
        "ApplicationRecordDB",
        back_populates="policy",
        cascade="save-update, merge",
        passive_deletes=True
    )
    simulation_runs: Mapped[List[SimulationRunDB]] = relationship(
        "SimulationRunDB",
        back_populates="policy",
        cascade="save-update, merge",
        passive_deletes=True
    )


class PolicyConfigurationDB(Base):
    """Entity 2: Versioned statutory eligibility parameters and financial relief rules."""
    __tablename__ = "policy_configurations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_id: Mapped[int] = mapped_column(Integer, ForeignKey("policies.id", ondelete="RESTRICT"), nullable=False)
    config_version: Mapped[str] = mapped_column(String(50), nullable=False)
    policy_source_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    max_income_limit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    min_attendance_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    baseline_relief_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_family_beneficiaries: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    allows_concurrent_scholarship: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_cap_admission: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    scheme_rules_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    is_verified_statutory_rule: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("policy_id", "config_version", name="uq_policy_configurations_policy_version"),
    )

    # Relationships
    policy: Mapped[PolicyDB] = relationship("PolicyDB", back_populates="configurations")
    simulation_runs: Mapped[List[SimulationRunDB]] = relationship(
        "SimulationRunDB",
        back_populates="policy_config",
        cascade="save-update, merge",
        passive_deletes=True
    )
    initial_applications: Mapped[List[ApplicationRecordDB]] = relationship(
        "ApplicationRecordDB",
        foreign_keys="ApplicationRecordDB.evaluation_policy_config_id",
        back_populates="evaluation_policy_config",
        cascade="save-update, merge",
        passive_deletes=True
    )
    verified_applications: Mapped[List[ApplicationRecordDB]] = relationship(
        "ApplicationRecordDB",
        foreign_keys="ApplicationRecordDB.latest_verification_policy_config_id",
        back_populates="latest_verification_policy_config",
        cascade="save-update, merge",
        passive_deletes=True
    )
    evaluations: Mapped[List[ApplicationEligibilityEvaluationDB]] = relationship(
        "ApplicationEligibilityEvaluationDB",
        back_populates="policy_config",
        cascade="save-update, merge",
        passive_deletes=True
    )


class SyntheticPersonaDB(Base):
    """Entity 3: Persistent catalog of synthetic citizen personas."""
    __tablename__ = "synthetic_personas"

    persona_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    gender: Mapped[str] = mapped_column(String(32), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    district: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    taluka: Mapped[str] = mapped_column(String(100), nullable=False)
    is_maharashtra_domicile: Mapped[bool] = mapped_column(Boolean, nullable=False)
    caste_category: Mapped[str] = mapped_column(String(50), nullable=False)
    family_income: Mapped[float] = mapped_column(Float, nullable=False)
    first_generation_learner: Mapped[bool] = mapped_column(Boolean, nullable=False)
    parental_education_level: Mapped[str] = mapped_column(String(50), nullable=False)
    course_name: Mapped[str] = mapped_column(String(150), nullable=False)
    course_level: Mapped[str] = mapped_column(String(50), nullable=False)
    is_professional_course: Mapped[bool] = mapped_column(Boolean, nullable=False)
    institution_type: Mapped[str] = mapped_column(String(50), nullable=False)
    admission_mode: Mapped[str] = mapped_column(String(50), nullable=False)
    annual_tuition_fee: Mapped[float] = mapped_column(Float, nullable=False)
    attendance_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    previous_year_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    previous_year_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    academic_gap_years: Mapped[int] = mapped_column(Integer, nullable=False)
    family_beneficiaries_count: Mapped[int] = mapped_column(Integer, nullable=False)
    has_other_scholarship: Mapped[bool] = mapped_column(Boolean, nullable=False)
    digital_literacy: Mapped[float] = mapped_column(Float, nullable=False)
    initial_awareness: Mapped[float] = mapped_column(Float, nullable=False)
    document_readiness: Mapped[float] = mapped_column(Float, nullable=False)
    financial_urgency: Mapped[float] = mapped_column(Float, nullable=False)
    peer_network_support: Mapped[float] = mapped_column(Float, nullable=False)
    institutional_trust: Mapped[float] = mapped_column(Float, nullable=False)
    personality_traits_json: Mapped[Any] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    run_states: Mapped[List[PersonaRunStateDB]] = relationship(
        "PersonaRunStateDB",
        back_populates="persona",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    sent_interactions: Mapped[List[PersonaInteractionDB]] = relationship(
        "PersonaInteractionDB",
        foreign_keys="PersonaInteractionDB.sender_id",
        back_populates="sender",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    received_interactions: Mapped[List[PersonaInteractionDB]] = relationship(
        "PersonaInteractionDB",
        foreign_keys="PersonaInteractionDB.receiver_id",
        back_populates="receiver",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    outcomes: Mapped[List[IndividualOutcomeDB]] = relationship(
        "IndividualOutcomeDB",
        back_populates="persona",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    applications: Mapped[List[ApplicationRecordDB]] = relationship(
        "ApplicationRecordDB",
        back_populates="persona",
        cascade="save-update, merge",
        passive_deletes=True
    )


class ScenarioConfigurationDB(Base):
    """Entity 4: Counterfactual policy experiments and behavioral interventions."""
    __tablename__ = "scenario_configurations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario_name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    awareness_campaign_boost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    document_helpdesk_boost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    income_cap_override: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    attendance_threshold_override: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    simulation_runs: Mapped[List[SimulationRunDB]] = relationship(
        "SimulationRunDB",
        back_populates="scenario_config",
        cascade="save-update, merge",
        passive_deletes=True
    )


class SimulationRunDB(Base):
    """Entity 5: Audit log of every executed simulation run with reproducibility parameters."""
    __tablename__ = "simulation_runs"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    policy_id: Mapped[int] = mapped_column(Integer, ForeignKey("policies.id", ondelete="RESTRICT"), nullable=False)
    policy_config_id: Mapped[int] = mapped_column(Integer, ForeignKey("policy_configurations.id", ondelete="RESTRICT"), nullable=False)
    scenario_config_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("scenario_configurations.id", ondelete="SET NULL"), nullable=True)
    population_config_name: Mapped[str] = mapped_column(String(100), nullable=False)
    population_data_version: Mapped[str] = mapped_column(String(50), nullable=False)
    software_version: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    district: Mapped[str] = mapped_column(String(100), nullable=False)
    population_size: Mapped[int] = mapped_column(Integer, nullable=False)
    random_seed: Mapped[int] = mapped_column(Integer, nullable=False)
    simulation_steps: Mapped[int] = mapped_column(Integer, nullable=False)
    llm_provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    execution_timestamp: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True, default=lambda: datetime.now(timezone.utc))
    completion_timestamp: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    run_status: Mapped[str] = mapped_column(String(32), nullable=False)
    status_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "run_status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')",
            name="check_simulation_run_status"
        ),
    )

    # Relationships
    policy: Mapped[PolicyDB] = relationship("PolicyDB", back_populates="simulation_runs")
    policy_config: Mapped[PolicyConfigurationDB] = relationship("PolicyConfigurationDB", back_populates="simulation_runs")
    scenario_config: Mapped[Optional[ScenarioConfigurationDB]] = relationship("ScenarioConfigurationDB", back_populates="simulation_runs")
    persona_states: Mapped[List[PersonaRunStateDB]] = relationship(
        "PersonaRunStateDB",
        back_populates="simulation_run",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    interactions: Mapped[List[PersonaInteractionDB]] = relationship(
        "PersonaInteractionDB",
        back_populates="simulation_run",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    individual_outcomes: Mapped[List[IndividualOutcomeDB]] = relationship(
        "IndividualOutcomeDB",
        back_populates="simulation_run",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    aggregate_results: Mapped[List[AggregateResultDB]] = relationship(
        "AggregateResultDB",
        back_populates="simulation_run",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    application_records: Mapped[List[ApplicationRecordDB]] = relationship(
        "ApplicationRecordDB",
        back_populates="simulation_run",
        cascade="save-update, merge",
        passive_deletes=True
    )


class PersonaRunStateDB(Base):
    """Entity 6: Temporal state snapshot of each persona at each simulation step."""
    __tablename__ = "persona_run_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("simulation_runs.run_id", ondelete="CASCADE"), nullable=False)
    persona_id: Mapped[str] = mapped_column(String(64), ForeignKey("synthetic_personas.persona_id", ondelete="CASCADE"), nullable=False)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    awareness_score: Mapped[float] = mapped_column(Float, nullable=False)
    trust_score: Mapped[float] = mapped_column(Float, nullable=False)
    document_readiness_score: Mapped[float] = mapped_column(Float, nullable=False)
    peer_network_support: Mapped[float] = mapped_column(Float, nullable=False)
    application_probability: Mapped[float] = mapped_column(Float, nullable=False)
    completion_probability: Mapped[float] = mapped_column(Float, nullable=False)
    expected_uptake_probability: Mapped[float] = mapped_column(Float, nullable=False)
    simulation_state: Mapped[str] = mapped_column(String(50), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("run_id", "persona_id", "step_number", name="uq_persona_run_states_run_persona_step"),
        CheckConstraint(
            "simulation_state IN ('UNINFORMED', 'AWARE', 'EVALUATING', 'COLLECTING_DOCUMENTS', 'APPLIED', 'BENEFIT_RECEIVED', 'REJECTED', 'DROPPED_OUT')",
            name="check_prs_simulation_state"
        ),
    )

    # Relationships
    simulation_run: Mapped[SimulationRunDB] = relationship("SimulationRunDB", back_populates="persona_states")
    persona: Mapped[SyntheticPersonaDB] = relationship("SyntheticPersonaDB", back_populates="run_states")


class PersonaInteractionDB(Base):
    """Entity 7: Word-of-mouth dialogue and state diffusion logs across the social graph."""
    __tablename__ = "persona_interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("simulation_runs.run_id", ondelete="CASCADE"), nullable=False)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    sender_id: Mapped[str] = mapped_column(String(64), ForeignKey("synthetic_personas.persona_id", ondelete="CASCADE"), nullable=False)
    receiver_id: Mapped[str] = mapped_column(String(64), ForeignKey("synthetic_personas.persona_id", ondelete="CASCADE"), nullable=False)
    interaction_topic: Mapped[str] = mapped_column(String(100), nullable=False)
    sender_message: Mapped[str] = mapped_column(Text, nullable=False)
    receiver_response: Mapped[str] = mapped_column(Text, nullable=False)
    state_changed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    state_changes_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    simulation_run: Mapped[SimulationRunDB] = relationship("SimulationRunDB", back_populates="interactions")
    sender: Mapped[SyntheticPersonaDB] = relationship(
        "SyntheticPersonaDB",
        foreign_keys=[sender_id],
        back_populates="sent_interactions"
    )
    receiver: Mapped[SyntheticPersonaDB] = relationship(
        "SyntheticPersonaDB",
        foreign_keys=[receiver_id],
        back_populates="received_interactions"
    )


class IndividualOutcomeDB(Base):
    """Entity 8: Final policy evaluation, realization outcome, and AI monologue per persona."""
    __tablename__ = "individual_outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("simulation_runs.run_id", ondelete="CASCADE"), nullable=False)
    persona_id: Mapped[str] = mapped_column(String(64), ForeignKey("synthetic_personas.persona_id", ondelete="CASCADE"), nullable=False)
    is_statutorily_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    estimated_fee_relief_inr: Mapped[float] = mapped_column(Float, nullable=False)
    statutory_failure_reasons_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    final_simulation_state: Mapped[str] = mapped_column(String(50), nullable=False)
    attempted_application: Mapped[bool] = mapped_column(Boolean, nullable=False)
    completed_application: Mapped[bool] = mapped_column(Boolean, nullable=False)
    benefit_received: Mapped[bool] = mapped_column(Boolean, nullable=False)
    inner_monologue: Mapped[str] = mapped_column(Text, nullable=False)
    stated_intention: Mapped[str] = mapped_column(String(255), nullable=False)
    perceived_barriers_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    chosen_action: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence_level: Mapped[str] = mapped_column(String(50), nullable=False)

    __table_args__ = (
        UniqueConstraint("run_id", "persona_id", name="uq_individual_outcomes_run_persona"),
        CheckConstraint(
            "confidence_level IN ('High', 'Moderate', 'Low')",
            name="check_io_confidence_level"
        ),
        CheckConstraint(
            "final_simulation_state IN ('UNINFORMED', 'AWARE', 'EVALUATING', 'COLLECTING_DOCUMENTS', 'APPLIED', 'BENEFIT_RECEIVED', 'REJECTED', 'DROPPED_OUT')",
            name="check_io_simulation_state"
        ),
    )

    # Relationships
    simulation_run: Mapped[SimulationRunDB] = relationship("SimulationRunDB", back_populates="individual_outcomes")
    persona: Mapped[SyntheticPersonaDB] = relationship("SyntheticPersonaDB", back_populates="outcomes")


class AggregateResultDB(Base):
    """Entity 9: Macro-level cohort outcomes per run and step."""
    __tablename__ = "aggregate_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("simulation_runs.run_id", ondelete="CASCADE"), nullable=False)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    total_personas: Mapped[int] = mapped_column(Integer, nullable=False)
    eligible_count: Mapped[int] = mapped_column(Integer, nullable=False)
    ineligible_count: Mapped[int] = mapped_column(Integer, nullable=False)
    eligibility_rate: Mapped[float] = mapped_column(Float, nullable=False)
    mean_awareness: Mapped[float] = mapped_column(Float, nullable=False)
    mean_perceived_benefit: Mapped[float] = mapped_column(Float, nullable=False)
    mean_application_probability: Mapped[float] = mapped_column(Float, nullable=False)
    expected_uptake_probability: Mapped[float] = mapped_column(Float, nullable=False)
    realized_uptake_count: Mapped[int] = mapped_column(Integer, nullable=False)
    realized_uptake_rate: Mapped[float] = mapped_column(Float, nullable=False)
    total_fee_relief_inr: Mapped[float] = mapped_column(Float, nullable=False)
    avg_relief_per_eligible_inr: Mapped[float] = mapped_column(Float, nullable=False)
    categorical_breakdowns_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("run_id", "step_number", name="uq_aggregate_results_run_step"),
    )

    # Relationships
    simulation_run: Mapped[SimulationRunDB] = relationship("SimulationRunDB", back_populates="aggregate_results")


class ApplicationRecordDB(Base):
    """
    Entity 10: Official administrative student scholarship application file.
    Maintains immutable point-in-time initial eligibility snapshot and links
    to full evaluation and status transition audit history.
    """
    __tablename__ = "application_lifecycle_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    persona_id: Mapped[str] = mapped_column(String(64), ForeignKey("synthetic_personas.persona_id", ondelete="RESTRICT"), nullable=False)
    policy_id: Mapped[int] = mapped_column(Integer, ForeignKey("policies.id", ondelete="RESTRICT"), nullable=False)
    evaluation_policy_config_id: Mapped[int] = mapped_column(Integer, ForeignKey("policy_configurations.id", ondelete="RESTRICT"), nullable=False)
    run_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("simulation_runs.run_id", ondelete="SET NULL"), nullable=True)
    current_status: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    initial_eligibility_snapshot: Mapped[bool] = mapped_column(Boolean, nullable=False)
    initial_ineligibility_reasons_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    evaluated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    latest_verified_eligibility_status: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    latest_verification_policy_config_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("policy_configurations.id", ondelete="RESTRICT"), nullable=True)
    latest_verification_timestamp: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    claimed_fee_relief_inr: Mapped[float] = mapped_column(Float, nullable=False)
    approved_fee_relief_inr: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    disbursed_amount_inr: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    submission_timestamp: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    scrutiny_timestamp: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    approval_timestamp: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    disbursement_timestamp: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    rejection_timestamp: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    revocation_timestamp: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    abandoned_timestamp: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint(
            "current_status IN ('DRAFT', 'SUBMITTED', 'UNDER_VERIFICATION', 'SENT_BACK_FOR_CORRECTION', 'RESUBMITTED', 'APPROVED', 'BENEFIT_DISBURSED', 'REJECTED', 'REVOKED', 'ABANDONED')",
            name="check_alr_current_status"
        ),
    )

    # Relationships
    persona: Mapped[SyntheticPersonaDB] = relationship("SyntheticPersonaDB", back_populates="applications")
    policy: Mapped[PolicyDB] = relationship("PolicyDB", back_populates="applications")
    evaluation_policy_config: Mapped[PolicyConfigurationDB] = relationship(
        "PolicyConfigurationDB",
        foreign_keys=[evaluation_policy_config_id],
        back_populates="initial_applications"
    )
    latest_verification_policy_config: Mapped[Optional[PolicyConfigurationDB]] = relationship(
        "PolicyConfigurationDB",
        foreign_keys=[latest_verification_policy_config_id],
        back_populates="verified_applications"
    )
    simulation_run: Mapped[Optional[SimulationRunDB]] = relationship("SimulationRunDB", back_populates="application_records")
    evaluation_history: Mapped[List[ApplicationEligibilityEvaluationDB]] = relationship(
        "ApplicationEligibilityEvaluationDB",
        back_populates="application",
        cascade="save-update, merge",
        passive_deletes=True
    )
    audit_history: Mapped[List[ApplicationAuditLogDB]] = relationship(
        "ApplicationAuditLogDB",
        back_populates="application",
        cascade="save-update, merge",
        passive_deletes=True
    )


class ApplicationEligibilityEvaluationDB(Base):
    """
    Supporting Table 1: Preserves complete immutable history of every eligibility evaluation
    event across application lifecycle (initial assessment, desk scrutiny, re-evaluation, audit).
    """
    __tablename__ = "application_eligibility_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("application_lifecycle_records.id", ondelete="RESTRICT"), nullable=False)
    evaluation_stage: Mapped[str] = mapped_column(String(50), nullable=False)
    is_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    failure_reasons_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    policy_config_id: Mapped[int] = mapped_column(Integer, ForeignKey("policy_configurations.id", ondelete="RESTRICT"), nullable=False)
    evaluated_by: Mapped[str] = mapped_column(String(50), nullable=False)
    evaluation_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evaluated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_app_eval_app_id_evaluated_at", "application_id", "evaluated_at"),
        Index("ix_app_eval_app_id_stage", "application_id", "evaluation_stage"),
        CheckConstraint(
            "evaluation_stage IN ('INITIAL_ASSESSMENT', 'DESK_SCRUTINY', 'RESUBMISSION_RE_EVALUATION', 'POST_SANCTION_AUDIT')",
            name="check_eval_stage"
        ),
        CheckConstraint(
            "evaluated_by IN ('SYSTEM_ENGINE', 'SCRUTINY_OFFICER', 'AUDIT_OFFICER')",
            name="check_eval_by"
        ),
    )

    # Relationships
    application: Mapped[ApplicationRecordDB] = relationship("ApplicationRecordDB", back_populates="evaluation_history")
    policy_config: Mapped[PolicyConfigurationDB] = relationship("PolicyConfigurationDB", back_populates="evaluations")


class ApplicationAuditLogDB(Base):
    """
    Supporting Table 2: Strictly append-only audit trail recording every administrative
    lifecycle status transition.
    """
    __tablename__ = "application_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("application_lifecycle_records.id", ondelete="RESTRICT"), nullable=False)
    from_status: Mapped[str] = mapped_column(String(50), nullable=False)
    to_status: Mapped[str] = mapped_column(String(50), nullable=False)
    reason_or_remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    performed_by: Mapped[str] = mapped_column(String(50), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_app_audit_app_id_timestamp", "application_id", "timestamp"),
        CheckConstraint(
            "from_status IN ('DRAFT', 'SUBMITTED', 'UNDER_VERIFICATION', 'SENT_BACK_FOR_CORRECTION', 'RESUBMITTED', 'APPROVED', 'BENEFIT_DISBURSED', 'REJECTED', 'REVOKED', 'ABANDONED')",
            name="check_audit_from_status"
        ),
        CheckConstraint(
            "to_status IN ('DRAFT', 'SUBMITTED', 'UNDER_VERIFICATION', 'SENT_BACK_FOR_CORRECTION', 'RESUBMITTED', 'APPROVED', 'BENEFIT_DISBURSED', 'REJECTED', 'REVOKED', 'ABANDONED')",
            name="check_audit_to_status"
        ),
        CheckConstraint(
            "performed_by IN ('STUDENT', 'SCRUTINY_OFFICER', 'DISBURSEMENT_OFFICER', 'SYSTEM_ENGINE')",
            name="check_audit_performed_by"
        ),
    )

    # Relationships
    application: Mapped[ApplicationRecordDB] = relationship("ApplicationRecordDB", back_populates="audit_history")


__all__ = [
    # Custom Types & Enums
    "UTCDateTime",
    "ApplicationLifecycleStatus",
    "SimulationRunStatus",
    "SimulationState",
    "ApplicationEvaluationStage",
    "EvaluationActor",
    "AuditActor",
    "ConfidenceLevel",
    # 12 ORM Models
    "PolicyDB",
    "PolicyConfigurationDB",
    "SyntheticPersonaDB",
    "ScenarioConfigurationDB",
    "SimulationRunDB",
    "PersonaRunStateDB",
    "PersonaInteractionDB",
    "IndividualOutcomeDB",
    "AggregateResultDB",
    "ApplicationRecordDB",
    "ApplicationEligibilityEvaluationDB",
    "ApplicationAuditLogDB",
]
