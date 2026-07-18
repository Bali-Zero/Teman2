"""Guilt+innocence tests for the WR2 daily reconciler decision core.

Spec: docs/specs/wr2-definitiva-v1.md §1.C — "one carousel per day, or a P0
that says why". `decide()` is pure (no DB, no launchctl) by construction.
"""
from __future__ import annotations

import importlib.util
import asyncio
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _load(name: str) -> ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / f"{name}.py")
    assert spec and spec.loader, f"cannot load {name}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


rec = _load("wr2_daily_reconciler")

WITA = rec.WITA
NOON = datetime(2026, 7, 7, 12, 0, tzinfo=WITA)
EVENING = datetime(2026, 7, 7, 18, 0, tzinfo=WITA)


def _row(status: str, *, attempts: int = 0, updated_min_ago: int = 10, now=NOON) -> dict:
    return {
        "id": uuid.uuid4(),
        "status": status,
        "attempts": attempts,
        "updated_at": (now - timedelta(minutes=updated_min_ago)).astimezone(timezone.utc),
        "topic": "test topic",
    }


# ── innocence: healthy day → ok, no meddling ─────────────────────────────────────
def test_rendered_today_is_ok():
    d = rec.decide([_row("rendered")], NOON)
    assert d.action == "ok" and not d.escalate


def test_rendered_wins_over_dead_siblings():
    rows = [_row("render_failed", attempts=3), _row("rendered"), _row("missed")]
    assert rec.decide(rows, NOON).action == "ok"


def test_inflight_fresh_waits():
    d = rec.decide([_row("rendering", updated_min_ago=20)], NOON)
    assert d.action == "wait" and not d.escalate


# ── guilt: broken day → corrective action ────────────────────────────────────────
def test_empty_day_picks_new_topic():
    d = rec.decide([], NOON)
    assert d.action == "new_topic" and not d.escalate


def test_empty_day_late_escalates():
    d = rec.decide([], EVENING)
    assert d.action == "new_topic" and d.escalate


def test_render_failed_with_attempts_left_requeues():
    d = rec.decide([_row("render_failed", attempts=1)], NOON)
    assert d.action == "requeue_render_failed" and d.draft_id


def test_render_failed_exhausted_goes_new_topic():
    d = rec.decide([_row("render_failed", attempts=3)], NOON)
    assert d.action == "new_topic"


def test_stuck_inflight_kicks():
    d = rec.decide([_row("drafts_imaged", updated_min_ago=200)], NOON)
    assert d.action == "kick_stuck"


def test_shadow_render_does_not_count_as_ok():
    d = rec.decide([_row("rendered_shadow")], NOON)
    assert d.action == "new_topic"


def test_rejected_only_goes_new_topic_and_escalates_late():
    d = rec.decide([_row("rejected")], EVENING)
    assert d.action == "new_topic" and d.escalate


def test_late_inflight_still_waits_without_escalation():
    d = rec.decide([_row("rendering", updated_min_ago=5, now=EVENING)], EVENING)
    assert d.action == "wait" and not d.escalate


def test_tick_wait_writes_running_heartbeat_without_p0(monkeypatch):
    class FakeConn:
        async def fetch(self, *_args, **_kwargs):
            return [_row("drafts_imaged_checked", updated_min_ago=5, now=EVENING)]

    heartbeats = []
    notifications = []
    monkeypatch.setattr(rec, "_heartbeat", lambda status, note: heartbeats.append((status, note)))
    monkeypatch.setattr(
        rec,
        "_tg_notify",
        lambda tier, dedup_key, text: notifications.append((tier, dedup_key, text)) or True,
    )

    rc = asyncio.run(
        rec._tick(
            FakeConn(),
            EVENING,
            EVENING.astimezone(timezone.utc),
            dry_run=False,
            escalate_hour=17,
            stuck_hours=2,
            max_attempts=3,
        )
    )

    assert rc == 0
    assert len(heartbeats) == 1
    assert heartbeats[0][0] == "running"
    assert heartbeats[0][1].startswith("wait: draft ")
    assert notifications == []


# ── visibility verify/backfill (Codex red-team #1/#15: status='rendered' is a proxy) ──
def _rendered_row(draft_id: str) -> dict:
    return {
        "id": draft_id, "status": "rendered", "attempts": 0,
        "updated_at": NOON.astimezone(timezone.utc),
        "topic": "Verified Topic", "drive_url": "https://drive/z",
    }


