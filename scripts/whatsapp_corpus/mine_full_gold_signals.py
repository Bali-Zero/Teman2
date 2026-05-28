from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

DEFAULT_FULL_DIR = Path("research/personal/wa-corpus/full")
DEFAULT_INPUT_DB = DEFAULT_FULL_DIR / "full_messages.local.sqlite"
DEFAULT_USABLE_TSV = DEFAULT_FULL_DIR / "usable_after_spicy_quarantine.local.tsv"
DEFAULT_OUTPUT_DB = DEFAULT_FULL_DIR / "full_gold_signals.local.sqlite"
DEFAULT_SUMMARY = DEFAULT_FULL_DIR / "full_gold_signals_summary.md"

EXPECTED_INPUT_DB_NAME = "full_messages.local.sqlite"
EXPECTED_USABLE_TSV_NAME = "usable_after_spicy_quarantine.local.tsv"


@dataclass(frozen=True)
class SignalSpec:
    signal_group: str
    signal_code: str
    patterns: tuple[re.Pattern[str], ...]
    score: int


@dataclass(frozen=True)
class MessageRow:
    file_id: str
    source: str
    source_tag: str | None
    path_hash: str
    message_index: int
    timestamp: str | None
    month: str
    sender_hash: str | None
    body_text: str


@dataclass(frozen=True)
class SignalHit:
    file_id: str
    source: str
    source_tag: str | None
    path_hash: str
    message_index: int
    timestamp: str | None
    month: str
    sender_hash: str | None
    signal_group: str
    signal_code: str
    score: int
    body_hash: str


