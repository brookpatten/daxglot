"""Unit tests for powermglot — M parser and SQL transpiler."""

from __future__ import annotations

import pytest

from powermglot.lexer import Lexer, LexError, TokenType
from powermglot.ast_nodes import (
    BinaryOpExpr,
    CallExpr,
    EachExpr,
    FieldAccessExpr,
    IdentExpr,
    LetExpr,
    ListExpr,
    LiteralExpr,
    NavExpr,
    RecordExpr,
)
from powermglot.parser import MParser, ParseError, parse_m
from powermglot.transpiler import MToSqlTranspiler, TranspilerError, m_to_sql


# ===========================================================================
# LEXER tests
# ===========================================================================


@pytest.mark.unit
class TestLexer:
    def _types(self, text: str) -> list[str]:
        return [t.type.name for t in Lexer.tokenize(text) if t.type != TokenType.EOF]

    def _values(self, text: str) -> list[str]:
        return [t.value for t in Lexer.tokenize(text) if t.type != TokenType.EOF]

    def test_keywords(self):
        types = self._types("let in each if then else true false null not and or")
        assert types == [
            "LET", "IN", "EACH", "IF", "THEN", "ELSE",
            "TRUE", "FALSE", "NULL", "NOT", "AND", "OR",
        ]

    def test_identifier(self):
        toks = Lexer.tokenize("Source")
        assert toks[0].type == TokenType.IDENT
        assert toks[0].value == "Source"

    def test_quoted_identifier(self):
        toks = Lexer.tokenize('#"My Table"')
        assert toks[0].type == TokenType.QUOTED_IDENT
        assert toks[0].value == "My Table"

    def test_string_literal(self):
        toks = Lexer.tokenize('"hello world"')
        assert toks[0].type == TokenType.STRING
        assert toks[0].value == "hello world"

    def test_string_escaped_doublequote(self):
        toks = Lexer.tokenize('"say ""hi"""')
        assert toks[0].type == TokenType.STRING
        assert toks[0].value == 'say "hi"'

    def test_integer(self):
        toks = Lexer.tokenize("42")
        assert toks[0].type == TokenType.NUMBER
        assert toks[0].value == "42"

    def test_decimal(self):
        toks = Lexer.tokenize("3.14")
        assert toks[0].type == TokenType.NUMBER
        assert toks[0].value == "3.14"

    def test_two_char_operators(self):
        types = self._types("<> <= >= =>")
        assert types == ["NEQ", "LTE", "GTE", "ARROW"]

    def test_dot_operator(self):
        types = self._types(".")
        assert types == ["DOT"]

    def test_punctuation(self):
        types = self._types("{ } [ ] ( ) , = :")
        assert types == [
            "LBRACE", "RBRACE", "LBRACKET", "RBRACKET",
            "LPAREN", "RPAREN", "COMMA", "EQ", "COLON",
        ]

    def test_line_comment_skipped(self):
        types = self._types("42 // this is a comment\n99")
        assert types == ["NUMBER", "NUMBER"]

    def test_block_comment_skipped(self):
        types = self._types("42 /* comment */ 99")
        assert types == ["NUMBER", "NUMBER"]

    def test_unexpected_char(self):
        with pytest.raises(LexError):
            Lexer.tokenize("~")


# ===========================================================================
# PARSER tests
# ===========================================================================


