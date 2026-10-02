"""Bomb / penalty takeover producer for Round 2 (kita full-screen event)."""

import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest

from backend.services.portal import challenge_events as events
from backend.services.portal import challenge_round2 as r2

UTC = timezone.utc
# Wed 2026-10-07: 09:00 WITA = 01:00 UTC. -3 working hours -> 12:00 WITA = 04:00 UTC.
CREATED = datetime(2026, 10, 7, 1, 0, tzinfo=UTC)
REQUEST_START = datetime(2026, 10, 7, 4, 0, tzinfo=UTC)
# 9.5 working hours end exactly at 18:30 WITA, where nothing has accrued past the limit yet:
# the penalty only counts once the next working day opens (Thu 09:00 WITA = 01:00 UTC).
REVIEW_START = datetime(2026, 10, 8, 1, 0, tzinfo=UTC)
ADIT = "adit@balizero.com"


def _roster(*emails):
    return [
        {
            "email": e,
            "display_name": e.split("@")[0].title(),
            "department": "setup",
            "role": "member",
            "active": True,
            "avatar": None,
        }
        for e in emails
    ]


def _snapshot(now, first_docs=(), requests=(), reviews=(), roster=(ADIT,)):
    return r2.score_round2(
        _roster(*roster), [], [], list(first_docs), list(requests), list(reviews), [], [], now
    )


def _doc(at, practice_id=7, assignee=ADIT):
    return {
        "practice_id": practice_id,
        "first_doc_at": at,
        "practice_assignee": assignee,
        "client_assignee": None,
    }


def _request(row_id=11, assignee=ADIT, client_id=1):
    return {
        "id": row_id,
        "client_id": client_id,
        "practice_id": None,
        "created_at": CREATED,
        "reply_at": None,
        "practice_assignee": assignee,
        "client_assignee": None,
    }


def _review(row_id=5, client_id=2):
    return {
        "id": row_id,
        "practice_id": 3,
        "client_id": client_id,
        "uploaded_at": CREATED,
        "review_at": None,
        "practice_assignee": ADIT,
        "client_assignee": None,
    }


class FakeRedis:
    def __init__(self, lock_free=True):
        self.stream = []
        self.seen = set()
        self.lock_free = lock_free
        self.set_calls = []
        self.deleted = []

    async def delete(self, key):
        self.deleted.append(key)

    async def eval(self, script, numkeys, stream, dedupe_key, payload):
        if dedupe_key in self.seen:
            return None
        self.seen.add(dedupe_key)
        self.stream.append(json.loads(payload))
        return f"{len(self.stream)}-0"

    async def set(self, key, value, nx=False, ex=None):
        self.set_calls.append((key, nx, ex))
        return True if self.lock_free else None


def _patch_snapshot(monkeypatch, snapshot, avatars=None):
    async def fake(pool, now):
        return snapshot, avatars or {}

    monkeypatch.setattr(events, "compute_round2_snapshot", fake)


# ── scorer: internal producer events, public shape untouched ──


def test_scorer_exposes_producer_events_without_changing_scoring_event_shape():
    now = REVIEW_START + timedelta(seconds=5)
    snap = _snapshot(now, [_doc(now - timedelta(seconds=10))], [_request()], [_review()])
    kinds = sorted((e.kind, e.reason) for e in snap.producer_events)
    # client 2's review is a different incident from client 1's request: both count
    assert kinds == [
        ("bomb", None),
        ("penalty", "unanswered_request"),
        ("penalty", "unreviewed_document"),
    ]
    assert set(r2.ScoringEvent.__dataclass_fields__) == {"kind", "display_name", "points", "at"}


def test_penalty_start_is_the_working_deadline_not_the_origin():
    now = REQUEST_START + timedelta(seconds=5)
    snap = _snapshot(now, requests=[_request()])
    (event,) = snap.producer_events
    assert event.at == REQUEST_START and event.points == -2
    assert event.key == "unanswered_request:11"


