"""Regression registry -- GARUDA-FILIERA Batch A Lot 10 (A-L10) tier-scoped cures, the LAST
6 codes of Batch-A's originally-scoped 114-code sweep (93111, 93112, 93114, 93119, 93191,
93193), driven by scripts/kbli_filiera/cure_specs/batch_a_lot10.json and applied via
scripts/kbli_filiera/cure_canonical_collisions.py --spec batch_a_lot10.json.

Modeled closely on test_kbli_batch_a_lot9_registry.py (Lot 9 registry, 2026-07-20) -- the
ALL_DATASET_COPIES list and the _existing_dataset_copies / _load_by_code / _load_record /
_contains_word_or_phrase helpers below are COPIED VERBATIM from that file (comment marks the
origin instead of importing, to keep this file self-contained and independently readable as its
own regression pin, same convention Lot 1-9 used).

Lot 10 disposition (gate report research/operations/2026-07-21-kbli-batch-a-lot10-conductor-gate.md,
adjudication already complete at Lot 8/Lot 9's own gates -- no new D1/D5 Workflow lane was run for
this lot, this is purely mechanical cure execution now that the tier-scoped partial_detach
primitive exists, PR #2921, 2026-07-21):

  GROUP CURE-PARTIAL (2 codes: 93114, 93191) -- action="partial_detach" + tier_selector. Each
    record carries exactly ONE genuinely sound tier (own-code PP28 row, image-verified) and ONE
    genuinely defective tier (93114: zero PP28 backing for the golf/Tinggi tier, Lot 8 gate
    report §3.4; 93191: verbatim-byte-identical foreign-activity content borrowed from 93193,
    Lot 9 gate report §2.1/§3.2). The tier-scoped selector moves ONLY the defective tier into the
    disputed key; the sound tier survives in per_skala BYTE-IDENTICAL -- the whole point of this
    primitive (PENDING-ARMS L8 §3.4/§5.1b, opened when a whole-array detach would have destroyed
    93114's/93191's sound tier).

  GROUP CURE-FULL (1 code: 93193) -- default action (no "action" key), a plain full detach. Its
    Tier 1 is the SAME foreign-activity content 93191 carries (verbatim byte-identical,
    "Promotor Kegiatan Olahraga", not 93193's own activity) and its Tier 2, while correctly named
    ("Aktivitas Perburuan", 93193's own activity), has ZERO PP28/OSS backing anywhere in the
    21-file/11,208-page vault (Lot 9 gate report §2.1, Kimi K3 red-team F2 correction) -- so once
    the contaminated Tier 1 is removed, nothing sound remains to preserve. Both tiers move to the
    disputed key, per_skala -> [].

  GROUP INNOCENCE (3 codes: 93111, 93112, 93119) -- NO spec entry, explicitly excluded. Genuinely
    clean per Lot 8 D1+D5 (own-code crosswalk + fully image-verified PP28 licensing rows, gate
    report §3.5) and this session's PP28/2025 Pasal 8(1) regulatory research (NB-3) confirming
    the fiktif_positif derivation-formula's Menengah-Tinggi/Tinggi-only scope is regulatorily
    correct, not a gap. 93112's prior "quarantined-for-derived_license" listing was additionally
    a pure tooling-inventory mistake (PR #2920): perizinan is already stated non-empty on 93112,
    so derived_license never applies to it at all. This lot does NOT touch these three codes in
    any way -- see the guard-over-match innocence tests below.

status_mapping / intel_2026.whatChanged for 93191/93193 were ALREADY corrected to
MATCH_CON_AGGREGAZIONE at Lot 9 (batch_a_lot9.json, action="metadata_only") -- this spec does
not carry a status_mapping_correction or whatChanged_correction for either code, and this file
pins that those fields stay exactly as Lot 9 left them.

Gold-editorial-layer cross-check (proactive, per Lot 8's PR #2906/#2909 + Lot 9's own gold-mirror
step precedent): of this lot's 3 real cure targets, apps/mouth/data/kbli-gold-all.json contains
an entry for 93114 (whatYouNeed rewritten to canonical's own newly-cured honest-gap text verbatim
-- same mechanism as Lot 8 commit c2269e807d / Lot 9) and for 93191 (whatYouNeed left COMPLETELY
untouched, pinned to its exact pre-cure value -- canonical's own whatYouNeed for 93191 is
similarly untouched this lot, since the retained sound tier already covers the full skala_usaha
range at identical procedural terms to the removed tier, so no client-facing claim is lost).
93193 is absent from gold entirely (confirmed this session) -- nothing to mirror there.

Discovery flagged but explicitly OUT OF SCOPE for this cure (same class Lot 9 flagged and left
for a future Appendix A / PENDING-ARMS line): canonical's own intel_2026.editorial and
intel_2026.zantaraOpener for 93114 independently assert facts derived from the now-partially-
disputed Tinggi/golf tier (e.g. "This activity survives that restriction at the Besar scale
because the record identifies that scale as Tinggi risk") -- fixing this program-wide sweep is
out of scope for a single lot's cure and is flagged in the gate report for a dedicated follow-up,
exactly as Lot 9's own analogous discovery was handled.

Scar-family #3 (guard-over-match/under-match) discipline applies throughout: every guilt
assertion is paired with an innocence assertion on a legitimate neighbor code, and every content
marker is a multi-word phrase verified (direct read of the applied canonical record in this
session, programmatic cross-check across all 3 codes' own _data_note) to actually appear
verbatim in that code's own _data_note AND to NOT collide with either of the other 2 codes in
this lot.
"""

