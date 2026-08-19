"""wa_finalize — the codex-leg additions the extraction introduced.

The Gemini-leg behavior of ``finalize_wa_answer`` is proven by the PRE-EXISTING
suites, which drive it through ``wa_inbox_bot.generate_bot_reply`` unchanged
(``test_wa_inbox_bot.py``, ``test_wa_abstain_reaches_a_human.py``,
``test_wa_abstain_with_content_is_sent.py``). This file covers what is NEW:
the typed-outcome mapping for the codex provider (TEXT_DEFECT fails off
silently, POLICY behaves like the Gemini leg), the fail-closed configuration
contract, the structural checks inside the abstain branch (PR-3 adversarial
review BLOCKER-1), and the two codex egress vetoes — each with guilt AND
innocence cases, per cicatrix family #3.
"""

from __future__ import annotations

from typing import Any

import pytest

from backend.services.integrations.wa_finalize import (
    _KG_WORKFLOW_TRAILER,
    _WHATSAPP_HARD_SEND_LIMIT,
    FinalizeOutcome,
    finalize_wa_answer,
    price_tokens_outside_sources,
    scan_text_for_secret_egress,
)

# Long enough to clear _ABSTAIN_MIN_SENDABLE_CHARS after cleaning/formatting.
_REAL_ANSWER = (
    "To establish a PT PMA in Indonesia you follow these steps. First choose the "
    "business sector and verify the KBLI codes allow foreign ownership. Then "
    "reserve the company name and notarize the deed of establishment. After the "
    "SK Kemenkumham is issued you register on OSS for the NIB, then obtain the "
    "NPWP and any sector licenses your KBLI requires."
)

_SCAFFOLD_ONLY = (
    "## SUGGESTED WORKFLOW (from graph_traversal, confidence: 90%)\n"
    "1. Do the thing\n2. Do the next thing\n" + _KG_WORKFLOW_TRAILER
)


class _Tell:
    """Recording stand-in for the caller's tell_a_human callback."""

    def __init__(self) -> None:
        self.reasons: list[str] = []

    async def __call__(self, reason: str) -> bool:
        self.reasons.append(reason)
        return True


def _payload(answer: str, *, abstain: bool = False, ctx: int = 3, ev: float = 0.5) -> dict[str, Any]:
    return {
        "answer": answer,
        "abstain": abstain,
        "abstain_reason": "below_domain_threshold" if abstain else None,
        "context_length": ctx,
        "evidence_score": ev,
    }


async def _run(data: dict[str, Any], *, provider: str, tell: _Tell, **kw: Any):
    if provider == "codex":
        # The codex configuration is MANDATORY (fail-closed contract) — tests
        # that probe the missing-config error call finalize_wa_answer directly.
        kw.setdefault("price_sources", [])
        kw.setdefault("secret_scan", True)
    return await finalize_wa_answer(
        data=data,
        query="How do I open a PT PMA?",
        thread_id=42,
        provider=provider,
        tell_a_human=tell,
        **kw,
    )


# ── Pricing veto (pure function): guilt and innocence ────────────────────


def test_pricing_veto_catches_an_amount_absent_from_every_source() -> None:
    offenders = price_tokens_outside_sources(
        "The service costs Rp 5.000.000 all-inclusive.",
        ["Company setup — Rp 3.500.000, duration 30 days"],
    )
    assert offenders == ["IDR:5000000"]


def test_pricing_veto_matches_amounts_across_separator_formats() -> None:
    # Answer uses commas, source uses dots — same canonical value, no veto.
    assert (
        price_tokens_outside_sources(
            "It costs Rp 3,500,000 in total.",
            ['{"price": "Rp 3.500.000"}'],
        )
        == []
    )


def test_pricing_veto_canonicalizes_multipliers_both_ways() -> None:
    # "Rp 3,5 juta" in the answer is the same price as "Rp 3.500.000" in the
    # block; "Rp 99 juta" absent from every source is an invented price and
    # must be vetoed (review MAJOR-5 — a made-up price cannot hide behind
    # its spelling).
    assert (
        price_tokens_outside_sources("Biaya: Rp 3,5 juta.", ["Rp 3.500.000"]) == []
    )
    assert price_tokens_outside_sources(
        "Our fee is Rp 99 juta.", ["Company setup — Rp 3.500.000"]
    ) == ["IDR:99000000"]


