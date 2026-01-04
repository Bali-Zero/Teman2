import importlib
import os
import runpy
import sys
import types
from unittest.mock import patch

import pytest


def _install_stubs(*, genai_available=True, is_available=True, response_text=""):
    dotenv_module = types.ModuleType("dotenv")
    dotenv_module.load_dotenv = lambda override=True: None

    llm_module = types.ModuleType("llm")
    genai_module = types.ModuleType("llm.genai_client")

    class GenAIClient:
        def __init__(self, api_key):
            self.is_available = is_available

        async def generate_content(self, contents, model, max_output_tokens):
            return {"text": response_text}

    genai_module.GENAI_AVAILABLE = genai_available
    genai_module.GenAIClient = GenAIClient

    services_module = types.ModuleType("services")
    rag_module = types.ModuleType("services.rag")
    agentic_module = types.ModuleType("services.rag.agentic")
    agentic_module.AgenticRAGOrchestrator = object

    prompts_module = types.ModuleType("prompts")
    persona_module = types.ModuleType("prompts.jaksel_persona")
    persona_module.SYSTEM_INSTRUCTION = "STRAIGHT TO THE POINT"

    sys.modules.update(
        {
            "dotenv": dotenv_module,
            "llm": llm_module,
            "llm.genai_client": genai_module,
            "services": services_module,
            "services.rag": rag_module,
            "services.rag.agentic": agentic_module,
            "prompts": prompts_module,
            "prompts.jaksel_persona": persona_module,
        }
    )


def test_import_raises_without_api_key():
    _install_stubs(genai_available=False)
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError):
            runpy.run_module("verify_soul_persona", run_name="__main__")


def test_import_raises_on_genai_init_failure():
    _install_stubs(genai_available=True, is_available=False)
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "key"}, clear=True):
        with pytest.raises(RuntimeError):
            runpy.run_module("verify_soul_persona", run_name="__main__")


@pytest.mark.asyncio
async def test_soul_persona_success(caplog):
    response_text = "Straight to the point. Nominee risk 10m safe foundation."
    _install_stubs(genai_available=True, is_available=True, response_text=response_text)

    with patch.dict(os.environ, {"GOOGLE_API_KEY": "key"}, clear=True):
        sys.modules.pop("verify_soul_persona", None)
        module = importlib.import_module("verify_soul_persona")
        await module.test_soul_persona()

    assert "Markers found" in caplog.text


def test_main_runs():
    response_text = "straight to nominee risk 10m"
    _install_stubs(genai_available=True, is_available=True, response_text=response_text)

    def run_coroutine(coro):
        coro.close()
        return None

    with patch.dict(os.environ, {"GOOGLE_API_KEY": "key"}, clear=True):
        with patch("asyncio.run", side_effect=run_coroutine):
            runpy.run_module("verify_soul_persona", run_name="__main__")
