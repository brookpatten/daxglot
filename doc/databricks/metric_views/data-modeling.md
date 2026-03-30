---
layout: Conceptual
title: Model metric view data - Azure Databricks | Microsoft Learn
canonicalUrl: https://learn.microsoft.com/en-us/azure/databricks/metric-views/data-modeling/
breadcrumb_path: /azure/databricks/breadcrumb/toc.json
feedback_system: Standard
feedback_product_url: https://feedback.azure.com/d365community/forum/2efba7dc-ef24-ec11-b6e6-000d3a4f0da0
uhfHeaderId: azure
ms.topic: concept-article
ms.service: azure-databricks
ms.reviewer: jasonh
ms.custom: databricksmigration
ms.author: saperla
author: mssaperla
ms.date: 2026-03-18T00:00:00.0000000Z
description: Learn how to model data with Unity Catalog metric views.
locale: en-us
document_id: eb3bb1b6-3049-8493-3629-47fcf347ac45
document_version_independent_id: eb3bb1b6-3049-8493-3629-47fcf347ac45
updated_at: 2026-03-23T18:02:00.0000000Z
original_content_git_url: https://github.com/MicrosoftDocs/databricks-pr/blob/live/databricks/metric-views/data-modeling/index.md
gitcommit: https://github.com/MicrosoftDocs/databricks-pr/blob/fdaf586380a44520a5b0c845439f9c0994d03ce0/databricks/metric-views/data-modeling/index.md
git_commit_id: fdaf586380a44520a5b0c845439f9c0994d03ce0
site_name: Docs
depot_name: MSDN.databricks
page_type: conceptual
toc_rel: ../../toc.json
feedback_help_link_type: ''
feedback_help_link_url: ''
word_count: 1426
asset_id: metric-views/data-modeling/index
moniker_range_name: 
monikers: []
item_type: Content
source_path: databricks/metric-views/data-modeling/index.md
cmProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/cbe4ca68-43ac-4375-aba5-5945a6394c20
- https://authoring-docs-microsoft.poolparty.biz/devrel/8b896464-3b7d-4e1f-84b0-9bb45aeb5f64
- https://authoring-docs-microsoft.poolparty.biz/devrel/545d40c6-c50c-444b-b422-1c707eeab28e
spProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/ced846cc-6a3c-4c8f-9dfb-3de0e90e2742
- https://authoring-docs-microsoft.poolparty.biz/devrel/b1d2d671-9549-46e8-918c-24349120dbf5
- https://authoring-docs-microsoft.poolparty.biz/devrel/b908d601-32e8-445a-b044-a507b5d1689e
platformId: a473fd66-33c0-3e69-f1f5-8ee077500579
---

# Model metric view data - Azure Databricks | Microsoft Learn

This page describes how to model metric views and best practices for working with them.

Metric views help to create a semantic layer for your data, transforming raw tables into standardized, business-friendly metrics. They define what to measure, how to aggregate it, and how to segment it, ensuring that every user across the organization reports the same number for the same Key Performance Indicator (KPI). The goal is to create a single source of truth for business metrics.

By modeling your data as metric views, you abstract away complex SQL, table structures, and data quality issues, allowing analysts to focus purely on analysis.

## Core components

Modeling a metric view involves defining the following elements over your source data:

| Component | Description | Example |
| --- | --- | --- |
| **Source** | The base table, view, or SQL query containing the raw transactional data. | `samples.tpch.orders` |
| **Dimensions** | The column attributes used to segment or group the metrics | Product category, Order month, Customer region |
| **Measures** | The column aggregations that produce the metrics. These measures are what you usually report on. | `COUNT(o_order_id)` as Order Count, `SUM(o_total_price)` as Total Revenue. |
| **Filters** | Persistent conditions applied to the source data to define scope. | - `status = 'completed'`<br>- `order_date > '2024-01-01'` |

## Define a source

You can use a table-like asset or a SQL query as the source for your metric view. To use a table-like asset, you must have at least `SELECT` privileges on the asset.

### Use a table as a source

