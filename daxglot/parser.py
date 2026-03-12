"""DAX recursive-descent parser.

Converts a stream of Token objects (produced by Lexer) into a DaxNode AST.

Grammar (simplified, operator precedence low → high):
    query      := EVALUATE table_expr [order_by] [start_at]
                | '=' var_block_or_expr
                | var_block_or_expr

    var_block_or_expr :=
                  VAR var_def+ RETURN expr
                | expr

    var_def    := IDENTIFIER '=' expr

    expr       := or_expr
    or_expr    := and_expr  (( '||' | OR ) and_expr)*
    and_expr   := not_expr  (( '&&' | AND ) not_expr)*
    not_expr   := ( NOT | '!' ) not_expr | comparison
    comparison := additive  (( '=' | '<>' | '<' | '<=' | '>' | '>=' ) additive
                            | (NOT) IN '{' expr (',' expr)* '}'
                            | IN '{' expr (',' expr)* '}'  )*
    additive   := multiplicative  (( '+' | '-' | '&' ) multiplicative)*
    multiplicative := unary  (( '*' | '/' ) unary)*
    unary      := '-' unary | power
    power      := primary ( '^' unary )*
    primary    := literal | column_ref | quoted_ident | '(' expr ')' | func_call
    func_call  := IDENTIFIER '(' arg_list ')'
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from .ast_nodes import (
    All,
    AllExcept,
    Aggregation,
    BinaryOp,
    Calculate,
    CalculateTable,
    ColumnRef,
    ContextFunction,
    CountRows,
    CrossFilter,
    DaxNode,
    EvaluateQuery,
    Filter,
    FunctionCall,
    IfError,
    IfExpr,
    InExpr,
    Iterator,
    KeepFilters,
    Literal,
    MeasureExpr,
    NotInExpr,
    OrderBy,
    OrderByItem,
    RelatedFunction,
    RemoveFilters,
    SwitchCase,
    SwitchExpr,
    TableRef,
    TreatAs,
    UnaryOp,
    UseRelationship,
    VarBlock,
    VarDef,
)
from .tokens import Lexer, Token, TokenType


class ParseError(Exception):
    def __init__(self, message: str, token: Token) -> None:
        super().__init__(
            f"{message} (got {token.type.name} {token.value!r} @{token.pos})")
        self.token = token


# Aggregation functions that take a single expression argument
_AGGREGATIONS = {
    "SUM", "MAX", "MIN", "AVERAGE", "COUNT", "DISTINCTCOUNT",
    "COUNTA", "AVERAGEA", "MINA", "MAXA",
}

# Iterator (X) functions: (table, expr)
_ITERATORS = {
    "SUMX", "AVERAGEX", "MAXX", "MINX", "COUNTX", "PRODUCTX",
    "RANKX", "PERCENTILEX.INC", "PERCENTILEX.EXC",
    "CONCATENATEX", "FIRSTNONBLANKVALUE", "LASTNONBLANKVALUE",
    "GEOMEANX",
}

# Function names that are really keyword tokens — map them back to a string name
_KEYWORD_FUNC_NAMES: dict[TokenType, str] = {
    TokenType.CALCULATE: "CALCULATE",
    TokenType.CALCULATETABLE: "CALCULATETABLE",
    TokenType.FILTER: "FILTER",
    TokenType.ALL: "ALL",
    TokenType.ALLEXCEPT: "ALLEXCEPT",
    TokenType.ALLNOBLANKROW: "ALLNOBLANKROW",
    TokenType.ALLSELECTED: "ALLSELECTED",
    TokenType.VALUES: "VALUES",
    TokenType.DISTINCT: "DISTINCT",
    TokenType.IF: "IF",
    TokenType.IFERROR: "IFERROR",
    TokenType.SWITCH: "SWITCH",
    TokenType.EARLIER: "EARLIER",
    TokenType.EARLIEST: "EARLIEST",
    TokenType.RELATED: "RELATED",
    TokenType.RELATEDTABLE: "RELATEDTABLE",
    TokenType.ADDCOLUMNS: "ADDCOLUMNS",
    TokenType.SELECTCOLUMNS: "SELECTCOLUMNS",
    TokenType.SUMMARIZE: "SUMMARIZE",
    TokenType.SUMMARIZECOLUMNS: "SUMMARIZECOLUMNS",
    TokenType.CROSSJOIN: "CROSSJOIN",
    TokenType.UNION: "UNION",
    TokenType.INTERSECT: "INTERSECT",
    TokenType.GENERATE: "GENERATE",
    TokenType.GENERATEALL: "GENERATEALL",
    TokenType.TOPN: "TOPN",
    TokenType.SAMPLE: "SAMPLE",
    TokenType.ROW: "ROW",
    TokenType.DATATABLE: "DATATABLE",
    TokenType.TREATAS: "TREATAS",
    TokenType.USERELATIONSHIP: "USERELATIONSHIP",
    TokenType.CROSSFILTER: "CROSSFILTER",
    TokenType.KEEPFILTERS: "KEEPFILTERS",
    TokenType.REMOVEFILTERS: "REMOVEFILTERS",
    TokenType.DATEADD: "DATEADD",
    TokenType.DATESYTD: "DATESYTD",
    TokenType.DATESQTD: "DATESQTD",
    TokenType.DATESMTD: "DATESMTD",
    TokenType.SAMEPERIODLASTYEAR: "SAMEPERIODLASTYEAR",
    TokenType.DATESBETWEEN: "DATESBETWEEN",
    TokenType.DATESINPERIOD: "DATESINPERIOD",
    TokenType.PARALLELPERIOD: "PARALLELPERIOD",
    TokenType.PREVIOUSMONTH: "PREVIOUSMONTH",
    TokenType.PREVIOUSQUARTER: "PREVIOUSQUARTER",
    TokenType.PREVIOUSYEAR: "PREVIOUSYEAR",
    TokenType.NEXTMONTH: "NEXTMONTH",
    TokenType.NEXTQUARTER: "NEXTQUARTER",
    TokenType.NEXTYEAR: "NEXTYEAR",
    TokenType.BLANK: "BLANK",
}

# All token types that can be the start of a function-that-looks-like-a-keyword
_FUNC_TOKEN_TYPES = set(_KEYWORD_FUNC_NAMES.keys())


class DaxParser:
    """Hand-written recursive descent parser for DAX.

    Usage::

        node = DaxParser().parse(text)
    """

    def __init__(self) -> None:
        self._tokens: List[Token] = []
        self._pos: int = 0

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def parse(self, text: str) -> DaxNode:
        """Parse *text* and return the root AST node."""
        self._tokens = Lexer.tokenize(text)
        self._pos = 0

        # Optional leading '=' for measure definitions
        if self._peek().type == TokenType.EQ:
            self._advance()  # consume '='
            inner = self._parse_var_block_or_expr()
            self._expect(TokenType.EOF)
            return MeasureExpr(expr=inner)

        # EVALUATE query
        if self._peek().type == TokenType.EVALUATE:
            node = self._parse_evaluate_query()
            self._expect(TokenType.EOF)
            return node

        # Bare expression (e.g. in test / REPL context)
        node = self._parse_var_block_or_expr()
        self._expect(TokenType.EOF)
        return node

    # ------------------------------------------------------------------
    # Token stream helpers
    # ------------------------------------------------------------------

    def _peek(self, offset: int = 0) -> Token:
        idx = self._pos + offset
        if idx >= len(self._tokens):
            return self._tokens[-1]  # EOF
        return self._tokens[idx]

    def _advance(self) -> Token:
        tok = self._tokens[self._pos]
        if tok.type != TokenType.EOF:
            self._pos += 1
        return tok

    def _expect(self, ttype: TokenType) -> Token:
        tok = self._peek()
        if tok.type != ttype:
            raise ParseError(f"Expected {ttype.name}", tok)
        return self._advance()

    def _match(self, *ttypes: TokenType) -> bool:
        return self._peek().type in ttypes

    def _consume_if(self, *ttypes: TokenType) -> Optional[Token]:
        if self._peek().type in ttypes:
            return self._advance()
        return None

    # ------------------------------------------------------------------
    # High-level constructs
    # ------------------------------------------------------------------

    def _parse_evaluate_query(self) -> EvaluateQuery:
        self._expect(TokenType.EVALUATE)
        table_expr = self._parse_expr()

        order_by: Optional[OrderBy] = None
        if self._match(TokenType.ORDER):
            self._advance()  # ORDER
            self._expect(TokenType.BY)
            order_by = self._parse_order_by_items()

        start_at: Optional[List[DaxNode]] = None
        if self._match(TokenType.START):
            self._advance()  # START
            self._expect(TokenType.AT)
            start_at = [self._parse_expr()]
            while self._consume_if(TokenType.COMMA):
                start_at.append(self._parse_expr())

        return EvaluateQuery(
            table_expr=table_expr,
            order_by=order_by,
            start_at=start_at,
        )

    def _parse_order_by_items(self) -> OrderBy:
        items: List[OrderByItem] = []
        expr = self._parse_expr()
        direction = "ASC"
        if self._match(TokenType.ASC):
            self._advance()
            direction = "ASC"
        elif self._match(TokenType.DESC):
            self._advance()
            direction = "DESC"
        items.append(OrderByItem(expr=expr, direction=direction))
        while self._consume_if(TokenType.COMMA):
            expr = self._parse_expr()
            direction = "ASC"
            if self._match(TokenType.ASC):
                self._advance()
                direction = "ASC"
            elif self._match(TokenType.DESC):
                self._advance()
                direction = "DESC"
            items.append(OrderByItem(expr=expr, direction=direction))
        return OrderBy(items=tuple(items))

    def _parse_var_block_or_expr(self) -> DaxNode:
        if not self._match(TokenType.VAR):
            return self._parse_expr()

        var_defs: List[VarDef] = []
        while self._match(TokenType.VAR):
            self._advance()  # VAR
            name_tok = self._expect(TokenType.IDENTIFIER)
            self._expect(TokenType.EQ)
            expr = self._parse_expr()
            var_defs.append(VarDef(name=name_tok.value, expr=expr))

        self._expect(TokenType.RETURN)
        return_expr = self._parse_expr()
        return VarBlock(vars=tuple(var_defs), return_expr=return_expr)

    # ------------------------------------------------------------------
    # Expression grammar — operator precedence (low → high)
    # ------------------------------------------------------------------

    def _parse_expr(self) -> DaxNode:
        return self._parse_or()

    def _parse_or(self) -> DaxNode:
        left = self._parse_and()
        while self._match(TokenType.OR_OP, TokenType.OR):
            op = self._advance().value
            right = self._parse_and()
            left = BinaryOp(op=op, left=left, right=right)
        return left

    def _parse_and(self) -> DaxNode:
        left = self._parse_not()
        while self._match(TokenType.AND_OP, TokenType.AND):
            op = self._advance().value
            right = self._parse_not()
            left = BinaryOp(op=op, left=left, right=right)
        return left

    def _parse_not(self) -> DaxNode:
        if self._match(TokenType.NOT):
            self._advance()
            # Check for NOT IN pattern — handled in comparison
            if self._peek().type == TokenType.IN:
                # Put the NOT back conceptually — this is parsed at comparison level.
                # We rewind by one position.
                self._pos -= 1
                return self._parse_comparison()
            return UnaryOp(op="NOT", expr=self._parse_not())
        if self._match(TokenType.BANG):
            self._advance()
            return UnaryOp(op="!", expr=self._parse_not())
        return self._parse_comparison()

    def _parse_comparison(self) -> DaxNode:
        left = self._parse_additive()

        _CMP_OPS = {
            TokenType.EQ, TokenType.NEQ,
            TokenType.LT, TokenType.LTE,
            TokenType.GT, TokenType.GTE,
        }

        while True:
            tok = self._peek()

            # NOT IN { ... }
            if tok.type == TokenType.NOT and self._peek(1).type == TokenType.IN:
                self._advance()  # NOT
                self._advance()  # IN
                values = self._parse_in_values()
                left = NotInExpr(expr=left, values=tuple(values))
                continue

            # IN { ... }
            if tok.type == TokenType.IN:
                self._advance()  # IN
                values = self._parse_in_values()
                left = InExpr(expr=left, values=tuple(values))
                continue

            if tok.type in _CMP_OPS:
                op = self._advance().value
                right = self._parse_additive()
                left = BinaryOp(op=op, left=left, right=right)
                continue

            break

        return left

    def _parse_in_values(self) -> List[DaxNode]:
        """Parse ``{ expr, expr, ... }``."""
        self._expect(TokenType.LBRACE)
        values: List[DaxNode] = [self._parse_expr()]
        while self._consume_if(TokenType.COMMA):
            values.append(self._parse_expr())
        self._expect(TokenType.RBRACE)
        return values

    def _parse_additive(self) -> DaxNode:
        left = self._parse_multiplicative()
        while self._match(TokenType.PLUS, TokenType.MINUS, TokenType.AMP):
            op = self._advance().value
            right = self._parse_multiplicative()
            left = BinaryOp(op=op, left=left, right=right)
        return left

    def _parse_multiplicative(self) -> DaxNode:
        left = self._parse_unary()
        while self._match(TokenType.STAR, TokenType.SLASH):
            op = self._advance().value
            right = self._parse_unary()
            left = BinaryOp(op=op, left=left, right=right)
        return left

    def _parse_unary(self) -> DaxNode:
        if self._match(TokenType.MINUS):
            self._advance()
            return UnaryOp(op="-", expr=self._parse_unary())
        return self._parse_power()

    def _parse_power(self) -> DaxNode:
        base = self._parse_primary()
        if self._match(TokenType.CARET):
            self._advance()
            exp = self._parse_unary()
            return BinaryOp(op="^", left=base, right=exp)
        return base

    # ------------------------------------------------------------------
    # Primary expressions
    # ------------------------------------------------------------------

    def _parse_primary(self) -> DaxNode:
        tok = self._peek()

        # Parenthesised expression
        if tok.type == TokenType.LPAREN:
            self._advance()
            inner = self._parse_expr()
            self._expect(TokenType.RPAREN)
            return inner

        # COLUMN_REF: Table[Column] (single token from lexer)
        if tok.type == TokenType.COLUMN_REF:
            self._advance()
            raw = tok.value  # e.g. "Changes[member_id]"
            bracket = raw.index("[")
            table = raw[:bracket]
            column = raw[bracket + 1: -1]
            return ColumnRef(table=table, column=column)

        # COLUMN_ONLY: [Column]
        if tok.type == TokenType.COLUMN_ONLY:
            self._advance()
            return ColumnRef(table=None, column=tok.value)

        # Quoted identifier: 'Table Name' — may be followed by [Column]
        if tok.type == TokenType.QUOTED_IDENTIFIER:
            self._advance()
            # If followed by a COLUMN_ONLY token, it's Table[Column]
            if self._peek().type == TokenType.COLUMN_ONLY:
                col_tok = self._advance()
                return ColumnRef(table=tok.value, column=col_tok.value)
            # If followed by a COLUMN_REF ... shouldn't happen after quoted, but guard
            return TableRef(name=tok.value, is_quoted=True)

        # Literals
        if tok.type == TokenType.NUMBER:
            self._advance()
            raw = tok.value
            val: int | float = float(
                raw) if "." in raw or "e" in raw.lower() else int(raw)
            return Literal(value=val, kind="NUMBER")

        if tok.type == TokenType.STRING_LIT:
            self._advance()
            return Literal(value=tok.value, kind="STRING")

        if tok.type == TokenType.TRUE:
            self._advance()
            return Literal(value=True, kind="BOOLEAN")

        if tok.type == TokenType.FALSE:
            self._advance()
            return Literal(value=False, kind="BOOLEAN")

        if tok.type == TokenType.BLANK:
            # BLANK() or BLANK (both valid in DAX)
            self._advance()
            self._consume_if(TokenType.LPAREN)
            # If we consumed '(', also consume ')'
            if self._peek(-1).type == TokenType.LPAREN:  # we just consumed it
                pass  # already advanced past LPAREN
            # peek back — but simpler: try to consume matching ')'
            # Actually, we need to handle BLANK() correctly.
            # Re-implement: if next is '(', advance and expect ')'
            # Let's reset: we already advanced past BLANK.
            # The _consume_if above consumed '(' if present; now consume ')':
            self._consume_if(TokenType.RPAREN)
            return Literal(value=None, kind="BLANK")

        # ASC / DESC used as direction argument values in functions like TOPN, SAMPLE
        if tok.type in (TokenType.ASC, TokenType.DESC):
            self._advance()
            return Literal(value=tok.value.upper(), kind="STRING")

        # Keyword-functions (e.g. CALCULATE, FILTER, IF …)
        if tok.type in _FUNC_TOKEN_TYPES and self._peek(1).type == TokenType.LPAREN:
            func_name = _KEYWORD_FUNC_NAMES[tok.type]
            self._advance()  # consume keyword token
            return self._parse_function_dispatch(func_name)

        # Generic IDENTIFIER — could be function call or bare table reference
        if tok.type == TokenType.IDENTIFIER:
            name = tok.value
            self._advance()

            # Function call
            if self._peek().type == TokenType.LPAREN:
                return self._parse_function_dispatch(name.upper())

            # Otherwise it's a bare table reference
            return TableRef(name=name, is_quoted=False)

        raise ParseError(f"Unexpected token in expression", tok)

    # ------------------------------------------------------------------
    # Peek helper for negative offsets — used in BLANK() workaround
    # ------------------------------------------------------------------

    # Note: _peek(-1) is used above; let's make sure it works
    def _peek(self, offset: int = 0) -> Token:  # type: ignore[override]
        idx = self._pos + offset
        if idx < 0:
            return self._tokens[0]
        if idx >= len(self._tokens):
            return self._tokens[-1]
        return self._tokens[idx]

    # ------------------------------------------------------------------
    # Function call dispatch
    # ------------------------------------------------------------------

    def _parse_arg_list(self) -> List[DaxNode]:
        """Parse ``( expr [, expr]* )`` and return the list of argument nodes."""
        self._expect(TokenType.LPAREN)
        args: List[DaxNode] = []
        if not self._match(TokenType.RPAREN):
            args.append(self._parse_expr())
            while self._consume_if(TokenType.COMMA):
                args.append(self._parse_expr())
        self._expect(TokenType.RPAREN)
        return args

    def _parse_function_dispatch(self, name: str) -> DaxNode:
        """Dispatch a function call by name to a specific node constructor."""
        upper = name.upper()

        # CALCULATE
        if upper == "CALCULATE":
            args = self._parse_arg_list()
            if not args:
                raise ParseError(
                    "CALCULATE requires at least one argument", self._peek())
            return Calculate(expr=args[0], filters=tuple(args[1:]))

        # CALCULATETABLE
        if upper == "CALCULATETABLE":
            args = self._parse_arg_list()
            if not args:
                raise ParseError(
                    "CALCULATETABLE requires at least one argument", self._peek())
            return CalculateTable(table_expr=args[0], filters=tuple(args[1:]))

        # FILTER
        if upper == "FILTER":
            args = self._parse_arg_list()
            if len(args) != 2:
                raise ParseError(
                    "FILTER requires exactly 2 arguments", self._peek())
            return Filter(table_expr=args[0], condition=args[1])

        # ALL
        if upper == "ALL":
            args = self._parse_arg_list()
            if not args:
                raise ParseError(
                    "ALL requires at least one argument", self._peek())
            return All(table_or_column=args[0], columns=tuple(args[1:]))

        # ALLEXCEPT
        if upper == "ALLEXCEPT":
            args = self._parse_arg_list()
            if len(args) < 2:
                raise ParseError(
                    "ALLEXCEPT requires at least 2 arguments", self._peek())
            return AllExcept(table_expr=args[0], columns=tuple(args[1:]))

        # KEEPFILTERS
        if upper == "KEEPFILTERS":
            args = self._parse_arg_list()
            if len(args) != 1:
                raise ParseError(
                    "KEEPFILTERS requires exactly 1 argument", self._peek())
            return KeepFilters(expr=args[0])

        # REMOVEFILTERS
        if upper == "REMOVEFILTERS":
            args = self._parse_arg_list()
            if len(args) != 1:
                raise ParseError(
                    "REMOVEFILTERS requires exactly 1 argument", self._peek())
            return RemoveFilters(expr=args[0])

        # TREATAS
        if upper == "TREATAS":
            args = self._parse_arg_list()
            if len(args) < 2:
                raise ParseError(
                    "TREATAS requires at least 2 arguments", self._peek())
            return TreatAs(table_expr=args[0], columns=tuple(args[1:]))

        # USERELATIONSHIP
        if upper == "USERELATIONSHIP":
            args = self._parse_arg_list()
            if len(args) != 2:
                raise ParseError(
                    "USERELATIONSHIP requires exactly 2 arguments", self._peek())
            return UseRelationship(col1=args[0], col2=args[1])

        # CROSSFILTER
        if upper == "CROSSFILTER":
            args = self._parse_arg_list()
            if len(args) != 3:
                raise ParseError(
                    "CROSSFILTER requires exactly 3 arguments", self._peek())
            direction_arg = args[2]
            direction = direction_arg.value if isinstance(
                direction_arg, Literal) else str(direction_arg)
            return CrossFilter(col1=args[0], col2=args[1], direction=str(direction))

        # Aggregation functions
        if upper in _AGGREGATIONS:
            args = self._parse_arg_list()
            if len(args) != 1:
                raise ParseError(
                    f"{upper} requires exactly 1 argument", self._peek())
            return Aggregation(func=upper, expr=args[0])

        # COUNTROWS
        if upper == "COUNTROWS":
            args = self._parse_arg_list()
            return CountRows(table_expr=args[0] if args else None)

        # Iterator (X) functions
        if upper in _ITERATORS:
            args = self._parse_arg_list()
            if len(args) < 2:
                raise ParseError(
                    f"{upper} requires at least 2 arguments", self._peek())
            return Iterator(func=upper, table_expr=args[0], body=args[1])

        # EARLIER / EARLIEST
        if upper in ("EARLIER", "EARLIEST"):
            args = self._parse_arg_list()
            if not args:
                raise ParseError(
                    f"{upper} requires at least 1 argument", self._peek())
            depth = 1
            if len(args) >= 2 and isinstance(args[1], Literal) and args[1].kind == "NUMBER":
                depth = int(args[1].value)
            return ContextFunction(func=upper, expr=args[0], depth=depth)

        # RELATED / RELATEDTABLE
        if upper in ("RELATED", "RELATEDTABLE"):
            args = self._parse_arg_list()
            if len(args) != 1:
                raise ParseError(
                    f"{upper} requires exactly 1 argument", self._peek())
            return RelatedFunction(func=upper, expr=args[0])

        # IF
        if upper == "IF":
            args = self._parse_arg_list()
            if len(args) < 2:
                raise ParseError(
                    "IF requires at least 2 arguments", self._peek())
            return IfExpr(
                condition=args[0],
                true_val=args[1],
                false_val=args[2] if len(args) > 2 else None,
            )

        # IFERROR
        if upper == "IFERROR":
            args = self._parse_arg_list()
            if len(args) != 2:
                raise ParseError(
                    "IFERROR requires exactly 2 arguments", self._peek())
            return IfError(value=args[0], value_if_error=args[1])

        # SWITCH
        if upper == "SWITCH":
            return self._parse_switch()

        # BLANK (called as BLANK())
        if upper == "BLANK":
            self._expect(TokenType.LPAREN)
            self._expect(TokenType.RPAREN)
            return Literal(value=None, kind="BLANK")

        # VALUES, DISTINCT — single-arg table/column functions
        if upper in ("VALUES", "DISTINCT", "ALLNOBLANKROW", "ALLSELECTED"):
            args = self._parse_arg_list()
            return FunctionCall(name=upper, args=tuple(args))

        # Generic fallback — covers time intelligence and anything else
        args = self._parse_arg_list()
        return FunctionCall(name=upper, args=tuple(args))

    def _parse_switch(self) -> SwitchExpr:
        """SWITCH(<expr>, <val1>, <result1> [, <valN>, <resultN>]* [, <else>])"""
        self._expect(TokenType.LPAREN)
        switch_expr = self._parse_expr()
        self._expect(TokenType.COMMA)

        cases: List[SwitchCase] = []
        default: Optional[DaxNode] = None

        while not self._match(TokenType.RPAREN, TokenType.EOF):
            val = self._parse_expr()
            if self._consume_if(TokenType.COMMA):
                # Peek: if next is RPAREN there is no result — shouldn't happen
                result = self._parse_expr()
                cases.append(SwitchCase(when=val, then=result))
                self._consume_if(TokenType.COMMA)
                # After a pair, if next token is RPAREN the loop ends.
            else:
                # Last argument with no comma after — the default/else value
                default = val
        self._expect(TokenType.RPAREN)
        return SwitchExpr(expr=switch_expr, cases=tuple(cases), default=default)


def parse_dax(text: str) -> DaxNode:
    """Convenience function: parse *text* and return the root AST node."""
    return DaxParser().parse(text)
