"""Intel Lake Tier 1 Router — rules-based routing for incoming intel_items.

Subscribes to PG channel `intel_lake_event` via EventBus (event_type
`intel_lake.event`). On each new item, applies regex rules to source_domain
to set `routing_status` and `routing_targets`.

Routing categories:
- nb-intel: Indonesian regulatory/legal/AI research → push to NotebookLM NB-INTEL
- blog:    Indonesian press/news → eligible for balizero.com blog
- archive: OSINT social/reddit/twitter/youtube → keep for trend analysis only
- skip:    explicit drop (no current rules)
- needs_review: NO rule matched → Tier 2 LLM (weekly)

Key invariants:

1. Trigger loop prevention: PG trigger `trg_notify_intel_lake_event` is
   AFTER INSERT only (mig 168). Router does UPDATE, NOT INSERT.

2. Idempotency: UPDATE guarded by `WHERE routing_status='unrouted'`.

3. Hot-loop prevention: regex anchored at ^ on source_domain (already
   canonicalized lowercase by IntelLakeService).

4. Multi-process safety: idempotency guard handles parallel listeners.

5. Cold-start: existing pre-deploy unrouted rows handled by
   `backfill_unrouted()` one-shot helper.

6. Audit: every routing decision logged with producer_name='router',
   request_path='router/tier1'.

Design: research/symbiosis/2026-05-13-intel-lake-router-tier1-design.md
"""

from __future__ import annotations

import logging
import os
import re
from typing import TYPE_CHECKING, Any

import asyncpg

if TYPE_CHECKING:
    from backend.services.events.event_bus import EventBus

logger = logging.getLogger(__name__)


# ─── NB-INTEL NotebookLM UUIDs (production, verified) ───────────────────────

NB_INTEL_IMMIGRATION = "78573978-4564-4bdc-b082-fbd625c2d33d"
NB_INTEL_TAX = "78b45ad8-ddce-4bd8-bdf0-3b45800897da"
NB_INTEL_REGULATION = "80821295-703f-40ab-a32a-f0307e43ae2a"
NB_INTEL_PRESS = "caec5b82-287c-464f-844f-02e2c8f04c21"
NB_INTEL_AI_RESEARCH = "d48c4933-4d93-4d1e-8753-23b88145ba78"

# ─── NB-PROBE-SANDBOX (Phase F, 2026-05-20) ─────────────────────────────────
# Dedicated NotebookLM for synthetic e2e probes. Never NB-INTEL family.
# Matching rule: source_domain == "probe-sandbox.example.test" (RFC 2606 .test
# TLD never resolves on the public internet — only probe scripts use it).
# Migration 187 CHECK constraint enforces canonical_url prefix at INSERT.
NB_PROBE_SANDBOX = "7e6ae978-136c-4c96-bed5-9fab6f39176f"


# ─── Routing rules (closed-set, applied top-to-bottom; first match wins) ────

# 2-stage routing fix (PR-B1a 2026-05-20):
# Empirical bug: 90% of items fell to needs_review because regex `^kompas`
# fails to match `money.kompas.com`, `en.tempo.co`, `www.antaranews.com`
# (subdomain prefixes). Fix: tolerate press subdomain prefixes only for exact
# approved press roots.
# Plus: press_indonesian rule split into 2-stage (eligibility + content-gate)
# to send regulatory-keyword press to nb-intel/press instead of blog (which
# was starving NB-INTEL-Press notebook).
#
# 3-LLM panel approved (Gemini + Codex + DeepSeek convergent 2026-05-20):
# "Routing expansion MUST be 2-stage (domain + keyword)". Reference:
# .worktrees/audit-2026-05-20/docs/audit/2026-05-20-panel-verdict.md

