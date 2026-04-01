"""Unit tests for measurediff.serializer."""

from __future__ import annotations

import yaml

from measurediff.models import (
    DimensionDefinition,
    JoinDefinition,
    LineageColumn,
    MeasureDefinition,
    MetricViewDefinition,
    WindowSpec,
)
from measurediff.serializer import (
    measure_to_dict,
    measure_to_yaml,
    to_dict,
    to_yaml,
    write,
    write_measures,
)


def _make_view(**kwargs) -> MetricViewDefinition:
    """Build a minimal MetricViewDefinition with optional overrides."""
    defaults = dict(
        full_name="cat.sch.sales_metrics",
        source="cat.sch.fact_orders",
        version="1.1",
        comment="Test metric view",
    )
    defaults.update(kwargs)
    return MetricViewDefinition(**defaults)


class TestToDict:
    def test_required_fields_present(self):
        mv = _make_view()
        d = to_dict(mv)
        assert d["version"] == "1.1"
        assert d["full_name"] == "cat.sch.sales_metrics"
        assert d["source"] == "cat.sch.fact_orders"

    def test_optional_fields_omitted_when_none(self):
        mv = _make_view(comment=None, filter=None)
        d = to_dict(mv)
        assert "comment" not in d
        assert "filter" not in d

    def test_optional_fields_included_when_set(self):
        mv = _make_view(filter="status = 'O'")
        d = to_dict(mv)
        assert d["filter"] == "status = 'O'"

    def test_joins_serialised(self):
        join = JoinDefinition(
            name="customer",
            source="cat.sch.dim_customer",
            on="source.cid = customer.id",
        )
        mv = _make_view(joins=(join,))
        d = to_dict(mv)
        assert len(d["joins"]) == 1
        assert d["joins"][0]["name"] == "customer"
        assert d["joins"][0]["on"] == "source.cid = customer.id"

    def test_join_using_serialised(self):
        join = JoinDefinition(
            name="region",
            source="cat.sch.region",
            using=("region_id",),
        )
        mv = _make_view(joins=(join,))
        d = to_dict(mv)
        assert d["joins"][0]["using"] == ["region_id"]
        assert "on" not in d["joins"][0]

    def test_dimensions_serialised(self):
        dim = DimensionDefinition(
            name="order_date", expr="o_orderdate", comment="Order date"
        )
        mv = _make_view(dimensions=(dim,))
        d = to_dict(mv)
        assert d["dimensions"][0]["name"] == "order_date"
        assert d["dimensions"][0]["expr"] == "o_orderdate"
        assert d["dimensions"][0]["comment"] == "Order date"

    def test_measures_serialised(self):
        m = MeasureDefinition(name="total_revenue", expr="SUM(o_totalprice)")
        mv = _make_view(measures=(m,))
        d = to_dict(mv)
        assert d["measures"][0]["name"] == "total_revenue"
        assert d["measures"][0]["expr"] == "SUM(o_totalprice)"

    def test_measure_lineage_omitted_when_empty(self):
        m = MeasureDefinition(name="order_count", expr="COUNT(1)")
        mv = _make_view(measures=(m,))
        d = to_dict(mv)
        assert "lineage" not in d["measures"][0]

    def test_measure_lineage_serialised(self):
        leaf = LineageColumn(table="cat.raw.orders",
                             column="price", type="TABLE")
        root = LineageColumn(
            table="cat.sch.fact_orders",
            column="o_totalprice",
            type="METRIC_VIEW",
            upstream=(leaf,),
        )
        m = MeasureDefinition(
            name="total_revenue", expr="SUM(o_totalprice)", lineage=(root,)
        )
        mv = _make_view(measures=(m,))
        d = to_dict(mv)
        lin = d["measures"][0]["lineage"]
        assert len(lin) == 1
        assert lin[0]["table"] == "cat.sch.fact_orders"
        assert lin[0]["column"] == "o_totalprice"
        assert lin[0]["upstream"][0]["table"] == "cat.raw.orders"
        assert lin[0]["upstream"][0]["type"] == "TABLE"
        # leaf has no upstream key
        assert "upstream" not in lin[0]["upstream"][0]

    def test_measure_window_serialised(self):
        w = WindowSpec(order="date", range="trailing 7 day",
                       semiadditive="last")
        m = MeasureDefinition(
            name="t7d", expr="COUNT(DISTINCT id)", window=(w,))
        mv = _make_view(measures=(m,))
        d = to_dict(mv)
        win = d["measures"][0]["window"]
        assert win[0]["order"] == "date"
        assert win[0]["range"] == "trailing 7 day"
        assert win[0]["semiadditive"] == "last"

    def test_window_semiadditive_omitted_when_none(self):
        w = WindowSpec(order="date", range="cumulative")
        m = MeasureDefinition(name="cumulative", expr="SUM(x)", window=(w,))
        mv = _make_view(measures=(m,))
        d = to_dict(mv)
        assert "semiadditive" not in d["measures"][0]["window"][0]

    def test_referenced_measures_serialised(self):
        m = MeasureDefinition(
            name="aov",
            expr="MEASURE(rev) / MEASURE(cnt)",
            referenced_measures=("rev", "cnt"),
        )
        mv = _make_view(measures=(m,))
        d = to_dict(mv)
        assert d["measures"][0]["referenced_measures"] == ["rev", "cnt"]

    def test_empty_collections_omitted(self):
        mv = _make_view()
        d = to_dict(mv)
        assert "joins" not in d
        assert "dimensions" not in d
        assert "measures" not in d


