"""
Tests for GitHubPublisher.

Covers:
- Path traversal validation (_validate_path)
- is_configured property
- _get_headers (no token leak)
- check_file_exists (mocked httpx)
- upload_file happy-path and error handling
- create_commit_with_files path validation
- close() lifecycle
"""

import asyncio
import base64
import json
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.integrations.github_publisher import (
    GitHubPublisher,
    GitHubPublisherError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_publisher(
    token: str = "ghp_fake",
    owner: str = "org",
    repo: str = "repo",
) -> GitHubPublisher:
    with patch("backend.services.integrations.github_publisher.settings") as mock_settings:
        mock_settings.github_token = token
        mock_settings.github_owner = owner
        mock_settings.github_repo = repo
        pub = GitHubPublisher()
    return pub


# ---------------------------------------------------------------------------
# _validate_path
# ---------------------------------------------------------------------------


class TestValidatePath:
    def test_normal_path_unchanged(self):
        assert (
            GitHubPublisher._validate_path("content/articles/foo.mdx") == "content/articles/foo.mdx"
        )

    def test_leading_slash_stripped(self):
        assert GitHubPublisher._validate_path("/content/foo.mdx") == "content/foo.mdx"

    def test_dot_dot_segment_rejected(self):
        with pytest.raises(ValueError, match="traversal"):
            GitHubPublisher._validate_path("../../etc/passwd")

    def test_dot_dot_in_middle_rejected(self):
        with pytest.raises(ValueError, match="traversal"):
            GitHubPublisher._validate_path("content/../../../etc/passwd")

    def test_dot_dot_at_end_rejected(self):
        with pytest.raises(ValueError, match="traversal"):
            GitHubPublisher._validate_path("content/..")

    def test_null_byte_rejected(self):
        with pytest.raises(ValueError, match="control characters"):
            GitHubPublisher._validate_path("content/foo\x00bar.mdx")

    def test_empty_path_rejected(self):
        with pytest.raises(ValueError, match="empty"):
            GitHubPublisher._validate_path("")

    def test_slash_only_rejected(self):
        # After stripping leading slash → empty string → rejected
        with pytest.raises(ValueError, match="empty"):
            GitHubPublisher._validate_path("/")

    def test_nested_valid_path(self):
        result = GitHubPublisher._validate_path("a/b/c/d.txt")
        assert result == "a/b/c/d.txt"


# ---------------------------------------------------------------------------
# is_configured
# ---------------------------------------------------------------------------


class TestIsConfigured:
    def test_configured_when_all_set(self):
        pub = _make_publisher()
        assert pub.is_configured is True

    def test_not_configured_when_token_missing(self):
        pub = _make_publisher(token="")
        assert pub.is_configured is False

    def test_not_configured_when_owner_missing(self):
        pub = _make_publisher(owner="")
        assert pub.is_configured is False

    def test_not_configured_when_repo_missing(self):
        pub = _make_publisher(repo="")
        assert pub.is_configured is False


# ---------------------------------------------------------------------------
# _get_headers
# ---------------------------------------------------------------------------


class TestGetHeaders:
    def test_contains_bearer_token(self):
        pub = _make_publisher(token="ghp_secret123")
        headers = pub._get_headers()
        assert headers["Authorization"] == "Bearer ghp_secret123"
        assert "application/vnd.github" in headers["Accept"]

    def test_token_not_logged(self):
        """Ensures the token value is encapsulated and not exposed via repr."""
        pub = _make_publisher(token="ghp_supersecret")
        pub._get_headers()  # side-effect call; we only check str(pub) below
        # The header dict is fine to use internally but we verify no accidental exposure.
        assert "ghp_supersecret" not in str(pub)


# ---------------------------------------------------------------------------
# _get_client
# ---------------------------------------------------------------------------


class TestGetClient:
    @pytest.mark.asyncio
    async def test_client_follows_redirects(self):
        """A renamed/transferred repo answers 301 on its old owner/repo path;
        without follow_redirects every publish fails as a bare
        "GitHub publish failed" (2026-08-28, 2026-09-04)."""
        pub = GitHubPublisher(token="t", owner="o", repo="r")
        try:
            assert pub._get_client().follow_redirects is True
        finally:
            await pub.close()


# ---------------------------------------------------------------------------
# close()
# ---------------------------------------------------------------------------


class TestClose:
    @pytest.mark.asyncio
    async def test_close_calls_aclose(self):
        pub = _make_publisher()
        mock_client = AsyncMock()
        mock_client.is_closed = False
        pub._client = mock_client
        await pub.close()
        mock_client.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_skips_already_closed(self):
        pub = _make_publisher()
        mock_client = AsyncMock()
        mock_client.is_closed = True
        pub._client = mock_client
        await pub.close()
        mock_client.aclose.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_close_safe_when_no_client(self):
        pub = _make_publisher()
        pub._client = None
        await pub.close()
        assert pub._client is None


# ---------------------------------------------------------------------------
# check_file_exists
# ---------------------------------------------------------------------------


class TestCheckFileExists:
    @pytest.mark.asyncio
    async def test_returns_true_when_200(self):
        pub = _make_publisher()
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.is_closed = False
        pub._client = mock_client

        result = await pub.check_file_exists("content/foo.mdx")
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_404(self):
        pub = _make_publisher()
        mock_resp = MagicMock()
        mock_resp.status_code = 404

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.is_closed = False
        pub._client = mock_client

        result = await pub.check_file_exists("content/missing.mdx")
        assert result is False

    @pytest.mark.asyncio
    async def test_raises_on_traversal_path(self):
        pub = _make_publisher()
        with pytest.raises(ValueError, match="traversal"):
            await pub.check_file_exists("../../etc/passwd")

    @pytest.mark.asyncio
    async def test_raises_when_not_configured(self):
        pub = _make_publisher(token="")
        with pytest.raises(GitHubPublisherError, match="not configured"):
            await pub.check_file_exists("content/foo.mdx")


class TestGetFileContent:
    @pytest.mark.asyncio
    async def test_decodes_utf8_base64_content(self):
        pub = _make_publisher()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "content": base64.b64encode(b'{"hero_main":"story"}\n').decode()
        }
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.is_closed = False
        pub._client = mock_client

        content = await pub.get_file_content(
            "apps/mouth/src/content/homepage-layout.json"
        )

        assert content == '{"hero_main":"story"}\n'

    @pytest.mark.asyncio
    async def test_non_200_is_an_error(self):
        pub = _make_publisher()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = "not found"
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.is_closed = False
        pub._client = mock_client

        with pytest.raises(GitHubPublisherError, match="Failed to read"):
            await pub.get_file_content("missing.json")


