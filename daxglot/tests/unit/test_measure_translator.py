"""Tests for daxglot.measure_translator."""

from __future__ import annotations

import pytest

from daxglot.measure_translator import (
    ByteFormatSpec,
    CurrencyFormatSpec,
    DecimalPlacesSpec,
    MeasureTranslation,
    NumberFormatSpec,
    PercentageFormatSpec,
    WindowSpec,
    format_spec_from_pbi_string,
    format_spec_to_dict,
    translate_measure,
)


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

    def test_datesinperiod_trailing(self):
        r = translated(
            "= CALCULATE(SUM(Sales[Amount]), DATESINPERIOD('Date'[Date], LASTDATE('Date'[Date]), -7, DAY))"
        )
        assert len(r.window_spec) == 1
        assert r.window_spec[0].range == "trailing 7 day"

    def test_datesinperiod_leading(self):
        r = translated(
            "= CALCULATE(SUM(Sales[Amount]), DATESINPERIOD('Date'[Date], TODAY(), 3, MONTH))"
        )
        assert len(r.window_spec) == 1
        assert r.window_spec[0].range == "leading 3 month"

    def test_datesbetween_startofyear(self):
        r = translated(
            "= CALCULATE(SUM(Sales[Amount]), DATESBETWEEN('Date'[Date], STARTOFYEAR('Date'[Date]), LASTDATE('Date'[Date])))"
        )
        assert any("cumulative" in ws.range for ws in r.window_spec)
        assert any("current" in ws.range for ws in r.window_spec)

    def test_datesbetween_startofmonth(self):
        r = translated(
            "= CALCULATE(SUM(Sales[Amount]), DATESBETWEEN('Date'[Date], STARTOFMONTH('Date'[Date]), LASTDATE('Date'[Date])))"
        )
        assert any("cumulative" in ws.range for ws in r.window_spec)

    def test_datesbetween_unrecognised_warns(self):
        r = translated(
            "= CALCULATE(SUM(Sales[Amount]), DATESBETWEEN('Date'[Date], DATE(2024,1,1), DATE(2024,12,31)))"
        )
        assert len(r.warnings) > 0
        assert any("DATESBETWEEN" in w for w in r.warnings)

    def test_datesytd_fiscal_year_end_warning(self):
        r = translated(
            "= CALCULATE(SUM(Sales[Amount]), DATESYTD('Date'[Date], \"3/31\"))"
        )
        assert any("cumulative" in ws.range for ws in r.window_spec)
        assert any("fiscal year-end" in w for w in r.warnings)

    def test_totalytd_fiscal_year_end_warning(self):
        r = translated(
            "= TOTALYTD(SUM(Sales[Amount]), 'Date'[Date], \"6/30\")")
        assert any("cumulative" in ws.range for ws in r.window_spec)
        assert any("fiscal year-end" in w for w in r.warnings)

    def test_openingbalanceyear_semiadditive_first(self):
        r = translated(
            "= OPENINGBALANCEYEAR(SUM(Inventory[Stock]), 'Date'[Date])")
        assert len(r.window_spec) >= 1
        assert all(ws.semiadditive == "first" for ws in r.window_spec)
        assert any("cumulative" in ws.range for ws in r.window_spec)

    def test_closingbalanceyear_semiadditive_last(self):
        r = translated(
            "= CLOSINGBALANCEYEAR(SUM(Inventory[Stock]), 'Date'[Date])")
        assert len(r.window_spec) >= 1
        assert all(ws.semiadditive == "last" for ws in r.window_spec)

    def test_openingbalancemonth_semiadditive_first(self):
        r = translated(
            "= OPENINGBALANCEMONTH(SUM(Inventory[Stock]), 'Date'[Date])")
        assert len(r.window_spec) >= 1
        assert all(ws.semiadditive == "first" for ws in r.window_spec)

    def test_period_dimensions_used_for_ytd(self):
        r = translated(
            "= CALCULATE(SUM(Sales[Amount]), DATESYTD('Date'[Date]))",
            period_dimensions={"year": "fiscal_year"},
        )
        year_specs = [ws for ws in r.window_spec if ws.range == "current"]
        assert len(year_specs) == 1
        assert year_specs[0].order == "fiscal_year"
        # No heuristic-guess warning since the period was explicitly provided
        assert not any("guessed" in w for w in r.warnings)

    def test_period_dimensions_missing_emits_warning(self):
        r = translated(
            "= CALCULATE(SUM(Sales[Amount]), DATESYTD('Date'[Date]))",
            period_dimensions={},  # empty — no year dim registered
        )
        assert any("guessed" in w for w in r.warnings)

    def test_totalytd_with_period_dimensions(self):
        r = translated(
            "= TOTALYTD(SUM(Sales[Amount]), 'Date'[Date])",
            period_dimensions={"year": "order_year"},
        )
        year_specs = [ws for ws in r.window_spec if ws.range == "current"]
        assert year_specs[0].order == "order_year"


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


