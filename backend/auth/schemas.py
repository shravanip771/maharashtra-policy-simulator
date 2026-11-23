"""
Pydantic Schemas for Real-User Authentication (Stages 2 & 3).
Exclusively for actual application users. Decoupled from simulation personas.
"""

from __future__ import annotations

import re
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

# Standard RFC-compliant email pattern without external email-validator dependency
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+$")


class UserRegisterRequest(BaseModel):
    """
    Request payload for new user registration.
    Enforces email format validation, trimmed non-empty full name,
    and a minimum password length of 8 characters.
    """
    email: str = Field(
        ...,
        description="User email address. Will be normalized to lowercase.",
        examples=["researcher@example.gov.in"],
    )
    full_name: str = Field(
        ...,
        min_length=1,
        max_length=150,
        description="Full name of the user.",
        examples=["Dr. Sunita Deshmukh"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Plaintext password (minimum 8 characters).",
        examples=["SecurePassw0rd!"],
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Email cannot be blank or whitespace-only.")
        if " " in trimmed or "@" not in trimmed:
            raise ValueError("Invalid email format.")
        if not EMAIL_REGEX.match(trimmed):
            raise ValueError("Invalid email format.")
        return trimmed

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Full name cannot be blank or whitespace-only.")
        return trimmed

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if len(v) > 128:
            raise ValueError("Password must not exceed 128 characters.")
        return v


class UserRegisterResponse(BaseModel):
    """
    Response DTO returned upon successful registration.
    Strictly excludes sensitive cryptographic material (never includes raw tokens or password hashes).
    """
    id: int = Field(..., description="Unique database identifier of the created user.")
    email: str = Field(..., description="Normalized user email address.")
    full_name: str = Field(..., description="Full name of the registered user.")
    is_active: bool = Field(..., description="Whether the user account is active.")
    is_verified: bool = Field(..., description="Whether the user email is verified.")
    role: str = Field(..., description="Access control role (e.g. 'user', 'researcher').")
    message: str = Field(..., description="User-facing status message.")
    verification_email_sent: bool = Field(..., description="Whether the verification email was successfully dispatched.")

    model_config = ConfigDict(from_attributes=True)


# -----------------------------------------------------------------------------
# Stage 3: Email Verification Schemas
# -----------------------------------------------------------------------------

class VerifyEmailRequest(BaseModel):
    """
    Request payload to verify an account email address using a single-use token.
    """
    token: str = Field(
        ...,
        min_length=16,
        description="Raw verification token string received via email.",
        examples=["eXamP1e-t0kEn_sTr1ng-vEr1fY2026"],
    )

    @field_validator("token")
    @classmethod
    def validate_token(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Verification token cannot be empty.")
        if len(trimmed) < 16:
            raise ValueError("Invalid verification token format.")
        return trimmed


class VerifyEmailResponse(BaseModel):
    """
    Response DTO indicating the result of an email verification attempt.
    """
    message: str = Field(..., description="Result message for user feedback.")
    email: Optional[str] = Field(None, description="Email address verified (if successful).")
    is_verified: bool = Field(..., description="Current verification state of the user account.")


# -----------------------------------------------------------------------------
# Stage 3: Resend Verification Schemas
# -----------------------------------------------------------------------------

class ResendVerificationRequest(BaseModel):
    """
    Request payload to request a fresh verification email link.
    """
    email: str = Field(
        ...,
        description="Email address of the unverified user account.",
        examples=["researcher@example.gov.in"],
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Email cannot be blank or whitespace-only.")
        if " " in trimmed or "@" not in trimmed or not EMAIL_REGEX.match(trimmed):
            raise ValueError("Invalid email format.")
        return trimmed


class ResendVerificationResponse(BaseModel):
    """
    Generic response DTO for verification email resend requests.
    Intentionally vague to prevent user enumeration attacks.
    """
    message: str = Field(
        ...,
        description="Generic message confirming that a verification link was dispatched if the account exists and is unverified.",
    )
