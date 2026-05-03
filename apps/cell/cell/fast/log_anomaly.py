"""Log Anomaly detector reflex — 50ms latency budget.
Regex-based pattern detection. No LLM."""
from __future__ import annotations

import glob
import re
from dataclasses import dataclass, field
from pathlib import Path

ERROR_PATTERN = re.compile(r"(Error|Exception|Failure|Panic|Timeout|OOM)", re.IGNORECASE)
FATAL_KEYWORDS = ("SIGKILL", "FATAL", "SEGV", "SIGSEGV", "SIGTERM")

# Paths scanned by `scan_watched_paths()`. Each entry is an already-expanded
# pathlib.Path — may be a concrete file or a glob (contains `*`). Audit
# 2026-04-19 (blind-spot #2): cron-agent logs were never scanned because the
# detector only ever consumed pre-loaded lines. The glob is resolved at scan
# time, so new cron-agent buckets are picked up automatically.
WATCHED_LOG_PATHS: list[Path] = [
    (Path.home() / "logs" / "cron-agent" / "*.log"),
    (Path.home() / "logs" / "cron-agent-*" / "*.log"),
]


@dataclass
class LogAnomaly:
    anomaly: bool = False
    reason: str = ""
    critical_keywords: list[str] = field(default_factory=list)


@dataclass
class WatchedPathsReport:
    """Result of scanning `WATCHED_LOG_PATHS`.

    `severity` is one of `ok` / `low` / `medium` / `high`:
      - `ok`     — files scanned, no anomaly
      - `low`    — no files matched the glob (backward-compat: not a crash)
      - `medium` — at least one anomaly found
      - `high`   — critical keyword (SIGKILL/FATAL/…) found
    """

    anomaly: bool = False
    reason: str = ""
    severity: str = "ok"
    critical_keywords: list[str] = field(default_factory=list)
    sources: list[Path] = field(default_factory=list)
    files_scanned: int = 0


_EXIT_CODE_RE = re.compile(r"exit code\s+[1-9]\d*", re.IGNORECASE)


def detect_anomaly(lines: list[str], recent_window: int = 10) -> LogAnomaly:
    """Detect anomalies in log lines."""
    result = LogAnomaly()
    for line in lines:
        for keyword in FATAL_KEYWORDS:
            if keyword in line:
                result.anomaly = True
                if keyword not in result.critical_keywords:
                    result.critical_keywords.append(keyword)
    if result.critical_keywords:
        result.reason = f"Critical keywords found: {', '.join(result.critical_keywords)}"
        return result
    recent = lines[-recent_window:] if len(lines) >= recent_window else lines
    error_count = sum(1 for line in recent if ERROR_PATTERN.search(line))
    if error_count > 2:
        result.anomaly = True
        result.reason = f"Error spike: {error_count} errors in last {recent_window} lines"
    return result


def _resolve(path: Path) -> list[Path]:
    """Expand a glob path to concrete files. Non-glob paths pass through if
    they exist (empty otherwise)."""
    s = str(path)
    if "*" in s or "?" in s or "[" in s:
        return [Path(p) for p in glob.glob(s)]
    return [path] if path.exists() else []


def scan_watched_paths(
    paths: list[Path] | None = None,
    recent_window: int = 10,
) -> WatchedPathsReport:
    """Scan each path in `WATCHED_LOG_PATHS` for anomalies.

    Missing paths do NOT raise — they degrade to severity='low' so the caller
    (system_doctor) can surface the gap without crashing the whole health
    pipeline. Audit 2026-04-19 (blind-spot #2).
    """
    targets = paths if paths is not None else WATCHED_LOG_PATHS
    report = WatchedPathsReport()

    all_files: list[Path] = []
    for p in targets:
        all_files.extend(_resolve(p))

    if not all_files:
        report.severity = "low"
        report.reason = (
            f"No files matched WATCHED_LOG_PATHS "
            f"(targets={[str(t) for t in targets]}) — missing cron-agent dir?"
        )
        return report

    for f in all_files:
        try:
            lines = f.read_text(errors="replace").splitlines()
        except OSError as e:
            report.severity = "low"
            report.reason = f"Cannot read {f}: {type(e).__name__}"
            report.sources.append(f)
            continue

        report.files_scanned += 1

        per_file = detect_anomaly(lines, recent_window=recent_window)

        # `exit code [1-9]` is the canonical cron-agent failure marker that
        # the plain regex in detect_anomaly() might miss when it is the only
        # signal in the file — pick it up explicitly.
        has_exit_failure = any(_EXIT_CODE_RE.search(l) for l in lines)

        if per_file.critical_keywords:
            report.anomaly = True
            report.severity = "high"
            for kw in per_file.critical_keywords:
                if kw not in report.critical_keywords:
                    report.critical_keywords.append(kw)
            if f not in report.sources:
                report.sources.append(f)
            report.reason = (
                f"Critical keywords {report.critical_keywords} found in "
                f"{len(report.sources)} file(s)"
            )
        elif per_file.anomaly or has_exit_failure:
            report.anomaly = True
            if report.severity != "high":
                report.severity = "medium"
            if f not in report.sources:
                report.sources.append(f)
            if not report.reason or "critical" not in report.reason.lower():
                marker = (
                    per_file.reason
                    if per_file.reason
                    else "non-zero exit code detected"
                )
                report.reason = (
                    f"{marker} (first offender: {f.name}, "
                    f"{len(report.sources)} file(s) total)"
                )

    if not report.anomaly and report.severity == "ok":
        report.reason = (
            f"Scanned {report.files_scanned} file(s) across "
            f"{len(targets)} watched path(s) — clean"
        )

    return report
