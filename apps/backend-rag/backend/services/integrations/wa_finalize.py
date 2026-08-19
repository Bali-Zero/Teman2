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
      internal-monologue leak, scaffold-only output, empty after strip/format,
      pricing veto, secret-egress hit) returns ``DEFECT`` WITHOUT serving a stub
      and WITHOUT telling a human — the caller fails off to the Gemini leg,
      which regenerates and re-enters this pipeline, so the client still gets
      an answer and the silent-client alarm stays with the leg that owns it
      (spec §2.3 TEXT_DEFECT). The abstain-label branch is the one POLICY
      branch: its verdict derives from the frozen evidence, not from who wrote
      the text, so it behaves identically on both providers (stub + tell a
      human — failing off could not change the verdict, spec §2.3 POLICY).

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


@dataclass(frozen=True)
class FinalizeResult:
    outcome: FinalizeOutcome
    text: str = ""
    # Why a human was (already) told, or None. On SEND outcomes the pipeline
    # has performed the notification itself via the caller's `tell_a_human`.
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
# currency-marked (Rp/IDR/USD/$). Bare numbers are deliberately OUT of scope:
# regulatory figures like "2,5 miliar modal disetor" legitimately come from
# retrieved chunks without a currency prefix, and vetoing them would be a
# family-#3 over-match blocking correct answers.
_CURRENCY_AMOUNT_RE = re.compile(
    r"(?:\bRp\.?|\bIDR\b|\bUSD\b|\$)\s*([0-9][0-9.,\s]*[0-9]|[0-9])"
    r"|([0-9][0-9.,\s]*[0-9]|[0-9])\s*(?:\bIDR\b|\bUSD\b)",
    re.IGNORECASE,
)

# Amounts shorter than this many digits are not vetoable: "Rp 5jt" captures
# only "5", and near-any source contains a lone digit — matching it would make
# the veto decorative. Declared limit: multiplier forms (jt/juta/miliar) are
# out of this veto's scan; the label gate + PricingTool grounding own them.
_PRICE_VETO_MIN_DIGITS = 4


def _normalized_digits(amount: str) -> str:
    return re.sub(r"[^0-9]", "", amount)


def price_tokens_outside_sources(text: str, price_sources: Sequence[str]) -> list[str]:
    """Digit-strings of currency-marked amounts in ``text`` absent from every source.

    ``price_sources`` should be the serialized PricingTool block of the frozen
    package plus the retrieved chunk texts — an amount is legitimate if ANY of
    them contains it (digit-normalized substring match, so "Rp 3.500.000" in
    the answer matches "3500000" or "3,500,000" in a source).
    """
    normalized_sources = [_normalized_digits(s) for s in price_sources]
    offenders: list[str] = []
    for match in _CURRENCY_AMOUNT_RE.finditer(text):
        amount = match.group(1) or match.group(2) or ""
        digits = _normalized_digits(amount)
        if len(digits) < _PRICE_VETO_MIN_DIGITS:
            continue
        if not any(digits in src for src in normalized_sources):
            offenders.append(digits)
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
        "token_assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token"
            r"|client[_-]?secret|authorization)\b\s*[:=]\s*['\"]?[A-Za-z0-9_.\-]{16,}"
        ),
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
    provider: str = "gemini",
    tell_a_human: Callable[[str], Awaitable[Any]] | None = None,
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
        provider: ``"gemini"`` (behavior-preserving inline path) or
            ``"codex"`` (typed-outcome path; see module docstring).
        tell_a_human: one-argument async callable ``(reason) -> accepted``.
            The pipeline calls it exactly where the pre-extraction code called
            ``_tell_a_human`` — stub paths on both providers, defect paths on
            the Gemini provider only (a codex defect fails off to the Gemini
            leg, which still owes the client an answer and re-enters here).
        price_sources / secret_scan / canary_tokens: codex-only egress vetoes,
            inert unless supplied (see module docstring).
    """

    async def _tell(reason: str) -> None:
        if tell_a_human is not None:
            await tell_a_human(reason)

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
        if substantive:
            if provider == "codex":
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
            return FinalizeResult(
                outcome=FinalizeOutcome.SEND,
                text=substantive + get_localized_stub("low_confidence_note", language),
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
        human_reason = "rag_abstain"
    else:
        answer = (data.get("answer") or "").strip()
        if not answer:
            # Measured deterministic, not transient: the 2026-08-10 battery got
            # a 0-character answer 5 times out of 5 on the same question, so the
            # retry ladder below cannot rescue this — it only spends attempts
            # and ends in silence. Tell a human BEFORE the raise, because the
            # raise is precisely what makes this silent. (Gemini leg only: a
            # codex defect fails off to the Gemini leg, which still answers.)
            if provider == "gemini":
                await _tell("empty_rag_answer")
            return FinalizeResult(
                outcome=FinalizeOutcome.DEFECT,
                defect_reason="empty_rag_answer",
                defect_message=f"wa-inbox bot: empty RAG answer for thread {thread_id}",
            )

        if _starts_with_internal_monologue_leak(answer):
            if provider == "codex":
                # TEXT_DEFECT (spec §2.3): a different generator can
                # legitimately cure a defective text — fail off instead of
                # serving the stub the Gemini leg would serve.
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
            if provider == "gemini":
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
            if provider == "codex":
                # TEXT_DEFECT: scaffold-only output is a broken text, and the
                # Gemini leg can produce a real answer — fail off.
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
    if provider == "codex" and human_reason != "rag_abstain":
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
        if provider == "gemini":
            await _tell(reason)
        return FinalizeResult(
            outcome=FinalizeOutcome.DEFECT,
            defect_reason=reason,
            defect_message=(
                f"wa-inbox bot: answer empty after channel formatting, thread {thread_id}"
            ),
        )
    post_format_len = len(answer)

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
