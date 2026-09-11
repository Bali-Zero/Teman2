#!/usr/bin/env python3
"""imigrasi.go.id scoped mirror — crawl, snapshot, diff, alert.

Usage:
    run.py --tier daily              # 15 pages (count asserted in urls.py, not narrated here)
    run.py --tier weekly             # 114 per-visa-code pages
    run.py --tier all                # everything
    run.py --select parent,voa,bvk,calling,faq-evoa   # ad-hoc subset (dry-run scope)
    run.py --selftest                # no network — unit-check extract/diff/snapshot logic
    run.py --verify-codes            # cross-check urls.CODES against the repo's seed file

Data lives in a SEPARATE git repo (not this monorepo — avoids repo bloat from
daily snapshots): default `~/nuzantara-imigrasi-mirror`, override with
`--data-root` or `IMIGRASI_MIRROR_DATA_ROOT`. Each run writes
`snapshots/<date>/<slug>.txt` and commits — git history IS the version log.

NOT installed as a cron/LaunchAgent by this change (Zero mandate: code +
dry-run only, arming is a follow-up decision after the dry-run is reviewed).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from crawler import crawl
from diff_alert import compute_diff, content_hash, send_diff_alert, send_status_note
from urls import ALL_PAGES, Page, pages_for_select, pages_for_tier

DEFAULT_DATA_ROOT = os.environ.get("IMIGRASI_MIRROR_DATA_ROOT") or str(Path.home() / "nuzantara-imigrasi-mirror")

# Self-health heartbeat: written OUTSIDE the data git repo (so it never
# pollutes the "nothing_to_commit" clean signal) and alongside the launchd
# logs. The independent healthcheck.py reads it to tell whether the mirror is
# still running at all. Same default path on both sides — keep in sync.
DEFAULT_HEARTBEAT = os.environ.get("IMIGRASI_MIRROR_HEARTBEAT") or str(Path.home() / "logs" / "imigrasi-mirror-heartbeat.json")

# Overall wall-clock budget scales with how many pages a tier touches — a
# 9-page daily run and a 114-page weekly run should not share one constant
# (guardrail: bounded, but "bounded" must still fit the job).
OVERALL_TIMEOUT_BY_TIER = {"daily": 600.0, "weekly": 1800.0, "all": 2400.0}
DEFAULT_OVERALL_TIMEOUT = 900.0


# --------------------------------------------------------------------------- snapshot IO
def snapshot_dir(data_root: Path, date: str) -> Path:
    return data_root / "snapshots" / date


def find_previous_snapshot(data_root: Path, slug: str, before_date: str) -> tuple[str, Path] | None:
    """Most recent prior snapshot for `slug`, searched back through however
    many days it takes (a weekly-tier page's "previous" may be ~7 days old —
    searching only d-1 would treat every weekly run as a first capture)."""
    snapshots_root = data_root / "snapshots"
    if not snapshots_root.is_dir():
        return None
    dates = sorted(
        (d.name for d in snapshots_root.iterdir() if d.is_dir() and d.name < before_date),
        reverse=True,
    )
    for d in dates:
        candidate = snapshots_root / d / f"{slug}.txt"
        if candidate.is_file():
            return d, candidate
    return None


def git_commit(data_root: Path, message: str) -> str:
    """Commits everything new/changed under data_root. Returns a short status
    string; 'nothing_to_commit' is not an error (e.g. a page fetched identical
    to what's already on disk for today, on a re-run)."""
    subprocess.run(["git", "add", "-A"], cwd=data_root, check=True, capture_output=True)
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=data_root, check=True, capture_output=True, text=True
    )
    if not status.stdout.strip():
        return "nothing_to_commit"
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=data_root, check=True, capture_output=True)
    return "committed"


