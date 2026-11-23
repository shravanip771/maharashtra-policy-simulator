"""
Authentication Business Logic & Database Services for Real Users (Stages 2 & 3).
Provides:
- RegistrationService: User onboarding, password hashing, and token dispatch
- VerificationService: Atomic email verification and anti-enumeration resend recovery
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import text, update
from sqlalchemy.orm import Session

from backend.auth.email_adapter import ResendEmailAdapter
from backend.auth.models import EmailVerificationTokenDB, UserDB
from backend.auth.rate_limiter import rate_limiter
from backend.auth.schemas import (
    ResendVerificationRequest,
    ResendVerificationResponse,
    UserRegisterRequest,
    UserRegisterResponse,
    VerifyEmailRequest,
    VerifyEmailResponse,
)
from backend.auth.security import (
    generate_secure_token,
    hash_password,
    hash_token,
    is_token_expired,
)

logger = logging.getLogger("backend.auth.service")


def _dispatch_resend_email(
    email_adapter: ResendEmailAdapter,
    to_email: str,
    recipient_name: str,
    raw_token: str,
    user_id: int,
) -> None:
    """
    Helper function for background or synchronous dispatch of resend verification emails.
    Catches all exceptions to isolate email delivery failures from crashing the worker process.
    Strictly avoids logging raw tokens.
    """
    try:
        email_adapter.send_verification_email(
            to_email=to_email,
            recipient_name=recipient_name,
            raw_token=raw_token,
        )
    except Exception:
        logger.exception("Unhandled error dispatching resend verification email for user id=%d", user_id)


class RegistrationService:
    """Encapsulates business operations for real-user registration."""

    @staticmethod
    def register_user(
        db: Session,
        payload: UserRegisterRequest,
        email_adapter: ResendEmailAdapter,
    ) -> UserRegisterResponse:
        """
        Registers a new user, hashes password with Argon2id, generates an email verification
        token, persists records in a transaction, and dispatches a verification email.

        Raises:
            HTTPException(409): If a user with the normalized email already exists.
            HTTPException(500): On database or unexpected transaction failure.
        """
        # 1. Normalize email
        normalized_email = UserDB.normalize_email(str(payload.email))

        # 2. Check for duplicate registration
        existing_user = db.query(UserDB).filter_by(email=normalized_email).first()
        if existing_user is not None:
            logger.warning("Registration rejected: Duplicate email address '%s'", normalized_email)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email address is already registered.",
            )

        # 3. Hash password using Argon2id
        hashed_pw = hash_password(payload.password)

        # 4. Generate high-entropy cryptographic token for email verification
        raw_token = generate_secure_token(32)
        tok_hash = hash_token(raw_token)
        token_expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

        # 5. Persist user and verification token record inside a database transaction
        try:
            new_user = UserDB(
                email=normalized_email,
                full_name=payload.full_name,
                hashed_password=hashed_pw,
                is_active=True,
                is_verified=False,
                role="user",
            )
            db.add(new_user)
            db.flush()  # Generate user.id for foreign key assignment

            token_record = EmailVerificationTokenDB(
                user_id=new_user.id,
                token_hash=tok_hash,
                expires_at=token_expires_at,
            )
            db.add(token_record)
            db.commit()
            db.refresh(new_user)
            logger.info("Successfully registered user id=%d (email=%s)", new_user.id, new_user.email)

        except Exception as exc:
            db.rollback()
            logger.exception("Database transaction failed during user registration for %s", normalized_email)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User registration could not be completed due to a database error.",
            ) from exc

        # 6. Dispatch verification email via decoupled email adapter
        email_sent = False
        try:
            email_sent = email_adapter.send_verification_email(
                to_email=new_user.email,
                recipient_name=new_user.full_name,
                raw_token=raw_token,
            )
        except Exception:
            logger.exception("Unhandled error during email dispatch for user id=%d", new_user.id)
            email_sent = False

        status_message = (
            "Registration successful. A verification email has been sent to your address."
            if email_sent
            else "Registration successful. Verification email could not be sent at this time or email service is in local development mode."
        )

        return UserRegisterResponse(
            id=new_user.id,
            email=new_user.email,
            full_name=new_user.full_name,
            is_active=new_user.is_active,
            is_verified=new_user.is_verified,
            role=new_user.role,
            message=status_message,
            verification_email_sent=email_sent,
        )


class VerificationService:
    """Encapsulates business operations for email verification and recovery (Stage 3)."""

    GENERIC_RESEND_MESSAGE = (
        "If an unverified account exists for this email address, a new verification link has been sent."
    )

    @classmethod
    def verify_email(
        cls,
        db: Session,
        payload: VerifyEmailRequest,
        client_ip: str,
    ) -> VerifyEmailResponse:
        """
        Atomically verifies an email address using a single-use token.

        Guarantees:
        - Raw token is never stored or logged.
        - Token hash is validated against DB.
        - Expired, already-used, or invalid tokens are rejected.
        - Atomic compare-and-swap update prevents concurrent double-consumption.
        - Enforces IP-level brute-force rate limiting.
        """
        # 1. IP-level rate limiting to defend against token brute-force attempts
        if rate_limiter.is_rate_limited(f"verify_ip:{client_ip}", max_requests=10, window_seconds=60):
            logger.warning("Verification rejected: IP rate limit exceeded for %s", client_ip)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many verification attempts. Please wait a moment before trying again.",
            )

        # 2. Hash raw token using SHA-256
        tok_hash = hash_token(payload.token.strip())

        # 3. Locate verification token record
        token_record = db.query(EmailVerificationTokenDB).filter_by(token_hash=tok_hash).first()
        if token_record is None:
            logger.info("Verification failed: Token hash not found (IP: %s)", client_ip)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification token.",
            )

        # 4. Check whether token was already used
        if token_record.used_at is not None:
            logger.info("Verification rejected: Token already used (token_id: %d)", token_record.id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification token has already been used.",
            )

        # 5. Check whether token has expired
        if is_token_expired(token_record.expires_at):
            logger.info("Verification rejected: Token expired (token_id: %d)", token_record.id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification token has expired. Please request a new verification email.",
            )

        # 6. Validate associated user existence and state
        user = token_record.user or db.query(UserDB).filter_by(id=token_record.user_id).first()
        if user is None:
            logger.error("Verification failed: Orphaned token record without user (token_id: %d)", token_record.id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User associated with this verification token no longer exists.",
            )

        if user.is_verified:
            logger.info("Verification rejected: User %d is already verified", user.id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Account is already verified.",
            )

        # 7. Atomic consumption: Compare-And-Swap update to prevent concurrent double-consumption
        now_utc = datetime.now(timezone.utc)
        stmt = (
            update(EmailVerificationTokenDB)
            .where(
                EmailVerificationTokenDB.id == token_record.id,
                EmailVerificationTokenDB.used_at.is_(None),
            )
            .values(used_at=now_utc)
        )
        update_result = db.execute(stmt)
        if update_result.rowcount == 0:
            # Another concurrent transaction consumed this token first
            db.rollback()
            logger.warning("Concurrent token consumption blocked for token_id %d", token_record.id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification token has already been used.",
            )

        # 8. Mark user account verified and commit transaction atomically
        try:
            user.is_verified = True
            db.commit()
            db.refresh(user)
            logger.info("Successfully verified email for user id=%d (%s)", user.id, user.email)
        except Exception as exc:
            db.rollback()
            logger.exception("Database error while marking user id=%d verified", user.id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Account verification failed due to a database error.",
            ) from exc

        return VerifyEmailResponse(
            message="Email successfully verified. You may now log in.",
            email=user.email,
            is_verified=True,
        )

    @classmethod
    def resend_verification(
        cls,
        db: Session,
        payload: ResendVerificationRequest,
        email_adapter: ResendEmailAdapter,
        client_ip: str,
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> ResendVerificationResponse:
        """
        Dispatches a fresh verification token for unverified accounts.

        Guarantees:
        - Defends against user enumeration: returns identical generic message regardless of account status.
        - Enforces IP-level and account-level rate limiting / cooldown.
        - Database-level concurrency protection prevents duplicate tokens and race conditions.
        - Invalidates previous unused tokens for that user.
        - Stores only SHA-256 token hash with 24h expiration.
        """
        # 1. IP-level rate limiting on resend attempts (legitimately returns HTTP 429)
        if rate_limiter.is_rate_limited(f"resend_ip:{client_ip}", max_requests=5, window_seconds=60):
            logger.warning("Resend rejected: IP rate limit exceeded for %s", client_ip)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many verification requests from this IP. Please wait before trying again.",
            )

        normalized_email = UserDB.normalize_email(str(payload.email))

        # 2. Initial lookup without exclusive lock (prevents lock exhaustion DoS for non-existent emails)
        user = db.query(UserDB).filter_by(email=normalized_email).first()

        # Security: Do not reveal whether account exists
        if user is None:
            logger.info("Resend requested for non-existent email (enumeration masked)")
            return ResendVerificationResponse(message=cls.GENERIC_RESEND_MESSAGE)

        # Security: Do not reveal if account is already verified, do not send email
        if user.is_verified:
            logger.info("Resend requested for already verified user id=%d (masked)", user.id)
            return ResendVerificationResponse(message=cls.GENERIC_RESEND_MESSAGE)

        # 3. Enter serialized write transaction based on database dialect
        try:
            dialect_name = db.get_bind().dialect.name if db.get_bind() else ""
            if dialect_name == "sqlite":
                db.execute(text("BEGIN IMMEDIATE"))
            elif dialect_name == "postgresql":
                user = (
                    db.query(UserDB)
                    .filter_by(id=user.id)
                    .with_for_update()
                    .populate_existing()
                    .first()
                )

            # 4. Re-read/refresh user inside the serialized transaction
            db.refresh(user)
            if user.is_verified:
                db.commit()
                logger.info("Resend skipped: User %d verified by concurrent transaction (masked)", user.id)
                return ResendVerificationResponse(message=cls.GENERIC_RESEND_MESSAGE)

            # 5. Check account-level cooldown against the user's latest token creation time
            latest_token = (
                db.query(EmailVerificationTokenDB)
                .filter_by(user_id=user.id)
                .order_by(EmailVerificationTokenDB.created_at.desc())
                .first()
            )
            is_cooldown, remaining = rate_limiter.check_resend_cooldown(
                latest_token.created_at if latest_token else None,
                cooldown_seconds=60,
            )
            if is_cooldown:
                db.commit()
                logger.info("Resend cooldown active for user id=%d (%ds remaining) - masked", user.id, remaining)
                return ResendVerificationResponse(message=cls.GENERIC_RESEND_MESSAGE)

            # 6. Invalidate previous unused tokens and persist fresh token atomically
            raw_token = generate_secure_token(32)
            tok_hash = hash_token(raw_token)
            now_utc = datetime.now(timezone.utc)
            expires_at = now_utc + timedelta(hours=24)

            db.execute(
                update(EmailVerificationTokenDB)
                .where(
                    EmailVerificationTokenDB.user_id == user.id,
                    EmailVerificationTokenDB.used_at.is_(None),
                )
                .values(used_at=now_utc)
            )

            recipient_email = user.email
            recipient_name = user.full_name
            recipient_user_id = user.id

            new_token = EmailVerificationTokenDB(
                user_id=user.id,
                token_hash=tok_hash,
                expires_at=expires_at,
            )
            db.add(new_token)
            db.commit()
            logger.info("Created fresh verification token for user id=%d", user.id)
        except Exception as exc:
            db.rollback()
            logger.exception("Database transaction failed during resend verification for user id=%d", user.id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to process verification request at this time.",
            ) from exc

        # 7. Dispatch email via decoupled Resend adapter (scheduled via BackgroundTasks if provided)
        if background_tasks is not None:
            background_tasks.add_task(
                _dispatch_resend_email,
                email_adapter=email_adapter,
                to_email=recipient_email,
                recipient_name=recipient_name,
                raw_token=raw_token,
                user_id=recipient_user_id,
            )
        else:
            _dispatch_resend_email(
                email_adapter=email_adapter,
                to_email=recipient_email,
                recipient_name=recipient_name,
                raw_token=raw_token,
                user_id=recipient_user_id,
            )

        return ResendVerificationResponse(message=cls.GENERIC_RESEND_MESSAGE)
