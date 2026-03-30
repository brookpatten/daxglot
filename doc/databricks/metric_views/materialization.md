---
layout: Conceptual
title: Materialization for metric views - Azure Databricks | Microsoft Learn
canonicalUrl: https://learn.microsoft.com/en-us/azure/databricks/metric-views/materialization
breadcrumb_path: /azure/databricks/breadcrumb/toc.json
feedback_system: Standard
feedback_product_url: https://feedback.azure.com/d365community/forum/2efba7dc-ef24-ec11-b6e6-000d3a4f0da0
uhfHeaderId: azure
ms.topic: feature-guide
ms.service: azure-databricks
ms.reviewer: jasonh
ms.custom: databricksmigration
ms.author: saperla
author: mssaperla
ms.date: 2026-03-11T00:00:00.0000000Z
description: Learn how to use materialization to accelerate metric view queries with automatic incremental updates and intelligent query rewrite.
locale: en-us
document_id: aa17af33-a9d6-f560-0d8f-96e06890a6d7
document_version_independent_id: aa17af33-a9d6-f560-0d8f-96e06890a6d7
updated_at: 2026-03-23T18:02:00.0000000Z
original_content_git_url: https://github.com/MicrosoftDocs/databricks-pr/blob/live/databricks/metric-views/materialization.md
gitcommit: https://github.com/MicrosoftDocs/databricks-pr/blob/fdaf586380a44520a5b0c845439f9c0994d03ce0/databricks/metric-views/materialization.md
git_commit_id: fdaf586380a44520a5b0c845439f9c0994d03ce0
site_name: Docs
depot_name: MSDN.databricks
page_type: conceptual
toc_rel: ../toc.json
feedback_help_link_type: ''
feedback_help_link_url: ''
word_count: 1335
asset_id: metric-views/materialization
moniker_range_name: 
monikers: []
item_type: Content
source_path: databricks/metric-views/materialization.md
cmProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/545d40c6-c50c-444b-b422-1c707eeab28e
- https://authoring-docs-microsoft.poolparty.biz/devrel/8b896464-3b7d-4e1f-84b0-9bb45aeb5f64
spProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/b908d601-32e8-445a-b044-a507b5d1689e
- https://authoring-docs-microsoft.poolparty.biz/devrel/b1d2d671-9549-46e8-918c-24349120dbf5
platformId: 38a73a51-3dc0-bc69-be4f-a7e670a7292a
---

# Materialization for metric views - Azure Databricks | Microsoft Learn

Important

This feature is [Experimental](../release-notes/release-types).

This article explains how to use materialization for metric views to accelerate query performance.

Materialization for metric views accelerates queries by using materialized views. Lakeflow Spark Declarative Pipelines orchestrates user-defined materialized views for a given metric view. At query time, the query optimizer intelligently routes user queries on the metric view to the best materialized view using automatic aggregate-aware query matching, also known as query rewriting.

This approach provides the benefits of pre-computation and automatic incremental updates, so you don't need to determine which aggregation table or materialized view to query for different performance goals, and eliminates the need to manage separate production pipelines.

## Overview

The following diagram illustrates how metric views handle definition and query execution:

![Metric views materialization definition and query execution](../_static/images/metric-views/materialization.png)

### Definition phase

When you define a metric view with materialization, `CREATE METRIC VIEW` or `ALTER METRIC VIEW` specifies your dimensions, measures, and refresh schedule. Databricks creates a [managed pipeline](../ldp/) that maintains the materialized views.

### Query execution

When you run `SELECT ... FROM <metric_view>`, the query optimizer uses aggregate-aware query rewriting to optimize performance:

- **Fast path**: Reads from pre-computed materialized views when applicable.
- **Fallback path**: Reads from source data directly when materializations aren't available.

The query optimizer automatically balances performance and freshness by choosing between materialized and source data. You receive results transparently regardless of which path is used.

## Requirements

To use materialization for metric views:

- Your workspace must have serverless compute enabled. This is required to run Lakeflow Spark Declarative Pipelines.
- Databricks Runtime 17.2 or above.

## Configuration reference

All information related to materialization is defined in a top-level field named `materialization` in the metric view YAML definition.

The `materialization` field contains the following required fields:

