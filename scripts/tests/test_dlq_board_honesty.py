"""Board-honesty cures (2026-07-16) — shared/escalations_pro.jsonl is a board,
not a write-only log.

Two independent bugs fixed, two test classes:

1. TestNoiseGate — process_entry()'s classifier-failure branch escalated
   content-free entries (empty error_summary + classifier.py's no_error_text
   short-circuit: type=UNKNOWN, confidence=0.0) every cooldown cycle
   (dropbox_intake: 5+ repeat offenders in the live board). Guard family #3
   (guard-over-match / under-match): the fix must match the FACT (both
   fields), not the subtype substring — other CLASSIFIER_FAILURE_SUBTYPES
   members with a real error must still escalate (guilt), only the exact
   no-signal combo is suppressed (innocence).

2. TestResolveSweptEscalations — sweep_recovered_corpses() drains DLQ entries
   for jobs that proved fresh recovery, but nothing ever flipped the matching
   escalations_pro.jsonl entry from pending -> resolved (mark_resolved was
   defined in sentinel_lib.escalations but never called). _resolve_swept_
   escalations() wires that call in; it must be a no-op (0 written) for jobs
   with no matching pending escalation, and must never let one job's failure
   block the rest.

Run:
    cd ~/nuzantara/.worktrees/ops-board-honesty
    source apps/backend-rag/.venv/bin/activate
    python -m pytest scripts/tests/test_dlq_board_honesty.py -v
"""
import importlib.util
import time
from pathlib import Path

import pytest


@pytest.fixture()
def dlq(tmp_path, monkeypatch):
    """Import THIS worktree's dlq_autopilot.py by explicit path (not sys.path
    — avoids resolving to a sibling checkout, same pattern as
    test_escalations_s3.py), with side-effect dirs redirected into tmp.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
    mod_path = Path(__file__).parent.parent / "dlq_autopilot.py"
    spec = importlib.util.spec_from_file_location("dlq_autopilot_board_honesty", mod_path)
    d = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(d)
    monkeypatch.setattr(d, "CLAUDE_TASKS_DIR", tmp_path / "claude_tasks")
    monkeypatch.setattr(d, "load_registry", lambda: {})
    monkeypatch.setattr(d, "send_telegram", lambda *a, **k: None)
    return d


def _entry(job: str, error: str, classification: dict) -> dict:
    return {
        "job": job,
        "error_summary": error,
        "classification": classification,
        "autopilot_attempts": 0,
        "files_implicated": [],
        # Fresh added_ts: preflight #2 (archive entries >48h old with empty
        # error) must NOT preempt the noise-gate check under test — a stale
        # added_ts (default 0) would misfire that unrelated, earlier check.
        "added_ts": time.time(),
    }


class TestNoiseGate:
    def test_innocence_empty_error_unknown_confidence_suppressed(self, dlq, monkeypatch):
        """The exact classifier.py no_error_text short-circuit: type=UNKNOWN,
        confidence=0.0, subtype='no_error_text' (in CLASSIFIER_FAILURE_SUBTYPES),
        error_summary empty. Must log-only — no board write, no Telegram."""
        d = dlq
        escalated = []
        monkeypatch.setattr(d, "escalate_to_claude_code", lambda *a, **k: escalated.append(a))

        entry = _entry(
            "dropbox_intake", "",
            {"type": "UNKNOWN", "subtype": "no_error_text", "confidence": 0.0},
        )
        action = d.process_entry(entry, {})

        assert action == "skipped_noise"
        assert escalated == [], "noise-gate must NOT call escalate_to_claude_code"

    def test_innocence_whitespace_only_error_suppressed(self, dlq, monkeypatch):
        """error_summary of pure whitespace must be treated as empty (.strip())."""
        d = dlq
        escalated = []
        monkeypatch.setattr(d, "escalate_to_claude_code", lambda *a, **k: escalated.append(a))

        entry = _entry(
            "dropbox_intake", "   \n  ",
            {"type": "UNKNOWN", "subtype": "no_error_text", "confidence": 0.0},
        )
        action = d.process_entry(entry, {})

        assert action == "skipped_noise"
        assert escalated == []

    def test_guilt_real_classifier_failure_with_error_still_escalates(self, dlq, monkeypatch):
        """A CLASSIFIER_FAILURE_SUBTYPES member with an ACTUAL error_summary
        (e.g. no_api_key — the sentinel couldn't reach an LLM, but the DLQ
        entry itself carries real diagnostic text) must still escalate. Only
        the empty-error+UNKNOWN+0.0 combo is noise."""
        d = dlq
        escalated = []
        monkeypatch.setattr(d, "escalate_to_claude_code", lambda *a, **k: escalated.append(a))

        entry = _entry(
            "some_job", "ANTHROPIC_API_KEY not set, cannot classify: connection refused",
            {"type": "UNKNOWN", "subtype": "no_api_key", "confidence": 0.0},
        )
        action = d.process_entry(entry, {})

        assert action == "skipped_preflight"
        assert len(escalated) == 1, "a real classifier failure must still reach the board"

    def test_guilt_unknown_type_but_nonzero_confidence_still_escalates(self, dlq, monkeypatch):
        """Guards against over-match: only confidence==0.0 exactly triggers the
        gate, even with empty error and type=UNKNOWN, matching the FACT not a
        loose heuristic."""
        d = dlq
        escalated = []
        monkeypatch.setattr(d, "escalate_to_claude_code", lambda *a, **k: escalated.append(a))

        entry = _entry(
            "some_job", "",
            {"type": "UNKNOWN", "subtype": "unclassified", "confidence": 0.4},
        )
        action = d.process_entry(entry, {})

        assert action == "skipped_preflight"
        assert len(escalated) == 1


class TestResolveSweptEscalations:
    def test_calls_mark_resolved_per_swept_job(self, dlq, monkeypatch):
        calls = []

        def fake_mark_resolved(job_id: str) -> int:
            calls.append(job_id)
            return 1 if job_id == "job_a" else 0  # job_b has no pending escalation

        monkeypatch.setattr(dlq, "_mark_resolved", fake_mark_resolved)

        resolved_count = dlq._resolve_swept_escalations(["job_a", "job_b"])

        assert calls == ["job_a", "job_b"]
        assert resolved_count == 1, "only jobs mark_resolved actually matched count"

    def test_noop_job_writes_nothing_matches_no_pending(self, dlq, monkeypatch):
        """mark_resolved returning 0 (no matching pending entry) must not be
        double-counted or retried — a healthy no-op."""
        monkeypatch.setattr(dlq, "_mark_resolved", lambda job_id: 0)

        resolved_count = dlq._resolve_swept_escalations(["job_never_escalated"])

        assert resolved_count == 0

    def test_one_job_failing_does_not_block_the_rest(self, dlq, monkeypatch):
        """karpathy zero-collaterali: mark_resolved raising for one job must
        not prevent the sibling jobs' resolutions from landing."""
        calls = []

        def flaky_mark_resolved(job_id: str) -> int:
            calls.append(job_id)
            if job_id == "job_boom":
                raise RuntimeError("simulated write failure")
            return 1

        monkeypatch.setattr(dlq, "_mark_resolved", flaky_mark_resolved)

        resolved_count = dlq._resolve_swept_escalations(["job_ok_1", "job_boom", "job_ok_2"])

        assert calls == ["job_ok_1", "job_boom", "job_ok_2"], "every job must still be attempted"
        assert resolved_count == 2
