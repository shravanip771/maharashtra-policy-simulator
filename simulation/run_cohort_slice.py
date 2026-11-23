"""
Maharashtra Policy Simulator - 10-Persona Cohort Simulation Runner
Executes population simulation for 10 personas using the Dhule empirical dataset
against the Rajarshi Chhatrapati Shahu Maharaj Shikshan Shulk Shishyavrutti Yojna policy.
"""

import json
from data.dhule_adapter import DhuleEducationDatasetAdapter
from simulation.persona_generator import SyntheticPersonaGenerator
from simulation.engine import SimulationEngine, CohortSimulationResult

def run_10_person_dhule_cohort(seed: int = 42, assumed_reimbursement_rate: float = 0.50) -> CohortSimulationResult:
    # 1. Load Dhule empirical configuration
    dhule_config = DhuleEducationDatasetAdapter.create_population_config()

    # 2. Instantiate persona generator with fixed seed
    generator = SyntheticPersonaGenerator(config=dhule_config, seed=seed)

    # 3. Generate exactly 10 personas with unique IDs
    student_population = generator.generate_student_population(
        count=10,
        id_prefix="DHULE-STU",
        start_index=1
    )

    # 4. Run cohort evaluation through SimulationEngine
    engine = SimulationEngine()
    cohort_result = engine.run_cohort(
        personas=student_population,
        cohort_name="Dhule-10-Student-MVP-Cohort",
        seed=seed,
        assumed_reimbursement_rate=assumed_reimbursement_rate
    )

    return cohort_result

def print_cohort_report(result: CohortSimulationResult) -> None:
    print("=" * 80)
    print("MAHARASHTRA POLICY SIMULATOR - 10-PERSONA POPULATION SIMULATION")
    print("Policy: Rajarshi Chhatrapati Shahu Maharaj Shikshan Shulk Shishyavrutti Yojna")
    print(f"Cohort: {result.cohort_name} | Seed: {result.seed} | Population: {result.total_personas}")
    print("=" * 80)

    print("\n--- 1. INDIVIDUAL PERSONA RESULTS ---")
    for i, ind in enumerate(result.individual_results, 1):
        status_symbol = "[ELIGIBLE]" if ind.is_eligible else "[INELIGIBLE]"
        demo = ind.demographics_summary
        print(f"\n[{i:02d}] {ind.persona_id}: {ind.persona_name} ({demo['gender']}, Age {demo['age']}, {demo['district']})")
        print(f"     Course: {demo['course']} | Type: {demo['institution_type']} | Mode: {demo['admission_mode']}")
        print(f"     Income: INR {demo['family_income']:,.0f} | Caste: {demo['caste_category']} | Fee: INR {demo['annual_tuition_fee']:,.0f}")
        print(f"     Statutory Evaluation: {status_symbol}")

        if ind.is_eligible:
            print(f"     Estimated Benefit Relief: INR {ind.estimated_fee_relief_inr:,.0f} ({ind.reimbursement_percentage*100:.0f}% PoC rate)")
        else:
            print(f"     Failure Reasons: {'; '.join(ind.statutory_failure_reasons)}")
        print(f"     Probabilities: Awareness={ind.awareness_score:.2f}, Apply={ind.application_probability:.2f}, Complete={ind.completion_probability:.2f}, Uptake={ind.expected_uptake_probability:.2f}")
        print(f"     Final State: {ind.final_simulation_state} | Stated Intention: {ind.stated_intention}")

    print("\n" + "=" * 80)
    print("--- 2. AGGREGATE COHORT SUMMARY ---")
    print(f"Total Personas Evaluated: {result.total_personas}")
    print(f"Eligible Count:           {result.eligible_count} ({result.eligibility_rate*100:.1f}%)")
    print(f"Ineligible Count:         {result.ineligible_count} ({(1-result.eligibility_rate)*100:.1f}%)")
    print(f"Total Estimated Relief:   INR {result.total_estimated_fee_relief_inr:,.0f}")
    print(f"Avg Relief (Per Eligible):INR {result.average_fee_relief_per_eligible_inr:,.0f}")
    print(f"Realized Benefit Uptake:  {result.benefit_received_count}/{result.total_personas} ({result.uptake_rate*100:.1f}%)")

    print("\n--- Average Behavioral & Decision Metrics ---")
    print(f"  * Mean Awareness Score:          {result.average_awareness_score:.3f}")
    print(f"  * Mean Perceived Benefit Score:  {result.average_perceived_benefit_score:.3f}")
    print(f"  * Mean Application Probability:  {result.average_application_probability:.3f}")
    print(f"  * Mean Completion Probability:   {result.average_completion_probability:.3f}")
    print(f"  * Mean Expected Uptake Score:    {result.average_expected_uptake_probability:.3f}")

    print("\n--- Breakdown by Gender ---")
    for g, data in result.breakdown_by_gender.items():
        print(f"  * {g:10s}: Total={data['total_count']}, Eligible={data['eligible_count']} ({data['eligibility_rate']*100:.1f}%), Uptake={data['benefit_received_count']} ({data['uptake_rate']*100:.1f}%), Total Relief=INR {data['total_relief_inr']:,.0f}")

    print("\n--- Breakdown by Institution Type ---")
    for inst, data in result.breakdown_by_institution_type.items():
        print(f"  * {inst:20s}: Total={data['total_count']}, Eligible={data['eligible_count']} ({data['eligibility_rate']*100:.1f}%), Uptake={data['benefit_received_count']}, Relief=INR {data['total_relief_inr']:,.0f}")

    if result.ineligibility_reasons_summary:
        print("\n--- Ineligibility Barrier Frequencies ---")
        for reason, count in result.ineligibility_reasons_summary.items():
            print(f"  * [{count} student(s)] {reason}")

    print("\n--- State Distribution ---")
    for st, count in result.state_distribution.items():
        print(f"  * {st:25s}: {count} student(s)")
    print("=" * 80)


if __name__ == "__main__":
    result = run_10_person_dhule_cohort(seed=42)
    print_cohort_report(result)
