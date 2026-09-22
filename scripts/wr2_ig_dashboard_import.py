#!/usr/bin/env python3
"""WR2 IG dashboard importer — merges a manual Instagram Professional-dashboard
.xlsx export (Account / Caroselli / Orari sheets, e.g. the 90-day report) into
`engagement_metrics` of matching queue items.

Why this exists: the Graph API (see wr2_ig_metrics_scraper.py) does NOT expose
the per-post follower/non-follower view split, profile visits, follows, or the
follower-online hours grid. Those live ONLY in the manual dashboard export, so
this importer is the single writer that carries them into the queue, using
`dashboard_`-prefixed keys that NEVER collide with scraper keys — and the
scraper's refresh carries them over instead of replacing the dict wholesale.

Matching: dashboard `Link` holds the post shortcode (/p/<code>/); a queue item
matches when its `instagram_post_url` contains the same shortcode.

Usage:
  python3 wr2_ig_dashboard_import.py --xlsx report.xlsx --queue /path/to/queue.json [--dry-run] [--limit N] [--save-summary summary.json]
"""
import argparse
import json
import re
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import openpyxl
except ImportError:
    print("ERROR: openpyxl is required (pip install openpyxl>=3.1.5)", file=sys.stderr)
    sys.exit(2)

SHORTCODE_RE = re.compile(r"instagram\.com/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)")

POST_COLUMNS = {  # dashboard header -> engagement_metrics key
    "Views": "dashboard_views",
    "Viewers": "dashboard_viewers",
    "Interactions": "dashboard_interactions",
    "Accounts engaged": "dashboard_accounts_engaged",
    "Shares": "dashboard_shares",
    "Likes": "dashboard_likes",
    "Comments": "dashboard_comments",
    "Saves": "dashboard_saves",
    "% Views da follower": "dashboard_follower_share",
    "Views da Home": "dashboard_views_home",
    "Views da Profilo": "dashboard_views_profile",
    "Views da Altro": "dashboard_views_other",
    "Profile activity": "dashboard_profile_activity",
    "Profile visits": "dashboard_profile_visits",
    "Follows": "dashboard_follows",
    "Engagement rate (Interactions/Views)": "dashboard_engagement_rate",
    "Share rate (Shares/Views)": "dashboard_share_rate",
}


def shortcode_of(url: str) -> str | None:
    m = SHORTCODE_RE.search(url or "")
    return m.group(1) if m else None


