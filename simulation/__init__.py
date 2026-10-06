"""
Maharashtra Policy Simulator - Simulation Module
Phase 1 Vertical Slice
"""

from simulation.persona import (
    StudentPersona,
    InstitutionType,
    AdmissionMode,
    SimulationState,
    PersonalityTraits
)
from simulation.policy_rules import (
    RajarshiShahuPolicyEngine,
    PolicyEvaluationResult,
    RuleCheckResult
)
from simulation.agent import (
    PersonaAgent,
    BaseLLMProvider,
    StubLLMProvider,
    ConfigurableLLMProvider,
    GeminiLLMProvider,
    PersonaCalculatedMetrics,
    PersonaReasoningOutput,
    PersonaInteractionOutput,
    build_persona_reasoning_prompt,
    build_peer_interaction_prompt
)
from simulation.engine import (
    SimulationEngine,
    SimulationStepOutput,
    CohortSimulationResult,
    MultiStepSimulationResult
)
from simulation.social_network import (
    SyntheticSocialNetwork,
    NetworkEdge
)
from simulation.interaction import (
    InteractionTopic,
    InteractionRecord,
    StateChangeDelta,
    InteractionStateEngine
)

from simulation.persona_schema import (
    AttributeProvenance,
    GroundedAttributes,
    DerivedAttributes,
    SyntheticBehaviouralAttributes,
    PersonaProfile,
    PopulationDistributionConfig
)
from simulation.persona_generator import (
    SyntheticPersonaGenerator,
    EXAMPLE_POPULATION_CONFIG
)

__all__ = [
    "StudentPersona",
    "InstitutionType",
    "AdmissionMode",
    "SimulationState",
    "PersonalityTraits",
    "RajarshiShahuPolicyEngine",
    "PolicyEvaluationResult",
    "RuleCheckResult",
    "PersonaAgent",
    "BaseLLMProvider",
    "StubLLMProvider",
    "ConfigurableLLMProvider",
    "GeminiLLMProvider",
    "PersonaCalculatedMetrics",
    "PersonaReasoningOutput",
    "PersonaInteractionOutput",
    "build_persona_reasoning_prompt",
    "build_peer_interaction_prompt",
    "SimulationEngine",
    "SimulationStepOutput",
    "CohortSimulationResult",
    "MultiStepSimulationResult",
    "SyntheticSocialNetwork",
    "NetworkEdge",
    "InteractionTopic",
    "InteractionRecord",
    "StateChangeDelta",
    "InteractionStateEngine",
    "AttributeProvenance",
    "GroundedAttributes",
    "DerivedAttributes",
    "SyntheticBehaviouralAttributes",
    "PersonaProfile",
    "PopulationDistributionConfig",
    "SyntheticPersonaGenerator",
    "EXAMPLE_POPULATION_CONFIG"
]