@pytest.mark.unit
class TestParser:
    def test_literal_string(self):
        node = parse_m('"hello"')
        assert isinstance(node, LiteralExpr)
        assert node.value == "hello"
        assert node.kind == "string"

    def test_literal_number(self):
        node = parse_m("42")
        assert isinstance(node, LiteralExpr)
        assert node.value == 42

    def test_literal_true(self):
        node = parse_m("true")
        assert isinstance(node, LiteralExpr)
        assert node.value is True

    def test_literal_null(self):
        node = parse_m("null")
        assert isinstance(node, LiteralExpr)
        assert node.value is None

    def test_identifier(self):
        node = parse_m("Source")
        assert isinstance(node, IdentExpr)
        assert node.name == "Source"

    def test_quoted_identifier(self):
        node = parse_m('#"My Table"')
        assert isinstance(node, IdentExpr)
        assert node.name == "My Table"

    def test_simple_let(self):
        node = parse_m('let x = 1 in x')
        assert isinstance(node, LetExpr)
        assert len(node.bindings) == 1
        assert node.bindings[0][0] == "x"

    def test_multi_binding_let(self):
        node = parse_m('let x = 1, y = 2 in y')
        assert isinstance(node, LetExpr)
        assert len(node.bindings) == 2

    def test_list_expr(self):
        node = parse_m('{"a", "b", "c"}')
        assert isinstance(node, ListExpr)
        assert len(node.items) == 3

    def test_record_expr(self):
        node = parse_m('[Name = "schema"]')
        assert isinstance(node, RecordExpr)
        assert node.fields[0][0] == "Name"

    def test_call_expr(self):
        node = parse_m("Databricks.Catalogs()")
        assert isinstance(node, CallExpr)

    def test_binary_op(self):
        node = parse_m('"a" = "b"')
        assert isinstance(node, BinaryOpExpr)
        assert node.op == "="

    def test_each_expr(self):
        node = parse_m('each [Status] = "Active"')
        assert isinstance(node, EachExpr)

    def test_nav_expr(self):
        node = parse_m('Source{[Name="schema"]}')
        assert isinstance(node, NavExpr)

    def test_field_access(self):
        node = parse_m('Source{[Name="schema"]}[Data]')
        assert isinstance(node, FieldAccessExpr)
        assert node.field == "Data"

    def test_dotted_name_in_call(self):
        node = parse_m('Table.SelectRows(src, each true)')
        assert isinstance(node, CallExpr)
        # function should be a FieldAccessExpr
        assert isinstance(node.function, FieldAccessExpr)
        assert node.function.field == "SelectRows"

    def test_if_expr(self):
        node = parse_m('if true then 1 else 2')
        from powermglot.ast_nodes import IfExpr
        assert isinstance(node, IfExpr)

    def test_and_or(self):
        node = parse_m('[A] = 1 and [B] = 2')
        assert isinstance(node, BinaryOpExpr)
        assert node.op == "and"

    def test_not_expr(self):
        node = parse_m('not true')
        from powermglot.ast_nodes import UnaryOpExpr
        assert isinstance(node, UnaryOpExpr)
        assert node.op == "not"

    def test_nested_let(self):
        m = """
        let
            a = 1,
            b = let c = 2 in c
        in b
        """
        node = parse_m(m)
        assert isinstance(node, LetExpr)

    def test_quoted_ident_in_binding(self):
        node = parse_m('let #"My Step" = 1 in #"My Step"')
        assert isinstance(node, LetExpr)
        assert node.bindings[0][0] == "My Step"


# ===========================================================================
# TRANSPILER tests
# ===========================================================================


