"""
Simulation Service Layer: Orchestrates the execution of multi-step cohort simulations
and packages the results into the frontend Data Contract.
"""

import os
from typing import Dict, List, Any

from data.dhule_adapter import DhuleEducationDatasetAdapter
from simulation.persona_generator import SyntheticPersonaGenerator
from simulation.agent import StubLLMProvider, GeminiLLMProvider
from simulation.engine import SimulationEngine, MultiStepSimulationResult, _safe_serialize
from simulation.policy_rules import RajarshiShahuPolicyEngine
from simulation.district_config import get_district_profile

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
    DistrictSummaryDTO
)


class SimulationService:
    """Service orchestrating persona generation, engine simulation, and DTO transformation."""

    @classmethod
    def execute_simulation(cls, req: SimulationRequest) -> SimulationResponse:
        # Resolve target district & statewide flag
        target_district = (req.district or "Dhule").strip()
        is_statewide = target_district.upper() in {"STATEWIDE", "ALL", "MAHARASHTRA"}

        # Safety Guard: Explicitly reject statewide simulations with live Gemini AI mode
        if is_statewide and req.use_gemini:
            raise ValueError(
                "Gemini live AI mode is restricted to single-district simulations to prevent rate exhaustion. "
                "Statewide simulation across all 36 districts must be run in offline mode (use_gemini=False)."
            )

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
        if is_statewide:
            per_district = req.cohort_size_per_district or 5
            cohort = SyntheticPersonaGenerator.generate_statewide_cohort(
                count_per_district=per_district,
                seed=req.seed
            )
            resolved_district_name = "Maharashtra (Statewide)"
            disclaimer = (
                f"Statewide composite simulation across all 36 Maharashtra districts ({len(cohort)} synthetic personas; {per_district} per district). "
                "Demographics combine official empirical tables (Dhule 2010-11, Mumbai City 2021-22) with calibrated provisional baseline districts. "
                "Behavioral factors, network ties, and dialogue are synthetic simulation models, not empirical census facts."
            )
            epistemic_status = "statewide_composite"
        else:
            if target_district.lower() == "mumbai":
                target_district = "Mumbai City"

            if target_district.lower() == "dhule":
                adapter = DhuleEducationDatasetAdapter()
                config = adapter.create_population_config()
                generator = SyntheticPersonaGenerator(config=config, seed=req.seed, district="Dhule")
                resolved_district_name = "Dhule"
                disclaimer = (
                    "Ground-truth demographics derived from official 2010-11 Dhule Educational Census table. "
                    "Behavioral attributes, network ties, and dialogue are synthetic simulation models."
                )
                epistemic_status = "empirical_observed"
            else:
                profile = get_district_profile(target_district)
                resolved_district_name = profile.district_name
                generator = SyntheticPersonaGenerator.for_district(resolved_district_name, seed=req.seed)
                if profile.provenance_tier == "empirical_observed":
                    disclaimer = (
                        f"Ground-truth demographics derived from {profile.source_reference} ({profile.reference_year}). "
                        "Behavioral attributes, network ties, and dialogue are synthetic simulation models."
                    )
                    epistemic_status = "empirical_observed"
                else:
                    disclaimer = (
                        f"Demographics for {resolved_district_name} District are provisional simulation baselines. "
                        "Behavioral factors are synthetic simulation priors, not empirical census facts."
                    )
                    epistemic_status = "provisional"

            id_prefix = f"{resolved_district_name.upper().replace(' ', '_')}-STU"
            cohort = generator.generate_cohort(count=req.cohort_size, id_prefix=id_prefix, seed=req.seed)

        # 3. Execute multi-step engine run
        engine = SimulationEngine(llm_provider=provider)
        cohort_display_name = f"Maharashtra-Statewide-{len(cohort)}-Persona-Cohort" if is_statewide else f"{resolved_district_name}-{req.cohort_size}-Persona-Cohort"
        raw_result: MultiStepSimulationResult = engine.run_multistep_cohort(
            personas=cohort,
            total_steps=req.simulation_steps,
            cohort_name=cohort_display_name,
            seed=req.seed,
            enable_social_interaction=True,
            max_connections_per_persona=2,
            policy_mode=req.policy_mode,
            assumed_reimbursement_rate=req.assumed_reimbursement_rate
        )

        # 4. Map Metadata & Provenance
        metadata = SimulationMetadata(
            scheme_name=RajarshiShahuPolicyEngine.SCHEME_NAME,
            scheme_code="RCSMS-EBC",
            district=resolved_district_name,
            cohort_size=len(cohort),
            simulation_steps=req.simulation_steps,
            seed=req.seed,
            llm_provider=provider_label,
            is_synthetic_poc=True,
            assumed_reimbursement_rate=raw_result.assumed_reimbursement_rate or 0.50,
            data_disclaimer=disclaimer,
            requested_policy_mode=req.policy_mode,
            resolved_policy_mode=raw_result.policy_mode,
            is_counterfactual=raw_result.is_counterfactual,
            policy_version="2024.1-provisional",
            epistemic_status=epistemic_status
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
            total_tuition_fee_relief_inr=final_cohort_res.total_tuition_fee_relief_inr,
            total_exam_fee_relief_inr=final_cohort_res.total_exam_fee_relief_inr,
            cohort_effective_relief_rate=final_cohort_res.cohort_effective_relief_rate
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
                    reimbursement_rate=step_out.reimbursement_percentage,
                    tuition_fee_relief_inr=step_out.tuition_fee_relief_inr,
                    exam_fee_relief_inr=step_out.exam_fee_relief_inr,
                    policy_details=_safe_serialize(step_out.policy_result) if step_out.policy_result else None
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

        # 10. Map District Summaries for Statewide Execution
        district_summaries: Optional[Dict[str, DistrictSummaryDTO]] = None
        if is_statewide:
            district_summaries = {}
            from simulation.district_config import DISTRICT_REGISTRY

            persona_obj_map = {p.persona_id: p for p in cohort}
            grouped_steps: Dict[str, List[Any]] = {}
            for step_res in final_cohort_res.individual_results:
                p_obj = persona_obj_map.get(step_res.persona_id)
                d_name = p_obj.district if p_obj else step_res.demographics_summary.get("district", "Unknown")
                grouped_steps.setdefault(d_name, []).append(step_res)

            for prof in DISTRICT_REGISTRY.values():
                d_name = prof.district_name
                s_list = grouped_steps.get(d_name, [])
                d_total = len(s_list)
                d_eligible = sum(1 for r in s_list if r.is_eligible)
                d_ineligible = d_total - d_eligible
                d_eligibility_rate = round(d_eligible / d_total, 4) if d_total > 0 else 0.0
                d_relief = round(sum(r.estimated_fee_relief_inr for r in s_list), 2)
                d_avg_relief = round(d_relief / d_eligible, 2) if d_eligible > 0 else 0.0
                d_awareness = round(sum(r.awareness_score for r in s_list) / d_total, 4) if d_total > 0 else 0.0
                d_benefit = round(sum(r.perceived_benefit_score for r in s_list) / d_total, 4) if d_total > 0 else 0.0
                d_app_prob = round(sum(r.application_probability for r in s_list) / d_total, 4) if d_total > 0 else 0.0
                d_uptake_prob = round(sum(r.expected_uptake_probability for r in s_list) / d_total, 4) if d_total > 0 else 0.0
                d_uptake_count = sum(1 for r in s_list if r.benefit_received)
                d_uptake_rate = round(d_uptake_count / d_total, 4) if d_total > 0 else 0.0

                d_talukas = sorted(list({
                    persona_obj_map[r.persona_id].taluka
                    for r in s_list
                    if r.persona_id in persona_obj_map and hasattr(persona_obj_map[r.persona_id], "taluka")
                }))

                district_summaries[d_name] = DistrictSummaryDTO(
                    district_name=d_name,
                    district_code=prof.district_id,
                    division=prof.division,
                    provenance_tier=prof.provenance_tier,
                    total_personas=d_total,
                    eligible_count=d_eligible,
                    ineligible_count=d_ineligible,
                    eligibility_rate=d_eligibility_rate,
                    mean_awareness=d_awareness,
                    mean_perceived_benefit=d_benefit,
                    mean_application_probability=d_app_prob,
                    expected_uptake_probability=d_uptake_prob,
                    realized_uptake_count=d_uptake_count,
                    realized_uptake_rate=d_uptake_rate,
                    total_estimated_fee_relief_inr=d_relief,
                    average_fee_relief_per_eligible_inr=d_avg_relief,
                    talukas_represented=d_talukas
                )

        return SimulationResponse(
            metadata=metadata,
            provenance_breakdown=provenance,
            aggregate_metrics=agg_metrics,
            step_metrics=step_metrics,
            network_topology=network,
            personas=personas_out,
            interactions=interactions_out,
            is_statewide=is_statewide,
            district_summaries=district_summaries
        )
