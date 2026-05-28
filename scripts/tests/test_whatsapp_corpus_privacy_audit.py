"""Tests for the WhatsApp corpus privacy output audit CLI.

Fixtures are synthetic and live in temporary repositories only; no real
WhatsApp export or local corpus file is read.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_SCRIPT = REPO_ROOT / "scripts" / "whatsapp_corpus" / "audit_privacy_outputs.py"
WA_ROOT = Path("research/personal/wa-corpus")


def _run_git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _write(repo: Path, rel_path: Path | str, content: str) -> Path:
    path = repo / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def fixture_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(repo, "init", "-b", "main")
    return repo


def _track(repo: Path, *paths: Path | str) -> None:
    _run_git(repo, "add", *(str(path) for path in paths))


def _run_audit(repo: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(AUDIT_SCRIPT), "--repo", str(repo), *extra_args],
        check=False,
        capture_output=True,
        text=True,
    )


def test_clean_tracked_report_exits_zero(fixture_repo: Path) -> None:
    report = _write(
        fixture_repo,
        WA_ROOT / "summary.md",
        "# Synthetic summary\n\nAggregate counts only.\n",
    )
    _track(fixture_repo, report.relative_to(fixture_repo))

    result = _run_audit(fixture_repo)

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_detects_leaks_without_printing_matched_content(fixture_repo: Path) -> None:
    report = _write(
        fixture_repo,
        WA_ROOT / "review.md",
        "Synthetic fixture with +628123456789 and Bebe in the same line.\n",
    )
    _track(fixture_repo, report.relative_to(fixture_repo))

    result = _run_audit(fixture_repo)

    assert result.returncode == 1
    output_lines = result.stdout.splitlines()
    assert output_lines == [
        "research/personal/wa-corpus/review.md\traw_international_phone",
        "research/personal/wa-corpus/review.md\tphone_prefix_62",
        "research/personal/wa-corpus/review.md\tname_bebe",
    ]
    assert "+62" not in result.stdout
    assert "Bebe" not in result.stdout
    assert "Synthetic fixture" not in result.stdout


@pytest.mark.parametrize(
    ("marker", "label"),
    [
        ("/Users/nuzantara/Desktop/wa-chats", "wa_corpus_path"),
        ("/Users/nuzantara/Desktop/wa-corpus/analysis", "wa_corpus_path"),
        ("~/Desktop/whatsapp-exports/group-a/chat.txt", "wa_corpus_path"),
        ("wa-chats/private-export/chat.txt", "wa_corpus_path"),
        ("privacy@example.com", "email_address"),
        ("+1 415 555 0100", "raw_international_phone"),
        ("0062 812 3456 7890", "raw_international_phone"),
        ("6281234567890", "raw_international_phone"),
        ("A12345678", "passport_like_id"),
        ("AB1234567", "passport_like_id"),
        ("1234567890123", "long_digit_id"),
        ("https://example.com/private-report", "raw_url"),
        ("https://drive.google.com/file/d/abc123/view", "drive_link"),
        ("docs.google.com/document/d/abc123/edit", "drive_link"),
        ("+62", "phone_prefix_62"),
        ("Bebe", "name_bebe"),
        ("Adit", "name_adit"),
        ("Ari", "name_ari"),
        ("Krisna", "name_krisna"),
        ("Sahira", "name_sahira"),
        ("Surya", "name_surya"),
        ("GoogleDrive", "google_drive"),
        ("Papa", "name_papa"),
        ("Antonello", "name_antonello"),
        ("Siano", "name_siano"),
    ],
)
def test_detects_each_configured_pattern(
    fixture_repo: Path,
    marker: str,
    label: str,
) -> None:
    report = _write(
        fixture_repo,
        WA_ROOT / "pattern.md",
        f"Synthetic fixture marker: {marker}\n",
    )
    _track(fixture_repo, report.relative_to(fixture_repo))

    result = _run_audit(fixture_repo)

    assert result.returncode == 1
    assert result.stdout.strip() == f"research/personal/wa-corpus/pattern.md\t{label}"


def test_allows_local_anonymized_ids_dates_tables_and_code_identifiers(
    fixture_repo: Path,
) -> None:
    report = _write(
        fixture_repo,
        WA_ROOT / "allowed.md",
        "\n".join(
            [
                "| local_id | tag | date | code_identifier |",
                "| --- | --- | --- | --- |",
                "| wa-file-0579 | tag-123456789012 | 2026-05-26 | CASE_ID_1234567890 |",
                "Repo-local report path: research/personal/wa-corpus/analysis/README.md.",
                "Compact date fixture: 20260526.",
                "Compact datetime fixture: 202605260915.",
                "Code-like passport fixture: CASE_A1234567.",
                "Code-like URL fixture: HTTP_CLIENT_IDENTIFIER.",
            ]
        ),
    )
    _track(fixture_repo, report.relative_to(fixture_repo))

    result = _run_audit(fixture_repo)

    assert result.returncode == 0
    assert result.stdout == ""


def test_ignores_local_db_and_pycache_files_even_if_tracked(fixture_repo: Path) -> None:
    ignored_paths = [
        WA_ROOT / ".local.jsonl",
        WA_ROOT / "summary.local.jsonl",
        WA_ROOT / "export.sqlite",
        WA_ROOT / "cache.db",
        WA_ROOT / "__pycache__" / "cached.md",
    ]
    for rel_path in ignored_paths:
        _write(fixture_repo, rel_path, "Synthetic fixture with Antonello and +62.\n")
    _track(fixture_repo, *ignored_paths)

    result = _run_audit(fixture_repo)

    assert result.returncode == 0
    assert result.stdout == ""


def test_untracked_reports_are_not_scanned_when_git_is_available(
    fixture_repo: Path,
) -> None:
    clean_report = _write(
        fixture_repo,
        WA_ROOT / "tracked.md",
        "# Synthetic summary\n\nNo sensitive fixture markers.\n",
    )
    _write(
        fixture_repo,
        WA_ROOT / "untracked.md",
        "Synthetic fixture with /Users/nuzantara/Desktop/wa-chats.\n",
    )
    _track(fixture_repo, clean_report.relative_to(fixture_repo))

    result = _run_audit(fixture_repo)

    assert result.returncode == 0
    assert result.stdout == ""


def test_include_untracked_scans_filesystem_files_under_target(
    fixture_repo: Path,
) -> None:
    clean_report = _write(
        fixture_repo,
        WA_ROOT / "tracked.md",
        "# Synthetic summary\n\nNo sensitive fixture markers.\n",
    )
    _write(
        fixture_repo,
        WA_ROOT / "untracked.md",
        "Synthetic fixture with privacy@example.com.\n",
    )
    _track(fixture_repo, clean_report.relative_to(fixture_repo))

    result = _run_audit(fixture_repo, "--include-untracked")

    assert result.returncode == 1
    assert result.stdout.strip() == (
        "research/personal/wa-corpus/untracked.md\temail_address"
    )


def test_scans_filesystem_when_repo_is_not_git(tmp_path: Path) -> None:
    repo = tmp_path / "plain"
    report = _write(
        repo,
        WA_ROOT / "plain.md",
        "Synthetic fixture with GoogleDrive.\n",
    )

    result = _run_audit(repo)

    assert result.returncode == 1
    assert result.stdout.strip() == (
        f"{report.relative_to(repo).as_posix()}\tgoogle_drive"
    )
