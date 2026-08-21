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

W89 class-fix: an endpoint that calls a service method able to raise
ValueError must catch it as a 4xx BEFORE `except Exception → 500`.

SECOND SCAR (2026-08-20): this guard used to answer BOTH of its questions by
TEXTUAL PROXIMITY, and both answers were wrong in both directions.

* "Does this block resolve a client?" was `"portal_service." in the 18 lines
  above` — a line distance. `download_document`'s service call sits 19 lines
  above its `except Exception`, so the endpoint was silently OUT of the scan
  set entirely: a false CLEAN produced by a window edge.
* "Is the ValueError handled?" was `"except ValueError" in the 10 lines
  above`. Three endpoints sat exactly 12 lines apart while the rest sat at
  10, so a PR that only added COMMENT lines pushed them out of the window and
  the guard reported them as missing a handler they plainly had — and its
  message said to "add `except ValueError → 404`", advice that, followed,
  adds a second one. It was one comment line from accusing anyone. The same
  window also credits an `except ValueError` from a DIFFERENT, nested try.

The cure is not a bigger window: both questions are now asked of the entity.

* Handled-ness is read off the parse tree: a ValueError handler counts only
  when it belongs to the SAME `try` and precedes the Exception handler —
  which is what actually decides whether Python reaches the 500.
* Scope is read off the SERVICE: the guard computes, by AST over
  `backend/services/portal/`, which methods can raise ValueError, and an
  endpoint is in scope only when it calls one of them. Measured on the live
  tree: 8 methods raise it, and only 5 endpoints call one — the other 15
  `except Exception → 500` blocks in portal.py were never this guard's
  business, and the old proxy could not tell the difference.

DECLARED LIMIT: the scan sees explicit `raise ValueError(...)` (plus one
level of transitivity through `self.<helper>()` — measured to add nothing
today). A ValueError raised implicitly by a builtin inside a service method
(`int()`, `float()`, `datetime.fromisoformat()`) is NOT modelled. That is
exactly why the defensive `except ValueError → 404` handlers on the other
endpoints are good practice: this guard does not ask for them, and does not
ask anyone to remove them either.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[5] / "backend"
ROUTER_PATH = _BACKEND / "app" / "routers" / "portal.py"
SERVICE_PKG = _BACKEND / "services" / "portal"

# A ValueError raised while resolving a client is a client-side condition. Most
# endpoints map it to 404 (not found); a few legitimately map it to 400
# (bad-input validation, e.g. set_primary_company). Either counts as handled.
CLIENT_ERROR_STATUSES = frozenset({400, 404})

# Pinned so a refactor that empties the scan FAILS instead of passing vacuously
# (W84: zero subjects traversed is not a clean verdict). These five are the
# endpoints measured to call a ValueError-raising service method on 2026-08-20.
KNOWN_IN_SCOPE_ENDPOINTS = frozenset(
    {
        "get_dashboard",
        "get_visa_status",
        "get_company_detail",
        "set_primary_company",
        "upload_document",
    }
)


def _caught_names(handler: ast.ExceptHandler) -> set[str]:
    """The exception names this handler catches (`except (A, B)` included)."""
    node = handler.type
    if node is None:  # bare `except:`
        return {"BaseException"}
    parts = node.elts if isinstance(node, ast.Tuple) else [node]
    names: set[str] = set()
    for p in parts:
        if isinstance(p, ast.Name):
            names.add(p.id)
        elif isinstance(p, ast.Attribute):
            names.add(p.attr)
    return names


def _raised_statuses(handler: ast.ExceptHandler) -> set[int]:
    """Integer `status_code=` values passed anywhere inside this handler.

    Scoped to the handler's own body, so a status raised by a nested function
    or a sibling handler cannot be credited to this one.
    """
    statuses: set[int] = set()
    for stmt in handler.body:
        for node in ast.walk(stmt):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords:
                if kw.arg == "status_code" and isinstance(kw.value, ast.Constant):
                    if isinstance(kw.value.value, int):
                        statuses.add(kw.value.value)
    return statuses


