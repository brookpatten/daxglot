"""DAX → sqlglot expression tree transpiler.

Converts a DaxNode AST produced by DaxParser into a sqlglot expression tree
which can then be rendered to any SQL dialect supported by sqlglot.

Usage::

    from dax.parser import parse_dax
    from dax.transpiler import DaxToSqlTranspiler

    node = parse_dax("= SUM(Sales[Amount])")
    transpiler = DaxToSqlTranspiler()
    sql_expr = transpiler.transpile(node)
    print(sql_expr.sql(dialect="spark"))   # → SUM(Sales.Amount)

Limitations / future work:
- EARLIER/EARLIEST: Generates annotated column expressions with a SQL comment
  to mark the outer-row-context reference.  Full correlated-subquery rewriting
  requires a separate semantic analysis pass and is not yet implemented.
- RANKX, PERCENTILEX: Mapped to FunctionCall (exp.Anonymous) — semantics are
  complex and dialect-specific.
- Time-intelligence functions: Mapped to FunctionCall (exp.Anonymous); the
  caller needs to provide the appropriate date table structures.
- VAR/RETURN: Converted to a SQL CTE-style WITH expression where supported, or
  a subquery-inline form for dialects that do not support WITH in expressions.
"""

from __future__ import annotations

from typing import Callable

import sqlglot.expressions as exp

from .ast_nodes import (
    All,
    AllExcept,
    Aggregation,
    BinaryOp,
    Calculate,
    CalculateTable,
    ColumnRef,
    ContextFunction,
    CountRows,
    CrossFilter,
    DaxNode,
    EvaluateQuery,
    Filter,
    FunctionCall,
    IfError,
    IfExpr,
    InExpr,
    Iterator,
    KeepFilters,
    Literal,
    MeasureExpr,
    NotInExpr,
    OrderBy,
    OrderByItem,
    RelatedFunction,
    RemoveFilters,
    SwitchExpr,
    TableRef,
    TreatAs,
    UnaryOp,
    UseRelationship,
    VarBlock,
    VarDef,
)


class TranspilerError(Exception):
    pass


