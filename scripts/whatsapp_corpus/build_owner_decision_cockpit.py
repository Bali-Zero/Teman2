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
DEFAULT_OWNER_DECISION_COCKPIT_DIR = Path(
    "research/personal/wa-corpus/owner-decision-cockpit"
)

DEFAULT_OWNER_INBOX_DB = DEFAULT_OWNER_DECISION_INBOX_DIR / "owner_decision_inbox.local.sqlite"
DEFAULT_OUTPUT_DB = (
    DEFAULT_OWNER_DECISION_COCKPIT_DIR / "owner_decision_cockpit.local.sqlite"
)
DEFAULT_OUTPUT_TEMPLATE = (
    DEFAULT_OWNER_DECISION_COCKPIT_DIR / "owner_decisions_template.local.jsonl"
)
DEFAULT_SUMMARY = (
    DEFAULT_OWNER_DECISION_COCKPIT_DIR / "owner_decision_cockpit_summary.md"
)

EXPECTED_OWNER_INBOX_DB_NAME = "owner_decision_inbox.local.sqlite"
COCKPIT_READY_FOR_COMPILE = "ready_for_compile"
COCKPIT_AWAITING_OWNER_INPUT = "awaiting_owner_input"


@dataclass(frozen=True)
class OwnerDecisionInboxRow:
    owner_inbox_item_id: str
    review_item_id: str
    packet_id: str
    entry_id: str
    inbox_rank: int
    assigned_lane: str
    decision_type: str
    review_state: str
    console_bucket: str
    allowed_decisions: tuple[str, ...]
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class OwnerDecisionInput:
    review_item_id: str
    owner_decision: str
    decision_note: str
    event_actor: str
    event_recorded_at_utc: str


@dataclass(frozen=True)
class OwnerDecisionCockpitItem:
    cockpit_item_id: str
    review_item_id: str
    packet_id: str
    entry_id: str
    cockpit_rank: int
    inbox_rank: int
    assigned_lane: str
    decision_type: str
    review_state: str
    console_bucket: str
    owner_decision: str
    decision_note: str
    event_actor: str
    event_recorded_at_utc: str
    cockpit_status: str
    template_record: dict[str, object]
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class OwnerDecisionCockpitBuildResult:
    inbox_item_count: int
    captured_decision_count: int
    awaiting_owner_input_count: int
    send_whatsapp_count: int
    crm_mutation_count: int
    status_counts: dict[str, int]
    decision_counts: dict[str, int]
    output_db: Path
    output_template: Path
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
        raise ValueError("Owner Decision Inbox DB missing run metadata")
    return str(row["generated_at_utc"]), int(row["inbox_item_count"])


def read_owner_inbox_rows(db_path: Path) -> tuple[OwnerDecisionInboxRow, ...]:
    with _connect_ro(
        db_path,
        expected_name=EXPECTED_OWNER_INBOX_DB_NAME,
        label="Owner Decision Inbox DB",
    ) as conn:
        rows = conn.execute(
            """
            SELECT owner_inbox_item_id, review_item_id, packet_id, entry_id,
                   inbox_rank, assigned_lane, decision_type, review_state,
                   console_bucket, allowed_decisions_json, send_whatsapp,
                   crm_mutation, requires_human_approval
            FROM owner_decision_inbox_items
            ORDER BY inbox_rank, review_item_id
            """
        ).fetchall()

    inbox_rows: list[OwnerDecisionInboxRow] = []
    for row in rows:
        allowed_raw = json.loads(str(row["allowed_decisions_json"]))
        if not isinstance(allowed_raw, list) or not all(
            isinstance(item, str) for item in allowed_raw
        ):
            raise ValueError(f"Invalid allowed decisions on {row['review_item_id']}")
        allowed = tuple(allowed_raw)
        if set(allowed) != set(ALLOWED_OWNER_DECISIONS):
            raise ValueError(f"Owner cockpit allowed decisions drifted for {row['review_item_id']}")
        if bool(row["send_whatsapp"]) or bool(row["crm_mutation"]):
            raise ValueError(f"Unsafe owner inbox item flags on {row['review_item_id']}")
        if not bool(row["requires_human_approval"]):
            raise ValueError(f"Owner inbox item missing human approval gate: {row['review_item_id']}")
        inbox_rows.append(
            OwnerDecisionInboxRow(
                owner_inbox_item_id=str(row["owner_inbox_item_id"]),
                review_item_id=str(row["review_item_id"]),
                packet_id=str(row["packet_id"]),
                entry_id=str(row["entry_id"]),
                inbox_rank=int(row["inbox_rank"]),
                assigned_lane=str(row["assigned_lane"]),
                decision_type=str(row["decision_type"]),
                review_state=str(row["review_state"]),
                console_bucket=str(row["console_bucket"]),
                allowed_decisions=allowed,
                send_whatsapp=False,
                crm_mutation=False,
                requires_human_approval=True,
            )
        )
    return tuple(inbox_rows)