# ---------------------------------------------------------------------------
# Semantic metadata: synonyms
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSynonyms:
    def test_synonyms_propagated(self):
        r = translated("= SUM(Sales[Amount])", synonyms=[
                       "revenue", "total sales"])
        assert r.synonyms == ["revenue", "total sales"]

    def test_no_synonyms_by_default(self):
        r = translated("= SUM(Sales[Amount])")
        assert r.synonyms == []

    def test_synonyms_with_time_intelligence(self):
        r = translated(
            "= CALCULATE(SUM(Sales[Amount]), SAMEPERIODLASTYEAR('Date'[Date]))",
            synonyms=["last year sales"],
        )
        assert "last year sales" in r.synonyms
        assert r.window_spec  # window should still be set


# ---------------------------------------------------------------------------
# Semantic metadata: format_spec from explicit spec
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExplicitFormatSpec:
    def test_explicit_number_format(self):
        spec = NumberFormatSpec(
            decimal_places=DecimalPlacesSpec(type="exact", places=2),
        )
        r = translated("= SUM(Sales[Amount])", format_spec=spec)
        assert isinstance(r.format_spec, NumberFormatSpec)
        assert r.format_spec.decimal_places.places == 2

    def test_explicit_currency_format(self):
        spec = CurrencyFormatSpec(currency_code="EUR")
        r = translated("= SUM(Sales[Revenue])", format_spec=spec)
        assert isinstance(r.format_spec, CurrencyFormatSpec)
        assert r.format_spec.currency_code == "EUR"

    def test_explicit_percentage_format(self):
        spec = PercentageFormatSpec(
            decimal_places=DecimalPlacesSpec(type="exact", places=1),
        )
        r = translated("= DIVIDE(SUM(A[x]), SUM(B[y]))", format_spec=spec)
        assert isinstance(r.format_spec, PercentageFormatSpec)

    def test_explicit_byte_format(self):
        spec = ByteFormatSpec(
            decimal_places=DecimalPlacesSpec(type="max", places=2),
        )
        r = translated("= SUM(Storage[Bytes])", format_spec=spec)
        assert isinstance(r.format_spec, ByteFormatSpec)

    def test_explicit_spec_takes_precedence_over_format_string(self):
        spec = CurrencyFormatSpec(currency_code="GBP")
        r = translated(
            "= SUM(Sales[Amount])",
            format_spec=spec,
            format_string="0.00%",  # should be ignored
        )
        assert isinstance(r.format_spec, CurrencyFormatSpec)
        assert r.format_spec.currency_code == "GBP"


# ---------------------------------------------------------------------------
# Semantic metadata: format_spec from PBI format string
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFormatSpecFromPbiString:
    def test_currency_named(self):
        spec = format_spec_from_pbi_string("Currency")
        assert isinstance(spec, CurrencyFormatSpec)
        assert spec.currency_code == "USD"
        assert spec.decimal_places.places == 2

    def test_currency_dollar_symbol(self):
        spec = format_spec_from_pbi_string("$#,##0.00")
        assert isinstance(spec, CurrencyFormatSpec)
        assert spec.currency_code == "USD"
        assert spec.decimal_places.places == 2

    def test_currency_euro_symbol(self):
        spec = format_spec_from_pbi_string("€#,##0.00")
        assert isinstance(spec, CurrencyFormatSpec)
        assert spec.currency_code == "EUR"

    def test_currency_gbp_symbol(self):
        spec = format_spec_from_pbi_string("£#,##0")
        assert isinstance(spec, CurrencyFormatSpec)
        assert spec.currency_code == "GBP"
        assert spec.decimal_places.places == 0

    def test_percentage_named(self):
        spec = format_spec_from_pbi_string("Percent")
        assert isinstance(spec, PercentageFormatSpec)

    def test_percentage_format_two_decimals(self):
        spec = format_spec_from_pbi_string("0.00%")
        assert isinstance(spec, PercentageFormatSpec)
        assert spec.decimal_places.places == 2

    def test_percentage_format_zero_decimals(self):
        spec = format_spec_from_pbi_string("0%")
        assert isinstance(spec, PercentageFormatSpec)
        assert spec.decimal_places.places == 0

    def test_number_hash_format(self):
        spec = format_spec_from_pbi_string("#,##0.00")
        assert isinstance(spec, NumberFormatSpec)
        assert spec.decimal_places.places == 2

    def test_number_named_fixed(self):
        spec = format_spec_from_pbi_string("Fixed")
        assert isinstance(spec, NumberFormatSpec)

    def test_number_no_group_separator(self):
        spec = format_spec_from_pbi_string("0.00")
        assert isinstance(spec, NumberFormatSpec)
        assert spec.hide_group_separator is True

    def test_unrecognised_returns_none(self):
        spec = format_spec_from_pbi_string("General")
        assert spec is None

    def test_empty_returns_none(self):
        assert format_spec_from_pbi_string("") is None


