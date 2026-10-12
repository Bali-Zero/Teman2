#!/usr/bin/env python3
"""Verify the public TLS certificates used by Bali Zero services."""

from __future__ import annotations

import argparse
import json
import socket
import ssl
import sys
import time
from datetime import datetime, timezone
from typing import Callable, Iterable, Mapping, Optional

HOSTS = (
    "balizero.com",
    "kita.balizero.com",
    "mail.balizero.com",
    "calendar.balizero.com",
    "drive.balizero.com",
    "knowledge.balizero.com",
    "nuzantara-rag.fly.dev",
)
PORT = 443
TIMEOUT_SECONDS = 8
THRESHOLD_DAYS = 30


def fetch_certificate(host: str, port: int = PORT) -> Mapping[str, object]:
    """Fetch a verified peer certificate using SNI."""
    context = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=TIMEOUT_SECONDS) as raw:
        with context.wrap_socket(raw, server_hostname=host) as tls:
            return tls.getpeercert()


def issuer_common_name(cert: Mapping[str, object]) -> Optional[str]:
    for rdn in cert.get("issuer", ()):  # type: ignore[union-attr]
        for key, value in rdn:
            if key == "commonName":
                return str(value)
    return None


def days_until_expiry(cert: Mapping[str, object], now_epoch: float) -> int:
    not_after = cert.get("notAfter")
    if not isinstance(not_after, str) or not not_after:
        raise ValueError("certificate has no notAfter")
    expiry = ssl.cert_time_to_seconds(not_after)
    return int((expiry - now_epoch) // 86400)


def classify(days_left: int) -> str:
    return "expiring" if days_left < THRESHOLD_DAYS else "ok"


def check_host(
    host: str,
    fetch: Callable[[str, int], Mapping[str, object]],
    now_epoch: float,
) -> dict[str, object]:
    base: dict[str, object] = {"host": host, "days_left": None, "issuer_cn": None}
    try:
        cert = fetch(host, PORT)
        days_left = days_until_expiry(cert, now_epoch)
        return {
            **base,
            "days_left": days_left,
            "status": classify(days_left),
            "issuer_cn": issuer_common_name(cert),
        }
    except ssl.SSLCertVerificationError as exc:
        return {
            **base,
            "status": "verify_failed",
            "reason": getattr(exc, "verify_message", str(exc)),
        }
    except (socket.timeout, TimeoutError, OSError, ssl.SSLError) as exc:
        return {**base, "status": "unreachable", "reason": str(exc)}
    except (TypeError, ValueError, KeyError, OverflowError) as exc:
        return {**base, "status": "parse_error", "reason": str(exc)}


def run_checks(
    hosts: Optional[Iterable[str]] = None,
    fetch: Optional[Callable[[str, int], Mapping[str, object]]] = None,
    now_epoch: Optional[float] = None,
) -> tuple[dict[str, object], int]:
    active_fetch = fetch or fetch_certificate
    active_hosts = HOSTS if hosts is None else hosts
    checked_at = time.time() if now_epoch is None else now_epoch
    results = [check_host(host, active_fetch, checked_at) for host in active_hosts]
    summary = {
        "checked_at": datetime.fromtimestamp(checked_at, timezone.utc).isoformat(),
        "results": results,
    }
    return summary, 1 if any(item["status"] != "ok" for item in results) else 0


def self_test() -> None:
    now = ssl.cert_time_to_seconds("Jan 01 00:00:00 2030 GMT")
    cert = {
        "notAfter": "Jan 31 00:00:00 2030 GMT",
        "issuer": ((('commonName', 'Unit Test CA'),),),
    }
    assert days_until_expiry(cert, now) == 30
    assert classify(30) == "ok" and classify(29) == "expiring"
    assert issuer_common_name(cert) == "Unit Test CA"
    summary, rc = run_checks(("example.invalid",), lambda _h, _p: cert, now)
    assert rc == 0 and summary["results"][0]["status"] == "ok"  # type: ignore[index]


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        self_test()
        print("self-test ok")
        return 0
    summary, rc = run_checks()
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return rc


if __name__ == "__main__":
    sys.exit(main())
