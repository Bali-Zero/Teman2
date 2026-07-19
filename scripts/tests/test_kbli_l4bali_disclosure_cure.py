"""Regression registry — GARUDA-FILIERA l4_bali disclosure cure (57 codes,
2026-07-19), driven by scripts/kbli_filiera/cure_specs/l4bali_disclosure_2026_07_19.json
and applied via scripts/kbli_filiera/cure_l4bali_disclosure.py --apply.

Modeled closely on test_kbli_batch_a_lot1_registry.py — the ALL_DATASET_COPIES
list and the _existing_dataset_copies / _load_by_code / _load_record helpers
below are COPIED VERBATIM from that file (comment marks the origin instead of
importing, to keep this file self-contained and independently readable as its
own regression pin, same convention that file used).

Background (Lot 6 gate report Appendix A §A.2 finding + census
`census_disputed.py`, read-only, run 2026-07-19): 56 of the 73
`per_skala_disputed_*`-carrying codes on origin/main had a STALE-CERTIFYING
`l4_bali` block — deriving the Bali-moratorium verdict from a `kategori_risiko`
tier that lives ONLY in the disowned `per_skala_disputed_pp28_collision` block,
while still asserting `confidence` MEDIUM/HIGH and `needs_review:false` (some
`blocked:true` at HIGH confidence, e.g. 52105 — the seed finding). This cure
brings all 56 (+ 80190, guarded pending PR #2800) to the SAME disclosed shape
already proven for the 8 pilot DISCLOSED codes: confidence LOW, needs_review
true, reason preserving the original derivation sentence as an audit trail
plus a disclosure sentence naming the detached key.

HARD RULE tested throughout: l4_bali.status and l4_bali.blocked are NEVER
modified by this cure (F15 — the conservative posture stays; flipping either
would be an unauthorized re-derivation). Only confidence/needs_review/reason
change.

Scar-family #3 (guard-over-match/under-match) discipline: every guilt
assertion (the 56 cured + 80190 conditional) is paired with an innocence
assertion (the 8 DISCLOSED + 9 CLEAN pilot/structural records must be
byte-IDENTICAL to their pre-cure l4_bali — this cure must never touch them).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "scripts/kbli_filiera/cure_specs/l4bali_disclosure_2026_07_19.json"
CANONICAL_PATH = REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"
DISPUTED_KEY = "per_skala_disputed_pp28_collision"
DISCLOSURE_MARKER = "[derivation under review] "
DETACH_PHRASE = "has been detached to per_skala_disputed_pp28_collision"
GARUDA_TOKEN = "(GARUDA-FILIERA)"

# --- verbatim from test_kbli_batch_a_lot1_registry.py (2026-07-18) ---------

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


# --- end verbatim block -----------------------------------------------------


def _load_spec() -> dict[str, Any]:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


def _cure_applied() -> bool:
    """True once the canonical 52105 record (the seed finding) shows the
    post-cure disclosed shape. Gates the whole module: pre-apply, 52105's
    l4_bali.confidence is HIGH and needs_review is false; post-apply,
    confidence is LOW, needs_review is true, and reason starts with the
    disclosure marker. If the canonical file or the record is missing
    entirely, treat the cure as NOT applied (module stays skipped)."""
    if not CANONICAL_PATH.exists():
        return False
    try:
        rec = _load_record(CANONICAL_PATH, "52105")
    except AssertionError:
        return False
    l4 = rec.get("l4_bali") or {}
    return (
        l4.get("confidence") == "LOW"
        and l4.get("needs_review") is True
        and isinstance(l4.get("reason"), str)
        and l4["reason"].startswith(DISCLOSURE_MARKER)
    )


pytestmark = pytest.mark.skipif(
    not _cure_applied(),
    reason="l4bali_disclosure cure not yet applied — tests arm after the data PR",
)

_DATASET_IDS = [str(p.relative_to(REPO_ROOT)) for p in _existing_dataset_copies()]

# The 56 STALE-CERTIFYING codes (verified against the census exactly, zero
# drift, 2026-07-19). 80190 is handled separately below (guarded, PR #2800).
CURED_CODES = [
    "01700", "02201", "02402", "02409", "05102", "05200", "08920", "19206",
    "36003", "38222", "39001", "42999", "49233", "49296", "50113", "52103",
    "52105", "52219", "52232", "52239", "52299", "60101", "60103", "60201",
    "60203", "60311", "61905", "61909", "64220", "64320", "64330", "64920",
    "64940", "64955", "64996", "64997", "66113", "66116", "66123", "66124",
    "66129", "66131", "66132", "66149", "66153", "66159", "66192", "66197",
    "66211", "66224", "66292", "66299", "66309", "68123", "68125", "68126",
]
assert len(CURED_CODES) == 56, f"expected 56 cured codes, got {len(CURED_CODES)}"

# Codes whose PRE-cure l4_bali carried an extra "review_basis" key (must
# survive the cure verbatim) vs. codes that never had one (must stay absent).
REVIEW_BASIS_CODES = [
    "01700", "08920", "19206", "49233", "52103", "52105", "61909", "64220",
    "64320", "64330", "64920", "64940", "64996", "64997", "66113", "66116",
    "66123", "66124", "66129", "66131", "66132", "66149", "66153", "66159",
    "66192", "66197", "66211", "66224", "66292", "66299", "66309",
]
NO_REVIEW_BASIS_CODES = [c for c in CURED_CODES if c not in REVIEW_BASIS_CODES]
assert len(REVIEW_BASIS_CODES) == 31 and len(NO_REVIEW_BASIS_CODES) == 25

MORATORIUM_BLOCK = {
    "rule": "Bali province blocks ALL Low + Medium-Low risk KBLI for PMA (island-wide, permanent)",
    "effective": "2026-05-13",
    "source": "Gubernur letter B.27.000/642/PM/DPMPTSP",
    "virtual_office": "BANNED as PMA domicile in Bali",
}

# Pinned, byte-exact PRE-cure l4_bali for the 8 DISCLOSED pilot codes (already
# correctly disclosed by an earlier cure — cure_l4_editorial.py) + the 9 CLEAN
# structural/legal-basis codes (census-verified: their l4_bali reason does NOT
# key on a disputed-only tier). Verified by direct read of the canonical
# dataset THIS session (2026-07-19) both before and after applying
# cure_l4bali_disclosure.py --apply — none of these 17 records changed a
# single byte. This is the innocence half of the guilt+innocence discipline
# (scar-family #3): if this cure ever over-reaches onto one of them, these
# tests fail.
UNTOUCHED_L4_BALI: dict[str, dict[str, Any]] = {
    "20111": {
        "status": "NON_CLASSIFICABILE",
        "reason": "Bali moratorium applicability not classifiable: the risk tier this verdict depended on was carried over from a different activity (code-number collision) and has been detached. Pending re-derivation from the true risk tier (GARUDA-FILIERA). Previous status: OK_or_HIGHER_RISK.",
        "confidence": "LOW",
        "needs_review": True,
        "blocked": False,
        "from_2020": None,
        "moratorium": MORATORIUM_BLOCK,
    },
    "49213": {
        "status": "NON_CLASSIFICABILE",
        "reason": "Bali moratorium applicability not classifiable: the risk tier this verdict depended on was carried over from a different activity (code-number collision) and has been detached. Pending re-derivation from the true risk tier (GARUDA-FILIERA). Previous status: OK_or_HIGHER_RISK.",
        "confidence": "LOW",
        "needs_review": True,
        "blocked": False,
        "from_2020": None,
        "moratorium": MORATORIUM_BLOCK,
    },
    "50115": {
        "status": "NON_CLASSIFICABILE",
        "reason": "Bali moratorium applicability not classifiable: the risk tier this verdict depended on was carried over from a different activity (code-number collision) and has been detached. Pending re-derivation from the true risk tier (GARUDA-FILIERA). Previous status: OK_or_HIGHER_RISK.",
        "confidence": "LOW",
        "needs_review": True,
        "blocked": False,
        "from_2020": None,
        "moratorium": MORATORIUM_BLOCK,
    },
    "51103": {
        "status": "NON_CLASSIFICABILE",
        "reason": "Bali moratorium applicability not classifiable: the risk tier this verdict depended on was carried over from a different activity (code-number collision) and has been detached. Pending re-derivation from the true risk tier (GARUDA-FILIERA). Previous status: OK_or_HIGHER_RISK.",
        "confidence": "LOW",
        "needs_review": True,
        "blocked": False,
        "from_2020": None,
        "moratorium": MORATORIUM_BLOCK,
    },
    "51203": {
        "status": "NON_CLASSIFICABILE",
        "reason": "Bali moratorium applicability not classifiable: the risk tier this verdict depended on was carried over from a different activity (code-number collision) and has been detached. Pending re-derivation from the true risk tier (GARUDA-FILIERA). Previous status: OK_or_HIGHER_RISK.",
        "confidence": "LOW",
        "needs_review": True,
        "blocked": False,
        "from_2020": None,
        "moratorium": MORATORIUM_BLOCK,
    },
    "60312": {
        "status": "NON_CLASSIFICABILE",
        "reason": "Bali moratorium applicability not classifiable: the risk tier this verdict depended on was carried over from a different activity (code-number collision) and has been detached. Pending re-derivation from the true risk tier (GARUDA-FILIERA). Previous status: OK_or_HIGHER_RISK.",
        "confidence": "LOW",
        "needs_review": True,
        "blocked": False,
        "from_2020": None,
        "moratorium": MORATORIUM_BLOCK,
    },
    "64310": {
        "status": "NON_CLASSIFICABILE",
        "reason": "Bali moratorium applicability not classifiable: the risk tier this verdict depended on was carried over from a different activity (code-number collision) and has been detached. Pending re-derivation from the true risk tier (GARUDA-FILIERA). Previous status: CHIUSO_MORATORIA_BALI.",
        "confidence": "LOW",
        "needs_review": True,
        "blocked": False,
        "from_2020": None,
        "moratorium": MORATORIUM_BLOCK,
    },
    "68112": {
        "status": "NON_CLASSIFICABILE",
        "reason": "Bali moratorium applicability not classifiable: the risk tier this verdict depended on was carried over from a different activity (code-number collision) and has been detached. Pending re-derivation from the true risk tier (GARUDA-FILIERA). Previous status: CHIUSO_MORATORIA_BALI.",
        "confidence": "LOW",
        "needs_review": True,
        "blocked": False,
        "from_2020": None,
        "moratorium": MORATORIUM_BLOCK,
    },
    "01287": {
        "status": "TERTUTUP",
        "reason": "Closed to foreign ownership at the national level (TERTUTUP/0%).",
        "confidence": "HIGH",
        "needs_review": False,
        "blocked": True,
        "from_2020": None,
        "moratorium": MORATORIUM_BLOCK,
        "review_basis": "nb3_2026_06_28_moratoria_risk_tier",
    },
    "38122": {
        "status": "CHIUSO_REGOLATORE_SETTORIALE",
        "reason": "Radioactive-waste collection — strategic sector reserved to the State (BUMN) and BAPETEN; closed to private/PMA capital. [NB-3 28 June 2026]",
        "confidence": "HIGH",
        "needs_review": False,
        "blocked": True,
        "from_2020": None,
        "moratorium": MORATORIUM_BLOCK,
        "review_basis": "nb3_2026_06_28_moratoria_risk_tier",
    },
    "47771": {
        "status": "CHIUSO_PMA_NO_BESAR",
        "reason": "OSS has no Usaha Besar scale row -> reserved for UMKM; a PT PMA (Usaha Besar by law) cannot register. [structural]",
        "confidence": "HIGH",
        "needs_review": False,
        "blocked": True,
        "from_2020": None,
        "moratorium": MORATORIUM_BLOCK,
        "review_basis": "nb3_2026_06_28_moratoria_risk_tier",
    },
    "52211": {
        "status": "CHIUSO_PMA_NO_BESAR",
        "reason": "OSS has no Usaha Besar scale row (only Mikro/Kecil/Menengah) -> a PT PMA (Besar by law, Omnibus UU 6/2023) is barred by OSS-RBA scale-gating (PP 28/2025 Pasal 127). Verified NB-3 30 June 2026.",
        "confidence": "HIGH",
        "needs_review": False,
        "blocked": True,
        "from_2020": None,
        "moratorium": MORATORIUM_BLOCK,
    },
    "59131": {
        "status": "TERTUTUP",
        "reason": "Closed to foreign ownership at the national level (TERTUTUP/0%).",
        "confidence": "HIGH",
        "needs_review": False,
        "blocked": True,
        "from_2020": None,
        "moratorium": MORATORIUM_BLOCK,
        "review_basis": "nb3_2026_06_28_moratoria_risk_tier",
    },
    "64110": {
        "status": "CHIUSO_REGOLATORE_SETTORIALE",
        "reason": "Bank Sentral — exclusive State monopoly operated by Bank Indonesia; structurally closed to any private/PMA capital. [NB-3 28 June 2026]",
        "confidence": "HIGH",
        "needs_review": False,
        "blocked": True,
        "from_2020": None,
        "moratorium": MORATORIUM_BLOCK,
        "review_basis": "nb3_2026_06_28_moratoria_risk_tier",
    },
    "68127": {
        "status": "CHIUSO_BALI_PROPOSTO",
        "reason": "real estate: proposto per chiusura PMA Bali",
        "confidence": "HIGH",
        "needs_review": False,
        "blocked": False,
        "from_2020": "68111",
        "moratorium": MORATORIUM_BLOCK,
    },
    "68129": {
        "status": "CHIUSO_BALI_PROPOSTO",
        "reason": "real estate: proposto per chiusura PMA Bali",
        "confidence": "HIGH",
        "needs_review": False,
        "blocked": False,
        "from_2020": "68111",
        "moratorium": MORATORIUM_BLOCK,
    },
    "70100": {
        "status": "CHIUSO_PMA_NO_BESAR",
        "reason": "OSS has no Usaha Besar scale row -> reserved for UMKM; a PT PMA (Usaha Besar by law) cannot register. [structural]",
        "confidence": "HIGH",
        "needs_review": False,
        "blocked": True,
        "from_2020": None,
        "moratorium": MORATORIUM_BLOCK,
        "review_basis": "nb3_2026_06_28_moratoria_risk_tier",
    },
}
DISCLOSED_PILOT_CODES = [
    "20111", "49213", "50115", "51103", "51203", "60312", "64310", "68112",
]
CLEAN_CODES = [
    "01287", "38122", "47771", "52211", "59131", "64110", "68127", "68129", "70100",
]
assert set(UNTOUCHED_L4_BALI) == set(DISCLOSED_PILOT_CODES) | set(CLEAN_CODES)

# 80190's pre-merge (guarded) l4_bali shape — PR #2800 (origin/kbli/lot6-data-apply)
# not yet merged as of this cure. If the merge lands and this branch rebases
# before the cure re-runs, 80190 moves into CURED_CODES-shape instead; the test
# below handles both outcomes explicitly (never silently passes on drift).
GUARDED_80190_PRE_MERGE_L4_BALI = {
    "status": "OK_or_HIGHER_RISK",
    "reason": "medium-high/high risk → not blocked by moratorium (verify per address)",
    "confidence": "MEDIUM",
    "needs_review": False,
    "blocked": False,
    "from_2020": None,
    "moratorium": MORATORIUM_BLOCK,
}


# ---------------------------------------------------------------------------
# 1. GUILT — confidence LOW + needs_review true for all 56 cured codes.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", _existing_dataset_copies(), ids=_DATASET_IDS)
@pytest.mark.parametrize("code", CURED_CODES)
def test_cured_confidence_low_and_needs_review_true(path: Path, code: str):
    rec = _load_record(path, code)
    l4 = rec.get("l4_bali") or {}
    assert l4.get("confidence") == "LOW", (
        f"{path}: {code}.l4_bali.confidence is {l4.get('confidence')!r}, expected 'LOW' "
        "— the disclosure cure must have downgraded confidence for a STALE-CERTIFYING record."
    )
    assert l4.get("needs_review") is True, (
        f"{path}: {code}.l4_bali.needs_review is {l4.get('needs_review')!r}, expected True."
    )


# ---------------------------------------------------------------------------
# 2. GUILT — reason preserves the ORIGINAL derivation sentence (audit trail)
#    AND carries the disclosure sentence naming the detached key.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", CURED_CODES)
def test_cured_reason_contains_audit_trail_and_disclosure(code: str):
    spec = _load_spec()
    entry = spec["codes"][code]
    rec = _load_record(CANONICAL_PATH, code)
    reason = rec.get("l4_bali", {}).get("reason", "")

    assert reason.startswith(DISCLOSURE_MARKER), (
        f"{code}: reason does not start with the disclosure marker {DISCLOSURE_MARKER!r} — "
        f"got: {reason!r}"
    )
    assert entry["expected_reason"] in reason, (
        f"{code}: the ORIGINAL pre-cure reason is not preserved verbatim inside the new "
        f"reason (audit-trail requirement). Expected substring: {entry['expected_reason']!r}. "
        f"Got: {reason!r}"
    )
    assert DETACH_PHRASE in reason, (
        f"{code}: disclosure sentence missing expected phrase {DETACH_PHRASE!r} in: {reason!r}"
    )
    assert GARUDA_TOKEN in reason, (
        f"{code}: disclosure sentence missing {GARUDA_TOKEN!r} in: {reason!r}"
    )


# ---------------------------------------------------------------------------
# 3. HARD RULE — status and blocked are NEVER modified by this cure.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", CURED_CODES)
def test_cured_status_and_blocked_unchanged(code: str):
    spec = _load_spec()
    entry = spec["codes"][code]
    rec = _load_record(CANONICAL_PATH, code)
    l4 = rec.get("l4_bali") or {}
    assert l4.get("status") == entry["expected_status"], (
        f"{code}: l4_bali.status drifted to {l4.get('status')!r}, expected unchanged "
        f"{entry['expected_status']!r} — this cure must NEVER re-derive status."
    )
    assert l4.get("blocked") == entry["expected_blocked"], (
        f"{code}: l4_bali.blocked drifted to {l4.get('blocked')!r}, expected unchanged "
        f"{entry['expected_blocked']!r} — this cure must NEVER flip blocked (F15)."
    )


# ---------------------------------------------------------------------------
# 4. moratorium block + review_basis presence/value preserved verbatim.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", CURED_CODES)
def test_cured_moratorium_block_unchanged(code: str):
    rec = _load_record(CANONICAL_PATH, code)
    l4 = rec.get("l4_bali") or {}
    assert l4.get("moratorium") == MORATORIUM_BLOCK, (
        f"{code}: l4_bali.moratorium drifted from the standard boilerplate block."
    )
    assert l4.get("from_2020") is None, (
        f"{code}: l4_bali.from_2020 unexpectedly non-null: {l4.get('from_2020')!r}"
    )


@pytest.mark.parametrize("code", REVIEW_BASIS_CODES)
def test_cured_review_basis_preserved_when_present(code: str):
    rec = _load_record(CANONICAL_PATH, code)
    l4 = rec.get("l4_bali") or {}
    assert l4.get("review_basis") == "nb3_2026_06_28_moratoria_risk_tier", (
        f"{code}: l4_bali.review_basis drifted — expected preserved "
        f"'nb3_2026_06_28_moratoria_risk_tier', got {l4.get('review_basis')!r}."
    )


@pytest.mark.parametrize("code", NO_REVIEW_BASIS_CODES)
def test_cured_review_basis_absent_when_not_present_before(code: str):
    rec = _load_record(CANONICAL_PATH, code)
    l4 = rec.get("l4_bali") or {}
    assert "review_basis" not in l4, (
        f"{code}: l4_bali unexpectedly gained a 'review_basis' key — this cure must never "
        "invent one where the pre-cure record had none."
    )


# ---------------------------------------------------------------------------
# 5. per_skala stays [] (out of this cure's scope entirely — sanity check).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", CURED_CODES)
def test_cured_per_skala_untouched_empty(code: str):
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("per_skala") == [], (
        f"{code}: per_skala is not [] — this cure must never touch per_skala, only l4_bali."
    )
    assert DISPUTED_KEY in rec, (
        f"{code}: missing {DISPUTED_KEY!r} — precondition of this cure (a prior lot's detach)."
    )


# ---------------------------------------------------------------------------
# 6. INNOCENCE — the 8 DISCLOSED pilot codes + 9 CLEAN structural codes are
#    byte-IDENTICAL to their pre-cure l4_bali (this cure never touches them).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", DISCLOSED_PILOT_CODES)
def test_disclosed_pilot_records_byte_unchanged(code: str):
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("l4_bali") == UNTOUCHED_L4_BALI[code], (
        f"{code}: l4_bali drifted — this is one of the 8 pilot DISCLOSED records, already "
        "correctly disclosed by an earlier cure (cure_l4_editorial.py); the l4bali_disclosure "
        "cure must NEVER touch it. If this fails, the cure over-reached (guard-over-match)."
    )
    assert not rec["l4_bali"]["reason"].startswith(DISCLOSURE_MARKER), (
        f"{code}: reason unexpectedly carries THIS cure's marker {DISCLOSURE_MARKER!r} — "
        "the pilot codes have their OWN (earlier, differently-worded) disclosed reason."
    )


@pytest.mark.parametrize("code", CLEAN_CODES)
def test_clean_structural_records_byte_unchanged(code: str):
    rec = _load_record(CANONICAL_PATH, code)
    assert rec.get("l4_bali") == UNTOUCHED_L4_BALI[code], (
        f"{code}: l4_bali drifted — this is one of the 9 CLEAN records (structural/legal "
        "basis, not derived from a disputed-only risk tier per the census); the "
        "l4bali_disclosure cure must NEVER touch it."
    )
    assert not rec["l4_bali"]["reason"].startswith(DISCLOSURE_MARKER), (
        f"{code}: reason unexpectedly carries this cure's disclosure marker — "
        "CLEAN records were never in scope."
    )


# ---------------------------------------------------------------------------
# 7. 80190 — guarded pending PR #2800. Handles BOTH outcomes explicitly:
#    still pre-merge (disputed key absent, l4_bali pinned pre-merge shape) or
#    already merged+cured (disputed key present, cured shape like the other 56).
# ---------------------------------------------------------------------------

def test_80190_guarded_pending_pr_or_cured_after_merge():
    rec = _load_record(CANONICAL_PATH, "80190")
    has_disputed_key = DISPUTED_KEY in rec
    l4 = rec.get("l4_bali") or {}

    if not has_disputed_key:
        assert l4 == GUARDED_80190_PRE_MERGE_L4_BALI, (
            "80190: disputed key absent (PR #2800 not yet merged) but l4_bali drifted from "
            "the recorded pre-merge shape — unexpected mutation while guarded."
        )
    else:
        # #2800 merged (and this branch rebased) — 80190 should now be cured
        # exactly like the other 56, same template.
        assert l4.get("confidence") == "LOW"
        assert l4.get("needs_review") is True
        assert l4.get("status") == GUARDED_80190_PRE_MERGE_L4_BALI["status"], (
            "80190: status must stay unchanged even post-merge+cure."
        )
        assert l4.get("blocked") == GUARDED_80190_PRE_MERGE_L4_BALI["blocked"], (
            "80190: blocked must stay unchanged even post-merge+cure."
        )
        assert GUARDED_80190_PRE_MERGE_L4_BALI["reason"] in l4.get("reason", ""), (
            "80190: original reason not preserved as audit trail after cure."
        )
        assert DETACH_PHRASE in l4.get("reason", "")


# ---------------------------------------------------------------------------
# 8. Idempotency: compiler dry-run over the served dataset reports every cured
#    code already-cured (no-op) and 80190 either skipped-by-guard or cured.
# ---------------------------------------------------------------------------

def test_compiler_dry_run_reports_already_cured_and_guard():
    result = subprocess.run(
        [
            "python3",
            str(REPO_ROOT / "scripts/kbli_filiera/cure_l4bali_disclosure.py"),
            "--spec",
            str(SPEC_PATH),
            "--canonical",
            str(CANONICAL_PATH),
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
    for code in CURED_CODES:
        assert f"{code}: ALREADY CURED (skip)" in result.stdout, (
            f"expected '{code}: ALREADY CURED (skip)' in dry-run output, not found. "
            f"stdout:\n{result.stdout}"
        )
    assert (
        "80190: SKIPPED (guard)" in result.stdout
        or "80190: ALREADY CURED (skip)" in result.stdout
    ), (
        "expected 80190 to be either guard-skipped (pre-merge) or already-cured "
        f"(post-merge) in dry-run output. stdout:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# 9. Spec self-documentation.
# ---------------------------------------------------------------------------

def test_spec_hard_rule_documented():
    spec = _load_spec()
    hard_rule = spec["_meta"]["hard_rule"]
    assert "NEVER" in hard_rule and "status" in hard_rule and "blocked" in hard_rule, (
        "spec _meta.hard_rule must explicitly document that status/blocked are never modified."
    )


def test_spec_has_exactly_57_codes():
    spec = _load_spec()
    assert len(spec["codes"]) == 57, (
        f"spec expected exactly 57 codes (56 STALE-CERTIFYING + 80190 guarded), "
        f"got {len(spec['codes'])}"
    )
    assert set(spec["codes"]) == set(CURED_CODES) | {"80190"}
