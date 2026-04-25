"""Tests for scripts/nlm_activation/collect_cep_answers.py — defensive
parsing of the prod RAG endpoint response shapes.
"""

import importlib.util
import json
import sys
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest


def _load_collector():
    p = Path(__file__).resolve().parents[2] / "scripts" / "nlm_activation" / "collect_cep_answers.py"
    spec = importlib.util.spec_from_file_location("collect_cep", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["collect_cep"] = mod
    spec.loader.exec_module(mod)
    return mod


class _FakeResponse:
    def __init__(self, payload: dict):
        self._buf = BytesIO(json.dumps(payload).encode())

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._buf.read()


def test_fetch_answer_top_level_answer_key():
    cep = _load_collector()
    with patch.object(cep.urllib.request, "urlopen", return_value=_FakeResponse({"answer": "OK!"})):
        assert cep.fetch_answer("http://x", "q") == "OK!"


def test_fetch_answer_nested_under_value():
    """Some NLM CLI wrappers return {value: {answer: ...}} — accept it."""
    cep = _load_collector()
    payload = {"value": {"answer": "wrapped answer"}}
    with patch.object(cep.urllib.request, "urlopen", return_value=_FakeResponse(payload)):
        assert cep.fetch_answer("http://x", "q") == "wrapped answer"


def test_fetch_answer_text_alias():
    """Tolerates {'text': ...} shape if the endpoint changes."""
    cep = _load_collector()
    with patch.object(cep.urllib.request, "urlopen", return_value=_FakeResponse({"text": "alias"})):
        assert cep.fetch_answer("http://x", "q") == "alias"


def test_fetch_answer_unknown_shape_returns_empty():
    cep = _load_collector()
    with patch.object(cep.urllib.request, "urlopen", return_value=_FakeResponse({"weird": True})):
        assert cep.fetch_answer("http://x", "q") == ""


def test_fetch_answer_http_error_returns_empty():
    cep = _load_collector()
    err = cep.urllib.error.HTTPError("http://x", 500, "boom", {}, None)
    with patch.object(cep.urllib.request, "urlopen", side_effect=err):
        assert cep.fetch_answer("http://x", "q") == ""


def test_fetch_answer_timeout_returns_empty():
    cep = _load_collector()
    with patch.object(cep.urllib.request, "urlopen", side_effect=TimeoutError("slow")):
        assert cep.fetch_answer("http://x", "q") == ""


def test_collect_iterates_synthetic_golden(tmp_path):
    """collect() walks every (domain, query) tuple in the golden file.

    Uses a synthetic golden file local to the test rather than depending
    on the real apps/evaluator/cep/golden_v20260425.json, which lives in
    a separate PR. This keeps the test self-contained.
    """
    cep = _load_collector()
    golden_path = tmp_path / "synthetic_golden.json"
    golden_path.write_text(json.dumps({
        "version": "test",
        "domains": {
            "immigration": [
                {"id": "imm-01", "query": "Q1", "required_facts": ["x"], "tier": 1},
                {"id": "imm-02", "query": "Q2", "required_facts": ["y"], "tier": 1},
            ],
            "tax": [
                {"id": "tax-01", "query": "Q3", "required_facts": ["z"], "tier": 1},
            ],
        },
    }))

    called = []

    def fake_fetch(endpoint, query, *, token=None, timeout=30):
        called.append(query)
        return f"FAKE-ANSWER for {query}"

    with patch.object(cep, "fetch_answer", side_effect=fake_fetch):
        answers = cep.collect(golden_path, "http://x", token=None, delay_seconds=0)

    assert len(answers) == 3
    assert {"imm-01", "imm-02", "tax-01"} == set(answers.keys())
    assert all(v.startswith("FAKE-ANSWER") for v in answers.values())