# ---------------------------------------------------------------------------
# upload_file
# ---------------------------------------------------------------------------


class TestUploadFile:
    def _make_upload_response(self, status_code: int = 201) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.json.return_value = {
            "content": {"sha": "abc" * 13 + "x"},
            "commit": {
                "sha": "def" * 13 + "y",
                "html_url": "https://github.com/org/repo/commit/def",
            },
        }
        return mock_resp

    @pytest.mark.asyncio
    async def test_upload_new_file_success(self):
        pub = _make_publisher()

        # get_file_sha → file doesn't exist yet
        pub.get_file_sha = AsyncMock(return_value=None)

        mock_resp = self._make_upload_response(201)
        mock_client = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_resp)
        mock_client.is_closed = False
        pub._client = mock_client

        result = await pub.upload_file("content/new.mdx", "# Hello", "Add article")
        assert result["success"] is True
        assert result["path"] == "content/new.mdx"

    @pytest.mark.asyncio
    async def test_upload_existing_file_includes_sha(self):
        pub = _make_publisher()
        pub.get_file_sha = AsyncMock(return_value="existing-sha-12345")

        mock_resp = self._make_upload_response(200)
        captured_payload: dict = {}

        async def fake_put(url, **kwargs):
            captured_payload.update(kwargs.get("json", {}))
            return mock_resp

        mock_client = AsyncMock()
        mock_client.put = fake_put
        mock_client.is_closed = False
        pub._client = mock_client

        result = await pub.upload_file("content/existing.mdx", b"bytes content", "Update")
        assert result["success"] is True
        assert captured_payload.get("sha") == "existing-sha-12345"

    @pytest.mark.asyncio
    async def test_upload_raises_on_traversal_path(self):
        pub = _make_publisher()
        with pytest.raises(ValueError, match="traversal"):
            await pub.upload_file("../../secret", "content", "msg")

    @pytest.mark.asyncio
    async def test_upload_raises_on_api_error(self):
        pub = _make_publisher()
        pub.get_file_sha = AsyncMock(return_value=None)

        mock_resp = MagicMock()
        mock_resp.status_code = 422
        mock_resp.text = "Unprocessable Entity"
        mock_resp.json.return_value = {"message": "Unprocessable Entity"}
        mock_client = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_resp)
        mock_client.is_closed = False
        pub._client = mock_client

        with pytest.raises(GitHubPublisherError):
            await pub.upload_file("content/bad.mdx", "content", "msg")

    @pytest.mark.asyncio
    async def test_upload_string_content_encoded(self):
        pub = _make_publisher()
        pub.get_file_sha = AsyncMock(return_value=None)

        mock_resp = self._make_upload_response(201)
        captured_payload: dict = {}

        async def fake_put(url, **kwargs):
            captured_payload.update(kwargs.get("json", {}))
            return mock_resp

        mock_client = AsyncMock()
        mock_client.put = fake_put
        mock_client.is_closed = False
        pub._client = mock_client

        await pub.upload_file("content/str.mdx", "# Hello", "msg")
        # Content must be base64-encoded UTF-8
        decoded = base64.b64decode(captured_payload["content"]).decode("utf-8")
        assert decoded == "# Hello"


