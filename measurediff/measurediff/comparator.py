"""Compare two :class:`~measurediff.models.MeasureDefinition` objects.

Comparison is broken into three dimensions:

* **Expression** — are the SQL formulas semantically equivalent once table
  qualifiers are stripped from column references?
* **Window** — do the time-intelligence/semi-additive window specs match
  field-by-field?
* **Lineage** — do the ultimate upstream *leaf* sources agree?  Intermediate
  hops (passthrough views/tables) are flagged separately rather than being
  counted against the score, because ``a→b→c`` is functionally the same
  lineage as ``a→c``.

A weighted similarity score is computed from these three dimensions:

  ``score = 0.5 × expr + 0.2 × window + 0.3 × lineage``

Labels:
  * **Identical** — score ≥ 0.98
  * **Similar**   — score ≥ 0.60
  * **Different** — score < 0.60

Names and metric-view locations are *always* expected to differ and are
therefore displayed but excluded from the score.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

import sqlglot
import sqlglot.expressions as exp

from .models import LineageColumn, MeasureDefinition, WindowSpec


# ---------------------------------------------------------------------------
# Result dataclasses (all frozen / immutable)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExprComparison:
    """Comparison of two measure expressions.

    Attributes:
        raw_a:         Original expression from measure A.
        raw_b:         Original expression from measure B.
        normalized_a:  Expression A with table qualifiers stripped.
        normalized_b:  Expression B with table qualifiers stripped.
        same:          True when *normalized_a* == *normalized_b* (case-insensitive).
    """

    raw_a: str
    raw_b: str
    normalized_a: str
    normalized_b: str
    same: bool


@dataclass(frozen=True)
class WindowFieldDiff:
    """A single field that differs between two window spec entries.

    Attributes:
        spec_index: Which window spec (0-based) this diff belongs to.
        field:      One of ``"order"``, ``"range"``, or ``"semiadditive"``.
        value_a:    Value from measure A (``None`` if absent).
        value_b:    Value from measure B (``None`` if absent).
    """

    spec_index: int
    field: str
    value_a: Optional[str]
    value_b: Optional[str]


@dataclass(frozen=True)
class WindowComparison:
    """Comparison of window specifications.

    Attributes:
        specs_a:     Window specs from measure A.
        specs_b:     Window specs from measure B.
        same:        True when all fields across all specs are identical.
        field_diffs: Tuple of individual field differences.
    """

    specs_a: tuple[WindowSpec, ...]
    specs_b: tuple[WindowSpec, ...]
    same: bool
    field_diffs: tuple[WindowFieldDiff, ...]


@dataclass(frozen=True)
class LeafSource:
    """An ultimate upstream source column with no further lineage.

    Attributes:
        table:  Three-part name of the source table.
        column: Column name within *table*.
    """

    table: str
    column: str


@dataclass(frozen=True)
class LineageComparison:
    """Comparison of lineage leaf sources between two measures.

    Attributes:
        leaf_sources_a:   All leaf sources of measure A.
        leaf_sources_b:   All leaf sources of measure B.
        shared_leaves:    Leaves present in both.
        only_in_a:        Leaves exclusive to A.
        only_in_b:        Leaves exclusive to B.
        leaves_same:      True when shared_leaves == leaf_sources_a == leaf_sources_b.
        has_extra_hops_a: True when A has intermediate nodes absent from B's tree —
                          i.e. A reaches the same leaf via more steps.
        has_extra_hops_b: True when B has extra intermediate hops vs A.
    """

    leaf_sources_a: frozenset[LeafSource]
    leaf_sources_b: frozenset[LeafSource]
    shared_leaves: frozenset[LeafSource]
    only_in_a: frozenset[LeafSource]
    only_in_b: frozenset[LeafSource]
    leaves_same: bool
    has_extra_hops_a: bool
    has_extra_hops_b: bool


@dataclass(frozen=True)
class MeasureComparison:
    """Full comparison result for two measures.

    Attributes:
        view_a:     Metric view full name for measure A.
        measure_a:  Measure definition A.
        view_b:     Metric view full name for measure B.
        measure_b:  Measure definition B.
        expr:       Expression comparison.
        window:     Window comparison.
        lineage:    Lineage comparison.
        score:      Weighted similarity score in [0.0, 1.0].
        label:      Human-readable label: ``"Identical"``, ``"Similar"``, or ``"Different"``.
    """

    view_a: str
    measure_a: MeasureDefinition
    view_b: str
    measure_b: MeasureDefinition
    expr: ExprComparison
    window: WindowComparison
    lineage: LineageComparison
    score: float
    label: str


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def compare_measures(
    view_a: str,
    measure_a: MeasureDefinition,
    view_b: str,
    measure_b: MeasureDefinition,
) -> MeasureComparison:
    """Compare two measures and return a :class:`MeasureComparison`.

    Names and metric-view locations are expected to differ and are excluded
    from the similarity score.  The score is based purely on expression
    semantics, window specs, and ultimate upstream lineage sources.

    Args:
        view_a:    Metric view full name for *measure_a*.
        measure_a: First measure to compare.
        view_b:    Metric view full name for *measure_b*.
        measure_b: Second measure to compare.

    Returns:
        A fully-populated :class:`MeasureComparison`.
    """
    expr_cmp = _compare_expr(measure_a.expr, measure_b.expr)
    window_cmp = _compare_window(measure_a.window, measure_b.window)
    lineage_cmp = _compare_lineage(measure_a.lineage, measure_b.lineage)

    expr_score = 1.0 if expr_cmp.same else 0.0
    window_score = _window_score(window_cmp)
    lineage_score = _lineage_score(lineage_cmp)

    score = round(0.5 * expr_score + 0.2 *
                  window_score + 0.3 * lineage_score, 4)

    if score >= 0.98:
        label = "Identical"
    elif score >= 0.60:
        label = "Similar"
    else:
        label = "Different"

    return MeasureComparison(
        view_a=view_a,
        measure_a=measure_a,
        view_b=view_b,
        measure_b=measure_b,
        expr=expr_cmp,
        window=window_cmp,
        lineage=lineage_cmp,
        score=score,
        label=label,
    )


# ---------------------------------------------------------------------------
# Expression helpers
# ---------------------------------------------------------------------------


def _normalize_expr(expr: str) -> str:
    """Return *expr* with table qualifiers stripped from column references.

    ``SUM(source.total)`` → ``SUM(total)``

    Falls back to the original string if sqlglot cannot parse it.
    """
    try:
        tree = sqlglot.parse_one(expr, dialect="spark")
    except Exception:
        return expr.strip()

    for col in tree.find_all(exp.Column):
        if col.table:
            # Replace the column node with a bare column (no table qualifier)
            col.replace(exp.column(col.name))

    return tree.sql(dialect="spark").strip()


def _compare_expr(raw_a: str, raw_b: str) -> ExprComparison:
    norm_a = _normalize_expr(raw_a)
    norm_b = _normalize_expr(raw_b)
    return ExprComparison(
        raw_a=raw_a,
        raw_b=raw_b,
        normalized_a=norm_a,
        normalized_b=norm_b,
        same=norm_a.casefold() == norm_b.casefold(),
    )


# ---------------------------------------------------------------------------
# Window helpers
# ---------------------------------------------------------------------------


def _compare_window(
    specs_a: tuple[WindowSpec, ...],
    specs_b: tuple[WindowSpec, ...],
) -> WindowComparison:
    diffs: list[WindowFieldDiff] = []

    # Compare field-by-field for overlapping indices
    for i, (wa, wb) in enumerate(zip(specs_a, specs_b)):
        for field_name in ("order", "range", "semiadditive"):
            va = getattr(wa, field_name)
            vb = getattr(wb, field_name)
            if va != vb:
                diffs.append(WindowFieldDiff(
                    spec_index=i, field=field_name, value_a=va, value_b=vb))

    # Extra specs on A side
    for i in range(len(specs_b), len(specs_a)):
        wa = specs_a[i]
        for field_name in ("order", "range", "semiadditive"):
            va = getattr(wa, field_name)
            if va is not None:
                diffs.append(WindowFieldDiff(
                    spec_index=i, field=field_name, value_a=va, value_b=None))

    # Extra specs on B side
    for i in range(len(specs_a), len(specs_b)):
        wb = specs_b[i]
        for field_name in ("order", "range", "semiadditive"):
            vb = getattr(wb, field_name)
            if vb is not None:
                diffs.append(WindowFieldDiff(
                    spec_index=i, field=field_name, value_a=None, value_b=vb))

    return WindowComparison(
        specs_a=specs_a,
        specs_b=specs_b,
        same=len(diffs) == 0,
        field_diffs=tuple(diffs),
    )


def _window_score(cmp: WindowComparison) -> float:
    """Fraction of window fields that match across both specs."""
    total_specs = max(len(cmp.specs_a), len(cmp.specs_b))
    if total_specs == 0:
        return 1.0

    # Each spec has 3 fields: order, range, semiadditive
    total_fields = total_specs * 3
    differing = len(cmp.field_diffs)
    matching = max(0, total_fields - differing)
    return matching / total_fields


# ---------------------------------------------------------------------------
# Lineage helpers
# ---------------------------------------------------------------------------


def _collect_leaves(lineage: tuple[LineageColumn, ...]) -> frozenset[LeafSource]:
    """Recursively collect all leaf nodes (nodes with no upstream)."""
    leaves: set[LeafSource] = set()
    _walk_leaves(lineage, leaves)
    return frozenset(leaves)


def _walk_leaves(nodes: tuple[LineageColumn, ...], acc: set[LeafSource]) -> None:
    for node in nodes:
        if not node.upstream:
            acc.add(LeafSource(table=node.table, column=node.column))
        else:
            _walk_leaves(node.upstream, acc)


def _collect_intermediates(lineage: tuple[LineageColumn, ...]) -> frozenset[LeafSource]:
    """Recursively collect all non-leaf nodes."""
    intermediates: set[LeafSource] = set()
    _walk_intermediates(lineage, intermediates)
    return frozenset(intermediates)


def _walk_intermediates(nodes: tuple[LineageColumn, ...], acc: set[LeafSource]) -> None:
    for node in nodes:
        if node.upstream:
            acc.add(LeafSource(table=node.table, column=node.column))
            _walk_intermediates(node.upstream, acc)


def _compare_lineage(
    lineage_a: tuple[LineageColumn, ...],
    lineage_b: tuple[LineageColumn, ...],
) -> LineageComparison:
    leaves_a = _collect_leaves(lineage_a)
    leaves_b = _collect_leaves(lineage_b)

    # If one side has no lineage at all treat them as matching (no info to compare)
    no_lineage = not lineage_a and not lineage_b

    shared = leaves_a & leaves_b
    only_a = leaves_a - leaves_b
    only_b = leaves_b - leaves_a

    if no_lineage:
        leaves_same = True
    else:
        leaves_same = (shared == leaves_a == leaves_b)

    # Extra-hop detection: does A have intermediates that B doesn't, while
    # sharing the same ultimate leaves?
    intermediates_a = _collect_intermediates(lineage_a)
    intermediates_b = _collect_intermediates(lineage_b)

    # An extra hop in A means A has intermediate nodes whose columns also
    # appear as leaves in B (i.e. B reaches those leaves directly).
    extra_intermediate_a = intermediates_a - intermediates_b
    extra_intermediate_b = intermediates_b - intermediates_a

    has_extra_hops_a = bool(extra_intermediate_a)
    has_extra_hops_b = bool(extra_intermediate_b)

    return LineageComparison(
        leaf_sources_a=leaves_a,
        leaf_sources_b=leaves_b,
        shared_leaves=shared,
        only_in_a=only_a,
        only_in_b=only_b,
        leaves_same=leaves_same,
        has_extra_hops_a=has_extra_hops_a,
        has_extra_hops_b=has_extra_hops_b,
    )


def _lineage_score(cmp: LineageComparison) -> float:
    """Jaccard similarity of leaf sources.  Returns 1.0 when both have no lineage."""
    if not cmp.leaf_sources_a and not cmp.leaf_sources_b:
        return 1.0
    union = cmp.leaf_sources_a | cmp.leaf_sources_b
    if not union:
        return 1.0
    return len(cmp.shared_leaves) / len(union)
