"""Tests for BlogBatchPublisher — batch single-commit + daily cap."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from backend.services.publisher.base import DraftPayload, SlidePayload
from backend.services.publisher.blog_batch_publisher import (
    HARD_DAILY_CAP,
    SOFT_DAILY_TARGET_MAX,
    SOFT_DAILY_TARGET_MIN,
    BlogBatchPublisher,
)
from backend.services.publisher.blog_publisher import BlogPublisher
from backend.services.publisher.mdx_template import MdxExtras
from backend.services.war_room.models import RegisterTone


def _draft(topic: str = "t") -> DraftPayload:
    return DraftPayload(
        draft_id=uuid4(),
        topic=topic,
        tone_register=RegisterTone.TECNICO,
        cover_image_url="https://tigris/c.png",
        main_caption="Main caption " * 30,
        slides=[
            SlidePayload(
                slide_number=2, image_url="https://tigris/s1.png",
                caption="A", final_text="body A " * 40,
            ),
        ],
        hashtags=["KBLI"],
    )


@pytest.fixture
def repo_env(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    (tmp_path / "content" / "war-room").mkdir(parents=True)
    return tmp_path


def _blog_publisher(tmp_repo: Path, *, skip_push: bool = True) -> BlogPublisher:
    return BlogPublisher(
        content_root=str(tmp_repo / "content" / "war-room"),
        repo_root=str(tmp_repo),
        site_url="https://balizero.com",
        url_prefix="/blog",
        skip_push=skip_push,
        clock=lambda: datetime(2026, 4, 18, 10, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def git_mock():
    async def fake_git(self, argv, *, cwd):
        return 0, ""

    with patch.object(BlogPublisher, "_git", new=fake_git):
        yield


# ── Constants sanity ─────────────────────────────────────────


def test_soft_target_design_3_to_5():
    assert SOFT_DAILY_TARGET_MIN == 3
    assert SOFT_DAILY_TARGET_MAX == 5


def test_hard_cap_design_8():
    assert HARD_DAILY_CAP == 8


# ── Empty batch ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_publish_empty_batch(repo_env, git_mock):
    bp = _blog_publisher(repo_env)
    batch = BlogBatchPublisher(blog_publisher=bp)
    result = await batch.publish_batch([])
    assert result.requested == 0
    assert result.published_count == 0


# ── Batch writes files + single commit ───────────────────────


@pytest.mark.asyncio
async def test_batch_writes_all_files(repo_env):
    """3 drafts → 3 MDX files → single git commit pass."""
    bp = _blog_publisher(repo_env)
    batch = BlogBatchPublisher(blog_publisher=bp)

    calls: list[tuple[str, ...]] = []

    async def fake_git(self, argv, *, cwd):
        calls.append(tuple(argv))
        return 0, ""

    with patch.object(BlogPublisher, "_git", new=fake_git):
        result = await batch.publish_batch([
            _draft("topic A"),
            _draft("topic B"),
            _draft("topic C"),
        ])

    assert result.published_count == 3
    assert result.commit_ok is True

    # Exactly one add (batch) + one commit
    adds = [c for c in calls if c and c[0] == "add"]
    commits = [c for c in calls if c and c[0] == "commit"]
    assert len(adds) == 1
    assert len(commits) == 1

    # Files exist on disk
    content_dir = repo_env / "content" / "war-room"
    mdx_files = list(content_dir.glob("*.mdx"))
    assert len(mdx_files) == 3


# ── Daily cap enforcement ────────────────────────────────────


@pytest.mark.asyncio
async def test_hard_cap_enforced_via_repo_count(repo_env, git_mock):
    repo = AsyncMock()
    repo.count_posts_published_today = AsyncMock(return_value=7)

    bp = _blog_publisher(repo_env)
    batch = BlogBatchPublisher(blog_publisher=bp, repo=repo, hard_cap=8)

    # budget remaining = 8 - 7 = 1 → 1 published, 2 skipped over cap
    result = await batch.publish_batch([_draft(f"t{i}") for i in range(3)])

    assert result.published_count == 1
    assert len(result.over_cap_skipped) == 2
    assert all(
        r.meta.get("over_daily_cap") is True for r in result.over_cap_skipped
    )


@pytest.mark.asyncio
async def test_cap_saturated_writes_nothing(repo_env, git_mock):
    repo = AsyncMock()
    repo.count_posts_published_today = AsyncMock(return_value=8)

    bp = _blog_publisher(repo_env)
    batch = BlogBatchPublisher(blog_publisher=bp, repo=repo, hard_cap=8)
    result = await batch.publish_batch([_draft(), _draft()])

    assert result.published_count == 0
    assert len(result.over_cap_skipped) == 2
    # commit_ok but pushed stays False-ish (nothing to commit → shortcut)
    # still counts as a clean run
    assert result.commit_ok is True


@pytest.mark.asyncio
async def test_no_repo_no_cap_check(repo_env, git_mock):
    """Without a repo, we trust the caller — no cap enforcement."""
    bp = _blog_publisher(repo_env)
    batch = BlogBatchPublisher(blog_publisher=bp, repo=None)
    result = await batch.publish_batch([_draft(f"t{i}") for i in range(5)])
    assert result.published_count == 5
    assert result.over_cap_skipped == []


@pytest.mark.asyncio
async def test_repo_error_counted_but_batch_proceeds(repo_env, git_mock):
    repo = AsyncMock()
    repo.count_posts_published_today = AsyncMock(
        side_effect=RuntimeError("pg"),
    )
    bp = _blog_publisher(repo_env)
    batch = BlogBatchPublisher(blog_publisher=bp, repo=repo)
    result = await batch.publish_batch([_draft("x")])
    # Repo failure → remaining_budget defaults to 0 → skipped over cap
    # but `daily_count` error recorded
    assert any("daily_count" in e for e in result.errors)


# ── Idempotency ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_idempotent_draft_in_batch(repo_env, git_mock):
    bp = _blog_publisher(repo_env)
    batch = BlogBatchPublisher(blog_publisher=bp)
    draft = _draft("idempotent")
    await batch.publish_batch([draft])

    # re-publish same draft → should be skipped
    result = await batch.publish_batch([draft])
    assert result.published_count == 0
    assert len(result.idempotent_skipped) == 1
    assert result.idempotent_skipped[0].meta.get("idempotent_skip") is True


# ── Extras wiring ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_extras_applied_to_output(repo_env, git_mock):
    bp = _blog_publisher(repo_env)
    batch = BlogBatchPublisher(blog_publisher=bp)
    draft = _draft("with extras")
    extras = MdxExtras(dossier_id="doss-42", composite_score=0.82)

    result = await batch.publish_batch(
        [draft],
        extras_by_draft={draft.draft_id: extras},
    )
    assert result.published_count == 1
    file_path = Path(result.published[0].meta["file_path"])
    content = file_path.read_text(encoding="utf-8")
    assert 'dossier_id: "doss-42"' in content
    assert "composite_score: 0.820" in content
    # auto_reading_time=True so this field appears too
    assert "reading_time_min:" in content


# ── Validation failure ───────────────────────────────────────


@pytest.mark.asyncio
async def test_invalid_draft_counts_as_error(repo_env, git_mock):
    bp = _blog_publisher(repo_env)
    batch = BlogBatchPublisher(blog_publisher=bp)
    bad = _draft("bad")
    bad.topic = ""
    bad.main_caption = ""
    result = await batch.publish_batch([bad])
    assert result.published_count == 0
    assert len(result.published) == 1
    assert result.published[0].ok is False


# ── git failure ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_git_add_failure_surfaced_as_error(repo_env):
    bp = _blog_publisher(repo_env)
    batch = BlogBatchPublisher(blog_publisher=bp)

    async def fake_git(self, argv, *, cwd):
        if argv and argv[0] == "add":
            return 1, "add error"
        return 0, ""

    with patch.object(BlogPublisher, "_git", new=fake_git):
        result = await batch.publish_batch([_draft("x")])

    assert any("commit" in e or "add" in e for e in result.errors)
    assert result.commit_ok is False


@pytest.mark.asyncio
async def test_nothing_to_commit_still_ok(repo_env):
    """Race with manual commits: nothing-to-commit → commit_ok stays True."""
    bp = _blog_publisher(repo_env)
    batch = BlogBatchPublisher(blog_publisher=bp)

    async def fake_git(self, argv, *, cwd):
        if argv and argv[0] == "commit":
            return 1, "nothing to commit, working tree clean"
        return 0, ""

    with patch.object(BlogPublisher, "_git", new=fake_git):
        result = await batch.publish_batch([_draft("x")])

    assert result.commit_ok is True
