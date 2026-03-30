"""Tests for pbi2dbr.extractor — PBIX extraction via PBIXRay."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from pbi2dbr.extractor import PbixExtractor
from pbi2dbr.models import SemanticModel


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


DATA_DIR = Path(__file__).parent.parent.parent / "data" / "powerbi" / "pbix"
ADVENTURE_WORKS = DATA_DIR / "Adventure Works DW 2020.pbix"
SALES_RETURNS = DATA_DIR / "Sales & Returns Sample v201912.pbix"


# ---------------------------------------------------------------------------
# Mocked extractor tests (unit tests — no PBIX file needed)
# ---------------------------------------------------------------------------


def _make_mock_ray(
    tables=None,
    schema=None,
    dax_measures=None,
    relationships=None,
    power_query=None,
):
    ray = MagicMock()

    # tables
    tables_df = pd.DataFrame({"Table": tables or ["Sales", "Customer"]})
    type(ray).tables = property(lambda self, _df=tables_df: _df)

    # schema
    if schema is None:
        schema = [
            ("Sales", "Amount", "float64"),
            ("Sales", "CustomerID", "int64"),
            ("Customer", "CustomerID", "int64"),
            ("Customer", "Name", "object"),
        ]
    schema_df = pd.DataFrame(
        schema, columns=["TableName", "ColumnName", "PandasDataType"])
    type(ray).schema = property(lambda self, _df=schema_df: _df)

    # dax_measures
    if dax_measures is None:
        dax_measures = [
            ("Sales", "Total Sales", "= SUM(Sales[Amount])", "", "")]
    measures_df = pd.DataFrame(
        dax_measures,
        columns=["TableName", "Name", "Expression",
                 "DisplayFolder", "Description"],
    )
    type(ray).dax_measures = property(lambda self, _df=measures_df: _df)

    # relationships
    if relationships is None:
        relationships = [
            ("Sales", "CustomerID", "Customer", "CustomerID", True, "ManyToOne")
        ]
    rels_df = pd.DataFrame(
        relationships,
        columns=[
            "FromTableName",
            "FromColumnName",
            "ToTableName",
            "ToColumnName",
            "IsActive",
            "Cardinality",
        ],
    )
    type(ray).relationships = property(lambda self, _df=rels_df: _df)

    # power_query
    if power_query is None:
        power_query = [
            (
                "Sales",
                'let Source = Databricks.Catalogs("host", [Catalog="dev", Schema="pbi"]), '
                'nav = Source{[Name="sales"]}[Data] in nav',
            )
        ]
    pq_df = pd.DataFrame(power_query, columns=["TableName", "Expression"])
    type(ray).power_query = property(lambda self, _df=pq_df: _df)

    return ray


class TestPbixExtractorMocked:
    def test_extract_returns_semantic_model(self):
        with patch("pbi2dbr.extractor.PBIXRay") as mock_cls:
            mock_cls.return_value = _make_mock_ray()
            extractor = PbixExtractor(self.fake_pbix)
            model = extractor.extract()
        assert isinstance(model, SemanticModel)

    def test_tables_populated(self):
        with patch("pbi2dbr.extractor.PBIXRay") as mock_cls:
            mock_cls.return_value = _make_mock_ray()
            model = PbixExtractor(self.fake_pbix).extract()
        assert "Sales" in model.tables
        assert "Customer" in model.tables

    def test_columns_populated(self):
        with patch("pbi2dbr.extractor.PBIXRay") as mock_cls:
            mock_cls.return_value = _make_mock_ray()
            model = PbixExtractor(self.fake_pbix).extract()
        assert len(model.columns) > 0
        col_names = {c.column for c in model.columns}
        assert "Amount" in col_names

    def test_measures_populated(self):
        with patch("pbi2dbr.extractor.PBIXRay") as mock_cls:
            mock_cls.return_value = _make_mock_ray()
            model = PbixExtractor(self.fake_pbix).extract()
        assert len(model.measures) == 1
        assert model.measures[0].name == "Total Sales"
        assert model.measures[0].table == "Sales"

    def test_relationships_populated(self):
        with patch("pbi2dbr.extractor.PBIXRay") as mock_cls:
            mock_cls.return_value = _make_mock_ray()
            model = PbixExtractor(self.fake_pbix).extract()
        assert len(model.relationships) == 1
        rel = model.relationships[0]
        assert rel.from_table == "Sales"
        assert rel.to_table == "Customer"
        assert rel.is_active

    def test_inactive_relationship_included(self):
        rels = [
            ("Sales", "CustomerID", "Customer", "CustomerID", False, "ManyToOne"),
        ]
        with patch("pbi2dbr.extractor.PBIXRay") as mock_cls:
            mock_cls.return_value = _make_mock_ray(relationships=rels)
            model = PbixExtractor(self.fake_pbix).extract()
        # Inactive relationships are still included in the model
        assert len(model.relationships) == 1
        assert not model.relationships[0].is_active

    def test_uc_ref_extracted_from_power_query(self):
        pq = [
            (
                "Sales",
                'let Source = Databricks.Catalogs("host"), '
                'nav1 = Source{[Name="dev"]}[Data], '
                'nav2 = nav1{[Name="pbi"]}[Data], '
                'nav3 = nav2{[Name="sales"]}[Data] in nav3',
            )
        ]
        with patch("pbi2dbr.extractor.PBIXRay") as mock_cls:
            mock_cls.return_value = _make_mock_ray(power_query=pq)
            model = PbixExtractor(self.fake_pbix).extract("dev", "pbi")
        # Should have resolved UC ref for Sales
        assert "Sales" in model.source_tables

    def test_multistep_let_three_nav_steps_resolves_uc_ref(self):
        """Multi-step let: three {[Name=...]} navigations → catalog.schema.table."""
        pq = [
            (
                "Orders",
                'let\n'
                '    Source = Databricks.Catalogs("adb-host"),\n'
                '    mycatalog = Source{[Name="prod"]}[Data],\n'
                '    myschema = mycatalog{[Name="retaildb"]}[Data],\n'
                '    mytable = myschema{[Name="orders"]}[Data]\n'
                'in mytable',
            )
        ]
        with patch("pbi2dbr.extractor.PBIXRay") as mock_cls:
            mock_cls.return_value = _make_mock_ray(
                tables=["Orders"],
                power_query=pq,
            )
            model = PbixExtractor(self.fake_pbix).extract()
        assert model.source_tables["Orders"].uc_ref == "prod.retaildb.orders"

    def test_multistep_let_two_nav_steps_uses_default_catalog(self):
        """Two navigation steps: uses provided catalog, extracts schema + table."""
        pq = [
            (
                "Sales",
                'let\n'
                '    Source = Databricks.Catalogs("host"),\n'
                '    sch = Source{[Name="finance"]}[Data],\n'
                '    tbl = sch{[Name="sales_fact"]}[Data]\n'
                'in tbl',
            )
        ]
        with patch("pbi2dbr.extractor.PBIXRay") as mock_cls:
            mock_cls.return_value = _make_mock_ray(
                tables=["Sales"],
                power_query=pq,
            )
            model = PbixExtractor(self.fake_pbix).extract(source_catalog="dev")
        assert model.source_tables["Sales"].uc_ref == "dev.finance.sales_fact"

    def test_multistep_let_one_nav_step_uses_default_catalog_and_schema(self):
        """One navigation step: fills in both catalog and schema from defaults."""
        pq = [
            (
                "Customers",
                'let Source = Databricks.Catalogs("host"),\n'
                '    tbl = Source{[Name="customers"]}[Data]\nin tbl',
            )
        ]
        with patch("pbi2dbr.extractor.PBIXRay") as mock_cls:
            mock_cls.return_value = _make_mock_ray(
                tables=["Customers"],
                power_query=pq,
            )
            model = PbixExtractor(self.fake_pbix).extract(
                source_catalog="dev", source_schema="pbi"
            )
        assert model.source_tables["Customers"].uc_ref == "dev.pbi.customers"

    def test_select_rows_simple_equality_extracted(self):
        """Table.SelectRows with simple equality predicate → filter_expr."""
        pq = [
            (
                "ActiveSales",
                'let\n'
                '    Source = Databricks.Catalogs("host"),\n'
                '    raw = Source{[Name="dev"]}[Data]{[Name="pbi"]}[Data]{[Name="sales"]}[Data],\n'
                '    filtered = Table.SelectRows(raw, each [Status] = "Active")\n'
                'in filtered',
            )
        ]
        with patch("pbi2dbr.extractor.PBIXRay") as mock_cls:
            mock_cls.return_value = _make_mock_ray(
                tables=["ActiveSales"],
                power_query=pq,
            )
            model = PbixExtractor(self.fake_pbix).extract()
        src = model.source_tables["ActiveSales"]
        assert src.filter_expr is not None
        assert "Status" in src.filter_expr
        assert "Active" in src.filter_expr

    def test_select_rows_numeric_comparison(self):
        """Table.SelectRows with numeric comparison → filter_expr."""
        pq = [
            (
                "BigOrders",
                'let Source = SomeSource,\n'
                '    f = Table.SelectRows(Source, each [Amount] > 1000)\n'
                'in f',
            )
        ]
        with patch("pbi2dbr.extractor.PBIXRay") as mock_cls:
            mock_cls.return_value = _make_mock_ray(
                tables=["BigOrders"],
                power_query=pq,
            )
            model = PbixExtractor(self.fake_pbix).extract()
        src = model.source_tables["BigOrders"]
        assert src.filter_expr == "Amount > 1000"

    def test_select_rows_compound_and_predicate(self):
        """Table.SelectRows with two clauses joined by 'and'."""
        pq = [
            (
                "T",
                'let f = Table.SelectRows(S, each [Region] = "West" and [Year] = 2024)\nin f',
            )
        ]
        with patch("pbi2dbr.extractor.PBIXRay") as mock_cls:
            mock_cls.return_value = _make_mock_ray(
                tables=["T"],
                power_query=pq,
            )
            model = PbixExtractor(self.fake_pbix).extract()
        fe = model.source_tables["T"].filter_expr
        assert fe is not None
        assert "Region" in fe and "West" in fe
        assert "AND" in fe
        assert "Year" in fe

    def test_select_rows_complex_predicate_returns_none(self):
        """Complex predicate that can't be safely translated → filter_expr is None."""
        pq = [
            (
                "T",
                'let f = Table.SelectRows(S, each List.Contains({"A","B"}, [Col]))\nin f',
            )
        ]
        with patch("pbi2dbr.extractor.PBIXRay") as mock_cls:
            mock_cls.return_value = _make_mock_ray(
                tables=["T"],
                power_query=pq,
            )
            model = PbixExtractor(self.fake_pbix).extract()
        assert model.source_tables["T"].filter_expr is None

    def test_no_select_rows_filter_expr_is_none(self):
        """M expression without Table.SelectRows → filter_expr is None."""
        pq = [
            (
                "Sales",
                'let Source = SomeConnector(), tbl = Source{[Name="sales"]}[Data] in tbl',
            )
        ]
        with patch("pbi2dbr.extractor.PBIXRay") as mock_cls:
            mock_cls.return_value = _make_mock_ray(
                tables=["Sales"],
                power_query=pq,
            )
            model = PbixExtractor(self.fake_pbix).extract()
        assert model.source_tables["Sales"].filter_expr is None

    def test_extract_source_catalog_param(self):
        with patch("pbi2dbr.extractor.PBIXRay") as mock_cls:
            mock_cls.return_value = _make_mock_ray()
            model = PbixExtractor(self.fake_pbix).extract(
                source_catalog="mycat", source_schema="mysch")
        assert isinstance(model, SemanticModel)

    def test_empty_measures_handled(self):
        with patch("pbi2dbr.extractor.PBIXRay") as mock_cls:
            mock_cls.return_value = _make_mock_ray(dax_measures=[])
            model = PbixExtractor(self.fake_pbix).extract()
        assert model.measures == []

    def test_columns_for_helper(self):
        with patch("pbi2dbr.extractor.PBIXRay") as mock_cls:
            mock_cls.return_value = _make_mock_ray()
            model = PbixExtractor(self.fake_pbix).extract()
        sales_cols = model.columns_for("Sales")
        assert all(c.table == "Sales" for c in sales_cols)

    def test_measures_for_helper(self):
        with patch("pbi2dbr.extractor.PBIXRay") as mock_cls:
            mock_cls.return_value = _make_mock_ray()
            model = PbixExtractor(self.fake_pbix).extract()
        sales_measures = model.measures_for("Sales")
        assert all(m.table == "Sales" for m in sales_measures)


