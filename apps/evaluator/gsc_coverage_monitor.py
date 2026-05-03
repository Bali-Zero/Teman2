"""
GSC Coverage Monitor
=====================
Confronta le URL inviate via Indexing API con quelle effettivamente indicizzate in GSC.
Chiude il loop: "submitted ≠ indexed".

Usa la GSC URL Inspection API per campionare le URL inviate e capire quante
sono state effettivamente indicizzate da Google.

Usage:
    python apps/evaluator/gsc_coverage_monitor.py             # report completo
    python apps/evaluator/gsc_coverage_monitor.py --sample 20 # campiona 20 URL
    python apps/evaluator/gsc_coverage_monitor.py --days 3    # solo URL inviate negli ultimi N giorni
    python apps/evaluator/gsc_coverage_monitor.py --json      # output JSON machine-readable
"""

import argparse
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[CoverageMonitor] %(levelname)s: %(message)s")

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / ".secrets" / "google-credentials.json"
STATE_PATH = PROJECT_ROOT / "apps" / "evaluator" / "indexing_state.json"
COVERAGE_STATE_PATH = PROJECT_ROOT / "apps" / "evaluator" / "coverage_state.json"
KBLI_DATA_PATH = PROJECT_ROOT / "apps" / "mouth" / "data" / "KBLI_2025_FINAL_CLEAN.json"

SITE_URL = "https://balizero.com/"
SITE_BASE_URL = "https://balizero.com/kbli/"
GSC_PROPERTY = "https://balizero.com/"

# URL Inspection API quota: 2000 req/day, 600 req/min
INSPECTION_DELAY_SEC = 0.12  # ~8 req/sec, well under 600/min limit
DEFAULT_SAMPLE_SIZE = 50     # default URLs to inspect per run


# Index coverage verdicts from URL Inspection API
VERDICT_INDEXED = "PASS"           # URL is indexed
VERDICT_EXCLUDED = "EXCLUDED"      # URL excluded (canonical, noindex, etc.)
VERDICT_ERROR = "FAIL"             # URL has errors
VERDICT_NEUTRAL = "NEUTRAL"        # Submitted but not yet processed


def build_webmaster_service():
    """Client per GSC Search Console API (webmasters v3)."""
    creds = service_account.Credentials.from_service_account_file(
        str(CREDENTIALS_PATH),
        scopes=[
            "https://www.googleapis.com/auth/webmasters",
            "https://www.googleapis.com/auth/webmasters.readonly",
        ],
    )
    return build("webmasters", "v3", credentials=creds)


def build_search_console_service():
    """Client per URL Inspection API (searchconsole v1)."""
    creds = service_account.Credentials.from_service_account_file(
        str(CREDENTIALS_PATH),
        scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
    )
    return build("searchconsole", "v1", credentials=creds)


def load_indexing_state() -> dict[str, Any]:
    """Carica lo stato dell'Indexing API submitter."""
    if not STATE_PATH.exists():
        return {"submitted": [], "failed": [], "last_run": None}
    with open(STATE_PATH) as f:
        return json.load(f)


def load_coverage_state() -> dict[str, Any]:
    """Carica lo stato del coverage monitor (risultati precedenti)."""
    if not COVERAGE_STATE_PATH.exists():
        return {"results": {}, "last_check": None, "summary_history": []}
    with open(COVERAGE_STATE_PATH) as f:
        return json.load(f)


