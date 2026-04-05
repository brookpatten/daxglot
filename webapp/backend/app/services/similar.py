"""Find measures ranked by similarity to a given measure."""

from __future__ import annotations

import logging

from fastapi import HTTPException

from ..config import settings
from ..models import MeasureOut, SimilarMeasureOut
from .measure_store import get_by_id, load_all

logger = logging.getLogger(__name__)


def run_similar(measure_id: str) -> list[SimilarMeasureOut]:
    """Compare *measure_id* against every other stored measure and return the
    results sorted by similarity score descending.

    Raises:
        HTTPException 404: If the requested measure is not found.
        HTTPException 503: If measurediff is not installed.
    """
    try:
        from measurediff.comparator import compare_measures
        from measurediff.loader import load_measure_yaml
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"measurediff is not installed: {exc}",
        ) from exc

    measures_dir = settings.measures_dir_resolved

    # Load the target measure
    target_path = measures_dir / f"{measure_id}.yaml"
    if not target_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Measure '{measure_id}' not found.",
        )
    target_view, target_def = load_measure_yaml(target_path)

    # Load all other measures and compare
    results: list[SimilarMeasureOut] = []
    for measure_out in load_all():
        if measure_out.id == measure_id:
            continue

        candidate_path = measures_dir / f"{measure_out.id}.yaml"
        if not candidate_path.exists():
            continue

        try:
            candidate_view, candidate_def = load_measure_yaml(candidate_path)
            cmp = compare_measures(
                target_view, target_def, candidate_view, candidate_def)
            if cmp.score > 0:
                results.append(
                    SimilarMeasureOut(
                        score=cmp.score,
                        label=cmp.label,
                        measure=measure_out,
                    )
                )
        except Exception as exc:
            logger.warning("Skipping similarity for %s — %s",
                           measure_out.id, exc)

    results.sort(key=lambda r: r.score, reverse=True)
    return results
