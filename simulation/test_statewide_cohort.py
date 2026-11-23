"""
Targeted tests for Phase 1A Statewide Cohort Generation.
Verifies that SyntheticPersonaGenerator.generate_statewide_cohort():
1. Generates exactly 36 * count_per_district personas (default 180).
2. Represents all 36 districts in DISTRICT_REGISTRY without omissions.
3. Correctly assigns district and valid district-exclusive talukas to every persona.
4. Preserves deterministic fixed-seed repeatability and seed variance.
5. Ensures isolated district seeds prevent cross-district RNG interference.
6. Preserves existing single-district generator behavior without regression.
"""

import hashlib
import os
import sys

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from simulation.district_config import DISTRICT_REGISTRY, get_district_profile
from simulation.persona import StudentPersona
from simulation.persona_generator import SyntheticPersonaGenerator


def test_statewide_cohort_size_and_all_36_districts():
    """Verifies total count = 180 and all 36 districts are represented with exactly 5 personas each."""
    cohort = SyntheticPersonaGenerator.generate_statewide_cohort(count_per_district=5, seed=42)

    assert len(cohort) == 180, f"Expected 180 personas, got {len(cohort)}"
    assert all(isinstance(p, StudentPersona) for p in cohort)

    # Check distribution of personas across districts
    district_counts = {}
    for p in cohort:
        district_counts[p.district] = district_counts.get(p.district, 0) + 1

    assert len(district_counts) == 36, f"Expected 36 districts represented, got {len(district_counts)}"

    for d_key, prof in DISTRICT_REGISTRY.items():
        d_name = prof.district_name
        assert d_name in district_counts, f"District {d_name} missing from statewide cohort"
        assert district_counts[d_name] == 5, f"Expected 5 personas for {d_name}, got {district_counts[d_name]}"


def test_configurable_count_per_district():
    """Verifies that count_per_district scales total cohort size deterministically and validates bounds."""
    cohort_2 = SyntheticPersonaGenerator.generate_statewide_cohort(count_per_district=2, seed=42)
    assert len(cohort_2) == 72  # 36 * 2

    cohort_1 = SyntheticPersonaGenerator.generate_statewide_cohort(count_per_district=1, seed=42)
    assert len(cohort_1) == 36  # 36 * 1

    try:
        SyntheticPersonaGenerator.generate_statewide_cohort(count_per_district=0, seed=42)
        assert False, "Expected ValueError for count_per_district=0"
    except ValueError:
        pass


def test_statewide_district_and_taluka_validity():
    """Verifies that every persona has valid district and valid district-exclusive taluka."""
    cohort = SyntheticPersonaGenerator.generate_statewide_cohort(count_per_district=5, seed=42)

    for p in cohort:
        assert p.district is not None
        prof = get_district_profile(p.district)
        assert prof is not None
        assert p.district == prof.district_name
        assert hasattr(p, "taluka")
        assert p.taluka in prof.talukas, f"Persona {p.persona_id} has invalid taluka '{p.taluka}' for district '{p.district}'"


def test_statewide_fixed_seed_repeatability():
    """Verifies identical personas are generated for identical seeds, and differ across seeds."""
    cohort_run1 = SyntheticPersonaGenerator.generate_statewide_cohort(count_per_district=3, seed=42)
    cohort_run2 = SyntheticPersonaGenerator.generate_statewide_cohort(count_per_district=3, seed=42)
    cohort_run3 = SyntheticPersonaGenerator.generate_statewide_cohort(count_per_district=3, seed=999)

    assert len(cohort_run1) == len(cohort_run2) == 108

    for p1, p2 in zip(cohort_run1, cohort_run2):
        assert p1.persona_id == p2.persona_id
        assert p1.name == p2.name
        assert p1.district == p2.district
        assert p1.taluka == p2.taluka
        assert p1.gender == p2.gender
        assert p1.family_income == p2.family_income
        assert p1.annual_tuition_fee == p2.annual_tuition_fee
        assert p1.initial_awareness == p2.initial_awareness

    # Verify seed 999 differs
    different_names = sum(1 for p1, p3 in zip(cohort_run1, cohort_run3) if p1.name != p3.name)
    assert different_names > 50, f"Expected substantial divergence between different seeds, got {different_names}"


def test_district_isolation_and_no_interference():
    """Verifies that district persona sampling is isolated and repeatable individually."""
    # Run statewide cohort with seed 42
    statewide = SyntheticPersonaGenerator.generate_statewide_cohort(count_per_district=5, seed=42)
    pune_from_statewide = [p for p in statewide if p.district == "Pune"]
    assert len(pune_from_statewide) == 5

    # Derive Pune's isolated seed using the exact same formula
    pune_prof = get_district_profile("Pune")
    pune_seed = int(hashlib.sha256(f"42:{pune_prof.district_id}".encode("utf-8")).hexdigest()[:8], 16) & 0x7FFFFFFF

    # Generate Pune directly with its isolated seed
    pune_gen = SyntheticPersonaGenerator.for_district("Pune", seed=pune_seed)
    pune_direct = pune_gen.generate_cohort(count=5, id_prefix="PUNE-STU", start_index=1, seed=pune_seed)

    for p_sw, p_dir in zip(pune_from_statewide, pune_direct):
        assert p_sw.name == p_dir.name
        assert p_sw.taluka == p_dir.taluka
        assert p_sw.family_income == p_dir.family_income
        assert p_sw.initial_awareness == p_dir.initial_awareness


def test_existing_district_generator_unaffected():
    """Verifies that single-district generation and default generation continue to work as before."""
    # Default generator
    default_gen = SyntheticPersonaGenerator(seed=42)
    p1 = default_gen.generate_student_persona()
    assert isinstance(p1, StudentPersona)

    # for_district generator
    dhule_gen = SyntheticPersonaGenerator.for_district("Dhule", seed=42)
    dhule_cohort = dhule_gen.generate_cohort(count=5)
    assert len(dhule_cohort) == 5
    assert all(p.district == "Dhule" for p in dhule_cohort)

    kolhapur_gen = SyntheticPersonaGenerator.for_district("Kolhapur", seed=42)
    kolhapur_cohort = kolhapur_gen.generate_cohort(count=5)
    assert len(kolhapur_cohort) == 5
    assert all(p.district == "Kolhapur" for p in kolhapur_cohort)


if __name__ == "__main__":
    print("Running test_statewide_cohort_size_and_all_36_districts...")
    test_statewide_cohort_size_and_all_36_districts()
    print("PASS: test_statewide_cohort_size_and_all_36_districts")

    print("Running test_configurable_count_per_district...")
    test_configurable_count_per_district()
    print("PASS: test_configurable_count_per_district")

    print("Running test_statewide_district_and_taluka_validity...")
    test_statewide_district_and_taluka_validity()
    print("PASS: test_statewide_district_and_taluka_validity")

    print("Running test_statewide_fixed_seed_repeatability...")
    test_statewide_fixed_seed_repeatability()
    print("PASS: test_statewide_fixed_seed_repeatability")

    print("Running test_district_isolation_and_no_interference...")
    test_district_isolation_and_no_interference()
    print("PASS: test_district_isolation_and_no_interference")

    print("Running test_existing_district_generator_unaffected...")
    test_existing_district_generator_unaffected()
    print("PASS: test_existing_district_generator_unaffected")

    print("\nALL 6 STATEWIDE COHORT FOCUSED TESTS PASSED SUCCESSFULLY!")
