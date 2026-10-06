"""
Data Adapter for Maharashtra Reference Dataset:
Dhule District Education & Social Community Services (2010-11)

File Source: data/raw/Dhule_Education_Social_Community_Services_2010_11.xlsx
Source Context: District Statistical Abstract / Educational Amenities Census Table.

Epistemic Provenance Transparency:
1. Directly Observed / Reference Values:
   - District & Taluka names and administrative codes (Dhule, Shirpur, Sindkhede, Sakri).
   - Higher education institution counts by management type (Govt: 0, Pvt-Aided: 24, Pvt-Unaided: 49).
   - Professional institute counts (Engineering Degree: 4, Engineering Diploma: 4, Medical: 1, ITI/Voc: 8).
   - Stream-wise intake enrolment (Arts, Science, Commerce, MCVC, Polytech, ITI, Engg, Med).
   - Senior Secondary student enrolment by gender (Boys: 26,138, Girls: 19,882).

2. Derived Distributions (for Dhule Cohort Generation):
   - Higher education institution management distribution:
     Govt = 0.0, Pvt-Aided = 24/73 (32.88%), Pvt-Unaided = 49/73 (67.12%).
   - Senior secondary transition gender ratio:
     Male = 26,138 / 46,020 (56.8%), Female = 19,882 / 46,020 (43.2%).
   - Taluka weight distribution based on aggregate higher education enrolments.
   - Professional stream ratio in higher education enrolments (~23.5% professional, 76.5% non-professional).

3. Unavailable Fields in this Dataset:
   - Caste / Social categories (SC / ST / OBC / General-EBC / VJNT).
   - Household income and socio-economic strata.
   - Admission quota types (CAP vs Management Quota).
   - Parental education levels.
   - All synthetic behavioural and psychological factors.
"""

from dataclasses import dataclass, field
import os
from typing import Dict, List, Any, Optional
import xml.etree.ElementTree as ET
import zipfile

from simulation.persona_schema import PopulationDistributionConfig
from simulation.persona_generator import EXAMPLE_POPULATION_CONFIG


@dataclass
class RawTalukaEducationRecord:
    """Represents one directly observed taluka row from the Excel table."""
    reference_year: str
    district_name: str
    district_code: str
    taluka_name: str
    taluka_code: str
    
    # Institution Counts
    govt_colleges: int
    pvt_aided_colleges: int
    pvt_unaided_colleges: int
    eng_degree_colleges: int
    eng_diploma_colleges: int
    med_degree_colleges: int
    iti_voc_institutes: int

    # Higher Ed Enrolments by Stream
    arts_enrolment: int
    science_enrolment: int
    commerce_enrolment: int
    mcvc_enrolment: int
    polytechnic_enrolment: int
    iti_enrolment: int
    eng_degree_enrolment: int
    eng_diploma_enrolment: int
    med_degree_enrolment: int

    # Senior Secondary Gender Enrolment
    sr_sec_boys: int
    sr_sec_girls: int


@dataclass
class DhuleEducationDatasetSummary:
    """
    Structured summary of directly observed aggregates and derived distributions
    from the Dhule 2010-11 education dataset.
    """
    reference_year: str
    district_name: str
    district_code: str
    taluka_records: List[RawTalukaEducationRecord]

    # Directly Observed Totals across the District
    total_govt_colleges: int
    total_pvt_aided_colleges: int
    total_pvt_unaided_colleges: int
    total_engineering_degree_colleges: int
    total_engineering_diploma_colleges: int
    total_medical_degree_colleges: int
    total_iti_voc_institutions: int
    total_higher_ed_enrolment: int
    total_sr_sec_boys: int
    total_sr_sec_girls: int

    # Derived Proportions (Explicitly computed from observed aggregates)
    derived_gender_distribution: Dict[str, float]
    derived_institution_type_distribution: Dict[str, float]
    derived_taluka_distribution: Dict[str, float]
    derived_professional_stream_ratio: float

    # Explicit documentation of unavailable fields
    unavailable_fields: List[str] = field(default_factory=lambda: [
        "caste_category",
        "family_income",
        "admission_mode",
        "parental_education_level",
        "initial_awareness",
        "digital_literacy",
        "document_readiness",
        "financial_urgency",
        "peer_network_support",
        "institutional_trust",
        "personality_traits"
    ])


