# Playwright Automation — Entry Point for Next Claude

**Read this first. Time budget: 60 seconds.**

## What's here

Playwright-based browser automation for WR2 carousel pipeline and one-off research. All sessions use **persistent profiles** in `~/.nuzantara/playwright-profiles/` — login once, cron reuses forever.

## Decision tree

```
Need to generate an image?
├── Editorial cover (best quality) → SITE-PLAYBOOK.md § Gemini
├── Inside Canva carousel (no download/upload) → SITE-PLAYBOOK.md § Canva Magic Media
├── Batch / quota-light → SITE-PLAYBOOK.md § Flow
└── Google blocking → SITE-PLAYBOOK.md § ChatGPT (fallback)

Need to edit a Canva design (e.g. WR2 template DAHE6lx1lf8)?
└── SITE-PLAYBOOK.md § Canva Editor

Login expired / selector broken?
└── SITE-PLAYBOOK.md § Recovery (for the affected site)

Need to add a new site?
└── PROFILES.md § Add a new site
```

## Files in this directory

| File | Purpose | When to read |
|---|---|---|
| `NEXT-CLAUDE-README.md` | This file — entry point | Every session |
| `SITE-PLAYBOOK.md` | Per-site selectors, flows, gotchas (narrative) | When touching a specific site |
| `sites/*.yaml` | **Machine-readable source of truth** (one file per site) | Consumed by `inject.py`, read by humans for editing |
| `PROFILES.md` | Profile dir structure + login persistence mechanics | When setting up a new site or recovering login |
| `HOOK-SETUP.md` | One-time activation of auto-injection hook | First setup only |

## Tooling

- `scripts/playwright/playwright_login.py` — headed first-time login per site, auto-fills creds, waits for 2FA
- `tools/playwright-context/inject.py` — emit site context (markdown/compact/json) for any LLM
- `tools/playwright-context/cross-llm-wrapper.sh` — wrap claude/gemini/codex/ollama with auto-injected context
- `~/.claude/hooks/playwright-context-inject.sh` — PreToolUse hook; auto-injects context on `mcp__playwright__*` tool calls. Activation steps in `HOOK-SETUP.md`.

## Cross-LLM usage

```bash
# Direct CLI invocation with context:
tools/playwright-context/cross-llm-wrapper.sh gemini canva edit_template_text -- "slide 3: replace headline"

# Inside a cron script:
CTX=$(python3 tools/playwright-context/inject.py --site canva --format markdown)
gemini -m gemini-3.1-pro-preview -p "$CTX\n\n---\n\nEdit slide 3..."

# Claude Code: context auto-injected via PreToolUse hook (see HOOK-SETUP.md)
```

## Status matrix

| Site | Purpose | Profile | YAML | Last login | Known issues |
|---|---|---|---|---|---|
| canva.com | Magic Media + design edit | `~/.nuzantara/playwright-profiles/canva` | `sites/canva.yaml` ✅ | _pending_ | OAuth via Google, quota ~100/day |
| gemini.google.com | Imagen image gen | `~/.nuzantara/playwright-profiles/gemini` | `sites/gemini.yaml` ✅ | _pending_ | Google anti-bot; needs headed or Xvfb |
| labs.google/fx/tools/flow | Imagen 4 / Veo | `~/.nuzantara/playwright-profiles/flow` | `sites/flow.yaml` ✅ | _pending_ | Subscription required, UI beta |
| chat.openai.com | DALL-E fallback | `~/.nuzantara/playwright-profiles/chatgpt` | _not yet_ | _pending_ | Rate limits |

**Update "Last login" date after each successful `playwright_login.py <site>` run.**

_Update the **Verified** column every time you run through a site. Empty = not yet validated this cycle._

## Hard rules

1. **Never hardcode selectors in cron scripts.** Selectors live in `SITE-PLAYBOOK.md`; scripts import from a shared module.
2. **Never commit profile dirs.** `~/.nuzantara/playwright-profiles/` is outside the repo on purpose — contains session cookies.
3. **Never run Google sites fully headless** without `--disable-blink-features=AutomationControlled` + realistic UA. Google detects plain-vanilla headless in <5s.
4. **Always update `Verified` date** after a successful run. A 3-month-old verification is a warning flag, not a guarantee.
5. **When a selector breaks, fix the playbook FIRST, then the script.** Single source of truth.

## The "new Claude starts" ritual

1. Read this file (you're doing it).
2. Read `SITE-PLAYBOOK.md` section(s) for the site(s) you'll touch.
3. If verified date >30d old, run a dry-run first (navigate, take screenshot, abort before destructive step).
4. If login expired, follow `PROFILES.md § Recovery`.
5. Execute. On finish, update `Verified` column here + add notes to `SITE-PLAYBOOK.md`.

## Escalation

- UI changed dramatically → snapshot HTML + screenshot, update SITE-PLAYBOOK before retrying
- Anti-bot blocks you → check PROFILES.md § Anti-bot; don't brute-force
- Repeatedly broken → ping Antonello; don't loop

_Last updated: 2026-04-24_
