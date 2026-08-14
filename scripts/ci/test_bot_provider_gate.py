"""Guilt+innocence corpus for scripts/ci/bot_provider_gate.py.

Cicatrix-superscar.md family #3 discipline: every implemented check has a
GUILT test (fires on the bad case) and an INNOCENCE test (does NOT fire on
an adjacent legitimate case) — including, per team-lead's explicit
instruction, the substring-trap check: `OPENAI_WA_PROVIDER_API_KEY` must
never trip the bare `OPENAI_API_KEY` ban.

Synthetic tmp_path trees laid out to mirror SCOPE_DIRS exactly (so
ADAPTER-shaped call sites land under `apps/backend-rag/backend/llm/` etc.)
— never the real repo tree, so this corpus is deterministic and immune to
whatever the real tree looks like on any given day.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from bot_provider_gate import run  # noqa: E402

LLM_DIR = "apps/backend-rag/backend/llm"
AGENTIC_DIR = "apps/backend-rag/backend/services/rag/agentic"
CHANNELS_DIR = "apps/backend-rag/backend/channels"


def _write(root: Path, rel_path: str, content: str) -> None:
    p = root / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _rules_fired(root: Path) -> set[str]:
    return {f.rule for f in run(root)}


# ── G1: OAuth-session-consumer ban ──────────────────────────────────────────


def test_g1_guilt_codex_home_env(tmp_path: Path) -> None:
    _write(tmp_path, f"{LLM_DIR}/openai_client.py", 'codex_home = os.environ["CODEX_HOME"]\n')
    assert "G1" in _rules_fired(tmp_path)


def test_g1_guilt_codex_exec_subprocess(tmp_path: Path) -> None:
    _write(
        tmp_path,
        f"{AGENTIC_DIR}/some_module.py",
        'subprocess.run(["codex", "exec", "-m", "gpt-5.6-sol", prompt])\n',
    )
    assert "G1" in _rules_fired(tmp_path)


def test_g1_guilt_chatgpt_cookie_domain(tmp_path: Path) -> None:
    _write(tmp_path, f"{CHANNELS_DIR}/some_module.py", 'COOKIE_HOST = "chat.openai.com"\n')
    assert "G1" in _rules_fired(tmp_path)


def test_g1_guilt_codex_auth_json_path(tmp_path: Path) -> None:
    _write(tmp_path, f"{LLM_DIR}/some_module.py", 'auth_path = "~/.codex/auth.json"\n')
    assert "G1" in _rules_fired(tmp_path)


def test_g1_guilt_claude_code_oauth_token_as_bot_credential(tmp_path: Path) -> None:
    _write(tmp_path, f"{LLM_DIR}/some_module.py", 'token = os.environ["CLAUDE_CODE_OAUTH_TOKEN"]\n')
    assert "G1" in _rules_fired(tmp_path)


def test_g1_innocence_bare_word_codex_is_fine(tmp_path: Path) -> None:
    """A bare mention of 'codex' (e.g. a comment referencing the CLI in
    general, with no CODEX_HOME/exec/login/auth.json shape) must not trip
    G1 — the ban targets the credential SHAPE, not the word."""
    _write(tmp_path, f"{LLM_DIR}/some_module.py", "# see the codex CLI docs for reference\n")
    assert "G1" not in _rules_fired(tmp_path)


def test_g1_innocence_excluded_tests_dir(tmp_path: Path) -> None:
    """The exact guilty shape, but under a tests/ dir nested inside scope —
    fixture data, not deploy code."""
    _write(tmp_path, f"{AGENTIC_DIR}/tests/test_something.py", 'codex_home = os.environ["CODEX_HOME"]\n')
    assert "G1" not in _rules_fired(tmp_path)


def test_g1_innocence_outside_scope_dirs_entirely(tmp_path: Path) -> None:
    _write(tmp_path, "apps/backend-rag/backend/app/routers/unrelated.py", 'os.environ["CODEX_HOME"]\n')
    assert "G1" not in _rules_fired(tmp_path)


def test_g1_innocence_pre_existing_sanctioned_claude_oauth_client(tmp_path: Path) -> None:
    """Found by the live dry-run against origin/main, not assumed in
    advance: apps/backend-rag/backend/llm/claude_oauth_client.py is the
    CLAUDE.md §5 sanctioned wrapper that reads CLAUDE_CODE_OAUTH_TOKEN by
    design, for 3 unrelated pre-existing consumers (article_composer,
    coreference, multi_ai_adapter.ClaudeAdapter) — none of them the
    WA-bot/OpenAI-adapter surface this gate fences. Must not trip G1."""
    _write(
        tmp_path,
        f"{LLM_DIR}/claude_oauth_client.py",
        'token = os.getenv("CLAUDE_CODE_OAUTH_TOKEN", "").strip()\n',
    )
    assert "G1" not in _rules_fired(tmp_path)


def test_g1_guilt_claude_oauth_token_in_a_different_llm_file_still_fires(tmp_path: Path) -> None:
    """The allowlist is scoped to the ONE named pre-existing file, not to
    the llm/ directory as a whole — a NEW file in the same directory
    reading this token must still trip G1."""
    _write(
        tmp_path,
        f"{LLM_DIR}/openai_responses_client.py",
        'token = os.getenv("CLAUDE_CODE_OAUTH_TOKEN", "").strip()\n',
    )
    assert "G1" in _rules_fired(tmp_path)


# ── G-claude-cli: bot backend must never shell out to `claude` CLI ──────────


def test_g_claude_cli_guilt(tmp_path: Path) -> None:
    _write(
        tmp_path,
        f"{AGENTIC_DIR}/llm_gateway.py",
        'result = subprocess.run(["claude", "--print", prompt])\n',
    )
    assert "G-claude-cli" in _rules_fired(tmp_path)


def test_g_claude_cli_innocence_openai_subprocess_unrelated(tmp_path: Path) -> None:
    _write(
        tmp_path,
        f"{AGENTIC_DIR}/llm_gateway.py",
        'result = subprocess.run(["some_other_tool", "--flag"])\n',
    )
    assert "G-claude-cli" not in _rules_fired(tmp_path)


# ── G2/G20: bare shared-key ban, with the explicit substring-trap guard ─────


def test_g2_guilt_bare_openai_api_key_settings(tmp_path: Path) -> None:
    _write(tmp_path, f"{LLM_DIR}/openai_client.py", "client = AsyncOpenAI(api_key=settings.openai_api_key)\n")
    assert "G2/G20" in _rules_fired(tmp_path)


def test_g2_guilt_bare_openai_api_key_env_var(tmp_path: Path) -> None:
    _write(tmp_path, f"{AGENTIC_DIR}/some_module.py", 'key = os.environ["OPENAI_API_KEY"]\n')
    assert "G2/G20" in _rules_fired(tmp_path)


def test_g2_innocence_dedicated_key_name_never_matches_bare_ban(tmp_path: Path) -> None:
    """The exact substring-trap team-lead flagged: OPENAI_WA_PROVIDER_API_KEY
    contains the substring 'API_KEY' and the words 'openai'/'provider', but
    must NEVER be treated as matching the bare OPENAI_API_KEY ban — the
    dedicated name is the SANCTIONED path, not a variant of the banned one."""
    _write(
        tmp_path,
        f"{LLM_DIR}/openai_client.py",
        "client = AsyncOpenAI(api_key=settings.openai_wa_provider_api_key)\n"
        'alt = os.environ["OPENAI_WA_PROVIDER_API_KEY"]\n',
    )
    assert "G2/G20" not in _rules_fired(tmp_path)


def test_g2_innocence_outside_scope_dirs(tmp_path: Path) -> None:
    """The pre-existing, legitimate embeddings/voice consumers live OUTSIDE
    the declared scope dirs entirely (core/embeddings.py, app/routers/
    voice.py, etc.) — verified this session against origin/main. This gate
    never sees them by construction."""
    _write(
        tmp_path,
        "apps/backend-rag/backend/core/embeddings.py",
        "self.client = AsyncOpenAI(api_key=settings.openai_api_key)\n",
    )
    assert "G2/G20" not in _rules_fired(tmp_path)


# ── G16: OpenAI-native tool-type ban ─────────────────────────────────────────


def test_g16_guilt_mcp_tool_type(tmp_path: Path) -> None:
    _write(tmp_path, f"{LLM_DIR}/openai_client.py", 'tools = [{"type": "mcp", "server_url": "https://x"}]\n')
    assert "G16" in _rules_fired(tmp_path)


def test_g16_guilt_web_search_tool_type(tmp_path: Path) -> None:
    _write(tmp_path, f"{AGENTIC_DIR}/shadow_provider.py", 'tools = [{"type": "web_search"}]\n')
    assert "G16" in _rules_fired(tmp_path)


def test_g16_innocence_function_tool_type(tmp_path: Path) -> None:
    _write(
        tmp_path,
        f"{LLM_DIR}/openai_client.py",
        'tools = [{"type": "function", "function": {"name": "crm_query"}}]\n',
    )
    assert "G16" not in _rules_fired(tmp_path)


# ── G17: AsyncOpenAI(base_url=...) pinning ──────────────────────────────────


def test_g17_guilt_untrusted_base_url(tmp_path: Path) -> None:
    _write(
        tmp_path,
        f"{LLM_DIR}/openai_client.py",
        'client = AsyncOpenAI(base_url="https://some-proxy.example/v1", api_key=k)\n',
    )
    assert "G17" in _rules_fired(tmp_path)


def test_g17_innocence_official_endpoint(tmp_path: Path) -> None:
    _write(
        tmp_path,
        f"{LLM_DIR}/openai_client.py",
        'client = AsyncOpenAI(base_url="https://api.openai.com/v1", api_key=k)\n',
    )
    assert "G17" not in _rules_fired(tmp_path)


def test_g17_innocence_no_base_url(tmp_path: Path) -> None:
    _write(tmp_path, f"{LLM_DIR}/openai_client.py", "client = AsyncOpenAI(api_key=k)\n")
    assert "G17" not in _rules_fired(tmp_path)


# ── G11: Responses API payload must set "store": false ─────────────────────


def test_g11_guilt_no_store_key_in_payload(tmp_path: Path) -> None:
    _write(
        tmp_path,
        f"{LLM_DIR}/openai_responses_client.py",
        'response = await self.client.responses.create(\n    model=self.model,\n    input=payload,\n)\n',
    )
    assert "G11" in _rules_fired(tmp_path)


def test_g11_innocence_store_false_present(tmp_path: Path) -> None:
    _write(
        tmp_path,
        f"{LLM_DIR}/openai_responses_client.py",
        "response = await self.client.responses.create(\n"
        "    model=self.model,\n"
        "    input=payload,\n"
        '    "store": False,\n'
        ")\n",
    )
    assert "G11" not in _rules_fired(tmp_path)


def test_g11_innocence_no_responses_create_call_at_all(tmp_path: Path) -> None:
    _write(tmp_path, f"{LLM_DIR}/unrelated.py", "def helper():\n    return 1\n")
    assert "G11" not in _rules_fired(tmp_path)


# ── G15: phantom ADR/doc citation ban ───────────────────────────────────────


def test_g15_guilt_cites_nonexistent_adr(tmp_path: Path) -> None:
    _write(
        tmp_path,
        f"{LLM_DIR}/openai_responses_client.py",
        '"""See research/operations/2026-08-15-adr-wa-runtime-openai-provider.md for the mandate."""\n',
    )
    assert "G15" in _rules_fired(tmp_path)


def test_g15_innocence_cites_a_doc_that_actually_exists(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "research/operations/2026-08-15-real-adr.md",
        "# Real ADR\n\nThis document exists.\n",
    )
    _write(
        tmp_path,
        f"{LLM_DIR}/openai_responses_client.py",
        '"""See research/operations/2026-08-15-real-adr.md for the mandate."""\n',
    )
    assert "G15" not in _rules_fired(tmp_path)


# ── Composite: a clean adapter file trips nothing ────────────────────────────


def test_clean_adapter_file_trips_nothing(tmp_path: Path) -> None:
    _write(
        tmp_path,
        f"{LLM_DIR}/openai_responses_client.py",
        "\n".join(
            [
                "from backend.app.core.config import settings",
                "",
                "client = AsyncOpenAI(",
                '    base_url="https://api.openai.com/v1",',
                "    api_key=settings.openai_wa_provider_api_key,",
                ")",
                "",
                "async def generate():",
                "    response = await client.responses.create(",
                "        model=MODEL_TERRA,",
                "        input=payload,",
                '        "store": False,',
                "    )",
                '    tools = [{"type": "function", "function": {"name": "crm_query"}}]',
                "    return response",
                "",
            ]
        ),
    )
    assert run(tmp_path) == []


# ── not_statically_checkable manifest is non-empty and self-consistent ──────


def test_not_statically_checkable_declared_with_reasons() -> None:
    from bot_provider_gate import NOT_STATICALLY_CHECKABLE

    assert len(NOT_STATICALLY_CHECKABLE) > 0
    for rule, reason in NOT_STATICALLY_CHECKABLE.items():
        assert len(reason) > 20, f"{rule} has a suspiciously thin justification"


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
