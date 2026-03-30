"""DAX measure bridge: wraps daxglot.translate_measure with pbi2dbr post-processing."""

from __future__ import annotations

import re
from typing import Optional

from daxglot.measure_translator import MeasureTranslation, WindowSpec, translate_measure

from .models import Dimension, FactTable, Join, Measure, PbiMeasure


class DaxBridge:
    """Translate PBI DAX measures to Databricks metric view Measure objects.

    Wraps :func:`daxglot.measure_translator.translate_measure` and applies
    column-reference normalisation and composability detection.

    Args:
        source_table: Name of the fact/source table (used for col ref normalisation).
        joins: Joins defined in the metric view (for col ref normalisation).
        existing_measures: Measures already translated in this view (for composability).
        date_dimension: Name of the date dimension for time-intelligence window mapping.
        dialect: SQL dialect passed to daxglot.
    """

    def __init__(
        self,
        source_table: str,
        joins: Optional[list[Join]] = None,
        existing_measures: Optional[list[Measure]] = None,
        date_dimension: str = "date",
        dialect: str = "databricks",
    ) -> None:
        self._source_table = source_table
        self._joins = joins or []
        self._existing_measures = existing_measures or []
        self._date_dimension = date_dimension
        self._dialect = dialect

        # Build alias → original column prefix map from joins
        self._join_aliases: dict[str, str] = {
            j.name: j.name for j in self._joins}
        # Recursively add nested join aliases
        for j in self._joins:
            for nj in j.nested_joins:
                self._join_aliases[nj.name] = f"{j.name}.{nj.name}"

    def translate(self, pbi_measure: PbiMeasure) -> Measure:
        """Translate a :class:`~pbi2dbr.models.PbiMeasure` to a :class:`~pbi2dbr.models.Measure`."""
        dax = pbi_measure.expression.strip()
        if not dax:
            return Measure(
                name=pbi_measure.name,
                expr="/* EMPTY DAX EXPRESSION */",
                comment=pbi_measure.description or None,
                display_name=pbi_measure.display_folder or pbi_measure.name,
                is_approximate=True,
                original_dax=dax,
                warnings=["Empty DAX expression"],
            )

        # Auto-detect date dimension from expression if not set
        date_dim = self._date_dimension
        detected = _detect_date_dimension(dax)
        if detected:
            date_dim = detected

        result: MeasureTranslation = translate_measure(
            dax,
            dialect=self._dialect,
            date_dimension=date_dim,
        )

        # Post-process: normalise column references
        sql_expr = self._normalise_column_refs(result.sql_expr)

        # Post-process: detect composability opportunities
        sql_expr = self._apply_composability(sql_expr)

        # Build window list in YAML-ready dict format
        window: list[dict] = []
        for ws in result.window_spec:
            window.append(
                {
                    "order": ws.order,
                    "range": ws.range,
                    "semiadditive": ws.semiadditive,
                }
            )

        return Measure(
            name=pbi_measure.name,
            expr=sql_expr,
            comment=pbi_measure.description or None,
            display_name=pbi_measure.name,
            window=window,
            is_approximate=result.is_approximate,
            original_dax=dax,
            warnings=result.warnings,
        )

    # ------------------------------------------------------------------
    # Column reference normalisation
    # ------------------------------------------------------------------

    def _normalise_column_refs(self, sql: str) -> str:
        """Replace TableName.ColumnName refs that refer to the source table.

        Transforms ``SalesTable.Amount`` → ``Amount`` for source columns.
        Leaves ``customer.name`` as-is (it's a join alias reference).
        """
        if not sql:
            return sql

        def replace_ref(m: re.Match) -> str:
            table_part = m.group(1)
            col_part = m.group(2)
            # If the table part matches the source table name → strip it
            if table_part.lower() == self._source_table.lower():
                return col_part
            # If the table part is a known join alias → keep as-is
            if table_part.lower() in {a.lower() for a in self._join_aliases}:
                return m.group(0)
            # Generic quoted identifier patterns ([TableName]) → strip table
            # strip source table references from [TableName].[ColumnName] style
            return col_part

        # Match Table.Column (bare identifiers — not inside strings)
        # Pattern: word.word where left side matches source table
        table_escaped = re.escape(self._source_table)
        sql = re.sub(
            rf"\b({table_escaped})\.([\w`\"]+)",
            replace_ref,
            sql,
            flags=re.IGNORECASE,
        )
        return sql

    # ------------------------------------------------------------------
    # Composability detection
    # ------------------------------------------------------------------

    def _apply_composability(self, sql: str) -> str:
        """Replace repeated sub-expressions with MEASURE(name) references."""
        if not self._existing_measures or not sql:
            return sql

        for m in self._existing_measures:
            # Only consider non-approximate, non-window measures for composability
            if m.is_approximate or m.window or not m.expr:
                continue
            # Simple check: if the exact expr appears as a sub-expression
            expr = m.expr.strip()
            if expr in sql and sql != expr:
                sql = sql.replace(expr, f"MEASURE({m.name})", 1)
        return sql


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _detect_date_dimension(dax: str) -> Optional[str]:
    """Heuristically detect the date column name from a DAX expression."""
    # Look for patterns like 'Date'[Date], Date[OrderDate], etc.
    m = re.search(
        r"(?:SAMEPERIODLASTYEAR|DATESYTD|DATESQTD|DATESMTD|DATEADD|PARALLELPERIOD|TOTALYTD|TOTALQTD|TOTALMTD)\s*\(\s*['\"]?[\w\s]+['\"]?\[([^\]]+)\]",
        dax,
        re.IGNORECASE,
    )
    if m:
        col = m.group(1).lower().replace(" ", "_")
        return col
    return None


def translate_fact_table(
    fact: FactTable,
    dialect: str = "databricks",
) -> list[Measure]:
    """Translate all measures for a FactTable.

    Returns a list of translated :class:`~pbi2dbr.models.Measure` objects in
    the order they should appear in the metric view (atomic measures first so
    composed measures can reference them via MEASURE()).
    """
    # Detect primary date dimension from dimension names
    date_dim = "date"
    for dim in fact.dimensions:
        if "date" in dim.name.lower() or "date" in dim.expr.lower():
            date_dim = dim.name
            break

    bridge = DaxBridge(
        source_table=fact.name,
        joins=fact.joins,
        date_dimension=date_dim,
        dialect=dialect,
    )

    translated: list[Measure] = []
    for pbi_m in fact.measures:
        m = bridge.translate(pbi_m)
        bridge._existing_measures.append(m)  # noqa: SLF001 — allow composability as we go
        translated.append(m)

    return translated
