#!/usr/bin/env python3
"""WR2 IG profile harvester — STRATO 4 of the IG-metrics feedback loop.

Auto-extracts the URLs of posts published BY HAND on @balizero0 (Zero's own
back-catalogue) so they don't have to be pasted one by one. Feeds them to
STRATO 3 `ingest_external_post`, which mints scraper-consumable `published`
items; the IG-metrics scraper then collects their engagement.

The @balizero0 account is login-walled and there is no logged-in scraping
session on the Pro, so this uses a PERSISTENT Playwright profile
(~/.chrome-cdp-profile/balizero0-ig — the SAME profile the existing
_ig-metrics-scraper.py uses, so a login here also unblocks that scraper). Two
commands:

    login    — open a headful browser, let Zero log in to Instagram ONCE; the
               session is saved into the persistent profile. Run by the operator.
    harvest  — reuse the saved profile, scroll @balizero0, collect every post
               shortcode, and (with --ingest) register them via STRATO 3.

Login detection is by polling (no stdin needed): the script watches the page
until the login form disappears, then saves and exits — so it can be launched
with `!` from the Claude prompt or from a terminal.

Law 2: these are PUBLIC Instagram posts of Bali Zero; only public post URLs are
read. No client PII. The harvest acts only on the account's own grid.

CLI:
    wr2_ig_profile_harvester.py login                  [--handle balizero0]
    wr2_ig_profile_harvester.py harvest --collect-only [--handle balizero0] [--max-scrolls N]
    wr2_ig_profile_harvester.py harvest --ingest       [--handle balizero0]
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import sys
from pathlib import Path
from typing import Optional

# ── Import STRATO 3 (sibling module in scripts/) ───────────────────────────
_THIS_DIR = Path(__file__).resolve().parent
_WRITER_PATH = _THIS_DIR / "wr2_queue_writer.py"
_spec = importlib.util.spec_from_file_location("wr2_queue_writer", _WRITER_PATH)
_qw = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _qw
_spec.loader.exec_module(_qw)

IG_CHROME_PROFILE = Path.home() / ".chrome-cdp-profile/balizero0-ig"
DEFAULT_HANDLE = "balizero0"
LOGIN_POLL_TIMEOUT_S = 300
LOGIN_POLL_INTERVAL_S = 3
SCROLL_SETTLE_MS = 1800
DEFAULT_MAX_SCROLLS = 60


# ── Pure helpers (no I/O, unit-tested) ─────────────────────────────────────


def normalize_post_urls(hrefs: list[str], handle: Optional[str] = None) -> list[str]:
    """From a list of hrefs scraped off the grid, return unique canonical IG
    post/reel permalinks, order-preserving.

    - keeps only /p/<code>/ and /reel/<code>/ (drops /tv/ stories, /explore/,
      profile links, etc.)
    - canonicalizes to https://www.instagram.com/p|reel/<code>/
    - dedups by shortcode (a post can appear multiple times in the DOM)
    """
    seen: set[str] = set()
    out: list[str] = []
    for href in hrefs:
        if not href:
            continue
        code = _qw.extract_ig_shortcode(href)
        if not code or code in seen:
            continue
        # determine kind from the path
        kind = "reel" if "/reel/" in href else "p"
        seen.add(code)
        out.append(f"https://www.instagram.com/{kind}/{code}/")
    return out


# ── Browser I/O ────────────────────────────────────────────────────────────


async def _is_logged_in(page) -> bool:
    """Best-effort: logged in when no username login field is present and we are
    not on an /accounts/login route."""
    try:
        if "/accounts/login" in page.url:
            return False
        has_login = await page.evaluate(
            "() => !!document.querySelector('input[name=\"username\"]')"
        )
        return not has_login
    except Exception:
        return False


async def do_login(handle: str) -> int:
    """Open a headful browser on Instagram and wait (polling) until Zero logs in.
    Saves the session into the persistent profile. Returns 0 on success."""
    from playwright.async_api import async_playwright

    IG_CHROME_PROFILE.parent.mkdir(parents=True, exist_ok=True)
    print(f"[harvester] opening Instagram for login — profile: {IG_CHROME_PROFILE}")
    print("[harvester] >>> LOG IN to @balizero0 in the window that opens. "
          "This script detects login automatically and saves the session.")
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=str(IG_CHROME_PROFILE), headless=False
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto("https://www.instagram.com/accounts/login/", wait_until="domcontentloaded")
        waited = 0
        while waited < LOGIN_POLL_TIMEOUT_S:
            if await _is_logged_in(page):
                print(f"[harvester] login detected after ~{waited}s — session saved. You can close the window.")
                await page.wait_for_timeout(2000)
                await ctx.close()
                return 0
            await page.wait_for_timeout(LOGIN_POLL_INTERVAL_S * 1000)
            waited += LOGIN_POLL_INTERVAL_S
        print(f"[harvester] timed out after {LOGIN_POLL_TIMEOUT_S}s without detecting login.", file=sys.stderr)
        await ctx.close()
        return 1


async def collect_post_urls(handle: str, max_scrolls: int) -> list[str]:
    """Reuse the saved profile, scroll the @handle grid, return unique post URLs."""
    from playwright.async_api import async_playwright

    if not IG_CHROME_PROFILE.exists():
        print(f"[harvester] profile missing at {IG_CHROME_PROFILE} — run `login` first.", file=sys.stderr)
        return []

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=str(IG_CHROME_PROFILE), headless=True
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto(f"https://www.instagram.com/{handle}/", wait_until="domcontentloaded")
        await page.wait_for_timeout(SCROLL_SETTLE_MS)

        if not await _is_logged_in(page):
            print("[harvester] not logged in (session expired?) — re-run `login`.", file=sys.stderr)
            await ctx.close()
            return []

        all_hrefs: list[str] = []
        stable_rounds = 0
        prev_count = 0
        for _ in range(max_scrolls):
            hrefs = await page.evaluate(
                "() => Array.from(document.querySelectorAll('a[href*=\"/p/\"], a[href*=\"/reel/\"]')).map(a => a.href)"
            )
            all_hrefs.extend(hrefs)
            unique = normalize_post_urls(all_hrefs, handle)
            if len(unique) == prev_count:
                stable_rounds += 1
                if stable_rounds >= 3:  # grid exhausted (no new posts after 3 scrolls)
                    break
            else:
                stable_rounds = 0
            prev_count = len(unique)
            await page.evaluate("() => window.scrollBy(0, document.body.scrollHeight)")
            await page.wait_for_timeout(SCROLL_SETTLE_MS)

        await ctx.close()
        return normalize_post_urls(all_hrefs, handle)


# ── Orchestration ──────────────────────────────────────────────────────────


def _resolve_queue_path() -> Path:
    import os
    env = os.environ.get("WR2_QUEUE_PATH")
    return Path(env) if env else _qw.DEFAULT_QUEUE_PATH


def _cmd_login(args: argparse.Namespace) -> int:
    return asyncio.run(do_login(args.handle))


def _cmd_harvest(args: argparse.Namespace) -> int:
    urls = asyncio.run(collect_post_urls(args.handle, args.max_scrolls))
    if not urls:
        print("[harvester] no post URLs collected.")
        return 1
    print(f"[harvester] collected {len(urls)} unique post URL(s) from @{args.handle}:")
    for u in urls:
        print(f"  {u}")
    if args.collect_only:
        return 0
    if args.ingest:
        queue_path = _resolve_queue_path()
        ingested = already = failed = 0
        for u in urls:
            res = _qw.ingest_external_post(queue_path, u)
            if res.status == "ingested":
                ingested += 1
            elif res.status == "already_present":
                already += 1
            else:
                failed += 1
                print(f"  ! {u} -> {res.status}: {res.detail}", file=sys.stderr)
        print(f"[harvester] ingest: {ingested} new, {already} already present, {failed} failed.")
        return 0 if failed == 0 else 1
    print("[harvester] (dry: pass --ingest to register, or --collect-only to suppress this hint)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="WR2 IG profile harvester (STRATO 4)")
    sub = p.add_subparsers(dest="cmd", required=True)

    lg = sub.add_parser("login", help="one-time interactive login (headful), saves the IG session")
    lg.add_argument("--handle", default=DEFAULT_HANDLE)
    lg.set_defaults(func=_cmd_login)

    hv = sub.add_parser("harvest", help="scroll the profile grid and collect post URLs")
    hv.add_argument("--handle", default=DEFAULT_HANDLE)
    hv.add_argument("--max-scrolls", type=int, default=DEFAULT_MAX_SCROLLS)
    g = hv.add_mutually_exclusive_group()
    g.add_argument("--collect-only", action="store_true", help="print URLs only, do not register")
    g.add_argument("--ingest", action="store_true", help="register collected URLs via STRATO 3 ingest-external")
    hv.set_defaults(func=_cmd_harvest)
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
