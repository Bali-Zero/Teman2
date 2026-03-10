"""
KBLI Indexing API Submitter
============================
Sottomette le 1,563 URL KBLI a Google Indexing API con:
- Priorità Gold (504 codici con intel_2026) → prima
- Batching 200 URL/day (limite Google per progetto)
- Persistenza stato (riprende da dove si è fermato)
- Dry-run mode per verifica

PREREQUISITO: Il service account deve essere verificato come Owner in GSC.
Aggiungilo su: https://search.google.com/search-console/users?resource_id=https://balizero.com/
→ Sezione "Ownership" (non solo "Full" user — serve Owner verification)

Usage:
    python kbli_indexing_submit.py              # batch del giorno (200 URL)
    python kbli_indexing_submit.py --dry-run    # mostra cosa farebbe
    python kbli_indexing_submit.py --status     # mostra stato avanzamento
    python kbli_indexing_submit.py --reset      # azzera stato (ricomincia)
    python kbli_indexing_submit.py --batch 50   # batch personalizzato
"""

import argparse
import json
import logging
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[Indexing] %(levelname)s: %(message)s")

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
KBLI_DATA_PATH = PROJECT_ROOT / "apps" / "mouth" / "data" / "KBLI_2025_FINAL_CLEAN.json"
CREDENTIALS_PATH = PROJECT_ROOT / ".secrets" / "google-credentials.json"
STATE_PATH = PROJECT_ROOT / "apps" / "evaluator" / "indexing_state.json"

SITE_BASE_URL = "https://balizero.com/kbli/"
DAILY_LIMIT = 200           # Google Indexing API limit per service account/day
BATCH_DELAY_SEC = 0.5       # delay between requests (avoid rate limit burst)


def load_kbli_codes() -> list[dict[str, Any]]:
    """Carica e ordina i codici KBLI: Gold prima, poi standard."""
    with open(KBLI_DATA_PATH) as f:
        data = json.load(f)

    gold = []
    standard = []
    for item in data["data"]:
        entry = {
            "code": item["kode_kbli_2025"],
            "title": item.get("judul", ""),
            "gold": bool(item.get("intel_2026")),
        }
        if entry["gold"]:
            gold.append(entry)
        else:
            standard.append(entry)

    logger.info("KBLI loaded: %d gold + %d standard = %d total", len(gold), len(standard), len(gold) + len(standard))
    return gold + standard  # Gold first


def load_state() -> dict[str, Any]:
    """Carica lo stato di avanzamento precedente."""
    if STATE_PATH.exists():
        with open(STATE_PATH) as f:
            return json.load(f)
    return {
        "submitted": [],
        "failed": [],
        "last_run": None,
        "total_submitted": 0,
    }


def save_state(state: dict[str, Any]) -> None:
    state["last_run"] = datetime.now().isoformat()
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def build_service():
    """
    Costruisce il client Google Indexing API.

    NOTA: Il service account deve essere Owner (non solo Full) in GSC.
    Per aggiungere ownership al service account:
    1. Vai su https://search.google.com/search-console/users?resource_id=https://balizero.com/
    2. Clicca i 3 puntini accanto al service account → "Change permissions" → Owner
    OPPURE aggiungi il service account come owner via DNS TXT record per sc-domain:balizero.com

    Stato attuale: service account è siteFullUser, non siteOwner → 403 su Indexing API
    Quando sarà Owner, questo script funzionerà senza modifiche.
    """
    creds = service_account.Credentials.from_service_account_file(
        str(CREDENTIALS_PATH),
        scopes=["https://www.googleapis.com/auth/indexing"],
    )
    return build("indexing", "v3", credentials=creds)


def submit_url(service, url: str, dry_run: bool = False) -> tuple[bool, str]:
    """
    Sottomette una singola URL all'Indexing API.
    Ritorna (success, message).
    """
    if dry_run:
        return True, "DRY RUN"

    try:
        result = service.urlNotifications().publish(
            body={"url": url, "type": "URL_UPDATED"}
        ).execute()
        notify_time = result.get("urlNotificationMetadata", {}).get("latestUpdate", {}).get("notifyTime", "")
        return True, notify_time
    except HttpError as e:
        if e.resp.status == 403:
            # Ownership not verified — stop immediately
            raise RuntimeError(
                f"403 Ownership not verified for {url}. "
                "Add service account as OWNER (not just user) in GSC:\n"
                "https://search.google.com/search-console/users?resource_id=https://balizero.com/"
            ) from e
        if e.resp.status == 429:
            return False, "RATE_LIMIT"
        return False, f"HTTP_{e.resp.status}: {str(e)}"
    except Exception as e:
        return False, str(e)


