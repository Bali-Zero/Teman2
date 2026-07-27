#!/usr/bin/env python3
"""
Fly Deploy Watcher — event-driven deploy monitoring (Monitor pattern).

# Organo: fly-watcher (cron-agent-python, monitor pattern) → produce:
#         Telegram alert (deploy success/fail) + Redis event `cron:fly-watcher`
#         consumato da: tech-orchestrator, ops team
# Consuma da: fly logs --app nuzantara-rag (streaming subprocess)
#
# Ruolo: sentinella deploy. Sostituisce polling fly status ogni 15s con
#         event-driven stream watching. Zero token durante silenzio.
#         Implementa il Monitor pattern di Claude Agent SDK in Python asyncio.

Pattern: stream fly logs → match deploy patterns → publish Redis event + Telegram.

Replaces the polling pattern in fly-health-check.sh with event-driven:
  BEFORE: cron every 30min, fly status call, parse output
  AFTER: streaming log watch, instant reaction on pattern match

Modes:
  1. watch-deploy: Triggered after fly deploy, watch for completion
  2. watch-health: Continuous log tail, alert on error patterns
  3. check-now: Single health snapshot (backward compat)

Usage:
  python fly_watcher.py                    # check-now mode
  python fly_watcher.py watch-deploy       # watch until deploy done/failed
  bash run.sh fly-watcher                  # check-now via cron wrapper
"""
from __future__ import annotations

import asyncio
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from agent_job import AgentJob, RunResult, WITA, main

# Fly apps to monitor
FLY_APPS = ["nuzantara-rag", "nuzantara-postgres", "nuzantara-qdrant"]

# Deploy success/failure patterns
DEPLOY_SUCCESS_PATTERNS = [
    r"v\d+ deployed successfully",
    r"deployed successfully",
    r"Deployment complete",
    r"Release v\d+ created",
    r"Machine.*started",
]
DEPLOY_FAIL_PATTERNS = [
    r"Error.*deploy",
    r"deployment.*failed",
    r"Machine.*failed",
    r"Error creating release",
    r"health check.*failed",
]

# Health alert patterns (for watch-health mode)
HEALTH_ALERT_PATTERNS = [
    r"OOMKilled",
    r"502 Bad Gateway",
    r"503 Service Unavailable",
    r"panic:",
    r"FATAL",
    r"out of memory",
    r"connection refused",
]

# Lifespan-stuck detector — incident 2026-04-29.
# FastAPI lifespan logs "Middleware registered" but never reaches
# "Application startup complete". Caused by drive_poll_service flooding
# the event loop when ServiceAccountDriveService was missing get_file_metadata.
# Memories 1865 / 1867 / 1870, scar entry in cicatrix-scars.md.
LIFESPAN_PROGRESS_MARKER = r"Middleware registered"
LIFESPAN_COMPLETE_MARKER = r"Application startup complete"
LIFESPAN_STUCK_LOG_LINES = 400

# Max seconds to watch deploy stream
DEPLOY_WATCH_TIMEOUT = 600  # 10 min


