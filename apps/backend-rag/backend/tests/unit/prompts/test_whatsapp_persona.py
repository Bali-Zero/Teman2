"""
Regression guard: the WhatsApp persona must never inject a full price list.

Context (FIX 1, 2026-07-21): ``backend/prompts/whatsapp_persona.py`` used to
have a ``_load_full_pricing()`` helper that dumped the ENTIRE 2026 price
JSON (``bali_zero_official_prices_2026.json``) into ``build_system_prompt()``'s
output under an "OFFICIAL BALI ZERO 2026 PRICE LIST" header — a full
price-list injection that violates the "prices ONLY from PricingTool"
golden rule in spirit (project CLAUDE.md §8 Golden Rule #11 / §9 Data
Invariants). The call site (``process_whatsapp_message``'s Gemini-fallback
branch in ``app/routers/whatsapp_chat.py``, "Path A") is dormant in
production today — the live Meta Inbox number is routed elsewhere before
this module is ever reached — but a routing refactor could silently
reactivate it. This test pins the fix so the landmine cannot come back.
"""

import json
from pathlib import Path

from backend.prompts import whatsapp_persona
from backend.prompts.whatsapp_persona import build_system_prompt

# Exact header strings the old _load_full_pricing() injected, one per
# language build_system_prompt supports.
_OLD_PRICE_LIST_HEADERS = [
    "OFFICIAL BALI ZERO 2026 PRICE LIST",
    "LISTINO PREZZI UFFICIALE BALI ZERO 2026",
    "DAFTAR HARGA RESMI BALI ZERO 2026",
    "OFFIZIELLE BALI ZERO 2026 PREISLISTE",
]

_PRICING_FILE = (
    Path(__file__).resolve().parents[3] / "data" / "bali_zero_official_prices_2026.json"
)


def test_load_full_pricing_helper_removed():
    """The helper that dumped the JSON price file must not exist anymore —
    its mere presence was the landmine (importable/callable even while the
    one call site was dormant)."""
    assert not hasattr(whatsapp_persona, "_load_full_pricing")
    assert not hasattr(whatsapp_persona, "_PRICING_TABLE")
    assert not hasattr(whatsapp_persona, "_PRICING_TABLES")


def test_build_system_prompt_never_contains_price_list_header():
    """No language variant of build_system_prompt() output may contain the
    old 'use ONLY these prices' price-list header."""
    for lang in ("en", "it", "id", "de"):
        prompt = build_system_prompt(detected_language=lang)
        for header in _OLD_PRICE_LIST_HEADERS:
            assert header not in prompt, (
                f"build_system_prompt(lang={lang!r}) still injects a full "
                f"price-list header ({header!r}) — the landmine regressed."
            )


def test_build_system_prompt_never_contains_a_real_priced_entry():
    """Sanity anchor: a real entry from the 2026 price JSON must not leak
    verbatim into the persona prompt (would only happen if the full-dump
    behavior were reintroduced)."""
    assert _PRICING_FILE.exists(), f"Expected pricing file missing: {_PRICING_FILE}"
    data = json.loads(_PRICING_FILE.read_text(encoding="utf-8"))
    sample_entry = data["services"]["single_entry_visas"]["B1 Visa on Arrival (VOA)"]

    prompt = build_system_prompt(detected_language="en")
    assert sample_entry["price"] not in prompt
    assert "B1 Visa on Arrival (VOA)" not in prompt


def test_build_system_prompt_still_builds_a_persona_prompt():
    """The refactor must not break the function — it still returns a
    non-empty, per-language system prompt built on ZANTARA_MASTER_TEMPLATE."""
    prompt = build_system_prompt(
        client_name="Test Client",
        is_first_message=True,
        detected_language="en",
    )
    assert isinstance(prompt, str)
    assert prompt.strip()
    assert "Test Client" in prompt
