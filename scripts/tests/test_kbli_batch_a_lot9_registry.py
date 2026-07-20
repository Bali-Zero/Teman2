"""Regression registry -- GARUDA-FILIERA Batch A Lot 9 false-friend per_skala collisions (10
codes, the remainder of the division-93 sport-facility/klub/activity split not covered by Lot 8,
2026-07-20), driven by scripts/kbli_filiera/cure_specs/batch_a_lot9.json and applied via
scripts/kbli_filiera/cure_canonical_collisions.py --spec batch_a_lot9.json.

THIRD SIGNING addendum (post-implementation adversarial review, Kimi K3, 2026-07-20): the
initial cure correctly set status_mapping_correction="MATCH_CON_AGGREGAZIONE" on 93191/93193/
93199 but left their intel_2026.whatChanged text stale ("Direct match ... Same code, same
scope"/"Direct 1:1 match ... code and scope unchanged") -- a self-contradiction the cure itself
introduced (pre-cure the record was consistently wrong; a status_mapping-only fix left it
self-contradictory instead). Cured via whatChanged_correction on all three codes (mirrors the
existing Lot-2-era whatChanged_correction primitive), verified against the dataset's own
convention: every one of the 202 pre-existing MATCH_CON_AGGREGAZIONE records already describes
its merge in whatChanged. Gold-layer mirror applied to 93191 and 93199 (both present in
apps/mouth/data/kbli-gold-all.json, same stale text); 93193 is absent from gold, nothing to
mirror there. See section 6b below for the guilt+innocence tests. PROCESS NOTE: this addendum
was applied by the Kimi K3 CLI directly during what was scoped as a read-only adversarial
review -- it modified the cure spec, re-ran the sanctioned compiler, and extended this test file
itself, rather than only reporting the finding. The content was independently re-verified
(byte-identity of 93191/93193 per_skala re-confirmed unchanged, whatChanged text re-checked
against the crosswalk evidence and the 202-record convention, sync/sidecar consistency
re-checked) before being accepted into this signing; one gap in Kimi's own fix (gold's 93191
whatChanged was left stale) was found and closed in that same re-verification pass.

Modeled closely on test_kbli_batch_a_lot8_registry.py (Lot 8 registry, 2026-07-20) -- the
ALL_DATASET_COPIES list and the _existing_dataset_copies / _load_by_code / _load_record /
_contains_word_or_phrase helpers below are COPIED VERBATIM from that file (comment marks the
origin instead of importing, to keep this file self-contained and independently readable as its
own regression pin, same convention Lot 1-8 used).

Two disposition classes this lot (gate report Section 3, SECOND SIGNING):

  GROUP A -- full detach (8 codes: 93127, 93128, 93129, 93192, 93194, 93195, 93197, 93199).
    Identical mechanics to Lot 1-8 (see cure_canonical_collisions.py docstring):
      1. per_skala -> []  (frontend guards licensing.length > 0 -> honest gap instead of wrong data)
      2. the ORIGINAL per_skala preserved verbatim under the disputed key
         "per_skala_disputed_pp28_collision" -- never silently deleted
      3. _data_note added (verbatim from the cure spec -- never invented here)
      4. intel_2026.whatYouNeed rewritten to the spec's honest-gap text (verbatim)
      5. pp28_sources / judul / uraian / pma_* / every other field left untouched
    93199 ALSO gets status_mapping_correction "MATCH_LANGSUNG" -> "MATCH_CON_AGGREGAZIONE"
    (genuine 2-parent merge 93199+51106, mislabeled -- gate report 3.4, Kimi red-team F1).

  GROUP B -- metadata_only, NO detach (2 codes: 93191, 93193). Confirmed tier-scoped
    payload_cross_contamination (gate report 2.1/3.2) that cure_canonical_collisions.py cannot
    cure yet (no per-tier/index/skala_usaha selector -- Lot 8 PENDING-ARMS 3.4/5.1b). The ONLY
    change for these two: action="metadata_only" + status_mapping_correction
    "MATCH_LANGSUNG" -> "MATCH_CON_AGGREGAZIONE" (same genuine-2-parent-merge disease as 93199).
    per_skala (both tiers, including the KNOWN cross-contaminated content) is left COMPLETELY
    untouched -- byte-identical before/after this cure, independently proven via git diff in the
    conductor session (zero per_skala lines in either code's diff hunk) and via this file's own
    hardcoded pre-cure snapshot (below).

GROUP C -- no spec entry, innocence controls only: 46201, 96300 (gate report 2.4/3.3, genuinely
clean per D1+D5 -- the quarantined label on both is a tooling artifact of the known
derive_fiktif_positif.py Rendah-tier coverage gap, PENDING-ARMS opened Lot 8 -- not Batch-A
members of this lot, not touched by this spec).

ADJUDICATION HISTORY (2026-07-20): conductor gate on lane run wf_8d2d246d-f8f (24 agent
invocations [12 codes x D1+D5], 0 errors), SECOND SIGNING after adversarial review. Codex was
quota-exhausted (until 2026-08-19) and GLM keychain-unavailable in this background session --
Kimi K3 (kimi -m kimi-code/k3) was dispatched as a genuinely cross-family substitute red-team
seat (same pattern as Lot 8), verdict CONFIRMED-WITH-NOTES: 2 MEDIUM (F1 status_mapping mislabel
on 93191/93193/93199, actioned in this signing; F2 93193-zero-sound-tiers reframing, reasoning
correction only, disposition unchanged) + 2 LOW (wording precision) + 1 NOTE, refuted NONE of the
12 dispositions (10 real members + 2 innocence controls).

Byte-identical disputed-PAYLOAD group (verified this session, json-dump sort_keys byte-comparison
of the preserved per_skala_disputed_pp28_collision blob): 93192/93197/93199 share a byte-identical
single-tier generic template (Rendah risk / NIB / "submit periodic activity reports" only /
skala_usaha Mikro-Kecil-Menengah). 93127, 93128, 93129, 93194, 93195 each carry their OWN distinct
disputed payload (different risk tier, authority, and/or skala_usaha coverage) and are NOT part of
that group -- verified below.

Scar-family #3 (guard-over-match/under-match) discipline applies throughout: every guilt assertion
is paired with an innocence assertion on a legitimate neighbor code, and every content marker is a
multi-word-or-code-number phrase verified (by direct read of the applied canonical record in this
session, programmatic guilt+innocence cross-check across all 10 codes' _data_note) to actually
appear verbatim in that code's own _data_note AND to NOT collide with any of the other 9 codes in
this lot.

Gold-editorial-layer cross-check (proactive, per Lot 8's PR #2906/#2909 Appendix A precedent --
applied THIS TIME at cure time instead of waiting for a follow-up Appendix A finding): of this
lot's 10 codes, apps/mouth/data/kbli-gold-all.json contains entries for 93127, 93129, 93191, 93195,
93199 (93128/93192/93193/93194/93197 are absent from gold entirely -- nothing to fix). Of those 5,
93127/93129/93195/93199 (all Group A, all detached) had gold whatYouNeed text asserting the exact
stale pre-cure licensing steps (numbered PT PMA/NIB/Standard-Certificate lists, specific risk
tiers) -- same disease class as Lot 8's Appendix A finding (91425/93113/93115/93122/93123/93124).
Fixed by rewriting gold whatYouNeed to canonical's own already-adversarially-reviewed honest-gap
text, verbatim reuse (identical mechanism to commit c2269e807d). 93191 is Group B (per_skala/
whatYouNeed untouched this lot by design) -- its gold entry is correspondingly left untouched;
there is no cured canonical text to mirror into it, and touching it would be an unrelated,
non-adjudicated change.

Discovery flagged but explicitly OUT OF SCOPE for this cure (recommended for a future Appendix A /
PENDING-ARMS line, NOT fixed here): canonical's own intel_2026.zantaraOpener and
intel_2026.editorial (headline/standfirst/body/byTheNumbers) blocks for ALL 10 of this lot's codes
independently assert specific risk-tier/authority facts (e.g. "Menengah Rendah risk", "no Besar
scale row") derived from the very per_skala payload now detached or held-uncured -- a MUCH
larger-scale instance of the same bug class Lot 8's Appendix A caught as a single-code finding
(93122's zantaraOpener). Fixing this program-wide is out of scope for a single lot's cure PR (it
would need to sweep potentially every cured code in the program, not just this lot's 10) and was
not part of the gate report's adjudication (Section 3) -- flagged here and in the PR description
for a dedicated follow-up.

Final category census (8 detach + 2 metadata-only = 10, per gate report 3.1/3.2/3.4):
  source_absent_in_vault, self-referential single-tier (6: 93127, 93128, 93129, 93194, 93195,
    93199 -- clean own-code crosswalk, exhaustive 21-file/11,208-page PP28 vault hunt absent;
    93199 additionally a genuine 2-parent merge with a status_mapping fix)
  source_absent_in_vault, genuine split (2: 93192, 93197 -- clean SPLIT from 2020 code 93192, both
    pp28 AND independent OSS endpoint probe absent)
  payload_cross_contamination, tier-scoped, held un-cured (2: 93191, 93193 -- each code's one
    wrong tier is verbatim byte-identical to the OTHER code's corresponding correct tier; both
    also get a status_mapping fix for their own separate genuine 2-parent merge)
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LOT9_SPEC_PATH = REPO_ROOT / "scripts/kbli_filiera/cure_specs/batch_a_lot9.json"
CANONICAL_PATH = REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"
GOLD_PATH = REPO_ROOT / "apps/mouth/data/kbli-gold-all.json"
DISPUTED_KEY = "per_skala_disputed_pp28_collision"

# --- verbatim from test_kbli_batch_a_lot8_registry.py (2026-07-20) ---------

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
    bare "SPA" inside "aerospace"). A multi-word phrase (contains a space) is matched as a plain
    substring -- the multi-word shape itself is already a strong disambiguator."""
    if " " in marker:
        return marker in haystack
    return re.search(rf"\b{re.escape(marker)}\b", haystack) is not None


