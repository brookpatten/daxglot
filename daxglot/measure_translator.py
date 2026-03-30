"""DAX measure → Databricks metric view expression translator.

Translates a DAX measure expression into components suitable for use in
Databricks Unity Catalog metric view YAML definitions:

- ``sql_expr``: the aggregate SQL expression for the metric view ``expr:`` field.
- ``window_spec``: list of window specifications for time-intelligence measures.
- ``warnings``: any approximations or unsupported patterns detected.

Usage::

    from daxglot.measure_translator import translate_measure

    result = translate_measure("= CALCULATE(SUM(Sales[Amount]), SAMEPERIODLASTYEAR('Date'[Date]))")
    print(result.sql_expr)      # → SUM(Sales.Amount)
    print(result.window_spec)   # → [WindowSpec(order='date', range='trailing 1 year', ...)]

    result = translate_measure("= CALCULATE(SUM(Sales[Amount]), FILTER(Sales, Sales[Region] = \\"West\\"))")
    print(result.sql_expr)      # → SUM(Sales.Amount) FILTER (WHERE Sales.Region = 'West')
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, replace
from typing import Optional

import sqlglot.expressions as exp

from .ast_nodes import (
    Aggregation,
    All,
    AllExcept,
    BinaryOp,
    Calculate,
    ColumnRef,
    CountRows,
    DaxNode,
    Filter,
    FunctionCall,
    IfError,
    IfExpr,
    Iterator,
    KeepFilters,
    Literal,
    MeasureExpr,
    RemoveFilters,
    SwitchExpr,
    TableRef,
    UnaryOp,
    VarBlock,
    VarDef,
)
from .parser import ParseError, parse_dax
from .tokens import LexError
from .transpiler import DaxToSqlTranspiler, TranspilerError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Time-intelligence function names that can be converted to window specs.
_TIME_INTEL_FUNCS = frozenset(
    {
        "SAMEPERIODLASTYEAR",
        "PREVIOUSYEAR",
        "PREVIOUSQUARTER",
        "PREVIOUSMONTH",
        "NEXTYEAR",
        "NEXTQUARTER",
        "NEXTMONTH",
        "DATESYTD",
        "DATESQTD",
        "DATESMTD",
        "TOTALYTD",
        "TOTALQTD",
        "TOTALMTD",
        "DATEADD",
        "PARALLELPERIOD",
        "DATESBETWEEN",
        "DATESINPERIOD",
    }
)

# DATEADD / PARALLELPERIOD unit names → window unit strings
_INTERVAL_UNITS = {
    "DAY": "day",
    "MONTH": "month",
    "QUARTER": "quarter",
    "YEAR": "year",
}

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class WindowSpec:
    """Specification for a Databricks metric view window measure."""

    # name of the ordering dimension (typically a date dimension)
    order: str
    range: str          # window range expression, e.g. "trailing 1 year", "cumulative"
    semiadditive: str = "last"  # how to aggregate when the order dim is not in GROUP BY


@dataclass
class MeasureTranslation:
    """Result of translating a single DAX measure expression."""

    sql_expr: str
    """The aggregate SQL expression for the metric view ``expr:`` field."""

    window_spec: list[WindowSpec] = field(default_factory=list)
    """Non-empty for time-intelligence measures; defines the window array in YAML."""

    warnings: list[str] = field(default_factory=list)
    """Human-readable notes about approximations or unsupported patterns."""

    is_approximate: bool = False
    """True when the translation is a best-effort approximation."""

    original_dax: str = ""
    """Original DAX expression text (set by translate_measure)."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def translate_measure(
    dax_text: str,
    dialect: str = "databricks",
    date_dimension: str = "date",
) -> MeasureTranslation:
    """Translate a DAX measure expression to Databricks metric view components.

    Args:
        dax_text: DAX expression with or without a leading ``=``.
        dialect: Target SQL dialect for rendered expressions (passed to sqlglot).
        date_dimension: Name of the date dimension to use as the ``order:`` field
            when time-intelligence patterns are detected.

    Returns:
        :class:`MeasureTranslation` containing ``sql_expr``, optional
        ``window_spec``, and any ``warnings``.
    """
    text = dax_text.strip()
    if not text.startswith("="):
        text = "= " + text

    try:
        ast = parse_dax(text)
    except (ParseError, LexError) as exc:
        return MeasureTranslation(
            sql_expr=f"/* PARSE_ERROR: {exc} */",
            warnings=[f"Parse error: {exc}"],
            is_approximate=True,
            original_dax=dax_text,
        )

    node = ast.expr if isinstance(ast, MeasureExpr) else ast
    result = _translate_node(node, dialect=dialect,
                             date_dimension=date_dimension)
    result.original_dax = dax_text
    return result


