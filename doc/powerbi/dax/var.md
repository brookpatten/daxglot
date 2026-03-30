---
layout: Conceptual
title: VAR keyword (DAX) - DAX | Microsoft Learn
canonicalUrl: https://learn.microsoft.com/en-us/dax/var-dax
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
description: 'Learn more about: VAR'
locale: en-us
document_id: 5bd7887f-e790-e9c8-c49f-93d0b3634233
document_version_independent_id: 782f8973-8dbe-dbc7-c587-d8a32c0b493c
updated_at: 2026-01-20T22:02:00.0000000Z
original_content_git_url: https://github.com/MicrosoftDocs/query-docs-pr/blob/live/query-languages/dax/var-dax.md
gitcommit: https://github.com/MicrosoftDocs/query-docs-pr/blob/28fcd46236b720119a14e4b68dfa608ea997186a/query-languages/dax/var-dax.md
git_commit_id: 28fcd46236b720119a14e4b68dfa608ea997186a
site_name: Docs
depot_name: MSDN.dax
page_type: conceptual
toc_rel: toc.json
pdf_url_template: https://learn.microsoft.com/pdfstore/en-us/MSDN.dax/{branchName}{pdfName}
feedback_product_url: ''
feedback_help_link_type: ''
feedback_help_link_url: ''
word_count: 459
asset_id: var-dax
moniker_range_name: 
monikers: []
item_type: Content
source_path: query-languages/dax/var-dax.md
cmProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/8b896464-3b7d-4e1f-84b0-9bb45aeb5f64
spProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/b1d2d671-9549-46e8-918c-24349120dbf5
platformId: a7327ec7-8846-1441-8314-d7f95fa493f0
---

# VAR keyword (DAX) - DAX | Microsoft Learn

Stores the result of an expression as a named variable, which can then be passed as an argument to other measure expressions. Once resultant values have been calculated for a variable expression, those values do not change, even if the variable is referenced in another expression.

## Syntax

```dax
VAR <name> = <expression>
```

### Parameters

| Term | Definition |
| --- | --- |
| `name` | The name of the variable (identifier).Delimiters are not supported. For example, 'varName' or [varName] will result in an error.Supported character set: a-z, A-Z, 0-9. 0-9 are not valid as first character.\_\_ (double underscore) is allowed as a prefix to the identifier name.No other special characters are supported.Reserved keywords not allowed.Names of existing tables are not allowed.Empty spaces are not allowed. |
| `expression` | A DAX expression which returns a scalar or table value. |

## Return value

A named variable containing the result of the expression argument.

## Remarks

- An expression passed as an argument to VAR can contain another VAR declaration.
- When referencing a variable:

    - Measures cannot refer to variables defined outside the measure expression, but can refer to functional scope variables defined within the expression.
    - Variables can refer to measures.
    - Variables can refer to previously defined variables.
    - Columns in table variables cannot be referenced via TableName[ColumnName] syntax.
- For best practices when using VAR, see [Use variables to improve your DAX formulas](best-practices/dax-variables).
- To learn more about how VAR is used within a DAX Query, see [DAX queries](dax-queries).

## Example

To calculate a percentage of year-over-year growth without using a variable, you could create three separate measures. This first measure calculates Sum of Sales Amount:

```dax
Sum of Sales Amount =
SUM ( Sales[Sales Amount] )
```

A second measure calculates the sales amount for the previous year:

```dax
Sales Amount PreviousYear =
CALCULATE ( [Sum of Sales Amount], SAMEPERIODLASTYEAR ( 'Date'[Date] ) )
```

You can then create a third measure that combines the other two measures to calculate a growth percentage. Notice the Sum of SalesAmount measure is used in two places; first to determine if there is a sale, then again to calculate a percentage.

```dax
Sum of SalesAmount YoY%: =
IF (
    [Sum of Sales Amount] && [Sales Amount PreviousYear],
    DIVIDE (
        ( [Sum of Sales Amount] - [Sales Amount PreviousYear] ),
        [Sales Amount PreviousYear]
    )
)
```

By using a variable, you can create a single measure that calculates the same result:

```dax
YoY% =
VAR Sales =
    SUM ( Sales[Sales Amount] )
VAR SalesLastYear =
    CALCULATE ( SUM ( Sales[Sales Amount] ), SAMEPERIODLASTYEAR ( 'Date'[Date] ) )
RETURN
    IF ( Sales && SalesLastYear, DIVIDE ( Sales - SalesLastYear, SalesLastYear ) )
```

By using a variable, you can get the same outcome, but in a more readable way. And because the result of the expression is stored in the variable, the measure's performance can be significantly improved because it doesn't have to be recalculated each time it's used.