"""Regression pin — KBLI 68112 PP28-MICE code-number collision (2026-07-16).

Verified facts (image-verified 3x against the official PP 28/2025 + BPS Peraturan
7/2025 PDFs; see PR description for the full chain):
  - 68112 under BPS Peraturan 7/2025 (KBLI 2025, current — what OSS uses today) =
    residential leasing ("Aktivitas Penyewaan Bangunan dan Lahan Hunian Milik
    Sendiri atau Sewa"). The dataset's judul/uraian for this code are correct.
  - 68112 under PP 28/2025 (numbered on the OLD KBLI 2020) = a DIFFERENT activity,
    "Penyewaan Venue Penyelenggaraan Aktifitas MICE dan Event Khusus" (Lampiran
    I.L, Sektor Pariwisata, p.I.L.44 row 25) — a pure code-NUMBER collision across
    the two regulations, not the same business activity.
  - The served dataset had (until 2026-07-16) the CORRECT residential title but the
    WRONG per_skala licensing block — the PP28-MICE block, whose kewajiban text
    literally names "Penyewaan Venue Penyelenggra aan Aktifitas MICE" / mentions
    "LSPr (khusus PMA)".
  - OSS RBA ruang-lingkup for the new residential 68112 returns 404 (no published
    risk-based NSPK yet) — hence `_l2_status: "no_oss_risk"` on the record. There is
    no ground truth to fabricate a residential per_skala from, so the honest fix is
    an EMPTY per_skala (the frontend already guards `licensing.length > 0`), not a
    guess.

The fix (see scripts/sync_kbli_dataset.sh consumers): per_skala -> [], the original
MICE block preserved verbatim under `per_skala_disputed_pp28_mice` for audit (never
silently deleted), and an advisory `_data_note` added.

This test is the tripwire: it FAILS if 68112's per_skala EVER again contains the
MICE-venue licensing text, on every dataset copy that ships to a client-facing
surface. It is scoped to this ONE known historical collision — a dataset-wide
"no MICE/Venue anywhere" rule would false-positive on 68124 ("Penyewaan Tempat
Penyelenggaraan ... MICE ...") and 82300 ("Penyelenggaraan Konvensi dan Pameran
Bisnis"), which legitimately are MICE/venue/convention codes (verified 2026-07-16 —
do not generalize this guard to those records).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CODE = "68112"
CONTAMINATION_MARKERS = ("MICE", "Venue")

# Every SERVED/canonical copy that must stay clean. Gitignored RAG runtime copies
# are materialized by scripts/sync_kbli_dataset.sh at build time and may be absent
# on a fresh checkout/CI runner — skipped if missing, same convention as that script.
DATASET_PATHS = [
    REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json",  # production, balizero.com/kbli
    REPO_ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json",  # tracked fallback / canonical (via source_documents/ symlink)
    REPO_ROOT / "apps/backend-rag/backend/data/KBLI_2025_FINAL_CLEAN.json",  # gitignored, RAG runtime
]


def _load_record(path: Path) -> dict:
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
    rec = _load_record(path)
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
    rec = _load_record(REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json")
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
    rec = _load_record(REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json")
    note = rec.get("_data_note", "")
    assert "68111" in note, "advisory note should point to the nearest residential NSPK reference (68111)"
    assert "no_oss_risk" not in note  # note is prose, not a field-name echo
    assert "OSS" in note and "404" in note, "advisory note should explain the OSS 404 (no published NSPK yet)"


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