# ---------------------------------------------------------------------------
# create_commit_with_files — path validation
# ---------------------------------------------------------------------------


class TestCreateCommitWithFiles:
    @pytest.mark.asyncio
    async def test_rejects_traversal_in_files_list(self):
        pub = _make_publisher()
        files = [
            {"path": "content/ok.mdx", "content": "fine"},
            {"path": "../../etc/passwd", "content": "bad"},
        ]
        with pytest.raises(ValueError, match="traversal"):
            await pub.create_commit_with_files(files, "msg")

    @pytest.mark.asyncio
    async def test_raises_when_not_configured(self):
        pub = _make_publisher(token="")
        with pytest.raises(GitHubPublisherError, match="not configured"):
            await pub.create_commit_with_files([{"path": "a.mdx", "content": "x"}], "msg")

    @pytest.mark.asyncio
    async def test_idempotent_publication_resumes_existing_pr_without_new_commit(self):
        pub = _make_publisher()
        existing = {
            "success": True,
            "commit_sha": "existing-sha",
            "pull_request_number": 91,
            "idempotent": True,
        }
        pub._resume_publication_pull_request = AsyncMock(return_value=existing)

        result = await pub.create_commit_with_files(
            [{"path": "content/story.mdx", "content": "story"}],
            "feat(article): story",
            pull_request=True,
            idempotency_key="news_20260827_story",
        )

        assert result == existing
        pub._resume_publication_pull_request.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_long_distinct_idempotency_keys_use_distinct_branch_hashes(self):
        pub = _make_publisher()
        pub._resume_publication_pull_request = AsyncMock(
            return_value={"success": True, "idempotent": True}
        )
        common = "x" * 110

        await pub.create_commit_with_files(
            [{"path": "content/story.mdx", "content": "story"}],
            "feat(article): story",
            pull_request=True,
            idempotency_key=common + "a",
        )
        await pub.create_commit_with_files(
            [{"path": "content/story.mdx", "content": "story"}],
            "feat(article): story",
            pull_request=True,
            idempotency_key=common + "b",
        )

        branches = {
            call.kwargs["head_branch"]
            for call in pub._resume_publication_pull_request.await_args_list
        }
        assert len(branches) == 2

    @pytest.mark.asyncio
    async def test_absence_check_uses_same_parent_sha_and_blocks_collision(self):
        pub = _make_publisher()

        def response(status: int, payload: dict, text: str = "") -> MagicMock:
            item = MagicMock()
            item.status_code = status
            item.json.return_value = payload
            item.text = text
            return item

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.get = AsyncMock(
            side_effect=[
                response(200, {"object": {"sha": "base-after-concurrent-merge"}}),
                response(200, {"tree": {"sha": "tree-after-concurrent-merge"}}),
                response(200, {"sha": "article-that-now-exists"}),
            ]
        )
        mock_client.post = AsyncMock()
        pub._client = mock_client

        with pytest.raises(GitHubPublisherError, match="already exists"):
            await pub.create_commit_with_files(
                [{"path": "content/story.mdx", "content": "replacement"}],
                "feat(article): story",
                must_not_exist_paths=["content/story.mdx"],
            )

        collision_call = mock_client.get.await_args_list[2]
        assert collision_call.kwargs["params"] == {
            "ref": "base-after-concurrent-merge"
        }
        mock_client.post.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_json_update_reads_document_from_exact_parent_sha(self):
        pub = _make_publisher()

        def response(status: int, payload: dict, text: str = "") -> MagicMock:
            item = MagicMock()
            item.status_code = status
            item.json.return_value = payload
            item.text = text
            return item

        layout = base64.b64encode(b'{"hero_2":"newer-concurrent-story"}\n').decode()
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.get = AsyncMock(
            side_effect=[
                response(200, {"object": {"sha": "new-main-parent"}}),
                response(200, {"tree": {"sha": "new-main-tree"}}),
                response(200, {"content": layout}),
            ]
        )
        mock_client.post = AsyncMock(
            return_value=response(500, {}, "stop after same-parent proof")
        )
        pub._client = mock_client

        with pytest.raises(GitHubPublisherError, match="Failed to create blob"):
            await pub.create_commit_with_files(
                [],
                "feat(article): story",
                json_object_updates={
                    "apps/mouth/src/content/homepage-layout.json": {
                        "hero_3": "story"
                    }
                },
            )

        layout_read = mock_client.get.await_args_list[2]
        assert layout_read.kwargs["params"] == {"ref": "new-main-parent"}
        blob_payload = mock_client.post.await_args_list[-1].kwargs["json"]
        resolved = json.loads(base64.b64decode(blob_payload["content"]).decode())
        assert resolved == {
            "hero_2": "newer-concurrent-story",
            "hero_3": "story",
        }


