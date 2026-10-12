"""baseline_ledger.py — the attested read of a page as the yardstick for "did the page change?".

The weekly organ asks a Claude judge whether a page still says what the pack assumes. A judge
can call a byte-identical page "changed" (it did, on the first real run). The visible-text
fingerprint settles that without a model: when a fresh receipt carries the SAME fingerprint
as the ATTESTED read of that record, the page did not change and the organ writes the ``none``
judgement itself (``judge: "fingerprint"``). The attested read is not a directory someone names: it
is proven. A ledger under the baseline root attests the anchor pack when a record has in it a
successful receipt dated exactly at one of the pack's portal ``verified_at`` stamps and a judgement
(the fold stamps the earliest successful read of the ledger it consumed); two such ledgers make the
baseline ambiguous and attest nothing. The attested read of a record is the receipt bound by that
record's latest judgement, whose own saved text carries the fingerprint the receipt recorded. The run's own ledger is excluded by path. The fold resolves the
same reads, re-proves every fingerprint judgement against them, and downgrades a ``changed`` verdict
on an unchanged fingerprint to ``none``, listing it as a baseline disagreement.

Stdlib plus ``portal_read_receipt.fingerprint`` and ``ledger_paths`` only; must import under the
system python3 that cron runs the organ with (3.9), so no runtime ``X | Y`` unions.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
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


@dataclass(frozen=True)
class Attested:
    ledger: Path
    receipt: dict[str, Any]
    text: str

    @property
    def fingerprint(self) -> str:
        return str(self.receipt["visible_text_sha256"])

    def label(self) -> str:
        return f"{self.ledger.name}@{self.receipt['fetched_at']}"


def _instant(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).astimezone(
        timezone.utc
    )


def first_sentence(text: str) -> str | None:
    """First complete sentence (ends . ! ?) of at least MIN_SENTENCE_CHARS, within one line."""
    for line in text.splitlines():
        for part in _SENTENCE_SPLIT.split(line.strip()):
            if len(part) >= MIN_SENTENCE_CHARS and part[-1] in ".!?":
                return part
    return None


def checked_sentence(ledger_dir: Path, record_id: str, fresh_text: str) -> str | None:
    """The attested ledger's own quote if the fresh text carries it, else the first sentence."""
    quotes = sorted(
        (
            row
            for row in _rows(ledger_dir, "*-judgements.jsonl")
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


def is_success(receipt: dict[str, Any]) -> bool:
    return (
        receipt.get("http_status") == 200
        and receipt.get("key_phrase_found") is True
        and _instant(receipt.get("fetched_at")) is not None
    )


def latest_success(receipts: Iterable[dict[str, Any]], record_id: str) -> dict[str, Any] | None:
    ok = [r for r in receipts if r.get("source_record_id") == record_id and is_success(r)]
    return max(ok, key=lambda r: _instant(r["fetched_at"])) if ok else None  # type: ignore[arg-type,return-value]


def _own_text(ledger_dir: Path, receipt: dict[str, Any]) -> str | None:
    """THE receipt's saved text (its own text_file), if it carries the fingerprint it recorded."""
    try:
        saved = read_receipt_text(ledger_dir / "text", receipt)
    except LedgerPathError:
        return None
    if saved is None or saved_fingerprint(saved) != receipt.get("visible_text_sha256"):
        return None
    return saved


def judged_read(
    successes: list[dict[str, Any]], judgement: dict[str, Any]
) -> dict[str, Any] | None:
    """The receipt a judgement read, resolved as the fold resolves it.

    A judgement that names ``receipt_fetched_at`` / ``text_sha256`` must match that receipt. An old
    judgement that names neither binds to the latest success with ``fetched_at <= judged_at``.
    """
    judged_at = _instant(judgement.get("judged_at"))
    if judged_at is None:
        return None
    named = judgement.get("receipt_fetched_at")
    if named is not None:
        hits = [r for r in successes if r["fetched_at"] == named]
        bound = hits[0] if hits else None
    else:
        eligible = [r for r in successes if _instant(r["fetched_at"]) <= judged_at]  # type: ignore[operator]
        bound = max(eligible, key=lambda r: _instant(r["fetched_at"])) if eligible else None  # type: ignore[arg-type,return-value]
    if bound is None:
        return None
    pinned = judgement.get("text_sha256")
    if pinned is not None and pinned != bound.get("visible_text_sha256"):
        return None
    return bound


def attested_reads(
    root: Path,
    portals: Iterable[dict[str, Any]],
    *,
    exclude: Iterable[Path] = (),
    log: Callable[[str], None] = lambda _m: None,
) -> dict[str, Attested]:
    """record id -> the read the anchor pack attests, proven from the ledgers under ``root``.

    ``portals`` are the anchor's OFFICIAL_PORTAL records (``source_record_id``, ``verified_at``).
    A ledger qualifies only when a record has in it a successful receipt dated EXACTLY at a portal
    stamp of the pack AND a judgement. When more than one ledger qualifies the baseline is ambiguous:
    nothing is attested (ledgers are never combined). The attested read of a record is the receipt
    bound by that record's latest judgement in the qualifying ledger, whose own saved text re-hashes
    to the fingerprint; a read nobody judged attests nothing. A record without one is absent: it goes
    to the judge.
    """
    records = list(portals)
    stamps = {_instant(p.get("verified_at")) for p in records} - {None}
    skip = {p.resolve() for p in exclude}
    if not stamps or not root.is_dir():
        return {}
    qualifying: list[tuple[Path, list[dict[str, Any]], list[dict[str, Any]]]] = []
    for ledger in sorted(p for p in root.iterdir() if p.is_dir()):
        if ledger.resolve() in skip:
            continue
        successes = [r for r in _rows(ledger, "*-receipts.jsonl") if is_success(r)]
        judgements = _rows(ledger, "*-judgements.jsonl")
        judged = {j.get("source_record_id") for j in judgements}
        if any(
            _instant(r["fetched_at"]) in stamps and r.get("source_record_id") in judged
            for r in successes
        ):
            qualifying.append((ledger, successes, judgements))
    if len(qualifying) > 1:
        log(
            "ambiguous baseline: "
            + ", ".join(q[0].name for q in qualifying)
            + " all attest the pack"
        )
        return {}
    chosen: dict[str, Attested] = {}
    for ledger, successes, judgements in qualifying:
        for record in records:
            rid = record["source_record_id"]
            mine = [
                j
                for j in judgements
                if j.get("source_record_id") == rid and _instant(j.get("judged_at"))
            ]
            if not mine:
                continue
            judgement = max(mine, key=lambda j: _instant(j["judged_at"]))  # type: ignore[arg-type,return-value]
            receipt = judged_read(
                [r for r in successes if r.get("source_record_id") == rid], judgement
            )
            text = _own_text(ledger, receipt) if receipt else None
            if receipt is not None and text is not None:
                chosen[rid] = Attested(ledger, receipt, text)
    return chosen


def unchanged_judgement(
    record_id: str,
    receipt: dict[str, Any],
    fresh_text: str,
    attested: Attested,
    *,
    reader: str,
    judged_at: str,
) -> dict[str, Any] | None:
    """The ``none`` judgement for a record whose fresh text is the attested text, else None."""
    if attested.fingerprint != receipt.get("visible_text_sha256"):
        return None
    sentence = checked_sentence(attested.ledger, record_id, fresh_text)
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
        "page_states": "visible text is byte-identical to the attested read",
        "pack_assumes": {},
        "semantic_change": "none",
        "notes": f"fingerprint {attested.fingerprint} equals attested read {attested.label()}; no model consulted",
    }


def fingerprint_judgements(
    ledger_dir: Path,
    record_ids: Iterable[str],
    attested: dict[str, Attested],
    *,
    reader: str,
    judged_at: str,
) -> list[dict[str, Any]]:
    """Judgement rows for every record whose fresh read is fingerprint-identical to its attested read."""
    receipts = _rows(ledger_dir, "*-receipts.jsonl")
    out: list[dict[str, Any]] = []
    for record_id in record_ids:
        held = attested.get(record_id)
        receipt = latest_success(receipts, record_id)
        fresh = _own_text(ledger_dir, receipt) if receipt else None
        if held is None or receipt is None or fresh is None:
            continue
        row = unchanged_judgement(
            record_id, receipt, fresh, held, reader=reader, judged_at=judged_at
        )
        if row is not None:
            out.append(row)
    return out