def test_penalty_start_rolls_to_next_workday_when_the_deadline_is_end_of_day():
    # Fri 15:30 WITA + 3 working hours = 18:30 Fri -> counts from Mon 09:00 WITA.
    origin = datetime(2026, 10, 9, 7, 30, tzinfo=UTC)
    assert r2.penalty_start(origin, 3.0) == datetime(2026, 10, 12, 1, 0, tzinfo=UTC)
    # Mid-day deadline is unchanged.
    assert r2.penalty_start(CREATED, 3.0) == REQUEST_START


# ── publisher ──


@pytest.mark.asyncio
async def test_bomb_payload_shape_and_member_total(monkeypatch):
    now = datetime(2026, 10, 7, 5, 0, tzinfo=UTC)
    at = now - timedelta(seconds=30)
    _patch_snapshot(monkeypatch, _snapshot(now, [_doc(at)]), {ADIT: "/static/team/adit.jpg"})
    redis = FakeRedis()
    assert await events.publish_round2_scoring_events(object(), redis, now) == 1
    (payload,) = redis.stream
    assert payload == {
        "kind": "bomb",
        "member": "adit",
        "display_name": "Adit",
        "avatar_url": "/static/team/adit.jpg",
        "activations": 3,
        "points": 3,
        "at": at.isoformat(timespec="milliseconds"),
    }
    assert "practice" not in json.dumps(payload) and "@" not in json.dumps(payload)


@pytest.mark.asyncio
async def test_penalty_payloads_for_request_and_review(monkeypatch):
    # Review of a DIFFERENT client so it is not dropped as the same incident.
    now = REVIEW_START + timedelta(seconds=10)
    snap = _snapshot(now, requests=[_request()], reviews=[_review(client_id=9)])
    # request start is hours earlier -> outside window; only the review is due now
    _patch_snapshot(monkeypatch, snap)
    redis = FakeRedis()
    assert await events.publish_round2_scoring_events(object(), redis, now) == 1
    (payload,) = redis.stream
    assert payload["kind"] == "penalty" and payload["points"] == -1
    assert payload["reason"] == "unreviewed_document"
    assert payload["at"] == REVIEW_START.isoformat(timespec="milliseconds")
    assert payload["activations"] == -3  # -2 request, -1 review

    now2 = REQUEST_START + timedelta(seconds=10)
    _patch_snapshot(monkeypatch, _snapshot(now2, requests=[_request()]))
    redis2 = FakeRedis()
    await events.publish_round2_scoring_events(object(), redis2, now2)
    assert redis2.stream[0]["reason"] == "unanswered_request"
    assert redis2.stream[0]["points"] == -2


@pytest.mark.asyncio
async def test_same_incident_review_penalty_is_not_published(monkeypatch):
    now = REVIEW_START + timedelta(seconds=10)
    # Same client 1 as the request -> the doc penalty is dropped by the scorer.
    _patch_snapshot(
        monkeypatch, _snapshot(now, requests=[_request()], reviews=[_review(client_id=1)])
    )
    redis = FakeRedis()
    assert await events.publish_round2_scoring_events(object(), redis, now) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("delta,expected", [(-1, 0), (0, 1), (1, 1), (119, 1), (120, 0), (600, 0)])
async def test_window_boundaries_120s(monkeypatch, delta, expected):
    at = datetime(2026, 10, 7, 5, 0, tzinfo=UTC)
    now = at + timedelta(seconds=delta)
    if delta < 0:  # first_doc_at in the future relative to now: not yet due
        now, at = at, at + timedelta(seconds=-delta)
    snap = _snapshot(now, [_doc(at)])
    _patch_snapshot(monkeypatch, snap)
    redis = FakeRedis()
    assert await events.publish_round2_scoring_events(object(), redis, now) == expected


