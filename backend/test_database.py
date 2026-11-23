"""
Automated Unit Tests for Database Foundation (Phase 2).
Tests engine connectivity, session management, project-relative path resolution,
and SQLite foreign key enforcement against an isolated in-memory database.
Zero disk footprint: Never writes to or deletes the development database.
"""

from pathlib import Path
from sqlalchemy import Integer, String, ForeignKey, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import IntegrityError

from backend.database import (
    Base,
    PROJECT_ROOT,
    DEFAULT_DB_FILE,
    get_db_session,
    get_db,
    init_db
)

# -----------------------------------------------------------------------------
# Minimal Temporary ORM Models for Foundation Verification (Isolated Base)
# -----------------------------------------------------------------------------
class TestModelBase(DeclarativeBase):
    """Isolated declarative base for temporary test models to avoid polluting Base.metadata."""
    __test__ = False


class TestParent(TestModelBase):
    __test__ = False
    __tablename__ = "_test_parents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50))


class TestChild(TestModelBase):
    __test__ = False
    __tablename__ = "_test_children"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_id: Mapped[int] = mapped_column(Integer, ForeignKey("_test_parents.id", ondelete="RESTRICT"))


# -----------------------------------------------------------------------------
# Isolated In-Memory Test Fixture Helpers
# -----------------------------------------------------------------------------
def create_isolated_test_engine():
    """Creates a strictly in-memory SQLite engine isolated from development files."""
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )


# -----------------------------------------------------------------------------
# Test Cases
# -----------------------------------------------------------------------------
def test_project_root_database_path_resolution():
    """Verifies that the default database path is anchored predictably to the project root."""
    assert PROJECT_ROOT.exists(), "PROJECT_ROOT must exist on disk"
    assert (PROJECT_ROOT / "backend").is_dir(), "PROJECT_ROOT must contain backend/"
    assert DEFAULT_DB_FILE == PROJECT_ROOT / "simulator.db", "DEFAULT_DB_FILE must point to simulator.db in project root"
    print("PASS: test_project_root_database_path_resolution")


def test_in_memory_engine_connectivity():
    """Verifies that an in-memory SQLite connection opens cleanly and executes queries."""
    test_engine = create_isolated_test_engine()
    with test_engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
        assert result == 1, "SELECT 1 must return 1"
    print("PASS: test_in_memory_engine_connectivity")


def test_sqlite_foreign_key_pragma_enforcement():
    """Verifies that the connect listener executes 'PRAGMA foreign_keys=ON' for SQLite."""
    test_engine = create_isolated_test_engine()
    with test_engine.connect() as conn:
        pragma_val = conn.execute(text("PRAGMA foreign_keys")).scalar()
        assert pragma_val == 1, "PRAGMA foreign_keys must be 1 (ON) for SQLite connections"
    print("PASS: test_sqlite_foreign_key_pragma_enforcement")


def test_table_creation_in_isolated_database():
    """Verifies that init_db() creates tables against the isolated in-memory engine."""
    test_engine = create_isolated_test_engine()
    init_db(target_engine=test_engine)
    TestModelBase.metadata.create_all(bind=test_engine)

    with test_engine.connect() as conn:
        # Check that test tables exist in sqlite_master
        tables = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).scalars().all()
        assert "_test_parents" in tables
        assert "_test_children" in tables
        assert "policies" in tables
    print("PASS: test_table_creation_in_isolated_database")


def test_foreign_key_constraint_blocks_orphaned_records():
    """Verifies that SQLite strictly blocks inserting child rows with invalid parent IDs."""
    test_engine = create_isolated_test_engine()
    init_db(target_engine=test_engine)
    TestModelBase.metadata.create_all(bind=test_engine)

    test_factory = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)

    # 1. Valid parent insertion succeeds
    with get_db_session(session_factory=test_factory) as session:
        parent = TestParent(id=1, name="Valid Parent")
        session.add(parent)

    # 2. Inserting child with valid parent succeeds
    with get_db_session(session_factory=test_factory) as session:
        child = TestChild(id=10, parent_id=1)
        session.add(child)

    # 3. Inserting child with nonexistent parent (ID=999) raises IntegrityError
    integrity_error_raised = False
    try:
        with get_db_session(session_factory=test_factory) as session:
            orphaned_child = TestChild(id=20, parent_id=999)
            session.add(orphaned_child)
    except IntegrityError:
        integrity_error_raised = True

    assert integrity_error_raised, "Foreign key violation must raise IntegrityError"
    print("PASS: test_foreign_key_constraint_blocks_orphaned_records")


def test_session_context_manager_commit_and_rollback():
    """Verifies that get_db_session commits valid transactions and rolls back on error."""
    test_engine = create_isolated_test_engine()
    init_db(target_engine=test_engine)
    TestModelBase.metadata.create_all(bind=test_engine)

    test_factory = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)

    # 1. Commit verification
    with get_db_session(session_factory=test_factory) as session:
        p1 = TestParent(id=100, name="Committed Parent")
        session.add(p1)

    with test_engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM _test_parents WHERE id=100")).scalar()
        assert count == 1, "Record must be committed"

    # 2. Rollback verification on exception
    try:
        with get_db_session(session_factory=test_factory) as session:
            p2 = TestParent(id=200, name="Aborted Parent")
            session.add(p2)
            raise RuntimeError("Simulated transaction failure")
    except RuntimeError:
        pass

    with test_engine.connect() as conn:
        count_aborted = conn.execute(text("SELECT COUNT(*) FROM _test_parents WHERE id=200")).scalar()
        assert count_aborted == 0, "Aborted record must be rolled back"
    print("PASS: test_session_context_manager_commit_and_rollback")


def test_get_db_generator_lifecycle():
    """Verifies that get_db() yields a functional session and closes it on exit."""
    test_engine = create_isolated_test_engine()
    init_db(target_engine=test_engine)
    TestModelBase.metadata.create_all(bind=test_engine)

    test_factory = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)

    gen = get_db(session_factory=test_factory)
    session = next(gen)
    assert session is not None, "get_db must yield a session"

    # Session is operational
    session.add(TestParent(id=300, name="Generator Parent"))
    session.commit()

    # Generator finalization closes session
    try:
        next(gen)
    except StopIteration:
        pass

    print("PASS: test_get_db_generator_lifecycle")


# -----------------------------------------------------------------------------
# Main Test Runner
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    print("Running Database Foundation Tests (Phase 2)...")
    test_project_root_database_path_resolution()
    test_in_memory_engine_connectivity()
    test_sqlite_foreign_key_pragma_enforcement()
    test_table_creation_in_isolated_database()
    test_foreign_key_constraint_blocks_orphaned_records()
    test_session_context_manager_commit_and_rollback()
    test_get_db_generator_lifecycle()
    print("All Database Foundation tests passed successfully!")
