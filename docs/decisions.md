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

## 9. Multi-Persona Social Interaction & Multi-Step Architecture

* **Status:** Approved
* **Context:** To model peer-to-peer diffusion, word-of-mouth awareness, and informational nudges for government scholarship uptake, personas need reproducible social interactions without unrealistic all-to-all communication or unbounded state drift.
* **Decisions:**
  1. **Synthetic Social Graph (`SyntheticSocialNetwork`):**
     * Lightweight graph with bounded degree (max degree 2–4 per persona for 10-person cohort).
     * Deterministic and reproducible via explicit random seed.
     * Plausible homophily weights based on matching district, taluka, and college category.
     * Strictly synthetic simulation relationships; no self-connections.
  2. **Structured Interaction Model (`InteractionRecord`):**
     * Explicit sender/receiver IDs, simulation step, topic (`AWARENESS_DIFFUSION`, `DOCUMENT_HELP`, `APPLICATION_NUDGE`, `GENERAL_QUERY`), sender dialogue, receiver response, and applied state deltas.
  3. **Strict Policy Separation:**
     * Gemini/LLM handles persona communication and reasoning grounded in persona attributes.
     * Deterministic statutory policy rules (`RajarshiShahuPolicyEngine`) remain authoritative for eligibility and statutory benefit calculations.
  4. **Bounded State Updates (`InteractionStateEngine`):**
     * State updates (`awareness`, `institutional_trust`, `document_readiness`, `peer_network_support`) are strictly clamped to $[0.0, 1.0]$.
  5. **Multi-Step Simulation Loop (`run_multistep_cohort`):**
     * Iterates over configurable steps executing the 5-phase cycle: $\text{Observe} \to \text{Reason} \to \text{Interact} \to \text{Act} \to \text{Update State}$.
     * Fully backward compatible with single-step cohort execution.

---

## 10. FastAPI Service Layer & React Dashboard Integration

* **Status:** Approved & Implemented
* **Context:** To allow interactive exploration of the multi-agent policy simulation, a clean API layer and responsive frontend dashboard are required without compromising deterministic policy logic or exposing API secrets.
* **Decisions:**
  1. **Strict Client-Server Data Contract:**
     * Clean JSON DTO schema (`backend/models.py`) separating metadata, aggregate metrics, step-by-step diffusion metrics, persona states/reasoning, social interaction dialogues, and network topology.
     * All financial relief calculations (`estimated_fee_relief_inr`) and eligibility classifications (`statutory_eligibility`) are computed exclusively by Python engines before serialization.
  2. **FastAPI Endpoints:**
     * `GET /api/health`: Service health and provider readiness check.
     * `GET /api/schemes`: Catalog of supported schemes and ground-truth policy metadata.
     * `GET /api/districts`: Supported administrative regions with demographic calibration info.
     * `POST /api/simulate`: Full orchestration endpoint executing deterministic or Gemini-powered multi-step simulations.
  3. **No Direct Frontend-to-LLM Communication:**
     * React frontend communicates strictly with FastAPI backend; zero LLM calls or API keys reside in the client.
  4. **React + Vite Dashboard Architecture:**
     * Presentation-friendly dashboard with KPI metric cards, step-by-step diffusion timeline, filterable/searchable persona table, detailed persona inspection modal drawer, and peer dialogue feed.
     * 100% offline development and testing support via deterministic StubLLMProvider by default.

---

## 11. Open / Unresolved Items

* **Status:** Open / Under Research
1. **Specific Local LLM Engine & Model Size:** Selection of the exact quantized model (e.g., Llama-3-8B / Mistral / Qwen) and serving method (Ollama vs. local runtime vs. API fallback).
2. **Reference Dataset Files:** Finalizing exact CSV/JSON schemas for Maharashtra district-level college demographics.
3. **Historical Validation Dataset:** Identifying official scheme audit/disbursement reports to benchmark simulated uptake against historical actuals.


