"""Pins `client_admitted_permit` — THE ONE admission predicate (spec §1/§7 of
`docs/specs/2026-09-02-kbli-kg-licensing-class-cure-spec.md`) — against a
verbatim reimplementation of the router's OLD inline gate, so the extraction
in `kbli_requires_kind.py` is proven to change nothing about what the router
serves a client.

`_old_inline_admission_predicate` below is copied, not adapted, from
`apps/backend-rag/backend/app/routers/kbli_notebook.py`'s `licenses_raw` loop
as it stood BEFORE this PR:

    kind = classify_requires_target(lic["target_entity_type"])
    if kind == "license":
        kind = permit_name_verdict(lic["entity_id"], lic["name"])
        if kind == "permit":
            kind = "license"
    if kind != "license":
        related_requirements.setdefault(kind, []).append(lic["name"])
        continue
    licenses.append(...)

— i.e. the boolean question "does this REQUIRES target reach `licenses[]`" is
`kind == "license"` after that two-stage gate. It is kept here ONLY to prove
parity; it must never be imported or reused as a second spelling of the
predicate anywhere else (that duplication is exactly what this PR removes).
"""

from __future__ import annotations

import pytest

from backend.services.kbli_requires_kind import (
    classify_requires_target,
    client_admitted_permit,
    permit_name_verdict,
)


def _old_inline_admission_predicate(
    entity_id: str | None, entity_type: str | None, name: str | None
) -> bool:
    kind = classify_requires_target(entity_type)
    if kind == "license":
        kind = permit_name_verdict(entity_id, name)
        if kind == "permit":
            kind = "license"
    return kind == "license"


# (entity_id, entity_type, name, expected) — six-plus fixtures spanning every
# branch of the two-stage gate, each admitted verdict re-derived independently
# rather than copied from the classifier's own docstrings.
PARITY_FIXTURES: list[tuple[str, str, str, bool]] = [
    # A real, named permit: permit-typed AND a named permit.
    ("perizinan:384f5445cb38", "perizinan", "NIB dan Sertifikat Standar", True),
    ("license:nib", "license", "NIB", True),
    # Type alone says non-permit (a cost) — never reaches the name stage.
    ("biaya:x", "biaya", "10 Billion IDR", False),
    # Permit-typed, but the graph's own id admits ignorance.
    ("izin_usaha_tidak_diketahui", "izin_usaha", "Izin Usaha", False),
    # Permit-typed, id carries the `kewajiban` (obligation) token.
    ("x_kewajiban_y", "perizinan", "Laporan 6 Bulan", False),
    # Permit-typed, name is an enumerated category label.
    ("izin:generic", "izin_usaha", "Izin Usaha", False),
    # Permit-typed, name opens with an enumerated obligation verb.
    ("x", "perizinan", "Melaporkan kegiatan usahanya secara periodik", False),
    # Two of the three §2.1 placeholders: already demoted by an EXACT
    # `_NOT_A_PERMIT_LABELS` match (F5).
    ("status_perizinan_pending", "izin_usaha", "PENDING_REGULATION", False),
    ("izin_usaha_pending", "izin_usaha", "Status Perizinan: PENDING_REGULATION", False),
    # The THIRD §2.1 placeholder: its name ("Status Perizinan
    # PENDING_REGULATION", no colon) does NOT match `_NOT_A_PERMIT_LABELS`'s
    # exact string and survives as a permit today — measured on PROD in this
    # PR. `kg_stray_admission` catches it by ID, not by name; this fixture
    # pins that the ONE predicate (not a demotion this PR invents) is what
    # both the router and the detector see.
    (
        "izin_usaha_status_pending_regulation",
        "izin_usaha",
        "Status Perizinan PENDING_REGULATION",
        True,
    ),
    # `permit_type` left `PERMIT_TYPES` 2026-09-19 — type alone excludes it.
    ("permit_type:kitas", "permit_type", "KITAS", False),
]


@pytest.mark.parametrize("entity_id,entity_type,name,expected", PARITY_FIXTURES)
def test_client_admitted_permit_matches_the_old_inline_predicate(
    entity_id: str, entity_type: str, name: str, expected: bool
) -> None:
    assert client_admitted_permit(entity_id, entity_type, name) is expected
    assert _old_inline_admission_predicate(entity_id, entity_type, name) is expected


def test_extraction_changes_nothing_innocence():
    """The extraction is innocence-tested as a WHOLE, not just fixture by
    fixture: run every fixture through both spellings and require identical
    verdicts, so a future edit to one without the other is caught even if a
    fixture above were ever deleted."""
    for entity_id, entity_type, name, _expected in PARITY_FIXTURES:
        assert client_admitted_permit(entity_id, entity_type, name) == (
            _old_inline_admission_predicate(entity_id, entity_type, name)
        )
