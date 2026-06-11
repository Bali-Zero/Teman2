# Lead intent matcher — runbook

**What**: `scripts/lead_intent_matcher.py` correlates anonymous WhatsApp-CTA
clicks (`lead_intents` rows written by `POST /api/lead/capture`) with clients
who show up on WhatsApp shortly after (phone match + 30-min window), and
writes the attribution back to `lead_intents.matched_client_id` +
`clients.lead_source` / `clients.lead_metadata`.

**Why it exists**: this is the wire that turns "we published 3,126 articles"
into "article X produced client Y and practice Z". Without it the
content→lead→revenue funnel is unmeasured (state found 2026-06-11: 5 intents,
0 matched, matcher never installed on Pro — the docstring still pointed to
the decommissioned Air checkout).

## Architecture

```
balizero.com article / kbli page
        │ click "Chat on WhatsApp"
        ▼
POST /api/lead/capture  (public, anonymous — Fly backend)
        │ INSERT lead_intents + returns pre-filled wa.me deeplink
        ▼
user lands on WhatsApp, team replies, client row appears/updates
        ▼
LaunchAgent com.nuzantara.lead-intent-matcher (Pro, every 5 min)
        │ scripts/lead_intent_matcher_run.sh → lead_intent_matcher.py
        ▼
lead_intents.matched_client_id + clients.lead_source populated
```

## Install (Pro)

```bash
cp infra/launchagents/com.nuzantara.lead-intent-matcher.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.nuzantara.lead-intent-matcher.plist
```

Requirements:

- `~/.nuzantara-secrets.env` (0600) must export `DATABASE_URL` pointing at the
  Fly Postgres reachable from the Pro. Until it does, every tick logs a
  `SKIP DATABASE_URL not set` line — unarmed-but-visible by design.
- venv: `~/Desktop/nuzantara/apps/backend-rag/.venv` (needs `asyncpg`).

## Verify

```bash
launchctl list | grep lead-intent-matcher          # loaded?
tail -5 ~/logs/lead-intent-matcher.log             # "pass complete rc=0"
# attribution actually flowing:
# SELECT count(*) FROM lead_intents WHERE matched_client_id IS NOT NULL;
```

## Uninstall / kill switch

```bash
launchctl bootout gui/$(id -u)/com.nuzantara.lead-intent-matcher
rm ~/Library/LaunchAgents/com.nuzantara.lead-intent-matcher.plist
```

## Gotchas

- **NO KeepAlive** in the plist — it's a one-shot cron (StartInterval).
  Adding KeepAlive recreates the W67 crash-loop signature.
- The matcher is read-only except the two attribution UPDATEs; safe at 5-min
  cadence, idempotent on retry.
- Matching is best-effort (phone + time window). Deterministic matching via
  the `Lead ID: li_…` line embedded in the wa.me message body is a known
  follow-up: no inbound parser exists yet (checked 2026-06-11).
