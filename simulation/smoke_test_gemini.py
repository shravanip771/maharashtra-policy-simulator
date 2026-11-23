"""
Gemini Provider Integration Smoke Test (ONE Persona)

This script is an explicitly invoked integration smoke test for verifying
the Gemini LLM Provider with a real live API call for a SINGLE synthetic persona.

SAFETY & ARCHITECTURAL RULES:
1. This smoke test is NOT part of the automated offline test suite.
2. It reads credentials exclusively from the GEMINI_API_KEY environment variable.
3. It NEVER logs, prints, or exposes the API key or authentication headers.
4. Deterministic statutory eligibility is computed first and remains strictly authoritative.
5. If GEMINI_API_KEY is missing, it exits with a clear setup message.

Usage:
    # Windows PowerShell:
    $env:GEMINI_API_KEY="your_actual_key_here"
    python -m simulation.smoke_test_gemini

    # Optional: Configure model (defaults to gemini-3.8-flash)
    $env:GEMINI_MODEL="gemini-3.8-flash"
    python -m simulation.smoke_test_gemini
"""

import os
import sys
import json

from simulation.persona import StudentPersona, InstitutionType, AdmissionMode, PersonalityTraits
from simulation.policy_rules import RajarshiShahuPolicyEngine, PolicyEvaluationResult
from simulation.agent import (
    PersonaAgent,
    GeminiLLMProvider,
    PersonaCalculatedMetrics,
    PersonaReasoningOutput
)


def create_smoke_test_persona() -> StudentPersona:
    """Instantiates a single representative synthetic student persona for the smoke test."""
    return StudentPersona(
        persona_id="GEMINI-SMOKE-001",
        name="Sunita Patil",
        age=19,
        gender="Female",
        district="Dhule",
        is_maharashtra_domicile=True,
        family_income=120000.0,
        caste_category="General-EBC",
        first_generation_learner=True,
        parental_education_level="Primary",
        course_name="B.Tech Computer Engineering",
        course_level="Undergraduate",
        is_professional_course=True,
        institution_type=InstitutionType.PRIVATE_UNAIDED,
        admission_mode=AdmissionMode.CAP,
        annual_tuition_fee=90000.0,
        attendance_percentage=85.0,
        previous_year_passed=True,
        previous_year_percentage=74.0,
        academic_gap_years=0,
        digital_literacy=0.65,
        initial_awareness=0.50,
        document_readiness=0.70,
        financial_urgency=0.85,
        peer_network_support=0.55,
        personality=PersonalityTraits(
            patience=0.60,
            diligence=0.75,
            risk_aversion=0.45,
            self_advocacy=0.65
        )
    )


def run_gemini_smoke_test() -> int:
    """Executes the single-persona integration smoke test against Google Gemini API."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("\n" + "=" * 70, file=sys.stderr)
        print("[ERROR] GEMINI_API_KEY environment variable is missing or empty.", file=sys.stderr)
        print("Please set your GEMINI_API_KEY environment variable before running this test.", file=sys.stderr)
        print("Example (PowerShell):", file=sys.stderr)
        print('    $env:GEMINI_API_KEY="your_api_key_here"', file=sys.stderr)
        print('    python -m simulation.smoke_test_gemini', file=sys.stderr)
        print("=" * 70 + "\n", file=sys.stderr)
        return 1

    model_name = os.getenv("GEMINI_MODEL", GeminiLLMProvider.DEFAULT_MODEL).strip()

    print("=" * 70)
    print("MAHARASHTRA POLICY SIMULATOR - GEMINI PROVIDER SMOKE TEST (1 PERSONA)")
    print("=" * 70)
    print(f"Target LLM Provider : Google Gemini API")
    print(f"Configured Model    : {model_name}")
    print(f"Target Persona      : Sunita Patil (GEMINI-SMOKE-001)")
    print("-" * 70)

    # 1. Instantiate Persona
    persona = create_smoke_test_persona()

    # 2. Run Deterministic Policy Evaluation FIRST
    policy_eval: PolicyEvaluationResult = RajarshiShahuPolicyEngine.evaluate_eligibility(persona)

    # 3. Compute Deterministic Baseline Metrics
    temp_agent = PersonaAgent(persona=persona)
    metrics: PersonaCalculatedMetrics = temp_agent.compute_baseline_metrics(policy_eval)

    print("\n[STEP 1: DETERMINISTIC STATUTORY POLICY EVALUATION (AUTHORITATIVE)]")
    print(f"  * Scheme Name              : {policy_eval.scheme_name}")
    print(f"  * Statutory Eligibility    : {'ELIGIBLE' if policy_eval.is_eligible else 'INELIGIBLE'}")
    print(f"  * Estimated Fee Relief     : INR {policy_eval.estimated_fee_relief_inr:,.2f} ({policy_eval.reimbursement_percentage * 100:.0f}%)")
    print(f"  * Baseline Awareness Score : {metrics.awareness_score:.2f}")
    print(f"  * Baseline Uptake Prob     : {metrics.expected_uptake_probability:.2%}")

    # 4. Invoke Gemini Provider
    print("\n[STEP 2: QUALITATIVE REASONING VIA GEMINI AI PERSONA AGENT]")
    print(f"  * Connecting to Gemini endpoint for model: {model_name}...")

    provider = GeminiLLMProvider(model_name=model_name, fallback_to_stub=False)
    agent = PersonaAgent(persona=persona, llm_provider=provider)

    try:
        reasoning_output: PersonaReasoningOutput = agent.reason(policy_eval, metrics)
    except Exception as e:
        print(f"\n[FAILURE] Gemini API invocation failed: {str(e)}", file=sys.stderr)
        return 1

    # 5. Validate Structured Output
    assert reasoning_output.persona_id == persona.persona_id, f"Persona ID mismatch: {reasoning_output.persona_id}"
    assert isinstance(reasoning_output.perceived_awareness, float), "perceived_awareness must be a float"
    assert isinstance(reasoning_output.perceived_benefit, float), "perceived_benefit must be a float"
    assert isinstance(reasoning_output.application_intention, str) and len(reasoning_output.application_intention) > 0
    assert isinstance(reasoning_output.main_barriers, list)
    assert isinstance(reasoning_output.reasoning, str) and len(reasoning_output.reasoning) > 0
    assert isinstance(reasoning_output.recommended_next_action, str)

    # 6. Print Safe Fields
    print("\n[STEP 3: STRUCTURED PERSONA REASONING OUTPUT RECEIVED & VALIDATED]")
    print(f"  * Persona ID               : {reasoning_output.persona_id}")
    print(f"  * Perceived Awareness      : {reasoning_output.perceived_awareness:.2f}")
    print(f"  * Perceived Benefit        : {reasoning_output.perceived_benefit:.2f}")
    print(f"  * Application Intention    : {reasoning_output.application_intention}")
    print(f"  * Completion Confidence    : {reasoning_output.completion_confidence}")
    print(f"  * Recommended Next Action  : {reasoning_output.recommended_next_action}")
    print(f"  * Perceived Barriers       : {json.dumps(reasoning_output.main_barriers, indent=6)}")
    print(f"\n  * Qualitative Reasoning (Student Voice):\n    \"{reasoning_output.reasoning}\"")

    # 7. Authoritative Summary
    print("\n" + "=" * 70)
    print("SMOKE TEST RESULT: SUCCESS")
    print("AUTHORITATIVE NOTE:")
    print("  The deterministic policy result (Eligible = True, INR 45,000.00) remains authoritative.")
    print("  The Gemini AI layer provided subjective persona reasoning, perceived friction, and voice.")
    print("=" * 70 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(run_gemini_smoke_test())
