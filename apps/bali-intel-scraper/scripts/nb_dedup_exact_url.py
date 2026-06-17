#!/usr/bin/env python3
"""Deterministic exact-URL dedup for the 5 NB-INTEL notebooks.

No LLM. Two sources are duplicates iff their canonical URL is identical after
normalization:
  L1 — lowercase scheme+host, drop fragment, strip trailing slash.
  L4 — drop only tracking query params (utm_*, fbclid, gclid, ...); SIGNIFICANT
       query params (e.g. ?page=2, ?id=...) are KEPT so distinct pages stay distinct.
The OLDEST source (first in listing order) is kept; the rest are deleted via
`nlm source delete <ids> --confirm`.

Title-based dedup (L2/L3) is deliberately NOT done here: empirically the scraper
captures anti-bot placeholder titles ("just a moment", "security checkpoint",
site name) on DISTINCT articles, so identical titles are false positives. Title
and fuzzy dedup are left to the LLM Mode C propose-only pass.

Challenge-sweep mode (--challenge-sweep): the ONE narrow exception to "no title
dedup". Anti-bot placeholder pages ("Just a moment...", "Vercel Security
Checkpoint") are zero-content garbage that never get a URL-dup partner, so the
LLM proposes their deletion every day but is forbidden from applying it — they
pile up until a notebook hits NotebookLM's hard 500-source ceiling and silently
drops new sources. This mode deletes ONLY those exact-title placeholders, ONLY in
notebooks at/near the ceiling (--near-cap). STRICT exact allowlist, never fuzzy/
substring, so a real article whose title merely contains "moment"/"security" is
untouched. Same per-run cap / --apply gate / audit log as the dedup path.

Safety:
  - Only canonical-URL matches (L1+L4). NEVER title/Levenshtein/fuzzy.
  - Per-run delete cap (default 20): abort the whole run if exceeded — a large
    batch signals a matching bug, not real dedup.
  - --apply gates real deletion; default is dry-run.
  - Every deletion is appended to ~/logs/nb-dedup-deleted.jsonl for audit.

Exit codes: 0 ok (dry-run or applied), 2 cap exceeded (abort), 3 nlm error.
"""
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("nb-dedup")

NLM_CLI = str(Path.home() / ".local" / "bin" / "nlm")
AUDIT_LOG = Path.home() / "logs" / "nb-dedup-deleted.jsonl"
DELETE_CAP_PER_RUN = 20
DELETE_CHUNK = 10  # nlm source delete fails on very large argv; chunk the bulk delete
NLM_TIMEOUT = 90

# L4: query params that never change page content — safe to strip before comparison.
TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "gbraid", "wbraid", "msclkid", "mc_cid", "mc_eid",
    "ref", "ref_src", "igshid", "_hsenc", "_hsmi", "yclid", "dclid",
})

# Anti-bot challenge-page placeholder titles (zero real content) the scraper
# captures when a site's WAF blocks it. STRICT exact-match allowlist on the
# NORMALIZED title (see _norm_title) — NEVER substring/fuzzy, so a real article
# titled "A moment of reckoning" or "Vercel raises Series D" is never matched.
# Only used by --challenge-sweep, and only on notebooks at/near the 500 ceiling.
CHALLENGE_TITLES = frozenset({
    "just a moment",                       # Cloudflare interstitial
    "attention required! | cloudflare",    # Cloudflare block page
    "vercel security checkpoint",          # Vercel WAF interstitial
})

# NB-INTEL live UUIDs (post 2026-05-18 switch). Source of truth: `nlm list notebooks`.
NB_INTEL: dict[str, str] = {
    "immigration": "1ed02e54-542f-426a-94f8-53c5ffde4b7d",
    "tax": "7fb12c9c-4e12-4a8d-9bd1-c5b857bf310f",
    "press": "9d262101-abeb-4e15-af9c-c38e028c62fe",
    "regulation": "a17f134e-b9ab-42d9-bfc2-5bbc45165c76",
    "ai_research": "dc5d01cd-e99f-4c8f-aae4-75060b43d0de",
}


def canonical_url(raw: str) -> str:
    """Normalize a URL for exact-dup comparison.

    L1: lowercase scheme+host, drop fragment, strip trailing slash.
    L4: drop tracking query params only; keep significant ones (sorted for
        order-independence) so ?page=2 stays distinct from ?page=3.
    """
    try:
        s = urlsplit(raw.strip())
    except ValueError:
        return raw.strip().lower()
    scheme = (s.scheme or "https").lower()
    netloc = s.netloc.lower()
    path = s.path.rstrip("/") or "/"
    kept_query = sorted(
        (k, v) for k, v in parse_qsl(s.query, keep_blank_values=True)
        if k.lower() not in TRACKING_PARAMS
    )
    query = urlencode(kept_query)
    return urlunsplit((scheme, netloc, path, query, ""))