# ---------------------------------------------------------------------------
# Internal: pattern dispatch
# ---------------------------------------------------------------------------


def _translate_node(
    node: DaxNode,
    dialect: str,
    date_dimension: str,
) -> MeasureTranslation:
    """Dispatch to the appropriate pattern handler."""

    if isinstance(node, (Aggregation, CountRows)):
        return _simple_agg(node, dialect)

    if isinstance(node, Calculate):
        return _translate_calculate(node, dialect, date_dimension)

    if isinstance(node, VarBlock):
        return _translate_var_block(node, dialect, date_dimension)

    if isinstance(node, BinaryOp):
        return _translate_binary(node, dialect, date_dimension)

    if isinstance(node, (IfExpr, IfError, SwitchExpr)):
        return _translate_conditional(node, dialect)

    if isinstance(node, FunctionCall):
        return _translate_function_call(node, dialect, date_dimension)

    if isinstance(node, Iterator):
        return _translate_iterator(node, dialect)

    return _fallback(node, dialect)


# ---------------------------------------------------------------------------
# Pattern handlers
# ---------------------------------------------------------------------------


def _simple_agg(node: DaxNode, dialect: str) -> MeasureTranslation:
    try:
        return MeasureTranslation(sql_expr=_render(node, dialect))
    except TranspilerError as exc:
        return _fallback(node, dialect, hint=str(exc))


def _translate_calculate(
    node: Calculate,
    dialect: str,
    date_dimension: str,
) -> MeasureTranslation:
    warnings: list[str] = []
    time_intel: list[FunctionCall] = []
    filter_conditions: list[DaxNode] = []

    for f in node.filters:
        if isinstance(f, FunctionCall) and f.name.upper() in _TIME_INTEL_FUNCS:
            time_intel.append(f)
        elif isinstance(f, Filter):
            filter_conditions.append(f.condition)
        elif isinstance(f, BinaryOp):
            # DAX direct predicate: CALCULATE(SUM(...), Table[col] = "val")
            filter_conditions.append(f)
        elif isinstance(f, (All, AllExcept, RemoveFilters)):
            fname = type(f).__name__ if not isinstance(
                f, FunctionCall) else f.name.upper()
            warnings.append(
                f"{fname} filter removed — not applicable in metric views (removes filter context)"
            )
        elif isinstance(f, KeepFilters):
            # KEEPFILTERS wraps another filter — extract inner
            filter_conditions.append(f.expr)
        elif isinstance(f, FunctionCall) and f.name.upper() in (
            "ALL",
            "ALLEXCEPT",
            "ALLNOBLANKROW",
            "ALLSELECTED",
        ):
            warnings.append(
                f"{f.name.upper()}() filter removed — not applicable in metric views"
            )
        else:
            warnings.append(
                f"Unsupported CALCULATE modifier {type(f).__name__} "
                f"— base aggregate returned"
            )

    base = _translate_node(node.expr, dialect, date_dimension)

    # --- Time-intelligence → window spec ---
    if time_intel:
        wspec: list[WindowSpec] = []
        for fc in time_intel:
            ws = _resolve_window(fc, date_dimension)
            if ws:
                wspec.extend(ws)
            else:
                warnings.append(
                    f"{fc.name.upper()}() could not be converted to a window spec "
                    f"— emitting base aggregate"
                )
        return MeasureTranslation(
            sql_expr=base.sql_expr,
            window_spec=wspec,
            warnings=base.warnings + warnings,
            is_approximate=bool(warnings),
        )

    # --- Filter conditions → FILTER (WHERE ...) clause ---
    if filter_conditions:
        cond_sqls: list[str] = []
        for cond in filter_conditions:
            try:
                cond_sqls.append(_render(cond, dialect))
            except TranspilerError as exc:
                warnings.append(f"Could not render filter condition: {exc}")
        if cond_sqls:
            combined = " AND ".join(cond_sqls)
            return MeasureTranslation(
                sql_expr=f"{base.sql_expr} FILTER (WHERE {combined})",
                warnings=base.warnings + warnings,
                is_approximate=bool(warnings),
            )

    # --- Only non-filter modifiers → return base aggregate ---
    return MeasureTranslation(
        sql_expr=base.sql_expr,
        warnings=base.warnings + warnings,
        is_approximate=bool(warnings),
    )


