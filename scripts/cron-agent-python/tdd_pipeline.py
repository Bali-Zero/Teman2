#!/usr/bin/env python3
"""
TDD Pipeline — weekly on Monday 09:00 WITA.

# Organo: tdd-pipeline (cron-agent-python, --agents pattern) → produce:
#         Test files in backend-rag/tests/ + Telegram report
# Consuma da: backend-rag/backend/services/ (recently modified files)
#
# Ruolo: dev velocity. Scansiona services/ per file modificati nell'ultima
#         settimana senza test corrispondenti. Invoca Claude Code con pattern
#         --agents (planner → test_writer → code_writer → reviewer) per
#         generare test. Max 3 target files per run (token budget).

Process:
  1. Find recently modified .py files in backend/services/ without tests
  2. For each (up to MAX_TARGETS): invoke claude with --agents JSON pipeline
  3. Verify generated tests run (pytest --collect-only)
  4. Report results via Telegram

Usage:
  bash run.sh tdd-pipeline
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from agent_job import AgentJob, RunResult, WITA, main

BACKEND_ROOT = Path.home() / "nuzantara" / "apps" / "backend-rag"
SERVICES_DIR = BACKEND_ROOT / "backend" / "services"
TESTS_DIR = BACKEND_ROOT / "backend" / "tests" / "services"

# Max service files to process per run (token budget control)
MAX_TARGETS = 3
# Files modified within this many days
RECENCY_DAYS = 7

# Claude Code binary (macOS: installed to ~/.local/bin/claude)
CLAUDE_BIN = str(Path.home() / ".local" / "bin" / "claude")


class TddPipelineJob(AgentJob):
    name = "tdd-pipeline"
    timeout_s = 600  # 10min per file × 3 = 30min, but capped
    requires_side_effects = False

    async def run(self) -> RunResult:
        if not BACKEND_ROOT.exists():
            return RunResult(
                status="error", duration_s=self._elapsed(),
                error="backend-rag not found", side_effects=[],
            )

        # Find targets: recently modified services without tests
        targets = self._find_targets()
        self.log_step("scan_targets", outputs={"targets": len(targets)})

        if not targets:
            return RunResult(
                status="ok", duration_s=self._elapsed(),
                side_effects=self._side_effects,
                output="no_targets",
            )

        results: list[dict] = []
        for svc_file in targets[:MAX_TARGETS]:
            result = await self._run_tdd_agent(svc_file)
            results.append(result)
            self.log_step(
                "tdd_agent_done",
                inputs={"file": svc_file.name},
                outputs={"status": result.get("status"), "tests_added": result.get("tests_added", 0)},
            )
            await asyncio.sleep(2)  # brief pause between targets

        passed = sum(1 for r in results if r.get("status") == "ok")
        failed = len(results) - passed

        msg = self._compose_report(results)
        ok = await self.send_telegram(msg)
        self.log_step("telegram_sent", side_effect="tdd_report" if ok else None)

        return RunResult(
            status="ok",
            duration_s=self._elapsed(),
            side_effects=self._side_effects,
            output=json.dumps({"targets": len(targets), "processed": len(results),
                                "passed": passed, "failed": failed}),
        )

    def _find_targets(self) -> list[Path]:
        """Find recently modified service files without corresponding tests."""
        if not SERVICES_DIR.exists():
            return []

        cutoff = time.time() - (RECENCY_DAYS * 86400)
        targets = []

        for svc_file in SERVICES_DIR.rglob("*.py"):
            if svc_file.name.startswith("_") or "test" in svc_file.name:
                continue
            # Check recency
            if svc_file.stat().st_mtime < cutoff:
                continue
            # Check for corresponding test file
            rel_path = svc_file.relative_to(SERVICES_DIR)
            expected_test = TESTS_DIR / rel_path.parent / f"test_{svc_file.name}"
            if expected_test.exists():
                continue  # test exists, skip
            targets.append(svc_file)

        # Sort by modification time (most recent first)
        targets.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        return targets

    async def _run_tdd_agent(self, svc_file: Path) -> dict[str, Any]:
        """Run Claude Code TDD pipeline for a single service file."""
        rel_path = svc_file.relative_to(BACKEND_ROOT)
        test_rel = Path("backend/tests/services") / svc_file.relative_to(SERVICES_DIR).parent / f"test_{svc_file.name}"
        test_abs = BACKEND_ROOT / test_rel

        # Build the --agents JSON for the TDD pipeline
        agents_config = {
            "agents": [
                {
                    "name": "planner",
                    "model": "claude-haiku-4-5-20251001",
                    "prompt": (
                        f"Read {rel_path} and output ONLY a JSON object with: "
                        "'module_purpose' (1 sentence), "
                        "'public_functions' (list of function names to test), "
                        "'test_scenarios' (list of 3-5 test case descriptions). "
                        "No code, no explanations, JSON only."
                    ),
                    "output_key": "plan",
                },
                {
                    "name": "test_writer",
                    "model": "claude-sonnet-4-6",
                    "prompt": (
                        f"Using the plan from the planner agent, write pytest tests for {rel_path}. "
                        f"Save to {test_rel}. "
                        "Rules: PYTHONPATH=. imports, async tests with pytest-asyncio, "
                        "mock external deps (httpx, asyncpg, redis), "
                        "no database connections in tests, "
                        "test only the public API from the plan."
                    ),
                    "depends_on": ["planner"],
                },
                {
                    "name": "reviewer",
                    "model": "claude-haiku-4-5-20251001",
                    "prompt": (
                        f"Review {test_rel} for: import errors, missing fixtures, "
                        "correct async/sync annotations, proper mocking. "
                        "Fix any issues found. Report ONLY: 'LGTM' or list of fixes applied."
                    ),
                    "depends_on": ["test_writer"],
                },
            ]
        }

        prompt = (
            f"TDD pipeline for {rel_path}. "
            "Planner analyzes the service, test_writer writes tests, reviewer fixes issues. "
            f"Target: {test_rel}"
        )

        try:
            # Check if claude binary exists
            if not Path(CLAUDE_BIN).exists():
                return await self._run_tdd_simple(svc_file, test_abs, rel_path, test_rel)

            proc = await asyncio.create_subprocess_exec(
                CLAUDE_BIN,
                "--dangerously-skip-permissions",
                "-p", prompt,
                "--agents", json.dumps(agents_config),
                "--model", "claude-sonnet-4-6",
                "--output-format", "text",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(BACKEND_ROOT),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=180)
            output = stdout.decode(errors="replace").strip()

            if proc.returncode != 0:
                self.logger.warning(
                    "tdd_agent_failed",
                    file=svc_file.name,
                    returncode=proc.returncode,
                    stderr=stderr.decode(errors="replace")[:200],
                )
                return {"file": svc_file.name, "status": "error", "error": f"exit {proc.returncode}"}

            # Verify test file was created and is collectible
            tests_added = await self._verify_tests(test_abs)
            # task #17/#42 (2026-07-26): the failure branch above logs plaintext via
            # self.logger.warning; success left NO plaintext trace — log_step()'s
            # hash-on-inputs/outputs was the only record, into a state.json overwritten
            # every run. Measured: 3 months, 14 runs, 18 successful writes into the live
            # checkout, none reconstructable from any log/state/git-history. "An
            # unattended writer whose success path logs a hash cannot be held
            # accountable for anything it did." None of these three fields are PII —
            # service filenames + relative test path, same class of data the failure
            # path already logs in plaintext.
            self.logger.info(
                "tdd_agent_succeeded",
                file=svc_file.name,
                tests_added=tests_added,
                test_path=str(test_rel),
            )
            return {"file": svc_file.name, "status": "ok", "tests_added": tests_added, "output": output[:200]}

        except asyncio.TimeoutError:
            return {"file": svc_file.name, "status": "error", "error": "timeout_180s"}
        except Exception as e:
            return {"file": svc_file.name, "status": "error", "error": str(e)[:100]}

    async def _run_tdd_simple(
        self, svc_file: Path, test_abs: Path, rel_path: Path, test_rel: Path
    ) -> dict[str, Any]:
        """Fallback: invoke claude via subprocess without --agents (single-pass)."""
        try:
            if not Path(CLAUDE_BIN).exists():
                return {"file": svc_file.name, "status": "skip", "error": "claude binary not found"}

            prompt = (
                f"Write pytest tests for `{rel_path}`. "
                f"Save to `{test_rel}`. "
                "Use PYTHONPATH=. imports, mock external deps (httpx, asyncpg, redis), "
                "pytest-asyncio for async tests, no real DB connections."
            )
            proc = await asyncio.create_subprocess_exec(
                CLAUDE_BIN,
                "--dangerously-skip-permissions",
                "-p", prompt,
                "--model", "claude-sonnet-4-6",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(BACKEND_ROOT),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            if proc.returncode != 0:
                return {"file": svc_file.name, "status": "error", "error": f"exit {proc.returncode}"}
            tests_added = await self._verify_tests(test_abs)
            return {"file": svc_file.name, "status": "ok", "tests_added": tests_added}
        except Exception as e:
            return {"file": svc_file.name, "status": "error", "error": str(e)[:100]}

    async def _verify_tests(self, test_file: Path) -> int:
        """Run pytest --collect-only on the generated test file. Returns test count."""
        if not test_file.exists():
            return 0
        try:
            venv_pytest = BACKEND_ROOT / ".venv" / "bin" / "pytest"
            pytest_bin = str(venv_pytest) if venv_pytest.exists() else "pytest"
            proc = await asyncio.create_subprocess_exec(
                pytest_bin,
                str(test_file),
                "--collect-only",
                "--no-header",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(BACKEND_ROOT),
                env={**os.environ, "PYTHONPATH": str(BACKEND_ROOT)},
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            output = stdout.decode(errors="replace")
            # Count "test_" items collected
            return output.count("<Function test_")
        except Exception:
            return 0

    def _compose_report(self, results: list[dict]) -> str:
        now = datetime.now(WITA)
        passed = [r for r in results if r.get("status") == "ok"]
        failed = [r for r in results if r.get("status") != "ok"]
        icon = "✅" if not failed else "⚠️"
        lines = [
            f"{icon} <b>TDD Pipeline</b> — {len(results)} files",
            f"{now.strftime('%Y-%m-%d %H:%M WITA')}",
            "",
        ]
        for r in passed:
            n = r.get("tests_added", 0)
            lines.append(f"✅ {r['file']} (+{n} tests)")
        for r in failed:
            lines.append(f"❌ {r['file']} — {r.get('error', '?')[:60]}")
        return "\n".join(lines)

    def _elapsed(self) -> float:
        return time.time() - self.started_at


if __name__ == "__main__":
    main(TddPipelineJob)
