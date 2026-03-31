"""Generate the FastAPI OpenAPI schema for frontend type generation."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger("zantara.openapi_gen")


def _configure_environment() -> None:
    """Set safe defaults so schema generation avoids production-like side effects."""
    os.environ.setdefault("ENVIRONMENT", "test")


def _write_schema(schema: dict[str, Any], output_path: Path) -> None:
    """Serialize the OpenAPI schema to disk."""
    output_path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    """Create the FastAPI app, generate OpenAPI, and persist it to project root."""
    _configure_environment()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    from backend.app.setup.app_factory import create_app

    project_root = Path(__file__).resolve().parents[1]
    output_path = project_root / "openapi.json"

    logger.info("Creating FastAPI app for OpenAPI schema generation")
    app = create_app()

    logger.info("Generating OpenAPI schema")
    schema = app.openapi()
    _write_schema(schema=schema, output_path=output_path)

    logger.info("OpenAPI schema written to %s", output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