# --- end verbatim block -----------------------------------------------------


def _load_lot9_spec_by_code() -> dict[str, dict[str, Any]]:
    spec = json.loads(LOT9_SPEC_PATH.read_text(encoding="utf-8"))
    assert spec["disputed_key"] == DISPUTED_KEY, (
        f"spec disputed_key drifted to {spec['disputed_key']!r}, tests hardcode {DISPUTED_KEY!r}"
    )
    return {e["code"]: e for e in spec["codes"]}


def _cure_applied() -> bool:
    """True once the canonical 93199 record shows the post-cure shape (per_skala == [] AND
    intel_2026.whatYouNeed matches the spec's honest-gap text AND status_mapping ==
    MATCH_CON_AGGREGAZIONE). Pre-apply, per_skala is non-empty; post-apply, per_skala == [] and
    whatYouNeed/status_mapping match. If the canonical file, the spec, or the 93199 record is
    missing entirely, treat the cure as NOT applied (module stays skipped rather than erroring at
    collection time). 93199 is used as the canary (last code in the spec's own codes[] array, same
    convention as every prior lot's canary choice)."""
    if not CANONICAL_PATH.exists() or not LOT9_SPEC_PATH.exists():
        return False
    try:
        rec = _load_record(CANONICAL_PATH, "93199")
        spec_by_code = _load_lot9_spec_by_code()
    except (AssertionError, KeyError):
        return False
    intel = rec.get("intel_2026") or {}
    entry = spec_by_code.get("93199", {})
    return (
        rec.get("per_skala") == []
        and intel.get("whatYouNeed") == entry.get("whatYouNeed")
        and rec.get("status_mapping") == entry.get("status_mapping_correction")
    )


pytestmark = pytest.mark.skipif(
    not _cure_applied(),
    reason="batch_a_lot9 cure not yet applied -- tests arm after the data PR",
)


LOT9_CODES = [
    "93127", "93128", "93129", "93191", "93192", "93193", "93194", "93195", "93197", "93199",
]

LOT9_DETACH_CODES = [
    "93127", "93128", "93129", "93192", "93194", "93195", "93197", "93199",
]

LOT9_METADATA_ONLY_CODES = ["93191", "93193"]

# pp28_sources pre/post-cure value per code, hardcoded from a direct read of the canonical dataset
# (2026-07-20) -- must survive the cure untouched for EVERY code in this lot, including 93197
# (whose pp28_sources correctly cites its split-parent 93192, honest, never self-referential) and
# 93191/93193/93199 (whose true 2-parent-merge siblings 82302/91037/51106 are recorded as
# _data_note provenance ONLY, never injected here -- rule #9).
LOT9_PP28_SOURCES = {
    "93127": ["93127"],
    "93128": ["93128"],
    "93129": ["93129"],
    "93191": ["93191"],
    "93192": ["93192"],
    "93193": ["93193"],
    "93194": ["93194"],
    "93195": ["93195"],
    "93197": ["93192"],
    "93199": ["93199"],
}

