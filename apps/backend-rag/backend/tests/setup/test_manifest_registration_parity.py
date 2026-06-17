"""Manifest ↔ registration parity tests (Antibody Debt ledger #5, 2026-06-13).

SCAR CONTEXT (PR #422 → hotfix #423/#424, 2026-05-02): a router landed in
router_manifest.py but router_registration.py uses EXPLICIT imports +
api.include_router(...) calls — the manifest entry without matching include
calls shipped a silent 404 to prod (and PRs #54/#55/#60 hit the same class
before: present in include_routers() but missing from include_light_routers()
used by main_api in production).

test_router_manifest.py validates the manifest INTERNALLY; nothing validated
that the manifest and the three include_* functions stay in lockstep. These
tests parse router_registration.py with ast (no app boot, no env needed) and
assert bidirectional parity per process group:

  - every manifest entry for group "api" is included in BOTH include_routers()
    (monolithic, app_factory) and include_light_routers() (main_api prod);
  - every manifest entry for group "rag" is included in BOTH include_routers()
    and include_heavy_routers() (main_rag prod);
  - every include_router(...) target in each function maps back to a manifest
    entry of the right group (no undeclared routers).

Conditional includes (debug, autonomous_lab) are still statically present in
the AST, so condition-gated entries are matched like any other.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from backend.app.setup.router_manifest import ROUTER_MANIFEST, RouterEntry

SETUP_DIR = Path(__file__).resolve().parents[2] / "app" / "setup"
REGISTRATION_PATH = SETUP_DIR / "router_registration.py"

# Targets included by a registration function that are deliberately NOT in the
# manifest. Keep this list EMPTY unless a special mount is verified intentional
# — every addition needs a comment with the reason.
UNDECLARED_ALLOWLIST: frozenset[tuple[str, str]] = frozenset()


# ── AST extraction ────────────────────────────────────────────────────────────


def _load_functions() -> dict[str, ast.FunctionDef]:
    tree = ast.parse(REGISTRATION_PATH.read_text())
    fns = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing = {"include_routers", "include_light_routers", "include_heavy_routers"} - set(fns)
    assert not missing, f"router_registration.py lost function(s): {missing}"
    return fns


def _alias_map(fn: ast.FunctionDef) -> dict[str, tuple[str, str]]:
    """local name -> (module path, original imported name)."""
    aliases: dict[str, tuple[str, str]] = {}
    for node in ast.walk(fn):
        if isinstance(node, ast.ImportFrom) and node.module:
            for a in node.names:
                aliases[a.asname or a.name] = (node.module, a.name)
    return aliases


def _include_targets(fn: ast.FunctionDef) -> set[tuple[str, str]]:
    """Resolve every `<x>.include_router(<target>)` in fn to
    (module_import_path, router_attr) using the function-local imports."""
    aliases = _alias_map(fn)
    targets: set[tuple[str, str]] = set()
    unresolved: list[str] = []
    for node in ast.walk(fn):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "include_router"
            and node.args
        ):
            continue
        arg = node.args[0]
        if isinstance(arg, ast.Attribute) and isinstance(arg.value, ast.Name):
            # e.g. `auth.router`, `debug.v1_router` — `auth` imported via
            # `from backend.app.routers import (auth, ...)`
            src = aliases.get(arg.value.id)
            if src:
                targets.add((f"{src[0]}.{src[1]}", arg.attr))
            else:
                unresolved.append(ast.dump(arg))
        elif isinstance(arg, ast.Name):
            # e.g. `identity_router` — imported via
            # `from backend.app.modules.identity.router import router as identity_router`
            src = aliases.get(arg.id)
            if src:
                targets.add((src[0], src[1]))
            else:
                unresolved.append(arg.id)
        else:
            unresolved.append(ast.dump(arg))
    assert not unresolved, (
        f"{fn.name}: include_router target(s) this parser cannot resolve "
        f"(extend the test, do not ignore): {unresolved}"
    )
    return targets


def _entry_key(entry: RouterEntry) -> tuple[str, str]:
    module_path = entry.import_path or f"backend.app.routers.{entry.name}"
    return (module_path, entry.attr)


def _entries_for(group: str) -> list[RouterEntry]:
    return [e for e in ROUTER_MANIFEST if group in e.process_groups]


FNS = _load_functions()
TARGETS = {name: _include_targets(fn) for name, fn in FNS.items()}


# ── Manifest → registration (the #424 / #54-#55-#60 killer) ─────────────────


class TestManifestEntriesAreRegistered:
    @pytest.mark.parametrize("entry", _entries_for("api"), ids=lambda e: f"{e.name}.{e.attr}")
    def test_api_entry_in_monolithic_include(self, entry: RouterEntry) -> None:
        assert _entry_key(entry) in TARGETS["include_routers"], (
            f"manifest entry {entry.name} (attr={entry.attr}, groups=api) has NO "
            f"include_router call in include_routers() — scar #424 class"
        )

    @pytest.mark.parametrize("entry", _entries_for("api"), ids=lambda e: f"{e.name}.{e.attr}")
    def test_api_entry_in_light_include(self, entry: RouterEntry) -> None:
        assert _entry_key(entry) in TARGETS["include_light_routers"], (
            f"manifest entry {entry.name} (attr={entry.attr}, groups=api) missing "
            f"from include_light_routers() — main_api PROD would 404 (scar #54/#55/#60 class)"
        )

    @pytest.mark.parametrize("entry", _entries_for("rag"), ids=lambda e: f"{e.name}.{e.attr}")
    def test_rag_entry_in_monolithic_include(self, entry: RouterEntry) -> None:
        assert _entry_key(entry) in TARGETS["include_routers"], (
            f"manifest entry {entry.name} (attr={entry.attr}, groups=rag) has NO "
            f"include_router call in include_routers()"
        )

    @pytest.mark.parametrize("entry", _entries_for("rag"), ids=lambda e: f"{e.name}.{e.attr}")
    def test_rag_entry_in_heavy_include(self, entry: RouterEntry) -> None:
        assert _entry_key(entry) in TARGETS["include_heavy_routers"], (
            f"manifest entry {entry.name} (attr={entry.attr}, groups=rag) missing "
            f"from include_heavy_routers() — main_rag PROD would 404"
        )


# ── Registration → manifest (no undeclared routers) ─────────────────────────


class TestRegisteredTargetsAreDeclared:
    def _undeclared(self, fn_name: str, group: str | None) -> set[tuple[str, str]]:
        if group is None:
            declared = {_entry_key(e) for e in ROUTER_MANIFEST}
        else:
            declared = {_entry_key(e) for e in _entries_for(group)}
        return TARGETS[fn_name] - declared - UNDECLARED_ALLOWLIST

    def test_monolithic_targets_declared(self) -> None:
        extra = self._undeclared("include_routers", None)
        assert not extra, (
            f"include_routers() mounts router(s) absent from ROUTER_MANIFEST "
            f"(declare them or allowlist with a reason): {sorted(extra)}"
        )

    def test_light_targets_declared_as_api(self) -> None:
        extra = self._undeclared("include_light_routers", "api")
        assert not extra, (
            f"include_light_routers() mounts router(s) not declared with "
            f"process_groups containing 'api': {sorted(extra)}"
        )

    def test_heavy_targets_declared_as_rag(self) -> None:
        extra = self._undeclared("include_heavy_routers", "rag")
        assert not extra, (
            f"include_heavy_routers() mounts router(s) not declared with "
            f"process_groups containing 'rag': {sorted(extra)}"
        )


# ── Self-checks on the parser (the verifier must be verifiable) ──────────────


class TestParserSanity:
    def test_extraction_found_a_plausible_volume(self) -> None:
        """323 include_router calls existed at authoring time; a parser
        regression that silently extracts ~0 targets must fail loudly."""
        assert len(TARGETS["include_routers"]) > 50
        assert len(TARGETS["include_light_routers"]) > 30
        assert len(TARGETS["include_heavy_routers"]) > 5

    def test_known_multi_attr_module_resolved(self) -> None:
        """instagram_chat declares router AND webhook_router — both must be
        seen as distinct targets (attr-level parity, not module-level)."""
        mono = TARGETS["include_routers"]
        assert ("backend.app.routers.instagram_chat", "router") in mono
        assert ("backend.app.routers.instagram_chat", "webhook_router") in mono

    def test_known_module_router_resolved(self) -> None:
        """identity is a module router imported as a bare alias name."""
        assert ("backend.app.modules.identity.router", "router") in TARGETS["include_routers"]
