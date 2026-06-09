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

        logger.debug("Checking file exists: %s (branch: %s)", path, branch)

        client = self._get_client()
        response = await client.get(
            url,
            headers=self._get_headers(),
            params=params,
            timeout=30.0,
        )

        exists = response.status_code == 200
        logger.debug("File exists check: %s → %s", path, exists)
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

        logger.debug("Getting file SHA: %s", path)

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

        logger.debug("File not found (no SHA): %s", path)
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
                "GitHub API error uploading %s: %s",
                path,
                error_detail,
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

    async def _create_branch_ref(self, branch: str, from_sha: str) -> None:
        """
        Create a new branch ref pointing at ``from_sha``.

        Used by the pull-request publish path so the commit lands on a
        fresh, unprotected branch instead of attempting a direct push to a
        protected branch (which GitHub rejects with HTTP 422).

        Args:
            branch: New branch name (without ``refs/heads/`` prefix).
            from_sha: Commit SHA the new branch should point at.

        Raises:
            GitHubPublisherError: If the branch ref cannot be created.
        """
        client = self._get_client()
        create_ref_url = f"{self.BASE_URL}/repos/{self.owner}/{self.repo}/git/refs"
        response = await client.post(
            create_ref_url,
            headers=self._get_headers(),
            json={"ref": f"refs/heads/{branch}", "sha": from_sha},
            timeout=30.0,
        )
        # 201 Created on success. 422 means the ref already exists — reuse it.
        if response.status_code == 422 and "already exists" in response.text:
            logger.warning("Branch '%s' already exists, reusing it", branch)
            return
        if response.status_code != 201:
            logger.error("Failed to create branch ref '%s': %s", branch, response.text)
            raise GitHubPublisherError(
                f"Failed to create branch ref '{branch}': {response.text}",
            )

    async def _create_pull_request(
        self,
        head_branch: str,
        base_branch: str,
        title: str,
        body: str,
    ) -> dict[str, Any]:
        """
        Open a pull request from ``head_branch`` into ``base_branch``.

        Args:
            head_branch: Source branch carrying the new commit.
            base_branch: Target (protected) branch, e.g. ``main``.
            title: PR title.
            body: PR description.

        Returns:
            Dict with ``number`` (PR number), ``node_id`` (GraphQL id) and
            ``html_url``.

        Raises:
            GitHubPublisherError: If the PR cannot be created.
        """
        client = self._get_client()
        pulls_url = f"{self.BASE_URL}/repos/{self.owner}/{self.repo}/pulls"
        response = await client.post(
            pulls_url,
            headers=self._get_headers(),
            json={
                "title": title,
                "body": body,
                "head": head_branch,
                "base": base_branch,
            },
            timeout=30.0,
        )
        if response.status_code != 201:
            logger.error("Failed to open pull request: %s", response.text)
            raise GitHubPublisherError(f"Failed to open pull request: {response.text}")
        data = response.json()
        return {
            "number": data["number"],
            "node_id": data["node_id"],
            "html_url": data["html_url"],
        }

    async def _enable_auto_merge(self, pr_node_id: str) -> bool:
        """
        Enable auto-merge (squash) on a PR via the GraphQL API.

        Once the branch protection's required status checks pass, GitHub
        merges the PR automatically — no human intervention. Best-effort:
        if auto-merge cannot be enabled (e.g. the repo setting is off), the
        PR is still open and mergeable manually, so we log and return False
        rather than raising.

        Args:
            pr_node_id: The PR's GraphQL ``node_id``.

        Returns:
            True if auto-merge was enabled, False otherwise.
        """
        client = self._get_client()
        graphql_url = f"{self.BASE_URL}/graphql"
        mutation = (
            "mutation($id:ID!){enablePullRequestAutoMerge"
            "(input:{pullRequestId:$id,mergeMethod:SQUASH})"
            "{pullRequest{autoMergeRequest{enabledAt}}}}"
        )
        try:
            response = await client.post(
                graphql_url,
                headers=self._get_headers(),
                json={"query": mutation, "variables": {"id": pr_node_id}},
                timeout=30.0,
            )
        except httpx.HTTPError as exc:
            logger.warning("Auto-merge request failed (non-blocking): %s", exc)
            return False
        if response.status_code != 200:
            logger.warning(
                "Auto-merge not enabled (HTTP %s, non-blocking): %s",
                response.status_code,
                response.text,
            )
            return False
        payload = response.json()
        if payload.get("errors"):
            logger.warning(
                "Auto-merge not enabled (GraphQL errors, non-blocking): %s",
                payload["errors"],
            )
            return False
        return True

    async def create_commit_with_files(
        self,
        files: list[dict[str, Any]],
        message: str,
        branch: str = "main",
        pull_request: bool = False,
        pr_branch_prefix: str = "auto-publish",
    ) -> dict[str, Any]:
        """
        Create a single commit with multiple files.

        Uses the Git Data API for atomic commits with multiple files.

        Two publish modes:

        - ``pull_request=False`` (default): commit is pushed directly to
          ``branch`` by updating its ref. Works only when ``branch`` is
          unprotected.
        - ``pull_request=True``: the commit is placed on a fresh branch
          (``{pr_branch_prefix}/<short-sha>``), a PR into ``branch`` is
          opened and auto-merge (squash) is enabled. This is the correct
          path for protected branches (e.g. ``main`` with required status
          checks), which reject direct pushes with HTTP 422.

        Args:
            files: List of dicts with 'path' and 'content' keys
            message: Commit message
            branch: Target branch (default: main)
            pull_request: If True, publish via branch + PR + auto-merge.
            pr_branch_prefix: Prefix for the temporary PR branch name.

        Returns:
            Commit info. When ``pull_request=True`` also includes
            ``pull_request_url``, ``pull_request_number`` and
            ``auto_merge_enabled``.
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
        logger.debug("Step 1/6: Getting branch ref for '%s'", branch)
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

        if pull_request:
            # Step 6 (PR path): land the commit on a fresh branch, then open a
            # PR into `branch` with auto-merge. Required for protected branches
            # (direct ref update returns HTTP 422).
            pr_branch = f"{pr_branch_prefix}/{new_commit_sha[:12]}"
            logger.debug("Step 6/6 (PR): creating branch '%s' + pull request", pr_branch)
            await self._create_branch_ref(pr_branch, new_commit_sha)
            pr_title = message.split("\n", 1)[0]
            pr_body = (
                f"{message}\n\n"
                "Auto-opened by Article Composer (News Room publish). "
                "Auto-merge enabled — merges once required checks pass."
            )
            pr = await self._create_pull_request(
                head_branch=pr_branch,
                base_branch=branch,
                title=pr_title,
                body=pr_body,
            )
            auto_merge_enabled = await self._enable_auto_merge(pr["node_id"])

            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(
                f"Article PR opened: #{pr['number']} {new_commit_sha[:7]} "
                f"({len(files)} files, auto_merge={auto_merge_enabled}, {elapsed_ms:.0f}ms)",
                extra={
                    "commit_sha": new_commit_sha,
                    "pull_request_number": pr["number"],
                    "pr_branch": pr_branch,
                    "auto_merge_enabled": auto_merge_enabled,
                    "files_count": len(files),
                    "elapsed_ms": elapsed_ms,
                },
            )
            return {
                "success": True,
                "commit_sha": new_commit_sha,
                "files_count": len(files),
                "branch": pr_branch,
                "pull_request_url": pr["html_url"],
                "pull_request_number": pr["number"],
                "auto_merge_enabled": auto_merge_enabled,
            }

        # Step 6 (direct path): update branch reference (unprotected branches).
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
