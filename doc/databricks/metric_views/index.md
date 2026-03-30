---
layout: Conceptual
title: Unity Catalog metric views - Azure Databricks | Microsoft Learn
canonicalUrl: https://learn.microsoft.com/en-us/azure/databricks/metric-views/
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
ms.date: 2026-03-10T00:00:00.0000000Z
description: Learn what Unity Catalog metric views are and how to define, govern, and consume them.
locale: en-us
document_id: a20c5e0b-4c16-07d2-b812-2194d7564aa9
document_version_independent_id: a20c5e0b-4c16-07d2-b812-2194d7564aa9
updated_at: 2026-03-23T18:02:00.0000000Z
original_content_git_url: https://github.com/MicrosoftDocs/databricks-pr/blob/live/databricks/metric-views/index.md
gitcommit:
https://github.com/MicrosoftDocs/databricks-pr/blob/fdaf586380a44520a5b0c845439f9c0994d03ce0/databricks/metric-views/index.md
git_commit_id: fdaf586380a44520a5b0c845439f9c0994d03ce0
site_name: Docs
depot_name: MSDN.databricks
page_type: conceptual
toc_rel: ../toc.json
feedback_help_link_type: ''
feedback_help_link_url: ''
word_count: 1099
asset_id: metric-views/index
moniker_range_name:
monikers: []
item_type: Content
source_path: databricks/metric-views/index.md
cmProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/cbe4ca68-43ac-4375-aba5-5945a6394c20
- https://authoring-docs-microsoft.poolparty.biz/devrel/545d40c6-c50c-444b-b422-1c707eeab28e
- https://authoring-docs-microsoft.poolparty.biz/devrel/540ac133-a371-4dbb-8f94-28d6cc77a70b
spProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/ced846cc-6a3c-4c8f-9dfb-3de0e90e2742
- https://authoring-docs-microsoft.poolparty.biz/devrel/b908d601-32e8-445a-b044-a507b5d1689e
- https://authoring-docs-microsoft.poolparty.biz/devrel/60bfc045-f127-4841-9d00-ea35495a5800
platformId: 345d1c0f-e209-c4ec-6366-9a0bd70bb6a2
---

# Unity Catalog metric views - Azure Databricks | Microsoft Learn

Metric views provide a centralized way to define and manage consistent, reusable, and governed core business metrics.
This page explains metric views, how to define them, control access, and query them in downstream tools.

## What is a metric view?

Metric views abstract complex business logic into a centralized definition, enabling organizations to define key
performance indicators once and use them consistently across reporting tools like dashboards, Genie spaces, and alerts.
Metric views are defined in YAML format and registered in Unity Catalog. You can create them using SQL or the Catalog
Explorer UI. Like any other table or view, metric views can be queried using SQL.

![Diagram showing that metric views are defined on source tables, views, and queries and consumed from code and no code
interfaces.](../_static/images/metric-views/what-is.png)

## Why use metric views

Unlike standard views that lock in aggregations and dimensions at creation time, metric views separate measure
definitions from dimension groupings. This allows you to define metrics once and query them flexibly across any
dimension at runtime, while the query engine automatically generates the correct computation.

Metric views provide key benefits:

- **Standardize metric definitions** across teams and tools to prevent inconsistencies.
- **Handle complex measures** like ratios and distinct counts that cannot be safely re-aggregated in standard views.
- **Enable flexible analysis** by supporting star and snowflake schemas with multi-level joins (for example, orders →
products → categories).
- **Accelerate query performance** with built-in [materialization](materialization) that automatically pre-computes and
incrementally updates aggregations.
- **Simplify the user experience** while maintaining SQL transparency and governance.

### Example

Suppose you want to analyze revenue per distinct customer across different geographic levels. With a standard view, you
would need to create separate views for each grouping (state, region, country) or compute all combinations in advance
using `GROUP BY CUBE()` and filter afterward. These workarounds increase complexity and lead to performance and
governance issues.

With a metric view, you define the metric once (*sum of revenue divided by distinct customer count*), and users can
group by any available geography dimension. The query engine rewrites the query behind the scenes to perform the correct
computation, regardless of how the data is grouped.

## Components

A metric view specifies a set of metric definitions, which include dimensions and measures, based on a data source, or
multiple sources if join logic is used. The `source` in the metric view definition can be a view, table, or SQL query.
Joins are only supported on views and tables.

