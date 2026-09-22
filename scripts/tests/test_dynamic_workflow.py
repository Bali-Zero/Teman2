"""Tests for scripts/dynamic_workflow.py — the /dynamic-workflow launcher (PR1a core:
brief/check/validate/ledger/selftest; PR1b: the r1 seat-dispatch launcher).

Loaded via importlib.util.spec_from_file_location (scripts/ is a flat bag, not a package,
mirrors scripts/tests/test_arsenal_probe.py). DW_FAKE_SEATS=1 (autouse) replaces every real
CLI launch and the real arsenal_probe.py subprocess with canned output.

The refusal/guilt scenarios below deliberately do NOT re-derive what dw.run_selftest()
already proves case-by-case (test_run_selftest_end_to_end drives that path) — they add the
INNOCENCE twins and the entry points --selftest never reaches, through the same public CLI
surface, table-driven.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import difflib
import importlib.util
import json
import os
import re
import shutil
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

import pytest

MODULE_PATH = Path(__file__).resolve().parent.parent / "dynamic_workflow.py"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "dynamic_workflow"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("dynamic_workflow", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


dw = _load_module()


@pytest.fixture(autouse=True)
def _fake_seats(monkeypatch):
    monkeypatch.setenv("DW_FAKE_SEATS", "1")


@pytest.fixture()
def template(tmp_path) -> Path:
    p = tmp_path / "template.md"
    p.write_text(dw._FIXTURE_TEMPLATE_TEXT)
    return p


@pytest.fixture()
def clean_objective(tmp_path) -> Path:
    p = tmp_path / "objective.txt"
    p.write_text("Design the workflow formation for the dynamic-workflow launcher. " * 3)
    return p


def _brief_ns(objective, template, kit, colour="BLUE"):
    return argparse.Namespace(slug="s", objective_file=str(objective), colour=colour,
                               floor=None, template=str(template), kit=str(kit))


def _dummy_objective(tmp_path) -> Path:
    p = tmp_path / "objective.txt"
    if not p.exists():
        p.write_text("Design the workflow formation for the dynamic-workflow launcher. " * 3)
    return p


def _seed_convener(kit: Path, text: str | None = None) -> str:
    sha = (kit / "brief.sha").read_text().strip()
    (kit / "r1" / "fable-5-1.md").write_text(text if text is not None
                                              else dw._CANNED_VALID.format(seat="fable-5-1", sha=sha))
    return sha


# --------------------------------------------------------------- guilt: refusals (SystemExit)

def _dirty_objective(tmp_path, template, kit):
    dirty = tmp_path / "dirty.txt"
    dirty.write_text("Reach me at +6281234567890 or foo@example.com about this review. " * 3)
    return lambda: dw.cmd_brief(_brief_ns(dirty, template, kit))


def _kit_inside_repo(tmp_path, template, _kit):
    # REFUSALS calls every `build` uniformly as build(tmp_path, template, kit); this one needs
    # its OWN kit path (must resolve inside REPO_ROOT), so the caller's `kit` is intentionally
    # unused — the leading underscore reads as "accepted, deliberately ignored" to every
    # linter in this repo without the varargs indirection an earlier branch needed.
    inside = dw.REPO_ROOT / "tmp-dw-kit-should-not-exist"
    return lambda: dw.cmd_brief(_brief_ns(_dummy_objective(tmp_path), template, inside))


def _check_hand_edited(tmp_path, template, kit):
    dw.cmd_brief(_brief_ns(_dummy_objective(tmp_path), template, kit))
    brief_path = kit / "BRIEF.md"
    brief_path.write_text(brief_path.read_text() + "\nhand-added line\n")
    return lambda: dw.cmd_check(argparse.Namespace(kit=str(kit)))


def _check_tamper(tmp_path, template, kit):
    dw.cmd_brief(_brief_ns(_dummy_objective(tmp_path), template, kit))
    dw.ledger_append(kit, "kimi-k3", "sent", "deadbeefcafef00d")
    lines = dw._ledger_path(kit).read_text().splitlines()
    dw._ledger_path(kit).write_text("\n".join(lines[:-1]) + "\n")  # drop a row, no re-hash
    return lambda: dw.cmd_check(argparse.Namespace(kit=str(kit)))


def _r1_no_convener(tmp_path, template, kit):
    dw.cmd_brief(_brief_ns(_dummy_objective(tmp_path), template, kit))
    return lambda: dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="kimi-k3", astra_fallback=False))


def _r1_invalid_convener(tmp_path, template, kit):
    dw.cmd_brief(_brief_ns(_dummy_objective(tmp_path), template, kit))
    (kit / "r1" / "fable-5-1.md").write_text("not a valid answer")
    return lambda: dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="kimi-k3", astra_fallback=False))


REFUSALS = [
    ("dirty objective -> PII gate", _dirty_objective, 3),
    ("kit inside repo", _kit_inside_repo, 2),
    ("check on a hand-edited BRIEF.md (W78)", _check_hand_edited, 1),
    ("check on a tampered ledger", _check_tamper, 1),
    ("r1 with no convener file", _r1_no_convener, 2),
    ("r1 with an invalid convener answer", _r1_invalid_convener, 2),
]


@pytest.mark.parametrize("label,build,code", REFUSALS, ids=[r[0] for r in REFUSALS])
def test_refuses_with_expected_exit_code(tmp_path, template, label, build, code):
    kit = tmp_path / f"kit-{abs(hash(label))}"
    action = build(tmp_path, template, kit)
    with pytest.raises(SystemExit) as exc:
        action()
    assert exc.value.code == code, label


# --------------------------------------------------------------- innocence: happy paths

def test_pii_gate_passes_and_check_passes(tmp_path, template, clean_objective, capsys):
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    assert (kit / "BRIEF.md").exists() and (kit / "brief.sha").exists()
    dw.cmd_check(argparse.Namespace(kit=str(kit)))  # must not raise
    assert "PASS" in capsys.readouterr().out


def test_brief_sha_stable_then_diverges_on_a_different_objective(tmp_path, template, clean_objective):
    kit1, kit2 = tmp_path / "k1", tmp_path / "k2"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit1))
    dw.cmd_brief(_brief_ns(clean_objective, template, kit2))
    assert (kit1 / "brief.sha").read_text() == (kit2 / "brief.sha").read_text()

    other = tmp_path / "other.txt"
    other.write_text("A completely different objective for the same launcher review. " * 3)
    kit3 = tmp_path / "k3"
    dw.cmd_brief(_brief_ns(other, template, kit3))
    assert (kit1 / "brief.sha").read_text() != (kit3 / "brief.sha").read_text()
    assert "{{SEAT}}" in (kit1 / "BRIEF.md").read_text()  # never collapsed by a generic replace


# --------------------------------------------------------------- arsenal liveness / squad block
# R10 + R3 (ruled 2026-09-20, first real run 2026-09-19): the squad block says only what the
# probe knows (status/healthy/latency_ms) and never its raw `evidence`, and a TIMEOUT status —
# an artifact of the probe's own 15s budget, not a verdict on the seat — renders as `unknown`,
# never as `dead`. These tests bypass the autouse DW_FAKE_SEATS path (which only ever reports
# LIVE) and fake arsenal_probe.py's own subprocess call, the same seam
# test_launch_seat_astra_resolves_a_seat_before_invoking_codex uses for `codex`.

def _fake_probe_run(seats: list[dict]):
    def _run(_cmd, **_kwargs):
        return argparse.Namespace(stdout=json.dumps({"seats": seats}), stderr="")
    return _run


def test_arsenal_liveness_block_drops_raw_evidence_and_rewrites_timeout_to_unknown(monkeypatch):
    monkeypatch.delenv("DW_FAKE_SEATS", raising=False)
    marker = "MARKER-raw-cli-output-7f3a"
    seats = [
        {"seat": "kimi", "status": "TIMEOUT", "healthy": False, "latency_ms": None,
         "evidence": marker},
        {"seat": "claude", "status": "LIVE", "healthy": True, "latency_ms": 320,
         "evidence": "PONG " + marker},
    ]
    monkeypatch.setattr(dw.subprocess, "run", _fake_probe_run(seats))

    block = dw._arsenal_liveness_block()

    assert marker not in block
    header = block.splitlines()[0]
    assert "evidence" not in header
    kimi_row = next(l for l in block.splitlines() if l.startswith("| kimi "))
    assert "TIMEOUT" not in kimi_row
    assert "False" not in kimi_row  # healthy is unknown too — R10, one column over
    assert f"unknown (probe budget {dw.PROBE_TIMEOUT_S} s)" in kimi_row
    assert "| unknown |" in kimi_row
    assert block.count(dw._ARSENAL_UNKNOWN_NOTE) == 1


def test_arsenal_liveness_block_evidence_marker_never_reaches_a_rendered_brief(
        tmp_path, template, clean_objective, monkeypatch):
    monkeypatch.delenv("DW_FAKE_SEATS", raising=False)
    marker = "MARKER-raw-cli-output-7f3a"
    seats = [{"seat": "agy", "status": "TIMEOUT", "healthy": False, "latency_ms": None,
              "evidence": marker}]
    monkeypatch.setattr(dw.subprocess, "run", _fake_probe_run(seats))

    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))

    assert marker not in (kit / "BRIEF.md").read_text()


@pytest.mark.parametrize("status,healthy", [
    ("LIVE", True), ("QUOTA_DEAD", False), ("AUTH_DEAD", False), ("NOT_INSTALLED", None),
])
def test_arsenal_liveness_block_keeps_known_statuses_and_healthy_verbatim(monkeypatch, status, healthy):
    # Only an exact `TIMEOUT` status gets its `status` AND `healthy` cells rewritten to
    # `unknown` — every other status keeps the probe's own `healthy` verdict untouched.
    monkeypatch.delenv("DW_FAKE_SEATS", raising=False)
    seats = [{"seat": "codex", "status": status, "healthy": healthy, "latency_ms": 10,
              "evidence": "irrelevant"}]
    monkeypatch.setattr(dw.subprocess, "run", _fake_probe_run(seats))

    block = dw._arsenal_liveness_block()

    row = next(l for l in block.splitlines() if l.startswith("| codex "))
    assert f"| {status} |" in row
    assert f"| {healthy} |" in row


def test_arsenal_liveness_block_does_not_rewrite_a_status_that_merely_contains_timeout(monkeypatch):
    # Scar family #3 (guard-over-match/under-match): the guard must judge the ENTITY "TIMEOUT",
    # never a substring — "TIMEOUT_RETRYING" is a different status and stays untouched.
    monkeypatch.delenv("DW_FAKE_SEATS", raising=False)
    seats = [{"seat": "jules", "status": "TIMEOUT_RETRYING", "healthy": False, "latency_ms": None,
              "evidence": "irrelevant"}]
    monkeypatch.setattr(dw.subprocess, "run", _fake_probe_run(seats))

    block = dw._arsenal_liveness_block()

    row = next(l for l in block.splitlines() if l.startswith("| jules "))
    assert "| TIMEOUT_RETRYING |" in row
    assert "unknown (probe budget" not in row
    assert "| False |" in row  # healthy stays verbatim too — only exact TIMEOUT rewrites it


def test_arsenal_liveness_block_fallback_path_is_still_a_well_formed_table_with_no_evidence(
        monkeypatch):
    monkeypatch.delenv("DW_FAKE_SEATS", raising=False)

    def _raise(_cmd, **_kwargs):
        raise dw.subprocess.TimeoutExpired(cmd=_cmd, timeout=600)
    monkeypatch.setattr(dw.subprocess, "run", _raise)

    block = dw._arsenal_liveness_block()
    lines = block.splitlines()

    header = lines[0]
    assert header == "| seat | status | healthy | latency_ms |"
    body_rows = [l for l in lines[2:] if l.startswith("|")]
    assert len(body_rows) == len(dw.FALLBACK_SEATS)
    for row in body_rows:
        assert row.count("|") == header.count("|")  # same column count, no dropped/extra cell
        assert "evidence" not in row
    assert block.count(dw._ARSENAL_UNKNOWN_NOTE) == 1


def test_arsenal_liveness_block_brief_sha_stable_across_identical_real_probe_runs(
        tmp_path, template, clean_objective, monkeypatch):
    monkeypatch.delenv("DW_FAKE_SEATS", raising=False)
    seats = [{"seat": "kimi", "status": "TIMEOUT", "healthy": False, "latency_ms": None,
              "evidence": "noise"},
             {"seat": "claude", "status": "LIVE", "healthy": True, "latency_ms": 200,
              "evidence": "PONG"}]
    monkeypatch.setattr(dw.subprocess, "run", _fake_probe_run(seats))

    kit1, kit2 = tmp_path / "k1", tmp_path / "k2"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit1))
    dw.cmd_brief(_brief_ns(clean_objective, template, kit2))

    assert (kit1 / "brief.sha").read_text() == (kit2 / "brief.sha").read_text()


def test_ledger_append_is_hashed_and_verify_passes(tmp_path, template, clean_objective):
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    dw.ledger_append(kit, "kimi-k3", "sent", "deadbeefcafef00d")
    dw.ledger_append(kit, "kimi-k3", "answered", "deadbeefcafef00d")
    ok, _ = dw.ledger_verify(kit)
    assert ok
    assert len(dw._ledger_path(kit).read_text().splitlines()) == 2


# --------------------------------------------------------------- ledger lock (guilt + innocence)
# append -> hash -> write .sha was three unlocked steps on two files. Measured on the unlocked
# launcher: 8 processes released by one barrier, one row each -> ledger_verify False in 11 of 60
# rounds (rows never lost, only the .sha stale). These pin the same interleavings
# deterministically: writer-a is parked at the one point where it has appended and hashed but
# not yet written the .sha (_ledger_sha_path is resolved right there, after the digest).

def _park_writer_a_before_its_sha_write(monkeypatch, parked, until, waited=None):
    real = dw._ledger_sha_path

    def resolve(kit):
        if threading.current_thread().name == "writer-a" and not parked.is_set():
            parked.set()
            got = until.wait(timeout=0.5 if waited is not None else 10)
            if waited is not None:
                waited.append(got)
        return real(kit)

    monkeypatch.setattr(dw, "_ledger_sha_path", resolve)


def test_ledger_sha_still_describes_the_ledger_when_a_second_writer_arrives_mid_append(
        tmp_path, monkeypatch):
    kit = tmp_path / "k"
    kit.mkdir()
    a_parked, b_done, b_finished_inside_a = threading.Event(), threading.Event(), []
    _park_writer_a_before_its_sha_write(monkeypatch, a_parked, b_done, waited=b_finished_inside_a)

    def writer_b():
        assert a_parked.wait(timeout=10)
        dw.ledger_append(kit, "seat-b", "sent", "b" * 16)
        b_done.set()

    a = threading.Thread(target=dw.ledger_append, args=(kit, "seat-a", "sent", "a" * 16),
                         name="writer-a")
    b = threading.Thread(target=writer_b, name="writer-b")
    a.start(), b.start()
    a.join(10), b.join(10)
    # unlocked, b appends and writes sha(a+b) inside a's pause, then a overwrites it with sha(a)
    ok, msg = dw.ledger_verify(kit)
    assert ok, msg
    assert b_finished_inside_a == [False]
    assert [r[1] for r in dw._ledger_rows(kit)] == ["seat-a", "seat-b"]


def test_ledger_verify_waits_for_an_append_in_flight_instead_of_calling_it_a_tamper(
        tmp_path, monkeypatch):
    kit = tmp_path / "k"
    kit.mkdir()
    dw.ledger_append(kit, "seat-a", "sent", "a" * 16)
    a_parked, release, verdict = threading.Event(), threading.Event(), []
    _park_writer_a_before_its_sha_write(monkeypatch, a_parked, release)
    a = threading.Thread(target=dw.ledger_append, args=(kit, "seat-a", "answered", "a" * 16),
                         name="writer-a")
    a.start()
    assert a_parked.wait(timeout=10)  # two rows on disk, .sha still describes one
    v_started = threading.Event()

    def verify():
        v_started.set()
        verdict.append(dw.ledger_verify(kit))

    v = threading.Thread(target=verify)
    v.start()
    assert v_started.wait(timeout=10)  # a verifier not yet scheduled would look "blocked" too
    v.join(0.3)
    answered_mid_append = not v.is_alive()
    release.set()
    a.join(10), v.join(10)
    assert verdict[0][0], verdict[0][1]
    assert not answered_mid_append


def test_ledger_verify_never_creates_the_lock_and_still_catches_a_real_tamper(tmp_path):
    kit = tmp_path / "k"
    kit.mkdir()
    assert dw.ledger_verify(kit) == (True, "no ledger yet")
    assert not (kit / "ledger.md.lock").exists()  # verifying must not write
    dw.ledger_append(kit, "seat-a", "sent", "a" * 16)
    dw.ledger_append(kit, "seat-a", "answered", "a" * 16)
    first_row = dw._ledger_path(kit).read_text().splitlines()[0]
    dw._ledger_path(kit).write_text(first_row + "\n")  # a row disappears, no re-hash
    ok, _ = dw.ledger_verify(kit)
    assert not ok


def test_r1_flaky_seat_succeeds_on_relaunch_and_ledger_stays_hashed(tmp_path, template, clean_objective):
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    summary = dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="z-fakeflaky", astra_fallback=False))
    assert summary["z-fakeflaky"] == "answered"
    assert dw.ledger_sent_count(kit, "z-fakeflaky") == 2
    ok, _ = dw.ledger_verify(kit)
    assert ok


def test_r1_invalid_seat_dies_then_refuses_a_third_sent_row(tmp_path, template, clean_objective):
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    summary1 = dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="x-fakeinvalid", astra_fallback=False))
    assert summary1["x-fakeinvalid"] == "dead"
    assert dw.ledger_sent_count(kit, "x-fakeinvalid") == 2
    summary2 = dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="x-fakeinvalid", astra_fallback=False))
    assert summary2["x-fakeinvalid"] == "refused-max-relaunch"
    assert dw.ledger_sent_count(kit, "x-fakeinvalid") == 2  # refusal adds no third sent row


def test_r1_astra_defaults_to_awaiting_window(tmp_path, template, clean_objective):
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    summary = dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="astra", astra_fallback=False))
    assert summary["astra"] == "awaiting-window"
    assert not (kit / "r1" / "astra.md").exists()


def test_launch_seat_astra_resolves_a_seat_before_invoking_codex(tmp_path, monkeypatch):
    """DW_FAKE_SEATS=1 (the autouse fixture, and --selftest) short-circuits _run_one_seat
    before it ever reaches _launch_seat, so the astra branch's real `codex exec` call has no
    coverage from the fake-seat path. This calls _launch_seat directly and proves the corpus
    rule (scripts/tests/test_codex_seat_lib.py::test_no_call_site_invokes_codex_without_choosing_a_seat)
    is actually satisfied in substance, not just in import: codex_seat_env() is called and its
    result is threaded into subprocess.run's env=, not a hand-rolled/omitted one."""
    kit = tmp_path / "k"
    (kit / "r1").mkdir(parents=True)
    sentinel_env = {"CODEX_HOME": "/fake/seat/dir"}
    calls = []

    def _fake_env(_env=None):
        return sentinel_env

    def _fake_run(_cmd, **kwargs):
        calls.append(kwargs)
        Path(_cmd[_cmd.index("-o") + 1]).write_text("stub output")
        return None

    monkeypatch.setattr(dw, "codex_seat_env", _fake_env)
    monkeypatch.setattr(dw.subprocess, "run", _fake_run)

    output = dw._launch_seat("astra", "prompt text", 5, kit)

    assert output == "stub output"
    assert len(calls) == 1
    assert calls[0].get("env") is sentinel_env
    assert calls[0].get("stdin") == dw.subprocess.DEVNULL


