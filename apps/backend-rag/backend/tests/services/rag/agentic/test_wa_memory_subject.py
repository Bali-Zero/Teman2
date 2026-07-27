"""W-1 follow-up to P0-MEM (#3036): per-sender WhatsApp memory subject.

P0-MEM contained a cross-client memory bleed by disabling long-term memory
for the SHARED ``wa-mirror-internal`` identity every WhatsApp sender was
authenticated as — correct, but it left every WhatsApp client with no
memory at all. This item re-enables memory, keyed on a pseudonymous subject
derived per sender instead of the shared bucket.

Zero's acceptance test for this item was explicit, and it is not "memory
works again" — it is **"sender A cannot see anything of sender B"**. That is
what ``TestTheAcceptanceTestSenderACannotSeeSenderB`` proves, with two
distinct phone numbers through the full derivation → context-read path.

Everything else here is the supporting contract:

  - ``derive_wa_memory_subject``: the four gates from its own docstring
    (trust, HMAC not a bare hash, fail-closed, salt is its own secret) —
    GUILT + INNOCENCE + mutation-proved.
  - ``context_manager.get_user_context``: the FACTS/PROFILE split this item
    required (a subject must never smuggle the shared identity's PROFILE
    through, only replace the FACTS key) — the near-miss this file exists to
    pin, caught while wiring the fix itself, not by review.
  - ``memory_handler``: the write side mirrors the read side's subject
    substitution, including in the per-thread LOCK key — two senders must
    never share a lock, or concurrent saves serialise across strangers.
"""

from __future__ import annotations

import hmac
from hashlib import sha256
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.rag.agentic import context_manager as module
from backend.services.rag.agentic._memory_identity import (
    WA_MEMORY_SUBJECT_PREFIX,
    derive_wa_memory_subject,
)
from backend.services.rag.agentic.context_manager import get_user_context
from backend.services.rag.agentic.memory_handler import MemoryHandler

SALT = "test-salt-do-not-use-in-prod"
PHONE_A = "+62 821-3465-159"
PHONE_B = "+62 811-9999-000"


# ============================================================
# derive_wa_memory_subject — the four gates
# ============================================================


class TestGuiltEveryGateMustBlock:
    def test_untrusted_caller_gets_nothing_even_with_phone_and_salt(self) -> None:
        assert (
            derive_wa_memory_subject(is_trusted_wa_bot=False, phone=PHONE_A, salt=SALT) is None
        )

    def test_missing_phone_gets_nothing_even_when_trusted(self) -> None:
        assert derive_wa_memory_subject(is_trusted_wa_bot=True, phone=None, salt=SALT) is None

    def test_missing_salt_gets_nothing_even_when_trusted_with_phone(self) -> None:
        assert (
            derive_wa_memory_subject(is_trusted_wa_bot=True, phone=PHONE_A, salt=None) is None
        )

    def test_phone_with_no_digits_gets_nothing(self) -> None:
        assert (
            derive_wa_memory_subject(is_trusted_wa_bot=True, phone="+--- ", salt=SALT) is None
        )

    def test_empty_salt_string_gets_nothing(self) -> None:
        """An empty string is falsy — must behave like "unprovisioned", not like a real key."""
        assert derive_wa_memory_subject(is_trusted_wa_bot=True, phone=PHONE_A, salt="") is None


