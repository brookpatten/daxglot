---
layout: Conceptual
title: MEASURE keyword (DAX) - DAX | Microsoft Learn
canonicalUrl: https://learn.microsoft.com/en-us/dax/measure-statement-dax
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
description: 'Learn more about: MEASURE'
locale: en-us
document_id: f7e4ff19-5374-4098-9b4a-66d1e178923f
document_version_independent_id: f7e4ff19-5374-4098-9b4a-66d1e178923f
updated_at: 2026-01-13T22:02:00.0000000Z
original_content_git_url: https://github.com/MicrosoftDocs/query-docs-pr/blob/live/query-languages/dax/measure-statement-dax.md
gitcommit: https://github.com/MicrosoftDocs/query-docs-pr/blob/15cde6f5b2e8ae300d18f9a79a80f73bc51e47f0/query-languages/dax/measure-statement-dax.md
git_commit_id: 15cde6f5b2e8ae300d18f9a79a80f73bc51e47f0
site_name: Docs
depot_name: MSDN.dax
page_type: conceptual
toc_rel: toc.json
pdf_url_template: https://learn.microsoft.com/pdfstore/en-us/MSDN.dax/{branchName}{pdfName}
feedback_product_url: ''
feedback_help_link_type: ''
feedback_help_link_url: ''
word_count: 147
asset_id: measure-statement-dax
moniker_range_name: 
monikers: []
item_type: Content
source_path: query-languages/dax/measure-statement-dax.md
cmProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/8b896464-3b7d-4e1f-84b0-9bb45aeb5f64
spProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/b1d2d671-9549-46e8-918c-24349120dbf5
platformId: b6e2e3f9-4d85-6aec-cd59-1b65678b4fbf
---

# MEASURE keyword (DAX) - DAX | Microsoft Learn

Introduces a measure definition in a DEFINE statement of a [DAX query](dax-queries).

## Syntax

```dax
[DEFINE 
    (
      MEASURE <table name>[<measure name>] = <scalar expression>
    ) + 
]

(EVALUATE <table expression>) +
```

### Parameters

| Term | Definition |
| --- | --- |
| `table name` | The name of a table containing the measure. |
| `measure name` | The name of the measure. It cannot be an expression. The name does not have to be unique. The name exists only for the duration of the query. |
| `scalar expression` | A DAX expression that returns a scalar value. |

## Return value

The calculated result of the measure expression.

## Remarks

- Measure definitions for a query override model measures of the same name for the duration of the query. They will not affect the model measure.
- The measure expression can be used with any other expression in the same query.
- To learn more about how MEASURE statements are used, see [DAX queries](dax-queries).