# ---------------------------------------------------------------------------
# Semantic metadata: format_spec from format_string parameter
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFormatStringParameter:
    def test_currency_format_string(self):
        r = translated("= SUM(Sales[Amount])", format_string="Currency")
        assert isinstance(r.format_spec, CurrencyFormatSpec)
        assert r.format_spec.currency_code == "USD"

    def test_percentage_format_string(self):
        r = translated(
            "= DIVIDE(SUM(A[x]), SUM(B[total]))", format_string="0.00%")
        assert isinstance(r.format_spec, PercentageFormatSpec)
        assert r.format_spec.decimal_places.places == 2

    def test_number_format_string(self):
        r = translated("= SUM(Sales[Qty])", format_string="#,##0")
        assert isinstance(r.format_spec, NumberFormatSpec)


# ---------------------------------------------------------------------------
# Semantic metadata: format_spec inferred from DAX FORMAT() call
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDaxFormatInference:
    def test_format_percent(self):
        r = translated('= FORMAT(DIVIDE(SUM(A[x]), SUM(B[y])), "0.00%")')
        assert isinstance(r.format_spec, PercentageFormatSpec)
        assert r.format_spec.decimal_places.places == 2

    def test_format_currency_named(self):
        r = translated('= FORMAT(SUM(Sales[Revenue]), "Currency")')
        assert isinstance(r.format_spec, CurrencyFormatSpec)

    def test_format_currency_symbol(self):
        r = translated('= FORMAT(SUM(Sales[Revenue]), "$#,##0.00")')
        assert isinstance(r.format_spec, CurrencyFormatSpec)
        assert r.format_spec.currency_code == "USD"

    def test_no_format_call_no_spec(self):
        r = translated("= SUM(Sales[Amount])")
        assert r.format_spec is None


# ---------------------------------------------------------------------------
# Semantic metadata: format_spec_to_dict serialisation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFormatSpecToDict:
    def test_number_dict(self):
        spec = NumberFormatSpec(
            decimal_places=DecimalPlacesSpec(type="max", places=2),
            hide_group_separator=False,
            abbreviation="compact",
        )
        d = format_spec_to_dict(spec)
        assert d["type"] == "number"
        assert d["decimal_places"] == {"type": "max", "places": 2}
        assert "hide_group_separator" not in d  # False is omitted
        assert d["abbreviation"] == "compact"

    def test_currency_dict(self):
        spec = CurrencyFormatSpec(
            currency_code="USD",
            decimal_places=DecimalPlacesSpec(type="exact", places=2),
            hide_group_separator=False,
        )
        d = format_spec_to_dict(spec)
        assert d["type"] == "currency"
        assert d["currency_code"] == "USD"
        assert d["decimal_places"]["places"] == 2

    def test_percentage_dict(self):
        spec = PercentageFormatSpec(
            decimal_places=DecimalPlacesSpec(type="all"),
            hide_group_separator=True,
        )
        d = format_spec_to_dict(spec)
        assert d["type"] == "percentage"
        assert d["decimal_places"] == {"type": "all"}
        assert d["hide_group_separator"] is True

    def test_byte_dict(self):
        spec = ByteFormatSpec(
            decimal_places=DecimalPlacesSpec(type="max", places=2),
        )
        d = format_spec_to_dict(spec)
        assert d["type"] == "byte"
        assert d["decimal_places"]["places"] == 2

    def test_no_decimal_places(self):
        spec = CurrencyFormatSpec(currency_code="JPY")
        d = format_spec_to_dict(spec)
        assert "decimal_places" not in d
