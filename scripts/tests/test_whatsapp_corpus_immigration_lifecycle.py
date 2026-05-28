from __future__ import annotations

import importlib.util
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "whatsapp_corpus" / "analyze_immigration_lifecycle.py"


def _load_lifecycle_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("immigration_lifecycle", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_messages_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE parsed_messages (
                file_id TEXT NOT NULL,
                source_tag TEXT,
                message_index INTEGER NOT NULL,
                timestamp TEXT,
                body_text TEXT,
                is_system_event INTEGER NOT NULL
            );
            """
        )
        conn.executemany(
            """
            INSERT INTO parsed_messages (
                file_id, source_tag, message_index, timestamp, body_text, is_system_event
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "wa-file-0001",
                    "tag-fixture",
                    1,
                    "2026-05-01T09:00:00+00:00",
                    "Hello, I need help with visa requirements for raw-name Fixture.",
                    0,
                ),
                (
                    "wa-file-0001",
                    "tag-fixture",
                    2,
                    "2026-05-01T10:00:00+00:00",
                    "Passport A1234567 scan and photo sent from fixture@example.com.",
                    0,
                ),
                (
                    "wa-file-0001",
                    "tag-fixture",
                    3,
                    "2026-05-01T11:00:00+00:00",
                    "Company sponsor PT PMA director NIB for KITAS application submitted.",
                    0,
                ),
                (
                    "wa-file-0001",
                    "tag-fixture",
                    4,
                    "2026-05-02T09:00:00+00:00",
                    "Biometric appointment scheduled at immigration office.",
                    0,
                ),
                (
                    "wa-file-0001",
                    "tag-fixture",
                    5,
                    "2026-05-03T09:00:00+00:00",
                    "Approval issued, visa ready for pickup.",
                    0,
                ),
                (
                    "wa-file-0001",
                    "tag-fixture",
                    6,
                    "2026-06-01T09:00:00+00:00",
                    "Renewal expiry is urgent, problem with +62 812 3456 7890.",
                    0,
                ),
                (
                    "wa-file-0001",
                    "tag-fixture",
                    7,
                    "2026-06-01T10:00:00+00:00",
                    "System event fixture with urgent passport words.",
                    1,
                ),
            ],
        )
        conn.commit()


def _write_candidates_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE extracted_candidates (
                file_id TEXT NOT NULL,
                source_tag TEXT,
                message_index INTEGER NOT NULL,
                timestamp TEXT,
                sender_hash TEXT,
                category_code TEXT NOT NULL,
                evidence_code TEXT NOT NULL,
                body_hash TEXT,
                value_hash TEXT
            );
            """
        )
        conn.executemany(
            """
            INSERT INTO extracted_candidates (
                file_id, source_tag, message_index, timestamp, sender_hash,
                category_code, evidence_code, body_hash, value_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "wa-file-0001",
                    "tag-fixture",
                    2,
                    "2026-05-01T10:00:00+00:00",
                    "sender-hash",
                    "identity_document",
                    "passport_like_hash",
                    "body-hash-fixture",
                    "A1234567",
                ),
                (
                    "wa-file-0001",
                    "tag-fixture",
                    3,
                    "2026-05-01T11:00:00+00:00",
                    "sender-hash",
                    "company_case",
                    "category_keyword",
                    "body-hash-fixture",
                    None,
                ),
                (
                    "wa-file-0001",
                    "tag-fixture",
                    3,
                    "2026-05-01T11:00:00+00:00",
                    "sender-hash",
                    "visa_case",
                    "category_keyword",
                    "body-hash-fixture",
                    None,
                ),
                (
                    "wa-file-0001",
                    "tag-fixture",
                    6,
                    "2026-06-01T09:00:00+00:00",
                    "sender-hash",
                    "urgency_case",
                    "category_keyword",
                    "body-hash-fixture",
                    None,
                ),
            ],
        )
        conn.commit()


def _write_signal_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE signal_hits (
                file_id TEXT NOT NULL,
                source_tag TEXT,
                message_index INTEGER NOT NULL,
                timestamp TEXT,
                signal_code TEXT NOT NULL
            );
            """
        )
        conn.executemany(
            """
            INSERT INTO signal_hits
                (file_id, source_tag, message_index, timestamp, signal_code)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    "wa-file-0001",
                    "tag-fixture",
                    2,
                    "2026-05-01T10:00:00+00:00",
                    "identity_document",
                ),
                (
                    "wa-file-0001",
                    "tag-fixture",
                    3,
                    "2026-05-01T11:00:00+00:00",
                    "company_corporate",
                ),
                (
                    "wa-file-0001",
                    "tag-fixture",
                    3,
                    "2026-05-01T11:00:00+00:00",
                    "immigration",
                ),
                (
                    "wa-file-0001",
                    "tag-fixture",
                    4,
                    "2026-05-02T09:00:00+00:00",
                    "immigration",
                ),
                (
                    "wa-file-0001",
                    "tag-fixture",
                    6,
                    "2026-06-01T09:00:00+00:00",
                    "urgency_risk",
                ),
            ],
        )
        conn.commit()


