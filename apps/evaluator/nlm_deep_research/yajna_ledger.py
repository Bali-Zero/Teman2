"""Yajña Ledger — append-only audit of claim lifecycle across NLM ecosystem.

Sacred root (not invoked in code, only here): "yajña" in the Vedic tradition
is the ritual of offering. An offering that produces no smoke is mute; smoke
that produces no rain is sterile. The ledger asks: when we offer a claim to
an NB, does it return (cited in chat, corroborated by synth, superseded by
later evidence)? Or does it evaporate?

For 3 months after deployment this module ONLY collects data — no automatic
threshold tuning, no confidence re-calibration. Zero reviews the metrics
after the collection window and decides whether calibration is warranted.

Events emitted:

    CLAIM_OFFERED              claim extracted + appended to jsonl registry
    CLAIM_CITED_IN_CHAT        backend-rag orchestrator cited source_id
    CLAIM_PROMOTED_TO_SYNTH    synthesis_roller included in weekly/monthly
    CLAIM_CORROBORATED         nlm_verifier confirmed externally
    CLAIM_ORPHAN_30D           weekly scan: offered 30d ago, never cited

File: apps/evaluator/nlm_deep_research/yajna_ledger.jsonl (git-ignored, append-only)

Kill switch: env YAJNA_LEDGER_DISABLED=1 → all append_event calls are no-op.
Kill switch applies before the file touch; no partial state possible.

Usage:

    from apps.evaluator.nlm_deep_research.yajna_ledger import (
        append_event,
        EVENT_CLAIM_OFFERED,
    )

    append_event(
        event_type=EVENT_CLAIM_OFFERED,
        nb="nb4",
        claim_id="NB4-abc123",
        metadata={"category": "FEE_CHANGE", "confidence": 0.78},
    )

Weekly scan (separate cron):

    python -m apps.evaluator.nlm_deep_research.yajna_ledger --scan

"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────────────────

_DIR = Path(__file__).parent
LEDGER_FILE = _DIR / "yajna_ledger.jsonl"
METRICS_FILE = _DIR / "yajna_metrics.jsonl"

# ── Event types ───────────────────────────────────────────────────────────────

EVENT_CLAIM_OFFERED = "CLAIM_OFFERED"
EVENT_CLAIM_CITED_IN_CHAT = "CLAIM_CITED_IN_CHAT"
EVENT_CLAIM_PROMOTED_TO_SYNTH = "CLAIM_PROMOTED_TO_SYNTH"
EVENT_CLAIM_CORROBORATED = "CLAIM_CORROBORATED"
EVENT_CLAIM_ORPHAN_30D = "CLAIM_ORPHAN_30D"

VALID_EVENTS = frozenset(
    {
        EVENT_CLAIM_OFFERED,
        EVENT_CLAIM_CITED_IN_CHAT,
        EVENT_CLAIM_PROMOTED_TO_SYNTH,
        EVENT_CLAIM_CORROBORATED,
        EVENT_CLAIM_ORPHAN_30D,
    }
)

ORPHAN_WINDOW_DAYS = 30

# ── Kill switch ──────────────────────────────────────────────────────────────


def _disabled() -> bool:
    """Return True if ledger is killed via env var.

    Read at call time so tests and canaries can flip it between calls.
    """
    return os.environ.get("YAJNA_LEDGER_DISABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


# ── Core append ──────────────────────────────────────────────────────────────


def append_event(
    event_type: str,
    nb: str,
    claim_id: str,
    metadata: Optional[dict[str, Any]] = None,
    ledger_file: Optional[Path] = None,
) -> bool:
    """Append a single lifecycle event to the ledger.

    Returns True when the line was written, False when the ledger is disabled
    or the event was rejected. Never raises — caller guarantees no blocking.

    Args:
        event_type: one of VALID_EVENTS
        nb: notebook key (nb2, nb3, ...) — free-form string, not validated here
        claim_id: the claim identifier this event pertains to
        metadata: optional extra fields (category, confidence, consumer, ...)
        ledger_file: override target path (tests only)
    """
    if _disabled():
        return False

    if event_type not in VALID_EVENTS:
        logger.warning("yajna: rejected unknown event_type=%r", event_type)
        return False

    if not nb or not claim_id:
        logger.warning("yajna: rejected event with empty nb=%r claim_id=%r", nb, claim_id)
        return False

    target = ledger_file or LEDGER_FILE
    row: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event_type,
        "nb": nb,
        "claim_id": claim_id,
    }
    if metadata:
        row["meta"] = metadata

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return True
    except OSError as exc:
        # Non-fatal: the ledger is an audit, never block the pipeline.
        logger.warning("yajna: append failed (%s) — %s", target, exc)
        return False


def append_events_batch(
    event_type: str,
    nb: str,
    entries: Iterable[tuple[str, Optional[dict[str, Any]]]],
    ledger_file: Optional[Path] = None,
) -> int:
    """Append many entries with the same event_type in one file open.

    entries = iterable of (claim_id, metadata). Returns count written.
    """
    if _disabled():
        return 0
    if event_type not in VALID_EVENTS:
        logger.warning("yajna batch: rejected event_type=%r", event_type)
        return 0

    target = ledger_file or LEDGER_FILE
    count = 0
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "a", encoding="utf-8") as f:
            for claim_id, meta in entries:
                if not claim_id:
                    continue
                row: dict[str, Any] = {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "event": event_type,
                    "nb": nb,
                    "claim_id": claim_id,
                }
                if meta:
                    row["meta"] = meta
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                count += 1
    except OSError as exc:
        logger.warning("yajna batch: append failed (%s) — %s", target, exc)
    return count


# ── Scan (weekly cron) ───────────────────────────────────────────────────────


def _load_ledger(ledger_file: Optional[Path] = None) -> list[dict[str, Any]]:
    target = ledger_file or LEDGER_FILE
    if not target.exists():
        return []
    rows: list[dict[str, Any]] = []
    with open(target, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                logger.warning("yajna: skipping malformed ledger line")
    return rows


def compute_metrics(
    rows: list[dict[str, Any]],
    now: Optional[datetime] = None,
    window_days: int = 30,
) -> dict[str, Any]:
    """Aggregate ledger into cite_rate + orphans per NB + per category.

    Pure function — easy to test. now default = datetime.now(UTC) at call time.
    """
    now = now or datetime.now(timezone.utc)
    horizon = now - timedelta(days=window_days)

    # Group claim_id -> set of events in window
    claim_events: dict[str, set[str]] = defaultdict(set)
    claim_nb: dict[str, str] = {}
    claim_meta: dict[str, dict[str, Any]] = {}
    claim_offered_ts: dict[str, datetime] = {}

    for row in rows:
        ts_raw = row.get("ts", "")
        try:
            ts = datetime.fromisoformat(ts_raw)
        except (ValueError, TypeError):
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts < horizon:
            continue

        cid = row.get("claim_id", "")
        if not cid:
            continue
        event = row.get("event", "")
        claim_events[cid].add(event)
        claim_nb.setdefault(cid, row.get("nb", ""))
        if event == EVENT_CLAIM_OFFERED:
            claim_meta.setdefault(cid, row.get("meta", {}) or {})
            claim_offered_ts[cid] = ts

    # Global counts
    offered = sum(1 for ev in claim_events.values() if EVENT_CLAIM_OFFERED in ev)
    cited = sum(1 for ev in claim_events.values() if EVENT_CLAIM_CITED_IN_CHAT in ev)
    promoted = sum(1 for ev in claim_events.values() if EVENT_CLAIM_PROMOTED_TO_SYNTH in ev)
    corroborated = sum(1 for ev in claim_events.values() if EVENT_CLAIM_CORROBORATED in ev)

    # Per-NB breakdown
    per_nb: dict[str, dict[str, int]] = defaultdict(lambda: {"offered": 0, "cited": 0, "promoted": 0})
    for cid, events in claim_events.items():
        nb = claim_nb.get(cid, "unknown")
        if EVENT_CLAIM_OFFERED in events:
            per_nb[nb]["offered"] += 1
        if EVENT_CLAIM_CITED_IN_CHAT in events:
            per_nb[nb]["cited"] += 1
        if EVENT_CLAIM_PROMOTED_TO_SYNTH in events:
            per_nb[nb]["promoted"] += 1

    # Per-category breakdown (only available for OFFERED since metadata is captured there)
    per_category: dict[str, dict[str, int]] = defaultdict(lambda: {"offered": 0, "cited": 0})
    for cid, events in claim_events.items():
        cat = claim_meta.get(cid, {}).get("category", "UNKNOWN")
        if EVENT_CLAIM_OFFERED in events:
            per_category[cat]["offered"] += 1
        if EVENT_CLAIM_CITED_IN_CHAT in events:
            per_category[cat]["cited"] += 1

    # Orphans: offered > 30d ago, never cited/promoted
    orphans: list[dict[str, Any]] = []
    for cid, events in claim_events.items():
        if EVENT_CLAIM_OFFERED not in events:
            continue
        if EVENT_CLAIM_CITED_IN_CHAT in events or EVENT_CLAIM_PROMOTED_TO_SYNTH in events:
            continue
        ts = claim_offered_ts.get(cid)
        if ts is None:
            continue
        age = (now - ts).days
        if age >= ORPHAN_WINDOW_DAYS:
            orphans.append(
                {
                    "claim_id": cid,
                    "nb": claim_nb.get(cid, ""),
                    "category": claim_meta.get(cid, {}).get("category", "UNKNOWN"),
                    "age_days": age,
                }
            )

    cite_rate = round(cited / offered, 3) if offered else 0.0
    promote_rate = round(promoted / offered, 3) if offered else 0.0

    return {
        "window_days": window_days,
        "computed_at": now.isoformat(),
        "totals": {
            "offered": offered,
            "cited": cited,
            "promoted": promoted,
            "corroborated": corroborated,
        },
        "rates": {
            "cite_rate": cite_rate,
            "promote_rate": promote_rate,
        },
        "per_nb": dict(per_nb),
        "per_category": dict(per_category),
        "orphans": orphans,
        "orphan_count": len(orphans),
    }


def run_scan(
    ledger_file: Optional[Path] = None,
    metrics_file: Optional[Path] = None,
    emit_orphan_events: bool = True,
    window_days: int = 30,
) -> dict[str, Any]:
    """Weekly scan: compute metrics, append to metrics jsonl, emit orphan events."""
    ledger_path = ledger_file or LEDGER_FILE
    metrics_path = metrics_file or METRICS_FILE

    rows = _load_ledger(ledger_path)
    metrics = compute_metrics(rows, window_days=window_days)

    # Write metrics as append (weekly snapshot)
    try:
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with open(metrics_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(metrics, ensure_ascii=False) + "\n")
    except OSError as exc:
        logger.warning("yajna scan: metrics write failed (%s) — %s", metrics_path, exc)

    # Emit ORPHAN events so next scan doesn't re-emit (idempotence).
    # We only emit if the ORPHAN event for this claim_id isn't already present.
    if emit_orphan_events and metrics["orphan_count"] > 0:
        seen_orphan_ids: set[str] = {
            r.get("claim_id", "")
            for r in rows
            if r.get("event") == EVENT_CLAIM_ORPHAN_30D
        }
        new_orphans = [o for o in metrics["orphans"] if o["claim_id"] not in seen_orphan_ids]
        if new_orphans:
            append_events_batch(
                event_type=EVENT_CLAIM_ORPHAN_30D,
                nb="",  # orphan event may span NBs; per-entry nb in metadata
                entries=[
                    (o["claim_id"], {"nb": o["nb"], "category": o["category"], "age_days": o["age_days"]})
                    for o in new_orphans
                ],
                ledger_file=ledger_path,
            )

    logger.info(
        "yajna scan done: offered=%d cited=%d cite_rate=%.3f orphans=%d",
        metrics["totals"]["offered"],
        metrics["totals"]["cited"],
        metrics["rates"]["cite_rate"],
        metrics["orphan_count"],
    )
    return metrics


# ── CLI ──────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="Yajña Ledger — audit of claim lifecycle")
    parser.add_argument("--scan", action="store_true", help="run weekly scan + append to metrics file")
    parser.add_argument("--status", action="store_true", help="print current totals without writing metrics")
    parser.add_argument("--window-days", type=int, default=30, help="observation window (default 30)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if not (args.scan or args.status):
        parser.print_help()
        return 1

    if args.status:
        rows = _load_ledger()
        metrics = compute_metrics(rows, window_days=args.window_days)
        print(json.dumps(metrics, indent=2, ensure_ascii=False))
        return 0

    if args.scan:
        metrics = run_scan(window_days=args.window_days)
        print(json.dumps({"scan": "ok", "summary": metrics["totals"], "rates": metrics["rates"]}, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