from __future__ import annotations

import copy
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LOT10_SPEC_PATH = REPO_ROOT / "scripts/kbli_filiera/cure_specs/batch_a_lot10.json"
CANONICAL_PATH = REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"
GOLD_PATH = REPO_ROOT / "apps/mouth/data/kbli-gold-all.json"
DISPUTED_KEY = "per_skala_disputed_pp28_collision"

# --- verbatim from test_kbli_batch_a_lot9_registry.py (2026-07-20) ---------

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


def _load_lot10_spec_by_code() -> dict[str, dict[str, Any]]:
    spec = json.loads(LOT10_SPEC_PATH.read_text(encoding="utf-8"))
    assert spec["disputed_key"] == DISPUTED_KEY, (
        f"spec disputed_key drifted to {spec['disputed_key']!r}, tests hardcode {DISPUTED_KEY!r}"
    )
    return {e["code"]: e for e in spec["codes"]}


def _cure_applied() -> bool:
    """True once the canonical 93193 record shows the post-cure shape (per_skala == [] AND
    intel_2026.whatYouNeed matches the spec's honest-gap text). Pre-apply, per_skala is
    non-empty; post-apply, per_skala == [] and whatYouNeed matches. If the canonical file, the
    spec, or the 93193 record is missing entirely, treat the cure as NOT applied (module stays
    skipped rather than erroring at collection time). 93193 is used as the canary (the one
    full-detach code in this lot, same convention as every prior lot's canary choice)."""
    if not CANONICAL_PATH.exists() or not LOT10_SPEC_PATH.exists():
        return False
    try:
        rec = _load_record(CANONICAL_PATH, "93193")
        spec_by_code = _load_lot10_spec_by_code()
    except (AssertionError, KeyError):
        return False
    intel = rec.get("intel_2026") or {}
    entry = spec_by_code.get("93193", {})
    return (
        rec.get("per_skala") == []
        and intel.get("whatYouNeed") == entry.get("whatYouNeed")
    )


pytestmark = pytest.mark.skipif(
    not _cure_applied(),
    reason="batch_a_lot10 cure not yet applied -- tests arm after the data PR",
)


LOT10_CODES = ["93114", "93191", "93193"]
LOT10_PARTIAL_DETACH_CODES = ["93114", "93191"]
LOT10_FULL_DETACH_CODES = ["93193"]

# Innocence controls: this lot's own 3 explicitly-excluded codes (93111/93112/93119, gate report
# Innocence-controls section) + 2 legitimate neighbors (mirrors Lot 9's own convention: one sharp
# in-family neighbor already touched by a PRIOR lot -- 93196, untouched division-93 neighbor with
# a healthy 7-tier per_skala -- and one totally-different-division neighbor, 47111, retail).
INNOCENT_NEIGHBORS = ["93111", "93112", "93119", "93196", "47111"]

_DATASET_IDS = [str(p.relative_to(REPO_ROOT)) for p in _existing_dataset_copies()]


# ---------------------------------------------------------------------------
# 1. GROUP CURE-PARTIAL -- 93114 (golf/Tinggi tier removed, Menengah Rendah tier survives)
# ---------------------------------------------------------------------------

# Hardcoded pre-cure per_skala snapshot for 93114 (verified this session, direct read of the
# canonical dataset BEFORE this cure ran -- json.dumps(sort_keys=True) is used for comparison so
# key-order in the live file can never spuriously fail this test).
PRE_CURE_93114_TIER_SOUND = {
    "skala_usaha": ["Mikro", "Kecil", "Menengah"],
    "kategori_risiko": "Menengah Rendah",
    "perizinan": "NIB dan Sertifikat Standar",
    "persyaratan": [],
    "jangka_waktu": "Otomatis",
    "kewajiban": [
        "Menyampaikan laporan kegiatan secara berkala",
        "Memiliki Sertifikat Laik Sehat",
        "Menyampaikan dokumen penerapan standar",
    ],
    "pb_umku": ["Sertifikat Laik Sehat"],
    "parameter": "Seluruh",
    "kewenangan": "Bupati/Walikota",
    "sanksi_peringatan": "Peringatan tertulis",
    "sanksi_denda": "Denda administratif",
    "sanksi_penghentian": "Penghentian sementara kegiatan usaha",
    "sanksi_pencabutan": "Pencabutan persyaratan dasar, PB, dan/atau PB UMKU",
    "fiktif_positif": True,
}

