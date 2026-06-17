"""Cross-stack parity guard: ALLOWED_EVENTS == FUNNEL_EVENTS ∪ APP_EVENTS.

MYTHOS defect D11: the backend allowlist covered 14 of the 32 events emitted
by packages/core/analytics/funnel-view.ts — the other 18 were silently dropped
({"ok": False, "reason": "unknown_event"}), so most funnel CTAs never reached
funnel_sessions.

MYTHOS B1 (IA-8) extends the guard to the app_* tool-funnel taxonomy
(packages/core/analytics/funnel-app.ts, APP_EVENTS): the backend allowlist is
now the UNION of both frontend consts. This test pins set EQUALITY in both
directions — any event added or removed on one side without the other fails
CI — and pins the two frontend taxonomies as disjoint.
"""

from __future__ import annotations

import re
from pathlib import Path

from backend.app.routers.analytics import (
    ALLOWED_EVENTS,
    FUNNEL_APP_EVENTS,
    FUNNEL_PAGE_EVENTS,
)


def _repo_root() -> Path:
    """Walk up from this file until the monorepo root (has packages/core)."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "packages" / "core").is_dir():
            return parent
    raise AssertionError(f"monorepo root with packages/core not found above {here}")


_ANALYTICS_DIR = _repo_root() / "packages" / "core" / "analytics"
FUNNEL_VIEW_TS = _ANALYTICS_DIR / "funnel-view.ts"
FUNNEL_APP_TS = _ANALYTICS_DIR / "funnel-app.ts"


def _extract_const_events(source_path: Path, const_name: str) -> list[str]:
    """Extract event-name string literals from `export const <NAME> = [...] as const`."""
    source = source_path.read_text(encoding="utf-8")
    match = re.search(
        rf"export const {const_name}\s*=\s*\[(.*?)\]\s*as const",
        source,
        re.DOTALL,
    )
    assert match, f"{const_name} array not found in {source_path}"
    # Strip // comments first — event names quoted inside comments (e.g. the
    # MYTHOS D5 note) must not leak into the extracted list.
    block = re.sub(r"//[^\n]*", "", match.group(1))
    return re.findall(r'"([a-z0-9_]+)"', block)


def _frontend_funnel_events() -> list[str]:
    return _extract_const_events(FUNNEL_VIEW_TS, "FUNNEL_EVENTS")


def _frontend_app_events() -> list[str]:
    return _extract_const_events(FUNNEL_APP_TS, "APP_EVENTS")


def test_funnel_source_files_exist() -> None:
    assert FUNNEL_VIEW_TS.is_file(), f"missing {FUNNEL_VIEW_TS}"
    assert FUNNEL_APP_TS.is_file(), f"missing {FUNNEL_APP_TS}"


def test_frontend_has_no_duplicate_events() -> None:
    funnel = _frontend_funnel_events()
    assert len(funnel) == len(set(funnel)), "duplicate entries in FUNNEL_EVENTS"
    app = _frontend_app_events()
    assert len(app) == len(set(app)), "duplicate entries in APP_EVENTS"


def test_frontend_taxonomies_are_disjoint() -> None:
    """Page-funnel and tool-funnel consts must never share an event name."""
    overlap = set(_frontend_funnel_events()) & set(_frontend_app_events())
    assert not overlap, f"events in BOTH FUNNEL_EVENTS and APP_EVENTS: {sorted(overlap)}"


def test_backend_page_events_match_funnel_view() -> None:
    frontend = set(_frontend_funnel_events())
    missing_in_backend = frontend - FUNNEL_PAGE_EVENTS
    stale_in_backend = FUNNEL_PAGE_EVENTS - frontend
    assert not missing_in_backend, (
        "events emitted by funnel-view.ts but DROPPED by the backend "
        f"allowlist: {sorted(missing_in_backend)}"
    )
    assert not stale_in_backend, (
        "events accepted by the backend but no longer emitted by "
        f"funnel-view.ts: {sorted(stale_in_backend)}"
    )


def test_backend_app_events_match_funnel_app() -> None:
    frontend = set(_frontend_app_events())
    missing_in_backend = frontend - FUNNEL_APP_EVENTS
    stale_in_backend = FUNNEL_APP_EVENTS - frontend
    assert not missing_in_backend, (
        "events emitted by funnel-app.ts but DROPPED by the backend "
        f"allowlist: {sorted(missing_in_backend)}"
    )
    assert not stale_in_backend, (
        "events accepted by the backend but no longer emitted by "
        f"funnel-app.ts: {sorted(stale_in_backend)}"
    )


def test_backend_allowlist_is_exactly_the_frontend_union() -> None:
    """ALLOWED_EVENTS == extracted(FUNNEL_EVENTS) ∪ extracted(APP_EVENTS), exactly."""
    union = set(_frontend_funnel_events()) | set(_frontend_app_events())
    missing_in_backend = union - ALLOWED_EVENTS
    stale_in_backend = ALLOWED_EVENTS - union
    assert not missing_in_backend, (
        f"frontend events DROPPED by the backend allowlist: {sorted(missing_in_backend)}"
    )
    assert not stale_in_backend, (
        f"backend-only events with no frontend source: {sorted(stale_in_backend)}"
    )
