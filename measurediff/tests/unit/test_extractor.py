"""Unit tests for measurediff.extractor."""

from __future__ import annotations

import textwrap

import pytest

from measurediff.extractor import (
    extract_column_refs,
    extract_measure_refs,
    extract_yaml_from_ddl,
    is_metric_view,
    parse_metric_view,
)
from measurediff.models import MetricViewDefinition


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SIMPLE_DDL = textwrap.dedent(
    """\
    CREATE OR REPLACE VIEW `cat`.`sch`.`orders_metrics`
    WITH METRICS
    LANGUAGE YAML
    AS
    $$
    version: '1.1'
    comment: Orders metric view
    source: cat.sch.fact_orders
    joins:
    - name: customer
      source: cat.sch.dim_customer
      'on': source.customer_key = customer.customer_key
    dimensions:
    - name: order_date
      expr: o_orderdate
    - name: customer_name
      expr: customer.c_name
      comment: From customer join
    measures:
    - name: total_revenue
      expr: SUM(o_totalprice)
      comment: Gross revenue
    - name: order_count
      expr: COUNT(1)
    - name: avg_order_value
      expr: MEASURE(total_revenue) / MEASURE(order_count)
      display_name: Avg Order Value
    - name: t7d_revenue
      expr: SUM(o_totalprice)
      window:
      - order: order_date
        range: trailing 7 day
        semiadditive: last
    $$
    """
)

_NOT_METRIC_VIEW_DDL = textwrap.dedent(
    """\
    CREATE OR REPLACE VIEW `cat`.`sch`.`some_view` AS
    SELECT * FROM cat.sch.some_table;
    """
)


# ---------------------------------------------------------------------------
# is_metric_view
# ---------------------------------------------------------------------------


class TestIsMetricView:
    def test_true_for_metric_view(self):
        assert is_metric_view(_SIMPLE_DDL) is True

    def test_false_for_plain_view(self):
        assert is_metric_view(_NOT_METRIC_VIEW_DDL) is False

    def test_false_for_empty_string(self):
        assert is_metric_view("") is False

    def test_case_insensitive(self):
        lower_ddl = _SIMPLE_DDL.lower()
        assert is_metric_view(lower_ddl) is True


# ---------------------------------------------------------------------------
# extract_yaml_from_ddl
# ---------------------------------------------------------------------------


class TestExtractYamlFromDdl:
    def test_extracts_yaml_body(self):
        raw = extract_yaml_from_ddl(_SIMPLE_DDL)
        assert raw is not None
        assert "version: '1.1'" in raw
        assert "source: cat.sch.fact_orders" in raw

    def test_returns_none_for_no_delimiters(self):
        assert extract_yaml_from_ddl(_NOT_METRIC_VIEW_DDL) is None

    def test_strips_whitespace(self):
        raw = extract_yaml_from_ddl(_SIMPLE_DDL)
        assert raw is not None
        assert not raw.startswith("\n")
        assert not raw.endswith("\n")


# ---------------------------------------------------------------------------
# parse_metric_view
# ---------------------------------------------------------------------------


