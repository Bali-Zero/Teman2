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
provable without ever reaching Telegram's API: `tg_notify`'s own gateway
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
    payload = {
        "schema": 1,
        "probe": "voa_journey",
        "mode": "full",
        "ts_epoch": int(time.time()),
    }
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
    payload = {
        "schema": 1,
        "probe": "voa_journey",
        "mode": "full",
        "verdict": "pass",
    }
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

    Reclassified in the SAME round (refuter item 7): a directory is now
    caught by the proactive "not a regular file" check (which also covers
    FIFOs/sockets/devices that would otherwise BLOCK the read forever),
    not by a dedicated IsADirectoryError except-arm -- that dedicated arm
    would have been dead code under every test this module can
    deterministically construct, the exact class of hazard just found in
    `_NEVER_FIRE_VERDICTS`. The problem code changed name; the guarantee
    (a directory here is SILENCE, distinctly labelled) did not.
    """
    d = tmp_path / "hb.json"
    d.mkdir()
    hb = vd.read_heartbeat(str(d))
    assert hb.ok is False
    assert hb.problem == "unreadable_not_a_regular_file"

    decision = vd.classify(hb, time.time(), vd.DEFAULT_SILENCE_THRESHOLD_S)
    assert decision.fire is True
    assert decision.state == "fire_silence_unreadable_not_a_regular_file"
    # The reason must name THIS specific cause, not a generic one -- an
    # operator debugging a false fire at 3am reads this string, not the code.
    assert "unreadable_not_a_regular_file" in decision.reason
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



# --------------------------------------------------------------------------
# Codex sol xhigh refuter round (3 CRITICAL / 8 HIGH / 5 MEDIUM / 1 LOW).
# Identity gate (item 6), regular-file + size bound (item 7), exact schema
# (item 8), and ts_epoch overflow/non-finite (items 3 + 5) all live inside
# read_heartbeat() -- one test per invariant below.
# --------------------------------------------------------------------------


def test_guilt_wrong_probe_identity_fires_with_specific_reason(tmp_path):
    """A fresh, otherwise well-formed `pass` heartbeat from a DIFFERENT
    probe must never be accepted as proof THIS production funnel is
    healthy (refuter CRITICAL, item 6) -- e.g. a stray heartbeat from an
    unrelated tool that happens to share this file's schema shape.
    """
    p = tmp_path / "hb.json"
    _write_heartbeat(p, probe="some_other_probe", verdict="pass")
    hb = vd.read_heartbeat(str(p))
    assert hb.ok is False
    assert hb.problem == "wrong_probe_identity:'some_other_probe'"

    decision = vd.classify(hb, time.time(), vd.DEFAULT_SILENCE_THRESHOLD_S)
    assert decision.fire is True
    assert "wrong_probe_identity" in decision.state
    assert "some_other_probe" in decision.reason


def test_guilt_non_production_mode_fires_with_specific_reason(tmp_path):
    """A `--dry-run` heartbeat (mode="dry_run") must never be accepted as
    proof production is healthy, even with a correct probe name and a
    `verdict=pass` (refuter CRITICAL, item 6) -- PR-2's own docstring says
    every heartbeat carries `mode` for exactly this reason.
    """
    p = tmp_path / "hb.json"
    _write_heartbeat(p, mode="dry_run", verdict="pass")
    hb = vd.read_heartbeat(str(p))
    assert hb.ok is False
    assert hb.problem == "non_production_mode:'dry_run'"

    decision = vd.classify(hb, time.time(), vd.DEFAULT_SILENCE_THRESHOLD_S)
    assert decision.fire is True
    assert "non_production_mode" in decision.state


def test_innocence_correct_identity_and_mode_pass_through(tmp_path):
    """The identity gate must not reject the ORDINARY, correct case --
    innocence sibling for the two guilt tests immediately above."""
    p = tmp_path / "hb.json"
    _write_heartbeat(p, probe="voa_journey", mode="full", verdict="pass")
    hb = vd.read_heartbeat(str(p))
    assert hb.ok is True
    assert hb.problem == ""



def test_probe_version_and_base_url_are_declared_not_gated(tmp_path):
    """`probe_version`/`base_url` are read but consciously NOT validated in
    this round (see read_heartbeat()'s own comment) -- "at minimum" per the
    gate meant probe name + production mode, not the full identity
    surface. Pinned so a mismatch here is currently ACCEPTED, and so a
    future tightening of this boundary is a deliberate, tested widening,
    not an accidental behaviour change discovered by surprise.
    """
    p = tmp_path / "hb.json"
    _write_heartbeat(
        p, probe_version=99, base_url="https://not-balizero.example", verdict="pass"
    )
    hb = vd.read_heartbeat(str(p))
    assert hb.ok is True  # consciously not gated in this round

def test_guilt_fifo_at_heartbeat_path_is_rejected_not_blocking(tmp_path):
    """A FIFO sitting at the heartbeat path would BLOCK `read_bytes()`
    forever without the proactive regular-file check (refuter MEDIUM, item
    7) -- and launchd will not start a second instance of this organ while
    the first hangs, so a hang here is the watcher itself going dark. This
    test's own pass/fail is the proof: if the check were missing, this test
    would HANG (and the timeout on the outer test run would fail it), not
    merely assert something false.
    """
    fifo_path = tmp_path / "hb.json"
    os.mkfifo(str(fifo_path))
    hb = vd.read_heartbeat(str(fifo_path))
    assert hb.ok is False
    assert hb.problem == "unreadable_not_a_regular_file"

    decision = vd.classify(hb, time.time(), vd.DEFAULT_SILENCE_THRESHOLD_S)
    assert decision.fire is True
    assert decision.state == "fire_silence_unreadable_not_a_regular_file"


def test_guilt_oversized_heartbeat_file_is_rejected(tmp_path):
    """A heartbeat file far larger than the real contract could ever be
    (a corrupted/runaway write) is rejected by stat BEFORE this organ reads
    it fully into memory (refuter MEDIUM, item 7 size bound).
    """
    p = tmp_path / "hb.json"
    p.write_bytes(b"x" * (vd._MAX_HEARTBEAT_BYTES + 1))
    hb = vd.read_heartbeat(str(p))
    assert hb.ok is False
    assert hb.problem == "unreadable_too_large"


def test_innocence_ordinary_sized_heartbeat_is_not_rejected(tmp_path):
    """The size bound must not reject a normal, real-shaped heartbeat --
    innocence sibling for the oversized test above."""
    p = tmp_path / "hb.json"
    _write_heartbeat(p, verdict="pass")
    assert p.stat().st_size < vd._MAX_HEARTBEAT_BYTES
    hb = vd.read_heartbeat(str(p))
    assert hb.ok is True


@pytest.mark.parametrize("schema_value", [True, 1.0, "1"])
def test_guilt_schema_lookalikes_are_rejected_not_treated_as_exactly_one(tmp_path, schema_value):
    """`True == 1` and `1.0 == 1` both hold in Python -- a bare `!= 1`
    check is NOT the strict int identity its own comment claims (refuter
    LOW, item 8). None of these three lookalikes may pass.
    """
    p = tmp_path / "hb.json"
    _write_heartbeat(p, schema=schema_value)
    hb = vd.read_heartbeat(str(p))
    assert hb.ok is False
    assert hb.problem == "wrong_schema"


def test_innocence_schema_exactly_int_one_passes(tmp_path):
    """The exactness fix must not reject the ORDINARY, correct case."""
    p = tmp_path / "hb.json"
    _write_heartbeat(p, schema=1, verdict="pass")
    hb = vd.read_heartbeat(str(p))
    assert hb.ok is True


def test_guilt_huge_json_integer_ts_epoch_overflows_to_silence_not_a_crash(tmp_path):
    """A JSON integer has no upper bound -- `json.loads` parses a 400-digit
    integer with no error, but `float()` on it raises OverflowError
    (refuter HIGH, item 5). Before this fix, that OverflowError propagated
    out of classify() uncaught: no Decision, no P0, no DEADMAN_RESULT line
    -- the crash itself silent, the worst possible failure mode for a
    dead-man. Must now be SILENCE, same as every other malformed shape, and
    must not raise.
    """
    p = tmp_path / "hb.json"
    _write_heartbeat(p, verdict="pass", ts_epoch=int("9" * 400))
    hb = vd.read_heartbeat(str(p))
    assert hb.ok is False
    assert hb.problem == "invalid_ts_epoch_overflow"

    decision = vd.classify(hb, time.time(), vd.DEFAULT_SILENCE_THRESHOLD_S)  # must not raise
    assert decision.fire is True
    assert decision.state == "fire_silence_invalid_ts_epoch_overflow"


@pytest.mark.parametrize("literal, label", [("NaN", "nan"), ("Infinity", "inf"), ("-Infinity", "-inf")])
def test_guilt_non_finite_ts_epoch_is_silence_not_an_immortal_green(tmp_path, literal, label):
    """Python's `json` module accepts the non-RFC8259 literals `NaN`/
    `Infinity`/`-Infinity` with no error by default (refuter HIGH, item 3)
    -- a `pass` heartbeat with `ts_epoch: Infinity` would never go stale
    under ANY threshold (`now - inf` is `-inf`, always <= threshold), an
    IMMORTAL false green. `1e309` silently overflows to the same `inf` at
    JSON-parse time, same bug, different spelling. All must be rejected as
    SILENCE, never accepted as a valid timestamp.
    """
    p = tmp_path / "hb.json"
    raw = (
        '{"schema": 1, "probe": "voa_journey", "mode": "full", '
        f'"verdict": "pass", "ts_epoch": {literal}}}'
    )
    p.write_text(raw)
    hb = vd.read_heartbeat(str(p))
    assert hb.ok is False
    assert hb.problem == "invalid_ts_epoch_non_finite"

    decision = vd.classify(hb, time.time(), vd.DEFAULT_SILENCE_THRESHOLD_S)  # must not raise
    assert decision.fire is True


def test_guilt_1e309_overflow_literal_ts_epoch_is_silence(tmp_path):
    """`1e309` is a syntactically ordinary JSON number literal that
    overflows to `float('inf')` at PARSE time (not an OverflowError, a
    silent overflow) -- a different code path than the huge-integer case
    above, same required outcome.
    """
    p = tmp_path / "hb.json"
    raw = (
        '{"schema": 1, "probe": "voa_journey", "mode": "full", '
        '"verdict": "pass", "ts_epoch": 1e309}'
    )
    p.write_text(raw)
    hb = vd.read_heartbeat(str(p))
    assert hb.ok is False
    assert hb.problem == "invalid_ts_epoch_non_finite"


def test_concurrent_write_via_temp_file_and_rename_is_never_observed_torn(tmp_path):
    """Refuted-and-confirmed by the coordinator's gate, not invented here:
    the producer (voa_journey_probe.mjs) writes a per-PID-random
    `<path>.<pid>.<random>.tmp` then RENAMES it over the target -- rename
    on one filesystem is atomic, so this organ can never observe a torn or
    partial write at the TARGET path, and needs no retry, no "read twice
    and compare" stable-read check, and no last-known-good fallback. This
    pins that guarantee directly: a writer mid-flight (a real, un-renamed
    temp file sitting NEXT TO the target, standing in for the split second
    before a concurrent `os.replace()`) must never be able to influence
    what `read_heartbeat()` sees at the STABLE target path.
    """
    target = tmp_path / "hb.json"
    _write_heartbeat(target, verdict="pass")  # the stable, already-renamed content

    # A writer mid-flight, at a DIFFERENT path in the same directory --
    # deliberately truncated/invalid, to prove its content can never leak
    # into a read of the target.
    concurrent_tmp = tmp_path / "hb.json.99999.deadbeef.tmp"
    concurrent_tmp.write_text('{"schema": 1, "verdict": "fail"')

    hb = vd.read_heartbeat(str(target))
    assert hb.ok is True
    assert hb.data["verdict"] == "pass"  # the stable content, never the in-flight temp file's

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



# --------------------------------------------------------------------------
# Sustained-unknown escalation (refuter CRITICAL, item 1) -- pure-function
# level first (no file I/O), then the real run_once() cross-tick level.
# --------------------------------------------------------------------------


def test_pin_unknown_escalation_streak_constant_and_margin_relationship():
    """Two structural pins the refuter's gate specifically asked for named
    constants over bare literals: the escalation streak is a small, named
    integer (not hidden in an if-condition), and the silence threshold is
    DERIVED with an explicit, nonzero margin over the producer's own
    interval -- `threshold == interval` exactly is the bug item 2 found.
    """
    assert vd.UNKNOWN_ESCALATION_STREAK == 3
    assert vd.SILENCE_MARGIN_S > 0
    assert vd.DEFAULT_SILENCE_THRESHOLD_S == vd.PRODUCER_INTERVAL_S + vd.SILENCE_MARGIN_S
    assert vd.DEFAULT_SILENCE_THRESHOLD_S > vd.PRODUCER_INTERVAL_S


def test_next_unknown_streak_increments_on_new_distinct_observation():
    state0 = vd.UnknownStreakState(0, None)
    state1 = vd._next_unknown_streak(state0, True, 1000.0)
    assert state1 == vd.UnknownStreakState(1, 1000.0)
    state2 = vd._next_unknown_streak(state1, True, 2000.0)
    assert state2 == vd.UnknownStreakState(2, 2000.0)


def test_next_unknown_streak_does_not_double_count_the_same_observation():
    """A faster deadman poll re-reading the SAME still-unwritten-over
    heartbeat (same ts_epoch) must not count as a second distinct
    occurrence -- otherwise one real `unknown` tick could satisfy the
    escalation streak entirely on its own within a single producer
    interval, defeating the point of requiring SUSTAINED, DISTINCT
    observations.
    """
    state1 = vd.UnknownStreakState(1, 1000.0)
    state_same = vd._next_unknown_streak(state1, True, 1000.0)
    assert state_same == state1  # unchanged, not incremented to 2


def test_next_unknown_streak_resets_on_non_unknown_observation():
    state2 = vd.UnknownStreakState(2, 2000.0)
    reset = vd._next_unknown_streak(state2, False, 3000.0)
    assert reset == vd.UnknownStreakState(0, None)


def test_apply_unknown_streak_escalation_n_minus_one_does_not_fire():
    """UNKNOWN_ESCALATION_STREAK - 1 consecutive distinct `unknown`
    observations must NOT escalate -- the boundary just below the
    threshold."""
    decision = vd.Decision(False, "healthy_unknown", "unattributable transport failure", 5.0)
    streak_before = vd.UnknownStreakState(vd.UNKNOWN_ESCALATION_STREAK - 2, 1000.0)
    escalated, streak_after = vd.apply_unknown_streak_escalation(decision, streak_before, 2000.0)
    assert streak_after.consecutive_unknown == vd.UNKNOWN_ESCALATION_STREAK - 1
    assert escalated.fire is False
    assert escalated.state == "healthy_unknown"


def test_apply_unknown_streak_escalation_at_n_fires():
    """Exactly UNKNOWN_ESCALATION_STREAK consecutive distinct `unknown`
    observations MUST escalate to fire-eligible -- the boundary AT the
    threshold, one more than the test immediately above."""
    decision = vd.Decision(False, "healthy_unknown", "unattributable transport failure", 5.0)
    streak_before = vd.UnknownStreakState(vd.UNKNOWN_ESCALATION_STREAK - 1, 1000.0)
    escalated, streak_after = vd.apply_unknown_streak_escalation(decision, streak_before, 2000.0)
    assert streak_after.consecutive_unknown == vd.UNKNOWN_ESCALATION_STREAK
    assert escalated.fire is True
    assert escalated.state == "fire_sustained_unknown"
    assert str(vd.UNKNOWN_ESCALATION_STREAK) in escalated.reason


def test_apply_unknown_streak_escalation_passes_through_non_unknown_decisions():
    """A `healthy_pass`/`fire_fail`/etc decision must pass through this
    layer completely unchanged -- escalation applies ONLY to `healthy_
    unknown`."""
    decision = vd.Decision(True, "fire_fail", "probe reported verdict=fail", 5.0)
    streak_before = vd.UnknownStreakState(vd.UNKNOWN_ESCALATION_STREAK - 1, 1000.0)
    passthrough, streak_after = vd.apply_unknown_streak_escalation(decision, streak_before, 2000.0)
    assert passthrough == decision
    assert streak_after == vd.UnknownStreakState(0, None)


def test_unknown_streak_state_round_trips_through_disk(tmp_path):
    path = str(tmp_path / "heartbeat.json.deadman-unknown-streak.json")
    state = vd.UnknownStreakState(2, 12345.0)
    vd._write_unknown_streak_state(path, state)
    read_back = vd._read_unknown_streak_state(path)
    assert read_back == state


def test_unknown_streak_state_missing_file_defaults_to_zero(tmp_path):
    path = str(tmp_path / "does-not-exist.json")
    assert vd._read_unknown_streak_state(path) == vd.UnknownStreakState(0, None)


def test_unknown_streak_state_malformed_file_defaults_to_zero_not_a_crash(tmp_path):
    path = tmp_path / "streak.json"
    path.write_text("{not json at all")
    assert vd._read_unknown_streak_state(str(path)) == vd.UnknownStreakState(0, None)


def test_run_once_sustained_unknown_fires_only_after_n_distinct_ticks(tmp_path, scratch_spool):
    """End-to-end: N-1 consecutive `run_once()` ticks over DISTINCT fresh
    `unknown` heartbeats must not fire; the Nth must fire, log the full
    blast radius, and send a confirmed Telegram alert -- exactly what the
    coordinator measured missing (three consecutive fresh `unknown` ticks,
    all `healthy_unknown fire=False`, forever).
    """
    hb_path = tmp_path / "hb.json"
    base_ts = int(time.time())

    for i in range(vd.UNKNOWN_ESCALATION_STREAK - 1):
        _write_heartbeat(hb_path, verdict="unknown", ts_epoch=base_ts + i)
        decision, tg_verdict = vd.run_once(str(hb_path), vd.DEFAULT_SILENCE_THRESHOLD_S)
        assert decision.fire is False, f"tick {i + 1} fired too early"
        assert tg_verdict is None

    _write_heartbeat(
        hb_path, verdict="unknown", ts_epoch=base_ts + vd.UNKNOWN_ESCALATION_STREAK - 1
    )
    decision, tg_verdict = vd.run_once(str(hb_path), vd.DEFAULT_SILENCE_THRESHOLD_S)
    assert decision.fire is True
    assert decision.state == "fire_sustained_unknown"
    assert tg_verdict == "sent"

    sent = _sent_texts(scratch_spool)
    assert len(sent) == 1
    for name in vd.GARUDA_ARM_SECRETS:
        assert name in sent[0]


def test_run_once_repeated_reads_of_the_same_unknown_heartbeat_do_not_fire(
    tmp_path, scratch_spool
):
    """The deadman polls faster than the producer writes -- re-reading the
    SAME still-current `unknown` heartbeat UNKNOWN_ESCALATION_STREAK+ times
    must never fire; only DISTINCT probe observations count.
    """
    hb_path = tmp_path / "hb.json"
    _write_heartbeat(hb_path, verdict="unknown", ts_epoch=int(time.time()))
    for _ in range(vd.UNKNOWN_ESCALATION_STREAK + 5):
        decision, tg_verdict = vd.run_once(str(hb_path), vd.DEFAULT_SILENCE_THRESHOLD_S)
        assert decision.fire is False
        assert tg_verdict is None


def test_run_once_a_healthy_tick_resets_the_unknown_streak(tmp_path, scratch_spool):
    """unknown, unknown, pass, unknown, unknown must NOT fire -- the pass
    in the middle resets the streak, so only 2 consecutive unknowns follow
    it, one short of UNKNOWN_ESCALATION_STREAK=3."""
    hb_path = tmp_path / "hb.json"
    base_ts = int(time.time())

    _write_heartbeat(hb_path, verdict="unknown", ts_epoch=base_ts)
    vd.run_once(str(hb_path), vd.DEFAULT_SILENCE_THRESHOLD_S)
    _write_heartbeat(hb_path, verdict="unknown", ts_epoch=base_ts + 1)
    vd.run_once(str(hb_path), vd.DEFAULT_SILENCE_THRESHOLD_S)

    _write_heartbeat(hb_path, verdict="pass", ts_epoch=base_ts + 2)
    decision, _ = vd.run_once(str(hb_path), vd.DEFAULT_SILENCE_THRESHOLD_S)
    assert decision.fire is False

    _write_heartbeat(hb_path, verdict="unknown", ts_epoch=base_ts + 3)
    decision, _ = vd.run_once(str(hb_path), vd.DEFAULT_SILENCE_THRESHOLD_S)
    assert decision.fire is False
    _write_heartbeat(hb_path, verdict="unknown", ts_epoch=base_ts + 4)
    decision, _ = vd.run_once(str(hb_path), vd.DEFAULT_SILENCE_THRESHOLD_S)
    assert decision.fire is False  # only 2 in a row since the reset -- one short


# --------------------------------------------------------------------------
# Silence-threshold validation (refuter HIGH, item 4) -- both the CLI's own
# `argparse type=float` parse and the env var's parse must be refused when
# non-finite/non-positive/non-numeric, never crash and never silently run
# with a threshold that cannot fire.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf"), 0.0, -5.0])
def test_validate_silence_threshold_rejects_non_finite_and_non_positive(bad_value):
    result = vd._validate_silence_threshold_s(bad_value, "test-source")
    assert result == vd.DEFAULT_SILENCE_THRESHOLD_S


def test_validate_silence_threshold_accepts_a_sane_positive_value():
    assert vd._validate_silence_threshold_s(1200.0, "test-source") == 1200.0


def test_resolve_silence_threshold_cli_nan_falls_back_to_default():
    """argparse's own `type=float` accepts "nan" exactly like bare
    `float()` -- the CLI path needs the SAME guard as the env-var path."""
    assert vd.resolve_silence_threshold_s(float("nan"), None) == vd.DEFAULT_SILENCE_THRESHOLD_S


def test_resolve_silence_threshold_env_inf_falls_back_to_default():
    assert vd.resolve_silence_threshold_s(None, "inf") == vd.DEFAULT_SILENCE_THRESHOLD_S


def test_resolve_silence_threshold_env_negative_falls_back_to_default():
    assert vd.resolve_silence_threshold_s(None, "-100") == vd.DEFAULT_SILENCE_THRESHOLD_S


def test_resolve_silence_threshold_env_non_numeric_does_not_crash():
    """A non-numeric env value used to raise ValueError BEFORE run_once()
    ever started -- no decision, no P0, no DEADMAN_RESULT line at all.
    Must now be caught and refused, never propagate."""
    assert vd.resolve_silence_threshold_s(None, "not-a-number") == vd.DEFAULT_SILENCE_THRESHOLD_S


def test_resolve_silence_threshold_env_sane_value_is_honoured():
    assert vd.resolve_silence_threshold_s(None, "1500") == 1500.0


def test_resolve_silence_threshold_cli_takes_precedence_over_env():
    assert vd.resolve_silence_threshold_s(1500.0, "2000") == 1500.0


def test_cli_nan_silence_threshold_does_not_crash_and_falls_back(tmp_path):
    """End-to-end: the CLI flag itself, not just the pure resolver."""
    hb_path = tmp_path / "hb.json"
    _write_heartbeat(hb_path, verdict="pass")
    env = dict(os.environ, TG_DRY_RUN="1", TG_SPOOL_DIR=str(tmp_path / "spool"))
    res = subprocess.run(
        [sys.executable, str(MODULE_PATH), "--heartbeat", str(hb_path), "--silence-threshold-s", "nan"],
        capture_output=True, text=True, timeout=30, env=env,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    assert "REFUSING invalid silence threshold" in res.stdout


def test_cli_bad_env_silence_threshold_does_not_crash_and_falls_back(tmp_path):
    hb_path = tmp_path / "hb.json"
    _write_heartbeat(hb_path, verdict="pass")
    env = dict(
        os.environ, TG_DRY_RUN="1", TG_SPOOL_DIR=str(tmp_path / "spool"),
        VOA_DEADMAN_SILENCE_THRESHOLD_S="not-a-number",
    )
    res = subprocess.run(
        [sys.executable, str(MODULE_PATH), "--heartbeat", str(hb_path)],
        capture_output=True, text=True, timeout=30, env=env,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    assert "REFUSING non-numeric" in res.stdout

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