class TestToYaml:
    def test_produces_valid_yaml(self):
        m = MeasureDefinition(name="revenue", expr="SUM(price)")
        mv = _make_view(measures=(m,))
        text = to_yaml(mv)
        parsed = yaml.safe_load(text)
        assert parsed["measures"][0]["name"] == "revenue"

    def test_multiline_filter_uses_block_literal(self):
        mv = _make_view(filter="status = 'O'\nAND region = 'US'")
        text = to_yaml(mv)
        assert "|" in text  # block literal marker

    def test_sort_keys_false_preserves_field_order(self):
        mv = _make_view()
        text = to_yaml(mv)
        # version should appear before full_name which appears before source
        v_pos = text.index("version")
        fn_pos = text.index("full_name")
        src_pos = text.index("source")
        assert v_pos < fn_pos < src_pos


class TestWrite:
    def test_writes_file(self, tmp_path):
        mv = _make_view()
        path = write(mv, tmp_path)
        assert path.exists()
        assert path.name == "sales_metrics.yaml"

    def test_written_file_is_valid_yaml(self, tmp_path):
        m = MeasureDefinition(name="rev", expr="SUM(price)")
        mv = _make_view(measures=(m,))
        path = write(mv, tmp_path)
        content = yaml.safe_load(path.read_text())
        assert content["measures"][0]["name"] == "rev"

    def test_creates_output_dir(self, tmp_path):
        new_dir = tmp_path / "nested" / "output"
        mv = _make_view()
        path = write(mv, new_dir)
        assert path.exists()

    def test_uses_last_segment_of_full_name(self, tmp_path):
        mv = _make_view(full_name="my_catalog.my_schema.my_view_name")
        path = write(mv, tmp_path)
        assert path.name == "my_view_name.yaml"


# ---------------------------------------------------------------------------
# measure_to_dict / measure_to_yaml
# ---------------------------------------------------------------------------


def _make_measure(**kwargs) -> MeasureDefinition:
    defaults = dict(name="total_revenue", expr="SUM(o_totalprice)")
    defaults.update(kwargs)
    return MeasureDefinition(**defaults)


class TestMeasureToDict:
    def test_metric_view_is_full_name_string(self):
        m = _make_measure()
        mv = _make_view()
        d = measure_to_dict(m, mv)
        assert d["metric_view"] == "cat.sch.sales_metrics"

    def test_metric_view_no_nested_structure(self):
        m = _make_measure()
        mv = _make_view(filter="status = 'O'", joins=(
            JoinDefinition(name="c", source="cat.sch.c",
                           on="source.id = c.id"),
        ))
        d = measure_to_dict(m, mv)
        # metric_view must be a plain string — no source/filter/joins/dimensions
        assert isinstance(d["metric_view"], str)

    def test_measure_fields_at_top_level(self):
        m = _make_measure()
        mv = _make_view()
        d = measure_to_dict(m, mv)
        assert d["name"] == "total_revenue"
        assert d["expr"] == "SUM(o_totalprice)"

    def test_measure_lineage_at_top_level(self):
        leaf = LineageColumn(table="cat.raw.t", column="price", type="TABLE")
        m = _make_measure(lineage=(leaf,))
        mv = _make_view()
        d = measure_to_dict(m, mv)
        assert "lineage" in d
        assert d["lineage"][0]["column"] == "price"

    def test_measure_lineage_omitted_when_empty(self):
        m = MeasureDefinition(name="cnt", expr="COUNT(1)")
        mv = _make_view()
        d = measure_to_dict(m, mv)
        assert "lineage" not in d

    def test_window_at_top_level(self):
        w = WindowSpec(order="date", range="trailing 7 day",
                       semiadditive="last")
        m = _make_measure(window=(w,))
        mv = _make_view()
        d = measure_to_dict(m, mv)
        assert d["window"][0]["order"] == "date"


class TestMeasureToYaml:
    def test_produces_valid_yaml(self):
        m = _make_measure()
        mv = _make_view()
        text = measure_to_yaml(m, mv)
        parsed = yaml.safe_load(text)
        assert parsed["name"] == "total_revenue"
        assert parsed["metric_view"] == "cat.sch.sales_metrics"

    def test_metric_view_key_comes_first(self):
        m = _make_measure()
        mv = _make_view()
        text = measure_to_yaml(m, mv)
        mv_pos = text.index("metric_view")
        name_pos = text.index("name:")
        assert mv_pos < name_pos


class TestWriteMeasures:
    def test_one_file_per_measure(self, tmp_path):
        m1 = _make_measure(name="revenue", expr="SUM(price)")
        m2 = MeasureDefinition(name="order_count", expr="COUNT(1)")
        mv = _make_view(measures=(m1, m2))
        paths = write_measures(mv, tmp_path)
        assert len(paths) == 2

    def test_filename_format(self, tmp_path):
        m = _make_measure(name="total_revenue")
        mv = _make_view(full_name="cat.sch.sales_metrics", measures=(m,))
        paths = write_measures(mv, tmp_path)
        assert paths[0].name == "cat.sch.sales_metrics.total_revenue.yaml"

    def test_written_file_is_valid_yaml(self, tmp_path):
        m = _make_measure(name="rev", expr="SUM(price)")
        mv = _make_view(measures=(m,))
        paths = write_measures(mv, tmp_path)
        content = yaml.safe_load(paths[0].read_text())
        assert content["name"] == "rev"
        assert content["metric_view"] == "cat.sch.sales_metrics"

    def test_creates_output_dir(self, tmp_path):
        m = _make_measure()
        mv = _make_view(measures=(m,))
        new_dir = tmp_path / "nested" / "output"
        paths = write_measures(mv, new_dir)
        assert paths[0].exists()

    def test_no_measures_returns_empty_list(self, tmp_path):
        mv = _make_view()
        paths = write_measures(mv, tmp_path)
        assert paths == []
