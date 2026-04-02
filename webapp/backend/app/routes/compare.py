"""Route for comparing a set of measures using measurediff."""

from __future__ import annotations

from fastapi import APIRouter

from ..models import CompareOut, CompareRequest
from ..services import comparer

router = APIRouter(prefix="/api/compare", tags=["compare"])


@router.post("", response_model=CompareOut)
def compare_measures(request: CompareRequest) -> CompareOut:
    """Compare a set of measures by id.

    Accepts 2+ measure ids and returns pairwise diff results including
    expression, window, and lineage comparisons with similarity scores.
    """
    return comparer.run_compare(request.ids)
