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
from backend.auth.router import auth_router
from simulation.policy_rules import RajarshiShahuPolicyEngine
from simulation.district_config import list_supported_districts, get_district_profile

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
    """Health check endpoint confirming API status, active policy reference, and all supported districts."""
    supported = list_supported_districts()
    return {
        "status": "ok",
        "version": "1.0.0",
        "active_policy": RajarshiShahuPolicyEngine.SCHEME_NAME,
        "active_district": "Dhule",
        "supported_districts": supported,
        "total_supported_districts": len(supported),
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
    Lists all 36 Maharashtra districts configured in the policy simulator.
    Dhule (primary empirical baseline) is ordered first, followed by all remaining districts.
    """
    all_names = list_supported_districts()
    ordered_names = ["Dhule"] + [d for d in all_names if d != "Dhule"]

    results: List[Dict[str, Any]] = []
    for d_name in ordered_names:
        prof = get_district_profile(d_name)
        status_label = (
            "Verified Empirical Baseline"
            if prof.provenance_tier == "empirical_observed"
            else "Provisional Baseline"
        )
        results.append({
            "district_name": prof.district_name,
            "district_id": prof.district_id,
            "division": prof.division,
            "region_type": prof.region_type,
            "provenance_tier": prof.provenance_tier,
            "status": status_label,
            "reference_dataset": prof.source_reference,
            "reference_year": prof.reference_year,
            "source_url": prof.source_url,
            "talukas": prof.talukas,
            "missing_data": prof.missing_data,
            "available_statistics": prof.available_statistics,
            "assumptions_and_fallbacks": prof.assumptions_and_fallbacks,
        })
    return results


@app.post("/api/simulate", response_model=SimulationResponse, status_code=status.HTTP_200_OK)
def run_simulation(request: SimulationRequest) -> SimulationResponse:
    """
    Executes a multi-step cohort simulation on synthetic citizen personas,
    reconciles deterministic eligibility with social interactions, and returns the complete DTO.
    """
    try:
        return SimulationService.execute_simulation(request)
    except (ValueError, TypeError) as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Simulation execution failed: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
