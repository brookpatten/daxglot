"""Unit tests for the DAX parser and transpiler."""

from __future__ import annotations

import pytest

from daxglot.tokens import Lexer, LexError, TokenType
from daxglot.ast_nodes import (
    Aggregation,
    BinaryOp,
    Calculate,
    CalculateTable,
    ColumnRef,
    ContextFunction,
    CountRows,
    DaxNode,
    EvaluateQuery,
    Filter,
    FunctionCall,
    IfExpr,
    InExpr,
    Iterator,
    Literal,
    MeasureExpr,
    NotInExpr,
    OrderBy,
    OrderByItem,
    RelatedFunction,
    SwitchCase,
    SwitchExpr,
    TableRef,
    UnaryOp,
    VarBlock,
    VarDef,
)
from daxglot.parser import DaxParser, ParseError, parse_dax
from daxglot.transpiler import DaxToSqlTranspiler, dax_to_sql


# ===========================================================================
# Helpers
# ===========================================================================


def token_types(text: str) -> list[str]:
    return [t.type.name for t in Lexer.tokenize(text) if t.type.name != "EOF"]


def token_values(text: str) -> list[str]:
    return [t.value for t in Lexer.tokenize(text) if t.type.name != "EOF"]


# ===========================================================================
# LEXER tests
# ===========================================================================


@pytest.mark.unit
class TestLexer:
    def test_simple_number(self):
        toks = Lexer.tokenize("42")
        assert toks[0].type == TokenType.NUMBER
        assert toks[0].value == "42"

    def test_float_number(self):
        toks = Lexer.tokenize("3.14")
        assert toks[0].type == TokenType.NUMBER
        assert toks[0].value == "3.14"

    def test_string_literal(self):
        toks = Lexer.tokenize('"hello world"')
        assert toks[0].type == TokenType.STRING_LIT
        assert toks[0].value == "hello world"

    def test_string_escaped_doublequote(self):
        toks = Lexer.tokenize('"say ""hi"""')
        assert toks[0].type == TokenType.STRING_LIT
        assert toks[0].value == 'say "hi"'

    def test_column_ref(self):
        toks = Lexer.tokenize("Sales[Amount]")
        assert len(toks) == 2  # COLUMN_REF + EOF
        assert toks[0].type == TokenType.COLUMN_REF
        assert toks[0].value == "Sales[Amount]"

    def test_column_ref_with_spaces_in_column(self):
        toks = Lexer.tokenize("Changes[new_value]")
        assert toks[0].type == TokenType.COLUMN_REF
        assert toks[0].value == "Changes[new_value]"

    def test_column_only(self):
        toks = Lexer.tokenize("[Revenue]")
        assert toks[0].type == TokenType.COLUMN_ONLY
        assert toks[0].value == "Revenue"

    def test_quoted_identifier(self):
        toks = Lexer.tokenize("'My Table'")
        assert toks[0].type == TokenType.QUOTED_IDENTIFIER
        assert toks[0].value == "My Table"

    def test_two_char_ops(self):
        assert token_types("<> <= >= && ||") == [
            "NEQ", "LTE", "GTE", "AND_OP", "OR_OP"]

    def test_single_char_ops(self):
        assert token_types(
            "= < > + - * /") == ["EQ", "LT", "GT", "PLUS", "MINUS", "STAR", "SLASH"]

    def test_keywords_case_insensitive(self):
        types = token_types("calculate FILTER All")
        assert types == ["CALCULATE", "FILTER", "ALL"]

    def test_line_comment_stripped(self):
        types = token_types("42 // this is a comment\n+ 1")
        assert types == ["NUMBER", "PLUS", "NUMBER"]

    def test_block_comment_stripped(self):
        types = token_types("42 /* block */ + 1")
        assert types == ["NUMBER", "PLUS", "NUMBER"]

    def test_true_false_blank(self):
        types = token_types("TRUE FALSE BLANK")
        assert types == ["TRUE", "FALSE", "BLANK"]

    def test_in_brace_syntax(self):
        types = token_types('x IN {"a", "b"}')
        assert types == ["IDENTIFIER", "IN", "LBRACE",
                         "STRING_LIT", "COMMA", "STRING_LIT", "RBRACE"]

    def test_var_return_keywords(self):
        types = token_types("VAR RETURN")
        assert types == ["VAR", "RETURN"]

    def test_evaluate_keyword(self):
        types = token_types("EVALUATE")
        assert types == ["EVALUATE"]

    def test_complex_expression_tokens(self):
        text = "CALCULATE(MAX(Changes[new_value]), FILTER(Changes, Changes[member_id] = 1))"
        types = token_types(text)
        assert "CALCULATE" in types
        # MAX is an IDENTIFIER (not a keyword token!)
        assert "MAX" not in types
        assert "FILTER" in types
        assert "COLUMN_REF" in types

    def test_unterminated_string_raises(self):
        with pytest.raises(LexError):
            Lexer.tokenize('"unterminated')

    def test_unterminated_bracket_raises(self):
        with pytest.raises(LexError):
            Lexer.tokenize("[unterminated")


