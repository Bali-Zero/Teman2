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
import shutil
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

    def _fake_env(_env=None):
        return sentinel_env

    def _fake_run(_cmd, **kwargs):
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
        "| gate | opus-5 | window | serial | 1 | sign | done |\n", "")
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
# _file_slug(), and by validating the seat id BEFORE the first ledger_append.

def test_r1_seat_id_with_a_slash_writes_under_a_file_safe_slug(tmp_path, template, clean_objective):
    kit = tmp_path / "k"
    dw.cmd_brief(_brief_ns(clean_objective, template, kit))
    _seed_convener(kit)
    dw.cmd_r1(argparse.Namespace(kit=str(kit), seats="kimi-code/k3", astra_fallback=False))
    assert (kit / "r1" / "kimi-code__k3.md").exists()
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


def test_anonymise_z_blind_copy_differs_from_the_original_only_on_seat_and_sha_lines(
        tmp_path, template, clean_objective):
    kit = _juried_kit(tmp_path, template, clean_objective, _THREE_FAMILY_SEATS)
    mapping = dw.cmd_anonymise(argparse.Namespace(kit=str(kit)))
    letter, seat = next(iter(mapping.items()))
    original = (kit / "r1" / f"{dw._file_slug(seat)}.md").read_text().splitlines()
    blind = (kit / "Z-BLIND" / f"{letter}.md").read_text().splitlines()
    assert len(original) == len(blind)
    changed = [i for i, (o, b) in enumerate(zip(original, blind)) if o != b]
    assert len(changed) == 2
    for i in changed:
        key = original[i].split(":", 1)[0].strip()
        assert key in ("seat", "objective_sha256")


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


def _outcome_text() -> str:
    return "rounds_used: 1\ndead_at_launch: 0\nwall_clock: 4m\nbites: selftest green\n"


def _capture_ready_kit(tmp_path, template, clean_objective) -> Path:
    kit = _juried_kit(tmp_path, template, clean_objective, _THREE_FAMILY_SEATS)
    dw.cmd_anonymise(argparse.Namespace(kit=str(kit)))
    (kit / "Z-DECISIONI.md").write_text("# Zero's decision\nA\n")
    (kit / "OUTCOME.md").write_text(_outcome_text())
    return kit


@pytest.mark.parametrize("missing_rel", ["BRIEF.md", "judge.md", "jury/tabulation.md",
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


def test_capture_check_copies_the_full_artifact_set_when_everything_is_present(
        tmp_path, template, clean_objective):
    kit = _capture_ready_kit(tmp_path, template, clean_objective)
    dest = tmp_path / "dest"
    dw.cmd_capture_check(argparse.Namespace(kit=str(kit), dest=str(dest)))
    assert (dest / "BRIEF.md").exists()
    assert (dest / "brief.sha").exists()
    assert (dest / "judge.md").exists()
    assert (dest / "jury" / "tabulation.md").exists()
    assert (dest / "Z-DECISIONI.md").exists()
    assert (dest / "OUTCOME.md").exists()
    assert (dest / "r1").is_dir()
    assert (dest / "r2").is_dir()


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