A dimension is a categorical attribute that organizes and filters data, such as product names, customer types, or
regions. Dimensions provide the labels and groupings needed to analyze measures effectively.

A measure is a value that summarizes business activity, typically using an aggregate function such as `SUM()` or
`AVG()`. Measures can be applied to one or more base fields in the source table or view, or reference earlier-defined
dimensions and measures. Measures are defined independently of dimensions, allowing users to aggregate them across any
dimension at runtime. For example, defining a `total_revenue` measure enables aggregation by `customer`, `supplier`, or
`region`. Measures are commonly used as KPIs in reports and dashboards.

## Access and edit metric views

Metric views are registered to Unity Catalog. Users with at least SELECT permission on the metric view can access
details using the Catalog Explorer UI.

### View details in the Catalog Explorer UI

To view the metric view in Catalog Explorer:

1. Click ![Data icon.](../_static/images/product-icons/dataicon.svg)**Catalog** in the sidebar.
2. Browse available data or use the search bar to search for the metric view by name.
3. Click the name of the metric view.
4. Use the tabs to view information about the metric view:

- **Overview**: Shows all measures and dimensions defined in the metric and any semantic metadata that has been defined.
- **Details**: Shows the complete YAML definition for the metric view.
- **Permissions**: Shows all principals who can access the metric view, their privileges, and the containing database
object on which the privilege is defined.
- **Lineage**: Displays related assets, such as tables, notebooks, dashboards, and other metric views.
- **Insights**: Queries made on the metric view and users who accessed the metric view in the past 30 days are listed in
order of frequency, with the most frequent on top.

### Enable collaborative editing

By default, only the owner of a metric view can edit its definition. To enable multiple people to collaborate on the
same metric view, transfer ownership to a group. All members of that group can then edit the definition, but only access
data the group has permissions to see.

To enable collaborative editing:

1. Create or identify a group that should have edit access to the metric view. See
[Groups](../admin/users-groups/groups).
2. Grant the group `SELECT` access to all tables the metric view depends on.
3. Transfer ownership of the metric view to the group. See [Transfer
ownership](../data-governance/unity-catalog/manage-privileges/ownership#transfer-ownership).
4. Add or remove users from the group to control who can edit the metric view.

## Query a metric view

You can query metric views in the same way as a standard view. Run queries from any SQL editor that is attached to a SQL
warehouse or other compute resource running a supported runtime.

### Query measures and dimensions

All measure evaluations in a metric view query must use the `MEASURE` aggregate function. For complete details and
syntax, see [`measure` aggregate function](../sql/language-manual/functions/measure).

Note

Metric views don't support `SELECT *` queries. Measures are aggregations that must be explicitly referenced by name
using the `MEASURE()` function, so you must specify the dimensions and measures you want to query.

JOINs at query time aren't supported. To join tables:

- Define JOINs in the YAML specification that creates the metric view. See [Use joins in metric
views](data-modeling/joins).
- Use common table expressions (CTEs) to join sources when querying a metric view. See [Common table expression
(CTE)](../sql/language-manual/sql-ref-syntax-qry-select-cte).

### View details as a query result

The following query returns the full YAML definition for a metric view, including measures, dimensions, joins, and
[semantic metadata](data-modeling/semantic-metadata). The `AS JSON` parameter is optional. For complete syntax details,
see [JSON formatted output](../sql/language-manual/sql-ref-syntax-aux-describe-table#json-formatted-output).

```sql
DESCRIBE TABLE EXTENDED <catalog.schema.metric_view_name> AS JSON
	```

	The complete YAML definition is shown in the **View Text** field in the results. Each column contains a **metadata**
	field that holds semantic metadata.

	## Consume metric views

	You can also use metric views throughout the Azure Databricks workspace or in Power BI. For more information, see
	the associated documentation:

	- [Use metric views with AI/BI dashboards](../dashboards/manage/data-modeling/datasets#use-metric-views)
	- [Use metric views with Genie](../genie/set-up#create)
	- [Set alerts on metric views](../sql/user/alerts/#metric-views)
	- [Troubleshoot with query profile](../sql/user/queries/query-profile)
	- [Work with metric view metadata using the Databricks JDBC Driver](../integrations/jdbc-oss/metadata)
	- [Query metric views in Power BI](../partners/bi/power-bi-metric-views)

	## Limitations

	The following limitations apply to metric views:

	- Metric views do not support Delta Sharing or data profiling.