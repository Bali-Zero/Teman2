"""Regression test for the 2026-04-29 incident.

Failure mode: drive_poll_service.py called `await drive_service.get_file_metadata(...)`
on a `ServiceAccountDriveService` instance that did not implement that method,
flooding the event loop with AttributeErrors and stalling the FastAPI lifespan.

This test parses drive_poll_service.py with the ast module, extracts every
method invoked on the local variable `drive_service`, and asserts that
ServiceAccountDriveService exposes each one. It will fail at PR-check time
before deploy, regardless of which method is added or renamed in the future.

Memories: 1865 / 1867 / 1870. Scar: .claude/rules/cicatrix-scars.md.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from backend.services.integrations.service_account_drive_service import (
    ServiceAccountDriveService,
)

DRIVE_VAR_NAMES = {"drive_service", "self.drive_service", "self._drive_service"}
DRIVE_POLL_PATH = (
    Path(__file__).resolve().parents[4]
    / "services"
    / "crm"
    / "drive_poll_service.py"
)

# Attributes accessed but not invoked as methods on the client (e.g. raw
# google-api-python-client `service` handle). These are documented escape
# hatches, not part of the abstract drive-client contract.
WHITELIST_ATTRIBUTES: set[str] = {"service"}


def _collect_drive_service_methods(source: str) -> set[str]:
    tree = ast.parse(source)
    methods: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        # Match `drive_service.<method>(...)`
        if isinstance(func.value, ast.Name) and func.value.id == "drive_service":
            methods.add(func.attr)
        # Match `self.drive_service.<method>(...)` and `self._drive_service.<method>(...)`
        elif (
            isinstance(func.value, ast.Attribute)
            and isinstance(func.value.value, ast.Name)
            and func.value.value.id == "self"
            and func.value.attr in {"drive_service", "_drive_service"}
        ):
            methods.add(func.attr)

    return methods - WHITELIST_ATTRIBUTES


def test_service_account_drive_service_implements_all_methods_called_by_drive_poll() -> None:
    assert DRIVE_POLL_PATH.exists(), f"drive_poll_service.py not found at {DRIVE_POLL_PATH}"

    source = DRIVE_POLL_PATH.read_text(encoding="utf-8")
    invoked = _collect_drive_service_methods(source)
    assert invoked, "AST extraction returned 0 methods — extractor is broken or file structure changed"

    implemented = {
        name
        for name, _ in inspect.getmembers(ServiceAccountDriveService, predicate=callable)
        if not name.startswith("_")
    }

    missing = sorted(invoked - implemented)
    assert not missing, (
        f"drive_poll_service.py calls these methods on drive_service that "
        f"ServiceAccountDriveService does NOT implement: {missing}. "
        f"This is the exact bug class of the 2026-04-29 incident "
        f"(memory 1865 — backend lifespan stuck on missing get_file_metadata)."
    )


def test_get_file_metadata_is_present_on_service_account_drive_service() -> None:
    # Pinned regression — fails fast if the 2026-04-29 hotfix is reverted.
    assert hasattr(ServiceAccountDriveService, "get_file_metadata"), (
        "ServiceAccountDriveService.get_file_metadata is required by "
        "drive_poll_service. Removing it reproduces the 2026-04-29 outage. "
        "See commit 720d54f5c."
    )


@pytest.mark.parametrize(
    "method_name",
    [
        "get_start_page_token",
        "list_changes_since",
        "get_file_metadata",
    ],
)
def test_drive_client_contract(method_name: str) -> None:
    # Pinned contract: any future drive client implementation MUST expose these.
    # If you rename one of these methods, update drive_poll_service AND this list.
    assert hasattr(ServiceAccountDriveService, method_name), (
        f"ServiceAccountDriveService is missing the contract method '{method_name}'."
    )
