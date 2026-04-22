"""Yin-Yang Audit — weekly balance check between ingestion (yang) and consumption (yin).

Sacred root (commented only): in the Tao Te Ching each quality exists only in
its polarity — essere/non-essere, alto/basso. Isolating one term breaks the
armonia. Our NB ecosystem has natural polarities (yang=production of claims,
yin=consumption via chat/synth). An NB biased extremely in either direction
is a structural signal.

For each NB the audit computes:

    ratio = (claims_offered_7d + sources_added_7d) / (cited_7d + promoted_7d + 1)

Bands (target after 3 months for 80% of NB):

    ratio ∈ [0.5, 3.0]    HEALTHY    — equilibrium
    ratio > 3.0           YANG_FLOOD — producing more than consumed
    ratio < 0.5           YIN_FAMINE — consuming without producing

Input:
    yajna_metrics.jsonl (weekly, written by yajna_ledger --scan)
    sources_7d_added  = per-NB from {nb}_sources.json delta (if tracked)

Output:
    yin_yang_state.jsonl (append weekly)

Auto-adjust (L2, reversible):
    if YANG_FLOOD for 2 consecutive weeks:
        set synth_cadence[nb] = daily (was weekly)  — accelerate digestion
    if YIN_FAMINE for 2 consecutive weeks:
        propose Zero: add cluster rotation to NB-X (NO auto-creation)

Kill switch:
    YIN_YANG_AUTO_DISABLED=1  — audit still runs, auto-adjust does not fire

Usage:
    python -m apps.evaluator.nlm_deep_research.yin_yang_audit --audit
    python -m apps.evaluator.nlm_deep_research.yin_yang_audit --status
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────────────────

_DIR = Path(__file__).parent
YIN_YANG_STATE_FILE = _DIR / "yin_yang_state.jsonl"
YAJNA_METRICS_FILE = _DIR / "yajna_metrics.jsonl"
# Sources .json tracked for NB-2 and NB-3 only — others have no source registry
# (see NLM_SYSTEM_MAP §2.1 — only NB-2/3 have sources.json populated today).
# yin_yang reads per-NB claims_offered from yajna_metrics; sources tracking is
# a nice-to-have but not required for the ratio computation.

# ── Bands ────────────────────────────────────────────────────────────────────

HEALTHY_BAND = (0.5, 3.0)
YANG_FLOOD_THRESHOLD = 3.0
YIN_FAMINE_THRESHOLD = 0.5

STATUS_HEALTHY = "HEALTHY"
STATUS_YANG_FLOOD = "YANG_FLOOD"
STATUS_YIN_FAMINE = "YIN_FAMINE"
STATUS_UNKNOWN = "UNKNOWN"  # empty data

# ── Kill switch ──────────────────────────────────────────────────────────────


def _auto_adjust_disabled() -> bool:
    return os.environ.get("YIN_YANG_AUTO_DISABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


# ── Load most-recent yajna_metrics ──────────────────────────────────────────


def load_latest_metrics(
    metrics_file: Optional[Path] = None,
) -> Optional[dict[str, Any]]:
    """Return the last (most recent) line from yajna_metrics.jsonl."""
    path = metrics_file or YAJNA_METRICS_FILE
    if not path.exists():
        return None
    latest: Optional[dict[str, Any]] = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                latest = json.loads(line)
            except json.JSONDecodeError:
                continue
    return latest


def _load_prior_audit_entries(
    state_file: Optional[Path] = None, limit: int = 4
) -> list[dict[str, Any]]:
    """Return last N weekly audit entries (for 2-week streak detection)."""
    path = state_file or YIN_YANG_STATE_FILE
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries[-limit:]


# ── Ratio computation ────────────────────────────────────────────────────────


def classify_ratio(ratio: float) -> str:
    if ratio <= 0:
        return STATUS_UNKNOWN
    if ratio < YIN_FAMINE_THRESHOLD:
        return STATUS_YIN_FAMINE
    if ratio > YANG_FLOOD_THRESHOLD:
        return STATUS_YANG_FLOOD
    return STATUS_HEALTHY


def compute_nb_ratios(
    yajna_metrics: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Compute yang/yin ratio per NB from a yajna_metrics snapshot.

    yang = offered (production)
    yin  = cited + promoted (consumption: chat citation OR synth inclusion)

    Returns { nb: { offered, cited, promoted, ratio, status } }.
    """
    per_nb = yajna_metrics.get("per_nb", {}) or {}
    result: dict[str, dict[str, Any]] = {}
    for nb, counts in per_nb.items():
        offered = int(counts.get("offered", 0))
        cited = int(counts.get("cited", 0))
        promoted = int(counts.get("promoted", 0))

        # +1 in denominator avoids divide-by-zero for NBs with no consumer yet
        denom = cited + promoted + 1
        ratio = round(offered / denom, 3)

        result[nb] = {
            "offered": offered,
            "cited": cited,
            "promoted": promoted,
            "ratio": ratio,
            "status": classify_ratio(ratio),
        }
    return result