def test_launch_seat_astra_degrades_silently_when_no_seat_resolves(tmp_path, monkeypatch):
    """Innocence twin: codex_seat_env() with no logged-in seat returns the env unchanged
    (never raises, never adds an empty CODEX_HOME — see scripts/lib/codex_seat.py). The
    astra branch must still call it and still invoke codex, not treat "no seat" as a reason
    to skip resolution."""
    kit = tmp_path / "k"
    (kit / "r1").mkdir(parents=True)
    calls = []

    def _fake_env(_env=None):
        return dict(os.environ)

    def _fake_run(_cmd, **kwargs):
        calls.append(kwargs)
        return None

    monkeypatch.setattr(dw, "codex_seat_env", _fake_env)
    monkeypatch.setattr(dw.subprocess, "run", _fake_run)

    output = dw._launch_seat("astra", "prompt text", 5, kit)

    assert output == ""  # out_file never written, "no seat" is not a crash
    assert len(calls) == 1
    assert calls[0].get("env") == dict(os.environ)


def _codex_stub_writing(text: str | None, seen_cmds: list | None = None):
    """A subprocess.run stand-in for the astra branch: writes `text` to whatever path the
    command names after `-o` (None = codex wrote nothing), so the test follows the launcher's
    real output path instead of assuming one."""
    def _run(cmd, **_kwargs):
        if seen_cmds is not None:
            seen_cmds.append(cmd)
        if text is not None and "-o" in cmd:
            Path(cmd[cmd.index("-o") + 1]).write_text(text)
        return argparse.Namespace(stdout="")
    return _run


def test_launch_seat_astra_never_writes_into_the_kit(tmp_path, monkeypatch):
    """PR3i, GUILT (first real run 2026-09-19): the astra branch named kit/r1/astra.md as
    codex's `-o` target for EVERY caller, so a launch made by r2 or jury overwrote the seat's
    R1 answer. Seeds an R1 answer, launches astra again the way r2 does, and requires the R1
    bytes to survive and the `-o` path to sit outside the kit."""
    kit = tmp_path / "k"
    (kit / "r1").mkdir(parents=True)
    r1_answer = kit / "r1" / "astra.md"
    r1_answer.write_text("R1 ANSWER")
    seen: list = []
    monkeypatch.setattr(dw, "codex_seat_env", lambda _env=None: {})
    monkeypatch.setattr(dw.subprocess, "run", _codex_stub_writing("R2 OBJECTIONS", seen))

    output = dw._launch_seat("astra", "prompt text", 5, kit)

    assert output == "R2 OBJECTIONS"
    assert r1_answer.read_text() == "R1 ANSWER"
    out_target = Path(seen[0][seen[0].index("-o") + 1]).resolve()
    assert kit.resolve() not in out_target.parents


def test_launch_seat_astra_that_writes_nothing_returns_empty_not_stale_bytes(tmp_path, monkeypatch):
    """PR3i: with the target inside the kit, a relaunch whose codex wrote nothing found
    attempt 1's file still there and returned ITS bytes as attempt 2's answer."""
    kit = tmp_path / "k"
    (kit / "r1").mkdir(parents=True)
    (kit / "r1" / "astra.md").write_text("ATTEMPT 1")
    monkeypatch.setattr(dw, "codex_seat_env", lambda _env=None: {})
    monkeypatch.setattr(dw.subprocess, "run", _codex_stub_writing(None))

    assert dw._launch_seat("astra", "prompt text", 5, kit) == ""


def test_r2_with_a_real_astra_launch_keeps_its_r1_answer_and_pairs_on_the_formation(
        monkeypatch, tmp_path, template, clean_objective):
    """PR3i, end to end through cmd_r2's NON-fake branch — the path DW_FAKE_SEATS=1 never
    reaches, which is why only a real run found this. Pairing order is sorted, so astra
    launches first and is a review target of both other seats: before the fix they were handed
    astra's R2 objections in place of its R1 formation (the real kimi answered "Ruling on the
    four objections…")."""
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="astra,kimi-k3,gemini-3.1-pro-high",
                                  astra_fallback=True))
    r1_answer = kit / "r1" / "astra.md"
    r1_bytes = r1_answer.read_bytes()
    assert b"seat: astra" in r1_bytes

    r2_stub = "C1 this is astra's R2 objection.\nTest: run it twice."
    seen: list = []
    monkeypatch.delenv("DW_FAKE_SEATS", raising=False)
    monkeypatch.setattr(dw, "codex_seat_env", lambda _env=None: {})
    monkeypatch.setattr(dw.subprocess, "run", _codex_stub_writing(r2_stub, seen))

    dw.cmd_r2(argparse.Namespace(kit=str(kit)))

    assert r1_answer.read_bytes() == r1_bytes
    assert (kit / "r2" / "astra.raw.md").read_text() == r2_stub
    partner_prompts = [" ".join(c) for c in seen if c[0] != "codex"]
    assert len(partner_prompts) == 2
    for prompt in partner_prompts:
        assert "seat: astra" in prompt
        assert "astra's R2 objection" not in prompt


# --------------------------------------------------------------- r2 (guilt + innocence)

def _seed_answered(kit: Path, seat: str, text: str, sha16: str = "cafe") -> None:
    """Bypass cmd_r1 to seed an `answered` ledger row + r1/<seat>.md directly, for judge
    fixtures that need content cmd_r1's fake path cannot produce (a specific C1/C5/C8 defect)."""
    dw.ledger_append(kit, seat, "sent", sha16)
    (kit / "r1" / f"{seat}.md").write_text(text)
    dw.ledger_append(kit, seat, "answered", sha16)


def test_r2_pairing_is_deterministic_and_cross_family(tmp_path, template, clean_objective):
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="kimi-k3,qwen3.8-max,gemini-3.1-pro-high",
                                  astra_fallback=False))
    first = dw.cmd_r2(argparse.Namespace(kit=str(kit)))
    pairing_text = (kit / "pairing.md").read_text()
    second = dw.cmd_r2(argparse.Namespace(kit=str(kit)))
    assert (kit / "pairing.md").read_text() == pairing_text  # byte-for-byte, same recompute
    assert first == second
    pairing = dw.compute_pairing(kit, (kit / "brief.sha").read_text().strip())
    for seat, targets in pairing.items():
        assert seat not in targets
        target_families = {dw._seat_family(t) for t in targets}
        assert dw._seat_family(seat) not in target_families
        assert len(target_families) == len(targets)  # two DIFFERENT other families, not the same twice


def _parse_pairing_md_reviewers(text: str) -> dict[str, list[str]]:
    """Parses the `| seat | reviews |` table _render_pairing_md writes back into
    seat -> [reviewer, ...], splitting the reviews cell exactly the way the renderer joined
    it (', '.join). Shared by the two tests below."""
    rows: dict[str, list[str]] = {}
    for line in text.splitlines():
        if not line.startswith("| ") or line.startswith("| seat") or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        seat, reviews = cells[0], cells[1]
        rows[seat] = [r.strip() for r in reviews.split(",")] if reviews else []
    return rows


def test_r2_pairing_md_content_matches_in_memory_pairing_exactly(tmp_path, template,
                                                                   clean_objective):
    """Item 1 (PR2g, dw-gate-7 REWORK-BUILD on PR2e #6772, sha 76f0580b): mutating the
    renderer to `', '.join(pairing[seat][:1])` — one of the two mandated cross-family
    reviewers silently dropped from every WRITTEN row — left the suite at 79/79 green,
    because every existing pairing test only ever inspected the in-memory `pairing` dict or
    pairing.md's byte-identity across two recomputes, never the WRITTEN table's own per-seat
    content against that dict. This parses pairing.md back and asserts, per seat, the WRITTEN
    reviewers equal the in-memory ones exactly. Reopens and closes gate-4 obs (b)."""
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="kimi-k3,qwen3.8-max,gemini-3.1-pro-high",
                                  astra_fallback=False))
    dw.cmd_r2(argparse.Namespace(kit=str(kit)))
    pairing = dw.compute_pairing(kit, (kit / "brief.sha").read_text().strip())
    written = _parse_pairing_md_reviewers((kit / "pairing.md").read_text())
    assert set(written) == set(pairing)
    for seat, reviewers in pairing.items():
        assert written[seat] == reviewers  # exact two, exact identity, exact order
        assert len(written[seat]) == 2
        assert len({dw._seat_family(r) for r in written[seat]}) == 2


def test_r2_pairing_md_parse_would_catch_the_dropped_reviewer_mutation(tmp_path, template,
                                                                        clean_objective):
    """Proves the assertion above is not vacuous: re-rendering the SAME pairing dict with
    gate-7's exact mutated join (`pairing[seat][:1]`, one reviewer dropped) produces a
    pairing.md whose parsed content the equality check above would reject — the mutation that
    left the OLD suite green now fails here."""
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="kimi-k3,qwen3.8-max,gemini-3.1-pro-high",
                                  astra_fallback=False))
    pairing = dw.compute_pairing(kit, (kit / "brief.sha").read_text().strip())
    mutated_lines = ["| seat | reviews |", "|---|---|"]
    for seat in sorted(pairing):
        mutated_lines.append(f"| {seat} | {', '.join(pairing[seat][:1])} |")  # gate-7's mutation
    written = _parse_pairing_md_reviewers("\n".join(mutated_lines) + "\n")
    for seat, reviewers in pairing.items():
        assert written[seat] != reviewers  # the drop is now visible: 1 reviewer, not 2


def test_r2_refuses_a_mutated_pairing_md(tmp_path, template, clean_objective):
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="kimi-k3,qwen3.8-max,gemini-3.1-pro-high",
                                  astra_fallback=False))
    dw.cmd_r2(argparse.Namespace(kit=str(kit)))
    (kit / "pairing.md").write_text((kit / "pairing.md").read_text() + "| tampered | row |\n")
    with pytest.raises(SystemExit) as e:
        dw.cmd_r2(argparse.Namespace(kit=str(kit)))
    assert e.value.code == 2


def test_r2_filter_keeps_only_objections_with_an_fc_ref_and_a_test_line(tmp_path, template, clean_objective):
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="kimi-k3,qwen3.8-max,gemini-3.1-pro-high",
                                  astra_fallback=False))
    summary = dw.cmd_r2(argparse.Namespace(kit=str(kit)))
    for seat, counts in summary.items():
        assert counts == {"kept": 1, "rejected": 1}
        assert (kit / "r2" / f"{seat}.md").exists()
        assert (kit / "r2" / f"{seat}.rejected.md").exists()
        assert dw._FC_REF_RE.search((kit / "r2" / f"{seat}.md").read_text())


def test_r2_filter_drops_a_referenceless_no_test_objection_entirely(tmp_path, template,
                                                                      clean_objective, monkeypatch):
    # "gemini-3.1-pro-high" is a REAL FAMILY_MAP seat (r2's fail-closed family check now refuses
    # any answered seat outside FAMILY_MAP, so the old "<seat>-fakenoobject" synthetic identity
    # can no longer stand in as a reviewer); force ITS fake r2 reply to be a no-objection one.
    real_fake_r2_output = dw._fake_r2_output

    def _forced_no_objection(seat: str) -> str:
        if seat == "gemini-3.1-pro-high":
            return "No objections. Everything checks out fine here."
        return real_fake_r2_output(seat)

    monkeypatch.setattr(dw, "_fake_r2_output", _forced_no_objection)
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="kimi-k3,qwen3.8-max,gemini-3.1-pro-high",
                                  astra_fallback=False))
    summary = dw.cmd_r2(argparse.Namespace(kit=str(kit)))
    assert summary["gemini-3.1-pro-high"] == {"kept": 0, "rejected": 1}
    assert not (kit / "r2" / "gemini-3.1-pro-high.md").read_text().strip()


def test_r2_marks_a_seat_that_returned_nothing_as_dead_not_as_no_objections(
        tmp_path, template, clean_objective, monkeypatch, capsys):
    """First real run (2026-09-19): one r2 seat returned 0 bytes and its ledger row read
    `r2-kept=0-rejected=0` — byte-identical to a seat that answered and simply had no
    objections (scar family #2, 'exists != armed'). This exercises cmd_r2's NON-fake branch
    (mirrors test_r2_with_a_real_astra_launch_keeps_its_r1_answer_and_pairs_on_the_formation),
    because DW_FAKE_SEATS never returns an empty string."""
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="kimi-k3,qwen3.8-max,gemini-3.1-pro-high",
                                  astra_fallback=False))
    objection = "C1 something.\nTest: run it."
    monkeypatch.delenv("DW_FAKE_SEATS", raising=False)
    monkeypatch.setattr(
        dw, "_launch_seat",
        lambda seat, prompt, timeout, kit: "" if seat == "kimi-k3" else objection)

    dw.cmd_r2(argparse.Namespace(kit=str(kit)))

    rows = {r[1]: r[2] for r in dw._ledger_rows(kit) if r[2].startswith("r2-")}
    assert rows["kimi-k3"] == "r2-dead"
    assert rows["qwen3.8-max"].startswith("r2-kept=")
    assert rows["gemini-3.1-pro-high"].startswith("r2-kept=")
    assert "kimi-k3: dead (empty output)" in capsys.readouterr().out


