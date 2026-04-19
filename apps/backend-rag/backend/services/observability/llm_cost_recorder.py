"""LLM cost recorder — indestructible triple-write ledger.

Every LLM call in the backend (and any Pro/Air cron that calls the
``/api/admin/llm-costs/record`` endpoint) funnels through
:func:`record_llm_call`. The recorder writes the same event to three
places in parallel; each write is independent, so the failure of one
does NOT prevent the others from landing:

1. **Prometheus counters** (``zantara_llm_prompt_tokens_total``,
   ``zantara_llm_completion_tokens_total``, ``zantara_llm_cost_usd_total``)
   — real-time dashboards.
2. **Postgres table** ``llm_cost_events`` (see migration 112) —
   queryable audit trail, per-endpoint aggregation, reconciliation with
   provider invoices.
3. **JSONL append-only log** on the Fly ``/data`` volume, rotated
   daily (``/data/llm_cost_log.YYYY-MM-DD.jsonl``) — last-resort record
   that survives DB outages and OOM kills. An O_APPEND + fsync write is
   atomic at the POSIX level on modern filesystems for payloads under
   PIPE_BUF (4 KiB); our events are ~400 bytes, well under that bound.

If ALL THREE fail, the call logs a CRITICAL warning but does NOT raise:
we never want cost tracking to break an actual user-facing response.

Project policy:
- ``memory/feedback_claude_oauth_only.md`` — no ANTHROPIC_API_KEY.
- ``memory/feedback_claude_cli_linux_hang.md`` — Claude CLI path is
  broken on Fly; this module still records whatever the CLI reports.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Default JSONL root. Fly api process mounts /data as a persistent volume
# (see fly.toml [mounts]). Override via env for local dev / tests.
JSONL_ROOT: Final[Path] = Path(
    os.getenv("LLM_COST_JSONL_ROOT", "/data"),
)
JSONL_FILENAME_TEMPLATE: Final[str] = "llm_cost_log.{date}.jsonl"

# Retention: we keep rotated files locally for this many days.
# Older files are still queryable from Postgres; the JSONL is only
# "last resort" when DB is down.
DEFAULT_RETENTION_DAYS: Final[int] = int(
    os.getenv("LLM_COST_JSONL_RETENTION_DAYS", "90"),
)


# ---------------------------------------------------------------------------
# Event model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LLMCallEvent:
    """One LLM call worth recording.

    All fields are required except where a default is given. The
    recorder does NOT validate pricing — callers are expected to
    compute ``cost_usd`` using :mod:`backend.services.llm_clients.pricing`.
    """

    provider: str            # 'gemini' | 'deepseek' | 'claude_oauth' | 'openrouter' | …
    model: str               # exact slug the provider sees
    input_tokens: int
    output_tokens: int
    cost_usd: float
    success: bool
    latency_ms: int
    endpoint: str | None = None           # caller module, e.g. 'article_composer'
    request_id: str | None = None         # correlation id if available
    error_class: str | None = None        # populated when success=False
    cache_hit_tokens: int = 0
    ts_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_json_dict(self) -> dict[str, Any]:
        """Serialise to JSON-safe dict (datetime → ISO string)."""
        d = asdict(self)
        d["ts_utc"] = self.ts_utc.isoformat()
        return d


# ---------------------------------------------------------------------------
# Recorder
# ---------------------------------------------------------------------------


class LLMCostRecorder:
    """Singleton that handles the triple-write. Never raises to callers."""

    def __init__(
        self,
        *,
        jsonl_root: Path = JSONL_ROOT,
        retention_days: int = DEFAULT_RETENTION_DAYS,
    ) -> None:
        self.jsonl_root = jsonl_root
        self.retention_days = retention_days
        self._jsonl_lock = asyncio.Lock()
        self._jsonl_ready: bool | None = None  # tri-state: None=unchecked, True=ok, False=unavailable

        # Lazy refs so import-time cycles stay impossible.
        self._pg_pool_getter = None
        self._prom_metrics = None

    # -------- setup -------------------------------------------------------

    async def _ensure_jsonl_dir(self) -> bool:
        """Ensure the JSONL output directory exists and is writable.

        Returns True on success. On failure, caches False to avoid spamming
        filesystem errors on every call; a process restart re-probes.
        """
        if self._jsonl_ready is not None:
            return self._jsonl_ready
        try:
            self.jsonl_root.mkdir(parents=True, exist_ok=True)
            probe = self.jsonl_root / ".llm_cost_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            self._jsonl_ready = True
        except OSError as exc:
            logger.error(
                "⚠️ LLM cost JSONL root %s is not writable: %s — "
                "JSONL persistence disabled for this process",
                self.jsonl_root,
                exc,
            )
            self._jsonl_ready = False
        return self._jsonl_ready

    # -------- persistence sinks ------------------------------------------

    def _current_jsonl_path(self, event: LLMCallEvent) -> Path:
        date_str = event.ts_utc.strftime("%Y-%m-%d")
        return self.jsonl_root / JSONL_FILENAME_TEMPLATE.format(date=date_str)

    async def _write_jsonl(self, event: LLMCallEvent) -> None:
        if not await self._ensure_jsonl_dir():
            raise OSError(
                f"JSONL root {self.jsonl_root} is not writable",
            )
        line = json.dumps(event.to_json_dict(), ensure_ascii=False) + "\n"
        path = self._current_jsonl_path(event)
        # O_APPEND + fsync is the POSIX-atomic recipe for a single line
        # under PIPE_BUF. We serialise with a lock so the per-line fsync
        # stays cheap even under high concurrency.
        async with self._jsonl_lock:
            try:
                fd = await asyncio.to_thread(
                    os.open,
                    str(path),
                    os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                    0o640,
                )
                try:
                    await asyncio.to_thread(os.write, fd, line.encode("utf-8"))
                    await asyncio.to_thread(os.fsync, fd)
                finally:
                    await asyncio.to_thread(os.close, fd)
            except OSError as exc:
                logger.error("⚠️ JSONL write failed for %s: %s", path, exc)
                raise

    async def _write_postgres(self, event: LLMCallEvent) -> None:
        # Lazy import to avoid pulling in asyncpg at module load (tests).
        from backend.app.core.database import get_db_pool

        pool = await get_db_pool()
        if pool is None:
            raise RuntimeError("db pool not initialised")
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO llm_cost_events (
                    ts_utc, provider, model,
                    input_tokens, output_tokens, cache_hit_tokens, cost_usd,
                    endpoint, request_id, success, error_class, latency_ms
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                """,
                event.ts_utc,
                event.provider,
                event.model,
                event.input_tokens,
                event.output_tokens,
                event.cache_hit_tokens,
                event.cost_usd,
                event.endpoint,
                event.request_id,
                event.success,
                event.error_class,
                event.latency_ms,
            )

    def _write_prometheus(self, event: LLMCallEvent) -> None:
        # Lazy import to avoid circular dependency with app/metrics.py.
        from backend.app import metrics as m

        endpoint_label = event.endpoint or "unknown"
        m.llm_prompt_tokens.labels(
            model=event.model,
            endpoint=endpoint_label,
        ).inc(event.input_tokens)
        m.llm_completion_tokens.labels(
            model=event.model,
            endpoint=endpoint_label,
        ).inc(event.output_tokens)
        m.llm_cost_usd.labels(model=event.model).inc(event.cost_usd)
        # Feed the request-size histogram too.
        if event.input_tokens:
            m.llm_request_tokens.labels(
                model=event.model, type="prompt",
            ).observe(event.input_tokens)
        if event.output_tokens:
            m.llm_request_tokens.labels(
                model=event.model, type="completion",
            ).observe(event.output_tokens)

    # -------- public API --------------------------------------------------

    async def record(self, event: LLMCallEvent) -> dict[str, bool]:
        """Record an LLM call to all three sinks.

        Returns a dict ``{"prometheus": bool, "postgres": bool, "jsonl": bool}``
        indicating which sinks succeeded. Never raises. If all three fail,
        logs a CRITICAL warning so the ops pipeline can alert.
        """
        results: dict[str, bool] = {"prometheus": False, "postgres": False, "jsonl": False}

        # Prometheus is sync and extremely fast; do it inline.
        try:
            self._write_prometheus(event)
            results["prometheus"] = True
        except Exception as exc:  # noqa: BLE001
            logger.warning("prometheus write failed for llm_cost event: %s", exc)

        # Postgres + JSONL run in parallel.
        pg_task = asyncio.create_task(self._write_postgres(event))
        jsonl_task = asyncio.create_task(self._write_jsonl(event))

        pg_err: BaseException | None = None
        jsonl_err: BaseException | None = None
        try:
            await pg_task
            results["postgres"] = True
        except BaseException as exc:  # noqa: BLE001 — catch every failure mode
            pg_err = exc
        try:
            await jsonl_task
            results["jsonl"] = True
        except BaseException as exc:  # noqa: BLE001
            jsonl_err = exc

        if pg_err is not None:
            logger.warning(
                "postgres write failed for llm_cost event (model=%s endpoint=%s): %s",
                event.model,
                event.endpoint,
                pg_err,
            )
        if jsonl_err is not None:
            logger.warning(
                "jsonl write failed for llm_cost event (model=%s endpoint=%s): %s",
                event.model,
                event.endpoint,
                jsonl_err,
            )

        if not any(results.values()):
            logger.critical(
                "🚨 ALL THREE llm_cost sinks failed for event "
                "(provider=%s model=%s endpoint=%s cost=$%.6f) — "
                "COST TRACKING GAP, check Prometheus/Postgres/JSONL health",
                event.provider,
                event.model,
                event.endpoint,
                event.cost_usd,
            )

        return results