# pre-cure status_mapping per code, hardcoded from a direct read of the canonical dataset
# (2026-07-20).
LOT9_PRE_CURE_STATUS_MAPPING = {
    "93127": "MATCH_LANGSUNG",
    "93128": "MATCH_LANGSUNG",
    "93129": "MATCH_LANGSUNG",
    "93191": "MATCH_LANGSUNG",
    "93192": "MATCH_LANGSUNG",
    "93193": "MATCH_LANGSUNG",
    "93194": "MATCH_LANGSUNG",
    "93195": "MATCH_LANGSUNG",
    "93197": "CODICE_RINUMERATO",
    "93199": "MATCH_LANGSUNG",
}

# post-cure status_mapping per code: 93191/93193/93199 get the MATCH_CON_AGGREGAZIONE correction
# (genuine 2-parent merges mislabeled MATCH_LANGSUNG, gate report 3.4, Kimi red-team F1); every
# other code (including 93197's already-correct CODICE_RINUMERATO) is untouched.
LOT9_POST_CURE_STATUS_MAPPING = dict(LOT9_PRE_CURE_STATUS_MAPPING)
LOT9_POST_CURE_STATUS_MAPPING.update(
    {"93191": "MATCH_CON_AGGREGAZIONE", "93193": "MATCH_CON_AGGREGAZIONE", "93199": "MATCH_CON_AGGREGAZIONE"}
)

# Byte-identical disputed-PAYLOAD group (verified this session, json.dumps(sort_keys=True)
# byte-comparison of the preserved per_skala_disputed_pp28_collision blob): the generic single-tier
# "Rendah / NIB / submit periodic activity reports" template (skala_usaha Mikro-Kecil-Menengah) is
# shared VERBATIM across these three codes.
LOT9_GENERIC_TEMPLATE_GROUP = ["93192", "93197", "93199"]

# Content markers: multi-word phrases OR code-number substrings verified (direct read of the
# applied canonical dataset, 2026-07-20, programmatic guilt+innocence cross-check across all 10
# codes) to be verbatim substrings of that code's _data_note, AND verified to NOT collide with any
# of the other 9 codes' _data_note in this lot (guard-over-match discipline).
LOT9_DATA_NOTE_MARKERS = {
    "93127": "D1's extraction rubric read as reconciling the absence",
    "93128": "Crosswalk 93128<->93128",
    "93129": "Crosswalk 93129<->93129",
    "93191": "82302",
    "93192": "pp28_sources=['93192'] is self-referential",
    "93193": "93193 has ZERO genuinely sound tiers",
    "93194": "Crosswalk 93194<->93194",
    "93195": "Crosswalk 93195<->93195",
    "93197": "not self-referential — status_mapping=CODICE_RINUMERATO",
    "93199": "51106",
}

# Innocence controls (scar-family #3 discipline): legitimate neighbor codes untouched by this
# cure, verified this session to carry non-empty per_skala and no disputed key.
#   46201, 96300 -- this SAME gate report's own explicitly-excluded innocence controls (2.4/3.3):
#           genuinely clean per D1+D5, "quarantined" label is a tooling artifact only, NOT Batch-A
#           members of this lot.
#   93196 -- "Pengelolaan Fasilitas Pemancingan" (fishing-facility management), the sharpest
#           in-family neighbor: same division-93 sport/recreation cluster, sits alphabetically
#           between 93195 and 93197 in this lot's own codes, but was never adjudicated by this
#           gate and carries its own healthy 7-tier per_skala -- the closest available guard-over-
#           match antidote.
#   47111 -- "Perdagangan Eceran ... Sistem Swalayan" (retail supermarket trade), a code from a
#           totally different division (47, wholesale/retail), chosen per program convention to
#           avoid any near-term-lot foreseeable-regression risk (Lot 8's own discipline note: an
#           innocence control must not be a code with a cure scheduled against it soon).
INNOCENT_NEIGHBORS = ["46201", "96300", "93196", "47111"]

_DATASET_IDS = [str(p.relative_to(REPO_ROOT)) for p in _existing_dataset_copies()]


# ---------------------------------------------------------------------------
# 1. GROUP A -- per_skala detached and audited (8 codes, all dataset copies)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", _existing_dataset_copies(), ids=_DATASET_IDS)
@pytest.mark.parametrize("code", LOT9_DETACH_CODES)
def test_lot9_per_skala_detached_and_audited(path: Path, code: str):
    """GUILT, core: per_skala must be [] and the disputed key must be present with a non-empty
    preserved blob (the original rows, kept for audit)."""
    rec = _load_record(path, code)
    assert rec.get("per_skala") == [], (
        f"{path}: {code}.per_skala is not [] -- the Lot-9 false-friend licensing block has "
        "leaked back into the served field."
    )
    disputed = rec.get(DISPUTED_KEY)
    assert disputed, (
        f"{path}: {code} is missing (or has an empty) {DISPUTED_KEY!r} -- the original per_skala "
        "rows must be preserved for audit, never silently deleted."
    )
    assert isinstance(disputed, list) and len(disputed) > 0, (
        f"{path}: {code}.{DISPUTED_KEY} expected to be a non-empty list of the original "
        f"per_skala rows, got {type(disputed)} / {disputed!r}"
    )


# ---------------------------------------------------------------------------
# 2. GROUP B -- per_skala NOT detached, byte-identical before/after (2 codes)
# ---------------------------------------------------------------------------

