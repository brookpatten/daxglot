"""Discover and fetch Databricks metric view definitions via databricks-connect.

This module uses a live :class:`pyspark.sql.SparkSession` (provided by
``databricks-connect``) to:

1. Enumerate catalogs/schemas/views in Unity Catalog.
2. Fetch each view's DDL via ``SHOW CREATE TABLE``.
3. Filter to metric views using :func:`~measurediff.extractor.is_metric_view`.
4. Parse DDL into :class:`~measurediff.models.MetricViewDefinition` instances.

Lineage enrichment is handled separately by :mod:`measurediff.lineage`.
"""

from __future__ import annotations

import logging
from typing import Optional

from .extractor import parse_metric_view
from .models import MetricViewDefinition

logger = logging.getLogger(__name__)


class MetricViewCollector:
    """Discover and parse Databricks metric views.

    Args:
        spark: A live :class:`pyspark.sql.SparkSession`.  Pass the result of
               ``databricks.connect.DatabricksSession.builder.getOrCreate()``.
    """

    def __init__(self, spark) -> None:  # spark: pyspark.sql.SparkSession
        self._spark = spark

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def collect(
        self,
        catalog: Optional[str] = None,
        schema: Optional[str] = None,
        view: Optional[str] = None,
    ) -> list[MetricViewDefinition]:
        """Return parsed :class:`~measurediff.models.MetricViewDefinition` objects.

        Args:
            catalog: Unity Catalog catalog name.  When *None* every accessible
                     catalog is scanned (can be slow).
            schema:  Schema name within *catalog* to restrict search.
            view:    Specific view name.  When provided only that view is fetched.
        """
        names = self.discover(catalog=catalog, schema=schema, view=view)
        results: list[MetricViewDefinition] = []
        for full_name in names:
            try:
                ddl = self.get_ddl(full_name)
                results.append(parse_metric_view(full_name, ddl))
            except Exception as exc:
                logger.warning("Skipping %s — parse error: %s", full_name, exc)
        return results

    def discover(
        self,
        catalog: Optional[str] = None,
        schema: Optional[str] = None,
        view: Optional[str] = None,
    ) -> list[str]:
        """Return three-part names of all metric views matching the filters.

        Queries ``information_schema.tables`` with ``table_type = 'METRIC_VIEW'``
        directly — no DDL pre-fetch needed for discovery.  When *view* is given
        the result is a single three-part name constructed from the provided
        catalog/schema/view (requires all three to be non-None).

        Args:
            catalog: Restrict search to this catalog.
            schema:  Restrict search to this schema within *catalog*.
            view:    Return only this specific view name.
        """
        # Fast path: caller specified an exact three-part name.
        if view:
            if not catalog or not schema:
                raise ValueError(
                    "--view requires both --catalog and --schema to be specified."
                )
            return [f"{catalog}.{schema}.{view}"]

        catalogs = [catalog] if catalog else self._list_catalogs()
        names: list[str] = []
        for cat in catalogs:
            names.extend(self._list_metric_views(cat, schema))
        return names

    def get_ddl(self, full_name: str) -> str:
        """Fetch the metric view definition via ``DESCRIBE TABLE EXTENDED``.

        ``DESCRIBE TABLE EXTENDED`` returns a multi-row key/value result set.
        The row where ``col_name = 'View Text'`` contains the raw YAML body
        (the content between ``$$…$$`` in the original DDL).

        The returned string is wrapped in synthetic ``$$…$$`` delimiters so
        that :func:`~measurediff.extractor.extract_yaml_from_ddl` and
        :func:`~measurediff.extractor.is_metric_view` work unchanged.

        Args:
            full_name: Three-part Unity Catalog name ``catalog.schema.view``.

        Returns:
            Synthetic DDL string containing ``WITH METRICS LANGUAGE YAML`` and
            the YAML body wrapped in ``$$…$$``.

        Raises:
            RuntimeError: If the ``View Text`` row cannot be found.
        """
        quoted = _quote_full_name(full_name)
        rows = self._spark.sql(f"DESCRIBE TABLE EXTENDED {quoted}").collect()

        view_text: Optional[str] = None
        for row in rows:
            # col_name is the first field; data_type is the second (value).
            if str(row[0]).strip() == "View Text":
                view_text = str(row[1]).strip()
                break

        if view_text is None:
            raise RuntimeError(
                f"'View Text' row not found in DESCRIBE TABLE EXTENDED for {full_name!r}"
            )

        # Wrap in synthetic DDL markers so callers can use extract_yaml_from_ddl().
        return f"WITH METRICS\nLANGUAGE YAML\nAS\n$$\n{view_text}\n$$"

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _list_catalogs(self) -> list[str]:
        """Return all catalogs visible to the current principal."""
        rows = self._spark.sql("SHOW CATALOGS").collect()
        return [r[0] for r in rows if not str(r[0]).startswith("__")]

    def _list_metric_views(
        self, catalog: str, schema: Optional[str]
    ) -> list[str]:
        """Query ``information_schema.tables`` for ``METRIC_VIEW`` objects.

        Uses ``table_type = 'METRIC_VIEW'`` — the exact value Unity Catalog
        stores for metric views, confirmed from
        ``select * from system.information_schema.tables where table_type='METRIC_VIEW'``.
        """
        schema_filter = (
            f"AND table_schema = '{_escape_sql_string(schema)}'"
            if schema
            else ""
        )
        try:
            rows = self._spark.sql(
                f"SELECT table_catalog, table_schema, table_name "
                f"FROM `{catalog}`.information_schema.tables "
                f"WHERE table_type = 'METRIC_VIEW' "
                f"{schema_filter}"
            ).collect()
            return [f"{r[0]}.{r[1]}.{r[2]}" for r in rows]
        except Exception as exc:
            logger.debug(
                "Cannot list metric views in catalog %s: %s", catalog, exc
            )
            return []


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _quote_full_name(full_name: str) -> str:
    """Wrap each part of a three-part name in backticks.

    Handles names already quoted or names with fewer/more than 3 parts
    gracefully by quoting each dot-separated segment.
    """
    parts = [p.strip("`") for p in full_name.split(".")]
    return ".".join(f"`{p}`" for p in parts)


def _escape_sql_string(value: str) -> str:
    """Escape single quotes in a string value for inline SQL."""
    return value.replace("'", "''")
