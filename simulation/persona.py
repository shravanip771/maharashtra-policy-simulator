from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional

class InstitutionType(str, Enum):
    GOVERNMENT = "Government"
    GOVERNMENT_AIDED = "Government-Aided"
    PRIVATE_UNAIDED = "Private-Unaided"
    DEEMED_OR_PRIVATE_UNIVERSITY = "Deemed/Private-University"

class AdmissionMode(str, Enum):
    CAP = "CAP"  # Centralized Admission Process
    MANAGEMENT_QUOTA = "Management-Quota"
    INSTITUTE_LEVEL = "Institute-Level"
    GENERAL_MERIT = "General-Merit"

class SimulationState(str, Enum):
    UNINFORMED = "UNINFORMED"
    AWARE = "AWARE"
    EVALUATING = "EVALUATING"
    COLLECTING_DOCUMENTS = "COLLECTING_DOCUMENTS"
    APPLIED = "APPLIED"
    BENEFIT_RECEIVED = "BENEFIT_RECEIVED"
    REJECTED = "REJECTED"
    DROPPED_OUT = "DROPPED_OUT"

@dataclass
class PersonalityTraits:
    patience: float = 0.5          # 0.0 (easily frustrated by red tape) to 1.0 (persistent)
    diligence: float = 0.5         # 0.0 (disorganized with paperwork) to 1.0 (meticulous)
    risk_aversion: float = 0.5     # 0.0 (eager to try new processes) to 1.0 (fears bureaucratic hassle/fraud)
    self_advocacy: float = 0.5     # 0.0 (hesitant to seek help) to 1.0 (actively visits college office/cyber cafe)

@dataclass
class StudentPersona:
    # Basic Demographics & Geography
    persona_id: str
    name: str
    age: int
    gender: str
    district: str
    is_maharashtra_domicile: bool

    # Family & Socio-Economic Profile
    family_income: float            # Annual household income in INR
    caste_category: str             # e.g., "General-EBC", "OBC", "SC", "ST", "SEBC"
    first_generation_learner: bool = False
    parental_education_level: str = "Secondary"  # None, Primary, Secondary, Graduate

    # Academic & Institutional Profile
    course_name: str = "B.Tech Computer Engineering"
    course_level: str = "Undergraduate"  # Undergraduate, Postgraduate, Diploma
    is_professional_course: bool = True
    institution_type: InstitutionType = InstitutionType.PRIVATE_UNAIDED
    admission_mode: AdmissionMode = AdmissionMode.CAP
    annual_tuition_fee: float = 110000.0  # in INR
    attendance_percentage: float = 80.0
    previous_year_passed: bool = True
    previous_year_percentage: float = 72.0
    academic_gap_years: int = 0

    # Scheme Statutory Attributes
    family_beneficiaries_count: int = 0   # Number of siblings already receiving scheme benefits (Max allowed is 2)
    has_other_scholarship: bool = False    # Cannot hold concurrent state/central scholarships

    # Behavioral & Capacity Factors (Normalized 0.0 to 1.0)
    digital_literacy: float = 0.6          # Ability to navigate MahaDBT portal, upload PDFs, handle OTPs
    initial_awareness: float = 0.3         # Initial baseline awareness of the specific scheme
    document_readiness: float = 0.5        # Availability of valid Income Certificate, Domicile, CAP letter
    financial_urgency: float = 0.8         # Need for fee concession to avoid debt/dropout
    peer_network_support: float = 0.5      # Presence of peers/seniors guiding through application
    institutional_trust: float = 0.5       # Perceived fairness and trust in DBT processing timelines

    # Psychology & Agent State
    personality: PersonalityTraits = field(default_factory=PersonalityTraits)
    current_state: SimulationState = SimulationState.UNINFORMED
    memory: List[Dict[str, Any]] = field(default_factory=list)

    def record_memory(self, step: int, event_type: str, details: Dict[str, Any]) -> None:
        """Appends a trace event to the persona's state memory."""
        self.memory.append({
            "step": step,
            "event_type": event_type,
            "details": details
        })
