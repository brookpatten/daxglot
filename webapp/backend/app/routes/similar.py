"""Route for finding measures similar to a given measure."""

from __future__ import annotations

from fastapi import APIRouter

from ..models import SimilarMeasureOut
from ..services import similar as similar_service

router = APIRouter(prefix="/api/similar", tags=["similar"])


@router.get("", response_model=list[SimilarMeasureOut])
def find_similar(id: str) -> list[SimilarMeasureOut]:
    """Return all measures ranked by similarity to the given measure id, descending.

    Accepts the measure id as a query parameter to avoid path-matching issues
    with ids that contain dots and slashes.
    """
    return similar_service.run_similar(id)
