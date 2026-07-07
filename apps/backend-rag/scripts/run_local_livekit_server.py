#!/usr/bin/env python3
"""Run the local-only LiveKit server for voice concierge development."""

from __future__ import annotations

import argparse
import ipaddress
import os
import shutil
import socket
from pathlib import Path
from urllib.parse import urlparse

APPROVED_RUNTIME_HOST_ALIASES = {
    "nuzantara": "Nuzantara",
    "mini-pro2": "Mini-Pro2",
}
APPROVED_RUNTIME_HOSTS = frozenset(APPROVED_RUNTIME_HOST_ALIASES.values())
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "0:0:0:0:0:0:0:1"}


class PreflightError(RuntimeError):
    """Raised when the local LiveKit server should not start."""


def normalize_hostname(hostname: str) -> str:
    short_hostname = hostname.split(".", 1)[0]
    return APPROVED_RUNTIME_HOST_ALIASES.get(short_hostname.lower(), short_hostname)


def is_approved_runtime_host(hostname: str | None = None) -> bool:
    return normalize_hostname(hostname or socket.gethostname()) in APPROVED_RUNTIME_HOSTS


def validate_loopback_bind(bind_host: str) -> None:
    host = bind_host.strip().lower()
    if host in LOOPBACK_HOSTS:
        return
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise PreflightError("LiveKit server bind host must be loopback") from exc
    if not address.is_loopback:
        raise PreflightError("LiveKit server bind host must be loopback")


def validate_livekit_url(url: str, bind_host: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"ws", "wss"} or parsed.hostname is None:
        raise PreflightError("LIVEKIT_URL must be ws:// or wss://")
    if parsed.hostname.lower() not in LOOPBACK_HOSTS:
        raise PreflightError("LIVEKIT_URL must point at loopback for local audio")
    validate_loopback_bind(bind_host)


def resolve_livekit_server_binary(configured_binary: str | None = None) -> Path:
    configured = configured_binary or os.environ.get("LIVEKIT_SERVER_BINARY")
    if configured:
        path = Path(configured).expanduser()
        if not path.exists():
            raise PreflightError(f"LiveKit server binary not found: {path}")
        return path

    discovered = shutil.which("livekit-server")
    if not discovered:
        raise PreflightError("livekit-server binary not found in PATH")
    return Path(discovered)


def build_livekit_server_command(
    *,
    binary: Path,
    bind_host: str,
) -> list[str]:
    validate_loopback_bind(bind_host)
    return [str(binary), "--dev", "--bind", bind_host]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local loopback LiveKit server")
    parser.add_argument("--bind", default=os.environ.get("VOICE_CONCIERGE_LIVEKIT_BIND", "127.0.0.1"))
    parser.add_argument("--binary", default=os.environ.get("LIVEKIT_SERVER_BINARY"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not is_approved_runtime_host():
        raise PreflightError("local LiveKit server is allowed only on Nuzantara/Mini-Pro2")

    validate_livekit_url(os.environ.get("LIVEKIT_URL", "ws://127.0.0.1:7880"), args.bind)
    binary = resolve_livekit_server_binary(args.binary)
    command = build_livekit_server_command(binary=binary, bind_host=args.bind)
    os.execv(command[0], command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
