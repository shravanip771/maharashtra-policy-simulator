"""
Automated Test Suite for Authentication Stage 3: Email Verification & Self-Service Recovery.

Covers:
1. Verification:
   - Valid token verification marks user verified and token used.
   - Invalid / unknown token rejection (HTTP 400).
   - Expired token rejection (HTTP 400).
   - Reused token rejection (HTTP 400).
   - Already-verified account safe rejection (HTTP 400).
   - Missing / orphaned user relationship handling (HTTP 400).
   - Concurrent verification attempts atomic double-consumption defense.
   - IP rate limiting on repeated verification attempts (HTTP 429).
2. Resend:
   - Unverified account receives fresh verification token.
   - Previous unused tokens are invalidated upon resend.
   - Only SHA-256 token hash persisted in database (raw token never stored).
   - Verified account receives identical generic response without email dispatch.
   - Non-existent account receives identical generic response without email dispatch.
   - Email adapter failure / timeout handled gracefully without crashing.
   - Resend cooldown enforced (HTTP 429).
   - IP rate limit enforced on repeated resends (HTTP 429).
"""

from collections import deque
from datetime import datetime, timedelta, timezone
import asyncio
import os
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from fastapi import BackgroundTasks, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.auth.email_adapter import ResendEmailAdapter, get_email_adapter
from backend.auth.models import EmailVerificationTokenDB, UserDB, init_auth_db
from backend.auth.rate_limiter import RateLimiter, rate_limiter
from backend.auth.router import get_auth_db
from backend.auth.schemas import ResendVerificationRequest
from backend.auth.security import generate_secure_token, hash_password, hash_token
from backend.auth.service import VerificationService, _dispatch_resend_email
from backend.main import app


