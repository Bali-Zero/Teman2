"""Tests for scripts/harness_fable_gate.py — the harness/fable-gate publisher.

This is a PUBLISHER, not a guard (it never accepts/rejects PR content — see
its own docstring: "no verdict logic inside"), so it is deliberately NOT
registered in infra/guard-conformance/registry.json alongside
evidence_pack_lint.py. These tests still pin the verdict->state mapping and
the CLI's --dry-run contract so a future edit can't quietly invert PASS/BLOCK.
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"

sys.path.insert(0, str(SCRIPTS))
import harness_fable_gate  # noqa: E402
from harness_fable_gate import (  # noqa: E402
    VERDICT_STATE,
    build_description,
    check_overwrite,
    ledger_append,
    ledger_command,
    main,
)

HEAD = "a" * 40


@pytest.fixture(autouse=True)
def _no_ledger_ssh(monkeypatch, request):
    """main() appends to the Pro ledger before it posts (B25-prime P1): no test here may reach ssh. The tests of ledger_append itself
    (named test_ledger_append_*) and the end-to-end one stub the process layer below it instead."""
    if not request.node.name.startswith(("test_ledger_append_", "test_the_publisher_and_the_ledger")):
        monkeypatch.setattr(harness_fable_gate, "ledger_append", lambda *a, **k: 0)


def test_pass_maps_to_success():
    assert VERDICT_STATE["PASS"] == "success"


def test_pass_with_conditions_maps_to_success():
    assert VERDICT_STATE["PASS-WITH-CONDITIONS"] == "success"


def test_rework_build_maps_to_failure():
    assert VERDICT_STATE["REWORK-BUILD"] == "failure"


def test_rework_design_maps_to_failure():
    assert VERDICT_STATE["REWORK-DESIGN"] == "failure"


def test_block_maps_to_failure():
    assert VERDICT_STATE["BLOCK"] == "failure"


def test_exactly_five_legal_verdicts():
    """No sixth verdict can sneak in — the harness-v2 §6 grammar is closed."""
    assert set(VERDICT_STATE) == {
        "PASS", "PASS-WITH-CONDITIONS", "REWORK-BUILD", "REWORK-DESIGN", "BLOCK",
    }


def test_description_names_degraded_fallback():
    desc = build_description("PASS", degraded=True, extra=None, conditions_ref=None)
    assert "gate_degraded=fable->opus" in desc


def test_description_clean_pass_has_no_degraded_marker():
    desc = build_description("PASS", degraded=False, extra=None, conditions_ref=None)
    assert "gate_degraded" not in desc


def test_description_carries_conditions_ref_only_on_pwc():
    desc = build_description("PASS-WITH-CONDITIONS", degraded=False, extra=None,
                              conditions_ref="PENDING-ARMS.md#L900")
    assert "PENDING-ARMS.md#L900" in desc
    desc_pass = build_description("PASS", degraded=False, extra=None,
                                   conditions_ref="PENDING-ARMS.md#L900")
    assert "PENDING-ARMS.md#L900" not in desc_pass


def test_description_truncates_at_140_chars():
    long_extra = "x" * 300
    desc = build_description("PASS", degraded=False, extra=long_extra, conditions_ref=None)
    assert len(desc) <= 140
    assert desc.endswith("...")


def test_cli_dry_run_prints_gh_command_without_network():
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "harness_fable_gate.py"),
         "--verdict", "PASS", "--sha", "deadbeef", "--repo", "acme/example", "--dry-run"],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "DRY-RUN:" in proc.stdout
    assert "state=success" in proc.stdout
    assert "context=harness/fable-gate" in proc.stdout
    assert "repos/acme/example/statuses/deadbeef" in proc.stdout


def test_cli_rejects_unknown_verdict():
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "harness_fable_gate.py"),
         "--verdict", "APPROVED", "--sha", "deadbeef", "--dry-run"],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode != 0


def test_cli_dry_run_marks_degraded_and_block_as_failure():
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "harness_fable_gate.py"),
         "--verdict", "BLOCK", "--sha", "cafef00d", "--repo", "acme/example",
         "--degraded", "--dry-run"],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "state=failure" in proc.stdout
    assert "gate_degraded" in proc.stdout


def test_cli_rejects_pwc_without_conditions_ref():
    """GUILT (adversarial-review 2026-08-10): PASS-WITH-CONDITIONS with no
    --conditions-ref is an unenforceable PWC — harness-v2 §6 calls that
    shape 'la falla da cui passa tutto'. Must refuse, not silently publish."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "harness_fable_gate.py"),
         "--verdict", "PASS-WITH-CONDITIONS", "--sha", "deadbeef",
         "--repo", "acme/example", "--dry-run"],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode != 0
    assert "--conditions-ref" in proc.stderr


