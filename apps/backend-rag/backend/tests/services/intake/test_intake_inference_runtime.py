"""Admission-control tests for the shared Intake Ollama runtime."""

from __future__ import annotations

import asyncio

from backend.services.intake import inference_runtime


async def test_default_gate_serialises_model_calls(monkeypatch) -> None:
    monkeypatch.delenv("INTAKE_OLLAMA_MAX_INFLIGHT", raising=False)
    inference_runtime.clear_ollama_inference_gates()
    active = 0
    peak = 0

    async def _call() -> None:
        nonlocal active, peak
        async with inference_runtime.ollama_inference_slot(
            operation="test",
            model="synthetic",
        ):
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1

    await asyncio.gather(*(_call() for _ in range(6)))

    assert peak == 1


async def test_configured_gate_allows_bounded_parallelism(monkeypatch) -> None:
    monkeypatch.setenv("INTAKE_OLLAMA_MAX_INFLIGHT", "2")
    inference_runtime.clear_ollama_inference_gates()
    active = 0
    peak = 0

    async def _call() -> None:
        nonlocal active, peak
        async with inference_runtime.ollama_inference_slot(
            operation="test",
            model="synthetic",
        ):
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1

    await asyncio.gather(*(_call() for _ in range(8)))

    assert peak == 2


def test_invalid_gate_configuration_fails_safe(monkeypatch) -> None:
    monkeypatch.setenv("INTAKE_OLLAMA_MAX_INFLIGHT", "not-an-int")
    assert inference_runtime.ollama_max_inflight() == 1


def test_keep_alive_has_safe_default_and_override(monkeypatch) -> None:
    monkeypatch.delenv("INTAKE_OLLAMA_KEEP_ALIVE", raising=False)
    assert inference_runtime.ollama_keep_alive() == "5s"
    monkeypatch.setenv("INTAKE_OLLAMA_KEEP_ALIVE", "30m")
    assert inference_runtime.ollama_keep_alive() == "30m"
