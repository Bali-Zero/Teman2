from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ANALYSIS_DIR = REPO_ROOT / "research/personal/wa-corpus/analysis"
DEFAULT_SUMMARY = DEFAULT_ANALYSIS_DIR / "analysis_inventory_summary.md"
FORBIDDEN_COLUMNS = frozenset({"body_text", "sender_raw", "local_path"})


@dataclass(frozen=True)
class TableCount:
    table_name: str
    row_count: int


@dataclass(frozen=True)
class SqliteArtifact:
    artifact_name: str
    table_counts: tuple[TableCount, ...]
    status: str

    @property
    def total_rows(self) -> int:
        return sum(table.row_count for table in self.table_counts)


@dataclass(frozen=True)
class SummaryArtifact:
    artifact_name: str
    title: str
    line_count: int


@dataclass(frozen=True)
class AnalysisInventory:
    analysis_dir_name: str
    sqlite_artifacts: tuple[SqliteArtifact, ...]
    summary_artifacts: tuple[SummaryArtifact, ...]

    @property
    def sqlite_count(self) -> int:
        return len(self.sqlite_artifacts)

    @property
    def summary_count(self) -> int:
        return len(self.summary_artifacts)


def _quote_identifier(value: str) -> str:
    if not value.replace("_", "").isalnum() or value[0].isdigit():
        raise ValueError(f"Unsafe SQLite identifier: {value!r}")
    return f'"{value}"'


def _deny_forbidden_column_reads(
    action: int,
    _arg1: str | None,
    arg2: str | None,
    _db_name: str | None,
    _trigger: str | None,
) -> int:
    if action == sqlite3.SQLITE_READ and (arg2 or "").lower() in FORBIDDEN_COLUMNS:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def _connect_readonly(db_path: Path) -> sqlite3.Connection:
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.set_authorizer(_deny_forbidden_column_reads)
    return conn


def _table_names(conn: sqlite3.Connection) -> tuple[str, ...]:
    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    return tuple(str(row["name"]) for row in rows)


def inspect_sqlite_artifact(db_path: Path) -> SqliteArtifact:
    """Inspect a local SQLite artifact using table counts only."""
    try:
        with _connect_readonly(db_path) as conn:
            table_counts = tuple(
                TableCount(
                    table_name=table_name,
                    row_count=int(
                        conn.execute(
                            f"SELECT COUNT(*) AS row_count FROM {_quote_identifier(table_name)}"
                        ).fetchone()["row_count"]
                    ),
                )
                for table_name in _table_names(conn)
            )
    except (OSError, sqlite3.Error, ValueError) as exc:
        return SqliteArtifact(
            artifact_name=db_path.name,
            table_counts=(),
            status=f"unreadable:{type(exc).__name__}",
        )
    return SqliteArtifact(
        artifact_name=db_path.name,
        table_counts=table_counts,
        status="ok",
    )


def inspect_summary_artifact(summary_path: Path) -> SummaryArtifact:
    """Read only the title and line count of a tracked markdown summary."""
    text = summary_path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    title = next((line.lstrip("# ").strip() for line in lines if line.startswith("#")), "(untitled)")
    return SummaryArtifact(
        artifact_name=summary_path.name,
        title=title,
        line_count=len(lines),
    )


def build_inventory(analysis_dir: Path) -> AnalysisInventory:
    """Build an aggregate inventory of analysis artifacts."""
    sqlite_artifacts = tuple(
        inspect_sqlite_artifact(path) for path in sorted(analysis_dir.glob("*.local.sqlite"))
    )
    summary_artifacts = tuple(
        inspect_summary_artifact(path) for path in sorted(analysis_dir.glob("*_summary.md"))
    )
    return AnalysisInventory(
        analysis_dir_name=analysis_dir.name,
        sqlite_artifacts=sqlite_artifacts,
        summary_artifacts=summary_artifacts,
    )


