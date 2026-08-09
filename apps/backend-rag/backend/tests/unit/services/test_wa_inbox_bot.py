"""Tests for the WA Meta-inbox bot reply generator (generate_bot_reply).

Covers the Option-B safety contract:
  - feature flag OFF (default) → raises (worker marks failed/retry, no send).
  - no customer message in thread → raises.
  - RAG abstain → ignores the raw answer and returns the server-owned,
    query-language-localized refusal as a terminal sendable outcome.
  - empty normal RAG answer → raises.
  - happy path → returns a normal outcome, sends the correct payload to the
    RAG worker (query = latest customer msg, history oldest→newest, channel).
  - [ESCALATE] marker stripped from the answer.
"""

from __future__ import annotations

import ast
import asyncio
import os
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest

from backend.services.common.localized_stubs import get_localized_stub
from backend.services.integrations import wa_inbox_bot
from backend.services.integrations.wa_bot_outcomes import BotReply, BotStandingCondition


class _Conn:
    def __init__(
        self,
        rows: list[dict[str, Any]],
        fetchrow_result: dict[str, Any] | None = None,
        fetchrow_error: Exception | None = None,
    ) -> None:
        self._rows = rows
        self._fetchrow_result = fetchrow_result
        self._fetchrow_error = fetchrow_error
        self.fetchrow_calls = 0

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        return self._rows

    async def fetchrow(self, sql: str, *args: Any) -> dict[str, Any] | None:
        # Used by resolve_sender_identity's team_members/clients lookups.
        # No table-routing needed here — these tests either want "no match"
        # (default None, both lookups miss → role=unknown) or "DB down"
        # (fetchrow_error, raised on the first lookup it makes).
        self.fetchrow_calls += 1
        if self._fetchrow_error is not None:
            raise self._fetchrow_error
        return self._fetchrow_result


class _Pool:
    def __init__(
        self,
        rows: list[dict[str, Any]],
        fetchrow_result: dict[str, Any] | None = None,
        fetchrow_error: Exception | None = None,
    ) -> None:
        self._conn = _Conn(rows, fetchrow_result=fetchrow_result, fetchrow_error=fetchrow_error)

    def acquire(self) -> Any:
        @asynccontextmanager
        async def _cm():
            yield self._conn

        return _cm()


def _thread(thread_id: int = 7, phone: str = "62811") -> dict[str, Any]:
    return {"thread_id": thread_id, "counterpart_phone": phone}


def _mock_rag(monkeypatch, response_json: dict[str, Any]) -> dict[str, Any]:
    """Patch the persistent RAG client; return a captured dict for assertions."""
    captured: dict[str, Any] = {}

    resp = MagicMock()
    resp.raise_for_status = MagicMock(return_value=None)
    resp.json = MagicMock(return_value=response_json)

    async def _post(url: str, json: dict[str, Any]) -> Any:
        captured["url"] = url
        captured["json"] = json
        return resp

    client = MagicMock()
    client.post = AsyncMock(side_effect=_post)

    async def _get_client() -> Any:
        return client

    monkeypatch.setattr(wa_inbox_bot, "_get_rag_client", _get_client)
    return captured


# newest→oldest as the SQL ORDER BY DESC returns them.
_ROWS_NEWEST_FIRST = [
    {"direction": "inbound", "sender_role": "customer", "body": "Quanto costa un KITAS?"},
    {"direction": "outbound", "sender_role": "bot", "body": "Ciao! Come posso aiutarti?"},
    {"direction": "inbound", "sender_role": "customer", "body": "Ciao"},
]


@pytest.mark.asyncio
async def test_flag_off_raises(monkeypatch):
    monkeypatch.delenv("WA_INBOX_BOT_AUTOREPLY", raising=False)
    pool = _Pool(_ROWS_NEWEST_FIRST)
    with pytest.raises(BotStandingCondition, match="disabled"):
        await wa_inbox_bot.generate_bot_reply(pool, _thread())


