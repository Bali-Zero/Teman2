#!/usr/bin/env python3
"""The subset of GitHub Actions expressions the service contexts use, evaluated the way the hosted runner does — and refused,
never guessed, outside it. Runner-owned: runner.py validates every expression at plan time and ships this file beside
steps_driver.py (sha-pinned) so steps' `if:`, `env:` and `run:` bodies are evaluated at run time, when `steps.*` exist.

Grammar: 'string' ('' escapes a quote), numbers, true/false/null, context paths (`a.b-c.d`), ( ), !, ==, !=, &&, ||, and the
status functions always() success() failure() cancelled(). Semantics (actions/runner's ExpressionUtility and EvaluationResult):
`&&`/`||` return an operand, not a bool; `==`/`!=` compare two strings ignoring case per character (OrdinalIgnoreCase), two
objects by identity, and coerce any other pair to numbers (null 0, true 1, a string trimmed: '' 0, decimal, 0x hex, 0o octal,
anything else NaN, which equals nothing); falsy = false, 0, '', null, NaN; property names match ignoring case. A path into a
context that does not exist is null; a ROOT the run does not model (secrets, inputs, hashFiles, ...) is an ExprError, and the
planner refuses a path under a modelled root whose hosted value the run does not hold (`paths()`) — never read as ''.
"""
from __future__ import annotations

import math
import re

ROOTS = ("github", "env", "matrix", "needs", "steps", "vars", "runner", "job", "strategy")
STATUS_FUNCS = ("always", "success", "failure", "cancelled")
_TOKEN = re.compile(r"\s*(?:(?P<str>'(?:[^']|'')*')|(?P<num>\d+(?:\.\d+)?)|(?P<op>==|!=|&&|\|\||!|\(|\))"
                    r"|(?P<word>[A-Za-z_][A-Za-z0-9_-]*(?:\.[A-Za-z_][A-Za-z0-9_-]*)*))")
_WRAP = re.compile(r"\$\{\{(.*?)\}\}", re.S)
_DEC = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")
_RADIX = re.compile(r"0(?:x([0-9a-fA-F]+)|o([0-7]+))")


class ExprError(ValueError):
    """An expression outside the modelled subset: the step cannot be planned or run honestly."""


def tokens(src: str) -> list:
    out, pos, src = [], 0, src.rstrip()
    while pos < len(src):
        m = _TOKEN.match(src, pos)
        if not m or m.end() == pos:
            raise ExprError(f"unsupported syntax at {src[pos:pos + 30]!r}")
        kind = m.lastgroup
        out.append((kind, m.group(kind)))
        pos = m.end()
    return out


def parse(src: str):
    """-> AST of tuples: ('lit', v) ('path', [parts]) ('not', a) ('cmp', op, a, b) ('and'|'or', a, b) ('call', name)."""
    toks, i = tokens(src), 0

    def peek():
        return toks[i] if i < len(toks) else (None, None)

    def take(want=None):
        nonlocal i
        tok = peek()
        if tok[0] is None or (want and tok[1] != want):
            raise ExprError(f"expected {want or 'a term'} in {src!r}")
        i += 1
        return tok

    def binary(level):
        ops = (("||",), ("&&",), ("==", "!="))[level]
        node = binary(level + 1) if level < 2 else unary()
        while peek()[1] in ops:
            op = take()[1]
            rhs = binary(level + 1) if level < 2 else unary()
            node = ("cmp", op, node, rhs) if level == 2 else ("or" if op == "||" else "and", node, rhs)
        return node

    def unary():
        if peek()[1] == "!":
            take()
            return ("not", unary())
        kind, val = take()
        if val == "(":
            node = binary(0)
            take(")")
            return node
        if kind == "str":
            return ("lit", val[1:-1].replace("''", "'"))
        if kind == "num":
            return ("lit", float(val))
        if kind != "word":
            raise ExprError(f"unexpected {val!r} in {src!r}")
        if val in ("true", "false", "null"):
            return ("lit", {"true": True, "false": False, "null": None}[val])
        if peek()[1] == "(":
            take("(")
            take(")")
            if val not in STATUS_FUNCS:
                raise ExprError(f"function {val}() is not modelled")
            return ("call", val)
        parts = val.split(".")
        parts[0] = parts[0].lower()
        if parts[0] not in ROOTS or [p.lower() for p in parts[:2]] == ["github", "token"]:
            raise ExprError(f"{val!r} is not modelled (a value hosted holds that this run does not)")
        return ("path", parts)

    node = binary(0)
    if i != len(toks):
        raise ExprError(f"trailing tokens in {src!r}")
    return node


