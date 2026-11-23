"""
Session and Cookie Architecture for Maharashtra Policy Simulator.
Defines server-managed opaque session configuration, cookie attributes,
and security policies.

Architectural Rationale for Opaque Sessions over JWT:
1. Instant Server-Side Revocation:
   - When a user logs out, their session is immediately marked revoked (is_revoked=True).
   - In the event of password reset or account compromise, all existing sessions for that
     user can be invalidated server-side in a single query.
   - Stateless JWTs cannot be revoked prior to their expiry without maintaining a stateful
     revocation blacklist, which negates the primary benefit of JWTs.
2. XSS Protection via HttpOnly Cookies:
   - Opaque session identifiers stored in HttpOnly cookies are completely inaccessible to
     client-side JavaScript (document.cookie). This defends against credential exfiltration
     via Cross-Site Scripting (XSS).
3. Session Integrity & Hash Storage:
   - The raw session ID exists only in the user's browser cookie and is never stored in plaintext
     in the database. The database records only the SHA-256 hash (session_id_hash). Even if
     the database is leaked, session IDs cannot be used to hijack user accounts.
"""

import os
from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class SessionCookieConfig:
    """
    Configuration for server-managed session cookies.
    Enforces OWASP session management recommendations.
    """
    cookie_name: str = "mps_session_id"
    max_age_seconds: int = 7 * 24 * 60 * 60  # 7 days
    httponly: bool = True                    # Inaccessible to JS document.cookie
    secure: bool = False                     # Enforced in production (HTTPS)
    samesite: str = "lax"                    # Mitigates CSRF on cross-origin requests
    path: str = "/"                          # Global path for API session access

    @classmethod
    def from_env(cls) -> "SessionCookieConfig":
        """
        Loads session configuration from environment variables,
        defaulting to secure production defaults when ENV=production.
        """
        env = os.getenv("ENV", "development").lower()
        is_production = env in ["production", "prod"]
        
        # In production, secure cookies are mandatory (HTTPS required)
        secure_default = is_production or os.getenv("SESSION_COOKIE_SECURE", "").lower() in ["true", "1"]
        
        cookie_name = os.getenv("SESSION_COOKIE_NAME", "mps_session_id")
        max_age = int(os.getenv("SESSION_MAX_AGE_SECONDS", str(7 * 24 * 60 * 60)))
        samesite = os.getenv("SESSION_COOKIE_SAMESITE", "lax").lower()
        if samesite not in ["lax", "strict", "none"]:
            samesite = "lax"

        return cls(
            cookie_name=cookie_name,
            max_age_seconds=max_age,
            httponly=True,  # Always mandatory for security
            secure=secure_default,
            samesite=samesite,
            path="/",
        )

    def to_cookie_kwargs(self) -> Dict[str, Any]:
        """Returns standard kwargs for Starlette/FastAPI Response.set_cookie()."""
        return {
            "key": self.cookie_name,
            "max_age": self.max_age_seconds,
            "httponly": self.httponly,
            "secure": self.secure,
            "samesite": self.samesite,
            "path": self.path,
        }

    def to_delete_cookie_kwargs(self) -> Dict[str, Any]:
        """Returns kwargs for Starlette/FastAPI Response.delete_cookie()."""
        return {
            "key": self.cookie_name,
            "path": self.path,
            "httponly": self.httponly,
            "secure": self.secure,
            "samesite": self.samesite,
        }


# Default singleton instance
DEFAULT_SESSION_COOKIE_CONFIG = SessionCookieConfig.from_env()
