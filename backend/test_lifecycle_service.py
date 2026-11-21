"""
Comprehensive Unit Test Suite for Application Lifecycle Service Layer (Phase 2 - Step 3).
Tests all administrative lifecycle transitions, deterministic approval guards,
snapshot immutability, eligibility evaluation history, audit trails, and transaction rollback
against an isolated in-memory SQLite database.
"""

import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from backend.database import Base, init_db
from backend.db_models import (
    ApplicationAuditLogDB,
    ApplicationEligibilityEvaluationDB,
    ApplicationEvaluationStage,
    ApplicationLifecycleStatus,
    ApplicationRecordDB,
    AuditActor,
    EvaluationActor,
    PolicyConfigurationDB,
    PolicyDB,
    SyntheticPersonaDB,
)
from backend.lifecycle_service import (
    ApplicationNotFoundError,
    IneligibleApprovalViolationError,
    InvalidLifecycleTransitionError,
    LifecycleValidationError,
    MandatoryRemarksMissingError,
    PolicyConsistencyViolationError,
    UnauthorizedActorError,
    abandon_application,
    approve_application,
    create_application,
    disburse_benefit,
    get_application_audit_history,
    get_application_by_id,
    get_application_by_number,
    get_application_evaluation_history,
    get_latest_pre_approval_evaluation,
    record_eligibility_evaluation,
    reject_application,
    resubmit_application,
    revoke_application,
    send_back_for_correction,
    start_desk_scrutiny,
    submit_application,
    transition_application_status,
)


