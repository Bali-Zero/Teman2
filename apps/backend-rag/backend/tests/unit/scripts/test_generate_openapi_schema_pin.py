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
"""

from __future__ import annotations

from pathlib import Path

from scripts.generate_openapi import compute_schema_sha256

# This file: apps/backend-rag/backend/tests/unit/scripts/test_generate_openapi_schema_pin.py
# Repo root: six levels up (mirrors this directory's own conftest.py).
_REPO_ROOT = Path(__file__).resolve().parents[6]
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