- **schedule**: Supports the same syntax as the [schedule clause on materialized views](../sql/language-manual/sql-ref-syntax-ddl-create-materialized-view#syntax).
- **mode**: Must be set to `relaxed`.
- **materialized\_views**: A list of materialized views to materialize.
    - **name**: The name of the materialization.
    - **dimensions**: A list of dimensions to materialize. Only direct references to dimension names are allowed; expressions aren't supported.
    - **measures**: A list of measures to materialize. Only direct references to measure names are allowed; expressions aren't supported.
    - **type**: Specifies whether the materialized view is aggregated or not. Accepts two possible values: `aggregated` and `unaggregated`.
        - If `type` is `aggregated`, there must be at least one dimension or measure.
        - If `type` is `unaggregated`, no dimension or measures should be defined.

Note

The [`TRIGGER ON UPDATE` clause](../ldp/dbsql/schedule-refreshes#trigger-on-update) isn't supported for materialization for metric views.

### Example definition

```yaml
version: 1.1

source: prod.operations.orders_enriched_view

filter: revenue > 0

dimensions:
  - name: category
    expr: substring(category, 5)

  - name: color
    expr: color

measures:
  - name: total_revenue
    expr: SUM(revenue)

  - name: number_of_suppliers
    expr: COUNT(DISTINCT supplier_id)

materialization:
  schedule: every 6 hours
  mode: relaxed

  materialized_views:
    - name: baseline
      type: unaggregated

    - name: revenue_breakdown
      type: aggregated
      dimensions:
        - category
        - color
      measures:
        - total_revenue

    - name: suppliers_by_category
      type: aggregated
      dimensions:
        - category
      measures:
        - number_of_suppliers
```

## Mode

In `relaxed` mode, automatic query rewrite only verifies if candidate materialized views have the necessary dimensions and measures to serve the query.

This means that several checks are skipped:

- There aren't checks on whether the materialized view is up to date.
- There aren't checks on whether you have matching SQL settings (for example, `ANSI_MODE` or `TIMEZONE`).
- There aren't checks on whether the materialized view returns deterministic results.

If the query includes any of the following conditions, the query rewrite doesn't occur and the query falls back to the source tables:

- [Row-level security (RLS)](../data-governance/unity-catalog/filters-and-masks/#what-are-row-filters) or [column-level masking (CLM)](../data-governance/unity-catalog/filters-and-masks/#what-are-column-masks) in materialized views.
- Non-deterministic functions like `current_timestamp()` in materialized views. These might appear in the metric view definition or in a source table used by the metric view.

Note

During the experimental release period, `relaxed` is the only supported mode. If these checks fail, the query falls back to the source data.

## Types of materializations for metric views

The following sections explain the types of materialized views available for metric views.

### Aggregated type

This type pre-computes aggregations for specified measure and dimension combinations for targeted coverage.

This is useful for targeting specific common aggregation query patterns or widgets. Databricks recommends including potential filter columns as dimensions in the materialized view configuration. Potential filter columns are columns used at query time in the `WHERE` clause.

### Unaggregated type

This type materializes the entire unaggregated data model (for example, the `source`, `join`, and `filter` fields) for wider coverage with less performance lift compared to the aggregated type.

Use this type when the following are true:

- The source is an expensive view or SQL query.
- Joins defined in your metric view are expensive.

Note

If your source is a direct table reference without a selective filter applied, an unaggregated materialized view might not provide benefits.

## Materialization lifecycle

This section explains how materializations are created, managed, and refreshed throughout their lifecycle.

### Create and modify

Creating or modifying a metric view (using `CREATE`, `ALTER`, or Catalog Explorer) happens synchronously. Specified materialized views materialize asynchronously using Lakeflow Spark Declarative Pipelines.

When you create a metric view, Databricks creates a Lakeflow Spark Declarative Pipelines pipeline and schedules an initial update immediately if there are materialized views specified. The metric view remains queryable without materializations by falling back to querying from the source data.

When you modify a metric view, no new updates are scheduled, unless you are enabling materialization for the first time. Materialized views aren't used for automatic query rewrite until the next scheduled update is complete.

Changing the materialization schedule doesn't trigger a refresh.

See Manual refresh for finer control over refresh behavior.

### Inspect underlying pipeline

Materialization for metric views is implemented using Lakeflow Spark Declarative Pipelines. A link to the pipeline is present in the **Overview** tab in Catalog Explorer. To learn how to access Catalog Explorer, see [What is Catalog Explorer?](../catalog-explorer/).

You can also access this pipeline by running `DESCRIBE EXTENDED` on the metric view. The **Refresh Information** section contains a link to the pipeline.

```sql
DESCRIBE EXTENDED my_metric_view;
```

Example output:

```sql
-- Returns additional metadata such as parent schema, owner, access time etc.
> DESCRIBE TABLE EXTENDED customer;
                      col_name                       data_type    comment
 ------------------------------- ------------------------------ ----------
                           ...                             ...        ...

 # Detailed Table Information
                           ...                             ...

                      Language                            YAML
              Table properties                             ...
 # Refresh information
         Latest Refresh status                       Succeeded
                Latest Refresh                     https://...
              Refresh Schedule                   EVERY 3 HOURS

```

### Manual refresh

From the link to the Lakeflow Spark Declarative Pipelines page, you can manually start a pipeline update to update the materializations. You can also trigger a manual refresh using the following SQL command:

```sql
REFRESH MATERIALIZED VIEW <metric-view-name>
```

### Incremental refresh

The materialized views use incremental refresh whenever possible, and have the same limitations regarding data sources and plan structure.

For details on prerequisites and restrictions, see [Incremental refresh for materialized views](../optimizations/incremental-refresh).

## Automatic query rewrite

Queries to a metric view with materialization attempt to use its materializations as much as possible. There are two query rewrite strategies: exact match and unaggregated match.

![Aggregate-aware query rewriting](../_static/images/metric-views/aggregate-aware.png)

When you query a metric view, the optimizer analyzes the query and available user-defined materializations. The query automatically runs on the best materialization instead of the base tables using this algorithm:

1. First attempts an exact match.
2. If an unaggregated materialization exists, tries an unaggregated match.
3. If query rewriting fails, the query reads directly from the source tables.

Note

Materializations must finish materializing before query rewrite can take effect.

### Verify query is using materialized views

To check if a query is using a materialized view, run `EXPLAIN EXTENDED` on your query to see the query plan. If the query is using materialized views, the leaf node includes` __materialization_mat___metric_view` and the name of the materialization from the YAML file.

Alternatively, the query profile shows the same information.

### Exact match

To be eligible for the exact match strategy, the grouping expressions of the query must precisely match the materialization dimensions. The aggregation expressions of the query must be a subset of the materialization measures.

### Unaggregated match

If an unaggregated materialization is available, this strategy is always eligible.

## Billing

Refreshing materialized views incurs Lakeflow Spark Declarative Pipelines usage charges.

## Known restrictions

The following restrictions apply to materialization for metric views:

- A metric view with materialization that refers to another metric view as source can't have an unaggregated materialization.