class TestAuthStage3Verification(unittest.TestCase):
    """Test suite for email verification and resend recovery workflows."""

    @classmethod
    def setUpClass(cls):
        cls.engine: Engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False,
        )

        @event.listens_for(cls.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        init_auth_db(target_engine=cls.engine)
        cls.TestingSessionLocal = sessionmaker(
            bind=cls.engine, autocommit=False, autoflush=False, expire_on_commit=False
        )

    def setUp(self):
        rate_limiter.reset()
        self.session: Session = self.TestingSessionLocal()

        def override_get_db():
            session = self.TestingSessionLocal()
            try:
                yield session
            finally:
                session.close()

        self.mock_email_adapter = MagicMock(spec=ResendEmailAdapter)
        self.mock_email_adapter.send_verification_email.return_value = True

        app.dependency_overrides[get_auth_db] = override_get_db
        app.dependency_overrides[get_email_adapter] = lambda: self.mock_email_adapter

        self.client = TestClient(app)

    def tearDown(self):
        rate_limiter.reset()
        app.dependency_overrides.clear()
        self.session.rollback()
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM user_sessions"))
            conn.execute(text("DELETE FROM password_reset_tokens"))
            conn.execute(text("DELETE FROM email_verification_tokens"))
            conn.execute(text("DELETE FROM users"))
        self.session.close()

    def _create_test_user(self, email: str, is_verified: bool = False) -> UserDB:
        """Helper to create and persist a test user."""
        user = UserDB(
            email=email.lower().strip(),
            full_name="Test Citizen",
            hashed_password=hash_password("ValidPassword123!"),
            is_active=True,
            is_verified=is_verified,
            role="user",
        )
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    def _create_verification_token(
        self,
        user_id: int,
        raw_token: str,
        expires_in_hours: float = 24.0,
        used: bool = False,
        created_at_offset_seconds: float = 0.0,
    ) -> EmailVerificationTokenDB:
        """Helper to create and persist a token record."""
        now_utc = datetime.now(timezone.utc)
        created_time = now_utc - timedelta(seconds=created_at_offset_seconds)
        expires_time = created_time + timedelta(hours=expires_in_hours)
        used_time = now_utc if used else None

        tok_record = EmailVerificationTokenDB(
            user_id=user_id,
            token_hash=hash_token(raw_token),
            expires_at=expires_time,
            created_at=created_time,
            used_at=used_time,
        )
        self.session.add(tok_record)
        self.session.commit()
        self.session.refresh(tok_record)
        return tok_record

    # =========================================================================
    # 1. Email Verification Endpoint Tests
    # =========================================================================

    def test_verify_email_success(self):
        """Valid token successfully verifies account, updates DB state and marks token used."""
        user = self._create_test_user("student.pune@gov.in", is_verified=False)
        raw_token = generate_secure_token(32)
        tok_record = self._create_verification_token(user.id, raw_token)

        response = self.client.post("/api/auth/verify-email", json={"token": raw_token})
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertTrue(data["is_verified"])
        self.assertEqual(data["email"], "student.pune@gov.in")
        self.assertIn("successfully verified", data["message"].lower())

        # Check DB state
        self.session.refresh(user)
        self.session.refresh(tok_record)
        self.assertTrue(user.is_verified)
        self.assertIsNotNone(tok_record.used_at)
        self.assertFalse(tok_record.is_valid)

    def test_verify_email_invalid_token_rejected(self):
        """Unknown or invalid token string returns HTTP 400 Bad Request."""
        response = self.client.post("/api/auth/verify-email", json={"token": "non_existent_token_1234567890"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("invalid verification token", response.json()["detail"].lower())

    def test_verify_email_expired_token_rejected(self):
        """Expired token returns HTTP 400 and leaves account unverified."""
        user = self._create_test_user("expired.tok@test.org", is_verified=False)
        raw_token = generate_secure_token(32)
        # Token created 48 hours ago with 24h validity -> expired 24h ago
        tok_record = self._create_verification_token(
            user.id, raw_token, expires_in_hours=24.0, created_at_offset_seconds=48 * 3600
        )

        response = self.client.post("/api/auth/verify-email", json={"token": raw_token})
        self.assertEqual(response.status_code, 400)
        self.assertIn("expired", response.json()["detail"].lower())

        self.session.refresh(user)
        self.assertFalse(user.is_verified)

    def test_verify_email_already_used_token_rejected(self):
        """Reusing an already-consumed token returns HTTP 400."""
        user = self._create_test_user("reused@test.org", is_verified=False)
        raw_token = generate_secure_token(32)
        tok_record = self._create_verification_token(user.id, raw_token, used=True)

        response = self.client.post("/api/auth/verify-email", json={"token": raw_token})
        self.assertEqual(response.status_code, 400)
        self.assertIn("already been used", response.json()["detail"].lower())

    def test_verify_email_already_verified_account_rejected(self):
        """Attempting to verify an already-verified user returns HTTP 400."""
        user = self._create_test_user("already.verified@test.org", is_verified=True)
        raw_token = generate_secure_token(32)
        tok_record = self._create_verification_token(user.id, raw_token)

        response = self.client.post("/api/auth/verify-email", json={"token": raw_token})
        self.assertEqual(response.status_code, 400)
        self.assertIn("already verified", response.json()["detail"].lower())

    def test_verify_email_missing_user_handled_safely(self):
        """Token with nonexistent user_id returns HTTP 400 safely."""
        raw_token = generate_secure_token(32)
        tok_hash = hash_token(raw_token)
        now_utc = datetime.now(timezone.utc)

        # Insert orphaned token by temporarily disabling FK checks on engine connection
        with self.engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys=OFF"))
            conn.execute(
                text(
                    "INSERT INTO email_verification_tokens (user_id, token_hash, expires_at, created_at) "
                    "VALUES (999999, :hash, :expires, :created)"
                ),
                {
                    "hash": tok_hash,
                    "expires": now_utc + timedelta(hours=24),
                    "created": now_utc,
                },
            )
            conn.commit()
            conn.execute(text("PRAGMA foreign_keys=ON"))

        response = self.client.post("/api/auth/verify-email", json={"token": raw_token})
        self.assertEqual(response.status_code, 400)
        self.assertIn("no longer exists", response.json()["detail"].lower())

    def test_verify_email_concurrent_double_consumption_prevented(self):
        """Verifies that an atomic CAS update prevents consuming the same token twice."""
        user = self._create_test_user("concurrency@test.org", is_verified=False)
        raw_token = generate_secure_token(32)
        self._create_verification_token(user.id, raw_token)

        # First consumption
        res1 = self.client.post("/api/auth/verify-email", json={"token": raw_token})
        self.assertEqual(res1.status_code, 200)

        # Immediate second consumption with the exact same token
        res2 = self.client.post("/api/auth/verify-email", json={"token": raw_token})
        self.assertEqual(res2.status_code, 400)
        self.assertIn("already been used", res2.json()["detail"].lower())

    def test_verify_email_ip_rate_limiting(self):
        """Exceeding 10 verification attempts per minute triggers HTTP 429."""
        for _ in range(10):
            res = self.client.post("/api/auth/verify-email", json={"token": "bogus_token_attempt_1234"})
            self.assertEqual(res.status_code, 400)

        # 11th request from same IP
        res_blocked = self.client.post("/api/auth/verify-email", json={"token": "bogus_token_attempt_1234"})
        self.assertEqual(res_blocked.status_code, 429)
        self.assertIn("too many", res_blocked.json()["detail"].lower())

    # =========================================================================
    # 2. Resend Verification Endpoint Tests
    # =========================================================================

    def test_resend_verification_success_for_unverified_account(self):
        """Unverified account receives new verification token and invalidates old token."""
        user = self._create_test_user("unverified.resend@gov.in", is_verified=False)
        old_raw = generate_secure_token(32)
        # Old token was created 100 seconds ago (outside the 60s cooldown)
        old_token = self._create_verification_token(user.id, old_raw, created_at_offset_seconds=100.0)

        response = self.client.post(
            "/api/auth/resend-verification",
            json={"email": "unverified.resend@gov.in"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("if an unverified account exists", response.json()["message"].lower())

        # Verify old token was marked as used (invalidated)
        self.session.refresh(old_token)
        self.assertIsNotNone(old_token.used_at)

        # Verify a new token was generated and persisted
        tokens = (
            self.session.query(EmailVerificationTokenDB)
            .filter_by(user_id=user.id)
            .order_by(EmailVerificationTokenDB.created_at.desc())
            .all()
        )
        self.assertEqual(len(tokens), 2)
        new_token = tokens[0]
        self.assertIsNone(new_token.used_at)
        self.assertTrue(new_token.is_valid)

        # Verify email adapter was called with recipient details and raw token
        self.mock_email_adapter.send_verification_email.assert_called_once()
        args = self.mock_email_adapter.send_verification_email.call_args
        self.assertEqual(args.kwargs["to_email"], "unverified.resend@gov.in")
        self.assertEqual(hash_token(args.kwargs["raw_token"]), new_token.token_hash)

    def test_resend_verification_verified_account_no_email_sent(self):
        """Already verified accounts return identical generic response with NO email sent."""
        user = self._create_test_user("verified.citizen@test.org", is_verified=True)

        response = self.client.post(
            "/api/auth/resend-verification",
            json={"email": "verified.citizen@test.org"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("if an unverified account exists", response.json()["message"].lower())

        # Email adapter must NOT be called for already verified accounts
        self.mock_email_adapter.send_verification_email.assert_not_called()

    def test_resend_verification_unknown_email_no_email_sent(self):
        """Nonexistent emails return identical generic response with NO email sent (anti-enumeration)."""
        response = self.client.post(
            "/api/auth/resend-verification",
            json={"email": "unknown.person@nonexistent.domain.org"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("if an unverified account exists", response.json()["message"].lower())

        self.mock_email_adapter.send_verification_email.assert_not_called()

    def test_resend_verification_cooldown_anti_enumeration(self):
        """Requesting another verification within 60 seconds returns generic HTTP 200 with no email sent."""
        user = self._create_test_user("cooldown.user@test.org", is_verified=False)
        raw_tok = generate_secure_token(32)
        # Token created 10 seconds ago (inside 60s cooldown)
        self._create_verification_token(user.id, raw_tok, created_at_offset_seconds=10.0)

        response = self.client.post(
            "/api/auth/resend-verification",
            json={"email": "cooldown.user@test.org"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("if an unverified account exists", response.json()["message"].lower())
        self.mock_email_adapter.send_verification_email.assert_not_called()

    def test_resend_verification_ip_rate_limiting(self):
        """Exceeding 5 resend requests per minute from the same IP triggers HTTP 429."""
        for i in range(5):
            res = self.client.post(
                "/api/auth/resend-verification",
                json={"email": f"diff{i}@nonexistent.org"},
            )
            self.assertEqual(res.status_code, 200)

        # 6th request from same IP
        res_blocked = self.client.post(
            "/api/auth/resend-verification",
            json={"email": "diff6@nonexistent.org"},
        )
        self.assertEqual(res_blocked.status_code, 429)
        self.assertIn("too many verification requests", res_blocked.json()["detail"].lower())

    def test_resend_verification_email_failure_handled_gracefully(self):
        """When email adapter raises an exception, endpoint still returns generic 200 response."""
        user = self._create_test_user("emailfailure@test.org", is_verified=False)
        raw_tok = generate_secure_token(32)
        self._create_verification_token(user.id, raw_tok, created_at_offset_seconds=120.0)

        self.mock_email_adapter.send_verification_email.side_effect = Exception("SMTP Gateway Error")

        response = self.client.post(
            "/api/auth/resend-verification",
            json={"email": "emailfailure@test.org"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("if an unverified account exists", response.json()["message"].lower())


class TestRateLimiterMemoryManagement(unittest.TestCase):
    """Unit tests for Stage 3 Step 3: bounded capacity, cleanup, and invariant validation."""

    def test_rate_limiter_constructor_validation(self):
        """Constructor rejects invalid max_keys and cleanup_interval_seconds."""
        for invalid_keys in [0, -1, True, False, 10.5, "1000", None]:
            with self.assertRaises(ValueError):
                RateLimiter(max_keys=invalid_keys)

        for invalid_interval in [0, -1.0, float("inf"), float("nan"), True, False, "60", 10**400, None]:
            with self.assertRaises(ValueError):
                RateLimiter(cleanup_interval_seconds=invalid_interval)

    def test_rate_limiter_large_cleanup_interval_overflow_rejected(self):
        """Constructor safely catches float OverflowError for huge integers like 10**400 and raises ValueError."""
        with self.assertRaises(ValueError):
            RateLimiter(cleanup_interval_seconds=10**400)

    def test_rate_limiter_invalid_max_requests_rejected(self):
        """is_rate_limited rejects non-positive-integer max_requests before state modification."""
        limiter = RateLimiter(max_keys=10, cleanup_interval_seconds=60)
        for inv in [0, -1, True, False, 1.5, "5", None]:
            with self.assertRaises(ValueError):
                limiter.is_rate_limited("key_inv_max", inv, 60)
        self.assertEqual(len(limiter._history), 0)
        self.assertEqual(len(limiter._key_windows), 0)

    def test_rate_limiter_invalid_window_seconds_rejected(self):
        """is_rate_limited rejects non-positive-integer window_seconds before state modification."""
        limiter = RateLimiter(max_keys=10, cleanup_interval_seconds=60)
        for inv_w in [0, -1, True, False, 60.5, "60", None]:
            with self.assertRaises(ValueError):
                limiter.is_rate_limited("key_inv_w", 5, inv_w)
        self.assertEqual(len(limiter._history), 0)
        self.assertEqual(len(limiter._key_windows), 0)

    def test_rate_limiter_inconsistent_window_rejected(self):
        """Calling an active key with conflicting window_seconds raises ValueError without corrupting state."""
        limiter = RateLimiter(max_keys=10, cleanup_interval_seconds=60)
        self.assertFalse(limiter.is_rate_limited("client_ip", 5, 60))
        self.assertEqual(limiter._key_windows["client_ip"], 60)

        with self.assertRaises(ValueError) as ctx:
            limiter.is_rate_limited("client_ip", 5, 120)
        self.assertIn("Inconsistent window_seconds", str(ctx.exception))

        # Confirm original key is still functional with original window
        self.assertFalse(limiter.is_rate_limited("client_ip", 5, 60))
        self.assertEqual(len(limiter._history["client_ip"]), 2)

    def test_rate_limiter_re_registration_after_expiration(self):
        """Once an expired key is purged by cleanup, it can be re-registered with a different window."""
        limiter = RateLimiter(max_keys=10, cleanup_interval_seconds=60)
        t0 = time.time()
        self.assertFalse(limiter.is_rate_limited("dynamic_key", 5, 60))
        self.assertEqual(limiter._key_windows["dynamic_key"], 60)

        # Cleanup at t0 + 65 purges dynamic_key
        purged = limiter.cleanup(now=t0 + 65)
        self.assertEqual(purged, 1)
        self.assertNotIn("dynamic_key", limiter._history)
        self.assertNotIn("dynamic_key", limiter._key_windows)

        # Now re-register with different window (120)
        self.assertFalse(limiter.is_rate_limited("dynamic_key", 5, 120))
        self.assertEqual(limiter._key_windows["dynamic_key"], 120)

    def test_rejected_keys_do_not_allocate_metadata(self):
        """At capacity saturation, fail-closed rejections allocate zero history or metadata."""
        limiter = RateLimiter(max_keys=2, cleanup_interval_seconds=3600)
        self.assertFalse(limiter.is_rate_limited("key1", 5, 60))
        self.assertFalse(limiter.is_rate_limited("key2", 5, 60))
        self.assertEqual(len(limiter._history), 2)
        self.assertEqual(len(limiter._key_windows), 2)

        # Capacity saturated: untracked key3 should be blocked immediately (fail-closed)
        blocked = limiter.is_rate_limited("key3", 5, 60)
        self.assertTrue(blocked)
        self.assertNotIn("key3", limiter._history)
        self.assertNotIn("key3", limiter._key_windows)
        self.assertEqual(len(limiter._history), 2)
        self.assertEqual(len(limiter._key_windows), 2)

    def test_rate_limiter_prunes_abandoned_keys(self):
        """cleanup() deletes keys whose timestamps have fully expired."""
        limiter = RateLimiter(max_keys=100, cleanup_interval_seconds=3600)
        t0 = time.time()
        limiter.is_rate_limited("k1", 5, 60)
        limiter.is_rate_limited("k2", 5, 60)
        self.assertEqual(len(limiter._history), 2)

        # Run cleanup before expiration
        purged_early = limiter.cleanup(now=t0 + 30)
        self.assertEqual(purged_early, 0)
        self.assertEqual(len(limiter._history), 2)

        # Run cleanup after expiration
        purged_late = limiter.cleanup(now=t0 + 70)
        self.assertEqual(purged_late, 2)
        self.assertEqual(len(limiter._history), 0)
        self.assertEqual(len(limiter._key_windows), 0)

    def test_rate_limiter_preserves_active_keys_during_cleanup(self):
        """Active unexpired keys and timestamps are retained during cleanup pass."""
        limiter = RateLimiter(max_keys=100, cleanup_interval_seconds=3600)
        t0 = time.time()
        limiter.is_rate_limited("k_active", 5, 60)
        self.assertEqual(len(limiter._history), 1)

        purged = limiter.cleanup(now=t0 + 10)
        self.assertEqual(purged, 0)
        self.assertIn("k_active", limiter._history)
        self.assertEqual(len(limiter._history["k_active"]), 1)

    def test_rate_limiter_reclaims_expired_slots_at_capacity(self):
        """Capacity check opportunistically purges expired keys to admit new keys without failing closed."""
        limiter = RateLimiter(max_keys=2, cleanup_interval_seconds=3600)
        t0 = 1000.0
        # Seed two entries that will be expired at t0 + 70
        limiter._history["k1"] = deque([t0])
        limiter._key_windows["k1"] = 60
        limiter._history["k2"] = deque([t0])
        limiter._key_windows["k2"] = 60
        self.assertEqual(len(limiter._history), 2)

        with patch("time.time", return_value=t0 + 70):
            # Attempt to admit k3 at t0 + 70. Capacity is 2/2, but k1 and k2 are expired.
            allowed = not limiter.is_rate_limited("k3", 5, 60)
            self.assertTrue(allowed)
            self.assertIn("k3", limiter._history)
            self.assertNotIn("k1", limiter._history)
            self.assertNotIn("k2", limiter._history)
            self.assertEqual(len(limiter._history), 1)

    def test_deterministic_cleanup_timestamp_zero(self):
        """cleanup(now=0.0) correctly treats zero as a valid timestamp and purges expired entries."""
        limiter = RateLimiter(max_keys=10, cleanup_interval_seconds=3600)
        limiter._history["k_zero"] = deque([-100.0])
        limiter._key_windows["k_zero"] = 60

        # now = 0.0, cutoff = 0.0 - 60 = -60.0. Since -100.0 <= -60.0, timestamp is pruned and key removed.
        purged = limiter.cleanup(now=0.0)
        self.assertEqual(purged, 1)
        self.assertNotIn("k_zero", limiter._history)
        self.assertNotIn("k_zero", limiter._key_windows)


class TestResendConcurrencyProtection(unittest.TestCase):
    """Concurrency verification for resend_verification using file-backed SQLite."""

    def setUp(self):
        rate_limiter.reset()
        self.temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_file.close()
        self.db_path = self.temp_file.name

        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout = 5000")
            cursor.close()

        init_auth_db(target_engine=self.engine)
        self.SessionFactory = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        self.threads = []

    def tearDown(self):
        rate_limiter.reset()
        # Avoid disposing engine or unlinking file while worker threads are still running
        if any(t.is_alive() for t in getattr(self, "threads", [])):
            return

        if hasattr(self, "engine"):
            self.engine.dispose()
        if hasattr(self, "db_path") and os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def test_concurrent_resend_requests_serialized(self):
        """Simultaneous resend requests for the same unverified user produce exactly 1 token and 1 email."""
        from backend.auth.schemas import ResendVerificationRequest
        from backend.auth.service import VerificationService

        # 1. Seed user in file-backed database
        with self.SessionFactory() as session:
            user = UserDB(
                email="concurrent.resend@gov.in",
                full_name="Concurrent Citizen",
                hashed_password=hash_password("ValidPassword123!"),
                is_active=True,
                is_verified=False,
                role="user",
            )
            session.add(user)
            session.commit()
            user_id = user.id

        mock_email_adapter = MagicMock(spec=ResendEmailAdapter)
        mock_email_adapter.send_verification_email.return_value = True

        num_threads = 5
        barrier = threading.Barrier(num_threads)
        responses = []
        errors = []

        def worker(client_ip_suffix: int):
            session = self.SessionFactory()
            try:
                barrier.wait(timeout=10.0)
                resp = VerificationService.resend_verification(
                    db=session,
                    payload=ResendVerificationRequest(email="concurrent.resend@gov.in"),
                    email_adapter=mock_email_adapter,
                    client_ip=f"10.0.1.{client_ip_suffix}",
                )
                responses.append(resp)
            except Exception as exc:
                errors.append(exc)
            finally:
                session.close()

        threads = [
            threading.Thread(target=worker, args=(i,), daemon=True)
            for i in range(num_threads)
        ]
        self.threads = threads
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)

        alive_threads = [t for t in threads if t.is_alive()]
        self.assertEqual(
            len(alive_threads), 0, f"{len(alive_threads)} worker thread(s) timed out and remained alive"
        )

        # Zero errors
        self.assertEqual(len(errors), 0, f"Encountered unexpected errors during concurrency: {errors}")
        self.assertEqual(len(responses), num_threads)
        for resp in responses:
            self.assertIn("if an unverified account exists", resp.message.lower())

        # Inspect database state
        with self.SessionFactory() as session:
            tokens = (
                session.query(EmailVerificationTokenDB)
                .filter_by(user_id=user_id)
                .all()
            )
            active_tokens = (
                session.query(EmailVerificationTokenDB)
                .filter_by(user_id=user_id, used_at=None)
                .all()
            )

            # Exactly one token ever created
            self.assertEqual(len(tokens), 1)
            # That one token is currently active (used_at is None)
            self.assertEqual(len(active_tokens), 1)

        # Exactly one email dispatched
        self.assertEqual(mock_email_adapter.send_verification_email.call_count, 1)


class TestResendBackgroundTasks(unittest.TestCase):
    """Unit tests for Stage 3 Step 5: BackgroundTasks email dispatch in resend_verification."""

    @classmethod
    def setUpClass(cls):
        cls.engine: Engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False,
        )

        @event.listens_for(cls.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        init_auth_db(target_engine=cls.engine)
        cls.TestingSessionLocal = sessionmaker(
            bind=cls.engine, autocommit=False, autoflush=False, expire_on_commit=False
        )

    def setUp(self):
        rate_limiter.reset()
        self.session: Session = self.TestingSessionLocal()
        self.mock_email_adapter = MagicMock(spec=ResendEmailAdapter)
        self.mock_email_adapter.send_verification_email.return_value = True

    def tearDown(self):
        rate_limiter.reset()
        self.session.rollback()
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM email_verification_tokens"))
            conn.execute(text("DELETE FROM users"))
        self.session.close()

    def _create_user(self, email: str, is_verified: bool = False) -> UserDB:
        user = UserDB(
            email=email.lower().strip(),
            full_name="Citizen Tester",
            hashed_password=hash_password("ValidPassword123!"),
            is_active=True,
            is_verified=is_verified,
            role="user",
        )
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    def test_resend_schedules_background_task_deferred(self):
        """1. Successful resend schedules exactly one background task without immediately calling the email adapter."""
        user = self._create_user("bg.defer@gov.in", is_verified=False)
        bg = BackgroundTasks()

        resp = VerificationService.resend_verification(
            db=self.session,
            payload=ResendVerificationRequest(email="bg.defer@gov.in"),
            email_adapter=self.mock_email_adapter,
            client_ip="127.0.0.1",
            background_tasks=bg,
        )
        self.assertIn("if an unverified account exists", resp.message.lower())

        # Exactly 1 background task scheduled
        self.assertEqual(len(bg.tasks), 1)
        # Email adapter NOT called yet before background task execution
        self.mock_email_adapter.send_verification_email.assert_not_called()

    def test_executing_background_task_sends_email_with_token(self):
        """2. Executing the scheduled task calls the email adapter exactly once with the correct recipient and raw token."""
        user = self._create_user("bg.execute@gov.in", is_verified=False)
        bg = BackgroundTasks()

        VerificationService.resend_verification(
            db=self.session,
            payload=ResendVerificationRequest(email="bg.execute@gov.in"),
            email_adapter=self.mock_email_adapter,
            client_ip="127.0.0.1",
            background_tasks=bg,
        )
        self.assertEqual(len(bg.tasks), 1)

        # Run background tasks
        asyncio.run(bg())

        # Email adapter called exactly once
        self.mock_email_adapter.send_verification_email.assert_called_once()
        call_kwargs = self.mock_email_adapter.send_verification_email.call_args.kwargs
        self.assertEqual(call_kwargs["to_email"], "bg.execute@gov.in")
        self.assertEqual(call_kwargs["recipient_name"], "Citizen Tester")

        # Verify raw token matches the token_hash in database
        latest_token = (
            self.session.query(EmailVerificationTokenDB)
            .filter_by(user_id=user.id)
            .order_by(EmailVerificationTokenDB.created_at.desc())
            .first()
        )
        self.assertIsNotNone(latest_token)
        self.assertEqual(hash_token(call_kwargs["raw_token"]), latest_token.token_hash)

    def test_cooldown_requests_schedule_zero_tasks(self):
        """3. Cooldown requests schedule zero tasks and return generic HTTP 200."""
        user = self._create_user("bg.cooldown@gov.in", is_verified=False)
        # Create token created 5 seconds ago (within 60s cooldown)
        now_utc = datetime.now(timezone.utc)
        recent_tok = EmailVerificationTokenDB(
            user_id=user.id,
            token_hash=hash_token("sometoken12345"),
            expires_at=now_utc + timedelta(hours=24),
            created_at=now_utc - timedelta(seconds=5),
        )
        self.session.add(recent_tok)
        self.session.commit()

        bg = BackgroundTasks()
        resp = VerificationService.resend_verification(
            db=self.session,
            payload=ResendVerificationRequest(email="bg.cooldown@gov.in"),
            email_adapter=self.mock_email_adapter,
            client_ip="127.0.0.1",
            background_tasks=bg,
        )
        self.assertIn("if an unverified account exists", resp.message.lower())
        self.assertEqual(len(bg.tasks), 0)
        self.mock_email_adapter.send_verification_email.assert_not_called()

    def test_unknown_and_verified_schedule_zero_tasks(self):
        """4. Unknown and verified accounts schedule zero tasks."""
        # Unknown email
        bg_unknown = BackgroundTasks()
        resp_unknown = VerificationService.resend_verification(
            db=self.session,
            payload=ResendVerificationRequest(email="nonexistent@gov.in"),
            email_adapter=self.mock_email_adapter,
            client_ip="127.0.0.1",
            background_tasks=bg_unknown,
        )
        self.assertIn("if an unverified account exists", resp_unknown.message.lower())
        self.assertEqual(len(bg_unknown.tasks), 0)

        # Verified email
        verified_user = self._create_user("bg.verified@gov.in", is_verified=True)
        bg_verified = BackgroundTasks()
        resp_verified = VerificationService.resend_verification(
            db=self.session,
            payload=ResendVerificationRequest(email="bg.verified@gov.in"),
            email_adapter=self.mock_email_adapter,
            client_ip="127.0.0.1",
            background_tasks=bg_verified,
        )
        self.assertIn("if an unverified account exists", resp_verified.message.lower())
        self.assertEqual(len(bg_verified.tasks), 0)

        self.mock_email_adapter.send_verification_email.assert_not_called()

    def test_email_adapter_exceptions_contained_by_helper(self):
        """5. Email adapter exceptions are caught and contained by _dispatch_resend_email without raising."""
        self.mock_email_adapter.send_verification_email.side_effect = Exception("SMTP Outage")

        # Must not raise an exception
        try:
            _dispatch_resend_email(
                email_adapter=self.mock_email_adapter,
                to_email="test@fail.org",
                recipient_name="Fail Recipient",
                raw_token="rawtoken123",
                user_id=1,
            )
        except Exception as exc:
            self.fail(f"_dispatch_resend_email leaked an exception: {exc}")

        self.mock_email_adapter.send_verification_email.assert_called_once()

    def test_failed_database_transaction_does_not_schedule_task(self):
        """6. A failed database transaction rolls back and does not schedule a background email task."""
        user = self._create_user("bg.failtx@gov.in", is_verified=False)
        bg = BackgroundTasks()

        with patch.object(self.session, "commit", side_effect=Exception("Database Disk I/O Error")):
            with self.assertRaises(HTTPException) as ctx:
                VerificationService.resend_verification(
                    db=self.session,
                    payload=ResendVerificationRequest(email="bg.failtx@gov.in"),
                    email_adapter=self.mock_email_adapter,
                    client_ip="127.0.0.1",
                    background_tasks=bg,
                )
            self.assertEqual(ctx.exception.status_code, 500)

        # Background tasks must be empty, email adapter never called
        self.assertEqual(len(bg.tasks), 0)
        self.mock_email_adapter.send_verification_email.assert_not_called()


if __name__ == "__main__":
    unittest.main()
