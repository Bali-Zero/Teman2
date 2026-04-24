# Playwright Profiles — login persistence mechanics

## Directory layout

```
~/.nuzantara/playwright-profiles/
├── canva/        # persistent context for canva.com
├── gemini/       # persistent context for gemini.google.com
├── flow/         # persistent context for labs.google/fx/tools/flow
└── chatgpt/      # persistent context for chat.openai.com
```

Each dir is a full Chromium user-data-dir (cookies, localStorage, IndexedDB, cache). **Outside the git repo** — contains session secrets.

## Why persistent context (not storage_state)

- Google properties (Gemini, Flow, Workspace) aggressively detect cookie-only replay → force re-login or reCAPTCHA.
- Persistent context replays the full browser fingerprint → Google treats it like a returning user on the same machine.
- Canva tolerates `storage_state` but persistent is more resilient.

Rule: **always use `launch_persistent_context` for Google sites**, and for everything else unless you have a specific reason not to.

## First-time login (headed, auto-fill credentials, manual 2FA)

Login script: `scripts/playwright/playwright_login.py` — opens a headed browser, auto-fills email+password from `~/.nuzantara/playwright-credentials.env`, waits for you to complete 2FA/consent manually.

```bash
python3 scripts/playwright/playwright_login.py canva
```

### Credentials file

`~/.nuzantara/playwright-credentials.env` (chmod 600, outside repo):
```
CANVA_EMAIL=<email>
CANVA_PASSWORD=<password>
GEMINI_EMAIL=<email>
GEMINI_PASSWORD=<password>
FLOW_EMAIL=<email>
FLOW_PASSWORD=<password>
```

This file is **only read at login time**, not at cron runtime. Once `profile_dir` contains a valid session, passwords are irrelevant until the session expires.

### Why credentials in plaintext here

- chmod 600, owner-only read
- Outside the git repo (`~/.nuzantara/`, not `~/Desktop/nuzantara/`)
- Never sourced by committed scripts (only `playwright_login.py` reads it, and only on demand)
- Not in `~/.nuzantara-secrets.env` — that file is sandbox-locked and used for runtime API keys; this one is for one-shot logins
- Alternative is macOS Keychain — more secure but adds a prompt every login; not worth it for this use case

### Flow per site

- **Canva** → `login_via: google_oauth`: script clicks "Continue with Google" first, then fills Google creds
- **Gemini / Flow** → `login_via: google_direct`: Google's own login page, fill creds
- **ChatGPT** → `login_via: openai_direct`: OpenAI form, fill creds

All flows then pause at 2FA waiting for your phone/app confirmation. Press Enter in terminal to save + close.

## Cron usage (headed or headless)

```python
ctx = p.chromium.launch_persistent_context(
    user_data_dir=str(profile_dir),
    headless=True,   # True for cron unless site blocks it
    args=[
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",  # if running under launchd
    ],
    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
)
```

### Google sites specifically

Google detects `headless=True` even with flags. Options:

1. **Xvfb wrapper** (runs a virtual display, browser thinks it's headed):
   ```bash
   /opt/homebrew/bin/Xvfb :99 -screen 0 1440x900x24 &
   DISPLAY=:99 python3 script.py
   ```
   macOS note: Xvfb not stock, install via `brew install --cask xquartz` or use Linux VM.

2. **Headed but hidden window** (macOS):
   ```python
   ctx = p.chromium.launch_persistent_context(..., headless=False)
   # Move window off-screen: page.evaluate("() => window.moveTo(-2000, -2000)")
   ```
   Ugly but works on local cron.

3. **Accept detection, use Canva Magic Media instead** (Canva doesn't care about headless).

## Login expired — Recovery

Signs login expired:
- Redirect to `/login` or `/signin` on navigate
- "Continue with Google" prompt appears
- `document.cookie` missing known auth keys (e.g. Canva's `cfuvid`, Google's `SID`)

Recovery:
```bash
# Delete session state, re-login
rm -rf ~/.nuzantara/playwright-profiles/<site>
python3 scripts/playwright_login.py <site>
```

Do NOT try to refresh OAuth tokens programmatically — not worth the complexity.

## Add a new site

1. Pick a slug (lowercase, one word)
2. Create dir: `mkdir ~/.nuzantara/playwright-profiles/<slug>`
3. Add to `SITES` dict in `playwright_login.py`
4. Run `python3 scripts/playwright_login.py <slug>`
5. Add section to `SITE-PLAYBOOK.md` with selectors + flow
6. Add row to `NEXT-CLAUDE-README.md § Status matrix`

## Anti-bot cheat sheet

| Signal | Countermeasure |
|---|---|
| `navigator.webdriver === true` | `--disable-blink-features=AutomationControlled` (removes it) |
| Plasticine-perfect mouse paths | Use `page.mouse.move` with jitter, or `page.click` (library handles) |
| No `window.chrome` | Chromium has it; plain Chromium headless doesn't — use `channel="chrome"` if installed |
| reCAPTCHA pops up | Usually means fingerprint drift; run headed once to re-calibrate |
| IP fingerprint | Home IP is fine; AWS/GCP IPs get blocked instantly |

## Health check

```bash
# List profiles + last-modified
ls -lt ~/.nuzantara/playwright-profiles/
# If a profile's Default/Cookies file is >30d old, consider preemptive re-login
```

_Last updated: 2026-04-24_
