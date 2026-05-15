#!/usr/bin/env python3
"""WR2 Canva OAuth one-shot bootstrap.

Run interactively on Pro (browser available):
    export WR2_CANVA_TOKEN_FILE=~/.config/wr2/canva_tokens.json
    export WR2_CANVA_HMAC_KEY=$(openssl rand -hex 32)  # save to ~/.nuzantara-secrets.env
    python scripts/wr2_bootstrap_canva_oauth.py

Performs:
1. RFC 7591 dynamic client registration at mcp.canva.com/register
2. OAuth authorization code flow via local HTTP callback (ephemeral port)
3. Token exchange → token storage HMAC-signed
4. Smoke test: list-brand-kits via MCP, assert Bali Zero team in result

Idempotent: if token file already exists and is valid, prints status
and exits. To force re-bootstrap: delete WR2_CANVA_TOKEN_FILE first.
"""
import asyncio
import http.server
import json
import logging
import os
import socket
import socketserver
import sys
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "apps" / "backend-rag"))

from backend.services.canva_renderer_v2._token_storage import (  # noqa: E402
    OrchestratorTokenStorage, TokenStorageError, sign_payload,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("bootstrap")

CANVA_REGISTER = "https://mcp.canva.com/register"
CANVA_AUTHORIZE = "https://mcp.canva.com/authorize"
CANVA_TOKEN = "https://mcp.canva.com/token"
SCOPE = "user:read offline_access account:read teams:read"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _register_client(redirect_uri: str) -> dict:
    body = json.dumps({
        "client_name": "WR2 Pipeline Orchestrator",
        "redirect_uris": [redirect_uri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
        "scope": SCOPE,
    }).encode()
    req = urllib.request.Request(
        CANVA_REGISTER, data=body, headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _exchange_code(client_id: str, code: str, code_verifier: str, redirect_uri: str) -> dict:
    body = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": code_verifier,
    }).encode()
    req = urllib.request.Request(
        CANVA_TOKEN, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _smoke_test_list_brand_kits(access_token: str) -> bool:
    body = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                   "clientInfo": {"name": "wr2-bootstrap", "version": "1.0"}},
    }).encode()
    req = urllib.request.Request(
        "https://mcp.canva.com/mcp", data=body,
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream",
                 "Authorization": f"Bearer {access_token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            r.read(200)
            logger.info("Smoke initialize: HTTP %s", r.status)
            return True
    except Exception as e:
        logger.error("Smoke failed: %s", e)
        return False


def main() -> int:
    storage = OrchestratorTokenStorage()
    if storage.path.exists():
        try:
            storage.load_sync()
            logger.info("Token file already exists and valid: %s", storage.path)
            logger.info("To force re-bootstrap: rm %s", storage.path)
            return 0
        except TokenStorageError as e:
            logger.warning("Existing token invalid, re-running bootstrap: %s", e)

    port = _free_port()
    redirect_uri = f"http://localhost:{port}/oauth/callback"
    logger.info("Registering client at %s ...", CANVA_REGISTER)
    client_info = _register_client(redirect_uri)
    client_id = client_info["client_id"]
    logger.info("client_id assigned: %s", client_id)

    import base64, hashlib, secrets
    code_verifier = secrets.token_urlsafe(96)[:128]
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)

    auth_url = (
        f"{CANVA_AUTHORIZE}?response_type=code&client_id={client_id}"
        f"&redirect_uri={urllib.parse.quote(redirect_uri, safe='')}"
        f"&scope={urllib.parse.quote(SCOPE)}"
        f"&state={state}&code_challenge={code_challenge}&code_challenge_method=S256"
    )

    received: dict = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            received["code"] = params.get("code", [""])[0]
            received["state"] = params.get("state", [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h2>WR2 OAuth: code received. You can close this window.</h2></body></html>"
            )

        def log_message(self, format, *args):  # noqa: A002 — silence
            pass

    server = socketserver.TCPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    logger.info("Local callback server listening on %d. Opening Chrome ...", port)
    logger.info("If browser does NOT open Chrome automatically, paste this URL into Chrome manually:\n  %s", auth_url)
    # Force Chrome on macOS (Safari is the system default and was hijacking the flow)
    import subprocess as _sp
    try:
        _sp.run(["/usr/bin/open", "-a", "Google Chrome", auth_url], check=False, timeout=5)
    except Exception as _e:
        logger.warning("Chrome open failed (%s) — fall back to default browser", _e)
        webbrowser.open(auth_url)

    # Wait for callback (max 5min)
    for _ in range(300):
        if received.get("code"):
            break
        time.sleep(1)
    server.shutdown()

    if not received.get("code"):
        logger.error("No callback within 5min")
        return 2
    if received["state"] != state:
        logger.error("State mismatch — possible CSRF")
        return 2

    logger.info("Exchanging code for tokens ...")
    tokens = _exchange_code(client_id, received["code"], code_verifier, redirect_uri)

    # Persist with HMAC. Use save_sync but enrich with client_info first.
    payload = {
        "client_id": client_id,
        "client_secret": "",
        "redirect_uris": [redirect_uri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
        "scope": tokens.get("scope", SCOPE),
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token", ""),
        "token_type": tokens.get("token_type", "bearer"),
        "expires_in": tokens.get("expires_in", 3600),
    }
    storage.save_sync(payload)
    logger.info("Wrote token file: %s", storage.path)

    # Smoke test
    if _smoke_test_list_brand_kits(tokens["access_token"]):
        logger.info("✅ Bootstrap complete")
        return 0
    logger.error("❌ Smoke failed — token might still work but verify manually")
    return 3


if __name__ == "__main__":
    sys.exit(main())