def _value_error_raising_methods(sources: dict[str, str]) -> frozenset[str]:
    """Service method names that can raise ValueError.

    Direct `raise ValueError(...)` plus one closure pass over `self.<helper>()`
    calls, so a method that delegates the raise is still in scope.
    """
    direct: dict[str, bool] = {}
    self_calls: dict[str, set[str]] = {}
    for src in sources.values():
        for cls in ast.walk(ast.parse(src)):
            if not isinstance(cls, ast.ClassDef):
                continue
            for member in cls.body:
                if not isinstance(member, (ast.AsyncFunctionDef, ast.FunctionDef)):
                    continue
                raises = any(
                    isinstance(n, ast.Raise)
                    and isinstance(n.exc, ast.Call)
                    and isinstance(n.exc.func, ast.Name)
                    and n.exc.func.id == "ValueError"
                    for n in ast.walk(member)
                )
                direct[member.name] = direct.get(member.name, False) or raises
                callees = self_calls.setdefault(member.name, set())
                for n in ast.walk(member):
                    if (
                        isinstance(n, ast.Call)
                        and isinstance(n.func, ast.Attribute)
                        and isinstance(n.func.value, ast.Name)
                        and n.func.value.id == "self"
                    ):
                        callees.add(n.func.attr)

    reachable = {name for name, raises in direct.items() if raises}
    changed = True
    while changed:
        changed = False
        for name, callees in self_calls.items():
            if name not in reachable and (callees & reachable):
                reachable.add(name)
                changed = True
    return frozenset(reachable)


def _service_sources() -> dict[str, str]:
    sources = {
        str(f): f.read_text(encoding="utf-8") for f in sorted(SERVICE_PKG.rglob("*.py"))
    }
    # Fail loud rather than scan nothing and report a clean tree (W84).
    assert sources, f"no service sources found under {SERVICE_PKG} — the scan would be blind"
    return sources


