"""Power Query M AST node definitions.

Each class represents a syntactic construct in the M language.  Nodes are
plain dataclasses so they can be inspected and compared easily in tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple, Union


# ---------------------------------------------------------------------------
# Type alias — any M expression
# ---------------------------------------------------------------------------

MExpr = Union[
    "LetExpr",
    "CallExpr",
    "NavExpr",
    "FieldAccessExpr",
    "BinaryOpExpr",
    "UnaryOpExpr",
    "LiteralExpr",
    "IdentExpr",
    "ListExpr",
    "RecordExpr",
    "EachExpr",
    "FieldRef",
    "IfExpr",
    "ErrorExpr",
    "TypeExpr",
    "MetaExpr",
    "ParenExpr",
]


# ---------------------------------------------------------------------------
# Structural nodes
# ---------------------------------------------------------------------------


@dataclass
class LetExpr:
    """``let name1 = e1, name2 = e2, ... in result``"""

    bindings: List[Tuple[str, MExpr]]
    result: MExpr


@dataclass
class IdentExpr:
    """A bare or quoted identifier, e.g. ``Source`` or ``#"My Table"``."""

    name: str


@dataclass
class LiteralExpr:
    """A scalar literal: string, number, boolean, or null."""

    value: Any  # str | int | float | bool | None
    kind: str   # "string" | "number" | "bool" | "null"


@dataclass
class ListExpr:
    """``{item1, item2, ...}``"""

    items: List[MExpr]


@dataclass
class RecordExpr:
    """``[Field1 = value1, Field2 = value2, ...]``"""

    fields: List[Tuple[str, MExpr]]


@dataclass
class CallExpr:
    """A function call, e.g. ``Table.SelectRows(src, each ...)``.

    ``function`` is typically a dotted name represented as nested
    :class:`FieldAccessExpr` nodes built by the parser.
    """

    function: MExpr
    args: List[MExpr]


@dataclass
class NavExpr:
    """Navigation expression: ``expr{key}``.

    Used for record/list navigation such as ``Source{[Name="schema"]}[Data]``.
    """

    expr: MExpr
    key: MExpr  # typically a ListExpr containing a RecordExpr


@dataclass
class FieldAccessExpr:
    """Member/field access: ``expr[Field]`` or the dotted form ``Module.Func``.

    For dotted names (``Table.SelectRows``) ``expr`` is an :class:`IdentExpr`
    and ``field`` is the right-hand part.
    """

    expr: MExpr
    field: str


@dataclass
class FieldRef:
    """A field reference inside an ``each`` expression: ``[ColumnName]``."""

    name: str


@dataclass
class EachExpr:
    """``each <expr>`` — shorthand for ``(_) => <expr>``."""

    expr: MExpr


@dataclass
class BinaryOpExpr:
    """Binary operator expression, e.g. ``[Status] = "Active"``."""

    op: str
    left: MExpr
    right: MExpr


@dataclass
class UnaryOpExpr:
    """Unary operator expression, e.g. ``not [Flag]``."""

    op: str
    expr: MExpr


@dataclass
class IfExpr:
    """``if cond then t else e``"""

    condition: MExpr
    then_expr: MExpr
    else_expr: MExpr


@dataclass
class ParenExpr:
    """Parenthesised expression ``( expr )``."""

    expr: MExpr


@dataclass
class ErrorExpr:
    """``error <expr>``"""

    expr: MExpr


@dataclass
class TypeExpr:
    """``type <name>`` — used in Table.Group aggregation specs."""

    name: str


@dataclass
class MetaExpr:
    """``expr meta record`` — metadata annotation."""

    expr: MExpr
    meta: MExpr
