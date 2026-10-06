"""
Data Module for Maharashtra Policy Simulator
Provides dataset adapters, reference statistics loaders, and data transformation models.
"""

from data.dhule_adapter import (
    RawTalukaEducationRecord,
    DhuleEducationDatasetSummary,
    DhuleEducationDatasetAdapter
)

__all__ = [
    "RawTalukaEducationRecord",
    "DhuleEducationDatasetSummary",
    "DhuleEducationDatasetAdapter"
]
