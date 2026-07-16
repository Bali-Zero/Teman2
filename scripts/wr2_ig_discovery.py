#!/usr/bin/env python3
"""WR2 IG discovery — find posts published BY HAND that never entered the queue.

The nightly `wr2_ig_metrics_scraper.py` only refreshes metrics for entries
already sitting in `human-review-queue.json`. Posts published directly on
Instagram @balizero0 (bypassing the WR2 pipeline, e.g. by Zero) never get a
queue entry, so the "published carousels" view goes silently blind for them
— discovered 2026-07 after ~a month of hand-published posts with zero
tracking (scar #2 "esiste != armato": the queue LOOKED complete).

The Playwright-based harvester (`wr2_ig_profile_harvester.py`) is login-walled
against Instagram's web UI and collected 0 URLs in practice. This script uses
the SAME Instagram Graph API token the metrics scraper already has (it can
LIST the account's own media deterministically, no browser/login needed).

For each fetched media item not already known to the queue (by IG shortcode)
and within `--max-age-days`:
  - if its caption fuzzy-matches (word-token Jaccard) a queue item still in
    flight (drafted/reviewed/applied_ready_for_damar/approved), this is
    PROBABLY that item published early/out-of-band — print a
    `MATCH-PENDING` line. This is a SIGNAL only: this script never marks an
    item published on a fuzzy match (mark-published is exact-ref-code only,
    see `wr2_queue_writer.py`). A human/operator session resolves it with
    `wr2_queue_writer.py mark-published <ref_code> <url>`.
  - otherwise it is a genuinely-external post: register it via STRATO 3
    `ingest_external_post` (same path the profile harvester uses), which
    mints a scraper-consumable `published` item.

Fail-visible (scar #2, W84 blind-scan guard): an account with a real posting
history returning 0 media from the API is broken auth, not "clean" — exit 2.

Token: read from the env var NAMED by --token-env (default
INSTAGRAM_ACCESS_TOKEN). The token itself is NEVER printed or logged; any
exception text is redacted before being written to stdout/stderr.

CLI:
    wr2_ig_discovery.py --token-env INSTAGRAM_ACCESS_TOKEN [--queue PATH]
                         [--dry-run] [--max-age-days 90]

Exit codes:
    0  clean run, nothing pending
    1  run OK but MATCH-PENDING item(s) need human disambiguation
    2  API/HTTP error, or 0 media returned (blind-scan guard)
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ── Import STRATO 3 (sibling module in scripts/) — same pattern as
# wr2_ig_profile_harvester.py: register in sys.modules BEFORE exec_module,
# python 3.14's dataclass machinery needs the module findable by name. ──────
_THIS_DIR = Path(__file__).resolve().parent
_WRITER_PATH = _THIS_DIR / "wr2_queue_writer.py"
_spec = importlib.util.spec_from_file_location("wr2_queue_writer", _WRITER_PATH)
_qw = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _qw
_spec.loader.exec_module(_qw)

GRAPH = "https://graph.instagram.com"
DEFAULT_MAX_AGE_DAYS = 90
DEFAULT_LIMIT = 50
MATCH_STATES = frozenset({"drafted", "reviewed", "applied_ready_for_damar", "approved"})
JACCARD_THRESHOLD = 0.4
MIN_WORD_LEN = 4  # "words >3 chars"

_WORD_RE = re.compile(r"[A-Za-z0-9']+")


# ── SSL / HTTP (mirrors wr2_ig_metrics_scraper.py) ──────────────────────────


def _ssl_ctx() -> ssl.SSLContext:
    """Robust CA resolution — the macOS framework Python often lacks system CAs
    (SSL: CERTIFICATE_VERIFY_FAILED, verified on M5). Try, in order: certifi's
    bundle, the OpenSSL system bundles curl uses, then the plain default."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass
    for ca in ("/etc/ssl/cert.pem",
               "/opt/homebrew/etc/openssl@3/cert.pem",
               "/opt/homebrew/etc/ca-certificates/cert.pem"):
        if os.path.exists(ca):
            try:
                return ssl.create_default_context(cafile=ca)
            except Exception:
                continue
    return ssl.create_default_context()


_SSL = _ssl_ctx()


def _get(url: str, timeout: int = 25) -> dict:
    with urllib.request.urlopen(url, timeout=timeout, context=_SSL) as r:
        return json.load(r)