# ===========================================================================
# PARSER tests
# ===========================================================================


@pytest.mark.unit
class TestParserLiterals:
    def test_number_literal(self):
        node = parse_dax("42")
        assert isinstance(node, Literal)
        assert node.value == 42
        assert node.kind == "NUMBER"

    def test_float_literal(self):
        node = parse_dax("3.14")
        assert isinstance(node, Literal)
        assert node.value == 3.14

    def test_string_literal(self):
        node = parse_dax('"hello"')
        assert isinstance(node, Literal)
        assert node.value == "hello"
        assert node.kind == "STRING"

    def test_true_literal(self):
        node = parse_dax("TRUE")
        assert isinstance(node, Literal)
        assert node.value is True
        assert node.kind == "BOOLEAN"

    def test_false_literal(self):
        node = parse_dax("FALSE")
        assert isinstance(node, Literal)
        assert node.value is False

    def test_blank_literal(self):
        node = parse_dax("BLANK()")
        assert isinstance(node, Literal)
        assert node.kind == "BLANK"
        assert node.value is None


@pytest.mark.unit
class TestParserColumnRefs:
    def test_table_column_ref(self):
        node = parse_dax("Sales[Amount]")
        assert isinstance(node, ColumnRef)
        assert node.table == "Sales"
        assert node.column == "Amount"

    def test_column_only_ref(self):
        node = parse_dax("[Revenue]")
        assert isinstance(node, ColumnRef)
        assert node.table is None
        assert node.column == "Revenue"

    def test_quoted_table_column_ref(self):
        node = parse_dax("'My Table'[My Column]")
        assert isinstance(node, ColumnRef)
        assert node.table == "My Table"
        assert node.column == "My Column"

    def test_table_ref(self):
        node = parse_dax("Sales")
        assert isinstance(node, TableRef)
        assert node.name == "Sales"


@pytest.mark.unit
class TestParserBinaryOps:
    def test_equality(self):
        node = parse_dax('Changes[member_id] = "abc"')
        assert isinstance(node, BinaryOp)
        assert node.op == "="
        assert isinstance(node.left, ColumnRef)
        assert node.left.table == "Changes"
        assert isinstance(node.right, Literal)
        assert node.right.value == "abc"

    def test_less_than(self):
        node = parse_dax("Changes[start_date] < 5")
        assert isinstance(node, BinaryOp)
        assert node.op == "<"

    def test_not_equal(self):
        node = parse_dax("x[a] <> 0")
        assert isinstance(node, BinaryOp)
        assert node.op == "<>"

    def test_and_op(self):
        node = parse_dax("a[x] = 1 && b[y] = 2")
        assert isinstance(node, BinaryOp)
        assert node.op == "&&"
        assert isinstance(node.left, BinaryOp)
        assert isinstance(node.right, BinaryOp)

    def test_or_keyword(self):
        node = parse_dax("a[x] = 1 OR b[y] = 2")
        assert isinstance(node, BinaryOp)
        assert node.op in ("OR", "||")

    def test_arithmetic(self):
        node = parse_dax("3 + 4 * 2")
        # 3 + (4 * 2) — multiplication has higher precedence
        assert isinstance(node, BinaryOp)
        assert node.op == "+"
        assert isinstance(node.right, BinaryOp)
        assert node.right.op == "*"

    def test_string_concat(self):
        node = parse_dax('"a" & "b"')
        assert isinstance(node, BinaryOp)
        assert node.op == "&"


