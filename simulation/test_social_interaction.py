"""
Unit Tests for Multi-Persona Social Interaction & Multi-Step Simulation (Phase 2 Milestone)

Verifies:
1. Deterministic social-network generation and seed reproducibility.
2. Complete absence of self-connections across the social network graph.
3. Bounded degree constraints on network topology.
4. Bounded state updates (all state variables strictly clamped to [0.0, 1.0]).
5. Interaction record schema completeness and serialization.
6. Multi-step state evolution and peer diffusion dynamics.
7. Absolute preservation of deterministic statutory policy authority.
"""

from typing import List
import json

from simulation.persona import (
    StudentPersona,
    InstitutionType,
    AdmissionMode,
    PersonalityTraits,
    SimulationState
)
from simulation.policy_rules import RajarshiShahuPolicyEngine, PolicyEvaluationResult
from simulation.social_network import SyntheticSocialNetwork, NetworkEdge
from simulation.interaction import (
    InteractionTopic,
    InteractionRecord,
    StateChangeDelta,
    InteractionStateEngine,
    clamp
)
from simulation.agent import (
    PersonaAgent,
    StubLLMProvider,
    PersonaInteractionOutput,
    build_peer_interaction_prompt
)
from simulation.engine import (
    SimulationEngine,
    SimulationStepOutput,
    CohortSimulationResult,
    MultiStepSimulationResult
)
from data.dhule_adapter import DhuleEducationDatasetAdapter
from simulation.persona_generator import SyntheticPersonaGenerator


def create_test_cohort(count: int = 10, seed: int = 42) -> List[StudentPersona]:
    """Generates a standard test cohort using the Dhule empirical adapter."""
    adapter = DhuleEducationDatasetAdapter()
    config = adapter.create_population_config()
    generator = SyntheticPersonaGenerator(config=config, seed=seed)
    return generator.generate_cohort(count=count, seed=seed)


def test_deterministic_social_network_generation():
    """Verifies that social network generation is fully deterministic given a seed."""
    cohort1 = create_test_cohort(count=10, seed=42)
    cohort2 = create_test_cohort(count=10, seed=42)

    net1 = SyntheticSocialNetwork(personas=cohort1, seed=100, max_degree=2)
    net2 = SyntheticSocialNetwork(personas=cohort2, seed=100, max_degree=2)

    assert net1.adjacency == net2.adjacency
    assert len(net1.edges) == len(net2.edges)
    for e1, e2 in zip(net1.edges, net2.edges):
        assert e1.source_id == e2.source_id
        assert e1.target_id == e2.target_id
        assert round(e1.affinity_score, 4) == round(e2.affinity_score, 4)

    # Different seed produces different topology
    net3 = SyntheticSocialNetwork(personas=cohort1, seed=999, max_degree=2)
    assert net1.adjacency != net3.adjacency
    print("PASS: test_deterministic_social_network_generation")


def test_no_self_connections_and_bounded_degree():
    """Verifies that no persona connects to itself and degree bounds are respected."""
    cohort = create_test_cohort(count=10, seed=42)
    max_degree = 2
    network = SyntheticSocialNetwork(personas=cohort, seed=42, max_degree=max_degree)

    for p in cohort:
        neighbors = network.get_neighbors(p.persona_id)
        # 1. No self-loops
        assert p.persona_id not in neighbors, f"Self-connection detected for {p.persona_id}"
        # 2. Bounded degree
        assert len(neighbors) <= max_degree + 1, f"Degree {len(neighbors)} exceeds limit for {p.persona_id}"

    # Edge list checks
    for edge in network.edges:
        assert edge.source_id != edge.target_id
        assert edge.affinity_score > 0.0

    print("PASS: test_no_self_connections_and_bounded_degree")


