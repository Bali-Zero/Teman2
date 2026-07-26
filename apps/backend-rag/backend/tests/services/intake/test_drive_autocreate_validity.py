"""Guilt+innocence tests for drive-autocreate creation validity (spec v3 §6 +
gate round-3 fixes) and the shared census/apply candidate predicate (v3 §3).

Guard-conformance discipline (scar #3): every gate proves BOTH that it fires
on a guilty value AND that it stays quiet on a legitimate neighbour.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from backend.services.intake.drive_autocreate_validity import (
    VALIDATORS,
    canonical_alnum,
    canonical_digits,
    valid_kitas,
    valid_name,
    valid_npwp,
    valid_passport,
)

# The census script is not a package module — load it by path once so the
# classify_perimeter predicate is tested from its real home (no copy-paste
# twin that could drift).
_SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "intake_drive_contact_autocreate.py"
_spec = importlib.util.spec_from_file_location("intake_drive_contact_autocreate", _SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("intake_drive_contact_autocreate", _mod)
_spec.loader.exec_module(_mod)

Doc = _mod.Doc
classify_perimeter = _mod.classify_perimeter
_clustered_names = _mod._clustered_names


# --- creation validity -------------------------------------------------------


def test_passport_bound_guilt_and_innocence() -> None:
    # innocence: real-shaped values pass and come back canonical.
    assert valid_passport("X 123456") == "X123456"
    assert valid_passport("c1234567") == "C1234567"
    assert valid_passport("A12345678") == "A12345678"  # 9 chars — ICAO cap
    # guilt: fragments, letter-only, over-length, junk.
    assert valid_passport("C1234") is None  # 5 — OCR fragment
    assert valid_passport("ABCDEFG") is None  # no digit
    assert valid_passport("A123456789") is None  # 10 > ICAO 9303 cap
    assert valid_passport("") is None
    assert valid_passport(None) is None


def test_kitas_bound_guilt_and_innocence() -> None:
    assert valid_kitas("2C21JE1234-X") == "2C21JE1234X"
    assert valid_kitas("2C11AB12345678") == "2C11AB12345678"  # long kitas OK — no cap
    assert valid_kitas("ABCDEF") is None  # no digit
    assert valid_kitas("2C1") is None  # too short


def test_npwp_bound_guilt_and_innocence() -> None:
    assert valid_npwp("01.234.567.8-901.000") == "012345678901000"  # 15
    assert valid_npwp("0123456789012345") == "0123456789012345"  # 16
    assert valid_npwp("01234567890") is None  # 11 — fragment
    assert valid_npwp("01234567890123456") is None  # 17


def test_name_validity_guilt_and_innocence() -> None:
    assert valid_name("  jane   doe ") == "JANE DOE"
    assert valid_name("N/A") is None
    assert valid_name("UNKNOWN") is None
    assert valid_name("AB1") is None  # too short
    assert valid_name("12345") is None  # no letters


def test_projections_mirror_matcher_semantics() -> None:
    # canonical_alnum == routing._normalize_id (strip ONLY [\s.-/], upper).
    assert canonical_alnum("x 12-34.56/") == "X123456"
    # R3-4 guilt: '#' is NOT a routing separator — it must SURVIVE the
    # projection (identical canonicalization on both sides) and then fail
    # creation validity, never be silently cleaned into a different key.
    assert canonical_alnum("AB#123456") == "AB#123456"
    assert valid_passport("AB#123456") is None
    # canonical_digits == routing._ascii_digits (ASCII class, not unicode \d)
    assert canonical_digits("٠١٢345") == "345"


def test_validator_dispatch_covers_wave1_kinds_only() -> None:
    assert set(VALIDATORS) == {"passport", "kitas", "npwp"}  # NIK/ktp OUT (v3 §4)


# --- shared candidate predicate ---------------------------------------------


def _doc(**kw) -> Doc:
    base = {
        "pid": 1,
        "qid": 1,
        "status": "review_pending",
        "kind": "passport",
        "blob_hash": "b1",
        "is_drive": True,
        "root_segment": "PEMEGANG KITAS",
        "name": "JANE DOE",
        "canonical": "X123456",
        "has_validate": True,
        "validate_valid": "true",
        "fields_fp": "ff1",
    }
    base.update(kw)
    return Doc(**base)


def _classify(docs, **kw):
    base = {
        "existing_keys": set(),
        "ledgered": set(),
        "similar_to_existing": set(),
        "cluster_names": set(),
        "validate_strict": False,
    }
    base.update(kw)
    return classify_perimeter(docs, **base)


def test_clean_drive_doc_is_a_effective() -> None:
    res = _classify([_doc()])
    assert res.buckets["A_effective"] == 1
    assert res.per_kind_a == {"passport": 1}
    assert res.a_docs  # manifest evidence rows exist


def test_existing_id_blocks_create_never_merges() -> None:
    res = _classify([_doc()], existing_keys={"passport:X123456"})
    assert res.buckets["B_id_already_exists"] == 1
    assert not res.a_sids


def test_ledgered_key_is_tombstoned() -> None:
    res = _classify([_doc()], ledgered={"passport:X123456"})
    assert res.buckets["ledgered_skip"] == 1


def test_root_allowlist_is_enforced_in_predicate() -> None:
    # R3-1 guilt: a drive doc from an undeclared root never reaches A.
    res = _classify([_doc(root_segment="RANDOM SHARE")])
    assert res.buckets["B_root_not_allowlisted"] == 1
    # innocence: every declared root passes.
    res2 = _classify([_doc(root_segment="DATA ADI")])
    assert res2.buckets["A_effective"] == 1


def test_name_conflict_counts_distinct_blobs_only() -> None:
    # guilt: two DISTINCT blobs disagree on the name -> conflict.
    guilty = [
        _doc(pid=1, blob_hash="b1", name="JANE DOE"),
        _doc(pid=2, blob_hash="b2", name="JANE SMITH"),
    ]
    assert _classify(guilty).buckets["B_name_conflict"] == 2
    # innocence: the SAME blob duplicated (copies) cannot manufacture
    # agreement or conflict — one blob, one name, still A (R3-9: the bar is
    # ONE strictly-validated doc; copies add nothing either way).
    innocent = [
        _doc(pid=1, blob_hash="b1", name="JANE DOE"),
        _doc(pid=2, blob_hash="b1", name="JANE DOE"),
    ]
    assert _classify(innocent).buckets["A_effective"] == 2


def test_nondrive_provenance_excluded_from_wave1() -> None:
    res = _classify([_doc(is_drive=False)])
    assert res.buckets["B_nondrive_provenance"] == 1


def test_similar_to_existing_person_quarantined() -> None:
    res = _classify([_doc()], similar_to_existing={"JANE DOE"})
    assert res.buckets["B_possible_existing_person"] == 1


def test_cluster_names_quarantine_their_docs() -> None:
    docs = [
        _doc(pid=1, canonical="X123456", name="JANE DOE"),
        _doc(pid=2, canonical="Y654321", name="JANE D0E"),
    ]
    res = _classify(docs, cluster_names={"JANE DOE", "JANE D0E"})
    assert res.buckets["B_multisid_or_cluster"] == 2
    assert not res.a_sids


def test_clustered_names_requires_sid_diversity() -> None:
    # R3-10 guilt: same name on two different sids clusters (exact flavour)…
    exact = _clustered_names(
        {"passport:X123456": {"JANE DOE"}, "passport:Y654321": {"JANE DOE"}},
        set(),
    )
    assert exact == {"JANE DOE"}
    # …and a fuzzy pair spanning different sids clusters both names.
    fuzzy = _clustered_names(
        {"passport:X123456": {"JANE DOE"}, "passport:Y654321": {"JANE D0E"}},
        {frozenset({"JANE DOE", "JANE D0E"})},
    )
    assert fuzzy == {"JANE DOE", "JANE D0E"}
    # innocence: two spellings on the SAME sid never cluster.
    same_sid = _clustered_names(
        {"passport:X123456": {"JANE DOE", "JANE D0E"}},
        {frozenset({"JANE DOE", "JANE D0E"})},
    )
    assert same_sid == set()


def test_validate_strict_branch_guilt_and_innocence() -> None:
    # R3-3 guilt: under STRICT, a MISSING validate stage is a rejection —
    # never a pass-through.
    missing = _doc(has_validate=False, validate_valid=None)
    assert _classify([missing], validate_strict=True).buckets["B_validate_not_true"] == 1
    # guilt: stage present but not true.
    stale = _doc(has_validate=True, validate_valid="unknown")
    assert _classify([stale], validate_strict=True).buckets["B_validate_not_true"] == 1
    # innocence: stage present and true -> A under STRICT.
    ok = _doc(has_validate=True, validate_valid="true")
    assert _classify([ok], validate_strict=True).buckets["A_effective"] == 1
    # explicit false excludes on the non-strict branch too.
    bad = _doc(has_validate=True, validate_valid="false")
    assert _classify([bad], validate_strict=False).buckets["B_validate_false"] == 1


def test_incomplete_and_discard_buckets() -> None:
    res = _classify(
        [
            _doc(name=None, canonical=None),  # no signal at all
            _doc(canonical=None),  # name only
        ]
    )
    assert res.buckets["C_discard"] == 1
    assert res.buckets["B_incomplete"] == 1


def test_execution_order_covers_every_bucket() -> None:
    # R3-11: the report lists buckets in predicate order — the list must be
    # the complete vocabulary the predicate can emit.
    docs = [
        _doc(pid=1, name=None, canonical=None),
        _doc(pid=2, canonical=None),
        _doc(pid=3, is_drive=False),
        _doc(pid=4, root_segment="NOPE"),
        _doc(pid=5, canonical="L111111"),
        _doc(pid=6, canonical="E222222"),
        _doc(pid=7, blob_hash="x1", canonical="C333333", name="AA BB"),
        _doc(pid=8, blob_hash="x2", canonical="C333333", name="CC DD"),
        _doc(pid=9, canonical="V444444", validate_valid="false"),
        _doc(pid=10, canonical="S555555", name="SIM PERSON"),
        _doc(pid=11, canonical="K666666", name="CLUSTERED P"),
        _doc(pid=12, canonical="A777777", name="FREE PERSON"),
    ]
    res = _classify(
        docs,
        ledgered={"passport:L111111"},
        existing_keys={"passport:E222222"},
        similar_to_existing={"SIM PERSON"},
        cluster_names={"CLUSTERED P"},
    )
    assert set(res.buckets) <= set(_mod.EXECUTION_ORDER)


def test_valid_name_rejects_json_structural_chars():
    """R12-1: a scalar STRING whose content is serialized JSON passes the
    typed SQL projection (it IS a string) — the validator is the guard. No
    legitimate person name carries JSON/markup structural characters
    (probed live 2026-07-20: 0 hits in the alive client book, 18 in the
    extracted-name book — all OCR/JSON garbage)."""
    assert valid_name('{"label":"JOHN SMITH"}') is None
    assert valid_name('["JOHN","SMITH"]') is None
    assert valid_name('JOHN \\"SMITH\\"') is None
    assert valid_name("JOHN=SMITH") is None
    assert valid_name("JOHN <SMITH>") is None
    assert valid_name("JOHN|SMITH") is None
    # Innocence: real-world name punctuation survives.
    assert valid_name("O'BRIEN MICHAEL") == "O'BRIEN MICHAEL"
    assert valid_name("ANNE-MARIE VAN DER BERG") == "ANNE-MARIE VAN DER BERG"
    assert valid_name("MULYADI BIN SLAMET") == "MULYADI BIN SLAMET"
    assert valid_name("ST. JOHN SMYTHE") == "ST. JOHN SMYTHE"


def test_valid_name_rejects_structural_free_json_literals():
    """R13-1: a structural-char-free serialized JSON LITERAL (a field whose
    'value' member is the bare string 'false'/'true'/'null'/'undefined')
    has enough letters and no structural characters, so it survives both
    R12-1 gates above — the placeholder set must name these tokens too.
    Innocence: a name that merely CONTAINS one of these words is real."""
    assert valid_name("false") is None
    assert valid_name("true") is None
    assert valid_name("null") is None
    assert valid_name("undefined") is None
    assert valid_name("FALSE") is None
    assert valid_name("  Null  ") is None
    # Innocence: substring containment must not over-match (guard family #3).
    assert valid_name("FALSE POSITIVE") == "FALSE POSITIVE"
    assert valid_name("TRUEMAN JACKSON") == "TRUEMAN JACKSON"
