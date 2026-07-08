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

LogRule = tuple[Path, str, Callable[[str], None]]
STARTED_AT = time.time()
POLL_INTERVAL_SECONDS = int(os.getenv("CRON_LOG_SENTINEL_POLL_SECONDS", "10"))
MAX_DYNAMIC_LOGS = int(os.getenv("CRON_LOG_SENTINEL_MAX_DYNAMIC_LOGS", "3"))


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
CRON_LOG_RULES: list[LogRule] = [
    # intel-scraper: log line "Intel exit=0" indicates success
    (
        Path.home() / ".openclaw/workspace/logs/intel_nightly_*.log",
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


def _has_glob(path: Path) -> bool:
    """Return True when a path name includes shell glob metacharacters."""
    return any(char in path.name for char in "*?[")


def _resolve_log_paths(rule: LogRule) -> list[Path]:
    """Resolve concrete log files for one rule, newest first with a sane cap."""
    path, _, _ = rule
    if path.is_dir():
        paths = list(path.glob("*.log"))
    elif _has_glob(path):
        paths = list(path.parent.glob(path.name))
    else:
        return [path]

    files = [candidate for candidate in paths if candidate.is_file()]
    files.sort(key=lambda candidate: candidate.stat().st_mtime, reverse=True)
    return sorted(files[:MAX_DYNAMIC_LOGS])


def _initial_position(path: Path) -> int:
    """Avoid replaying old logs while still catching files created after start."""
    stat = path.stat()
    if stat.st_mtime >= STARTED_AT - 5:
        return 0
    return stat.st_size


def _read_new_lines(path: Path, position: int) -> tuple[int, list[str]]:
    """Read appended log lines and return the updated file offset."""
    try:
        stat = path.stat()
    except FileNotFoundError:
        return 0, []

    if stat.st_size < position:
        position = 0

    if stat.st_size == position:
        return position, []

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        handle.seek(position)
        lines = handle.readlines()
        return handle.tell(), lines


def _watch_rule(rule: LogRule) -> None:
    """Poll one log rule without spawning a child tail process per file."""
    path_spec, regex, callback = rule
    pattern = re.compile(regex)
    positions: dict[Path, int] = {}
    last_emit_at: dict[Path, float] = {}

    log.info("watching %s for /%s/", path_spec, regex)
    while True:
        paths = _resolve_log_paths(rule)
        active_paths = set(paths)
        for stale_path in set(positions) - active_paths:
            positions.pop(stale_path, None)
            last_emit_at.pop(stale_path, None)

        if not paths and not path_spec.exists():
            log.debug("log %s not yet present", path_spec)

        for path in paths:
            try:
                if path not in positions:
                    positions[path] = _initial_position(path)
                    log.info("started log watcher for %s", path)

                new_position, lines = _read_new_lines(path, positions[path])
                positions[path] = new_position
            except OSError as e:
                log.warning("log read failed on %s: %s", path, e)
                continue

            for line in lines:
                if not pattern.search(line):
                    continue

                now = time.time()
                if now - last_emit_at.get(path, 0.0) < 30:
                    continue

                last_emit_at[path] = now
                try:
                    callback(line)
                except Exception as e:
                    log.exception("callback failed on %s: %s", path, e)

        time.sleep(POLL_INTERVAL_SECONDS)


def _tail_file(path: Path, regex: str, callback: Callable[[str], None]) -> None:
    """Compatibility wrapper for older imports; prefer _watch_rule."""
    _watch_rule((path, regex, callback))


def main() -> int:
    log.info("Cron Log Sentinel starting. %d log rules configured.", len(CRON_LOG_RULES))
    start_background_beater("cron-log-sentinel", interval=30)

    threads: list[threading.Thread] = []
    for rule in CRON_LOG_RULES:
        t = threading.Thread(
            target=_watch_rule,
            args=(rule,),
            daemon=True,
            name=f"watch-{rule[0].name}",
        )
        t.start()
        threads.append(t)
        log.info("started watcher thread for %s", rule[0])

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