def _read_jsonl(path: Path) -> tuple[dict[str, object], ...]:
    if not path.exists():
        raise FileNotFoundError(f"Owner cockpit input JSONL not found: {path}")
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            decoded = json.loads(stripped)
            if not isinstance(decoded, dict):
                raise ValueError(f"Owner cockpit input line {line_number} must be a JSON object")
            rows.append(decoded)
    return tuple(rows)


def _parse_assignment(raw: str, *, label: str) -> tuple[str, str]:
    if "=" not in raw:
        raise ValueError(f"{label} must use review_item_id=value")
    key, value = raw.split("=", 1)
    key = key.strip()
    if not key:
        raise ValueError(f"{label} missing review_item_id")
    return key, value.strip()


def _inline_input_rows(
    *,
    decisions: Sequence[str],
    decision_notes: Sequence[str],
    event_recorded_at_utc: Sequence[str],
) -> tuple[dict[str, object], ...]:
    rows_by_review_item: dict[str, dict[str, object]] = {}
    for raw in decisions:
        review_item_id, owner_decision = _parse_assignment(raw, label="--decision")
        if review_item_id in rows_by_review_item:
            raise ValueError(f"Duplicate owner cockpit decision: {review_item_id}")
        rows_by_review_item[review_item_id] = {
            "owner_decision": owner_decision,
            "review_item_id": review_item_id,
        }
    for raw in decision_notes:
        review_item_id, decision_note = _parse_assignment(raw, label="--decision-note")
        if review_item_id not in rows_by_review_item:
            raise ValueError(f"--decision-note references missing decision: {review_item_id}")
        rows_by_review_item[review_item_id]["decision_note"] = decision_note
    for raw in event_recorded_at_utc:
        review_item_id, timestamp = _parse_assignment(raw, label="--event-recorded-at-utc")
        if review_item_id not in rows_by_review_item:
            raise ValueError(
                f"--event-recorded-at-utc references missing decision: {review_item_id}"
            )
        rows_by_review_item[review_item_id]["event_recorded_at_utc"] = timestamp
    return tuple(rows_by_review_item.values())


def _owner_inputs_by_review_item(
    rows: Sequence[dict[str, object]],
    *,
    generated_at_utc: str,
) -> dict[str, OwnerDecisionInput]:
    inputs: dict[str, OwnerDecisionInput] = {}
    for raw in rows:
        review_item_id_raw = raw.get("review_item_id")
        if not isinstance(review_item_id_raw, str) or not review_item_id_raw:
            raise ValueError("Owner cockpit input missing review_item_id")
        if review_item_id_raw in inputs:
            raise ValueError(f"Duplicate owner cockpit decision: {review_item_id_raw}")

        owner_decision_raw = raw.get("owner_decision")
        if not isinstance(owner_decision_raw, str) or not owner_decision_raw:
            raise ValueError(f"Owner cockpit decision is missing for {review_item_id_raw}")
        if owner_decision_raw not in ALLOWED_OWNER_DECISIONS:
            raise ValueError(
                f"Owner cockpit decision is not allowed for {review_item_id_raw}: "
                f"{owner_decision_raw}"
            )

        event_actor_raw = raw.get("event_actor")
        event_actor = (
            event_actor_raw
            if isinstance(event_actor_raw, str) and event_actor_raw
            else DEFAULT_EVENT_ACTOR
        )
        if event_actor != DEFAULT_EVENT_ACTOR:
            raise ValueError(f"Owner cockpit decision {review_item_id_raw} has invalid actor")

        decision_note_raw = raw.get("decision_note")
        decision_note = (
            decision_note_raw
            if isinstance(decision_note_raw, str) and decision_note_raw
            else ""
        )
        timestamp_raw = raw.get("event_recorded_at_utc")
        if isinstance(timestamp_raw, str) and timestamp_raw:
            event_recorded_at_utc = _format_utc(timestamp_raw)
        else:
            event_recorded_at_utc = ""

        inputs[review_item_id_raw] = OwnerDecisionInput(
            review_item_id=review_item_id_raw,
            owner_decision=owner_decision_raw,
            decision_note=decision_note,
            event_actor=event_actor,
            event_recorded_at_utc=event_recorded_at_utc,
        )
    _ = generated_at_utc
    return inputs


