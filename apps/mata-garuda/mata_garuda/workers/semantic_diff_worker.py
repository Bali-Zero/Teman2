"""
Mata Garuda — Semantic Diff Worker.

Monitors regulation pages (primarily .go.id) on the STREAM_OSINT
channel. For every item whose `source_type` marks it as a regulation
snapshot, the worker:

  1. Looks up the most recent stored snapshot for the same URL in the
     local KB (entry_type = "regulation_snapshot:<url_hash>").
  2. If a prior snapshot exists and text-level diff is non-trivial
     (not just whitespace / boilerplate), asks a local LLM whether
     the meaning changed — not just wording.
  3. Publishes to STREAM_ALERTS when the change is semantically
     significant.
  4. Always stores the new snapshot so the next poll has a baseline.

Unlike `contradiction_worker`, this one is specifically about the SAME
page changing over time — catches slow-burn regulatory drift that
never produces an explicit new "news" item.

Layer 2 Kognitif — final pass, OSINT-side.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any, Callable

from mata_garuda.config import STREAM_ALERTS, STREAM_OSINT
from mata_garuda.runtime.knowledge import KnowledgeBase
from mata_garuda.tools.ollama_tools import generate_json
from mata_garuda.workers.base_worker import (
    content_hash,
    stream_ack,
    stream_publish,
    stream_read_new,
)

logger = logging.getLogger("mata_garuda.workers.semantic_diff")

CONSUMER_GROUP = "semantic-diff"
CONSUMER_NAME = "semantic-diff-1"

SEMANTIC_DIFF_MODEL = "gemma4:26b"

REGULATION_SOURCE_TYPES = frozenset({"regulation", "gov_regulation", "go_id"})

# If text similarity ratio is above this, skip the LLM — cosmetic only.
SIMILARITY_SKIP_THRESHOLD = 0.97

SNAPSHOT_TYPE_PREFIX = "regulation_snapshot"

_SEMANTIC_DIFF_PROMPT = """You are a regulation reviewer. Compare OLD and NEW versions of the same page.

Decide whether the meaning of the regulation has substantively changed
(new obligation, changed threshold, different scope, removed exemption, etc.)
as opposed to cosmetic edits (typo fix, reformatting, punctuation).

Return STRICT JSON (no prose) with keys:
  "significant":    boolean
  "change_summary": one short sentence naming WHAT changed in meaning (empty if not significant)

OLD:
{old}

NEW:
{new}
"""


def snapshot_type_for(url: str) -> str:
    """Stable KB `entry_type` per-URL so we can fetch prior snapshots."""
    return f"{SNAPSHOT_TYPE_PREFIX}:{content_hash(url)}"


def fetch_prior_snapshot(kb: KnowledgeBase, url: str) -> dict | None:
    """Most recent KB snapshot for this URL, or None."""
    entries = kb.get_by_type(snapshot_type_for(url), limit=1)
    if not entries:
        return None
    return entries[0]


def store_snapshot(kb: KnowledgeBase, url: str, title: str, content: str) -> int:
    """Persist a regulation snapshot under the URL-scoped type."""
    payload = json.dumps(
        {
            "title": title,
            "content": content,
            "captured_at": datetime.now().isoformat(timespec="seconds"),
        },
        ensure_ascii=False,
    )
    return kb.store(
        agent="semantic_diff_worker",
        entry_type=snapshot_type_for(url),
        content=payload,
        source=url,
        confidence=1.0,
    )


def _parse_snapshot(entry: dict) -> dict:
    """Inverse of `store_snapshot` — returns {title, content, captured_at}."""
    raw = entry.get("content", "{}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"title": "", "content": raw, "captured_at": ""}


def text_similarity(a: str, b: str) -> float:
    """Character-level ratio in [0, 1]. Cheap pre-filter before LLM."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    # SequenceMatcher is O(n*m); cap input to keep the worker fast.
    a_ = a[:4000]
    b_ = b[:4000]
    return SequenceMatcher(None, a_, b_).ratio()


