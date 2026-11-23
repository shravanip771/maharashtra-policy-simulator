"""
Email Configuration Interface for Maharashtra Policy Simulator.
Configures Resend email credentials from environment variables.

Strict Requirements:
- No hardcoded credentials.
- Clear missing-configuration behavior.
- Never logs or exposes raw secrets in __repr__ or error messages.
- Does NOT send actual emails or invoke live external network calls during Stage 1.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ResendConfig:
    """
    Configuration interface for Resend transactional email service.
    Reads values from environment variables: RESEND_API_KEY, RESEND_FROM_EMAIL.
    """
    api_key: str
    from_email: str
    frontend_base_url: str = "http://localhost:5173"

    @property
    def is_configured(self) -> bool:
        """Returns True only when both API key and verified from_email are present."""
        return bool(self.api_key and self.from_email)

    def validate(self) -> None:
        """
        Validates that required configuration is present.
        Raises ValueError with clear, actionable guidance if unconfigured.
        """
        if not self.api_key:
            raise ValueError(
                "Resend API key is missing. Set the 'RESEND_API_KEY' environment variable. "
                "In local development, use console logging or mock dispatch."
            )
        if not self.from_email:
            raise ValueError(
                "Resend sender email is missing. Set the 'RESEND_FROM_EMAIL' environment variable "
                "(e.g., 'Maharashtra Policy Simulator <notifications@yourdomain.com>')."
            )

    def mask_key(self) -> str:
        """Safely masks the API key for logging and diagnostic display."""
        if not self.api_key:
            return "[NOT SET]"
        if len(self.api_key) <= 8:
            return "***"
        return f"{self.api_key[:4]}...{self.api_key[-4:]}"

    def __repr__(self) -> str:
        return (
            f"<ResendConfig is_configured={self.is_configured} "
            f"from_email='{self.from_email or '[NOT SET]'}' "
            f"api_key='{self.mask_key()}'>"
        )


def get_resend_config() -> ResendConfig:
    """
    Factory function to retrieve current Resend configuration from environment.
    Falls back gracefully to safe defaults when unconfigured.
    """
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    from_email = os.getenv("RESEND_FROM_EMAIL", "").strip()
    frontend_base_url = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173").strip()

    return ResendConfig(
        api_key=api_key,
        from_email=from_email,
        frontend_base_url=frontend_base_url,
    )
