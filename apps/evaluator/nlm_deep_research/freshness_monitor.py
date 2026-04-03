"""ARCH-5 Layer C: Regulatory Freshness Monitor.

Monitors Indonesian government websites for regulatory changes via Gemini CLI
(which has built-in web search). When a change is detected, triggers
`nlm research start` on the relevant notebook for auto-remediation.

Also reads coverage_matrix.json (from gap_scanner.py) to find STALE/GAP topics
that need remediation and triggers targeted research queries.

Cron schedule:
    07:00 WITA (23:00 UTC) and 19:00 WITA (11:00 UTC) daily
    0 23,11 * * *

Usage:
    python -m apps.evaluator.nlm_deep_research.freshness_monitor --scan
    python -m apps.evaluator.nlm_deep_research.freshness_monitor --remediate-stale
    python -m apps.evaluator.nlm_deep_research.freshness_monitor --scan --dry-run
    python -m apps.evaluator.nlm_deep_research.freshness_monitor --status
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

from apps.evaluator.nlm_deep_research.gap_scanner import DOMAIN_TOPICS

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────

_DIR = Path(__file__).parent
COVERAGE_MATRIX_FILE = _DIR / "coverage_matrix.json"
FRESHNESS_STATE_FILE = _DIR / "freshness_monitor_state.json"

# ── Config ────────────────────────────────────────────────────────────────────

_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
_CHAT_ID = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "")

# Gemini CLI timeout for web search queries
GEMINI_TIMEOUT = 120

# Max remediation queries per run (avoid NLM rate limiting)
MAX_REMEDIATIONS_PER_RUN = 3

# Indonesian government domains to monitor
REGULATORY_DOMAINS = [
    {
        "name": "Imigrasi (Immigration)",
        "query": "site:imigrasi.go.id OR site:kemenkumham.go.id berita terbaru peraturan imigrasi visa KITAS Indonesia 2025 2026",
        "notebook_domain": "immigration",
        "notebook_id": "cff93ab0-813a-42f2-a8de-36987e724271",
    },
    {
        "name": "OSS (Business Registration)",
        "query": "site:oss.go.id OR site:bkpm.go.id perubahan terbaru izin usaha NIB investasi PMA Indonesia 2025 2026",
        "notebook_domain": "company",
        "notebook_id": "933509f9-1561-403d-bd44-4a7a67a36df2",
    },
    {
        "name": "DJP (Tax Authority)",
        "query": "site:pajak.go.id OR site:kemenkeu.go.id perubahan pajak CoreTax PMK PPh PPN Indonesia 2025 2026",
        "notebook_domain": "tax",
        "notebook_id": "d4b2eedb-9863-4a1a-81ff-a11b0b45d853",
    },
    {
        "name": "BPN (Land Registry)",
        "query": "site:atrbpn.go.id OR site:bpn.go.id perubahan peraturan HGB hak milik properti asing Indonesia 2025 2026",
        "notebook_domain": "property",
        "notebook_id": "d9438180-5e63-4e2a-a473-6061101f6a8d",
    },
    {
        "name": "Ketenagakerjaan (Labour)",
        "query": "site:kemnaker.go.id OR site:bpjsketenagakerjaan.go.id perubahan UMR BPJS UU Cipta Kerja ketenagakerjaan 2025 2026",
        "notebook_domain": "operations",
        "notebook_id": "85207af3-352f-4554-8d2a-18f42cc541ba",
    },
]

# Research query templates for NLM Deep Research
RESEARCH_QUERY_TEMPLATES = {
    "immigration": "Latest changes to Indonesian immigration regulations KITAS KITAP visa requirements 2025 2026",
    "company": "Latest changes to PT PMA business registration OSS NIB requirements Indonesia 2025 2026",
    "tax": "Latest Indonesian tax regulation changes CoreTax PPh PPN compliance requirements 2025 2026",
    "property": "Latest changes to foreign property ownership rules HGB Hak Pakai Indonesia 2025 2026",
    "operations": "Latest changes to Indonesian employment law BPJS minimum wage UMR compliance 2025 2026",
}

# How long to wait between research triggers (rate limiting NLM)
RESEARCH_TRIGGER_DELAY = 30  # seconds


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run_gemini_search(query: str, timeout: int = GEMINI_TIMEOUT) -> str | None:
    """Run Gemini CLI with web search for regulatory monitoring.

    Uses gemini -p for headless mode with built-in web search.
    No API SDK — uses CLI tool.
    """
    prompt = (
        f"Search the web for: {query}\n\n"
        "Report ONLY if there are NEW regulatory changes, laws, or announcements "
        "from the past 30 days. If nothing significant found, respond with ONLY: NO_CHANGE\n"
        "If changes found, summarize in 2-3 bullet points with dates."
    )
    try:
        result = subprocess.run(
            ["gemini", "-p", prompt, "--model", "gemini-3-flash-preview"],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            logger.warning("Gemini CLI error: %s", result.stderr.strip()[:200])
            return None
        return result.stdout.strip() or None
    except subprocess.TimeoutExpired:
        logger.warning("Gemini search timeout after %ds", timeout)
        return None
    except FileNotFoundError:
        logger.error("gemini CLI not found — is it installed?")
        return None
    except Exception as exc:
        logger.error("Gemini search error: %s", exc)
        return None


def _trigger_nlm_research(notebook_id: str, query: str, mode: str = "fast", timeout: int = 30) -> bool:
    """Trigger NLM Deep Research on a notebook via nlm CLI.

    Returns True if research was triggered successfully.
    Note: research runs async — we don't wait for results.
    """
    try:
        result = subprocess.run(
            ["nlm", "research", "start", notebook_id, "--query", query, "--mode", mode],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            logger.error("nlm research start failed: %s", result.stderr.strip()[:200])
            return False
        logger.info("Research triggered for notebook %s: %s", notebook_id[:8], query[:60])
        return True
    except subprocess.TimeoutExpired:
        logger.warning("nlm research start timeout")
        return False
    except Exception as exc:
        logger.error("Error triggering research: %s", exc)
        return False


def _send_telegram(msg: str) -> None:
    if not _BOT_TOKEN or not _CHAT_ID:
        return
    try:
        data = json.dumps({
            "chat_id": _CHAT_ID,
            "text": msg[:4096],
            "parse_mode": "HTML",
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{_BOT_TOKEN}/sendMessage",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as exc:
        logger.warning("Telegram send failed: %s", exc)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── State ─────────────────────────────────────────────────────────────────────

def _load_state() -> dict[str, Any]:
    if FRESHNESS_STATE_FILE.exists():
        try:
            return json.loads(FRESHNESS_STATE_FILE.read_text())
        except Exception:
            pass
    return {
        "last_scan": None,
        "last_remediation": None,
        "scan_count": 0,
        "remediations_triggered": 0,
        "changes_detected": {},
    }


def _save_state(state: dict[str, Any]) -> None:
    FRESHNESS_STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


# ── Layer C: Regulatory scan ──────────────────────────────────────────────────

def run_scan(dry_run: bool = False) -> dict[str, Any]:
    """Layer C: Scan government domains for regulatory changes.

    Uses Gemini CLI (web search) to detect new regulations.
    Triggers nlm research start for domains with detected changes.
    """
    result: dict[str, Any] = {
        "status": "ok",
        "domains_scanned": 0,
        "changes_detected": 0,
        "research_triggered": 0,
        "dry_run": dry_run,
        "errors": [],
        "changes": {},
    }

    state = _load_state()

    for domain_config in REGULATORY_DOMAINS:
        name = domain_config["name"]
        query = domain_config["query"]
        nb_domain = domain_config["notebook_domain"]
        nb_id = domain_config["notebook_id"]

        logger.info("Scanning %s...", name)
        result["domains_scanned"] += 1

        if dry_run:
            logger.info("  DRY RUN: would search for '%s'", query[:60])
            continue

        response = _run_gemini_search(query)

        if not response:
            logger.warning("  No response from Gemini for %s", name)
            result["errors"].append(f"{name}: no Gemini response")
            time.sleep(5)
            continue

        # Check if change detected
        if "NO_CHANGE" in response.upper():
            logger.info("  No regulatory changes detected for %s", name)
            state["changes_detected"][nb_domain] = {
                "last_checked": _now_iso(),
                "change_detected": False,
            }
        else:
            logger.info("  CHANGE DETECTED for %s: %s", name, response[:100])
            result["changes_detected"] += 1
            result["changes"][nb_domain] = response[:500]
            state["changes_detected"][nb_domain] = {
                "last_checked": _now_iso(),
                "change_detected": True,
                "summary": response[:300],
            }

            # Trigger NLM research
            if result["research_triggered"] < MAX_REMEDIATIONS_PER_RUN:
                research_query = RESEARCH_QUERY_TEMPLATES.get(nb_domain, query)
                triggered = _trigger_nlm_research(nb_id, research_query, mode="fast")
                if triggered:
                    result["research_triggered"] += 1
                    state["remediations_triggered"] = state.get("remediations_triggered", 0) + 1
                    logger.info("  Research triggered for %s", nb_domain)
                    time.sleep(RESEARCH_TRIGGER_DELAY)

        time.sleep(10)  # Rate limit between Gemini searches

    if not dry_run:
        state["last_scan"] = _now_iso()
        state["scan_count"] = state.get("scan_count", 0) + 1
        _save_state(state)

    # Telegram alert if changes found
    if result["changes_detected"] > 0 and not dry_run:
        msg_lines = [f"🔔 <b>Regulatory Monitor — {result['changes_detected']} cambiamenti rilevati</b>\n"]
        for domain, change_summary in result["changes"].items():
            msg_lines.append(f"<b>{domain.title()}</b>: {change_summary[:200]}")
            msg_lines.append("")
        if result["research_triggered"] > 0:
            msg_lines.append(f"✅ {result['research_triggered']} ricerche NLM avviate automaticamente")
        _send_telegram("\n".join(msg_lines))

    if result["errors"]:
        result["status"] = "partial"

    return result


# ── Stale topic remediation ───────────────────────────────────────────────────

def remediate_stale(dry_run: bool = False) -> dict[str, Any]:
    """Read coverage_matrix.json, find STALE/GAP topics, trigger NLM research.

    Prioritizes: GAP > STALE. Max MAX_REMEDIATIONS_PER_RUN per invocation
    to avoid overwhelming NLM rate limits.
    """
    result: dict[str, Any] = {
        "status": "ok",
        "stale_topics": 0,
        "gap_topics": 0,
        "remediations_triggered": 0,
        "dry_run": dry_run,
        "errors": [],
    }

    if not COVERAGE_MATRIX_FILE.exists():
        logger.warning("coverage_matrix.json not found — run gap_scanner --layer-b first")
        result["status"] = "skipped"
        return result

    matrix = json.loads(COVERAGE_MATRIX_FILE.read_text())
    state = _load_state()

    # Collect stale/gap topics sorted by priority
    remediation_targets: list[tuple[str, str, str, str]] = []  # (priority, domain, topic, nb_id)

    for domain, data in matrix.items():
        coverage = data.get("coverage", {})
        # Find notebook_id from domain topics config
        nb_id = DOMAIN_TOPICS.get(domain, {}).get("notebook_id", "")
        if not nb_id:
            continue

        for topic, classification in coverage.items():
            if classification == "GAP":
                result["gap_topics"] += 1
                remediation_targets.append(("1_gap", domain, topic, nb_id))
            elif classification == "STALE":
                result["stale_topics"] += 1
                remediation_targets.append(("2_stale", domain, topic, nb_id))

    # Sort by priority (GAP first) and take first MAX_REMEDIATIONS_PER_RUN
    remediation_targets.sort(key=lambda x: x[0])
    targets_to_process = remediation_targets[:MAX_REMEDIATIONS_PER_RUN]

    logger.info("Found %d GAP + %d STALE topics. Processing %d remediations.",
                result["gap_topics"], result["stale_topics"], len(targets_to_process))

    for priority, domain, topic, nb_id in targets_to_process:
        logger.info("Remediating [%s] %s: %s", priority, domain, topic[:60])

        if not dry_run:
            research_query = f"{topic} Indonesia 2025 2026 latest regulations"
            triggered = _trigger_nlm_research(nb_id, research_query, mode="fast")
            if triggered:
                result["remediations_triggered"] += 1
                time.sleep(RESEARCH_TRIGGER_DELAY)
            else:
                result["errors"].append(f"{domain}/{topic[:40]}: trigger failed")
        else:
            logger.info("  DRY RUN: would trigger research for '%s'", topic[:60])
            result["remediations_triggered"] += 1

    if not dry_run and result["remediations_triggered"] > 0:
        state["last_remediation"] = _now_iso()
        _save_state(state)

        _send_telegram(
            f"🔧 <b>Freshness Monitor — Remediation</b>\n"
            f"GAP topics: {result['gap_topics']}\n"
            f"STALE topics: {result['stale_topics']}\n"
            f"Ricerche avviate: {result['remediations_triggered']}"
        )

    if result["errors"]:
        result["status"] = "partial"

    return result


def get_status() -> dict[str, Any]:
    state = _load_state()
    return {
        "last_scan": state.get("last_scan"),
        "last_remediation": state.get("last_remediation"),
        "scan_count": state.get("scan_count", 0),
        "remediations_triggered": state.get("remediations_triggered", 0),
        "changes_detected": state.get("changes_detected", {}),
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [FreshnessMonitor] %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Freshness Monitor — ARCH-5 Layer C")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--scan", action="store_true",
                       help="Scan government sites for regulatory changes (bi-daily)")
    group.add_argument("--remediate-stale", action="store_true",
                       help="Trigger NLM research for STALE/GAP topics from coverage matrix")
    group.add_argument("--status", action="store_true",
                       help="Show freshness monitor state")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview only, do not query Gemini or trigger NLM research")

    args = parser.parse_args()

    if args.status:
        status = get_status()
        print(f"Last scan: {status['last_scan'] or 'never'}")
        print(f"Last remediation: {status['last_remediation'] or 'never'}")
        print(f"Total scans: {status['scan_count']}")
        print(f"Total remediations triggered: {status['remediations_triggered']}")
        print(f"\nChanges detected per domain:")
        for domain, data in status["changes_detected"].items():
            icon = "🔴" if data.get("change_detected") else "🟢"
            print(f"  {icon} {domain}: {data.get('last_checked', 'never')[:16]}")
        return

    if args.scan:
        result = run_scan(dry_run=args.dry_run)
        print(f"\nScan: {result['status']}")
        print(f"  Domains scanned: {result['domains_scanned']}")
        print(f"  Changes detected: {result['changes_detected']}")
        print(f"  Research triggered: {result['research_triggered']}")
        if result["errors"]:
            print(f"  Errors: {result['errors']}")
        sys.exit(0 if result["status"] in ("ok", "partial") else 1)

    elif args.remediate_stale:
        result = remediate_stale(dry_run=args.dry_run)
        print(f"\nRemediation: {result['status']}")
        print(f"  GAP topics found: {result['gap_topics']}")
        print(f"  STALE topics found: {result['stale_topics']}")
        print(f"  Remediations triggered: {result['remediations_triggered']}")
        if result["errors"]:
            print(f"  Errors: {result['errors']}")
        sys.exit(0 if result["status"] in ("ok", "partial", "skipped") else 1)


if __name__ == "__main__":
    main()
