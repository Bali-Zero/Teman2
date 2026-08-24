"""Guilt/innocence tests for ``ConsultantAssignmentEvent`` (frozen contract
C3, ``docs/plans/2026-08-24-visa-oracle-live/contracts/FROZEN.md``).

V3/unit-1 deliverable. Written red-first per the assembly-line procedure
(``docs/factory/ASSEMBLY-LINE.md``): every test in this file failed with
``ModuleNotFoundError`` before ``consultant_assignment.py`` existed, and
each PII/invariant assertion was verified to fail on a naively-shaped model
(a version with a plain ``str`` ``notes`` field, and no origin_screen enum)
before the frozen-shape version made it pass.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from backend.services.visa_engine.consultant_assignment import (
    ConsultantAssignmentEvent,
    EventLocale,
    OriginScreen,
    ServiceTier,
)

UTC_NOW = datetime(2026, 8, 24, 12, 0, 0, tzinfo=timezone.utc)


def _minimal_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "evaluation_id": uuid4(),
        "requested_at": UTC_NOW,
        "origin_screen": OriginScreen.WIZARD,
        "tier": ServiceTier.T1,
        "locale": EventLocale.EN,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# The pre-purchase / anonymous-visitor case — the whole point of the event
# ---------------------------------------------------------------------------


class TestEmittableBeforeBuying:
    def test_emittable_with_client_id_and_product_version_id_both_null(self) -> None:
        """The anonymous, pre-verdict invocation — "invokable before buying"
        (MANDATE.md §1) is not a degraded case, it is the primary one."""

        event = ConsultantAssignmentEvent(**_minimal_kwargs())
        assert event.client_id is None
        assert event.product_version_id is None

    def test_client_id_and_product_version_id_populate_once_known(self) -> None:
        client_id = uuid4()
        product_version_id = uuid4()
        event = ConsultantAssignmentEvent(
            **_minimal_kwargs(
                client_id=client_id,
                product_version_id=product_version_id,
                origin_screen=OriginScreen.CHECKOUT,
                tier=ServiceTier.T2,
            )
        )
        assert event.client_id == client_id
        assert event.product_version_id == product_version_id


# ---------------------------------------------------------------------------
# All four screens (C3: "present on every screen — wizard, verdict,
# checkout, portal")
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "screen",
    [OriginScreen.WIZARD, OriginScreen.VERDICT, OriginScreen.CHECKOUT, OriginScreen.PORTAL],
)
def test_every_mandated_origin_screen_is_constructible(screen: OriginScreen) -> None:
    event = ConsultantAssignmentEvent(**_minimal_kwargs(origin_screen=screen))
    assert event.origin_screen is screen


def test_origin_screen_is_closed_to_a_fifth_value() -> None:
    """The enum is the enforcement mechanism for "present on every screen":
    a fifth surface must be a deliberate enum edit, not a string typo."""

    with pytest.raises(ValidationError):
        ConsultantAssignmentEvent(**_minimal_kwargs(origin_screen="checkout_confirmation"))


# ---------------------------------------------------------------------------
# tier=T3 (and T2) implies consultant_required — MANDATE.md §1
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("tier", "expected"),
    [(ServiceTier.T1, False), (ServiceTier.T2, True), (ServiceTier.T3, True)],
)
def test_consultant_required_follows_tier(tier: ServiceTier, expected: bool) -> None:
    event = ConsultantAssignmentEvent(**_minimal_kwargs(tier=tier))
    assert event.consultant_required is expected


def test_consultant_required_is_derived_never_serialized() -> None:
    """Not one of C3's seven wire fields — must not leak into the payload
    a CRM consumer actually receives, or the frozen shape has silently
    grown an eighth field."""

    event = ConsultantAssignmentEvent(**_minimal_kwargs(tier=ServiceTier.T3))
    dumped = event.model_dump()
    assert "consultant_required" not in dumped
    assert set(dumped.keys()) == {
        "evaluation_id",
        "client_id",
        "requested_at",
        "origin_screen",
        "tier",
        "product_version_id",
        "locale",
    }


# ---------------------------------------------------------------------------
# Law 2 — refuses to serialize if any PII-shaped field is present
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "pii_field",
    [
        "name",
        "full_name",
        "applicant_name",
        "phone",
        "phone_number",
        "whatsapp",
        "email",
        "passport",
        "passport_number",
        "ktp",
        "nik",
        "notes",
        "message",
        "contact",
    ],
)
def test_refuses_pii_shaped_field_by_name(pii_field: str) -> None:
    with pytest.raises(ValidationError):
        ConsultantAssignmentEvent(**_minimal_kwargs(**{pii_field: "irrelevant value"}))


def test_pii_guard_error_names_law_2_not_a_generic_pydantic_message() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ConsultantAssignmentEvent(**_minimal_kwargs(email="visitor@example.com"))
    assert "Law 2" in str(exc_info.value)


def test_arbitrary_unknown_field_still_rejected_extra_forbid() -> None:
    """Non-PII-named junk fields are still rejected — the PII name-guard is
    additive to ``extra="forbid"``, not a replacement for it."""

    with pytest.raises(ValidationError):
        ConsultantAssignmentEvent(**_minimal_kwargs(unexpected_field="x"))


def test_no_field_on_the_frozen_shape_can_hold_free_text() -> None:
    """Every field is a closed type (UUID / Enum / datetime) — there is no
    string-typed field a name, phone, or free-text note could be written
    into even if a caller tried, independent of the explicit name guard."""

    fields = ConsultantAssignmentEvent.model_fields
    assert set(fields) == {
        "evaluation_id",
        "client_id",
        "requested_at",
        "origin_screen",
        "tier",
        "product_version_id",
        "locale",
    }
    for field_name, field_info in fields.items():
        annotation = field_info.annotation
        # str is only reachable via the closed Enums (which subclass str),
        # never as a bare `str` annotation.
        assert annotation is not str, f"{field_name} is a bare str field"


# ---------------------------------------------------------------------------
# Frozen / immutable, extra-forbid — standard contract hygiene
# ---------------------------------------------------------------------------


def test_event_is_frozen() -> None:
    event = ConsultantAssignmentEvent(**_minimal_kwargs())
    with pytest.raises(ValidationError):
        event.tier = ServiceTier.T3  # type: ignore[misc]


def test_requested_at_must_be_utc() -> None:
    naive = datetime(2026, 8, 24, 12, 0, 0)
    with pytest.raises(ValidationError):
        ConsultantAssignmentEvent(**_minimal_kwargs(requested_at=naive))

    wib = timezone(timedelta(hours=8))
    with pytest.raises(ValidationError):
        ConsultantAssignmentEvent(
            **_minimal_kwargs(requested_at=datetime(2026, 8, 24, 20, 0, 0, tzinfo=wib))
        )


@pytest.mark.parametrize("locale", [EventLocale.EN, EventLocale.ID])
def test_both_locales_constructible(locale: EventLocale) -> None:
    event = ConsultantAssignmentEvent(**_minimal_kwargs(locale=locale))
    assert event.locale is locale


def test_evaluation_id_and_client_id_are_real_uuids_not_strings() -> None:
    event = ConsultantAssignmentEvent(**_minimal_kwargs(client_id=uuid4()))
    assert isinstance(event.evaluation_id, UUID)
    assert isinstance(event.client_id, UUID)
