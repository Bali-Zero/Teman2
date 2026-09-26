#!/usr/bin/env python3
"""Repo-wide guard, PENDING-ARMS L1287 (opened 2026-08-23, closed 2026-09-24):
two live call sites passed the literal tier "p1" to `_tg_notify`/`_ops_alert`.
tg_notify.py's argparse rejects any tier outside its own TIERS tuple, so
those two alarms failed silently -- the gateway subprocess exited non-zero,
`extract_gateway_verdict` yielded no verdict, and the caller logged and moved
on. This test statically scans every `scripts/**/*.py` file for a call to a
function literally named `_tg_notify` or `_ops_alert` and asserts any
constant-string tier argument (positional first-arg for `_tg_notify`,
keyword `tier=` for either) is a member of the gateway's real TIERS tuple --
parsed from tg_notify.py, never copied, so an edit to the gateway's tuple is
picked up automatically. A `p1` literal reintroduced anywhere fails this red.

Run:  python3 -m pytest scripts/tests/test_alert_tier_literals_valid.py -q
"""
from __future__ import annotations

import ast
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
ALERT_FUNCS = {"_tg_notify", "_ops_alert"}


def _gateway_tiers() -> tuple[str, ...]:
    gateway = REPO / "scripts" / "tg_notify.py"
    tree = ast.parse(gateway.read_text(encoding="utf-8"), filename=str(gateway))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "TIERS" for t in node.targets
        ):
            return tuple(ast.literal_eval(node.value))
    raise AssertionError(f"TIERS assignment not found in {gateway}")


def _tier_literal(call: ast.Call) -> object | None:
    """None means "no constant tier found" (dynamic value, or none passed) --
    not a violation, since we can only judge what's statically visible."""
    for kw in call.keywords:
        if kw.arg == "tier" and isinstance(kw.value, ast.Constant):
            return kw.value.value
    func_name = call.func.id if isinstance(call.func, ast.Name) else None
    if func_name == "_tg_notify" and call.args and isinstance(call.args[0], ast.Constant):
        return call.args[0].value
    return None


def _iter_violations(tiers: tuple[str, ...]):
    for path in sorted((REPO / "scripts").rglob("*.py")):
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id not in ALERT_FUNCS:
                continue
            literal = _tier_literal(node)
            if literal is not None and literal not in tiers:
                yield f"{path.relative_to(REPO)}:{node.lineno}: tier={literal!r} not in {tiers}"


def test_all_tg_notify_and_ops_alert_call_sites_use_a_real_tier():
    tiers = _gateway_tiers()
    violations = list(_iter_violations(tiers))
    assert not violations, (
        "found tier literal(s) argparse would reject at the real gateway "
        "(the alert would silently never deliver):\n" + "\n".join(violations)
    )


def test_guard_actually_catches_a_reintroduced_p1(tmp_path, monkeypatch):
    """Mutation check: without this guard, a reintroduced 'p1' call site is
    invisible until someone runs the probe by hand against the live gateway."""
    import sys

    this_mod = sys.modules[__name__]
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "tg_notify.py").write_text(
        'TIERS = ("p0", "digest", "log", "act")\n', encoding="utf-8"
    )
    (tmp_path / "scripts" / "offender.py").write_text(
        '_tg_notify("p1", "some-key", "some text")\n', encoding="utf-8"
    )
    monkeypatch.setattr(this_mod, "REPO", tmp_path)
    tiers = this_mod._gateway_tiers()
    violations = list(this_mod._iter_violations(tiers))
    assert any("offender.py" in v and "p1" in v for v in violations)
