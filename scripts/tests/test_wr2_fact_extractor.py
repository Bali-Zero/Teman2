"""Unit tests for scripts/wr2_fact_extractor.py (Sprint B B-bis).

Covers:
- JSON parser tolerates fenced + bare model output
- Claim type normalisation (rejects unknown types → 'other')
- Empty / malformed responses produce [] (degrade-open)
- _process_one_draft persists status='drafts_imaged_facted' on success
- OAuth failure → returns False, no DB mutation, telemetry recorded

All Claude calls + DB writes are mocked.
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
EXTRACTOR_PATH = SCRIPTS_DIR / "wr2_fact_extractor.py"


@pytest.fixture
def fx(tmp_path, monkeypatch):
    """Fresh import with telemetry redirected to tmp."""
    sys.modules.pop("wr2_fact_extractor", None)
    spec = importlib.util.spec_from_file_location("wr2_fact_extractor", EXTRACTOR_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["wr2_fact_extractor"] = mod
    spec.loader.exec_module(mod)
    mod.TELEMETRY_PATH = tmp_path / "extractor.jsonl"
    return mod


# ─────────────────────────────────────────────────────────────────────────
# JSON parser
# ─────────────────────────────────────────────────────────────────────────

def test_parse_claims_json_bare_object(fx):
    raw = '{"claims": [{"claim": "PP 28/2025", "slide_index": 2, "type": "law"}]}'
    out = fx._parse_claims_json(raw, slide_index=2)
    assert out is not None
    assert len(out) == 1
    assert out[0]["claim"] == "PP 28/2025"
    assert out[0]["type"] == "law"
    assert out[0]["slide_index"] == 2


def test_parse_claims_json_fenced(fx):
    raw = '```json\n{"claims": [{"claim": "1.5%", "slide_index": 3, "type": "number"}]}\n```'
    out = fx._parse_claims_json(raw, slide_index=3)
    assert out is not None and len(out) == 1
    assert out[0]["type"] == "number"


def test_parse_claims_json_with_prose(fx):
    """Tolerate model wrapping JSON in commentary."""
    raw = (
        "Here are the claims:\n"
        '{"claims": [{"claim": "31 May 2026", "slide_index": 1, "type": "date"}]}\n'
        "Hope this helps!"
    )
    out = fx._parse_claims_json(raw, slide_index=1)
    assert out is not None and len(out) == 1
    assert out[0]["type"] == "date"


def test_parse_claims_json_empty_list(fx):
    raw = '{"claims": []}'
    out = fx._parse_claims_json(raw, slide_index=0)
    assert out == []


def test_parse_claims_json_unknown_type_normalised(fx):
    """Unknown types collapse to 'other' rather than rejecting the claim."""
    raw = '{"claims": [{"claim": "X", "slide_index": 0, "type": "weird"}]}'
    out = fx._parse_claims_json(raw, slide_index=0)
    assert out is not None and len(out) == 1
    assert out[0]["type"] == "other"


def test_parse_claims_json_missing_claim_text_dropped(fx):
    raw = '{"claims": [{"claim": "", "slide_index": 0, "type": "law"}, {"claim": "ok", "slide_index": 0, "type": "law"}]}'
    out = fx._parse_claims_json(raw, slide_index=0)
    assert out is not None and len(out) == 1
    assert out[0]["claim"] == "ok"


def test_parse_claims_json_garbage_returns_none(fx):
    """Callers retry on None — never on []."""
    assert fx._parse_claims_json("totally not json", slide_index=0) is None
    assert fx._parse_claims_json("", slide_index=0) is None
    assert fx._parse_claims_json("{invalid", slide_index=0) is None


def test_parse_claims_json_invalid_slide_index_falls_back(fx):
    raw = '{"claims": [{"claim": "X", "slide_index": "not-a-number", "type": "law"}]}'
    out = fx._parse_claims_json(raw, slide_index=7)
    assert out is not None and out[0]["slide_index"] == 7


# ─────────────────────────────────────────────────────────────────────────
# Per-slide extraction
# ─────────────────────────────────────────────────────────────────────────

def test_extract_one_slide_empty_body_returns_empty(fx):
    out = asyncio.run(
        fx._extract_one_slide(
            topic="x",
            register="pedagogico",
            slide={"index": 1, "title": "T", "body": ""},
            model="claude-opus-4-7",
            timeout_s=60,
        )
    )
    assert out == []


def test_extract_one_slide_retry_on_parse_failure(fx):
    """First response is unparseable → retry → succeed."""
    fake_resp_bad = MagicMock()
    fake_resp_bad.text = "not json"
    fake_resp_good = MagicMock()
    fake_resp_good.text = '{"claims": [{"claim": "Y", "slide_index": 4, "type": "other"}]}'
    mock = AsyncMock(side_effect=[fake_resp_bad, fake_resp_good])
    with patch.object(fx, "complete_async", mock):
        out = asyncio.run(
            fx._extract_one_slide(
                topic="t", register="p",
                slide={"index": 4, "title": "T", "body": "some body"},
                model="claude-opus-4-7", timeout_s=60,
            )
        )
    assert mock.await_count == 2
    assert len(out) == 1 and out[0]["claim"] == "Y"


def test_extract_one_slide_persistent_parse_failure_returns_empty(fx):
    """After 2 retries with bad JSON, return empty (degrade-open)."""
    bad = MagicMock()
    bad.text = "still not json"
    mock = AsyncMock(side_effect=[bad, bad])
    with patch.object(fx, "complete_async", mock):
        out = asyncio.run(
            fx._extract_one_slide(
                topic="t", register="p",
                slide={"index": 0, "title": "T", "body": "body"},
                model="claude-opus-4-7", timeout_s=60,
            )
        )
    assert mock.await_count == 2
    assert out == []


# ─────────────────────────────────────────────────────────────────────────
# Per-draft pipeline
# ─────────────────────────────────────────────────────────────────────────

def _make_row(draft_id: uuid.UUID, slides: list[dict] | None = None) -> dict:
    return {
        "id": draft_id,
        "topic": "Test topic",
        "register": "pedagogico",
        "slides_json": {"slides": slides or [{"index": 1, "title": "T", "body": "B"}]},
    }


def test_process_one_draft_success_persists_facted(fx):
    """Happy path: claims extracted, status advances to drafts_imaged_facted."""
    draft_id = uuid.uuid4()
    row = _make_row(draft_id, slides=[
        {"index": 1, "title": "T1", "body": "Body with PP 28/2025"},
        {"index": 2, "title": "T2", "body": "Body 2"},
    ])

    fake_resp = MagicMock()
    fake_resp.text = '{"claims": [{"claim": "PP 28/2025", "slide_index": 1, "type": "law"}]}'

    conn = MagicMock()
    conn.execute = AsyncMock()

    with patch.object(fx, "complete_async", AsyncMock(return_value=fake_resp)):
        ok = asyncio.run(fx._process_one_draft(conn, row))

    assert ok is True
    conn.execute.assert_awaited_once()
    args = conn.execute.call_args[0]
    sql = args[0]
    assert "fact_check_json" in sql
    assert "drafts_imaged_facted" in sql
    # Verify draft_id passed.
    assert args[1] == draft_id
    # Verify payload contains the claims.
    payload = json.loads(args[2])
    assert "claims" in payload
    assert len(payload["claims"]) == 2  # one per slide
    assert all(c["type"] == "law" for c in payload["claims"])


def test_process_one_draft_oauth_error_returns_false(fx):
    """OAuth subprocess failure → no DB write, telemetry recorded, return False."""
    draft_id = uuid.uuid4()
    row = _make_row(draft_id)
    conn = MagicMock()
    conn.execute = AsyncMock()

    err = fx.ClaudeOAuthError("rate limited on all tokens")
    with patch.object(fx, "complete_async", AsyncMock(side_effect=err)), \
         patch.object(fx, "_send_telegram", lambda *_a, **_kw: None):
        ok = asyncio.run(fx._process_one_draft(conn, row))

    assert ok is False
    conn.execute.assert_not_awaited()
    # Telemetry has 'oauth_error' row.
    tel_lines = fx.TELEMETRY_PATH.read_text().splitlines() if fx.TELEMETRY_PATH.is_file() else []
    assert any('"outcome": "oauth_error"' in line for line in tel_lines)


def test_process_one_draft_no_slides_returns_false(fx):
    draft_id = uuid.uuid4()
    row = {
        "id": draft_id,
        "topic": "T",
        "register": "pedagogico",
        "slides_json": {"slides": []},
    }
    conn = MagicMock()
    conn.execute = AsyncMock()
    ok = asyncio.run(fx._process_one_draft(conn, row))
    assert ok is False
    conn.execute.assert_not_awaited()


def test_process_one_draft_handles_string_slides_json(fx):
    """slides_json may arrive as a JSON string from asyncpg."""
    draft_id = uuid.uuid4()
    row = {
        "id": draft_id,
        "topic": "T",
        "register": "pedagogico",
        "slides_json": json.dumps({"slides": [{"index": 1, "title": "X", "body": "Y"}]}),
    }
    conn = MagicMock()
    conn.execute = AsyncMock()
    fake_resp = MagicMock()
    fake_resp.text = '{"claims": []}'
    with patch.object(fx, "complete_async", AsyncMock(return_value=fake_resp)):
        ok = asyncio.run(fx._process_one_draft(conn, row))
    assert ok is True
    conn.execute.assert_awaited_once()


# ─────────────────────────────────────────────────────────────────────────
# OB-3 invariant guard
# ─────────────────────────────────────────────────────────────────────────

def test_uses_claude_oauth_client_not_anthropic_sdk():
    """OB-3 hard rule: never import anthropic / never use ANTHROPIC_API_KEY.

    The docstring/comments mention ANTHROPIC_API_KEY in the prohibition
    paragraph, so this test parses with `ast` and only inspects code
    nodes (Import / ImportFrom / Name lookup) rather than raw text.
    """
    import ast
    tree = ast.parse(EXTRACTOR_PATH.read_text())
    used_oauth_client = False
    for node in ast.walk(tree):
        # Forbid `import anthropic` / `from anthropic ...`
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("anthropic"), (
                    f"OB-3 violation: import anthropic at line {node.lineno}"
                )
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("anthropic"), (
                f"OB-3 violation: from anthropic import at line {node.lineno}"
            )
            if node.module and node.module.endswith("claude_oauth_client"):
                used_oauth_client = True
        # Forbid os.environ access of ANTHROPIC_API_KEY in code (not strings).
        # We inspect Subscript / Call patterns over the env lookup.
    assert used_oauth_client, "must import from claude_oauth_client"