@pytest.mark.unit
class TestParserUnaryOps:
    def test_unary_minus(self):
        node = parse_dax("- 5")
        assert isinstance(node, UnaryOp)
        assert node.op == "-"
        assert isinstance(node.expr, Literal)

    def test_not_keyword(self):
        node = parse_dax("NOT TRUE")
        assert isinstance(node, UnaryOp)
        assert node.op == "NOT"


@pytest.mark.unit
class TestParserAggregations:
    def test_sum(self):
        node = parse_dax("SUM(Sales[Amount])")
        assert isinstance(node, Aggregation)
        assert node.func == "SUM"
        assert isinstance(node.expr, ColumnRef)
        assert node.expr.table == "Sales"

    def test_max(self):
        node = parse_dax("MAX(Changes[new_value])")
        assert isinstance(node, Aggregation)
        assert node.func == "MAX"

    def test_min(self):
        node = parse_dax("MIN(T[col])")
        assert isinstance(node, Aggregation)
        assert node.func == "MIN"

    def test_count(self):
        node = parse_dax("COUNT(T[col])")
        assert isinstance(node, Aggregation)
        assert node.func == "COUNT"

    def test_distinctcount(self):
        node = parse_dax("DISTINCTCOUNT(T[col])")
        assert isinstance(node, Aggregation)
        assert node.func == "DISTINCTCOUNT"

    def test_countrows(self):
        node = parse_dax("COUNTROWS(Sales)")
        assert isinstance(node, CountRows)
        assert isinstance(node.table_expr, TableRef)


@pytest.mark.unit
class TestParserMeasureExpr:
    def test_measure_starts_with_eq(self):
        node = parse_dax("= SUM(Sales[Amount])")
        assert isinstance(node, MeasureExpr)
        assert isinstance(node.expr, Aggregation)

    def test_measure_max(self):
        node = parse_dax("= MAX(Changes[new_value])")
        assert isinstance(node, MeasureExpr)
        assert isinstance(node.expr, Aggregation)
        assert node.expr.func == "MAX"


@pytest.mark.unit
class TestParserCalculate:
    def test_calculate_simple(self):
        node = parse_dax('CALCULATE(SUM(T[x]), FILTER(T, T[y] = 1))')
        assert isinstance(node, Calculate)
        assert isinstance(node.expr, Aggregation)
        assert len(node.filters) == 1
        assert isinstance(node.filters[0], Filter)

    def test_calculate_multiple_filters(self):
        node = parse_dax(
            'CALCULATE(SUM(T[x]), FILTER(T, T[a] = 1), FILTER(T, T[b] = "x"))'
        )
        assert isinstance(node, Calculate)
        assert len(node.filters) == 2

    def test_calculatetable(self):
        node = parse_dax(
            "CALCULATETABLE(Sales, FILTER(Sales, Sales[Year] = 2024))")
        assert isinstance(node, CalculateTable)
        assert isinstance(node.table_expr, TableRef)
        assert len(node.filters) == 1

    def test_nested_calculatetable_in_filter(self):
        # FILTER( CALCULATETABLE(T, ...), condition )
        node = parse_dax(
            "FILTER(CALCULATETABLE(Changes, FILTER(Changes, Changes[x] = 1)), Changes[y] = 2)"
        )
        assert isinstance(node, Filter)
        assert isinstance(node.table_expr, CalculateTable)


