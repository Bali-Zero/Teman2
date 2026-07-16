#!/usr/bin/env python3
"""
WR2 IG metrics scraper — the "metratore automatico smart".

Repopulates `engagement_metrics` for PUBLISHED carousels in human-review-queue.json
from the Instagram Graph API. Smart: only fetches items that are missing metrics or
whose metrics are stale (older than --max-age-days), so it never re-hammers the whole
corpus every run. The wr2-ig-metrics-analyst already CONSUMES these metrics; nothing
produced them automatically until now (they required a manual Graph-API backfill).

Token: read from env INSTAGRAM_ACCESS_TOKEN (never logged). On the Pro the wrapper
sources it from Fly. PII boundary: IG posts are public; no client data touched.

Usage:
  INSTAGRAM_ACCESS_TOKEN=... python3 wr2_ig_metrics_scraper.py [--queue PATH]
      [--max-age-days 7] [--dry-run] [--limit N]
"""
import argparse
import json
import os
import ssl
import sys
import tempfile
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DEFAULT_QUEUE = Path.home() / "nuzantara/apps/war-room/output/queue/human-review-queue.json"
GRAPH = "https://graph.instagram.com"


def _ssl_ctx() -> ssl.SSLContext:
    """Robust CA resolution — the macOS framework Python often lacks system CAs
    (SSL: CERTIFICATE_VERIFY_FAILED, verified on M5). Try, in order: certifi's bundle,
    the OpenSSL system bundles curl uses, then the plain default."""
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
# metrics we want; insights edge gives reach/saved/shares/total_interactions,
# the node itself gives like_count/comments_count.
INSIGHT_METRICS = "reach,saved,shares,total_interactions"
NODE_FIELDS = "like_count,comments_count,media_type"


def _get(url: str, timeout: int = 25) -> dict:
    with urllib.request.urlopen(url, timeout=timeout, context=_SSL) as r:
        return json.load(r)


def fetch_metrics(media_id: str, token: str) -> Optional[dict]:
    """Return engagement dict for one media, or None on hard failure."""
    out: dict = {}
    # node fields (likes/comments)
    try:
        d = _get(f"{GRAPH}/{media_id}?fields={NODE_FIELDS}&access_token={token}")
        if d.get("like_count") is not None:
            out["likes"] = d["like_count"]
        if d.get("comments_count") is not None:
            out["comments"] = d["comments_count"]
    except urllib.error.HTTPError as e:
        # 190 = token dead; bubble up so the run can abort cleanly
        body = e.read().decode("utf-8", "ignore")[:200]
        if '"code":190' in body or e.code == 190:
            raise RuntimeError(f"IG token invalid (190): {body}")
        return None
    except Exception:
        return None
    # insights edge (reach/saved/shares)
    try:
        ins = _get(f"{GRAPH}/{media_id}/insights?metric={INSIGHT_METRICS}&access_token={token}")
        for row in ins.get("data", []):
            name = row.get("name")
            vals = row.get("values") or [{}]
            v = vals[0].get("value")
            if name and v is not None:
                out[name] = v
    except Exception:
        pass  # insights can be unavailable for older/boosted posts — keep node metrics
    if not out:
        return None
    out["source"] = "ig_metrics_scraper"
    out["scraped_at"] = datetime.now(timezone.utc).isoformat()
    return out


def is_stale(metrics: Optional[dict], max_age_days: int) -> bool:
    """True if metrics are missing or older than max_age_days."""
    if not metrics:
        return True
    ts = metrics.get("scraped_at")
    if not ts:
        return True  # backfilled without a timestamp → refresh once
    try:
        when = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return True
    age = (datetime.now(timezone.utc) - when).days
    return age >= max_age_days


def media_id_of(item: dict) -> Optional[str]:
    # backfill ids are "ig-<mediaid>"; otherwise derive from the permalink shortcode is not
    # enough (Graph needs the numeric media id) — rely on the ig-<id> convention.
    iid = item.get("id") or ""
    if iid.startswith("ig-"):
        return iid[3:]
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", default=str(DEFAULT_QUEUE))
    ap.add_argument("--max-age-days", type=int, default=7)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="cap fetches this run (0 = no cap)")
    args = ap.parse_args()

    token = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
    if not token:
        print("ERROR: INSTAGRAM_ACCESS_TOKEN not set", file=sys.stderr)
        return 2

    qpath = Path(args.queue)
    queue = json.loads(qpath.read_text())

    # smart selection: published items whose metrics are missing/stale + have a media id
    todo = []
    for item in queue:
        if not (item.get("instagram_post_url") and item.get("state") == "published"):
            continue
        if not media_id_of(item):
            continue
        if is_stale(item.get("engagement_metrics"), args.max_age_days):
            todo.append(item)
    if args.limit > 0:
        todo = todo[: args.limit]

    print(f"published={sum(1 for i in queue if i.get('state')=='published')} "
          f"to_refresh={len(todo)} (max_age={args.max_age_days}d)")

    updated = 0
    for item in todo:
        mid = media_id_of(item)
        m = fetch_metrics(mid, token)
        if m is None:
            print(f"  skip {item.get('topic_slug') or item['id']}: no metrics returned")
            continue
        if args.dry_run:
            print(f"  [dry] {item.get('topic_slug') or item['id']}: {m}")
        else:
            item["engagement_metrics"] = m
            updated += 1
            print(f"  ok   {item.get('topic_slug') or item['id']}: "
                  f"likes={m.get('likes')} reach={m.get('reach')} "
                  f"saved={m.get('saved')} shares={m.get('shares')}")
        time.sleep(0.3)  # be gentle on the API

    if updated and not args.dry_run:
        # atomic write + backup
        bak = qpath.with_suffix(qpath.suffix + f".bak-scraper-{int(time.time())}")
        bak.write_text(json.dumps(queue, ensure_ascii=False, indent=2))
        fd, tmp = tempfile.mkstemp(dir=str(qpath.parent), prefix=".queue-", suffix=".json")
        with os.fdopen(fd, "w") as f:
            json.dump(queue, f, ensure_ascii=False, indent=2)
        os.replace(tmp, qpath)
        print(f"WROTE {updated} updates → {qpath} (backup {bak.name})")
    else:
        print("no writes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
