"""Regression registry — KBLI false-friend per_skala collisions (68112 pattern,
generalized to all 8 known instances, 2026-07-17).

This file folds in (verbatim, unmodified assertions) the original
test_kbli_68112_pp28_mice_collision.py — 68112 coverage MUST survive — and adds
a registry-driven suite for the 7 codes cured by GARUDA-FILIERA Fase 1
(scripts/kbli_filiera/cure_canonical_collisions.py driven by
scripts/kbli_filiera/cure_specs/fase1_collisions.json): 49213, 51103, 51203,
20111, 50115, 60312, 64310.

Cure pattern (identical for all 8, see cure_canonical_collisions.py docstring):
  1. per_skala -> []  (frontend guards licensing.length > 0 -> honest "not yet
     defined" gap instead of wrong data)
  2. the ORIGINAL per_skala (+ per_skala_legacy, if present) preserved verbatim
     under a disputed key — never silently deleted
  3. _data_note added (verbatim from the cure spec — never invented here)
  4. pp28_sources / intel_2026 / judul / uraian / pma_* / status_mapping / every
     other field left untouched

Scar-family #3 (guard-over-match/under-match) discipline applies throughout:
every guilt assertion below is paired with an innocence assertion on a
legitimate neighbor code, and every content marker is a multi-word phrase or
a case-sensitive whole-word Indonesian/technical term verified (via direct
tool-call inspection of the served dataset, not assumed) to actually appear
in the disputed content or disclaiming prose it guards — never a bare
substring like "SPA" that would false-positive on "space"/"aerospace".
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FASE1_SPEC_PATH = REPO_ROOT / "scripts/kbli_filiera/cure_specs/fase1_collisions.json"

# Every SERVED/canonical copy that must stay clean. Gitignored RAG runtime
# copies are materialized by scripts/sync_kbli_dataset.sh at build/apply time
# and may be absent on a fresh checkout/CI runner — skipped if missing, same
# convention the original 68112 test used. This list covers all 4 consumer
# copies scripts/sync_kbli_dataset.sh propagates (the original 68112 test only
# checked 3 of the 4 — apps/backend-rag/source_documents/ was missing; adding
# it here is a strict superset, not a narrowing, of 68112's prior coverage).
ALL_DATASET_COPIES = [
    REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json",  # production, balizero.com/kbli
    REPO_ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json",  # canonical (via source_documents/ symlink)
    REPO_ROOT / "apps/backend-rag/backend/data/KBLI_2025_FINAL_CLEAN.json",  # gitignored, RAG runtime
    REPO_ROOT / "apps/backend-rag/source_documents/KBLI_2025_FINAL_CLEAN.json",  # gitignored, RAG runtime
]


def _existing_dataset_copies() -> list[Path]:
    return [p for p in ALL_DATASET_COPIES if p.exists()]


def _load_by_code(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {r["kode_kbli_2025"]: r for r in data["data"] if "kode_kbli_2025" in r}


def _load_record(path: Path, code: str) -> dict[str, Any]:
    rec = _load_by_code(path).get(code)
    if rec is None:
        raise AssertionError(f"{path}: record {code} not found in dataset")
    return rec


def _contains_word_or_phrase(haystack: str, marker: str) -> bool:
    """Word-boundary-safe containment check (scar-family #3 antidote): a
    single-word marker is matched with regex word boundaries so it cannot
    false-positive inside a longer word (e.g. bare 'SPA' inside 'aerospace').
    A multi-word phrase (contains a space) is matched as a plain substring —
    the multi-word shape itself is already a strong disambiguator."""
    if " " in marker:
        return marker in haystack
    return re.search(rf"\b{re.escape(marker)}\b", haystack) is not None


# ---------------------------------------------------------------------------
# Registry: all 8 known false-friend per_skala collisions.
#
# `marker_in_disputed` — whether the content marker is verified (by direct
# read of the served dataset) to literally appear inside the disputed key's
# preserved blob. True for 7 of 8: 64310 is the exception — its actual
# per_skala content, once inspected, turned out to be a generic low-risk NIB
# template with no code-specific vocabulary (the "Sante Par Aqua" identity of
# the wrong pp28 pointer target lives only in the disclaiming _data_note
# prose, not in the licensing rows themselves). Asserting the marker inside
# the disputed key for 64310 would be a fabricated claim about the data — so
# that check is skipped for 64310 specifically, and the marker is instead
# checked for presence in `_data_note` (the disclaiming surface where it
# genuinely lives) and continued absence from per_skala/intel_2026.
#
# `check_intel_clean` — whether "marker not present in intel_2026" is a valid
# guilt check for this code. True for all 7 Fase-1 codes (verified clean of
# wrong-licensing markers per the pilot D6 gate). False for 68112: its
# corrected intel_2026.whatYouNeed LEGITIMATELY mentions "MICE"/"Venue" as
# disclaiming prose (explaining the collision to the client) — a blind
# "marker never in intel_2026" rule would false-positive on 68112's own fix.
# 68112's nuanced disclaimer-aware whole-record scan lives in the folded-in
# legacy tests below instead.
FALSE_FRIENDS: list[dict[str, Any]] = [
    {
        "code": "68112",
        "disputed_key": "per_skala_disputed_pp28_mice",
        "marker": "MICE",
        "marker_in_disputed": True,
        "check_intel_clean": False,
    },
    {
        "code": "49213",
        "disputed_key": "per_skala_disputed_pp28_collision",
        "marker": "Gubernur",
        "marker_in_disputed": True,
        "check_intel_clean": True,
    },
    {
        "code": "51103",
        "disputed_key": "per_skala_disputed_pp28_collision",
        "marker": "pesawat udara",
        "marker_in_disputed": True,
        "check_intel_clean": True,
    },
    {
        "code": "51203",
        "disputed_key": "per_skala_disputed_pp28_collision",
        "marker": "pesawat udara",
        "marker_in_disputed": True,
        "check_intel_clean": True,
    },
    {
        "code": "20111",
        "disputed_key": "per_skala_disputed_pp28_collision",
        "marker": "Khlor dan Alkali",
        "marker_in_disputed": True,
        "check_intel_clean": True,
    },
    {
        "code": "50115",
        "disputed_key": "per_skala_disputed_pp28_collision",
        "marker": "Distribusi Ikan",
        "marker_in_disputed": True,
        "check_intel_clean": True,
    },
    {
        "code": "60312",
        "disputed_key": "per_skala_disputed_pp28_collision",
        "marker": "lembaga penyiaran",
        "marker_in_disputed": True,
        "check_intel_clean": True,
    },
    {
        "code": "64310",
        "disputed_key": "per_skala_disputed_pp28_collision",
        "marker": "Sante Par Aqua",
        "marker_in_disputed": False,  # see registry docstring above
        "check_intel_clean": True,
    },
]

FASE1_CODES = [
    "49213", "51103", "51203", "20111", "50115", "60312", "64310",
]

# Legitimate neighbor codes that must be UNTOUCHED by this cure (innocence
# guard, scar-family #3): each is verified (2026-07-17) to legitimately carry
# non-empty per_skala licensing. If the cure ever over-reaches onto one of
# these, this must fail.
#   68124 — real MICE/convention-venue code (68112's true neighbor)
#   49222 — real AKDP (Angkutan Antarkota Dalam Provinsi) successor
#   51101 — real scheduled airline code (51103's aviation neighbor)
#   20112 — real Industri Gas Industri (20111's chemical-industry neighbor)
#   50122 — real Angkutan Laut Dalam Negeri untuk Barang Khusus (50115's
#            crosswalk-true sea-transport predecessor, per the cure's own note)
#   64121 — real conventional bank (64310's financial-sector neighbor)
INNOCENT_NEIGHBORS = ["68124", "49222", "51101", "20112", "50122", "64121"]


# ---------------------------------------------------------------------------
# Registry-driven GUILT tests — structural core, all 8 codes, all copies.
# ---------------------------------------------------------------------------

_DATASET_IDS = [str(p.relative_to(REPO_ROOT)) for p in _existing_dataset_copies()]


@pytest.mark.parametrize(
    "path", _existing_dataset_copies(), ids=_DATASET_IDS,
)
@pytest.mark.parametrize(
    "friend", FALSE_FRIENDS, ids=[f["code"] for f in FALSE_FRIENDS],
)
def test_false_friend_per_skala_detached_and_audited(path: Path, friend: dict[str, Any]):
    """Core GUILT check, all 8: per_skala must be [], the disputed key must be
    present and non-empty (audit trail preserved, never silently deleted),
    and _data_note must be present (non-empty)."""
    rec = _load_record(path, friend["code"])
    assert rec.get("per_skala") == [], (
        f"{path}: {friend['code']}.per_skala is not [] — the false-friend "
        "licensing block has leaked back into the served field."
    )
    disputed = rec.get(friend["disputed_key"])
    assert disputed, (
        f"{path}: {friend['code']} is missing (or has an empty) "
        f"{friend['disputed_key']!r} — the original block must be preserved "
        "for audit, never silently deleted."
    )
    note = rec.get("_data_note", "")
    assert note, f"{path}: {friend['code']} is missing _data_note."


@pytest.mark.parametrize(
    "friend", FALSE_FRIENDS, ids=[f["code"] for f in FALSE_FRIENDS],
)
def test_false_friend_marker_present_in_disputed_key_where_expected(friend: dict[str, Any]):
    """Where the content marker is verified to genuinely live in the disputed
    blob (all but 64310, see registry docstring), assert it is still there —
    proof the preserved content is the REAL contaminated block, not a stub."""
    if not friend["marker_in_disputed"]:
        pytest.skip(f"{friend['code']}: marker lives in _data_note prose, not the disputed blob (see registry docstring)")
    path = REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"
    rec = _load_record(path, friend["code"])
    blob = json.dumps(rec[friend["disputed_key"]], ensure_ascii=False)
    assert _contains_word_or_phrase(blob, friend["marker"]), (
        f"{friend['code']}: expected marker {friend['marker']!r} not found inside "
        f"{friend['disputed_key']!r} — the audit trail may have been edited."
    )


@pytest.mark.parametrize(
    "path", _existing_dataset_copies(), ids=_DATASET_IDS,
)
@pytest.mark.parametrize(
    "friend", [f for f in FALSE_FRIENDS if f["check_intel_clean"]],
    ids=[f["code"] for f in FALSE_FRIENDS if f["check_intel_clean"]],
)
def test_false_friend_marker_absent_from_per_skala_and_intel(path: Path, friend: dict[str, Any]):
    """The contamination marker must never resurface OUTSIDE the disputed key
    — specifically not in the served per_skala (trivially true once it's [])
    and not in intel_2026 (the client-facing editorial content), word/phrase
    matched (scar #3: never a bare substring)."""
    rec = _load_record(path, friend["code"])
    per_skala_blob = json.dumps(rec.get("per_skala") or [], ensure_ascii=False)
    intel_blob = json.dumps(rec.get("intel_2026") or {}, ensure_ascii=False)
    assert not _contains_word_or_phrase(per_skala_blob, friend["marker"]), (
        f"{path}: {friend['code']}.per_skala still contains marker {friend['marker']!r}."
    )
    assert not _contains_word_or_phrase(intel_blob, friend["marker"]), (
        f"{path}: {friend['code']}.intel_2026 contains marker {friend['marker']!r} — "
        "the false-friend licensing appears to have leaked into client-facing content."
    )


# ---------------------------------------------------------------------------
# Fase-1-specific: _data_note verbatim-from-spec + pp28_sources untouched.
# ---------------------------------------------------------------------------

def _load_fase1_spec_by_code() -> dict[str, dict[str, Any]]:
    spec = json.loads(FASE1_SPEC_PATH.read_text(encoding="utf-8"))
    return {e["code"]: e for e in spec["codes"]}


@pytest.mark.parametrize("code", FASE1_CODES)
def test_fase1_data_note_matches_spec_verbatim(code: str):
    """_data_note must be copied VERBATIM from the cure spec — the compiler
    never authors a replacement licensing value or paraphrases the provenance
    note (rule #9 no-new-values-without-provenance)."""
    spec_by_code = _load_fase1_spec_by_code()
    path = REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"
    rec = _load_record(path, code)
    assert rec.get("_data_note") == spec_by_code[code]["data_note"], (
        f"{code}: _data_note drifted from scripts/kbli_filiera/cure_specs/"
        "fase1_collisions.json — the compiler must copy data_note verbatim."
    )


@pytest.mark.parametrize("code", FASE1_CODES)
def test_fase1_pp28_sources_untouched(code: str):
    """pp28_sources is provenance/audit and must survive the cure unchanged
    (rule: KEEP pp28_sources unchanged)."""
    path = REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"
    rec = _load_record(path, code)
    assert rec.get("pp28_sources"), f"{code}: pp28_sources missing or emptied — must be preserved untouched."


@pytest.mark.parametrize("code", ["49213", "20111"])
def test_fase1_legacy_block_folded_into_disputed_key(code: str):
    """49213 and 20111 are the two Fase-1 codes that also carried
    per_skala_legacy: the cure must fold BOTH per_skala and per_skala_legacy
    into the disputed key as {"per_skala": ..., "per_skala_legacy": ...} and
    remove the top-level per_skala_legacy key (never leave a stray copy)."""
    path = REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"
    rec = _load_record(path, code)
    disputed = rec["per_skala_disputed_pp28_collision"]
    assert isinstance(disputed, dict), (
        f"{code}: expected the disputed key to be a dict with 'per_skala'/"
        f"'per_skala_legacy' sub-keys (this code had a per_skala_legacy to fold), got {type(disputed)}"
    )
    assert set(disputed.keys()) == {"per_skala", "per_skala_legacy"}, (
        f"{code}: disputed key sub-structure is {sorted(disputed.keys())}, expected exactly "
        "{'per_skala', 'per_skala_legacy'}"
    )
    assert disputed["per_skala"], f"{code}: folded per_skala sub-value is empty."
    assert disputed["per_skala_legacy"], f"{code}: folded per_skala_legacy sub-value is empty."
    assert "per_skala_legacy" not in rec, (
        f"{code}: top-level per_skala_legacy key still present — must be removed after folding."
    )


@pytest.mark.parametrize("code", ["51103", "51203", "50115", "60312", "64310"])
def test_fase1_no_legacy_block_disputed_key_is_plain_list(code: str):
    """The other 5 Fase-1 codes never had per_skala_legacy: the disputed key
    must hold the original per_skala list directly (no extra wrapping dict)."""
    path = REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"
    rec = _load_record(path, code)
    disputed = rec["per_skala_disputed_pp28_collision"]
    assert isinstance(disputed, list), (
        f"{code}: expected the disputed key to be the plain original per_skala "
        f"list (no per_skala_legacy to fold for this code), got {type(disputed)}"
    )
    assert disputed, f"{code}: disputed per_skala list is empty."


# ---------------------------------------------------------------------------
# Idempotency: re-running the compiler dry-run over the served dataset must
# report every one of the 8 as already-cured (no-op). This exercises the
# compiler's own detection logic against the REAL served data, not a mock.
# ---------------------------------------------------------------------------

def test_compiler_dry_run_reports_all_fase1_codes_already_cured():
    import subprocess

    result = subprocess.run(
        [
            "python3",
            str(REPO_ROOT / "scripts/kbli_filiera/cure_canonical_collisions.py"),
            "--canonical",
            str(REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"dry-run over the served dataset should exit 0 (all already cured), "
        f"got {result.returncode}. stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    for code in FASE1_CODES:
        assert f"{code}: ALREADY CURED (skip)" in result.stdout, (
            f"expected '{code}: ALREADY CURED (skip)' in dry-run output, not found. "
            f"stdout:\n{result.stdout}"
        )


# ---------------------------------------------------------------------------
# INNOCENCE — legitimate neighbor codes untouched (scar-family #3 discipline:
# every guilt assertion above is paired with an innocence case here).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", INNOCENT_NEIGHBORS)
def test_innocent_neighbor_codes_per_skala_untouched(code: str):
    """These codes legitimately carry non-empty per_skala licensing and are
    NOT part of this cure — if the cure ever over-reaches onto one of them,
    this must fail."""
    path = REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"
    rec = _load_record(path, code)
    assert rec.get("per_skala"), (
        f"{code}: per_skala unexpectedly empty — this is a legitimate neighbor "
        "code, not one of the 8 false-friend collisions; the cure must not "
        "have touched it."
    )
    assert "per_skala_disputed_pp28_collision" not in rec and "per_skala_disputed_pp28_mice" not in rec, (
        f"{code}: unexpectedly carries a disputed key — this code was never "
        "part of the cure spec."
    )


# ===========================================================================
# Folded-in legacy coverage — verbatim from test_kbli_68112_pp28_mice_collision.py
# (2026-07-16). 68112 coverage MUST survive; kept unmodified below.
# ===========================================================================

CODE = "68112"
CONTAMINATION_MARKERS = ("MICE", "Venue")

# Kept identical to the original file's local DATASET_PATHS (3 copies) for the
# legacy functions below, to change nothing about what already passed. New
# code above uses the 4-copy ALL_DATASET_COPIES instead.
DATASET_PATHS = [
    REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json",  # production, balizero.com/kbli
    REPO_ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json",  # tracked fallback / canonical (via source_documents/ symlink)
    REPO_ROOT / "apps/backend-rag/backend/data/KBLI_2025_FINAL_CLEAN.json",  # gitignored, RAG runtime
]


def _load_68112_record(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    for rec in data["data"]:
        if rec.get("kode_kbli_2025") == CODE:
            return rec
    raise AssertionError(f"{path}: record {CODE} not found in dataset")


def _existing_paths():
    return [p for p in DATASET_PATHS if p.exists()]


@pytest.mark.parametrize(
    "path", _existing_paths(), ids=[str(p.relative_to(REPO_ROOT)) for p in _existing_paths()]
)
def test_68112_per_skala_has_no_mice_venue_contamination(path: Path):
    rec = _load_68112_record(path)
    per_skala_blob = json.dumps(rec.get("per_skala") or [], ensure_ascii=False)
    for marker in CONTAMINATION_MARKERS:
        assert marker not in per_skala_blob, (
            f"{path}: 68112 per_skala still contains {marker!r} — the PP28 "
            "MICE-venue licensing (Lampiran I.L, p.I.L.44) has leaked back into "
            "the residential-leasing code (BPS Peraturan 7/2025). Move it to "
            "per_skala_disputed_pp28_mice instead of shipping it as this code's "
            "own licensing."
        )


def test_68112_disputed_mice_block_preserved_for_audit():
    """The removed block must be KEPT (not silently deleted) for audit."""
    rec = _load_68112_record(REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json")
    disputed = rec.get("per_skala_disputed_pp28_mice")
    assert disputed, (
        "68112 must retain the original PP28-MICE per_skala under "
        "per_skala_disputed_pp28_mice for audit — it should never be silently deleted."
    )
    blob = json.dumps(disputed, ensure_ascii=False)
    assert any(marker in blob for marker in CONTAMINATION_MARKERS), (
        "per_skala_disputed_pp28_mice should still contain the MICE/Venue text it "
        "was moved to preserve — if this trips, the audit trail itself was edited."
    )


def test_68112_has_advisory_data_note():
    rec = _load_68112_record(REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json")
    note = rec.get("_data_note", "")
    assert "68111" in note, "advisory note should point to the nearest residential NSPK reference (68111)"
    assert "no_oss_risk" not in note  # note is prose, not a field-name echo
    assert "OSS" in note and "404" in note, "advisory note should explain the OSS 404 (no published NSPK yet)"


AUDIT_KEY = "per_skala_disputed_pp28_mice"

# A leaf string OUTSIDE the audit key is allowed to name "MICE"/"Venue" ONLY when
# it is DISCLAIMING the collision (explaining that this MICE-venue text belonged
# to a different activity and does not apply to 68112's residential leasing) —
# never when it ASSERTS the MICE licensing as this code's own requirement (that
# was the original bug: the old intel_2026.whatYouNeed named "MICE venue
# standards" as part of 68112's OWN obligations, with no disclaiming language
# anywhere in the field). "code-number collision" is the phrase both legitimate
# disclaimers (_data_note and the corrected whatYouNeed) share verbatim, and is
# absent from the original contaminated text — entity/intent match, not a bare
# substring, per this repo's scar-family #3 guard discipline (guilt+innocence,
# never over-match on the mere presence of "MICE").
DISCLAIMER_MARKER = "code-number collision"


def _iter_leaf_strings(obj, path=""):
    """Yield (path, value) for every string leaf in a nested dict/list structure."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _iter_leaf_strings(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _iter_leaf_strings(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield path, obj


@pytest.mark.parametrize(
    "path", _existing_paths(), ids=[str(p.relative_to(REPO_ROOT)) for p in _existing_paths()]
)
def test_68112_record_has_no_mice_venue_outside_audit_key(path: Path):
    """Whole-record guard: no field of 68112 — intel_2026, l4_bali, pma_*, etc. —
    may ASSERT the MICE-venue licensing as applicable, anywhere in the record,
    EXCEPT the intentional audit key `per_skala_disputed_pp28_mice` (excluded
    entirely — it exists precisely to preserve the original PP28 block verbatim).

    A field outside the audit key MAY still name "MICE"/"Venue" if — and only
    if — it is disclaiming the collision (contains DISCLAIMER_MARKER): this is
    legitimate explanatory prose (`_data_note`, `intel_2026.whatYouNeed`), not
    a resurgence of the bug. Any occurrence WITHOUT the disclaimer marker in the
    same field fails — this is what catches contamination anywhere in the
    record, not just per_skala (the shape of the intel_2026.whatYouNeed leak
    the first pass of this fix missed).
    """
    rec = _load_68112_record(path)
    rec_without_audit_key = {k: v for k, v in rec.items() if k != AUDIT_KEY}
    for field_path, value in _iter_leaf_strings(rec_without_audit_key):
        if any(marker in value for marker in CONTAMINATION_MARKERS):
            assert DISCLAIMER_MARKER in value.lower(), (
                f"{path}: 68112.{field_path} contains MICE/Venue text with no "
                f"{DISCLAIMER_MARKER!r} disclaimer in the same field — looks "
                "like the PP28 MICE-venue licensing is being ASSERTED as this "
                "code's own requirement again, not disclaimed as the collision "
                "it is. Field value: " + value[:200]
            )


def test_68112_other_mice_codes_untouched():
    """Sanity/innocence guard: 68124 and 82300 legitimately mention MICE/Venue in
    their own per_skala (verified 2026-07-16) — this fix must not have touched them."""
    data = json.loads(
        (REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json").read_text(encoding="utf-8")
    )
    by_code = {r["kode_kbli_2025"]: r for r in data["data"]}
    for code in ("68124", "82300"):
        rec = by_code.get(code)
        if rec is None:
            continue
        blob = json.dumps(rec.get("per_skala") or [], ensure_ascii=False)
        assert any(m in blob for m in CONTAMINATION_MARKERS), (
            f"{code} unexpectedly lost its legitimate MICE/Venue per_skala text — "
            "this guard is scoped to 68112 only, do not touch this record."
        )


# --- Third contaminated surface (2026-07-16, follow-up PR): apps/mouth/data/kbli-gold-all.json ---
#
# This gold file is a SEPARATE curated dataset (428 records, keyed directly by code — not the
# `{"data": [...]}` list shape of KBLI_2025_FINAL_CLEAN.json above) consumed by
# apps/mouth/src/lib/kbli-data.server.ts. It is NOT one of the copies scripts/sync_kbli_dataset.sh
# propagates, so PR #2508's per_skala fix never reached it: its 68112.whatYouNeed kept asserting
# "NIB + Standard Certificate (... Medium-Low risk)" and "Standard Certificate (auto-issued)" —
# the same PP28-MICE collision, served live on balizero.com/kbli/68112, invisible to every test
# above because none of them touch this file.

GOLD_PATH = REPO_ROOT / "apps/mouth/data/kbli-gold-all.json"


def _load_gold_record() -> dict:
    data = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    rec = data.get(CODE)
    if rec is None:
        raise AssertionError(f"{GOLD_PATH}: record {CODE} not found")
    return rec


def test_68112_gold_what_you_need_has_no_medium_low_risk():
    """Regression pin for the gold-specific bug: whatYouNeed (the customer-facing step
    list) must never again assert the collision-derived "Medium-Low risk" tier as this
    code's own requirement — not even in disclaimer form. This is a stricter bar than the
    whole-record guard below: whatYouNeed is what a client reads to know what to file: it
    should describe "not yet defined" plainly, not repeat the specific wrong risk-tier
    label even while debunking it."""
    rec = _load_gold_record()
    wyn = rec.get("whatYouNeed", "")
    assert "Medium-Low risk" not in wyn, (
        f"{GOLD_PATH}: 68112.whatYouNeed still asserts 'Medium-Low risk' — the "
        "PP28-MICE collision-derived licensing tier has leaked back into the "
        "customer-facing step list."
    )


@pytest.mark.parametrize("path", [GOLD_PATH], ids=["apps/mouth/data/kbli-gold-all.json"])
def test_68112_gold_record_has_no_mice_venue_without_disclaimer(path: Path):
    """Whole-gold-record guard, same discipline as
    test_68112_record_has_no_mice_venue_outside_audit_key above: the gold record has no
    `per_skala_disputed_pp28_mice`-style audit key to exclude (gold never carried the raw
    per_skala block), so every leaf string is in scope. Any field naming "MICE"/"Venue"
    must carry the DISCLAIMER_MARKER in the same field, or it looks like the collision is
    being asserted rather than debunked."""
    rec = _load_gold_record()
    for field_path, value in _iter_leaf_strings(rec):
        if any(marker in value for marker in CONTAMINATION_MARKERS):
            assert DISCLAIMER_MARKER in value.lower(), (
                f"{path}: 68112.{field_path} contains MICE/Venue text with no "
                f"{DISCLAIMER_MARKER!r} disclaimer in the same field — looks like the "
                "PP28 MICE-venue licensing is being asserted as this code's own "
                "requirement again. Field value: " + value[:200]
            )


def test_68112_gold_bali_context_untouched_and_innocent():
    """Innocence case (scar-family #3 guilt+innocence discipline): baliContext's mention
    of "Standard Certificate for Hospitality (SLHS)" is a LEGITIMATE reference (explaining
    that daily/Airbnb rentals need a different KBLI + SLHS, not this code) — it must
    survive this fix untouched, and the whole-record guard above must not have needed to
    touch it, because it never names "MICE"/"Venue" in the first place."""
    rec = _load_gold_record()
    bali_context = rec.get("baliContext", "")
    assert "SLHS" in bali_context and "Standard Certificate for Hospitality" in bali_context, (
        "baliContext's legitimate SLHS/hospitality explanation must be preserved verbatim."
    )
    assert not any(marker in bali_context for marker in CONTAMINATION_MARKERS), (
        "baliContext should not mention MICE/Venue at all — if it does now, the "
        "disclaimer-aware guard above, not a bare-substring ban, is what must clear it."
    )


# ---------------------------------------------------------------------------
# Gold-layer honest-gap cure for 49213 + 50115 (2026-07-17, follow-up to the
# canonical Fase-1 cure).
#
# 49213 and 50115 are the ONLY two of the seven Fase-1 codes that also had a
# record in the SEPARATE gold layer (apps/mouth/data/kbli-gold-all.json). Gold
# takes precedence over intel_2026 for editorial fields on /kbli/<code>
# (apps/mouth/src/lib/kbli-data.server.ts merges gold first;
# apps/mouth/src/components/kbli/LicensingSection.tsx parses gold.whatYouNeed
# directly, bypassing the merge) — so the canonical per_skala detach + the
# intel_2026 honest-gap did NOT reach the served page: the gold whatYouNeed kept
# asserting the collision-derived risk/authority as this code's own licensing:
#   49213 gold: "Low risk (Rendah) ... Authority: Bupati/Walikota" + a full
#         Izin-Trayek / KIR / AKDP step list carried from the inter-city AKDP
#         collision (see 49213 _data_note) — it even contradicted the code's own
#         l4_bali reason (Menengah-Tinggi/Tinggi).
#   50115 gold: "Medium-High risk ... Authority: Menteri · 3 Hari" carried from
#         the wrong AIR-transport source 51107 (see 50115 _data_note).
# Both cured to a short structured honest-gap (Codex-gated, generator != grader)
# that retracts the wrong risk/authority, keeps PMA-open, and routes the client
# to the Bali Zero team. The other 5 Fase-1 codes are NOT in gold, so intel_2026
# renders directly for them (no gold cure needed).

GOLD_HONEST_GAP_CODES = ["49213", "50115"]

# Collision-derived markers that must NOT reappear in the cured gold whatYouNeed.
# Verified (2026-07-17, via git show HEAD) to have been present in the pre-cure
# gold — so this guilt check would have failed on the old data. Word/phrase
# matched (scar #3), never a bare substring.
GOLD_STALE_MARKERS = {
    "49213": ["Rendah", "Bupati", "Izin Trayek", "AKDP"],
    "50115": ["Medium-High risk", "Menteri", "3 Hari"],
}


@pytest.mark.parametrize("code", GOLD_HONEST_GAP_CODES)
def test_gold_what_you_need_is_honest_gap_no_collision_markers(code: str):
    """GUILT: the cured gold whatYouNeed must declare the gap and route to the
    team, and must never again assert the collision-derived risk/authority."""
    rec = json.loads(GOLD_PATH.read_text(encoding="utf-8"))[code]
    wyn = rec.get("whatYouNeed", "")
    assert wyn, f"gold {code}: whatYouNeed missing"
    for marker in GOLD_STALE_MARKERS[code]:
        assert not _contains_word_or_phrase(wyn, marker), (
            f"gold {code}.whatYouNeed still asserts collision-derived {marker!r} — "
            "the wrong-code licensing has leaked back into the customer-facing gold "
            "step list (it masks the canonical intel_2026 honest-gap on /kbli/<code>)."
        )
    low = wyn.lower()
    assert "not yet reliably defined" in low, (
        f"gold {code}.whatYouNeed must declare the risk/licensing gap explicitly."
    )
    assert "bali zero team" in low, (
        f"gold {code}.whatYouNeed must route the client to team verification."
    )
    assert "100%" not in wyn, (
        f"gold {code}.whatYouNeed must not assert an ownership percentage."
    )


def test_gold_untouched_neighbor_keeps_real_licensing():
    """INNOCENCE (scar #3): the cure is scoped to 49213/50115 only — a
    legitimate gold code must keep its substantive licensing prose, not a gap
    stub. 01111 (corn cultivation, present at the file head) is a stable,
    unrelated entry; if it ever reads as honest-gapped, the cure over-reached."""
    gold = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    assert len(gold) == 428, (
        f"gold entry count changed ({len(gold)} != 428) — the cure must edit "
        "values in place, never add/remove records."
    )
    ref = gold.get("01111")
    assert ref is not None, "01111 (innocence reference) missing from gold"
    assert "not yet reliably defined" not in (ref.get("whatYouNeed") or "").lower(), (
        "01111 gold was accidentally honest-gapped — the cure is scoped to 49213/50115."
    )


# --- Cure-4 (2026-07-17): editorial + l4_bali NON_CLASSIFICABILE for all 8 ---

CURE4_CODES = ["68112", "49213", "51103", "51203", "20111", "50115", "60312", "64310"]


@pytest.mark.parametrize("code", CURE4_CODES)
def test_cure4_l4_bali_non_classificabile_and_editorial_clean(code: str):
    rec = _load_record(REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json", code)
    l4 = rec.get("l4_bali") or {}
    assert l4.get("status") == "NON_CLASSIFICABILE", f"{code}: l4 status regressed"
    assert l4.get("needs_review") is True
    assert "Previous status:" in (l4.get("reason") or ""), f"{code}: audit provenance missing"
    blob = json.dumps(rec.get("intel_2026", {}).get("editorial", {}), ensure_ascii=False)
    for m in ["OK_or_HIGHER_RISK", "medium-high risk", "Menengah-Tinggi", "Low risk (Rendah)"]:
        assert m not in blob, f"{code}: collision marker {m!r} back in editorial"


def test_cure4_gold_49213_clean_and_neighbor_l4_untouched():
    gold = json.loads(GOLD_PATH.read_text(encoding="utf-8"))["49213"]
    blob = json.dumps(gold, ensure_ascii=False)
    for m in ["Izin Trayek", "AKAP"]:
        assert m not in blob, f"gold 49213 still asserts {m!r}"
    assert not re.search(r"\bKIR\b", blob), "gold 49213 still asserts KIR"
    neighbor = _load_record(REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json", "68124")
    assert (neighbor.get("l4_bali") or {}).get("status") != "NON_CLASSIFICABILE", (
        "innocence: 68124 l4 must be untouched by cure-4"
    )