SIGNALS: tuple[SignalSpec, ...] = (
    SignalSpec(
        "crm_lead_intake",
        "new_lead_or_intake",
        (
            re.compile(r"\b(?:new client|new lead|prospect|inquiry|enquiry|interested)\b", re.I),
            re.compile(r"\b(?:mau tanya|ingin tanya|tertarik|calon klien|klien baru)\b", re.I),
            re.compile(r"\b(?:vorrei|interessato|nuovo cliente|preventivo)\b", re.I),
        ),
        3,
    ),
    SignalSpec(
        "crm_lead_intake",
        "pricing_or_quote",
        (
            re.compile(r"\b(?:price|pricing|quote|quotation|cost|fee|invoice|package)\b", re.I),
            re.compile(r"\b(?:harga|biaya|tagihan|invoice|penawaran)\b", re.I),
            re.compile(r"\b(?:prezzo|costo|preventivo|fattura)\b", re.I),
        ),
        3,
    ),
    SignalSpec(
        "document_ops",
        "identity_document",
        (
            re.compile(r"\b(?:passport|passports|ktp|id card|identity card)\b", re.I),
            re.compile(r"\b(?:paspor|kartu identitas)\b", re.I),
            re.compile(r"\b(?:passaporto|carta d'identit[aà])\b", re.I),
        ),
        4,
    ),
    SignalSpec(
        "document_ops",
        "company_document",
        (
            re.compile(r"\b(?:akta|nib|npwp|ahu|deed|notary|articles of association)\b", re.I),
            re.compile(r"\b(?:company document|business license|oss|kbli)\b", re.I),
        ),
        4,
    ),
    SignalSpec(
        "document_ops",
        "property_document",
        (
            re.compile(r"\b(?:lease|rental agreement|imb|pbg|slf|sertifikat|shm|hgb)\b", re.I),
            re.compile(r"\b(?:villa|property|land certificate|building permit)\b", re.I),
        ),
        3,
    ),
    SignalSpec(
        "immigration_lifecycle",
        "visa_stage",
        (
            re.compile(r"\b(?:visa|kitas|kitap|itas|itap|b211|evoa|voa|stay permit)\b", re.I),
            re.compile(r"\b(?:imigrasi|immigration|permit|extension|extend)\b", re.I),
            re.compile(r"\b(?:permesso|visto|immigrazione)\b", re.I),
        ),
        4,
    ),
    SignalSpec(
        "immigration_lifecycle",
        "appointment_or_biometric",
        (
            re.compile(r"\b(?:appointment|biometric|fingerprint|photo session|interview)\b", re.I),
            re.compile(r"\b(?:jadwal|foto|sidik jari|wawancara)\b", re.I),
        ),
        4,
    ),
    SignalSpec(
        "tax_payment",
        "tax_compliance",
        (
            re.compile(r"\b(?:tax|pph|ppn|spt|efin|djponline|npwp|tax return)\b", re.I),
            re.compile(r"\b(?:pajak|lapor pajak)\b", re.I),
            re.compile(r"\b(?:tasse|fiscale|dichiarazione)\b", re.I),
        ),
        4,
    ),
    SignalSpec(
        "tax_payment",
        "payment_or_transfer",
        (
            re.compile(r"\b(?:payment|paid|transfer|receipt|proof of payment|bank transfer)\b", re.I),
            re.compile(r"\b(?:bayar|pembayaran|bukti bayar|transferan)\b", re.I),
            re.compile(r"\b(?:pagamento|bonifico|ricevuta)\b", re.I),
        ),
        4,
    ),
    SignalSpec(
        "followup_risk",
        "followup_waiting",
        (
            re.compile(r"\b(?:follow[ -]?up|update|status|still waiting|pending)\b", re.I),
            re.compile(r"\b(?:cek|belum|menunggu|nunggu|tunggu|lanjut)\b", re.I),
            re.compile(r"\b(?:aggiornamento|in attesa|ancora)\b", re.I),
        ),
        3,
    ),
    SignalSpec(
        "followup_risk",
        "deadline_or_urgency",
        (
            re.compile(r"\b(?:urgent|asap|deadline|due|today|tomorrow|expired|expire)\b", re.I),
            re.compile(r"\b(?:mendesak|segera|hari ini|besok|terlambat|expired)\b", re.I),
            re.compile(r"\b(?:urgente|scadenza|oggi|domani|scaduto)\b", re.I),
        ),
        5,
    ),
    SignalSpec(
        "operational_risk",
        "problem_or_complaint",
        (
            re.compile(r"\b(?:problem|issue|mistake|error|failed|rejected|complaint|cancel)\b", re.I),
            re.compile(r"\b(?:masalah|kendala|salah|ditolak|komplain|batal)\b", re.I),
            re.compile(r"\b(?:problema|errore|rifiutato|reclamo|annulla)\b", re.I),
        ),
        5,
    ),
    SignalSpec(
        "knowledge_mining",
        "regulatory_or_kbli",
        (
            re.compile(r"\b(?:regulation|law|permit|license|kbli|oss|ministry|regency)\b", re.I),
            re.compile(r"\b(?:peraturan|izin|ijin|kementerian|kabupaten)\b", re.I),
            re.compile(r"\b(?:normativa|legge|licenza|permesso)\b", re.I),
        ),
        3,
    ),
    SignalSpec(
        "relationship_memory",
        "life_event_or_memory",
        (
            re.compile(r"\b(?:birthday|anniversary|wedding|family|home|travel|trip)\b", re.I),
            re.compile(r"\b(?:compleanno|anniversario|famiglia|casa|viaggio)\b", re.I),
            re.compile(r"\b(?:ulang tahun|keluarga|rumah|jalan jalan)\b", re.I),
        ),
        2,
    ),
)


def stable_hash(value: str, length: int = 32) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def month_key(timestamp: str | None) -> str:
    if not timestamp or len(timestamp) < 7:
        return "unknown"
    return timestamp[:7]


