"""
Unit Test Suite for SQLAlchemy ORM Models (Phase 2 - Step 2).
Tests all 12 ORM models, constraints, relationships, UTC timestamps,
JSON round-tripping, CheckConstraints, and deletion restrictions
against an isolated in-memory SQLite database.
"""

import unittest
from datetime import datetime, timezone
from typing import Generator

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from backend.database import Base, init_db
from backend.db_models import (
    ApplicationAuditLogDB,
    ApplicationEligibilityEvaluationDB,
    ApplicationEvaluationStage,
    ApplicationLifecycleStatus,
    ApplicationRecordDB,
    AuditActor,
    ConfidenceLevel,
    EvaluationActor,
    IndividualOutcomeDB,
    PersonaInteractionDB,
    PersonaRunStateDB,
    PolicyConfigurationDB,
    PolicyDB,
    ScenarioConfigurationDB,
    SimulationRunDB,
    SimulationRunStatus,
    SimulationState,
    SyntheticPersonaDB,
    UTCDateTime,
)


class TestORMModels(unittest.TestCase):
    """Isolated in-memory test suite for Maharashtra Policy Simulator ORM models."""

    @classmethod
    def setUpClass(cls):
        # Create an isolated in-memory SQLite engine
        cls.engine: Engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            echo=False
        )

        # Attach foreign key listener for this isolated test engine
        @event.listens_for(cls.engine, "connect")
        def set_sqlite_fk(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        # Create all tables using init_db
        init_db(cls.engine)

        cls.SessionLocal = sessionmaker(
            bind=cls.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False
        )

    def setUp(self):
        self.session: Session = self.SessionLocal()

    def tearDown(self):
        self.session.rollback()
        self.session.close()

    # -------------------------------------------------------------------------
    # 1. Model Registration & Table Existence
    # -------------------------------------------------------------------------
    def test_model_registration_and_table_count(self):
        """Verify that all 12 tables are registered in Base.metadata."""
        expected_tables = {
            "policies",
            "policy_configurations",
            "synthetic_personas",
            "scenario_configurations",
            "simulation_runs",
            "persona_run_states",
            "persona_interactions",
            "individual_outcomes",
            "aggregate_results",
            "application_lifecycle_records",
            "application_eligibility_evaluations",
            "application_audit_logs",
        }
        registered_tables = set(Base.metadata.tables.keys())
        self.assertEqual(len(registered_tables), 12)
        self.assertEqual(registered_tables, expected_tables)

    def test_all_expected_tables_created(self):
        """Verify that all 12 tables exist in SQLite database."""
        inspector = inspect(self.engine)
        created_tables = set(inspector.get_table_names())
        expected_tables = {
            "policies",
            "policy_configurations",
            "synthetic_personas",
            "scenario_configurations",
            "simulation_runs",
            "persona_run_states",
            "persona_interactions",
            "individual_outcomes",
            "aggregate_results",
            "application_lifecycle_records",
            "application_eligibility_evaluations",
            "application_audit_logs",
        }
        self.assertTrue(expected_tables.issubset(created_tables))

    # -------------------------------------------------------------------------
    # 2. Field-Level Schema Verification
    # -------------------------------------------------------------------------
    def test_field_level_schema_fidelity(self):
        """Verify column structure and primary keys on key tables."""
        inspector = inspect(self.engine)

        # Check policies table
        policy_cols = {col["name"]: col for col in inspector.get_columns("policies")}
        self.assertIn("id", policy_cols)
        self.assertIn("scheme_code", policy_cols)
        self.assertFalse(policy_cols["scheme_code"]["nullable"])
        self.assertTrue(policy_cols["official_portal_url"]["nullable"])

        # Check application_lifecycle_records table
        app_cols = {col["name"]: col for col in inspector.get_columns("application_lifecycle_records")}
        self.assertIn("initial_eligibility_snapshot", app_cols)
        self.assertFalse(app_cols["initial_eligibility_snapshot"]["nullable"])
        self.assertIn("latest_verified_eligibility_status", app_cols)
        self.assertTrue(app_cols["latest_verified_eligibility_status"]["nullable"])
        self.assertIn("approved_fee_relief_inr", app_cols)
        self.assertIn("disbursed_amount_inr", app_cols)

    # -------------------------------------------------------------------------
    # 3. Foreign-Key Enforcement
    # -------------------------------------------------------------------------
    def test_foreign_key_enforcement(self):
        """Verify that inserting a record with a non-existent foreign key raises IntegrityError."""
        invalid_config = PolicyConfigurationDB(
            policy_id=99999,  # Non-existent policy
            config_version="v2026.1",
            policy_source_reference="GR-TEST-001"
        )
        self.session.add(invalid_config)
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

    # -------------------------------------------------------------------------
    # 4. Unique Constraints
    # -------------------------------------------------------------------------
    def test_unique_constraints(self):
        """Verify that duplicate unique keys raise IntegrityError."""
        policy1 = PolicyDB(
            scheme_code="UNIQUE-TEST-01",
            scheme_name="Test Scheme",
            department="Higher Education",
            target_beneficiary="College Students"
        )
        self.session.add(policy1)
        self.session.commit()

        # Duplicate scheme_code
        policy2 = PolicyDB(
            scheme_code="UNIQUE-TEST-01",
            scheme_name="Duplicate Scheme",
            department="Higher Education",
            target_beneficiary="College Students"
        )
        self.session.add(policy2)
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

        # Duplicate (policy_id, config_version)
        config1 = PolicyConfigurationDB(
            policy_id=policy1.id,
            config_version="v1.0",
            policy_source_reference="GR-01"
        )
        self.session.add(config1)
        self.session.commit()

        config2 = PolicyConfigurationDB(
            policy_id=policy1.id,
            config_version="v1.0",
            policy_source_reference="GR-02"
        )
        self.session.add(config2)
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

    # -------------------------------------------------------------------------
    # 5. Bi-directional Relationship Navigation
    # -------------------------------------------------------------------------
    def test_relationship_bidirectional_loading(self):
        """Verify parent <-> child relationship navigation."""
        policy = PolicyDB(
            scheme_code="REL-TEST-01",
            scheme_name="Relationship Test Policy",
            department="Social Welfare",
            target_beneficiary="Students"
        )
        config = PolicyConfigurationDB(
            policy=policy,
            config_version="v1.0-rel",
            policy_source_reference="GR-REL-01",
            max_income_limit=800000.0
        )
        self.session.add(policy)
        self.session.commit()

        # Query fresh from DB
        fresh_policy = self.session.get(PolicyDB, policy.id)
        self.assertIsNotNone(fresh_policy)
        self.assertEqual(len(fresh_policy.configurations), 1)
        self.assertEqual(fresh_policy.configurations[0].config_version, "v1.0-rel")
        self.assertEqual(fresh_policy.configurations[0].policy.scheme_code, "REL-TEST-01")

    # -------------------------------------------------------------------------
    # 6. Deletion Restrictions: ON DELETE RESTRICT Enforcement
    # -------------------------------------------------------------------------
    def test_delete_restriction_for_application_history(self):
        """Verify that deleting an application with audit logs or evaluations fails with IntegrityError."""
        # 1. Create policy and config
        policy = PolicyDB(
            scheme_code="DEL-TEST-01",
            scheme_name="Delete Test Policy",
            department="Higher Education",
            target_beneficiary="Students"
        )
        config = PolicyConfigurationDB(
            policy=policy,
            config_version="v1.0-del",
            policy_source_reference="GR-DEL-01"
        )
        # 2. Create synthetic persona
        persona = SyntheticPersonaDB(
            persona_id="DEL-STU-001",
            name="Rahul Sharma",
            gender="Male",
            age=19,
            district="Dhule",
            taluka="Dhule",
            is_maharashtra_domicile=True,
            caste_category="General-EBC",
            family_income=350000.0,
            first_generation_learner=True,
            parental_education_level="Secondary",
            course_name="B.Tech Computer Engineering",
            course_level="Undergraduate",
            is_professional_course=True,
            institution_type="Government",
            admission_mode="CAP",
            annual_tuition_fee=85000.0,
            attendance_percentage=82.0,
            previous_year_passed=True,
            previous_year_percentage=75.0,
            academic_gap_years=0,
            family_beneficiaries_count=0,
            has_other_scholarship=False,
            digital_literacy=0.7,
            initial_awareness=0.5,
            document_readiness=0.6,
            financial_urgency=0.8,
            peer_network_support=0.6,
            institutional_trust=0.7,
            personality_traits_json={"patience": 0.6, "diligence": 0.7}
        )
        self.session.add_all([policy, config, persona])
        self.session.commit()

        # 3. Create application
        now_utc = datetime.now(timezone.utc)
        app = ApplicationRecordDB(
            application_number="MHD-2026-DEL-0001",
            persona_id=persona.persona_id,
            policy_id=policy.id,
            evaluation_policy_config_id=config.id,
            current_status=ApplicationLifecycleStatus.DRAFT.value,
            initial_eligibility_snapshot=True,
            evaluated_at=now_utc,
            claimed_fee_relief_inr=42500.0
        )
        self.session.add(app)
        self.session.commit()

        # 4. Attach an audit log
        audit = ApplicationAuditLogDB(
            application_id=app.id,
            from_status=ApplicationLifecycleStatus.DRAFT.value,
            to_status=ApplicationLifecycleStatus.SUBMITTED.value,
            reason_or_remarks="Student submitted documents",
            performed_by=AuditActor.STUDENT.value,
            timestamp=now_utc
        )
        self.session.add(audit)
        self.session.commit()

        # 5. Attempt to delete application with audit log -> MUST RAISE IntegrityError
        app_to_delete = self.session.get(ApplicationRecordDB, app.id)
        self.session.delete(app_to_delete)
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

    def test_delete_restriction_for_policy_configurations(self):
        """Verify that deleting a policy with configurations fails with IntegrityError."""
        policy = PolicyDB(
            scheme_code="POL-RESTRICT-01",
            scheme_name="Policy Restrict Test",
            department="Higher Education",
            target_beneficiary="Students"
        )
        config = PolicyConfigurationDB(
            policy=policy,
            config_version="v1.0-pol-del",
            policy_source_reference="GR-POL-01"
        )
        self.session.add_all([policy, config])
        self.session.commit()

        policy_to_del = self.session.get(PolicyDB, policy.id)
        self.session.delete(policy_to_del)
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

    # -------------------------------------------------------------------------
    # 7. JSON Serialization & Retrieval
    # -------------------------------------------------------------------------
    def test_json_serialization_and_retrieval(self):
        """Verify round-trip storage and retrieval of Python dict and list in JSON columns."""
        traits_data = {
            "patience": 0.85,
            "diligence": 0.90,
            "risk_aversion": 0.40,
            "self_advocacy": 0.75,
            "tags": ["diligent", "first-gen"]
        }
        persona = SyntheticPersonaDB(
            persona_id="JSON-STU-001",
            name="Snehal Patil",
            gender="Female",
            age=20,
            district="Dhule",
            taluka="Shirpur",
            is_maharashtra_domicile=True,
            caste_category="OBC",
            family_income=250000.0,
            first_generation_learner=False,
            parental_education_level="Graduate",
            course_name="B.Sc Agriculture",
            course_level="Undergraduate",
            is_professional_course=False,
            institution_type="Government-Aided",
            admission_mode="General-Merit",
            annual_tuition_fee=30000.0,
            attendance_percentage=88.0,
            previous_year_passed=True,
            previous_year_percentage=81.0,
            academic_gap_years=0,
            family_beneficiaries_count=1,
            has_other_scholarship=False,
            digital_literacy=0.8,
            initial_awareness=0.6,
            document_readiness=0.9,
            financial_urgency=0.5,
            peer_network_support=0.7,
            institutional_trust=0.8,
            personality_traits_json=traits_data
        )
        self.session.add(persona)
        self.session.commit()

        # Fresh retrieval
        retrieved = self.session.get(SyntheticPersonaDB, "JSON-STU-001")
        self.assertIsNotNone(retrieved)
        self.assertIsInstance(retrieved.personality_traits_json, dict)
        self.assertEqual(retrieved.personality_traits_json["patience"], 0.85)
        self.assertEqual(retrieved.personality_traits_json["tags"], ["diligent", "first-gen"])

    # -------------------------------------------------------------------------
    # 8. UTC Timestamp Round-Trip
    # -------------------------------------------------------------------------
    def test_utc_timestamp_round_trip(self):
        """Verify that storing UTC datetimes preserves tzinfo == timezone.utc and temporal equality."""
        original_now = datetime.now(timezone.utc)
        policy = PolicyDB(
            scheme_code="TIME-TEST-01",
            scheme_name="Time Test Policy",
            department="Higher Education",
            target_beneficiary="Students",
            created_at=original_now
        )
        self.session.add(policy)
        self.session.commit()

        retrieved = self.session.get(PolicyDB, policy.id)
        self.assertIsNotNone(retrieved)
        self.assertIsNotNone(retrieved.created_at.tzinfo)
        self.assertEqual(retrieved.created_at.tzinfo, timezone.utc)
        self.assertEqual(retrieved.created_at, original_now)

    # -------------------------------------------------------------------------
    # 9. Invalid Status/Enum CheckConstraints
    # -------------------------------------------------------------------------
    def test_invalid_enum_status_check_constraints(self):
        """Verify that inserting unauthorized strings for enum/status fields raises IntegrityError."""
        # 1. Invalid ApplicationLifecycleStatus
        with self.assertRaises(IntegrityError):
            invalid_app = ApplicationRecordDB(
                application_number="MHD-ERR-001",
                persona_id="NON_EXISTENT",
                policy_id=1,
                evaluation_policy_config_id=1,
                current_status="INSTANTLY_APPROVED",  # Invalid status
                initial_eligibility_snapshot=True,
                evaluated_at=datetime.now(timezone.utc),
                claimed_fee_relief_inr=50000.0
            )
            self.session.add(invalid_app)
            self.session.commit()
        self.session.rollback()

        # 2. Invalid SimulationRunStatus
        with self.assertRaises(IntegrityError):
            invalid_run = SimulationRunDB(
                run_id="run-err-001",
                policy_id=1,
                policy_config_id=1,
                population_config_name="test-pop",
                population_data_version="v1",
                software_version="commit-1",
                prompt_version="prompt-1",
                district="Dhule",
                population_size=10,
                random_seed=42,
                simulation_steps=2,
                llm_provider="Offline-Stub",
                model_version="stub-v1",
                run_status="PAUSED"  # Invalid status
            )
            self.session.add(invalid_run)
            self.session.commit()
        self.session.rollback()

        # 3. Invalid EvaluationActor
        with self.assertRaises(IntegrityError):
            invalid_eval = ApplicationEligibilityEvaluationDB(
                application_id=1,
                evaluation_stage=ApplicationEvaluationStage.INITIAL_ASSESSMENT.value,
                is_eligible=True,
                policy_config_id=1,
                evaluated_by="THIRD_PARTY_BOT"  # Invalid actor
            )
            self.session.add(invalid_eval)
            self.session.commit()
        self.session.rollback()

    # -------------------------------------------------------------------------
    # 10. Required versus Nullable Columns
    # -------------------------------------------------------------------------
    def test_required_versus_nullable_columns(self):
        """Verify that omitting required non-null fields raises IntegrityError, while nullable fields accept None."""
        # Missing required 'name' on SyntheticPersonaDB
        with self.assertRaises(IntegrityError):
            persona_no_name = SyntheticPersonaDB(
                persona_id="NO-NAME-001",
                gender="Male",
                age=21,
                district="Dhule",
                taluka="Dhule",
                is_maharashtra_domicile=True,
                caste_category="General-EBC",
                family_income=200000.0,
                first_generation_learner=True,
                parental_education_level="None",
                course_name="B.A.",
                course_level="Undergraduate",
                is_professional_course=False,
                institution_type="Government",
                admission_mode="CAP",
                annual_tuition_fee=5000.0,
                attendance_percentage=75.0,
                previous_year_passed=True,
                previous_year_percentage=60.0,
                academic_gap_years=0,
                family_beneficiaries_count=0,
                has_other_scholarship=False,
                digital_literacy=0.5,
                initial_awareness=0.5,
                document_readiness=0.5,
                financial_urgency=0.5,
                peer_network_support=0.5,
                institutional_trust=0.5,
                personality_traits_json={}
            )
            self.session.add(persona_no_name)
            self.session.commit()
        self.session.rollback()


if __name__ == "__main__":
    unittest.main()
