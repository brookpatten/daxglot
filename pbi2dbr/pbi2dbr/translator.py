"""DAX measure bridge: wraps daxglot.translate_measure with pbi2dbr post-processing."""

from __future__ import annotations

import re
from typing import Optional

from daxglot.measure_translator import (
    MeasureTranslation,
    WindowSpec,
    format_spec_to_dict,
    translate_measure,
)

from . import console
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
        period_dimensions: Optional[dict[str, str]] = None,
        dialect: str = "databricks",
    ) -> None:
        self._source_table = source_table
        self._joins = joins or []
        self._existing_measures = existing_measures or []
        self._date_dimension = date_dimension
        self._period_dimensions = period_dimensions
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
            period_dimensions=self._period_dimensions,
            synonyms=pbi_measure.synonyms or None,
            format_string=pbi_measure.format_string or None,
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

        measure = Measure(
            name=pbi_measure.name,
            expr=sql_expr,
            comment=pbi_measure.description or None,
            display_name=pbi_measure.name,
            window=window,
            is_approximate=result.is_approximate,
            original_dax=dax,
            warnings=result.warnings,
            synonyms=list(result.synonyms),
            format_spec=format_spec_to_dict(
                result.format_spec) if result.format_spec else None,
        )
        console.show_dax(
            pbi_measure.table,
            pbi_measure.name,
            dax,
            sql_expr,
            window,
            result.warnings,
        )
        return measure

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
    """Heuristically detect the date column name from a single DAX expression."""
    m = re.search(
        r"(?:SAMEPERIODLASTYEAR|DATESYTD|DATESQTD|DATESMTD|DATEADD|PARALLELPERIOD|TOTALYTD|TOTALQTD|TOTALMTD)\s*\(\s*['\"]?[\w\s]+['\"]?\[([^\]]+)\]",
        dax,
        re.IGNORECASE,
    )
    if m:
        col = m.group(1).lower().replace(" ", "_")
        return col
    return None


def _detect_date_dimension_from_measures(measures: list[PbiMeasure]) -> Optional[str]:
    """Scan all measure expressions and return the most-referenced date column name."""
    from collections import Counter
    hits: Counter = Counter()
    pattern = re.compile(
        r"(?:SAMEPERIODLASTYEAR|DATESYTD|DATESQTD|DATESMTD|DATEADD|"
        r"PARALLELPERIOD|TOTALYTD|TOTALQTD|TOTALMTD|PREVIOUSMONTH|PREVIOUSYEAR|"
        r"PREVIOUSQUARTER)\s*\(\s*['\"]?[\w\s]+['\"]?\[([^\]]+)\]",
        re.IGNORECASE,
    )
    for m in measures:
        for match in pattern.finditer(m.expression):
            col = match.group(1).lower().replace(" ", "_")
            hits[col] += 1
    return hits.most_common(1)[0][0] if hits else None


def _best_date_dimension(dimensions: list[Dimension], detected_col: Optional[str]) -> str:
    """Choose the best date dimension name from available dimensions.

    Priority:
    1. Dimension whose name exactly matches the detected column (e.g. ``order_date``).
    2. Dimension whose expr exactly matches the detected column.
    3. First dimension whose name contains ``date``.
    4. Fallback: ``"date"``.
    """
    if detected_col:
        for dim in dimensions:
            if dim.name.lower() == detected_col:
                return dim.name
        for dim in dimensions:
            if dim.expr.lower().replace(" ", "_") == detected_col:
                return dim.name
    for dim in dimensions:
        if "date" in dim.name.lower():
            return dim.name
    return "date"


def translate_fact_table(
    fact: FactTable,
    dialect: str = "databricks",
) -> list[Measure]:
    """Translate all measures for a FactTable.

    Returns a list of translated :class:`~pbi2dbr.models.Measure` objects in
    the order they should appear in the metric view (atomic measures first so
    composed measures can reference them via MEASURE()).
    """
    # Detect primary date dimension from measure expressions (best match across all measures)
    detected_col = _detect_date_dimension_from_measures(fact.measures)
    date_dim = _best_date_dimension(fact.dimensions, detected_col)

    # Build period dimension registry from dimensions that truncate to a period boundary
    period_dimensions = _build_period_dimensions(fact.dimensions)

    bridge = DaxBridge(
        source_table=fact.name,
        joins=fact.joins,
        date_dimension=date_dim,
        period_dimensions=period_dimensions or None,
        dialect=dialect,
    )

    translated: list[Measure] = []
    for pbi_m in fact.measures:
        m = bridge.translate(pbi_m)
        bridge._existing_measures.append(m)  # noqa: SLF001 — allow composability as we go
        translated.append(m)

    return translated


def _build_period_dimensions(dimensions: list[Dimension]) -> dict[str, str]:
    """Scan dimensions and return a mapping of period → dimension name.

    Detects:
    - Dimensions whose ``expr`` contains ``DATE_TRUNC('year'|'quarter'|'month', ...)``.
    - Dimensions whose *name* contains a period keyword as a fallback.

    DATE_TRUNC expressions always take priority over name-keyword matches,
    regardless of the order the dimensions appear in the list.
    """
    result: dict[str, str] = {}
    # First pass: DATE_TRUNC expressions (authoritative signal)
    for dim in dimensions:
        m = re.match(
            r"DATE_TRUNC\s*\(\s*['\"](\w+)['\"]", dim.expr, re.IGNORECASE)
        if m:
            period = m.group(1).lower()
            if period in ("year", "quarter", "month") and period not in result:
                result[period] = dim.name
    # Second pass: dimension name contains period keyword (fallback only)
    for dim in dimensions:
        name_lower = dim.name.lower()
        for period in ("year", "quarter", "month"):
            if period in name_lower and period not in result:
                result[period] = dim.name
    return result
