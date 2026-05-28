from __future__ import annotations

import csv
from pathlib import Path

import pytest

from scripts.whatsapp_corpus.compile_case_window_actions import (
    compile_case_window_actions,
)


def _write_workbook(path: Path, rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            [
                "review_status",
                "owner_decision",
                "action_type",
                "priority",
                "action_owner",
                "due_date",
                "owner_notes",
                "rank",
                "window_id",
                "file_id",
                "window_ordinal",
                "first_month",
                "last_month",
                "first_message_index",
                "last_message_index",
                "event_count",
                "message_count",
                "domain_count",
                "dominant_domain",
                "severity_high_count",
                "review_score",
                "review_reasons",
                "top_event_codes_json",
            ]
        )
        writer.writerows(rows)


def test_compile_case_window_actions_only_approved_rows(tmp_path: Path) -> None:
    workbook = tmp_path / "case_window_review_workbook.local.tsv"
    actions = tmp_path / "case_window_actions.local.tsv"
    summary = tmp_path / "case_window_actions_summary.md"
    _write_workbook(
        workbook,
        [
            [
                "reviewed",
                "approve",
                "",
                "P1",
                "ops",
                "2026-06-01",
                "keep local only",
                1,
                "window-a",
                "wa-file-0001",
                1,
                "2026-05",
                "2026-05",
                10,
                20,
                30,
                11,
                3,
                "followup_risk",
                2,
                99,
                "followup_dominant",
                "[]",
            ],
            [
                "reviewed",
                "hold",
                "document_chase",
                "P2",
                "",
                "",
                "do not action yet",
                2,
                "window-b",
                "wa-file-0002",
                1,
                "2026-05",
                "2026-05",
                5,
                7,
                8,
                3,
                1,
                "document_requirement",
                0,
                21,
                "document_dominant",
                "[]",
            ],
        ],
    )

    result = compile_case_window_actions(
        workbook_path=workbook,
        actions_path=actions,
        summary_path=summary,
    )

    assert len(result.workbook_rows) == 2
    assert len(result.action_rows) == 1
    assert result.action_rows[0].action_type == "crm_followup"
    assert result.action_rows[0].priority == "P1"

    actions_text = actions.read_text(encoding="utf-8")
    assert "wa-action-" in actions_text
    assert "window-a" in actions_text
    assert "window-b" not in actions_text
    assert "keep local only" in actions_text

    summary_text = summary.read_text(encoding="utf-8")
    assert "Approved action rows | 1" in summary_text
    assert "crm_followup" in summary_text
    assert "keep local only" not in summary_text
    assert "do not action yet" not in summary_text


def test_compile_case_window_actions_rejects_invalid_decision(tmp_path: Path) -> None:
    workbook = tmp_path / "case_window_review_workbook.local.tsv"
    actions = tmp_path / "case_window_actions.local.tsv"
    summary = tmp_path / "case_window_actions_summary.md"
    _write_workbook(
        workbook,
        [
            [
                "reviewed",
                "yes",
                "",
                "P2",
                "",
                "",
                "",
                1,
                "window-a",
                "wa-file-0001",
                1,
                "2026-05",
                "2026-05",
                10,
                20,
                30,
                11,
                3,
                "followup_risk",
                2,
                99,
                "followup_dominant",
                "[]",
            ],
        ],
    )

    with pytest.raises(ValueError, match="Invalid owner_decision"):
        compile_case_window_actions(
            workbook_path=workbook,
            actions_path=actions,
            summary_path=summary,
        )
