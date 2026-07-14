#!/usr/bin/env python3
"""Shared DeepSeek client for scripts/ — breaker-guarded, ledger-writing, flash-first.

WHY (smart-spend mandate 2026-07-14): the 30-day DeepSeek bill was $40.03 across
9,428 requests, 96% of it ``deepseek-v4-pro`` called RAW from campaign scripts
(curl/httpx straight to api.deepseek.com). Those callers were LEDGER-BLIND: the
already-shipped ``scripts/cost_breaker.py`` guard (provider "deepseek", default
budget $5/24h, DEGRADE at 85%) could never see or stop them, because nobody
wrote cost events and nobody consulted the breaker. This module is the missing
consumer side of that contract:

  1. DEFAULT MODEL IS CHEAP: ``deepseek-v4-flash`` unless the caller (or the
     ``DEEPSEEK_MODEL`` env) explicitly asks for ``deepseek-v4-pro``. Bulk
     passes get flash; pro is an opt-in per run, not a hardcoded constant.
  2. EVERY call appends a cost event to the breaker's JSONL ledger
     (``llm_cost_log.{date}.jsonl`` — same schema ``cost_breaker`` sums:
     ts_utc / provider / cost_usd), so the $5/day budget is real.
  3. BEFORE spending it consults ``cost_breaker.decide("deepseek", ...)`` and
     raises on DEGRADE/STOP (fail-closed; ``allow_degrade=True`` lets a caller
     finish a synthesis-grade pass inside the DEGRADE band).

Legacy aliases ``deepseek-chat`` / ``deepseek-reasoner`` are REJECTED: they
return 200 but silently route to flash (cicatrix 2026-05-24) — a caller that
thinks it bought pro quality must say so explicitly.

Pricing mirrors ``apps/backend-rag/backend/llm/deepseek_client.py`` (V4 list
prices, 2026-04-24 release). It is a governance PROXY for the breaker, not
billing truth — DeepSeek's invoice is authoritative.

Stdlib-only on purpose (urllib, no httpx/requests): campaign scripts and
launchd wrappers run outside any venv on M5/Pro/Mini.

Usage (sync scripts):
    from deepseek_client import complete
    text = complete("prompt", system="...", purpose="kbli-l3")          # flash
    text = complete("prompt", model="deepseek-v4-pro", purpose="quote")  # opt-in pro

Async callers (tri-LLM panel, devils-advocate) keep their own httpx call and
integrate the two halves separately:
    verdict = await budget_verdict_async()   # skip the seat on DEGRADE/STOP
    log_cost_event(model, usage_dict, purpose="tri-llm-review")  # after the call

CLI:
    python scripts/deepseek_client.py --status
    python scripts/deepseek_client.py --prompt "ping" [--model deepseek-v4-pro]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

# Make sibling scripts/ modules importable regardless of invocation cwd.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import cost_breaker  # noqa: E402

API_URL = "https://api.deepseek.com/v1/chat/completions"
PROVIDER = "deepseek"

DEFAULT_MODEL = "deepseek-v4-flash"
PRO_MODEL = "deepseek-v4-pro"

#: Aliases that still answer 200 OK but silently serve V4-Flash (2026-05-24 trap).
LEGACY_ALIASES = frozenset({"deepseek-chat", "deepseek-reasoner"})

#: USD per 1M tokens: (input cache-miss, input cache-hit, output).
#: Mirrors apps/backend-rag/backend/llm/deepseek_client.py (V4 list prices).
PRICES_PER_MTOK: dict[str, tuple[float, float, float]] = {
    PRO_MODEL: (0.435, 0.435, 0.87),
    DEFAULT_MODEL: (0.14, 0.0028, 0.28),
}

_SECRET_FILES = (
    Path.home() / ".openclaw" / "workspace" / ".env.master",
    Path.home() / ".nuzantara-secrets.env",
)

_verdict_lock = threading.Lock()
_verdict_cache: dict[str, Any] = {"ts": 0.0, "decision": None}


class DeepSeekError(RuntimeError):
    """Base error for this client."""


class DeepSeekBudgetExceeded(DeepSeekError):
    """cost_breaker said DEGRADE/STOP for provider deepseek — call refused."""

    def __init__(self, decision: Any) -> None:
        self.decision = decision
        verdict = getattr(decision, "verdict", decision)
        spend = getattr(decision, "spend_usd", "?")
        super().__init__(
            f"deepseek budget breaker: {verdict} (window spend ${spend}) — "
            "call refused. Raise COST_BREAKER_BUDGET_DEEPSEEK_USD deliberately "
            "or wait for the window to roll."
        )


class DeepSeekBalanceDead(DeepSeekError):
    """HTTP 402 Insufficient Balance — top-up is an operator[business] action."""


def resolve_model(model: str | None = None) -> str:
    """Explicit arg > DEEPSEEK_MODEL env > flash. Legacy aliases refused."""
    resolved = (model or os.environ.get("DEEPSEEK_MODEL") or DEFAULT_MODEL).strip()
    if resolved in LEGACY_ALIASES:
        raise DeepSeekError(
            f"model {resolved!r} is a legacy alias that SILENTLY serves V4-Flash "
            f"(2026-05-24 trap). Say {DEFAULT_MODEL!r} or {PRO_MODEL!r} explicitly."
        )
    return resolved


def api_key() -> str:
    """DEEPSEEK_API_KEY from env, else the on-disk secret files (launchd has no env)."""
    key = os.environ.get("DEEPSEEK_API_KEY")
    if key:
        return key
    for secrets_path in _SECRET_FILES:
        if not secrets_path.exists():
            continue
        try:
            for line in secrets_path.read_text().splitlines():
                stripped = line.strip()
                if stripped.startswith("export "):
                    stripped = stripped[len("export "):]
                if stripped.startswith("DEEPSEEK_API_KEY="):
                    value = stripped.split("=", 1)[1].strip().strip('"').strip("'")
                    if value:
                        return value
        except OSError:
            continue
    raise DeepSeekError("no DEEPSEEK_API_KEY in env or secret files")


def ledger_root(root: str | Path | None = None) -> Path:
    """Writer's ledger root — MUST match what cost_breaker reads.

    Resolution: explicit arg > LLM_COST_JSONL_ROOT env > /data when it exists
    (Fly volume) > ~/.organism/llm-cost (workstations). The same value is
    passed to the breaker's spend read, so writer and reader agree by
    construction.
    """
    if root is not None:
        return Path(root)
    env_root = os.environ.get("LLM_COST_JSONL_ROOT")
    if env_root:
        return Path(env_root)
    if Path("/data").is_dir():
        return Path("/data")
    return Path.home() / ".organism" / "llm-cost"


def ensure_ledger(root: Path) -> Path:
    """Create the ledger dir + today's file so the breaker sees a PRESENT source.

    Without this, the very first run on a machine finds no JSONL for the window
    -> spend UNKNOWN -> fail-closed DEGRADE -> bootstrap deadlock. An existing
    empty file is honest KNOWN-zero.
    """
    root.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).date().isoformat()
    path = root / f"llm_cost_log.{today}.jsonl"
    path.touch(exist_ok=True)
    return path


def estimate_cost_usd(model: str, usage: Mapping[str, Any]) -> float:
    """Cache-hit-aware V4 cost estimate from a response ``usage`` block."""
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or 0)
    cache_hit = int(usage.get("prompt_cache_hit_tokens") or 0)
    model_lc = model.lower()
    key = PRO_MODEL if ("v4-pro" in model_lc or model_lc.endswith("-pro")) else DEFAULT_MODEL
    miss_rate, hit_rate, out_rate = PRICES_PER_MTOK[key]
    cache_miss = max(0, prompt_tokens - cache_hit)
    return (
        cache_miss * miss_rate / 1_000_000
        + cache_hit * hit_rate / 1_000_000
        + completion_tokens * out_rate / 1_000_000
    )


def log_cost_event(
    model: str,
    usage: Mapping[str, Any],
    *,
    purpose: str = "",
    root: str | Path | None = None,
    now: datetime | None = None,
) -> float:
    """Append one cost event to the daily JSONL the breaker sums. Returns cost.

    Schema matches cost_breaker/cost_ledger_export: ts_utc (ISO-8601 str),
    provider (str), cost_usd (float); extra keys are ignored by the reader.
    Never raises on I/O problems — a broken ledger write must not kill the
    caller's run (mirrors the backend recorder's swallow-on-error).
    """
    cost = estimate_cost_usd(model, usage)
    ts = (now or datetime.now(timezone.utc)).isoformat()
    row = {
        "ts_utc": ts,
        "provider": PROVIDER,
        "model": model,
        "cost_usd": round(cost, 8),
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
        "cache_hit_tokens": int(usage.get("prompt_cache_hit_tokens") or 0),
        "purpose": purpose or Path(sys.argv[0]).name,
    }
    try:
        path = ensure_ledger(ledger_root(root))
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as exc:  # pragma: no cover - defensive
        print(f"deepseek_client: ledger write failed ({exc})", file=sys.stderr)
    return cost


async def budget_verdict_async(
    *,
    root: str | Path | None = None,
    now: datetime | None = None,
) -> Any:
    """Consult the breaker for provider deepseek (async callers: tri-LLM etc.)."""
    resolved_root = ledger_root(root)
    ensure_ledger(resolved_root)
    config = cost_breaker.BreakerConfig.from_env()
    spend = await cost_breaker.provider_spend_in_window(
        PROVIDER,
        config.window_seconds,
        jsonl_root=resolved_root,
        now=now,
    )
    return cost_breaker.decide(PROVIDER, spend, config)


def budget_verdict(
    *,
    root: str | Path | None = None,
    now: datetime | None = None,
) -> Any:
    """Sync wrapper around :func:`budget_verdict_async` for plain scripts."""
    return asyncio.run(budget_verdict_async(root=root, now=now))


def _cached_verdict(root: str | Path | None) -> Any:
    """Breaker verdict with a small TTL cache — bulk loops (ThreadPoolExecutor)
    consult at most every DEEPSEEK_BREAKER_TTL_S seconds (default 30) instead
    of re-reading the ledger per call. A runaway loop is still caught within
    one TTL. Thread-safe."""
    try:
        ttl = float(os.environ.get("DEEPSEEK_BREAKER_TTL_S", "30"))
    except ValueError:
        ttl = 30.0
    with _verdict_lock:
        age = time.monotonic() - _verdict_cache["ts"]
        if _verdict_cache["decision"] is not None and age < ttl:
            return _verdict_cache["decision"]
        decision = budget_verdict(root=root)
        _verdict_cache["ts"] = time.monotonic()
        _verdict_cache["decision"] = decision
        return decision


@dataclass
class DeepSeekResult:
    text: str
    model: str
    usage: dict[str, Any]
    cost_usd: float


def complete(
    user: str,
    *,
    system: str | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    reasoning_effort: str | None = None,
    timeout: int = 120,
    retries: int = 2,
    purpose: str = "",
    allow_degrade: bool = False,
    breaker: bool = True,
    ledger: str | Path | None = None,
) -> DeepSeekResult:
    """One guarded chat completion. Flash by default; pro only if asked.

    Raises DeepSeekBudgetExceeded on breaker DEGRADE/STOP (``allow_degrade=True``
    tolerates DEGRADE), DeepSeekBalanceDead on HTTP 402, DeepSeekError otherwise.
    ``breaker=False`` is an explicit escape hatch for emergencies — the ledger
    is still written so the spend stays visible.
    """
    resolved = resolve_model(model)

    if breaker:
        decision = _cached_verdict(ledger)
        if decision.verdict is cost_breaker.Verdict.STOP or (
            decision.verdict is cost_breaker.Verdict.DEGRADE and not allow_degrade
        ):
            raise DeepSeekBudgetExceeded(decision)

    payload: dict[str, Any] = {
        "model": resolved,
        "stream": False,
        "messages": ([{"role": "system", "content": system}] if system else [])
        + [{"role": "user", "content": user}],
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if temperature is not None:
        payload["temperature"] = temperature
    if reasoning_effort is not None:
        payload["reasoning_effort"] = reasoning_effort

    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key()}",
        },
        method="POST",
    )

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 402:
                raise DeepSeekBalanceDead(
                    "DeepSeek HTTP 402 Insufficient Balance — top-up is "
                    "operator[business] (Zero on platform.deepseek.com)."
                ) from exc
            body = exc.read().decode("utf-8", errors="replace")[:300]
            last_error = DeepSeekError(f"HTTP {exc.code}: {body}")
            if exc.code < 500 and exc.code != 429:
                raise last_error from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = DeepSeekError(f"request failed: {exc}")
        if attempt < retries:
            time.sleep(1.5 * (attempt + 1))
    else:
        raise last_error or DeepSeekError("request failed after retries")

    choices = data.get("choices") or []
    if not choices:
        raise DeepSeekError(f"empty choices: {json.dumps(data)[:300]}")
    text = ((choices[0].get("message") or {}).get("content") or "").strip()
    usage = dict(data.get("usage") or {})
    model_returned = str(data.get("model") or resolved)
    cost = log_cost_event(model_returned, usage, purpose=purpose, root=ledger)
    return DeepSeekResult(text=text, model=model_returned, usage=usage, cost_usd=cost)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--status", action="store_true", help="window spend + verdict")
    parser.add_argument("--prompt", help="one-shot completion")
    parser.add_argument("--model", default=None, help=f"default {DEFAULT_MODEL}")
    parser.add_argument("--purpose", default="cli")
    args = parser.parse_args(argv)

    if args.status:
        decision = budget_verdict()
        print(f"provider={PROVIDER} root={ledger_root()}")
        print(decision)
        return 0
    if args.prompt:
        result = complete(args.prompt, model=args.model, purpose=args.purpose)
        print(result.text)
        print(
            f"[model={result.model} cost=${result.cost_usd:.6f} "
            f"tokens={result.usage.get('total_tokens')}]",
            file=sys.stderr,
        )
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
