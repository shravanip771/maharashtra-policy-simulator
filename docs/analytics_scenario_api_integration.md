# Analytics and Scenario Engine API Integration Specification

**Module:** Policy Simulation Analytics (`simulation/analytics.py`) & Scenario Engine (`simulation/scenarios.py`)
**Project:** Maharashtra Policy Simulator
**Branch:** `feature/analytics-scenarios`
**Audience:** Backend Engineers, API Integration Developers, Policy Analysts

---

## 1. Executive Summary & Purpose

This document specifies the integration contract and serialization schema for exposing the **Policy Simulation Analytics Engine** and **Counterfactual Scenario Engine** via future FastAPI backend endpoints.

The simulation and scenario engines produce rich, typed dataclass outputs:
- `AnalyticsReport`: Comprehensive evaluation of baseline or realized multi-step simulation cohorts.
- `ScenarioComparisonReport`: Comparative analysis contrasting a baseline cohort against an identical counterfactual cohort subjected to targeted policy interventions (Awareness Campaigns, Documentation Assistance, or Institutional Support).

Both reports provide built-in serialization methods (`.to_dict()` and `.to_json()`) engineered specifically for REST API integration, strict RFC 8259 compliance, and deterministic analytical transparency.

---

## 2. Core Data Models and Methods

### 2.1 `AnalyticsReport`

Located in `simulation/analytics.py`, `AnalyticsReport` encapsulates complete population, funnel, benefit, demographic, and state distributions:

```python
@dataclass
class AnalyticsReport:
    cohort_name: str
    total_personas: int
    awareness_threshold: float
    population_and_eligibility: PopulationEligibilityMetrics
    awareness_and_application: AwarenessApplicationMetrics
    benefits: BenefitMetrics
    administrative_lifecycle: AdministrativeLifecycleStatus
    breakdowns: Dict[str, Dict[str, Dict[str, Any]]]
    ineligibility_reasons: Dict[str, int]
    methodological_notes: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Converts the analytics report into a clean, nested dictionary."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Serializes the analytics report to a structured JSON string, disallowing NaN/Infinity."""
        return json.dumps(self.to_dict(), indent=indent, default=str, allow_nan=False)
```

#### Key Sub-Structures:
- `population_and_eligibility`:
  - `total_personas`: Integer total cohort count ($N$).
  - `eligible_count`: Personas satisfying statutory eligibility criteria (Rajarshi Shahu EBC rules).
  - `ineligible_count`: Personas failing one or more statutory criteria.
  - `eligibility_rate`: Float rounded to 4 decimals ($\frac{\text{eligible}}{\text{total}}$).
  - `eligibility_percentage`: Float rounded to 2 decimals ($100 \times \text{eligibility\_rate}$).
- `awareness_and_application`:
  - `aware_count` / `awareness_rate`: Personas with `awareness_score >= awareness_threshold` (default threshold 0.50).
  - `attempted_application_count` / `application_attempt_rate`: Personas attempting application.
  - `eligible_attempted_count` / `eligible_application_attempt_rate`: Eligible personas attempting application ($\frac{\text{eligible\_attempted}}{\text{eligible\_count}}$).
  - `completed_application_count` / `application_completion_rate`: Personas successfully completing submission ($\frac{\text{completed}}{\text{attempted}}$).
- `benefits`:
  - `benefit_received_count` / `benefit_recipient_rate`: Realized beneficiaries ($B$).
  - `eligible_benefit_recipient_count` / `eligible_benefit_recipient_rate`: Realized eligible beneficiaries ($\frac{B_{\text{eligible}}}{\text{eligible\_count}}$).
  - `total_estimated_fee_relief_inr`: Sum of estimated fee relief for realized recipients ($INR$).
  - `total_cohort_statutory_relief_inr`: Sum of statutory fee relief across all eligible personas regardless of uptake ($INR$).
  - `average_fee_relief_per_eligible_inr`: $\frac{\text{total\_cohort\_statutory\_relief\_inr}}{\text{eligible\_count}}$.
  - `average_estimated_fee_relief_per_recipient_persona_inr`: $\frac{\text{total\_estimated\_fee\_relief\_inr}}{\text{benefit\_received\_count}}$.
- `administrative_lifecycle`:
  - `status`: `"UNAVAILABLE"`
  - `is_available`: `False`
  - Explicit warning detailing that administrative lifecycle records cannot be fabricated from simulation states.
- `breakdowns`:
  - Sliced across `"district"`, `"gender"`, `"caste_category"`, `"institution_type"`, and `"final_simulation_state"`.
- `ineligibility_reasons`:
  - Frequency distribution of statutory failure rules (e.g. `INCOME_EXCEEDS_LIMIT`, `NON_CAP_ADMISSION`, `LOW_ATTENDANCE`).

---