def _top_tables(artifacts: Sequence[SqliteArtifact], limit: int) -> list[tuple[str, str, int]]:
    rows: list[tuple[str, str, int]] = []
    for artifact in artifacts:
        for table_count in artifact.table_counts:
            rows.append((artifact.artifact_name, table_count.table_name, table_count.row_count))
    return sorted(rows, key=lambda row: (-row[2], row[0], row[1]))[:limit]


def inventory_to_dict(inventory: AnalysisInventory) -> dict[str, object]:
    """Convert inventory to JSON-serializable primitives."""
    return {
        "analysis_dir_name": inventory.analysis_dir_name,
        "sqlite_count": inventory.sqlite_count,
        "summary_count": inventory.summary_count,
        "sqlite_artifacts": [
            {
                "artifact_name": artifact.artifact_name,
                "status": artifact.status,
                "total_rows": artifact.total_rows,
                "table_count": len(artifact.table_counts),
            }
            for artifact in inventory.sqlite_artifacts
        ],
        "summary_artifacts": [
            {
                "artifact_name": artifact.artifact_name,
                "title": artifact.title,
                "line_count": artifact.line_count,
            }
            for artifact in inventory.summary_artifacts
        ],
    }


def write_summary(
    *,
    inventory: AnalysisInventory,
    summary_path: Path,
    generated_at_utc: str | None = None,
    top_limit: int = 20,
) -> None:
    """Write an aggregate-only inventory summary."""
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat(timespec="seconds")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# WhatsApp Analysis Inventory Summary",
        "",
        f"Generated UTC: `{generated}`",
        f"Analysis directory label: `{inventory.analysis_dir_name}`",
        "",
        "## Privacy Mode",
        "",
        "- This inventory does not open raw corpus files.",
        "- This inventory does not select raw message text, sender labels, or local paths.",
        "- SQLite inspection is limited to table names and row counts.",
        "- Tracked output contains artifact names, table names, titles, and counts only.",
        "",
        "## Artifact Counts",
        "",
        "| Artifact type | Count |",
        "|---|---:|",
        f"| Local SQLite artifacts | {inventory.sqlite_count} |",
        f"| Tracked markdown summaries | {inventory.summary_count} |",
        "",
        "## Local SQLite Artifacts",
        "",
        "| Artifact | Status | Tables | Total rows |",
        "|---|---|---:|---:|",
    ]
    for artifact in inventory.sqlite_artifacts:
        lines.append(
            f"| {artifact.artifact_name} | {artifact.status} | "
            f"{len(artifact.table_counts)} | {artifact.total_rows} |"
        )

    lines.extend(
        [
            "",
            "## Largest Local Tables",
            "",
            "| Artifact | Table | Rows |",
            "|---|---|---:|",
        ]
    )
    for artifact_name, table_name, row_count in _top_tables(inventory.sqlite_artifacts, top_limit):
        lines.append(f"| {artifact_name} | {table_name} | {row_count} |")

    lines.extend(
        [
            "",
            "## Tracked Summaries",
            "",
            "| Summary | Title | Lines |",
            "|---|---|---:|",
        ]
    )
    for artifact in inventory.summary_artifacts:
        lines.append(f"| {artifact.artifact_name} | {artifact.title} | {artifact.line_count} |")

    lines.extend(
        [
            "",
            "## Next Safe Step",
            "",
            "Use this inventory as the run checklist before adding new local extractors. New analyzers should add one ignored `.local.sqlite` artifact and one aggregate tracked summary.",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build an aggregate inventory of local WhatsApp analysis artifacts."
    )
    parser.add_argument(
        "--analysis-dir",
        type=Path,
        default=DEFAULT_ANALYSIS_DIR,
        help="Directory containing WhatsApp analysis artifacts.",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=DEFAULT_SUMMARY,
        help="Tracked markdown summary to write.",
    )
    parser.add_argument("--top-limit", type=int, default=20, help="Largest table rows to show.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable summary to stdout.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    inventory = build_inventory(args.analysis_dir)
    write_summary(inventory=inventory, summary_path=args.summary, top_limit=args.top_limit)
    if args.json:
        json.dump(inventory_to_dict(inventory), sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