class TestApplicationLifecycleService(unittest.TestCase):
    """Isolated in-memory test suite for student application lifecycle service."""

    def setUp(self):
        # Create a fresh isolated in-memory SQLite engine per test
        self.engine: Engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            echo=False
        )

        # Enforce foreign keys on SQLite
        @event.listens_for(self.engine, "connect")
        def set_sqlite_fk(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        # Initialize schema
        init_db(self.engine)

        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False
        )
        self.session: Session = self.SessionLocal()

        # Seed standard policy, configuration, and synthetic persona
        self.policy = PolicyDB(
            scheme_code="RCSMS-EBC",
            scheme_name="Rajarshi Chhatrapati Shahu Maharaj Shikshan Shulk Shishyavrutti Yojna",
            department="Higher and Technical Education",
            target_beneficiary="Economically Backward Class College Students",
            is_active=True
        )
        self.session.add(self.policy)
        self.session.flush()

        self.policy_config = PolicyConfigurationDB(
            policy_id=self.policy.id,
            config_version="v2026.1-baseline",
            policy_source_reference="GR No. TEM-2018/CR-123/TE-4",
            max_income_limit=800000.0,
            min_attendance_pct=75.0,
            baseline_relief_rate=0.50,
            max_family_beneficiaries=2,
            allows_concurrent_scholarship=False,
            requires_cap_admission=True,
            is_verified_statutory_rule=True
        )
        self.session.add(self.policy_config)
        self.session.flush()

        self.persona = SyntheticPersonaDB(
            persona_id="STU-DHULE-001",
            name="Aarav Deshmukh",
            gender="Male",
            age=19,
            district="Dhule",
            taluka="Dhule",
            is_maharashtra_domicile=True,
            caste_category="General-EBC",
            family_income=320000.0,
            first_generation_learner=True,
            parental_education_level="Secondary",
            course_name="B.Tech Computer Engineering",
            course_level="Undergraduate",
            is_professional_course=True,
            institution_type="Government",
            admission_mode="CAP",
            annual_tuition_fee=90000.0,
            attendance_percentage=82.0,
            previous_year_passed=True,
            previous_year_percentage=78.5,
            academic_gap_years=0,
            family_beneficiaries_count=0,
            has_other_scholarship=False,
            digital_literacy=0.75,
            initial_awareness=0.50,
            document_readiness=0.80,
            financial_urgency=0.70,
            peer_network_support=0.60,
            institutional_trust=0.70,
            personality_traits_json={"patience": 0.7, "diligence": 0.8}
        )
        self.session.add(self.persona)
        self.session.commit()

    def tearDown(self):
        self.session.rollback()
        self.session.close()
        self.engine.dispose()

    # -------------------------------------------------------------------------
    # 1. Application Creation & Snapshot Immutability
    # -------------------------------------------------------------------------
    def test_create_application_success(self):
        """Verifies initial creation, draft status, snapshot fields, evaluation row, and audit entry."""
        app = create_application(
            session=self.session,
            persona_id=self.persona.persona_id,
            policy_id=self.policy.id,
            evaluation_policy_config_id=self.policy_config.id,
            claimed_fee_relief_inr=45000.0,
            is_eligible=True,
            ineligibility_reasons=None,
            performed_by=AuditActor.STUDENT
        )
        self.session.commit()

        self.assertIsNotNone(app.id)
        self.assertEqual(app.current_status, ApplicationLifecycleStatus.DRAFT.value)
        self.assertTrue(app.initial_eligibility_snapshot)
        self.assertIsNone(app.initial_ineligibility_reasons_json)
        self.assertEqual(app.claimed_fee_relief_inr, 45000.0)
        self.assertEqual(app.approved_fee_relief_inr, 0.0)
        self.assertEqual(app.disbursed_amount_inr, 0.0)

        # Check evaluation history has exactly 1 initial evaluation row
        evals = get_application_evaluation_history(self.session, app.id)
        self.assertEqual(len(evals), 1)
        self.assertEqual(evals[0].evaluation_stage, ApplicationEvaluationStage.INITIAL_ASSESSMENT.value)
        self.assertTrue(evals[0].is_eligible)
        self.assertEqual(evals[0].evaluated_by, EvaluationActor.SYSTEM_ENGINE.value)

        # Check audit history has exactly 1 initiation row
        audits = get_application_audit_history(self.session, app.id)
        self.assertEqual(len(audits), 1)
        self.assertEqual(audits[0].from_status, ApplicationLifecycleStatus.DRAFT.value)
        self.assertEqual(audits[0].to_status, ApplicationLifecycleStatus.DRAFT.value)
        self.assertEqual(audits[0].performed_by, AuditActor.STUDENT.value)

    def test_create_application_policy_mismatch(self):
        """Asserts PolicyConsistencyViolationError when policy_config belongs to another policy."""
        # Create second policy
        policy2 = PolicyDB(
            scheme_code="OBC-SCHEME",
            scheme_name="OBC Scholarship",
            department="Social Welfare",
            target_beneficiary="OBC Students",
            is_active=True
        )
        self.session.add(policy2)
        self.session.flush()

        with self.assertRaises(PolicyConsistencyViolationError):
            create_application(
                session=self.session,
                persona_id=self.persona.persona_id,
                policy_id=policy2.id,  # Policy 2
                evaluation_policy_config_id=self.policy_config.id,  # Config belongs to Policy 1!
                claimed_fee_relief_inr=45000.0,
                is_eligible=True
            )
        self.session.rollback()

    def test_duplicate_application_number_fails(self):
        """Verifies that duplicate application number violates database unique constraint."""
        app1 = create_application(
            session=self.session,
            persona_id=self.persona.persona_id,
            policy_id=self.policy.id,
            evaluation_policy_config_id=self.policy_config.id,
            claimed_fee_relief_inr=45000.0,
            is_eligible=True,
            application_number="MHD-2026-DUP-001"
        )
        self.session.commit()

        with self.assertRaises(IntegrityError):
            create_application(
                session=self.session,
                persona_id=self.persona.persona_id,
                policy_id=self.policy.id,
                evaluation_policy_config_id=self.policy_config.id,
                claimed_fee_relief_inr=45000.0,
                is_eligible=True,
                application_number="MHD-2026-DUP-001"
            )
            self.session.commit()
        self.session.rollback()

    # -------------------------------------------------------------------------
    # 2. Complete Happy-Path Lifecycle & Approval Guard
    # -------------------------------------------------------------------------
    def test_valid_submission_and_scrutiny_lifecycle(self):
        """Walkthrough: DRAFT -> SUBMITTED -> UNDER_VERIFICATION -> DESK_SCRUTINY -> APPROVED -> BENEFIT_DISBURSED."""
        app = create_application(
            session=self.session,
            persona_id=self.persona.persona_id,
            policy_id=self.policy.id,
            evaluation_policy_config_id=self.policy_config.id,
            claimed_fee_relief_inr=45000.0,
            is_eligible=True
        )
        self.session.commit()

        # 1. Student submits application
        submit_application(self.session, app.id, performed_by=AuditActor.STUDENT)
        self.session.commit()
        self.assertEqual(app.current_status, ApplicationLifecycleStatus.SUBMITTED.value)
        self.assertIsNotNone(app.submission_timestamp)

        # 2. Desk scrutiny starts
        start_desk_scrutiny(self.session, app.id, performed_by=AuditActor.SCRUTINY_OFFICER)
        self.session.commit()
        self.assertEqual(app.current_status, ApplicationLifecycleStatus.UNDER_VERIFICATION.value)
        self.assertIsNotNone(app.scrutiny_timestamp)

        # 3. Desk scrutiny formal evaluation records applicant is eligible
        record_eligibility_evaluation(
            session=self.session,
            application_id=app.id,
            evaluation_stage=ApplicationEvaluationStage.DESK_SCRUTINY,
            is_eligible=True,
            policy_config_id=self.policy_config.id,
            evaluated_by=EvaluationActor.SCRUTINY_OFFICER,
            evaluation_notes="Tahsildar income certificate and CAP allotment letter verified in order."
        )
        self.session.commit()
        self.assertTrue(app.latest_verified_eligibility_status)
        self.assertIsNotNone(app.latest_verification_timestamp)

        # 4. Officer approves application
        approve_application(
            session=self.session,
            application_id=app.id,
            remarks="Sanctioned for 50% tuition reimbursement.",
            approved_amount=45000.0,
            performed_by=AuditActor.SCRUTINY_OFFICER
        )
        self.session.commit()
        self.assertEqual(app.current_status, ApplicationLifecycleStatus.APPROVED.value)
        self.assertEqual(app.approved_fee_relief_inr, 45000.0)
        self.assertIsNotNone(app.approval_timestamp)

        # 5. Disbursement completed
        disburse_benefit(
            session=self.session,
            application_id=app.id,
            disbursed_amount=45000.0,
            payment_reference="MahaDBT-NEFT-20261120-00123",
            performed_by=AuditActor.DISBURSEMENT_OFFICER
        )
        self.session.commit()
        self.assertEqual(app.current_status, ApplicationLifecycleStatus.BENEFIT_DISBURSED.value)
        self.assertEqual(app.disbursed_amount_inr, 45000.0)
        self.assertIsNotNone(app.disbursement_timestamp)

        # Check total audit entries: initial draft + submit + start scrutiny + approve + disburse = 5 entries
        audits = get_application_audit_history(self.session, app.id)
        self.assertEqual(len(audits), 5)
        self.assertEqual(audits[-1].to_status, ApplicationLifecycleStatus.BENEFIT_DISBURSED.value)

    # -------------------------------------------------------------------------
    # 3. Approval Guard Enforcement: Pre-Approval Evaluations Required
    # -------------------------------------------------------------------------
    def test_approval_blocked_when_pre_approval_evaluation_missing(self):
        """Approval must fail if no formal pre-approval verification evaluation exists."""
        app = create_application(
            session=self.session,
            persona_id=self.persona.persona_id,
            policy_id=self.policy.id,
            evaluation_policy_config_id=self.policy_config.id,
            claimed_fee_relief_inr=45000.0,
            is_eligible=True  # Initial snapshot is eligible, but NO pre-approval scrutiny has happened!
        )
        submit_application(self.session, app.id)
        start_desk_scrutiny(self.session, app.id)
        self.session.commit()

        # Attempt to approve without recording desk scrutiny evaluation
        with self.assertRaises(IneligibleApprovalViolationError):
            approve_application(
                self.session,
                app.id,
                remarks="Premature approval without scrutiny evaluation",
                performed_by=AuditActor.SCRUTINY_OFFICER
            )
        self.session.rollback()

    def test_approval_blocked_when_latest_evaluation_ineligible(self):
        """Approval must fail if the latest pre-approval verification evaluation is ineligible."""
        app = create_application(
            session=self.session,
            persona_id=self.persona.persona_id,
            policy_id=self.policy.id,
            evaluation_policy_config_id=self.policy_config.id,
            claimed_fee_relief_inr=45000.0,
            is_eligible=True
        )
        submit_application(self.session, app.id)
        start_desk_scrutiny(self.session, app.id)
        self.session.commit()

        # Desk scrutiny finds income certificate fraud / ineligibility
        record_eligibility_evaluation(
            session=self.session,
            application_id=app.id,
            evaluation_stage=ApplicationEvaluationStage.DESK_SCRUTINY,
            is_eligible=False,
            policy_config_id=self.policy_config.id,
            evaluated_by=EvaluationActor.SCRUTINY_OFFICER,
            failure_reasons=["Income certificate exceeds ceiling upon Tahsildar portal verification"]
        )
        self.session.commit()

        with self.assertRaises(IneligibleApprovalViolationError):
            approve_application(
                self.session,
                app.id,
                remarks="Attempting unauthorized approval for ineligible file",
                performed_by=AuditActor.SCRUTINY_OFFICER
            )
        self.session.rollback()

    def test_post_sanction_evaluation_cannot_authorize_approval(self):
        """Evaluations recorded under POST_SANCTION_AUDIT must never authorize an initial approval."""
        app = create_application(
            session=self.session,
            persona_id=self.persona.persona_id,
            policy_id=self.policy.id,
            evaluation_policy_config_id=self.policy_config.id,
            claimed_fee_relief_inr=45000.0,
            is_eligible=False  # Ineligible
        )
        submit_application(self.session, app.id)
        start_desk_scrutiny(self.session, app.id)
        self.session.commit()

        # An audit evaluation is recorded (e.g. error or audit log entry)
        record_eligibility_evaluation(
            session=self.session,
            application_id=app.id,
            evaluation_stage=ApplicationEvaluationStage.POST_SANCTION_AUDIT,
            is_eligible=True,  # Audit claims eligible, but stage is post-sanction!
            policy_config_id=self.policy_config.id,
            evaluated_by=EvaluationActor.AUDIT_OFFICER
        )
        self.session.commit()

        # Approval guard must ignore POST_SANCTION_AUDIT and reject approval
        with self.assertRaises(IneligibleApprovalViolationError):
            approve_application(
                self.session,
                app.id,
                remarks="Post sanction audit cannot authorize initial approval",
                performed_by=AuditActor.SCRUTINY_OFFICER
            )
        self.session.rollback()

    # -------------------------------------------------------------------------
    # 4. Send Back for Correction, Resubmission & Re-evaluation Workflow
    # -------------------------------------------------------------------------
    def test_send_back_resubmit_re_evaluation_approval(self):
        """
        Full resubmission lifecycle:
        1. Applicant initially evaluated as ineligible (missing income certificate).
        2. Scrutiny sends file back for correction.
        3. Applicant resubmits with valid documents.
        4. Re-evaluation explicitly records is_eligible = True.
        5. Approval guard permits approval based on latest re-evaluation.
        6. Initial snapshot remains False (immutable).
        """
        app = create_application(
            session=self.session,
            persona_id=self.persona.persona_id,
            policy_id=self.policy.id,
            evaluation_policy_config_id=self.policy_config.id,
            claimed_fee_relief_inr=45000.0,
            is_eligible=False,
            ineligibility_reasons=["Expired Income Certificate"]
        )
        submit_application(self.session, app.id)
        start_desk_scrutiny(self.session, app.id)
        self.session.commit()

        # Scrutiny records defective desk scrutiny evaluation
        record_eligibility_evaluation(
            session=self.session,
            application_id=app.id,
            evaluation_stage=ApplicationEvaluationStage.DESK_SCRUTINY,
            is_eligible=False,
            policy_config_id=self.policy_config.id,
            evaluated_by=EvaluationActor.SCRUTINY_OFFICER,
            failure_reasons=["Tahsildar certificate expired on 2026-03-31"]
        )
        self.session.commit()

        # 1. Send back for correction
        send_back_for_correction(
            self.session,
            app.id,
            reason="Please upload renewed FY 2026-27 Tahsildar Income Certificate.",
            performed_by=AuditActor.SCRUTINY_OFFICER
        )
        self.session.commit()
        self.assertEqual(app.current_status, ApplicationLifecycleStatus.SENT_BACK_FOR_CORRECTION.value)

        # 2. Resubmission by student
        resubmit_application(
            self.session,
            app.id,
            correction_summary="Uploaded fresh Tahsildar Certificate issued on 2026-06-15.",
            performed_by=AuditActor.STUDENT
        )
        self.session.commit()
        self.assertEqual(app.current_status, ApplicationLifecycleStatus.RESUBMITTED.value)

        # 3. Return to scrutiny queue
        start_desk_scrutiny(self.session, app.id, performed_by=AuditActor.SCRUTINY_OFFICER)
        self.session.commit()
        self.assertEqual(app.current_status, ApplicationLifecycleStatus.UNDER_VERIFICATION.value)

        # 4. Desk officer performs formal re-evaluation under RESUBMISSION_RE_EVALUATION
        record_eligibility_evaluation(
            session=self.session,
            application_id=app.id,
            evaluation_stage=ApplicationEvaluationStage.RESUBMISSION_RE_EVALUATION,
            is_eligible=True,
            policy_config_id=self.policy_config.id,
            evaluated_by=EvaluationActor.SCRUTINY_OFFICER,
            evaluation_notes="Renewed income certificate verified successfully."
        )
        self.session.commit()

        # 5. Now approval must succeed!
        approve_application(
            session=self.session,
            application_id=app.id,
            remarks="Sanctioned after successful document defect resolution.",
            approved_amount=45000.0,
            performed_by=AuditActor.SCRUTINY_OFFICER
        )
        self.session.commit()
        self.assertEqual(app.current_status, ApplicationLifecycleStatus.APPROVED.value)

        # 6. Verify initial snapshot immutability
        self.assertFalse(app.initial_eligibility_snapshot)
        self.assertEqual(app.initial_ineligibility_reasons_json, ["Expired Income Certificate"])
        self.assertTrue(app.latest_verified_eligibility_status)

        # Verify evaluation history preservation: Initial + Scrutiny + Re-evaluation = 3 evaluations
        eval_history = get_application_evaluation_history(self.session, app.id)
        self.assertEqual(len(eval_history), 3)
        self.assertEqual(eval_history[0].evaluation_stage, ApplicationEvaluationStage.INITIAL_ASSESSMENT.value)
        self.assertEqual(eval_history[1].evaluation_stage, ApplicationEvaluationStage.DESK_SCRUTINY.value)
        self.assertEqual(eval_history[2].evaluation_stage, ApplicationEvaluationStage.RESUBMISSION_RE_EVALUATION.value)

    def test_resubmission_does_not_automatically_create_evaluation(self):
        """Resubmission must only update lifecycle state and audit log, NOT assume or generate an eligibility decision."""
        app = create_application(
            session=self.session,
            persona_id=self.persona.persona_id,
            policy_id=self.policy.id,
            evaluation_policy_config_id=self.policy_config.id,
            claimed_fee_relief_inr=45000.0,
            is_eligible=True
        )
        submit_application(self.session, app.id)
        start_desk_scrutiny(self.session, app.id)
        send_back_for_correction(self.session, app.id, reason="Correction required")
        self.session.commit()

        evals_before = len(get_application_evaluation_history(self.session, app.id))

        # Resubmit
        resubmit_application(self.session, app.id, correction_summary="Attached corrected marksheet")
        self.session.commit()

        evals_after = len(get_application_evaluation_history(self.session, app.id))
        self.assertEqual(evals_before, evals_after)  # No evaluation created automatically!

    # -------------------------------------------------------------------------
    # 5. Mandatory Remarks & Actor Authorization Enforcement
    # -------------------------------------------------------------------------
    def test_mandatory_remarks_enforced(self):
        """Transitions requiring mandatory remarks must raise MandatoryRemarksMissingError if omitted."""
        app = create_application(
            session=self.session,
            persona_id=self.persona.persona_id,
            policy_id=self.policy.id,
            evaluation_policy_config_id=self.policy_config.id,
            claimed_fee_relief_inr=45000.0,
            is_eligible=True
        )
        submit_application(self.session, app.id)
        start_desk_scrutiny(self.session, app.id)
        self.session.commit()

        # Send back without remarks -> MUST FAIL
        with self.assertRaises(MandatoryRemarksMissingError):
            send_back_for_correction(self.session, app.id, reason="")
        self.session.rollback()

        # Reject without remarks -> MUST FAIL
        with self.assertRaises(MandatoryRemarksMissingError):
            reject_application(self.session, app.id, reason="   ")
        self.session.rollback()

    def test_unauthorized_actor_enforced(self):
        """Unauthorized actor attempting transition must raise UnauthorizedActorError."""
        app = create_application(
            session=self.session,
            persona_id=self.persona.persona_id,
            policy_id=self.policy.id,
            evaluation_policy_config_id=self.policy_config.id,
            claimed_fee_relief_inr=45000.0,
            is_eligible=True
        )
        self.session.commit()

        # Scrutiny officer attempting to submit draft -> MUST FAIL
        with self.assertRaises(UnauthorizedActorError):
            submit_application(self.session, app.id, performed_by=AuditActor.SCRUTINY_OFFICER)
        self.session.rollback()

        # Legitimate submission by student
        submit_application(self.session, app.id, performed_by=AuditActor.STUDENT)
        self.session.commit()

        # Student attempting to start desk scrutiny -> MUST FAIL
        with self.assertRaises(UnauthorizedActorError):
            start_desk_scrutiny(self.session, app.id, performed_by=AuditActor.STUDENT)
        self.session.rollback()

    # -------------------------------------------------------------------------
    # 6. Forbidden Transitions & Terminal States
    # -------------------------------------------------------------------------
    def test_forbidden_lifecycle_transitions(self):
        """Verifies that invalid jumps across the state machine raise InvalidLifecycleTransitionError."""
        app = create_application(
            session=self.session,
            persona_id=self.persona.persona_id,
            policy_id=self.policy.id,
            evaluation_policy_config_id=self.policy_config.id,
            claimed_fee_relief_inr=45000.0,
            is_eligible=True
        )
        self.session.commit()

        # 1. DRAFT -> APPROVED (illegal bypass)
        with self.assertRaises(InvalidLifecycleTransitionError):
            transition_application_status(
                self.session, app.id,
                to_status=ApplicationLifecycleStatus.APPROVED,
                performed_by=AuditActor.SCRUTINY_OFFICER,
                reason="Bypass attempt"
            )
        self.session.rollback()

        # 2. DRAFT -> BENEFIT_DISBURSED
        with self.assertRaises(InvalidLifecycleTransitionError):
            transition_application_status(
                self.session, app.id,
                to_status=ApplicationLifecycleStatus.BENEFIT_DISBURSED,
                performed_by=AuditActor.DISBURSEMENT_OFFICER,
                reason="Direct disburse attempt"
            )
        self.session.rollback()

    def test_terminal_state_immutability(self):
        """Terminal states (BENEFIT_DISBURSED, REJECTED, REVOKED, ABANDONED) reject all further transitions."""
        app = create_application(
            session=self.session,
            persona_id=self.persona.persona_id,
            policy_id=self.policy.id,
            evaluation_policy_config_id=self.policy_config.id,
            claimed_fee_relief_inr=45000.0,
            is_eligible=False
        )
        submit_application(self.session, app.id)
        start_desk_scrutiny(self.session, app.id)
        reject_application(self.session, app.id, reason="Statutory income ceiling exceeded.")
        self.session.commit()
        self.assertEqual(app.current_status, ApplicationLifecycleStatus.REJECTED.value)

        # Attempt to transition REJECTED -> APPROVED -> MUST FAIL
        with self.assertRaises(InvalidLifecycleTransitionError):
            transition_application_status(
                self.session, app.id,
                to_status=ApplicationLifecycleStatus.APPROVED,
                performed_by=AuditActor.SCRUTINY_OFFICER,
                reason="Attempting to revive rejected file"
            )
        self.session.rollback()

    # -------------------------------------------------------------------------
    # 7. Revocation & Abandonment Workflows
    # -------------------------------------------------------------------------
    def test_revocation_workflow(self):
        """Approved file can be revoked post-sanction with mandatory remarks."""
        app = create_application(
            session=self.session,
            persona_id=self.persona.persona_id,
            policy_id=self.policy.id,
            evaluation_policy_config_id=self.policy_config.id,
            claimed_fee_relief_inr=45000.0,
            is_eligible=True
        )
        submit_application(self.session, app.id)
        start_desk_scrutiny(self.session, app.id)
        record_eligibility_evaluation(
            session=self.session,
            application_id=app.id,
            evaluation_stage=ApplicationEvaluationStage.DESK_SCRUTINY,
            is_eligible=True,
            policy_config_id=self.policy_config.id,
            evaluated_by=EvaluationActor.SCRUTINY_OFFICER
        )
        approve_application(self.session, app.id, remarks="Approved")
        self.session.commit()

        # Revoke sanction
        revoke_application(
            self.session,
            app.id,
            reason="Post-sanction audit detected dual scholarship in another university.",
            performed_by=AuditActor.SCRUTINY_OFFICER
        )
        self.session.commit()
        self.assertEqual(app.current_status, ApplicationLifecycleStatus.REVOKED.value)
        self.assertIsNotNone(app.revocation_timestamp)

    def test_abandon_workflow(self):
        """Application in DRAFT or SENT_BACK can be abandoned by student or system engine."""
        app = create_application(
            session=self.session,
            persona_id=self.persona.persona_id,
            policy_id=self.policy.id,
            evaluation_policy_config_id=self.policy_config.id,
            claimed_fee_relief_inr=45000.0,
            is_eligible=True
        )
        self.session.commit()

        abandon_application(self.session, app.id, reason="Student withdrew enrollment", performed_by=AuditActor.STUDENT)
        self.session.commit()
        self.assertEqual(app.current_status, ApplicationLifecycleStatus.ABANDONED.value)
        self.assertIsNotNone(app.abandoned_timestamp)

    # -------------------------------------------------------------------------
    # 8. Transaction Atomicity & Rollback Verification
    # -------------------------------------------------------------------------
    def test_transaction_atomicity_and_rollback(self):
        """Verifies that when an operation fails or rollback is issued, no state change or audit log persists."""
        app = create_application(
            session=self.session,
            persona_id=self.persona.persona_id,
            policy_id=self.policy.id,
            evaluation_policy_config_id=self.policy_config.id,
            claimed_fee_relief_inr=45000.0,
            is_eligible=True
        )
        self.session.commit()

        initial_audits_count = len(get_application_audit_history(self.session, app.id))
        self.assertEqual(app.current_status, ApplicationLifecycleStatus.DRAFT.value)

        # Open transactional block and attempt invalid transition
        try:
            with self.session.begin_nested():
                transition_application_status(
                    self.session,
                    app.id,
                    to_status=ApplicationLifecycleStatus.APPROVED,  # Invalid from DRAFT
                    performed_by=AuditActor.SCRUTINY_OFFICER,
                    reason="Invalid transition"
                )
        except InvalidLifecycleTransitionError:
            pass

        # Query fresh app from database
        fresh_app = get_application_by_id(self.session, app.id)
        self.assertEqual(fresh_app.current_status, ApplicationLifecycleStatus.DRAFT.value)
        final_audits_count = len(get_application_audit_history(self.session, app.id))
        self.assertEqual(initial_audits_count, final_audits_count)

    def test_disbursement_requires_positive_amount(self):
        """Disbursing zero or negative amount must raise LifecycleValidationError."""
        app = create_application(
            session=self.session,
            persona_id=self.persona.persona_id,
            policy_id=self.policy.id,
            evaluation_policy_config_id=self.policy_config.id,
            claimed_fee_relief_inr=45000.0,
            is_eligible=True
        )
        submit_application(self.session, app.id)
        start_desk_scrutiny(self.session, app.id)
        record_eligibility_evaluation(
            session=self.session,
            application_id=app.id,
            evaluation_stage=ApplicationEvaluationStage.DESK_SCRUTINY,
            is_eligible=True,
            policy_config_id=self.policy_config.id,
            evaluated_by=EvaluationActor.SCRUTINY_OFFICER
        )
        approve_application(self.session, app.id, remarks="Approved", approved_amount=45000.0)
        self.session.commit()

        with self.assertRaises(LifecycleValidationError):
            disburse_benefit(
                self.session,
                app.id,
                disbursed_amount=-1000.0,
                payment_reference="REF-001"
            )
        self.session.rollback()

    # -------------------------------------------------------------------------
    # 9. Additional Lifecycle Validation & Actor Safeguards
    # -------------------------------------------------------------------------
    def test_approval_with_zero_claimed_relief_and_no_explicit_amount_fails(self):
        """Approval without explicit approved_amount fails if claimed fee relief is zero."""
        app = create_application(
            session=self.session,
            persona_id=self.persona.persona_id,
            policy_id=self.policy.id,
            evaluation_policy_config_id=self.policy_config.id,
            claimed_fee_relief_inr=0.0,
            is_eligible=True,
        )
        submit_application(self.session, app.id)
        start_desk_scrutiny(self.session, app.id)
        record_eligibility_evaluation(
            session=self.session,
            application_id=app.id,
            evaluation_stage=ApplicationEvaluationStage.DESK_SCRUTINY,
            is_eligible=True,
            policy_config_id=self.policy_config.id,
            evaluated_by=EvaluationActor.SCRUTINY_OFFICER,
        )
        self.session.commit()

        with self.assertRaises(LifecycleValidationError):
            approve_application(
                self.session,
                app.id,
                remarks="Approving with 0 claimed and no explicit amount",
                approved_amount=None,
                performed_by=AuditActor.SCRUTINY_OFFICER,
            )
        self.session.rollback()

    def test_approval_with_zero_claimed_relief_and_explicit_positive_amount_succeeds(self):
        """Approval succeeds with zero claimed fee relief if explicit positive approved_amount is provided."""
        app = create_application(
            session=self.session,
            persona_id=self.persona.persona_id,
            policy_id=self.policy.id,
            evaluation_policy_config_id=self.policy_config.id,
            claimed_fee_relief_inr=0.0,
            is_eligible=True,
        )
        submit_application(self.session, app.id)
        start_desk_scrutiny(self.session, app.id)
        record_eligibility_evaluation(
            session=self.session,
            application_id=app.id,
            evaluation_stage=ApplicationEvaluationStage.DESK_SCRUTINY,
            is_eligible=True,
            policy_config_id=self.policy_config.id,
            evaluated_by=EvaluationActor.SCRUTINY_OFFICER,
        )
        self.session.commit()

        approve_application(
            self.session,
            app.id,
            remarks="Explicit sanctioned relief determined by scrutiny officer",
            approved_amount=35000.0,
            performed_by=AuditActor.SCRUTINY_OFFICER,
        )
        self.session.commit()

        self.assertEqual(app.current_status, ApplicationLifecycleStatus.APPROVED.value)
        self.assertEqual(app.approved_fee_relief_inr, 35000.0)
        self.assertIsNotNone(app.approval_timestamp)

    def test_unauthorized_actor_disbursement_enforced(self):
        """Unauthorized actor attempting benefit disbursement raises UnauthorizedActorError."""
        app = create_application(
            session=self.session,
            persona_id=self.persona.persona_id,
            policy_id=self.policy.id,
            evaluation_policy_config_id=self.policy_config.id,
            claimed_fee_relief_inr=45000.0,
            is_eligible=True,
        )
        submit_application(self.session, app.id)
        start_desk_scrutiny(self.session, app.id)
        record_eligibility_evaluation(
            session=self.session,
            application_id=app.id,
            evaluation_stage=ApplicationEvaluationStage.DESK_SCRUTINY,
            is_eligible=True,
            policy_config_id=self.policy_config.id,
            evaluated_by=EvaluationActor.SCRUTINY_OFFICER,
        )
        approve_application(self.session, app.id, remarks="Approved", approved_amount=45000.0)
        self.session.commit()

        with self.assertRaises(UnauthorizedActorError):
            disburse_benefit(
                self.session,
                app.id,
                disbursed_amount=45000.0,
                payment_reference="MahaDBT-NEFT-20261120-00999",
                performed_by=AuditActor.STUDENT,
            )
        self.session.rollback()

    def test_unauthorized_actor_revocation_enforced(self):
        """Unauthorized actor attempting application revocation raises UnauthorizedActorError."""
        app = create_application(
            session=self.session,
            persona_id=self.persona.persona_id,
            policy_id=self.policy.id,
            evaluation_policy_config_id=self.policy_config.id,
            claimed_fee_relief_inr=45000.0,
            is_eligible=True,
        )
        submit_application(self.session, app.id)
        start_desk_scrutiny(self.session, app.id)
        record_eligibility_evaluation(
            session=self.session,
            application_id=app.id,
            evaluation_stage=ApplicationEvaluationStage.DESK_SCRUTINY,
            is_eligible=True,
            policy_config_id=self.policy_config.id,
            evaluated_by=EvaluationActor.SCRUTINY_OFFICER,
        )
        approve_application(self.session, app.id, remarks="Approved", approved_amount=45000.0)
        self.session.commit()

        with self.assertRaises(UnauthorizedActorError):
            revoke_application(
                self.session,
                app.id,
                reason="Student cannot revoke approved sanction",
                performed_by=AuditActor.STUDENT,
            )
        self.session.rollback()

    def test_unauthorized_actor_resubmission_enforced(self):
        """Unauthorized actor attempting resubmission raises UnauthorizedActorError."""
        app = create_application(
            session=self.session,
            persona_id=self.persona.persona_id,
            policy_id=self.policy.id,
            evaluation_policy_config_id=self.policy_config.id,
            claimed_fee_relief_inr=45000.0,
            is_eligible=True,
        )
        submit_application(self.session, app.id)
        start_desk_scrutiny(self.session, app.id)
        send_back_for_correction(self.session, app.id, reason="Document unclear")
        self.session.commit()

        with self.assertRaises(UnauthorizedActorError):
            resubmit_application(
                self.session,
                app.id,
                correction_summary="Officer cannot resubmit on behalf of student",
                performed_by=AuditActor.SCRUTINY_OFFICER,
            )
        self.session.rollback()


if __name__ == "__main__":
    unittest.main()