### 2.2 `ScenarioComparisonReport`

Located in `simulation/scenarios.py`, `ScenarioComparisonReport` contains the results of paired counterfactual simulation runs:

```python
@dataclass
class ScenarioComparisonReport:
    scenario_name: str
    intervention: ScenarioIntervention
    total_personas: int
    seed: Optional[int]
    assumed_reimbursement_rate: Optional[float]
    awareness_threshold: float
    baseline_analytics: AnalyticsReport
    intervention_analytics: AnalyticsReport
    deltas: ScenarioDeltaMetrics
    epistemic_disclaimer: str = DEFAULT_EPISTEMIC_DISCLAIMER
    methodological_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Converts the comparison report into a clean, nested dictionary."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Serializes the report to structured JSON, disallowing NaN/Infinity."""
        return json.dumps(self.to_dict(), indent=indent, default=str, allow_nan=False)
```

#### Key Sub-Structures:
- `intervention`:
  - `intervention_type`: `"AWARENESS_CAMPAIGN"`, `"DOCUMENTATION_ASSISTANCE"`, or `"INSTITUTIONAL_SUPPORT"`.
  - `name`: Human-readable label.
  - Parameter bounds: Targeted delta and optional floor applied to persona attributes.
- `baseline_analytics` & `intervention_analytics`:
  - Full `AnalyticsReport` instances for baseline and counterfactual runs.
- `deltas` (`ScenarioDeltaMetrics`):
  - Invariant statutory deltas: `eligible_count_delta == 0`, `ineligible_count_delta == 0`.
  - Behavioral funnel shifts: `aware_count_delta`, `attempted_application_count_delta`, `completed_application_count_delta`, `benefit_received_count_delta`.
  - Uptake shifts:
    - `uptake_percentage_point_delta`: Absolute percentage point change ($pp = (\text{interv\_rate} - \text{base\_rate}) \times 100$). Always finite.
    - `relative_uptake_growth_percentage`: Relative growth ($((\text{interv} - \text{base}) / \text{base}) \times 100$). Strictly `null` (`None`) when baseline recipients are zero.

---

## 3. RFC 8259 Compliance & Safe Serialization

Both engines strictly enforce JSON standards (RFC 8259):

1. **Disallowance of Non-Standard Floats (`allow_nan=False`):**
   - Standard JSON specifications do not support `NaN`, `Infinity`, or `-Infinity`.
   - In Python, `json.dumps(..., allow_nan=False)` raises a `ValueError` if any non-standard float is encountered.
   - All rates, averages, and deltas in `analytics.py` and `scenarios.py` are guarded against division by zero:
     - Zero denominators in rates return `0.0`.
     - Zero denominators in relative uptake growth return `None`, serializing directly to JSON `null`.
2. **Explicit `null` Representation:**
   - When baseline recipients are $0$, calculating relative growth $\frac{\text{interv} - 0}{0}$ is mathematically undefined.
   - In accordance with the system specification:
     ```json
     {
       "relative_uptake_growth_percentage": null
     }
     ```
   - API clients must inspect `relative_uptake_growth_percentage` for `null` and display `uptake_percentage_point_delta` (e.g. `+5.0 pp`) as the authoritative uptake change metric.
3. **Deterministic Numeric Rounding:**
   - Rates and probabilities are rounded to 4 decimal places (e.g., `0.7500`).
   - Percentages, percentage points, and currency values are rounded to 2 decimal places (e.g., `75.00`, `+5.00`, `150000.00`).

---

## 4. Administrative Lifecycle Non-Fabrication Rule

A critical architectural constraint in the Maharashtra Policy Simulator is the strict separation between:
1. **Citizen Cognitive Simulation State (`final_simulation_state`):**
   - Generated within `simulation/engine.py` / `simulation/agent.py`.
   - Represents student behavioral status (e.g., `AWARE`, `COLLECTING_DOCUMENTS`, `APPLIED`, `BENEFIT_RECEIVED`, `DROPPED_OUT`).
2. **Statutory Administrative Application Lifecycle (`ApplicationLifecycleStatus`):**
   - Managed within `backend/lifecycle_service.py` and persisted in `backend/database.py`.
   - Represents legally binding government file progress (e.g., `DRAFT`, `SUBMITTED`, `UNDER_VERIFICATION`, `APPROVED`, `REJECTED`, `BENEFIT_DISBURSED`).

### Why Lifecycle Metrics are Reported as `UNAVAILABLE`

