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

import base64
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
    token: str = "ghp_fake", owner: str = "org", repo: str = "repo",
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
        await pub.close()  # must not raise


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
