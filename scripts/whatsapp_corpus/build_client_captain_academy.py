from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

DEFAULT_ANALYSIS_DIR = Path("research/personal/wa-corpus/analysis")
DEFAULT_CLIENT_CAPTAIN_DIR = Path("research/personal/wa-corpus/client-captain")
DEFAULT_CASE_WINDOWS_DB = DEFAULT_ANALYSIS_DIR / "allowed_case_windows.local.sqlite"
DEFAULT_OUTPUT_DB = DEFAULT_CLIENT_CAPTAIN_DIR / "client_captain_academy.local.sqlite"
DEFAULT_JSONL = DEFAULT_CLIENT_CAPTAIN_DIR / "training_examples.local.jsonl"
DEFAULT_SUMMARY = DEFAULT_CLIENT_CAPTAIN_DIR / "client_captain_academy_summary.md"

EXPECTED_CASE_WINDOWS_DB_NAME = "allowed_case_windows.local.sqlite"
CASE_OWNER = "zantara_client_captain"


@dataclass(frozen=True)
class CaseWindowRow:
    window_id: str
    file_id: str
    window_ordinal: int
    first_timestamp: str | None
    last_timestamp: str | None
    first_month: str
    last_month: str
    first_message_index: int
    last_message_index: int
    event_count: int
    message_count: int
    domain_count: int
    dominant_domain: str
    severity_high_count: int
    top_event_codes_json: str


@dataclass(frozen=True)
class DomainFeature:
    domain_code: str
    event_count: int
    message_count: int


@dataclass(frozen=True)
class EventCodeFeature:
    rank: int
    domain_code: str
    event_code: str
    event_count: int


@dataclass(frozen=True)
class CaptainExample:
    example_id: str
    window: CaseWindowRow
    domains: tuple[DomainFeature, ...]
    event_codes: tuple[EventCodeFeature, ...]
    priority: str
    next_action: str
    human_specialist: str
    operator_coaching_mode: str

    @property
    def cut_message_index(self) -> int:
        return (self.window.first_message_index + self.window.last_message_index) // 2

    def input_payload(self) -> dict[str, object]:
        return {
            "schema_version": "client_captain_academy.v1",
            "privacy_mode": "local_only_aggregate_no_raw_text",
            "case_owner": CASE_OWNER,
            "case_window": {
                "first_month": self.window.first_month,
                "last_month": self.window.last_month,
                "event_count": self.window.event_count,
                "message_count": self.window.message_count,
                "domain_count": self.window.domain_count,
                "dominant_domain": self.window.dominant_domain,
                "severity_high_count": self.window.severity_high_count,
            },
            "domain_features": [
                {
                    "domain_code": domain.domain_code,
                    "event_count": domain.event_count,
                    "message_count": domain.message_count,
                }
                for domain in self.domains
            ],
            "top_event_codes": [
                {
                    "rank": event.rank,
                    "domain_code": event.domain_code,
                    "event_code": event.event_code,
                    "event_count": event.event_count,
                }
                for event in self.event_codes
            ],
        }

    def output_payload(self) -> dict[str, object]:
        return {
            "case_owner": CASE_OWNER,
            "next_action": self.next_action,
            "priority": self.priority,
            "human_specialist": self.human_specialist,
            "operator_coaching_mode": self.operator_coaching_mode,
            "send_whatsapp": False,
            "crm_mutation": False,
        }

    def jsonl_record(self) -> dict[str, object]:
        return {
            "example_id": self.example_id,
            "academy_task": "case_captain_next_action",
            "case_owner": CASE_OWNER,
            "captain_input": self.input_payload(),
            "captain_output": self.output_payload(),
        }


@dataclass(frozen=True)
class AcademyBuildResult:
    example_count: int
    replay_count: int
    owner_counts: dict[str, int]
    priority_counts: dict[str, int]
    output_db: Path
    output_jsonl: Path
    summary_path: Path


