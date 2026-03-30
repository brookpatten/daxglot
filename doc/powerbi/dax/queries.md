---
layout: Conceptual
title: DAX Queries - DAX | Microsoft Learn
canonicalUrl: https://learn.microsoft.com/en-us/dax/dax-queries
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
description: Describes Data Analysis Expressions (DAX) language queries.
locale: en-us
document_id: c57618d2-a2cb-979a-b0bc-fbed90795a87
document_version_independent_id: 669ccdb8-cf73-c4ff-a4e7-c578dd7ea98b
updated_at: 2026-01-22T22:02:00.0000000Z
original_content_git_url: https://github.com/MicrosoftDocs/query-docs-pr/blob/live/query-languages/dax/dax-queries.md
gitcommit: https://github.com/MicrosoftDocs/query-docs-pr/blob/5de07c5f6344cc2f77a3553a74fa1fd3e70a5911/query-languages/dax/dax-queries.md
git_commit_id: 5de07c5f6344cc2f77a3553a74fa1fd3e70a5911
site_name: Docs
depot_name: MSDN.dax
page_type: conceptual
toc_rel: toc.json
pdf_url_template: https://learn.microsoft.com/pdfstore/en-us/MSDN.dax/{branchName}{pdfName}
feedback_product_url: ''
feedback_help_link_type: ''
feedback_help_link_url: ''
word_count: 1841
asset_id: dax-queries
moniker_range_name: 
monikers: []
item_type: Content
source_path: query-languages/dax/dax-queries.md
cmProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/8b896464-3b7d-4e1f-84b0-9bb45aeb5f64
- https://authoring-docs-microsoft.poolparty.biz/devrel/d3197845-b4ce-44c6-a237-cd4be160e76c
- https://authoring-docs-microsoft.poolparty.biz/devrel/540ac133-a371-4dbb-8f94-28d6cc77a70b
spProducts:
- https://authoring-docs-microsoft.poolparty.biz/devrel/b1d2d671-9549-46e8-918c-24349120dbf5
- https://authoring-docs-microsoft.poolparty.biz/devrel/aea905fb-0a9d-4d46-b30f-e9cbaf772d1b
- https://authoring-docs-microsoft.poolparty.biz/devrel/60bfc045-f127-4841-9d00-ea35495a5800
platformId: 5dadc7a6-34df-6dc0-2a30-e48c62576b16
---

# DAX Queries - DAX | Microsoft Learn

Reporting clients like Power BI and Excel execute DAX queries whenever visuals display in a report, or a field added to a table, and these DAX queries adjust when a filter is applied. The [performance analyzer](/en-us/power-bi/create-reports/desktop-performance-analyzer) in Power BI Desktop can show you these DAX queries and even run them in DAX query view of Power BI Desktop.