def test_r2_keeps_the_kept_rejected_row_for_a_seat_whose_objections_were_all_filtered(
        tmp_path, template, clean_objective, monkeypatch):
    """A real answer with every objection filtered by _objection_ok stays
    r2-kept=0-rejected=N — it is NOT dead, unlike an empty raw_output. Same real-launch shape
    as the GUILT twin above, proving the two are told apart."""
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="kimi-k3,qwen3.8-max,gemini-3.1-pro-high",
                                  astra_fallback=False))
    objection = "C1 something.\nTest: run it."
    no_ref_no_test = "Just a vague worry, no F/C reference and no Test line at all."
    monkeypatch.delenv("DW_FAKE_SEATS", raising=False)
    monkeypatch.setattr(
        dw, "_launch_seat",
        lambda seat, prompt, timeout, kit: no_ref_no_test if seat == "kimi-k3" else objection)

    summary = dw.cmd_r2(argparse.Namespace(kit=str(kit)))

    assert summary["kimi-k3"] == {"kept": 0, "rejected": 1}
    rows = {r[1]: r[2] for r in dw._ledger_rows(kit) if r[2].startswith("r2-")}
    assert rows["kimi-k3"] == "r2-kept=0-rejected=1"


# --------------------------------------------------------------- r2 table objections (guilt + innocence)
# Owner ruling (2026-09-20): first real r2 run kept 0/16 real objections because the prompt
# never stated the parsed shape and the filter had no path for a markdown table (astra's real
# answer, 2026-09-19) — only for a `Test:`-line paragraph.

def test_r2_prompt_prefix_states_the_paragraph_shape_and_keeps_the_sealed_sentence():
    assert "Test:" in dw._R2_PROMPT_PREFIX
    assert dw._SEALED_SENTENCE in dw._R2_PROMPT_PREFIX


def test_r2_filter_table_with_a_test_column_splits_rows_and_reassembles_valid_tables(
        tmp_path, template, clean_objective, monkeypatch):
    """Guilt: astra's real shape — one objection per table row, with a test column. Mixed rows:
    F/C+real test (kept), no F/C (rejected), test cell is a placeholder (rejected) — split per
    row, counts match, both output files stay well-formed tables (header + separator + rows)."""
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="kimi-k3,qwen3.8-max,gemini-3.1-pro-high",
                                  astra_fallback=False))
    table = ("| Objection | Ref | Test |\n"
             "|---|---|---|\n"
             "| pairing may drift | F1 | rerun r2 twice, diff pairing.md |\n"
             "| vague worry, no ref | | rerun it |\n"
             "| no real test | F2 | n/a |\n")
    monkeypatch.delenv("DW_FAKE_SEATS", raising=False)
    monkeypatch.setattr(dw, "_launch_seat", lambda seat, prompt, timeout, kit: table)

    summary = dw.cmd_r2(argparse.Namespace(kit=str(kit)))

    for seat, counts in summary.items():
        assert counts == {"kept": 1, "rejected": 2}
        kept_text = (kit / "r2" / f"{seat}.md").read_text()
        rejected_text = (kit / "r2" / f"{seat}.rejected.md").read_text()
        for text in (kept_text, rejected_text):
            lines = [ln for ln in text.splitlines() if ln.strip()]
            assert lines[0] == "| Objection | Ref | Test |"
            assert dw._is_md_separator_row(lines[1])
        assert "F1" in kept_text and "F1" not in rejected_text
        assert "F2" in rejected_text


def test_r2_filter_table_with_no_test_column_is_still_rejected_as_one_prose_unit(
        tmp_path, template, clean_objective, monkeypatch):
    """Innocence: a table with no column named 'test' is not exploded per row — the paragraph
    goes through _objection_ok whole, and a table row is not a `Test:` line, so it is rejected."""
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="kimi-k3,qwen3.8-max,gemini-3.1-pro-high",
                                  astra_fallback=False))
    table = "| Objection | Ref |\n|---|---|\n| pairing may drift | F1 |\n"
    monkeypatch.delenv("DW_FAKE_SEATS", raising=False)
    monkeypatch.setattr(dw, "_launch_seat", lambda seat, prompt, timeout, kit: table)

    summary = dw.cmd_r2(argparse.Namespace(kit=str(kit)))
    for seat, counts in summary.items():
        assert counts == {"kept": 0, "rejected": 1}


def test_filter_objection_paragraph_prose_without_test_line_is_still_rejected():
    kept, rejected, kc, rc = dw._filter_objection_paragraph("F1 something is off, no test line.")
    assert kept is None and rejected is not None and (kc, rc) == (0, 1)


def test_filter_objection_paragraph_prose_with_fc_and_test_is_still_kept():
    para = "F1 something is off.\nTest: rerun it."
    kept, rejected, kc, rc = dw._filter_objection_paragraph(para)
    assert kept == para and rejected is None and (kc, rc) == (1, 0)


def test_filter_objection_paragraph_table_row_with_test_cell_but_no_fc_ref_is_rejected():
    table = "| Objection | Test |\n|---|---|\n| vague worry | rerun it |\n"
    kept, rejected, kc, rc = dw._filter_objection_paragraph(table)
    assert kept is None and (kc, rc) == (0, 1) and "vague worry" in rejected


def test_filter_objection_paragraph_separator_row_is_never_counted_as_a_data_row():
    table = "| Objection | Ref | Test |\n|---|---|---|\n| x | F1 | run it |\n"
    _, _, kc, rc = dw._filter_objection_paragraph(table)
    assert kc + rc == 1


# Guard over-match (scar family #3): "test" as a whole word in the header names the column;
# the same four letters embedded in a different word does not.
@pytest.mark.parametrize("header_word", ["Test", "TEST", "Test that would settle it", "Tests"])
def test_filter_objection_paragraph_recognises_test_as_a_whole_word_in_the_header(header_word):
    table = f"| Objection | Ref | {header_word} |\n|---|---|---|\n| x | F1 | run it |\n"
    kept, rejected, kc, rc = dw._filter_objection_paragraph(table)
    assert kept is not None and (kc, rc) == (1, 0)


@pytest.mark.parametrize("header_word", ["Latest status", "Contested by", "Attestation"])
def test_filter_objection_paragraph_does_not_take_a_test_substring_as_the_test_column(header_word):
    """Innocence twin: none of these header cells is the word 'test', so the table has no test
    column — the whole paragraph falls to the prose path and is rejected as ONE unit, not
    exploded per row (there is no `Test:` line anywhere in a bare table paragraph)."""
    table = f"| Objection | Ref | {header_word} |\n|---|---|---|\n| x | F1 | run it |\n"
    kept, rejected, kc, rc = dw._filter_objection_paragraph(table)
    assert kept is None and (kc, rc) == (0, 1) and rejected == table


# --------------------------------------------------------------- judge (guilt + innocence)

def test_judge_passes_a_clean_canned_answer(tmp_path, template, clean_objective):
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    sha = (kit / "brief.sha").read_text().strip()
    _seed_answered(kit, "kimi-k3", dw._CANNED_VALID.format(seat="kimi-k3", sha=sha))
    verdicts = dw.cmd_judge(argparse.Namespace(kit=str(kit)))
    assert verdicts["kimi-k3"] == {"c1": True, "c5": True, "c8": True, "disqualified": False}
    assert (kit / "judge.md").exists()


def test_judge_disqualifies_a_c1_banned_entity(tmp_path, template, clean_objective):
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    sha = (kit / "brief.sha").read_text().strip()
    dirty = dw._CANNED_VALID.format(seat="qwen3.8-max", sha=sha).replace(
        "1 call per seat", "1 call per seat, leaked key=ANTHROPIC_API_KEY")
    _seed_answered(kit, "qwen3.8-max", dirty)
    verdicts = dw.cmd_judge(argparse.Namespace(kit=str(kit)))
    assert verdicts["qwen3.8-max"]["c1"] is False
    assert verdicts["qwen3.8-max"]["disqualified"] is True


def test_judge_disqualifies_a_missing_gate_row(tmp_path, template, clean_objective):
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    sha = (kit / "brief.sha").read_text().strip()
    no_gate = dw._CANNED_VALID.format(seat="kimi-k3", sha=sha).replace(
        "| gate | opus-5-5 | window | serial | 1 | sign | done |\n", "")
    _seed_answered(kit, "kimi-k3", no_gate)
    verdicts = dw.cmd_judge(argparse.Namespace(kit=str(kit)))
    assert verdicts["kimi-k3"]["c5"] is False
    assert verdicts["kimi-k3"]["disqualified"] is True


def test_judge_disqualifies_a_never_bullet_with_no_fc_ref(tmp_path, template, clean_objective):
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    sha = (kit / "brief.sha").read_text().strip()
    no_ref = dw._CANNED_VALID.format(seat="kimi-k3", sha=sha).replace(
        "- No paid Anthropic per-token endpoint (C1)", "- No paid Anthropic per-token endpoint")
    _seed_answered(kit, "kimi-k3", no_ref)
    verdicts = dw.cmd_judge(argparse.Namespace(kit=str(kit)))
    assert verdicts["kimi-k3"]["c8"] is False
    assert verdicts["kimi-k3"]["disqualified"] is True


# --------------------------------------------------------------- judge C5: entity, not spelling, and
# the LAST gate row decides (owner ruling 2026-09-20). First real run, 2026-09-19: 3 of 3 real
# coaches were disqualified by C5 for form, not substance — a coach's own wording of the same
# seat/mode, or a pre-gate row listed before the real final gate, is not a defect.

def _tactics_body(*rows: str) -> str:
    header = ("| stage | seat(s) | in-script or window | parallel/serial | round cap | "
              "exit command | hands to next stage |")
    return "## Tactics\n" + header + "\n" + "|---|---|---|---|---|---|---|\n" + "\n".join(rows) + "\n"


@pytest.mark.parametrize("seat", ["opus-5-5", "Opus 5.5", "opus 5.5", "opus-5.5", "fresh opus-5-5 xhigh",
                                    "`opus-5-5`", "claude-opus-5-5", "opus-5-5-xhigh"])
def test_check_c5_accepts_an_opus_5_entity_spelled_loosely(seat):
    body = _tactics_body(f"| gate | {seat} | window | serial | 1 | sign | done |")
    assert dw._check_c5(body) == (True, "gate row ok")


@pytest.mark.parametrize(
    "seat", ["opus-4-8", "opus-5", "Opus 5", "claude-opus-5", "opus-5-50", "opus-5.55",
             "opus-5.5.1", "opus-5-5-1", "sonnet-5", "claude-opus-4-8", "", "opus-5-1",
             "claude-opus-5-1"])
def test_check_c5_still_rejects_a_seat_that_only_resembles_opus_5(seat):
    body = _tactics_body(f"| gate | {seat} | window | serial | 1 | sign | done |")
    assert dw._check_c5(body)[0] is False


@pytest.mark.parametrize("mode", ["window", "Window", "window (on-disk gate)", "windows",
                                    "two windows, post-reset"])
def test_check_c5_accepts_a_window_mode_spelled_loosely(mode):
    body = _tactics_body(f"| gate | opus-5-5 | {mode} | serial | 1 | sign | done |")
    assert dw._check_c5(body) == (True, "gate row ok")


@pytest.mark.parametrize("mode", ["windowless", "windowed", "batch", ""])
def test_check_c5_still_rejects_a_mode_that_only_resembles_window(mode):
    body = _tactics_body(f"| gate | opus-5-5 | {mode} | serial | 1 | sign | done |")
    assert dw._check_c5(body)[0] is False


def test_check_c5_lets_a_wrong_pre_gate_row_be_overruled_by_a_correct_final_gate_row():
    body = _tactics_body("| pre-gate | sonnet-5 | in-script | serial | 1 | check | gate |",
                          "| gate | opus-5-5 | window | serial | 1 | sign | done |")
    assert dw._check_c5(body) == (True, "gate row ok")


def test_check_c5_still_rejects_a_wrong_final_gate_row_even_with_a_fine_pre_gate_row():
    body = _tactics_body("| pre-gate | opus-5-5 | window | serial | 1 | check | gate |",
                          "| gate | sonnet-5 | in-script | serial | 1 | sign | done |")
    assert dw._check_c5(body)[0] is False


# ------------------------------------------------------------ judge C5: gate stage is a WORD,
# not a substring (owner ruling 2026-09-20, scar family #3: guard-over-match). "gate" as a bare
# substring also matches "aggregate"/"delegate"/"investigate"/"mitigate", and biting on the LAST
# matching Tactics row means a coach's post-gate stage named "aggregate results" would silently
# outrank the real gate row.

@pytest.mark.parametrize("stage", ["gate", "Final Gate", "on-disk gate", "pre-gate", "Gate 2"])
def test_check_c5_recognises_a_gate_stage_spelled_loosely(stage):
    body = _tactics_body(f"| {stage} | opus-5-5 | window | serial | 1 | sign | done |")
    assert dw._check_c5(body) == (True, "gate row ok")


@pytest.mark.parametrize(
    "stage", ["aggregate results", "delegate to r2", "investigate", "mitigate risk",
              "gatekeeper review"])
def test_check_c5_does_not_treat_a_gate_substring_as_a_gate_stage(stage):
    body = _tactics_body(f"| {stage} | opus-5-5 | window | serial | 1 | sign | done |")
    assert dw._check_c5(body) == (False, "no gate row in Tactics")


def test_check_c5_is_not_fooled_by_a_later_row_whose_stage_only_contains_gate_as_a_substring():
    body = _tactics_body(
        "| Final Gate | opus-5-5 | window | serial | 1 | sign | done |",
        "| aggregate results | sonnet-5 | in-script | serial | 1 | collate | done |")
    assert dw._check_c5(body) == (True, "gate row ok")


# --------------------------------------------------------------- judge C1: Never-bullet citation
# is not a use (owner ruling 2026-09-20). The brief's own C1 text invites a coach to NAME a
# banned entity while forbidding it ("Never route through Bedrock or Vertex (C1)") — the parent
# code disqualified exactly that citation. A match anywhere else still disqualifies, even when
# the same string also appears, correctly, inside a Never bullet.

def test_check_c1_ignores_a_banned_entity_named_only_inside_a_never_bullet():
    body = "## Never\n- Never route through Bedrock or Vertex (C1)\n"
    full_text = "---\nseat: x\n---\n" + body
    assert dw._check_c1(full_text, body) == (True, "clean")


def test_check_c1_still_disqualifies_a_banned_entity_outside_the_never_section():
    body = "## Tactics\nWe considered Vertex for stage 2.\n## Never\n- No paid Anthropic per-token endpoint (C1)\n"
    full_text = "---\nseat: x\n---\n" + body
    ok, msg = dw._check_c1(full_text, body)
    assert ok is False
    assert "Vertex" in msg


def test_check_c1_disqualifies_the_same_banned_string_appearing_both_inside_and_outside_never():
    body = ("## Tactics\nDo not use Bedrock anywhere.\n"
            "## Never\n- Never route through Bedrock (C1)\n")
    full_text = "---\nseat: x\n---\n" + body
    assert dw._check_c1(full_text, body)[0] is False


def test_check_c1_disqualifies_a_bullet_byte_identical_to_a_never_bullet_but_living_outside_it():
    """Forgiveness is by POSITION, not by line text — a bullet under `## First move` that
    happens to read exactly like the `## Never` bullet is a USE (it names the entity outside the
    section that exempts naming it), and must not be forgiven just because the two lines match."""
    body = ("## Never\n- Never route through Bedrock (C1)\n"
            "## First move\n- Never route through Bedrock (C1)\n")
    full_text = "---\nseat: x\n---\n" + body
    assert dw._check_c1(full_text, body)[0] is False


def test_check_c1_disqualifies_a_banned_entity_in_the_frontmatter_even_when_never_cites_it_too():
    """The frontmatter is never a `## Never` bullet — it has no headings at all — so a match
    there always disqualifies, regardless of whether the same entity is also correctly cited
    under `## Never` further down."""
    body = "## Never\n- Never route through Bedrock (C1)\n"
    full_text = "---\nseat: x\nfacts_cited: mentions Bedrock in scope\n---\n" + body
    ok, msg = dw._check_c1(full_text, body)
    assert ok is False
    assert "Bedrock" in msg


# --------------------------------------------------------------- judge vs the markdown separator row
# First real r1 run, 2026-09-19: 3 of 3 real coaches wrote a standard markdown table with a
# separator line after the header. _md_table_rows read that line as a data row (['---', ...])
# and C8 disqualified every one of them for a non-integer round cap.

_FORMATION_HEADER = "| role | seat | why (F ref) | substitute if dead (F8) |"
_TACTICS_HEADER = ("| stage | seat(s) | in-script or window | parallel/serial | round cap | "
                    "exit command | hands to next stage |")

SEPARATOR_VARIANTS = [
    ("plain dashes", "|---|---|---|---|", "|---|---|---|---|---|---|---|"),
    ("colons and spaces", "| :--- | :---: | ---: | :--- |",
     "| :--- | :---: | ---: | :--- | :---: | ---: | :--- |"),
]


