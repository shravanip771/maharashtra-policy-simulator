# Directorate of Technical Education (DTE) Maharashtra: Scholarship Policy Rules Reference

**Scheme Name:** Rajarshi Chhatrapati Shahu Maharaj Shikshan Shulk Shishyavrutti Yojna (EBC Scheme)
**Department:** Higher & Technical Education Department, Government of Maharashtra
**Implementing Directorate:** Directorate of Technical Education (DTE), Maharashtra State
**Application Portal:** MahaDBT (`mahadbt.maharashtra.gov.in`)
**Scope:** Single-Scheme Evaluation (Rajarshi Chhatrapati Shahu Maharaj EBC Scheme only). Cross-departmental scholarship discovery or alternative routing is **not** implemented.
**Policy Version:** `2024.1-provisional`
**Default Verification Status:** `PROVISIONAL` (Awaiting local archival of primary Government Resolution PDFs)

---

## 1. Epistemic Provenance and Classification Framework

To guarantee simulation integrity, eliminate hallucinations, and maintain strict scientific audit standards, all policy parameters and rules are governed by three epistemic provenance tiers:

| Status Tier | Definition & Evidentiary Standard | Current Project Application |
| :--- | :--- | :--- |
| **VERIFIED** | Directly confirmed against an official primary Government Resolution (शासन निर्णय - GR) PDF or official State Gazette text **physically stored and verified locally within the workspace**. | Currently **zero** rules qualify as `VERIFIED` because no primary government gazette PDFs are stored locally on disk. |
| **PROVISIONAL** | Strongly supported by administrative circulars, university guidelines, college fee notices, or official portal workflow manuals, but awaiting primary gazette PDF archiving in the repository. | **All candidate statutory rules, income thresholds, and benefit concession schedules** are classified as `PROVISIONAL`. |
| **UNVERIFIED** | Simulation priors, secondary assumptions, or speculative claims lacking direct government citations. Must remain configurable and explicitly identified. | Candidate hypotheses (e.g. female sibling exemption from the 2-child limit) are marked `UNVERIFIED` / refuted. |

> [!IMPORTANT]
> All referenced Government Resolution (GR) numbers—including GR No. शिष्यवृ-२०२४/प्र.क्र.१०५/तांशि-४ (08.07.2024), GR No. टीईएम-२०१८/प्र.क्र.३५/तांशि-४ (31.03.2018), and GR No. टीईएम-२०१६/प्र.क्र.५५९/तांशि-४ (15.04.2017)—are treated strictly as **unverified research references** pending local document archival.

---

## 2. DTE Scheme Statutory Eligibility Gatekeepers

The DTE Rajarshi Chhatrapati Shahu Maharaj scheme enforces an atomic **8-rule statutory check contract**. All checks return a boolean satisfaction flag, the observed value, the statutory condition, diagnostic messaging, and the epistemic status. Missing statutory attributes fail safely and cannot result in silent approval.

### Strict Input Type & Value Validation
- **Numeric Fields:** `family_income`, `attendance_percentage`, `academic_gap_years`, and `family_beneficiaries_count` strictly require finite numeric types. Booleans (`True`/`False`), non-numeric types, strings, `NaN`, and `Infinity` are rejected and fail eligibility with explicit diagnostics.
- **Negative Values:** Disallowed for all statutory counts, income, and percentages.
- **Whole Integers:** `academic_gap_years` and `family_beneficiaries_count` must be non-negative whole integers.

