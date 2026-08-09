"""One event must not offer two p0 alerts (2026-08-09).

TRAUMA, measured on the live spool (~/.organism/tg_spool on Pro, 2026-08-08):
eleven jobs reached TERMINAL in one night — seven NotebookLM pipelines inside a
31-minute window, plus nightly_autofix_ci, nb_agents_daily_dr, dropbox_intake and
run_gap_scanner_layer_a — and they offered **22 p0 records: eleven identical
pairs**, one `dlq-escalation:<job>` and one `dlq-terminal:<job>` per job, at the
same second, both saying "this is stuck, a human must act". dlq-autopilot was the
day's loudest producer (24 of the day's 69 offered records) and 22 of its 24 were
that doubling.

Both halves carried something the other did not — the escalation names the
claude_tasks file, the terminal line names the recovery command — so the cure is
ONE message carrying both facts, never dropping one. `escalate_to_claude_code`
gained `notify=False` (it still writes the task file, the federation JSONL and
the cooldown mark) and now returns the file name so the TERMINAL branch can name
it.

These assert on what reaches `send_telegram`, because that is the only surface
the operator ever sees: asserting on a helper would prove the helper, not that
the branch speaks once.
"""
import importlib.util
import json
import os
import sys
import time

import pytest

_SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture()
def dlq(tmp_path, monkeypatch):
    """Load dlq_autopilot.py fresh with HOME redirected to a tmp dir."""
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
    if _SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, _SCRIPTS_DIR)
    spec = importlib.util.spec_from_file_location(
        "dlq_autopilot_one_voice", os.path.join(_SCRIPTS_DIR, "dlq_autopilot.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def sent(dlq, monkeypatch):
    """Capture every gateway call as (text, tier, dedup_key)."""
    calls: list[tuple[str, str, str]] = []

    def _capture(message, tier="digest", dedup_key=""):
        calls.append((message, tier, dedup_key))

    monkeypatch.setattr(dlq, "send_telegram", _capture)
    # Never touch the real federation bus or cooldown state from a test.
    monkeypatch.setattr(dlq, "_write_escalation", lambda *a, **k: None)
    monkeypatch.setattr(dlq, "_mark_escalation_sent", lambda *a, **k: None)
    monkeypatch.setattr(dlq, "_check_escalation_cooldown", lambda *a, **k: False)
    monkeypatch.setattr(dlq, "load_registry", lambda: {})
    return calls


def _registry(job="run_nb7_pipeline"):
    """process_entry reads max_attempts from registry[job], not from the top level."""
    return {job: {"max_attempts": 3}}


def _entry(job="run_nb7_pipeline", attempts=3, error="boom, and then boom again"):
    return {
        "job": job,
        "error_summary": error,
        "log_tail": "…",
        "autopilot_attempts": attempts,
        "added_ts": time.time(),
        "classification": {"type": "DETERMINISTIC", "confidence": 0.9},
    }


# ── guilt ────────────────────────────────────────────────────────────────────

def test_a_terminal_job_offers_exactly_one_p0(dlq, sent):
    assert dlq.process_entry(_entry(), _registry()) == "terminal"
    p0 = [c for c in sent if c[1] == "p0"]
    assert len(p0) == 1, f"one event, {len(p0)} p0 alerts: {[c[2] for c in p0]}"
    assert p0[0][2] == "dlq-terminal:run_nb7_pipeline"


def test_the_one_message_still_names_the_task_file_and_the_recovery_command(dlq, sent):
    dlq.process_entry(_entry(), _registry())
    text = sent[0][0]
    assert "run_nb7_pipeline_" in text and ".json" in text, (
        "the task file name was the escalation half's only unique fact — "
        f"suppressing that half must not lose it: {text!r}"
    )
    assert "dlq clear run_nb7_pipeline" in text


def test_the_task_file_is_still_written_when_the_alert_is_suppressed(dlq, sent, tmp_path):
    """notify=False silences the ALERT, never the artifact a human then opens."""
    dlq.process_entry(_entry(), _registry())
    files = list((tmp_path / ".agent" / "decisions" / "claude_tasks").glob("*.json"))
    assert len(files) == 1, files
    payload = json.loads(files[0].read_text())
    assert payload["job"] == "run_nb7_pipeline"


def test_eleven_terminal_jobs_offer_eleven_alerts_not_twentytwo(dlq, sent):
    """The measured night, replayed: 11 jobs, 22 records before, 11 after."""
    jobs = [
        "run_nb3_pipeline", "run_nb4_pipeline", "run_nb5_pipeline",
        "run_nb6_pipeline", "run_nb7_pipeline", "run_nb8_pipeline",
        "run_nb10_pipeline", "nightly_autofix_ci", "nb_agents_daily_dr",
        "dropbox_intake", "run_gap_scanner_layer_a",
    ]
    for job in jobs:
        dlq.process_entry(_entry(job=job), _registry(job))
    p0 = [c for c in sent if c[1] == "p0"]
    assert len(p0) == len(jobs) == 11
    assert len({c[2] for c in p0}) == 11, "one key per job, no collisions"


def test_a_terminal_message_stays_readable_when_no_task_file_was_written(dlq, sent, monkeypatch):
    """An escalation that returns None must not print 'Task file: None'."""
    monkeypatch.setattr(dlq, "escalate_to_claude_code", lambda *a, **k: None)
    dlq.process_entry(_entry(), _registry())
    text = sent[0][0]
    assert "None" not in text
    assert "dlq clear" in text


# ── innocence ────────────────────────────────────────────────────────────────

def test_an_ordinary_escalation_still_sends_its_own_alert(dlq, sent):
    """Only the TERMINAL caller passes notify=False. Everyone else is unchanged."""
    dlq.escalate_to_claude_code(_entry(job="dropbox_intake"), None)
    p0 = [c for c in sent if c[1] == "p0"]
    assert len(p0) == 1
    assert p0[0][2] == "dlq-escalation:dropbox_intake"
    assert "Escalated to Claude Code" in p0[0][0]


def test_escalate_returns_the_task_file_name_for_a_normal_call_too(dlq, sent):
    name = dlq.escalate_to_claude_code(_entry(job="dropbox_intake"), None)
    assert name and name.startswith("dropbox_intake_") and name.endswith(".json")


def test_a_job_on_cooldown_still_returns_none_and_stays_silent(dlq, sent, monkeypatch):
    monkeypatch.setattr(dlq, "_check_escalation_cooldown", lambda *a, **k: True)
    monkeypatch.setattr(dlq, "_record_suppressed", lambda *a, **k: None)
    assert dlq.escalate_to_claude_code(_entry(job="dropbox_intake"), None) is None
    assert sent == []


def test_a_job_below_max_attempts_does_not_reach_the_terminal_branch(dlq, sent):
    """The innocence control for the branch itself: 2 of 3 attempts is not terminal."""
    verdict = dlq.process_entry(_entry(attempts=1), _registry())
    assert verdict != "terminal"
    assert not [c for c in sent if c[2].startswith("dlq-terminal:")]
