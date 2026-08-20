"""
Structural registry test: which PortalService mixin methods filter
`deleted_at` (soft-deleted rows) in their own SQL, and which don't.

WHY THIS TEST EXISTS
=====================
Nine `apps/backend-rag/backend/app/routers/portal.py` endpoints catch
`ValueError` from a service call and translate it to 404, with a comment
that used to (wrongly) claim the branch covers "client soft-deleted,
portal_service filters deleted_at IS NULL" — copy-pasted from
get_dashboard, whose comment IS true. Measured on disk 2026-08-20: 9 of the
17 `except ValueError` sites in portal.py call a service method with NO
`deleted_at` filter at all, so the branch can never fire for that reason
(the corrected comments now live in portal.py itself, per endpoint).

Whether archived (soft-deleted) clients should be locked out of the rest
of the portal is a BUSINESS DECISION reserved to the owner — it is
explicitly NOT this test's, or this PR's, call to make. Adding the
`deleted_at` guard to more service methods progressively narrows portal
access for archived clients; that must be a deliberate, visible act, never
something that drifts in one PR at a time because nobody noticed a helper
method quietly grew (or lost) a `deleted_at` clause.

This test pins the CURRENT structural fact — the exact set of
PortalService mixin methods whose own SQL filters `deleted_at` — against
an explicit, named registry. It fails loudly, in EITHER direction, the
moment that set changes, so the change has to be made on purpose in a PR
a human can see, not absorbed silently.

It asserts STRUCTURE (which methods contain a `deleted_at`-filtering SQL
clause), never PROSE — a test that asserts an English sentence becomes the
owner of that claim and can keep a lie alive (this repo has been bitten by
exactly that class of bug before).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# This file lives at:
#   backend/tests/unit/services/portal/test_deleted_at_guard_registry.py
# parents[4] is `backend/`.
BACKEND_DIR = Path(__file__).resolve().parents[4]
MIXINS_DIR = BACKEND_DIR / "services" / "portal" / "_mixins"

MIXIN_FILES = ("billing.py", "dashboard.py", "documents.py", "messaging.py")

# The 10 PortalService mixin methods (class-level, non-nested) whose OWN
# SQL filters `deleted_at` today. Measured 2026-08-20 by parsing the 4
# mixin files with `ast` and attributing every `deleted_at`-mentioning
# string literal to its enclosing CLASS-LEVEL method. A nested inner `def`
# (e.g. `update_profile`'s `_val` phone-lock helper) must NOT swallow a
# guard that actually belongs to the outer method — an earlier by-hand
# count made exactly that mistake and wrongly reported `update_profile` as
# unguarded.
DELETED_AT_GUARD_REGISTRY = frozenset(
    {
        "_get_profile_data",
        "download_document",
        "get_dashboard",
        "get_documents",
        "get_visa_status",
        "restore_document",
        "send_message",
        "soft_delete_document",
        "update_profile",
        "upload_document",
    }
)


def _iter_own_body(node: ast.AST):
    """Yield `node` and every descendant that belongs to `node`'s OWN
    scope — i.e. do NOT descend into a nested function/async-function/
    lambda's body. A nested `def` is a separate scope; whatever guard it
    contains (or doesn't) belongs to IT, not to whichever outer method
    happens to contain it textually.
    """
    yield node
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        yield from _iter_own_body(child)


def _has_deleted_at_guard(method_node: ast.AST) -> bool:
    """True if any string literal in `method_node`'s own body (excluding
    nested function/lambda scopes) mentions `deleted_at`."""
    for sub in _iter_own_body(method_node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            if "deleted_at" in sub.value:
                return True
    return False


def _class_level_methods(tree: ast.Module) -> dict[str, ast.AST]:
    """Map method name -> AST node for every DIRECT (class-body-level)
    function/async-function of every class defined at module top level.
    A method nested inside another method's body (e.g. a local helper
    closure) is NOT a class-level method and is excluded here — it is
    only ever visited as part of its enclosing method's own-body walk.
    """
    methods: dict[str, ast.AST] = {}
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods[child.name] = child
    return methods


def _scan_mixins() -> dict[str, ast.AST]:
    all_methods: dict[str, ast.AST] = {}
    for filename in MIXIN_FILES:
        path = MIXINS_DIR / filename
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        methods = _class_level_methods(tree)
        overlap = set(methods) & set(all_methods)
        assert not overlap, (
            f"Method name collision across portal mixin files: {overlap} — "
            "this test assumes method names are unique across mixins "
            "(true today because they're composed via multiple "
            "inheritance into one PortalService)."
        )
        all_methods.update(methods)
    return all_methods


def test_mixin_files_exist() -> None:
    """SANITY: fail loudly (not silently-empty-pass) if the mixin layout moves."""
    for filename in MIXIN_FILES:
        assert (MIXINS_DIR / filename).is_file(), (
            f"expected portal mixin file missing: {filename}"
        )


def test_deleted_at_guard_registry_matches_disk() -> None:
    """
    Pin the exact set of PortalService mixin methods whose own SQL filters
    `deleted_at`. See module docstring for WHY.

    If this fails because a method GAINED a `deleted_at` filter: that
    progressively locks archived (soft-deleted) clients out of more of the
    portal. Whether that's correct is a business decision reserved to the
    owner (Antonello) — it has been explicitly deferred, not decided. Do
    NOT just update this registry to match; get the decision made first,
    then update DELETED_AT_GUARD_REGISTRY in the same PR as a deliberate,
    reviewable act.

    If this fails because a method LOST a `deleted_at` filter: a
    soft-deleted row that should have stayed excluded may now leak
    through that method — investigate before updating the registry.
    """
    methods = _scan_mixins()
    guarded = frozenset(name for name, node in methods.items() if _has_deleted_at_guard(node))

    missing = DELETED_AT_GUARD_REGISTRY - guarded  # registry says guarded, disk says not
    extra = guarded - DELETED_AT_GUARD_REGISTRY  # disk says guarded, registry doesn't know

    assert not missing and not extra, (
        "PortalService mixin `deleted_at`-guard set changed since the "
        "2026-08-20 registry was pinned.\n"
        f"  Registry expects guarded: {sorted(DELETED_AT_GUARD_REGISTRY)}\n"
        f"  Disk shows guarded now:   {sorted(guarded)}\n"
        f"  Lost their guard (in registry, not on disk): {sorted(missing) or 'none'}\n"
        f"  Gained a guard (on disk, not in registry):    {sorted(extra) or 'none'}\n"
        "Whether archived clients should be locked out of more of the "
        "portal is a business decision reserved to the owner — it must be "
        "made deliberately and visibly (update DELETED_AT_GUARD_REGISTRY "
        "in this same PR with the reasoning), never absorbed silently by "
        "a routine service-layer change."
    )


@pytest.mark.parametrize("method_name", sorted(DELETED_AT_GUARD_REGISTRY))
def test_registry_members_are_real_class_level_methods(method_name: str) -> None:
    """INNOCENCE: every registry name must resolve to an actual class-level
    method on disk today (catches a typo/rename in the registry itself,
    independent of the guard-detection logic above)."""
    methods = _scan_mixins()
    assert method_name in methods, (
        f"DELETED_AT_GUARD_REGISTRY names {method_name!r}, but no such "
        "class-level method exists in the portal mixin files."
    )


def test_update_profile_guard_is_not_swallowed_by_its_nested_helper() -> None:
    """
    GUILT (regression pin): `update_profile` (billing.py) has a nested
    `def _val(...)` helper INSIDE its body (phone-lock convergence loop),
    followed by its own `deleted_at IS NULL` guard as a SIBLING statement,
    not inside `_val`. An earlier by-hand measurement attributed the guard
    to the nearest preceding `def` line (`_val`) instead of the enclosing
    class-level method, and so wrongly reported `update_profile` as
    unguarded. Pin both facts directly: `_val` is nested (not class-level),
    and `update_profile` (the outer method) is correctly detected as
    guarded despite the nested def sitting between its start and its
    guard statement.
    """
    methods = _scan_mixins()
    assert "update_profile" in methods
    assert "_val" not in methods, (
        "_val is a nested closure inside update_profile's body, not a "
        "class-level method — if this fails, the source file's structure "
        "around update_profile changed; re-verify the guard-attribution "
        "logic in this file still applies to the new shape."
    )
    assert _has_deleted_at_guard(methods["update_profile"]) is True
