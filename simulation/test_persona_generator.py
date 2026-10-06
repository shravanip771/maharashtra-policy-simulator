"""
Automated tests for Synthetic Persona Generation Foundation (Phase 2).

Tests:
1. Generation of synthetic student profile and conversion to StudentPersona.
2. Verification of all required scholarship attributes and schema validity.
3. Verification of strict reproducibility across identical random seeds.
4. Verification of variance across differing seeds.
5. Verification of explicit distinction between Grounded, Derived, and Synthetic attributes.
6. Verification of end-to-end compatibility with Phase 1 Policy Engine and Simulation Engine.
7. Verification that custom population configs can be injected without changing engine logic.
"""

from simulation.persona import (
    StudentPersona,
    InstitutionType,
    AdmissionMode,
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
from simulation.persona_generator import (
    SyntheticPersonaGenerator,
    EXAMPLE_POPULATION_CONFIG
)
from simulation.policy_rules import RajarshiShahuPolicyEngine
from simulation.engine import SimulationEngine


def test_generate_single_synthetic_student():
    """Verifies that a single persona is generated with all expected profile components."""
    generator = SyntheticPersonaGenerator(seed=42)
    profile = generator.generate_profile(persona_id="TEST-SYNTH-001")

    assert isinstance(profile, PersonaProfile)
    assert isinstance(profile.grounded, GroundedAttributes)
    assert isinstance(profile.derived, DerivedAttributes)
    assert isinstance(profile.synthetic, SyntheticBehaviouralAttributes)

    # Check grounded attributes
    assert profile.grounded.district in EXAMPLE_POPULATION_CONFIG.district_distribution
    assert profile.grounded.gender in ["Female", "Male", "Non-Binary"]
    assert isinstance(profile.grounded.institution_type, InstitutionType)
    assert isinstance(profile.grounded.admission_mode, AdmissionMode)
    assert isinstance(profile.grounded.is_professional_course, bool)

    # Check derived attributes
    assert profile.derived.persona_id == "TEST-SYNTH-001"
    assert len(profile.derived.name) > 0
    assert 16 <= profile.derived.age <= 30
    assert profile.derived.family_income > 0
    assert profile.derived.annual_tuition_fee > 0
    assert 0.0 <= profile.derived.attendance_percentage <= 100.0

    # Check synthetic behavioral attributes
    assert 0.0 <= profile.synthetic.initial_awareness <= 1.0
    assert 0.0 <= profile.synthetic.digital_literacy <= 1.0
    assert 0.0 <= profile.synthetic.document_readiness <= 1.0
    assert 0.0 <= profile.synthetic.financial_urgency <= 1.0
    assert 0.0 <= profile.synthetic.peer_network_support <= 1.0
    assert 0.0 <= profile.synthetic.institutional_trust <= 1.0
    assert 0.0 <= profile.synthetic.personality.patience <= 1.0

    # Check conversion to Phase 1 StudentPersona
    student = profile.to_student_persona()
    assert isinstance(student, StudentPersona)
    assert student.persona_id == "TEST-SYNTH-001"
    assert student.district == profile.grounded.district
    assert student.family_income == profile.derived.family_income
    assert student.digital_literacy == profile.synthetic.digital_literacy
    print("PASS: test_generate_single_synthetic_student")


def test_required_scholarship_attributes_exist():
    """Verifies that all attributes checked by RajarshiShahuPolicyEngine exist and are valid."""
    generator = SyntheticPersonaGenerator(seed=101)
    student = generator.generate_student_persona()

    # Verify attributes required by statutory checks in policy_rules.py
    required_fields = [
        "persona_id",
        "name",
        "age",
        "gender",
        "district",
        "is_maharashtra_domicile",
        "family_income",
        "caste_category",
        "is_professional_course",
        "institution_type",
        "admission_mode",
        "family_beneficiaries_count",
        "has_other_scholarship",
        "previous_year_passed",
        "academic_gap_years",
        "attendance_percentage",
        "annual_tuition_fee",
        "digital_literacy",
        "initial_awareness",
        "document_readiness",
        "financial_urgency",
        "peer_network_support",
        "personality",
        "current_state"
    ]

    for field_name in required_fields:
        assert hasattr(student, field_name), f"Missing required scholarship attribute: {field_name}"
        val = getattr(student, field_name)
        assert val is not None, f"Attribute {field_name} must not be None"

    # Verify evaluation executes without exception
    is_eligible, checks, failures = RajarshiShahuPolicyEngine.check_statutory_eligibility(student)
    assert isinstance(is_eligible, bool)
    assert len(checks) == 8
    print("PASS: test_required_scholarship_attributes_exist")


def test_seed_reproducibility():
    """Verifies that identical random seeds produce 100% identical personas."""
    gen1 = SyntheticPersonaGenerator(seed=12345)
    gen2 = SyntheticPersonaGenerator(seed=12345)

    profile1 = gen1.generate_profile(persona_id="STU-A")
    profile2 = gen2.generate_profile(persona_id="STU-A")

    assert profile1.to_dict() == profile2.to_dict(), "Outputs with identical seeds must be identical"

    student1 = profile1.to_student_persona()
    student2 = profile2.to_student_persona()

    assert student1.name == student2.name
    assert student1.district == student2.district
    assert student1.family_income == student2.family_income
    assert student1.annual_tuition_fee == student2.annual_tuition_fee
    assert student1.digital_literacy == student2.digital_literacy
    assert student1.document_readiness == student2.document_readiness
    assert student1.personality.patience == student2.personality.patience

    # Also verify that a different seed produces different attributes
    gen_different = SyntheticPersonaGenerator(seed=99999)
    profile_diff = gen_different.generate_profile(persona_id="STU-A")
    assert profile1.to_dict() != profile_diff.to_dict()
    print("PASS: test_seed_reproducibility")


def test_attribute_provenance_separation():
    """Verifies that the schema preserves strict provenance separation and lookup."""
    schema = PersonaProfile.get_provenance_schema()

    # Grounded fields
    assert schema["district"] == AttributeProvenance.GROUNDED
    assert schema["gender"] == AttributeProvenance.GROUNDED
    assert schema["caste_category"] == AttributeProvenance.GROUNDED
    assert schema["institution_type"] == AttributeProvenance.GROUNDED
    assert schema["admission_mode"] == AttributeProvenance.GROUNDED

    # Derived fields
    assert schema["family_income"] == AttributeProvenance.DERIVED
    assert schema["annual_tuition_fee"] == AttributeProvenance.DERIVED
    assert schema["age"] == AttributeProvenance.DERIVED
    assert schema["course_name"] == AttributeProvenance.DERIVED
    assert schema["first_generation_learner"] == AttributeProvenance.DERIVED

    # Synthetic fields
    assert schema["initial_awareness"] == AttributeProvenance.SYNTHETIC
    assert schema["digital_literacy"] == AttributeProvenance.SYNTHETIC
    assert schema["document_readiness"] == AttributeProvenance.SYNTHETIC
    assert schema["financial_urgency"] == AttributeProvenance.SYNTHETIC
    assert schema["peer_network_support"] == AttributeProvenance.SYNTHETIC
    assert schema["institutional_trust"] == AttributeProvenance.SYNTHETIC
    assert schema["personality"] == AttributeProvenance.SYNTHETIC

    # Metadata disclaimer check
    gen = SyntheticPersonaGenerator(seed=77)
    profile = gen.generate_profile()
    assert profile.metadata["is_example_placeholder"] is True
    assert "data_disclaimer" in profile.metadata
    print("PASS: test_attribute_provenance_separation")


def test_simulation_engine_compatibility_with_generated_persona():
    """Verifies that a generated synthetic persona executes end-to-end through SimulationEngine."""
    generator = SyntheticPersonaGenerator(seed=2024)
    student = generator.generate_student_persona(persona_id="SYNTH-RUN-01")

    engine = SimulationEngine()
    step_output = engine.run_step(student)

    assert step_output.persona_id == "SYNTH-RUN-01"
    assert isinstance(step_output.is_eligible, bool)
    assert isinstance(step_output.application_probability, float)
    assert step_output.final_simulation_state in [s.value for s in SimulationState]
    assert len(step_output.inner_monologue) > 0
    assert len(step_output.stated_intention) > 0
    print("PASS: test_simulation_engine_compatibility_with_generated_persona")



def test_custom_population_distribution_injection():
    """Verifies that the generator works seamlessly with custom user-provided distributions."""
    custom_config = PopulationDistributionConfig(
        config_name="Custom-Rural-Tribal-Test-Cohort",
        description="Test config with 100% Gadchiroli ST population.",
        is_example_placeholder=False,
        district_distribution={"Gadchiroli": 1.0},
        district_region_mapping={"Gadchiroli": "Rural"},
        gender_distribution={"Female": 1.0},
        caste_category_distribution={"ST": 1.0},
        parental_education_distribution={"None": 1.0},
        institution_type_distribution={"Government": 1.0},
        admission_mode_distribution={"CAP": 1.0},
        course_level_distribution={"Undergraduate": 1.0},
        professional_probability_by_level={"Undergraduate": 1.0},
        courses_by_stream={"Professional": ["B.Tech Agriculture"]},
        income_brackets=[{"label": "BPL", "min_inr": 30000.0, "max_inr": 60000.0, "weight": 1.0}],
        tuition_fee_ranges={"Government:True": (20000.0, 30000.0)},
        attendance_mean_std=(85.0, 2.0),
        previous_year_pass_rate=1.0,
        previous_year_percentage_mean_std=(75.0, 5.0),
        gap_years_distribution={0: 1.0},
        beneficiaries_count_distribution={0: 1.0},
        other_scholarship_probability=0.0,
        behavioral_priors={
            "initial_awareness": (0.30, 0.05),
            "digital_literacy": (0.40, 0.05),
            "document_readiness": (0.40, 0.05),
            "financial_urgency": (0.90, 0.05),
            "peer_network_support": (0.35, 0.05),
            "institutional_trust": (0.50, 0.05),
        },
        personality_priors={
            "patience": (0.6, 0.05),
            "diligence": (0.6, 0.05),
            "risk_aversion": (0.5, 0.05),
            "self_advocacy": (0.5, 0.05),
        },
        first_names_by_gender={"Female": ["Sunita"]},
        last_names=["Madavi"]
    )

    gen = SyntheticPersonaGenerator(config=custom_config, seed=55)
    student = gen.generate_student_persona()

    assert student.district == "Gadchiroli"
    assert student.gender == "Female"
    assert student.caste_category == "ST"
    assert student.name == "Sunita Madavi"
    assert student.course_name == "B.Tech Agriculture"
    assert student.first_generation_learner is True
    assert 30000.0 <= student.family_income <= 60000.0
    print("PASS: test_custom_population_distribution_injection")


if __name__ == "__main__":
    test_generate_single_synthetic_student()
    test_required_scholarship_attributes_exist()
    test_seed_reproducibility()
    test_attribute_provenance_separation()
    test_simulation_engine_compatibility_with_generated_persona()
    test_custom_population_distribution_injection()
    print("All Phase 2 persona foundation tests passed successfully!")