def build_cockpit_items(
    inbox_rows: Sequence[OwnerDecisionInboxRow],
    owner_inputs: dict[str, OwnerDecisionInput],
) -> tuple[OwnerDecisionCockpitItem, ...]:
    by_review_item = {row.review_item_id: row for row in inbox_rows}
    unknown = set(owner_inputs) - set(by_review_item)
    if unknown:
        first = sorted(unknown)[0]
        raise ValueError(f"Owner cockpit input references unknown inbox item: {first}")

    items: list[OwnerDecisionCockpitItem] = []
    for cockpit_rank, inbox_row in enumerate(inbox_rows, start=1):
        owner_input = owner_inputs.get(inbox_row.review_item_id)
        owner_decision = owner_input.owner_decision if owner_input else ""
        decision_note = owner_input.decision_note if owner_input else ""
        event_recorded_at_utc = owner_input.event_recorded_at_utc if owner_input else ""
        cockpit_status = (
            COCKPIT_READY_FOR_COMPILE if owner_input else COCKPIT_AWAITING_OWNER_INPUT
        )
        template_record = {
            "allowed_decisions": list(inbox_row.allowed_decisions),
            "assigned_lane": inbox_row.assigned_lane,
            "console_bucket": inbox_row.console_bucket,
            "decision_note": decision_note,
            "decision_type": inbox_row.decision_type,
            "entry_id": inbox_row.entry_id,
            "event_actor": DEFAULT_EVENT_ACTOR,
            "event_recorded_at_utc": event_recorded_at_utc,
            "owner_decision": owner_decision,
            "packet_id": inbox_row.packet_id,
            "review_item_id": inbox_row.review_item_id,
            "review_state": inbox_row.review_state,
        }
        items.append(
            OwnerDecisionCockpitItem(
                cockpit_item_id=f"owner-decision-cockpit-item-{inbox_row.inbox_rank:06d}",
                review_item_id=inbox_row.review_item_id,
                packet_id=inbox_row.packet_id,
                entry_id=inbox_row.entry_id,
                cockpit_rank=cockpit_rank,
                inbox_rank=inbox_row.inbox_rank,
                assigned_lane=inbox_row.assigned_lane,
                decision_type=inbox_row.decision_type,
                review_state=inbox_row.review_state,
                console_bucket=inbox_row.console_bucket,
                owner_decision=owner_decision,
                decision_note=decision_note,
                event_actor=DEFAULT_EVENT_ACTOR,
                event_recorded_at_utc=event_recorded_at_utc,
                cockpit_status=cockpit_status,
                template_record=template_record,
                send_whatsapp=False,
                crm_mutation=False,
                requires_human_approval=True,
            )
        )
    return tuple(items)


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


def _clear_cockpit_outputs(*, output_db: Path, output_template: Path, summary_path: Path) -> None:
    for path in (output_db, output_template, summary_path):
        _unlink_file_if_present(path)
        _unlink_file_if_present(path.with_name(f".{path.name}.tmp"))


