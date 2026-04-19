"""BlogPublisher — MDX commit into content_root, then git add+commit+push.

Design §9.5. The receiving app is expected to pick up ``*.mdx`` under
``content_root`` at deploy time (Next.js + Vercel). The publisher is
deliberately storage-agnostic: it just writes files and runs git.

Flow:
    1. Resolve content_root (e.g. ``apps/web/content/war-room``)
    2. Build slug + filename (``YYYY-MM-DD-<slug>.mdx``)
    3. Idempotency: if file already exists on disk AND contains the
       same ``draft_id``, skip (return previous path as success).
    4. Write MDX
    5. ``git -C <repo_root> add <relative_path>``
    6. ``git -C <repo_root> commit -m ...``
    7. ``git -C <repo_root> push`` (unless ``skip_push=True``)

Configuration:
    env ``BLOG_CONTENT_ROOT``        absolute dir (default:
        ~/Desktop/nuzantara/apps/web/content/war-room)
    env ``BLOG_SITE_URL``            base URL for rendered post (e.g.
        https://balizero.com)
    env ``BLOG_PUBLISH_SKIP_PUSH``   if "1", skip the push step (for local
        testing; file is still committed locally)

The publisher never raises from ``publish`` — errors become
:class:`PublishResult.ok=False` so the orchestrator can isolate them.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from backend.services.publisher.base import (
    DraftPayload,
    Publisher,
    PublishResult,
    ValidationResult,
)
from backend.services.publisher.mdx_template import (
    build_slug,
    filename_for,
    render_full_mdx,
)
from backend.services.war_room.models import Platform

logger = logging.getLogger(__name__)


DEFAULT_CONTENT_ROOT = str(
    Path.home() / "Desktop" / "nuzantara" / "apps" / "web" / "content" / "war-room"
)
DEFAULT_SITE_URL = "https://balizero.com"
DEFAULT_URL_PREFIX = "/blog"


class BlogPublisher(Publisher):
    platform_name = Platform.BLOG

    def __init__(
        self,
        *,
        content_root: str | None = None,
        repo_root: str | None = None,
        site_url: str | None = None,
        url_prefix: str | None = None,
        skip_push: bool | None = None,
        clock: ClockFn | None = None,
    ) -> None:
        self.content_root = Path(
            content_root or os.environ.get("BLOG_CONTENT_ROOT", DEFAULT_CONTENT_ROOT)
        )
        self.repo_root = Path(
            repo_root or self._infer_repo_root(self.content_root)
        )
        self.site_url = (
            site_url or os.environ.get("BLOG_SITE_URL", DEFAULT_SITE_URL)
        ).rstrip("/")
        self.url_prefix = (
            url_prefix or os.environ.get("BLOG_URL_PREFIX", DEFAULT_URL_PREFIX)
        ).rstrip("/")
        env_skip = os.environ.get("BLOG_PUBLISH_SKIP_PUSH", "").strip()
        self.skip_push = (
            skip_push if skip_push is not None else env_skip in ("1", "true", "yes")
        )
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    # ── Public API ───────────────────────────────────────────────────

    async def validate(self, draft: DraftPayload) -> ValidationResult:
        issues: list[str] = []
        if not draft.main_caption or not draft.main_caption.strip():
            issues.append("main_caption required")
        if not draft.topic or not draft.topic.strip():
            issues.append("topic required")
        return ValidationResult(
            ok=not issues,
            platform=Platform.BLOG,
            issues=issues,
        )

    async def publish(self, draft: DraftPayload) -> PublishResult:
        validation = await self.validate(draft)
        if not validation.ok:
            return PublishResult(
                ok=False,
                platform=Platform.BLOG,
                draft_id=draft.draft_id,
                error=f"validation: {', '.join(validation.issues)}",
            )

        try:
            published_at = self._clock()
            slug = build_slug(draft.topic, draft.draft_id)
            filename = filename_for(published_at, slug)
            file_path = self.content_root / filename

            # idempotency: existing file containing this draft_id → success noop
            if file_path.exists():
                existing = file_path.read_text(encoding="utf-8")
                if f'draft_id: "{draft.draft_id}"' in existing:
                    return PublishResult(
                        ok=True,
                        platform=Platform.BLOG,
                        draft_id=draft.draft_id,
                        post_external_id=str(file_path.relative_to(self.repo_root)),
                        post_url=self._public_url(slug),
                        final_text=draft.main_caption,
                        meta={
                            "idempotent_skip": True,
                            "file_path": str(file_path),
                        },
                    )

            self.content_root.mkdir(parents=True, exist_ok=True)
            mdx = render_full_mdx(draft, slug=slug, published_at=published_at)
            file_path.write_text(mdx, encoding="utf-8")

            relative = str(file_path.relative_to(self.repo_root))
            commit_message = (
                f"content(war-room): {draft.topic[:60]} [{slug}]"
            )

            add_rc, add_err = await self._git(
                ["add", relative], cwd=self.repo_root,
            )
            if add_rc != 0:
                return PublishResult(
                    ok=False,
                    platform=Platform.BLOG,
                    draft_id=draft.draft_id,
                    error=f"git add failed: {add_err}",
                )

            commit_rc, commit_err = await self._git(
                ["commit", "-m", commit_message], cwd=self.repo_root,
            )
            # rc=1 can mean "nothing to commit" when file already staged —
            # treat as idempotent success if stderr confirms no changes.
            if commit_rc != 0 and "nothing to commit" not in (commit_err or ""):
                return PublishResult(
                    ok=False,
                    platform=Platform.BLOG,
                    draft_id=draft.draft_id,
                    error=f"git commit failed: {commit_err}",
                )

            if not self.skip_push:
                push_rc, push_err = await self._git(
                    ["push"], cwd=self.repo_root,
                )
                if push_rc != 0:
                    return PublishResult(
                        ok=False,
                        platform=Platform.BLOG,
                        draft_id=draft.draft_id,
                        error=f"git push failed: {push_err}",
                    )

            return PublishResult(
                ok=True,
                platform=Platform.BLOG,
                draft_id=draft.draft_id,
                post_external_id=relative,
                post_url=self._public_url(slug),
                final_text=draft.main_caption,
                meta={
                    "file_path": str(file_path),
                    "slug": slug,
                    "pushed": not self.skip_push,
                },
            )

        except Exception as exc:  # noqa: BLE001
            return PublishResult(
                ok=False,
                platform=Platform.BLOG,
                draft_id=draft.draft_id,
                error=f"{type(exc).__name__}: {exc}",
            )

    async def delete(self, post_external_id: str) -> bool:
        """Best-effort rollback: remove the MDX file and commit.

        ``post_external_id`` is the repo-relative path.
        """
        try:
            full = self.repo_root / post_external_id
            if not full.exists():
                return False
            rc, err = await self._git(
                ["rm", post_external_id], cwd=self.repo_root,
            )
            if rc != 0:
                return False
            rc, err = await self._git(
                ["commit", "-m", f"revert(war-room): {post_external_id}"],
                cwd=self.repo_root,
            )
            if rc != 0 and "nothing to commit" not in (err or ""):
                return False
            if not self.skip_push:
                rc, _ = await self._git(["push"], cwd=self.repo_root)
                if rc != 0:
                    return False
            return True
        except Exception as exc:  # noqa: BLE001
            logger.info("blog delete failed: %s", exc)
            return False

    # ── Internals ───────────────────────────────────────────────────

    def _public_url(self, slug: str) -> str:
        return f"{self.site_url}{self.url_prefix}/{slug}"

    @staticmethod
    def _infer_repo_root(content_root: Path) -> Path:
        """Walk up from content_root to find a .git directory."""
        cur = content_root.resolve()
        for ancestor in [cur, *cur.parents]:
            if (ancestor / ".git").exists():
                return ancestor
        # fallback to content_root itself — tests can override
        return content_root

    async def _git(
        self,
        argv: list[str],
        *,
        cwd: Path,
    ) -> tuple[int, str]:
        """Run a git command; return (rc, stderr)."""
        proc = await asyncio.create_subprocess_exec(
            "git",
            *argv,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        err = stderr.decode("utf-8", errors="replace").strip()
        rc = proc.returncode or 0
        return rc, err


# Type alias for the injectable clock (for deterministic tests).
from collections.abc import Callable  # noqa: E402

ClockFn = Callable[[], datetime]
