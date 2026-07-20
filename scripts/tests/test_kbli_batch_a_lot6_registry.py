"""Regression registry — GARUDA-FILIERA Batch A Lot 6 false-friend per_skala collisions +
one certification revocation (13 codes, divisions 72->85, 2026-07-19), driven by
scripts/kbli_filiera/cure_specs/batch_a_lot6.json and applied via
scripts/kbli_filiera/cure_canonical_collisions.py --spec batch_a_lot6.json.

Modeled closely on test_kbli_batch_a_lot5_registry.py (Lot 5 registry, 2026-07-19) — the
ALL_DATASET_COPIES list and the _existing_dataset_copies / _load_by_code / _load_record /
_contains_word_or_phrase helpers below are COPIED VERBATIM from that file (comment marks the
origin instead of importing, to keep this file self-contained and independently readable as its
own regression pin, same convention Lot 1-5 used).

Cure pattern for all 13 detach-only codes (identical to Lot 1-5, see
cure_canonical_collisions.py docstring):
  1. per_skala -> []  (frontend guards licensing.length > 0 -> honest "not yet defined" gap
     instead of wrong data)
  2. the ORIGINAL per_skala preserved verbatim under the disputed key
     "per_skala_disputed_pp28_collision" -- never silently deleted
  3. _data_note added (verbatim from the cure spec -- never invented here)
  4. intel_2026.whatYouNeed rewritten to the spec's honest-gap text (verbatim)
  5. pp28_sources / judul / uraian / pma_* / status_mapping / every other field left untouched

NONE of Lot 6's 13 codes get a status_mapping_correction or whatChanged_correction key in the
spec (same discipline as Lot 1-5): the veterinary trio's true second parent (01621) and 85321's
true crosswalk parents ({51108, 85230}) are corroborated this session by direct render read, but
the relationship SHAPE / cited NUMBER stays untouched — the same rule that withheld a correction
from Lot 3's 64940, Lot 4's 64955, and Lot 5's 68123/68126/66192. pp28_sources is NOT touched on
any of the 13 codes.

THIS LOT IS THE FIRST TO INCLUDE A CERTIFICATION-REVOCATION CODE (80190): the runner's
first-signed report CERTIFIED it (D1/D5 concordantly clean), but the second-signed conductor
gate's adversarial review revoked that certification as materially false (the record's four
per_skala tiers assert Tinggi/7-day/scope/fiktif_positif facts with EMPTY perizinan arrays and no
resolvable source) and it JOINS the 13/13 detach. The #1813 fill (scripts/fill_kbli_80190.py) is
preserved under the disputed key, never destroyed.

IMPORTANT -- these tests are EXPECTED TO BE SKIPPED until the Batch A Lot 6 cure is applied to
the canonical dataset (this file lands ahead of / together with the data PR that runs
cure_canonical_collisions.py --apply). The whole module is skipped via a module-level
pytestmark until the canonical 80190 record shows the post-cure shape (per_skala == [] and
intel_2026.whatYouNeed matches the spec's honest-gap text) -- at that point the module arms
itself automatically, no edit needed. 80190 is used as the canary (same convention as Lot 3's
64940 / Lot 4's 64955 / Lot 5's 66192 canaries) -- it is the flagship finding of this lot (the
program's first certification revocation).

Scar-family #3 (guard-over-match/under-match) discipline applies throughout: every guilt
assertion is paired with an innocence assertion on a legitimate neighbor code, and every content
marker is a multi-word phrase verified (by direct read of the applied canonical record in this
session) to actually appear verbatim in that code's _data_note -- never a bare substring.

ADJUDICATION HISTORY (2026-07-19): conductor D6 gate on lane run wf_dfae986f-5d3 (30 seats, 0
errors — FIRST lot run with seat-surface-symmetric controls, #2778), SIGNED as a SECOND SIGNING
after adversarial review (codex sol xhigh read-only, 2 BLOCKER + 3 MAJOR + 1 MINOR, all cured).
Outcome: runner emitted 12 QUARANTINED + 1 CERTIFIED (80190); the adversarial review REJECTED
the certification. Operational disposition: 13/13 in-scope QUARANTINED, ZERO valid
certifications in the program to date. Categories: source_absent_in_vault (2: 72101, 72103) --
mapping_metadata_false (3: 72105, 75002, 77397) -- code_collision (1: 75001) --
wrong_authority_level (1: 75009, FIRST Batch-A sighting) -- payload_cross_contamination (5:
78109, 82911, 85321, 85323, 85324) -- CERTIFIED-then-REVOKED (1: 80190). Full report:
research/operations/2026-07-19-kbli-batch-a-lot6-conductor-gate.md (read from the kbli/lot6-lane
branch in this session via `git show origin/kbli/lot6-lane:...` -- that branch's PR had not yet
merged when this cure was authored, same chain-of-custody pattern Lot 2-5 used for their own
not-yet-merged gate reports). This PR ALSO ships the certification-contract patch to
infra/workflows/kbli-batch-a-lot.js mandated by the gate's adversarial BLOCKER 2 (§5.3) -- see
infra/workflows/tests/test-kbli-certification-contract.mjs for that regression coverage.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LOT6_SPEC_PATH = REPO_ROOT / "scripts/kbli_filiera/cure_specs/batch_a_lot6.json"
CANONICAL_PATH = REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"
DISPUTED_KEY = "per_skala_disputed_pp28_collision"

# --- verbatim from test_kbli_batch_a_lot5_registry.py (2026-07-19) ---------

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
    """Word-boundary-safe containment check (scar-family #3 antidote): a single-word marker is
    matched with regex word boundaries so it cannot false-positive inside a longer word (e.g.
    bare 'SPA' inside 'aerospace'). A multi-word phrase (contains a space) is matched as a plain
    substring -- the multi-word shape itself is already a strong disambiguator."""
    if " " in marker:
        return marker in haystack
    return re.search(rf"\b{re.escape(marker)}\b", haystack) is not None


# --- end verbatim block -----------------------------------------------------


def _load_lot6_spec_by_code() -> dict[str, dict[str, Any]]:
    spec = json.loads(LOT6_SPEC_PATH.read_text(encoding="utf-8"))
    assert spec["disputed_key"] == DISPUTED_KEY, (
        f"spec disputed_key drifted to {spec['disputed_key']!r}, tests hardcode {DISPUTED_KEY!r}"
    )
    return {e["code"]: e for e in spec["codes"]}


def _cure_applied() -> bool:
    """True once the canonical 80190 record shows the post-cure shape (per_skala == [] AND
    intel_2026.whatYouNeed matches the spec's honest-gap text verbatim). Pre-apply, per_skala is
    non-empty; post-apply, per_skala == [] and whatYouNeed is the honest-gap text. If the
    canonical file, the spec, or the 80190 record is missing entirely, treat the cure as NOT
    applied (module stays skipped rather than erroring at collection time)."""
    if not CANONICAL_PATH.exists() or not LOT6_SPEC_PATH.exists():
        return False
    try:
        rec = _load_record(CANONICAL_PATH, "80190")
        spec_by_code = _load_lot6_spec_by_code()
    except (AssertionError, KeyError):
        return False
    intel = rec.get("intel_2026") or {}
    return (
        rec.get("per_skala") == []
        and intel.get("whatYouNeed") == spec_by_code.get("80190", {}).get("whatYouNeed")
    )


pytestmark = pytest.mark.skipif(
    not _cure_applied(),
    reason="batch_a_lot6 cure not yet applied — tests arm after the data PR",
)


LOT6_CODES = [
    "72101", "72103", "72105", "75001", "75002", "75009", "77397", "78109",
    "82911", "85321", "85323", "85324", "80190",
]

# pp28_sources pre-cure value per code, hardcoded from a direct read of the canonical dataset
# (2026-07-19) — must survive the cure untouched (including on 75001/75002/75009/85321, whose
# TRUE parents are image/record-verified but never injected, and 80190, whose pp28_sources is
# EMPTY both before and after — the empty array itself is what the certification-contract patch
# no longer treats as a free pass).
LOT6_PP28_SOURCES = {
    "72101": ["72101"],
    "72103": ["72103"],
    "72105": ["72105"],
    "75001": ["75000"],
    "75002": ["75000"],
    "75009": ["75000"],
    "77397": ["77301"],
    "78109": ["78429"],
    "82911": ["82911"],
    "85321": ["85321"],
    "85323": ["85240"],
    "85324": ["85230"],
    "80190": [],
}

# pre-cure status_mapping per code, hardcoded from a direct read of the canonical dataset
# (2026-07-19) — NONE of Lot 6's 13 codes get a metadata correction in this lot (same discipline
# as Lot 1-5).
LOT6_PRE_CURE_STATUS_MAPPING = {
    "72101": "MATCH_LANGSUNG",
    "72103": "MATCH_LANGSUNG",
    "72105": "MATCH_LANGSUNG",
    "75001": "CODICE_RINUMERATO",
    "75002": "CODICE_RINUMERATO",
    "75009": "MATCH_CON_AGGREGAZIONE",
    "77397": "CODICE_RINUMERATO",
    "78109": "MATCH_CON_AGGREGAZIONE",
    "82911": "MATCH_LANGSUNG",
    "85321": "MATCH_LANGSUNG",
    "85323": "CODICE_RINUMERATO",
    "85324": "CODICE_RINUMERATO",
    "80190": "BPS_ONLY",
}

# The 3 R&D codes sharing the byte-identical "Penyelenggaraan Bank Plasma" industrial-services
# contaminated payload (verified this session, json-dump byte-comparison).
LOT6_BANK_PLASMA_PAYLOAD_CODES = ["72101", "72103", "72105"]

# 75002 and 75009 share a byte-identical veterinary-health served payload (verified this
# session); 75001 is near-identical but differs by a `dati_inferiti: true` marker present only
# on 75001's rows, so it is checked separately rather than folded into this byte-identical set.
LOT6_VET_BYTE_IDENTICAL_CODES = ["75002", "75009"]

# 85323 and 85324 share a byte-identical aviation flight-school served payload (verified this
# session, json-dump byte-comparison).
LOT6_AVIATION_PAYLOAD_CODES = ["85323", "85324"]

# Content markers: multi-word phrases verified (direct read of the applied canonical dataset,
# 2026-07-19) to be verbatim substrings of that code's _data_note. Checked ONLY against
# _data_note.
LOT6_DATA_NOTE_MARKERS = {
    "72101": "D1 accepted the canonical's relabel-note prose, D5 flagged source_absent_in_vault",
    "72103": "the second of the lot's true D1-clean-vs-D5-problem seat-agreement divergences",
    "72105": "a doubly-corroborated finding rather than a D1-clean/D5-problem divergence",
    "75001": "the digit-string collision shape a 2-parent unacknowledged split produces",
    "75002": "the disease D5 found is the missing second parent, invisible to a crosswalk-only read",
    "75009": "FIRST BATCH-A SIGHTING of the wrong_authority_level category",
    "77397": "shows no independently-observable topical-contamination signature on its face",
    "78109": "a DIFFERENT ketenagakerjaan activity (worker training, not placement)",
    "82911": "all wholly unconnected to debt-collection agency activity",
    "85321": "TRUE crosswalk parents for this code are therefore {51108, 85230}",
    "85323": '51108 Angkutan Udara Bukan Niaga" residual bucket',
    "85324": "meaning 85230 fans to at least two 2025 targets in this lot",
    "80190": "the certification was materially false",
}

# Innocence controls (scar-family #3 discipline): legitimate neighbor codes untouched by this
# cure.
#   72102, 72104, 72106, 72109 — division-72 R&D neighbors, untouched
#   75000 is a 2020-vintage number, not itself a 2025 record — no neighbor test needed for it
#   78101, 78105 — division-78 labour-placement/recruitment neighbors, untouched
#   82912 — division-82 neighbor (credit-bureau activity), untouched
#   85322 — division-85 neighbor between 85321 and 85323 (private general vocational secondary
#           education), untouched
#   80110 — "Aktivitas Investigasi dan Keamanan Swasta", the explicit sibling fill_kbli_80190.py
#           itself names as distinct/NOT remapped — untouched
#   59140, 59201 — the Batch-A gate reports' OWN reused innocence controls (film screening / sound
#           recording), untouched
INNOCENT_NEIGHBORS = [
    "72102", "72104", "72106", "72109", "78101", "78105", "82912", "85322",
    "80110", "59140", "59201",
]

_DATASET_IDS = [str(p.relative_to(REPO_ROOT)) for p in _existing_dataset_copies()]


# ---------------------------------------------------------------------------
# 1. per_skala detached and audited (all 13 codes, all dataset copies)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", _existing_dataset_copies(), ids=_DATASET_IDS)
@pytest.mark.parametrize("code", LOT6_CODES)
def test_lot6_per_skala_detached_and_audited(path: Path, code: str):
    """GUILT, core: per_skala must be [] and the disputed key must be present with a non-empty
    preserved blob (the original rows, kept for audit)."""
    rec = _load_record(path, code)
    assert rec.get("per_skala") == [], (
        f"{path}: {code}.per_skala is not [] — the Lot-6 false-friend licensing block has "
        "leaked back into the served field."
    )
    disputed = rec.get(DISPUTED_KEY)
    assert disputed, (
        f"{path}: {code} is missing (or has an empty) {DISPUTED_KEY!r} — the original per_skala "
        "rows must be preserved for audit, never silently deleted."
    )
    assert isinstance(disputed, list) and len(disputed) > 0, (
        f"{path}: {code}.{DISPUTED_KEY} expected to be a non-empty list of the original "
        f"per_skala rows, got {type(disputed)} / {disputed!r}"
    )


# ---------------------------------------------------------------------------
# 2. _data_note verbatim from spec
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT6_CODES)
def test_lot6_data_note_matches_spec_verbatim(code: str):
    """_data_note must be copied VERBATIM from the cure spec — the compiler never authors a
    replacement licensing value or paraphrases the provenance note (rule #9
    no-new-values-without-provenance)."""
    spec_by_code = _load_lot6_spec_by_code()
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("_data_note") == spec_by_code[code]["data_note"], (
        f"{code}: _data_note drifted from scripts/kbli_filiera/cure_specs/batch_a_lot6.json — "
        "the compiler must copy data_note verbatim."
    )


# ---------------------------------------------------------------------------
# 3. intel_2026.whatYouNeed honest gap, verbatim from spec
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT6_CODES)
def test_lot6_whatYouNeed_honest_gap(code: str):
    """intel_2026.whatYouNeed must be rewritten to the spec's honest-gap text VERBATIM —
    replacing the stale client-facing prose derived from the detached (contaminated / revoked)
    per_skala rows."""
    spec_by_code = _load_lot6_spec_by_code()
    rec = _load_record(CANONICAL_PATH, code)
    intel = rec.get("intel_2026") or {}
    assert intel.get("whatYouNeed") == spec_by_code[code]["whatYouNeed"], (
        f"{code}: intel_2026.whatYouNeed does not match the spec's honest-gap text verbatim — "
        "the compiler must copy whatYouNeed verbatim, never paraphrase or invent it."
    )


# ---------------------------------------------------------------------------
# 4. pp28_sources untouched (all 13, including 75001/75002/75009/85321 whose true parents are
#    verified but never injected, and 80190 whose pp28_sources is empty both sides)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT6_CODES)
def test_lot6_pp28_sources_untouched(code: str):
    """pp28_sources is provenance/audit and must survive the cure unchanged — even for
    75001/75002/75009/85321, whose true parents are established this session, and 80190, whose
    empty pp28_sources is exactly the field the certification-contract patch stops trusting as a
    free pass: the compiler never authors new source values (Lot 1-5 detach convention)."""
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("pp28_sources") == LOT6_PP28_SOURCES[code], (
        f"{code}: pp28_sources drifted from its pre-cure value {LOT6_PP28_SOURCES[code]!r} — "
        "must be preserved untouched (rule: KEEP pp28_sources unchanged)."
    )


# ---------------------------------------------------------------------------
# 5. NO metadata corrections in this lot — status_mapping must survive untouched on ALL 13
#    codes (same discipline as Lot 1-5)
# ---------------------------------------------------------------------------

def test_lot6_no_code_gets_a_status_mapping_correction():
    """No code in this lot has an independently-verified SHAPE change (split/merge) established
    in the gate report — the veterinary trio's/85321's true parents are found but the
    relationship stays as cited (same rule as Lot 3's 64940, Lot 4's 64955, Lot 5's
    68123/68126/66192); the other codes have no established replacement at all. Every
    status_mapping must therefore match its pre-cure value exactly."""
    for code, expected in LOT6_PRE_CURE_STATUS_MAPPING.items():
        rec = _load_record(CANONICAL_PATH, code)
        assert rec.get("status_mapping") == expected, (
            f"{code}: status_mapping drifted to {rec.get('status_mapping')!r} — expected "
            f"untouched pre-cure value {expected!r} (this lot is detach-only, no metadata "
            "correction on any of its 13 codes)."
        )


def test_lot6_spec_never_declares_a_status_mapping_correction():
    """Guard against the spec itself silently growing a correction key that the compiler would
    then apply — Lot 6's adjudication established no independently-verified shape change for any
    of its 13 codes (rule #9)."""
    spec_by_code = _load_lot6_spec_by_code()
    for code in LOT6_CODES:
        entry = spec_by_code[code]
        assert "status_mapping_correction" not in entry, (
            f"{code}: spec unexpectedly declares status_mapping_correction "
            f"{entry.get('status_mapping_correction')!r} — Lot 6 has no independently-verified "
            "shape change for any code (rule #9)."
        )
        assert "whatChanged_correction" not in entry, (
            f"{code}: spec unexpectedly declares whatChanged_correction "
            f"{entry.get('whatChanged_correction')!r}"
        )
        assert "pp28_sources_correction" not in entry, (
            f"{code}: spec unexpectedly declares pp28_sources_correction "
            f"{entry.get('pp28_sources_correction')!r}"
        )
        assert entry.get("action") != "metadata_only", (
            f"{code}: spec unexpectedly declares action=metadata_only — Lot 6 detaches every one "
            "of its 13 codes, none is standalone-metadata-only."
        )


# ---------------------------------------------------------------------------
# 6. Idempotency: compiler dry-run over the served dataset reports every code already-cured
#    (no-op).
# ---------------------------------------------------------------------------

def test_lot6_compiler_dry_run_reports_already_cured():
    result = subprocess.run(
        [
            "python3",
            str(REPO_ROOT / "scripts/kbli_filiera/cure_canonical_collisions.py"),
            "--spec",
            str(LOT6_SPEC_PATH),
            "--canonical",
            str(CANONICAL_PATH),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"dry-run over the served dataset should exit 0 (all already cured), got "
        f"{result.returncode}. stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    for code in LOT6_CODES:
        assert f"{code}: ALREADY CURED (skip)" in result.stdout, (
            f"expected '{code}: ALREADY CURED (skip)' in dry-run output, not found. "
            f"stdout:\n{result.stdout}"
        )


# ---------------------------------------------------------------------------
# 7. INNOCENCE (scar #3 discipline) — legitimate neighbor codes must be untouched by this spec.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", INNOCENT_NEIGHBORS)
def test_lot6_innocent_neighbors_untouched(code: str):
    """These codes are legitimate neighbors (or the gate reports' own pre-verified innocence
    controls) and are NOT part of this cure — if the cure ever over-reaches onto one of them,
    this must fail."""
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("per_skala"), (
        f"{code}: per_skala unexpectedly empty — this is an innocence control, not one of the "
        "13 Lot-6 codes; the cure must not have touched it."
    )
    assert DISPUTED_KEY not in rec, (
        f"{code}: unexpectedly carries {DISPUTED_KEY!r} — this code was never part of the "
        "batch_a_lot6 cure spec."
    )


# ---------------------------------------------------------------------------
# 8. Content markers — verified verbatim in _data_note only (never invented inside the disputed
#    blobs, per the task instruction).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT6_CODES)
def test_lot6_data_note_content_marker_present(code: str):
    rec = _load_record(CANONICAL_PATH, code)
    note = rec.get("_data_note", "")
    marker = LOT6_DATA_NOTE_MARKERS[code]
    assert _contains_word_or_phrase(note, marker), (
        f"{code}: expected marker {marker!r} not found inside _data_note — the provenance note "
        f"may have drifted from the spec. _data_note: {note!r}"
    )


# ---------------------------------------------------------------------------
# 9. Byte-identical disputed payload clusters — the preserved disputed blocks for the three
#    contaminated-payload families this cure adjudicates must survive the cure exactly as found
#    (verified by direct read of the canonical payload in this session).
# ---------------------------------------------------------------------------

def test_lot6_bank_plasma_trio_shares_byte_identical_disputed_payload():
    """72101/72103/72105 (natural/medical/agricultural-veterinary R&D) carry the IDENTICAL
    'Penyelenggaraan Bank Plasma' industrial-services obligation payload — must survive
    byte-identical."""
    blobs = {
        code: json.dumps(_load_record(CANONICAL_PATH, code).get(DISPUTED_KEY), ensure_ascii=False)
        for code in LOT6_BANK_PLASMA_PAYLOAD_CODES
    }
    reference_code = LOT6_BANK_PLASMA_PAYLOAD_CODES[0]
    reference = blobs[reference_code]
    for code, blob in blobs.items():
        assert blob == reference, (
            f"{code}: preserved disputed block diverges from {reference_code}'s — the gate "
            "report's finding that these three R&D codes carry a byte-identical contaminated "
            "payload should be preserved by the cure (both are audit-only preserved blocks, "
            "never mutated)."
        )
    marker = "Bank Plasma"
    for code in LOT6_BANK_PLASMA_PAYLOAD_CODES:
        assert marker in blobs[code], (
            f"{code}: preserved disputed block no longer carries the industrial-services "
            f"contamination signature {marker!r} — audit trail may have drifted."
        )


def test_lot6_vet_pair_shares_byte_identical_disputed_payload():
    """75002/75009 carry the identical veterinary-health served payload (verified this session)
    — must survive byte-identical. 75001 is intentionally excluded here (near-identical, differs
    by a `dati_inferiti: true` marker) and checked separately below."""
    blobs = {
        code: json.dumps(_load_record(CANONICAL_PATH, code).get(DISPUTED_KEY), ensure_ascii=False)
        for code in LOT6_VET_BYTE_IDENTICAL_CODES
    }
    reference_code = LOT6_VET_BYTE_IDENTICAL_CODES[0]
    reference = blobs[reference_code]
    for code, blob in blobs.items():
        assert blob == reference, (
            f"{code}: preserved disputed block diverges from {reference_code}'s — 75002/75009 "
            "should share a byte-identical veterinary-health contaminated payload."
        )


def test_lot6_75001_near_identical_to_vet_pair_but_not_byte_identical():
    """GUILT+INNOCENCE for the `dati_inferiti` distinguishing marker: 75001's disputed rows must
    NOT be byte-identical to 75002/75009's (the `dati_inferiti: true` marker is present only on
    75001's rows), but must still carry the same underlying veterinary-health content signature."""
    blob_75001 = json.dumps(_load_record(CANONICAL_PATH, "75001").get(DISPUTED_KEY), ensure_ascii=False)
    blob_75002 = json.dumps(_load_record(CANONICAL_PATH, "75002").get(DISPUTED_KEY), ensure_ascii=False)
    assert blob_75001 != blob_75002, (
        "75001: preserved disputed block is unexpectedly byte-identical to 75002's — the "
        "`dati_inferiti: true` marker distinguishing them may have been lost."
    )
    assert "dati_inferiti" in blob_75001, (
        "75001: preserved disputed block no longer carries the `dati_inferiti` marker that "
        "distinguishes it from 75002/75009's rows."
    )
    assert "dati_inferiti" not in blob_75002, (
        "75002: preserved disputed block unexpectedly carries `dati_inferiti` — this marker is "
        "specific to 75001's rows per the gate's finding."
    )
    for marker in ("Klinik Hewan", "Rumah Sakit Hewan", "Laboratorium Veteriner"):
        assert marker in blob_75001, f"75001: disputed block missing veterinary content marker {marker!r}"


def test_lot6_aviation_pair_shares_byte_identical_disputed_payload():
    """85323/85324 (Islamic / other-religion vocational secondary education) carry the identical
    aviation flight-school served payload (verified this session) — must survive byte-identical."""
    blobs = {
        code: json.dumps(_load_record(CANONICAL_PATH, code).get(DISPUTED_KEY), ensure_ascii=False)
        for code in LOT6_AVIATION_PAYLOAD_CODES
    }
    reference_code = LOT6_AVIATION_PAYLOAD_CODES[0]
    reference = blobs[reference_code]
    for code, blob in blobs.items():
        assert blob == reference, (
            f"{code}: preserved disputed block diverges from {reference_code}'s — 85323/85324 "
            "should share a byte-identical aviation flight-school contaminated payload."
        )
    marker = "angkutan udara bukan niaga"
    for code in LOT6_AVIATION_PAYLOAD_CODES:
        assert marker in blobs[code].lower(), (
            f"{code}: preserved disputed block no longer carries the aviation-licensing "
            f"contamination signature {marker!r} — audit trail may have drifted."
        )


# ---------------------------------------------------------------------------
# 10. 80190 CERTIFICATION-REVOCATION — MANDATORY per the Lot 6 conductor gate SECOND SIGNING
#     (§3.4): the code was CERTIFIED by the runner's first-signed report and REVOKED by the
#     adversarial review; this cure detaches it and preserves the #1813 fill under the disputed
#     key, fully reconstructable, never destroyed.
# ---------------------------------------------------------------------------

def test_lot6_80190_data_note_records_certification_revocation():
    rec = _load_record(CANONICAL_PATH, "80190")
    note = rec.get("_data_note", "")
    for marker in (
        "CERTIFIED this code",
        "REVOKED that certification",
        "the certification was materially false",
        "fill_kbli_80190.py (PR #1813",
        "80190 <- 80200",
        "RE-CERTIFICATION PATH",
    ):
        assert marker in note, (
            f"80190: _data_note missing expected certification-revocation marker {marker!r} — "
            "the gate report's revocation must be recorded explicitly, not just alluded to. "
            f"_data_note: {note!r}"
        )
    # F12 wording discipline: never "not published" (a claim about regulatory non-existence)
    assert "not published" not in note.lower(), (
        "80190: _data_note uses F12-forbidden 'not published' wording — must say "
        "'not retrievable/verifiable from our sources' instead"
    )


def test_lot6_80190_disputed_block_preserves_the_1813_fill_reconstructably():
    """The #1813 fill (kategori_risiko=Tinggi, jangka_waktu='7', the security-devices scope_uraian,
    fiktif_positif=true, and the nb3_lampiran_keamanan_verified marker) must be fully preserved
    under the disputed key — detach supersedes but never destroys the operator fill."""
    rec = _load_record(CANONICAL_PATH, "80190")
    disputed = rec.get(DISPUTED_KEY)
    assert isinstance(disputed, list) and len(disputed) == 4, (
        f"80190: expected 4 preserved per_skala tiers (Mikro/Kecil/Menengah/Besar), got "
        f"{len(disputed) if isinstance(disputed, list) else type(disputed)}"
    )
    for tier in disputed:
        assert tier.get("kategori_risiko") == "Tinggi", f"80190: preserved tier lost kategori_risiko=Tinggi: {tier}"
        assert tier.get("jangka_waktu") == "7", f"80190: preserved tier lost jangka_waktu='7': {tier}"
        assert tier.get("fiktif_positif") is True, f"80190: preserved tier lost fiktif_positif=true: {tier}"
        assert tier.get("perizinan") == [], f"80190: preserved tier's perizinan unexpectedly non-empty: {tier}"
        assert tier.get("jangka_waktu_source") == "nb3_lampiran_keamanan_verified", (
            f"80190: preserved tier lost the nb3_lampiran_keamanan_verified marker: {tier}"
        )


def test_lot6_80190_status_mapping_and_pp28_sources_left_unchanged_despite_revocation():
    """Even for the revoked certification, rule #9 holds: this cure does not author a replacement
    citation or adjudicate the 80200->80190 crosswalk inheritance — status_mapping stays
    'BPS_ONLY' and pp28_sources stays the empty array it was pre-cure."""
    rec = _load_record(CANONICAL_PATH, "80190")
    assert rec.get("status_mapping") == "BPS_ONLY"
    assert rec.get("pp28_sources") == []


# ---------------------------------------------------------------------------
# 11. Veterinary-trio true-parent provenance — corroborated this session against the gate's
#     by-eye render finding (Lampiran 10 printed p.408, rows 1-6): all three codes' true 2020
#     lineage is a two-parent split {01621, 75000}, omitted down to 75000-only in the canonical.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", ["75001", "75002", "75009"])
def test_lot6_veterinary_trio_true_second_parent_recorded_as_provenance_only(code: str):
    rec = _load_record(CANONICAL_PATH, code)
    note = rec.get("_data_note", "")
    assert "01621" in note, (
        f"{code}: _data_note must name the true second parent 01621 as provenance"
    )
    assert "Jasa Pelayanan Kesehatan Ternak" in note, (
        f"{code}: _data_note must name 01621's title as provenance"
    )
    # rule #9: the true second parent is recorded as _data_note provenance ONLY, never injected
    # into pp28_sources/kbli_2020_source/status_mapping.
    assert rec.get("kbli_2020_source") == "75000", (
        f"{code}: kbli_2020_source drifted — must stay the single-parent citation '75000', "
        "the true second parent (01621) is provenance-only per rule #9"
    )
    assert "01621" not in (rec.get("pp28_sources") or []), (
        f"{code}: pp28_sources unexpectedly contains the true second parent 01621 — rule #9 "
        "forbids injecting a replacement/additional source value"
    )


def test_lot6_75009_authority_inheritance_recorded_as_provenance_only():
    """75009's wrong_authority_level finding (authority facts inherited from the PP28 2020-75000
    row across the unacknowledged 2-parent split) must be named in its _data_note."""
    rec = _load_record(CANONICAL_PATH, "75009")
    note = rec.get("_data_note", "")
    for marker in ("AUTHORITY facts", "p.693", "wrong_authority_level"):
        assert marker in note, f"75009: _data_note missing expected authority-inheritance marker {marker!r}"


# ---------------------------------------------------------------------------
# 12. 85321 true crosswalk parents — corroborated this session against the gate's by-eye render
#     finding (Lampiran 5 printed p.193): {51108, 85230}, neither of which is 85321's own
#     self-cited number.
# ---------------------------------------------------------------------------

def test_lot6_85321_true_crosswalk_parents_recorded_as_provenance_only():
    rec = _load_record(CANONICAL_PATH, "85321")
    note = rec.get("_data_note", "")
    for marker in ("51108", "85230", "Angkutan Udara Bukan Niaga"):
        assert marker in note, f"85321: _data_note missing expected true-parent marker {marker!r}"
    # rule #9: recorded as provenance only, never injected as a replacement citation.
    assert rec.get("pp28_sources") == ["85321"], (
        "85321: pp28_sources drifted from its self-referencing pre-cure value — the true "
        "{51108, 85230} parents are provenance-only per rule #9"
    )
    assert rec.get("status_mapping") == "MATCH_LANGSUNG"


# ---------------------------------------------------------------------------
# 13. 72101/72103/72105 `_source_relabeled` dispute — the 70100 precedent (Lot 5 gate §3.4)
#     applied to all three R&D codes: structured markers beat prose.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", ["72101", "72103", "72105"])
def test_lot6_rd_trio_source_relabeled_dispute_corroborated_against_canonical_markers(code: str):
    """Cross-check the _data_note's claims about each code's OWN structured markers against the
    live canonical record — the dispute-resolution text must describe reality, not merely assert
    it (anti-hallucination discipline)."""
    rec = _load_record(CANONICAL_PATH, code)
    assert "_l2_source" not in rec, (
        f"{code}: canonical unexpectedly now carries an _l2_source key — the data_note's "
        "refutation of the _source_relabeled prose claim depends on this key being genuinely "
        "absent"
    )
    assert rec.get("_l2_status") == "no_oss_risk", (
        f"{code}: _l2_status drifted to {rec.get('_l2_status')!r} — the data_note's "
        "dispute-resolution text cites this as 'no_oss_risk' verbatim"
    )
    note = rec.get("_data_note", "")
    assert "_source_relabeled" in note, (
        f"{code}: _data_note must explicitly name the _source_relabeled dispute"
    )
    lowered = note.lower()
    assert (
        "track-p doctrine" in lowered
        or "structured markers" in lowered
        or "structured-marker" in lowered
    ), (
        f"{code}: _data_note must record the structured-markers-beat-prose resolution explicitly"
    )
