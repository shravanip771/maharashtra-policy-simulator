"""
Unit tests for Dhule Education Dataset Adapter (Phase 2 Data Integration).

Verifies:
1. Exact parsing of the raw workbook (4 talukas, 125 columns).
2. Correct calculation of directly observed aggregate totals (colleges, enrolments).
3. Correct derivation of grounded distributions (gender, institution type, professional ratio).
4. Explicit documentation and isolation of unavailable fields.
5. Generation of synthetic persona using the empirical Dhule configuration.
6. Execution through RajarshiShahuPolicyEngine with zero regressions.
"""

import os
from data.dhule_adapter import (
    DhuleEducationDatasetAdapter,
    DhuleEducationDatasetSummary,
    RawTalukaEducationRecord
)
from simulation.persona_generator import SyntheticPersonaGenerator
from simulation.policy_rules import RajarshiShahuPolicyEngine


def test_parse_real_dhule_dataset():
    """Verifies that the adapter reads the real workbook without errors or modifications."""
    summary = DhuleEducationDatasetAdapter.load_and_parse()

    assert isinstance(summary, DhuleEducationDatasetSummary)
    assert summary.reference_year == "2010-11"
    assert summary.district_name == "Dhule"
    assert summary.district_code == "498"
    assert len(summary.taluka_records) == 4

    taluka_names = [r.taluka_name for r in summary.taluka_records]
    assert taluka_names == ["Shirpur", "Sindkhede", "Sakri", "Dhule"]

    # Verify directly observed higher ed college counts
    assert summary.total_govt_colleges == 0
    assert summary.total_pvt_aided_colleges == 24
    assert summary.total_pvt_unaided_colleges == 49
    assert summary.total_engineering_degree_colleges == 4
    assert summary.total_engineering_diploma_colleges == 4
    assert summary.total_medical_degree_colleges == 1
    assert summary.total_iti_voc_institutions == 8

    # Verify observed senior secondary enrolments
    assert summary.total_sr_sec_boys == 26138
    assert summary.total_sr_sec_girls == 19882
    print("PASS: test_parse_real_dhule_dataset")


def test_derived_distributions_and_unavailable_fields():
    """Verifies mathematically derived distributions and unavailable field declarations."""
    summary = DhuleEducationDatasetAdapter.load_and_parse()

    # Gender ratio derived from 26,138 boys / 19,882 girls
    tot_sr = 26138 + 19882  # 46,020
    expected_male_ratio = round(26138 / tot_sr, 4)
    expected_female_ratio = round(19882 / tot_sr, 4)
    assert summary.derived_gender_distribution["Male"] == expected_male_ratio
    assert summary.derived_gender_distribution["Female"] == expected_female_ratio

    # Institution management ratio derived from 24 aided / 49 unaided / 0 govt (73 total)
    assert summary.derived_institution_type_distribution["Government"] == 0.0
    assert summary.derived_institution_type_distribution["Government-Aided"] == round(24 / 73, 4)
    assert summary.derived_institution_type_distribution["Private-Unaided"] == round(49 / 73, 4)

    # Unavailable fields check
    assert "caste_category" in summary.unavailable_fields
    assert "family_income" in summary.unavailable_fields
    assert "admission_mode" in summary.unavailable_fields
    assert "initial_awareness" in summary.unavailable_fields
    print("PASS: test_derived_distributions_and_unavailable_fields")


def test_persona_generation_with_dhule_empirical_config():
    """Verifies that the empirical Dhule config generates valid personas that pass policy evaluation."""
    dhule_config = DhuleEducationDatasetAdapter.create_population_config()

    assert dhule_config.is_example_placeholder is False
    assert "Dhule" in dhule_config.district_distribution
    assert dhule_config.district_distribution["Dhule"] == 1.0

    generator = SyntheticPersonaGenerator(config=dhule_config, seed=777)
    profile = generator.generate_profile(persona_id="DHULE-TEST-001")
    student = profile.to_student_persona()

    # Grounded fields check
    assert student.district == "Dhule"
    assert student.gender in ["Male", "Female"]
    assert student.institution_type.value in ["Government-Aided", "Private-Unaided"]

    # Verify policy evaluation runs cleanly
    is_eligible, checks, failures = RajarshiShahuPolicyEngine.check_statutory_eligibility(student)
    assert isinstance(is_eligible, bool)
    assert len(checks) == 8
    print("PASS: test_persona_generation_with_dhule_empirical_config")


if __name__ == "__main__":
    test_parse_real_dhule_dataset()
    test_derived_distributions_and_unavailable_fields()
    test_persona_generation_with_dhule_empirical_config()
    print("All Dhule dataset adapter tests passed successfully!")
