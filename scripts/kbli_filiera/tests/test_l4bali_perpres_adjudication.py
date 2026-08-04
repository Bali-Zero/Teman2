"""Guilt and innocence on the withdrawal of the `CHIUSO_PMA_NO_BESAR` inference.

The cure under test rewrites a CLIENT-FACING verdict on 39 live pages, so the
corpus is built around the two ways it could do harm:

  - it could KEEP a false closure (the seven genuinely reserved codes must stay
    closed, but never again on the OSS-scale inference);
  - it could OPEN something that is genuinely blocked (a code sitting in the
    moratorium tiers must not become "registrable" merely because the ownership
    bar was withdrawn — the two questions are independent and answering one must
    not silently answer the other).

The third failure mode is scope: a code some later pass has re-decided must be
REFUSED by name, never quietly overwritten.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_FILIERA_DIR = str(Path(__file__).resolve().parents[1])
if _FILIERA_DIR not in sys.path:
    sys.path.insert(0, _FILIERA_DIR)

from cure_l4bali_perpres_adjudication import (  # noqa: E402
    ADJUDICATION,
    EXPECTED_CURRENT_STATUS,
    HIGH_RISK,
    decide,
    pma_fingerprint,
    plan,
    risk_tiers,
)

_CLOSED = {"l4_bali": {"status": EXPECTED_CURRENT_STATUS, "reason": "OSS has no Usaha Besar scale row"}}


def _record(code: str, tiers: list[str] | None = None, status: str = EXPECTED_CURRENT_STATUS) -> dict:
    return {
        "kode_kbli_2025": code,
        "pma_status": "TERBUKA",
        "pma_max_asing": 100,
        "per_skala": [{"skala_usaha": ["Mikro"], "kategori_risiko": t} for t in (tiers or [])],
        "l4_bali": {"status": status, "reason": "OSS has no Usaha Besar scale row -> reserved for UMKM"},
    }


# ----------------------------------------------------------------- guilt


def test_a_reserved_code_stays_closed_but_loses_the_inference():
    """The seven are genuinely allocated to Koperasi/UMKM, so the OUTCOME is
    right and must not move. What must move is the REASON: the page currently
    asserts that the absence of a licensing row bars foreign ownership, which is
    what Permeninves/BKPM 5/2025 Pasal 26(1) inverts."""
    status, reason = decide("RESERVED", _record("96220", ["Rendah"]), "Lampiran II p.16 entry 57")
    assert status == EXPECTED_CURRENT_STATUS
    assert "Lampiran II" in reason
    assert "Usaha Besar" not in reason
    assert "scale row" not in reason


def test_a_partial_reservation_becomes_scope_dependent_not_closed():
    """Pasal 5(5) scopes a reservation to the wording in the Bidang Usaha column.
    `55209` is reserved as *Guest House*; glamping and hostels under the same code
    are not. Publishing the whole code as closed asserts what the annex denies."""
    status, reason = decide("PARTIAL", _record("55209", ["Menengah Rendah"]), "sub-row Guest House")
    assert status == "BLOCCATO_DIPENDE_SCOPE"
    assert "Pasal 5(5)" in reason


def test_an_unrestricted_low_tier_code_is_blocked_by_the_moratorium_not_by_ownership():
    """THE failure this corpus exists for. Withdrawing the ownership bar must not
    turn a moratorium-blocked code into a registrable one: the badge stays red,
    and the reason changes from a false one to a true one."""
    status, reason = decide("NONE", _record("86995", ["Menengah Rendah"]), "")
    assert status == "CHIUSO_MORATORIA_BALI"
    assert "NOT closed to foreign ownership" in reason
    assert "B.27.000/642/PM/DPMPTSP" in reason


def test_a_code_with_no_licensing_rows_says_so_instead_of_guessing():
    """These 17 are why the bad inference was tempting: we hold nothing about
    them. 'Not classifiable — verify' is the honest verdict and a strict
    improvement on a closure derived from that same absence."""
    status, reason = decide("NONE", _record("93122"), "")
    assert status == "NON_CLASSIFICABILE"
    assert "no licensing rows" in reason
    assert "Pasal 26(1)" in reason


def test_a_requirement_is_reported_as_satisfiable_not_as_a_bar():
    status, reason = decide("REQUIREMENT", _record("73300", ["Rendah"]), "Permenkes hygiene standard")
    assert status == "CHIUSO_MORATORIA_BALI"
    assert "a PT PMA can satisfy it" in reason
    assert "Permenkes hygiene standard" in reason


# ------------------------------------------------------------- innocence


def test_a_high_tier_code_is_not_swept_into_the_moratorium():
    """Measured 0 of 39 today, and the branch stays anyway: an empty bucket that
    is still computed will speak when the licensing rows arrive, whereas a
    deleted one turns the same case into a silent misclassification."""
    status, reason = decide("NONE", _record("99999", ["Menengah Tinggi"]), "")
    assert status == "APERTO_BALI_RISCHIO_ALTO"
    assert "survives the Bali PMA moratorium" in reason


def test_a_code_already_re_decided_elsewhere_is_refused_by_name():
    """Scope discipline. If a later pass has moved a code off this verdict, this
    cure has no business moving it back — and a silent skip would read as 'there
    was nothing to do'."""
    adjudication = {"rows": [{"code": "55203", "verdict": "RESERVED", "instrument": "x"}]}
    changes, refusals = plan([_record("55203", ["Rendah"], status="TERTUTUP")], adjudication)
    assert changes == []
    assert refusals and refusals[0]["code"] == "55203"
    assert "TERTUTUP" in refusals[0]["why"]


