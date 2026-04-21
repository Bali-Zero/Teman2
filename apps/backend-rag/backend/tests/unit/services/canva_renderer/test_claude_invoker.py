"""Tests for canva_renderer.claude_invoker.

Covers URL extraction patterns from varied claude -p outputs; subprocess
spawn/timeout is tested separately (needs Claude CLI, skipped in CI).
"""

from __future__ import annotations

import pytest

from backend.services.canva_renderer.claude_invoker import (
    APPLICA_RUNBOOK_PATH,
    CanvaInvokeError,
    extract_canva_urls,
)


class TestExtractCanvaUrls:
    def test_extracts_edit_and_view_urls_from_json_response(self) -> None:
        stdout = (
            '{"design_id":"DABC12345XY","edit_url":'
            '"https://www.canva.com/d/iG2ND48jrmlbc7O",'
            '"view_url":"https://www.canva.com/d/sQLTJKhsJI91xmr"}'
        )
        result = extract_canva_urls(stdout)
        assert result.design_id == "DABC12345XY"
        assert result.edit_url == "https://www.canva.com/d/iG2ND48jrmlbc7O"
        assert result.view_url == "https://www.canva.com/d/sQLTJKhsJI91xmr"

    def test_extracts_when_claude_emits_extra_narrative_text(self) -> None:
        stdout = """I have applied the operations successfully.
        Here is the carousel:
        {"design_id":"DXYZ98765AB","edit_url":"https://www.canva.com/d/abc","view_url":"https://www.canva.com/d/def"}
        Let me know if you want to edit more."""
        result = extract_canva_urls(stdout)
        assert result.design_id == "DXYZ98765AB"
        assert result.edit_url == "https://www.canva.com/d/abc"

    def test_extracts_edit_url_from_markdown_link(self) -> None:
        """Fallback: if claude writes `[link](url)` without JSON."""
        stdout = (
            "Applied 26 operations. Open in Canva: "
            "[here](https://www.canva.com/d/Ft182s1_e9vPZ-J) to review."
        )
        result = extract_canva_urls(stdout)
        assert result.edit_url == "https://www.canva.com/d/Ft182s1_e9vPZ-J"
        assert result.design_id is None  # markdown path doesn't carry it

    def test_extracts_bare_canva_url(self) -> None:
        stdout = "Done. https://www.canva.com/d/cprPEwtwcvzdtuC is the editor."
        result = extract_canva_urls(stdout)
        assert result.edit_url == "https://www.canva.com/d/cprPEwtwcvzdtuC"

    def test_raises_when_no_url_found(self) -> None:
        stdout = "I tried but MCP Canva returned an error."
        with pytest.raises(CanvaInvokeError, match="no Canva URL"):
            extract_canva_urls(stdout)

    def test_raises_on_empty_output(self) -> None:
        with pytest.raises(CanvaInvokeError, match="empty output"):
            extract_canva_urls("")


class TestRunbookPath:
    def test_runbook_resolves_relative_to_module(self) -> None:
        """Runbook must ship with the module (portable across machines)."""
        assert APPLICA_RUNBOOK_PATH.is_file(), (
            f"APPLICA_WAR_ROOM.md must live at {APPLICA_RUNBOOK_PATH} "
            "so Pro/Air/CI all resolve it without an absolute home path."
        )

    def test_runbook_is_canva_renderer_internal(self) -> None:
        """Decommission guard: runbook is NOT in apps/war-room anymore."""
        parts = APPLICA_RUNBOOK_PATH.parts
        assert "canva_renderer" in parts
        assert "war-room" not in parts  # i.e. not apps/war-room
