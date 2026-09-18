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
import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest

MODULE_PATH = Path(__file__).resolve().parent.parent / "dynamic_workflow.py"


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


def test_ledger_append_is_hashed_and_verify_passes(tmp_path, template, clean_objective):
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    dw.ledger_append(kit, "kimi-k3", "sent", "deadbeefcafef00d")
    dw.ledger_append(kit, "kimi-k3", "answered", "deadbeefcafef00d")
    ok, _ = dw.ledger_verify(kit)
    assert ok
    assert len(dw._ledger_path(kit).read_text().splitlines()) == 2


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

    def _fake_env(env=None):
        return sentinel_env

    def _fake_run(cmd, **kwargs):
        calls.append(kwargs)
        (kit / "r1" / "astra.md").write_text("stub output")
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

    def _fake_env(env=None):
        return dict(os.environ)

    def _fake_run(cmd, **kwargs):
        calls.append(kwargs)
        return None

    monkeypatch.setattr(dw, "codex_seat_env", _fake_env)
    monkeypatch.setattr(dw.subprocess, "run", _fake_run)

    output = dw._launch_seat("astra", "prompt text", 5, kit)

    assert output == ""  # out_file never written, "no seat" is not a crash
    assert len(calls) == 1
    assert calls[0].get("env") == dict(os.environ)


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


# --------------------------------------------------------------- selftest wrapper

def test_run_selftest_end_to_end(capsys):
    dw.run_selftest()  # raises SystemExit(1) via sys.exit only on failure; success returns
    out = capsys.readouterr().out
    assert "SELFTEST OK" in out
    assert "SELFTEST FAILED" not in out
    assert not [ln for ln in out.splitlines() if ln.startswith("FAIL - ")]
