"""
Tests for District Configuration & Multi-District Population Generation (Vardayini Module).

Verifies:
1. District-specific generation for Pilot and Provisional districts.
2. Deterministic reproducibility with random seed.
3. Multiple district generation and exact quota fulfillment.
4. Large-scale state generation (1,000 personas across 18 districts).
5. Persona schema compatibility and taluka attribute attachment.
6. Natural generation of both statutorily eligible and ineligible students.
7. Error handling for missing or unsupported district identifiers.
8. Incomplete / provisional configuration handling with fallback priors.
9. Backward compatibility with the original Phase 2 generator interface.
"""

import pytest
from typing import Dict, List

from simulation.persona import StudentPersona, InstitutionType, AdmissionMode
from simulation.persona_schema import GroundedAttributes, PersonaProfile
from simulation.persona_generator import SyntheticPersonaGenerator, EXAMPLE_POPULATION_CONFIG
from simulation.district_config import (
    DISTRICT_REGISTRY,
    DistrictProfile,
    get_district_profile,
    get_district_population_config,
    list_supported_districts,
)
from simulation.policy_rules import RajarshiShahuPolicyEngine


class TestDistrictConfiguration:
    """Verifies district configuration data structures and empirical grounding."""

    def test_all_18_assigned_districts_registered(self):
        """Confirms that all 18 required Maharashtra districts are registered."""
        expected_districts = {
            "Ahilyanagar",
            "Akola",
            "Amravati",
            "Beed",
            "Bhandara",
            "Buldhana",
            "Chandrapur",
            "Chhatrapati Sambhajinagar",
            "Dharashiv",
            "Dhule",
            "Gadchiroli",
            "Gondia",
            "Hingoli",
            "Jalgaon",
            "Jalna",
            "Kolhapur",
            "Latur",
            "Mumbai City",
        }
        supported = set(list_supported_districts())
        assert expected_districts.issubset(supported)
        assert len(supported) == 18

    def test_two_pilot_districts_have_empirical_provenance(self):
        """Verifies that Dhule and Mumbai City are flagged as empirical observed pilots."""
        dhule = get_district_profile("Dhule")
        assert dhule.provenance_tier == "empirical_observed"
        assert "2010-11" in dhule.reference_year
        assert len(dhule.talukas) == 4
        assert "Shirpur" in dhule.talukas
        assert dhule.available_statistics["total_higher_ed_enrolment"] == 28652

        mumbai = get_district_profile("Mumbai City")
        assert mumbai.provenance_tier == "empirical_observed"
        assert "2021-22" in mumbai.reference_year
        assert mumbai.region_type == "Urban"
        assert mumbai.professional_stream_ratio == 0.380
        assert mumbai.talukas == ["Mumbai City"]
        assert mumbai.taluka_distribution is None

    def test_provisional_districts_explicitly_catalog_missing_data(self):
        """Verifies that non-pilot districts clearly document missing data and fallbacks."""
        gadchiroli = get_district_profile("Gadchiroli")
        assert gadchiroli.provenance_tier == "provisional_baseline"
        assert len(gadchiroli.missing_data) > 0
        assert "cap_seat_allotment_vacancy_rate" in gadchiroli.missing_data
        assert gadchiroli.caste_category_distribution["ST"] == 0.38  # High tribal representation

        beed = get_district_profile("Beed")
        assert beed.provenance_tier == "provisional_baseline"
        assert beed.region_type == "Rural"
        assert len(beed.missing_data) > 0

    def test_missing_district_raises_informative_key_error(self):
        """Verifies that requesting an unregistered district raises KeyError with supported options."""
        with pytest.raises(KeyError) as exc_info:
            get_district_profile("NonExistentDistrictXYZ")
        assert "Supported districts" in str(exc_info.value)


