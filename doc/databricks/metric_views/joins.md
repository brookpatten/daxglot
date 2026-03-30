---
layout: Conceptual
title: Use joins in metric views - Azure Databricks | Microsoft Learn
canonicalUrl: https://learn.microsoft.com/en-us/azure/databricks/metric-views/data-modeling/joins
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
ms.date: 2025-12-15T00:00:00.0000000Z
description: Learn how to use joins in metric views to model complex data relationships and support snowflake schemas.
locale: en-us
document_id: f389b693-0e93-6ef2-88e8-f61ab9a73866
document_version_independent_id: f389b693-0e93-6ef2-88e8-f61ab9a73866
updated_at: 2026-03-23T18:02:00.0000000Z
original_content_git_url: https://github.com/MicrosoftDocs/databricks-pr/blob/live/databricks/metric-views/data-modeling/joins.md
gitcommit: https://github.com/MicrosoftDocs/databricks-pr/blob/fdaf586380a44520a5b0c845439f9c0994d03ce0/databricks/metric-views/data-modeling/joins.md
git_commit_id: fdaf586380a44520a5b0c845439f9c0994d03ce0
site_name: Docs
depot_name: MSDN.databricks
page_type: conceptual
toc_rel: ../../toc.json
feedback_help_link_type: ''
feedback_help_link_url: ''
word_count: 586
asset_id: metric-views/data-modeling/joins
moniker_range_name: 
monikers: []
item_type: Content
source_path: databricks/metric-views/data-modeling/joins.md
cmProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/545d40c6-c50c-444b-b422-1c707eeab28e
spProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/b908d601-32e8-445a-b044-a507b5d1689e
platformId: c15aaa56-9bdc-3399-7b84-fc2c55fd2feb
---

# Use joins in metric views - Azure Databricks | Microsoft Learn

Joins in metric views support both direct joins from a fact table to dimension tables ([star schema](https://www.databricks.com/glossary/star-schema)) and joins traversing from the fact table to dimension tables, and then to subdimension tables, allowing multi-hop joins across normalized dimension tables ([snowflake schemas](https://www.databricks.com/glossary/snowflake-schema)). This page explains how to define joins in the YAML definition of a metric view.

Note

Joined tables cannot include `MAP` type columns. To learn how to unpack values from `MAP` type columns, see [Explode nested elements from a map or array](../../semi-structured/complex-types#map-array).

## Model star schemas

In a star schema, the `source` is the fact table and joins with one or more dimension tables using a `LEFT OUTER JOIN`. Metric views join the fact and dimension tables that are needed for the specific query, based on the selected dimensions and measures.

Specify join columns in a metric view using either an `ON` clause or a `USING` clause.

- **`ON` clause**: Uses a boolean expression to define the join condition.
- **`USING` clause**: Lists columns with the same name in both the parent table and the joined table. For first-level joins, the parent is the metric view's source. For nested joins in a snowflake schema, the parent is the immediate upstream join.

The join should follow a many-to-one relationship. In cases of many-to-many, the first matching row from the joined dimension table is selected.

Note

YAML 1.1 parsers (such as PyYAML) can misinterpret certain unquoted keys, such as `on`, `off`, `yes`, `no`, or `NO`, as boolean values. This can cause join errors.To avoid this issue, wrap these keys in quotes. For example: `'on': source.dim_fk = dim.pk`

```
source: catalog.schema.fact_table

joins:

  # The on clause supports a boolean expression
  - name: dimension_table_1
    source: catalog.schema.dimension_table_1
    on: source.dimension_table_1_fk = dimension_table_1.pk

  # The using clause supports an array of columns
  # found in both of the tables being joined.
  - name: dimension_table_2
    source: catalog.schema.dimension_table_2
    using:
      - dimension_table_2_key_a
      - dimension_table_2_key_b

dimensions:

  # Dimension referencing a join column from dimension_table_1 using dot notation
  - name: Dimension table 1 key
    expr: dimension_table_1.pk

measures:

  # Measure referencing a join column from dimension_table_1
  - name: Count of dimension table 1 keys
    expr: COUNT(dimension_table_1.pk)

```

Note

The `source` namespace references columns from the metric view's source, while the join `name` refers to columns from the joined table. For example, in the join condition `source.dimension_table_1_fk = dimension_table_1.pk`, `source` refers to the metric view's source table (`fact_table`), and `dimension_table_1` refers to the joined table. The reference defaults to the join table if no prefix is provided in an `on` clause.

## Model snowflake schema

A snowflake schema extends a star schema by normalizing dimension tables and connecting them to subdimensions. This creates a multi-level join structure that can match the depth of your data model.

Note

Snowflake joins require Databricks Runtime compute 17.1 and above.

To define a join that models a snowflake schema:

1. Create a metric view.
2. Add first-level (star schema) joins.
3. Join with other dimension tables.
4. Expose nested dimensions by adding dimensions in your view.

The following example uses the TPCH dataset to illustrate how to model a snowflake schema. The TPCH dataset can be accessed in the `samples` catalog in your Azure Databricks workspace.

```yaml
source: samples.tpch.orders

joins:
  - name: customer
    source: samples.tpch.customer
    on: source.o_custkey = customer.c_custkey
    joins:
      - name: nation
        source: samples.tpch.nation
        on: customer.c_nationkey = nation.n_nationkey
        joins:
          - name: region
            source: samples.tpch.region
            on: nation.n_regionkey = region.r_regionkey

dimensions:
  - name: clerk
    expr: o_clerk
  - name: customer
    expr: customer # returns the full customer row as a struct
  - name: customer_name
    expr: customer.c_name
  - name: nation
    expr: customer.nation
  - name: nation_name
    expr: customer.nation.n_name
```