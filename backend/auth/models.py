"""
SQLAlchemy ORM Models for Real-User Authentication & Security Foundations.
Scope: Exclusively for actual application users (researchers, administrators, public users).
Completely decoupled from synthetic student personas and the simulation engine.

Uses an isolated DeclarativeBase (AuthBase) so authentication tables never
contaminate or interfere with Base.metadata from simulation domain models.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    TypeDecorator,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from backend.database import engine as default_engine


# -----------------------------------------------------------------------------
# 1. Custom UTCDateTime TypeDecorator
# -----------------------------------------------------------------------------
class UTCDateTime(TypeDecorator):
    """
    Ensures datetimes are stored in UTC in SQLite and always retrieved
    as timezone-aware UTC datetime objects.
    """
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: Optional[datetime], dialect: Any) -> Optional[datetime]:
        if value is not None:
            if not isinstance(value, datetime):
                raise TypeError(f"Expected datetime object, got {type(value)}")
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            else:
                value = value.astimezone(timezone.utc)
            return value.replace(tzinfo=None)
        return None

    def process_result_value(self, value: Optional[datetime], dialect: Any) -> Optional[datetime]:
        if value is not None:
            return value.replace(tzinfo=timezone.utc)
        return None


# -----------------------------------------------------------------------------
# 2. Isolated Declarative Base for Authentication
# -----------------------------------------------------------------------------
class AuthBase(DeclarativeBase):
    """
    Dedicated declarative base for application user authentication tables.
    Maintains complete isolation from Base.metadata to prevent test metadata contamination.
    """
    pass


# -----------------------------------------------------------------------------
# 3. User Model
# -----------------------------------------------------------------------------
class UserDB(AuthBase):
    """
    Real human user of the Maharashtra Policy Simulator platform.
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="user")
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    verification_tokens: Mapped[List[EmailVerificationTokenDB]] = relationship(
        "EmailVerificationTokenDB",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    password_reset_tokens: Mapped[List[PasswordResetTokenDB]] = relationship(
        "PasswordResetTokenDB",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    sessions: Mapped[List[UserSessionDB]] = relationship(
        "UserSessionDB",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @staticmethod
    def normalize_email(email_str: str) -> str:
        """Strips whitespace and normalizes email address to lowercase."""
        if not email_str or not isinstance(email_str, str):
            raise ValueError("Email must be a non-empty string.")
        return email_str.strip().lower()

    def __repr__(self) -> str:
        return f"<UserDB id={self.id} email='{self.email}' is_verified={self.is_verified} role='{self.role}'>"


# -----------------------------------------------------------------------------
# 4. Email Verification Token Model
# -----------------------------------------------------------------------------
class EmailVerificationTokenDB(AuthBase):
    """
    Cryptographic single-use token for email verification.
    Stores the SHA-256 hash of the raw token, never the raw token itself.
    """
    __tablename__ = "email_verification_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    used_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True, default=None)

    # Relationship
    user: Mapped[UserDB] = relationship("UserDB", back_populates="verification_tokens")

    @property
    def is_valid(self) -> bool:
        """Token is valid if unused and not expired."""
        if self.used_at is not None:
            return False
        now_utc = datetime.now(timezone.utc)
        return now_utc < self.expires_at

    def __repr__(self) -> str:
        return f"<EmailVerificationTokenDB id={self.id} user_id={self.user_id} is_valid={self.is_valid}>"


# -----------------------------------------------------------------------------
# 5. Password Reset Token Model
# -----------------------------------------------------------------------------
class PasswordResetTokenDB(AuthBase):
    """
    Cryptographic single-use token for password reset workflows.
    Stores the SHA-256 hash of the raw token, never the raw token itself.
    """
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    used_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True, default=None)

    # Relationship
    user: Mapped[UserDB] = relationship("UserDB", back_populates="password_reset_tokens")

    @property
    def is_valid(self) -> bool:
        """Token is valid if unused and not expired."""
        if self.used_at is not None:
            return False
        now_utc = datetime.now(timezone.utc)
        return now_utc < self.expires_at

    def __repr__(self) -> str:
        return f"<PasswordResetTokenDB id={self.id} user_id={self.user_id} is_valid={self.is_valid}>"


# -----------------------------------------------------------------------------
# 6. User Session Model (Opaque Server-Managed Session)
# -----------------------------------------------------------------------------
class UserSessionDB(AuthBase):
    """
    Server-managed opaque session record.
    The client cookie stores an unguessable high-entropy session identifier;
    the database stores the SHA-256 hash to defend against database credential dumps.
    """
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    session_id_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    is_revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationship
    user: Mapped[UserDB] = relationship("UserDB", back_populates="sessions")

    @property
    def is_active(self) -> bool:
        """Session is active if unrevoked and not expired."""
        if self.is_revoked:
            return False
        now_utc = datetime.now(timezone.utc)
        return now_utc < self.expires_at

    def __repr__(self) -> str:
        return f"<UserSessionDB id={self.id} user_id={self.user_id} is_active={self.is_active}>"


# -----------------------------------------------------------------------------
# 7. Isolated Table Initialization Helper
# -----------------------------------------------------------------------------
def init_auth_db(target_engine: Optional[Engine] = None) -> None:
    """
    Initializes only the authentication tables against the target engine.
    Safe to use with in-memory SQLite engines for testing.
    """
    eng = target_engine or default_engine
    AuthBase.metadata.create_all(bind=eng)
