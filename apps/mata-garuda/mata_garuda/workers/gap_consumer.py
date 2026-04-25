"""
Mata Garuda — Gap Consumer Worker.

Reads nexus:gaps stream, dispatches the appropriate agent for each gap type,
and acks on success. On failure does NOT ack — the message is redelivered.

Dispatch table:
- gap.missing_nip       → lhkpn_harvester
- gap.missing_lhkpn     → lhkpn_harvester
- gap.missing_angkatan  → lhkpn_harvester
- gap.stale_official    → regulation_watcher
- gap.orphan_org        → regulation_watcher
- gap.missing_office    → regulation_watcher
- gap.kanim_struktur    → regulation_watcher
- gap.missing_procurement → None (Phase 2: lpse_harvester)

Reference: docs/superpowers/specs/2026-04-14-organism-nervous-system-design.md §5
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable, Optional

from mata_garuda.config import STREAM_NEXUS_GAPS
from mata_garuda.workers.base_worker import stream_ack, stream_read_new
from mata_garuda.workers.gap_legacy import coerce_to_canonical, is_legacy_shape

logger = logging.getLogger("mata_garuda.workers.gap_consumer")


CONSUMER_GROUP = "gap-consumer"
CONSUMER_NAME = "consumer-1"

# Rate limit: max dispatches per run + sleep between them
MAX_DISPATCH_PER_RUN = 5
DISPATCH_SLEEP_S = 2

# Gap type → agent name (None = Phase 2, skipped with ack)
GAP_DISPATCH: dict[str, Optional[str]] = {
    "gap.missing_nip":          "lhkpn_harvester",
    "gap.missing_lhkpn":        "lhkpn_harvester",
    "gap.missing_angkatan":     "lhkpn_harvester",
    "gap.stale_official":       "regulation_watcher",
    "gap.orphan_org":           "regulation_watcher",
    "gap.missing_office":       "regulation_watcher",
    "gap.kanim_struktur":       "regulation_watcher",
    "gap.missing_procurement":  None,  # Phase 2: lpse_harvester
}


def _default_dispatch_agent(agent_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Default dispatcher: invokes the registered agent via Lamarckian loop.

    Returns {"case_resolved": bool, "reason": str}.
    Exceptions propagate so the caller can convert them to status="error".
    """
    import mata_garuda.agents  # noqa: F401 — populate @register_agent registry

    from mata_garuda.registry import get_agent
    from mata_garuda.runtime.knowledge import KnowledgeBase
    from mata_garuda.runtime.lamarckian import run_with_lamarckian_feedback

    agent = get_agent(agent_name)
    if agent is None:
        return {"case_resolved": False, "reason": f"agent {agent_name!r} not registered"}

    # Format payload as a query string the agent can understand
    query = json.dumps(payload, ensure_ascii=False)
    kb = KnowledgeBase()
    try:
        response = run_with_lamarckian_feedback(agent, query, kb=kb)
    finally:
        kb.close()

    # Inspect the response messages for the case_resolved/case_not_resolved tool call.
    # The lamarckian loop ends with one of these tools being called.
    resolved = False
    reason = ""
    if response is not None and hasattr(response, "messages"):
        for msg in response.messages:
            content = msg.get("content", "") if isinstance(msg, dict) else ""
            if "Case resolved" in content or "case_resolved" in content.lower():
                resolved = True
                break
            if "Case not resolved" in content or "case_not_resolved" in content.lower():
                resolved = False
                reason = content[:200]
                break

    return {"case_resolved": resolved, "reason": reason}


def _default_xack(stream: str, group: str, msg_id: str) -> None:
    """Default ACK: delegate to base_worker.stream_ack."""
    stream_ack(stream, group, msg_id)


