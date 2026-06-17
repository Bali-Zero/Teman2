from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

DEFAULT_DRIVE_DIR = Path("research/personal/wa-corpus/drive")
DEFAULT_MANIFEST_DB = DEFAULT_DRIVE_DIR / "drive_export_manifest.local.sqlite"
DEFAULT_DOWNLOAD_DIR = DEFAULT_DRIVE_DIR / "downloads.local"
DEFAULT_CORPUS_ROOT = Path.home() / "Desktop" / "wa-chats-MASTER-2026-05-26"
DEFAULT_IMPORT_SOURCE = "03_drive-imports"
DEFAULT_SUMMARY = DEFAULT_DRIVE_DIR / "drive_import_summary.md"
EXPECTED_MANIFEST_DB_NAME = "drive_export_manifest.local.sqlite"

Runner = Callable[[list[str]], int]


@dataclass(frozen=True)
class ImportCandidate:
    file_id: str
    raw_path: str
    drive_id: str | None
    size_bytes: int


@dataclass(frozen=True)
class ImportRowResult:
    file_id: str
    status: str
    size_bytes: int
    extracted_text_files: int


@dataclass(frozen=True)
class DriveImportResult:
    selected_count: int
    downloaded_count: int
    extracted_text_files: int
    failed_count: int
    summary_path: Path


def _default_runner(command: list[str]) -> int:
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    return completed.returncode


def _connect_manifest(db_path: Path) -> sqlite3.Connection:
    if db_path.name != EXPECTED_MANIFEST_DB_NAME:
        raise ValueError(f"Refusing unexpected manifest DB: {db_path.name}")
    if not db_path.exists():
        raise FileNotFoundError(f"Manifest DB not found: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _load_candidates(
    conn: sqlite3.Connection,
    *,
    limit: int,
    max_size_bytes: int | None,
) -> list[ImportCandidate]:
    clauses = [
        "candidate_kind = 'whatsapp_chat_zip'",
        "download_status = 'pending'",
        "imported_to_corpus = 0",
    ]
    params: list[int] = []
    if max_size_bytes is not None:
        clauses.append("size_bytes <= ?")
        params.append(max_size_bytes)
    sql = f"""
        SELECT file_id, raw_path, drive_id, size_bytes
        FROM drive_export_candidates
        WHERE {" AND ".join(clauses)}
        ORDER BY size_bytes ASC, file_id
        LIMIT ?
    """
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [
        ImportCandidate(
            file_id=str(row["file_id"]),
            raw_path=str(row["raw_path"]),
            drive_id=str(row["drive_id"]) if row["drive_id"] else None,
            size_bytes=int(row["size_bytes"]),
        )
        for row in rows
    ]


def _download_command(
    *,
    candidate: ImportCandidate,
    remote_label: str,
    rclone_bin: str,
    destination_zip: Path,
) -> list[str]:
    if candidate.drive_id:
        return [
            rclone_bin,
            "backend",
            "copyid",
            f"{remote_label}:",
            candidate.drive_id,
            str(destination_zip),
        ]
    return [
        rclone_bin,
        "copyto",
        f"{remote_label}:{candidate.raw_path}",
        str(destination_zip),
    ]


def _extract_chat_texts(
    *,
    zip_path: Path,
    import_source_dir: Path,
    file_id: str,
) -> int:
    destination = import_source_dir / file_id
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)

    extracted = 0
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            if member.is_dir() or not member.filename.lower().endswith(".txt"):
                continue
            extracted += 1
            output_path = destination / f"chat-{extracted:04d}.txt"
            with archive.open(member, "r") as source, output_path.open("wb") as target:
                shutil.copyfileobj(source, target)
    return extracted


def _update_status(
    conn: sqlite3.Connection,
    *,
    file_id: str,
    status: str,
    imported_to_corpus: bool,
) -> None:
    conn.execute(
        """
        UPDATE drive_export_candidates
        SET download_status = ?, imported_to_corpus = ?
        WHERE file_id = ?
        """,
        (status, 1 if imported_to_corpus else 0, file_id),
    )


