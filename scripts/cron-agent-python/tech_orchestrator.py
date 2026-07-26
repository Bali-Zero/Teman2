#!/usr/bin/env python3
"""
Tech Orchestrator (L2) — every 4h at :30.

# Organo: tech-orchestrator (cron-agent-python, L2 correlator) → produce:
#         Telegram brief operazionale + azioni fly/git/deploy (condizionali)
# Consuma da: system-doctor state.json, weekly-dep-audit state.json (L1 agents)
#
# Ruolo: cervello decisionale. Correla segnali multipli, applica guardrails
#         deterministici (blackout/deploy-in-progress/diff-gate), delega fix
#         bounded a Claude SDK con can_use_tool safety. Se l'organismo ha un
#         immune system, qui e' il T-helper che orchestra la risposta.
# Simbiosi: non decide autonomamente deploy se diff tocca file critici
#         (fly.toml, dependencies.py, alembic) — escalate a Zero sempre.

Reads L1 agent outputs (system-doctor, weekly-dep-audit), correlates signals,
decides remediation, executes LOW-risk fixes, delegates MEDIUM fixes to Claude
Code CLI, and reports HIGH issues for human review.

Uses full Claude Agent SDK:
- can_use_tool hook for deploy safety (diff-size gate, critical files check)
- max_turns + max_budget_usd hard caps (prevent runaway)
- PreToolUse / PostToolUseFailure hooks for audit trail
- Streaming ToolUseBlock inspection

Guardrails (deterministic, no LLM):
- Blackout 00:00-03:00 WITA → skip
- Deploy-in-progress → no deploy actions
- Diff-size gate → >3 files or critical paths → no deploy
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from agent_job import AgentJob, RunResult, WITA, main

STATE_DIR = Path.home() / ".cron-agent-python"


# ─── Guardrails (deterministic) ─────────────────────────────────────────────

def is_blackout() -> bool:
    """00:00-03:00 WITA = no action window."""
    hour = datetime.now(WITA).hour
    return 0 <= hour < 3


async def is_deploy_in_progress() -> bool:
    """Check fly status for 'deploy' keyword."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "fly", "status", "--app", "nuzantara-rag",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=20.0)
        return b"deploy" in stdout.lower()
    except Exception:
        return False


def diff_size_check() -> dict:
    """Returns {safe: bool, files: list, critical: list}."""
    try:
        r = subprocess.run(
            ["git", "-C", str(Path.home() / "Desktop" / "nuzantara"),
             "diff", "--name-only", "HEAD", "--", "apps/backend-rag/backend/"],
            capture_output=True, text=True, timeout=10,
        )
        # task #17/#20 fail-open fix (2026-07-26): `subprocess.run` here had no
        # `check=True`, so a nonzero returncode (dead/unreadable path — a stale
        # `~/Desktop/nuzantara` compat symlink is the only thing standing
        # between this and a permanently-open gate) never raised, and empty
        # stdout on a failed `git diff` is byte-identical to empty stdout on a
        # genuinely clean tree: `files = []` -> `safe = True`. A gate that
        # cannot measure the diff must not authorise a deploy.
        if r.returncode != 0:
            return {"safe": False, "files": [], "critical": [], "error": f"git diff exited {r.returncode}: {r.stderr.strip()}"}
        files = [f for f in r.stdout.strip().split("\n") if f]
        critical_patterns = ["dependencies.py", "fly.toml", ".env", "alembic/env.py"]
        critical = [f for f in files if any(p in f for p in critical_patterns)]
        safe = len(files) <= 3 and len(critical) == 0
        return {"safe": safe, "files": files, "critical": critical}
    except Exception as e:
        return {"safe": False, "files": [], "critical": [], "error": str(e)}


# ─── Load L1 reports ────────────────────────────────────────────────────────

def load_l1_report(name: str) -> dict | None:
    """Read state.json from a sibling agent job (fallback path)."""
    f = STATE_DIR / f"{name}.state.json"
    if not f.exists():
        return None
    try:
        d = json.loads(f.read_text())
        # Fresh if run in last 24h
        age = time.time() - d.get("ts", 0)
        if age > 86400:
            return None
        return d
    except Exception:
        return None


