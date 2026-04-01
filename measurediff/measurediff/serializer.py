"""Serialise :class:`~measurediff.models.MetricViewDefinition` objects to YAML.

Output design
-------------
The primary output is **one YAML file per measure**, named
``{catalog}.{schema}.{view}.{measure}.yaml``.  Each file contains the full
measure definition together with the metric view context it was sourced from
(view name, source table, joins, dimensions, filter).

Example layout::

    metric_view:
      full_name: catalog.schema.sales_metrics
      source: catalog.schema.fact_orders
      version: '1.1'
      comment: Sales KPIs
      filter: status = 'O'
      joins:
        - name: customer
          source: catalog.schema.dim_customer
          on: source.cid = customer.id
      dimensions:
        - name: order_date
          expr: o_orderdate
    name: total_revenue
    expr: SUM(o_totalprice)
    comment: Gross revenue
    lineage:
      - table: catalog.schema.fact_orders
        column: o_totalprice
        type: METRIC_VIEW
        upstream:
          - table: catalog.schema.raw_orders
            column: price
            type: TABLE

When a measure has no column references (e.g. ``COUNT(1)``), ``lineage`` is
omitted rather than emitting an empty list.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

from .models import (
    DimensionDefinition,
    JoinDefinition,
    LineageColumn,
    MeasureDefinition,
    MetricViewDefinition,
    WindowSpec,
)


# ---------------------------------------------------------------------------
# Custom YAML Dumper — multiline strings as block literals
# ---------------------------------------------------------------------------


class _LiteralDumper(yaml.Dumper):
    """YAML Dumper that renders multi-line strings as block literals (``|``)."""


def _literal_str_representer(dumper: yaml.Dumper, data: str) -> yaml.ScalarNode:
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_LiteralDumper.add_representer(str, _literal_str_representer)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def to_dict(view_def: MetricViewDefinition) -> dict:
    """Convert *view_def* to a plain :class:`dict` suitable for ``yaml.dump``.

    Fields that are ``None`` or empty collections are omitted to keep output
    concise.
    """
    doc: dict = {
        "version": view_def.version,
        "full_name": view_def.full_name,
    }

    if view_def.comment:
        doc["comment"] = view_def.comment

    doc["source"] = view_def.source

    if view_def.filter:
        doc["filter"] = view_def.filter

    if view_def.joins:
        doc["joins"] = [_join_to_dict(j) for j in view_def.joins]

    if view_def.dimensions:
        doc["dimensions"] = [_dim_to_dict(d) for d in view_def.dimensions]

    if view_def.measures:
        doc["measures"] = [_measure_to_dict(m) for m in view_def.measures]

    return doc


def to_yaml(view_def: MetricViewDefinition) -> str:
    """Serialise a single :class:`~measurediff.models.MetricViewDefinition` to YAML."""
    return yaml.dump(
        to_dict(view_def),
        Dumper=_LiteralDumper,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        width=120,
    )


def measure_to_dict(
    measure: MeasureDefinition,
    view_def: MetricViewDefinition,
) -> dict:
    """Convert one *measure* to a lineage-focused plain dict.

    The output contains only:
    - ``metric_view``: the full three-part name of the source metric view
      (string, not a nested object — the lineage tree captures the data flow)
    - The measure's own fields (name, expr, comment, display_name, window,
      referenced_measures, lineage)

    Fields that are None or empty are omitted.
    """
    doc: dict = {"metric_view": view_def.full_name}
    doc.update(_measure_to_dict(measure))
    return doc


def measure_to_yaml(
    measure: MeasureDefinition,
    view_def: MetricViewDefinition,
) -> str:
    """Serialise one *measure* with its view context to a YAML string."""
    return yaml.dump(
        measure_to_dict(measure, view_def),
        Dumper=_LiteralDumper,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        width=120,
    )


def write_measures(
    view_def: MetricViewDefinition,
    output_dir: str | Path,
) -> list[Path]:
    """Write one YAML file per measure in *view_def* to *output_dir*.

    Files are named ``{full_name}.{measure_name}.yaml``, e.g.
    ``prod.finance.sales_metrics.total_revenue.yaml``.

    Args:
        view_def:   Enriched metric view definition.
        output_dir: Directory to write into (created if it does not exist).

    Returns:
        List of written file paths, one per measure.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for measure in view_def.measures:
        filename = f"{view_def.full_name}.{measure.name}.yaml"
        path = out / filename
        path.write_text(measure_to_yaml(measure, view_def), encoding="utf-8")
        paths.append(path)
    return paths


def write(
    view_def: MetricViewDefinition,
    output_dir: str | Path,
) -> Path:
    """Write a single YAML file containing the full *view_def* to *output_dir*.

    The file is named ``{view_name}.yaml``.  Prefer :func:`write_measures` for
    the standard per-measure output.

    Args:
        view_def:   Definition to serialise.
        output_dir: Directory to write into (created if it does not exist).

    Returns:
        Path to the written YAML file.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    view_name = view_def.full_name.rsplit(".", 1)[-1]
    path = out / f"{view_name}.yaml"
    path.write_text(to_yaml(view_def), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Private serialisation helpers
# ---------------------------------------------------------------------------


def _join_to_dict(join: JoinDefinition) -> dict:
    d: dict = {"name": join.name, "source": join.source}
    if join.on:
        d["on"] = join.on
    elif join.using:
        d["using"] = list(join.using)
    return d


def _dim_to_dict(dim: DimensionDefinition) -> dict:
    d: dict = {"name": dim.name, "expr": dim.expr}
    if dim.comment:
        d["comment"] = dim.comment
    if dim.display_name:
        d["display_name"] = dim.display_name
    return d


def _window_to_dict(w: WindowSpec) -> dict:
    d: dict = {"order": w.order, "range": w.range}
    if w.semiadditive:
        d["semiadditive"] = w.semiadditive
    return d


def _lineage_col_to_dict(node: LineageColumn) -> dict:
    d: dict = {
        "table": node.table,
        "column": node.column,
        "type": node.type,
    }
    if node.upstream:
        d["upstream"] = [_lineage_col_to_dict(u) for u in node.upstream]
    return d


def _measure_to_dict(measure: MeasureDefinition) -> dict:
    d: dict = {"name": measure.name, "expr": measure.expr}
    if measure.comment:
        d["comment"] = measure.comment
    if measure.display_name:
        d["display_name"] = measure.display_name
    if measure.window:
        d["window"] = [_window_to_dict(w) for w in measure.window]
    if measure.referenced_measures:
        d["referenced_measures"] = list(measure.referenced_measures)
    if measure.lineage:
        d["lineage"] = [_lineage_col_to_dict(lc) for lc in measure.lineage]
    return d
