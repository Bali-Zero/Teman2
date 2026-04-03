"""ARCH-2: Persona Engineering — inject and maintain persona notes in NLM notebooks.

Each domain notebook (NB-2 through NB-8) gets a "Persona Directive" source injected
as generated_text. The persona defines expertise boundary, reasoning style, anti-
hallucination directives, and output format for each domain.

Also configures chat persona via nlm chat configure (goal=custom).

Usage:
    # Inject all personas
    python -m apps.evaluator.nlm_deep_research.persona_engine --inject-all

    # Validate all personas exist (cron weekly)
    python -m apps.evaluator.nlm_deep_research.persona_engine --validate

    # Inject/restore single notebook
    python -m apps.evaluator.nlm_deep_research.persona_engine --inject nb2_immigration

    # Dry run
    python -m apps.evaluator.nlm_deep_research.persona_engine --validate --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────────────────

_DIR = Path(__file__).parent
DEFINITIONS_FILE = _DIR / "persona_definitions.json"
STATE_FILE = _DIR / "persona_state.json"

# ── Telegram ──────────────────────────────────────────────────────────────────

_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
_CHAT_ID = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "")


def _send_telegram(msg: str) -> None:
    if not _BOT_TOKEN or not _CHAT_ID:
        return
    try:
        data = json.dumps({"chat_id": _CHAT_ID, "text": msg, "parse_mode": "HTML"}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{_BOT_TOKEN}/sendMessage",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as exc:
        logger.warning("Telegram send failed: %s", exc)


# ── State persistence ─────────────────────────────────────────────────────────

def _load_state() -> dict[str, Any]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_state(state: dict[str, Any]) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


# ── NLM CLI helpers ───────────────────────────────────────────────────────────

def _nlm_source_list(notebook_id: str) -> list[dict[str, str]]:
    """Return list of {source_id, title} for a notebook via nlm CLI."""
    try:
        result = subprocess.run(
            ["nlm", "source", "list", notebook_id, "--json"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            logger.warning("nlm source list failed for %s: %s", notebook_id, result.stderr.strip())
            return []
        data = json.loads(result.stdout)
        # Handle multiple response shapes
        if isinstance(data, list):
            sources_raw = data
        elif isinstance(data, dict):
            sources_raw = data.get("value") or data.get("sources") or data.get("items") or []
        else:
            return []
        return [
            {"source_id": s.get("id") or s.get("source_id", ""), "title": s.get("title", "")}
            for s in sources_raw
            if isinstance(s, dict)
        ]
    except Exception as exc:
        logger.warning("Error listing sources for %s: %s", notebook_id, exc)
        return []


def _nlm_source_add(notebook_id: str, title: str, content: str, timeout: int = 90) -> str | None:
    """Add a text source to notebook. Returns source_id or None on failure."""
    try:
        result = subprocess.run(
            ["nlm", "source", "add", notebook_id, "--type", "text",
             "--title", title, "--text", content],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            logger.error("nlm source add failed: %s", result.stderr.strip())
            return None
        # Parse source ID from output
        for line in result.stdout.splitlines():
            if "source" in line.lower() and any(c == "-" for c in line):
                parts = line.strip().split()
                for part in parts:
                    if len(part) == 36 and part.count("-") == 4:
                        return part
        # Try JSON parse
        try:
            data = json.loads(result.stdout)
            return data.get("id") or data.get("source_id")
        except Exception:
            pass
        logger.warning("Could not parse source_id from output: %s", result.stdout[:200])
        return None
    except Exception as exc:
        logger.error("Error adding source to %s: %s", notebook_id, exc)
        return None


def _nlm_source_delete_cli(notebook_id: str, source_id: str, timeout: int = 30) -> bool:
    """Delete a source via nlm CLI with --confirm flag."""
    try:
        result = subprocess.run(
            ["nlm", "source", "delete", notebook_id, source_id, "--confirm"],
            capture_output=True, text=True, timeout=timeout,
        )
        return result.returncode == 0
    except Exception as exc:
        logger.warning("Error deleting source %s: %s", source_id, exc)
        return False


def _nlm_chat_configure(notebook_id: str, goal: str, custom_prompt: str) -> bool:
    """Configure chat persona for notebook."""
    try:
        cmd = ["nlm", "chat", "configure", notebook_id, "--goal", goal]
        if goal == "custom" and custom_prompt:
            cmd += ["--prompt", custom_prompt]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            logger.warning("chat configure failed for %s: %s", notebook_id, result.stderr.strip())
            return False
        return True
    except Exception as exc:
        logger.warning("Error configuring chat for %s: %s", notebook_id, exc)
        return False


# ── Core logic ────────────────────────────────────────────────────────────────

def load_definitions() -> dict[str, Any]:
    """Load persona definitions from JSON."""
    return json.loads(DEFINITIONS_FILE.read_text())


def _find_persona_source(notebook_id: str, source_title: str) -> str | None:
    """Return source_id of existing persona note, or None if missing."""
    sources = _nlm_source_list(notebook_id)
    for s in sources:
        if s["title"] == source_title:
            return s["source_id"]
    return None


def inject_persona(
    persona_key: str,
    persona_def: dict[str, Any],
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """Inject persona note into notebook.

    Returns dict with status, source_id, action taken.
    """
    notebook_id = persona_def["notebook_id"]
    source_title = persona_def["source_title"]
    persona_note = persona_def["persona_note"]
    chat_goal = persona_def.get("chat_goal", "custom")
    chat_prompt = persona_def.get("chat_custom_prompt", "")

    result: dict[str, Any] = {
        "persona_key": persona_key,
        "notebook_id": notebook_id,
        "action": "none",
        "source_id": None,
        "chat_configured": False,
        "error": None,
    }

    # Check if persona already exists
    existing_id = _find_persona_source(notebook_id, source_title)

    if existing_id and not force:
        logger.info("[%s] Persona already present (id=%s) — skip", persona_key, existing_id)
        result["action"] = "already_present"
        result["source_id"] = existing_id
        return result

    if dry_run:
        action = "would_reinject" if existing_id else "would_inject"
        logger.info("[%s] DRY RUN: %s", persona_key, action)
        result["action"] = action
        return result

    # Delete old persona if present (force refresh)
    if existing_id:
        logger.info("[%s] Removing old persona (id=%s)", persona_key, existing_id)
        _nlm_source_delete_cli(notebook_id, existing_id)
        time.sleep(1)

    # Inject new persona
    logger.info("[%s] Injecting persona note: '%s'", persona_key, source_title)
    source_id = _nlm_source_add(notebook_id, source_title, persona_note)

    if not source_id:
        result["action"] = "inject_failed"
        result["error"] = "source_add returned None"
        logger.error("[%s] Failed to inject persona", persona_key)
        return result

    result["action"] = "injected"
    result["source_id"] = source_id
    logger.info("[%s] Persona injected (id=%s)", persona_key, source_id)

    # Configure chat persona
    if chat_goal:
        configured = _nlm_chat_configure(notebook_id, chat_goal, chat_prompt)
        result["chat_configured"] = configured
        if configured:
            logger.info("[%s] Chat persona configured (goal=%s)", persona_key, chat_goal)
        else:
            logger.warning("[%s] Chat configure failed — persona note still active", persona_key)

    return result


def inject_all(dry_run: bool = False, force: bool = False) -> list[dict[str, Any]]:
    """Inject personas into all notebooks defined in persona_definitions.json."""
    definitions = load_definitions()
    results = []
    state = _load_state()

    for key, persona_def in definitions.items():
        logger.info("Processing %s (%s)", key, persona_def["label"])
        result = inject_persona(key, persona_def, dry_run=dry_run, force=force)
        results.append(result)

        if not dry_run and result["action"] in ("injected", "already_present"):
            state[key] = {
                "source_id": result["source_id"],
                "last_verified": _now_iso(),
                "status": "ok",
            }
        elif not dry_run and result["action"] == "inject_failed":
            state[key] = {
                "source_id": None,
                "last_verified": _now_iso(),
                "status": "error",
                "error": result["error"],
            }

        time.sleep(1)  # Rate limiting between notebooks

    if not dry_run:
        _save_state(state)

    return results


def validate_personas(dry_run: bool = False) -> list[dict[str, Any]]:
    """Validate all personas exist; auto-restore missing ones.

    Designed for weekly cron run.
    Returns list of validation results.
    """
    definitions = load_definitions()
    state = _load_state()
    results = []
    missing = []

    for key, persona_def in definitions.items():
        notebook_id = persona_def["notebook_id"]
        source_title = persona_def["source_title"]

        existing_id = _find_persona_source(notebook_id, source_title)

        if existing_id:
            logger.info("[%s] Persona OK (id=%s)", key, existing_id)
            state[key] = {"source_id": existing_id, "last_verified": _now_iso(), "status": "ok"}
            results.append({"persona_key": key, "status": "ok", "source_id": existing_id})
        else:
            logger.warning("[%s] Persona MISSING — restoring...", key)
            missing.append(key)

            if not dry_run:
                result = inject_persona(key, persona_def, dry_run=False, force=False)
                status = "restored" if result["action"] == "injected" else "restore_failed"
                state[key] = {
                    "source_id": result.get("source_id"),
                    "last_verified": _now_iso(),
                    "status": status,
                }
                results.append({
                    "persona_key": key,
                    "status": status,
                    "source_id": result.get("source_id"),
                })
            else:
                results.append({"persona_key": key, "status": "missing_dry_run"})

        time.sleep(0.5)

    if not dry_run:
        _save_state(state)

    if missing and not dry_run:
        restored = [k for k in missing if state.get(k, {}).get("status") == "restored"]
        failed = [k for k in missing if state.get(k, {}).get("status") == "restore_failed"]
        msg_parts = [f"<b>Persona Validation — {_now_iso()[:10]}</b>"]
        if restored:
            msg_parts.append(f"✅ Restored {len(restored)} missing personas: {', '.join(restored)}")
        if failed:
            msg_parts.append(f"❌ FAILED to restore: {', '.join(failed)}")
        _send_telegram("\n".join(msg_parts))

    return results


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [PersonaEngine] %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Persona Engine for NLM notebooks (ARCH-2)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--inject-all", action="store_true", help="Inject personas into all notebooks")
    group.add_argument("--validate", action="store_true", help="Validate all personas, restore missing")
    group.add_argument("--inject", metavar="PERSONA_KEY", help="Inject single persona by key")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, do not modify")
    parser.add_argument("--force", action="store_true", help="Re-inject even if persona already present")
    parser.add_argument("--list", action="store_true", help="List all defined persona keys and exit")

    args = parser.parse_args()

    if args.list:
        defs = load_definitions()
        for key, d in defs.items():
            print(f"{key:30s} | {d['label']:40s} | {d['notebook_id']}")
        return

    if args.inject_all:
        results = inject_all(dry_run=args.dry_run, force=args.force)
        injected = sum(1 for r in results if r["action"] == "injected")
        skipped = sum(1 for r in results if r["action"] == "already_present")
        failed = sum(1 for r in results if r["action"] == "inject_failed")
        print(f"\nSummary: {injected} injected, {skipped} already present, {failed} failed")
        if failed:
            sys.exit(1)

    elif args.validate:
        results = validate_personas(dry_run=args.dry_run)
        ok = sum(1 for r in results if r["status"] == "ok")
        restored = sum(1 for r in results if r["status"] == "restored")
        missing = sum(1 for r in results if r["status"] in ("missing_dry_run", "restore_failed"))
        print(f"\nValidation: {ok} OK, {restored} restored, {missing} missing/failed")
        if missing > 0:
            sys.exit(1)

    elif args.inject:
        defs = load_definitions()
        if args.inject not in defs:
            print(f"Unknown persona key: {args.inject}")
            print(f"Available: {', '.join(defs.keys())}")
            sys.exit(1)
        result = inject_persona(args.inject, defs[args.inject], dry_run=args.dry_run, force=args.force)
        print(f"Result: {result['action']} | source_id={result.get('source_id')} | chat={result.get('chat_configured')}")
        if result.get("error"):
            print(f"Error: {result['error']}")
            sys.exit(1)


if __name__ == "__main__":
    main()
