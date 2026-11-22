"""
Simulation Persistence Adapter: Bridges in-memory simulation entities,
behavioral progression states, social interactions, and macro outcomes with
the SQLAlchemy 2.x relational persistence schema (backend/db_models.py).

Architectural Rules:
1. Transaction Ownership: The adapter NEVER calls session.commit().
   All operations use session.flush() so the caller (backend service or test runner)
   retains full transactional authority.
2. Zero Rebuilding: Reuses existing ORM models from backend.db_models.
3. Schema Fidelity: Maps exact field names, constraints, and JSON fields
   defined by Diya's database models.
"""

import json
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db_models import (
    PolicyDB,
    PolicyConfigurationDB,
    SimulationRunDB,
    SyntheticPersonaDB,
    PersonaRunStateDB,
    PersonaInteractionDB,
    IndividualOutcomeDB,
    AggregateResultDB,
    SimulationRunStatus,
    ConfidenceLevel,
)
from simulation.persona import StudentPersona
from simulation.engine import SimulationStepOutput, CohortSimulationResult
from simulation.policy_rules import RajarshiShahuPolicyEngine


class SimulationPersistenceAdapter:
    """
    Adapter providing transactional persistence operations for the simulation engine.
    Does not commit transactions; leaves transaction demarcation to the service layer.
    """

    @classmethod
    def ensure_policy_and_config(
        cls,
        session: Session,
        scheme_code: str = "RCSMS-EBC"
    ) -> Tuple[PolicyDB, PolicyConfigurationDB]:
        """
        Retrieves or bootstraps the reference policy and versioned configuration.
        Flushes to guarantee primary keys without committing.
        """
        stmt_policy = select(PolicyDB).where(PolicyDB.scheme_code == scheme_code)
        policy = session.scalars(stmt_policy).first()

        if policy is None:
            policy = PolicyDB(
                scheme_code=scheme_code,
                scheme_name=RajarshiShahuPolicyEngine.SCHEME_NAME,
                department="Higher & Technical Education Department",
                target_beneficiary="Economically Backward Class (EBC) College Students",
                official_portal_url="https://mahadbt.maharashtra.gov.in",
                description="Statutory fee reimbursement scheme for eligible EBC students in Maharashtra higher education.",
                is_active=True,
                created_at=datetime.now(timezone.utc),
            )
            session.add(policy)
            session.flush()

        stmt_config = (
            select(PolicyConfigurationDB)
            .where(PolicyConfigurationDB.policy_id == policy.id)
            .order_by(PolicyConfigurationDB.id.desc())
        )
        config = session.scalars(stmt_config).first()

        if config is None:
            config = PolicyConfigurationDB(
                policy_id=policy.id,
                config_version="v1.0-provisional",
                policy_source_reference="Provisional PolicyEngine Reference (GR EBC-2016/C.R.221/Edu-1 Unverified)",
                max_income_limit=RajarshiShahuPolicyEngine.MAX_INCOME_LIMIT,
                min_attendance_pct=RajarshiShahuPolicyEngine.MIN_ATTENDANCE_PERCENT,
                baseline_relief_rate=RajarshiShahuPolicyEngine.DEFAULT_POC_ASSUMED_REIMBURSEMENT_RATE,
                max_family_beneficiaries=RajarshiShahuPolicyEngine.MAX_FAMILY_BENEFICIARIES,
                allows_concurrent_scholarship=False,
                requires_cap_admission=True,
                is_verified_statutory_rule=False,
                notes=(
                    "Provisional simulation configuration derived from PolicyEngine statutory caps "
                    f"(Income <= INR {RajarshiShahuPolicyEngine.MAX_INCOME_LIMIT:,.0f}, "
                    f"Min Attendance >= {RajarshiShahuPolicyEngine.MIN_ATTENDANCE_PERCENT:.0f}%) "
                    "alongside configurable PoC benefit assumptions "
                    f"(Baseline fee relief rate {RajarshiShahuPolicyEngine.DEFAULT_POC_ASSUMED_REIMBURSEMENT_RATE * 100:.0f}%, "
                    f"Max family beneficiaries {RajarshiShahuPolicyEngine.MAX_FAMILY_BENEFICIARIES}). "
                    "Formal statutory rule verification and official GR cross-reference pending sign-off "
                    "from Policy Engine module owner (Shravani)."
                ),
                created_at=datetime.now(timezone.utc),
            )
            session.add(config)
            session.flush()

        return policy, config

    @classmethod
    def sync_personas(
        cls,
        session: Session,
        personas: List[StudentPersona]
    ) -> List[SyntheticPersonaDB]:
        """
        Upserts/registers synthetic citizen personas into the database catalog.
        """
        db_personas: List[SyntheticPersonaDB] = []
        for p in personas:
            existing = session.get(SyntheticPersonaDB, p.persona_id)
            if existing is not None:
                db_personas.append(existing)
                continue

            inst_val = p.institution_type.value if hasattr(p.institution_type, "value") else str(p.institution_type)
            adm_val = p.admission_mode.value if hasattr(p.admission_mode, "value") else str(p.admission_mode)
            taluka_val = getattr(p, "taluka", None) or p.district
            personality_dict = asdict(p.personality) if hasattr(p, "personality") else {}

            db_persona = SyntheticPersonaDB(
                persona_id=p.persona_id,
                name=p.name,
                gender=p.gender,
                age=p.age,
                district=p.district,
                taluka=taluka_val,
                is_maharashtra_domicile=p.is_maharashtra_domicile,
                caste_category=p.caste_category,
                family_income=p.family_income,
                first_generation_learner=p.first_generation_learner,
                parental_education_level=p.parental_education_level,
                course_name=p.course_name,
                course_level=getattr(p, "course_level", "Undergraduate"),
                is_professional_course=p.is_professional_course,
                institution_type=inst_val,
                admission_mode=adm_val,
                annual_tuition_fee=p.annual_tuition_fee,
                attendance_percentage=p.attendance_percentage,
                previous_year_passed=p.previous_year_passed,
                previous_year_percentage=getattr(p, "previous_year_percentage", 65.0),
                academic_gap_years=getattr(p, "academic_gap_years", 0),
                family_beneficiaries_count=getattr(p, "family_beneficiaries_count", 1),
                has_other_scholarship=getattr(p, "has_other_scholarship", False),
                digital_literacy=p.digital_literacy,
                initial_awareness=p.initial_awareness,
                document_readiness=p.document_readiness,
                financial_urgency=getattr(p, "financial_urgency", 0.5),
                peer_network_support=getattr(p, "peer_network_support", 0.5),
                institutional_trust=p.institutional_trust,
                personality_traits_json=personality_dict,
                created_at=datetime.now(timezone.utc),
            )
            session.add(db_persona)
            db_personas.append(db_persona)

        session.flush()
        return db_personas

    @classmethod
    def start_simulation_run(
        cls,
        session: Session,
        run_id: str,
        policy_id: int,
        policy_config_id: int,
        district: str,
        population_size: int,
        simulation_steps: int,
        seed: Optional[int] = 42,
        llm_provider: str = "Deterministic Rule-Grounded Stub (Offline)",
        model_version: str = "v1.0-stub",
        scenario_config_id: Optional[int] = None,
        population_config_name: str = "Dhule-Census-2010-11",
        population_data_version: str = "v1.0",
        software_version: str = "1.0.0",
        prompt_version: str = "v1.0-grounded",
        status_message: Optional[str] = None
    ) -> SimulationRunDB:
        """
        Creates a new audit record for a simulation execution batch in RUNNING status.
        """
        run = SimulationRunDB(
            run_id=run_id,
            policy_id=policy_id,
            policy_config_id=policy_config_id,
            scenario_config_id=scenario_config_id,
            population_config_name=population_config_name,
            population_data_version=population_data_version,
            software_version=software_version,
            prompt_version=prompt_version,
            district=district,
            population_size=population_size,
            random_seed=seed if seed is not None else 42,
            simulation_steps=simulation_steps,
            llm_provider=llm_provider,
            model_version=model_version,
            execution_timestamp=datetime.now(timezone.utc),
            completion_timestamp=None,
            run_status=SimulationRunStatus.RUNNING.value,
            status_message=status_message or "Simulation run initiated",
        )
        session.add(run)
        session.flush()
        return run

    @classmethod
    def record_step_snapshot(
        cls,
        session: Session,
        run_id: str,
        step_number: int,
        personas: List[StudentPersona],
        step_outputs: List[SimulationStepOutput],
        interactions: List[Dict[str, Any]],
        step_cohort: CohortSimulationResult
    ) -> None:
        """
        Persists temporal persona states, interaction logs, and step aggregates.
        """
        output_map = {out.persona_id: out for out in step_outputs}

        # 1. Temporal persona states
        for p in personas:
            out = output_map.get(p.persona_id)
            if out is None:
                continue

            state_record = PersonaRunStateDB(
                run_id=run_id,
                persona_id=p.persona_id,
                step_number=step_number,
                awareness_score=out.awareness_score,
                trust_score=p.institutional_trust,
                document_readiness_score=p.document_readiness,
                peer_network_support=getattr(p, "peer_network_support", 0.5),
                application_probability=out.application_probability,
                completion_probability=out.completion_probability,
                expected_uptake_probability=out.expected_uptake_probability,
                simulation_state=out.final_simulation_state,
                recorded_at=datetime.now(timezone.utc),
            )
            session.add(state_record)

        # 2. Peer interactions
        for inter in interactions:
            interaction_record = PersonaInteractionDB(
                run_id=run_id,
                step_number=step_number,
                sender_id=inter.get("sender_id", ""),
                receiver_id=inter.get("receiver_id", ""),
                interaction_topic=inter.get("interaction_topic", "SCHEME_AWARENESS"),
                sender_message=inter.get("sender_message", ""),
                receiver_response=inter.get("receiver_response", ""),
                state_changed=bool(inter.get("state_changed", False)),
                state_changes_json=inter.get("state_changes"),
                occurred_at=datetime.now(timezone.utc),
            )
            session.add(interaction_record)

        # 3. Macro step aggregate
        breakdowns = {
            "gender": step_cohort.breakdown_by_gender,
            "institution_type": step_cohort.breakdown_by_institution_type,
            "caste_category": step_cohort.breakdown_by_caste_category,
            "ineligibility_reasons": step_cohort.ineligibility_reasons_summary,
            "state_distribution": step_cohort.state_distribution,
        }

        agg_step = AggregateResultDB(
            run_id=run_id,
            step_number=step_number,
            total_personas=step_cohort.total_personas,
            eligible_count=step_cohort.eligible_count,
            ineligible_count=step_cohort.ineligible_count,
            eligibility_rate=step_cohort.eligibility_rate,
            mean_awareness=step_cohort.average_awareness_score,
            mean_perceived_benefit=step_cohort.average_perceived_benefit_score,
            mean_application_probability=step_cohort.average_application_probability,
            expected_uptake_probability=step_cohort.average_expected_uptake_probability,
            realized_uptake_count=step_cohort.benefit_received_count,
            realized_uptake_rate=step_cohort.uptake_rate,
            total_fee_relief_inr=step_cohort.total_estimated_fee_relief_inr,
            avg_relief_per_eligible_inr=step_cohort.average_fee_relief_per_eligible_inr,
            categorical_breakdowns_json=breakdowns,
        )
        session.add(agg_step)
        session.flush()

    @classmethod
    def record_final_outcomes(
        cls,
        session: Session,
        run_id: str,
        individual_results: List[SimulationStepOutput]
    ) -> None:
        """
        Persists final individual realized outcomes, reasoning narrative, and barriers.
        """
        for out in individual_results:
            # Map confidence level string safely to allowed enum values
            conf_val = out.confidence_level
            if conf_val not in ("High", "Moderate", "Low"):
                conf_val = "Moderate"

            outcome = IndividualOutcomeDB(
                run_id=run_id,
                persona_id=out.persona_id,
                is_statutorily_eligible=out.is_eligible,
                estimated_fee_relief_inr=out.estimated_fee_relief_inr,
                statutory_failure_reasons_json=out.statutory_failure_reasons,
                final_simulation_state=out.final_simulation_state,
                attempted_application=out.attempted_application,
                completed_application=out.completed_application,
                benefit_received=out.benefit_received,
                inner_monologue=out.inner_monologue or "",
                stated_intention=out.stated_intention or "Evaluating options.",
                perceived_barriers_json=out.perceived_barriers,
                chosen_action=out.chosen_action or "EVALUATE",
                confidence_level=conf_val,
            )
            session.add(outcome)

        session.flush()

    @classmethod
    def complete_simulation_run(
        cls,
        session: Session,
        run_id: str,
        final_cohort: CohortSimulationResult,
        status: SimulationRunStatus = SimulationRunStatus.COMPLETED,
        status_message: Optional[str] = None
    ) -> SimulationRunDB:
        """
        Records the final cohort summary (step_number=0) and marks the run COMPLETED.
        """
        run = session.get(SimulationRunDB, run_id)
        if run is not None:
            run.run_status = status.value if hasattr(status, "value") else str(status)
            run.completion_timestamp = datetime.now(timezone.utc)
            run.status_message = status_message or "Simulation run completed successfully"

        # Step 0 represents the final cumulative cohort result
        breakdowns = {
            "gender": final_cohort.breakdown_by_gender,
            "institution_type": final_cohort.breakdown_by_institution_type,
            "caste_category": final_cohort.breakdown_by_caste_category,
            "ineligibility_reasons": final_cohort.ineligibility_reasons_summary,
            "state_distribution": final_cohort.state_distribution,
        }

        agg_final = AggregateResultDB(
            run_id=run_id,
            step_number=0,
            total_personas=final_cohort.total_personas,
            eligible_count=final_cohort.eligible_count,
            ineligible_count=final_cohort.ineligible_count,
            eligibility_rate=final_cohort.eligibility_rate,
            mean_awareness=final_cohort.average_awareness_score,
            mean_perceived_benefit=final_cohort.average_perceived_benefit_score,
            mean_application_probability=final_cohort.average_application_probability,
            expected_uptake_probability=final_cohort.average_expected_uptake_probability,
            realized_uptake_count=final_cohort.benefit_received_count,
            realized_uptake_rate=final_cohort.uptake_rate,
            total_fee_relief_inr=final_cohort.total_estimated_fee_relief_inr,
            avg_relief_per_eligible_inr=final_cohort.average_fee_relief_per_eligible_inr,
            categorical_breakdowns_json=breakdowns,
        )
        session.add(agg_final)
        session.flush()
        return run
