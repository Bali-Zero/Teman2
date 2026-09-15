"""Guilt, innocence, refusal, and idempotence for the 2026 Bali applied-closure overlay.

The cure under test (`cure_l4bali_applied_closure.py`) narrows the Bali
`blocked` verdict from "every low/medium-low risk tier" (~519 codes) to the
40 KBLI-2025 codes that actually descend from the 18 KBLI-2020 business
fields the Bali Provincial Government closed to new PMA licensing in 2026.
The corpus below is built around the three ways that narrowing could do
harm:

  - it could leave a genuinely closed code (the 40, or one of W-H's held 19)
    reading as open;
  - it could touch a code the compiler has no mandate over (the excluded 19,
    a TERTUTUP code, any field on a passthrough record beyond `moratorium`);
  - it could silently accept a membership derivation that no longer matches
    the pinned `expected_2025_codes` — a refusal, never a guess.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

FILIERA_DIR = str(Path(__file__).resolve().parents[1])
if FILIERA_DIR not in sys.path:
    sys.path.insert(0, FILIERA_DIR)

import cure_l4bali_applied_closure as cure  # noqa: E402
import _hardened_cure_io as H  # noqa: E402

CureError = H.CureError

_OLD_MORATORIUM = {
    "rule": "Bali province blocks ALL Low + Medium-Low risk KBLI for PMA (island-wide, permanent)",
    "effective": "2026-05-13",
    "source": "Gubernur letter B.27.000/642/PM/DPMPTSP",
    "virtual_office": "BANNED as PMA domicile in Bali",
}


def _spec(*, eighteen=None, expected=None, excluded=None):
    eighteen = eighteen if eighteen is not None else {
        "99990": {"name": "Test Field Alpha"},
        "99991": {"name": "Test Field Beta (<6.000 m²)", "scope_qualifier": "building area under 6,000 m²"},
    }
    expected = expected if expected is not None else ["88001", "88002", "88003"]
    excluded = excluded if excluded is not None else ["88004"]
    return {
        "numbering": "KBLI 2020",
        "mapping_rule": "bps_2020_ancestors only",
        "effective": "third week of May 2026",
        "until": "until further policy",
        "approval": "with the approval of the Minister of Investment/BKPM",
        "sources": {
            "official": {
                "instrument": "Bali Provincial Government press release",
                "event": "2026-07-22",
                "published": "2026-07-24",
                "url": "https://example.test/press-release",
            },
            "code_list": {
                "source": "ANTARA Bali",
                "published": "2026-07-23",
                "url": "https://example.test/code-list",
            },
            "request_letter": {
                "id": "B.27.000/642/PM/DPMPTSP",
                "date": "2026-01-28",
                "note": "request; Lampiran: -",
            },
        },
        "eighteen": eighteen,
        "expected_2025_codes": expected,
        "excluded_codes": {"codes": excluded, "owner": "W-H (SAETTA-20260915)", "note": "fixture"},
        "moratorium": {
            "rule": "Bali closed OSS to new PMA licensing for 18 business fields (KBLI 2020 numbering), not for every low/medium-low risk activity",
            "effective": "third week of May 2026",
            "until": "until further policy",
            "source": "Bali Provincial Government press release, 24 Jul 2026",
            "source_url": "https://example.test/press-release",
            "request": "Governor letter B.27.000/642/PM/DPMPTSP (28 Jan 2026), a request covering all low/medium-low risk PMA and virtual offices",
            "virtual_office": "requested in letter B.27.000/642/PM/DPMPTSP; application not confirmed",
        },
    }


def _record(
    code: str,
    *,
    status: str = "OK_or_HIGHER_RISK",
    blocked: bool = False,
    confidence: str = "MEDIUM",
    needs_review: bool = False,
    ancestors_2020: list[str] | None = None,
    reason: str = "fixture reason",
) -> dict:
    l4: dict = {
        "status": status,
        "blocked": blocked,
        "confidence": confidence,
        "needs_review": needs_review,
        "reason": reason,
        "moratorium": dict(_OLD_MORATORIUM),
    }
    record: dict = {"kode_kbli_2025": code, "per_skala": [], "l4_bali": l4}
    if ancestors_2020 is not None:
        record["bps_2020_ancestors"] = {"codes": list(ancestors_2020)}
    return record


def _write(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _fixture_files(tmp_path: Path, records: list[dict], **spec_kwargs) -> tuple[Path, Path]:
    canonical = _write(tmp_path / "canonical.json", {"data": records})
    spec_path = _write(tmp_path / "spec.json", _spec(**spec_kwargs))
    return canonical, spec_path


def _run(canonical: Path, spec: Path, *, apply: bool = False) -> int:
    argv = ["--canonical", str(canonical), "--spec", str(spec)]
    if apply:
        argv.append("--apply")
    return cure.main(argv)


def _records(canonical: Path) -> list[dict]:
    return json.loads(canonical.read_text(encoding="utf-8"))["data"]


def _by_code(canonical: Path) -> dict[str, dict]:
    return {r["kode_kbli_2025"]: r for r in _records(canonical)}


# --------------------------------------------------------------- guilt: CHIUSO_BALI


def test_single_ancestor_on_list_is_guilty_chiuso_bali_high_confidence(tmp_path: Path) -> None:
    guilty = _record("88001", status="BLOCCATO_CLASSE_RISCHIO", blocked=True, ancestors_2020=["99990"])
    canonical, spec = _fixture_files(tmp_path, [guilty], expected=["88001"], excluded=[])

    assert _run(canonical, spec, apply=True) == 0
    l4 = _by_code(canonical)["88001"]["l4_bali"]
    assert l4["status"] == "CHIUSO_BALI"
    assert l4["blocked"] is True
    assert l4["needs_review"] is False
    assert l4["confidence"] == "HIGH"
    assert "Bali Provincial Government closed OSS" in l4["reason"]
    assert "99990" in l4["reason"]
    assert l4["closure"]["ancestors_2020"] == ["99990"]
    assert l4["closure"]["scope_qualifier"] is None
    assert "buildings under 6,000" not in l4["reason"]
    assert "merges KBLI 2020" not in l4["reason"]
    assert l4["verdict_state"] == "blocked"


def test_hotel_ancestor_gets_scope_qualifier_sentence(tmp_path: Path) -> None:
    guilty = _record("88002", ancestors_2020=["99991"])
    canonical, spec = _fixture_files(tmp_path, [guilty], expected=["88002"], excluded=[])

    assert _run(canonical, spec, apply=True) == 0
    l4 = _by_code(canonical)["88002"]["l4_bali"]
    assert l4["status"] == "CHIUSO_BALI"
    assert "buildings under 6,000 m²" in l4["reason"]
    assert l4["closure"]["scope_qualifier"] == "building area under 6,000 m²"


def test_multi_ancestor_code_gets_merge_note_and_medium_confidence(tmp_path: Path) -> None:
    guilty = _record("88003", ancestors_2020=["99990", "some-other-2020-code"])
    canonical, spec = _fixture_files(tmp_path, [guilty], expected=["88003"], excluded=[])

    assert _run(canonical, spec, apply=True) == 0
    l4 = _by_code(canonical)["88003"]["l4_bali"]
    assert l4["confidence"] == "MEDIUM"
    assert "merges KBLI 2020 activities that are not on the list" in l4["reason"]
    assert l4["closure"]["ancestors_2020"] == ["99990", "some-other-2020-code"]
    assert l4["verdict_state"] == "provisional"  # MEDIUM confidence -> not HIGH -> provisional


def test_two_matching_ancestors_are_both_named(tmp_path: Path) -> None:
    eighteen = {
        "99990": {"name": "Test Field Alpha"},
        "99992": {"name": "Test Field Gamma"},
    }
    guilty = _record("88010", ancestors_2020=["99990", "99992", "other"])
    canonical, spec = _fixture_files(tmp_path, [guilty], eighteen=eighteen, expected=["88010"], excluded=[])

    assert _run(canonical, spec, apply=True) == 0
    reason = _by_code(canonical)["88010"]["l4_bali"]["reason"]
    assert "99990 (Test Field Alpha)" in reason
    assert "99992 (Test Field Gamma)" in reason
    assert " and " in reason


# --------------------------------------------------------------- guilt: ATTENZIONE_FASCIA_BALI


def test_off_list_bloccato_classe_rischio_becomes_attenzione_open(tmp_path: Path) -> None:
    off_list = _record("88006", status="BLOCCATO_CLASSE_RISCHIO", blocked=True)
    canonical, spec = _fixture_files(tmp_path, [off_list], expected=[], excluded=[])

    assert _run(canonical, spec, apply=True) == 0
    l4 = _by_code(canonical)["88006"]["l4_bali"]
    assert l4["status"] == "ATTENZIONE_FASCIA_BALI"
    assert l4["blocked"] is False
    assert l4["needs_review"] is True
    assert "Not among the 18 business fields" in l4["reason"]
    assert l4["verdict_state"] == "provisional"


def test_off_list_chiuso_moratoria_bali_becomes_attenzione_open(tmp_path: Path) -> None:
    off_list = _record("88009", status="CHIUSO_MORATORIA_BALI", blocked=True)
    canonical, spec = _fixture_files(tmp_path, [off_list], expected=[], excluded=[])

    assert _run(canonical, spec, apply=True) == 0
    l4 = _by_code(canonical)["88009"]["l4_bali"]
    assert l4["status"] == "ATTENZIONE_FASCIA_BALI"
    assert l4["blocked"] is False


# --------------------------------------------------------------- guilt: NON_CLASSIFICABILE


def test_non_classificabile_blocked_false_status_unchanged_reason_appended(tmp_path: Path) -> None:
    rec = _record(
        "88007", status="NON_CLASSIFICABILE", blocked=True, reason="the catalogue holds no licensing rows"
    )
    canonical, spec = _fixture_files(tmp_path, [rec], expected=[], excluded=[])

    assert _run(canonical, spec, apply=True) == 0
    l4 = _by_code(canonical)["88007"]["l4_bali"]
    assert l4["status"] == "NON_CLASSIFICABILE"
    assert l4["blocked"] is False
    assert l4["reason"].startswith("the catalogue holds no licensing rows")
    assert "Not among the 18 business fields" in l4["reason"]
    assert l4["verdict_state"] == "unknown"


# --------------------------------------------------------------- innocence


def test_excluded_code_untouched_except_moratorium(tmp_path: Path) -> None:
    excluded_rec = _record("88004", status="CHIUSO_MORATORIA_BALI", blocked=True, confidence="HIGH")
    canonical, spec = _fixture_files(tmp_path, [excluded_rec], expected=[], excluded=["88004"])
    before = copy.deepcopy(excluded_rec["l4_bali"])

    assert _run(canonical, spec, apply=True) == 0
    after = _by_code(canonical)["88004"]["l4_bali"]
    before.pop("moratorium")
    after_no_mor = dict(after)
    after_no_mor.pop("moratorium")
    assert after_no_mor == before
    assert after["moratorium"] != before.get("moratorium")  # sanity: moratorium DID change on disk
    assert "2026-05-13" not in json.dumps(after["moratorium"])


def test_tertutup_untouched_except_moratorium(tmp_path: Path) -> None:
    tertutup = _record("88005", status="TERTUTUP", blocked=True, confidence="HIGH", reason="reserved basic activity")
    canonical, spec = _fixture_files(tmp_path, [tertutup], expected=[], excluded=[])
    before = copy.deepcopy(tertutup["l4_bali"])

    assert _run(canonical, spec, apply=True) == 0
    after = _by_code(canonical)["88005"]["l4_bali"]
    before.pop("moratorium")
    after_no_mor = dict(after)
    after_no_mor.pop("moratorium")
    assert after_no_mor == before
    assert after["status"] == "TERTUTUP"
    assert after["blocked"] is True


# --------------------------------------------------------------- guilt/innocence: TERTUTUP stale reason (47222)


def test_tertutup_stale_reason_with_national_tertutup_status_gets_literal_sentence(tmp_path: Path) -> None:
    # Same shape as 47222 (status TERTUPUT, the exact stale risk-tier reason)
    # but with a national pma_status of TERTUTUP — the one case where the
    # literal "closed at the national level" sentence is true.
    guilty = _record(
        "88012", status="TERTUTUP", blocked=True, confidence="HIGH", reason=cure.TERTUTUP_STALE_REASON
    )
    guilty["pma_status"] = "TERTUTUP"
    guilty["pma_max_asing"] = 0
    canonical, spec = _fixture_files(tmp_path, [guilty], expected=[], excluded=[])

    assert _run(canonical, spec, apply=True) == 0
    l4 = _by_code(canonical)["88012"]["l4_bali"]
    assert l4["reason"] == cure.TERTUTUP_NATIONAL_REASON
    assert l4["status"] == "TERTUTUP"
    assert l4["blocked"] is True
    assert "13 May 2026" not in l4["reason"]


def test_tertutup_stale_reason_with_47222_shape_gets_field_derived_reason(tmp_path: Path) -> None:
    # 47222 itself, verified 2026-09-15: l4_bali.status TERTUTUP + the exact
    # stale reason, but pma_status TERBATAS (0% via a Perpres 49/2021
    # Lampiran II cooperative/UMKM reservation) — NOT a blanket national
    # closure. The literal "TERTUTUP/0%" sentence must NOT be written here;
    # the guard has to actually read pma_status, not assume it.
    guilty = _record(
        "47222", status="TERTUTUP", blocked=True, confidence="HIGH", reason=cure.TERTUTUP_STALE_REASON
    )
    guilty["pma_status"] = "TERBATAS"
    guilty["pma_max_asing"] = 0
    guilty["pma_source"] = "Perpres 10/2021, 49/2021"
    canonical, spec = _fixture_files(tmp_path, [guilty], expected=[], excluded=[])

    assert _run(canonical, spec, apply=True) == 0
    l4 = _by_code(canonical)["47222"]["l4_bali"]
    assert l4["reason"] != cure.TERTUTUP_NATIONAL_REASON
    assert "TERTUTUP/0%" not in l4["reason"]
    assert "13 May 2026" not in l4["reason"]
    assert "TERBATAS" in l4["reason"]
    assert "Perpres 10/2021, 49/2021" in l4["reason"]
    assert l4["status"] == "TERTUTUP"  # status/blocked untouched — reason only
    assert l4["blocked"] is True


def test_tertutup_with_a_different_reason_is_untouched(tmp_path: Path) -> None:
    # Innocence: a TERTUTUP record whose reason is NOT the stale risk-tier
    # sentence (guard-over-match, scar #3 — entity match, never a substring).
    innocent = _record(
        "88013", status="TERTUTUP", blocked=True, confidence="HIGH", reason="Reserved basic activity — closed to PMA."
    )
    innocent["pma_status"] = "TERBATAS"
    canonical, spec = _fixture_files(tmp_path, [innocent], expected=[], excluded=[])
    before = copy.deepcopy(innocent["l4_bali"])

    assert _run(canonical, spec, apply=True) == 0
    after = _by_code(canonical)["88013"]["l4_bali"]
    assert after["reason"] == before["reason"]
    assert after["reason"] == "Reserved basic activity — closed to PMA."


def test_moratorium_rewritten_on_every_record_no_stale_language(tmp_path: Path) -> None:
    records = [
        _record("88001", status="BLOCCATO_CLASSE_RISCHIO", blocked=True, ancestors_2020=["99990"]),
        _record("88004", status="CHIUSO_MORATORIA_BALI", blocked=True),
        _record("88005", status="TERTUTUP", blocked=True),
        _record("88006", status="BLOCCATO_CLASSE_RISCHIO", blocked=True),
        _record("88008", status="OK_or_HIGHER_RISK", blocked=False),
    ]
    canonical, spec = _fixture_files(tmp_path, records, expected=["88001"], excluded=["88004"])

    assert _run(canonical, spec, apply=True) == 0
    for record in _records(canonical):
        blob = json.dumps(record["l4_bali"]["moratorium"])
        assert "ALL" not in blob
        assert "permanent" not in blob
        assert "2026-05-13" not in blob
        assert set(record["l4_bali"]["moratorium"]) == set(cure.MORATORIUM_KEYS)


# --------------------------------------------------------------- refusals


def test_membership_drift_is_refused(tmp_path: Path) -> None:
    guilty = _record("88001", ancestors_2020=["99990"])
    # expected_2025_codes omits 88001, which the ancestors DO derive -> drift.
    canonical, spec = _fixture_files(tmp_path, [guilty], expected=[], excluded=[])

    assert _run(canonical, spec, apply=True) == cure.EXIT_REFUSED
    assert _by_code(canonical)["88001"]["l4_bali"]["status"] != "CHIUSO_BALI"


def test_expected_code_with_no_matching_ancestor_is_also_drift(tmp_path: Path) -> None:
    innocent = _record("88011")  # no bps_2020_ancestors at all
    canonical, spec = _fixture_files(tmp_path, [innocent], expected=["88011"], excluded=[])

    assert _run(canonical, spec, apply=True) == cure.EXIT_REFUSED


def test_code_in_both_forty_and_excluded_is_refused(tmp_path: Path) -> None:
    rec = _record("88001", ancestors_2020=["99990"])
    canonical, spec = _fixture_files(tmp_path, [rec], expected=["88001"], excluded=["88001"])

    assert _run(canonical, spec, apply=True) == cure.EXIT_REFUSED


# --------------------------------------------------------------- idempotence / dry-run


def test_idempotent_second_apply_preserves_bytes(tmp_path: Path) -> None:
    records = [
        _record("88001", status="BLOCCATO_CLASSE_RISCHIO", blocked=True, ancestors_2020=["99990"]),
        _record("88006", status="BLOCCATO_CLASSE_RISCHIO", blocked=True),
        _record("88007", status="NON_CLASSIFICABILE", blocked=True),
        _record("88008", status="OK_or_HIGHER_RISK", blocked=False),
    ]
    canonical, spec = _fixture_files(tmp_path, records, expected=["88001"], excluded=[])

    assert _run(canonical, spec, apply=True) == 0
    after_first = canonical.read_bytes()
    assert _run(canonical, spec, apply=True) == 0
    assert canonical.read_bytes() == after_first


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    rec = _record("88001", status="BLOCCATO_CLASSE_RISCHIO", blocked=True, ancestors_2020=["99990"])
    canonical, spec = _fixture_files(tmp_path, [rec], expected=["88001"], excluded=[])
    before = canonical.read_bytes()

    assert _run(canonical, spec) == 0
    assert canonical.read_bytes() == before


# --------------------------------------------------------------- against the real canonical


def test_real_canonical_applies_to_the_expected_census(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical.json"
    canonical.write_bytes(cure.DEFAULT_CANONICAL.read_bytes())
    before_records = json.loads(cure.DEFAULT_CANONICAL.read_text(encoding="utf-8"))["data"]
    before_by_code = {r["kode_kbli_2025"]: r for r in before_records}
    closure_spec = cure.load_closure_spec(cure.DEFAULT_SPEC)

    assert cure.main(["--canonical", str(canonical), "--spec", str(cure.DEFAULT_SPEC), "--apply"]) == 0

    records = _records(canonical)
    by_code = {r["kode_kbli_2025"]: r for r in records}
    counter = cure._status_blocked_counter(records)
    total_blocked = sum(c for (_status, blocked), c in counter.items() if blocked is True)

    # SAETTA-20260915 W-H #6596 (merged into this branch's base) lifted
    # 43110's own Bali block, dropping the pre-cure raw population 519->518
    # and this compiler's own output 132->131 (BLOCCATO_DIPENDE_SCOPE
    # blocked=true: 2->1; every other group unchanged).
    assert total_blocked == 131
    assert counter[("CHIUSO_BALI", True)] == 40
    assert counter[("ATTENZIONE_FASCIA_BALI", False)] == 387
    assert counter[("TERTUTUP", True)] == 68

    # guilt
    assert by_code["68111"]["l4_bali"]["status"] == "CHIUSO_BALI"
    assert by_code["68111"]["l4_bali"]["blocked"] is True
    assert "Bali Provincial Government closed OSS" in by_code["68111"]["l4_bali"]["reason"]
    assert by_code["55101"]["l4_bali"]["status"] == "CHIUSO_BALI"
    assert "6,000 m" in by_code["55101"]["l4_bali"]["reason"]
    assert by_code["56400"]["l4_bali"]["status"] == "CHIUSO_BALI"
    assert "merges KBLI 2020 activities" in by_code["56400"]["l4_bali"]["reason"]

    # innocence
    for code in closure_spec["excluded_codes"]["codes"]:
        before_l4 = dict(before_by_code[code]["l4_bali"])
        after_l4 = dict(by_code[code]["l4_bali"])
        before_l4.pop("moratorium", None)
        after_l4.pop("moratorium", None)
        assert before_l4 == after_l4, f"excluded code {code} moved outside moratorium"

    before_01111 = dict(before_by_code["01111"]["l4_bali"])
    after_01111 = dict(by_code["01111"]["l4_bali"])
    before_01111.pop("moratorium", None)
    after_01111.pop("moratorium", None)
    assert before_01111 == after_01111
    assert after_01111["status"] == "TERTUTUP"

    assert by_code["01192"]["l4_bali"]["status"] == "ATTENZIONE_FASCIA_BALI"
    assert by_code["01192"]["l4_bali"]["blocked"] is False

    # moratorium sanity across the WHOLE corpus
    for record in records:
        blob = json.dumps(record["l4_bali"]["moratorium"])
        assert "ALL" not in blob
        assert "permanent" not in blob
        assert "2026-05-13" not in blob

    # idempotence on the real corpus too
    after_first = canonical.read_bytes()
    assert cure.main(["--canonical", str(canonical), "--spec", str(cure.DEFAULT_SPEC), "--apply"]) == 0
    assert canonical.read_bytes() == after_first
