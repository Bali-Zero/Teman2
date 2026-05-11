"""JSON schema validator for the 2026 Bali Zero price list.

Stdlib only. Returns a `ValidationResult` with .ok and .errors.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


CANONICAL_CONTACT = {
    "email": "zero@balizero.com",
    "whatsapp": "+62 821 31 07 363",
    "wa_link": "https://wa.me/628213107363",
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
