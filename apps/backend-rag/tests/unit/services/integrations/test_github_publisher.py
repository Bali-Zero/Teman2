"""
Unit tests for GitHubPublisher service.

Tests GitHub API interactions for article publishing workflow.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.integrations.github_publisher import (
    GitHubPublisher,
    GitHubPublisherError,
)


class TestGitHubPublisherInit:
    """Tests for GitHubPublisher initialization."""

    def test_init_with_explicit_params(self):
        """Test initialization with explicit parameters."""
        publisher = GitHubPublisher(
            token="test-token",
            owner="test-owner",
            repo="test-repo",
        )
        assert publisher.token == "test-token"
        assert publisher.owner == "test-owner"
        assert publisher.repo == "test-repo"

    def test_init_with_none_params_uses_settings(self):
        """Test initialization falls back to settings when params are None."""
        with patch("backend.services.integrations.github_publisher.settings") as mock_settings:
            mock_settings.github_token = "settings-token"
            mock_settings.github_owner = "settings-owner"
            mock_settings.github_repo = "settings-repo"

            publisher = GitHubPublisher()
            assert publisher.token == "settings-token"
            assert publisher.owner == "settings-owner"
            assert publisher.repo == "settings-repo"

    def test_init_logs_warning_when_token_missing(self, caplog):
        """Test that warning is logged when token is not configured."""
        with patch("backend.services.integrations.github_publisher.settings") as mock_settings:
            mock_settings.github_token = None
            mock_settings.github_owner = "owner"
            mock_settings.github_repo = "repo"

            GitHubPublisher()
            assert "GitHub token not configured" in caplog.text


class TestGitHubPublisherIsConfigured:
    """Tests for is_configured property."""

    def test_is_configured_returns_true_when_all_set(self):
        """Test is_configured returns True when all params are set."""
        publisher = GitHubPublisher(
            token="token",
            owner="owner",
            repo="repo",
        )
        assert publisher.is_configured is True

    def test_is_configured_returns_false_when_token_missing(self):
        """Test is_configured returns False when token is missing."""
        with patch("backend.services.integrations.github_publisher.settings") as mock_settings:
            mock_settings.github_token = None
            mock_settings.github_owner = None
            mock_settings.github_repo = None

            publisher = GitHubPublisher(
                token=None,
                owner="owner",
                repo="repo",
            )
            assert publisher.is_configured is False

    def test_is_configured_returns_false_when_owner_missing(self):
        """Test is_configured returns False when owner is missing."""
        with patch("backend.services.integrations.github_publisher.settings") as mock_settings:
            mock_settings.github_token = None
            mock_settings.github_owner = None
            mock_settings.github_repo = None

            publisher = GitHubPublisher(
                token="token",
                owner=None,
                repo="repo",
            )
            assert publisher.is_configured is False

    def test_is_configured_returns_false_when_repo_missing(self):
        """Test is_configured returns False when repo is missing."""
        with patch("backend.services.integrations.github_publisher.settings") as mock_settings:
            mock_settings.github_token = None
            mock_settings.github_owner = None
            mock_settings.github_repo = None

            publisher = GitHubPublisher(
                token="token",
                owner="owner",
                repo=None,
            )
            assert publisher.is_configured is False


class TestGitHubPublisherHeaders:
    """Tests for _get_headers method."""

    def test_get_headers_includes_bearer_token(self):
        """Test headers include Bearer token."""
        publisher = GitHubPublisher(token="my-token", owner="o", repo="r")
        headers = publisher._get_headers()
        assert headers["Authorization"] == "Bearer my-token"

    def test_get_headers_includes_accept_header(self):
        """Test headers include Accept header."""
        publisher = GitHubPublisher(token="t", owner="o", repo="r")
        headers = publisher._get_headers()
        assert headers["Accept"] == "application/vnd.github.v3+json"

    def test_get_headers_includes_api_version(self):
        """Test headers include API version."""
        publisher = GitHubPublisher(token="t", owner="o", repo="r")
        headers = publisher._get_headers()
        assert headers["X-GitHub-Api-Version"] == "2022-11-28"


class TestCheckFileExists:
    """Tests for check_file_exists method."""

    @pytest.fixture
    def publisher(self):
        return GitHubPublisher(token="token", owner="owner", repo="repo")

    @pytest.mark.asyncio
    async def test_check_file_exists_returns_true_on_200(self, publisher):
        """Test returns True when file exists (200 response)."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)

        with patch.object(publisher, "_get_client", return_value=mock_client_instance):
            result = await publisher.check_file_exists("path/to/file.mdx")
        assert result is True

    @pytest.mark.asyncio
    async def test_check_file_exists_returns_false_on_404(self, publisher):
        """Test returns False when file doesn't exist (404 response)."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)

        with patch.object(publisher, "_get_client", return_value=mock_client_instance):
            result = await publisher.check_file_exists("path/to/file.mdx")
        assert result is False

    @pytest.mark.asyncio
    async def test_check_file_exists_raises_when_not_configured(self):
        """Test raises error when not configured."""
        with patch("backend.services.integrations.github_publisher.settings") as mock_settings:
            mock_settings.github_token = None
            mock_settings.github_owner = None
            mock_settings.github_repo = None

            publisher = GitHubPublisher(token=None, owner="o", repo="r")

            with pytest.raises(GitHubPublisherError, match="not configured"):
                await publisher.check_file_exists("path/to/file.mdx")

    @pytest.mark.asyncio
    async def test_check_file_exists_uses_correct_url(self, publisher):
        """Test uses correct GitHub API URL."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)

        with patch.object(publisher, "_get_client", return_value=mock_client_instance):
            await publisher.check_file_exists("path/to/file.mdx", branch="develop")

        mock_client_instance.get.assert_called_once()
        call_args = mock_client_instance.get.call_args
        assert "repos/owner/repo/contents/path/to/file.mdx" in call_args[0][0]
        assert call_args[1]["params"]["ref"] == "develop"