| Rule ID | Rule Domain | Policy Requirement | Epistemic Status | Authoritative Reference (Research Prior) |
| :--- | :--- | :--- | :---: | :--- |
| **DTE-STAT-01** | **Maharashtra Domicile** | Applicant must be an Indian National and a resident Domicile of Maharashtra State (valid Domicile Certificate issued by Tahsildar / Sub-Divisional Officer). Students belonging to the 865 Maharashtra-Karnataka disputed border villages qualify with border area certificate. Missing or non-boolean domicile fails eligibility. | **PROVISIONAL** | GR No. TEM-2018/C.R.35/TE-4; MahaDBT Eligibility Rules |
| **DTE-STAT-02** | **Family Income Ceiling** | Total annual family income from all sources must not exceed **₹8,00,000 (INR 8 Lakh)**. Must be certified by an authorized Tahsildar / SDO digital certificate. Missing, boolean, string, non-finite (NaN/Inf), or negative income fails eligibility. | **PROVISIONAL** | GR No. TEM-2018/C.R.35/TE-4 (31 March 2018) |
| **DTE-STAT-03** | **CAP Admission Route** | For professional / technical courses, admission must be strictly secured through the **Centralized Admission Process (CAP)** conducted by the State CET Cell / DTE. Non-professional general merit courses are exempt. Management Quota and Institute Level seats are disqualified. Missing admission mode fails for professional courses. | **PROVISIONAL** | DTE Admission Rules; GR TEM-2016/C.R.559/TE-4 |
| **DTE-STAT-04** | **Eligible Institutions** | Approved Government, Government-Aided, University Departments, Autonomous Colleges, and recognized Private Un-aided colleges participating in CAP and affiliated to state public universities or MSBTE. Deemed Universities and State Private Universities are statutorily excluded. Missing institution type fails eligibility. | **PROVISIONAL** | MahaDBT Institution Registry; AICTE/PCI Approval Lists |
| **DTE-STAT-05** | **Sibling / Beneficiary Limit** | In the current academic year, **maximum 2 children / beneficiaries from the same family** can claim this scheme or related state fee concessions. Requires mandatory signed undertaking (*Pratidnya Patra*). Applicant family must have `< 2` existing beneficiaries. Missing, non-integer, or negative count fails eligibility. | **PROVISIONAL** | MahaDBT Mandatory Upload Form; GR TEM-2016/C.R.559/TE-4 |
| **DTE-STAT-06** | **Attendance Threshold** | Mandatory institutional attendance showing **minimum 50.0% attendance** in the previous semester/term (or 75.0% institutional baseline if configured). Missing, non-numeric, or out-of-range ($<0\%$ or $>100\%$) attendance on continuing students fails eligibility. | **PROVISIONAL** | MahaDBT Scheme Data & Eligibility Specification |
| **DTE-STAT-07** | **First-Year Attendance Exemption** | Fresh newly admitted 1st year students are statutorily **exempted** from submitting previous semester attendance proof for their initial application. | **PROVISIONAL** | MahaDBT Eligibility Manual & Scrutiny Directive |
| **DTE-STAT-08** | **Academic Progression & Gap Limit** | **Reconciled Behavior:**<br>1. *Continuing Students (`is_first_year=False`):* Must have passed the previous academic college year (`previous_year_passed=True`). Missing (`None`), `False`, or non-boolean fails.<br>2. *First-Year Entrants (`is_first_year=True`):* Must have cleared the 12th/diploma qualifying examination for admission (`previous_year_passed=True`). Missing (`None`), `False`, or non-boolean fails.<br>3. *Gap Limit:* Total educational gap across course must be a non-negative whole integer $\le$ **2 years**. Gap $> 2$ fails. | **PROVISIONAL** | MahaDBT Qualification Form & Scrutiny Guidelines |
| **DTE-STAT-09** | **Concurrent Scholarship Prohibition** | Student cannot simultaneously avail of duplicate fee waivers or maintenance allowances from other state or central government scholarship schemes for the same course. Missing or non-boolean flag fails eligibility. | **PROVISIONAL** | MahaDBT General Terms & Conditions |

---

## 3. Benefit & Fee Reimbursement Schedule

Benefits are calculated on approved instructional fees only: instructional **Tuition Fees** and university **Examination Fees**. Non-instructional fees (Development fees, Gymkhana, Caution Money, Mess/Hostel charges) are strictly excluded.

