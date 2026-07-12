# IG token watchdog (Task 30) — keep the measurer's Meta token alive

> Module: `apps/backend-rag/backend/services/measurer/ig_token_watchdog.py`
> Tests: `apps/backend-rag/backend/tests/services/measurer/test_ig_token_watchdog.py`
> Ledger: `.claude/skills/modus/PENDING-ARMS.md` (measurer double-starve line)

## Why

The WR2 measurer (`com.balizero.wr2.measurer` → `scheduler_cli.py` →
`MetaGraphSampler`) is the learning-loop's food supply: it samples IG
engagement for published carousels. Its Meta **long-lived token expires
after ~60 days** — when it dies, the sampler logs
`no samplers available; set IG_LONG_LIVED_TOKEN or INSTAGRAM_ACCESS_TOKEN`
every 6 hours and the loop silently starves (observed live since 2026-05-24).

The watchdog refreshes the token **before** it expires, so a valid token
only needs to be landed by hand **once**.

## The two token families (get this wrong = watchdog is useless)

| Family                                               | Host                  | Refresh flow                                            | Needs app creds                   | Expiry introspection                                                                        |
| ---------------------------------------------------- | --------------------- | ------------------------------------------------------- | --------------------------------- | ------------------------------------------------------------------------------------------- |
| `instagram` (**default** — the verified live family) | `graph.instagram.com` | `GET /refresh_access_token?grant_type=ig_refresh_token` | no                                | none server-side → local state sidecar (`IG_TOKEN_STATE_FILE`, dates only, never the token) |
| `facebook`                                           | `graph.facebook.com`  | `GET /oauth/access_token?grant_type=fb_exchange_token`  | `META_APP_ID` + `META_APP_SECRET` | `GET /debug_token`                                                                          |

The live Fly secret `INSTAGRAM_ACCESS_TOKEN` is an _Instagram API with
Instagram Login_ token (probe 2026-06-25, see the comment block in
`scripts/wr2_ig_publish.py`): it works **only** against `graph.instagram.com`
— `graph.facebook.com` answers `Cannot parse access token` (code 190).

**Corollary for the "malformed" Mini token**: Mini's `IG_LONG_LIVED_TOKEN`
failing with code 190 was probed against `graph.facebook.com`; before
declaring a token dead, probe it against **its own family host**. The same
applies to `MetaGraphSampler` itself: its default `graph_base` is
`graph.facebook.com` — an instagram-family token needs the sampler
constructed with `graph_base="https://graph.instagram.com"` (constructor
already accepts it; wiring an env override into `scheduler_cli._build_samplers`
is a small follow-up when the first token lands).

## What it does (one pass)

1. Establish remaining lifetime — `facebook`: `/debug_token`; `instagram`:
   read the state sidecar written by the previous refresh.
2. Durability gate: `days_remaining >= threshold` (default **7**) → do
   nothing (`action=fresh`). Explicit `expires_at=0` (never-expiring) → do
   nothing. **Unknown** expiry (absent field / no state file) → refresh
   conservatively, never assume immortality.
3. Refresh via the family's flow (~60 more days).
4. Persist: rewrites the token line in `IG_TOKEN_ENV_FILE` under an
   exclusive `flock` (a concurrent secrets-writer is never clobbered),
   atomic rename, mode forced **0600** (scar #4). Refuses to **create** the
   file — the first landing is operator-owned. For `instagram`, also writes
   the new expiry to `IG_TOKEN_STATE_FILE` (dates only).
5. Secret discipline: network/JSON failures map to `action=error` (never a
   raw traceback carrying `request.url`); Graph error messages are redacted
   before logging (a proxy may echo the URL, token inside); an httpx-logger
   filter masks query params at INFO. Provenance line:
   `[ig-token-watchdog] refreshed, new expiry=YYYY-MM-DD`.

## Invocation (one-shot, works today)

```bash
cd apps/backend-rag && source .venv/bin/activate
set -a && source ~/.nuzantara-backend-secrets.env && set +a   # names only; never cat this file
IG_TOKEN_ENV_FILE=~/.nuzantara-backend-secrets.env \
IG_TOKEN_STATE_FILE=~/.nuzantara-ig-token-state.json \
PYTHONPATH=. python -m backend.services.measurer.ig_token_watchdog
```

| Var                                                 | Meaning                                                                                                      |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `IG_LONG_LIVED_TOKEN` (or `INSTAGRAM_ACCESS_TOKEN`) | current token — same precedence as the sampler                                                               |
| `IG_TOKEN_FAMILY`                                   | `instagram` (default) or `facebook`                                                                          |
| `META_APP_ID` / `META_APP_SECRET`                   | required for `facebook` family only                                                                          |
| `IG_TOKEN_ENV_FILE`                                 | env file to persist the refreshed token into — **a refresh without it is a failure (exit 2)**, not a warning |
| `IG_TOKEN_STATE_FILE`                               | `instagram` family expiry sidecar; without it every tick refreshes (harmless but chatty)                     |
| `IG_TOKEN_REFRESH_THRESHOLD_DAYS`                   | optional — default 7                                                                                         |

Exit codes: `0` fresh, or refreshed+persisted · `1` config error ·
`2` token invalid / refresh failed / network failure / refresh-not-persistable.

## Arming (deliberately NOT done by this PR)

- **First valid token** — `operator[secret]`. As of 2026-07-13 the only
  known-valid token lives as Fly secret `INSTAGRAM_ACCESS_TOKEN` on
  `nuzantara-rag` (not extractable); Pro's measurer env has no token; Mini's
  `IG_LONG_LIVED_TOKEN` fails 190 **on the facebook host** — re-probe it
  against `graph.instagram.com` before writing it off. Landing: put a
  long-lived token in Pro's secrets env (0600) under `IG_LONG_LIVED_TOKEN`.
- **Cron arming** — `operator[control-plane]` (no new daemon: 176 daemons +
  W84). Recommended: NOT a new plist — a watchdog step inside the existing
  measurer wrapper, before `scheduler_cli`, same 6h tick:

  ```bash
  IG_TOKEN_ENV_FILE="$SECRETS_ENV" IG_TOKEN_STATE_FILE="$HOME/.nuzantara-ig-token-state.json" \
    PYTHONPATH=. python -m backend.services.measurer.ig_token_watchdog
  rc=$?
  [ $rc -eq 2 ] && echo "[measurer] token watchdog NEEDS OPERATOR (exit 2)"
  # re-source $SECRETS_ENV so a refreshed token reaches scheduler_cli
  ```

- **Proof-of-armed**: a `[ig-token-watchdog]` line in the measurer log each
  tick, and `posts_measured > 0` continuing past the old token's expiry date.

## Failure modes

| Symptom                                            | Meaning                             | Action                                                                                 |
| -------------------------------------------------- | ----------------------------------- | -------------------------------------------------------------------------------------- |
| `token INVALID: code 190 ...` (facebook family)    | token dead **or wrong family**      | re-probe on `graph.instagram.com` first; if genuinely dead, operator lands a new token |
| `ig refresh failed: ...`                           | token <24h old, expired, or revoked | if just-issued wait a day; else land a new token                                       |
| `refreshed but IG_TOKEN_ENV_FILE not set` → exit 2 | new token obtained and **dropped**  | set `IG_TOKEN_ENV_FILE`; the old token stays valid until its original expiry           |
| `network failure calling Graph` → exit 2           | transient connectivity              | next tick retries; alert only if persistent                                            |
| `env file not found`                               | persist target missing              | first landing is operator-owned; watchdog only rotates existing installs               |