@pytest.mark.asyncio
async def test_no_customer_message_raises(monkeypatch):
    monkeypatch.setenv("WA_INBOX_BOT_AUTOREPLY", "true")
    pool = _Pool([{"direction": "outbound", "sender_role": "bot", "body": "hi"}])
    with pytest.raises(BotStandingCondition, match="no customer message"):
        await wa_inbox_bot.generate_bot_reply(pool, _thread())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "language"),
    [
        ("Quanto costa un KITAS?", "ITALIAN"),
        ("Serve un visto?", "ITALIAN"),
        ("Vorrei aprire una società", "ITALIAN"),
        ("Berapa biaya KITAS?", "INDONESIAN"),
        ("How much does a KITAS cost?", "ENGLISH"),
        ("Сколько стоит виза KITAS?", "RUSSIAN"),
        ("Скільки коштує віза KITAS?", "UKRAINIAN"),
    ],
)
async def test_abstain_never_forwards_rag_claim_and_uses_localized_server_stub(
    monkeypatch,
    query: str,
    language: str,
):
    monkeypatch.setenv("WA_INBOX_BOT_AUTOREPLY", "true")
    forbidden_canary = (
        "CANARY_E33_FORBIDDEN_CLAIM: E33 is always approved in one day. "
        "[ESCALATE]" + _KG_WORKFLOW_BLOCK
    )
    _mock_rag(
        monkeypatch,
        {
            "abstain": True,
            "abstain_reason": "e33_forbidden_claim",
            "answer": forbidden_canary,
        },
    )
    rows = [dict(_ROWS_NEWEST_FIRST[0], body=query), *_ROWS_NEWEST_FIRST[1:]]
    pool = _Pool(rows)

    outcome = await wa_inbox_bot.generate_bot_reply(pool, _thread())

    assert outcome.abstained is True
    assert outcome.reason == "e33_forbidden_claim"
    assert outcome.text == get_localized_stub("abstain", language)
    assert "CANARY_E33_FORBIDDEN_CLAIM" not in outcome.text
    assert "always approved" not in outcome.text


@pytest.mark.asyncio
async def test_unknown_abstain_reason_never_forwards_raw_answer(monkeypatch):
    """A future reason value cannot turn model-owned text back into a send."""
    monkeypatch.setenv("WA_INBOX_BOT_AUTOREPLY", "true")
    forbidden_canary = "CANARY_UNKNOWN_REASON_RAW_ANSWER"
    _mock_rag(
        monkeypatch,
        {
            "abstain": True,
            "abstain_reason": "future_unrecognized_reason",
            "answer": forbidden_canary,
        },
    )
    rows = [
        dict(_ROWS_NEWEST_FIRST[0], body="Serve un visto?"),
        *_ROWS_NEWEST_FIRST[1:],
    ]

    outcome = await wa_inbox_bot.generate_bot_reply(_Pool(rows), _thread())

    assert outcome == BotReply(
        text=get_localized_stub("abstain", "ITALIAN"),
        abstained=True,
        reason="future_unrecognized_reason",
    )
    assert forbidden_canary not in outcome.text


@pytest.mark.asyncio
async def test_short_followup_uses_existing_user_history_for_abstain_language(monkeypatch):
    """An ambiguous correction reuses the already-loaded thread history.

    This pins the no-second-DB-read contract: language detection receives the
    history returned by the same ``_load_thread_context`` fetch.
    """
    monkeypatch.setenv("WA_INBOX_BOT_AUTOREPLY", "true")
    _mock_rag(
        monkeypatch,
        {
            "abstain": True,
            "abstain_reason": "no_relevant_context",
            "answer": "CANARY_HISTORY_RAW_ANSWER",
        },
    )
    rows = [
        {"direction": "inbound", "sender_role": "customer", "body": "ok"},
        {
            "direction": "outbound",
            "sender_role": "bot",
            "body": "Puoi precisare?",
        },
        {
            "direction": "inbound",
            "sender_role": "customer",
            "body": "Vorrei aprire una società",
        },
    ]
    pool = _Pool(rows)

    outcome = await wa_inbox_bot.generate_bot_reply(pool, _thread())

    assert outcome.text == get_localized_stub("abstain", "ITALIAN")
    assert "CANARY_HISTORY_RAW_ANSWER" not in outcome.text
    assert pool._conn.fetchrow_calls == 0