def _num(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_dashboard(xlsx_path: Path) -> tuple[list[dict], dict]:
    """Return (posts, account_summary). Raises FileNotFoundError / ValueError."""
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    if "Caroselli" not in wb.sheetnames:
        raise ValueError(f"sheet 'Caroselli' missing (have: {wb.sheetnames})")
    ws = wb["Caroselli"]
    header_row = None
    headers: list[str] = []
    for row in ws.iter_rows(values_only=True):
        vals = [(str(c).strip() if c is not None else "") for c in row]
        if "Data" in vals and "Carosello" in vals:
            header_row = row
            headers = vals
            break
    if header_row is None:
        raise ValueError("header row with 'Data'/'Carosello' not found")
    idx = {h: i for i, h in enumerate(headers)}
    posts = []
    dropped_no_shortcode = 0
    for row in ws.iter_rows(min_row=ws.min_row, values_only=True):
        vals = list(row)
        if vals[idx["Data"]] is None and not vals[idx["Carosello"]]:
            continue
        if str(vals[idx["Data"]] or "") == "Data" and str(vals[idx["Carosello"]] or "") == "Carosello":
            continue  # the header row itself
        title = str(vals[idx["Carosello"]] or "").strip()
        if not title or title.upper() in ("TOTALE", "MEDIA"):
            continue
        if "estratti da in" in title.lower() or title.startswith("Note:"):
            continue
        link = str(vals[idx["Link"]] or "") if "Link" in idx else ""
        code = shortcode_of(link)
        if not code:
            dropped_no_shortcode += 1
            continue
        post: dict = {
            "shortcode": code,
            "date": str(vals[idx["Data"]])[:10],
            "title": title[:80],
        }
        for col, key in POST_COLUMNS.items():
            if col in idx:
                v = _num(vals[idx[col]])
                if v is not None:
                    post[key] = v
        posts.append(post)

    summary: dict = {"posts_parsed": len(posts)}
    if "Account" in wb.sheetnames:
        acc: dict = {}
        for row in wb["Account"].iter_rows(values_only=True):
            vals = [c for c in row if c is not None]
            if len(vals) == 2 and isinstance(vals[0], str):
                acc[vals[0].strip()] = vals[1]
        for k in ("Views", "Interactions", "Accounts engaged", "Profile visits",
                  "Total followers", "External link taps"):
            v = _num(acc.get(k))
            if v is not None:
                summary[f"account_{k.lower().replace(' ', '_')}"] = v
    if "Orari attivi follower" in wb.sheetnames:
        wo = wb["Orari attivi follower"]
        grid = list(wo.iter_rows(values_only=True))
        days = [str(c) for c in grid[2][1:8]] if len(grid) > 2 else []
        peak: dict = {}
        for row in grid[3:]:
            if not row or row[0] is None:
                continue
            label = str(row[0]).strip()
            if label.lower() == "picco":
                for d, v in zip(days, list(row)[1:8]):
                    peak[d] = str(v)
                break
        if peak:
            summary["best_hours"] = peak
    summary["dropped_no_shortcode"] = dropped_no_shortcode
    return posts, summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", required=True)
    ap.add_argument("--queue", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--save-summary", default="")
    args = ap.parse_args()

    xlsx = Path(args.xlsx)
    if not xlsx.exists():
        print(f"ERROR: xlsx not found: {xlsx}", file=sys.stderr)
        return 2
    qpath = Path(args.queue)
    pre_image = qpath.read_text()  # the backup must be the queue BEFORE this run
    queue = json.loads(pre_image)

    try:
        posts, summary = parse_dashboard(xlsx)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    by_code: dict[str, dict] = {}
    dup_codes = 0
    for p in posts:
        if p["shortcode"] in by_code:
            dup_codes += 1  # last row wins, but never silently
        by_code[p["shortcode"]] = p

    # index queue items by shortcode found in instagram_post_url
    index: dict[str, dict] = {}
    for item in queue:
        code = shortcode_of(item.get("instagram_post_url") or "")
        if code and code not in index:
            index[code] = item

    matched = [(by_code[c], index[c]) for c in by_code if c in index]
    if args.limit > 0:
        matched = matched[: args.limit]
    unmatched = [c for c in by_code if c not in index]
    now = datetime.now(timezone.utc).isoformat()

    for post, item in matched:
        m = dict(item.get("engagement_metrics") or {})
        for k, v in post.items():
            if k in ("shortcode", "date", "title"):
                continue
            m[k] = v
        m["dashboard_post_date"] = post["date"]
        m["dashboard_post_title"] = post["title"]
        m["dashboard_source"] = "dashboard_xlsx"
        m["dashboard_scraped_at"] = now
        if args.dry_run:
            print(f"  [dry] {post['shortcode']} {post['date']} {post['title'][:40]}")
        else:
            item["engagement_metrics"] = m
            print(f"  ok    {post['shortcode']} {post['date']} {post['title'][:40]}")

    print(f"posts={len(posts)} matched={len(matched)} unmatched_dashboard={len(unmatched)} "
          f"dropped_no_shortcode={summary.get('dropped_no_shortcode', 0)} "
          f"dup_dashboard_shortcodes={dup_codes}")
    if unmatched:
        print("  unmatched shortcodes: " + ", ".join(sorted(unmatched)[:10]))
    if summary.get("best_hours"):
        print("  best_hours: " + json.dumps(summary["best_hours"], ensure_ascii=False))
    if args.save_summary:
        Path(args.save_summary).write_text(json.dumps(summary, ensure_ascii=False, indent=2))
        print(f"  summary → {args.save_summary}")

    if matched and not args.dry_run:
        bak = qpath.with_suffix(qpath.suffix + f".bak-dashimport-{int(time.time())}")
        bak.write_text(pre_image)
        fd, tmp = tempfile.mkstemp(dir=str(qpath.parent), prefix=".queue-", suffix=".json")
        with open(fd, "w") as f:
            json.dump(queue, f, ensure_ascii=False, indent=2)
        Path(tmp).replace(qpath)
        print(f"WROTE {len(matched)} updates → {qpath} (backup {bak.name})")
    else:
        print("no writes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
