"""Guards `apps/mouth/src/lib/api/schema.d.ts` against silently going stale.

SHWEB-20260911 PR-RISYNC: the schema sat 20 days behind the live backend
contract (last regenerated 2026-08-24, `6ee7f50d1e`) with nothing in CI
noticing — four endpoint groups shipped on the backend and appeared zero
times in the checked-in frontend contract. This test regenerates the
OpenAPI schema via the SAME code path `npm run contract:visa-oracle`'s
`generate:openapi` step uses (`scripts.generate_openapi.create_app` +
`.openapi()`), hashes it with that module's own `compute_schema_sha256`
(imported, not reimplemented — one hashing implementation, so the writer and
this checker cannot drift apart from each other the way the schema and the
backend did), and compares against the pin file committed next to
`schema.d.ts`. A backend change that alters the live OpenAPI contract
without a matching `npm run contract:visa-oracle` regeneration turns this
test RED, naming exactly what to run.

Determinism proved before this file was committed (see the PR body /
evidence pack for the exact commands): two separate
`python -m scripts.generate_openapi` invocations, each a fresh interpreter
process, produced byte-identical `openapi.json` and identical SHA-256 hashes
both times.

This test lives in `apps/backend-rag` (a CI job here already sets up the
Python stack and already imports the app — see `contract-tests.yml`), but it
guards a CONTRACT, not backend runtime behaviour: merging it changes zero
runtime code, so the merge is a Fly deploy of identical runtime code, only
adding this test to the suite that runs against it.

SCOPE, stated honestly (round-2 council MINOR, CONFIRMED — both the
coordinator and `tp1-qwen3.8-max` reached this independently): this pin
guards ONE layer — the live backend OpenAPI JSON moving ahead of the schema
last committed — which is exactly the 20-day failure this PR fixes. It does
**NOT** guard the OTHER layer: `schema.d.ts` being a faithful RENDER of that
JSON. The `openapi-typescript` rendering step (`generate:api` in
`apps/mouth/package.json`) is never re-run or hashed here, so if that tool
is bumped or changes its output format, `schema.d.ts` can diverge from what
a fresh render of the SAME, unchanged `openapi.json` would produce, while
this test stays GREEN (the backend has not moved). A second pin hashing
`schema.d.ts`'s own bytes was considered and DELIBERATELY not added: nothing
in this backend-only pytest job can re-derive `schema.d.ts` from a fresh
render to compare against it — that needs Node + the exact
`openapi-typescript` version, which this job's Python-only CI setup does not
have (the same category of cost already named for the original
`generate:openapi`-in-CI question). A pin nothing re-checks is a file that
exists without being armed (cicatrix family #2, esiste≠armato), so the
honest choice is a stated scope gap here, not a decorative second pin.
Closing that second gap — if ever warranted — is a separate PR with its own
spec (Node in this job, or a mouth-side vitest check that re-renders and
diffs), not a hidden addition to this one.

`create_app()` SIDE-EFFECT VERIFICATION (round-2 council MINOR — the seat's
worry: importing/constructing the app inside a test function, under this
repo's real CI parallelism (`-n auto --dist loadfile`, `.github/workflows/
tests.yml`), could flake if construction opens a DB handle or a socket).
Checked, not assumed: `create_app()` calls `register_middleware()`, which
imports `backend.middleware.rate_limiter`, whose module-level singleton
`rate_limiter = RateLimiter()` (line 233) DOES attempt to acquire a Redis
client in its constructor via `RedisManager.get_instance().get_sync_client()`
— but `RedisManager.__init__` is a no-op (only sets attributes to
`None`/`False`); the actual blocking call
(`redis.from_url(...).ping()`, `socket_connect_timeout=5`) lives in the
SEPARATE `RedisManager.initialize()` method
(`backend/core/redis_manager.py`), which is invoked from the app's
`lifespan` startup handler — never triggered by `create_app()` + `.openapi()`
alone, since neither runs the ASGI lifespan. `get_sync_client()` therefore
returns `None` immediately (no connection attempted), matching the
consistently-observed log line "Rate limiter using in-memory storage — no
Redis available" appearing INSTANTLY on every run in this PR (never a
5-second stall) and the ~1-2s total runtime measured across every
`python -m scripts.generate_openapi` invocation in this PR's determinism
proof. `PricingService`'s eager load (also visible in every run's logs,
"118 services loaded across 9 categories") is a local JSON file read
(`backend/data/bali_zero_official_prices_2026.json`), not network I/O.
Additionally, `create_app()` is already called this same way — no fixture,
no gating — by five OTHER files in this suite
(`test_app_factory.py`, `test_endpoints_reachable.py`,
`test_evaluate_endpoint.py`, `test_intake_review.py`,
`test_garuda_voa_openapi_parity.py`), which already run today under the
exact `-n auto --dist loadfile` regime this concern is about, with no
recorded flake for this pattern. Conclusion: side-effect-free with respect
to network I/O; no fixture-gating added.
"""

from __future__ import annotations

from pathlib import Path

from scripts.generate_openapi import compute_schema_sha256

# This file: apps/backend-rag/backend/tests/unit/scripts/test_generate_openapi_schema_pin.py
# Repo root: six levels up (mirrors this directory's own conftest.py). A
# restructure that changes this file's depth would otherwise fail with an
# opaque FileNotFoundError deep inside the assertion below — round-2 council
# MINOR (CONFIRMED); assert the landmark explicitly instead.
_REPO_ROOT = Path(__file__).resolve().parents[6]
assert (_REPO_ROOT / "apps" / "mouth" / "package.json").is_file(), (
    f"computed repo root {_REPO_ROOT} does not contain apps/mouth/package.json — "
    "this file moved and the parents[6] depth above needs updating"
)
_PIN_PATH = (
    _REPO_ROOT / "apps" / "mouth" / "src" / "lib" / "api" / "schema.d.ts.openapi-sha256"
)


def test_schema_d_ts_pin_matches_the_live_openapi_contract() -> None:
    from backend.app.setup.app_factory import create_app

    app = create_app()
    schema = app.openapi()
    live_hash = compute_schema_sha256(schema)

    assert _PIN_PATH.exists(), (
        f"pin file missing at {_PIN_PATH} — run `npm run contract:visa-oracle` "
        "in apps/mouth and commit schema.d.ts + the pin"
    )
    pinned_hash = _PIN_PATH.read_text(encoding="utf-8").strip()

    assert live_hash == pinned_hash, (
        "openapi changed: run npm run contract:visa-oracle in apps/mouth and "
        "commit schema.d.ts + pin"
    )
