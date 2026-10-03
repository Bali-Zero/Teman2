"""research_sentinel keeps its own log setup after importing curl_send from
meta_dispatcher.

Regression found in gate-7514's re-gate (2026-09-27): research_sentinel.py
now does `from eventbus.meta_dispatcher import curl_send`, and
meta_dispatcher's module-level `logging.basicConfig(...)` runs first and
claims the root logger, turning research_sentinel's own `basicConfig` into a
no-op. Its lines would silently land in meta-dispatcher.log instead of
research-sentinel.log, with no logger name in the format string to tell them
apart. Cure: `force=True` on research_sentinel's basicConfig so it reclaims
the root logger after meta_dispatcher's import-time side effect.
"""
from __future__ import annotations

import importlib
import logging
import sys
from pathlib import Path

import pytest

MODULE_NAMES = ("eventbus.research_sentinel", "eventbus.meta_dispatcher")


@pytest.fixture
def fresh_research_sentinel(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    saved_modules = {name: sys.modules.pop(name, None) for name in MODULE_NAMES}
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    for h in saved_handlers:
        root.removeHandler(h)

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    try:
        module = importlib.import_module("eventbus.research_sentinel")
        yield module
    finally:
        for h in list(root.handlers):
            root.removeHandler(h)
            h.close()
        for h in saved_handlers:
            root.addHandler(h)
        root.setLevel(saved_level)
        for name, mod in saved_modules.items():
            if mod is not None:
                sys.modules[name] = mod
            else:
                sys.modules.pop(name, None)


class TestResearchSentinelKeepsOwnLogSetup:
    def test_root_handler_targets_research_sentinel_log(self, fresh_research_sentinel):
        root = logging.getLogger()
        file_handler_names = [
            Path(h.baseFilename).name
            for h in root.handlers
            if isinstance(h, logging.FileHandler)
        ]
        assert file_handler_names == ["research-sentinel.log"]

    def test_meta_dispatcher_log_gets_no_line_from_research_sentinel(self, fresh_research_sentinel, tmp_path):
        fresh_research_sentinel.log.warning("probe from research_sentinel")
        for h in logging.getLogger().handlers:
            h.flush()

        sentinel_log = tmp_path / "logs" / "research-sentinel.log"
        meta_log = tmp_path / "logs" / "meta-dispatcher.log"

        assert sentinel_log.exists()
        assert "probe from research_sentinel" in sentinel_log.read_text()
        assert not meta_log.exists() or "probe from research_sentinel" not in meta_log.read_text()
