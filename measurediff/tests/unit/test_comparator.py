"""Unit tests for measurediff.comparator."""

from __future__ import annotations

import pytest

from measurediff.comparator import (
    LeafSource,
    MeasureComparison,
    _collect_intermediates,
    _collect_leaves,
    _compare_expr,
    _compare_lineage,
    _compare_window,
    _normalize_expr,
    compare_measures,
)
from measurediff.models import LineageColumn, MeasureDefinition, WindowSpec


# ---------------------------------------------------------------------------
# Fixtures — Monthly_Sales (bravo) and MonthSales (charlie)
# ---------------------------------------------------------------------------

MONTHLY_SALES_LINEAGE = (
    LineageColumn(
        table="playground.bravo.sales",
        column="total",
        type="UNKNOWN",
        upstream=(
            LineageColumn(
                table="playground.alpha.sales",
                column="total",
                type="TABLE",
                upstream=(),
            ),
        ),
    ),
)

MONTH_SALES_LINEAGE = (
    LineageColumn(
        table="playground.alpha.sales",
        column="total",
        type="UNKNOWN",
        upstream=(),
    ),
)

MONTHLY_SALES = MeasureDefinition(
    name="Monthly_Sales",
    expr="SUM(source.total)",
    display_name="Monthly Sales",
    window=(WindowSpec(order="date", range="trailing 1 months", semiadditive="last"),),
    lineage=MONTHLY_SALES_LINEAGE,
)

MONTH_SALES = MeasureDefinition(
    name="MonthSales",
    expr="SUM(source.total)",
    display_name="Month Sales",
    window=(WindowSpec(order="date", range="trailing 30 days", semiadditive="last"),),
    lineage=MONTH_SALES_LINEAGE,
)


# ---------------------------------------------------------------------------
# _normalize_expr
# ---------------------------------------------------------------------------


class TestNormalizeExpr:
    def test_strips_table_qualifier(self):
        assert _normalize_expr("SUM(source.total)") == "SUM(total)"

    def test_preserves_function(self):
        assert _normalize_expr("COUNT(*)") == "COUNT(*)"

    def test_count_one(self):
        assert _normalize_expr("COUNT(1)") == "COUNT(1)"

    def test_no_qualifier_unchanged(self):
        assert _normalize_expr("SUM(total)") == "SUM(total)"

    def test_multiple_qualifiers(self):
        result = _normalize_expr("a.x + b.y")
        assert "a." not in result and "b." not in result

    def test_case_preserved_on_function(self):
        result = _normalize_expr("sum(source.total)")
        assert "total" in result.lower()

    def test_fallback_on_unparseable(self):
        # Should not raise; returns original stripped
        result = _normalize_expr("THIS IS NOT SQL @@!!")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _collect_leaves
# ---------------------------------------------------------------------------


class TestCollectLeaves:
    def test_single_leaf(self):
        lineage = (LineageColumn(table="a.b.c",
                   column="x", type="TABLE", upstream=()),)
        leaves = _collect_leaves(lineage)
        assert leaves == frozenset({LeafSource("a.b.c", "x")})

    def test_intermediate_skipped(self):
        lineage = MONTHLY_SALES_LINEAGE
        leaves = _collect_leaves(lineage)
        # Only playground.alpha.sales is a leaf
        assert leaves == frozenset(
            {LeafSource("playground.alpha.sales", "total")})

    def test_direct_leaf(self):
        lineage = MONTH_SALES_LINEAGE
        leaves = _collect_leaves(lineage)
        assert leaves == frozenset(
            {LeafSource("playground.alpha.sales", "total")})

    def test_empty_lineage(self):
        assert _collect_leaves(()) == frozenset()

    def test_deep_tree(self):
        deep = LineageColumn(
            table="a.b.c",
            column="col",
            type="TABLE",
            upstream=(
                LineageColumn(
                    table="a.b.d",
                    column="col",
                    type="TABLE",
                    upstream=(
                        LineageColumn(table="a.b.e", column="col",
                                      type="TABLE", upstream=()),
                    ),
                ),
            ),
        )
        leaves = _collect_leaves((deep,))
        assert leaves == frozenset({LeafSource("a.b.e", "col")})


# ---------------------------------------------------------------------------
# _collect_intermediates
# ---------------------------------------------------------------------------


class TestCollectIntermediates:
    def test_no_intermediates_for_leaf(self):
        lineage = (LineageColumn(table="a.b.c",
                   column="x", type="TABLE", upstream=()),)
        assert _collect_intermediates(lineage) == frozenset()

    def test_finds_intermediate(self):
        intermediates = _collect_intermediates(MONTHLY_SALES_LINEAGE)
        assert LeafSource("playground.bravo.sales", "total") in intermediates

    def test_direct_measure_has_no_intermediates(self):
        intermediates = _collect_intermediates(MONTH_SALES_LINEAGE)
        assert intermediates == frozenset()


# ---------------------------------------------------------------------------
# _compare_expr
# ---------------------------------------------------------------------------


class TestCompareExpr:
    def test_same_normalized(self):
        cmp = _compare_expr("SUM(source.total)", "SUM(source.total)")
        assert cmp.same is True

    def test_different_qualifier_same_result(self):
        cmp = _compare_expr("SUM(source.total)", "SUM(s.total)")
        assert cmp.same is True

    def test_different_function(self):
        cmp = _compare_expr("SUM(total)", "COUNT(*)")
        assert cmp.same is False

    def test_normalized_stored(self):
        cmp = _compare_expr("SUM(source.total)", "SUM(source.total)")
        assert cmp.normalized_a == "SUM(total)"
        assert cmp.normalized_b == "SUM(total)"

    def test_raw_preserved(self):
        cmp = _compare_expr("SUM(source.total)", "SUM(source.total)")
        assert cmp.raw_a == "SUM(source.total)"
        assert cmp.raw_b == "SUM(source.total)"


