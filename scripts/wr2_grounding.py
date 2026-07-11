#!/usr/bin/env python3
"""WR2 grounding — populate brief_json.enrichment with regulatory rails (cron-safe).

WHY THIS EXISTS (root cause, 2026-06-24)
----------------------------------------
`wr2_fact_checker` flags every `law` claim as `unverifiable` (capping a draft at
`fact_check_status='degraded'`) unless the source corpus it scans —
`research_json + brief_json + council_debate_json`, flattened by
`_extract_source_text` — contains a law citation in a `LAW_PATTERNS` form. On 12/12
live drafts (DB audit 2026-06-24) `brief_json.enrichment` was `{}` and no citation
was present, so accurate carousels never earned a clean fact-check.

The grounding producer was already designed (`warroom_step2_briefer.py`, PR #1155):
`_inject_rails_into_facts` injects verbatim law citations + key numbers + taboo INTO
`enrichment.the_facts` — the exact text the fact-checker scans. But that script's
WRAPPER is incompatible with the live pipeline (it reads `intel_items`, needs a human
gate, and INSERTs its own drafts), and it was never armed. So the *engine* is reused
here and called in-process from `wr2_topic_selector` right before its INSERT.

WHY HTTP (not the local RAG)
----------------------------
The "local RAG" (`backend.services.rag.hybrid_search`) does NOT run on Pro/Mini: it
needs a remote Qdrant host + OPENAI_API_KEY (embeddings) + JWT_SECRET_KEY + API_KEYS,
none of which exist outside Fly (verified 2026-06-24: import dies on pydantic Settings
validation). The cron-safe source is the Fly backend RAG the topic-selector ALREADY
talks to (`NUZANTARA_BACKEND_URL` + `X-API-Key`). We query it over HTTP, read the
answer text, and extract the law citations the same way the fact-checker matches them.

KNOWN GAP — UPDATED 2026-07-07 (was: verified live 2026-06-24, 3 domains): the
chat-stream RAG endpoint (/api/v2/bali-zero/chat-stream) still returns prose +
title-only sources, NOT extractable PP/PMK/UU N/YYYY citations on its own. As of
2026-07-07 the search tool backing `/api/oracle/query` now fills a `snippet`
field (first 500 chars of the retrieved chunk) on every source/citation entry
(`backend/services/rag/agentic/tools.py`), so `_query_oracle()` below queries
that endpoint directly and scans `answer` + every `citations[].snippet` +
`sources[].snippet` for law citations. `ground_enrichment` tries the chat-stream
path FIRST (cheaper, already warm) and falls back to `_query_oracle` only if
that path yields zero citations — so the day the chat-stream path itself starts
returning citations, the fallback simply never triggers, no code change needed.

CONTRACTS
---------
- Cron-safe: pure stdlib + httpx (already a topic-selector dep). No backend-rag import.
- Graceful-degrade: ANY failure returns the brief UNCHANGED. Never raises, never blocks.
- Feature flag: `WR2_RESEARCH_STEP_ENABLED` (default OFF). Off → no-op passthrough.
- PII boundary (Law 2): the RAG query is built ONLY from the public topic string.
- Deterministic injection: `_inject_rails_into_facts` (verbatim from #1155) is pure
  string assembly — zero LLM, zero SDK, so no CLAUDE.md §5 conflict.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

logger = logging.getLogger("wr2.grounding")

ENABLED = os.environ.get("WR2_RESEARCH_STEP_ENABLED", "false").lower() == "true"
RAG_TIMEOUT_S = float(os.environ.get("WR2_GROUNDING_TIMEOUT_S", "8"))
ORACLE_TIMEOUT_S = float(os.environ.get("WR2_GROUNDING_ORACLE_TIMEOUT_S", "90"))
BACKEND_URL = os.environ.get("NUZANTARA_BACKEND_URL", "https://nuzantara-rag.fly.dev")
API_KEY = os.environ.get("NUZANTARA_API_KEY", "zantara-secret-2024")

# Replicated VERBATIM from wr2_fact_checker.LAW_PATTERNS (read 2026-06-24) so the
# citations we extract are exactly the ones the fact-checker will later recognize.
LAW_PATTERNS = [
    re.compile(r"\bPP\s+\d+/\d{4}\b", re.IGNORECASE),
    re.compile(r"\bPMK\s+\d+/\d{4}\b", re.IGNORECASE),
    re.compile(r"\bKEP-\d+/PJ/\d{4}\b", re.IGNORECASE),
    re.compile(r"\bPENG-\d+/PJ\.\d+/\d{4}\b", re.IGNORECASE),
    re.compile(r"\bUU\s+\d+/\d{4}\b", re.IGNORECASE),
    re.compile(r"\bPerbup\s+\d+/\d{4}\b", re.IGNORECASE),
    re.compile(r"\bPerda\s+\d+/\d{4}\b", re.IGNORECASE),
    re.compile(r"\bPermen[a-z]*\s+\d+/\d{4}\b", re.IGNORECASE),
    re.compile(r"\bPerpres\s+\d+/\d{4}\b", re.IGNORECASE),
    re.compile(r"\bPerpu\s+\d+/\d{4}\b", re.IGNORECASE),
    re.compile(r"\bPasal\s+\d+[A-Za-z]?\b", re.IGNORECASE),
]


def _find_law_citations(text: str) -> list[str]:
    """All law citations in `text`, deduped, order-preserving (first-seen)."""
    seen: dict[str, None] = {}
    for rx in LAW_PATTERNS:
        for m in rx.finditer(text):
            seen.setdefault(m.group(0), None)
    return list(seen.keys())


def _inject_rails_into_facts(prose_facts: str, nb_brief: dict[str, Any]) -> str:
    """Embed verbatim citations + key numbers + taboo INSIDE the_facts.

    Replicated verbatim from warroom_step2_briefer._inject_rails_into_facts (#1155).
    The drafter reads ONLY enrichment.the_facts; the rich top-level fields are
    invisible to it, so the guardrails MUST land here. Pure string assembly.
    """
    parts = [prose_facts.strip()] if prose_facts and prose_facts.strip() else []

    cites = [c for c in (nb_brief.get("regulatory_citations_verbatim") or []) if str(c).strip()]
    if cites:
        parts.append(
            "Riferimenti normativi (verbatim, citare senza parafrasare): "
            + " · ".join(str(c).strip() for c in cites[:8])
        )

    nums = [str(n).strip() for n in (nb_brief.get("key_numbers") or []) if str(n).strip()]
    if nums:
        parts.append("Numeri chiave (riportare esatti): " + ", ".join(nums[:12]))

    taboos = [str(t).strip() for t in (nb_brief.get("taboo_check") or []) if str(t).strip()]
    if taboos:
        parts.append("NON usare / evitare: " + " ; ".join(taboos[:8]))

    return "\n\n".join(parts)


async def _query_rag(topic: str) -> str:
    """Ask the Fly backend RAG about `topic`; return the answer text. "" on failure."""
    import json

    import httpx

    query = (
        f"What Indonesian regulations, laws, or articles govern: {topic}? "
        "Cite the specific regulation numbers (e.g. PP, PMK, UU, Perpres, Pasal)."
    )
    url = f"{BACKEND_URL.rstrip('/')}/api/v2/bali-zero/chat-stream"
    chunks: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=RAG_TIMEOUT_S) as client:
            async with client.stream(
                "GET", url, params={"query": query}, headers={"X-API-Key": API_KEY},
            ) as resp:
                if resp.status_code != 200:
                    logger.warning("RAG grounding: backend returned %s", resp.status_code)
                    return ""
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[len("data:"):].strip()
                    if not payload or payload == "[DONE]":
                        continue
                    try:
                        obj = json.loads(payload)
                    except json.JSONDecodeError:
                        chunks.append(payload)
                        continue
                    data = obj.get("data", obj)
                    if isinstance(data, str):
                        chunks.append(data)
                    elif isinstance(data, dict):
                        for k in ("text", "content", "answer", "delta"):
                            v = data.get(k)
                            if isinstance(v, str):
                                chunks.append(v)
                        src = data.get("sources")
                        if isinstance(src, list):
                            chunks.append(json.dumps(src, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001 — graceful-degrade on ANY error
        logger.warning("RAG grounding query failed (degrading): %s", exc)
        return ""
    return "\n".join(chunks)


async def _query_oracle(topic: str) -> str:
    """Ask /api/oracle/query about `topic`; return a scan corpus for law citations.

    Unlike `_query_rag` (chat-stream prose), the oracle endpoint's search tool
    fills a `snippet` field (raw chunk text) on every source/citation entry
    (backend/services/rag/agentic/tools.py). The scan corpus is `answer` plus
    every `citations[].snippet` and `sources[].snippet` — "" on any failure.
    """
    import json

    import httpx

    query = (
        f"What Indonesian regulations, laws, or articles govern: {topic}? "
        "Cite the specific regulation numbers (e.g. PP, PMK, UU, Perpres, Pasal)."
    )
    url = f"{BACKEND_URL.rstrip('/')}/api/oracle/query"
    try:
        async with httpx.AsyncClient(timeout=ORACLE_TIMEOUT_S) as client:
            resp = await client.post(
                url,
                json={"query": query},
                headers={"X-API-Key": API_KEY},
            )
            if resp.status_code != 200:
                logger.warning("Oracle grounding: backend returned %s", resp.status_code)
                return ""
            data = resp.json()
    except Exception as exc:  # noqa: BLE001 — graceful-degrade on ANY error
        logger.warning("Oracle grounding query failed (degrading): %s", exc)
        return ""

    if not isinstance(data, dict):
        return ""

    parts: list[str] = []
    answer = data.get("answer")
    if isinstance(answer, str):
        parts.append(answer)

    for key in ("citations", "sources"):
        entries = data.get(key)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, dict):
                snippet = entry.get("snippet")
                if isinstance(snippet, str) and snippet:
                    parts.append(snippet)
    return "\n".join(parts)


async def ground_enrichment(brief_json: dict[str, Any], topic: str) -> dict[str, Any]:
    """Populate brief_json['enrichment'] with regulatory rails for `topic`.

    Returns the brief (mutated copy) — UNCHANGED if disabled, if the RAG yields no
    citations, or on any error. Never raises. Single entry point for wr2_topic_selector.
    """
    if not ENABLED:
        return brief_json

    enrichment = dict(brief_json.get("enrichment") or {})
    existing_facts = str(enrichment.get("the_facts") or "")
    if _find_law_citations(existing_facts):
        return brief_json

    answer = await _query_rag(topic)
    citations = _find_law_citations(answer) if answer else []
    grounding_source = "fly-rag-http"

    if not citations:
        # Chat-stream path yielded nothing extractable — fall back to the
        # oracle endpoint, whose sources/citations carry a `snippet` field.
        try:
            oracle_corpus = await _query_oracle(topic)
        except Exception as exc:  # noqa: BLE001 — graceful-degrade on ANY error
            logger.warning("Oracle grounding fallback failed (degrading): %s", exc)
            oracle_corpus = ""
        if oracle_corpus:
            citations = _find_law_citations(oracle_corpus)
            grounding_source = "fly-oracle-http"

    if not citations:
        logger.info("RAG grounding: no law citations for topic=%r — degrading", topic[:60])
        return brief_json

    nb_brief = {"regulatory_citations_verbatim": citations}
    base_facts = existing_facts or str(brief_json.get("article_summary") or "")[:600]
    enrichment["the_facts"] = _inject_rails_into_facts(base_facts, nb_brief)
    enrichment.setdefault("grounding_source", grounding_source)

    out = dict(brief_json)
    out["enrichment"] = enrichment
    logger.info(
        "RAG grounding: injected %d citation(s) for topic=%r via %s: %s",
        len(citations), topic[:60], grounding_source, ", ".join(citations[:8]),
    )
    return out
