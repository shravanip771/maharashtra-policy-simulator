"""
Authentication Package for Maharashtra Policy Simulator.
Provides real-user authentication, password security, session management,
registration, transactional email verification, and recovery foundations.

Completely decoupled from synthetic student personas and the simulation engine.
"""

from backend.auth.models import (
    AuthBase,
    UserDB,
    EmailVerificationTokenDB,
    PasswordResetTokenDB,
    UserSessionDB,
    init_auth_db,
)
from backend.auth.security import (
    hash_password,
    verify_password,
    generate_secure_token,
    hash_token,
    verify_token_hash,
    generate_session_id,
    is_token_expired,
)
from backend.auth.session import (
    SessionCookieConfig,
    DEFAULT_SESSION_COOKIE_CONFIG,
)
from backend.auth.email_config import (
    ResendConfig,
    get_resend_config,
)
from backend.auth.email_adapter import (
    ResendEmailAdapter,
    get_email_adapter,
)
from backend.auth.rate_limiter import (
    RateLimiter,
    rate_limiter,
)
from backend.auth.schemas import (
    UserRegisterRequest,
    UserRegisterResponse,
    VerifyEmailRequest,
    VerifyEmailResponse,
    ResendVerificationRequest,
    ResendVerificationResponse,
)
from backend.auth.service import (
    RegistrationService,
    VerificationService,
)
from backend.auth.router import (
    auth_router,
    get_auth_db,
    get_client_ip,
)

__all__ = [
    "AuthBase",
    "UserDB",
    "EmailVerificationTokenDB",
    "PasswordResetTokenDB",
    "UserSessionDB",
    "init_auth_db",
    "hash_password",
    "verify_password",
    "generate_secure_token",
    "hash_token",
    "verify_token_hash",
    "generate_session_id",
    "is_token_expired",
    "SessionCookieConfig",
    "DEFAULT_SESSION_COOKIE_CONFIG",
    "ResendConfig",
    "get_resend_config",
    "ResendEmailAdapter",
    "get_email_adapter",
    "RateLimiter",
    "rate_limiter",
    "UserRegisterRequest",
    "UserRegisterResponse",
    "VerifyEmailRequest",
    "VerifyEmailResponse",
    "ResendVerificationRequest",
    "ResendVerificationResponse",
    "RegistrationService",
    "VerificationService",
    "auth_router",
    "get_auth_db",
    "get_client_ip",
]