@pytest.mark.asyncio
async def test_abstain_with_empty_rag_answer_still_returns_server_stub(monkeypatch):
    monkeypatch.setenv("WA_INBOX_BOT_AUTOREPLY", "true")
    _mock_rag(monkeypatch, {"abstain": True, "abstain_reason": "low_evidence", "answer": " "})
    rows = [
        dict(_ROWS_NEWEST_FIRST[0], body="Ciao, quanto costa un KITAS?"),
        *_ROWS_NEWEST_FIRST[1:],
    ]
    pool = _Pool(rows)

    outcome = await wa_inbox_bot.generate_bot_reply(pool, _thread())

    assert outcome == BotReply(
        text=get_localized_stub("abstain", "ITALIAN"),
        abstained=True,
        reason="low_evidence",
    )


@pytest.mark.asyncio
async def test_empty_answer_raises(monkeypatch):
    monkeypatch.setenv("WA_INBOX_BOT_AUTOREPLY", "true")
    _mock_rag(monkeypatch, {"abstain": False, "answer": "   "})
    pool = _Pool(_ROWS_NEWEST_FIRST)
    with pytest.raises(RuntimeError, match="empty RAG answer"):
        await wa_inbox_bot.generate_bot_reply(pool, _thread())


@pytest.mark.asyncio
async def test_happy_path_returns_answer_and_payload(monkeypatch):
    monkeypatch.setenv("WA_INBOX_BOT_AUTOREPLY", "true")
    captured = _mock_rag(
        monkeypatch,
        {"abstain": False, "answer": "Il KITAS investitore parte da..."},
    )
    pool = _Pool(_ROWS_NEWEST_FIRST)

    outcome = await wa_inbox_bot.generate_bot_reply(pool, _thread(thread_id=7, phone="62811"))

    assert outcome == BotReply(text="Il KITAS investitore parte da...")
    sent = captured["json"]
    # query = the LATEST inbound customer message
    assert sent["query"] == "Quanto costa un KITAS?"
    assert sent["channel"] == "whatsapp"
    assert sent["user_id"] == "whatsapp_62811"
    assert sent["session_id"] == "wa_meta_session_7"
    # history oldest→newest, EXCLUDING the query row → ["Ciao"(user), bot(assistant)]
    hist = sent["conversation_history"]
    assert hist == [
        {"role": "user", "content": "Ciao"},
        {"role": "assistant", "content": "Ciao! Come posso aiutarti?"},
    ]


@pytest.mark.asyncio
async def test_escalate_marker_stripped(monkeypatch):
    monkeypatch.setenv("WA_INBOX_BOT_AUTOREPLY", "true")
    _mock_rag(
        monkeypatch,
        {"abstain": False, "answer": "Ti metto in contatto col team [ESCALATE]"},
    )
    pool = _Pool(_ROWS_NEWEST_FIRST)
    outcome = await wa_inbox_bot.generate_bot_reply(pool, _thread())
    assert "[ESCALATE]" not in outcome.text
    assert outcome == BotReply(text="Ti metto in contatto col team")


# ── Client-voice hardening (2026-07-25): channel formatting + KG-workflow
# scaffold strip. Regression pinned to the exact production defect: raw
# markdown noise (headings/**bold**/bullets/bare citations) AND internal
# KG diagnostics ("## SUGGESTED WORKFLOW (from ..." through the literal
# "IMPORTANT: ..." trailer) were both being shipped verbatim to real
# WhatsApp clients. See _strip_kg_workflow_scaffold + format_rich_text.


_KG_WORKFLOW_BLOCK = (
    "\n## SUGGESTED WORKFLOW (from visa_subgraph, confidence: 78%)\n"
    "**KITAS Visa Processing** (visa_processing):\n"
    "\n1. Apply for TKA allocation quota and IMTA via SPKP system"
    "\n\n**Confidence**: medium — 3 source(s), relationship strength 90%"
    "\n\nIMPORTANT: This is a suggested workflow. Always verify current requirements with the user."
)