def process_gap(
    msg_id: str,
    gap_type: str,
    payload: dict[str, Any],
    dispatch_agent: Callable[..., dict[str, Any]] = _default_dispatch_agent,
    xack: Callable[[str, str, str], None] = _default_xack,
) -> dict[str, Any]:
    """Process a single gap message.

    Returns dict with status: "resolved" | "failed" | "skipped" | "unknown" | "error"
    """
    if gap_type not in GAP_DISPATCH:
        logger.warning(
            "Unknown gap type %s (msg_id=%s) — ACKing to skip",
            gap_type, msg_id,
        )
        xack(STREAM_NEXUS_GAPS, CONSUMER_GROUP, msg_id)
        return {"status": "unknown", "agent": None}

    agent_name = GAP_DISPATCH[gap_type]
    if agent_name is None:
        logger.info("Gap %s mapped to None (Phase 2) — ACKing", gap_type)
        xack(STREAM_NEXUS_GAPS, CONSUMER_GROUP, msg_id)
        return {"status": "skipped", "agent": None}

    # Inject _gap_type so the agent knows what it's solving
    enriched = {**payload, "_gap_type": gap_type}

    try:
        result = dispatch_agent(agent_name=agent_name, payload=enriched)
    except Exception as e:
        logger.error(
            "Dispatch %s for %s raised: %s — NOT acking",
            agent_name, gap_type, e,
        )
        return {"status": "error", "agent": agent_name, "reason": str(e)}

    if result.get("case_resolved"):
        xack(STREAM_NEXUS_GAPS, CONSUMER_GROUP, msg_id)
        logger.info("Gap %s resolved by %s (msg %s)", gap_type, agent_name, msg_id)
        return {"status": "resolved", "agent": agent_name}
    else:
        logger.warning(
            "Gap %s NOT resolved by %s (msg %s): %s — NOT acking",
            gap_type, agent_name, msg_id, result.get("reason", ""),
        )
        return {"status": "failed", "agent": agent_name}


def run_gap_consumer(
    max_items: int = MAX_DISPATCH_PER_RUN,
    stream_read: Optional[Callable[[], list[dict[str, Any]]]] = None,
    dispatch_agent: Callable[..., dict[str, Any]] = _default_dispatch_agent,
    xack: Callable[[str, str, str], None] = _default_xack,
) -> dict[str, int]:
    """One cycle: read up to max_items from nexus:gaps and process each.

    Returns stats {read, resolved, failed, skipped, unknown, errors}.
    """
    if stream_read is None:
        stream_read = lambda: stream_read_new(
            STREAM_NEXUS_GAPS, CONSUMER_GROUP, CONSUMER_NAME, count=max_items
        )

    stats: dict[str, int] = {
        "read": 0,
        "resolved": 0,
        "failed": 0,
        "skipped": 0,
        "unknown": 0,
        "errors": 0,
    }

    items = stream_read()
    if not items:
        logger.info("Gap consumer: no new gaps in %s", STREAM_NEXUS_GAPS)
        return stats

    stats["read"] = len(items)

    for i, item in enumerate(items):
        msg_id: str = item["id"]
        data: dict[str, Any] = item["data"]

        coerced = coerce_to_canonical(msg_id, data)
        if coerced is None:
            # Legacy entry with no canonical mapping — drain to avoid PEL bloat.
            xack(STREAM_NEXUS_GAPS, CONSUMER_GROUP, msg_id)
            stats["skipped"] += 1
            continue

        gap_type, payload_seed = coerced

        if is_legacy_shape(data):
            # Legacy shape: payload is the whole dict (already a real dict).
            payload: dict[str, Any] = payload_seed
        else:
            # Canonical envelope shape: payload is a JSON string field.
            try:
                raw_payload = data.get("payload", "{}")
                payload = json.loads(raw_payload)
                if not isinstance(payload, dict):
                    payload = {}
            except (json.JSONDecodeError, TypeError):
                payload = {}

        result = process_gap(
            msg_id=msg_id,
            gap_type=gap_type,
            payload=payload,
            dispatch_agent=dispatch_agent,
            xack=xack,
        )

        # Map status to stats key
        key = {
            "resolved": "resolved",
            "failed": "failed",
            "skipped": "skipped",
            "unknown": "unknown",
            "error": "errors",
        }.get(result["status"], "errors")
        stats[key] += 1

        # Rate limit between dispatches (skip after last item)
        if i < len(items) - 1 and result.get("agent"):
            time.sleep(DISPATCH_SLEEP_S)

    logger.info("Gap consumer cycle: %s", stats)
    return stats


def main() -> None:
    """Entry point for the cron worker (single iteration)."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    run_gap_consumer()


if __name__ == "__main__":
    main()
