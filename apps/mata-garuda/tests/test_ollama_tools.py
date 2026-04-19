"""Tests for mata_garuda.tools.ollama_tools — JSON extraction + subprocess mocking."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from mata_garuda.tools import ollama_tools


def test_extract_json_plain_object():
    assert ollama_tools.extract_json('{"a": 1, "b": "x"}') == {"a": 1, "b": "x"}


def test_extract_json_with_prose():
    text = 'Here is the answer:\n{"domain": "tax_fiscal", "priority": "high"}\nhope that helps.'
    assert ollama_tools.extract_json(text) == {"domain": "tax_fiscal", "priority": "high"}


def test_extract_json_fenced_code_block():
    text = 'Sure!\n```json\n{"keywords": ["a", "b"]}\n```\nDone.'
    assert ollama_tools.extract_json(text) == {"keywords": ["a", "b"]}


def test_extract_json_nested_object():
    text = 'out: {"entities": {"persons": ["Joko"], "laws": []}, "ok": true}'
    parsed = ollama_tools.extract_json(text)
    assert parsed == {"entities": {"persons": ["Joko"], "laws": []}, "ok": True}


def test_extract_json_none_when_unparseable():
    assert ollama_tools.extract_json("no json here, sorry") is None
    assert ollama_tools.extract_json("") is None
    assert ollama_tools.extract_json("{broken") is None


def test_generate_returns_response_on_happy_path():
    fake_proc = MagicMock()
    fake_proc.returncode = 0
    fake_proc.stdout = json.dumps({"response": "hello world"})
    with patch.object(ollama_tools.subprocess, "run", return_value=fake_proc) as run:
        out = ollama_tools.generate("gemma4:26b", "hi")
    assert out == "hello world"
    args, _ = run.call_args
    assert args[0][0] == "curl"
    assert ollama_tools.OLLAMA_ENDPOINT in args[0]


def test_generate_returns_none_on_timeout():
    import subprocess as sp

    with patch.object(
        ollama_tools.subprocess, "run", side_effect=sp.TimeoutExpired(cmd="curl", timeout=1)
    ):
        assert ollama_tools.generate("gemma4:26b", "hi", timeout=1) is None


def test_generate_returns_none_on_nonzero_exit():
    fake_proc = MagicMock()
    fake_proc.returncode = 7
    fake_proc.stderr = "boom"
    fake_proc.stdout = ""
    with patch.object(ollama_tools.subprocess, "run", return_value=fake_proc):
        assert ollama_tools.generate("gemma4:26b", "hi") is None


def test_generate_json_round_trip():
    fake_proc = MagicMock()
    fake_proc.returncode = 0
    fake_proc.stdout = json.dumps(
        {"response": 'Here: {"domain": "property", "priority": "low"}'}
    )
    with patch.object(ollama_tools.subprocess, "run", return_value=fake_proc):
        parsed = ollama_tools.generate_json("gemma4:26b", "?")
    assert parsed == {"domain": "property", "priority": "low"}


def test_embed_returns_vector_on_success():
    fake_proc = MagicMock()
    fake_proc.returncode = 0
    fake_proc.stdout = json.dumps({"embedding": [0.1, 0.2, 0.3]})
    with patch.object(ollama_tools.subprocess, "run", return_value=fake_proc):
        vec = ollama_tools.embed("nomic-embed-text", "hi")
    assert vec == [0.1, 0.2, 0.3]


def test_embed_returns_none_when_missing():
    fake_proc = MagicMock()
    fake_proc.returncode = 0
    fake_proc.stdout = json.dumps({"embedding": None})
    with patch.object(ollama_tools.subprocess, "run", return_value=fake_proc):
        assert ollama_tools.embed("nomic-embed-text", "hi") is None


def test_has_model_true_when_listed():
    fake_proc = MagicMock()
    fake_proc.returncode = 0
    fake_proc.stdout = json.dumps(
        {"models": [{"name": "gemma4:26b"}, {"name": "qwen3.5:9b"}]}
    )
    with patch.object(ollama_tools.subprocess, "run", return_value=fake_proc):
        assert ollama_tools.has_model("gemma4:26b") is True
        assert ollama_tools.has_model("nonexistent:1b") is False


def test_list_local_models_empty_on_ollama_down():
    import subprocess as sp

    with patch.object(
        ollama_tools.subprocess, "run", side_effect=sp.TimeoutExpired(cmd="curl", timeout=1)
    ):
        assert ollama_tools.list_local_models(timeout=1) == []
