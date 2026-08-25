"""The signed switchboard-#3 criterion, ARMED.

`OWNER-RULINGS-2026-08-25.md` §7 replaced the mandate's "zero-divergence"
wording with a criterion Zero signed:

    Every divergence explained, and none of them a dead end.

Until 2026-08-26 that criterion lived only in prose. `GOLD-DIVERGENCE-TRIAGE.md`
adjudicated all 16 divergences one by one, but the driver had never been told,
so every run still reported `explained_divergences: 0, unexplained: 16` — and
the next reader re-did the adjudication from scratch. That is not hypothetical:
the session that wrote this file did exactly that, re-raised persona #16 as a
scandal the triage had already explained in writing, and had to retract it.

`contracts/gold-accepted-explanations.json` is the transcription. These tests
are what makes it a gate rather than a document: the explanations are bound to
the exact divergence they accept (the driver re-checks `expected`/`actual`/
`pack`/`differences` verbatim), so an explanation cannot outlive the outcome it
was written for.

Persona #15 is deliberately LEFT UNEXPLAINED. It is the one real dead end, its
root is purpose coverage (the signed pack declares
`E23.covered_purposes = ["EMPLOYMENT"]` while Kepmen M.IP-08.GR.01.01/2025
Lampiran B.1 grants an E23 holder an explicit tourism right), and curing it is a
seq-16 fold. Explaining it away here would turn the gate green over a live
defect, which is the precise failure this file exists to prevent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.scripts.visa_engine.gold_replay_driver import _load_accepted_explanations

_CONTRACTS = (
    Path(__file__).resolve().parents[3] / "services" / "visa_engine" / "contracts"
)
_FILE = _CONTRACTS / "gold-accepted-explanations.json"

#: The one divergence that must NOT carry an explanation until seq-16 lands.
_DEAD_END = 15


@pytest.fixture(scope="module")
def report() -> dict:
    assert _FILE.exists(), f"{_FILE} is committed; absent is a failure, not a skip"
    return json.loads(_FILE.read_text(encoding="utf-8"))


def test_the_file_is_a_valid_driver_input(report: dict) -> None:
    """The driver's own loader must accept it — a hand-written file that the
    real consumer rejects is a document, not a gate."""
    loaded = _load_accepted_explanations(_FILE)
    assert loaded, "loader returned nothing — the file would explain zero divergences"
    assert _DEAD_END not in loaded


def test_every_divergence_except_the_dead_end_is_explained(report: dict) -> None:
    divergent = {p["persona_id"] for p in report["personas"] if p.get("divergence")}
    explained = {
        p["persona_id"]
        for p in report["personas"]
        if p.get("divergence") and (p.get("explanation") or "").strip()
    }
    # Anti-vacuity: a parse that found nothing would make the rest trivially true.
    assert len(divergent) >= 16, f"only {len(divergent)} divergences parsed"
    assert divergent - explained == {_DEAD_END}, (
        "the signed criterion is 'every divergence explained, and none of them a "
        f"dead end'; unexplained = {sorted(divergent - explained)}"
    )


def test_the_dead_end_is_not_explained_away(report: dict) -> None:
    row = next(p for p in report["personas"] if p["persona_id"] == _DEAD_END)
    assert row.get("divergence") is True
    assert not (row.get("explanation") or "").strip(), (
        "persona #15 is the live dead end; giving it an explanation turns the gate "
        "green over the defect it exists to hold open. Cure it with seq-16 instead."
    )
    # And it must still be the SAME dead end, not some other divergence that
    # drifted into the slot.
    assert row["expected"]["state"] == "SUPPORTED_CANDIDATES"
    assert row["expected"]["candidate_products"] == ["E23"]
    assert row["actual"]["state"] == "NEEDS_INPUT"
    assert "intent.requested_product_code" in row["actual"]["missing_facts"]


def test_no_explanation_is_a_placeholder(report: dict) -> None:
    """Guard against the gate being satisfied with filler."""
    for p in report["personas"]:
        text = (p.get("explanation") or "").strip()
        if not text:
            continue
        assert len(text) >= 80, f"persona #{p['persona_id']}: explanation too thin"
        lowered = text.lower()
        for filler in ("tbd", "todo", "n/a", "see above", "explained"):
            assert lowered != filler, f"persona #{p['persona_id']}: placeholder"


def test_the_two_transcribed_residuals_stay_visible(report: dict) -> None:
    """#10 and #17 were transcribed on the triage's authority, but each carries a
    doubt the triage's general reason does not settle (both are cases where the
    engine gives LESS than expected, not more). The doubt is written INTO the
    explanation on purpose; this test stops a later tidy-up from deleting it."""
    for pid in (10, 17):
        row = next(p for p in report["personas"] if p["persona_id"] == pid)
        assert "RESIDUAL" in (row.get("explanation") or ""), (
            f"persona #{pid}'s explanation must keep its recorded residual — it is "
            "the trail for the re-check owed before ENFORCE"
        )
