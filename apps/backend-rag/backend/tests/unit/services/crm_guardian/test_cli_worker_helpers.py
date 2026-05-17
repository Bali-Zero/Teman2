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

import importlib.util
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


def _import_cli_worker():
    """Dynamic import of scripts/crm_guardian_gemini_cli_worker.py."""
    worker_path = (
        Path(__file__).resolve().parents[7]
        / "scripts"
        / "crm_guardian_gemini_cli_worker.py"
    )
    assert worker_path.exists(), f"worker not found at {worker_path}"
    spec = importlib.util.spec_from_file_location(
        "crm_guardian_gemini_cli_worker", worker_path,
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
        files = [{
            "id": "file_abc",
            "name": "passport.pdf",
            "mimeType": "application/pdf",
            "size": "2048576",
            "modifiedTime": "2026-05-16T10:00:00Z",
            "source_folder_id": "folder_xyz",
        }]
        block = worker.build_file_inventory_block(files, {"folder_xyz": "Mario Rossi"})
        assert "Mario Rossi | file_abc | passport.pdf | application/pdf | 2048576" in block
        assert "Total files: 1" in block

    def test_multi_folder_provenance(self, worker) -> None:
        files = [
            {"id": "f1", "name": "akta.pdf", "mimeType": "application/pdf",
             "modifiedTime": "t1", "source_folder_id": "co_folder"},
            {"id": "f2", "name": "spt.pdf", "mimeType": "application/pdf",
             "modifiedTime": "t2", "source_folder_id": "client_folder"},
        ]
        name_map = {"co_folder": "PT Sample Bali", "client_folder": "Mario Rossi"}
        block = worker.build_file_inventory_block(files, name_map)
        # Each file shows its OWN source folder name
        assert "PT Sample Bali | f1 | akta.pdf" in block
        assert "Mario Rossi | f2 | spt.pdf" in block

    def test_unknown_source_folder_shows_qmark(self, worker) -> None:
        files = [{"id": "x", "name": "y", "mimeType": "z",
                  "modifiedTime": "t", "source_folder_id": "unmapped"}]
        block = worker.build_file_inventory_block(files, {})
        assert "? | x | y" in block

    def test_missing_size_handled(self, worker) -> None:
        files = [{"id": "g", "name": "gdoc", "mimeType": "application/vnd.google-apps.document",
                  "modifiedTime": "t", "source_folder_id": "f"}]
        block = worker.build_file_inventory_block(files, {"f": "Folder"})
        # No "size" key in Google Docs files — should render empty without KeyError
        assert "Folder | g | gdoc | application/vnd.google-apps.document |  |" in block

    def test_format_header_documents_columns(self, worker) -> None:
        """Header comment must list columns in order so prompt readers know
        the table shape without parsing a sample row."""
        block = worker.build_file_inventory_block([], {})
        assert "source_folder | file_id | name | mimeType | size_bytes | modifiedTime" in block


# ---------------------------------------------------------------------------
# assemble_full_prompt
# ---------------------------------------------------------------------------


class TestAssembleFullPrompt:
    def test_concatenation_order(self, worker) -> None:
        ctx = "<CROSS_FOLDER_CONTEXT>\nclient_id: 1\n</CROSS_FOLDER_CONTEXT>"
        inv = "<FILE_INVENTORY>\nfile data\n</FILE_INVENTORY>"
        tpl = "## Prompt\nYou are the CRM intelligence layer..."
        out = worker.assemble_full_prompt(tpl, ctx, inv)
        # Order: context → inventory → template
        assert out.index(ctx) < out.index(inv) < out.index(tpl)

    def test_double_newline_separator(self, worker) -> None:
        out = worker.assemble_full_prompt("TPL", "CTX", "INV")
        assert "CTX\n\nINV\n\nTPL" == out


# ---------------------------------------------------------------------------
# call_gemini_cli (subprocess contract)
# ---------------------------------------------------------------------------


class TestCallGeminiCli:
    def test_basic_invocation(self, worker) -> None:
        """Mock subprocess.run, verify command shape."""
        mock_result = subprocess.CompletedProcess(
            args=["gemini", "-p", "test"],
            returncode=0,
            stdout="```json\n{\"ok\": true}\n```\n",
            stderr="",
        )
        with patch.object(worker.subprocess, "run", return_value=mock_result) as mock_run, \
             patch.object(worker.shutil, "which", return_value="/opt/homebrew/bin/gemini"):
            out = worker.call_gemini_cli("hello prompt")
            assert "```json" in out
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert args[0] == worker.GEMINI_CLI
            assert args[1] == "-p"
            assert args[2] == "hello prompt"

    def test_model_override(self, worker) -> None:
        mock_result = subprocess.CompletedProcess(args=[], returncode=0, stdout="x", stderr="")
        with patch.object(worker.subprocess, "run", return_value=mock_result) as mock_run, \
             patch.object(worker.shutil, "which", return_value="/opt/homebrew/bin/gemini"):
            worker.call_gemini_cli("p", model="gemini-2.5-pro")
            args = mock_run.call_args[0][0]
            assert "-m" in args
            assert "gemini-2.5-pro" in args
            # Order: -p value -m value (positional)
            assert args.index("-m") > args.index("-p")

    def test_timeout_propagates(self, worker) -> None:
        with patch.object(
            worker.subprocess, "run",
            side_effect=subprocess.TimeoutExpired(cmd=["gemini"], timeout=240),
        ), patch.object(worker.shutil, "which", return_value="/opt/homebrew/bin/gemini"):
            with pytest.raises(subprocess.TimeoutExpired):
                worker.call_gemini_cli("p", timeout_seconds=240)

    def test_nonzero_exit_raises(self, worker) -> None:
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="auth required",
        )
        with patch.object(worker.subprocess, "run", return_value=mock_result), \
             patch.object(worker.shutil, "which", return_value="/opt/homebrew/bin/gemini"):
            with pytest.raises(RuntimeError, match="gemini CLI returncode=1"):
                worker.call_gemini_cli("p")

    def test_missing_cli_binary_raises(self, worker) -> None:
        with patch.object(worker.shutil, "which", return_value=None):
            with pytest.raises(RuntimeError, match="gemini CLI not found"):
                worker.call_gemini_cli("p")


# ---------------------------------------------------------------------------
# extract_json_block (re-exported from worker — sanity)
# ---------------------------------------------------------------------------


class TestExtractJsonBlock:
    def test_fenced_json(self, worker) -> None:
        text = "Some intro\n```json\n{\"foo\": 1}\n```\nTrailing prose"
        assert worker.extract_json_block(text) == {"foo": 1}

    def test_unfenced_fallback(self, worker) -> None:
        text = "no fence but {\"k\": 2} is here"
        assert worker.extract_json_block(text) == {"k": 2}

    def test_no_json_returns_none(self, worker) -> None:
        assert worker.extract_json_block("just words, no json") is None


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
        fp1 = worker.compute_cross_folder_fingerprint([
            {"id": "a", "modifiedTime": "t", "source_folder_id": "F"},
        ])
        fp2 = worker.compute_cross_folder_fingerprint([
            {"id": "a", "modifiedTime": "t", "source_folder_id": "F"},
        ])
        assert fp1 == fp2
        assert len(fp1) == 64

    def test_build_cross_folder_context_block_exists(self, worker) -> None:
        out = worker.build_cross_folder_context_block(1, "root", [])
        assert "<CROSS_FOLDER_CONTEXT>" in out
        assert "client_id: 1" in out

    def test_queue_helpers_exist(self, worker) -> None:
        assert callable(worker.queue_mark_running)
        assert callable(worker.queue_mark_terminal)