class TestGetFileSha:
    """Tests for get_file_sha method."""

    @pytest.fixture
    def publisher(self):
        return GitHubPublisher(token="token", owner="owner", repo="repo")

    @pytest.mark.asyncio
    async def test_get_file_sha_returns_sha_on_200(self, publisher):
        """Test returns SHA when file exists."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"sha": "abc123def456"}

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)

        with patch.object(publisher, "_get_client", return_value=mock_client_instance):
            result = await publisher.get_file_sha("path/to/file.mdx")
            assert result == "abc123def456"

    @pytest.mark.asyncio
    async def test_get_file_sha_returns_none_on_404(self, publisher):
        """Test returns None when file doesn't exist."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)

        with patch.object(publisher, "_get_client", return_value=mock_client_instance):
            result = await publisher.get_file_sha("path/to/file.mdx")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_file_sha_raises_when_not_configured(self):
        """Test raises error when not configured."""
        with patch("backend.services.integrations.github_publisher.settings") as mock_settings:
            mock_settings.github_token = None
            mock_settings.github_owner = None
            mock_settings.github_repo = None

            publisher = GitHubPublisher(token=None, owner="o", repo="r")

            with pytest.raises(GitHubPublisherError, match="not configured"):
                await publisher.get_file_sha("path/to/file.mdx")