def write_owner_decision_cockpit_sqlite(
    output_db: Path,
    *,
    items: Sequence[OwnerDecisionCockpitItem],
    source_inbox_item_count: int,
    generated_at_utc: str,
    source_generated_at_utc: str,
) -> None:
    output_db.parent.mkdir(parents=True, exist_ok=True)
    temp_db = output_db.with_name(f".{output_db.name}.tmp")
    if temp_db.exists():
        temp_db.unlink()
    status_counts = Counter(item.cockpit_status for item in items)
    with sqlite3.connect(temp_db) as conn:
        conn.executescript(
            """
            CREATE TABLE owner_decision_cockpit_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                source_generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                source_inbox_item_count INTEGER NOT NULL,
                inbox_item_count INTEGER NOT NULL,
                captured_decision_count INTEGER NOT NULL,
                awaiting_owner_input_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL CHECK (send_whatsapp_count = 0),
                crm_mutation_count INTEGER NOT NULL CHECK (crm_mutation_count = 0)
            );

            CREATE TABLE owner_decision_cockpit_items (
                cockpit_item_id TEXT PRIMARY KEY,
                review_item_id TEXT NOT NULL UNIQUE,
                packet_id TEXT NOT NULL,
                entry_id TEXT NOT NULL,
                cockpit_rank INTEGER NOT NULL,
                inbox_rank INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                review_state TEXT NOT NULL,
                console_bucket TEXT NOT NULL,
                owner_decision TEXT NOT NULL,
                decision_note TEXT NOT NULL,
                event_actor TEXT NOT NULL,
                event_recorded_at_utc TEXT NOT NULL,
                cockpit_status TEXT NOT NULL,
                output_template_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );

            CREATE INDEX idx_owner_decision_cockpit_rank
                ON owner_decision_cockpit_items(cockpit_rank);
            CREATE INDEX idx_owner_decision_cockpit_status
                ON owner_decision_cockpit_items(cockpit_status);
            CREATE INDEX idx_owner_decision_cockpit_decision
                ON owner_decision_cockpit_items(owner_decision);
            """
        )
        conn.execute(
            """
            INSERT INTO owner_decision_cockpit_runs (
                id, generated_at_utc, source_generated_at_utc, privacy_mode,
                source_inbox_item_count, inbox_item_count,
                captured_decision_count, awaiting_owner_input_count,
                send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, 0, 0)
            """,
            (
                generated_at_utc,
                source_generated_at_utc,
                "local_only_owner_decision_cockpit_no_raw_text_no_send_no_crm_mutation",
                source_inbox_item_count,
                len(items),
                status_counts.get(COCKPIT_READY_FOR_COMPILE, 0),
                status_counts.get(COCKPIT_AWAITING_OWNER_INPUT, 0),
            ),
        )
        conn.executemany(
            """
            INSERT INTO owner_decision_cockpit_items (
                cockpit_item_id, review_item_id, packet_id, entry_id,
                cockpit_rank, inbox_rank, assigned_lane, decision_type,
                review_state, console_bucket, owner_decision, decision_note,
                event_actor, event_recorded_at_utc, cockpit_status,
                output_template_json, send_whatsapp, crm_mutation,
                requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item.cockpit_item_id,
                    item.review_item_id,
                    item.packet_id,
                    item.entry_id,
                    item.cockpit_rank,
                    item.inbox_rank,
                    item.assigned_lane,
                    item.decision_type,
                    item.review_state,
                    item.console_bucket,
                    item.owner_decision,
                    item.decision_note,
                    item.event_actor,
                    item.event_recorded_at_utc,
                    item.cockpit_status,
                    json.dumps(item.template_record, ensure_ascii=False, sort_keys=True),
                    int(item.send_whatsapp),
                    int(item.crm_mutation),
                    int(item.requires_human_approval),
                )
                for item in items
            ],
        )
        conn.commit()
    _replace_sqlite(temp_db, output_db)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(text, encoding="utf-8")
    temp_path.replace(path)


def write_owner_decision_template_jsonl(
    output_template: Path,
    items: Sequence[OwnerDecisionCockpitItem],
) -> None:
    _atomic_write_text(
        output_template,
        "".join(
            json.dumps(item.template_record, ensure_ascii=False, sort_keys=True) + "\n"
            for item in items
        ),
    )


def _counter_table(title: str, counts: Counter[str]) -> list[str]:
    lines = [f"## {title}", "", "| Value | Count |", "|---|---:|"]
    if not counts:
        lines.append("| none | 0 |")
        return lines
    for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| {value or 'blank'} | {count} |")
    return lines


def write_summary(
    *,
    summary_path: Path,
    items: Sequence[OwnerDecisionCockpitItem],
    generated_at_utc: str,
    source_generated_at_utc: str,
) -> None:
    status_counts = Counter(item.cockpit_status for item in items)
    decision_counts = Counter(item.owner_decision for item in items)
    lane_counts = Counter(item.assigned_lane for item in items)
    lines = [
        "# Zantara Owner Decision Cockpit Summary",
        "",
        f"Generated UTC: `{generated_at_utc}`",
        f"Source Owner Decision Inbox UTC: `{source_generated_at_utc}`",
        "",
        "## Privacy Mode",
        "",
        "- This summary contains no raw message text.",
        "- This summary contains no message snippets.",
        "- This summary contains no phone numbers, emails, raw paths, case IDs, pack IDs, packet IDs, review item IDs, or inbox item IDs.",
        "- Owner Decision Cockpit artifacts are local-only and ignored under `research/personal/wa-corpus/`.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Owner inbox items | {len(items)} |",
        f"| Captured decisions | {status_counts.get(COCKPIT_READY_FOR_COMPILE, 0)} |",
        f"| Awaiting owner input | {status_counts.get(COCKPIT_AWAITING_OWNER_INPUT, 0)} |",
        "| WhatsApp sends | 0 |",
        "| CRM mutations | 0 |",
        "| Human approval required | 100% |",
        "",
        *_counter_table("Cockpit Status", status_counts),
        "",
        *_counter_table("Owner Decisions", decision_counts),
        "",
        *_counter_table("Assigned Lanes", lane_counts),
        "",
        "## Execution Contract",
        "",
        "- The Owner Decision Cockpit records only explicit owner inputs.",
        "- Missing owner inputs stay blank and awaiting owner input.",
        "- It writes a compiler-compatible owner decision template.",
        "- It does not parse raw WhatsApp messages.",
        "- It does not call a cloud LLM.",
        "- Runtime must not send WhatsApp messages from this artifact.",
        "- Runtime must not mutate CRM records from this artifact.",
        "- Human approval remains mandatory before any client-facing message or operational mutation.",
    ]
    _atomic_write_text(summary_path, "\n".join(lines) + "\n")


def build_owner_decision_cockpit(
    *,
    owner_inbox_db: Path = DEFAULT_OWNER_INBOX_DB,
    owner_inputs_jsonl: Path | None = None,
    inline_decisions: Sequence[str] = (),
    inline_decision_notes: Sequence[str] = (),
    inline_event_recorded_at_utc: Sequence[str] = (),
    output_dir: Path = DEFAULT_OWNER_DECISION_COCKPIT_DIR,
    output_db: Path | None = None,
    output_template: Path | None = None,
    summary_path: Path | None = None,
    generated_at_utc: str | None = None,
) -> OwnerDecisionCockpitBuildResult:
    """Build a local cockpit artifact and compiler-compatible decision template."""
    output_db = output_db or output_dir / DEFAULT_OUTPUT_DB.name
    output_template = output_template or output_dir / DEFAULT_OUTPUT_TEMPLATE.name
    summary_path = summary_path or output_dir / DEFAULT_SUMMARY.name
    generated = _format_utc(generated_at_utc)
    _clear_cockpit_outputs(
        output_db=output_db,
        output_template=output_template,
        summary_path=summary_path,
    )

    try:
        source_generated, source_count = read_source_metadata(owner_inbox_db)
        inbox_rows = read_owner_inbox_rows(owner_inbox_db)
        raw_inputs: list[dict[str, object]] = []
        if owner_inputs_jsonl is not None:
            raw_inputs.extend(_read_jsonl(owner_inputs_jsonl))
        raw_inputs.extend(
            _inline_input_rows(
                decisions=inline_decisions,
                decision_notes=inline_decision_notes,
                event_recorded_at_utc=inline_event_recorded_at_utc,
            )
        )
        owner_inputs = _owner_inputs_by_review_item(
            raw_inputs,
            generated_at_utc=generated,
        )
        items = build_cockpit_items(inbox_rows, owner_inputs)
        source_total = source_count or len(inbox_rows)

        write_owner_decision_cockpit_sqlite(
            output_db,
            items=items,
            source_inbox_item_count=source_total,
            generated_at_utc=generated,
            source_generated_at_utc=source_generated,
        )
        write_owner_decision_template_jsonl(output_template, items)
        write_summary(
            summary_path=summary_path,
            items=items,
            generated_at_utc=generated,
            source_generated_at_utc=source_generated,
        )
    except Exception:
        _clear_cockpit_outputs(
            output_db=output_db,
            output_template=output_template,
            summary_path=summary_path,
        )
        raise

    status_counts = Counter(item.cockpit_status for item in items)
    decision_counts = Counter(item.owner_decision for item in items)
    return OwnerDecisionCockpitBuildResult(
        inbox_item_count=len(items),
        captured_decision_count=status_counts.get(COCKPIT_READY_FOR_COMPILE, 0),
        awaiting_owner_input_count=status_counts.get(COCKPIT_AWAITING_OWNER_INPUT, 0),
        send_whatsapp_count=sum(1 for item in items if item.send_whatsapp),
        crm_mutation_count=sum(1 for item in items if item.crm_mutation),
        status_counts=dict(status_counts),
        decision_counts=dict(decision_counts),
        output_db=output_db,
        output_template=output_template,
        summary_path=summary_path,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a local-only Zantara Owner Decision Cockpit template."
    )
    parser.add_argument("--owner-inbox-db", type=Path, default=DEFAULT_OWNER_INBOX_DB)
    parser.add_argument("--owner-inputs-jsonl", type=Path, default=None)
    parser.add_argument("--decision", action="append", default=[])
    parser.add_argument("--decision-note", action="append", default=[])
    parser.add_argument("--event-recorded-at-utc", action="append", default=[])
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OWNER_DECISION_COCKPIT_DIR)
    parser.add_argument("--output-db", type=Path, default=None)
    parser.add_argument("--output-template", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=None)
    parser.add_argument("--generated-at-utc", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        result = build_owner_decision_cockpit(
            owner_inbox_db=args.owner_inbox_db,
            owner_inputs_jsonl=args.owner_inputs_jsonl,
            inline_decisions=args.decision,
            inline_decision_notes=args.decision_note,
            inline_event_recorded_at_utc=args.event_recorded_at_utc,
            output_dir=args.output_dir,
            output_db=args.output_db,
            output_template=args.output_template,
            summary_path=args.summary,
            generated_at_utc=args.generated_at_utc,
        )
    except (FileNotFoundError, ValueError, TypeError, json.JSONDecodeError):
        print("ERROR: Owner decision cockpit input is missing or invalid.", file=sys.stderr)
        return 1
    except (sqlite3.Error, OSError):
        print("ERROR: Owner decision cockpit run failed safely.", file=sys.stderr)
        return 1
    except Exception:
        print("ERROR: Owner decision cockpit run failed safely.", file=sys.stderr)
        return 1
    if args.json:
        print(
            json.dumps(
                {
                    "awaiting_owner_input_count": result.awaiting_owner_input_count,
                    "captured_decision_count": result.captured_decision_count,
                    "crm_mutation_count": result.crm_mutation_count,
                    "inbox_item_count": result.inbox_item_count,
                    "send_whatsapp_count": result.send_whatsapp_count,
                },
                sort_keys=True,
            )
        )
    else:
        print(
            "Owner decision cockpit complete: "
            f"{result.captured_decision_count}/{result.inbox_item_count} decisions -> "
            f"{result.output_template.name}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
