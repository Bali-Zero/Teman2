"""Tests for crm_guardian_gemini_cli_worker helpers.

The CLI worker shares most helpers with the Playwright worker (same SQL
contract, same fingerprint algorithm, same JSON extraction). This test
file covers ONLY the CLI-specific surface area:

  - build_file_inventory_block (Drive metadata table for inline prompt)
  - assemble_full_prompt (context + inventory + template composition)
  - call_gemini_cli (subprocess invocation contract)

Shared helpers (fetch_linked_companies, queue_mark_*, fingerprint, context
block, aggregate_cross_folder_files, extract_json_block) are tested in
test_worker_helpers.py and re-imported here only for sanity.
"""

from __future__ import annotations

import asyncio
import importlib.util
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


def _import_cli_worker():
    """Dynamic import of scripts/crm_guardian_gemini_cli_worker.py."""
    worker_path = (
        Path(__file__).resolve().parents[7] / "scripts" / "crm_guardian_gemini_cli_worker.py"
    )
    assert worker_path.exists(), f"worker not found at {worker_path}"
    spec = importlib.util.spec_from_file_location(
        "crm_guardian_gemini_cli_worker",
        worker_path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["crm_guardian_gemini_cli_worker"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def worker():
    return _import_cli_worker()


# ---------------------------------------------------------------------------
# build_file_inventory_block
# ---------------------------------------------------------------------------


class TestFileInventoryBlock:
    def test_empty_inventory(self, worker) -> None:
        block = worker.build_file_inventory_block([], {})
        assert block.startswith("<FILE_INVENTORY>")
        assert block.endswith("</FILE_INVENTORY>")
        assert "Total files: 0" in block

    def test_single_file_rendered(self, worker) -> None:
        files = [
            {
                "id": "file_abc",
                "name": "passport.pdf",
                "mimeType": "application/pdf",
                "size": "2048576",
                "modifiedTime": "2026-05-16T10:00:00Z",
                "source_folder_id": "folder_xyz",
            }
        ]
        block = worker.build_file_inventory_block(files, {"folder_xyz": "Mario Rossi"})
        assert "Mario Rossi | file_abc | passport.pdf | application/pdf | 2048576" in block
        assert "Total files: 1" in block

    def test_multi_folder_provenance(self, worker) -> None:
        files = [
            {
                "id": "f1",
                "name": "akta.pdf",
                "mimeType": "application/pdf",
                "modifiedTime": "t1",
                "source_folder_id": "co_folder",
            },
            {
                "id": "f2",
                "name": "spt.pdf",
                "mimeType": "application/pdf",
                "modifiedTime": "t2",
                "source_folder_id": "client_folder",
            },
        ]
        name_map = {"co_folder": "PT Sample Bali", "client_folder": "Mario Rossi"}
        block = worker.build_file_inventory_block(files, name_map)
        # Each file shows its OWN source folder name
        assert "PT Sample Bali | f1 | akta.pdf" in block
        assert "Mario Rossi | f2 | spt.pdf" in block

    def test_unknown_source_folder_shows_qmark(self, worker) -> None:
        files = [
            {
                "id": "x",
                "name": "y",
                "mimeType": "z",
                "modifiedTime": "t",
                "source_folder_id": "unmapped",
            }
        ]
        block = worker.build_file_inventory_block(files, {})
        assert "? | x | y" in block

    def test_missing_size_handled(self, worker) -> None:
        files = [
            {
                "id": "g",
                "name": "gdoc",
                "mimeType": "application/vnd.google-apps.document",
                "modifiedTime": "t",
                "source_folder_id": "f",
            }
        ]
        block = worker.build_file_inventory_block(files, {"f": "Folder"})
        # No "size" key in Google Docs files — should render empty without KeyError
        assert "Folder | g | gdoc | application/vnd.google-apps.document |  |" in block

    def test_format_header_documents_columns(self, worker) -> None:
        """Header comment must list columns in order so prompt readers know
        the table shape without parsing a sample row."""
        block = worker.build_file_inventory_block([], {})
        assert "source_folder | file_id | name | mimeType | size_bytes | modifiedTime" in block

    def test_inventory_prompt_budget_prioritizes_ocr_and_doc_type(
        self,
        worker,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        files = [
            {
                "id": "old_plain",
                "name": "meeting-notes-2020.pdf",
                "mimeType": "application/pdf",
                "modifiedTime": "2020-01-01T00:00:00Z",
                "source_folder_id": "f",
            },
            {
                "id": "new_plain",
                "name": "meeting-notes-2026.pdf",
                "mimeType": "application/pdf",
                "modifiedTime": "2026-01-01T00:00:00Z",
                "source_folder_id": "f",
            },
            {
                "id": "priority_doc",
                "name": "passport.pdf",
                "mimeType": "application/pdf",
                "modifiedTime": "2021-01-01T00:00:00Z",
                "source_folder_id": "f",
            },
            {
                "id": "ocr_doc",
                "name": "random-scan.pdf",
                "mimeType": "application/pdf",
                "modifiedTime": "2019-01-01T00:00:00Z",
                "source_folder_id": "f",
            },
        ]
        ocr_results = {
            "ocr_doc": worker.ExtractionResult(
                text="ocr text",
                extractor="pdfminer",
                confidence=0.9,
                page_count=1,
                duration_ms=1,
                truncated=False,
            )
        }

        monkeypatch.setattr(worker, "INVENTORY_MAX_FILES", 3)

        block = worker.build_file_inventory_block(files, {"f": "Folder"}, ocr_results)

        assert "ocr_doc" in block
        assert "priority_doc" in block
        assert "new_plain" in block
        assert "old_plain" not in block
        assert block.index("ocr_doc") < block.index("priority_doc") < block.index("new_plain")
        assert "priority_doc | passport.pdf | application/pdf |  | 2021-01-01T00:00:00Z | passport" in block
        assert "# Total files: 4" in block
        assert "# Files rendered: 3" in block
        assert "# Files skipped_by_prompt_budget: 1" in block


# ---------------------------------------------------------------------------
# build_file_content_snippets_block
# ---------------------------------------------------------------------------


class TestFileContentSnippetsBlock:
    def test_empty_snippets_block(self, worker) -> None:
        block = worker.build_file_content_snippets_block([], {})

        assert block.startswith("<FILE_CONTENT_SNIPPETS>")
        assert "No OCR content extracted" in block
        assert block.endswith("</FILE_CONTENT_SNIPPETS>")

    def test_snippet_prompt_budget_caps_cache_hits(
        self,
        worker,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        files = [
            {"id": "f1", "name": "passport.pdf"},
            {"id": "f2", "name": "akta.pdf"},
            {"id": "f3", "name": "npwp.pdf"},
        ]
        ocr_results = {
            "f1": worker.ExtractionResult(
                text="abcdefghi",
                extractor="pdfminer",
                confidence=0.9,
                page_count=1,
                duration_ms=1,
                truncated=False,
            ),
            "f2": worker.ExtractionResult(
                text="jklmnopqr",
                extractor="pdfminer",
                confidence=0.8,
                page_count=1,
                duration_ms=1,
                truncated=False,
            ),
            "f3": worker.ExtractionResult(
                text="stuvwxyz",
                extractor="pdfminer",
                confidence=0.7,
                page_count=1,
                duration_ms=1,
                truncated=False,
            ),
        }

        monkeypatch.setattr(worker, "CONTENT_SNIPPET_MAX_FILES", 2)
        monkeypatch.setattr(worker, "CONTENT_SNIPPET_MAX_CHARS_PER_FILE", 5)
        monkeypatch.setattr(worker, "CONTENT_SNIPPET_MAX_CHARS_TOTAL", 8)

        block = worker.build_file_content_snippets_block(files, ocr_results)

        assert "--- file_id: f1 ---" in block
        assert "abcde" in block
        assert "abcdef" not in block
        assert "--- file_id: f2 ---" in block
        assert "jkl" in block
        assert "jklm" not in block
        assert "--- file_id: f3 ---" not in block
        assert "# Snippets rendered: 2" in block
        assert "# Snippets skipped_by_prompt_budget: 1" in block
        assert "# Snippet text chars rendered: 8/8" in block
        assert "prompt_truncated=true" in block


# ---------------------------------------------------------------------------
# enrich_files_with_ocr
# ---------------------------------------------------------------------------


class TestOcrEnrichmentBudgets:
    def test_default_fresh_ocr_budget_matches_rendered_snippets(self, worker) -> None:
        assert worker.OCR_MAX_FILES_PER_CLIENT == 8
        assert worker.CONTENT_SNIPPET_MAX_FILES == 8
        assert worker.OCR_MAX_SECONDS_PER_CLIENT > 0
        assert worker.OCR_MAX_SECONDS_PER_FILE > 0

    @pytest.mark.asyncio
    async def test_fresh_ocr_budget_caps_extraction_work(
        self,
        worker,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        files = [
            {"id": "f1", "name": "passport-a.pdf", "mimeType": "application/pdf"},
            {"id": "f2", "name": "passport-b.pdf", "mimeType": "application/pdf"},
            {"id": "f3", "name": "passport-c.pdf", "mimeType": "application/pdf"},
        ]
        extraction = worker.ExtractionResult(
            text="passport text",
            extractor="pdfminer",
            confidence=None,
            page_count=1,
            duration_ms=1,
            truncated=False,
        )

        extract = AsyncMock(return_value=extraction)
        download = AsyncMock(return_value=b"%PDF")
        upsert = AsyncMock()

        monkeypatch.setattr(worker, "get_cached_content", AsyncMock(return_value=None))
        monkeypatch.setattr(worker, "download_drive_file_bytes", download)
        monkeypatch.setattr(worker, "extract_file_content", extract)
        monkeypatch.setattr(worker, "upsert_cache_row", upsert)

        enriched = await worker.enrich_files_with_ocr(
            object(),
            object(),
            files,
            object(),
            budget=2,
            max_seconds_per_client=999,
            max_seconds_per_file=999,
        )

        assert extract.await_count == 2
        assert download.await_count == 2
        assert upsert.await_count == 2
        assert set(enriched) == {"f1", "f2"}
        assert [f["inferred_doc_type"] for f in files] == ["passport", "passport", "passport"]

    @pytest.mark.asyncio
    async def test_fresh_ocr_file_timeout_records_skipped_cache_row(
        self,
        worker,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async def slow_extract(**_kwargs):
            await asyncio.sleep(0.05)

        files = [{"id": "f1", "name": "passport.pdf", "mimeType": "application/pdf"}]
        upsert = AsyncMock()

        monkeypatch.setattr(worker, "get_cached_content", AsyncMock(return_value=None))
        monkeypatch.setattr(worker, "download_drive_file_bytes", AsyncMock(return_value=b"%PDF"))
        monkeypatch.setattr(worker, "extract_file_content", slow_extract)
        monkeypatch.setattr(worker, "upsert_cache_row", upsert)

        enriched = await worker.enrich_files_with_ocr(
            object(),
            object(),
            files,
            object(),
            budget=1,
            max_seconds_per_client=999,
            max_seconds_per_file=0.01,
        )

        assert enriched == {}
        result = upsert.await_args.kwargs["result"]
        assert result.extractor == "skipped"
        assert result.notes == "file_timeout_after_0.01s"


# ---------------------------------------------------------------------------
# assemble_full_prompt
# ---------------------------------------------------------------------------


class TestAssembleFullPrompt:
    def test_concatenation_order(self, worker) -> None:
        ctx = "<CROSS_FOLDER_CONTEXT>\nclient_id: 1\n</CROSS_FOLDER_CONTEXT>"
        inv = "<FILE_INVENTORY>\nfile data\n</FILE_INVENTORY>"
        content = "<FILE_CONTENT_SNIPPETS>\nstatic ocr text\n</FILE_CONTENT_SNIPPETS>"
        tpl = "## Prompt\nYou are the CRM intelligence layer..."
        out = worker.assemble_full_prompt(tpl, ctx, inv, content)
        # Order: hard agy contract -> template -> evidence -> final JSON contract.
        assert out.index(worker.AGY_PRINT_MODE_CONTRACT) < out.index(tpl)
        assert out.index(tpl) < out.index(ctx) < out.index(inv) < out.index(content)
        assert out.index(content) < out.index(worker.AGY_FINAL_OUTPUT_CONTRACT)

    def test_double_newline_separator(self, worker) -> None:
        out = worker.assemble_full_prompt("TPL", "CTX", "INV")
        assert "\n\n".join(
            [
                worker.AGY_PRINT_MODE_CONTRACT,
                "TPL",
                "CTX",
                "INV",
                worker.AGY_FINAL_OUTPUT_CONTRACT,
            ]
        ) == out

    def test_agy_contract_blocks_waiting_and_tools(self, worker) -> None:
        out = worker.assemble_full_prompt("TPL", "CTX", "INV", "CONTENT")

        assert "Do not use tools" in out
        assert "Do not wait" in out
        assert "All Drive listing, OCR extraction, and cache lookup work has already completed" in out
        assert "Emit only one ```json fenced object now" in out

    def test_default_prompt_is_v5_and_lean(self, worker) -> None:
        prompt = worker.DEFAULT_PROMPT_FILE.read_text(encoding="utf-8")

        assert worker.DEFAULT_PROMPT_FILE.name == "L1_extraction_v5.md"
        assert len(prompt) < 10_000
        assert "Do not wait" in prompt
        assert '"prompt_version": "L1_extraction_v5"' in prompt


# ---------------------------------------------------------------------------
# call_gemini_cli (subprocess contract)
# ---------------------------------------------------------------------------


class FakePopen:
    """Small Popen test double that writes into the provided output files."""

    pid = 12345

    def __init__(
        self,
        _cmd: list[str],
        *,
        stdout,
        stderr,
        returncode: int = 0,
        stdout_text: str = "",
        stderr_text: str = "",
        timeout: bool = False,
        **_kwargs,
    ) -> None:
        self.returncode = returncode
        self._timeout = timeout
        self.wait_calls = 0
        stdout.write(stdout_text)
        stderr.write(stderr_text)

    def wait(self, timeout: int | None = None) -> int:
        self.wait_calls += 1
        if self._timeout and self.wait_calls == 1:
            raise subprocess.TimeoutExpired(cmd=["agy"], timeout=timeout)
        return self.returncode

    def poll(self) -> int | None:
        if self._timeout and self.wait_calls <= 1:
            return None
        return self.returncode


class TestCallGeminiCli:
    def test_basic_invocation(self, worker, tmp_path: Path) -> None:
        """Mock subprocess.Popen, verify command and no pipe capture."""
        popen = FakePopen
        with (
            patch.object(
                worker.subprocess,
                "Popen",
                side_effect=lambda *args, **kwargs: popen(
                    *args,
                    stdout_text='```json\n{"ok": true}\n```\n',
                    **kwargs,
                ),
            ) as mock_popen,
            patch.object(worker.Path, "exists", return_value=True),
            patch.object(worker, "RAW_DUMP_DIR", tmp_path),
        ):
            out = worker.call_gemini_cli("hello prompt")
            assert "```json" in out
            mock_popen.assert_called_once()
            args = mock_popen.call_args[0][0]
            kwargs = mock_popen.call_args.kwargs
            assert args[0] == worker.GEMINI_CLI
            assert args[1] == "-p"
            assert args[2] == "--print-timeout"
            assert args[3].endswith("s")
            assert "hello prompt" not in args
            assert kwargs["stdin"] is not None
            assert kwargs["stdout"] is not subprocess.PIPE
            assert kwargs["stderr"] is not subprocess.PIPE
            assert kwargs["start_new_session"] is True

    def test_model_arg_ignored_on_agy(self, worker, tmp_path: Path) -> None:
        """agy does not support `-m`; the model arg is accepted but never passed."""
        with (
            patch.object(
                worker.subprocess,
                "Popen",
                side_effect=lambda *args, **kwargs: FakePopen(
                    *args,
                    stdout_text="x",
                    **kwargs,
                ),
            ) as mock_popen,
            patch.object(worker.Path, "exists", return_value=True),
            patch.object(worker, "RAW_DUMP_DIR", tmp_path),
        ):
            worker.call_gemini_cli("p", model="gemini-2.5-pro")
            args = mock_popen.call_args[0][0]
            assert "-m" not in args
            assert "gemini-2.5-pro" not in args

    def test_timeout_propagates_and_kills_process_group(self, worker, tmp_path: Path) -> None:
        with (
            patch.object(
                worker.subprocess,
                "Popen",
                side_effect=lambda *args, **kwargs: FakePopen(
                    *args,
                    timeout=True,
                    stderr_text="still running",
                    **kwargs,
                ),
            ),
            patch.object(worker.os, "killpg") as mock_killpg,
            patch.object(worker.Path, "exists", return_value=True),
            patch.object(worker, "RAW_DUMP_DIR", tmp_path),
        ):
            with pytest.raises(subprocess.TimeoutExpired):
                worker.call_gemini_cli("p", timeout_seconds=240)
            mock_killpg.assert_called()

    def test_nonzero_exit_raises(self, worker, tmp_path: Path) -> None:
        with (
            patch.object(
                worker.subprocess,
                "Popen",
                side_effect=lambda *args, **kwargs: FakePopen(
                    *args,
                    returncode=1,
                    stderr_text="auth required",
                    **kwargs,
                ),
            ),
            patch.object(worker.Path, "exists", return_value=True),
            patch.object(worker, "RAW_DUMP_DIR", tmp_path),
        ):
            with pytest.raises(RuntimeError, match="gemini CLI returncode=1"):
                worker.call_gemini_cli("p")

    def test_missing_cli_binary_raises(self, worker) -> None:
        with patch.object(worker.Path, "exists", return_value=False):
            with pytest.raises(RuntimeError, match="agy CLI not found"):
                worker.call_gemini_cli("p")


# ---------------------------------------------------------------------------
# extract_json_block (re-exported from worker — sanity)
# ---------------------------------------------------------------------------


class TestExtractJsonBlock:
    def test_fenced_json(self, worker) -> None:
        text = 'Some intro\n```json\n{"foo": 1}\n```\nTrailing prose'
        assert worker.extract_json_block(text) == {"foo": 1}

    def test_unfenced_fallback(self, worker) -> None:
        text = 'no fence but {"k": 2} is here'
        assert worker.extract_json_block(text) == {"k": 2}

    def test_no_json_returns_none(self, worker) -> None:
        assert worker.extract_json_block("just words, no json") is None

    def test_agentic_wait_response_detected(self, worker) -> None:
        text = (
            "I will wait for the background OCR task to complete before continuing.\n"
            "Error: timed out waiting for response"
        )

        assert worker.extract_json_block(text) is None
        assert worker._looks_like_agentic_wait_response(text) is True


# ---------------------------------------------------------------------------
# main() operational state
# ---------------------------------------------------------------------------


class TestMainOperationalState:
    @pytest.mark.asyncio
    async def test_reset_stale_running_jobs_returns_update_count(self, worker) -> None:
        class FakeConn:
            def __init__(self) -> None:
                self.execute = AsyncMock(return_value="UPDATE 2")

        fake_conn = FakeConn()

        result = await worker.reset_stale_running_jobs(fake_conn, stale_after_seconds=600)

        assert result == 2
        sql = fake_conn.execute.await_args.args[0]
        assert "status = 'running'" in sql
        assert "status = 'pending'" in sql
        assert fake_conn.execute.await_args.args[1] == 600

    @pytest.mark.asyncio
    async def test_no_pending_queue_bumps_i10b_success(
        self,
        worker,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("prompt", encoding="utf-8")

        class FakeConn:
            def __init__(self) -> None:
                self.execute = AsyncMock(return_value="UPDATE 0")
                self.fetch = AsyncMock(return_value=[])
                self.close = AsyncMock()

        fake_conn = FakeConn()

        import asyncpg

        import backend.services.crm_guardian.base as guardian_base

        bump = AsyncMock()
        monkeypatch.setattr(worker, "_resolve_db_url", lambda: "postgresql://test/db")
        monkeypatch.setattr(asyncpg, "connect", AsyncMock(return_value=fake_conn))
        monkeypatch.setattr(guardian_base, "bump_circuit_breaker", bump)
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "crm_guardian_gemini_cli_worker.py",
                "--from-queue",
                "--prompt-file",
                str(prompt_file),
            ],
        )

        exit_code = await worker.main()

        assert exit_code == 0
        bump.assert_awaited_once_with(fake_conn, "I10b_summary_queue", True)
        fake_conn.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_processed_batch_bumps_queue_and_l1_state(
        self,
        worker,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("prompt", encoding="utf-8")

        class FakeConn:
            def __init__(self) -> None:
                self.execute = AsyncMock(return_value="UPDATE 0")
                self.fetch = AsyncMock(return_value=[{"client_id": 123}])
                self.close = AsyncMock()

        fake_conn = FakeConn()

        import asyncpg

        import backend.services.crm_guardian.base as guardian_base

        bump = AsyncMock()
        monkeypatch.setattr(worker, "_resolve_db_url", lambda: "postgresql://test/db")
        monkeypatch.setattr(asyncpg, "connect", AsyncMock(return_value=fake_conn))
        monkeypatch.setattr(guardian_base, "bump_circuit_breaker", bump)
        monkeypatch.setattr(guardian_base, "build_drive_service", lambda prefer_user_oauth: object())
        monkeypatch.setattr(
            worker,
            "run_one_client",
            AsyncMock(return_value={"client_id": 123, "status": "success"}),
        )
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "crm_guardian_gemini_cli_worker.py",
                "--from-queue",
                "--prompt-file",
                str(prompt_file),
            ],
        )

        exit_code = await worker.main()

        assert exit_code == 0
        assert bump.await_args_list[0].args == (fake_conn, "I10b_summary_queue", True, None)
        assert bump.await_args_list[1].args == (fake_conn, "I10_summary_l1", True, None)
        fake_conn.close.assert_awaited_once()


# ---------------------------------------------------------------------------
# Shared helpers — sanity check they exist in CLI worker (copy from Playwright)
# ---------------------------------------------------------------------------


class TestSharedHelpersExist:
    """Ensure CLI worker exposes the same helper API as the Playwright worker.

    Phase 1 design: workers are interchangeable — same fingerprint, same
    queue lifecycle, same context block. Only the LLM driver differs.
    """

    def test_fetch_linked_companies_exists(self, worker) -> None:
        assert callable(worker.fetch_linked_companies)

    def test_aggregate_cross_folder_files_exists(self, worker) -> None:
        assert callable(worker.aggregate_cross_folder_files)

    def test_compute_cross_folder_fingerprint_exists(self, worker) -> None:
        # Reuse identical hash from playwright worker
        fp1 = worker.compute_cross_folder_fingerprint(
            [
                {"id": "a", "modifiedTime": "t", "source_folder_id": "F"},
            ]
        )
        fp2 = worker.compute_cross_folder_fingerprint(
            [
                {"id": "a", "modifiedTime": "t", "source_folder_id": "F"},
            ]
        )
        assert fp1 == fp2
        assert len(fp1) == 64

    def test_build_cross_folder_context_block_exists(self, worker) -> None:
        out = worker.build_cross_folder_context_block(1, "root", [])
        assert "<CROSS_FOLDER_CONTEXT>" in out
        assert "client_id: 1" in out

    def test_queue_helpers_exist(self, worker) -> None:
        assert callable(worker.queue_mark_running)
        assert callable(worker.queue_mark_terminal)
