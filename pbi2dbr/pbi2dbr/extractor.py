"""PBIX semantic model extractor using pbixray."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .models import ColumnSchema, PbiMeasure, Relationship, SemanticModel, SourceTable

from pbixray import PBIXRay  # type: ignore[import]

# Patterns for resolving Unity Catalog references from Power Query M expressions
_UC_PATTERNS = [
    # DatabricksCatalog.Contents("catalog")[Schema][Table]
    re.compile(
        r'DatabricksCatalog\.Contents\(["\'](?P<catalog>[^"\']+)["\']\)'
        r'(?:\s*\{\s*\[Name\s*=\s*["\'](?P<schema>[^"\']+)["\']\]\s*\})?'
        r'(?:\s*\{\s*\[Name\s*=\s*["\'](?P<table>[^"\']+)["\']\]\s*\})?',
        re.IGNORECASE,
    ),
    # Catalog.Contents("catalog")
    re.compile(
        r'Catalog\.Contents\(["\'](?P<catalog>[^"\']+)["\']\)',
        re.IGNORECASE,
    ),
    # Value.NativeQuery(... , "SELECT ... FROM catalog.schema.table ...")
    re.compile(
        r'FROM\s+["`]?(?P<catalog>[a-zA-Z0-9_]+)["`]?\.'
        r'["`]?(?P<schema>[a-zA-Z0-9_]+)["`]?\.'
        r'["`]?(?P<table>[a-zA-Z0-9_]+)["`]?',
        re.IGNORECASE,
    ),
    # Direct table reference: catalog.schema.table_name in M
    re.compile(
        r'["\'](?P<catalog>[a-zA-Z0-9_]+)\.(?P<schema>[a-zA-Z0-9_]+)\.(?P<table>[a-zA-Z0-9_]+)["\']',
        re.IGNORECASE,
    ),
]

# Extracts individual Name= navigation steps from a let expression.
# Matches: {[Name="value"]} or {[Name = 'value']}
_NAME_NAV_RE = re.compile(
    r'\{\s*\[Name\s*=\s*["\']([^"\']+)["\']\]', re.IGNORECASE)

# Table.SelectRows(source, each <predicate>) — captures the predicate part.
_SELECT_ROWS_RE = re.compile(
    r'Table\.SelectRows\s*\([^,]+,\s*each\s+(.+?)\)',
    re.IGNORECASE | re.DOTALL,
)

# Simple equality/comparison predicates on record fields: [Column] op "value" or [Column] op number
_SIMPLE_PREDICATE_RE = re.compile(
    r'\[(?P<col>[^\]]+)\]\s*(?P<op>=|<>|<|<=|>|>=)\s*(?P<val>"[^"]*"|\d[\d.]*)',
)

# M operator → SQL operator
_M_OP_TO_SQL = {"=": "=", "<>": "!=",
                "<": "<", "<=": "<=", ">": ">", ">=": ">="}


class PbixExtractor:
    """Extract semantic model components from a PBIX file using pbixray.

    Usage::

        extractor = PbixExtractor("path/to/model.pbix")
        model = extractor.extract()
    """

    def __init__(self, pbix_path: str | Path) -> None:
        self._path = Path(pbix_path)
        if not self._path.exists():
            raise FileNotFoundError(f"PBIX file not found: {self._path}")
        self._ray = PBIXRay(str(self._path))

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def extract(
        self,
        source_catalog: Optional[str] = None,
        source_schema: Optional[str] = None,
    ) -> SemanticModel:
        """Extract the complete semantic model.

        Args:
            source_catalog: Fallback Unity Catalog catalog name when the table's
                Power Query M expression cannot be resolved automatically.
            source_schema: Fallback Unity Catalog schema name.

        Returns:
            A populated :class:`~pbi2dbr.models.SemanticModel`.
        """
        model = SemanticModel()

        # Tables
        try:
            tables_df = self._ray.tables
            if tables_df is not None and hasattr(tables_df, "__iter__"):
                # tables is a list of table names or a DataFrame with a Name column
                if hasattr(tables_df, "tolist"):
                    model.tables = [str(t)
                                    for t in tables_df.tolist() if str(t)]
                elif hasattr(tables_df, "iloc"):
                    col = "Name" if "Name" in tables_df.columns else tables_df.columns[0]
                    model.tables = [str(t)
                                    for t in tables_df[col].tolist() if str(t)]
                else:
                    model.tables = [str(t) for t in tables_df if str(t)]
        except Exception:  # noqa: BLE001
            model.tables = []

        # Column schema
        try:
            schema_df = self._ray.schema
            if schema_df is not None and len(schema_df) > 0:
                for _, row in schema_df.iterrows():
                    model.columns.append(
                        ColumnSchema(
                            table=str(
                                row.get("TableName", row.get("Table", ""))),
                            column=str(
                                row.get("ColumnName", row.get("Column", ""))),
                            data_type=str(
                                row.get("PandasDataType", row.get("DataType", "object"))),
                        )
                    )
        except Exception:  # noqa: BLE001
            pass

        # Ensure all schema tables are in model.tables
        schema_tables = {c.table for c in model.columns}
        for t in schema_tables:
            if t and t not in model.tables:
                model.tables.append(t)

        # DAX measures
        try:
            measures_df = self._ray.dax_measures
            if measures_df is not None and len(measures_df) > 0:
                for _, row in measures_df.iterrows():
                    model.measures.append(
                        PbiMeasure(
                            table=str(row.get("TableName", "")),
                            name=str(row.get("Name", "")),
                            expression=str(row.get("Expression", "")),
                            display_folder=str(row.get("DisplayFolder", "")),
                            description=str(row.get("Description", "")),
                        )
                    )
        except Exception:  # noqa: BLE001
            pass

        # Relationships (active only)
        try:
            rels_df = self._ray.relationships
            if rels_df is not None and len(rels_df) > 0:
                for _, row in rels_df.iterrows():
                    is_active = bool(row.get("IsActive", True))
                    model.relationships.append(
                        Relationship(
                            from_table=str(row.get("FromTableName", "")),
                            from_column=str(row.get("FromColumnName", "")),
                            to_table=str(row.get("ToTableName", "")),
                            to_column=str(row.get("ToColumnName", "")),
                            is_active=is_active,
                            cardinality=str(row.get("Cardinality", "")),
                        )
                    )
        except Exception:  # noqa: BLE001
            pass

        # Power Query M expressions for UC source resolution
        pq_map: dict[str, str] = {}
        try:
            pq_df = self._ray.power_query
            if pq_df is not None and len(pq_df) > 0:
                for _, row in pq_df.iterrows():
                    tname = str(row.get("TableName", ""))
                    expr = str(row.get("Expression", ""))
                    if tname:
                        pq_map[tname] = expr
        except Exception:  # noqa: BLE001
            pass

        # Resolve UC source for each table
        for table in model.tables:
            m_expr = pq_map.get(table)
            uc_ref = self._resolve_uc_ref(
                table, m_expr, source_catalog, source_schema
            )
            filter_expr = _extract_filter_expr(m_expr) if m_expr else None
            model.source_tables[table] = SourceTable(
                name=table,
                uc_ref=uc_ref,
                m_expression=m_expr,
                filter_expr=filter_expr,
            )

        return model

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_uc_ref(
        table_name: str,
        m_expr: Optional[str],
        default_catalog: Optional[str],
        default_schema: Optional[str],
    ) -> Optional[str]:
        """Try to extract a fully-qualified UC ``catalog.schema.table`` reference.

        First attempts multi-step ``let`` variable navigation (the most common
        Databricks connector pattern), then falls back to the static regex patterns.
        """
        if m_expr:
            # --- Improvement 1: multi-step let navigation ---
            # Collect all {[Name="..."]} navigation steps in document order.
            # In a typical Databricks M expression the steps are:
            #   Source = Databricks.Catalogs(...)
            #   step1 = Source{[Name="catalog"]}
            #   step2 = step1{[Name="schema"]}
            #   step3 = step2{[Name="table"]}
            nav_names = _NAME_NAV_RE.findall(m_expr)
            if len(nav_names) >= 3:
                catalog, schema, table = nav_names[0], nav_names[1], nav_names[2]
                return f"{catalog}.{schema}.{table}"
            if len(nav_names) == 2 and default_catalog:
                schema, table = nav_names[0], nav_names[1]
                return f"{default_catalog}.{schema}.{table}"
            if len(nav_names) == 1 and default_catalog and default_schema:
                return f"{default_catalog}.{default_schema}.{nav_names[0]}"

            # --- Fallback: static regex patterns ---
            for pattern in _UC_PATTERNS:
                m = pattern.search(m_expr)
                if m:
                    groups = m.groupdict()
                    catalog = groups.get("catalog")
                    schema = groups.get("schema")
                    table = groups.get("table")
                    if catalog and schema and table:
                        return f"{catalog}.{schema}.{table}"
                    if catalog and default_schema:
                        snake = _to_snake(table_name)
                        return f"{catalog}.{default_schema}.{snake}"

        # Fallback: construct from provided defaults
        if default_catalog and default_schema:
            return f"{default_catalog}.{default_schema}.{_to_snake(table_name)}"

        return None


def _extract_filter_expr(m_expr: str) -> Optional[str]:
    """Extract a SQL WHERE predicate from a ``Table.SelectRows`` call in an M expression.

    Only simple equality/comparison predicates on record fields are supported,
    e.g. ``Table.SelectRows(Source, each [Status] = "Active")``
    → ``Status = 'Active'``.

    Compound predicates joined by ``and``/``or`` are handled when every
    individual clause is simple.  Returns ``None`` when the predicate is
    too complex to translate safely.
    """
    m = _SELECT_ROWS_RE.search(m_expr)
    if not m:
        return None
    predicate_text = m.group(1).strip()

    # Split on M's logical operators (and / or), preserving the operator
    # so we can reconstruct the SQL expression.
    parts = re.split(r'\b(and|or)\b', predicate_text, flags=re.IGNORECASE)
    sql_parts: list[str] = []
    for part in parts:
        part = part.strip()
        if part.lower() in ("and", "or"):
            sql_parts.append(part.upper())
            continue
        cm = _SIMPLE_PREDICATE_RE.fullmatch(part)
        if not cm:
            # Complex clause — bail out rather than produce a wrong filter
            return None
        col = cm.group("col")
        op = _M_OP_TO_SQL[cm.group("op")]
        val = cm.group("val")
        # M string literals use double-quotes; SQL uses single-quotes
        if val.startswith('"') and val.endswith('"'):
            val = "'" + val[1:-1] + "'"
        sql_parts.append(f"{col} {op} {val}")

    return " ".join(sql_parts) if sql_parts else None


def _to_snake(name: str) -> str:
    """Convert a PascalCase or space-separated name to snake_case."""
    # Insert underscores before uppercase following lowercase
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    # Replace spaces, hyphens, dots with underscores
    s = re.sub(r"[\s\-\.]", "_", s)
    return s.lower()
