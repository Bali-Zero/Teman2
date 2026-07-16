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

3. TestSameTickRecoveryResolution — W89 class-audit (2026-07-16): the
   corpse-sweep fix in #2 covered only 1-of-4 job-recovery paths.
   process_entry()'s Tier 1 (retried_ok), Tier 2 (aider_fixed), and Tier 2.5
   (codex_fixed) returns are jobs healed WITHIN this tick — they never touch
   sweep_recovered_corpses() at all, since they never even entered the DLQ
   loop as "still broken". _resolve_job_escalation() (a single-job wrapper
   around _resolve_swept_escalations) is now called at all three return
   points. Guilt: each of the three paths resolves a pending escalation.
   Innocence: a job that still fails (falls through to Tier 3 escalate)
   never calls mark_resolved.

4. TestCodexFixedDlqRemoval — W89 class-audit, second finding (2026-07-16):
   run_autopilot()'s DLQ-removal tuple listed ("retried_ok", "aider_fixed",
   "archived") but NOT "codex_fixed" — a codex-fixed job stayed in the DLQ
   and got autopilot_attempts incremented every tick instead of being
   removed, eventually reaching a false TERMINAL despite having already been
   fixed. Board-honesty (the escalation resolution) was unaffected — this is
   the DLQ-entry-on-disk half of the same bug.

Run:
    cd ~/nuzantara/.worktrees/ops-board-honesty
    source apps/backend-rag/.venv/bin/activate
    python -m pytest scripts/tests/test_dlq_board_honesty.py -v
"""
import importlib.util
import json
import sys
import time
import types
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


class TestSameTickRecoveryResolution:
    """W89 class-audit — see module docstring #3. Same helper, three more
    call sites: a job healed in THIS tick (never entered the DLQ as
    'still broken') needed its own resolution call, distinct from the
    corpse-sweep path in TestResolveSweptEscalations."""

    def test_guilt_retried_ok_resolves_escalation(self, dlq, monkeypatch):
        d = dlq
        monkeypatch.setattr(
            d, "claude_reason",
            lambda entry: {
                "fix_type": "restart", "fix_instruction": "restart the service",
                "confidence": 0.99, "needs_code_change": False,
                "llm_suggested_only": True,
            },
        )
        resolved_jobs = []
        monkeypatch.setattr(
            d, "_mark_resolved", lambda job: (resolved_jobs.append(job), 1)[1]
        )

        entry = _entry("fly_backup", "connection refused talking to fly api endpoint", {})
        registry = {"fly_backup": {"restart_cmd": "true"}}  # real no-op success command

        action = d.process_entry(entry, registry)

        assert action == "retried_ok"
        assert resolved_jobs == ["fly_backup"]

    def test_guilt_aider_fixed_resolves_escalation(self, dlq, monkeypatch, tmp_path):
        d = dlq
        monkeypatch.setattr(
            d, "claude_reason",
            lambda entry: {
                "fix_type": "code", "fix_instruction": "patch the retry loop",
                "confidence": 0.95, "needs_code_change": True,
                "llm_suggested_only": True,
            },
        )
        monkeypatch.setattr(
            d, "dispatch_aider", lambda entry, reasoning, registry: (True, "applied")
        )
        monkeypatch.setattr(d, "verify_fix", lambda test_cmd: (True, ""))
        resolved_jobs = []
        monkeypatch.setattr(
            d, "_mark_resolved", lambda job: (resolved_jobs.append(job), 1)[1]
        )

        real_file = tmp_path / "some_service.py"
        real_file.write_text("# placeholder\n")

        entry = _entry("some_job", "TypeError in handler at line 42, traceback follows", {})
        entry["files_implicated"] = [str(real_file)]
        registry = {"some_job": {"test_cmd": "true"}}

        action = d.process_entry(entry, registry)

        assert action == "aider_fixed"
        assert resolved_jobs == ["some_job"]

    def test_guilt_codex_fixed_resolves_escalation(self, dlq, monkeypatch, tmp_path):
        """Tier 2.5 (codex_fixed) — extended past the two paths literally
        named in the mandate: it is the third instance of the SAME class
        (job healed within this tick), so leaving it uncured would repeat
        the exact 1-of-N mistake this audit exists to close. dispatch_codex_fix
        is imported lazily inside process_entry (`from sentinel_lib.repairer
        import dispatch_codex_fix`), so it's faked via sys.modules rather than
        monkeypatch.setattr on the dlq module."""
        d = dlq
        monkeypatch.setattr(
            d, "claude_reason",
            lambda entry: {
                "fix_type": "code", "fix_instruction": "patch the retry loop",
                "confidence": 0.95, "needs_code_change": True,
                "llm_suggested_only": True,
            },
        )
        monkeypatch.setattr(
            d, "dispatch_aider", lambda entry, reasoning, registry: (False, "aider failed")
        )
        monkeypatch.setattr(d, "verify_fix", lambda test_cmd: (True, ""))

        fake_repairer = types.ModuleType("sentinel_lib.repairer")
        fake_repairer.dispatch_codex_fix = lambda **kwargs: (True, "codex applied")
        monkeypatch.setitem(sys.modules, "sentinel_lib.repairer", fake_repairer)

        resolved_jobs = []
        monkeypatch.setattr(
            d, "_mark_resolved", lambda job: (resolved_jobs.append(job), 1)[1]
        )

        real_file = tmp_path / "some_service.py"
        real_file.write_text("# placeholder\n")

        entry = _entry("some_job", "TypeError in handler at line 42, traceback follows", {})
        entry["files_implicated"] = [str(real_file)]
        registry = {"some_job": {"test_cmd": "true"}}

        action = d.process_entry(entry, registry)

        assert action == "codex_fixed"
        assert resolved_jobs == ["some_job"]

    def test_innocence_still_failing_job_never_resolves(self, dlq, monkeypatch):
        """A job that falls through to Tier 3 (escalate) must NEVER call
        mark_resolved — it hasn't recovered, the board must keep it pending."""
        d = dlq
        monkeypatch.setattr(
            d, "claude_reason",
            lambda entry: {
                "fix_type": "unknown", "fix_instruction": "needs manual triage",
                "confidence": 0.3, "needs_code_change": False,
                "llm_suggested_only": True,
            },
        )
        monkeypatch.setattr(d, "escalate_to_claude_code", lambda *a, **k: None)
        resolved_jobs = []
        monkeypatch.setattr(
            d, "_mark_resolved", lambda job: (resolved_jobs.append(job), 1)[1]
        )

        entry = _entry("still_broken_job", "connection refused talking to some endpoint", {})
        action = d.process_entry(entry, {})

        assert action == "escalated"
        assert resolved_jobs == [], "a still-failing job must never resolve its own escalation"


