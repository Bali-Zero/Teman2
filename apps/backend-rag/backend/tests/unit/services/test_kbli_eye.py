"""Tests for KBLIEye — the deterministic KBLI audit matrix.

This service shipped with ZERO direct tests (only downstream mocks), which is
how two defects survived in it:

1. `max_foreign_ownership` was `100 if TERBUKA else 0` — a BINARY derived from a
   TERNARY status. `TERBATAS` ("limited") spans 0%, 49%, 100% and a
   non-percentage "special" regime, so 9 of the 10 TERBATAS codes were served a
   figure the dataset itself contradicts — 8 of them in the direction that
   DENIES a lawful foreign stake.
2. `is_umkm_reserved` was `not is_open_pma` — asserting "reserved for micro and
   small enterprise" on all 71 non-TERBUKA codes, while the data names such a
   reservation on exactly 2. A code can be closed for defence, environment,
   culture or cabotage; inferring UMKM from closure is plausible-but-unfounded.

Both are the same disease: deriving a CAUSE or a LIMIT from a flag that does not
carry it. The dataset already holds the adjudicated answer per code
(`pma_max_asing` + `pma_official_basis` citing the Perpres 10/2021 lampiran);
the code threw it away.

Every guilt test below is paired with an innocence test, so a future "tidy-up"
back to the binary fails loudly instead of silently.
"""

from pathlib import Path

import pytest

from backend.services.kbli_eye import KBLIEye

# apps/backend-rag/backend/tests/unit/services/ -> repo root
REPO_ROOT = Path(__file__).resolve().parents[6]
DATASET = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"


@pytest.fixture(scope="module")
def eye() -> KBLIEye:
    # Deliberately NOT skipped when absent: the dataset is tracked in git, so a
    # missing file is a real failure, not a reason to pass vacuously.
    assert DATASET.exists(), f"canonical KBLI dataset missing at {DATASET}"
    instance = KBLIEye(db_path=str(DATASET))
    assert instance.data, "KBLIEye loaded an empty dataset"
    return instance


@pytest.fixture(scope="module")
def records(eye: KBLIEye) -> list[dict]:
    return eye.data


# --------------------------------------------------------------------------
# GUILT — the defect, on real records
# --------------------------------------------------------------------------


def test_sea_cabotage_is_limited_not_rejected(eye: KBLIEye) -> None:
    """50111 allows 49% foreign. The binary called it REJECTED."""
    out = eye.get_decision("50111", is_pma=True)
    assert out["pma_logic"]["max_foreign_ownership"] == 49
    assert out["audit"]["state"] == "WARNING"
    assert out["audit"]["reason_code"] == "PERPRES_10_2021_FOREIGN_CAP"


def test_travel_agency_terbatas_carries_full_cap(eye: KBLIEye) -> None:
    """79110 is TERBATAS but the adjudicated cap is 100% — never 0."""
    out = eye.get_decision("79110", is_pma=True)
    assert out["pma_logic"]["max_foreign_ownership"] == 100
    assert out["audit"]["state"] != "REJECTED"


def test_special_regime_asserts_no_percentage(eye: KBLIEye) -> None:
    """47221's lampiran row carries a condition, not a %. None, not 0."""
    out = eye.get_decision("47221", is_pma=True)
    assert out["pma_logic"]["max_foreign_ownership"] is None
    assert out["audit"]["state"] == "WARNING"


def test_umkm_reservation_is_not_inferred_from_closure(eye: KBLIEye, records: list[dict]) -> None:
    """A code closed to foreigners is not thereby 'reserved for UMKM'."""
    closed_without_marker = next(
        r
        for r in records
        if r.get("pma_status") == "TERTUTUP"
        and not (r.get("pma_kondisi") or "")
        and "DIALOKASIKAN" not in (r.get("pma_official_basis") or "")
    )
    out = eye.get_decision(closed_without_marker["kode_kbli_2025"], is_pma=True)
    assert out["pma_logic"]["is_umkm_reserved"] is None, "closure must not imply UMKM reservation"


def test_partnership_requirement_is_not_a_reservation(eye: KBLIEye) -> None:
    """'Kemitraan dengan UMKM/Koperasi' is a partnership duty, not a reservation.

    47221 names UMKM in its condition but its lampiran basis does NOT allocate
    the activity to K-UMKM — a bare substring match on 'UMKM' would over-match
    here (scar family #3).
    """
    out = eye.get_decision("47221", is_pma=True)
    assert out["pma_logic"]["is_umkm_reserved"] is None
    assert "UMKM" in (out["pma_logic"]["pma_condition"] or ""), "condition still surfaced verbatim"


