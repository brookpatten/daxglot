---
layout: Conceptual
title: Use level of detail (LOD) expressions in metric views - Azure Databricks | Microsoft Learn
canonicalUrl: https://learn.microsoft.com/en-us/azure/databricks/metric-views/data-modeling/level-of-detail
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
description: Use level of detail expressions in metric views to control aggregation granularity independently of the dimensions in your query.
locale: en-us
document_id: 7829704d-dc33-1279-1b31-90de3c8c113d
document_version_independent_id: 7829704d-dc33-1279-1b31-90de3c8c113d
updated_at: 2026-03-23T18:02:00.0000000Z
original_content_git_url: https://github.com/MicrosoftDocs/databricks-pr/blob/live/databricks/metric-views/data-modeling/level-of-detail.md
gitcommit: https://github.com/MicrosoftDocs/databricks-pr/blob/fdaf586380a44520a5b0c845439f9c0994d03ce0/databricks/metric-views/data-modeling/level-of-detail.md
git_commit_id: fdaf586380a44520a5b0c845439f9c0994d03ce0
site_name: Docs
depot_name: MSDN.databricks
page_type: conceptual
toc_rel: ../../toc.json
feedback_help_link_type: ''
feedback_help_link_url: ''
word_count: 840
asset_id: metric-views/data-modeling/level-of-detail
moniker_range_name: 
monikers: []
item_type: Content
source_path: databricks/metric-views/data-modeling/level-of-detail.md
cmProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/8b896464-3b7d-4e1f-84b0-9bb45aeb5f64
spProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/b1d2d671-9549-46e8-918c-24349120dbf5
platformId: 9253f4b0-3774-fdda-0b6e-f6fb80ba93b8
---

# Use level of detail (LOD) expressions in metric views - Azure Databricks | Microsoft Learn

Level of detail (LOD) expressions let you specify the granularity at which aggregations are calculated independently of the dimensions in your query. This page explains how to use LOD expressions in metric views.

## What are level of detail expressions?

Level of detail expressions enable you to specify exactly which dimensions to use when calculating an aggregate, regardless of the dimensions present in your query. This gives you fine-grained control over the scope of your calculations.

There are two types of level of detail expressions:

- **Fixed level of detail**: Aggregate over a pre-defined set of dimensions specified in the expression itself, ignoring other dimensions in the query.
- **Coarser level of detail**: Aggregate at a coarser granularity than the query by excluding specific dimensions from the grouping.

### When to use level of detail expressions

Use level of detail expressions when you need to do the following:

- Calculate percentages of total (for example, each category's share of total sales).
- Compare individual values to dataset-wide aggregates (for example, sales versus average sales).
- Create segment-level metrics that remain constant across different groupings.

## Fixed level of detail

A fixed level of detail expression computes an aggregate at a granularity that you define, ignoring the dimensions in your query. In metric views, fixed LOD expressions are implemented using SQL window functions with `PARTITION BY` clauses in the `source` query. The pre-computed result is then exposed as an identity dimension.

### Syntax

Fixed LOD expressions use [SQL window functions](../../sql/language-manual/sql-ref-window-functions) to compute aggregates at a defined granularity.

1. Include the window function in the `source` query:

    ```sql
    SELECT ..., <AGGREGATE_FUNCTION>(<column>) OVER (PARTITION BY <dim1>, <dim2>, ...) AS <lod_name>
    FROM <table>
    ```

    To aggregate over the entire dataset, omit the `PARTITION BY` clause and leave empty parentheses after `OVER`.
2. Expose the precomputed column as an identity dimension, where both `name` and `expr` are the column name:

    ```yaml
    dimensions:
      - name: <lod_name>
        expr: <lod_name>
    ```

### When to use a fixed level of detail

Use fixed level of detail expressions when you need the following:

- **No dependency on query groupings**: Metrics with static partitioning across all uses.
- **Dataset-level aggregates**: Global aggregates compared with row-level groupings (for example, percent of total sales by priority).
- **Multi-level hierarchies**: Detail-level and rollup-level metrics available in the same metric view.

### Example: Total sales by order priority

Suppose you want to define a metric view where each order's sales can be compared alongside the total sales for its priority group. The following example computes `priority_total_price` in the source query and exposes it as an identity dimension:

```yaml
version: 1.1

source: |
  SELECT
    o_orderkey,
    o_orderpriority,
    o_totalprice,
    o_orderdate,
    SUM(o_totalprice) OVER (PARTITION BY o_orderpriority) AS priority_total_price
  FROM samples.tpch.orders

dimensions:
  - name: order_priority
    expr: o_orderpriority
  - name: order_date
    expr: o_orderdate
  - name: priority_total_price
    expr: priority_total_price

measures:
  - name: total_sales
    expr: SUM(o_totalprice)

  - name: pct_of_priority_total
    expr: SUM(o_totalprice) / ANY_VALUE(priority_total_price)
```

The `priority_total_price` identity dimension holds the fixed total for each priority group. The `pct_of_priority_total` measure divides individual order sales by that fixed total to produce a percentage, regardless of how the query groups results.

Note

When referencing a fixed level of detail dimension in a measure expression, wrap it in an aggregate function. Use `ANY_VALUE` when the value is constant within a group, as in the previous example.

### Filtering on fixed level of detail expressions

Fixed level of detail expressions are computed within the `source` query before any query-time filters are applied. To apply a filter to a fixed LOD calculation, include the filter condition in the `source` query itself.

## Coarser level of detail

A coarser level of detail expression aggregates at a coarser granularity than the query by excluding one or more dimensions from the partition. In metric views, coarser LOD expressions are implemented using [window measures](window-measures) with the `all` range specification.

Important

Window measures are [Experimental](../../release-notes/release-types).

### Syntax

For each dimension to exclude from the partition, define a window measure with `range: all`:

```yaml
measures:
  - name: <measure_name>
    expr: <AGGREGATE_EXPRESSION>
    window:
      - order: <dimension_to_exclude>
        range: all
        semiadditive: last
```

To exclude multiple dimensions, add an entry to the `window` array for each dimension.

### When to use a coarser level of detail

Use coarser level of detail expressions when you need:

- **Dynamic groupings**: Aggregates that adapt to query groupings (for example, percent of total for any selected dimension).
- **Filter-aware aggregations**: Compute at a coarser granularity while respecting query-time filters.

### Example: Percent of total sales

To calculate the percentage of total sales for each order priority:

```yaml
version: 1.1

source: samples.tpch.orders

dimensions:
  - name: order_priority
    expr: o_orderpriority

measures:
  - name: total_sales
    expr: SUM(o_totalprice)

  - name: all_priorities_sales
    expr: SUM(o_totalprice)
    window:
      - order: order_priority
        range: all
        semiadditive: last

  - name: pct_of_total_sales
    expr: SUM(o_totalprice) / MEASURE(all_priorities_sales)
```

In this example:

- `total_sales` aggregates at the query's grouping level.
- `all_priorities_sales` uses `range: all` to compute a grand total across all order priorities, ignoring the `order_priority` dimension in the query.
- `pct_of_total_sales` divides priority-level sales by the grand total to produce a percentage.