def test_cli_accepts_pwc_with_conditions_ref():
    """INNOCENCE: the same verdict WITH a --conditions-ref publishes
    normally."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "harness_fable_gate.py"),
         "--verdict", "PASS-WITH-CONDITIONS", "--sha", "deadbeef",
         "--repo", "acme/example", "--conditions-ref", "PENDING-ARMS.md#L900",
         "--dry-run"],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "state=success" in proc.stdout


def test_cli_conditions_ref_not_required_for_other_verdicts():
    """INNOCENCE: PASS/BLOCK/etc without --conditions-ref are unaffected —
    the new guard is scoped to PASS-WITH-CONDITIONS only."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "harness_fable_gate.py"),
         "--verdict", "PASS", "--sha", "deadbeef", "--repo", "acme/example",
         "--dry-run"],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


# --- overwrite guard: check_overwrite (pure, no I/O) ------------------------

def test_check_overwrite_no_existing_no_supersede_is_ok():
    ok, msg = check_overwrite([], None)
    assert ok is True
    assert msg == ""


def test_check_overwrite_no_existing_with_supersede_is_refused():
    """GUILT: a --supersede claiming to overwrite a verdict that does not
    exist is a false sentence — refuse it."""
    ok, msg = check_overwrite([], "some reason")
    assert ok is False
    assert "nothing to supersede" in msg


def test_check_overwrite_one_existing_no_supersede_is_refused():
    existing = [{"state": "failure", "description": "REWORK-BUILD | x",
                 "created_at": "2026-09-21T01:00:00Z"}]
    ok, msg = check_overwrite(existing, None)
    assert ok is False
    assert "failure" in msg
    assert "2026-09-21T01:00:00Z" in msg
    assert "REWORK-BUILD | x" in msg
    assert "--supersede" in msg


def test_check_overwrite_two_existing_no_supersede_names_count_and_most_recent():
    """The most recent entry is deliberately NOT first. GitHub returns
    statuses newest-first, so a fixture in that order cannot tell "picks the
    most recent by created_at" from "picks position 0" — an earlier draft of
    this test put the newest first while its docstring said out of order, and
    a mutation to `existing[0]` left it green."""
    existing = [
        {"state": "failure", "description": "REWORK-BUILD | oldest",
         "created_at": "2026-09-21T01:00:00Z"},
        {"state": "success", "description": "PASS | newest",
         "created_at": "2026-09-21T02:00:00Z"},
    ]
    ok, msg = check_overwrite(existing, None)
    assert ok is False
    assert "2" in msg
    assert "PASS | newest" in msg
    assert "2026-09-21T02:00:00Z" in msg
    assert "REWORK-BUILD | oldest" not in msg


def test_check_overwrite_blank_supersede_is_refused_regardless_of_existing():
    ok, msg = check_overwrite(
        [{"state": "success", "description": "PASS", "created_at": "2026-09-21T01:00:00Z"}],
        "   ",
    )
    assert ok is False
    assert "reason" in msg


