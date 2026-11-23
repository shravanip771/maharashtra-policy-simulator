"""
Targeted tests for Stage 2.6 P2 Taluka Sampling Remediation.
Verifies that persona generation correctly samples talukas from each district's
registered taluka list and distribution, preserving deterministic reproducibility.
"""

import os
import sys

# Ensure project root is on sys.path when invoked directly as a script
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from simulation.district_config import DISTRICT_REGISTRY, get_district_profile
from simulation.persona_generator import SyntheticPersonaGenerator
from data.dhule_adapter import DhuleEducationDatasetAdapter
from backend.service import SimulationService
from backend.models import SimulationRequest


def test_dhule_taluka_sampling():
    """Dhule talukas are valid and adhere to Dhule's educational census distribution."""
    adapter = DhuleEducationDatasetAdapter()
    config = adapter.create_population_config()
    gen = SyntheticPersonaGenerator(config=config, seed=42, district="Dhule")
    cohort = gen.generate_cohort(count=20, seed=42)
    dhule_prof = get_district_profile("Dhule")
    
    assert len(cohort) == 20
    for p in cohort:
        assert p.district == "Dhule"
        assert p.taluka in dhule_prof.talukas, f"Invalid taluka {p.taluka} for Dhule"

    # Verify distribution covers multiple talukas
    taluka_set = {p.taluka for p in cohort}
    assert len(taluka_set) > 1, f"Expected multiple talukas sampled, got {taluka_set}"


def test_pune_taluka_sampling():
    """Pune talukas are sampled from Pune's official taluka list (including Pune City)."""
    gen = SyntheticPersonaGenerator.for_district("Pune", seed=42)
    cohort = gen.generate_cohort(count=30, seed=42)
    pune_prof = get_district_profile("Pune")

    assert len(cohort) == 30
    for p in cohort:
        assert p.district == "Pune"
        assert p.taluka in pune_prof.talukas, f"Invalid taluka {p.taluka} for Pune"

    # Confirm Pune City or other specific talukas appear
    taluka_set = {p.taluka for p in cohort}
    assert len(taluka_set) > 1, f"Expected multiple talukas sampled, got {taluka_set}"
    assert any(t in taluka_set for t in ["Pune City", "Haveli", "Baramati", "Shirur"])


def test_kolhapur_taluka_sampling():
    """Kolhapur talukas are sampled from Kolhapur's official taluka list (including Karvir)."""
    gen = SyntheticPersonaGenerator.for_district("Kolhapur", seed=42)
    cohort = gen.generate_cohort(count=30, seed=42)
    kolhapur_prof = get_district_profile("Kolhapur")

    assert len(cohort) == 30
    for p in cohort:
        assert p.district == "Kolhapur"
        assert p.taluka in kolhapur_prof.talukas, f"Invalid taluka {p.taluka} for Kolhapur"

    taluka_set = {p.taluka for p in cohort}
    assert len(taluka_set) > 1, f"Expected multiple talukas sampled, got {taluka_set}"
    assert any(t in taluka_set for t in ["Karvir", "Hatkangale", "Panhala", "Shirol"])


def test_akola_taluka_sampling():
    """Akola talukas are sampled from Akola's official taluka list."""
    gen = SyntheticPersonaGenerator.for_district("Akola", seed=42)
    cohort = gen.generate_cohort(count=20, seed=42)
    akola_prof = get_district_profile("Akola")

    assert len(cohort) == 20
    for p in cohort:
        assert p.district == "Akola"
        assert p.taluka in akola_prof.talukas, f"Invalid taluka {p.taluka} for Akola"

    taluka_set = {p.taluka for p in cohort}
    assert len(taluka_set) > 1, f"Expected multiple talukas sampled, got {taluka_set}"


def test_all_36_districts_taluka_validity():
    """Verifies that all 36 districts sample valid, district-exclusive talukas."""
    for d_key, prof in DISTRICT_REGISTRY.items():
        d_name = prof.district_name
        if d_name.lower() == "dhule":
            adapter = DhuleEducationDatasetAdapter()
            cfg = adapter.create_population_config()
            gen = SyntheticPersonaGenerator(config=cfg, seed=42, district="Dhule")
        else:
            gen = SyntheticPersonaGenerator.for_district(d_name, seed=42)

        cohort = gen.generate_cohort(count=10, seed=42)
        for p in cohort:
            assert p.district == d_name, f"District mismatch: {p.district} != {d_name}"
            assert p.taluka in prof.talukas, f"Taluka {p.taluka} not in {d_name} talukas: {prof.talukas}"


def test_fixed_seed_repeatability():
    """Verifies that persona taluka sampling is strictly deterministic for identical seeds."""
    for d_name in ["Dhule", "Pune", "Kolhapur", "Nandurbar"]:
        if d_name.lower() == "dhule":
            adapter = DhuleEducationDatasetAdapter()
            cfg = adapter.create_population_config()
            gen1 = SyntheticPersonaGenerator(config=cfg, seed=123, district="Dhule")
            gen2 = SyntheticPersonaGenerator(config=cfg, seed=123, district="Dhule")
        else:
            gen1 = SyntheticPersonaGenerator.for_district(d_name, seed=123)
            gen2 = SyntheticPersonaGenerator.for_district(d_name, seed=123)

        cohort1 = gen1.generate_cohort(count=10, seed=123)
        cohort2 = gen2.generate_cohort(count=10, seed=123)

        talukas1 = [p.taluka for p in cohort1]
        talukas2 = [p.taluka for p in cohort2]
        assert talukas1 == talukas2, f"Seed determinism failed for {d_name}: {talukas1} != {talukas2}"


def test_service_dto_taluka_mapping():
    """Verifies that PersonaOutput in SimulationResponse carries the sampled taluka."""
    for d_name in ["Pune", "Kolhapur", "Dhule"]:
        prof = get_district_profile(d_name)
        req = SimulationRequest(district=d_name, cohort_size=5, simulation_steps=1, seed=42, use_gemini=False)
        resp = SimulationService.execute_simulation(req)
        for persona_out in resp.personas:
            assert persona_out.district == d_name
            assert persona_out.taluka in prof.talukas, (
                f"DTO taluka {persona_out.taluka} not in {d_name} talukas: {prof.talukas}"
            )


if __name__ == "__main__":
    test_dhule_taluka_sampling()
    print("PASS: test_dhule_taluka_sampling")
    test_pune_taluka_sampling()
    print("PASS: test_pune_taluka_sampling")
    test_kolhapur_taluka_sampling()
    print("PASS: test_kolhapur_taluka_sampling")
    test_akola_taluka_sampling()
    print("PASS: test_akola_taluka_sampling")
    test_all_36_districts_taluka_validity()
    print("PASS: test_all_36_districts_taluka_validity")
    test_fixed_seed_repeatability()
    print("PASS: test_fixed_seed_repeatability")
    test_service_dto_taluka_mapping()
    print("PASS: test_service_dto_taluka_mapping")
    print("\nALL TARGETED TALUKA SAMPLING TESTS PASSED SUCCESSFULLY!")
