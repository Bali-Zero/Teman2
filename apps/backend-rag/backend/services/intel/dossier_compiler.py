"""DossierCompiler — transform unconsumed TrendSignals into ResearchDossiers.

Reference: docs/war-room-2.0-design.md §15.5 (pre-generation hybrid), §17 (cognitive substrate).

Cycle:
    1. Query top-N unconsumed trends (urgency*relevance ordered)
    2. Group trends into clusters (same topic normalized → same anchor)
    3. For each cluster → invoke Claude CLI with strict JSON schema
    4. Parse output → ResearchDossierCreate → IntelRepository.upsert_dossier
    5. Mark source signals as consumed_by_dossier=<dossier_id>

Legge 1 compliance: Claude CLI subprocess only (no SDK). The compiler
uses the same :class:`CLIRunner` injection pattern used by Council.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from backend.services.council.cli_runners import CLIRunner
from backend.services.intel.dossier_models import (
    DossierCitation,
    DossierEntity,
    DossierFact,
    DossierNumber,
    DossierPrecedent,
    ResearchDossier,
    ResearchDossierCreate,
    TopicCategory,
    TrendSignal,
)
from backend.services.intel.dossier_repository import IntelRepository
from backend.services.intel.dossier_slug import (
    build_dossier_slug,
    categorize_topic,
    flatten_topics,
)

logger = logging.getLogger(__name__)


# Default freshness for newly compiled dossiers (design §15.3: 30d archive).
DEFAULT_FRESHNESS_DAYS = 30
DEFAULT_BATCH_SIZE = 20
DEFAULT_CLUSTER_SIMILARITY = 3   # min shared keywords to group trends

MIN_CONFIDENCE = 0.3
MAX_CONFIDENCE = 0.95


@dataclass
class CompileSummary:
    ran_at: datetime
    batch_size: int = 0
    clusters_built: int = 0
    dossiers_compiled: int = 0
    dossiers_failed: int = 0
    signals_consumed: int = 0
    errors: list[str] = field(default_factory=list)
    per_dossier: list[dict[str, Any]] = field(default_factory=list)


_COMPILE_PROMPT_TEMPLATE = """Sei un analista compliance Indonesia per Bali Zero.
Hai questi segnali trending sullo stesso tema (topic: {topic_hint}).

SEGNALI GREZZI:
{signals_block}

COMPITO: compila un dossier strutturato in italiano. Rispondi SOLO JSON strict:

{{
  "title": "titolo preciso, max 100 char, in italiano",
  "topic_category": "visa|tax|kbli|property|compliance|cultural|macro|finance|crypto|other",
  "confidence_0_1": 0.0-1.0,
  "domains": ["chatbot","crm","nlm","curiosity","council","warroom","newsletter","guardian","team","public"],
  "public_safe": true|false,
  "facts": [
    {{"claim": "...", "source_url": "...", "confidence": 0.0-1.0}}
  ],
  "numbers": [
    {{"metric": "...", "value": 0, "unit": "...", "period": "...", "source": "..."}}
  ],
  "citations": [
    {{"norma": "...", "articolo": "...", "comma": "...", "quote_exact": "...", "year": 2026}}
  ],
  "entities_linked": [
    {{"kg_entity_id": "visa:B211A|kbli:47711|...", "type": "Visa|KBLI|Norma|Entity", "role": "subject|context"}}
  ],
  "summary_short": "140 char max",
  "summary_medium": "500 char max"
}}