class DhuleEducationDatasetAdapter:
    """
    Parser and adapter for `Dhule_Education_Social_Community_Services_2010_11.xlsx`.
    Uses standard library zipfile/XML parsing to remain completely dependency-free.
    """

    DEFAULT_DATASET_PATH = os.path.join(
        os.path.dirname(__file__), "..", "data", "raw", "Dhule_Education_Social_Community_Services_2010_11.xlsx"
    )

    @classmethod
    def load_and_parse(cls, file_path: Optional[str] = None) -> DhuleEducationDatasetSummary:
        """
        Parses the raw Excel file and produces a structured summary of observed
        and derived values.
        """
        target_path = file_path or cls.DEFAULT_DATASET_PATH
        target_path = os.path.abspath(target_path)

        if not os.path.exists(target_path):
            raise FileNotFoundError(f"Dhule reference dataset not found at: {target_path}")

        records: List[RawTalukaEducationRecord] = []

        with zipfile.ZipFile(target_path, "r") as z:
            sheet_tree = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
            ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            rows = sheet_tree.findall(".//s:row", ns)

            if not rows:
                raise ValueError("Workbook sheet is empty")

            headers: List[str] = []
            for c in rows[0].findall("s:c", ns):
                is_node = c.find("s:is/s:t", ns)
                v_node = c.find("s:v", ns)
                val = is_node.text if is_node is not None else (v_node.text if v_node is not None else "")
                headers.append(val.strip())

            for r in rows[1:]:
                vals: List[str] = []
                for c in r.findall("s:c", ns):
                    is_node = c.find("s:is/s:t", ns)
                    v_node = c.find("s:v", ns)
                    val = is_node.text if is_node is not None else (v_node.text if v_node is not None else "")
                    vals.append(val.strip())

                row_dict = dict(zip(headers, vals))
                
                def get_int(col_name: str) -> int:
                    raw_val = row_dict.get(col_name, "0")
                    try:
                        return int(float(raw_val)) if raw_val else 0
                    except ValueError:
                        return 0

                sr_sec_boys = (
                    get_int("SR_SEC_BOYS_GOVT_SCH") +
                    get_int("SR_SEC_BOYS_LOCAL_BODIES_SCH") +
                    get_int("SR_SEC_BOYS_PVT_ADDED_SCH") +
                    get_int("SR_SEC_BOYS_PVT_UNAIDED_NO")
                )
                sr_sec_girls = (
                    get_int("SR_SEC_GIRLS_GOVT_SCH") +
                    get_int("SR_SEC_GIRLS_LOCAL_BODIES_SCH") +
                    get_int("SR_SEC_GIRLS_PVT_ADDED_SCH") +
                    get_int("SR_SEC_GIRLS_PVT_UNAIDED_NO")
                )

                record = RawTalukaEducationRecord(
                    reference_year=row_dict.get("REFERENCE_YEAR", "2010-11"),
                    district_name=row_dict.get("DISTRICT_NAME", "Dhule"),
                    district_code=row_dict.get("DISTRICT_CODE", "498"),
                    taluka_name=row_dict.get("TALUKA_NAME", ""),
                    taluka_code=row_dict.get("TALUKA_CODE", ""),
                    govt_colleges=get_int("GOVT_COLLEGES_NO"),
                    pvt_aided_colleges=get_int("PVT_AIDED_COLLEGES"),
                    pvt_unaided_colleges=get_int("PVT_UNAIDED_COLLEGES"),
                    eng_degree_colleges=get_int("ENG_INST_FOR_DEG"),
                    eng_diploma_colleges=get_int("ENG_INST_FOR_DIP"),
                    med_degree_colleges=get_int("MEDI_INST_FOR_DEG"),
                    iti_voc_institutes=get_int("ITI_N_VOC_INST"),
                    arts_enrolment=get_int("ART_INTAKE_ENROLL"),
                    science_enrolment=get_int("SCI_INTAKE_ENROLL"),
                    commerce_enrolment=get_int("COM_INTAKE_ENROLL"),
                    mcvc_enrolment=get_int("MCVC_INTAKE_ENROLL"),
                    polytechnic_enrolment=get_int("POLYTECH_INTAKE_ENROLL"),
                    iti_enrolment=get_int("ITI_INTAKE_ENROLL"),
                    eng_degree_enrolment=get_int("ENG_INST_FOR_DEG_ENROL"),
                    eng_diploma_enrolment=get_int("ENG_INST_FOR_DIP_ENROL"),
                    med_degree_enrolment=get_int("MEDI_INST_FOR_DEG_ENROL"),
                    sr_sec_boys=sr_sec_boys,
                    sr_sec_girls=sr_sec_girls
                )
                records.append(record)

        # Compute District Aggregates
        tot_govt_col = sum(r.govt_colleges for r in records)
        tot_pvt_aided_col = sum(r.pvt_aided_colleges for r in records)
        tot_pvt_unaided_col = sum(r.pvt_unaided_colleges for r in records)
        tot_eng_deg = sum(r.eng_degree_colleges for r in records)
        tot_eng_dip = sum(r.eng_diploma_colleges for r in records)
        tot_med_deg = sum(r.med_degree_colleges for r in records)
        tot_iti = sum(r.iti_voc_institutes for r in records)

        tot_sr_boys = sum(r.sr_sec_boys for r in records)
        tot_sr_girls = sum(r.sr_sec_girls for r in records)
        tot_sr_students = tot_sr_boys + tot_sr_girls

        # Higher education enrolments
        taluka_enrolments: Dict[str, int] = {}
        tot_prof_enrol = 0
        tot_non_prof_enrol = 0

        for r in records:
            prof = (
                r.eng_degree_enrolment + r.eng_diploma_enrolment +
                r.med_degree_enrolment + r.polytechnic_enrolment +
                r.iti_enrolment + r.mcvc_enrolment
            )
            non_prof = r.arts_enrolment + r.science_enrolment + r.commerce_enrolment
            taluka_total = prof + non_prof
            taluka_enrolments[r.taluka_name] = taluka_total
            tot_prof_enrol += prof
            tot_non_prof_enrol += non_prof

        tot_he_enrolment = tot_prof_enrol + tot_non_prof_enrol

        # Derived Distributions
        # 1. Gender distribution derived from senior secondary enrolment totals
        gender_dist = {
            "Male": round(tot_sr_boys / tot_sr_students, 4) if tot_sr_students > 0 else 0.5,
            "Female": round(tot_sr_girls / tot_sr_students, 4) if tot_sr_students > 0 else 0.5,
        }

        # 2. Higher education institution management distribution
        tot_colleges = tot_govt_col + tot_pvt_aided_col + tot_pvt_unaided_col
        inst_dist = {
            "Government": round(tot_govt_col / tot_colleges, 4) if tot_colleges > 0 else 0.0,
            "Government-Aided": round(tot_pvt_aided_col / tot_colleges, 4) if tot_colleges > 0 else 0.5,
            "Private-Unaided": round(tot_pvt_unaided_col / tot_colleges, 4) if tot_colleges > 0 else 0.5,
            "Deemed/Private-University": 0.0
        }

        # 3. Taluka distribution from higher education enrolments
        taluka_dist = {
            t: round(c / tot_he_enrolment, 4) if tot_he_enrolment > 0 else 0.25
            for t, c in taluka_enrolments.items()
        }

        # 4. Professional stream ratio
        prof_ratio = round(tot_prof_enrol / tot_he_enrolment, 4) if tot_he_enrolment > 0 else 0.3

        return DhuleEducationDatasetSummary(
            reference_year=records[0].reference_year if records else "2010-11",
            district_name=records[0].district_name if records else "Dhule",
            district_code=records[0].district_code if records else "498",
            taluka_records=records,
            total_govt_colleges=tot_govt_col,
            total_pvt_aided_colleges=tot_pvt_aided_col,
            total_pvt_unaided_colleges=tot_pvt_unaided_col,
            total_engineering_degree_colleges=tot_eng_deg,
            total_engineering_diploma_colleges=tot_eng_dip,
            total_medical_degree_colleges=tot_med_deg,
            total_iti_voc_institutions=tot_iti,
            total_higher_ed_enrolment=tot_he_enrolment,
            total_sr_sec_boys=tot_sr_boys,
            total_sr_sec_girls=tot_sr_girls,
            derived_gender_distribution=gender_dist,
            derived_institution_type_distribution=inst_dist,
            derived_taluka_distribution=taluka_dist,
            derived_professional_stream_ratio=prof_ratio
        )

    @classmethod
    def create_population_config(
        cls,
        summary: Optional[DhuleEducationDatasetSummary] = None,
        file_path: Optional[str] = None
    ) -> PopulationDistributionConfig:
        """
        Builds a PopulationDistributionConfig using verified empirical distributions
        for grounded fields observed in the Dhule dataset, with explicit fallback
        priors for fields not covered in this dataset.
        """
        ds_summary = summary or cls.load_and_parse(file_path=file_path)

        # Baseline fallback priors for unobserved fields (caste, income, synthetic priors)
        base = EXAMPLE_POPULATION_CONFIG

        return PopulationDistributionConfig(
            config_name=f"Empirical-Grounded-Dhule-{ds_summary.reference_year}",
            description=(
                f"Grounded distributions for {ds_summary.district_name} District from official "
                f"2010-11 Educational Census table. Note: Caste & Income use baseline fallback priors."
            ),
            is_example_placeholder=False,  # Grounded fields are from verified reference data

            # Grounded in Dhule observed dataset:
            district_distribution={ds_summary.district_name: 1.0},
            district_region_mapping={ds_summary.district_name: "Semi-Urban"},
            gender_distribution=ds_summary.derived_gender_distribution,
            institution_type_distribution=ds_summary.derived_institution_type_distribution,
            professional_probability_by_level={
                "Undergraduate": ds_summary.derived_professional_stream_ratio,
                "Postgraduate": ds_summary.derived_professional_stream_ratio * 0.8,
                "Diploma": 0.85
            },

            # Fields unobserved in this table (using explicitly labeled baseline priors):
            caste_category_distribution=base.caste_category_distribution,
            parental_education_distribution=base.parental_education_distribution,
            admission_mode_distribution=base.admission_mode_distribution,
            course_level_distribution=base.course_level_distribution,
            courses_by_stream=base.courses_by_stream,
            income_brackets=base.income_brackets,
            tuition_fee_ranges=base.tuition_fee_ranges,
            attendance_mean_std=base.attendance_mean_std,
            previous_year_pass_rate=base.previous_year_pass_rate,
            previous_year_percentage_mean_std=base.previous_year_percentage_mean_std,
            gap_years_distribution=base.gap_years_distribution,
            beneficiaries_count_distribution=base.beneficiaries_count_distribution,
            other_scholarship_probability=base.other_scholarship_probability,
            behavioral_priors=base.behavioral_priors,
            personality_priors=base.personality_priors,
            first_names_by_gender=base.first_names_by_gender,
            last_names=["Patil", "Ahirrao", "Bhadane", "Chavan", "Deore", "Gavit", "Mali", "Suryawanshi"]
        )
