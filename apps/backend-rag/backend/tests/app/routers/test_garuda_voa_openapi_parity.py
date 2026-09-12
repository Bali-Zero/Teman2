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

Widened 2026-08-30 (team-lead F1 mandate, PR #4959's gate-completeness
follow-up): `_MOUNTED_OPERATION_IDS` used to be a hand-typed 3-item
allowlist covering only `garuda_voa_public.py`'s three operations — a gate
that "passes even if code and contract diverge on everything not in that
list." Measured that day: the frozen contract declares **13** operations;
**10** of them are genuinely mounted (this router's 3, plus L4
`garuda_portal_auth.py`'s `requestMagicLink`/`exchangeMagicLink`, plus L3
`garuda_orders_router.py`'s `createOrderFromCheck`/`getOrderAndPractice`/
`observePaymentBrowserReturn`/`receivePaymentWebhook`/`resolveLateOrder`) and
**3** have no router at all (`uploadIntakeDocument`, `listIntakeDocuments`,
`transitionPractice` — corrected: the first two moved to
`_MOUNTED_OPERATION_IDS` when `garuda_documents_router.py`, L5's hinge,
mounted; `transitionPractice` remains the only genuinely unmounted one).
None of the 7 L3/L4 operations were checked before
this widening — 5 of them were not even *resolvable* by operationId (their
decorators never set `operation_id=`, so FastAPI auto-generated one from the
Python function name), and the 2 that were resolvable (`requestMagicLink`/
`exchangeMagicLink`) had the identical missing-`responses=` disease this
file's docstring already described for L2. Both routers were fixed
alongside this widening (`garuda_orders_router.py` and
`garuda_portal_auth.py`; `garuda_voa_public.py`'s `_NO_VALIDATION_ERROR_
OPERATIONS` gained `getOrderAndPractice`, the same bare-`str`-path-param
auto-422 already described above for L2).

Three of the 10 mounted operations still do not fully match the frozen
contract after that fix, for reasons that are real, separate product
defects — not test-file bugs, and not fixable by touching this test file,
a `responses=` kwarg, or the frozen contract (which every router's own
docstring says none of them may edit). `_KNOWN_STATUS_CODE_GAPS` below
names each one explicitly, cites the exact code path (or absence of one)
responsible, and is guarded (`test_known_status_code_gaps_are_still_true`)
so a future fix to the underlying defect — closing the gap without updating
this dict — fails the suite rather than silently going unnoticed the other
way. This mirrors, for a second kind of gap, the same "explicit + guarded,
never silent" discipline `_NOT_YET_BUILT_OPERATION_IDS` already applies to
the 3 never-mounted operations.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

# Importing this module BUILDS the deployed `main_api` FastAPI app as a
# side effect (`app = create_api_app()` at its own module scope) — the same
# thing that happens when uvicorn imports `main_api:app` in production.
# That is the point: see `_live_operations` below for why a lighter build
# would not prove what this file needs proven. Paid once per pytest worker
# (Python caches the import), not once per test function.
from backend.app import main_api as _main_api_module

_CONTRACT_PATH = (
    Path(__file__).resolve().parents[6] / "products" / "garuda-voa" / "contracts" / "openapi.yaml"
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


def _live_path_methods() -> set[tuple[str, str]]:
    """Every (path, HTTP method) the live app answers, independent of
    operationId — used only to prove a NOT-YET-BUILT operation is genuinely
    absent (an operationId-keyed lookup would trivially "miss" a route that
    exists under some OTHER operationId at that same path/method, which is
    not the claim this guard needs to prove)."""
    out: set[tuple[str, str]] = set()
    schema = _main_api_module.app.openapi()
    for path, methods in schema["paths"].items():
        if not isinstance(methods, dict):
            continue
        for method, op in methods.items():
            if isinstance(op, dict):
                out.add((path, method.upper()))
    return out


# operationIds the frozen contract declares that NO router file exposes a
# path for at all today (measured 2026-08-30 via `_live_path_methods()`
# against every path `_frozen_schema()` declares) — magic-link/customer-
# intake/payment/staff-practice lanes ahead of a router landing, per
# `products/garuda-voa/LANES.md`. Contract-first is allowed to be ahead of
# the build; what is NOT allowed is this fact going unverified. Guarded by
# `test_declared_not_yet_built_operations_are_genuinely_absent_from_the_live_app`
# below — if a future PR mounts a router for one of these paths, that test
# starts failing, forcing the operationId out of this set (removing it here
# is sufficient: it then falls into `_MOUNTED_OPERATION_IDS` automatically
# and gets full status-parity coverage from the parametrized test, with zero
# new test code required).
# `uploadIntakeDocument`/`listIntakeDocuments` moved to
# `_MOUNTED_OPERATION_IDS` when `garuda_documents_router.py` (L5 hinge) was
# mounted — its production store still fails closed 503 until L1's
# retention-covered store exists (see that router's module docstring), but
# the HTTP surface itself is real and answers every status code the frozen
# contract declares. `transitionPractice` moved the same way (step 8,
# `garuda_staff_router.py`) — the frozen contract's status-code set is now
# matched byte-for-byte by that router's own `_status_responses()` helper,
# so it needs no `_KNOWN_STATUS_CODE_GAPS` entry either.
_NOT_YET_BUILT_OPERATION_IDS: frozenset[str] = frozenset()

# Mounted operations whose live status-code set does not fully match the
# frozen contract for reasons that are real, separate product defects — see
# the module docstring's "Widened 2026-08-30" paragraph for the one-line
# summary of each. Each entry names EXACTLY the codes the frozen contract
# declares that the live router cannot yet produce; nothing here is a status
# code the live schema is missing merely for lack of `responses=`
# documentation (`_assert_status_parity` below folds these into the live set
# before comparing, so real drift beyond what is named here still fails the
# suite). Guarded by `test_known_status_code_gaps_are_still_true`: if the
# underlying defect is fixed and the code path starts producing one of these
# statuses, that guard fails, forcing the fix's PR to shrink this entry (or
# remove it, once its set is empty) rather than leaving a stale exemption
# that quietly stops checking anything.
_KNOWN_STATUS_CODE_GAPS: dict[str, frozenset[str]] = {
    # `GarudaOrderRepository.record_browser_return_observation`
    # (repository.py) unconditionally overwrites `browser_return_nonce` on a
    # mismatch instead of raising `IdempotencyConflict` — the contract's
    # declared 409 IDEMPOTENCY_CONFLICT has no code path that can raise it.
    "observePaymentBrowserReturn": frozenset({"409"}),
    # `receive_payment_webhook` (garuda_orders_router.py) never constructs a
    # 202 (the quarantine response shape) and deliberately stopped reading
    # Idempotency-Key (see that handler's own comment) — the frozen
    # contract's `responses` block for 400/409 was not updated to match when
    # the parameter was removed, and this module never edits the contract.
    "receivePaymentWebhook": frozenset({"202", "400", "409"}),
    # `_require_staff_actor` (garuda_orders_router.py) only ever returns 401
    # or a verified actor — the real staff-authority verifier is "wired
    # nowhere today" per that function's own docstring, so ACCESS_DENIED (403)
    # has no code path that can raise it yet.
    "resolveLateOrder": frozenset({"403"}),
}

# Derived, not hand-typed: every frozen operationId except the ones
# EXPLICITLY declared not-yet-built above. A newly-mounted contract
# operation is automatically included here (and therefore automatically
# gets full parity coverage from the parametrized test below) the moment its
# operationId stops appearing in `_NOT_YET_BUILT_OPERATION_IDS` — nobody has
# to remember to add it to a second list.
_MOUNTED_OPERATION_IDS: frozenset[str] = (
    frozenset(_operations_by_id(_frozen_schema())) - _NOT_YET_BUILT_OPERATION_IDS
)


def test_contract_file_is_readable_and_declares_mounted_operations():
    """Guilt+innocence anchor for the fixture itself (cicatrix #6/#2): if this
    fails, the parametrized parity test below would otherwise report a
    misleading per-operation KeyError instead of "the fixture is broken"."""
    frozen_ops = _operations_by_id(_frozen_schema())
    missing = _MOUNTED_OPERATION_IDS - frozen_ops.keys()
    assert not missing, f"frozen contract no longer declares: {sorted(missing)}"


def test_declared_not_yet_built_operations_are_genuinely_absent_from_the_live_app():
    """Guard for `_NOT_YET_BUILT_OPERATION_IDS` (cicatrix #3 discipline: a
    static allowlist needs a test that fails when it goes stale, not a
    silence). If a future PR mounts a router that answers one of these
    paths, this test starts failing — the fix is to remove that operationId
    from `_NOT_YET_BUILT_OPERATION_IDS`, which automatically moves it into
    `_MOUNTED_OPERATION_IDS` and under full status-parity coverage."""
    frozen_ops = _operations_by_id(_frozen_schema())
    live_pairs = _live_path_methods()
    for operation_id in _NOT_YET_BUILT_OPERATION_IDS:
        path, method, _codes = frozen_ops[operation_id]
        assert (path, method) not in live_pairs, (
            f"{operation_id}: declared NOT YET BUILT in this test file, but "
            f"{method} {path} now answers live — move it out of "
            f"_NOT_YET_BUILT_OPERATION_IDS so it gets real parity coverage"
        )


def test_known_status_code_gaps_are_declared_only_for_mounted_operations():
    """Guilt+innocence anchor for `_KNOWN_STATUS_CODE_GAPS`: every key must
    be a real mounted operation (never one already covered by
    `_NOT_YET_BUILT_OPERATION_IDS` — those two lists are disjoint by
    construction, and a name in both would mean one of them is wrong)."""
    declared = set(_KNOWN_STATUS_CODE_GAPS)
    assert declared <= _MOUNTED_OPERATION_IDS, (
        f"_KNOWN_STATUS_CODE_GAPS names operation(s) not in "
        f"_MOUNTED_OPERATION_IDS: {sorted(declared - _MOUNTED_OPERATION_IDS)}"
    )


def test_known_status_code_gaps_are_still_true():
    """The other half of the guard: each declared-missing code must
    genuinely be ABSENT from the live schema today. If a fix lands that
    makes one of these codes reachable without updating
    `_KNOWN_STATUS_CODE_GAPS`, this fails — the parametrized parity test
    below would otherwise silently start passing on a narrower comparison
    than the contract actually requires, exactly the "gate that stops
    checking and nobody notices" failure mode this whole file exists to
    prevent."""
    live_ops = _live_operations()
    for operation_id, missing_codes in _KNOWN_STATUS_CODE_GAPS.items():
        _path, _method, live_codes = live_ops[operation_id]
        overlap = missing_codes & live_codes
        assert not overlap, (
            f"{operation_id}: _KNOWN_STATUS_CODE_GAPS declares {sorted(overlap)} "
            f"as unreachable, but the live schema now documents them — shrink "
            f"or remove this entry instead of leaving a stale exemption"
        )


def test_live_router_exposes_every_mounted_operation():
    live_ops = _live_operations()
    missing = _MOUNTED_OPERATION_IDS - live_ops.keys()
    assert not missing, f"live router no longer exposes: {sorted(missing)}"


@pytest.mark.parametrize("operation_id", sorted(_MOUNTED_OPERATION_IDS))
def test_live_status_codes_match_frozen_contract(operation_id: str) -> None:
    _assert_status_parity(operation_id)


def _assert_status_parity(operation_id: str) -> None:
    frozen_ops = _operations_by_id(_frozen_schema())
    live_ops = _live_operations()
    frozen_path, frozen_method, frozen_codes = frozen_ops[operation_id]
    live_path, live_method, live_codes = live_ops[operation_id]
    assert (live_path, live_method) == (frozen_path, frozen_method), (
        f"{operation_id}: path/method drifted — "
        f"live={live_method} {live_path} frozen={frozen_method} {frozen_path}"
    )
    known_gap = _KNOWN_STATUS_CODE_GAPS.get(operation_id, frozenset())
    reconciled_codes = live_codes | known_gap
    assert reconciled_codes == frozen_codes, (
        f"{operation_id}: live status codes {sorted(live_codes)} "
        f"(+ declared gap {sorted(known_gap)}) != "
        f"frozen contract {sorted(frozen_codes)} — "
        f"missing and NOT declared as a known gap: "
        f"{sorted(frozen_codes - reconciled_codes)}, "
        f"advertised by live but not in contract: {sorted(live_codes - frozen_codes)}"
    )


def test_not_yet_built_operations_are_counted_not_silently_ignored():
    """The frozen contract legitimately declares 3 operations no lane has
    mounted a router for yet. This test exists to make that count VISIBLE
    — never to fail the build over it — and to catch accidental double-
    counting between the two tracked sets."""
    frozen_ops = _operations_by_id(_frozen_schema())
    accounted = _MOUNTED_OPERATION_IDS | _NOT_YET_BUILT_OPERATION_IDS
    assert accounted == frozen_ops.keys(), (
        "every frozen operationId must land in exactly one of "
        "_MOUNTED_OPERATION_IDS / _NOT_YET_BUILT_OPERATION_IDS — "
        f"unaccounted: {sorted(frozen_ops.keys() - accounted)}, "
        f"phantom (declared but not in the frozen contract): "
        f"{sorted(accounted - frozen_ops.keys())}"
    )
    print(
        f"garuda-voa: {len(_NOT_YET_BUILT_OPERATION_IDS)} frozen operation(s) "
        f"not yet mounted: {sorted(_NOT_YET_BUILT_OPERATION_IDS)}; "
        f"{len(_MOUNTED_OPERATION_IDS)} mounted and checked for status "
        f"parity ({len(_KNOWN_STATUS_CODE_GAPS)} with a declared, guarded gap)"
    )


# ---------------------------------------------------------------------------
# Round-3 disposition item G: security scheme / Idempotency-Key requiredness
# / Idempotency-Replayed header, for the 4 staff-practice operations.
#
# FastAPI infers ALL THREE of these from either a `fastapi.security.*`
# dependency (this router has none — auth is a hand-rolled `Authorization`
# header read via `require_garuda_staff`) or from a parameter's own default
# (`Header(None, ...)` reads as NOT required, even though the handler's own
# `_idempotency_key()` raises 400 IDEMPOTENCY_KEY_REQUIRED on absence). Two
# of the three are now DECLARED via `openapi_extra` on the route decorators
# (`_STAFF_SESSION_SECURITY` / `_TRANSITION_OPENAPI_EXTRA` in
# garuda_staff_router.py) and checked here as real parity, not a gap.
#
# The third — Idempotency-Key's `required` flag — used to be a declared
# exemption here (`_KNOWN_IDEMPOTENCY_KEY_NOT_MARKED_REQUIRED`, removed
# 2026-09-12) covering assignPractice/transitionPractice. It is now real
# parity for all TEN mutating operations the frozen contract governs, and the
# reason the exemption existed is still the reason the cure is not
# `openapi_extra`: that merge (`fastapi.utils.deep_dict_update`) concatenates
# `parameters` LISTS rather than matching by name, so a second entry would
# DUPLICATE the parameter instead of overriding it. The cure is
# `garuda_voa_public.mark_idempotency_key_required`, chained onto
# `app.openapi` in both factories next to `strip_unreachable_validation_errors`,
# which OVERWRITES the `required` flag of the entry FastAPI already generated.
# `test_idempotency_key_is_declared_once_per_operation` below is what keeps
# the distinction honest.
#
# No behaviour changed with it: every family already answered a missing key
# with the contract's 400 IDEMPOTENCY_KEY_REQUIRED before this
# (`garuda_voa_public._valid_idempotency_key`,
# `garuda_portal_auth._require_idempotency_key`, and the inline length check
# in the orders/staff/documents routers) — the schema was the only liar.


#: The operations the FROZEN contract marks `Idempotency-Key: required` —
#: derived from the file, never transcribed. A hardcoded copy here and a
#: hardcoded copy in the transform can agree with each other while both
#: diverge from the contract, which is the one disagreement this module
#: exists to catch (Sol round 1, finding 2).
def _frozen_idempotency_key_operations() -> frozenset[str]:
    frozen = _frozen_schema()
    ops: set[str] = set()
    for methods in frozen.get("paths", {}).values():
        for op in methods.values():
            if not isinstance(op, dict):
                continue
            for param in op.get("parameters", []) or []:
                ref = param.get("$ref") if isinstance(param, dict) else None
                if ref == "#/components/parameters/IdempotencyKey":
                    ops.add(op["operationId"])
    return frozenset(ops)


_IDEMPOTENCY_KEY_REQUIRED_OPERATIONS: tuple[str, ...] = tuple(
    sorted(_frozen_idempotency_key_operations())
)

#: Mutating GARUDA operations the contract deliberately leaves without the
#: header. Named, so "absent" is a pinned decision and not an oversight.
_NO_IDEMPOTENCY_KEY_OPERATIONS: tuple[str, ...] = (
    "receivePaymentWebhook",
    "previewMagicLink",
)

_STAFF_PRACTICE_OPERATIONS: tuple[str, ...] = (
    "listStaffPractices",
    "getStaffPractice",
    "assignPractice",
    "transitionPractice",
)


def _idempotency_key_param(op: dict) -> dict | None:
    for param in op.get("parameters", []):
        if isinstance(param, dict) and param.get("name") == "Idempotency-Key":
            return param
    return None


@pytest.mark.parametrize("operation_id", _STAFF_PRACTICE_OPERATIONS)
def test_staff_operation_declares_staff_session_security(operation_id: str) -> None:
    live_ops = _live_operations()
    live_path, live_method, _codes = live_ops[operation_id]
    schema = _main_api_module.app.openapi()
    op = schema["paths"][live_path][live_method.lower()]
    assert op.get("security") == [{"StaffSession": []}], (
        f"{operation_id}: live security={op.get('security')!r}, expected "
        f"the StaffSession scheme the frozen contract declares for every "
        f"staff-practice operation"
    )


def test_the_transform_covers_exactly_the_operations_the_contract_names() -> None:
    """The production set and the frozen contract must be the SAME set.

    Without this, adding a `$ref` to the contract (or dropping one) leaves the
    transform and the parametrized tests below agreeing with each other and
    both wrong — they would simply never visit the new operation. Compares the
    live module constant against the set derived from the file.
    """
    from backend.app.routers.garuda_voa_public import _IDEMPOTENCY_KEY_REQUIRED_OPERATIONS as prod

    frozen_ops = _frozen_idempotency_key_operations()
    assert set(prod) == set(frozen_ops), (
        f"transform covers {sorted(set(prod) - frozen_ops)} the contract does not, and "
        f"misses {sorted(frozen_ops - set(prod))} the contract names"
    )


@pytest.mark.parametrize("operation_id", _IDEMPOTENCY_KEY_REQUIRED_OPERATIONS)
def test_mutating_operation_declares_idempotency_key_required(operation_id: str) -> None:
    """Frozen contract vs live schema on the ONE flag FastAPI cannot infer.

    `openapi.yaml` declares `components.parameters.IdempotencyKey` with
    `required: true` and every one of these ten operations references it, so
    a live `required: false` is a documented lie about a header the handler
    refuses to work without. Read from the FROZEN file rather than hardcoded
    here, so the day the contract changes its mind this test follows it
    instead of outvoting it.
    """
    frozen_required = _frozen_schema()["components"]["parameters"]["IdempotencyKey"]["required"]
    assert frozen_required is True, (
        "the frozen contract no longer declares Idempotency-Key required — "
        "this suite's premise moved, update it deliberately"
    )
    live_ops = _live_operations()
    live_path, live_method, _codes = live_ops[operation_id]
    schema = _main_api_module.app.openapi()
    op = schema["paths"][live_path][live_method.lower()]
    param = _idempotency_key_param(op)
    assert param is not None, f"{operation_id}: no Idempotency-Key parameter in live schema"
    assert param.get("in") == "header", f"{operation_id}: Idempotency-Key is not a header parameter"
    assert bool(param.get("required")) is True, (
        f"{operation_id}: live Idempotency-Key required={param.get('required')!r}, "
        f"frozen contract says required=true"
    )


@pytest.mark.parametrize("operation_id", _IDEMPOTENCY_KEY_REQUIRED_OPERATIONS)
def test_idempotency_key_is_declared_once_per_operation(operation_id: str) -> None:
    """The cure must OVERWRITE the generated parameter, never append a second.

    This is the failure `openapi_extra` would have produced — two
    `Idempotency-Key` entries, one required and one not — and it is invisible
    to the test above, which reads the first match.
    """
    live_ops = _live_operations()
    live_path, live_method, _codes = live_ops[operation_id]
    schema = _main_api_module.app.openapi()
    op = schema["paths"][live_path][live_method.lower()]
    matches = [
        p
        for p in (op.get("parameters") or [])
        if isinstance(p, dict) and p.get("name") == "Idempotency-Key"
    ]
    assert len(matches) == 1, (
        f"{operation_id}: {len(matches)} Idempotency-Key parameters in the live schema, expected 1"
    )


@pytest.mark.parametrize("operation_id", _NO_IDEMPOTENCY_KEY_OPERATIONS)
def test_operation_without_idempotency_key_did_not_acquire_one(operation_id: str) -> None:
    """The transform is scoped by operationId; these two must stay untouched.

    `receivePaymentWebhook` is called by the payment provider and
    `previewMagicLink` mutates nothing — the contract gives neither the
    header, so a live entry here would be the transform reaching too far.
    """
    schema = _main_api_module.app.openapi()
    for path, methods in schema.get("paths", {}).items():
        for method, op in methods.items():
            if not isinstance(op, dict) or op.get("operationId") != operation_id:
                continue
            assert _idempotency_key_param(op) is None, (
                f"{operation_id} ({method.upper()} {path}) declares an Idempotency-Key "
                f"parameter the contract never gave it"
            )
            return
    pytest.fail(f"{operation_id} is not mounted in the live app — this test lost its subject")


def test_the_documented_requirement_is_served_when_nothing_answers_first(monkeypatch) -> None:
    """The other half of `required: true`: the DEPLOYED app must refuse the
    request the document now says is invalid — and refuse it the contract's
    way (400 with a code), not FastAPI's way (422).

    SCOPE, stated because the broader claim is FALSE and was refuted before
    this test was believed (Sol round 1, finding 1): 400
    IDEMPOTENCY_KEY_REQUIRED is what an OTHERWISE VALID, ALREADY AUTHENTICATED
    request gets. It is not what every keyless request gets, and that is
    correct rather than a defect — authentication and body validation
    legitimately answer first. Measured on this head with the flag on and no
    header: `createEligibilityCheck`, `requestMagicLink` and
    `exchangeMagicLink` answer 422 INVALID_REQUEST for the BODY
    (`garuda_voa_public.py:607`, `garuda_portal_auth.py:427`), and
    `uploadIntakeDocument`, the three orders operations and the two staff
    operations answer 401 SESSION_REQUIRED when unauthenticated
    (`garuda_orders_router.py:368`, `garuda_documents_router.py:533`,
    `garuda_staff_router.py:386`). `required: true` in a schema says the
    client must send the header; it never promised to be the first thing
    checked.

    So this test picks the one operation with no body and no session —
    DELETE on a public eligibility result — because that is where the key
    check is genuinely the first gate, and asserts there. It runs against
    `main_api.app`, the same singleton `_live_operations()` reads, so the
    document and the behaviour under test belong to one object.
    """
    from fastapi.testclient import TestClient

    monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", "true")
    client = TestClient(_main_api_module.app)
    # DELETE deliberately: no body and no session, so the key check is the
    # first gate rather than the third. (Measured while writing this test:
    # the same call as a POST with an empty body returns FastAPI's 422 for
    # the BODY — which is why the docstring above states the scope instead of
    # letting this one green case imply a universal one.)
    response = client.delete("/api/visa/voa/eligibility-checks/" + "r" * 22)
    assert response.status_code == 400, (
        f"missing Idempotency-Key answered {response.status_code}, expected the "
        f"contract's 400 — a 422 would mean FastAPI started enforcing the header "
        f"itself and the contract's error envelope was lost"
    )
    assert response.json()["code"] == "IDEMPOTENCY_KEY_REQUIRED"


def test_transition_practice_declares_idempotency_replayed_header() -> None:
    live_ops = _live_operations()
    live_path, live_method, _codes = live_ops["transitionPractice"]
    schema = _main_api_module.app.openapi()
    op = schema["paths"][live_path][live_method.lower()]
    headers = op["responses"]["200"].get("headers", {})
    assert "Idempotency-Replayed" in headers, (
        "transitionPractice: live 200 response does not document the "
        "Idempotency-Replayed header the frozen contract declares"
    )
