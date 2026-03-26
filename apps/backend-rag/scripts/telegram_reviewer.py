#!/usr/bin/env python3
"""Telegram Reviewer — Step 6 of the Verified Generation Pipeline.

Sends failed claims to Zero via Telegram for human review.
Polls for /approve or /reject reply (30 min timeout).

Exit codes:
  0 — approved
  1 — rejected or timeout
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

POLL_INTERVAL_SEC = 15
TIMEOUT_SEC = 30 * 60


def send_telegram_message(token: str, chat_id: str, text: str) -> dict:  # type: ignore[type-arg]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())  # type: ignore[no-any-return]


def get_updates(token: str, offset: int = 0) -> list[dict]:  # type: ignore[type-arg]
    url = f"https://api.telegram.org/bot{token}/getUpdates?offset={offset}&timeout=10"
    with urllib.request.urlopen(url, timeout=15) as resp:
        data = json.loads(resp.read())
    return data.get("result", [])  # type: ignore[no-any-return]


def build_review_message(report: object, document_name: str) -> str:
    """Build Telegram review message from a VerificationReport (dataclass or dict)."""
    # Handle both dataclass and dict (e.g. deserialized from JSON)
    if isinstance(report, dict):
        blocked = report.get("blocked_claims", [])
        ratio = report.get("verified_ratio", 0)
        total = report.get("total_claims", 0)
        verified = report.get("verified_count", 0)
        results = report.get("results", [])
    else:
        blocked = getattr(report, "blocked_claims", [])
        ratio = getattr(report, "verified_ratio", 0)
        total = getattr(report, "total_claims", 0)
        verified = getattr(report, "verified_count", 0)
        results = getattr(report, "results", [])

    failed_results = []
    for r in results:
        if isinstance(r, dict):
            if r.get("verdict") != "FAITHFUL":
                failed_results.append(r)
        else:
            if getattr(r, "verdict", None) != "FAITHFUL":
                failed_results.append(r)

    lines = [
        "\u26a0\ufe0f *NB Pipeline \u2014 Human Review Required*",
        f"\U0001f4c4 Document: `{document_name}`",
        f"\U0001f4ca Verification: {verified}/{total} claims verified ({ratio:.0%})",
        "",
        "*Blocked claims:*",
    ]
    for i, result in enumerate(failed_results[:10], 1):
        if isinstance(result, dict):
            cid = result.get("claim_id", "?")
            verdict = result.get("verdict", "UNCERTAIN")
            reason = result.get("reason", "")
        else:
            cid = getattr(result, "claim_id", "?")
            verdict = getattr(result, "verdict", "UNCERTAIN")
            reason = getattr(result, "reason", "")
        lines.append(f"{i}. `{cid}` \u2192 {verdict}")
        lines.append(f"   _{reason}_")
    if len(blocked) > 10:
        lines.append(f"   ...and {len(blocked) - 10} more")

    lines += ["", "Reply with:", "/approve \u2014 upload to NLM", "/reject \u2014 discard, fix required"]
    return "\n".join(lines)


def poll_for_decision(token: str, chat_id: str, message: str) -> str:
    """Send message to Telegram, then poll for /approve or /reject.
    Returns 'approved', 'rejected', or 'timeout'."""
    send_telegram_message(token, chat_id, message)

    offset = 0
    updates = get_updates(token, offset=0)
    if updates:
        offset = updates[-1]["update_id"] + 1

    deadline = time.time() + TIMEOUT_SEC
    while time.time() < deadline:
        updates = get_updates(token, offset=offset)
        for upd in updates:
            offset = upd["update_id"] + 1
            msg = upd.get("message", {})
            if str(msg.get("chat", {}).get("id", "")) != str(chat_id):
                continue
            text = msg.get("text", "").strip().lower()
            if text.startswith("/approve"):
                return "approved"
            if text.startswith("/reject"):
                return "rejected"
        time.sleep(POLL_INTERVAL_SEC)
        remaining = (deadline - time.time()) / 60
        print(f"  Waiting for decision... ({remaining:.0f} min remaining)", end="\r")  # noqa: T201

    return "timeout"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--document-name", required=True)
    args = parser.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_ZERO_CHAT_ID", "")
    if not token or not chat_id:
        print("ERROR: TELEGRAM_BOT_TOKEN and TELEGRAM_ZERO_CHAT_ID must be set", file=sys.stderr)  # noqa: T201
        sys.exit(1)

    report = json.loads(Path(args.report).read_text())
    message = build_review_message(report, args.document_name)

    print("Sending review request to Telegram and waiting for Zero's decision (/approve or /reject)...")  # noqa: T201
    decision = poll_for_decision(token, chat_id, message)

    if decision == "approved":
        print("\nApproved — proceeding with NLM upload")  # noqa: T201
        sys.exit(0)
    elif decision == "rejected":
        print("\nRejected — document will not be uploaded")  # noqa: T201
        sys.exit(1)
    else:
        print("\nTimeout (30 min) — treating as rejected for safety")  # noqa: T201
        send_telegram_message(token, chat_id, "Timeout \u2014 document NOT uploaded (safety default).")
        sys.exit(1)


if __name__ == "__main__":
    main()