def _redact(text: str, token: Optional[str]) -> str:
    """Strip the raw token out of any string before it is printed/logged."""
    if token and token in text:
        return text.replace(token, "***REDACTED***")
    return text


# ── Pure helpers (no I/O, unit-tested) ─────────────────────────────────────


def word_tokens(text: str) -> set[str]:
    """Lowercase word tokens of length > 3 chars — the unit the Jaccard match
    operates on. Deliberately crude (no stemming/stopwords): this is a
    signaler, not an auto-actuator, so false negatives are safe (they just
    fall through to a fresh external ingest, never a wrong auto-publish)."""
    if not text:
        return set()
    return {w.lower() for w in _WORD_RE.findall(text) if len(w) > MIN_WORD_LEN - 1}


def jaccard_similarity(a: set[str], b: set[str]) -> float:
    """|intersection| / |union|. 0.0 if both sets are empty (no signal, not a match)."""
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def caption_first_line(caption: Optional[str]) -> str:
    """First non-empty visual line of an IG caption (captions are usually
    hook-line + blank line + body)."""
    if not caption:
        return ""
    stripped = caption.strip()
    if not stripped:
        return ""
    return stripped.splitlines()[0].strip()


def build_known_shortcodes(queue_items: list[dict[str, Any]]) -> set[str]:
    """Every IG shortcode already present in the queue (via instagram_post_url).

    TOCTOU note (§E, team-lead diagnosis 2026-07-17): this is a ONE-TIME
    snapshot taken at the top of `main()` before the ingest loop below writes
    anything. A post that becomes known between this snapshot and this run's
    own `ingest_external_post` calls (e.g. a native WR2 entry published
    mid-run, or a second discovery run racing this one) can still produce a
    virtual `ig-<shortcode>` entry sharing a URL/shortcode with a native
    entry — exactly the live case that triggered this diagnosis (idx 61
    `bali-pma-rental-crackdown`, native + published, vs idx 71
    `ig-DaxDJuYFPi6`, discovery-ingested 07-14 while idx 61's URL was still
    null). This function does NOT close that race, and isn't meant to: the
    backstop is the WR2 Control app's own §E dedup
    (`WarRoom.swift::matchesAnyPhysicalInstagramURL`), which hides a virtual
    entry at GALLERY READ TIME whenever a non-virtual sibling shares its URL,
    independent of ingestion order or timing.
    """
    known: set[str] = set()
    for item in queue_items:
        url = item.get("instagram_post_url")
        if not url:
            continue
        code = _qw.extract_ig_shortcode(url)
        if code:
            known.add(code)
    return known


def find_media_id_backfills(
    media_list: list[dict[str, Any]],
    queue_items: list[dict[str, Any]],
) -> list[tuple[str, str, str]]:
    """Pair up (item_id, ig_media_id, shortcode) for queue items ALREADY known
    by shortcode but missing `ig_media_id` — the RECONCILIATION half of §C
    (`ingest_external_post`'s `ig_media_id` pass-through is the fresh-mint
    half; this closes the gap for posts that predate that field, notably
    WR2-NATIVE carousels published via the app's own gate, which records the
    permalink but never a Graph media id — e.g. `bali-pma-rental-crackdown`).

    Matches by SHORTCODE (not URL string equality — queue URLs may differ in
    query string/scheme/www; shortcode is the same load-bearing key
    `build_known_shortcodes()` already uses). Pure and read-only: callers
    (`main()`) drive the actual `backfill_media_id()` write + dry-run gating.

    The shortcode is returned alongside the pair (Codex red-team, 2026-07-17,
    finding F) so the caller can pass it to `backfill_media_id` as
    `expected_shortcode` — a compare-and-set guard taken under that call's OWN
    lock, re-verifying the entry hasn't moved to a different URL between THIS
    snapshot and the write acquiring the lock (TOCTOU race).
    """
    media_by_shortcode: dict[str, str] = {}
    for m in media_list:
        code = _qw.extract_ig_shortcode(m.get("permalink") or "")
        media_id = m.get("id")
        if code and media_id:
            media_by_shortcode[code] = str(media_id)

    pairs: list[tuple[str, str, str]] = []
    for item in queue_items:
        if item.get("ig_media_id"):
            continue  # already reconciled — nothing to do
        url = item.get("instagram_post_url")
        if not url:
            continue
        code = _qw.extract_ig_shortcode(url)
        if not code:
            continue
        media_id = media_by_shortcode.get(code)
        if not media_id:
            continue  # this run's fetch didn't happen to include that post
        item_id = _qw.item_id_of(item)
        if not item_id:
            continue
        pairs.append((item_id, media_id, code))
    return pairs


