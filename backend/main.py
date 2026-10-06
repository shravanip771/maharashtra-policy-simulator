"""
FastAPI Main Application for Maharashtra Policy Simulator.
Exposes REST endpoints to trigger multi-step simulations and query system health.
"""

import os
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from backend.models import SimulationRequest, SimulationResponse
from backend.service import SimulationService
from simulation.policy_rules import RajarshiShahuPolicyEngine

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
    return [
        {
            "district_name": "Dhule",
            "district_code": "498",
            "reference_dataset": "Dhule Education & Social Community Services (2010-11 Census Table)",
            "talukas": ["Dhule", "Shirpur", "Sindkhede", "Sakri"],
            "status": "Verified Empirical Baseline"
        }
    ]


@app.post("/api/simulate", response_model=SimulationResponse, status_code=status.HTTP_200_OK)
def run_simulation(request: SimulationRequest) -> SimulationResponse:
    """
    Executes a multi-step cohort simulation on synthetic citizen personas,
    reconciles deterministic eligibility with social interactions, and returns the complete DTO.
    """
    try:
        return SimulationService.execute_simulation(request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Simulation execution failed: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