@pytest.mark.asyncio
async def test_markdown_and_kg_scaffold_stripped_for_whatsapp_client(monkeypatch):
    """Guilt: the exact production shape — a markdown-formatted answer with
    the KG workflow block appended — must come out WhatsApp-clean, with the
    internal scaffold fully removed (not just reformatted)."""
    raw_answer = (
        "Hey! Here is the official breakdown for the remote worker visa path.\n"
        "### Key Features\n"
        "*   **Initial Validity & Stay:** 1 year (365 days) ... [5]" + _KG_WORKFLOW_BLOCK
    )
    _mock_rag(monkeypatch, {"abstain": False, "answer": raw_answer})
    monkeypatch.setenv("WA_INBOX_BOT_AUTOREPLY", "true")
    pool = _Pool(_ROWS_NEWEST_FIRST)

    outcome = await wa_inbox_bot.generate_bot_reply(pool, _thread())

    # Internal scaffold fully gone.
    for scaffold_marker in (
        "SUGGESTED WORKFLOW",
        "KITAS Visa Processing",
        "TKA allocation quota",
        "Confidence**: medium",
        "IMPORTANT: This is a suggested workflow",
    ):
        assert scaffold_marker not in outcome.text, f"{scaffold_marker!r} leaked: {outcome.text!r}"
    # Raw markdown noise gone too.
    for md_marker in ("###", "**", "[5]"):
        assert md_marker not in outcome.text, f"{md_marker!r} leaked: {outcome.text!r}"
    # The real client-facing content survives, WhatsApp-formatted.
    assert "*Key Features*" in outcome.text
    assert "• *Initial Validity & Stay:*" in outcome.text
    assert "remote worker visa path" in outcome.text


@pytest.mark.asyncio
async def test_kg_workflow_scaffold_stripped_when_answer_is_only_scaffold(monkeypatch):
    """Guilt, edge case: if the RAG answer is NOTHING but the KG workflow
    block (no separate main answer — the KG fast-path shape), stripping it
    must leave nothing, and generate_bot_reply must raise rather than ever
    send an empty message — mirrors the existing empty-answer guards."""
    _mock_rag(monkeypatch, {"abstain": False, "answer": _KG_WORKFLOW_BLOCK.strip()})
    monkeypatch.setenv("WA_INBOX_BOT_AUTOREPLY", "true")
    pool = _Pool(_ROWS_NEWEST_FIRST)

    with pytest.raises(RuntimeError, match="empty after workflow-scaffold strip"):
        await wa_inbox_bot.generate_bot_reply(pool, _thread())


@pytest.mark.asyncio
async def test_kg_reasoning_after_workflow_block_survives_strip(monkeypatch):
    """Innocence: the KG fast-path can put the workflow block FIRST and
    legitimate reasoning/explanation text AFTER it (answer_parts joined
    with a blank line in orchestrator_core.py::_try_kg_fast_path). The
    strip must remove ONLY the scaffold span (start heading -> trailer
    sentence), never content that follows it."""
    raw_answer = _KG_WORKFLOW_BLOCK.strip() + "\n\nQuesto e' il KBLI 70100 per consulenza IT."
    _mock_rag(monkeypatch, {"abstain": False, "answer": raw_answer})
    monkeypatch.setenv("WA_INBOX_BOT_AUTOREPLY", "true")
    pool = _Pool(_ROWS_NEWEST_FIRST)

    outcome = await wa_inbox_bot.generate_bot_reply(pool, _thread())

    assert "SUGGESTED WORKFLOW" not in outcome.text
    assert "KBLI 70100 per consulenza IT" in outcome.text


@pytest.mark.asyncio
async def test_legitimate_workflow_mention_is_not_mangled(monkeypatch):
    """Innocence: an answer that merely uses the word 'workflow' in normal
    prose (not the literal KG heading) must pass through untouched by the
    scaffold strip — only the exact anchored heading triggers it."""
    raw_answer = "Il nostro workflow di onboarding prevede 3 passaggi molto semplici."
    _mock_rag(monkeypatch, {"abstain": False, "answer": raw_answer})
    monkeypatch.setenv("WA_INBOX_BOT_AUTOREPLY", "true")
    pool = _Pool(_ROWS_NEWEST_FIRST)

    outcome = await wa_inbox_bot.generate_bot_reply(pool, _thread())

    assert outcome == BotReply(text=raw_answer)


@pytest.mark.asyncio
async def test_legitimate_numbered_procedure_is_preserved(monkeypatch):
    """Innocence: a real client-relevant numbered procedure the consultant
    SHOULD send (not the KG scaffold shape — no '## SUGGESTED WORKFLOW'
    heading, no trailer sentence) must survive intact."""
    raw_answer = (
        "Ecco i passaggi per il tuo KITAS:\n"
        "1. Prepara il passaporto valido 6+ mesi\n"
        "2. Invia i documenti al team\n"
        "3. Paga la fattura"
    )
    _mock_rag(monkeypatch, {"abstain": False, "answer": raw_answer})
    monkeypatch.setenv("WA_INBOX_BOT_AUTOREPLY", "true")
    pool = _Pool(_ROWS_NEWEST_FIRST)

    outcome = await wa_inbox_bot.generate_bot_reply(pool, _thread())

    assert outcome == BotReply(text=raw_answer)


