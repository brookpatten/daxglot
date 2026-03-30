---
layout: Conceptual
title: Use SQL to create and manage metric views - Azure Databricks | Microsoft Learn
canonicalUrl: https://learn.microsoft.com/en-us/azure/databricks/metric-views/create/sql
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
description: Learn how to create a metric view to centralize business logic and consistently define key performance indicators across reporting tools.
locale: en-us
document_id: 911c5fa4-79c3-0e8c-9db2-41dd382f0f2e
document_version_independent_id: 911c5fa4-79c3-0e8c-9db2-41dd382f0f2e
updated_at: 2026-03-23T18:02:00.0000000Z
original_content_git_url: https://github.com/MicrosoftDocs/databricks-pr/blob/live/databricks/metric-views/create/sql.md
gitcommit: https://github.com/MicrosoftDocs/databricks-pr/blob/fdaf586380a44520a5b0c845439f9c0994d03ce0/databricks/metric-views/create/sql.md
git_commit_id: fdaf586380a44520a5b0c845439f9c0994d03ce0
site_name: Docs
depot_name: MSDN.databricks
page_type: conceptual
toc_rel: ../../toc.json
feedback_help_link_type: ''
feedback_help_link_url: ''
word_count: 767
asset_id: metric-views/create/sql
moniker_range_name: 
monikers: []
item_type: Content
source_path: databricks/metric-views/create/sql.md
cmProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/cbe4ca68-43ac-4375-aba5-5945a6394c20
- https://authoring-docs-microsoft.poolparty.biz/devrel/545d40c6-c50c-444b-b422-1c707eeab28e
spProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/ced846cc-6a3c-4c8f-9dfb-3de0e90e2742
- https://authoring-docs-microsoft.poolparty.biz/devrel/b908d601-32e8-445a-b044-a507b5d1689e
platformId: 024a8928-10ed-94f0-e509-512ce9263158
---

# Use SQL to create and manage metric views - Azure Databricks | Microsoft Learn

This page explains how to create and manage metric views using SQL.

## Prerequisites

- You must have `SELECT` privileges on the source data objects.
- You must have the [`CREATE TABLE` privilege](../../data-governance/unity-catalog/manage-privileges/privileges#create-table) and the [`USE SCHEMA` privilege](../../data-governance/unity-catalog/manage-privileges/privileges#use-schema) in the schema where you want to create the metric view.
- You must also have the [`USE CATALOG` privilege](../../data-governance/unity-catalog/manage-privileges/privileges#use-catalog) on the schema's parent catalog.
- CAN USE permissions on a SQL warehouse or other compute resource running Databricks Runtime 17.2 or above.

A metastore admin or the catalog owner can grant you all of these privileges. A schema owner or user with the `MANAGE` privilege can grant you `USE SCHEMA` and `CREATE TABLE` privileges on the schema.

## Create a metric view

Use `CREATE VIEW` with the `WITH METRICS` clause to create a metric view. The metric view must be defined with a valid YAML specification in the body. Source data for a metric view can be a table, view, or SQL query.

The source data for the following metric view is the `samples.tpch.orders` table available in the samples catalog for most Azure Databricks deployments. The following SQL DDL creates a metric view named `orders_metric_view` in the current catalog and schema. To specify a different catalog and schema, use the Unity Catalog three-level namespace.

You can add table-level and column-level comments to the metric view definition.

```sql
CREATE OR REPLACE VIEW orders_metric_view
WITH METRICS
LANGUAGE YAML
AS $$
  version: 1.1
  comment: "Orders KPIs for sales and financial analysis"
  source: samples.tpch.orders
  filter: o_orderdate > '1990-01-01'
  dimensions:
    - name: Order Month
      expr: DATE_TRUNC('MONTH', o_orderdate)
    - name: Order Status
      expr: CASE
        WHEN o_orderstatus = 'O' then 'Open'
        WHEN o_orderstatus = 'P' then 'Processing'
        WHEN o_orderstatus = 'F' then 'Fulfilled'
        END
    - name: Order Priority
      expr: SPLIT(o_orderpriority, '-')[1]
  measures:
    - name: Order Count
      expr: COUNT(1)
    - name: Total Revenue
      expr: SUM(o_totalprice)
    - name: Total Revenue per Customer
      expr: SUM(o_totalprice) / COUNT(DISTINCT o_custkey)
    - name: Total Revenue for Open Orders
      expr: SUM(o_totalprice) FILTER (WHERE o_orderstatus='O')
$$
```

## Alter a metric view

To make changes to the definition associated with a metric view, use `ALTER VIEW`. The following example adds comments to dimensions and measures in the `orders_metric_view` metric view.

```sql
ALTER VIEW orders_metric_view
AS $$
  version: 1.1
  comment: "Orders KPIs for sales and financial analysis"
  source: samples.tpch.orders
  filter: o_orderdate > '1990-01-01'
  dimensions:
    - name: Order Month
      expr: DATE_TRUNC('MONTH', o_orderdate)
      comment: "Month of order"
    - name: Order Status
      expr: CASE
        WHEN o_orderstatus = 'O' then 'Open'
        WHEN o_orderstatus = 'P' then 'Processing'
        WHEN o_orderstatus = 'F' then 'Fulfilled'
        END
      comment: "Status of order: open, processing, or fulfilled"
    - name: Order Priority
      expr: SPLIT(o_orderpriority, '-')[1]
      comment: "Numeric priority 1 through 5; 1 is highest"
  measures:
    - name: Order Count
      expr: COUNT(1)
    - name: Total Revenue
      expr: SUM(o_totalprice)
      comment: "Sum of total price"
    - name: Total Revenue per Customer
      expr: SUM(o_totalprice) / COUNT(DISTINCT o_custkey)
      comment: "Sum of total price by customer"
    - name: Total Revenue for Open Orders
      expr: SUM(o_totalprice) FILTER (WHERE o_orderstatus='O')
      comment: "Potential revenue from open orders"
$$
```

## Grant privileges on a metric view

A metric view is a Unity Catalog securable object and follows the same permission model as other views. Privileges are hierarchical, so privileges on a metastore, catalog, or schema cascade to the objects contained within. The following example grants minimum privileges necessary for users in the `data_consumers` group to query a metric view.

```sql
GRANT SELECT ON orders_metric_view to `data-consumers`;
```

To learn more about privileges in Unity Catalog, see [Manage privileges in Unity Catalog](../../data-governance/unity-catalog/manage-privileges/). To learn more about creating and managing groups, see [Groups](../../admin/users-groups/groups).

## Get metric view definition

Use `DESCRIBE TABLE EXTENDED` with the optional `AS JSON` parameter to view the definition for a metric view. The `AS JSON` parameter is optional. Omitting it provides output that is better for human readers, while including it is better for machine consumers. The following example returns a JSON string that describes the metric view and its components.

```sql
DESCRIBE TABLE EXTENDED orders_metric_view AS JSON
```

## Drop a metric view

Use `DROP VIEW` syntax to delete a metric view.

```sql
DROP VIEW orders_metric_view;
```