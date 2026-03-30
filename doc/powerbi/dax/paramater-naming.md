---
layout: Conceptual
title: DAX parameter-naming conventions - DAX | Microsoft Learn
canonicalUrl: https://learn.microsoft.com/en-us/dax/dax-parameter-naming-conventions
feedback_system: Standard
breadcrumb_path: /dax/breadcrumb/toc.json
uhfHeaderId: MSDocsHeader-DAX
ms.service: powerbi
ms.subservice: dax
ms.topic: concept-article
ms.author: jterh
author: jeroenterheerdt
recommendations: false
ms.date: 2023-10-20T00:00:00.0000000Z
show_latex: true
description: 'Learn more about: DAX parameter-naming conventions'
locale: en-us
document_id: b41d03f4-6748-a864-7e8a-1cdb8477c97a
document_version_independent_id: 6bc54f5b-1abf-b6b1-26d0-a6922e6aa850
updated_at: 2026-01-13T22:02:00.0000000Z
original_content_git_url: https://github.com/MicrosoftDocs/query-docs-pr/blob/live/query-languages/dax/dax-parameter-naming-conventions.md
gitcommit: https://github.com/MicrosoftDocs/query-docs-pr/blob/db4161bd161a16808f41898383ed50e440b52823/query-languages/dax/dax-parameter-naming-conventions.md
git_commit_id: db4161bd161a16808f41898383ed50e440b52823
site_name: Docs
depot_name: MSDN.dax
page_type: conceptual
toc_rel: toc.json
pdf_url_template: https://learn.microsoft.com/pdfstore/en-us/MSDN.dax/{branchName}{pdfName}
feedback_product_url: ''
feedback_help_link_type: ''
feedback_help_link_url: ''
word_count: 329
asset_id: dax-parameter-naming-conventions
moniker_range_name: 
monikers: []
item_type: Content
source_path: query-languages/dax/dax-parameter-naming-conventions.md
cmProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/8b896464-3b7d-4e1f-84b0-9bb45aeb5f64
spProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/b1d2d671-9549-46e8-918c-24349120dbf5
platformId: 72d5a061-8a30-edad-ad76-7048914f66c6
---

# DAX parameter-naming conventions - DAX | Microsoft Learn

Parameter names are standardized in DAX reference to facilitate the usage and understanding of the functions.

## Parameter names

| Term | Definition |
| --- | --- |
| `expression` | Any DAX expression that returns a single scalar value, where the expression is to be evaluated multiple times (for each row/context). |
| `value` | Any DAX expression that returns a single scalar value where the expression is to be evaluated exactly once before all other operations. |
| `table` | Any DAX expression that returns a table of data. |
| `tableName` | The name of an existing table using standard DAX syntax. It cannot be an expression. |
| `columnName` | The name of an existing column using standard DAX syntax, usually fully qualified. It cannot be an expression. |
| `name` | A string constant that will be used to provide the name of a new object. |
| `order` | An enumeration used to determine the sort order. |
| `ties` | An enumeration used to determine the handling of tie values. |
| `type` | An enumeration used to determine the data type for PathItem and PathItemReverse. |

### Prefixing parameter names or using the prefix only

| Term | Definition |
| --- | --- |
| `prefixing` | Parameter names may be further qualified with a prefix that is descriptive of how the argument is used and to avoid ambiguous reading of the parameters. For example:Result\_ColumnName - Refers to an existing column used to get the result values in the LOOKUPVALUE() function.Search\_ColumnName - Refers to an existing column used to search for a value in the LOOKUPVALUE() function. |
| `omitting` | Parameter names will be omitted if the prefix is clear enough to describe the parameter.For example, instead of having the following syntax DATE (Year\_Value, Month\_Value, Day\_Value) it is clearer for the user to read DATE (Year, Month, Day); repeating three times the suffix value does not add anything to a better comprehension of the function and it clutters the reading unnecessarily.However, if the prefixed parameter is Year\_columnName then the parameter name and the prefix will stay to make sure the user understands that the parameter requires a reference to an existing column of Years. |