@pytest.mark.unit
class TestParserContextFunctions:
    def test_earlier(self):
        node = parse_dax("EARLIER(Changes[member_id])")
        assert isinstance(node, ContextFunction)
        assert node.func == "EARLIER"
        assert isinstance(node.expr, ColumnRef)
        assert node.depth == 1

    def test_earliest(self):
        node = parse_dax("EARLIEST(Changes[start_date])")
        assert isinstance(node, ContextFunction)
        assert node.func == "EARLIEST"

    def test_earlier_with_depth(self):
        node = parse_dax("EARLIER(T[col], 2)")
        assert isinstance(node, ContextFunction)
        assert node.depth == 2


@pytest.mark.unit
class TestParserRelatedFunctions:
    def test_related(self):
        node = parse_dax("RELATED(Products[Category])")
        assert isinstance(node, RelatedFunction)
        assert node.func == "RELATED"

    def test_relatedtable(self):
        node = parse_dax("RELATEDTABLE(Orders)")
        assert isinstance(node, RelatedFunction)
        assert node.func == "RELATEDTABLE"


@pytest.mark.unit
class TestParserIfSwitch:
    def test_if_expr(self):
        node = parse_dax('IF(T[x] > 0, "positive", "non-positive")')
        assert isinstance(node, IfExpr)
        assert isinstance(node.condition, BinaryOp)
        assert node.condition.op == ">"
        assert isinstance(node.true_val, Literal)
        assert isinstance(node.false_val, Literal)

    def test_if_two_args(self):
        node = parse_dax("IF(T[x] = 1, 100)")
        assert isinstance(node, IfExpr)
        assert node.false_val is None

    def test_switch_expr(self):
        node = parse_dax('SWITCH(T[status], "A", 1, "B", 2, 0)')
        assert isinstance(node, SwitchExpr)
        assert len(node.cases) == 2
        assert isinstance(node.default, Literal)
        assert node.default.value == 0


@pytest.mark.unit
class TestParserInExpr:
    def test_in_expr(self):
        node = parse_dax('T[col] IN {"a", "b", "c"}')
        assert isinstance(node, InExpr)
        assert len(node.values) == 3

    def test_not_in_expr(self):
        node = parse_dax('T[col] NOT IN {"x", "y"}')
        assert isinstance(node, NotInExpr)
        assert len(node.values) == 2


@pytest.mark.unit
class TestParserIterator:
    def test_sumx(self):
        node = parse_dax("SUMX(Sales, Sales[Price] * Sales[Qty])")
        assert isinstance(node, Iterator)
        assert node.func == "SUMX"
        assert isinstance(node.table_expr, TableRef)
        assert isinstance(node.body, BinaryOp)

    def test_maxx(self):
        node = parse_dax("MAXX(T, T[col])")
        assert isinstance(node, Iterator)
        assert node.func == "MAXX"


@pytest.mark.unit
class TestParserVarBlock:
    def test_var_return(self):
        node = parse_dax("VAR x = 10 RETURN x + 1")
        assert isinstance(node, VarBlock)
        assert len(node.vars) == 1
        assert node.vars[0].name == "x"
        assert isinstance(node.vars[0].expr, Literal)
        assert isinstance(node.return_expr, BinaryOp)

    def test_multiple_vars(self):
        node = parse_dax("VAR a = 1 VAR b = 2 RETURN a + b")
        assert isinstance(node, VarBlock)
        assert len(node.vars) == 2

    def test_measure_with_var(self):
        node = parse_dax("= VAR total = SUM(Sales[Amount]) RETURN total")
        assert isinstance(node, MeasureExpr)
        assert isinstance(node.expr, VarBlock)

    def test_var_with_calculate(self):
        node = parse_dax(
            '= VAR filtered = CALCULATETABLE(Sales, FILTER(Sales, Sales[Year] = 2024)) RETURN SUM(Sales[Amount])'
        )
        assert isinstance(node, MeasureExpr)
        assert isinstance(node.expr, VarBlock)
        assert isinstance(node.expr.vars[0].expr, CalculateTable)


