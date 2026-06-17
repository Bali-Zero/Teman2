from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.whatsapp_corpus.build_owner_decision_intake import (
    ALLOWED_OWNER_DECISIONS,
    DEFAULT_EVENT_ACTOR,
    _format_utc,
)

DEFAULT_OWNER_DECISION_INBOX_DIR = Path(
    "research/personal/wa-corpus/owner-decision-inbox"
)
DEFAULT_OWNER_DECISION_COMPILER_DIR = Path(
    "research/personal/wa-corpus/owner-decision-compiler"
)

DEFAULT_OWNER_INBOX_DB = DEFAULT_OWNER_DECISION_INBOX_DIR / "owner_decision_inbox.local.sqlite"
DEFAULT_EDITED_TEMPLATE_JSONL = (
    DEFAULT_OWNER_DECISION_INBOX_DIR / "owner_decisions_template.local.jsonl"
)
DEFAULT_OUTPUT_DB = (
    DEFAULT_OWNER_DECISION_COMPILER_DIR / "owner_decision_compiler.local.sqlite"
)
DEFAULT_OUTPUT_JSONL = DEFAULT_OWNER_DECISION_COMPILER_DIR / "owner_decisions.local.jsonl"
DEFAULT_SUMMARY = (
    DEFAULT_OWNER_DECISION_COMPILER_DIR / "owner_decision_compiler_summary.md"
)

EXPECTED_OWNER_INBOX_DB_NAME = "owner_decision_inbox.local.sqlite"
EXPECTED_EDITED_TEMPLATE_NAME = "owner_decisions_template.local.jsonl"
TIMESTAMP_OWNER_SUPPLIED = "owner_supplied"
TIMESTAMP_COMPILER_GENERATED = "compiler_generated_at_utc"


@dataclass(frozen=True)
class OwnerInboxRow:
    owner_inbox_item_id: str
    review_item_id: str
    packet_id: str
    entry_id: str
    inbox_rank: int
    assigned_lane: str
    decision_type: str
    review_state: str
    console_bucket: str
    owner_decision_status: str
    allowed_decisions: tuple[str, ...]
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class CompiledOwnerDecision:
    compiler_item_id: str
    review_item_id: str
    packet_id: str
    entry_id: str
    compile_rank: int
    inbox_rank: int
    assigned_lane: str
    decision_type: str
    review_state: str
    console_bucket: str
    owner_decision: str
    decision_note: str
    event_actor: str
    event_recorded_at_utc: str
    timestamp_source: str
    output_payload: dict[str, str]
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class OwnerDecisionCompilerBuildResult:
    source_inbox_item_count: int
    template_row_count: int
    compiled_decision_count: int
    backfilled_timestamp_count: int
    owner_supplied_timestamp_count: int
    send_whatsapp_count: int
    crm_mutation_count: int
    decision_counts: dict[str, int]
    timestamp_source_counts: dict[str, int]
    output_db: Path
    output_jsonl: Path
    summary_path: Path


def _connect_ro(db_path: Path, *, expected_name: str, label: str) -> sqlite3.Connection:
    if db_path.name != expected_name:
        raise ValueError(f"Refusing to read unexpected {label}: {db_path.name}")
    if not db_path.exists():
        raise FileNotFoundError(f"{label} not found: {db_path}")
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _read_jsonl(path: Path) -> tuple[dict[str, object], ...]:
    if path.name != EXPECTED_EDITED_TEMPLATE_NAME:
        raise ValueError(f"Refusing to read unexpected owner decision template: {path.name}")
    if not path.exists():
        raise FileNotFoundError(f"Owner decision template not found: {path}")
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            decoded = json.loads(stripped)
            if not isinstance(decoded, dict):
                raise ValueError(f"Owner decision compiler line {line_number} must be a JSON object")
            rows.append(decoded)
    return tuple(rows)


def read_source_metadata(db_path: Path) -> tuple[str, int]:
    with _connect_ro(
        db_path,
        expected_name=EXPECTED_OWNER_INBOX_DB_NAME,
        label="Owner Decision Inbox DB",
    ) as conn:
        row = conn.execute(
            """
            SELECT generated_at_utc, inbox_item_count
            FROM owner_decision_inbox_runs
            WHERE id = 1
            """
        ).fetchone()
    if row is None:
        return "unknown", 0
    return str(row["generated_at_utc"]), int(row["inbox_item_count"])