# --------------------------------------------------------------------------- main flow
async def run(args: argparse.Namespace) -> dict:
    if args.select:
        ids = [s.strip() for s in args.select.split(",") if s.strip()]
        pages = pages_for_select(ids)
        tier_label = f"select({len(pages)})"
    else:
        pages = pages_for_tier(args.tier)
        tier_label = args.tier

    overall_timeout = args.overall_timeout_s or OVERALL_TIMEOUT_BY_TIER.get(args.tier, DEFAULT_OVERALL_TIMEOUT)

    results, skipped = await crawl(
        pages,
        concurrency=args.concurrency,
        rate_limit_s=args.rate_limit_s,
        timeout_s=args.timeout_s,
        overall_timeout_s=overall_timeout,
    )

    date = args.date or time.strftime("%Y-%m-%d", time.localtime())
    data_root = Path(args.data_root).expanduser()
    out_dir = snapshot_dir(data_root, date)
    out_dir.mkdir(parents=True, exist_ok=True)

    captured: list[Page] = []
    failed: list[tuple[Page, str, int | None]] = []
    diffs: list[dict] = []
    total_bytes = 0

    for r in results:
        if not r.ok or r.text is None:
            failed.append((r.page, r.error or "unknown_error", r.status_code))
            continue

        out_path = out_dir / f"{r.page.slug}.txt"
        out_path.write_text(r.text, encoding="utf-8")
        total_bytes += len(r.text.encode("utf-8"))
        captured.append(r.page)

        prev = find_previous_snapshot(data_root, r.page.slug, date)
        if prev is None:
            continue  # first capture — nothing to diff against yet
        prev_date, prev_path = prev
        prev_text = prev_path.read_text(encoding="utf-8")
        if prev_text == r.text:
            continue  # unchanged

        excerpt, added, removed, truncated = compute_diff(prev_text, r.text)
        diffs.append(
            {
                "page": r.page,
                "prev_date": prev_date,
                "added": added,
                "removed": removed,
                "truncated": truncated,
                "excerpt": excerpt,
                "hash": content_hash(r.text),
            }
        )

    commit_status = "skipped_dry_write" if args.no_commit else git_commit(
        data_root, f"chore(snapshot): {date} tier={tier_label} {len(captured)} pages, {len(diffs)} diffs"
    )

    alert_results: list[tuple[str, str]] = []
    if not args.no_alert:
        for d in diffs:
            status = send_diff_alert(d["page"].label, d["page"].url, d["excerpt"], d["hash"])
            alert_results.append((d["page"].id, status))

    summary = {
        "date": date,
        "tier": tier_label,
        "pages_requested": len(pages),
        "captured": len(captured),
        "failed": [(p.id, err, code) for p, err, code in failed],
        "skipped_deadline": [p.id for p in skipped],
        "total_bytes": total_bytes,
        "diffs": [
            {"id": d["page"].id, "label": d["page"].label, "prev_date": d["prev_date"],
             "added": d["added"], "removed": d["removed"]}
            for d in diffs
        ],
        "alert_results": alert_results,
        "commit_status": commit_status,
        "data_root": str(data_root),
    }
    return summary


def write_heartbeat(summary: dict, path: str = DEFAULT_HEARTBEAT) -> None:
    """Record that a run happened, with its capture/failure counts, so the
    independent healthcheck can tell a live-but-stumbling mirror from a dead
    one. Written on EVERY completed run (including partial) — a total crash in
    run() writes nothing, which correctly reads as STALE later. A write failure
    here must never break the run (it's telemetry, not the job)."""
    try:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        hb = {
            "last_run_epoch": time.time(),
            "last_run_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime()),
            "tier": summary["tier"],
            "pages_requested": summary["pages_requested"],
            "captured": summary["captured"],
            "failed": len(summary["failed"]),
            "failed_ids": [pid for pid, _err, _code in summary["failed"]],
            "diffs": len(summary["diffs"]),
            "commit_status": summary["commit_status"],
        }
        p.write_text(json.dumps(hb, indent=2), encoding="utf-8")
    except Exception as exc:  # telemetry must never break the crawl
        print(f"  heartbeat write FAILED: {exc}", file=sys.stderr)


def print_summary(summary: dict) -> None:
    print(f"[imigrasi-mirror] date={summary['date']} tier={summary['tier']}")
    print(f"  requested={summary['pages_requested']} captured={summary['captured']} "
          f"failed={len(summary['failed'])} skipped_deadline={len(summary['skipped_deadline'])}")
    print(f"  total_bytes={summary['total_bytes']} diffs={len(summary['diffs'])} commit={summary['commit_status']}")
    for pid, err, code in summary["failed"]:
        print(f"  FAILED {pid}: {err} (http={code})")
    for pid in summary["skipped_deadline"]:
        print(f"  SKIPPED (deadline) {pid}")
    for d in summary["diffs"]:
        print(f"  DIFF {d['id']} vs {d['prev_date']}: +{d['added']}/-{d['removed']}")
    for pid, status in summary["alert_results"]:
        print(f"  ALERT {pid}: {status}")
    print(f"  data_root={summary['data_root']}")


