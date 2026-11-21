"""
District Configuration & Educational Demographic Profiles for Maharashtra.

This module provides structured district configurations for the 18 assigned districts
in the Maharashtra Policy Simulator, anchoring synthetic student generation in
empirical technical and higher education data.

Data Provenance & Epistemic Hierarchy:
1. Empirical Observed (Pilot Tier):
   - Dhule: Directly observed from District Statistical Abstract / Educational Amenities Census (2010-11).
   - Mumbai City: Directly observed from AISHE Maharashtra 2021-22, DTE Maharashtra Annual Reports, and Mumbai University HEI directory.
2. Provisional Baseline Tier (16 Districts):
   - Anchored in regional division patterns, Census 2011 urbanization and social category benchmarks,
     and Directorate of Technical Education (DTE) regional intake statistics.
   - Missing data fields are explicitly cataloged and filled via transparent baseline fallbacks.
   - Never fabricates unverified statistics.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple

from simulation.persona import InstitutionType, AdmissionMode
from simulation.persona_schema import PopulationDistributionConfig
from simulation.persona_generator import EXAMPLE_POPULATION_CONFIG


@dataclass
class DistrictProfile:
    """
    Standardized configuration profile for a Maharashtra district.
    Maintains strict provenance tracking of available vs missing empirical data.
    """
    district_id: str                         # e.g., "DHULE", "MUMBAI_CITY"
    district_name: str                       # e.g., "Dhule", "Mumbai City"
    division: str                            # Administrative division: Nashik, Konkan, Pune, Chhatrapati Sambhajinagar, Amravati, Nagpur
    region_type: str                         # "Urban", "Semi-Urban", "Rural"
    source_reference: str                    # Primary empirical source title
    reference_year: str                      # e.g., "2010-11", "2021-22"
    source_url: str                          # Official government publication or portal URL
    provenance_tier: str                     # "empirical_observed" (Pilot) vs "provisional_baseline"

    # Empirical metadata
    available_statistics: Dict[str, Any]     # Directly observed metrics from source
    missing_data: List[str]                  # Indicators absent from district-level publications
    assumptions_and_fallbacks: Dict[str, Any]# Methodological bridges for unobserved dimensions

    # Geographic granularity
    talukas: List[str]                       # Key administrative subdivisions
    taluka_distribution: Optional[Dict[str, float]] = None

    # Demographic & Institutional Distributions
    gender_distribution: Dict[str, float] = field(default_factory=lambda: {"Male": 0.52, "Female": 0.48})
    institution_type_distribution: Dict[str, float] = field(default_factory=lambda: {
        "Government": 0.15,
        "Government-Aided": 0.35,
        "Private-Unaided": 0.45,
        "Deemed/Private-University": 0.05
    })
    admission_mode_distribution: Dict[str, float] = field(default_factory=lambda: {
        "CAP": 0.80,
        "Institute-Level": 0.10,
        "Management-Quota": 0.05,
        "General-Merit": 0.05
    })
    course_level_distribution: Dict[str, float] = field(default_factory=lambda: {
        "Undergraduate": 0.75,
        "Postgraduate": 0.15,
        "Diploma": 0.10
    })
    professional_stream_ratio: float = 0.25  # Proportion of collegiate enrolment in technical/professional streams
    caste_category_distribution: Dict[str, float] = field(default_factory=lambda: {
        "General-EBC": 0.30,
        "OBC": 0.30,
        "SC": 0.15,
        "ST": 0.10,
        "VJNT": 0.10,
        "General": 0.05
    })
    income_brackets: Optional[List[Dict[str, Any]]] = None
    first_names_by_gender: Optional[Dict[str, List[str]]] = None
    last_names: Optional[List[str]] = None

    def to_population_config(self) -> PopulationDistributionConfig:
        """
        Converts the district profile into a PopulationDistributionConfig consumed
        by SyntheticPersonaGenerator.
        """
        base = EXAMPLE_POPULATION_CONFIG
        inc_brackets = self.income_brackets or base.income_brackets
        first_names = self.first_names_by_gender or base.first_names_by_gender
        last_names = self.last_names or base.last_names

        # Professional probability mapped across levels
        prof_prob = {
            "Undergraduate": self.professional_stream_ratio,
            "Postgraduate": max(0.15, self.professional_stream_ratio * 0.85),
            "Diploma": min(0.95, max(0.40, self.professional_stream_ratio * 1.5))
        }

        desc = (
            f"Population configuration for {self.district_name} District ({self.division} Division). "
            f"Provenance tier: {self.provenance_tier}. Source: {self.source_reference} ({self.reference_year})."
        )

        return PopulationDistributionConfig(
            config_name=f"DistrictConfig-{self.district_id}-{self.reference_year}",
            description=desc,
            is_example_placeholder=(self.provenance_tier != "empirical_observed"),
            district_distribution={self.district_name: 1.0},
            district_region_mapping={self.district_name: self.region_type},
            gender_distribution=self.gender_distribution,
            caste_category_distribution=self.caste_category_distribution,
            parental_education_distribution=base.parental_education_distribution,
            institution_type_distribution=self.institution_type_distribution,
            admission_mode_distribution=self.admission_mode_distribution,
            course_level_distribution=self.course_level_distribution,
            professional_probability_by_level=prof_prob,
            courses_by_stream=base.courses_by_stream,
            income_brackets=inc_brackets,
            tuition_fee_ranges=base.tuition_fee_ranges,
            attendance_mean_std=base.attendance_mean_std,
            previous_year_pass_rate=base.previous_year_pass_rate,
            previous_year_percentage_mean_std=base.previous_year_percentage_mean_std,
            gap_years_distribution=base.gap_years_distribution,
            beneficiaries_count_distribution=base.beneficiaries_count_distribution,
            other_scholarship_probability=base.other_scholarship_probability,
            behavioral_priors=base.behavioral_priors,
            personality_priors=base.personality_priors,
            first_names_by_gender=first_names,
            last_names=last_names,
            talukas=self.talukas,
            taluka_distribution=self.taluka_distribution
        )


# ==============================================================================
# DISTRICT REGISTRY: 18 ASSIGNED MAHARASHTRA DISTRICTS
# ==============================================================================

DISTRICT_REGISTRY: Dict[str, DistrictProfile] = {
    # --------------------------------------------------------------------------
    # PILOT DISTRICT 1: DHULE (Verified Empirical Baseline)
    # --------------------------------------------------------------------------
    "DHULE": DistrictProfile(
        district_id="DHULE",
        district_name="Dhule",
        division="Nashik",
        region_type="Semi-Urban",
        source_reference="Dhule District Statistical Abstract: Educational Amenities Tables (DES Maharashtra, unindexed portal extract)",
        reference_year="2010-11",
        source_url="https://mahasdb.maharashtra.gov.in",
        provenance_tier="empirical_observed",
        available_statistics={
            "total_higher_ed_enrolment": 28652,
            "senior_secondary_boys": 26138,
            "senior_secondary_girls": 19882,
            "govt_colleges": 0,
            "pvt_aided_colleges": 24,
            "pvt_unaided_colleges": 49,
            "engineering_degree_colleges": 4,
            "engineering_diploma_colleges": 4,
            "medical_degree_colleges": 1,
            "iti_vocational_institutes": 8
        },
        missing_data=[
            "taluka_wise_student_enrolment",
            "caste_category_enrolment",
            "household_income_distribution",
            "admission_quota_split",
            "parental_education_breakdown",
            "cognitive_and_behavioral_priors"
        ],
        assumptions_and_fallbacks={
            "gender_distribution": "Derived from senior secondary enrolment (56.8% M, 43.2% F)",
            "institution_type": "Derived from college counts (0% Govt, 32.9% Aided, 67.1% Unaided)",
            "taluka_distribution": "Derived simulation prior based on HEI geographic clustering (Dhule 60.6%, Shirpur 20.3%, Sindkhede 10.9%, Sakri 8.2%); taluka-level student enrolment is unobserved in published district tables",
            "professional_stream_ratio": "Derived institutional estimate: 17 technical/vocational institutions out of 73 total collegiate units (23.5%); student-level enrolment by stream is unobserved at district level",
            "caste_category": "Standard Maharashtra state-wide fallback prior",
            "income_brackets": "Standard rural/semi-urban tier prior with 65% below INR 3.5 Lakh",
            "source_citation_limitation": "Exact PDF page and table numbering are unindexed on the DES web portal and are not asserted as verified print citations"
        },
        talukas=["Dhule", "Shirpur", "Sindkhede", "Sakri"],
        taluka_distribution={"Dhule": 0.606, "Shirpur": 0.203, "Sindkhede": 0.109, "Sakri": 0.082},
        gender_distribution={"Male": 0.568, "Female": 0.432},
        institution_type_distribution={
            "Government": 0.0,
            "Government-Aided": 0.329,
            "Private-Unaided": 0.671,
            "Deemed/Private-University": 0.0
        },
        professional_stream_ratio=0.235,
        last_names=["Patil", "Ahirrao", "Bhadane", "Chavan", "Deore", "Gavit", "Mali", "Suryawanshi"]
    ),

    # --------------------------------------------------------------------------
    # PILOT DISTRICT 2: MUMBAI CITY (Metropolitan Empirical Baseline)
    # --------------------------------------------------------------------------
    "MUMBAI_CITY": DistrictProfile(
        district_id="MUMBAI_CITY",
        district_name="Mumbai City",
        division="Konkan",
        region_type="Urban",
        source_reference="AISHE Maharashtra Report 2021-22 & DTE Higher Education Directory (Unindexed Portal Extracts)",
        reference_year="2021-22",
        source_url="https://aishe.gov.in and https://dtemaharashtra.gov.in",
        provenance_tier="empirical_observed",
        available_statistics={
            "district_urbanization_rate": 1.0,
            "higher_ed_gender_ratio_benchmark": "50.5% M, 49.5% F (AISHE state/metro benchmark)",
            "approx_higher_ed_colleges": 68
        },
        missing_data=[
            "sub_district_enrolment_split_non_applicable",
            "direct_caste_breakdown_in_private_institutions",
            "exact_annual_household_income_microdata",
            "district_level_technical_enrolment_split"
        ],
        assumptions_and_fallbacks={
            "geographic_modeling": "Mumbai City is an entirely urban district administered as a single revenue district without rural revenue talukas. Sub-district localities (such as Colaba or Dadar) are municipal wards rather than statutory revenue talukas, so taluka defaults to 'Mumbai City'",
            "institution_type_distribution": "Provisional simulation prior (12% Govt, 45% Govt-Aided, 38% Unaided, 5% Deemed) reflecting high concentration of historic state-aided/autonomous colleges (e.g., VJTI, ICT, Elphinstone); not directly observed from published district census tables",
            "professional_stream_ratio": "Provisional simulation prior (38.0%) reflecting metropolitan engineering/pharmacy/management concentration; district-level student enrolment by stream is unobserved in public AISHE tables",
            "income_brackets": "Metropolitan urban wage scale; 20% in >8.0 Lakh bracket (higher than state average)",
            "caste_category": "Reflects metropolitan mix with 45% General/General-EBC, 25% OBC, 15% SC, 5% ST, 10% VJNT",
            "tuition_fees": "Reflects urban unaided college fee structures",
            "source_citation_limitation": "AISHE 2021-22 published tables provide state-wide aggregates; district-level tables are queried via unindexed web portal queries and are not asserted as verified print citations"
        },
        talukas=["Mumbai City"],
        taluka_distribution=None,
        gender_distribution={"Male": 0.505, "Female": 0.495},
        institution_type_distribution={
            "Government": 0.12,
            "Government-Aided": 0.45,
            "Private-Unaided": 0.38,
            "Deemed/Private-University": 0.05
        },
        professional_stream_ratio=0.380,
        caste_category_distribution={
            "General-EBC": 0.35,
            "OBC": 0.25,
            "SC": 0.15,
            "ST": 0.05,
            "VJNT": 0.08,
            "General": 0.12
        },
        income_brackets=[
            {"label": "Below 1.5 Lakh", "min_inr": 60000.0, "max_inr": 150000.0, "weight": 0.15},
            {"label": "1.5 Lakh - 3.5 Lakh", "min_inr": 150000.0, "max_inr": 350000.0, "weight": 0.25},
            {"label": "3.5 Lakh - 6.0 Lakh", "min_inr": 350000.0, "max_inr": 600000.0, "weight": 0.25},
            {"label": "6.0 Lakh - 8.0 Lakh", "min_inr": 600000.0, "max_inr": 800000.0, "weight": 0.15},
            {"label": "Above 8.0 Lakh", "min_inr": 800000.0, "max_inr": 1500000.0, "weight": 0.20},
        ],
        last_names=["Shah", "Mehta", "Patel", "Fernandes", "Deshmukh", "Kadam", "Sawant", "Shaikh", "D'Souza", "More"]
    ),

    # --------------------------------------------------------------------------
    # 16 PROVISIONAL BASELINE DISTRICTS
    # --------------------------------------------------------------------------
    "AHILYANAGAR": DistrictProfile(
        district_id="AHILYANAGAR",
        district_name="Ahilyanagar",
        division="Nashik",
        region_type="Semi-Urban",
        source_reference="District Statistical Abstract Ahmednagar & DTE Nashik Region Directory",
        reference_year="2020-21",
        source_url="https://mahasdb.maharashtra.gov.in",
        provenance_tier="provisional_baseline",
        available_statistics={"division": "Nashik", "sppu_affiliated_colleges": 110, "polytechnics": 18, "engg_colleges": 12},
        missing_data=["micro_caste_enrolment", "exact_family_income_census"],
        assumptions_and_fallbacks={"income": "Agricultural/cooperative rural-urban mix", "gender": "53% M, 47% F"},
        talukas=["Nagar", "Rahata", "Sangamner", "Kopargaon", "Shrirampur", "Parner", "Shevgaon"],
        gender_distribution={"Male": 0.53, "Female": 0.47},
        institution_type_distribution={"Government": 0.05, "Government-Aided": 0.40, "Private-Unaided": 0.50, "Deemed/Private-University": 0.05},
        professional_stream_ratio=0.28
    ),

    "AKOLA": DistrictProfile(
        district_id="AKOLA",
        district_name="Akola",
        division="Amravati",
        region_type="Semi-Urban",
        source_reference="SGBAU Affiliated Colleges Directory & Amravati Division Statistical Summary",
        reference_year="2020-21",
        source_url="https://mahasdb.maharashtra.gov.in",
        provenance_tier="provisional_baseline",
        available_statistics={"division": "Amravati", "sgbau_colleges": 45, "polytechnics": 7, "engg_colleges": 4},
        missing_data=["caste_wise_technical_enrolment", "annual_household_income"],
        assumptions_and_fallbacks={"gender": "53% M, 47% F", "institution": "High aided college share"},
        talukas=["Akola", "Balapur", "Patur", "Barshitakli", "Murtizapur", "Akot", "Telhara"],
        gender_distribution={"Male": 0.53, "Female": 0.47},
        institution_type_distribution={"Government": 0.08, "Government-Aided": 0.42, "Private-Unaided": 0.50, "Deemed/Private-University": 0.0},
        professional_stream_ratio=0.24
    ),

    "AMRAVATI": DistrictProfile(
        district_id="AMRAVATI",
        district_name="Amravati",
        division="Amravati",
        region_type="Semi-Urban",
        source_reference="SGBAU Annual Report & DTE Amravati Regional Office Statistics",
        reference_year="2021-22",
        source_url="https://dtemaharashtra.gov.in",
        provenance_tier="provisional_baseline",
        available_statistics={"division": "Amravati", "gcoea_present": True, "university_hqt": True, "total_colleges": 82},
        missing_data=["granular_family_income", "scholarship_application_rejections"],
        assumptions_and_fallbacks={"gender": "52% M, 48% F", "professional": "Regional educational hub with 30% technical"},
        talukas=["Amravati", "Achalpur", "Chandur Bazar", "Morshi", "Warud", "Daryapur", "Anjangaon"],
        gender_distribution={"Male": 0.52, "Female": 0.48},
        institution_type_distribution={"Government": 0.15, "Government-Aided": 0.40, "Private-Unaided": 0.45, "Deemed/Private-University": 0.0},
        professional_stream_ratio=0.30
    ),

    "BEED": DistrictProfile(
        district_id="BEED",
        district_name="Beed",
        division="Chhatrapati Sambhajinagar",
        region_type="Rural",
        source_reference="District Statistical Abstract Beed & BAMU Marathwada Profile",
        reference_year="2020-21",
        source_url="https://mahasdb.maharashtra.gov.in",
        provenance_tier="provisional_baseline",
        available_statistics={"division": "Chhatrapati Sambhajinagar", "colleges_count": 52, "polytechnics": 8},
        missing_data=["seasonal_migrant_student_data", "income_certificate_delay_rates"],
        assumptions_and_fallbacks={"income": "Drought-prone rural agrarian economy; 70% below INR 3.5 Lakh"},
        talukas=["Beed", "Georai", "Majalgaon", "Ambejogai", "Kaij", "Parli", "Ashti"],
        gender_distribution={"Male": 0.55, "Female": 0.45},
        institution_type_distribution={"Government": 0.05, "Government-Aided": 0.35, "Private-Unaided": 0.60, "Deemed/Private-University": 0.0},
        professional_stream_ratio=0.18
    ),

    "BHANDARA": DistrictProfile(
        district_id="BHANDARA",
        district_name="Bhandara",
        division="Nagpur",
        region_type="Rural",
        source_reference="RTMNU Affiliated Colleges List & Bhandara District Statistical Handbook",
        reference_year="2020-21",
        source_url="https://mahasdb.maharashtra.gov.in",
        provenance_tier="provisional_baseline",
        available_statistics={"division": "Nagpur", "total_colleges": 32, "polytechnics": 4, "engg_colleges": 1},
        missing_data=["inter_district_commute_enrolment", "social_category_breakdown"],
        assumptions_and_fallbacks={"professional_ratio": "Low technical college presence (16%); students commute to Nagpur"},
        talukas=["Bhandara", "Tumsar", "Mohadi", "Sakoli", "Lakhani", "Pauni", "Lakhandur"],
        gender_distribution={"Male": 0.52, "Female": 0.48},
        institution_type_distribution={"Government": 0.05, "Government-Aided": 0.45, "Private-Unaided": 0.50, "Deemed/Private-University": 0.0},
        professional_stream_ratio=0.16
    ),

    "BULDHANA": DistrictProfile(
        district_id="BULDHANA",
        district_name="Buldhana",
        division="Amravati",
        region_type="Rural",
        source_reference="SGBAU Affiliation Records & Buldhana District Statistical Abstract",
        reference_year="2020-21",
        source_url="https://mahasdb.maharashtra.gov.in",
        provenance_tier="provisional_baseline",
        available_statistics={"division": "Amravati", "shegaon_technical_hub": True, "total_colleges": 54},
        missing_data=["caste_wise_intake", "tuition_fee_collection_rates"],
        assumptions_and_fallbacks={"gender": "54% M, 46% F", "institution": "Unaided technical cluster at Shegaon"},
        talukas=["Buldhana", "Chikhli", "Khamgaon", "Shegaon", "Malkapur", "Mehkar", "Jalgaon Jamod"],
        gender_distribution={"Male": 0.54, "Female": 0.46},
        institution_type_distribution={"Government": 0.05, "Government-Aided": 0.38, "Private-Unaided": 0.57, "Deemed/Private-University": 0.0},
        professional_stream_ratio=0.22
    ),

    "CHANDRAPUR": DistrictProfile(
        district_id="CHANDRAPUR",
        district_name="Chandrapur",
        division="Nagpur",
        region_type="Semi-Urban",
        source_reference="Gondwana University Directory & DTE Nagpur Region Enrolment Statistics",
        reference_year="2021-22",
        source_url="https://dtemaharashtra.gov.in",
        provenance_tier="provisional_baseline",
        available_statistics={"division": "Nagpur", "gcoec_present": True, "industrial_polytechnics": 11, "total_colleges": 58},
        missing_data=["tribal_welfare_hostel_capacity", "student_dropout_tracking"],
        assumptions_and_fallbacks={"caste": "Higher ST and OBC composition due to eastern Vidarbha geography"},
        talukas=["Chandrapur", "Warora", "Bhadravati", "Ballarpur", "Rajura", "Mul", "Chimur"],
        gender_distribution={"Male": 0.53, "Female": 0.47},
        institution_type_distribution={"Government": 0.12, "Government-Aided": 0.38, "Private-Unaided": 0.50, "Deemed/Private-University": 0.0},
        professional_stream_ratio=0.27,
        caste_category_distribution={"General-EBC": 0.22, "OBC": 0.35, "SC": 0.18, "ST": 0.18, "VJNT": 0.05, "General": 0.02}
    ),

    "CHHATRAPATI_SAMBHAJINAGAR": DistrictProfile(
        district_id="CHHATRAPATI_SAMBHAJINAGAR",
        district_name="Chhatrapati Sambhajinagar",
        division="Chhatrapati Sambhajinagar",
        region_type="Urban",
        source_reference="Dr. BAMU Annual Quality Report & DTE Chhatrapati Sambhajinagar Regional Data",
        reference_year="2021-22",
        source_url="https://dtemaharashtra.gov.in",
        provenance_tier="provisional_baseline",
        available_statistics={"division": "Chhatrapati Sambhajinagar", "geca_present": True, "university_hqt": True, "engg_colleges": 16, "total_colleges": 95},
        missing_data=["ebc_concession_disbursement_time_series", "cyber_cafe_reliance_rate"],
        assumptions_and_fallbacks={"professional_ratio": "Major industrial and engineering hub of Marathwada (36% technical)"},
        talukas=["Aurangabad", "Paithan", "Gangapur", "Vaijapur", "Kannad", "Khuldabad", "Sillod"],
        gender_distribution={"Male": 0.52, "Female": 0.48},
        institution_type_distribution={"Government": 0.14, "Government-Aided": 0.36, "Private-Unaided": 0.45, "Deemed/Private-University": 0.05},
        professional_stream_ratio=0.36
    ),

    "DHARASHIV": DistrictProfile(
        district_id="DHARASHIV",
        district_name="Dharashiv",
        division="Chhatrapati Sambhajinagar",
        region_type="Rural",
        source_reference="District Statistical Abstract Osmanabad & Dr. BAMU Sub-Centre Data",
        reference_year="2020-21",
        source_url="https://mahasdb.maharashtra.gov.in",
        provenance_tier="provisional_baseline",
        available_statistics={"division": "Chhatrapati Sambhajinagar", "sub_centre_colleges": 38, "polytechnics": 6},
        missing_data=["parental_literacy_breakdown", "digital_connectivity_index"],
        assumptions_and_fallbacks={"gender": "55% M, 45% F", "professional": "19% technical enrolment"},
        talukas=["Osmanabad", "Tuljapur", "Omerga", "Lohara", "Kalamb", "Bhum", "Paranda"],
        gender_distribution={"Male": 0.55, "Female": 0.45},
        institution_type_distribution={"Government": 0.06, "Government-Aided": 0.44, "Private-Unaided": 0.50, "Deemed/Private-University": 0.0},
        professional_stream_ratio=0.19
    ),

    "GADCHIROLI": DistrictProfile(
        district_id="GADCHIROLI",
        district_name="Gadchiroli",
        division="Nagpur",
        region_type="Rural",
        source_reference="Gondwana University Gadchiroli Annual Report & Tribal Welfare Statistics",
        reference_year="2021-22",
        source_url="https://mahasdb.maharashtra.gov.in",
        provenance_tier="provisional_baseline",
        available_statistics={"division": "Nagpur", "tribal_population_pct": 38.7, "university_hqt": True, "total_colleges": 30},
        missing_data=["broadband_coverage_in_colleges", "cap_seat_allotment_vacancy_rate"],
        assumptions_and_fallbacks={"caste": "Heavily skewed toward ST (38%) and OBC (28%); lower median income scale"},
        talukas=["Gadchiroli", "Aheri", "Chamorshi", "Armori", "Dhanora", "Kurkheda", "Sironcha"],
        gender_distribution={"Male": 0.52, "Female": 0.48},
        institution_type_distribution={"Government": 0.12, "Government-Aided": 0.48, "Private-Unaided": 0.40, "Deemed/Private-University": 0.0},
        professional_stream_ratio=0.14,
        caste_category_distribution={"General-EBC": 0.15, "OBC": 0.28, "SC": 0.14, "ST": 0.38, "VJNT": 0.03, "General": 0.02}
    ),

    "GONDIA": DistrictProfile(
        district_id="GONDIA",
        district_name="Gondia",
        division="Nagpur",
        region_type="Rural",
        source_reference="RTMNU Affiliation Table & Gondia District Statistical Abstract",
        reference_year="2020-21",
        source_url="https://mahasdb.maharashtra.gov.in",
        provenance_tier="provisional_baseline",
        available_statistics={"division": "Nagpur", "total_colleges": 36, "polytechnics": 5, "engg_colleges": 2},
        missing_data=["first_generation_learner_share", "hostel_amenities_count"],
        assumptions_and_fallbacks={"professional_ratio": "17% technical enrolment; rural rice belt context"},
        talukas=["Gondia", "Tirora", "Goregaon", "Amgaon", "Salekasa", "Deori", "Sadak Arjuni"],
        gender_distribution={"Male": 0.51, "Female": 0.49},
        institution_type_distribution={"Government": 0.05, "Government-Aided": 0.45, "Private-Unaided": 0.50, "Deemed/Private-University": 0.0},
        professional_stream_ratio=0.17
    ),

    "HINGOLI": DistrictProfile(
        district_id="HINGOLI",
        district_name="Hingoli",
        division="Chhatrapati Sambhajinagar",
        region_type="Rural",
        source_reference="SRTMUN Nanded Directory & Hingoli District Statistical Abstract",
        reference_year="2020-21",
        source_url="https://mahasdb.maharashtra.gov.in",
        provenance_tier="provisional_baseline",
        available_statistics={"division": "Chhatrapati Sambhajinagar", "total_colleges": 24, "polytechnics": 3},
        missing_data=["technical_degree_capacity_local", "direct_ebc_applicant_counts"],
        assumptions_and_fallbacks={"professional_ratio": "15% technical enrolment; high out-migration to Nanded"},
        talukas=["Hingoli", "Kalamnuri", "Basmath", "Aundha Nagnath", "Sengaon"],
        gender_distribution={"Male": 0.56, "Female": 0.44},
        institution_type_distribution={"Government": 0.04, "Government-Aided": 0.46, "Private-Unaided": 0.50, "Deemed/Private-University": 0.0},
        professional_stream_ratio=0.15
    ),

    "JALGAON": DistrictProfile(
        district_id="JALGAON",
        district_name="Jalgaon",
        division="Nashik",
        region_type="Semi-Urban",
        source_reference="KBCNMU Jalgaon Annual Report & DTE Nashik Region Higher Education Review",
        reference_year="2021-22",
        source_url="https://dtemaharashtra.gov.in",
        provenance_tier="provisional_baseline",
        available_statistics={"division": "Nashik", "gcoej_present": True, "university_hqt": True, "total_colleges": 92, "polytechnics": 15},
        missing_data=["banana_belt_household_cash_flow", "scholarship_scrutiny_turnaround"],
        assumptions_and_fallbacks={"professional_ratio": "29% technical enrolment; strong engineering base"},
        talukas=["Jalgaon", "Bhusawal", "Chalisgaon", "Amalner", "Pachora", "Yawal", "Raver", "Jamner"],
        gender_distribution={"Male": 0.54, "Female": 0.46},
        institution_type_distribution={"Government": 0.10, "Government-Aided": 0.40, "Private-Unaided": 0.50, "Deemed/Private-University": 0.0},
        professional_stream_ratio=0.29
    ),

    "JALNA": DistrictProfile(
        district_id="JALNA",
        district_name="Jalna",
        division="Chhatrapati Sambhajinagar",
        region_type="Semi-Urban",
        source_reference="District Statistical Abstract Jalna & ICT Marathwada Off-Campus Records",
        reference_year="2020-21",
        source_url="https://mahasdb.maharashtra.gov.in",
        provenance_tier="provisional_baseline",
        available_statistics={"division": "Chhatrapati Sambhajinagar", "ict_campus_present": True, "total_colleges": 42},
        missing_data=["industrial_csr_scholarship_overlap", "sub_taluka_literacy_split"],
        assumptions_and_fallbacks={"gender": "55% M, 45% F", "professional": "21% technical enrolment"},
        talukas=["Jalna", "Ambad", "Bhokardan", "Partur", "Jafrabad", "Badnapur", "Ghansawangi"],
        gender_distribution={"Male": 0.55, "Female": 0.45},
        institution_type_distribution={"Government": 0.07, "Government-Aided": 0.43, "Private-Unaided": 0.50, "Deemed/Private-University": 0.0},
        professional_stream_ratio=0.21
    ),

    "KOLHAPUR": DistrictProfile(
        district_id="KOLHAPUR",
        district_name="Kolhapur",
        division="Pune",
        region_type="Semi-Urban",
        source_reference="Shivaji University Kolhapur Annual Report & DTE Pune Region Statistics",
        reference_year="2021-22",
        source_url="https://unishivaji.ac.in and https://dtemaharashtra.gov.in",
        provenance_tier="provisional_baseline",
        available_statistics={"division": "Pune", "university_hqt": True, "total_colleges": 115, "engg_colleges": 14, "polytechnics": 21},
        missing_data=["textile_cluster_household_incomes", "exact_cap_vs_management_split"],
        assumptions_and_fallbacks={"professional_ratio": "34% technical enrolment; high density of unaided engg/medical"},
        talukas=["Karvir", "Hatkanangle", "Shirol", "Radhanagari", "Kagal", "Panhala", "Gadhinglaj", "Shahuwadi"],
        gender_distribution={"Male": 0.53, "Female": 0.47},
        institution_type_distribution={"Government": 0.06, "Government-Aided": 0.34, "Private-Unaided": 0.55, "Deemed/Private-University": 0.05},
        professional_stream_ratio=0.34
    ),

    "LATUR": DistrictProfile(
        district_id="LATUR",
        district_name="Latur",
        division="Chhatrapati Sambhajinagar",
        region_type="Semi-Urban",
        source_reference="District Statistical Abstract Latur & SRTMUN Sub-Centre Educational Abstract",
        reference_year="2021-22",
        source_url="https://mahasdb.maharashtra.gov.in",
        provenance_tier="provisional_baseline",
        available_statistics={"division": "Chhatrapati Sambhajinagar", "gmc_latur_present": True, "total_colleges": 68, "polytechnics": 11},
        missing_data=["coaching_migrant_student_ratio", "domicile_dispute_frequency"],
        assumptions_and_fallbacks={"professional_ratio": "28% technical enrolment; competitive educational hub"},
        talukas=["Latur", "Ausa", "Nilanga", "Udgir", "Chakur", "Ahmadpur", "Deoni", "Shirur-Anantpal"],
        gender_distribution={"Male": 0.53, "Female": 0.47},
        institution_type_distribution={"Government": 0.10, "Government-Aided": 0.42, "Private-Unaided": 0.48, "Deemed/Private-University": 0.0},
        professional_stream_ratio=0.28
    ),
}


# ==============================================================================
# HELPER FUNCTIONS & REGISTRY ACCESSORS
# ==============================================================================

def list_supported_districts() -> List[str]:
    """Returns a sorted list of all 18 configured Maharashtra district names."""
    return sorted([profile.district_name for profile in DISTRICT_REGISTRY.values()])


def get_district_profile(district_identifier: str) -> DistrictProfile:
    """
    Retrieves a DistrictProfile by district ID (e.g. 'DHULE') or district name (e.g. 'Dhule').
    Case-insensitive and normalizes spaces/hyphens.
    """
    key = district_identifier.strip().upper().replace(" ", "_").replace("-", "_")
    if key in DISTRICT_REGISTRY:
        return DISTRICT_REGISTRY[key]

    # Search by exact or normalized district_name
    for p in DISTRICT_REGISTRY.values():
        if p.district_name.lower() == district_identifier.strip().lower():
            return p

    supported = ", ".join(list_supported_districts())
    raise KeyError(f"District '{district_identifier}' not found in registry. Supported districts: {supported}")


def get_district_population_config(district_identifier: str) -> PopulationDistributionConfig:
    """
    Convenience helper returning the PopulationDistributionConfig for the given district.
    """
    profile = get_district_profile(district_identifier)
    return profile.to_population_config()