# --------------------------------------------------------------------------
# INNOCENCE — what must NOT change
# --------------------------------------------------------------------------


def test_open_code_unchanged(eye: KBLIEye, records: list[dict]) -> None:
    # Derived from the catalogue, never hardcoded: a guessed code silently
    # resolves to CODE_NOT_FOUND and the assertions below stop testing anything.
    plain_open = next(
        r
        for r in records
        if r.get("pma_status") == "TERBUKA"
        and r["kode_kbli_2025"] not in KBLIEye.BALI_GOV_LETTER_CODES
        and r["kode_kbli_2025"] not in KBLIEye.BALI_MORATORIUM_RETAIL
    )
    out = eye.get_decision(plain_open["kode_kbli_2025"], is_pma=True, location="Jakarta")
    assert out["pma_logic"]["max_foreign_ownership"] == 100
    assert out["pma_logic"]["is_umkm_reserved"] is False
    assert out["audit"]["state"] == "APPROVED"


def test_closed_code_still_rejected(eye: KBLIEye, records: list[dict]) -> None:
    closed = next(r for r in records if r.get("pma_status") == "TERTUTUP")
    out = eye.get_decision(closed["kode_kbli_2025"], is_pma=True)
    assert out["pma_logic"]["max_foreign_ownership"] == 0
    assert out["audit"]["state"] == "REJECTED"
    assert out["audit"]["reason_code"] == "PERPRES_10_2021_RESERVATION"


def test_named_umkm_reservation_still_true(eye: KBLIEye) -> None:
    """The 2 codes the lampiran genuinely allocates to K-UMKM keep the flag."""
    assert eye.get_decision("47111", is_pma=True)["pma_logic"]["is_umkm_reserved"] is True
    assert eye.get_decision("47222", is_pma=True)["pma_logic"]["is_umkm_reserved"] is True


def test_bali_gov_letter_branch_survives(eye: KBLIEye) -> None:
    """68111 is TERBUKA — it must still reach the Bali letter branch."""
    out = eye.get_decision("68111", is_pma=True, location="Bali")
    assert out["audit"]["state"] == "WARNING"
    assert out["audit"]["reason_code"] == "BALI_GOV_LETTER_9_CODES"


def test_non_pma_applicant_is_not_rejected_for_a_foreign_cap(eye: KBLIEye) -> None:
    """A domestic (PMDN) applicant is unaffected by the foreign-ownership cap."""
    out = eye.get_decision("50111", is_pma=False, location="Jakarta")
    assert out["audit"]["state"] != "REJECTED"


def test_unknown_code_still_errors(eye: KBLIEye) -> None:
    assert eye.get_decision("00000")["reason_code"] == "CODE_NOT_FOUND"


# --------------------------------------------------------------------------
# POPULATION PINS — measured on the whole catalogue, not on samples
# --------------------------------------------------------------------------


def test_cap_never_contradicts_the_dataset(records: list[dict]) -> None:
    """Every numeric cap we serve equals the adjudicated figure on the record."""
    mismatches = [
        r["kode_kbli_2025"]
        for r in records
        if isinstance(r.get("pma_max_asing"), int)
        and not isinstance(r.get("pma_max_asing"), bool)
        and KBLIEye._foreign_cap(r)[0] != r["pma_max_asing"]
    ]
    assert mismatches == []


def test_cap_is_always_a_percentage_or_a_declared_gap(records: list[dict]) -> None:
    for r in records:
        cap, _basis, _verified = KBLIEye._foreign_cap(r)
        assert cap is None or 0 <= cap <= 100, f"{r['kode_kbli_2025']} -> {cap!r}"


