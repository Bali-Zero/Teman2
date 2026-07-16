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

Follow-up (2026-07-16, same PR): the contamination had ALSO leaked into
`intel_2026.whatYouNeed` ("Self-Assessment document covering MICE venue
standards..."), a field the first pass of this fix did not touch. That field
has now been replaced verbatim. `test_68112_record_has_no_mice_venue_outside_audit_key`
is the whole-record guard added for this: it scans the ENTIRE 68112 record
(every field) for "MICE"/"Venue", excluding only the intentional audit key
`per_skala_disputed_pp28_mice` — so no other field (present or future) can
carry the collision back in unnoticed.
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
    rec = _load_record(path)
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
