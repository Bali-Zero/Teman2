#!/usr/bin/env python3
"""tp1_pin_smoketest.py — re-pin discipline for `team_bot.brain.tp1_client.TP1Model`.

Kimi refuter warning (directive#1§1's own evidence §4): "pin an explicit
VERSION, never an alias. Deprecation churn is quarterly, every re-pin needs
a smoke test." This script IS that smoke test: it calls the real, live
`GET /models` on the TP1 door and fails loudly if any of the three pinned
slugs (`qwen3.7-plus`, `qwen3.6-flash`, `glm-5.2`) has disappeared from the
plan's live roster — the exact failure mode a `model_not_found` 404 in
production would otherwise be the first sign of.

Usage:
    python3 scripts/duebot/tp1_pin_smoketest.py

Reads the key the same way `team_bot.brain.settings.load_tp1_api_key()`
does (`~/.qwen/settings.json`, `env.BAILIAN_TOKEN_PLAN_API_KEY`) — never
prints it, never logs it. Exit 0 iff every pinned slug is present in the
live `/models` response; exit 1 otherwise, with the missing slugs named on
stderr (never a value, never a header).

This is intentionally a standalone stdlib-only script (no `apps/team-bot`
import) so it can run as a pre-deploy/cron health-check without needing
that app's virtualenv — mirrors `scripts/arsenal_probe.py`'s own
`load_tp1_settings_key()`/`http_post_json()` shape.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

TP1_BASE_URL = "https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
PINNED_SLUGS = ("qwen3.7-plus", "qwen3.6-flash", "glm-5.2")


def load_key(path: str = "~/.qwen/settings.json") -> str:
    p = Path(os.path.expanduser(path))
    if not p.exists():
        print(f"FAIL: {p} not found", file=sys.stderr)
        sys.exit(1)
    try:
        parsed = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"FAIL: {p} unreadable: {type(e).__name__}", file=sys.stderr)
        sys.exit(1)
    value = (parsed.get("env") or {}).get("BAILIAN_TOKEN_PLAN_API_KEY")
    if not isinstance(value, str) or not value.strip():
        print(f"FAIL: env.BAILIAN_TOKEN_PLAN_API_KEY not set in {p}", file=sys.stderr)
        sys.exit(1)
    return value.strip()


def fetch_live_models(key: str, timeout: float = 20.0) -> list[str]:
    req = urllib.request.Request(
        f"{TP1_BASE_URL}/models", headers={"Authorization": f"Bearer {key}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"FAIL: GET /models returned HTTP {e.code}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:  # noqa: BLE001 — any transport failure is a hard FAIL here
        print(f"FAIL: GET /models transport error: {type(e).__name__}", file=sys.stderr)
        sys.exit(1)
    return sorted(m.get("id") for m in data.get("data", []) if isinstance(m, dict))


def main() -> int:
    key = load_key()
    live = fetch_live_models(key)
    missing = [slug for slug in PINNED_SLUGS if slug not in live]
    if missing:
        print(f"FAIL: pinned slug(s) no longer on the live TP1 roster: {missing}", file=sys.stderr)
        print(f"      live roster: {live}", file=sys.stderr)
        return 1
    print(f"OK: all {len(PINNED_SLUGS)} pinned slugs present on the live TP1 roster.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
