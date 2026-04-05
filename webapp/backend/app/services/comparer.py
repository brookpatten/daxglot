"""Compare a set of measures using measurediff.comparator."""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import Optional

from fastapi import HTTPException

from ..config import settings
from ..models import (
    CompareOut,
    ExprComparisonOut,
    LeafSourceOut,
    LineageComparisonOut,
    MeasureOut,
    PairComparisonOut,
    WindowComparisonOut,
    WindowFieldDiffOut,
    WindowSpecOut,
)
from ..services.measure_store import get_by_id


def run_compare(ids: list[str]) -> CompareOut:
    """Load each measure by id, run pairwise comparisons, and return results.

    Raises:
        HTTPException 404: If any requested id is not found.
        HTTPException 400: If fewer than 2 ids supplied.
    """
    if len(ids) != 2:
        raise HTTPException(
            status_code=400,
            detail="Exactly 2 measure ids are required for comparison.",
        )

    try:
        from measurediff.comparator import compare_measures
        from measurediff.loader import load_measure_yaml
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"measurediff is not installed: {exc}",
        ) from exc

    # Resolve measure YAMLs from disk (we need the MeasureDefinition objects)
    measures_dir = settings.measures_dir_resolved
    # id → (metric_view, MeasureDefinition)
    loaded: dict[str, tuple[str, object]] = {}

    for measure_id in ids:
        path = measures_dir / f"{measure_id}.yaml"
        if not path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Measure '{measure_id}' not found.",
            )
        metric_view, measure_def = load_measure_yaml(path)
        loaded[measure_id] = (metric_view, measure_def)

    # MeasureOut objects to return
    measure_outs: list[MeasureOut] = []
    for mid in ids:
        m = get_by_id(mid)
        if m is None:
            raise HTTPException(
                status_code=404, detail=f"Measure '{mid}' not found.")
        measure_outs.append(m)

    # All pairwise comparisons
    pairs: list[PairComparisonOut] = []
    for id_a, id_b in itertools.combinations(ids, 2):
        view_a, def_a = loaded[id_a]
        view_b, def_b = loaded[id_b]

        result = compare_measures(view_a, def_a, view_b, def_b)

        # Expr
        expr_out = ExprComparisonOut(
            raw_a=result.expr.raw_a,
            raw_b=result.expr.raw_b,
            normalized_a=result.expr.normalized_a,
            normalized_b=result.expr.normalized_b,
            same=result.expr.same,
        )

        # Window
        window_out = WindowComparisonOut(
            specs_a=[
                WindowSpecOut(order=w.order, range=w.range,
                              semiadditive=w.semiadditive)
                for w in result.window.specs_a
            ],
            specs_b=[
                WindowSpecOut(order=w.order, range=w.range,
                              semiadditive=w.semiadditive)
                for w in result.window.specs_b
            ],
            same=result.window.same,
            field_diffs=[
                WindowFieldDiffOut(
                    spec_index=d.spec_index,
                    field=d.field,
                    value_a=d.value_a,
                    value_b=d.value_b,
                )
                for d in result.window.field_diffs
            ],
        )

        # Lineage
        def _ls(s: frozenset) -> list[LeafSourceOut]:
            return sorted(
                [LeafSourceOut(table=x.table, column=x.column) for x in s],
                key=lambda x: (x.table, x.column),
            )

        lineage_out = LineageComparisonOut(
            leaf_sources_a=_ls(result.lineage.leaf_sources_a),
            leaf_sources_b=_ls(result.lineage.leaf_sources_b),
            shared_leaves=_ls(result.lineage.shared_leaves),
            only_in_a=_ls(result.lineage.only_in_a),
            only_in_b=_ls(result.lineage.only_in_b),
            leaves_same=result.lineage.leaves_same,
            has_extra_hops_a=result.lineage.has_extra_hops_a,
            has_extra_hops_b=result.lineage.has_extra_hops_b,
        )

        pairs.append(
            PairComparisonOut(
                id_a=id_a,
                id_b=id_b,
                view_a=view_a,
                view_b=view_b,
                name_a=def_a.name,
                name_b=def_b.name,
                score=result.score,
                label=result.label,
                expr=expr_out,
                window=window_out,
                lineage=lineage_out,
            )
        )

    return CompareOut(measures=measure_outs, pairs=pairs)