def _resolve_window(fc: FunctionCall, date_dimension: str) -> list[WindowSpec]:
    """Map a time-intelligence FunctionCall to WindowSpec entries."""
    fname = fc.name.upper()

    # Derive date column name from the first argument if it's a ColumnRef
    date_col = date_dimension
    if fc.args and isinstance(fc.args[0], ColumnRef):
        date_col = fc.args[0].column.lower().replace(" ", "_")

    if fname == "SAMEPERIODLASTYEAR":
        return [WindowSpec(order=date_col, range="trailing 1 year")]

    if fname == "PREVIOUSYEAR":
        return [WindowSpec(order=date_col, range="trailing 1 year")]

    if fname == "PREVIOUSQUARTER":
        return [WindowSpec(order=date_col, range="trailing 1 quarter")]

    if fname == "PREVIOUSMONTH":
        return [WindowSpec(order=date_col, range="trailing 1 month")]

    if fname == "NEXTYEAR":
        return [WindowSpec(order=date_col, range="leading 1 year")]

    if fname == "NEXTQUARTER":
        return [WindowSpec(order=date_col, range="leading 1 quarter")]

    if fname == "NEXTMONTH":
        return [WindowSpec(order=date_col, range="leading 1 month")]

    if fname in ("DATESYTD", "TOTALYTD"):
        # Cumulative year-to-date: aggregate cumulatively, reset at year boundary
        year_dim = _derive_period_dim(date_col, "year")
        return [
            WindowSpec(order=date_col, range="cumulative"),
            WindowSpec(order=year_dim, range="current"),
        ]

    if fname in ("DATESQTD", "TOTALQTD"):
        quarter_dim = _derive_period_dim(date_col, "quarter")
        return [
            WindowSpec(order=date_col, range="cumulative"),
            WindowSpec(order=quarter_dim, range="current"),
        ]

    if fname in ("DATESMTD", "TOTALMTD"):
        month_dim = _derive_period_dim(date_col, "month")
        return [
            WindowSpec(order=date_col, range="cumulative"),
            WindowSpec(order=month_dim, range="current"),
        ]

    if fname == "DATEADD":
        # DATEADD(date_col, offset, unit)
        if len(fc.args) >= 3:
            n_node, unit_node = fc.args[1], fc.args[2]
            n = _extract_int_offset(n_node)
            raw_unit = _extract_unit_name(unit_node)
            unit = _INTERVAL_UNITS.get(raw_unit, raw_unit.lower())
            direction = "trailing" if n < 0 else "leading"
            count = abs(n) if n != 0 else 1
            return [WindowSpec(order=date_col, range=f"{direction} {count} {unit}")]
        return []

    if fname == "PARALLELPERIOD":
        # PARALLELPERIOD(date_col, offset, unit) — similar to DATEADD
        if len(fc.args) >= 3:
            n_node, unit_node = fc.args[1], fc.args[2]
            n = _extract_int_offset(n_node)
            raw_unit = _extract_unit_name(unit_node)
            unit = _INTERVAL_UNITS.get(raw_unit, raw_unit.lower())
            direction = "trailing" if n < 0 else "leading"
            count = abs(n) if n != 0 else 1
            return [WindowSpec(order=date_col, range=f"{direction} {count} {unit}")]
        return []

    # DATESBETWEEN / DATESINPERIOD — cannot express as simple window
    return []