# Tolerate press subdomain prefixes (e.g. `www.`, `en.`, `money.`, `sumsel.`).
# This is intentionally used for generic press domains only. Government and
# official-source rules stay strict so arbitrary-looking hostnames such as
# `malicious.imigrasi.go.id` do not bypass the review queue.
_SUBDOMAIN_PREFIX = r"(?:[a-z0-9-]+\.)*"
_PRESS_GENERAL_DOMAINS = (
    r"detik\.com|kompas\.com|tempo\.co|tribunnews\.com|"
    r"jakartapost\.com|thejakartapost\.com|antaranews\.com|"
    r"bisnis\.com|cnnindonesia\.com|kontan\.co\.id|"
    r"katadata\.co\.id|katadata\.id|"
    r"indonesiaexpat\.id|letsmoveindonesia\.com|expat\.com|"
    r"livenworkindonesia\.com|jakartaglobe\.id|investinasia\.id|"
    r"balinews\.live|chiangraitimes\.com"
)

# Content-gate keywords for stage-2 classification of generic press domains.
# When a domain matches `press_general` AND title/url contains one of these,
# route to nb-intel/press (NB-INTEL-Press notebook). Otherwise route to blog.
_PRESS_REGULATORY_KEYWORDS = (
    # Immigration
    "visa",
    "kitas",
    "kitap",
    "imigrasi",
    "voa",
    "golden visa",
    "c1 ",
    "c2 ",
    "d2 ",
    "d12",
    "e23",
    "e28",
    # Tax
    "pajak",
    "tax",
    "pph",
    "ppn",
    "spt",
    "vat",
    "pmk",
    "coretax",
    "npwp",
    # Regulation
    "kbli",
    "pt pma",
    "oss",
    "bkpm",
    "ruu",
    "peraturan",
    "perpres",
    "permenkumham",
    "permenkeu",
    "permenaker",
    "permenkes",
    "pp nomor",
    "uu nomor",
    "regulasi",
    # Compliance / financial
    "lkpm",
    "investasi",
    "investment",
    "compliance",
    "regulatory",
)


def _build_press_pattern(domains: str) -> re.Pattern[str]:
    """Build an exact hostname regex that tolerates press subdomains."""
    return re.compile(rf"^{_SUBDOMAIN_PREFIX}(?:{domains})$")


def _compile_keyword_pattern(keyword: str) -> re.Pattern[str]:
    """Compile a keyword matcher with token boundaries and flexible spacing."""
    escaped_parts = [re.escape(part) for part in keyword.strip().split()]
    body = r"[\s_-]+".join(escaped_parts)
    return re.compile(rf"(?<![a-z0-9]){body}(?![a-z0-9])")


_PRESS_REGULATORY_PATTERNS = tuple(
    _compile_keyword_pattern(keyword) for keyword in _PRESS_REGULATORY_KEYWORDS
)


