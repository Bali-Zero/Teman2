#!/usr/bin/env python3
"""
Intel Radar — hourly web search for Bali Zero business intelligence.

# Organo: intel-radar (cron-agent-python) →
#   produce: rows in `intel_radar_findings` (canonical handoff to scraper)
#   + Redis cache `bz:intel-radar:seen` per deduplicazione hot-path
# Consuma da: Brave Search API → DuckDuckGo fallback (web_search helper)
#
# Ruolo: ricercatore proattivo. Cerca notizie rilevanti per il business
#         (investimento, visa, normative, mercato) e le accumula in DB.
#         Il digest serale (intel_radar_daily_digest.py) le legge, riassume,
#         e notifica Zero. Lo scraper le pesca processed=true & not picked.
#
# Refactor 2026-04-26 (PR-1 §A):
#   - freshness pw → pd (giorno, non settimana)
#   - 12 query flat → 3 tier × 12 query (L1/L2/L3) ruotanti per ora WITA
#   - Telegram digest orario rimosso → solo INSERT in intel_radar_findings
#     (digest serale separato in intel_radar_daily_digest.py)
#   - Feature-flag INTEL_RADAR_PERSIST_DB / INTEL_RADAR_FRESHNESS retrocompat

Tier rotation by hour-of-day WITA (UTC+8):
  - 0-7   → L1 (core: visa, kitas, KBLI, OSS, BPN, pajak, BPJS)
  - 8-15  → L2 (adjacent: banking, fintech, real estate, tourism stats, expat)
  - 16-23 → L3 (lateral: rupiah/dollar, ASEAN, US/China-Indonesia, G20, COP)

Each hour: 1 query from the active tier (round-robin within tier).
Total daily queries: 24 (was 24, no change in volume — only tier-aware).

Deduplication:
  - Redis hot path: 7-day TTL set of URL hashes (preserves old logic for backward compat)
  - DB hard dedup: UNIQUE(canonical_url) on intel_radar_findings (migration 139)

Output: only DB INSERT (when INTEL_RADAR_PERSIST_DB=true). Telegram is silent.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))  # for intel_lake_outbox
from agent_job import AgentJob, RunResult, WITA, main, web_search

# Intel Lake Wave 1 (2026-05-12): dual-write to local SQLite outbox so the
# observations table on Fly backend gets every finding even when intel_radar_findings
# ON CONFLICT DO NOTHING skips an insert. Best-effort: failure to enqueue
# MUST NOT break the main radar flow.
try:
    from intel_lake_outbox import enqueue as _lake_enqueue  # type: ignore
    _LAKE_ENABLED = True
except Exception:
    _LAKE_ENABLED = False
    _lake_enqueue = None  # type: ignore


# Three tier query rotation (12 queries each).
# L1 = CORE: regulatory and operational queries Bali Zero clients ask weekly.
L1_QUERIES = [
    "investasi asing Indonesia regulation terbaru",
    "digital nomad visa Bali update",
    "KITAS KITAP regulation Indonesia terbaru",
    "company formation Indonesia PT PMA new rules",
    "pajak tax regulation Indonesia terbaru",
    "OSS perizinan update Indonesia",
    "BKPM permit foreign investment Indonesia",
    "BPJS kesehatan ketenagakerjaan terbaru",
    "BPN sertifikat tanah hak guna bangunan",
    "KBLI klasifikasi baku lapangan usaha update",
    "imigrasi visa on arrival Indonesia",
    "pajak penghasilan PPh 21 25 terbaru",
]

# L2 = ADJACENT: market and ecosystem signals that affect clients indirectly.
L2_QUERIES = [
    "perbankan Indonesia foreign account regulation",
    "fintech Indonesia OJK regulation terbaru",
    "Bali real estate market property law",
    "tourism statistics Indonesia BPS",
    "expat events conference Indonesia",
    "Indonesia startup ecosystem investment",
    "Bali property ownership foreigner regulation",
    "Indonesia e-commerce regulation update",
    "OJK fintech P2P lending Indonesia",
    "Bank Indonesia rupiah policy update",
    "Indonesia economic outlook quarterly",
    "Bali tourism recovery 2026",
]

# L3 = LATERAL: macro/geopolitical signals — slow-moving but high-impact tail risks.
L3_QUERIES = [
    "rupiah dollar exchange Indonesia outlook",
    "ASEAN policy Indonesia integration",
    "US Indonesia trade investment relations",
    "China Indonesia investment infrastructure",
    "G20 Indonesia outcome statement",
    "COP climate Indonesia commitment",
    "Bali climate disaster risk",
    "Indonesia geopolitical strategic position",
    "ASEAN summit outcomes Indonesia",
    "Indonesia inflation interest rate Bank Indonesia",
    "global supply chain Indonesia impact",
    "regional cooperation Indonesia Pacific",
]


def _active_tier(hour: int) -> str:
    """Return tier label for the given hour-of-day (WITA, 0-23)."""
    if 0 <= hour <= 7:
        return "L1"
    if 8 <= hour <= 15:
        return "L2"
    return "L3"


def _tier_queries(tier: str) -> list[str]:
    return {"L1": L1_QUERIES, "L2": L2_QUERIES, "L3": L3_QUERIES}[tier]


REDIS_SEEN_KEY = "bz:intel-radar:seen"
REDIS_SEEN_TTL = 86400 * 7  # 7 days


# URL canonicalization — strip tracking params + fragment, lowercase host.
# Used for UNIQUE(canonical_url) dedup at the DB layer.
_TRACKING_PARAM_RE = re.compile(r"^(utm_|fbclid|gclid|mc_eid|mc_cid|_ga|ref$|src$)", re.I)


def _canonical_url(raw: str) -> str:
    try:
        p = urlparse(raw.strip())
        host = (p.netloc or "").lower()
        # Strip default ports
        host = host.replace(":80", "").replace(":443", "")
        # Filter tracking query params
        if p.query:
            keep = {k: v for k, v in parse_qs(p.query, keep_blank_values=False).items()
                    if not _TRACKING_PARAM_RE.match(k)}
            query = urlencode(keep, doseq=True) if keep else ""
        else:
            query = ""
        path = (p.path or "/").rstrip("/") or "/"
        return urlunparse((p.scheme.lower() or "https", host, path, "", query, "")).rstrip("?")
    except Exception:
        return raw.lower().strip()


def _content_hash(title: str, description: str) -> str:
    """sha256 of title + ' ' + description, lowercased + whitespace-normalized."""
    text = f"{(title or '').strip()} {(description or '').strip()}".lower()
    text = re.sub(r"\s+", " ", text)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class IntelRadarJob(AgentJob):
    name = "intel-radar"
    timeout_s = 120
    requires_side_effects = False  # only side effects if new intel found

    async def run(self) -> RunResult:
        # Pick query based on current hour: tier from hour bucket, query from
        # round-robin within tier (uses hour itself as index for determinism).
        now = datetime.now(WITA)
        hour = now.hour
        tier = _active_tier(hour)
        queries = _tier_queries(tier)
        query = queries[hour % len(queries)]

        # Freshness: 'pd' (past day) by default; can be overridden via env for
        # backward-compat with older cron schedules that wanted weekly window.
        freshness = os.getenv("INTEL_RADAR_FRESHNESS", "pd")

        self.log_step(
            "search_start",
            inputs={"query": query, "hour": hour, "tier": tier, "freshness": freshness},
        )

        results = await web_search(query, count=5, freshness=freshness, logger=self.logger)
        self.log_step(
            "search_done",
            outputs={
                "results": len(results),
                "source": results[0]["source"] if results else "none",
            },
        )

        if not results:
            return RunResult(
                status="ok",
                duration_s=self._elapsed(),
                side_effects=self._side_effects,
                output="no_results",
            )

        # Hot-path dedup via Redis (preserves legacy behavior).
        new_results = self._filter_new(results)
        self.log_step("dedup_redis", outputs={"new": len(new_results), "total": len(results)})

        if not new_results:
            return RunResult(
                status="ok",
                duration_s=self._elapsed(),
                side_effects=self._side_effects,
                output="no_new_intel",
            )

        # Mark seen in Redis (7-day TTL).
        self._mark_seen(new_results)

        # DB persistence (feature-flagged for safe rollout).
        if os.getenv("INTEL_RADAR_PERSIST_DB", "false").lower() == "true":
            inserted = await self._persist_to_db(query, tier, new_results)
            self.log_step(
                "db_persist",
                outputs={"inserted": inserted, "candidates": len(new_results)},
                side_effect="intel_radar_findings_insert" if inserted > 0 else None,
            )

        # No Telegram. Daily digest job (intel_radar_daily_digest.py at 18:00 WITA)
        # reads from intel_radar_findings WHERE processed=false and notifies once/day.
        return RunResult(
            status="ok",
            duration_s=self._elapsed(),
            side_effects=self._side_effects,
            output=json.dumps(
                {
                    "tier": tier,
                    "query": query,
                    "new": len(new_results),
                },
                default=str,
            ),
        )

    async def _persist_to_db(
        self,
        query: str,
        tier: str,
        results: list[dict],
    ) -> int:
        """INSERT findings into intel_radar_findings.

        Returns the count of rows actually inserted (UNIQUE(canonical_url) may
        skip duplicates already seen in earlier runs).
        """
        try:
            import asyncpg  # local import: only loaded when flag enabled
        except ImportError:
            self.logger.error("asyncpg_missing", msg="install asyncpg or unset INTEL_RADAR_PERSIST_DB")
            return 0

        dsn = os.getenv("DATABASE_URL")
        if not dsn:
            self.logger.error("database_url_missing")
            return 0

        inserted = 0
        try:
            conn = await asyncpg.connect(dsn, timeout=10)
        except Exception as exc:
            self.logger.error("db_connect_failed", error=str(exc))
            return 0

        try:
            for r in results:
                url = (r.get("url") or "").strip()
                if not url:
                    continue
                canonical = _canonical_url(url)
                title = r.get("title") or ""
                description = r.get("description") or ""
                content_hash = _content_hash(title, description)
                source = r.get("source") or "brave"
                # Sprint 5: defense-in-depth — DB function COALESCEs to
                # 'unknown' but Python fallback avoids NULL crossing the
                # asyncpg boundary. urlparse() can yield empty netloc on
                # non-standard URLs (file://, data:, etc.).
                source_domain = urlparse(canonical).netloc or "unknown"

                published_at = r.get("published_at") or r.get("age")
                # Best-effort parse: only accept ISO-ish strings; otherwise NULL.
                published_dt = None
                if published_at and isinstance(published_at, str):
                    try:
                        published_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                    except ValueError:
                        published_dt = None

                # Step 1: INSERT finding (fail-soft per existing contract).
                # If duplicate URL, fetch the existing id for re-tagging
                # as a corroboration signal (Sprint 5 R3 verdict).
                finding_id = None
                is_corroboration = False
                try:
                    rec = await conn.fetchrow(
                        """
                        INSERT INTO intel_radar_findings (
                            query, query_tier, url, canonical_url, content_hash,
                            title, description, source_domain, published_at, source
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        ON CONFLICT (canonical_url) DO NOTHING
                        RETURNING id
                        """,
                        query, tier, url, canonical, content_hash,
                        title[:500], description[:2000], source_domain, published_dt, source,
                    )
                    if rec is not None:
                        finding_id = rec["id"]
                        inserted += 1
                    else:
                        # Duplicate URL — fetch existing id so we can re-tag
                        # provenance and bump credibility (corroboration).
                        existing = await conn.fetchrow(
                            "SELECT id FROM intel_radar_findings WHERE canonical_url = $1",
                            canonical,
                        )
                        if existing is not None:
                            finding_id = existing["id"]
                            is_corroboration = True
                except Exception as exc:
                    self.logger.warning("db_insert_failed", url=url[:80], error=str(exc))
                    continue

                # Step 2: tag provenance via mata_garuda DB function.
                # SEPARATE try/except (best-effort, R1 verdict) — finding row
                # is already committed; provenance failure must NOT trigger
                # rollback or skip the next finding. Pattern copied from WR2
                # _tag_provenance_safe().
                if finding_id is not None:
                    try:
                        await conn.fetchval(
                            "SELECT mata_garuda.tag_intel_finding($1, $2, $3, $4, $5)",
                            finding_id, source_domain, query, tier, is_corroboration,
                        )
                    except Exception as exc:
                        self.logger.warning(
                            "tag_provenance_failed",
                            finding_id=finding_id,
                            error=str(exc),
                        )

                # Step 3 (Intel Lake Wave 1, 2026-05-12):
                # Enqueue to local SQLite outbox for downstream lake dispatch.
                # ALWAYS enqueue regardless of INSERT/ON CONFLICT outcome —
                # intel_observations table is append-only (every producer-hit
                # counts as a trust signal). Drain worker
                # ~/scripts/intel-lake-outbox-drain.py posts batches every 60s.
                # Best-effort: outbox failure MUST NOT block the radar.
                if _LAKE_ENABLED and _lake_enqueue is not None:
                    try:
                        _lake_enqueue(
                            "intel_radar",
                            {
                                "producer_name": "intel_radar",
                                "canonical_url": canonical,
                                "content_hash": content_hash,
                                "title": title[:500],
                                "summary": description[:2000],
                                "source_domain": source_domain,
                                "language": None,
                                "jurisdiction": None,
                                "topic_tags": [tier.lower(), source],
                                "published_at": published_dt.isoformat() if published_dt else None,
                                "score": None,
                                "raw_payload": {
                                    "query": query,
                                    "tier": tier,
                                    "source": source,
                                    "url": url,
                                    "is_corroboration": is_corroboration,
                                    "finding_id": str(finding_id) if finding_id else None,
                                },
                            },
                        )
                    except Exception as exc:
                        self.logger.warning(
                            "lake_enqueue_failed",
                            url=url[:80],
                            error=str(exc),
                        )
        finally:
            await conn.close()

        return inserted

    def _url_hash(self, url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()[:12]

    def _filter_new(self, results: list[dict]) -> list[dict]:
        try:
            out = subprocess.run(
                ["redis-cli", "SMEMBERS", REDIS_SEEN_KEY],
                capture_output=True, text=True, timeout=3,
            )
            seen: set = set(out.stdout.strip().splitlines()) if out.returncode == 0 else set()
            return [r for r in results if self._url_hash(r.get("url", "")) not in seen]
        except Exception:
            return results

    def _mark_seen(self, results: list[dict]) -> None:
        try:
            for r in results:
                h = self._url_hash(r.get("url", ""))
                subprocess.run(
                    ["redis-cli", "SADD", REDIS_SEEN_KEY, h],
                    capture_output=True, timeout=3,
                )
            subprocess.run(
                ["redis-cli", "EXPIRE", REDIS_SEEN_KEY, str(REDIS_SEEN_TTL)],
                capture_output=True, timeout=3,
            )
        except Exception:
            pass

    def _elapsed(self) -> float:
        return time.time() - self.started_at


if __name__ == "__main__":
    main(IntelRadarJob)
