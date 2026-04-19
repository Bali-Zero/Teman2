"""
Mata Garuda — Contradiction Worker.

Reads from garuda:enriched, restricted to high-volatility domains
(immigration_visa, tax_fiscal, investment_licensing), queries the
local KB for recent prior statements, and asks a local LLM whether
the new item contradicts any of them. On detected contradiction the
worker publishes a pointer onto garuda:alerts with a short reason
string so Layer 3 briefing agents can surface the conflict.

Design notes:
- We only pull recent items (last N scored entries per domain) —
  contradictions in month-old items are already downstream.
- LLM returns JSON `{"contradicts": bool, "which": int, "reason": str}`
  where `which` is the 0-based index into the prior list we passed.
- Invalid `which` indices are coerced to -1 + no alert. Bogus LLM
  output defaults to no-contradict (fail-closed) so the alert channel
  stays low-noise.

Layer 2 Kognitif — final pass before Layer 3.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Callable

from mata_garuda.config import STREAM_ALERTS, STREAM_ENRICHED
from mata_garuda.runtime.knowledge import KnowledgeBase
from mata_garuda.tools.ollama_tools import generate_json
from mata_garuda.workers.base_worker import (
    stream_ack,
    stream_publish,
    stream_read_new,
)

logger = logging.getLogger("mata_garuda.workers.contradiction")

CONSUMER_GROUP = "contradiction"
CONSUMER_NAME = "contradiction-1"

CONTRADICTION_MODEL = "gemma4:26b"

WATCHED_DOMAINS = frozenset(
    {"immigration_visa", "tax_fiscal", "investment_licensing"}
)

PRIOR_WINDOW = 10

_CONTRADICTION_PROMPT = """You are a regulation analyst. Decide whether the NEW STATEMENT contradicts any of the PRIOR STATEMENTS.

A contradiction means the NEW statement asserts something incompatible with a prior
(e.g. reversed rule, changed fee, withdrawn policy). Mere topic overlap or updates
with no conflict are NOT contradictions.

Return STRICT JSON (no prose) with keys:
  "contradicts": boolean
  "which":       integer, the 0-based index of the prior that is contradicted (-1 if none)
  "reason":      one short sentence explaining the contradiction (empty if none)

NEW STATEMENT:
TITLE: {title}
CONTENT: {content}

PRIOR STATEMENTS:
{priors}
"""


def _format_priors(priors: list[dict]) -> str:
    if not priors:
        return "(none)"
    lines = []
    for idx, entry in enumerate(priors):
        text = entry.get("content") or entry.get("title") or ""
        lines.append(f"[{idx}] {text[:400]}")
    return "\n\n".join(lines)


def fetch_priors(
    kb: KnowledgeBase,
    domain: str,
    *,
    limit: int = PRIOR_WINDOW,
) -> list[dict]:
    """Return recent KB entries relevant to `domain` for contradiction check.

    Uses FTS search over the scorer-stored scored_items (which include
    TITLE/TOPIC/CONTENT blocks). Domain token is queried verbatim.
    """
    results = kb.search(domain, limit=limit)
    return [r for r in results if isinstance(r, dict)]


def _coerce_verdict(raw: Any, prior_count: int) -> dict:
    """Normalise the LLM JSON envelope, clamp `which` to valid range."""
    default = {"contradicts": False, "which": -1, "reason": ""}
    if not isinstance(raw, dict):
        return default

    contradicts = bool(raw.get("contradicts"))
    reason = str(raw.get("reason", "")).strip()

    try:
        which = int(raw.get("which", -1))
    except (TypeError, ValueError):
        which = -1

    if not contradicts:
        return {"contradicts": False, "which": -1, "reason": reason}

    if which < 0 or which >= prior_count:
        # LLM said contradicts but gave no valid index → treat as no-contradict.
        return {"contradicts": False, "which": -1, "reason": reason}

    if not reason:
        # A positive verdict without a reason is too noisy to alert on.
        return {"contradicts": False, "which": -1, "reason": ""}

    return {"contradicts": True, "which": which, "reason": reason}


def check_contradiction(
    title: str,
    content: str,
    priors: list[dict],
    *,
    llm: Callable[..., dict | None] = generate_json,
) -> dict:
    """LLM-assisted contradiction check. Returns `{"contradicts", "which", "reason"}`."""
    if not priors:
        return {"contradicts": False, "which": -1, "reason": ""}

    prompt = _CONTRADICTION_PROMPT.format(
        title=title[:300],
        content=content[:800],
        priors=_format_priors(priors),
    )

    try:
        raw = llm(CONTRADICTION_MODEL, prompt, num_predict=250)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[contradiction] LLM error: {e}")
        raw = None

    return _coerce_verdict(raw, prior_count=len(priors))


def run_contradiction(
    kb: KnowledgeBase,
    max_items: int = 20,
    *,
    llm: Callable[..., dict | None] = generate_json,
    publish: Callable[..., str] | None = None,
    ack: Callable[..., None] | None = None,
) -> dict:
    """Run one pass of the contradiction worker."""
    publish = publish or (lambda stream, data: stream_publish(stream, data))
    ack = ack or (lambda stream, group, msg_id: stream_ack(stream, group, msg_id))

    stats = {"processed": 0, "skipped_domain": 0, "checked": 0, "alerts": 0}

    items = stream_read_new(
        STREAM_ENRICHED, CONSUMER_GROUP, CONSUMER_NAME, count=max_items
    )
    if not items:
        return stats

    for item in items:
        msg_id = item["id"]
        data = item["data"]
        stats["processed"] += 1

        domain = data.get("domain", "other")
        if domain not in WATCHED_DOMAINS:
            stats["skipped_domain"] += 1
            ack(STREAM_ENRICHED, CONSUMER_GROUP, msg_id)
            continue

        title = data.get("title", "")
        content = data.get("content", "")
        priors = fetch_priors(kb, domain)

        verdict = check_contradiction(title, content, priors, llm=llm)
        stats["checked"] += 1

        if verdict["contradicts"]:
            alert = {
                "kind": "contradiction",
                "title": title,
                "url": data.get("url", ""),
                "source": data.get("source", ""),
                "domain": domain,
                "reason": verdict["reason"],
                "prior_which": str(verdict["which"]),
                "prior_source": priors[verdict["which"]].get("source", ""),
                "detected_at": datetime.now().isoformat(timespec="seconds"),
            }
            publish(STREAM_ALERTS, alert)
            kb.store(
                agent="contradiction_worker",
                entry_type="contradiction_alert",
                content=json.dumps(alert, ensure_ascii=False),
                source=data.get("url", ""),
                confidence=0.7,
            )
            stats["alerts"] += 1

        ack(STREAM_ENRICHED, CONSUMER_GROUP, msg_id)

    logger.info(
        f"[contradiction] Done: {stats['processed']} processed, "
        f"{stats['checked']} checked, {stats['alerts']} alerts"
    )
    return stats
