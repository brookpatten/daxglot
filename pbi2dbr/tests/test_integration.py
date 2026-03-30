"""Integration tests using real PBIX files from data/powerbi/pbix/.

These tests exercise the full pbi2dbr pipeline:
  PbixExtractor → ModelAnalyzer → MetricViewGenerator → YAML / SQL DDL

Tests are skipped when the PBIX files are not present on disk.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml as pyyaml

pytestmark = pytest.mark.integration

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "powerbi" / "pbix"

_FILES = {
    "adventure_works": DATA_DIR / "Adventure Works DW 2020.pbix",
    "sales_returns": DATA_DIR / "Sales & Returns Sample v201912.pbix",
    "retail": DATA_DIR / "old-Retail-Analysis-Sample-PBIX.pbix",
    "customer_prof": DATA_DIR / "old-Customer-Profitability-Sample-PBIX.pbix",
    "human_resources": DATA_DIR / "old-Human-Resources-Sample-PBIX.pbix",
    "procurement": DATA_DIR / "old-Procurement-Analysis-Sample-PBIX.pbix",
}


def _skip_if_missing(key: str):
    """Return a pytest.mark.skipif for a named PBIX file."""
    path = _FILES[key]
    return pytest.mark.skipif(
        not path.exists(), reason=f"PBIX file not found: {path.name}"
    )


def _pbix(key: str) -> str:
    return str(_FILES[key])


# ---------------------------------------------------------------------------
# Lazy imports so collection doesn't fail without pbixray
# ---------------------------------------------------------------------------

def _imports():
    from pbi2dbr.analyzer import AnalysisOptions, ModelAnalyzer
    from pbi2dbr.extractor import PbixExtractor
    from pbi2dbr.generator import MetricViewGenerator
    return PbixExtractor, ModelAnalyzer, AnalysisOptions, MetricViewGenerator


# ===========================================================================
# Extractor-level integration tests
# ===========================================================================


@_skip_if_missing("adventure_works")
class TestAdventureWorksExtractor:
    """Adventure Works DW 2020 — large star schema, no DAX measures."""

    def test_extract_returns_semantic_model(self):
        PbixExtractor, *_ = _imports()
        from pbi2dbr.models import SemanticModel
        model = PbixExtractor(_pbix("adventure_works")).extract()
        assert isinstance(model, SemanticModel)

    def test_expected_tables_present(self):
        PbixExtractor, *_ = _imports()
        model = PbixExtractor(_pbix("adventure_works")).extract()
        expected = {"Currency", "Customer", "Date", "Product", "Sales"}
        assert expected.issubset(set(model.tables))

    def test_columns_populated(self):
        PbixExtractor, *_ = _imports()
        model = PbixExtractor(_pbix("adventure_works")).extract()
        assert len(model.columns) > 0
        tables_with_cols = {c.table for c in model.columns}
        assert "Sales" in tables_with_cols

    def test_relationships_populated(self):
        PbixExtractor, *_ = _imports()
        model = PbixExtractor(_pbix("adventure_works")).extract()
        assert len(model.relationships) > 0

    def test_active_relationships_connect_sales(self):
        PbixExtractor, *_ = _imports()
        model = PbixExtractor(_pbix("adventure_works")).extract()
        active = [r for r in model.relationships if r.is_active]
        sales_fk = [r for r in active if r.from_table == "Sales"]
        assert len(sales_fk) > 0, "Sales should have active FK relationships"

    def test_column_data_types_present(self):
        PbixExtractor, *_ = _imports()
        model = PbixExtractor(_pbix("adventure_works")).extract()
        for col in model.columns:
            assert col.data_type, f"Column {col.table}.{col.column} has empty data_type"

    def test_columns_for_helper(self):
        PbixExtractor, *_ = _imports()
        model = PbixExtractor(_pbix("adventure_works")).extract()
        sales_cols = model.columns_for("Sales")
        assert len(sales_cols) > 0
        assert all(c.table == "Sales" for c in sales_cols)

    def test_no_measures(self):
        """Adventure Works DW 2020 PBIX has no DAX measures."""
        PbixExtractor, *_ = _imports()
        model = PbixExtractor(_pbix("adventure_works")).extract()
        assert len(model.measures) == 0


@_skip_if_missing("sales_returns")
class TestSalesReturnsExtractor:
    """Sales & Returns — 15 tables, 58 measures, 9 relationships."""

    def test_extract_succeeds(self):
        PbixExtractor, *_ = _imports()
        from pbi2dbr.models import SemanticModel
        model = PbixExtractor(_pbix("sales_returns")).extract()
        assert isinstance(model, SemanticModel)

    def test_has_many_measures(self):
        PbixExtractor, *_ = _imports()
        model = PbixExtractor(_pbix("sales_returns")).extract()
        assert len(model.measures) >= 50

    def test_known_measure_present(self):
        PbixExtractor, *_ = _imports()
        model = PbixExtractor(_pbix("sales_returns")).extract()
        names = {m.name for m in model.measures}
        assert "Net Sales" in names

    def test_measure_expressions_non_empty(self):
        PbixExtractor, *_ = _imports()
        model = PbixExtractor(_pbix("sales_returns")).extract()
        for m in model.measures:
            if m.name in ("Net Sales", "Net Sales PM", "Units Sold", "Return Rate"):
                assert m.expression.strip(
                ), f"Measure {m.name!r} has empty expression"

    def test_net_sales_table(self):
        PbixExtractor, *_ = _imports()
        model = PbixExtractor(_pbix("sales_returns")).extract()
        net_sales = next(m for m in model.measures if m.name == "Net Sales")
        assert net_sales.table == "Analysis DAX"

    def test_sales_table_present(self):
        PbixExtractor, *_ = _imports()
        model = PbixExtractor(_pbix("sales_returns")).extract()
        assert "Sales" in model.tables

    def test_relationships_count(self):
        PbixExtractor, *_ = _imports()
        model = PbixExtractor(_pbix("sales_returns")).extract()
        assert len(model.relationships) >= 5

    def test_measures_for_helper(self):
        PbixExtractor, *_ = _imports()
        model = PbixExtractor(_pbix("sales_returns")).extract()
        analysis_measures = model.measures_for("Analysis DAX")
        assert len(analysis_measures) > 0
        assert all(m.table == "Analysis DAX" for m in analysis_measures)


@_skip_if_missing("retail")
class TestRetailAnalysisExtractor:
    """Retail Analysis — 8 tables, 32 measures, 6 relationships."""

    def test_extract_succeeds(self):
        PbixExtractor, *_ = _imports()
        from pbi2dbr.models import SemanticModel
        model = PbixExtractor(_pbix("retail")).extract()
        assert isinstance(model, SemanticModel)

    def test_expected_tables(self):
        PbixExtractor, *_ = _imports()
        model = PbixExtractor(_pbix("retail")).extract()
        assert "Sales" in model.tables
        assert "Store" in model.tables
        assert "Item" in model.tables

    def test_sales_measures_present(self):
        PbixExtractor, *_ = _imports()
        model = PbixExtractor(_pbix("retail")).extract()
        sales_measures = model.measures_for("Sales")
        assert len(sales_measures) > 0


# ===========================================================================
# Analyzer-level integration tests
# ===========================================================================


@_skip_if_missing("adventure_works")
class TestAdventureWorksAnalyzer:
    """Fact/dimension classification on the star schema."""

    def test_sales_identified_as_fact(self):
        PbixExtractor, ModelAnalyzer, AnalysisOptions, _ = _imports()
        model = PbixExtractor(_pbix("adventure_works")).extract()
        fts = ModelAnalyzer(model).analyze()
        names = {f.name for f in fts}
        assert "Sales" in names

    def test_dimension_tables_not_fact(self):
        PbixExtractor, ModelAnalyzer, AnalysisOptions, _ = _imports()
        model = PbixExtractor(_pbix("adventure_works")).extract()
        fts = ModelAnalyzer(model).analyze()
        names = {f.name for f in fts}
        # Pure dimension tables should not be classified as facts
        assert "Product" not in names
        assert "Customer" not in names
        assert "Date" not in names

    def test_sales_has_joins(self):
        PbixExtractor, ModelAnalyzer, AnalysisOptions, _ = _imports()
        model = PbixExtractor(_pbix("adventure_works")).extract()
        fts = ModelAnalyzer(model).analyze()
        sales = next(f for f in fts if f.name == "Sales")
        assert len(sales.joins) > 0

    def test_joins_have_on_clauses(self):
        PbixExtractor, ModelAnalyzer, AnalysisOptions, _ = _imports()
        model = PbixExtractor(_pbix("adventure_works")).extract()
        fts = ModelAnalyzer(model).analyze()
        sales = next(f for f in fts if f.name == "Sales")
        for j in sales.joins:
            assert j.on_clause, f"Join {j.name!r} missing on_clause"

    def test_joins_reference_uc_or_table(self):
        PbixExtractor, ModelAnalyzer, AnalysisOptions, _ = _imports()
        model = PbixExtractor(_pbix("adventure_works")).extract()
        fts = ModelAnalyzer(model).analyze()
        sales = next(f for f in fts if f.name == "Sales")
        for j in sales.joins:
            assert j.source_uc_ref, f"Join {j.name!r} has empty source_uc_ref"

    def test_sales_has_dimensions(self):
        PbixExtractor, ModelAnalyzer, AnalysisOptions, _ = _imports()
        model = PbixExtractor(_pbix("adventure_works")).extract()
        fts = ModelAnalyzer(model).analyze()
        sales = next(f for f in fts if f.name == "Sales")
        assert len(sales.dimensions) > 0

    def test_explicit_fact_tables_override(self):
        PbixExtractor, ModelAnalyzer, AnalysisOptions, _ = _imports()
        model = PbixExtractor(_pbix("adventure_works")).extract()
        opts = AnalysisOptions(fact_tables=["Product"])
        fts = ModelAnalyzer(model, opts).analyze()
        names = {f.name for f in fts}
        assert "Product" in names
        assert "Sales" not in names

    def test_exclude_tables(self):
        PbixExtractor, ModelAnalyzer, AnalysisOptions, _ = _imports()
        model = PbixExtractor(_pbix("adventure_works")).extract()
        opts = AnalysisOptions(exclude_tables=["Sales"])
        fts = ModelAnalyzer(model, opts).analyze()
        names = {f.name for f in fts}
        assert "Sales" not in names


@_skip_if_missing("retail")
class TestRetailAnalysisAnalyzer:
    """Star schema with 3 fact candidates and many measures."""

    def test_sales_is_fact(self):
        PbixExtractor, ModelAnalyzer, *_ = _imports()
        model = PbixExtractor(_pbix("retail")).extract()
        fts = ModelAnalyzer(model).analyze()
        names = {f.name for f in fts}
        assert "Sales" in names

    def test_sales_has_measures(self):
        PbixExtractor, ModelAnalyzer, *_ = _imports()
        model = PbixExtractor(_pbix("retail")).extract()
        fts = ModelAnalyzer(model).analyze()
        sales = next(f for f in fts if f.name == "Sales")
        assert len(sales.measures) > 0

    def test_sales_has_three_joins(self):
        """Sales → District, Item, Store (3 FK relationships)."""
        PbixExtractor, ModelAnalyzer, *_ = _imports()
        model = PbixExtractor(_pbix("retail")).extract()
        fts = ModelAnalyzer(model).analyze()
        sales = next(f for f in fts if f.name == "Sales")
        assert len(sales.joins) == 3

    def test_joined_dimension_columns_exposed(self):
        """Joined dim-table columns should appear as prefixed dimensions."""
        PbixExtractor, ModelAnalyzer, *_ = _imports()
        model = PbixExtractor(_pbix("retail")).extract()
        fts = ModelAnalyzer(model).analyze()
        sales = next(f for f in fts if f.name == "Sales")
        join_names = {j.name for j in sales.joins}
        # At least one dimension should be prefixed with a join alias
        prefixed_dims = [
            d for d in sales.dimensions
            if any(d.name.startswith(alias) for alias in join_names)
        ]
        assert len(prefixed_dims) > 0


@_skip_if_missing("customer_prof")
class TestCustomerProfitabilityAnalyzer:
    """Fact table with many measures and 5 joins."""

    def test_fact_table_detected(self):
        PbixExtractor, ModelAnalyzer, *_ = _imports()
        model = PbixExtractor(_pbix("customer_prof")).extract()
        fts = ModelAnalyzer(model).analyze()
        names = {f.name for f in fts}
        assert "Fact" in names

    def test_fact_has_many_measures(self):
        PbixExtractor, ModelAnalyzer, *_ = _imports()
        model = PbixExtractor(_pbix("customer_prof")).extract()
        fts = ModelAnalyzer(model).analyze()
        fact = next(f for f in fts if f.name == "Fact")
        assert len(fact.measures) >= 40

    def test_fact_has_joins(self):
        PbixExtractor, ModelAnalyzer, *_ = _imports()
        model = PbixExtractor(_pbix("customer_prof")).extract()
        fts = ModelAnalyzer(model).analyze()
        fact = next(f for f in fts if f.name == "Fact")
        assert len(fact.joins) > 0


# ===========================================================================
# Generator-level integration tests
# ===========================================================================


@_skip_if_missing("adventure_works")
class TestAdventureWorksGenerator:
    """Full pipeline: extractor → analyzer → generator on Adventure Works."""

    @pytest.fixture(scope="class")
    def spec(self):
        PbixExtractor, ModelAnalyzer, _, MetricViewGenerator = _imports()
        model = PbixExtractor(_pbix("adventure_works")).extract()
        fts = ModelAnalyzer(model).analyze()
        sales = next(f for f in fts if f.name == "Sales")
        gen = MetricViewGenerator()
        return gen.build_spec(sales, target_catalog="dev", target_schema="pbi")

    def test_spec_has_name(self, spec):
        assert spec.name == "sales"

    def test_spec_has_source(self, spec):
        assert spec.source

    def test_spec_has_dimensions(self, spec):
        assert len(spec.dimensions) > 0

    def test_yaml_is_valid(self, spec):
        _, _, _, MetricViewGenerator = _imports()
        gen = MetricViewGenerator()
        text = gen.to_yaml(spec)
        doc = pyyaml.safe_load(text)
        assert doc["version"] == "1.1"
        assert "source" in doc

    def test_yaml_has_joins(self, spec):
        _, _, _, MetricViewGenerator = _imports()
        gen = MetricViewGenerator()
        doc = pyyaml.safe_load(gen.to_yaml(spec))
        assert "joins" in doc
        assert len(doc["joins"]) > 0

    def test_join_structure_valid(self, spec):
        _, _, _, MetricViewGenerator = _imports()
        gen = MetricViewGenerator()
        doc = pyyaml.safe_load(gen.to_yaml(spec))
        for j in doc["joins"]:
            assert "name" in j
            assert "source" in j

    def test_ddl_is_valid(self, spec):
        _, _, _, MetricViewGenerator = _imports()
        gen = MetricViewGenerator()
        ddl = gen.to_sql_ddl(spec, catalog="dev", schema="pbi")
        assert "CREATE OR REPLACE VIEW" in ddl
        assert "WITH METRICS" in ddl
        assert "LANGUAGE YAML" in ddl
        assert "$$" in ddl

    def test_ddl_embeds_valid_yaml(self, spec):
        _, _, _, MetricViewGenerator = _imports()
        gen = MetricViewGenerator()
        ddl = gen.to_sql_ddl(spec, catalog="dev", schema="pbi")
        inner_yaml = ddl.split("$$")[1]
        doc = pyyaml.safe_load(inner_yaml)
        assert isinstance(doc, dict)
        assert doc["version"] == "1.1"

    def test_write_produces_files(self, spec, tmp_path):
        _, _, _, MetricViewGenerator = _imports()
        gen = MetricViewGenerator()
        yaml_path, sql_path = gen.write(
            spec, output_dir=tmp_path, catalog="dev", schema="pbi")
        assert yaml_path.exists()
        assert sql_path.exists()
        assert yaml_path.stat().st_size > 0
        assert sql_path.stat().st_size > 0


@_skip_if_missing("sales_returns")
class TestSalesReturnsMeasureTranslation:
    """Verify DAX measures from Sales & Returns are translated to SQL."""

    @pytest.fixture(scope="class")
    def analysis_dax_spec(self):
        PbixExtractor, ModelAnalyzer, AnalysisOptions, MetricViewGenerator = _imports()
        model = PbixExtractor(_pbix("sales_returns")).extract()
        opts = AnalysisOptions(fact_tables=["Analysis DAX"])
        fts = ModelAnalyzer(model, opts).analyze()
        fact = next(f for f in fts if f.name == "Analysis DAX")
        gen = MetricViewGenerator()
        return gen.build_spec(fact)

    def test_measures_translated(self, analysis_dax_spec):
        assert len(analysis_dax_spec.measures) > 0

    def test_net_sales_translated(self, analysis_dax_spec):
        # Measure names are preserved from the original DAX (not snake_cased)
        net_sales = next(
            (m for m in analysis_dax_spec.measures if m.name == "Net Sales"),
            None,
        )
        assert net_sales is not None, "Net Sales measure not found"
        assert "SUM" in net_sales.expr.upper()

    def test_time_intelligence_produces_window(self, analysis_dax_spec):
        """Net Sales PM uses PREVIOUSMONTH → should produce a window spec."""
        pm = next(
            (m for m in analysis_dax_spec.measures if "pm" in m.name.lower()),
            None,
        )
        assert pm is not None, "No trailing-month measure found"
        assert len(pm.window) > 0, f"Expected window spec on {pm.name!r}"
        assert any("month" in ws["range"] for ws in pm.window)

    def test_window_spec_has_order_and_range(self, analysis_dax_spec):
        window_measures = [m for m in analysis_dax_spec.measures if m.window]
        for m in window_measures:
            for ws in m.window:
                assert "order" in ws, f"Missing 'order' in window spec of {m.name!r}"
                assert "range" in ws, f"Missing 'range' in window spec of {m.name!r}"

    def test_measures_have_sql_expr(self, analysis_dax_spec):
        for m in analysis_dax_spec.measures:
            assert m.expr.strip(), f"Measure {m.name!r} has empty sql_expr"

    def test_original_dax_preserved(self, analysis_dax_spec):
        for m in analysis_dax_spec.measures:
            assert m.original_dax is not None, f"Measure {m.name!r} missing original_dax"

    def test_yaml_has_measures(self, analysis_dax_spec):
        _, _, _, MetricViewGenerator = _imports()
        gen = MetricViewGenerator()
        doc = pyyaml.safe_load(gen.to_yaml(analysis_dax_spec))
        assert "measures" in doc
        assert len(doc["measures"]) > 0

    def test_window_measure_in_yaml(self, analysis_dax_spec):
        _, _, _, MetricViewGenerator = _imports()
        gen = MetricViewGenerator()
        doc = pyyaml.safe_load(gen.to_yaml(analysis_dax_spec))
        window_measures = [m for m in doc["measures"] if "window" in m]
        assert len(
            window_measures) > 0, "Expected at least one measure with 'window' in YAML"
        for m in window_measures:
            assert isinstance(m["window"], list)
            assert len(m["window"]) > 0


@_skip_if_missing("retail")
class TestRetailFullPipeline:
    """End-to-end pipeline test on Retail Analysis Sales table."""

    @pytest.fixture(scope="class")
    def retail_sales_spec(self):
        PbixExtractor, ModelAnalyzer, _, MetricViewGenerator = _imports()
        model = PbixExtractor(_pbix("retail")).extract()
        fts = ModelAnalyzer(model).analyze()
        sales = next(f for f in fts if f.name == "Sales")
        return MetricViewGenerator().build_spec(sales, target_catalog="dev", target_schema="pbi")

    def test_spec_name(self, retail_sales_spec):
        assert retail_sales_spec.name == "sales"

    def test_has_measures(self, retail_sales_spec):
        assert len(retail_sales_spec.measures) >= 20

    def test_has_dimensions(self, retail_sales_spec):
        assert len(retail_sales_spec.dimensions) >= 20

    def test_has_joins(self, retail_sales_spec):
        assert len(retail_sales_spec.joins) == 3

    def test_totalsales_measure(self, retail_sales_spec):
        """TotalSales = [Regular_Sales_Dollars]+[Markdown_Sales_Dollars] should translate."""
        total = next(
            (m for m in retail_sales_spec.measures if m.name == "TotalSales"),
            None,
        )
        assert total is not None, "TotalSales measure not found"
        # TotalSales is a measure-reference sum — expr should not be empty
        assert total.expr.strip()

    def test_yaml_dimensions_have_expr(self, retail_sales_spec):
        _, _, _, MetricViewGenerator = _imports()
        doc = pyyaml.safe_load(
            MetricViewGenerator().to_yaml(retail_sales_spec))
        for dim in doc.get("dimensions", []):
            assert "expr" in dim, f"Dimension {dim.get('name')!r} missing expr"
            assert dim["expr"], f"Dimension {dim.get('name')!r} has empty expr"

    def test_yaml_measures_have_expr(self, retail_sales_spec):
        _, _, _, MetricViewGenerator = _imports()
        doc = pyyaml.safe_load(
            MetricViewGenerator().to_yaml(retail_sales_spec))
        for m in doc.get("measures", []):
            assert "expr" in m, f"Measure {m.get('name')!r} missing expr"
            assert m["expr"], f"Measure {m.get('name')!r} has empty expr"

    def test_full_ddl_roundtrip(self, retail_sales_spec, tmp_path):
        """Write YAML + SQL, read them back, verify structure."""
        _, _, _, MetricViewGenerator = _imports()
        gen = MetricViewGenerator()
        yaml_path, sql_path = gen.write(
            retail_sales_spec, output_dir=tmp_path, catalog="dev", schema="pbi"
        )
        # YAML file is valid
        doc = pyyaml.safe_load(yaml_path.read_text())
        assert doc["version"] == "1.1"
        assert "measures" in doc

        # SQL file wraps the YAML
        sql = sql_path.read_text()
        assert "CREATE OR REPLACE VIEW" in sql
        inner = sql.split("$$")[1]
        assert pyyaml.safe_load(inner)["version"] == "1.1"


@_skip_if_missing("customer_prof")
class TestCustomerProfitabilityFullPipeline:
    """End-to-end on the Fact table with 44 measures and 5 joins."""

    @pytest.fixture(scope="class")
    def fact_spec(self):
        PbixExtractor, ModelAnalyzer, _, MetricViewGenerator = _imports()
        model = PbixExtractor(_pbix("customer_prof")).extract()
        fts = ModelAnalyzer(model).analyze()
        fact = next(f for f in fts if f.name == "Fact")
        return MetricViewGenerator().build_spec(fact, target_catalog="dev", target_schema="pbi")

    def test_many_measures_translated(self, fact_spec):
        assert len(fact_spec.measures) >= 40

    def test_total_revenue_measure(self, fact_spec):
        # Preserved name from DAX
        total_rev = next(
            (m for m in fact_spec.measures if m.name == "Total Revenue"),
            None,
        )
        assert total_rev is not None, "Total Revenue measure not found"
        assert "SUM" in total_rev.expr.upper()

    def test_yaml_valid(self, fact_spec):
        _, _, _, MetricViewGenerator = _imports()
        doc = pyyaml.safe_load(MetricViewGenerator().to_yaml(fact_spec))
        assert doc["version"] == "1.1"
        assert len(doc.get("measures", [])) >= 40

    def test_all_measures_have_expr(self, fact_spec):
        for m in fact_spec.measures:
            assert m.expr.strip(), f"Measure {m.name!r} has empty expr"


# ===========================================================================
# Multi-file smoke tests — verify every PBIX parses without crashing
# ===========================================================================


@pytest.mark.skipif(not any(p.exists() for p in _FILES.values()), reason="No PBIX files found")
class TestAllFilesSmokeTest:
    """Verify that all available PBIX files can be processed end-to-end
    without raising exceptions.  Individual assertions are deliberately
    minimal — the goal is to catch crashes, not validate semantics."""

    @pytest.mark.parametrize(
        "key",
        [k for k, p in _FILES.items() if p.exists()],
    )
    def test_extract_does_not_crash(self, key):
        PbixExtractor, *_ = _imports()
        from pbi2dbr.models import SemanticModel
        model = PbixExtractor(_pbix(key)).extract()
        assert isinstance(model, SemanticModel)
        assert isinstance(model.tables, list)

    @pytest.mark.parametrize(
        "key",
        [k for k, p in _FILES.items() if p.exists()],
    )
    def test_analyze_does_not_crash(self, key):
        PbixExtractor, ModelAnalyzer, *_ = _imports()
        model = PbixExtractor(_pbix(key)).extract()
        fact_tables = ModelAnalyzer(model).analyze()
        assert isinstance(fact_tables, list)

    @pytest.mark.parametrize(
        "key",
        [k for k, p in _FILES.items() if p.exists()],
    )
    def test_generate_yaml_does_not_crash(self, key):
        PbixExtractor, ModelAnalyzer, _, MetricViewGenerator = _imports()
        model = PbixExtractor(_pbix(key)).extract()
        fact_tables = ModelAnalyzer(model).analyze()
        if not fact_tables:
            pytest.skip(f"No fact tables detected in {key}")
        gen = MetricViewGenerator()
        for ft in fact_tables:
            spec = gen.build_spec(ft)
            yaml_text = gen.to_yaml(spec)
            doc = pyyaml.safe_load(yaml_text)
            assert doc["version"] == "1.1"

    @pytest.mark.parametrize(
        "key",
        [k for k, p in _FILES.items() if p.exists()],
    )
    def test_generate_ddl_does_not_crash(self, key):
        PbixExtractor, ModelAnalyzer, _, MetricViewGenerator = _imports()
        model = PbixExtractor(_pbix(key)).extract()
        fact_tables = ModelAnalyzer(model).analyze()
        if not fact_tables:
            pytest.skip(f"No fact tables detected in {key}")
        gen = MetricViewGenerator()
        for ft in fact_tables:
            spec = gen.build_spec(ft)
            ddl = gen.to_sql_ddl(spec, catalog="dev", schema="pbi")
            assert "CREATE OR REPLACE VIEW" in ddl
