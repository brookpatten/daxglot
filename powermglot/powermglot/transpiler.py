"""Power Query M → SQL transpiler.

Walks the ``let … in`` step chain of a parsed M expression and produces a
sqlglot :class:`~sqlglot.expressions.Select` (or a raw SQL string via
:func:`m_to_sql`).

Supported M patterns
--------------------
* **Connector navigation** — 2- or 3-level ``{[Name=…]}[Data]`` chains that
  resolve to ``catalog.schema.table`` or ``schema.table``.
* ``Table.SelectRows(t, each predicate)`` → ``WHERE`` clause.
* ``Table.SelectColumns(t, {cols})`` → column projection.
* ``Table.RenameColumns(t, {{old, new}, …})`` → column aliases.
* ``Table.AddColumn(t, "name", each expr)`` → computed column.
* ``Table.RemoveColumns(t, {cols})`` → column exclusion.
* ``Table.Group(t, {keys}, {agg_specs})`` → ``GROUP BY`` with aggregations.
* ``Table.NestedJoin`` / ``Table.Join`` → ``JOIN`` clause.
* ``Value.NativeQuery(src, "sql")`` → pass-through SQL.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import sqlglot
import sqlglot.expressions as exp

from .ast_nodes import (
    BinaryOpExpr,
    CallExpr,
    EachExpr,
    FieldAccessExpr,
    FieldRef,
    IdentExpr,
    LetExpr,
    ListExpr,
    LiteralExpr,
    MExpr,
    NavExpr,
    RecordExpr,
    UnaryOpExpr,
)
from .parser import parse_m


class TranspilerError(Exception):
    pass


# ---------------------------------------------------------------------------
# Intermediate query representation
# ---------------------------------------------------------------------------


@dataclass
class _Column:
    """A column in the SELECT list."""

    name: str            # output name
    expr: Optional[exp.Expression] = None  # sqlglot expression; None → bare name


@dataclass
class _JoinSpec:
    source: str          # table reference string (e.g. "catalog.schema.table")
    alias: str           # join alias
    left_cols: List[str]
    right_cols: List[str]
    kind: str = "INNER"  # INNER | LEFT | RIGHT | FULL


@dataclass
class _QueryState:
    """Accumulated state as we walk the step chain."""

    from_source: Optional[str] = None          # catalog.schema.table or raw SQL
    from_is_sql: bool = False                  # True when from_source is raw SQL
    from_alias: Optional[str] = None
    select_cols: Optional[List[_Column]] = None  # None → SELECT *
    where_clauses: List[exp.Expression] = field(default_factory=list)
    joins: List[_JoinSpec] = field(default_factory=list)
    group_by_cols: Optional[List[str]] = None
    group_aggs: List[_Column] = field(default_factory=list)
    rename_map: Dict[str, str] = field(default_factory=dict)  # old → new
    remove_cols: List[str] = field(default_factory=list)
    add_cols: List[_Column] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Main transpiler class
# ---------------------------------------------------------------------------


class MToSqlTranspiler:
    """Transpile a parsed M :class:`~powermglot.ast_nodes.LetExpr` to SQL."""

    def transpile(
        self,
        node: MExpr,
        dialect: Optional[str] = None,
    ) -> str:
        """Return a SQL string for *node* in the given sqlglot *dialect*.

        If *node* is not a :class:`~powermglot.ast_nodes.LetExpr` the method
        tries to evaluate it directly as a scalar expression.
        """
        if not isinstance(node, LetExpr):
            raise TranspilerError(
                "MToSqlTranspiler requires a LetExpr as top-level node; "
                f"got {type(node).__name__}"
            )
        select_expr = self._let_to_select(node)
        return select_expr.sql(dialect=dialect or "")

    # ------------------------------------------------------------------
    # Internal: let chain evaluation
    # ------------------------------------------------------------------

    def _let_to_select(self, let: LetExpr) -> exp.Expression:
        env: Dict[str, MExpr] = {name: expr for name, expr in let.bindings}
        state = _QueryState()

        # Resolve the chain starting from the result expression
        self._resolve(let.result, env, state)

        return self._build_select(state)

    def _resolve(self, node: MExpr, env: Dict[str, MExpr], state: _QueryState) -> None:  # noqa: C901
        """Recursively walk *node* and populate *state*."""

        # Variable reference → recurse into its definition
        if isinstance(node, IdentExpr):
            if node.name in env:
                self._resolve(env[node.name], env, state)
            # Unknown ident — nothing to do
            return

        # Let expression (nested)
        if isinstance(node, LetExpr):
            sub_env = dict(env)
            sub_env.update({n: e for n, e in node.bindings})
            self._resolve(node.result, sub_env, state)
            return

        # Function call — the main dispatch
        if isinstance(node, CallExpr):
            fname = _qual_name(node.function)
            if fname is not None:
                handled = self._dispatch_call(fname, node, env, state)
                if handled:
                    return
            # Unrecognised call — try to resolve first arg as the source
            if node.args:
                self._resolve(node.args[0], env, state)
            return

        # Navigation: expr{key}[Data]  — connector navigation step
        if isinstance(node, NavExpr):
            self._resolve_nav(node, env, state)
            return

        # Field access on a nav result: expr[Data]
        if isinstance(node, FieldAccessExpr):
            if node.field == "Data":
                self._resolve(node.expr, env, state)
            else:
                # Could be Module.Function — pass through
                self._resolve(node.expr, env, state)
            return

    # ------------------------------------------------------------------
    # Navigation resolution
    # ------------------------------------------------------------------

    def _resolve_nav(
        self, node: NavExpr, env: Dict[str, MExpr], state: _QueryState
    ) -> None:
        """Resolve ``expr{key}`` navigation into a table source.

        Follows variable references through *env* so that a multi-step chain
        like::

            Source = Connector(...),
            db = Source{[Name="schema"]}[Data],
            tbl = db{[Name="table"]}[Data]

        correctly produces ``catalog.schema.table``.
        """
        catalog, segments = self._flatten_nav_chain(node, env)
        parts = [p for p in ([catalog] if catalog else []) + segments if p]
        if parts:
            state.from_source = ".".join(parts)
        else:
            self._resolve(node.expr, env, state)

    def _flatten_nav_chain(
        self, node: MExpr, env: Dict[str, MExpr]
    ) -> Tuple[Optional[str], List[str]]:
        """Recursively flatten a navigation chain into ``(catalog, [seg1, seg2, ...])``.

        Variable references are followed through *env*, so intermediate steps
        that bind the result of a navigation are unwound correctly.
        """
        # Variable reference — resolve through env
        if isinstance(node, IdentExpr) and node.name in env:
            return self._flatten_nav_chain(env[node.name], env)

        # [Data] field access — unwrap and continue
        if isinstance(node, FieldAccessExpr) and node.field == "Data":
            return self._flatten_nav_chain(node.expr, env)

        # Navigation: expr{[Name="..."]} — collect segment and recurse
        if isinstance(node, NavExpr):
            seg = _extract_nav_key(node.key)
            catalog, parent_segs = self._flatten_nav_chain(node.expr, env)
            if seg:
                return (catalog, parent_segs + [seg])
            return (catalog, parent_segs)

        # Connector call — extract the catalog and stop
        if isinstance(node, CallExpr):
            fname = _qual_name(node.function)
            if fname is not None:
                info = _extract_connector_info(fname, node)
                if info is not None:
                    return (info[0], [])

        return (None, [])

    # ------------------------------------------------------------------
    # Call dispatch
    # ------------------------------------------------------------------

    def _dispatch_call(  # noqa: C901
        self,
        fname: str,
        node: CallExpr,
        env: Dict[str, MExpr],
        state: _QueryState,
    ) -> bool:
        """Handle a recognised M function call.  Returns True if handled."""

        upper = fname.upper()

        # Value.NativeQuery(connection, "sql text")
        if upper == "VALUE.NATIVEQUERY":
            if len(node.args) >= 2:
                sql_node = node.args[1]
                if isinstance(sql_node, LiteralExpr) and sql_node.kind == "string":
                    state.from_source = sql_node.value
                    state.from_is_sql = True
                    return True
            return False

        # Table.SelectRows(table, each predicate)
        if upper == "TABLE.SELECTROWS":
            if len(node.args) >= 2:
                self._resolve(node.args[0], env, state)
                predicate = node.args[1]
                if isinstance(predicate, EachExpr):
                    predicate = predicate.expr
                where = _predicate_to_sql(predicate)
                if where is not None:
                    state.where_clauses.append(where)
            return True

        # Table.SelectColumns(table, {col_list})
        if upper == "TABLE.SELECTCOLUMNS":
            if len(node.args) >= 2:
                self._resolve(node.args[0], env, state)
                cols = _extract_string_list(node.args[1])
                if cols is not None:
                    state.select_cols = [_Column(name=c) for c in cols]
            return True

        # Table.RenameColumns(table, { {old, new}, ... })
        if upper == "TABLE.RENAMECOLUMNS":
            if len(node.args) >= 2:
                self._resolve(node.args[0], env, state)
                renames = _extract_rename_pairs(node.args[1])
                for old, new in renames:
                    state.rename_map[old] = new
            return True

        # Table.RemoveColumns(table, {col_list})
        if upper == "TABLE.REMOVECOLUMNS":
            if len(node.args) >= 2:
                self._resolve(node.args[0], env, state)
                cols = _extract_string_list(node.args[1])
                if cols:
                    state.remove_cols.extend(cols)
            return True

        # Table.AddColumn(table, "new_col", each expr [, type])
        if upper == "TABLE.ADDCOLUMN":
            if len(node.args) >= 3:
                self._resolve(node.args[0], env, state)
                if isinstance(node.args[1], LiteralExpr):
                    col_name = str(node.args[1].value)
                    col_expr = node.args[2]
                    if isinstance(col_expr, EachExpr):
                        col_expr = col_expr.expr
                    sql_expr = _expr_to_sql(col_expr)
                    state.add_cols.append(_Column(name=col_name, expr=sql_expr))
            return True

        # Table.TransformColumns(table, { {col, transform}, ... })
        if upper == "TABLE.TRANSFORMCOLUMNS":
            if node.args:
                self._resolve(node.args[0], env, state)
            return True

        # Table.Group(table, {key_cols}, { {name, init, each agg}, ... })
        if upper == "TABLE.GROUP":
            if len(node.args) >= 3:
                self._resolve(node.args[0], env, state)
                key_cols = _extract_string_list(node.args[1])
                state.group_by_cols = key_cols or []
                aggs = _extract_group_aggs(node.args[2])
                state.group_aggs = aggs
            return True

        # Table.NestedJoin(left, leftKey, right, rightKey, newColName [, kind])
        if upper in ("TABLE.NESTEDJOIN", "TABLE.JOIN"):
            return self._handle_join(node, env, state)

        # Table.Sort, Table.Distinct, Table.Buffer, Table.Distinct, etc.
        # — pass the first argument through unchanged
        if upper.startswith("TABLE.") or upper.startswith("LIST."):
            if node.args:
                self._resolve(node.args[0], env, state)
            return True

        # Databricks.Catalogs / DatabricksCatalog.Contents / Sql.Database
        fname_norm = fname.upper().replace("DATABRICKSCATALOG.CONTENTS", "DATABRICKS.CATALOGS")
        if any(
            fname_norm.startswith(p)
            for p in (
                "DATABRICKS.CATALOGS",
                "DATABRICKS.",
                "AZUREDATABRICKS.",
                "SQL.DATABASE",
                "POSTGRESQL.",
                "MYSQL.",
                "ORACLE.",
                "SNOWFLAKE.",
                "BIGQUERY.",
            )
        ):
            info = _extract_connector_info(fname, node)
            if info is not None:
                catalog, _host = info
                if catalog and not state.from_source:
                    state.from_source = catalog
            return True

        return False

    def _handle_join(
        self, node: CallExpr, env: Dict[str, MExpr], state: _QueryState
    ) -> bool:
        """Handle ``Table.NestedJoin`` and ``Table.Join``."""
        # Table.NestedJoin(left, leftKey, rightTable, rightKey, newCol [, JoinKind.X])
        # Table.Join(left, leftKey, right, rightKey [, JoinKind.X])
        args = node.args
        if len(args) < 4:
            return False

        self._resolve(args[0], env, state)

        left_keys = _extract_string_list(args[1]) or []
        if not left_keys and isinstance(args[1], LiteralExpr):
            left_keys = [str(args[1].value)]

        right_ref = args[2]
        right_table_name: Optional[str] = None
        if isinstance(right_ref, IdentExpr) and right_ref.name in env:
            sub_state = _QueryState()
            self._resolve(env[right_ref.name], env, sub_state)
            right_table_name = sub_state.from_source
        elif isinstance(right_ref, IdentExpr):
            right_table_name = right_ref.name

        right_keys = _extract_string_list(args[3]) or []
        if not right_keys and isinstance(args[3], LiteralExpr):
            right_keys = [str(args[3].value)]

        # Join kind from last argument (optional)
        kind = "INNER"
        if len(args) >= 6:
            kind_arg = args[5] if len(args) > 5 else args[4]
            kind = _extract_join_kind(kind_arg)
        elif len(args) == 5:
            kind = _extract_join_kind(args[4])

        alias = right_table_name.split(".")[-1] if right_table_name else "joined"
        if right_table_name:
            state.joins.append(
                _JoinSpec(
                    source=right_table_name,
                    alias=alias,
                    left_cols=left_keys,
                    right_cols=right_keys,
                    kind=kind,
                )
            )
        return True

    # ------------------------------------------------------------------
    # SQL assembly
    # ------------------------------------------------------------------

    def _build_select(self, state: _QueryState) -> exp.Expression:  # noqa: C901
        """Assemble a sqlglot SELECT from the accumulated *state*."""

        # ---- FROM -------------------------------------------------------
        if state.from_source is None:
            raise TranspilerError("No data source found in M expression")

        if state.from_is_sql:
            # Wrap the native SQL as a subquery
            inner = sqlglot.parse_one(state.from_source)
            from_clause: exp.Expression = inner.subquery("_native")  # type: ignore[union-attr]
        else:
            from_clause = exp.to_table(state.from_source)

        # ---- SELECT columns ---------------------------------------------
        select_exprs: List[exp.Expression] = []

        if state.group_by_cols is not None:
            # GROUP BY path: select key cols + aggregations
            for key in state.group_by_cols:
                aliased_key = state.rename_map.get(key, key)
                select_exprs.append(exp.column(aliased_key))
            for agg in state.group_aggs:
                col_name = state.rename_map.get(agg.name, agg.name)
                if agg.expr is not None:
                    select_exprs.append(
                        exp.alias_(agg.expr, col_name)
                        if col_name != agg.name
                        else agg.expr
                    )
                else:
                    select_exprs.append(exp.column(col_name))
        elif state.select_cols is not None:
            # Explicit column list
            remove_set = {c.lower() for c in state.remove_cols}
            for col in state.select_cols:
                if col.name.lower() in remove_set:
                    continue
                new_name = state.rename_map.get(col.name)
                if col.expr is not None:
                    sql_col: exp.Expression = col.expr
                else:
                    sql_col = exp.column(col.name)
                if new_name:
                    select_exprs.append(exp.alias_(sql_col, new_name))
                else:
                    select_exprs.append(sql_col)
            # add_cols
            for add_col in state.add_cols:
                col_name = state.rename_map.get(add_col.name, add_col.name)
                if add_col.expr is not None:
                    select_exprs.append(exp.alias_(add_col.expr, col_name))
        else:
            # No explicit column list — SELECT *
            if state.rename_map or state.add_cols or state.remove_cols:
                # We have transforms but no explicit column list — emit SELECT *
                # with a note that full resolution requires schema information
                select_exprs = [exp.Star()]
            else:
                select_exprs = [exp.Star()]

        if not select_exprs:
            select_exprs = [exp.Star()]

        # ---- Build base query -------------------------------------------
        query = exp.select(*select_exprs).from_(from_clause)

        # ---- JOINs -------------------------------------------------------
        for join_spec in state.joins:
            right_tbl = exp.to_table(join_spec.source)
            on_parts: List[exp.Expression] = []
            for lc, rc in zip(join_spec.left_cols, join_spec.right_cols):
                on_parts.append(
                    exp.EQ(
                        this=exp.column(lc),
                        expression=exp.column(rc, table=join_spec.alias),
                    )
                )
            on_expr: exp.Expression = on_parts[0]
            for part in on_parts[1:]:
                on_expr = exp.And(this=on_expr, expression=part)

            join_kind = join_spec.kind.upper()
            join_node = exp.Join(
                this=right_tbl,
                on=on_expr,
                kind=join_kind if join_kind != "INNER" else None,
            )
            query = query.join(join_node)  # type: ignore[assignment]

        # ---- WHERE -------------------------------------------------------
        if state.where_clauses:
            where_expr: exp.Expression = state.where_clauses[0]
            for clause in state.where_clauses[1:]:
                where_expr = exp.And(this=where_expr, expression=clause)
            query = query.where(where_expr)  # type: ignore[assignment]

        # ---- GROUP BY ----------------------------------------------------
        if state.group_by_cols:
            group_exprs = [exp.column(k) for k in state.group_by_cols]
            query = query.group_by(*group_exprs)  # type: ignore[assignment]

        return query


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _qual_name(node: MExpr) -> Optional[str]:
    """Return the dotted qualified name of a function expression, e.g. ``Table.SelectRows``."""
    if isinstance(node, IdentExpr):
        return node.name
    if isinstance(node, FieldAccessExpr):
        base = _qual_name(node.expr)
        if base is not None:
            return f"{base}.{node.field}"
    return None


def _nav_base(node: MExpr) -> MExpr:
    """Return the base expression of a nav/field-access chain."""
    if isinstance(node, (NavExpr, FieldAccessExpr)):
        return _nav_base(node.expr)
    return node


def _extract_nav_key(key: MExpr) -> Optional[str]:
    """Extract the string value from a navigation key like ``[Name="schema"]``."""
    # key is typically a RecordExpr with Name= or Item= fields
    if isinstance(key, RecordExpr):
        for field_name, val in key.fields:
            if field_name.lower() in ("name", "item"):
                if isinstance(val, LiteralExpr) and val.kind == "string":
                    return str(val.value)
        return None
    # key might be a ListExpr containing a RecordExpr: {[Name="schema"]}
    if isinstance(key, ListExpr) and len(key.items) == 1:
        return _extract_nav_key(key.items[0])
    return None


def _extract_connector_info(
    fname: str, node: CallExpr
) -> Optional[Tuple[Optional[str], str]]:
    """Return ``(catalog, host)`` from a connector call, or None."""
    host = ""
    catalog: Optional[str] = None
    if node.args:
        first = node.args[0]
        if isinstance(first, LiteralExpr) and first.kind == "string":
            host = str(first.value)

    # Look for [Catalog="..."] in any argument
    for arg in node.args:
        if isinstance(arg, RecordExpr):
            for fname_r, val in arg.fields:
                if fname_r.lower() == "catalog" and isinstance(val, LiteralExpr):
                    catalog = str(val.value)

    # Sql.Database("server", "database") → catalog is the second arg
    if fname.upper().startswith("SQL.DATABASE") and len(node.args) >= 2:
        second = node.args[1]
        if isinstance(second, LiteralExpr) and catalog is None:
            catalog = str(second.value)

    return (catalog, host)


def _extract_string_list(node: MExpr) -> Optional[List[str]]:
    """Extract a list of string values from a ListExpr of LiteralExpr nodes."""
    if not isinstance(node, ListExpr):
        return None
    result: List[str] = []
    for item in node.items:
        if isinstance(item, LiteralExpr) and item.kind == "string":
            result.append(str(item.value))
        else:
            return None  # Non-string element → cannot extract
    return result


def _extract_rename_pairs(node: MExpr) -> List[Tuple[str, str]]:
    """Extract ``[(old, new), …]`` from a ListExpr of 2-element string lists."""
    if not isinstance(node, ListExpr):
        return []
    pairs: List[Tuple[str, str]] = []
    for item in node.items:
        if isinstance(item, ListExpr) and len(item.items) == 2:
            a, b = item.items
            if (
                isinstance(a, LiteralExpr) and a.kind == "string"
                and isinstance(b, LiteralExpr) and b.kind == "string"
            ):
                pairs.append((str(a.value), str(b.value)))
    return pairs


def _extract_group_aggs(node: MExpr) -> List[_Column]:
    """Extract aggregation specs from Table.Group's third argument."""
    if not isinstance(node, ListExpr):
        return []
    aggs: List[_Column] = []
    for item in node.items:
        if not isinstance(item, ListExpr) or len(item.items) < 2:
            continue
        name_node = item.items[0]
        agg_node = item.items[1] if len(item.items) >= 2 else None
        if not isinstance(name_node, LiteralExpr) or name_node.kind != "string":
            continue
        col_name = str(name_node.value)
        if agg_node is not None:
            if isinstance(agg_node, EachExpr):
                agg_node = agg_node.expr
            sql_expr = _expr_to_sql(agg_node)
            aggs.append(_Column(name=col_name, expr=sql_expr))
        else:
            aggs.append(_Column(name=col_name))
    return aggs


