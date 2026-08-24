"""SurfaceProfile — the four frozen client-bot surface contracts (F2).

Frozen per docs/plans/2026-08-25-due-bot-live/MANDATE.md F2 and
research/operations/2026-08-25-due-bot-7-lens-research.md §1.4.

F2 invariants (enforced by tests, not just convention):

- A profile carries length/format/citation-style/history/deadlines/
  handoff-queue and NEVER a provider name. Changing
  ``CLIENT_BOT_PRIMARY_PROVIDER`` cannot alter transport behavior because
  no field on this model can hold a provider identifier.
- ``client-kbli-v1`` is domain-restricted to KBLI only.
- ``client-portal-v1`` requires authentication.

Author: Claude Opus 5 (lane B1a — client-bot contract freeze)
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from backend.channels.models import AttachmentKind, ClientSurface

__all__ = [
    "CLIENT_IG_V1",
    "CLIENT_KBLI_V1",
    "CLIENT_PORTAL_V1",
    "CLIENT_WA_V1",
    "FROZEN_PROFILES",
    "PROFILES_BY_ID",
    "PROFILES_BY_SURFACE",
    "CitationPolicy",
    "CitationStyle",
    "ProgressMode",
    "SurfaceProfile",
    "get_profile",
]


class CitationPolicy(StrEnum):
    REGULATORY_AND_NUMERIC = "regulatory_and_numeric"
    ALL_FACTUAL = "all_factual"


class CitationStyle(StrEnum):
    COMPACT_NUMBERED = "compact_numbered"
    MARKDOWN_FOOTNOTE = "markdown_footnote"
    SOURCE_CARDS = "source_cards"


class ProgressMode(StrEnum):
    NONE = "none"
    STATUS_ONLY = "status_only"
    SSE_STATUS = "sse_status"


class SurfaceProfile(BaseModel):
    """Everything about HOW a surface renders/behaves — never WHICH brain answers it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_id: str
    version: int
    surface: ClientSurface

    allowed_domains: frozenset[str]
    authentication_required: bool

    max_words: int
    soft_max_chars: int
    hard_max_chars: int
    max_paragraphs: int
    max_bullets: int

    allow_markdown: bool
    allow_emoji: bool
    citation_policy: CitationPolicy
    citation_style: CitationStyle

    progress_mode: ProgressMode
    final_content_atomic: bool = True

    history_turns: int
    provider_deadline_ms: int
    ack_deadline_ms: int

    accepted_attachment_kinds: frozenset[AttachmentKind]
    max_attachments: int

    renderer_name: str
    handoff_queue: str
    abstention_copy_key: str
    transient_failure_copy_key: str
    handoff_copy_key: str


# ---------------------------------------------------------------------------
# The four frozen profiles (research capture §1.4 table). Field values not
# given a concrete number/string in the table are documented inventions —
# see the report's decision log for the rationale on each.
# ---------------------------------------------------------------------------

_REGULATED_DOMAINS = frozenset({"immigration", "company", "tax", "property", "kbli"})

CLIENT_WA_V1 = SurfaceProfile(
    profile_id="client-wa-v1",
    version=1,
    surface=ClientSurface.WHATSAPP,
    allowed_domains=_REGULATED_DOMAINS,
    authentication_required=False,
    max_words=150,
    soft_max_chars=1_800,
    hard_max_chars=4_096,
    max_paragraphs=5,
    max_bullets=7,
    allow_markdown=False,
    allow_emoji=True,
    citation_policy=CitationPolicy.REGULATORY_AND_NUMERIC,
    citation_style=CitationStyle.COMPACT_NUMBERED,
    progress_mode=ProgressMode.STATUS_ONLY,
    final_content_atomic=True,
    history_turns=12,
    provider_deadline_ms=15_000,
    ack_deadline_ms=200,
    accepted_attachment_kinds=frozenset(
        {AttachmentKind.IMAGE, AttachmentKind.DOCUMENT, AttachmentKind.AUDIO}
    ),
    max_attachments=3,
    renderer_name="whatsapp_light",
    handoff_queue="client_general",
    abstention_copy_key="client_bot.whatsapp.abstain",
    transient_failure_copy_key="client_bot.whatsapp.transient_failure",
    handoff_copy_key="client_bot.whatsapp.handoff",
)

