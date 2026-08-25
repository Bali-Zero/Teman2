"""Focused unit tests for check_domain_boundary (check 5) and
check_render_and_length (checks 10 + text-half of 11) — edge cases the
B6b golden fixtures do not individually isolate.

Author: Claude Opus 5 (lane B1b — client-bot engine).
"""

from __future__ import annotations

from backend.channels.models import AttachmentKind, ClientSurface
from backend.channels.profiles import CLIENT_IG_V1, CLIENT_KBLI_V1, CLIENT_PORTAL_V1, CLIENT_WA_V1
from backend.services.client_bot.policy.surface_check import (
    check_domain_boundary,
    check_render_and_length,
)
from backend.services.client_bot.policy.types import GateReason, GateVerdict
from backend.tests.duebot.goldens.builders import (
    make_abstain_candidate,
    make_answer_candidate,
    make_attachment,
    make_canonical_message,
    make_portal_message,
)


def test_domain_outside_profile_scope_aborts() -> None:
    # "kbli" is itself a member of CLIENT_WA_V1.allowed_domains (the shared
    # _REGULATED_DOMAINS frozenset covers all five domains for every
    # non-KBLI-widget profile) — a domain genuinely outside scope for every
    # frozen profile is needed here instead.
    message = make_canonical_message("dom")
    outcome = check_domain_boundary(message, CLIENT_WA_V1, domain="logistics")
    assert outcome is not None
    assert outcome.verdict == GateVerdict.ABSTAIN
    assert outcome.reason == GateReason.DOMAIN_OUT_OF_SURFACE_SCOPE


def test_domain_inside_profile_scope_passes() -> None:
    message = make_canonical_message("dom")
    outcome = check_domain_boundary(message, CLIENT_WA_V1, domain="immigration")
    assert outcome is None


def test_kbli_widget_rejects_non_kbli_domain() -> None:
    message = make_canonical_message("dom", surface=ClientSurface.KBLI_WIDGET)
    outcome = check_domain_boundary(message, CLIENT_KBLI_V1, domain="immigration")
    assert outcome is not None
    assert outcome.reason == GateReason.DOMAIN_OUT_OF_SURFACE_SCOPE


def test_unauthenticated_portal_context_is_leak() -> None:
    # CanonicalMessage._portal_surface_requires_authentication (F2) forbids
    # constructing a PORTAL-surface message with actor.authenticated=False
    # at all, so the check_domain_boundary branch under test — which reads
    # profile.authentication_required together with message.actor.authenticated,
    # not message.surface — is exercised via a WHATSAPP-surface message
    # (unauthenticated, which IS constructible) paired with the
    # authentication-requiring CLIENT_PORTAL_V1 profile.
    message = make_canonical_message("dom", authenticated=False)
    outcome = check_domain_boundary(message, CLIENT_PORTAL_V1, domain="immigration")
    assert outcome is not None
    assert outcome.reason == GateReason.UNAUTHENTICATED_PORTAL_CONTEXT_LEAK


def test_authenticated_portal_context_passes() -> None:
    message = make_portal_message("dom")
    outcome = check_domain_boundary(message, CLIENT_PORTAL_V1, domain="immigration")
    assert outcome is None


def test_unaccepted_attachment_kind_is_profile_mismatch() -> None:
    attachment = make_attachment("dom", kind=AttachmentKind.DOCUMENT)
    message = make_canonical_message("dom", surface=ClientSurface.INSTAGRAM, attachments=(attachment,))
    outcome = check_domain_boundary(message, CLIENT_IG_V1, domain="immigration")
    assert outcome is not None
    assert outcome.reason == GateReason.ATTACHMENT_PROFILE_MISMATCH


def test_too_many_attachments_is_profile_mismatch() -> None:
    attachments = tuple(make_attachment("dom", suffix=f"a{i}") for i in range(5))
    message = make_canonical_message("dom", attachments=attachments)
    outcome = check_domain_boundary(message, CLIENT_WA_V1, domain="immigration")
    assert outcome is not None
    assert outcome.reason == GateReason.ATTACHMENT_PROFILE_MISMATCH


def test_non_answer_disposition_is_a_trivial_pass() -> None:
    candidate = make_abstain_candidate("ren")
    message = make_canonical_message("ren")
    outcome, rendered = check_render_and_length(candidate, message, CLIENT_WA_V1)
    assert outcome is None
    assert rendered is None


def test_markdown_in_a_no_markdown_profile_is_format_violation() -> None:
    candidate = make_answer_candidate("ren", answer="**Bold** claim here.")
    message = make_canonical_message("ren")
    outcome, rendered = check_render_and_length(candidate, message, CLIENT_WA_V1)
    assert outcome is not None
    assert outcome.reason == GateReason.RENDER_FORMAT_VIOLATION
    assert rendered is None


def test_too_many_paragraphs_is_format_violation() -> None:
    body = "\n\n".join(f"Paragraf {i}." for i in range(CLIENT_WA_V1.max_paragraphs + 1))
    candidate = make_answer_candidate("ren", answer=body)
    message = make_canonical_message("ren")
    outcome, rendered = check_render_and_length(candidate, message, CLIENT_WA_V1)
    assert outcome is not None
    assert outcome.reason == GateReason.RENDER_FORMAT_VIOLATION


def test_too_many_bullets_is_format_violation() -> None:
    body = "\n".join(f"- item {i}" for i in range(CLIENT_WA_V1.max_bullets + 1))
    candidate = make_answer_candidate("ren", answer=body)
    message = make_canonical_message("ren")
    outcome, rendered = check_render_and_length(candidate, message, CLIENT_WA_V1)
    assert outcome is not None
    assert outcome.reason == GateReason.RENDER_FORMAT_VIOLATION


def test_length_exceeding_hard_max_chars_is_rejected() -> None:
    body = "x" * (CLIENT_IG_V1.hard_max_chars + 200)
    candidate = make_answer_candidate("ren", answer=body)
    message = make_canonical_message("ren")
    outcome, rendered = check_render_and_length(candidate, message, CLIENT_IG_V1)
    assert outcome is not None
    assert outcome.reason in (GateReason.LENGTH_EXCEEDS_HARD_LIMIT, GateReason.RENDERER_ADDED_CONTENT)


def test_clean_short_answer_passes_and_renders() -> None:
    candidate = make_answer_candidate("ren", answer="Jawaban singkat yang jelas.")
    message = make_canonical_message("ren")
    outcome, rendered = check_render_and_length(candidate, message, CLIENT_WA_V1)
    assert outcome is None
    assert rendered is not None
