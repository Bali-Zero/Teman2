#!/usr/bin/env python3
"""Corpus for scripts/probes/voa_deadman.py — L07-PR3.

WHY GUILT AND INNOCENCE, BOTH
------------------------------
The organ's whole point is a four-state lattice where two states must NEVER
fire (`dark`, `unknown`) and two classes of condition MUST fire (`fail`
verdict, and any flavour of silence: absent/unreadable/malformed/stale).
Getting either half wrong is dangerous in a different direction: firing on
`dark` pages an operator on every single tick pre-launch (an alarm that
always fires is an alarm nobody reads); NOT firing on a genuinely stale or
malformed heartbeat lets a dead probe sit invisible forever (superscar #2).
So every guilty case here has a paired innocent sibling that proves the
organ does not over-fire, per superscar #3 discipline (no guard merges
without both).

NO NETWORK CALLS. `send_telegram_p0()` shells out to `scripts/tg_notify.py`,
which itself never touches the network under `TG_DRY_RUN=1` (it writes to
`sent-dry.jsonl` in a scratch `TG_SPOOL_DIR` instead — see tg_notify.py's own
`send_telegram()`). Every test that exercises a fire path sets both env vars
to a fresh temp dir, so "Telegram message sent AND delivery verified" is
provable without ever reaching api.telegram.org: `tg_notify`'s own gateway
verdict of "sent" means it read a confirmed `{"ok": true}`-shaped response
from its (dry-run, faked) send_telegram() — the SAME code path a real
delivery takes, minus the actual HTTP call.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.probes import voa_deadman as vd  # noqa: E402

MODULE_PATH = _REPO_ROOT / "scripts" / "probes" / "voa_deadman.py"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _write_heartbeat(path: Path, **overrides) -> None:
    """Write a syntactically-valid heartbeat, PR-2's real contract shape,
    with any field overridden by the caller.
    """
    base = {
        "schema": 1,
        "probe": "voa_journey",
        "mode": "full",
        "ts": "2026-08-29T14:46:05.839Z",
        "ts_epoch": int(time.time()),
        "verdict": "pass",
        "reason": "page_live_journey_ok",
        "latency_ms": {"page": 100, "post": 50, "get": 40},
        "legs": {},
        "cleanup": {"attempted": 1, "verified_gone": 1, "unverified": 0, "leaked": 0},
        "base_url": "https://balizero.com",
        "probe_version": 1,
    }
    base.update(overrides)
    path.write_text(json.dumps(base))


@pytest.fixture()
def scratch_spool(tmp_path, monkeypatch):
    """A disposable tg_notify spool -- TG_DRY_RUN so no network call is ever
    made, TG_SPOOL_DIR so the real (shared, live) spool is never touched.
    """
    spool = tmp_path / "spool"
    monkeypatch.setenv("TG_DRY_RUN", "1")
    monkeypatch.setenv("TG_SPOOL_DIR", str(spool))
    return spool


def _sent_texts(spool: Path) -> list[str]:
    f = spool / "sent-dry.jsonl"
    if not f.is_file():
        return []
    out = []
    for line in f.read_text().splitlines():
        if line.strip():
            out.append(json.loads(line)["text"])
    return out


# --------------------------------------------------------------------------
# read_heartbeat — distinguishing SILENCE reasons
# --------------------------------------------------------------------------


def test_read_heartbeat_absent_file(tmp_path):
    hb = vd.read_heartbeat(str(tmp_path / "does-not-exist.json"))
    assert hb.ok is False
    assert hb.problem == "absent"


def test_read_heartbeat_malformed_json(tmp_path):
    p = tmp_path / "hb.json"
    p.write_text("{not json at all")
    hb = vd.read_heartbeat(str(p))
    assert hb.ok is False
    assert hb.problem == "malformed_json"
    # Distinct from "absent" — an operator debugging a false fire needs to
    # know the file EXISTS but is garbage, not that it is missing entirely.
    assert hb.problem != "absent"


def test_read_heartbeat_not_a_dict(tmp_path):
    p = tmp_path / "hb.json"
    p.write_text("[1, 2, 3]")
    hb = vd.read_heartbeat(str(p))
    assert hb.ok is False
    assert hb.problem == "malformed_json"


def test_read_heartbeat_wrong_schema(tmp_path):
    p = tmp_path / "hb.json"
    _write_heartbeat(p, schema=2)
    hb = vd.read_heartbeat(str(p))
    assert hb.ok is False
    assert hb.problem == "wrong_schema"


def test_read_heartbeat_schema_as_string_is_not_int_one(tmp_path):
    p = tmp_path / "hb.json"
    _write_heartbeat(p, schema="1")  # string "1" != int 1 — strict compare
    hb = vd.read_heartbeat(str(p))
    assert hb.ok is False
    assert hb.problem == "wrong_schema"


def test_read_heartbeat_missing_verdict(tmp_path):
    p = tmp_path / "hb.json"
    payload = {"schema": 1, "ts_epoch": int(time.time())}
    p.write_text(json.dumps(payload))
    hb = vd.read_heartbeat(str(p))
    assert hb.ok is False
    assert hb.problem == "unrecognized_verdict"


def test_read_heartbeat_unrecognized_verdict_value(tmp_path):
    p = tmp_path / "hb.json"
    _write_heartbeat(p, verdict="PASS")  # wrong case — not in the enum
    hb = vd.read_heartbeat(str(p))
    assert hb.ok is False
    assert hb.problem == "unrecognized_verdict"


def test_read_heartbeat_missing_ts_epoch(tmp_path):
    p = tmp_path / "hb.json"
    payload = {"schema": 1, "verdict": "pass"}
    p.write_text(json.dumps(payload))
    hb = vd.read_heartbeat(str(p))
    assert hb.ok is False
    assert hb.problem == "invalid_ts_epoch"


def test_read_heartbeat_bool_ts_epoch_rejected(tmp_path):
    p = tmp_path / "hb.json"
    _write_heartbeat(p, ts_epoch=True)  # bool is an int subclass in Python
    hb = vd.read_heartbeat(str(p))
    assert hb.ok is False
    assert hb.problem == "invalid_ts_epoch"


def test_read_heartbeat_valid_shape_ok(tmp_path):
    p = tmp_path / "hb.json"
    _write_heartbeat(p)
    hb = vd.read_heartbeat(str(p))
    assert hb.ok is True
    assert hb.problem == ""
    assert hb.data["verdict"] == "pass"


# --------------------------------------------------------------------------
# classify — the four-state lattice (superscar #3: guilt AND innocence)
# --------------------------------------------------------------------------


def _fresh(verdict: str, tmp_path, age_s: float = 5.0):
    p = tmp_path / "hb.json"
    now = time.time()
    _write_heartbeat(p, verdict=verdict, ts_epoch=int(now - age_s))
    return vd.read_heartbeat(str(p)), now



def test_guilt_directory_at_heartbeat_path_fires_with_specific_reason(tmp_path):
    """A directory sitting where the heartbeat FILE should be (a botched
    deploy, a stray `mkdir -p` one level too deep) is its own distinct
    SILENCE reason -- not conflated with "absent" (the path DOES exist) or
    a generic OSError. Found untested by the coordinator's systematic
    branch-mutation gate: flipping this branch's HeartbeatRead(False, ...)
    to True passed 43/43 before this test existed.
    """
    d = tmp_path / "hb.json"
    d.mkdir()
    hb = vd.read_heartbeat(str(d))
    assert hb.ok is False
    assert hb.problem == "unreadable_is_a_directory"

    decision = vd.classify(hb, time.time(), vd.DEFAULT_SILENCE_THRESHOLD_S)
    assert decision.fire is True
    assert decision.state == "fire_silence_unreadable_is_a_directory"
    # The reason must name THIS specific cause, not a generic one -- an
    # operator debugging a false fire at 3am reads this string, not the code.
    assert "unreadable_is_a_directory" in decision.reason
    assert decision.state != "fire_silence_absent"
    assert decision.state != "fire_silence_malformed_json"


def test_guilt_permission_denied_heartbeat_fires_with_specific_reason(tmp_path):
    """A heartbeat file that EXISTS but this process cannot read (chmod 000)
    is a third distinct SILENCE reason -- neither "absent" (the file is
    right there) nor "malformed" (we never got as far as reading its
    bytes). Skipped cleanly when running as root, where chmod 000 does not
    deny read access at all -- forcing the assertion there would fail for a
    reason that has nothing to do with this organ's logic. Found untested
    by the same gate as the directory case above.
    """
    if os.geteuid() == 0:
        pytest.skip("running as root -- chmod 000 does not deny root read access")
    p = tmp_path / "hb.json"
    _write_heartbeat(p)
    p.chmod(0o000)
    try:
        hb = vd.read_heartbeat(str(p))
    finally:
        p.chmod(0o644)  # restore so tmp_path's own cleanup can remove it

    assert hb.ok is False
    assert hb.problem == "unreadable_PermissionError"

    decision = vd.classify(hb, time.time(), vd.DEFAULT_SILENCE_THRESHOLD_S)
    assert decision.fire is True
    assert decision.state == "fire_silence_unreadable_PermissionError"
    assert "unreadable_PermissionError" in decision.reason


def test_guilt_invalid_utf8_heartbeat_fires_with_specific_reason(tmp_path):
    """Bytes that are not valid UTF-8 at all (a truncated write, a write
    from a process using a different encoding, a corrupted disk block) is a
    fourth distinct SILENCE reason -- the file exists and was readable as
    BYTES, but never decoded to text at all, which is a different failure
    from "decoded fine but was not valid JSON" (malformed_json). Found
    untested by the same gate: `grep -n 'utf8|utf-8|UnicodeDecode'` over
    this file returned nothing before this test existed.
    """
    p = tmp_path / "hb.json"
    p.write_bytes(b"\xff\xfe\x00")
    hb = vd.read_heartbeat(str(p))
    assert hb.ok is False
    assert hb.problem == "malformed_not_utf8"

    decision = vd.classify(hb, time.time(), vd.DEFAULT_SILENCE_THRESHOLD_S)
    assert decision.fire is True
    assert decision.state == "fire_silence_malformed_not_utf8"
    assert "malformed_not_utf8" in decision.reason
    assert decision.state != "fire_silence_malformed_json"


def test_innocence_fresh_pass_never_fires(tmp_path):
    hb, now = _fresh("pass", tmp_path)
    decision = vd.classify(hb, now, vd.DEFAULT_SILENCE_THRESHOLD_S)
    assert decision.fire is False
    assert decision.state == "healthy_pass"


def test_innocence_fresh_dark_never_fires(tmp_path):
    """`dark` is the pre-launch NORMAL state. A dead-man that fires on this
    fires on every tick — the one outcome this organ must never produce.
    """
    hb, now = _fresh("dark", tmp_path)
    decision = vd.classify(hb, now, vd.DEFAULT_SILENCE_THRESHOLD_S)
    assert decision.fire is False
    assert decision.state == "healthy_dark"


def test_innocence_fresh_unknown_never_fires(tmp_path):
    """`unknown` is unattributable to production — firing on it would be
    exactly the "outage the probe itself caused" class PR-2 was hardened
    against, one layer up.
    """
    hb, now = _fresh("unknown", tmp_path)
    decision = vd.classify(hb, now, vd.DEFAULT_SILENCE_THRESHOLD_S)
    assert decision.fire is False
    assert decision.state == "healthy_unknown"


def test_guilt_fresh_fail_fires(tmp_path):
    hb, now = _fresh("fail", tmp_path)
    decision = vd.classify(hb, now, vd.DEFAULT_SILENCE_THRESHOLD_S)
    assert decision.fire is True
    assert decision.state == "fire_fail"


def test_guilt_stale_pass_still_fires(tmp_path):
    """Staleness is judged BEFORE the verdict — a heartbeat that says
    verdict=pass but is older than the silence threshold is evidence the
    PROBE stopped, not that the funnel currently works.
    """
    hb, now = _fresh("pass", tmp_path, age_s=vd.DEFAULT_SILENCE_THRESHOLD_S + 1)
    decision = vd.classify(hb, now, vd.DEFAULT_SILENCE_THRESHOLD_S)
    assert decision.fire is True
    assert decision.state == "fire_silence_stale"


def test_innocence_almost_stale_pass_does_not_fire(tmp_path):
    """One second inside the threshold must not fire — a boundary check
    against an off-by-one in the comparison direction."""
    hb, now = _fresh("pass", tmp_path, age_s=vd.DEFAULT_SILENCE_THRESHOLD_S - 1)
    decision = vd.classify(hb, now, vd.DEFAULT_SILENCE_THRESHOLD_S)
    assert decision.fire is False
    assert decision.state == "healthy_pass"


def test_guilt_absent_heartbeat_fires_as_silence(tmp_path):
    hb = vd.read_heartbeat(str(tmp_path / "nope.json"))
    decision = vd.classify(hb, time.time(), vd.DEFAULT_SILENCE_THRESHOLD_S)
    assert decision.fire is True
    assert decision.state == "fire_silence_absent"


def test_guilt_malformed_heartbeat_fires_and_is_distinguishable(tmp_path):
    """A malformed heartbeat is SILENCE (fire-eligible), not silently
    healthy — AND its state label must differ from the absent-file case, so
    a human/wrapper can tell "the probe wrote garbage" from "nothing wrote
    anything at all".
    """
    p = tmp_path / "hb.json"
    p.write_text("{{{not json")
    hb = vd.read_heartbeat(str(p))
    decision = vd.classify(hb, time.time(), vd.DEFAULT_SILENCE_THRESHOLD_S)
    assert decision.fire is True
    assert decision.state == "fire_silence_malformed_json"
    assert decision.state != "fire_silence_absent"


def test_clock_skew_future_timestamp_does_not_crash_or_read_as_stale(tmp_path):
    """A future-dated ts_epoch (clock skew) must not crash and must not be
    read as "very stale" — negative age_s can never satisfy `age_s >
    threshold`, so it falls through to the verdict-based rule untouched.
    """
    p = tmp_path / "hb.json"
    now = time.time()
    _write_heartbeat(p, verdict="pass", ts_epoch=int(now + 10_000))  # far future
    hb = vd.read_heartbeat(str(p))
    decision = vd.classify(hb, now, vd.DEFAULT_SILENCE_THRESHOLD_S)  # must not raise
    assert decision.fire is False
    assert decision.state == "healthy_pass"
    assert decision.age_s is not None and decision.age_s < 0


# --------------------------------------------------------------------------
# real-fire gate — PIN: default OFF, only the exact literal arms it
# --------------------------------------------------------------------------



# --------------------------------------------------------------------------
# `_NEVER_FIRE_VERDICTS` -- the coordinator's gate found this constant was
# DEAD CODE: `classify()` decided fire/no-fire via independent hardcoded
# `if verdict == "dark": return Decision(False, ...)` branches, and this set
# sat next to them unread by anything (grep across the module AND the tests
# returned exactly its own definition; removing "dark" or "unknown" from it
# left 43/43 green). Fixed in classify() so the set now GOVERNS the boolean
# while the branches only supply the per-verdict state label + reason
# string. These two tests pin that relationship directly, so a future
# decoupling is caught here even before anyone runs a manual mutation pass.
# --------------------------------------------------------------------------


def test_pin_never_fire_verdicts_set_membership():
    """Direct pin on the set's exact contents -- this organ fires on
    exactly `_KNOWN_VERDICTS - _NEVER_FIRE_VERDICTS`, which today is
    `{"fail"}` alone. If this assertion ever needs to change, the change is
    a DELIBERATE widening/narrowing of what fires, not an accident.
    """
    assert vd._NEVER_FIRE_VERDICTS == frozenset({"pass", "dark", "unknown"})
    assert vd._KNOWN_VERDICTS - vd._NEVER_FIRE_VERDICTS == frozenset({"fail"})


@pytest.mark.parametrize("verdict", sorted(vd._KNOWN_VERDICTS))
def test_pin_fire_decision_for_known_verdicts_is_governed_by_never_fire_set(tmp_path, verdict):
    """For every known verdict at a FRESH age (staleness never in play),
    `classify()`'s fire boolean must equal `verdict not in
    _NEVER_FIRE_VERDICTS` -- computed from the SAME live constant the
    module exposes, not a hardcoded expectation. This proves classify() is
    actually WIRED to the set (catches a regression back to independent
    hardcoded booleans); it does NOT by itself catch a mutation of the
    set's own membership (both sides would move together) -- that is what
    the innocence/guilt tests elsewhere in this file (with a hardcoded
    True/False on each side) and the membership pin above are for.
    """
    hb, now = _fresh(verdict, tmp_path, age_s=5.0)
    decision = vd.classify(hb, now, vd.DEFAULT_SILENCE_THRESHOLD_S)
    assert decision.fire is (verdict not in vd._NEVER_FIRE_VERDICTS)


def test_pin_real_fire_default_is_off(monkeypatch):
    monkeypatch.delenv(vd._REAL_FIRE_ENV, raising=False)
    assert vd.real_fire_enabled() is False


@pytest.mark.parametrize(
    "value",
    ["true", "True", "1", "yes", "YES", "on", "REAL_FIRE_CONFIRMED_BY_ZERO ", " REAL_FIRE_CONFIRMED_BY_ZERO", "real_fire_confirmed_by_zero"],
)
def test_pin_real_fire_rejects_truthy_lookalikes(monkeypatch, value):
    """Only the EXACT literal arms it — not an ordinary boolean-looking
    value, not the right literal with stray whitespace, not a case variant.
    An operator setting this out of habit must not accidentally arm it.
    """
    monkeypatch.setenv(vd._REAL_FIRE_ENV, value)
    assert vd.real_fire_enabled() is False


def test_real_fire_exact_literal_arms_the_gate_check(monkeypatch):
    """The gate CHECK can report armed — but see the next test: even then,
    no `gh workflow run` invocation exists anywhere in this file."""
    monkeypatch.setenv(vd._REAL_FIRE_ENV, vd._REAL_FIRE_MAGIC)
    assert vd.real_fire_enabled() is True


def test_gh_workflow_run_is_never_invoked_anywhere_in_the_module():
    """Structural guard: the ONLY subprocess.run call site in this file is
    the Telegram gateway invocation. `gh workflow run` may appear as prose
    inside a message string (for the dry-run log/alert text), but never as
    an argv list handed to subprocess — even when the real-fire gate above
    reports itself armed.
    """
    src = MODULE_PATH.read_text()
    assert src.count("subprocess.run(") == 1, (
        "expected exactly one subprocess.run call site (the tg_notify gateway); "
        "found a different count — verify no gh-invoking code was added"
    )
    # The only place "gh" and "workflow" and "run" appear together as a
    # three-token sequence must be inside a string literal (message prose),
    # never as separate argv elements passed to a subprocess call.
    assert "gh workflow run" in src  # present as prose, in the dry-run message
    assert '"gh"' not in src and "'gh'" not in src  # never its own argv token


# --------------------------------------------------------------------------
# blast radius enumeration — PIN: all eight secrets + the restart
# --------------------------------------------------------------------------


def test_pin_blast_radius_enumerates_all_eight_secrets_and_restart():
    msg = vd.blast_radius_message()
    assert len(vd.GARUDA_ARM_SECRETS) == 8
    for name in vd.GARUDA_ARM_SECRETS:
        assert name in msg, f"blast radius message is missing {name}"
    assert "RESTART" in msg


def test_pin_fire_text_carries_the_full_blast_radius(tmp_path):
    hb, now = _fresh("fail", tmp_path)
    decision = vd.classify(hb, now, vd.DEFAULT_SILENCE_THRESHOLD_S)
    text = vd._build_fire_text(decision, str(tmp_path / "hb.json"))
    for name in vd.GARUDA_ARM_SECRETS:
        assert name in text
    assert "RESTART" in text
    assert "no `gh workflow run` invoked" in text


# --------------------------------------------------------------------------
# run_once — end to end (guilt: fire + telegram sent+verified; innocence: no alert)
# --------------------------------------------------------------------------


def test_guilt_stale_heartbeat_dry_run_fires_and_telegram_confirmed(tmp_path, scratch_spool):
    hb_path = tmp_path / "hb.json"
    _write_heartbeat(hb_path, verdict="pass", ts_epoch=int(time.time()) - 2000)

    decision, tg_verdict = vd.run_once(str(hb_path), vd.DEFAULT_SILENCE_THRESHOLD_S)

    assert decision.fire is True
    assert decision.state == "fire_silence_stale"
    # "Telegram message sent AND delivery verified" — tg_notify's own
    # canonical verdict for a confirmed delivery is exactly "sent" (see
    # scripts/tg_gateway_verdict.gateway_delivered).
    assert tg_verdict == "sent"

    sent = _sent_texts(scratch_spool)
    assert len(sent) == 1
    for name in vd.GARUDA_ARM_SECRETS:
        assert name in sent[0]
    assert "RESTART" in sent[0]


def test_innocence_fresh_pass_no_fire_no_alert(tmp_path, scratch_spool):
    hb_path = tmp_path / "hb.json"
    _write_heartbeat(hb_path, verdict="pass")

    decision, tg_verdict = vd.run_once(str(hb_path), vd.DEFAULT_SILENCE_THRESHOLD_S)

    assert decision.fire is False
    assert tg_verdict is None
    assert _sent_texts(scratch_spool) == []


def test_innocence_fresh_dark_no_fire_no_alert(tmp_path, scratch_spool):
    hb_path = tmp_path / "hb.json"
    _write_heartbeat(hb_path, verdict="dark")

    decision, tg_verdict = vd.run_once(str(hb_path), vd.DEFAULT_SILENCE_THRESHOLD_S)

    assert decision.fire is False
    assert tg_verdict is None
    assert _sent_texts(scratch_spool) == []


def test_guilt_absent_heartbeat_run_once_fires(tmp_path, scratch_spool):
    decision, tg_verdict = vd.run_once(
        str(tmp_path / "nope.json"), vd.DEFAULT_SILENCE_THRESHOLD_S
    )
    assert decision.fire is True
    assert decision.state == "fire_silence_absent"
    assert tg_verdict == "sent"


def test_run_once_prints_trailer_line_for_wrapper_grep(tmp_path, scratch_spool, capsys):
    hb_path = tmp_path / "hb.json"
    _write_heartbeat(hb_path, verdict="fail")
    vd.run_once(str(hb_path), vd.DEFAULT_SILENCE_THRESHOLD_S)
    out = capsys.readouterr().out
    assert "DEADMAN_RESULT state=fire_fail fire=True" in out


# --------------------------------------------------------------------------
# CLI entry (subprocess, exercises argparse + exit codes)
# --------------------------------------------------------------------------


def test_cli_healthy_exits_zero(tmp_path):
    hb_path = tmp_path / "hb.json"
    _write_heartbeat(hb_path, verdict="pass")
    env = dict(os.environ, TG_DRY_RUN="1", TG_SPOOL_DIR=str(tmp_path / "spool"))
    res = subprocess.run(
        [sys.executable, str(MODULE_PATH), "--heartbeat", str(hb_path)],
        capture_output=True, text=True, timeout=30, env=env,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    assert "dry-run mode (default)" in res.stdout


def test_cli_fire_exits_one(tmp_path):
    hb_path = tmp_path / "hb.json"
    _write_heartbeat(hb_path, verdict="fail")
    env = dict(os.environ, TG_DRY_RUN="1", TG_SPOOL_DIR=str(tmp_path / "spool"))
    res = subprocess.run(
        [sys.executable, str(MODULE_PATH), "--heartbeat", str(hb_path)],
        capture_output=True, text=True, timeout=30, env=env,
    )
    assert res.returncode == 1, res.stdout + res.stderr


def test_cli_test_alert_flag_sends_and_confirms(tmp_path):
    env = dict(os.environ, TG_DRY_RUN="1", TG_SPOOL_DIR=str(tmp_path / "spool"))
    res = subprocess.run(
        [sys.executable, str(MODULE_PATH), "--test-alert"],
        capture_output=True, text=True, timeout=30, env=env,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    assert "delivered=True verdict=sent" in res.stdout
    sent = _sent_texts(tmp_path / "spool")
    assert len(sent) == 1
    assert "channel liveness self-probe" in sent[0]


def test_cli_test_alert_does_not_read_heartbeat_at_all(tmp_path):
    """--test-alert must work even with NO heartbeat file present at all —
    it is a channel probe, not a fire-condition probe."""
    env = dict(
        os.environ,
        TG_DRY_RUN="1",
        TG_SPOOL_DIR=str(tmp_path / "spool"),
        VOA_PROBE_HEARTBEAT=str(tmp_path / "definitely-does-not-exist.json"),
    )
    res = subprocess.run(
        [sys.executable, str(MODULE_PATH), "--test-alert"],
        capture_output=True, text=True, timeout=30, env=env,
    )
    assert res.returncode == 0, res.stdout + res.stderr


def test_cli_real_fire_gate_armed_still_never_invokes_gh(tmp_path):
    """Even with the real-fire gate reporting itself armed, a fire condition
    must still only DRY-RUN log + alert — never invoke `gh`."""
    hb_path = tmp_path / "hb.json"
    _write_heartbeat(hb_path, verdict="fail")
    env = dict(
        os.environ,
        TG_DRY_RUN="1",
        TG_SPOOL_DIR=str(tmp_path / "spool"),
        VOA_DEADMAN_REAL_FIRE=vd._REAL_FIRE_MAGIC,
    )
    res = subprocess.run(
        [sys.executable, str(MODULE_PATH), "--heartbeat", str(hb_path)],
        capture_output=True, text=True, timeout=30, env=env,
    )
    assert res.returncode == 1, res.stdout + res.stderr
    assert "REAL-FIRE GATE ARMED" in res.stdout
    assert "refusing" in res.stdout
    # Still only ever a dry-run fire text, never an actual gh invocation.
    assert "no `gh workflow run` invoked" in res.stdout