def _derive_period_dim(date_col: str, period: str) -> str:
    """Derive a period dimension name from a date column name."""
    for suffix in ("date", "dt", "day"):
        if suffix in date_col:
            return date_col.replace(suffix, period)
    return f"{date_col}_{period}"


def _extract_int_offset(node: DaxNode) -> int:
    """Extract a signed integer from a Literal or UnaryOp(-,Literal) node.

    Returns -1 (trailing direction) if the node type is not recognised.
    """
    if isinstance(node, Literal) and node.kind == "NUMBER":
        return int(float(node.value))
    if isinstance(node, UnaryOp) and node.op == "-" and isinstance(node.expr, Literal):
        return -int(float(node.expr.value))
    return -1


def _extract_unit_name(node: DaxNode) -> str:
    """Extract the interval unit string from a Literal, TableRef, or FunctionCall node.

    DAX time-intelligence functions express the unit as identifiers (MONTH, YEAR etc.)
    which the parser may return as ``TableRef`` (unquoted) or ``Literal`` nodes.
    """
    if isinstance(node, Literal):
        return str(node.value).upper()
    if isinstance(node, TableRef):
        return node.name.upper()
    if isinstance(node, FunctionCall) and not node.args:
        # e.g. MONTH as a zero-arg function call
        return node.name.upper()
    return ""


def _translate_var_block(
    node: VarBlock,
    dialect: str,
    date_dimension: str,
) -> MeasureTranslation:
    """Inline scalar VAR definitions and re-translate the RETURN expression."""
    # Build var map from the original definitions
    var_map: dict[str, DaxNode] = {v.name: v.expr for v in node.vars}

    # Try inlining and re-translating
    try:
        inlined = _inline_vars(node.return_expr, var_map)
        result = _translate_node(inlined, dialect, date_dimension)
        if not result.is_approximate:
            return result
        # Inlined but approximate — still better than a raw CTE
        result.warnings.insert(0, "VAR block inlined into return expression")
        return result
    except Exception as exc:  # noqa: BLE001
        pass

    # Fallback: transpile the whole VAR block (generates CTE-style SQL)
    try:
        sql = _render(node, dialect)
        return MeasureTranslation(
            sql_expr=sql,
            warnings=[
                "VAR/RETURN translated to CTE-style SQL — verify compatibility with metric views"],
            is_approximate=True,
        )
    except (TranspilerError, Exception) as exc:  # noqa: BLE001
        return MeasureTranslation(
            sql_expr="/* UNSUPPORTED: VAR block */",
            warnings=[f"Could not translate VAR block: {exc}"],
            is_approximate=True,
        )


def _inline_vars(node: DaxNode, var_map: dict[str, DaxNode]) -> DaxNode:
    """Recursively substitute variable references in an expression tree.

    Variable references appear as ``TableRef`` (bare name) or ``ColumnRef``
    (name in brackets with no table prefix) nodes whose name matches a var.
    """
    # Substitute matching leaf nodes, then recursively inline the substituted value
    if isinstance(node, TableRef) and node.name in var_map:
        return _inline_vars(var_map[node.name], var_map)
    if isinstance(node, ColumnRef) and node.table is None and node.column in var_map:
        return _inline_vars(var_map[node.column], var_map)

    # Recursively rebuild the node with inlined children
    updates: dict[str, object] = {}
    changed = False
    for f in fields(node):
        val = getattr(node, f.name)
        if isinstance(val, DaxNode):
            new_val = _inline_vars(val, var_map)
            if new_val is not val:
                updates[f.name] = new_val
                changed = True
        elif isinstance(val, (list, tuple)):
            new_items: list[object] = []
            for item in val:
                if isinstance(item, DaxNode):
                    new_item = _inline_vars(item, var_map)
                    new_items.append(new_item)
                    if new_item is not item:
                        changed = True
                else:
                    new_items.append(item)
            if changed and new_items:
                updates[f.name] = type(val)(new_items)
    if changed:
        return replace(node, **updates)
    return node