@pytest.mark.asyncio
async def test_second_tick_publishes_nothing(monkeypatch):
    now = datetime(2026, 10, 7, 5, 0, tzinfo=UTC)
    _patch_snapshot(monkeypatch, _snapshot(now, [_doc(now - timedelta(seconds=30))]))
    redis = FakeRedis()
    assert await events.publish_round2_scoring_events(object(), redis, now) == 1
    later = now + timedelta(seconds=30)
    assert await events.publish_round2_scoring_events(object(), redis, later) == 0
    assert len(redis.stream) == 1


@pytest.mark.asyncio
async def test_non_participant_and_asya_events_are_ignored(monkeypatch):
    now = datetime(2026, 10, 7, 5, 0, tzinfo=UTC)
    at = now - timedelta(seconds=30)
    docs = [_doc(at, 1, "outsider@balizero.com"), _doc(at, 2, "asya@balizero.com")]
    _patch_snapshot(monkeypatch, _snapshot(now, docs, roster=(ADIT, "outsider@balizero.com")))
    redis = FakeRedis()
    assert await events.publish_round2_scoring_events(object(), redis, now) == 0
    assert redis.stream == [] and redis.deleted == []


# ── tick: gates, lock, kill switch ──


@pytest.mark.asyncio
async def test_tick_skips_when_round_not_live(monkeypatch):
    called = []

    async def fake(pool, redis, now):
        called.append(1)
        return 1

    monkeypatch.setattr(events, "publish_round2_scoring_events", fake)
    redis = FakeRedis()
    closed = datetime(2026, 11, 2, tzinfo=UTC)
    assert await events.champion_event_tick(object(), redis, closed) == 0
    round1 = datetime(2026, 9, 20, tzinfo=UTC)
    assert await events.champion_event_tick(object(), redis, round1) == 0
    assert called == [] and redis.set_calls == []


@pytest.mark.asyncio
async def test_tick_lock_held_skips_and_lock_is_set_nx_ex25(monkeypatch):
    async def fake(pool, redis, now):
        return 2

    monkeypatch.setattr(events, "publish_round2_scoring_events", fake)
    live = datetime(2026, 10, 7, 5, 0, tzinfo=UTC)
    held = FakeRedis(lock_free=False)
    assert await events.champion_event_tick(object(), held, live) == 0
    free = FakeRedis()
    assert await events.champion_event_tick(object(), free, live) == 2
    assert free.set_calls == [(events.PRODUCER_LOCK_KEY, True, 25)]


@pytest.mark.asyncio
async def test_tick_swallows_errors_and_logs_no_detail(monkeypatch, caplog):
    async def boom(pool, redis, now):
        raise RuntimeError("secret-client-detail")

    monkeypatch.setattr(events, "publish_round2_scoring_events", boom)
    live = datetime(2026, 10, 7, 5, 0, tzinfo=UTC)
    assert await events.champion_event_tick(object(), FakeRedis(), live) == 0
    assert "secret-client-detail" not in caplog.text and "RuntimeError" in caplog.text


@pytest.mark.asyncio
async def test_tick_has_a_deadline(monkeypatch):
    async def hang(pool, redis, now):
        await asyncio.sleep(60)

    monkeypatch.setattr(events, "publish_round2_scoring_events", hang)
    monkeypatch.setattr(events, "PRODUCER_TICK_TIMEOUT_SECONDS", 0.05)
    live = datetime(2026, 10, 7, 5, 0, tzinfo=UTC)
    assert await events.champion_event_tick(object(), FakeRedis(), live) == 0


@pytest.mark.parametrize(
    "value,enabled",
    [(None, True), ("1", True), ("true", True), ("0", False), ("false", False), (" FALSE ", False)],
)
def test_kill_switch(monkeypatch, value, enabled):
    if value is None:
        monkeypatch.delenv("CHAMPION_EVENT_PRODUCER_ENABLED", raising=False)
    else:
        monkeypatch.setenv("CHAMPION_EVENT_PRODUCER_ENABLED", value)
    assert events.champion_producer_enabled() is enabled
