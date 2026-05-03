"""
GitHub Publisher Service

Handles publishing articles to the GitHub repository via the GitHub API.
Creates MDX files and commits them to trigger Vercel auto-deploy.

Usage:
    from backend.services.integrations.github_publisher import github_publisher

    # Check if configured
    if github_publisher.is_configured:
        result = await github_publisher.upload_file(
            path="path/to/file.mdx",
            content="# Content",
            message="Add article",
        )

    # Or atomic multi-file commit
    result = await github_publisher.create_commit_with_files(
        files=[
            {"path": "file1.mdx", "content": "content1"},
            {"path": "file2.jpg", "content": image_bytes},
        ],
        message="Add article with image",
    )
"""

import base64
import logging
import re
import time
from typing import Any

import httpx

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class GitHubPublisherError(Exception):
    """Custom exception for GitHub Publisher errors"""

    pass


class GitHubPublisher:
    """
    Service for publishing files to GitHub repository.

    Uses the GitHub Contents API to create/update files and commits.
    """

    BASE_URL = "https://api.github.com"

    def __init__(
        self,
        token: str | None = None,
        owner: str | None = None,
        repo: str | None = None,
    ) -> None:
        """
        Initialize GitHub Publisher.

        Args:
            token: GitHub Personal Access Token (defaults to settings)
            owner: Repository owner (defaults to settings)
            repo: Repository name (defaults to settings)
        """
        self.token = token or settings.github_token
        self.owner = owner or settings.github_owner
        self.repo = repo or settings.github_repo
        self._client: httpx.AsyncClient | None = None

        if not self.token:
            logger.warning("GitHub token not configured - publishing will fail")

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create the shared async client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._client

    async def close(self) -> None:
        """Close the internal async client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        logger.info("GitHubPublisher HTTP client closed.")

    @property
    def is_configured(self) -> bool:
        """Check if GitHub API is configured."""
        return bool(self.token and self.owner and self.repo)

    def _get_headers(self) -> dict[str, str]:
        """Get headers for GitHub API requests."""
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    @staticmethod
    def _validate_path(path: str) -> str:
        """
        Validate and normalize a repository-relative file path.

        Prevents path traversal attacks (e.g. ``../../etc/passwd``) by
        rejecting paths that contain ``..`` segments or an absolute leading
        slash after normalization.

        Args:
            path: Repository-relative file path supplied by the caller.

        Returns:
            The original path, stripped of any leading slash.

        Raises:
            ValueError: If the path contains traversal sequences or invalid
                characters that could be exploited in the GitHub API URL.
        """
        # Strip accidental leading slash
        normalized = path.lstrip("/")

        # Reject path traversal sequences
        if re.search(r"(^|/)\.\.(\/|$)", normalized):
            raise ValueError(f"Invalid repository path (traversal detected): {path!r}")

        # Reject null bytes or other control characters
        if any(ord(c) < 0x20 for c in normalized):
            raise ValueError(f"Invalid repository path (control characters): {path!r}")

        if not normalized:
            raise ValueError("Repository path must not be empty.")

        return normalized

    async def check_file_exists(self, path: str, branch: str = "main") -> bool:
        """
        Check if a file exists in the repository.

        Args:
            path: File path relative to repository root
            branch: Branch name (default: main)

        Returns:
            True if file exists, False otherwise
        """
        if not self.is_configured:
            raise GitHubPublisherError("GitHub API not configured")

        path = self._validate_path(path)
        url = f"{self.BASE_URL}/repos/{self.owner}/{self.repo}/contents/{path}"
        params = {"ref": branch}

        logger.debug(f"Checking file exists: {path} (branch: {branch})")

        client = self._get_client()
        response = await client.get(
            url,
            headers=self._get_headers(),
            params=params,
            timeout=30.0,
        )

        exists = response.status_code == 200
        logger.debug(f"File exists check: {path} → {exists}")
        return exists

    async def get_file_sha(self, path: str, branch: str = "main") -> str | None:
        """
        Get the SHA of an existing file (needed for updates).

        Args:
            path: File path relative to repository root
            branch: Branch name (default: main)

        Returns:
            File SHA if exists, None otherwise
        """
        if not self.is_configured:
            raise GitHubPublisherError("GitHub API not configured")

        path = self._validate_path(path)
        url = f"{self.BASE_URL}/repos/{self.owner}/{self.repo}/contents/{path}"
        params = {"ref": branch}

        logger.debug(f"Getting file SHA: {path}")

        client = self._get_client()
        response = await client.get(
            url,
            headers=self._get_headers(),
            params=params,
            timeout=30.0,
        )

        if response.status_code == 200:
            sha = response.json().get("sha")
            logger.debug(f"File SHA found: {path} → {sha[:7] if sha else 'N/A'}")
            return sha

        logger.debug(f"File not found (no SHA): {path}")
        return None

    async def upload_file(
        self,
        path: str,
        content: bytes | str,
        message: str,
        branch: str = "main",
    ) -> dict[str, Any]:
        """
        Upload/create a single file to the repository.

        Args:
            path: File path relative to repository root
            content: File content (bytes or string)
            message: Commit message
            branch: Branch name (default: main)

        Returns:
            GitHub API response with commit info
        """
        if not self.is_configured:
            raise GitHubPublisherError("GitHub API not configured")

        path = self._validate_path(path)
        start_time = time.time()
        url = f"{self.BASE_URL}/repos/{self.owner}/{self.repo}/contents/{path}"

        # Encode content to base64
        content_bytes = content.encode("utf-8") if isinstance(content, str) else content
        content_base64 = base64.b64encode(content_bytes).decode("utf-8")
        content_size_kb = len(content_bytes) / 1024

        logger.info(f"Uploading file: {path} ({content_size_kb:.1f} KB)")

        # Check if file exists (need SHA for update)
        existing_sha = await self.get_file_sha(path, branch)
        is_update = existing_sha is not None

        payload = {
            "message": message,
            "content": content_base64,
            "branch": branch,
        }

        if existing_sha:
            payload["sha"] = existing_sha
            logger.debug(f"Updating existing file (SHA: {existing_sha[:7]})")

        client = self._get_client()
        response = await client.put(
            url,
            headers=self._get_headers(),
            json=payload,
            timeout=60.0,
        )

        elapsed_ms = (time.time() - start_time) * 1000

        if response.status_code not in (200, 201):
            error_detail = response.json().get("message", response.text)
            logger.error(
                f"GitHub API error uploading {path}: {error_detail}",
                extra={
                    "path": path,
                    "status_code": response.status_code,
                    "elapsed_ms": elapsed_ms,
                },
            )
            raise GitHubPublisherError(f"Failed to upload file: {error_detail}")

        result = response.json()
        commit_sha = result["commit"]["sha"]

        logger.info(
            f"File {'updated' if is_update else 'created'}: {path}",
            extra={
                "path": path,
                "commit_sha": commit_sha[:7],
                "size_kb": content_size_kb,
                "elapsed_ms": elapsed_ms,
                "is_update": is_update,
            },
        )

        return {
            "success": True,
            "path": path,
            "sha": result["content"]["sha"],
            "commit_sha": commit_sha,
            "commit_url": result["commit"]["html_url"],
        }

    async def create_commit_with_files(
        self,
        files: list[dict[str, Any]],
        message: str,
        branch: str = "main",
    ) -> dict[str, Any]:
        """
        Create a single commit with multiple files.

        Uses the Git Data API for atomic commits with multiple files.

        Args:
            files: List of dicts with 'path' and 'content' keys
            message: Commit message
            branch: Branch name (default: main)

        Returns:
            Commit info
        """
        if not self.is_configured:
            raise GitHubPublisherError("GitHub API not configured")

        # Validate all paths up front before touching the GitHub API.
        for file_info in files:
            file_info["path"] = self._validate_path(file_info["path"])

        start_time = time.time()
        file_paths = [f["path"] for f in files]
        total_size_kb = (
            sum(
                len(f["content"].encode("utf-8") if isinstance(f["content"], str) else f["content"])
                for f in files
            )
            / 1024
        )

        logger.info(
            f"Creating atomic commit with {len(files)} files ({total_size_kb:.1f} KB total)",
            extra={
                "files": file_paths,
                "branch": branch,
                "total_size_kb": total_size_kb,
            },
        )

        client = self._get_client()
        # Step 1: Get the current commit SHA of the branch
        logger.debug(f"Step 1/6: Getting branch ref for '{branch}'")
        ref_url = f"{self.BASE_URL}/repos/{self.owner}/{self.repo}/git/refs/heads/{branch}"
        ref_response = await client.get(
            ref_url,
            headers=self._get_headers(),
            timeout=30.0,
        )

        if ref_response.status_code != 200:
            logger.error(f"Failed to get branch ref: {ref_response.text}")
            raise GitHubPublisherError(f"Failed to get branch ref: {ref_response.text}")

        current_commit_sha = ref_response.json()["object"]["sha"]
        logger.debug(f"Current commit SHA: {current_commit_sha[:7]}")

        # Step 2: Get the current tree SHA
        logger.debug("Step 2/6: Getting current tree SHA")
        commit_url = (
            f"{self.BASE_URL}/repos/{self.owner}/{self.repo}/git/commits/{current_commit_sha}"
        )
        commit_response = await client.get(
            commit_url,
            headers=self._get_headers(),
            timeout=30.0,
        )

        if commit_response.status_code != 200:
            logger.error(f"Failed to get commit: {commit_response.text}")
            raise GitHubPublisherError(f"Failed to get commit: {commit_response.text}")

        current_tree_sha = commit_response.json()["tree"]["sha"]
        logger.debug(f"Current tree SHA: {current_tree_sha[:7]}")

        # Step 3: Create blobs for each file
        logger.debug(f"Step 3/6: Creating {len(files)} blobs")
        tree_items = []
        for idx, file_info in enumerate(files):
            path = file_info["path"]
            content = file_info["content"]

            # Encode content to base64
            if isinstance(content, str):
                content = content.encode("utf-8")
            content_base64 = base64.b64encode(content).decode("utf-8")

            # Create blob
            blob_url = f"{self.BASE_URL}/repos/{self.owner}/{self.repo}/git/blobs"
            blob_response = await client.post(
                blob_url,
                headers=self._get_headers(),
                json={"content": content_base64, "encoding": "base64"},
                timeout=30.0,
            )

            if blob_response.status_code != 201:
                logger.error(f"Failed to create blob for {path}: {blob_response.text}")
                raise GitHubPublisherError(
                    f"Failed to create blob for {path}: {blob_response.text}",
                )

            blob_sha = blob_response.json()["sha"]
            logger.debug(f"  Blob {idx + 1}/{len(files)}: {path} → {blob_sha[:7]}")

            tree_items.append(
                {
                    "path": path,
                    "mode": "100644",  # Regular file
                    "type": "blob",
                    "sha": blob_sha,
                },
            )

        # Step 4: Create new tree
        logger.debug("Step 4/6: Creating new tree")
        tree_url = f"{self.BASE_URL}/repos/{self.owner}/{self.repo}/git/trees"
        tree_response = await client.post(
            tree_url,
            headers=self._get_headers(),
            json={"base_tree": current_tree_sha, "tree": tree_items},
            timeout=30.0,
        )

        if tree_response.status_code != 201:
            logger.error(f"Failed to create tree: {tree_response.text}")
            raise GitHubPublisherError(f"Failed to create tree: {tree_response.text}")

        new_tree_sha = tree_response.json()["sha"]
        logger.debug(f"New tree SHA: {new_tree_sha[:7]}")

        # Step 5: Create commit
        logger.debug("Step 5/6: Creating commit")
        create_commit_url = f"{self.BASE_URL}/repos/{self.owner}/{self.repo}/git/commits"
        commit_create_response = await client.post(
            create_commit_url,
            headers=self._get_headers(),
            json={
                "message": message,
                "tree": new_tree_sha,
                "parents": [current_commit_sha],
            },
            timeout=30.0,
        )

        if commit_create_response.status_code != 201:
            logger.error(f"Failed to create commit: {commit_create_response.text}")
            raise GitHubPublisherError(f"Failed to create commit: {commit_create_response.text}")

        new_commit_sha = commit_create_response.json()["sha"]
        logger.debug(f"New commit SHA: {new_commit_sha[:7]}")

        # Step 6: Update branch reference
        logger.debug("Step 6/6: Updating branch reference")
        update_ref_response = await client.patch(
            ref_url,
            headers=self._get_headers(),
            json={"sha": new_commit_sha, "force": True},
            timeout=30.0,
        )

        if update_ref_response.status_code != 200:
            logger.error(f"Failed to update branch ref: {update_ref_response.text}")
            raise GitHubPublisherError(f"Failed to update branch ref: {update_ref_response.text}")

        elapsed_ms = (time.time() - start_time) * 1000

        logger.info(
            f"Atomic commit created: {new_commit_sha[:7]} ({len(files)} files, {elapsed_ms:.0f}ms)",
            extra={
                "commit_sha": new_commit_sha,
                "files_count": len(files),
                "branch": branch,
                "elapsed_ms": elapsed_ms,
                "total_size_kb": total_size_kb,
            },
        )

        return {
            "success": True,
            "commit_sha": new_commit_sha,
            "files_count": len(files),
            "branch": branch,
        }


# Singleton instance
github_publisher = GitHubPublisher()