def test_check_overwrite_existing_with_reason_is_ok():
    """INNOCENCE: existing status + a real reason is allowed to overwrite."""
    ok, msg = check_overwrite(
        [{"state": "success", "description": "PASS", "created_at": "2026-09-21T01:00:00Z"}],
        "gate re-run after rebase",
    )
    assert ok is True
    assert msg == ""


# --- overwrite guard: build_description carries supersedes -----------------

def test_description_carries_supersedes_before_extra():
    desc = build_description(
        "PASS", degraded=False, extra="tail text", conditions_ref=None,
        supersedes="failure@2026-09-21T01:00:00Z: gate re-run after rebase",
    )
    assert "supersedes=failure@2026-09-21T01:00:00Z: gate re-run after rebase" in desc
    assert desc.index("supersedes=") < desc.index("tail text")


def test_description_supersedes_truncates_at_140_and_eats_extra_first():
    desc = build_description(
        "PASS", degraded=False, extra="x" * 300, conditions_ref=None,
        supersedes="failure@2026-09-21T01:00:00Z: gate re-run after rebase",
    )
    assert len(desc) <= 140
    assert "supersedes=failure@2026-09-21T01:00:00Z" in desc


# --- overwrite guard: main() wiring ------------------------------------------

_EXISTING_REWORK = [{
    "state": "failure",
    "description": "REWORK-BUILD | plan sound, implementation defective",
    "created_at": "2026-09-21T01:00:00Z",
}]


def test_main_refuses_pass_over_existing_rework_without_supersede(monkeypatch):
    """GUILT: the exact PASS-over-REWORK collision this guard exists for —
    must refuse (exit 2) and must NEVER call publish."""
    calls = []
    monkeypatch.setattr("harness_fable_gate.publish", lambda *a, **k: calls.append((a, k)) or 0)
    rc = main(
        ["--verdict", "PASS", "--sha", "abc", "--repo", "acme/example"],
        read_statuses=lambda repo, sha: _EXISTING_REWORK,
    )
    assert rc == 2
    assert calls == []


def test_main_allows_supersede_over_existing_rework(monkeypatch):
    """INNOCENCE: same collision, but --supersede with a reason publishes,
    and the description records what was superseded."""
    calls = []
    monkeypatch.setattr(
        "harness_fable_gate.publish",
        lambda repo, sha, state, description, dry_run: calls.append(description) or 0,
    )
    rc = main(
        ["--verdict", "PASS", "--sha", "abc", "--repo", "acme/example",
         "--supersede", "gate re-run after rebase"],
        read_statuses=lambda repo, sha: _EXISTING_REWORK,
    )
    assert rc == 0
    assert len(calls) == 1
    assert calls[0].startswith("PASS | supersedes=failure@2026-09-21T01:00:00Z: gate re-run after rebase")


def test_main_reader_failure_fails_closed(monkeypatch):
    calls = []
    monkeypatch.setattr("harness_fable_gate.publish", lambda *a, **k: calls.append((a, k)) or 0)
    rc = main(
        ["--verdict", "PASS", "--sha", "abc", "--repo", "acme/example"],
        read_statuses=lambda repo, sha: None,
    )
    assert rc == 1
    assert calls == []


def test_cli_dry_run_skips_overwrite_read_and_prints_notice():
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "harness_fable_gate.py"),
         "--verdict", "PASS", "--sha", "deadbeef", "--repo", "acme/example",
         "--dry-run"],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "overwrite check skipped" in proc.stdout


def test_cli_dry_run_with_supersede_shows_placeholder_shape():
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "harness_fable_gate.py"),
         "--verdict", "PASS", "--sha", "deadbeef", "--repo", "acme/example",
         "--supersede", "gate re-run after rebase", "--dry-run"],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "supersedes=<unread>: gate re-run after rebase" in proc.stdout