def _connect_case_windows(db_path: Path) -> sqlite3.Connection:
    if db_path.name != EXPECTED_CASE_WINDOWS_DB_NAME:
        raise ValueError(f"Refusing to read unexpected input artifact: {db_path.name}")
    if not db_path.exists():
        raise FileNotFoundError(f"Input DB not found: {db_path}")
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _read_case_windows(db_path: Path) -> tuple[CaseWindowRow, ...]:
    with _connect_case_windows(db_path) as conn:
        rows = conn.execute(
            """
            SELECT window_id, file_id, window_ordinal, first_timestamp, last_timestamp,
                   first_month, last_month, first_message_index, last_message_index,
                   event_count, message_count, domain_count, dominant_domain,
                   severity_high_count, top_event_codes_json
            FROM case_windows
            ORDER BY severity_high_count DESC, event_count DESC, message_count DESC,
                     domain_count DESC, window_id
            """
        ).fetchall()
    return tuple(
        CaseWindowRow(
            window_id=str(row["window_id"]),
            file_id=str(row["file_id"]),
            window_ordinal=int(row["window_ordinal"]),
            first_timestamp=row["first_timestamp"],
            last_timestamp=row["last_timestamp"],
            first_month=str(row["first_month"]),
            last_month=str(row["last_month"]),
            first_message_index=int(row["first_message_index"]),
            last_message_index=int(row["last_message_index"]),
            event_count=int(row["event_count"]),
            message_count=int(row["message_count"]),
            domain_count=int(row["domain_count"]),
            dominant_domain=str(row["dominant_domain"]),
            severity_high_count=int(row["severity_high_count"]),
            top_event_codes_json=str(row["top_event_codes_json"]),
        )
        for row in rows
    )


def _read_domain_features(db_path: Path) -> dict[str, tuple[DomainFeature, ...]]:
    with _connect_case_windows(db_path) as conn:
        rows = conn.execute(
            """
            SELECT window_id, domain_code, event_count, message_count
            FROM case_window_domains
            ORDER BY window_id, event_count DESC, domain_code
            """
        ).fetchall()
    grouped: dict[str, list[DomainFeature]] = defaultdict(list)
    for row in rows:
        grouped[str(row["window_id"])].append(
            DomainFeature(
                domain_code=str(row["domain_code"]),
                event_count=int(row["event_count"]),
                message_count=int(row["message_count"]),
            )
        )
    return {window_id: tuple(features) for window_id, features in grouped.items()}


def _read_event_code_features(db_path: Path) -> dict[str, tuple[EventCodeFeature, ...]]:
    with _connect_case_windows(db_path) as conn:
        rows = conn.execute(
            """
            SELECT window_id, rank, domain_code, event_code, event_count
            FROM case_window_event_codes
            ORDER BY window_id, rank
            """
        ).fetchall()
    grouped: dict[str, list[EventCodeFeature]] = defaultdict(list)
    for row in rows:
        grouped[str(row["window_id"])].append(
            EventCodeFeature(
                rank=int(row["rank"]),
                domain_code=str(row["domain_code"]),
                event_code=str(row["event_code"]),
                event_count=int(row["event_count"]),
            )
        )
    return {window_id: tuple(features) for window_id, features in grouped.items()}


def _next_action_for_domain(domain_code: str) -> tuple[str, str]:
    return {
        "immigration_lifecycle": ("immigration_status_check", "ari"),
        "document_requirement": ("document_chase", "adit"),
        "tax_payment": ("payment_reconcile", "surya"),
        "followup_risk": ("crm_followup", "sahira"),
        "operational_risk": ("team_escalation", "sahira"),
        "crm_lead_intake": ("lead_context_review", "sahira"),
        "knowledge_mining": ("kb_extract", "adit"),
        "relationship_memory": ("case_note", "sahira"),
    }.get(domain_code, ("case_note", "sahira"))


def _priority(window: CaseWindowRow) -> str:
    if window.severity_high_count > 0:
        return "high"
    if window.dominant_domain in {"followup_risk", "operational_risk"}:
        return "high"
    return "normal"


def _operator_coaching_mode(window: CaseWindowRow, priority: str) -> str:
    if priority == "high" and window.dominant_domain == "followup_risk":
        return "firm_accountability_nudge"
    if priority == "high":
        return "supportive_urgent_nudge"
    return "steady_family_motivation"


