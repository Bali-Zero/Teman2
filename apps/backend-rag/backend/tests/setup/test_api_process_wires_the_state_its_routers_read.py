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
    # `garuda_staff_session_verifier` left this table on 2026-09-02 (PR #5584):
    # `initialize_services()` now assigns it, so the real guard judges it.
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


def _api_router_entries() -> list[tuple[str, Path]]:
    """(name, source file) for every router the manifest puts in the `api` group.

    Parsed from the manifest source rather than imported: importing the manifest
    drags in the app's settings and half the service layer, and this guard must
    stay runnable on a bare checkout.

    `import_path` is HONOURED, and that is not a nicety. Two live api-group
    entries — `notifications` and `notifications_admin` — declare
    `import_path="backend.app.modules.notifications.*"`, so the obvious
    `routers/<name>.py` guess resolves to a file that does not exist. While this
    helper made that guess, those two routers were read as the empty set: the
    guard reported "reads no garuda key" about a file it had never opened. The
    same hole is open for any future module-router, which is why resolution
    happens HERE, once, and every resolved path is asserted to exist.
    """
    src = _MANIFEST.read_text()
    out: dict[str, Path] = {}
    for chunk in re.split(r"\bRouterEntry\(", src)[1:]:
        block = chunk.split("\n    )")[0]
        name_m = re.search(r'name="([A-Za-z0-9_.]+)"', block)
        group_m = re.search(r"process_groups=(_API|_RAG|_BOTH)", block)
        if not name_m or not group_m or group_m.group(1) == "_RAG":
            continue
        name = name_m.group(1)
        override = re.search(r'import_path="([A-Za-z0-9_.]+)"', block)
        if override:
            rel = override.group(1).removeprefix("backend.").replace(".", "/")
        else:
            rel = "app/routers/" + name.replace(".", "/")
        module = _BACKEND / f"{rel}.py"
        if not module.exists():
            module = _BACKEND / rel / "__init__.py"
        assert module.exists(), (
            f"router_manifest names {name!r} but neither {_BACKEND / rel}.py nor "
            f"{_BACKEND / rel}/__init__.py exists — this guard can no longer read "
            "what it claims to read"
        )
        out[name] = module
    assert out, "parsed zero api-group RouterEntry rows — the manifest shape changed"
    return sorted(out.items())