# Hardcoded pre-cure per_skala snapshot for 93191/93193 (verified this session, direct read of the
# canonical dataset BEFORE this cure ran -- json.dumps(sort_keys=True) is used for the comparison
# so key-order in the live file can never spuriously fail this test). Generated via repr() from a
# live pre-apply snapshot, not hand-transcribed, to eliminate manual-transcription error.
LOT9_PRE_CURE_PER_SKALA_93191 = [{'skala_usaha': ['Mikro', 'Kecil', 'Menengah', 'Besar'], 'kategori_risiko': 'Menengah Rendah', 'perizinan': 'NIB dan Sertifikat Standar', 'persyaratan': [], 'jangka_waktu': 'Otomatis', 'kewajiban': ['Memiliki sertifikat standar yang diterbitkan oleh LSPr (khusus PMA)', 'Memiliki Dokumen Penilaian Mandiri Kesiapan Penerapan Standar usaha Promotor Kegiatan Olahraga meliputi Sarana, Struktur Organisasi dan SDM, Pelayanan, Produk usaha dan Sistem Manajemen Usaha'], 'pb_umku': [], 'parameter': 'Seluruh', 'kewenangan': 'Bupati/Walikota', 'sanksi_peringatan': 'Peringatan tertulis', 'sanksi_denda': 'Denda administratif', 'sanksi_penghentian': 'Penghentian sementara kegiatan usaha', 'sanksi_pencabutan': 'Pencabutan persyaratan dasar, PB, dan/atau PB UMKU', 'fiktif_positif': True, 'dati_inferiti': True}, {'skala_usaha': ['Kecil', 'Menengah', 'Besar'], 'kategori_risiko': 'Menengah Rendah', 'perizinan': 'NIB dan Sertifikat Standar', 'persyaratan': [], 'jangka_waktu': 'Otomatis', 'kewajiban': ['Memiliki sertifikat standar yang diterbitkan oleh LSPr (khusus PMA)', 'Memiliki Dokumen Penilaian Mandiri Kesiapan Penerapan Standar usaha Aktivitas Perburuan meliputi Sarana, Struktur Organisasi dan SDM, Pelayanan, Produk usaha dan Sistem Manajemen Usaha'], 'pb_umku': ['-'], 'parameter': 'Seluruh', 'kewenangan': 'Bupati/Walikota', 'sanksi_peringatan': 'Peringatan tertulis', 'sanksi_denda': 'Denda administratif', 'sanksi_penghentian': 'Penghentian sementara kegiatan usaha', 'sanksi_pencabutan': 'Pencabutan persyaratan dasar, PB, dan/atau PB UMKU', 'fiktif_positif': True, 'dati_inferiti': True}]

# 93193's pre-cure per_skala is structurally identical in shape to 93191's (same two tiers, same
# cross-contamination) -- hardcoded independently here (not derived from
# LOT9_PRE_CURE_PER_SKALA_93191) to catch a copy-paste error in either fixture. Gate report 2.1:
# "the two codes' WRONG tiers are not just similar -- they are verbatim byte-identical to each
# other's corresponding CORRECT tier."
LOT9_PRE_CURE_PER_SKALA_93193 = [{'skala_usaha': ['Mikro', 'Kecil', 'Menengah', 'Besar'], 'kategori_risiko': 'Menengah Rendah', 'perizinan': 'NIB dan Sertifikat Standar', 'persyaratan': [], 'jangka_waktu': 'Otomatis', 'kewajiban': ['Memiliki sertifikat standar yang diterbitkan oleh LSPr (khusus PMA)', 'Memiliki Dokumen Penilaian Mandiri Kesiapan Penerapan Standar usaha Promotor Kegiatan Olahraga meliputi Sarana, Struktur Organisasi dan SDM, Pelayanan, Produk usaha dan Sistem Manajemen Usaha'], 'pb_umku': [], 'parameter': 'Seluruh', 'kewenangan': 'Bupati/Walikota', 'sanksi_peringatan': 'Peringatan tertulis', 'sanksi_denda': 'Denda administratif', 'sanksi_penghentian': 'Penghentian sementara kegiatan usaha', 'sanksi_pencabutan': 'Pencabutan persyaratan dasar, PB, dan/atau PB UMKU', 'fiktif_positif': True, 'dati_inferiti': True}, {'skala_usaha': ['Kecil', 'Menengah', 'Besar'], 'kategori_risiko': 'Menengah Rendah', 'perizinan': 'NIB dan Sertifikat Standar', 'persyaratan': [], 'jangka_waktu': 'Otomatis', 'kewajiban': ['Memiliki sertifikat standar yang diterbitkan oleh LSPr (khusus PMA)', 'Memiliki Dokumen Penilaian Mandiri Kesiapan Penerapan Standar usaha Aktivitas Perburuan meliputi Sarana, Struktur Organisasi dan SDM, Pelayanan, Produk usaha dan Sistem Manajemen Usaha'], 'pb_umku': ['-'], 'parameter': 'Seluruh', 'kewenangan': 'Bupati/Walikota', 'sanksi_peringatan': 'Peringatan tertulis', 'sanksi_denda': 'Denda administratif', 'sanksi_penghentian': 'Penghentian sementara kegiatan usaha', 'sanksi_pencabutan': 'Pencabutan persyaratan dasar, PB, dan/atau PB UMKU', 'fiktif_positif': True, 'dati_inferiti': True}]

LOT9_PRE_CURE_PER_SKALA_SNAPSHOT = {
    "93191": LOT9_PRE_CURE_PER_SKALA_93191,
    "93193": LOT9_PRE_CURE_PER_SKALA_93193,
}


@pytest.mark.parametrize("path", _existing_dataset_copies(), ids=_DATASET_IDS)
@pytest.mark.parametrize("code", LOT9_METADATA_ONLY_CODES)
def test_lot9_metadata_only_per_skala_completely_untouched(path: Path, code: str):
    """GUILT+INNOCENCE, the lot's sharpest invariant: 93191/93193 are action=metadata_only --
    per_skala must be UNCHANGED from its pre-cure value, BYTE-IDENTICAL (both tiers, including the
    KNOWN cross-contaminated content), never detached, never folded into the disputed key."""
    rec = _load_record(path, code)
    per_skala = rec.get("per_skala")
    assert isinstance(per_skala, list) and len(per_skala) == 2, (
        f"{path}: {code}.per_skala expected exactly 2 tiers (untouched by this cure), got "
        f"{type(per_skala)} / len={len(per_skala) if isinstance(per_skala, list) else None!r}"
    )
    expected = LOT9_PRE_CURE_PER_SKALA_SNAPSHOT[code]
    actual_dump = json.dumps(per_skala, sort_keys=True, ensure_ascii=False)
    expected_dump = json.dumps(expected, sort_keys=True, ensure_ascii=False)
    assert actual_dump == expected_dump, (
        f"{path}: {code}.per_skala drifted from its hardcoded pre-cure snapshot -- this code is "
        "action=metadata_only this lot, per_skala must be byte-identical before/after."
    )
    assert DISPUTED_KEY not in rec, (
        f"{path}: {code} unexpectedly carries {DISPUTED_KEY!r} -- action=metadata_only codes must "
        "never get a disputed-key fold (per_skala was never detached)."
    )


