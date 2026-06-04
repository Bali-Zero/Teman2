"""Manifest→registration TOTAL-ORPHAN parity test (PR #422 scar antibody).

SCAR FAMILY: PRs #54/#55/#60 and #422→#424.

``router_manifest.py`` declares every router exactly once with its
``process_groups`` (the data the tests trust). ``router_registration.py``
does the *actual* runtime wiring with explicit
``api.include_router(<name>.router)`` calls inside three functions:

    include_routers(api)        — combined app  (setup/app_factory.py)
    include_light_routers(api)  — the "api" process (main_api.py, light/no-ML)
    include_heavy_routers(api)  — the "rag" process (main_rag.py, heavy/ML)

The two **deployed** Fly process groups are:
    api  → include_light_routers   (main_api.py)
    rag  → include_heavy_routers   (main_rag.py)

process_groups → the deployed function a router MUST appear in:
    "api" in process_groups  → include_light_routers
    "rag" in process_groups  → include_heavy_routers
    {"api","rag"}            → BOTH deployed functions

WHY THIS FILE EXISTS (the gap it closes)
----------------------------------------
``test_router_registration_parity.py::TestIncludeFunctionsParity`` already
guards the *asymmetric* drift: a router wired in ``include_routers`` but
missing from ``include_light_routers`` (``in_main - in_light``). But it does
NOT catch the **total-orphan** case — a manifest entry with ZERO
``include_router`` calls *anywhere*. Such a router is in neither ``in_main``
nor ``in_light``, so the set-difference passes while the endpoint 404s in
every process. That is exactly how 10 finished routers (admin_pii,
compliance_alerts, war_room_dashboard, llm_costs, research_control,
intel_observability, …) shipped invisible.

This is the prescribed-but-previously-unshipped antibody from the
PR #422/#54/#55/#60 scar family: assert that **every** manifest RouterEntry
is wired in **each deployed function** its ``process_groups`` requires.

The check is a static parse of the registration source (no app build, no
heavy imports) — fast and import-side-effect-free. It mirrors the manifest's
own process_groups → function mapping rather than a hand-maintained
allowlist, so new routers are covered automatically.

SCOPE NOTE — combined app vs deployed processes
-----------------------------------------------
``include_routers`` (the combined ``app_factory`` app) intentionally omits
some heavy/intel routers and is NOT a deployed process group, so this test
enforces parity only on the two DEPLOYED functions (light=api, heavy=rag).
The combined app is covered by a lighter "no NEW total orphan" check.

Two PRE-EXISTING production gaps (``intel_lake`` not in heavy; ``olympus``
internal router not in light) are recorded in ``_KNOWN_PREEXISTING_GAPS``
with a shrink-only ceiling so they stay VISIBLE without blocking unrelated
PRs. They are out of scope for the orphan-wiring change that added this test.

Cicatrix ref: .claude/rules/cicatrix-scars.md "Test infrastructure mock
!= production stack (Sprint 1.B 2026-05-02)".
"""

from __future__ import annotations

import inspect
import re

from backend.app.setup import router_registration
from backend.app.setup.router_manifest import ROUTER_MANIFEST

# Deployed process group → the registration function that serves it.
_DEPLOYED_FN_FOR_GROUP: dict[str, str] = {
    "api": "include_light_routers",  # main_api.py
    "rag": "include_heavy_routers",  # main_rag.py
}

# Manifest entries wired via an aliased local symbol rather than a bare
# ``api.include_router(<manifest_name>.<attr>)`` — the static (module, attr)
# matcher cannot see these. They ARE registered (the apps build); keep this
# list MINIMAL and justified.
_ALIASED_IMPORT_EXEMPT: frozenset[str] = frozenset(
    {
        "identity",  # imported as `identity_router`
        "knowledge",  # imported as `knowledge_router`
        "notifications",  # local import as `notifications_router`
        "cron_notifiers",  # local import as `cron_notifiers_router`
        "preview",  # in-body `from backend.app.routers import preview`
    }
)

# PRE-EXISTING production parity gaps, OUT OF SCOPE for the orphan-wiring PR
# that introduced this test. Recorded (not hidden) so the test is green for
# unrelated changes while the debt stays visible. Format: (name, attr, fn).
# SHRINK ONLY — fixing a gap means deleting its line, never adding one.
_KNOWN_PREEXISTING_GAPS: frozenset[tuple[str, str, str]] = frozenset(
    {
        # _BOTH router wired in light(api) but not heavy(rag) → 404 on rag.
        ("intel_lake", "router", "include_heavy_routers"),
        # _API internal router wired in combined app but not light(api).
        ("olympus", "internal_router", "include_light_routers"),
    }
)


def _registration_source() -> str:
    """Full source of router_registration.py as a single string."""
    return inspect.getsource(router_registration)


def _function_body(source: str, fn_name: str) -> str:
    """Return the source text of a single top-level function body."""
    match = re.search(rf"^def {re.escape(fn_name)}\(", source, flags=re.MULTILINE)
    assert match, f"Function {fn_name} not found in router_registration.py"
    start = match.start()
    rest = source[start + 1 :]
    nxt = re.search(r"^(def |async def |class )", rest, flags=re.MULTILINE)
    return source[start : start + 1 + nxt.start()] if nxt else source[start:]


def _wired_router_attrs(body: str) -> set[tuple[str, str]]:
    """Set of (module, attr) pairs wired via api.include_router(<module>.<attr>).

    Captures the default ``.router`` and multi-router attrs alike
    (``.webhook_router`` / ``.v1_router`` / ``.internal_router``).
    """
    pat = re.compile(r"include_router\(\s*([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)")
    return set(pat.findall(body))


