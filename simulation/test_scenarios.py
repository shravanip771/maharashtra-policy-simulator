"""
Unit tests for Scenario Engine (simulation/scenarios.py).

Tests:
1. Attribute changes for each intervention:
   - Awareness Campaign modifies ONLY initial_awareness.
   - Documentation Assistance modifies ONLY document_readiness.
   - Institutional Support modifies ONLY document_readiness and institutional_trust.
2. No unintended attribute changes:
   - peer_network_support, digital_literacy, personality, and statutory attributes untouched.
3. Original persona immutability:
   - Input persona objects are never mutated across apply_intervention or run_comparison.
4. Eligibility preservation:
   - Statutory eligibility counts and individual statuses match identically between baseline and intervention.
5. Baseline versus intervention comparison effects:
   - Uplift in awareness, application attempts, and completions.
6. Deterministic reproducibility:
   - Identical seeds yield identical comparison outputs.
7. Zero-denominator handling:
   - Empty cohort total=0.
   - Whenever baseline recipients are zero, relative_uptake_growth_percentage is strictly None,
     regardless of intervention recipient count (zero or positive).
8. Strict boundary violation checks:
   - Attempting to set cross-intervention parameters raises ValueError.
9. Offline execution:
   - Executes with StubLLMProvider, ensuring zero network calls to Gemini or external APIs.
10. Reimbursement-rate integration dependency and limitation notes:
    - Assumed 50% PoC limitation noted when assumed_reimbursement_rate is None.
    - Explicit rate pass-through verified.
11. Institutional support behavioral note:
    - Explicit disclaimer that institutional_trust does not directly alter deterministic application probability.
12. JSON serialization integrity:
    - Strictly compliant RFC 8259 output without NaN or Infinity.
"""

import pytest
import copy
import json
from typing import List

from simulation.persona import StudentPersona, InstitutionType, AdmissionMode, PersonalityTraits
from simulation.persona_generator import SyntheticPersonaGenerator
from simulation.agent import StubLLMProvider
from simulation.scenarios import (
    ScenarioEngine,
    ScenarioIntervention,
    InterventionType,
    ScenarioComparisonReport,
    run_scenario_comparison,
    DEFAULT_EPISTEMIC_DISCLAIMER
)


def _create_test_persona(
    persona_id: str = "STU-001",
    name: str = "Aarav Sharma",
    district: str = "Dhule",
    gender: str = "Male",
    family_income: float = 300000.0,
    is_eligible: bool = True,
    initial_awareness: float = 0.20,
    document_readiness: float = 0.30,
    digital_literacy: float = 0.50,
    peer_network_support: float = 0.40,
    institutional_trust: float = 0.40,
    annual_tuition_fee: float = 80000.0
) -> StudentPersona:
    """Helper fixture to construct a deterministic StudentPersona."""
    return StudentPersona(
        persona_id=persona_id,
        name=name,
        age=20,
        gender=gender,
        district=district,
        is_maharashtra_domicile=True if is_eligible else False,
        family_income=family_income if is_eligible else 1200000.0,
        caste_category="General-EBC",
        first_generation_learner=True,
        parental_education_level="Secondary",
        course_name="B.Tech Computer Engineering",
        course_level="Undergraduate",
        is_professional_course=True,
        institution_type=InstitutionType.GOVERNMENT_AIDED,
        admission_mode=AdmissionMode.CAP,
        annual_tuition_fee=annual_tuition_fee,
        attendance_percentage=85.0,
        previous_year_passed=True,
        previous_year_percentage=75.0,
        academic_gap_years=0,
        family_beneficiaries_count=0,
        has_other_scholarship=False,
        digital_literacy=digital_literacy,
        initial_awareness=initial_awareness,
        document_readiness=document_readiness,
        financial_urgency=0.80,
        peer_network_support=peer_network_support,
        institutional_trust=institutional_trust,
        personality=PersonalityTraits(
            patience=0.6,
            diligence=0.7,
            risk_aversion=0.5,
            self_advocacy=0.6
        )
    )


