"""Tests for proprioception.py's `parse: "tri_state_exit"` wrap parser (L13-PR2).

WHY THIS PARSE MODE EXISTS. `parse: "exit_code"` maps EVERY non-zero exit to DIVERGED.
That is right for a two-state tool ("clean" / "not clean"), and wrong for a receptor
that distinguishes three answers:

    0  CLEAN     I looked, and they match.
    1  DIVERGED  I looked, and they differ.
    2  BLIND     I could not look at all.

Filing BLIND as DIVERGED is worse than it first sounds. The two have OPPOSITE remedies:
DIVERGED needs the declared policy applied, BLIND needs an operator to restore
visibility. Collapsing them sends a healer to reconcile a difference nobody has
observed, and makes "we cannot see the enforced state" indistinguishable from "we can
see it and it is wrong". `scripts/tailnet_policy_drift.py` is the first such probe: on
this fleet the tailnet is allow-all and `policy.hujson` is proposed-not-applied, so its
honest answers are DIVERGED (policy unapplied) or BLIND (no readable netmap) — never
CLEAN. Reporting BLIND as drift would have made the receptor look like it had measured
something it never saw.

Each test names the mutation it would survive, because a parser test that only asserts
the happy mapping is satisfied by a parser that ignores rc entirely.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[1] / "proprioception.py"
_spec = importlib.util.spec_from_file_location("proprioception", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
prop = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prop)  # type: ignore[union-attr]


def _entry() -> dict:
    return {
        "id": "probe_under_test",
        "type": "wrap",
        "target": ["python3", "{repo}/scripts/tailnet_policy_drift.py"],
        "parse": "tri_state_exit",
    }


def _run(rc: int, out: str, err: str = "", monkeypatch=None) -> tuple[str, int, list[str]]:
    """Drive run_wrap with a stubbed subprocess so the mapping is exercised without
    needing the real probe on disk (and without a network call, ever)."""
    entry = _entry()

    def fake_sh(argv, timeout=None, cwd=None):  # noqa: ARG001
        return rc, out, err

    original_sh = prop.sh
    original_exists = Path.exists
    prop.sh = fake_sh  # type: ignore[assignment]
    Path.exists = lambda self: True  # type: ignore[method-assign]
    try:
        return prop.run_wrap(Path("/repo"), entry, timeout=5)
    finally:
        prop.sh = original_sh  # type: ignore[assignment]
        Path.exists = original_exists  # type: ignore[method-assign]


# ------------------------------------------------------------------ the three states

def test_exit_zero_is_reconciled() -> None:
    """Mutation it survives: a parser that returns DIVERGED unconditionally."""
    status, n, _ = _run(0, json.dumps({"verdict": "CLEAN", "evidence": []}))
    assert status == prop.RECONCILED
    assert n == 0


def test_exit_one_is_diverged_and_carries_the_probe_evidence() -> None:
    """Mutation it survives: a parser that drops the body and reports a bare count."""
    body = json.dumps({"verdict": "DIVERGED",
                       "evidence": ["1 rule: any-source -> 0.0.0.0/0 ports 0-65535"]})
    status, n, ev = _run(1, body)
    assert status == prop.DIVERGED
    assert n == 1
    assert any("0-65535" in e for e in ev)


def test_exit_two_is_unprobeable_not_diverged() -> None:
    """THE POINT OF THIS PARSE MODE. Under `parse: exit_code` this same input returns
    DIVERGED — the collapse this mode exists to prevent. Mutation it survives: routing
    rc==2 through _parse_exit_code."""
    body = json.dumps({"verdict": "BLIND", "reason": "tailscale CLI not present"})
    status, n, ev = _run(2, body)
    assert status == prop.UNPROBEABLE
    assert status != prop.DIVERGED
    assert n == 0
    assert any("tailscale CLI not present" in e for e in ev)

    # And the contrast is real, not asserted: the OLD parser genuinely disagrees.
    old_status, _, _ = prop._parse_exit_code(2, body, "")
    assert old_status == prop.DIVERGED


# ------------------------------------------------------- the exit code stays authoritative

def test_unparseable_body_does_not_override_the_exit_code() -> None:
    """A tri-state probe's verdict lives in its EXIT CODE. If a malformed body could
    turn a known verdict into UNPROBEABLE, the mode would hand its meaning back to the
    schema it was chosen to be independent of. Detail may be lost; the verdict may not.
    Mutation it survives: parsing JSON before the rc branch (the shape this parser
    originally had, corrected during review)."""
    status, _, _ = _run(1, "this is not json at all")
    assert status == prop.DIVERGED

    status, _, _ = _run(0, "")
    assert status == prop.RECONCILED

    status, _, ev = _run(2, "<html>gateway error</html>")
    assert status == prop.UNPROBEABLE
    assert ev  # still says something, even with no parseable body


def test_unexpected_exit_code_is_unprobeable_never_diverged() -> None:
    """A tool that promised three states and returned a fourth has drifted from its
    contract, and schema drift must not normalize into a verdict — the same rule
    findings_list already follows. Mutation it survives: a final `else: DIVERGED`."""
    status, n, ev = _run(3, json.dumps({"verdict": "???"}))
    assert status == prop.UNPROBEABLE
    assert status != prop.DIVERGED
    assert n == 0
    assert any("unexpected exit 3" in e for e in ev)


def test_blind_never_reports_as_clean() -> None:
    """The fail-safe polarity, stated as its own case because it is the one property a
    security receptor may never lose: no BLIND input may resolve to RECONCILED."""
    for body in ("", "null", "not json", json.dumps({"verdict": "BLIND"}),
                 json.dumps({"verdict": "CLEAN"})):
        status, _, _ = _run(2, body)
        assert status == prop.UNPROBEABLE, f"BLIND body {body!r} resolved to {status}"
        assert status != prop.RECONCILED


# ------------------------------------------------------------------ registry integrity

def test_selftest_still_passes_with_the_new_mode_registered() -> None:
    """The registry validator must accept the new entry; a parse mode the validator
    rejects would be dead on arrival."""
    errs = prop.validate_registry(prop.DEFAULT_REGISTRY)
    assert errs == [], errs
