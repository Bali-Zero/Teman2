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

UPDATED 2026-08-26 — THE DEAD END WAS CURED, NOT EXPLAINED AWAY. Persona #15
used to be deliberately left unexplained: it was the one real dead end, rooted in
purpose coverage (the signed pack declared `E23.covered_purposes = ["EMPLOYMENT"]`
while Kepmen M.IP-08.GR.01.01/2025, Lampiran, row E23, column Hak, item 4 — read
on the PDF at page 35 — grants an E23 holder an explicit tourism right). seq-16
folded that right into the pack and Zero signed it; persona #15 now MATCHES with
`SUPPORTED_CANDIDATES ["E23"]`. The tests below flipped accordingly: what was
"#15 must stay unexplained" is now "#15 must not be divergent at all", so a
regression that re-opens the dead end goes red just as loudly as an explanation
that papered over it would have.

WHAT BIT US RE-BINDING IT, and is now guarded: the driver requires the accepted
explanation's `pack` to match the CURRENT pack EXACTLY. seq-16 changed all four
identity fields, so every explanation silently detached and a run that had read
`explained 15 / unexplained 1` suddenly read `explained 0 / unexplained 15`. That
is the anti-staleness guard working as designed — an explanation accepted against
one pack is not automatically valid against the next. Re-binding was justified
only because all 15 divergences were measured byte-identical under seq-16 (same
`expected`/`actual`/`differences`; only the pack identity moved).
`test_the_file_is_bound_to_the_pack_the_engine_actually_serves` keeps that from
rotting in silence.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.scripts.visa_engine.gold_replay_driver import _load_accepted_explanations

_CONTRACTS = Path(__file__).resolve().parents[3] / "services" / "visa_engine" / "contracts"
_FILE = _CONTRACTS / "gold-accepted-explanations.json"

#: The persona seq-16 cured. It must NOT be divergent any more — and it must be
#: cured for the right reason (E23 supported), not by some other drift.
_CURED = 15


@pytest.fixture(scope="module")
def report() -> dict:
    assert _FILE.exists(), f"{_FILE} is committed; absent is a failure, not a skip"
    return json.loads(_FILE.read_text(encoding="utf-8"))


def test_the_file_is_a_valid_driver_input(report: dict) -> None:
    """The driver's own loader must accept it — a hand-written file that the
    real consumer rejects is a document, not a gate."""
    loaded = _load_accepted_explanations(_FILE)
    assert loaded, "loader returned nothing — the file would explain zero divergences"
    assert _CURED not in loaded, (
        "persona #15 no longer diverges, so it must carry no explanation at all"
    )


def test_every_divergence_is_explained(report: dict) -> None:
    divergent = {p["persona_id"] for p in report["personas"] if p.get("divergence")}
    explained = {
        p["persona_id"]
        for p in report["personas"]
        if p.get("divergence") and (p.get("explanation") or "").strip()
    }
    # Anti-vacuity: a parse that found nothing would make the rest trivially true.
    assert len(divergent) >= 15, f"only {len(divergent)} divergences parsed"
    assert divergent - explained == set(), (
        "the signed criterion is 'every divergence explained, and none of them a "
        f"dead end'; unexplained = {sorted(divergent - explained)}"
    )
    assert report["summary"]["unexplained_divergences"] == 0
    assert report["overall_pass"] is True


def test_the_cured_persona_is_no_longer_a_dead_end(report: dict) -> None:
    """seq-16 had one falsifiable acceptance: #15 flips from NEEDS_INPUT to
    SUPPORTED_CANDIDATES ['E23']. This is that acceptance, kept armed — if the
    purpose coverage regresses, this goes red instead of quietly returning the
    applicant to the dead end."""
    row = next(p for p in report["personas"] if p["persona_id"] == _CURED)
    assert not row.get("divergence"), (
        "persona #15 diverges again — seq-16's cure regressed; do NOT paper over it "
        "with an explanation, re-check E23.covered_purposes"
    )
    assert not (row.get("explanation") or "").strip()
    # Cured for the RIGHT reason: expected and actual agree ON E23 being supported.
    assert row["expected"]["state"] == "SUPPORTED_CANDIDATES"
    assert row["expected"]["candidate_products"] == ["E23"]
    assert row["actual"]["state"] == "SUPPORTED_CANDIDATES"
    assert row["actual"]["candidate_products"] == ["E23"]
    assert row["actual"]["missing_facts"] == []


def test_the_file_is_bound_to_the_pack_the_engine_actually_serves(report: dict) -> None:
    """The driver matches an accepted explanation only when its `pack` equals the
    CURRENT pack exactly. If this file still names an older pack, every
    explanation detaches and the gate silently reports `explained 0` — which is
    what happened the moment seq-16 was signed. Bind the file to the highest
    SIGNED pack on disk, or this goes red."""
    packs_dir = _CONTRACTS / "packs"
    signed = []
    for path in packs_dir.glob("rulepack-prod-*.signed.json"):
        env = json.loads(path.read_text(encoding="utf-8"))
        if env.get("payload", {}).get("environment") == "PRODUCTION":
            signed.append((env["payload"]["sequence"], env["payload_sha256"]))
    assert signed, "no signed PRODUCTION pack on disk — cannot bind anything"
    highest_seq, highest_sha = max(signed)
    assert report["pack"]["sequence"] == highest_seq, (
        f"this file is bound to seq {report['pack']['sequence']} but the engine "
        f"serves seq {highest_seq}; every explanation would detach"
    )
    assert report["pack"]["payload_sha256"] == highest_sha
    for row in report["personas"]:
        if (row.get("explanation") or "").strip():
            assert row["pack"]["payload_sha256"] == highest_sha


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
