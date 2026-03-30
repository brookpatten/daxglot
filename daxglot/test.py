from daxglot import transpiler
from daxglot.parser import DaxParser
from daxglot.transpiler import DaxToSqlTranspiler


def test():
    dax = """EVALUATE
CALCULATETABLE ( VALUES ( Customer[City] ), LEFT ( Customer[City], 1 ) = "R" )
ORDER BY Customer[City]"""

    measure = """DEFINE
    MEASURE Sales[My Sales Amount] =
        SUM ( Sales[Sales Amount] )
EVALUATE
ADDCOLUMNS ( VALUES ( 'Date'[Month] ), "My Sales Amount", [My Sales Amount] )"""

    parser = DaxParser()
    ast = parser.parse(dax)
    # print(ast.pretty())

    transpiler = DaxToSqlTranspiler()
    sql = transpiler.transpile(ast)
    print(sql.sql())


if __name__ == "__main__":
    test()
