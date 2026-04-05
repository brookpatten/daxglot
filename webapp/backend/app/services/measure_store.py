"""Load and search per-measure YAML files from the configured MEASURES_DIR."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from measurediff.loader import load_measure_yaml
from measurediff.models import LineageColumn, MeasureDefinition, DimensionDefinition

from ..config import settings
from ..models import DimensionOut, LineageColumnOut, MeasureOut, WindowSpecOut

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------


def _lineage_to_out(node: LineageColumn) -> LineageColumnOut:
    return LineageColumnOut(
        table=node.table,
        column=node.column,
        type=node.type,
        upstream=[_lineage_to_out(u) for u in node.upstream],
    )


def _measure_to_out(
    stem: str,
    metric_view: str,
    measure: MeasureDefinition,
    source_table: str = "",
    dimensions: list[DimensionDefinition] | None = None,
) -> MeasureOut:
    return MeasureOut(
        id=stem,
        metric_view=metric_view,
        source_table=source_table,
        dimensions=[DimensionOut(name=d.name, expr=d.expr)
                    for d in (dimensions or [])],
        name=measure.name,
        expr=measure.expr,
        comment=measure.comment,
        display_name=measure.display_name,
        window=[WindowSpecOut(order=w.order, range=w.range,
                              semiadditive=w.semiadditive) for w in measure.window],
        referenced_measures=list(measure.referenced_measures),
        lineage=[_lineage_to_out(lc) for lc in measure.lineage],
    )


# ---------------------------------------------------------------------------
# Lineage filtering helper
# ---------------------------------------------------------------------------


def _lineage_matches(nodes: list[LineageColumnOut], catalog: Optional[str], schema: Optional[str], table: Optional[str], column: Optional[str]) -> bool:
    """Recursively walk the lineage tree; return True if any node matches ALL provided filters."""
    for node in nodes:
        parts = node.table.lower().split(".")
        # table field is catalog.schema.table (three parts)
        node_catalog = parts[0] if len(parts) > 0 else ""
        node_schema = parts[1] if len(parts) > 1 else ""
        node_table = parts[2] if len(parts) > 2 else ""

        match = True
        if catalog and catalog.lower() not in node_catalog:
            match = False
        if schema and schema.lower() not in node_schema:
            match = False
        if table and table.lower() not in node_table:
            match = False
        if column and column.lower() not in node.column.lower():
            match = False

        if match:
            return True

        if _lineage_matches(node.upstream, catalog, schema, table, column):
            return True

    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_all() -> list[MeasureOut]:
    """Load every *.yaml file in MEASURES_DIR as a MeasureOut."""
    measures_dir = settings.measures_dir_resolved
    if not measures_dir.exists():
        return []

    results: list[MeasureOut] = []
    for path in sorted(measures_dir.glob("*.yaml")):
        try:
            metric_view, measure, source_table, dimensions = load_measure_yaml(
                path)
            results.append(_measure_to_out(
                path.stem, metric_view, measure, source_table, dimensions))
        except Exception as exc:
            logger.warning("Skipping %s — %s", path.name, exc)
    return results


def search(
    name: Optional[str] = None,
    display_name: Optional[str] = None,
    metric_view: Optional[str] = None,
    catalog: Optional[str] = None,
    schema: Optional[str] = None,
    table: Optional[str] = None,
    column: Optional[str] = None,
    function: Optional[str] = None,
) -> list[MeasureOut]:
    """Return measures matching ALL provided filters (case-insensitive substring)."""
    measures = load_all()

    def _matches(m: MeasureOut) -> bool:
        if name and name.lower() not in m.name.lower():
            return False
        if display_name and (m.display_name is None or display_name.lower() not in m.display_name.lower()):
            return False
        if metric_view and metric_view.lower() not in m.metric_view.lower():
            return False
        if function and function.lower() not in m.expr.lower():
            return False
        # Lineage filters: check both top-level table name (in metric_view field)
        # and the recursive lineage tree.
        if catalog or schema or table or column:
            # Also check metric_view full name for catalog/schema/table parts
            mv_parts = m.metric_view.lower().split(".")
            mv_catalog = mv_parts[0] if len(mv_parts) > 0 else ""
            mv_schema = mv_parts[1] if len(mv_parts) > 1 else ""
            mv_table = mv_parts[2] if len(mv_parts) > 2 else ""

            mv_match = True
            col_match = False  # column can only match lineage, not metric_view
            if catalog and catalog.lower() not in mv_catalog:
                mv_match = False
            if schema and schema.lower() not in mv_schema:
                mv_match = False
            if table and table.lower() not in mv_table:
                mv_match = False
            if column:
                mv_match = False  # column-level match needs the lineage tree

            lineage_match = _lineage_matches(
                m.lineage, catalog, schema, table, column)

            if not mv_match and not lineage_match:
                return False

        return True

    return [m for m in measures if _matches(m)]


def get_by_id(measure_id: str) -> Optional[MeasureOut]:
    """Return a single measure by its filename stem, or None."""
    path = settings.measures_dir_resolved / f"{measure_id}.yaml"
    if not path.exists():
        return None
    try:
        metric_view, measure, source_table, dimensions = load_measure_yaml(
            path)
        return _measure_to_out(path.stem, metric_view, measure, source_table, dimensions)
    except Exception as exc:
        logger.warning("Failed to load %s — %s", path, exc)
        return None