@pytest.mark.asyncio
async def test_oversized_reply_logs_non_silently(monkeypatch, caplog):
    """The single-send + hard-truncate behaviour downstream (whatsapp_service.py
    text[:4096]) is UNCHANGED here — this only proves the near-silent data
    loss is now logged with the pre-truncation length, out loud, before it
    happens, so a future chunking feature has real data to work from."""
    oversized = "A" * 5000
    _mock_rag(monkeypatch, {"abstain": False, "answer": oversized})
    monkeypatch.setenv("WA_INBOX_BOT_AUTOREPLY", "true")
    pool = _Pool(_ROWS_NEWEST_FIRST)

    with caplog.at_level("WARNING"):
        outcome = await wa_inbox_bot.generate_bot_reply(pool, _thread())

    assert outcome == BotReply(text=oversized)
    assert any(
        "5000 chars" in r.message and "exceeds WhatsApp" in r.message for r in caplog.records
    )


@pytest.mark.asyncio
async def test_reply_within_limit_does_not_log_warning(monkeypatch, caplog):
    """Innocence: an ordinary-length reply must not trip the new warning."""
    _mock_rag(monkeypatch, {"abstain": False, "answer": "Risposta breve e normale."})
    monkeypatch.setenv("WA_INBOX_BOT_AUTOREPLY", "true")
    pool = _Pool(_ROWS_NEWEST_FIRST)

    with caplog.at_level("WARNING"):
        await wa_inbox_bot.generate_bot_reply(pool, _thread())

    assert not any("exceeds WhatsApp" in r.message for r in caplog.records)


# ── Service-to-service auth header (X-Internal-Key) ──
# Regression guard for the silent-401 bug: /api/agentic-rag/query is not public,
# so the api→rag hop MUST carry X-Internal-Key or HybridAuthMiddleware rejects it
# with 401 → the worker marks every bot row failed → the bot never replies.


def test_rag_client_headers_sends_internal_key_when_configured(monkeypatch):
    monkeypatch.setattr(wa_inbox_bot.settings, "wa_mirror_internal_key", "secret-xyz")
    monkeypatch.setattr(wa_inbox_bot.settings, "wa_inbox_bot_profile_key", None)
    headers = wa_inbox_bot._rag_client_headers()
    assert headers == {"X-Internal-Key": "secret-xyz"}


def test_rag_client_headers_omits_internal_key_and_warns_when_unset(monkeypatch, caplog):
    monkeypatch.setattr(wa_inbox_bot.settings, "wa_mirror_internal_key", None)
    monkeypatch.setattr(wa_inbox_bot.settings, "wa_inbox_bot_profile_key", None)
    with caplog.at_level("WARNING"):
        headers = wa_inbox_bot._rag_client_headers()
    assert headers == {}
    assert any("WA_MIRROR_INTERNAL_KEY not configured" in r.message for r in caplog.records)


# ── P0-ID hardening: dedicated X-WA-Bot-Profile-Key (2026-07-24) ──
# Distinct from X-Internal-Key by design — see agentic_rag.py's
# `_verify_wa_inbox_bot_profile_key` for why the shared internal key alone
# was not enough to gate persona-override resolution safely.


def test_rag_client_headers_sends_both_keys_when_both_configured(monkeypatch):
    monkeypatch.setattr(wa_inbox_bot.settings, "wa_mirror_internal_key", "secret-xyz")
    monkeypatch.setattr(wa_inbox_bot.settings, "wa_inbox_bot_profile_key", "bot-only-secret")
    headers = wa_inbox_bot._rag_client_headers()
    assert headers == {
        "X-Internal-Key": "secret-xyz",
        "X-WA-Bot-Profile-Key": "bot-only-secret",
    }


