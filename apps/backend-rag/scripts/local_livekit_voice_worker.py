#!/usr/bin/env python3
"""Local-only LiveKit worker for the voice concierge readiness gate."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import os
import socket
import sys
import threading
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

APPROVED_RUNTIME_HOST_ALIASES = {
    "nuzantara": "Nuzantara",
    "mini-pro2": "Mini-Pro2",
}
APPROVED_RUNTIME_HOSTS = frozenset(APPROVED_RUNTIME_HOST_ALIASES.values())
DEFAULT_HEALTH_URL = "http://127.0.0.1:7889/healthz"
DEFAULT_NATIVE_HEALTH_URL = "http://127.0.0.1:7888/"
LOCAL_HEALTH_HOSTS = {"localhost", "127.0.0.1", "::1", "0:0:0:0:0:0:0:1"}
OFFLINE_ENV_GUARDS = {
    "DO_NOT_TRACK": "1",
    "HF_DATASETS_OFFLINE": "1",
    "HF_HUB_DISABLE_TELEMETRY": "1",
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
}
TAILSCALE_CGNAT = ipaddress.ip_network("100.64.0.0/10")

logger = logging.getLogger("local_livekit_voice_worker")


@dataclass(frozen=True)
class HealthEndpoint:
    host: str
    port: int
    path: str
    url: str


@dataclass(frozen=True)
class SidecarConfig:
    health_endpoint: HealthEndpoint
    native_endpoint: HealthEndpoint
    livekit_url: str
    agent_name: str


class PreflightError(RuntimeError):
    """Raised when the local-only worker should not start."""


def normalize_hostname(hostname: str) -> str:
    short_hostname = hostname.split(".", 1)[0]
    return APPROVED_RUNTIME_HOST_ALIASES.get(short_hostname.lower(), short_hostname)


def is_approved_runtime_host(hostname: str | None = None) -> bool:
    return normalize_hostname(hostname or socket.gethostname()) in APPROVED_RUNTIME_HOSTS


def health_endpoint_from_env() -> HealthEndpoint:
    configured_url = os.environ.get(
        "VOICE_CONCIERGE_LIVEKIT_WORKER_HEALTH_URL",
        DEFAULT_HEALTH_URL,
    )
    return _parse_loopback_http_url(configured_url, require_root_path=False)


def native_health_endpoint_from_env() -> HealthEndpoint:
    configured_url = os.environ.get(
        "VOICE_CONCIERGE_LIVEKIT_WORKER_NATIVE_HEALTH_URL",
        DEFAULT_NATIVE_HEALTH_URL,
    )
    endpoint = _parse_loopback_http_url(configured_url, require_root_path=True)
    if endpoint.path != "/":
        raise PreflightError(
            "VOICE_CONCIERGE_LIVEKIT_WORKER_NATIVE_HEALTH_URL must point at the native LiveKit root /",
        )
    return endpoint


def _parse_loopback_http_url(configured_url: str, *, require_root_path: bool) -> HealthEndpoint:
    parsed = urlparse(configured_url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
        raise PreflightError(
            "LiveKit worker health URLs must be HTTP(S) loopback URLs",
        )
    if parsed.hostname.lower() not in LOCAL_HEALTH_HOSTS:
        raise PreflightError(
            "LiveKit worker health URLs must bind to localhost/loopback",
        )
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise PreflightError(
            "LiveKit worker health URLs must not include credentials, query, or fragment",
        )
    path = parsed.path or "/"
    if require_root_path and path != "/":
        raise PreflightError(
            "LiveKit Agents native health is served at /",
        )
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return HealthEndpoint(host=parsed.hostname, port=port, path=path, url=configured_url)


def livekit_server_url_from_env() -> str:
    server_url = os.environ.get("LIVEKIT_URL", "").strip()
    if not server_url:
        raise PreflightError("LIVEKIT_URL is required and must point at the local LiveKit server")
    parsed = urlparse(server_url)
    if parsed.scheme not in {"ws", "wss"} or parsed.hostname is None:
        raise PreflightError("LIVEKIT_URL must be ws:// or wss://")
    if not _is_local_livekit_host(parsed.hostname):
        raise PreflightError("LIVEKIT_URL must use localhost, .local, RFC1918, or Tailscale LAN")
    return server_url


def require_livekit_credentials() -> tuple[str, str]:
    api_key = os.environ.get("LIVEKIT_API_KEY", "").strip()
    api_secret = os.environ.get("LIVEKIT_API_SECRET", "").strip()
    if not api_key or not api_secret:
        raise PreflightError("LIVEKIT_API_KEY and LIVEKIT_API_SECRET are required")
    return api_key, api_secret


def validate_offline_env() -> None:
    missing_or_wrong = [
        key for key, expected in OFFLINE_ENV_GUARDS.items() if os.environ.get(key) != expected
    ]
    if missing_or_wrong:
        raise PreflightError(
            "offline guard env missing or mismatched: " + ", ".join(missing_or_wrong),
        )


def preflight() -> HealthEndpoint:
    if not is_approved_runtime_host():
        raise PreflightError("local LiveKit voice worker is allowed only on Nuzantara/Mini-Pro2")
    validate_offline_env()
    livekit_server_url_from_env()
    require_livekit_credentials()
    health_endpoint = health_endpoint_from_env()
    native_endpoint = native_health_endpoint_from_env()
    if (health_endpoint.host, health_endpoint.port) == (native_endpoint.host, native_endpoint.port):
        raise PreflightError("sidecar health and native LiveKit health must use different ports")
    return health_endpoint


async def entrypoint(ctx: object) -> None:
    from livekit.agents import AutoSubscribe

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    await asyncio.Event().wait()


def _is_local_livekit_host(hostname: str) -> bool:
    host = hostname.lower()
    if host in LOCAL_HEALTH_HOSTS or host.endswith(".local"):
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return normalize_hostname(host) in APPROVED_RUNTIME_HOSTS
    return (
        address.is_loopback
        or address.is_private
        or address.is_link_local
        or address in TAILSCALE_CGNAT
    )


def start_health_sidecar(config: SidecarConfig) -> ThreadingHTTPServer:
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path != config.health_endpoint.path:
                self.send_error(404)
                return
            status_code, payload = build_sidecar_health_payload(config)
            body = json.dumps(payload, sort_keys=True).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = ThreadingHTTPServer((config.health_endpoint.host, config.health_endpoint.port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, name="livekit-health-sidecar", daemon=True)
    thread.start()
    return server


def build_sidecar_health_payload(config: SidecarConfig) -> tuple[int, dict[str, object]]:
    livekit_reachable = _tcp_reachable(config.livekit_url)
    native_ok = _native_worker_root_ok(config.native_endpoint.url)
    worker_metadata = _native_worker_metadata(config.native_endpoint.url)
    agent_matches = worker_metadata.get("agent_name") == config.agent_name
    healthy = livekit_reachable and native_ok and agent_matches
    payload: dict[str, object] = {
        "healthy": healthy,
        "status": "healthy" if healthy else "unhealthy",
        "agent_name": config.agent_name,
        "livekit_server_reachable": livekit_reachable,
        "native_worker_ready": native_ok,
        "worker_metadata": worker_metadata,
    }
    return (200 if healthy else 503), payload


def _native_worker_root_ok(native_url: str) -> bool:
    try:
        body = _http_get(native_url).decode("utf-8").strip().lower()
    except OSError:
        return False
    return body == "ok"


def _native_worker_metadata(native_url: str) -> dict[str, object]:
    worker_url = native_url.rstrip("/") + "/worker"
    try:
        body = _http_get(worker_url)
    except OSError:
        return {}
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _http_get(url: str) -> bytes:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=1.0) as response:
        status_code = getattr(response, "status", 0)
        if status_code < 200 or status_code >= 300:
            raise urllib.error.HTTPError(url, status_code, "not healthy", {}, None)
        return response.read()


def _tcp_reachable(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.hostname is None:
        return False
    port = parsed.port or (443 if parsed.scheme == "wss" else 80)
    try:
        with socket.create_connection((parsed.hostname, port), timeout=1.0):
            return True
    except OSError:
        return False


def _help_requested(argv: Sequence[str]) -> bool:
    return any(arg in {"-h", "--help"} for arg in argv)


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=os.environ.get("LIVEKIT_LOG_LEVEL", "INFO"))
    args = list(sys.argv[1:] if argv is None else argv)
    if not _help_requested(args):
        try:
            health_endpoint = preflight()
            native_endpoint = native_health_endpoint_from_env()
            livekit_url = livekit_server_url_from_env()
            agent_name = os.environ.get(
                "VOICE_CONCIERGE_LIVEKIT_AGENT_NAME",
                "voice-concierge-local",
            )
        except PreflightError as exc:
            logger.error("%s", exc)
            return 1
        sidecar = start_health_sidecar(
            SidecarConfig(
                health_endpoint=health_endpoint,
                native_endpoint=native_endpoint,
                livekit_url=livekit_url,
                agent_name=agent_name,
            ),
        )
        logger.info("starting local LiveKit sidecar health at %s", health_endpoint.url)
        logger.info("starting native LiveKit worker health at %s", native_endpoint.url)
    else:
        health_endpoint = health_endpoint_from_env()
        native_endpoint = native_health_endpoint_from_env()
        agent_name = os.environ.get("VOICE_CONCIERGE_LIVEKIT_AGENT_NAME", "voice-concierge-local")
        sidecar = None

    from livekit import agents

    server_url = os.environ.get("LIVEKIT_URL")
    api_key = os.environ.get("LIVEKIT_API_KEY")
    api_secret = os.environ.get("LIVEKIT_API_SECRET")
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name=agent_name,
            ws_url=server_url,
            api_key=api_key,
            api_secret=api_secret,
            host=native_endpoint.host,
            port=native_endpoint.port,
            http_proxy=None,
        ),
    )
    if sidecar is not None:
        sidecar.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
