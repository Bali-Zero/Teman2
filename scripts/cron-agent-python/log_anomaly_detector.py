#!/usr/bin/env python3
"""
Log Anomaly Detector — runs every 5min for 4.5min window (supervisor pattern).

# Organo: log-anomaly-detector (cron-agent-python, Monitor pattern) → produce:
#         Telegram alert (se anomalia) + Redis event `cron:log-anomaly-detector`
# Consuma da: ~/logs/ (cron logs), fly logs (Fly.io streaming)
#
# Ruolo: sentinella live. Invece di aspettare il prossimo ciclo cron,
#         monitora i log in streaming e reagisce in secondi su anomalie.
#         Implementa il Monitor pattern: zero token durante silenzio,
#         sveglia immediata su pattern match.

Monitors:
  1. Local cron-agent-python logs (FATAL, Traceback, ERROR × 3+)
  2. fly logs streaming (OOMKilled, 502, 503, panic, connection refused)

Deduplication: 30min cooldown per pattern match (Redis TTL).
Max 3 alerts per run to avoid spam.
"""
from __future__ import annotations

import asyncio
import hashlib
import re
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from agent_job import (
    AgentJob, RunResult, WITA, LOG_DIR, main, _REDIS_ERR_RE,
)


# Log patterns to watch (regex → severity)
LOG_PATTERNS: list[tuple[str, str, str]] = [
    # (regex, severity, label)
    (r"FATAL|CRITICAL", "RED", "fatal_error"),
    (r"Traceback \(most recent", "RED", "python_exception"),
    (r"circuit_breaker_opened", "YELLOW", "circuit_breaker"),
    (r"ERROR.*CRM.*unreachable|CRM backend unreachable", "RED", "crm_down"),
    (r"telegram.*failed|telegram_failed", "YELLOW", "telegram_issue"),
    (r"timeout after \d+s", "YELLOW", "job_timeout"),
    # Audit 2026-04-19: core-guardian was failing silently for >24h because
    # the cron wrapper referenced a script that didn't exist. Add patterns
    # to catch that class of breakage.
    (r"script not found|No such file or directory", "RED", "script_not_found"),
    (r"\bexit code [1-9]\d*\b", "RED", "non_zero_exit"),
]

# Extra log dirs to scan beyond LOG_DIR (cron-agent-python).
# cron-agent.sh (bash-tier) writes to ~/logs/cron-agent/, which the
# original implementation ignored — hiding failures like core-guardian.
EXTRA_LOG_DIRS = [Path.home() / "logs" / "cron-agent"]

# Fly.io log patterns
FLY_PATTERNS: list[tuple[str, str, str]] = [
    (r"OOMKilled", "RED", "oom_killed"),
    (r"502 Bad Gateway|503 Service Unavailable", "RED", "gateway_error"),
    (r"panic:", "RED", "go_panic"),
    (r"connection refused", "YELLOW", "connection_refused"),
    (r"Traceback \(most recent", "RED", "python_exception"),
    (r"Error starting app|App crashed", "RED", "app_crash"),
]

# Cooldown: don't re-alert same pattern within 30min
ALERT_COOLDOWN_TTL = 1800
# Fix C (2026-04-17): reduced from 270→60. Cron runs every 5min, and we only
# care about NEW errors — a 1-min streaming window is sufficient. Cuts cron
# runtime from 261s → ~60s, saving 80% execution time without missing events.
WATCH_WINDOW_S = 60
MAX_ALERTS_PER_RUN = 3

# Fix A (2026-04-17): only scan log lines whose timestamp is within this
# window. Prevents re-alerting on old errors already surfaced hours earlier.
LOG_FRESHNESS_S = 600  # 10 min

# Fix B (2026-04-17): per-line-hash dedup TTL. If the same exact log line has
# been alerted before (within this window), skip it.
LINE_DEDUP_TTL = 86400  # 24h
LINE_DEDUP_PREFIX = "bz:log-anomaly:linehash"

# Regex to extract "YYYY-MM-DD HH:MM:SS" or ISO8601 ts from structlog / fly logs.
_TS_PATTERN = re.compile(
    r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})"
)


def _parse_ts(line: str) -> datetime | None:
    """Extract the line's own timestamp, or None if it carries none."""
    m = _TS_PATTERN.search(line)
    if not m:
        return None
    try:
        return datetime.strptime(
            m.group(1).replace("T", " "), "%Y-%m-%d %H:%M:%S",
        )
    except Exception:
        return None


