"""
FastAPI Main Application for Maharashtra Policy Simulator.
Exposes REST endpoints to trigger multi-step simulations and query system health.
"""

import os
from typing import Dict, Any, List, Union
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
from simulation.policy_rules import RajarshiShahuPolicyEngine
from simulation.district_config import DISTRICT_REGISTRY, list_supported_districts

app = FastAPI(
    title="Maharashtra Policy Simulator API",
    description="Agent-based policy uptake and social interaction simulation engine for Maharashtra education schemes.",
    version="1.0.0"
)

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
    supported = list_supported_districts()
    return {
        "status": "ok",
        "version": "1.0.0",
        "active_policy": RajarshiShahuPolicyEngine.SCHEME_NAME,
        "active_district": "Dhule",
        "supported_districts": supported,
        "total_districts": len(supported),
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
    """
    Lists all configured Maharashtra districts.
    Ensures Dhule is first for backward compatibility with existing tests.
    """
    districts: List[Dict[str, Any]] = []

    # Ensure Dhule is first
    dhule_p = DISTRICT_REGISTRY.get("DHULE")
    if dhule_p:
        is_empirical = (dhule_p.provenance_tier == "empirical_observed")
        status_label = "Verified Empirical Baseline" if is_empirical else "Provisional Baseline"
        districts.append({
            "district_id": dhule_p.district_id,
            "district_name": dhule_p.district_name,
            "district_code": "498",
            "division": dhule_p.division,
            "region_type": dhule_p.region_type,
            "provenance_tier": dhule_p.provenance_tier,
            "reference_dataset": dhule_p.source_reference,
            "reference_year": dhule_p.reference_year,
            "talukas": dhule_p.talukas or [],
            "taluka_distribution": dhule_p.taluka_distribution,
            "source_reference": dhule_p.source_reference,
            "source_url": dhule_p.source_url,
            "available_statistics": dhule_p.available_statistics,
            "status": status_label,
            "is_empirical": is_empirical
        })

    # Add all other configured districts from registry
    for key, p in DISTRICT_REGISTRY.items():
        if key == "DHULE":
            continue
        is_empirical = (p.provenance_tier == "empirical_observed")
        status_label = "Verified Empirical Baseline" if is_empirical else "Provisional Baseline"
        districts.append({
            "district_id": p.district_id,
            "district_name": p.district_name,
            "district_code": p.district_id,
            "division": p.division,
            "region_type": p.region_type,
            "provenance_tier": p.provenance_tier,
            "reference_dataset": p.source_reference,
            "reference_year": p.reference_year,
            "talukas": p.talukas or [],
            "taluka_distribution": p.taluka_distribution,
            "source_reference": p.source_reference,
            "source_url": p.source_url,
            "available_statistics": p.available_statistics,
            "status": status_label,
            "is_empirical": is_empirical
        })

    return districts


@app.post("/api/simulate", response_model=Union[SimulationResponse, StatewideSimulationResponse], status_code=status.HTTP_200_OK)
def run_simulation(request: SimulationRequest) -> Union[SimulationResponse, StatewideSimulationResponse]:
    """
    Executes a multi-step cohort simulation on synthetic citizen personas.
    Automatically resolves single district or statewide mode.
    """
    try:
        return SimulationService.execute_simulation(request)
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except KeyError as ke:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ke).strip("'\"")
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
