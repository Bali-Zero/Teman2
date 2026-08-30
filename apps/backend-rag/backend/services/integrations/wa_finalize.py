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
# test_wa_finalize.py::test_pricing_veto_multiplier_pattern_is_derived_from_the_table
# asserts the derivation holds. (The name cited here until 2026-08-30 was
# test_wa_finalize_price_veto.py, a file that does not exist in this tree —
# a citation pointing at nothing protects nothing.)
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


# ---------------------------------------------------------------------------
# TWO-COMPONENT TOTALS (added 2026-08-30)
#
# THE DEFECT that opened this, measured rather than argued: the ONE rule this
# bot must obey was unshippable. Zero's 2026-07-17 ruling is a single
# all-inclusive client-facing price, which for an Investor KITAS means
# 17,000,000 + 9,500,000 = 26,500,000 — a figure that appears in no source.
# Against the real package notation, before this change:
#
#     "Total all-in ... Rp26.500.000"        -> ['IDR:26500000']   VETOED
#     "biaya layanan Rp17.000.000.
#      PNBP pemerintah Rp9.500.000"          -> []                 passes
#
# So this veto was actively PUSHING the generator toward splitting the
# government levy out of the client price: splitting is the only shape that
# keeps every figure verbatim-anchored. The split-price defect guarded
# separately by `price_split_offenders` was, in part, this veto's own output.
#
# THE RULE: an amount is anchored if it is a source amount, or the sum of
# exactly TWO DISTINCT source amounts that are each price-sized. Nothing else.
# The generator may add up two things the sources state; it may not invent, and
# it may not multiply.
#
# WHAT WAS TRIED AND REJECTED, kept because the wider shape is the tempting one
# and this is the record of why it fails. The first version also admitted an
# integer multiple of a source amount, on the reasoning that a per-day rate
# times a day count is honest arithmetic. It is — but the code cannot see the
# count. It divided the GENERATED figure by a source figure and accepted any
# whole quotient. A cross-family adversarial reviewer returned BLOCK, and all
# seven of its concrete cases reproduced verbatim against the code:
#
#     Rp250.000.000  passed (250x the daily rate; the client asked about 5 days)
#     Rp88.000.000   passed (as did every whole million up to 366 million)
#     Rp1.002.069    passed (1,000,000 + 2024 + 45 — a year and an article no.)
#     Rp26.500.002   passed (the bare "2" from "2 years" used as an operand)
#     Rp43.500.000   passed (one 17,000,000 service fee charged twice)
#     Rp20.500.000   passed (KITAS fee + tax penalty + overstay fine, laundered)
#     Rp3.000.000    passed (a USD source authorizing an IDR multiple)
#
# With one Rp1,000,000/day source the guard admitted the entire round-million
# grid — precisely the numbers a generator emits. Divisibility is not
# derivation. Each of those seven is now a test.
#
# WHAT THIS STILL COSTS, stated rather than buried:
# * An honest multiplication is still vetoed. "5 hari x Rp1.000.000" is a
#   correct answer to a real question, and `wa_outbox` row 387 — fired alone
#   into a quiet thread — failed 5 of 5 attempts on exactly that and the client
#   got an apology. Admitting it safely requires binding the multiplier to a
#   count present in the CUSTOMER'S QUESTION, which this function never
#   receives. That is a signature change; it will be specified, not guessed.
# * Two REAL price amounts from unrelated chunks can still sum to a total no
#   source authorizes, because `price_sources` is a flat sequence of strings
#   carrying no provenance, no currency family and no semantic role. Closing
#   that is a data-contract change, not a predicate change.
def _summable_operands(price_sources: Sequence[str], cur: str) -> set[int]:
    """Source amounts eligible to be COMPONENTS of a two-part total.

    Deliberately much narrower than the membership set the veto uses. Two
    restrictions, each of which a cross-family reviewer demonstrated is
    load-bearing with a concrete case:

    * CURRENCY-MARKED ONLY. The membership set is harvested from every numeric
      token in every chunk, which is right for membership (a pricing block may
      state an amount without repeating its marker) and catastrophic for
      addition: years, article numbers, KBLI codes, quantities and even
      statistics are not money. `USD 59` passed as `45 + 14` from "Pasal 45"
      and "14 hari kerja"; `Rp7.275.000` passed as a tourist count plus a real
      fee. An earlier draft tried to exclude those with a magnitude floor,
      which is the wrong instrument -- a number's ROLE is not recoverable from
      its size, and the floor was simultaneously too low for a 7-digit
      non-money token and too high for a real Rp10.000 stamp duty.
    * SAME CURRENCY FAMILY as the answer. The membership set is untyped, so a
      USD figure could authorize an IDR one: `USD 100,000` (a capital minimum)
      plus `Rp500.000` (notary) authorized `Rp600.000`. Family is available
      here at no cost -- `_currency_amounts` already returns it -- so the pair
      rule keeps it even though membership, by its own documented residual,
      does not.

    Dropping the magnitude floor is what lets a genuine small line item (stamp
    duty, admin fee) still be a component; being currency-marked is the test
    that does the work the floor was failing to do.
    """
    operands: set[int] = set()
    for src in price_sources:
        for family, value in _currency_amounts(src):
            if family == cur and value > 0:
                operands.add(value)
    return operands


def _is_two_component_total(
    value: int, price_sources: Sequence[str], cur: str
) -> bool:
    """True when ``value`` is the sum of two DISTINCT same-currency amounts.

    Two terms, not three: three let unrelated chunks be laundered into a
    plausible package total (a KITAS fee + a tax penalty + an overstay fine
    summing to a "PT PMA setup price" no source states). Distinct VALUES, not
    occurrences: with replacement, one 17,000,000 service fee authorized
    43,500,000 by being charged twice.

    NO MULTIPLES, and that exclusion is the important one. An earlier version
    allowed an integer multiple of a source amount, reasoning that a per-day
    rate times a day count is honest arithmetic. It is -- but this function
    cannot see the count. It divided the GENERATED figure by a source figure
    and accepted any whole quotient, so a single `IDR 1,000,000/day` source
    authorized every whole million to 366 million, and `Rp250.000.000` passed
    a five-day question. Divisibility is not derivation.

    DECLARED FALSE POSITIVES, named so they are not mistaken for coverage.
    Each costs a retry and then an apology to a client whose answer was right:
    * an honest multiplication (5 days x Rp1.000.000) -- needs the multiplier
      bound to a count in the customer's question, which this function never
      receives;
    * a percentage of a base (PPh final 5% of Rp100.000.000) -- same shape,
      same missing input;
    * a legitimate three-component total (PNBP + telex + service fee).
    All three want the same thing: typed operands carrying a role, not a
    predicate guessing arithmetic backwards. That is a data-contract change.

    DECLARED FALSE NEGATIVE: two REAL same-currency amounts from UNRELATED
    chunks still sum to a total no source authorizes, because `price_sources`
    carries no provenance and no semantic role.
    """
    operands = _summable_operands(price_sources, cur)
    for a in operands:
        b = value - a
        if b > a and b in operands:
            return True
    return False


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
        if value in source_values:
            continue
        if not _is_two_component_total(value, price_sources, cur):
            offenders.append(f"{cur}:{value}")
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
