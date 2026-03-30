---
layout: Conceptual
title: EVALUATE keyword (DAX) - DAX | Microsoft Learn
canonicalUrl: https://learn.microsoft.com/en-us/dax/evaluate-statement-dax
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
description: 'Learn more about: EVALUATE'
locale: en-us
document_id: 4ec60550-662a-97a9-4ec7-ad5b143902ca
document_version_independent_id: f0b4acbf-a24a-82f2-88d4-e4b3fd61b335
updated_at: 2026-01-13T22:02:00.0000000Z
original_content_git_url: https://github.com/MicrosoftDocs/query-docs-pr/blob/live/query-languages/dax/evaluate-statement-dax.md
gitcommit: https://github.com/MicrosoftDocs/query-docs-pr/blob/db4161bd161a16808f41898383ed50e440b52823/query-languages/dax/evaluate-statement-dax.md
git_commit_id: db4161bd161a16808f41898383ed50e440b52823
site_name: Docs
depot_name: MSDN.dax
page_type: conceptual
toc_rel: toc.json
pdf_url_template: https://learn.microsoft.com/pdfstore/en-us/MSDN.dax/{branchName}{pdfName}
feedback_product_url: ''
feedback_help_link_type: ''
feedback_help_link_url: ''
word_count: 78
asset_id: evaluate-statement-dax
moniker_range_name: 
monikers: []
item_type: Content
source_path: query-languages/dax/evaluate-statement-dax.md
cmProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/8b896464-3b7d-4e1f-84b0-9bb45aeb5f64
spProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/b1d2d671-9549-46e8-918c-24349120dbf5
platformId: 325135d6-0b20-f524-d7c7-359c4236bd5a
---

# EVALUATE keyword (DAX) - DAX | Microsoft Learn

Introduces a statement containing a table expression required in a [DAX query](dax-queries).

## Syntax

```dax
EVALUATE <table>
```

## Parameters

| Term | Definition |
| --- | --- |
| `table` | A table expression |

## Return value

The result of a table expression.

## Remarks

- A DAX query can contain multiple EVALUATE statements.
- To learn more about how EVALUATE statements are used, see [DAX queries](dax-queries).

## Example

```dax
EVALUATE
    'Internet Sales'
```

Returns all rows and columns from the Internet Sales table, as a table.