def test_visibility_verified_when_queue_has_entry(tmp_path, monkeypatch):
    import json
    monkeypatch.setenv("WR2_OUTPUT_ROOT", str(tmp_path))
    qp = tmp_path / "queue" / "human-review-queue.json"
    qp.parent.mkdir(parents=True)
    qp.write_text(json.dumps([{"id": "x", "draft_id": "d-verified"}]))
    assert rec._verify_visibility_or_backfill(_rendered_row("d-verified"), dry_run=False) == "verified"


def test_visibility_backfill_without_intended_count_is_incomplete_not_drafted(tmp_path, monkeypatch):
    """Codex red-team HIGH #2: `_rendered_row` carries no `slides_json` (legacy/
    unresolvable DB row) — intended is genuinely unknown. A lone PNG on disk must
    NOT be trusted as "the whole carousel"; the entry is backfilled as
    render_incomplete, never as a reviewable "drafted"."""
    import json
    monkeypatch.setenv("WR2_OUTPUT_ROOT", str(tmp_path))
    draft_id = "abcd1234-9999-0000-0000-000000000000"
    slides = tmp_path / "carousel" / "2026-07-07-verified-topic-abcd1234" / "slides"
    slides.mkdir(parents=True)
    (slides / "01.png").write_bytes(b"png")
    out = rec._verify_visibility_or_backfill(_rendered_row(draft_id), dry_run=False)
    assert out == "backfilled_incomplete"
    queue = json.loads((tmp_path / "queue" / "human-review-queue.json").read_text())
    assert queue[0]["draft_id"] == draft_id
    assert queue[0]["slides_dir"].endswith("slides")
    assert queue[0]["drive_url"] == "https://drive/z"
    assert queue[0]["state"] == rec.RENDER_INCOMPLETE_STATE


def test_visibility_backfill_honest_without_local_slides(tmp_path, monkeypatch):
    import json
    monkeypatch.setenv("WR2_OUTPUT_ROOT", str(tmp_path))
    out = rec._verify_visibility_or_backfill(_rendered_row("feed0000-1111"), dry_run=False)
    assert out == "backfilled_incomplete"
    queue = json.loads((tmp_path / "queue" / "human-review-queue.json").read_text())
    assert queue[0]["slides_dir"] is None
    assert "Drive" in queue[0]["critic_summary"]
    assert queue[0]["state"] == rec.RENDER_INCOMPLETE_STATE


def test_visibility_backfill_marks_drafted_when_disk_matches_intended(tmp_path, monkeypatch):
    """Complement: when the DB row DOES carry slides_json and disk matches it
    exactly, the backfill still produces a genuinely reviewable "drafted" entry
    (not every backfill degrades to render_incomplete — only unverifiable ones)."""
    import json
    monkeypatch.setenv("WR2_OUTPUT_ROOT", str(tmp_path))
    draft_id = "1111aaaa-2222-0000-0000-000000000000"
    slides = tmp_path / "carousel" / "2026-07-07-verified-topic-1111aaaa" / "slides"
    slides.mkdir(parents=True)
    (slides / "01.png").write_bytes(b"png")
    row = dict(_rendered_row(draft_id), slides_json=json.dumps({"slides": [{"n": 1}]}))
    out = rec._verify_visibility_or_backfill(row, dry_run=False)
    assert out == "backfilled"
    queue = json.loads((tmp_path / "queue" / "human-review-queue.json").read_text())
    assert queue[0]["draft_id"] == draft_id
    assert queue[0]["state"] != rec.RENDER_INCOMPLETE_STATE


def test_visibility_dry_run_touches_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("WR2_OUTPUT_ROOT", str(tmp_path))
    assert rec._verify_visibility_or_backfill(_rendered_row("d-dry"), dry_run=True) == "dry_run"
    assert not (tmp_path / "queue" / "human-review-queue.json").exists()


# ── --rebrief one-shot CLI dispatch (B5 remake-hygiene verb + Codex red-team round) ──


def _write_rebrief_queue(tmp_path, entries):
    """W96: NEVER touch the real prod queue — every test below sets
    WR2_OUTPUT_ROOT to tmp_path first, mirroring the existing
    test_visibility_* convention in this file."""
    import json

    qp = tmp_path / "queue" / "human-review-queue.json"
    qp.parent.mkdir(parents=True, exist_ok=True)
    qp.write_text(json.dumps(entries))
    return qp


# ── _rebrief_queue_guard (FIX 1 BLOCKER) ──────────────────────────────────────