CLIENT_IG_V1 = SurfaceProfile(
    profile_id="client-ig-v1",
    version=1,
    surface=ClientSurface.INSTAGRAM,
    allowed_domains=_REGULATED_DOMAINS,
    authentication_required=False,
    max_words=150,
    soft_max_chars=800,
    hard_max_chars=1_000,
    max_paragraphs=4,
    max_bullets=5,
    allow_markdown=False,
    allow_emoji=True,
    citation_policy=CitationPolicy.REGULATORY_AND_NUMERIC,
    citation_style=CitationStyle.COMPACT_NUMBERED,
    progress_mode=ProgressMode.NONE,
    final_content_atomic=True,
    history_turns=8,
    provider_deadline_ms=12_000,
    ack_deadline_ms=200,
    accepted_attachment_kinds=frozenset({AttachmentKind.IMAGE}),
    max_attachments=1,
    renderer_name="plain_text",
    handoff_queue="client_general",
    abstention_copy_key="client_bot.instagram.abstain",
    transient_failure_copy_key="client_bot.instagram.transient_failure",
    handoff_copy_key="client_bot.instagram.handoff",
)

CLIENT_PORTAL_V1 = SurfaceProfile(
    profile_id="client-portal-v1",
    version=1,
    surface=ClientSurface.PORTAL,
    allowed_domains=_REGULATED_DOMAINS,
    authentication_required=True,
    max_words=800,
    soft_max_chars=6_000,
    hard_max_chars=12_000,
    max_paragraphs=12,
    max_bullets=15,
    allow_markdown=True,
    allow_emoji=False,
    citation_policy=CitationPolicy.REGULATORY_AND_NUMERIC,
    # Table cell is the compound "source cards/footnotes" — MARKDOWN_FOOTNOTE
    # chosen here (KBLI takes SOURCE_CARDS below); see report decision log.
    citation_style=CitationStyle.MARKDOWN_FOOTNOTE,
    progress_mode=ProgressMode.SSE_STATUS,
    final_content_atomic=True,
    history_turns=20,
    provider_deadline_ms=20_000,
    ack_deadline_ms=500,
    accepted_attachment_kinds=frozenset({AttachmentKind.IMAGE, AttachmentKind.DOCUMENT}),
    max_attachments=5,
    renderer_name="markdown",
    handoff_queue="portal_case",
    abstention_copy_key="client_bot.portal.abstain",
    transient_failure_copy_key="client_bot.portal.transient_failure",
    handoff_copy_key="client_bot.portal.handoff",
)

CLIENT_KBLI_V1 = SurfaceProfile(
    profile_id="client-kbli-v1",
    version=1,
    surface=ClientSurface.KBLI_WIDGET,
    allowed_domains=frozenset({"kbli"}),
    # Table says "No, unless personalized" — the personalized case is a
    # future extension not yet designed; frozen at False for this unit. See
    # report decision log.
    authentication_required=False,
    max_words=400,
    soft_max_chars=3_200,
    hard_max_chars=6_000,
    max_paragraphs=8,
    max_bullets=10,
    allow_markdown=True,
    allow_emoji=False,
    citation_policy=CitationPolicy.ALL_FACTUAL,
    citation_style=CitationStyle.SOURCE_CARDS,
    progress_mode=ProgressMode.SSE_STATUS,
    final_content_atomic=True,
    history_turns=8,
    provider_deadline_ms=15_000,
    ack_deadline_ms=500,
    accepted_attachment_kinds=frozenset({AttachmentKind.IMAGE, AttachmentKind.DOCUMENT}),
    max_attachments=2,
    renderer_name="markdown",
    handoff_queue="kbli_specialist",
    abstention_copy_key="client_bot.kbli_widget.abstain",
    transient_failure_copy_key="client_bot.kbli_widget.transient_failure",
    handoff_copy_key="client_bot.kbli_widget.handoff",
)

FROZEN_PROFILES: tuple[SurfaceProfile, ...] = (
    CLIENT_WA_V1,
    CLIENT_IG_V1,
    CLIENT_PORTAL_V1,
    CLIENT_KBLI_V1,
)

PROFILES_BY_ID: dict[str, SurfaceProfile] = {p.profile_id: p for p in FROZEN_PROFILES}
PROFILES_BY_SURFACE: dict[ClientSurface, SurfaceProfile] = {p.surface: p for p in FROZEN_PROFILES}


def get_profile(profile_id: str) -> SurfaceProfile:
    """Look up a frozen profile by id. Raises KeyError on an unknown id."""
    return PROFILES_BY_ID[profile_id]