def build_examples(
    case_windows_db: Path,
    *,
    max_examples: int | None = None,
) -> tuple[CaptainExample, ...]:
    windows = _read_case_windows(case_windows_db)
    domain_features = _read_domain_features(case_windows_db)
    event_code_features = _read_event_code_features(case_windows_db)
    selected = windows[:max_examples] if max_examples is not None else windows
    examples: list[CaptainExample] = []
    for window in selected:
        next_action, human_specialist = _next_action_for_domain(window.dominant_domain)
        priority = _priority(window)
        examples.append(
            CaptainExample(
                example_id=f"cca-{window.window_id}",
                window=window,
                domains=domain_features.get(window.window_id, ()),
                event_codes=event_code_features.get(window.window_id, ()),
                priority=priority,
                next_action=next_action,
                human_specialist=human_specialist,
                operator_coaching_mode=_operator_coaching_mode(window, priority),
            )
        )
    return tuple(examples)


def write_jsonl(path: Path, examples: Sequence[CaptainExample]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(example.jsonl_record(), ensure_ascii=False, sort_keys=True)
        for example in examples
    ]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def write_sqlite(path: Path, examples: Sequence[CaptainExample]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE academy_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                example_count INTEGER NOT NULL,
                replay_count INTEGER NOT NULL
            );

            CREATE TABLE captain_training_examples (
                example_id TEXT PRIMARY KEY,
                source_window_id TEXT NOT NULL,
                file_id TEXT NOT NULL,
                case_owner TEXT NOT NULL,
                dominant_domain TEXT NOT NULL,
                priority TEXT NOT NULL,
                next_action TEXT NOT NULL,
                human_specialist TEXT NOT NULL,
                operator_coaching_mode TEXT NOT NULL,
                first_month TEXT NOT NULL,
                last_month TEXT NOT NULL,
                first_message_index INTEGER NOT NULL,
                last_message_index INTEGER NOT NULL,
                event_count INTEGER NOT NULL,
                message_count INTEGER NOT NULL,
                domain_count INTEGER NOT NULL,
                severity_high_count INTEGER NOT NULL,
                captain_input_json TEXT NOT NULL,
                captain_output_json TEXT NOT NULL
            );

            CREATE TABLE captain_replay_scenarios (
                replay_id TEXT PRIMARY KEY,
                example_id TEXT NOT NULL,
                cut_message_index INTEGER NOT NULL,
                expected_next_action TEXT NOT NULL,
                expected_priority TEXT NOT NULL,
                expected_human_specialist TEXT NOT NULL,
                expected_case_owner TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            INSERT INTO academy_runs (
                id, generated_at_utc, privacy_mode, example_count, replay_count
            )
            VALUES (1, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "local_only_case_windows_no_raw_text_no_raw_paths",
                len(examples),
                len(examples),
            ),
        )
        conn.executemany(
            """
            INSERT INTO captain_training_examples (
                example_id, source_window_id, file_id, case_owner, dominant_domain,
                priority, next_action, human_specialist, operator_coaching_mode,
                first_month, last_month, first_message_index, last_message_index,
                event_count, message_count, domain_count, severity_high_count,
                captain_input_json, captain_output_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    example.example_id,
                    example.window.window_id,
                    example.window.file_id,
                    CASE_OWNER,
                    example.window.dominant_domain,
                    example.priority,
                    example.next_action,
                    example.human_specialist,
                    example.operator_coaching_mode,
                    example.window.first_month,
                    example.window.last_month,
                    example.window.first_message_index,
                    example.window.last_message_index,
                    example.window.event_count,
                    example.window.message_count,
                    example.window.domain_count,
                    example.window.severity_high_count,
                    json.dumps(example.input_payload(), ensure_ascii=False, sort_keys=True),
                    json.dumps(example.output_payload(), ensure_ascii=False, sort_keys=True),
                )
                for example in examples
            ],
        )
        conn.executemany(
            """
            INSERT INTO captain_replay_scenarios (
                replay_id, example_id, cut_message_index, expected_next_action,
                expected_priority, expected_human_specialist, expected_case_owner
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    f"replay-{example.example_id}",
                    example.example_id,
                    example.cut_message_index,
                    example.next_action,
                    example.priority,
                    example.human_specialist,
                    CASE_OWNER,
                )
                for example in examples
            ],
        )
        conn.commit()


def _counter_table(title: str, counts: Counter[str]) -> list[str]:
    rows = [f"## {title}", "", "| Value | Count |", "|---|---:|"]
    for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        rows.append(f"| {value or 'unknown'} | {count} |")
    if not counts:
        rows.append("| none | 0 |")
    return rows