# ---------------------------------------------------------------------------
# Integration tests with real PBIX files (skipped if files missing)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.skipif(
    not ADVENTURE_WORKS.exists(),
    reason="Adventure Works PBIX not found",
)
class TestAdventureWorksExtraction:
    def test_extract_succeeds(self):
        model = PbixExtractor(str(ADVENTURE_WORKS)).extract()
        assert isinstance(model, SemanticModel)

    def test_has_tables(self):
        model = PbixExtractor(str(ADVENTURE_WORKS)).extract()
        assert len(model.tables) > 0

    def test_has_measures(self):
        """Adventure Works DW 2020 contains no DAX measures."""
        model = PbixExtractor(str(ADVENTURE_WORKS)).extract()
        assert len(model.measures) == 0

    def test_has_relationships(self):
        model = PbixExtractor(str(ADVENTURE_WORKS)).extract()
        assert len(model.relationships) > 0

    def test_has_columns(self):
        model = PbixExtractor(str(ADVENTURE_WORKS)).extract()
        assert len(model.columns) > 0


@pytest.mark.integration
@pytest.mark.skipif(
    not SALES_RETURNS.exists(),
    reason="Sales & Returns PBIX not found",
)
class TestSalesReturnsExtraction:
    def test_extract_succeeds(self):
        model = PbixExtractor(str(SALES_RETURNS)).extract()
        assert isinstance(model, SemanticModel)

    def test_has_tables(self):
        model = PbixExtractor(str(SALES_RETURNS)).extract()
        assert len(model.tables) > 0
