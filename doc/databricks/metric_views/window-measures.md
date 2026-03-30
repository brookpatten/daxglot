---
layout: Conceptual
title: Use window measures in metric views - Azure Databricks | Microsoft Learn
canonicalUrl: https://learn.microsoft.com/en-us/azure/databricks/metric-views/data-modeling/window-measures
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
ms.date: 2026-01-24T00:00:00.0000000Z
description: Use examples to start defining window measures in metric views.
locale: en-us
document_id: 269a2c48-8835-dcc2-ae42-39b4668c3f63
document_version_independent_id: 269a2c48-8835-dcc2-ae42-39b4668c3f63
updated_at: 2026-03-23T18:02:00.0000000Z
original_content_git_url: https://github.com/MicrosoftDocs/databricks-pr/blob/live/databricks/metric-views/data-modeling/window-measures.md
gitcommit: https://github.com/MicrosoftDocs/databricks-pr/blob/fdaf586380a44520a5b0c845439f9c0994d03ce0/databricks/metric-views/data-modeling/window-measures.md
git_commit_id: fdaf586380a44520a5b0c845439f9c0994d03ce0
site_name: Docs
depot_name: MSDN.databricks
page_type: conceptual
toc_rel: ../../toc.json
feedback_help_link_type: ''
feedback_help_link_url: ''
word_count: 803
asset_id: metric-views/data-modeling/window-measures
moniker_range_name: 
monikers: []
item_type: Content
source_path: databricks/metric-views/data-modeling/window-measures.md
cmProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/bcbcbad5-4208-4783-8035-8481272c98b8
spProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/43b2e5aa-8a6d-4de2-a252-692232e5edc8
platformId: 24a42ccc-9314-fc45-2f72-bd39dee21111
---

# Use window measures in metric views - Azure Databricks | Microsoft Learn

Important

This feature is [Experimental](../../release-notes/release-types).

Window measures enable you to define measures with windowed, cumulative, or semiadditive aggregations in your metric views. These types of measures allow for more complex calculations, such as moving averages, period-over-period changes, and running totals. This page includes practical examples demonstrating how to work with window measures in metric views.

## Define a window measure

Window measures enable defining measures with windowed, cumulative, or semi-additive aggregations. A window measure includes the following required values:

- **order:** The dimension that determines the ordering of the window.
- **range:** Defines the extent of the window, such as trailing, cumulative, or all data. Possible range values include the following:

    - **`current`:** Includes rows where the window ordering value equals the current row’s value.
    - **`cumulative`**: Includes all rows where the window ordering value is less than or equal to the current row’s value.
    - **`trailing <value> <unit>`:** Includes rows from the current row going backward by the specified number of time units, such as `trailing 3 months`. This does not include the current unit. For example, `trailing 3 months` excludes the current month.
    - **`leading <value> <unit>`:** Includes rows from the current row going forward by the specified number of time units, such as `leading 7 days`.
    - **`all`:** Includes all rows regardless of the window value.
- **semiadditive:** Specifies how to summarize the measure when the order field is not included in the query's `GROUP BY`. Possible values include `first` and `last`.

## Trailing, moving, or leading window measure example

The following example calculates a measure over a trailing or leading window of time in the last 7 days.

```yaml
version: 0.1

source: samples.tpch.orders
filter: o_orderdate > DATE'1998-01-01'

dimensions:
  - name: date
    expr: o_orderdate

measures:
  - name: t7d_customers
    expr: COUNT(DISTINCT o_custkey)
    window:
      - order: date
        range: trailing 7 day
        semiadditive: last
```

For this example, the following configuration applies:

**order:**`date` specifies that the date dimension orders the window.

**range:** The `trailing 7 day` specification defines the window as the 7 days before each date, excluding the date itself.

**semiadditive:**`last` indicates the last value in the 7-day window is used.

## Period-over-period window measure example

Calculate the change from the previous period to the current period.

```yaml
version: 0.1

source: samples.tpch.orders
filter: o_orderdate > DATE'1998-01-01'

dimensions:
  - name: date
    expr: o_orderdate
measures:
  - name: previous_day_sales
    expr: SUM(o_totalprice)
    window:
      - order: date
        range: trailing 1 day
        semiadditive: last
  - name: current_day_sales
    expr: SUM(o_totalprice)
    window:
      - order: date
        range: current
        semiadditive: last
  - name: day_over_day_growth
    expr: (MEASURE(current_day_sales) - MEASURE(previous_day_sales)) / MEASURE(previous_day_sales) * 100
```

For this example, the following conditions apply:

- Two window measures are used: one for calculating total sales on the previous day and one for the current day.
- A third measure calculates the percentage change (growth) between the current and previous days.

## Cumulative (running) total measure example

Calculate a running total of a measure up to each point in time.

```yaml
version: 0.1

source: samples.tpch.orders
filter: o_orderdate > DATE'1998-01-01'

dimensions:
  - name: date
    expr: o_orderdate
measures:
  - name: running_total_sales
    expr: SUM(o_totalprice)
    window:
      - order: date
        range: cumulative
        semiadditive: last
```

The following details highlight key parts of this definition:

**order:**`date` ensures that the `date` dimension orders the window.

**range:**`cumulative` defines the window as all data up to and including each date.

**semiadditive:**`last` makes sure that the last cumulative value is used when aggregating over dimensions.

## Period to date measure example

Calculate a running total in a given period.

```yaml
version: 0.1

source: samples.tpch.orders
filter: o_orderdate > DATE'1997-01-01'

dimensions:
  - name: date
    expr: o_orderdate
  - name: year
    expr: DATE_TRUNC('year', o_orderdate)
measures:
  - name: ytd_sales
    expr: SUM(o_totalprice)
    window:
      - order: date
        range: cumulative
        semiadditive: last
      - order: year
        range: current
        semiadditive: last
```

The following details highlight key parts of this definition:

- Two window measures are used: one for the cumulative sum over the `date` dimension and another to limit the sum to the `current` year.
- The cumulative sum is restricted by the `year` dimension to check that it is calculated only within the current year.

## Semiadditive measure example

Calculate a measure that should not be summed over a specific dimension, such as a bank balance.

```yaml
dimensions:
  - name: date
    expr: date
  - name: customer
    expr: customer_id

measures:
  - name: semiadditive_balance
    expr: SUM(balance)
    window:
      - order: date
        range: current
        semiadditive: last
```

The following details highlight key parts of this definition:

- **order:**`date` ensures the `date` dimension orders the window.
- **range:**`current` restricts the window to a single day with no aggregation across days.
- **semiadditive:**`last` ensures that the most recent balance is returned when aggregating over multiple days.

Note

This window measure still sums over all customers to get the overall balance per day.

## Query a window measure

You can query a metric view with a window measure like any other metric view. The following example queries a metric view:

```sql
SELECT
   state,
   DATE_TRUNC('month', date),
   MEASURE(t7d_distinct_customers) as m
FROM sales_metric_view
WHERE date >= DATE'2024-06-01'
GROUP BY ALL

```