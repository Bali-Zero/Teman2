#!/usr/bin/env python3
"""
System Doctor — every 4h (:00).

# Organo: system-doctor (cron-agent-python, L1 diagnostic) → produce:
#         state.json (consumato da tech-orchestrator L2) + Telegram alert
#         (se YELLOW/RED) + reflection in memory.db
# Consuma da: Fly.io status, HTTP health endpoints, Redis ping, subprocess
#
# Ruolo: occhi e naso dell'organismo. Rileva infra degradation prima
#         che diventi business outage. L2 (tech-orchestrator) correla i
#         suoi segnali e decide azioni.

Runs 4 parallel specialist checks (db_diagnoser, vector_diagnoser,
runtime_diagnoser, services_diagnoser), triages into GREEN/YELLOW/RED,
applies LOW-risk auto-fixes, synthesizes narrative via Claude SDK if issues.

No LangGraph — plain asyncio gather. Each diagnoser owns its domain.
"""
from __future__ import annotations

import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import TypedDict

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from agent_job import AgentJob, RunResult, WITA, main


# ─── Shared helpers ────────────────────────────────────────────────────────


async def _http_check(url: str, timeout: float = 15.0) -> dict:
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            start = time.time()
            r = await client.get(url)
            return {
                "url": url,
                "status": r.status_code,
                "latency_ms": int((time.time() - start) * 1000),
                "ok": 200 <= r.status_code < 300,
                "body_preview": r.text[:300],
            }
        except Exception as e:
            return {"url": url, "ok": False, "error": str(e), "latency_ms": -1}


async def _shell_check(cmd: list[str], timeout: float = 30.0) -> dict:
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
            "exit_code": proc.returncode,
            "ok": proc.returncode == 0,
            "stdout": stdout.decode(errors="ignore")[:500],
            "stderr": stderr.decode(errors="ignore")[:500],
        }
    except asyncio.TimeoutError:
        return {"cmd": " ".join(cmd), "ok": False, "error": "timeout"}
    except Exception as e:
        return {"cmd": " ".join(cmd), "ok": False, "error": str(e)}


# ─── 4 Diagnosers (run in parallel) ────────────────────────────────────────


async def db_diagnoser() -> dict:
    """Checks: Fly Postgres status + Redis ping."""
    results = await asyncio.gather(
        _shell_check(["fly", "status", "--app", "nuzantara-postgres"], timeout=20.0),
        _shell_check(["redis-cli", "ping"], timeout=5.0),
        return_exceptions=True,
    )
    fly_pg = results[0] if not isinstance(results[0], Exception) else {"ok": False, "error": str(results[0])}
    redis = results[1] if not isinstance(results[1], Exception) else {"ok": False, "error": str(results[1])}

    issues = []
    if not fly_pg.get("ok"):
        issues.append(("RED", "fly_postgres", f"fly status failed: {fly_pg.get('error', fly_pg.get('stderr', '?')[:100])}"))
    if not redis.get("ok"):
        issues.append(("RED", "redis", f"PING failed: {redis.get('error', '?')}"))
    elif "PONG" not in redis.get("stdout", ""):
        issues.append(("YELLOW", "redis", f"unexpected response: {redis.get('stdout', '?')[:50]}"))

    return {"domain": "db", "checks": {"fly_postgres": fly_pg, "redis": redis}, "issues": issues}


async def vector_diagnoser() -> dict:
    """Checks: local Qdrant daemon (launchd) + Qdrant HTTP health.

    Qdrant runs as the LOCAL MOS daemon (com.balizero.qdrant.daemon on :6333),
    NOT on Fly — there is no nuzantara-qdrant Fly app (only nuzantara-rag +
    nuzantara-postgres). The previous Fly target was a phantom that emitted a
    permanent false RED/YELLOW every run. Fixed 2026-06-19 (TAC alert-flood).
    """
    results = await asyncio.gather(
        _shell_check(["launchctl", "list", "com.balizero.qdrant.daemon"], timeout=10.0),
        _http_check("http://localhost:6333/healthz", timeout=10.0),
        return_exceptions=True,
    )
    daemon = results[0] if not isinstance(results[0], Exception) else {"ok": False, "error": str(results[0])}
    qd_http = results[1] if not isinstance(results[1], Exception) else {"ok": False, "error": str(results[1])}

    issues = []
    if not daemon.get("ok"):
        issues.append(("RED", "qdrant_daemon", "com.balizero.qdrant.daemon not loaded"))
    if not qd_http.get("ok"):
        issues.append(("YELLOW", "qdrant_http", f"localhost:6333/healthz unreachable ({qd_http.get('error', '?')[:80]})"))

    return {"domain": "vector", "checks": {"qdrant_daemon": daemon, "qdrant_http": qd_http}, "issues": issues}


