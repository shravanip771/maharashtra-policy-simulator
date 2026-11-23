"""
Simulation Service Layer: Orchestrates the execution of multi-step cohort simulations
and packages the results into the frontend Data Contract.
"""

import os
import uuid
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session

from data.dhule_adapter import DhuleEducationDatasetAdapter
from simulation.persona_generator import SyntheticPersonaGenerator
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
    InteractionRecordDTO
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
        adapter = DhuleEducationDatasetAdapter()
        config = adapter.create_population_config()
        generator = SyntheticPersonaGenerator(config=config, seed=req.seed)
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

        # 4. Resolve Counterfactual Policy Parameters if applicable
        counterfactual_config = None
        raw_mode = (getattr(req, "policy_mode", None) or "").strip().lower()
        cp = getattr(req, "counterfactual_params", None)
        cc = getattr(req, "counterfactual_config", None)
        if cp is not None and cc is not None:
            raise ValueError(
                "Cannot supply both 'counterfactual_params' and 'counterfactual_config'. "
                "Please provide only one."
            )
        if raw_mode in ("counterfactual",) or cp is not None or cc is not None:
            from simulation.policy_rules import DTEPolicyConfig
            if cp is not None:
                counterfactual_config = DTEPolicyConfig(
                    policy_version=f"counterfactual-{cp.policy_label or 'scenario'}",
                    max_income_limit=cp.max_income_limit if cp.max_income_limit is not None else 800000.0,
                    income_slab_lower=cp.income_slab_lower if cp.income_slab_lower is not None else 250000.0,
                    min_attendance_percent=cp.min_attendance_percent if cp.min_attendance_percent is not None else 50.0,
                    institutional_attendance_threshold=cp.institutional_attendance_threshold if cp.institutional_attendance_threshold is not None else 75.0,
                    enable_female_100_percent_rule=cp.enable_female_100_percent_rule if cp.enable_female_100_percent_rule is not None else True,
                    female_tuition_rate=cp.female_tuition_rate if cp.female_tuition_rate is not None else 1.00,
                    female_exam_rate=cp.female_exam_rate if cp.female_exam_rate is not None else 1.00,
                    male_tier1_govt_tuition_rate=cp.male_tier1_govt_tuition_rate if cp.male_tier1_govt_tuition_rate is not None else 1.00,
                    male_tier1_pvt_tuition_rate=cp.male_tier1_pvt_tuition_rate if cp.male_tier1_pvt_tuition_rate is not None else 0.50,
                    male_tier2_tuition_rate=cp.male_tier2_tuition_rate if cp.male_tier2_tuition_rate is not None else 0.50,
                    male_exam_rate=cp.male_exam_rate if cp.male_exam_rate is not None else 0.50,
                )
            elif cc is not None:
                counterfactual_config = cc
            else:
                counterfactual_config = DTEPolicyConfig(policy_version="counterfactual-scenario")

        # 5. Execute multi-step engine run
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
                policy_mode=getattr(req, "policy_mode", "legacy_poc"),
                override_reimbursement_rate=getattr(req, "override_reimbursement_rate", None),
                assumed_reimbursement_rate=getattr(req, "assumed_reimbursement_rate", None),
                counterfactual_config=counterfactual_config,
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
        final_cohort_res = raw_result.step_cohort_results[-1]
        policy_mode_val = getattr(final_cohort_res, "policy_mode", "legacy_poc")
        is_prov = (policy_mode_val in ("statutory", "counterfactual"))

        if is_prov:
            provisional_notes = [
                "PROVISIONAL ASSUMPTION: 50% examination fee relief for male candidates is provisional/unverified pending local primary GR confirmation.",
                "PROVISIONAL ASSUMPTION: Female 100% tuition and exam fee waiver is modeled under provisional GR No. शिष्यवृ-२०२४/प्र.क्र.१०५/तांशि-४ (08 July 2024; unverified raw GR text).",
                "PROVISIONAL ASSUMPTION: Male income slab cutoff of INR 2.50 Lakh and 8.00 Lakh ceiling modeled under provisional GR TEM-2018/C.R.35/TE-4.",
            ]
        else:
            provisional_notes = []

        metadata = SimulationMetadata(
            scheme_name=RajarshiShahuPolicyEngine.SCHEME_NAME,
            scheme_code="RCSMS-EBC",
            district=req.district,
            cohort_size=req.cohort_size,
            simulation_steps=req.simulation_steps,
            seed=req.seed,
            llm_provider=provider_label,
            is_synthetic_poc=True,
            assumed_reimbursement_rate=final_cohort_res.assumed_reimbursement_rate,
            data_disclaimer=(
                "Ground-truth demographics derived from official 2010-11 Dhule Educational Census table. "
                "Behavioral attributes, network ties, and dialogue are synthetic simulation models."
            ),
            policy_mode=policy_mode_val,
            policy_version=getattr(final_cohort_res, "policy_version", "2024.1-provisional"),
            is_provisional=is_prov,
            provisional_notes=provisional_notes
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
                "50% tuition fee reimbursement baseline estimate" if policy_mode_val == "legacy_poc" else f"Policy evaluation mode: {policy_mode_val}",
                "Synthetic social graph degree bound k <= 2"
            ]
        )

        # 5. Map Final Step Aggregate Metrics
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
            total_net_payable_tuition_fee_inr=getattr(final_cohort_res, "total_net_payable_tuition_fee_inr", 0.0),
            total_net_payable_exam_fee_inr=getattr(final_cohort_res, "total_net_payable_exam_fee_inr", 0.0),
            total_net_payable_fee_inr=getattr(final_cohort_res, "total_net_payable_fee_inr", 0.0),
            policy_mode=policy_mode_val,
            policy_version=getattr(final_cohort_res, "policy_version", "2024.1-provisional"),
            is_provisional=is_prov,
            provisional_notes=provisional_notes
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
                    annual_exam_fee=getattr(p, "annual_exam_fee", 0.0),
                    attendance_percentage=p.attendance_percentage,
                    previous_year_passed=p.previous_year_passed,
                    first_generation_learner=p.first_generation_learner,
                    is_statutorily_eligible=step_out.is_eligible,
                    estimated_fee_relief_inr=step_out.estimated_fee_relief_inr,
                    statutory_failure_reasons=step_out.statutory_failure_reasons,
                    tuition_fee_relief_inr=getattr(step_out, "tuition_fee_relief_inr", 0.0),
                    exam_fee_relief_inr=getattr(step_out, "exam_fee_relief_inr", 0.0),
                    net_payable_tuition_fee=getattr(step_out, "net_payable_tuition_fee", 0.0),
                    net_payable_exam_fee=getattr(step_out, "net_payable_exam_fee", 0.0),
                    total_net_payable_fee=getattr(step_out, "total_net_payable_fee", 0.0),
                    policy_version=getattr(step_out, "policy_version", "2024.1-provisional"),
                    is_provisional=getattr(step_out, "is_provisional", is_prov),
                    provisional_notes=provisional_notes,
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
                    inner_monologue=step_out.inner_monologue
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
