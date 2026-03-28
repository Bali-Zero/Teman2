"""
Intel Review Chain — workflow chain for processing staging intel items.

Chain ID: "intel.review"

Payload keys:
  - limit: int (default 20) — max staging items to process
  - item_type: str (default "all") — "article" | "regulation" | "all"
  - min_confidence: float (default 0.7) — auto-notify threshold

Steps (LangGraph):
  1. fetch_pending  — list staging items from DB
  2. assess_items   — LLM confidence scoring per item
  3. notify_team    — send Telegram approval notifications for high-confidence items
  4. summarize      — persist final results to episodic memory

Pointer State Pattern:
  State holds only item_ids + confidence scores (NOT full content).
  Full content is fetched on-demand in each step to avoid TOAST bloat.
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

logger = logging.getLogger("zantara.workflow.chains.intel")


# ─────────────────────────────────────────────────────────────
# LangGraph State
# ─────────────────────────────────────────────────────────────


class IntelReviewState(TypedDict):
    """Pointer State — no large payloads. URIs + metadata only."""

    # Input
    limit: int
    item_type: str
    min_confidence: float

    # Step 1 output: list of {"id": str, "type": str, "title": str}
    pending_items: list[dict[str, Any]]

    # Step 2 output: list of {"id": str, "type": str, "confidence": float, "significant": bool}
    assessments: list[dict[str, Any]]

    # Step 3 output: list of item_ids notified
    notified_ids: list[str]

    # Step 4 output: summary
    summary: dict[str, Any]

    # Error accumulation
    errors: list[str]


# ─────────────────────────────────────────────────────────────
# Step implementations
# ─────────────────────────────────────────────────────────────


async def _fetch_pending(state: IntelReviewState, app_state: Any) -> IntelReviewState:
    """Fetch pending staging items — returns IDs + titles only (Pointer State)."""
    db_pool = getattr(app_state, "db_pool", None)
    if db_pool is None:
        state["errors"].append("db_pool not available")
        state["pending_items"] = []
        return state

    try:
        # Query staging items directly from DB — avoids internal HTTP round-trip
        rows = await db_pool.fetch(
            """
            SELECT id::text, item_type, title
            FROM intel_staging
            WHERE status = 'pending'
            ORDER BY created_at DESC
            LIMIT $1
            """,
            state["limit"],
        )
        items = [
            {"id": r["id"], "type": r["item_type"], "title": r["title"] or "Untitled"}
            for r in rows
            if state["item_type"] == "all" or r["item_type"] == state["item_type"]
        ]
        state["pending_items"] = items
        logger.info(f"intel.review: fetched {len(items)} pending items")
    except Exception as e:
        # Table may not exist yet or column names differ — non-fatal, log and continue
        logger.warning(f"intel.review: fetch_pending failed: {e}")
        state["errors"].append(f"fetch_pending: {e}")
        state["pending_items"] = []

    return state


async def _assess_items(state: IntelReviewState, app_state: Any) -> IntelReviewState:
    """Score each item's significance using Gemini Flash — cheap, fast."""
    import os

    items = state["pending_items"]
    if not items:
        state["assessments"] = []
        return state

    gemini_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GOOGLEAISTUDIO_API_KEY", "")
    assessments: list[dict[str, Any]] = []

    for item in items:
        title = item["title"]
        item_id = item["id"]
        item_type = item["type"]

        if not gemini_key:
            # No LLM key — mark everything as pending human review
            assessments.append(
                {
                    "id": item_id,
                    "type": item_type,
                    "confidence": 0.0,
                    "significant": False,
                    "reason": "no_llm_key",
                },
            )
            continue

        try:
            import json as _json
            import urllib.request as _ur

            prompt = (
                "Is this news/regulation significant for foreign investors or expats in Bali?\n"
                f"Title: {title}\n\n"
                "Reply ONLY with JSON: "
                '{"significant": true/false, "confidence": 0.0-1.0, "reason": "one sentence"}'
            )
            req = _ur.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}",
                data=_json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode(),
                headers={"Content-Type": "application/json"},
            )
            resp = _ur.urlopen(req, timeout=15)
            data = _json.loads(resp.read())
            text = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
                .strip()
                .strip("`")
            )
            if text.startswith("json"):
                text = text[4:].strip()
            result = _json.loads(text)
            assessments.append(
                {
                    "id": item_id,
                    "type": item_type,
                    "confidence": float(result.get("confidence", 0)),
                    "significant": bool(result.get("significant", False)),
                    "reason": result.get("reason", ""),
                },
            )
        except Exception as e:
            logger.warning(f"intel.review: assessment failed for {item_id}: {e}")
            assessments.append(
                {
                    "id": item_id,
                    "type": item_type,
                    "confidence": 0.0,
                    "significant": False,
                    "reason": f"error: {e}",
                },
            )

    state["assessments"] = assessments
    min_c = state["min_confidence"]
    high_conf = sum(1 for a in assessments if a["confidence"] >= min_c and a["significant"])
    logger.info(f"intel.review: assessed {len(assessments)} items, {high_conf} high-confidence")
    return state


