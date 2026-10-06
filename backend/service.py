"""
Simulation Service Layer: Orchestrates the execution of multi-step cohort simulations
and packages the results into the frontend Data Contract.
"""

import os
from typing import Dict, List, Any

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
    def execute_simulation(cls, req: SimulationRequest) -> SimulationResponse:
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

        # 3. Execute multi-step engine run
        engine = SimulationEngine(llm_provider=provider)
        raw_result: MultiStepSimulationResult = engine.run_multistep_cohort(
            personas=cohort,
            total_steps=req.simulation_steps,
            cohort_name=f"{req.district}-{req.cohort_size}-Persona-Cohort",
            seed=req.seed,
            enable_social_interaction=True,
            max_connections_per_persona=2
        )

        # 4. Map Metadata & Provenance
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
