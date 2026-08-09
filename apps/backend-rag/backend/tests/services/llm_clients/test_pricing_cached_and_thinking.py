"""The ledger must see cached and thinking tokens.

Born from the 2026-08-09 spend audit. `llm_cost_events` reported $51.31/30d on
`gemini-3.5-flash` while being wrong in BOTH directions at once:

  - it billed every prompt token at the full input rate, though implicit context
    caching is ON BY DEFAULT for all Gemini 2.5+ models (our stable prompt prefix
    is 5,103 tokens, over the 4,096 eligibility threshold) → OVERSTATED the bill;
  - it never read `thoughts_token_count`, which Gemini reports separately from
    `candidates_token_count` and bills at the OUTPUT rate → UNDERSTATED the bill.

`cache_hit_tokens` had been a parameter of `record_llm_call` the whole time and
only the (retired) DeepSeek client ever passed it, so a zero in that column meant
"nobody measured", not "no cache hit" — the exact shape of a meter that lies.

Guilt AND innocence on every claim: a discount that also fires when there is no
cache hit would be a new lie with the opposite sign.
"""

import pytest

from backend.services.llm_clients.pricing import (
    LLM_PRICING,
    calculate_cost,
    create_token_usage,
    extract_gemini_usage,
    get_model_pricing,
    resolve_pricing,
)

MODEL = "gemini-3.5-flash"  # $1.50 in / $9.00 out / $0.15 cached (verified 2026-08-09)


class _FakeUsage:
    """Stand-in for google-genai's GenerateContentResponseUsageMetadata."""

    def __init__(self, prompt=0, candidates=0, cached=0, thoughts=0):
        self.prompt_token_count = prompt
        self.candidates_token_count = candidates
        self.cached_content_token_count = cached
        self.thoughts_token_count = thoughts


# ── extract_gemini_usage ────────────────────────────────────────────────────


def test_extract_reads_all_four_fields():
    """GUILT: the two previously-invisible fields must come back non-zero."""
    assert extract_gemini_usage(_FakeUsage(1000, 50, 800, 30)) == (1000, 50, 800, 30)


def test_extract_survives_missing_metadata():
    """INNOCENCE: no usage object must never raise — cost accounting is fail-open."""
    assert extract_gemini_usage(None) == (0, 0, 0, 0)


def test_extract_treats_none_fields_as_zero():
    """The SDK leaves these None when the model reports nothing."""
    assert extract_gemini_usage(_FakeUsage(None, None, None, None)) == (0, 0, 0, 0)


def test_extract_zeroes_a_field_that_is_not_a_number():
    """INNOCENCE for the live path, and a real regression this caught.

    A meter handed something it cannot interpret must record nothing, never
    take the answer down with it. Before this, a non-numeric field flowed
    into the cache clamp and raised
    `TypeError: '<' not supported between instances of 'int' and 'MagicMock'` —
    four gateway tests went red, and in production the same shape would have
    turned an unreadable usage field into a failed chat response.
    """
    opaque = object()
    assert extract_gemini_usage(_FakeUsage(opaque, "12", [], opaque)) == (0, 0, 0, 0)


def test_extract_does_not_meter_a_boolean_as_one_token():
    """`bool` is an `int` subclass: True would silently meter as 1 token —
    a wrong number, which is worse than a missing one."""
    assert extract_gemini_usage(_FakeUsage(True, False, True, True)) == (0, 0, 0, 0)


def test_calculate_cost_survives_non_numeric_usage_end_to_end():
    """GUILT: the crash was in the composition, so assert the composition."""
    tokens = extract_gemini_usage(_FakeUsage(object(), object(), object(), object()))
    assert calculate_cost(*tokens[:2], MODEL, cached_tokens=tokens[2], thinking_tokens=tokens[3]) == 0.0


# ── cached tokens ───────────────────────────────────────────────────────────


def test_cached_tokens_are_cheaper_than_fresh_ones():
    """GUILT: a cache hit must cost less than the same prompt with no hit."""
    no_cache = calculate_cost(10_000, 100, MODEL)
    with_cache = calculate_cost(10_000, 100, MODEL, cached_tokens=8_000)
    assert with_cache < no_cache


