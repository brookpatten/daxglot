---
layout: Conceptual
title: YAML syntax reference - Azure Databricks | Microsoft Learn
canonicalUrl: https://learn.microsoft.com/en-us/azure/databricks/metric-views/data-modeling/syntax
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
description: Learn the syntax and expressions supported in a YAML metric view definition.
locale: en-us
document_id: bc31bfa7-a2d6-d932-0355-456d7d773cf7
document_version_independent_id: bc31bfa7-a2d6-d932-0355-456d7d773cf7
updated_at: 2026-03-23T18:02:00.0000000Z
original_content_git_url: https://github.com/MicrosoftDocs/databricks-pr/blob/live/databricks/metric-views/data-modeling/syntax.md
gitcommit: https://github.com/MicrosoftDocs/databricks-pr/blob/fdaf586380a44520a5b0c845439f9c0994d03ce0/databricks/metric-views/data-modeling/syntax.md
git_commit_id: fdaf586380a44520a5b0c845439f9c0994d03ce0
site_name: Docs
depot_name: MSDN.databricks
page_type: conceptual
toc_rel: ../../toc.json
feedback_help_link_type: ''
feedback_help_link_url: ''
word_count: 1086
asset_id: metric-views/data-modeling/syntax
moniker_range_name: 
monikers: []
item_type: Content
source_path: databricks/metric-views/data-modeling/syntax.md
cmProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/8b896464-3b7d-4e1f-84b0-9bb45aeb5f64
spProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/b1d2d671-9549-46e8-918c-24349120dbf5
platformId: 9b92b2f5-157f-a8a8-f0dd-59f0c20b94df
---

# YAML syntax reference - Azure Databricks | Microsoft Learn

Metric view definitions follow standard YAML notation syntax. This page explains how to define a metric view.

