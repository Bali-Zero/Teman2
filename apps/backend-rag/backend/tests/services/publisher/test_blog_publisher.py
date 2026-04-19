"""Tests for BlogPublisher (git subprocess mocked + tmpdir)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import pytest

from backend.services.publisher.base import DraftPayload, SlidePayload
from backend.services.publisher.blog_publisher import BlogPublisher
from backend.services.war_room.models import RegisterTone

DID = UUID("12345678-1234-1234-1234-123456789abc")


def _draft() -> DraftPayload:
    return DraftPayload(
        draft_id=DID,
        topic="Permenkumham 22/2023",
        tone_register=RegisterTone.TECNICO,
        cover_image_url="https://tigris/cover.png",
        main_caption="Una lettura.",
        slides=[
            SlidePayload(
                slide_number=2,
                image_url="https://tigris/s1.png",
                caption="Slide A",
                final_text="body A",
            ),
        ],
        hashtags=["KBLI"],
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Create a tmp git-repo-like directory with content_root inside."""
    (tmp_path / ".git").mkdir()
    (tmp_path / "content" / "war-room").mkdir(parents=True)
    return tmp_path


def _make_publisher(tmp_repo: Path, *, skip_push: bool = True) -> BlogPublisher:
    content_root = tmp_repo / "content" / "war-room"
    return BlogPublisher(
        content_root=str(content_root),
        repo_root=str(tmp_repo),
        site_url="https://balizero.com",
        url_prefix="/blog",
        skip_push=skip_push,
        clock=lambda: datetime(2026, 4, 18, 9, 30, tzinfo=timezone.utc),
    )


@pytest.fixture
def git_mock():
    """Patch BlogPublisher._git so we don't hit the real git binary."""
    async def fake_git(self, argv, *, cwd):
        return 0, ""

    with patch.object(BlogPublisher, "_git", new=fake_git):
        yield


# ── Config ─────────────────────────────────────────────────────


def test_infer_repo_root_walks_up(tmp_path: Path):
    (tmp_path / ".git").mkdir()
    nested = tmp_path / "a" / "b" / "c"
    nested.mkdir(parents=True)
    got = BlogPublisher._infer_repo_root(nested)
    assert got == tmp_path


def test_env_skip_push_flag_true(monkeypatch):
    monkeypatch.setenv("BLOG_PUBLISH_SKIP_PUSH", "1")
    p = BlogPublisher(
        content_root="/tmp/xyz",
        repo_root="/tmp",
        skip_push=None,  # let env decide
    )
    assert p.skip_push is True


# ── Validation ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_validate_empty_caption_fails(repo: Path, git_mock):
    p = _make_publisher(repo)
    d = _draft()
    d.main_caption = ""
    v = await p.validate(d)
    assert v.ok is False


@pytest.mark.asyncio
async def test_validate_empty_topic_fails(repo: Path, git_mock):
    p = _make_publisher(repo)
    d = _draft()
    d.topic = ""
    v = await p.validate(d)
    assert v.ok is False


# ── Publish happy path ────────────────────────────────────────


@pytest.mark.asyncio
async def test_publish_writes_mdx_and_commits(repo: Path, git_mock):
    p = _make_publisher(repo)
    result = await p.publish(_draft())
    assert result.ok is True
    file_path = Path(result.meta["file_path"])
    assert file_path.exists()
    content = file_path.read_text(encoding="utf-8")
    assert content.startswith("---")
    assert "# Permenkumham 22/2023" in content
    assert f'draft_id: "{DID}"' in content
    # external id is repo-relative path
    assert result.post_external_id and not result.post_external_id.startswith("/")
    assert result.post_url and "balizero.com/blog/" in result.post_url


@pytest.mark.asyncio
async def test_publish_creates_content_root_if_missing(tmp_path: Path, git_mock):
    # No content/ directory yet
    (tmp_path / ".git").mkdir()
    p = BlogPublisher(
        content_root=str(tmp_path / "new" / "war-room"),
        repo_root=str(tmp_path),
        skip_push=True,
        clock=lambda: datetime(2026, 4, 18, 12, 0, tzinfo=timezone.utc),
    )
    result = await p.publish(_draft())
    assert result.ok is True
    assert (tmp_path / "new" / "war-room").is_dir()


# ── Idempotency ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_publish_idempotent_when_same_draft_id(repo: Path, git_mock):
    p = _make_publisher(repo)
    r1 = await p.publish(_draft())
    assert r1.ok is True
    r2 = await p.publish(_draft())
    assert r2.ok is True
    assert r2.meta.get("idempotent_skip") is True
    # same file path, no duplication
    assert r2.meta["file_path"] == r1.meta["file_path"]


# ── Git failures ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_publish_fails_when_git_add_fails(repo: Path):
    p = _make_publisher(repo)
    calls: list[tuple[str, ...]] = []

    async def fake_git(self, argv, *, cwd):
        calls.append(tuple(argv))
        if argv[0] == "add":
            return 1, "add error"
        return 0, ""

    with patch.object(BlogPublisher, "_git", new=fake_git):
        result = await p.publish(_draft())
    assert result.ok is False
    assert "git add" in (result.error or "")


@pytest.mark.asyncio
async def test_publish_nothing_to_commit_is_success(repo: Path):
    p = _make_publisher(repo)

    async def fake_git(self, argv, *, cwd):
        if argv[0] == "commit":
            return 1, "nothing to commit, working tree clean"
        return 0, ""

    with patch.object(BlogPublisher, "_git", new=fake_git):
        result = await p.publish(_draft())
    assert result.ok is True


@pytest.mark.asyncio
async def test_publish_fails_when_push_fails(repo: Path):
    p = _make_publisher(repo, skip_push=False)

    async def fake_git(self, argv, *, cwd):
        if argv[0] == "push":
            return 1, "push rejected"
        return 0, ""

    with patch.object(BlogPublisher, "_git", new=fake_git):
        result = await p.publish(_draft())
    assert result.ok is False
    assert "git push" in (result.error or "")


@pytest.mark.asyncio
async def test_skip_push_does_not_run_push(repo: Path):
    p = _make_publisher(repo, skip_push=True)
    calls: list[tuple[str, ...]] = []

    async def fake_git(self, argv, *, cwd):
        calls.append(tuple(argv))
        return 0, ""

    with patch.object(BlogPublisher, "_git", new=fake_git):
        result = await p.publish(_draft())
    assert result.ok is True
    assert result.meta["pushed"] is False
    # push must not have been called
    assert not any(c[0] == "push" for c in calls)


# ── Delete ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_missing_file_returns_false(repo: Path, git_mock):
    p = _make_publisher(repo)
    assert await p.delete("nonexistent.mdx") is False


@pytest.mark.asyncio
async def test_delete_existing_file_ok(repo: Path, git_mock):
    p = _make_publisher(repo)
    # publish first to create the file
    result = await p.publish(_draft())
    assert result.ok is True
    rel = result.post_external_id
    assert rel
    # now delete
    deleted = await p.delete(rel)
    assert deleted is True