def test_cached_tokens_are_a_subset_of_prompt_tokens_not_an_addition():
    """Gemini's prompt_token_count ALREADY includes the cache hit.

    Billing them additively would invent tokens nobody sent. Fully-cached prompt
    → exactly the cached rate on every token, nothing at the full rate.
    """
    cost = calculate_cost(10_000, 0, MODEL, cached_tokens=10_000)
    assert cost == pytest.approx(10_000 / 1e6 * 0.15)


def test_cached_tokens_are_clamped_to_the_prompt():
    """A provider reporting more cached than prompt must not mint a negative charge."""
    assert calculate_cost(1_000, 0, MODEL, cached_tokens=99_999) == pytest.approx(
        1_000 / 1e6 * 0.15
    )


def test_model_without_a_cached_rate_bills_cache_at_the_full_input_rate():
    """INNOCENCE (conservative default): absent a published cached rate we must
    NEVER invent a discount. `gemini-3-flash-preview` has no `cached_input` key."""
    legacy = "gemini-3-flash-preview"
    assert "cached_input" not in LLM_PRICING[legacy]
    assert calculate_cost(1_000, 0, legacy, cached_tokens=1_000) == calculate_cost(
        1_000, 0, legacy
    )


# ── thinking tokens ─────────────────────────────────────────────────────────


def test_thinking_tokens_are_billed_at_the_output_rate():
    """GUILT: reasoning tokens cost money and were invisible.

    https://ai.google.dev/gemini-api/docs/thinking — "response pricing is the sum
    of output tokens and thinking tokens".
    """
    without = calculate_cost(0, 100, MODEL)
    with_thoughts = calculate_cost(0, 100, MODEL, thinking_tokens=400)
    assert with_thoughts == pytest.approx(without + 400 / 1e6 * 9.00)


def test_negative_thinking_tokens_cannot_create_a_credit():
    assert calculate_cost(0, 100, MODEL, thinking_tokens=-500) == calculate_cost(0, 100, MODEL)


# ── innocence: the un-cached, un-thinking path is byte-identical to before ──


def test_plain_call_is_unchanged_by_this_feature():
    """INNOCENCE: with neither cache nor thinking, the number must equal the
    old formula exactly — this change re-prices nothing that was already right."""
    expected = 18_168 / 1e6 * 1.50 + 211 / 1e6 * 9.00
    assert calculate_cost(18_168, 211, MODEL) == pytest.approx(expected)


def test_measured_thirty_day_volume_still_reproduces_the_ledger():
    """Anchor on real traffic: the 2026-07-10→08-09 gemini-3.5-flash volume from
    `llm_cost_events` priced at list must land on the $51.18 the ledger recorded.
    If someone edits the rate table by accident, this is the tripwire."""
    cost = calculate_cost(31_420_905, 449_849, MODEL)
    assert cost == pytest.approx(51.18, abs=0.05)


# ── longest-match resolution (superscar #3: form standing in for entity) ────


def test_suffixed_lite_slug_resolves_to_lite_not_to_its_parent():
    """GUILT: `gemini-3.5-flash` is a substring of `gemini-3.5-flash-lite`.

    First-match-wins would bill a suffixed lite slug at the parent's $1.50
    instead of $0.30 — a 5x over-charge from a substring standing in for an
    entity. Only reachable once the lite tier entered the table.
    """
    assert resolve_pricing("gemini-3.5-flash-lite-preview-09-2026")["input"] == 0.30


def test_exact_slugs_still_resolve_to_themselves():
    """INNOCENCE: longest-match must not disturb the plain names."""
    assert resolve_pricing("gemini-3.5-flash")["input"] == 1.50
    assert resolve_pricing("gemini-2.5-flash-lite")["input"] == 0.10


def test_get_model_pricing_agrees_with_resolve_pricing():
    """Two functions answering "what does this model cost" must not disagree on
    which row wins — they used to carry two independent copies of the match loop."""
    for slug in ("gemini-3.5-flash-lite-preview-09-2026", "gemini-2.5-flash", "totally-unknown"):
        assert get_model_pricing(slug) == resolve_pricing(slug)


