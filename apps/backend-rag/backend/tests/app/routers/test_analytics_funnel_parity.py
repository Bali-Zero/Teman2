"""Cross-stack parity guard: ALLOWED_EVENTS == FUNNEL_EVENTS (funnel-view.ts).

MYTHOS defect D11: the backend allowlist covered 14 of the 32 events emitted
by packages/core/analytics/funnel-view.ts — the other 18 were silently dropped
({"ok": False, "reason": "unknown_event"}), so most funnel CTAs never reached
funnel_sessions. This test pins set EQUALITY in both directions: any event
added or removed on one side without the other fails CI.
"""

from __future__ import annotations

import re
from pathlib import Path

from backend.app.routers.analytics import ALLOWED_EVENTS


def _repo_root() -> Path:
    """Walk up from this file until the monorepo root (has packages/core)."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "packages" / "core").is_dir():
            return parent
    raise AssertionError(f"monorepo root with packages/core not found above {here}")


FUNNEL_VIEW_TS = _repo_root() / "packages" / "core" / "analytics" / "funnel-view.ts"


def _frontend_events() -> list[str]:
    source = FUNNEL_VIEW_TS.read_text(encoding="utf-8")
    match = re.search(
        r"export const FUNNEL_EVENTS\s*=\s*\[(.*?)\]\s*as const",
        source,
        re.DOTALL,
    )
    assert match, f"FUNNEL_EVENTS array not found in {FUNNEL_VIEW_TS}"
    return re.findall(r'"([a-z0-9_]+)"', match.group(1))


def test_funnel_view_ts_exists() -> None:
    assert FUNNEL_VIEW_TS.is_file(), f"missing {FUNNEL_VIEW_TS}"


def test_frontend_has_no_duplicate_events() -> None:
    events = _frontend_events()
    assert len(events) == len(set(events)), "duplicate entries in FUNNEL_EVENTS"


def test_backend_allowlist_matches_frontend_funnel_events() -> None:
    frontend = set(_frontend_events())
    missing_in_backend = frontend - ALLOWED_EVENTS
    stale_in_backend = ALLOWED_EVENTS - frontend
    assert not missing_in_backend, (
        "events emitted by funnel-view.ts but DROPPED by the backend "
        f"allowlist: {sorted(missing_in_backend)}"
    )
    assert not stale_in_backend, (
        "events accepted by the backend but no longer emitted by "
        f"funnel-view.ts: {sorted(stale_in_backend)}"
    )