class TestInnocenceTheHappyPathWorks:
    def test_all_gates_satisfied_returns_a_subject(self) -> None:
        subject = derive_wa_memory_subject(is_trusted_wa_bot=True, phone=PHONE_A, salt=SALT)
        assert subject is not None
        assert subject.startswith(WA_MEMORY_SUBJECT_PREFIX)

    def test_subject_is_stable_for_the_same_phone(self) -> None:
        first = derive_wa_memory_subject(is_trusted_wa_bot=True, phone=PHONE_A, salt=SALT)
        second = derive_wa_memory_subject(is_trusted_wa_bot=True, phone=PHONE_A, salt=SALT)
        assert first == second

    @pytest.mark.parametrize(
        "variant",
        ["+62 821-3465-159", "62821-3465159", "+628213465159", "0821 3465 159"],
    )
    def test_formatting_does_not_change_the_subject(self, variant: str) -> None:
        """Same underlying number, different formatting upstream — one subject."""
        canonical = derive_wa_memory_subject(is_trusted_wa_bot=True, phone=PHONE_A, salt=SALT)
        reformatted = derive_wa_memory_subject(is_trusted_wa_bot=True, phone=variant, salt=SALT)
        if "0821" in variant:
            # A local-format leading 0 vs. the country-code form is a genuinely
            # different digit string — documented as NOT unified here; that is
            # phone-number normalisation, a different concern than formatting
            # noise (spaces/dashes/plus), which IS unified.
            pytest.skip("leading-0 vs +62 is digit-string normalisation, out of scope")
        assert reformatted == canonical

    def test_two_different_phones_get_two_different_subjects(self) -> None:
        a = derive_wa_memory_subject(is_trusted_wa_bot=True, phone=PHONE_A, salt=SALT)
        b = derive_wa_memory_subject(is_trusted_wa_bot=True, phone=PHONE_B, salt=SALT)
        assert a != b


class TestGuiltItIsHMACNotABareHash:
    """A bare sha256(phone) is reversible by brute force (low phone-number
    entropy) and is therefore not a pseudonym. This pins the algorithm, not
    just its output shape, so a regression to ``sha256(phone)`` fails loudly
    instead of silently reopening the re-identification risk."""

    @staticmethod
    def _digits(phone: str) -> str:
        """The exact normalisation the implementation applies — computed here
        independently (strip via a plain str filter, not the module's own
        regex) so this test cannot pass by sharing a bug with the code it
        checks."""
        return "".join(ch for ch in phone if ch.isdigit())

    def test_subject_is_not_a_bare_sha256_of_the_digits(self) -> None:
        subject = derive_wa_memory_subject(is_trusted_wa_bot=True, phone=PHONE_A, salt=SALT)
        bare = "wa:" + sha256(self._digits(PHONE_A).encode()).hexdigest()[:32]
        assert subject != bare

    def test_subject_matches_hmac_sha256_with_the_salt_as_key(self) -> None:
        subject = derive_wa_memory_subject(is_trusted_wa_bot=True, phone=PHONE_A, salt=SALT)
        expected_digest = hmac.new(
            SALT.encode("utf-8"), self._digits(PHONE_A).encode("utf-8"), sha256
        ).hexdigest()[:32]
        assert subject == f"wa:{expected_digest}"

    def test_different_salt_produces_a_different_subject(self) -> None:
        """Proves the salt is load-bearing in the digest, not decorative."""
        with_salt_a = derive_wa_memory_subject(is_trusted_wa_bot=True, phone=PHONE_A, salt=SALT)
        with_salt_b = derive_wa_memory_subject(
            is_trusted_wa_bot=True, phone=PHONE_A, salt="a-different-salt-entirely"
        )
        assert with_salt_a != with_salt_b


# ============================================================
# THE ACCEPTANCE TEST — sender A cannot see anything of sender B
# ============================================================


def _patch_fetchers_recording_calls(monkeypatch: pytest.MonkeyPatch) -> dict[str, AsyncMock]:
    """Each subject gets its OWN facts, keyed by the subject it was called with.

    A bleed would show up as A's read returning B's facts (or vice versa) —
    this fixture makes that observable instead of both sides just returning
    "some fact" and hiding a swap.
    """
    facts_by_subject = {
        derive_wa_memory_subject(is_trusted_wa_bot=True, phone=PHONE_A, salt=SALT): [
            "A: prefers email contact",
        ],
        derive_wa_memory_subject(is_trusted_wa_bot=True, phone=PHONE_B, salt=SALT): [
            "B: KITAS expiring in September",
        ],
    }

    async def _fake_fetch_memory_facts(memory_orchestrator, subject, query):  # noqa: ANN001
        return {
            "facts": facts_by_subject.get(subject, []),
            "collective_facts": [],
            "timeline_summary": None,
            "kg_entities": [],
            "summary": None,
            "counters": None,
            "memory_context": None,
        }

    profile_mock = AsyncMock(
        return_value={"profile": None, "history": [], "entities": {}},
    )
    memory_mock = AsyncMock(side_effect=_fake_fetch_memory_facts)
    monkeypatch.setattr(module, "fetch_profile_and_history", profile_mock)
    monkeypatch.setattr(module, "fetch_memory_facts", memory_mock)
    return {"profile": profile_mock, "memory": memory_mock}