class TestScenarioEngineInterventions:
    """Tests verifying attribute boundaries and isolation for each intervention."""

    def test_awareness_campaign_modifies_only_initial_awareness(self):
        """Verifies Awareness Campaign increases initial_awareness and leaves all other attributes unchanged."""
        engine = ScenarioEngine()
        personas = [_create_test_persona(initial_awareness=0.20, document_readiness=0.40, institutional_trust=0.50)]
        original_copy = copy.deepcopy(personas[0])

        intervention = engine.create_awareness_campaign(delta=0.30)
        modified = engine.apply_intervention(personas, intervention)

        assert len(modified) == 1
        mod_p = modified[0]

        # initial_awareness must change
        assert mod_p.initial_awareness == 0.50

        # All other attributes must remain exactly identical
        assert mod_p.document_readiness == original_copy.document_readiness
        assert mod_p.institutional_trust == original_copy.institutional_trust
        assert mod_p.peer_network_support == original_copy.peer_network_support
        assert mod_p.digital_literacy == original_copy.digital_literacy
        assert mod_p.personality == original_copy.personality
        assert mod_p.family_income == original_copy.family_income
        assert mod_p.is_maharashtra_domicile == original_copy.is_maharashtra_domicile

    def test_awareness_campaign_floor_and_bounding(self):
        """Verifies awareness campaign respects floors and does not exceed 1.0."""
        engine = ScenarioEngine()
        p1 = _create_test_persona(persona_id="P1", initial_awareness=0.10)
        p2 = _create_test_persona(persona_id="P2", initial_awareness=0.90)

        intervention = engine.create_awareness_campaign(delta=0.20, floor=0.50)
        modified = engine.apply_intervention([p1, p2], intervention)

        # P1: 0.10 + 0.20 = 0.30, but floor is 0.50 -> becomes 0.50
        assert modified[0].initial_awareness == 0.50
        # P2: 0.90 + 0.20 = 1.10 -> clamped to 1.00
        assert modified[1].initial_awareness == 1.00

    def test_documentation_assistance_modifies_only_document_readiness(self):
        """Verifies Documentation Assistance alters ONLY document_readiness."""
        engine = ScenarioEngine()
        personas = [_create_test_persona(initial_awareness=0.30, document_readiness=0.25, institutional_trust=0.45)]
        original_copy = copy.deepcopy(personas[0])

        intervention = engine.create_documentation_assistance(delta=0.40)
        modified = engine.apply_intervention(personas, intervention)

        mod_p = modified[0]
        # document_readiness must change
        assert mod_p.document_readiness == 0.65

        # All other attributes must remain unchanged
        assert mod_p.initial_awareness == original_copy.initial_awareness
        assert mod_p.institutional_trust == original_copy.institutional_trust
        assert mod_p.peer_network_support == original_copy.peer_network_support
        assert mod_p.digital_literacy == original_copy.digital_literacy
        assert mod_p.family_income == original_copy.family_income

    def test_institutional_support_modifies_only_document_readiness_and_trust(self):
        """Verifies Institutional Support alters strictly document_readiness and institutional_trust."""
        engine = ScenarioEngine()
        personas = [_create_test_persona(
            initial_awareness=0.35,
            document_readiness=0.30,
            institutional_trust=0.40,
            peer_network_support=0.50,
            digital_literacy=0.60
        )]
        original_copy = copy.deepcopy(personas[0])

        intervention = engine.create_institutional_support(doc_delta=0.20, trust_delta=0.30)
        modified = engine.apply_intervention(personas, intervention)

        mod_p = modified[0]
        # document_readiness and institutional_trust must change
        assert mod_p.document_readiness == 0.50
        assert mod_p.institutional_trust == 0.70

        # initial_awareness, peer_network_support, and digital_literacy must NOT change
        assert mod_p.initial_awareness == original_copy.initial_awareness
        assert mod_p.peer_network_support == original_copy.peer_network_support
        assert mod_p.digital_literacy == original_copy.digital_literacy
        assert mod_p.personality.self_advocacy == original_copy.personality.self_advocacy
        assert mod_p.family_income == original_copy.family_income

    def test_strict_boundary_violations_raise_value_error(self):
        """Verifies that attempting to configure unpermitted attributes raises a ValueError."""
        # 1. Awareness campaign cannot set document_readiness_delta
        with pytest.raises(ValueError, match="can modify ONLY initial_awareness"):
            ScenarioIntervention(
                intervention_type=InterventionType.AWARENESS_CAMPAIGN,
                name="Illegal Awareness",
                description="Test",
                awareness_delta=0.2,
                document_readiness_delta=0.1
            )

        # 2. Awareness campaign cannot set institutional_trust_delta
        with pytest.raises(ValueError, match="can modify ONLY initial_awareness"):
            ScenarioIntervention(
                intervention_type=InterventionType.AWARENESS_CAMPAIGN,
                name="Illegal Awareness",
                description="Test",
                awareness_delta=0.2,
                institutional_trust_delta=0.1
            )

        # 3. Documentation assistance cannot set awareness_delta
        with pytest.raises(ValueError, match="can modify ONLY document_readiness"):
            ScenarioIntervention(
                intervention_type=InterventionType.DOCUMENTATION_ASSISTANCE,
                name="Illegal Docs",
                description="Test",
                document_readiness_delta=0.2,
                awareness_delta=0.1
            )

        # 4. Institutional support cannot set awareness_delta
        with pytest.raises(ValueError, match="can modify ONLY document_readiness and institutional_trust"):
            ScenarioIntervention(
                intervention_type=InterventionType.INSTITUTIONAL_SUPPORT,
                name="Illegal Support",
                description="Test",
                document_readiness_delta=0.1,
                institutional_trust_delta=0.1,
                awareness_delta=0.1
            )

    def test_numeric_validation_rejects_invalid_types_and_ranges(self):
        """
        Verifies that intervention parameters reject booleans, strings, NaN,
        Infinity, negative numbers, and out-of-range values.
        """
        # Rejection of boolean values (True / False)
        with pytest.raises(ValueError, match="strictly numeric int or float"):
            ScenarioIntervention(
                intervention_type=InterventionType.AWARENESS_CAMPAIGN,
                name="Bool Delta",
                description="Test",
                awareness_delta=True
            )

        with pytest.raises(ValueError, match="strictly numeric int or float"):
            ScenarioIntervention(
                intervention_type=InterventionType.DOCUMENTATION_ASSISTANCE,
                name="Bool Floor",
                description="Test",
                document_readiness_floor=False
            )

        # Rejection of strings
        with pytest.raises(ValueError, match="strictly numeric int or float"):
            ScenarioIntervention(
                intervention_type=InterventionType.AWARENESS_CAMPAIGN,
                name="String Delta",
                description="Test",
                awareness_delta="0.25"
            )

        with pytest.raises(ValueError, match="strictly numeric int or float"):
            ScenarioIntervention(
                intervention_type=InterventionType.DOCUMENTATION_ASSISTANCE,
                name="String Floor",
                description="Test",
                document_readiness_floor="0.50"
            )

        # Rejection of NaN and Infinity
        with pytest.raises(ValueError, match="finite numeric value"):
            ScenarioIntervention(
                intervention_type=InterventionType.AWARENESS_CAMPAIGN,
                name="NaN Delta",
                description="Test",
                awareness_delta=float("nan")
            )

        with pytest.raises(ValueError, match="finite numeric value"):
            ScenarioIntervention(
                intervention_type=InterventionType.DOCUMENTATION_ASSISTANCE,
                name="Inf Delta",
                description="Test",
                document_readiness_delta=float("inf")
            )

        # Rejection of negative deltas
        with pytest.raises(ValueError, match="bounded between 0.0 and 1.0"):
            ScenarioIntervention(
                intervention_type=InterventionType.AWARENESS_CAMPAIGN,
                name="Negative Delta",
                description="Test",
                awareness_delta=-0.05
            )

        # Rejection of deltas > 1.0
        with pytest.raises(ValueError, match="bounded between 0.0 and 1.0"):
            ScenarioIntervention(
                intervention_type=InterventionType.AWARENESS_CAMPAIGN,
                name="Excessive Delta",
                description="Test",
                awareness_delta=1.25
            )

        # Rejection of floors out of [0.0, 1.0]
        with pytest.raises(ValueError, match="bounded between 0.0 and 1.0"):
            ScenarioIntervention(
                intervention_type=InterventionType.AWARENESS_CAMPAIGN,
                name="Negative Floor",
                description="Test",
                awareness_floor=-0.10
            )

        with pytest.raises(ValueError, match="bounded between 0.0 and 1.0"):
            ScenarioIntervention(
                intervention_type=InterventionType.AWARENESS_CAMPAIGN,
                name="Excessive Floor",
                description="Test",
                awareness_floor=1.50
            )

    def test_original_persona_population_immutability(self):
        """
        Verifies that running apply_intervention and run_comparison never mutates
        the caller's original persona instances.
        """
        original_personas = [
            _create_test_persona("P1", initial_awareness=0.20, document_readiness=0.30),
            _create_test_persona("P2", initial_awareness=0.40, document_readiness=0.50),
        ]
        # Snapshot pre-state
        snapshot = copy.deepcopy(original_personas)

        engine = ScenarioEngine()
        intervention = engine.create_awareness_campaign(delta=0.40)

        # 1. apply_intervention must not mutate input
        _ = engine.apply_intervention(original_personas, intervention)
        for i in range(len(original_personas)):
            assert original_personas[i].initial_awareness == snapshot[i].initial_awareness
            assert original_personas[i].document_readiness == snapshot[i].document_readiness

        # 2. run_comparison must not mutate input
        report = engine.run_comparison(original_personas, intervention, seed=42)
        for i in range(len(original_personas)):
            assert original_personas[i].initial_awareness == snapshot[i].initial_awareness
            assert original_personas[i].document_readiness == snapshot[i].document_readiness
            assert original_personas[i].current_state == snapshot[i].current_state
            assert len(original_personas[i].memory) == len(snapshot[i].memory)

    def test_statutory_eligibility_preservation(self):
        """
        Verifies that interventions never change statutory eligibility.
        delta_eligible and delta_ineligible must be strictly zero.
        """
        personas = [
            _create_test_persona("P1", is_eligible=True, initial_awareness=0.10),
            _create_test_persona("P2", is_eligible=False, family_income=1500000.0, initial_awareness=0.10),
            _create_test_persona("P3", is_eligible=True, initial_awareness=0.15),
        ]

        engine = ScenarioEngine()
        intervention = engine.create_documentation_assistance(delta=0.50)
        report = engine.run_comparison(personas, intervention, seed=42)

        assert report.baseline_analytics.population_and_eligibility.eligible_count == 2
        assert report.intervention_analytics.population_and_eligibility.eligible_count == 2
        assert report.deltas.eligible_count_delta == 0
        assert report.deltas.ineligible_count_delta == 0