PRE_CURE_93114_TIER_GOLF = {
    "skala_usaha": ["Menengah", "Besar"],
    "kategori_risiko": "Tinggi",
    "perizinan": "NIB dan Izin",
    "persyaratan": ["Memiliki Penilaian Mandiri Kesiapan Penerapan Standar"],
    "jangka_waktu": "14 Hari",
    "kewajiban": [
        "Memiliki Sertifikat Standar Usaha Pariwisata yang diterbitkan oleh LSPr",
        "Menerapkan standar usaha Fasilitas Lapangan Golf meliputi Sarana, Struktur Organisasi "
        "dan SDM, Pelayanan, Produk usaha dan Sistem Manajemen Usaha",
        "Memiliki Sertifikat laik sehat",
    ],
    "pb_umku": ["Sertifikat Laik Sehat"],
    "parameter": "Seluruh",
    "kewenangan": "Menteri/ Kepala Badan",
    "sanksi_peringatan": "Peringatan tertulis",
    "sanksi_denda": "Denda administratif",
    "sanksi_penghentian": "Penghentian sementara kegiatan usaha",
    "sanksi_pencabutan": "Pencabutan persyaratan dasar, PB, dan/atau PB UMKU",
    "fiktif_positif": True,
}

# 93191's two tiers (verified this session -- byte-identical to Lot 9's own hardcoded
# LOT9_PRE_CURE_PER_SKALA_93191 fixture, reproduced independently here rather than imported, same
# discipline Lot 9 itself used for its 93191/93193 pair).
PRE_CURE_93191_TIER_SOUND = {
    "skala_usaha": ["Mikro", "Kecil", "Menengah", "Besar"],
    "kategori_risiko": "Menengah Rendah",
    "perizinan": "NIB dan Sertifikat Standar",
    "persyaratan": [],
    "jangka_waktu": "Otomatis",
    "kewajiban": [
        "Memiliki sertifikat standar yang diterbitkan oleh LSPr (khusus PMA)",
        "Memiliki Dokumen Penilaian Mandiri Kesiapan Penerapan Standar usaha Promotor Kegiatan "
        "Olahraga meliputi Sarana, Struktur Organisasi dan SDM, Pelayanan, Produk usaha dan "
        "Sistem Manajemen Usaha",
    ],
    "pb_umku": [],
    "parameter": "Seluruh",
    "kewenangan": "Bupati/Walikota",
    "sanksi_peringatan": "Peringatan tertulis",
    "sanksi_denda": "Denda administratif",
    "sanksi_penghentian": "Penghentian sementara kegiatan usaha",
    "sanksi_pencabutan": "Pencabutan persyaratan dasar, PB, dan/atau PB UMKU",
    "fiktif_positif": True,
    "dati_inferiti": True,
}

PRE_CURE_93191_TIER_CONTAMINATED = {
    "skala_usaha": ["Kecil", "Menengah", "Besar"],
    "kategori_risiko": "Menengah Rendah",
    "perizinan": "NIB dan Sertifikat Standar",
    "persyaratan": [],
    "jangka_waktu": "Otomatis",
    "kewajiban": [
        "Memiliki sertifikat standar yang diterbitkan oleh LSPr (khusus PMA)",
        "Memiliki Dokumen Penilaian Mandiri Kesiapan Penerapan Standar usaha Aktivitas Perburuan "
        "meliputi Sarana, Struktur Organisasi dan SDM, Pelayanan, Produk usaha dan Sistem "
        "Manajemen Usaha",
    ],
    "pb_umku": ["-"],
    "parameter": "Seluruh",
    "kewenangan": "Bupati/Walikota",
    "sanksi_peringatan": "Peringatan tertulis",
    "sanksi_denda": "Denda administratif",
    "sanksi_penghentian": "Penghentian sementara kegiatan usaha",
    "sanksi_pencabutan": "Pencabutan persyaratan dasar, PB, dan/atau PB UMKU",
    "fiktif_positif": True,
    "dati_inferiti": True,
}

# 93193's pre-cure per_skala is the SAME two tiers as 93191's (gate report §2.1: "the FULL
# two-tier per_skala array is byte-identical between the two codes") -- hardcoded independently
# here (not derived from the 93191 constants above) to catch a copy-paste error in either
# fixture, same discipline Lot 9 used.
PRE_CURE_93193_TIER_CONTAMINATED = dict(PRE_CURE_93191_TIER_SOUND)  # Tier 1: foreign "Promotor..."
PRE_CURE_93193_TIER_OWN_UNSOURCED = dict(PRE_CURE_93191_TIER_CONTAMINATED)  # Tier 2: own "Perburuan..."


