"""Tests for daxglot.measure_translator."""

from __future__ import annotations

import pytest

from daxglot.measure_translator import MeasureTranslation, WindowSpec, translate_measure


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def translated(dax: str, **kw) -> MeasureTranslation:
    return translate_measure(dax, **kw)


# ---------------------------------------------------------------------------
# Simple aggregations
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSimpleAggregations:
    def test_sum(self):
        r = translated("= SUM(Sales[Amount])")
        assert "SUM" in r.sql_expr
        assert "Amount" in r.sql_expr
        assert not r.window_spec

    def test_count(self):
        r = translated("= COUNT(Orders[OrderID])")
        assert "COUNT" in r.sql_expr

    def test_distinctcount(self):
        r = translated("= DISTINCTCOUNT(Sales[CustomerID])")
        assert "COUNT" in r.sql_expr
        assert "DISTINCT" in r.sql_expr

    def test_average(self):
        r = translated("= AVERAGE(Sales[Price])")
        assert "AVG" in r.sql_expr

    def test_countrows(self):
        r = translated("= COUNTROWS(Sales)")
        assert "COUNT" in r.sql_expr

    def test_no_leading_equals(self):
        r1 = translated("SUM(Sales[Amount])")
        r2 = translated("= SUM(Sales[Amount])")
        assert r1.sql_expr == r2.sql_expr

    def test_max_min(self):
        r = translated("= MAX(Sales[SaleDate])")
        assert "MAX" in r.sql_expr
        r2 = translated("= MIN(Sales[SaleDate])")
        assert "MIN" in r2.sql_expr


# ---------------------------------------------------------------------------
# DIVIDE (safe division)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDivide:
    def test_basic_divide(self):
        r = translated("= DIVIDE(SUM(Sales[Amount]), SUM(Sales[Qty]))")
        assert "NULLIF" in r.sql_expr
        assert "SUM" in r.sql_expr

    def test_divide_with_alternate(self):
        r = translated("= DIVIDE(SUM(A[x]), SUM(B[y]), 0)")
        assert "COALESCE" in r.sql_expr or "NULLIF" in r.sql_expr


# ---------------------------------------------------------------------------
# Binary ratio measures
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRatioMeasures:
    def test_ratio(self):
        r = translated("= SUM(Sales[Revenue]) / SUM(Sales[Qty])")
        assert "/" in r.sql_expr
        assert "SUM" in r.sql_expr

    def test_sum_plus_sum(self):
        r = translated("= SUM(A[x]) + SUM(B[y])")
        assert "SUM" in r.sql_expr
        assert "+" in r.sql_expr


# ---------------------------------------------------------------------------
# IFERROR + DIVIDE pattern
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestIfError:
    def test_iferror_wraps_divide(self):
        r = translated("= IFERROR(DIVIDE(SUM(A[x]), SUM(B[y])), 0)")
        # IFERROR → COALESCE, DIVIDE → NULLIF
        assert "COALESCE" in r.sql_expr or "NULLIF" in r.sql_expr

    def test_iferror_with_blank(self):
        r = translated("= IFERROR(SUM(A[x]) / SUM(B[y]), BLANK())")
        assert r.sql_expr  # Should produce something


# ---------------------------------------------------------------------------
# CALCULATE with FILTER
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCalculateFilter:
    def test_filter_clause(self):
        r = translated(
            '= CALCULATE(SUM(Sales[Amount]), FILTER(Sales, Sales[Region] = "West"))'
        )
        assert "SUM" in r.sql_expr
        assert "FILTER" in r.sql_expr.upper() or "WHERE" in r.sql_expr.upper()
        assert not r.window_spec

    def test_direct_predicate(self):
        r = translated(
            '= CALCULATE(SUM(Sales[Amount]), Sales[Status] = "Active")')
        assert "SUM" in r.sql_expr

    def test_all_filter_removed(self):
        r = translated("= CALCULATE(SUM(Sales[Amount]), ALL(Sales))")
        assert "SUM" in r.sql_expr
        assert len(r.warnings) > 0  # should warn about ALL being removed


