"""Metric view YAML and SQL DDL generator."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import yaml

from .models import Dimension, Join, Measure, MetricViewSpec
from .translator import translate_fact_table
from .models import FactTable


class MetricViewGenerator:
    """Generate Databricks metric view YAML and SQL DDL from a :class:`~pbi2dbr.models.FactTable`.

    Usage::

        gen = MetricViewGenerator()
        spec = gen.build_spec(fact_table, target_catalog="dev", target_schema="pbi")
        yaml_text = gen.to_yaml(spec)
        sql_text = gen.to_sql_ddl(spec, catalog="dev", schema="pbi")
        gen.write(spec, output_dir="/tmp/output", catalog="dev", schema="pbi")
    """

    def __init__(self, dialect: str = "databricks") -> None:
        self._dialect = dialect

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def build_spec(
        self,
        fact: FactTable,
        target_catalog: str = "",
        target_schema: str = "",
        view_name_prefix: str = "",
    ) -> MetricViewSpec:
        """Build a :class:`~pbi2dbr.models.MetricViewSpec` from an analysed FactTable.

        Any warnings from DAX translation are preserved on each :class:`~pbi2dbr.models.Measure`.
        """
        source = fact.source_table.uc_ref or fact.name

        # Translate all DAX measures
        measures = translate_fact_table(fact, dialect=self._dialect)

        # Clean up view name
        view_name = _clean_name(f"{view_name_prefix}{fact.name}")

        return MetricViewSpec(
            name=view_name,
            source=source,
            comment=f"Metric view generated from PowerBI table '{fact.name}'",
            dimensions=fact.dimensions,
            measures=measures,
            joins=fact.joins,
            fact_table=fact.name,
        )

    def to_yaml(self, spec: MetricViewSpec) -> str:
        """Serialise a MetricViewSpec to a YAML string (version 1.1)."""
        doc: dict = {"version": "1.1"}
        if spec.comment:
            doc["comment"] = spec.comment
        doc["source"] = spec.source
        if spec.filter:
            doc["filter"] = spec.filter

        if spec.joins:
            doc["joins"] = [_join_to_dict(j) for j in spec.joins]

        if spec.dimensions:
            doc["dimensions"] = [_dim_to_dict(d) for d in spec.dimensions]

        if spec.measures:
            doc["measures"] = [_measure_to_dict(m) for m in spec.measures]

        return yaml.dump(
            doc,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            width=120,
        )

    def to_sql_ddl(
        self,
        spec: MetricViewSpec,
        catalog: str = "",
        schema: str = "",
    ) -> str:
        """Wrap YAML in a CREATE OR REPLACE VIEW … WITH METRICS … AS $$ … $$ statement."""
        yaml_body = self.to_yaml(spec)

        if catalog and schema:
            fqn = f"`{catalog}`.`{schema}`.`{spec.name}`"
        elif schema:
            fqn = f"`{schema}`.`{spec.name}`"
        else:
            fqn = f"`{spec.name}`"

        # Any approximate measures get a warning header comment
        approx = [m for m in spec.measures if m.is_approximate]
        header_comment = ""
        if approx:
            names = ", ".join(m.name for m in approx)
            header_comment = (
                f"-- WARNING: The following measures use best-effort DAX translation\n"
                f"-- and should be reviewed: {names}\n"
            )

        return (
            f"{header_comment}"
            f"CREATE OR REPLACE VIEW {fqn}\n"
            f"WITH METRICS\n"
            f"LANGUAGE YAML\n"
            f"AS\n"
            f"$$\n"
            f"{yaml_body}"
            f"$$\n"
        )

    def write(
        self,
        spec: MetricViewSpec,
        output_dir: str | Path,
        catalog: str = "",
        schema: str = "",
    ) -> tuple[Path, Path]:
        """Write YAML and SQL DDL files to *output_dir*.

        Returns:
            Tuple of (yaml_path, sql_path).
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        yaml_path = out / f"{spec.name}.yaml"
        sql_path = out / f"{spec.name}_mv.sql"

        yaml_path.write_text(self.to_yaml(spec), encoding="utf-8")
        sql_path.write_text(self.to_sql_ddl(
            spec, catalog, schema), encoding="utf-8")

        return yaml_path, sql_path


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _join_to_dict(join: Join) -> dict:
    d: dict = {"name": join.name, "source": join.source_uc_ref}
    if join.on_clause:
        d["on"] = join.on_clause
    elif join.using_cols:
        d["using"] = join.using_cols
    if join.nested_joins:
        d["joins"] = [_join_to_dict(nj) for nj in join.nested_joins]
    return d


def _dim_to_dict(dim: Dimension) -> dict:
    d: dict = {"name": dim.name, "expr": _safe_expr(dim.expr)}
    if dim.comment:
        d["comment"] = dim.comment
    if dim.display_name and dim.display_name != dim.name:
        d["display_name"] = dim.display_name
    return d


def _measure_to_dict(m: Measure) -> dict:
    d: dict = {"name": m.name, "expr": _safe_expr(m.expr)}
    if m.comment:
        d["comment"] = m.comment
    if m.display_name and m.display_name != m.name:
        d["display_name"] = m.display_name
    if m.window:
        d["window"] = m.window
    return d


def _safe_expr(expr: str) -> str:
    """Return the expression string, quoting it if it contains YAML-unsafe chars."""
    if not expr:
        return expr
    # Expressions containing colons must be double-quoted (YAML interprets : as key sep)
    if ":" in expr or expr.startswith("`") or "\n" in expr:
        # Use YAML block literal style for multi-line
        if "\n" in expr:
            return expr  # yaml.dump handles this via block literal when the value is set
        # Single-line with colons — return as-is and let PyYAML quote it
        return expr
    return expr


def _clean_name(name: str) -> str:
    """Clean a name to be a valid identifier (snake_case, no special chars)."""
    s = re.sub(r"[\s\-\.]+", "_", name)
    s = re.sub(r"[^a-zA-Z0-9_]", "", s)
    s = re.sub(r"_+", "_", s)
    return s.strip("_").lower()
