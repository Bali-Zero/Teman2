#!/usr/bin/env python3
"""openclaw-skill-audit.py — Sprint 0 Track A2

Audit OpenClaw skill ecosystem against the Telegram BOT_COMMANDS_TOO_MUCH
(100-command Telegram API limit) by:

  1. Reading ~/.openclaw/openclaw.json `skills.entries` and `plugins.entries`
     (Pro local read; SSH if running on Air via OPENCLAW_HOST=pro).
  2. Listing bundled skills under
     ~/.openclaw/lib/node_modules/openclaw/skills/* (each one contributes
     ≥1 command to the Telegram menu when enabled).
  3. Counting invocations in ~/.openclaw/logs/gateway.log over the last
     30 days (best-effort: skill names that appear next to `[skills]`,
     `tool_use`, or `command:/<name>` patterns).
  4. Emitting a JSON line per skill on stdout with a `recommendation`
     of `keep` / `disable` / `unknown` so it can be diffed before manual
     application.

Output schema (one JSON object per stdout line):

    {
      "skill": "notion",
      "kind": "user-enabled" | "bundled" | "plugin",
      "enabled": true,
      "invocations_30d": 12,
      "last_seen": "2026-04-30T12:33:01+0800" | null,
      "recommendation": "keep" | "disable" | "unknown",
      "reason": "string"
    }

Usage:

    # On Pro directly:
    python3 scripts/openclaw-skill-audit.py > audit.jsonl

    # On Air, reading Pro via SSH (does NOT modify Pro):
    OPENCLAW_HOST=pro python3 scripts/openclaw-skill-audit.py > audit.jsonl

NEVER modifies ~/.openclaw/openclaw.json. Application is manual via
`docs/audits/sprint0/openclaw-telegram-skills.md`.

Reference: brainstorm 2026-05-02 round 2, Codex flagged Telegram
BOT_COMMANDS_TOO_MUCH at 92-97 commands (100 hard limit).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

OPENCLAW_HOST = os.environ.get("OPENCLAW_HOST", "")
GATEWAY_LOG_TAIL = 50_000   # lines, ~3 months of gateway.log on Pro
DAYS_BACK = 30


def _read_remote(path: str) -> str | None:
    if not OPENCLAW_HOST:
        local = Path(path).expanduser()
        if not local.exists():
            return None
        return local.read_text(encoding="utf-8", errors="replace")
    proc = subprocess.run(
        ["ssh", OPENCLAW_HOST, f"cat {path}"],
        check=False, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


def _list_remote(path: str) -> list[str]:
    if not OPENCLAW_HOST:
        local = Path(path).expanduser()
        if not local.exists():
            return []
        return [p.name for p in local.iterdir() if p.is_dir()]
    proc = subprocess.run(
        ["ssh", OPENCLAW_HOST, f"ls -1 {path} 2>/dev/null"],
        check=False, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _tail_gateway_log(lines: int) -> str:
    path = "~/.openclaw/logs/gateway.log"
    if OPENCLAW_HOST:
        proc = subprocess.run(
            ["ssh", OPENCLAW_HOST, f"tail -n {lines} {path}"],
            check=False, capture_output=True, text=True,
        )
        return proc.stdout if proc.returncode == 0 else ""
    p = Path(path).expanduser()
    if not p.exists():
        return ""
    proc = subprocess.run(
        ["tail", "-n", str(lines), str(p)],
        check=False, capture_output=True, text=True,
    )
    return proc.stdout if proc.returncode == 0 else ""


def parse_config() -> dict[str, Any]:
    raw = _read_remote("~/.openclaw/openclaw.json")
    if not raw:
        sys.stderr.write("ERROR: cannot read ~/.openclaw/openclaw.json\n")
        sys.exit(2)
    return json.loads(raw)


def list_bundled_skills() -> list[str]:
    return sorted(_list_remote("~/.openclaw/lib/node_modules/openclaw/skills"))


_TS_PREFIX = re.compile(
    r"^\x1b\[?\d*m?(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+\+\d{2}:\d{2})"
)


def count_invocations(skills: list[str], log_text: str, cutoff: dt.datetime) -> dict[str, dict]:
    """Crude line-grep: count occurrences of each skill name in the log
    after the cutoff timestamp. Designed for "directional" signal, not
    forensic accuracy.
    """
    result = {s: {"count": 0, "last_seen": None} for s in skills}
    name_re = {
        s: re.compile(rf"\b{re.escape(s)}\b") for s in skills
    }
    for line in log_text.splitlines():
        m = _TS_PREFIX.match(line)
        if not m:
            continue
        try:
            ts = dt.datetime.fromisoformat(m.group(1))
        except ValueError:
            continue
        if ts.replace(tzinfo=None) < cutoff:
            continue
        for s, pat in name_re.items():
            if pat.search(line):
                result[s]["count"] += 1
                cur = result[s]["last_seen"]
                if cur is None or ts > dt.datetime.fromisoformat(cur):
                    result[s]["last_seen"] = ts.isoformat()
    return result


def recommend(kind: str, enabled: bool, count: int) -> tuple[str, str]:
    if kind == "user-enabled" and enabled and count == 0:
        return "disable", "user-enabled but 0 invocations in 30d"
    if kind == "user-enabled" and enabled and count > 0:
        return "keep", f"actively used ({count} invocations 30d)"
    if kind == "bundled" and not enabled and count == 0:
        return "keep", "bundled (loads regardless), 0 invocations — no menu cost reduction available without source patch"
    if kind == "bundled" and count > 0:
        return "keep", f"bundled, has {count} invocations — keep visible"
    if kind == "plugin":
        return "keep", "plugin — separate lifecycle from Telegram menu"
    return "unknown", "manual review required"


def main() -> None:
    cfg = parse_config()
    user_skills = cfg.get("skills", {}).get("entries", {})
    plugins = cfg.get("plugins", {}).get("entries", {})
    bundled = list_bundled_skills()

    cutoff = dt.datetime.utcnow() - dt.timedelta(days=DAYS_BACK)
    log_text = _tail_gateway_log(GATEWAY_LOG_TAIL)
    all_skills = sorted(set(list(user_skills.keys()) + bundled + list(plugins.keys())))
    counts = count_invocations(all_skills, log_text, cutoff)

    for name in all_skills:
        if name in user_skills:
            kind = "user-enabled"
            enabled = bool(user_skills[name].get("enabled"))
        elif name in plugins:
            kind = "plugin"
            enabled = bool(plugins[name].get("enabled"))
        else:
            kind = "bundled"
            enabled = True   # bundled skills load by default
        c = counts.get(name, {"count": 0, "last_seen": None})
        rec, reason = recommend(kind, enabled, c["count"])
        print(json.dumps({
            "skill": name,
            "kind": kind,
            "enabled": enabled,
            "invocations_30d": c["count"],
            "last_seen": c["last_seen"],
            "recommendation": rec,
            "reason": reason,
        }))


if __name__ == "__main__":
    main()