def _by_path_record(path: Path, code: str) -> dict[str, Any]:
    return _load_record(path, code)


@pytest.mark.parametrize("path", _existing_dataset_copies(), ids=_DATASET_IDS)
def test_lot10_93114_sound_tier_survives_byte_identical(path: Path):
    """GUILT+INNOCENCE, core: 93114's Menengah Rendah tier must survive in per_skala completely
    UNTOUCHED, byte-identical to its pre-cure value -- the whole point of partial_detach."""
    rec = _load_record(path, "93114")
    per_skala = rec.get("per_skala")
    assert isinstance(per_skala, list) and len(per_skala) == 1, (
        f"{path}: 93114.per_skala expected exactly 1 surviving tier (partial_detach), got "
        f"{type(per_skala)} / len={len(per_skala) if isinstance(per_skala, list) else None!r}"
    )
    actual_dump = json.dumps(per_skala[0], sort_keys=True, ensure_ascii=False)
    expected_dump = json.dumps(PRE_CURE_93114_TIER_SOUND, sort_keys=True, ensure_ascii=False)
    assert actual_dump == expected_dump, (
        f"{path}: 93114's surviving tier drifted from its hardcoded pre-cure snapshot -- the "
        "sound Menengah Rendah tier must be byte-identical before/after partial_detach."
    )


@pytest.mark.parametrize("path", _existing_dataset_copies(), ids=_DATASET_IDS)
def test_lot10_93114_golf_tier_moved_to_disputed_key(path: Path):
    rec = _load_record(path, "93114")
    disputed = rec.get(DISPUTED_KEY)
    assert isinstance(disputed, list) and len(disputed) == 1, (
        f"{path}: 93114.{DISPUTED_KEY} expected exactly 1 moved tier, got "
        f"{type(disputed)} / {disputed!r}"
    )
    actual_dump = json.dumps(disputed[0], sort_keys=True, ensure_ascii=False)
    expected_dump = json.dumps(PRE_CURE_93114_TIER_GOLF, sort_keys=True, ensure_ascii=False)
    assert actual_dump == expected_dump, (
        f"{path}: 93114's moved (golf/Tinggi) tier drifted from its hardcoded pre-cure "
        "snapshot -- must be preserved verbatim in the disputed key."
    )


@pytest.mark.parametrize("path", _existing_dataset_copies(), ids=_DATASET_IDS)
def test_lot10_93191_sound_tier_survives_byte_identical(path: Path):
    rec = _load_record(path, "93191")
    per_skala = rec.get("per_skala")
    assert isinstance(per_skala, list) and len(per_skala) == 1, (
        f"{path}: 93191.per_skala expected exactly 1 surviving tier (partial_detach), got "
        f"{type(per_skala)} / len={len(per_skala) if isinstance(per_skala, list) else None!r}"
    )
    actual_dump = json.dumps(per_skala[0], sort_keys=True, ensure_ascii=False)
    expected_dump = json.dumps(PRE_CURE_93191_TIER_SOUND, sort_keys=True, ensure_ascii=False)
    assert actual_dump == expected_dump, (
        f"{path}: 93191's surviving tier drifted from its hardcoded pre-cure snapshot -- the "
        "sound 'Promotor Kegiatan Olahraga' tier must be byte-identical before/after "
        "partial_detach."
    )


@pytest.mark.parametrize("path", _existing_dataset_copies(), ids=_DATASET_IDS)
def test_lot10_93191_contaminated_tier_moved_to_disputed_key(path: Path):
    rec = _load_record(path, "93191")
    disputed = rec.get(DISPUTED_KEY)
    assert isinstance(disputed, list) and len(disputed) == 1, (
        f"{path}: 93191.{DISPUTED_KEY} expected exactly 1 moved tier, got "
        f"{type(disputed)} / {disputed!r}"
    )
    actual_dump = json.dumps(disputed[0], sort_keys=True, ensure_ascii=False)
    expected_dump = json.dumps(PRE_CURE_93191_TIER_CONTAMINATED, sort_keys=True, ensure_ascii=False)
    assert actual_dump == expected_dump, (
        f"{path}: 93191's moved (contaminated 'Aktivitas Perburuan') tier drifted from its "
        "hardcoded pre-cure snapshot -- must be preserved verbatim in the disputed key."
    )


@pytest.mark.parametrize("path", _existing_dataset_copies(), ids=_DATASET_IDS)
def test_lot10_93191_93114_partial_detach_disputed_key_is_exactly_one_tier(path: Path):
    """INNOCENCE: partial_detach must move ONLY the flagged tier -- never both, never zero."""
    for code in LOT10_PARTIAL_DETACH_CODES:
        rec = _load_record(path, code)
        assert rec.get("per_skala") not in (None, []), (
            f"{path}: {code}.per_skala unexpectedly empty -- partial_detach must leave the "
            "sound tier in place, never empty the array entirely."
        )
        assert len(rec["per_skala"]) == 1, f"{path}: {code}.per_skala expected exactly 1 tier"
        assert len(rec.get(DISPUTED_KEY, [])) == 1, (
            f"{path}: {code}.{DISPUTED_KEY} expected exactly 1 tier"
        )