def _coerce_diff_verdict(raw: Any) -> dict:
    default = {"significant": False, "change_summary": ""}
    if not isinstance(raw, dict):
        return default

    significant = bool(raw.get("significant"))
    summary = str(raw.get("change_summary", "")).strip()

    if significant and not summary:
        # Significant verdict without a summary is too noisy.
        return default

    return {"significant": significant, "change_summary": summary}


def diff_meaning(
    old: dict,
    new_title: str,
    new_content: str,
    *,
    llm: Callable[..., dict | None] = generate_json,
) -> dict:
    """LLM-assisted semantic diff of two snapshots."""
    old_text = f"TITLE: {old.get('title', '')}\nCONTENT: {old.get('content', '')}"
    new_text = f"TITLE: {new_title}\nCONTENT: {new_content}"

    prompt = _SEMANTIC_DIFF_PROMPT.format(old=old_text[:2000], new=new_text[:2000])

    try:
        raw = llm(SEMANTIC_DIFF_MODEL, prompt, num_predict=200)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[semantic_diff] LLM error: {e}")
        raw = None

    return _coerce_diff_verdict(raw)


def run_semantic_diff(
    kb: KnowledgeBase,
    max_items: int = 20,
    *,
    llm: Callable[..., dict | None] = generate_json,
    publish: Callable[..., str] | None = None,
    ack: Callable[..., None] | None = None,
) -> dict:
    """Run one pass of the semantic-diff worker against STREAM_OSINT."""
    publish = publish or (lambda stream, data: stream_publish(stream, data))
    ack = ack or (lambda stream, group, msg_id: stream_ack(stream, group, msg_id))

    stats = {
        "processed": 0,
        "first_seen": 0,
        "unchanged": 0,
        "cosmetic": 0,
        "semantic_alerts": 0,
        "skipped_non_regulation": 0,
        "skipped_no_url": 0,
    }

    items = stream_read_new(
        STREAM_OSINT, CONSUMER_GROUP, CONSUMER_NAME, count=max_items
    )
    if not items:
        return stats

    for item in items:
        msg_id = item["id"]
        data = item["data"]
        stats["processed"] += 1

        source_type = data.get("source_type", "")
        if source_type not in REGULATION_SOURCE_TYPES:
            stats["skipped_non_regulation"] += 1
            ack(STREAM_OSINT, CONSUMER_GROUP, msg_id)
            continue

        url = data.get("url", "").strip()
        if not url:
            stats["skipped_no_url"] += 1
            ack(STREAM_OSINT, CONSUMER_GROUP, msg_id)
            continue

        title = data.get("title", "")
        content = data.get("content", "")

        prior_entry = fetch_prior_snapshot(kb, url)

        if prior_entry is None:
            store_snapshot(kb, url, title, content)
            stats["first_seen"] += 1
            ack(STREAM_OSINT, CONSUMER_GROUP, msg_id)
            continue

        old_snapshot = _parse_snapshot(prior_entry)
        similarity = text_similarity(old_snapshot.get("content", ""), content)

        if similarity >= SIMILARITY_SKIP_THRESHOLD:
            stats["unchanged"] += 1
            ack(STREAM_OSINT, CONSUMER_GROUP, msg_id)
            continue

        verdict = diff_meaning(old_snapshot, title, content, llm=llm)

        if verdict["significant"]:
            alert = {
                "kind": "regulation_change",
                "title": title,
                "url": url,
                "source": data.get("source", ""),
                "change_summary": verdict["change_summary"],
                "similarity_ratio": f"{similarity:.3f}",
                "detected_at": datetime.now().isoformat(timespec="seconds"),
            }
            publish(STREAM_ALERTS, alert)
            stats["semantic_alerts"] += 1
        else:
            stats["cosmetic"] += 1

        # Record the NEW snapshot either way so the next diff compares
        # against this version, not the now-stale prior.
        store_snapshot(kb, url, title, content)

        ack(STREAM_OSINT, CONSUMER_GROUP, msg_id)

    logger.info(
        f"[semantic_diff] Done: {stats['processed']} processed, "
        f"{stats['first_seen']} first_seen, {stats['unchanged']} unchanged, "
        f"{stats['cosmetic']} cosmetic, {stats['semantic_alerts']} alerts"
    )
    return stats
