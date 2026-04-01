"""Internal data models for measurediff.

All models are immutable frozen dataclasses.  ``upstream`` tuples in
:class:`LineageColumn` form the recursive lineage tree — an empty tuple
means the node is a leaf (a base TABLE or a column with no captured lineage).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Lineage tree
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LineageColumn:
    """One node in the column-lineage tree.

    Attributes:
        table:    Three-part name ``catalog.schema.table`` of the source entity.
        column:   Column name within *table*.
        type:     Entity type as reported by Unity Catalog — one of
                  ``TABLE``, ``VIEW``, ``MATERIALIZED_VIEW``, ``METRIC_VIEW``,
                  ``STREAMING_TABLE``, or ``PATH``.
        upstream: Immediate upstream sources for this column.  Empty at leaf nodes
                  (i.e. when the entity is a base TABLE, when lineage data is
                  unavailable, or when ``max_depth`` has been reached).
    """

    table: str
    column: str
    type: str
    upstream: tuple[LineageColumn, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Metric-view structural models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class JoinDefinition:
    """A single join entry from the metric view YAML ``joins:`` block.

    Attributes:
        name:   Alias used to reference the joined table in expressions.
        source: Three-part name of the joined table/view.
        on:     SQL ON predicate (mutually exclusive with *using*).
        using:  List of column names for a USING join (mutually exclusive with *on*).
    """

    name: str
    source: str
    on: Optional[str] = None
    using: Optional[tuple[str, ...]] = None


@dataclass(frozen=True)
class DimensionDefinition:
    """A single ``dimensions:`` entry from a metric view.

    Attributes:
        name:         Dimension alias within the metric view.
        expr:         SQL scalar expression.
        comment:      Optional free-text description.
        display_name: Optional human-readable label.
    """

    name: str
    expr: str
    comment: Optional[str] = None
    display_name: Optional[str] = None


@dataclass(frozen=True)
class WindowSpec:
    """One window clause entry (``window:`` list item in the YAML).

    Attributes:
        order:       Dimension name that controls the ordering / partitioning.
        range:       Window extent string, e.g. ``"trailing 7 day"``, ``"cumulative"``.
        semiadditive: Aggregation strategy when the order dimension is absent from
                      the query: ``"first"`` or ``"last"``.
    """

    order: str
    range: str
    semiadditive: Optional[str] = None


@dataclass(frozen=True)
class MeasureDefinition:
    """A fully-enriched measure definition including upstream column lineage.

    Attributes:
        name:                Measure alias within the metric view.
        expr:                SQL aggregate / composed expression.
        comment:             Optional free-text description.
        display_name:        Optional human-readable label.
        window:              Window specifications (time-intelligence / semi-additive).
        lineage:             One :class:`LineageColumn` root per column reference
                             found in *expr*.  Empty for expressions with no column
                             references (e.g. ``COUNT(1)``), or when lineage
                             collection was skipped (``--no-lineage``).
        referenced_measures: Names of other measures referenced via ``MEASURE(x)``
                             in *expr*.  These are resolved transitively during
                             lineage collection so their lineage is merged into
                             *lineage*.
    """

    name: str
    expr: str
    comment: Optional[str] = None
    display_name: Optional[str] = None
    window: tuple[WindowSpec, ...] = field(default_factory=tuple)
    lineage: tuple[LineageColumn, ...] = field(default_factory=tuple)
    referenced_measures: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class MetricViewDefinition:
    """A complete metric view definition enriched with column lineage.

    This is the primary output of the ``measurediff collect`` pipeline.

    Attributes:
        full_name:   Three-part name ``catalog.schema.view``.
        source:      Source table/view/SQL for the metric view (the ``source:`` field).
        version:     Metric view YAML version string (e.g. ``"1.1"``).
        comment:     Optional metric view description.
        filter:      Optional SQL predicate applied to all queries.
        source_yaml: The raw YAML string extracted from the metric view DDL.
        joins:       Join definitions (star/snowflake schema).
        dimensions:  Dimension definitions.
        measures:    Measure definitions, each optionally enriched with lineage.
    """

    full_name: str
    source: str
    version: str = "1.1"
    comment: Optional[str] = None
    filter: Optional[str] = None
    source_yaml: str = ""
    joins: tuple[JoinDefinition, ...] = field(default_factory=tuple)
    dimensions: tuple[DimensionDefinition, ...] = field(default_factory=tuple)
    measures: tuple[MeasureDefinition, ...] = field(default_factory=tuple)
