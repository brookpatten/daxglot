"""Internal data models for the pbi2dbr semantic layer."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Raw PBIX extraction models
# ---------------------------------------------------------------------------


@dataclass
class ColumnSchema:
    """Schema information for a single column."""

    table: str
    column: str
    # pandas dtype string, e.g. "object", "int64", "float64", "datetime64[ns]"
    data_type: str

    @property
    def is_date(self) -> bool:
        return "datetime" in self.data_type or "date" in self.data_type.lower()

    @property
    def is_numeric(self) -> bool:
        return any(t in self.data_type for t in ("int", "float", "decimal", "double"))


@dataclass
class Relationship:
    """An active relationship between two tables."""

    from_table: str
    from_column: str
    to_table: str
    to_column: str
    is_active: bool = True
    cardinality: str = ""  # e.g. "ManyToOne", "OneToMany", "OneToOne"


@dataclass
class PbiMeasure:
    """A DAX measure as extracted from the PBIX file."""

    table: str
    name: str
    expression: str       # raw DAX text, may contain leading '='
    display_folder: str = ""
    description: str = ""


@dataclass
class SourceTable:
    """A table in the semantic model with its Unity Catalog reference."""

    name: str
    uc_ref: Optional[str] = None          # catalog.schema.table if resolvable
    is_calculated: bool = False           # True for DAX calculated tables
    m_expression: Optional[str] = None   # raw Power Query M expression
    # SQL WHERE predicate extracted from Table.SelectRows
    filter_expr: Optional[str] = None
    # Full SQL query extracted from Value.NativeQuery (takes precedence over uc_ref)
    source_sql: Optional[str] = None


@dataclass
class SemanticModel:
    """Complete extracted semantic model from a PBIX file."""

    tables: list[str] = field(default_factory=list)
    columns: list[ColumnSchema] = field(default_factory=list)
    measures: list[PbiMeasure] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    source_tables: dict[str, SourceTable] = field(default_factory=dict)

    def columns_for(self, table: str) -> list[ColumnSchema]:
        return [c for c in self.columns if c.table == table]

    def measures_for(self, table: str) -> list[PbiMeasure]:
        return [m for m in self.measures if m.table == table]

    def outgoing_relationships(self, table: str) -> list[Relationship]:
        """Relationships where ``table`` is the FK (many) side."""
        return [r for r in self.relationships if r.from_table == table and r.is_active]

    def incoming_relationships(self, table: str) -> list[Relationship]:
        """Relationships where ``table`` is the PK (one) side."""
        return [r for r in self.relationships if r.to_table == table and r.is_active]


# ---------------------------------------------------------------------------
# Analyzed / translated metric view models
# ---------------------------------------------------------------------------


@dataclass
class Join:
    """A join from a fact (or dimension) table to another table."""

    name: str             # alias used in expressions, e.g. "customer"
    source_uc_ref: str    # fully-qualified UC table reference
    # e.g. "source.customer_id = customer.id"
    on_clause: Optional[str] = None
    using_cols: list[str] = field(default_factory=list)
    nested_joins: list[Join] = field(default_factory=list)


@dataclass
class Dimension:
    """A dimension defined in a metric view."""

    name: str
    expr: str
    comment: Optional[str] = None
    display_name: Optional[str] = None


@dataclass
class Measure:
    """A measure defined in a metric view."""

    name: str
    expr: str                            # SQL aggregate expression
    comment: Optional[str] = None
    display_name: Optional[str] = None
    # [{order, range, semiadditive}]
    window: list[dict] = field(default_factory=list)
    is_approximate: bool = False
    original_dax: Optional[str] = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class MetricViewSpec:
    """Complete specification for a single Databricks metric view."""

    name: str                    # view name (without catalog/schema prefix)
    source: str                  # UC table or SQL query
    comment: Optional[str] = None
    filter: Optional[str] = None
    dimensions: list[Dimension] = field(default_factory=list)
    measures: list[Measure] = field(default_factory=list)
    joins: list[Join] = field(default_factory=list)
    fact_table: Optional[str] = None


@dataclass
class FactTable:
    """An analyzed fact table ready for metric view generation."""

    name: str
    source_table: SourceTable
    dimensions: list[Dimension] = field(default_factory=list)
    measures: list[PbiMeasure] = field(default_factory=list)
    joins: list[Join] = field(default_factory=list)

    def should_skip(
        self,
        skip_calculated: bool = True,
        skip_no_uc_ref: bool = False,
        skip_system_tables: bool = True,
        require_measures_or_numeric: bool = False,
        columns: Optional[list] = None,
    ) -> tuple[bool, str]:
        """Return (True, reason) when this table should not generate a metric view.

        Args:
            skip_calculated: Skip DAX-calculated tables (no UC backing storage).
            skip_no_uc_ref: Skip tables whose Unity Catalog source cannot be resolved.
            skip_system_tables: Skip Power BI auto-generated tables
                (DateTableTemplate, LocalDateTable_*, Measures holding table, etc.).
            require_measures_or_numeric: Skip tables that have neither DAX measures
                nor any numeric columns.
            columns: List of :class:`ColumnSchema` for this table (used when
                ``require_measures_or_numeric=True``).
        """
        if skip_calculated and self.source_table.is_calculated:
            return True, f"'{self.name}' is a DAX calculated table with no UC backing storage"

        if skip_no_uc_ref and self.source_table.uc_ref is None:
            return True, f"'{self.name}' has no resolvable Unity Catalog source reference"

        if skip_system_tables and _is_system_table(self.name):
            return True, f"'{self.name}' is a Power BI system/auto-generated table"

        if require_measures_or_numeric:
            has_measures = bool(self.measures)
            has_numeric = any(c.is_numeric for c in (columns or []))
            if not has_measures and not has_numeric:
                return True, (
                    f"'{self.name}' has no DAX measures and no numeric columns"
                    " — not meaningful as a metric view"
                )

        return False, ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Power BI auto-generated table name patterns that should never become metric views
_SYSTEM_TABLE_PATTERNS = re.compile(
    r"^("
    r"DateTableTemplate"           # date-intelligence template table
    r"|LocalDateTable_"            # per-column auto date table
    r"|DateTable_"                 # legacy auto date table prefix
    r"|Measures"                   # holding table for disconnected measures
    # internal/hidden tables (double-underscore prefix)
    r"|__"
    r")",
    re.IGNORECASE,
)


def _is_system_table(name: str) -> bool:
    """Return ``True`` when *name* matches a Power BI system table pattern."""
    return bool(_SYSTEM_TABLE_PATTERNS.match(name))