def _garuda_state_keys_read_by(module: Path) -> set[str]:
    """`garuda_*` state keys a router module reads off `app.state`.

    Takes the RESOLVED path, never a name to be guessed at — see
    `_api_router_entries` for why a guess here is a silent loss of coverage.
    """
    src = module.read_text()
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

    @pytest.mark.parametrize(
        ("module_name", "module"), _api_router_entries(), ids=lambda v: getattr(v, "stem", v)
    )
    def test_api_router_reads_no_garuda_state_key_the_light_path_leaves_unset(
        self, module_name: str, module: Path
    ) -> None:
        """The generalisation: catches the NEXT one, not just this one.

        A router added to `_API` tomorrow that reads a `garuda_*` state key
        nothing wires on the light path fails here at collection time, instead
        of failing in production as a 503 nobody attributes to wiring.
        """
        read = _garuda_state_keys_read_by(module)
        if not read:
            pytest.skip(f"{module_name} reads no garuda_* state key")
        light = _reachable_state_keys(_LIGHT_ENTRY)
        unwired = read - light - set(_DELIBERATELY_UNWIRED)
        assert not unwired, (
            f"router {module_name} runs on the api process and reads "
            f"{sorted(unwired)} off app.state, which "
            f"{_LIGHT_ENTRY}() never assigns"
        )

    def test_no_await_separates_the_pool_from_the_garuda_wiring(self) -> None:
        """Closes a race an adversarial review found, and pins it shut.

        `fly.toml`'s `[[http_service.checks]]` routes on `/health/ready`, and for
        the light process that endpoint returns 200 the moment
        `app.state.db_pool` exists — nothing else is required. So every `await`
        between publishing the pool and wiring GARUDA is a window in which Fly
        declares this process ready and sends a real customer to a route that
        still answers 503. The first draft placed the call after the Timesheet,
        Olympus and DLQ awaits: three windows wide.

        `initialize_garuda_services` contains ZERO awaits, so calling it on the
        statement right after the pool assignment means the event loop cannot
        interleave a readiness probe between them at all. That is what makes
        this a CLOSED race and not a narrowed one — and it only holds while both
        facts hold, which is what this test checks: no await in between, and no
        await inside the helper.
        """
        tree = _module()
        fns = {
            n.name: n
            for n in tree.body
            if isinstance(n, (ast.AsyncFunctionDef, ast.FunctionDef))
        }
        helper = fns["initialize_garuda_services"]
        inner = [n for n in ast.walk(helper) if isinstance(n, (ast.Await, ast.AsyncWith, ast.AsyncFor))]
        assert not inner, (
            "initialize_garuda_services now awaits at lines "
            f"{[n.lineno for n in inner]} — the event loop can yield inside it, "
            "so the readiness race is reopened. Either keep it await-free or "
            "gate /health/ready on a wiring-complete flag instead."
        )

        light = fns[_LIGHT_ENTRY]
        nodes = list(ast.walk(light))
        pool_assign = [
            n.lineno
            for n in nodes
            if isinstance(n, ast.Assign)
            and any(
                isinstance(t, ast.Attribute)
                and t.attr == "db_pool"
                and isinstance(t.value, ast.Attribute)
                and t.value.attr == "state"
                for t in n.targets
            )
        ]
        wiring_call = [
            n.lineno
            for n in nodes
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "initialize_garuda_services"
        ]
        assert pool_assign and wiring_call, "could not locate both anchors in the light path"
        first_pool, first_wire = min(pool_assign), min(wiring_call)
        assert first_pool < first_wire, "the wiring must come AFTER the pool exists"
        between = [
            n.lineno for n in nodes if isinstance(n, ast.Await) and first_pool < n.lineno < first_wire
        ]
        assert not between, (
            f"{len(between)} await(s) at lines {between} sit between publishing "
            "app.state.db_pool and wiring GARUDA. /health/ready reports this "
            "process ready as soon as the pool exists, so each one is a window "
            "where live traffic reaches unwired routes and gets a 503."
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

        # The comment is the STATED premise; this is the MEASURED one. An
        # adversarial review made the point that a stale comment plus a
        # now-operational route is exactly how an exemption starts hiding a
        # regression. "Wired nowhere" is checkable, so check it — and note
        # WHICH failure this catches: if the key is ever wired on the full
        # path but not the light one, the exemption would otherwise mask the
        # precise api/rag inversion this whole file exists to prevent.
        for entry in (_FULL_ENTRY, _LIGHT_ENTRY):
            assert key not in _reachable_state_keys(entry), (
                f"{key} is now assigned on {entry}(), so it is no longer "
                "'wired nowhere'. Delete its _DELIBERATELY_UNWIRED row and let "
                "the real guard judge it — an exemption granted on a premise "
                "that has since become false is worse than no exemption."
            )


class TestTheWiringActuallyRuns:
    """The static guard above proves the SOURCE says it is wired. Not the same thing.

    An adversarial review made the point precisely: `ast.walk` counts an
    assignment under `if False:` as present, so a guard built on it can go green
    while production stays broken. That blindness is inherent to reading source,
    not a bug in the parsing — the answer is to also EXECUTE the thing.

    So this class calls `initialize_garuda_services` for real and asserts the
    adapters land on `app.state`. It is the complement, not a replacement: the
    static guard catches the process/manifest seam that no running app can see,
    this one catches the reachability the static guard cannot.
    """

    @pytest.mark.asyncio
    async def test_calling_the_wiring_puts_real_adapters_on_app_state(self) -> None:
        from fastapi import FastAPI

        from backend.app.setup.service_initializer import initialize_garuda_services

        class _FakePool:
            """Adapters only stash the pool at construction; nothing is queried here."""

        app = FastAPI()
        pool = _FakePool()

        await initialize_garuda_services(app, pool)

        check_store = getattr(app.state, "garuda_check_store", None)
        assert check_store is not None, (
            "initialize_garuda_services ran and left garuda_check_store unset — "
            "this is the exact condition that returned 503 in production"
        )
        assert type(check_store).__name__ != "UnconfiguredCheckStore", (
            "the fail-closed placeholder is still what a request would get"
        )
        assert getattr(app.state, "garuda_db_pool", None) is pool
        assert getattr(app.state, "garuda_magic_link_store", None) is not None
        assert getattr(app.state, "garuda_magic_session_verifier", None) is not None

    @pytest.mark.asyncio
    async def test_it_never_raises_when_there_is_no_pool(self) -> None:
        """Boot safety, executed rather than argued.

        This now runs inside the api process's startup. If it could raise, the
        cure would be worse than the disease it fixes — a 503 on one product
        would become a process that will not boot at all.
        """
        from fastapi import FastAPI

        from backend.app.setup.service_initializer import initialize_garuda_services

        app = FastAPI()
        await initialize_garuda_services(app, None)  # must not raise

        assert getattr(app.state, "garuda_check_store", None) is None, (
            "with no pool the adapters must stay unset and the routes fail closed"
        )