def test_bounded_state_updates():
    """Verifies that state changes are strictly clamped to [0.0, 1.0] under extreme values."""
    p_high = StudentPersona(
        persona_id="P-HIGH",
        name="High Awareness Student",
        age=20,
        gender="Male",
        district="Dhule",
        is_maharashtra_domicile=True,
        family_income=200000.0,
        caste_category="General-EBC",
        initial_awareness=0.99,
        institutional_trust=0.95,
        document_readiness=0.95,
        peer_network_support=0.90
    )

    p_low = StudentPersona(
        persona_id="P-LOW",
        name="Low Awareness Student",
        age=19,
        gender="Female",
        district="Dhule",
        is_maharashtra_domicile=True,
        family_income=150000.0,
        caste_category="General-EBC",
        initial_awareness=0.05,
        institutional_trust=0.05,
        document_readiness=0.05,
        peer_network_support=0.10
    )

    # Test scheme awareness diffusion
    has_changed, delta, delta_dict = InteractionStateEngine.compute_state_updates(
        sender=p_high,
        receiver=p_low,
        topic=InteractionTopic.SCHEME_AWARENESS,
        sender_eligible=True,
        receiver_eligible=True
    )

    assert has_changed is True
    assert 0.0 <= delta.awareness_after <= 1.0
    assert 0.0 <= delta.trust_after <= 1.0
    assert 0.0 <= delta.doc_readiness_after <= 1.0
    assert 0.0 <= delta.peer_support_after <= 1.0
    assert delta.awareness_after > p_low.initial_awareness

    # Apply update
    InteractionStateEngine.apply_state_updates(p_low, delta)
    assert p_low.initial_awareness == delta.awareness_after
    assert 0.0 <= p_low.initial_awareness <= 1.0

    # Test clamp utility directly on boundary extremes
    assert clamp(-5.0) == 0.0
    assert clamp(10.5) == 1.0
    assert clamp(0.75333) == 0.7533
    print("PASS: test_bounded_state_updates")


def test_interaction_schema_and_agent_dialogue():
    """Verifies that PersonaAgent.interact_with produces valid structured InteractionRecord."""
    cohort = create_test_cohort(count=10, seed=42)
    p1 = cohort[0]
    p2 = cohort[1]

    eval1 = RajarshiShahuPolicyEngine.evaluate_eligibility(p1)
    eval2 = RajarshiShahuPolicyEngine.evaluate_eligibility(p2)

    agent = PersonaAgent(persona=p1, llm_provider=StubLLMProvider())
    record: InteractionRecord = agent.interact_with(
        receiver=p2,
        sender_eval=eval1,
        receiver_eval=eval2,
        topic=InteractionTopic.APPLICATION_GUIDANCE.value,
        step_index=1
    )

    assert record.sender_id == p1.persona_id
    assert record.receiver_id == p2.persona_id
    assert record.simulation_step == 1
    assert record.interaction_topic == InteractionTopic.APPLICATION_GUIDANCE.value
    assert len(record.sender_message) > 0
    assert len(record.receiver_response) > 0
    assert isinstance(record.state_changed, bool)
    assert isinstance(record.state_changes, dict)
    assert "awareness" in record.pre_interaction_state
    assert "awareness" in record.post_interaction_state

    # Memory trace verification
    assert len(p1.memory) > 0
    assert len(p2.memory) > 0
    assert p1.memory[-1]["event_type"] == "SENT_PEER_INTERACTION"
    assert p2.memory[-1]["event_type"] == "RECEIVED_PEER_INTERACTION"

    # JSON serialization
    json_str = record.to_json()
    parsed = json.loads(json_str)
    assert parsed["sender_id"] == p1.persona_id
    print("PASS: test_interaction_schema_and_agent_dialogue")


def test_multistep_cohort_simulation_cycle():
    """Verifies end-to-end multi-step cohort simulation with social interactions."""
    cohort = create_test_cohort(count=10, seed=42)
    engine = SimulationEngine()

    total_steps = 2
    multi_result: MultiStepSimulationResult = engine.run_multistep_cohort(
        personas=cohort,
        total_steps=total_steps,
        seed=42,
        enable_social_interaction=True
    )

    assert multi_result.total_personas == 10
    assert multi_result.total_steps == total_steps
    assert len(multi_result.step_cohort_results) == total_steps
    assert 1 in multi_result.interactions_by_step
    assert 2 in multi_result.interactions_by_step

    # Verify awareness diffusion across steps
    step1_awareness = multi_result.step_cohort_results[0].average_awareness_score
    step2_awareness = multi_result.step_cohort_results[1].average_awareness_score
    assert step2_awareness >= step1_awareness

    # Verify state evolution summary
    for pid, ev in multi_result.state_evolution_summary.items():
        assert "initial_awareness" in ev
        assert "final_awareness" in ev
        assert "awareness_gain" in ev
        assert ev["final_awareness"] >= ev["initial_awareness"]

    print("PASS: test_multistep_cohort_simulation_cycle")