By using [DAX query view](/en-us/power-bi/transform-model/dax-query-view) in Power BI Desktop or [Write DAX queries](/en-us/power-bi/transform-model/dax-query-view#dax-query-view-in-web) in Power BI service, you can create and run your own DAX queries. With [Microsoft Fabric](/en-us/fabric/get-started/microsoft-fabric-overview), you can further increase your productivity with [Copilot to write DAX queries](/en-us/dax/dax-copilot) in DAX query view of Desktop or web. In addition to Power BI tools, DAX queries can be run in [Fabric notebooks](/en-us/fabric/data-engineering/how-to-use-notebook) using [semantic link](/en-us/fabric/data-science/read-write-power-bi-python) to read data from semantic models with python, and with the [Execute Queries REST API](/en-us/rest/api/power-bi/datasets/execute-queries), also available in [Power Automate](https://powerbi.microsoft.com/blog/unlocking-new-self-service-bi-scenarios-with-executequeries-support-in-power-automate/). Other tools such as [SQL Server Management Studio](/en-us/sql/ssms/download-sql-server-management-studio-ssms) (SSMS), [Power BI Report Builder](/en-us/power-bi/paginated-reports/report-builder-power-bi), and open-source tools like [DAX Studio](https://daxstudio.org), also allow you to create and run DAX queries.

DAX queries return results as a table right within the tool, allowing you to quickly create and test the performance of your DAX formulas in measures or simply view the data in your semantic model. INFO and INFO.VIEW DAX functions can also get information about your semantic model, such as a listing of tables, columns, measures, and much more.

Before learning about queries, it is important you have a solid understanding of DAX basics. If you haven't already, be sure to check out [DAX overview](dax-overview).

## Keywords

DAX queries have a simple syntax comprised of just one required keyword, EVALUATE. EVALUATE is followed by a table expression, such as a DAX function or table name, that when run outputs a result table. Table expressions that output a result table include:

1. Common DAX functions that output a table, such as [SUMMARIZE](summarize-function-dax), [SUMMARIZECOLUMNS](summarizecolumns-function-dax), [SELECTCOLUMNS](selectcolumns-function-dax), [FILTER](filter-function-dax), [UNION](union-function-dax), [TOPN](topn-function-dax), [ADDCOLUMNS](addcolumns-function-dax), [DATATABLE](datatable-function-dax), and many others, work with EVALUATE to output a result table.
2. Tables in the model when referenced by name work with EVALUATE to output a result table showing the data in the table. For example, **EVALUATE ‘Table name’** can be ran as a DAX query.
3. Measures in the model or any DAX formula, which return a scalar value, work with EVALUATE to show the value as a result table when enclosed in curly braces. For example, **EVALUATE {[Total Sales]}** or **EVALUATE {COUNTROWS(‘Sales’)}** can be ran as a DAX query. These are called [table constructors](table-constructor).

There are several optional keywords specific to DAX queries: ORDER BY, START AT, DEFINE, MEASURE, VAR, TABLE, and COLUMN.

### EVALUATE (Required)

At the most basic level, a DAX query is an `EVALUATE` statement containing a table expression. At least one EVALUATE statement is required, however, a query can contain any number of EVALUATE statements.

#### EVALUATE Syntax

```dax
EVALUATE <table>
```

#### EVALUATE Parameters

| Term | Definition |
| --- | --- |
| `table` | A table expression. |

#### EVALUATE Example

```dax
EVALUATE'Sales Order'
```

Returns all rows and columns from the Sales Order table, as a result table. This can be limited with the use of [TOPN](topn-function-dax) or [FILTER](filter-function-dax), and sorted with ORDER BY.

[![Screenshot showing how to use EVALUATE for a DAX query in DAX query view of Power BI Desktop.](media/dax-queries/dax-evaluate.png)](media/dax-queries/dax-evaluate.png#lightbox)

### ORDER BY (Optional)

The optional `ORDER BY` keyword defines one or more columns in the query or expressions used to sort query results. Any expression that can be evaluated for each row of the result is valid. Any column in the query itself is also valid.

Sort by column property in semantic models do not apply to DAX query results. If a column should be sorted by a different column in the model, such as in the case of Month Name, the sort by column should also be included in the DAX query to be used in the ORDER BY.

#### ORDER BY Syntax

```dax
EVALUATE <table>
[ORDER BY {<expression> [{ASC | DESC}]}[, …]]
```

#### ORDER BY Parameters

| Term | Definition |
| --- | --- |
| `expression` | Any DAX expression that returns a single scalar value, or column included in the DAX query. |
| `ASC` | (default) Ascending sort order. |
| `DESC` | Descending sort order. |

#### ORDER BY Example

```dax
EVALUATESUMMARIZECOLUMNS(	// Group by columns	'Date'[Month Name],	'Date'[Month of Year],	'Product'[Category],
	// Optional filters	FILTER(		VALUES('Product'[Category]),		[Category] = "Clothing"	),
	// Measures or explicit DAX formulas to aggregate and analyze the data by row	"Orders", [Orders],	"Avg Profit per Order", DIVIDE(		[Total Sales Profit],		[Orders]	))
// DAX queries do not use sort order defined in Power BI, // sort by columns must be included in the DAX query to be used in order byORDER BY 'Date'[Month of Year] ASC
```

Returns clothing orders and average profit per order by month, in ascending order by month, as a result table.

[![Screenshot showing how to use ORDER BY for a DAX query in DAX query view of Power BI Desktop.](media/dax-queries/dax-evaluate-orderby.png)](media/dax-queries/dax-evaluate-orderby.png#lightbox)

TOPN does not choose the specified number of rows to return based on the sort order specified in ORDER BY. Instead, TOPN has its own syntax to optionally specify a sort before the top 100 rows are return. ORDER BY only sorts the result table returned by TOPN.

```dax
EVALUATETOPN(	100,	'Sales Order',	// The way the data is sorted before the top 100 rows are selected	'Sales Order'[SalesOrderLineKey], ASC)// The way the data is sorted for the resultsORDER BY	'Sales Order'[Sales Order] ASC,	'Sales Order'[Sales Order Line] ASC
```

Returns the top 100 sales orders sorted by SalesOrderLienKey ascending, then sorts the results first by sales order, then by sales order line.

[![Screenshot showing how to use TOPN and ORDER BY for a DAX query in DAX query view of Power BI Desktop.](media/dax-queries/dax-evaluate-topn.png)](media/dax-queries/dax-evaluate-topn.png#lightbox)

### START AT (Optional)

The optional `START AT` keyword is used inside an `ORDER BY` clause. It defines the value at which the query results begin.

#### START AT Syntax

```dax
EVALUATE <table>
[ORDER BY {<expression> [{ASC | DESC}]}[, …]
[START AT {<value>|<parameter>} [, …]]]
```

#### START AT Parameters

| Term | Definition |
| --- | --- |
| `value` | A constant value. Cannot be an expression. |
| `parameter` | The name of a parameter in an XMLA statement prefixed with an `@` character. |

#### START AT Remarks

START AT arguments have a one-to-one correspondence with the columns in the ORDER BY clause. There can be as many arguments in the START AT clause as there are in the ORDER BY clause, but not more. The first argument in the START AT defines the starting value in column 1 of the ORDER BY columns. The second argument in the START AT defines the starting value in column 2 of the ORDER BY columns within the rows that meet the first value for column 1.

#### START AT Example

```dax
EVALUATE'Sales Order'ORDER BY 'Sales Order'[Sales Order] ASC// Start at this order, orders before this order will not be displayedSTART AT "SO43661"
```

Returns all columns from the Sales Order table, in ascending order by Sales Order, beginning at SO43661. Rows before this sales order are not included in the result table.

[![Screenshot showing how to use ORDER BY and START AT for a DAX query in DAX query view of Power BI Desktop.](media/dax-queries/dax-evaluate-startat.png)](media/dax-queries/dax-evaluate-startat.png#lightbox)

### DEFINE (Optional)

The optional `DEFINE` keyword introduces one or more calculated entity definitions that exist only for the duration of the query. Unlike `EVALUATE`, there can only be one `DEFINE` block with one or more definitions in a DAX query. `DEFINE` must precede the first `EVALUATE` statement and are valid for all EVALUATE statements in the query. Definitions can be variables, measures, tables^1^, and columns^1^. Definitions can reference other definitions that appear before or after the current definition. At least one definition is required if the `DEFINE` keyword is included in a query.

`DEFINE MEASURE` is a common scenario to build new measures or edit existing measures in a semantic model. When the measure already exists in the model, the DAX query will use the measure DAX formula defined in the query. This is helpful for testing measures with a DAX query before updating the model.

`DEFINE MEASURE` is also helpful to build additional analysis with DAX formulas for a specific DAX query where you may not have permission to add a model measure or it is not necessary to have it in the model.

#### DEFINE Syntax

```dax
[DEFINE 
    (
     (MEASURE <table name>[<measure name>] = <scalar expression>) | 
     (VAR <var name> = <table or scalar expression>) |
     (TABLE <table name> = <virtual table definition>) | 
     (COLUMN <table name>[<column name>] = <scalar expression>) | 
    ) + 
]

(EVALUATE <table expression>) +
```

#### DEFINE Parameters

| Term | Definition |
| --- | --- |
| `Entity` | MEASURE, VAR, TABLE^1^, or COLUMN^1^. |
| `name` | The name of a measure, var, table, or column definition. It cannot be an expression. The name does not have to be unique. The name exists only for the duration of the query. |
| `expression` | Any DAX expression that returns a table or scalar value. The expression can use any of the defined entities. If there is a need to convert a scalar expression into a table expression, wrap the expression inside a table constructor with curly braces `{}`, or use the `ROW()` function to return a single row table. |

[1]**Caution:** Query scoped TABLE and COLUMN definitions are meant for internal use only. While you can define TABLE and COLUMN expressions for a query without syntax error, they may produce runtime errors and are not recommended.

#### DEFINE Remarks

- A DAX query can have multiple EVALUATE statements, but can have only one DEFINE statement. Definitions in the DEFINE statement can apply to any EVALUATE statements in the query.
- At least one definition is required in a DEFINE statement.
- Measure definitions for a query override model measures of the same name but are only used within the query. They will not affect the model measure.
- VAR names have unique restrictions. To learn more, see [VAR - Parameters](var-dax#parameters).

#### DEFINE Example

```dax
DEFINEVAR _firstyear = MIN('Date'[Fiscal Year])VAR _lastyear = MAX('Date'[Fiscal Year])TABLE 'Unbought products' = FILTER('Product', [Orders] + 0 = 0)COLUMN 'Unbought products'[Year Range] = _firstyear & " - " & _lastyearMEASURE 'Unbought products'[Unbought products] = COUNTROWS('Unbought products')
EVALUATE'Unbought products'
EVALUATE{[Unbought products]}
```

Returns the table defined in the DAX query to show unbought products with an additional defined column referencing defined variables. A measure is also defined and evaluated to count the rows of unbought products.

[![Screenshot showing how to use DEFINE for a DAX query in DAX query view of Power BI Desktop.](media/dax-queries/dax-evaluate-define.png)](media/dax-queries/dax-evaluate-define.png#lightbox)

```dax
DEFINEMEASURE 'Pick a sales measure'[Orders] = DISTINCTCOUNT('Sales Order'[Sales Order])MEASURE 'Pick a sales measure'[Customers] = CALCULATE(		COUNTROWS(Customer),		FILTER(			'Sales',			[Orders] > 0		)	)MEASURE 'Pick a sales measure'[Orders per Customer] = DIVIDE(		[Orders],		[Customers],		0	)

EVALUATESUMMARIZECOLUMNS(	'Date'[Fiscal Year],	"Orders", [Orders],	"Customers", [Customers],	"Orders per Customer", [Orders per Customer])
```

Returns a table evaluating three defined measures to show the results by fiscal year. All measures also exist in the model, and Orders per Customer is modified in the DAX query.

[![Screenshot showing how to use DEFINE MEASURE for a DAX query in DAX query view of Power BI Desktop.](media/dax-queries/dax-evaluate-define-measures.png)](media/dax-queries/dax-evaluate-define-measures.png#lightbox)

## Parameters in DAX queries

A well-defined DAX query statement can be parameterized and then used over and over with just changes in the parameter values.

The [Execute Method (XMLA)](/en-us/analysis-services/xmla/xml-elements-methods-execute) method has a [Parameters Element (XMLA)](/en-us/analysis-services/xmla/xml-elements-properties/parameters-element-xmla) collection element that allows parameters to be defined and assigned a value. Within the collection, each [Parameter Element (XMLA)](/en-us/analysis-services/xmla/xml-elements-properties/parameter-element-xmla) element defines the name of the parameter and a value to it.

Reference XMLA parameters by prefixing the name of the parameter with an `@` character. Any place in the syntax where a value is allowed, the value can be replaced with a parameter call. All XMLA parameters are typed as text.

Important

Parameters defined in the parameters section and not used in the `<STATEMENT>` element generate an error response in XMLA. Parameters used and not defined in the `<Parameters>` element generate an error response in XMLA.