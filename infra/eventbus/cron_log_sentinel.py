#!/usr/bin/env python3
"""F-N1 — Cron Log Sentinel.

Tails specific cron log files for completion markers and emits eventbus events.
Zero-touch instrumentation: we never modify the cron Python scripts themselves.

Mappings: see CRON_LOG_RULES below.
"""
from __future__ import annotations
import os
import sys
import json
import logging
import re
import subprocess
import time
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from eventbus import publish, beat, start_background_beater

LOG_PATH = Path.home() / "logs" / "cron-log-sentinel.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
)
log = logging.getLogger("cron-log-sentinel")


def _emit_intel_collected_for_intel_scraper(line: str) -> None:
    """intel.nightly completion → emit intel.collected with marker."""
    try:
        eid = publish("intel.collected", {
            "source": "bali-intel-scraper",
            "citation_or_url": "cron-completion://intel.nightly",
            "raw_payload": {"completion_line": line.strip()[:200]},
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "agent_name": "bali-intel-scraper",
        }, emitted_by="cron-log-sentinel")
        log.info("emitted intel.collected event=%s for intel.nightly", eid)
    except Exception as e:
        log.warning("emit intel.collected failed: %s", e)


def _emit_topic_candidate_for_topic_selector(line: str) -> None:
    """wr2.topic-selector completion → emit topic.candidate.created marker."""
    try:
        m = re.search(r"(?:topic|slug)[:\s=]+(\S+)", line, re.IGNORECASE)
        topic_slug = (m.group(1)[:60] if m else f"cron-marker-{int(time.time())}")
        eid = publish("topic.candidate.created", {
            "topic_slug": topic_slug,
            "domain": "regulatory",  # default; real pipeline will override
            "audience_segment": "founder",
            "score": 0,
            "source_intel_event_id": "cron-log-sentinel-marker",
            "key_facts": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }, emitted_by="cron-log-sentinel")
        log.info("emitted topic.candidate.created event=%s for topic-selector", eid)
    except Exception as e:
        log.warning("emit topic.candidate.created failed: %s", e)


def _emit_content_draft_ready_for_supervisor(line: str) -> None:
    """wr2.supervisor draft completion → emit content.draft.ready marker."""
    try:
        m = re.search(r"(?:topic|slug)[:\s=]+(\S+)", line, re.IGNORECASE)
        topic_slug = (m.group(1)[:60] if m else f"supervisor-marker-{int(time.time())}")
        eid = publish("content.draft.ready", {
            "topic_slug": topic_slug,
            "slides_path": "/tmp/none",
            "brief_path": "/tmp/none",
            "critic_report_path": "/tmp/none",
            "slide_count": 0,
            "hero_count": 0,
            "status": "pass",
            "ready_at": datetime.now(timezone.utc).isoformat(),
        }, emitted_by="cron-log-sentinel")
        log.info("emitted content.draft.ready event=%s for supervisor", eid)
    except Exception as e:
        log.warning("emit content.draft.ready failed: %s", e)


def _emit_publish_completed_for_canva(line: str) -> None:
    """canva-apply completion → emit publish.completed."""
    try:
        m = re.search(r"design_id[:\s=]+(\w+)", line, re.IGNORECASE)
        item_id = (m.group(1)[:60] if m else f"canva-marker-{int(time.time())}")
        eid = publish("publish.completed", {
            "item_id": item_id,
            "published_at": datetime.now(timezone.utc).isoformat(),
            "channel": "instagram",
        }, emitted_by="cron-log-sentinel")
        log.info("emitted publish.completed event=%s for canva-apply", eid)
    except Exception as e:
        log.warning("emit publish.completed failed: %s", e)


# (log_file_path, completion_regex, emit_callback)
CRON_LOG_RULES: list[tuple[Path, str, Callable[[str], None]]] = [
    # intel-scraper: log line "Intel exit=0" indicates success
    (
        Path.home() / ".openclaw/workspace/logs",  # daily rotated dir, glob-handled below
        r"Intel exit=0",
        _emit_intel_collected_for_intel_scraper,
    ),
    # wr2.topic-selector: writes one line per pick to ~/logs/wr2_topic_selector.log
    (
        Path.home() / "logs" / "wr2_topic_selector.log",
        r"(?:Selected|picked|writing draft)",
        _emit_topic_candidate_for_topic_selector,
    ),
    # wr2.supervisor: completion of a carousel cycle
    (
        Path.home() / "logs" / "wr2-supervisor.log",
        r"(?:carousel.*complete|draft.*ready|status[:\s=]pass)",
        _emit_content_draft_ready_for_supervisor,
    ),
    # canva-apply skill log (if present)
    (
        Path.home() / ".claude" / "skills" / "bali-zero-brand" / "logs" / "canva-apply.log",
        r"(?:design_url|carousel.*applied|published)",
        _emit_publish_completed_for_canva,
    ),
]


def _resolve_log_paths(rule: tuple[Path, str, Callable]) -> list[Path]:
    """Expand the path: if it's a directory, glob *.log; else single file."""
    path, _, _ = rule
    if path.is_dir():
        return sorted(path.glob("*.log"))
    return [path]


def _tail_file(path: Path, regex: str, callback: Callable[[str], None]) -> None:
    """tail -F equivalent, calling callback on each matching line.

    Uses subprocess `tail -F -n 0` so we only get NEW lines (avoid replay
    historical hits on every restart)."""
    pattern = re.compile(regex)
    cmd = ["tail", "-F", "-n", "0", str(path)]
    log.info("watching %s for /%s/", path, regex)
    last_emit_at = 0.0
    while True:
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                 bufsize=1, text=True)
            for line in iter(p.stdout.readline, ""):
                if not line:
                    continue
                if pattern.search(line):
                    # Throttle: don't emit more than 1 event per 30s for same log
                    now = time.time()
                    if now - last_emit_at < 30:
                        continue
                    last_emit_at = now
                    try:
                        callback(line)
                    except Exception as e:
                        log.exception("callback failed on %s: %s", path, e)
        except FileNotFoundError:
            log.info("log %s not yet present, retrying in 60s", path)
            time.sleep(60)
        except Exception as e:
            log.warning("tail failed on %s: %s — restart in 30s", path, e)
            time.sleep(30)


def main() -> int:
    log.info("Cron Log Sentinel starting. %d log rules configured.", len(CRON_LOG_RULES))
    start_background_beater("cron-log-sentinel", interval=30)

    threads = []
    for rule in CRON_LOG_RULES:
        for path in _resolve_log_paths(rule):
            t = threading.Thread(
                target=_tail_file,
                args=(path, rule[1], rule[2]),
                daemon=True,
                name=f"tail-{path.name}",
            )
            t.start()
            threads.append(t)
            log.info("started tail thread for %s", path)

    if not threads:
        log.warning("no log files matched any rule — sentinel will idle")

    # Block forever (threads are daemons, will die with process)
    while True:
        time.sleep(60)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log.info("Cron Log Sentinel interrupted")
        sys.exit(0)
