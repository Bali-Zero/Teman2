"""Tests for crm_guardian_gemini_worker helper functions (Phase 1 cross-folder).

Tests ONLY the pure helpers (no Playwright, no real DB, no real Drive API).
Worker integration with Gemini Web App is exercised manually via canary smoke
on Day 3 — Playwright can't be mocked deterministically.

Covers:
  - compute_cross_folder_fingerprint: stability + folder-id sensitivity
  - build_cross_folder_context_block: format compliance with L1_extraction_v2
  - aggregate_cross_folder_files: cliente + linked companies merge
  - extract_json_block: fenced + balanced-brace fallback
  - queue_mark_running / queue_mark_terminal SQL parameter shape
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


def _import_worker():
    """Import the worker module (lives outside backend/ packaged tree).

    The worker script is at <repo>/scripts/crm_guardian_gemini_worker.py and
    is not part of the backend Python package. We load it dynamically so the
    test suite can exercise its helpers without packaging gymnastics.
    """
    # Resolve repo root by walking up from this test file:
    # test_worker_helpers.py → crm_guardian → services → unit → tests →
    # backend → backend-rag → apps → <repo_root>
    worker_path = (
        Path(__file__).resolve().parents[7]
        / "scripts"
        / "crm_guardian_gemini_worker.py"
    )
    assert worker_path.exists(), f"worker not found at {worker_path}"
    spec = importlib.util.spec_from_file_location(
        "crm_guardian_gemini_worker", worker_path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Block the worker's _resolve_db_url() side effect at import time by
    # NOT calling it — only helpers are needed. Import is otherwise safe
    # because top-level imports do not run network/DB.
    sys.modules["crm_guardian_gemini_worker"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def worker():
    return _import_worker()


# ---------------------------------------------------------------------------
# compute_cross_folder_fingerprint
# ---------------------------------------------------------------------------


class TestCrossFolderFingerprint:
    def test_empty_files_returns_stable_hash(self, worker) -> None:
        fp = worker.compute_cross_folder_fingerprint([])
        assert isinstance(fp, str)
        assert len(fp) == 64  # SHA256 hex digest

    def test_same_files_same_hash(self, worker) -> None:
        files = [
            {"id": "a", "modifiedTime": "2026-05-16T10:00:00Z", "source_folder_id": "f1"},
            {"id": "b", "modifiedTime": "2026-05-16T11:00:00Z", "source_folder_id": "f1"},
        ]
        assert worker.compute_cross_folder_fingerprint(files) == \
               worker.compute_cross_folder_fingerprint(files)

    def test_order_independence(self, worker) -> None:
        """Files in different order must produce same hash (sorted internally)."""
        f1 = [
            {"id": "a", "modifiedTime": "t1", "source_folder_id": "F"},
            {"id": "b", "modifiedTime": "t2", "source_folder_id": "F"},
        ]
        f2 = [
            {"id": "b", "modifiedTime": "t2", "source_folder_id": "F"},
            {"id": "a", "modifiedTime": "t1", "source_folder_id": "F"},
        ]
        assert worker.compute_cross_folder_fingerprint(f1) == \
               worker.compute_cross_folder_fingerprint(f2)

    def test_folder_id_sensitivity(self, worker) -> None:
        """Same file moved between folders → different fingerprint.

        This is the key Phase 1 property: cross_folder fingerprint includes
        source_folder_id so a file relocating between cliente root and
        company folder triggers re-enqueue.
        """
        f1 = [{"id": "x", "modifiedTime": "t", "source_folder_id": "folder_A"}]
        f2 = [{"id": "x", "modifiedTime": "t", "source_folder_id": "folder_B"}]
        assert worker.compute_cross_folder_fingerprint(f1) != \
               worker.compute_cross_folder_fingerprint(f2)

    def test_modified_time_sensitivity(self, worker) -> None:
        f1 = [{"id": "x", "modifiedTime": "2026-05-16T10:00:00Z", "source_folder_id": "F"}]
        f2 = [{"id": "x", "modifiedTime": "2026-05-16T11:00:00Z", "source_folder_id": "F"}]
        assert worker.compute_cross_folder_fingerprint(f1) != \
               worker.compute_cross_folder_fingerprint(f2)


# ---------------------------------------------------------------------------
# build_cross_folder_context_block
# ---------------------------------------------------------------------------


class TestCrossFolderContextBlock:
    def test_no_linked_companies(self, worker) -> None:
        block = worker.build_cross_folder_context_block(
            client_id=42, client_root_folder="folder_root", linked_companies=[],
        )
        assert block.startswith("<CROSS_FOLDER_CONTEXT>")
        assert block.endswith("</CROSS_FOLDER_CONTEXT>")
        assert "client_id: 42" in block
        assert "client_root_folder: folder_root" in block
        assert "linked_company_folders: []" in block

    def test_one_linked_company(self, worker) -> None:
        companies = [
            {
                "company_id": 100,
                "company_name": "PT Sample Bali",
                "google_drive_folder_id": "co_folder_abc",
                "role": "Director",
                "is_primary": True,
            },
        ]
        block = worker.build_cross_folder_context_block(
            client_id=1, client_root_folder="root_id", linked_companies=companies,
        )
        assert "- id: co_folder_abc" in block
        assert "company_name: PT Sample Bali" in block
        assert "company_id: 100" in block
        assert "role: Director" in block
        assert "is_primary: true" in block

    def test_multiple_linked_companies_primary_first(self, worker) -> None:
        companies = [
            {
                "company_id": 200,
                "company_name": "PT Primary",
                "google_drive_folder_id": "p_folder",
                "role": "Shareholder",
                "is_primary": True,
            },
            {
                "company_id": 201,
                "company_name": "PT Secondary",
                "google_drive_folder_id": "s_folder",
                "role": "Commissioner",
                "is_primary": False,
            },
        ]
        block = worker.build_cross_folder_context_block(
            client_id=1, client_root_folder="root", linked_companies=companies,
        )
        # Both folders rendered
        assert "p_folder" in block
        assert "s_folder" in block
        # Primary boolean rendered as 'true'/'false' (YAML-style)
        assert "is_primary: true" in block
        assert "is_primary: false" in block

    def test_block_yaml_like_indentation(self, worker) -> None:
        """Each linked company nested under 2-space indent for LLM parseability."""
        companies = [{
            "company_id": 1, "company_name": "X", "google_drive_folder_id": "f",
            "role": "Director", "is_primary": False,
        }]
        block = worker.build_cross_folder_context_block(
            client_id=1, client_root_folder="r", linked_companies=companies,
        )
        # Each sub-field indented under "  - id:" parent
        lines = block.split("\n")
        company_field_lines = [
            line for line in lines if line.startswith("    company_name")
        ]
        assert len(company_field_lines) == 1


# ---------------------------------------------------------------------------
# aggregate_cross_folder_files (mocked drive_service)
# ---------------------------------------------------------------------------


class TestAggregateCrossFolderFiles:
    @pytest.mark.asyncio
    async def test_no_linked_companies_only_cliente(self, worker, monkeypatch) -> None:
        """No companies → only cliente root files contribute to fingerprint."""
        async def mock_list(_drive, folder_id: str) -> list[dict[str, Any]]:
            if folder_id == "cliente_root":
                return [
                    {"id": "f1", "name": "passport.pdf", "modifiedTime": "t1"},
                    {"id": "f2", "name": "kitas.pdf", "modifiedTime": "t2"},
                ]
            return []

        async def mock_resolve(_drive, folder_id: str) -> str:
            return f"Folder-{folder_id}"

        monkeypatch.setattr(worker, "list_drive_files", mock_list)
        monkeypatch.setattr(worker, "resolve_folder_name", mock_resolve)

        flat, name_map = await worker.aggregate_cross_folder_files(
            drive_service=MagicMock(),
            client_folder_id="cliente_root",
            linked_companies=[],
        )
        assert len(flat) == 2
        assert all(f["source_folder_id"] == "cliente_root" for f in flat)
        assert name_map == {"cliente_root": "Folder-cliente_root"}

    @pytest.mark.asyncio
    async def test_cliente_plus_one_company(self, worker, monkeypatch) -> None:
        async def mock_list(_drive, folder_id: str) -> list[dict[str, Any]]:
            if folder_id == "cliente_root":
                return [{"id": "personal", "name": "passport.pdf", "modifiedTime": "t1"}]
            if folder_id == "company_root":
                return [{"id": "corp", "name": "akta.pdf", "modifiedTime": "t2"}]
            return []

        async def mock_resolve(_drive, folder_id: str) -> str:
            return f"Folder-{folder_id}"

        monkeypatch.setattr(worker, "list_drive_files", mock_list)
        monkeypatch.setattr(worker, "resolve_folder_name", mock_resolve)

        flat, name_map = await worker.aggregate_cross_folder_files(
            drive_service=MagicMock(),
            client_folder_id="cliente_root",
            linked_companies=[{
                "google_drive_folder_id": "company_root",
                "company_name": "PT Test",
                "company_id": 1,
                "role": "Director",
                "is_primary": True,
            }],
        )
        assert len(flat) == 2
        # Provenance attribution preserved per-file
        source_ids = {f["source_folder_id"] for f in flat}
        assert source_ids == {"cliente_root", "company_root"}
        # Folder name lookup uses company_name for linked companies
        assert name_map["company_root"] == "PT Test"

    @pytest.mark.asyncio
    async def test_company_folder_error_does_not_break_pipeline(
        self, worker, monkeypatch,
    ) -> None:
        """A flaky company Drive folder must not block the cliente summary —
        Symbiosis Law 4 graceful degradation."""

        async def mock_list(_drive, folder_id: str) -> list[dict[str, Any]]:
            if folder_id == "cliente_root":
                return [{"id": "ok", "modifiedTime": "t"}]
            raise RuntimeError("Drive API 503")

        async def mock_resolve(_drive, folder_id: str) -> str:
            return f"Folder-{folder_id}"

        monkeypatch.setattr(worker, "list_drive_files", mock_list)
        monkeypatch.setattr(worker, "resolve_folder_name", mock_resolve)

        flat, name_map = await worker.aggregate_cross_folder_files(
            drive_service=MagicMock(),
            client_folder_id="cliente_root",
            linked_companies=[{
                "google_drive_folder_id": "flaky_co",
                "company_name": "PT Flaky",
                "company_id": 99,
                "role": "Director",
                "is_primary": False,
            }],
        )
        # cliente files still present, company silently dropped
        assert len(flat) == 1
        assert flat[0]["source_folder_id"] == "cliente_root"
        assert "flaky_co" not in name_map


# ---------------------------------------------------------------------------
# extract_json_block — existing helper, exercise edge cases
# ---------------------------------------------------------------------------


class TestExtractJsonBlock:
    def test_fenced_json_block(self, worker) -> None:
        text = 'Some intro\n```json\n{"foo": 1}\n```\nTrailing'
        assert worker.extract_json_block(text) == {"foo": 1}

    def test_unfenced_balanced_brace_fallback(self, worker) -> None:
        text = 'Gemini said {"foo": 2} and then more'
        assert worker.extract_json_block(text) == {"foo": 2}

    def test_largest_balanced_block_preferred(self, worker) -> None:
        text = '{"a":1} and a bigger one {"b": {"nested": true}}'
        result = worker.extract_json_block(text)
        # The larger nested object wins (sorted by length descending)
        assert result == {"b": {"nested": True}}

    def test_no_json_returns_none(self, worker) -> None:
        assert worker.extract_json_block("just prose, no braces") is None

    def test_malformed_fenced_falls_back_to_braces(self, worker) -> None:
        text = '```json\nNOT JSON HERE\n```\nbut here is {"valid": true}'
        result = worker.extract_json_block(text)
        assert result == {"valid": True}


# ---------------------------------------------------------------------------
# fetch_linked_companies — verify SQL query shape with mock asyncpg
# ---------------------------------------------------------------------------


class TestFetchLinkedCompanies:
    @pytest.mark.asyncio
    async def test_query_filters_status_active(self, worker) -> None:
        """Locks in the SQL contract: ccl.status = 'active' filter is non-negotiable."""
        captured_sql: list[str] = []

        async def mock_fetch(sql: str, *args, **kwargs) -> list:
            captured_sql.append(sql)
            return []

        mock_conn = MagicMock()
        mock_conn.fetch = mock_fetch

        await worker.fetch_linked_companies(mock_conn, client_id=42)

        assert len(captured_sql) == 1
        sql = captured_sql[0]
        assert "ccl.status = 'active'" in sql
        assert "google_drive_folder_id IS NOT NULL" in sql
        assert "client_company_links ccl" in sql
        assert "JOIN companies c" in sql
        # Primary companies first
        assert "is_primary DESC" in sql

    @pytest.mark.asyncio
    async def test_returns_dicts(self, worker) -> None:
        mock_row = {
            "company_id": 1, "role": "Director", "is_primary": True,
            "company_name": "PT X", "google_drive_folder_id": "drive_id",
        }
        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(return_value=[mock_row])

        result = await worker.fetch_linked_companies(mock_conn, client_id=1)
        assert result == [mock_row]
        assert isinstance(result[0], dict)


# ---------------------------------------------------------------------------
# queue_mark_running — verify SQL contract
# ---------------------------------------------------------------------------


class TestQueueMarkRunning:
    @pytest.mark.asyncio
    async def test_updates_pending_to_running(self, worker) -> None:
        captured: list[tuple[str, tuple]] = []

        async def mock_fetchrow(sql: str, *args, **kwargs) -> dict:
            captured.append((sql, args))
            return {"id": 999}

        mock_conn = MagicMock()
        mock_conn.fetchrow = mock_fetchrow

        result = await worker.queue_mark_running(
            mock_conn, client_id=42, run_id="abc-uuid",
        )
        assert result == 999
        sql, args = captured[0]
        assert "SET status = 'running'" in sql
        assert "attempts = attempts + 1" in sql
        assert "WHERE client_id = $1 AND status = 'pending'" in sql
        assert args == (42, "abc-uuid")

    @pytest.mark.asyncio
    async def test_no_pending_returns_none(self, worker) -> None:
        mock_conn = MagicMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        result = await worker.queue_mark_running(
            mock_conn, client_id=42, run_id="x",
        )
        assert result is None


# ---------------------------------------------------------------------------
# queue_mark_terminal — verify branch behavior
# ---------------------------------------------------------------------------


class TestQueueMarkTerminal:
    @pytest.mark.asyncio
    async def test_no_queue_id_is_noop(self, worker) -> None:
        """Manual --client-id invocation has no queue row → noop."""
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock()
        await worker.queue_mark_terminal(mock_conn, None, "success")
        mock_conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_success_sets_completed_at(self, worker) -> None:
        captured: list[tuple[str, tuple]] = []

        async def mock_execute(sql: str, *args) -> None:
            captured.append((sql, args))

        mock_conn = MagicMock()
        mock_conn.execute = mock_execute

        await worker.queue_mark_terminal(
            mock_conn, queue_id=1, status="success",
            duration_ms=12345,
        )
        assert len(captured) == 1
        sql, args = captured[0]
        assert "completed_at = NOW()" in sql
        assert args[1] == "success"

    @pytest.mark.asyncio
    async def test_error_with_retry_left_schedules_backoff(self, worker) -> None:
        """attempts=1 → backoff 15min, attempts=2 → 30min, attempts=3+ → terminal."""
        executes: list[tuple[str, tuple]] = []

        async def mock_execute(sql: str, *args) -> None:
            executes.append((sql, args))

        async def mock_fetchrow(sql: str, *args) -> dict:
            return {"attempts": 1}

        mock_conn = MagicMock()
        mock_conn.execute = mock_execute
        mock_conn.fetchrow = mock_fetchrow

        await worker.queue_mark_terminal(
            mock_conn, queue_id=1, status="error",
            last_error="DOM timeout",
        )
        assert len(executes) == 1
        sql, _args = executes[0]
        # attempts=1 → 15 * 2^0 = 15 minutes
        assert "INTERVAL '15 minutes'" in sql

    @pytest.mark.asyncio
    async def test_error_after_max_retries_is_terminal(self, worker) -> None:
        executes: list[tuple[str, tuple]] = []

        async def mock_execute(sql: str, *args) -> None:
            executes.append((sql, args))

        async def mock_fetchrow(sql: str, *args) -> dict:
            return {"attempts": 3}  # max_retries=3 hit

        mock_conn = MagicMock()
        mock_conn.execute = mock_execute
        mock_conn.fetchrow = mock_fetchrow

        await worker.queue_mark_terminal(
            mock_conn, queue_id=1, status="error",
            last_error="final fail",
        )
        # Single UPDATE that does NOT set next_retry_at (terminal)
        assert len(executes) == 1
        sql, _ = executes[0]
        assert "INTERVAL" not in sql
        assert "completed_at = NOW()" in sql
