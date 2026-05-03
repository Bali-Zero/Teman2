"""BlogBatchPublisher — publish N blog articles in a single atomic commit.

Wraps :class:`BlogPublisher` (Sprint 8) with:

    1. Volume governor: soft target 3-5/day, hard cap 8/day (design §19.1).
       Over-cap drafts are skipped with ``ok=True, meta={"over_daily_cap": True}``
       so the orchestrator can record them as war_room_posts without git write.
    2. Single-commit batch: writes all MDX files, then one ``git add`` covering
       the batch + one commit message listing slugs. Reduces churn and makes
       the commit history readable.
    3. Per-article MdxExtras: accepts optional extras dict keyed by draft_id
       so callers can pass dossier_id / composite_score / etc.

Idempotency: if the batch contains a draft whose slug+draft_id already
lives on disk with matching draft_id frontmatter, BlogPublisher's idempotency
path kicks in (file not rewritten), and we skip git add for that entry.

This class does NOT extend Publisher ABC — it's an orchestrator that
delegates to BlogPublisher per-file, then commits once at the end.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from backend.services.publisher.base import DraftPayload, PublishResult
from backend.services.publisher.blog_publisher import BlogPublisher
from backend.services.publisher.mdx_template import (
    MdxExtras,
    build_slug,
    filename_for,
    render_full_mdx,
)
from backend.services.war_room.models import Platform
from backend.services.war_room.repository import WarRoomRepository

logger = logging.getLogger(__name__)


# Design §19.1
SOFT_DAILY_TARGET_MIN = 3
SOFT_DAILY_TARGET_MAX = 5
HARD_DAILY_CAP = 8


@dataclass
class BatchResult:
    ran_at: datetime
    requested: int = 0
    published: list[PublishResult] = field(default_factory=list)
    over_cap_skipped: list[PublishResult] = field(default_factory=list)
    idempotent_skipped: list[PublishResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    commit_ok: bool = False
    pushed: bool = False

    @property
    def published_count(self) -> int:
        return sum(1 for r in self.published if r.ok)


class BlogBatchPublisher:
    """Write N MDX files + single git commit, under daily cap."""

    def __init__(
        self,
        blog_publisher: BlogPublisher,
        repo: WarRoomRepository | None = None,
        *,
        hard_cap: int = HARD_DAILY_CAP,
    ) -> None:
        self.blog_publisher = blog_publisher
        self.repo = repo
        self.hard_cap = hard_cap
        self.logger = logger

    async def publish_batch(
        self,
        drafts: list[DraftPayload],
        *,
        extras_by_draft: dict[UUID, MdxExtras] | None = None,
        clock: Any | None = None,
    ) -> BatchResult:
        now_fn = clock or (lambda: datetime.now(timezone.utc))
        result = BatchResult(ran_at=now_fn(), requested=len(drafts))

        if not drafts:
            return result

        # 1. daily volume governor
        already_today = 0
        if self.repo is not None:
            try:
                already_today = await self.repo.count_posts_published_today(
                    Platform.BLOG,
                )
            except Exception as exc:  # noqa: BLE001
                result.errors.append(
                    f"daily_count: {type(exc).__name__}: {exc}",
                )

        remaining_budget = max(0, self.hard_cap - already_today)

        extras_by_draft = extras_by_draft or {}
        staged_files: list[Path] = []

        # 2. per-draft file write (single git-skipping publish call)
        for idx, draft in enumerate(drafts):
            within_cap = idx < remaining_budget
            if not within_cap:
                skip = PublishResult(
                    ok=True,
                    platform=Platform.BLOG,
                    draft_id=draft.draft_id,
                    meta={"over_daily_cap": True},
                )
                result.over_cap_skipped.append(skip)
                continue

            try:
                publish_result = await self._publish_file_only(
                    draft,
                    extras=extras_by_draft.get(draft.draft_id),
                    clock=now_fn,
                    staged_files=staged_files,
                )
            except Exception as exc:  # noqa: BLE001
                result.errors.append(
                    f"draft {draft.draft_id}: {type(exc).__name__}: {exc}"
                )
                continue

            if publish_result.meta.get("idempotent_skip"):
                result.idempotent_skipped.append(publish_result)
                continue
            result.published.append(publish_result)

        # 3. single-commit batch if we wrote anything
        if staged_files:
            try:
                result.commit_ok, result.pushed = await self._commit_batch(
                    staged_files=staged_files,
                    published=result.published,
                )
            except Exception as exc:  # noqa: BLE001
                result.errors.append(
                    f"commit: {type(exc).__name__}: {exc}"
                )
        else:
            # nothing new to commit; still pushed=True trivially
            result.commit_ok = True
            result.pushed = not self.blog_publisher.skip_push

        return result

    # ── Internals ────────────────────────────────────────────────

    async def _publish_file_only(
        self,
        draft: DraftPayload,
        *,
        extras: MdxExtras | None,
        clock: Any,
        staged_files: list[Path],
    ) -> PublishResult:
        """Write the MDX file without invoking git. Caller batches the commit.

        We don't reuse :meth:`BlogPublisher.publish` directly because that
        method runs git add+commit+push per-file. Here we replicate the
        file-write half and let :meth:`_commit_batch` do the SCM work.
        """
        validation = await self.blog_publisher.validate(draft)
        if not validation.ok:
            return PublishResult(
                ok=False,
                platform=Platform.BLOG,
                draft_id=draft.draft_id,
                error=f"validation: {', '.join(validation.issues)}",
            )

        published_at = clock()
        slug = build_slug(draft.topic, draft.draft_id)
        filename = filename_for(published_at, slug)
        file_path = self.blog_publisher.content_root / filename

        # idempotency — same draft_id already on disk → success noop
        if file_path.exists():
            try:
                existing = file_path.read_text(encoding="utf-8")
            except Exception as exc:  # noqa: BLE001
                return PublishResult(
                    ok=False,
                    platform=Platform.BLOG,
                    draft_id=draft.draft_id,
                    error=f"read existing: {exc}",
                )
            if f'draft_id: "{draft.draft_id}"' in existing:
                return PublishResult(
                    ok=True,
                    platform=Platform.BLOG,
                    draft_id=draft.draft_id,
                    post_external_id=str(
                        file_path.relative_to(self.blog_publisher.repo_root)
                    ),
                    post_url=self.blog_publisher._public_url(slug),
                    final_text=draft.main_caption,
                    meta={
                        "idempotent_skip": True,
                        "file_path": str(file_path),
                    },
                )

        self.blog_publisher.content_root.mkdir(parents=True, exist_ok=True)
        mdx = render_full_mdx(
            draft,
            slug=slug,
            published_at=published_at,
            extras=extras,
            auto_reading_time=True,
        )
        file_path.write_text(mdx, encoding="utf-8")
        staged_files.append(file_path)

        return PublishResult(
            ok=True,
            platform=Platform.BLOG,
            draft_id=draft.draft_id,
            post_external_id=str(
                file_path.relative_to(self.blog_publisher.repo_root)
            ),
            post_url=self.blog_publisher._public_url(slug),
            final_text=draft.main_caption,
            meta={"slug": slug, "file_path": str(file_path)},
        )

    async def _commit_batch(
        self,
        *,
        staged_files: list[Path],
        published: list[PublishResult],
    ) -> tuple[bool, bool]:
        """Run ``git add`` across files + one commit + optional push."""
        repo_root = self.blog_publisher.repo_root
        add_args = ["add"] + [
            str(p.relative_to(repo_root)) for p in staged_files
        ]
        add_rc, add_err = await self.blog_publisher._git(
            add_args, cwd=repo_root,
        )
        if add_rc != 0:
            raise RuntimeError(f"git add failed: {add_err}")

        slugs = [
            (r.meta.get("slug") or "?") for r in published if r.ok
        ]
        commit_msg = (
            f"content(war-room): batch of {len(slugs)} articles "
            f"[{', '.join(slugs[:5])}{'…' if len(slugs) > 5 else ''}]"
        )
        commit_rc, commit_err = await self.blog_publisher._git(
            ["commit", "-m", commit_msg], cwd=repo_root,
        )
        commit_ok = commit_rc == 0 or "nothing to commit" in (commit_err or "")
        if not commit_ok:
            raise RuntimeError(f"git commit failed: {commit_err}")

        pushed = False
        if not self.blog_publisher.skip_push:
            push_rc, push_err = await self.blog_publisher._git(
                ["push"], cwd=repo_root,
            )
            if push_rc != 0:
                raise RuntimeError(f"git push failed: {push_err}")
            pushed = True
        return commit_ok, pushed
