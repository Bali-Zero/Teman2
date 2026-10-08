"""baseline_ledger — an unchanged page is proven by fingerprint against a PROVEN attested read.

Guilt: any difference in the text, no ledger that attests the pack, the run's own ledger, a read after
the pack, a tampered saved text, a newer text file that is not the attested receipt's -> no judgement.
Innocence: the same text -> a `none` judgement.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.scripts.visa_engine import baseline_ledger as bl
from backend.scripts.visa_engine.portal_read_receipt import fingerprint

RID = "d" * 36
SHORT = RID[:8]
STAMP = "2026-10-07T13:32:18Z"
TEXT = "Heading\nThe applicant may extend the permit once for a further period.\nFooter line\n"
QUOTE = "The applicant may extend the permit once for a further period."
PORTALS = [{"source_record_id": RID, "verified_at": STAMP}]


def _receipt(text: str, fetched_at: str, file: str | None = None, **extra: Any) -> dict[str, Any]:
    return {
        "source_record_id": RID,
        "http_status": 200,
        "key_phrase_found": True,
        "fetched_at": fetched_at,
        "visible_text_sha256": bl.saved_fingerprint(text),
        "text_file": f"text/{file or SHORT + '.txt'}",
        **extra,
    }


def _ledger(
    root: Path,
    name: str,
    text: str,
    fetched_at: str = STAMP,
    *,
    quote: str | None = None,
    file: str | None = None,
    judged: bool = True,
    judged_at: str = "2026-10-07T13:33:00Z",
    named: bool = False,
) -> Path:
    """A ledger with one read of the record and (when judged) one judgement of it."""
    led = root / name
    (led / "text").mkdir(parents=True, exist_ok=True)
    (led / "text" / (file or f"{SHORT}.txt")).write_text(text, encoding="utf-8")
    with (led / "r-receipts.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(_receipt(text, fetched_at, file)) + "\n")
    if judged:
        row: dict[str, Any] = {"source_record_id": RID, "judged_at": judged_at}
        if quote is not None:
            row["checked_sentence"] = quote
        if named:
            row.update(receipt_fetched_at=fetched_at, text_sha256=bl.saved_fingerprint(text))
        with (led / "r-judgements.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    return led


def _attested(root: Path, **kw: Any) -> dict[str, bl.Attested]:
    return bl.attested_reads(root, PORTALS, **kw)


def _row(attested: bl.Attested, fresh: str = TEXT) -> dict[str, Any] | None:
    return bl.unchanged_judgement(
        RID,
        _receipt(fresh, "2026-10-08T10:11:50Z"),
        fresh,
        attested,
        reader="organ-x",
        judged_at="2026-10-08T10:12:00Z",
    )


def test_saved_fingerprint_is_the_receipt_fingerprint() -> None:
    body = TEXT[:-1]
    assert bl.saved_fingerprint(TEXT) == fingerprint(body)
    token = "A" * 40
    assert bl.saved_fingerprint(f"{body} {token}\n") == fingerprint(f"{body} {token}")


def test_innocence_identical_text_yields_a_none_judgement(tmp_path: Path) -> None:
    _ledger(tmp_path, "base", TEXT, quote=QUOTE)
    held = _attested(tmp_path)[RID]
    row = _row(held)
    assert row is not None
    assert (row["semantic_change"], row["judge"], row["reader"]) == (
        "none",
        "fingerprint",
        "organ-x",
    )
    assert row["text_sha256"] == bl.saved_fingerprint(TEXT)
    assert row["receipt_fetched_at"] == "2026-10-08T10:11:50Z"
    assert row["checked_sentence"] == QUOTE
    assert held.label() == f"base@{STAMP}"


def test_guilt_one_changed_word_is_not_proven_unchanged(tmp_path: Path) -> None:
    _ledger(tmp_path, "base", TEXT)
    assert _row(_attested(tmp_path)[RID], TEXT.replace("once", "twice")) is None


def test_guilt_a_ledger_without_a_read_at_the_pack_stamp_attests_nothing(tmp_path: Path) -> None:
    _ledger(tmp_path, "base", TEXT, "2026-10-07T13:35:00Z")
    assert _attested(tmp_path) == {}


def test_guilt_the_run_own_ledger_is_never_the_baseline(tmp_path: Path) -> None:
    own = _ledger(tmp_path, "own", TEXT)
    assert _attested(tmp_path, exclude=[own]) == {}


def test_guilt_a_read_nobody_judged_attests_nothing_even_if_it_is_the_latest(
    tmp_path: Path,
) -> None:
    """Text A read and judged, text B read later and never judged, pack created after both."""
    led = _ledger(tmp_path, "base", TEXT)
    other = "The applicant may NOT extend the permit any more.\n"
    (led / "text" / f"{SHORT}-later.txt").write_text(other, encoding="utf-8")
    with (led / "r-receipts.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(_receipt(other, "2026-10-07T13:39:00Z", f"{SHORT}-later.txt")) + "\n")
    held = _attested(tmp_path)[RID]
    assert held.receipt["fetched_at"] == STAMP and held.text == TEXT


def test_a_judgement_that_names_its_receipt_binds_to_that_receipt(tmp_path: Path) -> None:
    led = _ledger(tmp_path, "base", TEXT, named=True, judged_at="2026-10-07T13:45:00Z")
    other = "A different later page.\n"
    (led / "text" / f"{SHORT}-later.txt").write_text(other, encoding="utf-8")
    with (led / "r-receipts.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(_receipt(other, "2026-10-07T13:39:00Z", f"{SHORT}-later.txt")) + "\n")
    assert _attested(tmp_path)[RID].text == TEXT


def test_guilt_a_judgement_pinning_another_text_hash_attests_nothing(tmp_path: Path) -> None:
    led = _ledger(tmp_path, "base", TEXT, named=True)
    row = json.loads((led / "r-judgements.jsonl").read_text())
    row["text_sha256"] = "0" * 64
    (led / "r-judgements.jsonl").write_text(json.dumps(row) + "\n")
    assert _attested(tmp_path) == {}


def test_guilt_a_ledger_with_a_read_at_the_stamp_but_no_judgement_attests_nothing(
    tmp_path: Path,
) -> None:
    _ledger(tmp_path, "base", TEXT, judged=False)
    assert _attested(tmp_path) == {}


def test_guilt_two_qualifying_ledgers_make_the_baseline_ambiguous(tmp_path: Path) -> None:
    _ledger(tmp_path, "one", TEXT)
    _ledger(tmp_path, "two", TEXT)
    said: list[str] = []
    assert _attested(tmp_path, log=said.append) == {}
    assert said and "ambiguous baseline" in said[0] and "one" in said[0] and "two" in said[0]
    assert RID in _attested(tmp_path, exclude=[tmp_path / "two"])


def test_the_attested_text_is_the_receipts_own_file_not_the_newest_file(tmp_path: Path) -> None:
    led = _ledger(tmp_path, "base", TEXT)
    (led / "text" / f"{SHORT}-20261009T000000Z.txt").write_text(
        "a newer, unrelated text\n", encoding="utf-8"
    )
    assert _attested(tmp_path)[RID].text == TEXT


def test_guilt_a_saved_text_that_lost_its_fingerprint_is_not_attested(tmp_path: Path) -> None:
    led = _ledger(tmp_path, "base", TEXT)
    (led / "text" / f"{SHORT}.txt").write_text(TEXT + "edited later\n", encoding="utf-8")
    assert _attested(tmp_path) == {}


def test_a_later_ledger_without_a_read_at_the_stamp_does_not_override_the_attesting_one(
    tmp_path: Path,
) -> None:
    _ledger(tmp_path, "a-attesting", "first text\n", STAMP)
    _ledger(tmp_path, "b-stray", TEXT, "2026-10-07T13:36:00Z", judged_at="2026-10-07T13:37:00Z")
    assert _attested(tmp_path)[RID].ledger.name == "a-attesting"


def test_no_sentence_of_forty_characters_leaves_the_record_to_the_judge(tmp_path: Path) -> None:
    short = "Menu\nHome\nContact us.\n"
    assert bl.first_sentence(short) is None
    _ledger(tmp_path, "base", short)
    assert _row(_attested(tmp_path)[RID], short) is None


def test_a_baseline_quote_missing_from_the_fresh_text_falls_back_to_a_real_sentence(
    tmp_path: Path,
) -> None:
    _ledger(tmp_path, "base", TEXT, quote="A sentence that the fresh text does not carry at all.")
    row = _row(_attested(tmp_path)[RID])
    assert row is not None and row["checked_sentence"] == QUOTE


def test_fingerprint_judgements_over_a_ledger(tmp_path: Path) -> None:
    _ledger(tmp_path / "root", "base", TEXT)
    fresh = _ledger(tmp_path / "fresh-parent", "fresh", TEXT, "2026-10-08T10:11:50Z", judged=False)
    held = _attested(tmp_path / "root")
    rows = bl.fingerprint_judgements(
        fresh, [RID], held, reader="organ-x", judged_at="2026-10-08T10:12:00Z"
    )
    assert [r["source_record_id"] for r in rows] == [RID]
    (fresh / "text" / f"{SHORT}.txt").write_text(
        TEXT + "edited after the fetch\n", encoding="utf-8"
    )
    assert (
        bl.fingerprint_judgements(
            fresh, [RID], held, reader="organ-x", judged_at="2026-10-08T10:12:00Z"
        )
        == []
    )
