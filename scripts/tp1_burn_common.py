#!/usr/bin/env python3
"""Shared guard/window helpers for the 2026-10 TP1 quota-burn runners.

The fleet cost_breaker deliberately leaves provider ``deepseek`` (the TP1 door)
UNGUARDED — flat subscription, zero marginal cost, same posture as kimi/ollama
(see ``cost_breaker.GUARDED_PROVIDERS``; the retired metered DeepSeek door's
$5 slot was not carried forward). The burn's guard therefore lives HERE: a hard
per-run token/call cap, fail-closed, on top of the 12h console-% checkpoint
loop in research/operations/2026-10-05-tp1-burn-task-brief.md. Ledger
visibility is untouched: every call still goes through
``deepseek_client.complete`` -> ``log_cost_event``.
"""
from __future__ import annotations

import os
import threading
from datetime import datetime, timedelta, timezone

WITA = timezone(timedelta(hours=8))


def is_night_wita(now: datetime | None = None) -> bool:
    """Night window 22:00-08:00 WITA (= UTC+8 night, qwen3.8-max Night 50% Off)."""
    now = now or datetime.now(WITA)
    return now.hour >= 22 or now.hour < 8


def window_model() -> str:
    """qwen3.8-max at night (discount), qwen3.7-plus by day, env-overridable."""
    if is_night_wita():
        return os.environ.get("BURN_NIGHT_MODEL", "qwen3.8-max")
    return os.environ.get("BURN_DAY_MODEL", "qwen3.7-plus")


def window_effort() -> str:
    return "high" if is_night_wita() else "low"


class BurnGuard:
    """Hard per-run caps; fail-closed. ``add`` returns False once exceeded."""

    def __init__(self, max_tokens: int | None = None, max_calls: int | None = None) -> None:
        self.max_tokens = int(
            max_tokens if max_tokens is not None
            else os.environ.get("BURN_MAX_TOKENS", "40000000")
        )
        self.max_calls = int(
            max_calls if max_calls is not None
            else os.environ.get("BURN_MAX_CALLS", "200000")
        )
        self._lock = threading.Lock()
        self.tokens = 0
        self.calls = 0

    def _over(self) -> bool:
        return self.tokens >= self.max_tokens or self.calls >= self.max_calls

    def add(self, usage: dict) -> bool:
        total = int(usage.get("total_tokens") or 0) or (
            int(usage.get("prompt_tokens") or 0) + int(usage.get("completion_tokens") or 0)
        )
        with self._lock:
            self.tokens += total
            self.calls += 1
            return not self._over()

    def ok(self) -> bool:
        with self._lock:
            return not self._over()

    def stats(self) -> dict:
        with self._lock:
            return {
                "tokens": self.tokens,
                "calls": self.calls,
                "cap_tokens": self.max_tokens,
                "cap_calls": self.max_calls,
            }