class FlyWatcherJob(AgentJob):
    name = "fly-watcher"
    timeout_s = 300
    requires_side_effects = False

    def __init__(self, mode: str = "check-now") -> None:
        super().__init__()
        self.mode = mode
        # fly v0.4.49 regression: does not read access_token from ~/.fly/config.yml
        self._fly_token = self._read_fly_token()

    @staticmethod
    def _read_fly_token() -> str:
        import re
        config = Path.home() / ".fly" / "config.yml"
        try:
            for line in config.read_text().splitlines():
                m = re.match(r'^access_token:\s*"?([^"]+)"?', line)
                if m:
                    return m.group(1).strip()
        except Exception:
            pass
        return ""

    def _fly_cmd(self, *args: str) -> list[str]:
        base = ["/opt/homebrew/bin/fly"]
        if self._fly_token:
            base += ["-t", self._fly_token]
        return base + list(args)

    async def run(self) -> RunResult:
        if self.mode == "watch-deploy":
            return await self._watch_deploy()
        elif self.mode == "watch-health":
            return await self._watch_health()
        else:
            return await self._check_now()

    async def _check_now(self) -> RunResult:
        """Single health snapshot — backward compatible with old cron."""
        self.log_step("check_now_start")

        # Parallel HTTP + fly status checks
        checks = await asyncio.gather(
            self._http_check("https://nuzantara-rag.fly.dev/health"),
            self._http_check("https://balizero.com", timeout=10.0),
            self._shell_check(self._fly_cmd("status", "--app", "nuzantara-rag"), timeout=15.0),
            self._shell_check(["redis-cli", "ping"], timeout=5.0),
            self._lifespan_stuck_check("nuzantara-rag"),
            return_exceptions=True,
        )

        backend = checks[0] if not isinstance(checks[0], Exception) else {"ok": False, "error": str(checks[0])}
        frontend = checks[1] if not isinstance(checks[1], Exception) else {"ok": False, "error": str(checks[1])}
        fly_rag = checks[2] if not isinstance(checks[2], Exception) else {"ok": False, "error": str(checks[2])}
        redis = checks[3] if not isinstance(checks[3], Exception) else {"ok": False, "error": str(checks[3])}
        lifespan = checks[4] if not isinstance(checks[4], Exception) else {"ok": True, "skipped": True, "error": str(checks[4])}

        failures = []
        if not backend.get("ok"):
            failures.append(f"backend: HTTP {backend.get('status', '?')} ({backend.get('error', '?')[:60]})")
        if not frontend.get("ok"):
            failures.append(f"frontend: {frontend.get('error', '?')[:60]}")
        if not fly_rag.get("ok"):
            failures.append("fly_rag: status failed")
        if not redis.get("ok") or "PONG" not in redis.get("stdout", ""):
            failures.append(f"redis: {redis.get('error', redis.get('stdout', '?'))[:40]}")
        if not lifespan.get("ok") and not lifespan.get("skipped"):
            failures.append(f"lifespan_stuck: {lifespan.get('reason', 'unknown')}")

        self.log_step("check_now_done", outputs={"failures": len(failures)})

        if failures:
            # Deduplicate alerts (don't spam if same failure)
            failure_hash = str(hash(tuple(failures)))
            last_hash_key = "bz:fly-watcher:last-failure-hash"
            import subprocess
            last_hash = subprocess.run(
                ["redis-cli", "GET", last_hash_key],
                capture_output=True, text=True, timeout=3
            ).stdout.strip()

            msg = (
                f"🚨 <b>Fly Health Alert</b>\n"
                f"{datetime.now(WITA).strftime('%Y-%m-%d %H:%M WITA')}\n\n"
                + "\n".join(f"• {f}" for f in failures)
            )

            if last_hash != failure_hash:
                ok = await self.send_telegram(msg)
                self.log_step("telegram_alert", outputs={"ok": ok},
                              side_effect="fly_health_alert" if ok else None)
                # Store hash with 30min TTL (avoid duplicate alerts)
                subprocess.run(
                    ["redis-cli", "SET", last_hash_key, failure_hash, "EX", "1800"],
                    capture_output=True, timeout=3
                )
            else:
                self.log_step("alert_deduplicated", outputs={"reason": "same_failure_within_30min"})

        else:
            # Clear dedup hash on success
            import subprocess
            subprocess.run(
                ["redis-cli", "DEL", "bz:fly-watcher:last-failure-hash"],
                capture_output=True, timeout=3
            )

        return RunResult(
            status="ok",
            duration_s=self._elapsed(),
            side_effects=self._side_effects,
            output=f"failures={len(failures)}",
        )

    async def _watch_deploy(self) -> RunResult:
        """Event-driven deploy watcher — streams fly logs until complete/failed.

        This is the Monitor pattern: zero token when deploy is running normally,
        instant reaction when success/failure pattern matches.
        """
        self.log_step("watch_deploy_start", inputs={"app": "nuzantara-rag"})

        matched_pattern = None
        matched_line = None
        start = time.time()

        try:
            proc = await asyncio.create_subprocess_exec(
                *self._fly_cmd("logs", "--app", "nuzantara-rag"),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            async def read_with_timeout():
                nonlocal matched_pattern, matched_line
                async for raw_line in proc.stdout:
                    line = raw_line.decode(errors="ignore").strip()
                    if not line:
                        continue

                    # Check success patterns
                    for pattern in DEPLOY_SUCCESS_PATTERNS:
                        if re.search(pattern, line, re.IGNORECASE):
                            matched_pattern = "success"
                            matched_line = line
                            return

                    # Check failure patterns
                    for pattern in DEPLOY_FAIL_PATTERNS:
                        if re.search(pattern, line, re.IGNORECASE):
                            matched_pattern = "failure"
                            matched_line = line
                            return

                    # Timeout check inline
                    if time.time() - start > DEPLOY_WATCH_TIMEOUT:
                        matched_pattern = "timeout"
                        return

            await asyncio.wait_for(read_with_timeout(), timeout=DEPLOY_WATCH_TIMEOUT + 30)
            proc.kill()

        except asyncio.TimeoutError:
            matched_pattern = "timeout"
        except Exception as e:
            self.log_step("watch_error", outputs={"error": str(e)})

        duration = time.time() - start
        self.log_step("watch_deploy_done", outputs={
            "pattern": matched_pattern, "line": (matched_line or "")[:100], "duration_s": duration
        })

        if matched_pattern == "success":
            msg = (
                f"✅ <b>Deploy completato</b>\n"
                f"{datetime.now(WITA).strftime('%H:%M WITA')} — {duration:.0f}s\n"
                f"<code>{(matched_line or '')[:200]}</code>"
            )
            ok = await self.send_telegram(msg)
            self.log_step("deploy_success_alert", side_effect="deploy_success" if ok else None)
        elif matched_pattern == "failure":
            msg = (
                f"❌ <b>Deploy FALLITO</b>\n"
                f"{datetime.now(WITA).strftime('%H:%M WITA')}\n"
                f"<code>{(matched_line or '')[:200]}</code>"
            )
            ok = await self.send_telegram(msg)
            self.log_step("deploy_fail_alert", side_effect="deploy_failure" if ok else None)
        else:
            # Timeout — run check-now to get current status
            self.log_step("deploy_timeout_fallback")

        return RunResult(
            status="ok" if matched_pattern == "success" else "error" if matched_pattern == "failure" else "ok",
            duration_s=self._elapsed(),
            side_effects=self._side_effects,
            output=matched_pattern or "unknown",
        )

    async def _watch_health(self) -> RunResult:
        """Continuous log anomaly watcher (supervisor pattern).

        Stream fly logs, react instantly on error patterns.
        Typically run via background process, not cron.
        """
        self.log_step("watch_health_start")
        alerts_sent = 0
        max_alerts = 5  # don't spam

        try:
            proc = await asyncio.create_subprocess_exec(
                *self._fly_cmd("logs", "--app", "nuzantara-rag"),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            async def watch():
                nonlocal alerts_sent
                async for raw_line in proc.stdout:
                    line = raw_line.decode(errors="ignore").strip()
                    for pattern in HEALTH_ALERT_PATTERNS:
                        if re.search(pattern, line, re.IGNORECASE) and alerts_sent < max_alerts:
                            msg = (
                                f"🚨 <b>Live Log Alert</b>\n"
                                f"<code>{line[:300]}</code>"
                            )
                            await self.send_telegram(msg)
                            alerts_sent += 1
                            self.log_step("live_alert", outputs={"pattern": pattern, "alerts": alerts_sent})

            await asyncio.wait_for(watch(), timeout=self.timeout_s)
            proc.kill()

        except asyncio.TimeoutError:
            pass
        except Exception as e:
            self.log_step("watch_health_error", outputs={"error": str(e)})

        return RunResult(
            status="ok",
            duration_s=self._elapsed(),
            side_effects=self._side_effects,
            output=f"alerts_sent={alerts_sent}",
        )

    async def _http_check(self, url: str, timeout: float = 15.0) -> dict:
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                start = time.time()
                r = await client.get(url)
                return {
                    "url": url,
                    "status": r.status_code,
                    "latency_ms": int((time.time() - start) * 1000),
                    "ok": 200 <= r.status_code < 300,
                }
            except Exception as e:
                return {"url": url, "ok": False, "error": str(e)}

    async def _shell_check(self, cmd: list[str], timeout: float = 30.0) -> dict:
        try:
            proc = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                ),
                timeout=timeout,
            )
            stdout, stderr = await proc.communicate()
            return {
                "cmd": " ".join(cmd),
                "ok": proc.returncode == 0,
                "stdout": stdout.decode(errors="ignore")[:300],
            }
        except asyncio.TimeoutError:
            return {"cmd": " ".join(cmd), "ok": False, "error": "timeout"}
        except Exception as e:
            return {"cmd": " ".join(cmd), "ok": False, "error": str(e)}

    async def _lifespan_stuck_check(self, app: str) -> dict:
        # Pulls the last LIFESPAN_STUCK_LOG_LINES from `fly logs --no-tail` and
        # decides: if any line contains LIFESPAN_PROGRESS_MARKER but none
        # contains LIFESPAN_COMPLETE_MARKER, FastAPI startup is stuck.
        # Skips silently when fly CLI is unreachable to avoid false positives
        # in degraded environments.
        try:
            proc = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    *self._fly_cmd("logs", "--app", app, "--no-tail", "-n", str(LIFESPAN_STUCK_LOG_LINES)),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=20.0,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=20.0)
        except asyncio.TimeoutError:
            return {"ok": True, "skipped": True, "reason": "fly_logs_timeout"}
        except Exception as e:
            return {"ok": True, "skipped": True, "reason": f"fly_logs_error:{e}"}

        text = stdout.decode(errors="ignore")
        progress_seen = bool(re.search(LIFESPAN_PROGRESS_MARKER, text))
        complete_seen = bool(re.search(LIFESPAN_COMPLETE_MARKER, text))

        if progress_seen and not complete_seen:
            return {
                "ok": False,
                "reason": (
                    f"FastAPI lifespan never reached "
                    f"'{LIFESPAN_COMPLETE_MARKER}' (last {LIFESPAN_STUCK_LOG_LINES} log lines)"
                ),
            }
        return {"ok": True, "progress_seen": progress_seen, "complete_seen": complete_seen}

    def _elapsed(self) -> float:
        return time.time() - self.started_at


def _main_with_mode() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "check-now"
    job = FlyWatcherJob(mode=mode)
    import asyncio as _asyncio
    from agent_job import run_job
    exit_code = _asyncio.run(run_job(job))
    sys.exit(exit_code)


if __name__ == "__main__":
    _main_with_mode()
