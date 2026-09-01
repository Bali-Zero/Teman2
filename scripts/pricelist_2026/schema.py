"""JSON schema validator for the 2026 Bali Zero price list.

Stdlib only. Returns a `ValidationResult` with .ok and .errors.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# Single source of truth for the digits the CLIENT-FACING price list shows.
#
# This is deliberately NOT `settings.SUPPORT_WHATSAPP`
# (apps/backend-rag/backend/app/core/config.py). They are different things:
# SUPPORT_WHATSAPP is the Meta-verified number the BOT RECEIVES on — its
# inbound identity, which no human answers — while these digits are the line
# a client is invited to write to. On 2026-08-31 a fix for a real defect
# resolved the two toward SUPPORT_WHATSAPP and put the bot's inbound number
# on the price list; the owner reversed it on 2026-09-01. The lead-capture and
# document surfaces (the IT/ID notification templates, the lead-capture
# deeplink, the welcome-practice and welcome-email services, the Canva renderer,
# the rendered price list, the whole frontend) already used these digits —
# among those, this sheet was the only dissenter. A separate set of email
# footers and the chat CTA still carry the bot's inbound number; that is
# ledgered as an owner decision, not silently corrected here.
#
# `whatsapp` (human-readable) and `wa_link` (wa.me href) are both derived
# from this one string below so they cannot disagree — that was the 2026-08-31
# defect: a hand-typed duplication let `wa_link` drift to different digits
# while `whatsapp` was edited (docs/pricing/Bali_Zero_Price_List_2026.md).
# Keep them derived; never hand-edit either half, here or in the sheet.
_CANONICAL_WHATSAPP_DIGITS = "628213454721"

CANONICAL_CONTACT = {
    "email": "zero@balizero.com",
    "whatsapp": (
        f"+{_CANONICAL_WHATSAPP_DIGITS[:2]} {_CANONICAL_WHATSAPP_DIGITS[2:5]} "
        f"{_CANONICAL_WHATSAPP_DIGITS[5:9]} {_CANONICAL_WHATSAPP_DIGITS[9:]}"
    ),
    "wa_link": f"https://wa.me/{_CANONICAL_WHATSAPP_DIGITS}",
    "location": "Kerobokan, Bali, Indonesia",
    "website": "balizero.com",
}

REQUIRED_TOP_LEVEL = ["version", "effective_date", "metadata", "services"]
REQUIRED_METADATA = ["currency", "contact", "last_updated"]
REQUIRED_CONTACT = list(CANONICAL_CONTACT.keys())
REQUIRED_SERVICE_FIELDS = [
    "name", "price", "tier_range", "duration", "validity",
    "notes", "description_en", "icon_id",
]


@dataclass
class ValidationResult:
    ok: bool = True
    errors: list[str] = field(default_factory=list)

    def fail(self, msg: str) -> None:
        self.ok = False
        self.errors.append(msg)


def validate(data: dict[str, Any]) -> ValidationResult:
    result = ValidationResult()

    for key in REQUIRED_TOP_LEVEL:
        if key not in data:
            result.fail(f"top-level: missing '{key}'")

    metadata = data.get("metadata", {})
    for key in REQUIRED_METADATA:
        if key not in metadata:
            result.fail(f"metadata: missing '{key}'")

    contact = metadata.get("contact", {})
    for key, expected in CANONICAL_CONTACT.items():
        actual = contact.get(key)
        if actual is None:
            result.fail(f"metadata.contact: missing '{key}'")
        elif actual != expected:
            result.fail(
                f"metadata.contact.{key} mismatch: expected '{expected}', got '{actual}'"
            )

    services = data.get("services", {})
    for category, entries in services.items():
        # tax_accounting has ONE extra level of nesting (sub-blocks)
        if category == "tax_accounting":
            for subblock, subentries in entries.items():
                for name, svc in subentries.items():
                    _validate_service(result, f"{category}.{subblock}.{name}", svc)
        else:
            for name, svc in entries.items():
                _validate_service(result, f"{category}.{name}", svc)

    return result


def _validate_service(result: ValidationResult, path: str, svc: dict) -> None:
    for field_name in REQUIRED_SERVICE_FIELDS:
        if field_name not in svc:
            result.fail(f"{path}: missing field '{field_name}'")

    price = svc.get("price", "")
    tier = svc.get("tier_range")

    has_price = bool(price and price.strip())
    has_tier = tier is not None and isinstance(tier, list) and len(tier) == 2

    if not has_price and not has_tier:
        result.fail(f"{path}: must have price or tier_range")
    if has_price and has_tier:
        result.fail(f"{path}: must have price or tier_range, not both")

    if tier is not None:
        if not isinstance(tier, list) or len(tier) != 2:
            result.fail(f"{path}: tier_range must be a list of exactly 2 strings")
        elif not all(isinstance(x, str) for x in tier):
            result.fail(f"{path}: tier_range entries must be strings")