class TestUploadFile:
    """Tests for upload_file method."""

    @pytest.fixture
    def publisher(self):
        return GitHubPublisher(token="token", owner="owner", repo="repo")

    @pytest.mark.asyncio
    async def test_upload_file_creates_new_file(self, publisher):
        """Test creates new file when it doesn't exist."""
        # Mock get_file_sha to return None (file doesn't exist)
        mock_get_response = MagicMock()
        mock_get_response.status_code = 404

        # Mock PUT response
        mock_put_response = MagicMock()
        mock_put_response.status_code = 201
        mock_put_response.json.return_value = {
            "content": {"sha": "content-sha"},
            "commit": {"sha": "commit-sha-123", "html_url": "https://github.com/..."},
        }

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_get_response)
        mock_client_instance.put = AsyncMock(return_value=mock_put_response)

        with patch.object(publisher, "_get_client", return_value=mock_client_instance):
            result = await publisher.upload_file(
                path="path/to/file.mdx",
                content="# Hello World",
                message="Add file",
            )

            assert result["success"] is True
            assert result["commit_sha"] == "commit-sha-123"

    @pytest.mark.asyncio
    async def test_upload_file_updates_existing_file(self, publisher):
        """Test updates file when it already exists (includes SHA)."""
        # Mock get_file_sha to return existing SHA
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {"sha": "existing-sha"}

        # Mock PUT response
        mock_put_response = MagicMock()
        mock_put_response.status_code = 200
        mock_put_response.json.return_value = {
            "content": {"sha": "new-content-sha"},
            "commit": {"sha": "commit-sha-456", "html_url": "https://github.com/..."},
        }

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_get_response)
        mock_client_instance.put = AsyncMock(return_value=mock_put_response)

        with patch.object(publisher, "_get_client", return_value=mock_client_instance):
            result = await publisher.upload_file(
                path="path/to/file.mdx",
                content="# Updated Content",
                message="Update file",
            )

            # Verify SHA was included in payload
            put_call = mock_client_instance.put.call_args
            payload = put_call[1]["json"]
            assert payload["sha"] == "existing-sha"
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_upload_file_handles_bytes_content(self, publisher):
        """Test handles bytes content correctly."""
        mock_get_response = MagicMock()
        mock_get_response.status_code = 404

        mock_put_response = MagicMock()
        mock_put_response.status_code = 201
        mock_put_response.json.return_value = {
            "content": {"sha": "sha"},
            "commit": {"sha": "commit-sha", "html_url": "url"},
        }

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_get_response)
        mock_client_instance.put = AsyncMock(return_value=mock_put_response)

        with patch.object(publisher, "_get_client", return_value=mock_client_instance):
            image_bytes = b"\x89PNG\r\n\x1a\n"  # PNG magic bytes
            result = await publisher.upload_file(
                path="image.png",
                content=image_bytes,
                message="Add image",
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_upload_file_raises_on_api_error(self, publisher):
        """Test raises GitHubPublisherError on API error."""
        mock_get_response = MagicMock()
        mock_get_response.status_code = 404

        mock_put_response = MagicMock()
        mock_put_response.status_code = 422
        mock_put_response.text = "Validation failed"
        mock_put_response.json.return_value = {"message": "Validation failed"}

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_get_response)
        mock_client_instance.put = AsyncMock(return_value=mock_put_response)

        with patch.object(publisher, "_get_client", return_value=mock_client_instance):
            with pytest.raises(GitHubPublisherError, match="Failed to upload file"):
                await publisher.upload_file(
                    path="file.mdx",
                    content="content",
                    message="msg",
                )

    @pytest.mark.asyncio
    async def test_upload_file_raises_when_not_configured(self):
        """Test raises error when not configured."""
        with patch("backend.services.integrations.github_publisher.settings") as mock_settings:
            mock_settings.github_token = None
            mock_settings.github_owner = None
            mock_settings.github_repo = None

            publisher = GitHubPublisher(token=None, owner="o", repo="r")

            with pytest.raises(GitHubPublisherError, match="not configured"):
                await publisher.upload_file("path", "content", "message")


