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

The watchdog exchanges the current long-lived token for a fresh one
**before** it expires (Graph API `fb_exchange_token` flow), so a valid token
only needs to be landed by hand **once**.

## What it does (one pass)

1. `GET /debug_token` — validity + expiry of the current token.
2. Durability gate: if `days_remaining >= threshold` (default **7**), do
   nothing (`action=fresh`). Never churns a healthy token.
3. If expiring: `GET /oauth/access_token?grant_type=fb_exchange_token&...`
   → new long-lived token (~60 more days).
4. If `IG_TOKEN_ENV_FILE` is set: atomically rewrites the token line in that
   env file (mode forced to **0600**, scar #4). It **refuses to create** the
   file — the first landing is operator-owned.
5. Provenance log **never contains the token**:
   `[ig-token-watchdog] refreshed, new expiry=YYYY-MM-DD`. An httpx-logger
   redaction filter also masks the query params httpx would otherwise print
   at INFO.

## Invocation (one-shot, works today)

```bash
cd apps/backend-rag && source .venv/bin/activate
set -a && source ~/.nuzantara-backend-secrets.env && set +a   # names only; never cat this file
IG_TOKEN_ENV_FILE=~/.nuzantara-backend-secrets.env \
PYTHONPATH=. python -m backend.services.measurer.ig_token_watchdog
```

Required env (values live in the secrets env file, 0600):

| Var                                                 | Meaning                                                                          |
| --------------------------------------------------- | -------------------------------------------------------------------------------- |
| `IG_LONG_LIVED_TOKEN` (or `INSTAGRAM_ACCESS_TOKEN`) | current token — same precedence as the sampler                                   |
| `META_APP_ID` / `META_APP_SECRET`                   | the Meta app that issued the token (exchange flow requires app creds)            |
| `IG_TOKEN_ENV_FILE`                                 | optional — env file to persist the refreshed token into (key rewritten in place) |
| `IG_TOKEN_REFRESH_THRESHOLD_DAYS`                   | optional — default 7                                                             |

Exit codes: `0` fresh/refreshed · `1` config missing · `2` token invalid or
refresh failed (→ a NEW token must be landed by the operator).

## Arming (deliberately NOT done by this PR)

- **First valid token** — `operator[secret]`. As of 2026-07-13 the only
  valid token lives as Fly secret `INSTAGRAM_ACCESS_TOKEN` on `nuzantara-rag`
  (not extractable); Pro's measurer env has no token; Mini's
  `IG_LONG_LIVED_TOKEN` is malformed (Graph error 190). Landing: generate a
  long-lived token for the app in Meta Developers → put it in Pro's secrets
  env file (0600) under `IG_LONG_LIVED_TOKEN`, plus `META_APP_ID` /
  `META_APP_SECRET` if absent.
- **Cron arming** — `operator[control-plane]` (no new daemon without a
  decision: 176 daemons + W84). Recommended shape: NOT a new plist — add a
  watchdog step to the existing measurer wrapper so it runs right before
  `scheduler_cli` on the same 6h tick:

  ```bash
  # inside the measurer wrapper, before the scheduler invocation:
  IG_TOKEN_ENV_FILE="$SECRETS_ENV" PYTHONPATH=. \
    python -m backend.services.measurer.ig_token_watchdog \
    || echo "[measurer] token watchdog exit=$? (2 = operator must land a new token)"
  # then re-source $SECRETS_ENV so a refreshed token reaches scheduler_cli
  ```

- **Proof-of-armed**: measurer log shows a `[ig-token-watchdog]` line each
  tick, and — after a real refresh window — `posts_measured > 0` continues
  past the old token's expiry date.

## Failure modes

| Symptom                                   | Meaning                                                         | Action                                                                       |
| ----------------------------------------- | --------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| `token INVALID: code 190 ...`             | token already dead/malformed — refresh flow cannot resurrect it | operator lands a new token (see above)                                       |
| `refresh FAILED: ...`                     | Graph rejected the exchange (app creds wrong, token too old)    | check `META_APP_ID`/`META_APP_SECRET`; if token expired, land a new one      |
| `refreshed but IG_TOKEN_ENV_FILE not set` | new token obtained and **dropped**                              | set `IG_TOKEN_ENV_FILE`; the old token stays valid until its original expiry |
| `env file not found`                      | persist target missing                                          | first landing is operator-owned; watchdog only rotates existing installs     |
