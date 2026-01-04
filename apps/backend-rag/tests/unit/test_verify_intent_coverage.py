import runpy
import sys
import types
from unittest.mock import patch

import pytest
import verify_intent


def _install_intent_classifier(classify_impl):
    services_module = types.ModuleType("services")
    classification_module = types.ModuleType("services.classification")
    intent_module = types.ModuleType("services.classification.intent_classifier")

    class IntentClassifier:
        async def classify_intent(self, query):
            return await classify_impl(query)

    intent_module.IntentClassifier = IntentClassifier
    sys.modules.setdefault("services", services_module)
    sys.modules.setdefault("services.classification", classification_module)
    sys.modules["services.classification.intent_classifier"] = intent_module


@pytest.mark.asyncio
async def test_intent_success(capsys):
    async def classify_impl(_query):
        return "visa"

    _install_intent_classifier(classify_impl)
    await verify_intent.test_intent()
    output = capsys.readouterr().out
    assert "Intent Classified" in output


@pytest.mark.asyncio
async def test_intent_timeout(capsys):
    async def classify_impl(_query):
        return "visa"

    _install_intent_classifier(classify_impl)

    import asyncio

    async def raise_timeout(coro, timeout=None):
        coro.close()
        raise asyncio.TimeoutError

    with patch("verify_intent.asyncio.wait_for", side_effect=raise_timeout):
        await verify_intent.test_intent()
    output = capsys.readouterr().out
    assert "IntentClassifier TIMED OUT" in output


@pytest.mark.asyncio
async def test_intent_exception(capsys):
    async def classify_impl(_query):
        raise RuntimeError("boom")

    _install_intent_classifier(classify_impl)
    await verify_intent.test_intent()
    output = capsys.readouterr().out
    assert "IntentClassifier Failed: boom" in output


def test_main_runs():
    async def classify_impl(_query):
        return "visa"

    _install_intent_classifier(classify_impl)
    called = {"ran": False}

    def run_coroutine(coro):
        called["ran"] = True
        coro.close()
        return None

    with patch("asyncio.run", side_effect=run_coroutine):
        runpy.run_module("verify_intent", run_name="__main__")

    assert called["ran"] is True
