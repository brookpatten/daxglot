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
