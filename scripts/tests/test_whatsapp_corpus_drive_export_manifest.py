from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from scripts.whatsapp_corpus.build_drive_export_manifest import (
    build_drive_export_manifest,
)


def _write_lsjson(path: Path) -> None:
    records = [
        {
            "Path": "Private Clients/WhatsApp Chat - VeryPrivateClient.zip",
            "Name": "WhatsApp Chat - VeryPrivateClient.zip",
            "Size": 1024,
            "ModTime": "2026-06-01T10:00:00Z",
            "MimeType": "application/zip",
            "IsDir": False,
            "ID": "drive-file-secret-alpha",
        },
        {
            "Path": "Private Clients/not-a-chat.zip",
            "Name": "not-a-chat.zip",
            "Size": 512,
            "ModTime": "2026-06-01T10:10:00Z",
            "MimeType": "application/zip",
            "IsDir": False,
            "ID": "drive-file-secret-beta",
        },
        {
            "Path": "Archive/whatsapp chat - CompanyOps.zip",
            "Name": "whatsapp chat - CompanyOps.zip",
            "Size": 2048,
            "ModTime": "2026-06-02T11:00:00Z",
            "MimeType": "application/octet-stream",
            "IsDir": False,
            "ID": "drive-file-secret-gamma",
        },
        {
            "Path": "Archive/WhatsApp Chat - Folder",
            "Name": "WhatsApp Chat - Folder",
            "Size": 0,
            "ModTime": "2026-06-02T11:00:00Z",
            "MimeType": "inode/directory",
            "IsDir": True,
            "ID": "drive-folder-secret",
        },
    ]
    path.write_text(json.dumps(records), encoding="utf-8")


def test_build_drive_export_manifest_writes_local_db_and_safe_summary(tmp_path: Path) -> None:
    lsjson = tmp_path / "drive_lsjson.local.json"
    output_db = tmp_path / "drive_export_manifest.local.sqlite"
    summary = tmp_path / "drive_export_manifest_summary.md"
    _write_lsjson(lsjson)

    result = build_drive_export_manifest(
        lsjson_path=lsjson,
        output_db=output_db,
        summary_path=summary,
        remote_label="gdrive",
    )

    assert result.scanned_records == 4
    assert result.candidate_count == 2
    assert result.total_size_bytes == 3072

    with sqlite3.connect(output_db) as conn:
        rows = conn.execute(
            """
            SELECT file_id, candidate_kind, raw_path, path_hash, drive_id_hash
            FROM drive_export_candidates
            ORDER BY file_id
            """
        ).fetchall()
    assert rows[0][0] == "drive-wa-0001"
    assert rows[0][1] == "whatsapp_chat_zip"
    assert rows[0][2] == "Private Clients/WhatsApp Chat - VeryPrivateClient.zip"
    assert rows[0][3]
    assert rows[0][4]
    assert rows[1][0] == "drive-wa-0002"

    rendered = summary.read_text(encoding="utf-8")
    assert "VeryPrivateClient" not in rendered
    assert "CompanyOps" not in rendered
    assert "drive-file-secret" not in rendered
    assert "Private Clients" not in rendered
    assert "3,072" in rendered
    assert "drive-wa-0001" in rendered
    assert "whatsapp_chat_zip" in rendered


def test_cli_writes_json_counts_without_raw_drive_names(tmp_path: Path) -> None:
    lsjson = tmp_path / "drive_lsjson.local.json"
    output_db = tmp_path / "drive_export_manifest.local.sqlite"
    summary = tmp_path / "drive_export_manifest_summary.md"
    _write_lsjson(lsjson)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.whatsapp_corpus.build_drive_export_manifest",
            "--lsjson",
            str(lsjson),
            "--output-db",
            str(output_db),
            "--summary",
            str(summary),
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload == {
        "candidate_count": 2,
        "scanned_records": 4,
        "total_size_bytes": 3072,
    }
    assert "VeryPrivateClient" not in result.stdout
    assert "drive-file-secret" not in result.stdout


def test_cli_error_is_sanitized_for_missing_lsjson(tmp_path: Path) -> None:
    missing_lsjson = tmp_path / "VeryPrivateClient_drive_lsjson.local.json"
    output_db = tmp_path / "drive_export_manifest.local.sqlite"
    summary = tmp_path / "drive_export_manifest_summary.md"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.whatsapp_corpus.build_drive_export_manifest",
            "--lsjson",
            str(missing_lsjson),
            "--output-db",
            str(output_db),
            "--summary",
            str(summary),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "ERROR: Drive export manifest input is missing or invalid.\n"
    forbidden_markers = [
        str(tmp_path),
        str(missing_lsjson),
        missing_lsjson.name,
        str(output_db),
        str(summary),
        "Traceback",
        ".json",
        ".sqlite",
    ]
    for marker in forbidden_markers:
        assert marker not in result.stderr


def test_manifest_allows_duplicate_names_when_drive_ids_differ(tmp_path: Path) -> None:
    lsjson = tmp_path / "drive_lsjson.local.json"
    output_db = tmp_path / "drive_export_manifest.local.sqlite"
    summary = tmp_path / "drive_export_manifest_summary.md"
    records = [
        {
            "Path": "WhatsApp Chat - Duplicate.zip",
            "Name": "WhatsApp Chat - Duplicate.zip",
            "Size": 100,
            "IsDir": False,
            "ID": "drive-file-duplicate-a",
        },
        {
            "Path": "WhatsApp Chat - Duplicate.zip",
            "Name": "WhatsApp Chat - Duplicate.zip",
            "Size": 200,
            "IsDir": False,
            "ID": "drive-file-duplicate-b",
        },
    ]
    lsjson.write_text(json.dumps(records), encoding="utf-8")

    result = build_drive_export_manifest(
        lsjson_path=lsjson,
        output_db=output_db,
        summary_path=summary,
        remote_label="gdrive",
    )

    assert result.candidate_count == 2
    with sqlite3.connect(output_db) as conn:
        path_hashes = [
            row[0]
            for row in conn.execute(
                "SELECT path_hash FROM drive_export_candidates ORDER BY file_id"
            )
        ]
    assert len(set(path_hashes)) == 2


def test_summary_formats_large_numbers_with_separators(tmp_path: Path) -> None:
    lsjson = tmp_path / "drive_lsjson.local.json"
    output_db = tmp_path / "drive_export_manifest.local.sqlite"
    summary = tmp_path / "drive_export_manifest_summary.md"
    records = [
        {
            "Path": "WhatsApp Chat - BigExport.zip",
            "Name": "WhatsApp Chat - BigExport.zip",
            "Size": 7567964172,
            "IsDir": False,
            "ID": "drive-file-big-export",
        },
    ]
    lsjson.write_text(json.dumps(records), encoding="utf-8")

    build_drive_export_manifest(
        lsjson_path=lsjson,
        output_db=output_db,
        summary_path=summary,
        remote_label="gdrive",
    )

    rendered = summary.read_text(encoding="utf-8")
    assert "7567964172" not in rendered
    assert "7,567,964,172" in rendered