# ---------------------------------------------------------------------------
# _apply_merge_label (B31 P1: the label the LocalCI merger needs)
# ---------------------------------------------------------------------------

_SUITE_AT = "2026-10-17T10:00:05Z"
_LABEL_AT = "2026-10-17T10:00:09Z"


def _resp(status: int = 200, payload: dict | None = None, text: str = "") -> MagicMock:
    item = MagicMock()
    item.status_code = status
    item.json.return_value = payload if payload is not None else {}
    item.text = text
    return item


class _FakeGitHub:
    """Routes the calls `_apply_merge_label` makes; records every request."""

    def __init__(
        self,
        suites: list[list[str]] | None = None,
        label_status: int = 200,
        actor: dict | None = None,
        labelled_at: str = _LABEL_AT,
        role: str = "admin",
        has_label: bool = True,
        events: list[dict] | None = None,
        suites_status: int = 200,
        graphql_misses: int = 0,
    ) -> None:
        self.events = events
        self.suites_status = suites_status
        self.graphql_misses = graphql_misses
        self.graphql_vars: list[dict] = []
        self.suites = list(suites if suites is not None else [[_SUITE_AT]])
        self.label_status = label_status
        self.actor = actor if actor is not None else {"__typename": "User", "login": "owner"}
        self.labelled_at = labelled_at
        self.role = role
        self.has_label = has_label
        self.calls: list[tuple[str, str]] = []
        self.is_closed = False

    async def get(self, url: str, **kwargs):
        self.calls.append(("GET", url))
        if "/check-suites" in url:
            if self.suites_status != 200:
                return _resp(self.suites_status, text="limited")
            stamps = self.suites.pop(0) if len(self.suites) > 1 else self.suites[0]
            return _resp(
                200,
                {
                    "total_count": len(stamps),
                    "check_suites": [{"created_at": x} for x in stamps],
                },
            )
        if "/collaborators/" in url:
            return _resp(200, {"role_name": self.role})
        raise AssertionError(f"unexpected GET {url}")

    async def post(self, url: str, **kwargs):
        self.calls.append(("POST", url))
        if url.endswith("/issues/77/labels"):
            assert kwargs["json"] == {"labels": ["localci:merge-shadow-ok"]}
            return _resp(self.label_status, text="boom")
        if url.endswith("/graphql"):
            self.graphql_vars.append(kwargs["json"]["variables"])
            name = "localci:merge-shadow-ok"
            if self.graphql_misses > 0:
                self.graphql_misses -= 1
                return _resp(200, {"data": {"repository": {"pullRequest": None}}})
            nodes = self.events or [
                {"createdAt": self.labelled_at, "label": {"name": name}, "actor": self.actor}
            ]
            pr = {
                "labels": {"nodes": [{"name": name}] if self.has_label else []},
                "timelineItems": {"nodes": nodes},
            }
            return _resp(200, {"data": {"repository": {"pullRequest": pr}}})
        raise AssertionError(f"unexpected POST {url}")


