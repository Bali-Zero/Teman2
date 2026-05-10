#!/usr/bin/env python3
"""Run the backend stability gate used by CI and local pre-deploy checks."""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def build_gate_commands() -> list[list[str]]:
    """Return stability-gate commands in execution order."""
    python = sys.executable
    return [
        [
            python,
            "-m",
            "py_compile",
            "backend/db/schema_audit.py",
            "backend/db/repositories/client_repository.py",
            "backend/db/migration_manager.py",
            "backend/db/migration_base.py",
        ],
        [python, "-m", "backend.db.schema_audit"],
        [
            python,
            "-m",
            "pytest",
            "backend/tests/db/test_migration_uniqueness.py",
            "backend/tests/db/test_schema_audit.py",
            "backend/tests/db/test_legacy_promotion_migrations.py",
            "backend/tests/db/test_migration_165.py",
            "backend/tests/db/test_migration_166.py",
            "tests/test_migrations.py",
            "-q",
        ],
        [
            python,
            "-m",
            "pytest",
            "backend/tests/services/compliance/test_lkpm_ready_pack_automation.py",
            "backend/tests/app/routers/test_compliance_lkpm_readypack.py",
            "backend/tests/services/compliance/test_lkpm_portal_cascade.py",
            "backend/tests/unit/scripts/test_fix_lkpm_q1_2026_client_ids.py",
            "-q",
        ],
        [
            python,
            "-m",
            "pytest",
            "backend/tests/services/rag/test_kg_langgraph.py",
            "backend/tests/services/rag/test_kg_subgraphs.py",
            "backend/tests/services/rag/test_confidence.py",
            "-q",
        ],
    ]


def run_commands(commands: list[list[str]], *, dry_run: bool = False) -> int:
    """Run commands sequentially and return the first non-zero exit code."""
    for command in commands:
        logger.info("backend_stability_gate.run command=%s", " ".join(command))
        if dry_run:
            continue
        completed = subprocess.run(command, cwd=BACKEND_ROOT, check=False)
        if completed.returncode != 0:
            logger.error(
                "backend_stability_gate.failed command=%s exit_code=%s",
                " ".join(command),
                completed.returncode,
            )
            return completed.returncode
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log commands without executing them.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _build_parser().parse_args(argv)
    return run_commands(build_gate_commands(), dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
