---
layout: Conceptual
title: ORDER BY keyword (DAX) - DAX | Microsoft Learn
canonicalUrl: https://learn.microsoft.com/en-us/dax/orderby-statement-dax
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
description: 'Learn more about: ORDER BY'
locale: en-us
document_id: 28adbb4c-479d-b4e2-5fef-ee47b2e4a11f
document_version_independent_id: e43a8d73-7a6c-8568-956b-e57f0d868567
updated_at: 2026-01-20T22:02:00.0000000Z
original_content_git_url: https://github.com/MicrosoftDocs/query-docs-pr/blob/live/query-languages/dax/orderby-statement-dax.md
gitcommit: https://github.com/MicrosoftDocs/query-docs-pr/blob/3936ccf820b947b3e91a8dbde99be167165f52df/query-languages/dax/orderby-statement-dax.md
git_commit_id: 3936ccf820b947b3e91a8dbde99be167165f52df
site_name: Docs
depot_name: MSDN.dax
page_type: conceptual
toc_rel: toc.json
pdf_url_template: https://learn.microsoft.com/pdfstore/en-us/MSDN.dax/{branchName}{pdfName}
feedback_product_url: ''
feedback_help_link_type: ''
feedback_help_link_url: ''
word_count: 87
asset_id: orderby-statement-dax
moniker_range_name: 
monikers: []
item_type: Content
source_path: query-languages/dax/orderby-statement-dax.md
cmProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/8b896464-3b7d-4e1f-84b0-9bb45aeb5f64
- https://microsoft-devrel.poolparty.biz/DevRelOfferingOntology/73d288b3-5f0b-439f-9063-286cbe262b41
- https://authoring-docs-microsoft.poolparty.biz/devrel/8e3fdb08-a059-4277-98f6-c0e21e940707
spProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/b1d2d671-9549-46e8-918c-24349120dbf5
- https://microsoft-devrel.poolparty.biz/DevRelOfferingOntology/7b0c94d5-593e-4a2e-9007-2f991aa523ef
- https://authoring-docs-microsoft.poolparty.biz/devrel/88291526-9c74-4f87-878c-de0a82134421
platformId: 2fed2940-9519-5571-016b-760ad645f034
---

# ORDER BY keyword (DAX) - DAX | Microsoft Learn

Introduces a statement that defines sort order of query results returned by an EVALUATE statement in a [DAX query](dax-queries).

## Syntax

```dax
[ORDER BY {<expression> [{ASC | DESC}]}[, …]]
```

### Parameters

| Term | Definition |
| --- | --- |
| `expression` | Any DAX expression that returns a single scalar value. |
| `ASC` | (default) Ascending sort order. |
| `DESC` | Descending sort order. |

## Return value

The result of an EVALUATE statement in ascending (ASC) or descending (DESC) order.

## Remarks

To learn more about how ORDER BY statements are used, see [DAX queries](dax-queries).