def test_pricing_veto_catches_small_dollar_amounts() -> None:
    # Review MAJOR-5: "$999" is a real price shape; the IDR floor must not
    # shield dollar amounts.
    assert price_tokens_outside_sources("$999 flat.", ["no prices"]) == ["USD:999"]


def test_pricing_veto_amount_never_crosses_a_newline() -> None:
    # Review MAJOR-6 reproduced: "Rp 3.500.000\n30 days" must parse as
    # 3500000 (present in sources → no veto), never as 350000030.
    assert (
        price_tokens_outside_sources(
            "Fee Rp 3.500.000\n30 days processing.",
            ["Company setup — Rp 3.500.000"],
        )
        == []
    )


def test_pricing_veto_sources_are_tokenized_never_concatenated() -> None:
    # Review MAJOR-7 reproduced: a source holding "Rp 12.345" then "67 days"
    # must NOT authorize an invented "Rp 34.567" via the concatenation
    # artifact "1234567".
    assert price_tokens_outside_sources(
        "Total Rp 34.567.", ["Item Rp 12.345, duration 67 days"]
    ) == ["IDR:34567"]


def test_pricing_veto_ignores_amounts_without_a_currency_marker() -> None:
    # "2,5 miliar" is a regulatory capital figure from retrieved chunks, not a
    # price — currency-anchored scope means it must never be vetoed.
    assert (
        price_tokens_outside_sources(
            "The minimum paid-up capital is 2,5 miliar rupiah per BKPM 5/2025.",
            ["unrelated source"],
        )
        == []
    )


def test_pricing_veto_floor_skips_noise_amounts() -> None:
    # "Rp 5" (per page, say) is below any real IDR price — noise, not a price.
    assert price_tokens_outside_sources("Rp 5 per page.", ["no numbers"]) == []


# ── Secret-egress scan (pure function): guilt and innocence ──────────────


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("-----BEGIN OPENSSH PRIVATE KEY-----\nabc", "private_key_block"),
        ("here sk-" + "a" * 24 + " is the key", "openai_style_key"),
        ("eyJ" + "a" * 12 + "." + "b" * 12 + "." + "c" * 12, "jwt"),
        ('config: api_key = "' + "x" * 20 + '"', "token_assignment"),
        # Review MAJOR-4 reproduced: JSON auth-file fragment (quoted key) and
        # a bare Bearer header value must both be caught.
        ('"refresh_token":"1//opaque-long-token0"', "token_assignment"),
        ("Authorization: Bearer opaque-token-12345", "bearer_token"),
        ("use Bearer opaque-token-1234567 to call it", "bearer_token"),
    ],
)
def test_secret_scan_names_the_pattern_without_the_content(text: str, expected: str) -> None:
    assert scan_text_for_secret_egress(text) == expected


def test_secret_scan_catches_a_canary_token() -> None:
    assert (
        scan_text_for_secret_egress("…CANARY-9f3a-token…", canary_tokens=("CANARY-9f3a-token",))
        == "canary_token"
    )


def test_secret_scan_passes_ordinary_consulting_prose() -> None:
    assert (
        scan_text_for_secret_egress(
            "You will need an API key from the OSS system to submit the LKPM "
            "report; the access token is issued after NIB registration. The "
            "bearer of the visa must keep the passport valid."
        )
        is None
    )


# ── Fail-closed configuration (review BLOCKER-2 / MAJOR-3) ───────────────


@pytest.mark.asyncio
async def test_codex_without_vetoes_configured_raises_not_fail_open() -> None:
    with pytest.raises(ValueError, match="fail-open"):
        await finalize_wa_answer(
            data=_payload(_REAL_ANSWER),
            query="q",
            thread_id=42,
            provider="codex",
            tell_a_human=_Tell(),
        )


@pytest.mark.asyncio
async def test_unknown_provider_string_raises() -> None:
    with pytest.raises(ValueError):
        await finalize_wa_answer(
            data=_payload(_REAL_ANSWER),
            query="q",
            thread_id=42,
            provider="Codex",  # typo case — must never silently mean gemini
            tell_a_human=_Tell(),
        )


@pytest.mark.asyncio
async def test_a_raising_tell_callback_is_contained() -> None:
    async def _boom(reason: str) -> None:
        raise RuntimeError("notifier down")

    result = await finalize_wa_answer(
        data=_payload("short", abstain=True, ctx=0, ev=0.0),
        query="q",
        thread_id=42,
        provider="gemini",
        tell_a_human=_boom,
    )
    # The stub outcome survives the notifier failure.
    assert result.outcome is FinalizeOutcome.SEND
    assert result.human_reason == "rag_abstain"


