"""WA answer finalization pipeline — ONE sequence, used by BOTH generation legs.

Extracted 2026-08-19 from ``wa_inbox_bot.generate_bot_reply``'s post-generation
tail (BOT-V4 S2, spec
``research/operations/2026-08-19-bot-chatgpt-provider-broker-spec.md`` §2.3):
the sequence that turns a raw RAG/LLM payload into either "text safe to send on
WhatsApp" or a typed defect. Before this module, that sequence lived inline in
the Gemini leg only; the codex broker leg (S2 PR-5) needs the SAME pipeline, and
two hand-maintained copies of a safety sequence is how ``wa_inbox_bot`` and
``whatsapp_chat`` drifted apart on the ``[ESCALATE]`` marker in the first place.

Behavior contract:
    * ``provider="gemini"`` is BEHAVIOR-PRESERVING against the pre-extraction
      ``generate_bot_reply`` tail: same branch order, same log lines, same
      human-notification points, same returned text, and the same
      ``RuntimeError`` messages (the caller raises them from
      ``FinalizeResult.defect_message`` so the worker's retry ladder sees
      identical exceptions).
    * ``provider="codex"`` maps the spec's typed outcomes onto the same
      sequence: every branch where the TEXT ITSELF is defective (empty payload,
      internal-monologue leak — including inside a grounded abstain answer,
      scaffold-only output, empty after strip/format, oversized output,
      pricing veto, secret-egress hit) returns ``DEFECT`` WITHOUT serving a stub
      and WITHOUT telling a human — the caller (``wa_codex_leg.attempt``) falls
      off into the WORKER's retry ladder, not to a second generator (Gemini was
      retired from this worker 2026-08-27, Zero: "spegni gemini e collega
      chatgpt"): a LATER codex-leg attempt against a fresh claim re-enters this
      same pipeline, so the client still gets an answer once a clean attempt
      lands, and the silent-client alarm stays with the leg that owns it (spec
      §2.3 TEXT_DEFECT). The abstain-label branch is the one POLICY branch:
      its verdict derives from the frozen evidence, not from who wrote the
      text, so it behaves identically on both providers (stub + tell a human —
      failing off could not change the verdict, spec §2.3 POLICY).

Codex-only egress vetoes (inert on the Gemini leg by construction):
    * Pricing veto — every currency-marked amount in the answer must appear in
      at least one of the caller-supplied ``price_sources`` (the package's
      PricingTool block plus its retrieved chunks). Runs only when
      ``price_sources`` is provided, which only the codex worker leg does.
    * Secret-egress scan — pattern scan (key blocks, JWT shapes, token
      assignments, caller-supplied canary tokens) on text produced by the
      sandboxed executor. Runs only when ``secret_scan=True``. Never logs or
      returns the matched content — pattern NAME only (CLAUDE.md §14).

This module never talks to Telegram itself: the caller passes ``tell_a_human``
(a one-argument async callable) so ``wa_inbox_bot``'s tests keep patching
``wa_inbox_bot.notify_human_telegram`` and the notifier wiring stays in one
module.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any

from backend.channels.format import format_rich_text
from backend.services.rag.agentic._reasoning_stubs import get_localized_stub
from backend.services.rag.agentic.query_helpers import detect_query_language

logger = logging.getLogger("zantara.backend")

# ── KG workflow-scaffold strip (client-voice hardening, 2026-07-25) ──────
# `orchestrator_core.py::_format_workflow_for_prompt` appends an internal
# diagnostics block to the RAG answer on some queries — a "## SUGGESTED
# WORKFLOW (from <source>, confidence: NN%)" heading, the workflow name,
# a numbered step list, and an optional "**Confidence**: ..." line — ALWAYS
# closed by the literal trailer sentence below (`_KG_WORKFLOW_TRAILER`,
# copied verbatim from orchestrator_core.py). That block is internal
# diagnostics for an operator reading the raw answer, not a WhatsApp
# client, and has been observed CONTRADICTING the actual answer (e.g. an
# E33G remote-worker answer followed by a local-employment IMTA/TKA
# workflow it never asked for).
#
# We do NOT edit orchestrator_core.py (another lane owns it, and the block
# may be legitimate for other consumers like the web chat UI) — this strip
# lives at the WhatsApp channel boundary instead.
#
# Anchored on the two literal strings the emitter ALWAYS writes together
# (heading prefix + closing sentence, both from the SAME
# `_format_workflow_for_prompt` call) rather than a loose "workflow"
# keyword — see .claude/rules/cicatrix-superscar.md family #3
# (guard-over-match) for why a bare-substring match would be unsafe: a
# legitimate client answer ("il nostro workflow di onboarding...") must
# never be caught by this. The non-greedy DOTALL match between the two
# anchors also means only the block itself is removed, never content that
# happens to follow it (e.g. the KG fast-path's reasoning text, which is
# appended AFTER the workflow block in some code paths and must survive).
_KG_WORKFLOW_TRAILER = (
    "IMPORTANT: This is a suggested workflow. Always verify current requirements with the user."
)
_KG_WORKFLOW_SCAFFOLD_RE = re.compile(
    r"\s*##\s+SUGGESTED WORKFLOW \(from .*?" + re.escape(_KG_WORKFLOW_TRAILER),
    re.DOTALL,
)

# The 2026-08-11 KBLI baseline caught Gemini starting otherwise client-visible
# answers with the prompt's private XML section name (three of 25 probes).
# Do not try to recover a "final" paragraph from such a payload: the leaked
# block has no guaranteed delimiter and any guessed split could still expose
# chain-of-thought or unsupported claims.  At the WhatsApp boundary the safe
# behavior is to discard the entire payload and serve the normal localized
# source-honest refusal.  Anchor at the beginning so a legitimate discussion
# *about* an internal-monologue bug is not caught mid-answer.
_INTERNAL_MONOLOGUE_LEAK_RE = re.compile(
    r"^[^A-Za-z0-9]{0,32}internal[ _-]+monologue"
    r"(?:[ _-]+instructions)?(?:[^A-Za-z0-9]|$)",
    re.IGNORECASE,
)


# An abstain payload is worth sending when it actually contains an answer.
# Measured 2026-08-11 across 16 cold questions in 8 languages: 7 came back
# `abstain=true`, and 3 of those carried a complete on-topic answer. The old
# consumer discarded all 7.
#
# Deliberately NOT a quality judgement — this module cannot re-score evidence and
# must not try. It asks one thing: is there prose here, or only the residue of a
# refusal? The floor is length, because the refusal shapes the RAG emits are
# short ("Je suis prêt pour votre prochaine question." — 43 chars, measured) and
# a real answer to any question this bot receives is not.
_ABSTAIN_MIN_SENDABLE_CHARS = 200

# Mirrors whatsapp_service.WHATSAPP_BODY_LIMIT (WhatsApp Cloud API's
# message-body limit). Duplicated as a local constant rather than imported —
# this module's job ends at "the text to send"; the cut belongs to
# whatsapp_service.fit_to_whatsapp_limit, which as of 2026-08-11 cuts at a
# word boundary and marks it instead of severing mid-word. That placement is
# deliberate: a census showed send_message has ~14 non-test call sites of
# which only two chunk beforehand — curing this producer would have left the
# other eleven severing words. The warning below stays because this is the
# only place that knows the thread id and the pre-format length.
_WHATSAPP_HARD_SEND_LIMIT = 4096


class FinalizeOutcome(str, Enum):
    """What the pipeline decided about the payload."""

    SEND = "send"  # `text` is safe to hand to the channel sender
    DEFECT = "defect"  # nothing sendable — gemini: caller raises; codex: fail-off


class FinalizeProvider(str, Enum):
    """Which generation leg produced the payload.

    An Enum rather than a free string because a typo ("Codex", "codeX") on a
    free string would silently disarm every codex-only policy and run the
    payload down the Gemini branch — the PR-3 adversarial review reproduced
    exactly that. ``FinalizeProvider(value)`` raises ``ValueError`` on any
    unknown value, so a misconfigured caller fails loudly at the first call.
    """

    GEMINI = "gemini"
    CODEX = "codex"


@dataclass(frozen=True)
class FinalizeResult:
    outcome: FinalizeOutcome
    text: str = ""
    # Why a human was told, or None. On SEND outcomes the pipeline has
    # ATTEMPTED the notification via the caller's `tell_a_human` (delivery
    # semantics are the callback's own — wa_inbox_bot's helper never raises
    # and dedups per-thread; a callback that raises is contained and logged).
    human_reason: str | None = None
    # DEFECT only: machine token naming the defect class.
    defect_reason: str | None = None
    # DEFECT only: the exact message the Gemini caller raises (kept identical
    # to the pre-extraction RuntimeError strings so the worker ledger and any
    # log-driven tooling see an unchanged vocabulary).
    defect_message: str = ""


def _abstain_answer_worth_sending(data: dict[str, Any]) -> str:
    """The answer text inside an abstain payload, or "" if there is none worth sending.

    Returns the CLEANED, formatted text so the caller ships exactly what it
    inspected — an earlier shape that returned a bool and let the caller re-derive
    the text is how two code paths end up disagreeing about the same message.
    """
    # GROUNDING FIRST, length second. Added after a two-seat adversarial review
    # (Codex gpt-5.6-sol xhigh + Gemini 3.1 Pro, briefed to refute, reviewed
    # independently) returned the same verdict on the first version of this
    # function: gating on text length alone "measures fluency, not support" and
    # "can preferentially release the most confidently hallucinated answer" —
    # on immigration/tax advice, where a wrong capital requirement or overstay
    # rule carries real liability and a disclaimer does not neutralise it.
    #
    # They are right, and this module's OWN measurements say so too. Of the 7
    # abstains observed across 16 cold questions, the 5 carrying real answers
    # all had retrieved context (`context_length` 1-2); the 2 carrying junk had
    # `context_length == 0` — "Je suis prêt pour votre prochaine question." and
    # a Russian "I already provided the basic information". `context_length == 0`
    # with `evidence_score == 0.0` is the signature of the model writing from
    # parametric memory with nothing retrieved behind it. That is the one shape
    # that must never reach a client, and length cannot tell it apart.
    #
    # So this sends only the case the label gate exists FOR: evidence was
    # retrieved, and scored below the domain threshold. It never sends the case
    # where there was no evidence at all.
    try:
        context_length = int(data.get("context_length") or 0)
    except (TypeError, ValueError):
        context_length = 0
    try:
        evidence = float(data.get("evidence_score") or 0.0)
    except (TypeError, ValueError):
        evidence = 0.0
    if context_length <= 0 or evidence <= 0.0:
        return ""

    raw = (data.get("answer") or "").strip()
    if len(raw) < _ABSTAIN_MIN_SENDABLE_CHARS:
        return ""
    cleaned = _strip_kg_workflow_scaffold(raw)
    cleaned = format_rich_text(cleaned, "whatsapp")
    # Re-check AFTER cleaning: the scaffold strip and the channel formatter can
    # both shrink the text, and a payload that was only scaffold must not be
    # rescued by its own length before the scaffold was removed.
    if len(cleaned.strip()) < _ABSTAIN_MIN_SENDABLE_CHARS:
        return ""
    return cleaned.strip()


def _strip_kg_workflow_scaffold(answer: str) -> str:
    """Remove the internal KG-workflow diagnostics block, if present.

    Safe to call on any answer text — a no-op when the block is absent
    (the common case).
    """
    return _KG_WORKFLOW_SCAFFOLD_RE.sub("", answer).strip()


def _safe_abstain_reply(query: str) -> str:
    """Return the reasoning engine's localized, source-honest refusal.

    This is intentionally derived from the customer query, never from the
    endpoint's ``answer`` field: a low-evidence response can still contain
    fluent unsupported claims even when the endpoint correctly labels it
    ``abstain=true``.
    """
    language = detect_query_language(query)
    return get_localized_stub("abstain", language)


def _starts_with_internal_monologue_leak(answer: str) -> bool:
    """Return whether a model payload opens with a private prompt marker."""
    return bool(_INTERNAL_MONOLOGUE_LEAK_RE.match(answer))


# ── Codex-only egress vetoes ─────────────────────────────────────────────
#
# Both helpers are pure functions so they can be tested without the pipeline.

# Amounts ATTACHED to a currency marker — the entity this veto exists for is
# "a price the model asserts", and the price form in this bot's answers is
# currency-marked (Rp/IDR/USD/$), optionally with an Indonesian multiplier
# (jt/juta/rb/ribu/k/miliar/milyar/bn/triliun). Bare numbers are deliberately
# OUT of scope: regulatory figures like "2,5 miliar modal disetor" legitimately
# come from retrieved chunks without a currency prefix, and vetoing them would
# be a family-#3 over-match blocking correct answers.
#
# Three anti-scars, each a reproduced case from the PR-3 adversarial review:
# * an amount never crosses a newline and never absorbs a following bare
#   number ("Rp 3.500.000\n30 days" is 3500000, not 350000030) — horizontal
#   whitespace only around the amount, and NO whitespace inside it;
# * multipliers are canonicalized ("Rp 99 juta" == "Rp 99.000.000"), so an
#   invented price cannot pass on its spelling;
# * source numbers are extracted per TOKEN, never from a concatenation of the
#   whole source ("Rp 12.345" followed by "67 days" can never authorize an
#   invented "Rp 34.567").
#
# ENGLISH MAGNITUDE WORDS (added 2026-08-30): the Indonesian-only list below was
# not merely incomplete — it was a TOTAL VETO BYPASS in both directions, measured
# on origin/main before this change:
#   price_tokens_outside_sources("...IDR 2.5 billion.", [])          -> []
#   price_tokens_outside_sources("...IDR 999 billion.", [])          -> []   <- INVENTED
#   price_tokens_outside_sources("Rp 2.500.000.000", [<curated_qa>]) -> ["IDR:2500000000"]
# Mechanism: with "billion" unknown, the regex captures only the bare "2.5",
# _canonical_value returns 25, and 25 < _VETO_FLOORS["IDR"] discards it BEFORE the
# source-membership check ever runs. So an English-worded amount was never
# validated as grounded AND never caught as hallucinated — the 999-billion control
# proves that is the rule, not an accident of one value. Symmetrically, a source
# stating the right figure in English prose (the live curated_qa entry for PT PMA
# paid-up capital says "IDR 2.5 billion") could not be canonicalized either, so a
# CORRECT digit-grouped answer was rejected against evidence that actually
# supported it — the mechanism behind the finalize_pricing_outside_package
# rejections measured on the live bot 2026-08-30.
#
# The pattern is DERIVED from the dict below, longest-alternative-first, so the two
# can never drift apart. That coupling was live-ammunition: _canonical_value does
# _AMOUNT_MULTIPLIERS[multiplier.lower()] with no .get(), so a token the pattern
# matches and the dict lacks is a KeyError inside the finalize path, not a miss.
# test_wa_finalize_price_veto.py asserts the derivation holds.
#
# NOT widened here, deliberately, and named so it is not mistaken for coverage: a
# bare currency WORD ("2,5 miliar rupiah", with no Rp/IDR/USD marker) is still
# invisible to this veto. Adding "rupiah" as a currency marker only ever ADDS
# rejections, and the live bot is already over-rejecting (4 of 5 battery questions
# blocked on 2026-08-30); widening the marker vocabulary is a separate change that
# needs its own false-positive measurement, not a rider on this one.
_AMOUNT_MULTIPLIERS: dict[str, float] = {
    "k": 1e3,
    "rb": 1e3,
    "ribu": 1e3,
    "thousand": 1e3,
    "thousands": 1e3,
    "jt": 1e6,
    "juta": 1e6,
    "mn": 1e6,
    "million": 1e6,
    "millions": 1e6,
    "miliar": 1e9,
    "milyar": 1e9,
    "bn": 1e9,
    "billion": 1e9,
    "billions": 1e9,
    "triliun": 1e12,
    "trillion": 1e12,
    "trillions": 1e12,
}
# Longest first so a longer token is never pre-empted by a prefix of itself
# ("juta" by "jt" is safe only by luck of ordering; "millions" by "million" is not).
_MULT_ALTERNATION = "|".join(
    sorted((re.escape(k) for k in _AMOUNT_MULTIPLIERS), key=len, reverse=True)
)
_MULT_PATTERN = f"(?:{_MULT_ALTERNATION})"

# Currency MARKERS, marker -> family. Until 2026-08-30 this vocabulary lived
# inline in the regex as `Rp|IDR|USD|$` and everything that was not `$`/`USD`
# was folded into the IDR family. That was a second, SIMPLER bypass of this
# veto than the English-multiplier one fixed in #5293 — it needed no magnitude
# word at all. Measured on the parent commit, literal return values:
#   price_tokens_outside_sources("Costa EUR 5000 in totale.", []) -> []
#   price_tokens_outside_sources("The fee is SGD 8000.", [])      -> []
#   price_tokens_outside_sources("The fee is AUD 8000.", [])      -> []
# An invented foreign-currency price was never validated as grounded and never
# caught as hallucinated, exactly as an English-worded one was not.
#
# Why the marker list alone would NOT have fixed it: with every family folded
# into IDR, "EUR 500" canonicalized to IDR:500 and fell under the IDR floor of
# 1000 — so adding the marker without a per-family floor changes nothing. The
# family map and the floor table are one change, not two.
#
# Measured false-positive surface before widening (the reason the parent PR
# deferred this axis, re-examined rather than assumed): in
# apps/backend-rag/backend/kb/ the markers EUR, SGD, GBP and the euro sign do
# not occur at all; across the whole app, word-bounded, EUR appears 19 times in
# 14 files, AUD 3, GBP 2, SGD 1 — nearly all in tests and scripts, not in
# retrievable content. So this widening closes a hole at almost no cost in new
# rejections. It DOES newly veto a currency conversion the model computes
# itself ("about EUR 600"), which is intended: an unsourced computed figure is
# precisely what this veto exists to stop, and doctrine already forbids
# improvising a price.
#
# WORD BOUNDARIES ARE LOAD-BEARING HERE, and this is not theoretical: the first
# measurement of AUD's footprint returned "135 files" because it was counting
# the substring inside FRAUD and AUDIT. A marker without \b would read an
# amount out of the middle of an unrelated word — cicatrix family #3, committed
# by the probe that was measuring for this very change. The alternation below
# is derived from this table and every alphabetic marker is \b-anchored.
_CURRENCY_MARKERS: dict[str, str] = {
    "RP": "IDR",
    "IDR": "IDR",
    "USD": "USD",
    "$": "USD",
    "EUR": "EUR",
    "EURO": "EUR",
    "€": "EUR",
    "GBP": "GBP",
    "£": "GBP",
    "SGD": "SGD",
    "AUD": "AUD",
}
_SYMBOL_MARKERS = frozenset({"$", "€", "£"})


def _marker_alternation() -> str:
    """Regex alternation over _CURRENCY_MARKERS, longest first, \b-anchored.

    Alphabetic markers get a LEADING \b so "AUD" cannot match inside "FRAUD";
    symbols get none (\b before "$" would require a preceding word char). No
    trailing \b is needed: both branches of _CURRENCY_AMOUNT_RE require digits
    adjacent to the marker, which already excludes "EURO" matching "EUROPE".
    """
    parts = []
    for marker in sorted(_CURRENCY_MARKERS, key=len, reverse=True):
        escaped = re.escape(marker)
        # "Rp." is written with a trailing dot as often as without.
        if marker == "RP":
            escaped += r"\.?"
        parts.append(escaped if marker in _SYMBOL_MARKERS else r"\b" + escaped)
    return "|".join(parts)


_MARKER_PATTERN = _marker_alternation()
_CURRENCY_AMOUNT_RE = re.compile(
    r"(?:(?P<cur1>" + _MARKER_PATTERN + r")[ \t]*(?P<amt1>\d(?:[\d.,]*\d)?)"
    r"(?:[ \t]*(?P<mul1>" + _MULT_PATTERN + r")\b)?)"
    r"|(?:(?P<amt2>\d(?:[\d.,]*\d)?)(?:[ \t]*(?P<mul2>" + _MULT_PATTERN + r")\b)?"
    r"[ \t]*(?P<cur2>" + _MARKER_PATTERN + r"))",
    re.IGNORECASE,
)

# Veto floors per currency family: IDR prices below Rp 1.000 do not exist in
# this business (and tiny amounts would fire on noise); hard-currency prices
# are real from 10 up (the review's "$999" case must be vetoable). EVERY family
# in _CURRENCY_MARKERS must have an entry — _floor_for asserts it rather than
# defaulting, because a missing floor would silently wave a whole currency
# through, which is the failure this table exists to prevent.
_VETO_FLOORS: dict[str, int] = {
    "IDR": 1000,
    "USD": 10,
    "EUR": 10,
    "GBP": 10,
    "SGD": 10,
    "AUD": 10,
}


def _canonical_currency(cur: str) -> str:
    """Currency FAMILY for a matched marker.

    The regex only ever matches markers derived from _CURRENCY_MARKERS, so the
    lookup cannot miss; the explicit fallback is a fail-CLOSED default rather
    than a KeyError, because folding an unknown marker into IDR keeps it inside
    the veto (with the strictest floor) instead of dropping it on the floor.
    """
    c = cur.strip().rstrip(".").upper()
    return _CURRENCY_MARKERS.get(c, "IDR")


def _canonical_value(amount: str, multiplier: str | None) -> int | None:
    """Integer value of an amount string, multiplier applied. None if unparseable."""
    s = amount.strip()
    if not s:
        return None
    if multiplier:
        # A decimal form is allowed before a multiplier ("3,5 juta"); a grouped
        # form ("3.500 juta") canonicalizes by stripping separators.
        normalized = s.replace(",", ".")
        try:
            if normalized.count(".") == 1 and len(normalized.split(".")[1]) <= 2:
                base = float(normalized)
            else:
                base = float(re.sub(r"[.,]", "", s))
        except ValueError:
            return None
        return int(round(base * _AMOUNT_MULTIPLIERS[multiplier.lower()]))
    digits = re.sub(r"[.,]", "", s)
    if not digits.isdigit():
        return None
    return int(digits)


def _currency_amounts(text: str) -> list[tuple[str, int]]:
    """(currency_family, canonical_value) for every currency-marked amount in text."""
    out: list[tuple[str, int]] = []
    for m in _CURRENCY_AMOUNT_RE.finditer(text):
        cur = m.group("cur1") or m.group("cur2") or ""
        amt = m.group("amt1") or m.group("amt2") or ""
        mul = m.group("mul1") or m.group("mul2")
        value = _canonical_value(amt, mul)
        if value is not None:
            out.append((_canonical_currency(cur), value))
    return out


def price_tokens_outside_sources(text: str, price_sources: Sequence[str]) -> list[str]:
    """Canonical amounts in ``text`` that no source contains, as "CUR:value" strings.

    ``price_sources`` should be the serialized PricingTool block of the frozen
    package plus the retrieved chunk texts — an amount is legitimate if ANY of
    them contains the same canonical VALUE ("Rp 3,5 juta" in the answer matches
    "Rp 3.500.000" or a bare "3500000" in a source). Chunks are included on
    purpose: answers legitimately quote currency-marked regulatory fees that
    come from retrieval, not from PricingTool, and excluding them would fail
    off every such answer. Declared residual (review MAJOR-7): a figure present
    in a chunk could semantically launder a wrong "service fee" — accepted
    because the Gemini leg has the identical exposure today with NO veto at
    all, and the label gate + PricingTool grounding remain the primary control.

    Second declared residual, made visible by the 2026-08-30 currency-family
    change and deliberately NOT closed here: membership is tested on the VALUE
    alone, not on (family, value), so a "USD 5000" in a source authorizes an
    "EUR 5000" in the answer. Closing it would require dropping the bare-token
    pass below — the one that lets a pricing block state an amount without
    repeating its currency marker — and that pass is what keeps this veto from
    failing off correct answers. Trading a certain false-positive regression
    for a speculative laundering path is the wrong side of the exchange for a
    guard that already over-rejects. Pinned by
    test_pricing_veto_does_not_distinguish_currency_families so it cannot rot
    into an unexamined assumption.
    """
    source_values: set[int] = set()
    for src in price_sources:
        for _cur, value in _currency_amounts(src):
            source_values.add(value)
        # Discrete numeric tokens too (a pricing block may write the amount
        # without repeating the currency marker beside it) — each token
        # canonicalized ALONE, never concatenated with its neighbors.
        for token in re.findall(r"\d(?:[\d.,]*\d)?", src):
            value = _canonical_value(token, None)
            if value is not None:
                source_values.add(value)
    offenders: list[str] = []
    for cur, value in _currency_amounts(text):
        if value < _VETO_FLOORS[cur]:
            continue
        if value not in source_values:
            offenders.append(f"{cur}:{value}")
    return offenders


# ---------------------------------------------------------------------------
# THE SPLIT-PRICE VETO (added 2026-08-30)
#
# THE DEFECT, measured on the live bot, not argued: cycle 357 case q1 (outbox
# row 379, 2026-08-30T17:54Z, route=codex, done at attempt 1) answered an
# Investor-KITAS price question with
#
#   "biaya layanan kami: offshore Rp17.000.000, onshore Rp19.000.000 [...]
#    PNBP pemerintah Rp9.500.000 untuk 2 tahun"
#
# — a government levy presented to a CLIENT as a separate payable item beside
# the Bali Zero price. Zero's ruling of 2026-07-17 is one all-inclusive
# client-facing price, never a PNBP-vs-fee split, and the PricingTool rows say
# so in their own notes ("All-inclusive price - the government fee is included;
# nothing further is payable on arrival"). A client reading row 379 would
# reasonably budget Rp9.500.000 that is already inside the Rp17.000.000.
#
# WHY THE EXISTING PRICING VETO CANNOT SEE IT: `price_tokens_outside_sources`
# asks whether every amount is PRESENT in the frozen package's sources. It
# proves CONSISTENCY, never COMPLIANCE. Measured the same day: the pricing
# block returned for that exact question contains no "PNBP" and no
# "pemerintah" at all, yet the answer passed the veto — so the figure was
# laundered in from a retrieved chunk, which the veto accepts by design (see
# the "declared residual" in that function's docstring). Two different
# questions, two different guards.
#
# THE SHAPE, and why it is not a bare substring scan (cicatrix family #3): the
# forbidden thing is a government-fee marker carrying its OWN amount in the
# same sentence. A sentence that says the government fee is INCLUDED is the
# behaviour we want and must survive untouched - it is the literal text of the
# PricingTool notes. So: fire on (marker AND currency amount) within one
# sentence, UNLESS that sentence also carries an inclusion marker. "mencakup"
# / "covers" is deliberately NOT an inclusion marker: in row 379 it said the
# PNBP covers visa+ITAS, which is a statement about what the levy buys, not
# about it being inside our price.
# Levy vocabulary. Widened after the cross-family refuter (codex gpt-5.6-sol,
# xhigh, dispatched on the diff WITHOUT the brief) returned BLOCK with 15
# findings, 14 of which reproduced verbatim against this function; the one that
# did NOT is pinned in the innocence tests so it is not "fixed" again. The
# first cut knew only four spellings, so `Penerimaan Negara Bukan Pajak`
# (PNBP's own official expansion), `biaya imigrasi`, `tarif resmi` and
# `official fee` — all natural ways to bill a client for a levy — walked past
# it. Several markers deliberately share ONE name: the stored reason code is
# the single value `finalize_price_split_fee` either way, and a name here only
# ever reaches a log line.
_PRICE_SPLIT_MARKERS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("pnbp", re.compile(r"(?i)\bPNBP\b")),
    ("pnbp", re.compile(r"(?i)\bPenerimaan\s+Negara\s+Bukan\s+Pajak\b")),
    (
        "government_fee",
        re.compile(r"(?i)\bgovernment(?:al)?\s+(?:fee|charge|levy|tax)s?\b"),
    ),
    (
        "government_fee",
        re.compile(r"(?i)\b(?:official|statutory)\s+(?:fee|charge)s?\b"),
    ),
    ("biaya_pemerintah", re.compile(r"(?i)\bbiaya\s+(?:pemerintah|negara)\b")),
    (
        "biaya_imigrasi",
        re.compile(
            r"(?i)\b(?:biaya\s+(?:imigrasi|keimigrasian)|immigration\s+fees?)\b"
        ),
    ),
    ("tarif_resmi", re.compile(r"(?i)\b(?:tarif|biaya)\s+resmi\b")),
    ("state_fee", re.compile(r"(?i)\bstate\s+(?:fee|levy)s?\b")),
)

# SEPARATION beats INCLUSION, and that ordering is the heart of this guard.
#
# The first cut exempted a whole sentence the moment it contained any inclusion
# wording, and the refuter broke it four different ways with that one lever:
# `tidak termasuk dalam` (a NEGATED inclusion) read as an inclusion; `not
# all-inclusive` likewise; and an inclusion phrase about something ELSE
# ("sudah termasuk konsultasi, tetapi PNBP ... dibayar terpisah") exempted a
# levy it never referred to. Binding an exemption to its grammatical subject
# with a regex is a clause-parsing problem and would have been the wrong shape.
#
# The cure inverts the burden instead: an explicit statement that the levy is
# paid SEPARATELY is decisive evidence of a split and is checked FIRST, so a
# text carrying both signals fires. The negated inclusion forms are listed HERE
# rather than derived by a generic negation window, because a generic one would
# misread the inclusion phrase `tidak ada biaya tambahan` ("no additional
# charges") — which opens with a negator and MEANS inclusion.
_PRICE_SEPARATION_MARKERS = re.compile(
    r"(?i)\b(?:di ?bayar\s+terpisah|bayar\s+terpisah|terpisah"
    r"|(?:payable|paid|charged|billed)\s+separately|separately"
    r"|tidak\s+termasuk|belum\s+termasuk|not\s+included|not\s+all[\s-]?inclusive"
    r"|di\s+luar\s+(?:harga|biaya)|on\s+top\s+of|excluded\s+from)\b"
)

# An inclusion marker EXEMPTS the levy: it asserts the levy sits INSIDE the
# quoted price. Only consulted when no separation marker fired.
_PRICE_INCLUSION_MARKERS = re.compile(
    r"(?i)\b(?:sudah\s+(?:termasuk|include)|telah\s+termasuk|termasuk\s+dalam"
    r"|already\s+included|is\s+included|are\s+included|included\s+in"
    r"|all[\s-]?inclusive|all[\s-]?in\b|nothing\s+further\s+is\s+payable"
    r"|tidak\s+ada\s+biaya\s+tambahan|tidak\s+perlu|no\s+additional"
    r"|total\s+yang\s+anda\s+bayar|total\s+you\s+pay"
    r"|(?:this|that|it|which)\s+includes?|includes?\s+(?:our|the|your)"
    # BARE `mencakup` WAS HERE AND WAS WRONG — it exempted the very defect
    # this guard exists for. Row 379 reads "PNBP pemerintah Rp9.500.000 untuk
    # 2 tahun, mencakup visa, ITAS, izin masuk kembali" — there `mencakup`
    # says what the LEVY BUYS, not that the levy sits inside the client
    # price. Only the bound form `sudah mencakup` ("already comprises")
    # makes the inclusion claim. Caught by
    # test_price_split_veto_catches_the_reproduced_client_defect going red.
    r"|sudah\s+mencakup)\b"
)

# Association is by PROXIMITY, not by sentence, and that is a deliberate
# reversal. Sentence segmentation was the single largest source of defects in
# the first cut: an Indonesian abbreviation (`PP No. 28`) split a marker away
# from its amount, a full-width `。` failed to split at all and let one
# sentence's inclusion wording exempt another sentence's split levy, and a
# WhatsApp bullet with the label and the amount on separate LINES was severed
# by the newline rule. All five of those findings are ONE defect — the
# segmenter — so the segmenter is gone rather than patched. Cost, declared
# rather than hidden: a marker mentioned definitionally within 140 characters
# of an unrelated total now fires where a sentence-scoped rule would not. That
# costs a retry (the ladder rephrases); the reverse error costs a client
# budgeting a levy twice.
_PRICE_SPLIT_WINDOW = 140

# WhatsApp text copied from a price list routinely carries U+00A0 between the
# currency marker and the digits, and `_CURRENCY_AMOUNT_RE` accepts only ASCII
# blanks — so "Rp 9.500.000" was invisible to this veto. Normalized HERE, on
# this function's own input only: widening the shared regex would change the
# OTHER veto's behaviour too, and that belongs in its own change.
_NBSP = "\xa0"


def price_split_offenders(text: str) -> list[str]:
    """Names of levy markers that carry their own amount, uncontradicted.

    Returns marker NAMES only, never the matched text or the amount — this
    value is logged, and the DB stores the single code
    `finalize_price_split_fee` regardless (same discipline as
    `scan_text_for_secret_egress`).
    """
    haystack = text.replace(_NBSP, " ")
    offenders: list[str] = []
    for name, pattern in _PRICE_SPLIT_MARKERS:
        if name in offenders:
            continue
        for match in pattern.finditer(haystack):
            lo = max(0, match.start() - _PRICE_SPLIT_WINDOW)
            hi = min(len(haystack), match.end() + _PRICE_SPLIT_WINDOW)
            window = haystack[lo:hi]
            if not _CURRENCY_AMOUNT_RE.search(window):
                continue
            if not _PRICE_SEPARATION_MARKERS.search(
                window
            ) and _PRICE_INCLUSION_MARKERS.search(window):
                continue
            offenders.append(name)
            break
    return offenders


_SECRET_EGRESS_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private_key_block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("ssh_pubkey", re.compile(r"\bssh-(?:rsa|ed25519|dss)\s+[A-Za-z0-9+/=]{20,}")),
    ("openai_style_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    (
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    ),
    (
        # Covers both config-style (`api_key = xxxx`) and JSON auth-file
        # fragments (`"refresh_token":"1//xxxx"`) — the closing quote of a
        # JSON key sits between the name and the colon, and the value charset
        # includes `/` and `+` (OAuth refresh tokens carry both). The review
        # reproduced both misses against the first version of this pattern.
        "token_assignment",
        re.compile(
            r"(?i)[\"']?\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token"
            r"|client[_-]?secret|id[_-]?token|authorization)\b[\"']?\s*[:=]\s*"
            r"[\"']?[A-Za-z0-9_./+\-]{16,}"
        ),
    ),
    (
        # Any "Bearer <opaque>" / "Basic <opaque>" value, with or without an
        # Authorization: prefix (the space after the scheme word means
        # token_assignment above cannot reach the real token — this shape
        # owns it). Prose innocence: "the bearer of the visa" has
        # no 16-char opaque token after it, and the digit lookahead keeps a
        # long hyphenated English word ("Bearer responsibility-holder") from
        # firing — real opaque tokens carry digits.
        "bearer_token",
        re.compile(r"(?i)\b(?:bearer|basic)\s+(?=[A-Za-z0-9_./+\-=]*\d)[A-Za-z0-9_./+\-=]{16,}"),
    ),
)


def scan_text_for_secret_egress(
    text: str, canary_tokens: Sequence[str] = ()
) -> str | None:
    """Name of the first secret-egress pattern found in ``text``, or None.

    Returns the pattern NAME only — never the matched content, so a hit can be
    logged and ledgered without transcribing the secret it caught (CLAUDE.md
    §14 output boundary). Canary tokens are exact substrings supplied by the
    caller (the broker daemon plants them in the sandbox home; one appearing
    in outbound text means the executor read files it should not have).
    """
    for name, pattern in _SECRET_EGRESS_PATTERNS:
        if pattern.search(text):
            return name
    for token in canary_tokens:
        if token and token in text:
            return "canary_token"
    return None


def _codex_egress_veto(
    text: str,
    *,
    price_sources: Sequence[str] | None,
    secret_scan: bool,
    canary_tokens: Sequence[str],
    thread_id: Any,
) -> tuple[str, str] | None:
    """(defect_reason, defect_message) if codex-leg text must not leave, else None."""
    if price_sources is not None:
        offenders = price_tokens_outside_sources(text, price_sources)
        if offenders:
            logger.warning(
                "wa-finalize: pricing veto for thread %s — %d currency-marked "
                "amount(s) not present in the frozen package's price sources",
                thread_id,
                len(offenders),
            )
            return (
                "pricing_outside_package",
                f"wa-finalize: answer for thread {thread_id} asserts prices "
                "outside the frozen package",
            )
    # Runs unconditionally, NOT under `price_sources is not None`: splitting a
    # government levy out of a client-facing price is forbidden by the ruling
    # whether or not this leg was handed price sources to anchor against.
    split = price_split_offenders(text)
    if split:
        logger.warning(
            "wa-finalize: split-price veto for thread %s — %s presented as a "
            "separately payable amount beside a client price",
            thread_id,
            ",".join(split),
        )
        return (
            "price_split_fee",
            f"wa-finalize: answer for thread {thread_id} splits a government "
            "levy out of the client-facing price",
        )
    if secret_scan:
        hit = scan_text_for_secret_egress(text, canary_tokens)
        if hit is not None:
            # Pattern name only — never the matched content (see scanner docstring).
            logger.error(
                "wa-finalize: secret-egress scan hit (%s) for thread %s — "
                "discarding codex output",
                hit,
                thread_id,
            )
            return (
                f"secret_egress:{hit}",
                f"wa-finalize: secret-egress scan hit for thread {thread_id}",
            )
    return None


async def finalize_wa_answer(
    *,
    data: dict[str, Any],
    query: str,
    thread_id: Any,
    tell_a_human: Callable[[str], Awaitable[Any]],
    provider: str | FinalizeProvider = FinalizeProvider.GEMINI,
    price_sources: Sequence[str] | None = None,
    secret_scan: bool = False,
    canary_tokens: Sequence[str] = (),
) -> FinalizeResult:
    """Run the shared post-generation sequence on a generation payload.

    Args:
        data: the generation payload — the agentic-RAG response body on the
            Gemini leg; on the codex leg the worker builds the same shape from
            the frozen evidence (``answer``, ``abstain``, ``abstain_reason``,
            ``context_length``, ``evidence_score``).
        query: the customer query (drives stub localization only).
        thread_id: for log lines — this function never touches the DB.
        tell_a_human: REQUIRED one-argument async callable ``(reason)``. The
            pipeline calls it exactly where the pre-extraction code called
            ``_tell_a_human`` — stub paths on both providers, defect paths on
            the Gemini provider only (a codex defect falls off into the
            WORKER's retry ladder instead — see the module docstring's
            2026-08-27 correction — so the client still owes an answer from a
            LATER attempt, not from Gemini re-entering here).
            Required rather than defaulted (review MAJOR-9): an optional
            notifier makes "forgot to wire it" indistinguishable from "chose
            silence", which is the exact contract inversion the 2026-08-12
            scar in the /bot corner records. A callback that raises is
            contained here — a notifier failure must never corrupt the
            outcome.
        provider: ``FinalizeProvider`` (or its string value). An unknown
            string raises ``ValueError`` — a typo must never silently disarm
            the codex policies.
        price_sources / secret_scan / canary_tokens: codex egress vetoes. On
            the codex provider ``price_sources`` and ``secret_scan=True`` are
            MANDATORY (``ValueError`` otherwise): the protections are part of
            the route, not options (review BLOCKER-2 — fail-closed, never
            fail-open).
    """
    provider = FinalizeProvider(provider)
    if provider is FinalizeProvider.CODEX and (price_sources is None or not secret_scan):
        raise ValueError(
            "wa-finalize: provider='codex' requires price_sources and "
            "secret_scan=True — refusing a fail-open configuration"
        )

    async def _tell(reason: str) -> None:
        try:
            await tell_a_human(reason)
        # Containment, not delegation: wa_inbox_bot's helper already never
        # raises, but this pipeline must not depend on every future caller
        # honoring that — a notifier failure must never replace or corrupt
        # the outcome being returned.
        except Exception as exc:
            logger.error(
                "wa-finalize: tell_a_human(%s) raised for thread %s: %s",
                reason,
                thread_id,
                exc,
            )

    # Why a human needs to look at this thread, or None. Set at most once —
    # every later site guards on `is None`, so the FIRST (most specific) cause
    # is the one reported rather than whichever check happens to run last.
    human_reason: str | None = None

    if data.get("abstain"):
        # Zero's ruling (2026-08-11), on measurement: an abstain does NOT mean
        # "no content". Probed live across 16 cold questions in 8 languages,
        # SEVEN came back flagged `abstain=true` and three of those carried a
        # complete, on-topic answer — the two German ones and an Indonesian one
        # opened straight into the real PT PMA steps. Sending the stub instead
        # would throw away a written answer and hand the client a refusal.
        #
        # This does NOT touch the abstain gates. Their generation-vs-label
        # divergence is panel-ruled and tripwire-tested (CLAUDE.md §9) — the
        # label gate MARKS confidence, it does not decide whether advice may
        # exist. Reading the label as "discard the text" was this consumer's
        # error, not the gate's. `_abstain_answer_worth_sending` re-checks
        # grounding itself (context_length/evidence_score), so this can never
        # rescue the ungrounded-but-fluent case a length check alone would miss.
        #
        # A substantive answer is sent WITHOUT going through `human_reason`
        # below — the client got a real, on-topic answer, so nothing here is a
        # refusal that needs a human's eyes.
        #
        # POLICY branch (spec §2.3): the verdict derives from the frozen
        # evidence and would be identical whichever provider wrote the text,
        # so it deliberately behaves the same on both legs.
        substantive = _abstain_answer_worth_sending(data)

        # Structural text checks the early return used to SKIP (review
        # BLOCKER-1, reproduced): a grounded abstain payload is still MODEL
        # TEXT, and the label changes the confidence, not the text-safety
        # obligations — a monologue leak or an [ESCALATE] marker inside it
        # gets the same treatment as on the non-abstain path.
        escalate_in_substantive = False
        if substantive and _starts_with_internal_monologue_leak(substantive):
            if provider is FinalizeProvider.CODEX:
                return FinalizeResult(
                    outcome=FinalizeOutcome.DEFECT,
                    defect_reason="internal_monologue_leak",
                    defect_message=(
                        f"wa-finalize: internal-monologue leak in codex output, "
                        f"thread {thread_id}"
                    ),
                )
            logger.warning(
                "wa-inbox bot: internal-monologue marker inside grounded abstain "
                "answer for thread %s; discarding payload and serving safe abstention",
                thread_id,
            )
            human_reason = "internal_monologue_leak"
            substantive = ""
        if substantive and "[ESCALATE]" in substantive:
            # POLICY marker (spec §2.3): identical handling on both providers.
            escalate_in_substantive = True
            substantive = substantive.replace("[ESCALATE]", "").strip()
            if len(substantive) < _ABSTAIN_MIN_SENDABLE_CHARS:
                # The marker was load-bearing bulk — nothing substantive left.
                if human_reason is None:
                    human_reason = "persona_escalate_marker"
                substantive = ""

        if substantive:
            if provider is FinalizeProvider.CODEX:
                veto = _codex_egress_veto(
                    substantive,
                    price_sources=price_sources,
                    secret_scan=secret_scan,
                    canary_tokens=canary_tokens,
                    thread_id=thread_id,
                )
                if veto is not None:
                    return FinalizeResult(
                        outcome=FinalizeOutcome.DEFECT,
                        defect_reason=veto[0],
                        defect_message=veto[1],
                    )
            language = detect_query_language(query)
            logger.info(
                "wa-inbox bot: abstain on thread %s carried %d chars of answer — "
                "sending it with the caution note rather than the stub",
                thread_id,
                len(substantive),
            )
            reason = "persona_escalate_marker" if escalate_in_substantive else None
            if reason is not None:
                await _tell(reason)
            return FinalizeResult(
                outcome=FinalizeOutcome.SEND,
                text=substantive + get_localized_stub("low_confidence_note", language),
                human_reason=reason,
            )

        # Never surface the endpoint's raw answer on this branch. The baseline
        # caught an abstain-labelled payload that still asserted Rp 10bn.
        #
        # RAG refused. Until 2026-08-11 this raised, the worker burned five
        # retries and the client got SILENCE — while the answer being discarded
        # was, on the measured cases, the persona telling the client that the
        # team had been notified and would reply within one business hour. That
        # promise is taught by the prompt's ESCALATION section, and nothing on
        # this path performed it: the message was a promise nobody kept, thrown
        # away before anyone could read it.
        #
        # Zero's ruling (2026-08-10): "rifiuto + avviso a un umano". So: send
        # the localized refusal, and actually tell a human — via the single
        # `human_reason` choke point below, shared with the other causes.
        logger.info(
            "wa-inbox bot: serving localized safe abstention for thread %s (reason=%r)",
            thread_id,
            data.get("abstain_reason"),
        )
        answer = _safe_abstain_reply(query)
        # First cause wins (same rule as every other site): a leak or marker
        # found inside the discarded substantive text is the more specific
        # reason than the generic abstain label.
        if human_reason is None:
            human_reason = "rag_abstain"
    else:
        answer = (data.get("answer") or "").strip()
        if not answer:
            # Measured deterministic, not transient: the 2026-08-10 battery got
            # a 0-character answer 5 times out of 5 on the same question, so the
            # retry ladder below cannot rescue this — it only spends attempts
            # and ends in silence. Tell a human BEFORE the raise, because the
            # raise is precisely what makes this silent. (Gemini leg only: a
            # codex defect falls off into the worker's OWN retry ladder
            # instead — see the module docstring's 2026-08-27 correction.)
            if provider is FinalizeProvider.GEMINI:
                await _tell("empty_rag_answer")
            return FinalizeResult(
                outcome=FinalizeOutcome.DEFECT,
                defect_reason="empty_rag_answer",
                defect_message=f"wa-inbox bot: empty RAG answer for thread {thread_id}",
            )

        if _starts_with_internal_monologue_leak(answer):
            if provider is FinalizeProvider.CODEX:
                # TEXT_DEFECT (spec §2.3): fail off into the worker's
                # retry ladder instead of serving the stub the Gemini
                # branch below would serve — a LATER codex-leg attempt can
                # legitimately cure a defective text (no second generator
                # to hand this off to since the 2026-08-27 Gemini cut).
                return FinalizeResult(
                    outcome=FinalizeOutcome.DEFECT,
                    defect_reason="internal_monologue_leak",
                    defect_message=(
                        f"wa-finalize: internal-monologue leak in codex output, "
                        f"thread {thread_id}"
                    ),
                )
            logger.warning(
                "wa-inbox bot: internal-monologue marker at start of RAG output "
                "for thread %s; discarding payload and serving safe abstention",
                thread_id,
            )
            answer = _safe_abstain_reply(query)
            if human_reason is None:
                human_reason = "internal_monologue_leak"

        # Strip an [ESCALATE] marker if the persona emitted one (mirror whatsapp_chat.py).
        #
        # INERT TODAY, ON PURPOSE — say it plainly rather than let a reader assume
        # coverage. **No prompt in this backend asks the model to emit the token**
        # (grepped 2026-08-11: the only occurrences are the places that look for
        # it), and a live probe saw it 0/14. So this branch cannot fire yet. It is
        # here because the alternative — a second escalation path invented later —
        # is how this file and whatsapp_chat.py drifted apart in the first place.
        #
        # It exists for the case `abstain` provably cannot catch: a message that
        # asks a real question AND asks for a person retrieves an answer, does not
        # abstain, and reaches nobody (measured 2026-08-11: 2 of 4 such messages did
        # not abstain, and all 4 promised the client a callback).
        #
        # ARMING IT IS A SEPARATE CHANGE, and NOT just a prompt line: the prompt is
        # shared by every consumer, and `blog_ask.py` / `agentic_rag.py` /
        # `channels/web` return the answer with NO strip at all (0 occurrences of
        # the token in any of them). Teaching the model to emit it without first
        # moving the strip somewhere central would print an internal token to blog
        # readers. Tracked in PENDING-ARMS.
        if "[ESCALATE]" in answer and human_reason is None:
            human_reason = "persona_escalate_marker"
        answer = answer.replace("[ESCALATE]", "").strip()
        if not answer:
            # `human_reason` is already "persona_escalate_marker" whenever the
            # marker was the whole payload — report THAT (first cause wins,
            # same rule as every other site), never the generic emptiness.
            reason = human_reason or "empty_after_escalate_strip"
            if provider is FinalizeProvider.GEMINI:
                await _tell(reason)
            return FinalizeResult(
                outcome=FinalizeOutcome.DEFECT,
                defect_reason=reason,
                defect_message=(
                    f"wa-inbox bot: answer empty after ESCALATE strip, thread {thread_id}"
                ),
            )

        # Remove internal KG-workflow diagnostics before the answer ever reaches
        # the channel formatter — see _strip_kg_workflow_scaffold docstring.
        answer = _strip_kg_workflow_scaffold(answer)
        if not answer:
            if provider is FinalizeProvider.CODEX:
                # TEXT_DEFECT: scaffold-only output is a broken text — fail
                # off into the worker's retry ladder so a LATER codex-leg
                # attempt can produce a real answer.
                return FinalizeResult(
                    outcome=FinalizeOutcome.DEFECT,
                    defect_reason="workflow_only_output",
                    defect_message=(
                        f"wa-finalize: workflow-only codex output, thread {thread_id}"
                    ),
                )
            logger.info(
                "wa-inbox bot: workflow-only RAG output for thread %s; "
                "serving localized safe abstention",
                thread_id,
            )
            if human_reason is None:
                human_reason = "workflow_only_output"
            answer = _safe_abstain_reply(query)

    # Codex-only egress vetoes on the candidate text. Skipped when the text is
    # the static localized stub (human_reason == "rag_abstain" is the only way
    # a stub reaches this point on the codex leg — every text-defect stub path
    # above already returned DEFECT for codex): a fixed stub carries no prices
    # and no secrets, and vetoing it would turn a POLICY refusal into a
    # spurious fail-off loop.
    if provider is FinalizeProvider.CODEX and human_reason != "rag_abstain":
        veto = _codex_egress_veto(
            answer,
            price_sources=price_sources,
            secret_scan=secret_scan,
            canary_tokens=canary_tokens,
            thread_id=thread_id,
        )
        if veto is not None:
            return FinalizeResult(
                outcome=FinalizeOutcome.DEFECT,
                defect_reason=veto[0],
                defect_message=veto[1],
            )

    # Channel boundary: convert the orchestrator's generic markdown into
    # WhatsApp-safe formatting (*bold*, unicode bullets, no raw ##/**/[N]
    # noise) — see backend/channels/format.py::format_rich_text. Length is
    # tracked pre- AND post-format (not enforced — see
    # _WHATSAPP_HARD_SEND_LIMIT docstring for why 150-word ChannelConfig
    # guidance is the wrong unit for this) so the eventual chunked-sending
    # lane inherits a real length distribution instead of a guess.
    pre_format_len = len(answer)
    answer = format_rich_text(answer, "whatsapp")
    if not answer:
        reason = human_reason or "empty_after_channel_format"
        if provider is FinalizeProvider.GEMINI:
            await _tell(reason)
        return FinalizeResult(
            outcome=FinalizeOutcome.DEFECT,
            defect_reason=reason,
            defect_message=(
                f"wa-inbox bot: answer empty after channel formatting, thread {thread_id}"
            ),
        )
    post_format_len = len(answer)

    if provider is FinalizeProvider.CODEX and post_format_len > _WHATSAPP_HARD_SEND_LIMIT:
        # TEXT_DEFECT (spec §2.3 "malformed/oversized output"): on the codex
        # leg an oversized answer falls off into the worker's retry ladder
        # instead of being cut mid-content by the sender's hard limit — a
        # truncated answer can lose its disclaimer or conclusion, and a
        # LATER codex-leg attempt can legitimately produce one that fits.
        return FinalizeResult(
            outcome=FinalizeOutcome.DEFECT,
            defect_reason="oversized_output",
            defect_message=(
                f"wa-finalize: codex output {post_format_len} chars post-format "
                f"exceeds the WhatsApp single-message limit, thread {thread_id}"
            ),
        )

    if post_format_len > _WHATSAPP_HARD_SEND_LIMIT:
        logger.warning(
            "wa-inbox bot: reply for thread %s is %d chars post-format (%d "
            "pre-format), exceeds WhatsApp's %d-char single-message limit — "
            "whatsapp_service.fit_to_whatsapp_limit will cut it at a boundary "
            "and mark it on send. This module deliberately does NOT cut: the "
            "send is the choke point (~14 call sites, only 2 of which chunk), "
            "so curing it here would cure one producer and leave the rest "
            "severing words mid-token.",
            thread_id,
            post_format_len,
            pre_format_len,
            _WHATSAPP_HARD_SEND_LIMIT,
        )

    logger.info(
        "wa-inbox bot generated reply for thread %s (%d chars post-format, %d chars pre-format)",
        thread_id,
        post_format_len,
        pre_format_len,
    )

    if human_reason is not None:
        # The REPLY-PRODUCING causes land here; the defect exits above notify
        # (on the Gemini leg) before returning. All causes mean the same thing
        # operationally: the client did not get an answer to what they asked
        # (or explicitly asked for a person). The copy the client reads is
        # deliberately unchanged by this branch, so nothing here can turn into
        # a promise of a reply. The notification body is withheld inside the
        # caller's helper (`message_text=None`): routing a NEW trigger through
        # the cleartext payload would widen exactly the third-party exposure
        # CLAUDE.md §14 constrains. The thread ref is what makes the omission
        # workable — the notified human can open the thread.
        await _tell(human_reason)

    return FinalizeResult(
        outcome=FinalizeOutcome.SEND,
        text=answer,
        human_reason=human_reason,
    )
