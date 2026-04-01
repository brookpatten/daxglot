"""powermglot — Power Query M parser and SQL transpiler.

Public API::

    from powermglot import parse_m, m_to_sql, MToSqlTranspiler

    # Parse an M expression into an AST
    ast = parse_m("let Source = ... in result")

    # Transpile directly to SQL
    sql = m_to_sql("let Source = ... in result", dialect="spark")

    # Use the transpiler class for more control
    transpiler = MToSqlTranspiler()
    sql = transpiler.transpile(ast, dialect="tsql")
"""

from __future__ import annotations

from .ast_nodes import (
    BinaryOpExpr,
    CallExpr,
    EachExpr,
    ErrorExpr,
    FieldAccessExpr,
    FieldRef,
    IdentExpr,
    IfExpr,
    LetExpr,
    ListExpr,
    LiteralExpr,
    MetaExpr,
    MExpr,
    NavExpr,
    ParenExpr,
    RecordExpr,
    TypeExpr,
    UnaryOpExpr,
)
from .lexer import LexError, Lexer, Token, TokenType
from .parser import MParser, ParseError, parse_m
from .transpiler import MToSqlTranspiler, MSourceInfo, TranspilerError, m_to_sql, parse_m_source

__all__ = [
    # Entry points
    "parse_m",
    "m_to_sql",
    "parse_m_source",
    # Transpiler
    "MToSqlTranspiler",
    "MSourceInfo",
    "TranspilerError",
    # Parser
    "MParser",
    "ParseError",
    # Lexer
    "Lexer",
    "LexError",
    "Token",
    "TokenType",
    # AST nodes
    "MExpr",
    "LetExpr",
    "IdentExpr",
    "LiteralExpr",
    "ListExpr",
    "RecordExpr",
    "CallExpr",
    "NavExpr",
    "FieldAccessExpr",
    "FieldRef",
    "EachExpr",
    "BinaryOpExpr",
    "UnaryOpExpr",
    "IfExpr",
    "ParenExpr",
    "ErrorExpr",
    "TypeExpr",
    "MetaExpr",
]
