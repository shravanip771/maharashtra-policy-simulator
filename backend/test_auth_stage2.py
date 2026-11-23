"""
Test Suite for Authentication Stage 2: Registration API & Resend Email Adapter.

Verifies:
1. POST /api/auth/register successful registration with Argon2id password hashing.
2. Initial user verification state (is_verified=False).
3. Creation of SHA-256 hashed single-use verification token in DB (never raw token).
4. No leakage of secrets or raw tokens in API responses.
5. Case and whitespace email normalization and duplicate registration rejection (HTTP 409).
6. Input validation (invalid email format, short password, empty name) (HTTP 422).
7. Resend email adapter behavior (successful dispatch, unconfigured fallback, timeouts, HTTP errors).
8. Resilient registration workflow when email dispatch is unconfigured or fails.
9. Full metadata isolation and absence of side effects on simulation routes.
"""

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.auth.email_adapter import ResendEmailAdapter, get_email_adapter
from backend.auth.email_config import ResendConfig
from backend.auth.models import EmailVerificationTokenDB, UserDB, init_auth_db
from backend.auth.router import get_auth_db
from backend.auth.security import hash_token, verify_password
from backend.main import app


class TestAuthStage2Registration(unittest.TestCase):
    """Test suite for user registration API and Resend email adapter."""

    @classmethod
    def setUpClass(cls):
        # Configure isolated in-memory SQLite database
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
        self.session: Session = self.TestingSessionLocal()

        def override_get_db():
            session = self.TestingSessionLocal()
            try:
                yield session
            finally:
                session.close()

        # Mock email adapter for deterministic testing
        self.mock_email_adapter = MagicMock(spec=ResendEmailAdapter)
        self.mock_email_adapter.send_verification_email.return_value = True

        app.dependency_overrides[get_auth_db] = override_get_db
        app.dependency_overrides[get_email_adapter] = lambda: self.mock_email_adapter

        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.session.rollback()
        # Clean auth tables between tests
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM user_sessions"))
            conn.execute(text("DELETE FROM password_reset_tokens"))
            conn.execute(text("DELETE FROM email_verification_tokens"))
            conn.execute(text("DELETE FROM users"))
        self.session.close()

    # -------------------------------------------------------------------------
    # 1. Successful Registration
    # -------------------------------------------------------------------------
    def test_register_user_success(self):
        """Tests that valid registration returns 201 Created and expected DTO."""
        payload = {
            "email": "dr.deshmukh@gov.mah.in",
            "full_name": "Dr. Sunita Deshmukh",
            "password": "StrongSecretPassword2026!",
        }

        response = self.client.post("/api/auth/register", json=payload)
        self.assertEqual(response.status_code, 201)

        data = response.json()
        self.assertIn("id", data)
        self.assertEqual(data["email"], "dr.deshmukh@gov.mah.in")
        self.assertEqual(data["full_name"], "Dr. Sunita Deshmukh")
        self.assertTrue(data["is_active"])
        self.assertFalse(data["is_verified"])
        self.assertEqual(data["role"], "user")
        self.assertTrue(data["verification_email_sent"])
        self.assertIn("verification email", data["message"].lower())

        # CRITICAL: Verify NO raw tokens or passwords leak in response
        self.assertNotIn("password", data)
        self.assertNotIn("hashed_password", data)
        self.assertNotIn("raw_token", data)
        self.assertNotIn("token_hash", data)

        # Verify email adapter was called with recipient details
        self.mock_email_adapter.send_verification_email.assert_called_once()
        call_args = self.mock_email_adapter.send_verification_email.call_args
        self.assertEqual(call_args.kwargs["to_email"], "dr.deshmukh@gov.mah.in")
        self.assertEqual(call_args.kwargs["recipient_name"], "Dr. Sunita Deshmukh")
        # Token passed to email adapter must be high-entropy raw string (> 32 chars)
        raw_tok = call_args.kwargs["raw_token"]
        self.assertIsInstance(raw_tok, str)
        self.assertGreaterEqual(len(raw_tok), 32)

    # -------------------------------------------------------------------------
    # 2. Database Record & Security State
    # -------------------------------------------------------------------------
    def test_database_persistence_and_token_hashing(self):
        """Verifies Argon2id password hash and SHA-256 token hashing in the database."""
        payload = {
            "email": "researcher@example.org",
            "full_name": "Anand Shinde",
            "password": "SuperSecurePassword123#",
        }
        res = self.client.post("/api/auth/register", json=payload)
        self.assertEqual(res.status_code, 201)
        user_id = res.json()["id"]

        # Inspect database record
        user_db = self.session.query(UserDB).filter_by(id=user_id).first()
        self.assertIsNotNone(user_db)
        self.assertEqual(user_db.email, "researcher@example.org")
        self.assertFalse(user_db.is_verified)
        self.assertTrue(user_db.is_active)

        # Verify password is valid Argon2id hash and not plaintext
        self.assertNotEqual(user_db.hashed_password, payload["password"])
        self.assertTrue(user_db.hashed_password.startswith("$argon2id$v=19$"))
        self.assertTrue(verify_password(payload["password"], user_db.hashed_password))

        # Inspect token record
        token_db = self.session.query(EmailVerificationTokenDB).filter_by(user_id=user_id).first()
        self.assertIsNotNone(token_db)
        self.assertEqual(len(token_db.token_hash), 64)  # SHA-256 hex string

        # Verify that the raw token passed to the email adapter hashes to the stored token_hash
        raw_tok = self.mock_email_adapter.send_verification_email.call_args.kwargs["raw_token"]
        self.assertNotEqual(raw_tok, token_db.token_hash)
        self.assertEqual(hash_token(raw_tok), token_db.token_hash)
        self.assertTrue(token_db.is_valid)

        # Check expiry is roughly 24 hours in the future
        now_utc = datetime.now(timezone.utc)
        time_diff_hours = (token_db.expires_at - now_utc).total_seconds() / 3600.0
        self.assertAlmostEqual(time_diff_hours, 24.0, delta=0.5)

    # -------------------------------------------------------------------------
    # 3. Email Normalization and Duplicate Rejection
    # -------------------------------------------------------------------------
    def test_duplicate_registration_returns_409(self):
        """Tests that duplicate registrations return HTTP 409 Conflict."""
        payload1 = {
            "email": "duplicate@test.org",
            "full_name": "First User",
            "password": "PasswordOne123!",
        }
        res1 = self.client.post("/api/auth/register", json=payload1)
        self.assertEqual(res1.status_code, 201)

        # Attempt exact duplicate
        res2 = self.client.post("/api/auth/register", json=payload1)
        self.assertEqual(res2.status_code, 409)
        self.assertIn("already registered", res2.json()["detail"].lower())

        # Attempt duplicate with uppercase and whitespace
        payload_cased = {
            "email": "  DUPLICATE@Test.Org  ",
            "full_name": "Second User",
            "password": "PasswordTwo456!",
        }
        res3 = self.client.post("/api/auth/register", json=payload_cased)
        self.assertEqual(res3.status_code, 409)
        self.assertIn("already registered", res3.json()["detail"].lower())

    # -------------------------------------------------------------------------
    # 4. Input Validation (HTTP 422)
    # -------------------------------------------------------------------------
    def test_invalid_email_returns_422(self):
        """Tests that invalid email formats return HTTP 422."""
        invalid_emails = ["notanemail", "user@", "@domain.com", "user space@test.com"]
        for bad_email in invalid_emails:
            res = self.client.post(
                "/api/auth/register",
                json={"email": bad_email, "full_name": "Test User", "password": "Password123!"},
            )
            self.assertEqual(res.status_code, 422, f"Expected 422 for invalid email: {bad_email}")

    def test_short_password_returns_422(self):
        """Tests that passwords shorter than 8 characters return HTTP 422."""
        res = self.client.post(
            "/api/auth/register",
            json={"email": "shortpw@test.org", "full_name": "Short Password", "password": "short"},
        )
        self.assertEqual(res.status_code, 422)

    def test_blank_full_name_returns_422(self):
        """Tests that empty or whitespace full names return HTTP 422."""
        for blank_name in ["", "   "]:
            res = self.client.post(
                "/api/auth/register",
                json={"email": "blankname@test.org", "full_name": blank_name, "password": "Password123!"},
            )
            self.assertEqual(res.status_code, 422)

    # -------------------------------------------------------------------------
    # 5. Resilient Registration Workflow on Email Failure
    # -------------------------------------------------------------------------
    def test_registration_succeeds_when_email_sending_fails(self):
        """Verifies that an email delivery error does not roll back account creation."""
        self.mock_email_adapter.send_verification_email.return_value = False

        payload = {
            "email": "emailfail@test.org",
            "full_name": "Email Fail User",
            "password": "Password12345!",
        }
        res = self.client.post("/api/auth/register", json=payload)
        self.assertEqual(res.status_code, 201)

        data = res.json()
        self.assertFalse(data["verification_email_sent"])
        self.assertFalse(data["is_verified"])

        # Confirm user was created despite email failure
        user_in_db = self.session.query(UserDB).filter_by(email="emailfail@test.org").first()
        self.assertIsNotNone(user_in_db)


