"""pbi2dbr CLI — convert PowerBI PBIX files to Databricks metric views."""

from __future__ import annotations

import sys
from pathlib import Path
from textwrap import indent
from typing import Optional

import click

from .analyzer import AnalysisOptions, ModelAnalyzer
from . import console
from .extractor import PbixExtractor
from .generator import MetricViewGenerator


@click.group()
@click.version_option(package_name="pbi2dbr")
def main() -> None:
    """Convert PowerBI semantic models (PBIX) to Databricks metric views."""


# ---------------------------------------------------------------------------
# convert
# ---------------------------------------------------------------------------


@main.command("convert")
@click.option(
    "--pbix",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to the .pbix file.",
)
@click.option("--catalog", required=True, help="Target Unity Catalog catalog name.")
@click.option("--schema", required=True, help="Target Unity Catalog schema name.")
@click.option(
    "--output-dir",
    default="./output",
    show_default=True,
    help="Directory to write YAML and SQL files.",
)
@click.option(
    "--fact-tables",
    default=None,
    help="Comma-separated list of tables to force as fact tables.",
)
@click.option("--prefix", default="", help="Prefix for generated view names.")
@click.option(
    "--source-catalog",
    default=None,
    help="Fallback source catalog when Power Query M cannot be resolved.",
)
@click.option(
    "--source-schema",
    default=None,
    help="Fallback source schema when Power Query M cannot be resolved.",
)
@click.option(
    "--exclude-tables",
    default=None,
    help="Comma-separated list of tables to exclude.",
)
@click.option(
    "--include-isolated",
    is_flag=True,
    default=False,
    help="Include tables with no relationships or measures.",
)
@click.option(
    "--dialect",
    default="databricks",
    show_default=True,
    help="SQL dialect for generated expressions.",
)
def convert(  # noqa: PLR0913
    pbix: str,
    catalog: str,
    schema: str,
    output_dir: str,
    fact_tables: Optional[str],
    prefix: str,
    source_catalog: Optional[str],
    source_schema: Optional[str],
    exclude_tables: Optional[str],
    include_isolated: bool,
    dialect: str,
) -> None:
    """Convert a PBIX file to Databricks metric view YAML and SQL DDL files."""
    console.enabled = True
    click.echo(f"Extracting model from {pbix} …")
    try:
        extractor = PbixExtractor(pbix)
        model = extractor.extract(
            source_catalog=source_catalog, source_schema=source_schema)
    except Exception as exc:  # noqa: BLE001
        click.echo(f"ERROR extracting PBIX: {exc}", err=True)
        sys.exit(1)

    click.echo(
        f"  {len(model.tables)} tables, "
        f"{len(model.measures)} measures, "
        f"{len(model.relationships)} relationships"
    )

    fact_list = [t.strip()
                 for t in fact_tables.split(",")] if fact_tables else None
    excl_list = [t.strip() for t in exclude_tables.split(",")
                 ] if exclude_tables else None

    opts = AnalysisOptions(
        fact_tables=fact_list,
        include_isolated=include_isolated,
        exclude_tables=excl_list or [],
    )

    click.echo("Analysing model …")
    analyzer = ModelAnalyzer(model, opts)
    facts = analyzer.analyze()

    for w in analyzer.warnings:
        click.echo(f"  WARN: {w}", err=True)

    if not facts:
        click.echo(
            "No fact tables found. Use --fact-tables to specify tables manually.", err=True)
        sys.exit(1)

    click.echo(
        f"  {len(facts)} fact table(s) identified: {', '.join(f.name for f in facts)}")

    gen = MetricViewGenerator(dialect=dialect)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    for fact in facts:
        click.echo(f"Generating metric view for '{fact.name}' …")
        spec = gen.build_spec(
            fact,
            target_catalog=catalog,
            target_schema=schema,
            view_name_prefix=prefix,
        )

        yaml_path, sql_path = gen.write(
            spec, output_path, catalog=catalog, schema=schema)

        approx_count = sum(1 for m in spec.measures if m.is_approximate)
        click.echo(
            f"  ✓ {yaml_path.name}, {sql_path.name} "
            f"({len(spec.measures)} measures, "
            f"{len(spec.dimensions)} dimensions"
            + (f", {approx_count} approximate" if approx_count else "")
            + ")"
        )
        # Print any measure warnings
        for m in spec.measures:
            for w in m.warnings:
                click.echo(f"    WARN [{m.name}]: {w}", err=True)

    click.echo(f"\nDone. Output written to {output_path.resolve()}")


# ---------------------------------------------------------------------------
# inspect
# ---------------------------------------------------------------------------


@main.command("inspect")
@click.option(
    "--pbix",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to the .pbix file.",
)
@click.option("--tables", is_flag=True, default=False, help="Show table schema.")
@click.option("--measures", is_flag=True, default=False, help="Show DAX measures.")
@click.option("--relationships", is_flag=True, default=False, help="Show relationships.")
@click.option("--all", "show_all", is_flag=True, default=False, help="Show everything.")
def inspect(
    pbix: str,
    tables: bool,
    measures: bool,
    relationships: bool,
    show_all: bool,
) -> None:
    """Inspect the semantic model in a PBIX file."""
    click.echo(f"Inspecting {pbix} …\n")
    try:
        extractor = PbixExtractor(pbix)
        model = extractor.extract()
    except Exception as exc:  # noqa: BLE001
        click.echo(f"ERROR: {exc}", err=True)
        sys.exit(1)

    click.echo(f"Summary")
    click.echo(f"  Tables:        {len(model.tables)}")
    click.echo(f"  Measures:      {len(model.measures)}")
    click.echo(f"  Relationships: {len(model.relationships)}")
    click.echo(f"  Columns:       {len(model.columns)}")

    if tables or show_all:
        click.echo("\nTables & Columns:")
        for tname in sorted(model.tables):
            cols = model.columns_for(tname)
            src = model.source_tables.get(tname)
            uc = f"  → {src.uc_ref}" if src and src.uc_ref else ""
            click.echo(f"  {tname}{uc} ({len(cols)} columns)")
            for col in cols[:10]:
                click.echo(f"      {col.column}  [{col.data_type}]")
            if len(cols) > 10:
                click.echo(f"      … and {len(cols) - 10} more")

    if measures or show_all:
        click.echo("\nMeasures:")
        for m in sorted(model.measures, key=lambda x: (x.table, x.name)):
            click.echo(f"  [{m.table}] {m.name}")
            for line in m.expression.strip().splitlines()[:3]:
                click.echo(f"      {line}")
            if len(m.expression.strip().splitlines()) > 3:
                click.echo("      …")

    if relationships or show_all:
        click.echo("\nRelationships (active):")
        for r in [r for r in model.relationships if r.is_active]:
            click.echo(
                f"  {r.from_table}[{r.from_column}] → "
                f"{r.to_table}[{r.to_column}]  ({r.cardinality})"
            )