def _labeller(fake: _FakeGitHub, wait_s: float = 4.0) -> GitHubPublisher:
    pub = _make_publisher()
    pub._client = fake
    pub.MERGE_LABEL_SUITE_WAIT_S = wait_s
    pub.MERGE_LABEL_POLL_S = 0.0
    return pub


@pytest.fixture
def _no_sleep():
    with patch(
        "backend.services.integrations.github_publisher.asyncio.sleep", AsyncMock()
    ) as sleep:
        yield sleep


@pytest.mark.usefixtures("_no_sleep")
class TestApplyMergeLabel:
    @pytest.mark.asyncio
    async def test_normal_path_labels_and_reads_back(self):
        fake = _FakeGitHub()
        assert await _labeller(fake)._apply_merge_label(77, "a" * 40) is True
        assert [m for m, _ in fake.calls].count("POST") == 2  # label + graphql read-back

    @pytest.mark.asyncio
    async def test_waits_for_the_first_check_suite_then_labels(self):
        fake = _FakeGitHub(suites=[[], [], [_SUITE_AT]])
        assert await _labeller(fake)._apply_merge_label(77, "a" * 40) is True
        suite_polls = [u for m, u in fake.calls if "/check-suites" in u]
        assert len(suite_polls) == 3
        first_post = next(i for i, (m, _) in enumerate(fake.calls) if m == "POST")
        assert first_post > 2  # no label written before the suite existed

    @pytest.mark.asyncio
    async def test_no_suite_in_window_is_loud_false_and_writes_nothing(self, caplog):
        fake = _FakeGitHub(suites=[[]])
        pub = _labeller(fake, wait_s=0.0)
        with caplog.at_level("ERROR"):
            assert await pub._apply_merge_label(77, "a" * 40) is False
        assert not [1 for m, _ in fake.calls if m == "POST"]
        assert "NOT applied" in caplog.text

    @pytest.mark.asyncio
    async def test_label_post_failure_is_false_loud_not_raised(self, caplog):
        fake = _FakeGitHub(label_status=403)
        with caplog.at_level("ERROR"):
            assert await _labeller(fake)._apply_merge_label(77, "a" * 40) is False
        assert "POST HTTP 403" in caplog.text

    @pytest.mark.asyncio
    async def test_transport_error_is_false_not_raised(self):
        fake = _FakeGitHub()
        fake.get = AsyncMock(side_effect=RuntimeError("network down"))
        assert await _labeller(fake)._apply_merge_label(77, "a" * 40) is False

    @pytest.mark.asyncio
    async def test_readback_with_bot_actor_is_false(self, caplog):
        fake = _FakeGitHub(actor={"__typename": "Bot", "login": "github-actions"})
        with caplog.at_level("ERROR"):
            assert await _labeller(fake)._apply_merge_label(77, "a" * 40) is False
        assert "not applied by a User" in caplog.text

    @pytest.mark.asyncio
    async def test_readback_before_first_suite_is_false(self):
        fake = _FakeGitHub(labelled_at="2026-10-17T10:00:04Z")
        assert await _labeller(fake)._apply_merge_label(77, "a" * 40) is False

    @pytest.mark.asyncio
    async def test_label_at_the_same_second_as_the_suite_counts(self):
        fake = _FakeGitHub(labelled_at=_SUITE_AT)
        assert await _labeller(fake)._apply_merge_label(77, "a" * 40) is True

    @pytest.mark.asyncio
    async def test_actor_without_admin_or_maintain_is_false(self):
        fake = _FakeGitHub(role="write")
        assert await _labeller(fake)._apply_merge_label(77, "a" * 40) is False

    @pytest.mark.asyncio
    async def test_label_missing_from_pr_after_post_is_false(self):
        fake = _FakeGitHub(has_label=False)
        assert await _labeller(fake)._apply_merge_label(77, "a" * 40) is False