def test_statutory_eligibility_authority_preserved_across_interactions():
    """Verifies that social interactions cannot turn an ineligible student eligible."""
    ineligible_student = StudentPersona(
        persona_id="INELIGIBLE-001",
        name="Kailash Patil",
        age=20,
        gender="Male",
        district="Dhule",
        is_maharashtra_domicile=True,
        family_income=950000.0,  # Exceeds 8 Lakh cap
        caste_category="General-EBC",
        admission_mode=AdmissionMode.MANAGEMENT_QUOTA,
        annual_tuition_fee=120000.0,
        initial_awareness=0.20
    )

    eligible_peer = StudentPersona(
        persona_id="ELIGIBLE-002",
        name="Sunita Patil",
        age=19,
        gender="Female",
        district="Dhule",
        is_maharashtra_domicile=True,
        family_income=120000.0,
        caste_category="General-EBC",
        admission_mode=AdmissionMode.CAP,
        annual_tuition_fee=90000.0,
        initial_awareness=0.85
    )

    eval_inelig = RajarshiShahuPolicyEngine.evaluate_eligibility(ineligible_student)
    eval_elig = RajarshiShahuPolicyEngine.evaluate_eligibility(eligible_peer)

    assert eval_inelig.is_eligible is False
    assert eval_elig.is_eligible is True

    # Peer informs ineligible student about the scheme
    agent = PersonaAgent(persona=eligible_peer, llm_provider=StubLLMProvider())
    record = agent.interact_with(
        receiver=ineligible_student,
        sender_eval=eval_elig,
        receiver_eval=eval_inelig,
        topic=InteractionTopic.SCHEME_AWARENESS.value,
        step_index=1
    )

    # Ineligible student gains awareness
    assert ineligible_student.initial_awareness > 0.20

    # But deterministic statutory check remains firmly False
    eval_after = RajarshiShahuPolicyEngine.evaluate_eligibility(ineligible_student)
    assert eval_after.is_eligible is False
    assert eval_after.estimated_fee_relief_inr == 0.0

    # And simulation engine marks final state as REJECTED / Ineligible
    engine = SimulationEngine()
    step_out = engine.run_step(ineligible_student, step_index=2)
    assert step_out.is_eligible is False
    assert step_out.final_simulation_state == "REJECTED"
    print("PASS: test_statutory_eligibility_authority_preserved_across_interactions")


def test_no_universal_50_percent_claim_in_generated_dialogue():
    """Verifies that dialogue never presents 50% as a universal statutory scheme rule."""
    cohort = create_test_cohort(count=10, seed=42)
    provider = StubLLMProvider()

    for p1 in cohort[:3]:
        for p2 in cohort[3:6]:
            eval1 = RajarshiShahuPolicyEngine.evaluate_eligibility(p1)
            eval2 = RajarshiShahuPolicyEngine.evaluate_eligibility(p2)

            for topic in InteractionTopic:
                out = provider.generate_peer_interaction(
                    sender=p1,
                    sender_eval=eval1,
                    receiver=p2,
                    receiver_eval=eval2,
                    topic=topic.value,
                    step_index=1
                )
                # Assert no universal 50% claims
                assert "you get 50% tuition fee reimbursement" not in out.sender_message.lower()
                assert "50% ebc fee concession scheme" not in out.interaction_summary.lower()

    print("PASS: test_no_universal_50_percent_claim_in_generated_dialogue")


def test_no_unsupported_local_operational_claims():
    """Verifies dialogue does not invent specific local queues, named offices or ungrounded claims."""
    cohort = create_test_cohort(count=10, seed=42)
    provider = StubLLMProvider()

    for p1 in cohort[:3]:
        for p2 in cohort[3:6]:
            eval1 = RajarshiShahuPolicyEngine.evaluate_eligibility(p1)
            eval2 = RajarshiShahuPolicyEngine.evaluate_eligibility(p2)

            out = provider.generate_peer_interaction(
                sender=p1,
                sender_eval=eval1,
                receiver=p2,
                receiver_eval=eval2,
                topic=InteractionTopic.DOCUMENTATION_HURDLE.value,
                step_index=1
            )
            # Assert no invented local queue claims
            assert "has huge crowds" not in out.sender_message.lower()
            assert "setu kendra in" not in out.sender_message.lower()

    print("PASS: test_no_unsupported_local_operational_claims")


