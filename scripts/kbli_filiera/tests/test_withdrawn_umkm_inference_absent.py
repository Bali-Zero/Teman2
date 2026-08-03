"""No KBLI surface may re-assert the withdrawn no-Usaha-Besar inference.

THE CLAIM THIS GATE KILLS. For months the corpus argued: *OSS publishes no
Usaha Besar scale row for this code, therefore it is reserved for UMKM,
therefore a PT PMA cannot register it anywhere in Indonesia.* Permeninves/BKPM
5/2025 Pasal 26(1) inverts it — being Usaha Besar is a CONSEQUENCE of holding
PMA status, not a precondition for registering — so the inference was withdrawn
from the canonical layer and from the 1,559 public code pages on 2026-08-03,
leaving 7 codes closed on the only basis that survives: an explicit allocation
to Koperasi/UMKM in the Perpres 10/2021 (as amended by 49/2021) Lampiran II
`dialokasikan` column.

WHY IT NEEDS A GATE AND NOT A NOTE. The sentence had already been withdrawn on
the web when it was found still live, verbatim, in the macOS app's editorial
overlay — a surface installed on three machines and handed to the team as a
zip, telling the reader that a PT PMA cannot register a youth hostel, a villa
rental or a massage parlour anywhere in Indonesia. A withdrawal that is not
enforced only moves which surface still says the old thing.

SCOPE, STATED. This gate reads the two stores the monorepo owns: the canonical
record's `l4_bali.reason` and the app overlay's editorial prose. It does NOT
see the 1,559 rendered pages (those carry their own vitest population pins) nor
the Qdrant payload (published from canonical by
`kbli_qdrant_pma_sync.py --layer bali`). It is a floor, not a ceiling.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
CANONICAL = REPO / "data/source_documents/KBLI_2025_FINAL_CLEAN.json"
OVERLAY = REPO / "data/kbli-app-overlay/kbli-overlay.json"

# The inference is recognised by its LOAD-BEARING claims, each of which is the
# argument itself rather than one phrasing of it. A single literal sentence
# would be an under-match: the corpus already carried two wordings, and the one
# that got away lived in a paragraph a narrower reader never looked at.
WITHDRAWN_CLAIM = re.compile(
    r"no Usaha Besar scale row"
    r"|reserved for UMKM nationwide"
    r"|reserved for micro, small and medium enterprises \(UMKM\) nationwide"
    r"|cannot register (?:it|this activity) anywhere in Indonesia",
    re.IGNORECASE,
)

# The legitimate closure — an explicit annex allocation — must stay sayable.
# Innocence is asserted below so this gate cannot be "satisfied" by scrubbing
# every mention of UMKM from the corpus.
LEGITIMATE = (
    "Allocated to Koperasi/UMKM by Perpres 49/2021 Lampiran II (dialokasikan column): "
    "a PT PMA cannot take this bidang usaha."
)


def _canonical_rows() -> list[dict]:
    return json.loads(CANONICAL.read_text(encoding="utf-8"))["data"]


def _overlay() -> dict:
    return json.loads(OVERLAY.read_text(encoding="utf-8"))


def test_the_stores_this_gate_reads_are_actually_there():
    """A gate that silently reads nothing reports a clean world (W84). This
    fails loudly instead, and pins the populations so a truncated store cannot
    pass by being small."""
    assert CANONICAL.is_file(), f"canonical missing at {CANONICAL}"
    assert OVERLAY.is_file(), f"overlay missing at {OVERLAY}"
    assert len(_canonical_rows()) == 1559
    assert len(_overlay()) > 300


def test_no_canonical_l4_bali_reason_carries_the_withdrawn_inference():
    offenders = [
        r["kode_kbli_2025"]
        for r in _canonical_rows()
        if WITHDRAWN_CLAIM.search(str((r.get("l4_bali") or {}).get("reason") or ""))
    ]
    assert offenders == [], (
        "canonical l4_bali.reason re-asserts the withdrawn no-Usaha-Besar inference for "
        f"{offenders}. It is published to Qdrant as `bali_reason` and read aloud by the "
        "chat channel."
    )


def test_no_overlay_verdict_carries_the_withdrawn_inference():
    offenders = [
        code
        for code, entry in _overlay().items()
        if WITHDRAWN_CLAIM.search(((entry or {}).get("en") or {}).get("verdict") or "")
    ]
    assert offenders == [], (
        f"the macOS app overlay re-asserts the withdrawn inference for {offenders}. This "
        "file ships inside KBLI Navigator.app on three machines and in the team zip."
    )


def test_the_surviving_perpres_closure_is_still_sayable():
    """INNOCENCE. Seven codes are genuinely closed to PT PMA because the Perpres
    annex allocates them to Koperasi/UMKM. That sentence names UMKM and must
    pass — otherwise the cheapest way to green this gate is to delete the true
    closures along with the false ones."""
    assert WITHDRAWN_CLAIM.search(LEGITIMATE) is None

    closed = [
        r["kode_kbli_2025"]
        for r in _canonical_rows()
        if (r.get("l4_bali") or {}).get("status") == "CHIUSO_PMA_NO_BESAR"
    ]
    assert closed, "no code carries CHIUSO_PMA_NO_BESAR — the annex closures vanished"
    for code in closed:
        row = next(r for r in _canonical_rows() if r["kode_kbli_2025"] == code)
        reason = str((row.get("l4_bali") or {}).get("reason") or "")
        assert "Lampiran II" in reason and "dialokasikan" in reason, (
            f"{code} is closed as CHIUSO_PMA_NO_BESAR but its reason does not cite the "
            f"Lampiran II dialokasikan column: {reason[:160]!r}. After the withdrawal, "
            "that annex allocation is the ONLY basis this status may rest on."
        )


def test_the_editorial_prose_backlog_can_only_shrink():
    """A RATCHET, not a gate — and the difference is the point.

    The verdict layer was cured on 2026-08-03; the EDITORIAL prose that
    explains it was not. 36 codes still argue the withdrawn inference in
    `intel_2026`, in fluent English, on pages that render live — and several
    now contradict their own badge: 13 codes read NON_CLASSIFICABILE ("the
    Bali position cannot be stated") while the prose tells the reader a PT PMA
    "cannot register it", and 2 more are scope-dependent. That is the
    expensive direction of the error: it turns away business we could take.

    Curing it means re-authoring 45 passages of client-facing legal prose,
    which is a NEW claim each time and belongs behind a cross-family grader
    (W113: retracting one claim produced three false replacements, because
    every adversarial round was pointed at the sentence being removed and none
    at the sentence being written). Arming a hard gate on a live 36-code
    backlog would only turn every unrelated PR red (W95).

    So this asserts the only thing that is both true today and useful
    tomorrow: the number may fall, never rise. A new page that re-imports the
    argument fails here.
    """
    # 37 measured by THIS regex on 2026-08-03. A narrower hand-pattern gave 36 —
    # the number a ratchet pins must be the one its own guard measures, or the
    # ratchet is calibrated against a different question than it asks.
    known_backlog = 37
    offenders = sorted(
        r["kode_kbli_2025"]
        for r in _canonical_rows()
        if WITHDRAWN_CLAIM.search(json.dumps(r.get("intel_2026") or {}, ensure_ascii=False))
    )
    assert len(offenders) <= known_backlog, (
        f"{len(offenders)} canonical records now carry the withdrawn inference in editorial "
        f"prose, up from the recorded {known_backlog}. New ones: this claim was withdrawn on "
        f"2026-08-03 and may not re-enter the corpus. Offenders: {offenders}"
    )


@pytest.mark.parametrize(
    "sentence",
    [
        "OSS has no Usaha Besar scale row for this code — it is reserved for UMKM nationwide",
        "a PT PMA cannot register it anywhere in Indonesia (PP 28/2025 scale-gating)",
        "the code is reserved for micro, small and medium enterprises (UMKM) nationwide",
    ],
)
def test_guilt_every_historical_wording_is_caught(sentence: str):
    """GUILT, against the wordings that were actually live — not against a
    sentence written to match the pattern I had just written."""
    assert WITHDRAWN_CLAIM.search(sentence) is not None


@pytest.mark.parametrize(
    "sentence",
    [
        "Allocated to Koperasi/UMKM by Perpres 49/2021 Lampiran II (dialokasikan column).",
        "Blocked in Bali by the provincial PMA moratorium, independent of national opening.",
        "Reserved to Koperasi/UMKM only as to a NAMED sub-activity per Pasal 5(5).",
        "TERBUKA — 100%, and no instrument restricts it.",
    ],
)
def test_innocence_legitimate_verdicts_are_not_caught(sentence: str):
    assert WITHDRAWN_CLAIM.search(sentence) is None