def read_owner_inbox_rows(db_path: Path) -> tuple[OwnerInboxRow, ...]:
    with _connect_ro(
        db_path,
        expected_name=EXPECTED_OWNER_INBOX_DB_NAME,
        label="Owner Decision Inbox DB",
    ) as conn:
        rows = conn.execute(
            """
            SELECT owner_inbox_item_id, review_item_id, packet_id, entry_id,
                   inbox_rank, assigned_lane, decision_type, review_state,
                   console_bucket, owner_decision_status, allowed_decisions_json,
                   send_whatsapp, crm_mutation, requires_human_approval
            FROM owner_decision_inbox_items
            ORDER BY inbox_rank, review_item_id
            """
        ).fetchall()
    return tuple(
        OwnerInboxRow(
            owner_inbox_item_id=str(row["owner_inbox_item_id"]),
            review_item_id=str(row["review_item_id"]),
            packet_id=str(row["packet_id"]),
            entry_id=str(row["entry_id"]),
            inbox_rank=int(row["inbox_rank"]),
            assigned_lane=str(row["assigned_lane"]),
            decision_type=str(row["decision_type"]),
            review_state=str(row["review_state"]),
            console_bucket=str(row["console_bucket"]),
            owner_decision_status=str(row["owner_decision_status"]),
            allowed_decisions=tuple(json.loads(str(row["allowed_decisions_json"]))),
            send_whatsapp=bool(row["send_whatsapp"]),
            crm_mutation=bool(row["crm_mutation"]),
            requires_human_approval=bool(row["requires_human_approval"]),
        )
        for row in rows
    )


