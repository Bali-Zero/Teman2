"""Structural lint: no mata_garuda module may run bare `redis-cli` via subprocess.

W89 meta-pattern (cicatrix #2 NOAUTH-swallow): PR #1825's Stage 1 cutover put the
canonical Pro Redis behind requirepass and cured base_worker + stream_tools, but
the migration was PARTIAL — 7 other modules kept their own bare `redis-cli`
subprocess calls with no REDISCLI_AUTH, so they silently degraded to green-but-
dead the moment the password went live.

This test makes the cure structural: it greps every mata_garuda source file for a
`subprocess.run([... "redis-cli" ...])` and FAILS if found, forcing all redis
access through base_worker.redis_cmd (the single authed path: REDISCLI_AUTH +
canonical host + abs-path). base_worker itself is the ONE allowed definition.

If a new module needs redis, it must `from mata_garuda.workers.base_worker import
redis_cmd` — not re-implement a bare helper. That keeps the auth fix from rotting.
"""
from __future__ import annotations

import ast
import pathlib

PKG = pathlib.Path(__file__).resolve().parent.parent / "mata_garuda"

# base_worker is the authed SSOT (its redis_cmd is the single allowed definition).
# Other files MAY call subprocess.run with "redis-cli" ONLY if that same call
# carries env= (nerve.py + check_redis_split_brain.py probe explicitly with their
# own _redis_env and cannot use the single-host SSOT). A call WITHOUT env= is the
# W89 offender (NOAUTH-swallow under requirepass). AST, not regex — paren-balanced.
_ALLOWED = {"workers/base_worker.py"}


def _call_has_redis_cli_literal(node: ast.Call) -> bool:
    """True if any arg (incl. inside a list literal) is the string 'redis-cli'."""
    def _strings(n):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            yield n.value
        for child in ast.iter_child_nodes(n):
            yield from _strings(child)
    return any(s == "redis-cli" for arg in node.args for s in _strings(arg))


def _is_subprocess_run(node: ast.Call) -> bool:
    f = node.func
    return isinstance(f, ast.Attribute) and f.attr == "run" and (
        (isinstance(f.value, ast.Name) and f.value.id == "subprocess")
    )


def test_no_unauthed_bare_redis_cli():
    offenders = []
    for py in PKG.rglob("*.py"):
        rel = py.relative_to(PKG).as_posix()
        if rel in _ALLOWED:
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and _is_subprocess_run(node)):
                continue
            if not _call_has_redis_cli_literal(node):
                continue
            kwargs = {kw.arg for kw in node.keywords if kw.arg}
            if "env" not in kwargs:
                offenders.append(f"{rel}:{node.lineno}")
    assert not offenders, (
        "subprocess.run([... 'redis-cli' ...]) WITHOUT env= found — these bypass "
        "REDISCLI_AUTH and silently NOAUTH under requirepass (W89). Route through "
        f"base_worker.redis_cmd (preferred) or pass env=_redis_env(): {offenders}"
    )
