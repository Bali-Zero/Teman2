"""Data contracts for War Room 2.0 Review Gate.

Callback format: ``warroom:<action>:<draft_id>[:<motive>]``

- action: "approve" | "edit" | "reject"
- draft_id: UUID string (no dashes removed, str(uuid) form)
- motive (optional, reject-only): "tone" | "fact" | "visual" | "clickbait" | "other"

Telegram inline keyboards support up to 64 bytes per callback_data. Our format
stays well under that: prefix(7) + ":" + action(<=7) + ":" + uuid(36) + optional
":" + motive(<=9) = <=62 bytes. Safe.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from backend.services.war_room.models import RejectionReason

CALLBACK_PREFIX = "warroom"


class ReviewAction(str, Enum):
    APPROVE = "approve"
    EDIT = "edit"
    REJECT = "reject"


class ReviewCallbackError(ValueError):
    """Invalid callback_data received from Telegram."""


@dataclass(frozen=True)
class ReviewCallback:
    action: ReviewAction
    draft_id: UUID
    reject_reason: RejectionReason | None = None


@dataclass
class ReviewRequest:
    """Payload produced when a draft enters status=pending_review.

    Telegram limits caption length to 1024 chars; we keep caption trimmed
    in :meth:`to_caption` and extended info elsewhere.
    """

    draft_id: UUID
    topic: str
    tone_register: str
    cover_image_url: str
    first_slide_text: str
    rejected_registers: list[str] | None = None
    ultra_cost_usd: float | None = None
    canva_edit_url: str | None = None

    def to_caption(self, max_chars: int = 1000) -> str:
        parts = [
            "<b>War Room — bozza pronta</b>",
            f"<i>Topic:</i> {_escape_html(self.topic)}",
            f"<i>Registro:</i> <b>{_escape_html(self.tone_register)}</b>",
        ]
        if self.rejected_registers:
            parts.append(
                "<i>Scartati dal Consiglio:</i> "
                + ", ".join(_escape_html(r) for r in self.rejected_registers[:3])
            )
        parts.append(
            f"<i>Anteprima:</i> {_escape_html(self.first_slide_text[:280])}"
        )
        if self.ultra_cost_usd is not None:
            parts.append(f"<i>Costo immagini:</i> ${self.ultra_cost_usd:.2f}")
        if self.canva_edit_url:
            parts.append("🎨 <i>Canva editabile — usa il bottone qui sotto.</i>")
        caption = "\n".join(parts)
        if len(caption) > max_chars:
            return caption[: max_chars - 1] + "…"
        return caption


# ── Callback encoding / decoding ─────────────────────────────────────


def encode_callback(
    action: ReviewAction,
    draft_id: UUID,
    reject_reason: RejectionReason | None = None,
) -> str:
    pieces: list[str] = [CALLBACK_PREFIX, action.value, str(draft_id)]
    if reject_reason is not None:
        if action != ReviewAction.REJECT:
            raise ReviewCallbackError(
                "reject_reason only valid when action=reject",
            )
        pieces.append(reject_reason.value)
    payload = ":".join(pieces)
    if len(payload.encode("utf-8")) > 64:
        raise ReviewCallbackError(
            f"callback_data exceeds Telegram 64-byte limit: {len(payload)}",
        )
    return payload


def decode_callback(payload: str) -> ReviewCallback:
    if not payload or not isinstance(payload, str):
        raise ReviewCallbackError("empty or non-string callback_data")

    parts = payload.split(":")
    if len(parts) < 3 or parts[0] != CALLBACK_PREFIX:
        raise ReviewCallbackError(
            f"not a warroom callback: {payload[:80]}",
        )
    try:
        action = ReviewAction(parts[1])
    except ValueError as exc:
        raise ReviewCallbackError(
            f"unknown action: {parts[1]!r}",
        ) from exc

    try:
        draft_id = UUID(parts[2])
    except ValueError as exc:
        raise ReviewCallbackError(
            f"invalid draft_id UUID: {parts[2]!r}",
        ) from exc

    reject_reason: RejectionReason | None = None
    if len(parts) >= 4:
        if action != ReviewAction.REJECT:
            raise ReviewCallbackError(
                f"unexpected trailing segment for action={action.value}",
            )
        try:
            reject_reason = RejectionReason(parts[3])
        except ValueError as exc:
            raise ReviewCallbackError(
                f"unknown reject reason: {parts[3]!r}",
            ) from exc

    return ReviewCallback(
        action=action,
        draft_id=draft_id,
        reject_reason=reject_reason,
    )


# ── Inline keyboard builders ──────────────────────────────────────────


def build_primary_keyboard(
    draft_id: UUID,
    *,
    canva_edit_url: str | None = None,
) -> dict:
    """Top-level keyboard: Approva / Edit / Rifiuta.

    When ``canva_edit_url`` is set (draft was rendered via canva_renderer),
    a second row with a URL button opens the Canva editor in-place so Zero
    can tweak the design before approving.
    """
    rows: list[list[dict]] = [
        [
            {
                "text": "✅ Approva",
                "callback_data": encode_callback(
                    ReviewAction.APPROVE, draft_id,
                ),
            },
            {
                "text": "✏️ Edit",
                "callback_data": encode_callback(
                    ReviewAction.EDIT, draft_id,
                ),
            },
            {
                "text": "❌ Rifiuta",
                "callback_data": encode_callback(
                    ReviewAction.REJECT, draft_id,
                ),
            },
        ]
    ]
    if canva_edit_url:
        rows.append([
            {
                "text": "🎨 Apri in Canva",
                "url": canva_edit_url,
            },
        ])
    return {"inline_keyboard": rows}


def build_reject_reason_keyboard(draft_id: UUID) -> dict:
    """Second-step keyboard shown after user clicks ❌ Rifiuta."""
    rows = [
        [
            {
                "text": "🎭 Tono",
                "callback_data": encode_callback(
                    ReviewAction.REJECT, draft_id, RejectionReason.TONE,
                ),
            },
            {
                "text": "📚 Fatto errato",
                "callback_data": encode_callback(
                    ReviewAction.REJECT, draft_id, RejectionReason.FACT,
                ),
            },
        ],
        [
            {
                "text": "🖼️ Visual",
                "callback_data": encode_callback(
                    ReviewAction.REJECT, draft_id, RejectionReason.VISUAL,
                ),
            },
            {
                "text": "🎣 Clickbait",
                "callback_data": encode_callback(
                    ReviewAction.REJECT, draft_id, RejectionReason.CLICKBAIT,
                ),
            },
        ],
        [
            {
                "text": "❔ Altro",
                "callback_data": encode_callback(
                    ReviewAction.REJECT, draft_id, RejectionReason.OTHER,
                ),
            },
        ],
    ]
    return {"inline_keyboard": rows}


# ── helpers ──────────────────────────────────────────────────────────


def _escape_html(value: str) -> str:
    if value is None:
        return ""
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