def test_lot9_metadata_only_status_mapping_corrected():
    """93191/93193 get ONLY a status_mapping correction this lot (gate report 3.4) --
    MATCH_LANGSUNG -> MATCH_CON_AGGREGAZIONE, a genuine 2-parent crosswalk merge mislabeled."""
    for code in LOT9_METADATA_ONLY_CODES:
        rec = _load_record(CANONICAL_PATH, code)
        assert rec.get("status_mapping") == "MATCH_CON_AGGREGAZIONE", (
            f"{code}: status_mapping expected MATCH_CON_AGGREGAZIONE (metadata_only correction), "
            f"got {rec.get('status_mapping')!r}"
        )


def test_lot9_metadata_only_whatyouneed_untouched():
    """93191/93193 carry no whatYouNeed key in the spec -- canonical's intel_2026.whatYouNeed must
    remain whatever it already was, never rewritten to an honest-gap text this lot (per_skala
    itself was never detached, so there is no gap to declare)."""
    spec_by_code = _load_lot9_spec_by_code()
    for code in LOT9_METADATA_ONLY_CODES:
        assert "whatYouNeed" not in spec_by_code[code], (
            f"{code}: spec unexpectedly declares a whatYouNeed key -- this lot's metadata_only "
            "entries must carry none (per_skala/whatYouNeed stay completely out of scope)."
        )


# ---------------------------------------------------------------------------
# 3. _data_note verbatim from spec (all 10 codes)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT9_CODES)
def test_lot9_data_note_matches_spec_verbatim(code: str):
    """_data_note must be copied VERBATIM from the cure spec -- the compiler never authors a
    replacement licensing value or paraphrases the provenance note (rule #9
    no-new-values-without-provenance)."""
    spec_by_code = _load_lot9_spec_by_code()
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("_data_note") == spec_by_code[code]["data_note"], (
        f"{code}: _data_note drifted from scripts/kbli_filiera/cure_specs/batch_a_lot9.json -- "
        "the compiler must copy data_note verbatim."
    )


# ---------------------------------------------------------------------------
# 4. intel_2026.whatYouNeed honest gap, verbatim from spec (GROUP A only)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT9_DETACH_CODES)
def test_lot9_whatYouNeed_honest_gap(code: str):
    """intel_2026.whatYouNeed must be rewritten to the spec's honest-gap text VERBATIM --
    replacing the stale client-facing prose derived from the detached (source-absent) per_skala
    rows."""
    spec_by_code = _load_lot9_spec_by_code()
    rec = _load_record(CANONICAL_PATH, code)
    intel = rec.get("intel_2026") or {}
    assert intel.get("whatYouNeed") == spec_by_code[code]["whatYouNeed"], (
        f"{code}: intel_2026.whatYouNeed does not match the spec's honest-gap text verbatim -- "
        "the compiler must copy whatYouNeed verbatim, never paraphrase or invent it."
    )


# ---------------------------------------------------------------------------
# 5. pp28_sources untouched (all 10 codes, including 93197's honest split-parent citation and
#    93191/93193/93199's true merge-siblings which are provenance-only, never injected)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT9_CODES)
def test_lot9_pp28_sources_untouched(code: str):
    """pp28_sources is provenance/audit and must survive the cure unchanged -- even for
    93191/93193/93199, whose true 2-parent-merge siblings (82302/91037/51106) are established this
    session: the compiler never authors new source values (rule #9, Lot 1-8 detach convention)."""
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("pp28_sources") == LOT9_PP28_SOURCES[code], (
        f"{code}: pp28_sources drifted from its pre-cure value {LOT9_PP28_SOURCES[code]!r} -- "
        "must be preserved untouched (rule: KEEP pp28_sources unchanged)."
    )


# ---------------------------------------------------------------------------
# 6. status_mapping -- corrected on 93191/93193/93199, untouched on the other 7
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT9_CODES)
def test_lot9_status_mapping_matches_expected_post_cure_value(code: str):
    rec = _load_record(CANONICAL_PATH, code)
    expected = LOT9_POST_CURE_STATUS_MAPPING[code]
    assert rec.get("status_mapping") == expected, (
        f"{code}: status_mapping is {rec.get('status_mapping')!r}, expected {expected!r} "
        "(gate report 3.4 -- 93191/93193/93199 corrected to MATCH_CON_AGGREGAZIONE, every other "
        "code in this lot untouched, including 93197's already-correct CODICE_RINUMERATO)."
    )


# ---------------------------------------------------------------------------
# 6b. whatChanged -- corrected on 93191/93193/93199 alongside status_mapping (Kimi K3 adversarial
#     review, THIRD SIGNING, 2026-07-20): status_mapping_correction alone left
#     intel_2026.whatChanged asserting "Direct match ... same code, same scope" -- a
#     self-contradiction the cure itself introduced (pre-cure the record was consistently wrong;
#     a status_mapping-only fix would leave it self-contradictory). Fixed by adding
#     whatChanged_correction to these 3 spec entries, naming both merge-parent codes, matching the
#     established dataset convention every one of the 202 pre-existing MATCH_CON_AGGREGAZIONE
#     records already follows (verified this session: e.g. 93291/93294 read "Consolidated from
#     multiple KBLI 2020 codes (MATCH_CON_AGGREGAZIONE). ...").
# ---------------------------------------------------------------------------

LOT9_WHATCHANGED_CORRECTED_CODES = ["93191", "93193", "93199"]

# code -> the OTHER KBLI-2020 merge-parent absorbed into this 2025 code (gate report 3.4, BPS
# Lampiran 10 p.438/p.439 reverse-crosswalk, image-verified) -- the whatChanged text must name
# this parent code so the contradiction fix is itself verifiable, not just "some other text".
LOT9_WHATCHANGED_MERGE_PARENT = {
    "93191": "82302",
    "93193": "91037",
    "93199": "51106",
}

# Stale phrases the pre-cure whatChanged text used (verbatim, per-code, hardcoded from a direct
# read of the canonical dataset BEFORE this fix -- see Kimi K3 THIRD SIGNING finding). These must
# be GONE post-fix: leaving any of them would mean the self-contradiction survived.
LOT9_WHATCHANGED_STALE_PHRASES = {
    "93191": "Direct match from KBLI 2020 (MATCH_LANGSUNG). Same code, same scope.",
    "93193": "Direct 1:1 match from KBLI 2020 — code and scope unchanged.",
    "93199": "Direct 1:1 match from KBLI 2020 — code and scope unchanged.",
}