def _extract_join_kind(node: MExpr) -> str:
    """Extract the join type from a ``JoinKind.X`` field access expression."""
    name = _qual_name(node)
    if name:
        name_upper = name.upper()
        if "LEFT" in name_upper:
            return "LEFT"
        if "RIGHT" in name_upper:
            return "RIGHT"
        if "FULL" in name_upper:
            return "FULL"
    return "INNER"


# ---------------------------------------------------------------------------
# Predicate → sqlglot expression
# ---------------------------------------------------------------------------

_M_OP_TO_SQL: Dict[str, str] = {
    "=": "=",
    "<>": "!=",
    "<": "<",
    ">": ">",
    "<=": "<=",
    ">=": ">=",
}


def _predicate_to_sql(node: MExpr) -> Optional[exp.Expression]:  # noqa: C901
    """Convert an M predicate expression to a sqlglot expression."""
    if isinstance(node, BinaryOpExpr):
        op = node.op.lower()

        if op == "and":
            left = _predicate_to_sql(node.left)
            right = _predicate_to_sql(node.right)
            if left is not None and right is not None:
                return exp.And(this=left, expression=right)
            return left or right

        if op == "or":
            left = _predicate_to_sql(node.left)
            right = _predicate_to_sql(node.right)
            if left is not None and right is not None:
                return exp.Or(this=left, expression=right)
            return left or right

        sql_op = _M_OP_TO_SQL.get(op)
        if sql_op:
            left_expr = _expr_to_sql(node.left)
            right_expr = _expr_to_sql(node.right)
            if left_expr is not None and right_expr is not None:
                return _build_comparison(sql_op, left_expr, right_expr)

    if isinstance(node, UnaryOpExpr) and node.op.lower() == "not":
        inner = _predicate_to_sql(node.expr)
        if inner is not None:
            return exp.Not(this=inner)

    if isinstance(node, EachExpr):
        return _predicate_to_sql(node.expr)

    return None


