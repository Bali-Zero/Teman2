"""
Shared library for cron-agent-python jobs.

Provides:
- AgentJob: base class with run_ledger, idempotency, Telegram alerts, Claude Agent SDK integration
- Helpers: send_telegram, curl_json, backend_api, claude_synthesize
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import socket
import sys
import time
import traceback
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx
import structlog

HOME = Path.home()
STATE_DIR = HOME / ".cron-agent-python"
LOG_DIR = HOME / "logs" / "cron-agent-python"

# A redis-cli reply that begins with one of these is a server REFUSAL, not a
# value — and redis-cli still exits 0 when it happens (verified 2026-07-25).
_REDIS_ERR_RE = re.compile(
    r"^(NOAUTH|WRONGPASS|NOPERM|ERR|LOADING|BUSY|READONLY|MASTERDOWN|CLUSTERDOWN)\b"
)

# redis-cli reads REDISCLI_AUTH natively. Deriving it here (not only in run.sh)
# covers jobs launched straight from a LaunchAgent — e.g.
# com.balizero.intel-radar-daily-digest, which sources the secrets file but
# exports only REDIS_PASSWORD, a name redis-cli ignores. Passing the secret via
# the environment keeps it out of argv / `ps`.
if not os.environ.get("REDISCLI_AUTH") and os.environ.get("REDIS_PASSWORD"):
    os.environ["REDISCLI_AUTH"] = os.environ["REDIS_PASSWORD"]
SECRETS_FILE = HOME / ".nuzantara-secrets.env"
WITA = timezone(timedelta(hours=8))

STATE_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)


def _load_secrets() -> None:
    if not SECRETS_FILE.exists():
        return
    for line in SECRETS_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            val = val.strip().strip('"').strip("'")
            os.environ.setdefault(key.strip(), val)


def _prefer_local_pg_tunnel() -> None:
    """Use the local Fly Postgres proxy when present.

    Secrets stay as the canonical flycast DSN; LaunchAgents can run through
    `fly proxy 15432:5432 -a nuzantara-postgres` without duplicating credentials.
    """
    local_dsn = os.environ.get("DATABASE_URL_LOCAL")
    if local_dsn:
        os.environ["DATABASE_URL"] = local_dsn
        return

    dsn = os.environ.get("DATABASE_URL", "")
    if "nuzantara-postgres.flycast" not in dsn:
        return

    try:
        with socket.create_connection(("127.0.0.1", 15432), timeout=0.2):
            pass
    except OSError:
        return

    os.environ["DATABASE_URL"] = (
        dsn.replace("nuzantara-postgres.flycast:5432", "127.0.0.1:15432")
        .replace("nuzantara-postgres.flycast", "127.0.0.1:15432")
    )


def _force_oauth_only() -> None:
    """Remove any ANTHROPIC_API_KEY to force Claude Agent SDK down the OAuth
    Max-plan path via keychain. Prevents accidental pay-per-token billing.

    The SDK tries ANTHROPIC_API_KEY first if set. Removing it makes the SDK
    fall back to the OAuth token stored in macOS keychain (Claude Max plan).
    """
    if "ANTHROPIC_API_KEY" in os.environ:
        del os.environ["ANTHROPIC_API_KEY"]


_load_secrets()
_prefer_local_pg_tunnel()
_force_oauth_only()


def _hash(data: Any) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()[:12]


@dataclass
class RunLedgerEntry:
    run_id: str
    job: str
    step: str
    inputs_hash: str
    outputs_hash: str
    side_effects: list[str]
    error: str | None
    duration_s: float
    ts: str


@dataclass
class RunResult:
    status: str  # "ok", "error", "timeout"
    duration_s: float
    side_effects: list[str] = field(default_factory=list)
    output: str = ""
    error: str | None = None


class AgentJob:
    """Base class for all cron agent jobs.

    Subclass and implement `async def run()`. Returns RunResult.
    """

    # Override in subclass
    name: str = "unnamed-job"
    telegram_chat_id: str = ""  # defaults to TELEGRAM_OWNER_CHAT_ID
    timeout_s: int = 600

    def __init__(self) -> None:
        self.run_id = f"{self.name}-{int(time.time())}"
        self.started_at = time.time()
        self.ledger: list[RunLedgerEntry] = []
        self.logger = structlog.get_logger(self.name).bind(run_id=self.run_id)
        self.state_file = STATE_DIR / f"{self.name}.state.json"
        self.log_file = LOG_DIR / f"{self.name}.log"
        self.lock_file = STATE_DIR / f"{self.name}.lock"
        self._side_effects: list[str] = []

    # ─── Lock (PID-based for macOS) ────────────────────────────────────────

    def acquire_lock(self) -> bool:
        if self.lock_file.exists():
            try:
                old_pid = int(self.lock_file.read_text().strip())
                os.kill(old_pid, 0)  # check if alive
                return False  # lock held
            except (ValueError, ProcessLookupError, PermissionError):
                self.lock_file.unlink(missing_ok=True)
        self.lock_file.write_text(str(os.getpid()))
        return True

    def release_lock(self) -> None:
        self.lock_file.unlink(missing_ok=True)

    # ─── Run ledger ────────────────────────────────────────────────────────

    def log_step(
        self,
        step: str,
        inputs: Any = None,
        outputs: Any = None,
        error: str | None = None,
        side_effect: str | None = None,
        duration_s: float = 0.0,
    ) -> None:
        entry = RunLedgerEntry(
            run_id=self.run_id,
            job=self.name,
            step=step,
            inputs_hash=_hash(inputs) if inputs is not None else "",
            outputs_hash=_hash(outputs) if outputs is not None else "",
            side_effects=[side_effect] if side_effect else [],
            error=error,
            duration_s=duration_s,
            ts=datetime.now(WITA).isoformat(),
        )
        self.ledger.append(entry)
        if side_effect:
            self._side_effects.append(side_effect)
        self.logger.info(step, error=error, duration_s=duration_s, side_effect=side_effect)

    # ─── Telegram ──────────────────────────────────────────────────────────

    async def send_telegram(
        self, msg: str, tier: str, chat_id: str | None = None, dedup_key: str = ""
    ) -> bool:
        """Route through the notification gateway (scripts/tg_notify.py) — never
        call the raw Telegram HTTP API directly (anti-regrowth lint, W104 promotion 2026-07-25:
        this base class was cicatrix-superscar #3's 1-NEW violation poisoning
        every open PR). The gateway owns credential resolution, per-tier dedup and
        the daily P0 budget — a caller only decides `tier`.

        `tier` has no default on purpose: every call site (this file's own
        run_job() failure alert, log_anomaly_detector.py — per-alert severity,
        intel_radar_daily_digest.py) must state its severity explicitly rather
        than silently inherit one, since the choice is genuinely call-site
        specific and a silent default would hide behavior change in files this
        migration doesn't otherwise touch.

        `chat_id` is accepted for backward API-compatibility but is not
        forwarded — no caller in this tree has ever overridden it, and the
        gateway always resolves the configured owner chat itself.

        Returns whether the gateway took custody of the notification. The
        gateway always exits 0 by contract ("NEVER fails the caller" —
        tg_notify.py's own docstring), so `returncode` alone can't tell "sent"
        from "silently swallowed"; the real outcome is on its `tg_notify:
        <outcome>` STDERR line. Mirrors scripts/sentinel_lib/alerter.py's own
        outcome parsing (established 2026-07-07, PR #2067 cohort-2). False
        only when that line is missing/unparseable — a genuine transport
        failure, not merely "spooled for later" or "already sent, deduped".
        """
        import subprocess

        gateway = Path(__file__).resolve().parent.parent / "tg_notify.py"
        if not gateway.exists():  # HOME-fork copy: fall back to the repo checkout (#1)
            gateway = Path.home() / "nuzantara" / "scripts" / "tg_notify.py"

        cmd = [sys.executable, str(gateway), "--tier", tier, "--source", f"cron-agent-python:{self.name}"]
        if dedup_key:
            cmd += ["--dedup-key", dedup_key]
        cmd += ["--", msg]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            outcome = ""
            for line in ((proc.stderr or "") + "\n" + (proc.stdout or "")).splitlines():
                if line.startswith("tg_notify:"):
                    outcome = line.split(":", 1)[1].strip().split(" ")[0]
            ok = outcome in (
                "sent", "spooled", "logged", "deduped",
                "p0_overflow_spooled", "p0_unsent_spooled",
            )
            if ok:
                self._side_effects.append(f"telegram:{tier}")
            else:
                self.logger.warning(
                    "telegram_gateway_error", returncode=proc.returncode,
                    outcome=outcome or "unparseable", stderr=(proc.stderr or "")[:200],
                )
            return ok
        except Exception as e:
            self.logger.error("telegram_error", error=str(e))
            return False

    # ─── Backend API ───────────────────────────────────────────────────────

    async def backend_api(
        self,
        path: str,
        method: str = "GET",
        params: dict | None = None,
        json_body: dict | None = None,
        timeout: float = 30.0,
    ) -> dict | None:
        base = "https://nuzantara-rag.fly.dev"
        api_key = os.environ.get("NUZANTARA_API_KEY", "")
        headers = {"X-API-Key": api_key} if api_key else {}
        url = f"{base}{path}"
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.request(
                    method, url, params=params, json=json_body, headers=headers
                )
                r.raise_for_status()
                return r.json()
        except Exception as e:
            self.logger.error("backend_api_error", path=path, error=str(e))
            return None

    # ─── Claude Agent SDK (bounded synthesis) ──────────────────────────────

    async def claude_synthesize(
        self,
        prompt: str,
        max_turns: int = 3,
        effort: str | None = None,
        system_prompt: str | None = None,
        model: str | None = None,
        task_budget: int | None = None,
        betas: list[str] | None = None,
        fork_from_session: str | None = None,
        enable_checkpointing: bool = False,
        auto_failure_hook: bool = True,
        subagents: dict[str, dict[str, Any]] | None = None,
        tools_allowed: list[str] | None = None,
        adaptive_thinking: bool = False,
    ) -> str:
        """Use Claude SDK for bounded reasoning/synthesis.

        Routing: reads `agent_config.get_config(self.name)` to pick default
        model/effort/task_budget per tier. Callers can override any of those
        by passing the kwargs explicitly.

        Advanced flags (2026-04-17):
          - fork_from_session: if set, fork an existing session_id so prompt
            cache is preserved (punto 2 del roadmap potenzialita')
          - enable_checkpointing: snapshot files before Edit/Write for rollback
            (punto 1 del roadmap potenzialita')
          - auto_failure_hook: register PostToolUseFailure hook that records
            failures in memory.db as 'unresolved' (punto 4 del roadmap)
          - subagents: dict {name: {description, prompt, model, effort, tools}}
            — main agent can dispatch to specialists via Task tool (punto 3)
          - tools_allowed: override empty tools list (required when subagents
            need main to invoke Task tool)
          - adaptive_thinking: if True, enable thinking={"type":"adaptive"}
            so Opus 4.7 auto-modulates reasoning depth per query complexity
            (Opus 4.7 only — no-op on Sonnet/Haiku)

        Use ONLY for narrative output from collected data. Do NOT give it tools
        that cause side effects — the deterministic Python code owns those.
        """
        from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, HookMatcher
        from claude_agent_sdk.types import AgentDefinition

        # Resolve routing config (plan §1+§2)
        from agent_config import get_config, MODEL_OPUS_47

        cfg = get_config(self.name)
        resolved_model = model or cfg["model"]
        resolved_effort = effort or cfg["effort"]
        resolved_budget = task_budget if task_budget is not None else cfg.get("task_budget")
        resolved_betas = list(betas) if betas is not None else list(cfg.get("betas") or [])

        # CLI compat: Claude Code CLI (shell-out) currently only accepts
        # low|medium|high|max for --effort. xhigh is SDK/settings-only. Map
        # xhigh → high at call time to avoid "invalid argument" from the CLI.
        if resolved_effort == "xhigh":
            self.logger.debug(
                "effort_downgraded_for_cli",
                original="xhigh",
                effective="high",
                model=resolved_model,
            )
            resolved_effort = "high"

        # task_budget only applies to Opus 4.7 (beta currently model-specific).
        # If model != Opus 4.7, skip task_budget even if configured.
        # tools_allowed overrides empty list (needed when main uses Task to call subagents)
        resolved_tools: list[str] = list(tools_allowed) if tools_allowed else []

        # B5 2026-05-15: fallback_model auto-switches Opus 4.7 → Sonnet 4.6 when
        # the primary model is overloaded or quota-exhausted. SDK-native.
        # Maps cron-agent default Opus → Sonnet, Sonnet → Haiku, Haiku → Haiku.
        from agent_config import MODEL_SONNET_46, MODEL_HAIKU_45
        if resolved_model == MODEL_OPUS_47:
            resolved_fallback = MODEL_SONNET_46
        elif resolved_model == MODEL_SONNET_46:
            resolved_fallback = MODEL_HAIKU_45
        else:
            resolved_fallback = MODEL_HAIKU_45

        opts_kwargs: dict[str, Any] = {
            "max_turns": max_turns,
            "effort": resolved_effort,  # type: ignore[arg-type]
            "system_prompt": system_prompt,
            "model": resolved_model,
            "fallback_model": resolved_fallback,
            "tools": resolved_tools,
            "allowed_tools": resolved_tools,
            "permission_mode": "bypassPermissions",
            "setting_sources": [],  # skip user hooks (avoid SessionStart hang)
        }

        # ── Sub-agents (specialist dispatch via Task tool) ──────────────
        if subagents:
            sdk_agents: dict[str, AgentDefinition] = {}
            for name, spec in subagents.items():
                sdk_agents[name] = AgentDefinition(
                    description=spec.get("description", f"Specialist {name}"),
                    prompt=spec["prompt"],
                    tools=spec.get("tools"),
                    model=spec.get("model"),
                    effort=spec.get("effort"),
                    maxTurns=spec.get("max_turns", 3),
                    permissionMode="bypassPermissions",
                )
            opts_kwargs["agents"] = sdk_agents
            # Main must have Task tool available to dispatch to subagents
            if "Task" not in resolved_tools:
                resolved_tools.append("Task")
                opts_kwargs["tools"] = resolved_tools
                opts_kwargs["allowed_tools"] = resolved_tools
        if resolved_budget and resolved_model == MODEL_OPUS_47:
            opts_kwargs["task_budget"] = {"total": int(resolved_budget)}  # type: ignore[typeddict-item]
        if resolved_betas:
            opts_kwargs["betas"] = resolved_betas  # type: ignore[typeddict-item]

        # ── File checkpointing (snapshot before Edit/Write for rollback) ─
        if enable_checkpointing:
            opts_kwargs["enable_file_checkpointing"] = True

        # ── Adaptive thinking (Opus 4.7 auto-modulates reasoning depth) ──
        if adaptive_thinking and resolved_model == MODEL_OPUS_47:
            opts_kwargs["thinking"] = {"type": "adaptive"}  # type: ignore[typeddict-item]

        # ── Fork session (inherit prompt cache from a prior run) ─────────
        if fork_from_session:
            opts_kwargs["resume"] = fork_from_session
            opts_kwargs["fork_session"] = True
            self.logger.info("session_fork", parent=fork_from_session[:36])

        # ── Auto-failure hook (record failures as 'unresolved' memory) ────
        if auto_failure_hook:
            job_name = self.name
            job_logger = self.logger

            async def _post_fail_hook(input_data, tool_use_id, ctx):
                try:
                    tool_name = input_data.get("tool_name", "?")
                    err_msg = input_data.get("error", "")[:200]
                    tool_in = str(input_data.get("tool_input", ""))[:150]
                    mem_cli = Path.home() / ".claude" / "scripts" / "mem"
                    if mem_cli.exists():
                        import subprocess
                        content = (
                            f"cron-agent {job_name} tool_failure: {tool_name}"
                            f" on {tool_in} → {err_msg}"
                        )
                        subprocess.run(
                            [str(mem_cli), "save", "unresolved", content, "7"],
                            capture_output=True, timeout=10, check=False,
                        )
                    job_logger.warning(
                        "tool_use_failure_captured",
                        tool=tool_name, error=err_msg[:120],
                    )
                except Exception as e:
                    job_logger.error("post_fail_hook_error", error=str(e))
                return {}  # empty dict = allow continuation

            opts_kwargs["hooks"] = {
                "PostToolUseFailure": [HookMatcher(hooks=[_post_fail_hook])],
            }

        self.log_step(
            "claude_synthesize_start",
            inputs={
                "model_used": resolved_model,
                "effort_used": resolved_effort,
                "task_budget_advisory": resolved_budget if resolved_model == MODEL_OPUS_47 else None,
                "betas": resolved_betas,
                "forked_from": fork_from_session[:36] if fork_from_session else None,
                "checkpointing": enable_checkpointing,
                "auto_failure_hook": auto_failure_hook,
                "subagents": list(subagents.keys()) if subagents else None,
                "tools": resolved_tools or None,
                "adaptive_thinking": adaptive_thinking and resolved_model == MODEL_OPUS_47,
            },
        )

        opts = ClaudeAgentOptions(**opts_kwargs)
        chunks: list[str] = []
        last_usage: dict | None = None
        captured_session_id: str | None = None
        try:
            async with ClaudeSDKClient(options=opts) as client:
                await client.query(prompt)
                async for msg in client.receive_response():
                    # Accumulate text content
                    content = getattr(msg, "content", None)
                    if isinstance(content, list):
                        for block in content:
                            text = getattr(block, "text", None)
                            if text:
                                chunks.append(text)
                    elif isinstance(content, str):
                        chunks.append(content)
                    # Capture usage if exposed on msg
                    usage = getattr(msg, "usage", None)
                    if usage:
                        last_usage = usage if isinstance(usage, dict) else getattr(usage, "__dict__", None)
                    # Capture session_id for future fork_session chains
                    sid = getattr(msg, "session_id", None)
                    if sid and not captured_session_id:
                        captured_session_id = sid
        except Exception as e:
            self.logger.error(
                "claude_synthesize_error",
                error=str(e),
                model_used=resolved_model,
                effort_used=resolved_effort,
            )
            return f"[synthesis error: {e}]"

        # Log usage if present (task_budget_consumed_tokens when Opus 4.7 beta active)
        if last_usage:
            self.log_step(
                "claude_synthesize_done",
                outputs={
                    "model_used": resolved_model,
                    "task_budget_consumed": last_usage.get("task_budget_consumed_tokens")
                    if isinstance(last_usage, dict) else None,
                    "input_tokens": last_usage.get("input_tokens") if isinstance(last_usage, dict) else None,
                    "output_tokens": last_usage.get("output_tokens") if isinstance(last_usage, dict) else None,
                    "cache_read_input_tokens": last_usage.get("cache_read_input_tokens")
                    if isinstance(last_usage, dict) else None,
                    "cache_creation_input_tokens": last_usage.get("cache_creation_input_tokens")
                    if isinstance(last_usage, dict) else None,
                    "session_id": captured_session_id[:36] if captured_session_id else None,
                },
            )

        # Persist session_id for future fork_session reuse (scope: hourly)
        if captured_session_id:
            try:
                scope = f"synth-hourly:{datetime.now(WITA).strftime('%Y-%m-%d-%H')}"
                save_session(self.name, captured_session_id, scope=scope)
            except Exception as e:
                self.logger.debug("session_save_skipped", error=str(e))

        return "\n".join(chunks).strip()

    # ─── Entry point ───────────────────────────────────────────────────────

    async def run(self) -> RunResult:
        """Subclass MUST override this."""
        raise NotImplementedError

    async def _run_with_timeout(self) -> RunResult:
        try:
            return await asyncio.wait_for(self.run(), timeout=self.timeout_s)
        except asyncio.TimeoutError:
            return RunResult(
                status="timeout",
                duration_s=time.time() - self.started_at,
                side_effects=self._side_effects,
                error=f"timeout after {self.timeout_s}s",
            )
        except Exception as e:
            tb = traceback.format_exc()
            self.logger.error("run_exception", error=str(e), traceback=tb)
            return RunResult(
                status="error",
                duration_s=time.time() - self.started_at,
                side_effects=self._side_effects,
                error=f"{type(e).__name__}: {e}",
            )

    def _write_state(self, result: RunResult) -> None:
        state = {
            "job": self.name,
            "run_id": self.run_id,
            "ts": int(time.time()),
            "status": result.status,
            "duration_s": round(result.duration_s, 2),
            "side_effects": result.side_effects,
            "error": result.error,
            "host": socket.gethostname(),
            "ledger": [asdict(e) for e in self.ledger],
        }
        self.state_file.write_text(json.dumps(state, indent=2, default=str))

    def _exit_code(self, result: RunResult) -> int:
        """Fail-hard policy: if no side effects happened AND status != ok → exit 1.

        This implements the 'never allow empty success' principle.
        """
        if result.status == "ok":
            # Even if status is ok, verify side effects were produced for jobs that need them
            if hasattr(self, "requires_side_effects") and self.requires_side_effects:
                if not result.side_effects:
                    return 1
            return 0
        return 1

    async def _publish_redis_event(self, result: RunResult) -> None:
        """VADEMECUM §1 point 8 — publish Redis stream event if significant.

        Stream: `cron:<job_name>` — one per job, other organs can subscribe.
        Also: `cron:reports` — aggregated stream for L2 correlators (es. tech-orchestrator).

        Event only if significant: status!=ok OR side_effects produced OR partial errors.
        Graceful degradation: if Redis down, log warning and continue.
        """
        try:
            import subprocess

            partial_errors = sum(1 for e in self.ledger if e.error)
            significant = (
                result.status != "ok"
                or len(result.side_effects) > 0
                or partial_errors > 0
            )
            if not significant:
                return

            event = {
                "job": self.name,
                "run_id": self.run_id,
                "status": result.status,
                "duration_s": f"{result.duration_s:.2f}",
                "side_effects": ",".join(result.side_effects)[:200],
                "partial_errors": str(partial_errors),
                "ts": str(int(time.time())),
            }
            if result.error:
                event["error"] = result.error[:200]

            # Build redis-cli XADD command
            xadd_args = ["redis-cli", "-t", "3", "XADD", f"cron:reports", "MAXLEN", "~", "5000", "*"]
            for k, v in event.items():
                xadd_args.extend([k, v])

            # Also emit on job-specific stream
            xadd_job = ["redis-cli", "-t", "3", "XADD", f"cron:{self.name}", "MAXLEN", "~", "500", "*"]
            for k, v in event.items():
                xadd_job.extend([k, v])

            def _xadd(argv: list, stream: str) -> bool:
                """Run one XADD and report whether Redis actually accepted it.

                Fix (2026-07-25): `check=False` used to swallow a non-zero exit
                without raising, so the except-branch below never fired. When
                Redis gained a password, redis-cli returned NOAUTH on every call
                and this method still logged `redis_event_published` — 7957
                times, while the stream stayed frozen for 26.5 days. A producer
                that grades itself on "I ran the command" is blind by
                construction; grade on what the backend answered.
                """
                out = subprocess.run(
                    argv, capture_output=True, text=True, timeout=5, check=False,
                )
                reply = (out.stdout or "").strip()
                # redis-cli EXITS 0 even when the server refuses the command —
                # the error comes back as a REPLY on stdout ("NOAUTH ...",
                # "WRONGPASS ..."). Grading on returncode grades the proxy.
                refused = bool(_REDIS_ERR_RE.match(reply))
                if out.returncode != 0 or refused:
                    self.logger.warning(
                        "redis_publish_rejected",
                        stream=stream,
                        rc=out.returncode,
                        detail=reply[:120] or (out.stderr or "").strip()[:120],
                    )
                    return False
                return True

            published = _xadd(xadd_args, "cron:reports")
            published = _xadd(xadd_job, f"cron:{self.name}") and published

            if published:
                self.logger.info("redis_event_published", stream=f"cron:{self.name}")
        except Exception as e:
            self.logger.warning("redis_publish_failed", error=str(e))

    def _reflect(self, result: RunResult) -> None:
        """VADEMECUM §1 point 4 — reflection post-run into SQLite KB.

        Writes a structured reflection to ~/.claude/memory.db via the mem CLI.
        On error, the reflection also calls claude --print to generate a 'lesson'
        from the error context (only if the error is non-trivial).

        Failure to reflect is logged but does not affect exit code.
        """
        try:
            import subprocess

            mem_cli = Path.home() / ".claude" / "scripts" / "mem"
            if not mem_cli.exists():
                return  # MOS not available — skip silently

            # Build reflection content
            content_parts = [
                f"job={self.name}",
                f"run_id={self.run_id}",
                f"status={result.status}",
                f"duration_s={result.duration_s:.2f}",
                f"side_effects={len(result.side_effects)}",
            ]
            if result.error:
                content_parts.append(f"error={result.error[:200]}")

            # Pick memory type + importance based on outcome
            # Check if any step in the ledger had an error (partial failures matter)
            partial_errors = sum(1 for e in self.ledger if e.error)

            if result.status == "ok" and partial_errors == 0:
                # Routine full-success — skip to avoid memory spam
                # Only save unusual successes (long duration or many side effects)
                if result.duration_s < 60 and len(result.side_effects) <= 2:
                    return
                mem_type = "fact"
                importance = 4
            elif result.status == "ok":
                # Partial success — worth noting
                mem_type = "discovery"
                importance = 5
            else:
                mem_type = "unresolved"
                importance = 7  # failure — worth remembering

            content = f"cron-agent-python {self.name}: {result.status} in {result.duration_s:.1f}s"
            if result.error:
                content += f" — {result.error[:150]}"

            subprocess.run(
                [str(mem_cli), "save", mem_type, content, str(importance)],
                capture_output=True, timeout=10, check=False,
            )
        except Exception as e:
            # Don't fail the job if reflection fails
            self.logger.warning("reflection_failed", error=str(e))


async def run_job(job: AgentJob, send_alerts: bool = True) -> int:
    """Main entrypoint. Use from cron job scripts."""
    if not job.acquire_lock():
        job.logger.info("skipped", reason="lock_held")
        return 0  # not an error — previous run still active

    try:
        result = await job._run_with_timeout()
        job._write_state(result)
        job._reflect(result)  # VADEMECUM §1 point 4 — reflection in KB
        await job._publish_redis_event(result)  # VADEMECUM §1 point 8 — event bus

        if result.status != "ok" and send_alerts:
            # tier=digest, not p0: this fires for ANY subclass job that errors or
            # times out, with no severity signal at the base-class level (unlike
            # job_health.py, which only pages p0 for jobs it has marked critical).
            # Immediate-paging every cron-agent-python crash recreates the exact
            # alert-fatigue this gateway exists to prevent (Zero: "non posso più
            # ricevere 600 messaggi al giorno") — grouped + deduped is the honest
            # tier until a per-job criticality signal exists.
            await job.send_telegram(
                f"❌ {job.name} {result.status} ({result.duration_s:.1f}s)\n"
                f"{result.error or 'no error details'}",
                tier="digest",
                # Stable across repeated failures of the same job/status — the
                # message text above embeds duration_s, which varies every run
                # and would defeat the gateway's default text-hash dedup (same
                # lesson job_health.py already learned, 2026-07-11).
                dedup_key=f"cron-agent-python:{job.name}:{result.status}",
            )

        return job._exit_code(result)
    finally:
        job.release_lock()


def main(job_class: type[AgentJob]) -> None:
    """CLI entrypoint for subclass scripts."""
    job = job_class()
    exit_code = asyncio.run(run_job(job))
    sys.exit(exit_code)


# ─── Session resume helpers (Feature 4 — session resume) ───────────────────
# SQLite DB at ~/.cron-agent-python/sessions.db
# Each job can have a daily or weekly session ID stored here.
# Use with `claude --resume <session_id>` or `claude -c <session_id>`.

_SESSIONS_DB = STATE_DIR / "sessions.db"


def _sessions_db() -> Any:
    """Return sqlite3 connection to sessions.db."""
    import sqlite3
    conn = sqlite3.connect(str(_SESSIONS_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            job TEXT NOT NULL,
            scope TEXT NOT NULL,
            session_id TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            last_used INTEGER NOT NULL,
            PRIMARY KEY (job, scope)
        )
    """)
    conn.commit()
    return conn


def get_or_create_session(job_name: str, scope: str = "daily") -> str | None:
    """Get or create a Claude CLI session ID for a job.

    Args:
        job_name: Name of the job (e.g., "compliance-ops").
        scope: Session scope — "daily" (new each day), "weekly" (new each week),
               "persistent" (never expires).

    Returns:
        Session ID string or None if sessions.db unavailable.

    Usage:
        session_id = get_or_create_session("compliance-ops", scope="daily")
        if session_id:
            # Use: claude --resume {session_id} -p "today's context..."
            # Or:  claude -c {session_id} -p "..."
    """
    import sqlite3
    try:
        conn = _sessions_db()
        now = int(time.time())

        # Check if existing session is still in scope
        row = conn.execute(
            "SELECT session_id, created_at FROM sessions WHERE job=? AND scope=?",
            (job_name, scope)
        ).fetchone()

        if row:
            session_id, created_at = row
            age_hours = (now - created_at) / 3600

            # Check if within scope window
            if scope == "daily" and age_hours < 24:
                conn.execute("UPDATE sessions SET last_used=? WHERE job=? AND scope=?",
                             (now, job_name, scope))
                conn.commit()
                return session_id
            elif scope == "weekly" and age_hours < 168:  # 7 days
                conn.execute("UPDATE sessions SET last_used=? WHERE job=? AND scope=?",
                             (now, job_name, scope))
                conn.commit()
                return session_id
            elif scope == "persistent":
                conn.execute("UPDATE sessions SET last_used=? WHERE job=? AND scope=?",
                             (now, job_name, scope))
                conn.commit()
                return session_id
            else:
                # Expired — delete and create new
                conn.execute("DELETE FROM sessions WHERE job=? AND scope=?", (job_name, scope))
                conn.commit()

        # Create new session via claude CLI
        import subprocess
        # Start a minimal session to get a session ID
        result = subprocess.run(
            ["claude", "--print", f"Session start for {job_name} {scope} {datetime.now(WITA).strftime('%Y-%m-%d')}"],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, "ANTHROPIC_API_KEY": ""},
        )
        # Extract session ID from output (claude CLI outputs session_id in metadata)
        import re
        session_match = re.search(r'session[_-]?id["\s:]+([a-f0-9-]{36})', result.stdout + result.stderr, re.IGNORECASE)
        if not session_match:
            # Try environment variable approach
            env_result = subprocess.run(
                ["claude", "--print", "--output-format=json", f"Session init {job_name}"],
                capture_output=True, text=True, timeout=30,
                env={**os.environ, "ANTHROPIC_API_KEY": ""},
            )
            try:
                data = json.loads(env_result.stdout)
                session_id = data.get("session_id") or data.get("sessionId")
            except Exception:
                session_id = None
        else:
            session_id = session_match.group(1)

        if session_id:
            conn.execute(
                "INSERT OR REPLACE INTO sessions (job, scope, session_id, created_at, last_used) VALUES (?,?,?,?,?)",
                (job_name, scope, session_id, now, now)
            )
            conn.commit()

        conn.close()
        return session_id

    except Exception as e:
        structlog.get_logger("sessions").warning("session_error", job=job_name, error=str(e))
        return None


def save_session(job_name: str, session_id: str, scope: str = "daily") -> None:
    """Manually save a session ID (call after a successful claude run to capture its session_id)."""
    import sqlite3
    try:
        conn = _sessions_db()
        now = int(time.time())
        conn.execute(
            "INSERT OR REPLACE INTO sessions (job, scope, session_id, created_at, last_used) VALUES (?,?,?,?,?)",
            (job_name, scope, session_id, now, now)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        structlog.get_logger("sessions").warning("session_save_error", job=job_name, error=str(e))


def get_latest_session(
    job_name: str,
    max_age_hours: int = 2,
    scope_prefix: str | None = None,
) -> str | None:
    """Return the most recent session_id for `job_name` within max_age_hours.

    Used to fork a prior synthesize() run and inherit its prompt cache.
    Caller passes the returned id as `fork_from_session` to claude_synthesize.

    Args:
        job_name: the cron agent name.
        max_age_hours: ignore sessions older than this (default 2h — matches
          Anthropic prompt cache 1h TTL plus a grace window).
        scope_prefix: optional filter (e.g. "synth-hourly:" to only get
          synthesize-originated sessions).

    Returns:
        Latest session_id or None if no fresh session exists.
    """
    import sqlite3
    try:
        conn = _sessions_db()
        now = int(time.time())
        cutoff = now - max_age_hours * 3600
        if scope_prefix:
            row = conn.execute(
                "SELECT session_id, created_at FROM sessions "
                "WHERE job=? AND scope LIKE ? AND created_at >= ? "
                "ORDER BY created_at DESC LIMIT 1",
                (job_name, f"{scope_prefix}%", cutoff),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT session_id, created_at FROM sessions "
                "WHERE job=? AND created_at >= ? "
                "ORDER BY created_at DESC LIMIT 1",
                (job_name, cutoff),
            ).fetchone()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        structlog.get_logger("sessions").debug("latest_session_error", job=job_name, error=str(e))
        return None


# ─── WebSearch / WebFetch helpers ──────────────────────────────────────────
# Fallback chain: Brave Search API → DuckDuckGo HTML
# Brave API key loaded from secrets (BRAVE_API_KEY).
# Cache: Redis key `bz:websearch:<hash>` with 24h TTL.

_BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
_DDG_SEARCH_URL = "https://html.duckduckgo.com/html/"
_SEARCH_CACHE_TTL = 86400  # 24h


def _search_cache_key(query: str) -> str:
    return f"bz:websearch:{hashlib.md5(query.encode()).hexdigest()[:12]}"


async def web_search(
    query: str,
    count: int = 5,
    freshness: str | None = None,
    logger: Any = None,
) -> list[dict]:
    """Search the web via Brave API → DuckDuckGo fallback.

    Returns list of dicts with keys: title, url, description.
    Results cached in Redis for 24h (same query = 0 API calls).

    Args:
        query: Search query string.
        count: Max results to return (1-10).
        freshness: Optional time filter — "pd" (past day), "pw" (past week),
                   "pm" (past month), "py" (past year).
        logger: Optional structlog logger for debug output.

    Geographic note: Brave API has global coverage including Indonesia (.id).
    DuckDuckGo fallback is also global.
    """
    import subprocess
    log = logger or structlog.get_logger("web_search")
    cache_key = _search_cache_key(f"{query}:{count}:{freshness}")

    # Check Redis cache first
    try:
        cached = subprocess.run(
            ["redis-cli", "GET", cache_key],
            capture_output=True, text=True, timeout=3
        )
        if cached.returncode == 0 and cached.stdout.strip() not in ("", "(nil)"):
            results = json.loads(cached.stdout.strip())
            log.debug("web_search_cache_hit", query=query[:50], results=len(results))
            return results
    except Exception:
        pass

    # Try Brave Search API
    brave_key = os.environ.get("BRAVE_API_KEY", "")
    results: list[dict] = []

    if brave_key:
        try:
            params: dict = {"q": query, "count": min(count, 10)}
            if freshness:
                params["freshness"] = freshness
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(
                    _BRAVE_SEARCH_URL,
                    params=params,
                    headers={
                        "Accept": "application/json",
                        "Accept-Encoding": "gzip",
                        "X-Subscription-Token": brave_key,
                    },
                )
                if r.status_code == 200:
                    data = r.json()
                    web_results = data.get("web", {}).get("results", [])
                    results = [
                        {
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "description": item.get("description", ""),
                            "source": "brave",
                        }
                        for item in web_results[:count]
                    ]
                    log.debug("web_search_brave_ok", query=query[:50], results=len(results))
                elif r.status_code == 429:
                    log.warning("web_search_brave_rate_limit", query=query[:50])
        except Exception as e:
            log.warning("web_search_brave_error", error=str(e))

    # Fallback: DuckDuckGo HTML
    if not results:
        try:
            import re
            # TLS verification stays ON. This fallback's HTML is parsed into
            # search results that are fed straight into LLM synthesis prompts,
            # so a MITM here is a prompt-injection channel into an unattended
            # agent. `verify=False` bought nothing: probed 3x on Pro 2026-07-25,
            # verified and unverified returned identical status/bytes.
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                r = await client.post(
                    _DDG_SEARCH_URL,
                    data={"q": query},
                    headers={
                        "User-Agent": "Mozilla/5.0 (compatible; NuzantaraCron/1.0)",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )
                html = r.text
                # Parse DDG HTML results
                result_pattern = re.compile(
                    r'class="result__title".*?<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>'
                    r'.*?class="result__snippet"[^>]*>(.*?)</(?:a|span|div)>',
                    re.DOTALL | re.IGNORECASE,
                )
                for m in result_pattern.finditer(html[:100000]):
                    url = m.group(1)
                    title = re.sub(r'<[^>]+>', '', m.group(2)).strip()
                    desc = re.sub(r'<[^>]+>', '', m.group(3)).strip()
                    desc = re.sub(r'\s+', ' ', desc)
                    if url and title and len(results) < count:
                        results.append({
                            "title": title[:200],
                            "url": url,
                            "description": desc[:400],
                            "source": "ddg",
                        })
            log.debug("web_search_ddg_ok", query=query[:50], results=len(results))
        except Exception as e:
            log.warning("web_search_ddg_error", error=str(e))

    # Cache results in Redis
    if results:
        try:
            subprocess.run(
                ["redis-cli", "SET", cache_key, json.dumps(results), "EX", str(_SEARCH_CACHE_TTL)],
                capture_output=True, timeout=3
            )
        except Exception:
            pass

    return results


async def web_fetch(
    url: str,
    extract_text: bool = True,
    timeout: float = 15.0,
    logger: Any = None,
) -> dict:
    """Fetch a URL and return HTML/text content.

    Args:
        url: URL to fetch.
        extract_text: If True, strip HTML tags and return clean text.
        timeout: HTTP timeout in seconds.
        logger: Optional structlog logger.

    Returns:
        Dict with: url, status, html (raw), text (clean), error.
    """
    import re
    log = logger or structlog.get_logger("web_fetch")
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            r = await client.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; NuzantaraCron/1.0)"},
            )
            html = r.text
            text = ""
            if extract_text:
                # Remove scripts, styles, then strip tags
                text = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r'<[^>]+>', ' ', text)
                text = re.sub(r'\s+', ' ', text).strip()
            return {
                "url": str(r.url),
                "status": r.status_code,
                "ok": 200 <= r.status_code < 300,
                "html": html[:50000],
                "text": text[:20000] if extract_text else "",
            }
    except Exception as e:
        log.warning("web_fetch_error", url=url, error=str(e))
        return {"url": url, "status": 0, "ok": False, "html": "", "text": "", "error": str(e)}
