#!/usr/bin/env python3
"""codex_access_watch.py — WhatsApp receptor for balizero.com/codex access.

Polls Vercel request logs for the `mouth` project, filters /codex requests,
and sends Zero a WhatsApp when someone enters from OUTSIDE the US edge set —
the reader this exists for is Leopoldo, who connects from Italy (fra1/cdg1/...).
Zero and this fleet's own probes currently egress from California (sfo1), so
US-edge traffic is self-noise and stays silent.

Reading a request:
  POST 303 = correct PIN, entered · POST 401 = wrong sign at the door ·
  GET 200  = page load (door or codex, cookie-dependent).

Blind-guard (scar family #2, Esiste≠Armato): after N consecutive Vercel API
failures the receptor tells Zero it has gone blind — a watcher that cannot
see must not stay silently green. State (seen request ids, failure counter)
persists in ~/.organism/state/codex_access_watch.state.json.

Env (wrapper sources these; no secrets on the CLI):
  CODEX_WATCH_VERCEL_TOKEN     Vercel CLI bearer token (required)
  WHATSAPP_TOKEN               Meta Cloud API token (required)
  WHATSAPP_PHONE_NUMBER_ID     Bali Zero WA line id (required)
  CODEX_WATCH_ALERT_TO         recipient, default Zero 6282210302328
  CODEX_WATCH_TEST_PING=1      send a liveness test message and exit
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_ID = "prj_LcXb9ZgeUvWpxaIM9K47tQYPeuee"  # mouth on Vercel
OWNER_ID = "team_jX3mEbUemBs0Zy4i8aFYZsjS"  # nuzantara-2026
DEFAULT_ALERT_TO = "6282210302328"  # Zero — already public in wa.me fallback

# Vercel edges that are "us": Zero in California + this fleet's probes.
# Anything else (fra1/cdg1/lhr1/dub1/arn1 = Europe, sin1/hkg1 = Asia, ...)
# is a stranger at the door — for now that means Leopoldo.
SELF_EDGES = {"sfo1", "iad1", "pdx1", "cle1"}

EU_EDGES = {"fra1", "cdg1", "lhr1", "dub1", "arn1", "mad1"}

STATE_PATH = Path.home() / ".organism/state/codex_access_watch.state.json"
WINDOW_HOURS = 24  # catch-up horizon after downtime; dedup absorbs overlap
SEEN_TTL_HOURS = 48
BLIND_AFTER_FAILURES = 12  # ~1h at 300s cadence
BLIND_ALERT_COOLDOWN_H = 24


def _load_state() -> dict[str, Any]:
    try:
        return json.loads(STATE_PATH.read_text())
    except (OSError, ValueError):
        return {"seen": {}, "failures": 0, "last_blind_alert": 0}


def _save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state))
    tmp.replace(STATE_PATH)


def fetch_codex_rows(token: str) -> list[dict[str, Any]]:
    now_ms = int(time.time() * 1000)
    params = urllib.parse.urlencode(
        {
            "projectId": PROJECT_ID,
            "ownerId": OWNER_ID,
            "page": 0,
            "startDate": now_ms - WINDOW_HOURS * 3600 * 1000,
            "endDate": now_ms,
            "environment": "production",
            "search": "codex",
            "teamId": OWNER_ID,
        }
    )
    req = urllib.request.Request(
        f"https://vercel.com/api/logs/request-logs?{params}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    rows = data if isinstance(data, list) else (data.get("logs") or data.get("rows") or [])
    return [r for r in rows if isinstance(r, dict) and r.get("requestPath", "").startswith("/codex")]


def edge_regions(row: dict[str, Any]) -> set[str]:
    return {e.get("region", "") for e in (row.get("proxyEvents") or [])} - {""}


def classify_new_foreign(
    rows: list[dict[str, Any]], seen: dict[str, Any]
) -> list[dict[str, Any]]:
    """Return NEW events whose edge is outside SELF_EDGES (guilt),
    skipping self-noise and already-seen ids (innocence)."""
    out = []
    for r in rows:
        rid = r.get("requestId") or r.get("id") or ""
        if not rid or rid in seen:
            continue
        regions = edge_regions(r)
        foreign = regions - SELF_EDGES
        if not foreign:
            continue
        out.append(
            {
                "id": rid,
                "ts": r.get("timestamp", ""),
                "method": r.get("requestMethod", "?"),
                "status": r.get("statusCode", 0),
                "regions": sorted(foreign),
            }
        )
    return out


def _fmt_time(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        it = dt.astimezone(timezone(timedelta(hours=2)))
        return f"{it:%H:%M} IT"
    except ValueError:
        return ts


def _describe(ev: dict[str, Any]) -> str:
    where = ",".join(ev["regions"])
    zone = " (Europa)" if set(ev["regions"]) & EU_EDGES else ""
    m, s = ev["method"], ev["status"]
    if m == "POST" and s == 303:
        what = "PIN GIUSTO — è entrato"
    elif m == "POST":
        what = f"segno sbagliato alla porta ({s})"
    else:
        what = f"pagina caricata ({s})"
    return f"• {_fmt_time(ev['ts'])} da {where}{zone}: {what}"


def build_message(events: list[dict[str, Any]]) -> str:
    entered = any(e["method"] == "POST" and e["status"] == 303 for e in events)
    head = "📜 CODEX — qualcuno è ENTRATO" if entered else "📜 CODEX — movimento alla porta"
    lines = [_describe(e) for e in events[:10]]
    if len(events) > 10:
        lines.append(f"… e altri {len(events) - 10} eventi")
    return head + " (balizero.com/codex)\n" + "\n".join(lines)


def send_whatsapp(text: str) -> None:
    token = os.environ["WHATSAPP_TOKEN"]
    phone_id = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
    to = os.environ.get("CODEX_WATCH_ALERT_TO", DEFAULT_ALERT_TO)
    body = json.dumps(
        {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text[:4000]},
        }
    ).encode()
    req = urllib.request.Request(
        f"https://graph.facebook.com/v22.0/{phone_id}/messages",
        data=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        out = json.loads(resp.read())
    if not out.get("messages"):
        raise RuntimeError(f"WA send got no message id: {out}")


def main() -> int:
    if os.environ.get("CODEX_WATCH_TEST_PING") == "1":
        send_whatsapp("📜 Il ricettore del Codex è vivo: ti avviserò qui quando Leopoldo entra.")
        print("test ping sent")
        return 0

    state = _load_state()
    try:
        rows = fetch_codex_rows(os.environ["CODEX_WATCH_VERCEL_TOKEN"])
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, KeyError) as e:
        state["failures"] = int(state.get("failures", 0)) + 1
        print(f"fetch failed ({state['failures']} consecutive): {e}", file=sys.stderr)
        if state["failures"] >= BLIND_AFTER_FAILURES and (
            time.time() - state.get("last_blind_alert", 0) > BLIND_ALERT_COOLDOWN_H * 3600
        ):
            try:
                send_whatsapp(
                    "⚠️ Il ricettore del Codex è CIECO da ~1h (Vercel API failure). "
                    "Gli accessi di Leopoldo non sono osservati."
                )
                state["last_blind_alert"] = time.time()
            except OSError as we:
                print(f"blind-alert send failed too: {we}", file=sys.stderr)
        _save_state(state)
        return 1

    state["failures"] = 0
    events = classify_new_foreign(rows, state["seen"])
    now = time.time()
    for ev in events:
        state["seen"][ev["id"]] = now
    # prune old ids so the state file cannot grow unbounded
    cutoff = now - SEEN_TTL_HOURS * 3600
    state["seen"] = {k: v for k, v in state["seen"].items() if v > cutoff}

    if events:
        send_whatsapp(build_message(events))
        print(f"alerted: {len(events)} foreign events")
    else:
        print(f"quiet: {len(rows)} rows, all self")
    _save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