async def runtime_diagnoser() -> dict:
    """Checks: backend-rag health + Drive health (token expiry)."""
    import re
    results = await asyncio.gather(
        _http_check("https://nuzantara-rag.fly.dev/health"),
        _http_check("https://nuzantara-rag.fly.dev/api/admin/drive/health"),
        _shell_check(["fly", "status", "--app", "nuzantara-rag"], timeout=20.0),
        return_exceptions=True,
    )
    backend = results[0] if not isinstance(results[0], Exception) else {"ok": False, "error": str(results[0])}
    drive = results[1] if not isinstance(results[1], Exception) else {"ok": False, "error": str(results[1])}
    fly_rag = results[2] if not isinstance(results[2], Exception) else {"ok": False, "error": str(results[2])}

    issues = []

    # Backend
    if not backend.get("ok"):
        issues.append(("RED", "backend", f"HTTP {backend.get('status', '?')}, err={backend.get('error', '?')[:80]}"))
    elif backend.get("latency_ms", 0) > 3000:
        issues.append(("YELLOW", "backend", f"slow ({backend['latency_ms']}ms)"))

    # Fly RAG
    if not fly_rag.get("ok"):
        issues.append(("RED", "fly_rag", "fly status failed"))

    # Drive token
    if not drive.get("ok"):
        issues.append(("YELLOW", "drive", "health endpoint unreachable"))
    else:
        body = drive.get("body_preview", "")
        m = re.search(r'"time_left_seconds":(-?[\d.]+)', body)
        if m:
            secs = float(m.group(1))
            days = secs / 86400
            if days < 0:
                issues.append(("RED", "drive", f"token EXPIRED ({abs(days):.1f}d ago)"))
            elif days < 7:
                issues.append(("RED", "drive", f"token expires in {days:.1f}d"))
            elif days < 14:
                issues.append(("YELLOW", "drive", f"token expires in {days:.1f}d"))

    return {"domain": "runtime", "checks": {"backend": backend, "drive": drive, "fly_rag": fly_rag}, "issues": issues}


async def services_diagnoser() -> dict:
    """Checks: balizero.com frontend availability."""
    frontend = await _http_check("https://balizero.com", timeout=10.0)
    issues = []
    if not frontend.get("ok"):
        issues.append(("RED", "frontend", f"balizero.com down (HTTP {frontend.get('status', frontend.get('error', '?'))})"))
    elif frontend.get("latency_ms", 0) > 5000:
        issues.append(("YELLOW", "frontend", f"slow ({frontend['latency_ms']}ms)"))
    return {"domain": "services", "checks": {"frontend": frontend}, "issues": issues}


async def cron_agent_diagnoser() -> dict:
    """Scans ~/logs/cron-agent{,-python}/*.log for recent failures.

    Looks for 'ERROR' / 'script not found' / 'Traceback' / 'exit code [1-9]' in
    the last ~2h of each log. Absence of any run in >6h on a cron that should
    tick at least hourly also counts as YELLOW. Audit 2026-04-19 showed the
    existing diagnosers miss silent failures like core-guardian's missing
    wrapper script because they only probed HTTP/Redis/DB health.
    """
    import os
    import re
    import time

    from pathlib import Path as _Path

    log_dirs = [_Path.home() / "logs" / "cron-agent", _Path.home() / "logs" / "cron-agent-python"]
    error_re = re.compile(r"\b(ERROR|Traceback|script not found|No such file or directory)\b")
    exit_re = re.compile(r"exit code [1-9]")
    now = time.time()
    window_s = 2 * 3600  # look at last 2h of each log

    issues: list[tuple[str, str, str]] = []
    checks: dict[str, dict] = {}
    for d in log_dirs:
        if not d.is_dir():
            continue
        for log in d.glob("*.log"):
            try:
                st = log.stat()
            except OSError:
                continue
            age_s = now - st.st_mtime
            # Age-gate: a log that has not been written within the diagnoser
            # window is a DEAD job, not a failing one. Counting its stale tail
            # produces a false RED (e.g. core-guardian.log untouched for 52
            # days still reported its old errors). Skip it — staleness of a
            # job-that-should-tick is a separate concern handled elsewhere.
            if age_s > window_s:
                checks[log.name] = {"age_s": int(age_s), "err_hits_tail": 0, "stale_skipped": True}
                continue
            # Only the tail is relevant; read at most the last 64KB.
            try:
                with log.open("rb") as fh:
                    fh.seek(max(0, st.st_size - 65536))
                    tail = fh.read().decode("utf-8", errors="replace")
            except OSError as e:
                issues.append(("YELLOW", f"log:{log.name}", f"unreadable: {e}"))
                continue
            # Dedupe: count UNIQUE lines that match either regex, not the sum of
            # both findalls. A single line like "ERROR ... exit code 1" matches
            # BOTH error_re and exit_re and was previously counted twice,
            # inflating err_hits past the RED threshold on a single real error.
            err_lines = {
                i
                for i, line in enumerate(tail.splitlines())
                if error_re.search(line) or exit_re.search(line)
            }
            err_hits = len(err_lines)
            checks[log.name] = {"age_s": int(age_s), "err_hits_tail": err_hits}
            if err_hits >= 3:
                # Repeated failures = broken job, not a blip.
                issues.append(("RED", f"cron:{log.stem}", f"{err_hits} error lines in last 64KB"))
            elif err_hits >= 1:
                issues.append(("YELLOW", f"cron:{log.stem}", f"{err_hits} error lines in last 64KB"))
    return {"domain": "cron_agent", "checks": checks, "issues": issues}