def parse_ig_timestamp(ts: Optional[str]) -> Optional[datetime]:
    """Parse a Graph API timestamp (ISO-ish, e.g. '2026-06-01T12:34:56+0000')
    into an aware datetime, or None if unparseable."""
    if not ts:
        return None
    s = ts.strip()
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def is_recent(ts: Optional[str], max_age_days: int, now: datetime) -> bool:
    """True if `ts` parses and is no older than max_age_days relative to `now`."""
    dt = parse_ig_timestamp(ts)
    if dt is None:
        return False
    age_days = (now - dt).total_seconds() / 86400.0
    return age_days <= max_age_days


def filter_new_media(
    media_list: list[dict[str, Any]],
    known_shortcodes: set[str],
    max_age_days: int,
    now: datetime,
) -> list[dict[str, Any]]:
    """Media entries whose shortcode is NOT in `known_shortcodes` and whose
    timestamp is within `max_age_days` of `now`. Order-preserving."""
    out: list[dict[str, Any]] = []
    for m in media_list:
        permalink = m.get("permalink") or ""
        code = _qw.extract_ig_shortcode(permalink)
        if not code or code in known_shortcodes:
            continue
        if not is_recent(m.get("timestamp"), max_age_days, now):
            continue
        out.append(m)
    return out


def find_fuzzy_match(
    caption_line: str,
    queue_items: list[dict[str, Any]],
    states: frozenset[str] = MATCH_STATES,
    threshold: float = JACCARD_THRESHOLD,
) -> Optional[dict[str, Any]]:
    """Best queue item (in an in-flight state) whose topic fuzzy-matches
    `caption_line` above `threshold`, else None. Ties keep the first (queue
    order) at the winning score."""
    cap_tokens = word_tokens(caption_line)
    if not cap_tokens:
        return None
    best: Optional[dict[str, Any]] = None
    best_score = 0.0
    for item in queue_items:
        if item.get("state") not in states:
            continue
        topic_tokens = word_tokens(_qw.topic_of(item))
        score = jaccard_similarity(cap_tokens, topic_tokens)
        if score >= threshold and score > best_score:
            best = item
            best_score = score
    return best


# ── Network I/O ──────────────────────────────────────────────────────────


def fetch_all_media(token: str, limit: int = DEFAULT_LIMIT) -> list[dict[str, Any]]:
    """Fetch the account's own media via Graph API, following ONE
    `paging.next` page max (so at most 2 pages / ~2*limit items).

    Raises RuntimeError on a hard failure fetching page 1. A page-2 fetch
    failure is best-effort (we already have page-1 data) and only warns.
    """
    url = (
        f"{GRAPH}/me/media?fields=id,caption,permalink,timestamp,media_type"
        f"&limit={limit}&access_token={token}"
    )
    try:
        first = _get(url)
    except urllib.error.HTTPError as e:
        body = _redact(e.read().decode("utf-8", "ignore")[:200], token)
        raise RuntimeError(f"IG API HTTP error {e.code}: {body}") from e
    except Exception as e:
        raise RuntimeError(f"IG API error: {_redact(str(e), token)}") from e

    media: list[dict[str, Any]] = list(first.get("data", []))
    next_url = (first.get("paging") or {}).get("next")
    if next_url:
        try:
            second = _get(next_url)
            media.extend(second.get("data", []))
        except Exception as e:
            print(f"[discovery] WARN: paging.next fetch failed: {_redact(str(e), token)}", file=sys.stderr)
    return media


# ── Orchestration ──────────────────────────────────────────────────────────


