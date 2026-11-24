"""
FastAPI Main Application for Maharashtra Policy Simulator.
Exposes REST endpoints to trigger multi-step simulations and query system health.
"""

import os
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from backend.models import (
    SimulationRequest,
    SimulationResponse,
    StatewideCohortResponse,
    StatewideSimulationRequest,
    StatewideSimulationResponse
)
from backend.service import SimulationService
from backend.auth.router import auth_router
from simulation.policy_rules import RajarshiShahuPolicyEngine

app = FastAPI(
    title="Maharashtra Policy Simulator API",
    description="Agent-based policy uptake and social interaction simulation engine for Maharashtra education schemes.",
    version="1.0.0"
)

# Mount authentication router under /api/auth
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])

# Enable CORS for local React/Vite development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permits localhost Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", status_code=status.HTTP_200_OK)
def health_check() -> Dict[str, Any]:
    """Health check endpoint confirming API status and active policy reference."""
    return {
        "status": "ok",
        "version": "1.0.0",
        "active_policy": RajarshiShahuPolicyEngine.SCHEME_NAME,
        "active_district": "Dhule",
        "supported_districts": ["Dhule"],
        "default_mode": "Offline Deterministic Stub (Zero-cost safe)"
    }


@app.get("/api/schemes", status_code=status.HTTP_200_OK)
def list_schemes() -> List[Dict[str, Any]]:
    """Lists available government schemes configured in the policy engine."""
    return [
        {
            "scheme_code": "RCSMS-EBC",
            "scheme_name": RajarshiShahuPolicyEngine.SCHEME_NAME,
            "department": "Higher & Technical Education Department",
            "target_beneficiary": "Economically Backward Class (EBC) College Students",
            "income_ceiling_inr": RajarshiShahuPolicyEngine.MAX_INCOME_LIMIT,
            "attendance_threshold": RajarshiShahuPolicyEngine.MIN_ATTENDANCE_PERCENT,
            "baseline_fee_relief_rate": 0.50
        }
    ]


@app.get("/api/districts", status_code=status.HTTP_200_OK)
def list_districts() -> List[Dict[str, Any]]:
    """Lists districts with verified census / empirical baseline configurations."""
    from simulation.district_config import DISTRICT_REGISTRY
    districts: List[Dict[str, Any]] = []

    # Ensure Dhule is first for backward compatibility with existing tests
    dhule_p = DISTRICT_REGISTRY.get("DHULE")
    if dhule_p:
        districts.append({
            "district_name": dhule_p.district_name,
            "district_code": "498",
            "division": dhule_p.division,
            "region_type": dhule_p.region_type,
            "provenance_tier": dhule_p.provenance_tier,
            "reference_dataset": dhule_p.source_reference,
            "reference_year": dhule_p.reference_year,
            "talukas": dhule_p.talukas,
            "available_statistics": dhule_p.available_statistics,
            "status": "Verified Empirical Baseline" if dhule_p.provenance_tier == "empirical_observed" else "Provisional Baseline"
        })

    # Add all other configured districts from registry
    for key, p in DISTRICT_REGISTRY.items():
        if key == "DHULE":
            continue
        districts.append({
            "district_name": p.district_name,
            "district_code": p.district_id,
            "division": p.division,
            "region_type": p.region_type,
            "provenance_tier": p.provenance_tier,
            "reference_dataset": p.source_reference,
            "reference_year": p.reference_year,
            "talukas": p.talukas,
            "available_statistics": p.available_statistics,
            "status": "Verified Empirical Baseline" if p.provenance_tier == "empirical_observed" else "Provisional Baseline"
        })

    return districts


@app.post("/api/simulate", response_model=SimulationResponse, status_code=status.HTTP_200_OK)
def run_simulation(request: SimulationRequest) -> SimulationResponse:
    """
    Executes a multi-step cohort simulation on synthetic citizen personas,
    reconciles deterministic eligibility with social interactions, and returns the complete DTO.
    """
    try:
        return SimulationService.execute_simulation(request)
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Simulation execution failed: {str(e)}"
        )


@app.get("/api/cohorts/statewide", response_model=StatewideCohortResponse, status_code=status.HTTP_200_OK)
def get_statewide_cohort(
    seed: int = Query(default=42, description="Deterministic random seed for persona generation")
) -> StatewideCohortResponse:
    """
    Returns the complete statewide synthetic cohort of 1,000 personas distributed
    across the 36 configured districts according to Census 2011 population weighting.
    """
    try:
        return SimulationService.generate_statewide_cohort(seed=seed)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Statewide cohort generation failed: {str(e)}"
        )


@app.post("/api/simulate/statewide", response_model=StatewideSimulationResponse, status_code=status.HTTP_200_OK)
def run_statewide_simulation(request: StatewideSimulationRequest) -> StatewideSimulationResponse:
    """
    Executes a multi-step simulation across the complete 1,000-persona statewide cohort across all 36 districts.
    Aggregates macro KPIs across all 1,000 personas, compiles district-wise metrics, and returns detailed
    profiles and interaction dialogues for exactly 10 deterministically selected featured personas.
    """
    try:
        return SimulationService.execute_statewide_simulation(request)
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Statewide simulation execution failed: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