@pytest.fixture
def synthetic_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    messages_db = tmp_path / "allowed_messages.local.sqlite"
    candidates_db = tmp_path / "allowed_candidates.local.sqlite"
    signal_db = tmp_path / "allowed_signal_hits.local.sqlite"
    _write_messages_db(messages_db)
    _write_candidates_db(candidates_db)
    _write_signal_db(signal_db)
    return messages_db, candidates_db, signal_db


def _fetch_one(db_path: Path, query: str, params: tuple[object, ...]) -> sqlite3.Row:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(query, params).fetchone()
    finally:
        conn.close()
    assert row is not None
    return row


def test_cli_writes_lifecycle_db_and_safe_summary(
    synthetic_inputs: tuple[Path, Path, Path],
    tmp_path: Path,
) -> None:
    messages_db, candidates_db, signal_db = synthetic_inputs
    output_db = tmp_path / "allowed_immigration_lifecycle.local.sqlite"
    summary = tmp_path / "allowed_immigration_lifecycle_summary.md"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--messages-db",
            str(messages_db),
            "--candidates-db",
            str(candidates_db),
            "--signal-db",
            str(signal_db),
            "--output-db",
            str(output_db),
            "--summary",
            str(summary),
            "--summary-limit",
            "20",
            "--generated-at-utc",
            "2026-05-26T00:00:00+00:00",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert '"classified_message_count": 6' in result.stdout
    assert output_db.exists()
    assert summary.exists()

    identity_total = _fetch_one(
        output_db,
        """
        SELECT hit_count, message_count, file_count
        FROM stage_totals
        WHERE stage_code = ?
        """,
        ("identity_passport",),
    )
    assert dict(identity_total) == {"hit_count": 4, "message_count": 1, "file_count": 1}

    problem_message = _fetch_one(
        output_db,
        """
        SELECT primary_stage_code, stage_count, evidence_count
        FROM message_stage_summary
        WHERE message_index = ?
        """,
        (6,),
    )
    assert dict(problem_message) == {
        "primary_stage_code": "problem_escalation",
        "stage_count": 2,
        "evidence_count": 4,
    }

    transition = _fetch_one(
        output_db,
        """
        SELECT transition_count, file_count
        FROM primary_stage_transitions
        WHERE from_stage_code = ? AND to_stage_code = ?
        """,
        ("appointment_biometric", "approval_issuance"),
    )
    assert dict(transition) == {"transition_count": 1, "file_count": 1}

    columns = {
        row[0]
        for row in sqlite3.connect(output_db)
        .execute("SELECT name FROM pragma_table_info('stage_hits')")
        .fetchall()
    }
    assert "body_text" not in columns
    assert "sender_raw" not in columns
    assert "value_hash" not in columns

    summary_text = summary.read_text(encoding="utf-8")
    assert "A1234567" not in summary_text
    assert "fixture@example.com" not in summary_text
    assert "+62" not in summary_text
    assert "raw-name Fixture" not in summary_text
    assert "body-hash-fixture" not in summary_text
    assert "identity_passport" in summary_text
    assert "problem_escalation" in summary_text


def test_artifact_builder_classifies_from_feature_codes_without_raw_values(
    synthetic_inputs: tuple[Path, Path, Path],
) -> None:
    module = _load_lifecycle_module()
    messages_db, candidates_db, signal_db = synthetic_inputs

    messages = module.read_messages(messages_db)
    candidate_features = module.read_candidate_features(candidates_db)
    signal_features = module.read_signal_features(signal_db)
    artifacts = module.build_artifacts(messages, candidate_features, signal_features)

    assert artifacts.input_message_count == 7
    assert artifacts.skipped_system_event_count == 1
    assert artifacts.classified_message_count == 6
    assert {row["stage_code"] for row in artifacts.stage_totals} == {
        "lead_intake",
        "identity_passport",
        "sponsor_company",
        "application_submission",
        "appointment_biometric",
        "approval_issuance",
        "extension_renewal_expiry",
        "problem_escalation",
    }
    assert all("A1234567" not in feature.code for feature in candidate_features)
    assert all(
        "body-hash-fixture" not in feature.code for feature in candidate_features
    )


def test_input_filename_guard_rejects_unexpected_messages_db(tmp_path: Path) -> None:
    module = _load_lifecycle_module()
    blocked_db = tmp_path / "not_allowed.local.sqlite"
    blocked_db.write_bytes(b"")

    with pytest.raises(ValueError, match="Refusing to read"):
        module.run_analysis(
            messages_db=blocked_db,
            candidates_db=tmp_path / "allowed_candidates.local.sqlite",
            signal_db=tmp_path / "allowed_signal_hits.local.sqlite",
            output_db=tmp_path / "allowed_immigration_lifecycle.local.sqlite",
            summary_path=tmp_path / "allowed_immigration_lifecycle_summary.md",
            summary_limit=10,
            generated_at_utc="2026-05-26T00:00:00+00:00",
        )