def verify_codes() -> int:
    """Best-effort cross-check of urls.CODES against the seed file this
    catalog was derived from. Skips (exit 0, loud note) if the monorepo
    isn't reachable from here — this module must not hard-depend on it."""
    import re

    seed = Path(__file__).resolve().parent.parent.parent / (
        "apps/backend-rag/backend/migrations/scripts/seed_visa_types_complete_2026.py"
    )
    if not seed.is_file():
        print(f"[verify-codes] seed file not reachable at {seed} — skipping (not an error, this "
              f"module is designed to run standalone)")
        return 0
    text = seed.read_text(encoding="utf-8")
    live_codes = sorted(set(re.findall(r'"code":\s*"([^"]+)"', text)))
    from urls import CODES

    catalog_codes = sorted(set(CODES))
    if live_codes == catalog_codes:
        print(f"[verify-codes] OK — {len(live_codes)} codes match the seed file")
        return 0
    added = sorted(set(live_codes) - set(catalog_codes))
    removed = sorted(set(catalog_codes) - set(live_codes))
    print(f"[verify-codes] DRIFT — seed has {len(live_codes)} codes, catalog has {len(catalog_codes)}")
    if added:
        print(f"  in seed but not in urls.CODES: {added}")
    if removed:
        print(f"  in urls.CODES but not in seed: {removed}")
    return 1


