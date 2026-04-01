"""Parse Databricks metric view DDL into :class:`~measurediff.models.MetricViewDefinition`.

This module is intentionally free of Spark / databricks-connect dependencies so
it can be exercised in unit tests without a live cluster.

Key entry points
----------------
- :func:`is_metric_view` — quick check on a DDL string.
- :func:`parse_metric_view` — full parse of DDL → :class:`MetricViewDefinition`.
- :func:`extract_column_refs` — extract ``(table_full_name, column)`` pairs from
  a SQL expression using sqlglot.
"""

from __future__ import annotations

import re
from typing import Optional

import sqlglot
import sqlglot.expressions as exp
import yaml

from .models import (
    DimensionDefinition,
    JoinDefinition,
    MeasureDefinition,
    MetricViewDefinition,
    WindowSpec,
)

# Matches the $$ ... $$ body of a metric view DDL.
_DDL_YAML_RE = re.compile(r"\$\$(.*?)\$\$", re.DOTALL)

# Matches MEASURE(identifier) references in an expression.
_MEASURE_REF_RE = re.compile(r"\bMEASURE\((\w+)\)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def is_metric_view(ddl: str) -> bool:
    """Return True if *ddl* looks like a Databricks metric view DDL statement.

    Checks for both ``WITH METRICS`` and ``LANGUAGE YAML`` markers, which are
    always present in metric view CREATE statements regardless of formatting.
    """
    upper = ddl.upper()
    return "WITH METRICS" in upper and "LANGUAGE YAML" in upper


def extract_yaml_from_ddl(ddl: str) -> Optional[str]:
    """Extract the raw YAML body from a metric view DDL string.

    Returns the YAML text between the ``$$`` delimiters, or *None* if the
    delimiters are not found.
    """
    match = _DDL_YAML_RE.search(ddl)
    if not match:
        return None
    return match.group(1).strip()


def parse_metric_view(full_name: str, ddl: str) -> MetricViewDefinition:
    """Parse a complete metric view DDL string into a :class:`MetricViewDefinition`.

    The returned definition has empty ``lineage`` tuples on every
    :class:`~measurediff.models.MeasureDefinition`; lineage is populated
    separately by :mod:`measurediff.lineage`.

    Args:
        full_name: Three-part Unity Catalog name ``catalog.schema.view``.
        ddl:       Raw DDL string from ``SHOW CREATE TABLE``.

    Raises:
        ValueError: If no ``$$…$$`` YAML body can be found in *ddl*.
        yaml.YAMLError: If the embedded YAML is malformed.
    """
    raw_yaml = extract_yaml_from_ddl(ddl)
    if raw_yaml is None:
        raise ValueError(
            f"No $$…$$ YAML body found in DDL for {full_name!r}. "
            "Is this actually a metric view?"
        )

    doc = yaml.safe_load(raw_yaml)

    version = str(doc.get("version", "1.1"))
    comment = doc.get("comment") or None
    source: str = doc.get("source", "")
    filter_expr: Optional[str] = doc.get("filter") or None

    # --- joins ---
    joins = tuple(_parse_join(j) for j in (doc.get("joins") or []))

    # Build alias → full source name map for column-ref resolution.
    # The reserved alias "source" resolves to the metric view's own source.
    alias_map: dict[str, str] = {"source": source}
    for j in joins:
        alias_map[j.name] = j.source

    # --- dimensions ---
    dimensions = tuple(
        _parse_dimension(d) for d in (doc.get("dimensions") or [])
    )

    # --- measures ---
    measures = tuple(
        _parse_measure(m, source, alias_map) for m in (doc.get("measures") or [])
    )

    return MetricViewDefinition(
        full_name=full_name,
        source=source,
        version=version,
        comment=comment,
        filter=filter_expr,
        source_yaml=raw_yaml,
        joins=joins,
        dimensions=dimensions,
        measures=measures,
    )


def extract_column_refs(
    expr: str,
    source_table: str,
    alias_map: Optional[dict[str, str]] = None,
) -> list[tuple[str, str]]:
    """Return a deduplicated list of ``(table_full_name, column_name)`` pairs.

    Uses sqlglot to parse *expr* and walk all :class:`sqlglot.expressions.Column`
    nodes.  Table aliases are resolved using *alias_map* (which should map alias
    → three-part name) falling back to *source_table* when no qualifier is present.

    ``MEASURE(x)`` references are *not* column references and are ignored here;
    use :func:`extract_measure_refs` for those.

    Args:
        expr:         SQL expression string (e.g. ``"SUM(o_totalprice)"``).
        source_table: Three-part name of the metric view's primary source.
        alias_map:    Map from join alias (or ``"source"``) to three-part name.
    """
    resolved: dict[str, str] = alias_map or {}

    # Strip MEASURE(...) calls to avoid confusing the SQL parser.
    cleaned = _MEASURE_REF_RE.sub("1", expr)

    try:
        tree = sqlglot.parse_one(
            cleaned, dialect="databricks", error_level=sqlglot.ErrorLevel.IGNORE)
    except Exception:
        return []

    if tree is None:
        return []

    seen: dict[tuple[str, str], None] = {}  # ordered dedup
    for col in tree.find_all(exp.Column):
        col_name: str = col.name
        table_alias: Optional[str] = col.table or None

        if table_alias:
            table_full = resolved.get(table_alias, table_alias)
        else:
            table_full = source_table

        if col_name:
            seen[(table_full, col_name)] = None

    return list(seen.keys())


def extract_measure_refs(expr: str) -> list[str]:
    """Return deduplicated list of measure names referenced via ``MEASURE(name)``."""
    return list(dict.fromkeys(_MEASURE_REF_RE.findall(expr)))


# ---------------------------------------------------------------------------
# Private parse helpers
# ---------------------------------------------------------------------------


def _parse_join(raw: dict) -> JoinDefinition:
    using_raw = raw.get("using")
    using = tuple(using_raw) if using_raw else None
    # PyYAML (YAML 1.1) parses unquoted `on:` as boolean True.
    # The generated DDL quotes it as `'on':` (string key), but handle both.
    on_value = raw.get("on") or raw.get(True) or None
    return JoinDefinition(
        name=raw["name"],
        source=raw["source"],
        on=on_value,
        using=using,
    )


def _parse_dimension(raw: dict) -> DimensionDefinition:
    return DimensionDefinition(
        name=raw["name"],
        expr=str(raw.get("expr", "")),
        comment=raw.get("comment") or None,
        display_name=raw.get("display_name") or None,
    )


def _parse_measure(
    raw: dict, source_table: str, alias_map: dict[str, str]
) -> MeasureDefinition:
    expr = str(raw.get("expr", ""))

    # Window specs
    window_raw = raw.get("window") or []
    window = tuple(
        WindowSpec(
            order=w["order"],
            range=w["range"],
            semiadditive=w.get("semiadditive") or None,
        )
        for w in window_raw
    )

    # Composed-measure references (resolved later in lineage collection)
    referenced_measures = tuple(extract_measure_refs(expr))

    return MeasureDefinition(
        name=raw["name"],
        expr=expr,
        comment=raw.get("comment") or None,
        display_name=raw.get("display_name") or None,
        window=window,
        lineage=(),  # populated by lineage.LineageCollector.enrich()
        referenced_measures=referenced_measures,
    )