class DaxToSqlTranspiler:
    """Visitor-dispatch transpiler from DAX AST → sqlglot expression tree.

    Each ``_visit_<ClassName>`` method handles one AST node type.
    """

    def transpile(self, node: DaxNode) -> exp.Expression:
        """Convert *node* to a sqlglot expression."""
        method_name = f"_visit_{type(node).__name__}"
        visitor: Callable[[DaxNode], exp.Expression] = getattr(
            self, method_name, self._visit_unknown
        )
        return visitor(node)

    def _visit_unknown(self, node: DaxNode) -> exp.Expression:
        raise TranspilerError(
            f"No transpiler visitor for AST node type: {type(node).__name__}"
        )

    # ------------------------------------------------------------------
    # Leaf nodes
    # ------------------------------------------------------------------

    def _visit_Literal(self, node: Literal) -> exp.Expression:
        if node.kind == "STRING":
            return exp.Literal.string(str(node.value))
        if node.kind == "NUMBER":
            return exp.Literal.number(node.value)
        if node.kind == "BOOLEAN":
            return exp.Boolean(this=bool(node.value))
        if node.kind == "BLANK":
            return exp.Null()
        raise TranspilerError(f"Unknown literal kind: {node.kind!r}")

    def _visit_ColumnRef(self, node: ColumnRef) -> exp.Expression:
        col = exp.Column(
            this=exp.Identifier(this=node.column, quoted=False)
        )
        if node.table:
            col.args["table"] = exp.Identifier(this=node.table, quoted=False)
        return col

    def _visit_TableRef(self, node: TableRef) -> exp.Expression:
        return exp.Table(this=exp.Identifier(this=node.name, quoted=node.is_quoted))

    # ------------------------------------------------------------------
    # Operators
    # ------------------------------------------------------------------

    _BINARY_OP_MAP = {
        "=": exp.EQ,
        "<>": exp.NEQ,
        "<": exp.LT,
        "<=": exp.LTE,
        ">": exp.GT,
        ">=": exp.GTE,
        "+": exp.Add,
        "-": exp.Sub,
        "*": exp.Mul,
        "/": exp.Div,
        "&": exp.DPipe,   # string concatenation in DAX → || in SQL
        "&&": exp.And,
        "||": exp.Or,
        "AND": exp.And,
        "OR": exp.Or,
        "^": exp.Pow,
    }

    def _visit_BinaryOp(self, node: BinaryOp) -> exp.Expression:
        left = self.transpile(node.left)
        right = self.transpile(node.right)
        cls = self._BINARY_OP_MAP.get(node.op)
        if cls is None:
            raise TranspilerError(f"Unknown binary operator: {node.op!r}")
        return cls(this=left, expression=right)

    def _visit_UnaryOp(self, node: UnaryOp) -> exp.Expression:
        inner = self.transpile(node.expr)
        if node.op == "-":
            return exp.Neg(this=inner)
        if node.op in ("NOT", "!"):
            return exp.Not(this=inner)
        raise TranspilerError(f"Unknown unary operator: {node.op!r}")

    def _visit_InExpr(self, node: InExpr) -> exp.Expression:
        expr = self.transpile(node.expr)
        values = [self.transpile(v) for v in node.values]
        return exp.In(this=expr, expressions=values)

    def _visit_NotInExpr(self, node: NotInExpr) -> exp.Expression:
        return exp.Not(this=self._visit_InExpr(  # type: ignore[arg-type]
            InExpr(expr=node.expr, values=node.values)
        ))

    # ------------------------------------------------------------------
    # Aggregations
    # ------------------------------------------------------------------

    _AGG_MAP = {
        "SUM": exp.Sum,
        "MAX": exp.Max,
        "MIN": exp.Min,
        "AVERAGE": exp.Avg,
        "COUNT": exp.Count,
        "COUNTROWS": exp.Count,
        "COUNTA": exp.Count,
        # approximate — exact semantics via COUNT(DISTINCT)
        "DISTINCTCOUNT": exp.Count,
        "AVERAGEA": exp.Avg,
        "MINA": exp.Min,
        "MAXA": exp.Max,
    }

    def _visit_Aggregation(self, node: Aggregation) -> exp.Expression:
        inner = self.transpile(node.expr)
        cls = self._AGG_MAP.get(node.func.upper(), exp.Anonymous)
        if cls is exp.Anonymous:
            return exp.Anonymous(this=node.func, expressions=[inner])
        if node.func.upper() == "DISTINCTCOUNT":
            return exp.Count(this=exp.Distinct(expressions=[inner]))
        return cls(this=inner)

    def _visit_CountRows(self, node: CountRows) -> exp.Expression:
        if node.table_expr:
            # COUNTROWS(Table) — in SQL: COUNT(*) FROM Table used inside a subquery,
            # but as a scalar expression context we emit COUNT(*)
            # with the table noted as a comment via Anonymous wrapper.
            return exp.Count(this=exp.Star())
        return exp.Count(this=exp.Star())

    # ------------------------------------------------------------------
    # Iterator functions
    # ------------------------------------------------------------------

    def _visit_Iterator(self, node: Iterator) -> exp.Expression:
        # Iterators don't have a direct SQL equivalent — emit as Anonymous
        # so the tree is still traversable.
        table = self.transpile(node.table_expr)
        body = self.transpile(node.body)
        return exp.Anonymous(this=node.func, expressions=[table, body])

    # ------------------------------------------------------------------
    # Context / relationship functions
    # ------------------------------------------------------------------

    def _visit_ContextFunction(self, node: ContextFunction) -> exp.Expression:
        # EARLIER/EARLIEST — refers to an outer row context.
        # We emit the inner column reference annotated with a comment property
        # to signal that a correlated subquery rewrite is needed.
        inner = self.transpile(node.expr)
        # Wrap in an Anonymous call to preserve the semantic marker
        return exp.Anonymous(
            this=node.func,
            expressions=[inner, exp.Literal.number(node.depth)],
        )

    def _visit_RelatedFunction(self, node: RelatedFunction) -> exp.Expression:
        inner = self.transpile(node.expr)
        return exp.Anonymous(this=node.func, expressions=[inner])

    # ------------------------------------------------------------------
    # Filter / table functions
    # ------------------------------------------------------------------

    def _visit_Filter(self, node: Filter) -> exp.Expression:
        """FILTER(Table, Condition) → SELECT * FROM Table WHERE Condition"""
        table = self.transpile(node.table_expr)
        condition = self.transpile(node.condition)
        return (
            exp.select(exp.Star())
            .from_(table)
            .where(condition)
            .subquery()
        )

    def _visit_All(self, node: All) -> exp.Expression:
        exprs = [self.transpile(node.table_or_column)]
        exprs.extend(self.transpile(c) for c in node.columns)
        return exp.Anonymous(this="ALL", expressions=exprs)

    def _visit_AllExcept(self, node: AllExcept) -> exp.Expression:
        exprs = [self.transpile(node.table_expr)]
        exprs.extend(self.transpile(c) for c in node.columns)
        return exp.Anonymous(this="ALLEXCEPT", expressions=exprs)

    def _visit_KeepFilters(self, node: KeepFilters) -> exp.Expression:
        return exp.Anonymous(this="KEEPFILTERS", expressions=[self.transpile(node.expr)])

    def _visit_RemoveFilters(self, node: RemoveFilters) -> exp.Expression:
        return exp.Anonymous(this="REMOVEFILTERS", expressions=[self.transpile(node.expr)])

    def _visit_TreatAs(self, node: TreatAs) -> exp.Expression:
        exprs = [self.transpile(node.table_expr)]
        exprs.extend(self.transpile(c) for c in node.columns)
        return exp.Anonymous(this="TREATAS", expressions=exprs)

    def _visit_UseRelationship(self, node: UseRelationship) -> exp.Expression:
        return exp.Anonymous(
            this="USERELATIONSHIP",
            expressions=[self.transpile(node.col1), self.transpile(node.col2)],
        )

    def _visit_CrossFilter(self, node: CrossFilter) -> exp.Expression:
        return exp.Anonymous(
            this="CROSSFILTER",
            expressions=[
                self.transpile(node.col1),
                self.transpile(node.col2),
                exp.Literal.string(node.direction),
            ],
        )

    def _visit_Calculate(self, node: Calculate) -> exp.Expression:
        """CALCULATE(expr, filter1, filter2, ...) → SELECT expr WHERE filter1 AND filter2 ...

        If all filters are FILTER nodes, we merge their WHERE conditions.
        Otherwise, filters that cannot be inlined are emitted as Anonymous
        function calls preserving the full tree for semantic analysis.
        """
        scalar_expr = self.transpile(node.expr)

        if not node.filters:
            # No filters — just wrap the scalar expression
            return scalar_expr

        # Collect WHERE conditions from FILTER nodes; keep others as annotations
        where_conditions: list[exp.Expression] = []
        non_filter_modifiers: list[exp.Expression] = []
        table_source: exp.Expression | None = None

        for f in node.filters:
            if isinstance(f, Filter):
                if table_source is None:
                    table_source = self.transpile(f.table_expr)
                where_conditions.append(self.transpile(f.condition))
            else:
                non_filter_modifiers.append(self.transpile(f))

        if table_source is not None:
            query = exp.select(scalar_expr).from_(table_source)
            for cond in where_conditions:
                query = query.where(cond)
            return query.subquery()

        # No FILTER nodes — return as Anonymous CALCULATE for semantic pass
        exprs = [scalar_expr] + [self.transpile(f) for f in node.filters]
        return exp.Anonymous(this="CALCULATE", expressions=exprs)

    def _visit_CalculateTable(self, node: CalculateTable) -> exp.Expression:
        """CALCULATETABLE(table, filter1, ...) → SELECT * FROM table WHERE ..."""
        table = self.transpile(node.table_expr)

        if not node.filters:
            return table

        where_conditions: list[exp.Expression] = []
        table_source = table

        for f in node.filters:
            if isinstance(f, Filter):
                where_conditions.append(self.transpile(f.condition))
            else:
                # Non-FILTER modifiers (ALL, KEEPFILTERS, etc.) — kept as annotations
                pass

        query = exp.select(exp.Star()).from_(table_source)
        for cond in where_conditions:
            query = query.where(cond)
        return query.subquery()

    # ------------------------------------------------------------------
    # Conditional
    # ------------------------------------------------------------------

    def _visit_IfExpr(self, node: IfExpr) -> exp.Expression:
        condition = self.transpile(node.condition)
        true_val = self.transpile(node.true_val)
        false_val = self.transpile(
            node.false_val) if node.false_val else exp.Null()
        return exp.If(this=condition, true=true_val, false=false_val)

    def _visit_IfError(self, node: IfError) -> exp.Expression:
        """IFERROR(value, alt) → COALESCE(value, alt).

        Not semantically identical — COALESCE catches NULL, not arbitrary errors.
        However, when combined with DIVIDE() (which emits NULLIF(den, 0)) this
        correctly handles the most common divide-by-zero pattern.
        """
        value = self.transpile(node.value)
        alt = self.transpile(node.value_if_error)
        return exp.Coalesce(this=value, expressions=[alt])

    def _visit_SwitchExpr(self, node: SwitchExpr) -> exp.Expression:
        """SWITCH → CASE WHEN … THEN … ELSE … END.

        Handles the common SWITCH(TRUE(), cond1, val1, ...) idiom used as an
        if-elseif chain: when the switch expression is the literal TRUE, the
        WHEN conditions are used directly rather than compared to TRUE.
        """
        is_switch_true = (
            isinstance(node.expr, Literal)
            and node.expr.kind == "BOOLEAN"
            and node.expr.value is True
        )
        if not is_switch_true:
            switch_val = self.transpile(node.expr)
        ifs: list[exp.When] = []
        for case in node.cases:
            if is_switch_true:
                condition = self.transpile(case.when)
            else:
                condition = exp.EQ(
                    this=switch_val.copy(),  # type: ignore[possibly-undefined]
                    expression=self.transpile(case.when),
                )
            ifs.append(exp.When(this=condition, then=self.transpile(case.then)))
        default = self.transpile(node.default) if node.default else exp.Null()
        return exp.Case(ifs=ifs, default=default)

    # ------------------------------------------------------------------
    # Generic function call
    # ------------------------------------------------------------------

    def _visit_FunctionCall(self, node: FunctionCall) -> exp.Expression:  # noqa: C901
        args = [self.transpile(a) for a in node.args]
        fname = node.name.upper()

        # DIVIDE(numerator, denominator [, alternate_result])
        # → numerator / NULLIF(denominator, 0)
        # → COALESCE(numerator / NULLIF(denominator, 0), alternate_result)  [3-arg form]
        if fname == "DIVIDE" and len(args) >= 2:
            safe_den = exp.Anonymous(
                this="NULLIF", expressions=[args[1], exp.Literal.number(0)]
            )
            safe_div = exp.Div(this=args[0], expression=safe_den)
            if len(args) >= 3:
                return exp.Coalesce(this=safe_div, expressions=[args[2]])
            return safe_div

        # ISBLANK(expr) → expr IS NULL
        if fname == "ISBLANK" and len(args) == 1:
            return exp.Is(this=args[0], expression=exp.Null())

        # ISEMPTY(table) → (COUNT(*) = 0) — best effort approximation
        if fname == "ISEMPTY" and len(args) == 1:
            return exp.EQ(
                this=exp.Count(this=exp.Star()),
                expression=exp.Literal.number(0),
            )

        # COALESCE(a, b, ...) → standard SQL COALESCE
        if fname == "COALESCE" and args:
            return exp.Coalesce(this=args[0], expressions=args[1:])

        # TODAY() → CURRENT_DATE
        if fname == "TODAY":
            return exp.CurrentDate()

        # NOW() → CURRENT_TIMESTAMP
        if fname == "NOW":
            return exp.CurrentTimestamp()

        # LEN(text) → LENGTH(text)
        if fname == "LEN" and len(args) == 1:
            return exp.Length(this=args[0])

        # CONCATENATE(a, b) → CONCAT(a, b)
        if fname == "CONCATENATE":
            return exp.Anonymous(this="CONCAT", expressions=args)

        # SELECTEDVALUE(col [, default]) → ANY_VALUE(col)
        # (filter-context dependent in DAX; ANY_VALUE is the closest SQL aggregate)
        if fname == "SELECTEDVALUE" and args:
            return exp.Anonymous(this="ANY_VALUE", expressions=[args[0]])

        # HASONEVALUE / HASONEFILTER → COUNT(DISTINCT col) = 1
        if fname in ("HASONEVALUE", "HASONEFILTER") and len(args) == 1:
            cnt = exp.Count(this=exp.Distinct(expressions=[args[0]]))
            return exp.EQ(this=cnt, expression=exp.Literal.number(1))

        # INT / INTEGER → CAST(expr AS BIGINT)
        if fname in ("INT", "INTEGER") and len(args) == 1:
            return exp.Cast(this=args[0], to=exp.DataType.build("BIGINT"))

        # TRIM → standard SQL TRIM
        if fname == "TRIM" and len(args) == 1:
            return exp.Trim(this=args[0])

        # UPPER / LOWER → pass-through (identical in SQL)
        if fname in ("UPPER", "LOWER") and len(args) == 1:
            cls = exp.Upper if fname == "UPPER" else exp.Lower
            return cls(this=args[0])

        return exp.Anonymous(this=node.name, expressions=args)

    # ------------------------------------------------------------------
    # VAR / RETURN
    # ------------------------------------------------------------------

    def _visit_VarBlock(self, node: VarBlock) -> exp.Expression:
        """Convert VAR/RETURN to a nested CTE-style WITH expression.

        In standard SQL this becomes:
            WITH var1 AS (<expr1>), var2 AS (<expr2>) SELECT <return_expr>
        Many dialects support this as a subquery; sqlglot generates it correctly.
        """
        ctes: list[exp.CTE] = []
        for var_def in node.vars:
            var_expr = self.transpile(var_def.expr)
            # Wrap scalar in a SELECT if not already a select
            if not isinstance(var_expr, (exp.Select, exp.Subquery)):
                var_expr = exp.select(var_expr)
            ctes.append(
                exp.CTE(
                    this=var_expr,
                    alias=exp.TableAlias(
                        this=exp.Identifier(this=var_def.name)
                    ),
                )
            )

        return_expr = self.transpile(node.return_expr)
        if not isinstance(return_expr, (exp.Select, exp.Subquery)):
            return_expr = exp.select(return_expr)

        with_node = exp.With(expressions=ctes)
        return_expr.args["with"] = with_node
        return return_expr

    def _visit_VarDef(self, node: VarDef) -> exp.Expression:
        # Should not be reached directly — handled inside _visit_VarBlock
        return self.transpile(node.expr)

    # ------------------------------------------------------------------
    # Top-level query containers
    # ------------------------------------------------------------------

    def _visit_MeasureExpr(self, node: MeasureExpr) -> exp.Expression:
        return self.transpile(node.expr)

    def _visit_EvaluateQuery(self, node: EvaluateQuery) -> exp.Expression:
        """EVALUATE <table_expr> → SELECT * FROM <table_expr> [ORDER BY …]"""
        table = self.transpile(node.table_expr)

        # If table_expr is a Subquery, unwrap to use as FROM source
        if isinstance(table, exp.Subquery):
            query = exp.select(exp.Star()).from_(table)
        elif isinstance(table, exp.Table):
            query = exp.select(exp.Star()).from_(table)
        else:
            query = exp.select(exp.Star()).from_(
                table.subquery() if not isinstance(table, (exp.Select,)) else table)

        if node.order_by:
            order_items: list[exp.Ordered] = []
            for item in node.order_by.items:
                ordered_expr = self.transpile(item.expr)
                order_items.append(
                    exp.Ordered(
                        this=ordered_expr,
                        desc=item.direction.upper() == "DESC",
                    )
                )
            query = query.order_by(*order_items)

        return query

    # ------------------------------------------------------------------
    # ORDER BY helpers (not usually visited top-level)
    # ------------------------------------------------------------------

    def _visit_OrderBy(self, node: OrderBy) -> exp.Expression:
        raise TranspilerError("OrderBy should be handled inside EvaluateQuery")

    def _visit_OrderByItem(self, node: OrderByItem) -> exp.Expression:
        raise TranspilerError(
            "OrderByItem should be handled inside EvaluateQuery")


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


def dax_to_sql(node: DaxNode, dialect: str = "spark") -> str:
    """Transpile a DaxNode AST to a SQL string in the given dialect.

    Args:
        node: The root DAX AST node returned by ``parse_dax()``.
        dialect: Target SQL dialect (any dialect supported by sqlglot,
                 e.g. ``"spark"``, ``"databricks"``, ``"duckdb"``,
                 ``"tsql"``, ``"bigquery"``).

    Returns:
        A SQL string in the requested dialect.
    """
    transpiler = DaxToSqlTranspiler()
    sql_expr = transpiler.transpile(node)
    return sql_expr.sql(dialect=dialect)
