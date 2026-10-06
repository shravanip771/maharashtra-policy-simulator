"""
Persona Data Schema & Models for Synthetic Persona Generation (Phase 2 Foundation)

This module defines the structural foundation for generating college student personas
for the Maharashtra Policy Simulator.

Attributes are explicitly partitioned into three provenance tiers:
1. Grounded / Reference Attributes: Demographic, geographic, and institutional dimensions
   that map to reference empirical tables (e.g. AISHE, Census).
2. Derived Attributes: Values calculated, conditionally sampled, or constructed from
   grounded attributes and baseline distributions.
3. Synthetic Behavioural Attributes: Modelled cognitive, psychological, and behavioral
   factors (awareness, trust, digital confidence, documentation confidence, personality).
   THESE ARE SIMULATION HYPOTHESES AND MUST NOT BE TREATED AS EMPIRICAL OBSERVATIONS.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Any, Optional, Tuple
from simulation.persona import (
    StudentPersona,
    InstitutionType,
    AdmissionMode,
    PersonalityTraits,
    SimulationState
)

class AttributeProvenance(str, Enum):
    """
    Explicit provenance tag indicating the origin and epistemic nature of each attribute.
    """
    GROUNDED = "grounded"     # Directly sampled from demographic/institutional reference distributions
    DERIVED = "derived"       # Calculated or conditionally computed from grounded distributions
    SYNTHETIC = "synthetic"   # Modelled behavioral hypotheses, priors, and personality traits


@dataclass
class GroundedAttributes:
    """
    Attributes corresponding to empirical demographic, geographic, and institutional categories.
    These fields will be mapped to reference government/administrative datasets.
    """
    district: str
    region_type: str                         # e.g., "Rural", "Semi-Urban", "Urban"
    gender: str                              # e.g., "Female", "Male", "Non-Binary"
    caste_category: str                      # e.g., "General-EBC", "OBC", "SC", "ST", "VJNT", "General"
    parental_education_level: str            # e.g., "None", "Primary", "Secondary", "Higher Secondary", "Graduate"
    institution_type: InstitutionType        # Government, Government-Aided, Private-Unaided, Deemed/Private
    admission_mode: AdmissionMode            # CAP, Management-Quota, Institute-Level, General-Merit
    is_professional_course: bool             # True for Engineering/Pharmacy/Management, False for general BA/BSc
    course_level: str                        # "Undergraduate", "Postgraduate", "Diploma"


@dataclass
class DerivedAttributes:
    """
    Attributes computed or conditionally derived from grounded distributions, academic context,
    or financial brackets.
    """
    persona_id: str
    name: str
    age: int
    is_maharashtra_domicile: bool
    family_income: float                     # Annual household income in INR
    first_generation_learner: bool
    course_name: str
    annual_tuition_fee: float                # in INR
    attendance_percentage: float             # 0.0 to 100.0
    previous_year_passed: bool
    previous_year_percentage: float          # 0.0 to 100.0
    academic_gap_years: int
    family_beneficiaries_count: int          # Sibling count already receiving benefit
    has_other_scholarship: bool              # Concurrent scholarship flag


@dataclass
class SyntheticBehaviouralAttributes:
    """
    Modelled cognitive, psychological, and behavioral factors representing decision-making
    tendencies and administrative frictions.
    
    DISCLAIMER: These fields are synthetic simulation parameters, NOT empirical statistics.
    """
    initial_awareness: float                 # Baseline awareness of scheme and application portal (0.0 to 1.0)
    digital_literacy: float                  # Digital confidence navigating MahaDBT portal & PDF uploads (0.0 to 1.0)
    document_readiness: float                # Documentation confidence & readiness with Tahsildar certificates (0.0 to 1.0)
    financial_urgency: float                 # Perceived pressure of fee burden on household finances (0.0 to 1.0)
    peer_network_support: float              # Social influence & peer/senior guidance in college (0.0 to 1.0)
    institutional_trust: float = 0.5         # Trust in DBT timeliness and administrative fairness (0.0 to 1.0)
    personality: PersonalityTraits = field(default_factory=PersonalityTraits)


@dataclass
class PersonaProfile:
    """
    Full persona representation maintaining strict separation of provenance layers.
    Includes seamless conversion to the Phase 1 StudentPersona model for policy simulation.
    """
    grounded: GroundedAttributes
    derived: DerivedAttributes
    synthetic: SyntheticBehaviouralAttributes
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def get_provenance_schema(cls) -> Dict[str, AttributeProvenance]:
        """Returns a static lookup mapping every field name to its AttributeProvenance tier."""
        schema: Dict[str, AttributeProvenance] = {}
        
        for field_name in GroundedAttributes.__annotations__:
            schema[field_name] = AttributeProvenance.GROUNDED
            
        for field_name in DerivedAttributes.__annotations__:
            schema[field_name] = AttributeProvenance.DERIVED
            
        for field_name in SyntheticBehaviouralAttributes.__annotations__:
            schema[field_name] = AttributeProvenance.SYNTHETIC
            
        return schema

    def to_student_persona(self) -> StudentPersona:
        """
        Converts the layered profile into a StudentPersona instance compatible
        with the Phase 1 policy rule engine, agent reasoning, and simulation engine.
        """
        return StudentPersona(
            # Basic Demographics & Geography
            persona_id=self.derived.persona_id,
            name=self.derived.name,
            age=self.derived.age,
            gender=self.grounded.gender,
            district=self.grounded.district,
            is_maharashtra_domicile=self.derived.is_maharashtra_domicile,

            # Family & Socio-Economic Profile
            family_income=self.derived.family_income,
            caste_category=self.grounded.caste_category,
            first_generation_learner=self.derived.first_generation_learner,
            parental_education_level=self.grounded.parental_education_level,

            # Academic & Institutional Profile
            course_name=self.derived.course_name,
            course_level=self.grounded.course_level,
            is_professional_course=self.grounded.is_professional_course,
            institution_type=self.grounded.institution_type,
            admission_mode=self.grounded.admission_mode,
            annual_tuition_fee=self.derived.annual_tuition_fee,
            attendance_percentage=self.derived.attendance_percentage,
            previous_year_passed=self.derived.previous_year_passed,
            previous_year_percentage=self.derived.previous_year_percentage,
            academic_gap_years=self.derived.academic_gap_years,

            # Scheme Statutory Attributes
            family_beneficiaries_count=self.derived.family_beneficiaries_count,
            has_other_scholarship=self.derived.has_other_scholarship,

            # Behavioral & Capacity Factors
            digital_literacy=self.synthetic.digital_literacy,
            initial_awareness=self.synthetic.initial_awareness,
            document_readiness=self.synthetic.document_readiness,
            financial_urgency=self.synthetic.financial_urgency,
            peer_network_support=self.synthetic.peer_network_support,
            institutional_trust=self.synthetic.institutional_trust,

            # Psychology & Agent State
            personality=self.synthetic.personality,
            current_state=SimulationState.UNINFORMED
        )

    def to_dict(self) -> Dict[str, Any]:
        """Returns a nested dictionary representation of the persona profile."""
        return {
            "grounded": asdict(self.grounded),
            "derived": asdict(self.derived),
            "synthetic": asdict(self.synthetic),
            "metadata": self.metadata
        }


@dataclass
class PopulationDistributionConfig:
    """
    Configurable population distributions and sampling priors.
    Enables injecting real demographic data later without changing generator logic.
    """
    config_name: str
    description: str
    is_example_placeholder: bool

    # Grounded categorical distributions (key -> probability weight)
    district_distribution: Dict[str, float]
    district_region_mapping: Dict[str, str]
    gender_distribution: Dict[str, float]
    caste_category_distribution: Dict[str, float]
    parental_education_distribution: Dict[str, float]
    institution_type_distribution: Dict[str, float]
    admission_mode_distribution: Dict[str, float]
    course_level_distribution: Dict[str, float]

    # Derived context mappings & distributions
    professional_probability_by_level: Dict[str, float]
    courses_by_stream: Dict[str, List[str]]
    income_brackets: List[Dict[str, Any]]  # List of {label: str, min_inr: float, max_inr: float, weight: float}
    tuition_fee_ranges: Dict[str, Tuple[float, float]]  # Key: f"{institution_type}:{is_professional}" -> (min_fee, max_fee)
    
    attendance_mean_std: Tuple[float, float]
    previous_year_pass_rate: float
    previous_year_percentage_mean_std: Tuple[float, float]
    gap_years_distribution: Dict[int, float]
    beneficiaries_count_distribution: Dict[int, float]
    other_scholarship_probability: float

    # Synthetic behavioral priors: (mean, std) bounded between 0.0 and 1.0
    behavioral_priors: Dict[str, Tuple[float, float]]
    personality_priors: Dict[str, Tuple[float, float]]

    # Name sampling pools
    first_names_by_gender: Dict[str, List[str]]
    last_names: List[str]