# ---------------------------------------------------------------------------
# 2. GROUP CURE-FULL -- 93193 (both tiers unsound, plain full detach)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", _existing_dataset_copies(), ids=_DATASET_IDS)
def test_lot10_93193_full_detach(path: Path):
    """GUILT, core: 93193 has ZERO sound tiers (Lot 9 gate report §2.1, Kimi K3 F2) -- per_skala
    must be fully emptied, both tiers preserved verbatim in the disputed key."""
    rec = _load_record(path, "93193")
    assert rec.get("per_skala") == [], (
        f"{path}: 93193.per_skala is not [] -- full detach must empty the array entirely."
    )
    disputed = rec.get(DISPUTED_KEY)
    assert isinstance(disputed, list) and len(disputed) == 2, (
        f"{path}: 93193.{DISPUTED_KEY} expected exactly 2 preserved tiers, got "
        f"{type(disputed)} / len={len(disputed) if isinstance(disputed, list) else None!r}"
    )
    actual_dump = json.dumps(disputed, sort_keys=True, ensure_ascii=False)
    expected_dump = json.dumps(
        [PRE_CURE_93193_TIER_CONTAMINATED, PRE_CURE_93193_TIER_OWN_UNSOURCED],
        sort_keys=True,
        ensure_ascii=False,
    )
    assert actual_dump == expected_dump, (
        f"{path}: 93193's preserved disputed block drifted from its hardcoded pre-cure "
        "snapshot -- both tiers must survive verbatim, just relocated."
    )


def test_lot10_93193_per_skala_byte_identical_to_93191_pre_cure_shape():
    """Cross-code invariant (gate report §2.1): 93193's pre-cure per_skala was byte-identical to
    93191's pre-cure per_skala -- both codes carried the SAME two tiers. Verified here against
    the independently-hardcoded 93191 fixtures above (not derived from them at import time)."""
    ninety_three_193_dump = json.dumps(
        [PRE_CURE_93193_TIER_CONTAMINATED, PRE_CURE_93193_TIER_OWN_UNSOURCED],
        sort_keys=True,
        ensure_ascii=False,
    )
    ninety_three_191_dump = json.dumps(
        [PRE_CURE_93191_TIER_SOUND, PRE_CURE_93191_TIER_CONTAMINATED],
        sort_keys=True,
        ensure_ascii=False,
    )
    assert ninety_three_193_dump == ninety_three_191_dump, (
        "93193's and 93191's pre-cure per_skala fixtures are NOT byte-identical -- this "
        "contradicts gate report §2.1's own finding; one of the two hardcoded fixtures has a "
        "transcription error."
    )


# ---------------------------------------------------------------------------
# 3. _data_note verbatim from spec (all 3 codes)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LOT10_CODES)
def test_lot10_data_note_matches_spec_verbatim(code: str):
    spec_by_code = _load_lot10_spec_by_code()
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("_data_note") == spec_by_code[code]["data_note"], (
        f"{code}: _data_note drifted from scripts/kbli_filiera/cure_specs/batch_a_lot10.json -- "
        "the compiler must copy data_note verbatim."
    )


# ---------------------------------------------------------------------------
# 4. intel_2026.whatYouNeed -- 93114 (partial honest-gap), 93193 (full honest-gap), 93191 (NO
#    change, pinned to its exact pre-cure value)
# ---------------------------------------------------------------------------

LOT10_WHATYOUNEED_CODES = ["93114", "93193"]

# 93191's exact pre-cure intel_2026.whatYouNeed (verified this session, direct read of the
# canonical dataset BEFORE this cure ran) -- must remain UNCHANGED, since this lot's spec entry
# for 93191 carries no whatYouNeed key at all (the retained sound tier already covers the full
# scale range at identical terms, no client-facing claim is lost by the tier removal).
PRE_CURE_93191_WHATYOUNEED = (
    "**All scales**: Medium-Low risk (Menengah Rendah). NIB + Standard Certificate issued "
    "**automatically**.\n\n**PMA:** Fully open (TERBUKA) — 100% foreign ownership allowed."
)


@pytest.mark.parametrize("code", LOT10_WHATYOUNEED_CODES)
def test_lot10_whatYouNeed_honest_gap(code: str):
    spec_by_code = _load_lot10_spec_by_code()
    rec = _load_record(CANONICAL_PATH, code)
    intel = rec.get("intel_2026") or {}
    assert intel.get("whatYouNeed") == spec_by_code[code]["whatYouNeed"], (
        f"{code}: intel_2026.whatYouNeed does not match the spec's honest-gap text verbatim -- "
        "the compiler must copy whatYouNeed verbatim, never paraphrase or invent it."
    )