def write_summary(
    *,
    summary_path: Path,
    examples: Sequence[CaptainExample],
    generated_at_utc: str | None = None,
) -> None:
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat(timespec="seconds")
    owner_counts = Counter(CASE_OWNER for _ in examples)
    priority_counts = Counter(example.priority for example in examples)
    action_counts = Counter(example.next_action for example in examples)
    specialist_counts = Counter(example.human_specialist for example in examples)
    domain_counts = Counter(example.window.dominant_domain for example in examples)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Zantara Client Captain Academy Summary",
        "",
        f"Generated UTC: `{generated}`",
        "",
        "## Privacy Mode",
        "",
        "- This summary contains no raw message text.",
        "- This summary contains no message snippets.",
        "- This summary contains no phone numbers, emails, or raw paths.",
        "- This summary contains no per-window IDs, per-file IDs, or event-code values.",
        "- Local `.local.sqlite` and `.local.jsonl` artifacts stay ignored under `research/personal/wa-corpus/`.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Training examples | {len(examples)} |",
        f"| Replay scenarios | {len(examples)} |",
        "",
        *_counter_table("Case Owners", owner_counts),
        "",
        *_counter_table("Priorities", priority_counts),
        "",
        *_counter_table("Next Actions", action_counts),
        "",
        *_counter_table("Human Specialists", specialist_counts),
        "",
        *_counter_table("Dominant Domains", domain_counts),
        "",
        "## Execution Contract",
        "",
        "- The Captain is always the case owner.",
        "- Human names are specialist lanes, not ownership assignment.",
        "- Shadow mode remains the only allowed runtime target for this dataset.",
        "- Do not train a cloud model on the generated local JSONL.",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_client_captain_academy(
    *,
    case_windows_db: Path = DEFAULT_CASE_WINDOWS_DB,
    output_dir: Path = DEFAULT_CLIENT_CAPTAIN_DIR,
    output_db: Path | None = None,
    output_jsonl: Path | None = None,
    summary_path: Path = DEFAULT_SUMMARY,
    max_examples: int | None = None,
) -> AcademyBuildResult:
    """Build local-only Client Captain examples from anonymous case windows."""
    output_db = output_db or output_dir / DEFAULT_OUTPUT_DB.name
    output_jsonl = output_jsonl or output_dir / DEFAULT_JSONL.name
    examples = build_examples(case_windows_db, max_examples=max_examples)
    write_sqlite(output_db, examples)
    write_jsonl(output_jsonl, examples)
    write_summary(summary_path=summary_path, examples=examples)
    owner_counts = Counter(CASE_OWNER for _ in examples)
    priority_counts = Counter(example.priority for example in examples)
    return AcademyBuildResult(
        example_count=len(examples),
        replay_count=len(examples),
        owner_counts=dict(owner_counts),
        priority_counts=dict(priority_counts),
        output_db=output_db,
        output_jsonl=output_jsonl,
        summary_path=summary_path,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build local-only Zantara Client Captain Academy examples."
    )
    parser.add_argument("--case-windows-db", type=Path, default=DEFAULT_CASE_WINDOWS_DB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_CLIENT_CAPTAIN_DIR)
    parser.add_argument("--output-db", type=Path, default=None)
    parser.add_argument("--output-jsonl", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--max-examples", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        result = build_client_captain_academy(
            case_windows_db=args.case_windows_db,
            output_dir=args.output_dir,
            output_db=args.output_db,
            output_jsonl=args.output_jsonl,
            summary_path=args.summary,
            max_examples=args.max_examples,
        )
    except (FileNotFoundError, ValueError, TypeError, json.JSONDecodeError):
        print("ERROR: Client Captain Academy input is missing or invalid.", file=sys.stderr)
        return 1
    except (sqlite3.Error, OSError):
        print("ERROR: Client Captain Academy run failed safely.", file=sys.stderr)
        return 1
    except Exception:
        print("ERROR: Client Captain Academy run failed safely.", file=sys.stderr)
        return 1
    if args.json:
        print(
            json.dumps(
                {
                    "example_count": result.example_count,
                    "replay_count": result.replay_count,
                },
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
