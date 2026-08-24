"""CanonicalMessage — transport-neutral inbound-message contract for BOT A.

Frozen per docs/plans/2026-08-25-due-bot-live/MANDATE.md F1/F2 and
research/operations/2026-08-25-due-bot-7-lens-research.md §1.3.

Hard invariant (F1): the brain (ClientBotEngine / any ClientBrainProvider)
never receives a phone number, Instagram username, portal token, signed
media URL, or raw webhook payload — only opaque references and stable
pseudonymous subject tokens. That invariant is encoded here in the field
TYPES (HMAC-shaped patterns, a media reference validator that rejects
anything URL-shaped), not left to adapter discipline or a comment:

- ``CanonicalActor.subject_token`` must be a 64-hex-char digest (the shape
  of an HMAC-SHA256 hex output). A raw phone number or IG handle cannot
  satisfy this pattern, so a field-level type error — not a downstream
  policy check — is what happens if an adapter forgets to hash it.
- ``CanonicalAttachment.media_ref`` is rejected outright if it contains
  ``://`` (i.e. looks like any URL, signed or not). Adapters must resolve
  media through the internal media store and pass its opaque reference.

This module intentionally does NOT import ``backend.channels.profiles`` —
the "attachments/context must match the selected SurfaceProfile" checks
(research capture §1.6 check 5) are FinalPolicyGate business logic
(``final_gate.py``, explicitly out of scope for this contract-freeze unit)
and are not encoded as a CanonicalMessage-level validator here.

Author: Claude Opus 5 (lane B1a — client-bot contract freeze)
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

__all__ = [
    "AttachmentKind",
    "CanonicalActor",
    "CanonicalAttachment",
    "CanonicalMessage",
    "ClientSurface",
    "MessageKind",
    "SurfaceContext",
]

# sha256 hex digest — reused shape for subject_token/idempotency_key/raw_payload_sha256.
# Duplicated (not shared via a constant) deliberately: this is a channels/-layer
# contract file, and pulling a shared "patterns" module in from services/client_bot
# would create a cross-layer coupling this freeze does not need. See report decision log.
_SHA256_HEX = r"^[0-9a-f]{64}$"


class ClientSurface(StrEnum):
    """The four frozen BOT A surfaces (F2)."""

    WHATSAPP = "whatsapp"
    INSTAGRAM = "instagram"
    PORTAL = "portal"
    KBLI_WIDGET = "kbli_widget"


class MessageKind(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    DOCUMENT = "document"
    AUDIO = "audio"
    MIXED = "mixed"


class AttachmentKind(StrEnum):
    IMAGE = "image"
    DOCUMENT = "document"
    AUDIO = "audio"


class CanonicalAttachment(BaseModel):
    """A single attachment reference. Never a signed/raw URL — see module docstring."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    attachment_id: UUID
    kind: AttachmentKind
    mime_type: Annotated[str, Field(max_length=255)]
    media_ref: Annotated[str, Field(min_length=1, max_length=512)]
    filename: Annotated[str, Field(max_length=255)] | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    sha256: Annotated[str, Field(pattern=_SHA256_HEX)] | None = None
    extracted_text_ref: Annotated[str, Field(max_length=512)] | None = None

    @field_validator("media_ref")
    @classmethod
    def _media_ref_must_not_be_url_shaped(cls, value: str) -> str:
        """Reject anything that looks like a URL — signed or not (F1 hard invariant).

        A real opaque media-store reference never contains a scheme separator;
        a signed URL (S3/GCS/Meta media proxy) always does. This is a cheap,
        robust structural check rather than an allow-list of media-store
        naming schemes, which would need updating every time a new store is
        added.
        """
        if "://" in value:
            raise ValueError(
                "media_ref must be an opaque media-store reference, never a "
                "URL (signed or otherwise) — resolve via the media store "
                "before constructing CanonicalAttachment"
            )
        return value


