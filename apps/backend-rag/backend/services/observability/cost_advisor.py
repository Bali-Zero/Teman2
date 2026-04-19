"""CostAdvisor — weekly analysis of llm_cost_events → recommendations.

Mines the cost ledger (migration 117, `llm_cost_events`), identifies
high-spend endpoints, detects volume spikes vs a 28-day baseline, and
asks Claude OAuth Max for cheaper-model substitutions. Results land in
`llm_cost_recommendations` (migration 118) with a 7-day dedup window so
repeated weekly runs do not duplicate rows.

Public API:
    CostAdvisor.analyze_last_window(days) -> list[EndpointCostSummary]
    CostAdvisor.detect_spikes(summaries) -> set[str]
    CostAdvisor.propose_substitutions(top_n) -> list[CostRecommendation]
    CostAdvisor.persist_recommendations(recs) -> int  # rows inserted

Runtime dependency: Claude OAuth Max client. Never uses ANTHROPIC_API_KEY
(see project memory ``feedback_claude_oauth_only.md``).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Any, Literal

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EndpointCostSummary:
    endpoint: str
    model: str
    provider: str
    call_count: int
    total_cost_usd: Decimal
    avg_cost_per_call_usd: Decimal
    p50_latency_ms: int
    p95_latency_ms: int
    success_rate: float


@dataclass(frozen=True)
class CostRecommendation:
    endpoint: str
    current_model: str
    proposed_model: str
    estimated_monthly_saving_usd: Decimal
    quality_tradeoff: str
    confidence: Literal["low", "medium", "high"]
    spike_flag: bool = False


# ---------------------------------------------------------------------------
# Prompt for Claude OAuth judge
# ---------------------------------------------------------------------------

_JUDGE_SYSTEM_PROMPT = """You are a cost-optimisation advisor for an LLM system.
Given a list of endpoints with their current model + volume + cost, propose
cheaper substitutes. ONLY suggest models from these providers already integrated
in Nuzantara: 'gemini', 'deepseek', 'claude_oauth'.

Return ONE JSON array; each item MUST have exactly these keys:
- endpoint (string, echo from input)
- current_model (string, echo)
- proposed_model (string, a cheaper but comparable-quality model slug)
- estimated_monthly_saving_usd (string representing a decimal number)
- quality_tradeoff (string, ≤ 20 words)
- confidence (one of: 'low', 'medium', 'high')

