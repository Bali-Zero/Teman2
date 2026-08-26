"""Minimal backend client for the ChatGPT Business marketing bridge.

Unlike ``nuzantara_mcp.server``, this module never loads an admin key and never
imports or registers the full MCP tool catalog.  Endpoint selection remains in
the allowlisted marketing wrappers; this client only supplies authenticated
transport with normalized errors that cannot echo backend response bodies.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

BACKEND_URL = os.getenv("NUZANTARA_BACKEND_URL", "https://nuzantara-rag.fly.dev")
TIMEOUT_SECONDS = int(os.getenv("NUZANTARA_WORKSPACE_MARKETING_TIMEOUT", "30"))
_client: httpx.AsyncClient | None = None
_ALLOWED_READ_ENDPOINT_RE = re.compile(
    r"^/api/workspace-marketing/news/(?:pending|[A-Za-z0-9][A-Za-z0-9._-]{0,159})$"
)
_ALLOWED_PUBLISH_ENDPOINT_RE = re.compile(
    r"^/api/workspace-marketing/news/[A-Za-z0-9][A-Za-z0-9._-]{0,159}/publish$"
)


def _workspace_key(path: Path | None = None) -> str:
    configured = os.getenv("NUZANTARA_WORKSPACE_MARKETING_API_KEY", "").strip()
    if configured:
        return configured
    env_file = path if path is not None else Path.home() / ".nuzantara-secrets.env"
    try:
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line.startswith("export "):
                line = line[len("export ") :].lstrip()
            if line.startswith("NUZANTARA_WORKSPACE_MARKETING_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        return ""
    return ""


def _headers() -> dict[str, str]:
    """Return only the dedicated, route-scoped workspace credential."""

    key = _workspace_key()
    if not key:
        raise RuntimeError("Nuzantara workspace marketing credential is unavailable")
    return {
        "Content-Type": "application/json",
        "X-Workspace-Marketing-Key": key,
    }


def _validated_backend_url(value: str) -> str:
    try:
        parsed = urlsplit(value.strip())
    except ValueError as exc:
        raise RuntimeError("Nuzantara marketing backend URL is invalid") from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError("Nuzantara marketing backend URL must be an HTTPS origin")
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=_validated_backend_url(BACKEND_URL),
            timeout=TIMEOUT_SECONDS,
            limits=httpx.Limits(max_connections=6, max_keepalive_connections=3),
        )
    return _client


async def call(
    endpoint: str,
    method: str = "GET",
    json: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call one wrapper-selected backend endpoint without leaking response bodies."""

    global _client
    normalized_method = method.upper()
    allowed = (
        normalized_method == "GET" and _ALLOWED_READ_ENDPOINT_RE.fullmatch(endpoint)
    ) or (
        normalized_method == "POST" and _ALLOWED_PUBLISH_ENDPOINT_RE.fullmatch(endpoint)
    )
    if not allowed:
        raise RuntimeError("Nuzantara marketing backend endpoint is not allowed")
    request = {
        "method": normalized_method,
        "url": endpoint,
        "json": json,
        "params": params,
        "headers": _headers(),
        "timeout": TIMEOUT_SECONDS,
    }
    client = _get_client()
    try:
        response = await client.request(**request)
    except (httpx.RemoteProtocolError, httpx.ReadError, httpx.ConnectError):
        if _client is not None and not _client.is_closed:
            await _client.aclose()
        _client = None
        try:
            response = await _get_client().request(**request)
        except httpx.RequestError as exc:
            raise RuntimeError("Nuzantara marketing backend is unavailable") from exc
    except httpx.TimeoutException as exc:
        raise RuntimeError("Nuzantara marketing backend timed out") from exc
    except httpx.RequestError as exc:
        raise RuntimeError("Nuzantara marketing backend is unavailable") from exc

    if response.is_error:
        raise RuntimeError(
            f"Nuzantara marketing backend returned HTTP {response.status_code}"
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("Nuzantara marketing backend returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Nuzantara marketing backend returned an unsupported shape")
    return payload
