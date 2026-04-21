"""Tests for PublisherOrchestrator — parallel + retry + idempotency + recording."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.services.publisher.base import (
    DraftPayload,
    Publisher,
    PublishResult,
    ValidationResult,
)
from backend.services.publisher.orchestrator import PublisherOrchestrator
from backend.services.war_room.models import (
    Platform,
    RegisterTone,
    WarRoomPost,
)


@dataclass
class _ScriptedPublisher(Publisher):
    platform_name: Platform
    script: list[PublishResult] = field(default_factory=list)
    call_count: int = 0

    async def validate(self, draft: DraftPayload) -> ValidationResult:
        return ValidationResult(ok=True, platform=self.platform_name)

    async def publish(self, draft: DraftPayload) -> PublishResult:
        idx = self.call_count
        self.call_count += 1
        if idx >= len(self.script):
            return PublishResult(
                ok=False,
                platform=self.platform_name,
                draft_id=draft.draft_id,
                error="out of script",
            )
        result = self.script[idx]
        result.draft_id = draft.draft_id
        return result

    async def delete(self, post_external_id: str) -> bool:  # pragma: no cover
        return True


def _ok(platform: Platform, ext_id: str) -> PublishResult:
    return PublishResult(
        ok=True,
        platform=platform,
        draft_id=uuid4(),
        post_external_id=ext_id,
        post_url=f"https://{platform.value}/{ext_id}",
        final_text="text",
    )


def _err(platform: Platform, msg: str = "fail") -> PublishResult:
    return PublishResult(
        ok=False,
        platform=platform,
        draft_id=uuid4(),
        error=msg,
    )


def _draft() -> DraftPayload:
    return DraftPayload(
        draft_id=uuid4(),
        topic="B211A",
        tone_register=None,
        cover_image_url="https://x/cover",
        main_caption="main",
    )


def _fast_backoffs() -> tuple[float, ...]:
    return (0.0, 0.0, 0.0)


# ── Initialisation ─────────────────────────────────────────────


def test_orchestrator_rejects_empty_publisher_list():
    with pytest.raises(ValueError):
        PublisherOrchestrator(publishers=[])


# ── Parallel happy path ────────────────────────────────────────


@pytest.mark.asyncio
async def test_publishes_all_platforms_in_parallel():
    ig = _ScriptedPublisher(
        platform_name=Platform.INSTAGRAM,
        script=[_ok(Platform.INSTAGRAM, "ig-1")],
    )
    x = _ScriptedPublisher(
        platform_name=Platform.X,
        script=[_ok(Platform.X, "x-1")],
    )
    orch = PublisherOrchestrator(
        publishers=[ig, x],
        max_retries=3,
        backoffs_s=_fast_backoffs(),
    )
    result = await orch.publish_all(_draft())
    assert result.ok_count == 2
    assert result.failure_count == 0
    assert {r.post_external_id for r in result.per_platform} == {"ig-1", "x-1"}


# ── Retry with backoff ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_publisher_retries_up_to_max_then_returns_failure():
    ig = _ScriptedPublisher(
        platform_name=Platform.INSTAGRAM,
        script=[_err(Platform.INSTAGRAM), _err(Platform.INSTAGRAM), _err(Platform.INSTAGRAM)],
    )
    orch = PublisherOrchestrator(
        publishers=[ig],
        max_retries=3,
        backoffs_s=_fast_backoffs(),
    )
    result = await orch.publish_all(_draft())
    assert result.ok_count == 0
    ig_result = result.per_platform[0]
    assert ig_result.ok is False
    assert ig_result.attempts == 3
    assert ig.call_count == 3


@pytest.mark.asyncio
async def test_publisher_recovers_on_second_attempt():
    ig = _ScriptedPublisher(
        platform_name=Platform.INSTAGRAM,
        script=[_err(Platform.INSTAGRAM), _ok(Platform.INSTAGRAM, "ig-2")],
    )
    orch = PublisherOrchestrator(
        publishers=[ig],
        max_retries=3,
        backoffs_s=_fast_backoffs(),
    )
    result = await orch.publish_all(_draft())
    assert result.ok_count == 1
    assert result.per_platform[0].attempts == 2


@pytest.mark.asyncio
async def test_one_platform_failure_does_not_affect_other():
    ig = _ScriptedPublisher(
        platform_name=Platform.INSTAGRAM,
        script=[_err(Platform.INSTAGRAM)] * 3,
    )
    x = _ScriptedPublisher(
        platform_name=Platform.X,
        script=[_ok(Platform.X, "x-1")],
    )
    orch = PublisherOrchestrator(
        publishers=[ig, x],
        max_retries=3,
        backoffs_s=_fast_backoffs(),
    )
    result = await orch.publish_all(_draft())
    assert result.ok_count == 1
    assert result.failure_count == 1
    # order of per_platform matches publisher list order
    assert result.per_platform[0].platform == Platform.INSTAGRAM
    assert result.per_platform[0].ok is False
    assert result.per_platform[1].platform == Platform.X
    assert result.per_platform[1].ok is True


# ── Exception swallowed as failure ─────────────────────────────


class _RaisingPublisher(Publisher):
    platform_name = Platform.LINKEDIN

    async def validate(self, draft: DraftPayload) -> ValidationResult:
        return ValidationResult(ok=True, platform=Platform.LINKEDIN)

    async def publish(self, draft: DraftPayload) -> PublishResult:
        raise RuntimeError("boom")

    async def delete(self, pid: str) -> bool:  # pragma: no cover
        return False


@pytest.mark.asyncio
async def test_raising_publisher_is_caught_as_failure():
    orch = PublisherOrchestrator(
        publishers=[_RaisingPublisher()],
        max_retries=2,
        backoffs_s=_fast_backoffs(),
    )
    result = await orch.publish_all(_draft())
    assert result.ok_count == 0
    r = result.per_platform[0]
    assert r.ok is False
    assert "RuntimeError" in (r.error or "")


# ── Idempotency via repo ───────────────────────────────────────


@pytest.mark.asyncio
async def test_skips_platform_where_post_already_exists():
    ig = _ScriptedPublisher(
        platform_name=Platform.INSTAGRAM,
        script=[_ok(Platform.INSTAGRAM, "ig-new")],
    )
    repo = AsyncMock()
    existing = WarRoomPost(
        id=uuid4(),
        draft_id=uuid4(),
        platform=Platform.INSTAGRAM,
        post_external_id="ig-existing",
        post_url="https://instagram/p/old",
        tone_register=None,
        published_at=datetime.now(timezone.utc),
    )
    repo.get_posts_for_draft = AsyncMock(return_value=[existing])
    repo.create_post = AsyncMock()

    orch = PublisherOrchestrator(
        publishers=[ig],
        repo=repo,
        max_retries=3,
        backoffs_s=_fast_backoffs(),
    )
    result = await orch.publish_all(_draft())
    assert result.ok_count == 1
    assert result.per_platform[0].meta.get("idempotent_skip") is True
    # publisher was NOT called
    assert ig.call_count == 0
    # no new row written for idempotent skip
    repo.create_post.assert_not_called()
    assert "instagram" in result.skipped_already_published


@pytest.mark.asyncio
async def test_force_flag_republishes_even_if_existing():
    ig = _ScriptedPublisher(
        platform_name=Platform.INSTAGRAM,
        script=[_ok(Platform.INSTAGRAM, "ig-forced")],
    )
    repo = AsyncMock()
    existing = WarRoomPost(
        id=uuid4(),
        draft_id=uuid4(),
        platform=Platform.INSTAGRAM,
        post_external_id="ig-existing",
        tone_register=None,
        published_at=datetime.now(timezone.utc),
    )
    repo.get_posts_for_draft = AsyncMock(return_value=[existing])
    repo.create_post = AsyncMock()

    orch = PublisherOrchestrator(
        publishers=[ig],
        repo=repo,
        max_retries=3,
        backoffs_s=_fast_backoffs(),
    )
    result = await orch.publish_all(_draft(), force=True)
    assert ig.call_count == 1
    assert result.per_platform[0].post_external_id == "ig-forced"


# ── Recording success to repo ─────────────────────────────────


@pytest.mark.asyncio
async def test_successes_recorded_to_repo_with_tone_register():
    ig = _ScriptedPublisher(
        platform_name=Platform.INSTAGRAM,
        script=[_ok(Platform.INSTAGRAM, "ig-1")],
    )
    x = _ScriptedPublisher(
        platform_name=Platform.X,
        script=[_err(Platform.X)] * 3,
    )
    repo = AsyncMock()
    repo.get_posts_for_draft = AsyncMock(return_value=[])
    repo.create_post = AsyncMock()

    orch = PublisherOrchestrator(
        publishers=[ig, x],
        repo=repo,
        max_retries=3,
        backoffs_s=_fast_backoffs(),
    )
    await orch.publish_all(_draft(), tone_register=RegisterTone.ANALITICO)

    # only IG success should trigger create_post
    assert repo.create_post.await_count == 1
    post_create = repo.create_post.await_args.args[0]
    assert post_create.platform == Platform.INSTAGRAM
    assert post_create.tone_register == RegisterTone.ANALITICO


@pytest.mark.asyncio
async def test_record_failure_does_not_downgrade_success():
    ig = _ScriptedPublisher(
        platform_name=Platform.INSTAGRAM,
        script=[_ok(Platform.INSTAGRAM, "ig-1")],
    )
    repo = AsyncMock()
    repo.get_posts_for_draft = AsyncMock(return_value=[])
    repo.create_post = AsyncMock(side_effect=RuntimeError("pg down"))

    orch = PublisherOrchestrator(
        publishers=[ig],
        repo=repo,
        max_retries=3,
        backoffs_s=_fast_backoffs(),
    )
    result = await orch.publish_all(_draft())
    # publication succeeded; recording failure is isolated
    assert result.ok_count == 1


# ── Kill switch ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_kill_switch_off_skips_all_publishers():
    """When kill_switch_check() returns False, no publisher is invoked."""
    ig = _ScriptedPublisher(
        platform_name=Platform.INSTAGRAM,
        script=[_ok(Platform.INSTAGRAM, "ig-should-not-fire")],
    )
    x = _ScriptedPublisher(
        platform_name=Platform.X,
        script=[_ok(Platform.X, "x-should-not-fire")],
    )

    async def kill_switch_off() -> bool:
        return False

    orch = PublisherOrchestrator(
        publishers=[ig, x],
        max_retries=3,
        backoffs_s=_fast_backoffs(),
        kill_switch_check=kill_switch_off,
    )
    result = await orch.publish_all(_draft())

    assert ig.call_count == 0
    assert x.call_count == 0
    assert result.ok_count == 0
    assert result.failure_count == 2
    for pr in result.per_platform:
        assert pr.ok is False
        assert pr.error == "wr2_publisher_kill_switch_off"
        assert pr.attempts == 0


@pytest.mark.asyncio
async def test_kill_switch_on_lets_publishers_run():
    """When kill_switch_check() returns True, publication proceeds normally."""
    ig = _ScriptedPublisher(
        platform_name=Platform.INSTAGRAM,
        script=[_ok(Platform.INSTAGRAM, "ig-1")],
    )

    async def kill_switch_on() -> bool:
        return True

    orch = PublisherOrchestrator(
        publishers=[ig],
        max_retries=3,
        backoffs_s=_fast_backoffs(),
        kill_switch_check=kill_switch_on,
    )
    result = await orch.publish_all(_draft())

    assert ig.call_count == 1
    assert result.ok_count == 1


@pytest.mark.asyncio
async def test_no_kill_switch_check_defaults_to_allow():
    """Backwards compatible: orchestrators without kill switch still publish."""
    ig = _ScriptedPublisher(
        platform_name=Platform.INSTAGRAM,
        script=[_ok(Platform.INSTAGRAM, "ig-1")],
    )
    orch = PublisherOrchestrator(
        publishers=[ig],
        max_retries=3,
        backoffs_s=_fast_backoffs(),
    )
    result = await orch.publish_all(_draft())
    assert result.ok_count == 1


@pytest.mark.asyncio
async def test_kill_switch_skips_record_to_db():
    """Orchestrator must NOT record war_room_post rows when switch is off."""
    ig = _ScriptedPublisher(
        platform_name=Platform.INSTAGRAM,
        script=[_ok(Platform.INSTAGRAM, "ig-1")],
    )
    repo = AsyncMock()
    repo.get_posts_for_draft = AsyncMock(return_value=[])
    repo.create_post = AsyncMock()

    async def kill_switch_off() -> bool:
        return False

    orch = PublisherOrchestrator(
        publishers=[ig],
        repo=repo,
        max_retries=3,
        backoffs_s=_fast_backoffs(),
        kill_switch_check=kill_switch_off,
    )
    result = await orch.publish_all(_draft())

    assert ig.call_count == 0
    assert result.ok_count == 0
    repo.create_post.assert_not_awaited()
    # We also should not waste a query on existing posts when switch is off.
    repo.get_posts_for_draft.assert_not_awaited()


# ── DB-backed kill-switch helper ───────────────────────────────


class _FakeAcquire:
    """Minimal async context manager returning a pre-baked conn."""

    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc):
        return None


class _FakePool:
    def __init__(self, *, conn=None, raise_exc: Exception | None = None):
        self._conn = conn
        self._raise_exc = raise_exc

    def acquire(self):
        if self._raise_exc is not None:
            raise self._raise_exc
        return _FakeAcquire(self._conn)


@pytest.mark.asyncio
async def test_db_kill_switch_reads_system_settings_true():
    from backend.services.publisher.orchestrator import (
        build_db_kill_switch_check,
    )

    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value="true")
    pool = _FakePool(conn=conn)

    check = build_db_kill_switch_check(pool)
    assert await check() is True
    conn.fetchval.assert_awaited_once()
    args = conn.fetchval.await_args.args
    assert "wr2_publisher_enabled" in args[1]  # arg 0 = SQL, arg 1 = key


@pytest.mark.asyncio
async def test_db_kill_switch_defaults_to_off_when_unset():
    """Missing row (NULL) → False. Safe default: publisher stays disabled."""
    from backend.services.publisher.orchestrator import (
        build_db_kill_switch_check,
    )

    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=None)
    pool = _FakePool(conn=conn)

    check = build_db_kill_switch_check(pool)
    assert await check() is False


@pytest.mark.asyncio
async def test_db_kill_switch_off_when_value_is_not_true():
    from backend.services.publisher.orchestrator import (
        build_db_kill_switch_check,
    )

    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value="false")
    pool = _FakePool(conn=conn)

    check = build_db_kill_switch_check(pool)
    assert await check() is False


@pytest.mark.asyncio
async def test_db_kill_switch_fails_closed_on_db_error():
    """DB error → False (fail closed). Never publish if we can't read the flag."""
    from backend.services.publisher.orchestrator import (
        build_db_kill_switch_check,
    )

    pool = _FakePool(raise_exc=RuntimeError("pg unreachable"))

    check = build_db_kill_switch_check(pool)
    assert await check() is False