See [YAML Specification 1.2.2](https://yaml.org/spec/1.2.2/) documentation to learn more about YAML specifications.

## YAML overview

The YAML definition for a metric view includes the following top-level fields:

- **`version`:** Defaults to `1.1`. This is the version of the metric view specification. See Version specification changelog.
- **`source`:** The source data for the metric view. This can be a table-like asset or a SQL query.
- **`joins`:** Optional. Star schema and snowflake schema joins are supported.
- **`filter`:** Optional. A SQL boolean expression that applies to all queries; equivalent to the `WHERE` clause.
- **`comment`:** Optional. Description of the metric view.
- **`dimensions`:** An array of dimension definitions, including the dimension name and expression.
- **`measures`:** An array of aggregate expression columns.

## Column name references

When referencing column names that contain spaces or special characters in YAML expressions, enclose the column name in backticks to escape the space or character. If the expression starts with a backtick and is used directly as a YAML value, wrap the entire expression in double quotes. Valid YAML values cannot start with a backtick.

## Formatting examples

Use the following examples to learn how to format YAML correctly in common scenarios.

### Reference a column name

The following table shows how to format column names depending on the characters they contain.

| Case | Source column name(s) | Reference expression(s) | Notes |
| --- | --- | --- | --- |
| No spaces | `revenue` | `expr: "revenue"``expr: 'revenue'``expr: revenue` | Use double quotes, single quotes, or no quotes around the column name. |
| With spaces | `First Name` | `expr: "`First Name`" ` | Use backticks to escape spaces. Enclose the entire expression in double quotes. |
| Column name with spaces in a SQL expression | `First Name` and `Last Name` | `expr: CONCAT(`First Name`, , `Last Name`) ` | If the expression doesn't start with backticks, double quotes are not necessary. |
| Quotes are included in the source column name | `"name"` | `expr: '`"name"`' ` | Use backticks to escape the double-quotes in the column name. Enclose that expression in single quotes in the YAML definition. |

### Use expressions with colons

| Case | Expression | Notes |
| --- | --- | --- |
| Expressions with colons | `expr: "CASE WHEN `Customer Tier` = 'Enterprise: Premium' THEN 1 ELSE 0 END"` | Wrap the entire expression in double quotes for correct interpretation |

Note

YAML interprets unquoted colons as key-value separators. Always use double quotes around expressions that include colons.

### Multi-line indentation

| Case | Expression | Notes |
| --- | --- | --- |
| Multi-line indentation | `expr: \|``  CASE WHEN``    revenue > 100 THEN 'High'``  ELSE 'Low'``  END` | Indent the expression under the first line |

Note

Use the `|` block scalar after `expr:` for multi-line expressions. All lines must be indented at least two spaces beyond the `expr` key for correct parsing.

## Define a dimension

The following example demonstrates how to define dimensions:

```
dimensions:

  # Column name
  - name: Order date
    expr: o_orderdate

  # SQL expression
  - name: Order month
    expr: DATE_TRUNC('MONTH', `Order date`)

  # Referring to a column with a space in the name
  - name: Month of order
    expr: `Order month`

  # Multi-line expression
  - name: Order status
    expr: CASE
            WHEN o_orderstatus = 'O' THEN 'Open'
            WHEN o_orderstatus = 'P' THEN 'Processing'
            WHEN o_orderstatus = 'F' THEN 'Fulfilled'
          END

```

## Define a measure

The following example demonstrates how to define measures:

```
measures:

  # Basic aggregation
  - name: Total revenue
    expr: SUM(o_totalprice)

  # Basic aggregation with ratio
  - name: Total revenue per customer
    expr: SUM(`Total revenue`) / COUNT(DISTINCT o_custkey)

  # Measure-level filter
  - name: Total revenue for open orders
    expr: COUNT(o_totalprice) FILTER (WHERE o_orderstatus='O')

  # Measure-level filter with multiple aggregate functions
  # filter needs to be specified for each aggregate function in the expression
  - name: Total revenue per customer for open orders
    expr: SUM(o_totalprice) FILTER (WHERE o_orderstatus='O')/COUNT(DISTINCT o_custkey) FILTER (WHERE o_orderstatus='O')
```

## Column name mapping in `CREATE VIEW` with YAML

When you create a metric view using `CREATE VIEW` with a `column_list`, the system maps YAML-defined columns (measures and dimensions) to the `column_list` by position, not by name.

This follows standard SQL behavior as shown in the following example:

```sql
CREATE VIEW v (col1, col2) AS SELECT a, b FROM table;
```

In this example, `a` maps to `col1`, and `b` maps to `col2`, regardless of their original names.

## Upgrade your YAML to 1.1

Upgrading a metric view to YAML specification version 1.1 requires care, because comments are handled differently than in earlier versions.

### Types of comments

- **YAML comments (#)**: Inline or single-line comments written directly in the YAML file using the # symbol.
- **Unity Catalog comments**: Comments stored in Unity Catalog for the metric view or its columns (dimensions and measures). These are separate from YAML comments.

### Upgrade considerations

Choose the upgrade path that matches how you want to handle comments in your metric view. The following options describe the available approaches and provide examples.

#### Option 1: Preserve YAML comments using notebooks or the SQL editor

If your metric view contains YAML comments (#) that you want to keep, use the following steps:

1. Use the **ALTER VIEW** command in a notebook or SQL editor.
2. Copy the original YAML definition into $$..$$ section after **AS**. Change the value of version to 1.1.
3. Save the metric view.

```sql
ALTER VIEW metric_view_name AS
$$
# Inline comments are preserved in the notebook
version: 1.1
source: samples.tpch.orders
dimensions:
- name: order_date # Inline comments are preserved in the notebook
  expr: o_orderdate
measures:
# Commented out definition is preserved
# - name: total_orders
#   expr: COUNT(o_orderid)
- name: total_revenue
  expr: SUM(o_totalprice)
$$

```

Warning

Running `ALTER VIEW` removes Unity Catalog comments unless they are explicitly included in the `comment` fields of the YAML definition. If you want to preserve comments shown in Unity Catalog, see option 2.

#### Option 2: Preserve Unity Catalog comments

Note

The following guidance applies only when using the `ALTER VIEW` command in a notebook or SQL editor. If you upgrade your metric view to version 1.1 using the YAML editor UI, your Unity Catalog comments will be preserved automatically.

1. Copy all Unity Catalog comments into the appropriate `comment` fields in your YAML definition. Change the value of version to 1.1.
2. Save the metric view.

```sql
ALTER VIEW metric_view_name AS
$$
version: 1.1
source: samples.tpch.orders
comment: "Metric view of order (Updated comment)"

dimensions:
- name: order_date
  expr: o_orderdate
  comment: "Date of order - Copied from Unity Catalog"

measures:
- name: total_revenue
  expr: SUM(o_totalprice)
  comment: "Total revenue"
$$
```

## Version specification changelog

### Version 1.1 (requires Databricks Runtime 17.2 or above)

- **Added**:
    - Support for semantic metadata features. See [Use semantic metadata in metric views](semantic-metadata).
    - Support for optional YAML `comment` field to describe the metric view, dimensions, or measures.

### Version 0.1 (requires Databricks Runtime 16.4 through 17.1)

- Initial release of the metric view YAML spec.