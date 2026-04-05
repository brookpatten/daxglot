"""Route for comparing a set of measures using measurediff."""

from __future__ import annotations

from fastapi import APIRouter

from ..models import CompareOut, CompareRequest
from ..services import comparer

router = APIRouter(prefix="/api/compare", tags=["compare"])


@router.post("", response_model=CompareOut)
def compare_measures(request: CompareRequest) -> CompareOut:
    """Compare exactly 2 measures by id.

    Accepts exactly 2 measure ids and returns the diff result including
    expression, window, and lineage comparisons with a similarity score.
    """
    return comparer.run_compare(request.ids)
