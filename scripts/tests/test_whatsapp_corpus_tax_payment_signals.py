from __future__ import annotations

import importlib.util
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "whatsapp_corpus" / "extract_tax_payment_signals.py"


def _load_tax_payment() -> ModuleType:
    spec = importlib.util.spec_from_file_location("tax_payment_signals", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def synthetic_messages_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "allowed_messages.local.sqlite"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE parsed_messages (
                file_id TEXT NOT NULL,
                source_tag TEXT,
                message_index INTEGER NOT NULL,
                timestamp TEXT,
                sender_hash TEXT,
                body_text TEXT NOT NULL
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO parsed_messages (
                file_id, source_tag, message_index, timestamp, sender_hash, body_text
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "wa-file-test-1",
                    "synthetic-source",
                    1,
                    "2026-05-26T10:00:00+00:00",
                    "senderhash1",
                    (
                        "Tax accounting monthly VAT report is due 31/05/2026. "
                        "Please pay invoice INV-2026-ZERO by deadline, penalty applies. "
                        "Amount Rp 1.500.000 and NIB docs are attached."
                    ),
                ),
                (
                    "wa-file-test-1",
                    "synthetic-source",
                    2,
                    "2026-05-27T10:00:00+00:00",
                    "senderhash2",
                    (
                        "Payroll BPJS and PPh 21 salary report. "
                        "Proof of payment ref PAY-SECRET-42 was sent to client@example.test "
                        "and +6281234567890."
                    ),
                ),
                (
                    "wa-file-test-2",
                    "synthetic-source",
                    1,
                    "2026-06-01T10:00:00+00:00",
                    "senderhash3",
                    "NIB company docs are ready without reporting context.",
                ),
            ],
        )
        conn.commit()
    finally:
        conn.close()
    return db_path


