"""
Regression test for _ingest_to_backend swallowing the real failure reason
when the backend's terminal-state response carries message=None.

Live incident 2026-09-10 19:00Z: ingest-full job 88a120aa failed with
message=null and error="pending: ...", and the feeder raised a bare
TypeError ('NoneType' object is not subscriptable) instead of surfacing
status/message/error to the caller.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "nlm_deep_research"))

import peraturan_ingestion_trigger as trigger  # noqa: E402


def _row(**overrides) -> trigger.RegulationRow:
    defaults = dict(
        row_index=2,
        nome="PMK Nomor 43 Tahun 2026",
        tipo="PMK",
        categoria="Tax",
        anno="2026",
        sintesi_it="",
        categoria_en="",
        sintesi_en="",
        status="PENDING",
        url="https://peraturan.go.id/fake.pdf",
        drive_file_id="",
        timestamp="",
    )
    defaults.update(overrides)
    return trigger.RegulationRow(**defaults)


def _mock_client(terminal_payload: dict) -> MagicMock:
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = terminal_payload

    client = MagicMock()
    client.post.return_value = response
    client.__enter__.return_value = client
    client.__exit__.return_value = False
    return client


def test_null_message_surfaces_status_and_error_without_typeerror():
    payload = {
        "job_id": "j1",
        "status": "failed",
        "message": None,
        "error": "pending: ",
    }
    with patch.object(trigger.httpx, "Client", return_value=_mock_client(payload)):
        try:
            trigger._ingest_to_backend(Path("/tmp/fake.pdf"), _row())
        except TypeError as exc:
            raise AssertionError(f"TypeError escaped, message=None not handled: {exc}") from exc
        except RuntimeError as exc:
            text = str(exc)
            assert "j1" in text
            assert "failed" in text
            assert "pending" in text
        else:
            raise AssertionError("expected RuntimeError, none was raised")


def test_string_message_still_surfaced():
    payload = {
        "job_id": "j2",
        "status": "error",
        "message": "boom",
        "error": None,
    }
    with patch.object(trigger.httpx, "Client", return_value=_mock_client(payload)):
        try:
            trigger._ingest_to_backend(Path("/tmp/fake.pdf"), _row())
        except RuntimeError as exc:
            assert "boom" in str(exc)
        else:
            raise AssertionError("expected RuntimeError, none was raised")
