"""
Convert solver expression strings into LaTeX.

The solver builds expressions such as::

    ((sqrt(9)+(4!))*2)
    Σ(i=1..4)(i*(i+3))
    (2**(3+1))

This module parses that small grammar and renders it as LaTeX with only the
parentheses that are actually needed, e.g. ``\\left(\\sqrt{9} + 4!\\right) \\times 2``.
"""

import re

# Precedence levels, low to high.
P_SUM = 0
P_ADD = 1
P_MUL = 2
P_NEG = 3
P_POW = 4
P_ATOM = 5

_TOKEN_RE = re.compile(r"\s*(\d+(?:\.\d+)?|\*\*|\.\.|sqrt|[Σ+\-*/()!=i])")


def _tokenize(s):
    tokens = []
    pos = 0
    s = s.strip()
    while pos < len(s):
        m = _TOKEN_RE.match(s, pos)
        if not m:
            raise ValueError(f"Unexpected character at {pos}: {s[pos]!r}")
        tokens.append(m.group(1))
        pos = m.end()
    return tokens


class _Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def take(self, expected=None):
        tok = self.peek()
        if tok is None or (expected is not None and tok != expected):
            raise ValueError(f"Expected {expected!r}, got {tok!r}")
        self.pos += 1
        return tok

    def parse(self):
        node = self.expr()
        if self.peek() is not None:
            raise ValueError(f"Trailing token {self.peek()!r}")
        return node

    # expr := term (('+'|'-') term)*
    def expr(self):
        node = self.term()
        while self.peek() in ("+", "-"):
            op = self.take()
            node = (op, node, self.term())
        return node

    # term := unary (('*'|'/') unary)*
    def term(self):
        node = self.unary()
        while self.peek() in ("*", "/"):
            op = self.take()
            node = (op, node, self.unary())
        return node

    # unary := '-' unary | power
    def unary(self):
        if self.peek() == "-":
            self.take()
            return ("neg", self.unary())
        return self.power()

    # power := postfix ('**' unary)?   (right-associative)
    def power(self):
        base = self.postfix()
        if self.peek() == "**":
            self.take()
            return ("**", base, self.unary())
        return base

    # postfix := primary '!'*
    def postfix(self):
        node = self.primary()
        while self.peek() == "!":
            self.take()
            node = ("!", node)
        return node

    def primary(self):
        tok = self.peek()
        if tok is None:
            raise ValueError("Unexpected end of expression")
        if tok == "(":
            self.take("(")
            node = self.expr()
            self.take(")")
            return node
        if tok == "sqrt":
            self.take()
            self.take("(")
            node = self.expr()
            self.take(")")
            return ("sqrt", node)
        if tok == "Σ":
            self.take()
            self.take("(")
            self.take("i")
            self.take("=")
            lo = self.expr()
            self.take("..")
            hi = self.expr()
            self.take(")")
            body = self.postfix()
            return ("sum", lo, hi, body)
        if tok == "i":
            self.take()
            return ("var", "i")
        if re.fullmatch(r"\d+(?:\.\d+)?", tok):
            self.take()
            return ("num", tok)
        raise ValueError(f"Unexpected token {tok!r}")


def _render(node):
    """Return (latex, precedence) for an AST node."""
    kind = node[0]

    if kind in ("num", "var"):
        return node[1], P_ATOM

    if kind == "sqrt":
        return rf"\sqrt{{{_render(node[1])[0]}}}", P_ATOM

    if kind == "neg":
        inner, p = _render(node[1])
        return f"-{_wrap(inner, p, P_NEG)}", P_NEG

    if kind == "!":
        inner, p = _render(node[1])
        return f"{_wrap(inner, p, P_ATOM)}!", P_ATOM

    if kind == "sum":
        lo = _render(node[1])[0]
        hi = _render(node[2])[0]
        body, p = _render(node[3])
        return rf"\sum_{{i={lo}}}^{{{hi}}} {_wrap(body, p, P_ATOM)}", P_SUM

    op, left, right = node
    l, lp = _render(left)
    r, rp = _render(right)
    if rp == P_NEG:
        # never print "2 + -3" or "2 \\times -3"
        r, rp = rf"\left({r}\right)", P_ATOM

    if op == "+":
        return f"{_wrap(l, lp, P_ADD)} + {_wrap(r, rp, P_MUL)}", P_ADD
    if op == "-":
        return f"{_wrap(l, lp, P_ADD)} - {_wrap(r, rp, P_MUL)}", P_ADD
    if op == "*":
        return rf"{_wrap(l, lp, P_MUL)} \times {_wrap(r, rp, P_POW)}", P_MUL
    if op == "/":
        return rf"\frac{{{l}}}{{{r}}}", P_ATOM
    if op == "**":
        return f"{_wrap(l, lp, P_ATOM)}^{{{r}}}", P_POW

    raise ValueError(f"Unknown node {kind!r}")


def _wrap(latex, prec, min_prec):
    if prec < min_prec:
        return rf"\left({latex}\right)"
    return latex


def expr_to_latex(expr):
    """Convert a solver expression string to LaTeX. Returns None if it can't be parsed."""
    try:
        return _render(_Parser(_tokenize(expr)).parse())[0]
    except (ValueError, IndexError):
        return None
