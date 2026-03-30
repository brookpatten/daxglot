---
layout: Conceptual
title: New DAX functions - DAX | Microsoft Learn
canonicalUrl: https://learn.microsoft.com/en-us/dax/new-dax-functions
feedback_system: Standard
breadcrumb_path: /dax/breadcrumb/toc.json
uhfHeaderId: MSDocsHeader-DAX
ms.service: powerbi
ms.subservice: dax
ms.topic: whats-new
ms.author: jterh
author: jeroenterheerdt
recommendations: false
ms.date: 2023-10-20T00:00:00.0000000Z
show_latex: true
description: 'Learn more about: New DAX functions'
locale: en-us
document_id: 00edfc61-f50f-abb9-63a2-92cafbdaf981
document_version_independent_id: 3af9e459-bb2f-84d3-cebc-15fe3c8397a2
updated_at: 2026-02-10T18:05:00.0000000Z
original_content_git_url: https://github.com/MicrosoftDocs/query-docs-pr/blob/live/query-languages/dax/new-dax-functions.md
gitcommit: https://github.com/MicrosoftDocs/query-docs-pr/blob/5f3cd5868d3e011d5dd802f12bcef911284843a8/query-languages/dax/new-dax-functions.md
git_commit_id: 5f3cd5868d3e011d5dd802f12bcef911284843a8
site_name: Docs
depot_name: MSDN.dax
page_type: conceptual
toc_rel: toc.json
pdf_url_template: https://learn.microsoft.com/pdfstore/en-us/MSDN.dax/{branchName}{pdfName}
feedback_product_url: ''
feedback_help_link_type: ''
feedback_help_link_url: ''
word_count: 484
asset_id: new-dax-functions
moniker_range_name: 
monikers: []
item_type: Content
source_path: query-languages/dax/new-dax-functions.md
cmProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/540ac133-a371-4dbb-8f94-28d6cc77a70b
spProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/60bfc045-f127-4841-9d00-ea35495a5800
platformId: 0b862f6e-e40b-3805-6de5-5c4d47717bcd
---

# New DAX functions - DAX | Microsoft Learn

DAX is continuously being improved with new functions and functionality to support new features. New functions and updates are included in service, application, and tool updates which in most cases are monthly.

While functions and functionality are being updated all the time, only those updates that have a visible and functional change exposed to users are described in documentation. New functions and updates to existing functions within the past year are shown here.

Important

Not all functions are supported in all versions of Power BI Desktop, Analysis Services, and Power Pivot in Excel. New and updated functions are typically first introduced in Power BI Desktop, and then later in Analysis Services, Power Pivot in Excel, and tools.

## New functions

| Function | Month | Description |
| --- | --- | --- |
| [TABLEOF](tableof-function-dax) | February, 2026 | Returns a reference to the table associated with a specified column, measure, or calendar. |
| [TOTALWTD](totalwtd-function-dax) | September, 2025 | Calculates the running total of a measure to the current week in the filter context. |
| [CLOSINGBALANCEWEEK](closingbalanceweek-function-dax) | September, 2025 | Returns the closing balance for the week in the current context. |
| [ENDOFWEEK](endofweek-function-dax) | September, 2025 | Returns the last date of the current week in the calendar. |
| [NEXTWEEK](nextweek-function-dax) | September, 2025 | Returns a table that contains a column of dates for the next week. |
| [OPENINGBALANCEWEEK](openingbalanceweek-function-dax) | September, 2025 | Returns the opening balance for the week in the current context. |
| [PREVIOUSWEEK](previousweek-function-dax) | September, 2025 | Returns a table that contains a column of dates for the previous week. |
| [STARTOFWEEK](startofweek-function-dax) | September, 2025 | Returns the first date of the current week in the calendar. |
| [LOOKUPWITHTOTALS](lookupwithtotals-function-dax) | June, 2025 | Used in visual calculations only. Look up the value when filters are applied. Filters not specified would not be inferred. |
| [LOOKUP](lookup-function-dax) | June, 2025 | Used in visual calculations only. Look up the value when filters are applied. |
| [FIRST](first-function-dax) | January, 2024 | Used in visual calculations only. Retrieves a value in the visual matrix from the first row of an axis. |
| [LAST](last-function-dax) | January, 2024 | Used in visual calculations only. Retrieves a value in the visual matrix from the last row of an axis. |
| [NEXT](next-function-dax) | January, 2024 | Used in visual calculations only. Retrieves a value in the next row of an axis in the visual matrix. |
| [PREVIOUS](previous-function-dax) | January, 2024 | Used in visual calculations only. Retrieves a value in the previous row of an axis in the visual matrix. |
| [MATCHBY](matchby-function-dax) | May, 2023 | Define the columns that are used to to match data and identify the current row, in a window function expression. |
| [RANK](rank-function-dax) | April, 2023 | Returns the ranking for the current context within the specified partition, sorted by the specified order. |
| [ROWNUMBER](rownumber-function-dax) | April, 2023 | Returns the unique ranking for the current context within the specified partition, sorted by the specified order. |
| [LINEST](linest-function-dax) | February, 2023 | Uses the Least Squares method to calculate a straight line that best fits the given data. |
| [LINESTX](linestx-function-dax) | February, 2023 | Uses the Least Squares method to calculate a straight line that best fits the given data. The data result from expressions evaluated for each row in a table. |