def test_main_supersede_names_the_most_recent_status_not_the_first(monkeypatch):
    """The second `max` — the one that writes `supersedes=` on the PR — gets
    the same out-of-order fixture: naming the wrong predecessor on the page
    is the invisible-collision defect again, one level up."""
    calls = []

    def fake_reader(repo, sha):
        return [
            {"state": "failure", "description": "REWORK-BUILD | older",
             "created_at": "2026-09-21T01:00:00Z"},
            {"state": "success", "description": "PASS | newer",
             "created_at": "2026-09-21T03:00:00Z"},
        ]

    def fake_publish(repo, sha, state, description, dry_run):
        calls.append(description)
        return 0

    monkeypatch.setattr("harness_fable_gate.publish", fake_publish)
    rc = main(
        ["--verdict", "BLOCK", "--sha", "abc", "--repo", "acme/example",
         "--supersede", "third reading"],
        read_statuses=fake_reader,
    )
    assert rc == 0
    assert len(calls) == 1
    assert "supersedes=success@2026-09-21T03:00:00Z: third reading" in calls[0]


# --- B25-prime P1: the ledger is appended BEFORE the status is posted -----------------------------------------------------------

def test_main_appends_the_ledger_before_it_posts_and_passes_the_entry_fields(monkeypatch):
    calls = []
    monkeypatch.setattr(harness_fable_gate, "ledger_append", lambda *a: calls.append(("ledger", a)) or 0)
    monkeypatch.setattr(harness_fable_gate, "publish", lambda *a: calls.append(("post", a)) or 0)
    rc = main(["--verdict", "BLOCK", "--sha", HEAD, "--repo", "acme/example", "--pr", "42", "--gate-session", "gate-x",
               "--evidence-sha256", "b" * 64], read_statuses=lambda r, s: [])
    assert rc == 0 and [c[0] for c in calls] == ["ledger", "post"]
    assert calls[0][1] == ("acme/example", HEAD, 42, "failure", "gate-x", "b" * 64, False, False)


def test_a_failed_ledger_append_posts_nothing(monkeypatch):
    posts = []
    monkeypatch.setattr(harness_fable_gate, "ledger_append", lambda *a: 1)
    monkeypatch.setattr(harness_fable_gate, "publish", lambda *a: posts.append(a) or 0)
    assert main(["--verdict", "PASS", "--sha", HEAD, "--repo", "acme/example"], read_statuses=lambda r, s: []) == 1
    assert posts == []


def test_supersede_reaches_the_ledger_append_as_a_flag(monkeypatch):
    seen = []
    monkeypatch.setattr(harness_fable_gate, "ledger_append", lambda *a: seen.append(a[6]) or 0)
    monkeypatch.setattr(harness_fable_gate, "publish", lambda *a: 0)
    prev = [{"state": "failure", "description": "x", "created_at": "2026-09-21T01:00:00Z"}]
    assert main(["--verdict", "PASS", "--sha", HEAD, "--repo", "a/b", "--supersede", "why"], read_statuses=lambda r, s: prev) == 0
    assert main(["--verdict", "PASS", "--sha", HEAD, "--repo", "a/b"], read_statuses=lambda r, s: []) == 0
    assert seen == [True, False]


def test_dry_run_shows_the_ledger_command_before_the_post_and_runs_nothing():
    proc = subprocess.run([sys.executable, str(SCRIPTS / "harness_fable_gate.py"), "--verdict", "PASS", "--sha", "deadbeef",
                           "--repo", "acme/example", "--dry-run"], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0 and "DRY-RUN: ledger append would run:" in proc.stdout and "gate-append <entry-b64>" in proc.stdout
    assert proc.stdout.index("ledger append") < proc.stdout.index("statuses/deadbeef")


def test_the_ledger_command_is_ssh_pro_elsewhere_and_the_wrapper_itself_on_pro(monkeypatch):
    monkeypatch.setattr(harness_fable_gate.os, "uname", lambda: type("U", (), {"nodename": "Air-M5.local"})())
    assert ledger_command("QUJD", True) == ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "pro",
                                            "bash ~/.nuzantara-cron/localci_merger_tick.sh gate-append QUJD --supersede"]
    monkeypatch.setattr(harness_fable_gate.os, "uname", lambda: type("U", (), {"nodename": "Nuzantara.local"})())
    cmd = ledger_command("QUJD", False)
    assert cmd[0] == "/bin/bash" and cmd[1].endswith("/.nuzantara-cron/localci_merger_tick.sh") and cmd[2:] == ["gate-append", "QUJD"]


