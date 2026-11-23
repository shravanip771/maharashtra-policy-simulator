-- =============================================================================
-- Migration 001: Create Authentication and Security Tables
-- Target Database: SQLite 3.x / PostgreSQL compatible DDL
-- Project: Maharashtra Policy Simulator
-- Scope: Real-User Authentication & Security Foundations (Stage 1 & 2)
-- Status: DRAFT / PENDING REVIEW (NOT YET APPLIED TO PRODUCTION)
-- =============================================================================
-- Description:
-- Creates the four foundational authentication tables required for real human users:
--   1. users: Account identity, Argon2id password hash, verified flag, role.
--   2. email_verification_tokens: SHA-256 hashed single-use verification tokens.
--   3. password_reset_tokens: SHA-256 hashed single-use password reset tokens.
--   4. user_sessions: Server-managed opaque sessions with SHA-256 hashed session identifiers.
--
-- Safety Guarantees:
--   - Completely isolated from the 12 simulation domain tables.
--   - Uses IF NOT EXISTS to prevent accidental table re-creation.
--   - Does NOT drop or truncate any existing database objects.
--   - Enforces foreign key cascades on user deletion.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Users Table
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email VARCHAR(255) NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    is_verified BOOLEAN NOT NULL DEFAULT 0,
    role VARCHAR(50) NOT NULL DEFAULT 'user',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email);

-- -----------------------------------------------------------------------------
-- 2. Email Verification Tokens Table
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS email_verification_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_hash VARCHAR(64) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    used_at TIMESTAMP NULL,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_email_verification_tokens_token_hash ON email_verification_tokens (token_hash);
CREATE INDEX IF NOT EXISTS ix_email_verification_tokens_user_id ON email_verification_tokens (user_id);

-- -----------------------------------------------------------------------------
-- 3. Password Reset Tokens Table
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_hash VARCHAR(64) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    used_at TIMESTAMP NULL,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_password_reset_tokens_token_hash ON password_reset_tokens (token_hash);
CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_user_id ON password_reset_tokens (user_id);

-- -----------------------------------------------------------------------------
-- 4. User Sessions Table (Opaque Session Store)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    session_id_hash VARCHAR(64) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    last_activity_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_revoked BOOLEAN NOT NULL DEFAULT 0,
    ip_address VARCHAR(45) NULL,
    user_agent VARCHAR(500) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_user_sessions_session_id_hash ON user_sessions (session_id_hash);
CREATE INDEX IF NOT EXISTS ix_user_sessions_user_id ON user_sessions (user_id);

-- =============================================================================
-- ROLLBACK SCRIPT (For reference only - execute with caution)
-- =============================================================================
-- DROP TABLE IF EXISTS user_sessions;
-- DROP TABLE IF EXISTS password_reset_tokens;
-- DROP TABLE IF EXISTS email_verification_tokens;
-- DROP TABLE IF EXISTS users;
-- =============================================================================