class TestDeployedProcessParity:
    """Every manifest entry must be wired in each DEPLOYED function its
    process_groups require (light=api, heavy=rag).

    This is the core antibody — it catches both asymmetric drift AND the
    total-orphan case the existing parity test could not see.
    """

    def test_every_manifest_entry_wired_in_deployed_functions(self) -> None:
        source = _registration_source()
        bodies = {
            fn: _wired_router_attrs(_function_body(source, fn))
            for fn in ("include_light_routers", "include_heavy_routers")
        }

        violations: list[str] = []
        for entry in sorted(ROUTER_MANIFEST, key=lambda e: (e.name, e.attr)):
            if entry.name in _ALIASED_IMPORT_EXEMPT:
                continue
            for group in entry.process_groups:
                fn = _DEPLOYED_FN_FOR_GROUP[group]
                key = (entry.name, entry.attr)
                if key in bodies[fn]:
                    continue
                if (entry.name, entry.attr, fn) in _KNOWN_PREEXISTING_GAPS:
                    continue
                violations.append(f"  {entry.name}.{entry.attr}: missing from {fn}() [group={group}]")

        assert not violations, (
            "Manifest-declared routers with missing include_router() calls in a "
            "DEPLOYED process function (PR #422 scar class — would 404 in prod):\n"
            + "\n".join(violations)
            + '\n\nAdd `api.include_router(<name>.router)`: "api" group → '
            'include_light_routers(); "rag" group → include_heavy_routers(); '
            '{"api","rag"} → both.'
        )

    def test_known_gaps_are_real_and_shrink_only(self) -> None:
        """Each recorded pre-existing gap must (a) reference a real manifest
        entry and (b) actually still be a gap. If a gap got fixed, this fails
        and tells you to DELETE the stale line — the allowlist only shrinks.
        """
        source = _registration_source()
        bodies = {
            fn: _wired_router_attrs(_function_body(source, fn))
            for fn in ("include_light_routers", "include_heavy_routers")
        }
        manifest_keys = {(e.name, e.attr) for e in ROUTER_MANIFEST}

        stale: list[str] = []
        for name, attr, fn in sorted(_KNOWN_PREEXISTING_GAPS):
            if (name, attr) not in manifest_keys:
                stale.append(f"  {name}.{attr}: no longer in manifest — remove this known-gap line")
            elif (name, attr) in bodies.get(fn, set()):
                stale.append(f"  {name}.{attr}: now wired in {fn}() — remove this known-gap line")

        assert not stale, (
            "Stale _KNOWN_PREEXISTING_GAPS entries (the list is shrink-only):\n"
            + "\n".join(stale)
        )

    def test_known_gaps_ceiling(self) -> None:
        # Hard ceiling — forces fixing over recording. Never raise this.
        assert len(_KNOWN_PREEXISTING_GAPS) <= 2, (
            "_KNOWN_PREEXISTING_GAPS grew — a NEW parity gap was recorded "
            "instead of wired. Wire the router; do not add to the allowlist."
        )


class TestTenOrphanFixRoutersWired:
    """Explicit regression guard for the 10 routers fixed in this PR.

    Pins the exact scar instance so a future refactor dropping any of them
    fails loudly with a named list rather than a generic diff. These were the
    total orphans (zero include_router calls anywhere) that 404'd despite
    shipping the feature.
    """

    _API_GROUP = (
        "admin_email_health",
        "admin_pii",
        "compliance_alerts",
        "llm_costs",
        "research_control",
        "war_room_dashboard",
        "workspace_analytics",
    )
    _BOTH_GROUP = ("admin_rate_limit", "admin_self_healing", "intel_observability")

    def test_orphan_fix_routers_in_all_required_functions(self) -> None:
        source = _registration_source()
        main = _wired_router_attrs(_function_body(source, "include_routers"))
        light = _wired_router_attrs(_function_body(source, "include_light_routers"))
        heavy = _wired_router_attrs(_function_body(source, "include_heavy_routers"))

        missing: list[str] = []
        # _API: combined + light (the original "×2" of PR #424).
        for name in self._API_GROUP:
            if (name, "router") not in main:
                missing.append(f"{name} missing from include_routers()")
            if (name, "router") not in light:
                missing.append(f"{name} missing from include_light_routers()")
        # _BOTH: combined + light + heavy.
        for name in self._BOTH_GROUP:
            if (name, "router") not in main:
                missing.append(f"{name} missing from include_routers()")
            if (name, "router") not in light:
                missing.append(f"{name} missing from include_light_routers()")
            if (name, "router") not in heavy:
                missing.append(f"{name} missing from include_heavy_routers()")

        assert not missing, "Orphan-fix routers regressed:\n  " + "\n  ".join(missing)


class TestAliasedExemptListIsJustified:
    """Guard the aliased-import exempt list against silent growth."""

    def test_exempt_names_exist_in_manifest(self) -> None:
        manifest_names = {e.name for e in ROUTER_MANIFEST}
        stale = sorted(_ALIASED_IMPORT_EXEMPT - manifest_names)
        assert not stale, f"Exempt names no longer in manifest (remove them): {stale}"

    def test_exempt_list_stays_small(self) -> None:
        assert len(_ALIASED_IMPORT_EXEMPT) <= 6, (
            "Aliased-import exempt list grew beyond the ceiling — wire the "
            "router via api.include_router(<name>.router) instead of exempting it."
        )
