# measurediff

Collect comprehensive metric view measure definitions from Databricks Unity Catalog, enriched with recursive column lineage.

## Overview

`measurediff` discovers Databricks metric views, parses their YAML definitions, and traverses `system.access.column_lineage` to build a complete picture of how each measure's underlying columns flow from source tables through views and pipelines.

The output is a YAML file per metric view containing:
- The full measure and dimension definitions
- A recursive lineage tree for each column referenced in a measure expression
- Composed measure resolution (`MEASURE(x)` references tracked transitively)

## Installation

```bash
pip install measurediff
```

Requires `databricks-connect` to be installed and configured for live collection.

## Usage

```bash
# Collect all metric views in a catalog/schema
measurediff collect --catalog prod --schema finance -o ./definitions

# Collect a specific view
measurediff collect --catalog prod --schema finance --view sales_metrics -o ./definitions

# Fast mode — skip lineage traversal
measurediff collect --catalog prod --schema finance --no-lineage -o ./definitions

# Scan multiple catalogs
measurediff collect --catalog prod --catalog dev -o ./definitions
```

## Output Format

Each metric view is written as `{view_name}.yaml`:

```yaml
version: '1.1'
full_name: prod.finance.sales_metrics
source: prod.finance.fact_orders
comment: Sales KPIs
measures:
  - name: total_revenue
    expr: SUM(o_totalprice)
    lineage:
      - table: prod.finance.fact_orders
        column: o_totalprice
        type: METRIC_VIEW
        upstream:
          - table: prod.raw.orders
            column: price
            type: TABLE
  - name: order_count
    expr: COUNT(1)
    # lineage omitted — no column references
dimensions:
  - name: order_date
    expr: o_orderdate
```

## Lineage System Tables

Column lineage is sourced from `system.access.column_lineage`. This requires:
- Unity Catalog with lineage enabled on your Databricks workspace
- The `system.access` schema enabled in your metastore

See the [Databricks lineage system tables reference](https://docs.databricks.com/aws/en/admin/system-tables/lineage) for details.

## Requirements

- Python >= 3.10
- `databricks-connect == 18.0.0`
- `pyyaml >= 6.0`
- `sqlglot >= 25.0`
- `click >= 8.0`
