---
layout: Conceptual
title: Create a metric view - Azure Databricks | Microsoft Learn
canonicalUrl: https://learn.microsoft.com/en-us/azure/databricks/metric-views/create/
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
document_id: 9bf240e3-ba99-7e85-fb4b-0af8e30e0e77
document_version_independent_id: 9bf240e3-ba99-7e85-fb4b-0af8e30e0e77
updated_at: 2026-03-23T18:02:00.0000000Z
original_content_git_url: https://github.com/MicrosoftDocs/databricks-pr/blob/live/databricks/metric-views/create/index.md
gitcommit: https://github.com/MicrosoftDocs/databricks-pr/blob/fdaf586380a44520a5b0c845439f9c0994d03ce0/databricks/metric-views/create/index.md
git_commit_id: fdaf586380a44520a5b0c845439f9c0994d03ce0
site_name: Docs
depot_name: MSDN.databricks
page_type: conceptual
toc_rel: ../../toc.json
feedback_help_link_type: ''
feedback_help_link_url: ''
word_count: 684
asset_id: metric-views/create/index
moniker_range_name: 
monikers: []
item_type: Content
source_path: databricks/metric-views/create/index.md
cmProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/cbe4ca68-43ac-4375-aba5-5945a6394c20
- https://authoring-docs-microsoft.poolparty.biz/devrel/545d40c6-c50c-444b-b422-1c707eeab28e
spProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/ced846cc-6a3c-4c8f-9dfb-3de0e90e2742
- https://authoring-docs-microsoft.poolparty.biz/devrel/b908d601-32e8-445a-b044-a507b5d1689e
platformId: 22b80999-e94c-5ecc-9a4a-825f26a96476
---

# Create a metric view - Azure Databricks | Microsoft Learn

This page explains the data model and considerations used in the examples showing how to create a metric view using SQL or the UI.

## Sample dataset overview

The examples provided in [Use SQL to create and manage metric views](sql) and [Create a metric view using the Catalog Explorer UI](ui) use the TPC-H dataset, which is available by default in [Unity Catalog datasets](../../discover/databricks-datasets#uc-datasets).

The TPC-H dataset is a standard benchmark dataset used to evaluate decision support systems and query performance. It models a wholesale supply chain business and is structured around common business operations such as orders, customers, suppliers, and parts. It represents a sales and distribution environment, where customers place orders for parts supplied by various suppliers across different nations and regions.

The schema has 8 tables:

- `REGION` and `NATION`: These tables define the location.
- `CUSTOMER` and `SUPPLIER`: These tables describe business entities.
- `PART` and `PARTSUPP`: These tables capture product information and supplier availability.
- `ORDERS` and `LINEITEM`: These tables represent transactions, with line items detailing products within orders.

## TPC-H dataset ERD

The following diagram explains the relationships between the tables.

![TPC-H entity relationship diagram shows the relationships between tables.](../../_static/images/metric-views/tcp-h-erd.png)

Legend:

- The parentheses following each table name contain the prefix of the column names for that table;
- The arrows point in the direction of the one-to-many relationships between tables;
- The number/formula below each table name represents the cardinality (number of rows) of the table. Some are factored by SF, the Scale Factor, to obtain the chosen database size. The cardinality for the LINEITEM table is approximate (see Clause 4.2.5).

(source: [TPC Benchmark H Standard Specification](https://www.tpc.org/tpc_documents_current_versions/pdf/tpc-h_v2.17.1.pdf))

## Define a metric view

You can define a metric view using SQL DDL or the Catalog Explorer UI. Alternatively, Genie Code can help you get started creating your metric view. Then, you can edit the provided SQL DDL or use the metric view editor in the UI to refine the suggested definition.

The metric view defined for the examples in this section is designed for a sales or financial analyst to monitor key performance indicators (KPIs) related to the company's orders. It can help answer questions such as:

- How has our total revenue trended over time?
- What is the current breakdown of our orders by status (Open, Processing, Fulfilled)?
- Which order priorities generate the most revenue?
- How much revenue is currently 'at risk' or outstanding (i.e., from Open orders)?
- What is the average revenue generated per unique customer?

The necessary components are described in the following table:

| Component | YAML field/expression | Business meaning |
| --- | --- | --- |
| Source table | `samples.tpch.orders` | The raw data containing customer order records. |
| Filter | `o_orderdate > '1990-01-01'` | Focuses analysis only on orders placed *after* January 1, 1990, likely excluding historical or archived data. |
| Dimension: Order Month | `(DATE_TRUNC('MONTH', o_orderdate))` | Enables trend analysis (Month over month/Year over year), tracking how performance changes over time. |
| Dimension: Order Status | `CASE` statement that translates status to `Open`, `Processing`, or `Fulfilled` | Allows segmentation by lifecycle stage, helpful for fulfillment and backlog management. |
| Dimension: Order Priority | `SPLIT` statement that formats the order priority as a number | Used to group performance by the strategic importance or urgency of the order. |
| Measure: Order Count | `COUNT(1)` | Measures the volume sales activity |
| Measure: Total Revenue | `SUM(o_totalprice)` | The gross sales value of all orders |
| Measure: Total Revenue per Customer | `SUM(o_totalprice) / COUNT(DISTINCT o_custkey)` | A customer value metric useful for assessing customer transaction quality. |
| Measure: Total Revenue for Open Orders | `SUM(o_totalprice) FILTER (WHERE o_orderstatus='O')` | The value of unearned revenue or the current sales backlog. Used for forecasting and risk assessment. |

### Ask Genie Code

Genie Code can help you get started defining a metric view.

![Genie Code generates a metric view definition from a natural language prompt.](../../_static/images/assistant-create-metric-view.gif)

1. Click ![Sparkle fill icon.](../../_static/images/product-icons/sparklefillicon.svg) Genie Code icon in the upper-right corner of your Databricks workspace to open Genie Code.
2. Type a description of the metric view that you want to create. Genie Code returns SQL DDL that attempts to match your request.
3. Copy the provided SQL and paste it into the [SQL editor](../../sql/user/sql-editor/). Then, click **Run**.
4. Edit the SQL or open the metric view editor to make adjustments.

### Create a new metric view

Use one of the following examples to create a new metric view:

- [Create a metric view using the Catalog Explorer UI](ui)
- [Use SQL to create and manage metric views](sql)