class TestCreateCommitWithFiles:
    """Tests for create_commit_with_files method (atomic multi-file commit)."""

    @pytest.fixture
    def publisher(self):
        return GitHubPublisher(token="token", owner="owner", repo="repo")

    @pytest.fixture
    def mock_git_api_responses(self):
        """Create mock responses for Git Data API flow."""
        # Step 1: Get branch ref
        ref_response = MagicMock()
        ref_response.status_code = 200
        ref_response.json.return_value = {"object": {"sha": "current-commit-sha"}}

        # Step 2: Get commit to get tree SHA
        commit_response = MagicMock()
        commit_response.status_code = 200
        commit_response.json.return_value = {"tree": {"sha": "current-tree-sha"}}

        # Step 3: Create blob
        blob_response = MagicMock()
        blob_response.status_code = 201
        blob_response.json.return_value = {"sha": "blob-sha"}

        # Step 4: Create tree
        tree_response = MagicMock()
        tree_response.status_code = 201
        tree_response.json.return_value = {"sha": "new-tree-sha"}

        # Step 5: Create commit
        create_commit_response = MagicMock()
        create_commit_response.status_code = 201
        create_commit_response.json.return_value = {"sha": "new-commit-sha"}

        # Step 6: Update ref
        update_ref_response = MagicMock()
        update_ref_response.status_code = 200
        update_ref_response.json.return_value = {"object": {"sha": "new-commit-sha"}}

        return {
            "ref": ref_response,
            "commit": commit_response,
            "blob": blob_response,
            "tree": tree_response,
            "create_commit": create_commit_response,
            "update_ref": update_ref_response,
        }

    @pytest.mark.asyncio
    async def test_create_commit_with_files_success(self, publisher, mock_git_api_responses):
        """Test successfully creates atomic commit with multiple files."""
        mock_client_instance = AsyncMock()

        # Configure responses for each API call
        mock_client_instance.get = AsyncMock(
            side_effect=[
                mock_git_api_responses["ref"],
                mock_git_api_responses["commit"],
            ]
        )
        mock_client_instance.post = AsyncMock(
            side_effect=[
                mock_git_api_responses["blob"],
                mock_git_api_responses["blob"],  # Called twice for 2 files
                mock_git_api_responses["tree"],
                mock_git_api_responses["create_commit"],
            ]
        )
        mock_client_instance.patch = AsyncMock(
            return_value=mock_git_api_responses["update_ref"]
        )

        with patch.object(publisher, "_get_client", return_value=mock_client_instance):
            files = [
                {"path": "file1.mdx", "content": "content1"},
                {"path": "file2.png", "content": b"binary-content"},
            ]

            result = await publisher.create_commit_with_files(
                files=files,
                message="Add multiple files",
                branch="main",
            )

            assert result["success"] is True
            assert result["commit_sha"] == "new-commit-sha"
            assert result["files_count"] == 2
            assert result["branch"] == "main"

    @pytest.mark.asyncio
    async def test_create_commit_with_files_raises_on_ref_error(self, publisher):
        """Test raises error when getting branch ref fails."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Branch not found"

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)

        with patch.object(publisher, "_get_client", return_value=mock_client_instance):
            with pytest.raises(GitHubPublisherError, match="Failed to get branch ref"):
                await publisher.create_commit_with_files(
                    files=[{"path": "file.mdx", "content": "content"}],
                    message="msg",
                )

    @pytest.mark.asyncio
    async def test_create_commit_with_files_raises_when_not_configured(self):
        """Test raises error when not configured."""
        with patch("backend.services.integrations.github_publisher.settings") as mock_settings:
            mock_settings.github_token = None
            mock_settings.github_owner = None
            mock_settings.github_repo = None

            publisher = GitHubPublisher(token=None, owner="o", repo="r")

            with pytest.raises(GitHubPublisherError, match="not configured"):
                await publisher.create_commit_with_files(
                    files=[{"path": "file", "content": "content"}],
                    message="message",
                )


class TestGitHubPublisherSingleton:
    """Tests for singleton instance."""

    def test_singleton_is_github_publisher_instance(self):
        """Test that github_publisher is a GitHubPublisher instance."""
        from backend.services.integrations.github_publisher import github_publisher

        assert isinstance(github_publisher, GitHubPublisher)
