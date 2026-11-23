"""
Focused Unit Test Suite for Authentication & Security Foundation (Stage 1).

Tests:
1. Argon2id password hashing and constant-time verification.
2. Incorrect password rejection and tampered hash defense.
3. High-entropy token generation and SHA-256 token hashing.
4. Token expiry and single-use validation.
5. Auth ORM models against an isolated in-memory SQLite database (zero disk footprint).
6. Foreign key cascades, unique constraints, and session lifecycle.
7. Metadata isolation: Proves AuthBase does not contaminate Base.metadata (12 tables preserved).
8. Session cookie configuration and Resend configuration interface.
"""

import os
import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

# Import existing Base to verify non-contamination
from backend.database import Base
from backend.db_models import PolicyDB  # Trigger simulation model registration

# Import Auth module
from backend.auth.models import (
    AuthBase,
    EmailVerificationTokenDB,
    PasswordResetTokenDB,
    UserDB,
    UserSessionDB,
    init_auth_db,
)
from backend.auth.security import (
    generate_secure_token,
    generate_session_id,
    hash_password,
    hash_token,
    is_token_expired,
    verify_password,
    verify_token_hash,
)
from backend.auth.session import SessionCookieConfig
from backend.auth.email_config import ResendConfig, get_resend_config


class TestPasswordSecurity(unittest.TestCase):
    """Verifies Argon2id password hashing and validation security."""

    def test_hash_and_verify_argon2id(self):
        password = "SecurePassword123!"
        hashed = hash_password(password)

        self.assertIsInstance(hashed, str)
        self.assertTrue(hashed.startswith("$argon2id$v=19$"))
        self.assertNotEqual(password, hashed)
        self.assertTrue(verify_password(password, hashed))

    def test_incorrect_password_rejected(self):
        password = "CorrectHorseBatteryStaple99"
        hashed = hash_password(password)

        self.assertFalse(verify_password("WrongPassword123", hashed))
        self.assertFalse(verify_password("correcthorsebatterystaple99", hashed))  # Case-sensitive
        self.assertFalse(verify_password("", hashed))
        self.assertFalse(verify_password(password, ""))

    def test_empty_or_short_password_rejected(self):
        with self.assertRaises(ValueError):
            hash_password("")
        with self.assertRaises(ValueError):
            hash_password("short")  # Less than 8 characters

    def test_tampered_hash_rejected(self):
        password = "AnotherPassword888"
        hashed = hash_password(password)
        # Corrupt the hash payload
        tampered = hashed[:-5] + "XXXXX"
        self.assertFalse(verify_password(password, tampered))


class TestTokenSecurity(unittest.TestCase):
    """Verifies token generation, SHA-256 hashing, and expiry calculations."""

    def test_token_generation_uniqueness_and_entropy(self):
        tokens = [generate_secure_token(32) for _ in range(100)]
        self.assertEqual(len(tokens), 100)
        self.assertEqual(len(set(tokens)), 100)
        for t in tokens:
            self.assertGreaterEqual(len(t), 40)  # URL-safe base64 of 32 bytes

    def test_token_hashing_and_constant_time_verification(self):
        raw_token = generate_secure_token(32)
        token_hash = hash_token(raw_token)

        self.assertIsInstance(token_hash, str)
        self.assertEqual(len(token_hash), 64)  # SHA-256 hex digest
        self.assertTrue(verify_token_hash(raw_token, token_hash))
        self.assertFalse(verify_token_hash("wrong_token", token_hash))
        self.assertFalse(verify_token_hash(raw_token, "wrong_hash"))

    def test_token_expiry_validation(self):
        now = datetime.now(timezone.utc)
        future_time = now + timedelta(hours=24)
        past_time = now - timedelta(seconds=1)

        self.assertFalse(is_token_expired(future_time))
        self.assertTrue(is_token_expired(past_time))
        self.assertTrue(is_token_expired(None))

    def test_session_id_generation(self):
        s1 = generate_session_id()
        s2 = generate_session_id()
        self.assertNotEqual(s1, s2)
        self.assertGreaterEqual(len(s1), 40)


