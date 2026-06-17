from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

DEFAULT_LSJSON = Path("research/personal/wa-corpus/drive/drive_lsjson.local.json")
DEFAULT_OUTPUT_DIR = Path("research/personal/wa-corpus/drive")
DEFAULT_OUTPUT_DB = DEFAULT_OUTPUT_DIR / "drive_export_manifest.local.sqlite"
DEFAULT_SUMMARY = DEFAULT_OUTPUT_DIR / "drive_export_manifest_summary.md"


@dataclass(frozen=True)
class DriveExportCandidate:
    file_id: str
    candidate_kind: str
    raw_path: str
    raw_name: str
    path_hash: str
    name_hash: str
    drive_id: str | None
    drive_id_hash: str | None
    size_bytes: int
    mod_time: str | None
    mime_type: str | None


@dataclass(frozen=True)
class DriveManifestResult:
    scanned_records: int
    candidate_count: int
    total_size_bytes: int


def short_hash(value: str, length: int = 24) -> str:
    """Return a stable short hash for private identifiers."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def load_lsjson(path: Path) -> list[dict[str, Any]]:
    """Load rclone lsjson output from a local JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("rclone lsjson payload must be a JSON array")
    records: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("rclone lsjson entries must be JSON objects")
        records.append(item)
    return records


def build_candidates(
    records: Iterable[dict[str, Any]],
    *,
    remote_label: str,
) -> list[DriveExportCandidate]:
    """Build privacy-addressable WhatsApp export candidates from lsjson records."""
    selected: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for record in records:
        if bool(record.get("IsDir")):
            continue
        raw_path = str(record.get("Path") or record.get("Name") or "").strip()
        raw_name = str(record.get("Name") or Path(raw_path).name).strip()
        if not raw_path or not raw_name:
            continue
        if not _is_whatsapp_chat_zip(raw_path, raw_name, str(record.get("MimeType") or "")):
            continue
        drive_id = str(record.get("ID") or "").strip()
        dedupe_key = drive_id or raw_path
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        selected.append(record)

    width = max(4, len(str(len(selected))))
    candidates: list[DriveExportCandidate] = []
    for index, record in enumerate(selected, start=1):
        raw_path = str(record.get("Path") or record.get("Name") or "").strip()
        raw_name = str(record.get("Name") or Path(raw_path).name).strip()
        drive_id = str(record.get("ID") or "").strip() or None
        size_bytes = _as_int(record.get("Size"))
        private_locator = drive_id or raw_path
        candidates.append(
            DriveExportCandidate(
                file_id=f"drive-wa-{index:0{width}d}",
                candidate_kind="whatsapp_chat_zip",
                raw_path=raw_path,
                raw_name=raw_name,
                path_hash=short_hash(f"{remote_label}\n{private_locator}\n{raw_path}"),
                name_hash=short_hash(raw_name),
                drive_id=drive_id,
                drive_id_hash=short_hash(drive_id) if drive_id else None,
                size_bytes=size_bytes,
                mod_time=str(record.get("ModTime") or "").strip() or None,
                mime_type=str(record.get("MimeType") or "").strip() or None,
            )
        )
    return candidates


