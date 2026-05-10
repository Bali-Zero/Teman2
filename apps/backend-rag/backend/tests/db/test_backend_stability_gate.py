"""Guardrails for the backend stability gate wiring."""

from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path
from types import ModuleType

BACKEND_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = BACKEND_ROOT.parents[1]


def _load_gate_module() -> ModuleType:
    script_path = BACKEND_ROOT / "scripts" / "backend_stability_gate.py"
    spec = importlib.util.spec_from_file_location("backend_stability_gate", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fly_release_command_runs_schema_audit_after_migrations() -> None:
    fly_config = tomllib.loads((BACKEND_ROOT / "fly.toml").read_text(encoding="utf-8"))
    release_command = fly_config["deploy"]["release_command"]

    migrate = "python -m backend.db.migrate apply-all"
    audit = "python -m backend.db.schema_audit"
    assert migrate in release_command
    assert audit in release_command
    assert "&&" in release_command
    assert release_command.index(migrate) < release_command.index(audit)


def test_backend_stability_gate_lists_required_packs() -> None:
    gate = _load_gate_module()
    command_text = "\n".join(" ".join(command) for command in gate.build_gate_commands())

    assert "backend.db.schema_audit" in command_text
    assert "backend/tests/db/test_migration_base_tracking.py" in command_text
    assert "backend/tests/db/test_migration_uniqueness.py" in command_text
    assert "backend/tests/db/test_schema_audit.py" in command_text
    assert "backend/tests/db/test_legacy_promotion_migrations.py" in command_text
    assert "backend/tests/db/test_migration_165.py" in command_text
    assert "backend/tests/db/test_migration_166.py" in command_text
    assert "test_lkpm_ready_pack_automation.py" in command_text
    assert "test_compliance_lkpm_readypack.py" in command_text
    assert "test_lkpm_portal_cascade.py" in command_text
    assert "test_fix_lkpm_q1_2026_client_ids.py" in command_text
    assert "backend/tests/services/rag/test_kg_langgraph.py" in command_text
    assert "backend/tests/services/rag/test_kg_subgraphs.py" in command_text
    assert "backend/tests/services/rag/test_confidence.py" in command_text


def test_ci_runs_backend_stability_gate_after_migrations() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "tests.yml").read_text(
        encoding="utf-8",
    )

    apply_migrations_idx = workflow.index("name: Apply database migrations")
    gate_idx = workflow.index("name: Run backend stability gate")
    assert apply_migrations_idx < gate_idx
    assert "python scripts/backend_stability_gate.py" in workflow