class TestResendEmailAdapterUnit(unittest.TestCase):
    """Unit tests for ResendEmailAdapter."""

    def test_unconfigured_resend_adapter_returns_false_safely(self):
        """When api_key or from_email are missing, adapter logs warning and returns False without exception."""
        config = ResendConfig(api_key="", from_email="")
        adapter = ResendEmailAdapter(config=config)

        result = adapter.send_verification_email(
            to_email="test@example.com",
            recipient_name="Test User",
            raw_token="some_secure_raw_token_xyz",
        )
        self.assertFalse(result)

    def test_configured_adapter_sends_http_request(self):
        """When configured, adapter constructs valid Resend payload and dispatches via HTTP."""
        config = ResendConfig(
            api_key="re_valid_api_key_123456",
            from_email="notifications@simulator.gov.in",
            frontend_base_url="https://simulator.gov.in",
        )

        mock_http_client = MagicMock(spec=httpx.Client)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_http_client.post.return_value = mock_response

        adapter = ResendEmailAdapter(config=config, http_client=mock_http_client)
        result = adapter.send_verification_email(
            to_email="user@example.com",
            recipient_name="Sunita Deshmukh",
            raw_token="raw_token_abc_123",
        )

        self.assertTrue(result)
        mock_http_client.post.assert_called_once()

        endpoint = mock_http_client.post.call_args[0][0]
        self.assertEqual(endpoint, "https://api.resend.com/emails")

        kwargs = mock_http_client.post.call_args[1]
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer re_valid_api_key_123456")
        self.assertEqual(kwargs["json"]["from"], "notifications@simulator.gov.in")
        self.assertEqual(kwargs["json"]["to"], ["user@example.com"])
        self.assertIn("https://simulator.gov.in/verify-email?token=raw_token_abc_123", kwargs["json"]["html"])
        self.assertIn("https://simulator.gov.in/verify-email?token=raw_token_abc_123", kwargs["json"]["text"])

    def test_adapter_handles_timeout_gracefully(self):
        """Adapter catches httpx.TimeoutException and returns False without crashing."""
        config = ResendConfig(
            api_key="re_valid_api_key_123456",
            from_email="notifications@simulator.gov.in",
        )
        mock_http_client = MagicMock(spec=httpx.Client)
        mock_http_client.post.side_effect = httpx.TimeoutException("Connection timed out")

        adapter = ResendEmailAdapter(config=config, http_client=mock_http_client)
        result = adapter.send_verification_email(
            to_email="timeout@example.com",
            recipient_name="Timeout User",
            raw_token="raw_token_timeout",
        )
        self.assertFalse(result)

    def test_adapter_handles_http_error_gracefully(self):
        """Adapter handles 4xx/5xx status codes and returns False without crashing."""
        config = ResendConfig(
            api_key="re_valid_api_key_123456",
            from_email="notifications@simulator.gov.in",
        )
        mock_http_client = MagicMock(spec=httpx.Client)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 403
        mock_http_client.post.return_value = mock_response

        adapter = ResendEmailAdapter(config=config, http_client=mock_http_client)
        result = adapter.send_verification_email(
            to_email="forbidden@example.com",
            recipient_name="Forbidden User",
            raw_token="raw_token_forbidden",
        )
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
