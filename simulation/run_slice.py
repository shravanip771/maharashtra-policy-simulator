"""
Phase 1 Vertical Slice Test Runner
Demonstrates single-persona simulation execution for Rajarshi Chhatrapati Shahu Maharaj Scheme.
"""

import json
from simulation.persona import (
    StudentPersona,
    InstitutionType,
    AdmissionMode,
    PersonalityTraits,
    SimulationState
)
from simulation.engine import SimulationEngine

def run_single_persona_demo():
    print("=" * 80)
    print("MAHARASHTRA POLICY SIMULATOR - PHASE 1 VERTICAL SLICE")
    print("Policy: Rajarshi Chhatrapati Shahu Maharaj Shikshan Shulk Shishyavrutti Yojna")
    print("=" * 80)

    # Instantiate one realistic synthetic student persona
    # Aarav Kulkarni: Engineering student from Nanded, Maharashtra
    student = StudentPersona(
        persona_id="MH-STU-001",
        name="Aarav Kulkarni",
        age=19,
        gender="Male",
        district="Nanded",
        is_maharashtra_domicile=True,
        family_income=240000.0,            # INR 2.40 Lakhs/annum (eligible, < 8L cap)
        caste_category="General-EBC",
        first_generation_learner=True,
        parental_education_level="Secondary",
        course_name="B.Tech Mechanical Engineering",
        course_level="Undergraduate",
        is_professional_course=True,
        institution_type=InstitutionType.PRIVATE_UNAIDED,
        admission_mode=AdmissionMode.CAP,
        annual_tuition_fee=95000.0,        # INR 95,000 annual college fee
        attendance_percentage=82.5,
        previous_year_passed=True,
        previous_year_percentage=68.4,
        academic_gap_years=0,
        family_beneficiaries_count=0,      # 1st beneficiary in family (< 2 limit)
        has_other_scholarship=False,
        # Behavioral & Capability Factors
        digital_literacy=0.65,
        initial_awareness=0.55,
        document_readiness=0.70,           # Has income certificate in progress
        financial_urgency=0.85,
        peer_network_support=0.60,
        personality=PersonalityTraits(
            patience=0.60,
            diligence=0.75,
            risk_aversion=0.40,
            self_advocacy=0.70
        ),
        current_state=SimulationState.UNINFORMED
    )

    print(f"\n[1] Initial Persona Created:")
    print(f"    Name: {student.name} ({student.gender}, age {student.age})")
    print(f"    District: {student.district} | Family Income: INR {student.family_income:,.2f}")
    print(f"    Course: {student.course_name} at {student.institution_type.value} College")
    print(f"    Admission Mode: {student.admission_mode.value} | Annual Fee: INR {student.annual_tuition_fee:,.2f}")
    print(f"    Initial State: {student.current_state.value}")

    # Run simulation step
    engine = SimulationEngine()
    output = engine.run_step(persona=student, step_index=1)

    print("\n[2] Simulation Step Executed (Observe -> Reason -> Act -> Update State)")
    print("-" * 80)
    print(f"Scheme: {output.scheme_name}")
    print(f"Statutory Eligibility: {'ELIGIBLE' if output.is_eligible else 'INELIGIBLE'}")
    print(f"Fee Relief Awarded: INR {output.estimated_fee_relief_inr:,.2f} ({output.reimbursement_percentage * 100:.0f}%)")
    print(f"Awareness Score: {output.awareness_score:.2f}")
    print(f"Perceived Benefit Score: {output.perceived_benefit_score:.2f}")
    print(f"Application Probability: {output.application_probability * 100:.1f}%")
    print(f"Completion / Scrutiny Probability: {output.completion_probability * 100:.1f}%")
    print(f"Expected Uptake Probability: {output.expected_uptake_probability * 100:.1f}%")
    print(f"Attempted Application: {output.attempted_application}")
    print(f"Completed Application: {output.completed_application}")
    print(f"Final Benefit Received: {output.benefit_received}")
    print(f"Updated Persona State: {output.final_simulation_state}")

    print("\n[3] AI Persona Reasoning & Qualitative Barrier Analysis:")
    print(f"    Inner Monologue:\n      \"{output.inner_monologue}\"")
    print(f"    Stated Intention: {output.stated_intention}")
    print(f"    Chosen Action: {output.chosen_action} (Confidence: {output.confidence_level})")
    print("    Perceived Barriers:")
    for barrier in output.perceived_barriers:
        print(f"      * {barrier}")

    print("\n[4] Complete JSON Output Payload:")
    print(output.to_json(indent=2))
    print("=" * 80)

if __name__ == "__main__":
    run_single_persona_demo()
