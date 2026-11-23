"""
Transactional Email Adapter for Maharashtra Policy Simulator using Resend.
Provides decoupled email dispatch for user registration verification.

Key Requirements:
- No hardcoded credentials (uses ResendConfig from environment).
- Graceful handling of unconfigured environments (e.g. dev/test modes).
- Strict secret hygiene: never logs raw tokens, passwords, or API keys.
- Robust timeout and HTTP error handling via httpx.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from backend.auth.email_config import ResendConfig, get_resend_config

logger = logging.getLogger("backend.auth.email_adapter")


class ResendEmailAdapter:
    """
    Adapter for dispatching transactional emails through Resend's REST API.
    Designed for dependency injection and safe mocking during automated tests.
    """

    RESEND_API_ENDPOINT = "https://api.resend.com/emails"

    def __init__(self, config: Optional[ResendConfig] = None, http_client: Optional[httpx.Client] = None) -> None:
        self.config = config or get_resend_config()
        self._http_client = http_client

    def build_verification_link(self, raw_token: str) -> str:
        """
        Constructs the client-facing verification URL.
        Format: {frontend_base_url}/verify-email?token={raw_token}
        """
        base = self.config.frontend_base_url.rstrip("/")
        return f"{base}/verify-email?token={raw_token}"

    def send_verification_email(
        self,
        to_email: str,
        recipient_name: str,
        raw_token: str,
    ) -> bool:
        """
        Dispatches an email verification link to a newly registered user.

        Args:
            to_email: Recipient email address.
            recipient_name: Recipient full name.
            raw_token: Unhashed verification token string.

        Returns:
            bool: True if the email was successfully accepted by Resend, False otherwise.
        """
        if not self.config.is_configured:
            logger.warning(
                "Resend email dispatch skipped: Missing configuration (RESEND_API_KEY or RESEND_FROM_EMAIL not set). "
                "Email verification link would be: [REDACTED_LINK] for recipient: %s",
                to_email,
            )
            return False

        verification_link = self.build_verification_link(raw_token)

        html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Verify Your Email</title>
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
  <h2 style="color: #1a365d;">Welcome to Maharashtra Policy Simulator</h2>
  <p>Hello {recipient_name},</p>
  <p>Thank you for registering. Please confirm your email address by clicking the button below:</p>
  <p style="text-align: center; margin: 30px 0;">
    <a href="{verification_link}" style="background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">
      Verify Email Address
    </a>
  </p>
  <p style="font-size: 0.9em; color: #666;">
    If the button above does not work, copy and paste this URL into your browser:<br>
    <a href="{verification_link}" style="color: #2563eb; word-break: break-all;">{verification_link}</a>
  </p>
  <p style="font-size: 0.85em; color: #888; margin-top: 30px;">
    This link is valid for 24 hours. If you did not create an account on the Maharashtra Policy Simulator, you can safely ignore this email.
  </p>
</body>
</html>"""

        text_content = (
            f"Hello {recipient_name},\n\n"
            f"Thank you for registering on Maharashtra Policy Simulator.\n"
            f"Please verify your email address by opening the following link in your browser:\n\n"
            f"{verification_link}\n\n"
            f"This link expires in 24 hours.\n"
            f"If you did not create this account, please disregard this email."
        )

        payload = {
            "from": self.config.from_email,
            "to": [to_email],
            "subject": "Verify your email for Maharashtra Policy Simulator",
            "html": html_content,
            "text": text_content,
        }

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        try:
            if self._http_client is not None:
                response = self._http_client.post(
                    self.RESEND_API_ENDPOINT,
                    json=payload,
                    headers=headers,
                    timeout=10.0,
                )
            else:
                with httpx.Client(timeout=10.0) as client:
                    response = client.post(
                        self.RESEND_API_ENDPOINT,
                        json=payload,
                        headers=headers,
                    )

            if response.status_code in (200, 201):
                logger.info("Verification email successfully dispatched via Resend to %s", to_email)
                return True
            else:
                logger.error(
                    "Resend API rejected email dispatch to %s (Status: %d). Details masked for security.",
                    to_email,
                    response.status_code,
                )
                return False

        except httpx.TimeoutException:
            logger.error("Resend API timed out while attempting to dispatch verification email to %s", to_email)
            return False
        except httpx.RequestError as exc:
            logger.error(
                "Network or HTTP error communicating with Resend for recipient %s: %s",
                to_email,
                type(exc).__name__,
            )
            return False
        except Exception as exc:
            logger.error(
                "Unexpected failure in Resend email adapter for recipient %s: %s",
                to_email,
                type(exc).__name__,
            )
            return False


def get_email_adapter() -> ResendEmailAdapter:
    """FastAPI dependency provider for the Resend email adapter."""
    return ResendEmailAdapter()
