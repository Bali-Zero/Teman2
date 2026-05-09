"""Event schema validation + ULID generation."""
from __future__ import annotations
import os
import time
import secrets
from typing import Any

# Crockford base32 alphabet (no I, L, O, U)
_B32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def generate_event_id() -> str:
    """Generate ULID-style id: 48-bit timestamp + 80-bit random, base32 encoded.
    Lexicographic sortability + URL-safe + 26 char fixed."""
    ts_ms = int(time.time() * 1000)
    rand = secrets.token_bytes(10)
    val = (ts_ms << 80) | int.from_bytes(rand, "big")
    out = []
    for _ in range(26):
        out.append(_B32[val & 0x1F])
        val >>= 5
    return "".join(reversed(out))


# Event type → required payload keys (envelope keys NOT listed here)
EVENT_TYPES: dict[str, set[str]] = {
    "intel.collected": {"source", "citation_or_url", "raw_payload", "collected_at", "agent_name"},
    "intel.deduped": {"original_event_id", "content_hash", "dedup_key", "normalized_payload", "deduped_at"},
    "regulatory.delta.detected": {"citation", "regulation_type", "service_lines", "summary", "urgency", "source", "detected_at"},
    "topic.candidate.created": {"topic_slug", "domain", "audience_segment", "score", "source_intel_event_id", "key_facts", "created_at"},
    "content.draft.ready": {"topic_slug", "slides_path", "brief_path", "critic_report_path", "slide_count", "hero_count", "status", "ready_at"},
    "redteam.completed": {"source", "target_path", "topic_slug", "domain", "status", "critical_count", "high_count", "medium_count", "low_count", "report_path", "completed_at"},
    "human.review.completed": {"item_id", "action", "completed_at"},
    "publish.completed": {"item_id", "published_at", "channel"},
    "engagement.measured": {"item_id", "instagram_post_url", "likes", "comments", "scraped_at", "hours_since_publish"},
    "learning.updated": {"source", "lessons", "updated_at"},
}

# Stream retention (seconds, used by Redis MAXLEN approximation)
RETENTION: dict[str, int] = {
    "intel.collected": 30 * 86400,
    "intel.deduped": 30 * 86400,
    "regulatory.delta.detected": 90 * 86400,
    "topic.candidate.created": 30 * 86400,
    "content.draft.ready": 30 * 86400,
    "redteam.completed": 90 * 86400,
    "human.review.completed": 365 * 86400,
    "publish.completed": 365 * 86400,
    "engagement.measured": 365 * 86400,
    "learning.updated": 365 * 86400,
}

# Approximate MAXLEN per stream (heuristic: 1 event/minute peak)
MAXLEN: dict[str, int] = {
    "intel.collected": 50000,
    "intel.deduped": 50000,
    "regulatory.delta.detected": 5000,
    "topic.candidate.created": 10000,
    "content.draft.ready": 5000,
    "redteam.completed": 5000,
    "human.review.completed": 100000,
    "publish.completed": 100000,
    "engagement.measured": 200000,
    "learning.updated": 10000,
}

VALID_URGENCY = {"low", "medium", "high", "critical"}
VALID_ACTION = {"published", "rejected", "edited"}
VALID_CHANNEL = {"instagram", "telegram", "email", "web"}
VALID_STATUS_DRAFT = {"pass", "needs_human_edit"}
VALID_REDTEAM_STATUS = {"PASS", "NEEDS_FIX", "BLOCK"}
VALID_LEARNING_SOURCE = {"reflexion", "voyager", "ig-metrics-analyst", "competitor-monitor", "devils-advocate"}


def validate_payload(event_type: str, payload: dict[str, Any]) -> None:
    """Raise ValueError if event_type unknown or required keys missing or enum violated."""
    if event_type not in EVENT_TYPES:
        raise ValueError(f"unknown event_type '{event_type}'. Known: {sorted(EVENT_TYPES)}")
    required = EVENT_TYPES[event_type]
    missing = required - set(payload.keys())
    if missing:
        raise ValueError(f"event_type '{event_type}' missing keys: {sorted(missing)}")

    # Enum guards (cheap validation, catches typos at publish time)
    if event_type == "regulatory.delta.detected":
        u = payload.get("urgency")
        if u not in VALID_URGENCY:
            raise ValueError(f"urgency must be in {VALID_URGENCY}, got '{u}'")
    if event_type == "human.review.completed":
        a = payload.get("action")
        if a not in VALID_ACTION:
            raise ValueError(f"action must be in {VALID_ACTION}, got '{a}'")
    if event_type == "publish.completed":
        c = payload.get("channel")
        if c not in VALID_CHANNEL:
            raise ValueError(f"channel must be in {VALID_CHANNEL}, got '{c}'")
    if event_type == "content.draft.ready":
        s = payload.get("status")
        if s not in VALID_STATUS_DRAFT:
            raise ValueError(f"status must be in {VALID_STATUS_DRAFT}, got '{s}'")
    if event_type == "redteam.completed":
        s = payload.get("status")
        if s not in VALID_REDTEAM_STATUS:
            raise ValueError(f"redteam status must be in {VALID_REDTEAM_STATUS}, got '{s}'")
    if event_type == "learning.updated":
        s = payload.get("source")
        if s not in VALID_LEARNING_SOURCE:
            raise ValueError(f"source must be in {VALID_LEARNING_SOURCE}, got '{s}'")
