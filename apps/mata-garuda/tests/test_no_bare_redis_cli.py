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

import pathlib
import re

PKG = pathlib.Path(__file__).resolve().parent.parent / "mata_garuda"

# The ONLY files allowed to hand a literal "redis-cli" to subprocess: base_worker
# (the authed SSOT) and the split-brain guardian (probes BOTH hosts explicitly
# with its own self-contained _redis_env — it cannot use the single-host SSOT).
_ALLOWED = {"workers/base_worker.py"}

# subprocess.run( ... "redis-cli" ... )  — bare invocation on the same statement
_BARE = re.compile(r"subprocess\.run\([^)]*['\"]redis-cli['\"]", re.DOTALL)


def test_no_module_runs_bare_redis_cli():
    offenders = []
    for py in PKG.rglob("*.py"):
        rel = py.relative_to(PKG).as_posix()
        if rel in _ALLOWED:
            continue
        text = py.read_text(encoding="utf-8")
        if _BARE.search(text):
            offenders.append(rel)
    assert not offenders, (
        "bare `subprocess.run([... 'redis-cli' ...])` found — these bypass "
        "REDISCLI_AUTH and silently NOAUTH under requirepass (W89). Route through "
        f"base_worker.redis_cmd instead: {offenders}"
    )