@pytest.fixture
def synthetic_support_dbs(tmp_path: Path) -> tuple[Path, Path]:
    candidates_db = tmp_path / "allowed_candidates.local.sqlite"
    signals_db = tmp_path / "allowed_signal_hits.local.sqlite"

    conn = sqlite3.connect(candidates_db)
    try:
        conn.execute(
            """
            CREATE TABLE extracted_candidates (
                file_id TEXT,
                source_tag TEXT,
                message_index INTEGER,
                timestamp TEXT,
                sender_hash TEXT,
                category_code TEXT,
                evidence_code TEXT,
                body_hash TEXT,
                value_hash TEXT
            )
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
                    "wa-file-test-1",
                    "synthetic-source",
                    1,
                    None,
                    None,
                    "tax_payment",
                    "category_keyword",
                    "body1",
                    "",
                ),
                (
                    "wa-file-test-1",
                    "synthetic-source",
                    1,
                    None,
                    None,
                    "money_reference",
                    "money_like_hash",
                    "body1",
                    "hash1",
                ),
                (
                    "wa-file-test-1",
                    "synthetic-source",
                    1,
                    None,
                    None,
                    "date_reference",
                    "date_like_hash",
                    "body1",
                    "hash2",
                ),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    conn = sqlite3.connect(signals_db)
    try:
        conn.execute(
            """
            CREATE TABLE signal_hits (
                file_id TEXT,
                source_tag TEXT,
                message_index INTEGER,
                timestamp TEXT,
                signal_code TEXT
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO signal_hits (
                file_id, source_tag, message_index, timestamp, signal_code
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                ("wa-file-test-1", "synthetic-source", 1, None, "tax_accounting"),
                ("wa-file-test-1", "synthetic-source", 1, None, "money_like"),
                ("wa-file-test-2", "synthetic-source", 1, None, "company_corporate"),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    return candidates_db, signals_db


def _fetch_count(db_path: Path, table: str, column: str, value: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            f"SELECT hit_count FROM {table} WHERE {column} = ?",
            (value,),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    return int(row[0])


def test_cli_writes_hash_only_db_and_aggregate_summary(
    synthetic_messages_db: Path,
    synthetic_support_dbs: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    candidates_db, signals_db = synthetic_support_dbs
    output_db = tmp_path / "allowed_tax_payment.local.sqlite"
    summary = tmp_path / "allowed_tax_payment_summary.md"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--messages-db",
            str(synthetic_messages_db),
            "--candidates-db",
            str(candidates_db),
            "--signals-db",
            str(signals_db),
            "--output-db",
            str(output_db),
            "--summary",
            str(summary),
            "--summary-limit",
            "20",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert output_db.exists()
    assert summary.exists()
    assert '"messages_scanned": 3' in result.stdout

    expected_categories = {
        "tax_accounting",
        "invoice_payment_proof",
        "currency_amount",
        "deadline_penalty",
        "nib_company_tax_docs",
        "monthly_annual_reporting",
        "payroll_bpjs",
    }
    conn = sqlite3.connect(output_db)
    try:
        categories = {
            row[0]
            for row in conn.execute(
                "SELECT DISTINCT category_code FROM tax_payment_hits"
            )
        }
        body_column_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM pragma_table_info('tax_payment_hits')
            WHERE name IN ('body_text', 'raw_value', 'message_text')
            """
        ).fetchone()[0]
        raw_value_matches = conn.execute(
            """
            SELECT COUNT(*)
            FROM tax_payment_hits
            WHERE value_hash IN ('Rp 1.500.000', 'INV-2026-ZERO', 'PAY-SECRET-42')
            """
        ).fetchone()[0]
        hashed_value_count = conn.execute(
            """
            SELECT COUNT(DISTINCT value_hash)
            FROM tax_payment_hits
            WHERE value_hash != ''
            """
        ).fetchone()[0]
    finally:
        conn.close()

    assert categories >= expected_categories
    assert (
        _fetch_count(
            output_db, "category_totals", "category_code", "nib_company_tax_docs"
        )
        == 1
    )
    assert body_column_count == 0
    assert raw_value_matches == 0
    assert hashed_value_count >= 3

    summary_text = summary.read_text(encoding="utf-8")
    assert "# Allowed Tax/Payment Aggregate Summary" in summary_text
    assert "tax_accounting" in summary_text
    assert "invoice_payment_proof" in summary_text
    assert "nib_company_tax_docs" in summary_text
    assert "Rp 1.500.000" not in summary_text
    assert "INV-2026-ZERO" not in summary_text
    assert "PAY-SECRET-42" not in summary_text
    assert "client@example.test" not in summary_text
    assert "+6281234567890" not in summary_text
    assert str(tmp_path) not in summary_text


def test_non_tax_company_docs_do_not_trigger_tax_doc_category(
    synthetic_messages_db: Path,
    tmp_path: Path,
) -> None:
    module = _load_tax_payment()

    artifacts = module.run_extraction(
        messages_db=synthetic_messages_db,
        candidates_db=tmp_path / "allowed_candidates.local.sqlite",
        signals_db=tmp_path / "allowed_signal_hits.local.sqlite",
        output_db=tmp_path / "allowed_tax_payment.local.sqlite",
        summary_path=tmp_path / "allowed_tax_payment_summary.md",
        summary_limit=20,
        generated_at_utc="2026-05-26T00:00:00+00:00",
    )

    doc_rows = [
        row for row in artifacts.category_counts if row.code == "nib_company_tax_docs"
    ]

    assert len(doc_rows) == 1
    assert doc_rows[0].message_count == 1


def test_input_filename_guard_rejects_wrong_messages_db(tmp_path: Path) -> None:
    module = _load_tax_payment()
    blocked_db = tmp_path / "raw_whatsapp.sqlite"
    blocked_db.write_bytes(b"")

    with pytest.raises(ValueError, match="Refusing to read"):
        module.run_extraction(
            messages_db=blocked_db,
            candidates_db=tmp_path / "allowed_candidates.local.sqlite",
            signals_db=tmp_path / "allowed_signal_hits.local.sqlite",
            output_db=tmp_path / "allowed_tax_payment.local.sqlite",
            summary_path=tmp_path / "allowed_tax_payment_summary.md",
            summary_limit=20,
            generated_at_utc="2026-05-26T00:00:00+00:00",
        )
