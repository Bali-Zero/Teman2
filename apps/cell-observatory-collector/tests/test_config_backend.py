from __future__ import annotations
import pytest
from cell_observatory.config import Config


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ("OPENROUTER_API_KEY", "MINIMAXM2_API_KEY", "MINIMAX_API_KEY",
              "OBSERVATORY_CLASSIFIER", "EVENTBUS_DATABASE_URL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("EVENTBUS_DATABASE_URL", "postgresql://x@localhost:15432/db")


def test_ollama_backend_needs_no_llm_key(monkeypatch):
    monkeypatch.setenv("OBSERVATORY_CLASSIFIER", "ollama")
    cfg = Config.from_env()
    assert cfg.classifier_backend == "ollama"
    assert cfg.minimax_api_key is None


def test_default_backend_is_ollama(monkeypatch):
    cfg = Config.from_env()
    assert cfg.classifier_backend == "ollama"


def test_minimax_backend_still_requires_key(monkeypatch):
    monkeypatch.setenv("OBSERVATORY_CLASSIFIER", "minimax")
    with pytest.raises(RuntimeError, match="API_KEY"):
        Config.from_env()


def test_minimax_backend_with_key_ok(monkeypatch):
    monkeypatch.setenv("OBSERVATORY_CLASSIFIER", "minimax")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    cfg = Config.from_env()
    assert cfg.classifier_backend == "minimax"
    assert cfg.minimax_api_key == "sk-test"


def test_invalid_backend_raises(monkeypatch):
    monkeypatch.setenv("OBSERVATORY_CLASSIFIER", "local")
    with pytest.raises(RuntimeError, match="not a recognised backend"):
        Config.from_env()
