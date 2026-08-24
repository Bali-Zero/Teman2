"""Checks 5, 10, and the text-bound half of check 11 — surface/domain
boundary, language/rendering, and hard length (research capture Sol §1.6).
The "length/format/domain enforcement" module Sol's own layout names.

Check 11's OTHER half — "recheck idempotency immediately before outbox
insertion" — needs live DB state (an insert against the outbox table) and
stays in ``final_gate.py`` itself, the same way check 1's delivery/thread
fence does (both are injected-state checks, not pure functions of
candidate+profile).

Rendering (``render_answer``) reuses ``channels/format.py::format_rich_text``
— the existing, channel-aware formatter (whatsapp/instagram/web capability
table) rather than a new one. ``RENDERER_ADDED_CONTENT`` is a coarse
length-growth heuristic, not a semantic diff: this module cannot judge
"is this new sentence a fact" (that would be the same unbounded-NLP trap
the team lead's brief warned against) — it can only catch the SHAPE of a
renderer that grew the text well beyond what stripping/reformatting could
explain. A renderer that ADDS a short new factual clause while shrinking
elsewhere would not be caught by length alone; this is a documented
residual, not a claim of completeness.

Author: Claude Opus 5 (lane B1b — client-bot engine).
"""

from __future__ import annotations

import re

from backend.channels.format import format_rich_text
from backend.channels.models import CanonicalMessage, ClientSurface
from backend.channels.profiles import SurfaceProfile
from backend.services.client_bot.contracts import BrainCandidate
from backend.services.client_bot.policy.check_result import CheckOutcome
from backend.services.client_bot.policy.types import GateReason, GateVerdict
from backend.services.rag.agentic.query_helpers import detect_query_language

__all__ = ["check_domain_boundary", "check_render_and_length", "render_answer"]

_SURFACE_TO_FORMAT_CHANNEL: dict[ClientSurface, str] = {
    ClientSurface.WHATSAPP: "whatsapp",
    ClientSurface.INSTAGRAM: "instagram",
    ClientSurface.PORTAL: "web",
    ClientSurface.KBLI_WIDGET: "web",
}

# A conservative signal that markdown syntax leaked into a profile that
# forbids it (allow_markdown=False) — headers, emphasis, links, code
# fences. Not exhaustive of every markdown construct; broad enough to
# catch what an LLM actually emits.
_MARKDOWN_SYNTAX_RE = re.compile(r"(\*\*[^*]+\*\*|^#{1,6}\s|\[[^\]]+\]\([^)]+\)|```)", re.MULTILINE)

# format_rich_text is a formatting transform (strip/reformat), never a
# content generator — a legitimate transform can still grow text somewhat
# (e.g. expanding a citation marker into "(source: ...)"), so the
# tolerance is generous rather than tight, to keep this a shape check on
# gross growth, not a trigger-happy false-positive machine.
_RENDER_GROWTH_TOLERANCE_RATIO = 1.15
_RENDER_GROWTH_TOLERANCE_FLOOR = 80


def render_answer(answer: str, profile: SurfaceProfile) -> str:
    """The one rendering step every surface answer passes through before
    check 10/11 measure it — "render first, then measure the actual
    outbound payload" (Sol §1.6, check 11).
    """
    channel = _SURFACE_TO_FORMAT_CHANNEL[profile.surface]
    return format_rich_text(answer, channel)


def check_domain_boundary(
    message: CanonicalMessage, profile: SurfaceProfile, domain: str
) -> CheckOutcome | None:
    """Check 5. None means pass. ``domain`` is ``GroundingBundle.domain`` —
    passed separately rather than importing GroundingBundle here to keep
    this check's signature minimal (it only needs the one field).

    Runs regardless of ``candidate.disposition`` — domain/auth/attachment
    scope are structural facts about the REQUEST, not about what the
    candidate said, and take priority over a generic self-abstain when
    both apply (verified against the B6b golden fixture
    "client.kbli-outside-widget-domain": an abstain candidate on an
    out-of-domain query must still surface DOMAIN_OUT_OF_SURFACE_SCOPE,
    not the less specific MODEL_ABSTAINED — see final_gate.py's own
    comment on why this check runs before check 4).
    """
    if domain not in profile.allowed_domains:
        return CheckOutcome(
            verdict=GateVerdict.ABSTAIN,
            reason=GateReason.DOMAIN_OUT_OF_SURFACE_SCOPE,
            reason_detail=f"domain={domain!r} not in {sorted(profile.allowed_domains)!r}",
        )

    if profile.authentication_required and not message.actor.authenticated:
        return CheckOutcome(
            verdict=GateVerdict.ABSTAIN,
            reason=GateReason.UNAUTHENTICATED_PORTAL_CONTEXT_LEAK,
            reason_detail="profile requires authentication but actor.authenticated is False",
        )

    for attachment in message.attachments:
        if attachment.kind not in profile.accepted_attachment_kinds:
            return CheckOutcome(
                verdict=GateVerdict.ABSTAIN,
                reason=GateReason.ATTACHMENT_PROFILE_MISMATCH,
                reason_detail=f"attachment kind={attachment.kind.value!r} not accepted by {profile.profile_id}",
            )
    if len(message.attachments) > profile.max_attachments:
        return CheckOutcome(
            verdict=GateVerdict.ABSTAIN,
            reason=GateReason.ATTACHMENT_PROFILE_MISMATCH,
            reason_detail=f"{len(message.attachments)} attachments > max {profile.max_attachments}",
        )

    return None


