from __future__ import annotations

import subprocess
import shutil
import sqlite3
import sys
import zipfile
from pathlib import Path

from scripts.whatsapp_corpus.build_drive_export_manifest import build_drive_export_manifest
from scripts.whatsapp_corpus.import_drive_exports import import_drive_exports


def _write_manifest(tmp_path: Path, *, drive_id: str | None = "drive-file-secret") -> Path:
    lsjson = tmp_path / "drive_lsjson.local.json"
    output_db = tmp_path / "drive_export_manifest.local.sqlite"
    summary = tmp_path / "drive_export_manifest_summary.md"
    id_fragment = f', "ID": "{drive_id}"' if drive_id else ""
    lsjson.write_text(
        "["
        "{"
        '"Path": "Private Clients/WhatsApp Chat - VeryPrivateClient.zip",'
        '"Name": "WhatsApp Chat - VeryPrivateClient.zip",'
        '"Size": 1024,'
        '"IsDir": false'
        f"{id_fragment}"
        "}"
        "]",
        encoding="utf-8",
    )
    build_drive_export_manifest(
        lsjson_path=lsjson,
        output_db=output_db,
        summary_path=summary,
        remote_label="gdrive",
    )
    return output_db


def test_dry_run_writes_safe_summary_without_downloading(tmp_path: Path) -> None:
    manifest_db = _write_manifest(tmp_path)
    summary = tmp_path / "drive_import_summary.md"
    called: list[list[str]] = []

    result = import_drive_exports(
        manifest_db=manifest_db,
        download_dir=tmp_path / "downloads.local",
        corpus_root=tmp_path / "corpus",
        summary_path=summary,
        execute=False,
        runner=lambda command: called.append(command) or 0,
    )

    assert result.selected_count == 1
    assert result.downloaded_count == 0
    assert result.extracted_text_files == 0
    assert called == []

    rendered = summary.read_text(encoding="utf-8")
    assert "VeryPrivateClient" not in rendered
    assert "Private Clients" not in rendered
    assert "drive-file-secret" not in rendered
    assert "drive-wa-0001" in rendered
    assert "dry_run" in rendered

    with sqlite3.connect(manifest_db) as conn:
        row = conn.execute(
            "SELECT download_status, imported_to_corpus FROM drive_export_candidates"
        ).fetchone()
    assert row == ("pending", 0)


def test_import_by_drive_id_uses_copyid_and_extracts_sanitized_txt(tmp_path: Path) -> None:
    manifest_db = _write_manifest(tmp_path)
    source_zip = tmp_path / "source.zip"
    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr(
            "WhatsApp Chat with Secret Person.txt",
            "[01/06/26, 08.00.00] Secret Person: raw local message\n",
        )
        archive.writestr("Secret Person.jpg", b"not imported")

    commands: list[list[str]] = []

    def fake_runner(command: list[str]) -> int:
        commands.append(command)
        shutil.copyfile(source_zip, command[-1])
        return 0

    result = import_drive_exports(
        manifest_db=manifest_db,
        download_dir=tmp_path / "downloads.local",
        corpus_root=tmp_path / "corpus",
        summary_path=tmp_path / "drive_import_summary.md",
        execute=True,
        runner=fake_runner,
    )

    assert result.selected_count == 1
    assert result.downloaded_count == 1
    assert result.extracted_text_files == 1
    assert commands == [
        [
            "rclone",
            "backend",
            "copyid",
            "gdrive:",
            "drive-file-secret",
            str(tmp_path / "downloads.local" / "drive-wa-0001.zip"),
        ]
    ]

    imported = tmp_path / "corpus" / "03_drive-imports" / "drive-wa-0001" / "chat-0001.txt"
    assert imported.read_text(encoding="utf-8") == (
        "[01/06/26, 08.00.00] Secret Person: raw local message\n"
    )
    assert not list((tmp_path / "corpus").rglob("*Secret*"))

    with sqlite3.connect(manifest_db) as conn:
        row = conn.execute(
            "SELECT download_status, imported_to_corpus FROM drive_export_candidates"
        ).fetchone()
    assert row == ("imported", 1)


def test_import_without_drive_id_falls_back_to_copyto(tmp_path: Path) -> None:
    manifest_db = _write_manifest(tmp_path, drive_id=None)
    source_zip = tmp_path / "source.zip"
    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr("_chat.txt", "[01/06/26, 08.00.00] Person: body\n")

    commands: list[list[str]] = []

    def fake_runner(command: list[str]) -> int:
        commands.append(command)
        shutil.copyfile(source_zip, command[-1])
        return 0

    import_drive_exports(
        manifest_db=manifest_db,
        download_dir=tmp_path / "downloads.local",
        corpus_root=tmp_path / "corpus",
        summary_path=tmp_path / "drive_import_summary.md",
        execute=True,
        runner=fake_runner,
    )

    assert commands[0][:3] == ["rclone", "copyto", "gdrive:Private Clients/WhatsApp Chat - VeryPrivateClient.zip"]


def test_cli_error_is_sanitized_for_unexpected_manifest_name(tmp_path: Path) -> None:
    wrong_db = tmp_path / "wrong_manifest_should_not_leak.local.sqlite"
    wrong_db.write_bytes(b"")
    download_dir = tmp_path / "downloads.local"
    corpus_root = tmp_path / "corpus"
    summary = tmp_path / "drive_import_summary.md"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.whatsapp_corpus.import_drive_exports",
            "--manifest-db",
            str(wrong_db),
            "--download-dir",
            str(download_dir),
            "--corpus-root",
            str(corpus_root),
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
    assert result.stderr == "ERROR: Drive import input is missing or invalid.\n"
    forbidden_markers = [
        str(tmp_path),
        str(wrong_db),
        wrong_db.name,
        str(download_dir),
        str(corpus_root),
        str(summary),
        "Traceback",
        ".sqlite",
    ]
    for marker in forbidden_markers:
        assert marker not in result.stderr