def test_queue_guard_refuses_published(tmp_path, monkeypatch):
    """A draft already 'published' in the review queue must be refused — Damar's
    mark_published writes ONLY the queue JSON, never war_room_drafts.status, so
    a DB-only whitelist can't see this on its own."""
    monkeypatch.setenv("WR2_OUTPUT_ROOT", str(tmp_path))
    _write_rebrief_queue(tmp_path, [{"draft_id": "pub-1", "state": "published"}])
    ok, reason = rec._rebrief_queue_guard("pub-1")
    assert ok is False
    assert "published" in reason


def test_queue_guard_allows_rejected(tmp_path, monkeypatch):
    """A 'rejected' queue entry is a legitimate operator-remake target — same
    doctrine as the sibling wr2_rerender_requeue.py verb (_PREPUBLISH_STATES
    includes 'rejected')."""
    monkeypatch.setenv("WR2_OUTPUT_ROOT", str(tmp_path))
    _write_rebrief_queue(tmp_path, [{"draft_id": "rej-1", "state": "rejected"}])
    ok, _reason = rec._rebrief_queue_guard("rej-1")
    assert ok is True


def test_queue_guard_allows_drafted(tmp_path, monkeypatch):
    monkeypatch.setenv("WR2_OUTPUT_ROOT", str(tmp_path))
    _write_rebrief_queue(tmp_path, [{"draft_id": "dft-1", "state": "drafted"}])
    ok, _reason = rec._rebrief_queue_guard("dft-1")
    assert ok is True


def test_queue_guard_allows_absent_entry(tmp_path, monkeypatch):
    """No queue entry for THIS draft at all (a different id is published) —
    absence is normal (pre-queue-era draft); proceed on DB state only."""
    monkeypatch.setenv("WR2_OUTPUT_ROOT", str(tmp_path))
    _write_rebrief_queue(tmp_path, [{"draft_id": "other", "state": "published"}])
    ok, _reason = rec._rebrief_queue_guard("missing-id")
    assert ok is True


# ── _cmd_rebrief live path (queue guard wired in front of the mutation) ──────


def test_cmd_rebrief_live_refuses_published_without_touching_db(tmp_path, monkeypatch):
    """FIX 1 BLOCKER: the live path must refuse BEFORE calling _rebrief_async
    at all when the queue says published — never even attempts the mutation."""
    monkeypatch.setenv("WR2_OUTPUT_ROOT", str(tmp_path))
    _write_rebrief_queue(tmp_path, [{"draft_id": "pub-2", "state": "published"}])

    async def _boom(_draft_id):
        raise AssertionError("must not call _rebrief_async on a published queue entry")

    monkeypatch.setattr(rec, "_rebrief_async", _boom)
    assert rec._cmd_rebrief("pub-2", dry_run=False) == 1


def test_cmd_rebrief_live_proceeds_when_rejected_in_queue(tmp_path, monkeypatch):
    monkeypatch.setenv("WR2_OUTPUT_ROOT", str(tmp_path))
    _write_rebrief_queue(tmp_path, [{"draft_id": "rej-2", "state": "rejected"}])

    async def _fake(draft_id):
        assert draft_id == "rej-2"
        return True

    monkeypatch.setattr(rec, "_rebrief_async", _fake)
    assert rec._cmd_rebrief("rej-2", dry_run=False) == 0


def test_cmd_rebrief_success_returns_zero(tmp_path, monkeypatch):
    monkeypatch.setenv("WR2_OUTPUT_ROOT", str(tmp_path))  # empty queue dir -> guard fail-open

    async def _fake(draft_id):
        assert draft_id == "abc-123"
        return True

    monkeypatch.setattr(rec, "_rebrief_async", _fake)
    assert rec._cmd_rebrief("abc-123", dry_run=False) == 0


def test_cmd_rebrief_refused_returns_one(tmp_path, monkeypatch):
    """INNOCENCE (leased/wrong-status/not-found, per rebrief_draft's False path)
    surfaces as exit 1 — distinct from a connection/env failure (exit 2)."""
    monkeypatch.setenv("WR2_OUTPUT_ROOT", str(tmp_path))

    async def _fake(_draft_id):
        return False

    monkeypatch.setattr(rec, "_rebrief_async", _fake)
    assert rec._cmd_rebrief("abc-123", dry_run=False) == 1


def test_cmd_rebrief_connection_failure_returns_two(tmp_path, monkeypatch):
    monkeypatch.setenv("WR2_OUTPUT_ROOT", str(tmp_path))

    async def _fake(_draft_id):
        raise RuntimeError("DATABASE_URL not set")

    monkeypatch.setattr(rec, "_rebrief_async", _fake)
    assert rec._cmd_rebrief("abc-123", dry_run=False) == 2


# ── _rebrief_dry_run_message classifier (FIX 3 honest preview) ───────────────