def test_no_positive_framing_of_zero_benefit_and_monetary_consistency():
    """Verifies that zero estimated benefit is never praised as a financial gain."""
    ineligible_student = StudentPersona(
        persona_id="INELIGIBLE-001",
        name="Kailash Patil",
        age=20,
        gender="Male",
        district="Dhule",
        is_maharashtra_domicile=True,
        family_income=950000.0,
        caste_category="General-EBC",
        admission_mode=AdmissionMode.MANAGEMENT_QUOTA,
        annual_tuition_fee=120000.0,
        initial_awareness=0.20
    )

    eligible_peer = StudentPersona(
        persona_id="ELIGIBLE-002",
        name="Sunita Patil",
        age=19,
        gender="Female",
        district="Dhule",
        is_maharashtra_domicile=True,
        family_income=120000.0,
        caste_category="General-EBC",
        admission_mode=AdmissionMode.CAP,
        annual_tuition_fee=90000.0,
        initial_awareness=0.85
    )

    eval_inelig = RajarshiShahuPolicyEngine.evaluate_eligibility(ineligible_student)
    eval_elig = RajarshiShahuPolicyEngine.evaluate_eligibility(eligible_peer)

    provider = StubLLMProvider()

    # When ineligible student receives TRUST_AND_DISCOURAGEMENT
    out = provider.generate_peer_interaction(
        sender=eligible_peer,
        sender_eval=eval_elig,
        receiver=ineligible_student,
        receiver_eval=eval_inelig,
        topic=InteractionTopic.TRUST_AND_DISCOURAGEMENT.value,
        step_index=1
    )

    # Must NOT say "getting INR 0 credited is much better"
    assert "inr 0 credited is much better" not in out.receiver_response.lower()
    assert "getting inr 0" not in out.receiver_response.lower()
    assert "not eligible for fee relief" in out.receiver_response.lower()

    # When eligible student receives TRUST_AND_DISCOURAGEMENT
    out_elig = provider.generate_peer_interaction(
        sender=ineligible_student,
        sender_eval=eval_inelig,
        receiver=eligible_peer,
        receiver_eval=eval_elig,
        topic=InteractionTopic.TRUST_AND_DISCOURAGEMENT.value,
        step_index=1
    )
    assert f"INR {eval_elig.estimated_fee_relief_inr:,.0f}" in out_elig.receiver_response
    assert "still critical" in out_elig.receiver_response.lower()

    print("PASS: test_no_positive_framing_of_zero_benefit_and_monetary_consistency")


def test_monetary_benefit_provenance_and_llm_immutability():
    """
    Architecture Audit Test:
    Verifies that:
    1. Monetary fee relief originates exclusively from deterministic Python policy calculation.
    2. Prompt payload injects that exact calculated number into LLM context.
    3. LLM dialogue receives the pre-calculated figure and has no authority over the calculation.
    4. Simulation results and benefit totals are strictly derived from deterministic engine output.
    """
    from simulation.agent import build_peer_interaction_prompt, build_persona_reasoning_prompt

    cohort = create_test_cohort(count=3, seed=42)
    p1 = cohort[0]  # Vishal Patil, B.Tech, Tuition INR 95,900
    p3 = cohort[2]  # Priyanka Mali, MBA (Management Quota / Ineligible)

    # 1. Deterministic calculation
    eval1 = RajarshiShahuPolicyEngine.evaluate_eligibility(p1)
    eval3 = RajarshiShahuPolicyEngine.evaluate_eligibility(p3)

    # B.Tech at 50% rate = 95,900 * 0.5 = 47,950.0 (the exact origin of ~47k in dialogue)
    assert eval1.is_eligible is True
    assert eval1.estimated_fee_relief_inr == 47950.0
    assert eval3.is_eligible is False
    assert eval3.estimated_fee_relief_inr == 0.0

    # 2. Verify prompt context injection
    prompt_dict = build_peer_interaction_prompt(
        sender=p1,
        sender_eval=eval1,
        receiver=p3,
        receiver_eval=eval3,
        topic=InteractionTopic.SCHEME_AWARENESS.value,
        step_index=1
    )
    user_payload = json.loads(prompt_dict["user"])

    assert user_payload["sender_profile"]["estimated_fee_relief_inr"] == 47950.0
    assert user_payload["sender_profile"]["is_statutorily_eligible"] is True
    assert user_payload["receiver_profile"]["is_statutorily_eligible"] is False

    # 3. Verify that LLM cannot modify or output statutory benefits
    # The JSON schema required from LLM only permits conversational text, not financial calculation:
    schema = user_payload["required_json_schema"]
    assert "estimated_fee_relief_inr" not in schema
    assert "is_statutorily_eligible" not in schema

    # 4. Verify simulation engine produces aggregate financial relief from policy engine, not LLM text
    engine = SimulationEngine()
    step_res = engine.run_step(p1, step_index=1)
    assert step_res.estimated_fee_relief_inr == 47950.0

    print("PASS: test_monetary_benefit_provenance_and_llm_immutability")


if __name__ == "__main__":
    test_deterministic_social_network_generation()
    test_no_self_connections_and_bounded_degree()
    test_bounded_state_updates()
    test_interaction_schema_and_agent_dialogue()
    test_multistep_cohort_simulation_cycle()
    test_statutory_eligibility_authority_preserved_across_interactions()
    test_no_universal_50_percent_claim_in_generated_dialogue()
    test_no_unsupported_local_operational_claims()
    test_no_positive_framing_of_zero_benefit_and_monetary_consistency()
    test_monetary_benefit_provenance_and_llm_immutability()
    print("All multi-persona social interaction tests passed successfully!")