def _with_separators(text: str, formation_sep: str, tactics_sep: str) -> str:
    text2 = text.replace(_FORMATION_HEADER, _FORMATION_HEADER + "\n" + formation_sep, 1)
    assert text2 != text  # replacement must actually have happened
    text3 = text2.replace(_TACTICS_HEADER, _TACTICS_HEADER + "\n" + tactics_sep, 1)
    assert text3 != text2
    return text3


@pytest.mark.parametrize("style_name,formation_sep,tactics_sep", SEPARATOR_VARIANTS,
                          ids=[v[0] for v in SEPARATOR_VARIANTS])
def test_judge_does_not_read_a_markdown_separator_row_as_data(
        tmp_path, template, clean_objective, style_name, formation_sep, tactics_sep):
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    sha = (kit / "brief.sha").read_text().strip()
    text = _with_separators(dw._CANNED_VALID.format(seat="kimi-k3", sha=sha), formation_sep, tactics_sep)
    _seed_answered(kit, "kimi-k3", text)
    verdicts = dw.cmd_judge(argparse.Namespace(kit=str(kit)))
    assert verdicts["kimi-k3"] == {"c1": True, "c5": True, "c8": True, "disqualified": False}


def test_judge_still_disqualifies_a_prose_round_cap_beside_a_separator_row(tmp_path, template,
                                                                             clean_objective):
    """Innocence twin of the test above: guards against the cure becoming 'skip any row that
    fails' instead of 'skip only the separator row'. A separator row next to a genuinely broken
    round cap must still disqualify on C8 — must pass both before and after the fix."""
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    sha = (kit / "brief.sha").read_text().strip()
    text = _with_separators(dw._CANNED_VALID.format(seat="kimi-k3", sha=sha),
                             "|---|---|---|---|", "|---|---|---|---|---|---|---|")
    broken = text.replace("| serial | 1 | validate |", "| serial | one round | validate |")
    assert broken != text
    _seed_answered(kit, "kimi-k3", broken)
    verdicts = dw.cmd_judge(argparse.Namespace(kit=str(kit)))
    assert verdicts["kimi-k3"]["c8"] is False
    assert verdicts["kimi-k3"]["disqualified"] is True


IS_SEPARATOR_CASES = [
    ("|---|---|", True),
    ("| --- | :---: | ---: |", True),
    ("| r1 | --- | x |", False),
    ("| -- | -- |", False),
    ("| role | seat |", False),
    ("||", False),
    ("|", False),
]


@pytest.mark.parametrize("line,expected", IS_SEPARATOR_CASES, ids=[repr(c[0]) for c in IS_SEPARATOR_CASES])
def test_is_md_separator_row_judges_the_whole_row_not_a_substring(line, expected):
    assert dw._is_md_separator_row(line) is expected


# --------------------------------------------------------------- r1 convener mtime (guilt + innocence)
# REWORK-BUILD gate verdict on 8ffb9bc278/PR1b: the convener's mtime was recorded into the
# ledger but never compared against anything, so "the convener answers first" was theatre.

def test_r1_proceeds_when_convener_mtime_precedes_the_first_dispatch(tmp_path, template, clean_objective):
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="kimi-k3", astra_fallback=False))
    assert (kit / "r1" / "kimi-k3.md").exists()


def test_r1_refuses_a_convener_rewritten_after_the_first_dispatch(tmp_path, template, clean_objective):
    import time

    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="kimi-k3", astra_fallback=False))
    time.sleep(1.1)  # cross a whole-second boundary — the ledger's "when" has second precision
    _seed_convener(kit)  # touch/rewrite the convener file AFTER kimi-k3 was already dispatched
    with pytest.raises(SystemExit) as e:
        dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="qwen3.8-max", astra_fallback=False))
    assert e.value.code == 2
    assert not (kit / "r1" / "qwen3.8-max.md").exists()
    assert not dw._ledger_has_seat(kit, "qwen3.8-max")


# --------------------------------------------------------------- r2 family (guilt + innocence)
# REWORK-BUILD gate verdict on 4c062d2e09/PR2a: an `answered` seat absent from FAMILY_MAP has
# _seat_family return None, and None was treated as a family — pairing a seat with its own
# vendor whenever both were unrecognised, or pairing a known seat with an unrecognised one.

def test_r2_refuses_a_seat_absent_from_family_map(tmp_path, template, clean_objective):
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="kimi-k3,totally-unknown-seat",
                                  astra_fallback=False))
    with pytest.raises(SystemExit) as e:
        dw.cmd_r2(argparse.Namespace(kit=str(kit)))
    assert e.value.code == 2
    assert not (kit / "pairing.md").exists()


@pytest.mark.parametrize("alias,family", [
    ("kimi-2.7", "moonshot"),
    ("kimi-code/k3", "moonshot"),
])
def test_seat_family_resolves_the_mandate_aliases(alias, family):
    assert dw._seat_family(alias) == family


# --------------------------------------------------------------- file-safe slug (guilt + innocence)
# Gate finding 2 on PR2b's merge: a slash-bearing seat id (the mandate itself spells some seats
# that way, e.g. "kimi-code/k3") crashed r1 with an uncaught FileNotFoundError on r1/kimi-code/k3.md
# AFTER a "sent" row had already been appended. Fixed by routing every seat-to-path build through
# _seat_key(), and by validating the seat id BEFORE the first ledger_append.

def test_r1_seat_id_with_a_slash_writes_under_a_file_safe_slug(tmp_path, template, clean_objective):
    """"kimi-code/k3" is ALSO a _SEAT_ALIASES key (-> "kimi-k3"), so post-PR2g' S1 its slug is
    its alias TARGET's slug (_seat_key consolidation), not a literal slash-collapse of its own
    spelling — the old raw-_file_slug expectation ("kimi-code__k3.md") is exactly the stale
    write-path this fix retires; "kimi-k3.md" is what _seat_key("kimi-code/k3") now computes,
    matching what _claim_slug has claimed since PR2g item 3."""
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="kimi-code/k3", astra_fallback=False))
    assert (kit / "r1" / "kimi-k3.md").exists()
    assert not (kit / "r1" / "kimi-code__k3.md").exists()  # the pre-S1 raw-slug path, retired
    assert not (kit / "r1" / "kimi-code").exists()
    assert dw._ledger_has_seat(kit, "kimi-code/k3")  # ledger keeps the RAW seat id, not the slug


@pytest.mark.parametrize("bad_seat", ["../x", "a//b", "x/..", "/leading", "trailing/"])
def test_r1_refuses_a_seat_id_with_a_path_traversal_or_empty_component(tmp_path, template,
                                                                        clean_objective, bad_seat):
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    with pytest.raises(SystemExit) as e:
        dw.cmd_r1(argparse.Namespace(kit=str(kit), seats=bad_seat, astra_fallback=False))
    assert e.value.code == 2
    assert not dw._ledger_has_seat(kit, bad_seat)


@pytest.mark.parametrize("bad_seat", ["", ".", "..", "a/../b"])
def test_validate_seat_id_refuses_empty_or_dot_components(bad_seat):
    with pytest.raises(SystemExit) as e:
        dw._validate_seat_id(bad_seat)
    assert e.value.code == 2


# --------------------------------------------------------------- kimi model id (guilt + innocence)
# Gate-4 finding, PR2e addendum (scripts/dynamic_workflow.py:382): every kimi* seat launched
# with the same hardcoded '-m kimi-code/k3', so the kimi-2.7 alias would really be answered by
# K3. KIMI_MODEL_MAP is now the single source for the '-m' id, read by both _launch_seat and
# _validate_kimi_model (the latter refuses BEFORE any ledger row, from _run_one_seat).

def test_validate_kimi_model_accepts_both_real_kimi_seats_and_the_alias():
    assert dw._validate_kimi_model("kimi-k3") is None  # returns cleanly, no SystemExit
    assert dw._validate_kimi_model("kimi-code/kimi-for-coding-highspeed") is None
    assert dw._validate_kimi_model("kimi-2.7") is None  # alias, canonicalises to the highspeed seat


def test_validate_kimi_model_is_a_noop_for_a_non_kimi_seat():
    # _seat_kind != "kimi" — nothing to check, returns cleanly rather than raising
    assert dw._validate_kimi_model("qwen3.8-max") is None


def test_validate_kimi_model_refuses_an_unresolvable_kimi_seat():
    with pytest.raises(SystemExit) as e:
        dw._validate_kimi_model("kimi-nonexistent-model")
    assert e.value.code == 2


def test_r1_refuses_an_unresolvable_kimi_model_id_before_ledger_append(tmp_path, template,
                                                                        clean_objective):
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    bad_seat = "kimi-nonexistent-model"
    with pytest.raises(SystemExit) as e:
        dw.cmd_r1(argparse.Namespace(kit=str(kit), seats=bad_seat, astra_fallback=False))
    assert e.value.code == 2
    assert not dw._ledger_has_seat(kit, bad_seat)


def test_guilt_r2_validates_kimi_model_before_launch(tmp_path, monkeypatch):
    """Item 4 (PR2g, gate-7 obs :390/:732): _launch_seat's kimi branch reads
    KIMI_MODEL_MAP[_canonical_seat(seat)] inside a bare `except Exception: return ""` — an
    unresolvable kimi* id used to degrade cmd_r2 to an EMPTY objection file (exit 0) instead
    of a fail-closed refusal. compute_pairing can never hand cmd_r2 an unvalidated kimi seat
    via the normal r1->r2 pipeline (r1 already refuses one before it can answer and be
    paired), so this monkeypatches compute_pairing directly to exercise cmd_r2's OWN call
    site — defense in depth, not a reachable end-to-end bug today. DW_FAKE_SEATS=1 is
    autouse for this whole file, which is exactly why the validation must run BEFORE the
    fake-output branch (mirrors _run_one_seat's own ordering): otherwise no test in fake mode
    could ever prove this call site refuses at all."""
    kit = tmp_path / "k"
    kit.mkdir()
    (kit / "brief.sha").write_text("deadbeef" * 8)
    monkeypatch.setattr(
        dw, "compute_pairing",
        lambda kit, sha: {"kimi-nonexistent-model": ["qwen3.8-max", "gemini-3.1-pro-high"]},
    )
    with pytest.raises(SystemExit) as e:
        dw.cmd_r2(argparse.Namespace(kit=str(kit)))
    assert e.value.code == 2
    assert not any((kit / "r2").glob("*"))


def test_guilt_jury_validates_kimi_model_before_launch(tmp_path, monkeypatch):
    """Item 4 (PR2g, gate-7 obs :390/:994): cmd_jury's launch call site had the same gap as
    cmd_r2's — an unresolvable kimi* juror degraded to an empty ballot (jury-dead, exit 0)
    instead of refusing. judge.md/_jury_survivors already gate real disqualification
    upstream, so this monkeypatches _jury_survivors/_jury_mapping directly to exercise
    cmd_jury's OWN call site, same defense-in-depth rationale as the r2 test above."""
    kit = tmp_path / "k"
    kit.mkdir()
    monkeypatch.setattr(dw, "_jury_survivors",
                         lambda kit: ["kimi-nonexistent-model", "qwen3.8-max"])
    monkeypatch.setattr(
        dw, "_jury_mapping",
        lambda kit, survivors: {"A": "kimi-nonexistent-model", "B": "qwen3.8-max"},
    )
    with pytest.raises(SystemExit) as e:
        dw.cmd_jury(argparse.Namespace(kit=str(kit)))
    assert e.value.code == 2
    assert not (kit / "jury" / f"{dw._seat_key('kimi-nonexistent-model')}.md").exists()


def test_launch_seat_kimi_uses_the_per_seat_model_id(tmp_path, monkeypatch):
    """Launcher-intercept per the addendum: proves the '-m' argument _launch_seat actually
    threads to subprocess.run is per-seat, not the old hardcoded 'kimi-code/k3' for every
    kimi* seat. DW_FAKE_SEATS never reaches _launch_seat (see _run_one_seat), so this calls
    it directly, same pattern as test_launch_seat_astra_resolves_a_seat_before_invoking_codex."""
    kit = tmp_path / "k"
    calls = []

    class _FakeResult:
        stdout = "stub output"

    def _fake_run(cmd, **kwargs):
        calls.append(cmd)
        return _FakeResult()

    monkeypatch.setattr(dw.subprocess, "run", _fake_run)

    dw._launch_seat("kimi-k3", "prompt text", 5, kit)
    dw._launch_seat("kimi-code/kimi-for-coding-highspeed", "prompt text", 5, kit)

    assert len(calls) == 2
    assert calls[0][calls[0].index("-m") + 1] == "kimi-code/k3"
    assert calls[1][calls[1].index("-m") + 1] == "kimi-code/kimi-for-coding-highspeed"


def test_launch_seat_kimi_2_7_alias_resolves_to_the_highspeed_id_end_to_end(tmp_path, monkeypatch):
    """The addendum's other half: 'kimi-2.7 resolves to the highspeed id end to end (r1 launch
    args, not _seat_family)' — calls _launch_seat with the ALIAS spelling itself, proving
    _canonical_seat is consulted at dispatch time, not just by the family lookup."""
    kit = tmp_path / "k"
    calls = []

    class _FakeResult:
        stdout = "stub output"

    def _fake_run(cmd, **kwargs):
        calls.append(cmd)
        return _FakeResult()

    monkeypatch.setattr(dw.subprocess, "run", _fake_run)

    dw._launch_seat("kimi-2.7", "prompt text", 5, kit)

    assert len(calls) == 1
    assert calls[0][calls[0].index("-m") + 1] == "kimi-code/kimi-for-coding-highspeed"


def test_every_stage_prefix_carries_the_sealed_sentence():
    """PR3k, first real run (2026-09-19): the kimi seat, mid-r2, read the launcher's own
    source instead of answering blind — only r1's prefix told a seat not to. This pins the
    shared constant into all three stage prefixes, and pins _PROMPT_PREFIX's exact
    pre-existing bytes so the refactor that introduced the constant cannot also have
    changed the r1 prompt (its hash goes into a ledger)."""
    assert dw._SEALED_SENTENCE == "No tools, no browsing, no file reads."
    assert dw._SEALED_SENTENCE in dw._PROMPT_PREFIX
    assert dw._SEALED_SENTENCE in dw._R2_PROMPT_PREFIX
    assert dw._SEALED_SENTENCE in dw._JURY_PROMPT_PREFIX
    assert dw._PROMPT_PREFIX == (
        "You are a coach in a sealed brainstorm. Use ONLY the brief below and the "
        "exact skeleton in §4. No tools, no browsing, no file reads. Output "
        "only the answer.\n\n")


@pytest.mark.parametrize("seat", ["kimi-k3", "gemini-3.1-pro-high", "qwen3.8-max"])
def test_launch_seat_runs_every_cli_seat_from_an_empty_dir_outside_the_repo(
        tmp_path, monkeypatch, seat):
    """PR3k, GUILT (first real run 2026-09-19): the kimi seat, launched with no cwd=, inherited
    the caller's cwd (the repo worktree) and used its tools to read dynamic_workflow.py during
    r2 instead of answering blind — verified by real launches that kimi and agy both answer
    correctly from an empty temp dir (the qwen/tp1 kind could not be smoke-tested that week,
    its quota was exhausted). One param per non-astra kind (kimi, agy, tp1)."""
    kit = tmp_path / "k"
    seen: dict = {}

    def _fake_run(_cmd, **kwargs):
        cwd = kwargs.get("cwd")
        seen["cwd"] = cwd
        seen["existed_during_call"] = cwd is not None and os.path.isdir(cwd)
        seen["was_empty_during_call"] = cwd is not None and os.listdir(cwd) == []
        return argparse.Namespace(stdout="ok")

    monkeypatch.setattr(dw.subprocess, "run", _fake_run)

    output = dw._launch_seat(seat, "prompt text", 5, kit)

    assert output == "ok"
    assert seen["cwd"] is not None
    assert seen["existed_during_call"]
    assert seen["was_empty_during_call"]
    launch_dir = Path(seen["cwd"]).resolve()
    assert launch_dir != dw.REPO_ROOT
    assert dw.REPO_ROOT not in launch_dir.parents
    assert not launch_dir.exists()  # cleaned up once _launch_seat returns


def test_launch_seat_still_returns_empty_when_the_cli_raises(tmp_path, monkeypatch):
    """Innocence twin: the new `with tempfile.TemporaryDirectory()` block must not break the
    existing degrade-to-empty-string path when the CLI itself times out."""
    kit = tmp_path / "k"

    def _fake_run(_cmd, **_kwargs):
        raise dw.subprocess.TimeoutExpired(cmd="x", timeout=1)

    monkeypatch.setattr(dw.subprocess, "run", _fake_run)

    assert dw._launch_seat("kimi-k3", "prompt text", 5, kit) == ""