def _translate_binary(
    node: BinaryOp,
    dialect: str,
    date_dimension: str,
) -> MeasureTranslation:
    """Translate binary operations (ratios, arithmetic on aggregates)."""
    try:
        return MeasureTranslation(sql_expr=_render(node, dialect))
    except TranspilerError as exc:
        return _fallback(node, dialect, hint=str(exc))


def _translate_conditional(node: DaxNode, dialect: str) -> MeasureTranslation:
    """Translate IF / IFERROR / SWITCH expressions."""
    try:
        return MeasureTranslation(sql_expr=_render(node, dialect))
    except TranspilerError as exc:
        return _fallback(node, dialect, hint=str(exc))


def _translate_function_call(
    node: FunctionCall,
    dialect: str,
    date_dimension: str,
) -> MeasureTranslation:
    """Translate generic function calls including DIVIDE and time-intel in non-CALCULATE position."""
    fname = node.name.upper()

    # TOTALYTD / TOTALQTD / TOTALMTD used directly (not wrapped in CALCULATE)
    # Syntax: TOTALYTD(expr, date_col)
    if fname in ("TOTALYTD", "TOTALQTD", "TOTALMTD") and len(node.args) >= 2:
        inner_result = _translate_node(node.args[0], dialect, date_dimension)
        fake_fc = FunctionCall(name=fname, args=(node.args[1],))
        wspec = _resolve_window(fake_fc, date_dimension)
        return MeasureTranslation(
            sql_expr=inner_result.sql_expr,
            window_spec=wspec,
            warnings=inner_result.warnings,
            is_approximate=inner_result.is_approximate,
        )

    try:
        return MeasureTranslation(sql_expr=_render(node, dialect))
    except TranspilerError as exc:
        return _fallback(node, dialect, hint=str(exc))


def _translate_iterator(node: Iterator, dialect: str) -> MeasureTranslation:
    """Iterator functions (SUMX, AVERAGEX, etc.) — best-effort via transpiler."""
    try:
        sql = _render(node, dialect)
        return MeasureTranslation(
            sql_expr=sql,
            warnings=[
                f"{node.func}() is an iterator function — "
                "complex row-context semantics may not be preserved in metric views"
            ],
            is_approximate=True,
        )
    except TranspilerError:
        return _fallback(node, dialect)


def _fallback(node: DaxNode, dialect: str, hint: str = "") -> MeasureTranslation:
    try:
        sql = _render(node, dialect)
        msg = f"Expression type {type(node).__name__} used best-effort transpilation"
        if hint:
            msg += f": {hint}"
        return MeasureTranslation(sql_expr=sql, warnings=[msg], is_approximate=True)
    except (TranspilerError, Exception) as exc:  # noqa: BLE001
        return MeasureTranslation(
            sql_expr=f"/* UNSUPPORTED: {type(node).__name__} */",
            warnings=[f"Could not translate {type(node).__name__}: {exc}"],
            is_approximate=True,
        )


# ---------------------------------------------------------------------------
# Rendering helper
# ---------------------------------------------------------------------------

_transpiler = DaxToSqlTranspiler()


def _render(node: DaxNode, dialect: str = "databricks") -> str:
    """Render an AST node to a SQL string via the transpiler."""
    return _transpiler.transpile(node).sql(dialect=dialect)
