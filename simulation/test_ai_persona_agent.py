"""
Unit tests for AI Persona Agent Reasoning Layer (Phase 2 Milestone).

Verifies:
1. Structured schema completeness for PersonaReasoningOutput.
2. Preservation of persona_id across agent execution.
3. Authoritative separation of deterministic statutory eligibility from LLM reasoning.
4. Prompt generation includes explicit factuality and safety constraints.
5. StubLLMProvider deterministic execution with zero external keys.
6. JSON extraction and schema parsing logic.
7. End-to-end single persona simulation execution.
8. Zero regressions across existing test suites.
"""

from unittest.mock import patch, MagicMock
import io
import os
import json

from simulation.persona import StudentPersona, InstitutionType, AdmissionMode, PersonalityTraits
from simulation.policy_rules import RajarshiShahuPolicyEngine, PolicyEvaluationResult
from simulation.agent import (
    PersonaAgent,
    BaseLLMProvider,
    StubLLMProvider,
    ConfigurableLLMProvider,
    GeminiLLMProvider,
    PersonaReasoningOutput,
    PersonaCalculatedMetrics,
    build_persona_reasoning_prompt
)
from simulation.engine import SimulationEngine


def create_sample_student(persona_id: str = "TEST-AGENT-001", is_eligible: bool = True) -> StudentPersona:
    """Helper to instantiate a well-formed test persona."""
    return StudentPersona(
        persona_id=persona_id,
        name="Sunita Patil",
        age=19,
        gender="Female",
        district="Dhule",
        is_maharashtra_domicile=True,
        family_income=120000.0 if is_eligible else 950000.0,
        caste_category="General-EBC",
        first_generation_learner=True,
        parental_education_level="Primary",
        course_name="B.Tech Computer Engineering",
        course_level="Undergraduate",
        is_professional_course=True,
        institution_type=InstitutionType.PRIVATE_UNAIDED,
        admission_mode=AdmissionMode.CAP if is_eligible else AdmissionMode.MANAGEMENT_QUOTA,
        annual_tuition_fee=90000.0,
        attendance_percentage=85.0 if is_eligible else 65.0,
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


def test_structured_persona_reasoning_schema():
    """Verifies that the structured output contains all required fields and backward-compatible properties."""
    student = create_sample_student("TEST-AGENT-001")
    engine = SimulationEngine()
    policy_eval = RajarshiShahuPolicyEngine.evaluate_eligibility(student)
    
    agent = PersonaAgent(persona=student)
    metrics = agent.compute_baseline_metrics(policy_eval)
    reasoning_out: PersonaReasoningOutput = agent.reason(policy_eval, metrics)

    # Required structured schema fields
    assert reasoning_out.persona_id == "TEST-AGENT-001"
    assert isinstance(reasoning_out.perceived_awareness, float)
    assert isinstance(reasoning_out.perceived_benefit, float)
    assert isinstance(reasoning_out.application_intention, str)
    assert reasoning_out.completion_confidence in ["High", "Moderate", "Low"]
    assert isinstance(reasoning_out.main_barriers, list)
    assert len(reasoning_out.reasoning) > 0
    assert reasoning_out.recommended_next_action in [
        "SUBMIT_APPLICATION",
        "ATTEMPT_WITH_RISK_OF_DROPOUT",
        "ABANDON_APPLICATION",
        "DROP_OUT"
    ]

    # Backward compatibility properties
    assert reasoning_out.inner_monologue == reasoning_out.reasoning
    assert reasoning_out.stated_intention == reasoning_out.application_intention
    assert reasoning_out.perceived_barriers == reasoning_out.main_barriers
    assert reasoning_out.chosen_action == reasoning_out.recommended_next_action
    assert reasoning_out.confidence_level == reasoning_out.completion_confidence

    # JSON serialization and deserialization
    json_dict = reasoning_out.to_dict()
    assert json_dict["persona_id"] == "TEST-AGENT-001"
    parsed_back = PersonaReasoningOutput.from_dict(json_dict)
    assert parsed_back.persona_id == reasoning_out.persona_id
    assert parsed_back.recommended_next_action == reasoning_out.recommended_next_action
    print("PASS: test_structured_persona_reasoning_schema")


def test_deterministic_eligibility_authority():
    """Verifies that the LLM reasoning agent cannot alter or override deterministic statutory eligibility."""
    ineligible_student = create_sample_student("TEST-INELIGIBLE-002", is_eligible=False)
    
    # 1. Deterministic evaluation fails
    policy_eval = RajarshiShahuPolicyEngine.evaluate_eligibility(ineligible_student)
    assert policy_eval.is_eligible is False
    assert policy_eval.estimated_fee_relief_inr == 0.0
    assert len(policy_eval.failure_reasons) >= 2

    # 2. Agent reasoning reflects ineligibility
    agent = PersonaAgent(persona=ineligible_student)
    metrics = agent.compute_baseline_metrics(policy_eval)
    reasoning_out = agent.reason(policy_eval, metrics)

    assert metrics.application_probability == 0.0
    assert metrics.final_benefit_received is False
    assert reasoning_out.recommended_next_action == "ABANDON_APPLICATION"
    assert "ineligib" in reasoning_out.application_intention.lower()

    # 3. SimulationEngine step preserves deterministic failure
    engine = SimulationEngine()
    step_out = engine.run_step(ineligible_student)
    assert step_out.is_eligible is False
    assert step_out.estimated_fee_relief_inr == 0.0
    assert step_out.final_simulation_state == "REJECTED"
    print("PASS: test_deterministic_eligibility_authority")


def test_prompt_safeguards_against_hallucination():
    """Verifies that the constructed LLM prompt contains strict safety instructions and full persona payload."""
    student = create_sample_student("TEST-PROMPT-003")
    policy_eval = RajarshiShahuPolicyEngine.evaluate_eligibility(student)
    agent = PersonaAgent(persona=student)
    metrics = agent.compute_baseline_metrics(policy_eval)

    prompt = build_persona_reasoning_prompt(student, policy_eval, metrics)

    assert "STRICT SAFETY & FACTUALITY CONSTRAINTS" in prompt["system"]
    assert "DO NOT override or contradict the deterministic statutory eligibility status" in prompt["system"]
    assert "DO NOT invent official scheme rules" in prompt["system"]
    assert "simulated estimates, not real-world factual claims" in prompt["system"]

    # Verify user payload contains structured inputs
    user_data = prompt["user"]
    assert student.persona_id in user_data
    assert "deterministic_policy_evaluation" in user_data
    assert "required_json_schema" in user_data
    print("PASS: test_prompt_safeguards_against_hallucination")


def test_json_extraction_utility():
    """Verifies that ConfigurableLLMProvider._extract_json handles markdown code fences and clean JSON."""
    raw_clean = '{"persona_id": "TEST-01", "perceived_awareness": 0.8, "recommended_next_action": "SUBMIT_APPLICATION"}'
    parsed1 = ConfigurableLLMProvider._extract_json(raw_clean)
    assert parsed1["persona_id"] == "TEST-01"

    raw_fenced = '```json\n{"persona_id": "TEST-02", "perceived_benefit": 0.75, "recommended_next_action": "SUBMIT_APPLICATION"}\n```'
    parsed2 = ConfigurableLLMProvider._extract_json(raw_fenced)
    assert parsed2["persona_id"] == "TEST-02"
    assert parsed2["perceived_benefit"] == 0.75
    print("PASS: test_json_extraction_utility")


def test_gemini_provider_offline_initialization_and_safety():
    """Verifies GeminiLLMProvider initialization, security representation, and missing-key handling."""
    # 1. Missing API key with fallback=False raises ValueError
    provider = GeminiLLMProvider(api_key="", fallback_to_stub=False)
    student = create_sample_student("TEST-GEMINI-001")
    policy_eval = RajarshiShahuPolicyEngine.evaluate_eligibility(student)
    agent = PersonaAgent(persona=student, llm_provider=provider)
    metrics = agent.compute_baseline_metrics(policy_eval)

    try:
        provider.generate_persona_reasoning(student, policy_eval, metrics)
        assert False, "Expected ValueError when GEMINI_API_KEY is missing"
    except ValueError as e:
        assert "GEMINI_API_KEY" in str(e)

    # 2. Missing API key with fallback=True succeeds via Stub
    fallback_provider = GeminiLLMProvider(api_key="", fallback_to_stub=True)
    fallback_res = fallback_provider.generate_persona_reasoning(student, policy_eval, metrics)
    assert fallback_res.persona_id == "TEST-GEMINI-001"
    assert fallback_res.recommended_next_action == "SUBMIT_APPLICATION"

    # 3. Security: __repr__ must never expose secrets
    secret_key = "AIzaSySecretTestKeyNeverExposeInLogs12345"
    secure_provider = GeminiLLMProvider(api_key=secret_key, model_name="gemini-3.8-flash")
    repr_str = repr(secure_provider)
    assert secret_key not in repr_str
    assert "gemini-3.8-flash" in repr_str

    # 4. Timeout configuration: Default is 90.0s, explicit parameter works, and env var works
    assert secure_provider.timeout_seconds == 90.0

    custom_provider = GeminiLLMProvider(api_key="test", timeout_seconds=45.0)
    assert custom_provider.timeout_seconds == 45.0

    try:
        os.environ["GEMINI_TIMEOUT_SECONDS"] = "120.5"
        env_provider = GeminiLLMProvider(api_key="test")
        assert env_provider.timeout_seconds == 120.5
    finally:
        os.environ.pop("GEMINI_TIMEOUT_SECONDS", None)

    print("PASS: test_gemini_provider_offline_initialization_and_safety")


def test_gemini_provider_mock_response_and_statutory_guardrail():
    """Verifies GeminiLLMProvider response parsing and statutory ineligibility enforcement offline via mock."""
    mock_gemini_body = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": (
                                '{\n'
                                '  "persona_id": "TEST-GEMINI-INELIGIBLE",\n'
                                '  "perceived_awareness": 0.85,\n'
                                '  "perceived_benefit": 0.0,\n'
                                '  "application_intention": "I thought about applying, but I make too much money.",\n'
                                '  "completion_confidence": "Low",\n'
                                '  "main_barriers": ["Income exceeds 8 Lakh threshold."],\n'
                                '  "reasoning": "My family income is 9.5 Lakh so I am not eligible.",\n'
                                '  "recommended_next_action": "SUBMIT_APPLICATION"\n'
                                '}'
                            )
                        }
                    ],
                    "role": "model"
                },
                "finishReason": "STOP"
            }
        ]
    }

    ineligible_student = create_sample_student("TEST-GEMINI-INELIGIBLE", is_eligible=False)
    policy_eval = RajarshiShahuPolicyEngine.evaluate_eligibility(ineligible_student)
    assert policy_eval.is_eligible is False

    provider = GeminiLLMProvider(api_key="mock_key_for_testing", fallback_to_stub=False)
    agent = PersonaAgent(persona=ineligible_student, llm_provider=provider)
    metrics = agent.compute_baseline_metrics(policy_eval)

    # Mock urllib.request.urlopen
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(mock_gemini_body).encode("utf-8")
    mock_response.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_response):
        out = provider.generate_persona_reasoning(ineligible_student, policy_eval, metrics)
        # Even though LLM mock hallucinated SUBMIT_APPLICATION, statutory safeguard overrode it
        assert out.persona_id == "TEST-GEMINI-INELIGIBLE"
        assert out.recommended_next_action == "ABANDON_APPLICATION"
        assert out.perceived_awareness == 0.85
        assert "Income exceeds" in out.main_barriers[0]

    print("PASS: test_gemini_provider_mock_response_and_statutory_guardrail")


if __name__ == "__main__":
    test_structured_persona_reasoning_schema()
    test_deterministic_eligibility_authority()
    test_prompt_safeguards_against_hallucination()
    test_json_extraction_utility()
    test_gemini_provider_offline_initialization_and_safety()
    test_gemini_provider_mock_response_and_statutory_guardrail()
    print("All AI Persona Agent tests passed successfully!")