def test_a_code_missing_from_canonical_is_refused_not_invented():
    adjudication = {"rows": [{"code": "00000", "verdict": "NONE", "instrument": ""}]}
    changes, refusals = plan([_record("55203", ["Rendah"])], adjudication)
    assert changes == [] and refusals[0]["why"] == "not in canonical"


def test_the_national_ownership_fields_are_never_part_of_a_change():
    """This cure moves the BALI verdict layer only. `pma_status` /
    `pma_max_asing` / `pma_kondisi` are the national ownership answer and belong
    to a different instrument; the writer aborts if the fingerprint moves."""
    records = [_record("96220", ["Rendah"]), _record("93122")]
    before = pma_fingerprint(records)
    changes, _ = plan(records, json.loads(ADJUDICATION.read_text()))
    for change in changes:
        assert set(change) == {"code", "verdict", "from", "to", "reason", "blocked", "confidence"}
    assert pma_fingerprint(records) == before


# -------------------------------------------------------------- tripwires


def test_the_high_risk_set_agrees_with_the_pass_it_amends():
    """A set copied into two files is how this dataset earned its scars. This
    cure amends one branch of `resolve_kbli_l4_needs_review.py`; the tier
    vocabulary must stay the SAME in both, or the two will disagree about which
    codes the moratorium reaches."""
    root = Path(__file__).resolve().parents[2]
    source = (root / "resolve_kbli_l4_needs_review.py").read_text()
    for tier in HIGH_RISK:
        assert f'"{tier}"' in source, tier
    assert 'HIGH_RISK = {"Menengah Tinggi", "Tinggi"}' in source


def test_risk_tiers_reads_every_scale_not_only_besar():
    """The declared extension, pinned. These codes have NO Besar row — that
    absence is the misread fact — so the tier must come from the rows that do
    exist. A `besar`-only reader would return nothing for all 39 and send every
    one of them to NON_CLASSIFICABILE."""
    record = {"per_skala": [{"skala_usaha": ["Mikro", "Kecil"], "kategori_risiko": "Rendah"}]}
    assert risk_tiers(record) == {"Rendah"}


def test_the_adjudication_file_covers_exactly_the_thirty_nine():
    adjudication = json.loads(ADJUDICATION.read_text())
    codes = [row["code"] for row in adjudication["rows"]]
    assert len(codes) == 39 and len(set(codes)) == 39
    assert {row["verdict"] for row in adjudication["rows"]} <= {
        "RESERVED", "PARTIAL", "REQUIREMENT", "PARTNERSHIP", "NONE",
    }


def test_the_adjudication_file_declares_the_crosswalk_has_no_legal_force():
    """Every 2025-numbered verdict in that file runs through the BPS conversion
    table. If that limit ever stops being stated, a reader will take a statistical
    artefact for a citation."""
    adjudication = json.loads(ADJUDICATION.read_text())
    assert "no legal force" in adjudication["_declared_limit"]
