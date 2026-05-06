"""HTTP API exposing mata-garuda KG metadata over Tailscale loopback.

Hard rules (see apps/mata-garuda/CLAUDE.md §1.4):
- Bind only to Tailscale interface or 127.0.0.1 (test). Refuse 0.0.0.0 / ::.
- Never return observation.value, evidence_url, aliases_json, content/title/body.
- Read-only sqlite connection (mode=ro URI).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sqlite3
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast

logger = logging.getLogger("mata_garuda.api.kg_query")

DEFAULT_KG_PATH = Path.home() / ".agent" / "mata-garuda" / "kg.db"
DEFAULT_BIND = "100.93.236.6"
DEFAULT_PORT = 8990
SEARCH_LIMIT_HARD_CAP = 100
SEARCH_LIMIT_DEFAULT = 20
NEIGHBOR_HARD_CAP = 50

FORBIDDEN_BIND_PREFIXES = ("0.0.0.0", "::", "0:0:0:0")

ENTITY_TYPES = {"persons", "organizations", "locations", "laws", "topics"}

# Path safety: name must not contain / or .. or null bytes after URL decoding.
_SAFE_NAME_RE = re.compile(r"^[^\x00/]+$")


def _ro_conn(db_path: Path) -> sqlite3.Connection:
    """Open a read-only connection. Safe even if writer is active (WAL).

    `db_path` is percent-encoded so a path that happens to contain `?` or
    `#` is not silently truncated by SQLite's URI parser.
    """
    encoded = urllib.parse.quote(str(db_path), safe="/:@")
    uri = f"file:{encoded}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


class KGQueryHandler(BaseHTTPRequestHandler):
    server_version = "matagaruda-kg-query/1.0"

    # Suppress default stdout-noisy log_message; we use our logger.
    def log_message(self, fmt: str, *args: Any) -> None:
        # Audit line: status + path only, never body.
        try:
            ip = self.client_address[0]
        except Exception:
            ip = "?"
        logger.info("%s - %s", ip, fmt % args)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/health":
            return self._handle_health()
        self._send_json(404, {"error": "not_found", "detail": "no such endpoint"})

    # ── handlers ──────────────────────────────────────────────────
    @property
    def _kg_server(self) -> "KGServer":
        """Typed view of `self.server`. Avoids `# type: ignore` per handler."""
        return cast("KGServer", self.server)

    def _handle_health(self) -> None:
        db_path = self._kg_server.db_path
        try:
            conn = _ro_conn(db_path)
        except sqlite3.Error as exc:
            return self._send_json(500, {
                "ok": False,
                "kg_path": str(db_path),
                "error": "kg_unavailable",
                "detail": str(exc),
            })
        try:
            schema_ok = True
            counts = {"entities_count": 0, "relations_count": 0, "observations_count": 0}
            for tbl, key in (
                ("kg_entities", "entities_count"),
                ("kg_relations", "relations_count"),
                ("kg_observations", "observations_count"),
            ):
                try:
                    counts[key] = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                except sqlite3.Error:
                    schema_ok = False
            self._send_json(200, {
                "ok": True,
                "kg_path": str(db_path),
                "schema_ok": schema_ok,
                **counts,
            })
        finally:
            conn.close()

    # ── helpers ──────────────────────────────────────────────────
    def _send_json(self, status: int, body: dict) -> None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)


class _ConfiguredServer(ThreadingHTTPServer):
    """ThreadingHTTPServer that carries the configured KG path."""

    def __init__(self, server_address: tuple[str, int], handler_cls: type, db_path: Path) -> None:
        super().__init__(server_address, handler_cls)
        self.db_path = db_path


# Public alias used by tests; we keep `_ConfiguredServer` private so the
# stdlib `ThreadingHTTPServer` name in this file is unambiguously the base
# class from `http.server`.
KGServer = _ConfiguredServer


def build_server(*, bind: str, port: int, db_path: Path | None = None) -> KGServer:
    """Construct the HTTP server. Refuse forbidden bind addresses."""
    if any(bind == p or bind.startswith(p + ":") for p in FORBIDDEN_BIND_PREFIXES):
        raise RuntimeError(f"refusing to bind on wildcard address {bind!r}")
    db = db_path or DEFAULT_KG_PATH
    return _ConfiguredServer((bind, port), KGQueryHandler, db)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="mata-garuda KG query API")
    parser.add_argument("--bind", default=os.getenv("KG_API_BIND", DEFAULT_BIND))
    parser.add_argument("--port", type=int, default=int(os.getenv("KG_API_PORT", str(DEFAULT_PORT))))
    parser.add_argument("--db-path", type=Path, default=DEFAULT_KG_PATH)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    server = build_server(bind=args.bind, port=args.port, db_path=args.db_path)
    logger.info("kg-query listening on %s:%s db=%s", args.bind, args.port, args.db_path)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