# --------------------------------------------------------------- slug collision (guilt + innocence)
# Gate-4 finding, PR2e addendum (scripts/dynamic_workflow.py:420): _file_slug collapses '/' to
# '__', so 'vendor/x' and a literal 'vendor__x' seat id both produce r1/vendor__x.md — the
# second claimant used to overwrite the first silently (exit 0, no error). kit/slugs.json now
# refuses a second, DIFFERENT claimant before dispatch.

def test_r1_refuses_a_slug_collision_between_two_different_seat_ids(tmp_path, template,
                                                                     clean_objective):
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="vendor/x", astra_fallback=False))
    first_answer = (kit / "r1" / "vendor__x.md").read_text()
    with pytest.raises(SystemExit) as e:
        dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="vendor__x", astra_fallback=False))
    assert e.value.code == 2
    assert not dw._ledger_has_seat(kit, "vendor__x")  # the SECOND seat id, never dispatched
    assert dw._ledger_has_seat(kit, "vendor/x")  # the FIRST seat id, untouched by the refusal
    assert (kit / "r1" / "vendor__x.md").read_text() == first_answer  # first claimant's file intact


def test_r1_relaunching_the_same_seat_across_two_cmd_r1_calls_is_not_a_slug_collision(
        tmp_path, template, clean_objective):
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="kimi-k3", astra_fallback=False))
    assert dw.ledger_sent_count(kit, "kimi-k3") == 1
    summary2 = dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="kimi-k3", astra_fallback=False))
    assert summary2["kimi-k3"] == "answered"  # the SAME seat re-claims its own slug, no refusal
    assert dw.ledger_sent_count(kit, "kimi-k3") == 2


def test_r1_refuses_a_slug_collision_between_the_kimi_2_7_alias_and_its_canonical_spelling(
        tmp_path, template, clean_objective):
    """Item 3 (PR2g, gate-7 obs :442) + PR2g' S1/S3 Guilt (gate-13 obs 2 on PR2g #6790): the
    slug used to be claimed on the RAW seat id, so 'kimi-2.7' and its canonical spelling
    'kimi-code/kimi-for-coding-highspeed' claimed TWO different slugs for the ONE model
    KIMI_MODEL_MAP resolves both to — the same seat could answer twice and count twice in
    family diversity. Claiming on _canonical_seat(seat) makes the second claim collide,
    mirrors test_r1_refuses_a_slug_collision_between_two_different_seat_ids exactly, just
    with an alias pair instead of a literal '__' collision.

    Strengthened for S1: gate-13 found _claim_slug already claimed the CANONICAL key (PR2g)
    while _run_one_seat still wrote to the RAW, uncanonicalized _file_slug(seat) path — so
    the winning seat's claim key and its actual r1 filename could name two different strings
    even though nothing here ever raised. Post-_seat_key-consolidation they are the same
    computation, so the winner's r1 path now provably equals its own claim key."""
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="kimi-2.7", astra_fallback=False))
    with pytest.raises(SystemExit) as e:
        dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="kimi-code/kimi-for-coding-highspeed",
                                      astra_fallback=False))
    assert e.value.code == 2
    assert not dw._ledger_has_seat(kit, "kimi-code/kimi-for-coding-highspeed")
    assert dw._ledger_has_seat(kit, "kimi-2.7")
    slugs = json.loads((kit / "slugs.json").read_text())
    assert len(slugs) == 1  # one slug, not two — the alias and its canonical spelling collided
    assert slugs == {"kimi-code__kimi-for-coding-highspeed": "kimi-2.7"}  # claim key == write stem
    assert (kit / "r1" / "kimi-code__kimi-for-coding-highspeed.md").exists()  # winner's r1 path
    assert dw._seat_key("kimi-2.7") == "kimi-code__kimi-for-coding-highspeed"


def test_r1_an_aliased_seat_and_its_slash_collapse_lookalike_are_innocent_of_each_other(
        tmp_path, template, clean_objective, monkeypatch):
    """PR2g' S3 Innocence — and the concrete regression proof for gate-13 obs 2's "latent
    overwrite hole". The mandate's own literal example pair ('kimi-code/k3' vs 'kimi-code__k3')
    does not actually reach this code path through cmd_r1: the second spelling is kimi-shaped
    but unregistered, so _validate_kimi_model refuses it before _claim_slug ever runs — proving
    nothing about _seat_key (empirically verified; the mandate's own Bites-line correction
    licenses grounding fixes in actual call sites over stale prose). A monkeypatched, non-kimi
    alias reproduces the identical structural hazard without that interference: 'vendor/aliased'
    canonicalizes (via the alias) to 'vendor-canonical'; 'vendor__aliased' is not itself an alias
    key, so it canonicalizes to itself. _claim_slug already claims on the canonical key even
    pre-PR2g' (item 3), so the two seats claimed two DIFFERENT slugs even before this fix
    ('vendor-canonical' vs 'vendor__aliased') — no ledger collision, ever. But pre-fix,
    _run_one_seat wrote to the RAW, uncanonicalized _file_slug(seat): _file_slug('vendor/aliased')
    == _file_slug('vendor__aliased') == 'vendor__aliased' (plain slash-collapse, same string) —
    so the SECOND seat's write silently overwrote the FIRST's r1 file, exit 0, no error, even
    though slugs.json showed two distinct claims. Once every write goes through _seat_key (this
    fix), the write key equals the claim key for both, so two distinct claims now structurally
    guarantee two distinct files."""
    monkeypatch.setitem(dw._SEAT_ALIASES, "vendor/aliased", "vendor-canonical")
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="vendor/aliased", astra_fallback=False))
    dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="vendor__aliased", astra_fallback=False))
    assert dw._ledger_has_seat(kit, "vendor/aliased")
    assert dw._ledger_has_seat(kit, "vendor__aliased")
    assert (kit / "r1" / "vendor-canonical.md").exists()
    assert (kit / "r1" / "vendor__aliased.md").exists()
    slugs = json.loads((kit / "slugs.json").read_text())
    assert slugs == {"vendor-canonical": "vendor/aliased", "vendor__aliased": "vendor__aliased"}


def test_claim_slug_refuses_an_aliased_collision_for_a_non_kimi_seat_pair(tmp_path, monkeypatch):
    """PR2g' S3 Latency: the kimi-2.7 Guilt test above could in principle pass for the WRONG
    reason if some kimi-specific check (_validate_kimi_model, only reachable via cmd_r1 /
    _run_one_seat) were doing the refusing instead of _seat_key's own consolidation. Calling
    _claim_slug directly on a monkeypatched, non-kimi alias pair never goes near
    _validate_kimi_model at all, isolating _claim_slug itself as the true cause of the
    refusal."""
    monkeypatch.setitem(dw._SEAT_ALIASES, "acme/v1", "acme-vendor-canonical")
    kit = tmp_path / "k"
    kit.mkdir()
    dw._claim_slug(kit, "acme-vendor-canonical")
    with pytest.raises(SystemExit) as e:
        dw._claim_slug(kit, "acme/v1")
    assert e.value.code == 2
    slugs = json.loads((kit / "slugs.json").read_text())
    assert slugs == {"acme-vendor-canonical": "acme-vendor-canonical"}


@pytest.mark.parametrize("payload,failure_class", [
    pytest.param(b"\x00\xff\xfe", "UnicodeDecodeError", id="non-utf8-bytes"),
    pytest.param(b"{", "JSONDecodeError", id="truncated-json"),
    pytest.param(b"[]", "shape error", id="json-array-not-object"),
    pytest.param(b'{"a": 1}', "shape error", id="object-with-a-non-string-value"),
    pytest.param(b"not json", "JSONDecodeError", id="not-json-at-all"),
])
def test_guilt_claim_slug_refuses_a_corrupt_or_malshaped_slugs_json_naming_file_and_class(
        tmp_path, capsys, payload, failure_class):
    """PR2g' S4 (gate-13 obs 1 HIGH REWORK trigger): _claim_slug used to read slugs.json via
    Path.read_text(), which raises an UNCAUGHT UnicodeDecodeError on non-UTF8 bytes — a bare
    traceback naming a line number, exit 1, never the file. Reading as bytes and decoding
    explicitly closes that hole. A wrong-shape payload — valid JSON, but not a str -> str
    object (a bare list, or a dict holding a non-string value) — used to pass the old
    `isinstance(slugs, dict)` check and get silently adopted, later breaking an `existing !=
    seat` comparison against a non-string value; it must refuse here too, naming which of the
    three failure classes (UnicodeDecodeError / JSONDecodeError / shape error) fired. Every
    payload: exit 2, the file byte-for-byte UNCHANGED (this function is the ONLY writer and
    every one of these paths exits before its own write step), message names the file AND
    the failure class."""
    kit = tmp_path / "k"
    kit.mkdir()
    (kit / "slugs.json").write_bytes(payload)
    with pytest.raises(SystemExit) as e:
        dw._claim_slug(kit, "kimi-k3")
    assert e.value.code == 2
    err = capsys.readouterr().err
    assert str(kit / "slugs.json") in err
    assert failure_class in err
    assert (kit / "slugs.json").read_bytes() == payload  # byte-for-byte unchanged


def test_claim_slug_holds_up_under_concurrent_claimants_no_lost_updates(tmp_path):
    """Item 2 (PR2g, gate-7 obs: 14 concurrent r1 on one kit, distinct seats, wrote 14
    r1/*.md files but only 12 slugs.json entries — a plain read-modify-write lost updates).
    Serialized in-process equivalent of the N-process scenario (mandate's own permitted
    alternative): fcntl.flock locks are held per OPEN FILE DESCRIPTION, so N threads each
    opening the sidecar .lock genuinely serialize at the OS level, not just cooperatively —
    this is real contention, not an artifact of the GIL. Without the lock, N threads racing
    the old read-modify-write would lose some fraction of these N distinct-seat claims;
    with it, all N land."""
    kit = tmp_path / "k"
    kit.mkdir()
    seats = [f"vendor/seat-{i}" for i in range(20)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(seats)) as pool:
        list(pool.map(lambda s: dw._claim_slug(kit, s), seats))
    slugs = json.loads((kit / "slugs.json").read_text())
    assert len(slugs) == len(seats)
    assert set(slugs.values()) == set(seats)


# --------------------------------------------------------------- empty --seats (guilt + innocence)
# Gate-4 finding, PR2e addendum (scripts/dynamic_workflow.py:497): "" or whitespace-only
# --seats filtered down to an empty list and cmd_r1 returned an empty summary — exit 0,
# nothing dispatched, no error at all.

@pytest.mark.parametrize("bad_seats", ["", "   ", ",,,", " , "])
def test_r1_refuses_empty_or_whitespace_only_seats_before_touching_the_kit(tmp_path, bad_seats):
    kit = tmp_path / "nonexistent-kit"  # no cmd_brief, no convener — proves fail-fast
    with pytest.raises(SystemExit) as e:
        dw.cmd_r1(argparse.Namespace(kit=str(kit), seats=bad_seats, astra_fallback=False))
    assert e.value.code == 2


def test_r1_accepts_a_normal_non_empty_seats_string(tmp_path, template, clean_objective):
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    summary = dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="kimi-k3", astra_fallback=False))
    assert "kimi-k3" in summary


# --------------------------------------------------------------- r2 pairing "exactly two" (guilt + innocence)
# Gate finding 3, inherited from PR2a's merge: compute_pairing silently accepted 0 or 1
# cross-family partner as "good enough"; the mandate requires EXACTLY two.

def test_r2_refuses_when_a_seat_cannot_get_two_cross_family_partners(tmp_path, template, clean_objective):
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    dw.cmd_r1(argparse.Namespace(
        kit=str(kit),
        seats="kimi-k3,kimi-code/kimi-for-coding-highspeed,qwen3.8-max",
        astra_fallback=False))
    with pytest.raises(SystemExit) as e:
        dw.cmd_r2(argparse.Namespace(kit=str(kit)))
    assert e.value.code == 2
    assert not (kit / "pairing.md").exists()


def test_r2_pairs_every_seat_with_exactly_two_partners_across_four_families(tmp_path, template,
                                                                             clean_objective):
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    dw.cmd_r1(argparse.Namespace(
        kit=str(kit),
        seats="kimi-k3,qwen3.8-max,gemini-3.1-pro-high,deepseek-v4-pro",
        astra_fallback=False))
    dw.cmd_r2(argparse.Namespace(kit=str(kit)))
    pairing = dw.compute_pairing(kit, (kit / "brief.sha").read_text().strip())
    assert all(len(targets) == 2 for targets in pairing.values())


def test_r2_pairing_md_resolves_the_kimi_2_7_alias_to_moonshot_for_diversity(tmp_path, template,
                                                                              clean_objective):
    # Gate finding 5: kimi-2.7 is an ALIAS for a moonshot seat (see _SEAT_ALIASES); the unit
    # test above (test_seat_family_resolves_the_mandate_aliases) proves _seat_family resolves
    # it in isolation, but this proves the resolution actually reaches compute_pairing/pairing.md
    # end-to-end through cmd_r1 -> cmd_r2, not just the lookup function on its own.
    #
    # PR2e gate-4 addendum: the ORIGINAL seat list here had only ONE moonshot-family seat
    # (kimi-2.7 itself), so a broken alias resolution had no second moonshot seat to wrongly
    # pair it with, and only the in-memory compute_pairing() dict was ever checked, never the
    # WRITTEN pairing.md text cmd_r2 actually produces. With EXACTLY these four seats (kimi-2.7,
    # kimi-k3 = 2 moonshot; gemini-3.1-pro-high = 1 google; qwen3.8-max = 1 alibaba), both
    # kimi-2.7's and kimi-k3's candidate pool is FORCED to exactly {gemini, qwen} — no RNG
    # ambiguity in which two partners get picked, so a mis-resolved alias is guaranteed to be
    # visible here, not just possible.
    #
    # Verified by local mutation (not committed, see PR body): pointing
    # _SEAT_ALIASES["kimi-2.7"] at "gemini-3.1-pro-high" makes _seat_kind("kimi-2.7") still
    # report "kimi" (a raw-string check, unaffected by the alias), so _validate_kimi_model
    # refuses the mutated alias exit 2 from inside cmd_r1 itself, before cmd_r2/pairing.md is
    # ever reached — the earliest of this PR's fail-closed gates catches it first. This test
    # and _validate_kimi_model both key off the exact same single alias-resolution point
    # (_SEAT_ALIASES -> _canonical_seat), so there is no way to break one without the other.
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    dw.cmd_r1(argparse.Namespace(
        kit=str(kit),
        seats="kimi-2.7,kimi-k3,gemini-3.1-pro-high,qwen3.8-max",
        astra_fallback=False))
    dw.cmd_r2(argparse.Namespace(kit=str(kit)))
    pairing = dw.compute_pairing(kit, (kit / "brief.sha").read_text().strip())
    assert set(pairing["kimi-2.7"]) == {"gemini-3.1-pro-high", "qwen3.8-max"}
    assert set(pairing["kimi-k3"]) == {"gemini-3.1-pro-high", "qwen3.8-max"}

    pairing_text = (kit / "pairing.md").read_text()
    kimi27_row = next(l for l in pairing_text.splitlines() if l.startswith("| kimi-2.7 |"))
    kimik3_row = next(l for l in pairing_text.splitlines() if l.startswith("| kimi-k3 |"))
    assert "kimi-k3" not in kimi27_row, kimi27_row
    assert "kimi-2.7" not in kimik3_row, kimik3_row


# --------------------------------------------------------------- jury (guilt + innocence)

def _judged_kit(tmp_path, template, clean_objective, seats: str) -> Path:
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    dw.cmd_r1(argparse.Namespace(kit=str(kit), seats=seats, astra_fallback=False))
    dw.cmd_judge(argparse.Namespace(kit=str(kit)))
    return kit


def test_jury_refuses_before_judge_has_run(tmp_path, template, clean_objective):
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="kimi-k3", astra_fallback=False))
    with pytest.raises(SystemExit) as e:
        dw.cmd_jury(argparse.Namespace(kit=str(kit)))
    assert e.value.code == 2
    assert not (kit / "jury").exists()