# ---------------------------------------------------------------------------
# _compare_window
# ---------------------------------------------------------------------------


class TestCompareWindow:
    def test_identical_window(self):
        ws = (WindowSpec(order="date", range="trailing 1 months", semiadditive="last"),)
        cmp = _compare_window(ws, ws)
        assert cmp.same is True
        assert len(cmp.field_diffs) == 0

    def test_range_differs(self):
        wa = (WindowSpec(order="date", range="trailing 1 months", semiadditive="last"),)
        wb = (WindowSpec(order="date", range="trailing 30 days", semiadditive="last"),)
        cmp = _compare_window(wa, wb)
        assert cmp.same is False
        diff_fields = {d.field for d in cmp.field_diffs}
        assert "range" in diff_fields
        assert "order" not in diff_fields
        assert "semiadditive" not in diff_fields

    def test_both_empty(self):
        cmp = _compare_window((), ())
        assert cmp.same is True

    def test_one_empty(self):
        ws = (WindowSpec(order="date", range="trailing 1 months"),)
        cmp = _compare_window(ws, ())
        assert cmp.same is False
        assert len(cmp.field_diffs) > 0


# ---------------------------------------------------------------------------
# _compare_lineage
# ---------------------------------------------------------------------------


class TestCompareLineage:
    def test_same_root_different_path(self):
        """Monthly_Sales and MonthSales share the same leaf source."""
        cmp = _compare_lineage(MONTHLY_SALES_LINEAGE, MONTH_SALES_LINEAGE)
        assert cmp.leaves_same is True
        assert LeafSource("playground.alpha.sales",
                          "total") in cmp.shared_leaves
        assert len(cmp.only_in_a) == 0
        assert len(cmp.only_in_b) == 0

    def test_extra_hops_in_a(self):
        """Monthly_Sales has an intermediate hop (bravo.sales) that MonthSales skips."""
        cmp = _compare_lineage(MONTHLY_SALES_LINEAGE, MONTH_SALES_LINEAGE)
        assert cmp.has_extra_hops_a is True
        assert cmp.has_extra_hops_b is False

    def test_both_empty(self):
        cmp = _compare_lineage((), ())
        assert cmp.leaves_same is True
        assert cmp.has_extra_hops_a is False
        assert cmp.has_extra_hops_b is False

    def test_disjoint_leaves(self):
        a = (LineageColumn(table="t.s.a", column="x", type="TABLE", upstream=()),)
        b = (LineageColumn(table="t.s.b", column="x", type="TABLE", upstream=()),)
        cmp = _compare_lineage(a, b)
        assert cmp.leaves_same is False
        assert len(cmp.shared_leaves) == 0
        assert len(cmp.only_in_a) == 1
        assert len(cmp.only_in_b) == 1


# ---------------------------------------------------------------------------
# compare_measures — integration
# ---------------------------------------------------------------------------


class TestCompareMeasures:
    def test_monthly_vs_monthsales(self):
        """Monthly_Sales vs MonthSales: same expr + leaf, window range differs."""
        cmp: MeasureComparison = compare_measures(
            "playground.bravo.country_sales",
            MONTHLY_SALES,
            "playground.charlie.alphasales",
            MONTH_SALES,
        )
        # Expression is same (same normalized)
        assert cmp.expr.same is True
        # Window differs (range field)
        assert cmp.window.same is False
        # Lineage leaves are the same
        assert cmp.lineage.leaves_same is True
        # Score: 0.5*1.0 + 0.2*window_score + 0.3*1.0
        # window_score: 2/3 fields match (order and semiadditive match, range differs)
        # = 0.5 + 0.2*(2/3) + 0.3 = 0.5 + 0.1333 + 0.3 = 0.9333
        assert cmp.score > 0.6
        assert cmp.label in ("Identical", "Similar")
        assert cmp.label == "Similar"  # score ~0.93, below 0.98

    def test_identical_measures(self):
        cmp = compare_measures("v.a", MONTHLY_SALES, "v.b", MONTHLY_SALES)
        assert cmp.score == 1.0
        assert cmp.label == "Identical"

    def test_completely_different(self):
        m_a = MeasureDefinition(
            name="rev",
            expr="SUM(price)",
            lineage=(LineageColumn(table="a.b.orders",
                     column="price", type="TABLE", upstream=()),),
        )
        m_b = MeasureDefinition(
            name="cnt",
            expr="COUNT(*)",
            lineage=(LineageColumn(table="c.d.products",
                     column="id", type="TABLE", upstream=()),),
        )
        cmp = compare_measures("v.a", m_a, "v.b", m_b)
        assert cmp.score < 0.6
        assert cmp.label == "Different"

    def test_no_lineage_both(self):
        m_a = MeasureDefinition(name="cnt", expr="COUNT(*)")
        m_b = MeasureDefinition(name="cnt", expr="COUNT(*)")
        cmp = compare_measures("v.a", m_a, "v.b", m_b)
        assert cmp.score == 1.0
        assert cmp.label == "Identical"

    def test_names_excluded_from_score(self):
        """Different names should not reduce the score."""
        m_a = MeasureDefinition(name="Monthly_Sales", expr="SUM(total)")
        m_b = MeasureDefinition(name="MonthSales", expr="SUM(total)")
        cmp = compare_measures("v.a", m_a, "v.b", m_b)
        assert cmp.score == 1.0
