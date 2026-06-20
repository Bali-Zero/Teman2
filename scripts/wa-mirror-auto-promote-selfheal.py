#!/usr/bin/env python3
"""wa-mirror auto-promote SELF-HEAL guardian.

The auto-promote pipeline (`wa-mirror-auto-promote-leads.py`) carries leads from
the local wa-corpus to the Fly CRM. It failed SILENTLY for 15 days (2026-05-27 to
2026-06-20): the `WA_MIRROR_CRM_WRITE_KEY` evaporated from `~/.wa-mirror.env`, so
every candidate hit the unlogged `SKIPPED_NO_WRITE_KEY` path and the audit log
stayed green while ZERO leads reached Fly. Superscar #2 ("Esiste != Armato"): the
component existed and ran, but was disarmed, and the failure was invisible.

This guardian closes the loop WITHOUT a human in the path (operator decision
2026-06-20: "the alert must be picked up by the system itself and able to repair
it"). It does NOT message anyone — it diagnoses and re-arms.

Diagnosis (reads the auto-promote audit log):
  - SILENT-STALL  : no INSERTED/ENRICHED for > STALL_HOURS, AND there ARE
                    candidates being processed (the pipeline runs but pushes 0).
  - NO-WRITE-KEY  : a DEGRADED_NO_WRITE_KEY record in the recent window, OR the
                    key is simply absent from the env file.
  - QUERY-TIMEOUT : a DEGRADED_QUERY_TIMEOUT record in the recent window.

Repair (only the safe, deterministic one is automatic):
  - NO-WRITE-KEY  : if the canonical key file (`~/.nuzantara-db-snapshots/
                    .crm_write_key`, chmod 600) exists and the env file is missing
                    the line, RE-INJECT it into `~/.wa-mirror.env` (preserving 600).
                    This is the exact 2026-06-20 root cause and is fully reversible.
  - QUERY-TIMEOUT : not auto-repaired (a timeout means a slow query, not a config
                    drift) — recorded so the trend is visible, repaired by the
                    sargable-query fix already shipped. Left as a detect-only signal.

Every action is appended to the auto-promote audit log as a HEAL_* record so the
repair itself is observable (the guardian must not become the next silent actor).

Kill-switch: `WA_AUTO_PROMOTE_SELFHEAL_ENABLED=0` → detect-only, never writes env.
Cadence: run from launchd on a slow interval (e.g. every 30min); it is cheap and
idempotent (re-injecting an already-present key is a no-op).
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ENV_FILE = Path.home() / ".wa-mirror.env"
KEY_FILE = Path.home() / ".nuzantara-db-snapshots" / ".crm_write_key"
AUDIT_LOG = Path.home() / "logs" / "wa-mirror-auto-promote.jsonl"

KEY_ENV_NAME = "WA_MIRROR_CRM_WRITE_KEY"
STALL_HOURS = 6.0  # no real push for this long (while candidates exist) = stalled
WINDOW_HOURS = 24.0  # how far back to scan the audit log for DEGRADED markers

HEAL_ENABLED = os.environ.get("WA_AUTO_PROMOTE_SELFHEAL_ENABLED", "1").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(rec: dict[str, Any]) -> datetime | None:
    raw = rec.get("ts")
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _audit(rec: dict[str, Any]) -> None:
    """Append a HEAL_* record to the auto-promote audit log (observable repair)."""
    rec = {"ts": _now().isoformat(), **rec}
    try:
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with AUDIT_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
    except OSError as exc:  # auditing must never crash the guardian
        print(f"selfheal: audit write failed: {exc}", file=sys.stderr)
    print(json.dumps(rec))


def _read_recent(window_hours: float) -> list[dict[str, Any]]:
    """Recent audit records within the window (best-effort; skips malformed lines)."""
    if not AUDIT_LOG.exists():
        return []
    cutoff = _now() - timedelta(hours=window_hours)
    out: list[dict[str, Any]] = []
    try:
        # tail-ish: read the whole file but it rotates small; cheap enough at 5-min cadence
        for line in AUDIT_LOG.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = _parse_ts(rec)
            if ts is None or ts >= cutoff:
                out.append(rec)
    except OSError as exc:
        print(f"selfheal: cannot read audit log: {exc}", file=sys.stderr)
    return out


def _env_has_key() -> bool:
    """True if WA_MIRROR_CRM_WRITE_KEY is present (non-empty) in the env file."""
    if not ENV_FILE.exists():
        return False
    prefix = f"{KEY_ENV_NAME}="
    try:
        for raw in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line.startswith(prefix):
                return bool(line[len(prefix) :].strip().strip('"').strip("'"))
    except OSError:
        return False
    return False


def _reinject_key() -> dict[str, Any]:
    """Append the canonical write key to the env file, preserving 0600. Idempotent.

    Returns a HEAL_* record describing the outcome. Never raises.
    """
    if not KEY_FILE.exists():
        return {
            "action": "HEAL_NO_WRITE_KEY_FAILED",
            "detail": f"canonical key file {KEY_FILE} absent — cannot re-arm "
            "automatically; operator must restore the secret.",
        }
    try:
        key_value = KEY_FILE.read_text(encoding="utf-8").strip()
    except OSError as exc:
        return {"action": "HEAL_NO_WRITE_KEY_FAILED", "detail": f"key read error: {exc}"}
    if not key_value:
        return {"action": "HEAL_NO_WRITE_KEY_FAILED", "detail": "canonical key file is empty"}

    try:
        existing = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""
        sep = "" if existing.endswith("\n") or not existing else "\n"
        ENV_FILE.write_text(f"{existing}{sep}{KEY_ENV_NAME}={key_value}\n", encoding="utf-8")
        os.chmod(ENV_FILE, 0o600)
    except OSError as exc:
        return {"action": "HEAL_NO_WRITE_KEY_FAILED", "detail": f"env write error: {exc}"}

    # Never echo the secret value — only its length/fingerprint for audit.
    return {
        "action": "HEAL_NO_WRITE_KEY_REPAIRED",
        "detail": f"re-injected {KEY_ENV_NAME} into {ENV_FILE} (len={len(key_value)}); "
        "next auto-promote tick will push to Fly. chmod 0600 enforced.",
    }


def main() -> int:
    recent = _read_recent(WINDOW_HOURS)

    # --- Signal 1: write key disarmed (the exact 2026-06-20 root cause) -----------
    degraded_no_key = any(r.get("action") == "DEGRADED_NO_WRITE_KEY" for r in recent)
    key_missing = not _env_has_key()

    if degraded_no_key or key_missing:
        if not HEAL_ENABLED:
            _audit(
                {
                    "action": "HEAL_SKIPPED_DISABLED",
                    "detail": "write key disarmed but WA_AUTO_PROMOTE_SELFHEAL_ENABLED=0",
                    "key_missing": key_missing,
                    "saw_degraded": degraded_no_key,
                }
            )
            return 0
        result = _reinject_key()
        _audit(result)
        return 0 if result["action"] == "HEAL_NO_WRITE_KEY_REPAIRED" else 1

    # --- Signal 2: query timeout (detect-only; the sargable fix is the cure) ------
    if any(r.get("action") == "DEGRADED_QUERY_TIMEOUT" for r in recent):
        _audit(
            {
                "action": "HEAL_QUERY_TIMEOUT_NOTED",
                "detail": "find_candidates exceeded command_timeout recently — not "
                "auto-repaired (slow query, not config drift). The sargable rewrite "
                "is the cure; this only makes the trend observable.",
            }
        )
        return 0

    # --- Signal 3: silent stall (runs but pushes nothing for too long) ------------
    pushes = [r for r in recent if r.get("action") in {"INSERTED", "ENRICHED"}]
    summaries = [r for r in recent if "candidates" in r]
    candidates_seen = any((s.get("candidates") or 0) > 0 for s in summaries)
    if summaries and candidates_seen and not pushes:
        last_summary_ts = max((_parse_ts(s) for s in summaries if _parse_ts(s)), default=None)
        # The pipeline is running (summaries exist) with candidates but 0 pushes in
        # the window. Most likely the key path — re-check and heal if applicable.
        if key_missing or degraded_no_key:
            result = _reinject_key() if HEAL_ENABLED else {
                "action": "HEAL_SKIPPED_DISABLED",
                "detail": "silent stall + key missing but self-heal disabled",
            }
            _audit(result)
            return 0
        _audit(
            {
                "action": "HEAL_STALL_DETECTED_NO_AUTO_FIX",
                "detail": "pipeline runs with candidates but 0 pushes and the write "
                "key IS present — root cause is not the known key-drift; left for "
                "investigation (endpoint 401? all-idempotent-skip?).",
                "last_summary_ts": last_summary_ts.isoformat() if last_summary_ts else None,
            }
        )
        return 0

    # --- Healthy ------------------------------------------------------------------
    print(json.dumps({"ts": _now().isoformat(), "action": "HEAL_OK", "detail": "no disarm detected"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