@pytest.mark.unit
class TestParserEvaluateQuery:
    def test_evaluate_table(self):
        node = parse_dax("EVALUATE Sales")
        assert isinstance(node, EvaluateQuery)
        assert isinstance(node.table_expr, TableRef)
        assert node.table_expr.name == "Sales"
        assert node.order_by is None

    def test_evaluate_with_order_by(self):
        node = parse_dax("EVALUATE Sales ORDER BY Sales[Amount] DESC")
        assert isinstance(node, EvaluateQuery)
        assert isinstance(node.order_by, OrderBy)
        assert len(node.order_by.items) == 1
        assert node.order_by.items[0].direction == "DESC"

    def test_evaluate_with_filter(self):
        node = parse_dax('EVALUATE FILTER(Sales, Sales[Region] = "West")')
        assert isinstance(node, EvaluateQuery)
        assert isinstance(node.table_expr, Filter)

    def test_evaluate_calculatetable(self):
        node = parse_dax(
            'EVALUATE CALCULATETABLE(Sales, FILTER(Sales, Sales[Year] = 2024))'
        )
        assert isinstance(node, EvaluateQuery)
        assert isinstance(node.table_expr, CalculateTable)


@pytest.mark.unit
class TestParserComplexExample:
    """Tests the complex CALCULATE example provided by the user."""

    EXAMPLE = """= CALCULATE(
        MAX(Changes[new_value]),
        FILTER(Changes, Changes[member_id] = EARLIER(Changes[member_id])),
        FILTER(Changes, Changes[change_type] = "Type"),
        FILTER(
            Changes,
            Changes[start_date]
                = CALCULATE(
                    MAX(Changes[start_date]),
                    FILTER(
                        CALCULATETABLE(
                            Changes,
                            FILTER(Changes, Changes[member_id] = EARLIEST(Changes[member_id])),
                            FILTER(Changes, Changes[change_type] = "Type")
                        ),
                        Changes[start_date] < EARLIEST(Changes[start_date])
                    )
                )
        )
    )"""

    def test_parses_without_error(self):
        node = parse_dax(self.EXAMPLE)
        assert isinstance(node, MeasureExpr)

    def test_top_level_calculate(self):
        node = parse_dax(self.EXAMPLE)
        assert isinstance(node.expr, Calculate)

    def test_calculate_has_three_filters(self):
        node = parse_dax(self.EXAMPLE)
        calc = node.expr
        assert len(calc.filters) == 3

    def test_inner_expr_is_max(self):
        node = parse_dax(self.EXAMPLE)
        calc = node.expr
        assert isinstance(calc.expr, Aggregation)
        assert calc.expr.func == "MAX"

    def test_first_filter_uses_earlier(self):
        node = parse_dax(self.EXAMPLE)
        f = node.expr.filters[0]
        assert isinstance(f, Filter)
        assert isinstance(f.condition, BinaryOp)
        # Right side of equality should be EARLIER(...)
        assert isinstance(f.condition.right, ContextFunction)
        assert f.condition.right.func == "EARLIER"

    def test_third_filter_condition_is_calculate(self):
        node = parse_dax(self.EXAMPLE)
        f = node.expr.filters[2]
        assert isinstance(f, Filter)
        # Changes[start_date] = CALCULATE(...)
        cond = f.condition
        assert isinstance(cond, BinaryOp)
        assert cond.op == "="
        assert isinstance(cond.right, Calculate)

    def test_nested_calculatetable(self):
        node = parse_dax(self.EXAMPLE)
        outer_calc = node.expr.filters[2].condition.right
        inner_filter = outer_calc.filters[0]
        assert isinstance(inner_filter, Filter)
        # Table inside FILTER is a CALCULATETABLE
        assert isinstance(inner_filter.table_expr, CalculateTable)

    def test_earliest_in_nested_filter(self):
        node = parse_dax(self.EXAMPLE)
        outer_calc = node.expr.filters[2].condition.right
        # The outer_calc's FILTER has a condition with EARLIEST
        inner_filter_cond = outer_calc.filters[0].condition
        assert isinstance(inner_filter_cond, BinaryOp)
        assert isinstance(inner_filter_cond.right, ContextFunction)
        assert inner_filter_cond.right.func == "EARLIEST"

    def test_pretty_print_does_not_raise(self):
        node = parse_dax(self.EXAMPLE)
        result = node.pretty()
        assert "MeasureExpr" in result
        assert "Calculate" in result


