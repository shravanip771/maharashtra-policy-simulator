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

    # --------------------------------------------------------------------------
    # PILOT DISTRICT: PUNE (Provisional Baseline - Western Maharashtra)
    # --------------------------------------------------------------------------
    "PUNE": DistrictProfile(
        district_id="PUNE",
        district_name="Pune",
        division="Pune",
        region_type="Urban",
        source_reference="Census 2011 (Primary Census Abstract) & DTE Maharashtra Pune Region Seat Matrix",
        reference_year="2011 / 2022-23",
        source_url="https://censusindia.gov.in and https://dtemaharashtra.gov.in",
        provenance_tier="provisional_baseline",
        available_statistics={
            "census_reference_year": "2011",
            "census_population_scope": "General population (all ages, residential census count)",
            "total_population_2011": 9429408,
            "urban_population_2011": 5741026,
            "rural_population_2011": 3688382,
            "urbanization_rate_2011": 0.6088,
            "general_sex_ratio_2011": 915,
            "scheduled_castes_population_2011": 1180689,
            "scheduled_castes_share_2011": 0.1252,
            "scheduled_tribes_population_2011": 348779,
            "scheduled_tribes_share_2011": 0.0370,
            "administrative_revenue_talukas_count": 14,
            "administrative_division": "Pune",
        },
        missing_data=[
            "taluka_wise_student_enrolment",
            "district_level_household_income_microdata",
            "caste_breakdown_in_private_engineering",
            "direct_cap_vs_management_admission_microdata",
            "student_commute_and_hostel_residence_shares",
        ],
        assumptions_and_fallbacks={
            "region_type": (
                "Classified as 'Urban' under the quantitative classification rule (Census 2011 "
                "urban population share >= 60%), with Pune exhibiting a 60.88% urban population "
                "share (5,741,026 urban residents out of 9,429,408 total population). While the "
                "district encompasses 12 agrarian and semi-rural talukas alongside the PMC and PCMC "
                "metropolitan agglomerations, the aggregate classification strictly adheres to the "
                "quantitative threshold rather than behavioral assumptions."
            ),
            "gender_distribution": (
                "Derived simulation prior (51.0% Male, 49.0% Female) reflecting state-wide AISHE higher "
                "education gender parity benchmarks and higher female collegiate participation in the "
                "Pune metropolitan educational hub. It is not an observed district-level collegiate student census."
            ),
            "caste_category_distribution": (
                "Derived simulation prior (38% General-EBC, 24% OBC, 14% SC, 4% ST, 8% VJNT, 12% General) "
                "calibrated to reflect general population demographic baselines (Census 2011: 12.5% SC, 3.7% ST) "
                "adjusted for Maharashtra's 50% statutory reservation quota and high EBC scholarship participation. "
                "Exact student-level caste microdata in unaided higher education institutions is unobserved."
            ),
            "admission_mode_distribution": (
                "Provisional modelling assumption: 80% CAP, 10% Institute-Level, 5% Management-Quota, "
                "5% General-Merit. While anchored in the statutory framework of Maharashtra Act No. XXVIII "
                "of 2015 (which caps institutional/management quotas at 20% in unaided professional colleges "
                "and mandates at least 80% through CAP), this distribution is a provisional simulation modelling "
                "assumption and NOT an observed empirical admission count or universal statutory allocation "
                "across all college types (e.g., government and aided colleges admit 100% via centralized "
                "merit/CAP without management quotas, while non-professional arts/science colleges follow "
                "university-specific merit processes)."
            ),
            "institution_type_distribution": (
                "Derived simulation prior (8% Government, 22% Government-Aided, 60% Private-Unaided, "
                "10% Deemed/Private-University) based on DTE approved seat intake and SPPU college directories, "
                "reflecting the heavy concentration of private engineering colleges and private/deemed universities "
                "in Pune district. It is not an observed student census."
            ),
            "professional_stream_ratio": (
                "Derived simulation prior (36.0% / 0.360) reflecting Pune's role as a major technical and "
                "professional education hub ('Oxford of the East') with high engineering, management, and "
                "pharmacy college density. District-level student enrolment by stream is unobserved as a single "
                "published statistic."
            ),
            "taluka_distribution": (
                "Derived simulation prior based on Higher Education Institution (HEI) geographic concentration "
                "in SPPU and DTE directories (Pune City 38.0%, Haveli 36.0%, Baramati 4.0%, Maval 4.0%, "
                "Khed 3.0%, Shirur 3.0%, Mulshi 2.0%, Daund 2.0%, Indapur 2.0%, Purandar 2.0%, Junnar 1.5%, "
                "Ambegaon 1.5%, Bhor 0.5%, Velhe 0.5%). Published DES and census tables do not provide "
                "taluka-wise collegiate student enrolment counts."
            ),
            "source_citation_limitation": (
                "Census 2011 figures are from published Primary Census Abstract tables. AISHE and DTE technical "
                "intake figures are derived from state reports and portal directories; exact district-level "
                "cross-tabulations are unindexed in print volumes and are not asserted as verified print citations."
            ),
        },
        talukas=[
            "Pune City",
            "Haveli",
            "Khed",
            "Junnar",
            "Ambegaon",
            "Maval",
            "Mulshi",
            "Shirur",
            "Purandar",
            "Velhe",
            "Bhor",
            "Baramati",
            "Indapur",
            "Daund",
        ],
        taluka_distribution={
            "Pune City": 0.380,
            "Haveli": 0.360,
            "Baramati": 0.040,
            "Maval": 0.040,
            "Khed": 0.030,
            "Shirur": 0.030,
            "Mulshi": 0.020,
            "Daund": 0.020,
            "Indapur": 0.020,
            "Purandar": 0.020,
            "Junnar": 0.015,
            "Ambegaon": 0.015,
            "Bhor": 0.005,
            "Velhe": 0.005,
        },
        gender_distribution={"Male": 0.51, "Female": 0.49},
        institution_type_distribution={
            "Government": 0.08,
            "Government-Aided": 0.22,
            "Private-Unaided": 0.60,
            "Deemed/Private-University": 0.10,
        },
        admission_mode_distribution={
            "CAP": 0.80,
            "Institute-Level": 0.10,
            "Management-Quota": 0.05,
            "General-Merit": 0.05,
        },
        course_level_distribution={
            "Undergraduate": 0.75,
            "Postgraduate": 0.15,
            "Diploma": 0.10,
        },
        professional_stream_ratio=0.360,
        caste_category_distribution={
            "General-EBC": 0.38,
            "OBC": 0.24,
            "SC": 0.14,
            "ST": 0.04,
            "VJNT": 0.08,
            "General": 0.12,
        },
        last_names=[
            "Kulkarni",
            "Joshi",
            "Patil",
            "Deshmukh",
            "Shinde",
            "Pawar",
            "Gaikwad",
            "Jadhav",
            "Bhosale",
            "More",
        ],
    ),

    # --------------------------------------------------------------------------
    # PILOT DISTRICT: NAGPUR (Provisional Baseline - Eastern Vidarbha)
    # --------------------------------------------------------------------------
    "NAGPUR": DistrictProfile(
        district_id="NAGPUR",
        district_name="Nagpur",
        division="Nagpur",
        region_type="Urban",
        source_reference="Census 2011 (Primary Census Abstract) & DTE Maharashtra Nagpur Region Seat Matrix",
        reference_year="2011 / 2022-23",
        source_url="https://censusindia.gov.in and https://dtemaharashtra.gov.in",
        provenance_tier="provisional_baseline",
        available_statistics={
            "census_reference_year": "2011",
            "census_population_scope": "General population (all ages, residential census count)",
            "total_population_2011": 4653570,
            "urban_population_2011": 3178198,
            "rural_population_2011": 1475372,
            "urbanization_rate_2011": 0.6830,
            "general_sex_ratio_2011": 951,
            "scheduled_castes_population_2011": 865992,
            "scheduled_castes_share_2011": 0.1861,
            "scheduled_tribes_population_2011": 436009,
            "scheduled_tribes_share_2011": 0.0937,
            "administrative_revenue_talukas_count": 14,
            "administrative_division": "Nagpur",
        },
        missing_data=[
            "taluka_wise_student_enrolment",
            "district_level_household_income_microdata",
            "caste_breakdown_in_private_engineering",
            "direct_cap_vs_management_admission_microdata",
            "vidarbha_regional_student_migration_rates",
        ],
        assumptions_and_fallbacks={
            "region_type": (
                "Classified as 'Urban' under the quantitative classification rule (Census 2011 "
                "urban population share >= 60%), with Nagpur exhibiting a 68.30% urban population "
                "share (3,178,198 urban residents out of 4,653,570 total population). While the "
                "district encompasses 11 agrarian and semi-rural talukas alongside the Nagpur Municipal "
                "Corporation (NMC) metropolitan center, the aggregate classification strictly adheres to "
                "the quantitative threshold rather than behavioral assumptions."
            ),
            "gender_distribution": (
                "Derived simulation prior (52.0% Male, 48.0% Female) reflecting state-wide AISHE higher "
                "education benchmarks and DES senior-secondary gender ratios for eastern Vidarbha. "
                "It is not an observed district-level collegiate student census."
            ),
            "caste_category_distribution": (
                "Derived simulation prior (22% General-EBC, 32% OBC, 20% SC, 10% ST, 8% VJNT, 8% General) "
                "calibrated to reflect observed general population demographic baselines (Census 2011: 18.61% SC, "
                "9.37% ST — notable concentration of Scheduled Castes in Nagpur urban) and Vidarbha's high OBC "
                "share, aligned with the statutory 50% reservation structure and EBC scholarship limits. "
                "Exact student-level caste microdata in unaided higher education institutions is unobserved."
            ),
            "admission_mode_distribution": (
                "Provisional modelling assumption: 80% CAP, 10% Institute-Level, 5% Management-Quota, "
                "5% General-Merit. While anchored in the statutory framework of Maharashtra Act No. XXVIII "
                "of 2015 (which caps institutional/management quotas at 20% in unaided professional colleges "
                "and mandates at least 80% through CAP), this distribution is a provisional simulation modelling "
                "assumption and NOT an observed empirical admission count or universal statutory allocation "
                "across all college types (e.g., government and aided colleges admit 100% via centralized "
                "merit/CAP without management quotas, while non-professional arts/science colleges follow "
                "university-specific merit processes)."
            ),
            "institution_type_distribution": (
                "Derived simulation prior (12% Government, 28% Government-Aided, 55% Private-Unaided, "
                "5% Deemed/Private-University) reflecting Nagpur's prominent public institutions (GCOEN, VNIT, "
                "LITU, Government Polytechnic) alongside substantial private unaided engineering and polytechnic "
                "campuses. It is not an observed student census."
            ),
            "professional_stream_ratio": (
                "Derived simulation prior (30.0% / 0.300) reflecting Nagpur's status as the primary technical "
                "education and university hub for eastern Vidarbha. District-level student enrolment by stream is "
                "unobserved as a single published statistic."
            ),
            "taluka_distribution": (
                "Derived simulation prior based on Higher Education Institution (HEI) geographic concentration "
                "in RTMNU and DTE directories (Nagpur Urban 45.0%, Hingna 15.0%, Nagpur Rural 12.0%, Kamptee 6.0%, "
                "Kalameshwar 4.0%, Umred 4.0%, Savner 3.0%, Katol 3.0%, Ramtek 2.0%, Narkhed 1.5%, Mouda 1.5%, "
                "Parseoni 1.0%, Kuhi 1.0%, Bhivapur 1.0%). Published DES and census tables do not provide "
                "taluka-wise collegiate student enrolment counts."
            ),
            "source_citation_limitation": (
                "Census 2011 figures are from published Primary Census Abstract tables. AISHE and DTE technical "
                "intake figures are derived from state reports and portal directories; exact district-level "
                "cross-tabulations are unindexed in print volumes and are not asserted as verified print citations."
            ),
        },
        talukas=[
            "Nagpur Urban",
            "Nagpur Rural",
            "Hingna",
            "Kamptee",
            "Katol",
            "Narkhed",
            "Savner",
            "Ramtek",
            "Parseoni",
            "Mouda",
            "Umred",
            "Kuhi",
            "Bhivapur",
            "Kalameshwar",
        ],
        taluka_distribution={
            "Nagpur Urban": 0.450,
            "Hingna": 0.150,
            "Nagpur Rural": 0.120,
            "Kamptee": 0.060,
            "Kalameshwar": 0.040,
            "Umred": 0.040,
            "Savner": 0.030,
            "Katol": 0.030,
            "Ramtek": 0.020,
            "Narkhed": 0.015,
            "Mouda": 0.015,
            "Parseoni": 0.010,
            "Kuhi": 0.010,
            "Bhivapur": 0.010,
        },
        gender_distribution={"Male": 0.52, "Female": 0.48},
        institution_type_distribution={
            "Government": 0.12,
            "Government-Aided": 0.28,
            "Private-Unaided": 0.55,
            "Deemed/Private-University": 0.05,
        },
        admission_mode_distribution={
            "CAP": 0.80,
            "Institute-Level": 0.10,
            "Management-Quota": 0.05,
            "General-Merit": 0.05,
        },
        course_level_distribution={
            "Undergraduate": 0.75,
            "Postgraduate": 0.15,
            "Diploma": 0.10,
        },
        professional_stream_ratio=0.300,
        caste_category_distribution={
            "General-EBC": 0.22,
            "OBC": 0.32,
            "SC": 0.20,
            "ST": 0.10,
            "VJNT": 0.08,
            "General": 0.08,
        },
        last_names=[
            "Meshram",
            "Wankhede",
            "Bawankule",
            "Gedam",
            "Tembhurne",
            "Raut",
            "Kohle",
            "Thakur",
            "Patil",
            "Deshmukh",
        ],
    ),

    # --------------------------------------------------------------------------
    # DISTRICT: NASHIK (Provisional Baseline - North Maharashtra)
    # --------------------------------------------------------------------------
    "NASHIK": DistrictProfile(
        district_id="NASHIK",
        district_name="Nashik",
        division="Nashik",
        region_type="Semi-Urban",
        source_reference="Census 2011 (Primary Census Abstract) & DTE Maharashtra Nashik Region Seat Matrix",
        reference_year="2011 / 2022-23",
        source_url="https://censusindia.gov.in and https://dtemaharashtra.gov.in",
        provenance_tier="provisional_baseline",
        available_statistics={
            "census_reference_year": "2011",
            "census_population_scope": "General population (all ages, residential census count)",
            "total_population_2011": 6107187,
            "urban_population_2011": 2598397,
            "rural_population_2011": 3508790,
            "urbanization_rate_2011": 0.4255,
            "general_sex_ratio_2011": 934,
            "scheduled_castes_population_2011": 555898,
            "scheduled_castes_share_2011": 0.0910,
            "scheduled_tribes_population_2011": 1564369,
            "scheduled_tribes_share_2011": 0.2562,
            "administrative_revenue_talukas_count": 15,
            "administrative_division": "Nashik",
        },
        missing_data=[
            "taluka_wise_student_enrolment",
            "district_level_household_income_microdata",
            "caste_breakdown_in_private_engineering",
            "direct_cap_vs_management_admission_microdata",
            "tribal_belt_hostel_and_commute_shares",
        ],
        assumptions_and_fallbacks={
            "region_type": (
                "Classified as 'Semi-Urban' under the quantitative classification rule (Census 2011 "
                "urban population share >= 25% and < 60%), with Nashik recording a 42.55% urban population "
                "share (2,598,397 urban residents out of 6,107,187 total population). The district encompasses "
                "the Nashik Municipal Corporation (NMC) and Malegaon Municipal Corporation alongside 13 "
                "extensive agrarian and tribal talukas. Classification strictly follows the empirical "
                "population benchmark rather than behavioral assumptions."
            ),
            "gender_distribution": (
                "Derived simulation prior (51.5% Male, 48.5% Female) reflecting general sex ratio (934) "
                "and regional collegiate enrolment benchmarks. It is not an observed student census."
            ),
            "caste_category_distribution": (
                "Derived simulation prior (30% General-EBC, 28% OBC, 10% SC, 20% ST, 7% VJNT, 5% General) "
                "representing an uncalibrated heuristic simulation assumption grounded in general population "
                "demographic baselines (Census 2011: 25.62% ST, 9.10% SC — high Western Ghats tribal concentration "
                "in Surgana, Peth, Kalwan, Trimbakeshwar). Statutory reservation percentages are not observed "
                "collegiate caste shares and do not constitute an empirical or validated conversion formula. "
                "Exact student-level caste microdata in unaided higher education institutions is unobserved."
            ),
            "admission_mode_distribution": (
                "Provisional modelling assumption: 80% CAP, 10% Institute-Level, 5% Management-Quota, "
                "5% General-Merit anchored in Maharashtra Act No. XXVIII of 2015. Limits of applicability: "
                "This is a provisional modelling assumption, not an observed admission survey."
            ),
            "institution_type_distribution": (
                "Derived simulation prior (10% Government, 30% Government-Aided, 55% Private-Unaided, "
                "5% Deemed/Private-University) based on DTE approved seat intake matrices and SPPU college "
                "directories in Nashik region. It is not an observed student census."
            ),
            "professional_stream_ratio": (
                "Derived simulation prior (32.0% / 0.320) reflecting Nashik's role as a major regional "
                "educational hub (MUHS, YCMOU, engineering and polytechnic campuses). District-level student "
                "enrolment by stream is unobserved as a single published statistic."
            ),
            "taluka_distribution": (
                "Derived simulation prior based on Higher Education Institution (HEI) geographic concentration "
                "in DTE and university directories (Nashik 42.0%, Malegaon 14.0%, Sinnar 8.0%, Niphad 6.0%, "
                "Satana 5.0%, Yeola 4.0%, Chandwad 4.0%, Igatpuri 3.0%, Dindori 3.0%, Trimbakeshwar 3.0%, "
                "Nandgaon 2.0%, Kalwan 2.0%, Deola 2.0%, Peth 1.0%, Surgana 1.0%). Note: The statutory revenue "
                "taluka of Baglan is referenced by its administrative headquarters 'Satana' to maintain generator "
                "key compatibility. Published DES and census tables do not provide taluka-wise collegiate "
                "student enrolment counts."
            ),
            "source_citation_limitation": (
                "Census 2011 figures are from published Primary Census Abstract tables. Portal URLs "
                "(censusindia.gov.in, dtemaharashtra.gov.in) represent root agency landing domains rather than "
                "direct document or download links. AISHE and DTE technical intake figures are derived from state "
                "reports and portal directories; exact district-level cross-tabulations are unindexed in print "
                "volumes and are not asserted as verified print citations."
            ),
        },
        talukas=[
            "Nashik",
            "Malegaon",
            "Sinnar",
            "Niphad",
            "Satana",
            "Yeola",
            "Chandwad",
            "Igatpuri",
            "Dindori",
            "Trimbakeshwar",
            "Nandgaon",
            "Kalwan",
            "Deola",
            "Peth",
            "Surgana",
        ],
        taluka_distribution={
            "Nashik": 0.420,
            "Malegaon": 0.140,
            "Sinnar": 0.080,
            "Niphad": 0.060,
            "Satana": 0.050,
            "Yeola": 0.040,
            "Chandwad": 0.040,
            "Igatpuri": 0.030,
            "Dindori": 0.030,
            "Trimbakeshwar": 0.030,
            "Nandgaon": 0.020,
            "Kalwan": 0.020,
            "Deola": 0.020,
            "Peth": 0.010,
            "Surgana": 0.010,
        },
        gender_distribution={"Male": 0.515, "Female": 0.485},
        institution_type_distribution={
            "Government": 0.10,
            "Government-Aided": 0.30,
            "Private-Unaided": 0.55,
            "Deemed/Private-University": 0.05,
        },
        admission_mode_distribution={
            "CAP": 0.80,
            "Institute-Level": 0.10,
            "Management-Quota": 0.05,
            "General-Merit": 0.05,
        },
        course_level_distribution={
            "Undergraduate": 0.75,
            "Postgraduate": 0.15,
            "Diploma": 0.10,
        },
        professional_stream_ratio=0.320,
        caste_category_distribution={
            "General-EBC": 0.30,
            "OBC": 0.28,
            "SC": 0.10,
            "ST": 0.20,
            "VJNT": 0.07,
            "General": 0.05,
        },
        last_names=[
            "Patil",
            "Deshmukh",
            "Wagh",
            "Shinde",
            "Pawar",
            "Borse",
            "Gangurde",
            "Kadam",
            "Gite",
            "Aher",
        ],
    ),

    # --------------------------------------------------------------------------
    # DISTRICT: SANGLI (Provisional Baseline - Southern Western Maharashtra)
    # --------------------------------------------------------------------------
    "SANGLI": DistrictProfile(
        district_id="SANGLI",
        district_name="Sangli",
        division="Pune",
        region_type="Semi-Urban",
        source_reference="Census 2011 (Primary Census Abstract) & DTE Maharashtra Pune Region Seat Matrix",
        reference_year="2011 / 2022-23",
        source_url="https://censusindia.gov.in and https://dtemaharashtra.gov.in",
        provenance_tier="provisional_baseline",
        available_statistics={
            "census_reference_year": "2011",
            "census_population_scope": "General population (all ages, residential census count)",
            "total_population_2011": 2822143,
            "urban_population_2011": 719595,
            "rural_population_2011": 2102548,
            "urbanization_rate_2011": 0.2550,
            "general_sex_ratio_2011": 966,
            "scheduled_castes_population_2011": 353248,
            "scheduled_castes_share_2011": 0.1252,
            "scheduled_tribes_population_2011": 18041,
            "scheduled_tribes_share_2011": 0.0064,
            "administrative_revenue_talukas_count": 10,
            "administrative_division": "Pune",
        },
        missing_data=[
            "taluka_wise_student_enrolment",
            "district_level_household_income_microdata",
            "caste_breakdown_in_private_engineering",
            "direct_cap_vs_management_admission_microdata",
            "cooperative_sugar_belt_income_variability",
        ],
        assumptions_and_fallbacks={
            "region_type": (
                "Classified as 'Semi-Urban' under the quantitative classification rule (Census 2011 "
                "urban population share >= 25% and < 60%), with Sangli recording a 25.50% urban population "
                "share (719,595 urban residents out of 2,822,143 total population). The district includes "
                "the Sangli-Miraj-Kupwad Municipal Corporation alongside 9 extensive rural/agrarian talukas. "
                "Classification strictly adheres to the quantitative population threshold rather than "
                "behavioral assumptions."
            ),
            "gender_distribution": (
                "Derived simulation prior (52.0% Male, 48.0% Female) reflecting Southern Western Maharashtra "
                "higher education gender benchmarks. It is not an observed student census."
            ),
            "caste_category_distribution": (
                "Derived simulation prior (36% General-EBC, 28% OBC, 15% SC, 2% ST, 9% VJNT, 10% General) "
                "representing an uncalibrated heuristic simulation assumption grounded in general population "
                "demographic baselines (Census 2011: 12.52% SC, 0.64% ST) and high agricultural cooperative "
                "EBC scholarship demand. Statutory reservation percentages are not observed collegiate caste "
                "shares and do not constitute an empirical or validated conversion formula. Student-level "
                "caste microdata in unaided higher education institutions is unobserved."
            ),
            "admission_mode_distribution": (
                "Provisional modelling assumption: 80% CAP, 10% Institute-Level, 5% Management-Quota, "
                "5% General-Merit anchored in Maharashtra Act No. XXVIII of 2015. Limits of applicability: "
                "This is a provisional modelling assumption, not an observed admission survey."
            ),
            "institution_type_distribution": (
                "Derived simulation prior (8% Government, 35% Government-Aided, 52% Private-Unaided, "
                "5% Deemed/Private-University) reflecting prestigious state-aided autonomous institutions "
                "(Walchand College of Engineering - WCE, Sangli) alongside private colleges (RIT Islampur). "
                "Note: WCE serves as a qualitative institutional reference point, not empirical evidence that "
                "35% of district-wide tertiary students attend aided institutions. It is a provisional prior, "
                "not an observed student census."
            ),
            "professional_stream_ratio": (
                "Derived simulation prior (33.0% / 0.330) reflecting strong technical college concentration "
                "in Miraj and Walwa. District-level student enrolment by stream is unobserved as a single "
                "published statistic."
            ),
            "taluka_distribution": (
                "Derived simulation prior based on Higher Education Institution (HEI) geographic concentration "
                "in Shivaji University and DTE directories (Miraj 44.0%, Walwa 24.0%, Tasgaon 6.0%, Palus 5.0%, "
                "Khanapur 5.0%, Kadegaon 4.0%, Shirala 4.0%, Kavathe Mahankal 3.0%, Jat 3.0%, Atpadi 2.0%). "
                "Published DES and census tables do not provide taluka-wise collegiate student enrolment counts."
            ),
            "source_citation_limitation": (
                "Census 2011 figures are from published Primary Census Abstract tables. Portal URLs "
                "(censusindia.gov.in, dtemaharashtra.gov.in) represent root agency landing domains rather than "
                "direct document or download links. AISHE and DTE technical intake figures are derived from state "
                "reports and portal directories; exact district-level cross-tabulations are unindexed in print "
                "volumes and are not asserted as verified print citations."
            ),
        },
        talukas=[
            "Miraj",
            "Walwa",
            "Tasgaon",
            "Khanapur",
            "Atpadi",
            "Jat",
            "Kadegaon",
            "Shirala",
            "Palus",
            "Kavathe Mahankal",
        ],
        taluka_distribution={
            "Miraj": 0.440,
            "Walwa": 0.240,
            "Tasgaon": 0.060,
            "Palus": 0.050,
            "Khanapur": 0.050,
            "Kadegaon": 0.040,
            "Shirala": 0.040,
            "Kavathe Mahankal": 0.030,
            "Jat": 0.030,
            "Atpadi": 0.020,
        },
        gender_distribution={"Male": 0.52, "Female": 0.48},
        institution_type_distribution={
            "Government": 0.08,
            "Government-Aided": 0.35,
            "Private-Unaided": 0.52,
            "Deemed/Private-University": 0.05,
        },
        admission_mode_distribution={
            "CAP": 0.80,
            "Institute-Level": 0.10,
            "Management-Quota": 0.05,
            "General-Merit": 0.05,
        },
        course_level_distribution={
            "Undergraduate": 0.75,
            "Postgraduate": 0.15,
            "Diploma": 0.10,
        },
        professional_stream_ratio=0.330,
        caste_category_distribution={
            "General-EBC": 0.36,
            "OBC": 0.28,
            "SC": 0.15,
            "ST": 0.02,
            "VJNT": 0.09,
            "General": 0.10,
        },
        last_names=[
            "Patil",
            "Kadam",
            "Yadav",
            "Shinde",
            "Deshmukh",
            "Chavan",
            "Mane",
            "Salunkhe",
            "Bhosale",
            "Kulkarni",
        ],
    ),

    # --------------------------------------------------------------------------
    # DISTRICT: MUMBAI SUBURBAN (Provisional Baseline - Konkan Division)
    # --------------------------------------------------------------------------
    "MUMBAI_SUBURBAN": DistrictProfile(
        district_id="MUMBAI_SUBURBAN",
        district_name="Mumbai Suburban",
        division="Konkan",
        region_type="Urban",
        source_reference="Census 2011 (Primary Census Abstract) & DTE Maharashtra Mumbai Region Seat Matrix",
        reference_year="2011 / 2022-23",
        source_url="https://censusindia.gov.in and https://dtemaharashtra.gov.in",
        provenance_tier="provisional_baseline",
        available_statistics={
            "census_reference_year": "2011",
            "census_population_scope": "General population (all ages, residential census count)",
            "total_population_2011": 9356962,
            "urban_population_2011": 9356962,
            "rural_population_2011": 0,
            "urbanization_rate_2011": 1.0000,
            "general_sex_ratio_2011": 860,
            "scheduled_castes_population_2011": 669824,
            "scheduled_castes_share_2011": 0.0716,
            "scheduled_tribes_population_2011": 332607,
            "scheduled_tribes_share_2011": 0.0355,
            "administrative_revenue_talukas_count": 3,
            "administrative_division": "Konkan",
        },
        missing_data=[
            "taluka_wise_student_enrolment",
            "district_level_household_income_microdata",
            "caste_breakdown_in_private_engineering",
            "direct_cap_vs_management_admission_microdata",
            "commuter_and_migrant_student_fractions",
        ],
        assumptions_and_fallbacks={
            "region_type": (
                "Classified as 'Urban' under the quantitative classification rule (Census 2011 "
                "urban population share >= 60%), with Mumbai Suburban recording a 100.0% urban population "
                "share (9,356,962 urban residents out of 9,356,962 total population). The district is a "
                "fully contiguous metropolitan area administered under the Municipal Corporation of Greater "
                "Mumbai (MCGM) across 3 statutory revenue talukas (Andheri, Kurla, Borivali) without rural "
                "revenue blocks. Classification strictly follows the empirical population benchmark rather "
                "than behavioral assumptions."
            ),
            "gender_distribution": (
                "Derived simulation prior (50.5% Male, 49.5% Female) reflecting high metropolitan gender "
                "parity in tertiary education (aligned with Mumbai City AISHE benchmarks), despite general "
                "population sex ratio (860) being depressed by historical male migrant labor influx. "
                "It is a provisional prior, not an observed student census."
            ),
            "caste_category_distribution": (
                "Derived simulation prior (35% General-EBC, 25% OBC, 12% SC, 4% ST, 6% VJNT, 18% General) "
                "representing an uncalibrated heuristic simulation assumption grounded in general population "
                "demographic baselines (Census 2011: 7.16% SC, 3.55% ST) and metropolitan composition. "
                "Statutory reservation percentages are not observed collegiate caste shares and do not "
                "constitute an empirical or validated conversion formula. Exact student-level caste microdata "
                "in unaided higher education institutions is unobserved."
            ),
            "admission_mode_distribution": (
                "Provisional modelling assumption: 80% CAP, 10% Institute-Level, 5% Management-Quota, "
                "5% General-Merit anchored in Maharashtra Act No. XXVIII of 2015. Limits of applicability: "
                "This is a provisional modelling assumption, not an observed admission survey."
            ),
            "institution_type_distribution": (
                "Derived simulation prior (8% Government, 27% Government-Aided, 55% Private-Unaided, "
                "10% Deemed/Private-University) reflecting heavy private unaided engineering, management, "
                "and pharmacy campus concentration in suburban educational hubs (Bandra, Andheri, Vile Parle, "
                "Chembur) alongside university institutes. It is not an observed student census."
            ),
            "professional_stream_ratio": (
                "Derived simulation prior (36.0% / 0.360) reflecting dense metropolitan concentration of "
                "technical, management, and pharmacy institutions affiliated with University of Mumbai. "
                "District-level student enrolment by stream is unobserved as a single published statistic."
            ),
            "taluka_distribution": (
                "Derived simulation prior based on Higher Education Institution (HEI) geographic concentration "
                "in University of Mumbai and DTE directories (Andheri 40.0%, Kurla 35.0%, Borivali 25.0%). "
                "Published DES and census tables do not provide taluka-wise collegiate student enrolment counts."
            ),
            "source_citation_limitation": (
                "Census 2011 figures are from published Primary Census Abstract tables. Portal URLs "
                "(censusindia.gov.in, dtemaharashtra.gov.in) represent root agency landing domains rather than "
                "direct document or download links. AISHE and DTE technical intake figures are derived from state "
                "reports and portal directories; exact district-level cross-tabulations are unindexed in print "
                "volumes and are not asserted as verified print citations."
            ),
        },
        talukas=[
            "Kurla",
            "Andheri",
            "Borivali",
        ],
        taluka_distribution={
            "Andheri": 0.400,
            "Kurla": 0.350,
            "Borivali": 0.250,
        },
        gender_distribution={"Male": 0.505, "Female": 0.495},
        institution_type_distribution={
            "Government": 0.08,
            "Government-Aided": 0.27,
            "Private-Unaided": 0.55,
            "Deemed/Private-University": 0.10,
        },
        admission_mode_distribution={
            "CAP": 0.80,
            "Institute-Level": 0.10,
            "Management-Quota": 0.05,
            "General-Merit": 0.05,
        },
        course_level_distribution={
            "Undergraduate": 0.75,
            "Postgraduate": 0.15,
            "Diploma": 0.10,
        },
        professional_stream_ratio=0.360,
        caste_category_distribution={
            "General-EBC": 0.35,
            "OBC": 0.25,
            "SC": 0.12,
            "ST": 0.04,
            "VJNT": 0.06,
            "General": 0.18,
        },
        last_names=[
            "Shah",
            "Patel",
            "Sawant",
            "Kadam",
            "Shinde",
            "Deshmukh",
            "Kamble",
            "More",
            "Jadhav",
            "Bhosale",
        ],
    ),

    # --------------------------------------------------------------------------
    # DISTRICT: NANDED (Provisional Baseline - Marathwada Division)
    # --------------------------------------------------------------------------
    "NANDED": DistrictProfile(
        district_id="NANDED",
        district_name="Nanded",
        division="Chhatrapati Sambhajinagar",
        region_type="Semi-Urban",
        source_reference="Census 2011 (Primary Census Abstract) & DTE Maharashtra Chhatrapati Sambhajinagar Region Seat Matrix",
        reference_year="2011 / 2022-23",
        source_url="https://censusindia.gov.in and https://dtemaharashtra.gov.in",
        provenance_tier="provisional_baseline",
        available_statistics={
            "census_reference_year": "2011",
            "census_population_scope": "General population (all ages, residential census count)",
            "total_population_2011": 3361292,
            "urban_population_2011": 913715,
            "rural_population_2011": 2447577,
            "urbanization_rate_2011": 0.2718,
            "general_sex_ratio_2011": 937,
            "scheduled_castes_population_2011": 641310,
            "scheduled_castes_share_2011": 0.1908,
            "scheduled_tribes_population_2011": 284041,
            "scheduled_tribes_share_2011": 0.0845,
            "administrative_revenue_talukas_count": 16,
            "administrative_division": "Chhatrapati Sambhajinagar",
        },
        missing_data=[
            "taluka_wise_student_enrolment",
            "district_level_household_income_microdata",
            "caste_breakdown_in_private_engineering",
            "direct_cap_vs_management_admission_microdata",
            "out_of_district_student_migration_and_hostel_shares",
        ],
        assumptions_and_fallbacks={
            "region_type": (
                "Classified as 'Semi-Urban' under the quantitative classification rule (Census 2011 "
                "urban population share >= 25% and < 60%), with Nanded recording a 27.18% urban population "
                "share (913,715 urban residents out of 3,361,292 total population). The district encompasses "
                "the Nanded-Waghala City Municipal Corporation and headquarters of SRTMUN alongside 15 "
                "extensive agrarian and border talukas. Classification strictly follows the empirical "
                "population benchmark rather than behavioral assumptions."
            ),
            "gender_distribution": (
                "Derived simulation prior (52.0% Male, 48.0% Female) reflecting Marathwada regional collegiate "
                "gender benchmarks. It is not an observed student census."
            ),
            "caste_category_distribution": (
                "Derived simulation prior (30% General-EBC, 24% OBC, 22% SC, 9% ST, 8% VJNT, 7% General) "
                "representing an uncalibrated heuristic simulation assumption grounded in general population "
                "demographic baselines (Census 2011: 19.08% SC, 8.45% ST — notable SC concentration across "
                "the district and ST concentration in Kinwat/Mahur border belt) and agrarian Marathwada demand. "
                "Statutory reservation percentages are not observed collegiate caste shares and do not "
                "constitute an empirical or validated conversion formula. Exact student-level caste microdata "
                "in unaided higher education institutions is unobserved."
            ),
            "admission_mode_distribution": (
                "Provisional modelling assumption: 80% CAP, 10% Institute-Level, 5% Management-Quota, "
                "5% General-Merit anchored in Maharashtra Act No. XXVIII of 2015. Limits of applicability: "
                "This is a provisional modelling assumption, not an observed admission survey."
            ),
            "institution_type_distribution": (
                "Derived simulation prior (12% Government, 36% Government-Aided, 48% Private-Unaided, "
                "4% Deemed/Private-University) reflecting prestigious state-aided autonomous technical "
                "institutions (Shri Guru Gobind Singhji Institute of Engineering and Technology - SGGSIE&T, Nanded) "
                "and Dr. Shankarrao Chavan Government Medical College alongside private colleges. Note: SGGSIE&T "
                "serves as an illustrative qualitative reference point, not empirical evidence that 36% of "
                "district-wide tertiary students attend aided institutions. It is a provisional prior, "
                "not an observed student census."
            ),
            "professional_stream_ratio": (
                "Derived simulation prior (24.0% / 0.240) reflecting Nanded's role as the educational headquarters "
                "of southern Marathwada (SRTMUN, SGGSIE&T, medical and pharmacy campuses) alongside rural "
                "general arts/science/commerce colleges. District-level student enrolment by stream is "
                "unobserved as a single published statistic."
            ),
            "taluka_distribution": (
                "Derived simulation prior based on Higher Education Institution (HEI) geographic concentration "
                "in SRTMUN and DTE directories (Nanded 40.0%, Deglur 6.0%, Mudkhed 5.0%, Kandhar 5.0%, "
                "Loha 5.0%, Kinwat 5.0%, Hadgaon 5.0%, Mukhed 5.0%, Biloli 4.0%, Bhokar 4.0%, Dharmabad 4.0%, "
                "Ardhapur 3.0%, Naigaon 3.0%, Umri 3.0%, Himayatnagar 2.0%, Mahur 1.0%). Note: The statutory "
                "revenue taluka of Naigaon is officially styled Naigaon (Khairgaon). Published DES and census "
                "tables do not provide taluka-wise collegiate student enrolment counts."
            ),
            "source_citation_limitation": (
                "Census 2011 figures are from published Primary Census Abstract tables. Portal URLs "
                "(censusindia.gov.in, dtemaharashtra.gov.in) represent root agency landing domains rather than "
                "direct document or download links. AISHE and DTE technical intake figures are derived from state "
                "reports and portal directories; exact district-level cross-tabulations are unindexed in print "
                "volumes and are not asserted as verified print citations."
            ),
        },
        talukas=[
            "Nanded",
            "Ardhapur",
            "Mudkhed",
            "Bhokar",
            "Loha",
            "Kandhar",
            "Kinwat",
            "Himayatnagar",
            "Hadgaon",
            "Mahur",
            "Biloli",
            "Deglur",
            "Mukhed",
            "Dharmabad",
            "Umri",
            "Naigaon",
        ],
        taluka_distribution={
            "Nanded": 0.400,
            "Deglur": 0.060,
            "Mudkhed": 0.050,
            "Kandhar": 0.050,
            "Loha": 0.050,
            "Kinwat": 0.050,
            "Hadgaon": 0.050,
            "Mukhed": 0.050,
            "Biloli": 0.040,
            "Bhokar": 0.040,
            "Dharmabad": 0.040,
            "Ardhapur": 0.030,
            "Naigaon": 0.030,
            "Umri": 0.030,
            "Himayatnagar": 0.020,
            "Mahur": 0.010,
        },
        gender_distribution={"Male": 0.52, "Female": 0.48},
        institution_type_distribution={
            "Government": 0.12,
            "Government-Aided": 0.36,
            "Private-Unaided": 0.48,
            "Deemed/Private-University": 0.04,
        },
        admission_mode_distribution={
            "CAP": 0.80,
            "Institute-Level": 0.10,
            "Management-Quota": 0.05,
            "General-Merit": 0.05,
        },
        course_level_distribution={
            "Undergraduate": 0.75,
            "Postgraduate": 0.15,
            "Diploma": 0.10,
        },
        professional_stream_ratio=0.240,
        caste_category_distribution={
            "General-EBC": 0.30,
            "OBC": 0.24,
            "SC": 0.22,
            "ST": 0.09,
            "VJNT": 0.08,
            "General": 0.07,
        },
        last_names=[
            "Kadam",
            "Shinde",
            "Jadhav",
            "Pawar",
            "Deshmukh",
            "Chavan",
            "Gaekwad",
            "Hambarde",
            "Khatgaonkar",
            "Waghmare",
        ],
    ),

    # --------------------------------------------------------------------------
    # DISTRICT: NANDURBAR (Provisional Baseline - North Maharashtra Tribal Belt)
    # --------------------------------------------------------------------------
    "NANDURBAR": DistrictProfile(
        district_id="NANDURBAR",
        district_name="Nandurbar",
        division="Nashik",
        region_type="Rural",
        source_reference="Census 2011 (Primary Census Abstract) & DTE Maharashtra Nashik Region Seat Matrix",
        reference_year="2011 / 2022-23",
        source_url="https://censusindia.gov.in and https://dtemaharashtra.gov.in",
        provenance_tier="provisional_baseline",
        available_statistics={
            "census_reference_year": "2011",
            "census_population_scope": "General population (all ages, residential census count)",
            "total_population_2011": 1648295,
            "urban_population_2011": 275548,
            "rural_population_2011": 1372747,
            "urbanization_rate_2011": 0.1672,
            "general_sex_ratio_2011": 978,
            "scheduled_castes_population_2011": 78879,
            "scheduled_castes_share_2011": 0.0479,
            "scheduled_tribes_population_2011": 1141933,
            "scheduled_tribes_share_2011": 0.6928,
            "administrative_revenue_talukas_count": 6,
            "administrative_division": "Nashik",
        },
        missing_data=[
            "taluka_wise_student_enrolment",
            "district_level_household_income_microdata",
            "caste_breakdown_in_private_engineering",
            "direct_cap_vs_management_admission_microdata",
            "tribal_ashram_collegiate_transition_rates",
            "hostel_residence_and_remote_taluka_commute_shares",
        ],
        assumptions_and_fallbacks={
            "region_type": (
                "Classified as 'Rural' under the quantitative classification rule (Census 2011 "
                "urban population share < 25%), with Nandurbar recording a 16.72% urban population "
                "share (275,548 urban residents out of 1,648,295 total population). Nandurbar is "
                "Maharashtra's premier tribal district (69.28% ST population) with 5 of 6 talukas "
                "predominantly forested, Satpura hill terrain, and agrarian. Classification strictly "
                "follows the empirical population benchmark rather than behavioral assumptions."
            ),
            "gender_distribution": (
                "Derived simulation prior (52.0% Male, 48.0% Female) reflecting North Maharashtra tribal "
                "collegiate gender benchmarks. While general population sex ratio is high (978), higher "
                "education transition among female students experiences geographic and economic frictions. "
                "It is not an observed student census."
            ),
            "caste_category_distribution": (
                "Derived simulation prior (14% General-EBC, 18% OBC, 6% SC, 54% ST, 4% VJNT, 4% General) "
                "representing an uncalibrated heuristic simulation assumption grounded in general population "
                "demographic baselines (Census 2011: 69.28% ST, 4.79% SC — predominant Bhil, Pawara, Kokna "
                "communities across Satpura range) and collegiate transition constraints. Statutory reservation "
                "percentages are not observed collegiate caste shares and do not constitute an empirical "
                "or validated conversion formula. Exact student-level caste microdata in unaided higher "
                "education institutions is unobserved."
            ),
            "admission_mode_distribution": (
                "Provisional modelling assumption: 80% CAP, 10% Institute-Level, 5% Management-Quota, "
                "5% General-Merit anchored in Maharashtra Act No. XXVIII of 2015. Limits of applicability: "
                "This is a provisional modelling assumption, not an observed admission survey."
            ),
            "institution_type_distribution": (
                "Derived simulation prior (20% Government, 42% Government-Aided, 35% Private-Unaided, "
                "3% Deemed/Private-University) representing an uncalibrated provisional simulation assumption, "
                "not an empirically measured district-wide tertiary enrolment share. Government Ashram Schools "
                "and residential junior colleges operate at the school level as feeder pipelines into higher "
                "education rather than collegiate or tertiary facilities; neither general university affiliations "
                "nor individual grant-in-aid colleges validate the 42% aided share. It is not an observed student census."
            ),
            "professional_stream_ratio": (
                "Derived simulation prior (18.0% / 0.180) reflecting modest technical collegiate infrastructure "
                "(engineering and pharmacy campuses concentrated in Shahada and Nandurbar) relative to general "
                "arts, commerce, and science degree colleges. District-level student enrolment by stream is "
                "unobserved as a single published statistic."
            ),
            "taluka_distribution": (
                "Derived simulation prior based on Higher Education Institution (HEI) geographic concentration "
                "in KBCNMU and DTE directories (Nandurbar 42.0%, Shahada 28.0%, Navapur 12.0%, Taloda 8.0%, "
                "Akkalkuwa 6.0%, Akrani 4.0%). Note: The statutory revenue taluka of Akrani is also commonly "
                "referenced as Dhadgaon. Published DES and census tables do not provide taluka-wise collegiate "
                "student enrolment counts."
            ),
            "source_citation_limitation": (
                "Census 2011 figures are from published Primary Census Abstract tables. Portal URLs "
                "(censusindia.gov.in, dtemaharashtra.gov.in) represent root agency landing domains rather than "
                "direct document or download links. AISHE and DTE technical intake figures are derived from state "
                "reports and portal directories; exact district-level cross-tabulations are unindexed in print "
                "volumes and are not asserted as verified print citations."
            ),
        },
        talukas=[
            "Nandurbar",
            "Shahada",
            "Navapur",
            "Taloda",
            "Akkalkuwa",
            "Akrani",
        ],
        taluka_distribution={
            "Nandurbar": 0.420,
            "Shahada": 0.280,
            "Navapur": 0.120,
            "Taloda": 0.080,
            "Akkalkuwa": 0.060,
            "Akrani": 0.040,
        },
        gender_distribution={"Male": 0.52, "Female": 0.48},
        institution_type_distribution={
            "Government": 0.20,
            "Government-Aided": 0.42,
            "Private-Unaided": 0.35,
            "Deemed/Private-University": 0.03,
        },
        admission_mode_distribution={
            "CAP": 0.80,
            "Institute-Level": 0.10,
            "Management-Quota": 0.05,
            "General-Merit": 0.05,
        },
        course_level_distribution={
            "Undergraduate": 0.75,
            "Postgraduate": 0.15,
            "Diploma": 0.10,
        },
        professional_stream_ratio=0.180,
        caste_category_distribution={
            "General-EBC": 0.14,
            "OBC": 0.18,
            "SC": 0.06,
            "ST": 0.54,
            "VJNT": 0.04,
            "General": 0.04,
        },
        last_names=[
            "Padvi",
            "Naik",
            "Gavit",
            "Valvi",
            "Pawara",
            "Bhil",
            "Patil",
            "Chaudhari",
            "Shinde",
            "Vasave",
        ],
    ),

    # --------------------------------------------------------------------------
    # DISTRICT: PALGHAR (Provisional Baseline - Konkan Division / Reconstructed Post-Bifurcation)
    # --------------------------------------------------------------------------
    "PALGHAR": DistrictProfile(
        district_id="PALGHAR",
        district_name="Palghar",
        division="Konkan",
        region_type="Semi-Urban",
        source_reference="Census 2011 Reconstructed from Thane Taluka Tables & DTE Maharashtra Mumbai Region Seat Matrix",
        reference_year="2011 / 2022-23",
        source_url="https://censusindia.gov.in and https://dtemaharashtra.gov.in",
        provenance_tier="provisional_baseline",
        available_statistics={
            "census_reference_year": "2011",
            "census_population_scope": "Reconstructed post-bifurcation population from 2011 taluka-level Census PCA (8 constituent talukas of undivided Thane)",
            "reconstructed_total_population_2011": 2990116,
            "reconstructed_urban_population_2011": 1435210,
            "reconstructed_rural_population_2011": 1554906,
            "reconstructed_urbanization_rate_2011": 0.4800,
            "reconstructed_general_sex_ratio_2011": 921,
            "reconstructed_scheduled_castes_population_2011": 86763,
            "reconstructed_scheduled_castes_share_2011": 0.0290,
            "reconstructed_scheduled_tribes_population_2011": 1118529,
            "reconstructed_scheduled_tribes_share_2011": 0.3741,
            "administrative_revenue_talukas_count": 8,
            "administrative_division": "Konkan",
            "bifurcation_date": "2014-08-01",
            "bifurcated_from": "Thane",
            "methodological_note": (
                "Palghar district was formed on August 1, 2014 by bifurcating Thane district. "
                "2011 figures are reconstructed by aggregating the 8 talukas (Palghar, Vasai, Dahanu, "
                "Talasari, Jawhar, Mokhada, Vada, Vikramgad) from the District Census Handbook: Thane (2011). "
                "Figures are not published Census district-level totals."
            ),
        },
        missing_data=[
            "taluka_wise_student_enrolment",
            "district_level_household_income_microdata",
            "caste_breakdown_in_private_engineering",
            "direct_cap_vs_management_admission_microdata",
            "pre_2014_standalone_district_administrative_series",
            "coastal_urban_vs_eastern_tribal_collegiate_migration_rates",
        ],
        assumptions_and_fallbacks={
            "region_type": (
                "Classified as 'Semi-Urban' under the quantitative classification rule (Census 2011 "
                "reconstructed urban population share >= 25% and < 60%), with Palghar recording an estimated "
                "48.00% urban population share (1,435,210 urban residents out of 2,990,116 reconstructed total). "
                "The district exhibits internal duality: high urbanization and collegiate density along the "
                "coastal railway corridor (Vasai-Virar Municipal Corporation and Palghar/Boisar) contrasting "
                "with 5 extensive rural and tribal talukas in the eastern hinterland (Jawhar, Mokhada, Talasari, "
                "Vikramgad, Vada). Classification strictly follows the empirical population benchmark rather "
                "than behavioral assumptions."
            ),
            "gender_distribution": (
                "Derived simulation prior (51.5% Male, 48.5% Female) reflecting a blend of coastal metropolitan "
                "parity and eastern tribal collegiate participation. It is not an observed student census."
            ),
            "caste_category_distribution": (
                "Derived simulation prior (28% General-EBC, 24% OBC, 5% SC, 26% ST, 5% VJNT, 12% General) "
                "representing an uncalibrated heuristic simulation assumption grounded in reconstructed general "
                "population demographic baselines (Census 2011 reconstructed: 37.41% ST, 2.90% SC — high tribal "
                "concentration in Jawhar, Mokhada, Talasari alongside coastal non-tribal population in Vasai). "
                "Statutory reservation percentages are not observed collegiate caste shares and do not constitute "
                "an empirical or validated conversion formula. Exact student-level caste microdata in unaided "
                "higher education institutions is unobserved."
            ),
            "admission_mode_distribution": (
                "Provisional modelling assumption: 80% CAP, 10% Institute-Level, 5% Management-Quota, "
                "5% General-Merit anchored in Maharashtra Act No. XXVIII of 2015. Limits of applicability: "
                "This is a provisional modelling assumption, not an observed admission survey."
            ),
            "institution_type_distribution": (
                "Derived simulation prior (8% Government, 32% Government-Aided, 55% Private-Unaided, "
                "5% Deemed/Private-University) reflecting private engineering, pharmacy, and degree colleges "
                "in Vasai, Palghar, and Boisar alongside aided degree colleges affiliated with University of Mumbai. "
                "It is not an observed student census."
            ),
            "professional_stream_ratio": (
                "Derived simulation prior (26.0% / 0.260) reflecting technical institutions in the Vasai-Virar "
                "and Palghar-Boisar belts relative to general collegiate enrolment. District-level student "
                "enrolment by stream is unobserved as a single published statistic."
            ),
            "taluka_distribution": (
                "Derived simulation prior based on Higher Education Institution (HEI) geographic concentration "
                "in University of Mumbai and DTE directories (Vasai 50.0%, Palghar 22.0%, Dahanu 9.0%, "
                "Vada 6.0%, Vikramgad 4.0%, Jawhar 4.0%, Talasari 3.0%, Mokhada 2.0%). Published DES and census "
                "tables do not provide taluka-wise collegiate student enrolment counts."
            ),
            "source_citation_limitation": (
                "Census 2011 figures for Palghar are reconstructed from sub-district (taluka-level) tables of "
                "the undivided Thane District Census Handbook (2011). Post-bifurcation official standalone Census 2011 "
                "totals do not exist. Portal URLs (censusindia.gov.in, dtemaharashtra.gov.in) represent root agency "
                "landing domains rather than direct document or download links. AISHE and DTE technical intake figures "
                "are derived from state reports and portal directories; exact district-level cross-tabulations are "
                "unindexed in print volumes and are not asserted as verified print citations."
            ),
        },
        talukas=[
            "Palghar",
            "Vasai",
            "Dahanu",
            "Talasari",
            "Jawhar",
            "Mokhada",
            "Vada",
            "Vikramgad",
        ],
        taluka_distribution={
            "Vasai": 0.500,
            "Palghar": 0.220,
            "Dahanu": 0.090,
            "Vada": 0.060,
            "Vikramgad": 0.040,
            "Jawhar": 0.040,
            "Talasari": 0.030,
            "Mokhada": 0.020,
        },
        gender_distribution={"Male": 0.515, "Female": 0.485},
        institution_type_distribution={
            "Government": 0.08,
            "Government-Aided": 0.32,
            "Private-Unaided": 0.55,
            "Deemed/Private-University": 0.05,
        },
        admission_mode_distribution={
            "CAP": 0.80,
            "Institute-Level": 0.10,
            "Management-Quota": 0.05,
            "General-Merit": 0.05,
        },
        course_level_distribution={
            "Undergraduate": 0.75,
            "Postgraduate": 0.15,
            "Diploma": 0.10,
        },
        professional_stream_ratio=0.260,
        caste_category_distribution={
            "General-EBC": 0.28,
            "OBC": 0.24,
            "SC": 0.05,
            "ST": 0.26,
            "VJNT": 0.05,
            "General": 0.12,
        },
        last_names=[
            "Patil",
            "Thakur",
            "Gavit",
            "Vartha",
            "Baraf",
            "Kadam",
            "Save",
            "Pereira",
            "Deshmukh",
            "Chaudhari",
        ],
    ),

    # --------------------------------------------------------------------------
    # DISTRICT: PARBHANI (Provisional Baseline - Chhatrapati Sambhajinagar Division)
    # --------------------------------------------------------------------------
    "PARBHANI": DistrictProfile(
        district_id="PARBHANI",
        district_name="Parbhani",
        division="Chhatrapati Sambhajinagar",
        region_type="Semi-Urban",
        source_reference="Census 2011 (Primary Census Abstract) & DTE Maharashtra Chhatrapati Sambhajinagar Region Seat Matrix",
        reference_year="2011 / 2022-23",
        source_url="https://censusindia.gov.in and https://dtemaharashtra.gov.in",
        provenance_tier="provisional_baseline",
        available_statistics={
            "census_reference_year": "2011",
            "census_population_scope": "General population (all ages, residential census count)",
            "total_population_2011": 1836086,
            "urban_population_2011": 569824,
            "rural_population_2011": 1266262,
            "urbanization_rate_2011": 0.3103,
            "general_sex_ratio_2011": 947,
            "scheduled_castes_population_2011": 258217,
            "scheduled_castes_share_2011": 0.1406,
            "scheduled_tribes_population_2011": 40793,
            "scheduled_tribes_share_2011": 0.0222,
            "administrative_revenue_talukas_count": 9,
            "administrative_division": "Chhatrapati Sambhajinagar",
        },
        missing_data=[
            "taluka_wise_student_enrolment",
            "district_level_household_income_microdata",
            "caste_breakdown_in_private_engineering",
            "direct_cap_vs_management_admission_microdata",
            "agrarian_household_seasonal_income_variability",
            "hostel_residence_and_inter_district_collegiate_migration",
        ],
        assumptions_and_fallbacks={
            "region_type": (
                "Classified as 'Semi-Urban' under the quantitative classification rule (Census 2011 "
                "urban population share >= 25% and < 60%), with Parbhani recording a 31.03% urban "
                "population share (569,824 urban residents out of 1,836,086 total population). "
                "The district combines an urbanized commercial/educational core in Parbhani city with "
                "8 extensive agrarian Marathwada talukas. Classification strictly follows the empirical "
                "population benchmark rather than behavioral assumptions."
            ),
            "gender_distribution": (
                "Derived simulation prior (52.0% Male, 48.0% Female) reflecting Marathwada regional "
                "higher education gender transition benchmarks. While the general sex ratio is 947, female "
                "transition to collegiate education experiences rural transport and socioeconomic frictions. "
                "It is not an observed student census."
            ),
            "caste_category_distribution": (
                "Derived simulation prior (32% General-EBC, 28% OBC, 18% SC, 3% ST, 11% VJNT, 8% General) "
                "representing an uncalibrated heuristic simulation assumption grounded in general population "
                "demographic baselines (Census 2011: 14.06% SC, 2.22% ST) and agricultural Marathwada EBC "
                "scholarship demand. Statutory reservation percentages are not observed collegiate caste "
                "shares and do not constitute an empirical or validated conversion formula. Exact student-level "
                "caste microdata in unaided higher education institutions is unobserved."
            ),
            "admission_mode_distribution": (
                "Provisional modelling assumption: 80% CAP, 10% Institute-Level, 5% Management-Quota, "
                "5% General-Merit anchored in Maharashtra Act No. XXVIII of 2015. Limits of applicability: "
                "This is a provisional modelling assumption, not an observed admission survey."
            ),
            "institution_type_distribution": (
                "Derived simulation prior (10% Government, 35% Government-Aided, 52% Private-Unaided, "
                "3% Deemed/Private-University) reflecting state-aided degree colleges affiliated with SRTMUN "
                "alongside private professional engineering and pharmacy institutes and VNMKV agricultural "
                "presence. Note: VNMKV and SRTMUN-affiliated colleges serve as illustrative qualitative reference "
                "points, not empirical evidence that 35% of district-wide tertiary students attend aided institutions; "
                "this remains a provisional simulation prior. It is not an observed student census."
            ),
            "professional_stream_ratio": (
                "Derived simulation prior (22.0% / 0.220) reflecting regional agricultural and conventional "
                "arts, commerce, and science collegiate concentration relative to professional engineering "
                "and technology institutes. District-level student enrolment by stream is unobserved as a "
                "single published statistic."
            ),
            "taluka_distribution": (
                "Derived simulation prior based on Higher Education Institution (HEI) geographic concentration "
                "in SRTMUN and DTE directories (Parbhani 44.0%, Gangakhed 12.0%, Selu 10.0%, Jintur 8.0%, "
                "Purna 7.0%, Manwath 6.0%, Pathri 5.0%, Sonpeth 4.0%, Palam 4.0%). Published DES and census "
                "tables do not provide taluka-wise collegiate student enrolment counts."
            ),
            "source_citation_limitation": (
                "Census 2011 figures are from published Primary Census Abstract tables. Portal URLs "
                "(censusindia.gov.in, dtemaharashtra.gov.in) represent root agency landing domains rather "
                "than direct document or download links. AISHE and DTE technical intake figures are derived "
                "from state reports and portal directories; exact district-level cross-tabulations are "
                "unindexed in print volumes and are not asserted as verified print citations."
            ),
        },
        talukas=[
            "Parbhani",
            "Gangakhed",
            "Sonpeth",
            "Pathri",
            "Manwath",
            "Palam",
            "Selu",
            "Jintur",
            "Purna",
        ],
        taluka_distribution={
            "Parbhani": 0.440,
            "Gangakhed": 0.120,
            "Selu": 0.100,
            "Jintur": 0.080,
            "Purna": 0.070,
            "Manwath": 0.060,
            "Pathri": 0.050,
            "Sonpeth": 0.040,
            "Palam": 0.040,
        },
        gender_distribution={"Male": 0.52, "Female": 0.48},
        institution_type_distribution={
            "Government": 0.10,
            "Government-Aided": 0.35,
            "Private-Unaided": 0.52,
            "Deemed/Private-University": 0.03,
        },
        admission_mode_distribution={
            "CAP": 0.80,
            "Institute-Level": 0.10,
            "Management-Quota": 0.05,
            "General-Merit": 0.05,
        },
        course_level_distribution={
            "Undergraduate": 0.75,
            "Postgraduate": 0.15,
            "Diploma": 0.10,
        },
        professional_stream_ratio=0.220,
        caste_category_distribution={
            "General-EBC": 0.32,
            "OBC": 0.28,
            "SC": 0.18,
            "ST": 0.03,
            "VJNT": 0.11,
            "General": 0.08,
        },
        last_names=[
            "Deshmukh",
            "Patil",
            "Kadam",
            "Shinde",
            "Jadhav",
            "Gaikwad",
            "Pawar",
            "Chavan",
            "Kale",
            "Syed",
        ],
    ),

    # --------------------------------------------------------------------------
    # DISTRICT: RAIGAD (Provisional Baseline - Konkan Division)
    # --------------------------------------------------------------------------
    "RAIGAD": DistrictProfile(
        district_id="RAIGAD",
        district_name="Raigad",
        division="Konkan",
        region_type="Semi-Urban",
        source_reference="Census 2011 (Primary Census Abstract) & DTE Maharashtra Mumbai/Konkan Region Seat Matrix",
        reference_year="2011 / 2022-23",
        source_url="https://censusindia.gov.in and https://dtemaharashtra.gov.in",
        provenance_tier="provisional_baseline",
        available_statistics={
            "census_reference_year": "2011",
            "census_population_scope": "General population (all ages, residential census count)",
            "total_population_2011": 2634200,
            "urban_population_2011": 970142,
            "rural_population_2011": 1664058,
            "urbanization_rate_2011": 0.3683,
            "general_sex_ratio_2011": 959,
            "scheduled_castes_population_2011": 72709,
            "scheduled_castes_share_2011": 0.0276,
            "scheduled_tribes_population_2011": 305291,
            "scheduled_tribes_share_2011": 0.1159,
            "administrative_revenue_talukas_count": 15,
            "administrative_division": "Konkan",
        },
        missing_data=[
            "taluka_wise_student_enrolment",
            "district_level_household_income_microdata",
            "caste_breakdown_in_private_engineering",
            "direct_cap_vs_management_admission_microdata",
            "mumbai_metropolitan_commuter_student_fraction",
            "katkari_tribal_higher_ed_transition_microdata",
        ],
        assumptions_and_fallbacks={
            "region_type": (
                "Classified as 'Semi-Urban' under the quantitative classification rule (Census 2011 "
                "urban population share >= 25% and < 60%), with Raigad recording a 36.83% urban "
                "population share (970,142 urban residents out of 2,634,200 total population). "
                "The district features a rapidly urbanizing northern metropolitan corridor (Panvel, Uran, "
                "Karjat) alongside 12 coastal and Sahyadri foothill talukas with significant rural and "
                "tribal populations. Classification strictly follows the empirical population benchmark "
                "rather than behavioral assumptions."
            ),
            "gender_distribution": (
                "Derived simulation prior (51.0% Male, 49.0% Female) reflecting Mumbai metropolitan region "
                "educational access parity in northern talukas counterbalanced by rural southern taluka "
                "transition dynamics. It is not an observed student census."
            ),
            "caste_category_distribution": (
                "Derived simulation prior (34% General-EBC, 26% OBC, 6% SC, 12% ST, 8% VJNT, 14% General) "
                "representing an uncalibrated heuristic simulation assumption grounded in general population "
                "demographic baselines (Census 2011: 11.59% ST, 2.76% SC — notable Katkari and Thakar tribal "
                "populations in Karjat, Khalapur, Sudhagad, and coastal Agri/Koli OBC communities). "
                "Statutory reservation percentages are not observed collegiate caste shares and do not "
                "constitute an empirical or validated conversion formula. Exact student-level caste microdata "
                "in unaided higher education institutions is unobserved."
            ),
            "admission_mode_distribution": (
                "Provisional modelling assumption: 80% CAP, 10% Institute-Level, 5% Management-Quota, "
                "5% General-Merit anchored in Maharashtra Act No. XXVIII of 2015. Limits of applicability: "
                "This is a provisional modelling assumption, not an observed admission survey."
            ),
            "institution_type_distribution": (
                "Derived simulation prior (8% Government, 32% Government-Aided, 55% Private-Unaided, "
                "5% Deemed/Private-University) reflecting private engineering, architecture, and pharmacy "
                "campuses in the Panvel-Karjat cluster alongside University of Mumbai and DBATU Lonere "
                "affiliated colleges. Note: DBATU Lonere and affiliated regional colleges serve as illustrative "
                "qualitative reference points, not empirical evidence that 32% of district-wide tertiary students "
                "attend aided institutions; this remains a provisional simulation prior. It is not an observed student census."
            ),
            "professional_stream_ratio": (
                "Derived simulation prior (30.0% / 0.300) reflecting high density of technical, engineering, "
                "and management institutions in Panvel, Karjat, and Lonere catering to both local and MMR "
                "commuter students. District-level student enrolment by stream is unobserved as a single "
                "published statistic."
            ),
            "taluka_distribution": (
                "Derived simulation prior based on Higher Education Institution (HEI) geographic concentration "
                "in University of Mumbai, DBATU, and DTE directories (Panvel 37.0%, Alibag 14.0%, Karjat 8.0%, "
                "Mahad 7.0%, Pen 6.0%, Khalapur 5.0%, Roha 5.0%, Mangaon 4.0%, Uran 4.0%, Shrivardhan 3.0%, "
                "Murud 2.0%, Sudhagad 2.0%, Tala 1.0%, Mhasla 1.0%, Poladpur 1.0%). Published DES and census "
                "tables do not provide taluka-wise collegiate student enrolment counts."
            ),
            "source_citation_limitation": (
                "Census 2011 figures are from published Primary Census Abstract tables. Portal URLs "
                "(censusindia.gov.in, dtemaharashtra.gov.in) represent root agency landing domains rather "
                "than direct document or download links. AISHE and DTE technical intake figures are derived "
                "from state reports and portal directories; exact district-level cross-tabulations are "
                "unindexed in print volumes and are not asserted as verified print citations."
            ),
        },
        talukas=[
            "Alibag",
            "Panvel",
            "Uran",
            "Karjat",
            "Khalapur",
            "Pen",
            "Sudhagad",
            "Roha",
            "Mangaon",
            "Tala",
            "Mahad",
            "Poladpur",
            "Shrivardhan",
            "Mhasla",
            "Murud",
        ],
        taluka_distribution={
            "Panvel": 0.370,
            "Alibag": 0.140,
            "Karjat": 0.080,
            "Mahad": 0.070,
            "Pen": 0.060,
            "Khalapur": 0.050,
            "Roha": 0.050,
            "Mangaon": 0.040,
            "Uran": 0.040,
            "Shrivardhan": 0.030,
            "Murud": 0.020,
            "Sudhagad": 0.020,
            "Tala": 0.010,
            "Mhasla": 0.010,
            "Poladpur": 0.010,
        },
        gender_distribution={"Male": 0.51, "Female": 0.49},
        institution_type_distribution={
            "Government": 0.08,
            "Government-Aided": 0.32,
            "Private-Unaided": 0.55,
            "Deemed/Private-University": 0.05,
        },
        admission_mode_distribution={
            "CAP": 0.80,
            "Institute-Level": 0.10,
            "Management-Quota": 0.05,
            "General-Merit": 0.05,
        },
        course_level_distribution={
            "Undergraduate": 0.75,
            "Postgraduate": 0.15,
            "Diploma": 0.10,
        },
        professional_stream_ratio=0.300,
        caste_category_distribution={
            "General-EBC": 0.34,
            "OBC": 0.26,
            "SC": 0.06,
            "ST": 0.12,
            "VJNT": 0.08,
            "General": 0.14,
        },
        last_names=[
            "Patil",
            "Mhatre",
            "Thakur",
            "Gharat",
            "Gawand",
            "Kadam",
            "Sawant",
            "More",
            "Pawar",
            "Deshmukh",
        ],
    ),

    # --------------------------------------------------------------------------
    # DISTRICT: RATNAGIRI (Provisional Baseline - Konkan Division)
    # --------------------------------------------------------------------------
    "RATNAGIRI": DistrictProfile(
        district_id="RATNAGIRI",
        district_name="Ratnagiri",
        division="Konkan",
        region_type="Rural",
        source_reference="Census 2011 (Primary Census Abstract) & DTE Maharashtra Mumbai/Konkan Region Seat Matrix",
        reference_year="2011 / 2022-23",
        source_url="https://censusindia.gov.in and https://dtemaharashtra.gov.in",
        provenance_tier="provisional_baseline",
        available_statistics={
            "census_reference_year": "2011",
            "census_population_scope": "General population (all ages, residential census count)",
            "total_population_2011": 1615069,
            "urban_population_2011": 263770,
            "rural_population_2011": 1351299,
            "urbanization_rate_2011": 0.1633,
            "general_sex_ratio_2011": 1122,
            "scheduled_castes_population_2011": 66547,
            "scheduled_castes_share_2011": 0.0412,
            "scheduled_tribes_population_2011": 21291,
            "scheduled_tribes_share_2011": 0.0132,
            "administrative_revenue_talukas_count": 9,
            "administrative_division": "Konkan",
        },
        missing_data=[
            "taluka_wise_student_enrolment",
            "district_level_household_income_microdata",
            "caste_breakdown_in_private_engineering",
            "direct_cap_vs_management_admission_microdata",
            "money_order_economy_remittance_income_variability",
            "mumbai_out_migration_tertiary_transition_rates",
        ],
        assumptions_and_fallbacks={
            "region_type": (
                "Classified as 'Rural' under the quantitative classification rule (Census 2011 "
                "urban population share < 25%), with Ratnagiri recording a 16.33% urban population "
                "share (263,770 urban residents out of 1,615,069 total population). The district is "
                "characterized by coastal Konkan horticulture, fisheries, and rural agrarian settlements "
                "with limited urban agglomerations outside Ratnagiri and Chiplun. Classification strictly "
                "follows the empirical population benchmark rather than behavioral assumptions."
            ),
            "gender_distribution": (
                "Derived simulation prior (49.0% Male, 51.0% Female) reflecting Ratnagiri's distinctive "
                "demographic profile (Census 2011 general sex ratio of 1,122 females per 1,000 males associated "
                "with historic male out-migration). The general population sex ratio of 1,122 serves as demographic "
                "context motivating this simulation prior, not empirical proof of collegiate female enrolment share. "
                "Collegiate gender composition by faculty is unobserved. It is not an observed student census."
            ),
            "caste_category_distribution": (
                "Derived simulation prior (36% General-EBC, 30% OBC, 8% SC, 2% ST, 8% VJNT, 16% General) "
                "representing an uncalibrated heuristic simulation assumption grounded in general population "
                "demographic baselines (Census 2011: 4.12% SC, 1.32% ST — prominent Kunbi/Bhandari OBC populations "
                "and Maratha/Brahmin general communities) and high EBC fee concession demand. Statutory reservation "
                "percentages are not observed collegiate caste shares and do not constitute an empirical or validated "
                "conversion formula. Exact student-level caste microdata in unaided higher education institutions is unobserved."
            ),
            "admission_mode_distribution": (
                "Provisional modelling assumption: 80% CAP, 10% Institute-Level, 5% Management-Quota, "
                "5% General-Merit anchored in Maharashtra Act No. XXVIII of 2015. Limits of applicability: "
                "This is a provisional modelling assumption, not an observed admission survey."
            ),
            "institution_type_distribution": (
                "Derived simulation prior (10% Government, 40% Government-Aided, 47% Private-Unaided, "
                "3% Deemed/Private-University) reflecting long-established grant-in-aid colleges (e.g. Gogate-Jogalekar "
                "College, DBJ College Chiplun) alongside agricultural university faculties (DBSKKV Dapoli) and "
                "private professional institutes (FAMT Ratnagiri, GIT Lavale/Khed). Note: DBSKKV Dapoli and Gogate-Jogalekar "
                "College serve as illustrative qualitative reference points, not empirical evidence that 40% of district-wide "
                "tertiary students attend aided institutions; this remains a provisional simulation prior. It is not an observed student census."
            ),
            "professional_stream_ratio": (
                "Derived simulation prior (20.0% / 0.200) reflecting a collegiate landscape dominated by conventional "
                "arts, science, commerce, and agricultural faculties, with technical engineering and pharmacy seats "
                "concentrated in Ratnagiri, Chiplun, and Dapoli. District-level student enrolment by stream is unobserved "
                "as a single published statistic."
            ),
            "taluka_distribution": (
                "Derived simulation prior based on Higher Education Institution (HEI) geographic concentration "
                "in University of Mumbai, DBSKKV, and DTE directories (Ratnagiri 40.0%, Chiplun 22.0%, Dapoli 12.0%, "
                "Khed 8.0%, Sangameshwar 5.0%, Rajapur 4.0%, Guhagar 4.0%, Lanja 3.0%, Mandangad 2.0%). Published "
                "DES and census tables do not provide taluka-wise collegiate student enrolment counts."
            ),
            "source_citation_limitation": (
                "Census 2011 figures are from published Primary Census Abstract tables. Portal URLs "
                "(censusindia.gov.in, dtemaharashtra.gov.in) represent root agency landing domains rather "
                "than direct document or download links. AISHE and DTE technical intake figures are derived "
                "from state reports and portal directories; exact district-level cross-tabulations are "
                "unindexed in print volumes and are not asserted as verified print citations."
            ),
        },
        talukas=[
            "Ratnagiri",
            "Chiplun",
            "Dapoli",
            "Khed",
            "Guhagar",
            "Sangameshwar",
            "Lanja",
            "Rajapur",
            "Mandangad",
        ],
        taluka_distribution={
            "Ratnagiri": 0.400,
            "Chiplun": 0.220,
            "Dapoli": 0.120,
            "Khed": 0.080,
            "Sangameshwar": 0.050,
            "Rajapur": 0.040,
            "Guhagar": 0.040,
            "Lanja": 0.030,
            "Mandangad": 0.020,
        },
        gender_distribution={"Male": 0.49, "Female": 0.51},
        institution_type_distribution={
            "Government": 0.10,
            "Government-Aided": 0.40,
            "Private-Unaided": 0.47,
            "Deemed/Private-University": 0.03,
        },
        admission_mode_distribution={
            "CAP": 0.80,
            "Institute-Level": 0.10,
            "Management-Quota": 0.05,
            "General-Merit": 0.05,
        },
        course_level_distribution={
            "Undergraduate": 0.75,
            "Postgraduate": 0.15,
            "Diploma": 0.10,
        },
        professional_stream_ratio=0.200,
        caste_category_distribution={
            "General-EBC": 0.36,
            "OBC": 0.30,
            "SC": 0.08,
            "ST": 0.02,
            "VJNT": 0.08,
            "General": 0.16,
        },
        last_names=[
            "Sawant",
            "Kadam",
            "Joshi",
            "Bane",
            "Salvi",
            "Chavan",
            "Pawar",
            "Shinde",
            "Kambli",
            "Surve",
        ],
    ),

    # --------------------------------------------------------------------------
    # DISTRICT: SATARA (Provisional Baseline - Pune Division)
    # --------------------------------------------------------------------------
    "SATARA": DistrictProfile(
        district_id="SATARA",
        district_name="Satara",
        division="Pune",
        region_type="Rural",
        source_reference="Census 2011 (Primary Census Abstract) & DTE Maharashtra Pune Region Seat Matrix",
        reference_year="2011 / 2022-23",
        source_url="https://censusindia.gov.in and https://dtemaharashtra.gov.in",
        provenance_tier="provisional_baseline",
        available_statistics={
            "census_reference_year": "2011",
            "census_population_scope": "General population (all ages, residential census count)",
            "total_population_2011": 3003741,
            "urban_population_2011": 570058,
            "rural_population_2011": 2433683,
            "urbanization_rate_2011": 0.1898,
            "general_sex_ratio_2011": 988,
            "scheduled_castes_population_2011": 323071,
            "scheduled_castes_share_2011": 0.1076,
            "scheduled_tribes_population_2011": 30064,
            "scheduled_tribes_share_2011": 0.0100,
            "administrative_revenue_talukas_count": 11,
            "administrative_division": "Pune",
        },
        missing_data=[
            "taluka_wise_student_enrolment",
            "district_level_household_income_microdata",
            "caste_breakdown_in_private_engineering",
            "direct_cap_vs_management_admission_microdata",
            "sugar_belt_household_income_seasonality",
            "hostel_residence_and_inter_district_commuter_shares",
        ],
        assumptions_and_fallbacks={
            "region_type": (
                "Classified as 'Rural' under the quantitative classification rule (Census 2011 "
                "urban population share < 25%), with Satara recording an 18.98% urban population "
                "share (570,058 urban residents out of 3,003,741 total population). The district encompasses "
                "prominent Krishna valley agricultural belts and Sahyadri mountainous talukas, with urban "
                "clusters centered in Satara city and Karad. Classification strictly follows the empirical "
                "population benchmark rather than behavioral assumptions."
            ),
            "gender_distribution": (
                "Derived simulation prior (52.0% Male, 48.0% Female) reflecting Western Maharashtra higher "
                "education gender benchmarks. While the general sex ratio is high (988), collegiate technical "
                "and professional enrolment exhibits modest male skew. It is not an observed student census."
            ),
            "caste_category_distribution": (
                "Derived simulation prior (38% General-EBC, 26% OBC, 14% SC, 2% ST, 8% VJNT, 12% General) "
                "representing an uncalibrated heuristic simulation assumption grounded in general population "
                "demographic baselines (Census 2011: 10.76% SC, 1.00% ST) and extensive cooperative agrarian "
                "Maratha/Kunbi EBC fee relief utilization. Statutory reservation percentages are not observed "
                "collegiate caste shares and do not constitute an empirical or validated conversion formula. "
                "Exact student-level caste microdata in unaided higher education institutions is unobserved."
            ),
            "admission_mode_distribution": (
                "Provisional modelling assumption: 80% CAP, 10% Institute-Level, 5% Management-Quota, "
                "5% General-Merit anchored in Maharashtra Act No. XXVIII of 2015. Limits of applicability: "
                "This is a provisional modelling assumption, not an observed admission survey."
            ),
            "institution_type_distribution": (
                "Derived simulation prior (12% Government, 38% Government-Aided, 46% Private-Unaided, "
                "4% Deemed/Private-University) reflecting autonomous government technical education (Government "
                "College of Engineering Karad - GCOEK), prestigious grant-in-aid institutions established by "
                "Rayat Shikshan Sanstha (Chhatrapati Shivaji College, YCIS Satara), and private/deemed health sciences "
                "and engineering colleges (Krishna Vishwa Vidyapeeth Karad). Note: GCOEK and Rayat institutions "
                "serve as illustrative qualitative reference points, not empirical evidence that 38% of district-wide "
                "tertiary students attend aided institutions; this remains a provisional simulation prior."
            ),
            "professional_stream_ratio": (
                "Derived simulation prior (26.0% / 0.260) reflecting strong engineering, medical, pharmacy, and "
                "polytechnic infrastructure concentrated in the Karad and Satara educational clusters alongside "
                "extensive arts, commerce, and science colleges across rural talukas. District-level student enrolment "
                "by stream is unobserved as a single published statistic."
            ),
            "taluka_distribution": (
                "Derived simulation prior based on Higher Education Institution (HEI) geographic concentration "
                "in Shivaji University and DTE directories (Karad 35.0%, Satara 30.0%, Phaltan 8.0%, Wai 6.0%, "
                "Koregaon 5.0%, Patan 4.0%, Khatav 3.0%, Khandala 3.0%, Man 3.0%, Jaoli 2.0%, Mahabaleshwar 1.0%). "
                "Published DES and census tables do not provide taluka-wise collegiate student enrolment counts."
            ),
            "source_citation_limitation": (
                "Census 2011 figures are from published Primary Census Abstract tables. Portal URLs "
                "(censusindia.gov.in, dtemaharashtra.gov.in) represent root agency landing domains rather "
                "than direct document or download links. AISHE and DTE technical intake figures are derived "
                "from state reports and portal directories; exact district-level cross-tabulations are "
                "unindexed in print volumes and are not asserted as verified print citations."
            ),
        },
        talukas=[
            "Satara",
            "Karad",
            "Wai",
            "Phaltan",
            "Khandala",
            "Koregaon",
            "Patan",
            "Jaoli",
            "Mahabaleshwar",
            "Khatav",
            "Man",
        ],
        taluka_distribution={
            "Karad": 0.350,
            "Satara": 0.300,
            "Phaltan": 0.080,
            "Wai": 0.060,
            "Koregaon": 0.050,
            "Patan": 0.040,
            "Khatav": 0.030,
            "Khandala": 0.030,
            "Man": 0.030,
            "Jaoli": 0.020,
            "Mahabaleshwar": 0.010,
        },
        gender_distribution={"Male": 0.52, "Female": 0.48},
        institution_type_distribution={
            "Government": 0.12,
            "Government-Aided": 0.38,
            "Private-Unaided": 0.46,
            "Deemed/Private-University": 0.04,
        },
        admission_mode_distribution={
            "CAP": 0.80,
            "Institute-Level": 0.10,
            "Management-Quota": 0.05,
            "General-Merit": 0.05,
        },
        course_level_distribution={
            "Undergraduate": 0.75,
            "Postgraduate": 0.15,
            "Diploma": 0.10,
        },
        professional_stream_ratio=0.260,
        caste_category_distribution={
            "General-EBC": 0.38,
            "OBC": 0.26,
            "SC": 0.14,
            "ST": 0.02,
            "VJNT": 0.08,
            "General": 0.12,
        },
        last_names=[
            "Bhosale",
            "Patil",
            "Chavan",
            "Pawar",
            "Shinde",
            "Jadhav",
            "Deshmukh",
            "Ghadge",
            "Salunkhe",
            "Mane",
        ],
    ),
    "SINDHUDURG": DistrictProfile(
        district_id="SINDHUDURG",
        district_name="Sindhudurg",
        division="Konkan",
        region_type="Rural",
        source_reference="Census 2011 (Primary Census Abstract, Sindhudurg District) & DTE Maharashtra Mumbai/Konkan Region Seat Matrix",
        reference_year="2011 / 2022-23",
        source_url="https://censusindia.gov.in and https://dtemaharashtra.gov.in",
        provenance_tier="provisional_baseline",
        available_statistics={
            "census_reference_year": "2011",
            "census_population_scope": "General population (all ages, 2011 residential census count)",
            "total_population_2011": 849651,
            "urban_population_2011": 107006,
            "rural_population_2011": 742645,
            "urbanization_rate_2011": 0.1259,
            "general_sex_ratio_2011": 1036,
            "scheduled_castes_population_2011": 55586,
            "scheduled_castes_share_2011": 0.0654,
            "scheduled_tribes_population_2011": 6976,
            "scheduled_tribes_share_2011": 0.0082,
            "administrative_talukas_count": 8,
        },
        missing_data=[
            "taluka_wise_student_enrolment",
            "district_level_household_income_microdata",
            "caste_breakdown_in_private_colleges",
            "direct_cap_vs_management_admission_microdata",
            "horticultural_seasonal_income_variability",
            "out_migration_for_higher_education_to_mumbai_and_goa",
        ],
        assumptions_and_fallbacks={
            "region_type": (
                "Classified as 'Rural' under the quantitative classification rule (Census 2011 urban population share "
                "< 25%), with Sindhudurg recording a 12.59% urban population share (107,006 urban residents out of "
                "849,651). Classification strictly adheres to the empirical population benchmark rather than "
                "behavioral assumptions."
            ),
            "gender_distribution": (
                "Derived simulation prior (49.0% Male, 51.0% Female) reflecting Sindhudurg's female-majority demographic "
                "baseline (Census 2011 general sex ratio of 1,036 females per 1,000 males associated with historic "
                "male out-migration). The general population sex ratio of 1,036 serves as demographic context motivating "
                "this simulation prior, not empirical proof of collegiate female enrolment share. Collegiate gender "
                "composition by faculty is unobserved."
            ),
            "caste_category_distribution": (
                "Derived simulation prior (38% General-EBC, 30% OBC, 8% SC, 2% ST, 6% VJNT, 16% General) representing "
                "an uncalibrated heuristic simulation assumption grounded in general population demographic baselines "
                "(Census 2011: 6.54% SC, 0.82% ST — prominent Bhandari/Gabit coastal OBC communities and Maratha/Brahmin "
                "general groups) and high EBC fee concession demand. Statutory reservation percentages are not observed "
                "collegiate caste shares and do not constitute an empirical or validated conversion formula. "
                "Student-level caste microdata in unaided HEIs is unobserved in published tables."
            ),
            "admission_mode_distribution": (
                "Provisional modelling assumption (80% CAP, 10% Institute-Level, 5% Management-Quota, 5% General-Merit) "
                "anchored in the Maharashtra Unaided Private Professional Educational Institutions Act, 2015. Limits of "
                "applicability: This is a provisional modelling assumption, not an observed admission survey or universal "
                "statutory rule across all institution types."
            ),
            "institution_type_distribution": (
                "Derived simulation prior (10% Government, 42% Government-Aided, 45% Private-Unaided, 3% "
                "Deemed/Private-University) reflecting established rural grant-in-aid arts, commerce, and science colleges "
                "affiliated with the University of Mumbai alongside emerging private engineering and polytechnic institutes. "
                "Note: Regional colleges serve as illustrative qualitative reference points, not empirical evidence that "
                "42% of district-wide tertiary students attend aided institutions; this remains a provisional simulation prior."
            ),
            "professional_stream_ratio": (
                "Derived simulation prior (20.0% / 0.200) reflecting a collegiate landscape dominated by conventional arts, "
                "science, commerce, and horticulture/fisheries degree colleges, with engineering, pharmacy, and polytechnic "
                "seats concentrated in Kankavli, Kudal, and Sawantwadi. District-level student enrolment by stream is "
                "unobserved as a single published statistic."
            ),
            "taluka_distribution": (
                "Derived simulation prior based on Higher Education Institution (HEI) geographic concentration in "
                "University of Mumbai and DTE directories (Kankavli 28.0%, Kudal 24.0%, Sawantwadi 20.0%, Malvan 10.0%, "
                "Devgad 7.0%, Vengurla 5.0%, Dodamarg 3.0%, Vaibhavwadi 3.0%). Published DES and census tables do not provide "
                "taluka-wise collegiate student enrolment counts."
            ),
            "source_citation_limitation": (
                "Census 2011 figures are from published Primary Census Abstract tables. Portal URLs "
                "(censusindia.gov.in, dtemaharashtra.gov.in) represent root agency landing domains rather "
                "than direct document or download links. AISHE and DTE technical intake figures are derived "
                "from state reports and portal directories; exact district-level cross-tabulations are "
                "unindexed in print volumes and are not asserted as verified print citations."
            ),
        },
        talukas=[
            "Kankavli",
            "Devgad",
            "Kudal",
            "Malvan",
            "Sawantwadi",
            "Vengurla",
            "Dodamarg",
            "Vaibhavwadi",
        ],
        taluka_distribution={
            "Kankavli": 0.280,
            "Kudal": 0.240,
            "Sawantwadi": 0.200,
            "Malvan": 0.100,
            "Devgad": 0.070,
            "Vengurla": 0.050,
            "Dodamarg": 0.030,
            "Vaibhavwadi": 0.030,
        },
        gender_distribution={"Male": 0.49, "Female": 0.51},
        institution_type_distribution={
            "Government": 0.10,
            "Government-Aided": 0.42,
            "Private-Unaided": 0.45,
            "Deemed/Private-University": 0.03,
        },
        admission_mode_distribution={
            "CAP": 0.80,
            "Institute-Level": 0.10,
            "Management-Quota": 0.05,
            "General-Merit": 0.05,
        },
        course_level_distribution={
            "Undergraduate": 0.75,
            "Postgraduate": 0.15,
            "Diploma": 0.10,
        },
        professional_stream_ratio=0.200,
        caste_category_distribution={
            "General-EBC": 0.38,
            "OBC": 0.30,
            "SC": 0.08,
            "ST": 0.02,
            "VJNT": 0.06,
            "General": 0.16,
        },
        last_names=[
            "Sawant",
            "Rane",
            "Naik",
            "Parab",
            "Dalvi",
            "Kadam",
            "Gawas",
            "Samant",
            "Tawde",
            "Kambli",
        ],
    ),
    "SOLAPUR": DistrictProfile(
        district_id="SOLAPUR",
        district_name="Solapur",
        division="Pune",
        region_type="Semi-Urban",
        source_reference="Census 2011 (Primary Census Abstract, Solapur District) & DTE Maharashtra Pune Region Seat Matrix",
        reference_year="2011 / 2022-23",
        source_url="https://censusindia.gov.in and https://dtemaharashtra.gov.in",
        provenance_tier="provisional_baseline",
        available_statistics={
            "census_reference_year": "2011",
            "census_population_scope": "General population (all ages, 2011 residential census count)",
            "total_population_2011": 4317756,
            "urban_population_2011": 1399091,
            "rural_population_2011": 2918665,
            "urbanization_rate_2011": 0.3240,
            "general_sex_ratio_2011": 938,
            "scheduled_castes_population_2011": 649745,
            "scheduled_castes_share_2011": 0.1505,
            "scheduled_tribes_population_2011": 77592,
            "scheduled_tribes_share_2011": 0.0180,
            "administrative_talukas_count": 11,
        },
        missing_data=[
            "taluka_wise_student_enrolment",
            "district_level_household_income_microdata",
            "caste_breakdown_in_private_colleges",
            "direct_cap_vs_management_admission_microdata",
            "textile_handloom_household_income_cyclicality",
            "inter_district_student_inflow_to_solapur_university",
        ],
        assumptions_and_fallbacks={
            "region_type": (
                "Classified as 'Semi-Urban' under the quantitative classification rule (Census 2011 urban population "
                "share >= 25% and < 60%), with Solapur recording a 32.40% urban population share (1,399,091 urban "
                "residents out of 4,317,756). Classification strictly adheres to the empirical population benchmark "
                "rather than behavioral assumptions."
            ),
            "gender_distribution": (
                "Derived simulation prior (52.0% Male, 48.0% Female) reflecting Western Maharashtra higher education "
                "gender benchmarks. While general sex ratio is 938, collegiate technical and professional streams "
                "exhibit moderate male skew."
            ),
            "caste_category_distribution": (
                "Derived simulation prior (34% General-EBC, 26% OBC, 18% SC, 3% ST, 9% VJNT, 10% General) representing "
                "an uncalibrated heuristic simulation assumption grounded in general population demographic baselines "
                "(Census 2011: 15.05% SC, 1.80% ST — prominent SC presence, Padmashali/Lingayat OBC communities, and "
                "agrarian Maratha EBC groups). Statutory reservation percentages are not observed collegiate caste shares "
                "and do not constitute an empirical or validated conversion formula. Student-level caste microdata in "
                "unaided HEIs is unobserved in published tables."
            ),
            "admission_mode_distribution": (
                "Provisional modelling assumption (80% CAP, 10% Institute-Level, 5% Management-Quota, 5% General-Merit) "
                "anchored in the Maharashtra Unaided Private Professional Educational Institutions Act, 2015. Limits of "
                "applicability: This is a provisional modelling assumption, not an observed admission survey or universal "
                "statutory rule across all institution types."
            ),
            "institution_type_distribution": (
                "Derived simulation prior (12% Government, 36% Government-Aided, 48% Private-Unaided, 4% "
                "Deemed/Private-University) reflecting Punya Shlok Ahilyadevi Holkar Solapur University, established "
                "grant-in-aid colleges (Sangameshwar College, Dayanand College), and private engineering/polytechnic "
                "institutes (Walchand Institute of Technology). Note: Walchand Institute of Technology and Solapur "
                "University serve as illustrative qualitative reference points, not empirical evidence that 36% of "
                "district-wide tertiary students attend aided institutions; this remains a provisional simulation prior."
            ),
            "professional_stream_ratio": (
                "Derived simulation prior (26.0% / 0.260) reflecting strong technical, engineering, textile technology, "
                "pharmacy, and medical education in Solapur and Pandharpur alongside extensive conventional arts, science, "
                "and commerce degree enrolments across rural talukas. District-level student enrolment by stream is "
                "unobserved as a single published statistic."
            ),
            "taluka_distribution": (
                "Derived simulation prior based on Higher Education Institution (HEI) geographic concentration in "
                "Solapur University and DTE directories (Solapur North 32.0%, Pandharpur 18.0%, Barshi 12.0%, "
                "Solapur South 8.0%, Malshiras 7.0%, Madha 5.0%, Sangola 5.0%, Mohol 4.0%, Akkalkot 4.0%, Karmala 3.0%, "
                "Mangalwedha 2.0%). Published DES and census tables do not provide taluka-wise collegiate student enrolment counts."
            ),
            "source_citation_limitation": (
                "Census 2011 figures are from published Primary Census Abstract tables. Portal URLs "
                "(censusindia.gov.in, dtemaharashtra.gov.in) represent root agency landing domains rather "
                "than direct document or download links. AISHE and DTE technical intake figures are derived "
                "from state reports and portal directories; exact district-level cross-tabulations are "
                "unindexed in print volumes and are not asserted as verified print citations."
            ),
        },
        talukas=[
            "Solapur North",
            "Solapur South",
            "Barshi",
            "Pandharpur",
            "Malshiras",
            "Karmala",
            "Madha",
            "Sangola",
            "Mangalwedha",
            "Mohol",
            "Akkalkot",
        ],
        taluka_distribution={
            "Solapur North": 0.320,
            "Pandharpur": 0.180,
            "Barshi": 0.120,
            "Solapur South": 0.080,
            "Malshiras": 0.070,
            "Madha": 0.050,
            "Sangola": 0.050,
            "Mohol": 0.040,
            "Akkalkot": 0.040,
            "Karmala": 0.030,
            "Mangalwedha": 0.020,
        },
        gender_distribution={"Male": 0.52, "Female": 0.48},
        institution_type_distribution={
            "Government": 0.12,
            "Government-Aided": 0.36,
            "Private-Unaided": 0.48,
            "Deemed/Private-University": 0.04,
        },
        admission_mode_distribution={
            "CAP": 0.80,
            "Institute-Level": 0.10,
            "Management-Quota": 0.05,
            "General-Merit": 0.05,
        },
        course_level_distribution={
            "Undergraduate": 0.75,
            "Postgraduate": 0.15,
            "Diploma": 0.10,
        },
        professional_stream_ratio=0.260,
        caste_category_distribution={
            "General-EBC": 0.34,
            "OBC": 0.26,
            "SC": 0.18,
            "ST": 0.03,
            "VJNT": 0.09,
            "General": 0.10,
        },
        last_names=[
            "Patil",
            "Shinde",
            "Jadhav",
            "Bhosale",
            "Mane",
            "Kadam",
            "Gaikwad",
            "Kamble",
            "Pawar",
            "Kshirsagar",
        ],
    ),
    "THANE": DistrictProfile(
        district_id="THANE",
        district_name="Thane",
        division="Konkan",
        region_type="Urban",
        source_reference="Census 2011 (Primary Census Abstract Reconstructed for Post-Bifurcation Thane District) & DTE Maharashtra Mumbai/Konkan Region Seat Matrix",
        reference_year="2011 / 2022-23",
        source_url="https://censusindia.gov.in and https://dtemaharashtra.gov.in",
        provenance_tier="provisional_baseline",
        available_statistics={
            "census_reference_year": "2011",
            "census_population_scope": "General population (all ages, 2011 residential census count reconstructed for post-2014 7-taluka boundary)",
            "total_population_2011": 8070032,
            "urban_population_2011": 6953240,
            "rural_population_2011": 1116792,
            "urbanization_rate_2011": 0.8616,
            "general_sex_ratio_2011": 868,
            "scheduled_castes_population_2011": 643326,
            "scheduled_castes_share_2011": 0.0797,
            "scheduled_tribes_population_2011": 423922,
            "scheduled_tribes_share_2011": 0.0525,
            "administrative_talukas_count": 7,
            "bifurcation_notes": (
                "Undivided Thane (11,060,148 general population in Census 2011) was bifurcated on August 1, 2014, "
                "with 8 northern talukas forming Palghar district (2,990,116 general population) and 7 southern talukas "
                "retained in post-bifurcation Thane district (8,070,032 general population). The configured Thane demographic "
                "profile strictly represents the 7 post-bifurcation talukas: total population 8,070,032, urban 6,953,240 (86.16%), "
                "rural 1,116,792 (13.84%), SC 643,326 (7.97%), ST 423,922 (5.25%), and general sex ratio 868 (reconstructed "
                "Census 2011 PCA aggregate: 3,750,733 females / 4,319,299 males * 1,000 = 868.366, rounded to 868). Historical "
                "note: The Directorate of Economics and Statistics (DES) decadal series benchmark of 880 reflects the undivided "
                "15-taluka district (provisional compilation), while the final Census 2011 PCA sex ratio for undivided Thane was "
                "886 (5,195,070 females / 5,865,078 males * 1,000). Undivided baseline statistics (total: 11,060,148; urban: "
                "8,388,450; rural: 2,671,698; SC: 730,089; ST: 1,542,451) are documented for archival traceability."
            ),
        },
        missing_data=[
            "taluka_wise_student_enrolment",
            "district_level_household_income_microdata",
            "caste_breakdown_in_private_colleges",
            "direct_cap_vs_management_admission_microdata",
            "mumbai_metropolitan_commuter_student_fraction",
            "inter_municipal_migration_and_local_transit_subsidies",
        ],
        assumptions_and_fallbacks={
            "region_type": (
                "Classified as 'Urban' under the quantitative classification rule (Census 2011 reconstructed urban "
                "population share >= 60%), with post-bifurcation Thane recording an 86.16% urban population share "
                "(6,953,240 urban residents out of 8,070,032). Classification strictly adheres to the empirical "
                "population benchmark rather than behavioral assumptions."
            ),
            "gender_distribution": (
                "Derived simulation prior (50.5% Male, 49.5% Female) representing an uncalibrated provisional simulation "
                "assumption informed by broad metropolitan higher-education gender parity context in urban Maharashtra. "
                "AISHE does not publish an MMR or municipal-corporation-level gender breakdown, and district-level "
                "collegiate gender composition by faculty is unobserved. The configured values are provisional simulation "
                "assumptions, not measured student statistics."
            ),
            "caste_category_distribution": (
                "Derived simulation prior (35% General-EBC, 25% OBC, 12% SC, 6% ST, 6% VJNT, 16% General) representing "
                "an uncalibrated heuristic simulation assumption grounded in reconstructed general population demographic "
                "baselines (Census 2011: 7.97% SC, 5.25% ST — Agri/Koli coastal and municipal OBC populations, suburban "
                "Maratha/General communities, and residual tribal groups in Shahapur and Murbad). Statutory reservation "
                "percentages are not observed collegiate caste shares and do not constitute an empirical or validated "
                "conversion formula. Student-level caste microdata in unaided HEIs is unobserved in published tables."
            ),
            "admission_mode_distribution": (
                "Provisional modelling assumption (80% CAP, 10% Institute-Level, 5% Management-Quota, 5% General-Merit) "
                "anchored in the Maharashtra Unaided Private Professional Educational Institutions Act, 2015. Limits of "
                "applicability: This is a provisional modelling assumption, not an observed admission survey or universal "
                "statutory rule across all institution types."
            ),
            "institution_type_distribution": (
                "Derived simulation prior (8% Government, 28% Government-Aided, 58% Private-Unaided, 6% "
                "Deemed/Private-University) reflecting heavy density of private unaided engineering, architecture, "
                "pharmacy, and management institutes affiliated with the University of Mumbai alongside municipal "
                "and aided colleges. Note: Named regional institutions serve as illustrative qualitative reference "
                "points, not empirical evidence that 28% of district-wide tertiary students attend aided institutions; "
                "this remains a provisional simulation prior."
            ),
            "professional_stream_ratio": (
                "Derived simulation prior (34.0% / 0.340) reflecting substantial concentration of professional "
                "technical institutions (engineering, MCA, MBA, pharmacy, architecture) across the Thane-Belapur and "
                "Kalyan-Dombivli industrial and urban belts. District-level student enrolment by stream is unobserved as "
                "a single published statistic."
            ),
            "taluka_distribution": (
                "Derived simulation prior based on Higher Education Institution (HEI) geographic concentration in "
                "University of Mumbai and DTE directories (Thane 44.0%, Kalyan 24.0%, Bhiwandi 10.0%, Ambernath 8.0%, "
                "Ulhasnagar 8.0%, Shahapur 4.0%, Murbad 2.0%). Published DES and census tables do not provide "
                "taluka-wise collegiate student enrolment counts."
            ),
            "source_citation_limitation": (
                "Census 2011 figures are reconstructed from published Primary Census Abstract taluka tables of "
                "undivided Thane following the 2014 creation of Palghar. Portal URLs (censusindia.gov.in, "
                "dtemaharashtra.gov.in) represent root agency landing domains rather than direct document or "
                "download links. AISHE and DTE technical intake figures are derived from state reports and portal "
                "directories; exact district-level cross-tabulations are unindexed in print volumes and are not "
                "asserted as verified print citations."
            ),
        },
        talukas=[
            "Thane",
            "Kalyan",
            "Bhiwandi",
            "Ambernath",
            "Ulhasnagar",
            "Shahapur",
            "Murbad",
        ],
        taluka_distribution={
            "Thane": 0.440,
            "Kalyan": 0.240,
            "Bhiwandi": 0.100,
            "Ambernath": 0.080,
            "Ulhasnagar": 0.080,
            "Shahapur": 0.040,
            "Murbad": 0.020,
        },
        gender_distribution={"Male": 0.505, "Female": 0.495},
        institution_type_distribution={
            "Government": 0.08,
            "Government-Aided": 0.28,
            "Private-Unaided": 0.58,
            "Deemed/Private-University": 0.06,
        },
        admission_mode_distribution={
            "CAP": 0.80,
            "Institute-Level": 0.10,
            "Management-Quota": 0.05,
            "General-Merit": 0.05,
        },
        course_level_distribution={
            "Undergraduate": 0.75,
            "Postgraduate": 0.15,
            "Diploma": 0.10,
        },
        professional_stream_ratio=0.340,
        caste_category_distribution={
            "General-EBC": 0.35,
            "OBC": 0.25,
            "SC": 0.12,
            "ST": 0.06,
            "VJNT": 0.06,
            "General": 0.16,
        },
        last_names=[
            "Patil",
            "Mhatre",
            "Thakur",
            "Deshmukh",
            "Gharat",
            "Kadam",
            "Shinde",
            "Jadhav",
            "Bhoir",
            "Chavan",
        ],
    ),
    "WARDHA": DistrictProfile(
        district_id="WARDHA",
        district_name="Wardha",
        division="Nagpur",
        region_type="Semi-Urban",
        source_reference="Census 2011 (Primary Census Abstract, Wardha District) & DTE Maharashtra Nagpur Region Seat Matrix",
        reference_year="2011 / 2022-23",
        source_url="https://censusindia.gov.in and https://dtemaharashtra.gov.in",
        provenance_tier="provisional_baseline",
        available_statistics={
            "census_reference_year": "2011",
            "census_population_scope": "General population (all ages, 2011 residential census count)",
            "total_population_2011": 1300774,
            "urban_population_2011": 423300,
            "rural_population_2011": 877474,
            "urbanization_rate_2011": 0.3254,
            "general_sex_ratio_2011": 946,
            "scheduled_castes_population_2011": 188868,
            "scheduled_castes_share_2011": 0.1452,
            "scheduled_tribes_population_2011": 149460,
            "scheduled_tribes_share_2011": 0.1149,
            "administrative_talukas_count": 8,
        },
        missing_data=[
            "taluka_wise_student_enrolment",
            "district_level_household_income_microdata",
            "caste_breakdown_in_private_colleges",
            "direct_cap_vs_management_admission_microdata",
            "cotton_soybean_agrarian_income_seasonality",
            "inter_district_commuter_share_from_nagpur",
        ],
        assumptions_and_fallbacks={
            "region_type": (
                "Classified as 'Semi-Urban' under the quantitative classification rule (Census 2011 urban population "
                "share >= 25% and < 60%), with Wardha recording a 32.54% urban population share (423,300 urban "
                "residents out of 1,300,774). Classification strictly adheres to the empirical population benchmark "
                "rather than behavioral assumptions."
            ),
            "gender_distribution": (
                "Derived simulation prior (52.0% Male, 48.0% Female) reflecting Eastern Vidarbha higher education "
                "gender transition benchmarks. While general sex ratio is 946, collegiate technical and professional "
                "streams exhibit moderate male skew."
            ),
            "caste_category_distribution": (
                "Derived simulation prior (28% General-EBC, 32% OBC, 18% SC, 12% ST, 4% VJNT, 6% General) representing "
                "an uncalibrated heuristic simulation assumption grounded in general population demographic baselines "
                "(Census 2011: 14.52% SC, 11.49% ST — prominent SC/ST and Vidarbha Kunbi/OBC communities). Statutory "
                "reservation percentages are not observed collegiate caste shares and do not constitute an empirical "
                "or validated conversion formula. Student-level caste microdata in unaided HEIs is unobserved in "
                "published tables."
            ),
            "admission_mode_distribution": (
                "Provisional modelling assumption (80% CAP, 10% Institute-Level, 5% Management-Quota, 5% General-Merit) "
                "anchored in the Maharashtra Unaided Private Professional Educational Institutions Act, 2015. Limits of "
                "applicability: This is a provisional modelling assumption, not an observed admission survey or universal "
                "statutory rule across all institution types."
            ),
            "institution_type_distribution": (
                "Derived simulation prior (12% Government, 38% Government-Aided, 46% Private-Unaided, 4% "
                "Deemed/Private-University) reflecting prestigious historic aided educational trusts (Shiksha Mandal Wardha), "
                "prominent health sciences institutions (MGIMS Sewagram), and private engineering colleges (Bajaj "
                "Institute of Technology). Note: MGIMS Sewagram and Shiksha Mandal colleges serve as illustrative qualitative "
                "reference points, not empirical evidence that 38% of district-wide tertiary students attend aided "
                "institutions; this remains a provisional simulation prior."
            ),
            "professional_stream_ratio": (
                "Derived simulation prior (25.0% / 0.250) reflecting established medical, engineering, agricultural, "
                "and polytechnic institutions in Wardha and Sewagram alongside extensive conventional degree colleges. "
                "District-level student enrolment by stream is unobserved as a single published statistic."
            ),
            "taluka_distribution": (
                "Derived simulation prior based on Higher Education Institution (HEI) geographic concentration in "
                "RTMNU and DTE directories (Wardha 42.0%, Hinganghat 20.0%, Arvi 10.0%, Deoli 8.0%, Seloo 6.0%, "
                "Samudrapur 5.0%, Karanja 5.0%, Ashti 4.0%). Published DES and census tables do not provide "
                "taluka-wise collegiate student enrolment counts."
            ),
            "source_citation_limitation": (
                "Census 2011 figures are from published Primary Census Abstract tables. Portal URLs "
                "(censusindia.gov.in, dtemaharashtra.gov.in) represent root agency landing domains rather "
                "than direct document or download links. AISHE and DTE technical intake figures are derived "
                "from state reports and portal directories; exact district-level cross-tabulations are "
                "unindexed in print volumes and are not asserted as verified print citations."
            ),
        },
        talukas=[
            "Wardha",
            "Deoli",
            "Seloo",
            "Arvi",
            "Ashti",
            "Karanja",
            "Hinganghat",
            "Samudrapur",
        ],
        taluka_distribution={
            "Wardha": 0.420,
            "Hinganghat": 0.200,
            "Arvi": 0.100,
            "Deoli": 0.080,
            "Seloo": 0.060,
            "Samudrapur": 0.050,
            "Karanja": 0.050,
            "Ashti": 0.040,
        },
        gender_distribution={"Male": 0.52, "Female": 0.48},
        institution_type_distribution={
            "Government": 0.12,
            "Government-Aided": 0.38,
            "Private-Unaided": 0.46,
            "Deemed/Private-University": 0.04,
        },
        admission_mode_distribution={
            "CAP": 0.80,
            "Institute-Level": 0.10,
            "Management-Quota": 0.05,
            "General-Merit": 0.05,
        },
        course_level_distribution={
            "Undergraduate": 0.75,
            "Postgraduate": 0.15,
            "Diploma": 0.10,
        },
        professional_stream_ratio=0.250,
        caste_category_distribution={
            "General-EBC": 0.28,
            "OBC": 0.32,
            "SC": 0.18,
            "ST": 0.12,
            "VJNT": 0.04,
            "General": 0.06,
        },
        last_names=[
            "Bhende",
            "Chaudhari",
            "Gaikwad",
            "Ingle",
            "Meshram",
            "Raut",
            "Sonwane",
            "Wankhede",
            "Zade",
            "Deshmukh",
        ],
    ),
    "WASHIM": DistrictProfile(
        district_id="WASHIM",
        district_name="Washim",
        division="Amravati",
        region_type="Rural",
        source_reference="Census 2011 (Primary Census Abstract, Washim District) & DTE Maharashtra Amravati Region Seat Matrix",
        reference_year="2011 / 2022-23",
        source_url="https://censusindia.gov.in and https://dtemaharashtra.gov.in",
        provenance_tier="provisional_baseline",
        available_statistics={
            "census_reference_year": "2011",
            "census_population_scope": "General population (all ages, 2011 residential census count)",
            "total_population_2011": 1197160,
            "urban_population_2011": 211413,
            "rural_population_2011": 985747,
            "urbanization_rate_2011": 0.1766,
            "general_sex_ratio_2011": 930,
            "scheduled_castes_population_2011": 229462,
            "scheduled_castes_share_2011": 0.1917,
            "scheduled_tribes_population_2011": 80471,
            "scheduled_tribes_share_2011": 0.0672,
            "administrative_talukas_count": 6,
        },
        missing_data=[
            "taluka_wise_student_enrolment",
            "district_level_household_income_microdata",
            "caste_breakdown_in_private_colleges",
            "direct_cap_vs_management_admission_microdata",
            "soybean_cotton_dryland_income_variability",
            "out_migration_for_higher_education_to_amravati_and_pune",
        ],
        assumptions_and_fallbacks={
            "region_type": (
                "Classified as 'Rural' under the quantitative classification rule (Census 2011 urban population share "
                "< 25%), with Washim recording a 17.66% urban population share (211,413 urban residents out of "
                "1,197,160). Classification strictly adheres to the empirical population benchmark rather than "
                "behavioral assumptions."
            ),
            "gender_distribution": (
                "Derived simulation prior (53.0% Male, 47.0% Female) reflecting Western Vidarbha higher education "
                "gender transition benchmarks. While the Census 2011 general population sex ratio is 930 females per 1,000 "
                "males, this serves as demographic context motivating the prior rather than proof of collegiate female enrolment. "
                "Collegiate gender composition by faculty is unobserved in published district tables."
            ),
            "caste_category_distribution": (
                "Derived simulation prior (28% General-EBC, 32% OBC, 20% SC, 7% ST, 8% VJNT, 5% General) representing "
                "an uncalibrated heuristic simulation assumption grounded in general population demographic baselines "
                "(Census 2011: 19.17% SC, 6.72% ST — prominent SC communities, agrarian Kunbi/Mali OBC groups, and Banjara VJNT populations) "
                "alongside high EBC fee concession demand. Statutory reservation percentages are not observed collegiate caste shares "
                "and do not constitute an empirical or validated conversion formula. Student-level caste microdata in unaided HEIs "
                "is unobserved in published tables."
            ),
            "admission_mode_distribution": (
                "Provisional modelling assumption (80% CAP, 10% Institute-Level, 5% Management-Quota, 5% General-Merit) "
                "anchored in the Maharashtra Unaided Private Professional Educational Institutions Act, 2015. Limits of "
                "applicability: This is a provisional modelling assumption, not an observed admission survey or universal "
                "statutory rule across all institution types."
            ),
            "institution_type_distribution": (
                "Derived simulation prior (8% Government, 42% Government-Aided, 47% Private-Unaided, 3% "
                "Deemed/Private-University) reflecting established rural aided arts, commerce, and science colleges "
                "affiliated with Sant Gadge Baba Amravati University (SGBAU), the Government Polytechnic Washim, and private "
                "unaided technical/professional institutes. Note: Government Polytechnic Washim and SGBAU-affiliated degree colleges "
                "serve as illustrative qualitative reference points, not empirical evidence that 42% of district-wide tertiary "
                "students attend aided institutions; this remains a provisional simulation prior."
            ),
            "professional_stream_ratio": (
                "Derived simulation prior (20.0% / 0.200) reflecting an agrarian dryland economy where tertiary education "
                "is dominated by conventional university degree programs, with engineering, polytechnic, and pharmacy intake "
                "concentrated in Washim and Karanja. District-level student enrolment by stream is unobserved as a single "
                "published statistic."
            ),
            "taluka_distribution": (
                "Derived simulation prior based on Higher Education Institution (HEI) geographic concentration in "
                "SGBAU and DTE directories (Washim 38.0%, Karanja 22.0%, Risod 15.0%, Mangrulpir 11.0%, Malegaon 8.0%, "
                "Manora 6.0%). Published DES and census tables do not provide taluka-wise collegiate student enrolment counts."
            ),
            "source_citation_limitation": (
                "Census 2011 figures are from published Primary Census Abstract tables. Portal URLs "
                "(censusindia.gov.in, dtemaharashtra.gov.in) represent root agency landing domains rather "
                "than direct document or download links. AISHE and DTE technical intake figures are derived "
                "from state reports and portal directories; exact district-level cross-tabulations are "
                "unindexed in print volumes and are not asserted as verified print citations."
            ),
        },
        talukas=[
            "Washim",
            "Karanja",
            "Risod",
            "Mangrulpir",
            "Malegaon",
            "Manora",
        ],
        taluka_distribution={
            "Washim": 0.380,
            "Karanja": 0.220,
            "Risod": 0.150,
            "Mangrulpir": 0.110,
            "Malegaon": 0.080,
            "Manora": 0.060,
        },
        gender_distribution={"Male": 0.53, "Female": 0.47},
        institution_type_distribution={
            "Government": 0.08,
            "Government-Aided": 0.42,
            "Private-Unaided": 0.47,
            "Deemed/Private-University": 0.03,
        },
        admission_mode_distribution={
            "CAP": 0.80,
            "Institute-Level": 0.10,
            "Management-Quota": 0.05,
            "General-Merit": 0.05,
        },
        course_level_distribution={
            "Undergraduate": 0.75,
            "Postgraduate": 0.15,
            "Diploma": 0.10,
        },
        professional_stream_ratio=0.200,
        caste_category_distribution={
            "General-EBC": 0.28,
            "OBC": 0.32,
            "SC": 0.20,
            "ST": 0.07,
            "VJNT": 0.08,
            "General": 0.05,
        },
        last_names=[
            "Rathod",
            "Deshmukh",
            "Chavan",
            "Gaikwad",
            "Ingle",
            "Thakur",
            "Wankhade",
            "Patil",
            "Tayade",
            "Bhagat",
        ],
    ),
    "YAVATMAL": DistrictProfile(
        district_id="YAVATMAL",
        district_name="Yavatmal",
        division="Amravati",
        region_type="Rural",
        source_reference="Census 2011 (Primary Census Abstract, Yavatmal District) & DTE Maharashtra Amravati Region Seat Matrix",
        reference_year="2011 / 2022-23",
        source_url="https://censusindia.gov.in and https://dtemaharashtra.gov.in",
        provenance_tier="provisional_baseline",
        available_statistics={
            "census_reference_year": "2011",
            "census_population_scope": "General population (all ages, 2011 residential census count)",
            "total_population_2011": 2772348,
            "urban_population_2011": 598153,
            "rural_population_2011": 2174195,
            "urbanization_rate_2011": 0.2158,
            "general_sex_ratio_2011": 952,
            "scheduled_castes_population_2011": 328348,
            "scheduled_castes_share_2011": 0.1184,
            "scheduled_tribes_population_2011": 514142,
            "scheduled_tribes_share_2011": 0.1855,
            "administrative_talukas_count": 16,
        },
        missing_data=[
            "taluka_wise_student_enrolment",
            "district_level_household_income_microdata",
            "caste_breakdown_in_private_colleges",
            "direct_cap_vs_management_admission_microdata",
            "cotton_belt_agrarian_income_distress_seasonality",
            "tribal_ashram_school_tertiary_transition_rates",
        ],
        assumptions_and_fallbacks={
            "region_type": (
                "Classified as 'Rural' under the quantitative classification rule (Census 2011 urban population share "
                "< 25%), with Yavatmal recording a 21.58% urban population share (598,153 urban residents out of "
                "2,772,348). Classification strictly adheres to the empirical population benchmark rather than "
                "behavioral assumptions."
            ),
            "gender_distribution": (
                "Derived simulation prior (52.0% Male, 48.0% Female) reflecting Southern Vidarbha collegiate participation "
                "patterns. While the Census 2011 general population sex ratio is 952 females per 1,000 males, this serves as "
                "demographic context motivating the prior rather than proof of collegiate female enrolment. Collegiate gender "
                "composition by faculty is unobserved in published district tables."
            ),
            "caste_category_distribution": (
                "Derived simulation prior (25% General-EBC, 30% OBC, 14% SC, 19% ST, 7% VJNT, 5% General) representing "
                "an uncalibrated heuristic simulation assumption grounded in general population demographic baselines "
                "(Census 2011: 18.55% ST, 11.84% SC — substantial Kolam, Gond, and Andh tribal populations, Kunbi/Mali OBC base, "
                "and Banjara VJNT communities in Pusad and Darwha) alongside high EBC fee concession demand. Statutory reservation "
                "percentages are not observed collegiate caste shares and do not constitute an empirical or validated conversion formula. "
                "Student-level caste microdata in unaided HEIs is unobserved in published tables."
            ),
            "admission_mode_distribution": (
                "Provisional modelling assumption (80% CAP, 10% Institute-Level, 5% Management-Quota, 5% General-Merit) "
                "anchored in the Maharashtra Unaided Private Professional Educational Institutions Act, 2015. Limits of "
                "applicability: This is a provisional modelling assumption, not an observed admission survey or universal "
                "statutory rule across all institution types."
            ),
            "institution_type_distribution": (
                "Derived simulation prior (12% Government, 40% Government-Aided, 45% Private-Unaided, 3% "
                "Deemed/Private-University) reflecting the Government College of Engineering Yavatmal (GCOEY), Shri Vasantrao Naik "
                "Government Medical College, Government Polytechnic, aided colleges under SGBAU Amravati, and private unaided "
                "engineering/polytechnic institutes in Yavatmal and Pusad. Note: GCOEY and SVNGMC serve as illustrative qualitative "
                "reference points, not empirical evidence that 40% of district-wide tertiary students attend aided institutions; "
                "this remains a provisional simulation prior."
            ),
            "professional_stream_ratio": (
                "Derived simulation prior (22.0% / 0.220) reflecting professional engineering, polytechnic, medical, and pharmacy "
                "clusters in Yavatmal city and Pusad, balanced by broad rural agrarian conventional arts, commerce, and science colleges. "
                "District-level student enrolment by stream is unobserved as a single published statistic."
            ),
            "taluka_distribution": (
                "Derived simulation prior based on Higher Education Institution (HEI) geographic concentration in "
                "SGBAU and DTE directories (Yavatmal 30.0%, Pusad 18.0%, Wani 10.0%, Umarkhed 7.0%, Digras 5.0%, Darwha 5.0%, "
                "Kelapur 4.0%, Ghatanji 4.0%, Arni 3.5%, Ralegaon 3.0%, Mahagaon 2.5%, Kalamb 2.0%, Ner 2.0%, Babulgaon 1.5%, "
                "Maregaon 1.5%, Zari-Jamani 1.0%). Published DES and census tables do not provide taluka-wise collegiate student "
                "enrolment counts."
            ),
            "source_citation_limitation": (
                "Census 2011 figures are from published Primary Census Abstract tables. Portal URLs "
                "(censusindia.gov.in, dtemaharashtra.gov.in) represent root agency landing domains rather "
                "than direct document or download links. AISHE and DTE technical intake figures are derived "
                "from state reports and portal directories; exact district-level cross-tabulations are "
                "unindexed in print volumes and are not asserted as verified print citations."
            ),
        },
        talukas=[
            "Yavatmal",
            "Pusad",
            "Umarkhed",
            "Wani",
            "Digras",
            "Darwha",
            "Kelapur",
            "Ghatanji",
            "Arni",
            "Ralegaon",
            "Mahagaon",
            "Kalamb",
            "Ner",
            "Babulgaon",
            "Maregaon",
            "Zari-Jamani",
        ],
        taluka_distribution={
            "Yavatmal": 0.300,
            "Pusad": 0.180,
            "Wani": 0.100,
            "Umarkhed": 0.070,
            "Digras": 0.050,
            "Darwha": 0.050,
            "Kelapur": 0.040,
            "Ghatanji": 0.040,
            "Arni": 0.035,
            "Ralegaon": 0.030,
            "Mahagaon": 0.025,
            "Kalamb": 0.020,
            "Ner": 0.020,
            "Babulgaon": 0.015,
            "Maregaon": 0.015,
            "Zari-Jamani": 0.010,
        },
        gender_distribution={"Male": 0.52, "Female": 0.48},
        institution_type_distribution={
            "Government": 0.12,
            "Government-Aided": 0.40,
            "Private-Unaided": 0.45,
            "Deemed/Private-University": 0.03,
        },
        admission_mode_distribution={
            "CAP": 0.80,
            "Institute-Level": 0.10,
            "Management-Quota": 0.05,
            "General-Merit": 0.05,
        },
        course_level_distribution={
            "Undergraduate": 0.75,
            "Postgraduate": 0.15,
            "Diploma": 0.10,
        },
        professional_stream_ratio=0.220,
        caste_category_distribution={
            "General-EBC": 0.25,
            "OBC": 0.30,
            "SC": 0.14,
            "ST": 0.19,
            "VJNT": 0.07,
            "General": 0.05,
        },
        last_names=[
            "Rathod",
            "Jadhav",
            "Ade",
            "Meshram",
            "Tekam",
            "Madavi",
            "Chaudhari",
            "Deshmukh",
            "Gaikwad",
            "Pawar",
        ],
    ),

}


# ==============================================================================
# HELPER FUNCTIONS & REGISTRY ACCESSORS
# ==============================================================================

def list_supported_districts() -> List[str]:
    """Returns a sorted list of all configured Maharashtra district names."""
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