def detect_streaks(
    audits: list[dict[str, Any]], current_per_nb: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Return per-NB streak info given prior audits + current computation.

    Streak = consecutive weeks with same non-HEALTHY status.
    A streak of 2+ triggers auto-adjust.
    """
    streaks: dict[str, dict[str, Any]] = {}
    for nb, current in current_per_nb.items():
        current_status = current["status"]
        consecutive = 1 if current_status != STATUS_HEALTHY and current_status != STATUS_UNKNOWN else 0

        # Walk back through prior audits
        for prior in reversed(audits):
            prior_nb_entry = (prior.get("per_nb") or {}).get(nb, {})
            prior_status = prior_nb_entry.get("status")
            if prior_status == current_status and current_status not in {STATUS_HEALTHY, STATUS_UNKNOWN}:
                consecutive += 1
            else:
                break

        streaks[nb] = {
            "consecutive_weeks": consecutive,
            "current_status": current_status,
            "adjustable": consecutive >= 2
            and current_status in {STATUS_YANG_FLOOD, STATUS_YIN_FAMINE},
        }
    return streaks


# ── Auto-adjust recommendations ──────────────────────────────────────────────


def build_recommendations(
    streaks: dict[str, dict[str, Any]],
    auto_enabled: bool,
) -> list[dict[str, Any]]:
    """Build recommendation list. When auto_enabled=False, mark all as 'propose'."""
    recs: list[dict[str, Any]] = []
    for nb, info in streaks.items():
        if not info["adjustable"]:
            continue
        status = info["current_status"]
        if status == STATUS_YANG_FLOOD:
            recs.append(
                {
                    "nb": nb,
                    "action": "synth_cadence_to_daily" if auto_enabled else "propose_synth_cadence_to_daily",
                    "reason": f"YANG_FLOOD for {info['consecutive_weeks']} weeks — accelerate digestion",
                    "auto_applied": auto_enabled,
                    "reversible": True,
                }
            )
        elif status == STATUS_YIN_FAMINE:
            # Never auto-apply YIN_FAMINE — adding cluster rotation is irreversible work
            recs.append(
                {
                    "nb": nb,
                    "action": "propose_add_cluster_rotation",
                    "reason": f"YIN_FAMINE for {info['consecutive_weeks']} weeks — NB starved",
                    "auto_applied": False,  # always propose
                    "reversible": False,
                }
            )
    return recs


# ── Run audit ────────────────────────────────────────────────────────────────


def run_audit(
    metrics_file: Optional[Path] = None,
    state_file: Optional[Path] = None,
) -> dict[str, Any]:
    """Execute a weekly audit and append the result to yin_yang_state.jsonl.

    Side effects:
        - Reads yajna_metrics.jsonl (last line).
        - Reads yin_yang_state.jsonl (last 4 entries for streak detection).
        - Appends one JSON line to yin_yang_state.jsonl.

    Returns the audit dict that was appended.
    """
    metrics = load_latest_metrics(metrics_file)
    auto_enabled = not _auto_adjust_disabled()

    if not metrics:
        audit = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "status": "no_metrics",
            "per_nb": {},
            "recommendations": [],
            "auto_adjust_enabled": auto_enabled,
        }
    else:
        per_nb = compute_nb_ratios(metrics)
        prior = _load_prior_audit_entries(state_file)
        streaks = detect_streaks(prior, per_nb)
        recs = build_recommendations(streaks, auto_enabled=auto_enabled)
        audit = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "source_metrics_computed_at": metrics.get("computed_at"),
            "window_days": metrics.get("window_days"),
            "per_nb": per_nb,
            "streaks": streaks,
            "recommendations": recs,
            "auto_adjust_enabled": auto_enabled,
        }

    # Append
    target = state_file or YIN_YANG_STATE_FILE
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "a", encoding="utf-8") as f:
            f.write(json.dumps(audit, ensure_ascii=False) + "\n")
    except OSError as exc:
        logger.warning("yin-yang audit: write failed (%s) — %s", target, exc)

    total_nb = len(audit.get("per_nb", {}))
    recs = audit.get("recommendations", [])
    logger.info(
        "yin-yang audit done: nb_count=%d recommendations=%d auto_enabled=%s",
        total_nb,
        len(recs),
        auto_enabled,
    )
    return audit


# ── CLI ──────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="Yin-Yang Audit — weekly balance check")
    parser.add_argument("--audit", action="store_true", help="run weekly audit + append to state")
    parser.add_argument("--status", action="store_true", help="read latest metrics + print without writing")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if not (args.audit or args.status):
        parser.print_help()
        return 1

    if args.status:
        metrics = load_latest_metrics()
        if not metrics:
            print(json.dumps({"status": "no_metrics"}, indent=2))
            return 0
        per_nb = compute_nb_ratios(metrics)
        print(json.dumps({"per_nb": per_nb, "source_metrics_ts": metrics.get("computed_at")}, indent=2, ensure_ascii=False))
        return 0

    if args.audit:
        audit = run_audit()
        print(
            json.dumps(
                {
                    "audit": "ok",
                    "nb_count": len(audit.get("per_nb", {})),
                    "recommendations": audit.get("recommendations", []),
                    "auto_adjust_enabled": audit.get("auto_adjust_enabled", False),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