def has_status_call(node) -> bool:
    return node[0] == "call" or any(isinstance(x, tuple) and has_status_call(x) for x in node[1:])


def paths(text: str) -> list:
    """Every context path the `${{ }}` in `text` reads (parts as written, root lowered)."""
    found: list = []

    def walk(n):
        if n[0] == "path":
            found.append(n[1])
        for x in n[1:]:
            if isinstance(x, tuple):
                walk(x)
    for m in _WRAP.finditer(text):
        walk(parse(m.group(1)))
    return found


def _num(v) -> float:
    if v is None:
        return 0.0
    if isinstance(v, (bool, int, float)):
        return float(v)
    if isinstance(v, (dict, list)):
        return math.nan
    t = str(v).strip()   # ExpressionUtility.ParseNumber: trim; '' 0; invariant decimal; unsigned 0x/0o read as an Int32; Infinity
    if t == "":
        return 0.0
    if _DEC.fullmatch(t):
        return float(t)
    if (m := _RADIX.fullmatch(t)):
        n = int(m.group(1), 16) if m.group(1) else int(m.group(2), 8)
        return math.nan if n > 0xFFFFFFFF else float(n - (1 << 32) if n >= 1 << 31 else n)
    return {"infinity": math.inf, "+infinity": math.inf, "-infinity": -math.inf}.get(t.lower(), math.nan)


def truthy(v) -> bool:
    return not (v is None or v is False or v == "" or (isinstance(v, (int, float)) and not isinstance(v, bool) and (v == 0 or math.isnan(v))))


def _fold(s: str) -> str:
    return "".join(u if len(u := c.upper()) == 1 else c for c in s)


def _eq(a, b) -> bool:
    if isinstance(a, str) and isinstance(b, str):
        return _fold(a) == _fold(b)
    if isinstance(a, (dict, list)) or isinstance(b, (dict, list)):
        return a is b
    if type(a) is type(b) and not isinstance(a, (int, float)):
        return a == b
    x, y = _num(a), _num(b)
    return not (math.isnan(x) or math.isnan(y)) and x == y


def evaluate(node, ctx: dict, status: str = "success"):
    kind = node[0]
    if kind == "lit":
        return node[1]
    if kind == "path":
        cur = ctx
        for p in node[1]:
            if not isinstance(cur, dict):
                return None
            cur = cur[p] if p in cur else next((v for k, v in cur.items() if k.lower() == p.lower()), None)
        return cur
    if kind == "call":
        return {"always": True, "success": status == "success", "failure": status == "failure", "cancelled": status == "cancelled"}[node[1]]
    if kind == "not":
        return not truthy(evaluate(node[1], ctx, status))
    if kind == "cmp":
        same = _eq(evaluate(node[2], ctx, status), evaluate(node[3], ctx, status))
        return same if node[1] == "==" else not same
    left = evaluate(node[1], ctx, status)
    if kind == "and":
        return evaluate(node[2], ctx, status) if truthy(left) else left
    return left if truthy(left) else evaluate(node[2], ctx, status)


def to_str(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else repr(v)
    return str(v)


def unwrap(cond: str) -> str:
    s = cond.strip()
    m = _WRAP.fullmatch(s)
    return m.group(1) if m else s


def validate(text: str) -> None:
    """Every `${{ }}` in `text` parses inside the subset (plan time); raises ExprError otherwise."""
    for m in _WRAP.finditer(text):
        parse(m.group(1))


def substitute(text: str, ctx: dict, status: str = "success") -> str:
    return _WRAP.sub(lambda m: to_str(evaluate(parse(m.group(1)), ctx, status)), text)


def step_runs(cond, ctx: dict, status: str) -> bool:
    """A step's `if:` as the runner decides it: no condition = success(); a condition without a status function is
    `success() && (cond)`."""
    if cond is None:
        return status == "success"
    node = parse(unwrap(str(cond)))
    if not has_status_call(node):
        node = ("and", ("call", "success"), node)
    return truthy(evaluate(node, ctx, status))
