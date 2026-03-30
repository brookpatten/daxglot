"""Tests for pbi2dbr.analyzer — model analysis and fact/dimension classification."""

from __future__ import annotations

import pytest

from pbi2dbr.analyzer import AnalysisOptions, ModelAnalyzer
from pbi2dbr.models import (
    ColumnSchema,
    Dimension,
    FactTable,
    PbiMeasure,
    Relationship,
    SemanticModel,
    SourceTable,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _simple_model() -> SemanticModel:
    """Star schema: Sales → Customer, Sales → Product, Sales → Date."""
    model = SemanticModel(
        tables=["Sales", "Customer", "Product", "Date"],
        columns=[
            ColumnSchema("Sales", "OrderID", "int64"),
            ColumnSchema("Sales", "CustomerID", "int64"),
            ColumnSchema("Sales", "ProductID", "int64"),
            ColumnSchema("Sales", "DateKey", "int64"),
            ColumnSchema("Sales", "Amount", "float64"),
            ColumnSchema("Customer", "CustomerID", "int64"),
            ColumnSchema("Customer", "Name", "object"),
            ColumnSchema("Customer", "Region", "object"),
            ColumnSchema("Product", "ProductID", "int64"),
            ColumnSchema("Product", "ProductName", "object"),
            ColumnSchema("Product", "Category", "object"),
            ColumnSchema("Date", "DateKey", "int64"),
            ColumnSchema("Date", "Date", "datetime64[ns]"),
            ColumnSchema("Date", "Year", "int64"),
        ],
        measures=[
            PbiMeasure("Sales", "Total Sales", "= SUM(Sales[Amount])"),
        ],
        relationships=[
            Relationship("Sales", "CustomerID", "Customer", "CustomerID"),
            Relationship("Sales", "ProductID", "Product", "ProductID"),
            Relationship("Sales", "DateKey", "Date", "DateKey"),
        ],
        source_tables={
            "Sales": SourceTable("Sales", uc_ref="dev.pbi.sales"),
            "Customer": SourceTable("Customer", uc_ref="dev.pbi.customer"),
            "Product": SourceTable("Product", uc_ref="dev.pbi.product"),
            "Date": SourceTable("Date", uc_ref="dev.pbi.date"),
        },
    )
    return model


def _no_relationship_model() -> SemanticModel:
    """A model with a single table, no relationships."""
    return SemanticModel(
        tables=["Metrics"],
        columns=[
            ColumnSchema("Metrics", "Month", "object"),
            ColumnSchema("Metrics", "Revenue", "float64"),
        ],
        measures=[
            PbiMeasure("Metrics", "Total Revenue", "= SUM(Metrics[Revenue])"),
        ],
        relationships=[],
        source_tables={"Metrics": SourceTable(
            "Metrics", uc_ref="dev.pbi.metrics")},
    )


# ---------------------------------------------------------------------------
# Fact table detection
# ---------------------------------------------------------------------------


class TestFactTableDetection:
    def test_star_schema_detects_sales_as_fact(self):
        analyzer = ModelAnalyzer(_simple_model())
        results = analyzer.analyze()
        names = {f.name for f in results}
        assert "Sales" in names

    def test_dimension_tables_not_in_results(self):
        analyzer = ModelAnalyzer(_simple_model())
        results = analyzer.analyze()
        names = {f.name for f in results}
        # Customer, Product, Date are PK-only → should not be fact tables
        assert "Customer" not in names
        assert "Product" not in names
        assert "Date" not in names

    def test_single_table_no_relationships(self):
        analyzer = ModelAnalyzer(_no_relationship_model())
        results = analyzer.analyze()
        assert len(results) == 1
        assert results[0].name == "Metrics"

    def test_explicit_fact_tables_override(self):
        opts = AnalysisOptions(fact_tables=["Customer"])
        analyzer = ModelAnalyzer(_simple_model(), opts)
        results = analyzer.analyze()
        names = {f.name for f in results}
        assert "Customer" in names
        assert "Sales" not in names

    def test_exclude_tables_removes_table(self):
        opts = AnalysisOptions(exclude_tables=["Sales"])
        analyzer = ModelAnalyzer(_simple_model(), opts)
        results = analyzer.analyze()
        names = {f.name for f in results}
        assert "Sales" not in names


# ---------------------------------------------------------------------------
# Join tree
# ---------------------------------------------------------------------------


class TestJoinTree:
    def test_sales_has_three_joins(self):
        analyzer = ModelAnalyzer(_simple_model())
        results = analyzer.analyze()
        sales_ft = next(f for f in results if f.name == "Sales")
        assert len(sales_ft.joins) == 3

    def test_join_names_are_aliases(self):
        analyzer = ModelAnalyzer(_simple_model())
        results = analyzer.analyze()
        sales_ft = next(f for f in results if f.name == "Sales")
        join_names = {j.name for j in sales_ft.joins}
        # aliases should be lower-case or snake_cased versions of table names
        assert any("customer" in n.lower() for n in join_names)
        assert any("product" in n.lower() for n in join_names)

    def test_join_has_on_clause(self):
        analyzer = ModelAnalyzer(_simple_model())
        results = analyzer.analyze()
        sales_ft = next(f for f in results if f.name == "Sales")
        for j in sales_ft.joins:
            assert j.on_clause, f"Join {j.name} missing on_clause"
            assert "." in j.on_clause  # source.col = alias.col form

    def test_join_depth_limit_respected(self):
        # Build a chain a → b → c → d → e
        model = SemanticModel(
            tables=["a", "b", "c", "d", "e"],
            columns=[
                ColumnSchema("a", "b_id", "int64"),
                ColumnSchema("b", "b_id", "int64"),
                ColumnSchema("b", "c_id", "int64"),
                ColumnSchema("c", "c_id", "int64"),
                ColumnSchema("c", "d_id", "int64"),
                ColumnSchema("d", "d_id", "int64"),
                ColumnSchema("d", "e_id", "int64"),
                ColumnSchema("e", "e_id", "int64"),
            ],
            measures=[PbiMeasure("a", "M", "= COUNT(a[b_id])")],
            relationships=[
                Relationship("a", "b_id", "b", "b_id"),
                Relationship("b", "c_id", "c", "c_id"),
                Relationship("c", "d_id", "d", "d_id"),
                Relationship("d", "e_id", "e", "e_id"),
            ],
        )
        opts = AnalysisOptions(max_snowflake_depth=2)
        analyzer = ModelAnalyzer(model, opts)
        results = analyzer.analyze()
        a_ft = next(f for f in results if f.name == "a")
        # At depth 0: a→b (1 join), at depth 1: b→c (1 nested join), depth 2 stops
        assert len(a_ft.joins) == 1
        assert len(a_ft.joins[0].nested_joins) == 1
        # No further nesting beyond depth limit
        assert len(a_ft.joins[0].nested_joins[0].nested_joins) == 0

    def test_nested_join_on_clause_uses_parent_alias(self):
        """Bug fix: ON clause for a nested join must reference the parent join alias,
        not the hard-coded 'source' prefix."""
        # Chain: fact → order → product
        model = SemanticModel(
            tables=["fact", "order", "product"],
            columns=[
                ColumnSchema("fact", "order_id", "int64"),
                ColumnSchema("order", "order_id", "int64"),
                ColumnSchema("order", "product_id", "int64"),
                ColumnSchema("product", "product_id", "int64"),
                ColumnSchema("product", "name", "object"),
            ],
            measures=[PbiMeasure("fact", "M", "= COUNT(fact[order_id])")],
            relationships=[
                Relationship("fact", "order_id", "order", "order_id"),
                Relationship("order", "product_id", "product", "product_id"),
            ],
        )
        analyzer = ModelAnalyzer(model, AnalysisOptions(max_snowflake_depth=3))
        results = analyzer.analyze()
        fact_ft = next(f for f in results if f.name == "fact")

        # Top-level join: fact → order, left side must be "source"
        order_join = fact_ft.joins[0]
        assert order_join.name == "order"
        assert order_join.on_clause.startswith("source."), (
            f"Expected ON to start with 'source.', got: {order_join.on_clause!r}"
        )

        # Nested join: order → product, left side must be "order" (NOT "source")
        product_join = order_join.nested_joins[0]
        assert product_join.name == "product"
        assert product_join.on_clause.startswith("order."), (
            f"Expected ON to start with 'order.', got: {product_join.on_clause!r}"
        )


# ---------------------------------------------------------------------------
# Dimension extraction
# ---------------------------------------------------------------------------


class TestDimensionExtraction:
    def test_fk_columns_excluded(self):
        analyzer = ModelAnalyzer(_simple_model())
        results = analyzer.analyze()
        sales_ft = next(f for f in results if f.name == "Sales")
        dim_exprs = {d.expr for d in sales_ft.dimensions}
        # FK columns should not appear as standalone dimensions
        assert "CustomerID" not in dim_exprs
        assert "ProductID" not in dim_exprs
        assert "DateKey" not in dim_exprs

    def test_non_fk_columns_included(self):
        analyzer = ModelAnalyzer(_simple_model())
        results = analyzer.analyze()
        sales_ft = next(f for f in results if f.name == "Sales")
        dim_exprs = {d.expr for d in sales_ft.dimensions}
        assert "OrderID" in dim_exprs

    def test_joined_columns_exposed(self):
        analyzer = ModelAnalyzer(_simple_model())
        results = analyzer.analyze()
        sales_ft = next(f for f in results if f.name == "Sales")
        # Joined Customer columns should appear as customer_name, customer_region etc.
        prefixed = [
            d for d in sales_ft.dimensions if d.name.startswith("customer")]
        assert len(prefixed) >= 1

    def test_deeply_nested_columns_exposed(self):
        """Bug fix: dimension extraction must recurse beyond 2 levels."""
        # Chain: fact → order → product → category
        model = SemanticModel(
            tables=["fact", "order", "product", "category"],
            columns=[
                ColumnSchema("fact", "order_id", "int64"),
                ColumnSchema("order", "order_id", "int64"),
                ColumnSchema("order", "product_id", "int64"),
                ColumnSchema("product", "product_id", "int64"),
                ColumnSchema("product", "category_id", "int64"),
                ColumnSchema("category", "category_id", "int64"),
                ColumnSchema("category", "label", "object"),
            ],
            measures=[PbiMeasure("fact", "M", "= COUNT(fact[order_id])")],
            relationships=[
                Relationship("fact", "order_id", "order", "order_id"),
                Relationship("order", "product_id", "product", "product_id"),
                Relationship("product", "category_id",
                             "category", "category_id"),
            ],
        )
        analyzer = ModelAnalyzer(model, AnalysisOptions(max_snowflake_depth=4))
        results = analyzer.analyze()
        fact_ft = next(f for f in results if f.name == "fact")

        dim_names = {d.name for d in fact_ft.dimensions}
        # Level 1: order columns
        assert any(n.startswith("order_") for n in dim_names)
        # Level 2: product columns
        assert any(n.startswith("order_product_") for n in dim_names)
        # Level 3: category columns — this was the bug; previously not extracted
        assert any(n.startswith("order_product_category_") for n in dim_names), (
            f"Missing level-3 dimensions. Got: {sorted(dim_names)}"
        )

        # Check expr format is correct dot-notation chain
        category_dim = next(
            d for d in fact_ft.dimensions if "category_label" in d.name)
        assert category_dim.expr == "order.product.category.label"

    def test_measures_attached(self):
        analyzer = ModelAnalyzer(_simple_model())
        results = analyzer.analyze()
        sales_ft = next(f for f in results if f.name == "Sales")
        assert any(m.name == "Total Sales" for m in sales_ft.measures)


# ---------------------------------------------------------------------------
# Warnings
# ---------------------------------------------------------------------------


class TestWarnings:
    def test_empty_model_warns(self):
        model = SemanticModel()
        analyzer = ModelAnalyzer(model)
        analyzer.analyze()
        assert len(analyzer.warnings) > 0


# ---------------------------------------------------------------------------
# Skip / should_skip logic
# ---------------------------------------------------------------------------


class TestShouldSkip:
    """Unit tests for FactTable.should_skip()."""

    def _make_fact(self, name="Sales", uc_ref="dev.pbi.sales",
                   is_calculated=False, measures=None, columns=None):
        return FactTable(
            name=name,
            source_table=SourceTable(name=name, uc_ref=uc_ref,
                                     is_calculated=is_calculated),
            measures=measures or [],
            dimensions=[],
        ), columns or []

    def test_normal_table_not_skipped(self):
        ft, cols = self._make_fact(
            measures=[PbiMeasure("Sales", "m", "= SUM(Sales[x])")]
        )
        skip, _ = ft.should_skip()
        assert not skip

    def test_calculated_table_skipped_by_default(self):
        ft, cols = self._make_fact(is_calculated=True)
        skip, reason = ft.should_skip()
        assert skip
        assert "calculated" in reason.lower()

    def test_calculated_table_not_skipped_when_flag_off(self):
        ft, cols = self._make_fact(is_calculated=True)
        skip, _ = ft.should_skip(skip_calculated=False)
        assert not skip

    def test_no_uc_ref_skipped_when_flag_on(self):
        ft, cols = self._make_fact(uc_ref=None)
        skip, reason = ft.should_skip(skip_no_uc_ref=True)
        assert skip
        assert "Unity Catalog" in reason

    def test_no_uc_ref_not_skipped_by_default(self):
        ft, cols = self._make_fact(uc_ref=None)
        skip, _ = ft.should_skip()
        assert not skip

    def test_system_table_skipped_by_default(self):
        for name in ["DateTableTemplate", "LocalDateTable_abc",
                     "DateTable_12345", "__InternalTable"]:
            ft, cols = self._make_fact(name=name)
            skip, reason = ft.should_skip()
            assert skip, f"Expected '{name}' to be skipped"
            assert "system" in reason.lower()

    def test_system_table_not_skipped_when_flag_off(self):
        ft, cols = self._make_fact(name="DateTableTemplate")
        skip, _ = ft.should_skip(skip_system_tables=False)
        assert not skip

    def test_no_measures_no_numeric_skipped_when_flag_on(self):
        ft, cols = self._make_fact(
            measures=[],
            columns=[ColumnSchema("Bridge", "id_a", "int64"),
                     ColumnSchema("Bridge", "id_b", "int64")],
        )
        # int64 is numeric — so should NOT skip (bridge has numeric FKs)
        skip, _ = ft.should_skip(
            require_measures_or_numeric=True,
            columns=[ColumnSchema("Bridge", "id_a", "int64")],
        )
        assert not skip

    def test_no_measures_no_numeric_actually_skipped(self):
        ft, _ = self._make_fact(measures=[])
        skip, reason = ft.should_skip(
            require_measures_or_numeric=True,
            columns=[ColumnSchema("T", "code", "object"),
                     ColumnSchema("T", "label", "object")],
        )
        assert skip
        assert "no DAX measures" in reason


class TestAnalyzerSkipsSystemTables:
    """Integration: ModelAnalyzer skips system tables via AnalysisOptions."""

    def test_date_table_template_excluded(self):
        model = SemanticModel(
            tables=["Sales", "DateTableTemplate"],
            columns=[
                ColumnSchema("Sales", "Amount", "float64"),
            ],
            measures=[PbiMeasure("Sales", "Total", "= SUM(Sales[Amount])")],
            relationships=[],
            source_tables={
                "Sales": SourceTable("Sales", uc_ref="dev.pbi.sales"),
                "DateTableTemplate": SourceTable("DateTableTemplate"),
            },
        )
        opts = AnalysisOptions(skip_system_tables=True)
        results = ModelAnalyzer(model, opts).analyze()
        names = [f.name for f in results]
        assert "DateTableTemplate" not in names
        assert "Sales" in names

    def test_system_tables_included_when_flag_off(self):
        model = SemanticModel(
            tables=["DateTableTemplate"],
            columns=[ColumnSchema("DateTableTemplate",
                                  "Date", "datetime64[ns]")],
            measures=[PbiMeasure("DateTableTemplate", "m",
                                 "= SUM(DateTableTemplate[Date])")],
            relationships=[],
            source_tables={"DateTableTemplate": SourceTable(
                "DateTableTemplate")},
        )
        opts = AnalysisOptions(skip_system_tables=False)
        results = ModelAnalyzer(model, opts).analyze()
        assert any(f.name == "DateTableTemplate" for f in results)

    def test_calculated_table_excluded(self):
        model = SemanticModel(
            tables=["Sales", "CalcTable"],
            columns=[
                ColumnSchema("Sales", "Amount", "float64"),
                ColumnSchema("CalcTable", "Val", "float64"),
            ],
            measures=[PbiMeasure("Sales", "Total", "= SUM(Sales[Amount])")],
            relationships=[],
            source_tables={
                "Sales": SourceTable("Sales", uc_ref="dev.pbi.sales"),
                "CalcTable": SourceTable("CalcTable", is_calculated=True),
            },
        )
        opts = AnalysisOptions(skip_calculated=True)
        results = ModelAnalyzer(model, opts).analyze()
        names = [f.name for f in results]
        assert "CalcTable" not in names

    def test_skip_produces_warning(self):
        model = SemanticModel(
            tables=["DateTableTemplate"],
            columns=[],
            measures=[
                PbiMeasure("DateTableTemplate", "m",
                           "= COUNT(DateTableTemplate[Date])")
            ],
            relationships=[],
            source_tables={"DateTableTemplate": SourceTable(
                "DateTableTemplate")},
        )
        analyzer = ModelAnalyzer(
            model, AnalysisOptions(skip_system_tables=True))
        analyzer.analyze()
        assert any("DateTableTemplate" in w for w in analyzer.warnings)
