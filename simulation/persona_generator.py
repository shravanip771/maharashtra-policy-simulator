"""
Synthetic Persona Generator Module (Phase 2 Foundation)

This module generates plausible synthetic college student personas for the Maharashtra
Policy Simulator based on configurable population distributions.

Design & Transparency Principles:
1. Strict Epistemic Separation: Preserves explicit distinction between Grounded, Derived,
   and Synthetic Behavioural attributes.
2. Zero Hard-coded Claims: Uses configurable distributions rather than hardcoded demographic
   claims. Shipped with a clearly marked placeholder/example configuration.
3. Deterministic Reproducibility: Uses a dedicated `random.Random(seed)` instance to guarantee
   identical persona generation for identical seeds.
4. Phase 1 Compatibility: Produces `PersonaProfile` and `StudentPersona` objects directly usable
   by the policy engine and agent simulation components.
"""

import random
from typing import Dict, List, Any, Optional, Tuple, TypeVar

from simulation.persona import (
    StudentPersona,
    InstitutionType,
    AdmissionMode,
    PersonalityTraits,
    SimulationState
)
from simulation.persona_schema import (
    AttributeProvenance,
    GroundedAttributes,
    DerivedAttributes,
    SyntheticBehaviouralAttributes,
    PersonaProfile,
    PopulationDistributionConfig
)

T = TypeVar('T')

# ==============================================================================
# EXAMPLE / PLACEHOLDER POPULATION CONFIGURATION
# ------------------------------------------------------------------------------
# IMPORTANT NOTICE:
# The following distributions are synthetic placeholders intended purely for development,
# code testing, and structural validation.
# THEY DO NOT REPRESENT OFFICIAL MAHARASHTRA GOVERNMENT STATISTICS.
# Reference data from AISHE, Census, and DES Maharashtra will be integrated in future phases.
# ==============================================================================

EXAMPLE_POPULATION_CONFIG = PopulationDistributionConfig(
    config_name="Example-Maharashtra-College-Student-Baseline-Placeholder",
    description="Illustrative placeholder distributions for development and testing. Not official statistics.",
    is_example_placeholder=True,

    # Illustrative regional sample (placeholder weights)
    district_distribution={
        "Pune": 0.25,
        "Kolhapur": 0.15,
        "Nagpur": 0.15,
        "Nanded": 0.15,
        "Satara": 0.15,
        "Gadchiroli": 0.15,
    },
    district_region_mapping={
        "Pune": "Urban",
        "Kolhapur": "Semi-Urban",
        "Nagpur": "Urban",
        "Nanded": "Semi-Urban",
        "Satara": "Semi-Urban",
        "Gadchiroli": "Rural",
    },
    gender_distribution={
        "Female": 0.48,
        "Male": 0.50,
        "Non-Binary": 0.02,
    },
    caste_category_distribution={
        "General-EBC": 0.30,
        "OBC": 0.30,
        "SC": 0.15,
        "ST": 0.10,
        "VJNT": 0.10,
        "General": 0.05,
    },
    parental_education_distribution={
        "None": 0.10,
        "Primary": 0.20,
        "Secondary": 0.35,
        "Higher Secondary": 0.20,
        "Graduate": 0.15,
    },
    institution_type_distribution={
        "Government": 0.20,
        "Government-Aided": 0.30,
        "Private-Unaided": 0.45,
        "Deemed/Private-University": 0.05,
    },
    admission_mode_distribution={
        "CAP": 0.80,
        "Institute-Level": 0.10,
        "Management-Quota": 0.05,
        "General-Merit": 0.05,
    },
    course_level_distribution={
        "Undergraduate": 0.75,
        "Postgraduate": 0.15,
        "Diploma": 0.10,
    },
    professional_probability_by_level={
        "Undergraduate": 0.60,
        "Postgraduate": 0.50,
        "Diploma": 0.80,
    },
    courses_by_stream={
        "Professional": [
            "B.Tech Computer Engineering",
            "B.Tech Mechanical Engineering",
            "B.Pharm",
            "B.Tech Civil Engineering",
            "MBA",
            "MCA"
        ],
        "Non-Professional": [
            "B.Sc Computer Science",
            "B.Sc Chemistry",
            "B.Com",
            "B.A. Economics",
            "M.Sc Mathematics",
            "M.Com"
        ]
    },
    # Illustrative household income brackets (min_inr, max_inr, weight)
    income_brackets=[
        {"label": "Below 1.5 Lakh", "min_inr": 45000.0, "max_inr": 150000.0, "weight": 0.30},
        {"label": "1.5 Lakh - 3.5 Lakh", "min_inr": 150000.0, "max_inr": 350000.0, "weight": 0.35},
        {"label": "3.5 Lakh - 6.0 Lakh", "min_inr": 350000.0, "max_inr": 600000.0, "weight": 0.20},
        {"label": "6.0 Lakh - 8.0 Lakh", "min_inr": 600000.0, "max_inr": 800000.0, "weight": 0.10},
        {"label": "Above 8.0 Lakh", "min_inr": 800000.0, "max_inr": 1200000.0, "weight": 0.05},
    ],
    # Illustrative tuition fees by institution type and stream: (min_fee, max_fee)
    tuition_fee_ranges={
        "Government:True": (25000.0, 60000.0),
        "Government:False": (5000.0, 15000.0),
        "Government-Aided:True": (40000.0, 80000.0),
        "Government-Aided:False": (8000.0, 25000.0),
        "Private-Unaided:True": (80000.0, 160000.0),
        "Private-Unaided:False": (20000.0, 50000.0),
        "Deemed/Private-University:True": (150000.0, 300000.0),
        "Deemed/Private-University:False": (50000.0, 120000.0),
    },
    attendance_mean_std=(82.0, 6.0),
    previous_year_pass_rate=0.92,
    previous_year_percentage_mean_std=(70.0, 10.0),
    gap_years_distribution={0: 0.85, 1: 0.10, 2: 0.04, 3: 0.01},
    beneficiaries_count_distribution={0: 0.70, 1: 0.25, 2: 0.05},
    other_scholarship_probability=0.08,

    # Illustrative behavioral priors: (mean, std)
    behavioral_priors={
        "initial_awareness": (0.45, 0.20),
        "digital_literacy": (0.60, 0.18),
        "document_readiness": (0.50, 0.22),
        "financial_urgency": (0.70, 0.18),
        "peer_network_support": (0.55, 0.20),
        "institutional_trust": (0.50, 0.18),
    },
    personality_priors={
        "patience": (0.55, 0.18),
        "diligence": (0.60, 0.18),
        "risk_aversion": (0.50, 0.18),
        "self_advocacy": (0.50, 0.18),
    },
    first_names_by_gender={
        "Female": ["Pooja", "Sneha", "Anjali", "Rutuja", "Shravani", "Priyanka", "Sayali", "Tanvi"],
        "Male": ["Rahul", "Amit", "Pranav", "Sagar", "Omkar", "Aditya", "Vishal", "Akash"],
        "Non-Binary": ["Arya", "Samarth", "Kiran", "Shree"]
    },
    last_names=["Patil", "Deshmukh", "Jadhav", "Kulkarni", "Shinde", "Gaikwad", "More", "Pawar", "Bhosale", "Kamble"]
)


