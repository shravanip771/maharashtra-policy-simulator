"""
Simulation Service Layer: Orchestrates the execution of multi-step cohort simulations
and packages the results into the frontend Data Contract.
"""

import os
import uuid
from typing import Dict, List, Any, Optional
try:
    from sqlalchemy.orm import Session
except ImportError:
    Session = Any  # type: ignore

from data.dhule_adapter import DhuleEducationDatasetAdapter
from simulation.persona_generator import SyntheticPersonaGenerator
from simulation.district_config import DISTRICT_REGISTRY
from simulation.agent import StubLLMProvider, GeminiLLMProvider
from simulation.engine import SimulationEngine, MultiStepSimulationResult
from simulation.policy_rules import RajarshiShahuPolicyEngine

from backend.models import (
    SimulationRequest,
    SimulationResponse,
    SimulationMetadata,
    ProvenanceBreakdown,
    AggregateMetrics,
    StepMetric,
    NetworkTopology,
    PersonaOutput,
    InteractionRecordDTO,
    DistrictSummaryDTO,
    StatewideSimulationRequest,
    StatewideSimulationResponse
)


class SimulationService:
    """Service orchestrating persona generation, engine simulation, and DTO transformation."""

    @classmethod
    def execute_simulation(
        cls,
        req: SimulationRequest,
        session: Optional[Session] = None,
        persist: bool = False
    ) -> SimulationResponse:
        """
        Executes a multi-step simulation run. If persist is True and no session is provided,
        manages a database transaction boundary using get_db_session().
        If session is provided, participates in caller's session without committing.
        """
        if persist and session is None:
            from backend.database import get_db_session
            with get_db_session() as db_session:
                return cls._execute_simulation_impl(req, session=db_session, persist=True)

        return cls._execute_simulation_impl(req, session=session, persist=persist)

    @classmethod
    def _execute_simulation_impl(
        cls,
        req: SimulationRequest,
        session: Optional[Session] = None,
        persist: bool = False
    ) -> SimulationResponse:
        # 1. Resolve LLM Provider safely (offline stub by default)
        use_gemini = req.use_gemini or (os.getenv("USE_GEMINI", "0").strip() == "1")
        gemini_key = os.getenv("GEMINI_API_KEY", "").strip()

        if use_gemini and gemini_key:
            model_name = req.gemini_model or os.getenv("GEMINI_MODEL", GeminiLLMProvider.DEFAULT_MODEL)
            provider = GeminiLLMProvider(model_name=model_name, fallback_to_stub=True)
            provider_label = f"Google Gemini API ({model_name})"
        else:
            provider = StubLLMProvider()
            provider_label = "Deterministic Rule-Grounded Stub (Offline)"

        # 2. Generate grounded synthetic cohort
        if req.district.lower() == "dhule":
            adapter = DhuleEducationDatasetAdapter()
            config = adapter.create_population_config()
            generator = SyntheticPersonaGenerator(config=config, seed=req.seed, district="Dhule")
            cohort = generator.generate_cohort(count=req.cohort_size, seed=req.seed)
        else:
            generator = SyntheticPersonaGenerator.for_district(req.district, seed=req.seed)
            cohort = generator.generate_cohort(count=req.cohort_size, seed=req.seed)

        # 3. Handle Persistence Preparation if requested
        run_id: Optional[str] = None
        policy_id: Optional[int] = None
        policy_config_id: Optional[int] = None

        if persist and session is not None:
            from backend.simulation_persistence import SimulationPersistenceAdapter
            run_id = str(uuid.uuid4())
            policy, p_config = SimulationPersistenceAdapter.ensure_policy_and_config(session=session)
            policy_id = policy.id
            policy_config_id = p_config.id

            # Sync synthetic personas into catalog
            SimulationPersistenceAdapter.sync_personas(session=session, personas=cohort)

            # Record simulation run initiation
            SimulationPersistenceAdapter.start_simulation_run(
                session=session,
                run_id=run_id,
                policy_id=policy_id,
                policy_config_id=policy_config_id,
                district=req.district,
                population_size=req.cohort_size,
                simulation_steps=req.simulation_steps,
                seed=req.seed,
                llm_provider=provider_label,
            )

        # 4. Execute multi-step engine run
        try:
            engine = SimulationEngine(llm_provider=provider)
            raw_result: MultiStepSimulationResult = engine.run_multistep_cohort(
                personas=cohort,
                total_steps=req.simulation_steps,
                cohort_name=f"{req.district}-{req.cohort_size}-Persona-Cohort",
                seed=req.seed,
                enable_social_interaction=True,
                max_connections_per_persona=2,
                session=session,
                run_id=run_id,
                policy_id=policy_id,
                policy_config_id=policy_config_id,
                policy_mode=getattr(req, "policy_mode", None),
                assumed_reimbursement_rate=getattr(req, "assumed_reimbursement_rate", None),
            )

            # 5. Finalize Simulation Run in Persistence Adapter
            if persist and session is not None and run_id is not None:
                from backend.simulation_persistence import SimulationPersistenceAdapter
                SimulationPersistenceAdapter.complete_simulation_run(
                    session=session,
                    run_id=run_id,
                    final_cohort=raw_result.final_cohort_result,
                )
        except Exception as e:
            if persist and session is not None and run_id is not None:
                from backend.db_models import SimulationRunDB, SimulationRunStatus
                run_rec = session.get(SimulationRunDB, run_id)
                if run_rec is not None:
                    run_rec.run_status = SimulationRunStatus.FAILED.value
                    run_rec.status_message = f"Execution failed: {str(e)}"
                    session.flush()
            raise

        # 6. Map Metadata & Provenance
        metadata = SimulationMetadata(
            scheme_name=RajarshiShahuPolicyEngine.SCHEME_NAME,
            scheme_code="RCSMS-EBC",
            district=req.district,
            cohort_size=req.cohort_size,
            simulation_steps=req.simulation_steps,
            seed=req.seed,
            llm_provider=provider_label,
            is_synthetic_poc=True,
            assumed_reimbursement_rate=0.50,
            data_disclaimer=(
                "Ground-truth demographics derived from official 2010-11 Dhule Educational Census table. "
                "Behavioral attributes, network ties, and dialogue are synthetic simulation models."
            ),
            resolved_policy_mode=raw_result.policy_mode,
            is_counterfactual=raw_result.is_counterfactual,
            policy_version="2024.1-provisional"
        )

        provenance = ProvenanceBreakdown(
            grounded_reference_fields=[
                "district", "taluka", "institution_type", "gender_enrolment_ratio", "course_stream_distribution"
            ],
            derived_fields=[
                "name", "age", "annual_tuition_fee", "academic_gap_years", "first_generation_learner"
            ],
            synthetic_behavioral_priors=[
                "initial_awareness", "digital_literacy", "document_readiness", "institutional_trust", "personality_traits"
            ],
            poc_assumptions=[
                "50% tuition fee reimbursement baseline estimate",
                "Synthetic social graph degree bound k <= 2"
            ]
        )

        # 5. Map Final Step Aggregate Metrics
        final_cohort_res = raw_result.step_cohort_results[-1]
        agg_metrics = AggregateMetrics(
            total_personas=final_cohort_res.total_personas,
            eligible_count=final_cohort_res.eligible_count,
            ineligible_count=final_cohort_res.ineligible_count,
            eligibility_rate=round(final_cohort_res.eligibility_rate, 4),
            mean_awareness=round(final_cohort_res.average_awareness_score, 4),
            mean_perceived_benefit=round(final_cohort_res.average_perceived_benefit_score, 4),
            mean_application_probability=round(final_cohort_res.average_application_probability, 4),
            expected_uptake_probability=round(final_cohort_res.average_expected_uptake_probability, 4),
            realized_uptake_count=final_cohort_res.benefit_received_count,
            realized_uptake_rate=round(final_cohort_res.uptake_rate, 4),
            total_estimated_fee_relief_inr=final_cohort_res.total_estimated_fee_relief_inr,
            average_fee_relief_per_eligible_inr=final_cohort_res.average_fee_relief_per_eligible_inr,
            total_tuition_fee_relief_inr=getattr(final_cohort_res, "total_tuition_fee_relief_inr", 0.0),
            total_exam_fee_relief_inr=getattr(final_cohort_res, "total_exam_fee_relief_inr", 0.0),
            cohort_effective_relief_rate=getattr(final_cohort_res, "cohort_effective_relief_rate", 0.0)
        )

        # 6. Map Step Metrics
        step_metrics: List[StepMetric] = []
        for s_idx, s_res in enumerate(raw_result.step_cohort_results, start=1):
            interactions_in_step = raw_result.interactions_by_step.get(s_idx, [])
            step_metrics.append(
                StepMetric(
                    step_number=s_idx,
                    eligible_count=s_res.eligible_count,
                    mean_awareness=round(s_res.average_awareness_score, 4),
                    mean_perceived_benefit=round(s_res.average_perceived_benefit_score, 4),
                    mean_application_probability=round(s_res.average_application_probability, 4),
                    expected_uptake_probability=round(s_res.average_expected_uptake_probability, 4),
                    realized_uptake_count=s_res.benefit_received_count,
                    interaction_count=len(interactions_in_step)
                )
            )

        # 7. Map Network Topology
        net_summary = raw_result.network_summary
        network = NetworkTopology(
            total_nodes=net_summary.get("total_nodes", req.cohort_size),
            total_edges=net_summary.get("total_edges", 0),
            max_degree_limit=net_summary.get("max_degree_limit", 2),
            adjacency_list=net_summary.get("adjacency_list", {})
        )

        # 8. Map Persona List with final decision traces
        persona_name_map = {p.persona_id: p.name for p in cohort}
        personas_out: List[PersonaOutput] = []

        for p, step_out in zip(cohort, final_cohort_res.individual_results):
            ev = raw_result.state_evolution_summary.get(p.persona_id, {})
            personas_out.append(
                PersonaOutput(
                    persona_id=p.persona_id,
                    name=p.name,
                    gender=p.gender,
                    age=p.age,
                    district=p.district,
                    taluka=getattr(p, "taluka", p.district),
                    course_name=p.course_name,
                    is_professional_course=p.is_professional_course,
                    institution_type=p.institution_type.value,
                    admission_mode=p.admission_mode.value,
                    caste_category=p.caste_category,
                    family_income=p.family_income,
                    annual_tuition_fee=p.annual_tuition_fee,
                    attendance_percentage=p.attendance_percentage,
                    previous_year_passed=p.previous_year_passed,
                    first_generation_learner=p.first_generation_learner,
                    is_statutorily_eligible=step_out.is_eligible,
                    estimated_fee_relief_inr=step_out.estimated_fee_relief_inr,
                    statutory_failure_reasons=step_out.statutory_failure_reasons,
                    initial_awareness=ev.get("initial_awareness", p.initial_awareness),
                    final_awareness=ev.get("final_awareness", p.initial_awareness),
                    awareness_gain=ev.get("awareness_gain", 0.0),
                    initial_trust=ev.get("initial_trust", p.institutional_trust),
                    final_trust=ev.get("final_trust", p.institutional_trust),
                    digital_literacy=p.digital_literacy,
                    document_readiness=p.document_readiness,
                    application_probability=round(step_out.application_probability, 4),
                    completion_probability=round(step_out.completion_probability, 4),
                    final_state=step_out.final_simulation_state,
                    stated_intention=step_out.stated_intention,
                    major_barriers=step_out.perceived_barriers,
                    inner_monologue=step_out.inner_monologue,
                    reimbursement_rate=getattr(step_out, "reimbursement_percentage", 0.50),
                    tuition_fee_relief_inr=getattr(step_out, "tuition_fee_relief_inr", 0.0),
                    exam_fee_relief_inr=getattr(step_out, "exam_fee_relief_inr", 0.0),
                    policy_details={"policy_mode": getattr(step_out, "policy_mode", "statutory")}
                )
            )

        # 9. Map All Interactions Across Steps
        interactions_out: List[InteractionRecordDTO] = []
        for s_idx in range(1, req.simulation_steps + 1):
            raw_ints = raw_result.interactions_by_step.get(s_idx, [])
            for r in raw_ints:
                sender_id = r.get("sender_id", "")
                receiver_id = r.get("receiver_id", "")
                interactions_out.append(
                    InteractionRecordDTO(
                        simulation_step=s_idx,
                        sender_id=sender_id,
                        sender_name=persona_name_map.get(sender_id, sender_id),
                        receiver_id=receiver_id,
                        receiver_name=persona_name_map.get(receiver_id, receiver_id),
                        interaction_topic=r.get("interaction_topic", "SCHEME_AWARENESS"),
                        sender_message=r.get("sender_message", ""),
                        receiver_response=r.get("receiver_response", ""),
                        state_changed=r.get("state_changed", False),
                        state_changes=r.get("state_changes", {})
                    )
                )

        return SimulationResponse(
            metadata=metadata,
            provenance_breakdown=provenance,
            aggregate_metrics=agg_metrics,
            step_metrics=step_metrics,
            network_topology=network,
            personas=personas_out,
            interactions=interactions_out
        )

    @classmethod
    def execute_statewide_simulation(
        cls,
        req: StatewideSimulationRequest,
        session: Optional[Session] = None,
        persist: bool = False
    ) -> StatewideSimulationResponse:
        """
        Executes a statewide 1,000-persona multi-step simulation across all 36 Maharashtra districts.
        Aggregates outcomes, calculates per-district metrics, and samples deterministic featured personas.
        """
        use_gemini = req.use_gemini or (os.getenv("USE_GEMINI", "0").strip() == "1")
        gemini_key = os.getenv("GEMINI_API_KEY", "").strip()

        if use_gemini and gemini_key:
            model_name = os.getenv("GEMINI_MODEL", GeminiLLMProvider.DEFAULT_MODEL)
            provider = GeminiLLMProvider(model_name=model_name, fallback_to_stub=True)
            provider_label = f"Google Gemini API ({model_name})"
        else:
            provider = StubLLMProvider()
            provider_label = "Deterministic Rule-Grounded Stub (Offline)"

        # 1. Generate full statewide cohort of 1,000 personas
        cohort = SyntheticPersonaGenerator.generate_weighted_state_population(seed=req.seed)

        # 2. Execute multi-step engine run
        engine = SimulationEngine(llm_provider=provider)
        raw_result: MultiStepSimulationResult = engine.run_multistep_cohort(
            personas=cohort,
            total_steps=req.simulation_steps,
            cohort_name="Maharashtra-Statewide-1000-Cohort",
            seed=req.seed,
            enable_social_interaction=True,
            max_connections_per_persona=2,
            policy_mode=getattr(req, "policy_mode", "statutory") or "statutory",
            assumed_reimbursement_rate=getattr(req, "assumed_reimbursement_rate", None),
        )

        final_cohort_res = raw_result.final_cohort_result

        # 3. Compute per-district summaries from actual individual results
        district_summaries: Dict[str, DistrictSummaryDTO] = {}
        for d_key, prof in DISTRICT_REGISTRY.items():
            d_name = prof.district_name
            d_results = [r for r in final_cohort_res.individual_results if r.demographics_summary.get("district") == d_name]
            tot = len(d_results)
            el_count = sum(1 for r in d_results if r.is_eligible)
            inel_count = tot - el_count
            el_rate = round(el_count / tot, 4) if tot > 0 else 0.0
            mean_aw = round(sum(r.awareness_score for r in d_results) / tot, 4) if tot > 0 else 0.0
            mean_app = round(sum(r.application_probability for r in d_results) / tot, 4) if tot > 0 else 0.0
            exp_uptake = round(sum(r.expected_uptake_probability for r in d_results) / tot, 4) if tot > 0 else 0.0
            realized_cnt = sum(1 for r in d_results if r.benefit_received)
            realized_rate = round(realized_cnt / tot, 4) if tot > 0 else 0.0
            total_relief = round(sum(r.estimated_fee_relief_inr for r in d_results), 2)
            avg_relief = round(total_relief / el_count, 2) if el_count > 0 else 0.0

            district_summaries[d_name] = DistrictSummaryDTO(
                district_name=d_name,
                total_personas=tot,
                eligible_count=el_count,
                ineligible_count=inel_count,
                eligibility_rate=el_rate,
                mean_awareness=mean_aw,
                mean_application_probability=mean_app,
                expected_uptake_probability=exp_uptake,
                realized_uptake_count=realized_cnt,
                realized_uptake_rate=realized_rate,
                total_estimated_fee_relief_inr=total_relief,
                average_fee_relief_per_eligible_inr=avg_relief
            )

        # 4. Deterministically sample 10 featured personas across the 6 administrative divisions
        sentinel_districts = [
            "Dhule", "Mumbai City", "Pune", "Nagpur", "Chhatrapati Sambhajinagar",
            "Amravati", "Kolhapur", "Nashik", "Nanded", "Thane"
        ]
        featured_personas: List[PersonaOutput] = []
        for s_dist in sentinel_districts:
            matches = [
                (p, r) for p, r in zip(cohort, final_cohort_res.individual_results)
                if p.district == s_dist
            ]
            if matches:
                idx = (req.seed * 31) % len(matches)
                p_match, r_match = matches[idx]
                ev = raw_result.state_evolution_summary.get(p_match.persona_id, {})
                featured_personas.append(
                    PersonaOutput(
                        persona_id=p_match.persona_id,
                        name=p_match.name,
                        gender=p_match.gender,
                        age=p_match.age,
                        district=p_match.district,
                        taluka=getattr(p_match, "taluka", p_match.district),
                        course_name=p_match.course_name,
                        is_professional_course=p_match.is_professional_course,
                        institution_type=p_match.institution_type.value,
                        admission_mode=p_match.admission_mode.value,
                        caste_category=p_match.caste_category,
                        family_income=p_match.family_income,
                        annual_tuition_fee=p_match.annual_tuition_fee,
                        attendance_percentage=p_match.attendance_percentage,
                        previous_year_passed=p_match.previous_year_passed,
                        first_generation_learner=p_match.first_generation_learner,
                        is_statutorily_eligible=r_match.is_eligible,
                        estimated_fee_relief_inr=r_match.estimated_fee_relief_inr,
                        statutory_failure_reasons=r_match.statutory_failure_reasons,
                        initial_awareness=ev.get("initial_awareness", p_match.initial_awareness),
                        final_awareness=ev.get("final_awareness", p_match.initial_awareness),
                        awareness_gain=ev.get("awareness_gain", 0.0),
                        initial_trust=ev.get("initial_trust", p_match.institutional_trust),
                        final_trust=ev.get("final_trust", p_match.institutional_trust),
                        digital_literacy=p_match.digital_literacy,
                        document_readiness=p_match.document_readiness,
                        application_probability=round(r_match.application_probability, 4),
                        completion_probability=round(r_match.completion_probability, 4),
                        final_state=r_match.final_simulation_state,
                        stated_intention=r_match.stated_intention,
                        major_barriers=r_match.perceived_barriers,
                        inner_monologue=r_match.inner_monologue,
                        reimbursement_rate=getattr(r_match, "reimbursement_percentage", 0.50),
                        tuition_fee_relief_inr=getattr(r_match, "tuition_fee_relief_inr", 0.0),
                        exam_fee_relief_inr=getattr(r_match, "exam_fee_relief_inr", 0.0),
                        policy_details={"policy_mode": getattr(r_match, "policy_mode", "statutory")}
                    )
                )

        # 5. Filter interactions involving featured personas
        featured_ids = {p.persona_id for p in featured_personas}
        persona_name_map = {p.persona_id: p.name for p in cohort}
        interactions_out: List[InteractionRecordDTO] = []

        for s_idx in range(1, req.simulation_steps + 1):
            raw_ints = raw_result.interactions_by_step.get(s_idx, [])
            for r in raw_ints:
                sender_id = r.get("sender_id", "")
                receiver_id = r.get("receiver_id", "")
                if sender_id in featured_ids or receiver_id in featured_ids:
                    interactions_out.append(
                        InteractionRecordDTO(
                            simulation_step=s_idx,
                            sender_id=sender_id,
                            sender_name=persona_name_map.get(sender_id, sender_id),
                            receiver_id=receiver_id,
                            receiver_name=persona_name_map.get(receiver_id, receiver_id),
                            interaction_topic=r.get("interaction_topic", "SCHEME_AWARENESS"),
                            sender_message=r.get("sender_message", ""),
                            receiver_response=r.get("receiver_response", ""),
                            state_changed=r.get("state_changed", False),
                            state_changes=r.get("state_changes", {})
                        )
                    )

        if not interactions_out:
            for s_idx in range(1, req.simulation_steps + 1):
                raw_ints = raw_result.interactions_by_step.get(s_idx, [])
                for r in raw_ints[:10]:
                    sender_id = r.get("sender_id", "")
                    receiver_id = r.get("receiver_id", "")
                    interactions_out.append(
                        InteractionRecordDTO(
                            simulation_step=s_idx,
                            sender_id=sender_id,
                            sender_name=persona_name_map.get(sender_id, sender_id),
                            receiver_id=receiver_id,
                            receiver_name=persona_name_map.get(receiver_id, receiver_id),
                            interaction_topic=r.get("interaction_topic", "SCHEME_AWARENESS"),
                            sender_message=r.get("sender_message", ""),
                            receiver_response=r.get("receiver_response", ""),
                            state_changed=r.get("state_changed", False),
                            state_changes=r.get("state_changes", {})
                        )
                    )

        return StatewideSimulationResponse(
            is_statewide=True,
            aggregate_metrics={
                "total_personas": final_cohort_res.total_personas,
                "eligible_count": final_cohort_res.eligible_count,
                "ineligible_count": final_cohort_res.ineligible_count,
                "eligibility_rate": round(final_cohort_res.eligibility_rate, 4),
                "mean_awareness": round(final_cohort_res.average_awareness_score, 4),
                "mean_perceived_benefit": round(final_cohort_res.average_perceived_benefit_score, 4),
                "mean_application_probability": round(final_cohort_res.average_application_probability, 4),
                "expected_uptake_probability": round(final_cohort_res.average_expected_uptake_probability, 4),
                "realized_uptake_count": final_cohort_res.benefit_received_count,
                "realized_uptake_rate": round(final_cohort_res.uptake_rate, 4),
                "total_estimated_fee_relief_inr": final_cohort_res.total_estimated_fee_relief_inr,
                "average_fee_relief_per_eligible_inr": final_cohort_res.average_fee_relief_per_eligible_inr,
            },
            personas=featured_personas,
            district_summaries=district_summaries,
            interactions=interactions_out,
            metadata={
                "district": "Maharashtra",
                "cohort_size": 1000,
                "simulation_steps": req.simulation_steps,
                "seed": req.seed,
                "llm_provider": provider_label,
                "is_synthetic_poc": True,
                "assumed_reimbursement_rate": 0.50,
                "resolved_policy_mode": raw_result.policy_mode,
                "is_counterfactual": raw_result.is_counterfactual,
                "policy_version": "2024.1-provisional"
            },
            featured_personas=featured_personas
        )
