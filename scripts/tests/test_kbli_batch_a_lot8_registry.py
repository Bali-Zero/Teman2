"""Regression registry — GARUDA-FILIERA Batch A Lot 8 false-friend per_skala collisions (9
codes, division 91 kawasan-konservasi neighbor + the full 931xx sport-facility/klub cluster,
2026-07-20), driven by scripts/kbli_filiera/cure_specs/batch_a_lot8.json and applied via
scripts/kbli_filiera/cure_canonical_collisions.py --spec batch_a_lot8.json.

Modeled closely on test_kbli_batch_a_lot7_registry.py (Lot 7 registry, 2026-07-19) — the
ALL_DATASET_COPIES list and the _existing_dataset_copies / _load_by_code / _load_record /
_contains_word_or_phrase helpers below are COPIED VERBATIM from that file (comment marks the
origin instead of importing, to keep this file self-contained and independently readable as its
own regression pin, same convention Lot 1-7 used).

Cure pattern for all 9 detach-only codes (identical mechanics to Lot 1-7, see
cure_canonical_collisions.py docstring):
  1. per_skala -> []  (frontend guards licensing.length > 0 -> honest "not yet defined" gap
     instead of wrong data)
  2. the ORIGINAL per_skala preserved verbatim under the disputed key
     "per_skala_disputed_pp28_collision" -- never silently deleted
  3. _data_note added (verbatim from the cure spec -- never invented here)
  4. intel_2026.whatYouNeed rewritten to the spec's honest-gap text (verbatim)
  5. pp28_sources / judul / uraian / pma_* / status_mapping / every other field left untouched

NONE of Lot 8's 9 codes gets a status_mapping_correction, whatChanged_correction, or
pp28_sources_correction key in the spec (same discipline as Lot 1-7), and none uses
action=metadata_only (verified directly against the spec JSON this session -- every entry has
only code/flavor/judul/data_note/whatYouNeed keys): 91425's true crosswalk parent (91033,
corroborated by direct render read, this session) is recorded as _data_note provenance ONLY,
never injected into pp28_sources/kbli_2020_source/status_mapping (rule #9) -- the same discipline
Lot 7 applied to its four true-parent findings (85330/85401/85404/91222), Lot 8 has exactly ONE
such finding.

ADJUDICATION HISTORY (2026-07-20): conductor D6 gate on lane run wf_d079f983-515 (15 seats
[13 Lot-8 members + 2 borrowed innocence controls], the FIRST launch wf_3a28b22f-e6d having been
stopped and discarded after an evidence-loss incident -- evidenceRoot was empty at launch,
re-pulled and independently re-verified before relaunch, see gate report §0), SIGNED as a SECOND
SIGNING after adversarial review. Both non-DeepSeek primary red-team seats were confirmed down
this lot (Codex hard quota-exhausted until 2026-08-19; agy/Gemini hung indefinitely, reproduced
twice) -- Kimi K3 (`kimi -m kimi-code/k3`) was dispatched as a genuinely cross-family substitute
red-team seat (independent from the conductor/Fable and from every D1/D5/GLM seat already used in
this lot's own adjudication), verdict CONFIRMED-WITH-NOTES: 2 MEDIUM + 3 LOW + 1 NOTE finding, ALL
cured in this signing, NONE of the 13 codes' dispositions refuted. Finding #3 (LOW-MEDIUM)
corrected the cure spec's own 91425 `data_note`: an earlier draft cited the wrong-code PP28 row's
page header as "Lampiran I.J-P p.497 row 8"; the actual page header (viewed at full resolution) is
"Lampiran I.P.7" -- a DIFFERENT lampiran letter than 91425's own sektor_id (I.J-P), which if
anything strengthens the contamination finding rather than weakening it. This registry's expected
_data_note / marker for 91425 below is pinned to the FINAL, CORRECTED text (mentions "Lampiran
I.P.7", not the stale "I.J-P p.497 row 8" phrasing from the draft) -- verified this session by a
direct read of both the current canonical record and the current cure-spec JSON, which already
carry the corrected wording (the second-signing correction was applied before this cure was ever
run).

Final category census (1/6/1/1 = 9, per gate report §3.1-§3.4):
  payload_cross_contamination (1: 91425 -- licensing borrowed from a code-proximity neighbor,
    91025 "Taman Budaya", not from the true crosswalk parent 91033)
  source_absent_in_vault, single-tier (6: 93113, 93115, 93122, 93123, 93125, 93126 -- clean
    own-code crosswalk, but an exhaustive 21-file/11,208-page PP28 vault hunt returned
    verdict=absent for the self-referential citation)
  pp28-wrong-page-hot-trap (1: 93121 -- the cited PP28 render resolves to a blank-identity-column
    continuation row from an unrelated industrial-QC lampiran, a SECOND confirmed sighting of the
    same trap page/file first flagged against innocence control 63101)
  source_absent_in_vault, multi-tier (1: 93124 -- same absence finding as the 6-code group above,
    but spanning BOTH of the record's two per_skala tiers, Menengah Rendah and Tinggi)

This lot's cure spec deliberately EXCLUDES 4 codes from the same 931xx family that a flat "quarantine
= cure" reading would otherwise sweep in: 93111, 93112, 93114 (partially), 93119 -- their crosswalk
AND primary PP28-row licensing fields are genuinely image-verified and sound; they were quarantined
only by a contract-coverage/tooling gap (a synthetic `fiktif_positif`/`derived_license` field the
derivation-formula table doesn't yet cover at their risk tier, or -- 93114 only -- a compiler
limitation with no per-tier partial-detach primitive today). Detaching per_skala on these four would
have DESTROYED genuinely sourced data for the sake of tidiness -- gate report §3.5 holds them
un-cured on purpose, and this registry's innocence-neighbor section (below) uses exactly these four
as its sharpest guard-over-match antidote, since they are the MOST likely codes a sloppy future cure
patch might sweep in by mistake (same 931xx family, same lot's own gate report, same session).

Scar-family #3 (guard-over-match/under-match) discipline applies throughout: every guilt assertion
is paired with an innocence assertion on a legitimate neighbor code, and every content marker is a
multi-word phrase verified (by direct read of the applied canonical record in this session) to
actually appear verbatim in that code's _data_note -- AND checked for non-collision across the
other 8 codes in this lot. Five of the nine codes (93115, 93122, 93123, 93125, 93126) share the
SAME "pp28-source-absent-full-scan" _data_note boilerplate TEXT verbatim, differing only by the
embedded code number itself (e.g. "Crosswalk 93122<->93122" vs "Crosswalk 93125<->93125") -- markers
for these five deliberately lean on that embedded code-number substring, which is non-colliding by
construction (no other code in the lot shares that number), exactly the "byte-identical apart from
the code number" case flagged as acceptable rather than something to force artificial uniqueness
onto. A DIFFERENT and separately-verified 5-way group -- the actual disputed per_skala PAYLOAD
(licensing template content, not the _data_note prose) for 93121/93122/93123/93125/93126 -- is
byte-identical (the generic "Klub X" sport-facility Menengah-Tinggi/14-Hari/LSPr-certificate
template); this is the direct Lot-8 analogue of Lot 7's klinik-template pairs, except it is a single
5-member group rather than 3 separate pairs, and its membership does NOT match the _data_note-text
group above (93121 is IN the payload group but has its own distinct hot-trap _data_note; 93115 is IN
the _data_note-text group but has its own distinct absent-single-tier payload with a different risk
tier, Menengah Rendah not Menengah Tinggi).

IMPORTANT -- these tests are EXPECTED TO BE SKIPPED until the Batch A Lot 8 cure is applied to the
canonical dataset (this file lands together with the data PR that runs
cure_canonical_collisions.py --apply). The whole module is skipped via a module-level pytestmark
until the canonical 93126 record shows the post-cure shape (per_skala == [] and
intel_2026.whatYouNeed matches the spec's honest-gap text) -- at that point the module arms itself
automatically, no edit needed. 93126 is used as the canary (same convention as Lot 3's 64940 / Lot
4's 64955 / Lot 5's 66192 / Lot 6's 80190 / Lot 7's 91424 canaries) -- it is the last code in the
spec's own codes[] array.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LOT8_SPEC_PATH = REPO_ROOT / "scripts/kbli_filiera/cure_specs/batch_a_lot8.json"
CANONICAL_PATH = REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"
DISPUTED_KEY = "per_skala_disputed_pp28_collision"

# --- verbatim from test_kbli_batch_a_lot7_registry.py (2026-07-19) ---------

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


def _load_lot8_spec_by_code() -> dict[str, dict[str, Any]]:
    spec = json.loads(LOT8_SPEC_PATH.read_text(encoding="utf-8"))
    assert spec["disputed_key"] == DISPUTED_KEY, (
        f"spec disputed_key drifted to {spec['disputed_key']!r}, tests hardcode {DISPUTED_KEY!r}"
    )
    return {e["code"]: e for e in spec["codes"]}


def _cure_applied() -> bool:
    """True once the canonical 93126 record shows the post-cure shape (per_skala == [] AND
    intel_2026.whatYouNeed matches the spec's honest-gap text verbatim). Pre-apply, per_skala is
    non-empty; post-apply, per_skala == [] and whatYouNeed is the honest-gap text. If the
    canonical file, the spec, or the 93126 record is missing entirely, treat the cure as NOT
    applied (module stays skipped rather than erroring at collection time)."""
    if not CANONICAL_PATH.exists() or not LOT8_SPEC_PATH.exists():
        return False
    try:
        rec = _load_record(CANONICAL_PATH, "93126")
        spec_by_code = _load_lot8_spec_by_code()
    except (AssertionError, KeyError):
        return False
    intel = rec.get("intel_2026") or {}
    return (
        rec.get("per_skala") == []
        and intel.get("whatYouNeed") == spec_by_code.get("93126", {}).get("whatYouNeed")
    )


pytestmark = pytest.mark.skipif(
    not _cure_applied(),
    reason="batch_a_lot8 cure not yet applied — tests arm after the data PR",
)


LOT8_CODES = [
    "91425", "93113", "93115", "93121", "93122", "93123", "93124", "93125", "93126",
]

# pp28_sources pre-cure value per code, hardcoded from a direct read of the canonical dataset
# (2026-07-20) — must survive the cure untouched, including on 91425, whose TRUE crosswalk parent
# (91033) is established this session but never injected (rule #9 — the false-friend citation
# ['91025'] stays exactly as found).
LOT8_PP28_SOURCES = {
    "91425": ["91025"],
    "93113": ["93113"],
    "93115": ["93115"],
    "93121": ["93121"],
    "93122": ["93122"],
    "93123": ["93123"],
    "93124": ["93124"],
    "93125": ["93125"],
    "93126": ["93126"],
}

# pre-cure status_mapping per code, hardcoded from a direct read of the canonical dataset
# (2026-07-20) — NONE of Lot 8's 9 codes gets a metadata correction in this lot (same discipline
# as Lot 1-7): every code in this lot carries MATCH_LANGSUNG and must keep it.
LOT8_PRE_CURE_STATUS_MAPPING = {
    "91425": "MATCH_LANGSUNG",
    "93113": "MATCH_LANGSUNG",
    "93115": "MATCH_LANGSUNG",
    "93121": "MATCH_LANGSUNG",
    "93122": "MATCH_LANGSUNG",
    "93123": "MATCH_LANGSUNG",
    "93124": "MATCH_LANGSUNG",
    "93125": "MATCH_LANGSUNG",
    "93126": "MATCH_LANGSUNG",
}

# Byte-identical disputed-PAYLOAD group (verified this session, json-dump byte-comparison of the
# preserved per_skala_disputed_pp28_collision blob): the generic "Klub X" sport-facility licensing
# template (Menengah Tinggi risk / 14 Hari jangka waktu / LSPr tourism-standard certificate) is
# shared VERBATIM across all five of these codes — a single 5-member group, unlike Lot 7's three
# separate 2-member pairs. 93113/93115/93124/91425 each carry their OWN distinct payload (different
# risk tier and/or requirement wording) and are NOT part of this group — verified below.
LOT8_SPORT_CLUB_TEMPLATE_GROUP = ["93121", "93122", "93123", "93125", "93126"]

# Content markers: multi-word/distinctive phrases verified (direct read of the applied canonical
# dataset, 2026-07-20) to be verbatim substrings of that code's _data_note, AND verified to NOT
# collide with any of the other 8 codes' _data_note in this lot (guard-over-match discipline).
# Five codes (93115, 93122, 93123, 93125, 93126) share the SAME boilerplate _data_note TEXT
# differing only by the embedded code number — for those five, the marker deliberately leans on
# that embedded code-number substring ("Crosswalk 93122<->93122"), which is non-colliding by
# construction since no sibling code shares that number. Checked ONLY against _data_note.
LOT8_DATA_NOTE_MARKERS = {
    "91425": "Lampiran I.P.7",
    "93113": "despite the confident MATCH_LANGSUNG framing",
    "93115": "Crosswalk 93115<->93115",
    "93121": "entirely unrelated to a football club",
    "93122": "Crosswalk 93122<->93122",
    "93123": "Crosswalk 93123<->93123",
    "93124": "Menengah Rendah and Tinggi",
    "93125": "Crosswalk 93125<->93125",
    "93126": "Crosswalk 93126<->93126",
}

# Innocence controls (scar-family #3 discipline): legitimate neighbor codes untouched by this
# cure, verified this session to carry non-empty per_skala and no disputed key.
#   93111, 93112, 93119 — "Fasilitas Stadion" / "Fasilitas Sirkuit" /
#           "Pengelolaan Fasilitas Olahraga Lainnya", the THREE codes THIS SAME gate report
#           explicitly holds un-cured (§3.5, contract-coverage/tooling gap, not a record defect)
#           — the sharpest available guard-over-match antidote, same lot/same family/same session.
#   91429 — "Aktivitas Cagar Alam Lainnya" (other nature reserve activities), the direct
#           division-91 sibling of THIS lot's 91425 (nature recreation park) — untouched.
#
# SUPERSESSION (2026-07-21, Lot 10): 93114 — "Fasilitas Lapangan", originally the FOURTH §3.5
# code here (one genuinely-sound tier, one gap the compiler could not cure without a per-tier
# primitive) — was REMOVED from this list. Lot 10
# (research/operations/2026-07-21-kbli-batch-a-lot10-conductor-gate.md) built exactly that
# primitive (PR #2921, action="partial_detach"+tier_selector) and legitimately cured 93114's
# defective tier while leaving its sound tier byte-identical in per_skala — so 93114 now
# DOES carry the disputed key and IS no longer "untouched by this spec" (which was only ever
# true as of Lot 8; it was never a promise that no LATER lot would cure it once the tooling
# existed). Its current invariants are pinned in test_kbli_batch_a_lot10_registry.py instead.
# Do NOT re-add 93114 here without a fresh regression (this file remains authoritative for what
# Lot 8 itself did and did not touch).
#
# NOTE: deliberately does NOT include any of Lot 9's 10 sport-cluster members (93127, 93128,
# 93129, 93191, 93192, 93193, 93194, 93195, 93197, 93199 — see
# /tmp/kbli-conductor-a1-0718/lot9-prelaunch-pins.md) even though they are the sharpest
# textually-available neighbor to this lot's own 93121-93126 klub cluster: Lot 9 is the very next
# lot queued in this program and its D0 evidence is already pulled, so pinning an innocence
# assertion on a Lot-9 code here would be a foreseeable regression — this test would start failing
# the moment Lot 9's own cure lands, for a reason that has nothing to do with Lot 8. Innocence
# controls must be codes with no near-term cure scheduled against them.
INNOCENT_NEIGHBORS = [
    "93111", "93112", "93119",
    "91429",
]

_DATASET_IDS = [str(p.relative_to(REPO_ROOT)) for p in _existing_dataset_copies()]


# ---------------------------------------------------------------------------
# 1. per_skala detached and audited (all 9 codes, all dataset copies)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", _existing_dataset_copies(), ids=_DATASET_IDS)
@pytest.mark.parametrize("code", LOT8_CODES)
def test_lot8_per_skala_detached_and_audited(path: Path, code: str):
    """GUILT, core: per_skala must be [] and the disputed key must be present with a non-empty
    preserved blob (the original rows, kept for audit)."""
    rec = _load_record(path, code)
    assert rec.get("per_skala") == [], (
        f"{path}: {code}.per_skala is not [] — the Lot-8 false-friend licensing block has "
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

@pytest.mark.parametrize("code", LOT8_CODES)
def test_lot8_data_note_matches_spec_verbatim(code: str):
    """_data_note must be copied VERBATIM from the cure spec — the compiler never authors a
    replacement licensing value or paraphrases the provenance note (rule #9
    no-new-values-without-provenance)."""
    spec_by_code = _load_lot8_spec_by_code()
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("_data_note") == spec_by_code[code]["data_note"], (
        f"{code}: _data_note drifted from scripts/kbli_filiera/cure_specs/batch_a_lot8.json — "
        "the compiler must copy data_note verbatim."
    )


# ---------------------------------------------------------------------------
# 3. intel_2026.whatYouNeed honest gap, verbatim from spec
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT8_CODES)
def test_lot8_whatYouNeed_honest_gap(code: str):
    """intel_2026.whatYouNeed must be rewritten to the spec's honest-gap text VERBATIM —
    replacing the stale client-facing prose derived from the detached (cross-contaminated/absent/
    wrong-page) per_skala rows."""
    spec_by_code = _load_lot8_spec_by_code()
    rec = _load_record(CANONICAL_PATH, code)
    intel = rec.get("intel_2026") or {}
    assert intel.get("whatYouNeed") == spec_by_code[code]["whatYouNeed"], (
        f"{code}: intel_2026.whatYouNeed does not match the spec's honest-gap text verbatim — "
        "the compiler must copy whatYouNeed verbatim, never paraphrase or invent it."
    )


# ---------------------------------------------------------------------------
# 4. pp28_sources untouched (all 9, including 91425 whose true crosswalk parent is verified but
#    never injected)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT8_CODES)
def test_lot8_pp28_sources_untouched(code: str):
    """pp28_sources is provenance/audit and must survive the cure unchanged — even for 91425,
    whose true crosswalk parent (91033) is established this session: the compiler never authors
    new source values (Lot 1-7 detach convention)."""
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("pp28_sources") == LOT8_PP28_SOURCES[code], (
        f"{code}: pp28_sources drifted from its pre-cure value {LOT8_PP28_SOURCES[code]!r} — "
        "must be preserved untouched (rule: KEEP pp28_sources unchanged)."
    )


# ---------------------------------------------------------------------------
# 5. NO metadata corrections in this lot — status_mapping must survive untouched on ALL 9 codes
#    (same discipline as Lot 1-7)
# ---------------------------------------------------------------------------

def test_lot8_no_code_gets_a_status_mapping_correction():
    """No code in this lot has an independently-verified SHAPE change (split/merge) established
    in the gate report that gets INJECTED into the canonical — 91425's true-parent finding is
    recorded as _data_note provenance only (same rule as Lot 3's 64940, Lot 4's 64955, Lot 5's
    68123/68126/66192, Lot 6's veterinary trio/85321, Lot 7's 85330/85401/85404/91222). Every
    status_mapping must therefore match its pre-cure value exactly."""
    for code, expected in LOT8_PRE_CURE_STATUS_MAPPING.items():
        rec = _load_record(CANONICAL_PATH, code)
        assert rec.get("status_mapping") == expected, (
            f"{code}: status_mapping drifted to {rec.get('status_mapping')!r} — expected "
            f"untouched pre-cure value {expected!r} (this lot is detach-only, no metadata "
            "correction on any of its 9 codes)."
        )


def test_lot8_spec_never_declares_a_status_mapping_correction():
    """Guard against the spec itself silently growing a correction key that the compiler would
    then apply — Lot 8's adjudication established no independently-verified shape change for any
    of its 9 codes that gets injected into the canonical (rule #9)."""
    spec_by_code = _load_lot8_spec_by_code()
    for code in LOT8_CODES:
        entry = spec_by_code[code]
        assert "status_mapping_correction" not in entry, (
            f"{code}: spec unexpectedly declares status_mapping_correction "
            f"{entry.get('status_mapping_correction')!r} — Lot 8 has no independently-verified "
            "shape change injected for any code (rule #9)."
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
            f"{code}: spec unexpectedly declares action=metadata_only — Lot 8 detaches every one "
            "of its 9 codes, none is standalone-metadata-only."
        )


# ---------------------------------------------------------------------------
# 6. Idempotency: compiler dry-run over the served dataset reports every code already-cured
#    (no-op).
# ---------------------------------------------------------------------------

def test_lot8_compiler_dry_run_reports_already_cured():
    """Idempotency, all 9 codes -- EXTENDED 2026-07-20 (Appendix A gold-staleness fix) to also
    cover 93122's new zantaraOpener_correction: since the spec now carries that key on 93122's
    entry, this same dry-run additionally proves the zantaraOpener metadata correction is
    idempotent (a re-run against the served/cured canonical reports 93122 as ALREADY CURED, not
    'apply', for the zantaraOpener change too) -- no separate test needed, the existing
    already-cured assertion below already subsumes it because describe() collapses to
    'ALREADY CURED (skip)' only when EVERY requested action, including zantaraOpener, already
    matches."""
    result = subprocess.run(
        [
            "python3",
            str(REPO_ROOT / "scripts/kbli_filiera/cure_canonical_collisions.py"),
            "--spec",
            str(LOT8_SPEC_PATH),
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
    for code in LOT8_CODES:
        assert f"{code}: ALREADY CURED (skip)" in result.stdout, (
            f"expected '{code}: ALREADY CURED (skip)' in dry-run output, not found. "
            f"stdout:\n{result.stdout}"
        )
    assert "metadata-corrected" not in result.stdout, (
        "dry-run over the already-applied canonical unexpectedly still proposes a metadata "
        f"correction (zantaraOpener or otherwise) -- not idempotent. stdout:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# 7. INNOCENCE (scar #3 discipline) — legitimate neighbor codes must be untouched by this spec.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", INNOCENT_NEIGHBORS)
def test_lot8_innocent_neighbors_untouched(code: str):
    """These codes are legitimate neighbors (or this same gate report's own explicitly-excluded
    contract-coverage-gap codes) and are NOT part of this cure — if the cure ever over-reaches
    onto one of them, this must fail."""
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("per_skala"), (
        f"{code}: per_skala unexpectedly empty — this is an innocence control, not one of the "
        "9 Lot-8 codes; the cure must not have touched it."
    )
    assert DISPUTED_KEY not in rec, (
        f"{code}: unexpectedly carries {DISPUTED_KEY!r} — this code was never part of the "
        "batch_a_lot8 cure spec."
    )


# ---------------------------------------------------------------------------
# 8. Content markers — verified verbatim in _data_note only, AND verified non-colliding across
#    the other 8 codes in this lot.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT8_CODES)
def test_lot8_data_note_content_marker_present(code: str):
    rec = _load_record(CANONICAL_PATH, code)
    note = rec.get("_data_note", "")
    marker = LOT8_DATA_NOTE_MARKERS[code]
    assert _contains_word_or_phrase(note, marker), (
        f"{code}: expected marker {marker!r} not found inside _data_note — the provenance note "
        f"may have drifted from the spec. _data_note: {note!r}"
    )


@pytest.mark.parametrize("code", LOT8_CODES)
def test_lot8_data_note_marker_does_not_collide_with_siblings(code: str):
    """Guard-over-match antidote: each code's marker must NOT appear inside any OTHER Lot-8
    code's _data_note — five codes in this lot (93115, 93122, 93123, 93125, 93126) share the SAME
    boilerplate prose apart from the embedded code number, so a marker that is present-but-shared
    would silently pass this test for the wrong code."""
    marker = LOT8_DATA_NOTE_MARKERS[code]
    for other in LOT8_CODES:
        if other == code:
            continue
        other_note = _load_record(CANONICAL_PATH, other).get("_data_note", "")
        assert marker not in other_note, (
            f"{code}'s marker {marker!r} unexpectedly also appears in {other}'s _data_note — "
            "marker is not code-specific, guard-over-match risk."
        )


# ---------------------------------------------------------------------------
# 9. Byte-identical disputed payload group — the preserved disputed blocks for the 5-member
#    "Klub X" sport-facility licensing template must survive the cure exactly as found (verified
#    by direct read of the canonical payload in this session). 93113/93115/93124/91425 each carry
#    their own distinct payload, not part of this group.
# ---------------------------------------------------------------------------

def test_lot8_sport_club_template_group_shares_byte_identical_disputed_payload():
    """93121 (Klub Sepak Bola) / 93122 (Klub Golf) / 93123 (Klub Renang) / 93125 (Klub Tinju) /
    93126 (Klub Bela Diri) share the IDENTICAL generic sport-facility licensing template
    (Menengah Tinggi risk / 14 Hari jangka waktu / LSPr tourism-standard certificate) — must
    survive byte-identical, a single 5-member group (unlike Lot 7's three separate 2-member
    pairs)."""
    blobs = {
        code: json.dumps(_load_record(CANONICAL_PATH, code).get(DISPUTED_KEY), ensure_ascii=False)
        for code in LOT8_SPORT_CLUB_TEMPLATE_GROUP
    }
    reference_code = LOT8_SPORT_CLUB_TEMPLATE_GROUP[0]
    reference = blobs[reference_code]
    for code, blob in blobs.items():
        assert blob == reference, (
            f"{code}: preserved disputed block diverges from {reference_code}'s — the five sport-"
            "club codes should share a byte-identical generic licensing template."
        )
    marker = "LSPr"
    for code in LOT8_SPORT_CLUB_TEMPLATE_GROUP:
        assert marker in blobs[code], (
            f"{code}: preserved disputed block no longer carries the shared LSPr-certificate "
            f"template signature {marker!r} — audit trail may have drifted."
        )


def test_lot8_singleton_codes_are_not_byte_identical_to_the_sport_club_template_group():
    """GUILT+INNOCENCE for the sport/klub cluster: 93113 (Fasilitas Gelanggang/Arena), 93115
    (Fasilitas Olahraga Beladiri), 93124 (Klub Tenis Lapangan, two tiers), and 91425 (Taman Hutan
    Raya, a different activity family entirely) are each corroborated with their OWN distinct
    disputed payload — none should be byte-identical to the 5-member sport-club template group,
    per the gate report's own finding that only 93121/93122/93123/93125/93126 share that generic
    template."""
    reference = json.dumps(
        _load_record(CANONICAL_PATH, LOT8_SPORT_CLUB_TEMPLATE_GROUP[0]).get(DISPUTED_KEY),
        ensure_ascii=False,
    )
    for code in ("93113", "93115", "93124", "91425"):
        blob = json.dumps(_load_record(CANONICAL_PATH, code).get(DISPUTED_KEY), ensure_ascii=False)
        assert blob != reference, (
            f"{code}: preserved disputed block unexpectedly byte-identical to the sport-club "
            "template group — this code should carry its own distinct payload."
        )


# ---------------------------------------------------------------------------
# 10. True-parent provenance — corroborated this session against the gate's by-eye render/
#     crosswalk finding, recorded as _data_note provenance ONLY (rule #9: never injected into
#     pp28_sources/kbli_2020_source/status_mapping). Lot 8 has exactly ONE such finding (91425),
#     unlike Lot 7's four.
# ---------------------------------------------------------------------------

def test_lot8_91425_true_parent_recorded_as_provenance_only():
    """91425's true 2020 crosswalk parent is 91033 ('Taman Hutan Raya'), image-verified
    bidirectionally ONE_TO_ONE on BPS Vol.2 Lampiran 10 — but the record's own per_skala payload
    was borrowed from an unrelated code-proximity neighbor, 91025 ('Taman Budaya'/Cultural Park,
    which itself crosswalks to 90310, never to 91425). Recorded as provenance only: the cited
    91025 citation stays unchanged, 91033 is never injected into pp28_sources (rule #9)."""
    rec = _load_record(CANONICAL_PATH, "91425")
    note = rec.get("_data_note", "")
    for marker in ("91033", "91025", "Taman Budaya", "90310", "Taman Hutan Raya"):
        assert marker in note, f"91425: _data_note missing expected true-parent marker {marker!r}"
    assert rec.get("pp28_sources") == ["91025"], (
        "91425: pp28_sources drifted — must stay the false-friend citation ['91025'], the true "
        "crosswalk parent (91033) is provenance-only per rule #9"
    )
    assert "91033" not in (rec.get("pp28_sources") or []), (
        "91425: pp28_sources unexpectedly contains the true parent 91033 — rule #9 forbids "
        "injecting a replacement/additional source value"
    )
    assert rec.get("status_mapping") == "MATCH_LANGSUNG"


# ---------------------------------------------------------------------------
# 11. Gold-layer staleness fix (Appendix A cross-family finding, Kimi K3, 2026-07-20): 6 of Lot
#     8's 9 cured codes (91425, 93113, 93115, 93122, 93123, 93124) are ALSO present in the gold
#     editorial layer (apps/mouth/data/kbli-gold-all.json), whose own whatYouNeed still asserted
#     the EXACT stale pre-cure licensing facts that canonical's detach removed — and gold wins on
#     the live /kbli/<code> page (LicensingSection.tsx parses gold.whatYouNeed when gold exists),
#     so canonical's honest-gap cure never actually surfaced for these 6. Same disease class as
#     the established 49213/50115/60103/68123-etc. precedent (commit aa01a46b8b, #2794): gold's
#     whatYouNeed is rewritten to canonical's own already-adversarially-reviewed honest-gap text,
#     reused VERBATIM (not paraphrased) for consistency between the two surfaces.
# ---------------------------------------------------------------------------

GOLD_PATH = REPO_ROOT / "apps/mouth/data/kbli-gold-all.json"

# The 6 Lot-8 codes that are ALSO present in gold (of the 9 total) — fixed this session.
GOLD_STALE_CODES_FIXED = ["91425", "93113", "93115", "93122", "93123", "93124"]

# The 3 Lot-8 codes that were NEVER in gold — innocence controls, untouched by this fix.
GOLD_ABSENT_LOT8_CODES = ["93121", "93125", "93126"]


def _load_gold() -> dict[str, dict[str, Any]]:
    return json.loads(GOLD_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("code", GOLD_STALE_CODES_FIXED)
def test_lot8_gold_whatYouNeed_matches_canonical_honest_gap(code: str):
    """GUILT: gold's whatYouNeed for these 6 codes must now match canonical's own honest-gap
    text (scripts/kbli_filiera/cure_specs/batch_a_lot8.json's whatYouNeed, the same string
    already applied to intel_2026.whatYouNeed by the Lot 8 cure) VERBATIM — reused, not
    paraphrased, per the established gold-staleness-fix convention (commit aa01a46b8b)."""
    gold = _load_gold()
    spec_by_code = _load_lot8_spec_by_code()
    entry = gold.get(code)
    assert entry is not None, f"{code}: expected to be present in gold (this is one of the 6)"
    expected = spec_by_code[code]["whatYouNeed"]
    assert entry.get("whatYouNeed") == expected, (
        f"{code}: gold whatYouNeed does not match the Lot 8 cure spec's honest-gap text "
        f"verbatim.\nexpected: {expected!r}\nactual:   {entry.get('whatYouNeed')!r}"
    )
    # Cross-check against the LIVE canonical too (not just the spec) — gold and canonical must
    # now agree, closing the exact gap this Appendix A finding caught.
    rec = _load_record(CANONICAL_PATH, code)
    intel = rec.get("intel_2026") or {}
    assert entry.get("whatYouNeed") == intel.get("whatYouNeed"), (
        f"{code}: gold whatYouNeed diverges from canonical intel_2026.whatYouNeed — the two "
        "surfaces must agree post-fix."
    )


@pytest.mark.parametrize("code", GOLD_ABSENT_LOT8_CODES)
def test_lot8_gold_absent_codes_remain_absent(code: str):
    """INNOCENCE: these 3 Lot-8 codes (93121, 93125, 93126) were never part of the gold editorial
    layer and are unaffected by this fix — confirm they remain absent from gold, guarding against
    an over-broad future edit accidentally inserting them."""
    gold = _load_gold()
    assert code not in gold, (
        f"{code}: unexpectedly present in gold — this code was never part of the Appendix A "
        "gold-staleness fix and should stay absent."
    )


def test_lot8_93122_zantaraopener_honest_gap():
    """GUILT: canonical's intel_2026.zantaraOpener for 93122 must now match the cure spec's
    zantaraOpener_correction verbatim, and must NOT assert the stale "medium-high risk
    classification" fact that was part of the detached per_skala payload (Appendix A second
    finding, Kimi K3, 2026-07-20) — regression guard so a future re-run of the compiler (or a
    hand-edit) cannot silently reintroduce the risk-tier claim."""
    spec_by_code = _load_lot8_spec_by_code()
    rec = _load_record(CANONICAL_PATH, "93122")
    intel = rec.get("intel_2026") or {}
    expected = spec_by_code["93122"]["zantaraOpener_correction"]
    actual = intel.get("zantaraOpener")
    assert actual == expected, (
        f"93122: intel_2026.zantaraOpener does not match the spec's zantaraOpener_correction "
        f"verbatim.\nexpected: {expected!r}\nactual:   {actual!r}"
    )
    assert "medium-high risk classification" not in (actual or ""), (
        "93122: zantaraOpener still asserts the stale 'medium-high risk classification' fact "
        "that was part of the detached payload."
    )
    assert "medium-high" not in (actual or ""), (
        "93122: zantaraOpener unexpectedly still contains 'medium-high' in any form."
    )