# ---------------------------------------------------------------------------
# Module-level singleton + convenience wrapper
# ---------------------------------------------------------------------------

_recorder: LLMCostRecorder | None = None


def get_llm_cost_recorder() -> LLMCostRecorder:
    """Return the process-wide recorder singleton."""
    global _recorder
    if _recorder is None:
        _recorder = LLMCostRecorder()
    return _recorder


async def record_llm_call(
    *,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    success: bool,
    latency_ms: int,
    endpoint: str | None = None,
    request_id: str | None = None,
    error_class: str | None = None,
    cache_hit_tokens: int = 0,
) -> dict[str, bool]:
    """Record one LLM call. Thin convenience wrapper over the singleton.

    Example:
        >>> t0 = time.monotonic()
        >>> try:
        ...     resp = await client.post(...)
        ...     success = True
        ...     err = None
        ... except Exception as exc:
        ...     resp = None
        ...     success = False
        ...     err = type(exc).__name__
        ...     raise
        ... finally:
        ...     await record_llm_call(
        ...         provider="deepseek", model="deepseek-chat",
        ...         input_tokens=..., output_tokens=..., cost_usd=...,
        ...         success=success, latency_ms=int((time.monotonic()-t0)*1000),
        ...         endpoint="article_composer", error_class=err,
        ...     )
    """
    event = LLMCallEvent(
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        success=success,
        latency_ms=latency_ms,
        endpoint=endpoint,
        request_id=request_id,
        error_class=error_class,
        cache_hit_tokens=cache_hit_tokens,
    )
    return await get_llm_cost_recorder().record(event)