class TestDistrictPersonaGenerator:
    """Verifies SyntheticPersonaGenerator district extensions and population generation."""

    def test_district_specific_generation_dhule(self):
        """Generates cohort for Dhule and validates district-specific attributes."""
        gen = SyntheticPersonaGenerator.for_district("Dhule", seed=42)
        students = gen.generate_cohort(count=20)

        assert len(students) == 20
        for s in students:
            assert s.district == "Dhule"
            assert hasattr(s, "taluka")
            assert s.taluka in ["Dhule", "Shirpur", "Sindkhede", "Sakri"]
            assert s.institution_type in [InstitutionType.GOVERNMENT_AIDED, InstitutionType.PRIVATE_UNAIDED]
            assert s.annual_tuition_fee > 0

    def test_district_specific_generation_mumbai_city(self):
        """Generates cohort for Mumbai City and validates metropolitan characteristics."""
        gen = SyntheticPersonaGenerator.for_district("Mumbai City", seed=101)
        students = gen.generate_cohort(count=20)

        assert len(students) == 20
        for s in students:
            assert s.district == "Mumbai City"
            assert hasattr(s, "taluka")
            assert s.taluka == "Mumbai City"
            assert s.annual_tuition_fee > 0

    def test_reproducibility_with_same_seed(self):
        """Verifies deterministic identity when using the same seed."""
        gen1 = SyntheticPersonaGenerator.for_district("Kolhapur", seed=999)
        gen2 = SyntheticPersonaGenerator.for_district("Kolhapur", seed=999)

        c1 = gen1.generate_cohort(count=10)
        c2 = gen2.generate_cohort(count=10)

        for s1, s2 in zip(c1, c2):
            assert s1.persona_id == s2.persona_id
            assert s1.name == s2.name
            assert s1.family_income == s2.family_income
            assert s1.annual_tuition_fee == s2.annual_tuition_fee
            assert s1.digital_literacy == s2.digital_literacy
            assert s1.document_readiness == s2.document_readiness
            assert getattr(s1, "taluka", None) == getattr(s2, "taluka", None)

    def test_variance_across_differing_seeds(self):
        """Verifies that different seeds produce diverse student personas."""
        gen1 = SyntheticPersonaGenerator.for_district("Pune", seed=111) if "Pune" in list_supported_districts() else SyntheticPersonaGenerator.for_district("Amravati", seed=111)
        gen2 = SyntheticPersonaGenerator.for_district(gen1.district, seed=222)

        c1 = gen1.generate_cohort(count=5)
        c2 = gen2.generate_cohort(count=5)

        names1 = [s.name for s in c1]
        names2 = [s.name for s in c2]
        assert names1 != names2

    def test_multidistrict_population_exact_quotas(self):
        """Verifies generating exact quotas across multiple distinct districts."""
        quotas = {
            "Dhule": 15,
            "Mumbai City": 25,
            "Kolhapur": 20,
            "Gadchiroli": 10,
        }
        students = SyntheticPersonaGenerator.generate_multidistrict_population(
            district_quotas=quotas,
            seed=42,
        )

        assert len(students) == 70

        # Verify exact counts per district
        counts: Dict[str, int] = {}
        for s in students:
            counts[s.district] = counts.get(s.district, 0) + 1

        assert counts == quotas

        # Verify globally unique persona IDs
        ids = [s.persona_id for s in students]
        assert len(ids) == len(set(ids))

    def test_statewide_1000_persona_generation(self):
        """
        Generates a 1,000-person synthetic student population distributed across
        all 18 configured Maharashtra districts.
        """
        population = SyntheticPersonaGenerator.generate_state_population(
            total_count=1000,
            seed=42,
        )

        assert len(population) == 1000

        # Verify all 18 districts are represented
        districts_in_sample = {s.district for s in population}
        assert len(districts_in_sample) == 18

        # Verify all persona IDs are unique
        ids = {s.persona_id for s in population}
        assert len(ids) == 1000

        # Check gender breakdown is plausible across state
        females = sum(1 for s in population if s.gender == "Female")
        males = sum(1 for s in population if s.gender == "Male")
        assert 350 < females < 600
        assert 400 < males < 650

    def test_eligible_and_ineligible_generation_without_hardcoded_rules(self):
        """
        Verifies that the generator naturally produces both statutorily eligible
        and ineligible students based on demographic and academic attributes,
        evaluated through the official Policy Engine interface.
        """
        gen = SyntheticPersonaGenerator.for_district("Ahilyanagar", seed=555)
        students = gen.generate_cohort(count=50)

        eligible_count = 0
        ineligible_count = 0
        observed_failure_reasons = set()

        for s in students:
            eval_res = RajarshiShahuPolicyEngine.evaluate_eligibility(s)
            if eval_res.is_eligible:
                eligible_count += 1
                assert eval_res.estimated_fee_relief_inr > 0
            else:
                ineligible_count += 1
                for r in eval_res.failure_reasons:
                    observed_failure_reasons.add(r)

        # Both classes must be naturally represented in a 50-student cohort
        assert eligible_count > 0, "Cohort must contain eligible students"
        assert ineligible_count > 0, "Cohort must contain ineligible students"
        assert len(observed_failure_reasons) > 0

    def test_backward_compatibility_with_existing_generator(self):
        """Verifies that instantiating SyntheticPersonaGenerator without new args works seamlessly."""
        legacy_gen = SyntheticPersonaGenerator(seed=42)
        assert legacy_gen.config == EXAMPLE_POPULATION_CONFIG
        p = legacy_gen.generate_student_persona()
        assert isinstance(p, StudentPersona)
        assert p.persona_id.startswith("SYNTH-STU-")

        cohort = legacy_gen.generate_cohort(count=10, seed=42)
        assert len(cohort) == 10
        assert cohort[0].persona_id == "DHULE-STU-001"

    def test_multidistrict_population_empty_quota(self):
        """Verifies that an empty quota dictionary returns an empty list without error."""
        students = SyntheticPersonaGenerator.generate_multidistrict_population({}, seed=42)
        assert students == []

    def test_statewide_quota_distribution_bounds(self):
        """Verifies that 1,000 personas are evenly bounded across all 18 districts (55 or 56 each)."""
        population = SyntheticPersonaGenerator.generate_state_population(total_count=1000, seed=42)
        from collections import Counter
        district_counts = Counter(s.district for s in population)
        assert len(district_counts) == 18
        for dist_name, count in district_counts.items():
            assert count in (55, 56), f"District {dist_name} count {count} is outside expected bounds [55, 56]"
