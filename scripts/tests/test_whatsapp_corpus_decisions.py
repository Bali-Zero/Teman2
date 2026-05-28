from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.whatsapp_corpus.compile_review_decisions import (
    compile_review_decisions,
    read_review_manifest,
)


def write_manifest(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            [
                "rank",
                "file_id",
                "source",
                "source_tag",
                "path_hash",
                "classification_label",
                "privacy_tier",
                "processing_gate",
                "message_start_count",
                "normalized_message_start_count",
                "min_timestamp",
                "max_timestamp",
                "confidence",
                "resolution_status",
                "local_path",
                "evidence_codes",
                "warning_codes",
                "owner_decision",
                "owner_notes",
            ]
        )
        writer.writerow(
            [
                1,
                "wa-file-0001",
                "02_zip-extracted",
                "tag-private",
                "hash-private",
                "team_operator_archive_candidate",
                "team_sensitive",
                "local_only_team_analysis_after_owner_approval",
                20,
                22,
                "",
                "",
                "0.78",
                "resolved",
                "/tmp/PrivateTeam/_chat.txt",
                "source:zip_extracted",
                "",
                "",
                "",
            ]
        )
        writer.writerow(
            [
                2,
                "wa-file-0002",
                "03_drive-icloud",
                "",
                "hash-family",
                "private_drive_icloud_candidate",
                "personal_sensitive",
                "deny_content_mining_until_owner_allowlist",
                10,
                15,
                "",
                "",
                "0.86",
                "resolved",
                "/tmp/FamilyPrivate.txt",
                "source:drive_icloud",
                "",
                "",
                "",
            ]
        )
        writer.writerow(
            [
                3,
                "wa-file-0003",
                "02_zip-extracted",
                "tag-private",
                "hash-hold",
                "bulk_drive_export_candidate",
                "mixed_sensitive",
                "manual_review_before_content_mining",
                5,
                5,
                "",
                "",
                "0.72",
                "resolved",
                "/tmp/PrivateBulk/_chat.txt",
                "source:zip_extracted",
                "",
                "",
                "",
            ]
        )


def test_compile_review_decisions_applies_conservative_defaults(tmp_path: Path) -> None:
    manifest = tmp_path / "review_manifest.local.tsv"
    output_dir = tmp_path / "decisions"
    write_manifest(manifest)

    rows = compile_review_decisions(
        review_manifest_path=manifest,
        output_dir=output_dir,
        apply_safe_defaults=True,
    )

    assert [row.effective_decision for row in rows] == [
        "allow_team_local",
        "deny_personal",
        "unknown_hold",
    ]
    allowlist = (output_dir / "content_allowlist.local.jsonl").read_text(encoding="utf-8")
    denylist = (output_dir / "content_denylist.local.jsonl").read_text(encoding="utf-8")
    holdlist = (output_dir / "content_holdlist.local.jsonl").read_text(encoding="utf-8")
    assert json.loads(allowlist)["file_id"] == "wa-file-0001"
    assert json.loads(denylist)["file_id"] == "wa-file-0002"
    assert json.loads(holdlist)["file_id"] == "wa-file-0003"


def test_summary_does_not_include_raw_paths(tmp_path: Path) -> None:
    manifest = tmp_path / "review_manifest.local.tsv"
    output_dir = tmp_path / "decisions"
    write_manifest(manifest)

    compile_review_decisions(
        review_manifest_path=manifest,
        output_dir=output_dir,
        apply_safe_defaults=True,
    )

    summary = (output_dir / "review_decisions_summary.md").read_text(encoding="utf-8")
    assert "PrivateTeam" not in summary
    assert "FamilyPrivate" not in summary
    assert "PrivateBulk" not in summary
    assert "/tmp/" not in summary
    assert "allow_team_local" in summary


def test_blank_decisions_hold_without_safe_defaults(tmp_path: Path) -> None:
    manifest = tmp_path / "review_manifest.local.tsv"
    output_dir = tmp_path / "decisions"
    write_manifest(manifest)

    rows = compile_review_decisions(
        review_manifest_path=manifest,
        output_dir=output_dir,
        apply_safe_defaults=False,
    )

    assert {row.effective_decision for row in rows} == {"unknown_hold"}
    assert len(read_review_manifest(manifest)) == 3
