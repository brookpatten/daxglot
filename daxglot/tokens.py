"""DAX Lexer — tokenises a DAX expression or EVALUATE query."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import List


class TokenType(Enum):
    # Literals
    NUMBER = auto()
    STRING_LIT = auto()
    TRUE = auto()
    FALSE = auto()
    BLANK = auto()

    # Identifiers / references
    IDENTIFIER = auto()
    QUOTED_IDENTIFIER = auto()   # 'Quoted Table Name'
    COLUMN_REF = auto()          # Table[Column]
    COLUMN_ONLY = auto()         # [Column]

    # Keywords — query structure
    EVALUATE = auto()
    ORDER = auto()
    BY = auto()
    START = auto()
    AT = auto()
    ASC = auto()
    DESC = auto()

    # Keywords — filter/table functions
    CALCULATE = auto()
    CALCULATETABLE = auto()
    FILTER = auto()
    ALL = auto()
    ALLEXCEPT = auto()
    ALLNOBLANKROW = auto()
    ALLSELECTED = auto()
    VALUES = auto()
    DISTINCT = auto()
    ADDCOLUMNS = auto()
    SELECTCOLUMNS = auto()
    SUMMARIZE = auto()
    SUMMARIZECOLUMNS = auto()
    CROSSJOIN = auto()
    UNION = auto()
    INTERSECT = auto()
    EXCEPT = auto()
    GENERATE = auto()
    GENERATEALL = auto()
    TOPN = auto()
    SAMPLE = auto()
    ROW = auto()
    DATATABLE = auto()
    TREATAS = auto()
    USERELATIONSHIP = auto()
    CROSSFILTER = auto()
    KEEPFILTERS = auto()
    REMOVEFILTERS = auto()

    # Keywords — context / relationship
    EARLIER = auto()
    EARLIEST = auto()
    RELATED = auto()
    RELATEDTABLE = auto()

    # Keywords — logical
    IF = auto()
    IFERROR = auto()
    SWITCH = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    IN = auto()
    NOT_IN = auto()

    # Keywords — VAR / RETURN
    VAR = auto()
    RETURN = auto()

    # Keywords — time intelligence (commonly used)
    DATEADD = auto()
    DATESYTD = auto()
    DATESQTD = auto()
    DATESMTD = auto()
    SAMEPERIODLASTYEAR = auto()
    DATESBETWEEN = auto()
    DATESINPERIOD = auto()
    PARALLELPERIOD = auto()
    PREVIOUSMONTH = auto()
    PREVIOUSQUARTER = auto()
    PREVIOUSYEAR = auto()
    NEXTMONTH = auto()
    NEXTQUARTER = auto()
    NEXTYEAR = auto()

    # Arithmetic / comparison operators
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    AMP = auto()       # & string concat
    EQ = auto()        # =
    NEQ = auto()       # <>
    LT = auto()        # <
    LTE = auto()       # <=
    GT = auto()        # >
    GTE = auto()       # >=
    AND_OP = auto()    # &&
    OR_OP = auto()     # ||
    BANG = auto()      # ! (unary not)

    # Punctuation
    LPAREN = auto()
    RPAREN = auto()
    LBRACE = auto()    # {  — for IN {v1, v2}
    RBRACE = auto()    # }
    COMMA = auto()
    DOT = auto()
    CARET = auto()     # ^ (power in some DAX contexts)

    # Special
    EOF = auto()


# Maps uppercase keyword strings → TokenType
_KEYWORDS: dict[str, TokenType] = {
    "EVALUATE": TokenType.EVALUATE,
    "ORDER": TokenType.ORDER,
    "BY": TokenType.BY,
    "START": TokenType.START,
    "AT": TokenType.AT,
    "ASC": TokenType.ASC,
    "DESC": TokenType.DESC,
    "CALCULATE": TokenType.CALCULATE,
    "CALCULATETABLE": TokenType.CALCULATETABLE,
    "FILTER": TokenType.FILTER,
    "ALL": TokenType.ALL,
    "ALLEXCEPT": TokenType.ALLEXCEPT,
    "ALLNOBLANKROW": TokenType.ALLNOBLANKROW,
    "ALLSELECTED": TokenType.ALLSELECTED,
    "VALUES": TokenType.VALUES,
    "DISTINCT": TokenType.DISTINCT,
    "ADDCOLUMNS": TokenType.ADDCOLUMNS,
    "SELECTCOLUMNS": TokenType.SELECTCOLUMNS,
    "SUMMARIZE": TokenType.SUMMARIZE,
    "SUMMARIZECOLUMNS": TokenType.SUMMARIZECOLUMNS,
    "CROSSJOIN": TokenType.CROSSJOIN,
    "UNION": TokenType.UNION,
    "INTERSECT": TokenType.INTERSECT,
    "EXCEPT": TokenType.EXCEPT,
    "GENERATE": TokenType.GENERATE,
    "GENERATEALL": TokenType.GENERATEALL,
    "TOPN": TokenType.TOPN,
    "SAMPLE": TokenType.SAMPLE,
    "ROW": TokenType.ROW,
    "DATATABLE": TokenType.DATATABLE,
    "TREATAS": TokenType.TREATAS,
    "USERELATIONSHIP": TokenType.USERELATIONSHIP,
    "CROSSFILTER": TokenType.CROSSFILTER,
    "KEEPFILTERS": TokenType.KEEPFILTERS,
    "REMOVEFILTERS": TokenType.REMOVEFILTERS,
    "EARLIER": TokenType.EARLIER,
    "EARLIEST": TokenType.EARLIEST,
    "RELATED": TokenType.RELATED,
    "RELATEDTABLE": TokenType.RELATEDTABLE,
    "IF": TokenType.IF,
    "IFERROR": TokenType.IFERROR,
    "SWITCH": TokenType.SWITCH,
    "AND": TokenType.AND,
    "OR": TokenType.OR,
    "NOT": TokenType.NOT,
    "IN": TokenType.IN,
    "VAR": TokenType.VAR,
    "RETURN": TokenType.RETURN,
    "TRUE": TokenType.TRUE,
    "FALSE": TokenType.FALSE,
    "BLANK": TokenType.BLANK,
    "DATEADD": TokenType.DATEADD,
    "DATESYTD": TokenType.DATESYTD,
    "DATESQTD": TokenType.DATESQTD,
    "DATESMTD": TokenType.DATESMTD,
    "SAMEPERIODLASTYEAR": TokenType.SAMEPERIODLASTYEAR,
    "DATESBETWEEN": TokenType.DATESBETWEEN,
    "DATESINPERIOD": TokenType.DATESINPERIOD,
    "PARALLELPERIOD": TokenType.PARALLELPERIOD,
    "PREVIOUSMONTH": TokenType.PREVIOUSMONTH,
    "PREVIOUSQUARTER": TokenType.PREVIOUSQUARTER,
    "PREVIOUSYEAR": TokenType.PREVIOUSYEAR,
    "NEXTMONTH": TokenType.NEXTMONTH,
    "NEXTQUARTER": TokenType.NEXTQUARTER,
    "NEXTYEAR": TokenType.NEXTYEAR,
}


@dataclass(frozen=True)
class Token:
    type: TokenType
    value: str
    pos: int  # character offset in source

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r}, @{self.pos})"


class LexError(Exception):
    def __init__(self, message: str, pos: int) -> None:
        super().__init__(f"{message} at position {pos}")
        self.pos = pos


class Lexer:
    """Tokenises a DAX string into a list of Token objects.

    Notable rules:
    - ``'Quoted Name'`` → QUOTED_IDENTIFIER (single quotes)
    - ``"string"`` → STRING_LIT (double quotes)
    - Greedy: if an identifier is immediately followed by ``[``, the whole
      ``Identifier[Column]`` sequence is emitted as a single COLUMN_REF token.
    - ``[Column]`` alone → COLUMN_ONLY
    - ``//`` and ``/* … */`` comments are stripped
    - All keywords are case-insensitive
    """

    # Pre-compiled patterns for performance
    _WHITESPACE = re.compile(r"[ \t\r\n]+")
    _LINE_COMMENT = re.compile(r"//[^\n]*")
    _BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
    _NUMBER = re.compile(r"\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")
    _IDENTIFIER = re.compile(
        r"[A-Za-z_\u00C0-\u024F][A-Za-z0-9_\u00C0-\u024F]*")
    _COLUMN_BODY = re.compile(r"\[([^\]]+)\]")

    def __init__(self, text: str) -> None:
        self._text = text
        self._pos = 0
        self._tokens: List[Token] = []

    @classmethod
    def tokenize(cls, text: str) -> List[Token]:
        return cls(text)._scan()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _remaining(self) -> str:
        return self._text[self._pos:]

    def _emit(self, ttype: TokenType, value: str) -> None:
        self._tokens.append(Token(ttype, value, self._pos))

    def _advance(self, n: int) -> str:
        chunk = self._text[self._pos: self._pos + n]
        self._pos += n
        return chunk

    def _match(self, pattern: re.Pattern) -> re.Match | None:
        return pattern.match(self._text, self._pos)

    # ------------------------------------------------------------------
    # Main scan loop
    # ------------------------------------------------------------------

    def _scan(self) -> List[Token]:
        text = self._text

        while self._pos < len(text):
            start = self._pos

            # --- Whitespace ---
            m = self._WHITESPACE.match(text, self._pos)
            if m:
                self._pos = m.end()
                continue

            # --- Line comment ---
            m = self._LINE_COMMENT.match(text, self._pos)
            if m:
                self._pos = m.end()
                continue

            # --- Block comment ---
            m = self._BLOCK_COMMENT.match(text, self._pos)
            if m:
                self._pos = m.end()
                continue

            ch = text[self._pos]

            # --- Single-quoted identifier: 'Table Name' ---
            if ch == "'":
                self._pos += 1
                end = text.find("'", self._pos)
                if end == -1:
                    raise LexError(
                        "Unterminated single-quoted identifier", start)
                value = text[self._pos: end]
                self._pos = end + 1
                self._tokens.append(
                    Token(TokenType.QUOTED_IDENTIFIER, value, start))
                continue

            # --- Double-quoted string literal: "string value" ---
            if ch == '"':
                self._pos += 1
                parts = []
                while self._pos < len(text):
                    if text[self._pos] == '"':
                        # DAX escapes double-quote by doubling: "" means "
                        if self._pos + 1 < len(text) and text[self._pos + 1] == '"':
                            parts.append('"')
                            self._pos += 2
                        else:
                            self._pos += 1
                            break
                    else:
                        parts.append(text[self._pos])
                        self._pos += 1
                else:
                    raise LexError("Unterminated string literal", start)
                self._tokens.append(
                    Token(TokenType.STRING_LIT, "".join(parts), start))
                continue

            # --- [Column] standalone bracket reference ---
            if ch == "[":
                m = self._COLUMN_BODY.match(text, self._pos)
                if m:
                    self._tokens.append(
                        Token(TokenType.COLUMN_ONLY, m.group(1), start))
                    self._pos = m.end()
                else:
                    raise LexError(
                        f"Unterminated column reference at position {self._pos}", start)
                continue

            # --- Numbers ---
            m = self._NUMBER.match(text, self._pos)
            if m:
                self._tokens.append(Token(TokenType.NUMBER, m.group(), start))
                self._pos = m.end()
                continue

            # --- Identifiers and keywords (possibly followed by [Column]) ---
            m = self._IDENTIFIER.match(text, self._pos)
            if m:
                ident = m.group()
                self._pos = m.end()
                keyword_upper = ident.upper()

                # Greedy: if followed immediately by '[', emit as COLUMN_REF
                cm = self._COLUMN_BODY.match(text, self._pos)
                if cm:
                    col_name = cm.group(1)
                    self._tokens.append(
                        Token(TokenType.COLUMN_REF,
                              f"{ident}[{col_name}]", start)
                    )
                    self._pos = cm.end()
                    continue

                # Keyword?
                ttype = _KEYWORDS.get(keyword_upper, TokenType.IDENTIFIER)
                # Special-case: TRUE/FALSE/BLANK are literals but handled via keywords
                self._tokens.append(Token(ttype, ident, start))
                continue

            # --- Two-character operators (must be checked before single-char) ---
            two = text[self._pos: self._pos + 2]
            if two == "<>":
                self._tokens.append(Token(TokenType.NEQ, two, start))
                self._pos += 2
                continue
            if two == "<=":
                self._tokens.append(Token(TokenType.LTE, two, start))
                self._pos += 2
                continue
            if two == ">=":
                self._tokens.append(Token(TokenType.GTE, two, start))
                self._pos += 2
                continue
            if two == "&&":
                self._tokens.append(Token(TokenType.AND_OP, two, start))
                self._pos += 2
                continue
            if two == "||":
                self._tokens.append(Token(TokenType.OR_OP, two, start))
                self._pos += 2
                continue

            # --- Single-character tokens ---
            _SINGLE: dict[str, TokenType] = {
                "(": TokenType.LPAREN,
                ")": TokenType.RPAREN,
                "{": TokenType.LBRACE,
                "}": TokenType.RBRACE,
                ",": TokenType.COMMA,
                "+": TokenType.PLUS,
                "-": TokenType.MINUS,
                "*": TokenType.STAR,
                "/": TokenType.SLASH,
                "&": TokenType.AMP,
                "=": TokenType.EQ,
                "<": TokenType.LT,
                ">": TokenType.GT,
                ".": TokenType.DOT,
                "^": TokenType.CARET,
                "!": TokenType.BANG,
            }
            if ch in _SINGLE:
                self._tokens.append(Token(_SINGLE[ch], ch, start))
                self._pos += 1
                continue

            raise LexError(f"Unexpected character {ch!r}", self._pos)

        self._tokens.append(Token(TokenType.EOF, "", self._pos))
        return self._tokens
