"""Tests for the local OpenClaw WhatsApp bridge runtime script."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def _load_bridge_module() -> ModuleType:
    repo_root = Path(__file__).resolve().parents[6]
    script_path = repo_root / "scripts" / "openclaw_whatsapp_bridge.py"
    spec = importlib.util.spec_from_file_location("openclaw_whatsapp_bridge_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


bridge = _load_bridge_module()


def test_build_prompt_includes_kb_tool_contract_and_autonomy() -> None:
    history = [{"role": "user", "text": f"message {idx}"} for idx in range(10)]
    body = bridge.BridgeRequest(
        agent="wa",
        model="openai/gpt-5.5",
        thinking="high",
        persona="zantara_whatsapp_v1",
        autonomy_mode="supervised_autonomous",
        phone="+62 812-345",
        sender_name="Client",
        message_id="wamid.test",
        text="I want to open a cafe in Canggu. Which KBLI?",
        context={
            "detected_language": "en",
            "is_first_message": False,
            "client_profile": {"segment": "founder"},
            "conversation_history": history,
        },
    )

    prompt = json.loads(bridge._build_prompt(body))

    assert prompt["persona"] == "zantara_whatsapp_v1"
    assert prompt["autonomy_mode"] == "supervised_autonomous"
    assert prompt["incoming_text"] == "I want to open a cafe in Canggu. Which KBLI?"
    assert prompt["client_profile"] == {"segment": "founder"}
    assert len(prompt["recent_history"]) == 8
    assert prompt["recent_history"][0]["text"] == "message 2"
    assert any("KBLI" in rule for rule in prompt["knowledge_tool_contract"])
    assert any("nuzantara-mcp.search_kbli" in rule for rule in prompt["knowledge_tool_contract"])
    assert any("Nuzantara MCP tools" in rule for rule in prompt["knowledge_tool_contract"])
    assert any("do not invent" in rule for rule in prompt["reply_rules"])
    assert any("self-triggered loop" in step for step in prompt["operating_loop"])
    assert any("Do not expose internal tools" in rule for rule in prompt["reply_rules"])


def test_build_prompt_marks_pricing_intent_as_mandatory_tool_call() -> None:
    body = bridge.BridgeRequest(
        phone="+62 812-345",
        sender_name="Client",
        message_id="wamid.price",
        text="Give me the exact total price for investor KITAS and guarantee the timeline.",
    )

    prompt = json.loads(bridge._build_prompt(body))

    assert any("Pricing/quote/timeline intent detected" in rule for rule in prompt["tool_mandates"])
    assert any("nuzantara-mcp.search_service_pricing" in rule for rule in prompt["tool_mandates"])
    assert any("mandatory" in rule for rule in prompt["knowledge_tool_contract"])


def test_build_prompt_marks_kbli_followup_from_recent_context() -> None:
    body = bridge.BridgeRequest(
        phone="+62 812-345",
        sender_name="Client",
        message_id="wamid.followup",
        text="And can that work with a PT PMA, or do I need a different setup?",
        context={
            "conversation_history": [
                {
                    "role": "user",
                    "text": "I want to open a small cafe in Canggu. Which KBLI?",
                }
            ]
        },
    )

    prompt = json.loads(bridge._build_prompt(body))

    assert any("KBLI/company-setup intent detected" in rule for rule in prompt["tool_mandates"])
    assert any("nuzantara-mcp.search_kbli" in rule for rule in prompt["tool_mandates"])


def test_build_prompt_includes_villa_55193_to_55203_mapping_rule() -> None:
    body = bridge.BridgeRequest(
        phone="+62 812-345",
        sender_name="Client",
        message_id="wamid.villa",
        text="ma per ville Airbnb e' 55193 o 55203?",
        context={"detected_language": "it"},
    )

    prompt = json.loads(bridge._build_prompt(body))
    contract = "\n".join(prompt["knowledge_tool_contract"])

    assert "55193" in contract
    assert "55203" in contract
    assert "KBLI 2020/PP28" in contract
    assert "KBLI 2025" in contract
    assert "55901" in contract
    assert "55400" in contract
    assert "AC/ventilation" in contract


def test_bridge_guard_corrects_bad_villa_55193_reply() -> None:
    guarded = bridge._guard_villa_kbli_reply(
        "ma per ville Airbnb e' 55193 o 55203?",
        "55193 - Aktivitas Vila: usa questo codice per Airbnb.",
        "it",
    )

    assert "55203" in guarded
    assert "55193" in guarded
    assert "KBLI 2020/PP28" in guarded
    assert "usa questo codice" not in guarded


def test_bridge_guard_keeps_grounded_villa_mapping_reply() -> None:
    reply = (
        "55193 era il codice KBLI 2020/PP28 sorgente; nel mapping KBLI 2025 "
        "mappa a 55203 - AKTIVITAS VILA."
    )

    assert bridge._guard_villa_kbli_reply("Differenza 55193 vs 55203", reply, "it") == reply


def test_property_zoning_guard_allows_villa_leasehold_duration() -> None:
    # Regression (villa-zoning-guard 2026-06-08): a lease-DURATION question
    # must NOT be clobbered by the Airbnb/zoning canned answer. The bare
    # "lease" trigger matches "leasehold"; the escape clause (oss+bkpm) is
    # unreachable for a correct duration reply, so pre-fix this returned the
    # canned zoning text instead of the real answer.
    correct = (
        "A typical villa leasehold in Bali is often around 25 to 30 years, "
        "sometimes with an option to extend."
    )
    assert (
        bridge._guard_property_zoning_reply(
            "How long is a typical villa leasehold in Bali?", correct, "en"
        )
        == correct
    )


def test_property_zoning_guard_allows_villa_lease_duration_reworded() -> None:
    correct = "A villa lease in Bali usually runs 25 years with renewal options."
    assert (
        bridge._guard_property_zoning_reply(
            "What is the usual duration of a villa lease in Bali?", correct, "en"
        )
        == correct
    )


def test_property_zoning_guard_still_fires_on_airbnb_operation() -> None:
    # The guard must STILL clobber a genuine Airbnb-in-residential-zone
    # operation question whose reply lacks the OSS/BKPM grounding.
    ungrounded = "Sure, just rent your villa on Airbnb, no special permits needed."
    guarded = bridge._guard_property_zoning_reply(
        "Can I run my villa as an Airbnb in a residential zone?", ungrounded, "en"
    )
    assert guarded != ungrounded  # was replaced by the canned zoning answer
def test_b211_guard_allows_correct_definitional_answer() -> None:
    reply = (
        "A B211/B211A is a short-stay visit/business visa: it gives no residency and "
        "no work rights. A KITAS is a limited-stay residency permit, and its work "
        "variant grants employment. B211 is old wording; the current short-stay "
        "business route is usually C2 Business, which the team confirms for your case."
    )

    assert (
        bridge._guard_legacy_b211_reply(
            "What's the difference between a B211A visa and a KITAS?", reply, "en"
        )
        == reply
    )


def test_b211_guard_still_clobbers_unsafe_current_claim() -> None:
    unsafe = (
        "Yes, the B211 is the right visa for you. Apply for it and you can run your "
        "business meetings in Bali with no problem."
    )

    guarded = bridge._guard_legacy_b211_reply(
        "Can I use a B211 to do business in Bali?", unsafe, "en"
    )

    assert guarded != unsafe
    assert "C2 Business" in guarded


def test_contains_any_word_respects_word_boundaries() -> None:
    # The bare-substring trap that produced W68/W72: short triggers must not
    # match inside longer words.
    assert bridge._contains_any_word("what is the tax rate", ("tax",)) is True
    assert bridge._contains_any_word("explain the syntax please", ("tax",)) is False
    assert bridge._contains_any_word("how do i file the spt", ("spt",)) is True
    assert bridge._contains_any_word("short stay accommodation", ("short stay",)) is True


def test_villa_terms_no_longer_carry_substring_traps() -> None:
    # "ota" matched "quota"/"biota"; "rent" matched "different"/"current".
    assert "ota" not in bridge._VILLA_TERMS
    assert "rent" not in bridge._VILLA_TERMS
    # A food-import KBLI question must NOT be treated as a villa query.
    assert (
        bridge._is_villa_kbli_query(
            "Which KBLI code covers the import quota for frozen food distribution?"
        )
        is False
    )


def test_lkpm_guard_allows_definitional_answer() -> None:
    # Pure definition, no deadline asserted → must pass (W: guard-family).
    correct = (
        "LKPM is the quarterly investment activity report that PT PMA and other "
        "investment companies must submit to BKPM through the OSS system."
    )
    assert bridge._guard_lkpm_reply("What is LKPM and who has to file it?", correct, "en") == correct


def test_lkpm_guard_still_clobbers_stale_deadline() -> None:
    stale = "You must file LKPM by 10 April every quarter, on the 7th day."
    guarded = bridge._guard_lkpm_reply("When is the LKPM deadline?", stale, "en")
    assert guarded != stale


# --- F11: LKPM dated-fact time-bomb ----------------------------------------
import datetime as _f11_dt


def test_lkpm_window_clause_states_april_while_valid() -> None:
    # On/before valid_until the published window is quoted as current.
    clause = bridge._lkpm_window_clause("en", today=_f11_dt.date(2026, 4, 15))
    assert "1 to 15 april" in clause.lower()
    assert bridge._lkpm_window_is_current(_f11_dt.date(2026, 4, 30)) is True


def test_lkpm_window_clause_degrades_after_expiry() -> None:
    # After valid_until the bridge must NOT assert the stale April window as
    # the current rule; it tells the user to verify live instead.
    clause = bridge._lkpm_window_clause("en", today=_f11_dt.date(2026, 7, 1))
    assert "april" not in clause.lower()
    assert "verif" in clause.lower()
    assert bridge._lkpm_window_is_current(_f11_dt.date(2026, 7, 1)) is False


def test_lkpm_guard_does_not_clobber_newer_window_after_expiry(monkeypatch) -> None:
    # The time-bomb: once the April fact is stale, a CORRECT reply citing the
    # NEW (e.g. Q2 July) window must NOT be clobbered for omitting "1-15 April".
    monkeypatch.setattr(bridge, "_lkpm_window_is_current", lambda today=None: False)
    new_window = (
        "For Q2 2026, BKPM opened the LKPM window 1-15 July 2026; the deadline "
        "is no later than 15 July. Verify live on OSS/BKPM."
    )
    out = bridge._guard_lkpm_reply("When is the LKPM deadline this quarter?", new_window, "en")
    assert out == new_window


def test_lkpm_guard_still_clobbers_stale_deadline_after_expiry(monkeypatch) -> None:
    # Degradation keeps the stale-marker safety net even after expiry.
    monkeypatch.setattr(bridge, "_lkpm_window_is_current", lambda today=None: False)
    stale = "File LKPM by 10 April, on the 7th of the month."
    out = bridge._guard_lkpm_reply("LKPM deadline?", stale, "en")
    assert out != stale


def test_lkpm_guard_clobbers_wrong_window_while_valid(monkeypatch) -> None:
    # While valid, a deadline-asserting reply that omits the correct window is
    # clobbered (unchanged behaviour, now keyed off the central fact).
    monkeypatch.setattr(bridge, "_lkpm_window_is_current", lambda today=None: True)
    wrong = "The LKPM deadline is no later than the 20th of March 2026."
    out = bridge._guard_lkpm_reply("LKPM deadline?", wrong, "en")
    assert out != wrong


# --- F12: hak_milik content-gating (not length-gating) ----------------------
def test_hak_milik_guard_clobbers_short_wrong_claim() -> None:
    # The dangerous case the old length-only guard let through: a SHORT reply
    # (<125 words) that wrongly says a foreigner can own Hak Milik.
    wrong = "Yes, as a foreigner you can own Hak Milik land directly through your PMA."
    out = bridge._guard_hak_milik_reply(
        "Can a foreigner buy Hak Milik land in Bali?", wrong, "en"
    )
    assert out != wrong
    assert "cannot hold hak milik" in bridge._normalize_text(out)


def test_hak_milik_guard_passes_correct_short_answer() -> None:
    # A correct, concise answer must NOT be clobbered.
    correct = (
        "No. A foreigner cannot hold Hak Milik directly. A PT PMA may look at HGB, "
        "and personal residential use may involve Hak Pakai. The team verifies the route."
    )
    assert (
        bridge._guard_hak_milik_reply(
            "Can a foreigner own Hak Milik?", correct, "en"
        )
        == correct
    )


def test_hak_milik_guard_passes_correct_indonesian_answer() -> None:
    correct = (
        "Tidak. Orang asing tidak bisa memegang Hak Milik langsung. PT PMA biasanya "
        "melihat HGB; tim legal Bali Zero verify rutenya."
    )
    assert (
        bridge._guard_hak_milik_reply(
            "Orang asing bisa punya Hak Milik?", correct, "id"
        )
        == correct
    )


def test_hak_milik_affirmation_detector_polarity() -> None:
    norm = bridge._normalize_text
    assert bridge._hak_milik_asserts_foreigner_can_own(
        norm("a foreigner can own hak milik directly")
    )
    assert not bridge._hak_milik_asserts_foreigner_can_own(
        norm("a foreigner cannot hold hak milik directly")
    )


def test_tax_guard_does_not_append_on_stable_rate_fact() -> None:
    # "What is Coretax" is a definition; no OSS/BKPM verify tail should be added.
    answer = "Coretax is Indonesia's new tax administration system run by the DJP."
    assert bridge._guard_tax_compliance_reply("What is Coretax?", answer, "en") == answer
    rate = "The standard VAT rate is 11% effective, 12% headline."
    assert bridge._guard_tax_compliance_reply("What is the VAT rate?", rate, "en") == rate


def test_tax_guard_still_appends_on_penalty_intent() -> None:
    answer = "Late SPT filing carries an administrative fine."
    guarded = bridge._guard_tax_compliance_reply(
        "What is the penalty for late SPT filing and my risk?", answer, "en"
    )
    assert guarded != answer
    assert "verify" in guarded.lower()


def test_cafe_guard_does_not_clobber_definitional_pt_pma_answer() -> None:
    # Message asks PT PMA vs PT lokal; reply happens to mention a cafe as an
    # example. The guard must NOT substitute the cafe canonical.
    reply = (
        "A PT PMA is a foreign-owned company; a PT lokal is fully Indonesian-owned. "
        "The differences are ownership, minimum capital, eligible business fields, "
        "and control. For example, a small local cafe is usually a PT lokal, while a "
        "foreign-funded venture uses a PT PMA with the right KBLI and licensing."
    )
    assert (
        bridge._guard_cafe_pma_reply(
            "What's the difference between a PT PMA and a PT lokal?", reply, "en"
        )
        == reply
    )


def test_cafe_guard_still_fires_on_real_cafe_question() -> None:
    long_reply = (
        "Opening a cafe is possible. " + "You will need to think about the concept. " * 20
    )
    guarded = bridge._guard_cafe_pma_reply(
        "Can I open a cafe with a PT PMA in Canggu?", long_reply, "en"
    )
    assert guarded != long_reply
    assert "56303" in guarded


def test_nominee_guard_fires_on_natural_phrasing() -> None:
    # The dangerous question rarely contains the literal word "nominee".
    # Reply must exceed the 115-word substitution threshold to be clobbered.
    long_reply = (
        "Sure, that can work in practice and many people do it this way. " * 15
    )
    assert bridge._reply_word_count(long_reply) > 115
    guarded = bridge._guard_nominee_reply(
        "My Indonesian friend can hold the title for me, right?", long_reply, "en"
    )
    assert guarded != long_reply
    assert "illegal" in guarded.lower()


def test_nominee_intent_detects_lexical_variants() -> None:
    # The compositional detector must catch phrasings a fixed list misses.
    assert bridge._is_nominee_intent("my indonesian friend can hold the land title for me")
    assert bridge._is_nominee_intent("can my wife hold the property for us")
    assert bridge._is_nominee_intent("just put it in my friend's name")
    # And NOT fire on an unrelated "hold" sentence with no proxy/asset nominee intent.
    assert not bridge._is_nominee_intent("how long do i hold a tourist visa")


def test_nominee_guard_clobbers_short_risky_only_answer() -> None:
    # A nominee REQUEST answered with a short "it's risky" (no illegality) must
    # be substituted regardless of length — the exact live failure mode.
    short_risky = (
        "I wouldn't treat that as fully safe. Having your Indonesian friend hold "
        "the title can create serious legal and practical risk."
    )
    assert bridge._reply_word_count(short_risky) <= 115
    guarded = bridge._guard_nominee_reply(
        "My Indonesian friend can hold the title for me, right?", short_risky, "en"
    )
    assert guarded != short_risky
    assert "illegal" in guarded.lower()


def test_nominee_guard_keeps_short_answer_that_states_illegality() -> None:
    good_short = (
        "No — that is illegal. A nominee holding land for a foreigner is void under "
        "Indonesian law; use a PT PMA or a proper leasehold instead."
    )
    assert (
        bridge._guard_nominee_reply(
            "My Indonesian friend can hold the title for me, right?", good_short, "en"
        )
        == good_short
    )


def test_nominee_canonical_states_illegality() -> None:
    answer = bridge._canonical_nominee_answer("en")
    assert "illegal" in answer.lower()
    assert "void" in answer.lower()


def test_nominee_guard_allows_correct_definitional_answer() -> None:
    # A neutral "what is a nominee" question with a correct, risk-framed long
    # answer must not be clobbered purely for length.
    correct = (
        "A nominee arrangement is when an Indonesian holds an asset in their name "
        "for a foreigner. It is illegal and void under Indonesian agrarian law, so "
        "it carries serious legal risk and the proper route is a transparent PT PMA "
        "or leasehold structure instead. " * 2
    )
    assert (
        bridge._guard_nominee_reply("What is a nominee arrangement?", correct, "en")
        == correct
    )


# ---------------------------------------------------------------------------
# F05: property_zoning guard — word-boundary "please"→"lease", "village"→"villa"
# ---------------------------------------------------------------------------

def test_property_zoning_guard_please_does_not_match_lease() -> None:
    """F05 regression: 'please' contains 'lease' as a substring.

    'I'm buying a villa, can you please explain the purchase process?' used to
    trigger the zoning guard (villa + please→lease) and return the canned
    Airbnb/zoning answer instead of the correct purchase-process reply.
    """
    correct = (
        "Foreigners can buy a villa leasehold or use HGB via PT PMA. "
        "The purchase process involves due diligence, notary, and AJB signing."
    )
    assert (
        bridge._guard_property_zoning_reply(
            "I'm buying a villa, can you please explain the purchase process?",
            correct,
            "en",
        )
        == correct
    )


def test_property_zoning_guard_village_does_not_match_villa() -> None:
    """F05 regression: 'village' contains 'villa' as a substring.

    A question about a 'traditional village' must not trigger the zoning guard.
    """
    correct = (
        "Traditional Balinese village compounds (desa adat) follow customary "
        "land rules; they are not subject to the same zoning as tourist villas."
    )
    assert (
        bridge._guard_property_zoning_reply(
            "What are the zoning rules for a traditional village in Bali?",
            correct,
            "en",
        )
        == correct
    )


# ---------------------------------------------------------------------------
# F06: nominee guard — "'s name" / "atas nama" over-match company/invoice context
# ---------------------------------------------------------------------------

def test_nominee_guard_does_not_fire_on_company_name_change() -> None:
    """F06 regression: "Can I change my company's name?" hit "'s name" in
    _NOMINEE_DIRECT_TERMS and was replaced with the illegal-nominee canonical.
    """
    correct = (
        "Yes, you can change your PT PMA's name through a notary deed amendment "
        "and updated NIB registration. The process takes about 2-4 weeks."
    )
    assert bridge._is_nominee_intent("can i change my company's name in indonesia") is False
    assert (
        bridge._guard_nominee_reply(
            "Can I change my company's name in Indonesia?", correct, "en"
        )
        == correct
    )


def test_nominee_guard_does_not_fire_on_invoice_atas_nama() -> None:
    """F06 regression: "bisa buat faktur atas nama PT saya?" hit "atas nama"
    and returned the illegal-nominee canonical instead of an invoice answer.
    """
    correct = (
        "Ya, faktur pajak bisa diterbitkan atas nama PT Anda selama NPWP PT "
        "sudah aktif dan terdaftar di Coretax."
    )
    assert bridge._is_nominee_intent("bisa buat faktur atas nama pt saya?") is False
    assert (
        bridge._guard_nominee_reply("bisa buat faktur atas nama PT saya?", correct, "id")
        == correct
    )


def test_nominee_guard_still_fires_on_real_nominee_with_atas_nama() -> None:
    """F06: a REAL nominee request using 'atas nama' (person, not company/invoice)
    must still be clobbered.
    """
    unsafe = (
        "Kalau atas nama teman Indonesia saya bisa, banyak orang melakukannya "
        "dan tidak ada masalah biasanya."
    )
    guarded = bridge._guard_nominee_reply(
        "Bisa beli tanah atas nama teman Indonesia saya?", unsafe, "id"
    )
    assert guarded != unsafe
    assert "ilegal" in guarded.lower() or "illegal" in guarded.lower()


# ---------------------------------------------------------------------------
# F06 hardening (2026-06-13): "'s name" / "atas nama" are WEAK tokens — they
# need an asset/proxy co-occurrence and never fire in booking/tiket/rekening
# naming contexts. Both polarities per the W73 matrix convention.
# ---------------------------------------------------------------------------

def test_nominee_guard_does_not_fire_on_booking_atas_nama() -> None:
    """A hotel-booking request 'atas nama saya' is reservation NAMING, not a
    nominee asset-holding request — it was clobbered with the illegal-nominee
    canonical before the hardening."""
    correct = (
        "Ya, kami bisa bantu booking hotel atas nama Anda. Kirim tanggal "
        "check-in dan nama lengkap sesuai paspor."
    )
    assert bridge._is_nominee_intent("bisa booking hotel atas nama saya?") is False
    assert (
        bridge._guard_nominee_reply("Bisa booking hotel atas nama saya?", correct, "id")
        == correct
    )


def test_nominee_guard_does_not_fire_on_rekening_atas_nama() -> None:
    """A bank-transfer question about a 'rekening atas nama istri' is account
    NAMING — the proxy word ('istri') alone must not turn it into nominee
    intent."""
    correct = (
        "Bisa, transfer ke rekening atas nama istri Anda diterima selama "
        "datanya cocok dengan data pembayaran."
    )
    assert (
        bridge._is_nominee_intent("bisa transfer ke rekening atas nama istri saya?")
        is False
    )
    assert (
        bridge._guard_nominee_reply(
            "Bisa transfer ke rekening atas nama istri saya?", correct, "id"
        )
        == correct
    )


def test_nominee_guard_does_not_fire_on_plain_possessive_name() -> None:
    """"'s name" with NO asset/proxy co-occurrence (e.g. asking for the
    notary's name) is everyday possessive English, not nominee intent."""
    message = "Can you confirm the notary's name for tomorrow's appointment?"
    correct = (
        "The notary for your appointment is confirmed for 10am; the team will "
        "send the full name and office address shortly."
    )
    assert bridge._is_nominee_intent(bridge._normalize_text(message)) is False
    assert bridge._guard_nominee_reply(message, correct, "en") == correct


def test_nominee_guard_still_fires_on_weak_name_with_asset() -> None:
    """Clobber polarity: "'s name" WITH an asset + proxy co-occurrence is a
    genuine nominee request — a soft 'usually fine' answer must be replaced
    with the illegality canonical."""
    unsafe = "Yes, that is a common approach and usually fine in practice."
    guarded = bridge._guard_nominee_reply(
        "Can we put the villa certificate in my wife's name?", unsafe, "en"
    )
    assert guarded != unsafe
    assert "illegal" in guarded.lower()


def test_nominee_intent_compositional_beats_admin_token() -> None:
    """A genuine compositional nominee request must fire even when the message
    incidentally contains an administrative token (the old exclusion-first
    ordering returned False here)."""
    assert bridge._is_nominee_intent(
        "my indonesian friend will hold the land title for me, then send me the invoice"
    )


# ---------------------------------------------------------------------------
# F13: villa⊂village in _is_villa_kbli_query and _guard_villa_kbli_reply
# ---------------------------------------------------------------------------

def test_villa_kbli_query_village_is_not_villa() -> None:
    """F13 regression: 'village' contains 'villa', so a handicraft question
    mentioning 'in an Ubud village' was classified as a villa KBLI query and
    the reply was replaced with the 55203 villa canonical.
    """
    assert bridge._is_villa_kbli_query(
        "What KBLI code covers traditional handicraft workshops in an Ubud village?"
    ) is False


def test_villa_kbli_guard_village_not_clobbered() -> None:
    """F13 regression: guard must not clobber a correct handicraft/KBLI answer
    just because the word 'village' appears in the question.
    """
    correct = (
        "Traditional handicraft production in Bali typically uses KBLI 32904 "
        "(other personal goods manufacturing). The team verifies the exact code "
        "based on the specific product type."
    )
    assert (
        bridge._guard_villa_kbli_reply(
            "What KBLI code covers traditional handicraft workshops in an Ubud village?",
            correct,
            "en",
        )
        == correct
    )


# ---------------------------------------------------------------------------
# F39: incidental villa mention (probe T5 2026-06-11) — "kbli"+"villa" keyword
# conjunction is not villa-business intent (root class W73)
# ---------------------------------------------------------------------------

def test_villa_kbli_query_incidental_villa_beach_club_passes() -> None:
    """F39 regression (probe T5): a beach-club KBLI question mentioning a villa
    bought TO LIVE IN was classified as a villa KBLI query and the multi-part
    answer (KBLI 56301, foreign ownership, visas) was replaced with the 55203
    villa canonical.
    """
    assert bridge._is_villa_kbli_query(
        "I want to open a beach club in Canggu with my Australian partner: "
        "which KBLI codes apply, can it be 100% foreign owned, and what visas "
        "do we need? We are also thinking of buying a villa to live in."
    ) is False


def test_villa_kbli_query_residential_purchase_passes() -> None:
    """F39: a residential villa purchase with no rental signal is not a
    villa-business KBLI query — the right answer is 'no KBLI needed', not
    the 55203 canonical."""
    assert bridge._is_villa_kbli_query(
        "I'm buying a villa in Ubud to live in — do I need a KBLI code for that?"
    ) is False


def test_villa_kbli_guard_beach_club_not_clobbered() -> None:
    """F39 regression: guard must not clobber a correct beach-club answer."""
    correct = (
        "A beach club typically combines KBLI 56301 (bars) and 56101 "
        "(restaurants); both are open to 100% foreign ownership via PT PMA. "
        "You and your partner would need investor KITAS. The team verifies "
        "the exact code mix for your concept."
    )
    assert (
        bridge._guard_villa_kbli_reply(
            "I want to open a beach club in Canggu with my Australian partner: "
            "which KBLI codes apply, can it be 100% foreign owned, and what "
            "visas do we need? We are also thinking of buying a villa to live in.",
            correct,
            "en",
        )
        == correct
    )


def test_villa_kbli_query_still_fires_on_genuine_rental_intent() -> None:
    """F39 other polarity: a genuine villa-rental KBLI question still guards,
    even when another business is mentioned alongside."""
    assert bridge._is_villa_kbli_query(
        "Which KBLI code do I need to rent out my villa on Airbnb?"
    ) is True
    assert bridge._is_villa_kbli_query(
        "We run a restaurant and also rent out a villa to guests — "
        "which KBLI codes apply?"
    ) is True


def test_villa_kbli_query_explicit_codes_not_gated_by_incidental_bailout() -> None:
    """F39: explicit 55193/55203 codes in the message keep firing the guard
    regardless of residential/other-business wording."""
    assert bridge._is_villa_kbli_query(
        "For my restaurant company, is 55193 or 55203 the right code? "
        "The villa is just to live in."
    ) is True


# ---------------------------------------------------------------------------
# F40: WhatsApp formatting calibration (probe round 2026-06-11) — prompt rules
# + deterministic markdown→WhatsApp normalization net
# ---------------------------------------------------------------------------

def test_build_prompt_includes_whatsapp_format_rules() -> None:
    body = bridge.BridgeRequest(
        phone="+62 812-345",
        sender_name="Client",
        message_id="wamid.format",
        text="How much does the investor KITAS cost?",
        context={"detected_language": "en"},
    )
    rules = "\n".join(json.loads(bridge._build_prompt(body))["reply_rules"])

    assert "direct answer in the first line" in rules
    assert "900 characters" in rules
    assert "1500 characters" in rules
    assert "*single asterisks*" in rules
    assert "never ** double asterisks" in rules
    assert "• bullet character" in rules


def test_normalize_whatsapp_format_rewrites_markdown() -> None:
    raw = (
        "## Investor KITAS\n"
        "The **2-year investor KITAS** costs:\n"
        "- Offshore: 17M IDR\n"
        "* Onshore: 19M IDR\n"
    )
    assert bridge._normalize_whatsapp_format(raw) == (
        "Investor KITAS\n"
        "The *2-year investor KITAS* costs:\n"
        "• Offshore: 17M IDR\n"
        "• Onshore: 19M IDR\n"
    )


def test_normalize_whatsapp_format_keeps_clean_reply_unchanged() -> None:
    clean = (
        "The 2-year investor KITAS is 17M IDR offshore.\n\n"
        "• Documents: passport, company deed\n"
        "• Timeline: the team confirms\n\n"
        "Want me to start the checklist?"
    )
    assert bridge._normalize_whatsapp_format(clean) == clean


def test_normalize_whatsapp_format_bold_line_start_is_not_bullet() -> None:
    # "*Important:* ..." at line start is WhatsApp bold, not a "* " list marker.
    text = "*Important:* bring the original passport."
    assert bridge._normalize_whatsapp_format(text) == text


def test_normalize_whatsapp_format_preserves_bullet_indent() -> None:
    assert bridge._normalize_whatsapp_format("  - nested item") == "  • nested item"


# ---------------------------------------------------------------------------
# Sender identity rules (2026-06-11): backend resolves phone → owner/team/
# client/unknown; the bridge injects per-role persona rules into the prompt.
# ---------------------------------------------------------------------------

def test_identity_rules_owner() -> None:
    rules = "\n".join(bridge._identity_rules({"sender_identity": {"role": "owner"}}))
    assert "Zero (Antonello)" in rules
    assert "internal conversation" in rules
    assert "never say 'the team will contact" in rules


def test_identity_rules_team_uses_member_name() -> None:
    rules = "\n".join(
        bridge._identity_rules(
            {"sender_identity": {"role": "team", "team_member": "Sahira"}}
        )
    )
    assert "Sahira" in rules
    assert "internal colleague" in rules


def test_identity_rules_client_known_but_privacy_capped() -> None:
    rules = "\n".join(
        bridge._identity_rules(
            {
                "sender_identity": {
                    "role": "client",
                    "client_id": 42,
                    "client_name": "Marta Reyes",
                    "client_status": "active",
                }
            }
        )
    )
    assert "Marta Reyes" in rules
    assert "known client" in rules
    assert "never reveal information about any other client" in rules


def test_identity_rules_unknown_or_missing_is_empty() -> None:
    assert bridge._identity_rules({"sender_identity": {"role": "unknown"}}) == []
    assert bridge._identity_rules({}) == []
    assert bridge._identity_rules(None) == []


def test_build_prompt_injects_identity_rules_for_owner_only() -> None:
    owner_body = bridge.BridgeRequest(
        phone="+62 822-3010-2328",
        sender_name="Zero",
        message_id="wamid.owner",
        text="Quante pratiche KITAS abbiamo in pipeline questo mese?",
        context={"detected_language": "it", "sender_identity": {"role": "owner"}},
    )
    prompt = json.loads(bridge._build_prompt(owner_body))
    assert any("Zero (Antonello)" in rule for rule in prompt["sender_identity_rules"])

    anon_body = bridge.BridgeRequest(
        phone="+62 813-555-0009",
        sender_name="Client",
        message_id="wamid.anon",
        text="How much is a KITAS?",
        context={"detected_language": "en"},
    )
    assert "sender_identity_rules" not in json.loads(bridge._build_prompt(anon_body))


def test_run_script_uses_installed_bridge_app_dir() -> None:
    repo_root = Path(__file__).resolve().parents[6]
    script = (repo_root / "scripts" / "run_openclaw_whatsapp_bridge.sh").read_text(
        encoding="utf-8"
    )

    assert '--app-dir "$HOME/.openclaw/bin"' in script
    assert ".worktrees/backend-rag-openclaw-whatsapp-meta" not in script


def test_session_key_strips_phone_punctuation_and_scopes_message() -> None:
    assert bridge._session_key("wa", "+62 812-345") == "agent:wa:whatsapp-meta-62812345"
    assert (
        bridge._session_key("wa", "+62 812-345", "wamid.test:123")
        == "agent:wa:whatsapp-meta-62812345-wamid-test-123"
    )
    assert bridge._session_key("wa", "no digits") == "agent:wa:whatsapp-meta-unknown"


@pytest.mark.asyncio
async def test_run_openclaw_passes_runtime_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class FakeProcess:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            payload = {"result": {"finalAssistantVisibleText": "Ready from Zantara."}}
            return json.dumps(payload).encode(), b""

    async def fake_create_subprocess_exec(*args: str, **kwargs: Any) -> FakeProcess:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr(bridge.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setenv("OPENCLAW_WHATSAPP_TIMEOUT_SECONDS", "30")

    reply = await bridge._run_openclaw(
        "wa",
        '{"incoming_text":"hi"}',
        "628123",
        "wamid.test",
        "openai/gpt-5.5",
        "high",
    )

    args = captured["args"]
    assert reply == "Ready from Zantara."
    assert args[:4] == ("openclaw", "agent", "--agent", "wa")
    assert "--channel" in args
    assert args[args.index("--channel") + 1] == "whatsapp"
    assert "--to" in args
    assert args[args.index("--to") + 1] == "+628123"
    assert "--session-key" in args
    assert args[args.index("--session-key") + 1] == "agent:wa:whatsapp-meta-628123-wamid-test"
    assert "--model" in args
    assert args[args.index("--model") + 1] == "openai/gpt-5.5"
    assert "--thinking" in args
    assert args[args.index("--thinking") + 1] == "high"
    assert "--deliver" not in args


def test_army_owner_allowlist_deny_all_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    # Panel fix (Gemini): unset env = true closed-by-default = deny-all,
    # NOT hardcoded-open-to-one. The army feature is disabled until opt-in.
    monkeypatch.delenv("WA_ARMY_OWNERS", raising=False)
    assert bridge._army_owner_allowlist() == frozenset()
    monkeypatch.setenv("WA_ARMY_OWNERS", "   ")
    assert bridge._army_owner_allowlist() == frozenset()


def test_army_owner_allowlist_parses_and_normalizes_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WA_ARMY_OWNERS", " +62 822-3010-2328 , 6281234567890 , ")
    allow = bridge._army_owner_allowlist()
    assert allow == frozenset({"6282230102328", "6281234567890"})


def test_army_owner_allowlist_drops_non_digit_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    # Panel fix (Codex): an env value that normalizes to "" must NOT become a
    # member, or a malformed sender phone normalizing to "" would match it.
    monkeypatch.setenv("WA_ARMY_OWNERS", "abc, 6282230102328, ---")
    allow = bridge._army_owner_allowlist()
    assert allow == frozenset({"6282230102328"})
    assert "" not in allow


def test_is_army_owner_normalizes_punctuation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WA_ARMY_OWNERS", "6282230102328")
    assert bridge._is_army_owner("+62 822-3010-2328") is True
    assert bridge._is_army_owner("6282230102328") is True
    assert bridge._is_army_owner("+62 812-000-0000") is False
    assert bridge._is_army_owner(None) is False
    assert bridge._is_army_owner("") is False


def test_is_army_owner_rejects_malformed_phone_against_empty_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Panel fix (Codex): even if the allowlist were somehow empty, a phone
    # that normalizes to "" must never match. Belt-and-suspenders on both sides.
    monkeypatch.delenv("WA_ARMY_OWNERS", raising=False)
    assert bridge._is_army_owner("no-digits-here") is False
    assert bridge._is_army_owner("---") is False


@pytest.mark.asyncio
async def test_army_command_owner_can_launch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WA_ARMY_OWNERS", "6282230102328")
    captured: dict[str, Any] = {}

    async def fake_runner(*args: str) -> tuple[int, str, str]:
        captured["args"] = args
        return (0, "LAUNCHED sess-1 /tmp/log", "")

    monkeypatch.setattr(bridge, "_run_army_launcher", fake_runner)

    reply = await bridge._handle_army_command("/lancia S1", "+62 822-3010-2328")

    assert captured["args"] == ("launch", "S1")
    assert reply is not None
    assert "LANCIATA" in reply


@pytest.mark.asyncio
async def test_army_command_non_owner_falls_through_silently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WA_ARMY_OWNERS", "6282230102328")
    called = False

    async def fake_runner(*args: str) -> tuple[int, str, str]:
        nonlocal called
        called = True
        return (0, "should-not-run", "")

    monkeypatch.setattr(bridge, "_run_army_launcher", fake_runner)

    # Non-owner sends every army command shape — all must return None and
    # NEVER touch the launcher (no claude --dangerously-skip-permissions).
    for text in ("/lancia S1", "/armate", "armate-status", "/ferma S1"):
        assert await bridge._handle_army_command(text, "+62 812-000-0000") is None
    assert called is False


@pytest.mark.asyncio
async def test_army_command_deny_all_blocks_even_owner_number_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # With WA_ARMY_OWNERS unset, the allowlist is empty → NOBODY can launch,
    # not even the default owner number. Deny-all is the safe failure mode.
    monkeypatch.delenv("WA_ARMY_OWNERS", raising=False)
    called = False

    async def fake_runner(*args: str) -> tuple[int, str, str]:
        nonlocal called
        called = True
        return (0, "should-not-run", "")

    monkeypatch.setattr(bridge, "_run_army_launcher", fake_runner)

    assert await bridge._handle_army_command("/lancia S1", "+62 822-3010-2328") is None
    assert called is False


@pytest.mark.asyncio
async def test_army_command_non_command_returns_none_for_everyone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WA_ARMY_OWNERS", "6282230102328")
    # Even the owner: a normal message is not a command → None (LLM handles it).
    assert await bridge._handle_army_command("ciao come stai?", "+62 822-3010-2328") is None
    assert await bridge._handle_army_command("", "+62 822-3010-2328") is None


@pytest.mark.asyncio
async def test_run_openclaw_uses_env_model_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class FakeProcess:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            payload = {"result": {"payloads": [{"text": "Env defaults ok."}]}}
            return json.dumps(payload).encode(), b""

    async def fake_create_subprocess_exec(*args: str, **kwargs: Any) -> FakeProcess:
        captured["args"] = args
        return FakeProcess()

    monkeypatch.setattr(bridge.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setenv("OPENCLAW_WHATSAPP_MODEL", "openai/gpt-5.5")
    monkeypatch.setenv("OPENCLAW_WHATSAPP_THINKING", "high")

    reply = await bridge._run_openclaw("wa", "{}", "+628123", "wamid.env", None, None)

    args = captured["args"]
    assert reply == "Env defaults ok."
    assert args[args.index("--model") + 1] == "openai/gpt-5.5"
    assert args[args.index("--thinking") + 1] == "high"


# ---------------------------------------------------------------------------
# F14 — b211 escape word-boundary (2026-06-11)
# "holders" ⊃ "old", "selama" ⊃ "lama": must NOT escape as legacy framing.
# ---------------------------------------------------------------------------


def test_b211_guard_f14_holders_does_not_escape() -> None:
    """'B211A holders can work in Indonesia' must be CLOBBERED (not pass-through).

    Before F14 the escape clause matched 'old' inside 'holders', so the unsafe
    reply slipped through without being replaced.
    """
    unsafe = (
        "B211A holders can work in Indonesia as long as they have their documents."
    )
    guarded = bridge._guard_legacy_b211_reply(
        "Can I use a B211A to work in Indonesia?", unsafe, "en"
    )
    assert guarded != unsafe, (
        "F14 regression: 'holders' ⊃ 'old' escaped the b211 guard — must clobber"
    )


def test_b211_guard_f14_selama_does_not_escape() -> None:
    """Indonesian 'selama' ⊃ 'lama': must NOT escape as legacy framing."""
    unsafe = (
        "B211A adalah visa yang tepat untuk bisnis di Bali, berlaku selama Anda "
        "punya dokumen yang benar."
    )
    guarded = bridge._guard_legacy_b211_reply(
        "Apakah B211A masih visa yang tepat?", unsafe, "id"
    )
    assert guarded != unsafe, (
        "F14 regression: 'selama' ⊃ 'lama' escaped the b211 guard — must clobber"
    )


# ---------------------------------------------------------------------------
# F36 — risk-intent word-boundary (2026-06-11)
# "late" ⊂ "translate", "fine" ⊂ "define", "owe" ⊂ "lower" must NOT fire.
# ---------------------------------------------------------------------------


def test_tax_guard_f36_translate_does_not_fire() -> None:
    """A message asking to 'translate' a tax form has no risk intent."""
    reply = "LKPM is the investment realization report companies file with BKPM."
    original = reply
    guarded = bridge._guard_tax_compliance_reply(
        "Can you translate the LKPM form for me?", reply, "en"
    )
    assert guarded == original, (
        "F36 regression: 'late' inside 'translate' incorrectly appended verify-suffix"
    )


# ---------------------------------------------------------------------------
# F37 — document_status conditional "is approved" (2026-06-11)
# "once the application is approved" is safe explanatory text; must pass.
# A bare "is approved" still clobbers.
# ---------------------------------------------------------------------------


def test_document_status_guard_f37_conditional_approved_passes() -> None:
    """A reply explaining what happens 'once ... is approved' must survive."""
    reply = (
        "Once the application is approved by the immigration office, you will "
        "receive an email notification and can collect the KITAS within three "
        "working days."
    )
    guarded = bridge._guard_document_status_reply(
        "What happens after my KITAS application is approved?", reply, "en"
    )
    assert guarded == reply, (
        "F37 regression: conditional 'once ... is approved' incorrectly clobbered"
    )


def test_document_status_guard_f37_affirmative_approved_clobbers() -> None:
    """A bare affirmative 'is approved' claim must still be clobbered."""
    unsafe = "Your KITAS application is approved and has been processed."
    guarded = bridge._guard_document_status_reply(
        "What is the status of my KITAS application?", unsafe, "en"
    )
    assert guarded != unsafe, (
        "F37 regression: bare 'is approved' claim slipped through guard"
    )


# ---------------------------------------------------------------------------
# F38 — kbli_label postcode / amount false-positive (2026-06-11)
# A 5-digit postcode or amount in a message without KBLI context must NOT
# trigger the "KBLI direction to check:" prefix.
# ---------------------------------------------------------------------------


def test_kbli_label_guard_f38_postcode_does_not_fire() -> None:
    """A reply mentioning a postcode (80361 = Kuta) must NOT get KBLI prefix."""
    reply = "The Bali Zero office is in the Kerobokan area, postcode 80361, by appointment."
    guarded = bridge._guard_kbli_label_reply(
        "What is the Bali Zero office address?", reply, "en"
    )
    assert guarded == reply, (
        "F38 regression: postcode 80361 triggered KBLI prefix on a non-KBLI query"
    )


def test_kbli_label_guard_f38_kbli_context_still_fires() -> None:
    """A reply with a 5-digit code AND KBLI context in the message must still fire."""
    reply = "For that activity you'd look at code 56303."
    guarded = bridge._guard_kbli_label_reply(
        "What KBLI applies to a coffee shop PT PMA?", reply, "en"
    )
    assert guarded != reply, "F38: KBLI-context message should still trigger prefix"
    assert guarded.startswith("KBLI direction to check")


# ---------------------------------------------------------------------------
# Guard test-matrix harness (anti-over-match gate — W68/W72/W73 class).
# For EVERY _guard_* function: one "pass" case (a CORRECT on-topic answer that
# must survive unchanged) and one "clobber" case (a WRONG answer that must be
# changed). The META completeness test below makes a newly-added guard with no
# matrix entry FAIL the suite — that is the gate.
# ---------------------------------------------------------------------------

# A long, WRONG hak-milik answer (>125 words) so the word-count clobber fires.
_HAK_MILIK_WRONG_LONG = (
    "Yes, as a foreigner you can absolutely own Hak Milik land in Bali through "
    "several creative structures that many expats use successfully every day. "
) * 6  # 144 words

# A long cafe answer (>115 words) that is cafe-ish so the cafe clobber fires.
_CAFE_WRONG_LONG = (
    "Yes a cafe can work under a PT PMA if KBLI, ownership and location are right "
    "and you check 56303 first for cafe drink house activity and also consider a "
    "restaurant direction if you serve full meals and the final fit depends on menu "
    "alcohol takeaway delivery and exact Canggu zoning so send the concept menu and "
    "pin location to verify everything before you sign or invest in the project "
    "today right now please. "
) * 2  # 148 words

GUARD_MATRIX: list[dict[str, Any]] = [
    # 1. document_status -------------------------------------------------------
    {
        "guard": "_guard_document_status_reply",
        "message": "What is the status of my KITAS application number 12345?",
        "reply": (
            "I can't verify or confirm the application status from WhatsApp or the "
            "reference number alone. I'll pass the reference to the Bali Zero team so "
            "they can check the real status in the correct system."
        ),
        "lang": "en",
        "expect": "pass",
    },
    {
        "guard": "_guard_document_status_reply",
        "message": "What is the status of my KITAS application number 12345?",
        "reply": "Your KITAS is already approved and ready for collection.",
        "lang": "en",
        "expect": "clobber",
    },
    # 2. legacy_b211 -----------------------------------------------------------
    {
        "guard": "_guard_legacy_b211_reply",
        "message": "Is the B211A still the visa I need for a business meeting in Bali?",
        "reply": (
            "Treat B211/B211A as an old/legacy label, not the current code. For business "
            "meetings the current route is usually C2 Business or C12 Pre-Investment "
            "depending on activity; the team will verify."
        ),
        "lang": "en",
        "expect": "pass",
    },
    {
        "guard": "_guard_legacy_b211_reply",
        "message": "Is the B211A still the visa I need for a business meeting in Bali?",
        "reply": (
            "Yes, the B211A is exactly the visa you should apply for to do business in "
            "Indonesia."
        ),
        "lang": "en",
        "expect": "clobber",
    },
    # 3. hak_milik (word-count > 125) -----------------------------------------
    {
        "guard": "_guard_hak_milik_reply",
        "message": "Can a foreigner own Hak Milik land in Bali?",
        "reply": (
            "No. A foreigner cannot hold Hak Milik directly. Use HGB/Hak Pakai via a PT "
            "PMA, or a leasehold; the team verifies the route."
        ),
        "lang": "en",
        "expect": "pass",
    },
    {
        "guard": "_guard_hak_milik_reply",
        "message": "Can a foreigner own Hak Milik land in Bali?",
        "reply": _HAK_MILIK_WRONG_LONG,
        "lang": "en",
        "expect": "clobber",
    },
    # 4. lkpm (negative-gating) -----------------------------------------------
    {
        "guard": "_guard_lkpm_reply",
        "message": "What is LKPM and who has to file it?",
        "reply": (
            "LKPM is the investment realization report a PT PMA submits to BKPM through "
            "OSS, usually quarterly for medium and large companies. It reports how much "
            "of the planned investment has been realized."
        ),
        "lang": "en",
        "expect": "pass",
    },
    {
        "guard": "_guard_lkpm_reply",
        "message": "When is the LKPM deadline?",
        "reply": (
            "The LKPM deadline is the 10th of July each quarter, so make sure you file "
            "by then."
        ),
        "lang": "en",
        "expect": "clobber",
    },
    # 5. property_zoning (duration pass / operation clobber) -------------------
    {
        "guard": "_guard_property_zoning_reply",
        "message": "How long is a typical villa leasehold in Bali?",
        "reply": (
            "A villa leasehold in Bali typically runs 25 to 30 years, often with an "
            "option to extend by negotiation with the landowner."
        ),
        "lang": "en",
        "expect": "pass",
    },
    {
        "guard": "_guard_property_zoning_reply",
        "message": "Can I run my villa as an Airbnb short-stay in a residential zone?",
        "reply": (
            "Sure, just list it on Airbnb and start taking daily guests, no special "
            "permit needed for a residential villa."
        ),
        "lang": "en",
        "expect": "clobber",
    },
    # 6. tax_compliance (APPEND; 'verify' suffix) -----------------------------
    {
        "guard": "_guard_tax_compliance_reply",
        "message": "What is the current VAT rate in Indonesia?",
        "reply": (
            "VAT in Indonesia is 11% effective (12% headline under PMK 131/2024); full "
            "12% applies only to luxury goods subject to PPnBM."
        ),
        "lang": "en",
        "expect": "pass",
    },
    {
        "guard": "_guard_tax_compliance_reply",
        "message": "What is the penalty risk if my PT PMA files PPN late?",
        "reply": "Late PPN filing exposes the company to administrative fines and interest.",
        "lang": "en",
        "expect": "clobber",
    },
    # 7. villa_kbli ------------------------------------------------------------
    {
        "guard": "_guard_villa_kbli_reply",
        "message": "Which KBLI code covers villa short-stay accommodation under KBLI 2025?",
        "reply": (
            "For villa/Airbnb short-stay the current KBLI 2025 direction is 55203 "
            "(AKTIVITAS VILA); 55193 is the KBLI 2020/PP28 source code that maps to it. "
            "Final filing must be verified against live OSS/BKPM."
        ),
        "lang": "en",
        "expect": "pass",
    },
    {
        "guard": "_guard_villa_kbli_reply",
        "message": "Which KBLI code covers villa short-stay accommodation under KBLI 2025?",
        "reply": (
            "For your villa rental business you should register under KBLI 59201 for "
            "sound recording activities."
        ),
        "lang": "en",
        "expect": "clobber",
    },
    # 8. kbli_label (PREPEND) --------------------------------------------------
    {
        "guard": "_guard_kbli_label_reply",
        "message": "What KBLI applies to a coffee shop PT PMA?",
        "reply": (
            "The KBLI to check is 56303 for cafe/drink house activity; final fit depends "
            "on menu and zoning."
        ),
        "lang": "en",
        "expect": "pass",
    },
    {
        "guard": "_guard_kbli_label_reply",
        "message": "What KBLI applies to a coffee shop PT PMA?",
        "reply": "A coffee shop usually maps to 56303 for cafe/drink house activity.",
        "lang": "en",
        "expect": "clobber",
    },
    # 9. cafe_pma (word-count > 115; message-intent gated) --------------------
    {
        "guard": "_guard_cafe_pma_reply",
        "message": "What's the difference between a PT PMA and a PT lokal?",
        "reply": (
            "A PT PMA allows foreign ownership and has a higher capital requirement; a "
            "PT lokal is fully Indonesian-owned. For example a cafe can use either "
            "depending on who owns it."
        ),
        "lang": "en",
        "expect": "pass",
    },
    {
        "guard": "_guard_cafe_pma_reply",
        "message": "Can I open a cafe in Canggu under a PT PMA?",
        "reply": _CAFE_WRONG_LONG,
        "lang": "en",
        "expect": "clobber",
    },
    # 10. nominee (compositional intent) --------------------------------------
    {
        "guard": "_guard_nominee_reply",
        "message": "Can my Indonesian friend hold the land title for me?",
        "reply": (
            "No — this is not just risky, it is illegal. A nominee arrangement is void "
            "under Indonesian agrarian law; the asset can fall to the State and you'd "
            "have no enforceable claim. The clean route is a PT PMA with HGB/Hak Pakai "
            "or a proper leasehold."
        ),
        "lang": "en",
        "expect": "pass",
    },
    {
        "guard": "_guard_nominee_reply",
        "message": "Can my Indonesian friend hold the land title for me?",
        "reply": (
            "That can be a bit risky, but many people do it and it usually works out "
            "fine in practice."
        ),
        "lang": "en",
        "expect": "clobber",
    },
]

# ---------------------------------------------------------------------------
# Language-gap sweep (2026-06-13). The original matrix was English-only while
# every guard gate carries (or lacked) ID/IT markers — the exact W73 class on
# the language axis. An empirical probe of the live guards found 10 real gaps:
# wrong ID/IT answers passing unclobbered (document_status "sudah disetujui",
# LKPM "10 luglio", zoning IT/ID never firing, cafe "caffè" never arming,
# tax "IVA" never arming, hak-milik accented "può detenere" slipping) and one
# over-match (a CORRECT Italian B211 "vecchia dicitura" answer clobbered).
# These cases pin the fixes. The META gate below now requires pass+clobber in
# ALL THREE languages for every guard, plus a no_trigger probe.
# ---------------------------------------------------------------------------

_HAK_MILIK_WRONG_LONG_IT = (
    "Si', certo, uno straniero può tranquillamente comprare e detenere terreno a "
    "Bali usando una delle tante strutture creative che gli expat usano con "
    "successo ogni giorno senza alcun problema legale reale. "
) * 5  # >125 words
_CAFE_WRONG_LONG_ID = (
    "Ya kafe bisa jalan lewat PT PMA kalau KBLI ownership dan lokasi cocok dan "
    "kamu cek 56303 dulu untuk kegiatan kafe rumah minum dan juga pertimbangkan "
    "arah restoran kalau menjual makanan lengkap dan fit final tergantung menu "
    "alkohol takeaway delivery dan zona lokasi Canggu jadi kirim konsep menu dan "
    "pin lokasi untuk verifikasi semuanya sebelum tanda tangan atau investasi "
    "sekarang juga ya. "
) * 2  # >115 words
_CAFE_WRONG_LONG_IT = (
    "Si', certo, un caffè funziona sempre con PT PMA e dettagli su menu alcol "
    "takeaway delivery e zona esatta a Canggu vanno verificati con cura prima di "
    "firmare un lease o investire capitale nella localita' scelta per il progetto "
    "del locale che vuoi aprire quest'anno. "
) * 4  # >115 words

GUARD_MATRIX_I18N: list[dict[str, Any]] = [
    # 1. document_status --------------------------------------------------------
    {
        "guard": "_guard_document_status_reply",
        "message": "Bagaimana status aplikasi KITAS saya, nomor aplikasi 12345?",
        "reply": (
            "Saya tidak bisa verifikasi status aplikasi dari WhatsApp saja. Saya "
            "teruskan referensinya ke team Bali Zero untuk cek status sebenarnya."
        ),
        "lang": "id",
        "expect": "pass",
    },
    {
        "guard": "_guard_document_status_reply",
        "message": "Bagaimana status aplikasi KITAS saya, nomor aplikasi 12345?",
        "reply": "KITAS kamu sudah disetujui dan siap diambil minggu ini.",
        "lang": "id",
        "expect": "clobber",
    },
    {
        "guard": "_guard_document_status_reply",
        # ID analogue of F37: conditional "setelah ... disetujui" is safe
        # explanatory text, NOT an affirmative status claim.
        "message": "Bagaimana status aplikasi KITAS saya nomor 12345?",
        "reply": (
            "Saya teruskan referensinya ke team Bali Zero untuk cek status "
            "sebenarnya. Setelah aplikasi disetujui oleh imigrasi, team akan "
            "konfirmasi langkah berikutnya."
        ),
        "lang": "id",
        "expect": "pass",
    },
    {
        "guard": "_guard_document_status_reply",
        "message": "Qual e' lo stato della mia pratica KITAS, numero pratica 12345?",
        "reply": (
            "Non posso verificare lo stato della pratica da WhatsApp. Passo il "
            "riferimento al team Bali Zero per controllare il file nel sistema."
        ),
        "lang": "it",
        "expect": "pass",
    },
    {
        "guard": "_guard_document_status_reply",
        "message": "Qual e' lo stato della mia pratica KITAS, numero pratica 12345?",
        "reply": "La tua pratica KITAS e' gia' approvata e pronta per il ritiro.",
        "lang": "it",
        "expect": "clobber",
    },
    {
        "guard": "_guard_document_status_reply",
        # No status/document/receipt term in the message → guard must not arm.
        "message": "How much is a C1 tourism visa extension?",
        "reply": "A C1 extension is handled by the team; pricing comes from the catalog.",
        "lang": "en",
        "expect": "no_trigger",
    },
    # 2. legacy_b211 ------------------------------------------------------------
    {
        "guard": "_guard_legacy_b211_reply",
        "message": "Apakah B211A masih visa yang benar untuk meeting bisnis di Bali?",
        "reply": (
            "Anggap B211/B211A sebagai istilah lama: rute saat ini biasanya C2 "
            "Business atau C12 Pre-Investment; team akan verifikasi."
        ),
        "lang": "id",
        "expect": "pass",
    },
    {
        "guard": "_guard_legacy_b211_reply",
        "message": "Apakah B211A masih visa yang benar untuk meeting bisnis di Bali?",
        "reply": "Ya, B211A adalah visa yang tepat untuk bisnis di Indonesia, silakan apply.",
        "lang": "id",
        "expect": "clobber",
    },
    {
        "guard": "_guard_legacy_b211_reply",
        # The over-match found by the 2026-06-13 sweep: a CORRECT Italian
        # answer framing B211 as "una vecchia dicitura" was clobbered.
        "message": "Il B211A e' ancora il visto giusto per un meeting di lavoro a Bali?",
        "reply": (
            "Il B211/B211A e' una vecchia dicitura: oggi la rotta corrente per "
            "business meeting e' di solito C2 Business o C12 Pre-Investment; il "
            "team verifica il caso."
        ),
        "lang": "it",
        "expect": "pass",
    },
    {
        "guard": "_guard_legacy_b211_reply",
        "message": "Il B211A e' ancora il visto giusto per un meeting di lavoro a Bali?",
        "reply": "Si', il B211A e' esattamente il visto da richiedere per fare business in Indonesia.",
        "lang": "it",
        "expect": "clobber",
    },
    {
        "guard": "_guard_legacy_b211_reply",
        "message": "What visa do I need for a business meeting in Jakarta?",
        "reply": "For short business meetings the usual route is C2 Business; the team verifies.",
        "lang": "en",
        "expect": "no_trigger",
    },
    # 3. hak_milik ----------------------------------------------------------------
    {
        "guard": "_guard_hak_milik_reply",
        "message": "Apakah orang asing bisa punya tanah Hak Milik di Bali?",
        "reply": (
            "Tidak. Orang asing tidak bisa memegang Hak Milik langsung; PT PMA "
            "biasanya pakai HGB, atau Hak Pakai untuk residensial. Team Bali Zero "
            "bisa cek rutenya."
        ),
        "lang": "id",
        "expect": "pass",
    },
    {
        "guard": "_guard_hak_milik_reply",
        "message": "Apakah orang asing bisa punya tanah Hak Milik di Bali?",
        "reply": "Tentu, orang asing bisa memegang Hak Milik lewat PMA tanpa masalah.",
        "lang": "id",
        "expect": "clobber",
    },
    {
        "guard": "_guard_hak_milik_reply",
        # Accented Italian negation must be recognized as the CORRECT framing.
        "message": "Uno straniero può comprare terreno Hak Milik a Bali?",
        "reply": (
            "No. Uno straniero non può detenere Hak Milik direttamente; una PT PMA "
            "guarda a HGB o Hak Pakai. Il legal team Bali Zero verifica la rotta."
        ),
        "lang": "it",
        "expect": "pass",
    },
    {
        "guard": "_guard_hak_milik_reply",
        # Accented Italian WRONG claim ("può detenere") slipped before the fix.
        "message": "Uno straniero può comprare terreno Hak Milik a Bali?",
        "reply": "Si', uno straniero può detenere Hak Milik tramite una PT PMA senza problemi.",
        "lang": "it",
        "expect": "clobber",
    },
    {
        "guard": "_guard_hak_milik_reply",
        "message": "Can a foreigner lease land long-term in Bali?",
        "reply": "Yes, leasehold is a standard route for foreigners; terms run 25-30 years.",
        "lang": "en",
        "expect": "no_trigger",
    },
    # 4. lkpm ---------------------------------------------------------------------
    {
        "guard": "_guard_lkpm_reply",
        "message": "Apa itu LKPM?",
        "reply": (
            "LKPM adalah laporan realisasi investasi yang disampaikan PT PMA ke "
            "BKPM lewat OSS, biasanya triwulanan untuk usaha menengah dan besar."
        ),
        "lang": "id",
        "expect": "pass",
    },
    {
        "guard": "_guard_lkpm_reply",
        "message": "Kapan deadline LKPM triwulan kedua?",
        "reply": "Batas waktu LKPM adalah tanggal 10 Juli setiap tahun, pastikan lapor sebelum itu.",
        "lang": "id",
        "expect": "clobber",
    },
    {
        "guard": "_guard_lkpm_reply",
        "message": "Cos'e' l'LKPM e chi deve presentarlo?",
        "reply": (
            "L'LKPM e' il report di realizzazione investimenti che una PT PMA "
            "presenta a BKPM tramite OSS, di solito trimestrale per societa' "
            "medio-grandi."
        ),
        "lang": "it",
        "expect": "pass",
    },
    {
        "guard": "_guard_lkpm_reply",
        "message": "Quando scade l'LKPM del secondo trimestre?",
        "reply": "La scadenza LKPM e' il 10 luglio di ogni anno, ricordati di inviarla entro quella data.",
        "lang": "it",
        "expect": "clobber",
    },
    {
        "guard": "_guard_lkpm_reply",
        # No "lkpm" in the message → a 10-July SPT deadline answer is none of
        # this guard's business.
        "message": "When is the corporate SPT Tahunan deadline?",
        "reply": "The corporate annual SPT is due by the end of the fourth month after fiscal year-end.",
        "lang": "en",
        "expect": "no_trigger",
    },
    # 5. property_zoning ----------------------------------------------------------
    {
        "guard": "_guard_property_zoning_reply",
        "message": "Boleh saya sewakan villa saya sebagai Airbnb harian di zona residensial?",
        "reply": (
            "Tidak otomatis. Tamu harian biasanya short-stay accommodation, jadi perlu "
            "cek zoning, lease, izin landlord, dan NIB/OSS; selama transisi KBLI, "
            "BKPM/OSS harus diverifikasi live."
        ),
        "lang": "id",
        "expect": "pass",
    },
    {
        "guard": "_guard_property_zoning_reply",
        "message": "Boleh saya sewakan villa saya sebagai Airbnb harian di zona residensial?",
        "reply": (
            "Boleh saja, langsung pasang di Airbnb dan terima tamu harian, tidak perlu "
            "izin khusus untuk villa residensial."
        ),
        "lang": "id",
        "expect": "clobber",
    },
    {
        "guard": "_guard_property_zoning_reply",
        "message": "Posso affittare la mia villa come Airbnb in zona residenziale a Canggu?",
        "reply": (
            "Non automaticamente. Gli ospiti giornalieri sono short-stay accommodation: "
            "servono check su zoning, lease, consenso del landlord e NIB/OSS; durante la "
            "transizione KBLI serve verifica live BKPM/OSS."
        ),
        "lang": "it",
        "expect": "pass",
    },
    {
        "guard": "_guard_property_zoning_reply",
        "message": "Posso affittare la mia villa come Airbnb in zona residenziale a Canggu?",
        "reply": (
            "Certo, mettila su Airbnb e accetta ospiti giornalieri, non serve nessun "
            "permesso speciale per una villa residenziale."
        ),
        "lang": "it",
        "expect": "clobber",
    },
    {
        "guard": "_guard_property_zoning_reply",
        # No villa/airbnb arm in the message → restaurant zoning is out of scope.
        "message": "What zoning applies to a restaurant in Seminyak?",
        "reply": "Restaurant zoning in Seminyak depends on the local RDTR; the team can check the pin.",
        "lang": "en",
        "expect": "no_trigger",
    },
    # 6. tax_compliance -----------------------------------------------------------
    {
        "guard": "_guard_tax_compliance_reply",
        "message": "Apa risiko kalau PT PMA saya telat lapor PPN?",
        "reply": "Telat lapor PPN membuka risiko denda administratif dan bunga.",
        "lang": "id",
        "expect": "clobber",
    },
    {
        "guard": "_guard_tax_compliance_reply",
        "message": "Berapa tarif PPN sekarang?",
        "reply": (
            "Tarif headline PPN 12%, tapi tarif efektif kebanyakan barang/jasa 11% "
            "lewat mekanisme DPP Nilai Lain 11/12; 12% penuh hanya untuk barang "
            "mewah PPnBM."
        ),
        "lang": "id",
        "expect": "pass",
    },
    {
        "guard": "_guard_tax_compliance_reply",
        "message": "Quali rischi corre la mia PT PMA se paga l'IVA in ritardo?",
        "reply": "Il ritardo nel pagamento espone la societa' a sanzioni amministrative e interessi.",
        "lang": "it",
        "expect": "clobber",
    },
    {
        "guard": "_guard_tax_compliance_reply",
        "message": "Qual e' l'aliquota IVA attuale in Indonesia?",
        "reply": (
            "L'aliquota headline e' 12%, ma l'aliquota effettiva sulla maggior parte di "
            "beni e servizi e' 11% (meccanismo DPP Nilai Lain 11/12); il 12% pieno vale "
            "solo per i beni di lusso PPnBM."
        ),
        "lang": "it",
        "expect": "pass",
    },
    {
        "guard": "_guard_tax_compliance_reply",
        # F36 class: "translate" must not arm the risk suffix via "late".
        "message": "Can you translate this rental contract into English?",
        "reply": "I can summarize the key clauses; for a certified translation the team can help.",
        "lang": "en",
        "expect": "no_trigger",
    },
    # 7. villa_kbli ---------------------------------------------------------------
    {
        "guard": "_guard_villa_kbli_reply",
        "message": "Kode KBLI mana yang benar untuk villa short stay, 55193 atau 55203?",
        "reply": (
            "Untuk villa/Airbnb short stay, arah KBLI 2025 adalah 55203 (AKTIVITAS "
            "VILA); 55193 adalah kode sumber KBLI 2020/PP28 yang dipetakan (mapping) "
            "ke 55203 di KBLI 2025. Finalnya diverifikasi live di OSS/BKPM."
        ),
        "lang": "id",
        "expect": "pass",
    },
    {
        "guard": "_guard_villa_kbli_reply",
        "message": "Kode KBLI mana yang benar untuk villa short stay, 55193 atau 55203?",
        "reply": "Untuk bisnis sewa villa kamu daftar saja di KBLI 59201 untuk aktivitas rekaman suara.",
        "lang": "id",
        "expect": "clobber",
    },
    {
        "guard": "_guard_villa_kbli_reply",
        "message": "Quale codice KBLI copre una villa short-stay nel KBLI 2025, 55193 o 55203?",
        "reply": (
            "Per villa/Airbnb short-stay la direzione KBLI 2025 e' 55203 (AKTIVITAS "
            "VILA); 55193 e' il codice sorgente KBLI 2020/PP28 che mappa a 55203 nel "
            "KBLI 2025. Il filing finale va verificato live su OSS/BKPM."
        ),
        "lang": "it",
        "expect": "pass",
    },
    {
        "guard": "_guard_villa_kbli_reply",
        "message": "Quale codice KBLI copre una villa short-stay nel KBLI 2025?",
        "reply": "Per la tua villa in affitto registra il KBLI 59201, attivita' di registrazione sonora.",
        "lang": "it",
        "expect": "clobber",
    },
    {
        "guard": "_guard_villa_kbli_reply",
        # F13 class, pinned in the matrix: "village" is not "villa".
        "message": "Which KBLI covers handicraft export from an Ubud village workshop?",
        "reply": "Handicraft manufacturing and export map to the 16xxx/47xxx families; the team verifies the exact code.",
        "lang": "en",
        "expect": "no_trigger",
    },
    # 8. kbli_label ---------------------------------------------------------------
    {
        "guard": "_guard_kbli_label_reply",
        "message": "Kode KBLI apa yang cocok untuk coffee shop PT PMA?",
        "reply": "Arah yang dicek 56303 untuk kafe/rumah minum; fit final tergantung menu dan zoning. Kode KBLI finalnya diverifikasi team.",
        "lang": "id",
        "expect": "pass",
    },
    {
        "guard": "_guard_kbli_label_reply",
        "message": "Kode KBLI apa yang cocok untuk coffee shop PT PMA?",
        "reply": "Coffee shop biasanya masuk 56303 untuk kegiatan kafe/rumah minum.",
        "lang": "id",
        "expect": "clobber",
    },
    {
        "guard": "_guard_kbli_label_reply",
        "message": "Che codice KBLI serve per una caffetteria con PT PMA?",
        "reply": "La direzione KBLI da controllare e' la 56303 per cafe/drink house; il fit finale dipende da menu e zoning.",
        "lang": "it",
        "expect": "pass",
    },
    {
        "guard": "_guard_kbli_label_reply",
        "message": "Che codice KBLI serve per una caffetteria con PT PMA?",
        "reply": "Una caffetteria di solito rientra nella 56303 per attivita' di caffe'/drink house.",
        "lang": "it",
        "expect": "clobber",
    },
    {
        "guard": "_guard_kbli_label_reply",
        # F38 class, pinned: a postcode is not a KBLI code.
        "message": "My address is Jalan Pantai Berawa, Canggu 80361 — can you send documents there?",
        "reply": "Sure, deliveries to Canggu 80361 are fine; the team will confirm the courier.",
        "lang": "en",
        "expect": "no_trigger",
    },
    # 9. cafe_pma -----------------------------------------------------------------
    {
        "guard": "_guard_cafe_pma_reply",
        "message": "Bisakah saya buka kafe di Canggu lewat PT PMA?",
        "reply": (
            "Ya, kafe bisa jalan lewat PT PMA kalau KBLI, ownership, dan lokasi cocok; "
            "arah pertama 56303. Kirim konsep dan pin lokasi, team verifikasi."
        ),
        "lang": "id",
        "expect": "pass",
    },
    {
        "guard": "_guard_cafe_pma_reply",
        "message": "Bisakah saya buka kafe di Canggu lewat PT PMA?",
        "reply": _CAFE_WRONG_LONG_ID,
        "lang": "id",
        "expect": "clobber",
    },
    {
        "guard": "_guard_cafe_pma_reply",
        "message": "Posso aprire un caffè a Canggu con una PT PMA?",
        "reply": (
            "Si', un caffè puo' funzionare con PT PMA se KBLI, ownership e location sono "
            "corretti; prima direzione 56303. Manda concept e pin, il team verifica."
        ),
        "lang": "it",
        "expect": "pass",
    },
    {
        "guard": "_guard_cafe_pma_reply",
        "message": "Posso aprire un caffè a Canggu con una PT PMA?",
        "reply": _CAFE_WRONG_LONG_IT,
        "lang": "it",
        "expect": "clobber",
    },
    {
        "guard": "_guard_cafe_pma_reply",
        # No "pt pma" in the message → the cafe canonical must not be substituted.
        "message": "Can you recommend a good cafe in Canggu for a meeting?",
        "reply": "Plenty of options around Batu Bolong; for business meetings quieter spots work better.",
        "lang": "en",
        "expect": "no_trigger",
    },
    # 10. nominee -----------------------------------------------------------------
    {
        "guard": "_guard_nominee_reply",
        "message": "Bisakah teman Indonesia saya memegang sertifikat tanah atas nama dia untuk saya?",
        "reply": (
            "Tidak — ini bukan sekadar berisiko, ini ilegal. Struktur nominee batal demi "
            "hukum agraria; tanahnya bisa jatuh ke negara. Jalur benar: PT PMA dengan "
            "HGB/Hak Pakai atau leasehold resmi."
        ),
        "lang": "id",
        "expect": "pass",
    },
    {
        "guard": "_guard_nominee_reply",
        "message": "Bisakah teman Indonesia saya memegang sertifikat tanah atas nama dia untuk saya?",
        "reply": "Agak berisiko sih, tapi banyak orang melakukannya dan biasanya aman saja.",
        "lang": "id",
        "expect": "clobber",
    },
    {
        "guard": "_guard_nominee_reply",
        "message": "Il mio amico indonesiano puo' intestare a suo nome il terreno per me?",
        "reply": (
            "No — non e' solo rischioso, e' illegale: una struttura nominee e' nulla per "
            "la legge agraria indonesiana e la terra puo' essere devoluta allo Stato. La "
            "strada corretta e' PT PMA con Hak Pakai/HGB o un leasehold regolare."
        ),
        "lang": "it",
        "expect": "pass",
    },
    {
        "guard": "_guard_nominee_reply",
        "message": "Il mio amico indonesiano puo' intestare a suo nome il terreno per me?",
        "reply": "E' un po' rischioso, ma molti lo fanno e di solito funziona senza problemi.",
        "lang": "it",
        "expect": "clobber",
    },
    {
        "guard": "_guard_nominee_reply",
        # Administrative naming (booking) is not nominee intent — F06 class.
        "message": "Can you book the hotel room under my wife's name?",
        "reply": "Sure — send her name as on the passport and the team will arrange the booking.",
        "lang": "en",
        "expect": "no_trigger",
    },
]

GUARD_MATRIX.extend(GUARD_MATRIX_I18N)


def _discover_guards() -> set[str]:
    """Every _guard_* callable in the live bridge module (dynamic)."""
    return {
        name
        for name in dir(bridge)
        if name.startswith("_guard_") and callable(getattr(bridge, name))
    }


# Localized action markers for the APPEND/PREPEND guards (the suffix/prefix is
# language-routed by _villa_answer_language, so the assertion must be too).
_TAX_SUFFIX_MARKERS = {"en": "verify", "id": "verifikasi", "it": "verificare"}
_KBLI_PREFIX_MARKERS = {
    "en": "KBLI direction to check",
    "id": "Arah KBLI yang perlu dicek",
    "it": "Direzione KBLI da verificare",
}

# Mythos M2 (2026-06-14): the 8 SUBSTITUTION guards (those that REPLACE a wrong
# reply with a canned canonical, as opposed to the 2 APPEND/PREPEND guards). For
# these, asserting only `out != reply` on a clobber is too weak — a guard that
# clobbers with the WRONG canonical (cross-guard contamination, the W73 #1
# "villa-eats-food-import" class) would still pass. The matrix-polarity test now
# asserts the clobber lands on THIS guard's own canonical, in the case's language.
# Map: guard name -> the _canonical_*_answer(language) builder it must produce.
# Single source of truth so a new substitution guard is wired here once.
_SUBSTITUTION_CANONICAL = {
    "_guard_document_status_reply": "_canonical_document_status_answer",
    "_guard_legacy_b211_reply": "_canonical_b211_business_answer",
    "_guard_hak_milik_reply": "_canonical_hak_milik_answer",
    "_guard_lkpm_reply": "_canonical_lkpm_answer",
    "_guard_property_zoning_reply": "_canonical_property_zoning_answer",
    "_guard_villa_kbli_reply": "_canonical_villa_kbli_answer",
    "_guard_cafe_pma_reply": "_canonical_cafe_pma_answer",
    "_guard_nominee_reply": "_canonical_nominee_answer",
}


@pytest.mark.parametrize(
    "case",
    GUARD_MATRIX,
    ids=[f"{c['guard']}-{c['lang']}-{c['expect']}" for c in GUARD_MATRIX],
)
def test_guard_matrix_polarity(case: dict[str, Any]) -> None:
    """pass/no_trigger == reply survives unchanged; clobber == reply is changed.

    'pass' is an on-topic CORRECT answer the guard must not destroy;
    'no_trigger' is an out-of-domain message the guard must not even arm on
    (the substring-trap class). For APPEND/PREPEND guards a 'clobber' is still
    a change; we additionally assert the language-routed marker so a guard
    that mutates the WRONG way (or in the wrong language) still fails.
    """
    guard = getattr(bridge, case["guard"])
    out = guard(case["message"], case["reply"], case["lang"])

    if case["expect"] in ("pass", "no_trigger"):
        assert out == case["reply"], (
            f"{case['guard']} mutated a reply it must leave alone "
            f"({case['expect']}, lang={case['lang']}): {out!r}"
        )
    else:  # clobber
        assert out != case["reply"], (
            f"{case['guard']} failed to clobber a WRONG answer "
            f"(lang={case['lang']}): {out!r}"
        )
        # Action-specific marker so a wrong-direction mutation still fails.
        if case["guard"] == "_guard_tax_compliance_reply":  # APPEND
            assert out.startswith(case["reply"].rstrip())
            assert _TAX_SUFFIX_MARKERS[case["lang"]] in out.lower()
        elif case["guard"] == "_guard_kbli_label_reply":  # PREPEND
            assert out.startswith(_KBLI_PREFIX_MARKERS[case["lang"]])
            assert out.rstrip().endswith(case["reply"].rstrip())
        elif case["guard"] in _SUBSTITUTION_CANONICAL:
            # SUBSTITUTION guard: the clobber must land on THIS guard's OWN
            # canonical (cross-guard contamination guard, Mythos M2 2026-06-14).
            builder = getattr(bridge, _SUBSTITUTION_CANONICAL[case["guard"]])
            expected = builder(case["lang"])
            assert out == expected, (
                f"{case['guard']} clobbered to the WRONG canonical "
                f"(lang={case['lang']}): expected its own "
                f"{_SUBSTITUTION_CANONICAL[case['guard']]}, got {out!r}"
            )


def test_guard_matrix_covers_every_guard_both_polarities() -> None:
    """META gate: every _guard_* must have a 'pass' AND a 'clobber' matrix case.

    A newly-added guard with no entry (or only one polarity) FAILS here — that
    is the anti-regression gate (W68/W72/W73 class). Discovery is dynamic, so no
    hand-maintained list can drift out of sync with the module.
    """
    discovered = _discover_guards()
    assert discovered, "no _guard_* functions discovered — loader/module broken"

    polarities: dict[str, set[str]] = {}
    for case in GUARD_MATRIX:
        polarities.setdefault(case["guard"], set()).add(case["expect"])

    # Every matrix entry must name a guard that actually exists in the module.
    unknown = set(polarities) - discovered
    assert not unknown, f"GUARD_MATRIX names nonexistent guards: {sorted(unknown)}"

    missing_pass = sorted(g for g in discovered if "pass" not in polarities.get(g, set()))
    missing_clobber = sorted(
        g for g in discovered if "clobber" not in polarities.get(g, set())
    )
    assert not missing_pass and not missing_clobber, (
        "GUARD_MATRIX incomplete — add cases for these guards "
        f"(missing pass: {missing_pass}; missing clobber: {missing_clobber})"
    )


# ---------------------------------------------------------------------------
# Full-chain integration (2026-06-13). The single-guard matrix above cannot
# catch ORDERING bugs: an upstream guard clobbering a correct reply before the
# right guard ever sees it, or two guards double-mutating. _apply_reply_guards
# is the single source of truth for the production chain (the endpoint calls
# it), so these tests exercise exactly what ships.
# ---------------------------------------------------------------------------


def test_chain_correct_zoning_reply_survives_whole_chain() -> None:
    message = "Can I run my villa as an Airbnb short-stay in a residential zone?"
    reply = (
        "Not automatically. Daily guests are short-stay accommodation, so you need "
        "zoning, lease, landlord consent, and NIB/OSS checks; during the KBLI "
        "transition Bali Zero verifies live OSS/BKPM availability."
    )
    assert bridge._apply_reply_guards(message, reply, "en") == reply


def test_chain_wrong_nominee_reply_gets_nominee_canonical_not_another() -> None:
    message = "Can my Indonesian friend hold the land title for me?"
    reply = "That can be a bit risky, but many people do it and it works out fine."
    out = bridge._apply_reply_guards(message, reply, "en")
    assert out == bridge._canonical_nominee_answer("en"), (
        "the WRONG nominee answer must be replaced by the NOMINEE canonical, "
        f"not by another guard's: {out!r}"
    )


def test_chain_lkpm_canonical_not_double_mutated_by_tax_guard() -> None:
    # Message arms BOTH the lkpm guard (stale deadline) and the tax guard
    # (penalty intent). The LKPM canonical already carries 'verify', so the
    # tax suffix must NOT be appended on top of the substituted canonical.
    message = "What is the penalty if I miss the LKPM deadline?"
    reply = "The LKPM deadline is the 10th of July; missing it brings fines."
    out = bridge._apply_reply_guards(message, reply, "en")
    assert out == bridge._canonical_lkpm_answer("en"), (
        f"expected the clean LKPM canonical, got a double-mutated reply: {out!r}"
    )


def test_chain_italian_cafe_wrong_reply_gets_italian_cafe_canonical() -> None:
    message = "Posso aprire un caffè a Canggu con una PT PMA?"
    out = bridge._apply_reply_guards(message, _CAFE_WRONG_LONG_IT, "it")
    assert out == bridge._canonical_cafe_pma_answer("it")


def test_chain_format_net_applies_after_guards() -> None:
    # A correct reply that passes every guard still gets the WhatsApp format
    # net (markdown bold → WhatsApp bold) as the LAST step.
    message = "How long is a typical villa leasehold in Bali?"
    reply = "A villa leasehold typically runs **25 to 30 years**, extension negotiable."
    out = bridge._apply_reply_guards(message, reply, "en")
    assert out == "A villa leasehold typically runs *25 to 30 years*, extension negotiable."


def test_chain_endpoint_and_tests_share_the_same_chain() -> None:
    """The endpoint must call _apply_reply_guards (no inline drift): every
    guard in the module is in _REPLY_GUARD_CHAIN exactly once."""
    chain_names = [fn.__name__ for fn in bridge._REPLY_GUARD_CHAIN]
    assert sorted(chain_names) == sorted(_discover_guards()), (
        "a _guard_* exists that is NOT wired into _REPLY_GUARD_CHAIN "
        "(or is wired twice) — the chain and the module drifted"
    )
    assert len(chain_names) == len(set(chain_names))


def test_substitution_canonical_map_does_not_drift_from_module() -> None:
    """META gate (Mythos M2 2026-06-14): every guard that returns a
    `_canonical_*_answer` (a SUBSTITUTION guard) must be wired into
    `_SUBSTITUTION_CANONICAL` so the strict cross-contamination assertion in
    `test_guard_matrix_polarity` actually covers it.

    Discovery is dynamic — read each guard's source for `return _canonical_…`.
    A new substitution guard that forgets its entry here FAILS, exactly the way
    `_discover_guards()` gates per-guard matrix coverage. This is the structural
    antibody: the strict assertion can never silently stop covering a guard.
    """
    import inspect
    import re

    returns_canonical: dict[str, set[str]] = {}
    for name in _discover_guards():
        src = inspect.getsource(getattr(bridge, name))
        canonicals = set(re.findall(r"return (_canonical_[a-z0-9_]+_answer)", src))
        if canonicals:
            returns_canonical[name] = canonicals

    # 1. Every substitution guard is mapped.
    unmapped = sorted(set(returns_canonical) - set(_SUBSTITUTION_CANONICAL))
    assert not unmapped, (
        "substitution guard(s) missing from _SUBSTITUTION_CANONICAL — the strict "
        f"clobber-canonical assertion does not cover them: {unmapped}"
    )
    # 2. No stale entries naming a guard that no longer substitutes.
    stale = sorted(set(_SUBSTITUTION_CANONICAL) - set(returns_canonical))
    assert not stale, f"_SUBSTITUTION_CANONICAL names non-substitution guard(s): {stale}"
    # 3. The mapped canonical is one the guard actually returns (no wrong target).
    for guard, expected in _SUBSTITUTION_CANONICAL.items():
        assert expected in returns_canonical[guard], (
            f"{guard} is mapped to {expected} but its body returns "
            f"{sorted(returns_canonical[guard])}"
        )


def test_guard_matrix_covers_languages_and_no_trigger() -> None:
    """META gate, language axis (2026-06-13 sweep): every _guard_* must have a
    'pass' AND a 'clobber' case in EACH of en/id/it, plus at least one
    'no_trigger' probe (out-of-domain message left untouched).

    The 2026-06-13 empirical sweep found 10 real language gaps (wrong ID/IT
    answers passing, one correct IT answer clobbered) precisely because the
    matrix was English-only. A new guard — or a new language path in an
    existing guard — now fails here until it carries trilingual coverage.
    """
    required_langs = ("en", "id", "it")
    discovered = _discover_guards()

    coverage: dict[str, dict[str, set[str]]] = {}
    no_trigger: dict[str, int] = {}
    for case in GUARD_MATRIX:
        if case["expect"] == "no_trigger":
            no_trigger[case["guard"]] = no_trigger.get(case["guard"], 0) + 1
            continue
        coverage.setdefault(case["guard"], {}).setdefault(case["lang"], set()).add(
            case["expect"]
        )

    problems: list[str] = []
    for guard in sorted(discovered):
        for lang in required_langs:
            have = coverage.get(guard, {}).get(lang, set())
            for polarity in ("pass", "clobber"):
                if polarity not in have:
                    problems.append(f"{guard}: missing {polarity} case for lang={lang}")
        if not no_trigger.get(guard):
            problems.append(f"{guard}: missing no_trigger probe")
    assert not problems, "GUARD_MATRIX language coverage incomplete:\n" + "\n".join(
        problems
    )