# ── Codex typed outcomes: TEXT_DEFECT fails off silently ─────────────────


@pytest.mark.asyncio
async def test_codex_monologue_leak_is_a_silent_defect() -> None:
    tell = _Tell()
    result = await _run(
        _payload("Internal monologue: the user wants X…"), provider="codex", tell=tell
    )
    assert result.outcome is FinalizeOutcome.DEFECT
    assert result.defect_reason == "internal_monologue_leak"
    # Fail-off, not an incident: the Gemini leg still owes the client an answer.
    assert tell.reasons == []


@pytest.mark.asyncio
async def test_codex_scaffold_only_output_is_a_silent_defect() -> None:
    tell = _Tell()
    result = await _run(_payload(_SCAFFOLD_ONLY), provider="codex", tell=tell)
    assert result.outcome is FinalizeOutcome.DEFECT
    assert result.defect_reason == "workflow_only_output"
    assert tell.reasons == []


@pytest.mark.asyncio
async def test_empty_answer_tells_a_human_on_gemini_but_not_on_codex() -> None:
    gemini_tell, codex_tell = _Tell(), _Tell()
    gemini = await _run(_payload(""), provider="gemini", tell=gemini_tell)
    codex = await _run(_payload(""), provider="codex", tell=codex_tell)
    assert gemini.outcome is FinalizeOutcome.DEFECT
    assert codex.outcome is FinalizeOutcome.DEFECT
    assert gemini.defect_reason == codex.defect_reason == "empty_rag_answer"
    # Same message the pre-extraction RuntimeError carried, so the worker
    # ledger vocabulary is unchanged.
    assert gemini.defect_message == "wa-inbox bot: empty RAG answer for thread 42"
    assert gemini_tell.reasons == ["empty_rag_answer"]
    assert codex_tell.reasons == []