`SimulationStepOutput` and `CohortSimulationResult` record the cognitive behavior of student agents during the simulation run. They do **not** reflect official administrative scrutiny workflows or desk officer decisions:
- A student reaching behavioral state `APPLIED` has not yet been processed by an administrative verification officer.
- Inferring administrative metrics (`submitted_count`, `under_verification_count`, `approved_count`, `administratively_rejected_count`, `sent_back_count`) from agent psychological readiness would violate administrative realism and fabricate official government records.
- Consequently, `AnalyticsReport.administrative_lifecycle` is explicitly populated as:
  ```json
  {
    "administrative_lifecycle": {
      "status": "UNAVAILABLE",
      "is_available": false,
      "message": "Administrative lifecycle statuses (such as SUBMITTED, UNDER_VERIFICATION, APPROVED, REJECTED, SENT_BACK) are not exposed by the SimulationStepOutput schema. These statuses represent administrative records in the application lifecycle service and must not be inferred from behavioral simulation states (final_simulation_state).",
      "unavailable_metrics": [
        "submitted_count",
        "under_verification_count",
        "approved_count",
        "administratively_rejected_count",
        "sent_back_count"
      ]
    }
  }
  ```

---

## 5. Epistemic Guardrails & Decision-Support Caveats

Outputs from the Scenario Engine are counterfactual exploratory estimations designed for policy sensitivity analysis, not guaranteed empirical predictions or treasury expenditure mandates.

Every `ScenarioComparisonReport` includes the default epistemic disclaimer:
> *"Scenario comparison results are synthetic counterfactual estimates generated by agent-based behavioral simulation. They indicate directional sensitivity under modeled behavioral assumptions, not empirical real-world forecasts or guaranteed statutory outcomes. Administrative processing, budget caps, and external shocks are not modeled in these deltas."*

### Key Analytical Safeguards:
1. **Statutory Invariance:**
   - Interventions alter behavioral attributes (`initial_awareness`, `document_readiness`, `institutional_trust`).
   - Interventions **never** alter family income, admission quota, caste category, or statutory criteria.
   - `deltas.eligible_count_delta` and `deltas.ineligible_count_delta` are guaranteed to equal `0`.
2. **Proof-of-Concept 50% Reimbursement Assumption:**
   - In accordance with the project specification, baseline simulations default to an assumed 50% fee reimbursement rate when not explicitly supplied.
   - When applicable, reports append an explicit methodological note alerting the user to this assumption.
3. **Institutional Trust Independence:**
   - In the current behavioral model, `institutional_trust` contributes to conversational peer diffusion and qualitative LLM dialogue, but deterministic application attempt probability is governed primarily by perceived financial benefit versus document hassle.
   - Reports applying `Institutional Support` interventions document this caveat explicitly in `methodological_notes`.

---

## 6. FastAPI Endpoint Blueprints

Future FastAPI routes in `backend/` can expose these analytics capabilities cleanly without coupling to internal simulation mechanics.

### 6.1 `POST /api/simulate/analytics`

Analyzes an existing simulation run or cohort result.

#### Request Schema:
```json
{
  "simulation_run_id": "RUN-20261122-PUNE-001",
  "awareness_threshold": 0.50
}
```

#### Route Implementation Pattern:
```python
@router.post("/api/simulate/analytics", response_model=Dict[str, Any])
async def get_simulation_analytics(
    payload: AnalyticsRequestSchema,
    db: Session = Depends(get_db)
):
    # 1. Fetch simulation run from database
    run_record = db.query(SimulationRun).filter(SimulationRun.id == payload.simulation_run_id).first()
    if not run_record:
        raise HTTPException(status_code=404, detail="Simulation run not found")

    # 2. Reconstruct or retrieve CohortSimulationResult
    cohort_result = run_record.to_cohort_result()

    # 3. Compute analytics using PolicySimulationAnalytics
    report: AnalyticsReport = PolicySimulationAnalytics.analyze_cohort(
        cohort=cohort_result,
        awareness_threshold=payload.awareness_threshold
    )

    # 4. Return clean, RFC 8259-compliant dictionary
    return JSONResponse(content=report.to_dict())
```

---

### 6.2 `POST /api/scenarios/compare`

Runs a counterfactual scenario comparison against a grounded district cohort.

#### Request Schema:
```json
{
  "district": "Pune",
  "cohort_size": 50,
  "seed": 42,
  "intervention": {
    "type": "AWARENESS_CAMPAIGN",
    "name": "Pune Mission Awareness 2026",
    "delta": 0.25,
    "floor": 0.40
  },
  "awareness_threshold": 0.50,
  "assumed_reimbursement_rate": 0.50
}
```