def test_lot10_93191_whatYouNeed_untouched():
    """INNOCENCE: 93191's spec entry carries NO whatYouNeed key -- canonical's
    intel_2026.whatYouNeed must be byte-identical to its pre-cure value, never touched this lot."""
    spec_by_code = _load_lot10_spec_by_code()
    assert "whatYouNeed" not in spec_by_code["93191"], (
        "93191: spec unexpectedly declares a whatYouNeed key -- this lot's partial_detach entry "
        "for 93191 must carry none (the retained sound tier's info is unchanged)."
    )
    rec = _load_record(CANONICAL_PATH, "93191")
    intel = rec.get("intel_2026") or {}
    assert intel.get("whatYouNeed") == PRE_CURE_93191_WHATYOUNEED, (
        "93191: intel_2026.whatYouNeed drifted from its pre-cure value -- this lot must not "
        "touch it."
    )


# ---------------------------------------------------------------------------
# 5. pp28_sources / status_mapping / whatChanged untouched (all 3 codes) -- this lot changes
#    per_skala only, never these metadata fields (93191/93193's status_mapping/whatChanged were
#    already corrected at Lot 9 and must stay exactly as Lot 9 left them).
# ---------------------------------------------------------------------------

LOT10_PP28_SOURCES = {
    "93114": ["93114"],
    "93191": ["93191"],
    "93193": ["93193"],
}

LOT10_EXPECTED_STATUS_MAPPING = {
    "93114": "MATCH_LANGSUNG",
    "93191": "MATCH_CON_AGGREGAZIONE",  # Lot 9 correction, untouched by this lot
    "93193": "MATCH_CON_AGGREGAZIONE",  # Lot 9 correction, untouched by this lot
}


@pytest.mark.parametrize("code", LOT10_CODES)
def test_lot10_pp28_sources_untouched(code: str):
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("pp28_sources") == LOT10_PP28_SOURCES[code], (
        f"{code}: pp28_sources drifted from its pre-cure value {LOT10_PP28_SOURCES[code]!r} -- "
        "must be preserved untouched (rule: KEEP pp28_sources unchanged)."
    )


@pytest.mark.parametrize("code", LOT10_CODES)
def test_lot10_status_mapping_untouched_this_lot(code: str):
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("status_mapping") == LOT10_EXPECTED_STATUS_MAPPING[code], (
        f"{code}: status_mapping is {rec.get('status_mapping')!r}, expected "
        f"{LOT10_EXPECTED_STATUS_MAPPING[code]!r} -- this lot must not touch status_mapping "
        "(93191/93193 were already corrected at Lot 9)."
    )


@pytest.mark.parametrize("code", LOT10_CODES)
def test_lot10_spec_declares_no_status_mapping_or_whatchanged_correction(code: str):
    """Guard against the spec silently growing a metadata-correction key this lot never
    adjudicated -- Lot 10's scope is per_skala only."""
    spec_by_code = _load_lot10_spec_by_code()
    entry = spec_by_code[code]
    assert "status_mapping_correction" not in entry, (
        f"{code}: spec unexpectedly declares status_mapping_correction -- out of scope for "
        "Lot 10 (already corrected at Lot 9 for 93191/93193, never adjudicated for 93114)."
    )
    assert "whatChanged_correction" not in entry, (
        f"{code}: spec unexpectedly declares whatChanged_correction -- out of scope for Lot 10."
    )
    assert "pp28_sources_correction" not in entry, (
        f"{code}: spec unexpectedly declares pp28_sources_correction -- out of scope for Lot 10."
    )
    assert "zantaraOpener_correction" not in entry, (
        f"{code}: spec unexpectedly declares zantaraOpener_correction -- out of scope for Lot 10 "
        "(flagged as a discovery in the gate report, not fixed here, same as Lot 9's precedent)."
    )


def test_lot10_spec_action_matches_group_exactly():
    """Exactly the 2 partial_detach codes declare action="partial_detach" with a tier_selector;
    93193 has no action key (implicit default: full detach)."""
    spec_by_code = _load_lot10_spec_by_code()
    for code in LOT10_PARTIAL_DETACH_CODES:
        entry = spec_by_code[code]
        assert entry.get("action") == "partial_detach", (
            f"{code}: expected action='partial_detach', got {entry.get('action')!r}"
        )
        assert isinstance(entry.get("tier_selector"), dict) and entry["tier_selector"], (
            f"{code}: expected a non-empty tier_selector dict"
        )
    for code in LOT10_FULL_DETACH_CODES:
        entry = spec_by_code[code]
        assert "action" not in entry, (
            f"{code}: unexpectedly declares an action key {entry.get('action')!r} -- full-detach "
            "codes must use the implicit default (no action key)."
        )
        assert "tier_selector" not in entry, f"{code}: unexpectedly declares a tier_selector"


