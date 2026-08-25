"""Contract-parity gate: the LIVE generated OpenAPI schema for the GARUDA VOA
public router vs the FROZEN, orchestrator-owned contract
(`products/garuda-voa/contracts/openapi.yaml`).

Measured 2026-08-24/25: nothing anywhere compared the two. The workflow that
LOOKS like it does (`garuda-contract-parity.yml`) installs only pytest+pyyaml
and never imports FastAPI — its suite is a `yaml.safe_load` of the frozen
file checked against itself, so it always agreed with itself while the
router's real, generated schema drifted on every operation it exposes:

    createEligibilityCheck : live {201,422}      frozen {201,400,404,409,422,429,500,503}
    getEligibilityResult   : live {200,422}      frozen {200,404,500,503}
    deleteEligibilityResult: live {204,422}      frozen {204,400,404,409,500,503}

Cause: none of the three route decorators in `garuda_voa_public.py` passes
`responses=`, so FastAPI documents only its own defaults (success + the
auto-422 from body/path validation) — the router's own `_error()` call sites
return bare `JSONResponse`s FastAPI's schema generator cannot see. That half
is fixed (`_error_responses()`, keyed off `_ERROR_CATALOG`).

The 422 on GET/DELETE was itself bogus — `result_id` is a plain `str`
checked by hand-rolled regex inside the handler, so no code path can ever
produce that 422 — and a first attempt at this file's `_live_operations()`
built the schema via a router-file helper (`garuda_voa_public.install_router`)
that patched `app.openapi()` to strip it. That helper was never called from
`router_registration.py` (production mounts this router with a bare
`api.include_router(...)`), so the gate went green on a schema the deployed
app never served — the exact defect this file exists to catch, reproduced by
its own fix, in the same file, within the hour. `install_router` is deleted;
see the note in `garuda_voa_public.py` next to `_public_enabled()`.

Fixed properly 2026-08-25: the strip lives in the two real app factories
(`app_factory.py::create_app()` and `main_api.py::create_api_app()`), chained
after any existing `app.openapi` wrapper — never replacing one — via
`garuda_voa_public.strip_unreachable_validation_errors`, scoped to exactly
`{"getEligibilityResult", "deleteEligibilityResult"}`. This file's
`_live_operations()` therefore builds the schema from the actual deployed
`main_api` singleton (see its docstring for why, and for the demonstrated
cost) rather than any bare `include_router` — a bare include would never see
the factory-level strip and would silently regress to exactly the failure
mode this paragraph describes.

Deliberately lives HERE, not under `products/garuda-voa/contracts/tests/`:
that tree's own CI workflow installs only pytest+pyyaml (see its header
comment) — a test importing FastAPI there would either ERROR the job or,
with `pytest.importorskip`, SKIP into silence (cicatrix #2, "esiste !=
armato" — the exact failure mode that workflow's own header warns about for
its sibling tests). This file needs the real app, so it lives where FastAPI
is already a first-class dependency and is picked up by the full backend
suite as a REQUIRED PR check: `tests.yml` -> `scripts/ci/shard_tests.py`
`enumerate_tests()` globs `backend/tests/**/*.py` matching `test_*.py`
(`_is_test_file`), no allowlist, no opt-in — this file did not need to be
named anywhere for that to be true, which is the property `products/**`
never had.

`pytest.importorskip` is FORBIDDEN in this file on purpose: if fastapi or
pyyaml cannot import in this environment, that is a gate failure, not a
skip — this repo already has one gate that skipped by exactly this
mechanism (`products/garuda-voa/contracts/tests/test_contract_invariants.py`
before its own hardening) and one instance of that pattern in a live
codebase is the whole lesson.
"""

from __future__ import annotations

from pathlib import Path

import yaml

# Importing this module BUILDS the deployed `main_api` FastAPI app as a
# side effect (`app = create_api_app()` at its own module scope) — the same
# thing that happens when uvicorn imports `main_api:app` in production.
# That is the point: see `_live_operations` below for why a lighter build
# would not prove what this file needs proven. Paid once per pytest worker
# (Python caches the import), not once per test function.
from backend.app import main_api as _main_api_module

_CONTRACT_PATH = (
    Path(__file__).resolve().parents[6]
    / "products"
    / "garuda-voa"
    / "contracts"
    / "openapi.yaml"
)

# operationIds this router MOUNTS today (garuda_voa_public.py module
# docstring: "Implements exactly three operations"). Everything else the
# frozen contract declares (magic-link, intake documents, orders, webhooks,
# staff practice transitions) belongs to a lane with no router landed yet —
# the contract is contract-first and is allowed to be ahead of the build.
_MOUNTED_OPERATION_IDS = frozenset(
    {
        "createEligibilityCheck",
        "getEligibilityResult",
        "deleteEligibilityResult",
    }
)


def _frozen_schema() -> dict:
    with _CONTRACT_PATH.open() as handle:
        return yaml.safe_load(handle)


