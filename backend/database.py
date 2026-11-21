"""
Database Foundation Module for Maharashtra Policy Simulator.
Configures modern SQLAlchemy 2.x DeclarativeBase, session management,
project-relative path resolution, and SQLite foreign-key enforcement.
"""

import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# -----------------------------------------------------------------------------
# 1. Deterministic Project-Relative Path Resolution
# -----------------------------------------------------------------------------
# Resolve the project root dynamically (parent of the 'backend' folder)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Default SQLite database file path anchored predictably in the project root
DEFAULT_DB_FILE = PROJECT_ROOT / "simulator.db"
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_DB_FILE.as_posix()}"

# Allow override via DATABASE_URL environment variable
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

# Parse database URL safely and ensure parent directory exists for file-based SQLite databases
parsed_url = make_url(DATABASE_URL)
if parsed_url.get_backend_name() == "sqlite" and parsed_url.database and parsed_url.database != ":memory:":
    db_file_path = Path(parsed_url.database)
    db_file_path.parent.mkdir(parents=True, exist_ok=True)


# -----------------------------------------------------------------------------
# 2. Modern SQLAlchemy 2.x Declarative Base
# -----------------------------------------------------------------------------
class Base(DeclarativeBase):
    """
    Foundational declarative base for all Maharashtra Policy Simulator database models.
    Enforces SQLAlchemy 2.x Mapped column types and centralized metadata collection.
    """
    pass


# -----------------------------------------------------------------------------
# 3. SQLite-Specific Foreign Key Enforcement Listener
# -----------------------------------------------------------------------------
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record) -> None:
    """
    Ensures foreign key constraint checks are active on SQLite connections.
    Executes 'PRAGMA foreign_keys=ON' ONLY when connected to a SQLite database.
    Does not execute SQLite-specific pragmas on other database dialects.
    """
    is_sqlite = False

    # Check 1: Direct DBAPI connection type check
    if isinstance(dbapi_connection, sqlite3.Connection):
        is_sqlite = True
    # Check 2: Inspect connection_record engine dialect name if available
    elif getattr(connection_record, "engine", None) and getattr(connection_record.engine, "name", "") == "sqlite":
        is_sqlite = True
    elif "sqlite" in type(dbapi_connection).__module__.lower():
        is_sqlite = True

    if is_sqlite:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# -----------------------------------------------------------------------------
# 4. Engine & Session Factory Configuration
# -----------------------------------------------------------------------------
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    echo=False
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)


# -----------------------------------------------------------------------------
# 5. Session Context Managers, Generators & Lifecycle Helpers
# -----------------------------------------------------------------------------
@contextmanager
def get_db_session(session_factory: Optional[sessionmaker[Session]] = None) -> Generator[Session, None, None]:
    """
    Context manager for standalone scripts, batch simulations, and isolated test suites.
    Supports injecting an isolated session_factory (e.g. for in-memory testing).
    Automatically commits on exit, rolls back on exception, and guarantees session closure.
    """
    factory = session_factory or SessionLocal
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db(session_factory: Optional[sessionmaker[Session]] = None) -> Generator[Session, None, None]:
    """
    Dependency generator for FastAPI routes (supports isolated session factory injection).
    Yields a session and guarantees closure upon request completion.
    """
    factory = session_factory or SessionLocal
    session: Session = factory()
    try:
        yield session
    finally:
        session.close()


def init_db(target_engine: Engine = engine) -> None:
    """
    Creates all tables defined in Base.metadata against target_engine (safe and idempotent).
    Defaults to the application's global engine, but accepts an isolated test engine.
    """
    import backend.db_models  # noqa: F401
    Base.metadata.create_all(bind=target_engine)