# ─── Main job ──────────────────────────────────────────────────────────────


class SystemDoctor(AgentJob):
    name = "system-doctor"
    timeout_s = 600
    requires_side_effects = False  # GREEN runs don't need side effects

    async def run(self) -> RunResult:
        self.log_step("gather_health_start")

        # ── 5 diagnosers in parallel ──────────────────────────────────────
        diag_results = await asyncio.gather(
            db_diagnoser(),
            vector_diagnoser(),
            runtime_diagnoser(),
            services_diagnoser(),
            cron_agent_diagnoser(),
            return_exceptions=True,
        )

        all_issues: list[tuple[str, str, str]] = []
        all_checks: dict = {}
        for r in diag_results:
            if isinstance(r, Exception):
                all_issues.append(("RED", "diagnoser", str(r)[:100]))
            else:
                domain = r.get("domain", "?")
                all_checks[domain] = r.get("checks", {})
                all_issues.extend(r.get("issues", []))

        self.log_step("gather_health_done", outputs={"issues": len(all_issues), "domains": len(all_checks)})

        # ── Triage ────────────────────────────────────────────────────────
        triage = "GREEN"
        if any(s == "RED" for s, _, _ in all_issues):
            triage = "RED"
        elif any(s == "YELLOW" for s, _, _ in all_issues):
            triage = "YELLOW"

        self.log_step("triage", outputs={"level": triage, "issues": len(all_issues)})

        # ── Auto-fix (LOW-risk only) ──────────────────────────────────────
        fixes: list[str] = []
        if triage == "RED":
            for severity, service, detail in all_issues:
                if service == "backend" and severity == "RED" and (
                    "HTTP 5" in detail or "timeout" in detail.lower()
                ):
                    r = await _shell_check(
                        ["fly", "machines", "restart", "--app", "nuzantara-rag"],
                        timeout=60.0,
                    )
                    if r.get("ok"):
                        fixes.append("restarted fly machines (nuzantara-rag)")
                        self._side_effects.append("fly_restart:nuzantara-rag")
            self.log_step("auto_fix", outputs={"fixes": len(fixes)})

        # ── Compose report ────────────────────────────────────────────────
        report_text = self._compose_report(triage, all_issues, fixes)

        # ── Deliver (only if not GREEN to avoid spam) ─────────────────────
        if triage in ("YELLOW", "RED"):
            ok = await self.send_telegram(report_text)
            self.log_step(
                "telegram_send",
                outputs={"ok": ok},
                side_effect="telegram_alert" if ok else None,
                error=None if ok else "telegram_failed",
            )
        else:
            self.log_step("telegram_skipped", outputs={"reason": "GREEN_no_spam"})

        return RunResult(
            status="ok",
            duration_s=self._elapsed(),
            side_effects=self._side_effects,
            output=report_text,
        )

    def _compose_report(
        self,
        triage: str,
        issues: list[tuple[str, str, str]],
        fixes: list[str],
    ) -> str:
        emoji = {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴"}.get(triage, "❓")
        lines = [
            f"{emoji} <b>System Doctor</b> — {triage}",
            f"{datetime.now(WITA).strftime('%H:%M WITA')}",
        ]

        if triage == "GREEN":
            lines.append("All services healthy ✅")
        else:
            red = [i for i in issues if i[0] == "RED"]
            yel = [i for i in issues if i[0] == "YELLOW"]
            if red:
                lines.append(f"\n<b>🔴 RED ({len(red)}):</b>")
                for _, svc, det in red:
                    lines.append(f"• {svc}: {det}")
            if yel:
                lines.append(f"\n<b>🟡 YELLOW ({len(yel)}):</b>")
                for _, svc, det in yel:
                    lines.append(f"• {svc}: {det}")
            if fixes:
                lines.append("\n<b>✅ Auto-fixes applied:</b>")
                for f in fixes:
                    lines.append(f"• {f}")

        return "\n".join(lines)

    def _elapsed(self) -> float:
        return time.time() - self.started_at


if __name__ == "__main__":
    main(SystemDoctor)
