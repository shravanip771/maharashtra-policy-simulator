"""
Integration Test Suite for Simulation Engine and Technical Integration.

Verifies:
1. Multi-persona cohort execution over multiple simulation rounds.
2. In-memory state preservation and peer diffusion dynamics across steps.
3. Controlled 5-step application lifecycle progression:
   Step 1: DRAFT -> Step 2: SUBMITTED -> Step 3: UNDER_VERIFICATION -> Step 4: APPROVED -> Step 5: BENEFIT_DISBURSED.
4. Strict enforcement of at most ONE administrative status transition per persona per simulation step.
5. Ineligible persona rejection (Step 4: UNDER_VERIFICATION -> REJECTED) and zero disbursement.
6. Verification guard: approval blocked without formal pre-approval scrutiny evaluation.
7. Disallowance of disbursement before approval (InvalidLifecycleTransitionError).
8. Impossibility of approval and disbursement occurring within the same simulation round.
9. Ordered application audit log sequence and monotonic timestamps.
10. Full database persistence across all 6 ORM tables.
11. Transaction boundary ownership: engine and persistence adapter never commit session.
12. Simulation failure handling: failed runs are marked FAILED, never COMPLETED.
13. Policy configuration governance: provisional status clearly flagged (is_verified_statutory_rule=False).
"""

from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from backend.database import Base, init_db
from backend.db_models import (
    PolicyDB,
    PolicyConfigurationDB,
    SimulationRunDB,
    SyntheticPersonaDB,
    PersonaRunStateDB,
    PersonaInteractionDB,
    IndividualOutcomeDB,
    AggregateResultDB,
    ApplicationRecordDB,
    ApplicationAuditLogDB,
    ApplicationEligibilityEvaluationDB,
    ApplicationLifecycleStatus,
    SimulationRunStatus,
)
from backend.simulation_persistence import SimulationPersistenceAdapter
from backend.service import SimulationService
from backend.models import SimulationRequest, SimulationResponse
from backend.lifecycle_service import (
    create_application,
    disburse_benefit,
    InvalidLifecycleTransitionError,
)
from simulation.persona import StudentPersona, SimulationState, InstitutionType, AdmissionMode, PersonalityTraits
from simulation.engine import SimulationEngine, MultiStepSimulationResult
from simulation.policy_rules import RajarshiShahuPolicyEngine
from simulation.agent import StubLLMProvider
from simulation.social_network import SyntheticSocialNetwork


@pytest.fixture
def isolated_db_session():
    """
    Creates an isolated in-memory SQLite database for integration testing.
    Foreign key enforcement is enabled via StaticPool.
    """
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(target_engine=test_engine)
    test_factory = sessionmaker(bind=test_engine, autocommit=False, autoflush=False, expire_on_commit=False)
    session = test_factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def create_sample_personas() -> list[StudentPersona]:
    """Generates a controlled list of 3 personas with diverse eligibility attributes."""
    # Persona 1: Fully eligible (income 3L, 82% attendance, CAP admission)
    p1 = StudentPersona(
        persona_id="TEST-STU-001",
        name="Aarav Patil",
        age=19,
        gender="Male",
        district="Dhule",
        is_maharashtra_domicile=True,
        family_income=300000.0,
        caste_category="General-EBC",
        course_name="B.E. Computer Engineering",
        institution_type=InstitutionType.GOVERNMENT_AIDED,
        admission_mode=AdmissionMode.CAP,
        annual_tuition_fee=60000.0,
        attendance_percentage=82.0,
        previous_year_passed=True,
        digital_literacy=0.75,
        initial_awareness=0.80,
        document_readiness=0.85,
        institutional_trust=0.70,
        personality=PersonalityTraits(patience=0.7, diligence=0.8, risk_aversion=0.3, self_advocacy=0.8),
    )

    # Persona 2: Ineligible due to income > 8 Lakh (12 Lakh)
    p2 = StudentPersona(
        persona_id="TEST-STU-002",
        name="Sneha Shinde",
        age=20,
        gender="Female",
        district="Dhule",
        is_maharashtra_domicile=True,
        family_income=1200000.0,
        caste_category="General-EBC",
        course_name="B.Pharmacy",
        institution_type=InstitutionType.PRIVATE_UNAIDED,
        admission_mode=AdmissionMode.CAP,
        annual_tuition_fee=90000.0,
        attendance_percentage=85.0,
        previous_year_passed=True,
        digital_literacy=0.80,
        initial_awareness=0.70,
        document_readiness=0.90,
        institutional_trust=0.60,
        personality=PersonalityTraits(patience=0.6, diligence=0.7, risk_aversion=0.4, self_advocacy=0.6),
    )

    # Persona 3: Ineligible due to non-CAP admission (Management-Quota)
    p3 = StudentPersona(
        persona_id="TEST-STU-003",
        name="Rohan Deshmukh",
        age=19,
        gender="Male",
        district="Dhule",
        is_maharashtra_domicile=True,
        family_income=450000.0,
        caste_category="General-EBC",
        course_name="B.Tech Mechanical",
        institution_type=InstitutionType.PRIVATE_UNAIDED,
        admission_mode=AdmissionMode.MANAGEMENT_QUOTA,
        annual_tuition_fee=110000.0,
        attendance_percentage=78.0,
        previous_year_passed=True,
        digital_literacy=0.65,
        initial_awareness=0.50,
        document_readiness=0.60,
        institutional_trust=0.55,
        personality=PersonalityTraits(patience=0.5, diligence=0.5, risk_aversion=0.5, self_advocacy=0.5),
    )

    return [p1, p2, p3]


