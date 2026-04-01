"""Load per-measure YAML files written by :func:`~measurediff.serializer.write_measures`.

This is the inverse of :func:`~measurediff.serializer.measure_to_yaml`.  It
deserialises the YAML format back into a :class:`~measurediff.models.MeasureDefinition`
and the metric view full name string.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import LineageColumn, MeasureDefinition, WindowSpec


def load_measure_yaml(path: str | Path) -> tuple[str, MeasureDefinition]:
    """Load a per-measure YAML file and return ``(metric_view_full_name, measure)``.

    Args:
        path: Path to a YAML file produced by
              :func:`~measurediff.serializer.write_measures`.

    Returns:
        A two-tuple of the metric view full name (string) and the
        :class:`~measurediff.models.MeasureDefinition`.

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

    return str(metric_view), measure


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
