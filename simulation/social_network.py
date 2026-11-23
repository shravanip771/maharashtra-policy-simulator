"""
Synthetic Social Network Module (Phase 2 Social Interaction Layer)

This module implements a lightweight, deterministic social network model representing
peer-to-peer relationships, word-of-mouth diffusion, and informal college networks
among synthetic student personas in Maharashtra.

PROVENANCE & METHODOLOGY NOTICE:
These relationships are SYNTHETIC SIMULATION CONSTRUCTS generated for policy diffusion modeling.
They do not represent real-world citizen data or empirical social graphs.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple, Set
import random

from simulation.persona import StudentPersona


@dataclass
class NetworkEdge:
    """Represents a directional or mutual connection between two student personas."""
    source_id: str
    target_id: str
    affinity_score: float
    common_attributes: List[str] = field(default_factory=list)


class SyntheticSocialNetwork:
    """
    Lightweight, seeded social network generator for synthetic persona cohorts.
    
    Guarantees:
    1. Fully deterministic and reproducible using a fixed random seed.
    2. Zero self-connections (a persona cannot connect to itself).
    3. Small, bounded degree per persona (no all-to-all communication; e.g. 1 to 3 connections).
    4. Plausible homophily based on institution type, course, district, and socio-demographic traits.
    """

    def __init__(
        self,
        personas: List[StudentPersona],
        seed: Optional[int] = 42,
        max_degree: int = 2
    ):
        self.personas: Dict[str, StudentPersona] = {p.persona_id: p for p in personas}
        self.seed = seed
        self.max_degree = max_degree
        self.adjacency: Dict[str, List[str]] = {p.persona_id: [] for p in personas}
        self.edges: List[NetworkEdge] = []
        self.is_synthetic_simulation_graph: bool = True

        self._build_network()

    def _compute_affinity(self, p1: StudentPersona, p2: StudentPersona) -> Tuple[float, List[str]]:
        """Calculates a contextual compatibility score between two students for synthetic tie formation."""
        score = 0.5  # Baseline random encounter probability
        common: List[str] = []

        # 1. Institution type homophily (strongest driver of college peer groups)
        if p1.institution_type == p2.institution_type:
            score += 2.0
            common.append(f"Same institution type ({p1.institution_type.value})")

        # 2. Course & Stream proximity
        if p1.is_professional_course == p2.is_professional_course:
            score += 1.0
            if p1.course_name == p2.course_name:
                score += 2.0
                common.append(f"Same course ({p1.course_name})")
            else:
                common.append("Both in professional/technical streams" if p1.is_professional_course else "Both in general degree streams")

        # 3. Geographic proximity (same district)
        if p1.district.strip().lower() == p2.district.strip().lower():
            score += 1.5
            common.append(f"Same district ({p1.district})")

        # 4. First-generation learner peer affinity
        if p1.first_generation_learner and p2.first_generation_learner:
            score += 0.8
            common.append("Both first-generation college learners")

        # 5. Gender peer support
        if p1.gender.strip().lower() == p2.gender.strip().lower():
            score += 0.5
            common.append(f"Same gender ({p1.gender})")

        return score, common

    def _build_network(self) -> None:
        """Constructs a deterministic undirected graph connecting personas based on weighted homophily."""
        rng = random.Random(self.seed)
        persona_ids = sorted(list(self.personas.keys()))
        n = len(persona_ids)

        if n <= 1:
            return

        # Precompute candidate pair affinities
        candidate_pairs: List[Tuple[float, str, str, List[str]]] = []
        for i in range(n):
            for j in range(i + 1, n):
                id1, id2 = persona_ids[i], persona_ids[j]
                p1, p2 = self.personas[id1], self.personas[id2]
                affinity, common = self._compute_affinity(p1, p2)
                # Add a small random jitter scaled by seed for diversity
                jitter = rng.uniform(0.8, 1.2)
                candidate_pairs.append((affinity * jitter, id1, id2, common))

        # Sort candidate pairs by affinity score descending
        candidate_pairs.sort(key=lambda x: x[0], reverse=True)

        # Greedy degree-constrained edge selection
        degree_counts: Dict[str, int] = {pid: 0 for pid in persona_ids}

        for score, id1, id2, common in candidate_pairs:
            if degree_counts[id1] < self.max_degree and degree_counts[id2] < self.max_degree:
                # Add edge
                self.adjacency[id1].append(id2)
                self.adjacency[id2].append(id1)
                degree_counts[id1] += 1
                degree_counts[id2] += 1
                self.edges.append(NetworkEdge(source_id=id1, target_id=id2, affinity_score=score, common_attributes=common))

        # Ensure no isolated nodes if possible (every persona gets at least 1 connection if n >= 2)
        isolated = [pid for pid, deg in degree_counts.items() if deg == 0]
        for iso_id in isolated:
            # Connect to the highest affinity non-self node
            best_partner = None
            best_score = -1.0
            best_common = []
            for other_id in persona_ids:
                if other_id == iso_id:
                    continue
                score, common = self._compute_affinity(self.personas[iso_id], self.personas[other_id])
                if score > best_score:
                    best_score = score
                    best_partner = other_id
                    best_common = common

            if best_partner is not None and best_partner not in self.adjacency[iso_id]:
                self.adjacency[iso_id].append(best_partner)
                self.adjacency[best_partner].append(iso_id)
                degree_counts[iso_id] += 1
                degree_counts[best_partner] += 1
                self.edges.append(NetworkEdge(source_id=iso_id, target_id=best_partner, affinity_score=best_score, common_attributes=best_common))

    def get_neighbors(self, persona_id: str) -> List[str]:
        """Returns the list of connected peer persona IDs for a given persona."""
        return list(self.adjacency.get(persona_id, []))

    def select_interactions_for_step(
        self,
        step_index: int,
        seed: Optional[int] = None
    ) -> List[Tuple[str, str]]:
        """
        Selects a subset of directional peer interaction pairs (sender -> receiver) for a given simulation step.
        Ensures deterministic selection based on seed and step index.
        """
        eff_seed = (self.seed or 42) + step_index * 101 if seed is None else seed + step_index * 101
        rng = random.Random(eff_seed)

        pairs: Set[Tuple[str, str]] = set()
        for edge in self.edges:
            # With probability ~0.7, an edge is active in a given step
            if rng.random() < 0.75:
                # Decide direction (sender -> receiver)
                if rng.random() < 0.5:
                    pairs.add((edge.source_id, edge.target_id))
                else:
                    pairs.add((edge.target_id, edge.source_id))

        return sorted(list(pairs))

    def to_dict(self) -> Dict[str, Any]:
        """Returns a serializable dictionary summary of the social network graph."""
        return {
            "is_synthetic_simulation_graph": self.is_synthetic_simulation_graph,
            "total_nodes": len(self.personas),
            "total_edges": len(self.edges),
            "max_degree_limit": self.max_degree,
            "seed": self.seed,
            "adjacency_list": {pid: sorted(neighbors) for pid, neighbors in self.adjacency.items()},
            "provenance_note": (
                "Synthetic simulation topology generated via attribute homophily heuristics. "
                "Not empirical social survey data."
            )
        }