@pytest.mark.unit
class TestTranspiler:
    def sql(self, m_text: str, dialect: str | None = None) -> str:
        return m_to_sql(m_text, dialect=dialect)

    # ------------------------------------------------------------------
    # Basic source navigation
    # ------------------------------------------------------------------

    def test_simple_databricks_three_level(self):
        m = """
        let
            Source = Databricks.Catalogs("host", "443", [Catalog="prod"]),
            prod_db = Source{[Name="pbi"]}[Data],
            orders = prod_db{[Name="orders"]}[Data]
        in
            orders
        """
        sql = self.sql(m)
        assert "prod.pbi.orders" in sql
        assert "SELECT" in sql

    def test_simple_sql_database_two_level(self):
        m = """
        let
            Source = Sql.Database("server", "mydb"),
            schema_data = Source{[Name="dbo"]}[Data],
            customers = schema_data{[Name="customers"]}[Data]
        in
            customers
        """
        sql = self.sql(m)
        assert "dbo.customers" in sql.lower() or "customers" in sql

    def test_native_query_passthrough(self):
        m = """
        let
            Source = Databricks.Catalogs("host"),
            q = Value.NativeQuery(Source, "SELECT id, name FROM prod.pbi.orders WHERE status = 'Active'")
        in
            q
        """
        sql = self.sql(m)
        # The native query SQL should be embedded as a subquery or passed through
        assert "prod.pbi.orders" in sql or "SELECT" in sql

    # ------------------------------------------------------------------
    # Table.SelectRows (WHERE)
    # ------------------------------------------------------------------

    def test_select_rows_equality(self):
        m = """
        let
            Source = Databricks.Catalogs("host", "443", [Catalog="prod"]),
            db = Source{[Name="pbi"]}[Data],
            tbl = db{[Name="orders"]}[Data],
            filtered = Table.SelectRows(tbl, each [status] = "Active")
        in
            filtered
        """
        sql = self.sql(m)
        assert "status" in sql.lower()
        assert "Active" in sql or "active" in sql.lower()
        assert "WHERE" in sql.upper()

    def test_select_rows_numeric_comparison(self):
        m = """
        let
            Source = Databricks.Catalogs("host", "443", [Catalog="prod"]),
            db = Source{[Name="pbi"]}[Data],
            tbl = db{[Name="orders"]}[Data],
            filtered = Table.SelectRows(tbl, each [Year] >= 2023)
        in
            filtered
        """
        sql = self.sql(m)
        assert "WHERE" in sql.upper()
        assert "2023" in sql

    def test_select_rows_and_condition(self):
        m = """
        let
            Source = Databricks.Catalogs("host", "443", [Catalog="prod"]),
            db = Source{[Name="pbi"]}[Data],
            tbl = db{[Name="orders"]}[Data],
            filtered = Table.SelectRows(tbl, each [status] = "Active" and [year] >= 2023)
        in
            filtered
        """
        sql = self.sql(m)
        assert "AND" in sql.upper()
        assert "WHERE" in sql.upper()

    def test_select_rows_or_condition(self):
        m = """
        let
            Source = Databricks.Catalogs("host", "443", [Catalog="prod"]),
            db = Source{[Name="pbi"]}[Data],
            tbl = db{[Name="orders"]}[Data],
            filtered = Table.SelectRows(tbl, each [region] = "US" or [region] = "EU")
        in
            filtered
        """
        sql = self.sql(m)
        assert "OR" in sql.upper()

    # ------------------------------------------------------------------
    # Table.SelectColumns
    # ------------------------------------------------------------------

    def test_select_columns(self):
        m = """
        let
            Source = Databricks.Catalogs("host", "443", [Catalog="prod"]),
            db = Source{[Name="pbi"]}[Data],
            tbl = db{[Name="orders"]}[Data],
            selected = Table.SelectColumns(tbl, {"order_id", "amount", "status"})
        in
            selected
        """
        sql = self.sql(m)
        assert "order_id" in sql
        assert "amount" in sql
        assert "status" in sql
        assert "*" not in sql

    # ------------------------------------------------------------------
    # Table.RenameColumns
    # ------------------------------------------------------------------

    def test_rename_columns(self):
        m = """
        let
            Source = Databricks.Catalogs("host", "443", [Catalog="prod"]),
            db = Source{[Name="pbi"]}[Data],
            tbl = db{[Name="orders"]}[Data],
            selected = Table.SelectColumns(tbl, {"amount", "status"}),
            renamed = Table.RenameColumns(selected, {{"amount", "total_amount"}})
        in
            renamed
        """
        sql = self.sql(m)
        assert "total_amount" in sql

    # ------------------------------------------------------------------
    # Table.AddColumn
    # ------------------------------------------------------------------

    def test_add_column(self):
        m = """
        let
            Source = Databricks.Catalogs("host", "443", [Catalog="prod"]),
            db = Source{[Name="pbi"]}[Data],
            tbl = db{[Name="orders"]}[Data],
            selected = Table.SelectColumns(tbl, {"amount", "tax_rate"}),
            enriched = Table.AddColumn(selected, "total", each [amount] * 1.1)
        in
            enriched
        """
        sql = self.sql(m)
        assert "total" in sql

    # ------------------------------------------------------------------
    # Table.RemoveColumns
    # ------------------------------------------------------------------

    def test_remove_columns(self):
        m = """
        let
            Source = Databricks.Catalogs("host", "443", [Catalog="prod"]),
            db = Source{[Name="pbi"]}[Data],
            tbl = db{[Name="orders"]}[Data],
            selected = Table.SelectColumns(tbl, {"order_id", "amount", "internal_col"}),
            cleaned = Table.RemoveColumns(selected, {"internal_col"})
        in
            cleaned
        """
        sql = self.sql(m)
        assert "order_id" in sql
        assert "amount" in sql
        assert "internal_col" not in sql

    # ------------------------------------------------------------------
    # Table.Group (GROUP BY)
    # ------------------------------------------------------------------

    def test_group_by(self):
        m = """
        let
            Source = Databricks.Catalogs("host", "443", [Catalog="prod"]),
            db = Source{[Name="pbi"]}[Data],
            tbl = db{[Name="orders"]}[Data],
            grouped = Table.Group(tbl, {"region"}, {{"total", each List.Sum([amount]), type number}})
        in
            grouped
        """
        sql = self.sql(m)
        assert "GROUP BY" in sql.upper()
        assert "region" in sql

    # ------------------------------------------------------------------
    # Combined chain
    # ------------------------------------------------------------------

    def test_full_chain(self):
        m = """
        let
            Source = Databricks.Catalogs("adb-123.azuredatabricks.net", "443", [Catalog="prod"]),
            prod_db = Source{[Name="pbi"]}[Data],
            orders_tbl = prod_db{[Name="orders"]}[Data],
            filtered = Table.SelectRows(orders_tbl, each [status] = "Active"),
            selected = Table.SelectColumns(filtered, {"order_id", "customer_id", "amount", "status"}),
            renamed = Table.RenameColumns(selected, {{"amount", "total_amount"}})
        in
            renamed
        """
        sql = self.sql(m)
        assert "prod.pbi.orders" in sql
        assert "WHERE" in sql.upper()
        assert "status" in sql
        assert "total_amount" in sql
        assert "order_id" in sql

    def test_quoted_ident_steps(self):
        m = """
        let
            Source = Databricks.Catalogs("host", "443", [Catalog="prod"]),
            #"prod Database" = Source{[Name="pbi"]}[Data],
            #"orders Table" = #"prod Database"{[Name="orders"]}[Data],
            #"Filtered Rows" = Table.SelectRows(#"orders Table", each [status] = "Active")
        in
            #"Filtered Rows"
        """
        sql = self.sql(m)
        assert "WHERE" in sql.upper()
        assert "prod.pbi.orders" in sql

    # ------------------------------------------------------------------
    # Dialect output
    # ------------------------------------------------------------------

    def test_spark_dialect(self):
        m = """
        let
            Source = Databricks.Catalogs("host", "443", [Catalog="prod"]),
            db = Source{[Name="pbi"]}[Data],
            tbl = db{[Name="orders"]}[Data]
        in tbl
        """
        sql = self.sql(m, dialect="spark")
        assert "SELECT" in sql.upper()

    def test_tsql_dialect(self):
        m = """
        let
            Source = Sql.Database("server", "mydb"),
            dbo = Source{[Name="dbo"]}[Data],
            customers = dbo{[Name="customers"]}[Data]
        in customers
        """
        sql = self.sql(m, dialect="tsql")
        assert "SELECT" in sql.upper()

    # ------------------------------------------------------------------
    # Error cases
    # ------------------------------------------------------------------

    def test_transpiler_requires_let_expr(self):
        from powermglot.ast_nodes import IdentExpr
        transpiler = MToSqlTranspiler()
        with pytest.raises(TranspilerError):
            transpiler.transpile(IdentExpr(name="foo"))

    def test_no_source_raises(self):
        m = "let x = 1 in x"
        with pytest.raises(TranspilerError):
            m_to_sql(m)

    # ------------------------------------------------------------------
    # Table.NestedJoin
    # ------------------------------------------------------------------

    def test_nested_join(self):
        m = """
        let
            Source = Databricks.Catalogs("host", "443", [Catalog="prod"]),
            db = Source{[Name="pbi"]}[Data],
            orders = db{[Name="orders"]}[Data],
            customers = db{[Name="customers"]}[Data],
            joined = Table.NestedJoin(orders, {"customer_id"}, customers, {"id"}, "CustomerData")
        in
            joined
        """
        sql = self.sql(m)
        assert "JOIN" in sql.upper()