class CanonicalActor(BaseModel):
    """The message sender, identified only by a pseudonymous, server-derived token."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    # HMAC(surface + external subject) — never the raw phone number / IG
    # username / portal user id. The 64-hex-char pattern is the structural
    # enforcement of that rule: adapters/routers must hash before construction.
    subject_token: Annotated[str, Field(pattern=_SHA256_HEX)]
    canonical_user_id: UUID | None
    authenticated: bool
    locale: Annotated[str, Field(max_length=35)] | None
    customer_tier: Annotated[str, Field(max_length=64)] | None = None  # server-derived only


class SurfaceContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    account_ref: Annotated[str, Field(min_length=1, max_length=255)]
    route: Annotated[str, Field(max_length=255)] | None = None
    product: Literal["client_bot", "portal", "kbli_navigator"] = "client_bot"
    portal_case_id: UUID | None = None
    kbli_code: Annotated[str, Field(max_length=16)] | None = None
    page_context_ref: Annotated[str, Field(max_length=255)] | None = None
    authenticated_session_id: UUID | None = None


class CanonicalMessage(BaseModel):
    """The one inbound-message shape every ClientBotEngine consumer sees.

    Adapters (whatsapp/instagram/web) translate raw platform events into
    this type; it is the ONLY type that crosses into ClientBotEngine /
    ClientBrainProvider. Construction (idempotency_key, subject_token,
    profile selection, account mapping) is server-derived — an adapter must
    never accept these fields verbatim from client-controlled JSON. That
    discipline lives in the (out-of-scope) adapter code; this model only
    enforces what is checkable from its own fields.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    event_id: UUID
    trace_id: UUID
    surface: ClientSurface

    external_message_id: Annotated[str, Field(min_length=1, max_length=255)]
    idempotency_key: Annotated[str, Field(pattern=_SHA256_HEX)]
    conversation_id: UUID
    session_id: UUID
    reply_to_external_message_id: Annotated[str, Field(max_length=255)] | None = None

    kind: MessageKind
    text: Annotated[str, Field(max_length=16_000)] = ""
    attachments: tuple[CanonicalAttachment, ...] = Field(default=(), max_length=10)

    actor: CanonicalActor
    surface_context: SurfaceContext

    occurred_at: datetime
    received_at: datetime
    delivery_deadline_at: datetime | None = None
    locale_hint: Annotated[str, Field(max_length=35)] | None = None

    raw_payload_sha256: Annotated[str, Field(pattern=_SHA256_HEX)]

    @model_validator(mode="after")
    def _at_least_one_of_text_or_attachments(self) -> CanonicalMessage:
        if not self.text and not self.attachments:
            raise ValueError("CanonicalMessage requires at least one of text or attachments")
        return self

    @model_validator(mode="after")
    def _portal_case_id_only_on_portal(self) -> CanonicalMessage:
        if self.surface_context.portal_case_id is not None and self.surface != ClientSurface.PORTAL:
            raise ValueError("portal_case_id is only legal when surface is PORTAL")
        return self

    @model_validator(mode="after")
    def _kbli_code_only_on_kbli_widget(self) -> CanonicalMessage:
        if self.surface_context.kbli_code is not None and self.surface != ClientSurface.KBLI_WIDGET:
            raise ValueError("kbli_code is only legal when surface is KBLI_WIDGET")
        return self

    @model_validator(mode="after")
    def _portal_surface_requires_authentication(self) -> CanonicalMessage:
        """F2: 'Portal requires auth.' The four SurfaceProfiles are frozen
        1:1 with ClientSurface (PORTAL always resolves to client-portal-v1,
        which has authentication_required=True) — so this can be enforced
        here without importing profiles.py. See report decision log for why
        this replaces the research capture's more generic
        'authenticated_session_id must exist when the profile requires it'
        phrasing, which is not checkable from CanonicalMessage alone.
        """
        if self.surface == ClientSurface.PORTAL:
            if not self.actor.authenticated:
                raise ValueError("PORTAL surface requires actor.authenticated=True (F2)")
            if self.surface_context.authenticated_session_id is None:
                raise ValueError(
                    "PORTAL surface requires surface_context.authenticated_session_id (F2)"
                )
        return self
