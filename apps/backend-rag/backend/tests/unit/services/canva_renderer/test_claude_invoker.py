"""Tests for canva_renderer.claude_invoker.

Covers URL extraction patterns from varied claude -p outputs; subprocess
spawn/timeout is tested separately (needs Claude CLI, skipped in CI).
"""

from __future__ import annotations

import json
import subprocess

import pytest

from backend.services.canva_renderer import claude_invoker
from backend.services.canva_renderer.claude_invoker import (
    DEFAULT_CLAUDE_MODEL,
    CanvaInvokeError,
    extract_canva_urls,
    invoke_claude_apply,
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


class TestInvokeClaudeApplyModelPin:
    """Model pin added 2026-08-20 (token-cuts round2): this call was bare
    (no --model), inheriting the profile default — grandfathered by
    scripts/lint/lint_claude_headless_model_pin.py. Pure argv-construction
    check via a monkeypatched subprocess.run — no real Claude CLI spawned,
    so no skip marker needed (unlike the real-subprocess tests this file's
    docstring defers elsewhere).

    invoke_claude_apply() also reads a REAL userspace file first
    (~/.claude/skills/canva-apply.md, this module's runbook single-source)
    before it ever reaches subprocess.run — on a CI runner's ephemeral $HOME
    that file does not exist, so both tests here also monkeypatch
    APPLICA_RUNBOOK_PATH to a tmp file with dummy content, keeping this
    class's own claim ("no real Claude CLI spawned") true without silently
    depending on the operator machine's userspace skill install.
    """

    def _stub_runbook(self, tmp_path, monkeypatch) -> None:
        runbook = tmp_path / "canva-apply.md"
        runbook.write_text("dummy runbook body\n", encoding="utf-8")
        monkeypatch.setattr(claude_invoker, "APPLICA_RUNBOOK_PATH", runbook)

    def test_argv_carries_a_pinned_model(self, tmp_path, monkeypatch) -> None:
        self._stub_runbook(tmp_path, monkeypatch)
        pending = tmp_path / "canva_pending.json"
        pending.write_text(json.dumps({"pages": []}))

        captured: dict[str, list[str]] = {}

        def fake_run(argv, **kwargs):
            captured["argv"] = list(argv)

            class _R:
                returncode = 0
                stdout = '{"design_id":"DABC12345","edit_url":"https://www.canva.com/d/abc"}'
                stderr = ""

            return _R()

        monkeypatch.setattr(subprocess, "run", fake_run)
        invoke_claude_apply(pending)

        assert "argv" in captured, "invoke_claude_apply never called subprocess.run"
        argv = captured["argv"]
        assert "--model" in argv, f"no --model flag in {argv!r}"
        model = argv[argv.index("--model") + 1]
        assert model == DEFAULT_CLAUDE_MODEL

    def test_model_is_overridable(self, tmp_path, monkeypatch) -> None:
        self._stub_runbook(tmp_path, monkeypatch)
        pending = tmp_path / "canva_pending.json"
        pending.write_text(json.dumps({"pages": []}))

        captured: dict[str, list[str]] = {}

        def fake_run(argv, **kwargs):
            captured["argv"] = list(argv)

            class _R:
                returncode = 0
                stdout = '{"design_id":"DABC12345","edit_url":"https://www.canva.com/d/abc"}'
                stderr = ""

            return _R()

        monkeypatch.setattr(subprocess, "run", fake_run)
        invoke_claude_apply(pending, model="claude-opus-5")

        model = captured["argv"][captured["argv"].index("--model") + 1]
        assert model == "claude-opus-5"