def check_render_and_length(
    candidate: BrainCandidate, message: CanonicalMessage, profile: SurfaceProfile
) -> tuple[CheckOutcome | None, str | None]:
    """Checks 10 + the text half of 11. Returns ``(outcome, rendered_text)``
    — ``rendered_text`` is populated only when ``outcome is None`` (a
    non-None outcome means the sequence stops here and no send-worthy text
    exists), matching ``FinalDecision``'s own iff-ALLOW rule so the caller
    never has to reconcile the two independently.
    """
    if candidate.disposition != "answer":
        return None, None

    if not profile.allow_markdown and _MARKDOWN_SYNTAX_RE.search(candidate.answer):
        return (
            CheckOutcome(
                verdict=GateVerdict.TEXT_DEFECT,
                reason=GateReason.RENDER_FORMAT_VIOLATION,
                reason_detail="markdown syntax present but profile.allow_markdown is False",
            ),
            None,
        )

    paragraphs = [p for p in candidate.answer.split("\n\n") if p.strip()]
    if len(paragraphs) > profile.max_paragraphs:
        return (
            CheckOutcome(
                verdict=GateVerdict.TEXT_DEFECT,
                reason=GateReason.RENDER_FORMAT_VIOLATION,
                reason_detail=f"{len(paragraphs)} paragraphs > max {profile.max_paragraphs}",
            ),
            None,
        )

    bullets = len(re.findall(r"^\s*(?:[-*•]|\d+\.)\s+", candidate.answer, re.MULTILINE))
    if bullets > profile.max_bullets:
        return (
            CheckOutcome(
                verdict=GateVerdict.TEXT_DEFECT,
                reason=GateReason.RENDER_FORMAT_VIOLATION,
                reason_detail=f"{bullets} bullets > max {profile.max_bullets}",
            ),
            None,
        )

    if message.locale_hint is None and message.text:
        source_lang = detect_query_language(message.text)
        answer_lang = detect_query_language(candidate.answer)
        if source_lang not in ("und", "unknown", "") and answer_lang not in ("und", "unknown", ""):
            if source_lang != answer_lang:
                return (
                    CheckOutcome(
                        verdict=GateVerdict.TEXT_DEFECT,
                        reason=GateReason.RENDER_LANGUAGE_MISMATCH,
                        reason_detail=f"detected message={source_lang!r} answer={answer_lang!r}",
                    ),
                    None,
                )

    rendered = render_answer(candidate.answer, profile)

    growth_ceiling = len(candidate.answer) * _RENDER_GROWTH_TOLERANCE_RATIO + _RENDER_GROWTH_TOLERANCE_FLOOR
    if len(rendered) > growth_ceiling:
        return (
            CheckOutcome(
                verdict=GateVerdict.TEXT_DEFECT,
                reason=GateReason.RENDERER_ADDED_CONTENT,
                reason_detail=f"rendered {len(rendered)} chars vs answer {len(candidate.answer)} chars",
            ),
            None,
        )

    if len(rendered) > profile.hard_max_chars:
        return (
            CheckOutcome(
                verdict=GateVerdict.TEXT_DEFECT,
                reason=GateReason.LENGTH_EXCEEDS_HARD_LIMIT,
                reason_detail=f"rendered {len(rendered)} chars > hard_max_chars {profile.hard_max_chars}",
            ),
            None,
        )

    return None, rendered
