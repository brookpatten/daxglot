"""Tests for pbi2dbr.generator — YAML/DDL generation."""

from __future__ import annotations

import yaml as pyyaml
import pytest

from pbi2dbr.generator import MetricViewGenerator
from pbi2dbr.models import (
    Dimension,
    FactTable,
    Join,
    Measure,
    MetricViewSpec,
    SourceTable,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _simple_spec() -> MetricViewSpec:
    return MetricViewSpec(
        name="sales_mv",
        source="dev.pbi.sales",
        comment="Test metric view",
        dimensions=[
            Dimension("order_id", "OrderID", comment="Order identifier"),
            Dimension("region", "Region"),
        ],
        measures=[
            Measure(
                "total_sales",
                "SUM(Amount)",
                comment="Sum of sales amount",
                original_dax="= SUM(Sales[Amount])",
            ),
            Measure(
                "avg_price",
                "AVG(Price)",
            ),
        ],
    )


def _spec_with_window() -> MetricViewSpec:
    return MetricViewSpec(
        name="sales_time_mv",
        source="dev.pbi.sales",
        measures=[
            Measure(
                "yoy_sales",
                "SUM(Amount)",
                window=[{"order": "date", "range": "trailing 1 year"}],
                original_dax="= CALCULATE(SUM(Sales[Amount]), SAMEPERIODLASTYEAR('Date'[Date]))",
            )
        ],
    )


def _spec_with_joins() -> MetricViewSpec:
    return MetricViewSpec(
        name="sales_joined_mv",
        source="dev.pbi.sales",
        joins=[
            Join(
                name="customer",
                source_uc_ref="dev.pbi.customer",
                on_clause="source.CustomerID = customer.CustomerID",
            )
        ],
        dimensions=[
            Dimension("customer_name", "customer.Name"),
        ],
        measures=[Measure("total_sales", "SUM(Amount)")],
    )


def _spec_with_approximate() -> MetricViewSpec:
    return MetricViewSpec(
        name="approx_mv",
        source="dev.pbi.t",
        measures=[
            Measure("complex_m", "SUM(x)", is_approximate=True),
        ],
    )


def _simple_fact() -> FactTable:
    return FactTable(
        name="Sales",
        source_table=SourceTable("Sales", uc_ref="dev.pbi.sales"),
        dimensions=[Dimension("order_id", "OrderID")],
        measures=[],  # empty measures → won't attempt DAX translation
    )


# ---------------------------------------------------------------------------
# to_yaml tests
# ---------------------------------------------------------------------------


class TestToYaml:
    def test_yaml_has_version(self):
        gen = MetricViewGenerator()
        text = gen.to_yaml(_simple_spec())
        doc = pyyaml.safe_load(text)
        assert doc["version"] == "1.1"

    def test_yaml_has_source(self):
        gen = MetricViewGenerator()
        text = gen.to_yaml(_simple_spec())
        doc = pyyaml.safe_load(text)
        assert doc["source"] == "dev.pbi.sales"

    def test_yaml_has_comment(self):
        gen = MetricViewGenerator()
        text = gen.to_yaml(_simple_spec())
        doc = pyyaml.safe_load(text)
        assert doc["comment"] == "Test metric view"

    def test_yaml_has_dimensions(self):
        gen = MetricViewGenerator()
        text = gen.to_yaml(_simple_spec())
        doc = pyyaml.safe_load(text)
        assert "dimensions" in doc
        assert len(doc["dimensions"]) == 2

    def test_dimension_structure(self):
        gen = MetricViewGenerator()
        text = gen.to_yaml(_simple_spec())
        doc = pyyaml.safe_load(text)
        first_dim = doc["dimensions"][0]
        assert "name" in first_dim
        assert "expr" in first_dim

    def test_yaml_has_measures(self):
        gen = MetricViewGenerator()
        text = gen.to_yaml(_simple_spec())
        doc = pyyaml.safe_load(text)
        assert "measures" in doc
        assert len(doc["measures"]) == 2

    def test_measure_structure(self):
        gen = MetricViewGenerator()
        text = gen.to_yaml(_simple_spec())
        doc = pyyaml.safe_load(text)
        m = doc["measures"][0]
        assert m["name"] == "total_sales"
        assert "expr" in m

    def test_measure_comment_present(self):
        gen = MetricViewGenerator()
        text = gen.to_yaml(_simple_spec())
        doc = pyyaml.safe_load(text)
        m = next(x for x in doc["measures"] if x["name"] == "total_sales")
        assert m.get("comment") == "Sum of sales amount"

    def test_window_measure_emits_window(self):
        gen = MetricViewGenerator()
        text = gen.to_yaml(_spec_with_window())
        doc = pyyaml.safe_load(text)
        m = doc["measures"][0]
        assert "window" in m
        assert isinstance(m["window"], list)
        assert len(m["window"]) >= 1
        assert "order" in m["window"][0]
        assert "range" in m["window"][0]

    def test_join_emitted(self):
        gen = MetricViewGenerator()
        text = gen.to_yaml(_spec_with_joins())
        doc = pyyaml.safe_load(text)
        assert "joins" in doc
        j = doc["joins"][0]
        assert j["name"] == "customer"
        assert j["source"] == "dev.pbi.customer"
        assert "on" in j

    def test_valid_yaml(self):
        gen = MetricViewGenerator()
        for spec in [_simple_spec(), _spec_with_window(), _spec_with_joins()]:
            text = gen.to_yaml(spec)
            # Should not raise
            parsed = pyyaml.safe_load(text)
            assert isinstance(parsed, dict)


# ---------------------------------------------------------------------------
# to_sql_ddl tests
# ---------------------------------------------------------------------------


class TestToSqlDdl:
    def test_ddl_has_create_view(self):
        gen = MetricViewGenerator()
        ddl = gen.to_sql_ddl(_simple_spec(), catalog="dev", schema="pbi")
        assert "CREATE OR REPLACE VIEW" in ddl

    def test_ddl_has_with_metrics(self):
        gen = MetricViewGenerator()
        ddl = gen.to_sql_ddl(_simple_spec(), catalog="dev", schema="pbi")
        assert "WITH METRICS" in ddl

    def test_ddl_has_language_yaml(self):
        gen = MetricViewGenerator()
        ddl = gen.to_sql_ddl(_simple_spec(), catalog="dev", schema="pbi")
        assert "LANGUAGE YAML" in ddl

    def test_ddl_has_double_dollar_delimiters(self):
        gen = MetricViewGenerator()
        ddl = gen.to_sql_ddl(_simple_spec(), catalog="dev", schema="pbi")
        assert "$$" in ddl

    def test_ddl_view_name_qualified(self):
        gen = MetricViewGenerator()
        ddl = gen.to_sql_ddl(_simple_spec(), catalog="dev", schema="pbi")
        assert "`dev`" in ddl or "dev" in ddl
        assert "`pbi`" in ddl or "pbi" in ddl
        assert "sales_mv" in ddl

    def test_ddl_embeds_yaml(self):
        gen = MetricViewGenerator()
        ddl = gen.to_sql_ddl(_simple_spec(), catalog="dev", schema="pbi")
        # Extract YAML between $$ markers
        parts = ddl.split("$$")
        assert len(parts) >= 3
        inner = parts[1]
        doc = pyyaml.safe_load(inner)
        assert doc["version"] == "1.1"

    def test_approximate_warning_header(self):
        gen = MetricViewGenerator()
        ddl = gen.to_sql_ddl(_spec_with_approximate(),
                             catalog="dev", schema="pbi")
        assert "WARNING" in ddl

    def test_no_warning_when_exact(self):
        gen = MetricViewGenerator()
        ddl = gen.to_sql_ddl(_simple_spec(), catalog="dev", schema="pbi")
        assert "WARNING" not in ddl

    def test_schema_only_no_catalog(self):
        gen = MetricViewGenerator()
        ddl = gen.to_sql_ddl(_simple_spec(), schema="pbi")
        assert "CREATE OR REPLACE VIEW" in ddl
        assert "pbi" in ddl
        # The CREATE VIEW line should NOT contain a catalog qualifier
        create_line = next(l for l in ddl.splitlines()
                           if "CREATE OR REPLACE VIEW" in l)
        assert "dev" not in create_line

    def test_no_catalog_no_schema(self):
        gen = MetricViewGenerator()
        ddl = gen.to_sql_ddl(_simple_spec())
        assert "CREATE OR REPLACE VIEW" in ddl
        assert "sales_mv" in ddl


# ---------------------------------------------------------------------------
# write() tests
# ---------------------------------------------------------------------------


class TestWrite:
    def test_write_creates_yaml_and_sql_files(self, tmp_path):
        gen = MetricViewGenerator()
        yaml_path, sql_path = gen.write(
            _simple_spec(), output_dir=tmp_path, catalog="dev", schema="pbi"
        )
        assert yaml_path.exists()
        assert sql_path.exists()

    def test_yaml_file_is_valid(self, tmp_path):
        gen = MetricViewGenerator()
        yaml_path, _ = gen.write(_simple_spec(), output_dir=tmp_path)
        content = yaml_path.read_text()
        doc = pyyaml.safe_load(content)
        assert doc["version"] == "1.1"

    def test_sql_file_contains_create(self, tmp_path):
        gen = MetricViewGenerator()
        _, sql_path = gen.write(_simple_spec(), output_dir=tmp_path)
        content = sql_path.read_text()
        assert "CREATE OR REPLACE VIEW" in content

    def test_creates_output_dir_if_missing(self, tmp_path):
        gen = MetricViewGenerator()
        outdir = tmp_path / "new_output"
        assert not outdir.exists()
        gen.write(_simple_spec(), output_dir=outdir)
        assert outdir.exists()


# ---------------------------------------------------------------------------
# build_spec tests (with empty measures so no DAX parsing needed)
# ---------------------------------------------------------------------------


class TestBuildSpec:
    def test_spec_name_from_fact_table(self):
        gen = MetricViewGenerator()
        fact = _simple_fact()
        spec = gen.build_spec(fact, target_catalog="dev", target_schema="pbi")
        assert "sales" in spec.name.lower()

    def test_spec_source_uses_uc_ref(self):
        gen = MetricViewGenerator()
        fact = _simple_fact()
        spec = gen.build_spec(fact)
        assert spec.source == "dev.pbi.sales"

    def test_spec_source_falls_back_to_table_name(self):
        gen = MetricViewGenerator()
        fact = FactTable(
            name="Orders",
            source_table=SourceTable("Orders"),  # no uc_ref
            dimensions=[],
            measures=[],
        )
        spec = gen.build_spec(fact)
        assert spec.source == "Orders"

    def test_prefix_applied(self):
        gen = MetricViewGenerator()
        fact = _simple_fact()
        spec = gen.build_spec(fact, view_name_prefix="pbi_")
        assert spec.name.startswith("pbi_")
