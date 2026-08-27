"""The `api` process must wire every `app.state` key its own routers read.

WHY THIS FILE EXISTS. On 2026-08-27 the first action a real customer takes —
`POST /api/visa/voa/eligibility-checks` on balizero.com — answered HTTP 503
`PERSISTENCE_POLICY_UNAVAILABLE`. The cause was not the retention policy that
error names. All four GARUDA routers are `process_groups=_API`, so they are
mounted ONLY on the `api` process, which runs `initialize_services_light()`.
Every `app.state.garuda_*` adapter, however, was wired inside
`initialize_services()` — which ONLY the `rag` process runs, and which mounts
none of those routers. The two processes were exactly inverted: `rag` wired the
stores and served none of the routes, `api` served every route and wired none of
the stores. `get_garuda_check_store` therefore fell back to
`UnconfiguredCheckStore` on every single request, by construction.

WHY NO EXISTING TEST COULD SEE IT. Under pytest the application is ONE process:
the api/rag split simply does not exist, `app.dependency_overrides` supplies the
stores, and every route test passes. The defect lives in the seam between the
process manifest and the two init functions, which is exactly where no
behavioural test looks. So this guard is deliberately STATIC — it reads the
source, not a running app — because the thing it must catch is invisible to a
running app in a test.

WHAT WOULD MAKE THIS RED (the question a test that cannot fail never answers):
moving any `app.state.garuda_*` assignment back inside `initialize_services`
alone, deleting the `initialize_garuda_services` call from the light path, or
adding a new `_API` router that reads a `garuda_*` state key nothing wires.
Each is checked below and each fails loudly.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[2]
_INITIALIZER = _BACKEND / "app" / "setup" / "service_initializer.py"
_MANIFEST = _BACKEND / "app" / "setup" / "router_manifest.py"
_ROUTERS_DIR = _BACKEND / "app" / "routers"

#: The api process's entry point. `main_api.py` calls exactly this.
_LIGHT_ENTRY = "initialize_services_light"
#: The rag process's entry point, via `app_factory.lifespan`.
_FULL_ENTRY = "initialize_services"

#: State keys a router reads that NOTHING wires, deliberately and on the record.
#:
#: This exists because the guard below found one on its very first run, and the
#: honest answer was neither "delete the assertion" nor "wire it": the staff
#: late-resolution route fail-closes on purpose until a staff session surface
#: exists. An exemption that merely lists a name would rot the moment that
#: changed, so each entry must name a file AND a phrase that file still
#: contains — the justification is re-read on every run, not trusted once.
_DELIBERATELY_UNWIRED: dict[str, tuple[str, str]] = {
    "garuda_staff_session_verifier": (
        "app/routers/garuda_orders_router.py",
        "is wired nowhere today",
    ),
}


def _module() -> ast.Module:
    return ast.parse(_INITIALIZER.read_text())


def _state_assignments(node: ast.AST) -> set[str]:
    """Every `app.state.NAME = ...` assigned directly in this function body."""
    found: set[str] = set()
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Assign):
            continue
        for target in sub.targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Attribute)
                and target.value.attr == "state"
                and isinstance(target.value.value, ast.Name)
                and target.value.value.id == "app"
            ):
                found.add(target.attr)
    return found


def _local_calls(node: ast.AST, known: set[str]) -> set[str]:
    """Module-level functions from this file that the body calls."""
    called: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id in known:
            called.add(sub.func.id)
    return called


def _reachable_state_keys(entry: str) -> set[str]:
    """State keys assigned by `entry`, following calls to same-file functions.

    Transitive on purpose: the whole point of the cure is that the wiring now
    lives one call away, in `initialize_garuda_services`. A guard that only
    looked at the entry function's own body would go green on the BROKEN code
    and red on the FIXED code — precisely backwards.
    """
    tree = _module()
    fns = {
        n.name: n
        for n in tree.body
        if isinstance(n, (ast.AsyncFunctionDef, ast.FunctionDef))
    }
    assert entry in fns, f"{entry} is not a top-level function in {_INITIALIZER.name}"

    seen: set[str] = set()
    keys: set[str] = set()
    stack = [entry]
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        body = fns[name]
        keys |= _state_assignments(body)
        stack.extend(_local_calls(body, set(fns)) - seen)
    return keys


def _api_router_modules() -> list[str]:
    """Router module names the manifest puts in the `api` process group.

    Parsed from the manifest source rather than imported: importing the manifest
    drags in the app's settings and half the service layer, and this guard must
    stay runnable on a bare checkout.
    """
    src = _MANIFEST.read_text()
    entries = re.findall(
        r'name="(?P<name>[a-z0-9_]+)"[^)]*?process_groups=(?P<group>_API|_RAG|_BOTH)',
        src,
        re.DOTALL,
    )
    assert entries, "parsed zero RouterEntry rows — the manifest shape changed"
    return sorted({name for name, group in entries if group in {"_API", "_BOTH"}})


def _garuda_state_keys_read_by(module_name: str) -> set[str]:
    """`garuda_*` state keys a router module reads off `app.state`."""
    path = _ROUTERS_DIR / f"{module_name}.py"
    if not path.exists():
        return set()
    src = path.read_text()
    keys = set(re.findall(r'getattr\(\s*request\.app\.state\s*,\s*"(garuda_[a-z_]+)"', src))
    keys |= set(re.findall(r"request\.app\.state\.(garuda_[a-z_]+)", src))
    return keys


class TestTheApiProcessWiresWhatItServes:
    def test_every_garuda_state_key_the_rag_path_wires_is_wired_on_the_api_path_too(
        self,
    ) -> None:
        """The regression, stated as the asymmetry that caused the outage.

        Before the cure this assertion failed with all seven names: the full
        path wired `garuda_check_store`, `garuda_order_repository`,
        `garuda_payment_provider`, `garuda_db_pool`, `garuda_magic_link_store`,
        `garuda_magic_session_verifier` and `garuda_payment_http_client`, and
        the light path — the only one the api process runs — wired none.
        """
        full = {k for k in _reachable_state_keys(_FULL_ENTRY) if k.startswith("garuda_")}
        light = {k for k in _reachable_state_keys(_LIGHT_ENTRY) if k.startswith("garuda_")}

        assert full, (
            "found no garuda state keys on the rag init path at all — this guard "
            "has lost sight of its subject and would pass vacuously"
        )
        missing = full - light
        assert not missing, (
            "the api process mounts every GARUDA router but its init path does "
            f"not wire {sorted(missing)}. Each unwired key means a fail-closed "
            "503 on a live customer-facing route."
        )

    def test_the_shared_wiring_is_reached_from_both_entry_points(self) -> None:
        """Names the CURE, so deleting it is a failure and not a silent revert."""
        tree = _module()
        fns = {
            n.name: n
            for n in tree.body
            if isinstance(n, (ast.AsyncFunctionDef, ast.FunctionDef))
        }
        assert "initialize_garuda_services" in fns, (
            "initialize_garuda_services is gone — if the wiring was inlined back "
            "into one initializer, the api/rag inversion is back with it"
        )
        for entry in (_FULL_ENTRY, _LIGHT_ENTRY):
            assert "initialize_garuda_services" in _local_calls(fns[entry], set(fns)), (
                f"{entry} no longer calls initialize_garuda_services"
            )

    @pytest.mark.parametrize("module_name", _api_router_modules())
    def test_api_router_reads_no_garuda_state_key_the_light_path_leaves_unset(
        self, module_name: str
    ) -> None:
        """The generalisation: catches the NEXT one, not just this one.

        A router added to `_API` tomorrow that reads a `garuda_*` state key
        nothing wires on the light path fails here at collection time, instead
        of failing in production as a 503 nobody attributes to wiring.
        """
        read = _garuda_state_keys_read_by(module_name)
        if not read:
            pytest.skip(f"{module_name} reads no garuda_* state key")
        light = _reachable_state_keys(_LIGHT_ENTRY)
        unwired = read - light - set(_DELIBERATELY_UNWIRED)
        assert not unwired, (
            f"router {module_name} runs on the api process and reads "
            f"{sorted(unwired)} off app.state, which "
            f"{_LIGHT_ENTRY}() never assigns"
        )

    @pytest.mark.parametrize(
        ("key", "source_rel", "phrase"),
        [(k, v[0], v[1]) for k, v in _DELIBERATELY_UNWIRED.items()],
    )
    def test_each_deliberately_unwired_key_still_says_why(
        self, key: str, source_rel: str, phrase: str
    ) -> None:
        """An exemption must not outlive the reason it was granted.

        Without this, `_DELIBERATELY_UNWIRED` is just a list of names the guard
        agrees not to look at — indistinguishable from a defect somebody
        silenced. Here the justification is re-read every run: if the route is
        ever wired, or its comment rewritten, this goes red and the exemption
        gets revisited on purpose instead of persisting by inertia.
        """
        source = _BACKEND / source_rel
        assert source.exists(), f"{source_rel} is gone; the exemption for {key} has no basis"
        assert phrase in source.read_text(), (
            f"{source_rel} no longer says {phrase!r}. The exemption for {key} was "
            "granted on that statement — re-check whether the key is now wired "
            "(remove the exemption) or the comment simply drifted (update it)."
        )