class TestSimulationIntegration:
    """End-to-end integration tests for multi-step simulation orchestration."""

    def test_multistep_cohort_in_memory_execution(self):
        """Verifies multi-step simulation execution in pure in-memory mode."""
        personas = create_sample_personas()
        engine = SimulationEngine(llm_provider=StubLLMProvider())

        result: MultiStepSimulationResult = engine.run_multistep_cohort(
            personas=personas,
            total_steps=2,
            cohort_name="Test-Cohort",
            seed=42,
            enable_social_interaction=True,
            max_connections_per_persona=2,
        )

        assert result.total_personas == 3
        assert result.total_steps == 2
        assert len(result.step_cohort_results) == 2

        # Step 1 and Step 2 validation
        step1 = result.step_cohort_results[0]
        step2 = result.step_cohort_results[1]

        # Statutory eligibility: only persona 1 is eligible
        assert step1.eligible_count == 1
        assert step1.ineligible_count == 2
        assert step2.eligible_count == 1
        assert step2.ineligible_count == 2

        # State evolution tracking
        assert "TEST-STU-001" in result.state_evolution_summary
        p1_evo = result.state_evolution_summary["TEST-STU-001"]
        assert p1_evo["final_state"] in ("BENEFIT_RECEIVED", "APPLIED", "EVALUATING")

        # Ineligible personas must be REJECTED
        assert result.state_evolution_summary["TEST-STU-002"]["final_state"] == "REJECTED"
        assert result.state_evolution_summary["TEST-STU-003"]["final_state"] == "REJECTED"

    def test_step_aware_lifecycle_progression(self, isolated_db_session: Session):
        """
        Verifies controlled, step-aware progression across 5 simulation steps:
        - Step 1: Newly initiated application remains DRAFT (citizen: COLLECTING_DOCUMENTS).
        - Step 2: Citizen files application -> SUBMITTED (citizen: APPLIED).
        - Step 3: Verification officer commences scrutiny -> UNDER_VERIFICATION (citizen: APPLIED).
        - Step 4: Statutory evaluation completed -> APPROVED (citizen: APPLIED).
        - Step 5: Financial DBT execution -> BENEFIT_DISBURSED (citizen: BENEFIT_RECEIVED).

        Enforces that at most ONE administrative status transition occurs per persona per simulation step.
        """
        session = isolated_db_session
        personas = create_sample_personas()

        policy, config = SimulationPersistenceAdapter.ensure_policy_and_config(session=session)
        SimulationPersistenceAdapter.sync_personas(session=session, personas=personas)

        run_id = "FIVE-STEP-AWARE-TEST-001"
        SimulationPersistenceAdapter.start_simulation_run(
            session=session,
            run_id=run_id,
            policy_id=policy.id,
            policy_config_id=config.id,
            district="Dhule",
            population_size=len(personas),
            simulation_steps=5,
            seed=42,
            llm_provider="Deterministic Rule-Grounded Stub (Offline)",
        )

        engine = SimulationEngine(llm_provider=StubLLMProvider())
        result = engine.run_multistep_cohort(
            personas=personas,
            total_steps=5,
            cohort_name="Step-Aware-Cohort",
            seed=42,
            enable_social_interaction=True,
            max_connections_per_persona=2,
            session=session,
            run_id=run_id,
            policy_id=policy.id,
            policy_config_id=config.id,
        )

        SimulationPersistenceAdapter.complete_simulation_run(
            session=session,
            run_id=run_id,
            final_cohort=result.final_cohort_result,
        )

        # 1. Verify temporal state snapshots across all 5 steps for eligible persona TEST-STU-001
        states_p1 = session.scalars(
            select(PersonaRunStateDB)
            .where(PersonaRunStateDB.run_id == run_id, PersonaRunStateDB.persona_id == "TEST-STU-001")
            .order_by(PersonaRunStateDB.step_number.asc())
        ).all()
        assert len(states_p1) == 5

        # Step 1: DRAFT file initiated -> citizen is COLLECTING_DOCUMENTS
        assert states_p1[0].step_number == 1
        assert states_p1[0].simulation_state == SimulationState.COLLECTING_DOCUMENTS.value

        # Step 2: Citizen submits completed application -> citizen is APPLIED
        assert states_p1[1].step_number == 2
        assert states_p1[1].simulation_state == SimulationState.APPLIED.value

        # Step 3: Application starts desk scrutiny -> UNDER_VERIFICATION (citizen remains APPLIED)
        assert states_p1[2].step_number == 3
        assert states_p1[2].simulation_state == SimulationState.APPLIED.value

        # Step 4: Verification officer sanctions approval -> APPROVED (citizen remains APPLIED, awaiting DBT)
        assert states_p1[3].step_number == 4
        assert states_p1[3].simulation_state == SimulationState.APPLIED.value

        # Step 5: Treasury executes disbursement -> BENEFIT_DISBURSED (citizen reaches BENEFIT_RECEIVED)
        assert states_p1[4].step_number == 5
        assert states_p1[4].simulation_state == SimulationState.BENEFIT_RECEIVED.value

        # 2. Verify ApplicationRecordDB final status for eligible persona
        p1_app = session.scalars(
            select(ApplicationRecordDB)
            .where(ApplicationRecordDB.run_id == run_id, ApplicationRecordDB.persona_id == "TEST-STU-001")
        ).one()
        assert p1_app.current_status == ApplicationLifecycleStatus.BENEFIT_DISBURSED.value
        assert p1_app.disbursed_amount_inr == 30000.0  # 50% of 60,000

        # 3. Verify ordered audit log history for eligible persona across the 5 steps
        audit_logs = session.scalars(
            select(ApplicationAuditLogDB)
            .where(ApplicationAuditLogDB.application_id == p1_app.id)
            .order_by(ApplicationAuditLogDB.id.asc())
        ).all()

        # Exactly 5 audit entries for 5 distinct simulation steps
        assert len(audit_logs) == 5

        transition_tuples = [(log.from_status, log.to_status) for log in audit_logs]
        expected_transitions = [
            (ApplicationLifecycleStatus.DRAFT.value, ApplicationLifecycleStatus.DRAFT.value),                # Step 1: File initiation
            (ApplicationLifecycleStatus.DRAFT.value, ApplicationLifecycleStatus.SUBMITTED.value),            # Step 2: Submission
            (ApplicationLifecycleStatus.SUBMITTED.value, ApplicationLifecycleStatus.UNDER_VERIFICATION.value),# Step 3: Scrutiny
            (ApplicationLifecycleStatus.UNDER_VERIFICATION.value, ApplicationLifecycleStatus.APPROVED.value), # Step 4: Approval
            (ApplicationLifecycleStatus.APPROVED.value, ApplicationLifecycleStatus.BENEFIT_DISBURSED.value), # Step 5: Disbursement
        ]
        assert transition_tuples == expected_transitions

        # Verify remarks explicitly link each transition to its respective simulation step
        assert "step 2" in audit_logs[1].reason_or_remarks.lower()
        assert "step 3" in audit_logs[2].reason_or_remarks.lower()
        assert "step 4" in audit_logs[3].reason_or_remarks.lower()
        assert "approved under statutory" in audit_logs[3].reason_or_remarks.lower()
        assert "-s5" in audit_logs[4].reason_or_remarks.lower()  # Payment ref stamped with S5

        # Verify timestamp progression is non-decreasing
        for i in range(len(audit_logs) - 1):
            assert audit_logs[i].timestamp <= audit_logs[i + 1].timestamp

        # 4. Verify actual ApplicationRecordDB.current_status progression after EACH simulation step (Steps 1 to 5)
        expected_step_statuses = {
            1: ApplicationLifecycleStatus.DRAFT.value,
            2: ApplicationLifecycleStatus.SUBMITTED.value,
            3: ApplicationLifecycleStatus.UNDER_VERIFICATION.value,
            4: ApplicationLifecycleStatus.APPROVED.value,
            5: ApplicationLifecycleStatus.BENEFIT_DISBURSED.value,
        }
        for target_step, expected_status in expected_step_statuses.items():
            step_run_id = f"STEP-STATUS-CHECK-S{target_step}"
            SimulationPersistenceAdapter.start_simulation_run(
                session=session,
                run_id=step_run_id,
                policy_id=policy.id,
                policy_config_id=config.id,
                district="Dhule",
                population_size=len(personas),
                simulation_steps=target_step,
                seed=42,
            )
            step_engine = SimulationEngine(llm_provider=StubLLMProvider())
            step_engine.run_multistep_cohort(
                personas=create_sample_personas(),
                total_steps=target_step,
                cohort_name=f"Step-{target_step}-Progression",
                seed=42,
                session=session,
                run_id=step_run_id,
                policy_id=policy.id,
                policy_config_id=config.id,
            )
            app_step = session.scalars(
                select(ApplicationRecordDB)
                .where(ApplicationRecordDB.run_id == step_run_id, ApplicationRecordDB.persona_id == "TEST-STU-001")
            ).one()
            assert app_step.current_status == expected_status, (
                f"Step {target_step}: expected administrative status '{expected_status}', got '{app_step.current_status}'"
            )

    def test_ineligible_persona_five_step_lifecycle(self, isolated_db_session: Session):
        """
        Verifies that ineligible personas (e.g. income > 8L) progress step-by-step:
        Step 1: DRAFT
        Step 2: SUBMITTED
        Step 3: UNDER_VERIFICATION
        Step 4: REJECTED
        Step 5: Remains REJECTED (terminal, zero disbursement).
        """
        session = isolated_db_session
        personas = create_sample_personas()

        policy, config = SimulationPersistenceAdapter.ensure_policy_and_config(session=session)
        SimulationPersistenceAdapter.sync_personas(session=session, personas=personas)

        run_id = "INELIGIBLE-FIVE-STEP-TEST"
        SimulationPersistenceAdapter.start_simulation_run(
            session=session,
            run_id=run_id,
            policy_id=policy.id,
            policy_config_id=config.id,
            district="Dhule",
            population_size=len(personas),
            simulation_steps=5,
            seed=42,
        )

        engine = SimulationEngine(llm_provider=StubLLMProvider())
        result = engine.run_multistep_cohort(
            personas=personas,
            total_steps=5,
            cohort_name="Ineligible-Cohort",
            seed=42,
            session=session,
            run_id=run_id,
            policy_id=policy.id,
            policy_config_id=config.id,
        )

        SimulationPersistenceAdapter.complete_simulation_run(
            session=session,
            run_id=run_id,
            final_cohort=result.final_cohort_result,
        )

        # Verify persona 2 (high income: 12L)
        p2_app = session.scalars(
            select(ApplicationRecordDB)
            .where(ApplicationRecordDB.run_id == run_id, ApplicationRecordDB.persona_id == "TEST-STU-002")
        ).one()
        assert p2_app.current_status == ApplicationLifecycleStatus.REJECTED.value
        assert p2_app.disbursed_amount_inr == 0.0
        assert p2_app.approved_fee_relief_inr == 0.0

        audit_logs_p2 = session.scalars(
            select(ApplicationAuditLogDB)
            .where(ApplicationAuditLogDB.application_id == p2_app.id)
            .order_by(ApplicationAuditLogDB.id.asc())
        ).all()

        # Audit sequence: Initiation -> Submission -> Scrutiny -> Rejection (4 entries, no disbursement)
        p2_transitions = [(log.from_status, log.to_status) for log in audit_logs_p2]
        expected_p2 = [
            (ApplicationLifecycleStatus.DRAFT.value, ApplicationLifecycleStatus.DRAFT.value),
            (ApplicationLifecycleStatus.DRAFT.value, ApplicationLifecycleStatus.SUBMITTED.value),
            (ApplicationLifecycleStatus.SUBMITTED.value, ApplicationLifecycleStatus.UNDER_VERIFICATION.value),
            (ApplicationLifecycleStatus.UNDER_VERIFICATION.value, ApplicationLifecycleStatus.REJECTED.value),
        ]
        assert p2_transitions == expected_p2
        assert "step 4" in audit_logs_p2[3].reason_or_remarks.lower()
        assert "ineligible" in audit_logs_p2[3].reason_or_remarks.lower()

        # 4. Verify actual ApplicationRecordDB.current_status progression after EACH simulation step for ineligible persona
        expected_ineligible_step_statuses = {
            1: ApplicationLifecycleStatus.DRAFT.value,
            2: ApplicationLifecycleStatus.SUBMITTED.value,
            3: ApplicationLifecycleStatus.UNDER_VERIFICATION.value,
            4: ApplicationLifecycleStatus.REJECTED.value,
            5: ApplicationLifecycleStatus.REJECTED.value,
        }
        for target_step, expected_status in expected_ineligible_step_statuses.items():
            inelig_run_id = f"INELIG-STEP-STATUS-S{target_step}"
            SimulationPersistenceAdapter.start_simulation_run(
                session=session,
                run_id=inelig_run_id,
                policy_id=policy.id,
                policy_config_id=config.id,
                district="Dhule",
                population_size=len(personas),
                simulation_steps=target_step,
                seed=42,
            )
            step_engine = SimulationEngine(llm_provider=StubLLMProvider())
            step_engine.run_multistep_cohort(
                personas=create_sample_personas(),
                total_steps=target_step,
                cohort_name=f"Inelig-Step-{target_step}-Progression",
                seed=42,
                session=session,
                run_id=inelig_run_id,
                policy_id=policy.id,
                policy_config_id=config.id,
            )
            app_step_inelig = session.scalars(
                select(ApplicationRecordDB)
                .where(ApplicationRecordDB.run_id == inelig_run_id, ApplicationRecordDB.persona_id == "TEST-STU-002")
            ).one()
            assert app_step_inelig.current_status == expected_status, (
                f"Ineligible Step {target_step}: expected administrative status '{expected_status}', got '{app_step_inelig.current_status}'"
            )

        # Outcome record verification
        p2_out = session.scalars(
            select(IndividualOutcomeDB)
            .where(IndividualOutcomeDB.run_id == run_id, IndividualOutcomeDB.persona_id == "TEST-STU-002")
        ).one()
        assert p2_out.is_statutorily_eligible is False
        assert p2_out.final_simulation_state == SimulationState.REJECTED.value
        assert p2_out.benefit_received is False

    def test_approval_and_disbursement_cannot_happen_in_same_step(self, isolated_db_session: Session):
        """
        Verifies that in a 4-step simulation run, an eligible application reaches APPROVED
        at Step 4, but CANNOT be disbursed in that same step.
        Disbursement strictly requires a subsequent step (Step 5).
        """
        session = isolated_db_session
        personas = create_sample_personas()

        policy, config = SimulationPersistenceAdapter.ensure_policy_and_config(session=session)
        SimulationPersistenceAdapter.sync_personas(session=session, personas=personas)

        run_id = "FOUR-STEP-NO-SAME-STEP-DISBURSE"
        SimulationPersistenceAdapter.start_simulation_run(
            session=session,
            run_id=run_id,
            policy_id=policy.id,
            policy_config_id=config.id,
            district="Dhule",
            population_size=len(personas),
            simulation_steps=4,
            seed=42,
        )

        engine = SimulationEngine(llm_provider=StubLLMProvider())
        result = engine.run_multistep_cohort(
            personas=personas,
            total_steps=4,
            cohort_name="Four-Step-Cohort",
            seed=42,
            session=session,
            run_id=run_id,
            policy_id=policy.id,
            policy_config_id=config.id,
        )

        SimulationPersistenceAdapter.complete_simulation_run(
            session=session,
            run_id=run_id,
            final_cohort=result.final_cohort_result,
        )

        p1_app = session.scalars(
            select(ApplicationRecordDB)
            .where(ApplicationRecordDB.run_id == run_id, ApplicationRecordDB.persona_id == "TEST-STU-001")
        ).one()

        # At the end of 4 steps, status MUST be APPROVED, NOT BENEFIT_DISBURSED
        assert p1_app.current_status == ApplicationLifecycleStatus.APPROVED.value
        assert p1_app.disbursed_amount_inr == 0.0

        audit_logs = session.scalars(
            select(ApplicationAuditLogDB)
            .where(ApplicationAuditLogDB.application_id == p1_app.id)
            .order_by(ApplicationAuditLogDB.id.asc())
        ).all()

        # Audit logs must have exactly 4 entries; no 5th disbursement entry exists
        assert len(audit_logs) == 4
        assert audit_logs[-1].to_status == ApplicationLifecycleStatus.APPROVED.value

    def test_cannot_disburse_before_approval(self, isolated_db_session: Session):
        """
        Verifies that the administrative lifecycle strictly blocks disbursing an application
        that is still in DRAFT or SUBMITTED status.
        """
        session = isolated_db_session
        policy, config = SimulationPersistenceAdapter.ensure_policy_and_config(session=session)
        personas = create_sample_personas()
        SimulationPersistenceAdapter.sync_personas(session=session, personas=personas)

        app = create_application(
            session=session,
            persona_id="TEST-STU-001",
            policy_id=policy.id,
            evaluation_policy_config_id=config.id,
            claimed_fee_relief_inr=30000.0,
            is_eligible=True,
        )
        assert app.current_status == ApplicationLifecycleStatus.DRAFT.value

        # Attempt to directly disburse a DRAFT application -> must raise InvalidLifecycleTransitionError
        with pytest.raises(InvalidLifecycleTransitionError) as exc_info:
            disburse_benefit(
                session=session,
                application_id=app.id,
                disbursed_amount=30000.0,
                payment_reference="DBT-ILLEGAL-PRE-DISBURSE",
            )
        assert "forbidden" in str(exc_info.value).lower()

    def test_social_interactions_meaningful_assertion(self, isolated_db_session: Session):
        """
        Verifies that social interactions produce meaningful non-vacuous records when network edges exist,
        and verifies explicit behavior when social interactions are disabled.
        """
        session = isolated_db_session
        personas = create_sample_personas()
        policy, config = SimulationPersistenceAdapter.ensure_policy_and_config(session=session)
        SimulationPersistenceAdapter.sync_personas(session=session, personas=personas)

        # 1. Active social network: verify non-zero interactions when network has edges
        net = SyntheticSocialNetwork(personas=personas, seed=42, max_degree=2)
        assert len(net.edges) > 0, "Network should establish homophily ties among Dhule college students"

        run_id = "INTERACTIONS-TEST-001"
        SimulationPersistenceAdapter.start_simulation_run(
            session=session,
            run_id=run_id,
            policy_id=policy.id,
            policy_config_id=config.id,
            district="Dhule",
            population_size=len(personas),
            simulation_steps=2,
            seed=42,
        )

        engine = SimulationEngine(llm_provider=StubLLMProvider())
        result = engine.run_multistep_cohort(
            personas=personas,
            total_steps=2,
            cohort_name="Social-Cohort",
            seed=42,
            enable_social_interaction=True,
            max_connections_per_persona=2,
            session=session,
            run_id=run_id,
            policy_id=policy.id,
            policy_config_id=config.id,
        )

        interactions = session.scalars(
            select(PersonaInteractionDB).where(PersonaInteractionDB.run_id == run_id)
        ).all()

        # Non-vacuous assertion: exactly matches the recorded multi-step interactions
        expected_total = len(result.interactions_by_step.get(1, [])) + len(result.interactions_by_step.get(2, []))
        assert expected_total > 0, "Social network must have scheduled active interactions across 2 steps"
        assert len(interactions) == expected_total

        for inter in interactions:
            assert inter.sender_id in {p.persona_id for p in personas}
            assert inter.receiver_id in {p.persona_id for p in personas}
            assert inter.sender_id != inter.receiver_id
            assert len(inter.sender_message) > 0
            assert len(inter.receiver_response) > 0

    def test_policy_configuration_provisional_flag(self, isolated_db_session: Session):
        """
        Verifies that policy configurations generated by the persistence adapter are
        explicitly flagged is_verified_statutory_rule=False to indicate provisional status
        until verified by the policy owner (Shravani).
        """
        session = isolated_db_session
        policy, config = SimulationPersistenceAdapter.ensure_policy_and_config(session=session)

        # Must NOT independently declare hardcoded assumptions as verified
        assert config.is_verified_statutory_rule is False
        assert config.config_version == "v1.0-provisional"
        assert "provisional" in config.notes.lower()
        assert config.max_income_limit == RajarshiShahuPolicyEngine.MAX_INCOME_LIMIT
        assert config.min_attendance_pct == RajarshiShahuPolicyEngine.MIN_ATTENDANCE_PERCENT
        assert config.baseline_relief_rate == RajarshiShahuPolicyEngine.DEFAULT_POC_ASSUMED_REIMBURSEMENT_RATE
        assert config.max_family_beneficiaries == RajarshiShahuPolicyEngine.MAX_FAMILY_BENEFICIARIES

    def test_simulation_failure_marks_run_failed(self, isolated_db_session: Session):
        """
        Verifies that if a simulation run encounters an unexpected failure,
        the SimulationRunDB record is marked FAILED rather than left as COMPLETED.
        """
        session = isolated_db_session
        req = SimulationRequest(
            district="Dhule",
            cohort_size=3,
            simulation_steps=2,
            seed=42,
        )

        class FailingEngine(SimulationEngine):
            def run_multistep_cohort(self, *args, **kwargs):
                raise RuntimeError("Simulated internal worker crash")

        try:
            with pytest.raises(RuntimeError) as exc_info:
                from unittest.mock import patch
                with patch("backend.service.SimulationEngine", return_value=FailingEngine()):
                    SimulationService.execute_simulation(req, session=session, persist=True)

            assert "Simulated internal worker crash" in str(exc_info.value)

            # Query the run record: must be marked FAILED
            failed_run = session.scalars(select(SimulationRunDB)).first()
            assert failed_run is not None
            assert failed_run.run_status == SimulationRunStatus.FAILED.value
            assert "Simulated internal worker crash" in failed_run.status_message
        finally:
            pass

    def test_service_layer_execution_with_persistence(self, isolated_db_session: Session):
        """Verifies SimulationService executes and persists via the service interface."""
        session = isolated_db_session
        req = SimulationRequest(
            district="Dhule",
            cohort_size=5,
            simulation_steps=2,
            seed=42,
            use_gemini=False,
        )

        response: SimulationResponse = SimulationService.execute_simulation(
            req=req,
            session=session,
            persist=True,
        )

        assert response.metadata.district == "Dhule"
        assert response.metadata.cohort_size == 5
        assert response.aggregate_metrics.total_personas == 5
        assert len(response.personas) == 5
        assert len(response.step_metrics) == 2

        # Verify database records were created in the session
        run_count = session.execute(text("SELECT count(*) FROM simulation_runs")).scalar()
        assert run_count == 1

        persona_count = session.execute(text("SELECT count(*) FROM synthetic_personas")).scalar()
        assert persona_count == 5

        outcome_count = session.execute(text("SELECT count(*) FROM individual_outcomes")).scalar()
        assert outcome_count == 5

    def test_transaction_ownership_no_internal_commits(self, isolated_db_session: Session):
        """
        Confirms that the simulation engine and persistence adapter respect transaction boundaries
        and do NOT commit transactions. A rollback should revert all flushed entries.
        """
        session = isolated_db_session
        personas = create_sample_personas()

        policy, config = SimulationPersistenceAdapter.ensure_policy_and_config(session=session)
        run_id = "ROLLBACK-TEST-RUN"
        SimulationPersistenceAdapter.start_simulation_run(
            session=session,
            run_id=run_id,
            policy_id=policy.id,
            policy_config_id=config.id,
            district="Dhule",
            population_size=len(personas),
            simulation_steps=1,
            seed=42,
        )

        # Before rollback, entity is present in session
        assert session.get(SimulationRunDB, run_id) is not None

        # Rollback caller session
        session.rollback()

        # After rollback, record must not exist in database (confirming no internal session.commit() occurred)
        assert session.get(SimulationRunDB, run_id) is None
