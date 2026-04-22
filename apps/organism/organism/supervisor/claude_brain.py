"""L2 Claude CLI brain — shell-out to `claude` CLI with OAuth MAX token.

Golden Rule #13 enforcement:
- Strips `ANTHROPIC_API_KEY` from env before spawn (prevents paid-API escape)
- No `anthropic` SDK import anywhere
- Shell-out only path: `claude -p <prompt> --output-format text`
- The CLI reads `CLAUDE_CODE_OAUTH_TOKEN` from env (OAuth MAX quota, flat-rate)

Called by Decider when L0 YAML has no match AND the event is classifiable
(severity >= warning, not is_actuation, not already in decision cache).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time

from organism.schemas import ActionDecision, Event


log = logging.getLogger(__name__)

RATE_LIMIT_PER_MINUTE = 3
CACHE_KEY_PREFIX = "organism:decision_cache:"
CACHE_TTL = 600  # 10 min
CLAUDE_TIMEOUT_SECONDS = 30.0

TEMPLATE = """You are the Nuzantara organism supervisor. An event needs a decision.

Event kind: {kind}
Source: {source}
Severity: {severity}
Payload (sanitized, structured): {payload_json}
Ollama classifier bucket: {ollama_bucket}
Recent events in same correlation: {recent_events_count}

Available actuators: {available_actuators}

Respond ONLY with a JSON object:
{{"actuator": "<name>", "params": {{...}}, "confidence": 0.0-1.0, "reasoning": "<one sentence>"}}

No other text. No explanation. Just the JSON.
"""


class ClaudeBrain:
    """L2 brain — wraps the claude CLI with cache + rate limit + defer fallbacks."""

    def __init__(self, *, redis, claude_binary: str = "claude"):
        self.redis = redis
        self.claude_binary = claude_binary
        # Rate limit window state: (window_start_ts, calls_in_window)
        self._minute_start = time.time()
        self._calls_this_minute = 0

    async def decide(
        self,
        event: Event,
        *,
        ollama_bucket: str | None,
        recent_events_count: int,
        available_actuators: list[str],
    ) -> ActionDecision:
        # 1. Cache lookup first — burst of identical events hits cache
        cache_key = self._cache_key(event)
        cached_raw = await self.redis.get(cache_key)
        if cached_raw:
            try:
                data = json.loads(
                    cached_raw.decode("utf-8") if isinstance(cached_raw, (bytes, bytearray))
                    else cached_raw
                )
                return ActionDecision(**data)
            except Exception:
                log.warning("decision cache entry malformed, recomputing: key=%s", cache_key)

        # 2. Rate limit check — prevent burst from exhausting MAX quota
        if not self._allow_this_call():
            return ActionDecision(
                actuator="defer_to_human",
                params={"reason": "rate_limit", "limit_per_minute": RATE_LIMIT_PER_MINUTE},
                confidence=0.0,
                tier="L2_claude",
                reasoning=f"claude CLI rate limit {RATE_LIMIT_PER_MINUTE}/min hit",
            )

        # 3. Build prompt with slot-only substitution (no free-form payload echo)
        prompt = TEMPLATE.format(
            kind=event.kind,
            source=event.source,
            severity=event.severity.value,
            payload_json=json.dumps(event.payload, default=str),
            ollama_bucket=ollama_bucket or "unknown",
            recent_events_count=recent_events_count,
            available_actuators=", ".join(available_actuators),
        )

        # 4. Shell-out with ANTHROPIC_API_KEY stripped (Golden Rule #13)
        clean_env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        try:
            proc = await asyncio.create_subprocess_exec(
                self.claude_binary,
                "-p", prompt,
                "--output-format", "text",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=clean_env,
            )
        except FileNotFoundError:
            return ActionDecision(
                actuator="defer_to_human",
                params={"reason": "claude_cli_not_found", "binary": self.claude_binary},
                confidence=0.0,
                tier="L2_claude",
                reasoning=f"claude CLI binary not found at {self.claude_binary}",
            )

        try:
            out_b, err_b = await asyncio.wait_for(
                proc.communicate(), timeout=CLAUDE_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
                await proc.wait()
            except ProcessLookupError:
                pass
            return ActionDecision(
                actuator="defer_to_human",
                params={"reason": "timeout", "seconds": CLAUDE_TIMEOUT_SECONDS},
                confidence=0.0,
                tier="L2_claude",
                reasoning=f"claude CLI timeout {CLAUDE_TIMEOUT_SECONDS}s",
            )

        out = out_b.decode("utf-8", errors="replace").strip()

        # 5. Parse JSON response
        try:
            data = json.loads(out)
            decision = ActionDecision(
                actuator=data["actuator"],
                params=data.get("params", {}),
                confidence=float(data.get("confidence", 0.5)),
                tier="L2_claude",
                reasoning=data.get("reasoning"),
            )
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
            return ActionDecision(
                actuator="defer_to_human",
                params={"reason": "parse_error", "raw_output": out[:500]},
                confidence=0.0,
                tier="L2_claude",
                reasoning=f"failed to parse claude output as JSON: {exc}",
            )

        # 6. Cache the decision
        try:
            await self.redis.set(cache_key, decision.model_dump_json(), ex=CACHE_TTL)
        except Exception:
            log.warning("decision cache write failed (non-fatal)")
        return decision

    def _cache_key(self, event: Event) -> str:
        """Stable cache key per (kind, source, sorted payload) triple."""
        payload_items = sorted(event.payload.items()) if event.payload else []
        material = f"{event.kind}|{event.source}|{payload_items}"
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
        return CACHE_KEY_PREFIX + digest

    def _allow_this_call(self) -> bool:
        """Fixed-window rate limit: max N calls per 60s tumbling window.

        Note: instance-level state — multiple ClaudeBrain instances do not
        coordinate. W2 runs a single Supervisor; W3 wiring should consider
        Redis-backed rate limit if multi-Supervisor is introduced.
        """
        now = time.time()
        if now - self._minute_start >= 60:
            self._minute_start = now
            self._calls_this_minute = 0
        if self._calls_this_minute >= RATE_LIMIT_PER_MINUTE:
            return False
        self._calls_this_minute += 1
        return True
