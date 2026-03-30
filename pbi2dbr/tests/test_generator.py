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

    def test_filter_expr_from_source_table_forwarded(self):
        """filter_expr on SourceTable flows into MetricViewSpec.filter → YAML filter."""
        import yaml as pyyaml

        gen = MetricViewGenerator()
        fact = FactTable(
            name="Sales",
            source_table=SourceTable(
                "Sales", uc_ref="dev.pbi.sales", filter_expr="Status = 'Active'"
            ),
            dimensions=[],
            measures=[],
        )
        spec = gen.build_spec(fact)
        assert spec.filter == "Status = 'Active'"
        doc = pyyaml.safe_load(gen.to_yaml(spec))
        assert doc.get("filter") == "Status = 'Active'"

    def test_no_filter_expr_means_no_filter_in_yaml(self):
        """When source_table.filter_expr is None, the YAML has no filter key."""
        import yaml as pyyaml

        gen = MetricViewGenerator()
        fact = _simple_fact()  # source_table has no filter_expr
        spec = gen.build_spec(fact)
        assert spec.filter is None
        doc = pyyaml.safe_load(gen.to_yaml(spec))
        assert "filter" not in doc


# ---------------------------------------------------------------------------
# _build_period_dimensions and period registry tests
# ---------------------------------------------------------------------------


class TestBuildPeriodDimensions:
    """Tests for the period dimension registry builder in translator.py."""

    def test_detects_date_trunc_year(self):
        from pbi2dbr.translator import _build_period_dimensions

        dims = [
            Dimension("order_year", "DATE_TRUNC('year', order_date)"),
            Dimension("order_date", "order_date"),
        ]
        result = _build_period_dimensions(dims)
        assert result.get("year") == "order_year"

    def test_detects_date_trunc_quarter(self):
        from pbi2dbr.translator import _build_period_dimensions

        dims = [
            Dimension("order_quarter", "DATE_TRUNC('quarter', order_date)")]
        result = _build_period_dimensions(dims)
        assert result.get("quarter") == "order_quarter"

    def test_detects_date_trunc_month(self):
        from pbi2dbr.translator import _build_period_dimensions

        dims = [Dimension("order_month", "DATE_TRUNC('month', order_date)")]
        result = _build_period_dimensions(dims)
        assert result.get("month") == "order_month"

    def test_falls_back_to_name_keyword(self):
        from pbi2dbr.translator import _build_period_dimensions

        dims = [Dimension("fiscal_year", "FiscalYear")]
        result = _build_period_dimensions(dims)
        assert result.get("year") == "fiscal_year"

    def test_date_trunc_takes_priority_over_name(self):
        from pbi2dbr.translator import _build_period_dimensions

        # DATE_TRUNC dim should win over a name-keyword dim for same period
        dims = [
            # name match only
            Dimension("year_num", "YEAR(order_date)"),
            # DATE_TRUNC
            Dimension("order_year", "DATE_TRUNC('year', order_date)"),
        ]
        result = _build_period_dimensions(dims)
        assert result.get("year") == "order_year"

    def test_empty_dimensions_returns_empty(self):
        from pbi2dbr.translator import _build_period_dimensions

        assert _build_period_dimensions([]) == {}


class TestTranslatorWithPeriodDimensions:
    """Integration: period dimensions flow through DaxBridge → translate_measure."""

    def _make_fact(self, dax: str, dims: list[Dimension]) -> FactTable:
        from pbi2dbr.models import PbiMeasure

        return FactTable(
            name="Sales",
            source_table=SourceTable("Sales", uc_ref="dev.pbi.sales"),
            dimensions=dims,
            measures=[PbiMeasure(
                table="Sales", name="ytd_sales", expression=dax)],
        )

    def test_ytd_uses_registry_dim(self):
        from pbi2dbr.translator import translate_fact_table

        dims = [
            Dimension("order_date", "order_date"),
            Dimension("order_year", "DATE_TRUNC('year', order_date)"),
        ]
        fact = self._make_fact(
            "= CALCULATE(SUM(Sales[Amount]), DATESYTD('Date'[order_date]))", dims
        )
        measures = translate_fact_table(fact)
        assert len(measures) == 1
        window = measures[0].window
        current_specs = [w for w in window if w["range"] == "current"]
        assert len(current_specs) == 1
        assert current_specs[0]["order"] == "order_year"

    def test_no_period_dim_issues_warning(self):
        from pbi2dbr.translator import translate_fact_table

        dims = [Dimension("order_date", "order_date")]  # no year dim
        fact = self._make_fact(
            "= CALCULATE(SUM(Sales[Amount]), DATESYTD('Date'[order_date]))", dims
        )
        measures = translate_fact_table(fact)
        assert len(measures) == 1
        assert any("guessed" in w for w in measures[0].warnings)


# ---------------------------------------------------------------------------
# Value.NativeQuery → source_sql tests
# ---------------------------------------------------------------------------