class SyntheticPersonaGenerator:
    """
    Configurable generator that produces synthetic student personas with clear
    provenance separation.
    """

    def __init__(
        self,
        config: Optional[PopulationDistributionConfig] = None,
        seed: Optional[int] = None
    ):
        self.config = config or EXAMPLE_POPULATION_CONFIG
        self.seed = seed
        self._rng = random.Random(seed)

    def set_seed(self, seed: Optional[int]) -> None:
        """Sets or resets the random seed for reproducible generation."""
        self.seed = seed
        self._rng = random.Random(seed)

    # --------------------------------------------------------------------------
    # Sampling Helpers
    # --------------------------------------------------------------------------

    def _sample_categorical(self, distribution: Dict[T, float]) -> T:
        """Weighted categorical sampling using the internal RNG."""
        keys = list(distribution.keys())
        weights = list(distribution.values())
        return self._rng.choices(keys, weights=weights, k=1)[0]

    def _sample_bounded_normal(
        self,
        mean: float,
        std: float,
        min_val: float = 0.0,
        max_val: float = 1.0
    ) -> float:
        """Samples from a Gaussian distribution clamped to [min_val, max_val]."""
        val = self._rng.gauss(mean, std)
        return max(min_val, min(max_val, val))

    def _sample_uniform(self, min_val: float, max_val: float) -> float:
        """Uniform sampling within a closed interval."""
        return self._rng.uniform(min_val, max_val)

    # --------------------------------------------------------------------------
    # Persona Generation Logic
    # --------------------------------------------------------------------------

    def generate_profile(
        self,
        persona_id: Optional[str] = None,
        seed: Optional[int] = None
    ) -> PersonaProfile:
        """
        Generates a complete PersonaProfile, preserving explicit separation across
        grounded, derived, and synthetic behavioural attributes.
        """
        if seed is not None:
            local_rng = random.Random(seed)
        else:
            local_rng = self._rng

        # Helper with local RNG binding
        def choose_cat(dist: Dict[T, float]) -> T:
            k = list(dist.keys())
            w = list(dist.values())
            return local_rng.choices(k, weights=w, k=1)[0]

        def sample_norm(mean: float, std: float, low: float = 0.0, high: float = 1.0) -> float:
            v = local_rng.gauss(mean, std)
            return max(low, min(high, v))

        # 1. SAMPLE GROUNDED ATTRIBUTES (Empirical / Categorical Context)
        district = choose_cat(self.config.district_distribution)
        region_type = self.config.district_region_mapping.get(district, "Semi-Urban")
        gender = choose_cat(self.config.gender_distribution)
        caste_category = choose_cat(self.config.caste_category_distribution)
        parental_edu = choose_cat(self.config.parental_education_distribution)
        
        inst_type_raw = choose_cat(self.config.institution_type_distribution)
        institution_type = InstitutionType(inst_type_raw)
        
        adm_mode_raw = choose_cat(self.config.admission_mode_distribution)
        admission_mode = AdmissionMode(adm_mode_raw)
        
        course_level = choose_cat(self.config.course_level_distribution)
        prof_prob = self.config.professional_probability_by_level.get(course_level, 0.5)
        is_professional_course = (local_rng.random() < prof_prob)

        grounded = GroundedAttributes(
            district=district,
            region_type=region_type,
            gender=gender,
            caste_category=caste_category,
            parental_education_level=parental_edu,
            institution_type=institution_type,
            admission_mode=admission_mode,
            is_professional_course=is_professional_course,
            course_level=course_level
        )

        # 2. CALCULATE DERIVED ATTRIBUTES
        p_id = persona_id or f"SYNTH-STU-{local_rng.randint(10000, 99999)}"
        
        # Name generation based on gender pool
        first_names = self.config.first_names_by_gender.get(
            gender,
            self.config.first_names_by_gender.get("Female", ["Student"])
        )
        first_name = local_rng.choice(first_names)
        last_name = local_rng.choice(self.config.last_names)
        name = f"{first_name} {last_name}"

        # Gap years & age calculation
        gap_years = choose_cat(self.config.gap_years_distribution)
        base_age = 18 if course_level == "Undergraduate" else (21 if course_level == "Postgraduate" else 17)
        age = base_age + local_rng.randint(0, 2) + gap_years

        # Domicile (assumed True for Maharashtra student pool by default)
        is_domicile = True

        # First generation learner derivation
        first_gen = parental_edu in ["None", "Primary"]

        # Course name selection
        stream_key = "Professional" if is_professional_course else "Non-Professional"
        course_pool = self.config.courses_by_stream.get(stream_key, ["General Studies"])
        course_name = local_rng.choice(course_pool)

        # Household income derivation
        income_bracket = local_rng.choices(
            self.config.income_brackets,
            weights=[b["weight"] for b in self.config.income_brackets],
            k=1
        )[0]
        family_income = round(local_rng.uniform(income_bracket["min_inr"], income_bracket["max_inr"]), -2)

        # Annual tuition fee calculation based on institution type & course stream
        fee_key = f"{institution_type.value}:{is_professional_course}"
        fee_min, fee_max = self.config.tuition_fee_ranges.get(fee_key, (30000.0, 90000.0))
        annual_tuition_fee = round(local_rng.uniform(fee_min, fee_max), -2)

        # Academic performance derivation
        att_mean, att_std = self.config.attendance_mean_std
        attendance_percentage = round(sample_norm(att_mean, att_std, 50.0, 100.0), 1)

        prev_passed = (local_rng.random() < self.config.previous_year_pass_rate)
        marks_mean, marks_std = self.config.previous_year_percentage_mean_std
        previous_year_percentage = round(sample_norm(marks_mean, marks_std, 35.0, 99.0), 1)

        # Sibling beneficiaries count & concurrent scholarship derivation
        beneficiaries_count = choose_cat(self.config.beneficiaries_count_distribution)
        has_other_scholarship = (local_rng.random() < self.config.other_scholarship_probability)

        derived = DerivedAttributes(
            persona_id=p_id,
            name=name,
            age=age,
            is_maharashtra_domicile=is_domicile,
            family_income=family_income,
            first_generation_learner=first_gen,
            course_name=course_name,
            annual_tuition_fee=annual_tuition_fee,
            attendance_percentage=attendance_percentage,
            previous_year_passed=prev_passed,
            previous_year_percentage=previous_year_percentage,
            academic_gap_years=gap_years,
            family_beneficiaries_count=beneficiaries_count,
            has_other_scholarship=has_other_scholarship
        )

        # 3. SAMPLE SYNTHETIC BEHAVIOURAL ATTRIBUTES (Modelled Hypotheses)
        priors = self.config.behavioral_priors
        awareness_m, awareness_s = priors.get("initial_awareness", (0.45, 0.20))
        digital_m, digital_s = priors.get("digital_literacy", (0.60, 0.18))
        doc_m, doc_s = priors.get("document_readiness", (0.50, 0.22))
        urgency_m, urgency_s = priors.get("financial_urgency", (0.70, 0.18))
        peer_m, peer_s = priors.get("peer_network_support", (0.55, 0.20))
        trust_m, trust_s = priors.get("institutional_trust", (0.50, 0.18))

        # Adjust priors conditionally to reflect realistic simulation nuances
        # (e.g., lower income -> higher financial urgency; first gen -> slightly lower initial awareness)
        if family_income <= 200000.0:
            urgency_m = min(1.0, urgency_m + 0.15)
        if first_gen:
            doc_m = max(0.0, doc_m - 0.10)
            awareness_m = max(0.0, awareness_m - 0.10)
        if region_type == "Rural":
            digital_m = max(0.0, digital_m - 0.10)

        initial_awareness = round(sample_norm(awareness_m, awareness_s, 0.05, 0.95), 2)
        digital_literacy = round(sample_norm(digital_m, digital_s, 0.05, 0.95), 2)
        document_readiness = round(sample_norm(doc_m, doc_s, 0.05, 0.95), 2)
        financial_urgency = round(sample_norm(urgency_m, urgency_s, 0.05, 0.95), 2)
        peer_network_support = round(sample_norm(peer_m, peer_s, 0.05, 0.95), 2)
        institutional_trust = round(sample_norm(trust_m, trust_s, 0.05, 0.95), 2)

        pers_priors = self.config.personality_priors
        personality = PersonalityTraits(
            patience=round(sample_norm(*pers_priors.get("patience", (0.55, 0.18))), 2),
            diligence=round(sample_norm(*pers_priors.get("diligence", (0.60, 0.18))), 2),
            risk_aversion=round(sample_norm(*pers_priors.get("risk_aversion", (0.50, 0.18))), 2),
            self_advocacy=round(sample_norm(*pers_priors.get("self_advocacy", (0.50, 0.18))), 2),
        )

        synthetic = SyntheticBehaviouralAttributes(
            initial_awareness=initial_awareness,
            digital_literacy=digital_literacy,
            document_readiness=document_readiness,
            financial_urgency=financial_urgency,
            peer_network_support=peer_network_support,
            institutional_trust=institutional_trust,
            personality=personality
        )

        metadata = {
            "config_name": self.config.config_name,
            "is_example_placeholder": self.config.is_example_placeholder,
            "seed": seed if seed is not None else self.seed,
            "data_disclaimer": "Behavioral factors are synthetic simulation priors, not empirical census facts."
        }

        return PersonaProfile(
            grounded=grounded,
            derived=derived,
            synthetic=synthetic,
            metadata=metadata
        )

    def generate_student_persona(
        self,
        persona_id: Optional[str] = None,
        seed: Optional[int] = None
    ) -> StudentPersona:
        """
        Direct convenience method to generate a StudentPersona compatible with Phase 1.
        """
        profile = self.generate_profile(persona_id=persona_id, seed=seed)
        return profile.to_student_persona()

    def generate_population(
        self,
        count: int = 10,
        id_prefix: str = "DHULE-STU",
        start_index: int = 1
    ) -> List[PersonaProfile]:
        """
        Generates a reproducible population/cohort of N synthetic persona profiles.
        Maintains unique persona IDs and deterministic RNG state progression.
        """
        population: List[PersonaProfile] = []
        for i in range(count):
            p_id = f"{id_prefix}-{start_index + i:03d}"
            profile = self.generate_profile(persona_id=p_id)
            population.append(profile)
        return population

    def generate_student_population(
        self,
        count: int = 10,
        id_prefix: str = "DHULE-STU",
        start_index: int = 1
    ) -> List[StudentPersona]:
        """
        Generates a cohort of N StudentPersona instances ready for simulation.
        """
        profiles = self.generate_population(count=count, id_prefix=id_prefix, start_index=start_index)
        return [p.to_student_persona() for p in profiles]

    def generate_cohort(
        self,
        count: int = 10,
        id_prefix: str = "DHULE-STU",
        start_index: int = 1,
        seed: Optional[int] = None
    ) -> List[StudentPersona]:
        """Alias for generate_student_population with optional re-seeding."""
        if seed is not None:
            self.rng = random.Random(seed)
            self.seed = seed
        return self.generate_student_population(count=count, id_prefix=id_prefix, start_index=start_index)


