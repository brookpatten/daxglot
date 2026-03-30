---
layout: Conceptual
title: FUNCTION keyword (DAX) - DAX | Microsoft Learn
canonicalUrl: https://learn.microsoft.com/en-us/dax/function-statement-dax
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
description: 'Learn more about: FUNCTION'
locale: en-us
document_id: 9924e442-26c6-3e17-4cf8-672bd8c766b0
document_version_independent_id: 9924e442-26c6-3e17-4cf8-672bd8c766b0
updated_at: 2026-01-13T22:02:00.0000000Z
original_content_git_url: https://github.com/MicrosoftDocs/query-docs-pr/blob/live/query-languages/dax/function-statement-dax.md
gitcommit: https://github.com/MicrosoftDocs/query-docs-pr/blob/2635fa31dbc6fff9dfe349714b51805a511008c4/query-languages/dax/function-statement-dax.md
git_commit_id: 2635fa31dbc6fff9dfe349714b51805a511008c4
site_name: Docs
depot_name: MSDN.dax
page_type: conceptual
toc_rel: toc.json
pdf_url_template: https://learn.microsoft.com/pdfstore/en-us/MSDN.dax/{branchName}{pdfName}
feedback_product_url: ''
feedback_help_link_type: ''
feedback_help_link_url: ''
word_count: 173
asset_id: function-statement-dax
moniker_range_name: 
monikers: []
item_type: Content
source_path: query-languages/dax/function-statement-dax.md
cmProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/540ac133-a371-4dbb-8f94-28d6cc77a70b
spProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/60bfc045-f127-4841-9d00-ea35495a5800
platformId: bfad44fe-a529-ab72-3ffe-d48fbbed1ee0
---

# FUNCTION keyword (DAX) - DAX | Microsoft Learn

Introduces a function definition in a DEFINE statement of a [DAX query](dax-queries).

## Syntax

```dax
[DEFINE 
    (
      FUNCTION <function name> = ([parameter name] : [parameter type] [parameter subtype] [parameter passing mode], ...) => <function body>
    ) + 
]

(EVALUATE <table expression>) +
```

### Parameters

| Term | Definition |
| --- | --- |
| `function name` | The name of a function. |
| `parameter name` | The name of the parameter. This cannot be a reserved keyword such as `measure`. |
| `parameter type` | `anyval`, `scalar`, `table` or `anyref`. `Anyval` is an abstract type for `scalar` or `table`. `Anyref` is an abstract type for all references. |
| `parameter subtype` | applies only to `parameter type` = `scalar`. Can be one of the following: `boolean`, `datetime`, `decimal`, `double`, `int64`, `numeric`, `string`, `variant`. |
| `parameter passing mode` | `val` (eargerly evaluated) or `expr` (lazily evaluated). |
| `function body` | A DAX expression for the function. |

## Return value

The calculated result of the function body.

## Remarks

- To learn more about DAX User Defined Functions, see [DAX User Defined Functions](best-practices/dax-user-defined-functions).
- To learn more about how FUNCTION statements are used, see [DAX queries](dax-queries).