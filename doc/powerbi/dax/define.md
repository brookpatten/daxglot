---
layout: Conceptual
title: DEFINE keyword (DAX) - DAX | Microsoft Learn
canonicalUrl: https://learn.microsoft.com/en-us/dax/define-statement-dax
feedback_system: Standard
breadcrumb_path: /dax/breadcrumb/toc.json
uhfHeaderId: MSDocsHeader-DAX
ms.service: powerbi
ms.subservice: dax
ms.topic: reference
ms.author: jterh
author: jeroenterheerdt
recommendations: false
ms.date: 2023-10-20T00:00:00.0000000Z
show_latex: true
description: 'Learn more about: DEFINE'
locale: en-us
document_id: 7756922e-a045-4449-35be-d0b6680f3143
document_version_independent_id: 58e712eb-cc09-62f6-b8e2-086b0e085870
updated_at: 2026-01-13T22:02:00.0000000Z
original_content_git_url: https://github.com/MicrosoftDocs/query-docs-pr/blob/live/query-languages/dax/define-statement-dax.md
gitcommit: https://github.com/MicrosoftDocs/query-docs-pr/blob/db4161bd161a16808f41898383ed50e440b52823/query-languages/dax/define-statement-dax.md
git_commit_id: db4161bd161a16808f41898383ed50e440b52823
site_name: Docs
depot_name: MSDN.dax
page_type: conceptual
toc_rel: toc.json
pdf_url_template: https://learn.microsoft.com/pdfstore/en-us/MSDN.dax/{branchName}{pdfName}
feedback_product_url: ''
feedback_help_link_type: ''
feedback_help_link_url: ''
word_count: 344
asset_id: define-statement-dax
moniker_range_name: 
monikers: []
item_type: Content
source_path: query-languages/dax/define-statement-dax.md
cmProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/8b896464-3b7d-4e1f-84b0-9bb45aeb5f64
- https://authoring-docs-microsoft.poolparty.biz/devrel/540ac133-a371-4dbb-8f94-28d6cc77a70b
spProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/b1d2d671-9549-46e8-918c-24349120dbf5
- https://authoring-docs-microsoft.poolparty.biz/devrel/60bfc045-f127-4841-9d00-ea35495a5800
platformId: 0df1a81b-d853-2b19-6ec6-2eb907b8aa5a
---

# DEFINE keyword (DAX) - DAX | Microsoft Learn

Introduces a statement with one or more entity definitions that can be applied to one or more EVALUATE statements of a [DAX query](dax-queries).

## Syntax

```dax
[DEFINE 
    (
     (COLUMN <table name>[<column name>] = <scalar expression>) |
     (FUNCTION <function name> = ([parameter name]: [parameter type], ...) => <function body>) |
     (MEASURE <table name>[<measure name>] = <scalar expression>) | 
     (TABLE <table name> = <virtual table definition>) | 
     (VAR <var name> = <table or scalar expression>) |
    ) + 
]

(EVALUATE <table expression>) +
```

### Parameters

| Term | Definition |
| --- | --- |
| `Entity` | COLUMN^1^, FUNCTION, MEASURE, TABLE^1^, or VAR. |
| `name` | The name of a column, function, measure, table, or var definition. It cannot be an expression. The name does not have to be unique. The name exists only for the duration of the query. |
| `expression` | Any DAX expression that returns a table or scalar value. The expression can use any of the defined entities. If there is a need to convert a scalar expression into a table expression, wrap the expression inside a table constructor with curly braces `{}`, or use the `ROW()` function to return a single row table. |
| `parameter type`, `parameter name`, `function body` | See [FUNCTION statement](function-statement-dax). |

[1]**Caution:** Query scoped TABLE and COLUMN definitions are meant for internal use only. While you can define TABLE and COLUMN expressions for a query without syntax error, they may produce runtime errors and are not recommended.

## Remarks

- A DAX query can have multiple EVALUATE statements, but can have only one DEFINE statement. Definitions in the DEFINE statement can apply to any EVALUATE statements in the query.
- At least one definition is required in a DEFINE statement.
- Measure definitions for a query override model measures of the same name.
- VAR names have unique restrictions. To learn more, see [VAR - Parameters](var-dax#parameters).
- To learn more about how a DEFINE statement is used, see [DAX queries](dax-queries).
- To learn more about virtual column, see [Virtual Column](virtual-column-statement-dax)
- To learn more about virtual table, see [Virtual Table](virtual-table-statement-dax)
- To learn more about DAX user defined functions, see [DAX User Defined Functions](function-statement-dax)