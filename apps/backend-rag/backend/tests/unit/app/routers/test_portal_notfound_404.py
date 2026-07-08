"""
Tests for portal.py not-found → 404 consistency (W89 class-fix).

SCAR CONTEXT (found via live prod E2E, 2026-07-08):
Portal endpoints resolve a client via portal_service methods that filter
`... WHERE id = $1 AND deleted_at IS NULL` and raise
`ValueError("Client N not found")` for a soft-deleted / missing client.
`get_dashboard` correctly caught that ValueError and returned 404, but the
sibling endpoints (get_visa_status, get_companies, get_tax_overview, ...)
only had a bare `except Exception → 500`, so a not-found client surfaced as
an opaque 500 (confirmed live on /api/portal/visa & /api/portal/company).

W89 class-fix: EVERY portal endpoint that resolves a client and catches
Exception must FIRST catch ValueError → 404. This test enforces the whole
class, so the next endpoint added can't silently reintroduce the 500.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROUTER_PATH = (
    Path(__file__).resolve().parents[5]
    / "backend"
    / "app"
    / "routers"
    / "portal.py"
)


def _source_lines() -> list[str]:
    return ROUTER_PATH.read_text(encoding="utf-8").split("\n")


def _endpoints_resolving_client_with_500() -> list[tuple[str, int, bool]]:
    """For each `except Exception → 500` that follows a portal_service call on
    a client, return (fn_name, lineno, has_value_error_404_sibling)."""
    src = _source_lines()
    results: list[tuple[str, int, bool]] = []
    for i, line in enumerate(src):
        if "except Exception as e:" not in line:
            continue
        block = "\n".join(src[i : i + 7])
        if "status_code=500" not in block:
            continue
        # enclosing function
        fn = "?"
        for j in range(i, max(0, i - 70), -1):
            m = re.match(r"\s*async def (\w+)", src[j])
            if m:
                fn = m.group(1)
                break
        trybody = "\n".join(src[max(0, i - 18) : i])
        resolves_client = "portal_service." in trybody and "client[" in trybody
        if not resolves_client:
            continue
        back = "\n".join(src[max(0, i - 10) : i])
        # The invariant is "a ValueError from client resolution is HANDLED as a
        # 4xx, never a raw 500". Most endpoints map it to 404 (client not
        # found); a few legitimately map it to 400 (bad-input validation, e.g.
        # set_primary_company). Either counts as handled.
        handled = "except ValueError" in back and (
            "status_code=404" in back or "status_code=400" in back
        )
        results.append((fn, i + 1, handled))
    return results


def test_every_client_resolving_endpoint_handles_value_error_not_500() -> None:
    """GUILT+class: no portal endpoint that resolves a client may fall through
    to a raw 500 on a ValueError — each must catch ValueError as a 4xx
    (404 not-found, or 400 bad-input) before `except Exception → 500`.
    """
    offenders = [
        f"{fn} (L{ln})"
        for fn, ln, handled in _endpoints_resolving_client_with_500()
        if not handled
    ]
    assert not offenders, (
        "These portal endpoints resolve a client but 500 on a ValueError "
        "(e.g. a soft-deleted client) instead of a 4xx — add "
        "`except ValueError → 404` before `except Exception → 500` "
        "(see get_dashboard):\n  " + "\n  ".join(offenders)
    )


def test_module_still_imports_and_parses() -> None:
    """INNOCENCE: the 11 inserted handlers didn't break the module."""
    tree = ast.parse(ROUTER_PATH.read_text(encoding="utf-8"))
    fns = {n.name for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef)}
    # A representative set of the endpoints we hardened must still exist.
    for fn in ("get_dashboard", "get_visa_status", "get_companies", "get_tax_overview"):
        assert fn in fns, f"expected endpoint {fn} vanished after the edit"


def test_404_handler_reraises_only_value_error_not_generic() -> None:
    """INNOCENCE: the inserted 404 blocks catch ValueError specifically (not a
    bare Exception), so genuine internal errors still surface as 500."""
    src = ROUTER_PATH.read_text(encoding="utf-8")
    # Every inserted 404 block is guarded by `except ValueError as e:` — there
    # must be no `except Exception ... status_code=404` (that would 404 real
    # server errors).
    bad = re.findall(r"except Exception as e:[^\n]*\n(?:[^\n]*\n){0,4}?[^\n]*status_code=404", src)
    assert not bad, "A generic Exception handler returns 404 — it would mask real 500s"
