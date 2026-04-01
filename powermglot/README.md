# powermglot

A Power Query M parser and SQL transpiler built on [sqlglot](https://github.com/tobymao/sqlglot).

`powermglot` parses Power Query M `let...in` chain expressions (as used in Power BI data source definitions) and converts them to SQL SELECT statements.

## Quick start

```python
from powermglot import parse_m, m_to_sql

m_expr = """
let
    Source = Databricks.Catalogs("host", "443", [Catalog="prod"]),
    prod_db = Source{[Name="pbi"]}[Data],
    orders = prod_db{[Name="orders"]}[Data],
    filtered = Table.SelectRows(orders, each [status] = "Active"),
    selected = Table.SelectColumns(filtered, {"order_id", "amount", "status"})
in
    selected
"""

sql = m_to_sql(m_expr, dialect="spark")
print(sql)
# SELECT order_id, amount, status FROM prod.pbi.orders WHERE status = 'Active'
```

## Supported M patterns

| M expression | SQL equivalent |
|---|---|
| Connector navigation (3 levels) | `FROM catalog.schema.table` |
| `Table.SelectRows(t, each [col] op val)` | `WHERE col op val` |
| `Table.SelectColumns(t, {cols})` | `SELECT col1, col2, ...` |
| `Table.RenameColumns(t, {{old, new}, ...})` | Column aliases |
| `Table.AddColumn(t, "name", each expr)` | Computed column in SELECT |
| `Table.RemoveColumns(t, {cols})` | Exclude columns |
| `Table.Group(t, {keys}, {aggs})` | `GROUP BY` with aggregations |
| `Table.NestedJoin` / `Table.Join` | `JOIN` clause |
| `Value.NativeQuery(src, "sql")` | Pass-through SQL |