def test_rag_client_headers_omits_profile_key_and_warns_when_unset(monkeypatch, caplog):
    """Innocence: an unset profile key degrades gracefully — the query
    itself must still be sent (X-Internal-Key alone is enough for that),
    only the persona-override channel is silently unavailable."""
    monkeypatch.setattr(wa_inbox_bot.settings, "wa_mirror_internal_key", "secret-xyz")
    monkeypatch.setattr(wa_inbox_bot.settings, "wa_inbox_bot_profile_key", None)
    with caplog.at_level("WARNING"):
        headers = wa_inbox_bot._rag_client_headers()
    assert headers == {"X-Internal-Key": "secret-xyz"}
    assert any("WA_INBOX_BOT_PROFILE_KEY not configured" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_get_rag_client_applies_internal_key_header(monkeypatch):
    """End-to-end: the cached client carries both service-auth headers."""
    monkeypatch.setattr(wa_inbox_bot, "_rag_client", None)
    monkeypatch.setattr(wa_inbox_bot.settings, "wa_mirror_internal_key", "secret-xyz")
    monkeypatch.setattr(wa_inbox_bot.settings, "wa_inbox_bot_profile_key", "bot-only-secret")
    monkeypatch.setattr(wa_inbox_bot, "get_rag_worker_url", lambda: "http://rag.internal:8080")
    client = await wa_inbox_bot._get_rag_client()
    try:
        assert client.headers.get("x-internal-key") == "secret-xyz"
        assert client.headers.get("x-wa-bot-profile-key") == "bot-only-secret"
    finally:
        await client.aclose()
        wa_inbox_bot._rag_client = None


# ── P9: admission semaphore bounding concurrent RAG calls ──────────────────


def test_bot_generation_semaphore_defaults_to_3(monkeypatch):
    monkeypatch.delenv("WA_BOT_MAX_CONCURRENT_GENERATIONS", raising=False)
    monkeypatch.setattr(wa_inbox_bot, "_bot_generation_semaphore", None)
    sem = wa_inbox_bot._get_bot_generation_semaphore()
    assert sem._value == 3


def test_bot_generation_semaphore_env_override(monkeypatch):
    monkeypatch.setattr(wa_inbox_bot, "_bot_generation_semaphore", None)
    monkeypatch.setenv("WA_BOT_MAX_CONCURRENT_GENERATIONS", "7")
    sem = wa_inbox_bot._get_bot_generation_semaphore()
    assert sem._value == 7


def test_bot_generation_semaphore_invalid_env_falls_back_to_3(monkeypatch):
    monkeypatch.setattr(wa_inbox_bot, "_bot_generation_semaphore", None)
    monkeypatch.setenv("WA_BOT_MAX_CONCURRENT_GENERATIONS", "not-a-number")
    sem = wa_inbox_bot._get_bot_generation_semaphore()
    assert sem._value == 3


def test_bot_generation_semaphore_is_a_singleton(monkeypatch):
    monkeypatch.setattr(wa_inbox_bot, "_bot_generation_semaphore", None)
    monkeypatch.setenv("WA_BOT_MAX_CONCURRENT_GENERATIONS", "2")
    first = wa_inbox_bot._get_bot_generation_semaphore()
    # a second env value must NOT retroactively resize an already-built semaphore
    monkeypatch.setenv("WA_BOT_MAX_CONCURRENT_GENERATIONS", "9")
    second = wa_inbox_bot._get_bot_generation_semaphore()
    assert first is second
    assert second._value == 2


@pytest.mark.asyncio
async def test_bot_generation_semaphore_bounds_concurrent_rag_calls(monkeypatch):
    """5 concurrent generate_bot_reply calls with max_concurrent=2 must never
    have more than 2 RAG POSTs in flight at once."""
    monkeypatch.setenv("WA_INBOX_BOT_AUTOREPLY", "true")
    monkeypatch.setattr(wa_inbox_bot, "_bot_generation_semaphore", None)
    monkeypatch.setenv("WA_BOT_MAX_CONCURRENT_GENERATIONS", "2")

    in_flight = 0
    max_in_flight = 0
    lock = asyncio.Lock()

    resp = MagicMock()
    resp.raise_for_status = MagicMock(return_value=None)
    resp.json = MagicMock(return_value={"abstain": False, "answer": "ok"})

    async def _post(url: str, json: dict[str, Any]) -> Any:
        nonlocal in_flight, max_in_flight
        async with lock:
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.05)
        async with lock:
            in_flight -= 1
        return resp

    client = MagicMock()
    client.post = AsyncMock(side_effect=_post)

    async def _get_client() -> Any:
        return client

    monkeypatch.setattr(wa_inbox_bot, "_get_rag_client", _get_client)

    pool = _Pool(_ROWS_NEWEST_FIRST)
    results = await asyncio.gather(
        *[wa_inbox_bot.generate_bot_reply(pool, _thread(thread_id=i)) for i in range(5)]
    )

    assert results == [BotReply(text="ok")] * 5
    assert max_in_flight <= 2
    assert client.post.await_count == 5