def _all_disqualified_kit(tmp_path, template, clean_objective) -> Path:
    """judge.md marking every answered seat disqualified — the shape the first real run
    (2026-09-19) produced when judge disqualified 3 of 3 seats: the SAME defect
    (test_judge_disqualifies_a_never_bullet_with_no_fc_ref's own no-C1-ref mutation) applied
    to three different-family seats, so C8 fails for every one of them."""
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    sha = (kit / "brief.sha").read_text().strip()
    for seat in ("kimi-k3", "qwen3.8-max", "gemini-3.1-pro-high"):
        dirty = dw._CANNED_VALID.format(seat=seat, sha=sha).replace(
            "- No paid Anthropic per-token endpoint (C1)", "- No paid Anthropic per-token endpoint")
        _seed_answered(kit, seat, dirty)
    verdicts = dw.cmd_judge(argparse.Namespace(kit=str(kit)))
    assert all(v["disqualified"] for v in verdicts.values())
    return kit


def test_jury_refuses_when_judge_disqualified_every_seat(tmp_path, template, clean_objective,
                                                           capsys):
    """First real run (2026-09-19): judge.md disqualified 3 of 3 seats and cmd_jury still
    exited 0, writing jury/tabulation.md reading '0 live ballot(s), 0 dead: none' — a green
    exit on an empty outcome (scar family #2, 'exists != armed': monitor the OUTCOME, never
    the exit code). cmd_jury must refuse BEFORE _jury_mapping runs, so neither jury/mapping.json
    nor jury/tabulation.md ever gets written."""
    kit = _all_disqualified_kit(tmp_path, template, clean_objective)
    with pytest.raises(SystemExit) as e:
        dw.cmd_jury(argparse.Namespace(kit=str(kit)))
    assert e.value.code == 2
    assert "0 surviving formations" in capsys.readouterr().err
    assert not (kit / "jury" / "mapping.json").exists()
    assert not (kit / "jury" / "tabulation.md").exists()


def test_jury_scores_survivors_and_marks_a_malformed_ballot_dead(tmp_path, template, clean_objective):
    kit = _judged_kit(tmp_path, template, clean_objective,
                       "kimi-k3,qwen3.8-max,gemini-3.1-pro-high-fakejurydead")
    tabulation = dw.cmd_jury(argparse.Namespace(kit=str(kit)))
    mapping_path = kit / "jury" / "mapping.json"
    assert mapping_path.exists()
    assert oct(mapping_path.stat().st_mode)[-3:] == "600"
    assert (kit / "jury" / "tabulation.md").exists()
    assert tabulation["dead"] == ["gemini-3.1-pro-high-fakejurydead"]
    assert set(tabulation["borda"]) == {"A", "B", "C"}
    assert set(tabulation["firsts"]) == {"A", "B", "C"}


def test_jury_dir_names_no_seat_id_in_any_filename_or_content_before_reveal(
        tmp_path, template, clean_objective):
    # guilt (dw-gate-5 on PR2d; broadened PR2h addendum obs 1, gate-9 MEDIUM): the pre-fix
    # rendering embedded mapping[ltr] in the table, the Disagreements line and the header's
    # dead-ballot list; separately, jury/<seat-slug>.md ballot FILENAMES named the juror
    # directly, and the set difference over each ballot's ranked letters reconstructed
    # jury/mapping.json from world-readable files without ever opening it (gate-9 reproduced
    # it exactly). Every file under jury/ except mapping.json (0600, the one sanctioned place)
    # must carry no seat id in EITHER its filename or its content.
    seats = "kimi-k3,qwen3.8-max,gemini-3.1-pro-high-fakejurydead"
    kit = _judged_kit(tmp_path, template, clean_objective, seats)
    dw.cmd_jury(argparse.Namespace(kit=str(kit)))
    for f in (kit / "jury").iterdir():
        if f.name == "mapping.json":
            continue
        for seat in seats.split(","):
            assert seat not in f.name, f"{seat} leaked into filename {f.name}"
            assert seat not in f.read_text(), f"{seat} leaked into {f.name}'s content"


def test_jury_prompt_never_names_an_answered_seat_id(tmp_path, template, clean_objective):
    seats = "kimi-k3,qwen3.8-max,gemini-3.1-pro-high"
    kit = _judged_kit(tmp_path, template, clean_objective, seats)
    survivors = dw._jury_survivors(kit)
    mapping = dw._jury_mapping(kit, survivors)
    for juror in mapping.values():
        others = sorted(ltr for ltr, seat in mapping.items() if seat != juror)
        if not others:
            continue
        prompt = dw._jury_prompt(kit, mapping, others)
        for seat in seats.split(","):
            assert seat not in prompt, f"{seat} leaked into the prompt sent to {juror}"


def test_jury_refuses_when_mapping_json_exists_and_differs(tmp_path, template, clean_objective):
    kit = _judged_kit(tmp_path, template, clean_objective, "kimi-k3,qwen3.8-max")
    (kit / "jury").mkdir(parents=True, exist_ok=True)
    (kit / "jury" / "mapping.json").write_text('{"A": "not-the-real-seat"}\n')
    with pytest.raises(SystemExit) as e:
        dw.cmd_jury(argparse.Namespace(kit=str(kit)))
    assert e.value.code == 2


def test_parse_jury_ballot_rejects_a_partial_table():
    text = "| A | 3 | 3 | 3 | 3 | 3 | 3 |\n"  # missing letter B entirely
    assert dw._parse_jury_ballot(text, {"A", "B"}) is None


def test_parse_jury_ballot_accepts_a_complete_table():
    text = ("| formation | termination | cost | robustness | evidence | implementability | fit |\n"
            "|---|---|---|---|---|---|---|\n"
            "| A | 3 | 3 | 3 | 3 | 3 | 3 |\n"
            "| B | 5 | 1 | 5 | 1 | 5 | 1 |\n")
    ballot = dw._parse_jury_ballot(text, {"A", "B"})
    assert ballot == {"A": [3, 3, 3, 3, 3, 3], "B": [5, 1, 5, 1, 5, 1]}


# --------------------------------------------------------------- anonymise / reveal / capture-check

def _juried_kit(tmp_path, template, clean_objective, seats: str) -> Path:
    kit = _judged_kit(tmp_path, template, clean_objective, seats)
    dw.cmd_jury(argparse.Namespace(kit=str(kit)))
    return kit


_THREE_FAMILY_SEATS = "kimi-k3,qwen3.8-max,gemini-3.1-pro-high"


def test_anonymise_refuses_when_there_is_no_survivor(tmp_path, template, clean_objective,
                                                        capsys):
    """cmd_anonymise obtains its own mapping via _jury_survivors/_jury_mapping independently of
    cmd_jury having run at all, so this exercises a judged-but-never-juried kit directly. Same
    scar family #2 as cmd_jury's twin above: 'Z-BLIND/ written for 0 formation(s): ' was a
    green exit on nothing to anonymise."""
    kit = _all_disqualified_kit(tmp_path, template, clean_objective)
    with pytest.raises(SystemExit) as e:
        dw.cmd_anonymise(argparse.Namespace(kit=str(kit)))
    assert e.value.code == 2
    assert "0 surviving formations" in capsys.readouterr().err
    assert not (kit / "Z-BLIND").exists()


def test_jury_and_anonymise_still_run_with_survivors(tmp_path, template, clean_objective):
    """Innocence twin: a normal judged kit with clean survivors passes through cmd_jury and
    cmd_anonymise exactly as before the empty-outcome refusal was added."""
    kit = _judged_kit(tmp_path, template, clean_objective, _THREE_FAMILY_SEATS)
    dw.cmd_jury(argparse.Namespace(kit=str(kit)))
    mapping = dw.cmd_anonymise(argparse.Namespace(kit=str(kit)))
    assert (kit / "jury" / "tabulation.md").exists()
    assert {p.stem for p in (kit / "Z-BLIND").glob("*.md")} == set(mapping)


def test_anonymise_z_blind_copy_differs_from_the_original_only_on_seat_and_sha_lines(
        tmp_path, template, clean_objective):
    kit = _juried_kit(tmp_path, template, clean_objective, _THREE_FAMILY_SEATS)
    mapping = dw.cmd_anonymise(argparse.Namespace(kit=str(kit)))
    letter, seat = next(iter(mapping.items()))
    original = (kit / "r1" / f"{dw._seat_key(seat)}.md").read_text().splitlines()
    blind = (kit / "Z-BLIND" / f"{letter}.md").read_text().splitlines()
    changed = dw._diff_positions(original, blind)
    assert len(changed) == 2
    for i in changed:
        key = original[i].split(":", 1)[0].strip()
        assert key in ("seat", "objective_sha256")


def test_diff_positions_refuses_a_length_mismatch_instead_of_a_silent_zip_truncation():
    # guilt: a bare zip(a, b) would stop at the shorter list and miss the extra trailing
    # line entirely -- _diff_positions must raise instead of returning a partial answer.
    with pytest.raises(ValueError):
        dw._diff_positions(["a", "b", "c"], ["a", "b"])


def test_diff_positions_reports_every_differing_index_on_equal_length_input():
    # innocence: same-length input still returns every differing position, unaffected by
    # the added length guard.
    assert dw._diff_positions(["a", "x", "c"], ["a", "b", "c"]) == [1]
    assert dw._diff_positions(["a", "b", "c"], ["a", "b", "c"]) == []


def test_anonymise_writes_one_z_blind_copy_per_surviving_letter(tmp_path, template, clean_objective):
    kit = _juried_kit(tmp_path, template, clean_objective, _THREE_FAMILY_SEATS)
    mapping = dw.cmd_anonymise(argparse.Namespace(kit=str(kit)))
    assert {p.stem for p in (kit / "Z-BLIND").glob("*.md")} == set(mapping)


def test_anonymise_keeps_jury_mapping_json_chmod_600(tmp_path, template, clean_objective):
    kit = _juried_kit(tmp_path, template, clean_objective, _THREE_FAMILY_SEATS)
    dw.cmd_anonymise(argparse.Namespace(kit=str(kit)))
    mapping_path = kit / "jury" / "mapping.json"
    assert oct(mapping_path.stat().st_mode)[-3:] == "600"


def test_reveal_refuses_before_z_decisioni_exists_and_prints_nothing(
        tmp_path, template, clean_objective, capsys):
    kit = _juried_kit(tmp_path, template, clean_objective, _THREE_FAMILY_SEATS)
    dw.cmd_anonymise(argparse.Namespace(kit=str(kit)))
    capsys.readouterr()  # discard anonymise's own stdout
    with pytest.raises(SystemExit) as e:
        dw.cmd_reveal(argparse.Namespace(kit=str(kit)))
    assert e.value.code == 2
    assert capsys.readouterr().out == ""


def test_reveal_prints_the_jury_mapping_once_z_decisioni_exists(tmp_path, template, clean_objective):
    kit = _juried_kit(tmp_path, template, clean_objective, _THREE_FAMILY_SEATS)
    mapping = dw.cmd_anonymise(argparse.Namespace(kit=str(kit)))
    (kit / "Z-DECISIONI.md").write_text("# Zero's decision\nA\n")
    revealed = dw.cmd_reveal(argparse.Namespace(kit=str(kit)))
    assert revealed == mapping


def test_reveal_writes_a_seat_annotated_tabulation_revealed_md(tmp_path, template, clean_objective):
    # innocence: the revealed file names them.
    kit = _juried_kit(tmp_path, template, clean_objective, _THREE_FAMILY_SEATS)
    mapping = dw.cmd_anonymise(argparse.Namespace(kit=str(kit)))
    (kit / "Z-DECISIONI.md").write_text("# Zero's decision\nA\n")
    dw.cmd_reveal(argparse.Namespace(kit=str(kit)))
    revealed_path = kit / "jury" / "tabulation.revealed.md"
    assert revealed_path.exists()
    text = revealed_path.read_text()
    for seat in mapping.values():
        assert seat in text


def test_reveal_never_rewrites_the_blind_tabulation_md(tmp_path, template, clean_objective):
    kit = _juried_kit(tmp_path, template, clean_objective, _THREE_FAMILY_SEATS)
    mapping = dw.cmd_anonymise(argparse.Namespace(kit=str(kit)))
    (kit / "Z-DECISIONI.md").write_text("# Zero's decision\nA\n")
    dw.cmd_reveal(argparse.Namespace(kit=str(kit)))
    blind_text = (kit / "jury" / "tabulation.md").read_text()
    for seat in mapping.values():
        assert seat not in blind_text


def _outcome_text() -> str:
    return "rounds_used: 1\ndead_at_launch: 0\nwall_clock: 4m\nbites: selftest green\n"


def _capture_ready_kit(tmp_path, template, clean_objective) -> Path:
    kit = _juried_kit(tmp_path, template, clean_objective, _THREE_FAMILY_SEATS)
    dw.cmd_anonymise(argparse.Namespace(kit=str(kit)))
    (kit / "Z-DECISIONI.md").write_text("# Zero's decision\nA\n")
    dw.cmd_reveal(argparse.Namespace(kit=str(kit)))  # PR2h obs 2: revealed twin now required
    (kit / "OUTCOME.md").write_text(_outcome_text())
    return kit


def _capture_ready_kit_with_slug(tmp_path, template, clean_objective, slug: str) -> Path:
    # own slug (not the shared "s" every other fixture in this file carries) so the two
    # real-canonical-dest tests below each own a distinct research/operations/ path and
    # can never collide, in this process or under any future parallel test run.
    kit = tmp_path / "k"
    dw.cmd_brief(argparse.Namespace(slug=slug, objective_file=str(clean_objective), colour="BLUE",
                                     floor=None, template=str(template), kit=str(kit)))
    _seed_convener(kit)
    dw.cmd_r1(argparse.Namespace(kit=str(kit), seats=_THREE_FAMILY_SEATS, astra_fallback=False))
    dw.cmd_judge(argparse.Namespace(kit=str(kit)))
    dw.cmd_jury(argparse.Namespace(kit=str(kit)))
    dw.cmd_anonymise(argparse.Namespace(kit=str(kit)))
    (kit / "Z-DECISIONI.md").write_text("# Zero's decision\nA\n")
    dw.cmd_reveal(argparse.Namespace(kit=str(kit)))  # PR2h obs 2: revealed twin now required
    (kit / "OUTCOME.md").write_text(_outcome_text())
    return kit


@pytest.mark.parametrize("missing_rel", ["BRIEF.md", "judge.md", "jury/tabulation.md",
                                          "jury/tabulation.revealed.md",
                                          "Z-DECISIONI.md", "OUTCOME.md", "r1", "r2"])
def test_capture_check_refuses_naming_one_missing_item(tmp_path, template, clean_objective, missing_rel):
    kit = _capture_ready_kit(tmp_path, template, clean_objective)
    target = kit / missing_rel
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
    dest = tmp_path / "dest"
    with pytest.raises(SystemExit) as e:
        dw.cmd_capture_check(argparse.Namespace(kit=str(kit), dest=str(dest)))
    assert e.value.code == 1
    assert not dest.exists()


def test_capture_check_refuses_naming_a_missing_outcome_key(tmp_path, template, clean_objective):
    kit = _capture_ready_kit(tmp_path, template, clean_objective)
    (kit / "OUTCOME.md").write_text("rounds_used: 1\ndead_at_launch: 0\n")  # wall_clock, bites missing
    dest = tmp_path / "dest"
    with pytest.raises(SystemExit) as e:
        dw.cmd_capture_check(argparse.Namespace(kit=str(kit), dest=str(dest)))
    assert e.value.code == 1
    assert not dest.exists()


def test_capture_check_refuses_a_dest_outside_research_operations(
        tmp_path, template, clean_objective):
    # guilt: right shape in every way except location -- must name it and create nothing.
    kit = _capture_ready_kit(tmp_path, template, clean_objective)
    dest = tmp_path / "dest"
    with pytest.raises(SystemExit) as e:
        dw.cmd_capture_check(argparse.Namespace(kit=str(kit), dest=str(dest)))
    assert e.value.code == 2
    assert not dest.exists()


def test_capture_check_refuses_a_dotdot_escape_from_research_operations(
        tmp_path, template, clean_objective):
    # guilt: resolve()-then-compare must catch a '..' escape, not just a literal string check.
    kit = _capture_ready_kit(tmp_path, template, clean_objective)
    escaped = dw.REPO_ROOT / "research" / "operations" / ".." / ".." / "tmp-capture-escape"
    with pytest.raises(SystemExit) as e:
        dw.cmd_capture_check(argparse.Namespace(kit=str(kit), dest=str(escaped)))
    assert e.value.code == 2
    assert not escaped.resolve().exists()


