"""
Simulation Service Layer: Orchestrates the execution of multi-step cohort simulations
and packages the results into the frontend Data Contract.
"""

import os
import uuid
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Session

from data.dhule_adapter import DhuleEducationDatasetAdapter
from simulation.persona_generator import SyntheticPersonaGenerator
from simulation.agent import StubLLMProvider, GeminiLLMProvider
from simulation.engine import SimulationEngine, MultiStepSimulationResult, SimulationStepOutput
from simulation.policy_rules import RajarshiShahuPolicyEngine
from simulation.persona import StudentPersona

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
    StatewideCohortResponse,
    StatewideSimulationRequest,
    FeaturedPersonaDTO,
    DistrictSimulationResultDTO,
    StatewideSimulationSummaryDTO,
    StatewideSimulationMetadataDTO,
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
        from simulation.district_config import (
            get_district_profile,
            list_supported_districts,
            STATEWIDE_POPULATION_ALLOCATION_36,
        )
        try:
            district_profile = get_district_profile(req.district)
        except (KeyError, ValueError) as ke:
            supported = ", ".join(list_supported_districts())
            raise ValueError(f"Invalid district '{req.district}'. Supported districts: {supported}") from ke

        target_district_name = district_profile.district_name
        if target_district_name not in STATEWIDE_POPULATION_ALLOCATION_36:
            raise ValueError(
                f"Unsupported or unconfigured district '{req.district}'. Must be one of the 36 configured Maharashtra districts."
            )

        # Cohort size automatically determined from STATEWIDE_POPULATION_ALLOCATION_36
        cohort_size = STATEWIDE_POPULATION_ALLOCATION_36[target_district_name]
        clean_prefix = "MUMSUB" if target_district_name == "Mumbai Suburban" else target_district_name.upper().replace(" ", "_")[:6]
        id_prefix = f"{clean_prefix}-STU"

        if target_district_name == "Dhule":
            adapter = DhuleEducationDatasetAdapter()
            config = adapter.create_population_config()
            generator = SyntheticPersonaGenerator(config=config, seed=req.seed)
            cohort = generator.generate_cohort(count=cohort_size, id_prefix=id_prefix, seed=req.seed)
        else:
            generator = SyntheticPersonaGenerator.for_district(target_district_name, seed=req.seed)
            cohort = generator.generate_cohort(count=cohort_size, id_prefix=id_prefix, seed=req.seed)

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
                district=target_district_name,
                population_size=cohort_size,
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
                cohort_name=f"{target_district_name}-{cohort_size}-Persona-Cohort",
                seed=req.seed,
                enable_social_interaction=True,
                max_connections_per_persona=2,
                session=session,
                run_id=run_id,
                policy_id=policy_id,
                policy_config_id=policy_config_id,
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
            district=target_district_name,
            cohort_size=cohort_size,
            simulation_steps=req.simulation_steps,
            seed=req.seed,
            llm_provider=provider_label,
            is_synthetic_poc=True,
            assumed_reimbursement_rate=0.50,
            data_disclaimer=(
                f"Demographics grounded in {target_district_name} district profile ({district_profile.provenance_tier}). "
                f"District cohort size (N={cohort_size}) is a provisional synthetic quota derived from Census 2011 population proportions, "
                "not a verified student-population census statistic. "
                "Behavioral attributes, network ties, and dialogue are synthetic simulation models."
            )
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
            average_fee_relief_per_eligible_inr=final_cohort_res.average_fee_relief_per_eligible_inr
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
            total_nodes=net_summary.get("total_nodes", cohort_size),
            total_edges=net_summary.get("total_edges", 0),
            max_degree_limit=net_summary.get("max_degree_limit", 2),
            adjacency_list=net_summary.get("adjacency_list", {})
        )

        # 8. Deterministically select 10 featured personas using simulation seed
        import random
        sample_rng = random.Random(req.seed)
        k_sample = min(10, len(cohort))
        featured_indices = sorted(sample_rng.sample(range(len(cohort)), k=k_sample))
        featured_personas_raw = [cohort[i] for i in featured_indices]
        featured_step_outs = [final_cohort_res.individual_results[i] for i in featured_indices]
        featured_ids = {p.persona_id for p in featured_personas_raw}

        persona_name_map = {p.persona_id: p.name for p in cohort}

        # 9. Extract interactions involving the featured personas
        featured_interactions_map: Dict[str, List[InteractionRecordDTO]] = {p_id: [] for p_id in featured_ids}
        featured_interactions_all: List[InteractionRecordDTO] = []
        seen_interaction_keys = set()
        for s_idx in range(1, req.simulation_steps + 1):
            for r in raw_result.interactions_by_step.get(s_idx, []):
                s_id = r.get("sender_id", "")
                r_id = r.get("receiver_id", "")
                if s_id in featured_ids or r_id in featured_ids:
                    dto = InteractionRecordDTO(
                        simulation_step=s_idx,
                        sender_id=s_id,
                        sender_name=persona_name_map.get(s_id, s_id),
                        receiver_id=r_id,
                        receiver_name=persona_name_map.get(r_id, r_id),
                        interaction_topic=r.get("interaction_topic", "SCHEME_AWARENESS"),
                        sender_message=r.get("sender_message", ""),
                        receiver_response=r.get("receiver_response", ""),
                        state_changed=r.get("state_changed", False),
                        state_changes=r.get("state_changes", {})
                    )
                    if s_id in featured_ids:
                        featured_interactions_map[s_id].append(dto)
                    if r_id in featured_ids:
                        featured_interactions_map[r_id].append(dto)
                    inter_key = (s_idx, s_id, r_id, dto.interaction_topic, dto.sender_message)
                    if inter_key not in seen_interaction_keys:
                        seen_interaction_keys.add(inter_key)
                        featured_interactions_all.append(dto)

        # 10. Map Featured Persona DTOs
        personas_out: List[FeaturedPersonaDTO] = []
        for p, step_out in zip(featured_personas_raw, featured_step_outs):
            ev = raw_result.state_evolution_summary.get(p.persona_id, {})
            personas_out.append(
                FeaturedPersonaDTO(
                    persona_id=p.persona_id,
                    name=p.name,
                    gender=p.gender,
                    age=p.age,
                    district=p.district,
                    taluka=getattr(p, "taluka", p.district) or p.district,
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
                    interaction_history=featured_interactions_map.get(p.persona_id, [])
                )
            )

        return SimulationResponse(
            metadata=metadata,
            provenance_breakdown=provenance,
            aggregate_metrics=agg_metrics,
            step_metrics=step_metrics,
            network_topology=network,
            personas=personas_out,
            interactions=featured_interactions_all,
            featured_personas=personas_out
        )

    @classmethod
    def generate_statewide_cohort(cls, seed: int = 42) -> StatewideCohortResponse:
        """
        Generates the statewide cohort of 1,000 student personas distributed across
        all 36 configured districts according to Census 2011 population weighting.
        Evaluates baseline statutory eligibility for each persona.
        """
        from simulation.district_config import (
            STATEWIDE_POPULATION_ALLOCATION_36,
        )

        cohort = SyntheticPersonaGenerator.generate_weighted_state_population(
            district_quotas=STATEWIDE_POPULATION_ALLOCATION_36,
            seed=seed
        )
        personas_out: List[PersonaOutput] = []

        for p in cohort:
            eval_res = RajarshiShahuPolicyEngine.evaluate_eligibility(p)
            personas_out.append(
                PersonaOutput(
                    persona_id=p.persona_id,
                    name=p.name,
                    gender=p.gender,
                    age=p.age,
                    district=p.district,
                    taluka=getattr(p, "taluka", p.district) or p.district,
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
                    is_statutorily_eligible=eval_res.is_eligible,
                    estimated_fee_relief_inr=eval_res.estimated_fee_relief_inr,
                    statutory_failure_reasons=eval_res.failure_reasons,
                    initial_awareness=p.initial_awareness,
                    final_awareness=p.initial_awareness,
                    awareness_gain=0.0,
                    initial_trust=p.institutional_trust,
                    final_trust=p.institutional_trust,
                    digital_literacy=p.digital_literacy,
                    document_readiness=p.document_readiness,
                    application_probability=0.0,
                    completion_probability=0.0,
                    final_state=p.current_state.value,
                    stated_intention="Cohort baseline initialized (pre-simulation).",
                    major_barriers=[],
                    inner_monologue=""
                )
            )

        return StatewideCohortResponse(
            total_count=len(cohort),
            district_allocations=STATEWIDE_POPULATION_ALLOCATION_36,
            missing_district="None (All 36 districts allocated)",
            seed=seed,
            personas=personas_out,
        )

    @classmethod
    def execute_statewide_simulation(
        cls,
        req: StatewideSimulationRequest,
    ) -> StatewideSimulationResponse:
        """
        Executes a multi-step simulation across the complete 1,000-persona statewide cohort.
        Aggregates macro KPIs across all 1,000 personas, compiles district-wise outcomes for all
        36 districts, and deterministically samples exactly 10 featured personas with complete
        peer interaction histories for frontend presentation.
        """
        import random
        from simulation.district_config import STATEWIDE_POPULATION_ALLOCATION_36

        # 1. Setup LLM provider
        if req.use_gemini:
            model_name = req.gemini_model or "gemini-3.1-flash-lite"
            provider = GeminiLLMProvider(model_name=model_name, fallback_to_stub=True)
            provider_label = f"Google Gemini API ({model_name})"
        else:
            provider = StubLLMProvider()
            provider_label = "Deterministic Rule-Grounded Stub (Offline)"

        # 2. Generate complete statewide cohort across 36 districts (N=1,000)
        cohort = SyntheticPersonaGenerator.generate_weighted_state_population(
            district_quotas=STATEWIDE_POPULATION_ALLOCATION_36,
            seed=req.seed
        )

        run_id = f"statewide-run-{uuid.uuid4()}"

        # 3. Execute multi-step simulation on the complete 1,000 cohort
        engine = SimulationEngine(llm_provider=provider)
        raw_result: MultiStepSimulationResult = engine.run_multistep_cohort(
            personas=cohort,
            total_steps=req.simulation_steps,
            cohort_name="Maharashtra-Statewide-1000-Cohort",
            seed=req.seed,
            enable_social_interaction=True,
            max_connections_per_persona=2,
        )

        final_cohort_res = raw_result.final_cohort_result
        persona_name_map = {p.persona_id: p.name for p in cohort}

        # 4. Deterministically select 10 featured personas using simulation seed
        sample_rng = random.Random(req.seed)
        featured_indices = sorted(sample_rng.sample(range(len(cohort)), k=10))
        featured_personas_raw = [cohort[i] for i in featured_indices]
        featured_step_outs = [final_cohort_res.individual_results[i] for i in featured_indices]
        featured_ids = {p.persona_id for p in featured_personas_raw}

        # 5. Extract interactions involving the featured personas
        featured_interactions_map: Dict[str, List[InteractionRecordDTO]] = {p_id: [] for p_id in featured_ids}
        featured_interactions_all: List[InteractionRecordDTO] = []
        seen_interaction_keys = set()
        for s_idx in range(1, req.simulation_steps + 1):
            for r in raw_result.interactions_by_step.get(s_idx, []):
                s_id = r.get("sender_id", "")
                r_id = r.get("receiver_id", "")
                if s_id in featured_ids or r_id in featured_ids:
                    dto = InteractionRecordDTO(
                        simulation_step=s_idx,
                        sender_id=s_id,
                        sender_name=persona_name_map.get(s_id, s_id),
                        receiver_id=r_id,
                        receiver_name=persona_name_map.get(r_id, r_id),
                        interaction_topic=r.get("interaction_topic", "SCHEME_AWARENESS"),
                        sender_message=r.get("sender_message", ""),
                        receiver_response=r.get("receiver_response", ""),
                        state_changed=r.get("state_changed", False),
                        state_changes=r.get("state_changes", {})
                    )
                    if s_id in featured_ids:
                        featured_interactions_map[s_id].append(dto)
                    if r_id in featured_ids:
                        featured_interactions_map[r_id].append(dto)
                    inter_key = (s_idx, s_id, r_id, dto.interaction_topic, dto.sender_message)
                    if inter_key not in seen_interaction_keys:
                        seen_interaction_keys.add(inter_key)
                        featured_interactions_all.append(dto)

        # 6. Map Featured Personas DTOs
        featured_dtos: List[FeaturedPersonaDTO] = []
        for p, step_out in zip(featured_personas_raw, featured_step_outs):
            ev = raw_result.state_evolution_summary.get(p.persona_id, {})
            featured_dtos.append(
                FeaturedPersonaDTO(
                    persona_id=p.persona_id,
                    name=p.name,
                    gender=p.gender,
                    age=p.age,
                    district=p.district,
                    taluka=getattr(p, "taluka", p.district) or p.district,
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
                    interaction_history=featured_interactions_map.get(p.persona_id, [])
                )
            )

        # 7. Aggregate District Results across all 36 districts using ALL 1,000 personas
        district_results: List[DistrictSimulationResultDTO] = []
        district_personas_map: Dict[str, List[Tuple[StudentPersona, SimulationStepOutput]]] = {
            d: [] for d in STATEWIDE_POPULATION_ALLOCATION_36
        }
        for p, step_out in zip(cohort, final_cohort_res.individual_results):
            if p.district in district_personas_map:
                district_personas_map[p.district].append((p, step_out))
            else:
                district_personas_map.setdefault(p.district, []).append((p, step_out))

        for dist_name, expected_count in STATEWIDE_POPULATION_ALLOCATION_36.items():
            dp_list = district_personas_map.get(dist_name, [])
            d_total = len(dp_list)
            d_eligible = sum(1 for _, so in dp_list if so.is_eligible)
            d_ineligible = d_total - d_eligible
            d_attempted = sum(1 for _, so in dp_list if so.attempted_application)
            d_completed = sum(1 for _, so in dp_list if so.completed_application)
            d_beneficiaries = sum(1 for _, so in dp_list if so.benefit_received)
            d_relief = sum(so.estimated_fee_relief_inr for _, so in dp_list)
            d_avg_relief = round(d_relief / d_eligible, 2) if d_eligible > 0 else 0.0
            d_mean_aw = round(sum(so.awareness_score for _, so in dp_list) / d_total, 4) if d_total > 0 else 0.0
            d_mean_app_prob = round(sum(so.application_probability for _, so in dp_list) / d_total, 4) if d_total > 0 else 0.0
            d_uptake_rate = round(d_beneficiaries / d_total, 4) if d_total > 0 else 0.0
            d_elig_rate = round(d_eligible / d_total, 4) if d_total > 0 else 0.0

            district_results.append(
                DistrictSimulationResultDTO(
                    district_name=dist_name,
                    allocated_personas=d_total,
                    eligible_count=d_eligible,
                    ineligible_count=d_ineligible,
                    eligibility_rate=d_elig_rate,
                    attempted_applications=d_attempted,
                    completed_applications=d_completed,
                    realized_beneficiaries=d_beneficiaries,
                    uptake_rate=d_uptake_rate,
                    total_estimated_fee_relief_inr=d_relief,
                    average_relief_per_eligible_inr=d_avg_relief,
                    mean_awareness=d_mean_aw,
                    mean_application_probability=d_mean_app_prob
                )
            )

        # 8. Compute Top Barriers and Step Metrics across all 1,000 personas
        barrier_counts: Dict[str, int] = {}
        for so in final_cohort_res.individual_results:
            for b in so.perceived_barriers:
                barrier_counts[b] = barrier_counts.get(b, 0) + 1

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

        # Initial vs Final awareness means
        initial_awarenesses = [p.initial_awareness for p in cohort]
        mean_initial_aw = round(sum(initial_awarenesses) / len(initial_awarenesses), 4) if initial_awarenesses else 0.0
        mean_final_aw = round(final_cohort_res.average_awareness_score, 4)
        mean_gain = round(mean_final_aw - mean_initial_aw, 4)

        # 9. Build Summary DTO
        summary_dto = StatewideSimulationSummaryDTO(
            total_personas=final_cohort_res.total_personas,
            eligible_count=final_cohort_res.eligible_count,
            ineligible_count=final_cohort_res.ineligible_count,
            eligibility_rate=round(final_cohort_res.eligibility_rate, 4),
            mean_initial_awareness=mean_initial_aw,
            mean_final_awareness=mean_final_aw,
            mean_awareness_gain=mean_gain,
            mean_perceived_benefit=round(final_cohort_res.average_perceived_benefit_score, 4),
            mean_application_probability=round(final_cohort_res.average_application_probability, 4),
            expected_uptake_probability=round(final_cohort_res.average_expected_uptake_probability, 4),
            attempted_applications_count=final_cohort_res.attempted_application_count,
            completed_applications_count=final_cohort_res.completed_application_count,
            realized_beneficiaries_count=final_cohort_res.benefit_received_count,
            realized_uptake_rate=round(final_cohort_res.uptake_rate, 4),
            total_estimated_fee_relief_inr=final_cohort_res.total_estimated_fee_relief_inr,
            average_fee_relief_per_eligible_inr=final_cohort_res.average_fee_relief_per_eligible_inr,
            ineligibility_reasons_summary=final_cohort_res.ineligibility_reasons_summary,
            simulation_state_distribution=final_cohort_res.state_distribution,
            top_application_barriers=barrier_counts,
            step_metrics=step_metrics
        )

        metadata_dto = StatewideSimulationMetadataDTO(
            run_id=run_id,
            seed=req.seed,
            simulation_steps=req.simulation_steps,
            scheme_name=RajarshiShahuPolicyEngine.SCHEME_NAME,
            scheme_code="RCSMS-EBC",
            total_districts_configured=len(STATEWIDE_POPULATION_ALLOCATION_36),
            total_personas_processed=len(cohort),
            llm_provider=provider_label,
            completion_status="SUCCESS",
            assumed_reimbursement_rate=0.50,
            data_disclaimer=(
                "Statewide cohort (N=1,000) proportionally allocated across all 36 Maharashtra districts. "
                "District allocations are provisional synthetic quotas derived from Census 2011 population weighting, "
                "not verified student-population statistics or administrative census facts. "
                "Demographics grounded in division-level urbanization and census benchmarks. "
                "Behavioral attributes, peer diffusion dynamics, and dialogue are synthetic simulation models."
            )
        )

        return StatewideSimulationResponse(
            simulation_summary=summary_dto,
            district_results=district_results,
            featured_personas=featured_dtos,
            simulation_metadata=metadata_dto,
            interactions=featured_interactions_all
        )
