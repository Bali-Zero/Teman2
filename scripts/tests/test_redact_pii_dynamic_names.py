from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path


REDACTOR_PATH = Path(__file__).resolve().parents[1] / "_redact_pii.py"


def _import_redactor():
    sys.modules.pop("_redact_pii", None)
    spec = importlib.util.spec_from_file_location("_redact_pii", REDACTOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["_redact_pii"] = module
    spec.loader.exec_module(module)
    return module


def test_dynamic_company_names_query_uses_existing_company_name_column(
    monkeypatch,
) -> None:
    redactor = _import_redactor()
    queries: list[str] = []

    def fake_run(args, **kwargs):
        queries.append(args[3])
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setenv("DATABASE_URL", "postgres://example")
    monkeypatch.setattr(redactor.subprocess, "run", fake_run)

    redactor.Redactor.load_default()

    assert "SELECT company_name FROM companies WHERE company_name IS NOT NULL;" in queries
    assert "SELECT name FROM companies WHERE name IS NOT NULL;" not in queries
