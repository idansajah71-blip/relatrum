"""Alignment engine package: candidate retrieval + deterministic classification."""
from app.services.alignment._types import Candidate
from app.services.alignment.engine import (
    FULL_THRESHOLD,
    PARTIAL_THRESHOLD,
    ALIGNED_TYPES,
    AlignmentDecision,
    classify_candidates,
    classify_candidate,
)
from app.services.alignment.retrieval import retrieve_candidates

__all__ = [
    "Candidate",
    "FULL_THRESHOLD",
    "PARTIAL_THRESHOLD",
    "ALIGNED_TYPES",
    "AlignmentDecision",
    "classify_candidates",
    "classify_candidate",
    "retrieve_candidates",
]