def test_capture_check_refuses_a_non_empty_existing_dest(tmp_path, template, clean_objective,
                                                           monkeypatch):
    kit = _capture_ready_kit_with_slug(tmp_path, template, clean_objective,
                                        "pytest-capture-nonempty")
    monkeypatch.setattr(dw, "REPO_ROOT", tmp_path)  # PR2h obs 10: never the real tree
    dest = dw._capture_dest_for(kit)
    try:
        dest.mkdir(parents=True, exist_ok=True)
        sentinel = dest / "already-here.txt"
        sentinel.write_text("pre-existing, must survive untouched\n")
        with pytest.raises(SystemExit) as e:
            dw.cmd_capture_check(argparse.Namespace(kit=str(kit), dest=str(dest)))
        assert e.value.code == 2
        assert sentinel.read_text() == "pre-existing, must survive untouched\n"
    finally:
        shutil.rmtree(dest, ignore_errors=True)


def test_capture_check_copies_the_full_artifact_set_when_everything_is_present(
        tmp_path, template, clean_objective, monkeypatch):
    kit = _capture_ready_kit_with_slug(tmp_path, template, clean_objective,
                                        "pytest-capture-success")
    monkeypatch.setattr(dw, "REPO_ROOT", tmp_path)  # PR2h obs 10: never the real tree
    dest = dw._capture_dest_for(kit)
    try:
        dw.cmd_capture_check(argparse.Namespace(kit=str(kit), dest=str(dest)))
        assert (dest / "BRIEF.md").exists()
        assert (dest / "brief.sha").exists()
        assert (dest / "judge.md").exists()
        assert (dest / "jury" / "tabulation.md").exists()
        assert (dest / "jury" / "tabulation.revealed.md").exists()
        assert not (dest / "jury" / "mapping.json").exists()
        assert (dest / "Z-DECISIONI.md").exists()
        assert (dest / "OUTCOME.md").exists()
        assert (dest / "r1").is_dir()
        assert (dest / "r2").is_dir()
    finally:
        shutil.rmtree(dest, ignore_errors=True)


def test_capture_check_refuses_a_fake_phone_in_outcome_md(
        tmp_path, template, clean_objective, capsys, monkeypatch):
    # guilt fixture per the addendum, verbatim: 'a fake phone in OUTCOME.md'. Same phone
    # literal _dirty_objective already uses elsewhere in this file to trip the redactor.
    kit = _capture_ready_kit_with_slug(tmp_path, template, clean_objective, "pytest-capture-pii")
    phone = "+6281234567890"
    (kit / "OUTCOME.md").write_text(_outcome_text().rstrip("\n") + f"\ncontact: {phone}\n")
    monkeypatch.setattr(dw, "REPO_ROOT", tmp_path)  # PR2h obs 10: never the real tree
    dest = dw._capture_dest_for(kit)
    capsys.readouterr()
    try:
        with pytest.raises(SystemExit) as e:
            dw.cmd_capture_check(argparse.Namespace(kit=str(kit), dest=str(dest)))
        assert e.value.code == 3
        assert not dest.exists()
        captured = capsys.readouterr()
        assert phone not in captured.out
        assert phone not in captured.err
        assert "OUTCOME.md" in captured.err
    finally:
        shutil.rmtree(dest, ignore_errors=True)


def test_capture_check_copies_a_clean_outcome_md_once_the_pii_gate_clears(
        tmp_path, template, clean_objective, monkeypatch):
    # innocence: identical kit shape, no PII -- the gate lets it straight through.
    kit = _capture_ready_kit_with_slug(tmp_path, template, clean_objective,
                                        "pytest-capture-pii-clean")
    monkeypatch.setattr(dw, "REPO_ROOT", tmp_path)  # PR2h obs 10: never the real tree
    dest = dw._capture_dest_for(kit)
    try:
        dw.cmd_capture_check(argparse.Namespace(kit=str(kit), dest=str(dest)))
        assert (dest / "OUTCOME.md").read_text() == _outcome_text()
    finally:
        shutil.rmtree(dest, ignore_errors=True)


# --------------------------------------------------------------- PR2h named refusals (obs 3+4)

def test_judge_refuses_a_non_utf8_r1_file_naming_it_instead_of_a_traceback(
        tmp_path, template, clean_objective, capsys):
    # guilt (PR2h addendum obs 3+4): a non-UTF8 file under r1/ used to raise a bare
    # UnicodeDecodeError out of .read_text() -- a traceback naming a line number, not a file.
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="kimi-k3", astra_fallback=False))
    bad_path = kit / "r1" / f"{dw._seat_key('kimi-k3')}.md"
    bad_path.write_bytes(b"\xff\xfe not valid utf-8 \x80\x81")
    with pytest.raises(SystemExit) as e:
        dw.cmd_judge(argparse.Namespace(kit=str(kit)))
    assert e.value.code == 2
    assert str(bad_path) in capsys.readouterr().err


def test_capture_check_refuses_a_kit_missing_inputs_json_naming_the_file(
        tmp_path, template, clean_objective, capsys):
    # guilt (PR2h addendum obs 3+4): inputs.json is absent from _CAPTURE_REQUIRED (it is an
    # internal input, not a captured artifact), so a kit missing it used to crash
    # _capture_dest_for with a bare FileNotFoundError out of json.loads() instead of a named
    # refusal.
    kit = _capture_ready_kit(tmp_path, template, clean_objective)
    inputs_path = kit / "inputs.json"
    inputs_path.unlink()
    dest = tmp_path / "dest"
    with pytest.raises(SystemExit) as e:
        dw.cmd_capture_check(argparse.Namespace(kit=str(kit), dest=str(dest)))
    assert e.value.code == 2
    assert not dest.exists()
    assert str(inputs_path) in capsys.readouterr().err


# --------------------------------------------------------------- validate_answer (guilt + innocence)

def _valid_text(sha="abc123"):
    return dw._CANNED_VALID.format(seat="kimi-k3", sha=sha)


VALIDATE_CASES = [
    ("canned valid answer", _valid_text("abc"), "abc", True),
    ("sha mismatch", _valid_text("abc"), "different", False),
    ("missing frontmatter", "## Formation\nno frontmatter here", "abc", False),
    ("out-of-order sections", _valid_text("abc").replace("## Formation", "## XFormation"), "abc", False),
    ("empty Formation table", _valid_text("abc").replace("| build | sonnet-5 | F1 | haiku-4-5 |\n", ""),
     "abc", False),
    ("over the 1500-word limit", _valid_text("abc") + ("filler word " * 1500), "abc", False),
]


@pytest.mark.parametrize("label,text,sha,expected_ok", VALIDATE_CASES, ids=[c[0] for c in VALIDATE_CASES])
def test_validate_answer(label, text, sha, expected_ok):
    ok, reason = dw.validate_answer(text, sha)
    assert ok == expected_ok, f"{label}: {reason}"


def test_validate_answer_refuses_a_table_that_is_only_header_and_separator():
    """Twin of the judge fix: validate_answer's own Formation/Tactics non-empty check must not
    count a separator row as the required data row. Must fail on the unmodified launcher,
    which returns (True, "ok") here."""
    sha = "3" * 64
    text = dw._CANNED_VALID.format(seat="kimi-k3", sha=sha).replace(
        "| build | sonnet-5 | F1 | haiku-4-5 |", "|---|---|---|---|")
    ok, reason = dw.validate_answer(text, sha)
    assert (ok, reason) == (False, "Formation table empty or missing a data row")


# --------------------------------------------------------------- selftest wrapper

def test_run_selftest_end_to_end(capsys):
    dw.run_selftest()  # raises SystemExit(1) via sys.exit only on failure; success returns
    out = capsys.readouterr().out
    assert "SELFTEST OK" in out
    assert "SELFTEST FAILED" not in out
    assert not [ln for ln in out.splitlines() if ln.startswith("FAIL - ")]


def test_run_selftest_never_touches_the_real_research_operations_tree(capsys):
    """PR2i obs 2/3 (gate-14 LOW-MEDIUM + LOW, GATE-14-REPORT-6791.md): run_selftest's capture
    block used to mkdir the canonical dest under the REAL REPO_ROOT/research/operations/ and
    clean up only in a `finally` -- a crash or SIGKILL between mkdir and rmtree left a stray
    dated directory in the actual working tree. Proof per obs 3: a date grep on the dest name
    cannot catch this (_capture_dest_for dates in UTC; PR2h's own proof line missed a whole
    day for exactly this reason, since the run landed on 2026-09-18 UTC while the local date
    was already 2026-09-19) -- an entry count plus every mtime, the parent directory included,
    is what "nothing written" actually has to mean.
    """
    real_ops = dw.REPO_ROOT / "research" / "operations"
    before_names = sorted(p.name for p in real_ops.iterdir())
    watched = [real_ops, *real_ops.iterdir()]
    before_mtimes = {p: p.stat().st_mtime_ns for p in watched}
    dw.run_selftest()
    capsys.readouterr()
    after_names = sorted(p.name for p in real_ops.iterdir())
    assert after_names == before_names
    after_mtimes = {p: p.stat().st_mtime_ns for p in watched}
    assert after_mtimes == before_mtimes


def _refuse_to_launch(seat, prompt, timeout, kit):
    raise AssertionError("real seat launch attempted")


def test_r2_refuses_a_non_utf8_r1_partner_file_before_launching_any_seat(
        monkeypatch, tmp_path, template, clean_objective, capsys):
    """PR2i obs 1 (gate-14 MEDIUM, GATE-14-REPORT-6791.md): the r2 read of a partner's r1
    file lives in the non-fake branch, unreachable while the autouse fixture holds
    DW_FAKE_SEATS=1 -- mutating this site's _read_text_or_refuse() to a bare .read_text()
    left every other test green (mutation M6). DW_FAKE_SEATS is dropped and _launch_seat
    stubbed to raise, so a real launch attempted after a missed refusal fails the test too.
    """
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    dw.cmd_r1(argparse.Namespace(kit=str(kit), seats=_THREE_FAMILY_SEATS, astra_fallback=False))
    bad_path = kit / "r1" / f"{dw._seat_key('qwen3.8-max')}.md"
    bad_path.write_bytes(b"\xff\xfe not valid utf-8 \x80\x81")
    monkeypatch.delenv("DW_FAKE_SEATS", raising=False)
    monkeypatch.setattr(dw, "_launch_seat", _refuse_to_launch)
    with pytest.raises(SystemExit) as e:
        dw.cmd_r2(argparse.Namespace(kit=str(kit)))
    assert e.value.code == 2
    assert str(bad_path) in capsys.readouterr().err


def test_jury_prompt_refuses_a_non_utf8_r1_partner_file_before_launching_any_seat(
        monkeypatch, tmp_path, template, clean_objective, capsys):
    """PR2i obs 1 (gate-14 MEDIUM): _jury_prompt's read of a peer's r1 file lives in
    cmd_jury's own non-fake branch, same structural gap as r2 (mutation M7 left every other
    test green). DW_FAKE_SEATS dropped, _launch_seat stubbed to raise on any real attempt.
    """
    kit = _judged_kit(tmp_path, template, clean_objective, _THREE_FAMILY_SEATS)
    bad_path = kit / "r1" / f"{dw._seat_key('qwen3.8-max')}.md"
    bad_path.write_bytes(b"\xff\xfe not valid utf-8 \x80\x81")
    monkeypatch.delenv("DW_FAKE_SEATS", raising=False)
    monkeypatch.setattr(dw, "_launch_seat", _refuse_to_launch)
    with pytest.raises(SystemExit) as e:
        dw.cmd_jury(argparse.Namespace(kit=str(kit)))
    assert e.value.code == 2
    assert str(bad_path) in capsys.readouterr().err


def test_anonymise_refuses_a_non_utf8_r1_mapped_file_naming_it_instead_of_a_traceback(
        tmp_path, template, clean_objective, capsys):
    """PR2i obs 1 (gate-14 MEDIUM): cmd_anonymise's own _read_text_or_refuse call (no
    fake/not-fake gate at all -- it always reads real r1/ files) stayed green under every
    other test's mutation too (M8): nothing in the suite fed it a bad file before this.
    """
    kit = _juried_kit(tmp_path, template, clean_objective, _THREE_FAMILY_SEATS)
    bad_path = kit / "r1" / f"{dw._seat_key('qwen3.8-max')}.md"
    bad_path.write_bytes(b"\xff\xfe not valid utf-8 \x80\x81")
    with pytest.raises(SystemExit) as e:
        dw.cmd_anonymise(argparse.Namespace(kit=str(kit)))
    assert e.value.code == 2
    assert str(bad_path) in capsys.readouterr().err


def test_capture_pii_gate_refuses_a_non_utf8_scan_target_before_any_dest_write(
        monkeypatch, tmp_path, template, clean_objective, capsys):
    """PR2i obs 1 (gate-14 MEDIUM): _capture_pii_gate's own _read_text_or_refuse(f) call
    stayed green under every other test's mutation too (M9): capture-check's missing-item
    and dest-shape checks run first and never touch file bytes, so nothing upstream caught
    it either. REPO_ROOT is swapped to a throwaway root first (same technique as the
    selftest fix above), so a bug that reached dest.mkdir() before the refusal fired could
    never write into the real tree.
    """
    kit = _capture_ready_kit(tmp_path, template, clean_objective)
    bad_path = kit / "Z-DECISIONI.md"
    bad_path.write_bytes(b"\xff\xfe not valid utf-8 \x80\x81")
    monkeypatch.setattr(dw, "REPO_ROOT", tmp_path / "fake_repo_root")
    dest = dw._capture_dest_for(kit)
    with pytest.raises(SystemExit) as e:
        dw.cmd_capture_check(argparse.Namespace(kit=str(kit), dest=str(dest)))
    assert e.value.code == 2
    assert str(bad_path) in capsys.readouterr().err
    assert not dest.exists()


def test_seat_key_consolidation_guards_the_full_chain_for_an_aliased_seat(
        monkeypatch, tmp_path, template, clean_objective):
    """gate-15 obs 1 (MEDIUM, GATE-15-REPORT-6796.md): reverting cmd_r2's partner read
    (:816), own write (:825), rejected write (:827), cmd_judge's read (:887),
    _jury_prompt's read (:1099) or cmd_anonymise's read (:1161) back to raw _file_slug(seat)
    left the shipped suite green at 106/106 -- only _claim_slug and the r1 writer were
    guarded. kimi-2.7 canonicalizes to a DIFFERENT spelling, so each site reads/writes the
    wrong path once _seat_key stops being the one formula in force. The seventh site
    (run_selftest's own capture-check exercise, :1568) is proven separately by the
    temp-REPO_ROOT test above -- the selftest dispatches no aliased seat, so this chain
    cannot cover it.
    """
    seats = "kimi-2.7,qwen3.8-max,gemini-3.1-pro-high"
    key = dw._seat_key("kimi-2.7")
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    dw.cmd_r1(argparse.Namespace(kit=str(kit), seats=seats, astra_fallback=False))
    assert (kit / "r1" / f"{key}.md").exists()  # site :557 (already guarded), sanity anchor

    monkeypatch.delenv("DW_FAKE_SEATS", raising=False)
    monkeypatch.setattr(dw, "_launch_seat", lambda seat, prompt, timeout, kit: dw._fake_r2_output(seat))
    dw.cmd_r2(argparse.Namespace(kit=str(kit)))
    assert (kit / "r2" / f"{key}.md").exists()  # site :825
    assert (kit / "r2" / f"{key}.rejected.md").exists()  # site :827
    monkeypatch.setenv("DW_FAKE_SEATS", "1")  # back to fake: judge/jury's own ballots need no launch

    dw.cmd_judge(argparse.Namespace(kit=str(kit)))  # also exercises :816 (both other seats targeted kimi-2.7)
    assert "| kimi-2.7 |" in (kit / "judge.md").read_text()  # site :887

    dw.cmd_jury(argparse.Namespace(kit=str(kit)))
    survivors = dw._jury_survivors(kit)
    mapping = dw._jury_mapping(kit, survivors)
    inverse = {seat: ltr for ltr, seat in mapping.items()}
    prompt = dw._jury_prompt(kit, mapping, [inverse["kimi-2.7"]])  # direct call, fake-mode path
    assert dw._strip_identity((kit / "r1" / f"{key}.md").read_text()) in prompt  # site :1099

    dw.cmd_anonymise(argparse.Namespace(kit=str(kit)))
    assert (kit / "Z-BLIND" / f"{inverse['kimi-2.7']}.md").exists()  # site :1161


# --------------------------------------------------------------- PR3g: seat output normalisation

_WRAPPER_LINE_RE = re.compile(r"^```\w*$")


def _dewrap_one_line(line: str) -> str:
    if line.startswith("• "):
        return line[2:]
    if line.startswith("  "):
        return line[2:]
    return line


