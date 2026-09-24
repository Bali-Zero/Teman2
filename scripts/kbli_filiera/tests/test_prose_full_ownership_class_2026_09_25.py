"""Pins for the full-ownership-overclaim class cure
(`cure_specs/prose_full_ownership_class_2026_09_25.json`).

50134 (Angkutan Penyeberangan Perintis Antarprovinsi untuk Penumpang) is
TERBATAS with `pma_max_asing` 49 (Perpres 49/2021 Lampiran III entry #19), but
its `intel_2026.whatYouNeed` opened with "Foreign-owned PMA companies can
fully own this business in Bali" — a full-ownership claim with NO number, so
L10 (reads a number against `pma_max_asing`) and `editorial_record_
conformance.classify` (needs a national-scope word in the same sentence) were
both blind to it. `l12_full_ownership_claim` (`scripts/kbli_dataset_lint.py`)
reads the CLAIM instead of a number. Census of every `intel_2026` string on
records with `pma_max_asing < 100` or `pma_status != TERBUKA`: 50134 is the
ONLY affirmative full-ownership claim; the other nine phrase hits are
negations (or a 100% cap, out of L12's scope by construction).
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

_FILIERA = str(Path(__file__).resolve().parents[1])
if _FILIERA not in sys.path:
    sys.path.insert(0, _FILIERA)
_SCRIPTS = str(Path(__file__).resolve().parents[2])
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import cure_prose_national_openness as C  # noqa: E402
import editorial_record_conformance as E  # noqa: E402
from kbli_dataset_lint import l12_full_ownership_claim  # noqa: E402

SPEC = C.SPEC.parent / "prose_full_ownership_class_2026_09_25.json"
CODE = "50134"

# Codex MINOR (2026-09-25): `iter_prose` only yields its own hardcoded field
# list — `tkaInfo` is ALWAYS a nested dict on this dataset (never the string
# `iter_prose` expects), so a defect written into e.g. `tkaInfo.insight` or
# any other nested leaf would never reach the population test at all. These
# are the only `intel_2026` subtrees that are pure PROVENANCE/audit metadata
# (LLM model name, confidence enum, gate verdict, regen tag, gap-disclosure
# hash/date, a cover-image URL) rather than client-facing prose — excluded
# by exact key name, everything else is walked.
_INTEL_METADATA_KEYS = {"_l3_regen", "_l3_gap_disclosure", "coverImage"}


def _iter_intel_leaves(record):
    """Every string leaf under `intel_2026`, recursively — dicts and lists at
    any depth, not just `iter_prose`'s direct fields."""

    def walk(node, path):
        if isinstance(node, dict):
            for key, value in node.items():
                if path == "" and key in _INTEL_METADATA_KEYS:
                    continue
                yield from walk(value, f"{path}.{key}" if path else key)
        elif isinstance(node, list):
            for i, value in enumerate(node):
                yield from walk(value, f"{path}[{i}]")
        elif isinstance(node, str) and node.strip():
            yield path, node

    yield from walk(record.get("intel_2026") or {}, "")

# Verbatim pre-cure text (copied from origin/main e0b18b8bac, `repr()`-round-
# tripped, never hand-typed) — the exact defect this cure removed.
ORIGINAL_WHATYOUNEED = (
    "Foreign-owned PMA companies can fully own this business in Bali, as it's "
    "not blocked by local moratoriums. However, the government classifies it "
    "as medium-high risk, so you'll face extra scrutiny—address-specific "
    "verification is mandatory before you can operate, and compliance "
    "requirements are stricter than for low-risk activities."
)
# Pinned in the spec's `old_sha256`; proves ORIGINAL_WHATYOUNEED above is the
# real pre-cure text, not a paraphrase.
ORIGINAL_SHA256 = "ac705631361fe73f345ad9084314d248aa3e88e04630168f059b7bbb855587a2"

