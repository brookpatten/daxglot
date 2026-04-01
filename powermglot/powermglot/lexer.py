"""Power Query M language lexer.

Tokenises M source text into a flat list of :class:`Token` objects consumed
by :mod:`powermglot.parser`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import List


class TokenType(Enum):
    # ---- keywords -------------------------------------------------------
    LET = auto()
    IN = auto()
    EACH = auto()
    IF = auto()
    THEN = auto()
    ELSE = auto()
    TRUE = auto()
    FALSE = auto()
    NULL = auto()
    NOT = auto()
    AND = auto()
    OR = auto()
    ERROR = auto()
    TRY = auto()
    OTHERWISE = auto()
    META = auto()
    TYPE = auto()
    AS = auto()
    IS = auto()
    SHARED = auto()
    SECTION = auto()

    # ---- identifiers / literals -----------------------------------------
    IDENT = auto()           # bare identifier: foo, Table, SelectRows
    QUOTED_IDENT = auto()    # #"identifier with spaces"
    STRING = auto()          # "string literal"
    NUMBER = auto()          # 42, 3.14

    # ---- punctuation ----------------------------------------------------
    LBRACE = auto()       # {
    RBRACE = auto()       # }
    LBRACKET = auto()     # [
    RBRACKET = auto()     # ]
    LPAREN = auto()       # (
    RPAREN = auto()       # )
    COMMA = auto()        # ,
    COLON = auto()        # :
    SEMICOLON = auto()    # ;
    DOT = auto()          # .

    # ---- operators -------------------------------------------------------
    EQ = auto()       # =
    NEQ = auto()      # <>
    LT = auto()       # <
    GT = auto()       # >
    LTE = auto()      # <=
    GTE = auto()      # >=
    ARROW = auto()    # =>
    DOTDOT = auto()   # ..
    PLUS = auto()     # +
    MINUS = auto()    # -
    STAR = auto()     # *
    SLASH = auto()    # /
    AMP = auto()      # &
    AT = auto()       # @
    BANG = auto()     # !
    QUESTION = auto() # ?

    EOF = auto()


KEYWORDS: dict[str, TokenType] = {
    "let": TokenType.LET,
    "in": TokenType.IN,
    "each": TokenType.EACH,
    "if": TokenType.IF,
    "then": TokenType.THEN,
    "else": TokenType.ELSE,
    "true": TokenType.TRUE,
    "false": TokenType.FALSE,
    "null": TokenType.NULL,
    "not": TokenType.NOT,
    "and": TokenType.AND,
    "or": TokenType.OR,
    "error": TokenType.ERROR,
    "try": TokenType.TRY,
    "otherwise": TokenType.OTHERWISE,
    "meta": TokenType.META,
    "type": TokenType.TYPE,
    "as": TokenType.AS,
    "is": TokenType.IS,
    "shared": TokenType.SHARED,
    "section": TokenType.SECTION,
}


@dataclass
class Token:
    type: TokenType
    value: str
    line: int = 0
    col: int = 0

    def __repr__(self) -> str:  # pragma: no cover
        return f"Token({self.type.name}, {self.value!r})"


class LexError(Exception):
    pass


class Lexer:
    """Tokenise a Power Query M source string."""

    def __init__(self, text: str) -> None:
        self._text = text
        self._pos = 0
        self._line = 1
        self._col = 1

    @classmethod
    def tokenize(cls, text: str) -> List[Token]:
        """Return all tokens (including a terminal EOF token)."""
        lexer = cls(text)
        tokens: List[Token] = []
        while True:
            tok = lexer._next_token()
            tokens.append(tok)
            if tok.type == TokenType.EOF:
                break
        return tokens

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _peek(self, offset: int = 0) -> str:
        pos = self._pos + offset
        return self._text[pos] if pos < len(self._text) else ""

    def _advance(self) -> str:
        ch = self._text[self._pos]
        self._pos += 1
        if ch == "\n":
            self._line += 1
            self._col = 1
        else:
            self._col += 1
        return ch

    def _skip_whitespace_and_comments(self) -> None:
        while self._pos < len(self._text):
            ch = self._peek()
            if ch in (" ", "\t", "\r", "\n"):
                self._advance()
            elif ch == "/" and self._peek(1) == "/":
                # Line comment — skip to end of line
                while self._pos < len(self._text) and self._peek() != "\n":
                    self._advance()
            elif ch == "/" and self._peek(1) == "*":
                # Block comment
                self._advance()
                self._advance()
                while self._pos < len(self._text):
                    if self._peek() == "*" and self._peek(1) == "/":
                        self._advance()
                        self._advance()
                        break
                    self._advance()
            else:
                break

    def _next_token(self) -> Token:  # noqa: C901  (complex but straightforward)
        self._skip_whitespace_and_comments()
        if self._pos >= len(self._text):
            return Token(TokenType.EOF, "", self._line, self._col)

        line, col = self._line, self._col
        ch = self._peek()

        # Quoted identifier: #"..."
        if ch == "#" and self._peek(1) == '"':
            self._advance()  # #
            self._advance()  # opening "
            value = ""
            while self._pos < len(self._text):
                c = self._peek()
                if c == '"':
                    self._advance()
                    break
                value += self._advance()
            return Token(TokenType.QUOTED_IDENT, value, line, col)

        # String literal: "..." with "" for escaped quote
        if ch == '"':
            self._advance()  # opening "
            value = ""
            while self._pos < len(self._text):
                c = self._peek()
                if c == '"':
                    self._advance()
                    if self._peek() == '"':
                        value += '"'
                        self._advance()
                    else:
                        break
                else:
                    value += self._advance()
            return Token(TokenType.STRING, value, line, col)

        # Number: integer or decimal
        if ch.isdigit() or (ch == "." and self._peek(1).isdigit()):
            value = ""
            while self._pos < len(self._text) and (
                self._peek().isdigit() or self._peek() == "."
            ):
                value += self._advance()
            return Token(TokenType.NUMBER, value, line, col)

        # Identifier or keyword (stops at non-alphanumeric / non-underscore)
        if ch.isalpha() or ch == "_":
            value = ""
            while self._pos < len(self._text) and (
                self._peek().isalnum() or self._peek() == "_"
            ):
                value += self._advance()
            kw = KEYWORDS.get(value.lower())
            if kw is not None:
                return Token(kw, value, line, col)
            return Token(TokenType.IDENT, value, line, col)

        # Two-character operators (must be checked before single-char)
        if ch == "<" and self._peek(1) == ">":
            self._advance()
            self._advance()
            return Token(TokenType.NEQ, "<>", line, col)
        if ch == "<" and self._peek(1) == "=":
            self._advance()
            self._advance()
            return Token(TokenType.LTE, "<=", line, col)
        if ch == ">" and self._peek(1) == "=":
            self._advance()
            self._advance()
            return Token(TokenType.GTE, ">=", line, col)
        if ch == "=" and self._peek(1) == ">":
            self._advance()
            self._advance()
            return Token(TokenType.ARROW, "=>", line, col)
        if ch == "." and self._peek(1) == ".":
            self._advance()
            self._advance()
            return Token(TokenType.DOTDOT, "..", line, col)

        # Single-character tokens
        _SINGLE: dict[str, TokenType] = {
            "{": TokenType.LBRACE,
            "}": TokenType.RBRACE,
            "[": TokenType.LBRACKET,
            "]": TokenType.RBRACKET,
            "(": TokenType.LPAREN,
            ")": TokenType.RPAREN,
            ",": TokenType.COMMA,
            "=": TokenType.EQ,
            "<": TokenType.LT,
            ">": TokenType.GT,
            ".": TokenType.DOT,
            "+": TokenType.PLUS,
            "-": TokenType.MINUS,
            "*": TokenType.STAR,
            "/": TokenType.SLASH,
            "&": TokenType.AMP,
            "@": TokenType.AT,
            "!": TokenType.BANG,
            "?": TokenType.QUESTION,
            ":": TokenType.COLON,
            ";": TokenType.SEMICOLON,
        }
        if ch in _SINGLE:
            self._advance()
            return Token(_SINGLE[ch], ch, line, col)

        raise LexError(
            f"Unexpected character {ch!r} at line {line}, col {col}"
        )