@pytest.mark.asyncio
async def test_codex_oversized_output_is_a_defect_but_gemini_warns_and_sends() -> None:
    # Review MAJOR-8: spec §2.3 classes oversized output as TEXT_DEFECT on
    # the codex leg; the Gemini leg keeps today's warn-and-let-the-sender-cut.
    huge = "PT PMA setup notes. " + ("word " * ((_WHATSAPP_HARD_SEND_LIMIT // 5) + 200))
    codex = await _run(_payload(huge), provider="codex", tell=_Tell())
    gemini = await _run(_payload(huge), provider="gemini", tell=_Tell())
    assert codex.outcome is FinalizeOutcome.DEFECT
    assert codex.defect_reason == "oversized_output"
    assert gemini.outcome is FinalizeOutcome.SEND


# ── Abstain branch: POLICY parity + structural checks (BLOCKER-1) ────────


@pytest.mark.asyncio
async def test_codex_ungrounded_abstain_serves_the_stub_and_tells_a_human() -> None:
    tell = _Tell()
    result = await _run(
        _payload("short refusal", abstain=True, ctx=0, ev=0.0), provider="codex", tell=tell
    )
    assert result.outcome is FinalizeOutcome.SEND
    assert result.human_reason == "rag_abstain"
    assert result.text  # the localized stub, not silence
    assert "short refusal" not in result.text
    assert tell.reasons == ["rag_abstain"]


@pytest.mark.asyncio
async def test_codex_grounded_abstain_sends_the_answer_with_the_caution_note() -> None:
    tell = _Tell()
    result = await _run(_payload(_REAL_ANSWER, abstain=True), provider="codex", tell=tell)
    assert result.outcome is FinalizeOutcome.SEND
    assert result.text.startswith("To establish a PT PMA")
    assert len(result.text) > len(_REAL_ANSWER)  # caution note appended
    assert tell.reasons == []  # a real answer needs no human


@pytest.mark.asyncio
async def test_monologue_leak_inside_grounded_abstain_never_ships() -> None:
    # Review BLOCKER-1 reproduced: a grounded, >200-char abstain payload that
    # opens with the private marker used to be SENT by the early return.
    leaky = "Internal monologue instructions: reason step by step. " + _REAL_ANSWER
    gemini_tell, codex_tell = _Tell(), _Tell()
    gemini = await _run(
        _payload(leaky, abstain=True), provider="gemini", tell=gemini_tell
    )
    codex = await _run(_payload(leaky, abstain=True), provider="codex", tell=codex_tell)
    # Gemini: the payload is discarded, the stub ships, a human is told with
    # the MOST SPECIFIC cause (first cause wins).
    assert gemini.outcome is FinalizeOutcome.SEND
    assert "Internal monologue" not in gemini.text
    assert gemini.human_reason == "internal_monologue_leak"
    assert gemini_tell.reasons == ["internal_monologue_leak"]
    # Codex: a defective text fails off — a different generator can cure it.
    assert codex.outcome is FinalizeOutcome.DEFECT
    assert codex.defect_reason == "internal_monologue_leak"
    assert codex_tell.reasons == []


@pytest.mark.asyncio
async def test_escalate_marker_inside_grounded_abstain_is_stripped_and_told() -> None:
    marked = _REAL_ANSWER + " [ESCALATE]"
    tell = _Tell()
    result = await _run(_payload(marked, abstain=True), provider="gemini", tell=tell)
    assert result.outcome is FinalizeOutcome.SEND
    assert "[ESCALATE]" not in result.text
    assert result.human_reason == "persona_escalate_marker"
    assert tell.reasons == ["persona_escalate_marker"]


# ── Codex egress vetoes wired into the pipeline ──────────────────────────


@pytest.mark.asyncio
async def test_codex_price_outside_package_is_a_defect_but_gemini_sends_it() -> None:
    priced = _REAL_ANSWER + " The all-inclusive fee is Rp 9.999.000."
    codex_tell, gemini_tell = _Tell(), _Tell()
    codex = await _run(
        _payload(priced),
        provider="codex",
        tell=codex_tell,
        price_sources=["Company setup — Rp 3.500.000"],
    )
    gemini = await _run(_payload(priced), provider="gemini", tell=gemini_tell)
    assert codex.outcome is FinalizeOutcome.DEFECT
    assert codex.defect_reason == "pricing_outside_package"
    assert codex_tell.reasons == []
    # No price_sources on the Gemini leg — the veto is codex-only by construction.
    assert gemini.outcome is FinalizeOutcome.SEND


@pytest.mark.asyncio
async def test_codex_price_present_in_package_passes_the_veto() -> None:
    priced = _REAL_ANSWER + " The all-inclusive fee is Rp 3.500.000."
    result = await _run(
        _payload(priced),
        provider="codex",
        tell=_Tell(),
        price_sources=['{"company_setup": {"price": "Rp 3.500.000"}}'],
    )
    assert result.outcome is FinalizeOutcome.SEND


@pytest.mark.asyncio
async def test_codex_secret_egress_hit_is_a_defect_with_pattern_name_only() -> None:
    leaky = _REAL_ANSWER + " token sk-" + "a" * 24
    result = await _run(_payload(leaky), provider="codex", tell=_Tell())
    assert result.outcome is FinalizeOutcome.DEFECT
    assert result.defect_reason == "secret_egress:openai_style_key"
    # The defect record must never transcribe the secret it caught.
    assert "sk-" not in result.defect_message


@pytest.mark.asyncio
async def test_codex_veto_also_covers_the_grounded_abstain_early_return() -> None:
    # The early return is the one SEND that skips the main veto site — prove
    # the codex vetoes run there too.
    leaky = _REAL_ANSWER + " token sk-" + "b" * 24
    result = await _run(_payload(leaky, abstain=True), provider="codex", tell=_Tell())
    assert result.outcome is FinalizeOutcome.DEFECT
    assert result.defect_reason == "secret_egress:openai_style_key"


@pytest.mark.asyncio
async def test_codex_clean_answer_with_both_vetoes_armed_sends() -> None:
    result = await _run(
        _payload(_REAL_ANSWER),
        provider="codex",
        tell=_Tell(),
        price_sources=["no prices quoted"],
        canary_tokens=("CANARY-9f3a-token",),
    )
    assert result.outcome is FinalizeOutcome.SEND
    assert result.text.startswith("To establish a PT PMA")


# ── Gemini parity spot-check through the extracted pipeline ──────────────


@pytest.mark.asyncio
async def test_gemini_escalate_marker_is_stripped_and_a_human_is_told() -> None:
    tell = _Tell()
    result = await _run(
        _payload(_REAL_ANSWER + " [ESCALATE]"), provider="gemini", tell=tell
    )
    assert result.outcome is FinalizeOutcome.SEND
    assert "[ESCALATE]" not in result.text
    assert result.human_reason == "persona_escalate_marker"
    assert tell.reasons == ["persona_escalate_marker"]