_RULES: list[tuple[re.Pattern[str], str, dict[str, Any], str]] = [
    # ─── Sandbox probe (Phase F, 2026-05-20) ────────────────────────────────
    # Match EXACT RFC 2606 .test domain — never the public internet.
    # First rule so probes are routed before any other classification.
    # Uses ^...$ anchors via fullmatch semantics (pattern.match anchors at
    # start; explicit $ anchors at end) to prevent prefix attacks like
    # "probe-sandbox.example.test.evil.com".
    (
        re.compile(r"probe-sandbox\.example\.test$"),
        "nb-intel",
        {"nb_uuids": [NB_PROBE_SANDBOX]},
        "probe_sandbox",
    ),
    # Immigration (visa, KITAS, KITAP) → NB-INTEL-Immigration
    (
        re.compile(
            r"imigrasi\.go\.id|kanwilkemenkumham|kemenkumham\.go\.id|"
            r"kanim\.|jdih\.kemenkumham"
        ),
        "nb-intel",
        {"nb_uuids": [NB_INTEL_IMMIGRATION]},
        "immigration_govid",
    ),
    # Tax (PMK, PPh, SPT, Coretax) → NB-INTEL-Tax
    (
        re.compile(
            r"pajak\.go\.id|ortax\.org|ddtcnews|mucconsulting|"
            r"ikpi\.or\.id|kemenkeu\.go\.id|jdih\.kemenkeu"
        ),
        "nb-intel",
        {"nb_uuids": [NB_INTEL_TAX]},
        "tax_govid",
    ),
    # Regulation/KBLI/PT PMA → NB-INTEL-Regulation
    (
        re.compile(
            r"bkpm\.go\.id|oss\.go\.id|kemendag\.go\.id|"
            r"jdih\.bkpm|jdih\.menpan|jdih\.setkab|peraturan\.go\.id"
        ),
        "nb-intel",
        {"nb_uuids": [NB_INTEL_REGULATION]},
        "regulation_govid",
    ),
    # AI research / academic → NB-INTEL-AIResearch
    (
        re.compile(
            r"arxiv\.org|github\.com|huggingface\.co|openai\.com|"
            r"anthropic\.com|deepmind\.com|paperswithcode"
        ),
        "nb-intel",
        {"nb_uuids": [NB_INTEL_AI_RESEARCH]},
        "ai_research",
    ),
    # Indonesian press / news (generic eligibility — content gate applied
    # below in `_classify_press_general`). Expanded 2026-05-20 to include
    # English-language Indonesia-facing news/expat portals.
    (
        _build_press_pattern(_PRESS_GENERAL_DOMAINS),
        "press_general",  # placeholder — content gate decides nb-intel/press vs blog
        {},
        "press_general",
    ),
    # OSINT social → archive
    (
        re.compile(r"^(reddit|twitter|x\.com|youtube|t\.co|medium\.com)"),
        "archive",
        {},
        "osint_social",
    ),
]


_PRESS_GENERAL_RE = _build_press_pattern(_PRESS_GENERAL_DOMAINS)


def _press_content_gate(title: str | None, canonical_url: str | None) -> bool:
    """Stage-2 gate: True if title/url contains a regulatory keyword.

    Used by `press_general` rule to split into:
      - nb-intel/press   (regulatory content — feed NB-INTEL-Press)
      - blog             (general news — keep for balizero.com blog only)
    """
    haystack = " ".join(filter(None, [title, canonical_url])).lower()
    if not haystack:
        return False
    return any(pattern.search(haystack) for pattern in _PRESS_REGULATORY_PATTERNS)


# Shadow-mode flag (PR-B1a 2026-05-20): if set, the router logs the NEW
# classification but does NOT update the DB — used to validate the 2-stage
# fix on real traffic before bulk backfill. Set via Fly secret or local env:
#   fly secrets set INTEL_LAKE_ROUTING_SHADOW=1 -a nuzantara-rag
# Unset (default) → normal classification.
_SHADOW_MODE = os.environ.get("INTEL_LAKE_ROUTING_SHADOW", "").lower() in (
    "1",
    "true",
    "yes",
)