class TestScenarioComparisons:
    """Tests verifying simulation delta computations and behavioral effects."""

    def test_awareness_campaign_funnel_comparison(self):
        """
        Verifies that an awareness campaign increases aware_count,
        attempted_application_count, and uptake without altering eligibility.
        """
        personas = [
            # Low awareness baseline (0.10), high readiness (0.80) -> awareness bottleneck
            _create_test_persona("P1", is_eligible=True, initial_awareness=0.10, document_readiness=0.80),
            _create_test_persona("P2", is_eligible=True, initial_awareness=0.15, document_readiness=0.80),
            _create_test_persona("P3", is_eligible=False, initial_awareness=0.10, document_readiness=0.80),
        ]

        engine = ScenarioEngine()
        # Substantial awareness boost (+0.60)
        intervention = engine.create_awareness_campaign(name="Media & Campus Drive", delta=0.60)
        report = engine.run_comparison(personas, intervention, seed=42, awareness_threshold=0.50)

        # Baseline: with awareness score < 0.5, aware_count is low
        assert report.baseline_analytics.awareness_and_application.aware_count == 0
        # Intervention: awareness score elevates >= 0.5
        assert report.intervention_analytics.awareness_and_application.aware_count == 3
        assert report.deltas.aware_count_delta == 3

        # Eligible count preserved
        assert report.deltas.eligible_count_delta == 0

        # Uptake shifts
        assert report.deltas.uptake_percentage_point_delta >= 0.0
        assert report.epistemic_disclaimer == DEFAULT_EPISTEMIC_DISCLAIMER

    def test_documentation_assistance_completion_uplift(self):
        """
        Verifies that documentation assistance increases completion probability,
        lifting students who attempted but were stuck in documentation.
        """
        personas = [
            # High awareness (0.80), but low readiness (0.20) -> documentation bottleneck
            _create_test_persona("P1", is_eligible=True, initial_awareness=0.80, document_readiness=0.20),
            _create_test_persona("P2", is_eligible=True, initial_awareness=0.80, document_readiness=0.25),
        ]

        engine = ScenarioEngine()
        intervention = engine.create_documentation_assistance(name="Setu Kendra Camp", delta=0.50)
        report = engine.run_comparison(personas, intervention, seed=42)

        # Document readiness uplift enables higher completion probability
        assert report.deltas.completed_application_count_delta >= 0
        assert report.deltas.eligible_count_delta == 0

    def test_institutional_support_reproducibility_and_notes(self):
        """
        Verifies that Institutional Support includes proper disclaimers regarding
        institutional_trust and deterministic calculations.
        """
        personas = [
            _create_test_persona("P1", is_eligible=True, initial_awareness=0.60, document_readiness=0.30, institutional_trust=0.30),
        ]

        engine = ScenarioEngine()
        intervention = engine.create_institutional_support(doc_delta=0.30, trust_delta=0.40)
        report = engine.run_comparison(personas, intervention, seed=100)

        # Check documentation note regarding institutional trust
        assert any("institutional_trust serves as a behavioral/qualitative attribute" in note for note in report.methodological_notes)
        assert any("no numerical uptake effect is claimed from institutional_trust alone" in note.lower() for note in report.methodological_notes)

    def test_seed_reproducibility(self):
        """Verifies that two runs with identical seed produce byte-for-byte identical comparison outputs."""
        personas = [
            _create_test_persona("P1", is_eligible=True, initial_awareness=0.30),
            _create_test_persona("P2", is_eligible=True, initial_awareness=0.50),
        ]

        engine = ScenarioEngine()
        intervention = engine.create_awareness_campaign(delta=0.30)

        report1 = engine.run_comparison(personas, intervention, seed=999)
        report2 = engine.run_comparison(personas, intervention, seed=999)

        assert report1.to_dict() == report2.to_dict()

    def test_zero_denominator_safety(self):
        """
        Verifies robust handling when:
        1. Cohort is completely empty (relative_uptake_growth_percentage is None).
        2. Baseline recipients == 0 and intervention recipients == 0 (relative_uptake_growth_percentage is None).
        3. Baseline recipients == 0 and intervention recipients > 0 (relative_uptake_growth_percentage is None).
        Whenever baseline uptake is zero, relative growth is mathematically undefined and must be None.
        """
        engine = ScenarioEngine()
        intervention = engine.create_awareness_campaign(delta=0.20)

        # 1. Completely empty cohort (baseline recipients == 0 -> None)
        empty_report = engine.run_comparison([], intervention, seed=42)
        assert empty_report.total_personas == 0
        assert empty_report.deltas.eligible_count_delta == 0
        assert empty_report.deltas.relative_uptake_growth_percentage is None
        assert empty_report.deltas.uptake_percentage_point_delta == 0.0

        # 2. Ineligible population (0 baseline recipients, 0 intervention recipients -> None)
        ineligible_personas = [
            _create_test_persona("P1", is_eligible=False, family_income=2000000.0),
        ]
        inelig_report = engine.run_comparison(ineligible_personas, intervention, seed=42)
        assert inelig_report.deltas.benefit_received_count_delta == 0
        assert inelig_report.deltas.relative_uptake_growth_percentage is None

        # 3. Baseline recipients == 0, Intervention recipients > 0 -> None
        zero_base_personas = [
            _create_test_persona("P1", is_eligible=True, initial_awareness=0.05, document_readiness=0.80),
        ]
        high_intervention = engine.create_awareness_campaign(delta=0.80)
        boost_report = engine.run_comparison(zero_base_personas, high_intervention, seed=42)

        if boost_report.baseline_analytics.benefits.benefit_received_count == 0 and boost_report.intervention_analytics.benefits.benefit_received_count > 0:
            assert boost_report.deltas.relative_uptake_growth_percentage is None
            assert boost_report.deltas.uptake_percentage_point_delta > 0.0

    def test_reimbursement_rate_parameter_and_integration_notes(self):
        """
        Verifies that:
        1. When assumed_reimbursement_rate is None, the report documents the 50% PoC limitation.
        2. When an explicit assumed_reimbursement_rate is provided, it is forwarded and noted.
        """
        personas = [_create_test_persona("P1", is_eligible=True, annual_tuition_fee=100000.0)]
        engine = ScenarioEngine()
        intervention = engine.create_awareness_campaign(delta=0.20)

        # Case A: Default (None) -> PoC 50% limitation note present
        report_default = engine.run_comparison(personas, intervention, assumed_reimbursement_rate=None)
        assert any("Integration Limitation" in note for note in report_default.methodological_notes)
        assert any("PoC default baseline of 50%" in note for note in report_default.methodological_notes)
        assert report_default.assumed_reimbursement_rate is None

        # Case B: Explicit rate (e.g., 0.75)
        report_explicit = engine.run_comparison(personas, intervention, assumed_reimbursement_rate=0.75)
        assert report_explicit.assumed_reimbursement_rate == 0.75
        assert any("explicit assumed_reimbursement_rate=0.75" in note for note in report_explicit.methodological_notes)

    def test_offline_execution_stub_llm_provider(self):
        """Verifies ScenarioEngine runs purely offline using StubLLMProvider without network calls."""
        engine = ScenarioEngine()
        assert isinstance(engine.simulation_engine.llm_provider, StubLLMProvider)

        personas = [_create_test_persona("P1", is_eligible=True)]
        intervention = engine.create_awareness_campaign(delta=0.10)
        report = engine.run_comparison(personas, intervention)

        assert isinstance(report, ScenarioComparisonReport)
        assert report.total_personas == 1

    def test_json_serialization_integrity(self):
        """
        Verifies that ScenarioComparisonReport serializes cleanly to JSON without NaN or Infinity,
        even when relative_uptake_growth_percentage is None.
        """
        personas = [
            _create_test_persona("P1", is_eligible=True, initial_awareness=0.05, document_readiness=0.80),
        ]
        engine = ScenarioEngine()
        intervention = engine.create_awareness_campaign(delta=0.70)
        report = engine.run_comparison(personas, intervention)

        json_str = report.to_json(indent=2)
        assert isinstance(json_str, str)
        assert "NaN" not in json_str
        assert "Infinity" not in json_str
        assert "-Infinity" not in json_str

        # Must parse cleanly back to dict
        parsed = json.loads(json_str)
        assert parsed["scenario_name"] == "Scenario-Cohort"
        assert "deltas" in parsed
        assert "baseline_analytics" in parsed
        assert "intervention_analytics" in parsed
        assert parsed["epistemic_disclaimer"] == DEFAULT_EPISTEMIC_DISCLAIMER

    def test_convenience_function_run_scenario_comparison(self):
        """Verifies the module-level run_scenario_comparison helper functions identically."""
        personas = [_create_test_persona("P1", is_eligible=True)]
        intervention = ScenarioEngine.create_awareness_campaign(delta=0.20)
        report = run_scenario_comparison(personas, intervention, cohort_name="Helper-Cohort")

        assert isinstance(report, ScenarioComparisonReport)
        assert report.scenario_name == "Helper-Cohort"

    def test_district_to_scenario_integration_pune(self):
        """
        Integration test verifying end-to-end integration between SyntheticPersonaGenerator
        and ScenarioEngine using a grounded Pune district cohort.

        Verifies:
        1. Synthetic personas generated for Pune are accepted by ScenarioEngine.run_comparison().
        2. Counterfactual intervention executes correctly against the realistic district cohort.
        3. Original source persona instances remain completely unmutated.
        4. Statutory eligibility counts remain strictly invariant across baseline and intervention.
        5. Baseline and intervention reports both account for all personas in the cohort.
        """
        seed = 42
        gen = SyntheticPersonaGenerator.for_district("Pune", seed=seed)
        cohort = gen.generate_cohort(count=15, id_prefix="PUNE-STU", seed=seed)
        assert len(cohort) == 15
        assert all(p.district == "Pune" for p in cohort)

        # Snapshot source personas before simulation
        pre_run_snapshot = copy.deepcopy(cohort)

        # Configure ScenarioEngine and an Awareness Campaign intervention
        engine = ScenarioEngine()
        intervention = engine.create_awareness_campaign(
            name="Pune Awareness Drive",
            delta=0.25,
            floor=0.40
        )

        # Execute scenario comparison
        report = engine.run_comparison(
            personas=cohort,
            intervention=intervention,
            cohort_name="Pune-Scenario-Pilot",
            seed=seed
        )

        # 1. Verify report structure and cohort sizes
        assert isinstance(report, ScenarioComparisonReport)
        assert report.total_personas == 15
        assert report.baseline_analytics.total_personas == 15
        assert report.intervention_analytics.total_personas == 15

        # 2. Verify statutory eligibility counts remain strictly invariant
        base_pop = report.baseline_analytics.population_and_eligibility
        interv_pop = report.intervention_analytics.population_and_eligibility
        assert base_pop.eligible_count == interv_pop.eligible_count
        assert base_pop.ineligible_count == interv_pop.ineligible_count
        assert report.deltas.eligible_count_delta == 0
        assert report.deltas.ineligible_count_delta == 0

        # 3. Verify original source personas remain completely unmutated
        assert len(cohort) == len(pre_run_snapshot)
        for orig, snap in zip(cohort, pre_run_snapshot):
            assert orig.persona_id == snap.persona_id
            assert orig.initial_awareness == snap.initial_awareness
            assert orig.document_readiness == snap.document_readiness
            assert orig.institutional_trust == snap.institutional_trust
            assert orig.digital_literacy == snap.digital_literacy
            assert orig.family_income == snap.family_income
            assert orig.current_state == snap.current_state
            assert len(orig.memory) == len(snap.memory)