def read_usable_file_ids(path: Path) -> set[str]:
    """Read file IDs that survived the spicy quarantine."""
    if path.name != EXPECTED_USABLE_TSV_NAME:
        raise ValueError(f"Refusing unexpected usable TSV: {path.name}")
    if not path.exists():
        raise FileNotFoundError(f"Usable TSV not found: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {row["file_id"] for row in csv.DictReader(handle, delimiter="\t") if row.get("file_id")}


def _connect_readonly(db_path: Path) -> sqlite3.Connection:
    if db_path.name != EXPECTED_INPUT_DB_NAME:
        raise ValueError(f"Refusing unexpected input DB: {db_path.name}")
    if not db_path.exists():
        raise FileNotFoundError(f"Input DB not found: {db_path}")
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def read_messages(*, input_db: Path, usable_file_ids: set[str]) -> list[MessageRow]:
    """Read cleartext usable messages for local signal mining."""
    with _connect_readonly(input_db) as conn:
        rows = conn.execute(
            """
            SELECT file_id, source, source_tag, path_hash, message_index,
                   timestamp, sender_hash, body_text
            FROM parsed_messages
            ORDER BY file_id, message_index
            """
        ).fetchall()
    return [
        MessageRow(
            file_id=str(row["file_id"]),
            source=str(row["source"]),
            source_tag=str(row["source_tag"]) if row["source_tag"] is not None else None,
            path_hash=str(row["path_hash"]),
            message_index=int(row["message_index"]),
            timestamp=str(row["timestamp"]) if row["timestamp"] is not None else None,
            month=month_key(str(row["timestamp"]) if row["timestamp"] is not None else None),
            sender_hash=str(row["sender_hash"]) if row["sender_hash"] is not None else None,
            body_text=str(row["body_text"] or ""),
        )
        for row in rows
        if str(row["file_id"]) in usable_file_ids
    ]


def mine_signals(messages: Iterable[MessageRow]) -> list[SignalHit]:
    """Mine deterministic local business/personal value signals."""
    hits: list[SignalHit] = []
    for message in messages:
        body_hash = stable_hash(message.body_text)
        for spec in SIGNALS:
            if any(pattern.search(message.body_text) for pattern in spec.patterns):
                hits.append(
                    SignalHit(
                        file_id=message.file_id,
                        source=message.source,
                        source_tag=message.source_tag,
                        path_hash=message.path_hash,
                        message_index=message.message_index,
                        timestamp=message.timestamp,
                        month=message.month,
                        sender_hash=message.sender_hash,
                        signal_group=spec.signal_group,
                        signal_code=spec.signal_code,
                        score=spec.score,
                        body_hash=body_hash,
                    )
                )
    return hits


def write_sqlite(
    *,
    output_db: Path,
    input_db: Path,
    usable_tsv: Path,
    messages: list[MessageRow],
    hits: list[SignalHit],
) -> None:
    """Write local signal hits and aggregate tables."""
    output_db.parent.mkdir(parents=True, exist_ok=True)
    if output_db.exists():
        output_db.unlink()
    group_counts = Counter(hit.signal_group for hit in hits)
    signal_counts = Counter(hit.signal_code for hit in hits)
    month_group_counts = Counter((hit.month, hit.signal_group) for hit in hits)
    source_group_counts = Counter((hit.source, hit.signal_group) for hit in hits)
    file_group_counts = Counter((hit.file_id, hit.signal_group) for hit in hits)
    with sqlite3.connect(output_db) as conn:
        conn.executescript(
            """
            CREATE TABLE gold_signal_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at TEXT NOT NULL,
                input_db TEXT NOT NULL,
                usable_tsv TEXT NOT NULL,
                usable_messages INTEGER NOT NULL,
                privacy_mode TEXT NOT NULL
            );

            CREATE TABLE gold_signal_hits (
                file_id TEXT NOT NULL,
                source TEXT NOT NULL,
                source_tag TEXT,
                path_hash TEXT NOT NULL,
                message_index INTEGER NOT NULL,
                timestamp TEXT,
                month TEXT NOT NULL,
                sender_hash TEXT,
                signal_group TEXT NOT NULL,
                signal_code TEXT NOT NULL,
                score INTEGER NOT NULL,
                body_hash TEXT NOT NULL,
                PRIMARY KEY (file_id, message_index, signal_code)
            );

            CREATE TABLE group_totals (
                signal_group TEXT PRIMARY KEY,
                hit_count INTEGER NOT NULL
            );

            CREATE TABLE signal_totals (
                signal_code TEXT PRIMARY KEY,
                hit_count INTEGER NOT NULL
            );

            CREATE TABLE month_group_totals (
                month TEXT NOT NULL,
                signal_group TEXT NOT NULL,
                hit_count INTEGER NOT NULL,
                PRIMARY KEY (month, signal_group)
            );

            CREATE TABLE source_group_totals (
                source TEXT NOT NULL,
                signal_group TEXT NOT NULL,
                hit_count INTEGER NOT NULL,
                PRIMARY KEY (source, signal_group)
            );

            CREATE TABLE file_group_totals (
                file_id TEXT NOT NULL,
                signal_group TEXT NOT NULL,
                hit_count INTEGER NOT NULL,
                PRIMARY KEY (file_id, signal_group)
            );

            CREATE INDEX idx_gold_hits_group ON gold_signal_hits(signal_group, signal_code);
            CREATE INDEX idx_gold_hits_month ON gold_signal_hits(month);
            CREATE INDEX idx_gold_hits_file ON gold_signal_hits(file_id, message_index);
            """
        )
        conn.execute(
            """
            INSERT INTO gold_signal_runs (
                id, generated_at, input_db, usable_tsv, usable_messages, privacy_mode
            )
            VALUES (1, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                input_db.name,
                usable_tsv.name,
                len(messages),
                "local_only_cleartext_read_hashed_signal_outputs",
            ),
        )
        conn.executemany(
            """
            INSERT INTO gold_signal_hits (
                file_id, source, source_tag, path_hash, message_index,
                timestamp, month, sender_hash, signal_group, signal_code,
                score, body_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    hit.file_id,
                    hit.source,
                    hit.source_tag,
                    hit.path_hash,
                    hit.message_index,
                    hit.timestamp,
                    hit.month,
                    hit.sender_hash,
                    hit.signal_group,
                    hit.signal_code,
                    hit.score,
                    hit.body_hash,
                )
                for hit in hits
            ],
        )
        conn.executemany(
            "INSERT INTO group_totals (signal_group, hit_count) VALUES (?, ?)",
            group_counts.items(),
        )
        conn.executemany(
            "INSERT INTO signal_totals (signal_code, hit_count) VALUES (?, ?)",
            signal_counts.items(),
        )
        conn.executemany(
            """
            INSERT INTO month_group_totals (month, signal_group, hit_count)
            VALUES (?, ?, ?)
            """,
            [(month, group, count) for (month, group), count in month_group_counts.items()],
        )
        conn.executemany(
            """
            INSERT INTO source_group_totals (source, signal_group, hit_count)
            VALUES (?, ?, ?)
            """,
            [(source, group, count) for (source, group), count in source_group_counts.items()],
        )
        conn.executemany(
            """
            INSERT INTO file_group_totals (file_id, signal_group, hit_count)
            VALUES (?, ?, ?)
            """,
            [(file_id, group, count) for (file_id, group), count in file_group_counts.items()],
        )
        conn.commit()


