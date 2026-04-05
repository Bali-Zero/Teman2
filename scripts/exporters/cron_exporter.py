#!/usr/bin/env python3
"""
Cron Metrics Exporter for Prometheus.

Reads ~/logs/cron/*.jsonl files and exposes metrics on port 9101.
Each JSONL line has: {"job":"name","status":"ok|failed","exit_code":N,"attempts":N,"duration_s":N,"host":"...","ts":"..."}

Metrics exposed:
  cron_job_last_run_timestamp_seconds{job="..."} - Unix timestamp of last run
  cron_job_last_status{job="...",status="ok|failed"} - 1 if last run had this status
  cron_job_duration_seconds{job="..."} - Duration of last run
  cron_job_success_total{job="..."} - Total successful runs
  cron_job_failure_total{job="..."} - Total failed runs
  cron_job_last_exit_code{job="..."} - Exit code of last run
"""

import glob
import json
import logging
import os
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from collections import defaultdict
from datetime import datetime
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CRON_LOG_DIR = os.environ.get("CRON_LOG_DIR", "/logs/cron")
PORT = int(os.environ.get("EXPORTER_PORT", "9101"))


def parse_timestamp(ts_str: str) -> float:
    """Parse ISO timestamp to Unix seconds."""
    try:
        # Handle Z suffix
        ts_str = ts_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts_str)
        return dt.timestamp()
    except (ValueError, AttributeError):
        return 0.0


def collect_metrics() -> dict[str, dict[str, Any]]:
    """Read all JSONL files and aggregate metrics per job."""
    jobs: dict[str, dict[str, Any]] = {}
    totals: dict[str, dict[str, int]] = defaultdict(lambda: {"success": 0, "failure": 0})

    jsonl_files = glob.glob(os.path.join(CRON_LOG_DIR, "*.jsonl"))

    for filepath in jsonl_files:
        try:
            with open(filepath, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    job_name = entry.get("job", os.path.basename(filepath).replace(".jsonl", ""))
                    status = entry.get("status", "unknown")
                    ts = parse_timestamp(entry.get("ts", ""))
                    duration = float(entry.get("duration_s", 0))
                    exit_code = int(entry.get("exit_code", -1))
                    attempts = int(entry.get("attempts", 1))

                    # Count totals
                    if status == "ok":
                        totals[job_name]["success"] += 1
                    else:
                        totals[job_name]["failure"] += 1

                    # Track latest entry per job
                    if job_name not in jobs or ts > jobs[job_name].get("ts", 0):
                        jobs[job_name] = {
                            "ts": ts,
                            "status": status,
                            "duration": duration,
                            "exit_code": exit_code,
                            "attempts": attempts,
                        }
        except OSError as e:
            logger.warning("Failed to read %s: %s", filepath, e)

    # Merge totals into jobs
    for job_name in set(list(jobs.keys()) + list(totals.keys())):
        if job_name not in jobs:
            jobs[job_name] = {"ts": 0, "status": "unknown", "duration": 0, "exit_code": -1, "attempts": 0}
        jobs[job_name]["success_total"] = totals[job_name]["success"]
        jobs[job_name]["failure_total"] = totals[job_name]["failure"]

    return jobs


def format_prometheus(jobs: dict[str, dict[str, Any]]) -> str:
    """Format metrics in Prometheus text exposition format."""
    lines: list[str] = []

    lines.append("# HELP cron_job_last_run_timestamp_seconds Unix timestamp of last cron job run")
    lines.append("# TYPE cron_job_last_run_timestamp_seconds gauge")
    for job, data in sorted(jobs.items()):
        lines.append(f'cron_job_last_run_timestamp_seconds{{job="{job}"}} {data["ts"]:.1f}')

    lines.append("")
    lines.append("# HELP cron_job_last_status Whether last run was ok (1) or failed (0)")
    lines.append("# TYPE cron_job_last_status gauge")
    for job, data in sorted(jobs.items()):
        val = 1 if data["status"] == "ok" else 0
        lines.append(f'cron_job_last_status{{job="{job}"}} {val}')

    lines.append("")
    lines.append("# HELP cron_job_duration_seconds Duration of last cron job run")
    lines.append("# TYPE cron_job_duration_seconds gauge")
    for job, data in sorted(jobs.items()):
        lines.append(f'cron_job_duration_seconds{{job="{job}"}} {data["duration"]:.1f}')

    lines.append("")
    lines.append("# HELP cron_job_last_exit_code Exit code of last cron job run")
    lines.append("# TYPE cron_job_last_exit_code gauge")
    for job, data in sorted(jobs.items()):
        lines.append(f'cron_job_last_exit_code{{job="{job}"}} {data["exit_code"]}')

    lines.append("")
    lines.append("# HELP cron_job_success_total Total successful cron job runs")
    lines.append("# TYPE cron_job_success_total counter")
    for job, data in sorted(jobs.items()):
        lines.append(f'cron_job_success_total{{job="{job}"}} {data["success_total"]}')

    lines.append("")
    lines.append("# HELP cron_job_failure_total Total failed cron job runs")
    lines.append("# TYPE cron_job_failure_total counter")
    for job, data in sorted(jobs.items()):
        lines.append(f'cron_job_failure_total{{job="{job}"}} {data["failure_total"]}')

    lines.append("")
    lines.append("# HELP cron_job_attempts Number of attempts for last cron job run")
    lines.append("# TYPE cron_job_attempts gauge")
    for job, data in sorted(jobs.items()):
        lines.append(f'cron_job_attempts{{job="{job}"}} {data["attempts"]}')

    lines.append("")
    return "\n".join(lines)


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler that serves Prometheus metrics."""

    def do_GET(self) -> None:
        if self.path == "/metrics" or self.path == "/":
            jobs = collect_metrics()
            body = format_prometheus(jobs)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok\n")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default access log noise."""
        pass


def main() -> None:
    logger.info("Cron Exporter starting on port %d, reading from %s", PORT, CRON_LOG_DIR)
    server = HTTPServer(("0.0.0.0", PORT), MetricsHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down")
        server.shutdown()


if __name__ == "__main__":
    main()
