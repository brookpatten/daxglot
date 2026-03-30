---
layout: Conceptual
title: START AT keyword (DAX) - DAX | Microsoft Learn
canonicalUrl: https://learn.microsoft.com/en-us/dax/startat-statement-dax
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
description: 'Learn more about: START AT'
locale: en-us
document_id: 0bb3874e-0020-16c1-e2fc-7d703e5dad68
document_version_independent_id: 0bb3874e-0020-16c1-e2fc-7d703e5dad68
updated_at: 2026-01-20T22:02:00.0000000Z
original_content_git_url: https://github.com/MicrosoftDocs/query-docs-pr/blob/live/query-languages/dax/startat-statement-dax.md
gitcommit: https://github.com/MicrosoftDocs/query-docs-pr/blob/b9df863e8f9a5ee172514176cc6cd1b35dc50d37/query-languages/dax/startat-statement-dax.md
git_commit_id: b9df863e8f9a5ee172514176cc6cd1b35dc50d37
site_name: Docs
depot_name: MSDN.dax
page_type: conceptual
toc_rel: toc.json
pdf_url_template: https://learn.microsoft.com/pdfstore/en-us/MSDN.dax/{branchName}{pdfName}
feedback_product_url: ''
feedback_help_link_type: ''
feedback_help_link_url: ''
word_count: 170
asset_id: startat-statement-dax
moniker_range_name: 
monikers: []
item_type: Content
source_path: query-languages/dax/startat-statement-dax.md
cmProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/8b896464-3b7d-4e1f-84b0-9bb45aeb5f64
spProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/b1d2d671-9549-46e8-918c-24349120dbf5
platformId: 6320ef88-9c68-caf2-068b-b32656ae1e10
---

# START AT keyword (DAX) - DAX | Microsoft Learn

Introduces a statement that defines the starting value at which the query results of an ORDER BY clause in an EVALUATE statement in a [DAX query](dax-queries) are returned.

## Syntax

```dax
[START AT {<value>|<parameter>} [, …]]
```

## Parameters

| Term | Definition |
| --- | --- |
| `value` | A constant value. Cannot be an expression. |
| `parameter` | The name of a parameter in an XMLA statement prefixed with an `@` character. |

## Remarks

- START AT arguments have a one-to-one correspondence with the columns in the ORDER BY statement. There can be as many arguments in the START AT statement as there are in the ORDER BY statement, but not more. The first argument in the START AT statement defines the starting value in column 1 of the ORDER BY columns. The second argument in the START AT statement defines the starting value in column 2 of the ORDER BY columns within the rows that meet the first value for column 1.
- To learn more about how START AT statements are used, see [DAX queries](dax-queries).