@pytest.mark.parametrize("fixture_name", ["kimi-decorated.md", "gemini-fenced.md"])
def test_normalise_seat_output_fixture_fails_raw_passes_normalised(fixture_name):
    """G4: each fixture is a real coach answer copied from the live VISA-ORACLE-DW-20260919
    kit (PII-checked before commit — no '@', phone shape or passport token). Raw bytes fail
    validate_answer (the wrapper hides byte 0's '---'); the normalised text passes, against
    the fixture's OWN objective_sha256 line."""
    raw = (FIXTURES_DIR / fixture_name).read_text()
    m = re.search(r"objective_sha256:\s*(\S+)", raw)
    assert m, f"{fixture_name} carries no objective_sha256 line to anchor the expected sha"
    expected_sha = m.group(1)

    raw_ok, raw_reason = dw.validate_answer(raw, expected_sha)
    assert raw_ok is False, f"{fixture_name} raw unexpectedly validated: {raw_reason}"

    normalised = dw._normalise_seat_output(raw)
    norm_ok, norm_reason = dw.validate_answer(normalised, expected_sha)
    assert norm_ok is True, f"{fixture_name} normalised still fails: {norm_reason}"


@pytest.mark.parametrize("fixture_name", ["kimi-decorated.md", "gemini-fenced.md"])
def test_normalise_seat_output_is_idempotent_on_both_fixtures(fixture_name):
    raw = (FIXTURES_DIR / fixture_name).read_text()
    once = dw._normalise_seat_output(raw)
    twice = dw._normalise_seat_output(once)
    assert once == twice


def test_normalise_seat_output_is_not_idempotent_on_a_doubly_fenced_input():
    """PR3h/h4, gate-20 obs 3, PINNED not fixed: the launcher strips one fence layer per call
    (rule (b)), so a doubly-fenced answer (a fence wrapping another fence) needs two calls to
    fully unwrap. This is the accepted behaviour, not a bug — cmd_r1/_cmd_r1_register each call
    _normalise_seat_output exactly once per stage, so a doubly-fenced input is unreachable in
    practice from a real coach; a human pasting one by hand gets the outer layer stripped and
    the inner ```-delimited block left as literal text in the answer body, same as any other
    fence rule (b) does not recognise as a wrapper."""
    inner = dw._CANNED_VALID.format(seat="doubly-fenced", sha="2" * 64).strip()
    doubly_fenced = "```markdown\n```markdown\n" + inner + "\n```\n```\n"
    once = dw._normalise_seat_output(doubly_fenced)
    twice = dw._normalise_seat_output(once)
    assert once != inner
    assert twice == inner
    assert once != twice


@pytest.mark.parametrize("fixture_name", ["kimi-decorated.md", "gemini-fenced.md"])
def test_normalise_seat_output_cures_a_crlf_copy_of_a_valid_fixture(fixture_name):
    """PR3h/h1, gate-20 obs 4, GUILT proof: a CRLF-line-ending copy of an otherwise-clean
    fixture fails `validate_answer` even AFTER the fence/bullet unwrap, because `_FM_RE` wants
    `---\\n` and the line reads `---\\r\\n` — the exact failure class PR3g's addendum exists to
    fix. Normalising the CRLF copy must both strip the `\\r` and still pass the fixture's own
    objective_sha256."""
    raw = (FIXTURES_DIR / fixture_name).read_text()
    m = re.search(r"objective_sha256:\s*(\S+)", raw)
    assert m, f"{fixture_name} carries no objective_sha256 line to anchor the expected sha"
    expected_sha = m.group(1)
    crlf_raw = raw.replace("\n", "\r\n")

    normalised = dw._normalise_seat_output(crlf_raw)
    assert "\r" not in normalised
    ok, reason = dw.validate_answer(normalised, expected_sha)
    assert ok is True, f"{fixture_name} CRLF copy still fails after normalisation: {reason}"


@pytest.mark.parametrize("fixture_name", ["kimi-decorated.md", "gemini-fenced.md"])
def test_f11_guard_wrapper_removal_touches_only_wrapper_bytes(fixture_name):
    """F11 (G1): the launcher must never re-author a seat's content. The line-diff between
    raw and normalised, on both fixtures, contains only fence lines, '• ' prefixes,
    two-space indents and the resume trailer -- nothing else changes. Every 'replace' opcode
    must reduce to a pure de-wrap (removing only the recognised prefix leaves the line
    byte-identical to its normalised counterpart); every 'delete' opcode must consist only of
    fence-marker or resume-trailer lines."""
    raw = (FIXTURES_DIR / fixture_name).read_text()
    normalised = dw._normalise_seat_output(raw)
    raw_lines = raw.strip("\n").splitlines()
    norm_lines = normalised.splitlines()

    sm = difflib.SequenceMatcher(None, raw_lines, norm_lines)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        if tag == "delete":
            for line in raw_lines[i1:i2]:
                stripped = line.strip()
                is_fence = bool(_WRAPPER_LINE_RE.match(stripped))
                is_trailer = _dewrap_one_line(line).lstrip().startswith("To resume this session:")
                assert is_fence or is_trailer, (
                    f"{fixture_name}: deleted line is neither a fence nor the resume "
                    f"trailer: {line!r}")
        elif tag == "replace":
            assert (i2 - i1) == (j2 - j1), (
                f"{fixture_name}: replace opcode changes line COUNT ({i2-i1} -> {j2-j1}), "
                f"not just wrapper bytes")
            for ri, nj in zip(range(i1, i2), range(j1, j2)):
                assert _dewrap_one_line(raw_lines[ri]) == norm_lines[nj], (
                    f"{fixture_name}: line {ri} changed by more than its own wrapper prefix: "
                    f"{raw_lines[ri]!r} -> {norm_lines[nj]!r}")
        else:  # pragma: no cover - insert never fires: normalisation only ever removes bytes
            pytest.fail(f"{fixture_name}: unexpected '{tag}' opcode — normalisation added a line")


def test_normalise_seat_output_is_a_noop_on_already_clean_text(tmp_path):
    clean = dw._CANNED_VALID.format(seat="clean-seat", sha="1" * 64).strip()
    assert dw._normalise_seat_output(clean) == clean
    assert dw._normalise_seat_output(dw._normalise_seat_output(clean)) == clean


def test_normalise_seat_output_empty_string_is_a_noop():
    assert dw._normalise_seat_output("") == ""
    assert dw._normalise_seat_output("   \n  \n") == ""


def test_r1_writes_a_raw_copy_beside_the_normalised_answer(tmp_path, template, clean_objective):
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="kimi-k3", astra_fallback=False))
    raw_path = kit / "r1" / "kimi-k3.raw.md"
    assert raw_path.exists()
    assert raw_path.read_text() == dw._fake_seat_output("kimi-k3", (kit / "brief.sha").read_text().strip(), 1)


def test_r1_attempt_files_never_overwrite_each_other(tmp_path, template, clean_objective):
    """G2: the second defect the addendum named — attempt 2 used to overwrite attempt 1's
    only copy via a plain `out_path.write_text`. z-fakeflaky is dead on attempt 1 (empty
    output), answered on attempt 2 (auto-relaunch inside cmd_r1); both attempt files must
    survive, distinct, and r1/<seat>.md must hold the LAST attempt."""
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="z-fakeflaky", astra_fallback=False))
    key = dw._seat_key("z-fakeflaky")
    attempt1 = (kit / "r1" / f"{key}.attempt1.md").read_text()
    attempt2 = (kit / "r1" / f"{key}.attempt2.md").read_text()
    assert attempt1 == ""
    assert attempt2.strip() != ""
    assert attempt1 != attempt2
    assert (kit / "r1" / f"{key}.md").read_text() == attempt2


def test_r1_raw_files_never_overwrite_each_other(tmp_path, template, clean_objective):
    """PR3h/h3, gate-20 obs 5: attempt 2's raw bytes used to overwrite attempt 1's only raw
    copy at r1/<seat>.raw.md — same defect G2 already fixed for the NORMALISED file (see
    test_r1_attempt_files_never_overwrite_each_other above), now fixed for the raw one too.
    z-fakeflaky is dead (empty raw) on attempt 1, answered on attempt 2."""
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="z-fakeflaky", astra_fallback=False))
    key = dw._seat_key("z-fakeflaky")
    raw_attempt1 = (kit / "r1" / f"{key}.attempt1.raw.md").read_text()
    raw_attempt2 = (kit / "r1" / f"{key}.attempt2.raw.md").read_text()
    assert raw_attempt1 == ""
    assert raw_attempt2.strip() != ""
    assert raw_attempt1 != raw_attempt2
    assert (kit / "r1" / f"{key}.raw.md").read_text() == raw_attempt2


def test_r2_writes_a_raw_copy_beside_the_normalised_objections(tmp_path, template, clean_objective):
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="kimi-k3,qwen3.8-max,gemini-3.1-pro-high",
                                  astra_fallback=False))
    dw.cmd_r2(argparse.Namespace(kit=str(kit)))
    key = dw._seat_key("kimi-k3")
    raw_path = kit / "r2" / f"{key}.raw.md"
    assert raw_path.exists()
    assert raw_path.read_text() == dw._fake_r2_output("kimi-k3")


def test_jury_writes_a_raw_ballot_beside_the_normalised_one(tmp_path, template, clean_objective):
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="kimi-k3,qwen3.8-max,gemini-3.1-pro-high",
                                  astra_fallback=False))
    dw.cmd_judge(argparse.Namespace(kit=str(kit)))
    dw.cmd_jury(argparse.Namespace(kit=str(kit)))
    survivors = dw._jury_survivors(kit)
    mapping = dw._jury_mapping(kit, survivors)
    inverse = {seat: ltr for ltr, seat in mapping.items()}
    letter = inverse["kimi-k3"]
    raw_path = kit / "jury" / f"ballot-{letter}.raw.md"
    assert raw_path.exists()
    others = sorted(ltr for ltr in mapping if ltr != letter)
    assert raw_path.read_text() == dw._fake_jury_output("kimi-k3", others)


# --------------------------------------------------------------- PR3g: r1 --register

def _seed_awaiting_window(kit: Path, seat: str) -> None:
    dw.ledger_append(kit, seat, "awaiting-window", "-")


def _window_path(kit: Path, seat: str) -> Path:
    return kit / "r1" / f"{dw._seat_key(seat)}-window.md"


def test_register_requires_seats_to_name_exactly_the_registered_seat(tmp_path, template, clean_objective):
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    with pytest.raises(SystemExit) as exc:
        dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="hand-seat,other-seat",
                                      astra_fallback=False, register="hand-seat"))
    assert exc.value.code == 2


def test_register_refuses_a_seat_with_no_awaiting_window_row(tmp_path, template, clean_objective):
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    with pytest.raises(SystemExit) as exc:
        dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="never-seen", astra_fallback=False,
                                      register="never-seen"))
    assert exc.value.code == 2


def test_register_fails_closed_on_an_invalid_window_file(tmp_path, template, clean_objective):
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    _seed_awaiting_window(kit, "hand-seat")
    _window_path(kit, "hand-seat").write_text("not a valid answer, no frontmatter\n")
    with pytest.raises(SystemExit) as exc:
        dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="hand-seat", astra_fallback=False,
                                      register="hand-seat"))
    assert exc.value.code == 1
    assert dw._ledger_seat_has_status(kit, "hand-seat", "window-invalid")
    assert not (kit / "r1" / f"{dw._seat_key('hand-seat')}.md").exists()


def test_register_passes_a_normalised_window_file_and_stamps_its_own_mtime(
        tmp_path, template, clean_objective):
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    sha = _seed_convener(kit)
    _seed_awaiting_window(kit, "hand-seat")

    clean = dw._CANNED_VALID.format(seat="hand-seat", sha=sha).strip()
    fenced = "```markdown\n" + clean + "\n```\n"  # a human pastes exactly what the CLI gave them
    window_path = _window_path(kit, "hand-seat")
    window_path.write_text(fenced)

    result = dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="hand-seat", astra_fallback=False,
                                           register="hand-seat"))
    assert result == {"hand-seat": "answered"}
    assert (kit / "r1" / f"{dw._seat_key('hand-seat')}.md").read_text() == clean

    want_when = datetime.fromtimestamp(window_path.stat().st_mtime, tz=timezone.utc).replace(microsecond=0)
    assert dw._ledger_when(kit, "hand-seat", status="answered") == want_when


def test_register_stamp_is_read_from_the_answered_row_not_the_awaiting_window_row(
        tmp_path, template, clean_objective):
    """PR3m, the clock made deterministic: `_ledger_when(kit, seat)` returns the seat's FIRST
    row, which for a registered seat is `awaiting-window` (stamped at append time), not
    `answered` (stamped at the window file's mtime). The old assertion compared the first row
    with the mtime and held only while both fell in the same second — red under load, once in
    the selftest's own twin of this check. Here the awaiting-window row is a year old, so the
    two rows can never agree by luck."""
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    sha = _seed_convener(kit)
    dw.ledger_append(kit, "hand-seat", "awaiting-window", "-", when="2025-01-01T00:00:00Z")
    window_path = _window_path(kit, "hand-seat")
    window_path.write_text(dw._CANNED_VALID.format(seat="hand-seat", sha=sha))

    dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="hand-seat", astra_fallback=False,
                                  register="hand-seat"))

    want_when = datetime.fromtimestamp(window_path.stat().st_mtime, tz=timezone.utc).replace(microsecond=0)
    assert dw._ledger_when(kit, "hand-seat", status="answered") == want_when
    assert dw._ledger_when(kit, "hand-seat") == datetime(2025, 1, 1, tzinfo=timezone.utc)
    assert dw._ledger_when(kit, "hand-seat", status="window-invalid") is None


def test_fixture_template_lives_in_the_callers_own_dir_never_a_shared_path(tmp_path):
    """PR3m: the selftest's template was one fixed path under the system temp dir, rewritten
    on every call — two selftests at once read each other's half-written file (2 red in 30
    concurrent runs, `brief sha stable across identical runs` / `check passes on untouched
    kit`). Two callers must get two files, each inside its own dir."""
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    pa, pb = dw._fixture_template(a), dw._fixture_template(b)
    assert pa != pb
    assert pa.parent == a and pb.parent == b
    assert pa.read_text() == pb.read_text() == dw._FIXTURE_TEMPLATE_TEXT


def test_register_refuses_a_seat_already_answered(tmp_path, template, clean_objective):
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    sha = _seed_convener(kit)
    _seed_awaiting_window(kit, "hand-seat")
    _window_path(kit, "hand-seat").write_text(dw._CANNED_VALID.format(seat="hand-seat", sha=sha))
    dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="hand-seat", astra_fallback=False,
                                  register="hand-seat"))
    with pytest.raises(SystemExit) as exc:
        dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="hand-seat", astra_fallback=False,
                                      register="hand-seat"))
    assert exc.value.code == 2


def test_register_pass_prints_the_same_summary_line_every_other_r1_path_prints(
        tmp_path, template, clean_objective, capsys):
    """PR3h/h2, gate-20 obs 6: a successful --register used to return before cmd_r1's own
    `for seat, status in summary.items(): print(...)` loop, so it was the one silent-success
    path in the whole command — exactly the path a human is watching right after a hand
    paste."""
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    sha = _seed_convener(kit)
    _seed_awaiting_window(kit, "hand-seat")
    _window_path(kit, "hand-seat").write_text(dw._CANNED_VALID.format(seat="hand-seat", sha=sha))
    capsys.readouterr()  # discard cmd_brief's own stdout, if any

    result = dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="hand-seat", astra_fallback=False,
                                           register="hand-seat"))
    assert result == {"hand-seat": "answered"}
    assert capsys.readouterr().out == "hand-seat: answered\n"


def test_register_cures_a_crlf_hand_pasted_window_file(tmp_path, template, clean_objective):
    """PR3h/h1 end-to-end: `r1 --register` is exactly the path a human hand-pastes into (a
    terminal window that may carry CRLF line endings), so this is the addendum's headline
    scenario. Without the CRLF fix in _normalise_seat_output, this window file would still
    fail validate_answer's frontmatter check and register `window-invalid` (exit 1)."""
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    sha = _seed_convener(kit)
    _seed_awaiting_window(kit, "hand-seat")

    clean = dw._CANNED_VALID.format(seat="hand-seat", sha=sha).strip()
    crlf = clean.replace("\n", "\r\n") + "\r\n"
    window_path = _window_path(kit, "hand-seat")
    window_path.write_text(crlf)

    result = dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="hand-seat", astra_fallback=False,
                                           register="hand-seat"))
    assert result == {"hand-seat": "answered"}
    assert (kit / "r1" / f"{dw._seat_key('hand-seat')}.md").read_text() == clean
