---
layout: Conceptual
title: Use semantic metadata in metric views - Azure Databricks | Microsoft Learn
canonicalUrl: https://learn.microsoft.com/en-us/azure/databricks/metric-views/data-modeling/semantic-metadata
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
description: Learn how to use semantic metadata in metric views to enhance data visualization and improve LLM accuracy.
locale: en-us
document_id: af4a8049-4f82-ce07-88c3-287cb8939611
document_version_independent_id: af4a8049-4f82-ce07-88c3-287cb8939611
updated_at: 2026-03-23T18:02:00.0000000Z
original_content_git_url: https://github.com/MicrosoftDocs/databricks-pr/blob/live/databricks/metric-views/data-modeling/semantic-metadata.md
gitcommit: https://github.com/MicrosoftDocs/databricks-pr/blob/fdaf586380a44520a5b0c845439f9c0994d03ce0/databricks/metric-views/data-modeling/semantic-metadata.md
git_commit_id: fdaf586380a44520a5b0c845439f9c0994d03ce0
site_name: Docs
depot_name: MSDN.databricks
page_type: conceptual
toc_rel: ../../toc.json
feedback_help_link_type: ''
feedback_help_link_url: ''
word_count: 1079
asset_id: metric-views/data-modeling/semantic-metadata
moniker_range_name: 
monikers: []
item_type: Content
source_path: databricks/metric-views/data-modeling/semantic-metadata.md
cmProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/545d40c6-c50c-444b-b422-1c707eeab28e
- https://microsoft-devrel.poolparty.biz/DevRelOfferingOntology/c6f99e62-1cf6-4b71-af9b-649b05f80cce
spProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/b908d601-32e8-445a-b044-a507b5d1689e
- https://microsoft-devrel.poolparty.biz/DevRelOfferingOntology/3f56b378-07a9-4fa1-afe8-9889fdc77628
platformId: 36ad74f2-bd0c-53ea-40a5-c293ab1714a6
---

# Use semantic metadata in metric views - Azure Databricks | Microsoft Learn

This page explains how to use semantic metadata in metric views to enhance data visualization and improve large language model (LLM) accuracy. This feature is in [Public Preview](../../release-notes/release-types).

Note

