"""DAX parser package.

Re-exports the public API from daxparser.py for convenience:

    import dax
    ast = dax.parse_dax("= SUM(Sales[Amount])")
    sql = dax.dax_to_sql(ast, dialect="spark")
"""

from .daxparser import *  # noqa: F401, F403
from .daxparser import __all__  # noqa: F401