def _resolve_queue_path(arg: Optional[str]) -> Path:
    if arg:
        return Path(arg)
    env = os.environ.get("WR2_QUEUE_PATH")
    return Path(env) if env else _qw.DEFAULT_QUEUE_PATH


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="WR2 IG discovery — hand-published posts missing from the queue"
    )
    p.add_argument(
        "--token-env",
        default="INSTAGRAM_ACCESS_TOKEN",
        help="name of the env var holding the IG access token (default: INSTAGRAM_ACCESS_TOKEN). "
        "The token value itself is never printed or logged.",
    )
    p.add_argument("--queue", help="path to human-review-queue.json (default: env WR2_QUEUE_PATH or standard)")
    p.add_argument("--dry-run", action="store_true", help="do not mutate the queue; print what would happen")
    p.add_argument(
        "--max-age-days",
        type=int,
        default=DEFAULT_MAX_AGE_DAYS,
        help=f"only consider IG media published within this many days (default {DEFAULT_MAX_AGE_DAYS})",
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    token = os.environ.get(args.token_env)
    if not token:
        print(f"ERROR: env var {args.token_env} not set", file=sys.stderr)
        return 2

    queue_path = _resolve_queue_path(args.queue)

    try:
        media_list = fetch_all_media(token)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    fetched = len(media_list)
    if fetched == 0:
        # scar W84 blind-scan guard: an account with real posting history
        # returning 0 media is broken auth, never "clean".
        print(
            "ERROR: IG API returned 0 media — treating as broken auth, not a clean "
            "account (blind-scan guard, scar W84)",
            file=sys.stderr,
        )
        return 2

    try:
        queue_items = _qw.load_queue(queue_path)
    except FileNotFoundError:
        queue_items = []

    known = build_known_shortcodes(queue_items)
    now = datetime.now(timezone.utc)
    new_media = filter_new_media(media_list, known, args.max_age_days, now)

    ingested = 0
    match_pending = 0
    for m in new_media:
        permalink = m.get("permalink") or ""
        cap_line = caption_first_line(m.get("caption"))
        match = find_fuzzy_match(cap_line, queue_items)

        if match is not None:
            match_pending += 1
            iid = _qw.item_id_of(match)
            ref = _qw.compute_ref_code(iid) if iid else "UNKNOWN"
            topic = _qw.topic_of(match)
            print(f"MATCH-PENDING ref={ref} url={permalink} topic={topic}")
            continue

        shortcode = _qw.extract_ig_shortcode(permalink)
        topic = cap_line[:60] if cap_line else f"(external IG post {shortcode})"
        dt = parse_ig_timestamp(m.get("timestamp"))
        published_at = dt.isoformat() if dt else None
        media_id = m.get("id")  # real numeric Graph id — always carried through when we have it

        if args.dry_run:
            print(f"[dry-run] would ingest url={permalink} topic={topic!r} published_at={published_at} "
                  f"ig_media_id={media_id}")
            continue

        res = _qw.ingest_external_post(
            queue_path, permalink, topic=topic, published_at=published_at, ig_media_id=media_id,
        )
        if res.status == "ingested":
            ingested += 1
            print(f"INGESTED url={permalink} topic={topic!r}")
        elif res.status == "already_present":
            print(f"SKIP (already present) url={permalink}")
        else:
            print(f"WARN ingest failed url={permalink} status={res.status} detail={res.detail}", file=sys.stderr)

    # ── §C point 3 reconciliation: WR2-native carousels (published via the
    # app's own gate) never get an ig_media_id at publish time. Anything this
    # run's fetch can match by shortcode gets backfilled here, closing the
    # metrics gap for entries that predate `ig_media_id` (see
    # find_media_id_backfills docstring). Computed from the pre-ingest
    # `queue_items` snapshot — safe because backfill_media_id() re-reads the
    # live file under lock at write time; only already-known entries (which
    # exist in that snapshot) are ever candidates. ──────────────────────────
    backfill_pairs = find_media_id_backfills(media_list, queue_items)
    backfilled = 0
    for item_id, media_id, matched_shortcode in backfill_pairs:
        if args.dry_run:
            print(f"[dry-run] would backfill ig_media_id={media_id} onto item_id={item_id}")
            continue
        res = _qw.backfill_media_id(queue_path, item_id, media_id, expected_shortcode=matched_shortcode)
        if res.status == "backfilled":
            backfilled += 1
            print(f"BACKFILLED item_id={item_id} ig_media_id={media_id}")
        elif res.status == "already_backfilled":
            pass  # no-op, nothing new to report
        else:
            print(f"WARN backfill failed item_id={item_id} status={res.status} detail={res.detail}", file=sys.stderr)

    print(f"DISCOVERY: fetched={fetched} known={len(known)} ingested={ingested} "
          f"match_pending={match_pending} backfilled={backfilled}")

    if match_pending > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