def _write_summary(
    *,
    summary_path: Path,
    rows: list[ImportRowResult],
    execute: bool,
    import_source_name: str,
) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    selected_count = len(rows)
    downloaded_count = sum(1 for row in rows if row.status == "imported")
    extracted_count = sum(row.extracted_text_files for row in rows)
    failed_count = sum(1 for row in rows if row.status == "failed")
    mode = "execute" if execute else "dry_run"
    lines = [
        "# Drive Export Import Summary",
        "",
        f"Generated UTC: `{datetime.now(timezone.utc).isoformat(timespec='seconds')}`",
        "",
        "## Privacy Mode",
        "",
        "- Aggregate summary only.",
        "- No raw cloud file names.",
        "- No raw cloud paths.",
        "- No cloud file ids.",
        "- Downloaded ZIPs and extracted chat TXT files stay local-only on the Pro.",
        "",
        "## Import Scope",
        "",
        f"- Mode: `{mode}`",
        f"- Local corpus source: `{import_source_name}`",
        "",
        "## Global Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Candidates selected | {_fmt_int(selected_count)} |",
        f"| ZIPs imported | {_fmt_int(downloaded_count)} |",
        f"| Text files extracted | {_fmt_int(extracted_count)} |",
        f"| Failed candidates | {_fmt_int(failed_count)} |",
        "",
        "## Candidate Results",
        "",
        "| File ID | Status | Size bytes | Text files |",
        "|---|---|---:|---:|",
    ]
    for row in rows[:50]:
        lines.append(
            f"| {row.file_id} | {row.status} | {_fmt_int(row.size_bytes)} | "
            f"{_fmt_int(row.extracted_text_files)} |"
        )
    if len(rows) > 50:
        lines.append(f"| more | hidden | {_fmt_int(len(rows) - 50)} | aggregate-only |")
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def import_drive_exports(
    *,
    manifest_db: Path = DEFAULT_MANIFEST_DB,
    download_dir: Path = DEFAULT_DOWNLOAD_DIR,
    corpus_root: Path = DEFAULT_CORPUS_ROOT,
    summary_path: Path = DEFAULT_SUMMARY,
    remote_label: str = "gdrive",
    rclone_bin: str = "rclone",
    import_source_name: str = DEFAULT_IMPORT_SOURCE,
    limit: int = 10,
    max_size_bytes: int | None = None,
    execute: bool = False,
    runner: Runner = _default_runner,
) -> DriveImportResult:
    """Import selected Drive ZIP exports into the local corpus with anonymized paths."""
    if limit < 1:
        raise ValueError("limit must be >= 1")
    download_dir.mkdir(parents=True, exist_ok=True)
    import_source_dir = corpus_root / import_source_name
    rows: list[ImportRowResult] = []

    with _connect_manifest(manifest_db) as conn:
        candidates = _load_candidates(conn, limit=limit, max_size_bytes=max_size_bytes)
        for candidate in candidates:
            if not execute:
                rows.append(
                    ImportRowResult(
                        file_id=candidate.file_id,
                        status="dry_run",
                        size_bytes=candidate.size_bytes,
                        extracted_text_files=0,
                    )
                )
                continue

            destination_zip = download_dir / f"{candidate.file_id}.zip"
            command = _download_command(
                candidate=candidate,
                remote_label=remote_label,
                rclone_bin=rclone_bin,
                destination_zip=destination_zip,
            )
            return_code = runner(command)
            if return_code != 0 or not destination_zip.exists():
                _update_status(
                    conn,
                    file_id=candidate.file_id,
                    status="failed",
                    imported_to_corpus=False,
                )
                rows.append(
                    ImportRowResult(
                        file_id=candidate.file_id,
                        status="failed",
                        size_bytes=candidate.size_bytes,
                        extracted_text_files=0,
                    )
                )
                continue

            extracted_text_files = _extract_chat_texts(
                zip_path=destination_zip,
                import_source_dir=import_source_dir,
                file_id=candidate.file_id,
            )
            status = "imported" if extracted_text_files else "no_text"
            _update_status(
                conn,
                file_id=candidate.file_id,
                status=status,
                imported_to_corpus=bool(extracted_text_files),
            )
            rows.append(
                ImportRowResult(
                    file_id=candidate.file_id,
                    status=status,
                    size_bytes=candidate.size_bytes,
                    extracted_text_files=extracted_text_files,
                )
            )
        conn.commit()

    _write_summary(
        summary_path=summary_path,
        rows=rows,
        execute=execute,
        import_source_name=import_source_name,
    )
    return DriveImportResult(
        selected_count=len(rows),
        downloaded_count=sum(1 for row in rows if row.status == "imported"),
        extracted_text_files=sum(row.extracted_text_files for row in rows),
        failed_count=sum(1 for row in rows if row.status == "failed"),
        summary_path=summary_path,
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import selected Drive WhatsApp ZIP exports into the local corpus."
    )
    parser.add_argument("--manifest-db", type=Path, default=DEFAULT_MANIFEST_DB)
    parser.add_argument("--download-dir", type=Path, default=DEFAULT_DOWNLOAD_DIR)
    parser.add_argument("--corpus-root", type=Path, default=DEFAULT_CORPUS_ROOT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--remote-label", default="gdrive")
    parser.add_argument("--rclone-bin", default="rclone")
    parser.add_argument("--import-source-name", default=DEFAULT_IMPORT_SOURCE)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--max-size-bytes", type=int)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually download and extract selected ZIPs. Default is dry-run.",
    )
    parser.add_argument("--json", action="store_true", help="Print aggregate counts as JSON.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = import_drive_exports(
            manifest_db=args.manifest_db,
            download_dir=args.download_dir,
            corpus_root=args.corpus_root,
            summary_path=args.summary,
            remote_label=args.remote_label,
            rclone_bin=args.rclone_bin,
            import_source_name=args.import_source_name,
            limit=args.limit,
            max_size_bytes=args.max_size_bytes,
            execute=args.execute,
        )
    except (FileNotFoundError, ValueError, TypeError, json.JSONDecodeError):
        print("ERROR: Drive import input is missing or invalid.", file=sys.stderr)
        return 1
    except (sqlite3.Error, OSError, zipfile.BadZipFile):
        print("ERROR: Drive import run failed safely.", file=sys.stderr)
        return 1
    except Exception:
        print("ERROR: Drive import run failed safely.", file=sys.stderr)
        return 1
    if args.json:
        sys.stdout.write(
            json.dumps(
                {
                    "downloaded_count": result.downloaded_count,
                    "extracted_text_files": result.extracted_text_files,
                    "failed_count": result.failed_count,
                    "selected_count": result.selected_count,
                },
                sort_keys=True,
            )
            + "\n"
        )
    return 0 if result.failed_count == 0 else 1


def _fmt_int(value: int) -> str:
    return f"{value:,}"


if __name__ == "__main__":
    raise SystemExit(main())