#### Route Implementation Pattern:
```python
@router.post("/api/scenarios/compare", response_model=Dict[str, Any])
async def run_scenario_comparison_endpoint(
    payload: ScenarioCompareRequestSchema
):
    try:
        # 1. Generate grounded district cohort
        generator = SyntheticPersonaGenerator.for_district(payload.district, seed=payload.seed)
        cohort = generator.generate_cohort(count=payload.cohort_size, seed=payload.seed)

        # 2. Build scenario intervention with strict parameter validation
        engine = ScenarioEngine()
        if payload.intervention.type == "AWARENESS_CAMPAIGN":
            intervention = engine.create_awareness_campaign(
                name=payload.intervention.name,
                delta=payload.intervention.delta,
                floor=payload.intervention.floor
            )
        elif payload.intervention.type == "DOCUMENTATION_ASSISTANCE":
            intervention = engine.create_documentation_assistance(
                name=payload.intervention.name,
                delta=payload.intervention.delta,
                floor=payload.intervention.floor
            )
        elif payload.intervention.type == "INSTITUTIONAL_SUPPORT":
            intervention = engine.create_institutional_support(
                name=payload.intervention.name,
                doc_delta=payload.intervention.doc_delta,
                trust_delta=payload.intervention.trust_delta,
                doc_floor=payload.intervention.doc_floor,
                trust_floor=payload.intervention.trust_floor
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported intervention type: {payload.intervention.type}")

        # 3. Execute scenario comparison
        report: ScenarioComparisonReport = engine.run_comparison(
            personas=cohort,
            intervention=intervention,
            cohort_name=f"{payload.district}-Counterfactual",
            seed=payload.seed,
            assumed_reimbursement_rate=payload.assumed_reimbursement_rate,
            awareness_threshold=payload.awareness_threshold
        )

        # 4. Return serialized comparison report
        return JSONResponse(content=report.to_dict())

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
```

---

## 7. Sample API Response Payloads

### 7.1 Scenario Comparison Sample Response (`POST /api/scenarios/compare`)

```json
{
  "scenario_name": "Pune-Counterfactual",
  "intervention": {
    "intervention_type": "AWARENESS_CAMPAIGN",
    "name": "Pune Mission Awareness 2026",
    "awareness_delta": 0.25,
    "awareness_floor": 0.4,
    "doc_readiness_delta": null,
    "doc_readiness_floor": null,
    "institutional_trust_delta": null,
    "institutional_trust_floor": null
  },
  "total_personas": 15,
  "seed": 42,
  "assumed_reimbursement_rate": 0.5,
  "awareness_threshold": 0.5,
  "deltas": {
    "eligible_count_delta": 0,
    "ineligible_count_delta": 0,
    "aware_count_delta": 4,
    "awareness_rate_delta": 0.2667,
    "attempted_application_count_delta": 3,
    "application_attempt_rate_delta": 0.2,
    "eligible_attempted_count_delta": 3,
    "eligible_application_attempt_rate_delta": 0.25,
    "completed_application_count_delta": 2,
    "application_completion_rate_delta": -0.0556,
    "benefit_received_count_delta": 2,
    "eligible_benefit_recipient_count_delta": 2,
    "benefit_recipient_rate_delta": 0.1333,
    "eligible_benefit_recipient_rate_delta": 0.1667,
    "total_estimated_fee_relief_inr_delta": 90000.0,
    "average_estimated_fee_relief_per_recipient_persona_inr_delta": 0.0,
    "uptake_percentage_point_delta": 13.33,
    "relative_uptake_growth_percentage": 50.0
  },
  "epistemic_disclaimer": "Scenario comparison results are synthetic counterfactual estimates generated by agent-based behavioral simulation. They indicate directional sensitivity under modeled behavioral assumptions, not empirical real-world forecasts or guaranteed statutory outcomes. Administrative processing, budget caps, and external shocks are not modeled in these deltas.",
  "methodological_notes": [
    "Assumed fee reimbursement rate: 50%.",
    "Awareness Campaign applied: delta=+0.25, floor=0.40."
  ]
}
```

---

## 8. Summary Checklist for API Developers

| Item | Requirement | Verification Status |
| :--- | :--- | :--- |
| **JSON Standard** | Strictly adhere to RFC 8259 (`allow_nan=False`). | Verified (`test_json_serialization_integrity`). |
| **Zero Uptake Growth** | When baseline recipients are $0$, `relative_uptake_growth_percentage` is strictly `null`. | Verified (`test_zero_baseline_recipients_relative_growth_none`). |
| **Statutory Invariance** | `eligible_count_delta == 0` across all counterfactual scenarios. | Verified (`test_statutory_eligibility_preserved_across_interventions`). |
| **Persona Isolation** | Original persona objects are cloned via `copy.deepcopy` and never mutated. | Verified (`test_original_personas_not_mutated`). |
| **Lifecycle Transparency** | Administrative metrics must remain `UNAVAILABLE`; never infer them from `final_simulation_state`. | Verified (`test_unavailable_administrative_lifecycle_statuses_not_fabricated`). |
| **Offline Safety** | All engine operations run completely offline using `StubLLMProvider` without network or Gemini calls. | Verified (`test_offline_execution_stub_llm_provider`). |