# ---------------------------------------------------------------------------
# 6. Idempotency: compiler dry-run over the served dataset reports every code already-cured
#    (no-op).
# ---------------------------------------------------------------------------

def test_lot10_compiler_dry_run_reports_already_cured():
    result = subprocess.run(
        [
            "python3",
            str(REPO_ROOT / "scripts/kbli_filiera/cure_canonical_collisions.py"),
            "--spec",
            str(LOT10_SPEC_PATH),
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
    for code in LOT10_CODES:
        assert f"{code}: ALREADY CURED (skip)" in result.stdout, (
            f"expected '{code}: ALREADY CURED (skip)' in dry-run output, not found. "
            f"stdout:\n{result.stdout}"
        )


# ---------------------------------------------------------------------------
# 7. INNOCENCE (scar #3 discipline) -- the 3 explicitly-excluded innocence-control codes + 2
#    legitimate neighbors must be completely untouched by this spec.
# ---------------------------------------------------------------------------

LOT10_INNOCENCE_CONTROLS_STATUS_MAPPING = {
    "93111": "MATCH_LANGSUNG",
    "93112": "MATCH_LANGSUNG",
    "93119": "MATCH_LANGSUNG",
}


@pytest.mark.parametrize("code", INNOCENT_NEIGHBORS)
def test_lot10_innocent_neighbors_untouched(code: str):
    """These codes are legitimate neighbors (93196, 47111) or this lot's own explicitly-excluded
    innocence controls (93111, 93112, 93119) -- NOT part of this cure. If the cure ever
    over-reaches onto one of them, this must fail."""
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("per_skala"), (
        f"{code}: per_skala unexpectedly empty -- this code is not one of the 3 Lot-10 cure "
        "targets; the cure must not have touched it."
    )
    assert DISPUTED_KEY not in rec, (
        f"{code}: unexpectedly carries {DISPUTED_KEY!r} -- this code was never part of the "
        "batch_a_lot10 cure spec."
    )
    assert "_data_note" not in rec, (
        f"{code}: unexpectedly carries a _data_note -- this code was never part of the "
        "batch_a_lot10 cure spec."
    )


def test_lot10_innocence_controls_status_mapping_unchanged():
    """93111/93112/93119 (this lot's own explicitly-excluded innocence controls) keep their
    pre-cure status_mapping -- all three are clean direct matches, MATCH_LANGSUNG."""
    for code, expected in LOT10_INNOCENCE_CONTROLS_STATUS_MAPPING.items():
        assert _load_record(CANONICAL_PATH, code).get("status_mapping") == expected, (
            f"{code}: status_mapping unexpectedly changed -- this is an innocence control, not "
            "a Lot 10 cure target."
        )


def test_lot10_innocence_controls_fiktif_positif_legacy_value_preserved():
    """93111/93119's fiktif_positif=true is a KNOWN, deliberately-preserved legacy artifact (this
    session's regulatory research, gate report Innocence-controls section) -- it must survive
    untouched, never silently corrected by this cure (this cure does not touch these codes at
    all -- this test pins that non-touch at the field level specifically flagged as
    'quarantined')."""
    rec_93111 = _load_record(CANONICAL_PATH, "93111")
    rec_93119 = _load_record(CANONICAL_PATH, "93119")
    assert rec_93111["per_skala"][0].get("fiktif_positif") is True
    assert rec_93119["per_skala"][0].get("fiktif_positif") is True


def test_lot10_93112_derived_license_never_applicable_perizinan_non_empty():
    """93112's own per_skala row has a non-empty `perizinan` -- confirms the gate report's
    Innocence-controls reasoning (PR #2920): derived_license never applies here per the
    D5_SCHEMA field description ("the license type the frontend derives from risk WHEN
    PERIZINAN IS EMPTY"), so 93112 should never have been listed as needing that field verified."""
    rec = _load_record(CANONICAL_PATH, "93112")
    assert rec["per_skala"][0].get("perizinan"), (
        "93112: expected a non-empty perizinan on its per_skala row -- if this is ever empty, "
        "the gate report's derived_license reasoning for excluding 93112 no longer holds and "
        "this code may need re-adjudication before being excluded from a future spec."
    )


# ---------------------------------------------------------------------------
# 8. Content markers -- verified verbatim in _data_note only, AND verified non-colliding across
#    the other 2 codes in this lot.
# ---------------------------------------------------------------------------

LOT10_DATA_NOTE_MARKERS = {
    "93114": "KECUALI Lapangan Golf",
    "93191": "93193's own activity, not 93191's",
    "93193": "93193 has ZERO genuinely sound tiers",
}


@pytest.mark.parametrize("code", LOT10_CODES)
def test_lot10_data_note_content_marker_present(code: str):
    rec = _load_record(CANONICAL_PATH, code)
    note = rec.get("_data_note", "")
    marker = LOT10_DATA_NOTE_MARKERS[code]
    assert _contains_word_or_phrase(note, marker), (
        f"{code}: expected marker {marker!r} not found inside _data_note -- the provenance note "
        f"may have drifted from the spec. _data_note: {note!r}"
    )


@pytest.mark.parametrize("code", LOT10_CODES)
def test_lot10_data_note_marker_does_not_collide_with_siblings(code: str):
    """Guard-over-match antidote: each code's marker must NOT appear inside either OTHER Lot-10
    code's _data_note."""
    marker = LOT10_DATA_NOTE_MARKERS[code]
    for other in LOT10_CODES:
        if other == code:
            continue
        other_note = _load_record(CANONICAL_PATH, other).get("_data_note", "")
        assert marker not in other_note, (
            f"{code}'s marker {marker!r} unexpectedly also appears in {other}'s _data_note -- "
            "marker is not code-specific, guard-over-match risk."
        )


# ---------------------------------------------------------------------------
# 9. Gold editorial-layer cross-check (proactive fix, mirrors Lot 8/9 precedent)
# ---------------------------------------------------------------------------

LOT10_GOLD_PRESENT_CODES = ["93114", "93191"]
LOT10_GOLD_ABSENT_CODES = ["93193"]

# 93191's exact pre-cure gold whatYouNeed (hardcoded verbatim from
# test_kbli_batch_a_lot9_registry.py's own pin -- Lot 9 never touched it, and this lot does not
# either, since canonical's own whatYouNeed for 93191 is also unchanged this lot).
PRE_CURE_93191_GOLD_WHATYOUNEED = (
    '1. **PT PMA incorporation** — notary deed, AHU registration, TDP (~2–4 weeks)\n'
    '2. **NIB via OSS** — register on oss.go.id, select this code, issued automatically (1–3 '
    'days)\n'
    '3. **NIB + Standard Certificate** (Micro / Small / Medium / Large, Medium-Low risk) — '
    'Authority: Bupati/Walikota — automatic\n'
    '4. **NIB + Standard Certificate** (Small / Medium / Large, Medium-Low risk) — Authority: '
    'Bupati/Walikota — automatic\n'
    '5. **Standard Certificate (auto-issued)** — post-license obligation\n'
    '6. **Comply with applicable standards** — post-license obligation\n\n'
    '**Authority by scale:**\n'
    'Micro / Small / Medium / Large: **Bupati/Walikota** (Otomatis) · Small / Medium / Large: '
    '**Bupati/Walikota** (Otomatis)\n\n'
    '**PMA:** Fully open — 100% foreign ownership allowed.'
)


def _load_gold() -> dict[str, dict[str, Any]]:
    return json.loads(GOLD_PATH.read_text(encoding="utf-8"))


def test_lot10_gold_93114_whatyouneed_matches_cured_canonical_honest_gap():
    """Gold's whatYouNeed for 93114 must be rewritten to canonical's own cured (partial)
    honest-gap text VERBATIM (same mechanism as Lot 8 commit c2269e807d / Lot 9's own gold-mirror
    step) -- otherwise the stale pre-cure golf-tier licensing prose keeps reaching the live
    /kbli/93114 page via LicensingSection's gold.whatYouNeed parse, even though canonical itself
    is honest about the golf tier's gap."""
    gold = _load_gold()
    canon_wyn = _load_record(CANONICAL_PATH, "93114")["intel_2026"]["whatYouNeed"]
    assert "93114" in gold, "expected 93114 to be present in kbli-gold-all.json"
    assert gold["93114"].get("whatYouNeed") == canon_wyn, (
        "93114: gold whatYouNeed does not match canonical's cured honest-gap text verbatim -- "
        "gold-layer staleness fix did not land."
    )


def test_lot10_gold_93191_whatyouneed_untouched():
    """93191 IS present in gold but must be COMPLETELY untouched by this cure -- pinned to the
    exact pre-cure value (hardcoded, verified this session against Lot 9's own pin)."""
    gold = _load_gold()
    assert "93191" in gold
    assert gold["93191"].get("whatYouNeed") == PRE_CURE_93191_GOLD_WHATYOUNEED, (
        "93191: gold whatYouNeed unexpectedly changed -- this lot must not touch it (the "
        "retained sound tier's info is unchanged from what gold already described)."
    )


def test_lot10_gold_93193_absent_stays_absent():
    """93193 was never in the gold editorial layer -- this cure must not have added it (gold
    additions are out of scope for a per_skala cure)."""
    gold = _load_gold()
    assert "93193" not in gold, (
        "93193: unexpectedly present in kbli-gold-all.json -- this cure must never ADD gold "
        "entries."
    )