# ===========================================================================
# TRANSPILER tests
# ===========================================================================


@pytest.mark.unit
class TestTranspilerLeafs:
    def _t(self, node: DaxNode) -> str:
        return DaxToSqlTranspiler().transpile(node).sql(dialect="spark")

    def test_column_ref_with_table(self):
        sql = self._t(ColumnRef(table="Sales", column="Amount"))
        assert "Amount" in sql
        assert "Sales" in sql

    def test_column_ref_no_table(self):
        sql = self._t(ColumnRef(table=None, column="Revenue"))
        assert "Revenue" in sql

    def test_string_literal(self):
        sql = self._t(Literal(value="hello", kind="STRING"))
        assert "hello" in sql

    def test_number_literal_int(self):
        sql = self._t(Literal(value=42, kind="NUMBER"))
        assert "42" in sql

    def test_number_literal_float(self):
        sql = self._t(Literal(value=3.14, kind="NUMBER"))
        assert "3.14" in sql

    def test_blank_literal(self):
        sql = self._t(Literal(value=None, kind="BLANK"))
        assert sql.upper() == "NULL"

    def test_true_literal(self):
        sql = self._t(Literal(value=True, kind="BOOLEAN"))
        assert sql.upper() == "TRUE"

    def test_false_literal(self):
        sql = self._t(Literal(value=False, kind="BOOLEAN"))
        assert sql.upper() == "FALSE"


@pytest.mark.unit
class TestTranspilerOperators:
    def _t(self, text: str, dialect: str = "spark") -> str:
        return dax_to_sql(parse_dax(text), dialect=dialect)

    def test_equality(self):
        sql = self._t('T[a] = "x"')
        assert "=" in sql

    def test_addition(self):
        sql = self._t("1 + 2")
        assert "+" in sql

    def test_subtraction(self):
        sql = self._t("5 - 3")
        assert "-" in sql

    def test_and_op(self):
        sql = self._t("T[a] = 1 AND T[b] = 2")
        assert "AND" in sql.upper()

    def test_or_op(self):
        sql = self._t("T[a] = 1 OR T[b] = 2")
        assert "OR" in sql.upper()

    def test_not_op(self):
        sql = self._t("NOT TRUE")
        assert "NOT" in sql.upper()

    def test_unary_minus(self):
        sql = self._t("-5")
        assert sql.strip() == "-5"


@pytest.mark.unit
class TestTranspilerAggregations:
    def _t(self, text: str, dialect: str = "spark") -> str:
        return dax_to_sql(parse_dax(text), dialect=dialect)

    def test_sum(self):
        sql = self._t("= SUM(Sales[Amount])")
        assert sql.upper().startswith("SUM(")

    def test_max(self):
        sql = self._t("= MAX(T[col])")
        assert sql.upper().startswith("MAX(")

    def test_min(self):
        sql = self._t("= MIN(T[col])")
        assert sql.upper().startswith("MIN(")

    def test_average(self):
        sql = self._t("= AVERAGE(T[col])")
        assert "AVG" in sql.upper()

    def test_count(self):
        sql = self._t("= COUNT(T[col])")
        assert "COUNT" in sql.upper()

    def test_countrows(self):
        sql = self._t("= COUNTROWS(Sales)")
        assert "COUNT" in sql.upper()

    def test_distinctcount(self):
        sql = self._t("= DISTINCTCOUNT(T[col])")
        assert "COUNT" in sql.upper()
        assert "DISTINCT" in sql.upper()

    def test_dialect_duckdb(self):
        sql = self._t("= SUM(Sales[Amount])", dialect="duckdb")
        assert "SUM" in sql.upper()

    def test_dialect_tsql(self):
        sql = self._t("= SUM(Sales[Amount])", dialect="tsql")
        assert "SUM" in sql.upper()


