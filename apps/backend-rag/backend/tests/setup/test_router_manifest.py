"""
Router Manifest integrity tests.

SCAR CONTEXT: PRs #54, #55, #60 shipped routers only in include_routers()
but missed include_light_routers() used by main_api in production.
Three endpoints silently returned 404 in prod for weeks.

These tests ensure:
1. Every router file has a manifest entry (no orphans)
2. Every manifest entry has a corresponding file (no phantoms)
3. No duplicate entries
4. Process groups are valid
5. The manifest drives actual registration correctly
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from backend.app.setup.router_manifest import (
    PROCESS_GROUPS,
    ROUTER_MANIFEST,
    RouterEntry,
    all_router_names,
    routers_for_group,
    validate_manifest,
)

# ── Path to the routers directory ──
ROUTERS_DIR = Path(__file__).resolve().parents[2] / "app" / "routers"

# Files in backend/app/routers/ that are NOT routers (whitelist)
NON_ROUTER_FILES: frozenset[str] = frozenset({
    "__init__",
    "root_endpoints",       # mounted separately in app_factory
    "audio",                # mounted separately in app_factory
    "system_observability", # mounted separately in app_factory
    "crm_migration",       # one-time migration script, not a live router
    "guardian",             # not live yet (commented out in registration)
    "memory_vector",       # orphan router — not registered anywhere (never was)
    # twitter: RE-ENABLED 2026-04-29 (P0-6 zero-crash audit) — now in manifest.
    "team_members",        # DISABLED: duplicates team.py (audit 2026-04-03)
    "rag_proxy",           # not in routers dir — lives in backend/app/
})

# Module routers (not in backend/app/routers/) — covered by import_path
# cron_notifiers IS in routers/ but uses import_path — excluded from module set
MODULE_ROUTER_NAMES: frozenset[str] = frozenset({
    "identity",
    "knowledge",
    "notifications",
})


class TestManifestIntegrity:
    """Validate manifest data integrity."""

    def test_validate_manifest_no_errors(self) -> None:
        """Manifest validation passes with no errors."""
        errors = validate_manifest()
        assert not errors, f"Manifest validation errors:\n" + "\n".join(errors)

    def test_no_duplicate_entries(self) -> None:
        """Each (name, attr) pair appears exactly once."""
        seen: dict[tuple[str, str], int] = {}
        for i, entry in enumerate(ROUTER_MANIFEST):
            key = (entry.name, entry.attr)
            if key in seen:
                pytest.fail(
                    f"Duplicate manifest entry at index {i}: "
                    f"name={entry.name}, attr={entry.attr} "
                    f"(first seen at index {seen[key]})"
                )
            seen[key] = i

    def test_process_groups_valid(self) -> None:
        """All process_groups values are from the allowed set."""
        for entry in ROUTER_MANIFEST:
            invalid = entry.process_groups - PROCESS_GROUPS
            assert not invalid, (
                f"Router '{entry.name}' has invalid process_groups: {invalid}. "
                f"Valid: {sorted(PROCESS_GROUPS)}"
            )

    def test_process_groups_non_empty(self) -> None:
        """Every router has at least one process group."""
        for entry in ROUTER_MANIFEST:
            assert entry.process_groups, (
                f"Router '{entry.name}' has empty process_groups — "
                f"it won't be registered in any process"
            )

    def test_manifest_entries_are_frozen(self) -> None:
        """RouterEntry is immutable (frozen dataclass)."""
        entry = ROUTER_MANIFEST[0]
        with pytest.raises(AttributeError):
            entry.name = "hacked"  # type: ignore[misc]


class TestRouterFileCoverage:
    """Every .py in routers/ has a manifest entry and vice versa."""

    def _router_file_names(self) -> frozenset[str]:
        """Get all Python file stems in the routers directory."""
        return frozenset(
            p.stem
            for p in ROUTERS_DIR.glob("*.py")
            if p.stem not in NON_ROUTER_FILES
        )

    def _manifest_file_names(self) -> frozenset[str]:
        """Get all router names in manifest that map to routers/ files."""
        return frozenset(
            entry.name
            for entry in ROUTER_MANIFEST
            if entry.name not in MODULE_ROUTER_NAMES
        )

    def test_all_router_files_declared_in_manifest(self) -> None:
        """Every router file has a manifest entry — no orphan routers.

        If this test fails, a router file exists but wasn't added to the
        manifest. This means it won't be registered in ANY process.
        """
        file_names = self._router_file_names()
        manifest_names = self._manifest_file_names()
        orphans = file_names - manifest_names
        assert not orphans, (
            f"Router files without manifest entry (will NOT be registered):\n"
            f"  {sorted(orphans)}\n"
            f"Add RouterEntry for each in router_manifest.py"
        )

    def test_all_manifest_entries_have_files(self) -> None:
        """Every manifest entry has a corresponding router file — no phantom entries."""
        file_names = self._router_file_names()
        manifest_names = self._manifest_file_names()
        phantoms = manifest_names - file_names
        assert not phantoms, (
            f"Manifest entries without router files (phantom registrations):\n"
            f"  {sorted(phantoms)}\n"
            f"Either create the file or remove the manifest entry"
        )


class TestRouterGroupQueries:
    """Test the manifest query functions."""

    def test_routers_for_api(self) -> None:
        """API group returns entries."""
        api_routers = routers_for_group("api")
        assert len(api_routers) > 0
        assert all("api" in r.process_groups for r in api_routers)

    def test_routers_for_rag(self) -> None:
        """RAG group returns entries."""
        rag_routers = routers_for_group("rag")
        assert len(rag_routers) > 0
        assert all("rag" in r.process_groups for r in rag_routers)

    def test_invalid_group_raises(self) -> None:
        """Unknown process group raises ValueError."""
        with pytest.raises(ValueError, match="Unknown process group"):
            routers_for_group("invalid")

    def test_both_group_routers_exist(self) -> None:
        """Some routers should be in both groups (health, handlers)."""
        both = [r for r in ROUTER_MANIFEST if r.process_groups == frozenset({"api", "rag"})]
        both_names = {r.name for r in both}
        assert "health" in both_names, "health router must be in both api and rag"
        assert "handlers" in both_names, "handlers router must be in both api and rag"

    def test_all_router_names(self) -> None:
        """all_router_names returns non-empty frozenset."""
        names = all_router_names()
        assert isinstance(names, frozenset)
        assert len(names) > 50, f"Expected 50+ unique router names, got {len(names)}"

    def test_api_and_rag_union_covers_manifest(self) -> None:
        """Union of api + rag groups covers all manifest entries."""
        api_set = set(routers_for_group("api"))
        rag_set = set(routers_for_group("rag"))
        union = api_set | rag_set
        assert set(ROUTER_MANIFEST) == union, (
            "Some manifest entries are not in any process group"
        )


class TestModuleRouterImports:
    """Module routers (identity, knowledge, notifications) have valid import paths."""

    def test_module_routers_have_import_path(self) -> None:
        """Module routers must specify import_path."""
        for entry in ROUTER_MANIFEST:
            if entry.name in MODULE_ROUTER_NAMES:
                assert entry.import_path is not None, (
                    f"Module router '{entry.name}' must have import_path set"
                )

    @pytest.mark.parametrize(
        "name",
        [e.name for e in ROUTER_MANIFEST if e.import_path is not None],
    )
    def test_module_import_path_resolves(self, name: str) -> None:
        """Each import_path resolves to a real module."""
        entries = [e for e in ROUTER_MANIFEST if e.name == name and e.import_path]
        for entry in entries:
            try:
                mod = importlib.import_module(entry.import_path)
                assert hasattr(mod, entry.attr), (
                    f"Module {entry.import_path} has no attribute '{entry.attr}'"
                )
            except ImportError as exc:
                pytest.fail(
                    f"Cannot import {entry.import_path} for router '{entry.name}': {exc}"
                )