def list_sources(notebook_id: str) -> list[dict]:
    """Return [{id, title, type, url}, ...] for a notebook, or raise on error."""
    result = subprocess.run(
        [NLM_CLI, "source", "list", notebook_id, "--json"],
        capture_output=True,
        text=True,
        timeout=NLM_TIMEOUT,
    )
    if result.returncode != 0:
        raise RuntimeError(f"nlm source list failed for {notebook_id}: {result.stderr.strip()}")
    return json.loads(result.stdout or "[]")


def find_duplicates(sources: list[dict]) -> list[tuple[str, list[str]]]:
    """Group by canonical URL. Return [(kept_id, [dup_ids_to_delete]), ...].

    Sources without a URL (uploaded files, pasted text) are skipped entirely —
    only web_page sources with a real URL participate.
    """
    by_url: dict[str, list[str]] = defaultdict(list)
    for src in sources:
        url = src.get("url")
        sid = src.get("id")
        if not url or not sid:
            continue
        by_url[canonical_url(url)].append(sid)
    out: list[tuple[str, list[str]]] = []
    for ids in by_url.values():
        if len(ids) > 1:
            out.append((ids[0], ids[1:]))  # keep first (oldest), delete the rest
    return out


def _norm_title(title: str) -> str:
    """Normalize a title for exact challenge-page comparison: lowercase, fold the
    unicode ellipsis to '...', strip trailing dots/whitespace. So 'Just a moment...',
    'Just a moment…' and '  JUST A MOMENT ' all collapse to 'just a moment'."""
    return title.strip().lower().replace("…", "...").rstrip(". ")


def find_challenge_pages(sources: list[dict]) -> list[str]:
    """Return ids of sources whose NORMALIZED title is an exact challenge-page
    placeholder (CHALLENGE_TITLES). Exact-match only — a title that merely contains
    one of these words does not match."""
    out: list[str] = []
    for src in sources:
        sid = src.get("id")
        if sid and _norm_title(src.get("title") or "") in CHALLENGE_TITLES:
            out.append(sid)
    return out


def select_challenge_deletions(
    sources_by_nb: dict[str, list[dict]], near_cap: int
) -> list[tuple[str, str]]:
    """Plan challenge-page deletions, but ONLY for notebooks at/near the hard
    500-source ceiling (len(sources) >= near_cap). Below the ceiling there is no
    space pressure, so challenge pages stay as LLM propose-only items.
    Returns [(nb_key, source_id), ...] in notebook order."""
    plan: list[tuple[str, str]] = []
    for key, sources in sources_by_nb.items():
        if len(sources) < near_cap:
            continue
        for sid in find_challenge_pages(sources):
            plan.append((key, sid))
    return plan


def delete_sources(source_ids: list[str]):
    """Delete sources via nlm in chunks (large argv fails).

    Yields each successfully-deleted id so the caller can audit incrementally
    even if a later chunk raises.
    """
    for i in range(0, len(source_ids), DELETE_CHUNK):
        chunk = source_ids[i : i + DELETE_CHUNK]
        result = subprocess.run(
            [NLM_CLI, "source", "delete", *chunk, "--confirm"],
            capture_output=True,
            text=True,
            timeout=NLM_TIMEOUT,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"nlm source delete failed on chunk {i // DELETE_CHUNK}: {result.stderr.strip()}"
            )
        yield from chunk


