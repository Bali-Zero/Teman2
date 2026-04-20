"""
Mata Garuda — Brevo email adapter (Layer 5 Distribuzione).

Minimal Brevo v3 /smtp/email wrapper. One purpose: send a weekly digest
HTML email to Zero from zantara@balizero.com (aliased to damar@).

Why Brevo HTTP (not SDK):
- Stay pydantic-only (Legge stack minimale)
- Just curl + JSON

Env: BREVO_API_KEY (secrets file). Falls back to SENDGRID_API_KEY if
the value begins with `xkeysib-` (same Brevo key stored under either
name in different deployment eras).
"""
from __future__ import annotations

import json
import logging
import os
import subprocess

logger = logging.getLogger("mata_garuda.tools.brevo")

BREVO_ENDPOINT = "https://api.brevo.com/v3/smtp/email"
DEFAULT_SENDER = {"email": "zantara@balizero.com", "name": "Mata Garuda"}
DEFAULT_TIMEOUT_S = 45  # Brevo cold API calls occasionally &gt;20s


def _resolve_key() -> str | None:
    key = os.environ.get("BREVO_API_KEY")
    if key:
        return key
    alt = os.environ.get("SENDGRID_API_KEY")
    if alt and alt.startswith("xkeysib-"):
        return alt
    return None


def send_html(
    to_email: str,
    subject: str,
    html_content: str,
    *,
    to_name: str | None = None,
    sender: dict[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT_S,
) -> dict:
    """Send one HTML email via Brevo. Returns {"ok": bool, "status": int, ...}."""
    key = _resolve_key()
    if not key:
        return {"ok": False, "status": 0, "reason": "no BREVO_API_KEY"}

    payload = {
        "sender": sender or DEFAULT_SENDER,
        "to": [{"email": to_email, "name": to_name or to_email}],
        "subject": subject,
        "htmlContent": html_content,
    }

    try:
        result = subprocess.run(
            [
                "curl", "-s", "-w", "\nHTTP_STATUS:%{http_code}",
                "-X", "POST", BREVO_ENDPOINT,
                "-H", "accept: application/json",
                "-H", "content-type: application/json",
                "-H", f"api-key: {key}",
                "-d", json.dumps(payload),
            ],
            capture_output=True, text=True, timeout=timeout,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return {"ok": False, "status": 0, "reason": f"transport: {e}"}

    if result.returncode != 0:
        return {"ok": False, "status": 0, "reason": f"curl rc={result.returncode}"}

    out = result.stdout
    status = 0
    if "HTTP_STATUS:" in out:
        body, _, status_str = out.rpartition("HTTP_STATUS:")
        try:
            status = int(status_str.strip())
        except ValueError:
            status = 0
    else:
        body = out

    ok = 200 <= status < 300
    return {
        "ok": ok,
        "status": status,
        "body": body.strip()[:500],
    }
