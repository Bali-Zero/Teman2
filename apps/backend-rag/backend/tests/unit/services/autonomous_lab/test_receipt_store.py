from __future__ import annotations

import json
import stat
from datetime import datetime, timezone
from pathlib import Path

import pytest

import backend.services.autonomous_lab.receipt_store as receipt_store_module
from backend.services.autonomous_lab.planner import (
    AutonomousLabPlanner,
    MaterialSourceType,
    ResearchMaterial,
)


def _run(raw_phrase: str = "RAW_TEXT_MUST_NOT_LEAK"):
    material = ResearchMaterial(
        material_id="m1",
        source_type=MaterialSourceType.OPERATOR_NOTE,
        source_uri="note://receipt-store",
        title="Receipt store source",
        text=f"Derived facts only. {raw_phrase}",
        captured_at=datetime(2026, 5, 31, tzinfo=timezone.utc),
        metadata={"scope": "unit-test"},
    )
    return AutonomousLabPlanner().draft_run(
        objective="persist a lab receipt",
        materials=[material],
        target_paths=["apps/backend-rag/backend/services/autonomous_lab/planner.py"],
        task_id="receipt-store-test",
        created_at=datetime(2026, 5, 31, tzinfo=timezone.utc),
    )


def test_receipt_store_writes_receipt_and_event_without_raw_text(tmp_path: Path) -> None:
    raw_phrase = "RAW_TEXT_MUST_NOT_LEAK"
    store = receipt_store_module.ReceiptStore(tmp_path)

    record = store.write_run(_run(raw_phrase))

    receipt_text = record.receipt_path.read_text(encoding="utf-8")
    event_text = record.event_path.read_text(encoding="utf-8")
    event = json.loads(event_text)

    assert record.run_id == "receipt-store-test"
    assert record.blocked is False
    assert raw_phrase not in receipt_text
    assert event["event"] == "autonomous_lab.receipt_written"
    assert event["run_id"] == "receipt-store-test"


def test_receipt_store_loads_and_lists_run_ids(tmp_path: Path) -> None:
    store = receipt_store_module.ReceiptStore(tmp_path)
    store.write_run(_run())

    assert store.list_run_ids() == ["receipt-store-test"]
    assert store.load_receipt("receipt-store-test")["run_id"] == "receipt-store-test"


def test_receipt_store_accepts_orchestration_receipts(tmp_path: Path) -> None:
    store = receipt_store_module.ReceiptStore(tmp_path)

    record = store.write_receipt({"run": _run().to_receipt(), "blocked": False})

    assert record.run_id == "receipt-store-test"
    assert record.blocked is False
    assert store.load_receipt("receipt-store-test")["run"]["run_id"] == "receipt-store-test"


def test_receipt_store_rejects_raw_content_keys(tmp_path: Path) -> None:
    store = receipt_store_module.ReceiptStore(tmp_path)

    with pytest.raises(ValueError, match="forbidden raw-content key"):
        store.write_receipt({"run_id": "unsafe-receipt", "materials": [{"text": "raw body"}]})


def test_receipt_store_rejects_raw_or_secret_like_values(tmp_path: Path) -> None:
    store = receipt_store_module.ReceiptStore(tmp_path)

    with pytest.raises(ValueError, match="unsafe raw or secret-like value"):
        store.write_receipt(
            {
                "run_id": "unsafe-value",
                "summary": "Derived summary leaked RAW_PRIVATE_SENTENCE_SHOULD_NOT_APPEAR",
            }
        )


def test_receipt_store_rejects_mutating_commands(tmp_path: Path) -> None:
    store = receipt_store_module.ReceiptStore(tmp_path)

    with pytest.raises(ValueError, match="mutating command-like value"):
        store.write_receipt(
            {
                "run_id": "unsafe-command",
                "planned_only_commands": ["git push origin main"],
            }
        )


def test_receipt_store_rejects_embedded_unpersistable_findings(tmp_path: Path) -> None:
    store = receipt_store_module.ReceiptStore(tmp_path)

    with pytest.raises(ValueError, match="raw_text_leakage"):
        store.write_receipt(
            {
                "run": _run().to_receipt(),
                "blocked": True,
                "review_findings": [
                    {
                        "code": "raw_text_leakage",
                        "severity": "blocker",
                        "detail": "redacted unsafe receipt value",
                    }
                ],
                "failed_blockers": ["raw_text_leakage"],
            }
        )


def test_receipt_store_does_not_overwrite_existing_receipt(tmp_path: Path) -> None:
    store = receipt_store_module.ReceiptStore(tmp_path)
    store.write_run(_run())

    with pytest.raises(FileExistsError, match="receipt already exists"):
        store.write_run(_run())


def test_receipt_store_does_not_overwrite_if_receipt_appears_during_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = receipt_store_module.ReceiptStore(tmp_path)
    original_write_json_atomic = receipt_store_module._write_json_atomic
    first_writer_payload = {
        "run_id": "race-receipt",
        "summary": "first writer wins",
        "blocked": False,
    }

    def simulate_concurrent_writer(path: Path, payload: dict) -> None:
        path.write_text(json.dumps(first_writer_payload), encoding="utf-8")
        original_write_json_atomic(path, payload)

    monkeypatch.setattr(
        receipt_store_module,
        "_write_json_atomic",
        simulate_concurrent_writer,
    )

    with pytest.raises(FileExistsError, match="receipt already exists"):
        store.write_receipt(
            {
                "run_id": "race-receipt",
                "summary": "second writer must not replace this",
                "blocked": False,
            }
        )

    receipt = json.loads((tmp_path / "race-receipt.json").read_text(encoding="utf-8"))
    assert receipt == first_writer_payload


def test_receipt_store_uses_private_file_permissions(tmp_path: Path) -> None:
    store = receipt_store_module.ReceiptStore(tmp_path)

    record = store.write_run(_run())

    receipt_mode = stat.S_IMODE(record.receipt_path.stat().st_mode)
    event_mode = stat.S_IMODE(record.event_path.stat().st_mode)
    assert receipt_mode == 0o600
    assert event_mode == 0o600


def test_receipt_store_rejects_unsafe_run_id(tmp_path: Path) -> None:
    store = receipt_store_module.ReceiptStore(tmp_path)

    with pytest.raises(ValueError, match="run_id"):
        store.write_receipt({"run_id": "../unsafe", "blocked": False})