class TestNativeQuerySource:
    """build_spec + to_yaml when source table has Value.NativeQuery SQL."""

    _SIMPLE_SQL = "SELECT id, amount FROM prod.pbi.orders"
    _MULTILINE_SQL = "SELECT o.id, c.region\nFROM prod.pbi.orders o\nJOIN prod.pbi.customers c ON o.cust_id = c.id"

    def _make_fact_with_sql(self, sql: str, filter_expr=None) -> FactTable:
        return FactTable(
            name="Orders",
            source_table=SourceTable(
                "Orders", source_sql=sql, filter_expr=filter_expr),
            dimensions=[],
            measures=[],
        )

    def test_build_spec_source_is_sql(self):
        gen = MetricViewGenerator()
        fact = self._make_fact_with_sql(self._SIMPLE_SQL)
        spec = gen.build_spec(fact)
        assert spec.source == self._SIMPLE_SQL

    def test_build_spec_prefers_sql_over_uc_ref(self):
        gen = MetricViewGenerator()
        fact = FactTable(
            name="Orders",
            source_table=SourceTable(
                "Orders", uc_ref="dev.pbi.orders", source_sql=self._SIMPLE_SQL),
            dimensions=[],
            measures=[],
        )
        spec = gen.build_spec(fact)
        assert spec.source == self._SIMPLE_SQL

    def test_build_spec_filter_suppressed_when_sql_present(self):
        """filter_expr should NOT be forwarded when source_sql is set (SQL embeds it)."""
        gen = MetricViewGenerator()
        fact = self._make_fact_with_sql(
            self._SIMPLE_SQL, filter_expr="Status = 'A'")
        spec = gen.build_spec(fact)
        assert spec.filter is None

    def test_to_yaml_single_line_sql_parses_back(self):
        gen = MetricViewGenerator()
        fact = self._make_fact_with_sql(self._SIMPLE_SQL)
        spec = gen.build_spec(fact)
        text = gen.to_yaml(spec)
        doc = pyyaml.safe_load(text)
        assert doc["source"] == self._SIMPLE_SQL

    def test_to_yaml_multiline_sql_is_block_literal(self):
        """PyYAML emits multiline strings as block literals (|) when there are newlines."""
        gen = MetricViewGenerator()
        fact = self._make_fact_with_sql(self._MULTILINE_SQL)
        spec = gen.build_spec(fact)
        text = gen.to_yaml(spec)
        # Block literal indicator must appear in raw YAML
        assert "source: |" in text
        # And round-trip must preserve the SQL content
        doc = pyyaml.safe_load(text)
        assert "FROM prod.pbi.orders" in doc["source"]
        assert "JOIN prod.pbi.customers" in doc["source"]

    def test_to_yaml_no_filter_key_when_sql_source(self):
        gen = MetricViewGenerator()
        fact = self._make_fact_with_sql(self._SIMPLE_SQL, filter_expr="x = 1")
        spec = gen.build_spec(fact)
        doc = pyyaml.safe_load(gen.to_yaml(spec))
        assert "filter" not in doc


# ---------------------------------------------------------------------------
# Date dimension best-match fix
# ---------------------------------------------------------------------------


class TestDateDimensionBestMatch:
    """translate_fact_table picks the best date dimension across all measures."""

    def _make_fact(self, dax_exprs, dim_names):
        from pbi2dbr.models import PbiMeasure
        dims = [Dimension(name, name) for name in dim_names]
        measures = [
            PbiMeasure("Sales", f"m{i}", expr)
            for i, expr in enumerate(dax_exprs)
        ]
        return FactTable(
            name="Sales",
            source_table=SourceTable("Sales", uc_ref="dev.pbi.sales"),
            dimensions=dims,
            measures=measures,
        )

    def test_exact_name_match_preferred(self):
        """When a dim is named exactly after the detected column, it wins."""
        from pbi2dbr.translator import _best_date_dimension, _detect_date_dimension_from_measures
        from pbi2dbr.models import PbiMeasure
        measures = [PbiMeasure("S", "m", "= CALCULATE(SUM(S[x]), DATESYTD('Date'[order_date]))")]
        detected = _detect_date_dimension_from_measures(measures)
        assert detected == "order_date"
        dims = [Dimension("fiscal_date", "fiscal_date"), Dimension("order_date", "order_date")]
        assert _best_date_dimension(dims, detected) == "order_date"

    def test_falls_back_to_any_date_dim(self):
        """No exact match → first dim with 'date' in name is used."""
        from pbi2dbr.translator import _best_date_dimension
        dims = [Dimension("region", "region"), Dimension("calendar_date", "CalendarDate")]
        assert _best_date_dimension(dims, None) == "calendar_date"

    def test_no_date_dim_returns_fallback(self):
        from pbi2dbr.translator import _best_date_dimension
        dims = [Dimension("region", "Region")]
        assert _best_date_dimension(dims, None) == "date"

    def test_most_common_column_wins_when_multiple_time_intel_measures(self):
        """With two time-intel measures referencing different columns, the more
        common column wins."""
        from pbi2dbr.translator import _detect_date_dimension_from_measures
        from pbi2dbr.models import PbiMeasure
        measures = [
            PbiMeasure("S", "a", "= CALCULATE(SUM(S[x]), DATESYTD('Date'[order_date]))"),
            PbiMeasure("S", "b", "= CALCULATE(SUM(S[x]), DATESYTD('Date'[order_date]))"),
            PbiMeasure("S", "c", "= CALCULATE(SUM(S[x]), DATESYTD('Date'[ship_date]))"),
        ]
        detected = _detect_date_dimension_from_measures(measures)
        assert detected == "order_date"
