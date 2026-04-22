"""L1 Ollama async classifier — buckets event bursts for L2 prompt enrichment.

Uses local `qwen3.5:9b` via `ollama run` shell-out. Fire-and-forget by
design: the Decider does NOT await this; the classifier writes result
to IncidentContext.ollama_bucket asynchronously. L2 Claude CLI reads
whatever bucket is present at that moment (may be None if classifier
hasn't completed yet — that's OK, it's enrichment not gating).

Rationale (from spec §3 W2.B): Ollama latency is 30-120s on local
hardware, which is unacceptable for MTTD <90s. But as enrichment it
costs nothing — if ready in time, great; if not, L2 runs with
ollama_bucket='unknown'.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Iterable

from organism.schemas import Event


log = logging.getLogger(__name__)

VALID_BUCKETS = frozenset({
    "hardware", "deploy", "dependency", "data", "network", "unknown",
})
DEFAULT_BUCKET = "unknown"
CLASSIFIER_TIMEOUT_SECONDS = 120.0  # Ollama qwen3.5:9b realistic upper bound

PROMPT_TEMPLATE = """Classify this event burst into one of: hardware, deploy, dependency, data, network, unknown.

Events ({count}):
{events_summary}

Respond with ONLY the bucket name in lowercase. No punctuation. No other text."""


class OllamaClassifier:
    """L1 classifier — fires a background task that writes result to IncidentContext."""

    def __init__(
        self,
        *,
        incident_store,
        ollama_binary: str = "ollama",
        model: str = "qwen3.5:9b",
    ):
        self.incident_store = incident_store
        self.ollama_binary = ollama_binary
        self.model = model

    def enqueue(self, correlation_id: str, events: list[Event]) -> asyncio.Task:
        """Schedule classification as background task. Returns the task so
        tests can await it. In production, Decider fires-and-forgets."""
        return asyncio.create_task(self._classify_and_persist(correlation_id, events))

    async def _classify_and_persist(
        self, correlation_id: str, events: list[Event],
    ) -> str:
        bucket = await self._classify(events)
        # Persist to IncidentContext
        try:
            ctx = await self.incident_store.hydrate(correlation_id)
            ctx.ollama_bucket = bucket
            await self.incident_store.persist(ctx)
        except Exception:
            log.warning(
                "classifier: failed to persist bucket=%s for correlation=%s",
                bucket, correlation_id,
            )
        return bucket

    async def _classify(self, events: list[Event]) -> str:
        if not events:
            return DEFAULT_BUCKET
        prompt = PROMPT_TEMPLATE.format(
            count=len(events),
            events_summary=self._summarize(events),
        )
        try:
            proc = await asyncio.create_subprocess_exec(
                self.ollama_binary, "run", self.model, prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            log.warning("classifier: ollama binary not found at %s", self.ollama_binary)
            return DEFAULT_BUCKET

        try:
            out_b, _ = await asyncio.wait_for(
                proc.communicate(), timeout=CLASSIFIER_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
                await proc.wait()
            except ProcessLookupError:
                pass
            log.warning("classifier: ollama timeout after %ss", CLASSIFIER_TIMEOUT_SECONDS)
            return DEFAULT_BUCKET

        raw = out_b.decode("utf-8", errors="replace").strip().lower()
        # Model may include trailing punctuation, quotes, etc. — extract first valid bucket.
        first_token = raw.split()[0] if raw else ""
        first_token = first_token.strip(".,!?;:'\"()[]{}")
        if first_token in VALID_BUCKETS:
            return first_token
        # Fallback — scan full response for any valid bucket
        for bucket in VALID_BUCKETS:
            if bucket in raw:
                return bucket
        log.warning("classifier: unrecognized output %r", raw[:100])
        return DEFAULT_BUCKET

    @staticmethod
    def _summarize(events: Iterable[Event]) -> str:
        """One line per event: kind/source/severity/payload-keys."""
        lines = []
        for e in events:
            payload_keys = list(e.payload.keys()) if e.payload else []
            lines.append(
                f"- kind={e.kind} source={e.source} severity={e.severity.value} "
                f"payload_keys={payload_keys}"
            )
        return "\n".join(lines)
