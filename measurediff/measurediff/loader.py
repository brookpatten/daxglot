"""Load per-measure YAML files written by :func:`~measurediff.serializer.write_measures`.

This is the inverse of :func:`~measurediff.serializer.measure_to_yaml`.  It
deserialises the YAML format back into a :class:`~measurediff.models.MeasureDefinition`
and the metric view full name string.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import DimensionDefinition, LineageColumn, MeasureDefinition, WindowSpec


def load_measure_yaml(path: str | Path) -> tuple[str, MeasureDefinition, str, list[DimensionDefinition]]:
    """Load a per-measure YAML file and return ``(metric_view_name, measure, source_table, dimensions)``.

    Args:
        path: Path to a YAML file produced by
              :func:`~measurediff.serializer.write_measures`.

    Returns:
        A four-tuple of the metric view full name (string), the
        :class:`~measurediff.models.MeasureDefinition`, the source table
        full name (string, empty string if absent), and the list of
        :class:`~measurediff.models.DimensionDefinition` for the metric view.

    Raises:
        ValueError: If the file is missing required fields.
    """
    text = Path(path).read_text(encoding="utf-8")
    doc: dict[str, Any] = yaml.safe_load(text)

    metric_view = doc.get("metric_view")
    if not metric_view:
        raise ValueError(f"{path}: missing 'metric_view' field")

    name = doc.get("name")
    if not name:
        raise ValueError(f"{path}: missing 'name' field")

    expr = doc.get("expr")
    if not expr:
        raise ValueError(f"{path}: missing 'expr' field")

    window = tuple(
        WindowSpec(
            order=w["order"],
            range=w["range"],
            semiadditive=w.get("semiadditive"),
        )
        for w in (doc.get("window") or [])
    )

    lineage = tuple(
        _load_lineage_column(node) for node in (doc.get("lineage") or [])
    )

    referenced_measures = tuple(doc.get("referenced_measures") or [])

    measure = MeasureDefinition(
        name=name,
        expr=expr,
        comment=doc.get("comment"),
        display_name=doc.get("display_name"),
        window=window,
        lineage=lineage,
        referenced_measures=referenced_measures,
    )

    source_table: str = doc.get("source_table") or ""
    dimensions: list[DimensionDefinition] = [
        DimensionDefinition(
            name=d["name"],
            expr=d["expr"],
            comment=d.get("comment"),
            display_name=d.get("display_name"),
        )
        for d in (doc.get("dimensions") or [])
    ]

    return str(metric_view), measure, source_table, dimensions


def _load_lineage_column(node: dict[str, Any]) -> LineageColumn:
    """Recursively deserialise a lineage node dict into a :class:`LineageColumn`."""
    upstream = tuple(
        _load_lineage_column(u) for u in (node.get("upstream") or [])
    )
    return LineageColumn(
        table=node["table"],
        column=node["column"],
        type=node["type"],
        upstream=upstream,
    )
