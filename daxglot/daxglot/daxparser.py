"""DAX parser — public facade.

This module is the primary entry point for the DAX parser library.

Quickstart::

    from dax.daxparser import parse_dax, dax_to_sql

    # Parse into an AST
    ast = parse_dax("= CALCULATE(SUM(Sales[Amount]), FILTER(Sales, Sales[Region] = \\"West\\"))")
    print(ast.pretty())

    # Transpile to SQL (any sqlglot dialect)
    sql = dax_to_sql(ast, dialect="spark")
    print(sql)
"""

from __future__ import annotations

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
    SwitchCase,
    SwitchExpr,
    TableRef,
    TreatAs,
    UnaryOp,
    UseRelationship,
    VarBlock,
    VarDef,
)
from .measure_translator import MeasureTranslation, WindowSpec, translate_measure
from .parser import DaxParser, ParseError, parse_dax
from .transpiler import DaxToSqlTranspiler, TranspilerError, dax_to_sql

__all__ = [
    # Parse entry points
    "parse_dax",
    "DaxParser",
    "ParseError",
    # Transpile entry points
    "dax_to_sql",
    "DaxToSqlTranspiler",
    "TranspilerError",
    # AST node types
    "DaxNode",
    "EvaluateQuery",
    "MeasureExpr",
    "VarDef",
    "VarBlock",
    "Calculate",
    "CalculateTable",
    "Filter",
    "All",
    "AllExcept",
    "KeepFilters",
    "RemoveFilters",
    "TreatAs",
    "UseRelationship",
    "CrossFilter",
    "Aggregation",
    "CountRows",
    "Iterator",
    "ContextFunction",
    "RelatedFunction",
    "FunctionCall",
    "IfExpr",
    "IfError",
    "SwitchCase",
    "SwitchExpr",
    "BinaryOp",
    "UnaryOp",
    "InExpr",
    "NotInExpr",
    "ColumnRef",
    "TableRef",
    "Literal",
    "OrderBy",
    "OrderByItem",
    # Measure translation
    "translate_measure",
    "MeasureTranslation",
    "WindowSpec",
]
