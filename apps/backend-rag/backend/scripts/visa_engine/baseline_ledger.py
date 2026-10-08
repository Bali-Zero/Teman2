"""baseline_ledger.py — an earlier, attested ledger as the yardstick for "did the page change?".

The weekly organ asks a Claude judge whether a page still says what the pack assumes. A judge
can call a byte-identical page "changed" (it did, on the first real run). The visible-text
fingerprint settles that without a model: when a fresh receipt carries the SAME fingerprint
as the text attested in a baseline ledger, the page did not change and the organ writes the
``none`` judgement itself (``judge: "fingerprint"``). The fold uses the same baseline to refuse
the opposite contradiction: a ``changed`` verdict on a text whose fingerprint equals the baseline.

Stdlib plus ``portal_read_receipt.fingerprint`` and ``ledger_paths`` only; must import under the
system python3 that cron runs the organ with (3.9), so no runtime ``X | Y`` unions.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from backend.scripts.visa_engine.ledger_paths import LedgerPathError, read_receipt_text
from backend.scripts.visa_engine.portal_read_receipt import fingerprint

JUDGE_LABEL = "fingerprint"
MIN_SENTENCE_CHARS = 40
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def saved_fingerprint(saved: str) -> str:
    """Fingerprint of a saved text file: the file is the visible text plus one newline."""
    return fingerprint(saved[:-1] if saved.endswith("\n") else saved)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _rows(ledger_dir: Path, pattern: str) -> list[dict[str, Any]]:
    return [row for path in sorted(ledger_dir.glob(pattern)) for row in _read_jsonl(path)]


def baseline_text(baseline_dir: Path, record_id: str) -> str | None:
    """Newest saved text of a record: ``text/<8id>-<ts>.txt`` beats the plain ``text/<8id>.txt``."""
    text_dir = baseline_dir / "text"
    if not text_dir.is_dir():
        return None
    short = record_id[:8]
    plain = f"{short}.txt"
    found = [
        p
        for p in text_dir.iterdir()
        if p.is_file()
        and p.resolve().parent == text_dir.resolve()
        and (p.name == plain or (p.name.startswith(f"{short}-") and p.suffix == ".txt"))
    ]
    if not found:
        return None
    return max(found, key=lambda p: (p.name != plain, p.name)).read_text(encoding="utf-8")


def baseline_fingerprint(baseline_dir: Path, record_id: str) -> str | None:
    saved = baseline_text(baseline_dir, record_id)
    return None if saved is None else saved_fingerprint(saved)


def first_sentence(text: str) -> str | None:
    """First complete sentence (ends . ! ?) of at least MIN_SENTENCE_CHARS, within one line."""
    for line in text.splitlines():
        for part in _SENTENCE_SPLIT.split(line.strip()):
            if len(part) >= MIN_SENTENCE_CHARS and part[-1] in ".!?":
                return part
    return None


def checked_sentence(baseline_dir: Path, record_id: str, fresh_text: str) -> str | None:
    """A baseline judgement's own quote if the fresh text carries it, else the first sentence."""
    quotes = sorted(
        (
            row
            for row in _rows(baseline_dir, "*-judgements.jsonl")
            if row.get("source_record_id") == record_id
            and isinstance(row.get("checked_sentence"), str)
            and row["checked_sentence"].strip()
        ),
        key=lambda r: str(r.get("judged_at")),
        reverse=True,
    )
    for row in quotes:
        if row["checked_sentence"] in fresh_text:
            return str(row["checked_sentence"])
    return first_sentence(fresh_text)


def latest_success(receipts: Iterable[dict[str, Any]], record_id: str) -> dict[str, Any] | None:
    ok = [
        r
        for r in receipts
        if r.get("source_record_id") == record_id
        and r.get("http_status") == 200
        and r.get("key_phrase_found") is True
        and isinstance(r.get("fetched_at"), str)
    ]
    return max(ok, key=lambda r: r["fetched_at"]) if ok else None


def _own_text(ledger_dir: Path, receipt: dict[str, Any]) -> str | None:
    """The receipt's saved text if it carries the fingerprint the receipt recorded."""
    try:
        saved = read_receipt_text(ledger_dir / "text", receipt)
    except LedgerPathError:
        return None
    if saved is None or saved_fingerprint(saved) != receipt.get("visible_text_sha256"):
        return None
    return saved


def unchanged_judgement(
    record_id: str,
    receipt: dict[str, Any],
    fresh_text: str,
    baseline_dir: Path,
    *,
    reader: str,
    judged_at: str,
) -> dict[str, Any] | None:
    """The ``none`` judgement for a record whose fresh text is the baseline text, else None."""
    base_fp = baseline_fingerprint(baseline_dir, record_id)
    if base_fp is None or base_fp != receipt.get("visible_text_sha256"):
        return None
    sentence = checked_sentence(baseline_dir, record_id, fresh_text)
    if sentence is None or sentence not in fresh_text:
        return None
    return {
        "source_record_id": record_id,
        "reader": reader,
        "judge": JUDGE_LABEL,
        "judged_at": judged_at,
        "http_status": receipt["http_status"],
        "key_phrase_found": receipt["key_phrase_found"],
        "receipt_fetched_at": receipt["fetched_at"],
        "text_sha256": receipt["visible_text_sha256"],
        "checked_sentence": sentence,
        "page_states": "visible text is byte-identical to the baseline ledger's attested text",
        "pack_assumes": {},
        "semantic_change": "none",
        "notes": f"fingerprint {base_fp} equals baseline {baseline_dir.name}; no model consulted",
    }


def fingerprint_judgements(
    ledger_dir: Path,
    record_ids: Iterable[str],
    baseline_dir: Path,
    *,
    reader: str,
    judged_at: str,
) -> list[dict[str, Any]]:
    """Judgement rows for every record whose fresh read is fingerprint-identical to the baseline."""
    receipts = _rows(ledger_dir, "*-receipts.jsonl")
    out: list[dict[str, Any]] = []
    for record_id in record_ids:
        receipt = latest_success(receipts, record_id)
        fresh = _own_text(ledger_dir, receipt) if receipt else None
        if receipt is None or fresh is None:
            continue
        row = unchanged_judgement(
            record_id, receipt, fresh, baseline_dir, reader=reader, judged_at=judged_at
        )
        if row is not None:
            out.append(row)
    return out


def newest_covering_ledger(
    visa_root: Path,
    record_ids: Iterable[str],
    *,
    exclude: Iterable[Path] = (),
    accept: Callable[[Path], bool] = lambda _p: True,
) -> Path | None:
    """Newest (by directory name) ledger under ``visa_root`` holding a text for EVERY record."""
    wanted = [rid[:8] for rid in record_ids]
    skip = {p.resolve() for p in exclude}
    if not wanted or not visa_root.is_dir():
        return None
    for candidate in sorted((p for p in visa_root.iterdir() if p.is_dir()), reverse=True):
        if candidate.resolve() in skip or not accept(candidate):
            continue
        if all(baseline_text(candidate, rid) is not None for rid in wanted):
            return candidate
    return None