# Measured once (this session) against origin/main e0b18b8bac: every OTHER
# record (all 1558 codes besides 50134), sorted by code and serialized with
# `sort_keys=True`, hashes to this. A live `git show origin/main:...` at test
# time is not used because `actions/checkout@v7` in
# `.github/workflows/kbli-filiera-vault-compilers.yml` does not set
# `fetch-depth: 0` — the ref is unresolvable in that shallow checkout, the
# same reason `test_prose_wh_lot_remainder_2026_09_24.py` pins counts/hashes
# rather than diffing git history at test time.
OTHER_RECORDS_SHA256_PRECURE = (
    "55a14a53a193d68ebe7e87793f4b9c4e64ec1145b53bc72f92156c8975e02810"
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


def _records():
    return E.load_records()


def _by_code():
    return {r.get("kode_kbli_2025"): r for r in _records()}


def test_the_spec_names_the_one_code_and_field():
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    assert spec["compiler"] == C.LANE
    assert set(spec["codes"]) == {CODE}
    assert sum(len(e["fields"]) for e in spec["codes"].values()) == 1


def test_guilt_class_zero_l12_hits_on_the_real_canonical():
    """The cured population: walking every string leaf (recursively — see
    `_iter_intel_leaves`, Codex MINOR) of every record's `intel_2026` on the
    REAL (post-cure) canonical, L12 finds ZERO hits.

    Pre-cure, this test is RED: evaluated in memory against
    `git show e0b18b8bac:data/source_documents/KBLI_2025_FINAL_CLEAN.json`
    (origin/main e0b18b8bac, before this PR), `l12_full_ownership_claim`
    fires exactly once, on 50134's `intel_2026.whatYouNeed` — the sentence
    pinned in `ORIGINAL_WHATYOUNEED` below.
    """
    hits = []
    for record in _records():
        code = record.get("kode_kbli_2025")
        maxa = record.get("pma_max_asing")
        for path, text in _iter_intel_leaves(record):
            hit = l12_full_ownership_claim(text, maxa)
            if hit:
                hits.append(f"{code}.intel_2026.{path} :: {hit}")
    assert hits == [], f"L12 must find zero hits on the cured canonical: {hits}"


def test_the_recursive_walker_catches_a_defect_iter_prose_would_miss():
    """Codex MINOR: `iter_prose` only yields its own hardcoded field list, so
    a defect written into a nested leaf it never visits (e.g. `tkaInfo.
    summary` — `tkaInfo` is always a dict on this dataset, never the string
    `iter_prose` expects) would silently pass the population test above.
    Proof: inject the exact 50134 defect shape into a record COPY's
    `tkaInfo.summary` (a field that does not exist in the real schema) and
    confirm `_iter_intel_leaves` — and therefore the guilt test — finds it.
    """
    record = copy.deepcopy(_by_code()[CODE])
    record["intel_2026"]["tkaInfo"] = {
        "summary": "Foreign investors can fully own this company."
    }
    flagged = [
        (path, l12_full_ownership_claim(text, record.get("pma_max_asing")))
        for path, text in _iter_intel_leaves(record)
    ]
    flagged = [(path, hit) for path, hit in flagged if hit]
    assert any(path == "tkaInfo.summary" for path, _ in flagged), (
        f"the recursive walker must catch a defect injected into a nested leaf: {flagged}"
    )


def test_guilt_the_real_50134_equals_the_spec_and_replanning_is_a_noop():
    by_code = _by_code()
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    entry = spec["codes"][CODE]
    record = by_code[CODE]
    C.check_premise(record, CODE, entry["expect"])
    for path, patch in entry["fields"].items():
        assert C.read_field(record, path) == patch["new"], (
            f"{CODE}.{path} was edited after the spec was graded"
        )
    # Re-planning against the ALREADY-cured record refuses: the live text no
    # longer hashes to `old_sha256`, which is exactly the signal that the
    # cure already landed (not a re-match).
    try:
        C.plan_for(record, CODE, entry)
    except C.CureError as exc:
        assert "text moved since the spec was graded" in str(exc)
    else:
        raise AssertionError("re-planning an already-cured record must refuse, not re-patch")


def test_guilt_the_original_fixture_hashes_to_the_specs_old_sha256_and_is_flagged():
    digest = hashlib.sha256(ORIGINAL_WHATYOUNEED.encode("utf-8")).hexdigest()
    assert digest == ORIGINAL_SHA256, "fixture is not the real pre-cure text"
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    assert spec["codes"][CODE]["fields"]["whatYouNeed"]["old_sha256"] == ORIGINAL_SHA256
    hit = l12_full_ownership_claim(ORIGINAL_WHATYOUNEED, 49)
    assert hit is not None, "L12 must flag the real pre-cure sentence"
    assert "fully own" in hit


def test_innocence_the_tail_sentence_is_preserved_verbatim():
    by_code = _by_code()
    wyn = by_code[CODE]["intel_2026"]["whatYouNeed"]
    tail = (
        "However, the government classifies it as medium-high risk, so "
        "you'll face extra scrutiny—address-specific verification is "
        "mandatory before you can operate, and compliance requirements are "
        "stricter than for low-risk activities."
    )
    assert tail in wyn
    assert wyn.endswith(tail)


def test_innocence_new_text_states_only_the_records_own_cap():
    by_code = _by_code()
    record = by_code[CODE]
    wyn = record["intel_2026"]["whatYouNeed"]
    assert record.get("pma_max_asing") == 49
    percentages = set(C._PERCENT.findall(wyn))
    assert percentages == {"49"}, f"whatYouNeed must state only the record's own cap: {percentages}"


def test_innocence_50142_unchanged_and_not_flagged():
    by_code = _by_code()
    record = by_code["50142"]
    wyn = record["intel_2026"]["whatYouNeed"]
    assert "Nationally, a foreign-owned PT PMA can hold 100% of this KBLI." in wyn
    assert l12_full_ownership_claim(wyn, record.get("pma_max_asing")) is None


def test_innocence_no_record_other_than_50134_changed_vs_origin_main():
    records = [r for r in _records() if r.get("kode_kbli_2025") != CODE]
    records.sort(key=lambda r: r.get("kode_kbli_2025"))
    blob = json.dumps(records, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    assert digest == OTHER_RECORDS_SHA256_PRECURE, (
        "a record other than 50134 moved vs origin/main — this cure must touch ONLY 50134"
    )