class IntelLakeRouter:
    """Tier 1 routing service (rules-only, no LLM)."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self._pool = db_pool

    async def route_event(self, payload: dict[str, Any]) -> None:
        """Handle one `intel_lake.event` payload.

        Idempotent: UPDATE guarded by routing_status='unrouted'.

        Payload (from PG trigger ``trg_notify_intel_lake_event``):
          - item_id (uuid str)
          - canonical_url (str)
          - source_domain (str, lowercase)
          - topic_tags (list[str])
          - routing_status (str)
          - first_seen_at (iso str)

        For stage-2 content-gate (press_general rule), also reads ``title``
        and ``canonical_url`` from the payload. Missing fields → conservative
        fallback to ``blog`` (preserves pre-B1a behavior).
        """
        item_id = payload.get("item_id")
        source_domain = (payload.get("source_domain") or "").strip().lower()
        # Trigger NOTIFY payload does NOT include title (size optimization in
        # migration 168). For the 2-stage press_general content gate we need
        # title — fetch lazily from DB only when domain matches press_general.
        # No-op for all other rules (no extra query).
        canonical_url = payload.get("canonical_url")
        title = payload.get("title")

        if not item_id:
            logger.warning("intel_lake_router: missing item_id in payload")
            return

        # Lazy title fetch only when needed (content-gate eligibility check)
        if title is None and source_domain and _PRESS_GENERAL_RE.match(source_domain):
            try:
                async with self._pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT title, canonical_url FROM intel_items WHERE id = $1::uuid",
                        item_id,
                    )
                    if row is not None:
                        title = row["title"]
                        canonical_url = canonical_url or row["canonical_url"]
            except Exception as exc:
                logger.warning(
                    "intel_lake_router: title lookup failed item_id=%s: %s",
                    item_id,
                    exc,
                )

        decision = self._classify(source_domain, title, canonical_url)
        new_status = decision["status"]
        new_targets = decision["targets"]
        rule_name = decision["rule"]

        # Shadow-mode: log but do not write. Phase-C empirical validation.
        if _SHADOW_MODE:
            logger.info(
                "intel_lake_router SHADOW item_id=%s domain=%s rule=%s status=%s",
                item_id,
                source_domain,
                rule_name,
                new_status,
            )
            return

        try:
            async with self._pool.acquire() as conn:
                # NOTE: bind ``new_targets`` as a raw dict, NOT json.dumps(...).
                # The pool's jsonb codec (``backend/app/core/database.py``)
                # registers ``encoder=json.dumps`` — pre-serializing here
                # double-encodes and lands a jsonb *string* ("{}") instead of
                # a jsonb *object* ({}). Regression fixed 2026-05-14.
                affected = await conn.fetchval(
                    """
                    UPDATE intel_items
                       SET routing_status = $2,
                           routing_targets = $3::jsonb
                     WHERE id = $1::uuid
                       AND routing_status = 'unrouted'
                    RETURNING id
                    """,
                    item_id,
                    new_status,
                    new_targets,
                )
                await conn.execute(
                    """
                    INSERT INTO intel_lake_audit_log
                        (producer_name, client_ip, request_path, status_code,
                         payload_size, error_message)
                    VALUES ($1, NULL, $2, $3, NULL, $4)
                    """,
                    "router",
                    "router/tier1",
                    200 if affected else 304,
                    f"rule={rule_name} status={new_status}",
                )
        except Exception as exc:
            logger.exception(
                "intel_lake_router: UPDATE failed item_id=%s domain=%s: %s",
                item_id,
                source_domain,
                exc,
            )
            try:
                async with self._pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO intel_lake_audit_log
                            (producer_name, client_ip, request_path, status_code,
                             payload_size, error_message)
                        VALUES ('router', NULL, 'router/tier1', 500, NULL, $1)
                        """,
                        f"item_id={item_id} domain={source_domain}: {exc}"[:200],
                    )
            except Exception:
                pass

    def _classify(
        self,
        source_domain: str,
        title: str | None = None,
        canonical_url: str | None = None,
    ) -> dict[str, Any]:
        """Apply rules, return routing decision. NO DB I/O.

        2-stage routing for ``press_general`` rule (PR-B1a 2026-05-20):
        - Stage 1 (eligibility): domain matches the press_general pattern
        - Stage 2 (content gate): title/url contains regulatory keyword
          → upgrade to ``nb-intel`` targeting NB-INTEL-Press
          → otherwise route to ``blog`` (existing legacy behavior)

        All other rules unchanged.
        """
        for pattern, status, targets, rule_name in _RULES:
            if pattern.match(source_domain):
                # 2-stage gate for generic press domains
                if status == "press_general":
                    if _press_content_gate(title, canonical_url):
                        return {
                            "status": "nb-intel",
                            "targets": {"nb_uuids": [NB_INTEL_PRESS]},
                            "rule": f"{rule_name}+regulatory",
                        }
                    return {
                        "status": "blog",
                        "targets": {},
                        "rule": f"{rule_name}+general",
                    }
                return {"status": status, "targets": targets, "rule": rule_name}
        return {"status": "needs_review", "targets": {}, "rule": "no_match"}


