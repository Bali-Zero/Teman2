"""Tests for nb_monitor.collectors.log_scraper."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mata_garuda.scripts.nb_monitor.collectors.log_scraper import (
    iter_nlm_events,
    count_nlm_events_by_uuid,
    NLMEvent,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_iter_nlm_events_yields_only_nlm_tool_calls(tmp_path):
    src = FIXTURES / "jsonl_sample.jsonl"
    target = tmp_path / "session.jsonl"
    target.write_bytes(src.read_bytes())

    events = list(iter_nlm_events([target]))
    assert len(events) == 4  # 3 notebook_query + 1 source_add
    uuids = [e.uuid for e in events]
    assert "1ed02e54-542f-426a-94f8-53c5ffde4b7d" in uuids
    assert "7fb12c9c-4e12-4a8d-9bd1-c5b857bf310f" in uuids
    assert all(isinstance(e, NLMEvent) for e in events)


def test_iter_nlm_events_supports_both_field_variants(tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_text(
        '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"mcp__notebooklm-mcp__notebook_query","input":{"notebook_id":"a"}}]}}\n'
        '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"mcp__notebooklm-mcp__notebook_query","input":{"notebookId":"b"}}]}}\n'
    )
    events = list(iter_nlm_events([p]))
    assert {e.uuid for e in events} == {"a", "b"}


def test_iter_nlm_events_skips_malformed_lines(tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_text(
        "not json\n"
        '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"mcp__notebooklm-mcp__notebook_query","input":{"notebook_id":"a"}}]}}\n'
        "still not json\n"
    )
    events = list(iter_nlm_events([p]))
    assert len(events) == 1


def test_iter_nlm_events_skips_non_nlm_tools(tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_text(
        '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash","input":{"command":"ls"}}]}}\n'
        '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Read","input":{"file_path":"x"}}]}}\n'
    )
    events = list(iter_nlm_events([p]))
    assert events == []


def test_count_nlm_events_by_uuid(tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_text(
        '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"mcp__notebooklm-mcp__notebook_query","input":{"notebook_id":"a","query":"1"}}]}}\n'
        '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"mcp__notebooklm-mcp__notebook_query","input":{"notebook_id":"a","query":"2"}}]}}\n'
        '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"mcp__notebooklm-mcp__notebook_query","input":{"notebookId":"b","query":"x"}}]}}\n'
    )
    counts = count_nlm_events_by_uuid([p], window_seconds=86400 * 30, now=10**12)
    assert counts == {"a": 2, "b": 1}


def test_count_nlm_events_filters_by_window(tmp_path, monkeypatch):
    """File mtime older than window must be skipped entirely."""
    import os

    old = tmp_path / "old.jsonl"
    old.write_text(
        '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"mcp__notebooklm-mcp__notebook_query","input":{"notebook_id":"a"}}]}}\n'
    )
    sixty_days_ago = int(__import__("time").time()) - 60 * 86400
    os.utime(old, (sixty_days_ago, sixty_days_ago))

    new = tmp_path / "new.jsonl"
    new.write_text(
        '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"mcp__notebooklm-mcp__notebook_query","input":{"notebook_id":"b"}}]}}\n'
    )

    counts = count_nlm_events_by_uuid([old, new], window_seconds=7 * 86400)
    assert counts == {"b": 1}


def test_count_nlm_events_returns_empty_on_no_files(tmp_path):
    counts = count_nlm_events_by_uuid([], window_seconds=86400)
    assert counts == {}
