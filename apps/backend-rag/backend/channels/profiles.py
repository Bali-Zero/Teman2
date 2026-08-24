"""SurfaceProfile — the four frozen client-bot surface contracts (F2).

Frozen per docs/plans/2026-08-25-due-bot-live/MANDATE.md F2 and
research/operations/2026-08-25-due-bot-7-lens-research.md §1.4.

F2 invariants (enforced by tests, not just convention):

- A profile carries length/format/citation-style/history/deadlines/
  handoff-queue and NEVER a provider name. Changing
  ``CLIENT_BOT_PRIMARY_PROVIDER`` cannot alter transport behavior because
  no field on this model can hold a provider identifier: ``renderer_name``/
  ``handoff_queue`` are CLOSED enums (a value like ``"vertex-ai"`` cannot
  be constructed at all, not merely "not currently present"), and the
  three copy-key fields are pattern-anchored to
  ``client_bot.<surface>.<kind>`` rather than free text.
- ``client-kbli-v1`` is domain-restricted to KBLI only.
- ``client-portal-v1`` requires authentication.

Author: Claude Opus 5 (lane B1a — client-bot contract freeze)
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

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
    "HandoffQueue",
    "ProgressMode",
    "RendererName",
    "SurfaceProfile",
    "get_profile",
]

# The copy-key fields are per-surface i18n lookup keys, not a closed set the
# way renderer_name/handoff_queue are — but they must still be structurally
# incapable of holding an arbitrary value (a provider name included), so each
# is pattern-anchored to `client_bot.<surface-slug>.<kind>` rather than typed
# as free text.
_ABSTAIN_KEY_PATTERN = r"^client_bot\.[a-z_]+\.abstain$"
_TRANSIENT_FAILURE_KEY_PATTERN = r"^client_bot\.[a-z_]+\.transient_failure$"
_HANDOFF_KEY_PATTERN = r"^client_bot\.[a-z_]+\.handoff$"


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


class RendererName(StrEnum):
    """Closed set (F2: 'never a provider name'). A free ``str`` field could
    hold ``"vertex-ai"`` just as easily as a real renderer id — a closed
    enum cannot, by construction, so the value can never leak a provider
    identity regardless of what anyone types into a profile later.
    """

    WHATSAPP_LIGHT = "whatsapp_light"
    PLAIN_TEXT = "plain_text"
    MARKDOWN = "markdown"


class HandoffQueue(StrEnum):
    """Closed set, same rationale as ``RendererName``."""

    CLIENT_GENERAL = "client_general"
    PORTAL_CASE = "portal_case"
    KBLI_SPECIALIST = "kbli_specialist"


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

    renderer_name: RendererName
    handoff_queue: HandoffQueue
    abstention_copy_key: Annotated[str, Field(pattern=_ABSTAIN_KEY_PATTERN)]
    transient_failure_copy_key: Annotated[str, Field(pattern=_TRANSIENT_FAILURE_KEY_PATTERN)]
    handoff_copy_key: Annotated[str, Field(pattern=_HANDOFF_KEY_PATTERN)]


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
    renderer_name=RendererName.WHATSAPP_LIGHT,
    handoff_queue=HandoffQueue.CLIENT_GENERAL,
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
    renderer_name=RendererName.PLAIN_TEXT,
    handoff_queue=HandoffQueue.CLIENT_GENERAL,
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
    renderer_name=RendererName.MARKDOWN,
    handoff_queue=HandoffQueue.PORTAL_CASE,
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
    renderer_name=RendererName.MARKDOWN,
    handoff_queue=HandoffQueue.KBLI_SPECIALIST,
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