def _build_comparison(
    op: str, left: exp.Expression, right: exp.Expression
) -> exp.Expression:
    mapping = {
        "=": exp.EQ,
        "!=": exp.NEQ,
        "<": exp.LT,
        ">": exp.GT,
        "<=": exp.LTE,
        ">=": exp.GTE,
    }
    cls = mapping.get(op, exp.EQ)
    return cls(this=left, expression=right)


def _expr_to_sql(node: MExpr) -> Optional[exp.Expression]:  # noqa: C901
    """Convert a scalar M expression to a sqlglot expression."""
    if isinstance(node, LiteralExpr):
        if node.kind == "null":
            return exp.null()
        if node.kind == "bool":
            return exp.true() if node.value else exp.false()
        if node.kind == "number":
            return exp.Literal.number(node.value)
        return exp.Literal.string(str(node.value))

    if isinstance(node, FieldRef):
        return exp.column(node.name)

    # [ColumnName] inside an each — expressed as a RecordExpr with __field_ref__
    if isinstance(node, RecordExpr):
        if (
            len(node.fields) == 1
            and node.fields[0][0] == "__field_ref__"
            and isinstance(node.fields[0][1], IdentExpr)
        ):
            return exp.column(node.fields[0][1].name)

    if isinstance(node, IdentExpr):
        return exp.column(node.name)

    if isinstance(node, BinaryOpExpr):
        op = node.op.lower()
        left = _expr_to_sql(node.left)
        right = _expr_to_sql(node.right)
        if left is None or right is None:
            return None
        if op in _M_OP_TO_SQL:
            return _build_comparison(_M_OP_TO_SQL[op], left, right)
        op_map = {
            "+": exp.Add,
            "-": exp.Sub,
            "*": exp.Mul,
            "/": exp.Div,
            "&": exp.DPipe,  # string concatenation
        }
        cls = op_map.get(op)
        if cls:
            return cls(this=left, expression=right)

    if isinstance(node, UnaryOpExpr):
        inner = _expr_to_sql(node.expr)
        if inner is None:
            return None
        if node.op == "-":
            return exp.Neg(this=inner)
        if node.op.lower() == "not":
            return exp.Not(this=inner)

    if isinstance(node, CallExpr):
        fname = _qual_name(node.function)
        if fname is not None:
            sql_func = _m_func_to_sql(fname, node.args)
            if sql_func is not None:
                return sql_func

    if isinstance(node, EachExpr):
        return _expr_to_sql(node.expr)

    return None


