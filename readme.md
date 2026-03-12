# daxglot

## dax is a garbage language

daxglot is intended to be for powerbi dax what [sqlglot](https://sqlglot.com/) is for sql.  A no dependency python parser and transpiler for dax.

dax is a garbage language that no respectable developer likes working with.  The intent of daxglot is to provide an easy mechanism to liberate your semantics from the proprietary dumpster fire of powerbi.

```python
    dax = """EVALUATE
    CALCULATETABLE ( VALUES ( Customer[City] ), LEFT ( Customer[City], 1 ) = "R" )
    ORDER BY Customer[City]"""

    parser = DaxParser()
    ast = parser.parse(dax)
    # print(ast.pretty())

    transpiler = DaxToSqlTranspiler()
    sql = transpiler.transpile(ast)
    print(sql.sql())
```