# ===========================================================================
# parse_m_source tests
# ===========================================================================


@pytest.mark.unit
class TestParseMSource:
    """Tests for the parse_m_source convenience function."""

    def info(self, m_text: str):
        from powermglot import parse_m_source
        return parse_m_source(m_text)

    # ------------------------------------------------------------------
    # source_ref extraction
    # ------------------------------------------------------------------

    def test_three_level_nav_catalog_option(self):
        m = """
        let
            Source = Databricks.Catalogs("host", "443", [Catalog="prod"]),
            db = Source{[Name="pbi"]}[Data],
            tbl = db{[Name="orders"]}[Data]
        in tbl
        """
        i = self.info(m)
        assert i.source_ref == "prod.pbi.orders"
        assert i.native_sql is None
        assert i.filter_sql is None

    def test_three_level_nav_no_catalog(self):
        m = """
        let
            Source = Databricks.Catalogs("host"),
            cat = Source{[Name="prod"]}[Data],
            sch = cat{[Name="retaildb"]}[Data],
            tbl = sch{[Name="orders"]}[Data]
        in tbl
        """
        i = self.info(m)
        assert i.source_ref == "prod.retaildb.orders"

    def test_two_level_nav_no_catalog(self):
        m = """
        let
            Source = Databricks.Catalogs("host"),
            sch = Source{[Name="finance"]}[Data],
            tbl = sch{[Name="sales_fact"]}[Data]
        in tbl
        """
        i = self.info(m)
        assert i.source_ref == "finance.sales_fact"

    def test_sql_database_connector(self):
        m = (
            'let Source = Sql.Database("server", "prod"), '
            'db = Source{[Name="pbi"]}[Data], '
            'tbl = db{[Name="orders"]}[Data] in tbl'
        )
        i = self.info(m)
        assert i.source_ref == "prod.pbi.orders"

    def test_unknown_connector_gives_table_only(self):
        m = 'let src = CustomConnector("host"), t = src{[Name="orders"]}[Data] in t'
        i = self.info(m)
        assert i.source_ref == "orders"

    # ------------------------------------------------------------------
    # native_sql extraction
    # ------------------------------------------------------------------

    def test_native_query_returns_native_sql(self):
        m = 'let q = Value.NativeQuery(src, "SELECT id FROM prod.pbi.orders") in q'
        i = self.info(m)
        assert i.native_sql == "SELECT id FROM prod.pbi.orders"
        assert i.source_ref is None

    def test_native_query_escaped_quotes(self):
        m = 'let q = Value.NativeQuery(src, "SELECT ""col"" FROM t") in q'
        i = self.info(m)
        assert i.native_sql == 'SELECT "col" FROM t'

    def test_native_query_case_insensitive(self):
        m = 'let q = value.nativequery(src, "SELECT 1") in q'
        i = self.info(m)
        assert i.native_sql == "SELECT 1"

    def test_no_native_query_returns_none(self):
        m = 'let Source = Databricks.Catalogs("host"), nav = Source{[Name="t"]}[Data] in nav'
        i = self.info(m)
        assert i.native_sql is None

    # ------------------------------------------------------------------
    # filter_sql extraction
    # ------------------------------------------------------------------

    def test_select_rows_equality_filter(self):
        m = """
        let
            Source = Databricks.Catalogs("host", "443", [Catalog="prod"]),
            db = Source{[Name="pbi"]}[Data],
            tbl = db{[Name="orders"]}[Data],
            filtered = Table.SelectRows(tbl, each [status] = "Active")
        in filtered
        """
        i = self.info(m)
        assert i.filter_sql is not None
        assert "status" in i.filter_sql.lower()
        assert "Active" in i.filter_sql

    def test_select_rows_numeric_comparison(self):
        m = 'let f = Table.SelectRows(S, each [Amount] > 1000)\nin f'
        i = self.info(m)
        assert i.filter_sql == "Amount > 1000"

    def test_select_rows_compound_and(self):
        m = 'let f = Table.SelectRows(S, each [Region] = "West" and [Year] = 2024)\nin f'
        i = self.info(m)
        assert i.filter_sql is not None
        assert "AND" in i.filter_sql
        assert "Region" in i.filter_sql

    def test_select_rows_complex_predicate_returns_none(self):
        m = 'let f = Table.SelectRows(S, each List.Contains({"A","B"}, [Col]))\nin f'
        i = self.info(m)
        assert i.filter_sql is None

    def test_no_select_rows_filter_is_none(self):
        m = 'let Source = SomeConnector(), tbl = Source{[Name="sales"]}[Data] in tbl'
        i = self.info(m)
        assert i.filter_sql is None

    # ------------------------------------------------------------------
    # Error resilience
    # ------------------------------------------------------------------

    def test_invalid_m_returns_empty_info(self):
        """Any parse error must return an empty MSourceInfo, never raise."""
        from powermglot import MSourceInfo
        i = self.info("this is not valid M syntax !!@@##")
        assert isinstance(i, MSourceInfo)
        assert i.source_ref is None
        assert i.native_sql is None
        assert i.filter_sql is None

    def test_non_let_expression_returns_empty_info(self):
        i = self.info('"just a string"')
        assert i.source_ref is None

    def test_combined_source_and_filter(self):
        m = """
        let
            Source = Databricks.Catalogs("host", "443", [Catalog="prod"]),
            db = Source{[Name="pbi"]}[Data],
            tbl = db{[Name="orders"]}[Data],
            filtered = Table.SelectRows(tbl, each [year] >= 2023)
        in filtered
        """
        i = self.info(m)
        assert i.source_ref == "prod.pbi.orders"
        assert i.filter_sql is not None
        assert "2023" in i.filter_sql
        assert i.native_sql is None
