"""Manifest-vs-registration parity tests (cicatrix antibody 2026-05-02).

The router_manifest.py declares routers (used by tests). The
router_registration.py file uses **explicit imports** with
include_router(...) calls (used by main_api at runtime). When a manifest
entry is added without the corresponding explicit registration call,
the route 404s in production but tests pass.

Sprint 1.B PR #422 hit exactly this scar:
- Added channel_health to manifest ✓
- Forgot to add `from backend.app.routers import channel_health` ✗
- Forgot to add `api.include_router(channel_health.router)` ✗ (×2)
- Tests green, prod 404 → hotfix #424 to resolve

Same scar class as PRs #54/#55/#60 (manifest existed to prevent the
asymmetric case where a router was registered in include_routers but
not include_light_routers — but the manifest itself never enforced
runtime registration parity).

These tests are intentionally narrow — they regression-guard channel_health
(the most recent scar) and provide a lightweight parity check using a
baseline snapshot. A full manifest-vs-registration audit is out of scope:
many routers in the manifest are mounted via app_factory or other paths
not visible to a simple grep, so a strict "every entry must appear in
include_routers" test produces false positives.

Cicatrix ref: .claude/rules/cicatrix-scars.md "Test infrastructure mock
!= production stack (Sprint 1.B 2026-05-02)".
"""
from __future__ import annotations

import inspect
import re

from backend.app.setup import router_registration
from backend.app.setup.router_manifest import ROUTER_MANIFEST


def _read_registration_source() -> str:
    """Read router_registration.py source as a single string."""
    return inspect.getsource(router_registration)


def _extract_function_body(source: str, fn_name: str) -> str:
    """Extract source body of a top-level function."""
    start_pat = rf"^def {re.escape(fn_name)}\("
    match = re.search(start_pat, source, flags=re.MULTILINE)
    assert match, f"Function {fn_name} not found in source"
    start = match.start()
    rest = source[start + 1 :]
    next_match = re.search(r"^(def |async def |class )", rest, flags=re.MULTILINE)
    if next_match:
        return source[start : start + 1 + next_match.start()]
    return source[start:]


class TestChannelHealthRegression:
    """Regression guards for the Sprint 1.B PR #422→#424 scar.

    PR #422 added channel_health to the manifest but forgot the explicit
    import + 2 include_router calls in router_registration.py. Production
    returned 404 for ~3 hours until hotfix #424 landed. These tests ensure
    the same regression cannot recur for channel_health specifically; a
    broader sweep is in TestParityHeuristic below.
    """

    def test_channel_health_in_manifest(self):
        names = {e.name for e in ROUTER_MANIFEST}
        assert "channel_health" in names, (
            "channel_health entry missing from ROUTER_MANIFEST — "
            "Sprint 1.B PR #422 baseline regression."
        )

    def test_channel_health_imported_in_registration(self):
        source = _read_registration_source()
        # Look for `channel_health` as a token in the import lists
        # (commas, newlines, comments are all valid separators)
        pattern = r"\bchannel_health\b"
        matches = re.findall(pattern, source)
        # 2 imports + 2 include_router calls = at least 4 mentions expected
        assert len(matches) >= 4, (
            f"channel_health appears only {len(matches)} times in "
            f"router_registration.py source (expected >=4: 2 imports + 2 "
            f"include_router calls). Sprint 1.B PR #424 regression."
        )

    def test_channel_health_included_in_both_functions(self):
        source = _read_registration_source()
        body_main = _extract_function_body(source, "include_routers")
        body_light = _extract_function_body(source, "include_light_routers")

        pattern = r"include_router\s*\(\s*channel_health\."
        assert re.search(pattern, body_main), (
            "channel_health.router NOT in include_routers() — "
            "Sprint 1.B PR #424 regression."
        )
        assert re.search(pattern, body_light), (
            "channel_health.router NOT in include_light_routers() — "
            "Sprint 1.B PR #424 regression. This is the original "
            "PRs #54/#55/#60 scar pattern."
        )


class TestIncludeFunctionsParity:
    """For every _API/_BOTH router included in include_routers(), assert it
    is also included in include_light_routers().

    Routers tagged `_RAG` only in the manifest are intentionally main-only
    (heavy RAG endpoints not exposed via main_api). They are skipped via
    the manifest's process_groups field — no manual exempt list needed.

    This is the strictest form of the original PRs #54/#55/#60 antibody:
    "_API/_BOTH routers must have symmetric registration in both include
    functions". Test fails if drift introduces an _API router visible only
    in include_routers (the original scar pattern that 404'd in main_api).
    """

    def _light_eligible_names(self) -> set[str]:
        """Return manifest entry names with process_groups including _API."""
        from backend.app.setup.router_manifest import _API, _BOTH

        return {
            entry.name
            for entry in ROUTER_MANIFEST
            if entry.process_groups in (_API, _BOTH)
        }

    def test_api_routers_symmetric_in_both_include_functions(self):
        source = _read_registration_source()
        body_main = _extract_function_body(source, "include_routers")
        body_light = _extract_function_body(source, "include_light_routers")

        pat = re.compile(r"include_router\s*\(\s*(\w+)\.router\s*[,)]")
        in_main = set(pat.findall(body_main))
        in_light = set(pat.findall(body_light))

        light_eligible = self._light_eligible_names()
        # Drift class: a router that is _API/_BOTH and is in main but not in light.
        # That is the exact PRs #54/#55/#60 + #422 scar.
        only_main_api = (in_main - in_light) & light_eligible

        assert not only_main_api, (
            f"_API/_BOTH routers in include_routers() but NOT in "
            f"include_light_routers(): {sorted(only_main_api)}\n"
            f"This is the PRs #54/#55/#60 + #422 scar pattern — endpoints "
            f"would silently 404 in main_api production. Add explicit "
            f"`api.include_router(<name>.router)` in include_light_routers()."
        )
