"""
KBLI Indexing API Submitter
============================
Sottomette le 1,563 URL KBLI a Google Indexing API con:
- Priorità Gold (504 codici con intel_2026) → prima
- Multi-SA round-robin: 3 service accounts × 200 URL/day = 600 URL/day
- Persistenza stato (riprende da dove si è fermato)
- Dry-run mode per verifica

PREREQUISITI:
- SA-1 kbli-indexer@nuzantara.iam.gserviceaccount.com → .secrets/google-credentials.json
- SA-2 kbli-indexer-2@nuzantara.iam.gserviceaccount.com → .secrets/kbli-indexer-2.json
- SA-3 kbli-indexer-3@nuzantara.iam.gserviceaccount.com → .secrets/kbli-indexer-3.json
Tutti e 3 devono essere Owner in GSC (non solo Full user).

Usage:
    python kbli_indexing_submit.py              # batch completo (600 URL con 3 SA)
    python kbli_indexing_submit.py --dry-run    # mostra cosa farebbe
    python kbli_indexing_submit.py --status     # mostra stato avanzamento
    python kbli_indexing_submit.py --reset      # azzera stato (ricomincia)
    python kbli_indexing_submit.py --batch 50   # batch personalizzato
    python kbli_indexing_submit.py --sa 1       # usa solo SA-1 (default: tutti)
"""

import argparse
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[Indexing] %(levelname)s: %(message)s")

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
KBLI_DATA_PATH = PROJECT_ROOT / "apps" / "mouth" / "data" / "KBLI_2025_FINAL_CLEAN.json"
STATE_PATH = PROJECT_ROOT / "apps" / "evaluator" / "indexing_state.json"

# Multi-SA configuration — 200 URL/day each = 600/day total
SA_CREDENTIALS = [
    PROJECT_ROOT / ".secrets" / "google-credentials.json",   # SA-1 (original)
    PROJECT_ROOT / ".secrets" / "kbli-indexer-2.json",       # SA-2
    PROJECT_ROOT / ".secrets" / "kbli-indexer-3.json",       # SA-3
]
# Keep legacy single path for backwards compat
CREDENTIALS_PATH = SA_CREDENTIALS[0]

SITE_BASE_URL = "https://balizero.com/kbli/"
DAILY_LIMIT_PER_SA = 200    # Google Indexing API limit per service account/day
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


def build_service(creds_path: Path):
    """Costruisce il client Google Indexing API per un dato service account."""
    if not creds_path.exists():
        raise FileNotFoundError(f"Credentials not found: {creds_path}")
    creds = service_account.Credentials.from_service_account_file(
        str(creds_path),
        scopes=["https://www.googleapis.com/auth/indexing"],
    )
    return build("indexing", "v3", credentials=creds)


def get_active_services(sa_filter: int | None = None) -> list[tuple[int, Any]]:
    """
    Ritorna lista di (sa_index, service) per tutti i SA con credenziali disponibili.
    sa_filter: se specificato, usa solo quel SA (1-based).
    """
    services = []
    for i, creds_path in enumerate(SA_CREDENTIALS, start=1):
        if sa_filter is not None and i != sa_filter:
            continue
        if creds_path.exists():
            try:
                svc = build_service(creds_path)
                services.append((i, svc))
                logger.info("SA-%d loaded: %s", i, creds_path.name)
            except Exception as e:
                logger.warning("SA-%d failed to load: %s", i, e)
        else:
            logger.warning("SA-%d credentials not found: %s", i, creds_path)
    return services


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


def print_status(state: dict[str, Any], all_codes: list[dict], active_sa_count: int = 3) -> None:
    submitted_set = set(state["submitted"])
    failed_set = set(state["failed"])
    pending = [c for c in all_codes if c["code"] not in submitted_set and c["code"] not in failed_set]
    gold_pending = [c for c in pending if c["gold"]]
    std_pending = [c for c in pending if not c["gold"]]
    daily_cap = DAILY_LIMIT_PER_SA * active_sa_count

    print("\n=== INDEXING STATE ===")
    print(f"Total KBLI URLs:     {len(all_codes)}")
    print(f"Submitted OK:        {len(state['submitted'])} ({len(state['submitted'])/len(all_codes)*100:.1f}%)")
    print(f"Failed:              {len(state['failed'])}")
    print(f"Pending:             {len(pending)} ({len(gold_pending)} gold, {len(std_pending)} standard)")
    print(f"Last run:            {state.get('last_run', 'never')}")
    if state["failed"]:
        print(f"Failed codes:        {state['failed'][:10]}{'...' if len(state['failed']) > 10 else ''}")
    print(f"Active SAs:          {active_sa_count} × {DAILY_LIMIT_PER_SA} = {daily_cap} URL/day")
    days_remaining = len(pending) / daily_cap if daily_cap > 0 else float("inf")
    print(f"Est. days remaining: {days_remaining:.1f}")
    print("=====================\n")


