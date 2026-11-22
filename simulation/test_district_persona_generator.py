"""
Tests for District Configuration & Multi-District Population Generation (Vardayini Module).

Verifies:
1. District-specific generation for Pilot and Provisional districts.
2. Deterministic reproducibility with random seed.
3. Multiple district generation and exact quota fulfillment.
4. Large-scale state generation (1,000 personas across 36 districts).
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
        """Confirms that the initial 18 required Maharashtra districts are registered and present."""
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
        assert len(supported) == 36
        assert len(supported) == len(DISTRICT_REGISTRY)

    def test_pune_and_nagpur_pilot_districts_registered(self):
        """Verifies that Pune and Nagpur are registered with provisional_baseline tier."""
        supported = set(list_supported_districts())
        assert "Pune" in supported
        assert "Nagpur" in supported

        pune = get_district_profile("Pune")
        assert pune.district_id == "PUNE"
        assert pune.district_name == "Pune"
        assert pune.division == "Pune"
        assert pune.region_type == "Urban"
        assert pune.provenance_tier == "provisional_baseline"
        assert "2011" in pune.reference_year
        assert len(pune.talukas) == 14
        assert "Pune City" in pune.talukas
        assert "Haveli" in pune.talukas
        assert "Baramati" in pune.talukas

        # Available statistics must strictly record observed general-population census facts
        assert pune.available_statistics["census_reference_year"] == "2011"
        assert "General population" in pune.available_statistics["census_population_scope"]
        assert pune.available_statistics["total_population_2011"] == 9429408
        assert pune.available_statistics["urbanization_rate_2011"] == 0.6088
        assert pune.available_statistics["general_sex_ratio_2011"] == 915
        assert pune.available_statistics["scheduled_castes_population_2011"] == 1180689

        # Missing data catalog
        assert "taluka_wise_student_enrolment" in pune.missing_data
        assert "district_level_household_income_microdata" in pune.missing_data
        assert "caste_breakdown_in_private_engineering" in pune.missing_data

        # Assumptions and fallbacks documentation
        assert "region_type" in pune.assumptions_and_fallbacks
        assert "admission_mode_distribution" in pune.assumptions_and_fallbacks
        assert "gender_distribution" in pune.assumptions_and_fallbacks
        assert "caste_category_distribution" in pune.assumptions_and_fallbacks

        # Nagpur verification
        nagpur = get_district_profile("Nagpur")
        assert nagpur.district_id == "NAGPUR"
        assert nagpur.district_name == "Nagpur"
        assert nagpur.division == "Nagpur"
        assert nagpur.region_type == "Urban"
        assert nagpur.provenance_tier == "provisional_baseline"
        assert "2011" in nagpur.reference_year
        assert len(nagpur.talukas) == 14
        assert "Nagpur Urban" in nagpur.talukas
        assert "Nagpur Rural" in nagpur.talukas
        assert "Hingna" in nagpur.talukas

        # Available statistics for Nagpur
        assert nagpur.available_statistics["census_reference_year"] == "2011"
        assert "General population" in nagpur.available_statistics["census_population_scope"]
        assert nagpur.available_statistics["total_population_2011"] == 4653570
        assert nagpur.available_statistics["urbanization_rate_2011"] == 0.6830
        assert nagpur.available_statistics["general_sex_ratio_2011"] == 951
        assert nagpur.available_statistics["scheduled_castes_population_2011"] == 865992

        # Missing data for Nagpur
        assert "taluka_wise_student_enrolment" in nagpur.missing_data
        assert "district_level_household_income_microdata" in nagpur.missing_data

        # Assumptions and fallbacks for Nagpur
        assert "region_type" in nagpur.assumptions_and_fallbacks
        assert "admission_mode_distribution" in nagpur.assumptions_and_fallbacks

    def test_pune_and_nagpur_distributions_sum_to_unity(self):
        """Verifies that all probability distributions in Pune and Nagpur sum strictly to 1.0."""
        for dist_name in ["Pune", "Nagpur"]:
            p = get_district_profile(dist_name)
            assert sum(p.gender_distribution.values()) == pytest.approx(1.0)
            assert sum(p.institution_type_distribution.values()) == pytest.approx(1.0)
            assert sum(p.admission_mode_distribution.values()) == pytest.approx(1.0)
            assert sum(p.course_level_distribution.values()) == pytest.approx(1.0)
            assert sum(p.caste_category_distribution.values()) == pytest.approx(1.0)
            assert p.taluka_distribution is not None
            assert sum(p.taluka_distribution.values()) == pytest.approx(1.0)
            assert set(p.taluka_distribution.keys()) == set(p.talukas)
            assert 0.0 < p.professional_stream_ratio < 1.0

    def test_pune_and_nagpur_to_population_config_conversion(self):
        """Verifies conversion of Pune and Nagpur profiles into PopulationDistributionConfig."""
        pune_cfg = get_district_population_config("Pune")
        assert pune_cfg.config_name.startswith("DistrictConfig-PUNE-")
        assert pune_cfg.is_example_placeholder is True  # provisional_baseline tier
        assert pune_cfg.district_distribution == {"Pune": 1.0}
        assert pune_cfg.district_region_mapping == {"Pune": "Urban"}
        assert pune_cfg.talukas is not None
        assert len(pune_cfg.talukas) == 14

        nagpur_cfg = get_district_population_config("Nagpur")
        assert nagpur_cfg.config_name.startswith("DistrictConfig-NAGPUR-")
        assert nagpur_cfg.is_example_placeholder is True  # provisional_baseline tier
        assert nagpur_cfg.district_distribution == {"Nagpur": 1.0}
        assert nagpur_cfg.district_region_mapping == {"Nagpur": "Urban"}
        assert nagpur_cfg.talukas is not None
        assert len(nagpur_cfg.talukas) == 14

    def test_nashik_and_sangli_districts_registered(self):
        """Verifies that Nashik and Sangli are registered with provisional_baseline tier."""
        supported = set(list_supported_districts())
        assert "Nashik" in supported
        assert "Sangli" in supported

        nashik = get_district_profile("Nashik")
        assert nashik.district_id == "NASHIK"
        assert nashik.district_name == "Nashik"
        assert nashik.division == "Nashik"
        assert nashik.region_type == "Semi-Urban"
        assert nashik.provenance_tier == "provisional_baseline"
        assert "2011" in nashik.reference_year
        assert len(nashik.talukas) == 15
        assert "Nashik" in nashik.talukas
        assert "Malegaon" in nashik.talukas
        assert "Sinnar" in nashik.talukas
        assert "Igatpuri" in nashik.talukas

        # Available statistics for Nashik
        assert nashik.available_statistics["census_reference_year"] == "2011"
        assert "General population" in nashik.available_statistics["census_population_scope"]
        assert nashik.available_statistics["total_population_2011"] == 6107187
        assert nashik.available_statistics["urban_population_2011"] == 2598397
        assert nashik.available_statistics["rural_population_2011"] == 3508790
        assert nashik.available_statistics["urbanization_rate_2011"] == 0.4255
        assert nashik.available_statistics["general_sex_ratio_2011"] == 934
        assert nashik.available_statistics["scheduled_castes_population_2011"] == 555898
        assert nashik.available_statistics["scheduled_tribes_population_2011"] == 1564369
        assert nashik.available_statistics["administrative_revenue_talukas_count"] == 15

        # Missing data & assumptions catalog
        assert "taluka_wise_student_enrolment" in nashik.missing_data
        assert "district_level_household_income_microdata" in nashik.missing_data
        assert "region_type" in nashik.assumptions_and_fallbacks
        assert "admission_mode_distribution" in nashik.assumptions_and_fallbacks

        # Sangli verification
        sangli = get_district_profile("Sangli")
        assert sangli.district_id == "SANGLI"
        assert sangli.district_name == "Sangli"
        assert sangli.division == "Pune"
        assert sangli.region_type == "Semi-Urban"
        assert sangli.provenance_tier == "provisional_baseline"
        assert "2011" in sangli.reference_year
        assert len(sangli.talukas) == 10
        assert "Miraj" in sangli.talukas
        assert "Walwa" in sangli.talukas
        assert "Tasgaon" in sangli.talukas

        # Available statistics for Sangli
        assert sangli.available_statistics["census_reference_year"] == "2011"
        assert "General population" in sangli.available_statistics["census_population_scope"]
        assert sangli.available_statistics["total_population_2011"] == 2822143
        assert sangli.available_statistics["urban_population_2011"] == 719595
        assert sangli.available_statistics["rural_population_2011"] == 2102548
        assert sangli.available_statistics["urbanization_rate_2011"] == 0.2550
        assert sangli.available_statistics["general_sex_ratio_2011"] == 966
        assert sangli.available_statistics["scheduled_castes_population_2011"] == 353248
        assert sangli.available_statistics["scheduled_tribes_population_2011"] == 18041
        assert sangli.available_statistics["administrative_revenue_talukas_count"] == 10

        # Missing data & assumptions for Sangli
        assert "taluka_wise_student_enrolment" in sangli.missing_data
        assert "district_level_household_income_microdata" in sangli.missing_data
        assert "region_type" in sangli.assumptions_and_fallbacks
        assert "admission_mode_distribution" in sangli.assumptions_and_fallbacks

    def test_nashik_and_sangli_distributions_sum_to_unity(self):
        """Verifies that all probability distributions in Nashik and Sangli sum strictly to 1.0."""
        for dist_name in ["Nashik", "Sangli"]:
            p = get_district_profile(dist_name)
            assert sum(p.gender_distribution.values()) == pytest.approx(1.0)
            assert sum(p.institution_type_distribution.values()) == pytest.approx(1.0)
            assert sum(p.admission_mode_distribution.values()) == pytest.approx(1.0)
            assert sum(p.course_level_distribution.values()) == pytest.approx(1.0)
            assert sum(p.caste_category_distribution.values()) == pytest.approx(1.0)
            assert p.taluka_distribution is not None
            assert sum(p.taluka_distribution.values()) == pytest.approx(1.0)
            assert set(p.taluka_distribution.keys()) == set(p.talukas)
            assert 0.0 < p.professional_stream_ratio < 1.0

    def test_nashik_and_sangli_to_population_config_conversion(self):
        """Verifies conversion of Nashik and Sangli profiles into PopulationDistributionConfig."""
        nashik_cfg = get_district_population_config("Nashik")
        assert nashik_cfg.config_name.startswith("DistrictConfig-NASHIK-")
        assert nashik_cfg.is_example_placeholder is True
        assert nashik_cfg.district_distribution == {"Nashik": 1.0}
        assert nashik_cfg.district_region_mapping == {"Nashik": "Semi-Urban"}
        assert nashik_cfg.talukas is not None
        assert len(nashik_cfg.talukas) == 15

        sangli_cfg = get_district_population_config("Sangli")
        assert sangli_cfg.config_name.startswith("DistrictConfig-SANGLI-")
        assert sangli_cfg.is_example_placeholder is True
        assert sangli_cfg.district_distribution == {"Sangli": 1.0}
        assert sangli_cfg.district_region_mapping == {"Sangli": "Semi-Urban"}
        assert sangli_cfg.talukas is not None
        assert len(sangli_cfg.talukas) == 10

    def test_mumbai_suburban_nanded_nandurbar_palghar_districts_registered(self):
        """Verifies that Mumbai Suburban, Nanded, Nandurbar, and Palghar are registered with provisional_baseline tier."""
        supported = set(list_supported_districts())
        for d in ["Mumbai Suburban", "Nanded", "Nandurbar", "Palghar"]:
            assert d in supported

        # 1. Mumbai Suburban
        m_sub = get_district_profile("Mumbai Suburban")
        assert m_sub.district_id == "MUMBAI_SUBURBAN"
        assert m_sub.district_name == "Mumbai Suburban"
        assert m_sub.division == "Konkan"
        assert m_sub.region_type == "Urban"
        assert m_sub.provenance_tier == "provisional_baseline"
        assert len(m_sub.talukas) == 3
        assert set(m_sub.talukas) == {"Kurla", "Andheri", "Borivali"}
        assert m_sub.available_statistics["total_population_2011"] == 9356962
        assert m_sub.available_statistics["urbanization_rate_2011"] == 1.0000
        assert m_sub.available_statistics["general_sex_ratio_2011"] == 860
        assert m_sub.available_statistics["scheduled_castes_population_2011"] == 669824
        assert m_sub.available_statistics["scheduled_tribes_population_2011"] == 332607
        assert "taluka_wise_student_enrolment" in m_sub.missing_data
        assert "region_type" in m_sub.assumptions_and_fallbacks

        # 2. Nanded
        nanded = get_district_profile("Nanded")
        assert nanded.district_id == "NANDED"
        assert nanded.district_name == "Nanded"
        assert nanded.division == "Chhatrapati Sambhajinagar"
        assert nanded.region_type == "Semi-Urban"
        assert nanded.provenance_tier == "provisional_baseline"
        assert len(nanded.talukas) == 16
        assert "Nanded" in nanded.talukas
        assert "Deglur" in nanded.talukas
        assert "Kinwat" in nanded.talukas
        assert nanded.available_statistics["total_population_2011"] == 3361292
        assert nanded.available_statistics["urbanization_rate_2011"] == 0.2718
        assert nanded.available_statistics["general_sex_ratio_2011"] == 937
        assert nanded.available_statistics["scheduled_castes_population_2011"] == 641310
        assert nanded.available_statistics["scheduled_tribes_population_2011"] == 284041
        assert "taluka_wise_student_enrolment" in nanded.missing_data
        assert "region_type" in nanded.assumptions_and_fallbacks

        # 3. Nandurbar
        nandurbar = get_district_profile("Nandurbar")
        assert nandurbar.district_id == "NANDURBAR"
        assert nandurbar.district_name == "Nandurbar"
        assert nandurbar.division == "Nashik"
        assert nandurbar.region_type == "Rural"
        assert nandurbar.provenance_tier == "provisional_baseline"
        assert len(nandurbar.talukas) == 6
        assert "Nandurbar" in nandurbar.talukas
        assert "Shahada" in nandurbar.talukas
        assert "Navapur" in nandurbar.talukas
        assert nandurbar.available_statistics["total_population_2011"] == 1648295
        assert nandurbar.available_statistics["urbanization_rate_2011"] == 0.1672
        assert nandurbar.available_statistics["general_sex_ratio_2011"] == 978
        assert nandurbar.available_statistics["scheduled_tribes_population_2011"] == 1141933
        assert nandurbar.available_statistics["scheduled_tribes_share_2011"] == 0.6928
        assert "taluka_wise_student_enrolment" in nandurbar.missing_data
        assert "region_type" in nandurbar.assumptions_and_fallbacks

        # 4. Palghar (Reconstructed)
        palghar = get_district_profile("Palghar")
        assert palghar.district_id == "PALGHAR"
        assert palghar.district_name == "Palghar"
        assert palghar.division == "Konkan"
        assert palghar.region_type == "Semi-Urban"
        assert palghar.provenance_tier == "provisional_baseline"
        assert len(palghar.talukas) == 8
        assert "Palghar" in palghar.talukas
        assert "Vasai" in palghar.talukas
        assert "Jawhar" in palghar.talukas
        assert palghar.available_statistics["bifurcated_from"] == "Thane"
        assert palghar.available_statistics["bifurcation_date"] == "2014-08-01"
        assert palghar.available_statistics["reconstructed_total_population_2011"] == 2990116
        assert palghar.available_statistics["reconstructed_urbanization_rate_2011"] == 0.4800
        assert palghar.available_statistics["reconstructed_general_sex_ratio_2011"] == 921
        assert palghar.available_statistics["reconstructed_scheduled_tribes_population_2011"] == 1118529
        assert "pre_2014_standalone_district_administrative_series" in palghar.missing_data
        assert "region_type" in palghar.assumptions_and_fallbacks

    def test_mumbai_suburban_nanded_nandurbar_palghar_distributions_sum_to_unity(self):
        """Verifies that all probability distributions in Mumbai Suburban, Nanded, Nandurbar, and Palghar sum to 1.0."""
        for dist_name in ["Mumbai Suburban", "Nanded", "Nandurbar", "Palghar"]:
            p = get_district_profile(dist_name)
            assert sum(p.gender_distribution.values()) == pytest.approx(1.0)
            assert sum(p.institution_type_distribution.values()) == pytest.approx(1.0)
            assert sum(p.admission_mode_distribution.values()) == pytest.approx(1.0)
            assert sum(p.course_level_distribution.values()) == pytest.approx(1.0)
            assert sum(p.caste_category_distribution.values()) == pytest.approx(1.0)
            assert p.taluka_distribution is not None
            assert sum(p.taluka_distribution.values()) == pytest.approx(1.0)
            assert set(p.taluka_distribution.keys()) == set(p.talukas)
            assert 0.0 < p.professional_stream_ratio < 1.0

    def test_mumbai_suburban_nanded_nandurbar_palghar_to_population_config_conversion(self):
        """Verifies conversion of Mumbai Suburban, Nanded, Nandurbar, and Palghar profiles into PopulationDistributionConfig."""
        expected = {
            "Mumbai Suburban": ("MUMBAI_SUBURBAN", "Urban", 3),
            "Nanded": ("NANDED", "Semi-Urban", 16),
            "Nandurbar": ("NANDURBAR", "Rural", 6),
            "Palghar": ("PALGHAR", "Semi-Urban", 8),
        }
        for name, (d_id, reg_type, taluka_len) in expected.items():
            cfg = get_district_population_config(name)
            assert cfg.config_name.startswith(f"DistrictConfig-{d_id}-")
            assert cfg.is_example_placeholder is True
            assert cfg.district_distribution == {name: 1.0}
            assert cfg.district_region_mapping == {name: reg_type}
            assert cfg.talukas is not None
            assert len(cfg.talukas) == taluka_len

    def test_parbhani_raigad_ratnagiri_satara_districts_registered(self):
        """Verifies that Parbhani, Raigad, Ratnagiri, and Satara are registered with provisional_baseline tier."""
        supported = set(list_supported_districts())
        for d in ["Parbhani", "Raigad", "Ratnagiri", "Satara"]:
            assert d in supported

        # 1. Parbhani
        parbhani = get_district_profile("Parbhani")
        assert parbhani.district_id == "PARBHANI"
        assert parbhani.district_name == "Parbhani"
        assert parbhani.division == "Chhatrapati Sambhajinagar"
        assert parbhani.region_type == "Semi-Urban"
        assert parbhani.provenance_tier == "provisional_baseline"
        assert len(parbhani.talukas) == 9
        assert "Parbhani" in parbhani.talukas
        assert "Gangakhed" in parbhani.talukas
        assert "Selu" in parbhani.talukas
        assert parbhani.available_statistics["total_population_2011"] == 1836086
        assert parbhani.available_statistics["urbanization_rate_2011"] == 0.3103
        assert parbhani.available_statistics["general_sex_ratio_2011"] == 947
        assert parbhani.available_statistics["scheduled_castes_population_2011"] == 258217
        assert parbhani.available_statistics["scheduled_tribes_population_2011"] == 40793
        assert "taluka_wise_student_enrolment" in parbhani.missing_data
        assert "region_type" in parbhani.assumptions_and_fallbacks

        # 2. Raigad
        raigad = get_district_profile("Raigad")
        assert raigad.district_id == "RAIGAD"
        assert raigad.district_name == "Raigad"
        assert raigad.division == "Konkan"
        assert raigad.region_type == "Semi-Urban"
        assert raigad.provenance_tier == "provisional_baseline"
        assert len(raigad.talukas) == 15
        assert "Panvel" in raigad.talukas
        assert "Alibag" in raigad.talukas
        assert "Karjat" in raigad.talukas
        assert raigad.available_statistics["total_population_2011"] == 2634200
        assert raigad.available_statistics["urbanization_rate_2011"] == 0.3683
        assert raigad.available_statistics["general_sex_ratio_2011"] == 959
        assert raigad.available_statistics["scheduled_tribes_population_2011"] == 305291
        assert "mumbai_metropolitan_commuter_student_fraction" in raigad.missing_data
        assert "region_type" in raigad.assumptions_and_fallbacks

        # 3. Ratnagiri
        ratnagiri = get_district_profile("Ratnagiri")
        assert ratnagiri.district_id == "RATNAGIRI"
        assert ratnagiri.district_name == "Ratnagiri"
        assert ratnagiri.division == "Konkan"
        assert ratnagiri.region_type == "Rural"
        assert ratnagiri.provenance_tier == "provisional_baseline"
        assert len(ratnagiri.talukas) == 9
        assert "Ratnagiri" in ratnagiri.talukas
        assert "Chiplun" in ratnagiri.talukas
        assert "Dapoli" in ratnagiri.talukas
        assert ratnagiri.available_statistics["total_population_2011"] == 1615069
        assert ratnagiri.available_statistics["urbanization_rate_2011"] == 0.1633
        assert ratnagiri.available_statistics["general_sex_ratio_2011"] == 1122
        assert ratnagiri.available_statistics["scheduled_castes_population_2011"] == 66547
        assert "money_order_economy_remittance_income_variability" in ratnagiri.missing_data
        assert "region_type" in ratnagiri.assumptions_and_fallbacks

        # 4. Satara
        satara = get_district_profile("Satara")
        assert satara.district_id == "SATARA"
        assert satara.district_name == "Satara"
        assert satara.division == "Pune"
        assert satara.region_type == "Rural"
        assert satara.provenance_tier == "provisional_baseline"
        assert len(satara.talukas) == 11
        assert "Satara" in satara.talukas
        assert "Karad" in satara.talukas
        assert "Wai" in satara.talukas
        assert satara.available_statistics["total_population_2011"] == 3003741
        assert satara.available_statistics["urbanization_rate_2011"] == 0.1898
        assert satara.available_statistics["general_sex_ratio_2011"] == 988
        assert satara.available_statistics["scheduled_castes_population_2011"] == 323071
        assert "sugar_belt_household_income_seasonality" in satara.missing_data
        assert "region_type" in satara.assumptions_and_fallbacks

    def test_parbhani_raigad_ratnagiri_satara_distributions_sum_to_unity(self):
        """Verifies that all probability distributions in Parbhani, Raigad, Ratnagiri, and Satara sum to 1.0."""
        for dist_name in ["Parbhani", "Raigad", "Ratnagiri", "Satara"]:
            p = get_district_profile(dist_name)
            assert sum(p.gender_distribution.values()) == pytest.approx(1.0)
            assert sum(p.institution_type_distribution.values()) == pytest.approx(1.0)
            assert sum(p.admission_mode_distribution.values()) == pytest.approx(1.0)
            assert sum(p.course_level_distribution.values()) == pytest.approx(1.0)
            assert sum(p.caste_category_distribution.values()) == pytest.approx(1.0)
            assert p.taluka_distribution is not None
            assert sum(p.taluka_distribution.values()) == pytest.approx(1.0)
            assert set(p.taluka_distribution.keys()) == set(p.talukas)
            assert 0.0 < p.professional_stream_ratio < 1.0

    def test_parbhani_raigad_ratnagiri_satara_to_population_config_conversion(self):
        """Verifies conversion of Parbhani, Raigad, Ratnagiri, and Satara profiles into PopulationDistributionConfig."""
        expected = {
            "Parbhani": ("PARBHANI", "Semi-Urban", 9),
            "Raigad": ("RAIGAD", "Semi-Urban", 15),
            "Ratnagiri": ("RATNAGIRI", "Rural", 9),
            "Satara": ("SATARA", "Rural", 11),
        }
        for name, (d_id, reg_type, taluka_len) in expected.items():
            cfg = get_district_population_config(name)
            assert cfg.config_name.startswith(f"DistrictConfig-{d_id}-")
            assert cfg.is_example_placeholder is True
            assert cfg.district_distribution == {name: 1.0}
            assert cfg.district_region_mapping == {name: reg_type}
            assert cfg.talukas is not None
            assert len(cfg.talukas) == taluka_len

    def test_sindhudurg_solapur_thane_wardha_districts_registered(self):
        """Verifies that Sindhudurg, Solapur, Thane, and Wardha are registered with provisional_baseline tier."""
        supported = set(list_supported_districts())
        for d in ["Sindhudurg", "Solapur", "Thane", "Wardha"]:
            assert d in supported

        # 1. Sindhudurg
        sindhudurg = get_district_profile("Sindhudurg")
        assert sindhudurg.district_id == "SINDHUDURG"
        assert sindhudurg.district_name == "Sindhudurg"
        assert sindhudurg.division == "Konkan"
        assert sindhudurg.region_type == "Rural"
        assert sindhudurg.provenance_tier == "provisional_baseline"
        assert len(sindhudurg.talukas) == 8
        assert "Kankavli" in sindhudurg.talukas
        assert "Kudal" in sindhudurg.talukas
        assert "Sawantwadi" in sindhudurg.talukas
        assert sindhudurg.available_statistics["total_population_2011"] == 849651
        assert sindhudurg.available_statistics["urbanization_rate_2011"] == 0.1259
        assert sindhudurg.available_statistics["general_sex_ratio_2011"] == 1036
        assert sindhudurg.available_statistics["scheduled_castes_population_2011"] == 55586
        assert "horticultural_seasonal_income_variability" in sindhudurg.missing_data
        assert "region_type" in sindhudurg.assumptions_and_fallbacks

        # 2. Solapur
        solapur = get_district_profile("Solapur")
        assert solapur.district_id == "SOLAPUR"
        assert solapur.district_name == "Solapur"
        assert solapur.division == "Pune"
        assert solapur.region_type == "Semi-Urban"
        assert solapur.provenance_tier == "provisional_baseline"
        assert len(solapur.talukas) == 11
        assert "Solapur North" in solapur.talukas
        assert "Pandharpur" in solapur.talukas
        assert "Barshi" in solapur.talukas
        assert solapur.available_statistics["total_population_2011"] == 4317756
        assert solapur.available_statistics["urbanization_rate_2011"] == 0.3240
        assert solapur.available_statistics["general_sex_ratio_2011"] == 938
        assert solapur.available_statistics["scheduled_castes_population_2011"] == 649745
        assert "textile_handloom_household_income_cyclicality" in solapur.missing_data
        assert "region_type" in solapur.assumptions_and_fallbacks

        # 3. Thane
        thane = get_district_profile("Thane")
        assert thane.district_id == "THANE"
        assert thane.district_name == "Thane"
        assert thane.division == "Konkan"
        assert thane.region_type == "Urban"
        assert thane.provenance_tier == "provisional_baseline"
        assert len(thane.talukas) == 7
        assert "Thane" in thane.talukas
        assert "Kalyan" in thane.talukas
        assert "Ulhasnagar" in thane.talukas
        assert thane.available_statistics["total_population_2011"] == 8070032
        assert thane.available_statistics["urbanization_rate_2011"] == 0.8616
        assert thane.available_statistics["general_sex_ratio_2011"] == 868
        assert thane.available_statistics["scheduled_castes_population_2011"] == 643326
        assert thane.available_statistics["scheduled_tribes_population_2011"] == 423922
        assert "bifurcation_notes" in thane.available_statistics
        assert "mumbai_metropolitan_commuter_student_fraction" in thane.missing_data
        assert "region_type" in thane.assumptions_and_fallbacks

        # 4. Wardha
        wardha = get_district_profile("Wardha")
        assert wardha.district_id == "WARDHA"
        assert wardha.district_name == "Wardha"
        assert wardha.division == "Nagpur"
        assert wardha.region_type == "Semi-Urban"
        assert wardha.provenance_tier == "provisional_baseline"
        assert len(wardha.talukas) == 8
        assert "Wardha" in wardha.talukas
        assert "Hinganghat" in wardha.talukas
        assert "Arvi" in wardha.talukas
        assert wardha.available_statistics["total_population_2011"] == 1300774
        assert wardha.available_statistics["urbanization_rate_2011"] == 0.3254
        assert wardha.available_statistics["general_sex_ratio_2011"] == 946
        assert wardha.available_statistics["scheduled_castes_population_2011"] == 188868
        assert wardha.available_statistics["scheduled_tribes_population_2011"] == 149460
        assert "cotton_soybean_agrarian_income_seasonality" in wardha.missing_data
        assert "region_type" in wardha.assumptions_and_fallbacks

    def test_sindhudurg_solapur_thane_wardha_distributions_sum_to_unity(self):
        """Verifies that all probability distributions in Sindhudurg, Solapur, Thane, and Wardha sum to 1.0."""
        for dist_name in ["Sindhudurg", "Solapur", "Thane", "Wardha"]:
            p = get_district_profile(dist_name)
            assert sum(p.gender_distribution.values()) == pytest.approx(1.0)
            assert sum(p.institution_type_distribution.values()) == pytest.approx(1.0)
            assert sum(p.admission_mode_distribution.values()) == pytest.approx(1.0)
            assert sum(p.course_level_distribution.values()) == pytest.approx(1.0)
            assert sum(p.caste_category_distribution.values()) == pytest.approx(1.0)
            assert p.taluka_distribution is not None
            assert sum(p.taluka_distribution.values()) == pytest.approx(1.0)
            assert set(p.taluka_distribution.keys()) == set(p.talukas)
            assert 0.0 < p.professional_stream_ratio < 1.0

    def test_sindhudurg_solapur_thane_wardha_to_population_config_conversion(self):
        """Verifies conversion of Sindhudurg, Solapur, Thane, and Wardha profiles into PopulationDistributionConfig."""
        expected = {
            "Sindhudurg": ("SINDHUDURG", "Rural", 8),
            "Solapur": ("SOLAPUR", "Semi-Urban", 11),
            "Thane": ("THANE", "Urban", 7),
            "Wardha": ("WARDHA", "Semi-Urban", 8),
        }
        for name, (d_id, reg_type, taluka_len) in expected.items():
            cfg = get_district_population_config(name)
            assert cfg.config_name.startswith(f"DistrictConfig-{d_id}-")
            assert cfg.is_example_placeholder is True
            assert cfg.district_distribution == {name: 1.0}
            assert cfg.district_region_mapping == {name: reg_type}
            assert cfg.talukas is not None
            assert len(cfg.talukas) == taluka_len

    def test_washim_and_yavatmal_districts_registered(self):
        """Verifies that Washim and Yavatmal are registered with provisional_baseline tier."""
        supported = set(list_supported_districts())
        for d in ["Washim", "Yavatmal"]:
            assert d in supported

        # 1. Washim
        washim = get_district_profile("Washim")
        assert washim.district_id == "WASHIM"
        assert washim.district_name == "Washim"
        assert washim.division == "Amravati"
        assert washim.region_type == "Rural"
        assert washim.provenance_tier == "provisional_baseline"
        assert len(washim.talukas) == 6
        assert "Washim" in washim.talukas
        assert "Karanja" in washim.talukas
        assert "Risod" in washim.talukas
        assert washim.available_statistics["total_population_2011"] == 1197160
        assert washim.available_statistics["urbanization_rate_2011"] == 0.1766
        assert washim.available_statistics["general_sex_ratio_2011"] == 930
        assert washim.available_statistics["scheduled_castes_population_2011"] == 229462
        assert washim.available_statistics["scheduled_tribes_population_2011"] == 80471
        assert "soybean_cotton_dryland_income_variability" in washim.missing_data
        assert "region_type" in washim.assumptions_and_fallbacks

        # 2. Yavatmal
        yavatmal = get_district_profile("Yavatmal")
        assert yavatmal.district_id == "YAVATMAL"
        assert yavatmal.district_name == "Yavatmal"
        assert yavatmal.division == "Amravati"
        assert yavatmal.region_type == "Rural"
        assert yavatmal.provenance_tier == "provisional_baseline"
        assert len(yavatmal.talukas) == 16
        assert "Yavatmal" in yavatmal.talukas
        assert "Pusad" in yavatmal.talukas
        assert "Wani" in yavatmal.talukas
        assert "Umarkhed" in yavatmal.talukas
        assert yavatmal.available_statistics["total_population_2011"] == 2772348
        assert yavatmal.available_statistics["urbanization_rate_2011"] == 0.2158
        assert yavatmal.available_statistics["general_sex_ratio_2011"] == 952
        assert yavatmal.available_statistics["scheduled_castes_population_2011"] == 328348
        assert yavatmal.available_statistics["scheduled_tribes_population_2011"] == 514142
        assert "cotton_belt_agrarian_income_distress_seasonality" in yavatmal.missing_data
        assert "region_type" in yavatmal.assumptions_and_fallbacks

    def test_washim_and_yavatmal_distributions_sum_to_unity(self):
        """Verifies that all probability distributions in Washim and Yavatmal sum to 1.0."""
        for dist_name in ["Washim", "Yavatmal"]:
            p = get_district_profile(dist_name)
            assert sum(p.gender_distribution.values()) == pytest.approx(1.0)
            assert sum(p.institution_type_distribution.values()) == pytest.approx(1.0)
            assert sum(p.admission_mode_distribution.values()) == pytest.approx(1.0)
            assert sum(p.course_level_distribution.values()) == pytest.approx(1.0)
            assert sum(p.caste_category_distribution.values()) == pytest.approx(1.0)
            assert p.taluka_distribution is not None
            assert sum(p.taluka_distribution.values()) == pytest.approx(1.0)
            assert set(p.taluka_distribution.keys()) == set(p.talukas)
            assert 0.0 < p.professional_stream_ratio < 1.0

    def test_washim_and_yavatmal_to_population_config_conversion(self):
        """Verifies conversion of Washim and Yavatmal profiles into PopulationDistributionConfig."""
        expected = {
            "Washim": ("WASHIM", "Rural", 6),
            "Yavatmal": ("YAVATMAL", "Rural", 16),
        }
        for name, (d_id, reg_type, taluka_len) in expected.items():
            cfg = get_district_population_config(name)
            assert cfg.config_name.startswith(f"DistrictConfig-{d_id}-")
            assert cfg.is_example_placeholder is True
            assert cfg.district_distribution == {name: 1.0}
            assert cfg.district_region_mapping == {name: reg_type}
            assert cfg.talukas is not None
            assert len(cfg.talukas) == taluka_len

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
        all configured Maharashtra districts.
        """
        population = SyntheticPersonaGenerator.generate_state_population(
            total_count=1000,
            seed=42,
        )

        assert len(population) == 1000

        # Verify all configured districts are represented
        districts_in_sample = {s.district for s in population}
        assert len(districts_in_sample) == len(list_supported_districts())

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

    def test_district_specific_generation_pune(self):
        """Generates cohort for Pune and validates district-specific attributes and determinism."""
        pune_profile = get_district_profile("Pune")
        gen = SyntheticPersonaGenerator.for_district("Pune", seed=42)
        students = gen.generate_cohort(count=25)

        assert len(students) == 25
        for s in students:
            assert s.district == "Pune"
            assert hasattr(s, "taluka")
            assert s.taluka in pune_profile.talukas
            assert s.annual_tuition_fee > 0

        # Determinism check with identical seed
        gen2 = SyntheticPersonaGenerator.for_district("Pune", seed=42)
        students2 = gen2.generate_cohort(count=25)
        for s1, s2 in zip(students, students2):
            assert s1.persona_id == s2.persona_id
            assert s1.name == s2.name
            assert s1.family_income == s2.family_income
            assert s1.taluka == s2.taluka

    def test_district_specific_generation_nagpur(self):
        """Generates cohort for Nagpur and validates district-specific attributes and determinism."""
        nagpur_profile = get_district_profile("Nagpur")
        gen = SyntheticPersonaGenerator.for_district("Nagpur", seed=42)
        students = gen.generate_cohort(count=25)

        assert len(students) == 25
        for s in students:
            assert s.district == "Nagpur"
            assert hasattr(s, "taluka")
            assert s.taluka in nagpur_profile.talukas
            assert s.annual_tuition_fee > 0

        # Determinism check with identical seed
        gen2 = SyntheticPersonaGenerator.for_district("Nagpur", seed=42)
        students2 = gen2.generate_cohort(count=25)
        for s1, s2 in zip(students, students2):
            assert s1.persona_id == s2.persona_id
            assert s1.name == s2.name
            assert s1.family_income == s2.family_income
            assert s1.taluka == s2.taluka

    def test_pune_and_nagpur_policy_eligibility_mix(self):
        """Verifies natural distribution of eligible and ineligible personas in Pune and Nagpur cohorts."""
        for dist_name in ["Pune", "Nagpur"]:
            gen = SyntheticPersonaGenerator.for_district(dist_name, seed=777)
            cohort = gen.generate_cohort(count=50)

            eligible_count = 0
            ineligible_count = 0
            failure_reasons = set()

            for s in cohort:
                eval_res = RajarshiShahuPolicyEngine.evaluate_eligibility(s)
                if eval_res.is_eligible:
                    eligible_count += 1
                    assert eval_res.estimated_fee_relief_inr > 0
                else:
                    ineligible_count += 1
                    for r in eval_res.failure_reasons:
                        failure_reasons.add(r)

            assert eligible_count > 0, f"{dist_name} cohort should have eligible students"
            assert ineligible_count > 0, f"{dist_name} cohort should have ineligible students"
            assert len(failure_reasons) > 0

    def test_district_specific_generation_nashik(self):
        """Generates cohort for Nashik and validates district-specific attributes and determinism."""
        nashik_profile = get_district_profile("Nashik")
        gen = SyntheticPersonaGenerator.for_district("Nashik", seed=42)
        students = gen.generate_cohort(count=25)

        assert len(students) == 25
        for s in students:
            assert s.district == "Nashik"
            assert hasattr(s, "taluka")
            assert s.taluka in nashik_profile.talukas
            assert s.annual_tuition_fee > 0

        # Determinism check with identical seed
        gen2 = SyntheticPersonaGenerator.for_district("Nashik", seed=42)
        students2 = gen2.generate_cohort(count=25)
        for s1, s2 in zip(students, students2):
            assert s1.persona_id == s2.persona_id
            assert s1.name == s2.name
            assert s1.family_income == s2.family_income
            assert s1.taluka == s2.taluka

    def test_district_specific_generation_sangli(self):
        """Generates cohort for Sangli and validates district-specific attributes and determinism."""
        sangli_profile = get_district_profile("Sangli")
        gen = SyntheticPersonaGenerator.for_district("Sangli", seed=42)
        students = gen.generate_cohort(count=25)

        assert len(students) == 25
        for s in students:
            assert s.district == "Sangli"
            assert hasattr(s, "taluka")
            assert s.taluka in sangli_profile.talukas
            assert s.annual_tuition_fee > 0

        # Determinism check with identical seed
        gen2 = SyntheticPersonaGenerator.for_district("Sangli", seed=42)
        students2 = gen2.generate_cohort(count=25)
        for s1, s2 in zip(students, students2):
            assert s1.persona_id == s2.persona_id
            assert s1.name == s2.name
            assert s1.family_income == s2.family_income
            assert s1.taluka == s2.taluka

    def test_nashik_and_sangli_policy_eligibility_mix(self):
        """Verifies natural distribution of eligible and ineligible personas in Nashik and Sangli cohorts."""
        for dist_name in ["Nashik", "Sangli"]:
            gen = SyntheticPersonaGenerator.for_district(dist_name, seed=888)
            cohort = gen.generate_cohort(count=50)

            eligible_count = 0
            ineligible_count = 0
            failure_reasons = set()

            for s in cohort:
                eval_res = RajarshiShahuPolicyEngine.evaluate_eligibility(s)
                if eval_res.is_eligible:
                    eligible_count += 1
                    assert eval_res.estimated_fee_relief_inr > 0
                else:
                    ineligible_count += 1
                    for r in eval_res.failure_reasons:
                        failure_reasons.add(r)

            assert eligible_count > 0, f"{dist_name} cohort should have eligible students"
            assert ineligible_count > 0, f"{dist_name} cohort should have ineligible students"
            assert len(failure_reasons) > 0

    def test_district_specific_generation_mumbai_suburban(self):
        """Generates cohort for Mumbai Suburban and validates district-specific attributes and determinism."""
        profile = get_district_profile("Mumbai Suburban")
        gen = SyntheticPersonaGenerator.for_district("Mumbai Suburban", seed=42)
        students = gen.generate_cohort(count=25)

        assert len(students) == 25
        for s in students:
            assert s.district == "Mumbai Suburban"
            assert hasattr(s, "taluka")
            assert s.taluka in profile.talukas
            assert s.annual_tuition_fee > 0

        # Determinism check with identical seed
        gen2 = SyntheticPersonaGenerator.for_district("Mumbai Suburban", seed=42)
        students2 = gen2.generate_cohort(count=25)
        for s1, s2 in zip(students, students2):
            assert s1.persona_id == s2.persona_id
            assert s1.name == s2.name
            assert s1.family_income == s2.family_income
            assert s1.taluka == s2.taluka

    def test_district_specific_generation_nanded(self):
        """Generates cohort for Nanded and validates district-specific attributes and determinism."""
        profile = get_district_profile("Nanded")
        gen = SyntheticPersonaGenerator.for_district("Nanded", seed=42)
        students = gen.generate_cohort(count=25)

        assert len(students) == 25
        for s in students:
            assert s.district == "Nanded"
            assert hasattr(s, "taluka")
            assert s.taluka in profile.talukas
            assert s.annual_tuition_fee > 0

        # Determinism check with identical seed
        gen2 = SyntheticPersonaGenerator.for_district("Nanded", seed=42)
        students2 = gen2.generate_cohort(count=25)
        for s1, s2 in zip(students, students2):
            assert s1.persona_id == s2.persona_id
            assert s1.name == s2.name
            assert s1.family_income == s2.family_income
            assert s1.taluka == s2.taluka

    def test_district_specific_generation_nandurbar(self):
        """Generates cohort for Nandurbar and validates district-specific attributes and determinism."""
        profile = get_district_profile("Nandurbar")
        gen = SyntheticPersonaGenerator.for_district("Nandurbar", seed=42)
        students = gen.generate_cohort(count=25)

        assert len(students) == 25
        for s in students:
            assert s.district == "Nandurbar"
            assert hasattr(s, "taluka")
            assert s.taluka in profile.talukas
            assert s.annual_tuition_fee > 0

        # Determinism check with identical seed
        gen2 = SyntheticPersonaGenerator.for_district("Nandurbar", seed=42)
        students2 = gen2.generate_cohort(count=25)
        for s1, s2 in zip(students, students2):
            assert s1.persona_id == s2.persona_id
            assert s1.name == s2.name
            assert s1.family_income == s2.family_income
            assert s1.taluka == s2.taluka

    def test_district_specific_generation_palghar(self):
        """Generates cohort for Palghar and validates district-specific attributes and determinism."""
        profile = get_district_profile("Palghar")
        gen = SyntheticPersonaGenerator.for_district("Palghar", seed=42)
        students = gen.generate_cohort(count=25)

        assert len(students) == 25
        for s in students:
            assert s.district == "Palghar"
            assert hasattr(s, "taluka")
            assert s.taluka in profile.talukas
            assert s.annual_tuition_fee > 0

        # Determinism check with identical seed
        gen2 = SyntheticPersonaGenerator.for_district("Palghar", seed=42)
        students2 = gen2.generate_cohort(count=25)
        for s1, s2 in zip(students, students2):
            assert s1.persona_id == s2.persona_id
            assert s1.name == s2.name
            assert s1.family_income == s2.family_income
            assert s1.taluka == s2.taluka

    def test_mumbai_suburban_nanded_nandurbar_palghar_policy_eligibility_mix(self):
        """Verifies natural distribution of eligible and ineligible personas in the 4 new district cohorts."""
        for dist_name in ["Mumbai Suburban", "Nanded", "Nandurbar", "Palghar"]:
            gen = SyntheticPersonaGenerator.for_district(dist_name, seed=888)
            cohort = gen.generate_cohort(count=50)

            eligible_count = 0
            ineligible_count = 0
            failure_reasons = set()

            for s in cohort:
                eval_res = RajarshiShahuPolicyEngine.evaluate_eligibility(s)
                if eval_res.is_eligible:
                    eligible_count += 1
                    assert eval_res.estimated_fee_relief_inr > 0
                else:
                    ineligible_count += 1
                    for r in eval_res.failure_reasons:
                        failure_reasons.add(r)

            assert eligible_count > 0, f"{dist_name} cohort should have eligible students"
            assert ineligible_count > 0, f"{dist_name} cohort should have ineligible students"
            assert len(failure_reasons) > 0

    def test_district_specific_generation_parbhani(self):
        """Generates cohort for Parbhani and validates district-specific attributes and determinism."""
        profile = get_district_profile("Parbhani")
        gen = SyntheticPersonaGenerator.for_district("Parbhani", seed=42)
        students = gen.generate_cohort(count=25)

        assert len(students) == 25
        for s in students:
            assert s.district == "Parbhani"
            assert hasattr(s, "taluka")
            assert s.taluka in profile.talukas
            assert s.annual_tuition_fee > 0

        # Determinism check with identical seed
        gen2 = SyntheticPersonaGenerator.for_district("Parbhani", seed=42)
        students2 = gen2.generate_cohort(count=25)
        for s1, s2 in zip(students, students2):
            assert s1.persona_id == s2.persona_id
            assert s1.name == s2.name
            assert s1.family_income == s2.family_income
            assert s1.taluka == s2.taluka

    def test_district_specific_generation_raigad(self):
        """Generates cohort for Raigad and validates district-specific attributes and determinism."""
        profile = get_district_profile("Raigad")
        gen = SyntheticPersonaGenerator.for_district("Raigad", seed=42)
        students = gen.generate_cohort(count=25)

        assert len(students) == 25
        for s in students:
            assert s.district == "Raigad"
            assert hasattr(s, "taluka")
            assert s.taluka in profile.talukas
            assert s.annual_tuition_fee > 0

        # Determinism check with identical seed
        gen2 = SyntheticPersonaGenerator.for_district("Raigad", seed=42)
        students2 = gen2.generate_cohort(count=25)
        for s1, s2 in zip(students, students2):
            assert s1.persona_id == s2.persona_id
            assert s1.name == s2.name
            assert s1.family_income == s2.family_income
            assert s1.taluka == s2.taluka

    def test_district_specific_generation_ratnagiri(self):
        """Generates cohort for Ratnagiri and validates district-specific attributes and determinism."""
        profile = get_district_profile("Ratnagiri")
        gen = SyntheticPersonaGenerator.for_district("Ratnagiri", seed=42)
        students = gen.generate_cohort(count=25)

        assert len(students) == 25
        for s in students:
            assert s.district == "Ratnagiri"
            assert hasattr(s, "taluka")
            assert s.taluka in profile.talukas
            assert s.annual_tuition_fee > 0

        # Determinism check with identical seed
        gen2 = SyntheticPersonaGenerator.for_district("Ratnagiri", seed=42)
        students2 = gen2.generate_cohort(count=25)
        for s1, s2 in zip(students, students2):
            assert s1.persona_id == s2.persona_id
            assert s1.name == s2.name
            assert s1.family_income == s2.family_income
            assert s1.taluka == s2.taluka

    def test_district_specific_generation_satara(self):
        """Generates cohort for Satara and validates district-specific attributes and determinism."""
        profile = get_district_profile("Satara")
        gen = SyntheticPersonaGenerator.for_district("Satara", seed=42)
        students = gen.generate_cohort(count=25)

        assert len(students) == 25
        for s in students:
            assert s.district == "Satara"
            assert hasattr(s, "taluka")
            assert s.taluka in profile.talukas
            assert s.annual_tuition_fee > 0

        # Determinism check with identical seed
        gen2 = SyntheticPersonaGenerator.for_district("Satara", seed=42)
        students2 = gen2.generate_cohort(count=25)
        for s1, s2 in zip(students, students2):
            assert s1.persona_id == s2.persona_id
            assert s1.name == s2.name
            assert s1.family_income == s2.family_income
            assert s1.taluka == s2.taluka

    def test_parbhani_raigad_ratnagiri_satara_policy_eligibility_mix(self):
        """Verifies natural distribution of eligible and ineligible personas in Parbhani, Raigad, Ratnagiri, Satara cohorts."""
        for dist_name in ["Parbhani", "Raigad", "Ratnagiri", "Satara"]:
            gen = SyntheticPersonaGenerator.for_district(dist_name, seed=888)
            cohort = gen.generate_cohort(count=50)

            eligible_count = 0
            ineligible_count = 0
            failure_reasons = set()

            for s in cohort:
                eval_res = RajarshiShahuPolicyEngine.evaluate_eligibility(s)
                if eval_res.is_eligible:
                    eligible_count += 1
                    assert eval_res.estimated_fee_relief_inr > 0
                else:
                    ineligible_count += 1
                    for r in eval_res.failure_reasons:
                        failure_reasons.add(r)

            assert eligible_count > 0, f"{dist_name} cohort should have eligible students"
            assert ineligible_count > 0, f"{dist_name} cohort should have ineligible students"
            assert len(failure_reasons) > 0

    def test_district_specific_generation_sindhudurg(self):
        """Generates cohort for Sindhudurg and validates district-specific attributes and determinism."""
        profile = get_district_profile("Sindhudurg")
        gen = SyntheticPersonaGenerator.for_district("Sindhudurg", seed=42)
        students = gen.generate_cohort(count=25)

        assert len(students) == 25
        for s in students:
            assert s.district == "Sindhudurg"
            assert hasattr(s, "taluka")
            assert s.taluka in profile.talukas
            assert s.annual_tuition_fee > 0

        # Determinism check with identical seed
        gen2 = SyntheticPersonaGenerator.for_district("Sindhudurg", seed=42)
        students2 = gen2.generate_cohort(count=25)
        for s1, s2 in zip(students, students2):
            assert s1.persona_id == s2.persona_id
            assert s1.name == s2.name
            assert s1.family_income == s2.family_income
            assert s1.taluka == s2.taluka

    def test_district_specific_generation_solapur(self):
        """Generates cohort for Solapur and validates district-specific attributes and determinism."""
        profile = get_district_profile("Solapur")
        gen = SyntheticPersonaGenerator.for_district("Solapur", seed=42)
        students = gen.generate_cohort(count=25)

        assert len(students) == 25
        for s in students:
            assert s.district == "Solapur"
            assert hasattr(s, "taluka")
            assert s.taluka in profile.talukas
            assert s.annual_tuition_fee > 0

        # Determinism check with identical seed
        gen2 = SyntheticPersonaGenerator.for_district("Solapur", seed=42)
        students2 = gen2.generate_cohort(count=25)
        for s1, s2 in zip(students, students2):
            assert s1.persona_id == s2.persona_id
            assert s1.name == s2.name
            assert s1.family_income == s2.family_income
            assert s1.taluka == s2.taluka

    def test_district_specific_generation_thane(self):
        """Generates cohort for Thane and validates district-specific attributes and determinism."""
        profile = get_district_profile("Thane")
        gen = SyntheticPersonaGenerator.for_district("Thane", seed=42)
        students = gen.generate_cohort(count=25)

        assert len(students) == 25
        for s in students:
            assert s.district == "Thane"
            assert hasattr(s, "taluka")
            assert s.taluka in profile.talukas
            assert s.annual_tuition_fee > 0

        # Determinism check with identical seed
        gen2 = SyntheticPersonaGenerator.for_district("Thane", seed=42)
        students2 = gen2.generate_cohort(count=25)
        for s1, s2 in zip(students, students2):
            assert s1.persona_id == s2.persona_id
            assert s1.name == s2.name
            assert s1.family_income == s2.family_income
            assert s1.taluka == s2.taluka

    def test_district_specific_generation_wardha(self):
        """Generates cohort for Wardha and validates district-specific attributes and determinism."""
        profile = get_district_profile("Wardha")
        gen = SyntheticPersonaGenerator.for_district("Wardha", seed=42)
        students = gen.generate_cohort(count=25)

        assert len(students) == 25
        for s in students:
            assert s.district == "Wardha"
            assert hasattr(s, "taluka")
            assert s.taluka in profile.talukas
            assert s.annual_tuition_fee > 0

        # Determinism check with identical seed
        gen2 = SyntheticPersonaGenerator.for_district("Wardha", seed=42)
        students2 = gen2.generate_cohort(count=25)
        for s1, s2 in zip(students, students2):
            assert s1.persona_id == s2.persona_id
            assert s1.name == s2.name
            assert s1.family_income == s2.family_income
            assert s1.taluka == s2.taluka

    def test_sindhudurg_solapur_thane_wardha_policy_eligibility_mix(self):
        """Verifies natural distribution of eligible and ineligible personas in Sindhudurg, Solapur, Thane, Wardha cohorts."""
        for dist_name in ["Sindhudurg", "Solapur", "Thane", "Wardha"]:
            gen = SyntheticPersonaGenerator.for_district(dist_name, seed=888)
            cohort = gen.generate_cohort(count=50)

            eligible_count = 0
            ineligible_count = 0
            failure_reasons = set()

            for s in cohort:
                eval_res = RajarshiShahuPolicyEngine.evaluate_eligibility(s)
                if eval_res.is_eligible:
                    eligible_count += 1
                    assert eval_res.estimated_fee_relief_inr > 0
                else:
                    ineligible_count += 1
                    for r in eval_res.failure_reasons:
                        failure_reasons.add(r)

            assert eligible_count > 0, f"{dist_name} cohort should have eligible students"
            assert ineligible_count > 0, f"{dist_name} cohort should have ineligible students"
            assert len(failure_reasons) > 0

    def test_district_specific_generation_washim(self):
        """Generates cohort for Washim and validates district-specific attributes and determinism."""
        profile = get_district_profile("Washim")
        gen = SyntheticPersonaGenerator.for_district("Washim", seed=42)
        students = gen.generate_cohort(count=25)

        assert len(students) == 25
        for s in students:
            assert s.district == "Washim"
            assert hasattr(s, "taluka")
            assert s.taluka in profile.talukas
            assert s.annual_tuition_fee > 0

        # Determinism check with identical seed
        gen2 = SyntheticPersonaGenerator.for_district("Washim", seed=42)
        students2 = gen2.generate_cohort(count=25)
        for s1, s2 in zip(students, students2):
            assert s1.persona_id == s2.persona_id
            assert s1.name == s2.name
            assert s1.family_income == s2.family_income
            assert s1.taluka == s2.taluka

    def test_district_specific_generation_yavatmal(self):
        """Generates cohort for Yavatmal and validates district-specific attributes and determinism."""
        profile = get_district_profile("Yavatmal")
        gen = SyntheticPersonaGenerator.for_district("Yavatmal", seed=42)
        students = gen.generate_cohort(count=25)

        assert len(students) == 25
        for s in students:
            assert s.district == "Yavatmal"
            assert hasattr(s, "taluka")
            assert s.taluka in profile.talukas
            assert s.annual_tuition_fee > 0

        # Determinism check with identical seed
        gen2 = SyntheticPersonaGenerator.for_district("Yavatmal", seed=42)
        students2 = gen2.generate_cohort(count=25)
        for s1, s2 in zip(students, students2):
            assert s1.persona_id == s2.persona_id
            assert s1.name == s2.name
            assert s1.family_income == s2.family_income
            assert s1.taluka == s2.taluka

    def test_washim_and_yavatmal_policy_eligibility_mix(self):
        """Verifies natural distribution of eligible and ineligible personas in Washim and Yavatmal cohorts."""
        for dist_name in ["Washim", "Yavatmal"]:
            gen = SyntheticPersonaGenerator.for_district(dist_name, seed=888)
            cohort = gen.generate_cohort(count=50)

            eligible_count = 0
            ineligible_count = 0
            failure_reasons = set()

            for s in cohort:
                eval_res = RajarshiShahuPolicyEngine.evaluate_eligibility(s)
                if eval_res.is_eligible:
                    eligible_count += 1
                    assert eval_res.estimated_fee_relief_inr > 0
                else:
                    ineligible_count += 1
                    for r in eval_res.failure_reasons:
                        failure_reasons.add(r)

            assert eligible_count > 0, f"{dist_name} cohort should have eligible students"
            assert ineligible_count > 0, f"{dist_name} cohort should have ineligible students"
            assert len(failure_reasons) > 0

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
        """Verifies that 1,000 personas are evenly bounded across all configured districts."""
        population = SyntheticPersonaGenerator.generate_state_population(total_count=1000, seed=42)
        from collections import Counter
        district_counts = Counter(s.district for s in population)
        num_districts = len(list_supported_districts())
        assert len(district_counts) == num_districts
        base_quota = 1000 // num_districts
        remainder = 1000 % num_districts
        expected_bounds = (base_quota, base_quota + 1) if remainder > 0 else (base_quota, base_quota)
        for dist_name, count in district_counts.items():
            assert count in expected_bounds, f"District {dist_name} count {count} is outside expected bounds {expected_bounds}"
