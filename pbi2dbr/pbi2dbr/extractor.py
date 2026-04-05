"""PBIX semantic model extractor using pbixray."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .models import ColumnSchema, PbiMeasure, Relationship, SemanticModel, SourceTable

from pbixray import PBIXRay  # type: ignore[import]
from powermglot import MSourceInfo, parse_m_source

from . import console

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

# Alternative navigation: {[Item="value"][Kind="Table"]} (Databricks UI style)
_ITEM_NAV_RE = re.compile(
    r'\{\s*\[Item\s*=\s*["\']([^"\']+)["\'][^}]*Kind\s*=\s*["\']Table["\']',
    re.IGNORECASE,
)

# Extract catalog from Databricks connector options: [Catalog="..."]
_DATABRICKS_CATALOG_OPT_RE = re.compile(
    r'(?:Databricks\.Catalogs|Databricks\.Query|AzureDatabricks\.Contents)'
    r'\s*\([^)]*\[Catalog\s*=\s*["\'](?P<catalog>[^"\']+)["\']',
    re.IGNORECASE,
)

# Sql.Database("server", "database") — second arg is catalog/database name
_SQL_DATABASE_RE = re.compile(
    r'Sql\.Database\s*\(["\'][^"\']*["\'],\s*["\'](?P<catalog>[^"\']+)["\']',
    re.IGNORECASE,
)

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

# Value.NativeQuery(connection, "SQL text" [, params [, options]])
# Captures the SQL string literal (first string arg after the connection arg).
# Handles both single-step and multi-step let bindings.
_NATIVE_QUERY_RE = re.compile(
    r'Value\.NativeQuery\s*\([^,]+,\s*"((?:[^"\\]|\\.|"")*)"',
    re.IGNORECASE | re.DOTALL,
)


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
                            format_string=str(
                                row.get("FormatString", "") or ""),
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

        # Detect calculated tables (defined purely in DAX, no M expression)
        calculated_tables: set[str] = set()
        try:
            calc_df = self._ray.calculated_tables
            if calc_df is not None and len(calc_df) > 0:
                col = "TableName" if "TableName" in calc_df.columns else calc_df.columns[0]
                for t in calc_df[col].tolist():
                    if t:
                        calculated_tables.add(str(t))
        except Exception:  # noqa: BLE001
            pass
        # Fallback: tables that appear in model.tables but have no M expression
        # and no rows in the relationships/schema are NOT necessarily calculated,
        # so we only rely on the explicit calculated_tables attribute above.

        # Resolve UC source for each table
        for table in model.tables:
            m_expr = pq_map.get(table)
            uc_ref = self._resolve_uc_ref(
                table, m_expr, source_catalog, source_schema
            )
            filter_expr = _extract_filter_expr(m_expr) if m_expr else None
            source_sql = _extract_native_query_sql(m_expr) if m_expr else None
            model.source_tables[table] = SourceTable(
                name=table,
                uc_ref=uc_ref,
                is_calculated=table in calculated_tables,
                m_expression=m_expr,
                filter_expr=filter_expr,
                source_sql=source_sql,
            )
            if m_expr:
                console.show_m_resolution(
                    table, uc_ref, filter_expr, source_sql)

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

        Resolution order:
        1. **powermglot** M parser — handles ``let``-chain navigation and
           connector options (Databricks, Sql.Database, etc.).
        2. Regex fallback for patterns the powermglot parser cannot handle
           (e.g. ``{[Item=…][Kind=Table]}`` navigation style).
        3. Default catalog/schema + snake_case table name.
        """
        if m_expr:
            # 1. powermglot — primary resolution path
            info: MSourceInfo = parse_m_source(m_expr)
            if info.source_ref:
                parts = info.source_ref.split(".")
                if len(parts) >= 3:
                    return info.source_ref
                if len(parts) == 2 and default_catalog:
                    return f"{default_catalog}.{info.source_ref}"
                if len(parts) == 1 and default_catalog and default_schema:
                    return f"{default_catalog}.{default_schema}.{info.source_ref}"

            # 2. Regex fallback (handles patterns powermglot cannot parse)
            connector_catalog = _extract_connector_catalog(m_expr)
            effective_catalog = connector_catalog or default_catalog

            nav_names = _NAME_NAV_RE.findall(m_expr)
            if not nav_names:
                nav_names = _ITEM_NAV_RE.findall(m_expr)

            if len(nav_names) >= 3:
                return f"{nav_names[0]}.{nav_names[1]}.{nav_names[2]}"
            if len(nav_names) == 2 and effective_catalog:
                return f"{effective_catalog}.{nav_names[0]}.{nav_names[1]}"
            if len(nav_names) == 1 and effective_catalog and default_schema:
                return f"{effective_catalog}.{default_schema}.{nav_names[0]}"

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

        # 3. Fallback: construct from provided defaults
        if default_catalog and default_schema:
            return f"{default_catalog}.{default_schema}.{_to_snake(table_name)}"

        return None


def _extract_connector_catalog(m_expr: str) -> Optional[str]:
    """Extract a catalog name directly from a Databricks or Sql.Database connector call."""
    m = _DATABRICKS_CATALOG_OPT_RE.search(m_expr)
    if m:
        return m.group("catalog")
    m = _SQL_DATABASE_RE.search(m_expr)
    if m:
        return m.group("catalog")
    return None


def _extract_filter_expr(m_expr: str) -> Optional[str]:
    """Extract a SQL WHERE predicate from a ``Table.SelectRows`` call in an M expression.

    Tries the powermglot parser first; falls back to a regex-based approach
    for M expressions that powermglot cannot parse.

    Returns ``None`` when there is no ``Table.SelectRows`` call or the
    predicate is too complex to translate safely.
    """
    # 1. powermglot — handles nested let chains and complex expressions
    info: MSourceInfo = parse_m_source(m_expr)
    if info.filter_sql is not None:
        return info.filter_sql

    # 2. Regex fallback
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


def _extract_native_query_sql(m_expr: str) -> Optional[str]:
    """Extract the SQL text from a ``Value.NativeQuery`` call in an M expression.

    Tries the powermglot parser first; falls back to a regex-based approach.

    Returns the SQL string normalised to strip M-style escaped double-quote
    pairs (``""`` → ``"``).  Returns ``None`` if no ``Value.NativeQuery``
    pattern is found.

    Examples::

        let
            src = Databricks.Catalogs("host"),
            q = Value.NativeQuery(src, "SELECT o.id, c.region
                FROM prod.pbi.orders o
                JOIN prod.pbi.customers c ON o.cust_id = c.id")
        in q

        → "SELECT o.id, c.region\\n    FROM prod.pbi.orders o\\n    ..."
    """
    # 1. powermglot — handles let-chain bindings natively
    info: MSourceInfo = parse_m_source(m_expr)
    if info.native_sql is not None:
        return info.native_sql

    # 2. Regex fallback
    m = _NATIVE_QUERY_RE.search(m_expr)
    if not m:
        return None
    sql = m.group(1)
    # Unescape M double-quote pairs ("" → ") which can appear in SQL strings
    sql = sql.replace('""', '"')
    # Normalise leading/trailing whitespace
    sql = sql.strip()
    return sql if sql else None