_NAME = "localci:merge-shadow-ok"
_USER = {"__typename": "User", "login": "owner"}
_BOT = {"__typename": "Bot", "login": "github-actions"}


def _event(at: str, actor: dict) -> dict:
    return {"createdAt": at, "label": {"name": _NAME}, "actor": actor}


@pytest.mark.usefixtures("_no_sleep")
class TestApplyMergeLabelSurvivors:
    @pytest.mark.asyncio
    async def test_maintain_role_counts(self):
        assert await _labeller(_FakeGitHub(role="maintain"))._apply_merge_label(77, "a" * 40)

    @pytest.mark.asyncio
    async def test_last_labeled_event_is_the_one_judged_bad_last(self):
        events = [_event(_LABEL_AT, _USER), _event(_LABEL_AT, _BOT)]
        assert not await _labeller(_FakeGitHub(events=events))._apply_merge_label(77, "a" * 40)

    @pytest.mark.asyncio
    async def test_last_labeled_event_is_the_one_judged_good_last(self):
        events = [_event("2026-10-17T10:00:01Z", _USER), _event(_LABEL_AT, _USER)]
        assert await _labeller(_FakeGitHub(events=events))._apply_merge_label(77, "a" * 40)

    @pytest.mark.asyncio
    async def test_poll_sleeps_between_suite_reads(self, _no_sleep):
        fake = _FakeGitHub(suites=[[], [], [_SUITE_AT]])
        pub = _labeller(fake)
        pub.MERGE_LABEL_POLL_S = 2.0
        assert await pub._apply_merge_label(77, "a" * 40)
        assert [c.args for c in _no_sleep.await_args_list][:2] == [(2.0,), (2.0,)]

    @pytest.mark.asyncio
    async def test_readback_is_retried_for_timeline_lag(self, _no_sleep):
        fake = _FakeGitHub(graphql_misses=2)
        assert await _labeller(fake)._apply_merge_label(77, "a" * 40)
        assert len(fake.graphql_vars) == 3

    @pytest.mark.asyncio
    async def test_readback_gives_up_after_the_bounded_tries(self):
        fake = _FakeGitHub(graphql_misses=99)
        assert not await _labeller(fake)._apply_merge_label(77, "a" * 40)
        assert len(fake.graphql_vars) == 3

    @pytest.mark.asyncio
    async def test_owner_and_repo_are_not_swapped(self):
        fake = _FakeGitHub()
        await _labeller(fake)._apply_merge_label(77, "a" * 40)
        assert fake.graphql_vars == [{"o": "org", "r": "repo", "n": 77}]
        assert all("/repos/org/repo/" in u for m, u in fake.calls if "graphql" not in u)

    @pytest.mark.asyncio
    async def test_fractional_second_timestamp_is_unreadable_like_the_merger(self):
        fake = _FakeGitHub(labelled_at="2026-10-17T10:00:09.500Z")
        assert not await _labeller(fake)._apply_merge_label(77, "a" * 40)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("login", ["-lead", "a_b", "x" * 40, "ok\n"])
    async def test_login_shape_is_the_mergers(self, login):
        fake = _FakeGitHub(actor={"__typename": "User", "login": login})
        assert not await _labeller(fake)._apply_merge_label(77, "a" * 40)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status", [403, 429])
    async def test_rate_limit_is_named_not_reported_as_no_suite(self, status, caplog):
        fake = _FakeGitHub(suites_status=status)
        with caplog.at_level("ERROR"):
            assert not await _labeller(fake)._apply_merge_label(77, "a" * 40)
        assert "rate limit or permission" in caplog.text
        assert "no check suite" not in caplog.text
        assert not [1 for m, _ in fake.calls if m == "POST"]


