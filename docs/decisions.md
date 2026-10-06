# Project Decisions: Maharashtra Policy Simulator

This document records approved architectural, domain, and technical decisions for the Maharashtra Policy Simulator, along with genuinely open items.

---

## 1. Project & Policy Domain

* **Status:** Approved
* **Decision:** AI-enhanced agent-based policy simulation for Maharashtra government education schemes.
* **Initial Policy Selected:** **Rajarshi Chhatrapati Shahu Maharaj Shikshan Shulk Shishyavrutti Yojna** (Higher & Technical Education EBC scholarship scheme).
* **Target Population:** College-going students across Maharashtra districts and demographic strata.

---

## 2. Simulation Scope & Mechanics

* **Status:** Approved
* **Target Scale for PoC / MVP:** Approximately 20 genuinely intelligent synthetic student personas.
* **Social / Peer Interaction:** Personas must support peer-to-peer and social interactions (e.g., word-of-mouth awareness, peer encouragement/discouragement).
* **Virtual Simulation Step Cycle:** Each discrete step follows:
  $$\text{Observe} \longrightarrow \text{Reason} \longrightarrow \text{Interact} \longrightarrow \text{Act} \longrightarrow \text{Update State}$$
* **Outputs & Outcomes:**
  * Both **individual** (per-persona path and barrier log) and **aggregate** (cohort-level rates and breakdowns) outcomes are required.
  * Outputs are **probabilistic estimates** reflecting simulated behavioural tendencies, not guarantees.

---

## 3. Hybrid Architecture (Deterministic Rules + AI Reasoning)

* **Status:** Approved
* **Core Principle:** Separation of quantitative mechanics from qualitative reasoning.
* **Deterministic / Python Code Responsibilities:**
  * Policy eligibility checks and statutory rule validation.
  * Deterministic scoring and probability calculations.
  * State transitions, simulation loop control, and data aggregation.
* **AI / LLM Responsibilities:**
  * Persona reasoning, personality fidelity, and dialogue/communication.
  * Contextual choices under uncertainty and natural-language explanations of barriers.
* **Anti-Pattern Constraint:** Do not use the LLM to invent numerical probabilities and subsequently invent arbitrary reasons for them.

---

## 4. Persona Pipeline & Evaluation

* **Status:** Approved
* **Pipeline Structure:**
  $$\text{Dataset Attributes} \longrightarrow \text{Synthetic Persona Profile} \longrightarrow \text{Personality / State / Memory} \longrightarrow \text{AI Persona Agent}$$
* **Evaluation Rule:** Each persona is evaluated individually. If relevant attributes differ, evaluate separately; identical relevant states may reuse cached evaluations to preserve compute.

---

## 5. Outcome Dimensions

* **Status:** Approved
* **Tracked Metrics per Persona / Cohort:**
  1. **Eligibility:** Statutory compliance with scheme criteria.
  2. **Awareness:** Knowledge of scheme existence and application requirements.
  3. **Perceived Benefit:** Subjective evaluation of fee relief vs. paperwork/effort.
  4. **Application Probability:** Likelihood of initiating the application.
  5. **Completion Probability:** Likelihood of overcoming administrative/document barriers.
  6. **Benefit / Uptake:** Final receipt of scholarship.
  7. **Explanations & Barriers:** Narrative reasoning of failure points (e.g., income certificate delay, portal complexity, lack of guidance).

---

## 6. Data Strategy & Transparency

* **Status:** Approved
* **Reference Data:** Use real/reference Maharashtra demographic and education statistics where available; use historical/reference data for the PoC when granular current data is unavailable.
* **Transparency & Labelling:** Clearly label all synthetic and modelled behavioural attributes. Synthetic variables must never be presented as real statistical facts.
* **Modelling Progression:** Start with a transparent weighted/probabilistic baseline. Supervised ML will be introduced later only if verified historical training data becomes available.

---

## 7. Technology Stack

* **Status:** Approved
* **Simulation Engine:** Python
* **Backend Framework:** FastAPI
* **Frontend Dashboard:** React + Vite
* **Database & ORM:** SQLite + SQLAlchemy (lightweight, zero-setup persistence for runs and persona states)
* **LLM Strategy:** Local / open-source LLM preferred (e.g., Ollama / GGUF); free cloud tier fallback if required. Target ₹0 infrastructure cost where possible.

---

## 8. Implementation Strategy

* **Status:** Approved
* **Progression:** 1 Persona (Vertical Slice) $\longrightarrow$ 10 Personas $\longrightarrow$ 20 Personas (Full MVP) $\longrightarrow$ Larger populations.
* **Vertical Slice Rule:** Build and validate one complete end-to-end slice before scaling persona counts or UI complexity.

---

## 9. Open / Unresolved Items

* **Status:** Open / Under Research
1. **Specific Local LLM Engine & Model Size:** Selection of the exact quantized model (e.g., Llama-3-8B / Mistral / Qwen) and serving method (Ollama vs. local runtime vs. API fallback).
2. **Reference Dataset Files:** Finalizing exact CSV/JSON schemas for Maharashtra district-level college demographics.
3. **Historical Validation Dataset:** Identifying official scheme audit/disbursement reports to benchmark simulated uptake against historical actuals.
