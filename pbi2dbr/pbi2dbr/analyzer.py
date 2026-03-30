"""Semantic model analysis: fact/dimension classification, join-tree building, and dimension extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .models import (
    ColumnSchema,
    Dimension,
    FactTable,
    Join,
    Relationship,
    SemanticModel,
    SourceTable,
    _is_system_table,
)


@dataclass
class AnalysisOptions:
    """Options controlling how the analyzer classifies tables."""

    fact_tables: Optional[list[str]] = None
    """Explicitly list tables to treat as fact tables (overrides heuristic)."""

    include_isolated: bool = False
    """Include tables with no relationships and no measures."""

    max_snowflake_depth: int = 3
    """Maximum depth when traversing snowflake join chains."""

    exclude_tables: list[str] = None  # type: ignore[assignment]
    """Tables to skip entirely."""

    skip_calculated: bool = True
    """Skip DAX-calculated tables (no Unity Catalog backing storage)."""

    skip_no_uc_ref: bool = False
    """Skip tables whose Unity Catalog source reference cannot be resolved.
    When ``False`` (default), such tables are included with a warning."""

    skip_system_tables: bool = True
    """Skip Power BI auto-generated tables (DateTableTemplate, LocalDateTable_*, etc.)."""

    require_measures_or_numeric: bool = False
    """Skip tables that have neither DAX measures nor any numeric columns.
    Useful for filtering out pure bridge/lookup tables."""

    def __post_init__(self) -> None:
        if self.exclude_tables is None:
            self.exclude_tables = []


class ModelAnalyzer:
    """Analyse a :class:`~pbi2dbr.models.SemanticModel` and produce :class:`~pbi2dbr.models.FactTable` objects.

    Usage::

        model = PbixExtractor("model.pbix").extract()
        analyzer = ModelAnalyzer(model, options)
        fact_tables = analyzer.analyze()
    """

    def __init__(self, model: SemanticModel, options: Optional[AnalysisOptions] = None) -> None:
        self._model = model
        self._opts = options or AnalysisOptions()
        self._warnings: list[str] = []

    @property
    def warnings(self) -> list[str]:
        return list(self._warnings)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def analyze(self) -> list[FactTable]:
        """Classify tables and build FactTable objects with joins and dimensions."""
        active_rels = [r for r in self._model.relationships if r.is_active]

        # Tables with measures (always treated as fact or joined to a fact)
        tables_with_measures = {m.table for m in self._model.measures}

        # Tables that appear on the FK side of at least one relationship
        fk_tables = {r.from_table for r in active_rels}

        # Tables that ONLY appear on the PK side → pure dimension tables
        pk_only_tables = {r.to_table for r in active_rels} - fk_tables

        # Determine fact tables
        if self._opts.fact_tables:
            fact_names = set(self._opts.fact_tables)
        else:
            # Heuristic: fact tables have at least one outgoing FK OR have measures
            fact_names = (fk_tables | tables_with_measures) - pk_only_tables
            # Edge case: if a table has measures but no relationships at all, include it
            if not fact_names:
                fact_names = tables_with_measures | set(self._model.tables)

        results: list[FactTable] = []
        for table_name in sorted(fact_names):
            if table_name in (self._opts.exclude_tables or []):
                continue
            if not table_name:
                continue
            # Fast-path: skip system tables before building joins/dimensions
            if self._opts.skip_system_tables and _is_system_table(table_name):
                self._warnings.append(
                    f"Skipping system table '{table_name}'"
                )
                continue
            src = self._model.source_tables.get(
                table_name, SourceTable(name=table_name))
            joins = self._build_join_tree(
                table_name, active_rels, visited=set(), depth=0)
            dimensions = self._extract_dimensions(
                table_name, joins, active_rels)
            measures = self._model.measures_for(table_name)
            fact = FactTable(
                name=table_name,
                source_table=src,
                dimensions=dimensions,
                measures=measures,
                joins=joins,
            )
            skip, reason = fact.should_skip(
                skip_calculated=self._opts.skip_calculated,
                skip_no_uc_ref=self._opts.skip_no_uc_ref,
                skip_system_tables=False,  # already handled above
                require_measures_or_numeric=self._opts.require_measures_or_numeric,
                columns=self._model.columns_for(table_name),
            )
            if skip:
                self._warnings.append(f"Skipping: {reason}")
                continue
            results.append(fact)

        if not results:
            self._warnings.append(
                "No fact tables detected — check relationships or use --fact-tables"
            )
        return results

    # ------------------------------------------------------------------
    # Join tree construction
    # ------------------------------------------------------------------

    def _build_join_tree(
        self,
        table_name: str,
        active_rels: list[Relationship],
        visited: set[str],
        depth: int,
    ) -> list[Join]:
        if depth >= self._opts.max_snowflake_depth:
            return []
        visited = visited | {table_name}
        joins: list[Join] = []

        # Find relationships where table_name is the FK side (from_table)
        outgoing = [r for r in active_rels if r.from_table == table_name]
        for rel in outgoing:
            dim_table = rel.to_table
            if dim_table in visited:
                continue
            dim_src = self._model.source_tables.get(
                dim_table, SourceTable(name=dim_table))
            uc_ref = dim_src.uc_ref or dim_table
            # ON clause uses "source." prefix for the fact/parent table's column
            on_clause = f"source.{rel.from_column} = {_alias(dim_table)}.{rel.to_column}"
            nested = self._build_join_tree(
                dim_table, active_rels, visited, depth + 1)
            joins.append(
                Join(
                    name=_alias(dim_table),
                    source_uc_ref=uc_ref,
                    on_clause=on_clause,
                    nested_joins=nested,
                )
            )
        return joins

    # ------------------------------------------------------------------
    # Dimension extraction
    # ------------------------------------------------------------------

    def _extract_dimensions(
        self,
        table_name: str,
        joins: list[Join],
        active_rels: list[Relationship],
    ) -> list[Dimension]:
        dimensions: list[Dimension] = []
        seen: set[str] = set()

        # Columns of the fact table itself (exclude FK columns)
        fk_cols = {
            r.from_column
            for r in active_rels
            if r.from_table == table_name
        }
        for col in self._model.columns_for(table_name):
            if col.column in fk_cols:
                continue
            dim_name = _friendly(col.column)
            if dim_name in seen:
                continue
            seen.add(dim_name)
            dimensions.append(
                Dimension(
                    name=dim_name,
                    expr=col.column,
                    comment=None,
                )
            )

        # Expose columns from joined dimension tables via dot-notation
        for join in joins:
            dim_table_name = _unalias(join.name, self._model.tables)
            for col in self._model.columns_for(dim_table_name):
                dim_name = f"{join.name}_{_friendly(col.column)}"
                if dim_name in seen:
                    continue
                seen.add(dim_name)
                dimensions.append(
                    Dimension(
                        name=dim_name,
                        expr=f"{join.name}.{col.column}",
                        comment=f"From joined table {dim_table_name}",
                    )
                )
            # Recurse for nested joins (snowflake)
            for nested_join in join.nested_joins:
                nested_table = _unalias(nested_join.name, self._model.tables)
                for col in self._model.columns_for(nested_table):
                    dim_name = f"{join.name}_{nested_join.name}_{_friendly(col.column)}"
                    if dim_name in seen:
                        continue
                    seen.add(dim_name)
                    dimensions.append(
                        Dimension(
                            name=dim_name,
                            expr=f"{join.name}.{nested_join.name}.{col.column}",
                            comment=f"From joined table {nested_table}",
                        )
                    )

        return dimensions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _alias(table_name: str) -> str:
    """Convert a table name to a short join alias."""
    # Use snake_case of the table name, lowercased
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", table_name)
    s = re.sub(r"[\s\-\.]", "_", s)
    return s.lower()


def _unalias(alias: str, all_tables: list[str]) -> str:
    """Find the original table name for a given alias."""
    # Try exact match first (case-insensitive)
    for t in all_tables:
        if _alias(t) == alias:
            return t
    # Fallback: return alias as-is (will produce empty column list)
    return alias


def _friendly(column_name: str) -> str:
    """Convert a raw column name to a friendly dimension name."""
    # Replace weird characters that might appear in PBI column names
    s = re.sub(r"[\s\-\.]+", "_", column_name)
    return s