def write_summary(
    *,
    summary_path: Path,
    output_db: Path,
    usable_files: int,
    messages: list[MessageRow],
    hits: list[SignalHit],
) -> None:
    """Write tracked aggregate-only gold signal summary."""
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    group_counts = Counter(hit.signal_group for hit in hits)
    signal_counts = Counter(hit.signal_code for hit in hits)
    source_counts = Counter(hit.source for hit in hits)
    month_counts = Counter(hit.month for hit in hits)
    unique_hit_messages = {(hit.file_id, hit.message_index) for hit in hits}
    unique_hit_files = {hit.file_id for hit in hits}

    lines = [
        "# WhatsApp Full Corpus Gold Signals Summary",
        "",
        f"Generated UTC: `{datetime.now(timezone.utc).isoformat(timespec='seconds')}`",
        f"Local signal DB: `{output_db.name}`",
        "",
        "## Privacy Mode",
        "",
        "- This tracked summary contains no raw message text.",
        "- This tracked summary contains no message snippets.",
        "- This tracked summary contains no phone numbers or emails.",
        "- This tracked summary contains no raw source paths or contact names.",
        "- Signal hits reference local file/message IDs and body hashes only.",
        "",
        "## Scope",
        "",
        "- Reads the full cleartext local SQLite after spicy-conversation quarantine.",
        "- Excludes quarantined files from mining.",
        "- Uses deterministic multilingual patterns; no cloud LLM is called.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Usable files | {usable_files} |",
        f"| Usable messages scanned | {len(messages)} |",
        f"| Signal hits | {len(hits)} |",
        f"| Messages with at least one hit | {len(unique_hit_messages)} |",
        f"| Files with at least one hit | {len(unique_hit_files)} |",
        "",
        "## Signal Groups",
        "",
        "| Group | Hits |",
        "|---|---:|",
    ]
    for group, count in group_counts.most_common():
        lines.append(f"| {group} | {count} |")

    lines.extend(["", "## Signal Codes", "", "| Code | Hits |", "|---|---:|"])
    for code, count in signal_counts.most_common():
        lines.append(f"| {code} | {count} |")

    lines.extend(["", "## Sources", "", "| Source | Hits |", "|---|---:|"])
    for source, count in source_counts.most_common():
        lines.append(f"| {source} | {count} |")

    lines.extend(["", "## Top Months", "", "| Month | Hits |", "|---|---:|"])
    for month, count in month_counts.most_common(24):
        lines.append(f"| {month} | {count} |")

    lines.extend(
        [
            "",
            "## Operational Reading",
            "",
            "- The strongest immediate value is CRM/ops retrieval over lead intake, document, payment, visa-stage, and follow-up signals.",
            "- The local DB can drive dashboards, review queues, and local RAG without exposing corpus text.",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def mine_full_gold_signals_to_outputs(
    *,
    input_db: Path,
    usable_tsv: Path,
    output_db: Path,
    summary_path: Path,
) -> tuple[list[MessageRow], list[SignalHit], int]:
    """Mine full-corpus usable messages and write local artifacts."""
    usable_file_ids = read_usable_file_ids(usable_tsv)
    messages = read_messages(input_db=input_db, usable_file_ids=usable_file_ids)
    hits = mine_signals(messages)
    write_sqlite(
        output_db=output_db,
        input_db=input_db,
        usable_tsv=usable_tsv,
        messages=messages,
        hits=hits,
    )
    write_summary(
        summary_path=summary_path,
        output_db=output_db,
        usable_files=len(usable_file_ids),
        messages=messages,
        hits=hits,
    )
    return messages, hits, len(usable_file_ids)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Mine local gold signals from usable full-corpus WhatsApp messages."
    )
    parser.add_argument("--input-db", type=Path, default=DEFAULT_INPUT_DB)
    parser.add_argument("--usable-tsv", type=Path, default=DEFAULT_USABLE_TSV)
    parser.add_argument("--output-db", type=Path, default=DEFAULT_OUTPUT_DB)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        messages, hits, usable_files = mine_full_gold_signals_to_outputs(
            input_db=args.input_db,
            usable_tsv=args.usable_tsv,
            output_db=args.output_db,
            summary_path=args.summary,
        )
    except (FileNotFoundError, ValueError, sqlite3.DatabaseError) as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    if args.json:
        json.dump(
            {
                "usable_files": usable_files,
                "usable_messages": len(messages),
                "signal_hits": len(hits),
                "output_db": str(args.output_db),
                "summary": str(args.summary),
            },
            sys.stdout,
            sort_keys=True,
        )
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