def _operations_by_id(schema: dict) -> dict[str, tuple[str, str, set[str]]]:
    """operationId -> (path, HTTP method, {response status codes as str}).

    Same shape read off either an OpenAPI document loaded from YAML or one
    FastAPI generates in-process — both are plain `paths -> method -> op`
    dicts with a `responses` map keyed by status code.
    """
    out: dict[str, tuple[str, str, set[str]]] = {}
    for path, methods in schema["paths"].items():
        if not isinstance(methods, dict):
            continue
        for method, op in methods.items():
            if not isinstance(op, dict):
                continue
            op_id = op.get("operationId")
            if op_id is None:
                continue
            codes = {str(code) for code in op.get("responses", {})}
            out[op_id] = (path, method.upper(), codes)
    return out


def _live_operations() -> dict[str, tuple[str, str, set[str]]]:
    """Build the schema from `main_api.app` — the literal object `uvicorn
    backend.app.main_api:app` serves in production (`create_api_app()`
    called once at module scope; see the import at the top of this file).

    NOT a bare `include_router`, and NOT a throwaway `FastAPI()` +
    `include_light_routers()` either — the fix this file exists to prove
    (`strip_unreachable_validation_errors`) is chained onto `app.openapi`
    INSIDE `create_api_app()` / `create_app()`, not inside router mounting.
    A bare include or a router-mounting-only build would skip that wrap
    entirely and this gate would go green on a schema the deployed app does
    not serve — precisely the defect `install_router` caused (see module
    docstring). There is no cheaper build that still exercises the wrap.

    Cost, demonstrated 2026-08-25 rather than assumed: building
    `main_api.app` (560 paths, full middleware/logging/service init) took
    ~22-28s wall on this machine, vs ~20s for a bare `include_light_routers`
    build that would NOT have exercised the openapi wrap. Since the cheaper
    build cannot prove the thing this file checks, there was no real
    trade-off to make — approved explicitly (Zero/team-lead, 2026-08-25) as
    the cost of correctness. Paid once per pytest worker via the module-level
    import above, not once per test function in this file.
    """
    return _operations_by_id(_main_api_module.app.openapi())


def test_contract_file_is_readable_and_declares_mounted_operations():
    """Guilt+innocence anchor for the fixture itself (cicatrix #6/#2): if this
    fails, the two parametrized tests below would otherwise report a
    misleading per-operation KeyError instead of "the fixture is broken"."""
    frozen_ops = _operations_by_id(_frozen_schema())
    missing = _MOUNTED_OPERATION_IDS - frozen_ops.keys()
    assert not missing, f"frozen contract no longer declares: {sorted(missing)}"


def test_live_router_exposes_every_mounted_operation():
    live_ops = _live_operations()
    missing = _MOUNTED_OPERATION_IDS - live_ops.keys()
    assert not missing, f"live router no longer exposes: {sorted(missing)}"


def test_live_status_codes_match_frozen_contract_for_create_eligibility_check():
    _assert_status_parity("createEligibilityCheck")


def test_live_status_codes_match_frozen_contract_for_get_eligibility_result():
    _assert_status_parity("getEligibilityResult")


def test_live_status_codes_match_frozen_contract_for_delete_eligibility_result():
    _assert_status_parity("deleteEligibilityResult")


def _assert_status_parity(operation_id: str) -> None:
    frozen_ops = _operations_by_id(_frozen_schema())
    live_ops = _live_operations()
    frozen_path, frozen_method, frozen_codes = frozen_ops[operation_id]
    live_path, live_method, live_codes = live_ops[operation_id]
    assert (live_path, live_method) == (frozen_path, frozen_method), (
        f"{operation_id}: path/method drifted — "
        f"live={live_method} {live_path} frozen={frozen_method} {frozen_path}"
    )
    assert live_codes == frozen_codes, (
        f"{operation_id}: live status codes {sorted(live_codes)} != "
        f"frozen contract {sorted(frozen_codes)} — "
        f"missing from live schema: {sorted(frozen_codes - live_codes)}, "
        f"advertised by live but not in contract: {sorted(live_codes - frozen_codes)}"
    )


def test_unmounted_frozen_operations_are_counted_not_failed():
    """The frozen contract legitimately declares ~10 operations no lane has
    mounted a router for yet (magic-links, sessions, documents, orders,
    webhooks, staff transitions). This test exists to make that count
    VISIBLE — never to fail the build over it. If a future PR mounts one of
    these, move its operationId into `_MOUNTED_OPERATION_IDS` above and add
    a dedicated `_assert_status_parity` call for it; do not widen this
    test's assertion to cover it implicitly."""
    frozen_ops = _operations_by_id(_frozen_schema())
    unmounted = sorted(set(frozen_ops) - _MOUNTED_OPERATION_IDS)
    print(f"garuda-voa: {len(unmounted)} frozen operation(s) not yet mounted: {unmounted}")
    assert len(frozen_ops) >= len(_MOUNTED_OPERATION_IDS), (
        "frozen contract declares fewer operations than this router mounts — "
        "the contract file itself regressed"
    )
