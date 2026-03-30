---
layout: Conceptual
title: Composability in metric views - Azure Databricks | Microsoft Learn
canonicalUrl: https://learn.microsoft.com/en-us/azure/databricks/metric-views/data-modeling/composability
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
ms.date: 2025-10-23T00:00:00.0000000Z
description: Learn how to model data with Unity Catalog metric views.
locale: en-us
document_id: ccff4545-0ade-127f-0e66-c86c1643eedf
document_version_independent_id: ccff4545-0ade-127f-0e66-c86c1643eedf
updated_at: 2026-03-23T18:02:00.0000000Z
original_content_git_url: https://github.com/MicrosoftDocs/databricks-pr/blob/live/databricks/metric-views/data-modeling/composability.md
gitcommit: https://github.com/MicrosoftDocs/databricks-pr/blob/fdaf586380a44520a5b0c845439f9c0994d03ce0/databricks/metric-views/data-modeling/composability.md
git_commit_id: fdaf586380a44520a5b0c845439f9c0994d03ce0
site_name: Docs
depot_name: MSDN.databricks
page_type: conceptual
toc_rel: ../../toc.json
feedback_help_link_type: ''
feedback_help_link_url: ''
word_count: 639
asset_id: metric-views/data-modeling/composability
moniker_range_name: 
monikers: []
item_type: Content
source_path: databricks/metric-views/data-modeling/composability.md
cmProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/545d40c6-c50c-444b-b422-1c707eeab28e
- https://authoring-docs-microsoft.poolparty.biz/devrel/cbe4ca68-43ac-4375-aba5-5945a6394c20
- https://authoring-docs-microsoft.poolparty.biz/devrel/540ac133-a371-4dbb-8f94-28d6cc77a70b
spProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/b908d601-32e8-445a-b044-a507b5d1689e
- https://authoring-docs-microsoft.poolparty.biz/devrel/ced846cc-6a3c-4c8f-9dfb-3de0e90e2742
- https://authoring-docs-microsoft.poolparty.biz/devrel/60bfc045-f127-4841-9d00-ea35495a5800
platformId: 07ac278c-dc81-3f4c-16d7-64a741bd79fb
---

# Composability in metric views - Azure Databricks | Microsoft Learn

This page explains how composability works in metric views and provides examples that show you how to compose logic by building on dimensions, measures, and joins within a single view.

## Overview

Metric views are composable, which means you can define layered, reusable logic. Instead of writing every definition from scratch, you can create new ones that build on existing dimensions and measures.

With composability, you can:

- Reference previously defined dimensions in new dimensions
- Reference any dimension or previously defined measures in new measures
- Reference columns from joins defined in the metric view

Composability helps you avoid duplication, streamline metric definitions, and support more complex analysis without requiring raw SQL each time.

## Metric composability

**Composability** is the principle of building complex metrics by reusing simpler, foundational measures. Instead of writing and maintaining complex, nested SQL logic for every derived KPI, you define the core "atomic" measures once and then reference them in other, more sophisticated calculations. This approach dramatically improves **consistency**, **auditability**, and **maintenance** of your semantic layer.

The foundation of composability is the `MEASURE()` function, which allows a measure definition to reference any other measure defined within the same metric view.

### Define measures with composability

Composability is implemented in the `measures` section of the metric view YAML.

| Measure Type | Description | Example |
| --- | --- | --- |
| **Atomic** | A simple, direct aggregation on a source column. These form the building blocks. | `SUM(o_totalprice)` |
| **Composed** | An expression that mathematically combines one or more other measures using the `MEASURE()` function. | `MEASURE(Total Revenue) / MEASURE(Order Count)` |

#### Example: Average Order Value (AOV)

To calculate **Average Order Value (AOV)**, you need two measures: `Total Revenue` and `Order Count`.

```yaml
source: samples.tpch.orders

measures:
  # Total Revenue
  - name: total_revenue
    expr: SUM(o_totalprice)
    comment: The gross total value of all orders.
    display_name: 'Total Revenue'

  # Order Count
  - name: order_count
    expr: COUNT(1)
    comment: The total number of line items or orders.
    display_name: 'Order Count'

  # Composed Measure: Average Order Value (AOV)
  - name: avg_order_value
    # Defines AOV as Total Revenue divided by Order Count
    expr: MEASURE(total_revenue) / MEASURE(order_count)
    comment: Total revenue divided by the number of orders.
    display_name: 'Avg Order Value'
```

In this example, if the definition of `total_revenue` changes (e.g., if a filter to exclude tax is added), the `avg_order_value` automatically inherits that change, ensuring the AOV metric remains consistent with the new business rule.

### Composability with conditional logic

You can use composability to create complex ratios, conditional percentages, and growth rates without relying on window functions for simple period-over-period calculations.

#### Example: Fulfillment Rate

To calculate the **Fulfillment Rate** (Fulfilled Orders / Total Orders), you first define the measure for completed orders using a `FILTER` clause.

```yaml
source: samples.tpch.orders

measures:
  # Total Orders (denominator)
  - name: total_orders
    expr: COUNT(1)
    comment: Total volume of orders regardless of status.

  #  Fulfilled Orders (numerator)
  - name: fulfilled_orders
    expr: COUNT(1) FILTER (WHERE o_orderstatus = 'F')
    comment: Only includes orders marked as fulfilled.

  # Composed Measure: Fulfillment Rate (Ratio)
  - name: fulfillment_rate
    expr: MEASURE(fulfilled_orders) / MEASURE(total_orders)
    display_name: 'Order Fulfillment Rate'
    format:
      type: percentage # Using semantic metadata to format as a percent
```

### Best practices for using composability

1. **Define atomic measures first:** Always establish your fundamental measures (`SUM`, `COUNT`, `AVG`) before defining any measures that reference them.
2. **Use `MEASURE()` for consistency:** Always use the `MEASURE()` function when referencing another measure's calculation within an `expr`. Don't try to manually repeat the aggregation logic (for example, avoid `SUM(a) / COUNT(b)` if measures for both the numerator and denominator already exist).
3. **Prioritize readability:** The `expr` for a composed measure should read like a mathematical formula for the KPI. For example, `MEASURE(Gross Profit) / MEASURE(Total Revenue)` is clearer and easier to audit than a single complex SQL expression.
4. **Combine with semantic metadata:** After composing a ratio, use **semantic metadata** (as shown in the `fulfillment_rate` example) to automatically format the result as a percentage or currency for downstream tools. See [Use semantic metadata in metric views](semantic-metadata).