Regole:
- SOLO fatti supportati dai segnali o da citazioni normative ufficiali.
- Se non sei sicuro del comma/articolo, ometti quel campo (non inventare).
- `domains` deve riflettere chi può ragionevolmente consumare questo dossier.
- `public_safe=false` se ci sono informazioni sensibili o specifiche di un cliente."""


class DossierCompiler:
    """Batch compiler TrendSignal → ResearchDossier using Claude CLI.

    Parameters
    ----------
    repo : IntelRepository
        Reads top trends, writes dossiers, marks consumed.
    runner : CLIRunner
        Claude (Opus/Sonnet) CLI used for the per-cluster compile call.
    batch_size : int
        Max trends pulled per sweep (design §15.5 top-20).
    freshness_days : int
        TTL applied to ``freshness_expiry`` of new dossiers.
    """

    def __init__(
        self,
        repo: IntelRepository,
        runner: CLIRunner,
        *,
        batch_size: int = DEFAULT_BATCH_SIZE,
        freshness_days: int = DEFAULT_FRESHNESS_DAYS,
        timeout_per_cluster: int = 90,
    ) -> None:
        self.repo = repo
        self.runner = runner
        self.batch_size = batch_size
        self.freshness_days = freshness_days
        self.timeout = timeout_per_cluster
        self.logger = logger

    # ── Main entry ───────────────────────────────────────────────

    async def run_once(self) -> CompileSummary:
        started = datetime.now(timezone.utc)
        summary = CompileSummary(ran_at=started)

        try:
            trends = await self.repo.top_unconsumed_trends(limit=self.batch_size)
        except Exception as exc:  # noqa: BLE001
            summary.errors.append(f"fetch_trends: {type(exc).__name__}: {exc}")
            return summary

        summary.batch_size = len(trends)
        if not trends:
            return summary

        clusters = _cluster_trends(trends)
        summary.clusters_built = len(clusters)

        for cluster in clusters:
            try:
                compiled = await self._compile_cluster(cluster)
                if compiled is None:
                    summary.dossiers_failed += 1
                    continue
                dossier, consumed_count = compiled
                summary.dossiers_compiled += 1
                summary.signals_consumed += consumed_count
                summary.per_dossier.append({
                    "dossier_id": str(dossier.id),
                    "slug": dossier.slug,
                    "topic_category": dossier.topic_category.value,
                    "facts": len(dossier.facts),
                    "citations": len(dossier.citations),
                    "confidence": dossier.confidence_0_1,
                })
            except Exception as exc:  # noqa: BLE001
                summary.dossiers_failed += 1
                summary.errors.append(
                    f"cluster {cluster[0].id}: {type(exc).__name__}: {exc}"
                )

        return summary

    # ── Per-cluster compile ─────────────────────────────────────

    async def _compile_cluster(
        self,
        cluster: list[TrendSignal],
    ) -> tuple[ResearchDossier, int] | None:
        if not cluster:
            return None
        anchor = cluster[0]
        topic_hint = flatten_topics(s.topic for s in cluster) or anchor.topic
        signals_block = _render_signals(cluster)

        prompt = _COMPILE_PROMPT_TEMPLATE.format(
            topic_hint=topic_hint,
            signals_block=signals_block,
        )
        parsed, result = await self.runner.run_json(prompt, timeout=self.timeout)
        if not result.ok or parsed is None:
            self.logger.info(
                "compiler: CLI failed for anchor=%s err=%s",
                anchor.id,
                result.error,
            )
            return None

        try:
            dossier_create = self._build_dossier_create(
                parsed=parsed,
                cluster=cluster,
                anchor=anchor,
                topic_hint=topic_hint,
            )
        except Exception as exc:  # noqa: BLE001
            self.logger.info(
                "compiler: parse error anchor=%s err=%s", anchor.id, exc,
            )
            return None

        dossier = await self.repo.upsert_dossier(dossier_create)

        consumed = 0
        for signal in cluster:
            try:
                await self.repo.mark_trend_consumed(signal.id, dossier.id)
                consumed += 1
            except Exception as exc:  # noqa: BLE001
                self.logger.warning(
                    "mark_consumed failed signal=%s: %s", signal.id, exc,
                )
        return dossier, consumed

    # ── Parser helpers ──────────────────────────────────────────

    def _build_dossier_create(
        self,
        *,
        parsed: dict[str, Any],
        cluster: list[TrendSignal],
        anchor: TrendSignal,
        topic_hint: str,
    ) -> ResearchDossierCreate:
        title = str(parsed.get("title") or topic_hint)[:200]
        category = _coerce_topic_category(parsed.get("topic_category"), topic_hint)
        confidence = _coerce_confidence(parsed.get("confidence_0_1"))

        slug = build_dossier_slug(title, anchor.id)
        freshness = datetime.now(timezone.utc) + timedelta(days=self.freshness_days)

        facts = [DossierFact(**_coerce_fact(f)) for f in _as_list(parsed.get("facts"))]
        numbers = [DossierNumber(**_coerce_number(n)) for n in _as_list(parsed.get("numbers"))]
        citations = [
            DossierCitation(**_coerce_citation(c)) for c in _as_list(parsed.get("citations"))
        ]
        entities = [
            DossierEntity(**_coerce_entity(e)) for e in _as_list(parsed.get("entities_linked"))
        ]
        precedents = [
            DossierPrecedent(**_coerce_precedent(p))
            for p in _as_list(parsed.get("precedents"))
        ]

        return ResearchDossierCreate(
            slug=slug,
            title=title,
            topic_category=category,
            freshness_expiry=freshness,
            domains=[str(d) for d in _as_list(parsed.get("domains"))],
            public_safe=bool(parsed.get("public_safe", False)),
            facts=facts,
            numbers=numbers,
            citations=citations,
            entities_linked=entities,
            precedents=precedents,
            confidence_0_1=confidence,
            source_signals=[s.id for s in cluster],
            language=str(parsed.get("language") or "it"),
            summary_short=_trim(parsed.get("summary_short"), 140),
            summary_medium=_trim(parsed.get("summary_medium"), 500),
        )


# ── Clustering ───────────────────────────────────────────────


def _normalize_words(topic: str) -> set[str]:
    import re
    return {
        w for w in re.split(r"[^a-z0-9]+", (topic or "").lower()) if len(w) >= 3
    }


def _cluster_trends(
    trends: list[TrendSignal],
    *,
    min_shared_words: int = DEFAULT_CLUSTER_SIMILARITY,
) -> list[list[TrendSignal]]:
    """Group by shared topic keywords — cheap, deterministic.

    Two trends share a cluster if their normalized-word sets intersect with
    >= ``min_shared_words`` tokens. Each trend is placed in exactly one cluster
    (greedy; order preserved).
    """
    if not trends:
        return []

    clusters: list[list[TrendSignal]] = []
    cluster_words: list[set[str]] = []

    for trend in trends:
        words = _normalize_words(trend.topic)
        placed = False
        for idx, existing in enumerate(cluster_words):
            if len(existing & words) >= min_shared_words:
                clusters[idx].append(trend)
                cluster_words[idx] = existing | words
                placed = True
                break
        if not placed:
            clusters.append([trend])
            cluster_words.append(words)

    # sort each cluster by urgency desc so anchor is most urgent signal
    for cluster in clusters:
        cluster.sort(key=lambda s: s.urgency_score, reverse=True)

    return clusters


# ── Coercion helpers ────────────────────────────────────────


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _coerce_topic_category(value: Any, topic_hint: str) -> TopicCategory:
    if isinstance(value, str):
        try:
            return TopicCategory(value)
        except ValueError:
            pass
    return categorize_topic(topic_hint)


def _coerce_confidence(value: Any) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 0.5
    if f < MIN_CONFIDENCE:
        return MIN_CONFIDENCE
    if f > MAX_CONFIDENCE:
        return MAX_CONFIDENCE
    return f


def _coerce_fact(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"claim": str(raw or ""), "confidence": 0.5}
    claim = str(raw.get("claim") or "")[:1000]
    conf = raw.get("confidence")
    try:
        conf_f = float(conf) if conf is not None else 0.5
    except (TypeError, ValueError):
        conf_f = 0.5
    source_url = raw.get("source_url")
    if source_url is not None:
        source_url = str(source_url)[:500]
    return {
        "claim": claim,
        "source_url": source_url,
        "confidence": max(0.0, min(1.0, conf_f)),
    }


def _coerce_number(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"metric": "unknown", "value": 0.0}
    try:
        val = float(raw.get("value") or 0)
    except (TypeError, ValueError):
        val = 0.0
    return {
        "metric": str(raw.get("metric") or "")[:200],
        "value": val,
        "unit": raw.get("unit"),
        "period": raw.get("period"),
        "source": raw.get("source"),
    }


def _coerce_citation(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"norma": str(raw or "")}
    year_raw = raw.get("year")
    try:
        year = int(year_raw) if year_raw is not None else None
    except (TypeError, ValueError):
        year = None
    return {
        "norma": str(raw.get("norma") or "")[:200],
        "articolo": raw.get("articolo"),
        "comma": raw.get("comma"),
        "quote_exact": raw.get("quote_exact"),
        "year": year,
    }


def _coerce_entity(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"kg_entity_id": str(raw or ""), "type": "Entity"}
    return {
        "kg_entity_id": str(raw.get("kg_entity_id") or "")[:200],
        "type": str(raw.get("type") or "Entity")[:60],
        "role": raw.get("role"),
    }


def _coerce_precedent(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"dossier_id_related": UUID(int=0), "relation": "see_also"}
    related = raw.get("dossier_id_related")
    try:
        related_uuid = UUID(str(related)) if related else UUID(int=0)
    except (TypeError, ValueError):
        related_uuid = UUID(int=0)
    return {
        "dossier_id_related": related_uuid,
        "relation": str(raw.get("relation") or "see_also"),
    }


def _trim(value: Any, max_chars: int) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    return s[:max_chars]


# ── Render helper for prompt ────────────────────────────────


def _render_signals(cluster: list[TrendSignal]) -> str:
    lines: list[str] = []
    for signal in cluster[:8]:   # cap to keep prompt small
        lines.append(
            f"- [{signal.source.value}] urgency={signal.urgency_score:.1f} "
            f"rel={signal.bali_zero_relevance or 0:.1f}\n"
            f"  title: {signal.raw_title or signal.topic}\n"
            f"  snippet: {(signal.raw_snippet or '')[:240]}\n"
            f"  url: {signal.source_url or ''}"
        )
    return "\n".join(lines)
