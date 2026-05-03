"""LearnerOrchestrator — nightly sweep over posts ≥ T+72h old.

Cycle (design §10):
    for each eligible post:
        1. Collect latest metrics per metric_name (max collected_at wins)
        2. Build ScoreInputs; call ScoreCalculator
        3. if complete and score > p70: record_skill
        4. if complete and score < p20: record_scar
        5. Otherwise keep as observation (no write)
        6. Also: if draft was ``rejected_by_zero`` → always record scar
           (regardless of score completeness), per design §10.3.

Learning is append-only to the genome. The "idempotency" guarantee rests on
the genome's own ON CONFLICT logic (same ``skill_id`` → update procedure,
keep higher confidence). We don't maintain a separate ``learning_log`` table
in this sprint; a future sprint can add one for observability.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from backend.services.learner.genome_adapter import (
    GenomeAdapter,
    ScarEntry,
    SkillEntry,
)
from backend.services.learner.score_calculator import (
    CompositeScore,
    ScoreCalculator,
    ScoreInputs,
)
from backend.services.measurer.base import (
    METRIC_COMMENTS,
    METRIC_IMPRESSIONS,
    METRIC_LEADS_ATTRIBUTED,
    METRIC_LIKES,
    METRIC_REACH,
    METRIC_SAVES,
    METRIC_SHARES,
)
from backend.services.war_room.models import (
    DraftStatus,
    Platform,
    RegisterTone,
    RejectionReason,
    WarRoomPost,
)
from backend.services.war_room.repository import WarRoomRepository

logger = logging.getLogger(__name__)


# Percentile thresholds (§10.2, §10.3). Pre-computed per (platform, metric)
# from last 90d data — but for score composite thresholds we use absolute
# percentiles within the Learner's own cohort of completed posts.
DEFAULT_SKILL_THRESHOLD_P = 0.70
DEFAULT_SCAR_THRESHOLD_P = 0.20

DEFAULT_SKILL_CONFIDENCE = 0.65
REJECTED_SCAR_PRECONDITION_PREFIX = "zero_rejected"


class LearningDecision(str, Enum):
    SKILL = "skill"
    SCAR = "scar"
    OBSERVED = "observed"      # score computed but didn't cross thresholds
    INCOMPLETE = "incomplete"  # missing metrics → cannot classify
    SKIPPED = "skipped"


@dataclass
class LearnerResult:
    ran_at: datetime
    posts_considered: int = 0
    skills_recorded: int = 0
    scars_recorded: int = 0
    incomplete: int = 0
    errors: list[str] = field(default_factory=list)
    per_post: list[PostLearning] = field(default_factory=list)


@dataclass
class PostLearning:
    post_id: UUID
    decision: LearningDecision
    score: CompositeScore | None = None
    note: str = ""


class LearnerOrchestrator:
    """Nightly cron target — wraps the score → classify → genome pipeline."""

    def __init__(
        self,
        repo: WarRoomRepository,
        genome: GenomeAdapter,
        calculator: ScoreCalculator | None = None,
        *,
        skill_threshold: float = DEFAULT_SKILL_THRESHOLD_P,
        scar_threshold: float = DEFAULT_SCAR_THRESHOLD_P,
        min_age_hours: int = 72,
        max_age_hours: int = 168,          # 7d
        reach_history_days: int = 90,
    ) -> None:
        self.repo = repo
        self.genome = genome
        self.calculator = calculator or ScoreCalculator()
        self.skill_threshold = skill_threshold
        self.scar_threshold = scar_threshold
        self.min_age_hours = min_age_hours
        self.max_age_hours = max_age_hours
        self.reach_history_days = reach_history_days
        self.logger = logger

    # ── Main sweep ───────────────────────────────────────────────

    async def sweep_once(
        self,
        *,
        now: datetime | None = None,
    ) -> LearnerResult:
        now = now or datetime.now(timezone.utc)
        result = LearnerResult(ran_at=now)

        # 1. find eligible posts (72h-168h old, published)
        try:
            posts = await self._eligible_posts(now=now)
        except Exception as exc:  # noqa: BLE001
            result.errors.append(
                f"eligible_posts: {type(exc).__name__}: {exc}"
            )
            return result

        result.posts_considered = len(posts)

        # 2. cache reach distributions per platform (90d)
        reach_cache: dict[Platform, list[float]] = {}
        for post in posts:
            if post.platform not in reach_cache:
                try:
                    reach_cache[post.platform] = await self._reach_history(
                        platform=post.platform, days=self.reach_history_days,
                    )
                except Exception as exc:  # noqa: BLE001
                    reach_cache[post.platform] = []
                    result.errors.append(
                        f"reach_history {post.platform.value}: {exc}"
                    )

        # 3. process each post
        for post in posts:
            try:
                pl = await self._learn_from_post(
                    post, reach_distribution=reach_cache.get(post.platform, []),
                )
                result.per_post.append(pl)
                if pl.decision == LearningDecision.SKILL:
                    result.skills_recorded += 1
                elif pl.decision == LearningDecision.SCAR:
                    result.scars_recorded += 1
                elif pl.decision == LearningDecision.INCOMPLETE:
                    result.incomplete += 1
            except Exception as exc:  # noqa: BLE001
                result.errors.append(
                    f"learn post {post.id}: {type(exc).__name__}: {exc}"
                )

        return result

    # ── Per-post pipeline ────────────────────────────────────────

    async def _learn_from_post(
        self,
        post: WarRoomPost,
        *,
        reach_distribution: list[float],
    ) -> PostLearning:
        # Zero-rejected draft → immediate scar (§10.3), regardless of score.
        draft = await self.repo.get_draft(post.draft_id)
        is_rejected_by_zero = (
            draft is not None
            and draft.status == DraftStatus.REJECTED
            and (draft.rejection_reason or "") != RejectionReason.SLA_EXPIRED.value
        )

        metrics = await self._latest_metrics(post.id)
        inputs = _inputs_from_metrics(metrics)
        score = self.calculator.calculate(
            inputs=inputs,
            reach_distribution_90d=reach_distribution,
            platform=post.platform,
        )

        if is_rejected_by_zero:
            await self._record_scar_for_rejection(post, draft, score)
            return PostLearning(
                post_id=post.id,
                decision=LearningDecision.SCAR,
                score=score,
                note="zero_rejected",
            )

        if not score.complete:
            return PostLearning(
                post_id=post.id,
                decision=LearningDecision.INCOMPLETE,
                score=score,
                note=f"missing={score.missing_terms}",
            )

        if score.value > self.skill_threshold:
            await self._record_skill(post, score)
            return PostLearning(
                post_id=post.id,
                decision=LearningDecision.SKILL,
                score=score,
            )

        if score.value < self.scar_threshold:
            await self._record_scar(post, score, reason="low_score")
            return PostLearning(
                post_id=post.id,
                decision=LearningDecision.SCAR,
                score=score,
                note="low_score",
            )

        return PostLearning(
            post_id=post.id,
            decision=LearningDecision.OBSERVED,
            score=score,
        )

    # ── Recording helpers ────────────────────────────────────────

    async def _record_skill(
        self,
        post: WarRoomPost,
        score: CompositeScore,
    ) -> None:
        register = post.tone_register.value if post.tone_register else "unknown"
        skill_id = f"war_room:{register}:{post.platform.value}:{post.id}"
        procedure = (
            f"Post {post.post_external_id or post.id} on {post.platform.value} "
            f"in register '{register}' scored {score.value:.3f} "
            f"(reach_norm={score.norm_reach:.2f}, engagement={score.engagement_rate:.3f}, "
            f"leads_per_1k={score.leads_per_1k:.3f}, save_rate={score.save_rate:.3f}). "
            "Replicate the register/topic framing."
        )
        precondition = f"register={register}, platform={post.platform.value}"
        success_criterion = f"composite > {self.skill_threshold:.2f}"
        await self.genome.record_skill(
            SkillEntry(
                skill_id=skill_id,
                procedure=procedure,
                precondition=precondition,
                success_criterion=success_criterion,
                confidence=max(DEFAULT_SKILL_CONFIDENCE, min(1.0, score.value)),
                domain="war_room",
                scope="Project",
            )
        )

    async def _record_scar(
        self,
        post: WarRoomPost,
        score: CompositeScore,
        *,
        reason: str,
    ) -> None:
        register = post.tone_register.value if post.tone_register else "unknown"
        scar_id = f"war_room_scar:{reason}:{post.platform.value}:{post.id}"
        procedure = (
            f"Avoid the framing used in {post.post_external_id or post.id} "
            f"({post.platform.value}, register '{register}') — "
            f"it produced composite {score.value:.3f} "
            f"(reach_norm={score.norm_reach:.2f}, engagement={score.engagement_rate:.3f})."
        )
        precondition = f"reason={reason}"
        await self.genome.record_scar(
            ScarEntry(
                scar_id=scar_id,
                procedure=procedure,
                precondition=precondition,
            )
        )

    async def _record_scar_for_rejection(
        self,
        post: WarRoomPost,
        draft: Any,
        score: CompositeScore,
    ) -> None:
        register = post.tone_register.value if post.tone_register else "unknown"
        rejection_reason = (
            draft.rejection_reason if draft and getattr(draft, "rejection_reason", None)
            else "unspecified"
        )
        scar_id = (
            f"war_room_scar:{REJECTED_SCAR_PRECONDITION_PREFIX}:"
            f"{rejection_reason}:{post.id}"
        )
        procedure = (
            f"Zero rejected draft {post.draft_id} "
            f"(topic delivered on {post.platform.value}, register '{register}'). "
            f"Reason: {rejection_reason}. Avoid replicating this framing."
        )
        precondition = f"{REJECTED_SCAR_PRECONDITION_PREFIX}={rejection_reason}"
        await self.genome.record_scar(
            ScarEntry(
                scar_id=scar_id,
                procedure=procedure,
                precondition=precondition,
            )
        )

    # ── DB helpers ───────────────────────────────────────────────

    async def _eligible_posts(
        self, *, now: datetime,
    ) -> list[WarRoomPost]:
        upper = now - timedelta(hours=self.min_age_hours)
        lower = now - timedelta(hours=self.max_age_hours)
        rows = await self.repo.fetch_safe(
            """
            SELECT id, draft_id, platform, post_external_id, post_url,
                   register, published_at, final_text
              FROM war_room_posts
             WHERE published_at >= $1
               AND published_at <  $2
             ORDER BY published_at ASC;
            """,
            lower,
            upper,
        )
        return [_row_to_post(row) for row in rows]

    async def _latest_metrics(
        self, post_id: UUID,
    ) -> dict[str, float]:
        """Return metric_name → latest value. If multiple rows per name, pick
        the most recent non-partial; fall back to any."""
        rows = await self.repo.fetch_safe(
            """
            SELECT DISTINCT ON (metric_name)
                   metric_name, value, source, collected_at
              FROM war_room_metrics
             WHERE post_id = $1
             ORDER BY metric_name ASC, collected_at DESC;
            """,
            post_id,
        )
        out: dict[str, float] = {}
        for row in rows:
            try:
                out[row["metric_name"]] = float(row["value"])
            except (TypeError, ValueError):
                continue
        return out

    async def _reach_history(
        self, *, platform: Platform, days: int,
    ) -> list[float]:
        rows = await self.repo.fetch_safe(
            """
            SELECT m.value
              FROM war_room_metrics m
              JOIN war_room_posts p ON m.post_id = p.id
             WHERE p.platform = $1
               AND m.metric_name = 'reach'
               AND m.collected_at > NOW() - make_interval(days => $2)
             ORDER BY m.collected_at DESC
             LIMIT 500;
            """,
            platform.value,
            days,
        )
        out: list[float] = []
        for row in rows:
            try:
                out.append(float(row["value"]))
            except (TypeError, ValueError):
                continue
        return out


# ── helpers ──────────────────────────────────────────────────────


def _row_to_post(row: Any) -> WarRoomPost:
    register = row["register"]
    return WarRoomPost(
        id=row["id"],
        draft_id=row["draft_id"],
        platform=Platform(row["platform"]),
        post_external_id=row["post_external_id"],
        post_url=row["post_url"],
        tone_register=RegisterTone(register) if register else None,
        published_at=row["published_at"],
        final_text=row["final_text"],
    )


def _inputs_from_metrics(metrics: dict[str, float]) -> ScoreInputs:
    return ScoreInputs(
        reach=metrics.get(METRIC_REACH),
        impressions=metrics.get(METRIC_IMPRESSIONS),
        likes=metrics.get(METRIC_LIKES),
        comments=metrics.get(METRIC_COMMENTS),
        shares=metrics.get(METRIC_SHARES),
        saves=metrics.get(METRIC_SAVES),
        leads_attributed=metrics.get(METRIC_LEADS_ATTRIBUTED),
    )