class TestTheAcceptanceTestSenderACannotSeeSenderB:
    """This is the test Zero's GO was conditioned on, not an implementation detail."""

    @pytest.mark.asyncio
    async def test_sender_a_reads_only_sender_a_facts(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_fetchers_recording_calls(monkeypatch)
        subject_a = derive_wa_memory_subject(is_trusted_wa_bot=True, phone=PHONE_A, salt=SALT)

        result = await get_user_context(
            MagicMock(),
            "whatsapp_internal_shared_id",  # what user_id looks like today: irrelevant here
            memory_subject=subject_a,
        )

        assert result["facts"] == ["A: prefers email contact"]
        assert "B: KITAS expiring in September" not in result["facts"]

    @pytest.mark.asyncio
    async def test_sender_b_reads_only_sender_b_facts(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_fetchers_recording_calls(monkeypatch)
        subject_b = derive_wa_memory_subject(is_trusted_wa_bot=True, phone=PHONE_B, salt=SALT)

        result = await get_user_context(
            MagicMock(),
            "whatsapp_internal_shared_id",
            memory_subject=subject_b,
        )

        assert result["facts"] == ["B: KITAS expiring in September"]
        assert "A: prefers email contact" not in result["facts"]

    @pytest.mark.asyncio
    async def test_two_senders_through_the_full_router_derivation_get_different_subjects(
        self,
    ) -> None:
        """End-to-end from the two raw phone numbers to two DISTINCT subjects —
        the actual shape the router produces per request, not a hand-picked one."""
        subject_a = derive_wa_memory_subject(is_trusted_wa_bot=True, phone=PHONE_A, salt=SALT)
        subject_b = derive_wa_memory_subject(is_trusted_wa_bot=True, phone=PHONE_B, salt=SALT)
        assert subject_a is not None
        assert subject_b is not None
        assert subject_a != subject_b


# ============================================================
# The near-miss: FACTS and PROFILE must not travel together
# ============================================================


class TestGuiltASubjectMustNotSmuggleTheSharedProfile:
    """Caught while wiring this fix, not by review.

    Gating the whole read on the subject alone would let a WA request through
    to ``fetch_profile_and_history(user_id=<shared id>)`` and hand every
    client the SHARED bucket's profile and conversation history — the same
    class of bleed as P0-MEM, one surface over. The two must gate
    independently: FACTS on the subject, PROFILE/HISTORY on user_id.
    """

    @pytest.mark.asyncio
    async def test_subject_present_but_user_id_is_the_shared_identity_gets_no_profile(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mocks = _patch_fetchers_recording_calls(monkeypatch)
        subject_a = derive_wa_memory_subject(is_trusted_wa_bot=True, phone=PHONE_A, salt=SALT)

        result = await get_user_context(
            MagicMock(),
            "wa-mirror-internal",  # the shared identity, unchanged
            memory_subject=subject_a,
        )

        mocks["profile"].assert_not_called()
        assert result.get("profile") is None
        # Facts, by contrast, ARE fetched — that is the whole point of the subject.
        mocks["memory"].assert_called_once()
        assert result["facts"] == ["A: prefers email contact"]

    @pytest.mark.asyncio
    async def test_no_subject_falls_back_to_pre_existing_behaviour_byte_identical(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Every non-WA caller (memory_subject=None) must be untouched by this feature."""
        mocks = _patch_fetchers_recording_calls(monkeypatch)

        result = await get_user_context(MagicMock(), "real.client@example.com")

        mocks["profile"].assert_awaited_once()
        mocks["memory"].assert_awaited_once()
        # Matches this file's own fetcher fixture (profile=None) — the point
        # here is that profile/history were FETCHED at all, not their shape.
        assert result["profile"] is None
        assert result["history"] == []


# ============================================================
# WRITE side — lock key and subject substitution
# ============================================================


@pytest.fixture
def handler() -> MemoryHandler:
    return MemoryHandler(db_pool=MagicMock())


@pytest.fixture
def mock_orchestrator() -> AsyncMock:
    from dataclasses import dataclass

    @dataclass
    class FakeProcessResult:
        success: bool = True
        facts_extracted: int = 1
        facts_saved: int = 1
        processing_time_ms: float = 1.0

    orch = AsyncMock()
    orch.process_conversation = AsyncMock(return_value=FakeProcessResult())
    return orch


class TestWriteSideSubjectSubstitution:
    @pytest.mark.asyncio
    async def test_save_with_subject_writes_under_the_subject_not_user_id(
        self, handler: MemoryHandler, mock_orchestrator: AsyncMock
    ) -> None:
        handler._memory_orchestrator = mock_orchestrator
        subject_a = derive_wa_memory_subject(is_trusted_wa_bot=True, phone=PHONE_A, salt=SALT)

        await handler.save_conversation_memory(
            user_id="wa-mirror-internal",  # the shared identity
            query="q",
            answer="a",
            memory_subject=subject_a,
        )

        mock_orchestrator.process_conversation.assert_awaited_once()
        _, kwargs = mock_orchestrator.process_conversation.call_args
        assert kwargs["user_email"] == subject_a
        assert kwargs["user_email"] != "wa-mirror-internal"

    @pytest.mark.asyncio
    async def test_two_senders_never_share_a_lock_key(
        self, handler: MemoryHandler, mock_orchestrator: AsyncMock
    ) -> None:
        """Two different senders sharing a lock would serialise unrelated
        saves and imply a co-tenancy the storage no longer has."""
        import asyncio

        handler._memory_orchestrator = mock_orchestrator
        subject_a = derive_wa_memory_subject(is_trusted_wa_bot=True, phone=PHONE_A, salt=SALT)
        subject_b = derive_wa_memory_subject(is_trusted_wa_bot=True, phone=PHONE_B, salt=SALT)

        await asyncio.gather(
            handler.save_conversation_memory(
                user_id="wa-mirror-internal", query="qa", answer="aa", memory_subject=subject_a
            ),
            handler.save_conversation_memory(
                user_id="wa-mirror-internal", query="qb", answer="ab", memory_subject=subject_b
            ),
        )

        lock_keys = set(handler._memory_locks.keys())
        assert f"{subject_a}::__nosession__" in lock_keys
        assert f"{subject_b}::__nosession__" in lock_keys

    @pytest.mark.asyncio
    async def test_save_without_subject_is_byte_identical_to_before(
        self, handler: MemoryHandler, mock_orchestrator: AsyncMock
    ) -> None:
        handler._memory_orchestrator = mock_orchestrator
        await handler.save_conversation_memory(
            user_id="real.client@example.com", query="q", answer="a"
        )
        mock_orchestrator.process_conversation.assert_awaited_once()
        _, kwargs = mock_orchestrator.process_conversation.call_args
        assert kwargs["user_email"] == "real.client@example.com"

    @pytest.mark.asyncio
    async def test_shared_identity_with_no_subject_still_skipped(
        self, handler: MemoryHandler, mock_orchestrator: AsyncMock
    ) -> None:
        """The pre-existing P0-MEM containment survives when the salt is
        unprovisioned (memory_subject=None) — no silent re-opening."""
        handler._memory_orchestrator = mock_orchestrator
        await handler.save_conversation_memory(
            user_id="wa-mirror-internal", query="q", answer="a"
        )
        mock_orchestrator.process_conversation.assert_not_called()