def run_batch(batch_size: int | None = None, dry_run: bool = False, sa_filter: int | None = None) -> None:
    """
    Esegue un batch di sottomissioni usando tutti i SA disponibili in round-robin.
    Ogni SA invia fino a DAILY_LIMIT_PER_SA URL. Total = n_sa × DAILY_LIMIT_PER_SA.
    """
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

    # Load active service accounts
    if dry_run:
        services = [(i+1, None) for i in range(len(SA_CREDENTIALS))]
    else:
        services = get_active_services(sa_filter)
        if not services:
            logger.error("No active service accounts available!")
            return

    # Calculate total batch (default = all SAs × daily limit)
    n_sa = len(services)
    total_limit = batch_size if batch_size is not None else DAILY_LIMIT_PER_SA * n_sa
    batch = pending[:total_limit]

    gold_in_batch = sum(1 for c in batch if c["gold"])
    logger.info(
        "Batch: %d URLs (%d gold, %d standard) | %d remaining total | %d SA(s)",
        len(batch), gold_in_batch, len(batch) - gold_in_batch, len(pending), n_sa
    )

    if dry_run:
        logger.info("DRY RUN — showing first 10 URLs that would be submitted:")
        for c in batch[:10]:
            tag = "[GOLD]" if c["gold"] else "      "
            print(f"  {tag} {SITE_BASE_URL}{c['code']}  ({c['title'][:40]})")
        if len(batch) > 10:
            print(f"  ... and {len(batch)-10} more")
        print_status(state, all_codes, n_sa)
        return

    ok_count = 0
    fail_count = 0
    rate_limit_hits = 0

    # Round-robin: split batch across SAs, each gets its slice
    # SA-1 gets items 0,3,6,... SA-2 gets 1,4,7,... SA-3 gets 2,5,8,...
    # Each SA processes its own slice up to DAILY_LIMIT_PER_SA
    sa_batches: list[list] = [[] for _ in services]
    for idx, item in enumerate(batch):
        sa_idx = idx % n_sa
        if len(sa_batches[sa_idx]) < DAILY_LIMIT_PER_SA:
            sa_batches[sa_idx].append(item)

    for sa_pos, (sa_num, service) in enumerate(services):
        sa_batch = sa_batches[sa_pos]
        if not sa_batch:
            continue
        logger.info("--- SA-%d: %d URLs ---", sa_num, len(sa_batch))
        for i, item in enumerate(sa_batch, 1):
            url = f"{SITE_BASE_URL}{item['code']}"
            tag = "[GOLD]" if item["gold"] else "      "

            success, msg = submit_url(service, url, dry_run=False)

            if success:
                state["submitted"].append(item["code"])
                ok_count += 1
                logger.info("SA-%d %d/%d %s %s → OK", sa_num, i, len(sa_batch), tag, url)
            elif msg == "RATE_LIMIT":
                rate_limit_hits += 1
                logger.warning("SA-%d %d/%d %s %s → RATE LIMIT (sleeping 60s)", sa_num, i, len(sa_batch), tag, url)
                time.sleep(60)
                # Retry once
                success2, msg2 = submit_url(service, url)
                if success2:
                    state["submitted"].append(item["code"])
                    ok_count += 1
                    logger.info("  SA-%d Retry OK", sa_num)
                else:
                    state["failed"].append(item["code"])
                    fail_count += 1
                    logger.error("  SA-%d Retry failed: %s", sa_num, msg2)
            else:
                state["failed"].append(item["code"])
                fail_count += 1
                logger.error("SA-%d %d/%d %s %s → FAILED: %s", sa_num, i, len(sa_batch), tag, url, msg)

            # Save state every 10 submissions
            if i % 10 == 0:
                save_state(state)

            time.sleep(BATCH_DELAY_SEC)

    state["total_submitted"] = len(state["submitted"])
    save_state(state)

    print(f"\n✅ Batch complete: {ok_count} OK, {fail_count} failed, {rate_limit_hits} rate limit hits")
    print_status(state, all_codes, len(services))


def main() -> None:
    parser = argparse.ArgumentParser(description="KBLI Google Indexing API Submitter (multi-SA)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be submitted, don't call API")
    parser.add_argument("--status", action="store_true", help="Show submission progress")
    parser.add_argument("--reset", action="store_true", help="Reset state and start over")
    parser.add_argument("--batch", type=int, default=None, help=f"Total batch size (default: n_sa × {DAILY_LIMIT_PER_SA})")
    parser.add_argument("--sa", type=int, default=None, choices=[1, 2, 3], help="Use only this SA (1-3). Default: all")
    args = parser.parse_args()

    if args.reset:
        if STATE_PATH.exists():
            STATE_PATH.unlink()
        logger.info("State reset. Run again to start fresh.")
        return

    if args.status:
        all_codes = load_kbli_codes()
        state = load_state()
        n_sa = sum(1 for p in SA_CREDENTIALS if p.exists())
        print_status(state, all_codes, n_sa)
        return

    logger.info("=== KBLI Indexing Submitter | %s | SA=%s | dry_run=%s ===",
                datetime.now().strftime("%Y-%m-%d"), args.sa or "all", args.dry_run)
    run_batch(batch_size=args.batch, dry_run=args.dry_run, sa_filter=args.sa)


if __name__ == "__main__":
    main()
