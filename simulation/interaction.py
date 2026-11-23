"""
Multi-Persona Social Interaction Module (Phase 2 Social Dynamics Layer)

This module manages structured peer-to-peer dialogues, social diffusion of scheme awareness,
peer encouragement, administrative friction sharing, and bounded state updates.

CORE SAFETY MANDATES:
1. Statutory eligibility is deterministically calculated by the rule engine and CANNOT be altered
   by conversational exchanges.
2. Personas express uncertainty when official details are unknown rather than inventing policy rules.
3. State changes are strictly bounded in the range [0.0, 1.0].
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Any, Optional, Tuple
import json

from simulation.persona import StudentPersona, SimulationState
from simulation.policy_rules import PolicyEvaluationResult


class InteractionTopic(str, Enum):
    SCHEME_AWARENESS = "SCHEME_AWARENESS"                    # Informing peer about scholarship existence and potential fee relief
    APPLICATION_GUIDANCE = "APPLICATION_GUIDANCE"            # Guiding peer through MahaDBT portal registration & college scrutiny
    DOCUMENTATION_HURDLE = "DOCUMENTATION_HURDLE"            # Discussing documentation and certificate renewal friction
    TRUST_AND_DISCOURAGEMENT = "TRUST_AND_DISCOURAGEMENT"    # Expressing doubts/frustrations about disbursement timelines or red tape


@dataclass
class StateChangeDelta:
    """Explicit, transparent tracking of pre/post state changes for a persona."""
    awareness_before: float
    awareness_after: float
    awareness_delta: float

    trust_before: float
    trust_after: float
    trust_delta: float

    doc_readiness_before: float
    doc_readiness_after: float
    doc_readiness_delta: float

    peer_support_before: float
    peer_support_after: float
    peer_support_delta: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class InteractionRecord:
    """
    Structured record representing a single peer-to-peer conversational exchange.
    """
    sender_id: str
    receiver_id: str
    simulation_step: int
    interaction_topic: str
    sender_message: str
    receiver_response: str
    state_changed: bool
    state_changes: Dict[str, Any]
    pre_interaction_state: Dict[str, Any]
    post_interaction_state: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)


def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamps a numerical value strictly within [min_val, max_val] with precision rounding."""
    return round(min(max_val, max(min_val, value)), 4)


class InteractionStateEngine:
    """
    Applies bounded, explainable psychological and behavioral state updates
    following a peer-to-peer interaction exchange.
    """

    @staticmethod
    def compute_state_updates(
        sender: StudentPersona,
        receiver: StudentPersona,
        topic: InteractionTopic,
        sender_eligible: bool,
        receiver_eligible: bool
    ) -> Tuple[bool, StateChangeDelta, Dict[str, Any]]:
        """
        Calculates bounded state changes for the receiver based on topic, persona traits, and sender influence.
        """
        # Capture pre-interaction baselines
        aw_before = receiver.initial_awareness
        tr_before = receiver.institutional_trust
        doc_before = receiver.document_readiness
        net_before = receiver.peer_network_support

        aw_after = aw_before
        tr_after = tr_before
        doc_after = doc_before
        net_after = net_before

        # Topic-driven behavioral diffusion rules:
        if topic == InteractionTopic.SCHEME_AWARENESS:
            # High awareness sender raises receiver's awareness (diffusion effect)
            if sender.initial_awareness > receiver.initial_awareness:
                gain = (sender.initial_awareness - receiver.initial_awareness) * 0.45 * (0.8 + 0.4 * receiver.personality.self_advocacy)
                aw_after = clamp(aw_before + gain)
            # Peer support increases from positive interaction
            net_after = clamp(net_before + 0.08)

        elif topic == InteractionTopic.APPLICATION_GUIDANCE:
            # Positive procedural guidance increases documentation confidence and awareness
            guidance_effect = (sender.digital_literacy * 0.30) + (sender.document_readiness * 0.20)
            doc_after = clamp(doc_before + guidance_effect * (1.0 - doc_before) * 0.40)
            aw_after = clamp(aw_before + 0.10 * (1.0 - aw_before))
            tr_after = clamp(tr_before + 0.05 * (1.0 - tr_before))
            net_after = clamp(net_before + 0.12 * (1.0 - net_before))

        elif topic == InteractionTopic.DOCUMENTATION_HURDLE:
            # Sharing hurdles may prompt document readiness if diligent, but slightly lower trust
            if receiver.personality.diligence > 0.6:
                doc_after = clamp(doc_before + 0.08 * (1.0 - doc_before))
            tr_after = clamp(tr_before - 0.05 * receiver.personality.risk_aversion)
            net_after = clamp(net_before + 0.06 * (1.0 - net_before))

        elif topic == InteractionTopic.TRUST_AND_DISCOURAGEMENT:
            # Cynicism / delay complaints lower trust, especially if risk averse
            trust_drop = 0.12 * (0.5 + receiver.personality.risk_aversion)
            tr_after = clamp(tr_before - trust_drop)
            net_after = clamp(net_before + 0.04)

        # Calculate deltas
        aw_delta = round(aw_after - aw_before, 4)
        tr_delta = round(tr_after - tr_before, 4)
        doc_delta = round(doc_after - doc_before, 4)
        net_delta = round(net_after - net_before, 4)

        has_changed = (aw_delta != 0.0 or tr_delta != 0.0 or doc_delta != 0.0 or net_delta != 0.0)

        delta = StateChangeDelta(
            awareness_before=aw_before,
            awareness_after=aw_after,
            awareness_delta=aw_delta,
            trust_before=tr_before,
            trust_after=tr_after,
            trust_delta=tr_delta,
            doc_readiness_before=doc_before,
            doc_readiness_after=doc_after,
            doc_readiness_delta=doc_delta,
            peer_support_before=net_before,
            peer_support_after=net_after,
            peer_support_delta=net_delta
        )

        return has_changed, delta, delta.to_dict()

    @staticmethod
    def apply_state_updates(receiver: StudentPersona, delta: StateChangeDelta) -> None:
        """Applies calculated bounded state changes directly to the receiver persona."""
        receiver.initial_awareness = delta.awareness_after
        receiver.institutional_trust = delta.trust_after
        receiver.document_readiness = delta.doc_readiness_after
        receiver.peer_network_support = delta.peer_support_after
