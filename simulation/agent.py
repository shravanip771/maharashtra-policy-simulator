"""
AI Persona Agent Module (Phase 2 AI Reasoning Layer)

This module implements the AI Persona Agent interface for qualitative decision-making,
cognitive deliberation, barrier identification, and natural-language explanations.

Core Architectural Separation:
- DETERMINISTIC CODE (Policy Engine & Metrics):
  Statutory eligibility, policy rule checks, fee relief calculation, numerical probabilities,
  and state transitions.
- AI / LLM LAYER (Persona Reasoning):
  Persona voice perspective, subjective concerns, perceived friction, application intentions,
  and contextual natural-language explanations.

SAFETY MANDATE:
The prompt explicitly constrains the LLM so it CANNOT override statutory eligibility or
hallucinate official government rules.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional
import json
import os
import re
import time
import urllib.request
import urllib.error

from simulation.persona import StudentPersona, SimulationState
from simulation.policy_rules import PolicyEvaluationResult, RajarshiShahuPolicyEngine


@dataclass
class PersonaCalculatedMetrics:
    """Explicit, transparent deterministic & probabilistic baseline metrics."""
    awareness_score: float              # 0.0 to 1.0
    perceived_benefit_score: float      # 0.0 to 1.0 (utility of fee concession vs. hassle)
    application_probability: float      # 0.0 to 1.0
    completion_probability: float       # 0.0 to 1.0
    expected_uptake_probability: float  # 0.0 to 1.0 (eligibility * application * completion)
    will_attempt_application: bool
    will_complete_application: bool
    final_benefit_received: bool


@dataclass
class PersonaReasoningOutput:
    """
    Structured persona cognitive & contextual response produced by the reasoning agent.
    Maintains both modern structured schema fields and legacy properties for 100% backward compatibility.
    """
    persona_id: str
    perceived_awareness: float          # Subjective awareness score (0.0 to 1.0)
    perceived_benefit: float            # Subjective perceived utility of fee concession (0.0 to 1.0)
    application_intention: str          # Stated decision regarding application submission
    completion_confidence: str          # "High", "Moderate", "Low"
    main_barriers: List[str]            # Primary perceived administrative or personal hurdles
    reasoning: str                      # Detailed first-person cognitive deliberation / monologue
    recommended_next_action: str        # Action taken (SUBMIT_APPLICATION, ATTEMPT_WITH_RISK_OF_DROPOUT, ABANDON_APPLICATION, DROP_OUT)

    # Backward compatibility accessors for Phase 1 code
    @property
    def inner_monologue(self) -> str:
        return self.reasoning

    @property
    def stated_intention(self) -> str:
        return self.application_intention

    @property
    def perceived_barriers(self) -> List[str]:
        return self.main_barriers

    @property
    def chosen_action(self) -> str:
        return self.recommended_next_action

    @property
    def confidence_level(self) -> str:
        return self.completion_confidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "persona_id": self.persona_id,
            "perceived_awareness": self.perceived_awareness,
            "perceived_benefit": self.perceived_benefit,
            "application_intention": self.application_intention,
            "completion_confidence": self.completion_confidence,
            "main_barriers": self.main_barriers,
            "reasoning": self.reasoning,
            "recommended_next_action": self.recommended_next_action
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], fallback_id: str = "UNKNOWN-STU") -> "PersonaReasoningOutput":
        """Parses dictionary into PersonaReasoningOutput with robust fallback defaults."""
        return cls(
            persona_id=str(data.get("persona_id", fallback_id)),
            perceived_awareness=float(data.get("perceived_awareness", data.get("awareness_score", 0.5))),
            perceived_benefit=float(data.get("perceived_benefit", data.get("perceived_benefit_score", 0.5))),
            application_intention=str(data.get("application_intention", data.get("stated_intention", "Evaluating options."))),
            completion_confidence=str(data.get("completion_confidence", data.get("confidence_level", "Moderate"))),
            main_barriers=list(data.get("main_barriers", data.get("perceived_barriers", []))),
            reasoning=str(data.get("reasoning", data.get("inner_monologue", ""))),
            recommended_next_action=str(data.get("recommended_next_action", data.get("chosen_action", "EVALUATE")))
        )


def build_persona_reasoning_prompt(
    persona: StudentPersona,
    policy_eval: PolicyEvaluationResult,
    metrics: PersonaCalculatedMetrics
) -> Dict[str, str]:
    """
    Constructs the system and user prompt with explicit safeguards preventing
    hallucination of statutory eligibility or official scheme rules.
    """
    system_prompt = (
        "You are an AI Persona Reasoning Simulator representing college students navigating Maharashtra "
        "government higher education scholarship schemes (specifically MahaDBT).\n\n"
        "STRICT SAFETY & FACTUALITY CONSTRAINTS:\n"
        "1. Statutory eligibility and fee relief amounts are deterministically calculated by the rule engine.\n"
        "   - DO NOT override or contradict the deterministic statutory eligibility status.\n"
        "   - DO NOT invent official scheme rules, income caps, or government policy clauses.\n"
        "2. Your task is strictly to simulate the individual student's qualitative perspective, cognitive reaction, "
        "   bureaucratic friction, and emotional voice given their socio-economic context.\n"
        "3. Behavioural outputs are simulated estimates, not real-world factual claims about specific citizens.\n"
        "4. You MUST respond with ONLY a valid JSON object matching the requested schema. Do not add markdown commentary outside the JSON."
    )

    user_payload = {
        "persona_profile": {
            "persona_id": persona.persona_id,
            "name": persona.name,
            "age": persona.age,
            "gender": persona.gender,
            "district": persona.district,
            "caste_category": persona.caste_category,
            "annual_family_income_inr": persona.family_income,
            "first_generation_learner": persona.first_generation_learner,
            "parental_education": persona.parental_education_level,
            "course": persona.course_name,
            "course_level": persona.course_level,
            "institution_type": persona.institution_type.value,
            "admission_mode": persona.admission_mode.value,
            "annual_tuition_fee_inr": persona.annual_tuition_fee,
            "attendance_percentage": persona.attendance_percentage,
            "previous_year_passed": persona.previous_year_passed,
            "digital_literacy_score": persona.digital_literacy,
            "initial_awareness_score": persona.initial_awareness,
            "document_readiness_score": persona.document_readiness,
            "financial_urgency_score": persona.financial_urgency,
            "peer_network_support_score": persona.peer_network_support,
            "personality_traits": asdict(persona.personality)
        },
        "deterministic_policy_evaluation": {
            "scheme_name": policy_eval.scheme_name,
            "is_eligible": policy_eval.is_eligible,
            "statutory_failure_reasons": policy_eval.failure_reasons,
            "statutory_notes": policy_eval.statutory_notes,
            "estimated_fee_relief_inr": policy_eval.estimated_fee_relief_inr,
            "reimbursement_percentage": policy_eval.reimbursement_percentage
        },
        "deterministic_calculated_metrics": {
            "awareness_score": metrics.awareness_score,
            "perceived_benefit_score": metrics.perceived_benefit_score,
            "application_probability": metrics.application_probability,
            "completion_probability": metrics.completion_probability,
            "will_attempt_application": metrics.will_attempt_application,
            "will_complete_application": metrics.will_complete_application
        },
        "required_json_schema": {
            "persona_id": persona.persona_id,
            "perceived_awareness": "float (0.0 to 1.0)",
            "perceived_benefit": "float (0.0 to 1.0)",
            "application_intention": "string (clear sentence stating if and how student will proceed)",
            "completion_confidence": "string (High, Moderate, or Low)",
            "main_barriers": ["list of specific administrative/personal hurdles"],
            "reasoning": "string (first-person internal monologue in student's voice)",
            "recommended_next_action": "string (SUBMIT_APPLICATION | ATTEMPT_WITH_RISK_OF_DROPOUT | ABANDON_APPLICATION | DROP_OUT)"
        }
    }

    return {
        "system": system_prompt,
        "user": json.dumps(user_payload, indent=2)
    }


@dataclass
class PersonaInteractionOutput:
    """Structured dialogue outcome from a peer-to-peer interaction."""
    sender_id: str
    receiver_id: str
    topic: str
    sender_message: str
    receiver_response: str
    interaction_summary: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        fallback_sender: str = "SENDER",
        fallback_receiver: str = "RECEIVER",
        fallback_topic: str = "SCHEME_AWARENESS"
    ) -> "PersonaInteractionOutput":
        return cls(
            sender_id=str(data.get("sender_id", fallback_sender)),
            receiver_id=str(data.get("receiver_id", fallback_receiver)),
            topic=str(data.get("topic", fallback_topic)),
            sender_message=str(data.get("sender_message", "Hello, let us discuss our scholarship application options.")),
            receiver_response=str(data.get("receiver_response", "Thanks for sharing that information.")),
            interaction_summary=str(data.get("interaction_summary", "Shared information regarding college fee concession."))
        )


def build_peer_interaction_prompt(
    sender: StudentPersona,
    sender_eval: PolicyEvaluationResult,
    receiver: StudentPersona,
    receiver_eval: PolicyEvaluationResult,
    topic: str,
    step_index: int
) -> Dict[str, str]:
    """
    Constructs the prompt for peer-to-peer dialogue between two students.
    Explicitly constrains against inventing government policies and enforces uncertainty expression.
    """
    system_prompt = (
        "You are an AI Persona Conversation Simulator for college students in Maharashtra discussing "
        "government higher education scholarships (specifically MahaDBT Rajarshi Chhatrapati Shahu Maharaj scheme).\n\n"
        "STRICT SAFETY & GROUNDING CONSTRAINTS:\n"
        "1. Deterministic Rule Authority: Statutory eligibility criteria and fee relief calculations are fixed by the policy engine.\n"
        "   - Do NOT invent official statutory clauses, income caps, or universal reimbursement percentages.\n"
        "2. No Universal 50% Claims: Fee relief percentage varies across departments and schemes. Our simulation models a configurable PoC fee relief estimate.\n"
        "   - Do NOT claim that 50% is a universal official statutory percentage for all students.\n"
        "3. No Invented Local Operational Claims: Do NOT invent specific local office crowds, queues, named officers, or unverified operational facts.\n"
        "   - Frame administrative friction as general student beliefs, experiences, or hearsay (e.g., 'I heard getting income certificate renewed can take time').\n"
        "4. No Positive Framing of Zero Benefit: If estimated fee relief is INR 0 or the student is ineligible, do NOT frame receiving zero as a positive financial gain.\n"
        "5. Express Uncertainty Authentically: If an official rule or deadline is unknown, express realistic student uncertainty rather than inventing facts.\n"
        "6. Ground Dialogue in Attributes: Keep messages grounded in the sender and receiver's district, course, income, and readiness scores.\n"
        "7. Output MUST be a valid JSON object matching the requested schema."
    )

    user_payload = {
        "simulation_step": step_index,
        "interaction_topic": topic,
        "sender_profile": {
            "persona_id": sender.persona_id,
            "name": sender.name,
            "district": sender.district,
            "course": sender.course_name,
            "institution_type": sender.institution_type.value,
            "annual_family_income_inr": sender.family_income,
            "awareness_score": sender.initial_awareness,
            "document_readiness_score": sender.document_readiness,
            "is_statutorily_eligible": sender_eval.is_eligible,
            "estimated_fee_relief_inr": sender_eval.estimated_fee_relief_inr
        },
        "receiver_profile": {
            "persona_id": receiver.persona_id,
            "name": receiver.name,
            "district": receiver.district,
            "course": receiver.course_name,
            "institution_type": receiver.institution_type.value,
            "annual_family_income_inr": receiver.family_income,
            "awareness_score": receiver.initial_awareness,
            "document_readiness_score": receiver.document_readiness,
            "institutional_trust_score": receiver.institutional_trust,
            "is_statutorily_eligible": receiver_eval.is_eligible,
            "personality": asdict(receiver.personality)
        },
        "required_json_schema": {
            "sender_id": sender.persona_id,
            "receiver_id": receiver.persona_id,
            "topic": topic,
            "sender_message": "string (conversational message from sender in authentic student voice)",
            "receiver_response": "string (conversational response from receiver reflecting their personality)",
            "interaction_summary": "string (one-sentence factual summary of the exchange)"
        }
    }

    return {
        "system": system_prompt,
        "user": json.dumps(user_payload, indent=2)
    }


class BaseLLMProvider(ABC):
    """Abstract interface for LLM reasoning backend (Local Ollama, cloud API, or stub)."""
    @abstractmethod
    def generate_persona_reasoning(
        self,
        persona: StudentPersona,
        policy_eval: PolicyEvaluationResult,
        metrics: PersonaCalculatedMetrics
    ) -> PersonaReasoningOutput:
        pass

    @abstractmethod
    def generate_peer_interaction(
        self,
        sender: StudentPersona,
        sender_eval: PolicyEvaluationResult,
        receiver: StudentPersona,
        receiver_eval: PolicyEvaluationResult,
        topic: str,
        step_index: int
    ) -> PersonaInteractionOutput:
        pass


class StubLLMProvider(BaseLLMProvider):
    """
    Deterministic rule-driven stub provider.
    Produces high-fidelity, persona-grounded structured reasoning without requiring external API keys.
    """
    def generate_persona_reasoning(
        self,
        persona: StudentPersona,
        policy_eval: PolicyEvaluationResult,
        metrics: PersonaCalculatedMetrics
    ) -> PersonaReasoningOutput:
        barriers: List[str] = []

        # Identify perceived barriers based on persona attributes
        if persona.digital_literacy < 0.5:
            barriers.append("Struggles with MahaDBT online document scanning, portal upload errors, and OTP verification.")
        if persona.document_readiness < 0.6:
            barriers.append("Delays in procuring valid Tehsildar Income Certificate / Domicile Certificate from Setu Kendra.")
        if persona.first_generation_learner and persona.peer_network_support < 0.4:
            barriers.append("Lack of guidance at home or college regarding scheme deadlines and form scrutiny.")
        if persona.family_income > RajarshiShahuPolicyEngine.MAX_INCOME_LIMIT:
            barriers.append(f"Ineligible: Family income INR {persona.family_income:,.0f} exceeds INR 8 Lakh ceiling.")
        if not persona.is_maharashtra_domicile:
            barriers.append("Ineligible: Lack of Maharashtra domicile.")
        if not policy_eval.is_eligible and len(policy_eval.failure_reasons) > 0:
            barriers.extend(policy_eval.failure_reasons)

        if not barriers:
            barriers.append("Minimal barriers: Active college support and all certificates readily available.")

        # Construct persona voice monologue
        if not policy_eval.is_eligible:
            reasoning = (
                f"I looked into the Rajarshi Shahu EBC scholarship for my {persona.course_name} fees (INR {persona.annual_tuition_fee:,.0f}), "
                f"but realized I don't qualify because: {', '.join(policy_eval.failure_reasons)}. "
                f"I will have to explore other education loans or institutional aid."
            )
            intention = "Will not apply due to statutory ineligibility."
            action = "ABANDON_APPLICATION"
            confidence = "High"
        elif metrics.will_complete_application:
            reasoning = (
                f"Getting tuition fee reimbursement (estimated at INR {policy_eval.estimated_fee_relief_inr:,.0f} in this simulation) will drastically ease my family's financial burden. "
                f"With annual family income at INR {persona.family_income:,.0f}, this scholarship is critical for me to continue my studies. "
                f"I have gathered my certificates and will submit my application on MahaDBT."
            )
            intention = "Apply immediately and track status through college scrutiny officer."
            action = "SUBMIT_APPLICATION"
            confidence = "High" if metrics.completion_probability > 0.75 else "Moderate"
        elif metrics.will_attempt_application:
            reasoning = (
                f"I know I am eligible for an estimated INR {policy_eval.estimated_fee_relief_inr:,.0f} relief, and I really need it. "
                f"However, getting the income certificate renewed and dealing with the cyber cafe MahaDBT upload is intimidating. "
                f"I want to apply, but I might get stuck during document re-upload rounds."
            )
            intention = "Try to apply, but need assistance from friends or college desk."
            action = "ATTEMPT_WITH_RISK_OF_DROPOUT"
            confidence = "Moderate"
        else:
            reasoning = (
                f"I heard about the fee concession, but with my current lack of documentation and information, "
                f"the administrative process feels overwhelming. Without clear guidance, I cannot complete it before the deadline."
            )
            intention = "Postpone or drop out of application process."
            action = "DROP_OUT"
            confidence = "Low"
            
        return PersonaReasoningOutput(
            persona_id=persona.persona_id,
            perceived_awareness=metrics.awareness_score,
            perceived_benefit=metrics.perceived_benefit_score,
            application_intention=intention,
            completion_confidence=confidence,
            main_barriers=barriers,
            reasoning=reasoning,
            recommended_next_action=action
        )

    def generate_peer_interaction(
        self,
        sender: StudentPersona,
        sender_eval: PolicyEvaluationResult,
        receiver: StudentPersona,
        receiver_eval: PolicyEvaluationResult,
        topic: str,
        step_index: int
    ) -> PersonaInteractionOutput:
        """
        Deterministic, persona-grounded peer conversation stub.
        Enforces strict grounding, avoids universal statutory claims, and prevents
        positive framing of zero benefit or invented operational facts.
        """
        topic_str = str(topic).upper()

        if "AWARENESS" in topic_str:
            sender_msg = (
                f"Hey {receiver.name}, have you checked the Rajarshi Shahu EBC scholarship on MahaDBT? "
                f"If family income is under the statutory limit and admission was through CAP, eligible students can receive tuition fee reimbursement."
            )
            if receiver_eval.is_eligible and receiver_eval.estimated_fee_relief_inr > 0:
                receiver_reply = (
                    f"Thanks {sender.name}! For my {receiver.course_name} fees (INR {receiver.annual_tuition_fee:,.0f}), "
                    f"the estimated fee relief of INR {receiver_eval.estimated_fee_relief_inr:,.0f} would be a massive help. I'm going to start gathering my certificates."
                )
            else:
                receiver_reply = (
                    f"Thanks for letting me know, {sender.name}. I checked my details earlier, but based on my admission or income criteria, I don't qualify. "
                    f"Hope your application goes smoothly!"
                )
            summary = f"{sender.name} informed {receiver.name} about potential tuition fee relief under the Rajarshi Shahu EBC scholarship."

        elif "GUIDANCE" in topic_str:
            sender_msg = (
                f"When applying on MahaDBT, I heard it helps to scan income and domicile certificates clearly before heading to the portal or cyber cafe."
            )
            receiver_reply = (
                f"Good tip! My digital literacy is around {receiver.digital_literacy:.0%}, so having my certificates pre-scanned should help avoid upload issues."
            )
            summary = f"{sender.name} shared practical document scanning advice with {receiver.name}."

        elif "HURDLE" in topic_str:
            sender_msg = (
                f"I heard the certificate renewal and verification process can take time, so it is best to start early before college scrutiny closes."
            )
            receiver_reply = (
                f"Thanks for the reminder. I will try to sort out my income and domicile paperwork early so it doesn't delay my application."
            )
            summary = f"{sender.name} and {receiver.name} discussed starting the document gathering process early to avoid administrative delays."

        else: # TRUST_AND_DISCOURAGEMENT or default
            sender_msg = (
                f"A few seniors mentioned that DBT fee disbursements can sometimes take time to reflect in bank accounts."
            )
            if receiver_eval.is_eligible and receiver_eval.estimated_fee_relief_inr > 0:
                receiver_reply = (
                    f"Even if there are disbursement delays, receiving the estimated INR {receiver_eval.estimated_fee_relief_inr:,.0f} relief is still critical for continuing my studies."
                )
            else:
                receiver_reply = (
                    f"Since I'm not eligible for fee relief, disbursement delays won't affect me, but I hope those who qualify receive their funds without issues."
                )
            summary = f"{sender.name} shared concerns over disbursement timelines, which {receiver.name} evaluated in context of their eligibility."

        return PersonaInteractionOutput(
            sender_id=sender.persona_id,
            receiver_id=receiver.persona_id,
            topic=topic,
            sender_message=sender_msg,
            receiver_response=receiver_reply,
            interaction_summary=summary
        )


class ConfigurableLLMProvider(BaseLLMProvider):
    """
    HTTP-based LLM Provider for local models (Ollama / LM Studio) or OpenAI-compatible APIs.
    Reads credentials strictly from environment variables or explicit parameters.
    Does NOT require external SDK dependencies (uses standard library urllib).
    """

    def __init__(
        self,
        api_base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: float = 30.0,
        fallback_to_stub: bool = True
    ):
        self.api_base_url = api_base_url or os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
        self.api_key = api_key or os.getenv("LLM_API_KEY", "")
        self.model_name = model_name or os.getenv("LLM_MODEL", "llama3")
        self.timeout_seconds = timeout_seconds
        self.fallback_to_stub = fallback_to_stub
        self._stub_fallback = StubLLMProvider()

    def generate_persona_reasoning(
        self,
        persona: StudentPersona,
        policy_eval: PolicyEvaluationResult,
        metrics: PersonaCalculatedMetrics
    ) -> PersonaReasoningOutput:
        """
        Sends structured prompt to the configured LLM endpoint and parses JSON output.
        Falls back gracefully to StubLLMProvider if network/endpoint is unavailable.
        """
        prompt = build_persona_reasoning_prompt(persona, policy_eval, metrics)
        endpoint = f"{self.api_base_url.rstrip('/')}/chat/completions"

        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": prompt["system"]},
                {"role": "user", "content": prompt["user"]}
            ],
            "temperature": 0.3,
            "response_format": {"type": "json_object"}
        }

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(endpoint, data=req_data, headers=headers, method="POST")

            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                res_body = response.read().decode("utf-8")
                res_json = json.loads(res_body)

                content = res_json["choices"][0]["message"]["content"]
                parsed_dict = self._extract_json(content)
                return PersonaReasoningOutput.from_dict(parsed_dict, fallback_id=persona.persona_id)

        except Exception as e:
            if self.fallback_to_stub:
                return self._stub_fallback.generate_persona_reasoning(persona, policy_eval, metrics)
            raise RuntimeError(f"ConfigurableLLMProvider failed to connect to {endpoint}: {str(e)}") from e

    def generate_peer_interaction(
        self,
        sender: StudentPersona,
        sender_eval: PolicyEvaluationResult,
        receiver: StudentPersona,
        receiver_eval: PolicyEvaluationResult,
        topic: str,
        step_index: int
    ) -> PersonaInteractionOutput:
        """
        Sends peer dialogue prompt to OpenAI-compatible endpoint. Falls back to stub.
        """
        prompt = build_peer_interaction_prompt(sender, sender_eval, receiver, receiver_eval, topic, step_index)
        endpoint = f"{self.api_base_url.rstrip('/')}/chat/completions"

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": prompt["system"]},
                {"role": "user", "content": prompt["user"]}
            ],
            "temperature": 0.4,
            "response_format": {"type": "json_object"}
        }

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(endpoint, data=req_data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                res_body = response.read().decode("utf-8")
                res_json = json.loads(res_body)
                content = res_json["choices"][0]["message"]["content"]
                parsed_dict = self._extract_json(content)
                return PersonaInteractionOutput.from_dict(
                    parsed_dict,
                    fallback_sender=sender.persona_id,
                    fallback_receiver=receiver.persona_id,
                    fallback_topic=topic
                )
        except Exception:
            if self.fallback_to_stub:
                return self._stub_fallback.generate_peer_interaction(
                    sender, sender_eval, receiver, receiver_eval, topic, step_index
                )
            raise

    @staticmethod
    def _extract_json(raw_text: str) -> Dict[str, Any]:
        """Extracts JSON object from LLM response text, stripping markdown code fences."""
        raw_text = raw_text.strip()
        # Strip ```json ... ``` code fence if present
        if raw_text.startswith("```"):
            raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text, flags=re.IGNORECASE)
            raw_text = re.sub(r"\s*```$", "", raw_text)

        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            # Fallback regex search for outer braces
            match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            raise ValueError(f"Could not parse valid JSON from LLM output: {raw_text[:200]}")


class GeminiLLMProvider(BaseLLMProvider):
    """
    Official Google Gemini API Provider for AI Persona Agent qualitative reasoning.

    Security & Architecture:
    - Reads API credentials exclusively from the GEMINI_API_KEY environment variable (or explicit parameter).
    - NEVER prints, logs, or exposes the API key in outputs, errors, or stack traces.
    - Uses lightweight standard library HTTP (urllib.request) without external SDK dependencies.
    - Model name is configurable via GEMINI_MODEL env var (defaults to 'gemini-3.8-flash').
    - Strictly enforces structured PersonaReasoningOutput and statutory eligibility separation.
    """

    DEFAULT_MODEL: str = "gemini-3.8-flash"
    DEFAULT_API_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/models"
    DEFAULT_TIMEOUT_SECONDS: float = 90.0

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        api_base_url: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        fallback_to_stub: bool = False
    ):
        # Credentials are read ONLY from GEMINI_API_KEY environment variable if not passed directly
        self._api_key = (api_key if api_key is not None else os.getenv("GEMINI_API_KEY", "")).strip()
        self.model_name = (model_name or os.getenv("GEMINI_MODEL", self.DEFAULT_MODEL)).strip()
        self.api_base_url = (api_base_url or os.getenv("GEMINI_BASE_URL", self.DEFAULT_API_BASE_URL)).rstrip('/')

        # Timeout resolution: explicit parameter -> GEMINI_TIMEOUT_SECONDS env var -> DEFAULT_TIMEOUT_SECONDS (90.0)
        if timeout_seconds is not None:
            self.timeout_seconds = float(timeout_seconds)
        else:
            env_timeout = os.getenv("GEMINI_TIMEOUT_SECONDS", "").strip()
            self.timeout_seconds = float(env_timeout) if env_timeout else self.DEFAULT_TIMEOUT_SECONDS

        self.fallback_to_stub = fallback_to_stub
        self._stub_fallback = StubLLMProvider()
        self.call_count: int = 0

    def __repr__(self) -> str:
        # Never expose API key in object representation
        return f"GeminiLLMProvider(model_name='{self.model_name}', timeout_seconds={self.timeout_seconds}, fallback_to_stub={self.fallback_to_stub})"

    def generate_persona_reasoning(
        self,
        persona: StudentPersona,
        policy_eval: PolicyEvaluationResult,
        metrics: PersonaCalculatedMetrics
    ) -> PersonaReasoningOutput:
        """
        Sends persona context & deterministic policy evaluation to Gemini generateContent endpoint,
        validates the structured JSON response, and returns PersonaReasoningOutput.
        """
        if not self._api_key:
            if self.fallback_to_stub:
                return self._stub_fallback.generate_persona_reasoning(persona, policy_eval, metrics)
            raise ValueError(
                "GEMINI_API_KEY environment variable is missing or empty. "
                "Please configure GEMINI_API_KEY to use GeminiLLMProvider."
            )

        prompt = build_persona_reasoning_prompt(persona, policy_eval, metrics)
        endpoint = f"{self.api_base_url}/{self.model_name}:generateContent"

        # Headers using standard x-goog-api-key header (prevents key leakage in URL logs)
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self._api_key
        }

        # Gemini REST payload with JSON response constraint
        payload = {
            "system_instruction": {
                "parts": [{"text": prompt["system"]}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt["user"]}]
                }
            ],
            "generationConfig": {
                "temperature": 0.3,
                "responseMimeType": "application/json"
            }
        }

        max_retries = 3
        backoff_seconds = 2.0

        for attempt in range(1, max_retries + 1):
            try:
                self.call_count += 1
                req_data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(endpoint, data=req_data, headers=headers, method="POST")

                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                    res_body = response.read().decode("utf-8")
                    res_json = json.loads(res_body)

                    candidates = res_json.get("candidates", [])
                    if not candidates:
                        raise ValueError("Gemini API returned an empty candidates list.")

                    content_parts = candidates[0].get("content", {}).get("parts", [])
                    if not content_parts or "text" not in content_parts[0]:
                        raise ValueError("Gemini response candidate missing text content.")

                    raw_text = content_parts[0]["text"]
                    parsed_dict = ConfigurableLLMProvider._extract_json(raw_text)

                    # Validate structured response schema
                    output = PersonaReasoningOutput.from_dict(parsed_dict, fallback_id=persona.persona_id)

                    # Statutory guardrail: Never allow LLM to override deterministic statutory ineligibility
                    if not policy_eval.is_eligible and output.recommended_next_action == "SUBMIT_APPLICATION":
                        output.recommended_next_action = "ABANDON_APPLICATION"

                    return output

            except urllib.error.HTTPError as e:
                # Retry on transient server busy/rate limit errors
                if e.code in [503, 429] and attempt < max_retries:
                    time.sleep(backoff_seconds * attempt)
                    continue
                if self.fallback_to_stub:
                    return self._stub_fallback.generate_persona_reasoning(persona, policy_eval, metrics)
                error_details = ""
                try:
                    error_details = e.read().decode("utf-8")
                except Exception:
                    pass
                raise RuntimeError(
                    f"Gemini API request failed with HTTP {e.code} ({e.reason}) for model '{self.model_name}'. "
                    f"Details: {error_details[:250]}"
                ) from None
            except Exception as e:
                if self.fallback_to_stub:
                    return self._stub_fallback.generate_persona_reasoning(persona, policy_eval, metrics)
                raise RuntimeError(f"GeminiLLMProvider failed: {str(e)}") from None

    def generate_peer_interaction(
        self,
        sender: StudentPersona,
        sender_eval: PolicyEvaluationResult,
        receiver: StudentPersona,
        receiver_eval: PolicyEvaluationResult,
        topic: str,
        step_index: int
    ) -> PersonaInteractionOutput:
        """
        Sends peer interaction dialogue prompt to Gemini API with JSON mode. Falls back to stub.
        """
        if not self._api_key:
            if self.fallback_to_stub:
                return self._stub_fallback.generate_peer_interaction(
                    sender, sender_eval, receiver, receiver_eval, topic, step_index
                )
            raise ValueError("GEMINI_API_KEY is not set.")

        prompt = build_peer_interaction_prompt(sender, sender_eval, receiver, receiver_eval, topic, step_index)
        endpoint = f"{self.api_base_url}/{self.model_name}:generateContent"

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self._api_key
        }

        payload = {
            "system_instruction": {"parts": [{"text": prompt["system"]}]},
            "contents": [{"role": "user", "parts": [{"text": prompt["user"]}]}],
            "generationConfig": {
                "temperature": 0.4,
                "responseMimeType": "application/json"
            }
        }

        max_retries = 3
        backoff_seconds = 2.0

        for attempt in range(1, max_retries + 1):
            try:
                self.call_count += 1
                req_data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(endpoint, data=req_data, headers=headers, method="POST")

                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                    res_body = response.read().decode("utf-8")
                    res_json = json.loads(res_body)

                    candidates = res_json.get("candidates", [])
                    if not candidates:
                        raise ValueError("Gemini API returned empty candidates.")

                    parts = candidates[0].get("content", {}).get("parts", [])
                    if not parts or "text" not in parts[0]:
                        raise ValueError("Gemini candidate missing text part.")

                    raw_text = parts[0]["text"]
                    parsed_dict = ConfigurableLLMProvider._extract_json(raw_text)

                    return PersonaInteractionOutput.from_dict(
                        parsed_dict,
                        fallback_sender=sender.persona_id,
                        fallback_receiver=receiver.persona_id,
                        fallback_topic=topic
                    )
            except urllib.error.HTTPError as e:
                # Retry on transient server busy/rate limit errors
                if e.code in [503, 429] and attempt < max_retries:
                    time.sleep(backoff_seconds * attempt)
                    continue
                if self.fallback_to_stub:
                    return self._stub_fallback.generate_peer_interaction(
                        sender, sender_eval, receiver, receiver_eval, topic, step_index
                    )
                error_details = ""
                try:
                    error_details = e.read().decode("utf-8")
                except Exception:
                    pass
                raise RuntimeError(
                    f"Gemini API request failed with HTTP {e.code} ({e.reason}) for model '{self.model_name}'. "
                    f"Details: {error_details[:250]}"
                ) from None
            except Exception as e:
                if self.fallback_to_stub:
                    return self._stub_fallback.generate_peer_interaction(
                        sender, sender_eval, receiver, receiver_eval, topic, step_index
                    )
                raise RuntimeError(f"GeminiLLMProvider peer interaction failed: {str(e)}") from None


class PersonaAgent:
    """
    AI Persona Agent representing a student citizen.
    Separates deterministic quantitative policy math from persona reasoning.
    """
    def __init__(self, persona: StudentPersona, llm_provider: Optional[BaseLLMProvider] = None):
        self.persona = persona
        self.llm_provider = llm_provider or StubLLMProvider()

    def compute_baseline_metrics(self, policy_eval: PolicyEvaluationResult) -> PersonaCalculatedMetrics:
        """
        Computes transparent baseline probabilistic scores from persona attributes and policy outcome.
        Formulaic, explainable, and decoupled from LLM hallucinations.
        """
        p = self.persona

        # 1. Awareness Score (0.0 to 1.0)
        awareness = min(1.0, max(0.05, (
            p.initial_awareness * 0.50 +
            p.peer_network_support * 0.35 +
            p.digital_literacy * 0.15
        )))

        # 2. Perceived Benefit Score (0.0 to 1.0)
        if policy_eval.is_eligible and policy_eval.estimated_fee_relief_inr > 0:
            relief_ratio = min(1.0, policy_eval.estimated_fee_relief_inr / max(1.0, p.family_income * 0.3))
            friction_penalty = (1.0 - p.personality.patience) * 0.2 + p.personality.risk_aversion * 0.1
            perceived_benefit = min(1.0, max(0.1, (relief_ratio * 0.7 + p.financial_urgency * 0.3) - friction_penalty))
        else:
            perceived_benefit = 0.0

        # 3. Application Probability (0.0 to 1.0)
        if not policy_eval.is_eligible:
            app_prob = 0.0
        else:
            app_prob = (
                awareness * 0.30 +
                perceived_benefit * 0.35 +
                p.document_readiness * 0.20 +
                p.personality.self_advocacy * 0.15
            )
            app_prob = min(0.98, max(0.0, app_prob))

        # 4. Completion Probability (0.0 to 1.0)
        if not policy_eval.is_eligible:
            comp_prob = 0.0
        else:
            comp_prob = (
                p.document_readiness * 0.40 +
                p.digital_literacy * 0.30 +
                p.personality.diligence * 0.20 +
                p.peer_network_support * 0.10
            )
            comp_prob = min(0.98, max(0.05, comp_prob))

        # 5. Expected Uptake Probability
        expected_uptake = (1.0 if policy_eval.is_eligible else 0.0) * app_prob * comp_prob

        # Discrete outcome thresholds for single deterministic run
        will_attempt = (app_prob >= 0.45)
        will_complete = will_attempt and (comp_prob >= 0.50)
        final_benefit = policy_eval.is_eligible and will_complete

        return PersonaCalculatedMetrics(
            awareness_score=round(awareness, 4),
            perceived_benefit_score=round(perceived_benefit, 4),
            application_probability=round(app_prob, 4),
            completion_probability=round(comp_prob, 4),
            expected_uptake_probability=round(expected_uptake, 4),
            will_attempt_application=will_attempt,
            will_complete_application=will_complete,
            final_benefit_received=final_benefit
        )

    def reason(self, policy_eval: PolicyEvaluationResult, metrics: PersonaCalculatedMetrics) -> PersonaReasoningOutput:
        """Executes persona reasoning using the pluggable LLM provider."""
        return self.llm_provider.generate_persona_reasoning(
            persona=self.persona,
            policy_eval=policy_eval,
            metrics=metrics
        )

    def interact_with(
        self,
        receiver: StudentPersona,
        sender_eval: PolicyEvaluationResult,
        receiver_eval: PolicyEvaluationResult,
        topic: str,
        step_index: int
    ) -> Any:
        """
        Executes a peer-to-peer interaction from self.persona (sender) to receiver.
        Generates qualitative dialogue and applies bounded state updates to the receiver.
        """
        from simulation.interaction import InteractionStateEngine, InteractionRecord, InteractionTopic

        dialogue: PersonaInteractionOutput = self.llm_provider.generate_peer_interaction(
            sender=self.persona,
            sender_eval=sender_eval,
            receiver=receiver,
            receiver_eval=receiver_eval,
            topic=topic,
            step_index=step_index
        )

        pre_state = {
            "awareness": receiver.initial_awareness,
            "institutional_trust": receiver.institutional_trust,
            "document_readiness": receiver.document_readiness,
            "peer_network_support": receiver.peer_network_support
        }

        # Resolve Topic Enum
        try:
            topic_enum = InteractionTopic(topic)
        except ValueError:
            topic_enum = InteractionTopic.SCHEME_AWARENESS

        has_changed, delta, delta_dict = InteractionStateEngine.compute_state_updates(
            sender=self.persona,
            receiver=receiver,
            topic=topic_enum,
            sender_eligible=sender_eval.is_eligible,
            receiver_eligible=receiver_eval.is_eligible
        )

        if has_changed:
            InteractionStateEngine.apply_state_updates(receiver, delta)

        post_state = {
            "awareness": receiver.initial_awareness,
            "institutional_trust": receiver.institutional_trust,
            "document_readiness": receiver.document_readiness,
            "peer_network_support": receiver.peer_network_support
        }

        self.persona.record_memory(
            step=step_index,
            event_type="SENT_PEER_INTERACTION",
            details={"peer_id": receiver.persona_id, "topic": topic, "msg": dialogue.sender_message}
        )
        receiver.record_memory(
            step=step_index,
            event_type="RECEIVED_PEER_INTERACTION",
            details={
                "peer_id": self.persona.persona_id,
                "topic": topic,
                "reply": dialogue.receiver_response,
                "state_changed": has_changed,
                "deltas": delta_dict
            }
        )

        return InteractionRecord(
            sender_id=self.persona.persona_id,
            receiver_id=receiver.persona_id,
            simulation_step=step_index,
            interaction_topic=topic,
            sender_message=dialogue.sender_message,
            receiver_response=dialogue.receiver_response,
            state_changed=has_changed,
            state_changes=delta_dict,
            pre_interaction_state=pre_state,
            post_interaction_state=post_state
        )