No prose outside the JSON array. If no substitution is warranted for an
endpoint (already cheap enough or quality-critical), omit it from the array."""


# ---------------------------------------------------------------------------
# CostAdvisor
# ---------------------------------------------------------------------------


class CostAdvisor:
    """Weekly cost-analysis + model-substitution advisor."""

    def __init__(self, *, pg_pool: Any, oauth_client: Any) -> None:
        self.pg_pool = pg_pool
        self.oauth_client = oauth_client

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    async def analyze_last_window(
        self, days: int = 7,
    ) -> list[EndpointCostSummary]:
        """Aggregate llm_cost_events in the last N days by (endpoint, model, provider)."""
        async with self.pg_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    COALESCE(endpoint, 'unknown')                AS endpoint,
                    model,
                    provider,
                    COUNT(*)                                     AS call_count,
                    SUM(cost_usd)                                AS total_cost_usd,
                    AVG(cost_usd)                                AS avg_cost_per_call_usd,
                    PERCENTILE_CONT(0.5)  WITHIN GROUP (ORDER BY latency_ms) AS p50_latency_ms,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_latency_ms,
                    AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END) AS success_rate
                FROM llm_cost_events
                WHERE ts_utc >= NOW() - ($1::int || ' days')::interval
                GROUP BY endpoint, model, provider
                ORDER BY total_cost_usd DESC
                """,
                days,
            )
        return [
            EndpointCostSummary(
                endpoint=r["endpoint"],
                model=r["model"],
                provider=r["provider"],
                call_count=int(r["call_count"]),
                total_cost_usd=Decimal(str(r["total_cost_usd"])),
                avg_cost_per_call_usd=Decimal(str(r["avg_cost_per_call_usd"])),
                p50_latency_ms=int(r["p50_latency_ms"] or 0),
                p95_latency_ms=int(r["p95_latency_ms"] or 0),
                success_rate=float(r["success_rate"]),
            )
            for r in rows
        ]

    async def detect_spikes(
        self,
        summaries: list[EndpointCostSummary],
        *,
        baseline_days: int = 28,
        multiplier: float = 3.0,
    ) -> set[str]:
        """Return endpoints whose last-7d spend exceeds baseline weekly avg × multiplier.

        Baseline is computed from ts_utc ∈ (now - baseline_days, now - 7d), i.e.
        the trailing window excluding the current week.
        """
        spikes: set[str] = set()
        async with self.pg_pool.acquire() as conn:
            for s in summaries:
                baseline = await conn.fetchval(
                    """
                    SELECT COALESCE(SUM(cost_usd), 0) / ($2::float / 7)
                    FROM llm_cost_events
                    WHERE endpoint = $1
                      AND ts_utc >= NOW() - ($2::int || ' days')::interval
                      AND ts_utc <  NOW() - INTERVAL '7 days'
                    """,
                    s.endpoint,
                    baseline_days,
                )
                baseline_dec = Decimal(str(baseline or 0))
                if (
                    baseline_dec > 0
                    and s.total_cost_usd > baseline_dec * Decimal(str(multiplier))
                ):
                    spikes.add(s.endpoint)
        return spikes

    # ------------------------------------------------------------------
    # LLM-as-judge substitution proposals
    # ------------------------------------------------------------------

    async def propose_substitutions(
        self, *, top_n: int = 5,
    ) -> list[CostRecommendation]:
        """Ask the OAuth client for cheaper model substitutes on top-N endpoints."""
        summaries = await self.analyze_last_window(days=7)
        spikes = await self.detect_spikes(summaries)
        top = summaries[:top_n]
        if not top:
            return []

        payload = json.dumps([
            {
                "endpoint": s.endpoint,
                "current_model": s.model,
                "call_count": s.call_count,
                "total_cost_usd": str(s.total_cost_usd),
                "avg_cost_per_call_usd": str(s.avg_cost_per_call_usd),
            }
            for s in top
        ])

        raw = await self.oauth_client.complete(
            system=_JUDGE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": payload}],
        )
        try:
            items = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning(
                "CostAdvisor: LLM returned non-JSON on first attempt, retrying once",
            )
            raw = await self.oauth_client.complete(
                system=_JUDGE_SYSTEM_PROMPT + "\n\nRETURN JSON ARRAY ONLY. NO PROSE.",
                messages=[{"role": "user", "content": payload}],
            )
            try:
                items = json.loads(raw)
            except (json.JSONDecodeError, TypeError) as exc:
                logger.error(
                    "CostAdvisor: LLM returned non-JSON twice — dropping batch (%s)",
                    exc,
                )
                return []

        if not isinstance(items, list):
            logger.warning(
                "CostAdvisor: expected JSON array, got %s — dropping batch",
                type(items).__name__,
            )
            return []

        recs: list[CostRecommendation] = []
        for item in items:
            try:
                rec = CostRecommendation(
                    endpoint=item["endpoint"],
                    current_model=item["current_model"],
                    proposed_model=item["proposed_model"],
                    estimated_monthly_saving_usd=Decimal(
                        str(item["estimated_monthly_saving_usd"]),
                    ),
                    quality_tradeoff=item["quality_tradeoff"],
                    confidence=item["confidence"],
                    spike_flag=item["endpoint"] in spikes,
                )
                if rec.spike_flag:
                    rec = replace(rec, confidence="high")
                recs.append(rec)
            except (KeyError, ValueError, TypeError) as exc:
                logger.warning(
                    "CostAdvisor: dropping malformed recommendation %s: %s",
                    item,
                    exc,
                )
        return recs

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def persist_recommendations(
        self, recs: list[CostRecommendation],
    ) -> int:
        """Insert recommendations; skip duplicates landed in the last 7 days.

        Returns the number of rows actually inserted (0 means all were dupes).
        """
        if not recs:
            return 0
        inserted = 0
        async with self.pg_pool.acquire() as conn:
            for r in recs:
                result = await conn.execute(
                    """
                    INSERT INTO llm_cost_recommendations (
                        endpoint, current_model, proposed_model,
                        estimated_monthly_saving_usd, quality_tradeoff,
                        confidence, spike_flag
                    )
                    SELECT $1, $2, $3, $4, $5, $6, $7
                    WHERE NOT EXISTS (
                        SELECT 1 FROM llm_cost_recommendations
                        WHERE endpoint = $1
                          AND current_model = $2
                          AND proposed_model = $3
                          AND ts_utc >= NOW() - INTERVAL '7 days'
                    )
                    """,
                    r.endpoint,
                    r.current_model,
                    r.proposed_model,
                    r.estimated_monthly_saving_usd,
                    r.quality_tradeoff,
                    r.confidence,
                    r.spike_flag,
                )
                if result and "INSERT 0 1" in str(result):
                    inserted += 1
        return inserted