def _scan(router_source: str, risky_methods: frozenset[str]) -> list[tuple[str, int, bool]]:
    """For every `except Exception → 500` guarding a call that can raise
    ValueError, return (enclosing_function, handler_lineno, handled)."""
    results: list[tuple[str, int, bool]] = []

    for fn in ast.walk(ast.parse(router_source)):
        if not isinstance(fn, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        for node in ast.walk(fn):
            if not isinstance(node, ast.Try):
                continue
            called: set[str] = set()
            for stmt in node.body:
                for n in ast.walk(stmt):
                    if (
                        isinstance(n, ast.Call)
                        and isinstance(n.func, ast.Attribute)
                        and isinstance(n.func.value, ast.Name)
                        and n.func.value.id == "portal_service"
                    ):
                        called.add(n.func.attr)
            if not (called & risky_methods):
                continue
            for idx, handler in enumerate(node.handlers):
                catches_broad = bool(_caught_names(handler) & {"Exception", "BaseException"})
                if not (catches_broad and 500 in _raised_statuses(handler)):
                    continue
                handled = any(
                    "ValueError" in _caught_names(earlier)
                    and (_raised_statuses(earlier) & CLIENT_ERROR_STATUSES)
                    for earlier in node.handlers[:idx]
                )
                results.append((fn.name, handler.lineno, handled))
    return results


def _endpoints_at_risk() -> list[tuple[str, int, bool]]:
    return _scan(
        ROUTER_PATH.read_text(encoding="utf-8"),
        _value_error_raising_methods(_service_sources()),
    )


def test_endpoints_calling_a_value_error_raiser_map_it_to_4xx_not_500() -> None:
    """GUILT+class: an endpoint whose service call can raise ValueError must
    catch it as a 4xx (404 not-found, or 400 bad-input) before
    `except Exception → 500` — otherwise a soft-deleted client gets an opaque
    500 instead of a not-found.
    """
    offenders = [f"{fn} (L{ln})" for fn, ln, handled in _endpoints_at_risk() if not handled]
    assert not offenders, (
        "These portal endpoints call a portal_service method that raises "
        "ValueError, but 500 on it instead of a 4xx — add "
        "`except ValueError → 404` before `except Exception → 500` "
        "(see get_dashboard):\n  " + "\n  ".join(offenders)
    )


def test_the_scan_is_not_vacuous() -> None:
    """A scan that finds NOTHING would pass the class test by looking at
    nothing at all. Pin the endpoints measured to be genuinely in scope, so a
    refactor that hides them from the guard fails loudly instead."""
    in_scope = {fn for fn, _, _ in _endpoints_at_risk()}
    missing = KNOWN_IN_SCOPE_ENDPOINTS - in_scope
    assert not missing, (
        "these endpoints call a ValueError-raising service method but the scan "
        f"no longer sees them: {sorted(missing)} — the guard has gone blind"
    )


def test_the_service_scan_finds_the_known_raisers() -> None:
    """The scope predicate reads the SERVICE, so pin what it must find there."""
    risky = _value_error_raising_methods(_service_sources())
    for name in ("get_dashboard", "get_visa_status", "upload_document"):
        assert name in risky, f"{name} raises ValueError on disk but the scan missed it"
    # download_document takes client_id as a WHERE filter and returns None for a
    # missing/soft-deleted client — the endpoint already maps None to 404. It
    # must stay OUT of scope, or the guard demands a handler for an exception
    # that cannot arrive (see the SECOND SCAR note above).
    assert "download_document" not in risky


# --- the guard's own corpus: it must accuse the guilty and spare the innocent -

_RISKY = frozenset({"get_thing"})

_GUILTY = '''
async def get_thing(client):
    try:
        data = await portal_service.get_thing(client["client_id"])
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail="boom") from e
'''

# The regression that motivated the rewrite: a correct handler sitting far
# above the Exception handler. Under the old ten-line window this read as an
# offender; structurally it is plainly handled.
_INNOCENT_FAR = (
    '''
async def get_thing(client):
    try:
        data = await portal_service.get_thing(client["client_id"])
        return data
    except ValueError as e:
        # A long explanatory comment block, of exactly the kind that pushed
        # three real endpoints out of the old fixed-size look-back window.
'''
    + "        # filler\n" * 30
    + '''        raise HTTPException(status_code=404, detail="Client not found") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail="boom") from e
'''
)

# The opposite sign: a ValueError handler that belongs to a DIFFERENT try.
# Textually adjacent, structurally unrelated — the outer 500 is unguarded.
_GUILTY_NESTED = '''
async def get_thing(client):
    try:
        try:
            inner = await helper()
        except ValueError as e:
            raise HTTPException(status_code=404, detail="inner") from e
        data = await portal_service.get_thing(client["client_id"])
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail="boom") from e
'''

_INNOCENT_400 = '''
async def set_thing(client):
    try:
        data = await portal_service.get_thing(client["client_id"])
        return data
    except ValueError as e:
        raise HTTPException(status_code=400, detail="bad input") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail="boom") from e
'''

# The false CLEAN the 18-line scope window produced, and the false ACCUSATION
# my first AST rewrite produced: the service call is far from the handler AND
# the method cannot raise ValueError. Distance must not matter; the callee must.
_INNOCENT_SAFE_CALLEE = (
    '''
async def download_thing(client):
    try:
        data = await portal_service.download_thing(client["client_id"])
'''
    + "        # filler\n" * 25
    + '''        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail="boom") from e
'''
)


def test_guilt_unhandled_value_error_raiser_is_flagged() -> None:
    assert _scan(_GUILTY, _RISKY) == [("get_thing", 6, False)]


def test_innocence_handler_far_above_is_not_flagged() -> None:
    """The false accusation the line-window produced must stay dead."""
    verdicts = _scan(_INNOCENT_FAR, _RISKY)
    assert verdicts, "expected the scan to see this endpoint at all"
    assert all(handled for _, _, handled in verdicts), verdicts


def test_guilt_value_error_in_a_nested_try_does_not_count() -> None:
    """A ValueError handler from another try must not absolve the outer 500."""
    verdicts = _scan(_GUILTY_NESTED, _RISKY)
    assert [v for v in verdicts if v[2] is False], verdicts


def test_innocence_400_counts_as_handled() -> None:
    assert all(handled for _, _, handled in _scan(_INNOCENT_400, _RISKY))


def test_innocence_callee_that_cannot_raise_is_out_of_scope() -> None:
    """Distance is irrelevant; only the callee decides scope."""
    assert _scan(_INNOCENT_SAFE_CALLEE, _RISKY) == []


def test_service_scan_guilt_and_innocence() -> None:
    guilty = {"svc.py": "class S:\n    async def m(self):\n        raise ValueError('x')\n"}
    delegating = {
        "svc.py": (
            "class S:\n"
            "    async def outer(self):\n"
            "        await self.inner()\n"
            "    async def inner(self):\n"
            "        raise ValueError('x')\n"
        )
    }
    innocent = {"svc.py": "class S:\n    async def m(self):\n        return None\n"}
    assert "m" in _value_error_raising_methods(guilty)
    assert "outer" in _value_error_raising_methods(delegating)  # transitivity
    assert _value_error_raising_methods(innocent) == frozenset()


def test_module_still_imports_and_parses() -> None:
    """INNOCENCE: the inserted handlers didn't break the module."""
    tree = ast.parse(ROUTER_PATH.read_text(encoding="utf-8"))
    fns = {n.name for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef)}
    for fn in ("get_dashboard", "get_visa_status", "get_companies", "get_tax_overview"):
        assert fn in fns, f"expected endpoint {fn} vanished after the edit"


def test_404_handler_reraises_only_value_error_not_generic() -> None:
    """INNOCENCE: the inserted 404 blocks catch ValueError specifically (not a
    bare Exception), so genuine internal errors still surface as 500."""
    src = ROUTER_PATH.read_text(encoding="utf-8")
    bad = re.findall(r"except Exception as e:[^\n]*\n(?:[^\n]*\n){0,4}?[^\n]*status_code=404", src)
    assert not bad, "A generic Exception handler returns 404 — it would mask real 500s"
