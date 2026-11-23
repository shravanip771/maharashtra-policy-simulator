"""
Security Utilities for Maharashtra Policy Simulator Real-User Authentication.
Provides:
- Argon2id password hashing and constant-time verification
- Cryptographically secure token generation
- Token hashing (SHA-256) and constant-time comparison
- Expiration checks
- High-entropy session identifier generation
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from typing import Optional

from argon2 import PasswordHasher, Type
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)

# Standard Argon2id configuration (OWASP recommended parameters):
# Memory: 64MB (65536 KiB), Time: 2 iterations, Parallelism: 1 lane, Hash length: 32 bytes
_HASHER = PasswordHasher(
    time_cost=2,
    memory_cost=65536,
    parallelism=1,
    hash_len=32,
    type=Type.ID,
)


def hash_password(password: str) -> str:
    """
    Hashes a plaintext password using Argon2id with cryptographically secure salt.
    Never stores or returns plaintext.
    """
    if not password or not isinstance(password, str):
        raise ValueError("Password must be a non-empty string.")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    return _HASHER.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verifies a plaintext password against an Argon2id hash using constant-time comparison.
    Returns False on any mismatch, invalid format, or error.
    """
    if not password or not hashed_password:
        return False
    try:
        return _HASHER.verify(hashed_password, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    except Exception:
        return False


def needs_rehash(hashed_password: str) -> bool:
    """Checks whether the password hash was generated with older/weaker parameters."""
    try:
        return _HASHER.check_needs_rehash(hashed_password)
    except Exception:
        return True


def generate_secure_token(nbytes: int = 32) -> str:
    """
    Generates a cryptographically secure, unguessable URL-safe random string.
    Suitable for email verification tokens, password reset links, etc.
    """
    if nbytes < 16:
        raise ValueError("Token entropy must be at least 16 bytes.")
    return secrets.token_urlsafe(nbytes)


def hash_token(raw_token: str) -> str:
    """
    Computes the SHA-256 hex digest of a token string.
    Tokens must be hashed before storage in the database to prevent token theft from DB dumps.
    """
    if not raw_token or not isinstance(raw_token, str):
        raise ValueError("Token must be a non-empty string.")
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def verify_token_hash(raw_token: str, stored_hash: str) -> bool:
    """
    Verifies a raw token against a stored SHA-256 hash using constant-time comparison.
    Defends against timing attacks.
    """
    if not raw_token or not stored_hash:
        return False
    computed_hash = hash_token(raw_token)
    return hmac.compare_digest(computed_hash, stored_hash)


def generate_session_id() -> str:
    """
    Generates a high-entropy 256-bit (32 bytes / 43-44 chars) random session identifier
    suitable for opaque session cookies.
    """
    return secrets.token_urlsafe(32)


def is_token_expired(expires_at: datetime) -> bool:
    """
    Checks whether a timestamp is in the past relative to current UTC time.
    Safely handles both timezone-aware (UTC) and naive timestamps.
    """
    if expires_at is None:
        return True
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) >= expires_at