def write_sqlite(
    *,
    db_path: Path,
    remote_label: str,
    scanned_records: int,
    candidates: list[DriveExportCandidate],
) -> None:
    """Write the local-only manifest database."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE drive_manifest_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                remote_label_hash TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                scanned_records INTEGER NOT NULL,
                candidate_count INTEGER NOT NULL,
                total_size_bytes INTEGER NOT NULL
            );

            CREATE TABLE drive_export_candidates (
                file_id TEXT PRIMARY KEY,
                candidate_kind TEXT NOT NULL,
                raw_path TEXT NOT NULL,
                raw_name TEXT NOT NULL,
                path_hash TEXT NOT NULL UNIQUE,
                name_hash TEXT NOT NULL,
                drive_id TEXT,
                drive_id_hash TEXT,
                size_bytes INTEGER NOT NULL,
                mod_time TEXT,
                mime_type TEXT,
                download_status TEXT NOT NULL,
                imported_to_corpus INTEGER NOT NULL
            );

            CREATE INDEX idx_drive_export_candidates_kind
                ON drive_export_candidates(candidate_kind);
            CREATE INDEX idx_drive_export_candidates_size
                ON drive_export_candidates(size_bytes);
            """
        )
        conn.execute(
            """
            INSERT INTO drive_manifest_runs (
                id, generated_at_utc, remote_label_hash, privacy_mode,
                scanned_records, candidate_count, total_size_bytes
            )
            VALUES (1, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                short_hash(remote_label, length=16),
                "local_only_raw_drive_paths_in_ignored_sqlite_summary_aggregate_only",
                scanned_records,
                len(candidates),
                sum(candidate.size_bytes for candidate in candidates),
            ),
        )
        conn.executemany(
            """
            INSERT INTO drive_export_candidates (
                file_id, candidate_kind, raw_path, raw_name, path_hash, name_hash,
                drive_id, drive_id_hash, size_bytes, mod_time, mime_type,
                download_status, imported_to_corpus
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', 0)
            """,
            [
                (
                    candidate.file_id,
                    candidate.candidate_kind,
                    candidate.raw_path,
                    candidate.raw_name,
                    candidate.path_hash,
                    candidate.name_hash,
                    candidate.drive_id,
                    candidate.drive_id_hash,
                    candidate.size_bytes,
                    candidate.mod_time,
                    candidate.mime_type,
                )
                for candidate in candidates
            ],
        )


def write_summary(
    *,
    summary_path: Path,
    db_path: Path,
    scanned_records: int,
    candidates: list[DriveExportCandidate],
) -> None:
    """Write a shareable aggregate-only summary."""
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    kind_counts = Counter(candidate.candidate_kind for candidate in candidates)
    total_size = sum(candidate.size_bytes for candidate in candidates)
    lines: list[str] = [
        "# Cloud Export Manifest Summary",
        "",
        f"Generated UTC: `{datetime.now(timezone.utc).isoformat(timespec='seconds')}`",
        f"SQLite manifest file: `{db_path.name}`",
        "",
        "## Privacy Mode",
        "",
        "- Aggregate summary only.",
        "- No raw cloud file names.",
        "- No raw cloud paths.",
        "- No cloud file ids.",
        "- Raw resolver fields exist only in the ignored local SQLite manifest.",
        "",
        "## Global Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Metadata records scanned | {_fmt_int(scanned_records)} |",
        f"| Candidate export ZIP files | {_fmt_int(len(candidates))} |",
        f"| Candidate total size bytes | {_fmt_int(total_size)} |",
        "",
        "## Candidate Kinds",
        "",
        "| Kind | Files |",
        "|---|---:|",
    ]
    if kind_counts:
        for kind, count in kind_counts.most_common():
            lines.append(f"| {kind} | {_fmt_int(count)} |")
    else:
        lines.append("| none | 0 |")

    lines.extend(
        [
            "",
            "## Candidate References",
            "",
            "| File ID | Kind | Size bytes | Modified month |",
            "|---|---|---:|---|",
        ]
    )
    for candidate in candidates[:50]:
        lines.append(
            "| {file_id} | {kind} | {size} | {month} |".format(
                file_id=candidate.file_id,
                kind=candidate.candidate_kind,
                size=_fmt_int(candidate.size_bytes),
                month=_month_bucket(candidate.mod_time),
            )
        )
    if len(candidates) > 50:
        lines.append(f"| more | hidden | {_fmt_int(len(candidates) - 50)} | aggregate-only |")
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_drive_export_manifest(
    *,
    lsjson_path: Path,
    output_db: Path = DEFAULT_OUTPUT_DB,
    summary_path: Path = DEFAULT_SUMMARY,
    remote_label: str = "gdrive",
) -> DriveManifestResult:
    """Build the local-only manifest from a saved rclone lsjson payload."""
    records = load_lsjson(lsjson_path)
    candidates = build_candidates(records, remote_label=remote_label)
    write_sqlite(
        db_path=output_db,
        remote_label=remote_label,
        scanned_records=len(records),
        candidates=candidates,
    )
    write_summary(
        summary_path=summary_path,
        db_path=output_db,
        scanned_records=len(records),
        candidates=candidates,
    )
    return DriveManifestResult(
        scanned_records=len(records),
        candidate_count=len(candidates),
        total_size_bytes=sum(candidate.size_bytes for candidate in candidates),
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a local-only WhatsApp export manifest from rclone lsjson output."
    )
    parser.add_argument("--lsjson", type=Path, default=DEFAULT_LSJSON)
    parser.add_argument("--output-db", type=Path, default=DEFAULT_OUTPUT_DB)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--remote-label", default="gdrive")
    parser.add_argument("--json", action="store_true", help="Print aggregate counts as JSON.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = build_drive_export_manifest(
            lsjson_path=args.lsjson,
            output_db=args.output_db,
            summary_path=args.summary,
            remote_label=args.remote_label,
        )
    except (FileNotFoundError, ValueError, TypeError, json.JSONDecodeError):
        print("ERROR: Drive export manifest input is missing or invalid.", file=sys.stderr)
        return 1
    except (sqlite3.Error, OSError):
        print("ERROR: Drive export manifest run failed safely.", file=sys.stderr)
        return 1
    except Exception:
        print("ERROR: Drive export manifest run failed safely.", file=sys.stderr)
        return 1
    if args.json:
        sys.stdout.write(
            json.dumps(
                {
                    "candidate_count": result.candidate_count,
                    "scanned_records": result.scanned_records,
                    "total_size_bytes": result.total_size_bytes,
                },
                sort_keys=True,
            )
            + "\n"
        )
    return 0


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _is_whatsapp_chat_zip(raw_path: str, raw_name: str, mime_type: str) -> bool:
    text = _normalize_text(f"{raw_path} {raw_name}")
    if not (raw_path.lower().endswith(".zip") or raw_name.lower().endswith(".zip")):
        return False
    if "whatsapp chat" in text:
        return True
    return "application/zip" in mime_type.lower() and "whatsapp chat" in text


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).lower()
    return " ".join(normalized.replace("_", " ").replace("-", " ").split())


def _month_bucket(value: str | None) -> str:
    if not value:
        return "unknown"
    return value[:7] if len(value) >= 7 else "unknown"


def _fmt_int(value: int) -> str:
    return f"{value:,}"


if __name__ == "__main__":
    raise SystemExit(main())