def test_import_boundary_does_not_load_agentic_or_sklearn() -> None:
    """The API-side generator must stay independent of the RAG package graph."""
    backend_root = Path(__file__).resolve().parents[4]
    probe = """
import sys
import backend.services.integrations.wa_inbox_bot  # noqa: F401

forbidden = sorted(
    name
    for name in sys.modules
    if name == "backend.services.rag.agentic"
    or name.startswith("backend.services.rag.agentic.")
    or name == "sklearn"
    or name.startswith("sklearn.")
)
if forbidden:
    raise SystemExit("forbidden modules loaded: " + ", ".join(forbidden))
"""
    env = {**os.environ, "PYTHONPATH": "."}
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=backend_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr

    source_path = Path(wa_inbox_bot.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    forbidden_imports = [
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module
        and node.module.startswith("backend.services.rag.agentic")
    ]
    assert forbidden_imports == []


# ── P0-ID containment (2026-07-24): no client-side profile field anymore ──
# Team-assistant V1 (2026-07-19) used to resolve the sender's identity HERE
# and forward it as an explicit `profile` request field. That mechanism was
# removed: the RAG router now re-derives the same identity server-side
# (`agentic_rag.py::_resolve_trusted_wa_profile`) from `user_id`, so a
# client-declared `profile` can never be forged. These tests assert the new
# innocence contract: `generate_bot_reply`'s payload NEVER carries a
# `profile` key, and NEVER calls a DB-backed identity lookup of its own,
# regardless of whether the sender is owner/team/client/unknown or the DB
# is down — that work is no longer this function's job.


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("owner_env", "team_env", "fetchrow_result", "fetchrow_error", "phone"),
    [
        pytest.param("62811000111", None, None, None, "62811000111", id="owner"),
        pytest.param(
            None, "62811000222:Test Member Alpha", None, None, "62811000222", id="team-env"
        ),
        pytest.param(
            None,
            None,
            {"id": "tm-1", "display_name": "Test Member Beta", "email": "beta@balizero.com"},
            None,
            "62811000333",
            id="team-db",
        ),
        pytest.param(None, None, None, None, "62899999999", id="unknown"),
        pytest.param(
            None,
            None,
            None,
            asyncpg.PostgresError("db down"),
            "62899999999",
            id="db-down",
        ),
    ],
)
async def test_payload_never_carries_a_profile_key(
    monkeypatch, owner_env, team_env, fetchrow_result, fetchrow_error, phone
):
    monkeypatch.setenv("WA_INBOX_BOT_AUTOREPLY", "true")
    if owner_env:
        monkeypatch.setenv("WHATSAPP_OWNER_NUMBERS", owner_env)
    else:
        monkeypatch.delenv("WHATSAPP_OWNER_NUMBERS", raising=False)
    if team_env:
        monkeypatch.setenv("WHATSAPP_TEAM_NUMBERS", team_env)
    else:
        monkeypatch.delenv("WHATSAPP_TEAM_NUMBERS", raising=False)
    captured = _mock_rag(monkeypatch, {"abstain": False, "answer": "ok"})
    pool = _Pool(_ROWS_NEWEST_FIRST, fetchrow_result=fetchrow_result, fetchrow_error=fetchrow_error)

    await wa_inbox_bot.generate_bot_reply(pool, _thread(phone=phone))

    sent = captured["json"]
    assert "profile" not in sent
    # fetchrow (team/client DB lookups) would only ever fire from a local
    # identity resolution — asserting it was never called proves the
    # function truly stopped resolving identity itself, not just that it
    # happened to drop the key afterward.
    assert pool._conn.fetchrow_calls == 0
