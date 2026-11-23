"""
FastAPI Authentication Router for Real-User Authentication (Stages 2 & 3).
Exposes /api/auth endpoints:
- POST /api/auth/register: User registration with email verification dispatch
- POST /api/auth/verify-email: Single-use token verification
- POST /api/auth/resend-verification: Verification email resend with enumeration defense
"""

from __future__ import annotations

import ipaddress
import os
from typing import Generator, List, Union
from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from sqlalchemy.orm import Session

from backend.auth.email_adapter import ResendEmailAdapter, get_email_adapter
from backend.auth.schemas import (
    ResendVerificationRequest,
    ResendVerificationResponse,
    UserRegisterRequest,
    UserRegisterResponse,
    VerifyEmailRequest,
    VerifyEmailResponse,
)
from backend.auth.service import RegistrationService, VerificationService
from backend.database import get_db

auth_router = APIRouter(tags=["Authentication"])


def get_auth_db() -> Generator[Session, None, None]:
    """Dependency provider yielding an isolated database session for auth routes."""
    yield from get_db()


TrustedNetwork = Union[ipaddress.IPv4Network, ipaddress.IPv6Network]


def _get_trusted_proxy_networks() -> List[TrustedNetwork]:
    """
    Parses trusted proxy IP addresses and CIDR networks strictly from AUTH_TRUSTED_PROXIES.
    Defaults to 127.0.0.1 and ::1.
    Rejects wildcards, non-IP hostnames, and invalid entries safely.
    """
    raw = os.getenv("AUTH_TRUSTED_PROXIES", "127.0.0.1,::1").strip()
    if not raw:
        return []
    networks: List[TrustedNetwork] = []
    for item in raw.split(","):
        entry = item.strip()
        if not entry or entry == "*":
            # Wildcards and empty entries are strictly rejected
            continue
        try:
            networks.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            # Non-IP hostnames and malformed strings are strictly rejected
            continue
    return networks


def _is_ip_trusted(ip_str: str, networks: List[TrustedNetwork]) -> bool:
    """Checks whether an IP address string falls strictly within configured trusted proxy networks."""
    if not networks:
        return False
    try:
        addr = ipaddress.ip_address(ip_str)
        return any(addr in net for net in networks)
    except ValueError:
        return False


def get_client_ip(request: Request) -> str:
    """
    Safely extracts the real client IP address, defending against X-Forwarded-For spoofing.
    - If request.client or request.client.host is missing, returns safe fallback '127.0.0.1'
      and never trusts or processes X-Forwarded-For.
    - If direct peer is not in AUTH_TRUSTED_PROXIES, X-Forwarded-For is ignored entirely.
    - If direct peer is trusted, parses X-Forwarded-For from right to left,
      skipping trusted proxies and selecting the first untrusted valid IP as the client.
    - Falls back safely to direct peer IP.
    """
    if not request.client or not request.client.host:
        return "127.0.0.1"

    direct_peer = request.client.host
    forwarded = request.headers.get("x-forwarded-for")
    if not forwarded:
        return direct_peer

    trusted_networks = _get_trusted_proxy_networks()

    # Step 1: If direct socket peer is not trusted, completely ignore X-Forwarded-For
    if not _is_ip_trusted(direct_peer, trusted_networks):
        return direct_peer

    # Step 2: Direct peer is trusted -> parse chain from right to left
    raw_hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
    for hop in reversed(raw_hops):
        try:
            ipaddress.ip_address(hop)
        except ValueError:
            # Malformed entry in forwarded chain -> skip safely
            continue

        if not _is_ip_trusted(hop, trusted_networks):
            return hop

    # If all forwarded hops were trusted (or no valid untrusted IP found), fall back to direct peer
    return direct_peer


@auth_router.post(
    "/register",
    response_model=UserRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Registers a new user, hashes password with Argon2id, generates a verification token, and dispatches a verification email.",
)
def register(
    payload: UserRegisterRequest,
    db: Session = Depends(get_auth_db),
    email_adapter: ResendEmailAdapter = Depends(get_email_adapter),
) -> UserRegisterResponse:
    """Endpoint handling new user registration."""
    return RegistrationService.register_user(db=db, payload=payload, email_adapter=email_adapter)


@auth_router.post(
    "/verify-email",
    response_model=VerifyEmailResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify user email address",
    description="Validates single-use token, marks user account as verified, and marks token as used atomically.",
)
def verify_email(
    payload: VerifyEmailRequest,
    request: Request,
    db: Session = Depends(get_auth_db),
) -> VerifyEmailResponse:
    """Endpoint handling email verification token consumption."""
    client_ip = get_client_ip(request)
    return VerificationService.verify_email(db=db, payload=payload, client_ip=client_ip)


@auth_router.post(
    "/resend-verification",
    response_model=ResendVerificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Resend verification email",
    description="Generates a fresh verification link for unverified accounts, protected by rate limiting and anti-enumeration generic responses.",
)
def resend_verification(
    payload: ResendVerificationRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_auth_db),
    email_adapter: ResendEmailAdapter = Depends(get_email_adapter),
) -> ResendVerificationResponse:
    """Endpoint handling verification email resend requests."""
    client_ip = get_client_ip(request)
    return VerificationService.resend_verification(
        db=db,
        payload=payload,
        email_adapter=email_adapter,
        client_ip=client_ip,
        background_tasks=background_tasks,
    )