def selftest() -> int:
    """No-network unit checks (guilt+innocence pairs, tg_notify convention)."""
    import tempfile

    from extract import extract_produk_hukum, extract_text

    failures: list[str] = []

    def check(name: str, cond: bool) -> None:
        print(("  ok  " if cond else "  FAIL") + f" {name}")
        if not cond:
            failures.append(name)

    # --- extract_text: strips boilerplate, keeps content -------------------
    html = """
    <html><head><script>var x=1;</script></head>
    <body>
      <nav>Home | About</nav>
      <main><h1>Daftar Negara VOA</h1><p>Australia</p><p>Japan</p></main>
      <footer>Copyright 2026</footer>
    </body></html>
    """
    text = extract_text(html)
    check("main content kept", "Australia" in text and "Japan" in text)
    check("script stripped (guilt)", "var x=1" not in text)
    check("nav/footer stripped when main selector wins", "About" not in text and "Copyright" not in text)

    # innocence: no recognizable main container -> falls back to body, but
    # nav/header/footer boilerplate is still stripped from the fallback.
    html_no_main = "<html><body><nav>Menu</nav><div>Real content here padded out to exceed the minimum threshold so the fallback body extraction path is exercised honestly rather than trivially, still real content.</div><footer>Copy</footer></body></html>"
    text2 = extract_text(html_no_main)
    check("fallback body keeps real content", "Real content here" in text2)
    check("fallback body strips nav (innocence of a bare-body world)", "Menu" not in text2)

    # --- extract_produk_hukum: kemenimipas Joomla legal-doc listing ---------
    # The listing table lives inside <form id="adminForm"> (which extract_text
    # strips) and each row carries a volatile "Dilihat: N" view counter (which
    # extract_text would false-diff on). extract_produk_hukum pulls ONLY the
    # title links, so it survives the form and drops the counter.
    ph_html = """
    <html><body>
      <form id="adminForm">
        <table class="category table table-bordered"><tbody>
          <tr class="cat-list-row0"><td class="list-title">
            <a href="/x/15">Permenimipas No 15 Tahun 2025 tentang Politeknik</a>
          </td><td class="list-hits">Dilihat: 2720</td></tr>
          <tr class="cat-list-row1"><td class="list-title">
            <a href="/x/10">Permenimipas No 10 Tahun 2025 tentang penambahan daftar negara bebas visa</a>
          </td><td class="list-hits">Dilihat: 2994</td></tr>
        </tbody></table>
      </form>
      <footer>KEMENTERIAN IMIGRASI DAN PEMASYARAKATAN — Jakarta Selatan</footer>
    </body></html>
    """
    ph = extract_produk_hukum(ph_html)
    check("produk-hukum captures BOTH regulation titles (guilt)",
          "Permenimipas No 15 Tahun 2025" in ph and "Permenimipas No 10 Tahun 2025" in ph)
    check("produk-hukum drops the volatile view counter (innocence — no false diff)",
          "Dilihat" not in ph and "2720" not in ph)
    check("produk-hukum drops the footer menu (innocence — watches the list, not chrome)",
          "KEMENTERIAN IMIGRASI" not in ph)
    # a page WITHOUT the category table -> "" (loud empty diff, never a crash):
    ph_empty = extract_produk_hukum("<html><body><div>no listing here</div></body></html>")
    check("produk-hukum on a table-less page -> empty (loud, not a crash)", ph_empty == "")
    # and generic extract_text is BLIND to this listing (proves why we need the
    # custom one): the <form> is stripped, so the titles never survive.
    check("generic extract_text is blind to the form-wrapped listing (why custom exists)",
          "Permenimipas No 15" not in extract_text(ph_html))

    # --- compute_diff --------------------------------------------------------
    old = "line1\nline2\nline3"
    new = "line1\nline2-changed\nline3\nline4"
    excerpt, added, removed, truncated = compute_diff(old, new)
    check("diff counts additions", added >= 2)  # line2-changed + line4
    check("diff counts removals", removed >= 1)  # line2
    check("diff not truncated for a small diff", not truncated)

    long_old = "\n".join(f"l{i}" for i in range(100))
    long_new = "\n".join(f"l{i}x" for i in range(100))
    _, _, _, truncated_big = compute_diff(long_old, long_new, max_lines=5)
    check("large diff IS truncated (never a silent cap — must say so)", truncated_big)

    # --- find_previous_snapshot ----------------------------------------------
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for d, content in [("2026-08-01", "old"), ("2026-08-05", "newer"), ("2026-08-08", "today")]:
            sd = root / "snapshots" / d
            sd.mkdir(parents=True)
            (sd / "voa-subjects.txt").write_text(content)
        prev = find_previous_snapshot(root, "voa-subjects", "2026-08-08")
        check("finds most recent PRIOR snapshot, skipping today", prev is not None and prev[0] == "2026-08-05")

        prev_gap = find_previous_snapshot(root, "voa-subjects", "2026-08-20")
        check("searches back further than d-1 (weekly-tier gap)", prev_gap is not None and prev_gap[0] == "2026-08-08")

        none_case = find_previous_snapshot(root, "never-seen-slug", "2026-08-08")
        check("no prior snapshot -> None (first capture, not a false diff)", none_case is None)

    print("SELFTEST", "PASS" if not failures else f"FAIL ({failures})")
    return 0 if not failures else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tier", choices=["daily", "weekly", "all"], default="daily")
    ap.add_argument("--select", default="", help="comma-separated page ids, overrides --tier")
    ap.add_argument("--data-root", default=DEFAULT_DATA_ROOT)
    ap.add_argument("--date", default="", help="override YYYY-MM-DD (default: today, local time)")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--rate-limit-s", type=float, default=2.0)
    ap.add_argument("--timeout-s", type=float, default=30.0)
    ap.add_argument("--overall-timeout-s", type=float, default=0.0, help="0 = tier-based default")
    ap.add_argument("--no-alert", action="store_true", help="skip Telegram sends (still diffs+commits)")
    ap.add_argument("--no-commit", action="store_true", help="skip git commit (still writes files)")
    ap.add_argument("--announce", default="", help="send ONE status note after the run, e.g. for a dry-run channel check")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--verify-codes", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if args.verify_codes:
        return verify_codes()

    summary = asyncio.run(run(args))
    print_summary(summary)
    write_heartbeat(summary)

    if args.announce:
        n_diffs = len(summary["diffs"])
        text = args.announce.format(
            captured=summary["captured"], diffs=n_diffs, failed=len(summary["failed"]), date=summary["date"]
        )
        status = send_status_note(text, dedup_key=f"imigrasi-mirror-announce:{summary['tier']}")
        print(f"  ANNOUNCE: {status}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