class TestMergeLabelDeadline:
    @pytest.mark.asyncio
    async def test_whole_labelling_is_bounded_by_one_deadline(self, caplog):
        fake = _FakeGitHub()

        async def hang(url, **kwargs):
            await asyncio.Event().wait()

        fake.get = hang
        pub = _labeller(fake)
        pub.MERGE_LABEL_DEADLINE_S = 0.05
        with caplog.at_level("ERROR"):
            assert await pub._apply_merge_label(77, "a" * 40) is False
        assert "deadline" in caplog.text

    def test_worst_case_is_stated_and_fits_the_request(self):
        assert GitHubPublisher.MERGE_LABEL_DEADLINE_S <= 20.0
        assert GitHubPublisher.MERGE_LABEL_CALL_TIMEOUT_S <= 5.0


class TestMergerParity:
    def test_timestamp_and_login_shapes_equal_merger_source(self):
        from backend.services.integrations import github_publisher as gp

        root = next(
            (
                q
                for q in Path(__file__).resolve().parents
                if (q / "scripts/localci/merger.py").is_file()
            ),
            None,
        )
        assert gp._TS_RE.pattern == r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"
        assert gp._LOGIN_RE.pattern == "[A-Za-z0-9][A-Za-z0-9-]{0,38}"
        if root is None:
            pytest.skip("scripts/localci/merger.py not in this checkout")
        text = (root / "scripts/localci/merger.py").read_text()
        ts = re.search(r'^_TS_RE = re\.compile\(r"(.*?)"\)', text, re.M)
        login = re.search(r'^_LOGIN_RE = re\.compile\(r"(.*?)"\)', text, re.M)
        assert ts and login
        assert ts.group(1) == gp._TS_RE.pattern
        assert login.group(1) == gp._LOGIN_RE.pattern