def print_status(state: dict[str, Any], all_codes: list[dict]) -> None:
    submitted_set = set(state["submitted"])
    failed_set = set(state["failed"])
    pending = [c for c in all_codes if c["code"] not in submitted_set and c["code"] not in failed_set]
    gold_pending = [c for c in pending if c["gold"]]
    std_pending = [c for c in pending if not c["gold"]]

    print("\n=== INDEXING STATE ===")
    print(f"Total KBLI URLs:     {len(all_codes)}")
    print(f"Submitted OK:        {len(state['submitted'])} ({len(state['submitted'])/len(all_codes)*100:.1f}%)")
    print(f"Failed:              {len(state['failed'])}")
    print(f"Pending:             {len(pending)} ({len(gold_pending)} gold, {len(std_pending)} standard)")
    print(f"Last run:            {state.get('last_run', 'never')}")
    if state["failed"]:
        print(f"Failed codes:        {state['failed'][:10]}{'...' if len(state['failed']) > 10 else ''}")
    days_remaining = len(pending) / DAILY_LIMIT
    print(f"Est. days remaining: {days_remaining:.1f} @ {DAILY_LIMIT} URL/day")
    print("=====================\n")


def run_batch(batch_size: int = DAILY_LIMIT, dry_run: bool = False) -> None:
    """Esegue un batch di sottomissioni."""
    all_codes = load_kbli_codes()
    state = load_state()

    submitted_set = set(state["submitted"])
    failed_set = set(state["failed"])

    # Filter pending (not yet submitted, not failed)
    pending = [c for c in all_codes if c["code"] not in submitted_set and c["code"] not in failed_set]

    if not pending:
        logger.info("All %d URLs already submitted!", len(all_codes))
        print_status(state, all_codes)
        return

    batch = pending[:batch_size]
    gold_in_batch = sum(1 for c in batch if c["gold"])
    logger.info(
        "Batch: %d URLs (%d gold, %d standard) | %d remaining total",
        len(batch), gold_in_batch, len(batch) - gold_in_batch, len(pending)
    )

    if dry_run:
        logger.info("DRY RUN — showing first 10 URLs that would be submitted:")
        for c in batch[:10]:
            tag = "[GOLD]" if c["gold"] else "      "
            print(f"  {tag} {SITE_BASE_URL}{c['code']}  ({c['title'][:40]})")
        if len(batch) > 10:
            print(f"  ... and {len(batch)-10} more")
        print_status(state, all_codes)
        return

    service = build_service()

    ok_count = 0
    fail_count = 0
    rate_limit_hits = 0

    for i, item in enumerate(batch, 1):
        url = f"{SITE_BASE_URL}{item['code']}"
        tag = "[GOLD]" if item["gold"] else "      "

        success, msg = submit_url(service, url, dry_run=False)

        if success:
            state["submitted"].append(item["code"])
            ok_count += 1
            logger.info("%d/%d %s %s → OK %s", i, len(batch), tag, url, msg)
        elif msg == "RATE_LIMIT":
            rate_limit_hits += 1
            logger.warning("%d/%d %s %s → RATE LIMIT (sleeping 60s)", i, len(batch), tag, url)
            time.sleep(60)
            # Retry once
            success2, msg2 = submit_url(service, url)
            if success2:
                state["submitted"].append(item["code"])
                ok_count += 1
                logger.info("  Retry OK: %s", msg2)
            else:
                state["failed"].append(item["code"])
                fail_count += 1
                logger.error("  Retry failed: %s", msg2)
        else:
            state["failed"].append(item["code"])
            fail_count += 1
            logger.error("%d/%d %s %s → FAILED: %s", i, len(batch), tag, url, msg)

        # Save state every 10 submissions
        if i % 10 == 0:
            save_state(state)

        time.sleep(BATCH_DELAY_SEC)

    state["total_submitted"] = len(state["submitted"])
    save_state(state)

    print(f"\n✅ Batch complete: {ok_count} OK, {fail_count} failed, {rate_limit_hits} rate limit hits")
    print_status(state, all_codes)


def main() -> None:
    parser = argparse.ArgumentParser(description="KBLI Google Indexing API Submitter")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be submitted, don't call API")
    parser.add_argument("--status", action="store_true", help="Show submission progress")
    parser.add_argument("--reset", action="store_true", help="Reset state and start over")
    parser.add_argument("--batch", type=int, default=DAILY_LIMIT, help=f"Batch size (default: {DAILY_LIMIT})")
    args = parser.parse_args()

    if args.reset:
        if STATE_PATH.exists():
            STATE_PATH.unlink()
        logger.info("State reset. Run again to start fresh.")
        return

    if args.status:
        all_codes = load_kbli_codes()
        state = load_state()
        print_status(state, all_codes)
        return

    logger.info("=== KBLI Indexing Submitter | %s | batch=%d | dry_run=%s ===",
                date.today(), args.batch, args.dry_run)
    run_batch(batch_size=args.batch, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