def _get_required_string(raw: dict[str, object], key: str, *, reference: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Owner decision compiler row {reference} missing {key}")
    return value


def _verify_template_matches_inbox(raw: dict[str, object], inbox_row: OwnerInboxRow) -> None:
    reference = inbox_row.review_item_id
    expected = {
        "assigned_lane": inbox_row.assigned_lane,
        "console_bucket": inbox_row.console_bucket,
        "decision_type": inbox_row.decision_type,
        "entry_id": inbox_row.entry_id,
        "packet_id": inbox_row.packet_id,
        "review_state": inbox_row.review_state,
    }
    for key, expected_value in expected.items():
        actual = raw.get(key)
        if actual != expected_value:
            raise ValueError(
                f"Owner decision compiler row {reference} does not match inbox DB: {key}"
            )


def _timestamp_from_raw(
    raw: dict[str, object],
    *,
    reference: str,
    generated_at_utc: str,
) -> tuple[str, str]:
    raw_timestamp = raw.get("event_recorded_at_utc")
    if raw_timestamp is None or raw_timestamp == "":
        return generated_at_utc, TIMESTAMP_COMPILER_GENERATED
    if not isinstance(raw_timestamp, str):
        raise ValueError(f"Owner decision compiler row {reference} has invalid timestamp")
    return _format_utc(raw_timestamp), TIMESTAMP_OWNER_SUPPLIED


def build_compiled_decisions(
    inbox_rows: Sequence[OwnerInboxRow],
    edited_template_rows: Sequence[dict[str, object]],
    *,
    generated_at_utc: str,
) -> tuple[CompiledOwnerDecision, ...]:
    by_review_item = {row.review_item_id: row for row in inbox_rows}
    if len(edited_template_rows) != len(inbox_rows):
        raise ValueError("Owner decision compiler template must contain every inbox item")

    seen: set[str] = set()
    compiled: list[CompiledOwnerDecision] = []
    for raw in edited_template_rows:
        raw_review_item_id = raw.get("review_item_id")
        if not isinstance(raw_review_item_id, str) or not raw_review_item_id:
            raise ValueError("Owner decision compiler row missing review_item_id")
        if raw_review_item_id in seen:
            raise ValueError(f"Duplicate owner decision compiler row: {raw_review_item_id}")
        seen.add(raw_review_item_id)

        inbox_row = by_review_item.get(raw_review_item_id)
        if inbox_row is None:
            raise ValueError(
                f"Owner decision compiler row references unknown inbox item: {raw_review_item_id}"
            )
        if inbox_row.send_whatsapp or inbox_row.crm_mutation:
            raise ValueError(f"Unsafe inbox item flags on {raw_review_item_id}")
        if not inbox_row.requires_human_approval:
            raise ValueError(f"Inbox item missing human approval gate: {raw_review_item_id}")
        if set(inbox_row.allowed_decisions) != set(ALLOWED_OWNER_DECISIONS):
            raise ValueError(f"Inbox allowed decisions drifted for {raw_review_item_id}")
        _verify_template_matches_inbox(raw, inbox_row)

        owner_decision = raw.get("owner_decision")
        if not isinstance(owner_decision, str) or not owner_decision:
            raise ValueError(f"Owner decision is missing for {raw_review_item_id}")
        if owner_decision not in ALLOWED_OWNER_DECISIONS:
            raise ValueError(
                f"Owner decision is not allowed for {raw_review_item_id}: {owner_decision}"
            )

        event_actor_raw = raw.get("event_actor")
        event_actor = (
            event_actor_raw
            if isinstance(event_actor_raw, str) and event_actor_raw
            else DEFAULT_EVENT_ACTOR
        )
        if event_actor != DEFAULT_EVENT_ACTOR:
            raise ValueError(f"Owner decision compiler row {raw_review_item_id} has invalid actor")
        decision_note_raw = raw.get("decision_note")
        decision_note = (
            decision_note_raw
            if isinstance(decision_note_raw, str) and decision_note_raw
            else ""
        )
        event_recorded_at_utc, timestamp_source = _timestamp_from_raw(
            raw,
            reference=raw_review_item_id,
            generated_at_utc=generated_at_utc,
        )
        output_payload = {
            "decision_note": decision_note,
            "event_actor": event_actor,
            "event_recorded_at_utc": event_recorded_at_utc,
            "owner_decision": owner_decision,
            "review_item_id": raw_review_item_id,
            "timestamp_source": timestamp_source,
        }
        compiled.append(
            CompiledOwnerDecision(
                compiler_item_id=f"owner-decision-compiler-item-{inbox_row.inbox_rank:06d}",
                review_item_id=raw_review_item_id,
                packet_id=inbox_row.packet_id,
                entry_id=inbox_row.entry_id,
                compile_rank=inbox_row.inbox_rank,
                inbox_rank=inbox_row.inbox_rank,
                assigned_lane=inbox_row.assigned_lane,
                decision_type=inbox_row.decision_type,
                review_state=inbox_row.review_state,
                console_bucket=inbox_row.console_bucket,
                owner_decision=owner_decision,
                decision_note=decision_note,
                event_actor=event_actor,
                event_recorded_at_utc=event_recorded_at_utc,
                timestamp_source=timestamp_source,
                output_payload=output_payload,
                send_whatsapp=False,
                crm_mutation=False,
                requires_human_approval=True,
            )
        )
    missing = set(by_review_item) - seen
    if missing:
        raise ValueError("Owner decision compiler template is missing inbox items")
    return tuple(sorted(compiled, key=lambda item: (item.compile_rank, item.review_item_id)))


def _replace_sqlite(temp_db: Path, output_db: Path) -> None:
    output_db.parent.mkdir(parents=True, exist_ok=True)
    if output_db.exists():
        output_db.unlink()
    temp_db.replace(output_db)


def _unlink_file_if_present(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


def _clear_compiler_outputs(*, output_db: Path, output_jsonl: Path, summary_path: Path) -> None:
    for path in (output_db, output_jsonl, summary_path):
        _unlink_file_if_present(path)
        _unlink_file_if_present(path.with_name(f".{path.name}.tmp"))


def write_owner_decision_compiler_sqlite(
    output_db: Path,
    *,
    items: Sequence[CompiledOwnerDecision],
    source_inbox_item_count: int,
    template_row_count: int,
    generated_at_utc: str,
    source_generated_at_utc: str,
) -> None:
    output_db.parent.mkdir(parents=True, exist_ok=True)
    temp_db = output_db.with_name(f".{output_db.name}.tmp")
    if temp_db.exists():
        temp_db.unlink()
    decision_counts = Counter(item.owner_decision for item in items)
    timestamp_counts = Counter(item.timestamp_source for item in items)
    with sqlite3.connect(temp_db) as conn:
        conn.executescript(
            """
            CREATE TABLE owner_decision_compiler_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                source_generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                source_inbox_item_count INTEGER NOT NULL,
                template_row_count INTEGER NOT NULL,
                compiled_decision_count INTEGER NOT NULL,
                backfilled_timestamp_count INTEGER NOT NULL,
                owner_supplied_timestamp_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL CHECK (send_whatsapp_count = 0),
                crm_mutation_count INTEGER NOT NULL CHECK (crm_mutation_count = 0)
            );

            CREATE TABLE owner_decision_compiler_items (
                compiler_item_id TEXT PRIMARY KEY,
                review_item_id TEXT NOT NULL UNIQUE,
                packet_id TEXT NOT NULL,
                entry_id TEXT NOT NULL,
                compile_rank INTEGER NOT NULL,
                inbox_rank INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                review_state TEXT NOT NULL,
                console_bucket TEXT NOT NULL,
                owner_decision TEXT NOT NULL,
                decision_note TEXT NOT NULL,
                event_actor TEXT NOT NULL,
                event_recorded_at_utc TEXT NOT NULL,
                timestamp_source TEXT NOT NULL,
                output_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );

            CREATE INDEX idx_owner_decision_compiler_rank
                ON owner_decision_compiler_items(compile_rank);
            CREATE INDEX idx_owner_decision_compiler_decision
                ON owner_decision_compiler_items(owner_decision);
            CREATE INDEX idx_owner_decision_compiler_timestamp_source
                ON owner_decision_compiler_items(timestamp_source);
            """
        )
        conn.execute(
            """
            INSERT INTO owner_decision_compiler_runs (
                id, generated_at_utc, source_generated_at_utc, privacy_mode,
                source_inbox_item_count, template_row_count,
                compiled_decision_count, backfilled_timestamp_count,
                owner_supplied_timestamp_count, send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
            """,
            (
                generated_at_utc,
                source_generated_at_utc,
                "local_only_owner_decision_compiler_no_raw_text_no_send_no_crm_mutation",
                source_inbox_item_count,
                template_row_count,
                len(items),
                timestamp_counts.get(TIMESTAMP_COMPILER_GENERATED, 0),
                timestamp_counts.get(TIMESTAMP_OWNER_SUPPLIED, 0),
            ),
        )
        conn.executemany(
            """
            INSERT INTO owner_decision_compiler_items (
                compiler_item_id, review_item_id, packet_id, entry_id,
                compile_rank, inbox_rank, assigned_lane, decision_type,
                review_state, console_bucket, owner_decision, decision_note,
                event_actor, event_recorded_at_utc, timestamp_source,
                output_payload_json, send_whatsapp, crm_mutation,
                requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item.compiler_item_id,
                    item.review_item_id,
                    item.packet_id,
                    item.entry_id,
                    item.compile_rank,
                    item.inbox_rank,
                    item.assigned_lane,
                    item.decision_type,
                    item.review_state,
                    item.console_bucket,
                    item.owner_decision,
                    item.decision_note,
                    item.event_actor,
                    item.event_recorded_at_utc,
                    item.timestamp_source,
                    json.dumps(item.output_payload, ensure_ascii=False, sort_keys=True),
                    int(item.send_whatsapp),
                    int(item.crm_mutation),
                    int(item.requires_human_approval),
                )
                for item in items
            ],
        )
        conn.commit()
    _replace_sqlite(temp_db, output_db)
    _ = decision_counts


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(text, encoding="utf-8")
    temp_path.replace(path)


def write_owner_decisions_jsonl(
    output_jsonl: Path,
    items: Sequence[CompiledOwnerDecision],
) -> None:
    _atomic_write_text(
        output_jsonl,
        "".join(
            json.dumps(item.output_payload, ensure_ascii=False, sort_keys=True) + "\n"
            for item in items
        ),
    )


def _counter_table(title: str, counts: Counter[str]) -> list[str]:
    lines = [f"## {title}", "", "| Value | Count |", "|---|---:|"]
    if not counts:
        lines.append("| none | 0 |")
        return lines
    for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| {value or 'unknown'} | {count} |")
    return lines


def write_summary(
    *,
    summary_path: Path,
    items: Sequence[CompiledOwnerDecision],
    source_inbox_item_count: int,
    template_row_count: int,
    generated_at_utc: str,
    source_generated_at_utc: str,
) -> None:
    decision_counts = Counter(item.owner_decision for item in items)
    timestamp_counts = Counter(item.timestamp_source for item in items)
    lane_counts = Counter(item.assigned_lane for item in items)
    lines = [
        "# Zantara Owner Decision Compiler Summary",
        "",
        f"Generated UTC: `{generated_at_utc}`",
        f"Source Owner Decision Inbox UTC: `{source_generated_at_utc}`",
        "",
        "## Privacy Mode",
        "",
        "- This summary contains no raw message text.",
        "- This summary contains no message snippets.",
        "- This summary contains no phone numbers, emails, raw paths, case card IDs, judgment IDs, approval IDs, pack IDs, brief IDs, route IDs, ledger entry IDs, event IDs, work order IDs, packet IDs, review item IDs, or inbox item IDs.",
        "- Owner decision compiler artifacts are local-only and ignored under `research/personal/wa-corpus/`.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Source inbox items | {source_inbox_item_count} |",
        f"| Template rows | {template_row_count} |",
        f"| Compiled decisions | {len(items)} |",
        f"| Backfilled timestamps | {timestamp_counts.get(TIMESTAMP_COMPILER_GENERATED, 0)} |",
        f"| Owner supplied timestamps | {timestamp_counts.get(TIMESTAMP_OWNER_SUPPLIED, 0)} |",
        "| WhatsApp sends | 0 |",
        "| CRM mutations | 0 |",
        "| Human approval required | 100% |",
        "",
        *_counter_table("Owner Decisions", decision_counts),
        "",
        *_counter_table("Timestamp Sources", timestamp_counts),
        "",
        *_counter_table("Assigned Lanes", lane_counts),
        "",
        "## Execution Contract",
        "",
        "- The Owner Decision Compiler binds edited owner template rows to the local inbox DB.",
        "- It imports the downstream intake decision enum instead of redefining it.",
        "- It rejects blank, invalid, duplicate, unknown, or tampered owner decision rows.",
        "- It emits clean `owner_decisions.local.jsonl` for the real Owner Decision Intake.",
        "- It does not parse raw WhatsApp messages.",
        "- It does not call a cloud LLM.",
        "- Runtime must not send WhatsApp messages from this artifact.",
        "- Runtime must not mutate CRM records from this artifact.",
        "- Human approval remains mandatory before any client-facing message or operational mutation.",
    ]
    _atomic_write_text(summary_path, "\n".join(lines) + "\n")


def build_owner_decision_compiler(
    *,
    owner_inbox_db: Path = DEFAULT_OWNER_INBOX_DB,
    edited_template_jsonl: Path = DEFAULT_EDITED_TEMPLATE_JSONL,
    output_dir: Path = DEFAULT_OWNER_DECISION_COMPILER_DIR,
    output_db: Path | None = None,
    output_jsonl: Path | None = None,
    summary_path: Path | None = None,
    generated_at_utc: str | None = None,
) -> OwnerDecisionCompilerBuildResult:
    """Compile edited owner inbox decisions into intake-ready JSONL."""
    output_db = output_db or output_dir / DEFAULT_OUTPUT_DB.name
    output_jsonl = output_jsonl or output_dir / DEFAULT_OUTPUT_JSONL.name
    summary_path = summary_path or output_dir / DEFAULT_SUMMARY.name
    generated = _format_utc(generated_at_utc)
    _clear_compiler_outputs(
        output_db=output_db,
        output_jsonl=output_jsonl,
        summary_path=summary_path,
    )
    try:
        source_generated, source_count = read_source_metadata(owner_inbox_db)
        inbox_rows = read_owner_inbox_rows(owner_inbox_db)
        template_rows = _read_jsonl(edited_template_jsonl)
        source_total = source_count or len(inbox_rows)
        compiled = build_compiled_decisions(
            inbox_rows,
            template_rows,
            generated_at_utc=generated,
        )

        write_owner_decision_compiler_sqlite(
            output_db,
            items=compiled,
            source_inbox_item_count=source_total,
            template_row_count=len(template_rows),
            generated_at_utc=generated,
            source_generated_at_utc=source_generated,
        )
        write_owner_decisions_jsonl(output_jsonl, compiled)
        write_summary(
            summary_path=summary_path,
            items=compiled,
            source_inbox_item_count=source_total,
            template_row_count=len(template_rows),
            generated_at_utc=generated,
            source_generated_at_utc=source_generated,
        )
    except Exception:
        _clear_compiler_outputs(
            output_db=output_db,
            output_jsonl=output_jsonl,
            summary_path=summary_path,
        )
        raise

    timestamp_counts = Counter(item.timestamp_source for item in compiled)
    return OwnerDecisionCompilerBuildResult(
        source_inbox_item_count=source_total,
        template_row_count=len(template_rows),
        compiled_decision_count=len(compiled),
        backfilled_timestamp_count=timestamp_counts.get(TIMESTAMP_COMPILER_GENERATED, 0),
        owner_supplied_timestamp_count=timestamp_counts.get(TIMESTAMP_OWNER_SUPPLIED, 0),
        send_whatsapp_count=sum(1 for item in compiled if item.send_whatsapp),
        crm_mutation_count=sum(1 for item in compiled if item.crm_mutation),
        decision_counts=dict(Counter(item.owner_decision for item in compiled)),
        timestamp_source_counts=dict(timestamp_counts),
        output_db=output_db,
        output_jsonl=output_jsonl,
        summary_path=summary_path,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compile edited local owner decision inbox rows into intake-ready JSONL."
    )
    parser.add_argument("--owner-inbox-db", type=Path, default=DEFAULT_OWNER_INBOX_DB)
    parser.add_argument(
        "--edited-template-jsonl",
        type=Path,
        default=DEFAULT_EDITED_TEMPLATE_JSONL,
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OWNER_DECISION_COMPILER_DIR)
    parser.add_argument("--output-db", type=Path, default=None)
    parser.add_argument("--output-jsonl", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=None)
    parser.add_argument("--generated-at-utc", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        result = build_owner_decision_compiler(
            owner_inbox_db=args.owner_inbox_db,
            edited_template_jsonl=args.edited_template_jsonl,
            output_dir=args.output_dir,
            output_db=args.output_db,
            output_jsonl=args.output_jsonl,
            summary_path=args.summary,
            generated_at_utc=args.generated_at_utc,
        )
    except (FileNotFoundError, ValueError, TypeError, json.JSONDecodeError):
        print("ERROR: Owner decision compiler input is missing or invalid.", file=sys.stderr)
        return 1
    except (sqlite3.Error, OSError):
        print("ERROR: Owner decision compiler run failed safely.", file=sys.stderr)
        return 1
    except Exception:
        print("ERROR: Owner decision compiler run failed safely.", file=sys.stderr)
        return 1
    if args.json:
        print(
            json.dumps(
                {
                    "backfilled_timestamp_count": result.backfilled_timestamp_count,
                    "compiled_decision_count": result.compiled_decision_count,
                    "crm_mutation_count": result.crm_mutation_count,
                    "owner_supplied_timestamp_count": result.owner_supplied_timestamp_count,
                    "send_whatsapp_count": result.send_whatsapp_count,
                    "source_inbox_item_count": result.source_inbox_item_count,
                    "template_row_count": result.template_row_count,
                },
                sort_keys=True,
            )
        )
    else:
        print(
            "Owner decision compiler complete: "
            f"{result.compiled_decision_count} decisions -> {result.output_jsonl.name}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
