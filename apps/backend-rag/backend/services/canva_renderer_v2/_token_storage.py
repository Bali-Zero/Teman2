"""Orchestrator-owned OAuth token storage.

Independent from mcp-remote npm cache (see spec §3 + memory
fact_canva_mcp_dynamic_client_registration). Path:
~/.config/wr2/canva_tokens.json (mode 0600).

Features:
- HMAC-SHA256 integrity check on every read (key from WR2_CANVA_HMAC_KEY hex).
- fcntl.flock advisory exclusive lock around read+write.
- Proactive refresh: needs_refresh() True when <300s + jitter to expiry.
- Atomic write via temp+rename.
- Preserves refresh_token if Canva omits it in refresh response.
- NO mtime-compare-before-replace (anti-pattern per panel).

Public API matches mcp.client.auth.TokenStorage (async). Sync helpers
exposed for bootstrap script + tests.
"""
from __future__ import annotations

import asyncio
import fcntl
import hashlib
import hmac
import json
import logging
import os
import random
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REFRESH_MARGIN_S = 300
JITTER_MAX_S = 15


class TokenStorageError(RuntimeError):
    pass


def _canonical(payload: dict[str, Any]) -> str:
    without = {k: v for k, v in payload.items() if k != "_hmac"}
    return json.dumps(without, sort_keys=True, separators=(",", ":"))


def sign_payload(payload: dict[str, Any], *, key: bytes) -> dict[str, Any]:
    sig = hmac.new(key, _canonical(payload).encode(), hashlib.sha256).hexdigest()
    return {**{k: v for k, v in payload.items() if k != "_hmac"}, "_hmac": sig}


def verify_payload(payload: dict[str, Any], *, key: bytes) -> dict[str, Any]:
    stored = payload.get("_hmac")
    if not stored:
        raise TokenStorageError("Token file missing HMAC field")
    computed = hmac.new(key, _canonical(payload).encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(stored, computed):
        raise TokenStorageError("Token HMAC mismatch — corrupt or tampered")
    return {k: v for k, v in payload.items() if k != "_hmac"}


class OrchestratorTokenStorage:
    """Sync-first storage; async wrappers below for mcp SDK contract."""

    def __init__(self) -> None:
        path_env = os.environ.get("WR2_CANVA_TOKEN_FILE")
        if not path_env:
            raise TokenStorageError(
                "WR2_CANVA_TOKEN_FILE env var required (e.g. ~/.config/wr2/canva_tokens.json)"
            )
        self.path = Path(path_env).expanduser()
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")

        hex_key = os.environ.get("WR2_CANVA_HMAC_KEY")
        if not hex_key:
            raise TokenStorageError("WR2_CANVA_HMAC_KEY env var required (32-byte hex)")
        try:
            self.hmac_key = bytes.fromhex(hex_key)
        except ValueError as e:
            raise TokenStorageError(f"WR2_CANVA_HMAC_KEY not valid hex: {e}") from e

    @contextmanager
    def _lock(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.lock_path, "w") as fp:
            fcntl.flock(fp.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fp.fileno(), fcntl.LOCK_UN)

    def load_sync(self) -> dict[str, Any]:
        if not self.path.exists():
            raise TokenStorageError(
                f"Token file not found: {self.path}. Run scripts/wr2_bootstrap_canva_oauth.py"
            )
        with self._lock():
            payload = json.loads(self.path.read_text())
            return verify_payload(payload, key=self.hmac_key)

    def needs_refresh(self) -> bool:
        try:
            tokens = self.load_sync()
        except TokenStorageError:
            return True  # treat unloadable as expired
        remaining = float(tokens.get("expires_at_epoch", 0)) - time.time()
        threshold = REFRESH_MARGIN_S + random.uniform(0, JITTER_MAX_S)
        return remaining < threshold

    def save_sync(self, new_tokens: dict[str, Any]) -> None:
        """Merge new_tokens into existing, sign, atomic write."""
        with self._lock():
            existing = {}
            if self.path.exists():
                try:
                    existing = verify_payload(
                        json.loads(self.path.read_text()), key=self.hmac_key
                    )
                except TokenStorageError:
                    logger.warning(
                        "Existing token file unverifiable; backup + replace"
                    )
                    backup = self.path.with_suffix(
                        f".broken-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
                    )
                    self.path.rename(backup)

            merged = {**existing, **new_tokens}
            # Preserve refresh_token if Canva omitted it on refresh
            if not new_tokens.get("refresh_token") and existing.get("refresh_token"):
                merged["refresh_token"] = existing["refresh_token"]
            merged["last_refreshed_iso"] = datetime.now(timezone.utc).isoformat()
            expires_in = new_tokens.get("expires_in", 3600)
            merged["expires_at_epoch"] = time.time() + float(expires_in)

            signed = sign_payload(merged, key=self.hmac_key)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(json.dumps(signed, indent=2))
            tmp.chmod(0o600)
            tmp.replace(self.path)

    # Async wrappers for mcp SDK TokenStorage contract
    async def get_tokens(self):
        return await asyncio.to_thread(self._load_for_sdk)

    async def set_tokens(self, tokens) -> None:
        await asyncio.to_thread(self._save_from_sdk, tokens)

    async def get_client_info(self):
        return await asyncio.to_thread(self._load_client_info)

    async def set_client_info(self, info) -> None:
        # client_info is owned by the orchestrator and written during bootstrap
        # only. Runtime no-op. (Subsequent OAuth flows in this orchestrator
        # always reuse the bootstrap-time client_id.)
        return

    def _load_for_sdk(self):
        from mcp.shared.auth import OAuthToken
        if self.needs_refresh():
            return None  # mcp SDK will trigger refresh
        data = self.load_sync()
        return OAuthToken(
            access_token=data["access_token"],
            token_type=data.get("token_type", "bearer"),
            expires_in=int(max(0, data["expires_at_epoch"] - time.time())),
            refresh_token=data.get("refresh_token"),
            scope=data.get("scope"),
        )

    def _save_from_sdk(self, tokens):
        self.save_sync({
            "access_token": tokens.access_token,
            "token_type": tokens.token_type,
            "expires_in": tokens.expires_in,
            "refresh_token": tokens.refresh_token,
            "scope": tokens.scope,
        })

    def _load_client_info(self):
        from mcp.shared.auth import OAuthClientInformationFull
        data = self.load_sync()
        return OAuthClientInformationFull(
            client_id=data["client_id"],
            client_secret=data.get("client_secret") or None,
            redirect_uris=data.get("redirect_uris", []),
            grant_types=data.get("grant_types", ["authorization_code", "refresh_token"]),
            response_types=data.get("response_types", ["code"]),
            token_endpoint_auth_method=data.get("token_endpoint_auth_method", "none"),
            scope=data.get("scope"),
        )
