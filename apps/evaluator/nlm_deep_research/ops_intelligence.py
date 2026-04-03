"""ARCH-10: Ops Intelligence — weekly executive briefing from NB-11/12/13.

Runs Monday 08:00 WITA (00:00 UTC). Queries NB-11 and NB-12 for operational
intelligence, detects anomalies, and sends Telegram executive briefing.

Cron: 0 0 * * 1  (Monday 00:00 UTC = 08:00 WITA)

Usage:
    python -m apps.evaluator.nlm_deep_research.ops_intelligence --briefing
    python -m apps.evaluator.nlm_deep_research.ops_intelligence --briefing --dry-run
    python -m apps.evaluator.nlm_deep_research.ops_intelligence --check-anomalies
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

_DIR = Path(__file__).parent

# NB-11, NB-12, NB-13 IDs loaded from sync state
_SYNC_STATE_FILE = _DIR / "db_nlm_sync_state.json"

# Ops intelligence state
OPS_STATE_FILE = _DIR / "ops_intelligence_state.json"

_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
_CHAT_ID = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "")

# Query timeouts
NLM_QUERY_TIMEOUT = 120  # seconds

# Anomaly detection threshold
ANOMALY_THRESHOLD_PCT = 25.0

# ── NB IDs ────────────────────────────────────────────────────────────────────

def _load_nb_ids() -> dict[str, str]:
    """Load NB-11/12/13 IDs from db_nlm_sync state."""
    if not _SYNC_STATE_FILE.exists():
        return {}
    try:
        state = json.loads(_SYNC_STATE_FILE.read_text())
        return {
            "ops": state.get("nb_ops_id", ""),        # NB-11
            "intel": state.get("nb_intel_id", ""),    # NB-12
            "telemetry": state.get("nb_telemetry_id", ""),  # NB-13
        }
    except Exception as exc:
        logger.error("Failed to load NB IDs from sync state: %s", exc)
        return {}


# ── Telegram ──────────────────────────────────────────────────────────────────

def _send_telegram(msg: str, parse_mode: str = "HTML") -> bool:
    if not _BOT_TOKEN or not _CHAT_ID:
        logger.warning("Telegram not configured — TELEGRAM_BOT_TOKEN or TELEGRAM_OWNER_CHAT_ID missing")
        return False
    try:
        data = json.dumps({
            "chat_id": _CHAT_ID,
            "text": msg[:4096],  # Telegram limit
            "parse_mode": parse_mode,
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{_BOT_TOKEN}/sendMessage",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=15)
        return True
    except Exception as exc:
        logger.error("Telegram send failed: %s", exc)
        return False


# ── NLM query ─────────────────────────────────────────────────────────────────

def _query_notebook(notebook_id: str, query: str, timeout: int = NLM_QUERY_TIMEOUT) -> str | None:
    """Query a notebook via nlm CLI. Returns response text or None on failure."""
    if not notebook_id:
        logger.error("Empty notebook_id — cannot query")
        return None
    try:
        result = subprocess.run(
            ["nlm", "query", "notebook", notebook_id, query],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            logger.error("nlm query failed for %s: %s", notebook_id, result.stderr.strip())
            return None
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.error("nlm query timeout after %ds for notebook %s", timeout, notebook_id)
        return None
    except Exception as exc:
        logger.error("Error querying notebook %s: %s", notebook_id, exc)
        return None


# ── Anomaly detection ─────────────────────────────────────────────────────────

def _extract_anomalies_from_text(text: str) -> list[str]:
    """Extract anomaly signals from NLM response text.

    Looks for percentage indicators, 'increase', 'decrease', 'drop', 'spike',
    and formats them as anomaly lines.
    """
    if not text:
        return []

    anomalies = []
    keywords = [
        "anomal", "spike", "drop", "calo", "aumento", "increase", "decrease",
        "insolito", "critico", "⚠️", "alert", "rischio", "risk", "overdue",
        "scaduto", "ritardo", "unusual",
    ]
    # Negation phrases that indicate absence of anomaly — skip these lines
    negations = [
        "nessuna anomalia", "nessun rischio", "nessuna variazione",
        "nessun calo", "nessun aumento", "no anomal", "no risk",
        "normale", "stabile", "tutto ok", "tutto normale",
    ]
    lines = text.split("\n")
    for line in lines:
        line_lower = line.lower()
        # Skip lines that are explicit negations
        if any(neg in line_lower for neg in negations):
            continue
        if any(kw in line_lower for kw in keywords):
            clean = line.strip().lstrip("- *#")
            if clean and len(clean) > 10:
                anomalies.append(clean[:200])

    return anomalies[:10]


# ── State management ──────────────────────────────────────────────────────────

def _load_ops_state() -> dict[str, Any]:
    if OPS_STATE_FILE.exists():
        try:
            return json.loads(OPS_STATE_FILE.read_text())
        except Exception:
            pass
    return {
        "last_briefing": None,
        "briefings_count": 0,
        "last_anomaly_count": 0,
    }


def _save_ops_state(state: dict[str, Any]) -> None:
    OPS_STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _week_label() -> str:
    now = datetime.now(timezone.utc)
    return f"Settimana {now.strftime('%W')} — {now.strftime('%d %b %Y')}"


# ── Briefing generation ───────────────────────────────────────────────────────

# Weekly query templates for NB-11 (Ops Live)
OPS_QUERIES = [
    "Quali sono i 3 principali rischi operativi questa settimana? Include pratiche in ritardo, scadenze critiche e anomalie nei dati.",
    "Quanti clienti hanno pratiche aperte da più di 60 giorni? Quali sono i tipi di pratica più problematici?",
]

# Weekly query templates for NB-12 (Business Intelligence)
INTEL_QUERIES = [
    "Quali metriche di revenue o clienti sono fuori norma rispetto alla media mensile? Indica percentuali di variazione.",
    "Quali servizi stanno crescendo o calando nelle ultime settimane? Ci sono segnali di trend negativi?",
]


def run_briefing(dry_run: bool = False) -> dict[str, Any]:
    """Run weekly executive briefing.

    1. Query NB-11 (ops risks)
    2. Query NB-12 (intel anomalies)
    3. Detect anomalies from responses
    4. Build and send Telegram briefing
    5. Update state

    Returns dict with status and metrics.
    """
    result: dict[str, Any] = {
        "status": "ok",
        "week_label": _week_label(),
        "ops_queried": False,
        "intel_queried": False,
        "anomaly_count": 0,
        "telegram_sent": False,
        "dry_run": dry_run,
        "errors": [],
    }

    nb_ids = _load_nb_ids()
    nb_ops_id = nb_ids.get("ops", "")
    nb_intel_id = nb_ids.get("intel", "")

    if not nb_ops_id:
        result["status"] = "error"
        result["errors"].append("NB-11 (ops) ID not found in sync state")
        logger.error("NB-11 ID missing — cannot run briefing")
        return result

    if not nb_intel_id:
        result["status"] = "error"
        result["errors"].append("NB-12 (intel) ID not found in sync state")
        logger.error("NB-12 ID missing — cannot run briefing")
        return result

    # Query NB-11
    logger.info("Querying NB-11 (Ops Live): %s", OPS_QUERIES[0][:60])
    ops_response = None
    if not dry_run:
        ops_response = _query_notebook(nb_ops_id, OPS_QUERIES[0])
        if ops_response:
            result["ops_queried"] = True
            logger.info("NB-11 response: %d chars", len(ops_response))
        else:
            result["errors"].append("NB-11 query returned empty")
            logger.warning("NB-11 query failed or empty")
    else:
        ops_response = "[DRY RUN] NB-11 query would run here"
        result["ops_queried"] = True

    time.sleep(3)  # Rate limit between queries

    # Query NB-12
    logger.info("Querying NB-12 (Business Intelligence): %s", INTEL_QUERIES[0][:60])
    intel_response = None
    if not dry_run:
        intel_response = _query_notebook(nb_intel_id, INTEL_QUERIES[0])
        if intel_response:
            result["intel_queried"] = True
            logger.info("NB-12 response: %d chars", len(intel_response))
        else:
            result["errors"].append("NB-12 query returned empty")
            logger.warning("NB-12 query failed or empty")
    else:
        intel_response = "[DRY RUN] NB-12 query would run here"
        result["intel_queried"] = True

    # Detect anomalies
    all_text = (ops_response or "") + "\n" + (intel_response or "")
    anomalies = _extract_anomalies_from_text(all_text)
    result["anomaly_count"] = len(anomalies)
    logger.info("Anomalies detected: %d", len(anomalies))

    # Build Telegram briefing
    week_label = result["week_label"]
    ops_text = ops_response or "_Nessuna risposta da NB-11_"
    intel_text = intel_response or "_Nessuna risposta da NB-12_"

    anomaly_section = ""
    if anomalies:
        lines = "\n".join(f"• {a}" for a in anomalies[:5])
        anomaly_section = f"\n\n⚠️ <b>Anomalie rilevate ({len(anomalies)})</b>\n{lines}"

    briefing_msg = (
        f"📋 <b>Executive Ops Briefing</b> — {week_label}\n\n"
        f"<b>🔴 Rischi Operativi (NB-11)</b>\n{ops_text[:800]}\n\n"
        f"<b>💰 Business Intelligence (NB-12)</b>\n{intel_text[:800]}"
        f"{anomaly_section}"
    )

    logger.info("Briefing built (%d chars)", len(briefing_msg))

    if not dry_run:
        sent = _send_telegram(briefing_msg)
        result["telegram_sent"] = sent
        if not sent:
            result["errors"].append("Telegram send failed")
    else:
        logger.info("DRY RUN — would send Telegram:\n%s", briefing_msg[:300])
        result["telegram_sent"] = False

    # Update state
    if not dry_run:
        state = _load_ops_state()
        state["last_briefing"] = _now_iso()
        state["briefings_count"] = state.get("briefings_count", 0) + 1
        state["last_anomaly_count"] = len(anomalies)
        _save_ops_state(state)

    if result["errors"]:
        result["status"] = "partial" if (result["ops_queried"] or result["intel_queried"]) else "error"

    return result


def check_anomalies(dry_run: bool = False) -> dict[str, Any]:
    """Run anomaly-only check on NB-12 (Business Intelligence).

    Lighter than full briefing — used for mid-week checks.
    """
    result: dict[str, Any] = {
        "status": "ok",
        "anomaly_count": 0,
        "telegram_sent": False,
        "dry_run": dry_run,
    }

    nb_ids = _load_nb_ids()
    nb_intel_id = nb_ids.get("intel", "")

    if not nb_intel_id:
        result["status"] = "error"
        return result

    query = "Ci sono metriche anomale o fuori norma nel portfolio clienti o revenue questa settimana? Rispondi con sì/no e dettagli."
    logger.info("Anomaly check query on NB-12")

    if not dry_run:
        response = _query_notebook(nb_intel_id, query)
        if response:
            anomalies = _extract_anomalies_from_text(response)
            result["anomaly_count"] = len(anomalies)
            if anomalies:
                msg = f"⚠️ <b>Anomalie NB-12</b> ({_now_iso()[:10]})\n" + "\n".join(f"• {a}" for a in anomalies[:5])
                result["telegram_sent"] = _send_telegram(msg)
    else:
        logger.info("DRY RUN — would check NB-12 for anomalies")

    return result


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [OpsIntelligence] %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Ops Intelligence weekly briefing (ARCH-10)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--briefing", action="store_true", help="Run weekly executive briefing")
    group.add_argument("--check-anomalies", action="store_true", help="Run anomaly check only")
    group.add_argument("--status", action="store_true", help="Show ops intelligence status")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, do not send Telegram")

    args = parser.parse_args()

    if args.status:
        state = _load_ops_state()
        nb_ids = _load_nb_ids()
        print(f"Last briefing: {state.get('last_briefing', 'never')}")
        print(f"Total briefings: {state.get('briefings_count', 0)}")
        print(f"Last anomaly count: {state.get('last_anomaly_count', 0)}")
        print(f"NB-11 (ops): {nb_ids.get('ops', 'NOT CONFIGURED')}")
        print(f"NB-12 (intel): {nb_ids.get('intel', 'NOT CONFIGURED')}")
        print(f"NB-13 (telemetry): {nb_ids.get('telemetry', 'NOT CONFIGURED')}")
        return

    if args.briefing:
        result = run_briefing(dry_run=args.dry_run)
        print(f"\nBriefing: {result['status']}")
        print(f"  Week: {result['week_label']}")
        print(f"  NB-11 queried: {result['ops_queried']}")
        print(f"  NB-12 queried: {result['intel_queried']}")
        print(f"  Anomalies: {result['anomaly_count']}")
        print(f"  Telegram sent: {result['telegram_sent']}")
        if result["errors"]:
            print(f"  Errors: {result['errors']}")
        sys.exit(0 if result["status"] != "error" else 1)

    elif args.check_anomalies:
        result = check_anomalies(dry_run=args.dry_run)
        print(f"Anomaly check: {result['status']}")
        print(f"  Anomalies found: {result['anomaly_count']}")
        print(f"  Telegram sent: {result['telegram_sent']}")
        sys.exit(0 if result["status"] == "ok" else 1)


if __name__ == "__main__":
    main()