@pytest.mark.unit
class TestTranspilerFilter:
    def _t(self, text: str, dialect: str = "spark") -> str:
        return dax_to_sql(parse_dax(text), dialect=dialect)

    def test_filter_becomes_subquery(self):
        sql = self._t('FILTER(Sales, Sales[Region] = "West")')
        assert "SELECT" in sql.upper()
        assert "WHERE" in sql.upper()

    def test_calculate_with_filter(self):
        sql = self._t('= CALCULATE(SUM(T[x]), FILTER(T, T[y] = 1))')
        assert "SUM" in sql.upper()
        assert "WHERE" in sql.upper()

    def test_calculate_multiple_filters(self):
        sql = self._t(
            '= CALCULATE(SUM(T[x]), FILTER(T, T[a] = 1), FILTER(T, T[b] = "x"))'
        )
        assert "WHERE" in sql.upper()


@pytest.mark.unit
class TestTranspilerIfSwitch:
    def _t(self, text: str, dialect: str = "spark") -> str:
        return dax_to_sql(parse_dax(text), dialect=dialect)

    def test_if_expr(self):
        sql = self._t('= IF(T[x] > 0, "positive", "negative")')
        assert "IF" in sql.upper() or "CASE" in sql.upper()

    def test_switch_expr(self):
        sql = self._t('= SWITCH(T[status], "A", 1, "B", 2, 0)')
        assert "CASE" in sql.upper() or "WHEN" in sql.upper()


@pytest.mark.unit
class TestTranspilerEvaluateQuery:
    def _t(self, text: str, dialect: str = "spark") -> str:
        return dax_to_sql(parse_dax(text), dialect=dialect)

    def test_evaluate_table(self):
        sql = self._t("EVALUATE Sales")
        assert "SELECT" in sql.upper()
        assert "Sales" in sql

    def test_evaluate_with_order_by(self):
        sql = self._t("EVALUATE Sales ORDER BY Sales[Amount] DESC")
        assert "ORDER BY" in sql.upper()
        assert "DESC" in sql.upper()

    def test_evaluate_filter(self):
        sql = self._t('EVALUATE FILTER(Sales, Sales[Region] = "West")')
        assert "SELECT" in sql.upper()
        assert "WHERE" in sql.upper()


@pytest.mark.unit
class TestTranspilerComplexExample:
    """Transpile the provided complex CALCULATE example without errors."""

    EXAMPLE = """= CALCULATE(
        MAX(Changes[new_value]),
        FILTER(Changes, Changes[member_id] = EARLIER(Changes[member_id])),
        FILTER(Changes, Changes[change_type] = "Type"),
        FILTER(
            Changes,
            Changes[start_date]
                = CALCULATE(
                    MAX(Changes[start_date]),
                    FILTER(
                        CALCULATETABLE(
                            Changes,
                            FILTER(Changes, Changes[member_id] = EARLIEST(Changes[member_id])),
                            FILTER(Changes, Changes[change_type] = "Type")
                        ),
                        Changes[start_date] < EARLIEST(Changes[start_date])
                    )
                )
        )
    )"""

    def test_transpiles_without_error_spark(self):
        sql = dax_to_sql(parse_dax(self.EXAMPLE), dialect="spark")
        assert isinstance(sql, str)
        assert len(sql) > 0

    def test_transpiles_without_error_duckdb(self):
        sql = dax_to_sql(parse_dax(self.EXAMPLE), dialect="duckdb")
        assert isinstance(sql, str)
        assert len(sql) > 0

    def test_output_contains_max(self):
        sql = dax_to_sql(parse_dax(self.EXAMPLE), dialect="spark")
        assert "MAX" in sql.upper()

    def test_output_contains_where(self):
        sql = dax_to_sql(parse_dax(self.EXAMPLE), dialect="spark")
        assert "WHERE" in sql.upper()