def entry_of(cmd):
    words = " ".join(cmd).split()
    return json.loads(base64.b64decode(words[words.index("gate-append") + 1]))


def test_ledger_append_sends_exactly_the_seven_keys_as_one_base64_argv(monkeypatch):
    got = {}

    def fake_run(cmd, **kw):
        got["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="d" * 64 + "\n", stderr="")

    monkeypatch.setattr(harness_fable_gate.subprocess, "run", fake_run)
    assert ledger_append("acme/example", HEAD, 42, "success", "s" * 100, None, False, False) == 0
    assert entry_of(got["cmd"]) == {"repo": "acme/example", "pr": 42, "head_sha": HEAD, "verdict": "success", "gate_session": "s" * 80,
                     "evidence_sha256": None, "supersedes": None}


@pytest.mark.parametrize("sha,pr", [("deadbeef", 1), (HEAD.upper(), 1), (HEAD, None)], ids=["short", "upper", "no-pr"])
def test_ledger_append_refuses_a_bad_sha_and_an_unresolvable_pr_without_running_anything(monkeypatch, sha, pr):
    monkeypatch.setattr(harness_fable_gate.subprocess, "run", lambda *a, **k: pytest.fail("ran a process"))
    monkeypatch.setattr(harness_fable_gate, "derive_pr", lambda repo, s: None)
    assert ledger_append("acme/example", sha, pr, "success", "g", None, False, False) == 1


def test_ledger_append_reads_the_pr_from_github_when_none_is_given_and_reports_a_failed_append(monkeypatch):
    monkeypatch.setattr(harness_fable_gate, "derive_pr", lambda repo, s: 99)
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 3, stdout="", stderr="no mirror")

    monkeypatch.setattr(harness_fable_gate.subprocess, "run", fake_run)
    assert ledger_append("acme/example", HEAD, None, "failure", "g", None, False, False) == 1
    assert entry_of(calls[0])["pr"] == 99
    monkeypatch.setattr(harness_fable_gate.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(subprocess.TimeoutExpired("ssh", 60)))
    assert ledger_append("acme/example", HEAD, 5, "failure", "g", None, False, False) == 1


def test_the_publisher_and_the_ledger_module_agree_end_to_end(monkeypatch, tmp_path):
    """The entry the publisher builds is one the appender accepts, and the reader then confers OK (writer and reader, one rule)."""
    sys.path.insert(0, str(SCRIPTS / "localci"))
    import gate_ledger
    ledger = str(tmp_path / "d" / "verdicts.jsonl")
    monkeypatch.setattr(harness_fable_gate, "ledger_command", lambda b64, sup: [
        sys.executable, "-I", str(SCRIPTS / "localci" / "gate_ledger.py"), "--ledger", ledger, "append", b64] + (["--supersede"] if sup else []))
    assert ledger_append("Bali-Zero/Teman2", HEAD, 12, "failure", "g", None, False, False) == 0
    assert gate_ledger.gate_verdict(ledger, "Bali-Zero/Teman2", HEAD)[0] is False
    assert ledger_append("Bali-Zero/Teman2", HEAD, 12, "success", "g", "c" * 64, True, False) == 0
    assert gate_ledger.gate_verdict(ledger, "Bali-Zero/Teman2", HEAD)[0] is True