**Guarantees:**
1. **Strict Ineligibility Clamping:** If an applicant fails any statutory criterion, total estimated fee relief is strictly **₹0.00**, and the reimbursement percentage is **0.0%**.
2. **Pre-Breakdown Fee Sanitization (Stage 2.2.1 Hotfix):** `annual_tuition_fee` and `annual_exam_fee` are sanitized before constructing `FeeComponentBreakdown` across **both eligible and ineligible** paths. Early returns cannot bypass monetary validation.
3. **Monetary Field Invariants:** Every monetary and rate field inside `FeeComponentBreakdown` is strictly numeric (`float`), finite (not `NaN`, not $\pm\infty$), non-negative ($\ge 0.0$), and not a boolean. Invalid inputs (numeric/arbitrary strings, booleans `True`/`False`, `NaN`, $\pm\infty$, negative numbers, or `None`) safely default to **₹0.00** without causing crashes or altering statutory eligibility.
4. **Component Separation:** Tuition relief and exam relief are calculated independently and clamped to their respective assessed fees.
5. **Safe Fee Sanitization:** Non-numeric, boolean, non-finite (`NaN`/`Inf`), negative, zero, or missing fees are safely clamped to ₹0.00 with explicit diagnostic notices in `missing_fee_notes`.

| Beneficiary Category | Family Annual Income | Institution Type | Reimbursable Tuition Fee % | Reimbursable Exam Fee % | Status | Reference (Research Prior) |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| **Female Student** | Up to ₹8,00,000 | Government / Govt-Aided | **100%** | **100%** | **PROVISIONAL** | Research Ref: GR No. शिष्यवृ-२०२४/प्र.क्र.१०५/तांशि-४ (08.07.2024) |
| **Female Student** | Up to ₹8,00,000 | Private Un-aided | **100%** | **100%** | **PROVISIONAL** | Research Ref: GR No. शिष्यवृ-२०२४/प्र.क्र.१०५/तांशि-४ (08.07.2024) |
| **Orphan Student** | Up to ₹8,00,000 | Govt / Aided / Unaided | **100%** | **100%** | **PROVISIONAL** | Research Ref: GR No. शिष्यवृ-२०२४/प्र.क्र.१०५/तांशि-४ (08.07.2024) |
| **Male Student** | Up to ₹2,50,000 | Government / Govt-Aided | **100%** | **50%** | **PROVISIONAL** | Research Ref: GR No. टीईएम-२०१८/प्र.क्र.३५/तांशि-४ (31.03.2018) |
| **Male Student** | Up to ₹2,50,000 | Private Un-aided | **50%** | **50%** | **PROVISIONAL** | Research Ref: GR No. टीईएम-२०१८/प्र.क्र.३५/तांशि-४ (31.03.2018) |
| **Male Student** | ₹2,50,000 to ₹8,00,000 | Govt / Aided / Unaided | **50%** | **50%** | **PROVISIONAL** | Research Ref: GR No. टीईएम-२०१८/प्र.क्र.३५/तांशि-४ (31.03.2018) |
| **Any Student** | Above ₹8,00,000 | Any Institution Type | **0% (Ineligible)** | **0% (Ineligible)** | **PROVISIONAL** | Statutory ceiling (₹8,00,000) |

---

## 4. Finalized Engine-Facing Interface Specification

The DTE Policy Engine (`simulation/policy_rules.py`) serves as the **Single Source of Truth** for DTE scholarship statutory eligibility and financial benefit calculations. The Simulation Engine (`simulation/engine.py`) and AI Persona Agent (`simulation/agent.py`) consume its structured outputs.

### A. Evaluation Interface Method

```python
RajarshiShahuPolicyEngine.evaluate_eligibility(
    persona: StudentPersona,
    assumed_reimbursement_rate: Optional[float] = None,
    config: Optional[DTEPolicyConfig] = None
) -> PolicyEvaluationResult
```

### B. Input Attributes & Validation Rules

The method accepts a `StudentPersona` instance and optional configuration:

| Attribute | Type | Requirement / Description | Safe Handling of Invalid & Missing Data |
| :--- | :--- | :--- | :--- |
| `is_maharashtra_domicile` | `Optional[bool]` | Mandatory state domicile status | Must be `bool`. `None`, string, or number fails eligibility. |
| `family_income` | `Optional[float]` | Annual household income in INR | Must be finite number $\ge 0$. `None`, boolean, string, `NaN`, `Inf`, or $<0$ fails. |
| `is_professional_course` | `Optional[bool]` | Course nature (Technical/Professional vs General) | Defaults to `True` if omitted or non-bool. |
| `admission_mode` | `Optional[Union[AdmissionMode, str]]` | Admission path (CAP vs Management Quota) | `None` fails professional courses; passes general. |
| `institution_type` | `Optional[Union[InstitutionType, str]]` | College management status | `None` fails eligibility (unverifiable). |
| `family_beneficiaries_count` | `Optional[int]` | Existing family beneficiaries in current AY | Must be whole integer $\ge 0$. `None`, boolean, float, or $<0$ fails. |
| `has_other_scholarship` | `Optional[bool]` | Concurrent scholarship flag | Must be `bool`. `None`, string, or number fails eligibility. |
| `academic_gap_years` | `Optional[int]` | Total educational break years across course | Must be whole integer $\ge 0$. `None`, boolean, float, or $<0$ fails. |
| `previous_year_passed` | `Optional[bool]` | Prior examination clearance | Must be `bool` and `True`. `None`, `False`, string, or number fails both 1st-yr and continuing. |
| `attendance_percentage` | `Optional[float]` | Term-end institutional attendance percentage | Must be finite number in $[0.0, 100.0]$. `None`, boolean, `NaN`, `Inf`, or out-of-range fails continuing students; exempt for 1st yr. |
| `is_first_year` | `Optional[bool]` | Fresh admission flag for attendance exemption | Defaults to `False`. |
| `gender` | `Optional[str]` | Student gender (`"Female"` / `"Male"`) | Case-insensitive; defaults to male tier if missing. |
| `is_orphan` | `Optional[bool]` | Orphan status flag | Defaults to `False`. |
| `annual_tuition_fee` | `Optional[float]` | Annual instructional tuition fee in INR | Clamped: Non-numeric, boolean, `NaN`, `Inf`, $< 0$, or `None` $\rightarrow$ ₹0.00 relief. |
| `annual_exam_fee` | `Optional[float]` | Annual university examination fee in INR | Clamped: Non-numeric, boolean, `NaN`, `Inf`, $< 0$, or `None` $\rightarrow$ ₹0.00 relief. |
| `caste_category` | `Optional[str]` | Caste category name | Evaluated against `config.allowed_caste_categories` if set. |

### C. Override Parameter Validation (`assumed_reimbursement_rate`)
- **Normal Evaluator Call:** When `assumed_reimbursement_rate is None` (the default), the official deterministic DTE policy calculation executes without override.
- **Valid Explicit Overrides:** Must be a finite numeric value (`int` or `float`) between `0.0` and `1.0` inclusive.
- **Strict Invalid Rejection:** If an explicit override is passed as a boolean (`True`/`False`), string, `NaN`, `Infinity`, $< 0.0$, or $> 1.0$, the engine **fails safely**, issues diagnostics in `statutory_notes` and `indeterminate_reasons`, and sets the relief to **₹0.00** rather than silently applying an invalid rate or falling back to a default.

### D. Output Data Contract (`PolicyEvaluationResult`)

The method returns a structured, immutable dataclass containing full statutory and financial details:

```python
@dataclass
class PolicyEvaluationResult:
    scheme_name: str                           # Scheme display name
    is_eligible: bool                          # Statutory eligibility decision (True / False)
    reimbursement_percentage: float            # Blended effective relief rate (Total Relief / Assessed Fees)
    estimated_fee_relief_inr: float            # Total monetary benefit amount (Tuition + Exam Relief)
    rule_checks: List[RuleCheckResult]         # Exactly 8 rule checks with observed values and criteria
    failure_reasons: List[str]                 # Human-readable list of statutory disqualifications
    statutory_notes: List[str]                 # Regulatory audit trail and applied provisions
    benefit_assumptions: List[str]             # Epistemic assumptions used in calculation
    tuition_fee_relief_inr: float              # Itemized monetary relief for tuition fees
    exam_fee_relief_inr: float                 # Itemized monetary relief for examination fees
    tuition_reimbursement_percentage: float    # Specific percentage applied to tuition fee (0.0 to 1.0)
    exam_reimbursement_percentage: float       # Specific percentage applied to examination fee (0.0 to 1.0)
    policy_version: str                        # Configuration version ("2024.1-provisional")
    verification_status: str                   # Epistemic tier ("PROVISIONAL")
    indeterminate_reasons: List[str]           # Specific attributes that were missing or invalid
    fee_breakdown: Optional[FeeComponentBreakdown] # Full itemized component breakdown object
    scholarship_route: str                     # Backward compatibility: "DTE_EBC" or "INELIGIBLE"
    alternate_scheme_name: Optional[str]       # None (Cross-department routing not implemented)
    routing_reason: Optional[str]              # None (Cross-department routing not implemented)
```