def _m_func_to_sql(fname: str, args: List[MExpr]) -> Optional[exp.Expression]:
    """Map common M aggregate/list functions to SQL equivalents."""
    upper = fname.upper()

    def _first_col() -> Optional[exp.Expression]:
        if args and isinstance(args[0], EachExpr):
            inner = args[0].expr
            if isinstance(inner, RecordExpr) and len(inner.fields) == 1:
                if inner.fields[0][0] == "__field_ref__":
                    col_node = inner.fields[0][1]
                    if isinstance(col_node, IdentExpr):
                        return exp.column(col_node.name)
            return _expr_to_sql(inner)
        if args:
            return _expr_to_sql(args[0])
        return None

    agg_map = {
        "LIST.SUM": exp.Sum,
        "LIST.COUNT": exp.Count,
        "LIST.AVERAGE": exp.Avg,
        "LIST.MIN": exp.Min,
        "LIST.MAX": exp.Max,
    }
    if upper in agg_map:
        col = _first_col()
        if col is not None:
            return agg_map[upper](this=col)

    return None


# ---------------------------------------------------------------------------
# Public convenience function
# ---------------------------------------------------------------------------


def m_to_sql(m_expr: str, dialect: Optional[str] = None) -> str:
    """Parse a Power Query M expression and return a SQL string.

    Args:
        m_expr: The M source text (typically a ``let … in`` expression).
        dialect: Optional sqlglot dialect name, e.g. ``"spark"``, ``"tsql"``,
            ``"bigquery"``.  When ``None`` or empty the output is
            dialect-neutral.

    Returns:
        A SQL SELECT statement as a string.

    Example::

        sql = m_to_sql('''
            let
                Source = Databricks.Catalogs("host", "443", [Catalog="prod"]),
                db = Source{[Name="pbi"]}[Data],
                tbl = db{[Name="orders"]}[Data]
            in tbl
        ''', dialect="spark")
        # SELECT * FROM prod.pbi.orders
    """
    ast = parse_m(m_expr)
    return MToSqlTranspiler().transpile(ast, dialect=dialect)