def test_unknown_model_still_falls_back_and_is_not_matched_by_substring():
    """INNOCENCE: `unknown` is excluded from partial matching, so a real slug
    can never be silently priced by the fallback row through a substring fluke."""
    assert resolve_pricing("some-model-nobody-registered") is LLM_PRICING["unknown"]


# ── an abbreviation that fits several models identifies none of them ────────


@pytest.mark.parametrize(
    ("slug", "matches"),
    [
        ("gemini-3.5", "gemini-3.5-flash and gemini-3.5-flash-lite"),
        ("gemini", "every gemini row"),
        ("flash", "every flash row — it used to land on DeepSeek's table"),
    ],
)
def test_ambiguous_abbreviation_refuses_to_guess(slug, matches):
    """GUILT: a truncated slug must not be silently priced by whichever row
    the match loop happens to prefer.

    Longest-match is right when the TABLE KEY sits inside the slug (a real
    model wearing a suffix), and wrong in the other direction: taking the
    longest of {gemini-3.5-flash, gemini-3.5-flash-lite} for the abbreviation
    `gemini-3.5` picked the CHEAPER child and under-billed, while `flash`
    reached across providers entirely. Found by adversarial review (Codex,
    2026-08-09) on the very change that introduced longest-match.
    """
    assert resolve_pricing(slug) is LLM_PRICING["unknown"], matches


def test_unambiguous_abbreviation_still_resolves():
    """INNOCENCE: refusing ambiguity must not break the one-row abbreviation.

    `deepseek-chat` names exactly one key (`deepseek/deepseek-chat`), and
    test_pricing.py::test_calculate_cost_partial_match depends on it.
    """
    assert resolve_pricing("deepseek-chat") is LLM_PRICING["deepseek/deepseek-chat"]


def test_official_paid_tier_rates_for_every_gemini_row_we_route_to():
    """TRIPWIRE: rates verified verbatim against ai.google.dev/gemini-api/docs/pricing.

    `gemini-2.5-flash` shipped for months at 0.075/0.30 — a rate from two
    generations back, 4x under on input and 8.33x under on output — and the
    old unit test asserted the wrong numbers, so the table and its test agreed
    with each other and with nothing else. Anchor on the price list.
    """
    expected = {
        "gemini-3.5-flash": (1.50, 9.00, 0.15),
        "gemini-3.6-flash": (1.50, 7.50, 0.15),
        "gemini-2.5-flash": (0.30, 2.50, 0.03),
        "gemini-3.5-flash-lite": (0.30, 2.50, 0.03),
        "gemini-3.1-flash-lite": (0.25, 1.50, 0.025),
        "gemini-2.5-flash-lite": (0.10, 0.40, 0.01),
    }
    for slug, (inp, out, cached) in expected.items():
        row = LLM_PRICING[slug]
        assert (row["input"], row["output"], row["cached_input"]) == (inp, out, cached), slug


# ── one call, one price: the ledger and the spend cap must agree ────────────


def test_create_token_usage_prices_cache_and_thinking_like_the_ledger():
    """GUILT: `TokenUsage.cost_usd` feeds the gateway's per-request spend cap.

    While the ledger row saw the cache discount and the thinking tokens, this
    object saw neither — the same call carried two different prices depending
    on who asked.
    """
    usage = create_token_usage(
        prompt_tokens=10_000,
        completion_tokens=100,
        model=MODEL,
        cached_tokens=8_000,
        thinking_tokens=400,
    )
    assert usage.cost_usd == pytest.approx(
        calculate_cost(10_000, 100, MODEL, cached_tokens=8_000, thinking_tokens=400),
    )


def test_create_token_usage_without_the_new_counters_is_unchanged():
    """INNOCENCE: the OpenRouter fallback call site passes neither counter."""
    assert create_token_usage(10_000, 100, MODEL).cost_usd == pytest.approx(
        calculate_cost(10_000, 100, MODEL),
    )
