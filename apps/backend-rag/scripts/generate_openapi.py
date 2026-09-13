"""Generate the FastAPI OpenAPI schema for frontend type generation.

Also writes the drift pin (`SCHEMA_PIN_RELATIVE_PATH`) consumed by
`backend/tests/unit/scripts/test_generate_openapi_schema_pin.py` — SHWEB-20260911
PR-RISYNC's guard against `apps/mouth/src/lib/api/schema.d.ts` going stale
against the live backend contract (it sat 20 days behind once, silently).
`compute_schema_sha256` is the ONE hashing implementation, imported by that
test rather than reimplemented, so the writer and the checker cannot drift
apart from each other the way the schema and the backend did.

SCOPE (stated honestly, round-2 council MINOR): this pin covers the backend
OpenAPI JSON, not `schema.d.ts` itself — it cannot detect `openapi-typescript`
(the separate `generate:api` rendering step) diverging from that JSON on a
tool version bump. See the test module's docstring for the full reasoning on
why a second pin was deliberately not added.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger("zantara.openapi_gen")

# Relative to the repo root (four levels above this file:
# scripts/ -> backend-rag/ -> apps/ -> repo root).
SCHEMA_PIN_RELATIVE_PATH = Path("apps/mouth/src/lib/api/schema.d.ts.openapi-sha256")


def _configure_environment() -> None:
    """Set safe defaults so schema generation avoids production-like side effects."""
    os.environ.setdefault("ENVIRONMENT", "test")


def _schema_bytes(schema: dict[str, Any]) -> bytes:
    """Canonical, deterministic serialization — the ONLY place this repo turns
    an OpenAPI schema dict into bytes. `sort_keys=True` makes it independent
    of FastAPI/Pydantic's internal dict insertion order; shared by the file
    writer and the hash below so they cannot silently diverge."""
    return (json.dumps(schema, indent=2, sort_keys=True) + "\n").encode("utf-8")


def compute_schema_sha256(schema: dict[str, Any]) -> str:
    """SHA-256 hex digest of the canonical serialization."""
    return hashlib.sha256(_schema_bytes(schema)).hexdigest()


def _write_schema(schema: dict[str, Any], output_path: Path) -> None:
    """Serialize the OpenAPI schema to disk."""
    output_path.write_bytes(_schema_bytes(schema))


def _write_pin(schema: dict[str, Any], repo_root: Path) -> Path:
    """Write the drift pin next to `schema.d.ts`, read next commit."""
    pin_path = repo_root / SCHEMA_PIN_RELATIVE_PATH
    pin_path.write_text(compute_schema_sha256(schema) + "\n", encoding="utf-8")
    return pin_path


def main() -> int:
    """Create the FastAPI app, generate OpenAPI, and persist it + its pin."""
    _configure_environment()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    from backend.app.setup.app_factory import create_app

    project_root = Path(__file__).resolve().parents[1]
    repo_root = Path(__file__).resolve().parents[3]
    output_path = project_root / "openapi.json"

    logger.info("Creating FastAPI app for OpenAPI schema generation")
    app = create_app()

    logger.info("Generating OpenAPI schema")
    schema = app.openapi()
    _write_schema(schema=schema, output_path=output_path)
    logger.info("OpenAPI schema written to %s", output_path)

    pin_path = _write_pin(schema=schema, repo_root=repo_root)
    logger.info("OpenAPI drift pin written to %s", pin_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
