"""measurediff CLI — collect metric view definitions with column lineage."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

import click


@click.group()
@click.version_option(package_name="measurediff")
def cli() -> None:
    """Collect and compare Databricks metric view measure definitions."""


# ---------------------------------------------------------------------------
# collect
# ---------------------------------------------------------------------------


@cli.command("collect")
@click.option(
    "--catalog",
    "catalogs",
    multiple=True,
    metavar="CATALOG",
    help=(
        "Unity Catalog catalog to scan.  Repeat to scan multiple catalogs.  "
        "When omitted every accessible catalog is scanned (can be slow)."
    ),
)
@click.option(
    "--schema",
    default=None,
    metavar="SCHEMA",
    help="Restrict scan to this schema within the specified catalog(s).",
)
@click.option(
    "--view",
    default=None,
    metavar="VIEW",
    help="Collect only this specific view name (requires --catalog and --schema).",
)
@click.option(
    "-o",
    "--output",
    "output_dir",
    default=".",
    show_default=True,
    type=click.Path(file_okay=False),
    help="Directory to write output YAML files.",
)
@click.option(
    "--max-depth",
    default=10,
    show_default=True,
    type=click.IntRange(min=0),
    help=(
        "Maximum upstream depth for lineage traversal.  "
        "0 is equivalent to --no-lineage."
    ),
)
@click.option(
    "--no-lineage",
    is_flag=True,
    default=False,
    help="Skip lineage collection.  Output only the parsed measure definitions.",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Enable verbose (DEBUG) logging.",
)
def collect(
    catalogs: tuple[str, ...],
    schema: Optional[str],
    view: Optional[str],
    output_dir: str,
    max_depth: int,
    no_lineage: bool,
    verbose: bool,
) -> None:
    """Discover metric views and write one YAML file per measure to OUTPUT.

    Files are named ``{catalog}.{schema}.{view}.{measure}.yaml``.

    \b
    Examples
    --------
    # Scan a single catalog/schema, collect lineage
    measurediff collect --catalog prod --schema finance -o ./out

    # Scan a specific view only, skip lineage (fast)
    measurediff collect --catalog prod --schema finance --view sales_metrics \\
        --no-lineage -o ./out

    # Scan multiple catalogs
    measurediff collect --catalog prod --catalog dev -o ./out
    """
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(levelname)s  %(name)s  %(message)s",
        stream=sys.stderr,
    )

    # Lazy imports — keep CLI startup fast and avoid hard-failing if
    # databricks-connect is not installed in a non-Databricks environment.
    try:
        from .collector import MetricViewCollector
        from .lineage import LineageCollector
        from . import serializer
    except ImportError as exc:
        raise click.ClickException(
            f"Missing dependency: {exc}\n"
            "Ensure databricks-connect and pyyaml are installed."
        ) from exc

    # Build SparkSession.
    spark = _get_spark()

    # Collect definitions.
    collector = MetricViewCollector(spark)

    # Normalise: if no catalogs given, pass None so collector scans all.
    catalog_list = list(catalogs) if catalogs else [
        None]  # type: ignore[list-item]

    all_defs = []
    for cat in catalog_list:
        all_defs.extend(
            collector.collect(catalog=cat, schema=schema, view=view)
        )

    if not all_defs:
        click.echo("No metric views found.", err=True)
        return

    # Optionally enrich with lineage.
    effective_depth = 0 if no_lineage else max_depth
    if effective_depth > 0:
        lc = LineageCollector(spark, max_depth=effective_depth)
        all_defs = [lc.enrich(d) for d in all_defs]

    # Write output — one file per measure.
    out_path = Path(output_dir)
    written: list[Path] = []
    for view_def in all_defs:
        written.extend(serializer.write_measures(view_def, out_path))

    # Summary.
    click.echo(f"\nWrote {len(written)} measure definition(s):\n")
    for p in written:
        click.echo(f"  {p}")
    click.echo()


# ---------------------------------------------------------------------------
# diff
# ---------------------------------------------------------------------------


@cli.command("diff")
@click.argument("file_a", type=click.Path(exists=True, dir_okay=False))
@click.argument("file_b", type=click.Path(exists=True, dir_okay=False))
def diff(file_a: str, file_b: str) -> None:
    """Compare two per-measure YAML files and show a visual diff.

    FILE_A and FILE_B must be YAML files produced by the ``collect`` command
    (one per measure, named ``{catalog}.{schema}.{view}.{measure}.yaml``).

    \b
    Example
    -------
    measurediff diff bravo.country_sales.Monthly_Sales.yaml \\
                     charlie.alphasales.MonthSales.yaml
    """
    from .loader import load_measure_yaml
    from .comparator import compare_measures
    from .display import render_diff

    try:
        view_a, measure_a = load_measure_yaml(file_a)
        view_b, measure_b = load_measure_yaml(file_b)
    except (ValueError, KeyError) as exc:
        raise click.ClickException(str(exc)) from exc

    comparison = compare_measures(view_a, measure_a, view_b, measure_b)
    render_diff(comparison)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_spark():
    """Return a SparkSession via databricks-connect.

    Raises :class:`click.ClickException` with a helpful message when
    databricks-connect is not configured.
    """
    try:
        # type: ignore[import]
        from databricks.connect import DatabricksSession

        return DatabricksSession.builder.getOrCreate()
    except Exception as exc:
        raise click.ClickException(
            "Could not create a Databricks SparkSession.\n"
            "Ensure databricks-connect is installed and configured:\n"
            "  https://docs.databricks.com/en/dev-tools/databricks-connect/index.html\n"
            f"\nUnderlying error: {exc}"
        ) from exc