@pytest.mark.parametrize("code", LOT9_WHATCHANGED_CORRECTED_CODES)
def test_lot9_whatchanged_corrects_aggregation_mislabel(code: str):
    """GUILT, core fix: canonical intel_2026.whatChanged must match the spec's
    whatChanged_correction VERBATIM, must name the merge-parent code (so the fix is itself
    falsifiable), and must no longer carry the stale MATCH_LANGSUNG-era phrasing that
    contradicted this cure's own status_mapping correction."""
    spec_by_code = _load_lot9_spec_by_code()
    entry = spec_by_code[code]
    assert "whatChanged_correction" in entry, f"{code}: spec missing whatChanged_correction"
    target = entry["whatChanged_correction"]

    rec = _load_record(CANONICAL_PATH, code)
    intel = rec.get("intel_2026") or {}
    actual = intel.get("whatChanged")
    assert actual == target, (
        f"{code}: intel_2026.whatChanged does not match the spec's whatChanged_correction "
        f"verbatim -- the compiler must copy it verbatim, never paraphrase or invent it."
    )

    parent = LOT9_WHATCHANGED_MERGE_PARENT[code]
    assert _contains_word_or_phrase(actual, parent), (
        f"{code}: corrected whatChanged does not name its merge-parent code {parent!r} -- "
        f"whatChanged: {actual!r}"
    )
    assert "MATCH_CON_AGGREGAZIONE" in actual, (
        f"{code}: corrected whatChanged does not name MATCH_CON_AGGREGAZIONE, breaking the "
        f"dataset's established convention (every pre-existing aggregation record does). "
        f"whatChanged: {actual!r}"
    )

    stale = LOT9_WHATCHANGED_STALE_PHRASES[code]
    assert stale not in actual, (
        f"{code}: corrected whatChanged still carries the stale pre-fix phrase {stale!r} -- the "
        "self-contradiction with status_mapping=MATCH_CON_AGGREGAZIONE was not actually fixed."
    )
    assert "same code, same scope" not in actual.lower(), (
        f"{code}: whatChanged still asserts 'same code, same scope', contradicting this code's "
        f"own status_mapping=MATCH_CON_AGGREGAZIONE (a genuine 2-parent merge). whatChanged: "
        f"{actual!r}"
    )
    assert not actual.lower().startswith("direct"), (
        f"{code}: whatChanged still opens with a 'Direct match' framing, contradicting this "
        f"code's own status_mapping=MATCH_CON_AGGREGAZIONE. whatChanged: {actual!r}"
    )


@pytest.mark.parametrize("code", [c for c in LOT9_CODES if c not in LOT9_WHATCHANGED_CORRECTED_CODES])
def test_lot9_whatchanged_untouched_outside_the_3_corrected_codes(code: str):
    """INNOCENCE: the other 7 codes in this lot must carry NO whatChanged_correction in the spec
    -- this fix is scoped to exactly the 3 codes whose status_mapping was also corrected."""
    spec_by_code = _load_lot9_spec_by_code()
    assert "whatChanged_correction" not in spec_by_code[code], (
        f"{code}: spec unexpectedly declares whatChanged_correction -- this fix must stay scoped "
        "to 93191/93193/93199."
    )


def test_lot9_spec_declares_status_mapping_correction_only_where_adjudicated():
    """Guard against the spec silently growing (or losing) a correction key beyond what the gate
    report 3.4 adjudicated: exactly 93191, 93193, 93199 declare status_mapping_correction; the
    other 7 codes in this lot declare none.

    93191/93193/93199 ALSO declare whatChanged_correction (Kimi K3 adversarial-review finding,
    THIRD SIGNING, 2026-07-20: the status_mapping_correction alone left intel_2026.whatChanged
    asserting "Direct match ... same code, same scope" for these 3 codes -- a self-contradiction
    the cure itself created, since the corrected status_mapping now says MATCH_CON_AGGREGAZIONE.
    See test_lot9_whatchanged_corrects_aggregation_mislabel below for the fixed-value assertions.
    """
    spec_by_code = _load_lot9_spec_by_code()
    expected_correction_codes = {"93191", "93193", "93199"}
    for code in LOT9_CODES:
        entry = spec_by_code[code]
        has_correction = "status_mapping_correction" in entry
        assert has_correction == (code in expected_correction_codes), (
            f"{code}: status_mapping_correction presence is {has_correction}, expected "
            f"{code in expected_correction_codes} per gate report 3.4."
        )
        if has_correction:
            assert entry["status_mapping_correction"] == "MATCH_CON_AGGREGAZIONE"
        has_whatchanged_correction = "whatChanged_correction" in entry
        assert has_whatchanged_correction == (code in expected_correction_codes), (
            f"{code}: whatChanged_correction presence is {has_whatchanged_correction}, expected "
            f"{code in expected_correction_codes} (Kimi K3 THIRD SIGNING finding -- must travel "
            "together with status_mapping_correction on exactly these 3 codes, never alone, "
            "never on the other 7)."
        )
        assert "pp28_sources_correction" not in entry, (
            f"{code}: spec unexpectedly declares pp28_sources_correction "
            f"{entry.get('pp28_sources_correction')!r}"
        )
        assert "zantaraOpener_correction" not in entry, (
            f"{code}: spec unexpectedly declares zantaraOpener_correction "
            f"{entry.get('zantaraOpener_correction')!r} -- out of scope for this lot (see module "
            "docstring 'Discovery flagged but explicitly OUT OF SCOPE')."
        )


def test_lot9_spec_action_metadata_only_matches_group_b_exactly():
    """Exactly the 2 Group-B codes declare action=metadata_only; every Group-A code has no
    action key (implicit default: detach)."""
    spec_by_code = _load_lot9_spec_by_code()
    for code in LOT9_CODES:
        entry = spec_by_code[code]
        if code in LOT9_METADATA_ONLY_CODES:
            assert entry.get("action") == "metadata_only", (
                f"{code}: expected action=metadata_only (Group B), got {entry.get('action')!r}"
            )
        else:
            assert "action" not in entry, (
                f"{code}: unexpectedly declares an action key {entry.get('action')!r} -- Group A "
                "codes must use the implicit default (detach), no explicit action."
            )


# ---------------------------------------------------------------------------
# 7. Idempotency: compiler dry-run over the served dataset reports every code already-cured
#    (no-op).
# ---------------------------------------------------------------------------

