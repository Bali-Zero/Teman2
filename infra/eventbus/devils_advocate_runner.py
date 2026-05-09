#!/usr/bin/env python3
"""Devils Advocate runner — invokes DA sub-agent via cascade + publishes redteam.completed.

Usage (called by meta-dispatcher spawn_devils_advocate_if_high_stakes action):
  python3 devils_advocate_runner.py \\
      --target /path/to/draft.md \\
      --topic-slug pph21-q3 \\
      --domain tax \\
      --trace-id 01KR... \\
      --source-event-id 01KR...

The runner:
1. Spawns claude-cascade.sh with --agent devils-advocate (DA agent reads spec + writes JSON to /tmp)
2. Sniffs the JSON report at /tmp/devils-advocate-<slug>-report.json
3. Publishes redteam.completed event on the bus with verdict + counts + report_path
4. Exits 0 even if DA verdict is BLOCK — the event is the gate, not the runner exit code

Designed to be fire-and-forget by meta-dispatcher (subprocess.Popen).
"""
from __future__ import annotations
import argparse
import json
import logging
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from eventbus import publish

LOG_PATH = Path.home() / "logs" / "devils-advocate-runner.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
)
log = logging.getLogger("da-runner")

CASCADE = "/Users/nuzantara/scripts/claude-cascade.sh"
DA_TIMEOUT_SEC = 600  # 10 min cap for DeepSeek round-trip


def _slug_from_target(target: str) -> str:
    """Extract slug from target path. e.g. '2026-05-09-pph21-q3-deadlines-livetest.md' → 'pph21-q3-deadlines-livetest'."""
    name = Path(target).stem
    # Strip ISO date prefix if present
    m = re.match(r"^\d{4}-\d{2}-\d{2}-(.+)$", name)
    return m.group(1) if m else name


def _expected_report_path(slug: str) -> Path:
    return Path(f"/tmp/devils-advocate-{slug}-report.json")


def run_da(target: str, topic_slug: str, domain: str, trace_id: str | None) -> dict:
    """Spawn DA via cascade. Returns parsed JSON report dict, or raises RuntimeError on failure."""
    slug = _slug_from_target(target)
    report_path = _expected_report_path(slug)
    # Capture pre-existing report mtime to detect new write
    pre_mtime = report_path.stat().st_mtime if report_path.exists() else 0

    prompt = json.dumps({
        "target": target,
        "context": (
            f"meta-dispatcher pre-publish gate, domain={domain}, "
            f"topic_slug={topic_slug}, trace_id={trace_id or 'none'}"
        ),
    })
    cmd = [
        CASCADE,
        prompt,
        "--agent", "devils-advocate",
        "--model", "claude-sonnet-4-6",
    ]
    log.info("invoking cascade for DA: target=%s slug=%s domain=%s", target, slug, domain)

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=DA_TIMEOUT_SEC,
        )
        log.info("cascade exit=%d stderr-tail=%r", result.returncode, result.stderr[-300:])
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"DA cascade timed out after {DA_TIMEOUT_SEC}s")

    # Wait briefly for filesystem flush
    time.sleep(2)

    if not report_path.exists():
        raise RuntimeError(f"DA report not written: {report_path}")
    new_mtime = report_path.stat().st_mtime
    if new_mtime <= pre_mtime:
        log.warning("DA report mtime unchanged (%s) — DA may have failed silently", report_path)

    try:
        report = json.loads(report_path.read_text())
    except Exception as e:
        raise RuntimeError(f"DA report not valid JSON: {e}")

    return report


def emit_redteam_event(report: dict, target: str, topic_slug: str, domain: str,
                       trace_id: str | None) -> str:
    """Publish redteam.completed event from a parsed DA report. Returns event_id."""
    verdict = (report.get("verdict") or "PASS").upper()
    if verdict not in ("PASS", "NEEDS_FIX", "BLOCK"):
        log.warning("verdict %r not in valid enum — coercing to NEEDS_FIX", verdict)
        verdict = "NEEDS_FIX"

    counts = report.get("counts") or {}
    findings = report.get("findings") or []
    # Counts may be missing — derive from findings
    if not counts:
        counts = {
            "critical": sum(1 for f in findings if f.get("severity") == "critical"),
            "high": sum(1 for f in findings if f.get("severity") == "high"),
            "medium": sum(1 for f in findings if f.get("severity") == "medium"),
            "low": sum(1 for f in findings if f.get("severity") == "low"),
        }

    slug = _slug_from_target(target)
    payload = {
        "source": "devils-advocate",
        "target_path": target,
        "topic_slug": topic_slug,
        "domain": domain,
        "status": verdict,
        "critical_count": int(counts.get("critical", 0)),
        "high_count": int(counts.get("high", 0)),
        "medium_count": int(counts.get("medium", 0)),
        "low_count": int(counts.get("low", 0)),
        "report_path": str(_expected_report_path(slug)),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    event_id = publish("redteam.completed", payload, emitted_by="devils-advocate-runner",
                       trace_id=trace_id)
    log.info("published redteam.completed event_id=%s verdict=%s counts=%s",
             event_id, verdict, counts)
    return event_id


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True, help="Absolute path to target file")
    ap.add_argument("--topic-slug", required=True)
    ap.add_argument("--domain", required=True, choices=["tax", "regulatory", "property", "visa", "other"])
    ap.add_argument("--trace-id", default=None, help="Inherited trace_id from invoking event")
    ap.add_argument("--source-event-id", default=None)
    args = ap.parse_args()

    if not Path(args.target).exists():
        log.error("target file does not exist: %s", args.target)
        # Still emit a synthetic redteam.completed with verdict=BLOCK so the chain reacts
        emit_redteam_event(
            report={"verdict": "BLOCK", "counts": {"critical": 1, "high": 0, "medium": 0, "low": 0}},
            target=args.target, topic_slug=args.topic_slug, domain=args.domain,
            trace_id=args.trace_id,
        )
        return 1

    try:
        report = run_da(args.target, args.topic_slug, args.domain, args.trace_id)
    except Exception as e:
        log.exception("DA run failed: %s", e)
        # Emit BLOCK so meta-dispatcher knows something is wrong
        emit_redteam_event(
            report={"verdict": "BLOCK", "counts": {"critical": 1, "high": 0, "medium": 0, "low": 0}},
            target=args.target, topic_slug=args.topic_slug, domain=args.domain,
            trace_id=args.trace_id,
        )
        return 1

    emit_redteam_event(report, args.target, args.topic_slug, args.domain, args.trace_id)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log.info("DA runner interrupted")
        sys.exit(130)
