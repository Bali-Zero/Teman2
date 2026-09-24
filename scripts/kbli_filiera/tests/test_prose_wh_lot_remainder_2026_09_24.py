"""Pins for the W-H prose lot remainder cure
(`cure_specs/prose_wh_lot_remainder_2026_09_24.json`).

Four defect families, one guilt test each:
1. 50135/50221/51101/50222 `editorial.pullQuote` says Bali is not moratorium-blocked
   without stating the national 49% foreign-ownership cap that still applies.
2. 53200 `whatYouNeed` ends with an unverified precise date ("13 May 2026") for a
   moratorium the record itself dates only to "third week of May 2026".
3. 50133 `whatYouNeed` ends with a dangling self-referential fragment ("that is the
   risk class the record carries").
4. 93114 `editorial.*` asserts unqualified Bali registrability against its own
   `l4_bali.status` of BLOCCATO_DIPENDE_SCOPE — only paragraph 4 of the body may
   change; paragraphs 1-3 carry the true national-opening facts verbatim.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

_FILIERA = str(Path(__file__).resolve().parents[1])
if _FILIERA not in sys.path:
    sys.path.insert(0, _FILIERA)

import cure_prose_national_openness as C  # noqa: E402
import editorial_record_conformance as E  # noqa: E402

SPEC = C.SPEC.parent / "prose_wh_lot_remainder_2026_09_24.json"
CODES = {"50135", "50221", "51101", "50222", "53200", "50133", "93114"}
CAP_PULLQUOTE_CODES = {"50135", "50221", "51101", "50222"}

# Measured once against origin/main f300402e0e, before this spec is applied.
OTHER_CODES_WITH_13_MAY_PRECURE = 536
NEIGHBOUR_PULLQUOTE_CODES = {"50211", "50213"}
PARA_1_3_SHA256_PRECURE = (
    "7fce68c8cbbf04a4072313ede23f3c2331f3c7e2b46ede8e99944b455c0d7b70"
)


def _strings(node):
    if isinstance(node, dict):
        for v in node.values():
            yield from _strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _strings(v)
    elif isinstance(node, str):
        yield node


def _by_code():
    return {r.get("kode_kbli_2025"): r for r in E.load_records()}


def test_the_spec_names_the_seven_codes_and_ten_fields():
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    assert spec["compiler"] == C.LANE
    assert set(spec["codes"]) == CODES
    assert sum(len(e["fields"]) for e in spec["codes"].values()) == 10


def test_guilt_capless_pullquotes_state_the_national_cap():
    by_code = _by_code()
    for code in CAP_PULLQUOTE_CODES:
        pq = by_code[code]["intel_2026"]["editorial"]["pullQuote"]
        assert "49%" in pq, f"{code}: pullQuote still omits the national cap"


def test_guilt_53200_drops_the_unverified_date():
    record = _by_code()["53200"]
    for s in _strings(record.get("intel_2026") or {}):
        assert "13 May 2026" not in s


def test_guilt_50133_drops_the_dangling_fragment():
    record = _by_code()["50133"]
    for s in _strings(record.get("intel_2026") or {}):
        assert "that is the risk class the record carries" not in s


def test_guilt_93114_drops_the_unqualified_bali_claims():
    record = _by_code()["93114"]
    banned = (
        "registrable in Bali by a PT PMA",
        "remains registrable by a PT PMA",
        "Open in Bali (high-risk track)",
        "permanent moratorium",
        "Golf facilities at the Besar scale",
    )
    for s in _strings(record.get("intel_2026") or {}):
        for phrase in banned:
            assert phrase not in s, f"93114 still carries {phrase!r}"


def test_guilt_93114_risk_by_scope_matches_per_skala_not_scale():
    record = _by_code()["93114"]
    per_skala = record["per_skala"]
    by_scope: dict[int, set[str]] = {}
    for row in per_skala:
        by_scope.setdefault(row["scope_index"], set()).add(row["kategori_risiko"])
    # golf is scope_index 1, other courts scope_index 0 — scale-invariant on the record.
    assert by_scope[1] == {"Tinggi"}
    assert by_scope[0] == {"Menengah Rendah"}

    body = record["intel_2026"]["editorial"]["body"]
    assert "golf" in body.lower()
    assert "Tinggi" in body or "high risk" in body
    assert "Menengah Rendah" in body


def test_guilt_every_field_equals_the_graded_text_and_premise_holds():
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    by_code = _by_code()
    for code, entry in spec["codes"].items():
        record = by_code[code]
        C.check_premise(record, code, entry["expect"])
        for path, patch in entry["fields"].items():
            assert C.read_field(record, path) == patch["new"], f"{code}.{path} was edited after grading"


def test_innocence_53200_and_50133_keep_the_true_facts():
    by_code = _by_code()
    wyn_53200 = by_code["53200"]["intel_2026"]["whatYouNeed"]
    assert "Perpres 49/2021, Lampiran III, entry #32" in wyn_53200
    assert "foreign shareholders can hold up to 49% of a PT PMA" in wyn_53200

    wyn_50133 = by_code["50133"]["intel_2026"]["whatYouNeed"]
    assert "entry #22" in wyn_50133
    assert "foreign shareholders can hold up to 49% of a PT PMA" in wyn_50133


def test_innocence_93114_body_paragraphs_1_to_3_are_untouched():
    record = _by_code()["93114"]
    body = record["intel_2026"]["editorial"]["body"]
    paras = body.split("\n\n")
    assert len(paras) == 4
    joined = "\n\n".join(paras[0:3])
    assert hashlib.sha256(joined.encode("utf-8")).hexdigest() == PARA_1_3_SHA256_PRECURE
    assert "100%" in body
    assert "TERBUKA" in body


def test_innocence_cap_check_spares_neighbours_already_carrying_49_percent():
    by_code = _by_code()
    for code in NEIGHBOUR_PULLQUOTE_CODES:
        pq = by_code[code]["intel_2026"]["editorial"]["pullQuote"]
        assert "49%" in pq


def test_innocence_13_may_2026_count_on_other_codes_is_unchanged():
    n = 0
    for record in E.load_records():
        if record.get("kode_kbli_2025") == "53200":
            continue
        s = json.dumps(record.get("intel_2026") or {})
        if "13 May 2026" in s:
            n += 1
    assert n == OTHER_CODES_WITH_13_MAY_PRECURE