def test_lot9_compiler_dry_run_reports_already_cured():
    result = subprocess.run(
        [
            "python3",
            str(REPO_ROOT / "scripts/kbli_filiera/cure_canonical_collisions.py"),
            "--spec",
            str(LOT9_SPEC_PATH),
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
    for code in LOT9_CODES:
        assert f"{code}: ALREADY CURED (skip)" in result.stdout, (
            f"expected '{code}: ALREADY CURED (skip)' in dry-run output, not found. "
            f"stdout:\n{result.stdout}"
        )


# ---------------------------------------------------------------------------
# 8. INNOCENCE (scar #3 discipline) -- legitimate neighbor codes must be untouched by this spec.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", INNOCENT_NEIGHBORS)
def test_lot9_innocent_neighbors_untouched(code: str):
    """These codes are legitimate neighbors (or this same gate report's own explicitly-excluded
    innocence controls) and are NOT part of this cure -- if the cure ever over-reaches onto one of
    them, this must fail."""
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("per_skala"), (
        f"{code}: per_skala unexpectedly empty -- this is an innocence control, not one of the "
        "10 Lot-9 codes; the cure must not have touched it."
    )
    assert DISPUTED_KEY not in rec, (
        f"{code}: unexpectedly carries {DISPUTED_KEY!r} -- this code was never part of the "
        "batch_a_lot9 cure spec."
    )
    assert "_data_note" not in rec, (
        f"{code}: unexpectedly carries a _data_note -- this code was never part of the "
        "batch_a_lot9 cure spec."
    )


def test_lot9_innocent_neighbors_status_mapping_unchanged():
    """46201/96300 (this gate's own innocence controls) keep their pre-cure status_mapping --
    46201 MATCH_LANGSUNG (clean direct match), 96300 BPS_ONLY (no PP28 layer applies at all)."""
    assert _load_record(CANONICAL_PATH, "46201").get("status_mapping") == "MATCH_LANGSUNG"
    assert _load_record(CANONICAL_PATH, "96300").get("status_mapping") == "BPS_ONLY"


# ---------------------------------------------------------------------------
# 9. Content markers -- verified verbatim in _data_note only, AND verified non-colliding across
#    the other 9 codes in this lot.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT9_CODES)
def test_lot9_data_note_content_marker_present(code: str):
    rec = _load_record(CANONICAL_PATH, code)
    note = rec.get("_data_note", "")
    marker = LOT9_DATA_NOTE_MARKERS[code]
    assert _contains_word_or_phrase(note, marker), (
        f"{code}: expected marker {marker!r} not found inside _data_note -- the provenance note "
        f"may have drifted from the spec. _data_note: {note!r}"
    )


@pytest.mark.parametrize("code", LOT9_CODES)
def test_lot9_data_note_marker_does_not_collide_with_siblings(code: str):
    """Guard-over-match antidote: each code's marker must NOT appear inside any OTHER Lot-9
    code's _data_note -- 93192/93197 in particular share a large common SPLIT-description prefix,
    so their markers deliberately lean on the divergent tail (self-referential vs split-parent
    citation wording) to stay non-colliding."""
    marker = LOT9_DATA_NOTE_MARKERS[code]
    for other in LOT9_CODES:
        if other == code:
            continue
        other_note = _load_record(CANONICAL_PATH, other).get("_data_note", "")
        assert marker not in other_note, (
            f"{code}'s marker {marker!r} unexpectedly also appears in {other}'s _data_note -- "
            "marker is not code-specific, guard-over-match risk."
        )


# ---------------------------------------------------------------------------
# 10. Byte-identical disputed payload group -- 93192/93197/93199's generic single-tier template
#     must survive the cure exactly as found. 93127/93128/93129/93194/93195 each carry their own
#     distinct disputed payload, not part of this group.
# ---------------------------------------------------------------------------

def test_lot9_generic_template_group_shares_byte_identical_disputed_payload():
    """93192 (Aktivitas Juri dan Wasit Profesional) / 93197 (Aktivitas Olaharagawan/Atlet
    Independen) / 93199 (Aktivitas Lainnya YTDL) share the IDENTICAL generic single-tier licensing
    template (Rendah risk / NIB only / 'submit periodic activity reports' / skala_usaha
    Mikro-Kecil-Menengah) -- must survive byte-identical."""
    blobs = {
        code: json.dumps(
            _load_record(CANONICAL_PATH, code).get(DISPUTED_KEY), sort_keys=True, ensure_ascii=False
        )
        for code in LOT9_GENERIC_TEMPLATE_GROUP
    }
    reference_code = LOT9_GENERIC_TEMPLATE_GROUP[0]
    reference = blobs[reference_code]
    for code, blob in blobs.items():
        assert blob == reference, (
            f"{code}: preserved disputed block diverges from {reference_code}'s -- these three "
            "codes should share a byte-identical generic licensing template."
        )
    marker = "Menyampaikan laporan kegiatan secara berkala"
    for code in LOT9_GENERIC_TEMPLATE_GROUP:
        assert marker in blobs[code], (
            f"{code}: preserved disputed block no longer carries the shared periodic-reporting "
            f"template signature {marker!r} -- audit trail may have drifted."
        )


def test_lot9_singleton_codes_are_not_byte_identical_to_the_generic_template_group():
    """GUILT+INNOCENCE: 93127 (Klub Kebugaran/Fitness), 93128 (Klub Boling), 93129 (Klub Olahraga
    Lainnya), 93194 (Badan Regulasi dan Liga Olahraga), and 93195 (Aktivitas Olahraga Tradisional)
    each carry their OWN distinct disputed payload -- none should be byte-identical to the
    3-member generic template group."""
    reference = json.dumps(
        _load_record(CANONICAL_PATH, LOT9_GENERIC_TEMPLATE_GROUP[0]).get(DISPUTED_KEY),
        sort_keys=True,
        ensure_ascii=False,
    )
    for code in ("93127", "93128", "93129", "93194", "93195"):
        blob = json.dumps(
            _load_record(CANONICAL_PATH, code).get(DISPUTED_KEY), sort_keys=True, ensure_ascii=False
        )
        assert blob != reference, (
            f"{code}: preserved disputed block unexpectedly byte-identical to the generic "
            "template group -- this code should carry its own distinct payload."
        )


# ---------------------------------------------------------------------------
# 11. Gold editorial-layer cross-check (proactive fix, mirrors Lot 8 PR #2906/#2909 precedent)
# ---------------------------------------------------------------------------

LOT9_GOLD_PRESENT_CODES = ["93127", "93129", "93191", "93195", "93199"]
LOT9_GOLD_ABSENT_CODES = ["93128", "93192", "93193", "93194", "93197"]
LOT9_GOLD_FIXED_CODES = ["93127", "93129", "93195", "93199"]  # Group A intersect gold-present


def _load_gold() -> dict[str, dict[str, Any]]:
    return json.loads(GOLD_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("code", LOT9_GOLD_FIXED_CODES)
def test_lot9_gold_whatyouneed_matches_cured_canonical_honest_gap(code: str):
    """Gold's whatYouNeed for the 4 Group-A codes present in the gold editorial layer must be
    rewritten to canonical's own cured honest-gap text VERBATIM (same mechanism as Lot 8's commit
    c2269e807d) -- otherwise the stale pre-cure licensing prose keeps reaching the live
    /kbli/<code> page via LicensingSection's gold.whatYouNeed parse, even though canonical itself
    is honest."""
    gold = _load_gold()
    canon_wyn = _load_record(CANONICAL_PATH, code)["intel_2026"]["whatYouNeed"]
    assert code in gold, f"{code}: expected to be present in {GOLD_PATH}"
    assert gold[code].get("whatYouNeed") == canon_wyn, (
        f"{code}: gold whatYouNeed does not match canonical's cured honest-gap text verbatim -- "
        "gold-layer staleness fix did not land."
    )


@pytest.mark.parametrize("code", LOT9_GOLD_ABSENT_CODES)
def test_lot9_gold_absent_codes_stay_absent(code: str):
    """These 5 codes were never in the gold editorial layer to begin with -- this cure must not
    have added them (gold additions are out of scope for a per_skala/status_mapping cure)."""
    gold = _load_gold()
    assert code not in gold, (
        f"{code}: unexpectedly present in {GOLD_PATH} -- this cure must never ADD gold entries."
    )


def test_lot9_gold_93199_whatchanged_matches_cured_canonical():
    """Gold's 93199 whatChanged carried the SAME stale 'Direct 1:1 match ... code and scope
    unchanged' text as canonical's pre-fix value (Kimi K3 THIRD SIGNING finding) -- gold's flat
    top-level `whatChanged` key (gold's record shape is flat, NOT nested under intel_2026 like
    canonical's) must be rewritten to canonical's own corrected text VERBATIM, same
    verbatim-reuse mechanism as the whatYouNeed gold fix above and Lot 8's commit c2269e807d.
    93191/93193 are NOT touched here: 93191 is Group B (see
    test_lot9_gold_93191_untouched_group_b_out_of_scope below) and 93193 is confirmed absent from
    gold (LOT9_GOLD_ABSENT_CODES)."""
    gold = _load_gold()
    canon_whatchanged = _load_record(CANONICAL_PATH, "93199")["intel_2026"]["whatChanged"]
    assert "93199" in gold
    assert gold["93199"].get("whatChanged") == canon_whatchanged, (
        "93199: gold whatChanged does not match canonical's corrected whatChanged verbatim -- "
        "the gold-layer whatChanged contradiction fix did not land."
    )
    assert gold["93199"].get("whatChanged") != (
        "Direct 1:1 match from KBLI 2020 — code and scope unchanged."
    ), "93199: gold whatChanged still carries the stale pre-fix text."


def test_lot9_gold_93191_whatchanged_matches_cured_canonical():
    """Gold's 93191 whatChanged carried the SAME stale 'Unchanged from KBLI 2020 -- direct
    match' text as canonical's pre-fix value (same class of contradiction as 93199's gold
    whatChanged, fixed alongside it) -- gold's flat top-level `whatChanged` key must be
    rewritten to canonical's own corrected text VERBATIM. This is INDEPENDENT of 93191's
    whatYouNeed/per_skala freeze (test_lot9_gold_93191_untouched_group_b_out_of_scope below):
    whatChanged is mapping-derived, not per_skala-derived, and the mapping (status_mapping) IS
    corrected this lot -- so unlike whatYouNeed, gold's whatChanged for 93191 must track the
    correction, not stay frozen."""
    gold = _load_gold()
    canon_whatchanged = _load_record(CANONICAL_PATH, "93191")["intel_2026"]["whatChanged"]
    assert "93191" in gold
    assert gold["93191"].get("whatChanged") == canon_whatchanged, (
        "93191: gold whatChanged does not match canonical's corrected whatChanged verbatim -- "
        "the gold-layer whatChanged contradiction fix did not land."
    )
    assert gold["93191"].get("whatChanged") != (
        "Unchanged from KBLI 2020 — direct match."
    ), "93191: gold whatChanged still carries the stale pre-fix text."


def test_lot9_gold_93191_untouched_group_b_out_of_scope():
    """93191 IS present in gold (Group B) but must be COMPLETELY untouched by this cure -- its
    per_skala/whatYouNeed are deliberately out of scope this lot (action=metadata_only), so there
    is no cured canonical text to mirror into its gold entry. Pinned to the exact pre-cure value
    (hardcoded, verified this session) -- gold and canonical were never byte-identical to begin
    with (independently authored editorial prose), so the only invariant this lot can assert is
    that gold's text is unchanged from what it already was, never equality to canonical."""
    gold = _load_gold()
    assert "93191" in gold
    assert gold["93191"].get("whatYouNeed") == '1. **PT PMA incorporation** — notary deed, AHU registration, TDP (~2–4 weeks)\n2. **NIB via OSS** — register on oss.go.id, select this code, issued automatically (1–3 days)\n3. **NIB + Standard Certificate** (Micro / Small / Medium / Large, Medium-Low risk) — Authority: Bupati/Walikota — automatic\n4. **NIB + Standard Certificate** (Small / Medium / Large, Medium-Low risk) — Authority: Bupati/Walikota — automatic\n5. **Standard Certificate (auto-issued)** — post-license obligation\n6. **Comply with applicable standards** — post-license obligation\n\n**Authority by scale:**\nMicro / Small / Medium / Large: **Bupati/Walikota** (Otomatis) · Small / Medium / Large: **Bupati/Walikota** (Otomatis)\n\n**PMA:** Fully open — 100% foreign ownership allowed.', (
        "93191: gold whatYouNeed unexpectedly changed -- this code is Group B (metadata_only), "
        "its gold entry must be left completely untouched this lot."
    )
