"""Recursive column-lineage collection via ``system.access.column_lineage``.

This module walks the Unity Catalog column lineage system table to build the
upstream lineage tree for every column referenced in a metric view measure.

The recursion is bounded by *max_depth* and protected against cycles using an
immutable ``frozenset`` of ``(table, column)`` pairs accumulated per branch.
Because column lineage naturally forms a DAG (the same source column may feed
multiple targets), the same pair may appear in different branches — this is
intentional and correct.  Cycles (where column A derives from column B which
derives from column A) are still safely terminated.
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Optional

from .extractor import extract_column_refs, extract_measure_refs
from .models import LineageColumn, MeasureDefinition, MetricViewDefinition

logger = logging.getLogger(__name__)

# system table paths
_COLUMN_LINEAGE_TABLE = "system.access.column_lineage"


class LineageCollector:
    """Enrich :class:`~measurediff.models.MetricViewDefinition` measures with
    column lineage from ``system.access.column_lineage``.

    Args:
        spark:     A live :class:`pyspark.sql.SparkSession`.
        max_depth: Maximum recursion depth when traversing upstream lineage.
                   Defaults to 10.  Set to 0 to disable lineage traversal (same
                   effect as ``--no-lineage``).
    """

    def __init__(self, spark, max_depth: int = 10) -> None:
        self._spark = spark
        self._max_depth = max_depth
        # Per-column upstream cache: (target_table, target_column) → upstream rows.
        # None means "already queried, no results".
        self._cache: dict[
            tuple[str, str], Optional[list[tuple[str, str, str]]]
        ] = {}
        # Node result cache: avoids exponential re-traversal of shared DAG nodes.
        # The same (table, column) can appear on many branches; caching the fully
        # built LineageColumn converts O(branches^depth) calls to O(unique nodes).
        self._node_cache: dict[tuple[str, str], LineageColumn] = {}
        # Tracks tables whose lineage has already been bulk-fetched.  The first
        # time any column of a given table is looked up we fetch ALL columns of
        # that table in one SQL query, populating _cache for each one.  This
        # reduces round-trips from O(unique columns) to O(unique tables).
        self._fetched_tables: set[str] = set()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def enrich(self, view_def: MetricViewDefinition) -> MetricViewDefinition:
        """Return a copy of *view_def* with lineage populated on every measure.

        Measures that use ``MEASURE(x)`` composition have their lineage resolved
        transitively through sibling measure expressions before column lineage is
        traversed.

        Args:
            view_def: Parsed (but not yet lineage-enriched) definition.
        """
        # Build a map of measure name → expr for MEASURE() resolution.
        measure_expr_map = {m.name: m.expr for m in view_def.measures}

        # Build join alias map for column-ref resolution.
        alias_map: dict[str, str] = {"source": view_def.source}
        for j in view_def.joins:
            alias_map[j.name] = j.source

        enriched_measures = tuple(
            self._enrich_measure(m, view_def.source,
                                 alias_map, measure_expr_map)
            for m in view_def.measures
        )

        return dataclasses.replace(view_def, measures=enriched_measures)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _enrich_measure(
        self,
        measure: MeasureDefinition,
        source_table: str,
        alias_map: dict[str, str],
        measure_expr_map: dict[str, str],
        _resolving: frozenset[str] = frozenset(),
    ) -> MeasureDefinition:
        """Return *measure* with its ``lineage`` tuple populated.

        For composed measures (those with ``referenced_measures``), we first
        resolve each referenced measure's column refs transitively.
        """
        # Gather all column refs from this expression and from any MEASURE() refs.
        col_refs: list[tuple[str, str]] = list(
            extract_column_refs(measure.expr, source_table, alias_map)
        )

        for ref_name in measure.referenced_measures:
            if ref_name in _resolving:
                logger.debug(
                    "Skipping circular MEASURE(%s) reference in %s",
                    ref_name,
                    measure.name,
                )
                continue
            ref_expr = measure_expr_map.get(ref_name)
            if ref_expr is None:
                logger.debug(
                    "MEASURE(%s) not found in sibling measures", ref_name)
                continue
            col_refs.extend(
                extract_column_refs(ref_expr, source_table, alias_map)
            )
            # Recurse into nested MEASURE() refs within ref_expr.
            nested_refs = extract_measure_refs(ref_expr)
            for nested in nested_refs:
                if nested in _resolving or nested == ref_name:
                    continue
                nested_expr = measure_expr_map.get(nested)
                if nested_expr:
                    col_refs.extend(
                        extract_column_refs(
                            nested_expr, source_table, alias_map)
                    )

        # Deduplicate while preserving order.
        seen: dict[tuple[str, str], None] = {}
        for pair in col_refs:
            seen[pair] = None
        unique_col_refs = list(seen.keys())

        # Build lineage tree for each column ref.
        lineage = tuple(
            self._build_node(table, col, None, frozenset(), 0)
            for table, col in unique_col_refs
        )

        return dataclasses.replace(measure, lineage=lineage)

    def _build_node(
        self,
        table: str,
        column: str,
        entity_type: Optional[str],
        visited: frozenset[tuple[str, str]],
        depth: int,
    ) -> LineageColumn:
        """Recursively build a :class:`LineageColumn` tree node.

        Args:
            table:       Three-part name of the target table/view.
            column:      Column name within *table*.
            entity_type: Source type string from the lineage table (may be None
                         on the first call when we haven't queried yet).
            visited:     Immutable set of ``(table, column)`` pairs on the current
                         branch — prevents cycles.
            depth:       Current recursion depth.

        Returns:
            A :class:`LineageColumn` — either with upstream children or a leaf.
        """
        key = (table, column)

        # Return a previously-built node to avoid exponential re-traversal.
        # Shared DAG nodes (columns that feed multiple targets) would otherwise
        # be re-explored once per branch they appear in.
        if key in self._node_cache:
            return self._node_cache[key]

        if key in visited or depth >= self._max_depth:
            # Return a leaf — do not recurse further.
            return LineageColumn(
                table=table,
                column=column,
                type=entity_type or "UNKNOWN",
                upstream=(),
            )

        upstream_rows = self._get_upstream(table, column)
        if not upstream_rows:
            node = LineageColumn(
                table=table,
                column=column,
                type=entity_type or "UNKNOWN",
                upstream=(),
            )
            self._node_cache[key] = node
            return node

        new_visited = visited | {key}
        upstream_nodes = tuple(
            self._build_node(src_table, src_col, src_type,
                             new_visited, depth + 1)
            for src_table, src_col, src_type in upstream_rows
        )

        # Determine entity_type from first upstream row if not supplied.
        # The target_type of our current node is the source_type of the row
        # that wrote TO us, which isn't in this query.  We use what was passed
        # in (the src_type from our parent's query).
        resolved_type = entity_type or "UNKNOWN"

        node = LineageColumn(
            table=table,
            column=column,
            type=resolved_type,
            upstream=upstream_nodes,
        )
        self._node_cache[key] = node
        return node

    def _get_upstream(
        self, target_table: str, target_column: str
    ) -> list[tuple[str, str, str]]:
        """Return upstream sources for a single column, using a per-table cache.

        The first time any column of *target_table* is requested, the entire
        table's lineage is fetched in one SQL query (``_prefetch_table``).  All
        subsequent lookups for columns of the same table are served from cache,
        reducing round-trips from O(unique columns) to O(unique tables).
        """
        key = (target_table, target_column)
        if key in self._cache:
            cached = self._cache[key]
            return cached if cached is not None else []

        # Bulk-fetch all columns for this table if not done yet.
        if target_table not in self._fetched_tables:
            self._prefetch_table(target_table)

        cached = self._cache.get(key)
        return cached if cached is not None else []

    def _prefetch_table(
        self, target_table: str
    ) -> None:
        """Fetch column lineage for every column of *target_table* in one query.

        Populates ``self._cache`` for all ``(target_table, column)`` pairs found.
        Marks the table as fetched even when no rows are returned so repeated
        misses never trigger a second query.
        """
        self._fetched_tables.add(target_table)
        try:
            rows = self._spark.sql(
                f"""
                SELECT DISTINCT
                    target_column_name,
                    source_table_full_name,
                    source_column_name,
                    source_type
                FROM {_COLUMN_LINEAGE_TABLE}
                WHERE target_table_full_name = '{_escape(target_table)}'
                  AND source_table_full_name IS NOT NULL
                  AND source_column_name     IS NOT NULL
                """
            ).collect()
        except Exception as exc:
            logger.warning(
                "Lineage prefetch failed for table %s: %s", target_table, exc
            )
            return

        # Group rows by target column and populate per-column cache.
        grouped: dict[str, list[tuple[str, str, str]]] = {}
        for row in rows:
            col = row[0]
            entry = (row[1], row[2], row[3] or "UNKNOWN")
            grouped.setdefault(col, []).append(entry)

        for col, upstreams in grouped.items():
            self._cache[(target_table, col)] = upstreams

        logger.debug(
            "Prefetched lineage for %s: %d column(s) with upstream data",
            target_table,
            len(grouped),
        )


def _escape(value: str) -> str:
    """Minimal SQL string escaping — replace single quotes to prevent injection."""
    return value.replace("'", "''")