class TestAuthORMModels(unittest.TestCase):
    """Isolated in-memory test suite for Authentication ORM models."""

    @classmethod
    def setUpClass(cls):
        cls.engine: Engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            echo=False,
        )

        @event.listens_for(cls.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        # Initialize only auth tables
        init_auth_db(target_engine=cls.engine)
        cls.SessionLocal = sessionmaker(
            bind=cls.engine, autocommit=False, autoflush=False, expire_on_commit=False
        )

    def setUp(self):
        self.session: Session = self.SessionLocal()

    def tearDown(self):
        self.session.rollback()
        # Clean auth tables between test runs
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM user_sessions"))
            conn.execute(text("DELETE FROM password_reset_tokens"))
            conn.execute(text("DELETE FROM email_verification_tokens"))
            conn.execute(text("DELETE FROM users"))
        self.session.close()

    def test_user_creation_and_normalization(self):
        raw_email = "  Researcher.One@Example.COM  "
        normalized = UserDB.normalize_email(raw_email)
        self.assertEqual(normalized, "researcher.one@example.com")

        user = UserDB(
            email=normalized,
            full_name="Dr. Sunita Deshmukh",
            hashed_password=hash_password("ComplexSecret123"),
            is_active=True,
            is_verified=False,
            role="researcher",
        )
        self.session.add(user)
        self.session.commit()

        self.assertIsNotNone(user.id)
        self.assertEqual(user.email, "researcher.one@example.com")
        self.assertFalse(user.is_verified)
        self.assertIsInstance(user.created_at, datetime)
        self.assertEqual(user.created_at.tzinfo, timezone.utc)

    def test_user_unique_email_constraint(self):
        user1 = UserDB(
            email="unique@test.org",
            full_name="User One",
            hashed_password=hash_password("Pass12345!"),
        )
        user2 = UserDB(
            email="unique@test.org",
            full_name="User Two",
            hashed_password=hash_password("Pass67890!"),
        )
        self.session.add(user1)
        self.session.commit()

        self.session.add(user2)
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_email_verification_token_lifecycle(self):
        user = UserDB(
            email="verify@test.org",
            full_name="Pooja Patil",
            hashed_password=hash_password("Pass12345!"),
        )
        self.session.add(user)
        self.session.commit()

        raw_token = generate_secure_token(32)
        tok_hash = hash_token(raw_token)
        expires = datetime.now(timezone.utc) + timedelta(hours=24)

        token_record = EmailVerificationTokenDB(
            user_id=user.id,
            token_hash=tok_hash,
            expires_at=expires,
        )
        self.session.add(token_record)
        self.session.commit()

        self.assertTrue(token_record.is_valid)

        # Mark used
        token_record.used_at = datetime.now(timezone.utc)
        self.session.commit()
        self.assertFalse(token_record.is_valid)

    def test_cascade_delete_tokens_when_user_deleted(self):
        user = UserDB(
            email="delete_me@test.org",
            full_name="Temporary User",
            hashed_password=hash_password("Pass12345!"),
        )
        self.session.add(user)
        self.session.commit()

        raw_token = generate_secure_token(32)
        token_record = EmailVerificationTokenDB(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        session_record = UserSessionDB(
            user_id=user.id,
            session_id_hash=hash_token(generate_session_id()),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        self.session.add_all([token_record, session_record])
        self.session.commit()

        user_id = user.id
        self.session.delete(user)
        self.session.commit()

        # Confirm tokens and sessions were cascade deleted
        tok = self.session.query(EmailVerificationTokenDB).filter_by(user_id=user_id).first()
        sess = self.session.query(UserSessionDB).filter_by(user_id=user_id).first()
        self.assertIsNone(tok)
        self.assertIsNone(sess)

    def test_user_session_lifecycle(self):
        user = UserDB(
            email="session@test.org",
            full_name="Session User",
            hashed_password=hash_password("Pass12345!"),
        )
        self.session.add(user)
        self.session.commit()

        raw_session_id = generate_session_id()
        sess_hash = hash_token(raw_session_id)
        expires = datetime.now(timezone.utc) + timedelta(days=7)

        session_db = UserSessionDB(
            user_id=user.id,
            session_id_hash=sess_hash,
            expires_at=expires,
            ip_address="127.0.0.1",
            user_agent="Mozilla/5.0 Test Agent",
        )
        self.session.add(session_db)
        self.session.commit()

        self.assertTrue(session_db.is_active)

        # Revoke session
        session_db.is_revoked = True
        self.session.commit()
        self.assertFalse(session_db.is_active)


class TestMetadataIsolation(unittest.TestCase):
    """
    CRITICAL ARCHITECTURAL TEST:
    Verifies that AuthBase tables do NOT contaminate Base.metadata.
    Base.metadata must retain exactly the 12 simulation-domain tables.
    """

    def test_auth_does_not_contaminate_simulation_metadata(self):
        # 12 expected simulation domain tables
        expected_simulation_tables = {
            "policies",
            "policy_configurations",
            "synthetic_personas",
            "scenario_configurations",
            "simulation_runs",
            "persona_run_states",
            "persona_interactions",
            "individual_outcomes",
            "aggregate_results",
            "application_lifecycle_records",
            "application_eligibility_evaluations",
            "application_audit_logs",
        }

        # Check simulation Base.metadata
        simulation_tables = set(Base.metadata.tables.keys())
        self.assertEqual(
            simulation_tables,
            expected_simulation_tables,
            f"Base.metadata contaminated! Table count={len(simulation_tables)}, diff={simulation_tables.symmetric_difference(expected_simulation_tables)}",
        )

        # Check AuthBase.metadata
        expected_auth_tables = {
            "users",
            "email_verification_tokens",
            "password_reset_tokens",
            "user_sessions",
        }
        auth_tables = set(AuthBase.metadata.tables.keys())
        self.assertEqual(
            auth_tables,
            expected_auth_tables,
            f"AuthBase.metadata table mismatch! Found: {auth_tables}",
        )

        # Assert no overlap
        self.assertEqual(len(simulation_tables.intersection(auth_tables)), 0)


class TestSessionCookieConfig(unittest.TestCase):
    """Verifies cookie attributes and security settings."""

    def test_default_cookie_config(self):
        cfg = SessionCookieConfig()
        self.assertEqual(cfg.cookie_name, "mps_session_id")
        self.assertTrue(cfg.httponly)
        self.assertEqual(cfg.samesite, "lax")
        self.assertEqual(cfg.path, "/")
        self.assertEqual(cfg.max_age_seconds, 7 * 24 * 3600)

        kwargs = cfg.to_cookie_kwargs()
        self.assertEqual(kwargs["key"], "mps_session_id")
        self.assertTrue(kwargs["httponly"])
        self.assertEqual(kwargs["samesite"], "lax")

        del_kwargs = cfg.to_delete_cookie_kwargs()
        self.assertEqual(del_kwargs["key"], "mps_session_id")
        self.assertTrue(del_kwargs["httponly"])


class TestResendConfigInterface(unittest.TestCase):
    """Verifies Resend email configuration parsing, missing-state behavior, and secret masking."""

    def test_configured_state(self):
        cfg = ResendConfig(
            api_key="re_1234567890abcdef",
            from_email="noreply@example.com",
            frontend_base_url="http://localhost:5173",
        )
        self.assertTrue(cfg.is_configured)
        self.assertEqual(cfg.mask_key(), "re_1...cdef")
        self.assertNotIn("re_1234567890abcdef", repr(cfg))

    def test_missing_config_behavior(self):
        cfg = ResendConfig(api_key="", from_email="")
        self.assertFalse(cfg.is_configured)
        self.assertEqual(cfg.mask_key(), "[NOT SET]")

        with self.assertRaises(ValueError) as ctx:
            cfg.validate()
        self.assertIn("RESEND_API_KEY", str(ctx.exception))

    def test_missing_from_email_behavior(self):
        cfg = ResendConfig(api_key="re_test_key", from_email="")
        self.assertFalse(cfg.is_configured)
        with self.assertRaises(ValueError) as ctx:
            cfg.validate()
        self.assertIn("RESEND_FROM_EMAIL", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
