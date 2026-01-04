import runpy
import sys
import types

import pytest


class DummyResult:
    def __init__(self, status, score, reasoning):
        self.status = status
        self.score = score
        self.reasoning = reasoning


class DummyVerificationService:
    def __init__(self):
        self.calls = []

    async def verify_response(self, question, draft, context):
        self.calls.append((question, draft, context))
        if "Orbital" in draft:
            return DummyResult("fail", 0.1, "hallucination")
        return DummyResult("ok", 0.9, "grounded")


def _install_dummy_verification_service():
    services_module = types.ModuleType("services")
    rag_module = types.ModuleType("services.rag")
    verification_module = types.ModuleType("services.rag.verification_service")
    verification_module.verification_service = DummyVerificationService()

    sys.modules.setdefault("services", services_module)
    sys.modules.setdefault("services.rag", rag_module)
    sys.modules["services.rag.verification_service"] = verification_module

    return verification_module.verification_service


@pytest.mark.asyncio
async def test_verifier_outputs(capsys):
    dummy = _install_dummy_verification_service()

    import verify_draft_pattern

    await verify_draft_pattern.test_verifier()
    output = capsys.readouterr().out
    assert "Good Draft check" in output
    assert "Bad Draft check" in output
    assert len(dummy.calls) == 2


def test_main_runs():
    _install_dummy_verification_service()

    called = {"ran": False}

    def run_coroutine(coro):
        called["ran"] = True
        coro.close()
        return None

    from unittest.mock import patch

    with patch("asyncio.run", side_effect=run_coroutine):
        runpy.run_module("verify_draft_pattern", run_name="__main__")

    assert called["ran"] is True