---

## 5. Unresolved Simulation Engine Integration Finding

### The Integration Disconnect
In `simulation/engine.py` (specifically within `run_cohort` lines 217–221 and `run_multistep_cohort_simulation` lines 348–352), the cohort execution workflow handles the reimbursement rate as follows:

```python
effective_rate = (
    assumed_reimbursement_rate
    if assumed_reimbursement_rate is not None
    else RajarshiShahuPolicyEngine.DEFAULT_POC_ASSUMED_REIMBURSEMENT_RATE # (0.50)
)
```

When cohort simulations run without an explicit `assumed_reimbursement_rate`, the Simulation Engine forces `effective_rate = 0.50` instead of passing `None` to `RajarshiShahuPolicyEngine.evaluate_eligibility()`.

### Impact
1. Passing `0.50` activates Caller Override Mode in the Policy Engine.
2. The Policy Engine applies a flat 50% rate across the entire cohort, **silently overriding the DTE Policy Engine's policy-specific calculations** (such as the female 100% concession and the male income/institution tiers).
3. The newly implemented deterministic policy logic executes for single-persona `run_step()` calls, but is suppressed during batch cohort runs.

### Mandatory Remediation Principles
1. **Single Source of Truth:** The DTE Policy Engine must be the single source of truth for policy-specific benefits. A generic simulation default (0.50) must never override a policy engine's calculated benefit.
2. **Interface Alignment Required:** In future stages, the Simulation Engine owner must update `simulation/engine.py` to allow `assumed_reimbursement_rate` to default to `None` in cohort runs, while providing an explicit flag for users who intentionally want to simulate historical PoC rate overrides.
3. **Task Boundary Compliance:** In accordance with task constraints, `simulation/engine.py` remained **strictly untouched** during this task.

---

## 6. Verified Test Suite Execution Summary (Stage 2.2.1)

All 8 automated test suites across the project have been executed and verified in the actual Python 3.13 runtime environment:

| Test Suite File | Domain / Scope | Test Functions | Execution Status | Exit Code |
| :--- | :--- | :---: | :---: | :---: |
| `simulation/test_dte_policy.py` | DTE Scholarship Policy Engine (Statutory criteria, benefit calculations, type safety, invalid fee handling on ineligible paths) | **29** | **PASSED** | 0 |
| `simulation/test_slice.py` | Phase 1 Simulation Vertical Slice & Single-Student Engine Integration | **3** | **PASSED** | 0 |
| `simulation/test_ai_persona_agent.py` | AI Persona LLM Reasoning, Prompt Injection Defense, Structured Output Guardrails | **6** | **PASSED** | 0 |
| `simulation/test_cohort_simulation.py` | 10-Persona Synthetic Cohort Execution & Aggregate Benefit Reconciliation | **4** | **PASSED** | 0 |
| `simulation/test_persona_generator.py` | Phase 2 Synthetic Persona Generator & Demographic Attribute Distributions | **6** | **PASSED** | 0 |
| `simulation/test_social_interaction.py` | Multi-Agent Social Graph Interactions & Deliberation Invariant Guardrails | **10** | **PASSED** | 0 |
| `backend/test_api.py` | FastAPI Application Endpoints, Scheme Queries, Contract Adherence | **4** | **PASSED** | 0 |
| `data/test_dhule_adapter.py` | Real Dhule District Empirical Data Adapter & Attribute Mapping | **3** | **PASSED** | 0 |
| **Total Project Test Count** | **Full Workspace Automated Test Suite** | **65** | **ALL PASSED** | **0** |
