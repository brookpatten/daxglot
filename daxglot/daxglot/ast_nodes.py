"""DAX AST node definitions.

Every node is an immutable frozen dataclass that inherits from DaxNode.
The tree produced by DaxParser is composed entirely of these types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Any


@dataclass(frozen=True)
class DaxNode:
    """Base class for all DAX AST nodes."""

    def __repr__(self) -> str:
        cls = type(self).__name__
        parts = []
        for f in self.__dataclass_fields__:  # type: ignore[attr-defined]
            parts.append(f"{f}={getattr(self, f)!r}")
        return f"{cls}({', '.join(parts)})"

    def pretty(self, indent: int = 0) -> str:
        """Return a multi-line indented representation of the tree."""
        pad = "  " * indent
        cls = type(self).__name__
        fields = self.__dataclass_fields__  # type: ignore[attr-defined]
        lines = [f"{pad}{cls}("]
        for fname in fields:
            val = getattr(self, fname)
            if isinstance(val, DaxNode):
                inner = val.pretty(indent + 1).lstrip()
                lines.append(f"{pad}  {fname}={inner}")
            elif isinstance(val, list):
                items = []
                for item in val:
                    if isinstance(item, DaxNode):
                        items.append(item.pretty(indent + 2))
                    elif isinstance(item, tuple):
                        items.append(str(tuple(
                            v.pretty(indent + 2) if isinstance(v,
                                                               DaxNode) else repr(v)
                            for v in item
                        )))
                    else:
                        items.append(repr(item))
                if items:
                    joined = (",\n").join(items)
                    lines.append(f"{pad}  {fname}=[\n{joined}\n{pad}  ]")
                else:
                    lines.append(f"{pad}  {fname}=[]")
            else:
                lines.append(f"{pad}  {fname}={val!r}")
        lines.append(f"{pad})")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Top-level query / expression containers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EvaluateQuery(DaxNode):
    """EVALUATE <table_expr> [ORDER BY …] [START AT …]"""

    table_expr: DaxNode
    order_by: Optional["OrderBy"] = None
    start_at: Optional[List[DaxNode]] = None


@dataclass(frozen=True)
class MeasureExpr(DaxNode):
    """A measure definition starting with ``=``."""

    expr: DaxNode


@dataclass(frozen=True)
class VarDef(DaxNode):
    """VAR <name> = <expr>"""

    name: str
    expr: DaxNode


@dataclass(frozen=True)
class VarBlock(DaxNode):
    """One or more VAR definitions followed by RETURN <expr>."""

    vars: Tuple[VarDef, ...]
    return_expr: DaxNode


# ---------------------------------------------------------------------------
# Filter / table functions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Calculate(DaxNode):
    """CALCULATE(<expr> [, <filter1>, ...])"""

    expr: DaxNode
    filters: Tuple[DaxNode, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CalculateTable(DaxNode):
    """CALCULATETABLE(<table_expr> [, <filter1>, ...])"""

    table_expr: DaxNode
    filters: Tuple[DaxNode, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Filter(DaxNode):
    """FILTER(<table_expr>, <condition>)"""

    table_expr: DaxNode
    condition: DaxNode


@dataclass(frozen=True)
class All(DaxNode):
    """ALL(<table_or_column> [, <column>, ...])"""

    table_or_column: DaxNode
    columns: Tuple[DaxNode, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class AllExcept(DaxNode):
    """ALLEXCEPT(<table>, <column> [, ...])"""

    table_expr: DaxNode
    columns: Tuple[DaxNode, ...]


@dataclass(frozen=True)
class KeepFilters(DaxNode):
    """KEEPFILTERS(<expr>)"""

    expr: DaxNode


@dataclass(frozen=True)
class RemoveFilters(DaxNode):
    """REMOVEFILTERS(<table_or_column>)"""

    expr: DaxNode


@dataclass(frozen=True)
class TreatAs(DaxNode):
    """TREATAS(<table_expr>, <column> [, ...])"""

    table_expr: DaxNode
    columns: Tuple[DaxNode, ...]


@dataclass(frozen=True)
class UseRelationship(DaxNode):
    """USERELATIONSHIP(<col1>, <col2>)"""

    col1: DaxNode
    col2: DaxNode


@dataclass(frozen=True)
class CrossFilter(DaxNode):
    """CROSSFILTER(<col1>, <col2>, <direction>)"""

    col1: DaxNode
    col2: DaxNode
    direction: str


# ---------------------------------------------------------------------------
# Aggregation functions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Aggregation(DaxNode):
    """Single-column aggregation: SUM, MAX, MIN, AVERAGE, COUNT, DISTINCTCOUNT, COUNTA…"""

    func: str       # uppercase function name
    expr: DaxNode   # the ColumnRef or expression inside


@dataclass(frozen=True)
class CountRows(DaxNode):
    """COUNTROWS([<table>])"""

    table_expr: Optional[DaxNode] = None


# ---------------------------------------------------------------------------
# Iterator / X-functions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Iterator(DaxNode):
    """SUMX, AVERAGEX, MAXX, MINX, COUNTX, RANKX, etc."""

    func: str
    table_expr: DaxNode
    body: DaxNode


# ---------------------------------------------------------------------------
# Context / relationship functions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ContextFunction(DaxNode):
    """EARLIER(<expr> [, <n>]) or EARLIEST(<expr>)"""

    func: str       # 'EARLIER' or 'EARLIEST'
    expr: DaxNode
    depth: int = 1  # EARLIER(col, n) — defaults to 1 outer row context


@dataclass(frozen=True)
class RelatedFunction(DaxNode):
    """RELATED(<column>) or RELATEDTABLE(<table>)"""

    func: str
    expr: DaxNode


# ---------------------------------------------------------------------------
# Logical / conditional
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IfExpr(DaxNode):
    """IF(<condition>, <true_val> [, <false_val>])"""

    condition: DaxNode
    true_val: DaxNode
    false_val: Optional[DaxNode] = None


@dataclass(frozen=True)
class IfError(DaxNode):
    """IFERROR(<value>, <value_if_error>)"""

    value: DaxNode
    value_if_error: DaxNode


@dataclass(frozen=True)
class SwitchCase(DaxNode):
    """A single WHEN/THEN pair inside SWITCH."""

    when: DaxNode
    then: DaxNode


@dataclass(frozen=True)
class SwitchExpr(DaxNode):
    """SWITCH(<expr>, <val1>, <result1> [, …] [, <else>])"""

    expr: DaxNode
    cases: Tuple[SwitchCase, ...]
    default: Optional[DaxNode] = None


# ---------------------------------------------------------------------------
# Generic / fallback
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FunctionCall(DaxNode):
    """Generic DAX function call not handled by a specific node type."""

    name: str
    args: Tuple[DaxNode, ...]


# ---------------------------------------------------------------------------
# Operators / expressions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BinaryOp(DaxNode):
    """<left> <op> <right>

    op values: ``=``, ``<>``, ``<``, ``<=``, ``>``, ``>=``,
               ``+``, ``-``, ``*``, ``/``, ``&``,
               ``AND``, ``OR``, ``&&``, ``||``
    """

    op: str
    left: DaxNode
    right: DaxNode


@dataclass(frozen=True)
class UnaryOp(DaxNode):
    """<op> <expr>.  op values: ``-``, ``NOT``, ``!``"""

    op: str
    expr: DaxNode


@dataclass(frozen=True)
class InExpr(DaxNode):
    """<expr> IN { <v1>, <v2>, … }"""

    expr: DaxNode
    values: Tuple[DaxNode, ...]


@dataclass(frozen=True)
class NotInExpr(DaxNode):
    """<expr> NOT IN { <v1>, <v2>, … }"""

    expr: DaxNode
    values: Tuple[DaxNode, ...]


# ---------------------------------------------------------------------------
# Leaf nodes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ColumnRef(DaxNode):
    """A reference to ``Table[Column]`` or just ``[Column]``."""

    table: Optional[str]    # None when only [Column] is written
    column: str


@dataclass(frozen=True)
class TableRef(DaxNode):
    """A bare table reference (possibly single-quoted)."""

    name: str
    is_quoted: bool = False


@dataclass(frozen=True)
class Literal(DaxNode):
    """A scalar literal value.

    kind is one of: ``'STRING'``, ``'NUMBER'``, ``'BOOLEAN'``, ``'BLANK'``
    """

    value: Any
    kind: str   # 'STRING' | 'NUMBER' | 'BOOLEAN' | 'BLANK'


# ---------------------------------------------------------------------------
# ORDER BY
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OrderByItem(DaxNode):
    expr: DaxNode
    direction: str  # 'ASC' | 'DESC'


@dataclass(frozen=True)
class OrderBy(DaxNode):
    items: Tuple[OrderByItem, ...]
