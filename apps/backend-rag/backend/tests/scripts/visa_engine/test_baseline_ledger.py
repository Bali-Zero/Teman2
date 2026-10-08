"""baseline_ledger — an unchanged page is proven by fingerprint, never by a model's opinion.

Guilt: any difference in the text, a missing baseline, a tampered saved text -> no judgement.
Innocence: the same text -> a `none` judgement the fold accepts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.scripts.visa_engine import baseline_ledger as bl
from backend.scripts.visa_engine.portal_read_receipt import fingerprint

RID = "d" * 36
SHORT = RID[:8]
TEXT = "Heading\nThe applicant may extend the permit once for a further period.\nFooter line\n"


def _ledger(
    root: Path, name: str, text: str, *, file: str | None = None, quote: str | None = None
) -> Path:
    led = root / name
    (led / "text").mkdir(parents=True)
    (led / "text" / (file or f"{SHORT}.txt")).write_text(text, encoding="utf-8")
    if quote is not None:
        row = {
            "source_record_id": RID,
            "checked_sentence": quote,
            "judged_at": "2026-10-07T10:00:00Z",
        }
        (led / "r-judgements.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    return led


def _receipt(text: str, **extra: Any) -> dict[str, Any]:
    return {
        "source_record_id": RID,
        "http_status": 200,
        "key_phrase_found": True,
        "fetched_at": "2026-10-08T10:11:50Z",
        "visible_text_sha256": bl.saved_fingerprint(text),
        "text_file": f"text/{SHORT}.txt",
        **extra,
    }


def _fresh(root: Path, text: str) -> tuple[Path, dict[str, Any]]:
    led = _ledger(root, "fresh", text)
    receipt = _receipt(text)
    (led / "r-receipts.jsonl").write_text(json.dumps(receipt) + "\n", encoding="utf-8")
    return led, receipt


def _row(root: Path, base: Path, fresh: str = TEXT) -> dict[str, Any] | None:
    return bl.unchanged_judgement(
        RID, _receipt(fresh), fresh, base, reader="organ-x", judged_at="2026-10-08T10:12:00Z"
    )


def test_saved_fingerprint_is_the_receipt_fingerprint() -> None:
    body = TEXT[:-1]
    assert bl.saved_fingerprint(TEXT) == fingerprint(body)
    token = "A" * 40
    assert bl.saved_fingerprint(f"{body} {token}\n") == fingerprint(f"{body} {token}")


def test_innocence_identical_text_yields_a_none_judgement(tmp_path: Path) -> None:
    base = _ledger(
        tmp_path,
        "base",
        TEXT,
        quote="The applicant may extend the permit once for a further period.",
    )
    row = _row(tmp_path, base)
    assert row is not None
    assert (row["semantic_change"], row["judge"], row["reader"]) == (
        "none",
        "fingerprint",
        "organ-x",
    )
    assert row["text_sha256"] == bl.saved_fingerprint(TEXT)
    assert row["receipt_fetched_at"] == "2026-10-08T10:11:50Z"
    assert (
        row["checked_sentence"] == "The applicant may extend the permit once for a further period."
    )
    assert row["checked_sentence"] in TEXT


def test_guilt_one_changed_word_is_not_proven_unchanged(tmp_path: Path) -> None:
    base = _ledger(tmp_path, "base", TEXT)
    assert _row(tmp_path, base, TEXT.replace("once", "twice")) is None


def test_guilt_no_baseline_text_for_the_record(tmp_path: Path) -> None:
    base = _ledger(tmp_path, "base", TEXT, file="other000.txt")
    assert _row(tmp_path, base) is None


def test_a_baseline_quote_missing_from_the_fresh_text_falls_back_to_a_real_sentence(
    tmp_path: Path,
) -> None:
    base = _ledger(
        tmp_path, "base", TEXT, quote="A sentence that the fresh text does not carry at all."
    )
    row = _row(tmp_path, base)
    assert row is not None
    assert (
        row["checked_sentence"] == "The applicant may extend the permit once for a further period."
    )


def test_no_sentence_of_forty_characters_leaves_the_record_to_the_judge(tmp_path: Path) -> None:
    short = "Menu\nHome\nContact us.\n"
    assert bl.first_sentence(short) is None
    assert _row(tmp_path, _ledger(tmp_path, "base", short), short) is None


def test_the_newest_timestamped_text_beats_the_plain_one(tmp_path: Path) -> None:
    base = _ledger(tmp_path, "base", "old text\n")
    (base / "text" / f"{SHORT}-20261001T000000Z.txt").write_text("mid text\n", encoding="utf-8")
    (base / "text" / f"{SHORT}-20261007T000000Z.txt").write_text("new text\n", encoding="utf-8")
    assert bl.baseline_text(base, RID) == "new text\n"


def test_a_saved_text_that_lost_its_fingerprint_is_skipped(tmp_path: Path) -> None:
    base = _ledger(tmp_path, "base", TEXT)
    fresh, _ = _fresh(tmp_path, TEXT)
    (fresh / "text" / f"{SHORT}.txt").write_text(
        TEXT + "edited after the fetch\n", encoding="utf-8"
    )
    assert (
        bl.fingerprint_judgements(
            fresh, [RID], base, reader="organ-x", judged_at="2026-10-08T10:12:00Z"
        )
        == []
    )


def test_fingerprint_judgements_over_a_ledger(tmp_path: Path) -> None:
    base = _ledger(tmp_path, "base", TEXT)
    fresh, _ = _fresh(tmp_path, TEXT)
    rows = bl.fingerprint_judgements(
        fresh, [RID], base, reader="organ-x", judged_at="2026-10-08T10:12:00Z"
    )
    assert [r["source_record_id"] for r in rows] == [RID]


def test_newest_covering_ledger_skips_own_unattested_and_incomplete(tmp_path: Path) -> None:
    root = tmp_path / "visa"
    root.mkdir()
    good = _ledger(root, "2026-10-07-restamp", TEXT)
    _ledger(root, "2026-10-12-own", TEXT)
    _ledger(root, "2026-10-11-organ-reattest-seq27", TEXT)
    _ledger(root, "2026-10-09-partial", TEXT, file="other000.txt")
    pick = bl.newest_covering_ledger(
        root,
        [RID],
        exclude=[root / "2026-10-12-own"],
        accept=lambda p: "organ-reattest" not in p.name,
    )
    assert pick == good
    assert bl.newest_covering_ledger(root, [RID, "e" * 36], accept=lambda _p: True) is None