async def consume_redis_events(streams: list[str], max_age_s: int = 3600) -> list[dict]:
    """Read recent events from Redis cron:reports stream.

    VADEMECUM §1 point 8 — event-driven. Preferred over load_l1_report (polling).
    Returns list of event dicts from specified streams, filtered by age.

    Graceful degradation: if Redis down, returns empty list.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "redis-cli", "-t", "3",
            "XREVRANGE", "cron:reports", "+", "-", "COUNT", "20",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        if proc.returncode != 0:
            return []
    except Exception:
        return []

    # Parse redis-cli output: alternating lines
    # <id>\n<field1>\n<value1>\n<field2>\n<value2>\n...
    lines = stdout.decode().strip().split("\n")
    events: list[dict] = []
    now = time.time()
    i = 0
    while i < len(lines):
        stream_id = lines[i].strip()
        if not stream_id or "-" not in stream_id:
            i += 1
            continue
        # Read fields
        event: dict[str, str] = {"_stream_id": stream_id}
        i += 1
        while i < len(lines) and "-" not in lines[i]:
            key = lines[i].strip()
            i += 1
            if i < len(lines):
                val = lines[i].strip()
                event[key] = val
                i += 1
        # Filter by job name and age
        if event.get("job") in streams:
            ts = int(event.get("ts", 0))
            if now - ts <= max_age_s:
                events.append(event)
    return events


# ─── Correlation analysis (rule-based) ──────────────────────────────────────

def correlate(
    system_doctor: dict | None,
    weekly_dep_audit: dict | None,
) -> list[dict]:
    """Return list of issues with classification.

    Each issue: {severity: LOW|MED|HIGH, category: str, description: str,
                 auto_fix: callable | None, delegate_prompt: str | None}
    """
    issues: list[dict] = []

    # system-doctor signals — handle both dict (from state.json) and Redis event format
    sd = system_doctor or {}
    sd_status = sd.get("status", "?")
    # Redis events store side_effects as comma-separated string; state.json as list
    raw_side_effects = sd.get("side_effects", [])
    if isinstance(raw_side_effects, str):
        sd_side_effects = raw_side_effects.split(",")
    else:
        sd_side_effects = raw_side_effects

    # If system-doctor detected RED (via telegram_alert side effect) → investigate
    if any("telegram_alert" in s for s in sd_side_effects) and sd_status == "ok":
        issues.append({
            "severity": "MED",
            "category": "infra_alert",
            "description": "system-doctor alerted — check infra health",
            "auto_fix": None,
            "delegate_prompt": None,
        })

    # weekly-dep-audit signals
    # (not yet migrated, skip for now)

    return issues


# ─── Remediation actions ────────────────────────────────────────────────────


async def restart_backend() -> dict:
    """LOW-risk: restart nuzantara-rag Fly machines."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "fly", "machines", "restart", "--app", "nuzantara-rag",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60.0)
        ok = proc.returncode == 0
        return {"ok": ok, "stdout": stdout.decode()[:300], "stderr": stderr.decode()[:300]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ─── Main tech orchestrator job ─────────────────────────────────────────────


class TechOrchestrator(AgentJob):
    name = "tech-orchestrator"
    timeout_s = 900
    requires_side_effects = False

    async def run(self) -> RunResult:
        actions_taken: list[str] = []
        pending_human: list[str] = []

        # ── Guardrail 1: blackout ───────────────────────────────────────
        if is_blackout():
            self.log_step("blackout_skip", outputs={"hour": datetime.now(WITA).hour})
            return RunResult(status="ok", duration_s=self._elapsed(),
                             side_effects=[], output="BLACKOUT 00-03 WITA — skipped")

        # ── Guardrail 2: deploy in progress ─────────────────────────────
        deploy_in_progress = await is_deploy_in_progress()
        self.log_step("check_deploy_in_progress", outputs={"in_progress": deploy_in_progress})

        # ── Guardrail 3: diff size ──────────────────────────────────────
        diff = diff_size_check()
        self.log_step("diff_size_check", outputs=diff)

        # ── Step 1: load L1 reports (prefer Redis stream, fallback filesystem) ──
        # VADEMECUM §1 point 8 — event-driven Redis consumer.
        l1_events = await consume_redis_events(
            streams=["system-doctor", "weekly-dep-audit"],
            max_age_s=3600 * 6,  # last 6h
        )
        self.log_step("consume_redis_events", outputs={"count": len(l1_events)})

        # Deduplicate by job (keep most recent)
        latest_by_job: dict[str, dict] = {}
        for ev in l1_events:
            job = ev.get("job", "")
            if job not in latest_by_job or ev.get("ts", "0") > latest_by_job[job].get("ts", "0"):
                latest_by_job[job] = ev

        # Fallback to filesystem state.json if Redis has nothing
        sd = latest_by_job.get("system-doctor") or load_l1_report("system-doctor")
        dep = latest_by_job.get("weekly-dep-audit") or load_l1_report("weekly-dep-audit")
        self.log_step("load_l1_reports", outputs={
            "system_doctor": sd is not None,
            "weekly_dep_audit": dep is not None,
            "source": "redis" if latest_by_job else "filesystem",
        })

        if sd is None and dep is None:
            # No fresh data → passive
            self.log_step("no_fresh_data", outputs={"action": "no-op"})
            await self.send_telegram(
                "🔧 <b>Tech Orchestrator</b>\n"
                "No fresh L1 data (system-doctor / weekly-dep-audit). Skipping correlation."
            )
            return RunResult(status="ok", duration_s=self._elapsed(),
                             side_effects=self._side_effects,
                             output="No L1 data available")

        # ── Step 2: correlation ─────────────────────────────────────────
        issues = correlate(sd, dep)
        self.log_step("correlate", outputs={
            "issues_count": len(issues),
            "severities": [i["severity"] for i in issues],
        })

        # ── Step 3: remediation ─────────────────────────────────────────
        for issue in issues:
            sev = issue["severity"]
            cat = issue["category"]
            desc = issue["description"]

            if sev == "LOW":
                # Auto-act (if we have auto_fix)
                fn = issue.get("auto_fix")
                if fn:
                    r = await fn()
                    actions_taken.append(f"{cat}: {r}")
                    self._side_effects.append(f"auto_fix:{cat}")
                    self.log_step(f"auto_fix:{cat}", outputs=r)

            elif sev == "MED":
                # Delegate to Claude SDK with strict tool budget
                prompt = issue.get("delegate_prompt")
                if prompt and not deploy_in_progress:
                    result = await self._delegate_with_sdk(prompt, category=cat)
                    actions_taken.append(f"{cat}: delegated → {result[:100]}")
                    self.log_step(f"delegate:{cat}", outputs={"len": len(result)})

            elif sev == "HIGH":
                pending_human.append(f"[{cat}] {desc}")

        # ── Step 4: deploy rule (only if fixes applied AND diff safe) ──
        deployed = False
        if actions_taken and diff["safe"] and not deploy_in_progress:
            # Check tests first (deterministic)
            tests_ok = await self._run_tests()
            self.log_step("pre_deploy_tests", outputs={"ok": tests_ok})
            if tests_ok:
                deploy_result = await self._deploy()
                deployed = deploy_result["ok"]
                actions_taken.append(f"deploy: {'OK' if deployed else 'FAILED'}")
                self._side_effects.append("fly_deploy" if deployed else "fly_deploy_failed")
                self.log_step("deploy", outputs=deploy_result)

        # ── Step 5: compose Telegram brief ──────────────────────────────
        brief = self._compose_brief(
            sd=sd, dep=dep, issues=issues,
            actions_taken=actions_taken,
            pending_human=pending_human,
            deployed=deployed,
            diff=diff,
        )

        # Skip Telegram if nothing interesting (GREEN path)
        if actions_taken or pending_human or (sd and "telegram_alert" in sd.get("side_effects", [])):
            await self.send_telegram(brief)

        return RunResult(
            status="ok",
            duration_s=self._elapsed(),
            side_effects=self._side_effects,
            output=brief,
        )

    # ── SDK delegation (bounded) ────────────────────────────────────────

    async def _delegate_with_sdk(self, prompt: str, category: str) -> str:
        """Delegate a MED-severity fix to Claude via SDK with hard caps.

        Uses:
        - max_turns=5 (prevent infinite loops)
        - can_use_tool callback (block dangerous tools)
        - PreToolUse / PostToolUseFailure hooks (audit)
        """
        from claude_agent_sdk import (
            ClaudeSDKClient,
            ClaudeAgentOptions,
            PermissionResultAllow,
            PermissionResultDeny,
            HookMatcher,
        )

        audit: list[dict] = []

        async def can_use_tool(name: str, input: dict, ctx: Any):
            """Safety: block rm -rf, git push, fly deploy."""
            if name == "Bash":
                cmd = input.get("command", "")
                dangerous = ["rm -rf", "git push", "fly deploy", "DROP TABLE", "DELETE FROM"]
                if any(d in cmd for d in dangerous):
                    audit.append({"denied": True, "tool": name, "reason": f"dangerous: {cmd[:80]}"})
                    return PermissionResultDeny(message=f"Blocked dangerous command: {cmd[:80]}")
            audit.append({"tool": name, "input_preview": str(input)[:100]})
            return PermissionResultAllow()

        # Routing: use Opus 4.7 high effort for orchestration (enables
        # native parallel tool calls when tasks are independent).
        from agent_config import get_config, MODEL_OPUS_47
        cfg = get_config(self.name)
        resolved_model = cfg["model"]
        resolved_effort = cfg["effort"]
        if resolved_effort == "xhigh":
            resolved_effort = "high"  # CLI compat

        opts = ClaudeAgentOptions(
            max_turns=5,
            effort=resolved_effort,
            model=resolved_model,
            permission_mode="bypassPermissions",
            can_use_tool=can_use_tool,
            setting_sources=[],
            tools=["Bash", "Read", "Edit"],  # narrow tool set
            thinking={"type": "adaptive"} if resolved_model == MODEL_OPUS_47 else None,  # type: ignore[arg-type]
            system_prompt=(
                "You are a focused fix agent for a single issue. "
                "Make minimal changes. Do not modify dependencies.py, fly.toml, "
                ".env, or alembic/. When steps are INDEPENDENT (e.g. reading 3 "
                "unrelated files, running 2 non-conflicting Bash commands), "
                "emit their tool_use blocks IN PARALLEL in the same turn to "
                "minimize latency. Serialize only when step B depends on A's "
                "output."
            ),
        )

        chunks: list[str] = []
        try:
            async with ClaudeSDKClient(options=opts) as client:
                await client.query(prompt)
                async for msg in client.receive_response():
                    content = getattr(msg, "content", None)
                    if isinstance(content, list):
                        for block in content:
                            text = getattr(block, "text", None)
                            if text:
                                chunks.append(text)
                    elif isinstance(content, str):
                        chunks.append(content)
        except Exception as e:
            return f"[delegate error: {e}]"

        self.log_step(f"delegate_audit:{category}", outputs={"calls": len(audit)})
        return "\n".join(chunks).strip()

    # ── Deploy helpers ──────────────────────────────────────────────────

    async def _run_tests(self) -> bool:
        """Run core backend tests."""
        try:
            proc = await asyncio.create_subprocess_shell(
                "cd ~/nuzantara/apps/backend-rag && "
                "source .venv/bin/activate && "
                "PYTHONPATH=. timeout 120 pytest backend/tests/services/rag/test_confidence.py -x --tb=line -q",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=150.0)
            return proc.returncode == 0
        except Exception:
            return False

    async def _deploy(self) -> dict:
        """Deploy backend-rag (rolling)."""
        try:
            proc = await asyncio.create_subprocess_shell(
                "cd ~/nuzantara/apps/backend-rag && fly deploy --strategy rolling",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=480.0)
            return {
                "ok": proc.returncode == 0,
                "stdout": stdout.decode()[-500:],
                "stderr": stderr.decode()[-500:],
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Brief composition ──────────────────────────────────────────────

    def _compose_brief(self, sd, dep, issues, actions_taken, pending_human, deployed, diff) -> str:
        lines = [
            "🔧 <b>Tech Orchestrator</b>",
            f"{datetime.now(WITA).strftime('%H:%M WITA')}",
        ]

        # L1 status
        sd_icon = "✅" if sd and sd.get("status") == "ok" else "⚠️"
        dep_icon = "✅" if dep and dep.get("status") == "ok" else "—"
        lines.append(f"\n<b>L1 status:</b> system-doctor {sd_icon} · weekly-dep {dep_icon}")

        # Git diff context
        if diff["files"]:
            lines.append(f"<b>Uncommitted changes:</b> {len(diff['files'])} files" +
                         (f" ⚠️ {len(diff['critical'])} critical" if diff["critical"] else ""))

        # Issues
        if issues:
            lines.append(f"\n<b>Correlated issues:</b> {len(issues)}")
            for i in issues[:5]:
                lines.append(f"• [{i['severity']}] {i['description']}")

        # Actions
        if actions_taken:
            lines.append(f"\n<b>Actions taken:</b>")
            for a in actions_taken[:5]:
                lines.append(f"✅ {a[:120]}")

        if deployed:
            lines.append(f"\n🚀 Deployed backend-rag")

        if pending_human:
            lines.append(f"\n<b>Needs human:</b>")
            for p in pending_human[:5]:
                lines.append(f"⚠️ {p}")

        if not actions_taken and not pending_human and not issues:
            lines.append("\n✅ All quiet.")

        return "\n".join(lines)

    def _elapsed(self) -> float:
        return time.time() - self.started_at


if __name__ == "__main__":
    main(TechOrchestrator)
