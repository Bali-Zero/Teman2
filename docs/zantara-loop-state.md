# Zantara WA loop — state ledger

> Read at Step 0 of every `/bot` loop iteration, updated at Step 6. Numbers are stamped with the
> day they were measured; re-measure before trusting any of them.

## Instrument corrections (read before the KPI panel)

- **T1-T5 must be measured on Pro, not on Fly.** Since the 2026-05-24 wa-mirror local-only
  cutover (Symbiosis Law 2), `whatsapp_message_context`, `whatsapp_team_sessions`,
  `team_promises` and `action_queue` on Fly are frozen at 2026-05-25 by design. The live mirror
  writes to Pro `nuzantara_dev` (`ssh pro`, `psql -h 127.0.0.1 -d nuzantara_dev`). No
  backend-rag code reads Fly `whatsapp_team_sessions` (only migrations reference it).
- **Per-line mirror liveness has a dedicated organ**: `scripts/wa_session_liveness.py` (Pro cron
  08:15 daily, 72h threshold, Telegram alert). Read its log
  (`~/logs/cron-tmp/wa-session-liveness.log` on Pro) instead of `whatsapp_team_sessions.status`,
  which churns through janitor-ghost-cleanup rows on Pro as well.
- **F2 must exclude `superseded_by_coalescing`.** It is burst dedup, not a send attempt: the row
  never reaches Meta. A real delivery failure has a `meta_message_id` or a Meta error.
- **Broker liveness is `wa_broker_gauge.broker_last_seen_at` advancing** (the daemon polls every
  2s), never `breaker_state` — the breaker stays `closed` while the daemon is paused.

## Iteration 1 — 2026-09-25 (M5)

| Gate    | Re-measured                                                                                                                                                                                                                                                                                                                            | Verdict                                  |
| ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| T1      | Pro mirror alive: 1,641 rows/24h, 7,470/7d. Lines: 4/7 OK (Ari, Asya, Krisna, Surya); Adit `401 logged_out` (~22 d), Damar `401 logged_out` (~43 d), Vino no-link (~48 d)                                                                                                                                                              | BLOCKED — QR re-pair, operator[physical] |
| T2      | Watchdog exists and alerts daily by name; the three stale lines have been alerted every day with no action                                                                                                                                                                                                                             | organ OK, human loop open                |
| F2      | 14 d: 7 `failed` outbound = 4 `superseded_by_coalescing` (benign) + 2 `standing_no_customer_message` on image-only inbound (client re-sent the photo, got silence, nobody notified) + 1 `broker_absent` (apology sent). Real Meta send failures: 0 of 33 sent                                                                          | re-scoped, see below                     |
| F2-live | **Outage in progress at measurement time**: Homebrew codex on Pro upgraded to 0.156.1 at 2026-09-25 01:07 WITA; the broker daemon (alive, pid 565) stopped claiming on the version-pin mismatch; gauge frozen at 2026-09-24T17:10:32Z; seat sentinel RED `daemon_silent` from 01:30 WITA. Every inbound ends `broker_absent` → apology | BLOCKED — pin bump, operator[credential] |
| F1      | `ack_sent_at` NULL on all rows in 14 d                                                                                                                                                                                                                                                                                                 | not started                              |
| F3      | mean `evidence_score` 0.30 on 21 codex `done` rows, 0.08 on 9 route-less `done` rows                                                                                                                                                                                                                                                   | not started                              |

### Decisions / actions for the owner

1. **Restore the bot (urgent)** — on Pro: `sudo grep '^WA_CODEX_CLI_VERSION_PIN=' /Users/zantara-codex/.wa-codex-broker.env`, set it to `0.156.1` (all five exec flags the daemon passes exist in 0.156.1 `exec --help`), then `sudo launchctl kickstart -k system/com.balizero.wa-codex-broker`. Prove it with two ADVANCING reads of `wa_broker_gauge.broker_last_seen_at`.
2. **QR re-pair** for Adit and Damar (logged out), and decide whether Vino's line is still wanted.

### Next gap

F2 structural half: image-only inbound gets `standing_no_customer_message` → five retries →
silence with no human notified. Then the pin-drift class: the daemon shares the Homebrew codex
with every agent seat, so any seat upgrade silently stops the bot.
