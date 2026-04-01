"""Power Query M parser.

Parses a subset of the M language grammar sufficient to represent the
``let … in`` chain patterns found in Power BI data source definitions.

Grammar (simplified)::

    m_doc        := let_expr | expr
    let_expr     := 'let' binding (',' binding)* 'in' expr
    binding      := name '=' expr
    name         := IDENT | QUOTED_IDENT

    expr         := if_expr | each_expr | try_expr | not_expr
    if_expr      := 'if' expr 'then' expr 'else' expr
    each_expr    := 'each' expr
    try_expr     := 'try' expr ('otherwise' expr)?
    not_expr     := 'not' comparison | comparison

    comparison   := additive (('='|'<>'|'<'|'>'|'<='|'>=') additive)*
    additive     := multiplicative (('+' | '-' | '&') multiplicative)*
    multiplicative := unary (('*' | '/') unary)*
    unary        := '-' unary | primary_suffix

    primary_suffix := primary (call_suffix | nav_suffix | bracket_suffix | '.' IDENT)*
    call_suffix  := '(' args ')'
    nav_suffix   := '{' expr '}'
    bracket_suffix := '[' name ']'        (field access)

    primary      := literal | IDENT | QUOTED_IDENT | '(' expr ')' | list | record
    list         := '{' (expr (',' expr)*)? '}'
    record       := '[' (field (',' field)*)? ']'
    field        := name '=' expr   |   name          (record field reference)
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from .ast_nodes import (
    BinaryOpExpr,
    CallExpr,
    EachExpr,
    ErrorExpr,
    FieldAccessExpr,
    FieldRef,
    IdentExpr,
    IfExpr,
    LetExpr,
    ListExpr,
    LiteralExpr,
    MetaExpr,
    MExpr,
    NavExpr,
    ParenExpr,
    RecordExpr,
    TypeExpr,
    UnaryOpExpr,
)
from .lexer import Lexer, LexError, Token, TokenType


class ParseError(Exception):
    pass


def parse_m(text: str) -> MExpr:
    """Parse an M expression string and return the root AST node."""
    tokens = Lexer.tokenize(text)
    return MParser(tokens).parse()


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class MParser:
    """Recursive-descent parser for Power Query M expressions."""

    def __init__(self, tokens: List[Token]) -> None:
        self._tokens = tokens
        self._pos = 0

    # ------------------------------------------------------------------
    # Token navigation
    # ------------------------------------------------------------------

    def _peek(self, offset: int = 0) -> Token:
        pos = self._pos + offset
        if pos < len(self._tokens):
            return self._tokens[pos]
        return Token(TokenType.EOF, "")

    def _advance(self) -> Token:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _match(self, *types: TokenType) -> bool:
        return self._peek().type in types

    def _expect(self, ttype: TokenType) -> Token:
        tok = self._peek()
        if tok.type != ttype:
            raise ParseError(
                f"Expected {ttype.name} but got {tok.type.name} ({tok.value!r}) "
                f"at line {tok.line}, col {tok.col}"
            )
        return self._advance()

    def _expect_name(self) -> str:
        """Consume an identifier or quoted identifier and return its string value."""
        tok = self._peek()
        if tok.type in (TokenType.IDENT, TokenType.QUOTED_IDENT):
            return self._advance().value
        # Some keywords can appear as identifiers in binding names
        if tok.type in (
            TokenType.ERROR, TokenType.TYPE, TokenType.META,
            TokenType.AS, TokenType.IS, TokenType.SHARED,
            TokenType.TRY, TokenType.OTHERWISE,
        ):
            return self._advance().value
        raise ParseError(
            f"Expected identifier but got {tok.type.name} ({tok.value!r}) "
            f"at line {tok.line}, col {tok.col}"
        )

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def parse(self) -> MExpr:
        expr = self._parse_expr()
        self._expect(TokenType.EOF)
        return expr

    # ------------------------------------------------------------------
    # Expression grammar
    # ------------------------------------------------------------------

    def _parse_expr(self) -> MExpr:
        if self._match(TokenType.LET):
            return self._parse_let()
        if self._match(TokenType.IF):
            return self._parse_if()
        if self._match(TokenType.EACH):
            return self._parse_each()
        if self._match(TokenType.ERROR):
            self._advance()
            return ErrorExpr(expr=self._parse_expr())
        if self._match(TokenType.TRY):
            return self._parse_try()
        if self._match(TokenType.TYPE):
            self._advance()
            name = self._expect_name()
            return TypeExpr(name=name)
        return self._parse_logical_or()

    def _parse_let(self) -> LetExpr:
        self._expect(TokenType.LET)
        bindings: List[Tuple[str, MExpr]] = []
        while True:
            name = self._expect_name()
            self._expect(TokenType.EQ)
            expr = self._parse_expr()
            bindings.append((name, expr))
            if not self._match(TokenType.COMMA):
                break
            self._advance()  # consume ','
            # Allow trailing 'in' without a comma
            if self._match(TokenType.IN):
                break
        self._expect(TokenType.IN)
        result = self._parse_expr()
        return LetExpr(bindings=bindings, result=result)

    def _parse_if(self) -> IfExpr:
        self._expect(TokenType.IF)
        condition = self._parse_expr()
        self._expect(TokenType.THEN)
        then_expr = self._parse_expr()
        self._expect(TokenType.ELSE)
        else_expr = self._parse_expr()
        return IfExpr(condition=condition, then_expr=then_expr, else_expr=else_expr)

    def _parse_each(self) -> EachExpr:
        self._expect(TokenType.EACH)
        expr = self._parse_expr()
        return EachExpr(expr=expr)

    def _parse_try(self) -> MExpr:
        self._expect(TokenType.TRY)
        expr = self._parse_expr()
        if self._match(TokenType.OTHERWISE):
            self._advance()
            fallback = self._parse_expr()
            return BinaryOpExpr(op="otherwise", left=expr, right=fallback)
        return expr

    # ------------------------------------------------------------------
    # Logical / comparison operators (low → high precedence)
    # ------------------------------------------------------------------

    def _parse_logical_or(self) -> MExpr:
        left = self._parse_logical_and()
        while self._match(TokenType.OR):
            self._advance()
            right = self._parse_logical_and()
            left = BinaryOpExpr(op="or", left=left, right=right)
        return left

    def _parse_logical_and(self) -> MExpr:
        left = self._parse_not()
        while self._match(TokenType.AND):
            self._advance()
            right = self._parse_not()
            left = BinaryOpExpr(op="and", left=left, right=right)
        return left

    def _parse_not(self) -> MExpr:
        if self._match(TokenType.NOT):
            self._advance()
            return UnaryOpExpr(op="not", expr=self._parse_not())
        return self._parse_is_as()

    def _parse_is_as(self) -> MExpr:
        left = self._parse_comparison()
        while self._match(TokenType.IS, TokenType.AS):
            op = self._advance().value.lower()
            right = self._parse_comparison()
            left = BinaryOpExpr(op=op, left=left, right=right)
        return left

    def _parse_comparison(self) -> MExpr:
        left = self._parse_additive()
        while self._match(
            TokenType.EQ, TokenType.NEQ,
            TokenType.LT, TokenType.GT,
            TokenType.LTE, TokenType.GTE,
        ):
            op = self._advance().value
            right = self._parse_additive()
            left = BinaryOpExpr(op=op, left=left, right=right)
        return left

    def _parse_additive(self) -> MExpr:
        left = self._parse_multiplicative()
        while self._match(TokenType.PLUS, TokenType.MINUS, TokenType.AMP):
            op = self._advance().value
            right = self._parse_multiplicative()
            left = BinaryOpExpr(op=op, left=left, right=right)
        return left

    def _parse_multiplicative(self) -> MExpr:
        left = self._parse_unary()
        while self._match(TokenType.STAR, TokenType.SLASH):
            op = self._advance().value
            right = self._parse_unary()
            left = BinaryOpExpr(op=op, left=left, right=right)
        return left

    def _parse_unary(self) -> MExpr:
        if self._match(TokenType.MINUS):
            self._advance()
            return UnaryOpExpr(op="-", expr=self._parse_unary())
        if self._match(TokenType.PLUS):
            self._advance()
            return self._parse_unary()
        return self._parse_meta()

    def _parse_meta(self) -> MExpr:
        expr = self._parse_primary_suffix()
        if self._match(TokenType.META):
            self._advance()
            meta_record = self._parse_primary_suffix()
            return MetaExpr(expr=expr, meta=meta_record)
        return expr

    # ------------------------------------------------------------------
    # Primary with postfix operators
    # ------------------------------------------------------------------

    def _parse_primary_suffix(self) -> MExpr:  # noqa: C901
        expr = self._parse_primary()
        while True:
            if self._match(TokenType.LPAREN):
                # Function call: expr(args)
                self._advance()
                args: List[MExpr] = []
                if not self._match(TokenType.RPAREN):
                    args.append(self._parse_expr())
                    while self._match(TokenType.COMMA):
                        self._advance()
                        if self._match(TokenType.RPAREN):
                            break
                        args.append(self._parse_expr())
                self._expect(TokenType.RPAREN)
                expr = CallExpr(function=expr, args=args)

            elif self._match(TokenType.LBRACE):
                # Navigation: expr{key}
                self._advance()
                key = self._parse_expr()
                self._expect(TokenType.RBRACE)
                expr = NavExpr(expr=expr, key=key)

            elif self._match(TokenType.LBRACKET):
                # Field access: expr[Field]
                self._advance()
                name = self._expect_name()
                self._expect(TokenType.RBRACKET)
                expr = FieldAccessExpr(expr=expr, field=name)

            elif self._match(TokenType.DOT):
                # Dotted member: expr.Member
                self._advance()
                member = self._expect_name()
                expr = FieldAccessExpr(expr=expr, field=member)

            elif self._match(TokenType.BANG):
                # Optional access operator: expr!
                self._advance()

            else:
                break
        return expr

    def _parse_primary(self) -> MExpr:  # noqa: C901
        tok = self._peek()

        # Parenthesised expression
        if tok.type == TokenType.LPAREN:
            self._advance()
            expr = self._parse_expr()
            self._expect(TokenType.RPAREN)
            return ParenExpr(expr=expr)

        # List literal: { expr, ... }
        if tok.type == TokenType.LBRACE:
            return self._parse_list()

        # Record literal: [ field = expr, ... ]
        if tok.type == TokenType.LBRACKET:
            return self._parse_record()

        # Identifiers
        if tok.type == TokenType.IDENT:
            self._advance()
            return IdentExpr(name=tok.value)

        if tok.type == TokenType.QUOTED_IDENT:
            self._advance()
            return IdentExpr(name=tok.value)

        # Keywords that double as identifiers in some positions
        if tok.type in (
            TokenType.TRUE, TokenType.FALSE, TokenType.NULL,
        ):
            self._advance()
            if tok.type == TokenType.TRUE:
                return LiteralExpr(value=True, kind="bool")
            if tok.type == TokenType.FALSE:
                return LiteralExpr(value=False, kind="bool")
            return LiteralExpr(value=None, kind="null")

        # Number
        if tok.type == TokenType.NUMBER:
            self._advance()
            raw = tok.value
            val: float | int = float(raw) if "." in raw else int(raw)
            return LiteralExpr(value=val, kind="number")

        # String
        if tok.type == TokenType.STRING:
            self._advance()
            return LiteralExpr(value=tok.value, kind="string")

        # Minus / unary minus before a number already handled in _parse_unary,
        # but guard against stray tokens here for better error messages.
        raise ParseError(
            f"Unexpected token {tok.type.name} ({tok.value!r}) "
            f"at line {tok.line}, col {tok.col}"
        )

    def _parse_list(self) -> ListExpr:
        """Parse ``{ expr, expr, ... }``."""
        self._expect(TokenType.LBRACE)
        items: List[MExpr] = []
        if not self._match(TokenType.RBRACE):
            items.append(self._parse_expr())
            while self._match(TokenType.COMMA):
                self._advance()
                if self._match(TokenType.RBRACE):
                    break
                items.append(self._parse_expr())
        self._expect(TokenType.RBRACE)
        return ListExpr(items=items)

    def _parse_record(self) -> RecordExpr:
        """Parse ``[ field = expr, ... ]``.

        Fields without a ``=`` (e.g. ``[ColumnName]`` as a field reference in
        an ``each`` expression) are returned as :class:`FieldRef` placeholders
        when the record contains exactly one un-valued field.
        """
        self._expect(TokenType.LBRACKET)

        # Check for a plain field reference inside an each: [ColumnName]
        # Heuristic: if the next token is a name and the one after is ']',
        # treat it as a FieldRef.
        if self._peek().type in (TokenType.IDENT, TokenType.QUOTED_IDENT) and (
            self._peek(1).type == TokenType.RBRACKET
        ):
            name = self._advance().value
            self._expect(TokenType.RBRACKET)
            # Return a special sentinel so the caller can detect this case.
            # We wrap it in a RecordExpr with a sentinel marker.
            return RecordExpr(fields=[("__field_ref__", IdentExpr(name=name))])

        fields: List[Tuple[str, MExpr]] = []
        if not self._match(TokenType.RBRACKET):
            name = self._expect_name()
            if self._match(TokenType.EQ):
                self._advance()
                val: MExpr = self._parse_expr()
            else:
                # Bare name without value — treat as Type annotation reference
                val = IdentExpr(name=name)
            fields.append((name, val))
            while self._match(TokenType.COMMA):
                self._advance()
                if self._match(TokenType.RBRACKET):
                    break
                name = self._expect_name()
                if self._match(TokenType.EQ):
                    self._advance()
                    val = self._parse_expr()
                else:
                    val = IdentExpr(name=name)
                fields.append((name, val))
        self._expect(TokenType.RBRACKET)
        return RecordExpr(fields=fields)