To use a table as a source, include the fully-qualified table name, as in the following example.

```yaml
source: samples.tpch.orders
```

### Use a SQL query as a source

To use a SQL query, write the query text directly in the YAML.

```yaml
source: SELECT * FROM samples.tpch.orders o
  LEFT JOIN samples.tpch.customer c
  ON o.o_custkey = c.c_custkey
```

Note

When using a SQL query as a source with a `JOIN` clause, Databricks recommends setting primary and foreign key constraints on underlying tables and using the `RELY` option for optimal performance at query time, if applicable. For more information about using primary and foreign key constraints, see [Declare primary key and foreign key relationships](../../tables/constraints#pk-fk) and [Query optimization using primary key constraints](../../sql/user/queries/query-optimization-constraints).

### Use metric view as a source

You can also use an existing metric view as the source for a new metric view:

```yaml
version: 1.1
source: views.examples.source_metric_view

dimensions:
  # Dimension referencing dimension from source_metric_view
  - name: Order date
    expr: order_date_dim

measures:
  # Measure referencing dimension from source_metric_view
  - name: Latest order month
    expr: MAX(order_date_dim_month)

  # Measure referencing measure from source_metric_view
  - name: Latest order year
    expr: DATE_TRUNC('year', MEASURE(max_order_date_measure))
```

When using a metric view as a source, the same composability rules apply for referencing dimensions and measures. See Composability.

## Dimensions

Dimensions are columns used in `SELECT`, `WHERE`, and `GROUP BY` clauses at query time. Each expression must return a scalar value. Dimensions are defined as an array. Each dimension consists of two components:

- `name`: The alias of the column.
- `expr`: A SQL expression on the source data that defines the dimension or a previously defined dimension in the metric view.

Note

Starting from version 1.1, you can also define semantic metadata (display name, format, and synonyms) for each dimension. See [Use semantic metadata in metric views](semantic-metadata) for details.

## Measures

Measures are columns defined as an array of expressions that produce results without a pre-determined level of aggregation. They must be expressed using aggregate functions. To reference a measure in a query, you must use the `MEASURE` function. Measures can reference base fields in the source data or earlier-defined dimensions. Each measure consists of the following components:

- `name`: The alias of the measure.
- `expr`: An aggregate SQL expression that can include SQL aggregate functions.

The following example demonstrates common measure patterns:

```yaml
measures:
  # Simple count measure
  - name: Order Count
    expr: COUNT(1)

  # Sum aggregation measure
  - name: Total Revenue
    expr: SUM(o_totalprice)

  # Distinct count measure
  - name: Unique Customers
    expr: COUNT(DISTINCT o_custkey)

  # Calculated measure combining multiple aggregations
  - name: Average Order Value
    expr: SUM(o_totalprice) / COUNT(DISTINCT o_orderkey)

  # Filtered measure with WHERE condition
  - name: High Priority Order Revenue
    expr: SUM(o_totalprice) FILTER (WHERE o_orderpriority = '1-URGENT')

  # Measure using a dimension
  - name: Average Revenue per Month
    expr: SUM(o_totalprice) / COUNT(DISTINCT DATE_TRUNC('MONTH', o_orderdate))
```

See [Aggregate functions](../../sql/language-manual/sql-ref-functions-builtin#aggregate-functions) for a list of aggregate functions.

See [`measure` aggregate function](../../sql/language-manual/functions/measure).

Note

Starting from version 1.1, you can also define semantic metadata (display name, format, and synonyms) for each measure. See [Use semantic metadata in metric views](semantic-metadata) for details.

## Apply filters

A filter in the YAML definition of a metric view applies to all queries that reference it. It must be written as a SQL boolean expression and is equivalent to using a `WHERE` clause in a SQL query.

The following example demonstrates common filter patterns:

```yaml
# Single condition filter
filter: o_orderdate > '2024-01-01'

# Multiple conditions with AND
filter: o_orderdate > '2024-01-01' AND o_orderstatus = 'F'

# Multiple conditions with OR
filter: o_orderpriority = '1-URGENT' OR o_orderpriority = '2-HIGH'

# Complex filter with IN clause
filter: o_orderstatus IN ('F', 'P') AND o_orderdate >= '2024-01-01'

# Filter with NOT
filter: o_orderstatus != 'O' AND o_totalprice > 1000.00

# Filter with LIKE pattern matching
filter: o_comment LIKE '%express%' AND o_orderdate > '2024-01-01'
```

You can also add filters when you query or consume metric views.

## Advanced modeling capabilities

Metric view modeling supports advanced techniques to create sophisticated and highly reusable metrics.

### Joins

Joins allow you to enrich your metric view with descriptive attributes from related tables. You can use joins to model relationships from the fact table to dimension tables ([star schema](https://www.databricks.com/glossary/star-schema)) and to traverse from dimensions to subdimensions, allowing multi-hop joins across normalized dimension tables ([snowflake schema](https://www.databricks.com/glossary/snowflake-schema)).

See [Use joins in metric views](joins).

### Window measures

Important

This feature is [Experimental](../../release-notes/release-types).

Window measures enable you to define measures with windowed, cumulative, or semiadditive aggregations in your metric views. These types of measures allow for more complex calculations, such as moving averages, period-over-period changes, and running totals. See [Use window measures in metric views](window-measures) for examples that demonstrate how to use window measures in metric views.

### Level of detail expressions

Level of detail (LOD) expressions enable you to control the aggregation granularity independently of the dimensions in your query. See [Use level of detail (LOD) expressions in metric views](level-of-detail).

### Composability

Metric views are composable, allowing you to build complex logic by referencing previously defined elements. You can reference previously defined dimensions in new dimensions, reference any dimension or previously defined measures in new measures, and reference columns from joins defined in the metric view.

See [Composability in metric views](composability).

### Semantic metadata

Semantic metadata helps consuming tools understand how to display and treat measures and dimensions. This includes properties such as:

| Semantic metadata | Example |
| --- | --- |
| Display names | `Total Revenue` instead of `sum_o_price`. |
| Display format | Standardize formatting for currency, percentages, and dates. |
| Comments | Explain the metric's business definition in natural language. |

When you define semantic metadata, it travels with the metric. For example, when analysts use **Total Revenue** in a dashboard, it automatically displays as currency.

See [Use semantic metadata in metric views](semantic-metadata).

## YAML syntax and formatting

Metric view definitions follow standard YAML notation syntax. See [YAML syntax reference](syntax) to learn about the required syntax and formatting to define a metric view. See [YAML Specification 1.2.2](https://yaml.org/spec/1.2.2/) documentation to learn more about YAML specifications.

### Window measures

Window measures calculate a value over a defined *window*, or range of rows related to the current row. You can use window measures for time-series and comparative analysis, allowing you to define metrics such as:

- **Rolling 30-Day Total Revenue**: Sum of revenue over the last 30 days
- **Year-to-Date (YTD) Revenue**: Cumulative sum from the start of the year
- **Previous Period Comparison**: Revenue from the prior month

See [Use window measures in metric views](window-measures).

## Best practices for modeling metric views

Use the following guidelines when modeling metric views:

- **Model atomic measures**: Start by defining the simplest, non-calculated measures first (for example, `SUM(revenue)`, `COUNT(DISTINCT customer_id)`). Build complex measures (like AOV) using composability.
- **Standardize dimension values**: Use transformations (such as `CASE` statements or expressions) to convert cryptic database codes into clear business names (for example, convert order status 'O' to 'Open' and 'F' to 'Fulfilled').
- **Define scope with filters**: Be intentional about persistent filters. If a metric view should only ever include completed orders, define that filter in the metric view so users cannot accidentally include incomplete data.
- **Use business-friendly naming**: Metric names should be immediately recognizable to business users (for example, **Customer Lifetime Value** vs. `cltv_agg_measure`).
- **Separate time dimensions**: Always include granular time dimensions (such as **Order Date**) and truncated time dimensions (such as **Order Month** or **Order Week**) to support both detail-level and trend analysis.