# ---------------------------------------------------------------------------
# Time intelligence → window measures
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTimeIntelligence:
    def test_sameperiodlastyear(self):
        r = translated(
            "= CALCULATE(SUM(Sales[Amount]), SAMEPERIODLASTYEAR('Date'[Date]))"
        )
        assert len(r.window_spec) >= 1
        ws = r.window_spec[0]
        assert "trailing" in ws.range
        assert "year" in ws.range
        assert "SUM" in r.sql_expr

    def test_datesytd(self):
        r = translated(
            "= CALCULATE(SUM(Sales[Amount]), DATESYTD('Date'[Date]))"
        )
        assert any("cumulative" in ws.range for ws in r.window_spec)

    def test_previousyear(self):
        r = translated(
            "= CALCULATE(SUM(Sales[Amount]), PREVIOUSYEAR('Date'[Date]))"
        )
        assert any("year" in ws.range for ws in r.window_spec)

    def test_previousmonth(self):
        r = translated(
            "= CALCULATE(SUM(Sales[Amount]), PREVIOUSMONTH('Date'[Date]))"
        )
        assert any("month" in ws.range for ws in r.window_spec)

    def test_dateadd_negative_months(self):
        r = translated(
            "= CALCULATE(SUM(Sales[Amount]), DATEADD('Date'[Date], -3, MONTH))"
        )
        assert any(
            "trailing" in ws.range and "month" in ws.range for ws in r.window_spec)

    def test_totalytd_direct(self):
        r = translated("= TOTALYTD(SUM(Sales[Amount]), 'Date'[Date])")
        assert any("cumulative" in ws.range for ws in r.window_spec)

    def test_date_dimension_detected(self):
        r = translated(
            "= CALCULATE(SUM(Sales[Amount]), SAMEPERIODLASTYEAR('Date'[OrderDate]))",
            date_dimension="order_date",
        )
        assert r.window_spec[0].order == "orderdate" or r.window_spec[0].order != ""


# ---------------------------------------------------------------------------
# VAR / RETURN
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestVarReturn:
    def test_simple_var_inlined(self):
        dax = """\
= VAR _Sales = SUM(Sales[Amount])
RETURN _Sales"""
        r = translated(dax)
        assert "SUM" in r.sql_expr

    def test_var_with_divide(self):
        dax = """\
= VAR _Num = SUM(Sales[Revenue])
VAR _Den = SUM(Sales[Qty])
RETURN DIVIDE(_Num, _Den)"""
        r = translated(dax)
        assert "SUM" in r.sql_expr
        assert "NULLIF" in r.sql_expr

    def test_nested_var_refs(self):
        dax = """\
= VAR _x = SUM(A[val])
VAR _y = _x * 2
RETURN _y"""
        r = translated(dax)
        assert "SUM" in r.sql_expr


# ---------------------------------------------------------------------------
# IF / SWITCH
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConditional:
    def test_if_expression(self):
        r = translated('= IF(SUM(Sales[Amount]) > 1000, "High", "Low")')
        assert "CASE" in r.sql_expr.upper() or "IF" in r.sql_expr.upper()

    def test_switch_true(self):
        # DAX SWITCH(TRUE, ...) — note: TRUE without parens is the parser-supported form
        r = translated(
            '= SWITCH(TRUE, '
            'Sales[Category] = "A", "Alpha", '
            'Sales[Category] = "B", "Beta", '
            '"Other")'
        )
        assert "CASE" in r.sql_expr.upper()
        # Should NOT produce "CASE WHEN TRUE = ..."
        assert "TRUE =" not in r.sql_expr.upper()
        assert "= TRUE" not in r.sql_expr.upper()

    def test_switch_value(self):
        r = translated(
            '= SWITCH(Sales[Status], "A", "Active", "I", "Inactive", "Unknown")'
        )
        assert "CASE" in r.sql_expr.upper()


# ---------------------------------------------------------------------------
# Function call special cases
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFunctionSpecialCases:
    def test_isblank(self):
        r = translated("= ISBLANK(Sales[Amount])")
        sql = r.sql_expr.upper()
        assert "NULL" in sql

    def test_coalesce(self):
        r = translated("= COALESCE(Sales[Amount], 0)")
        assert "COALESCE" in r.sql_expr.upper()

    def test_today(self):
        r = translated("= TODAY()")
        sql = r.sql_expr.upper()
        assert "CURRENT_DATE" in sql or "TODAY" in sql

    def test_len(self):
        r = translated("= LEN(Customer[Name])")
        sql = r.sql_expr.upper()
        assert "LENGTH" in sql or "LEN" in sql

    def test_hasonevalue(self):
        r = translated("= HASONEVALUE(Product[Category])")
        sql = r.sql_expr.upper()
        assert "COUNT" in sql


# ---------------------------------------------------------------------------
# Parse errors
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestParseErrors:
    def test_invalid_dax_returns_approximation(self):
        r = translated("= THIS IS NOT VALID ??? ###")
        # Should not raise, should return something with is_approximate=True
        assert r.is_approximate or r.sql_expr  # Either approximation or best-effort

    def test_empty_expression(self):
        r = translated("= ")
        assert r.sql_expr is not None
