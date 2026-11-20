"""
Application Lifecycle Service Layer for Maharashtra Policy Simulator.
Provides administrative student application lifecycle management, state transitions,
deterministic approval guards, eligibility evaluation history, and audit trails.
Faithfully implements the specification in docs/database_schema.md.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

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


# -----------------------------------------------------------------------------
# 1. Domain Exceptions
# -----------------------------------------------------------------------------
class LifecycleServiceError(Exception):
    """Base exception for all application lifecycle service operations."""
    pass


class LifecycleValidationError(LifecycleServiceError):
    """Raised when application financial amounts or parameters fail validation."""
    pass


class ApplicationNotFoundError(LifecycleServiceError):
    """Raised when an application record is not found."""
    pass


class InvalidLifecycleTransitionError(LifecycleServiceError):
    """Raised when a lifecycle status transition violates the state machine rules."""
    pass


class IneligibleApprovalViolationError(LifecycleServiceError):
    """Raised when attempting to approve an application without verified statutory eligibility."""
    pass


class MandatoryRemarksMissingError(LifecycleServiceError):
    """Raised when an operation requiring mandatory remarks is submitted without remarks."""
    pass


class UnauthorizedActorError(LifecycleServiceError):
    """Raised when an actor is not authorized to execute the requested state transition."""
    pass


class PolicyConsistencyViolationError(LifecycleServiceError):
    """Raised when referenced policy and policy configuration do not belong to the same scheme."""
    pass


# -----------------------------------------------------------------------------
# 2. State Machine Rules & Matrices
# -----------------------------------------------------------------------------

# Valid state transitions from docs/database_schema.md Section 6.2 & 6.3
VALID_TRANSITIONS: dict[ApplicationLifecycleStatus, set[ApplicationLifecycleStatus]] = {
    ApplicationLifecycleStatus.DRAFT: {
        ApplicationLifecycleStatus.SUBMITTED,
        ApplicationLifecycleStatus.ABANDONED,
    },
    ApplicationLifecycleStatus.SUBMITTED: {
        ApplicationLifecycleStatus.UNDER_VERIFICATION,
        ApplicationLifecycleStatus.ABANDONED,
    },
    ApplicationLifecycleStatus.UNDER_VERIFICATION: {
        ApplicationLifecycleStatus.APPROVED,
        ApplicationLifecycleStatus.SENT_BACK_FOR_CORRECTION,
        ApplicationLifecycleStatus.REJECTED,
    },
    ApplicationLifecycleStatus.SENT_BACK_FOR_CORRECTION: {
        ApplicationLifecycleStatus.RESUBMITTED,
        ApplicationLifecycleStatus.ABANDONED,
    },
    ApplicationLifecycleStatus.RESUBMITTED: {
        ApplicationLifecycleStatus.UNDER_VERIFICATION,
    },
    ApplicationLifecycleStatus.APPROVED: {
        ApplicationLifecycleStatus.BENEFIT_DISBURSED,
        ApplicationLifecycleStatus.REVOKED,
    },
    # Terminal states: no further transitions permitted
    ApplicationLifecycleStatus.BENEFIT_DISBURSED: set(),
    ApplicationLifecycleStatus.REJECTED: set(),
    ApplicationLifecycleStatus.REVOKED: set(),
    ApplicationLifecycleStatus.ABANDONED: set(),
}

# Authorized actors per permitted transition
AUTHORIZED_ACTORS: dict[tuple[ApplicationLifecycleStatus, ApplicationLifecycleStatus], set[str]] = {
    (ApplicationLifecycleStatus.DRAFT, ApplicationLifecycleStatus.SUBMITTED): {
        AuditActor.STUDENT.value
    },
    (ApplicationLifecycleStatus.DRAFT, ApplicationLifecycleStatus.ABANDONED): {
        AuditActor.STUDENT.value,
        AuditActor.SYSTEM_ENGINE.value,
    },
    (ApplicationLifecycleStatus.SUBMITTED, ApplicationLifecycleStatus.UNDER_VERIFICATION): {
        AuditActor.SCRUTINY_OFFICER.value
    },
    (ApplicationLifecycleStatus.SUBMITTED, ApplicationLifecycleStatus.ABANDONED): {
        AuditActor.STUDENT.value,
        AuditActor.SYSTEM_ENGINE.value,
    },
    (ApplicationLifecycleStatus.UNDER_VERIFICATION, ApplicationLifecycleStatus.APPROVED): {
        AuditActor.SCRUTINY_OFFICER.value
    },
    (ApplicationLifecycleStatus.UNDER_VERIFICATION, ApplicationLifecycleStatus.SENT_BACK_FOR_CORRECTION): {
        AuditActor.SCRUTINY_OFFICER.value
    },
    (ApplicationLifecycleStatus.UNDER_VERIFICATION, ApplicationLifecycleStatus.REJECTED): {
        AuditActor.SCRUTINY_OFFICER.value
    },
    (ApplicationLifecycleStatus.SENT_BACK_FOR_CORRECTION, ApplicationLifecycleStatus.RESUBMITTED): {
        AuditActor.STUDENT.value
    },
    (ApplicationLifecycleStatus.SENT_BACK_FOR_CORRECTION, ApplicationLifecycleStatus.ABANDONED): {
        AuditActor.STUDENT.value,
        AuditActor.SYSTEM_ENGINE.value,
    },
    (ApplicationLifecycleStatus.RESUBMITTED, ApplicationLifecycleStatus.UNDER_VERIFICATION): {
        AuditActor.SCRUTINY_OFFICER.value
    },
    (ApplicationLifecycleStatus.APPROVED, ApplicationLifecycleStatus.BENEFIT_DISBURSED): {
        AuditActor.DISBURSEMENT_OFFICER.value
    },
    (ApplicationLifecycleStatus.APPROVED, ApplicationLifecycleStatus.REVOKED): {
        AuditActor.SCRUTINY_OFFICER.value
    },
}

# Transitions requiring mandatory remarks
MANDATORY_REMARKS_TRANSITIONS: set[ApplicationLifecycleStatus] = {
    ApplicationLifecycleStatus.SENT_BACK_FOR_CORRECTION,
    ApplicationLifecycleStatus.REJECTED,
    ApplicationLifecycleStatus.APPROVED,
    ApplicationLifecycleStatus.REVOKED,
    ApplicationLifecycleStatus.BENEFIT_DISBURSED,
    ApplicationLifecycleStatus.RESUBMITTED,
}


# -----------------------------------------------------------------------------
# 3. Core Service Implementation
# -----------------------------------------------------------------------------

def create_application(
    session: Session,
    persona_id: str,
    policy_id: int,
    evaluation_policy_config_id: int,
    claimed_fee_relief_inr: float,
    is_eligible: bool,
    ineligibility_reasons: Optional[List[str]] = None,
    application_number: Optional[str] = None,
    run_id: Optional[str] = None,
    performed_by: AuditActor | str = AuditActor.STUDENT,
    evaluation_notes: Optional[str] = None,
) -> ApplicationRecordDB:
    """
    Creates a new student scholarship application file in DRAFT status.
    Permanently stamps the immutable initial statutory eligibility snapshot
    and creates the initial evaluation and audit history records.
    Caller owns the transaction and must commit upon success.
    """
    # 1. Validate policy and configuration existence and cross-table consistency
    policy = session.get(PolicyDB, policy_id)
    if policy is None:
        raise PolicyConsistencyViolationError(f"Policy ID {policy_id} not found.")

    config = session.get(PolicyConfigurationDB, evaluation_policy_config_id)
    if config is None:
        raise PolicyConsistencyViolationError(f"PolicyConfiguration ID {evaluation_policy_config_id} not found.")

    if config.policy_id != policy_id:
        raise PolicyConsistencyViolationError(
            f"PolicyConfiguration {config.id} belongs to policy {config.policy_id}, "
            f"which does not match application policy {policy_id}."
        )

    persona = session.get(SyntheticPersonaDB, persona_id)
    if persona is None:
        raise ApplicationNotFoundError(f"SyntheticPersona ID '{persona_id}' not found.")

    if claimed_fee_relief_inr < 0:
        raise LifecycleValidationError("Claimed fee relief amount cannot be negative.")

    # 2. Generate unique application number if not explicitly provided
    now_utc = datetime.now(timezone.utc)
    if not application_number:
        application_number = f"MHD-{now_utc.year}-{policy.scheme_code}-{uuid.uuid4().hex[:8].upper()}"

    actor_val = performed_by.value if isinstance(performed_by, Enum) else performed_by

    # 3. Create ApplicationRecordDB with immutable initial snapshot
    app = ApplicationRecordDB(
        application_number=application_number,
        persona_id=persona_id,
        policy_id=policy_id,
        evaluation_policy_config_id=evaluation_policy_config_id,
        run_id=run_id,
        current_status=ApplicationLifecycleStatus.DRAFT.value,
        initial_eligibility_snapshot=is_eligible,
        initial_ineligibility_reasons_json=ineligibility_reasons,
        evaluated_at=now_utc,
        latest_verified_eligibility_status=None,
        latest_verification_policy_config_id=None,
        latest_verification_timestamp=None,
        claimed_fee_relief_inr=claimed_fee_relief_inr,
        approved_fee_relief_inr=0.0,
        disbursed_amount_inr=0.0,
        created_at=now_utc,
        updated_at=now_utc,
    )
    session.add(app)
    session.flush()

    # 4. Insert initial assessment event in application_eligibility_evaluations
    init_eval = ApplicationEligibilityEvaluationDB(
        application_id=app.id,
        evaluation_stage=ApplicationEvaluationStage.INITIAL_ASSESSMENT.value,
        is_eligible=is_eligible,
        failure_reasons_json=ineligibility_reasons,
        policy_config_id=evaluation_policy_config_id,
        evaluated_by=EvaluationActor.SYSTEM_ENGINE.value,
        evaluation_notes=evaluation_notes or "Initial eligibility snapshot recorded at application initiation",
        evaluated_at=now_utc,
    )
    session.add(init_eval)

    # 5. Insert initiation entry in application_audit_logs
    init_audit = ApplicationAuditLogDB(
        application_id=app.id,
        from_status=ApplicationLifecycleStatus.DRAFT.value,
        to_status=ApplicationLifecycleStatus.DRAFT.value,
        reason_or_remarks="Application file initiated in DRAFT status",
        performed_by=actor_val,
        timestamp=now_utc,
    )
    session.add(init_audit)
    session.flush()

    return app


def record_eligibility_evaluation(
    session: Session,
    application_id: int,
    evaluation_stage: ApplicationEvaluationStage | str,
    is_eligible: bool,
    policy_config_id: int,
    evaluated_by: EvaluationActor | str,
    failure_reasons: Optional[List[str]] = None,
    evaluation_notes: Optional[str] = None,
) -> ApplicationEligibilityEvaluationDB:
    """
    Records an immutable eligibility evaluation event in application_eligibility_evaluations.
    Pre-approval scrutiny/re-evaluation updates latest_verified_* metadata on the application record.
    Post-sanction audit records are append-only and do NOT update pre-approval metadata.
    Initial eligibility snapshot fields are NEVER modified.
    Caller owns the transaction and must commit upon success.
    """
    app = session.get(ApplicationRecordDB, application_id)
    if app is None:
        raise ApplicationNotFoundError(f"Application ID {application_id} not found.")

    config = session.get(PolicyConfigurationDB, policy_config_id)
    if config is None:
        raise PolicyConsistencyViolationError(f"PolicyConfiguration ID {policy_config_id} not found.")

    if config.policy_id != app.policy_id:
        raise PolicyConsistencyViolationError(
            f"PolicyConfiguration {config.id} belongs to policy {config.policy_id}, "
            f"which does not match application policy {app.policy_id}."
        )

    stage_val = evaluation_stage.value if isinstance(evaluation_stage, Enum) else evaluation_stage
    actor_val = evaluated_by.value if isinstance(evaluated_by, Enum) else evaluated_by
    now_utc = datetime.now(timezone.utc)

    # 1. Create evaluation history record
    evaluation = ApplicationEligibilityEvaluationDB(
        application_id=app.id,
        evaluation_stage=stage_val,
        is_eligible=is_eligible,
        failure_reasons_json=failure_reasons,
        policy_config_id=policy_config_id,
        evaluated_by=actor_val,
        evaluation_notes=evaluation_notes,
        evaluated_at=now_utc,
    )
    session.add(evaluation)

    # 2. Update verification metadata ONLY for pre-approval evaluations
    if stage_val in (
        ApplicationEvaluationStage.DESK_SCRUTINY.value,
        ApplicationEvaluationStage.RESUBMISSION_RE_EVALUATION.value,
    ):
        app.latest_verified_eligibility_status = is_eligible
        app.latest_verification_policy_config_id = policy_config_id
        app.latest_verification_timestamp = now_utc
        app.updated_at = now_utc

    session.flush()
    return evaluation


def get_latest_pre_approval_evaluation(
    session: Session, application_id: int
) -> Optional[ApplicationEligibilityEvaluationDB]:
    """
    Returns the latest formal pre-approval eligibility evaluation record
    (DESK_SCRUTINY or RESUBMISSION_RE_EVALUATION) for an application file.
    Explicitly ignores POST_SANCTION_AUDIT and INITIAL_ASSESSMENT evaluations.
    """
    stmt = (
        select(ApplicationEligibilityEvaluationDB)
        .where(
            ApplicationEligibilityEvaluationDB.application_id == application_id,
            ApplicationEligibilityEvaluationDB.evaluation_stage.in_([
                ApplicationEvaluationStage.DESK_SCRUTINY.value,
                ApplicationEvaluationStage.RESUBMISSION_RE_EVALUATION.value,
            ]),
        )
        .order_by(
            ApplicationEligibilityEvaluationDB.evaluated_at.desc(),
            ApplicationEligibilityEvaluationDB.id.desc(),
        )
    )
    return session.scalars(stmt).first()


def validate_lifecycle_transition(
    session: Session,
    application: ApplicationRecordDB,
    to_status: ApplicationLifecycleStatus,
    performed_by: str,
    reason: Optional[str] = None,
    approved_amount: Optional[float] = None,
    disbursed_amount: Optional[float] = None,
) -> None:
    """
    Deterministically validates whether a requested lifecycle transition is permitted.
    Enforces state machine rules, actor authorizations, mandatory remarks,
    and the final approval guard. Raises specific LifecycleServiceError subclasses if invalid.
    """
    try:
        current_status_enum = ApplicationLifecycleStatus(application.current_status)
    except ValueError:
        raise InvalidLifecycleTransitionError(
            f"Application has unrecognized current status: '{application.current_status}'"
        )

    # 1. State Machine Validity Check
    allowed_targets = VALID_TRANSITIONS.get(current_status_enum, set())
    if to_status not in allowed_targets:
        raise InvalidLifecycleTransitionError(
            f"Transition from '{current_status_enum.value}' to '{to_status.value}' is forbidden."
        )

    # 2. Authorized Actor Check
    transition_key = (current_status_enum, to_status)
    authorized_actors = AUTHORIZED_ACTORS.get(transition_key, set())
    if performed_by not in authorized_actors:
        raise UnauthorizedActorError(
            f"Actor '{performed_by}' is not authorized to transition from "
            f"'{current_status_enum.value}' to '{to_status.value}'. "
            f"Authorized actors: {sorted(authorized_actors)}"
        )

    # 3. Mandatory Remarks Check
    if to_status in MANDATORY_REMARKS_TRANSITIONS:
        if not reason or not reason.strip():
            raise MandatoryRemarksMissingError(
                f"Transition to '{to_status.value}' requires mandatory remarks or justification."
            )

    # 4. Final Approval Guard Enforcement
    if to_status == ApplicationLifecycleStatus.APPROVED:
        latest_eval = get_latest_pre_approval_evaluation(session, application.id)
        if latest_eval is None:
            raise IneligibleApprovalViolationError(
                f"Application {application.application_number} cannot be approved: "
                "no formal pre-approval verification evaluation exists. "
                "Approval requires formal desk scrutiny verification."
            )
        if not latest_eval.is_eligible:
            raise IneligibleApprovalViolationError(
                f"Application {application.application_number} cannot be approved: "
                f"latest pre-approval evaluation (ID {latest_eval.id}, Stage {latest_eval.evaluation_stage}) "
                "determined the applicant is ineligible."
            )
        if approved_amount is not None:
            if approved_amount <= 0:
                raise LifecycleValidationError("Approved fee relief amount must be greater than zero.")
        else:
            if application.claimed_fee_relief_inr <= 0:
                raise LifecycleValidationError(
                    f"Application {application.application_number} cannot be approved without an explicit "
                    "positive approved_amount because claimed fee relief is zero or negative."
                )

    # 5. Disbursement Verification Check
    if to_status == ApplicationLifecycleStatus.BENEFIT_DISBURSED:
        amount = disbursed_amount if disbursed_amount is not None else application.approved_fee_relief_inr
        if amount <= 0:
            raise LifecycleValidationError("Disbursement amount must be greater than zero.")


def transition_application_status(
    session: Session,
    application_id: int,
    to_status: ApplicationLifecycleStatus | str,
    performed_by: AuditActor | str,
    reason: Optional[str] = None,
    approved_amount: Optional[float] = None,
    disbursed_amount: Optional[float] = None,
) -> ApplicationRecordDB:
    """
    Executes a status transition and appends an audit log in the caller's session.
    Validates state machine rules, actor authorizations, mandatory remarks, and approval guards.
    Caller owns the transaction and must commit upon success.
    """
    app = session.get(ApplicationRecordDB, application_id)
    if app is None:
        raise ApplicationNotFoundError(f"Application ID {application_id} not found.")

    to_status_enum = (
        ApplicationLifecycleStatus(to_status) if isinstance(to_status, str) else to_status
    )
    actor_val = performed_by.value if isinstance(performed_by, Enum) else performed_by

    # 1. Deterministic validation
    validate_lifecycle_transition(
        session=session,
        application=app,
        to_status=to_status_enum,
        performed_by=actor_val,
        reason=reason,
        approved_amount=approved_amount,
        disbursed_amount=disbursed_amount,
    )

    from_status_val = app.current_status
    now_utc = datetime.now(timezone.utc)

    # 2. Update application status and lifecycle timestamps
    app.current_status = to_status_enum.value
    app.updated_at = now_utc

    if to_status_enum == ApplicationLifecycleStatus.SUBMITTED:
        app.submission_timestamp = now_utc
    elif to_status_enum == ApplicationLifecycleStatus.UNDER_VERIFICATION:
        app.scrutiny_timestamp = now_utc
    elif to_status_enum == ApplicationLifecycleStatus.APPROVED:
        app.approval_timestamp = now_utc
        app.approved_fee_relief_inr = (
            approved_amount if approved_amount is not None else app.claimed_fee_relief_inr
        )
    elif to_status_enum == ApplicationLifecycleStatus.BENEFIT_DISBURSED:
        app.disbursement_timestamp = now_utc
        app.disbursed_amount_inr = (
            disbursed_amount if disbursed_amount is not None else app.approved_fee_relief_inr
        )
    elif to_status_enum == ApplicationLifecycleStatus.REJECTED:
        app.rejection_timestamp = now_utc
    elif to_status_enum == ApplicationLifecycleStatus.REVOKED:
        app.revocation_timestamp = now_utc
    elif to_status_enum == ApplicationLifecycleStatus.ABANDONED:
        app.abandoned_timestamp = now_utc

    # 3. Insert append-only audit log in same session
    audit_entry = ApplicationAuditLogDB(
        application_id=app.id,
        from_status=from_status_val,
        to_status=to_status_enum.value,
        reason_or_remarks=reason,
        performed_by=actor_val,
        timestamp=now_utc,
    )
    session.add(audit_entry)
    session.flush()

    return app


# -----------------------------------------------------------------------------
# 4. Specialized Lifecycle Workflow Helpers
# -----------------------------------------------------------------------------

def submit_application(
    session: Session,
    application_id: int,
    performed_by: AuditActor | str = AuditActor.STUDENT,
    remarks: Optional[str] = None,
) -> ApplicationRecordDB:
    """Transitions application from DRAFT to SUBMITTED."""
    return transition_application_status(
        session=session,
        application_id=application_id,
        to_status=ApplicationLifecycleStatus.SUBMITTED,
        performed_by=performed_by,
        reason=remarks,
    )


def start_desk_scrutiny(
    session: Session,
    application_id: int,
    performed_by: AuditActor | str = AuditActor.SCRUTINY_OFFICER,
    remarks: Optional[str] = None,
) -> ApplicationRecordDB:
    """Transitions application from SUBMITTED or RESUBMITTED to UNDER_VERIFICATION."""
    return transition_application_status(
        session=session,
        application_id=application_id,
        to_status=ApplicationLifecycleStatus.UNDER_VERIFICATION,
        performed_by=performed_by,
        reason=remarks,
    )


def send_back_for_correction(
    session: Session,
    application_id: int,
    reason: str,
    performed_by: AuditActor | str = AuditActor.SCRUTINY_OFFICER,
) -> ApplicationRecordDB:
    """Sends application back to applicant for document defect correction (remarks mandatory)."""
    return transition_application_status(
        session=session,
        application_id=application_id,
        to_status=ApplicationLifecycleStatus.SENT_BACK_FOR_CORRECTION,
        performed_by=performed_by,
        reason=reason,
    )


def resubmit_application(
    session: Session,
    application_id: int,
    correction_summary: str,
    performed_by: AuditActor | str = AuditActor.STUDENT,
) -> ApplicationRecordDB:
    """
    Applicant resubmits corrected application documents (remarks mandatory).
    Does NOT automatically create an eligibility evaluation result.
    """
    return transition_application_status(
        session=session,
        application_id=application_id,
        to_status=ApplicationLifecycleStatus.RESUBMITTED,
        performed_by=performed_by,
        reason=correction_summary,
    )


def approve_application(
    session: Session,
    application_id: int,
    remarks: str,
    approved_amount: Optional[float] = None,
    performed_by: AuditActor | str = AuditActor.SCRUTINY_OFFICER,
) -> ApplicationRecordDB:
    """Sanctions scholarship approval based on verified pre-approval eligibility."""
    return transition_application_status(
        session=session,
        application_id=application_id,
        to_status=ApplicationLifecycleStatus.APPROVED,
        performed_by=performed_by,
        reason=remarks,
        approved_amount=approved_amount,
    )


def disburse_benefit(
    session: Session,
    application_id: int,
    disbursed_amount: float,
    payment_reference: str,
    performed_by: AuditActor | str = AuditActor.DISBURSEMENT_OFFICER,
) -> ApplicationRecordDB:
    """Records DBT credit and transitions application to terminal BENEFIT_DISBURSED status."""
    return transition_application_status(
        session=session,
        application_id=application_id,
        to_status=ApplicationLifecycleStatus.BENEFIT_DISBURSED,
        performed_by=performed_by,
        reason=payment_reference,
        disbursed_amount=disbursed_amount,
    )


def reject_application(
    session: Session,
    application_id: int,
    reason: str,
    performed_by: AuditActor | str = AuditActor.SCRUTINY_OFFICER,
) -> ApplicationRecordDB:
    """Permanently rejects application due to statutory ineligibility or fraud (mandatory reason)."""
    return transition_application_status(
        session=session,
        application_id=application_id,
        to_status=ApplicationLifecycleStatus.REJECTED,
        performed_by=performed_by,
        reason=reason,
    )


def revoke_application(
    session: Session,
    application_id: int,
    reason: str,
    performed_by: AuditActor | str = AuditActor.SCRUTINY_OFFICER,
) -> ApplicationRecordDB:
    """Revokes an approved sanction post-approval (mandatory reason)."""
    return transition_application_status(
        session=session,
        application_id=application_id,
        to_status=ApplicationLifecycleStatus.REVOKED,
        performed_by=performed_by,
        reason=reason,
    )


def abandon_application(
    session: Session,
    application_id: int,
    reason: Optional[str] = None,
    performed_by: AuditActor | str = AuditActor.STUDENT,
) -> ApplicationRecordDB:
    """Marks application as abandoned by applicant or deserted before completion."""
    return transition_application_status(
        session=session,
        application_id=application_id,
        to_status=ApplicationLifecycleStatus.ABANDONED,
        performed_by=performed_by,
        reason=reason,
    )


# -----------------------------------------------------------------------------
# 5. Query & Audit History Helpers
# -----------------------------------------------------------------------------

def get_application_by_id(session: Session, application_id: int) -> Optional[ApplicationRecordDB]:
    """Retrieves an application record by its primary key ID."""
    return session.get(ApplicationRecordDB, application_id)


def get_application_by_number(session: Session, application_number: str) -> Optional[ApplicationRecordDB]:
    """Retrieves an application record by its unique administrative application number."""
    stmt = select(ApplicationRecordDB).where(ApplicationRecordDB.application_number == application_number)
    return session.scalars(stmt).first()


def get_application_evaluation_history(
    session: Session, application_id: int
) -> Sequence[ApplicationEligibilityEvaluationDB]:
    """Returns the full chronological eligibility evaluation history for an application file."""
    stmt = (
        select(ApplicationEligibilityEvaluationDB)
        .where(ApplicationEligibilityEvaluationDB.application_id == application_id)
        .order_by(ApplicationEligibilityEvaluationDB.evaluated_at.asc(), ApplicationEligibilityEvaluationDB.id.asc())
    )
    return session.scalars(stmt).all()


def get_application_audit_history(
    session: Session, application_id: int
) -> Sequence[ApplicationAuditLogDB]:
    """Returns the complete chronological status transition audit log for an application file."""
    stmt = (
        select(ApplicationAuditLogDB)
        .where(ApplicationAuditLogDB.application_id == application_id)
        .order_by(ApplicationAuditLogDB.timestamp.asc(), ApplicationAuditLogDB.id.asc())
    )
    return session.scalars(stmt).all()