class TestCodexFixedDlqRemoval:
    """W89 class-audit, second finding — see module docstring #4. Drives the
    real run_autopilot() end-to-end (real lock/DLQ-file/state-file I/O under
    a tmp HOME, only process_entry() itself is mocked) so the assertion is
    about actual on-disk DLQ state, not just the in-memory disposition
    branch."""

    def test_guilt_codex_fixed_entry_removed_from_dlq(self, dlq, monkeypatch):
        d = dlq
        d.AGENT_DIR.mkdir(parents=True, exist_ok=True)
        d.DLQ_FILE.write_text(json.dumps({"queue": [
            {
                "job": "some_job",
                "error_summary": "boom, something broke",
                "classification": {},
                "autopilot_attempts": 0,
                "files_implicated": [],
                "added_ts": time.time(),
            },
        ]}))

        monkeypatch.setattr(d, "process_entry", lambda entry, registry: "codex_fixed")

        d.run_autopilot()

        saved = json.loads(d.DLQ_FILE.read_text())
        assert saved["queue"] == [], (
            "a codex_fixed job must be removed from the DLQ like retried_ok/"
            "aider_fixed, not left to increment autopilot_attempts toward a "
            "false TERMINAL"
        )

        state = json.loads((d.AGENT_DIR / "state" / "dlq_autopilot.last.json").read_text())
        assert "fixed=1" in state["detail"], (
            "the run summary's `fixed` counter must count codex_fixed too, "
            "not just retried_ok/aider_fixed (same 1-of-N tuple gap)"
        )