def test_umkm_reserved_is_tri_state_and_rare(records: list[dict]) -> None:
    """11 reserved / 1459 open / 89 undetermined — NOT 71 blanket True.

    The split was 1488/69 until 2026-08-02, when the Perpres 49/2021 Lampiran III
    cure moved 20 codes out of TERBUKA (arms and ammunition, military vehicles,
    commercial air transport, the ferry family, couriers, umrah travel). They
    became `None` — undetermined — which is the honest verdict: leaving TERBUKA
    says nothing at all about a K-UMKM reservation.

    2 -> 11 on 2026-08-06: the Lampiran II re-adjudication. Nine codes are now
    named as ALLOCATED to Koperasi/UMKM, so `True` here is a read of the annex
    and not a guess. `None` does not move — the nine came out of the `False`
    population, which is the shape that says the reader changed its mind about
    codes it had positively examined, rather than filling silence.
    """
    verdicts = [KBLIEye._umkm_reserved(r) for r in records]
    assert verdicts.count(True) == 11
    assert verdicts.count(False) == 1459
    assert verdicts.count(None) == 89
    # The counts above are population pins and will move again with the data.
    # This one is the invariant underneath them, and it must not: `False` means
    # exactly "TERBUKA and not named as reserved" — never a guess from silence.
    named = {r["kode_kbli_2025"] for r in records if KBLIEye._umkm_reserved(r) is True}
    terbuka = {r["kode_kbli_2025"] for r in records if r.get("pma_status") == "TERBUKA"}
    assert verdicts.count(False) == len(terbuka - named)


def test_every_umkm_true_is_named_by_the_data(records: list[dict]) -> None:
    """No record may be flagged 'reserved' without the data saying so."""
    for r in records:
        if KBLIEye._umkm_reserved(r) is True:
            named = (r.get("pma_kondisi") or "").strip() in KBLIEye.UMKM_RESERVED_KONDISI
            allocated = KBLIEye.UMKM_ALLOCATION_MARKER in (r.get("pma_official_basis") or "")
            assert named or allocated, f"{r['kode_kbli_2025']} flagged with no basis"


def test_the_cure_only_ever_shrinks_the_rejected_bucket(records: list[dict]) -> None:
    """Blast radius, measured: 27 codes leave the REJECTED bucket, none enters.

    Old rule: `is_pma and pma_status != TERBUKA` -> REJECTED.
    New rule: REJECTED only where the adjudicated cap is 0%.

    Was named `test_exactly_nine_...` while the counts were 71 / 62 / 9. On
    2026-08-02 the Perpres 49/2021 Lampiran III cure moved 20 codes out of
    TERBUKA: 18 of them at a 49% cap (they join the codes that stop being
    wrongly rejected, 9 -> 27) and 2 at 0% (16221, 79122 — they join
    `new_rejected`, 62 -> 64). The name was renamed rather than left lying:
    a test whose name asserts a number it no longer checks is worse than one
    with no name at all.
    """
    old_rejected = {r["kode_kbli_2025"] for r in records if r.get("pma_status") != "TERBUKA"}
    new_rejected = {
        r["kode_kbli_2025"] for r in records if KBLIEye._foreign_cap(r)[0] == 0
    }
    # 2026-08-06: both grew by the same nine (91->100, 64->73) because the
    # Lampiran II re-adjudication moves a code out of TERBUKA *and* sets its cap
    # to 0 in the same write. The DIFFERENCE is unchanged at 27, which is the
    # real content of this test's name: nothing new became wrongly-rejected.
    assert len(old_rejected) == 100
    assert len(new_rejected) == 73
    assert len(old_rejected - new_rejected) == 27
    # The counts above move with the data; THIS is the property that must not.
    assert new_rejected <= old_rejected, "the cure must never REJECT something new"


def test_missing_cap_falls_back_to_status_not_to_zero(records: list[dict]) -> None:
    """01122 (TERBUKA) carries no cap field — it must not read as 0%."""
    no_cap = [r for r in records if "pma_max_asing" not in r]
    assert len(no_cap) == 1
    cap, basis, verified = KBLIEye._foreign_cap(no_cap[0])
    assert cap == 100
    assert verified is False, "a status-derived figure is not an adjudicated one"
    assert basis is not None


# --------------------------------------------------------------------------
# TYPE TRAPS
# --------------------------------------------------------------------------


def test_boolean_cap_is_not_read_as_a_percentage() -> None:
    """`bool` subclasses `int` in Python: True must not become 1%."""
    cap, _basis, _verified = KBLIEye._foreign_cap(
        {"pma_max_asing": True, "pma_status": "TERBUKA"}
    )
    assert cap == 100, "a boolean must fall through to the status, not read as 1"


def test_numeric_string_cap_is_accepted() -> None:
    cap, _basis, _verified = KBLIEye._foreign_cap({"pma_max_asing": " 67 ", "pma_status": "TERBATAS"})
    assert cap == 67


def test_unloaded_database_reports_itself(tmp_path: Path) -> None:
    """The silent-death path: absent dataset must still answer honestly."""
    instance = KBLIEye(db_path=str(tmp_path / "nope.json"))
    assert instance.data == []
    assert instance.get_decision("62011")["reason_code"] == "DATABASE_NOT_LOADED"
