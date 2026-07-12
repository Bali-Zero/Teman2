"""CI gate: every mutating route must resolve to a known authorization posture.

Case OS Fase-1. A mutating route (POST/PUT/PATCH/DELETE) is COMPLIANT if it has:
  (a) an auth ``Depends`` resolver, OR
  (b) an in-body verifier call that RAISES (AST-checked, statement-level), OR
  (c) membership in ``PUBLIC_ENDPOINTS`` (deliberately open), OR
  (d) an explicit ``ROUTE_RISKS`` registry entry.

A new mutating route with none of the above FAILS this test — that is the whole
point: the 65-route hole cannot silently grow back. The registry is a declared
backlog, not runtime enforcement (see route_risk_registry.py docstring).

Two anti-decay guards (the Codex red-team's #4 concern — a registry entry that
just turns CI green is a rubber stamp):
  * every ROUTE_RISKS entry must name an owner, AND
  * no ROUTE_RISKS entry may be dead (its path+method must exist in the live app).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.app.auth.route_risk_registry import ROUTE_RISKS, risk_for
from backend.app.setup.route_walk import iter_leaf_routes
from backend.app.setup.router_registration import include_routers

MUTATING = {"POST", "PUT", "PATCH", "DELETE"}

# Structural heuristic for an auth-principal dependency name (mirrors the live
# inventory of Depends(...) verifiers across backend/app/routers/, 2026-07-12).
_AUTH_NAME_RE = re.compile(
    r"(^|_)(verify|require|get_current|authenticate|check)(_|$)"
    r"|_admin(_|$)|^admin_|(_|^)admin$|_user$|get_.*_user"
    r"|signature|_token(_|$)|_key(_|$)|_auth(_|$)|^require_|security$",
    re.IGNORECASE,
)
_SECURITY_CLASS = ("HTTPBearer", "HTTPBasic", "APIKeyHeader", "OAuth2", "security")
# Verifier calls that appear in a handler BODY and raise on failure.
_BODY_VERIFIER_RE = re.compile(
    r"(^|_)(verify|check|require|authenticate)", re.IGNORECASE
)

_ROUTERS_DIR = Path(__file__).resolve().parents[2] / "app" / "routers"


@pytest.fixture(scope="module")
def app() -> FastAPI:
    a = FastAPI()
    include_routers(a)
    return a


def _dep_names(dependant) -> list[str]:
    out: list[str] = []

    def walk(d):
        call = getattr(d, "call", None)
        if call is not None:
            out.append(getattr(call, "__qualname__", getattr(call, "__name__", str(call))))
        for sub in getattr(d, "dependencies", []):
            walk(sub)

    walk(dependant)
    return out


def _is_auth_dep(name: str) -> bool:
    if any(m in name for m in _SECURITY_CLASS):
        return True
    return bool(_AUTH_NAME_RE.search(name.split(".")[-1]))


def _call_name(call: ast.Call) -> str:
    fn = call.func
    if isinstance(fn, ast.Name):
        return fn.id
    if isinstance(fn, ast.Attribute):
        return fn.attr
    return ""


def _is_control_flow_verifier(node: ast.AST) -> bool:
    """A verifier call that actually gates control flow:
      * statement-level bare call / awaited bare call  (`verify_x(...)`)
      * inside an `if`/`elif` test                      (`if not verify_x(...):`)
      * inside an `assert`                              (`assert verify_x(...)`)
      * an argument to `raise`                          (`raise _auth_error(verify...)`)
    This DELIBERATELY excludes `x = verify_x(...)` where the result is bound and
    never used — the Codex red-team's false-pass #3 (a verifier whose bool return
    is ignored authorizes nothing). We only count calls whose value participates
    in a decision, never a dangling assignment target.
    """
    # collect Call nodes in gating positions
    gating_calls: list[ast.Call] = []
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
        gating_calls.append(node.value)
    elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Await) \
            and isinstance(node.value.value, ast.Call):
        gating_calls.append(node.value.value)
    elif isinstance(node, ast.If):
        gating_calls += [n for n in ast.walk(node.test) if isinstance(n, ast.Call)]
    elif isinstance(node, ast.Assert):
        gating_calls += [n for n in ast.walk(node.test) if isinstance(n, ast.Call)]
    elif isinstance(node, ast.Raise) and node.exc is not None:
        gating_calls += [n for n in ast.walk(node.exc) if isinstance(n, ast.Call)]
    return any(_BODY_VERIFIER_RE.search(_call_name(c)) for c in gating_calls if _call_name(c))


def _handlers_with_body_verifier() -> set[str]:
    """AST-scan every router file; return handler names whose body has a
    verifier call in a CONTROL-FLOW position (see _is_control_flow_verifier —
    guards against both the missed `if not verify(...)` under-match AND the
    ignored-return-value false-pass)."""
    authed: set[str] = set()
    for f in _ROUTERS_DIR.glob("*.py"):
        try:
            tree = ast.parse(f.read_text(), filename=str(f))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if any(_is_control_flow_verifier(stmt) for stmt in ast.walk(node)):
                authed.add(node.name)
    return authed


def _mutating_routes(app: FastAPI):
    for route in iter_leaf_routes(app):
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        if not methods or not path:
            continue
        muts = methods & MUTATING
        if muts:
            yield path, muts, getattr(route, "dependant", None), getattr(route, "endpoint", None)


def test_every_mutating_route_has_a_declared_authz_posture(app: FastAPI):
    """GUILT: an undeclared, ungated mutating route fails the build."""
    try:
        from backend.app.auth.public_endpoints import find_entry
    except Exception:
        find_entry = None

    body_authed = _handlers_with_body_verifier()
    uncovered: list[str] = []

    for path, muts, dependant, endpoint in _mutating_routes(app):
        deps = _dep_names(dependant) if dependant else []
        has_dep_auth = any(_is_auth_dep(d) for d in deps)
        has_body_auth = endpoint is not None and endpoint.__name__ in body_authed
        is_public = bool(find_entry and find_entry(path))
        has_registry = any(risk_for(path, m) for m in muts)
        if not (has_dep_auth or has_body_auth or is_public or has_registry):
            uncovered.append(f"{','.join(sorted(muts))} {path}")

    assert not uncovered, (
        f"{len(uncovered)} mutating route(s) have NO authorization posture "
        f"(no auth Depends, no body verifier, not PUBLIC, not in ROUTE_RISKS). "
        f"Add a real auth Depends, or (if intentionally team-wide) declare it in "
        f"route_risk_registry.py with an owner:\n  " + "\n  ".join(sorted(uncovered))
    )


def test_every_registry_entry_names_an_owner():
    """ANTI-DECAY #4: a registry row with no owner is a rubber stamp — reject it."""
    orphan = [r.path for r in ROUTE_RISKS if not (r.owner and r.owner.strip())]
    assert not orphan, f"ROUTE_RISKS entries missing an owner: {orphan}"


def test_no_dead_registry_entries(app: FastAPI):
    """ANTI-DECAY: a registry row whose route no longer exists is stale — the
    entry must map to a live path+method (else it silently covers nothing)."""
    live = [(p, m) for p, muts, _, _ in _mutating_routes(app) for m in muts]
    dead = []
    for r in ROUTE_RISKS:
        if not any(r.matches(p, m) for p, m in live):
            dead.append(f"{','.join(r.methods)} {r.path}")
    assert not dead, (
        "ROUTE_RISKS entries that match no live route (delete them — the route "
        "was removed or gained a real gate):\n  " + "\n  ".join(dead)
    )