def _fresh_lines(lines: list[str], cutoff: datetime) -> list[str]:
    """Keep lines at/after cutoff, dating each one by POSITION.

    Fix D (2026-07-25): a line with no timestamp of its own inherits the last
    timestamp seen ABOVE it — log files are chronological. The previous
    per-line check defaulted timestamp-less lines to "fresh", and the line the
    RED pattern matches is literally `Traceback (most recent call last):`,
    which never carries a timestamp. So a 2026-07-05 traceback sitting in the
    last-500-line window of a quiet log stayed eternally fresh and re-alerted
    every 5 minutes for 20 days (fact-checker, intel-feed-processor,
    vision-doc-extractor — all three jobs healthy, all three alerts false).

    Lines above the first timestamp in the window are still treated as fresh
    (conservative — nothing dates them either way).
    """
    out: list[str] = []
    current: datetime | None = None
    for line in lines:
        ts = _parse_ts(line)
        if ts is not None:
            current = ts
        if current is None or current >= cutoff:
            out.append(line)
    return out


class LogAnomalyDetectorJob(AgentJob):
    name = "log-anomaly-detector"
    timeout_s = 300
    requires_side_effects = False

    async def run(self) -> RunResult:
        self.log_step("start")
        alerts: list[dict] = []

        # Run both watchers in parallel with shared timeout
        local_task = asyncio.create_task(self._watch_local_logs(alerts))
        fly_task = asyncio.create_task(self._watch_fly_logs(alerts))

        try:
            await asyncio.wait_for(
                asyncio.gather(local_task, fly_task, return_exceptions=True),
                timeout=WATCH_WINDOW_S,
            )
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            self.log_step("watch_error", outputs={"error": str(e)})

        self.log_step("watch_done", outputs={"alerts": len(alerts)})

        if alerts:
            msg = self._compose_alert(alerts)
            # tier=digest: this IS "watcher findings" (tg_notify.py's own tier
            # description) — the gateway's dedup+budget is a second, independent
            # backstop on top of this job's own 30min-cooldown/3-per-run limits
            # (W104, 2026-07-25: those upstream limits fail-opened to 288/day
            # once, so the transport itself should not also be unbounded).
            ok = await self.send_telegram(msg, tier="digest")
            self.log_step("telegram_sent", outputs={"ok": ok},
                          side_effect="anomaly_alert" if ok else None)

        return RunResult(
            status="ok",
            duration_s=self._elapsed(),
            side_effects=self._side_effects,
            output=f"alerts={len(alerts)}",
        )

    async def _watch_local_logs(self, alerts: list) -> None:
        """Watch recent cron-agent-python log files for error patterns.

        Fix A: filter lines by timestamp (only LOG_FRESHNESS_S recent).
        Fix B: dedup by (line-content) hash via Redis (LINE_DEDUP_TTL).
        """
        log_dirs = [LOG_DIR, *EXTRA_LOG_DIRS]
        all_logs: list = []
        for d in log_dirs:
            if d.exists():
                all_logs.extend(d.glob("*.log"))

        if not all_logs:
            return

        log_files = sorted(
            all_logs,
            key=lambda f: f.stat().st_mtime, reverse=True,
        )[:10]

        freshness_cutoff = datetime.now() - timedelta(seconds=LOG_FRESHNESS_S)

        for log_file in log_files:
            try:
                content = log_file.read_text(errors="ignore")
                lines = content.splitlines()[-500:]  # bigger window; we filter by ts next

                # Fix A + D: keep only lines dated (by position) within the
                # freshness window — see _fresh_lines().
                fresh_lines = _fresh_lines(lines, freshness_cutoff)
                if not fresh_lines:
                    continue

                # Collect matches per (pattern, severity, label), dedup by line hash
                matches_by_label: dict = defaultdict(list)
                for line in fresh_lines:
                    for pattern, severity, label in LOG_PATTERNS:
                        if re.search(pattern, line, re.IGNORECASE):
                            matches_by_label[(pattern, severity, label)].append(line)
                            break  # one label per line

                for (pattern, severity, label), matched_lines in matches_by_label.items():
                    if len(alerts) >= MAX_ALERTS_PER_RUN:
                        break
                    # Fix B: line-hash dedup — filter out lines alerted in last 24h
                    unseen = [
                        ln for ln in matched_lines
                        if await self._line_is_unseen(ln)
                    ]
                    if not unseen:
                        continue
                    # Fix: per-label cooldown still applies (30 min global)
                    if not await self._should_alert(f"local:{label}"):
                        continue
                    alerts.append({
                        "source": f"local/{log_file.name}",
                        "severity": severity,
                        "label": label,
                        "count": len(unseen),
                        "sample": unseen[-1][:150],
                    })
            except Exception as e:
                self.logger.debug(
                    "local_watch_error", file=log_file.name, error=str(e),
                )

    async def _watch_fly_logs(self, alerts: list) -> None:
        """Stream fly logs for nuzantara-rag and watch for error patterns.

        Fly logs are streamed — already fresh (no need for Fix A timestamp
        filter). Fix B applies: line-hash dedup prevents alerting same exact
        line across runs.
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "fly", "logs", "--app", "nuzantara-rag",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            async def read_stream():
                async for raw_line in proc.stdout:
                    if len(alerts) >= MAX_ALERTS_PER_RUN:
                        break
                    line = raw_line.decode(errors="ignore").strip()
                    for pattern, severity, label in FLY_PATTERNS:
                        if re.search(pattern, line, re.IGNORECASE):
                            # Fix B: skip if this exact line already alerted
                            if not await self._line_is_unseen(line):
                                break
                            if await self._should_alert(f"fly:{label}"):
                                alerts.append({
                                    "source": "fly:nuzantara-rag",
                                    "severity": severity,
                                    "label": label,
                                    "count": 1,
                                    "sample": line[:200],
                                })
                            break

            # WATCH_WINDOW_S is now 60s (Fix C). Reserve 10s for parallel tasks.
            await asyncio.wait_for(
                read_stream(), timeout=max(WATCH_WINDOW_S - 10, 10),
            )
            proc.kill()

        except asyncio.TimeoutError:
            pass
        except Exception as e:
            self.logger.debug("fly_watch_error", error=str(e))

    def _redis_reply(self, argv: list[str]) -> str | None:
        """Run a redis-cli command; return its reply, or None if Redis refused.

        Fix (2026-07-25): redis-cli exits 0 even when the server rejects the
        command, delivering the error as a reply on stdout. The previous code
        compared that reply to "1", so `NOAUTH Authentication required.` read as
        "key absent" and BOTH dedup layers failed open — silently, for weeks,
        at 288 Telegram alerts a day. A refusal now returns None and is LOGGED,
        so the degradation is visible instead of merely loud.
        """
        try:
            out = subprocess.run(
                argv, capture_output=True, text=True, timeout=3,
            )
        except Exception as e:
            self.logger.warning("redis_dedup_unavailable", detail=str(e)[:120])
            return None
        reply = (out.stdout or "").strip()
        if out.returncode != 0 or _REDIS_ERR_RE.match(reply):
            self.logger.warning(
                "redis_dedup_refused",
                detail=reply[:120] or f"rc={out.returncode}",
            )
            return None
        return reply

    async def _should_alert(self, dedup_key: str) -> bool:
        """Return True if this alert key hasn't been sent recently (30min cooldown)."""
        redis_key = f"bz:log-anomaly:{dedup_key}"
        reply = self._redis_reply(["redis-cli", "EXISTS", redis_key])
        if reply is None:
            # Backend refused/unreachable: alert rather than go blind. Losing a
            # real alarm is worse than repeating one — and the warning above
            # names the degradation, which is what was missing before.
            return True
        if reply == "1":
            return False  # within cooldown
        self._redis_reply(
            ["redis-cli", "SET", redis_key, "1", "EX", str(ALERT_COOLDOWN_TTL)]
        )
        return True

    async def _line_is_unseen(self, line: str) -> bool:
        """Return True if this exact line hasn't been alerted within LINE_DEDUP_TTL.

        Fix B: prevents the same identical error line from triggering repeated
        alerts across runs (the primary cause of the 11-alerts-in-2h spam).
        """
        h = hashlib.sha1(line.encode("utf-8", errors="ignore")).hexdigest()[:16]
        key = f"{LINE_DEDUP_PREFIX}:{h}"
        reply = self._redis_reply(["redis-cli", "EXISTS", key])
        if reply is None:
            return True  # see _redis_reply: refusal is logged, not swallowed
        if reply == "1":
            return False
        self._redis_reply(
            ["redis-cli", "SET", key, "1", "EX", str(LINE_DEDUP_TTL)]
        )
        return True

    def _compose_alert(self, alerts: list[dict]) -> str:
        now = datetime.now(WITA)
        red_alerts = [a for a in alerts if a["severity"] == "RED"]
        icon = "🔴" if red_alerts else "🟡"
        lines = [
            f"{icon} <b>Log Anomaly</b> — {len(alerts)} issues",
            f"{now.strftime('%H:%M WITA')}",
            "",
        ]
        for a in alerts:
            sev_icon = "🔴" if a["severity"] == "RED" else "🟡"
            lines.append(f"{sev_icon} <b>{a['label']}</b> [{a['source']}]")
            if a.get("sample"):
                lines.append(f"  <code>{a['sample'][:150]}</code>")
        return "\n".join(lines)

    def _elapsed(self) -> float:
        return time.time() - self.started_at


if __name__ == "__main__":
    main(LogAnomalyDetectorJob)