class TestParseMetricView:
    def test_parses_full_name(self):
        mv = parse_metric_view("cat.sch.orders_metrics", _SIMPLE_DDL)
        assert mv.full_name == "cat.sch.orders_metrics"

    def test_parses_source(self):
        mv = parse_metric_view("cat.sch.orders_metrics", _SIMPLE_DDL)
        assert mv.source == "cat.sch.fact_orders"

    def test_parses_version(self):
        mv = parse_metric_view("cat.sch.orders_metrics", _SIMPLE_DDL)
        assert mv.version == "1.1"

    def test_parses_comment(self):
        mv = parse_metric_view("cat.sch.orders_metrics", _SIMPLE_DDL)
        assert mv.comment == "Orders metric view"

    def test_parses_joins(self):
        mv = parse_metric_view("cat.sch.orders_metrics", _SIMPLE_DDL)
        assert len(mv.joins) == 1
        j = mv.joins[0]
        assert j.name == "customer"
        assert j.source == "cat.sch.dim_customer"
        assert j.on == "source.customer_key = customer.customer_key"
        assert j.using is None

    def test_parses_dimensions(self):
        mv = parse_metric_view("cat.sch.orders_metrics", _SIMPLE_DDL)
        dim_names = [d.name for d in mv.dimensions]
        assert "order_date" in dim_names
        assert "customer_name" in dim_names

    def test_parses_measures(self):
        mv = parse_metric_view("cat.sch.orders_metrics", _SIMPLE_DDL)
        measure_names = [m.name for m in mv.measures]
        assert "total_revenue" in measure_names
        assert "order_count" in measure_names
        assert "avg_order_value" in measure_names
        assert "t7d_revenue" in measure_names

    def test_measure_comment(self):
        mv = parse_metric_view("cat.sch.orders_metrics", _SIMPLE_DDL)
        rev = next(m for m in mv.measures if m.name == "total_revenue")
        assert rev.comment == "Gross revenue"

    def test_measure_display_name(self):
        mv = parse_metric_view("cat.sch.orders_metrics", _SIMPLE_DDL)
        avg = next(m for m in mv.measures if m.name == "avg_order_value")
        assert avg.display_name == "Avg Order Value"

    def test_measure_referenced_measures(self):
        mv = parse_metric_view("cat.sch.orders_metrics", _SIMPLE_DDL)
        avg = next(m for m in mv.measures if m.name == "avg_order_value")
        assert set(avg.referenced_measures) == {"total_revenue", "order_count"}

    def test_measure_window(self):
        mv = parse_metric_view("cat.sch.orders_metrics", _SIMPLE_DDL)
        t7d = next(m for m in mv.measures if m.name == "t7d_revenue")
        assert len(t7d.window) == 1
        w = t7d.window[0]
        assert w.order == "order_date"
        assert w.range == "trailing 7 day"
        assert w.semiadditive == "last"

    def test_lineage_initially_empty(self):
        mv = parse_metric_view("cat.sch.orders_metrics", _SIMPLE_DDL)
        for m in mv.measures:
            assert m.lineage == ()

    def test_raises_on_missing_yaml_body(self):
        with pytest.raises(ValueError, match="No \\$\\$"):
            parse_metric_view("cat.sch.view", _NOT_METRIC_VIEW_DDL)

    def test_returns_frozen_definition(self):
        mv = parse_metric_view("cat.sch.orders_metrics", _SIMPLE_DDL)
        assert isinstance(mv, MetricViewDefinition)
        with pytest.raises((AttributeError, TypeError)):
            mv.full_name = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# extract_column_refs
# ---------------------------------------------------------------------------


class TestExtractColumnRefs:
    def test_simple_aggregate(self):
        refs = extract_column_refs("SUM(o_totalprice)", "cat.sch.fact_orders")
        assert ("cat.sch.fact_orders", "o_totalprice") in refs

    def test_count_star_no_refs(self):
        refs = extract_column_refs("COUNT(*)", "cat.sch.fact_orders")
        # COUNT(*) expands to a Star, not a Column — no refs expected
        assert refs == []

    def test_count_literal_no_refs(self):
        refs = extract_column_refs("COUNT(1)", "cat.sch.fact_orders")
        assert refs == []

    def test_qualified_column_resolved_to_alias(self):
        alias_map = {
            "source": "cat.sch.fact_orders",
            "customer": "cat.sch.dim_customer",
        }
        refs = extract_column_refs(
            "customer.c_name", "cat.sch.fact_orders", alias_map
        )
        assert ("cat.sch.dim_customer", "c_name") in refs

    def test_unqualified_column_uses_source_table(self):
        refs = extract_column_refs("SUM(revenue)", "cat.sch.fact_sales")
        assert ("cat.sch.fact_sales", "revenue") in refs

    def test_measure_refs_ignored(self):
        refs = extract_column_refs(
            "MEASURE(total_revenue) / MEASURE(order_count)", "cat.sch.tbl"
        )
        # MEASURE() calls are replaced with literals — no column refs
        assert refs == []

    def test_deduplication(self):
        refs = extract_column_refs(
            "SUM(price) + AVG(price)", "cat.sch.tbl"
        )
        # 'price' should appear only once
        assert refs.count(("cat.sch.tbl", "price")) == 1

    def test_multiple_columns(self):
        refs = extract_column_refs(
            "SUM(list_price) - SUM(discount)", "cat.sch.products"
        )
        assert ("cat.sch.products", "list_price") in refs
        assert ("cat.sch.products", "discount") in refs


# ---------------------------------------------------------------------------
# extract_measure_refs
# ---------------------------------------------------------------------------


class TestExtractMeasureRefs:
    def test_single_ref(self):
        assert extract_measure_refs("MEASURE(total_revenue)") == [
            "total_revenue"]

    def test_multiple_refs(self):
        refs = extract_measure_refs("MEASURE(a) / MEASURE(b)")
        assert refs == ["a", "b"]

    def test_no_refs(self):
        assert extract_measure_refs("SUM(price)") == []

    def test_deduplication(self):
        refs = extract_measure_refs("MEASURE(x) + MEASURE(x)")
        assert refs == ["x"]

    def test_case_insensitive(self):
        refs = extract_measure_refs("measure(total_revenue)")
        assert refs == ["total_revenue"]