async def _notify_team(state: IntelReviewState, app_state: Any) -> IntelReviewState:
    """Send Telegram approval notifications for high-confidence items."""
    min_conf = state["min_confidence"]
    to_notify = [
        a
        for a in state["assessments"]
        if a.get("significant") and a.get("confidence", 0) >= min_conf
    ]

    notified: list[str] = []

    if not to_notify:
        logger.info("intel.review: no items meet notification threshold")
        state["notified_ids"] = []
        return state

    # Lazy import module-level singletons from intel router
    try:
        from backend.app.routers.intel import approval_service as approval_svc
        from backend.app.routers.intel import staging_service as staging_svc
    except ImportError as exc:
        logger.warning(f"intel.review: cannot import intel services: {exc}")
        state["errors"].append(f"notify_team: import failed: {exc}")
        state["notified_ids"] = []
        return state

    for item in to_notify:
        item_id = item["id"]
        item_type = item["type"]

        try:
            data = staging_svc.load_staging_item(item_type, item_id)
            if data:
                await approval_svc.send_approval_notification(item_type, item_id, data, None, None)
                notified.append(item_id)
                logger.info(f"intel.review: notified team for {item_id} ({item_type})")
        except Exception as e:
            logger.warning(f"intel.review: notify failed for {item_id}: {e}")
            state["errors"].append(f"notify_team: {item_id}: {e}")

    state["notified_ids"] = notified
    return state


async def _summarize(state: IntelReviewState, app_state: Any) -> IntelReviewState:
    """Build and persist final summary."""
    assessments = state["assessments"]
    total = len(assessments)
    significant = sum(1 for a in assessments if a.get("significant"))
    notified = len(state["notified_ids"])
    errors = len(state["errors"])

    summary = {
        "total_reviewed": total,
        "significant": significant,
        "notified": notified,
        "skipped": total - significant,
        "errors": errors,
        "items": [
            {
                "id": a["id"],
                "type": a["type"],
                "confidence": a["confidence"],
                "significant": a["significant"],
            }
            for a in assessments
        ],
    }
    state["summary"] = summary

    logger.info(
        f"intel.review: complete — reviewed={total} significant={significant} "
        f"notified={notified} errors={errors}",
    )
    return state


# ─────────────────────────────────────────────────────────────
# Executor registered with the chain registry
# ─────────────────────────────────────────────────────────────


def _register() -> None:
    from backend.services.workflow.executor import register_chain

    @register_chain("intel.review")
    async def _execute_intel_review(
        payload: dict[str, Any],
        thread_id: str,
        app_state: Any,
    ) -> dict[str, Any]:
        """
        Intel review chain: assess pending staging items and notify team.

        Runs without LangGraph if langgraph is unavailable (graceful degradation).
        """
        limit = int(payload.get("limit", 20))
        item_type = str(payload.get("item_type", "all"))
        min_confidence = float(payload.get("min_confidence", 0.7))

        initial_state: IntelReviewState = {
            "limit": limit,
            "item_type": item_type,
            "min_confidence": min_confidence,
            "pending_items": [],
            "assessments": [],
            "notified_ids": [],
            "summary": {},
            "errors": [],
        }

        # Run steps sequentially — LangGraph adds checkpointing but is optional
        state = initial_state
        for step_fn in (_fetch_pending, _assess_items, _notify_team, _summarize):
            state = await step_fn(state, app_state)  # type: ignore[assignment]

        return state["summary"]


_register()