Requires Databricks Runtime 17.2 or above. Metric view YAML definitions must use specification version 1.1 or above. See [Version specification changelog](syntax#versions) for details.

## What is semantic metadata?

Semantic metadata includes display names, format specifications, and synonyms that provide additional context. This metadata helps visualization tools, such as AI/BI dashboards, and natural language tools, such as [Genie spaces](../../genie/), interpret and work with your data more effectively. Semantic metadata is defined in the YAML definition of a metric view.

Note

When you create or alter metric views with specification version 1.1, any single-line comments (denoted with `#`) in the YAML definition are removed when the definition is saved. See [Upgrade your YAML to 1.1](syntax#upgrade-yaml) for options and recommendations when upgrading existing YAML definitions.

### Display names

Display names provide human-readable labels that appear in visualization tools instead of technical column names. Display names are limited to 255 characters.

The following example shows display names defined on the `order_date` dimension and `total_revenue` measure.

```yaml
version: 1.1
source: samples.tpch.orders

dimensions:
  - name: order_date
    expr: o_orderdate
    display_name: 'Order Date'

measures:
  - name: total_revenue
    expr: SUM(o_totalprice)
    display_name: 'Total Revenue'
```

### Synonyms

Synonyms help LLM tools, such as [Genie](../../genie/), discover dimensions and measures through user input by providing alternative names. You can define synonyms using either block style or flow style YAML. Each dimension or measure can have up to 10 synonyms. Each synonym is limited to 255 characters.

The following example shows synonyms defined on the `order_date` dimension:

```yaml
version: 1.1
source: samples.tpch.orders

dimensions:
  - name: order_date
    expr: o_orderdate
    # block style
    synonyms:
      - 'order time'
      - 'date of order'

measures:
  - name: total_revenue
    expr: SUM(o_totalprice)
    # flow style
    synonyms: ['revenue', 'total sales']
```

### Format specifications

Format specifications define how values should be displayed in visualization tools. The following tables include supported format types and examples.

#### Numeric formats

| Format Type | Required Options | Optional Options |
| --- | --- | --- |
| **Number**: Use plain number format for general numeric values with optional decimal place control and abbreviation options. | `type: number` | - `decimal_places`: Controls the number of places shown after the decimal.<br>    - `type`: (Required if `decimal_places`is specified)<br>        - `max`<br>        - `exact`<br>        - `all`<br>    - `places`: Integer value from 0-10 (required if type is `max` or `exact`)<br>- `hide_group_separator`: When set to true, removes any applicable number grouping separator, such as a `,`.<br>    - `true`<br>    - `false`<br>- `abbreviation`:<br>    - `none`<br>    - `compact`<br>    - `scientific` |
| **Currency**: Use currency format for monetary values with ISO-4217 currency codes. | `type: currency` | - `currency_code`: ISO-4217 code (required). For example, the following codes insert the symbol for US dollars, Euros, and Yen, respectively.<br>    - `USD`<br>    - `EUR`<br>    - `JPY`<br>- `decimal_places`: Controls the number of places shown after the decimal.<br>    - `type`: (Required if `decimal_places`is specified)<br>        - `max`<br>        - `exact`<br>        - `all`<br>- `hide_group_separator`: When set to true, removes any applicable number grouping separator.<br>    - `true`<br>    - `false`<br>- `abbreviation`:<br>    - `none`<br>    - `compact`<br>    - `scientific` |
| **Percentage**: Use percentage format for ratio values expressed as percentages. | `type: percentage` | - `decimal_places`: Controls the number of places shown after the decimal.<br>    - `type`: (Required if `decimal_places`is specified)<br>        - `max`<br>        - `exact`<br>        - `all`<br>- `hide_group_separator`: When set to true, removes any applicable number grouping separator.<br>    - `true`<br>    - `false` |
| **Byte**: Use byte format for data size values displayed with appropriate byte units (KB, MB, GB, etc.). | `type: byte` | - `decimal_places`: Controls the number of places shown after the decimal.<br>    - `type`: (Required if `decimal_places`is specified)<br>        - `max`<br>        - `exact`<br>        - `all`<br>    - `places`: Integer value from 0-10 (required if type is `max` or `exact`)<br>- `hide_group_separator`: When set to true, removes any applicable number grouping separator.<br>    - `true`<br>    - `false` |

#### Numeric formatting examples

##### Number

```yaml
format:
  type: number
  decimal_places:
    type: max
    places: 2
  hide_group_separator: false
  abbreviation: compact
```

##### Currency

```yaml
format:
  type: currency
  currency_code: USD
  decimal_places:
    type: exact
    places: 2
  hide_group_separator: false
  abbreviation: compact
```

##### Percentage

```yaml
format:
  type: percentage
  decimal_places:
    type: all
  hide_group_separator: true
```

##### Byte

```yaml
format:
  type: byte
  decimal_places:
    type: max
    places: 2
  hide_group_separator: false
```

#### Date and time formats

The following table explains how to work with date and time formats.

| Format Type | Required Options | Optional Options |
| --- | --- | --- |
| **Date**: Use date format for date values with various display options. | - `type: date`<br>- `date_format`: Controls the way the date is displayed<br>    - `locale_short_month`: Displays the date with an abbreviated month<br>    - `locale_long_month`: Displays the date with the full name of the month<br>    - `year_month_day`: Formats the date as YYYY-MM-DD<br>    - `locale_number_month`: Displays the date with a month as a number<br>    - `year_week`: Formats the date as a year and a week number. For example, `2025-W1` | - `leading_zeros`: Controls whether single digit numbers are preceded by a zero<br>- `true`<br>- `false` |
| **DateTime**: Use datetime format for timestamp values combining date and time. | - `type: date_time`<br>- `date_format`: Controls the way the date is displayed<br>    - `no_date`: Date is hidden<br>    - `locale_short_month`: Displays the date with an abbreviated month<br>    - `locale_long_month`: Displays the date with the full name of the month<br>    - `year_month_day`: Formats the date as YYYY-MM-DD<br>    - `locale_number_month`: Displays the date with a month as a number<br>    - `year_week`: Formats the date as a year and a week number. For example, `2025-W1`<br>- `time_format`:<br>    - `no_time`: Time is hidden<br>    - `locale_hour_minute`: Displays the hour and minute<br>    - `locale_hour_minute_second`: Displays the hour, minute, and second | - `leading_zeros`: Controls whether single digit numbers are preceded by a zero<br>    - `true`<br>    - `false` |

Note

When working with a `date_time` type, at least one of `date_format` or `time_format` must specify a value other than `no_date` or `no_time`.

#### Datetime formatting examples

##### Date

```yaml
format:
  type: date
  date_format: year_month_day
  leading_zeros: true
```

##### DateTime

```yaml
format:
  type: date_time
  date_format: year_month_day
  time_format: locale_hour_minute_second
  leading_zeros: false
```

## Complete example

The following example shows a metric view definition that includes all semantic metadata types:

```yaml
version: 1.1
source: samples.tpch.orders
comment: Comprehensive sales metrics with enhanced semantic metadata
dimensions:
  - name: order_date
    expr: o_orderdate
    comment: Date when the order was placed
    display_name: Order Date
    format:
      type: date
      date_format: year_month_day
      leading_zeros: true
    synonyms:
      - order time
      - date of order
  - name: customer_segment
    expr: |
      CASE
        WHEN o_totalprice > 100000 THEN 'Enterprise'
        WHEN o_totalprice > 10000 THEN 'Mid-market'
        ELSE 'SMB'
      END
    comment: Customer classification based on order value
    display_name: Customer Segment
    synonyms:
      - segment
      - customer tier
measures:
  - name: total_revenue
    expr: SUM(o_totalprice)
    comment: Total revenue from all orders
    display_name: Total Revenue
    format:
      type: currency
      currency_code: USD
      decimal_places:
        type: exact
        places: 2
      hide_group_separator: false
      abbreviation: compact
    synonyms:
      - revenue
      - total sales
      - sales amount
  - name: order_count
    expr: COUNT(1)
    comment: Total number of orders
    display_name: Order Count
    format:
      type: number
      decimal_places:
        type: all
      hide_group_separator: true
    synonyms:
      - count
      - number of orders
  - name: avg_order_value
    expr: SUM(o_totalprice) / COUNT(1)
    comment: Average revenue per order
    display_name: Average Order Value
    format:
      type: currency
      currency_code: USD
      decimal_places:
        type: exact
        places: 2
    synonyms:
      - aov
      - average revenue
```