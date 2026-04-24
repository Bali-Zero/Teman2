#!/usr/bin/env python3
"""Interactive first-time login for a Playwright persistent profile.

Usage:
    python3 scripts/playwright/playwright_login.py <site>

Supported sites: canva, gemini, flow, chatgpt.

Opens a headed browser, auto-fills email + password from
~/.nuzantara/playwright-credentials.env when available, and waits for you
to complete 2FA. Press Enter in terminal to save profile + close.

Cookies/session persist in ~/.nuzantara/playwright-profiles/<site>.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

CREDS_FILE = Path.home() / ".nuzantara" / "playwright-credentials.env"

SITES: dict[str, dict] = {
    "canva": {
        "url": "https://www.canva.com/login",
        "email_env": "CANVA_EMAIL",
        "password_env": "CANVA_PASSWORD",
        "login_via": "google_oauth",  # click "Continue with Google"
    },
    "gemini": {
        "url": "https://gemini.google.com/app",
        "email_env": "GEMINI_EMAIL",
        "password_env": "GEMINI_PASSWORD",
        "login_via": "google_direct",
    },
    "flow": {
        "url": "https://labs.google/fx/tools/flow",
        "email_env": "FLOW_EMAIL",
        "password_env": "FLOW_PASSWORD",
        "login_via": "google_direct",
    },
    "chatgpt": {
        "url": "https://chat.openai.com/",
        "email_env": "CHATGPT_EMAIL",
        "password_env": "CHATGPT_PASSWORD",
        "login_via": "openai_direct",
    },
}


def load_creds() -> dict[str, str]:
    if not CREDS_FILE.exists():
        print(f"[login] No creds file at {CREDS_FILE} — manual login only.")
        return {}
    creds = {}
    for line in CREDS_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        creds[k.strip()] = v.strip()
    return creds


def _fill_google_oauth(page, email: str, password: str) -> None:
    """Fill Google OAuth screens. Waits for 2FA manually."""
    # Email step
    try:
        page.wait_for_selector("input[type='email']", timeout=15000)
        page.fill("input[type='email']", email)
        page.click("button:has-text('Next'), button:has-text('Avanti'), #identifierNext")
    except PWTimeout:
        print("[login] Email step not detected — you may already be partially signed in. Continue manually.")
        return

    # Password step
    try:
        page.wait_for_selector("input[type='password']", timeout=15000)
        page.fill("input[type='password']", password)
        page.click("button:has-text('Next'), button:has-text('Avanti'), #passwordNext")
    except PWTimeout:
        print("[login] Password step not detected — possibly a passkey / passwordless prompt. Handle manually.")
        return

    print("[login] Credentials submitted. If 2FA is required, complete it on your phone now.")


def login(site: str) -> None:
    if site not in SITES:
        raise SystemExit(f"Unknown site {site!r}. Known: {', '.join(SITES)}")
    conf = SITES[site]
    creds = load_creds()
    email = creds.get(conf["email_env"], "")
    password = creds.get(conf["password_env"], "")

    profile_dir = Path.home() / ".nuzantara" / "playwright-profiles" / site
    profile_dir.mkdir(parents=True, exist_ok=True)

    print(f"[login] Site: {site}")
    print(f"[login] URL:  {conf['url']}")
    print(f"[login] Profile: {profile_dir}")
    if email:
        print(f"[login] Email: {email} (auto-fill enabled)")
    else:
        print("[login] No email in creds file — manual login only")

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            viewport={"width": 1440, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(conf["url"])

        # Best-effort auto-fill
        if email and password:
            if conf["login_via"] == "google_oauth":
                # Canva — click "Continue with Google" first
                try:
                    page.wait_for_selector(
                        "button:has-text('Continue with Google'), button:has-text('Continua con Google'), a:has-text('Continue with Google')",
                        timeout=10000,
                    )
                    page.click(
                        "button:has-text('Continue with Google'), button:has-text('Continua con Google'), a:has-text('Continue with Google')"
                    )
                    page.wait_for_load_state("networkidle", timeout=10000)
                except PWTimeout:
                    print("[login] 'Continue with Google' button not found — may already be logged in, or UI changed.")
                _fill_google_oauth(page, email, password)
            elif conf["login_via"] == "google_direct":
                _fill_google_oauth(page, email, password)
            elif conf["login_via"] == "openai_direct":
                # OpenAI flow: click Log In → email → password
                try:
                    page.click("button:has-text('Log in')")
                    page.fill("input[name='username']", email)
                    page.click("button:has-text('Continue')")
                    page.fill("input[name='password']", password)
                    page.click("button[type='submit']")
                except Exception as e:
                    print(f"[login] OpenAI auto-fill failed: {e}. Continue manually.")

        print()
        print("[login] Complete any remaining steps (2FA, consent, captcha) in the browser window.")
        print("[login] When you see the app's home/dashboard, come back and press Enter to save + close.")
        try:
            input()
        except KeyboardInterrupt:
            print("\n[login] aborted — profile may be partial")
        ctx.close()
        print(f"[login] Done. Session saved to {profile_dir}")
        print(f"[login] Cron/scripts will reuse this profile automatically via launch_persistent_context.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    login(sys.argv[1])