class TestPublishPathsApplyTheLabel:
    @pytest.mark.asyncio
    async def test_create_path_labels_after_auto_merge_and_reports_it(self):
        pub = _make_publisher()
        order: list[str] = []
        client = AsyncMock()
        client.is_closed = False
        client.get = AsyncMock(
            side_effect=[
                _resp(200, {"object": {"sha": "b" * 40}}),
                _resp(200, {"tree": {"sha": "t" * 40}}),
            ]
        )
        client.post = AsyncMock(
            side_effect=[
                _resp(201, {"sha": "blob"}),
                _resp(201, {"sha": "tree"}),
                _resp(201, {"sha": "c" * 40}),
            ]
        )
        pub._client = client
        pub._create_branch_ref = AsyncMock()
        pub._create_pull_request = AsyncMock(
            return_value={"number": 77, "node_id": "PR_x", "html_url": "u"}
        )

        async def auto_merge(node_id):
            order.append("auto_merge")
            return True

        async def label(number, sha):
            order.append(f"label:{number}:{sha}")
            return True

        pub._enable_auto_merge = auto_merge
        pub._apply_merge_label = label

        result = await pub.create_commit_with_files(
            [{"path": "content/story.mdx", "content": "story"}],
            "feat(article): story",
            pull_request=True,
        )

        assert order == ["auto_merge", f"label:77:{'c' * 40}"]
        assert result["merge_label_applied"] is True
        assert result["auto_merge_enabled"] is True

    @pytest.mark.asyncio
    async def test_create_path_survives_a_failed_label(self):
        pub = _make_publisher()
        client = AsyncMock()
        client.is_closed = False
        client.get = AsyncMock(
            side_effect=[
                _resp(200, {"object": {"sha": "b" * 40}}),
                _resp(200, {"tree": {"sha": "t" * 40}}),
            ]
        )
        client.post = AsyncMock(
            side_effect=[
                _resp(201, {"sha": "blob"}),
                _resp(201, {"sha": "tree"}),
                _resp(201, {"sha": "c" * 40}),
            ]
        )
        pub._client = client
        pub._create_branch_ref = AsyncMock()
        pub._create_pull_request = AsyncMock(
            return_value={"number": 77, "node_id": "PR_x", "html_url": "u"}
        )
        pub._enable_auto_merge = AsyncMock(return_value=True)
        pub._apply_merge_label = AsyncMock(return_value=False)

        result = await pub.create_commit_with_files(
            [{"path": "content/story.mdx", "content": "story"}],
            "feat(article): story",
            pull_request=True,
        )

        assert result["success"] is True
        assert result["merge_label_applied"] is False

    @pytest.mark.asyncio
    async def test_resume_path_labels_the_recreated_pr(self):
        pub = _make_publisher()
        fingerprint = "f" * 64
        pub._find_pull_request = AsyncMock(return_value=None)
        pub._get_branch_commit_sha = AsyncMock(return_value="d" * 40)
        pub._get_commit_message = AsyncMock(
            return_value=f"feat\n\n{pub._fingerprint_marker(fingerprint)}"
        )
        pub._create_pull_request = AsyncMock(
            return_value={"number": 78, "node_id": "PR_y", "html_url": "u"}
        )
        pub._enable_auto_merge = AsyncMock(return_value=True)
        pub._apply_merge_label = AsyncMock(return_value=True)

        result = await pub._resume_publication_pull_request(
            head_branch="auto-publish/k",
            base_branch="main",
            message="feat: x",
            files_count=1,
            publication_fingerprint=fingerprint,
        )

        pub._apply_merge_label.assert_awaited_once_with(78, "d" * 40)
        assert result["merge_label_applied"] is True
        assert result["idempotent"] is True

    @pytest.mark.asyncio
    async def test_resume_path_survives_a_failed_label(self):
        pub = _make_publisher()
        fingerprint = "f" * 64
        pub._find_pull_request = AsyncMock(return_value=None)
        pub._get_branch_commit_sha = AsyncMock(return_value="d" * 40)
        pub._get_commit_message = AsyncMock(
            return_value=f"feat\n\n{pub._fingerprint_marker(fingerprint)}"
        )
        pub._create_pull_request = AsyncMock(
            return_value={"number": 78, "node_id": "PR_y", "html_url": "u"}
        )
        pub._enable_auto_merge = AsyncMock(return_value=True)
        pub._apply_merge_label = AsyncMock(return_value=False)

        result = await pub._resume_publication_pull_request(
            head_branch="auto-publish/k",
            base_branch="main",
            message="feat: x",
            files_count=1,
            publication_fingerprint=fingerprint,
        )

        assert result["success"] is True
        assert result["merge_label_applied"] is False