async def backfill_unrouted(db_pool: asyncpg.Pool, batch_size: int = 100) -> int:
    """Apply Tier 1 rules to all existing `routing_status='unrouted'` rows.

    One-shot manual run after first deploy. Idempotent.
    """
    router = IntelLakeRouter(db_pool)
    total = 0
    while True:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, source_domain, title, canonical_url
                  FROM intel_items
                 WHERE routing_status = 'unrouted'
                 LIMIT $1
                """,
                batch_size,
            )
        if not rows:
            break
        for row in rows:
            await router.route_event(
                {
                    "item_id": str(row["id"]),
                    "source_domain": row["source_domain"],
                    "title": row["title"],
                    "canonical_url": row["canonical_url"],
                }
            )
        total += len(rows)
        logger.info("backfill_unrouted: processed %s (total=%s)", len(rows), total)
        if len(rows) < batch_size:
            break
    return total


async def backfill_needs_review(
    db_pool: asyncpg.Pool, batch_size: int = 100, dry_run: bool = True
) -> dict[str, int]:
    """Re-classify ``needs_review`` items with the new 2-stage rules (PR-B1a).

    Mirrors ``backfill_unrouted`` but targets the ``needs_review`` pool.
    DEFAULT IS DRY-RUN — set ``dry_run=False`` after panel validates the
    shadow-mode output on a sample.

    Returns counts dict: ``{selected, reclassified, nb_intel, blog, archive,
    needs_review, skipped}``.

    Usage (one-shot, after PR-B1a deploys):
        python -c "import asyncio; from backend.services.intel.intel_lake_router \
import backfill_needs_review; from backend.app.core.database import \
get_db_pool; asyncio.run(backfill_needs_review(await get_db_pool(), \
dry_run=False))"
    """
    counts: dict[str, int] = {
        "selected": 0,
        "reclassified": 0,
        "nb-intel": 0,
        "blog": 0,
        "archive": 0,
        "needs_review": 0,
        "skipped": 0,
    }
    router = IntelLakeRouter(db_pool)
    last_seen_id: str | None = None
    while True:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, source_domain, title, canonical_url
                  FROM intel_items
                 WHERE routing_status = 'needs_review'
                   AND ($2::uuid IS NULL OR id > $2::uuid)
                 ORDER BY id
                 LIMIT $1
                """,
                batch_size,
                last_seen_id,
            )
        if not rows:
            break
        counts["selected"] += len(rows)
        last_seen_id = str(rows[-1]["id"])
        for row in rows:
            decision = router._classify(
                (row["source_domain"] or "").strip().lower(),
                row["title"],
                row["canonical_url"],
            )
            new_status = decision["status"]
            counts[new_status] = counts.get(new_status, 0) + 1
            if new_status == "needs_review":
                counts["skipped"] += 1
                continue
            counts["reclassified"] += 1
            if dry_run:
                continue
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE intel_items
                       SET routing_status = $2,
                           routing_targets = $3::jsonb
                     WHERE id = $1::uuid
                       AND routing_status = 'needs_review'
                    """,
                    row["id"],
                    new_status,
                    decision["targets"],
                )
        if len(rows) < batch_size:
            break
    logger.info(
        "backfill_needs_review (%s): %s",
        "DRY-RUN" if dry_run else "APPLIED",
        counts,
    )
    return counts


def register_intel_lake_router_handlers(bus: EventBus, db_pool: asyncpg.Pool) -> None:
    """Register Tier 1 router on `intel_lake.event` channel.

    Called from backend.services.events.handlers._core.register_handlers.
    """
    router = IntelLakeRouter(db_pool)
    bus.subscribe("intel_lake.event", router.route_event)
    logger.info("intel_lake_router: subscribed to intel_lake.event channel")