def save_coverage_state(state: dict[str, Any]) -> None:
    state["last_check"] = datetime.now().isoformat()
    with open(COVERAGE_STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def load_kbli_gold_codes() -> set[str]:
    """Carica i codici Gold per evidenziarli nel report."""
    if not KBLI_DATA_PATH.exists():
        return set()
    with open(KBLI_DATA_PATH) as f:
        data = json.load(f)
    return {item["kode_kbli_2025"] for item in data["data"] if item.get("intel_2026")}


def inspect_url(service, url: str) -> dict[str, Any]:
    """
    Chiama URL Inspection API per una singola URL.
    Ritorna dict con verdict, coverageState, robotsTxtState, indexingState.
    """
    try:
        result = (
            service.urlInspection()
            .index()
            .inspect(
                body={
                    "inspectionUrl": url,
                    "siteUrl": GSC_PROPERTY,
                }
            )
            .execute()
        )
        inspection = result.get("inspectionResult", {})
        index_status = inspection.get("indexStatusResult", {})

        return {
            "url": url,
            "verdict": index_status.get("verdict", "UNKNOWN"),
            "coverage_state": index_status.get("coverageState", ""),
            "robots_txt": index_status.get("robotsTxtState", ""),
            "indexing_state": index_status.get("indexingState", ""),
            "last_crawl": index_status.get("lastCrawlTime", ""),
            "page_fetch": index_status.get("pageFetchState", ""),
            "sitemap": index_status.get("sitemap", []),
            "referring_urls": index_status.get("referringUrls", []),
            "checked_at": datetime.now().isoformat(),
            "error": None,
        }
    except HttpError as e:
        return {
            "url": url,
            "verdict": "ERROR",
            "coverage_state": "",
            "error": f"HTTP_{e.resp.status}: {str(e)[:200]}",
            "checked_at": datetime.now().isoformat(),
        }
    except Exception as e:
        return {
            "url": url,
            "verdict": "ERROR",
            "coverage_state": "",
            "error": str(e)[:200],
            "checked_at": datetime.now().isoformat(),
        }


def select_sample(
    submitted: list[str],
    coverage_state: dict[str, Any],
    sample_size: int,
    days_filter: int | None,
    gold_codes: set[str],
) -> list[str]:
    """
    Seleziona URL da ispezionare con questa priorità:
    1. URL mai ispezionate prima (gold first)
    2. URL ispezionate >24h fa con verdict non PASS
    3. URL ispezionate >72h fa (refresh)
    """
    already_checked = coverage_state.get("results", {})
    now = datetime.now()

    never_checked_gold = []
    never_checked_std = []
    needs_recheck = []
    stale = []

    for code in submitted:
        url = f"{SITE_BASE_URL}{code}"

        # Days filter: skip if submitted too long ago
        # (we don't have submission timestamps per-code, so skip this for now)

        if url not in already_checked:
            if code in gold_codes:
                never_checked_gold.append(url)
            else:
                never_checked_std.append(url)
        else:
            prev = already_checked[url]
            checked_at = datetime.fromisoformat(prev["checked_at"])
            age_hours = (now - checked_at).total_seconds() / 3600

            if prev["verdict"] != "PASS" and age_hours > 24:
                needs_recheck.append(url)
            elif age_hours > 72:
                stale.append(url)

    # Build priority queue
    priority = never_checked_gold + never_checked_std + needs_recheck + stale
    return priority[:sample_size]


def print_report(
    results: list[dict[str, Any]],
    all_coverage: dict[str, Any],
    gold_codes: set[str],
    submitted_total: int,
    as_json: bool = False,
) -> None:
    """Stampa il report di copertura."""

    # Aggregate from full coverage state (not just this run)
    all_results = list(all_coverage.get("results", {}).values())
    total_checked = len(all_results)

    indexed = [r for r in all_results if r.get("verdict") == "PASS"]
    excluded = [r for r in all_results if r.get("verdict") == "EXCLUDED"]
    errors = [r for r in all_results if r.get("verdict") in ("FAIL", "ERROR")]
    neutral = [r for r in all_results if r.get("verdict") == "NEUTRAL"]
    unknown = [r for r in all_results if r.get("verdict") not in ("PASS", "EXCLUDED", "FAIL", "ERROR", "NEUTRAL")]

    indexed_rate = len(indexed) / total_checked * 100 if total_checked else 0

    if as_json:
        report = {
            "generated_at": datetime.now().isoformat(),
            "submitted_total": submitted_total,
            "checked_total": total_checked,
            "this_run": len(results),
            "indexed": len(indexed),
            "indexed_rate_pct": round(indexed_rate, 1),
            "excluded": len(excluded),
            "errors": len(errors),
            "neutral_pending": len(neutral),
            "unknown": len(unknown),
            "this_run_details": results,
            "not_indexed_urls": [r["url"] for r in all_results if r.get("verdict") != "PASS"],
        }
        print(json.dumps(report, indent=2))
        return

    print("\n" + "=" * 55)
    print("  GSC COVERAGE MONITOR — balizero.com/kbli/")
    print("=" * 55)
    print(f"  Submitted to Indexing API:  {submitted_total}")
    print(f"  Ever inspected via GSC:     {total_checked}")
    print(f"  ├─ ✅ INDEXED (PASS):       {len(indexed)} ({indexed_rate:.1f}%)")
    print(f"  ├─ ⏳ NEUTRAL (pending):    {len(neutral)}")
    print(f"  ├─ ⚠️  EXCLUDED:            {len(excluded)}")
    print(f"  ├─ ❌ ERRORS:              {len(errors)}")
    print(f"  └─ ❓ UNKNOWN:             {len(unknown)}")
    print(f"\n  This run: {len(results)} URL inspected")
    print("=" * 55)

    if results:
        print("\n  THIS RUN DETAILS:")
        for r in results:
            code = r["url"].split("/kbli/")[-1]
            gold_tag = "🥇" if code in gold_codes else "  "
            verdict = r.get("verdict", "?")
            coverage = r.get("coverage_state", "")
            last_crawl = r.get("last_crawl", "")[:10] if r.get("last_crawl") else "never"
            error = r.get("error", "")

            if verdict == "PASS":
                status = f"✅ INDEXED  (crawled: {last_crawl})"
            elif verdict == "NEUTRAL":
                status = f"⏳ PENDING  ({coverage})"
            elif verdict == "EXCLUDED":
                status = f"⚠️  EXCLUDED ({coverage})"
            elif verdict in ("FAIL", "ERROR"):
                status = f"❌ ERROR    ({error or coverage})"
            else:
                status = f"❓ {verdict} ({coverage})"

            print(f"  {gold_tag} {code}  {status}")

    # Alert if indexed rate is low
    if total_checked >= 10 and indexed_rate < 30:
        print(f"\n  🚨 ALERT: Solo {indexed_rate:.1f}% delle URL ispezionate risulta indicizzata.")
        print("     Possibili cause: sito lento, crawl budget esaurito, thin content.")

    if excluded:
        print(f"\n  ⚠️  EXCLUDED URLs (prime 5):")
        for r in excluded[:5]:
            print(f"     {r['url']} — {r.get('coverage_state', '')}")

    print()


def run(sample_size: int, days_filter: int | None, as_json: bool) -> None:
    """Esegue il coverage check."""
    indexing_state = load_indexing_state()
    submitted = indexing_state.get("submitted", [])

    if not submitted:
        logger.warning("Nessuna URL sottomessa trovata in indexing_state.json. Esegui prima kbli_indexing_submit.py.")
        return

    coverage_state = load_coverage_state()
    gold_codes = load_kbli_gold_codes()

    # Select URLs to inspect
    to_inspect = select_sample(submitted, coverage_state, sample_size, days_filter, gold_codes)

    if not to_inspect:
        logger.info("Nessuna URL nuova da ispezionare. Tutte già controllate di recente.")
        print_report([], coverage_state, gold_codes, len(submitted), as_json)
        return

    logger.info("Inspecing %d URLs via GSC URL Inspection API...", len(to_inspect))
    service = build_search_console_service()

    results = []
    for i, url in enumerate(to_inspect, 1):
        logger.info("%d/%d %s", i, len(to_inspect), url)
        result = inspect_url(service, url)
        results.append(result)

        # Save to coverage state
        coverage_state.setdefault("results", {})[url] = result

        # Save every 10 inspections
        if i % 10 == 0:
            save_coverage_state(coverage_state)

        time.sleep(INSPECTION_DELAY_SEC)

    # Save summary to history
    total_checked = len(coverage_state.get("results", {}))
    indexed_count = sum(1 for r in coverage_state["results"].values() if r.get("verdict") == "PASS")
    coverage_state.setdefault("summary_history", []).append({
        "date": datetime.now().isoformat(),
        "submitted": len(submitted),
        "checked": total_checked,
        "indexed": indexed_count,
        "indexed_rate_pct": round(indexed_count / total_checked * 100, 1) if total_checked else 0,
        "this_run": len(results),
    })
    # Keep only last 30 history entries
    coverage_state["summary_history"] = coverage_state["summary_history"][-30:]

    save_coverage_state(coverage_state)
    print_report(results, coverage_state, gold_codes, len(submitted), as_json)


def main() -> None:
    parser = argparse.ArgumentParser(description="GSC Coverage Monitor per KBLI balizero.com")
    parser.add_argument("--sample", type=int, default=DEFAULT_SAMPLE_SIZE,
                        help=f"Numero di URL da ispezionare (default: {DEFAULT_SAMPLE_SIZE})")
    parser.add_argument("--days", type=int, default=None,
                        help="Filtra solo URL inviate negli ultimi N giorni")
    parser.add_argument("--json", action="store_true",
                        help="Output in formato JSON machine-readable")
    args = parser.parse_args()

    run(sample_size=args.sample, days_filter=args.days, as_json=args.json)


if __name__ == "__main__":
    main()
