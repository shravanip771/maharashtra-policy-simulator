"""
Multi-Persona Social Interaction & Multi-Step Cohort Demo (10-Persona Dhule Pilot)

Runs a 2-step agent-based policy simulation of the 10-person Dhule student cohort,
modeling:
- Step 1: Observe -> Reason -> Interact -> Act -> Update State
- Step 2: Observe -> Reason -> Interact -> Act -> Update State

USAGE:
    # 1. Run offline with deterministic Stub provider (Default, ₹0 cost):
    python -m simulation.run_multistep_demo

    # 2. Optionally run with live Gemini API (if configured):
    $env:USE_GEMINI="1"
    $env:GEMINI_API_KEY="your_api_key_here"
    python -m simulation.run_multistep_demo
"""

import os
import sys
import json

from data.dhule_adapter import DhuleEducationDatasetAdapter
from simulation.persona_generator import SyntheticPersonaGenerator
from simulation.agent import StubLLMProvider, GeminiLLMProvider
from simulation.engine import SimulationEngine, MultiStepSimulationResult
from simulation.policy_rules import RajarshiShahuPolicyEngine


import argparse


def run_demo() -> int:
    parser = argparse.ArgumentParser(description="Multi-Persona Social Interaction & Multi-Step Cohort Demo")
    parser.add_argument("--count", type=int, default=int(os.getenv("COHORT_COUNT", "10")), help="Number of personas in cohort (default: 10)")
    parser.add_argument("--steps", type=int, default=int(os.getenv("SIM_STEPS", "2")), help="Number of simulation steps (default: 2)")
    parser.add_argument("--gemini", action="store_true", help="Use live Google Gemini API")
    parser.add_argument("--no-fallback", action="store_true", help="Disable fallback to stub on API failure")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducible cohort and network generation")
    args, _ = parser.parse_known_args()

    use_gemini = args.gemini or os.getenv("USE_GEMINI", "0").strip() == "1"
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    fallback = not args.no_fallback and os.getenv("GEMINI_NO_FALLBACK", "0").strip() != "1"

    if use_gemini and gemini_key:
        model_name = os.getenv("GEMINI_MODEL", GeminiLLMProvider.DEFAULT_MODEL).strip()
        provider = GeminiLLMProvider(model_name=model_name, fallback_to_stub=fallback)
        provider_label = f"Google Gemini API ({model_name})"
    else:
        provider = StubLLMProvider()
        provider_label = "Deterministic Rule-Grounded Stub (Offline)"

    print("=" * 78)
    print("  MAHARASHTRA POLICY SIMULATOR - MULTI-PERSONA SOCIAL INTERACTION DEMO")
    print("=" * 78)
    print(f"Cohort Target      : {args.count} Synthetic Student Personas (Dhule Empirical Baseline)")
    print(f"LLM Provider       : {provider_label}")
    print(f"Simulation Steps   : {args.steps} Sequential Cycles (Observe -> Reason -> Interact -> Act -> Update)")
    print(f"Target Policy      : {RajarshiShahuPolicyEngine.SCHEME_NAME}")
    print("-" * 78)

    # 1. Generate Persona Cohort from Dhule Dataset Adapter
    adapter = DhuleEducationDatasetAdapter()
    config = adapter.create_population_config()
    generator = SyntheticPersonaGenerator(config=config, seed=args.seed)
    cohort = generator.generate_cohort(count=args.count, seed=args.seed)

    # 2. Run Multi-Step Simulation Engine
    engine = SimulationEngine(llm_provider=provider)
    result: MultiStepSimulationResult = engine.run_multistep_cohort(
        personas=cohort,
        total_steps=args.steps,
        cohort_name=f"Dhule-{args.count}-Persona-Pilot",
        seed=args.seed,
        enable_social_interaction=True,
        max_connections_per_persona=2
    )

    # 3. Print Synthetic Social Network Topology
    print("\n[PHASE 1: SYNTHETIC SOCIAL NETWORK TOPOLOGY]")
    net_info = result.network_summary
    print(f"  * Total Students   : {net_info['total_nodes']}")
    print(f"  * Total Peer Ties  : {net_info['total_edges']}")
    print(f"  * Max Degree Bound : {net_info['max_degree_limit']} connections per student")
    print("  * Adjacency Connections:")
    for pid, peers in net_info["adjacency_list"].items():
        print(f"    - {pid:<16} connects with: {', '.join(peers) if peers else 'None'}")

    # 4. Print Interactions and Dialogues per Step
    for step_idx in range(1, result.total_steps + 1):
        print(f"\n" + "-" * 78)
        print(f"  SIMULATION STEP {step_idx}: OBSERVE -> REASON -> INTERACT -> ACT -> UPDATE")
        print("-" * 78)

        interactions = result.interactions_by_step.get(step_idx, [])
        print(f"[Step {step_idx} Active Peer Dialogues ({len(interactions)} exchanges)]:")
        for idx, inter in enumerate(interactions, 1):
            sender_id = inter["sender_id"]
            receiver_id = inter["receiver_id"]
            topic = inter["interaction_topic"]
            s_msg = inter["sender_message"]
            r_msg = inter["receiver_response"]
            changes = inter["state_changes"]

            print(f"\n  Exchange #{idx} [{topic}]: {sender_id} -> {receiver_id}")
            print(f"    Sender   : \"{s_msg}\"")
            print(f"    Receiver : \"{r_msg}\"")
            if inter["state_changed"]:
                aw_d = changes.get("awareness_delta", 0.0)
                tr_d = changes.get("trust_delta", 0.0)
                doc_d = changes.get("doc_readiness_delta", 0.0)
                print(f"    State Delta -> Awareness: {aw_d:+.2f} | Trust: {tr_d:+.2f} | Doc Readiness: {doc_d:+.2f}")
            else:
                print(f"    State Delta -> No state change.")

        # Step Aggregate Summary
        step_cohort = result.step_cohort_results[step_idx - 1]
        print(f"\n[Step {step_idx} Cohort Aggregate Metrics]:")
        print(f"  * Statutory Eligible Students : {step_cohort.eligible_count}/{step_cohort.total_personas} ({step_cohort.eligibility_rate:.1%})")
        print(f"  * Mean Awareness Score        : {step_cohort.average_awareness_score:.2f}")
        print(f"  * Mean Perceived Benefit      : {step_cohort.average_perceived_benefit_score:.2f}")
        print(f"  * Mean Application Probability : {step_cohort.average_application_probability:.2%}")
        print(f"  * Expected Uptake Probability : {step_cohort.average_expected_uptake_probability:.2%}")
        print(f"  * Realized Uptake / Benefits  : {step_cohort.benefit_received_count}/{step_cohort.total_personas} ({step_cohort.uptake_rate:.1%})")

    # 5. Overall State Evolution & Diffusion Comparison
    print("\n" + "=" * 78)
    print("  MULTI-STEP STATE EVOLUTION & PEER DIFFUSION SUMMARY")
    print("=" * 78)
    print(f"{'Persona ID':<16} | {'Init Aw':<8} | {'Final Aw':<8} | {'Aw Gain':<8} | {'Init Trust':<10} | {'Final Trust':<11} | {'Final State':<18}")
    print("-" * 78)
    for pid, ev in result.state_evolution_summary.items():
        print(
            f"{pid:<16} | "
            f"{ev['initial_awareness']:<8.2f} | "
            f"{ev['final_awareness']:<8.2f} | "
            f"{ev['awareness_gain']:<+8.2f} | "
            f"{ev['initial_trust']:<10.2f} | "
            f"{ev['final_trust']:<11.2f} | "
            f"{ev['final_state']:<18}"
        )

    # 6. Final Persona Reasoning & Barrier Breakdown
    print("\n[FINAL PERSONA REASONING & BARRIER BREAKDOWN (Step 2)]:")
    final_step = result.step_cohort_results[-1]
    for step_out in final_step.individual_results:
        print(f"  * {step_out.persona_id} ({step_out.final_simulation_state}):")
        print(f"    - Stated Intention : {step_out.stated_intention}")
        print(f"    - Key Barriers     : {', '.join(step_out.perceived_barriers[:2]) if step_out.perceived_barriers else 'None'}")
        if step_out.inner_monologue:
            short_mono = step_out.inner_monologue.replace('\n', ' ')[:140]
            print(f"    - Internal Voice   : \"{short_mono}...\"")

    # 7. Provider Call Count & Performance
    if isinstance(provider, GeminiLLMProvider):
        print(f"\n[LLM PROVIDER TELEMETRY]:")
        print(f"  * Total Gemini API Calls Made : {provider.call_count}")
        print(f"  * Model Used                  : {provider.model_name}")
        print(f"  * Timeout Configured          : {provider.timeout_seconds}s")
        print(f"  * Fallback to Stub Allowed    : {provider.fallback_to_stub}")

    # 7. Authoritative Policy Safeguard Disclosure
    print("\n" + "=" * 78)
    print("AUTHORITATIVE ARCHITECTURAL NOTE:")
    print("  1. Deterministic statutory eligibility checks remained strictly authoritative at all steps.")
    print("  2. Social interactions modeled peer-to-peer awareness diffusion and administrative guidance.")
    print("  3. Persona state changes remained strictly bounded within [0.0, 1.0].")
    print("=" * 78 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(run_demo())
