from __future__ import annotations
import time
from typing import Any
import httpx
from pydantic import ValidationError

from cell_observatory.models import (
    ClassificationLabel, ClassificationOutput, ClassificationResult, PulseEventV1
)


class CircuitOpenError(Exception):
    """Raised when MiniMax circuit breaker is open."""


_PROMPT_VERSION = "v1"
_SYSTEM_PROMPT = """You are an SRE classifier for biological-cell-style health pulses.
Given sensor readings + self-classification by the cell, output a JSON with:
- reasoning: 1-2 sentences, what catches your attention or confirms normality
- label: 'normal' | 'anomaly' | 'critical' | 'uncertain'
- confidence: 0.0 to 1.0

Rules:
- 'normal' = sensors within expected band, no trend break
- 'anomaly' = ONE sensor unusual but not failing, OR self-yellow with stable trend
- 'critical' = multi-sensor failure, OR self-red, OR trend break crossing threshold
- 'uncertain' = ambiguous, missing data, never seen pattern

Confidence calibration: 0.9+ only when symptom matches known scar OR signals are unambiguous.

Respond ONLY with valid JSON, no markdown."""


def _render_user_prompt(event: PulseEventV1) -> str:
    sensors_fmt = "\n".join(
        f"- {s.get('name', '?')}: " + ", ".join(f"{k}={v}" for k, v in s.items() if k != "name")
        for s in event.sensors
    ) or "  (no sensors)"
    return (
        f"Cell: {event.cell_id} ({event.cell_kind}, phase={event.phase})\n"
        f"Self-classification: {event.pulse_result.get('classifier_self', '?')}\n"
        f"Sensors:\n{sensors_fmt}\n"
        f"Trend: {event.pulse_result.get('trend_label', '?')} "
        f"over {event.pulse_result.get('trend_window_min', '?')}min\n"
        f"Homeostatic state: energy={event.homeostatic_state.get('energy_pct', '?')}%, "
        f"load={event.homeostatic_state.get('load_factor', '?')}\n\n"
        f"Classify."
    )


class MinimaxClassifier:
    """
    Routes through OpenRouter to minimax/minimax-m2.5:free (Track A activation
    2026-05-02). Original direct minimax.io endpoint had insufficient_balance
    on the user's account; OpenRouter free tier costs zero per call.

    Switch to a paid model (e.g. `minimax/minimax-m2.7` at $0.30/M input,
    $1.20/M output) by overriding MODEL via OBSERVATORY_CLASSIFIER_MODEL env.
    """
    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
    MODEL = "minimax/minimax-m2.5:free"
    # Pricing fields preserved for cost ledger semantics — set to 0 for :free.
    PRICE_INPUT_USD_PER_M = 0.0
    PRICE_OUTPUT_USD_PER_M = 0.0

    def __init__(self, api_key: str, circuit_threshold: int = 5,
                 circuit_recovery_s: float = 60.0):
        self._api_key = api_key
        self._client = httpx.AsyncClient(timeout=10.0)
        self._consecutive_failures = 0
        self._circuit_threshold = circuit_threshold
        self._circuit_open_until: float = 0.0
        self._circuit_recovery_s = circuit_recovery_s

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _call_api(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        resp = await self._client.post(
            self.BASE_URL,
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={"model": self.MODEL, "messages": messages, "temperature": 0.1, "max_tokens": 200},
        )
        resp.raise_for_status()
        return resp.json()

    def _check_circuit(self) -> None:
        if time.monotonic() < self._circuit_open_until:
            raise CircuitOpenError("MiniMax circuit open")

    def _record_success(self) -> None:
        self._consecutive_failures = 0

    def _record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._circuit_threshold:
            self._circuit_open_until = time.monotonic() + self._circuit_recovery_s

    async def classify(self, event: PulseEventV1) -> ClassificationResult:
        self._check_circuit()
        start = time.monotonic()

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _render_user_prompt(event)},
        ]

        try:
            resp = await self._call_api(messages)
        except Exception:
            self._record_failure()
            raise
        self._record_success()

        latency_ms = int((time.monotonic() - start) * 1000)
        content = resp["choices"][0]["message"]["content"]

        try:
            parsed = ClassificationOutput.model_validate_json(content)
        except ValidationError:
            # Retry once (PR #311 pattern); if second fail propagate
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": "Output was not valid JSON. Re-emit ONLY the JSON object."})
            resp2 = await self._call_api(messages)
            content2 = resp2["choices"][0]["message"]["content"]
            parsed = ClassificationOutput.model_validate_json(content2)

        usage = resp.get("usage", {})
        cost = (
            usage.get("prompt_tokens", 0) / 1_000_000 * self.PRICE_INPUT_USD_PER_M
            + usage.get("completion_tokens", 0) / 1_000_000 * self.PRICE_OUTPUT_USD_PER_M
        )

        cell_self = event.pulse_result.get("classifier_self", "unknown")
        label_diff = "agree" if (
            (cell_self == "green" and parsed.label == ClassificationLabel.NORMAL)
            or (cell_self in ("yellow", "red") and parsed.label != ClassificationLabel.NORMAL)
        ) else "disagree"

        return ClassificationResult(
            outbox_id=event.outbox_id,
            label=parsed.label,
            confidence=parsed.confidence,
            reasoning=parsed.reasoning[:500],
            label_diff=label_diff,
            model=f"minimax-m2-{_PROMPT_VERSION}",
            model_version=resp.get("model"),
            cost_usd=round(cost, 6),
            latency_ms=latency_ms,
            error=None,
        )