def audit(entry: dict) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_LOG.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def run_challenge_sweep(apply: bool, cap: int, near_cap: int) -> int:
    """Delete anti-bot challenge-page placeholders, but ONLY in NB-INTEL notebooks
    at/near the 500-source ceiling. Mirrors main()'s safety: cap-abort, --apply gate,
    per-deletion audit. Exit codes match main() (0 ok, 2 cap exceeded, 3 nlm error)."""
    sources_by_nb: dict[str, list[dict]] = {}
    for key, nb_uuid in NB_INTEL.items():
        try:
            sources_by_nb[key] = list_sources(nb_uuid)
        except (RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            logger.error("skip %s (%s): %s", key, nb_uuid, e)

    plan = select_challenge_deletions(sources_by_nb, near_cap)
    total = len(plan)
    if total == 0:
        logger.info(
            "challenge-sweep: no challenge pages in near-cap NB-INTEL (near_cap=%d)", near_cap
        )
        print(json.dumps({"challenge_deleted": 0, "planned": 0, "applied": apply}))
        return 0

    if total > cap:
        logger.error("ABORT challenge-sweep: %d planned exceed cap %d", total, cap)
        print(json.dumps({"challenge_deleted": 0, "planned": total, "aborted_cap": cap}))
        return 2

    if not apply:
        for key, sid in plan:
            logger.info("[dry-run] challenge-sweep %s: would delete %s", key, sid)
        print(json.dumps({"challenge_deleted": 0, "planned": total, "applied": False}))
        return 0

    deleted = 0
    ts = datetime.now(timezone.utc).isoformat()
    by_nb: dict[str, list[str]] = defaultdict(list)
    for key, sid in plan:
        by_nb[key].append(sid)
    for key, ids in by_nb.items():
        nb_deleted = 0
        try:
            for sid in delete_sources(ids):
                audit({"ts": ts, "nb": key, "deleted_id": sid, "reason": "challenge_page_at_cap"})
                deleted += 1
                nb_deleted += 1
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            logger.error("challenge-sweep delete failed for %s after %d: %s", key, nb_deleted, e)
            print(json.dumps({"challenge_deleted": deleted, "planned": total, "applied": True, "error": str(e)}))
            return 3
        logger.info("%s: deleted %d challenge pages (at cap)", key, nb_deleted)

    print(json.dumps({"challenge_deleted": deleted, "planned": total, "applied": True}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Exact-URL dedup for NB-INTEL notebooks.")
    parser.add_argument("--apply", action="store_true", help="Actually delete (default: dry-run).")
    parser.add_argument("--cap", type=int, default=DELETE_CAP_PER_RUN, help="Abort if planned deletes exceed this.")
    parser.add_argument(
        "--challenge-sweep",
        action="store_true",
        help="Instead of URL-dedup: delete exact-title anti-bot challenge pages, "
        "but only in notebooks at/near the 500 ceiling (--near-cap).",
    )
    parser.add_argument(
        "--near-cap",
        type=int,
        default=480,
        help="Challenge-sweep only runs on a notebook with >= this many sources (default 480).",
    )
    args = parser.parse_args()

    if args.challenge_sweep:
        return run_challenge_sweep(apply=args.apply, cap=args.cap, near_cap=args.near_cap)

    plan: list[tuple[str, str, str]] = []  # (legacy_key, kept_id, dup_id)
    for key, nb_uuid in NB_INTEL.items():
        try:
            sources = list_sources(nb_uuid)
        except (RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            logger.error("skip %s (%s): %s", key, nb_uuid, e)
            continue
        for kept, dups in find_duplicates(sources):
            for dup in dups:
                plan.append((key, kept, dup))

    total = len(plan)
    if total == 0:
        logger.info("no exact-URL duplicates found across %d NB-INTEL", len(NB_INTEL))
        print(json.dumps({"deleted": 0, "planned": 0, "applied": args.apply}))
        return 0

    if total > args.cap:
        logger.error("ABORT: %d planned deletes exceed cap %d — possible matching bug", total, args.cap)
        print(json.dumps({"deleted": 0, "planned": total, "aborted_cap": args.cap}))
        return 2

    if not args.apply:
        for key, kept, dup in plan:
            logger.info("[dry-run] %s: would delete %s (dup of %s)", key, dup, kept)
        print(json.dumps({"deleted": 0, "planned": total, "applied": False}))
        return 0

    deleted = 0
    ts = datetime.now(timezone.utc).isoformat()
    by_nb: dict[str, list[str]] = defaultdict(list)
    kept_for: dict[str, str] = {}
    for key, kept, dup in plan:
        by_nb[key].append(dup)
        kept_for[dup] = kept
    for key, dup_ids in by_nb.items():
        nb_deleted = 0
        try:
            for dup in delete_sources(dup_ids):
                audit({"ts": ts, "nb": key, "deleted_id": dup, "kept_id": kept_for[dup]})
                deleted += 1
                nb_deleted += 1
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            logger.error("delete batch failed for %s after %d deleted: %s", key, nb_deleted, e)
            print(json.dumps({"deleted": deleted, "planned": total, "applied": True, "error": str(e)}))
            return 3
        logger.info("%s: deleted %d exact-URL duplicates", key, nb_deleted)

    print(json.dumps({"deleted": deleted, "planned": total, "applied": True}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