def test_rebrief_dry_run_message_not_found():
    msg = rec._rebrief_dry_run_message(None, ok_queue=True, queue_reason="no queue entry for draft")
    assert msg == "would NO-OP (reason: not found)"


def test_rebrief_dry_run_message_leased():
    row = {"status": "rendering", "lease_owner": "pid@host"}
    msg = rec._rebrief_dry_run_message(row, ok_queue=True, queue_reason="no queue entry for draft")
    assert msg == "would NO-OP (reason: leased by pid@host)"


def test_rebrief_dry_run_message_published_in_queue():
    """A DB-eligible row (status='rendered', unleased) must still be reported
    NO-OP when the queue says published — the queue guard outranks the DB
    whitelist in the truthful message, matching the live-path refusal."""
    row = {"status": "rendered", "lease_owner": None}
    msg = rec._rebrief_dry_run_message(row, ok_queue=False, queue_reason="queue entry state=published")
    assert "would NO-OP" in msg
    assert "published" in msg


def test_rebrief_dry_run_message_wrong_status():
    row = {"status": "briefed", "lease_owner": None}
    msg = rec._rebrief_dry_run_message(row, ok_queue=True, queue_reason="no queue entry for draft")
    assert msg == "would NO-OP (reason: status=briefed not rebrief-eligible)"


def test_rebrief_dry_run_message_eligible():
    row = {"status": "rendered", "lease_owner": None}
    msg = rec._rebrief_dry_run_message(row, ok_queue=True, queue_reason="no queue entry for draft")
    assert msg == "would REBRIEF (status=rendered, unleased, queue=no queue entry for draft)"


# ── _cmd_rebrief dry-run wiring (never mutates, honest failure mode) ─────────


def test_cmd_rebrief_dry_run_never_mutates(tmp_path, monkeypatch):
    """FIX 3: dry-run must never call the mutating _rebrief_async, regardless
    of what the preview concludes."""
    monkeypatch.setenv("WR2_OUTPUT_ROOT", str(tmp_path))

    async def _boom(_draft_id):
        raise AssertionError("dry-run must not call _rebrief_async")

    async def _preview(_draft_id):
        return {"status": "rendered", "lease_owner": None}

    monkeypatch.setattr(rec, "_rebrief_async", _boom)
    monkeypatch.setattr(rec, "_rebrief_preview_async", _preview)
    assert rec._cmd_rebrief("elig-1", dry_run=True) == 0


def test_cmd_rebrief_dry_run_connection_failure_returns_two(tmp_path, monkeypatch):
    """DEVIATION from "exit 0 either way": a preview that could NOT run at all
    (DB unreachable) is an infra failure, not a truthful verdict — returns 2,
    same code as the live path's connection failure."""
    monkeypatch.setenv("WR2_OUTPUT_ROOT", str(tmp_path))

    async def _preview(_draft_id):
        raise RuntimeError("DATABASE_URL not set")

    monkeypatch.setattr(rec, "_rebrief_preview_async", _preview)
    assert rec._cmd_rebrief("abc-123", dry_run=True) == 2


def test_cmd_rebrief_dry_run_reflects_published_queue(tmp_path, monkeypatch, caplog):
    """Integration: a published queue entry must surface in the dry-run LOGGED
    message even though the DB row alone looks eligible (status='rendered',
    unleased) — the honest preview cannot say "would REBRIEF" for a draft the
    live path would actually refuse."""
    monkeypatch.setenv("WR2_OUTPUT_ROOT", str(tmp_path))
    _write_rebrief_queue(tmp_path, [{"draft_id": "pub-3", "state": "published"}])

    async def _preview(_draft_id):
        return {"status": "rendered", "lease_owner": None}

    monkeypatch.setattr(rec, "_rebrief_preview_async", _preview)
    caplog.set_level("INFO")
    assert rec._cmd_rebrief("pub-3", dry_run=True) == 0
    assert "NO-OP" in caplog.text
    assert "published" in caplog.text


def test_main_dispatches_rebrief_before_normal_tick(monkeypatch):
    """--rebrief must short-circuit main() before the normal decide()/run() tick —
    same dispatch shape as --repair-false-incomplete / --backfill-completeness."""
    calls = []
    monkeypatch.setattr(
        rec,
        "_cmd_rebrief",
        lambda draft_id, *, dry_run: calls.append((draft_id, dry_run)) or 0,
    )
    monkeypatch.setattr(sys, "argv", ["wr2_daily_reconciler.py", "--rebrief", "abc-123"])
    assert rec.main() == 0
    assert calls == [("abc-123", False)]
