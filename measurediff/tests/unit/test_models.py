"""Unit tests for measurediff.models."""

from __future__ import annotations

import pytest

from measurediff.models import (
    DimensionDefinition,
    JoinDefinition,
    LineageColumn,
    MeasureDefinition,
    MetricViewDefinition,
    WindowSpec,
)


class TestLineageColumn:
    def test_leaf_node(self):
        node = LineageColumn(table="cat.sch.tbl", column="price", type="TABLE")
        assert node.table == "cat.sch.tbl"
        assert node.column == "price"
        assert node.type == "TABLE"
        assert node.upstream == ()

    def test_recursive_tree(self):
        leaf = LineageColumn(table="cat.raw.orders",
                             column="price", type="TABLE")
        mid = LineageColumn(
            table="cat.dw.fact_orders",
            column="revenue",
            type="VIEW",
            upstream=(leaf,),
        )
        root = LineageColumn(
            table="cat.metrics.sales",
            column="total_revenue",
            type="METRIC_VIEW",
            upstream=(mid,),
        )
        assert root.upstream[0] is mid
        assert root.upstream[0].upstream[0] is leaf
        assert leaf.upstream == ()

    def test_frozen_immutable(self):
        node = LineageColumn(table="a.b.c", column="x", type="TABLE")
        with pytest.raises((AttributeError, TypeError)):
            node.table = "d.e.f"  # type: ignore[misc]

    def test_equality(self):
        a = LineageColumn(table="a.b.c", column="x", type="TABLE")
        b = LineageColumn(table="a.b.c", column="x", type="TABLE")
        assert a == b


class TestMeasureDefinition:
    def test_defaults(self):
        m = MeasureDefinition(name="total_revenue", expr="SUM(o_totalprice)")
        assert m.comment is None
        assert m.display_name is None
        assert m.window == ()
        assert m.lineage == ()
        assert m.referenced_measures == ()

    def test_with_lineage(self):
        leaf = LineageColumn(table="cat.raw.tbl", column="col", type="TABLE")
        m = MeasureDefinition(
            name="rev",
            expr="SUM(col)",
            lineage=(leaf,),
        )
        assert len(m.lineage) == 1
        assert m.lineage[0] is leaf

    def test_with_window(self):
        w = WindowSpec(order="date", range="trailing 7 day",
                       semiadditive="last")
        m = MeasureDefinition(
            name="t7d", expr="COUNT(DISTINCT id)", window=(w,))
        assert m.window[0].order == "date"
        assert m.window[0].semiadditive == "last"

    def test_frozen(self):
        m = MeasureDefinition(name="x", expr="COUNT(1)")
        with pytest.raises((AttributeError, TypeError)):
            m.name = "y"  # type: ignore[misc]


class TestMetricViewDefinition:
    def test_minimal(self):
        mv = MetricViewDefinition(
            full_name="cat.sch.view", source="cat.sch.tbl")
        assert mv.version == "1.1"
        assert mv.comment is None
        assert mv.joins == ()
        assert mv.dimensions == ()
        assert mv.measures == ()

    def test_roundtrip_fields(self):
        dim = DimensionDefinition(name="order_date", expr="o_orderdate")
        measure = MeasureDefinition(name="revenue", expr="SUM(price)")
        join = JoinDefinition(
            name="customer", source="cat.sch.customers", on="source.cid = customer.id")
        mv = MetricViewDefinition(
            full_name="cat.sch.sales",
            source="cat.sch.fact_orders",
            comment="Test view",
            filter="o_status = 'O'",
            joins=(join,),
            dimensions=(dim,),
            measures=(measure,),
        )
        assert mv.joins[0].name == "customer"
        assert mv.dimensions[0].expr == "o_orderdate"
        assert mv.measures[0].expr == "SUM(price)"
